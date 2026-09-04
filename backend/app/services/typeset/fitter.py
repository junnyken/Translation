"""Chọn cỡ chữ lớn nhất mà bản dịch vẫn nằm gọn trong bubble (M6).

Nguyên tắc không được vi phạm: **không co chữ xuống dưới `min_font_size` để giả vờ vừa khung**.
Không vừa ở cỡ nhỏ nhất ⇒ trả `overflow_warning` để M7 sửa tay, chứ không làm chữ bé li ti.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.interfaces import BBox
from app.services.typeset.fonts import FontResolver, normalize_for_layout
from app.services.typeset.layout import TextLayoutEngine

FIT_OK = "fit_ok"
OVERFLOW_WARNING = "overflow_warning"
PENDING = "pending"
#: `fit()` KHÔNG bao giờ tự trả trạng thái này — nó vẫn ném `MissingGlyph`, vì canh chữ cho một
#: vùng mà nuốt lỗi font là đúng thứ sinh ra ô vuông. Trạng thái này do **người gọi** ghi xuống
#: khi quyết định cho cả trang đi tiếp mà bỏ lại vùng hỏng (xem `_run_typeset`).
FONT_MISSING_GLYPH = "font_missing_glyph"


@dataclass(frozen=True)
class ContentRect:
    """Vùng chữ được phép chiếm = bbox trừ padding."""

    width: int
    height: int

    @property
    def usable(self) -> bool:
        return self.width > 0 and self.height > 0


class FitToBoxTypesetter:
    """Implement Protocol `ITypesetter` (M1) — giữ nguyên signature `fit(text, bbox, font_family)`."""

    def __init__(
        self,
        font_resolver: FontResolver,
        min_font_size: int,
        max_font_size: int,
        padding_ratio: float,
        line_spacing_ratio: float,
        stroke_width: int = 0,
    ) -> None:
        if min_font_size > max_font_size:
            raise ValueError(
                f"TYPESET_MIN_FONT_SIZE ({min_font_size}) > TYPESET_MAX_FONT_SIZE ({max_font_size})"
            )
        self.font_resolver = font_resolver
        self.min_font_size = int(min_font_size)
        self.max_font_size = int(max_font_size)
        self.padding_ratio = float(padding_ratio)
        self.line_spacing_ratio = float(line_spacing_ratio)
        self.stroke_width = int(stroke_width)
        self.layout = TextLayoutEngine()

    # ---------- hình học ----------
    def content_rect(self, bbox: BBox) -> ContentRect:
        """bbox trừ padding hai bên. bbox quá nhỏ ⇒ vùng chữ <= 0, KHÔNG tạo padding âm."""
        pad_x = bbox.w * self.padding_ratio
        pad_y = bbox.h * self.padding_ratio
        return ContentRect(int(bbox.w - 2 * pad_x), int(bbox.h - 2 * pad_y))

    def _spacing_for(self, font_size: int) -> int:
        return int(round(font_size * self.line_spacing_ratio))

    def _do_thu(self, text: str, font_family: str, size: int, rect: ContentRect) -> tuple[str, int, int]:
        font = self.font_resolver.resolve(font_family, size)
        wrapped = self.layout.wrap_to_width(text, font, rect.width)
        w, h = self.layout.measure_multiline(
            wrapped, font, spacing=self._spacing_for(size), stroke_width=self.stroke_width
        )
        return wrapped, w, h

    # ---------- contract M1 ----------
    def fit(self, text: str, bbox: BBox, font_family: str) -> dict:
        """Trả `{font_size, wrapped_text, fit_status}`. Không render, không ghi DB.

        Tìm cỡ lớn nhất vừa khung bằng cách **giảm dần 1px từ max xuống min**, lấy cỡ đầu tiên vừa.

        KHÔNG dùng tìm kiếm nhị phân: đo trên chính dữ liệu thật cho thấy quan hệ "vừa khung theo cỡ
        chữ" **không đơn điệu** — `"Cẩn thận!"` trong bubble 108x83 vừa ở cỡ 25, hỏng ở 26, rồi lại vừa
        ở 27, vì tăng cỡ làm ngắt dòng đổi đột ngột (2 dòng thành 1 dòng). Nhị phân sẽ dừng ở 25 và bỏ
        sót cỡ 27. Chỉ giữ MỘT thuật toán trong production (spec §6) — bằng chứng ở REPORT_M6 §3.
        """
        text = normalize_for_layout(text)

        # Không có chữ để canh: đây KHÔNG phải "tràn khung", nên không gắn overflow_warning.
        if not text.strip():
            return {"font_size": None, "wrapped_text": "", "fit_status": PENDING}

        rect = self.content_rect(bbox)
        if not rect.usable:
            # bbox nhỏ hơn 2×padding: cảnh báo, tuyệt đối không tạo padding âm hay crash.
            return {
                "font_size": float(self.min_font_size),
                "wrapped_text": text,
                "fit_status": OVERFLOW_WARNING,
            }

        # Kiểm glyph MỘT lần ở cỡ bất kỳ — thiếu glyph là lỗi của font, không phụ thuộc cỡ chữ.
        self.font_resolver.assert_can_render(
            self.font_resolver.resolve(font_family, self.max_font_size), text
        )

        for size in range(self.max_font_size, self.min_font_size - 1, -1):
            wrapped, w, h = self._do_thu(text, font_family, size, rect)
            if w <= rect.width and h <= rect.height:
                return {"font_size": float(size), "wrapped_text": wrapped, "fit_status": FIT_OK}

        # Tới cỡ nhỏ nhất vẫn không vừa: giữ nguyên cỡ min và nói thật là tràn.
        wrapped, _w, _h = self._do_thu(text, font_family, self.min_font_size, rect)
        return {
            "font_size": float(self.min_font_size),
            "wrapped_text": wrapped,
            "fit_status": OVERFLOW_WARNING,
        }

    def fit_at_size(self, text: str, bbox: BBox, font_family: str, font_size: float) -> dict:
        """Canh chữ ở ĐÚNG cỡ người dùng ghim (M7) — không dò cỡ, chỉ báo thật vừa hay tràn.

        Người dùng đổi cỡ chữ tay là vì auto-fit chưa vừa ý, nên tôn trọng lựa chọn đó. Nhưng
        vẫn phải nói thật: cỡ đó tràn khung thì gắn `overflow_warning`, không giả vờ vừa.
        Cỡ bị kẹp trong [min, max] để không ai đặt cỡ 500px làm vỡ trang.
        """
        text = normalize_for_layout(text)
        size = int(round(max(self.min_font_size, min(float(font_size), self.max_font_size))))
        if not text.strip():
            return {"font_size": None, "wrapped_text": "", "fit_status": PENDING}

        rect = self.content_rect(bbox)
        if not rect.usable:
            return {"font_size": float(size), "wrapped_text": text, "fit_status": OVERFLOW_WARNING}

        self.font_resolver.assert_can_render(
            self.font_resolver.resolve(font_family, size), text
        )
        wrapped, w, h = self._do_thu(text, font_family, size, rect)
        vua = w <= rect.width and h <= rect.height
        return {
            "font_size": float(size),
            "wrapped_text": wrapped,
            "fit_status": FIT_OK if vua else OVERFLOW_WARNING,
        }
