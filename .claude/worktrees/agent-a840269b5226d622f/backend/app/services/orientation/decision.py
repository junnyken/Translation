"""Kết quả phân tích hướng chữ + danh sách mã lý do đóng (E15)."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.models.enums import OrientationSource, OrientationStatus, TextOrientation


class LyDo:
    """Danh sách đóng. Giao diện dịch từng mã ra tiếng Việt nên không được đẻ mã tuỳ hứng.

    Lệch so với spec E15: spec dự kiến mã `ctd_line_geometry_*`, nhưng audit đã chứng minh bộ
    nhận diện **không hề** trả hình học dòng chữ (chỉ có khung chữ nhật). Nguồn hình học thật
    là **đường bao dòng của OCR**, nên mã được đặt lại cho đúng sự thật thay vì giữ tên gợi ý
    một nguồn không tồn tại. Lý do đầy đủ: `docs/REPORT_E15.md` §2.
    """

    OCR_LINE_GEOMETRY_VERTICAL = "ocr_line_geometry_vertical"
    OCR_LINE_GEOMETRY_HORIZONTAL = "ocr_line_geometry_horizontal"
    OCR_LAYOUT_UNAVAILABLE = "ocr_layout_unavailable"
    CTD_GEOMETRY_UNAVAILABLE = "ctd_geometry_unavailable"
    ROI_ROTATED_TEXT_EVIDENCE = "roi_rotated_text_evidence"
    BBOX_ASPECT_VERTICAL_SIGNAL = "bbox_aspect_vertical_signal"
    BBOX_ASPECT_HORIZONTAL_SIGNAL = "bbox_aspect_horizontal_signal"
    POSSIBLE_SFX_FROM_QUALITY_GATE = "possible_sfx_from_quality_gate"
    SAFE_AREA_FALLBACK_RECTANGLE = "safe_area_fallback_rectangle"
    VERTICAL_RENDERER_UNAVAILABLE = "vertical_renderer_unavailable"
    VERTICAL_FONT_GLYPH_UNAVAILABLE = "vertical_font_glyph_unavailable"
    VERTICAL_LAYOUT_OVERFLOW = "vertical_layout_overflow"
    ROTATED_TEXT_MANUAL_REVIEW_ONLY = "rotated_text_manual_review_only"
    ORIENTATION_EVIDENCE_CONFLICT = "orientation_evidence_conflict"
    ORIENTATION_UNKNOWN = "orientation_unknown"

    TAT_CA = frozenset({
        OCR_LINE_GEOMETRY_VERTICAL, OCR_LINE_GEOMETRY_HORIZONTAL, OCR_LAYOUT_UNAVAILABLE,
        CTD_GEOMETRY_UNAVAILABLE, ROI_ROTATED_TEXT_EVIDENCE, BBOX_ASPECT_VERTICAL_SIGNAL,
        BBOX_ASPECT_HORIZONTAL_SIGNAL, POSSIBLE_SFX_FROM_QUALITY_GATE,
        SAFE_AREA_FALLBACK_RECTANGLE, VERTICAL_RENDERER_UNAVAILABLE,
        VERTICAL_FONT_GLYPH_UNAVAILABLE, VERTICAL_LAYOUT_OVERFLOW,
        ROTATED_TEXT_MANUAL_REVIEW_ONLY, ORIENTATION_EVIDENCE_CONFLICT, ORIENTATION_UNKNOWN,
    })


@dataclass(frozen=True)
class OrientationDecision:
    orientation: TextOrientation
    source: OrientationSource
    status: OrientationStatus
    reason_codes: list[str] = field(default_factory=list)
    rotation_degrees: float | None = None
    line_count_estimate: int | None = None
    evidence_snapshot: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        la = [m for m in self.reason_codes if m not in LyDo.TAT_CA]
        if la:
            raise ValueError(f"mã lý do lạ: {la}")

        # `vertical_ttb` + `ready` là lời khẳng định mạnh nhất E15 đưa ra: nó khiến hệ thống
        # thật sự dựng chữ theo cột. Ràng ngay ở tầng kiểu dữ liệu để không nơi nào tạo được
        # một khẳng định như vậy mà không có bằng chứng hình học.
        if (self.orientation is TextOrientation.vertical_ttb
                and self.status is OrientationStatus.ready
                and LyDo.OCR_LINE_GEOMETRY_VERTICAL not in self.reason_codes):
            raise ValueError("vertical_ttb + ready phải có bằng chứng hình học dòng chữ")

        if self.orientation is TextOrientation.rotated_horizontal:
            if self.rotation_degrees is None:
                raise ValueError("rotated_horizontal phải kèm góc đã chuẩn hoá")
            if LyDo.ROTATED_TEXT_MANUAL_REVIEW_ONLY not in self.reason_codes:
                # v1 tuyệt đối không tự xoay chữ; nói rõ điều đó ngay trong bằng chứng.
                raise ValueError("rotated_horizontal ở v1 phải kèm rotated_text_manual_review_only")

        if (self.orientation is TextOrientation.unknown
                and LyDo.ORIENTATION_UNKNOWN not in self.reason_codes):
            raise ValueError("unknown phải kèm orientation_unknown")
