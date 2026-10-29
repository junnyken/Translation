"""E26-B2 — vùng LỚN lặp lại nguyên văn chữ của vùng NHỎ mà nó chồng lên.

Ca chính lấy **toạ độ và chữ THẬT** từ CSDL sau khi chạy 24 trang Pepper&Carrot — đây đúng là ca
mà ảnh production lộ ra và luật hình học của E26-B bỏ sót (REPORT_E26 §7b).

Rủi ro của luật này KHÔNG phải bỏ sót, mà là **bỏ oan làm mất cả câu thoại**. Nên phần lớn test
dưới đây canh chiều đó.
"""
from __future__ import annotations

from app.services.interfaces import BBox
from app.services.typeset.vung_bao import tim_vung_lap_noi_dung


def _b(x, y, w, h):
    return BBox(x=float(x), y=float(y), w=float(w), h=float(h))


class TestCaTrenTrangThat:
    """Toạ độ + chữ THẬT, không phải số tự nghĩ."""

    def test_ca_ma_HINH_HOC_bo_sot(self):
        """`e8e30ad4` chồng `6aaf8a55` chỉ 69% và chỉ 1 vùng con ⇒ E26-B không bắt.

        Nội dung thì lặp rõ: 'Smoke Potions..' nằm nguyên trong chữ của vùng lớn.
        """
        boxes = {
            "e8e30ad4": _b(421, 159, 250, 72),
            "6aaf8a55": _b(452, 211, 215, 29),
        }
        texts = {
            "e8e30ad4": '"Bright-Side" Potions\nSmoke Potions..',
            "6aaf8a55": "Smoke Potions...",
        }
        assert tim_vung_lap_noi_dung(boxes, texts) == {"e8e30ad4"}

    def test_chu_Y_HET_nhau_long_nhau_thi_bo_vung_LON(self):
        """Trang `cc1fffc9`: hai vùng cùng chữ "It's just / so nice here!", lồng nhau 100%.

        Luật chỉ-dài-hơn sẽ trượt ca này, nên điều kiện phải là **không ngắn hơn**.
        """
        boxes = {"6787e037": _b(956, 1442, 188, 113), "73bce606": _b(1000, 1454, 131, 48)}
        texts = {"6787e037": "It's just\nso nice here!", "73bce606": "It's just\nso nice here!"}
        assert tim_vung_lap_noi_dung(boxes, texts) == {"6787e037"}

    def test_vung_lon_mang_THEM_chu_van_bo_duoc_khi_chu_do_co_cho_khac(self):
        """Trang `29ab3d86`: vùng lớn = 'Pfff!' + thoại; 'Pfff!' đã có vùng riêng `617c502e`.

        Bỏ vùng lớn KHÔNG mất chữ nào. Đã kiểm trên dữ liệu thật trước khi bật luật này.
        """
        boxes = {
            "65ea2827": _b(343, 1002, 207, 153),
            "617c502e": _b(379, 1006, 58, 28),
            "0b346c76": _b(348, 1081, 203, 78),
        }
        texts = {
            "65ea2827": "Pfff!\n.. and I thought\nit'd be easier with an\nAir Dragon!",
            "617c502e": "Pfff!",
            "0b346c76": ".. and I thought\nit'd be easier with an\nAir Dragon!",
        }
        ra = tim_vung_lap_noi_dung(boxes, texts)
        assert ra == {"65ea2827"}
        assert "617c502e" not in ra and "0b346c76" not in ra

    def test_khong_bat_oan_vung_nao_tren_trang_that(self):
        """13 vùng còn lại của `0d47b661` không được lọt vào tập bỏ."""
        boxes = {
            "392e16e2": _b(466, 25, 173, 27), "473212d5": _b(391, 69, 274, 32),
            "6aaf8a55": _b(452, 211, 215, 29), "4b8c6563": _b(489, 296, 160, 50),
            "c1a2fab9": _b(71, 968, 135, 28), "cd115254": _b(110, 1029, 403, 53),
            "5ea82bf8": _b(265, 1118, 88, 99), "756e89d8": _b(620, 1312, 192, 51),
        }
        texts = {
            "392e16e2": "Laughing Potions", "473212d5": "Mega-Hairgrowth Potions",
            "6aaf8a55": "Smoke Potions...", "4b8c6563": "... to name just\na few!",
            "c1a2fab9": "Yeah, I know:",
            "cd115254": '"A-true-witch-of-Chaosah-wouldn\'t-create\nthese-kinds-of-potions".',
            "5ea82bf8": "Cling", "756e89d8": "I need to go to the\nmarket in Komona.",
        }
        assert tim_vung_lap_noi_dung(boxes, texts) == set()


