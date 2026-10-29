"""E15 — test đơn vị cho bộ chuẩn hoá góc và bộ nhận biết hướng chữ."""
from __future__ import annotations

import pytest

cv2 = pytest.importorskip("cv2")
import numpy as np

from app.models.enums import OrientationSource, OrientationStatus, TextOrientation
from app.services.orientation.analyzer import OrientationConfig, RegionOrientationAnalyzer
from app.services.orientation.angle import chuan_hoa_goc, la_doc, la_ngang
from app.services.orientation.decision import LyDo, OrientationDecision


# ---------- chuẩn hoá góc ----------

def _da_giac_o_goc(goc_ve: float, dai=240, ngan=40):
    """Đường bao của một dòng chữ giả, vẽ ở góc biết trước."""
    return cv2.boxPoints(((250.0, 250.0), (float(dai), float(ngan)), float(goc_ve))).tolist()


def _goc_do_duoc(goc_ve: float) -> float:
    img = np.zeros((500, 500), np.uint8)
    cv2.fillPoly(img, [np.array(_da_giac_o_goc(goc_ve), np.int32)], 255)
    c, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    (_, _), (w, h), a = cv2.minAreaRect(c[0])
    return chuan_hoa_goc(w, h, a)


@pytest.mark.parametrize("goc_ve,mong_doi", [(0, 0), (15, 15), (30, 30), (45, 45),
                                             (60, 60), (75, 75), (90, 90), (135, 135)])
def test_chuan_hoa_goc_dung_tren_hinh_biet_truoc(goc_ve, mong_doi):
    assert abs(_goc_do_duoc(goc_ve) - mong_doi) <= 1.5


def test_goc_tho_KHONG_phan_biet_duoc_0_va_90_nhung_da_chuan_hoa_thi_duoc():
    """Chốt chặn quan trọng nhất của E15: hai hình vuông góc cho CÙNG một góc thô.

    Đo thật: hình 0° cho angle=90.0 (w/h đảo), hình 90° cũng cho angle=90.0.
    """
    tho = []
    for goc_ve in (0, 90):
        img = np.zeros((500, 500), np.uint8)
        cv2.fillPoly(img, [np.array(_da_giac_o_goc(goc_ve), np.int32)], 255)
        c, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        (_, _), (w, h), a = cv2.minAreaRect(c[0])
        tho.append(round(a, 1))
    assert tho[0] == tho[1], "tiền đề của test đã đổi — đọc lại TEST_LOG §E15.1"
    assert abs(_goc_do_duoc(0) - 0) <= 1.5
    assert abs(_goc_do_duoc(90) - 90) <= 1.5


def test_gan_180_van_la_nam_ngang():
    assert la_ngang(179.0, 12) and not la_doc(179.0, 12)
    assert la_doc(88.0, 12) and not la_ngang(88.0, 12)


# ---------- bộ nhận biết ----------

def _bd(**kw) -> RegionOrientationAnalyzer:
    return RegionOrientationAnalyzer(OrientationConfig(**kw))


def _dong_ngang(n=3):
    return [_da_giac_o_goc(0) for _ in range(n)]


def _dong_doc(n=3):
    return [_da_giac_o_goc(90) for _ in range(n)]


def test_dong_nam_ngang_thi_ra_chu_ngang():
    d = _bd().analyze(bbox_w=200, bbox_h=80, line_polygons=_dong_ngang())
    assert d.orientation is TextOrientation.horizontal_ltr
    assert d.status is OrientationStatus.ready
    assert LyDo.OCR_LINE_GEOMETRY_HORIZONTAL in d.reason_codes


def test_dong_dung_dung_thi_ra_chu_doc_nhung_CHUA_dung_duoc():
    """Nhận ra hướng không có nghĩa là dựng được chữ theo hướng đó."""
    d = _bd().analyze(bbox_w=60, bbox_h=200, line_polygons=_dong_doc())
    assert d.orientation is TextOrientation.vertical_ttb
    assert d.status is OrientationStatus.unavailable
    assert LyDo.VERTICAL_RENDERER_UNAVAILABLE in d.reason_codes


def test_bat_dung_chu_doc_thi_moi_thanh_ready():
    d = _bd(vertical_render_enabled=True).analyze(
        bbox_w=60, bbox_h=200, line_polygons=_dong_doc())
    assert d.status is OrientationStatus.ready
    assert LyDo.OCR_LINE_GEOMETRY_VERTICAL in d.reason_codes


def test_dong_nghieng_thi_chi_dieu_huong_ra_soat_khong_tu_xoay():
    d = _bd().analyze(bbox_w=200, bbox_h=120,
                      line_polygons=[_da_giac_o_goc(30), _da_giac_o_goc(32)])
    assert d.orientation is TextOrientation.rotated_horizontal
    assert d.status is OrientationStatus.needs_review
    assert LyDo.ROTATED_TEXT_MANUAL_REVIEW_ONLY in d.reason_codes
    assert 25 <= d.rotation_degrees <= 37


def test_cac_dong_cai_nhau_thi_noi_thang_la_mau_thuan():
    d = _bd().analyze(bbox_w=150, bbox_h=150,
                      line_polygons=[_da_giac_o_goc(0), _da_giac_o_goc(90)])
    assert d.orientation is TextOrientation.unknown
    assert LyDo.ORIENTATION_EVIDENCE_CONFLICT in d.reason_codes
    assert d.status is OrientationStatus.needs_review


