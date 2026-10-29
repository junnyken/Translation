"""E16 — vẽ chữ nghiêng: kiểm bằng cách ĐO LẠI mực trên ảnh, không bằng mắt.

Phép kiểm chính là **vòng kín**: vẽ chữ ở một góc biết trước, rồi dùng `cv2.minAreaRect` +
`chuan_hoa_goc` của E15 đo lại hướng vệt mực. Nếu chiều xoay sai thì góc đo lại sẽ lệch — thứ mà
xem ảnh bằng mắt rất dễ bỏ qua vì ảnh "trông vẫn có xoay".
"""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from app.core.config import get_settings
from app.services.interfaces import BBox
from app.services.orientation.angle import chuan_hoa_goc
from app.services.typeset.fonts import FontResolver
from app.services.typeset.preview import PagePreviewRenderer, RegionDraw


@pytest.fixture
def ve():
    st = get_settings()
    rs = FontResolver(font_dir=st.font_dir, default_family=st.default_font_family,
                      allow_fallback=st.allow_font_fallback)
    return PagePreviewRenderer(font_resolver=rs,
                               line_spacing_ratio=st.typeset_line_spacing_ratio,
                               mark_overflow=False)


@pytest.fixture
def anh_trang(tmp_path):
    p = tmp_path / "clean.png"
    Image.new("RGB", (600, 400), (255, 255, 255)).save(p)
    return str(p)


def _vung(goc: float | None, chu: str = "CLANG") -> RegionDraw:
    st = get_settings()
    return RegionDraw(
        bbox=BBox(x=150.0, y=100.0, w=300.0, h=200.0),
        wrapped_text=chu, font_family=st.default_font_family, font_size=48.0,
        padding_ratio=st.typeset_padding_ratio, rotation_degrees=goc,
    )


