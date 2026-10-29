"""E84 — khung chữ ôm SÁT chữ (bộ nhận diện ngoài, vd Gemini): dải viền trắng tinh nhưng nét chữ
chạm mép khung ⇒ trước đây chốt "mép trong phải sạch" loại oan, rơi về LaMa và để lại bóng mờ chữ
gốc (đo thật 16-10-2026 trang ja_E12P01: 5/6 câu dải viền 100% trắng, mép trong 84–92%).
"""
from __future__ import annotations

import numpy as np

from app.services.inpaint.to_phang import KHE_HO, to_phang
from app.services.interfaces import BBox


def _chu_cham_mep(anh, x, y, w, h):
    """Nét chữ dọc chạm cả mép trên lẫn dưới khung, lấn 1px ra ngoài (vào khe hở)."""
    for xx in range(x + 2, x + w - 2, 6):
        anh[y - 1:y + h + 1, xx:xx + 2] = 0


def test_vien_sach_chu_cham_mep_van_to_phang_va_xoa_ca_phan_lan_khe():
    anh = np.full((200, 300, 3), 255, np.uint8)
    _chu_cham_mep(anh, 100, 80, 90, 20)
    kq = to_phang(anh, [BBox(100, 80, 90, 20)])
    assert kq.da_to == (0,)
    assert (anh[80 - KHE_HO:100 + KHE_HO, 100:190] == 255).all(), "phần nét lấn vào khe còn sót"


def test_net_vien_bong_bong_cat_qua_van_khong_to():
    """Đối chứng âm: nét viền bong bóng đi XUYÊN dải viền vào khung ⇒ dải không sạch ⇒ giữ chốt cũ."""
    anh = np.full((200, 300, 3), 255, np.uint8)
    _chu_cham_mep(anh, 100, 80, 90, 20)
    anh[60:120, 150:153] = 0  # nét viền chạy dọc xuyên qua khung và dải viền
    goc = anh.copy()
    kq = to_phang(anh, [BBox(100, 80, 90, 20)])
    assert kq.da_to == () and np.array_equal(anh, goc)


def test_to_khe_khong_lan_sang_khung_ben_canh():
    """Khe của khung 1 trùng chữ của khung 2 (khung 2 KHÔNG tô được vì nằm trên tranh) ⇒ khung 1 tô
    khe nhưng chừa phần thuộc khung 2."""
    rng = np.random.default_rng(3)
    anh = np.full((200, 300, 3), 255, np.uint8)
    anh[101:160, 115:200] = rng.integers(0, 256, (59, 85, 3), dtype=np.uint8)  # tranh dưới khung 1
    _chu_cham_mep(anh, 100, 60, 90, 20)
    khung2 = BBox(115, 81, 85, 79)  # bắt đầu ngay trong khe dưới của khung 1 (y 80–82)
    anh[81, 120:124] = 7
    kq = to_phang(anh, [BBox(100, 60, 90, 20), khung2])
    assert 1 not in kq.da_to
    assert (anh[81, 120:124] == 7).all(), "khung 1 tô lấn sang khung 2"
