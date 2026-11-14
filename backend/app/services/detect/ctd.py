"""CTDDetector — chạy comic-text-detector qua ONNX Runtime.

Chỉ GỌI model weight qua onnxruntime; không copy code inference của repo gốc (giữ đúng
guardrail "không nhúng code GPL" của M1). Tiền/hậu xử lý (letterbox, giải mã YOLO, NMS)
viết lại từ đầu trong file này và trong `geometry.py`.

Nguồn weight + license: xem docs/ARCH.md § Model weight.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, replace
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


def _la_hoa_tiet_hinh_hoc_don(
    sub_mask: np.ndarray,
    sub_gray: np.ndarray,
    tw: int,
    th: int,
    scov: float,
) -> bool:
    """Nhận diện họa tiết/biểu tượng đơn giản (khuy áo, viền tam giác `◁ ▷`) thay vì chữ nhiều nét."""
    import cv2
    import math

    check_dark_ornament = tw <= 78 and th <= 78 and scov < 0.28 and float((sub_gray >= 225).mean()) < 0.45
    check_border_poly = min(tw, th) <= 56 and max(tw, th) <= 120 and scov < 0.26
    if not (check_dark_ornament or check_border_poly):
        return False

    contours, hierarchy = cv2.findContours(sub_mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if not contours or hierarchy is None:
        return False

    hier = hierarchy[0]
    holes_by_parent: dict[int, int] = {}
    for _, hinfo in enumerate(hier):
        parent_i = int(hinfo[3])
        if parent_i >= 0:
            holes_by_parent[parent_i] = holes_by_parent.get(parent_i, 0) + 1

    n_outer_18 = 0
    max_holes_18 = 0
    toan_hinh_don_18 = True

    n_outer_12 = 0
    toan_da_giac_nho = True

    for ci, hinfo in enumerate(hier):
        if int(hinfo[3]) >= 0:
            continue
        cnt = contours[ci]
        area_cnt = float(cv2.contourArea(cnt))
        if area_cnt < 12.0:
            continue
        peri = float(cv2.arcLength(cnt, True))
        n_holes = holes_by_parent.get(ci, 0)

        n_outer_12 += 1
        verts8 = len(cv2.approxPolyDP(cnt, 0.08 * peri, True)) if peri > 0 else 99
        if area_cnt >= 180.0 or verts8 > 4 or n_holes > 2:
            toan_da_giac_nho = False

        if area_cnt >= 18.0:
            n_outer_18 += 1
            if n_holes > max_holes_18:
                max_holes_18 = n_holes
            circ = (4.0 * math.pi * area_cnt / (peri * peri)) if peri > 0 else 0.0
            verts6 = len(cv2.approxPolyDP(cnt, 0.06 * peri, True)) if peri > 0 else 99
            if n_holes > 1 or (circ < 0.42 and verts6 > 7):
                toan_hinh_don_18 = False

    if check_dark_ornament and 0 < n_outer_18 <= 3 and max_holes_18 <= 1 and toan_hinh_don_18:
        return True
    if check_border_poly and n_outer_12 > 0 and toan_da_giac_nho:
        return True
    return False


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

    # Bắt nét chữ thò nhẹ ngoài mép khung (<= 12px) và lọc nhiễu nét vẽ khuôn mặt khỏi `mat_na_chu`
    # TRƯỚC bước phục hồi `rem` để nét cuối chữ thò nhẹ (như chữ `'S`) được gộp vào khung mẹ
    # thay vì tách thành hộp mồ côi riêng lẻ cản trở khung mẹ.
    if has_mask and mat_na_chu is not None:
        da_loc = lam_sach_mat_na_chu_tren_tranh(anh_gray, mat_na_chu, da_loc)

    # Phục hồi các cụm chữ nổi thật mà đầu `blk` bỏ sót nhưng đầu `seg` (`mat_na_chu`) đã phân đoạn rõ
    so_truoc_rem = len(da_loc)
    if has_mask:
        rem = (mat_na_chu > 0).astype(np.uint8) * 255
        for reg in da_loc:
            rx0 = max(0, int(round(reg.bbox.x)))
            ry0 = max(0, int(round(reg.bbox.y)))
            rx1 = min(W, int(round(reg.bbox.x + reg.bbox.w)))
            ry1 = min(H, int(round(reg.bbox.y + reg.bbox.h)))
            rem[ry0:ry1, rx0:rx1] = 0
        if np.any(rem):
            def _thu_nap_vung_rem(tx0: int, ty0: int, tx1: int, ty1: int, mask_px: int) -> None:
                tw = tx1 - tx0
                th = ty1 - ty0
                if tw < 14 or th < 14 or tw > W * 0.48 or th > H * 0.48:
                    return
                area_cand = max(1, tw * th)
                if mask_px < 45 or (mask_px / area_cand) < 0.08:
                    return
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
                        return
                da_loc.append(
                    DetectedRegion(
                        bbox=BBox(x=float(tx0), y=float(ty0), w=float(tw), h=float(th)),
                        confidence=0.52,
                        cls=0,
                    )
                )

            # Tách bóng thoại trắng khép kín có rem bên trong trước khi dilate k_gom,
            # tránh nhập chung bóng nhỏ (`Uma...?`) với SFX trôi bên trên/bên cạnh (`p1 #11`).
            white_bg = (anh_gray >= 230).astype(np.uint8)
            nw_b, lbl_wb, st_wb, _ = cv2.connectedComponentsWithStats(white_bg, connectivity=4)
            k3_ring = np.ones((3, 3), np.uint8)
            max_wb_w, max_wb_h = int(W * 0.42), int(H * 0.42)
            for wbid in range(1, nw_b):
                wb_x, wb_y, wb_w, wb_h, wb_area = (int(v) for v in st_wb[wbid])
                if (
                    wb_area < 450
                    or wb_w < 14
                    or wb_h < 14
                    or wb_w > max_wb_w
                    or wb_h > max_wb_h
                    or wb_x <= 1
                    or wb_y <= 1
                    or wb_x + wb_w >= W - 1
                    or wb_y + wb_h >= H - 1
                ):
                    continue
                rx_0, ry_0 = max(0, wb_x - 2), max(0, wb_y - 2)
                rx_1, ry_1 = min(W, wb_x + wb_w + 2), min(H, wb_y + wb_h + 2)
                comp_wb = lbl_wb[ry_0:ry_1, rx_0:rx_1] == wbid
                rem_roi = rem[ry_0:ry_1, rx_0:rx_1]
                seg_in = (rem_roi > 0) & comp_wb
                px_in = int(np.count_nonzero(seg_in))
                # Loại halo trắng ôm sát chữ trên nền tóc/tối (`px_in / wb_area` > 0.58)
                # để không xé nhỏ từng dòng trong một bóng thoại tối thành nhiều hộp đè nhau.
                if px_in < 45 or (px_in / max(1, wb_area)) > 0.58:
                    continue
                ring_wb = (cv2.dilate(comp_wb.astype(np.uint8), k3_ring) > 0) & (~comp_wb)
                if not np.any(ring_wb):
                    continue
                if float((anh_gray[ry_0:ry_1, rx_0:rx_1][ring_wb] <= 170).mean()) < 0.50:
                    continue
                ys_b, xs_b = np.nonzero(seg_in)
                b_tx0 = max(rx_0, rx_0 + int(xs_b.min()) - 5)
                b_ty0 = max(ry_0, ry_0 + int(ys_b.min()) - 4)
                b_tx1 = min(rx_1, rx_0 + int(xs_b.max()) + 6)
                b_ty1 = min(ry_1, ry_0 + int(ys_b.max()) + 5)
                _thu_nap_vung_rem(b_tx0, b_ty0, b_tx1, b_ty1, px_in)
                rem[ry_0:ry_1, rx_0:rx_1][comp_wb] = 0

        if np.any(rem):
            k_gom = cv2.getStructuringElement(cv2.MORPH_RECT, (13, 15))
            dil = cv2.dilate(rem, k_gom)
            # Chặn dil (k_gom) nối vọt qua biên panel + rãnh trắng panel (`p1 #3`)
            min_line = min(45, max(28, int(min(H, W) * 0.04)))
            h_line = cv2.morphologyEx(
                (anh_gray <= 120).astype(np.uint8), cv2.MORPH_OPEN, np.ones((1, min_line), np.uint8)
            ) > 0
            v_line = cv2.morphologyEx(
                (anh_gray <= 120).astype(np.uint8), cv2.MORPH_OPEN, np.ones((min_line, 1), np.uint8)
            ) > 0
            clean_w_no_rem = ((anh_gray >= 238) & (rem == 0)).astype(np.uint8)
            h_white = cv2.morphologyEx(clean_w_no_rem, cv2.MORPH_OPEN, np.ones((1, min_line), np.uint8)) > 0
            v_white = cv2.morphologyEx(clean_w_no_rem, cv2.MORPH_OPEN, np.ones((min_line, 1), np.uint8)) > 0
            near_h_line = cv2.dilate(h_line.astype(np.uint8), np.ones((17, 1), np.uint8)) > 0
            near_v_line = cv2.dilate(v_line.astype(np.uint8), np.ones((1, 17), np.uint8)) > 0
            gutter_cut = (h_white & near_h_line) | (v_white & near_v_line) | ((h_line | v_line) & (rem == 0))
            clean_w_broad = ((anh_gray >= 244) & (rem == 0)).astype(np.uint8)
            borderless_h = cv2.morphologyEx(
                clean_w_broad, cv2.MORPH_OPEN, np.ones((6, max(120, W // 6)), np.uint8)
            ) > 0
            borderless_v = cv2.morphologyEx(
                clean_w_broad, cv2.MORPH_OPEN, np.ones((max(120, H // 6), 6), np.uint8)
            ) > 0
            dil[gutter_cut | borderless_h | borderless_v] = 0

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
                mask_px = int(np.count_nonzero(rem[ty0:ty1, tx0:tx1]))
                if mask_px < 80:
                    continue
                _thu_nap_vung_rem(tx0, ty0, tx1, ty1, mask_px)

    if has_mask and mat_na_chu is not None and len(da_loc) > so_truoc_rem:
        da_loc = lam_sach_mat_na_chu_tren_tranh(anh_gray, mat_na_chu, da_loc)
        # Hậu kiểm sau lọc nét vẽ: loại bỏ các vùng fallback `rem` bị tụt phủ (`scov < 0.085`)
        # hoặc chỉ còn hình học đơn giản trên nền tranh/áo choàng (`p5` khuy áo, `p4` tam giác viền).
        da_loc_sau: list[DetectedRegion] = list(da_loc[:so_truoc_rem])
        for reg in da_loc[so_truoc_rem:]:
            rx0 = max(0, int(round(reg.bbox.x)))
            ry0 = max(0, int(round(reg.bbox.y)))
            rx1 = min(W, int(round(reg.bbox.x + reg.bbox.w)))
            ry1 = min(H, int(round(reg.bbox.y + reg.bbox.h)))
            if rx1 <= rx0 or ry1 <= ry0:
                continue
            sub_mask = (mat_na_chu[ry0:ry1, rx0:rx1] > 0).astype(np.uint8)
            clean_px = int(np.count_nonzero(sub_mask))
            tw = rx1 - rx0
            th = ry1 - ry0
            scov = clean_px / max(1, tw * th)
            if clean_px < 75 or scov < 0.085:
                continue
            if _la_hoa_tiet_hinh_hoc_don(sub_mask, anh_gray[ry0:ry1, rx0:rx1], tw, th, scov):
                continue
            da_loc_sau.append(reg)
        da_loc = da_loc_sau

    return da_loc


def lam_sach_mat_na_chu_tren_tranh(
    anh_gray: np.ndarray,
    mat_na_chu: np.ndarray,
    regions: list[DetectedRegion],
) -> list[DetectedRegion]:
    """Bắt nét chữ thò nhẹ ngoài mép khung (<= 12px) và lọc nhiễu nét vẽ khuôn mặt khỏi `mat_na_chu`."""
    if not regions or mat_na_chu is None or mat_na_chu.shape[:2] != anh_gray.shape[:2]:
        return regions
    import cv2
    from app.services.inpaint.mat_na_net import loc_nhieu_net_ve_khoi_seg_crop

    H, W = anh_gray.shape[:2]
    max_pad = 12

    # Tạo mặt nạ sở hữu vùng khác để nới rộng không ăn nhầm sang khung lân cận:
    boxes = [
        (
            max(0, int(round(r.bbox.x))),
            max(0, int(round(r.bbox.y))),
            min(W, int(round(r.bbox.x + r.bbox.w))),
            min(H, int(round(r.bbox.y + r.bbox.h))),
        )
        for r in regions
    ]

    out_regions: list[DetectedRegion] = []
    for idx, r in enumerate(regions):
        x0, y0, x1, y1 = boxes[idx]
        if x1 <= x0 or y1 <= y0:
            out_regions.append(r)
            continue

        px0, py0 = max(0, x0 - max_pad), max(0, y0 - max_pad)
        px1, py1 = min(W, x1 + max_pad), min(H, y1 + max_pad)
        seg_pad = (mat_na_chu[py0:py1, px0:px1] > 0).astype(np.uint8) * 255
        if np.count_nonzero(seg_pad) == 0:
            out_regions.append(r)
            continue

        seg_pad_clean = loc_nhieu_net_ve_khoi_seg_crop(
            anh_gray[py0:py1, px0:px1], seg_pad, img_hw=(H, W)
        )
        other_mask = np.zeros((py1 - py0, px1 - px0), dtype=bool)
        for j, (ox0, oy0, ox1, oy1) in enumerate(boxes):
            if j == idx or ox1 <= px0 or ox0 >= px1 or oy1 <= py0 or oy0 >= py1:
                continue
            other_mask[
                max(0, oy0 - py0) : min(py1 - py0, oy1 - py0),
                max(0, ox0 - px0) : min(px1 - px0, ox1 - px0),
            ] = True

        # Bước 1A: Giữ mọi thành phần `seg` sạch chạm vào phần ruột khung hiện tại (kèm cầu nối 3px ở mép cắt)
        bx0, by0 = x0 - px0, y0 - py0
        bx1, by1 = x1 - px0, y1 - py0
        seed_box = np.zeros_like(seg_pad_clean, dtype=bool)
        seed_box[max(0, by0 - 2) : min(py1 - py0, by1 + 2), max(0, bx0 - 2) : min(px1 - px0, bx1 + 2)] = True
        in_core_only = np.zeros_like(seg_pad_clean, dtype=bool)
        in_core_only[by0:by1, bx0:bx1] = True

        # Chỉ bắt phần thò ra gần mép có sẵn chữ:
        if np.any((seg_pad_clean > 0) & in_core_only):
            # Gắn 1 cầu nối 3x3 cho chữ đứt nét ngay mép <= 12px
            merged = cv2.dilate((seg_pad_clean > 0).astype(np.uint8), np.ones((3, 3), np.uint8), iterations=1)
            nl_c, lbl_c, st_c, _ = cv2.connectedComponentsWithStats(merged, connectivity=8)
            nx0, ny0, nx1, ny1 = x0, y0, x1, y1
            for cid in range(1, nl_c):
                comp = (lbl_c == cid) & (seg_pad_clean > 0)
                if not np.any(comp & in_core_only):
                    continue
                if np.any(comp & other_mask):
                    # Vẫn giữ phần thuộc chính khung nếu chạm nhẹ, không mở rộng sang khung khác
                    comp = comp & (~other_mask)
                ys_c, xs_c = np.where(comp)
                if ys_c.size == 0:
                    continue
                # Chỉ cho phép nới ở cạnh thực sự có nét chữ chạm sát mép trong khung
                cx_min = px0 + int(xs_c.min())
                cy_min = py0 + int(ys_c.min())
                cx_max = px0 + int(xs_c.max()) + 1
                cy_max = py0 + int(ys_c.max()) + 1
                nx0 = min(nx0, cx_min)
                ny0 = min(ny0, cy_min)
                nx1 = max(nx1, cx_max)
                ny1 = max(ny1, cy_max)
            if nx0 != x0 or ny0 != y0 or nx1 != x1 or ny1 != y1:
                boxes[idx] = (nx0, ny0, nx1, ny1)
                r = replace(
                    r,
                    bbox=BBox(
                        x=float(nx0),
                        y=float(ny0),
                        w=float(nx1 - nx0),
                        h=float(ny1 - ny0),
                    ),
                )
        out_regions.append(r)

    # Bước 1B: Ghi kết quả `seg` đã lọc nhiễu nét vẽ khuôn mặt trở lại `mat_na_chu` (không đè lên khung khác):
    for idx, (x0, y0, x1, y1) in enumerate(boxes):
        if x1 <= x0 or y1 <= y0:
            continue
        cleaned = loc_nhieu_net_ve_khoi_seg_crop(
            anh_gray[y0:y1, x0:x1], mat_na_chu[y0:y1, x0:x1], img_hw=(H, W)
        )
        protect_other = np.zeros((y1 - y0, x1 - x0), dtype=bool)
        for j, (ox0, oy0, ox1, oy1) in enumerate(boxes):
            if j == idx or ox1 <= x0 or ox0 >= x1 or oy1 <= y0 or oy0 >= y1:
                continue
            protect_other[
                max(0, oy0 - y0) : min(y1 - y0, oy1 - y0),
                max(0, ox0 - x0) : min(x1 - x0, ox1 - x0),
            ] = True
        cur = mat_na_chu[y0:y1, x0:x1]
        mat_na_chu[y0:y1, x0:x1] = np.where(protect_other, cur, cleaned)

    return out_regions
