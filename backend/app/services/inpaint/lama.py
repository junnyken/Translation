"""LamaInpainter — chạy LaMa (bản finetune cho manga) qua ONNX Runtime.

Chỉ GỌI model weight; toàn bộ tiền/hậu xử lý (dựng mask, pad bội số 8, ghép ảnh) tự viết,
không copy code inference của repo gốc — giữ đúng guardrail kế thừa từ M1/M2.

Nguồn weight + license: xem docs/ARCH.md § Model weight.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

import numpy as np
from PIL import Image

from app.services.inpaint.mask import InvalidMask, build_mask, dilate_bboxes
from app.services.interfaces import BBox

logger = logging.getLogger(__name__)

#: LaMa (FFC) vỡ nếu cạnh ảnh không chia hết 8 — đã kiểm thật:
#: 1401x2001 -> ONNXRuntimeError ở node Mul; 1400x2000 -> chạy bình thường.
_SIZE_MULTIPLE = 8


class InpaintWeightsMissing(FileNotFoundError):
    """Không có weight — task fail ngay, KHÔNG lặng lẽ lùi về cv2.inpaint."""


class InpaintFailed(RuntimeError):
    pass


def gom_cum(masks: list, rong: int, cao: int, le: int) -> list[tuple[int, int, int, int]]:
    """Gom các vùng gần nhau thành từng CỤM, trả các ô cắt (x0, y0, x1, y1) đã nới lề.

    Vì sao phải cắt ô thay vì chạy cả trang: bộ nhớ LaMa tỉ lệ THUẬN với diện tích ảnh —
    đo thật **~1,6 GB cho mỗi triệu điểm ảnh**. Trang truyện thật ở cỡ đọc (1600x2259 ≈ 3,6
    triệu điểm) cần ~5,8 GB và bị hệ điều hành giết; ở cỡ in (2481x3503) cần ~14 GB.
    Cắt theo cụm thì bộ nhớ tỉ lệ với ô cắt chứ không với trang.

    Lề (`le`) là phần ảnh xung quanh để model có ngữ cảnh mà vẽ lại cho khớp nền.
    """
    o = []
    for m in masks:
        x0 = max(0, int(m.x) - le)
        y0 = max(0, int(m.y) - le)
        x1 = min(rong, int(m.x + m.w) + le)
        y1 = min(cao, int(m.y + m.h) + le)
        if x1 > x0 and y1 > y0:
            o.append([x0, y0, x1, y1])
    if not o:
        return []

    # Gộp các ô chồng nhau cho tới khi không gộp được nữa: hai bong bóng sát nhau mà chạy
    # model hai lần thì vùng giao bị vẽ đè hai lượt, dễ lộ đường nối.
    doi = True
    while doi:
        doi = False
        ket = []
        for c in o:
            for k in ket:
                if not (c[2] <= k[0] or c[0] >= k[2] or c[3] <= k[1] or c[1] >= k[3]):
                    k[0], k[1] = min(k[0], c[0]), min(k[1], c[1])
                    k[2], k[3] = max(k[2], c[2]), max(k[3], c[3])
                    doi = True
                    break
            else:
                ket.append(list(c))
        o = ket
    return [tuple(c) for c in o]


def _pad_to_multiple(arr: np.ndarray, multiple: int = _SIZE_MULTIPLE) -> tuple[np.ndarray, int, int]:
    """Pad mép phải/dưới cho chia hết `multiple`. Trả (mảng đã pad, pad_h, pad_w)."""
    h, w = arr.shape[-2], arr.shape[-1]
    pad_h = (-h) % multiple
    pad_w = (-w) % multiple
    if pad_h == 0 and pad_w == 0:
        return arr, 0, 0
    pad_spec = [(0, 0)] * (arr.ndim - 2) + [(0, pad_h), (0, pad_w)]
    # 'edge' để vùng pad nối tiếp nét vẽ, không tạo viền đen giả
    return np.pad(arr, pad_spec, mode="edge"), pad_h, pad_w


class LamaInpainter:
    """Implement Protocol `IInpainter` (M1). Không đổi tên method `inpaint`."""

    def __init__(
        self,
        weights_path: str,
        device: str = "cpu",
        dilate_ratio: float = 0.08,
        clean_suffix: str = "_clean",
        intra_op_threads: int = 0,
        whole_page_max_mpx: float = 2.5,
        tile_margin: int = 96,
    ) -> None:
        self.weights_path = weights_path
        self.device = device
        self.dilate_ratio = dilate_ratio
        self.clean_suffix = clean_suffix
        self.intra_op_threads = intra_op_threads
        #: Trang bao nhiêu triệu điểm ảnh trở xuống thì chạy CẢ TRANG một lượt (đường đã kiểm
        #: chứng ở M4). Lớn hơn thì chạy theo cụm, vì bộ nhớ LaMa ~1,6 GB / triệu điểm ảnh.
        self.whole_page_max_mpx = whole_page_max_mpx
        #: Lề ảnh giữ quanh mỗi cụm để model có ngữ cảnh vẽ lại cho khớp nền.
        self.tile_margin = tile_margin
        self._session = None
        self._lock = threading.Lock()

    # ---------- model ----------
    def _providers(self) -> list[str]:
        if self.device.lower() in ("cuda", "gpu"):
            return ["CUDAExecutionProvider", "CPUExecutionProvider"]
        return ["CPUExecutionProvider"]

    def _get_session(self):
        if self._session is None:
            with self._lock:
                if self._session is None:
                    if not Path(self.weights_path).is_file():
                        raise InpaintWeightsMissing(
                            f"Không thấy weight LaMa tại '{self.weights_path}'. "
                            "Đặt INPAINT_WEIGHTS_PATH trong .env và tải theo docs/ARCH.md."
                        )
                    import onnxruntime as ort  # import trễ: tiến trình API không bao giờ nạp

                    opts = ort.SessionOptions()
                    if self.intra_op_threads > 0:
                        opts.intra_op_num_threads = self.intra_op_threads
                    logger.info("Nạp LaMa ONNX từ %s (device=%s)", self.weights_path, self.device)
                    self._session = ort.InferenceSession(
                        self.weights_path, sess_options=opts, providers=self._providers()
                    )
        return self._session

    # ---------- helper dùng chung với bước kiểm chứng ----------
    def dilated_masks(self, image_w: int, image_h: int, masks: list[BBox]) -> list[BBox]:
        """Đúng các bbox đã nới mà mask dùng — để bước verify OCR lại đúng vùng đã xoá."""
        return dilate_bboxes(masks, image_w, image_h, self.dilate_ratio)

    def clean_path_for(self, image_path: str) -> Path:
        """Đường dẫn ảnh clean: file MỚI cạnh ảnh gốc, luôn khác tên ảnh gốc."""
        src = Path(image_path)
        target = src.with_name(f"{src.stem}{self.clean_suffix}.png")
        if target.resolve() == src.resolve():
            raise InpaintFailed("Đường dẫn ảnh clean trùng ảnh gốc — từ chối ghi đè")
        return target

    # ---------- API công khai ----------
    def _chay_model(self, rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """Chạy LaMa trên một mảng ảnh HWC (0..1) + mask HW, trả ảnh dự đoán HWC cùng cỡ."""
        cao, rong = mask.shape
        chw = rgb.transpose(2, 0, 1)[None]  # 1,3,H,W
        mask_in = mask[None, None]  # 1,1,H,W

        padded_img, pad_h, pad_w = _pad_to_multiple(chw)
        padded_mask, _, _ = _pad_to_multiple(mask_in)

        session = self._get_session()
        in_names = [i.name for i in session.get_inputs()]
        outputs = session.run(None, {in_names[0]: padded_img.astype(np.float32),
                                     in_names[1]: padded_mask.astype(np.float32)})
        pred = outputs[0]
        if pred.ndim != 4:
            raise InpaintFailed(f"Output LaMa có shape lạ: {pred.shape}")

        pred = pred[0, :, : padded_img.shape[2] - pad_h, : padded_img.shape[3] - pad_w]
        pred_hwc = np.clip(pred.transpose(1, 2, 0), 0.0, 1.0)
        if pred_hwc.shape[:2] != (cao, rong):
            raise InpaintFailed(f"LaMa trả ảnh {pred_hwc.shape[:2]} khác đầu vào {(cao, rong)}")
        return pred_hwc

    def inpaint(self, image_path: str, masks: list[BBox]) -> str:
        """Xoá chữ trong các vùng mask, trả ĐƯỜNG DẪN ẢNH CLEAN (file mới).

        KHÔNG bao giờ ghi đè ảnh gốc — đây là invariant quan trọng nhất của M4.
        """
        src = Path(image_path)
        if not src.is_file():
            raise FileNotFoundError(f"Không thấy ảnh tại '{image_path}'")
        if not masks:
            raise InvalidMask("Không có vùng nào để xoá chữ (masks rỗng)")

        with Image.open(src) as im:
            image = im.convert("RGB")
            width, height = image.size
            rgb = np.asarray(image, dtype=np.float32) / 255.0  # HWC

        mask = build_mask(width, height, masks, self.dilate_ratio)  # HW, 1 = xoá
        if mask.max() <= 0:
            raise InvalidMask("Mask rỗng sau khi dựng — không có gì để xoá")

        trieu_diem = (width * height) / 1e6
        if trieu_diem <= self.whole_page_max_mpx:
            # Trang nhỏ: chạy cả trang một lượt như M4 đã kiểm chứng.
            pred_hwc = self._chay_model(rgb, mask)
        else:
            # Trang lớn: chạy theo từng cụm bong bóng, nếu không sẽ hết bộ nhớ.
            pred_hwc = rgb.copy()
            cum = gom_cum(masks, width, height, self.tile_margin)
            logger.info(
                "Ảnh %dx%d (%.1f triệu điểm) vượt ngưỡng %.1f -> xoá chữ theo %d cụm",
                width, height, trieu_diem, self.whole_page_max_mpx, len(cum),
            )
            for x0, y0, x1, y1 in cum:
                o_anh = rgb[y0:y1, x0:x1]
                o_mask = mask[y0:y1, x0:x1]
                if o_mask.max() <= 0:
                    continue
                pred_hwc[y0:y1, x0:x1] = self._chay_model(o_anh, o_mask)

        # Chỉ thay pixel TRONG mask; ngoài mask giữ nguyên từng pixel của ảnh gốc
        # (tránh model làm mờ cả trang).
        mask3 = mask[:, :, None]
        blended = rgb * (1.0 - mask3) + pred_hwc * mask3
        out = Image.fromarray((blended * 255.0).round().astype(np.uint8), mode="RGB")

        target = self.clean_path_for(image_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        out.save(target, format="PNG")
        logger.info("Ảnh clean: %s (%d vùng, %.1f%% diện tích)", target, len(masks), mask.mean() * 100)
        return str(target)
