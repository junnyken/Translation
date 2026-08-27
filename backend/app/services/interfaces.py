"""Interface trừu tượng cho 5 bước pipeline AI.

M1 CHỈ định nghĩa contract — không có logic model thật ở đây.
Implementation thật: M2 (detect), M3 (OCR), M4 (inpaint), M5 (translate), M6 (typeset).
Mọi class implement sau này phải giữ NGUYÊN tên method dưới đây.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class BBox:
    """Bounding box theo pixel, gốc tọa độ là góc trên-trái của ảnh."""

    x: float
    y: float
    w: float
    h: float


@runtime_checkable
class IDetector(Protocol):
    def detect(self, image_path: str) -> list[BBox]:
        """Trả list bbox phát hiện được. Implement ở M2 (comic-text-detector)."""
        ...


@runtime_checkable
class IOCREngine(Protocol):
    def recognize(self, image_path: str, bbox: BBox) -> tuple[str, float]:
        """Trả (raw_text, confidence). Implement ở M3 (manga-ocr / PaddleOCR)."""
        ...


@runtime_checkable
class IInpainter(Protocol):
    def inpaint(self, image_path: str, masks: list[BBox]) -> str:
        """Trả đường dẫn ảnh clean. Implement ở M4 (LaMa)."""
        ...


@runtime_checkable
class ITranslator(Protocol):
    def translate(self, texts: list[str], source_lang: str, target_lang: str) -> list[str]:
        """Trả list bản dịch theo ĐÚNG thứ tự input. Implement ở M5."""
        ...


@runtime_checkable
class ITypesetter(Protocol):
    def fit(self, text: str, bbox: BBox, font_family: str) -> dict:
        """Trả {font_size, wrapped_text, fit_status}. Implement ở M6."""
        ...


class NotImplementedEngine:
    """Base cho các engine chưa có implementation — fail to lớn, không trả kết quả giả."""

    mini_spec: str = "?"

    def _not_yet(self, method: str):
        raise NotImplementedError(
            f"{type(self).__name__}.{method} chưa được implement (thuộc phạm vi {self.mini_spec})"
        )


class UnimplementedDetector(NotImplementedEngine):
    mini_spec = "M2"

    def detect(self, image_path: str) -> list[BBox]:
        self._not_yet("detect")


class UnimplementedOCREngine(NotImplementedEngine):
    mini_spec = "M3"

    def recognize(self, image_path: str, bbox: BBox) -> tuple[str, float]:
        self._not_yet("recognize")


class UnimplementedInpainter(NotImplementedEngine):
    mini_spec = "M4"

    def inpaint(self, image_path: str, masks: list[BBox]) -> str:
        self._not_yet("inpaint")


class UnimplementedTranslator(NotImplementedEngine):
    mini_spec = "M5"

    def translate(self, texts: list[str], source_lang: str, target_lang: str) -> list[str]:
        self._not_yet("translate")


class UnimplementedTypesetter(NotImplementedEngine):
    mini_spec = "M6"

    def fit(self, text: str, bbox: BBox, font_family: str) -> dict:
        self._not_yet("fit")
