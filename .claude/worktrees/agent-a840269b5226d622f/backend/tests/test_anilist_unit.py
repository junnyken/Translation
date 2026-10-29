"""E17 tầng 3b — đối chiếu danh xưng chapter với CSDL AniList.

Nguyên tắc bất di bất dịch: **chapter quyết định CẦN GÌ, CSDL chỉ trả lời VIẾT THẾ NÀO.**

Đo trên API thật 2026-09-04 trước khi thiết kế: One Piece có 500 nhân vật trong CSDL, một chapter
thật có 3 danh xưng. Lệch 150 lần — nên đổ danh sách CSDL vào glossary là làm ngập cảnh báo.
"""
from __future__ import annotations

from app.services.consistency.anilist import doi_chieu

def _nv(full=None, native=None, alt=None):
    return {"name": {"full": full, "native": native, "alternative": alt or []}}


class TestChiLayThuChapterCoThat:
    def test_nhan_vat_KHONG_co_trong_chapter_bi_loai_thang(self):
        kq = doi_chieu(["Nami"], [_nv("Nami", "ナミ"), _nv("Roronoa Zoro", "ゾロ")], "One Piece")
        assert [k.danh_xung for k in kq.khop] == ["Nami"]
        assert kq.bo_qua == 1, "nhân vật ngoài chapter phải bị loại và ĐẾM lại"

    def test_bo_qua_giu_nguyen_de_thay_do_lech(self):
        """`bo_qua` là bằng chứng CSDL rộng hơn chapter bao nhiêu — không được giấu đi."""
        kq = doi_chieu(["Nami"], [_nv(f"NV {i}") for i in range(30)] + [_nv("Nami")], "X")
        assert kq.bo_qua == 30

    def test_chapter_rong_thi_khong_khop_gi(self):
        kq = doi_chieu([], [_nv("Nami")], "X")
        assert kq.khop == [] and kq.bo_qua == 0


class TestGhepTen:
    def test_chapter_goi_ten_NGAN_van_khop_ten_day_du(self):
        """Chapter viết 'Naruto', CSDL ghi 'Naruto Uzumaki'. Không tách phần thì gần như không
        bao giờ khớp được gì."""
        kq = doi_chieu(["Naruto"], [_nv("Naruto Uzumaki", "うずまきナルト")], "Naruto")
        assert len(kq.khop) == 1
        assert kq.khop[0].ten_day_du == "Naruto Uzumaki"
        assert kq.khop[0].ten_goc == "うずまきナルト"

    def test_khop_duoc_ten_GOC_tieng_Nhat(self):
        kq = doi_chieu(["ナミ"], [_nv("Nami", "ナミ")], "One Piece")
        assert len(kq.khop) == 1 and "tên gốc" in kq.khop[0].ly_do

    def test_khop_duoc_ten_goi_khac(self):
        kq = doi_chieu(["Fox"], [_nv("Naruto Uzumaki", alt=["Fox", "Noisy Ninja"])], "Naruto")
        assert len(kq.khop) == 1 and "tên gọi khác" in kq.khop[0].ly_do

    def test_khong_phan_biet_hoa_thuong(self):
        assert len(doi_chieu(["nami"], [_nv("Nami")], "X").khop) == 1

    def test_KHONG_thay_danh_xung_cua_chapter_bang_dang_cua_CSDL(self):
        """Chapter viết sao thì giữ nguyên vậy. Thay bằng dạng CSDL là sửa dữ liệu người dùng."""
        kq = doi_chieu(["nami"], [_nv("Nami", "ナミ")], "X")
        assert kq.khop[0].danh_xung == "nami"


