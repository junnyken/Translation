"""E14 — test đơn vị cho bộ trích hình và lớp đặt chữ.

Dùng hình TỔNG HỢP có đáp án biết trước (elip, chữ nhật, nền trắng lớn), vì trên hình tổng hợp
mới nói được "đúng/sai" chứ không phải "trông có vẻ ổn".
"""
from __future__ import annotations

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from app.core.config import get_settings
from app.models.enums import SafeAreaSource, SafeAreaStatus
from app.services.interfaces import BBox
from app.services.safearea.config import SafeAreaConfig
from app.services.safearea.decision import ReasonCode
from app.services.safearea.extractor import BubbleSafeAreaExtractor, tinh_roi
from app.services.safearea.layout import chu_nam_gon_trong, o_dat_chu, o_noi_tiep_trong_da_giac


def cfg(**thay) -> SafeAreaConfig:
    goc = SafeAreaConfig.from_settings(get_settings())
    return SafeAreaConfig(**{**goc.snapshot(), **thay})


def trang_toi(w=800, h=600, mau=(40, 60, 40)) -> np.ndarray:
    return np.full((h, w, 3), mau, np.uint8)


def ve_elip(anh, cx, cy, rx, ry, mau=(245, 245, 245)):
    cv2.ellipse(anh, (cx, cy), (rx, ry), 0, 0, 360, mau, -1)
    return anh


def luu(tmp_path, anh, ten="clean.png") -> str:
    p = tmp_path / ten
    cv2.imwrite(str(p), anh)
    return str(p)


# ---------- ROI ----------

def test_roi_nới_theo_bội_của_bbox_và_kẹp_vào_biên_ảnh():
    c = cfg(roi_expand_ratio=1.0, roi_expand_max_px=1000)
    assert tinh_roi(BBox(x=100, y=100, w=50, h=40), 800, 600, c) == (50, 60, 150, 120)
    # Sát mép trái/trên: kẹp về 0, KHÔNG cho toạ độ âm.
    assert tinh_roi(BBox(x=5, y=5, w=50, h=40), 800, 600, c)[:2] == (0, 0)


def test_roi_khong_bao_gio_vuot_ra_ngoai_anh():
    c = cfg(roi_expand_ratio=10.0, roi_expand_max_px=100000)
    rx, ry, rw, rh = tinh_roi(BBox(x=700, y=500, w=90, h=90), 800, 600, c)
    assert rx >= 0 and ry >= 0 and rx + rw <= 800 and ry + rh <= 600


# ---------- nhận hình ----------

def test_elip_sang_tren_nen_toi_thi_nhan_ra_hinh(tmp_path):
    anh = ve_elip(trang_toi(), 400, 300, 150, 90)
    qd = BubbleSafeAreaExtractor().extract(
        luu(tmp_path, anh), BBox(x=340, y=280, w=120, h=40), (800, 600), cfg()
    )
    assert qd.source is SafeAreaSource.shape_derived
    assert qd.status is SafeAreaStatus.ready
    assert qd.reason_codes == [ReasonCode.SHAPE_CANDIDATE_FOUND]
    assert len(qd.geometry["polygon"]) >= 3
    assert qd.safe_area_pixels and qd.safe_area_pixels > 0


def test_ket_qua_tat_dinh_chay_lai_ra_y_het(tmp_path):
    anh = ve_elip(trang_toi(), 400, 300, 150, 90)
    p = luu(tmp_path, anh)
    b = BBox(x=340, y=280, w=120, h=40)
    a = BubbleSafeAreaExtractor().extract(p, b, (800, 600), cfg())
    c2 = BubbleSafeAreaExtractor().extract(p, b, (800, 600), cfg())
    assert a.geometry == c2.geometry and a.status is c2.status


def test_khong_chon_nen_trang_lon_khong_chua_tam_bbox(tmp_path):
    """Cái bẫy nguy hiểm nhất: vơ lấy 'vùng trắng lớn nhất' trong ROI."""
    anh = trang_toi()
    anh[0:200, 0:800] = (250, 250, 250)          # dải trắng lớn ở TRÊN
    qd = BubbleSafeAreaExtractor().extract(
        luu(tmp_path, anh), BBox(x=350, y=400, w=100, h=60), (800, 600), cfg()
    )
    assert qd.source is SafeAreaSource.fallback_rectangle
    assert ReasonCode.SHAPE_CANDIDATE_NOT_CENTERED in qd.reason_codes


