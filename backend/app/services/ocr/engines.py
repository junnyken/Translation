"""Engine OCR — chọn theo Project.source_lang (M3).

- `ja`      → manga-ocr (transformer, kha-white/manga-ocr-base)
- `zh`,`en` → PaddleOCR

Import thư viện OCR đều là import TRỄ, chỉ xảy ra trong worker khi thực sự nhận diện.
Tiến trình API không bao giờ nạp (có guardrail test canh).
"""
from __future__ import annotations

import logging
import re
import threading

from PIL import Image

from app.models.enums import OCREngine, SourceLang
from app.services.interfaces import BBox
from app.services.ocr.crop import crop_region

logger = logging.getLogger(__name__)

#: Ký tự "rác" thường gặp khi model đoán bừa trên vùng không có chữ.
_MEANINGFUL = re.compile(r"[0-9A-Za-z぀-ヿ㐀-鿿＀-￯À-ỹ]")


def has_meaningful_text(text: str) -> bool:
    """True nếu chuỗi có ít nhất 1 ký tự chữ/số thật (không chỉ khoảng trắng/dấu câu)."""
    return bool(_MEANINGFUL.search(text or ""))


class UnsupportedSourceLang(ValueError):
    """source_lang không nằm trong 3 giá trị đã chốt — KHÔNG fallback âm thầm sang engine khác."""


class OCREngineUnavailable(RuntimeError):
    """Thư viện/model OCR chưa cài được — báo rõ thay vì trả text rỗng giả vờ đã OCR."""


class _BaseOCREngine:
    engine_enum: OCREngine

    def __init__(self, device: str = "cpu") -> None:
        self.device = device
        self._model = None
        self._lock = threading.Lock()

    def _load(self):  # pragma: no cover - override
        raise NotImplementedError

    def _get_model(self):
        """Nạp model 1 lần/process (cold-start lặp lại sẽ giết hiệu năng)."""
        if self._model is None:
            with self._lock:
                if self._model is None:
                    self._model = self._load()
        return self._model

    def recognize(self, image_path: str, bbox: BBox) -> tuple[str, float | None]:  # pragma: no cover
        raise NotImplementedError


class MangaOCREngine(_BaseOCREngine):
    """source_lang == 'ja'.

    manga-ocr KHÔNG trả confidence (đã kiểm source 0.1.16: `__call__` chỉ trả chuỗi text).
    → confidence = None. Không bịa số. Tiêu chí `needs_manual` dựa vào text rỗng/không có
    ký tự có nghĩa. Xem docs/ARCH.md § OCR.
    """

    engine_enum = OCREngine.manga_ocr

    def _load(self):
        try:
            from manga_ocr import MangaOcr
        except ImportError as exc:  # pragma: no cover - phụ thuộc môi trường
            raise OCREngineUnavailable(f"Chưa cài manga-ocr: {exc}") from exc
        logger.info("Nạp manga-ocr (device=%s)", self.device)
        return MangaOcr(force_cpu=self.device == "cpu")

    def recognize(self, image_path: str, bbox: BBox) -> tuple[str, float | None]:
        with Image.open(image_path) as im:
            crop = crop_region(im.convert("RGB"), bbox)
        text = self._get_model()(crop)
        return (text or "").strip(), None


