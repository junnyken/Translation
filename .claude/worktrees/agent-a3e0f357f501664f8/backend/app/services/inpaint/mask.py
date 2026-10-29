"""Dựng mask inpaint từ bbox của TextRegion (M2).

Tách riêng khỏi model để test bằng số thuần, không cần chạy inference.
"""
from __future__ import annotations

import numpy as np

from app.services.interfaces import BBox

#: Trần cứng theo spec M4: không nới quá 15% kích thước box (nới quá sẽ ăn vào tranh).
MAX_DILATE_RATIO = 0.15


class InvalidMask(ValueError):
    """Không dựng được mask hợp lệ."""


def dilate_bbox(bbox: BBox, image_w: int, image_h: int, ratio: float) -> BBox:
    """Nới bbox thêm `ratio` × kích thước box (chia đều 2 bên), rồi clamp trong ảnh.

    ratio = 0.10 nghĩa là chiều rộng nới thêm tổng cộng 10% (mỗi bên 5%).
    ratio bị chặn trên bởi MAX_DILATE_RATIO — truyền cao hơn sẽ bị kẹp xuống, không im lặng nới bừa.
    """
    if ratio < 0:
        raise InvalidMask(f"dilate ratio âm: {ratio}")
    effective = min(ratio, MAX_DILATE_RATIO)

    dx = bbox.w * effective / 2.0
    dy = bbox.h * effective / 2.0

    x1 = max(0.0, bbox.x - dx)
    y1 = max(0.0, bbox.y - dy)
    x2 = min(float(image_w), bbox.x + bbox.w + dx)
    y2 = min(float(image_h), bbox.y + bbox.h + dy)

    if x2 <= x1 or y2 <= y1:
        raise InvalidMask(f"bbox nới xong không còn vùng hợp lệ: {bbox} trên ảnh {image_w}x{image_h}")
    return BBox(x=x1, y=y1, w=x2 - x1, h=y2 - y1)


def dilate_bboxes(bboxes: list[BBox], image_w: int, image_h: int, ratio: float) -> list[BBox]:
    return [dilate_bbox(b, image_w, image_h, ratio) for b in bboxes]


def build_mask(
    image_w: int, image_h: int, bboxes: list[BBox], ratio: float = 0.0
) -> np.ndarray:
    """Mask nhị phân cùng kích thước ảnh gốc: 1 = vùng cần xoá chữ, 0 = giữ nguyên.

    LaMa yêu cầu mask cùng kích thước ảnh (đã kiểm thật, xem docs/TEST_LOG.md § M4).
    """
    if image_w <= 0 or image_h <= 0:
        raise InvalidMask(f"Kích thước ảnh không hợp lệ: {image_w}x{image_h}")

    mask = np.zeros((image_h, image_w), dtype=np.float32)
    for bbox in dilate_bboxes(bboxes, image_w, image_h, ratio):
        x1 = int(np.floor(bbox.x))
        y1 = int(np.floor(bbox.y))
        x2 = int(np.ceil(bbox.x + bbox.w))
        y2 = int(np.ceil(bbox.y + bbox.h))
        # clamp lần nữa sau khi làm tròn ra ngoài
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(image_w, x2), min(image_h, y2)
        if x2 > x1 and y2 > y1:
            mask[y1:y2, x1:x2] = 1.0
    return mask


def mask_coverage(mask: np.ndarray) -> float:
    """Tỷ lệ diện tích ảnh bị mask — dùng để cảnh báo mask nuốt gần hết trang."""
    return float(mask.mean()) if mask.size else 0.0
