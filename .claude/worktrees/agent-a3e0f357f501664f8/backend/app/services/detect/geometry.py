"""Hình học cho bước detect: đổi format bbox, đo chồng lấp, NMS.

Tách riêng khỏi model để test được bằng số thuần, không cần chạy inference.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.interfaces import BBox


class InvalidBBox(ValueError):
    """Box không dùng được (nằm hoàn toàn ngoài ảnh, hoặc diện tích <= 0 sau khi clamp)."""


@dataclass(frozen=True)
class Detection:
    """1 box thô từ model, kèm điểm tin cậy và lớp do model gán."""

    bbox: BBox
    confidence: float
    cls: int = 0


def build_bbox(
    x1: float, y1: float, x2: float, y2: float, image_w: float, image_h: float
) -> BBox:
    """(x1,y1,x2,y2) → BBox(x,y,w,h), clamp vào trong ảnh.

    Model có thể trả tọa độ âm hoặc vượt biên ảnh → clamp, KHÔNG để lọt vào DB.
    Nếu box nằm hoàn toàn ngoài ảnh (clamp xong diện tích <= 0) → ném InvalidBBox
    để caller đếm và ghi log, không âm thầm ghi 1 box sai.
    """
    if image_w <= 0 or image_h <= 0:
        raise InvalidBBox(f"Kích thước ảnh không hợp lệ: {image_w}x{image_h}")
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1

    cx1 = min(max(x1, 0.0), image_w)
    cy1 = min(max(y1, 0.0), image_h)
    cx2 = min(max(x2, 0.0), image_w)
    cy2 = min(max(y2, 0.0), image_h)

    w, h = cx2 - cx1, cy2 - cy1
    if w <= 0 or h <= 0:
        raise InvalidBBox(
            f"Box nằm ngoài ảnh sau khi clamp: ({x1},{y1},{x2},{y2}) vs ảnh {image_w}x{image_h}"
        )
    return BBox(x=cx1, y=cy1, w=w, h=h)


def bbox_area(b: BBox) -> float:
    return max(b.w, 0.0) * max(b.h, 0.0)


def intersection_area(a: BBox, b: BBox) -> float:
    x1 = max(a.x, b.x)
    y1 = max(a.y, b.y)
    x2 = min(a.x + a.w, b.x + b.w)
    y2 = min(a.y + a.h, b.y + b.h)
    return max(x2 - x1, 0.0) * max(y2 - y1, 0.0)


def iou(a: BBox, b: BBox) -> float:
    inter = intersection_area(a, b)
    union = bbox_area(a) + bbox_area(b) - inter
    return inter / union if union > 0 else 0.0


def overlap_ratio(a: BBox, b: BBox) -> float:
    """Phần diện tích chồng lấp so với box NHỎ hơn.

    Dùng min-area (không dùng IoU) vì case cần cảnh báo là "box này gần như nằm trọn
    trong box kia" — IoU sẽ đánh giá thấp khi 2 box lệch nhau nhiều về kích thước.
    """
    smaller = min(bbox_area(a), bbox_area(b))
    if smaller <= 0:
        return 0.0
    return intersection_area(a, b) / smaller


def mark_overlap_suspects(boxes: list[BBox], threshold: float) -> list[bool]:
    """Trả cờ overlap_suspect cho từng box. Chỉ GẮN CỜ, không merge/xóa box nào."""
    flags = [False] * len(boxes)
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if overlap_ratio(boxes[i], boxes[j]) > threshold:
                flags[i] = True
                flags[j] = True
    return flags


def nms(detections: list[Detection], iou_threshold: float) -> list[Detection]:
    """Non-maximum suppression, giữ box điểm cao nhất trong cụm trùng nhau."""
    ordered = sorted(detections, key=lambda d: d.confidence, reverse=True)
    kept: list[Detection] = []
    for cand in ordered:
        if all(iou(cand.bbox, k.bbox) < iou_threshold for k in kept):
            kept.append(cand)
    return kept
