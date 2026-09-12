"""E27 — ô đặt chữ không được trùm lên khung chữ của vùng khác.

Ca chính dùng **số đo thật** từ trang `0d47b661`, nơi hai ô đặt chữ chồng nhau làm chữ vẽ đè.

Rủi ro của module này là **cắt quá tay**: cắt vào khung chữ của chính vùng đó thì chữ bé lại hoặc
bị gọt — tệ hơn cả khi không nới. Phần lớn test dưới đây canh chiều ấy.
"""
from __future__ import annotations

from app.services.safearea.khong_de_len_nhau import _chong_nhau, cat_o_dat_chu


class TestTrenTrangThat:
    """Số đo thật: hai ô đặt chữ chồng nhau, mỗi ô trùm khung chữ của vùng kia."""

    O_DAT = {
        "392e16e2": (399.0, 3.0, 497.0, 156.0),
        "473212d5": (379.0, 33.0, 636.0, 130.0),
    }
    KHUNG = {
        "392e16e2": (466.0, 25.0, 173.0, 27.0),
        "473212d5": (391.0, 69.0, 274.0, 32.0),
    }

    def test_truoc_khi_cat_hai_o_CHONG_nhau(self):
        """Chốt lại tiền đề — nếu ca này tự nhiên hết chồng thì test dưới thành rỗng nghĩa."""
        assert _chong_nhau(self.O_DAT["392e16e2"], self.O_DAT["473212d5"])

    def test_sau_khi_cat_o_KHONG_con_trum_khung_chu_vung_khac(self):
        ra = cat_o_dat_chu(self.O_DAT, self.KHUNG)
        assert not _chong_nhau(ra["392e16e2"], self.KHUNG["473212d5"])
        assert not _chong_nhau(ra["473212d5"], self.KHUNG["392e16e2"])

    def test_moi_o_van_chua_TRON_khung_chu_cua_chinh_no(self):
        """Bất biến quan trọng nhất: cắt vào khung chữ của mình là gọt mất chữ."""
        ra = cat_o_dat_chu(self.O_DAT, self.KHUNG)
        for rid, (kx, ky, kw, kh) in self.KHUNG.items():
            ox, oy, ow, oh = ra[rid]
            assert ox <= kx and oy <= ky, f"{rid}: ô cắt lẹm vào khung chữ"
            assert ox + ow >= kx + kw and oy + oh >= ky + kh, f"{rid}: ô cắt lẹm vào khung chữ"

    def test_van_con_RONG_HON_khung_chu_goc(self):
        """Không được thoái hoá thành 'bỏ nới ô' — mất luôn cái A1 đem lại."""
        ra = cat_o_dat_chu(self.O_DAT, self.KHUNG)
        for rid in self.KHUNG:
            k = self.KHUNG[rid]
            assert ra[rid][2] * ra[rid][3] > k[2] * k[3], f"{rid}: ô không còn rộng hơn khung chữ"