class PaddleOCREngine(_BaseOCREngine):
    """source_lang in ('zh', 'en'). PaddleOCR trả confidence thật theo từng dòng."""

    engine_enum = OCREngine.paddle_ocr

    def __init__(self, lang: str, device: str = "cpu", enable_mkldnn: bool = False) -> None:
        super().__init__(device=device)
        self.lang = lang
        #: paddlepaddle 3.3.1 ném NotImplementedError ở nhánh oneDNN trên CPU này
        #: -> mặc định TẮT. Bằng chứng + cách tái hiện: docs/TEST_LOG.md § M3.
        self.enable_mkldnn = enable_mkldnn

    def build_kwargs(self) -> dict:
        return {
            "lang": self.lang,
            "device": self.device,
            "use_textline_orientation": True,
            "enable_mkldnn": self.enable_mkldnn,
            # Đầu vào của ta là 1 crop bubble, KHÔNG phải trang tài liệu. Bộ phân loại hướng
            # trang không có gì để dựa vào nên đoán bừa và xoay crop 180° -> thứ tự dòng đảo
            # ngược ("OUT!/LOOK" thay vì "LOOK/OUT!"). Đo thật, xem docs/TEST_LOG.md § M3.
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
        }

    def _load(self):
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:  # pragma: no cover - phụ thuộc môi trường
            raise OCREngineUnavailable(f"Chưa cài paddleocr: {exc}") from exc
        kwargs = self.build_kwargs()
        logger.info("Nạp PaddleOCR %s", kwargs)
        return PaddleOCR(**kwargs)

    @staticmethod
    def _parse(result) -> tuple[str, float | None]:
        """Gom các dòng của 1 vùng crop thành 1 chuỗi + confidence trung bình.

        PaddleOCR đổi format output giữa các phiên bản (list lồng cũ vs dict mới) nên đọc cả 2
        dạng thay vì bám 1 dạng rồi vỡ khi nâng version.

        Thứ tự dòng trong output KHÔNG đảm bảo theo vị trí (đo thật: 1 bubble 2 dòng trả về
        đảo ngược) → sắp lại theo toạ độ trên→dưới, trái→phải. Chỉ sắp thứ tự dòng,
        TUYỆT ĐỐI không sửa ký tự nào trong text (việc sửa lỗi OCR là của bước dịch M5).
        """
        lines: list[tuple[float, float, str, float | None]] = []

        def _take(text, score, poly=None):
            if text is None:
                return
            y, x = 0.0, 0.0
            if poly is not None:
                pts = [(float(px), float(py)) for px, py in (list(pt) for pt in poly)]
                if pts:
                    y = min(py for _, py in pts)
                    x = min(px for px, _ in pts)
            lines.append((y, x, str(text), float(score) if score is not None else None))

        if not result:
            return "", None

        for page in result:
            if isinstance(page, dict):  # PaddleOCR >= 3.x
                texts = page.get("rec_texts") or []
                scores = page.get("rec_scores") or [None] * len(texts)
                polys = page.get("rec_polys")
                if polys is None:
                    polys = page.get("dt_polys")
                if polys is None:
                    polys = [None] * len(texts)
                for text, score, poly in zip(texts, scores, polys, strict=False):
                    _take(text, score, poly)
                continue
            for line in page or []:  # PaddleOCR 2.x: [[bbox, (text, score)], ...]
                if isinstance(line, (list, tuple)) and len(line) >= 2:
                    poly, payload = line[0], line[1]
                    if isinstance(payload, (list, tuple)) and len(payload) >= 2:
                        _take(payload[0], payload[1], poly)
                    else:
                        _take(payload, None, poly)

        lines.sort(key=lambda item: (item[0], item[1]))
        texts = [t for _, _, t, _ in lines if t]
        scores = [sc for _, _, _, sc in lines if sc is not None]
        confidence = sum(scores) / len(scores) if scores else None
        return "\n".join(texts).strip(), confidence

    def recognize(self, image_path: str, bbox: BBox) -> tuple[str, float | None]:
        import numpy as np

        with Image.open(image_path) as im:
            crop = crop_region(im.convert("RGB"), bbox)
        model = self._get_model()
        predict = getattr(model, "predict", None) or model.ocr
        result = predict(np.asarray(crop))
        return self._parse(result)


def get_ocr_engine(
    source_lang: str | SourceLang, device: str = "cpu", paddle_enable_mkldnn: bool = False
) -> _BaseOCREngine:
    """Factory theo source_lang. Giá trị lạ → raise rõ ràng, không fallback âm thầm."""
    value = source_lang.value if isinstance(source_lang, SourceLang) else str(source_lang)
    if value == SourceLang.ja.value:
        return MangaOCREngine(device=device)
    if value in (SourceLang.zh.value, SourceLang.en.value):
        return PaddleOCREngine(
            lang="ch" if value == "zh" else "en",
            device=device,
            enable_mkldnn=paddle_enable_mkldnn,
        )
    raise UnsupportedSourceLang(
        f"source_lang '{value}' không được hỗ trợ ở M3 (chỉ ja/zh/en)"
    )