def test_khong_co_bo_cuc_dong_thi_la_chua_biet_chu_khong_doan_bua():
    """manga-ocr chỉ trả chuỗi. Không có hình học thì câu trả lời trung thực là 'chưa biết'."""
    d = _bd().analyze(bbox_w=60, bbox_h=300, line_polygons=None)
    assert d.orientation is TextOrientation.unknown
    assert LyDo.OCR_LAYOUT_UNAVAILABLE in d.reason_codes
    assert d.source is OrientationSource.fallback_unknown


def test_TI_LE_KHUNG_KHONG_BAO_GIO_TU_QUYET():
    """Khung cao gấp 5 lần bề rộng vẫn KHÔNG được tự thành chữ dọc.

    Một chữ "PHEW!" viết thưa theo chiều dọc vẫn là chữ ngang cách điệu.
    """
    d = _bd().analyze(bbox_w=40, bbox_h=200, line_polygons=None)
    assert d.orientation is not TextOrientation.vertical_ttb
    assert LyDo.BBOX_ASPECT_VERTICAL_SIGNAL in d.reason_codes  # chỉ là tín hiệu


def test_ti_le_khung_khong_lat_nguoc_duoc_bang_chung_hinh_hoc():
    """Khung rất cao NHƯNG các dòng nằm ngang ⇒ vẫn là chữ ngang."""
    d = _bd().analyze(bbox_w=40, bbox_h=300, line_polygons=_dong_ngang())
    assert d.orientation is TextOrientation.horizontal_ltr


def test_sfx_cua_E12_chi_la_ngu_canh_khong_quyet_dinh_huong():
    d = _bd().analyze(bbox_w=200, bbox_h=80, line_polygons=_dong_ngang(),
                      region_relevance="possible_sfx")
    assert d.orientation is TextOrientation.horizontal_ltr
    assert LyDo.POSSIBLE_SFX_FROM_QUALITY_GATE in d.reason_codes


def test_sfx_khong_bao_gio_bi_tu_bo_qua():
    d = _bd().analyze(bbox_w=200, bbox_h=80, line_polygons=None,
                      region_relevance="possible_sfx")
    assert d.status is OrientationStatus.needs_review     # đưa người xem, không tự loại
    assert d.orientation is TextOrientation.unknown


def test_khung_hong_thi_bao_failed():
    d = _bd().analyze(bbox_w=0, bbox_h=100, line_polygons=_dong_ngang())
    assert d.status is OrientationStatus.failed
    assert d.orientation is TextOrientation.unknown


def test_bo_nhan_dien_khong_cho_hinh_hoc_luon_duoc_ghi_lai():
    """Mọi quyết định đều phải ghi rằng bộ nhận diện không cung cấp hình học dòng chữ."""
    d = _bd().analyze(bbox_w=200, bbox_h=80, line_polygons=_dong_ngang())
    assert LyDo.CTD_GEOMETRY_UNAVAILABLE in d.reason_codes


def test_ket_qua_tat_dinh():
    a = _bd().analyze(bbox_w=200, bbox_h=80, line_polygons=_dong_ngang())
    b = _bd().analyze(bbox_w=200, bbox_h=80, line_polygons=_dong_ngang())
    assert a == b


def test_bang_chung_luu_du_goc_tung_dong():
    d = _bd().analyze(bbox_w=200, bbox_h=80, line_polygons=_dong_ngang(2))
    assert d.evidence_snapshot["so_dong"] == 2
    assert len(d.evidence_snapshot["goc_tung_dong"]) == 2


# ---------- ràng buộc ở tầng kiểu dữ liệu ----------

def test_khong_the_tao_chu_doc_ready_ma_khong_co_bang_chung():
    with pytest.raises(ValueError):
        OrientationDecision(
            orientation=TextOrientation.vertical_ttb,
            source=OrientationSource.ocr_layout,
            status=OrientationStatus.ready,
            reason_codes=[LyDo.BBOX_ASPECT_VERTICAL_SIGNAL],
        )


def test_chu_nghieng_phai_kem_goc_va_ghi_ro_khong_tu_xoay():
    with pytest.raises(ValueError):
        OrientationDecision(
            orientation=TextOrientation.rotated_horizontal,
            source=OrientationSource.ocr_layout,
            status=OrientationStatus.needs_review,
            reason_codes=[LyDo.ROTATED_TEXT_MANUAL_REVIEW_ONLY],
        )
    with pytest.raises(ValueError):
        OrientationDecision(
            orientation=TextOrientation.rotated_horizontal,
            source=OrientationSource.ocr_layout,
            status=OrientationStatus.needs_review,
            reason_codes=[LyDo.ROI_ROTATED_TEXT_EVIDENCE],
            rotation_degrees=30.0,
        )


def test_ma_ly_do_la_bi_tu_choi():
    with pytest.raises(ValueError):
        OrientationDecision(
            orientation=TextOrientation.unknown,
            source=OrientationSource.fallback_unknown,
            status=OrientationStatus.needs_review,
            reason_codes=["tu_bia_ra"],
        )
