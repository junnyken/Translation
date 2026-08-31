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
    confidence: float
    cls: int


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
    def detect_regions(self, image_path: str) -> list[DetectedRegion]:
        """Chạy inference, trả list box + confidence (đã NMS, CHƯA lọc theo conf_threshold)."""
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(f"Không thấy ảnh tại '{image_path}'")

        with Image.open(path) as im:
            image = im.convert("RGB")
            img_w, img_h = image.size
            tensor, scale, pad_x, pad_y = self._letterbox(image)

        session = self._get_session()
        input_name = session.get_inputs()[0].name
        outputs = session.run(None, {input_name: tensor})
        blk = outputs[0]  # 'blk': [1, N, 4+1+num_classes]

        detections = self._decode(blk, scale, pad_x, pad_y, img_w, img_h)
        return [DetectedRegion(bbox=d.bbox, confidence=d.confidence, cls=d.cls) for d in detections]

    def detect(self, image_path: str) -> list[BBox]:
        """Đúng signature Protocol `IDetector` đã chốt ở M1."""
        return [r.bbox for r in self.detect_regions(image_path)]