class TestKhongCatQUA_TAY:
    def test_khong_co_vat_can_thi_giu_NGUYEN(self):
        o = {"a": (0.0, 0.0, 300.0, 200.0)}
        k = {"a": (50.0, 50.0, 40.0, 30.0)}
        assert cat_o_dat_chu(o, k) == o

    def test_vat_can_o_XA_thi_giu_NGUYEN(self):
        o = {"a": (0.0, 0.0, 100.0, 100.0)}
        k = {"a": (10.0, 10.0, 40.0, 30.0), "b": (900.0, 900.0, 50.0, 50.0)}
        assert cat_o_dat_chu(o, k)["a"] == (0.0, 0.0, 100.0, 100.0)

    def test_vat_can_de_len_CHINH_khung_chu_minh_thi_GIU_NGUYEN(self):
        """Hai vùng nhận diện chồng nhau — cắt kiểu gì cũng mất chữ.

        Đó là việc của E26-B/B2 ở bước VẼ, không phải việc cắt ô. Giữ nguyên còn hơn gọt bừa.
        """
        o = {"a": (0.0, 0.0, 300.0, 200.0)}
        k = {"a": (50.0, 50.0, 100.0, 80.0), "b": (60.0, 60.0, 90.0, 70.0)}
        assert cat_o_dat_chu(o, k)["a"] == (0.0, 0.0, 300.0, 200.0)

    def test_o_HEP_HON_khung_chu_van_cat_duoc_va_giu_phan_GIAO(self):
        """Với bong bóng THẬT, vùng an toàn là lòng bong bóng đã ăn mòn nên HẸP HƠN khung chữ.

        Số đo thật `e8e30ad4`: ô x 423–660 so với khung x 421–671. Nếu đòi ô bao trọn khung chữ
        thì module này không chạm tới phần lớn bong bóng thật — phải lấy phần GIAO.
        """
        o = {"a": (423.0, 4.0, 237.0, 238.0)}
        k = {
            "a": (421.0, 159.0, 250.0, 72.0),      # khung RỘNG hơn ô theo chiều ngang
            "b": (466.0, 25.0, 173.0, 27.0),       # vật cản nằm ở phần ô nhô lên trên
        }
        ra = cat_o_dat_chu(o, k)["a"]
        assert not _chong_nhau(ra, k["b"]), "không cắt được vì đòi bao trọn khung chữ"
        # phần giao (y 159–231) phải còn nguyên
        assert ra[1] <= 159.0 and ra[1] + ra[3] >= 231.0

    def test_o_KHONG_dinh_khung_chu_cua_minh_thi_giu_NGUYEN(self):
        o = {"a": (0.0, 0.0, 50.0, 50.0)}
        k = {"a": (900.0, 900.0, 50.0, 50.0), "b": (10.0, 10.0, 20.0, 20.0)}
        assert cat_o_dat_chu(o, k)["a"] == (0.0, 0.0, 50.0, 50.0)

    def test_thieu_khung_chu_cua_chinh_no_thi_giu_NGUYEN(self):
        """Thiếu bằng chứng thì không cắt, chứ không đoán."""
        o = {"a": (0.0, 0.0, 300.0, 200.0)}
        assert cat_o_dat_chu(o, {"b": (10.0, 10.0, 20.0, 20.0)})["a"] == (0.0, 0.0, 300.0, 200.0)

    def test_o_rong_khong_no(self):
        assert cat_o_dat_chu({"a": (0.0, 0.0, 0.0, 0.0)}, {"a": (0.0, 0.0, 10.0, 10.0)})["a"] == (
            0.0, 0.0, 0.0, 0.0
        )

    def test_khong_co_vung_nao(self):
        assert cat_o_dat_chu({}, {}) == {}

    def test_giu_dung_bo_khoa(self):
        """Bên gọi hỏi vùng nào thì nhận đúng vùng đó — không thêm, không bớt."""
        o = {"a": (0.0, 0.0, 300.0, 200.0)}
        k = {"a": (50.0, 50.0, 40.0, 30.0), "b": (400.0, 0.0, 50.0, 50.0)}
        assert set(cat_o_dat_chu(o, k)) == {"a"}


class TestChonNhatCatMatIT_NHAT:
    def test_cat_theo_chieu_giu_duoc_NHIEU_dien_tich_hon(self):
        """Vật cản ở góc phải-dưới: cả hai nhát đều HỢP LỆ, phải chọn nhát mất ít hơn.

        Khung chữ của `a` phải nhỏ và nằm góc trên-trái, nếu không nhát cắt dưới sẽ lẹm vào nó và
        bị loại — lúc đó test chỉ còn kiểm "có cắt" chứ không kiểm "chọn đúng nhát".
        """
        o = {"a": (0.0, 0.0, 400.0, 100.0)}
        k = {"a": (0.0, 0.0, 50.0, 50.0), "b": (300.0, 90.0, 100.0, 10.0)}
        ra = cat_o_dat_chu(o, k)["a"]
        assert not _chong_nhau(ra, k["b"])
        # cắt PHẢI còn 299x100 = 29900; cắt DƯỚI còn 400x89 = 35600  ⇒ phải chọn DƯỚI
        assert ra[2] == 400.0, "đã chọn nhát cắt mất nhiều diện tích hơn"
        assert ra[3] < 100.0

    def test_ca_nhat_cat_DUOI_bi_loai_vi_lem_khung_chu(self):
        """Đối chứng cho ca trên: khung chữ cao trọn ô ⇒ chỉ còn nhát cắt PHẢI hợp lệ."""
        o = {"a": (0.0, 0.0, 400.0, 100.0)}
        k = {"a": (0.0, 0.0, 50.0, 100.0), "b": (300.0, 90.0, 100.0, 10.0)}
        ra = cat_o_dat_chu(o, k)["a"]
        assert not _chong_nhau(ra, k["b"])
        assert ra[3] == 100.0 and ra[2] < 400.0


class TestNhieuVatCan:
    def test_ba_vung_xep_chong_deu_duoc_go(self):
        khung = {
            "tren": (100.0, 0.0, 100.0, 20.0),
            "giua": (100.0, 50.0, 100.0, 20.0),
            "duoi": (100.0, 100.0, 100.0, 20.0),
        }
        o_dat = {k: (0.0, 0.0, 400.0, 200.0) for k in khung}
        ra = cat_o_dat_chu(o_dat, khung)
        for rid in khung:
            for khac, b in khung.items():
                if khac != rid:
                    assert not _chong_nhau(ra[rid], b), f"{rid} vẫn trùm khung của {khac}"
            kx, ky, kw, kh = khung[rid]
            assert ra[rid][0] <= kx and ra[rid][1] <= ky
            assert ra[rid][0] + ra[rid][2] >= kx + kw and ra[rid][1] + ra[rid][3] >= ky + kh
