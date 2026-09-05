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
    #: A2 — cắt khung về trong lòng bong bóng. Xem `long_bong_bong.py`.
    #:
    #: **Mặc định TẮT.** Đây là thay đổi hình học, tức đổi thứ người dùng nhìn thấy, và cả ba
    #: ảnh đã đo được đều là ảnh DỰNG — chưa có trang manga in thật có lưới chấm (screentone),
    #: thứ có thể làm mặt nạ mực vỡ vụn. Bật khi đã đo trên trang thật, theo ba con số ở
    #: `docs/PLAN_A2_CAT_KHUNG_VE_TRONG_BONG_BONG.md` §7.
    cat_ve_bong_bong_enabled: bool = False
    #: Vùng tô loang lớn hơn ngần này so với ROI ⇒ coi là đã rò ra nền vẽ. Đo trên
    #: `test_fixtures/`: trong bong bóng 4-6% trang, rò ra 75-82% — chọn ngưỡng ở giữa.
    cat_tran_ti_le_roi: float = 0.60
    #: Và lớn hơn ngần này lần diện tích bbox chữ ⇒ nhiều khả năng đã rò sang panel bên cạnh.
    cat_tran_boi_bbox: float = 40.0

    #: A1 — nới khung dự phòng ra chỗ trống. Xem `grow.py`.
    grow_enabled: bool = True
    grow_max_ratio: float = 1.5
    grow_max_px: int = 400
    grow_step_px: int = 2
    #: Nới mà diện tích không hơn được ngần này thì coi như không nới — đổi hình học vì vài
    #: pixel chỉ làm bố cục nhảy lung tung giữa các lần chạy mà chẳng ai được lợi.
    grow_min_gain_ratio: float = 0.15

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
            grow_enabled=settings.e14_grow_enabled,
            grow_max_ratio=settings.e14_grow_max_ratio,
            grow_max_px=settings.e14_grow_max_px,
            grow_step_px=settings.e14_grow_step_px,
            grow_min_gain_ratio=settings.e14_grow_min_gain_ratio,
            cat_ve_bong_bong_enabled=settings.a2_cat_ve_bong_bong_enabled,
            cat_tran_ti_le_roi=settings.a2_cat_tran_ti_le_roi,
            cat_tran_boi_bbox=settings.a2_cat_tran_boi_bbox,
        )

    def snapshot(self) -> dict:
        """Chụp lại cấu hình để về sau dựng lại đúng kết quả cũ. Không có bí mật nào ở đây."""
        return asdict(self)