class TestBatBienKhongBaoGioMatHETChu:
    """Chỗ luật này có thể gây hại thật: bỏ hết mọi bản của một câu."""

    def test_hai_vung_BANG_dien_tich_cung_chu_thi_KHONG_bo_cai_nao(self):
        """Nếu cho phép bằng diện tích, cả hai coi nhau là bản lặp ⇒ MẤT CẢ CÂU."""
        boxes = {"a": _b(0, 0, 100, 50), "b": _b(0, 0, 100, 50)}
        texts = {"a": "Thanks for inviting us", "b": "Thanks for inviting us"}
        assert tim_vung_lap_noi_dung(boxes, texts) == set()

    def test_chuoi_LONG_NHAU_ba_cap_van_con_lai_vung_nho_nhat(self):
        boxes = {"to": _b(0, 0, 300, 200), "vua": _b(10, 10, 200, 150), "nho": _b(20, 20, 100, 80)}
        t = "Thanks for inviting us Coriander"
        ra = tim_vung_lap_noi_dung(boxes, texts={"to": t, "vua": t, "nho": t})
        assert "nho" not in ra, "vùng nhỏ nhất KHÔNG được bỏ — sẽ mất cả câu"
        assert len(ra) < 3

    def test_chu_NGAN_long_nhau_ngau_nhien_thi_khong_tinh(self):
        """'us' nằm trong 'just' — trùng ngẫu nhiên, không phải lặp nội dung."""
        boxes = {"lon": _b(0, 0, 200, 100), "nho": _b(10, 10, 40, 20)}
        assert tim_vung_lap_noi_dung(boxes, {"lon": "It's just", "nho": "us"}) == set()

    def test_KHONG_chong_nhau_thi_du_trung_chu_cung_khong_bo(self):
        """Hai bong bóng ở hai góc trang có thể nói cùng một câu — đó là chuyện thường."""
        boxes = {"lon": _b(0, 0, 300, 100), "nho": _b(900, 900, 100, 40)}
        t = "Thanks for inviting us"
        assert tim_vung_lap_noi_dung(boxes, {"lon": t + " Coriander", "nho": t}) == set()

    def test_chong_it_hon_nguong_thi_khong_bo(self):
        boxes = {"lon": _b(0, 0, 300, 100), "nho": _b(280, 90, 100, 40)}
        t = "Thanks for inviting us"
        assert tim_vung_lap_noi_dung(boxes, {"lon": t + " Coriander", "nho": t}) == set()

    def test_thieu_chu_thi_khong_ket_luan(self):
        """Vùng chưa có OCR ⇒ không có bằng chứng nội dung ⇒ dịch/vẽ bình thường."""
        boxes = {"lon": _b(0, 0, 300, 200), "nho": _b(20, 20, 100, 80)}
        assert tim_vung_lap_noi_dung(boxes, {"nho": "Thanks for inviting us"}) == set()
        assert tim_vung_lap_noi_dung(boxes, {"lon": "", "nho": ""}) == set()

    def test_khong_co_vung_nao(self):
        assert tim_vung_lap_noi_dung({}, {}) == set()


