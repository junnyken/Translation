"""ĐX-2 — test phần đọc gói ZIP/CBZ.

Test thuần, không CSDL: gói tự dựng trong bộ nhớ nên mỗi cạm bẫy kiểm được riêng rẽ.

Bài quan trọng nhất trong file này là `test_loi_no_ngay_luc_goi_chu_khong_doi_toi_luc_lap` —
nó canh đúng cái bẫy đã suýt lọt lúc viết: nếu `doc_goi_anh` là generator thì mọi phép kiểm
trần nằm im cho tới lần `next()` đầu tiên, và route sẽ bắt lỗi sai chỗ (có khi đã ghi vài trang
vào CSDL rồi mới nổ). Bài đó đỏ ngay nếu ai đó biến hàm này thành generator lần nữa.
"""

from __future__ import annotations

import io
import zipfile

import pytest
from PIL import Image

from app.services.archive import (
    ArchiveEmpty,
    ArchiveTooLarge,
    ArchiveUnsafe,
    NotAnArchive,
    doc_goi_anh,
    khoa_tu_nhien,
    la_goi_nen,
)

TRAN = dict(max_pages=200, max_total_bytes=500 * 1024 * 1024, max_page_bytes=25 * 1024 * 1024)


def anh_png(mau: str = "white", cd: tuple[int, int] = (8, 8)) -> bytes:
    """Ảnh PNG thật (không phải byte giả) — `sniff_image` xét magic nên phải là ảnh thật."""
    buf = io.BytesIO()
    Image.new("RGB", cd, mau).save(buf, format="PNG")
    return buf.getvalue()


