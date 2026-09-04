"""Kết quả của bộ trích hình: hình học + LÝ DO. Không có lý do thì không phải bằng chứng."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.models.enums import SafeAreaGeometryType, SafeAreaSource, SafeAreaStatus


class ReasonCode:
    """Danh sách đóng — giao diện dịch mã này ra tiếng Việt, nên không được đẻ mã tuỳ hứng."""

    SHAPE_CANDIDATE_FOUND = "shape_candidate_found"
    SHAPE_CANDIDATE_TOO_SMALL = "shape_candidate_too_small"
    SHAPE_CANDIDATE_NOT_CENTERED = "shape_candidate_not_centered"
    SHAPE_CANDIDATE_TOUCHES_ROI_BOUNDARY = "shape_candidate_touches_roi_boundary"
    SHAPE_CANDIDATE_MULTIPLE_AMBIGUOUS = "shape_candidate_multiple_ambiguous"
    SHAPE_CANDIDATE_FILLS_ROI = "shape_candidate_fills_roi"
    SHAPE_LOW_CONTRAST = "shape_low_contrast"
    SHAPE_INVALID_GEOMETRY = "shape_invalid_geometry"
    SHAPE_EROSION_ELIMINATED_AREA = "shape_erosion_eliminated_area"
    FALLBACK_NO_RELIABLE_SHAPE = "fallback_no_reliable_shape"
    #: A1 — không dựng được hình bong bóng, nhưng đã nới khung ra tới khi chạm nét vẽ.
    FALLBACK_GROWN_TO_FREE_SPACE = "fallback_grown_to_free_space"
    SAFE_AREA_SMALLER_THAN_MINIMUM = "safe_area_smaller_than_minimum"
    MANUAL_BBOX_CHANGED = "manual_bbox_changed"
    RENDER_FOOTPRINT_OUTSIDE_SAFE_AREA = "render_footprint_outside_safe_area"

    TAT_CA = frozenset({
        SHAPE_CANDIDATE_FOUND, SHAPE_CANDIDATE_TOO_SMALL, SHAPE_CANDIDATE_NOT_CENTERED,
        SHAPE_CANDIDATE_TOUCHES_ROI_BOUNDARY, SHAPE_CANDIDATE_MULTIPLE_AMBIGUOUS,
        SHAPE_CANDIDATE_FILLS_ROI, SHAPE_LOW_CONTRAST, SHAPE_INVALID_GEOMETRY,
        SHAPE_EROSION_ELIMINATED_AREA, FALLBACK_NO_RELIABLE_SHAPE,
        FALLBACK_GROWN_TO_FREE_SPACE,
        SAFE_AREA_SMALLER_THAN_MINIMUM, MANUAL_BBOX_CHANGED,
        RENDER_FOOTPRINT_OUTSIDE_SAFE_AREA,
    })


@dataclass(frozen=True)
class SafeAreaDecision:
    source: SafeAreaSource
    status: SafeAreaStatus
    geometry_type: SafeAreaGeometryType
    #: Toạ độ ẢNH GỐC. `polygon`: [[x,y], ...]; `rect`: {"x","y","w","h"}.
    geometry: dict
    roi: tuple[int, int, int, int]
    reason_codes: list[str] = field(default_factory=list)
    safe_area_pixels: int | None = None
    bbox_coverage_ratio: float | None = None

    def __post_init__(self) -> None:
        la = [m for m in self.reason_codes if m not in ReasonCode.TAT_CA]
        if la:
            raise ValueError(f"mã lý do lạ: {la}")
        if self.status is SafeAreaStatus.ready:
            # `ready` là lời khẳng định mạnh nhất hệ thống đưa ra về hình bong bóng.
            # Ràng ngay ở đây để không nơi nào dựng được một `ready` rỗng ruột.
            if self.source is not SafeAreaSource.shape_derived:
                raise ValueError("ready chỉ dành cho shape_derived")
            if not self.geometry.get("polygon"):
                raise ValueError("ready phải có đa giác")
            if not self.safe_area_pixels:
                raise ValueError("ready phải có safe_area_pixels > 0")
            if ReasonCode.SHAPE_CANDIDATE_FOUND not in self.reason_codes:
                raise ValueError("ready phải kèm shape_candidate_found")