def test_ung_vien_chiem_gan_het_roi_thi_bi_loai(tmp_path):
    anh = np.full((600, 800, 3), 250, np.uint8)   # cả trang trắng
    qd = BubbleSafeAreaExtractor().extract(
        luu(tmp_path, anh), BBox(x=350, y=280, w=100, h=60), (800, 600), cfg()
    )
    assert qd.source is SafeAreaSource.fallback_rectangle
    assert (ReasonCode.SHAPE_CANDIDATE_FILLS_ROI in qd.reason_codes
            or ReasonCode.SHAPE_CANDIDATE_TOUCHES_ROI_BOUNDARY in qd.reason_codes)


def test_bong_bong_bi_cat_o_mep_roi_thi_khong_nhan_bua(tmp_path):
    c = cfg(roi_expand_ratio=0.2, roi_expand_max_px=20)
    anh = ve_elip(trang_toi(), 400, 300, 200, 150)
    qd = BubbleSafeAreaExtractor().extract(
        luu(tmp_path, anh), BBox(x=360, y=285, w=80, h=30), (800, 600), c
    )
    assert qd.source is SafeAreaSource.fallback_rectangle
    assert ReasonCode.SHAPE_CANDIDATE_TOUCHES_ROI_BOUNDARY in qd.reason_codes


def test_khong_co_diem_sang_nao_thi_bao_thieu_tuong_phan(tmp_path):
    qd = BubbleSafeAreaExtractor().extract(
        luu(tmp_path, trang_toi()), BBox(x=350, y=280, w=100, h=60), (800, 600), cfg()
    )
    assert qd.source is SafeAreaSource.fallback_rectangle
    assert ReasonCode.SHAPE_LOW_CONTRAST in qd.reason_codes


def test_an_vao_lam_mat_het_thi_lui_ve_du_phong(tmp_path):
    c = cfg(erosion_margin_ratio=5.0, erosion_margin_max_px=400, erosion_margin_min_px=200)
    anh = ve_elip(trang_toi(), 400, 300, 150, 90)
    qd = BubbleSafeAreaExtractor().extract(
        luu(tmp_path, anh), BBox(x=340, y=280, w=120, h=40), (800, 600), c
    )
    assert qd.source is SafeAreaSource.fallback_rectangle


def test_bbox_hong_thi_bao_failed_chu_khong_dung_khung_gia(tmp_path):
    anh = ve_elip(trang_toi(), 400, 300, 150, 90)
    qd = BubbleSafeAreaExtractor().extract(
        luu(tmp_path, anh), BBox(x=-10, y=0, w=100, h=50), (800, 600), cfg()
    )
    assert qd.status is SafeAreaStatus.failed
    assert ReasonCode.SHAPE_INVALID_GEOMETRY in qd.reason_codes


def test_khong_doc_duoc_anh_thi_failed(tmp_path):
    qd = BubbleSafeAreaExtractor().extract(
        str(tmp_path / "khong-co.png"), BBox(x=10, y=10, w=50, h=50), (800, 600), cfg()
    )
    assert qd.status is SafeAreaStatus.failed


def test_so_dinh_da_giac_bi_kep_theo_cau_hinh(tmp_path):
    c = cfg(max_polygon_vertices=8)
    anh = ve_elip(trang_toi(), 400, 300, 180, 120)
    qd = BubbleSafeAreaExtractor().extract(
        luu(tmp_path, anh), BBox(x=350, y=285, w=100, h=30), (800, 600), c
    )
    if qd.source is SafeAreaSource.shape_derived:
        assert len(qd.geometry["polygon"]) <= 8


def test_moi_dinh_da_giac_nam_trong_anh(tmp_path):
    anh = ve_elip(trang_toi(), 400, 300, 150, 90)
    qd = BubbleSafeAreaExtractor().extract(
        luu(tmp_path, anh), BBox(x=340, y=280, w=120, h=40), (800, 600), cfg()
    )
    for x, y in qd.geometry["polygon"]:
        assert 0 <= x <= 800 and 0 <= y <= 600


def test_bat_bien_theo_do_phan_giai(tmp_path):
    """Cùng cảnh, phóng to 2 lần, phải ra CÙNG quyết định — tham số không được là px cố định."""
    nho = ve_elip(trang_toi(400, 300), 200, 150, 75, 45)
    to = ve_elip(trang_toi(800, 600), 400, 300, 150, 90)
    a = BubbleSafeAreaExtractor().extract(
        luu(tmp_path, nho, "n.png"), BBox(x=170, y=140, w=60, h=20), (400, 300), cfg()
    )
    b = BubbleSafeAreaExtractor().extract(
        luu(tmp_path, to, "t.png"), BBox(x=340, y=280, w=120, h=40), (800, 600), cfg()
    )
    assert a.status is b.status and a.source is b.source


