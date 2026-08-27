"""Unit — thứ tự đọc (M5 §7.1). Sai thứ tự ở đây là hỏng mạch văn cả trang."""
import pytest

from app.services.interfaces import BBox
from app.services.translate.reading_order import (
    OrderedItem,
    UnknownReadingDirection,
    direction_for,
    order_items,
)


def _items(*boxes) -> list[OrderedItem]:
    return [OrderedItem(key=name, bbox=BBox(x=x, y=y, w=w, h=h)) for name, x, y, w, h in boxes]


def _keys(items) -> list[str]:
    return [i.key for i in items]


class TestDirection:
    def test_nhat_doc_phai_sang_trai(self):
        assert direction_for("ja") == "rtl"

    @pytest.mark.parametrize("lang", ["en", "zh"])
    def test_anh_trung_doc_trai_sang_phai(self, lang):
        assert direction_for(lang) == "ltr"

    def test_lang_la_mac_dinh_ltr(self):
        assert direction_for("fr") == "ltr"

    def test_co_the_ep_huong_doc(self):
        assert direction_for("en", override="rtl") == "rtl"
        assert direction_for("ja", override="ltr") == "ltr"

    def test_huong_doc_khong_hop_le_bao_loi(self):
        with pytest.raises(UnknownReadingDirection):
            direction_for("ja", override="xyz")


class TestOrder:
    #: 2 hàng, mỗi hàng 2 bubble:  A B  /  C D   (toạ độ x tăng dần sang phải)
    LAYOUT = (
        ("A", 100, 100, 200, 80),
        ("B", 700, 110, 200, 80),
        ("C", 100, 600, 200, 80),
        ("D", 700, 610, 200, 80),
    )

    def test_manga_nhat_doc_phai_truoc_trai_sau(self):
        assert _keys(order_items(_items(*self.LAYOUT), "rtl")) == ["B", "A", "D", "C"]

    def test_tieng_anh_doc_trai_truoc_phai_sau(self):
        assert _keys(order_items(_items(*self.LAYOUT), "ltr")) == ["A", "B", "C", "D"]

    def test_hang_tren_luon_truoc_hang_duoi(self):
        order = _keys(order_items(_items(*self.LAYOUT), "rtl"))
        assert order.index("B") < order.index("D")
        assert order.index("A") < order.index("C")

    def test_lech_vai_chuc_pixel_van_tinh_la_cung_hang(self):
        """Bubble hiếm khi thẳng hàng tuyệt đối — lệch nhẹ không được tách thành 2 hàng."""
        items = _items(
            ("phai", 700, 105, 200, 80),
            ("trai", 100, 100, 200, 80),
        )
        assert _keys(order_items(items, "rtl")) == ["phai", "trai"]

    def test_khac_hang_ro_ret_thi_tach_hang(self):
        items = _items(
            ("duoi_phai", 700, 900, 200, 80),
            ("tren_trai", 100, 100, 200, 80),
        )
        assert _keys(order_items(items, "rtl")) == ["tren_trai", "duoi_phai"]

    def test_danh_sach_rong(self):
        assert order_items([], "rtl") == []

    def test_mot_phan_tu(self):
        assert _keys(order_items(_items(("X", 0, 0, 10, 10)), "rtl")) == ["X"]

    def test_khong_lam_mat_hay_nhan_doi_vung_nao(self):
        items = _items(*self.LAYOUT)
        out = order_items(items, "rtl")
        assert sorted(_keys(out)) == ["A", "B", "C", "D"]
        assert len(out) == len(items)


def test_calculate_reading_order_tren_object_giong_textregion():
    from app.services.translate.reading_order import calculate_reading_order

    class _R:
        def __init__(self, name, x, y):
            self.name, self.bbox_x, self.bbox_y = name, x, y
            self.bbox_w, self.bbox_h = 200.0, 80.0

    regions = [_R("trai", 100, 100), _R("phai", 700, 100)]
    assert [r.name for r in calculate_reading_order(regions, "ja")] == ["phai", "trai"]
    assert [r.name for r in calculate_reading_order(regions, "en")] == ["trai", "phai"]