class TestKhongNhanBua:
    def test_ten_qua_ngan_khong_duoc_dung_lam_manh_ghep(self):
        """Tách 'D' từ 'Monkey D Luffy' rồi khớp với chữ 'D' bất kỳ là nhận bừa."""
        kq = doi_chieu(["D"], [_nv("Monkey D Luffy")], "One Piece")
        assert kq.khop == []

    def test_moi_danh_xung_chi_khop_MOT_lan(self):
        """Hai nhân vật cùng khớp một danh xưng thì giữ bản đầu — kết quả phải TẤT ĐỊNH."""
        kq = doi_chieu(["Nami"], [_nv("Nami", "ナミ"), _nv("Nami", "なみ")], "X")
        assert len(kq.khop) == 1

    def test_thu_tu_ket_qua_theo_CHAPTER_chu_khong_theo_CSDL(self):
        kq = doi_chieu(["Zoro", "Nami"], [_nv("Nami"), _nv("Zoro")], "X")
        assert [k.danh_xung for k in kq.khop] == ["Zoro", "Nami"]


class TestNoiThatKhiHong:
    """"Không tìm thấy" và "AniList đang hỏng" là HAI chuyện khác nhau — gộp lại là nói dối."""

    def test_khong_ket_noi_duoc_thi_bao_ly_do_chu_khong_nem(self, monkeypatch):
        import urllib.request

        from app.services.consistency import anilist

        def sap(*a, **k):
            raise OSError("mạng đứt")

        monkeypatch.setattr(urllib.request, "urlopen", sap)
        kq = anilist.tra_ten_chinh_thuc(["Nami"], "One Piece", timeout=1)
        assert kq.khong_dung_duoc == "không kết nối được tới AniList"
        assert kq.khop == []

    def test_khong_tim_thay_bo_truyen_bao_KHAC_voi_hong_mang(self, monkeypatch):
        import json
        import urllib.request

        from app.services.consistency import anilist

        class _Resp:
            def read(self): return json.dumps({"data": {"Media": None}}).encode()
            def __enter__(self): return self
            def __exit__(self, *a): return False

        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Resp())
        kq = anilist.tra_ten_chinh_thuc(["Nami"], "Bộ Truyện Không Tồn Tại", timeout=1)
        assert "không có bộ truyện nào" in kq.khong_dung_duoc
        assert "không kết nối" not in kq.khong_dung_duoc, "gộp hai loại hỏng làm một là nói dối"

    def test_bi_gioi_han_nhip_bao_la_CHO_DUOC(self, monkeypatch):
        """429 nghĩa là chờ một phút là xong — rất khác 'không có truyện này'."""
        import urllib.error
        import urllib.request

        from app.services.consistency import anilist

        def qua_nhip(*a, **k):
            raise urllib.error.HTTPError("u", 429, "Too Many Requests", {}, None)

        monkeypatch.setattr(urllib.request, "urlopen", qua_nhip)
        kq = anilist.tra_ten_chinh_thuc(["Nami"], "One Piece", timeout=1)
        assert "thử lại sau" in kq.khong_dung_duoc

    def test_404_la_KHONG_CO_TRUYEN_chu_khong_phai_loi_ky_thuat(self, monkeypatch):
        """AniList báo "không tìm thấy" bằng HTTP 404, KHÔNG phải bằng `Media: null`.

        Đo trên host 2026-09-04 với "Pepper and Carrot":
            {"errors":[{"message":"Not Found.","status":404}],"data":{"Media":null}}

        Bản đầu rơi vào nhánh lỗi chung và hiện "AniList trả lỗi 404" — câu kỹ thuật không nói
        cho người dùng biết phải làm gì.
        """
        import urllib.error
        import urllib.request

        from app.services.consistency import anilist

        def khong_thay(*a, **k):
            raise urllib.error.HTTPError("u", 404, "Not Found", {}, None)

        monkeypatch.setattr(urllib.request, "urlopen", khong_thay)
        kq = anilist.tra_ten_chinh_thuc(["Nami"], "Bộ Không Có Thật", timeout=1)
        assert "không có bộ truyện nào" in kq.khong_dung_duoc
        assert "404" not in kq.khong_dung_duoc, "vẫn phun mã lỗi kỹ thuật ra cho người dùng"
