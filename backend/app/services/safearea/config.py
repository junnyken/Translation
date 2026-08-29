"""Tham số của E14. Mọi con số đều đến từ `.env`, không có magic number trong thuật toán."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SafeAreaConfig:
    roi_expand_ratio: float
    roi_expand_max_px: int
    brightness_threshold: int
    saturation_threshold: int
    morph_kernel_ratio: float
    erosion_margin_ratio: float
    erosion_margin_min_px: int
    erosion_margin_max_px: int
    min_bbox_coverage_ratio: float
    max_roi_coverage_ratio: float
    max_roi_touch_ratio: float
    max_polygon_vertices: int
    safe_area_min_pixels: int
    safe_area_min_width_px: int
    safe_area_min_height_px: int
    #: Lề của khung dự phòng — LẤY ĐÚNG `typeset_padding_ratio` của M6 để đường dự phòng cho ra
    #: kết quả y hệt M6. Dùng lề ăn-vào của E14 ở đây sẽ làm cỡ chữ đổi ở cả những vùng E14
    #: không hề nhận diện được gì: một thay đổi không ai xin và không ai giải thích được.
    fallback_padding_ratio: float

    @classmethod
    def from_settings(cls, settings) -> "SafeAreaConfig":
        return cls(
            roi_expand_ratio=settings.e14_roi_expand_ratio,
            roi_expand_max_px=settings.e14_roi_expand_max_px,
            brightness_threshold=settings.e14_brightness_threshold,
            saturation_threshold=settings.e14_saturation_threshold,
            morph_kernel_ratio=settings.e14_morph_kernel_ratio,
            erosion_margin_ratio=settings.e14_erosion_margin_ratio,
            erosion_margin_min_px=settings.e14_erosion_margin_min_px,
            erosion_margin_max_px=settings.e14_erosion_margin_max_px,
            min_bbox_coverage_ratio=settings.e14_min_bbox_coverage_ratio,
            max_roi_coverage_ratio=settings.e14_max_roi_coverage_ratio,
            max_roi_touch_ratio=settings.e14_max_roi_touch_ratio,
            max_polygon_vertices=settings.e14_max_polygon_vertices,
            safe_area_min_pixels=settings.e14_safe_area_min_pixels,
            safe_area_min_width_px=settings.e14_safe_area_min_width_px,
            safe_area_min_height_px=settings.e14_safe_area_min_height_px,
            fallback_padding_ratio=settings.typeset_padding_ratio,
        )

    def snapshot(self) -> dict:
        """Chụp lại cấu hình để về sau dựng lại đúng kết quả cũ. Không có bí mật nào ở đây."""
        return asdict(self)
