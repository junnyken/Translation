"""E82 — thứ tự đọc theo KHUNG TRANH (cắt XY theo rãnh trắng).

Canh:
1. Tìm đúng khung trên bố cục chuẩn; thứ tự hàng trên→dưới, cột phải→trái (rtl) / trái→phải (ltr).
2. Bố cục làm cách cũ HỎNG (khung cao bên phải, hai khung chồng bên trái): cách cũ đan xen, cách mới
   đọc hết khung phải rồi mới sang trái.
3. Trang không có rãnh (nền tối / tranh tràn lề) ⇒ một khung ⇒ y hệt cách cũ.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.services.translate.khung_tranh import la_theo_thu_tu, tim_khung_tranh
from app.services.translate.reading_order import calculate_reading_order


def _trang(khung, rong=1000, cao=1400):
    """Trang trắng, mỗi khung là hình chữ nhật xám đậm (tranh)."""
    a = np.full((cao, rong), 255, np.uint8)
    for x0, y0, x1, y1 in khung:
        a[y0:y1, x0:x1] = 90
    return a


@dataclass
class V:
    ten: str
    bbox_x: float
    bbox_y: float
    bbox_w: float = 80
    bbox_h: float = 60


def test_bo_cuc_chuan_ba_khung():
    a = _trang([(40, 40, 960, 600), (40, 640, 480, 1360), (520, 640, 960, 1360)])
    la = la_theo_thu_tu(tim_khung_tranh(a), rtl=False)
    assert len(la) == 3
    assert [round(k.x0 / 100) for k in la] == [0, 0, 5]
    la_rtl = la_theo_thu_tu(tim_khung_tranh(a), rtl=True)
    assert la_rtl[1].x0 > la_rtl[2].x0, "rtl: khung bên PHẢI đọc trước"


def test_khung_cao_ben_phai_cach_cu_dan_xen_cach_moi_dung():
    # phải: một khung cao suốt trang; trái: hai khung chồng nhau
    a = _trang([(560, 40, 960, 1360), (40, 40, 520, 680), (40, 720, 520, 1360)])
    vung = [
        V("phai_tren", 700, 100), V("phai_duoi", 700, 900),
        V("trai_tren", 200, 120), V("trai_duoi", 200, 920),
    ]
    cu = [v.ten for v in calculate_reading_order(vung, "ja")]
    assert cu == ["phai_tren", "trai_tren", "phai_duoi", "trai_duoi"], "cách cũ đan xen theo độ cao"
    la = la_theo_thu_tu(tim_khung_tranh(a), rtl=True)
    moi = [v.ten for v in calculate_reading_order(vung, "ja", khung_tranh=la)]
    assert moi == ["phai_tren", "phai_duoi", "trai_tren", "trai_duoi"]


def test_trang_khong_co_ranh_thi_y_nhu_cu():
    a = np.full((1400, 1000), 40, np.uint8)  # nền tối, không rãnh trắng
    la = la_theo_thu_tu(tim_khung_tranh(a), rtl=True)
    assert len(la) == 1
    vung = [V("a", 700, 100), V("b", 200, 120), V("c", 700, 900)]
    assert calculate_reading_order(vung, "ja", khung_tranh=la) == calculate_reading_order(vung, "ja")


def test_bong_bong_tran_qua_ranh_gan_vao_khung_gan_nhat():
    a = _trang([(40, 40, 960, 600), (40, 640, 960, 1360)])
    la = la_theo_thu_tu(tim_khung_tranh(a), rtl=False)
    vung = [V("duoi", 400, 900), V("tren_tran", 400, 590, bbox_h=30)]  # tâm nằm trên rãnh
    assert [v.ten for v in calculate_reading_order(vung, "en", khung_tranh=la)] == ["tren_tran", "duoi"]


def test_tat_co_thi_khong_tim_khung(monkeypatch):
    from app.workers import tasks

    monkeypatch.setattr(tasks.settings, "e82_thu_tu_theo_khung", False)
    assert tasks._khung_tranh_cua_trang("khong/ton/tai.png", "ja") is None


def test_loi_doc_anh_thi_none_khong_lam_hong_luot_dich():
    from app.workers import tasks

    assert tasks._khung_tranh_cua_trang("khong/ton/tai.png", "ja") is None
