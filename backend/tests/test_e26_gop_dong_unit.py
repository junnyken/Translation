"""E26-A — gộp dòng trước khi dịch. Ca kiểm lấy từ CHỮ THẬT trên trang thật.

Dấu xuống dòng trong `raw_text` là chỗ bong bóng ngắt chữ, không mang nghĩa — nhưng Google
Translate coi mỗi dòng là một câu riêng nên câu bị cắt rời thành vô nghĩa.
"""
from __future__ import annotations

import pytest

from app.services.translate.gop_dong import gop_dong_de_dich


class TestGopDongBiBongBongNgat:
    """Lấy nguyên từ `en_E12P01` và `ja_E12P01` (Pepper&Carrot) trong lượt đo 2026-09-11."""

    @pytest.mark.parametrize(("vao", "ra"), [
        ("... to name just\na few!", "... to name just a few!"),
        ("I need to go to the\nmarket in Komona.", "I need to go to the market in Komona."),
        ("Yeah, I know:", "Yeah, I know:"),
        ('"A-true-witch-of-Chaosah-wouldn\'t-create\nthese-kinds-of-potions".',
         '"A-true-witch-of-Chaosah-wouldn\'t-create these-kinds-of-potions".'),
    ])
    def test_chu_that_duoc_gop(self, vao, ra):
        assert gop_dong_de_dich(vao) == ra

    def test_cau_dai_nhieu_dong_gop_thanh_mot(self):
        vao = ("Make all this disappear\nwhile I'm gone;\nit wouldn't be good for\n"
               "little jokers to find it")
        # `;` là dấu kết câu nên GIỮ ranh giới ở đó, phần còn lại gộp.
        assert gop_dong_de_dich(vao) == (
            "Make all this disappear while I'm gone;\nit wouldn't be good for little jokers to find it"
        )


class TestGiuRanhGioiCauThat:
    """Gộp cả ranh giới câu thì hai câu rời dính thành một, bộ dịch mất chỗ chấm câu."""

    @pytest.mark.parametrize("vao", [
        "Exactly.\nAs well it should be.",
        "Xong rồi!\nĐi thôi.",
        "Thật à?\nTôi không tin.",
        "そうですね。\n行きましょう。",
    ])
    def test_dong_ket_thuc_bang_dau_cau_thi_GIU_xuong_dong(self, vao):
        assert gop_dong_de_dich(vao) == vao

    def test_dau_full_width_cung_duoc_coi_la_ket_cau(self):
        assert gop_dong_de_dich("笑い薬！\n超毛生え薬") == "笑い薬！\n超毛生え薬"


class TestKhongLamHong:
    @pytest.mark.parametrize("vao", ["", "một dòng thôi", "không có xuống dòng nào"])
    def test_khong_co_xuong_dong_thi_giu_nguyen(self, vao):
        assert gop_dong_de_dich(vao) == vao

    def test_chuoi_rong_va_None_khong_no(self):
        assert gop_dong_de_dich("") == ""
        assert gop_dong_de_dich(None) == ""

    def test_dong_trong_bi_bo(self):
        assert gop_dong_de_dich("a\n\nb") == "a b"

    def test_khoang_trang_thua_bi_gom(self):
        assert gop_dong_de_dich("to name   just\n  a few!") == "to name just a few!"

    def test_KHONG_noi_lien_chu_latin(self):
        """Nối liền không dấu cách sẽ tạo từ không tồn tại (`justa`) — hỏng nghĩa."""
        ra = gop_dong_de_dich("to name just\na few")
        assert "justa" not in ra
        assert ra == "to name just a few"


class TestTiengNhat:
    """Tiếng Nhật không cần dấu cách, nhưng thêm dấu cách là VÔ HẠI còn nối liền Latin thì hỏng.

    Sai một chiều vô hại, sai chiều kia hỏng nghĩa ⇒ chọn chiều vô hại.
    """

    def test_gop_co_them_dau_cach(self):
        assert gop_dong_de_dich("私はコモナの\n市場に行かねばならぬ") == "私はコモナの 市場に行かねばならぬ"
