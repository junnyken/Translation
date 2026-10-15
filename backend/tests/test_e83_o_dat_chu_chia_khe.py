"""E83 — hai vùng chữ chung MỘT bong bóng: ô đặt chữ chia khoảng trống ở ĐƯỜNG GIỮA.

Đo thật trên production 16-10-2026 (trang `ja_E12P01`, Pepper&Carrot): sáu câu trong một bong bóng
mây lớn. E27 cắt ô đặt chữ của mỗi vùng tới sát KHUNG CHỮ vùng kia (chừa 1px) ⇒ ô của câu 5 nới
xuống tới đỉnh khung câu 6, ô câu 6 nới lên tới đáy khung câu 5 ⇒ HAI Ô CÙNG CHIẾM khoảng trống
giữa, chữ căn giữa ô nên "THUỐC TẠO KHÓI..." đè lên "...THẬT LÀ, TOÀN MẤY".
"""
from __future__ import annotations

from app.services.safearea.khong_de_len_nhau import _chong_nhau, cat_o_dat_chu

# Khung chữ thật của hai vùng (toạ độ ảnh gốc), ô đặt chữ = lòng bong bóng lớn chung.
KHUNG = {
    "cau5": (543.6, 217.46, 84.0, 19.92),
    "cau6": (490.8, 302.12, 158.4, 48.14),
}
BONG_BONG = (440.0, 20.0, 260.0, 340.0)


def _o():
    return {k: BONG_BONG for k in KHUNG}


def test_hai_o_chung_bong_bong_khong_con_chong_nhau():
    ra = cat_o_dat_chu(_o(), KHUNG)
    assert not _chong_nhau(ra["cau5"], ra["cau6"]), ra


def test_cat_dung_duong_giua_khoang_trong():
    ra = cat_o_dat_chu(_o(), KHUNG)
    giua = (217.46 + 19.92 + 302.12) / 2
    day5 = ra["cau5"][1] + ra["cau5"][3]
    assert abs(day5 - giua) <= 1.0
    assert abs(ra["cau6"][1] - giua) <= 1.0


def test_van_giu_tron_khung_chu_cua_minh():
    ra = cat_o_dat_chu(_o(), KHUNG)
    for rid, (kx, ky, kw, kh) in KHUNG.items():
        ox, oy, ow, oh = ra[rid]
        assert ox <= kx and oy <= ky and ox + ow >= kx + kw and oy + oh >= ky + kh


def test_ca_that_E27_cung_khong_con_chong_nhau():
    """Số đo thật của E27 (`0d47b661`): trước đây chỉ canh ô vs KHUNG vùng kia; ô vs ô vẫn chồng."""
    o_dat = {"392e16e2": (399.0, 3.0, 497.0, 156.0), "473212d5": (379.0, 33.0, 636.0, 130.0)}
    khung = {"392e16e2": (466.0, 25.0, 173.0, 27.0), "473212d5": (391.0, 69.0, 274.0, 32.0)}
    ra = cat_o_dat_chu(o_dat, khung)
    assert not _chong_nhau(ra["392e16e2"], ra["473212d5"]), ra


def test_o_khong_cham_khung_ben_kia_nhung_hai_o_van_chong_nhau():
    """Số đo tái hiện local (LaMa thật) trang ja_E12P01: ô câu 6 tự nó chỉ lên tới y=257 nên KHÔNG
    chạm khung câu 5 (đáy 237) ⇒ lượt cắt theo khung bỏ qua; nhưng ô câu 5 xuống tới 270 ⇒ hai ô
    chồng 13px và chữ đè nhau."""
    o_dat = {"cau5": (493.0, 206.0, 145.0, 64.0), "cau6": (457.0, 257.0, 203.0, 94.0)}
    khung = {"cau5": (544.0, 217.0, 84.0, 20.0), "cau6": (492.0, 302.0, 155.0, 46.0)}
    ra = cat_o_dat_chu(o_dat, khung)
    assert not _chong_nhau(ra["cau5"], ra["cau6"]), ra
    for rid, (kx, ky, kw, kh) in khung.items():
        ox, oy, ow, oh = ra[rid]
        assert ox <= kx and oy <= ky and ox + ow >= kx + kw and oy + oh >= ky + kh


def test_hai_o_tach_roi_thi_giu_nguyen():
    o_dat = {"a": (0.0, 0.0, 100.0, 50.0), "b": (0.0, 60.0, 100.0, 50.0)}
    khung = {"a": (10.0, 10.0, 50.0, 20.0), "b": (10.0, 70.0, 50.0, 20.0)}
    assert cat_o_dat_chu(o_dat, khung) == o_dat
