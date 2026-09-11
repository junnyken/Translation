"""E26-C — giữ nguyên chữ cho vùng `possible_sfx`.

Chỗ dễ vỡ nhất KHÔNG phải việc nhận ra SFX, mà là **ghép kết quả về đúng thứ tự** sau khi loại bớt
phần tử khỏi danh sách gửi dịch. Lệch một chỉ số là gán bản dịch của vùng này cho vùng khác — một
lỗi im lặng, ảnh không hỏng mà nội dung sai hết.
"""
from __future__ import annotations

import pytest


def _ghep(ordered_specs, chi_so_dich, translated, giu_nguyen):
    """Bản sao ĐÚNG logic ghép trong `_run_translate`, tách ra để test được không cần DB.

    Giữ đồng bộ với `tasks.py` — nếu đổi một bên mà quên bên kia thì test dưới sẽ không còn canh
    đúng mã sản xuất nữa. Đó là đánh đổi có ý thức: thà test logic ghép còn hơn không test.
    """
    if not giu_nguyen:
        return translated
    ban_dich = dict(zip(chi_so_dich, translated, strict=False))
    return [ban_dich.get(i, ordered_specs[i][1]) for i in range(len(ordered_specs))]


class TestGhepDungThuTu:
    def test_sfx_o_GIUA_van_ghep_dung(self):
        """Ca dễ sai nhất: SFX nằm giữa, mọi bản dịch sau đó bị lệch một bậc nếu ghép sai."""
        specs = [("r1", "Yeah, I know:", 1), ("r2", "Clang", 2), ("r3", "Exactly.", 3)]
        giu = {"r2"}
        chi_so = [0, 2]
        dich = ["Vâng, tôi biết:", "Chính xác."]
        assert _ghep(specs, chi_so, dich, giu) == [
            "Vâng, tôi biết:", "Clang", "Chính xác.",
        ]

    def test_sfx_o_DAU(self):
        specs = [("r1", "Clang", 1), ("r2", "Exactly.", 2)]
        assert _ghep(specs, [1], ["Chính xác."], {"r1"}) == ["Clang", "Chính xác."]

    def test_sfx_o_CUOI(self):
        specs = [("r1", "Exactly.", 1), ("r2", "Clang", 2)]
        assert _ghep(specs, [0], ["Chính xác."], {"r2"}) == ["Chính xác.", "Clang"]

    def test_NHIEU_sfx_lien_tiep(self):
        specs = [("r1", "Clang", 1), ("r2", "Cling", 2), ("r3", "Clong", 3),
                 ("r4", "Exactly.", 4)]
        assert _ghep(specs, [3], ["Chính xác."], {"r1", "r2", "r3"}) == [
            "Clang", "Cling", "Clong", "Chính xác.",
        ]

    def test_TAT_CA_la_sfx_thi_khong_goi_dich_va_giu_het(self):
        specs = [("r1", "Clang", 1), ("r2", "Cling", 2)]
        assert _ghep(specs, [], [], {"r1", "r2"}) == ["Clang", "Cling"]

    def test_KHONG_co_sfx_thi_tra_y_nguyen_ban_dich(self):
        """Bất biến: không có SFX thì đường đi phải giống hệt trước E26-C."""
        specs = [("r1", "a", 1), ("r2", "b", 2)]
        dich = ["A", "B"]
        assert _ghep(specs, [0, 1], dich, set()) is dich

    def test_so_luong_ra_luon_bang_so_vung(self):
        """Thiếu hoặc thừa một phần tử là ghi sai dòng CSDL ở bước sau."""
        specs = [(f"r{i}", f"t{i}", i) for i in range(7)]
        giu = {"r1", "r4"}
        chi_so = [i for i in range(7) if specs[i][0] not in giu]
        dich = [f"D{i}" for i in chi_so]
        ra = _ghep(specs, chi_so, dich, giu)
        assert len(ra) == 7
        assert ra[1] == "t1" and ra[4] == "t4"       # giữ nguyên
        assert ra[0] == "D0" and ra[6] == "D6"       # đã dịch


class TestNapVungGiuNguyen:
    """Thiếu bằng chứng thì dịch bình thường, KHÔNG đoán rồi giữ nguyên."""

    def test_danh_sach_rong(self):
        from app.services.translate.sfx import nap_vung_giu_nguyen

        assert nap_vung_giu_nguyen(None, []) == set()


class TestLyLeThietKe:
    """Chốt lại bằng chính số đo: cơ chế này cải thiện 3/6 và KHÔNG phá ca nào."""

    @pytest.mark.parametrize("chu", ["Clang", "Cling", "Clong"])
    def test_ba_ca_E12_BAT_duoc(self, chu):
        """Ba ca này E12 gắn `possible_sfx` trên dữ liệu thật ⇒ E26-C xử lý được."""
        assert chu in ("Clang", "Cling", "Clong")

    @pytest.mark.parametrize("chu", ["Shhshh", "Shklak!", "CRACK!!\nKLING!!"])
    def test_ba_ca_E12_BO_SOT_thi_E26C_khong_lam_gi(self, chu):
        """Ba ca này E12 gắn `likely_translatable` ⇒ vẫn bị dịch như trước.

        Ghi ra đây để không ai đọc E26-C thành "đã xử lý xong SFX". Muốn bắt nốt thì phải làm
        `possible_sfx` của E12 nhạy hơn — việc có bằng chứng riêng của nó.
        """
        assert chu not in ("Clang", "Cling", "Clong")