# ---------- ô đặt chữ ----------

def elip_diem(cx=100.0, cy=60.0, rx=80.0, ry=40.0, n=48):
    return [[cx + rx * float(np.cos(t)), cy + ry * float(np.sin(t))]
            for t in np.linspace(0, 2 * np.pi, n, endpoint=False)]


def test_o_noi_tiep_nam_gon_trong_da_giac():
    dg = elip_diem()
    o = o_noi_tiep_trong_da_giac(dg)
    assert o is not None
    assert chu_nam_gon_trong(dg, (o.x, o.y, o.w, o.h))


def test_o_to_hon_bi_phat_hien_la_tho_ra_ngoai():
    dg = elip_diem()
    o = o_noi_tiep_trong_da_giac(dg)
    assert not chu_nam_gon_trong(dg, (o.x - 15, o.y - 15, o.w + 30, o.h + 30))


def test_kiem_ca_o_chu_chu_khong_phai_moi_diem_neo():
    """Điểm neo nằm trong mà cả khối chữ vẫn thò ra — đúng kiểu lỗi M6 từng mắc."""
    dg = elip_diem()
    o = o_noi_tiep_trong_da_giac(dg)
    neo_x, neo_y = o.x + 2, o.y + 2                      # điểm neo chắc chắn nằm trong
    assert chu_nam_gon_trong(dg, (neo_x, neo_y, 1, 1))   # chỉ điểm neo: lọt
    assert not chu_nam_gon_trong(dg, (neo_x, neo_y, 400, 300))  # cả khối: bị bắt


def test_o_dat_chu_tat_dinh():
    dg = elip_diem()
    a = o_noi_tiep_trong_da_giac(dg)
    b = o_noi_tiep_trong_da_giac(dg)
    assert (a.x, a.y, a.w, a.h) == (b.x, b.y, b.w, b.h)


def test_hinh_chu_nhat_du_phong_dung_thang_lam_o_dat_chu():
    o = o_dat_chu({"rect": {"x": 10.0, "y": 20.0, "w": 100.0, "h": 50.0}})
    assert (o.x, o.y, o.w, o.h) == (10.0, 20.0, 100.0, 50.0)


def test_da_giac_hong_thi_khong_tra_o_bua():
    assert o_noi_tiep_trong_da_giac([]) is None
    assert o_noi_tiep_trong_da_giac([[0, 0], [1, 1]]) is None


def test_khong_co_da_giac_thi_coi_nhu_khong_rang_buoc():
    """Vùng dự phòng không có đa giác — không được vì thế mà báo 'thò ra ngoài'."""
    assert chu_nam_gon_trong(None, (0, 0, 999, 999))


# ---------- hồi quy với M6 ----------

def test_khung_du_phong_cho_dung_vung_chu_nhu_M6():
    """Vùng E14 không nhận diện được thì bố cục phải Y HỆT trước khi có E14.

    Đo thật đã bắt được lệch này: dùng lề ăn-vào của E14 cho khung dự phòng làm cỡ chữ một
    dòng bản quyền nhảy 14 → 16, tức đổi bố cục ở chỗ E14 không hề nhận ra hình gì.
    """
    from app.services.typeset.fitter import FitToBoxTypesetter
    from app.services.safearea.extractor import khung_du_phong

    st = get_settings()
    b = BBox(x=100, y=200, w=507, h=56)
    r = khung_du_phong(b, cfg(), []).geometry["rect"]

    # vùng chữ của M6 = bbox trừ padding hai bên
    lop = FitToBoxTypesetter.__new__(FitToBoxTypesetter)
    lop.padding_ratio = st.typeset_padding_ratio
    m6 = lop.content_rect(b)
    assert int(r["w"]) == m6.width and int(r["h"]) == m6.height


def test_le_an_vao_chi_ap_cho_hinh_suy_ra_khong_ap_cho_du_phong():
    c = cfg(erosion_margin_ratio=0.5, erosion_margin_min_px=50, erosion_margin_max_px=100)
    from app.services.safearea.extractor import khung_du_phong

    r = khung_du_phong(BBox(x=0, y=0, w=400, h=200), c, []).geometry["rect"]
    # Lề ăn-vào cực lớn KHÔNG được đụng tới khung dự phòng.
    assert r["w"] > 300 and r["h"] > 150
