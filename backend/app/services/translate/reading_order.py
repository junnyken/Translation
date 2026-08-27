"""Thứ tự đọc của các vùng chữ trong 1 trang truyện.

Không dùng thứ tự bbox thô: manga Nhật đọc **phải → trái**, còn EN/CN đọc trái → phải.
Sai thứ tự ở đây làm hỏng cả mạch văn khi gộp cả trang gửi cho LLM (M5) và làm lệch
khi ghép bản dịch trở lại từng vùng.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.services.interfaces import BBox

Direction = Literal["ltr", "rtl"]

#: Hướng đọc mặc định theo ngôn ngữ nguồn — cấu hình được, không hard-code 1 hướng.
DEFAULT_DIRECTION: dict[str, Direction] = {
    "ja": "rtl",  # manga Nhật: phải sang trái
    "zh": "ltr",
    "en": "ltr",
}


class UnknownReadingDirection(ValueError):
    pass


def direction_for(source_lang: str, override: str | None = None) -> Direction:
    if override:
        value = override.strip().lower()
        if value not in ("ltr", "rtl"):
            raise UnknownReadingDirection(f"Hướng đọc '{override}' không hợp lệ (chỉ ltr/rtl)")
        return value  # type: ignore[return-value]
    return DEFAULT_DIRECTION.get(source_lang, "ltr")


@dataclass(frozen=True)
class OrderedItem:
    """1 vùng chữ kèm khoá của nó (id region) để ghép ngược lại sau khi dịch."""

    key: Any
    bbox: BBox


def _band_key(bbox: BBox, band_height: float) -> int:
    """Gom các bbox nằm cùng một 'hàng' (dải ngang) lại với nhau.

    Bubble hiếm khi thẳng hàng tuyệt đối nên không so y tuyệt đối mà chia theo dải.
    """
    return int(bbox.y // band_height) if band_height > 0 else 0


def order_items(
    items: list[OrderedItem], direction: Direction = "ltr", band_ratio: float = 0.6
) -> list[OrderedItem]:
    """Sắp các vùng theo thứ tự đọc: theo dải ngang từ trên xuống, trong dải theo hướng đọc.

    `band_ratio`: chiều cao dải = trung vị chiều cao bbox × band_ratio. Cùng dải nghĩa là
    "cùng một hàng bong bóng" dù lệch nhau vài chục pixel.
    """
    if not items:
        return []

    heights = sorted(i.bbox.h for i in items)
    median_h = heights[len(heights) // 2]
    band_height = max(median_h * band_ratio, 1.0)

    reverse_x = direction == "rtl"
    return sorted(
        items,
        key=lambda it: (
            _band_key(it.bbox, band_height),
            -(it.bbox.x + it.bbox.w) if reverse_x else it.bbox.x,
            it.bbox.y,
        ),
    )


def calculate_reading_order(
    regions: list[Any], source_lang: str, override: str | None = None
) -> list[Any]:
    """Nhận list TextRegion (hoặc object có bbox_x/y/w/h), trả list ĐÃ SẮP theo thứ tự đọc."""
    direction = direction_for(source_lang, override)
    items = [
        OrderedItem(key=r, bbox=BBox(x=r.bbox_x, y=r.bbox_y, w=r.bbox_w, h=r.bbox_h))
        for r in regions
    ]
    return [it.key for it in order_items(items, direction)]
