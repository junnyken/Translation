"""Vẽ chữ dịch lên ảnh clean, xuất ra ảnh preview RIÊNG (M6 constraint 6).

Tuyệt đối không ghi đè `image_path` (ảnh gốc) hay `clean_image_path` (ảnh sạch của M4):
M7 còn phải sửa tay từng vùng và M8 còn export, nên hai ảnh kia phải giữ nguyên để đối chiếu.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

from app.services.interfaces import BBox
from app.services.typeset.fonts import FontResolver
from app.services.typeset.paths import preview_relative_path

__all__ = ["PagePreviewRenderer", "RegionDraw", "preview_relative_path"]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RegionDraw:
    """Một vùng cần vẽ: bbox gốc + kết quả fit đã tính."""

    bbox: BBox
    wrapped_text: str
    font_family: str
    font_size: float | None
    padding_ratio: float
    overflow: bool = False
    #: E14: ô đặt chữ nằm gọn trong lòng bong bóng, toạ độ ảnh gốc (x, y, w, h).
    #: Có thì chữ được căn giữa trong ô NÀY và cũng bị cắt gọn trong nó; không có thì giữ nguyên
    #: hành vi M6 (bbox trừ padding). Một đường vẽ duy nhất cho cả xem thử lẫn xuất file.
    place_rect: tuple[float, float, float, float] | None = None


class PagePreviewRenderer:
    def __init__(
        self,
        font_resolver: FontResolver,
        line_spacing_ratio: float,
        text_color: str = "black",
        stroke_color: str = "white",
        stroke_width: int = 0,
        mark_overflow: bool = True,
    ) -> None:
        self.font_resolver = font_resolver
        self.line_spacing_ratio = line_spacing_ratio
        self.text_color = text_color
        self.stroke_color = stroke_color
        self.stroke_width = int(stroke_width)
        self.mark_overflow = mark_overflow

    def draw(self, clean_image_path: str, regions: list[RegionDraw]) -> Image.Image:
        """Vẽ chữ lên bản sao của ảnh clean và trả về **ảnh trong bộ nhớ**, không ghi file.

        Tách riêng khỏi `render()` để M8 xuất chapter dùng lại ĐÚNG logic vẽ này mà không cần
        file trung gian — hai đường vẽ khác nhau là mầm mống sai lệch giữa ảnh xem thử và
        ảnh xuất ra.
        """
        with Image.open(clean_image_path) as goc:
            canvas = goc.convert("RGB").copy()
        draw = ImageDraw.Draw(canvas)

        for region in regions:
            if not region.wrapped_text or region.font_size is None:
                continue
            font = self.font_resolver.resolve(region.font_family, int(region.font_size))
            spacing = int(round(region.font_size * self.line_spacing_ratio))

            if region.place_rect is not None:
                # Vùng an toàn của E14 đã thụt vào sẵn nên KHÔNG trừ padding lần nữa —
                # trừ hai lần là chữ tự nhiên bé lại mà không ai giải thích được vì sao.
                trai, tren, rong, cao = region.place_rect
                rong = max(rong, 1.0)
                cao = max(cao, 1.0)
            else:
                pad_x = region.bbox.w * region.padding_ratio
                pad_y = region.bbox.h * region.padding_ratio
                trai = region.bbox.x + pad_x
                tren = region.bbox.y + pad_y
                rong = max(region.bbox.w - 2 * pad_x, 1.0)
                cao = max(region.bbox.h - 2 * pad_y, 1.0)

            left, top, right, bottom = draw.multiline_textbbox(
                (0, 0), region.wrapped_text, font=font, spacing=spacing,
                stroke_width=self.stroke_width, align="center",
            )
            khoi_rong, khoi_cao = right - left, bottom - top

            # Căn giữa cả hai chiều trong vùng content; trừ đi offset của bbox (dấu nhô lên
            # làm `top` âm) để chữ nằm đúng giữa chứ không lệch lên.
            x = trai + (rong - khoi_rong) / 2 - left
            y = tren + (cao - khoi_cao) / 2 - top

            # Vẽ vào một ô riêng ĐÚNG BẰNG bbox rồi dán đè, thay vì vẽ thẳng lên trang.
            # Nhờ vậy chữ bị cắt gọn trong khung của chính nó: vùng tràn khung không bao giờ
            # đè lên bubble khác hay chạy dọc suốt trang.
            # (Bản đầu chỉ kẹp ĐIỂM BẮT ĐẦU vào biên ảnh — chữ vẫn tràn ra ngoài; lỗi này chỉ lộ
            #  khi mở màn sửa tay của M7 và ghim một cỡ chữ lớn.)
            # Ô cắt = đúng vùng được phép chiếm. Với E14 đó là ô trong lòng bong bóng, nên chữ
            # tràn cũng không thể leo ra ngoài viền bong bóng.
            cat_x = trai if region.place_rect is not None else region.bbox.x
            cat_y = tren if region.place_rect is not None else region.bbox.y
            cat_w = rong if region.place_rect is not None else region.bbox.w
            cat_h = cao if region.place_rect is not None else region.bbox.h
            o_rong = max(int(round(cat_w)), 1)
            o_cao = max(int(round(cat_h)), 1)
            o = Image.new("RGBA", (o_rong, o_cao), (0, 0, 0, 0))
            ImageDraw.Draw(o).multiline_text(
                (x - cat_x, y - cat_y),
                region.wrapped_text, font=font, fill=self.text_color,
                spacing=spacing, align="center",
                stroke_width=self.stroke_width, stroke_fill=self.stroke_color,
            )
            canvas.paste(o, (int(round(cat_x)), int(round(cat_y))), o)
            if region.overflow and self.mark_overflow:
                # Vùng tràn phải NHÌN THẤY được trên preview, không để chữ đẹp che mất cảnh báo.
                draw.rectangle(
                    [region.bbox.x, region.bbox.y,
                     region.bbox.x + region.bbox.w, region.bbox.y + region.bbox.h],
                    outline="red", width=2,
                )

        return canvas

    def render(self, clean_image_path: str, regions: list[RegionDraw], target_path: str) -> str:
        """Vẽ rồi ghi ra file. Trả đường dẫn tuyệt đối đã ghi.

        Ghi ra file tạm rồi `os.replace` — đổi chỗ nguyên tử, nên ảnh cũ chỉ bị thay khi ảnh mới
        đã ghi xong. Không bao giờ để lộ ảnh vẽ dở.
        """
        canvas = self.draw(clean_image_path, regions)
        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tam = target.with_suffix(".tmp.png")
        canvas.save(tam, format="PNG")
        os.replace(tam, target)
        logger.info("preview typeset -> %s (%dx%d)", target, canvas.width, canvas.height)
        return str(target)
