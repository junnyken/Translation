"""Vẽ chữ dịch lên ảnh clean, xuất ra ảnh preview RIÊNG (M6 constraint 6).

Tuyệt đối không ghi đè `image_path` (ảnh gốc) hay `clean_image_path` (ảnh sạch của M4):
M7 còn phải sửa tay từng vùng và M8 còn export, nên hai ảnh kia phải giữ nguyên để đối chiếu.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, replace
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
    #: E70 — màu đo từ chữ gốc. None = dùng màu mặc định của renderer (hành vi trước E70).
    #: `stroke_width` là px ẢNH GỐC; bộ vẽ tự nhân hệ số vẽ cùng chỗ với hình học.
    text_color: str | None = None
    stroke_color: str | None = None
    stroke_width: float | None = None
    #: E75 — chữ xếp theo hình bong bóng: `[[tâm_x, đỉnh_y], …]` mỗi dòng, toạ độ ẢNH GỐC, do bước
    #: căn chữ tính và lưu. Có thì vẽ TỪNG DÒNG đúng chỗ đó; None ⇒ khối chữ nhật như trước.
    dong: list | None = None


class PagePreviewRenderer:
    def __init__(
        self,
        font_resolver: FontResolver,
        line_spacing_ratio: float,
        text_color: str = "black",
        stroke_color: str = "white",
        stroke_width: int = 0,
        # E60b — MẶC ĐỊNH TẮT. Trước đây mặc định `True` và không ai truyền `False`, nên khung đỏ
        # cảnh báo tràn bị nướng vào **mọi** ảnh: cả tệp xuất lẫn ảnh mà trang chủ tải về cho người
        # dùng (`GET /doc-truyen/trang/{id}/anh` phục vụ chính ảnh preview này).
        #
        # Thông tin KHÔNG mất, và đó là lý do tắt được: giao diện web đã vẽ cảnh báo tràn ở phía máy
        # khách (`BboxOverlay.jsx` đọc `fit_status === 'overflow_warning'`), còn số vùng tràn hiện ở
        # ba chỗ khác (`ChapterProgress`, `ChapterSummary`, `ExportPanel`). Vẽ thêm vào chính ảnh là
        # thừa cho người rà soát, và là rác cho người đọc.
        #
        # Vẫn giữ tham số: ai cần một ảnh có dấu sẵn (gửi kèm báo lỗi, in ra soi) thì bật tường minh.
        mark_overflow: bool = False,
        # E65 — hệ số phóng ảnh RA. Bước căn chữ đã fit chữ vào khung nhân `he_so_ve`, nên
        # `font_size` trong `RegionDraw` là pixel của ảnh ĐÃ phóng. Vẽ mà quên phóng ⇒ chữ to
        # gấp `k` lần khung của nó. Mặc định 1.0 = y hệt hành vi trước E65.
        he_so_ve: float = 1.0,
    ) -> None:
        self.font_resolver = font_resolver
        self.line_spacing_ratio = line_spacing_ratio
        self.text_color = text_color
        self.stroke_color = stroke_color
        self.stroke_width = int(stroke_width)
        self.mark_overflow = mark_overflow
        self.he_so_ve = float(he_so_ve or 1.0)

    def draw(
        self, clean_image_path: str, regions: list[RegionDraw], he_so_ve: float | None = None,
    ) -> Image.Image:
        """Vẽ chữ lên bản sao của ảnh clean và trả về **ảnh trong bộ nhớ**, không ghi file.

        Tách riêng khỏi `render()` để M8 xuất chapter dùng lại ĐÚNG logic vẽ này mà không cần
        file trung gian — hai đường vẽ khác nhau là mầm mống sai lệch giữa ảnh xem thử và
        ảnh xuất ra.
        """
        # Hệ số theo LƯỢT vẽ: xuất cả chapter dùng CHUNG một renderer cho mọi trang, mà hệ số
        # là của từng trang. Ghim nó vào renderer thì mọi trang trong chapter bị phóng theo trang
        # đầu tiên.
        k = self._he_so(he_so_ve)
        canvas = self.mo_nen(clean_image_path, k)
        draw = ImageDraw.Draw(canvas)
        for region in regions:
            self._ve_vung(canvas, draw, region, k)
        return canvas

    def _he_so(self, he_so_ve: float | None) -> float:
        return float(he_so_ve if he_so_ve is not None else self.he_so_ve)

    @staticmethod
    def co_chu(region: RegionDraw) -> bool:
        """Vùng này có chữ để vẽ không — ĐÚNG điều kiện mà `_ve_vung` dùng để bỏ qua."""
        return bool(region.wrapped_text) and region.font_size is not None

    @staticmethod
    def mo_nen(duong_anh: str, k: float, kich_thuoc: tuple[int, int] | None = None) -> Image.Image:
        """Mở ảnh thành RGB và phóng theo hệ số `k` (LANCZOS) — nền mà chữ được vẽ lên.

        `kich_thuoc` (E78): ép về đúng cỡ này thay vì tính từ `k` — để ẢNH GỐC trong PSD khớp
        từng điểm ảnh với canvas đã phóng của ảnh clean, kể cả khi hai ảnh lệch nhau 1px.
        """
        with Image.open(duong_anh) as goc:
            canvas = goc.convert("RGB")
            dich = kich_thuoc or (max(round(canvas.width * k), 1), max(round(canvas.height * k), 1))
            if dich != canvas.size:
                # LANCZOS: nét mực manga là cạnh mảnh, tương phản cao — nội suy song tuyến làm
                # nó xám nhoè. Ảnh này chỉ đi VẼ CHỮ, không đi đọc chữ, nên phóng ở đây không
                # đụng gì tới chất lượng OCR (đó là cả ý của E65).
                canvas = canvas.resize(dich, Image.LANCZOS)
            else:
                canvas = canvas.copy()
        return canvas

    def draw_lop_vung(
        self, kich_thuoc: tuple[int, int], regions: list[RegionDraw],
        he_so_ve: float | None = None,
    ):
        """E78 — vẽ MỖI vùng có chữ lên một lớp RGBA trong suốt cỡ `kich_thuoc` (canvas đã phóng).

        Sinh ra `(số thứ tự vùng tính từ 1, vùng, lớp RGBA)` lần lượt — không giữ mọi lớp trong RAM.
        Dùng CHÍNH `_ve_vung` của `draw()`, nên chữ trong PSD là chữ của ảnh xem thử.
        """
        k = self._he_so(he_so_ve)
        for so, region in enumerate(regions, start=1):
            if not self.co_chu(region):
                continue
            lop = Image.new("RGBA", kich_thuoc, (0, 0, 0, 0))
            self._ve_vung(lop, ImageDraw.Draw(lop), region, k)
            yield so, region, lop

    @staticmethod
    def _dan(canvas: Image.Image, o: Image.Image, vi_tri: tuple[int, int]) -> None:
        """Dán ô chữ RGBA lên canvas.

        Canvas RGB (ảnh xem thử) giữ nguyên `paste(…, mask)` như trước E78. Canvas RGBA trong suốt
        (lớp PSD) phải dùng ghép alpha: `paste` với mask trộn CẢ kênh alpha nên mép chữ khử răng
        cưa ra alpha bình phương — chữ mỏng đi khi ghép lại trong Photoshop.
        """
        if canvas.mode != "RGBA":
            canvas.paste(o, vi_tri, o)
            return
        x, y = vi_tri
        if x < 0 or y < 0:  # alpha_composite không nhận đích âm ⇒ cắt phần thò ra ngoài trước
            o = o.crop((max(-x, 0), max(-y, 0), o.width, o.height))
            x, y = max(x, 0), max(y, 0)
            if o.width == 0 or o.height == 0:
                return
        canvas.alpha_composite(o, (x, y))

    def _ve_vung(self, canvas: Image.Image, draw, region: RegionDraw, k: float) -> None:
        """Vẽ MỘT vùng lên `canvas` — thân vòng lặp của `draw()`, tách ra cho E78 dùng lại."""
        if k != 1.0:
            # Nhân TOÀN BỘ hình học lên một lần, ngay tại đây. Nhân rải rác ở từng chỗ dùng
            # là cách chắc chắn bỏ sót một chỗ — và chỗ bỏ sót sẽ là một vùng chữ lệch mà
            # không có gì báo.
            region = replace(
                region,
                bbox=BBox(
                    x=region.bbox.x * k, y=region.bbox.y * k,
                    w=region.bbox.w * k, h=region.bbox.h * k,
                ),
                place_rect=(
                    None if region.place_rect is None
                    else tuple(v * k for v in region.place_rect)
                ),
                stroke_width=(
                    None if region.stroke_width is None else region.stroke_width * k
                ),
                dong=(None if not region.dong else [[x * k, y * k] for x, y in region.dong]),
            )
        if not region.wrapped_text or region.font_size is None:
            return
        font = self.font_resolver.resolve(region.font_family, int(region.font_size))
        spacing = int(round(region.font_size * self.line_spacing_ratio))
        ao = self._ao_chu(region)
        if region.dong and not nen_xoay(region.rotation_degrees):
            self._ve_theo_dong(draw, region, font, ao)
            return

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
            stroke_width=ao[2], align="center",
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
                ao,
            )
        else:
            ImageDraw.Draw(o).multiline_text(
                (x - cat_x, y - cat_y),
                region.wrapped_text, font=font, fill=ao[0],
                spacing=spacing, align="center",
                stroke_width=ao[2], stroke_fill=ao[1],
            )
        self._dan(canvas, o, (int(round(cat_x)), int(round(cat_y))))
        if region.overflow and self.mark_overflow:
            # Vùng tràn phải NHÌN THẤY được trên preview, không để chữ đẹp che mất cảnh báo.
            draw.rectangle(
                [region.bbox.x, region.bbox.y,
                 region.bbox.x + region.bbox.w, region.bbox.y + region.bbox.h],
                outline="red", width=2,
            )

    def _ve_theo_dong(self, draw, region: RegionDraw, font, ao) -> None:
        """E75 — vẽ từng dòng đúng vị trí bước căn chữ đã lưu.

        Bước căn đã bảo đảm từng dòng nằm trong đa giác bong bóng, nên không cần ô cắt. Chiều cao và
        độ lệch dòng lấy từ `do_dong()` — CÙNG hàm bước căn dùng, nên không thể lệch nhau.
        """
        from app.services.typeset.xep_theo_hinh import be_rong_dong, do_dong

        mau, mau_vien, vien = ao
        gian = int(round((region.font_size or 0) * self.line_spacing_ratio))
        lech, _cao, _buoc = do_dong(font, vien, gian)
        cac_dong = (region.wrapped_text or "").split("\n")
        for chu, (tam_x, dinh_y) in zip(cac_dong, region.dong, strict=False):
            x = tam_x - be_rong_dong(font, chu, vien) / 2 + vien
            draw.text((x, dinh_y - lech), chu, font=font, fill=mau, anchor="la",
                      stroke_width=vien, stroke_fill=mau_vien)

    def _ao_chu(self, region: RegionDraw) -> tuple[str, str, int]:
        """(màu chữ, màu viền, bề dày viền) để vẽ vùng này — E70 có đo thì dùng, không thì mặc định.

        Có màu chữ đo được mà không có viền ⇒ viền = 0, KHÔNG rơi về viền cấu hình: chữ gốc không
        viền thì chữ dịch cũng không viền.
        """
        if region.text_color is None:
            return self.text_color, self.stroke_color, self.stroke_width
        if region.stroke_color is None or not region.stroke_width:
            return region.text_color, self.stroke_color, 0
        return region.text_color, region.stroke_color, max(int(round(region.stroke_width)), 1)

    def _ve_xoay(self, o, region, font, spacing, o_size, khoi, offset, ao=None) -> None:
        """E16 — vẽ chữ nghiêng vào ô `o` (đã đúng cỡ ô cắt), không để tràn ra ngoài.

        Vì sao phải THU NHỎ cỡ chữ: hộp bao của chữ sau khi xoay LỚN HƠN chữ ngang —
        `w·|cosθ| + h·|sinθ|` theo chiều ngang. Cỡ chữ đã được bộ fit tính cho khung ngang, nên
        xoay nguyên cỡ đó là bị ô cắt gọt mất góc. Thu nhỏ theo đúng tỉ lệ hình học thì chữ nghiêng
        mà vẫn nằm gọn.

        Thu nhỏ bằng cách **vẽ lại ở cỡ font nhỏ hơn**, KHÔNG phải co ảnh bitmap — co bitmap làm
        nét chữ nhoè, mà đây là bước cuối cùng người dùng nhìn thấy.
        """
        import math

        if ao is None:
            ao = self._ao_chu(region)
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
            stroke_width=ao[2], align="center",
        )
        lop_rong, lop_cao = max(int(round(r2 - l2)), 1), max(int(round(b2 - t2)), 1)
        lop = Image.new("RGBA", (lop_rong, lop_cao), (0, 0, 0, 0))
        ImageDraw.Draw(lop).multiline_text(
            (-l2, -t2), region.wrapped_text, font=ve_font, fill=ao[0],
            spacing=ve_spacing, align="center",
            stroke_width=ao[2], stroke_fill=ao[1],
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
