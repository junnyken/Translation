"""Unit — so khớp thuật ngữ theo ngôn ngữ (E13). Thuần hàm, không DB."""
from __future__ import annotations

import unicodedata

import pytest

from app.services.consistency.matching import (
    chua_thuat_ngu_dich,
    chuan_hoa,
    khoa_thuat_ngu,
    khop_uu_tien_dai_truoc,
    tim_khop,
)


class TestChuanHoa:
    def test_nfd_va_nfc_cho_ra_cung_mot_dang(self):
        """Bài học từ M6: NFD trông y hệt NFC nhưng so chuỗi thì KHÁC — khớp sẽ trượt."""
        nfd = unicodedata.normalize("NFD", "bình thuốc")
        assert nfd != "bình thuốc"
        assert chuan_hoa(nfd) == "bình thuốc"

    def test_khong_doi_noi_dung_ngoai_chuan_hoa(self):
        assert chuan_hoa("Magic Potion!") == "Magic Potion!"
        assert chuan_hoa("") == ""


class TestKhoaThuatNgu:
    def test_tieng_anh_khong_phan_biet_hoa_thuong(self):
        assert khoa_thuat_ngu("Magic Potion", "en") == khoa_thuat_ngu("magic potion", "en")

    def test_gom_khoang_trang_thua(self):
        assert khoa_thuat_ngu("  magic   potion  ", "en") == "magic potion"

    def test_tieng_nhat_khong_ha_chu_thuong(self):
        """`casefold` kiểu Latin không có nghĩa với chữ tượng hình và có thể làm hỏng ký tự."""
        assert khoa_thuat_ngu("魔法薬", "ja") == "魔法薬"


class TestKhopTiengAnh:
    @pytest.mark.parametrize("van_ban,tu,so_lan", [
        ("I drink a magic potion now", "magic potion", 1),
        ("magicpotion here", "magic potion", 0),
        ("Pepper and Peppermint", "Pepper", 1),
        ("PEPPER shouted", "pepper", 1),
        ("the potion, magic potion.", "magic potion", 1),
    ])
    def test_ranh_gioi_tu(self, van_ban, tu, so_lan):
        assert len(tim_khop(van_ban, tu, "en")) == so_lan

    @pytest.mark.parametrize("van_ban,tu,so_lan", [
        ("Don't even think", "Don't", 1),
        ("Dont even think", "Don't", 0),
        ("well-known hero", "well-known", 1),
        ("wellknown hero", "well-known", 0),
    ])
    def test_giu_hanh_vi_cua_dau_nhay_va_gach_noi(self, van_ban, tu, so_lan):
        """`\\b` của Python coi ' và - là ranh giới, dùng thẳng sẽ khớp sai."""
        assert len(tim_khop(van_ban, tu, "en")) == so_lan

    def test_nhieu_lan_xuat_hien(self):
        assert len(tim_khop("Pepper met Pepper again", "Pepper", "en")) == 2


class TestKhopTiengNhatTrung:
    def test_khong_gia_dinh_co_khoang_trang(self):
        assert len(tim_khop("魔法薬を飲む", "魔法薬", "ja")) == 1

    def test_khop_giua_chuoi(self):
        assert len(tim_khop("这是魔法药水", "魔法", "zh")) == 1

    def test_khong_chong_lan_chinh_no(self):
        assert len(tim_khop("ととと", "とと", "ja")) == 1


class TestUuTienDaiTruoc:
    def test_thuat_ngu_dai_thang_thuat_ngu_ngan(self):
        """Không có luật này thì '魔法薬' bị tính thành hai lần khớp '魔法' — đếm sai, đề xuất sai."""
        r = khop_uu_tien_dai_truoc("魔法薬を飲む", [("ngan", "魔法"), ("dai", "魔法薬")], "ja")
        assert "dai" in r and "ngan" not in r

    def test_tieng_anh_cung_uu_tien_dai(self):
        r = khop_uu_tien_dai_truoc(
            "a magic potion", [("ngan", "potion"), ("dai", "magic potion")], "en"
        )
        assert "dai" in r and "ngan" not in r

    def test_hai_thuat_ngu_khong_giao_nhau_thi_giu_ca_hai(self):
        r = khop_uu_tien_dai_truoc(
            "Pepper drinks a potion", [("a", "Pepper"), ("b", "potion")], "en"
        )
        assert set(r) == {"a", "b"}

    def test_khong_co_thuat_ngu_nao_thi_rong(self):
        assert khop_uu_tien_dai_truoc("gì đó", [], "en") == {}


class TestChuaThuatNguDich:
    def test_khong_phan_biet_hoa_thuong(self):
        assert chua_thuat_ngu_dich("Bình thuốc phép đây", "bình thuốc phép")

    def test_giu_nguyen_dau_tieng_viet(self):
        """Bỏ dấu để so sẽ khiến 'ma' khớp cả 'mà', 'má', 'mã' — sinh hàng loạt cảnh báo sai."""
        assert not chua_thuat_ngu_dich("mà thôi", "ma")
        assert not chua_thuat_ngu_dich("cái mã đó", "ma")
        assert chua_thuat_ngu_dich("con ma kìa", "ma")

    def test_nfd_trong_thuat_ngu_van_khop(self):
        nfd = unicodedata.normalize("NFD", "bình thuốc")
        assert chua_thuat_ngu_dich("Đây là bình thuốc phép", nfd)
