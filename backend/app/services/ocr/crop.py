"""Crop vùng chữ theo bbox đã lưu ở TextRegion (M2).

Crop sai vùng thì OCR đúng cũng vô nghĩa → quy tắc chuyển float → pixel int viết riêng ở đây
và có test biên, không rải rác trong engine.
"""
from __future__ import annotations

from PIL import Image

from app.services.interfaces import BBox


class InvalidCropBox(ValueError):
    """bbox không cắt ra được vùng ảnh hợp lệ."""


def bbox_to_pixel_box(bbox: BBox, image_w: int, image_h: int) -> tuple[int, int, int, int]:
    """(x, y, w, h) float → (left, top, right, bottom) int, clamp trong ảnh.

    Dùng `round` trên toạ độ TUYỆT ĐỐI (x, x+w) chứ không round riêng w rồi cộng —
    tránh lệch 1px tích lũy khi w có phần lẻ.
    """
    if image_w <= 0 or image_h <= 0:
        raise InvalidCropBox(f"Kích thước ảnh không hợp lệ: {image_w}x{image_h}")

    left = int(round(bbox.x))
    top = int(round(bbox.y))
    right = int(round(bbox.x + bbox.w))
    bottom = int(round(bbox.y + bbox.h))

    left = max(0, min(left, image_w))
    top = max(0, min(top, image_h))
    right = max(0, min(right, image_w))
    bottom = max(0, min(bottom, image_h))

    if right <= left or bottom <= top:
        raise InvalidCropBox(
            f"bbox không cắt ra vùng hợp lệ: {bbox} trên ảnh {image_w}x{image_h}"
        )
    return left, top, right, bottom


def crop_region(image: Image.Image, bbox: BBox) -> Image.Image:
    """Cắt đúng vùng bbox. KHÔNG nới thêm lề — giữ đúng vùng detector đã chỉ ra."""
    box = bbox_to_pixel_box(bbox, image.width, image.height)
    return image.crop(box)
