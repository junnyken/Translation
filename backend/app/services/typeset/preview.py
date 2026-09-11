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

from app.services.typeset.xoay import goc_pil, nen_xoay

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
    #: E16: hướng-đường [0,180) từ `RegionTextOrientation.rotation_degrees`. **KHÔNG** phải góc
    #: xoay — xem `typeset/xoay.py`. `None` hoặc gần nằm ngang thì vẽ y như trước.
    rotation_degrees: float | None = None


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
            if nen_xoay(region.rotation_degrees):
                # E16 — chữ nghiêng. Vẽ vào lớp RIÊNG rồi xoay, xong dán vào chính ô cắt ở trên,
                # nên bất biến "chữ không thoát khỏi khung của nó" vẫn giữ nguyên.
                self._ve_xoay(
                    o, region, font, spacing, (o_rong, o_cao), (khoi_rong, khoi_cao), (left, top),
                )
            else:
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

    def _ve_xoay(self, o, region, font, spacing, o_size, khoi, offset) -> None:
        """E16 — vẽ chữ nghiêng vào ô `o` (đã đúng cỡ ô cắt), không để tràn ra ngoài.

        Vì sao phải THU NHỎ cỡ chữ: hộp bao của chữ sau khi xoay LỚN HƠN chữ ngang —
        `w·|cosθ| + h·|sinθ|` theo chiều ngang. Cỡ chữ đã được bộ fit tính cho khung ngang, nên
        xoay nguyên cỡ đó là bị ô cắt gọt mất góc. Thu nhỏ theo đúng tỉ lệ hình học thì chữ nghiêng
        mà vẫn nằm gọn.

        Thu nhỏ bằng cách **vẽ lại ở cỡ font nhỏ hơn**, KHÔNG phải co ảnh bitmap — co bitmap làm
        nét chữ nhoè, mà đây là bước cuối cùng người dùng nhìn thấy.
        """
        import math

        o_rong, o_cao = o_size
        khoi_rong, khoi_cao = khoi
        goc = goc_pil(region.rotation_degrees)
        rad = math.radians(goc)
        c, sn = abs(math.cos(rad)), abs(math.sin(rad))

        # Hộp bao sau khi xoay, tính từ khối chữ hiện tại.
        bao_rong = khoi_rong * c + khoi_cao * sn
        bao_cao = khoi_rong * sn + khoi_cao * c
        ti_le = min(1.0, o_rong / max(bao_rong, 1e-6), o_cao / max(bao_cao, 1e-6))

        ve_font, ve_spacing = font, spacing
        if ti_le < 1.0 and region.font_size:
            co_moi = max(1, int(region.font_size * ti_le))
            ve_font = self.font_resolver.resolve(region.font_family, co_moi)
            ve_spacing = int(round(co_moi * self.line_spacing_ratio))

        # Đo lại ở cỡ thật sẽ vẽ, rồi dựng lớp vừa khít khối chữ.
        l2, t2, r2, b2 = ImageDraw.Draw(Image.new("L", (1, 1))).multiline_textbbox(
            (0, 0), region.wrapped_text, font=ve_font, spacing=ve_spacing,
            stroke_width=self.stroke_width, align="center",
        )
        lop_rong, lop_cao = max(int(round(r2 - l2)), 1), max(int(round(b2 - t2)), 1)
        lop = Image.new("RGBA", (lop_rong, lop_cao), (0, 0, 0, 0))
        ImageDraw.Draw(lop).multiline_text(
            (-l2, -t2), region.wrapped_text, font=ve_font, fill=self.text_color,
            spacing=ve_spacing, align="center",
            stroke_width=self.stroke_width, stroke_fill=self.stroke_color,
        )

        # `expand=True` để không tự cắt góc lúc xoay; BICUBIC cho mép chữ đỡ răng cưa.
        da_xoay = lop.rotate(goc, resample=Image.Resampling.BICUBIC, expand=True)
        dan_x = int(round((o_rong - da_xoay.width) / 2))
        dan_y = int(round((o_cao - da_xoay.height) / 2))
        o.alpha_composite(da_xoay, (max(dan_x, 0), max(dan_y, 0))) if (
            dan_x >= 0 and dan_y >= 0
        ) else o.paste(da_xoay, (dan_x, dan_y), da_xoay)

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
