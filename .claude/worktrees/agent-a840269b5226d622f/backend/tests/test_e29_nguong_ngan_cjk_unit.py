"""E29 — ngưỡng "chữ rất ngắn" phải theo HỆ CHỮ, không dùng một con số chung.

Đo thật 2026-09-12 trên 3 trang Pepper&Carrot bản tiếng Nhật: hai vùng **thoại thật** bị gắn
`possible_sfx` rồi E26-C giữ nguyên chữ gốc ⇒ người đọc **mất hẳn hai câu**.

    それでも、   (5 ký tự) = "Dù vậy,"
    ちなみに、   (5 ký tự) = "Nhân tiện,"

Đây đúng là lớp dương tính giả đã ghi ở `REPORT_E26 §4.3` là "có thật nhưng chưa xảy ra trên dữ
liệu đo được" — với tiếng Nhật nó xảy ra ngay lượt chạy đầu.
"""
from __future__ import annotations

import pytest

from app.services.quality.assessor import NguongLuat, RegionQualityAssessor


def _nguong(chu: str) -> int:
    return RegionQualityAssessor.__dict__["_nguong_ngan"](
        type("X", (), {"nguong": NguongLuat()})(), chu
    )


class TestThoaiNhatNganKhongConBiCoiLaSFX:
    @pytest.mark.parametrize("chu", ["それでも、", "ちなみに、", "そんなこと、", "うーん"])
    def test_cac_ca_THOAI_THAT_vuot_nguong_cjk(self, chu):
        """Dài hơn ngưỡng CJK ⇒ KHÔNG bị gắn `short_stylized_text` ⇒ được dịch."""
        assert len(chu) > _nguong(chu), f"{chu!r} vẫn bị coi là chữ rất ngắn"

    @pytest.mark.parametrize("chu", ["ドン", "バン", "あ"])
    def test_SFX_nhat_that_ngan_thi_VAN_bat_duoc(self, chu):
        assert len(chu) <= _nguong(chu)


class TestKhongNoiLONG_cho_chu_LATIN:
    @pytest.mark.parametrize("chu", ["NO!", "Yes!", "Bam", "Clang"])
    def test_chu_latin_giu_nguyen_nguong_5(self, chu):
        """Ngưỡng Latin KHÔNG được đổi — E26-C đo được 13/13 đúng trên dữ liệu tiếng Anh."""
        assert _nguong(chu) == 5
        assert len(chu) <= _nguong(chu)

    def test_latin_dai_hon_5_thi_khong_bat(self):
        assert len("Shhshh") > _nguong("Shhshh")


class TestChonNguongTheoHeChuChiemDaSo:
    def test_lan_so_va_latin_nhung_da_so_CJK_thi_dung_nguong_cjk(self):
        assert _nguong("笑い薬21") == 2

    def test_da_so_LATIN_thi_dung_nguong_latin(self):
        assert _nguong("OK です") == 5

    def test_chu_rong_khong_no(self):
        assert _nguong("") == 5
