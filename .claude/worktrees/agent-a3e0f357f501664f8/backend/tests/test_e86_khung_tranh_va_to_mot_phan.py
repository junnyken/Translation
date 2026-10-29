"""E86 — (1) ô đặt chữ kẹp trong khung tranh; (2) tô phẳng từng phần khi dải viền lẫn nền khác.

Đo thật ja_E12P01 (khung Gemini, production 16-10-2026):
- "私はコモナの市場に…" bong bóng chạm mép trên khung tranh ⇒ ô nới tràn ra lề trắng ⇒ chữ vẽ ra
  ngoài khung; "私がいない間に…" tràn xuống dưới đáy trang.
- "その通り…" bong bóng trắng KHÔNG viền trên nền trời, khung chữ sát mép ⇒ dải viền lẫn màu trời
  ⇒ rơi về LaMa ⇒ vệt xanh trong bong bóng.
"""
from __future__ import annotations

import numpy as np

from app.services.inpaint.to_phang import to_phang
from app.services.interfaces import BBox
from app.services.safearea.khong_de_len_nhau import kep_trong_khung_tranh

TRANH = [(0, 16, 1200, 910), (0, 943, 1200, 1271), (609, 1303, 1152, 1611), (50, 1303, 592, 1611)]


def test_o_tran_ra_le_bi_kep_ve_khung_tranh():
    khung = {"a": (620.0, 1318.0, 193.0, 46.0)}
    o = {"a": (590.0, 1262.0, 260.0, 110.0)}  # nới lên lề trắng y<1303 và sang trái x<609
    ra = kep_trong_khung_tranh(o, khung, TRANH)["a"]
    assert ra[1] == 1303 and ra[0] == 609
    assert ra[0] <= 620 and ra[1] + ra[3] >= 1364, "vẫn giữ trọn khung chữ"


def test_bong_bong_co_y_tran_qua_mep_khung_thi_khong_kep_canh_do():
    khung = {"a": (620.0, 1290.0, 193.0, 46.0)}  # chính khung chữ đã vượt mép trên khung tranh
    o = {"a": (600.0, 1270.0, 230.0, 80.0)}
    ra = kep_trong_khung_tranh(o, khung, TRANH)["a"]
    assert ra[1] == 1270, "cạnh trên giữ nguyên vì chữ gốc cố ý tràn"
    assert ra[0] == 609, "cạnh trái vẫn kẹp"


def test_trang_mot_khung_khong_kep():
    o = {"a": (0.0, 0.0, 50.0, 50.0)}
    assert kep_trong_khung_tranh(o, {"a": (10.0, 10.0, 5.0, 5.0)}, [(0, 0, 100, 100)]) == o


def _bong_bong_tren_troi():
    anh = np.empty((200, 300, 3), np.uint8)
    anh[:] = (120, 190, 220)  # trời
    anh[60:140, 40:260] = 255  # bong bóng trắng không viền
    for x in range(70, 200, 8):  # "chữ" trong bong bóng
        anh[95:115, x:x + 3] = 20
    anh[112:115, 70:200:2] = 200  # viền khử răng cưa xám nhạt (vẫn "gần trắng")
    return anh


def test_to_mot_phan_xoa_chu_giu_nguyen_troi():
    anh = _bong_bong_tren_troi()
    khung = BBox(60, 88, 150, 56)  # đáy khung 144 > đáy bong bóng 140 ⇒ dải viền lẫn trời
    kq = to_phang(anh, [khung])
    assert kq.da_to == (0,)
    assert (anh[95:115, 70:200] == 255).all(), "nét chữ + viền mờ phải hết"
    assert (anh[141:144, 70:200] == (120, 190, 220)).all(), "phần trời lọt vào khung giữ nguyên"


def test_nen_da_so_khong_du_thi_de_lama():
    anh = _bong_bong_tren_troi()
    goc = anh.copy()
    kq = to_phang(anh, [BBox(40, 20, 120, 160)])  # khung chủ yếu nằm trên trời
    assert kq.da_to == () and np.array_equal(anh, goc)
