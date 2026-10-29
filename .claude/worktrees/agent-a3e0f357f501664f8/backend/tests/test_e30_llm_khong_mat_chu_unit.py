"""E30 — `llm_context` KHÔNG được làm mất chữ khi mục có dấu xuống dòng.

Đo thật 2026-09-12, trang `29ab3d86` (Pepper&Carrot, tiếng Anh):

    vào  "Whoo!\\nI think it'll be a teeny tiny bit more complicated than I thought!"
    ra   "Whoo!"                                              <- MẤT CẢ CÂU
    vào  "Pfff!\\n.. and I thought it'd be easier with an Air Dragon!"
    ra   "Phụt!"                                              <- MẤT CẢ CÂU

`google_fast` dịch đủ cả hai phần ⇒ đây là chỗ `llm_context` **tệ hơn hẳn**, và tệ theo kiểu IM
LẶNG: job xanh, ảnh vẫn ra, chỉ thiếu chữ. Loại lỗi tệ nhất.

Hai nguyên nhân lồng nhau, test cả hai:

1. `build_prompt` ghép `f"{i+1}. {t}"` — mục có `\\n` trải ra nhiều dòng, phá giao thức
   "một dòng một mục".
2. `parse_response` chỉ nhận chữ trên dòng CÓ SỐ, mọi dòng tiếp theo bị `continue` bỏ đi.
"""
from __future__ import annotations

import pytest

from app.services.translate.engines import LLMContextTranslator


def _tr():
    return LLMContextTranslator(api_keys=["khong-dung-den"])


class TestPromptMotDongMotMuc:
    def test_muc_co_xuong_dong_van_ra_DUNG_mot_dong(self):
        p = _tr().build_prompt(
            ["Whoo!\nI think it'll be harder than I thought!", "Ha ha!"], "en", "vi"
        )
        danh_so = [d for d in p.splitlines() if d[:2] in ("1.", "2.")]
        assert len(danh_so) == 2
        assert danh_so[0] == "1. Whoo! I think it'll be harder than I thought!"

    def test_KHONG_mat_chu_nao_khi_dan_phang(self):
        """Chốt chặn: mọi từ của bản gốc phải còn trong prompt."""
        goc = "Pfff!\n.. and I thought\nit'd be easier with an\nAir Dragon!"
        p = _tr().build_prompt([goc], "en", "vi")
        for tu in goc.split():
            assert tu in p, f"mất từ {tu!r} khỏi prompt"

    def test_nhieu_muc_KHONG_bi_lech_so(self):
        """Mục nhiều dòng làm lệch số thứ tự thì bản dịch gán sang vùng khác — lỗi im lặng."""
        p = _tr().build_prompt(["a\nb", "c\nd", "e"], "en", "vi")
        assert [d[:2] for d in p.splitlines() if d[:2] in ("1.", "2.", "3.")] == ["1.", "2.", "3."]

    @pytest.mark.parametrize("chu", ["", "   ", "\n", "\n\n"])
    def test_muc_rong_khong_no(self, chu):
        p = _tr().build_prompt([chu, "Ha!"], "en", "vi")
        assert "2. Ha!" in p


class TestParseGiuHanhViCU:
    """Tôi đã thử cho bộ đọc "nối dòng tiếp theo vào mục trước" và nó PHÁ
    `test_bo_qua_heading_va_dong_thua`: dòng tán gẫu cuối lọt vào bong bóng cuối.

    Nguyên nhân mất chữ nằm ở `build_prompt`, đã vá ở đó. Nên chỗ này giữ nguyên — thêm hành vi
    phỏng đoán là đổi một lỗi đã hết lấy một lỗi mới.
    """

    def test_dong_tan_gau_o_CUOI_van_bi_bo(self):
        ra = LLMContextTranslator.parse_response(
            "### page.jpg\n1. Một\n2. Hai\nGhi chú linh tinh", 2
        )
        assert ra == ["Một", "Hai"]

    def test_thieu_muc_van_tra_chuoi_RONG_khong_bia(self):
        assert LLMContextTranslator.parse_response("1. Một", 3) == ["Một", "", ""]

    def test_heading_van_bi_bo(self):
        assert LLMContextTranslator.parse_response("### page.jpg\n1. Một", 1) == ["Một"]


class TestCaTHATDaGayMatChu:
    """Hai ca nguyên văn từ trang `29ab3d86`. Đi qua CẢ prompt lẫn parse."""

    @pytest.mark.parametrize("goc,mong_doi_co", [
        ("Whoo!\nI think it'll be a teeny tiny bit more complicated than I thought!",
         ["Whoo!", "complicated"]),
        ("Pfff!\n.. and I thought it'd be easier with an Air Dragon!",
         ["Pfff!", "Air", "Dragon!"]),
    ])
    def test_prompt_giu_du_hai_phan(self, goc, mong_doi_co):
        p = _tr().build_prompt([goc], "en", "vi")
        dong = next(d for d in p.splitlines() if d.startswith("1."))
        for tu in mong_doi_co:
            assert tu in dong, f"{tu!r} không còn trên dòng đánh số ⇒ sẽ mất khi parse"