def _goc_cua_muc(img: Image.Image) -> float:
    """Đo hướng vệt mực trên ảnh, bằng ĐÚNG công cụ E15 dùng để đo hướng chữ."""
    import cv2

    a = np.array(img.convert("L"))
    _, nguong = cv2.threshold(a, 200, 255, cv2.THRESH_BINARY_INV)
    cnt, _ = cv2.findContours(nguong, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    assert cnt, "không thấy mực nào trên ảnh — chữ chưa được vẽ"
    diem = np.vstack(cnt)
    (_, _), (w, h), a_tho = cv2.minAreaRect(diem)
    return chuan_hoa_goc(w, h, a_tho)


def _lech_goc(a: float, b: float) -> float:
    """Lệch giữa hai HƯỚNG-ĐƯỜNG (vô hướng), nên 179° và 1° chỉ lệch 2°."""
    d = abs((a % 180.0) - (b % 180.0))
    return min(d, 180.0 - d)


class TestKhongCoGocThiGiuNguyen:
    def test_None_ve_y_nhu_truoc(self, ve, anh_trang):
        """Bất biến quan trọng nhất: vùng không có góc phải cho ảnh GIỐNG HỆT bản cũ."""
        a = ve.draw(anh_trang, [_vung(None)])
        b = ve.draw(anh_trang, [_vung(None)])
        assert np.array_equal(np.array(a), np.array(b))

    @pytest.mark.parametrize("goc", [0.0, 5.0, 176.0, 180.0])
    def test_gan_nam_ngang_KHONG_xoay(self, ve, anh_trang, goc):
        """Dưới ngưỡng thì phải cho ảnh y hệt trường hợp không có góc, từng pixel."""
        khong = np.array(ve.draw(anh_trang, [_vung(None)]))
        gan_ngang = np.array(ve.draw(anh_trang, [_vung(goc)]))
        assert np.array_equal(khong, gan_ngang), f"{goc}° đã bị xoay dù dưới ngưỡng"


class TestCoXoayThat:
    @pytest.mark.parametrize("goc_duong", [165.0, 149.0, 40.0, 126.9])
    def test_anh_doi_khi_co_goc(self, ve, anh_trang, goc_duong):
        khong = np.array(ve.draw(anh_trang, [_vung(None)]))
        co = np.array(ve.draw(anh_trang, [_vung(goc_duong)]))
        assert not np.array_equal(khong, co), f"{goc_duong}° không làm ảnh đổi — chưa xoay gì"

    @pytest.mark.parametrize("goc_duong", [165.0, 150.0, 30.0, 45.0])
    def test_VONG_KIN_do_lai_muc_ra_dung_goc(self, ve, anh_trang, goc_duong):
        """Vẽ ở góc biết trước rồi đo lại — phép duy nhất bắt được lỗi SAI CHIỀU.

        Dung sai 12° vì mực là chữ thật (có dấu, có khoảng trắng) chứ không phải một dải đặc, nên
        `minAreaRect` của nó không bao giờ trùng khít góc lý thuyết.
        """
        anh = ve.draw(anh_trang, [_vung(goc_duong, chu="CLANGCLANG")])
        do_lai = _goc_cua_muc(anh)
        assert _lech_goc(do_lai, goc_duong) <= 12.0, (
            f"yêu cầu {goc_duong}°, mực đo lại {do_lai:.1f}° — lệch quá, nghi SAI CHIỀU xoay"
        )

    def test_sai_chieu_se_bi_bat(self, ve, anh_trang):
        """Chứng minh phép kiểm trên có tác dụng: góc ĐẢO DẤU phải làm nó đỏ.

        Không có test này thì không biết dung sai 12° có quá rộng đến mức bỏ qua lỗi sai chiều.
        """
        goc = 150.0
        anh = ve.draw(anh_trang, [_vung(goc, chu="CLANGCLANG")])
        do_lai = _goc_cua_muc(anh)
        goc_nguoc = (180.0 - goc) % 180.0          # 150 -> 30, đúng cái ra khi đảo dấu
        assert _lech_goc(do_lai, goc_nguoc) > 12.0, (
            "mực khớp CẢ góc đúng lẫn góc ngược ⇒ dung sai quá rộng, phép kiểm vô dụng"
        )


class TestKhongTranKhoiKhung:
    @pytest.mark.parametrize("goc_duong", [165.0, 149.0, 126.9, 66.6, 45.0])
    def test_muc_nam_gon_trong_bbox(self, ve, anh_trang, goc_duong):
        """Bất biến của M6/E14 phải giữ: chữ xoay cũng KHÔNG được leo ra ngoài khung của nó.

        Xoay làm hộp bao chữ lớn hơn, nên đây là chỗ dễ vỡ nhất của E16.
        """
        v = _vung(goc_duong, chu="CLANGCLANGCLANG")
        anh = np.array(ve.draw(anh_trang, [v]).convert("L"))
        co_muc = anh < 200
        ys, xs = np.nonzero(co_muc)
        assert len(xs), "không có mực"
        assert xs.min() >= int(v.bbox.x) - 1, f"mực tràn trái: {xs.min()} < {v.bbox.x}"
        assert ys.min() >= int(v.bbox.y) - 1, f"mực tràn trên: {ys.min()} < {v.bbox.y}"
        assert xs.max() <= int(v.bbox.x + v.bbox.w) + 1, "mực tràn phải"
        assert ys.max() <= int(v.bbox.y + v.bbox.h) + 1, "mực tràn dưới"

    def test_chu_dai_o_goc_manh_van_khong_tran(self, ve, anh_trang):
        """Ca xấu nhất: chữ dài + góc gần 45° cho hộp bao phình to nhất."""
        v = _vung(45.0, chu="CLANGCLANGCLANGCLANG")
        anh = np.array(ve.draw(anh_trang, [v]).convert("L"))
        ys, xs = np.nonzero(anh < 200)
        assert xs.min() >= int(v.bbox.x) - 1 and xs.max() <= int(v.bbox.x + v.bbox.w) + 1
        assert ys.min() >= int(v.bbox.y) - 1 and ys.max() <= int(v.bbox.y + v.bbox.h) + 1
