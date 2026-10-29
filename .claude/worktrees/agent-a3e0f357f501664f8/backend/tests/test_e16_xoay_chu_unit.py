"""E16 — phép đổi góc, kiểm trên ĐÚNG 11 góc thật đo được ở lượt 24 trang E23.

Đây là chỗ duy nhất của E16 có thể làm chữ lộn ngược, nên nó được test trước và test kỹ nhất.

`rotation_degrees` của E15 là hướng **cạnh dài** quy về **[0, 180)** — một đường **vô hướng**. Xoay
chữ đúng theo con số đó thì 8/11 vùng thật ra chữ gần như lộn ngược.
"""
from __future__ import annotations

import pytest

from app.services.typeset.xoay import NGUONG_XOAY_DO, goc_xoay_chu, nen_xoay

#: 11 góc LẤY NGUYÊN từ CSDL sau lượt 24 trang (E23), không phải số tự nghĩ ra.
GOC_THAT = [25.0, 66.6, 126.9, 149.0, 158.6, 160.2, 162.2, 165.0, 165.4, 166.0, 166.7]


class TestGocXoayChu:
    @pytest.mark.parametrize(("vao", "ra"), [
        (0.0, 0.0),
        (15.0, 15.0),
        (90.0, 90.0),      # biên: 90 thuộc nửa dưới, giữ nguyên
        (90.1, -89.9),     # ngay sau biên là lật sang âm
        (165.0, -15.0),    # ca THẬT hay gặp nhất
        (179.0, -1.0),     # gần 180 = gần ngang, KHÔNG phải gần dựng đứng
        (180.0, 0.0),      # quy vòng
        (360.0, 0.0),
        (-15.0, -15.0),    # 345 % 180 = 165 -> -15
    ])
    def test_doi_dung(self, vao, ra):
        assert goc_xoay_chu(vao) == pytest.approx(ra)

    @pytest.mark.parametrize("goc", GOC_THAT)
    def test_moi_goc_THAT_deu_ra_trong_khoang_khong_lon_nguoc(self, goc):
        """(-90, 90] là khoảng duy nhất mà chữ không thể bị lộn ngược."""
        ra = goc_xoay_chu(goc)
        assert -90.0 < ra <= 90.0, f"{goc}° -> {ra}° nằm ngoài khoảng an toàn"

    def test_TAM_goc_that_o_149_167_do_phai_thanh_goc_AM_nho(self):
        """Đúng cái bẫy: 8/11 góc thật nằm 149-167°, xoay thẳng theo là lộn ngược.

        Sau khi đổi, chúng phải thành góc âm NHỎ (nghiêng nhẹ), không phải góc lớn.
        """
        gan_180 = [g for g in GOC_THAT if g >= 149.0]
        assert len(gan_180) == 8, "dữ liệu mẫu đã đổi — đọc lại trước khi sửa test"
        for g in gan_180:
            ra = goc_xoay_chu(g)
            assert ra < 0, f"{g}° phải ra góc âm, ra {ra}°"
            assert abs(ra) <= 31.0, f"{g}° -> {ra}°: nghiêng quá mạnh, nghi đổi sai"

    def test_giu_nguyen_huong_duong_khi_quay_ve_180(self):
        """Đổi góc KHÔNG được làm đổi đường: |ra| và góc tới trục ngang phải khớp."""
        for g in GOC_THAT:
            ra = goc_xoay_chu(g)
            tu_truc_ngang = min(g % 180.0, 180.0 - (g % 180.0))
            assert abs(ra) == pytest.approx(tu_truc_ngang, abs=0.01)


