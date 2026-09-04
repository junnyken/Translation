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

    def test_chi_con_dau_cau_thi_LOAI(self):
        """Đo trên trang thật 04/05: câu 23 ký tự bị trả về đúng một dấu `?`.

        Bộ lọc cũ nhận, vì nó "ngắn hơn bản cũ và không rỗng". Đó không phải rút gọn — đó là
        xoá mất một câu thoại, và người dùng chỉ biết khi mở trang ra nhìn.
        """
        assert phan_tich("1. ?\n2. Cậu nghĩ sao?", self.MUC)[0] is None

    def test_dung_chua_toi_35_phan_tram_SUC_CHUA_thi_LOAI(self):
        """Còn chỗ mà không dùng thì là xoá, không phải rút gọn."""
        assert phan_tich("1. Ừ.\n2. Cậu nghĩ sao?", self.MUC)[0] is None

    def test_bong_bong_TI_HON_van_duoc_rut_that_manh(self):
        """Mốc neo vào SỨC CHỨA, không vào độ dài bản cũ — nếu không thì phạt oan đúng ca cần nhất.

        Bong bóng chứa 12 ký tự mà bản dịch 200 ký tự: rút xuống 12 ký tự là việc phải làm.
        """
        dai = "nghe nói rằng chuyện đó cũng bình thường thôi mà " * 4
        muc = [MucRutGon(chu_goc="a", ban_dich=dai, suc_chua=12)]
        assert phan_tich("1. Nghe nói vậy", muc) == ["Nghe nói vậy"]

    def test_van_nhan_ban_rut_gon_MANH_nhung_con_la_cau(self):
        """Chống sửa quá tay: rút gọn thật sự vẫn phải được nhận."""
        kq = phan_tich("1. Mỗi người mỗi khác!\n2. Cậu nghĩ sao?", self.MUC)
        assert kq[0] == "Mỗi người mỗi khác!"

    def test_danh_roi_TEN_RIENG_thi_LOAI(self):
        """Đo trên trang thật: "Kazudake" biến mất khỏi bản rút gọn dù prompt đã dặn giữ.

        Dặn suông không phải chốt chặn.
        """
        muc = [MucRutGon(chu_goc="a", ban_dich="Tôi nghe Kazudake kể chuyện hồi bé của cô ấy",
                         suc_chua=20)]
        assert phan_tich("1. Nghe bồ cũ kể chuyện xưa", muc) == [None]
        assert phan_tich("1. Nghe Kazudake kể chuyện xưa", muc) == ["Nghe Kazudake kể chuyện xưa"]

    def test_ten_rieng_khong_nham_chu_dau_cau(self):
        from app.services.translate.rut_gon import ten_rieng

        assert ten_rieng("Cậu ổn chứ? Tôi về đây.") == set()
        assert "kazudake" in ten_rieng("Tôi nghe Kazudake kể chuyện.")

    def test_ten_rieng_khong_nham_DAI_TU_viet_hoa_giua_cau(self):
        """Bẫy bắt được lúc chạy test: "Tôi" giữa câu bị coi là tên riêng, và mọi bản rút gọn
        đổi cách xưng hô đều bị loại oan."""
        from app.services.translate.rut_gon import ten_rieng

        assert ten_rieng("Hôm qua Tôi gặp Cậu ở đó, Nhưng Anh không thấy") == set()

    def test_prompt_liet_ke_ten_rieng_phai_giu(self):
        muc = [MucRutGon(chu_goc="a", ban_dich="Tôi nghe Kazudake kể chuyện", suc_chua=20)]
        assert "PHẢI GIỮ NGUYÊN tên riêng: kazudake" in dung_prompt(muc, "ja")

    def test_KHONG_loai_chi_vi_lech_suc_chua_vai_ky_tu(self):
        """Sức chứa là ƯỚC LƯỢNG; `fit()` chạy ngay sau mới là bên có thẩm quyền.

        Loại ở đây là vứt đi một bản dịch ngắn hơn hẳn chỉ vì lệch con số ước lượng.
        """
        kq = phan_tich("1. Mỗi người một khác mà!\n2. Cậu không nghĩ thế à?", self.MUC)
        assert kq[0] is not None and len(kq[0]) > self.MUC[0].suc_chua
