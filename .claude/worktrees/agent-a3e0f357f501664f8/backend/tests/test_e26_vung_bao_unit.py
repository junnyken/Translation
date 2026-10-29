"""E26-B — tìm vùng bao. Ca chính lấy nguyên toạ độ thật của trang `en_E12P01`.

Chèn chữ cho cả vùng bao lẫn các vùng con ⇒ cùng một câu bị vẽ hai lần chồng lên nhau.
"""
from __future__ import annotations

from app.services.interfaces import BBox
from app.services.typeset.vung_bao import tim_vung_bao


def _b(x, y, w, h):
    return BBox(x=float(x), y=float(y), w=float(w), h=float(h))


#: Toạ độ THẬT từ CSDL sau khi chạy trang `en_E12P01` (Pepper&Carrot), không phải số tự nghĩ.
TRANG_THAT = {
    "r2_bao": _b(400, 41, 285, 228),   # 'Luughing Fotlons / Mega-Hairgrowth / Stink-bubble...'
    "r1": _b(466, 25, 173, 27),        # 'Laughing Potions'
    "r3": _b(391, 69, 274, 32),        # 'Mega-Hairgrowth Potions'
    "r4": _b(421, 159, 250, 72),       # '"Bright-Side" Potions / Smoke Potions..'
    "r5": _b(452, 211, 215, 29),       # 'Smoke Potions...'
    "r6": _b(489, 296, 160, 50),       # '... to name just / a few!'  — NGOÀI vùng bao
    "r8": _b(110, 1029, 403, 53),      # thoại ở nửa dưới trang
    "r12": _b(620, 1312, 192, 51),
    "r13": _b(82, 1472, 186, 51),
    "r14": _b(612, 1473, 239, 135),
}


class TestTrenTrangThat:
    def test_tim_dung_vung_bao(self):
        assert tim_vung_bao(TRANG_THAT) == {"r2_bao"}

    def test_KHONG_bo_vung_con(self):
        """Vùng con là vùng mang chữ ĐÚNG — bỏ nó là mất chữ, tệ hơn hẳn vẽ trùng."""
        bao = tim_vung_bao(TRANG_THAT)
        for k in ("r1", "r3", "r4", "r5"):
            assert k not in bao, f"{k} là vùng con, không được coi là vùng bao"

    def test_KHONG_bo_vung_ngoai_khoi_bao(self):
        bao = tim_vung_bao(TRANG_THAT)
        for k in ("r6", "r8", "r12", "r13", "r14"):
            assert k not in bao


class TestKhongBoOAN:
    """Bỏ oan một bong bóng thật là mất cả câu thoại — tệ hơn hẳn vẽ trùng một câu."""

    def test_chong_nhe_mot_vung_thi_KHONG_phai_vung_bao(self):
        """Chỉ `overlap_suspect` thôi là không đủ: bong bóng lớn chồng nhẹ 1 vùng vẫn hợp lệ."""
        boxes = {"lon": _b(0, 0, 300, 100), "nho": _b(280, 80, 60, 40)}
        assert tim_vung_bao(boxes) == set()

    def test_chua_TRON_mot_vung_thoi_cung_KHONG_du(self):
        """Một bong bóng có thể chứa một vùng nhỏ hợp lệ (vd dấu chấm than tách rời)."""
        boxes = {"lon": _b(0, 0, 300, 200), "nho": _b(50, 50, 40, 30)}
        assert tim_vung_bao(boxes) == set()

    def test_hai_box_gan_TRUNG_nhau_khong_coi_nhau_la_con(self):
        """Nếu không loại theo diện tích, hai box gần trùng sẽ cùng bị bỏ ⇒ MẤT CHỮ."""
        boxes = {"a": _b(0, 0, 200, 100), "b": _b(1, 1, 199, 99), "c": _b(2, 2, 198, 98)}
        bao = tim_vung_bao(boxes)
        assert len(bao) < len(boxes), "không được bỏ HẾT — sẽ mất chữ"

    def test_vung_rong_khong_no(self):
        assert tim_vung_bao({"a": _b(0, 0, 0, 0), "b": _b(0, 0, 10, 10)}) == set()

    def test_khong_co_vung_nao(self):
        assert tim_vung_bao({}) == set()

    def test_mot_vung_duy_nhat(self):
        assert tim_vung_bao({"a": _b(0, 0, 100, 100)}) == set()


class TestNguongDieuChinhDuoc:
    def test_doi_so_vung_con_toi_thieu(self):
        boxes = {"lon": _b(0, 0, 300, 200), "n1": _b(10, 10, 40, 30)}
        assert tim_vung_bao(boxes, toi_thieu=1) == {"lon"}
        assert tim_vung_bao(boxes, toi_thieu=2) == set()

    def test_khong_doi_ti_le_chua_tron_thi_box_lech_vai_pixel_van_tinh(self):
        """Box của bộ nhận diện lệch vài pixel là chuyện thường, nên không đòi 1.0 tuyệt đối."""
        boxes = {
            "lon": _b(100, 100, 200, 200),
            "n1": _b(95, 110, 50, 40),    # nhô ra trái 5px
            "n2": _b(150, 150, 60, 40),
        }
        assert tim_vung_bao(boxes) == {"lon"}