class TestNenXoay:
    def test_khong_co_goc_thi_KHONG_xoay(self):
        """Thiếu bằng chứng thì giữ hành vi cũ, không đoán một góc rồi xoay theo."""
        assert nen_xoay(None) is False

    @pytest.mark.parametrize("goc", [0.0, 3.0, 177.0, 180.0, 12.0])
    def test_gan_nam_ngang_thi_KHONG_xoay(self, goc):
        """Xoay vài độ chỉ làm nét chữ răng cưa mà mắt không thấy khác."""
        assert nen_xoay(goc) is False

    @pytest.mark.parametrize("goc", GOC_THAT)
    def test_moi_vung_THAT_deu_dang_xoay(self, goc):
        """Cả 11 vùng thật phải vượt ngưỡng — nếu không thì E16 không phục vụ được ca nào."""
        assert nen_xoay(goc) is True, f"{goc}° bị bỏ qua, E16 sẽ không làm gì cho vùng này"

    def test_nguong_khop_voi_dung_sai_NGANG_cua_E15(self):
        """Hai tầng không được mâu thuẫn: vùng nào E15 gọi là NGANG thì E16 không xoay.

        Test này KHÔNG được `skip`. Bản đầu tra `orientation_horizontal_tolerance_deg` — một tên
        không tồn tại — nên `getattr` trả None, test tự bỏ qua, và nó **đã che mất** việc tôi đặt
        ngưỡng 8.0 trong khi E15 dùng 12.0. Nay đọc thẳng thuộc tính, thiếu là ĐỎ.
        """
        from app.core.config import get_settings

        dung_sai_ngang = get_settings().e15_angle_tolerance_deg
        assert NGUONG_XOAY_DO >= float(dung_sai_ngang), (
            f"ngưỡng xoay {NGUONG_XOAY_DO}° nhỏ hơn dung sai ngang {dung_sai_ngang}° của E15 ⇒ "
            "có vùng E15 gọi là NGANG mà E16 lại xoay"
        )


class TestGocPIL:
    """Chiều xoay — chỗ thứ hai E16 có thể sai âm thầm, và nó ĐƯỢC ĐO chứ không đoán."""

    @pytest.mark.parametrize(("goc_duong", "pil_mong_doi"), [
        (165.0, 15.0),    # ảnh nghiêng +15° (ngược kim đồng hồ) -> PIL phải xoay +15°
        (15.0, -15.0),
        (140.0, 40.0),
        (40.0, -40.0),
        (0.0, 0.0),
    ])
    def test_dao_dau_so_voi_goc_xoay_chu(self, goc_duong, pil_mong_doi):
        from app.services.typeset.xoay import goc_pil

        assert goc_pil(goc_duong) == pytest.approx(pil_mong_doi)

    @pytest.mark.parametrize("goc", GOC_THAT)
    def test_luon_nguoc_dau_voi_goc_xoay_chu(self, goc):
        from app.services.typeset.xoay import goc_pil

        assert goc_pil(goc) == pytest.approx(-goc_xoay_chu(goc))

    def test_dung_chieu_so_voi_cv2_do_lai_duoc(self):
        """Kiểm vòng kín bằng chính cv2: xoay ảnh theo `goc_pil` phải cho lại đúng góc ban đầu.

        Đây là phép kiểm duy nhất chứng minh dấu đúng mà không phải tin lời tôi.
        """
        import cv2
        import numpy as np

        from app.services.orientation.angle import chuan_hoa_goc
        from app.services.typeset.xoay import goc_pil

        for goc_duong in (165.0, 15.0, 140.0, 40.0):
            img = np.zeros((400, 400), np.uint8)
            cv2.rectangle(img, (100, 190), (300, 210), 255, -1)
            # Xoay ảnh bằng ĐÚNG góc ta sẽ truyền cho PIL (cùng quy ước dấu).
            M = cv2.getRotationMatrix2D((200, 200), goc_pil(goc_duong), 1.0)
            xoay = cv2.warpAffine(img, M, (400, 400))
            cnt, _ = cv2.findContours(xoay, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            (_, _), (w, h), a = cv2.minAreaRect(max(cnt, key=cv2.contourArea))
            do_lai = chuan_hoa_goc(w, h, a)
            assert min(abs(do_lai - goc_duong), 180 - abs(do_lai - goc_duong)) < 1.0, (
                f"xoay theo goc_pil({goc_duong}) rồi đo lại ra {do_lai}° — SAI CHIỀU"
            )
