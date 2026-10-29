"""E33 — gộp nhiều chapter vào một file xuất.

Hai chỗ mất dữ liệu ÂM THẦM, và test ở đây canh đúng hai chỗ đó:

1. **Tên trùng trong archive.** Mỗi chapter đều có trang 1. Đổ thẳng vào một archive thì trang 1
   của chapter sau ghi đè trang 1 của chapter trước — `zipfile` KHÔNG báo lỗi, nó tạo hai entry
   cùng tên mà phần lớn ứng dụng đọc truyện chỉ thấy một. Mất trang mà không ai biết.
2. **Thứ tự.** Ứng dụng đọc truyện sắp trang theo TÊN FILE, không theo thứ tự ghi vào archive.
   Nên thứ tự người dùng chọn phải nằm trong TÊN.
"""
from __future__ import annotations

import pytest

from app.services.export.chapter import ChapterExporter, TrangCanXuat
from app.services.export.gop_chapter import kiem_thu_tu, tien_to_chapter


def ten_trong_archive(vi_tri: int, ten_chapter: str, tong: int, so_trang: int, tong_trang: int) -> str:
    """Đi qua ĐÚNG đường sản xuất: tiền tố của E33 + `ten_trang` của bộ xuất.

    Cố ý KHÔNG tự ghép chuỗi trong test: `ten_trang` là chỗ duy nhất quyết định tên trang (nó còn
    tự tính độ rộng chữ số theo tổng số trang). Test tự ghép là test một hàm không ai gọi.
    """
    trang = TrangCanXuat(
        page_id="p", order=so_trang, clean_image_rel="x.png", regions=[],
        tien_to=tien_to_chapter(vi_tri, ten_chapter, tong),
    )
    return ChapterExporter.ten_trang(trang, tong_trang)


class TestKhongTrungTenTrongArchive:
    def test_cung_so_trang_o_HAI_chapter_ra_hai_ten_KHAC_nhau(self):
        """Ca gây mất trang: cả hai chapter đều có `001.png`."""
        a = ten_trong_archive(1, "Chương Một", 2, 1, 3)
        b = ten_trong_archive(2, "Chương Hai", 2, 1, 3)
        assert a != b
        assert a == "01_chuong_mot/001.png"
        assert b == "02_chuong_hai/001.png"

    def test_hai_chapter_TEN_GIONG_NHAU_van_ra_ten_khac(self):
        """Người dùng có thể đặt hai chapter cùng tên — số thứ tự phải cứu được ca này."""
        a = ten_trong_archive(1, "Chương 1", 2, 1, 3)
        b = ten_trong_archive(2, "Chương 1", 2, 1, 3)
        assert a != b

    def test_ten_chapter_RONG_sau_khi_loc_van_ra_ten_dung_duoc(self):
        """Tên toàn ký tự lạ ⇒ `slugify` trả mặc định; số thứ tự vẫn phân biệt được."""
        a = ten_trong_archive(1, "★★★", 2, 1, 3)
        b = ten_trong_archive(2, "☆☆☆", 2, 1, 3)
        assert a != b
        assert a.endswith("/001.png") and not a.startswith("/")

    def test_gop_MOT_chapter_van_co_thu_muc(self):
        """Để xuất đơn và xuất gộp cùng một chapter không cho ra hai cấu trúc lẫn nhau."""
        assert "/" in ten_trong_archive(1, "Chương Một", 1, 1, 3)


class TestThuTuNamTrongTEN:
    def test_sap_theo_ten_ra_dung_thu_tu_nguoi_dung_chon(self):
        """Đây là phép kiểm thật sự: sort() theo tên phải ra đúng thứ tự đã chọn."""
        ten = [
            ten_trong_archive(i, t, 3, 1, 3)
            for i, t in enumerate(["Chương Ba", "Chương Một", "Chương Hai"], start=1)
        ]
        assert sorted(ten) == ten, "sắp theo tên file KHÔNG ra thứ tự người dùng chọn"

    def test_vuot_99_chapter_thi_NOI_chu_so_chu_khong_cat(self):
        """Cắt bớt chữ số là tạo tên trùng — đúng thứ luật này sinh ra để tránh."""
        a = tien_to_chapter(9, "c", 100)
        b = tien_to_chapter(99, "c", 100)
        c = tien_to_chapter(100, "c", 100)
        assert sorted([a, b, c]) == [a, b, c]
        assert a.startswith("009")

    def test_mot_chu_so_van_dem_hai_cho(self):
        """3 chapter thì `1` phải ra `01`, không phải `1` — nếu không thì 10 sắp trước 2."""
        assert tien_to_chapter(1, "c", 3).startswith("01")


class TestChuanHoaDanhSach:
    def test_bo_TRUNG_nhung_giu_thu_tu_lan_dau(self):
        """Chọn trùng là nhầm tay; để nguyên thì trang bị xuất hai lần với hai tiền tố."""
        assert kiem_thu_tu(["b", "a", "b", "c", "a"], "b") == ["b", "a", "c"]

    def test_chapter_CHINH_luon_co_mat(self):
        """`project_id` là chỗ nghẽn kiểm quyền — danh sách thiếu nó là chưa kiểm đủ quyền."""
        assert kiem_thu_tu(["a", "c"], "b") == ["b", "a", "c"]

    def test_chapter_chinh_da_co_thi_KHONG_nhan_doi(self):
        assert kiem_thu_tu(["a", "b"], "b") == ["a", "b"]

    @pytest.mark.parametrize("vao", [None, []])
    def test_danh_sach_rong_ra_dung_chapter_chinh(self, vao):
        assert kiem_thu_tu(vao, "b") == ["b"]

    def test_khong_co_chapter_chinh_thi_khong_no(self):
        assert kiem_thu_tu(["a"], None) == ["a"]