class TestChuanHoa:
    def test_khac_nhau_dung_phan_dau_cau_van_khop(self):
        """`Smoke Potions..` vs `Smoke Potions...` — so nguyên văn là trượt."""
        boxes = {"lon": _b(0, 0, 300, 200), "nho": _b(20, 20, 100, 80)}
        texts = {"lon": '"Bright-Side" Potions\nSmoke Potions..', "nho": "Smoke Potions..."}
        assert tim_vung_lap_noi_dung(boxes, texts) == {"lon"}

    def test_khac_hoa_thuong_va_xuong_dong_van_khop(self):
        boxes = {"lon": _b(0, 0, 300, 200), "nho": _b(20, 20, 100, 80)}
        texts = {"lon": "SO NICE HERE!\nTHANKS FOR INVITING US", "nho": "Thanks\nfor inviting us"}
        assert tim_vung_lap_noi_dung(boxes, texts) == {"lon"}

    def test_chu_nhat_cung_khop(self):
        boxes = {"lon": _b(0, 0, 300, 200), "nho": _b(20, 20, 100, 80)}
        texts = {"lon": "笑い薬\n超毛生え薬です", "nho": "超毛生え薬"}
        assert tim_vung_lap_noi_dung(boxes, texts) == {"lon"}


class TestNguongRiengChoChuNhatTrung:
    """Ngưỡng 6 ký tự hiệu chỉnh trên chữ LATIN. Dùng chung cho chữ Nhật là luật gần như không
    bao giờ chạy trên truyện Nhật — đúng loại truyện đang dùng thật.

    `超毛生え薬` chỉ 5 ký tự nhưng là cả một danh từ ghép; 5 chữ cái Latin mới là "just"/"nice".
    """

    def test_cum_kanji_5_ky_tu_van_tinh_la_lap(self):
        boxes = {"lon": _b(0, 0, 300, 200), "nho": _b(20, 20, 100, 80)}
        assert tim_vung_lap_noi_dung(
            boxes, {"lon": "笑い薬 超毛生え薬です", "nho": "超毛生え薬"}
        ) == {"lon"}

    def test_cum_kanji_3_ky_tu_la_muc_thap_nhat(self):
        boxes = {"lon": _b(0, 0, 300, 200), "nho": _b(20, 20, 100, 80)}
        assert tim_vung_lap_noi_dung(boxes, {"lon": "これは笑い薬だ", "nho": "笑い薬"}) == {"lon"}

    def test_MOT_HAI_ky_tu_kanji_thi_KHONG_tinh(self):
        """Một–hai ký tự CJK lồng nhau là ngẫu nhiên — `薬` có trong vô số từ."""
        boxes = {"lon": _b(0, 0, 300, 200), "nho": _b(20, 20, 100, 80)}
        for ngan in ("薬", "の薬"):
            assert tim_vung_lap_noi_dung(boxes, {"lon": "これは笑い薬だ", "nho": ngan}) == set()

    def test_chu_LATIN_van_giu_nguong_6(self):
        """Không được để ngưỡng CJK làm lỏng luật cho chữ Latin."""
        boxes = {"lon": _b(0, 0, 300, 200), "nho": _b(20, 20, 100, 80)}
        assert tim_vung_lap_noi_dung(boxes, {"lon": "It's just", "nho": "just"}) == set()

    def test_chuoi_LAN_hai_he_chu_thi_theo_he_chiem_da_so(self):
        """Chữ Nhật thường lẫn số/chữ Latin. Quá nửa là CJK ⇒ dùng ngưỡng CJK."""
        boxes = {"lon": _b(0, 0, 300, 200), "nho": _b(20, 20, 100, 80)}
        assert tim_vung_lap_noi_dung(
            boxes, {"lon": "これは21番の笑い薬だ", "nho": "笑い薬"}
        ) == {"lon"}