def dung_goi(muc: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for ten, data in muc.items():
            zf.writestr(ten, data)
    return buf.getvalue()


class TestThuTuTrang:
    def test_sap_theo_so_tu_nhien_khong_theo_chuoi(self):
        """`p10` phải đứng SAU `p2`. Sắp theo chuỗi thuần sẽ đảo trang mà không báo lỗi gì."""
        goi = dung_goi({f"p{i}.png": anh_png() for i in (1, 2, 10, 11, 3)})
        ten = [t.ten for t in doc_goi_anh(goi, **TRAN)]
        assert ten == ["p1.png", "p2.png", "p3.png", "p10.png", "p11.png"]

    def test_khoa_tu_nhien_so_duoc_voi_ten_khac_cau_truc(self):
        """Hai tên khác cấu trúc vẫn so được — không ném TypeError khi sắp."""
        assert sorted(["b.png", "a2.png", "a10.png"], key=khoa_tu_nhien) == [
            "a2.png", "a10.png", "b.png",
        ]

    def test_thu_muc_long_nhau_van_sap_theo_ten_file(self):
        goi = dung_goi({"ch/02.png": anh_png(), "ch/10.png": anh_png(), "ch/1.png": anh_png()})
        assert [t.ten for t in doc_goi_anh(goi, **TRAN)] == ["ch/1.png", "ch/02.png", "ch/10.png"]


class TestBoQuaRac:
    def test_bo_qua_macosx_dotfile_va_metadata(self):
        goi = dung_goi({
            "01.png": anh_png(),
            "__MACOSX/._01.png": b"rac",
            ".DS_Store": b"rac",
            "ComicInfo.xml": b"<ComicInfo/>",
            "02.png": anh_png(),
        })
        assert [t.ten for t in doc_goi_anh(goi, **TRAN)] == ["01.png", "02.png"]

    def test_goi_long_goi_bi_bo_qua_khong_de_quy(self):
        """Gói trong gói là mục không phải ảnh ⇒ bỏ qua, tuyệt đối không giải nén tiếp."""
        goi = dung_goi({"01.png": anh_png(), "trong.zip": dung_goi({"x.png": anh_png()})})
        assert [t.ten for t in doc_goi_anh(goi, **TRAN)] == ["01.png"]

    def test_chi_co_metadata_thi_bao_rong_chu_khong_tra_ve_khong_trang(self):
        """Trả danh sách rỗng sẽ thành 'tải lên thành công 0 trang' — thành công giả."""
        goi = dung_goi({"ComicInfo.xml": b"<ComicInfo/>"})
        with pytest.raises(ArchiveEmpty):
            list(doc_goi_anh(goi, **TRAN))


class TestChanGoiXau:
    def test_khong_phai_zip(self):
        with pytest.raises(NotAnArchive):
            doc_goi_anh(anh_png(), **TRAN)

    def test_zip_hong(self):
        hong = b"PK\x03\x04" + b"\x00" * 64
        with pytest.raises(NotAnArchive):
            doc_goi_anh(hong, **TRAN)

    def test_duoi_file_khong_quyet_dinh_gi_chi_magic_moi_quyet_dinh(self):
        assert la_goi_nen(dung_goi({"01.png": anh_png()})) is True
        assert la_goi_nen(anh_png()) is False

    @pytest.mark.parametrize(
        "ten_xau", ["../thoat.png", "/tuyet_doi.png", "a/../../thoat.png", "C:/windows/x.png"],
    )
    def test_chan_duong_dan_thoat_thu_muc(self, ten_xau):
        goi = dung_goi({ten_xau: anh_png(), "01.png": anh_png()})
        with pytest.raises(ArchiveUnsafe):
            doc_goi_anh(goi, **TRAN)

    def test_ten_xau_khong_nup_duoc_sau_ve_ngoai_file_rac(self):
        """Kiểm an toàn chạy TRƯỚC khi lọc rác — nếu lọc trước thì `__MACOSX/../x` lọt."""
        goi = dung_goi({"__MACOSX/../../thoat.png": anh_png(), "01.png": anh_png()})
        with pytest.raises(ArchiveUnsafe):
            doc_goi_anh(goi, **TRAN)

    def test_qua_nhieu_trang(self):
        goi = dung_goi({f"{i:04d}.png": anh_png() for i in range(12)})
        with pytest.raises(ArchiveTooLarge, match="vượt trần"):
            doc_goi_anh(goi, **{**TRAN, "max_pages": 10})

    def test_bom_giai_nen_bi_chan_TRUOC_khi_bung(self):
        """Gói bé tí khai bung ra rất lớn — chặn bằng `file_size` trong header, không bung thử."""
        goi = dung_goi({"bom.png": b"\x00" * (8 * 1024 * 1024)})
        assert len(goi) < 100 * 1024  # nén lại còn tí xíu — đúng hình dạng một quả bom
        with pytest.raises(ArchiveTooLarge, match="bung ra"):
            doc_goi_anh(goi, **{**TRAN, "max_total_bytes": 1024 * 1024})

    def test_mot_trang_qua_lon(self):
        goi = dung_goi({"to.png": anh_png(cd=(600, 600))})
        with pytest.raises(ArchiveTooLarge):
            list(doc_goi_anh(goi, **{**TRAN, "max_page_bytes": 256}))


class TestKiemSom:
    def test_loi_no_ngay_luc_goi_chu_khong_doi_toi_luc_lap(self):
        """**Bài canh bẫy.** Mọi phép kiểm trần phải nổ tại LỜI GỌI, không phải lúc lặp.

        Biến `doc_goi_anh` thành generator (viết `yield` thẳng vào thân) sẽ làm bài này đỏ:
        thân generator không chạy dòng nào cho tới `next()` đầu tiên, nên route sẽ bắt lỗi sai
        chỗ — có khi đã ghi được vài trang vào CSDL rồi mới nổ.
        """
        goi = dung_goi({f"{i:04d}.png": anh_png() for i in range(12)})
        with pytest.raises(ArchiveTooLarge):
            doc_goi_anh(goi, **{**TRAN, "max_pages": 10})  # KHÔNG bọc list() — đây là điểm mấu chốt

    def test_goi_tot_thi_chua_doc_byte_nao_truoc_khi_lap(self):
        """Đối chứng: gói hợp lệ trả iterator, và trang chỉ được đọc khi thực sự lặp tới."""
        goi = dung_goi({"01.png": anh_png(), "02.png": anh_png()})
        it = doc_goi_anh(goi, **TRAN)
        assert not isinstance(it, list)
        assert [t.ten for t in it] == ["01.png", "02.png"]


class TestDemMucBoQua:
    """`so_muc` phải là số ĐẾM THẬT — chỗ gọi lấy nó trừ đi số trang để báo "bỏ qua mấy mục".

    Bản viết đầu tiên lấy con số này bằng `getattr(..., 0)` trên một generator không hề có
    thuộc tính đó ⇒ luôn ra 0, tức là một con số **bịa** hiển thị cho người dùng. Bài này canh
    đúng chỗ đó.
    """

    def test_so_muc_dem_ung_vien_that(self):
        goi = dung_goi({"01.png": anh_png(), "ComicInfo.xml": b"<x/>", "02.png": anh_png()})
        g = doc_goi_anh(goi, **TRAN)
        assert g.so_muc == 3  # 2 ảnh + 1 metadata
        assert len(list(g)) == 2
        assert g.so_muc - 2 == 1  # đúng 1 mục bị bỏ qua

    def test_rac_biet_truoc_khong_tinh_la_bo_qua(self):
        """`__MACOSX/` và dotfile bị loại khỏi ứng viên — không báo là "bỏ qua" cho người dùng,
        vì đó là rác hệ điều hành tự nhét vào, không phải file của họ."""
        goi = dung_goi({"01.png": anh_png(), "__MACOSX/._01.png": b"r", ".DS_Store": b"r"})
        g = doc_goi_anh(goi, **TRAN)
        assert g.so_muc == 1
        assert len(list(g)) == 1


class TestNoiDung:
    def test_tra_ve_dung_byte_va_duoi_file(self):
        png = anh_png("red")
        (trang,) = list(doc_goi_anh(dung_goi({"01.png": png}), **TRAN))
        assert trang.data == png
        assert trang.ext == ".png"

    def test_nhan_ca_jpeg_va_webp(self):
        buf_j, buf_w = io.BytesIO(), io.BytesIO()
        Image.new("RGB", (8, 8), "blue").save(buf_j, format="JPEG")
        Image.new("RGB", (8, 8), "blue").save(buf_w, format="WEBP")
        goi = dung_goi({"01.jpg": buf_j.getvalue(), "02.webp": buf_w.getvalue()})
        assert [t.ext for t in doc_goi_anh(goi, **TRAN)] == [".jpg", ".webp"]
