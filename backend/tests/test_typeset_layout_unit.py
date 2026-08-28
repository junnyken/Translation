"""Unit — ngắt dòng & đo chữ theo font metrics THẬT (M6)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.services.typeset.fonts import FontNotFound, FontResolver, MissingGlyph, normalize_for_layout
from app.services.typeset.layout import TextLayoutEngine

FONT_DIR = os.environ.get("FONT_DIR") or str(Path(__file__).resolve().parents[1] / "fonts")


@pytest.fixture
def resolver() -> FontResolver:
    return FontResolver(FONT_DIR, "Bangers")


@pytest.fixture
def layout() -> TextLayoutEngine:
    return TextLayoutEngine()


class TestNormalize:
    def test_nfd_duoc_dua_ve_nfc(self):
        """Chuỗi NFD render sai và `getlength` lại trả đúng số của NFC ⇒ sai không lộ ra."""
        import unicodedata

        nfd = unicodedata.normalize("NFD", "ĐỪNG")
        assert len(nfd) > len("ĐỪNG")
        assert normalize_for_layout(nfd) == "ĐỪNG"

    def test_khong_doi_noi_dung_ngoai_chuan_hoa(self):
        assert normalize_for_layout("Chào cậu!") == "Chào cậu!"
        assert normalize_for_layout("") == ""


class TestWrap:
    def test_moi_dong_khong_vuot_be_rong(self, resolver, layout):
        font = resolver.resolve("Bangers", 24)
        text = "Cậu ổn chứ? Tớ tưởng cậu đã biến mất rồi, thật đấy!"
        wrapped = layout.wrap_to_width(text, font, 200)
        for dong in wrapped.split("\n"):
            assert font.getlength(dong) <= 200, f"dòng vượt khổ: {dong!r}"

    def test_wrap_theo_do_dai_that_khong_theo_so_ky_tu(self, resolver, layout):
        """'IIII' và 'MMMM' cùng 4 ký tự nhưng rộng khác nhau ⇒ ngắt dòng phải khác."""
        font = resolver.resolve("ShantellSans", 26)
        assert font.getlength("MMMM") > font.getlength("iiii")
        rong = int(font.getlength("MMMM")) + 1  # vừa đúng 1 token "MMMM"
        assert layout.wrap_to_width("MMMM MMMM", font, rong).count("\n") == 1
        assert layout.wrap_to_width("iiii iiii", font, rong).count("\n") == 0

    def test_chu_viet_co_dau_van_wrap_dung(self, resolver, layout):
        font = resolver.resolve("Bangers", 22)
        text = "ĐỪNG NGOẢNH LẠI NGUY HIỂM LẮM ĐẤY CẬU ƠI"
        wrapped = layout.wrap_to_width(text, font, 180)
        assert wrapped.count("\n") >= 1
        for dong in wrapped.split("\n"):
            assert font.getlength(dong) <= 180

    def test_token_dai_khong_khoang_trang_bi_cat_an_toan(self, resolver, layout):
        font = resolver.resolve("Bangers", 24)
        token = "siêuquậycựckỳlợihạikhôngaingănnổiđâunhé"
        wrapped = layout.wrap_to_width(token, font, 120)
        assert wrapped.count("\n") >= 1
        for dong in wrapped.split("\n"):
            assert font.getlength(dong) <= 120
        # Không mất/không thêm ký tự nào ngoài dấu xuống dòng.
        assert wrapped.replace("\n", "") == token

    def test_giu_nguyen_xuong_dong_co_san_trong_ban_dich(self, resolver, layout):
        font = resolver.resolve("Bangers", 20)
        assert layout.wrap_to_width("Xin chào\nĐÓ", font, 900) == "Xin chào\nĐÓ"

    def test_text_rong_tra_chuoi_rong(self, resolver, layout):
        font = resolver.resolve("Bangers", 20)
        assert layout.wrap_to_width("   ", font, 100) == ""
        assert layout.wrap_to_width("", font, 100) == ""

    def test_be_rong_khong_duong_khong_treo_vong_lap(self, resolver, layout):
        font = resolver.resolve("Bangers", 20)
        assert layout.wrap_to_width("abc", font, 0) == "abc"


class TestMeasure:
    def test_nhieu_dong_cao_hon_mot_dong(self, resolver, layout):
        font = resolver.resolve("Bangers", 24)
        _w1, h1 = layout.measure_multiline("MỘT", font, spacing=4)
        _w2, h2 = layout.measure_multiline("MỘT\nHAI", font, spacing=4)
        assert h2 > h1

    def test_khoang_cach_dong_lon_hon_thi_cao_hon(self, resolver, layout):
        font = resolver.resolve("Bangers", 24)
        _w, h_it = layout.measure_multiline("MỘT\nHAI", font, spacing=0)
        _w2, h_nhieu = layout.measure_multiline("MỘT\nHAI", font, spacing=20)
        assert h_nhieu > h_it

    def test_vien_chu_lam_khoi_to_ra(self, resolver, layout):
        font = resolver.resolve("Bangers", 24)
        w0, h0 = layout.measure_multiline("CẨN THẬN", font, spacing=4, stroke_width=0)
        w3, h3 = layout.measure_multiline("CẨN THẬN", font, spacing=4, stroke_width=3)
        assert w3 > w0 and h3 > h0

    def test_dau_tieng_viet_lam_dong_cao_hon_chu_khong_dau(self, resolver, layout):
        """Bằng chứng vì sao KHÔNG được ước lượng chiều cao theo số ký tự."""
        font = resolver.resolve("ShantellSans", 30)
        _w, h_co_dau = layout.measure_multiline("Ể", font)
        _w2, h_khong_dau = layout.measure_multiline("E", font)
        assert h_co_dau > h_khong_dau

    def test_chuoi_rong_do_ra_khong(self, resolver, layout):
        font = resolver.resolve("Bangers", 20)
        assert layout.measure_multiline("", font) == (0, 0)


class TestFontResolver:
    def test_family_ngoai_whitelist_bao_loi_ro(self, resolver):
        with pytest.raises(FontNotFound, match="font_not_found"):
            resolver.resolve("ComicSansGiaMao", 20)

    def test_file_font_thieu_bao_loi_ro(self):
        r = FontResolver("/duong-dan-khong-ton-tai", "Bangers")
        with pytest.raises(FontNotFound, match="thiếu file"):
            r.resolve("Bangers", 20)

    def test_khong_tu_fallback_khi_chua_bat(self):
        r = FontResolver(FONT_DIR, "Bangers", allow_fallback=False)
        with pytest.raises(FontNotFound):
            r.resolve("KhongTonTai", 20)

    def test_co_fallback_khi_bat_tuong_minh(self):
        r = FontResolver(FONT_DIR, "Bangers", allow_fallback=True)
        assert r.resolve("KhongTonTai", 20) is not None

    def test_font_bien_thien_chon_dung_net(self, resolver):
        thuong = resolver.resolve("ShantellSans", 30)
        dam = resolver.resolve("ShantellSans-Bold", 30)
        assert dam.getlength("Cẩn thận") > thuong.getlength("Cẩn thận")

    def test_thieu_glyph_bao_loi_khong_am_tham_ra_o_vuong(self, resolver, tmp_path):
        """Font thiếu dấu tiếng Việt phải NỔ, không được vẽ ô vuông rồi báo thành công.

        Tự cắt một font chỉ còn ASCII để dựng đúng tình huống — đây chính là thứ đã xảy ra thật
        với `HL Comic2` (font spec chỉ định, chỉ có 38/134 ký tự Việt, xem docs/FONTS.md).
        """
        from fontTools import subset
        from PIL import ImageFont

        chi_ascii = tmp_path / "chi-ascii.ttf"
        subsetter = subset.Subsetter()
        goc = subset.load_font(str(Path(FONT_DIR) / "Bangers" / "Bangers-Regular.ttf"), subset.Options())
        subsetter.populate(text="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz ,.!?")
        subsetter.subset(goc)
        goc.save(str(chi_ascii))
        thieu = ImageFont.truetype(str(chi_ascii), 24)
        with pytest.raises(MissingGlyph, match="font_missing_glyph"):
            resolver.assert_can_render(thieu, "Cẩn thận, ưở ẫ ệ ợ ắ")

    def test_font_du_dau_khong_bao_nham(self, resolver):
        for family in ("Bangers", "Mansalva", "SigmarOne", "ShantellSans-BoldItalic"):
            resolver.assert_can_render(
                resolver.resolve(family, 26), "ĐỪNG NGOẢNH LẠI ưở ẫ ệ ợ Cẩn thận"
            )
