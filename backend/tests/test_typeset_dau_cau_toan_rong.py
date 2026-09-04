"""Unit — gấp dấu câu toàn rộng trước khi đo/vẽ (sự cố 04/09).

## Sự cố gốc

Chapter thật trên bản chạy: 8 vùng, dịch xong bằng `google_fast`, rồi bước căn chữ chết sau
**0,034 giây** với `MissingGlyph: font thiếu glyph cho '．'`. Ký tự đó là U+FF0E — dấu chấm
toàn rộng của tiếng Nhật, không phải `.` (U+002E). Engine dịch đổi chữ sang tiếng Việt nhưng
bê nguyên dấu câu kiểu Nhật sang, và không font truyện tranh nào có glyph cho nó.

Test ở đây canh hai chiều: dấu câu phải được gấp, và **chữ Nhật thật thì KHÔNG được gấp** —
đổi chữ Nhật thành một ký tự Latin gần giống là dịch hộ người dùng, không phải xếp chữ.
"""
from __future__ import annotations

import os
import unicodedata
from pathlib import Path

import pytest

from app.services.interfaces import BBox
from app.services.typeset.fitter import FitToBoxTypesetter
from app.services.typeset.fonts import FontResolver, MissingGlyph, normalize_for_layout
from app.services.typeset.registry import FONT_REGISTRY

FONT_DIR = os.environ.get("FONT_DIR") or str(Path(__file__).resolve().parents[1] / "fonts")


@pytest.fixture
def fitter() -> FitToBoxTypesetter:
    return FitToBoxTypesetter(FontResolver(FONT_DIR, "Bangers"), 10, 28, 0.09, 0.18)


class TestGapDauCau:
    @pytest.mark.parametrize(
        ("goc", "mong_doi"),
        [
            ("．", "."), ("，", ","), ("！", "!"), ("？", "?"), ("：", ":"), ("；", ";"),
            ("（", "("), ("）", ")"), ("－", "-"), ("～", "~"), ("　", " "),
            ("。", "."), ("、", ","), ("・", "·"), ("〜", "~"), ("‥", ".."),
            ("「", '"'), ("」", '"'), ("『", '"'), ("』", '"'),
            ("Ａ", "A"), ("ｚ", "z"), ("１", "1"),
        ],
    )
    def test_tung_ky_tu(self, goc: str, mong_doi: str):
        assert normalize_for_layout(goc) == mong_doi

    def test_nguyen_cau_nhu_engine_dich_tra_ve(self):
        assert normalize_for_layout("Cậu ổn chứ？　Tớ về đây．") == "Cậu ổn chứ? Tớ về đây."

    def test_giu_nguyen_dau_cau_da_dung(self):
        cau = 'Ừ! Đi thôi... "ngay bây giờ" — nhé?'
        assert normalize_for_layout(cau) == cau

    def test_van_dua_ve_nfc(self):
        """Không được đánh mất việc cũ của hàm: NFD render sai (ĐỪNG → ĐUNG)."""
        nfd = unicodedata.normalize("NFD", "ĐỪNG NGOẢNH LẠI")
        assert nfd != "ĐỪNG NGOẢNH LẠI"          # chắc chắn đầu vào đúng là NFD
        assert normalize_for_layout(nfd) == "ĐỪNG NGOẢNH LẠI"

    def test_khong_dung_toi_chu_nhat(self):
        """Kana/kanji và dấu kéo dài âm `ー` KHÔNG phải dấu câu — không được tự đổi."""
        assert normalize_for_layout("オーイ、坂本") == "オーイ,坂本"   # chỉ `、` bị gấp

    def test_khong_dung_toi_katakana_nua_rong(self):
        """Dải U+FF61+ là katakana nửa rộng, KHÔNG phải dấu câu — gấp là ra chữ Latin bậy."""
        assert normalize_for_layout("ｱｲｳ") == "ｱｲｳ"

    def test_rong_va_none(self):
        assert normalize_for_layout("") == ""
        assert normalize_for_layout(None) == ""


class TestKhongConChetVi:
    """Tái hiện đúng sự cố: chuỗi đã làm chết trang test 2 phải căn được."""

    CAU_THAT = "Sakamoto－san．"

    def test_truoc_khi_gap_font_that_su_thieu_glyph(self):
        """Chốt tiền đề của cả bản sửa: các ký tự này thật sự không có trong MỌI font bundle.

        Đọc thẳng bảng `cmap` chứ không đi qua `assert_can_render` — hàm đó nay tự gấp dấu câu
        trước khi kiểm, nên hỏi nó thì không còn thấy được tình trạng THẬT của font nữa.
        """
        from fontTools.ttLib import TTFont

        for family, spec in FONT_REGISTRY.items():
            with TTFont(Path(FONT_DIR) / spec.relative_path, fontNumber=0, lazy=True) as f:
                ma: set[int] = set()
                for bang in f["cmap"].tables:
                    ma |= set(bang.cmap.keys())
            for ky_tu in "．。「，！？（〜・":
                assert ord(ky_tu) not in ma, f"{family} lại CÓ {ky_tu!r} — xem lại bảng gấp"
            for ky_tu in '.,!?()"~·':
                assert ord(ky_tu) in ma, f"{family} thiếu {ky_tu!r} — không dùng làm đích được"

    def test_sau_khi_gap_thi_can_duoc(self, fitter):
        kq = fitter.fit(self.CAU_THAT, BBox(x=0, y=0, w=600, h=400), "Bangers")
        assert kq["fit_status"] == "fit_ok"
        assert "．" not in kq["wrapped_text"]
        assert "Sakamoto-san." in kq["wrapped_text"]

    def test_chu_nhat_that_van_bao_loi(self, fitter):
        """Không được "sửa" bằng cách nuốt luôn chữ Nhật — vùng đó phải kêu lên."""
        with pytest.raises(MissingGlyph):
            fitter.fit("坂本さん", BBox(x=0, y=0, w=600, h=400), "Bangers")
