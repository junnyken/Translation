"""CTDDetector — chạy comic-text-detector qua ONNX Runtime.

Chỉ GỌI model weight qua onnxruntime; không copy code inference của repo gốc (giữ đúng
guardrail "không nhúng code GPL" của M1). Tiền/hậu xử lý (letterbox, giải mã YOLO, NMS)
viết lại từ đầu trong file này và trong `geometry.py`.

Nguồn weight + license: xem docs/ARCH.md § Model weight.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from app.services.detect.geometry import Detection, InvalidBBox, build_bbox, nms
from app.services.interfaces import BBox

logger = logging.getLogger(__name__)

#: Giá trị pad của letterbox — giữ tỷ lệ ảnh, phần thừa tô xám trung tính.
_PAD_VALUE = 114


@dataclass(frozen=True)
class DetectedRegion:
    """Kết quả detect có kèm confidence.

    `IDetector.detect()` chốt ở M1 chỉ trả `list[BBox]` (không chỗ nào chứa confidence),
    nên M2 bổ sung `detect_regions()` trả thêm confidence/cls. Protocol M1 GIỮ NGUYÊN,
    `detect()` vẫn là method chính thức — xem docs/REPORT_M2.md § lệch spec.
    """

    bbox: BBox
    #: E46 — `None` nghia la engine KHONG tra diem tin cay (Gemini), khac han diem THAP.
    #: Dien mot so cho gon la bia ra con so khong ton tai — xem `ConfidenceState.unavailable`.
    confidence: float | None
    cls: int
    #: E90 — chữ engine đọc được kèm khung (Gemini). None = engine chỉ cho khung (CTD).
    chu: str | None = None
    #: E96 — bản dịch ngữ cảnh đi kèm ngay trong lượt nhận diện gộp (chế độ `chi_chu`).
    ban_dich: str | None = None
    #: E96 — cờ báo mô hình phải đoán chữ gốc khi dịch trong lượt gộp.
    doan: bool = False


class ModelWeightsMissing(FileNotFoundError):
    """Không tìm thấy file weight — dừng và báo, tuyệt đối không detect bằng weight giả."""


class CTDDetector:
    """Implement Protocol `IDetector` (M1). Không đổi tên method `detect`."""

    def __init__(
        self,
        weights_path: str,
        device: str = "cpu",
        conf_threshold: float = 0.5,
        raw_min_conf: float = 0.25,
        nms_iou: float = 0.45,
        input_size: int = 1024,
        intra_op_threads: int = 0,
        cpu_mem_arena: bool = True,
    ) -> None:
        self.weights_path = weights_path
        self.device = device
        #: Ngưỡng phân loại low_confidence — CTDDetector KHÔNG tự lọc theo ngưỡng này,
        #: việc gắn cờ/lọc là của Celery task (giữ detector chỉ làm 1 việc: trả kết quả thô).
        self.conf_threshold = conf_threshold
        #: Sàn nhiễu trước NMS (khác conf_threshold): dưới mức này là rác của YOLO head.
        self.raw_min_conf = raw_min_conf
        self.nms_iou = nms_iou
        self.input_size = input_size
        self.intra_op_threads = intra_op_threads
        self.cpu_mem_arena = cpu_mem_arena
        self._session = None
        self._lock = threading.Lock()
        self._infer_lock = threading.Lock()
        self.mat_na_chu = None

    # ---------- model ----------
    def _providers(self) -> list[str]:
        if self.device.lower() in ("cuda", "gpu"):
            return ["CUDAExecutionProvider", "CPUExecutionProvider"]
        return ["CPUExecutionProvider"]

    def _get_session(self):
        """Load ONNX 1 lần/process (model ~91MB, load lại mỗi ảnh sẽ rất chậm)."""
        if self._session is None:
            with self._lock:
                if self._session is None:
                    if not Path(self.weights_path).is_file():
                        raise ModelWeightsMissing(
                            f"Không thấy model weight tại '{self.weights_path}'. "
                            "Đặt MODEL_WEIGHTS_PATH trong .env và tải weight theo docs/ARCH.md."
                        )
                    import onnxruntime as ort  # import trễ: tiến trình API không bao giờ nạp

                    opts = ort.SessionOptions()
                    if self.intra_op_threads > 0:
                        opts.intra_op_num_threads = self.intra_op_threads
                    # CTD letterbox về một kích thước cố định ⇒ một shape duy nhất ⇒ arena
                    # không phình. Khác hẳn LaMa (dynamic shape) — xem lama.py.
                    opts.enable_cpu_mem_arena = self.cpu_mem_arena
                    logger.info(
                        "Nạp CTD ONNX từ %s (device=%s, arena=%s)",
                        self.weights_path, self.device, self.cpu_mem_arena,
                    )
                    self._session = ort.InferenceSession(
                        self.weights_path, sess_options=opts, providers=self._providers()
                    )
        return self._session

    # ---------- tiền xử lý ----------
    def _letterbox(self, image: Image.Image) -> tuple[np.ndarray, float, int, int]:
        size = self.input_size
        w, h = image.size
        scale = min(size / w, size / h)
        new_w, new_h = round(w * scale), round(h * scale)
        canvas = Image.new("RGB", (size, size), (_PAD_VALUE,) * 3)
        pad_x, pad_y = (size - new_w) // 2, (size - new_h) // 2
        canvas.paste(image.resize((new_w, new_h), Image.BILINEAR), (pad_x, pad_y))
        tensor = np.asarray(canvas, dtype=np.float32).transpose(2, 0, 1)[None] / 255.0
        return tensor, scale, pad_x, pad_y

    # ---------- hậu xử lý ----------
    def _decode(
        self, raw: np.ndarray, scale: float, pad_x: int, pad_y: int, img_w: int, img_h: int
    ) -> list[Detection]:
        """Giải mã output YOLO `blk` [1, N, 4+1+num_classes] về bbox toạ độ ảnh gốc."""
        pred = raw[0]
        obj = pred[:, 4]
        cls_scores = pred[:, 5:]
        conf = obj * cls_scores.max(axis=1)
        keep = conf >= self.raw_min_conf
        if not keep.any():
            return []

        pred, conf = pred[keep], conf[keep]
        cls_idx = cls_scores[keep].argmax(axis=1)

        cx, cy, bw, bh = pred[:, 0], pred[:, 1], pred[:, 2], pred[:, 3]
        # bỏ padding rồi chia scale để về hệ toạ độ ảnh gốc
        x1 = (cx - bw / 2 - pad_x) / scale
        y1 = (cy - bh / 2 - pad_y) / scale
        x2 = (cx + bw / 2 - pad_x) / scale
        y2 = (cy + bh / 2 - pad_y) / scale

        detections: list[Detection] = []
        dropped = 0
        for i in range(len(conf)):
            try:
                bbox = build_bbox(float(x1[i]), float(y1[i]), float(x2[i]), float(y2[i]), img_w, img_h)
            except InvalidBBox:
                dropped += 1
                continue
            detections.append(Detection(bbox=bbox, confidence=float(conf[i]), cls=int(cls_idx[i])))
        if dropped:
            logger.warning("Bỏ %d box nằm ngoài ảnh sau khi clamp", dropped)
        return nms(detections, self.nms_iou)

    # ---------- API công khai ----------
    def detect_regions_va_mat_na(self, image_path: str) -> tuple[list[DetectedRegion], np.ndarray | None]:
        """Chạy inference an toàn luồng, trả (regions chưa lọc conf_threshold, mat_na_chu uint8 0/255)."""
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(f"Không thấy ảnh tại '{image_path}'")

        with Image.open(path) as im:
            image = im.convert("RGB")
            img_w, img_h = image.size
            tensor, scale, pad_x, pad_y = self._letterbox(image)

        session = self._get_session()
        input_name = session.get_inputs()[0].name
        with self._infer_lock:
            outputs = session.run(None, {input_name: tensor})
            blk = outputs[0]  # 'blk': [1, N, 4+1+num_classes]
            # E79 — `seg` [1,1,S,S] là mặt nạ ĐIỂM ẢNH của chữ; giữ lại (cỡ ảnh gốc)
            # để bước xoá chữ xoá theo nét thay vì cả khung.
            mat_na: np.ndarray | None = None
            if len(outputs) > 1 and getattr(outputs[1], "ndim", 0) == 4:
                from app.services.inpaint.mat_na_net import seg_ve_anh_goc

                mat_na = seg_ve_anh_goc(outputs[1][0, 0], scale, pad_x, pad_y, img_w, img_h)
            self.mat_na_chu = mat_na

        detections = self._decode(blk, scale, pad_x, pad_y, img_w, img_h)
        regions = [DetectedRegion(bbox=d.bbox, confidence=d.confidence, cls=d.cls) for d in detections]
        return regions, mat_na

    def detect_regions(self, image_path: str) -> list[DetectedRegion]:
        """Chạy inference, trả list box + confidence (đã NMS, CHƯA lọc theo conf_threshold)."""
        regions, _ = self.detect_regions_va_mat_na(image_path)
        return regions

    def detect(self, image_path: str) -> list[BBox]:
        """Đúng signature Protocol `IDetector` đã chốt ở M1."""
        return [r.bbox for r in self.detect_regions(image_path)]


_BANG_BASE36 = "0123456789abcdefghijklmnopqrstuvwxyz"


def _ma_hoa_base36(n: int) -> str:
    if n <= 0:
        return "0"
    ky_tu: list[str] = []
    val = int(n)
    while val > 0:
        val, du = divmod(val, 36)
        ky_tu.append(_BANG_BASE36[du])
    ky_tu.reverse()
    return "".join(ky_tu)


def ma_hoa_mat_na_vung_rle(
    mat_na_chu: np.ndarray | None,
    x: float,
    y: float,
    w: float,
    h: float,
) -> str | None:
    """Nén RLE base36 mặt nạ nét chữ nhị phân nằm gọn trong hộp `(x, y, w, h)` để gửi về Extension."""
    if mat_na_chu is None or getattr(mat_na_chu, "ndim", 0) < 2:
        return None
    H, W = mat_na_chu.shape[:2]
    x0 = max(0, int(round(x)))
    y0 = max(0, int(round(y)))
    x1 = min(W, int(round(x + w)))
    y1 = min(H, int(round(y + h)))
    rw, rh = x1 - x0, y1 - y0
    if rw <= 0 or rh <= 0:
        return None
    sub = (mat_na_chu[y0:y1, x0:x1] > 0).astype(np.uint8).ravel()
    if not np.any(sub):
        return None
    start_bit = int(sub[0])
    changes = np.flatnonzero(sub[1:] != sub[:-1]) + 1
    idx = np.concatenate(([0], changes, [sub.size]))
    runs = np.diff(idx)
    return f"rle1:{rw}x{rh}:{start_bit}:" + ",".join(_ma_hoa_base36(int(r)) for r in runs)


def giai_ma_mat_na_vung_rle(chuoi: str | None) -> tuple[int, int, np.ndarray] | None:
    """Giải mã chuỗi `rle1:WxH:start:runs` thành `(rw, rh, mask uint8 0/255)`."""
    if not chuoi or not isinstance(chuoi, str) or not chuoi.startswith("rle1:"):
        return None
    parts = chuoi.split(":", 3)
    if len(parts) != 4 or "x" not in parts[1]:
        return None
    try:
        rw_s, rh_s = parts[1].split("x", 1)
        rw, rh = int(rw_s), int(rh_s)
        start_bit = int(parts[2])
        if rw <= 0 or rh <= 0 or start_bit not in (0, 1):
            return None
        runs = [int(tok, 36) for tok in parts[3].split(",") if tok]
    except ValueError:
        return None
    total = rw * rh
    if sum(runs) != total:
        return None
    out = np.zeros(total, dtype=np.uint8)
    bit = start_bit
    pos = 0
    for r in runs:
        if r < 0 or pos + r > total:
            return None
        if bit == 1 and r > 0:
            out[pos : pos + r] = 255
        pos += r
        bit ^= 1
    return rw, rh, out.reshape((rh, rw))


def loc_va_thu_hep_khung_ctd(
    image_path: str,
    regions: list[DetectedRegion],
    mat_na_chu: np.ndarray | None,
    *,
    conf_toi_thieu: float = 0.28,
) -> list[DetectedRegion]:
    """Lọc khung CTD nhận nhầm nền/đồ vật (mask_cov=0, conf thấp) và thu gọn phần lề thừa quanh `mat_na_chu`."""
    if not regions:
        return []
    import cv2

    anh_gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if anh_gray is None or anh_gray.size == 0:
        return [r for r in regions if (r.confidence is None or r.confidence >= conf_toi_thieu)]
    H, W = anh_gray.shape[:2]
    has_mask = mat_na_chu is not None and mat_na_chu.shape[:2] == (H, W)

    sap_xep = sorted(regions, key=lambda r: float(r.confidence or 0.0), reverse=True)
    da_loc: list[DetectedRegion] = []
    for r in sap_xep:
        conf = float(r.confidence) if r.confidence is not None else 1.0
        if conf < conf_toi_thieu:
            continue
        x0 = max(0, int(round(r.bbox.x)))
        y0 = max(0, int(round(r.bbox.y)))
        x1 = min(W, int(round(r.bbox.x + r.bbox.w)))
        y1 = min(H, int(round(r.bbox.y + r.bbox.h)))
        bw, bh = x1 - x0, y1 - y0
        if bw < 6 or bh < 6:
            continue

        if has_mask:
            mask_roi = mat_na_chu[y0:y1, x0:x1] > 0
            mask_px = int(np.count_nonzero(mask_roi))
            mask_cov = mask_px / max(1, bw * bh)
            if mask_px == 0 and conf < 0.65:
                continue
            if mask_cov < 0.005 and conf < 0.45:
                patch = anh_gray[y0:y1, x0:x1]
                gx = cv2.Sobel(patch, cv2.CV_32F, 1, 0, ksize=3)
                gy = cv2.Sobel(patch, cv2.CV_32F, 0, 1, ksize=3)
                strong_edges = float(np.mean((np.abs(gx) + np.abs(gy)) > 160.0))
                if strong_edges < 0.02:
                    continue

            ys, xs = np.nonzero(mask_roi)
            if xs.size >= 12:
                mx0 = max(0, int(xs.min()) - 8)
                my0 = max(0, int(ys.min()) - 8)
                mx1 = min(bw, int(xs.max()) + 9)
                my1 = min(bh, int(ys.max()) + 9)
                patch_var = float(np.std(anh_gray[y0:y1, x0:x1]))
                if patch_var > 6.0:
                    def _strip_an_toan(p_strip: np.ndarray) -> bool:
                        if p_strip.size == 0:
                            return True
                        return float(np.std(p_strip)) < 24.0

                    nx0 = x0 + mx0 if mx0 > 16 and _strip_an_toan(anh_gray[y0:y1, x0 : x0 + mx0 - 2]) else x0
                    nx1 = x0 + mx1 if (bw - mx1) > 16 and _strip_an_toan(anh_gray[y0:y1, x0 + mx1 + 2 : x1]) else x1
                    ny0 = y0 + my0 if my0 > 16 and _strip_an_toan(anh_gray[y0 : y0 + my0 - 2, x0:x1]) else y0
                    ny1 = y0 + my1 if (bh - my1) > 16 and _strip_an_toan(anh_gray[y0 + my1 + 2 : y1, x0:x1]) else y1
                    if nx1 - nx0 >= 12 and ny1 - ny0 >= 12:
                        x0, y0, x1, y1 = nx0, ny0, nx1, ny1

        trung = False
        area_new = max(1, (x1 - x0) * (y1 - y0))
        for ex in da_loc:
            ex0, ey0 = ex.bbox.x, ex.bbox.y
            ex1, ey1 = ex0 + ex.bbox.w, ey0 + ex.bbox.h
            ix0, iy0 = max(x0, ex0), max(y0, ey0)
            ix1, iy1 = min(x1, ex1), min(y1, ey1)
            if ix1 <= ix0 or iy1 <= iy0:
                continue
            inter = (ix1 - ix0) * (iy1 - iy0)
            area_ex = max(1.0, ex.bbox.w * ex.bbox.h)
            iou = inter / max(1.0, area_new + area_ex - inter)
            contain_new = inter / area_new
            if iou > 0.78 or contain_new > 0.88:
                trung = True
                break
        if trung:
            continue

        da_loc.append(
            DetectedRegion(
                bbox=BBox(x=float(x0), y=float(y0), w=float(x1 - x0), h=float(y1 - y0)),
                confidence=r.confidence,
                cls=r.cls,
            )
        )

    # Phục hồi các cụm chữ nổi thật mà đầu `blk` bỏ sót nhưng đầu `seg` (`mat_na_chu`) đã phân đoạn rõ
    if has_mask:
        rem = (mat_na_chu > 0).astype(np.uint8) * 255
        for reg in da_loc:
            rx0 = max(0, int(round(reg.bbox.x)))
            ry0 = max(0, int(round(reg.bbox.y)))
            rx1 = min(W, int(round(reg.bbox.x + reg.bbox.w)))
            ry1 = min(H, int(round(reg.bbox.y + reg.bbox.h)))
            rem[ry0:ry1, rx0:rx1] = 0
        if np.any(rem):
            k_gom = cv2.getStructuringElement(cv2.MORPH_RECT, (13, 15))
            dil = cv2.dilate(rem, k_gom)
            n_cc, lbl_cc, st_cc, _ = cv2.connectedComponentsWithStats(dil)
            for idx_cc in range(1, n_cc):
                bx_c, by_c, bw_c, bh_c, area_c = (int(v) for v in st_cc[idx_cc])
                if area_c < 250 or bw_c < 10 or bh_c < 10:
                    continue
                sub_lbl = lbl_cc[by_c : by_c + bh_c, bx_c : bx_c + bw_c] == idx_cc
                sub_rem = (rem[by_c : by_c + bh_c, bx_c : bx_c + bw_c] > 0) & sub_lbl
                ys_c, xs_c = np.nonzero(sub_rem)
                if xs_c.size < 80:
                    continue
                tx0 = max(0, bx_c + int(xs_c.min()) - 5)
                ty0 = max(0, by_c + int(ys_c.min()) - 4)
                tx1 = min(W, bx_c + int(xs_c.max()) + 6)
                ty1 = min(H, by_c + int(ys_c.max()) + 5)
                tw = tx1 - tx0
                th = ty1 - ty0
                if tw < 14 or th < 14 or tw > W * 0.48 or th > H * 0.48:
                    continue
                mask_px = int(np.count_nonzero(rem[ty0:ty1, tx0:tx1]))
                mask_cov = mask_px / max(1, tw * th)
                if mask_px < 80 or mask_cov < 0.08:
                    continue
                area_cand = max(1, tw * th)
                trung_cand = False
                for ex in da_loc:
                    ex0, ey0 = ex.bbox.x, ex.bbox.y
                    ex1, ey1 = ex0 + ex.bbox.w, ey0 + ex.bbox.h
                    ix0, iy0 = max(tx0, ex0), max(ty0, ey0)
                    ix1, iy1 = min(tx1, ex1), min(ty1, ey1)
                    if ix1 <= ix0 or iy1 <= iy0:
                        continue
                    inter = (ix1 - ix0) * (iy1 - iy0)
                    area_ex = max(1.0, ex.bbox.w * ex.bbox.h)
                    iou = inter / max(1.0, area_cand + area_ex - inter)
                    if iou > 0.35 or (inter / area_cand) > 0.50:
                        trung_cand = True
                        break
                if trung_cand:
                    continue
                da_loc.append(
                    DetectedRegion(
                        bbox=BBox(x=float(tx0), y=float(ty0), w=float(tw), h=float(th)),
                        confidence=0.52,
                        cls=0,
                    )
                )

    return da_loc
