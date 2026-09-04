"""Unit — đo sức chứa bong bóng và rút gọn bản dịch cho vừa (E18).

## Vì sao có mini-spec này

Đo trên trang manga thật 04/09, sau khi đã nới khung hết cỡ (A1): vẫn còn 2/8 vùng tràn. Nhìn
kỹ thì khung đã trùm gần hết bong bóng — vấn đề không còn ở hình học nữa mà ở **độ dài bản
dịch**: một bong bóng vẽ vừa ~30 ký tự tiếng Nhật nhận về bản dịch tiếng Việt **105 ký tự**.

Tới đó thì không cách xếp chữ nào cứu được. Chỗ duy nhất còn sửa được là chính bản dịch.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.services.interfaces import BBox
from app.services.translate.rut_gon import MucRutGon, dung_prompt, phan_tich
from app.services.typeset.fitter import FitToBoxTypesetter
from app.services.typeset.fonts import FontResolver
from app.services.typeset.suc_chua import co_chu_muc_tieu, suc_chua_khung

FONT_DIR = os.environ.get("FONT_DIR") or str(Path(__file__).resolve().parents[1] / "fonts")


@pytest.fixture
def resolver() -> FontResolver:
    return FontResolver(FONT_DIR, "Bangers")


class TestCoChuMucTieu:
    def test_ty_le_0_la_co_nho_nhat_1_la_lon_nhat(self):
        assert co_chu_muc_tieu(10, 28, 0.0) == 10
        assert co_chu_muc_tieu(10, 28, 1.0) == 28

    def test_giua_dai(self):
        assert co_chu_muc_tieu(10, 28, 0.5) == 19

    def test_ty_le_ngoai_khoang_bi_kep_lai(self):
        assert co_chu_muc_tieu(10, 28, -5) == 10
        assert co_chu_muc_tieu(10, 28, 9) == 28


class TestSucChua:
    def test_khung_to_hon_thi_chua_duoc_nhieu_hon(self, resolver):
        nho = suc_chua_khung(120, 160, resolver, "Bangers", 19, 0.18)
        to = suc_chua_khung(240, 320, resolver, "Bangers", 19, 0.18)
        assert to.so_ky_tu > nho.so_ky_tu * 3

    def test_co_chu_lon_hon_thi_chua_duoc_it_hon(self, resolver):
        be = suc_chua_khung(200, 240, resolver, "Bangers", 12, 0.18)
        lon = suc_chua_khung(200, 240, resolver, "Bangers", 26, 0.18)
        assert lon.so_ky_tu < be.so_ky_tu

    def test_khung_ti_hon_van_tra_it_nhat_1(self, resolver):
        assert suc_chua_khung(3, 3, resolver, "Bangers", 19, 0.18).so_ky_tu >= 1

    def test_tat_dinh(self, resolver):
        a = suc_chua_khung(200, 240, resolver, "Bangers", 19, 0.18)
        b = suc_chua_khung(200, 240, resolver, "Bangers", 19, 0.18)
        assert a == b

    @pytest.mark.parametrize(("w", "h"), [(120, 160), (200, 240), (232, 320), (90, 120)])
    def test_uoc_luong_doi_chieu_voi_phep_CAN_CHU_THAT(self, resolver, w, h):
        """Ước lượng phải dùng được thật: cắt câu về đúng sức chứa thì `fit()` phải nói VỪA.

        Đây là chỗ dễ tự lừa nhất của cả mini-spec — một con số sức chứa đẹp mà chữ vẫn tràn thì
        vô dụng. Nên đối chiếu thẳng với bộ căn chữ của M6, bên duy nhất có thẩm quyền.
        """
        cau = ("Tôi nghe nói rằng cô gái tôi từng thích Kazudake đã kể về những chuyến "
               "phiêu lưu thời thơ ấu của cô ấy, thật không thể tin được đúng không")
        sc = suc_chua_khung(w, h, resolver, "Bangers", co_chu_muc_tieu(10, 28, 0.5), 0.18)
        chu = cau[:sc.so_ky_tu].rsplit(" ", 1)[0]
        kq = FitToBoxTypesetter(resolver, 10, 28, 0.09, 0.18).fit(
            chu, BBox(x=0, y=0, w=w, h=h), "Bangers")
        assert kq["fit_status"] == "fit_ok", (
            f"khung {w}×{h}: ước lượng {sc.so_ky_tu} ký tự nhưng {len(chu)} ký tự vẫn tràn")


class TestPrompt:
    MUC = [
        MucRutGon(chu_goc="そんなん人それぞれだろ！", ban_dich="Điều đó khác nhau ở mỗi người!", suc_chua=20),
        MucRutGon(chu_goc="だって思わない？", ban_dich="Nhưng cậu không nghĩ vậy à?", suc_chua=15),
    ]

    def test_prompt_noi_ro_so_ky_tu_toi_da_cua_TUNG_muc(self):
        p = dung_prompt(self.MUC, "ja")
        assert "tối đa 20 ký tự" in p and "tối đa 15 ký tự" in p

    def test_prompt_dua_ca_CHU_GOC_vao(self):
        """Không có chữ gốc thì model chỉ còn cách cắt cụt câu tiếng Việt — mất nghĩa mà vẫn sai."""
        p = dung_prompt(self.MUC, "ja")
        assert "そんなん人それぞれだろ！" in p

    def test_prompt_cam_bo_mat_thong_tin_chinh(self):
        p = dung_prompt(self.MUC, "ja")
        assert "KHÔNG được bỏ mất thông tin chính" in p


class TestPhanTich:
    MUC = [
        MucRutGon(chu_goc="a", ban_dich="Điều đó khác nhau ở mỗi người!", suc_chua=20),
        MucRutGon(chu_goc="b", ban_dich="Nhưng cậu không nghĩ vậy à?", suc_chua=15),
    ]

    def test_lay_dung_tung_dong_theo_so(self):
        assert phan_tich("1. Mỗi người mỗi khác!\n2. Cậu không nghĩ vậy à?", self.MUC) == [
            "Mỗi người mỗi khác!", "Cậu không nghĩ vậy à?",
        ]

    def test_dong_DAI_HON_ban_cu_bi_loai(self):
        """Model viết dài thêm thì rút gọn không còn nghĩa gì — giữ bản cũ."""
        kq = phan_tich("1. Điều đó thì khác nhau ở mỗi một người rồi!\n2. Cậu nghĩ sao?", self.MUC)
        assert kq[0] is None and kq[1] == "Cậu nghĩ sao?"

    def test_thieu_dong_thi_giu_ban_cu_chu_khong_bia(self):
        assert phan_tich("1. Mỗi người mỗi khác!", self.MUC) == ["Mỗi người mỗi khác!", None]

    def test_dong_rong_bi_loai(self):
        assert phan_tich("1. \n2. Cậu nghĩ sao?", self.MUC) == [None, "Cậu nghĩ sao?"]

    def test_phan_hoi_rac_thi_khong_doi_gi(self):
        assert phan_tich("xin lỗi tôi không hiểu yêu cầu", self.MUC) == [None, None]

    def test_KHONG_loai_chi_vi_lech_suc_chua_vai_ky_tu(self):
        """Sức chứa là ƯỚC LƯỢNG; `fit()` chạy ngay sau mới là bên có thẩm quyền.

        Loại ở đây là vứt đi một bản dịch ngắn hơn hẳn chỉ vì lệch con số ước lượng.
        """
        kq = phan_tich("1. Mỗi người một khác mà!\n2. Cậu không nghĩ thế à?", self.MUC)
        assert kq[0] is not None and len(kq[0]) > self.MUC[0].suc_chua
