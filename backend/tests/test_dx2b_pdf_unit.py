"""ĐX-2b — test phần dựng ảnh từ PDF.

Fixture PDF dựng bằng Pillow (`Image.save(format='PDF')`) nên là PDF **thật**, không phải byte
giả — `pypdfium2` phải mở được thì bài mới có nghĩa.

Bài đáng giá nhất ở đây là `test_loi_no_ngay_luc_goi`: giống `archive.py`, nếu ai đó biến
`doc_pdf_anh` thành generator thì mọi phép kiểm trần sẽ nằm im tới lần `next()` đầu tiên, và
route bắt lỗi sai chỗ — có khi đã ghi vài trang vào CSDL rồi mới nổ.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.services.archive import ArchiveEmpty, ArchiveTooLarge, NotAnArchive
from app.services.pdf import doc_pdf_anh, la_pdf

pytest.importorskip("pypdfium2", reason="ĐX-2b cần pypdfium2 — xem backend/requirements.txt")

TRAN = dict(max_pages=200, max_page_bytes=25 * 1024 * 1024, max_px=1600)


def _pdf(so_trang: int = 3, cd: tuple[int, int] = (600, 850)) -> bytes:
    """PDF thật `so_trang` trang, mỗi trang một màu khác nhau để phân biệt được thứ tự."""
    mau = ["red", "green", "blue", "yellow", "purple", "orange"]
    anh = [Image.new("RGB", cd, mau[i % len(mau)]) for i in range(so_trang)]
    buf = io.BytesIO()
    anh[0].save(buf, format="PDF", save_all=True, append_images=anh[1:])
    return buf.getvalue()


class TestNhanDien:
    def test_xet_bang_chu_ky_dau_file_khong_xet_duoi(self):
        assert la_pdf(_pdf(1)) is True
        assert la_pdf(b"\x89PNG\r\n\x1a\n" + b"0" * 32) is False

    def test_khong_phai_pdf_thi_bao_ngay(self):
        with pytest.raises(NotAnArchive):
            doc_pdf_anh(b"day khong phai pdf", **TRAN)

    def test_pdf_hong(self):
        with pytest.raises(NotAnArchive):
            doc_pdf_anh(b"%PDF-1.7\nrac rac rac", **TRAN)


class TestDungAnh:
    def test_dung_du_so_trang_dung_thu_tu(self):
        g = doc_pdf_anh(_pdf(3), **TRAN)
        assert g.so_muc == 3
        trang = list(g)
        assert [t.ten for t in trang] == ["pdf/0001.png", "pdf/0002.png", "pdf/0003.png"]
        assert all(t.ext == ".png" for t in trang)

    def test_ten_co_dem_0_nen_thu_tu_chuoi_trung_thu_tu_trang(self):
        """10 trang: `0010` phải đứng sau `0009` kể cả khi sắp bằng chuỗi thuần."""
        ten = [t.ten for t in doc_pdf_anh(_pdf(10), **TRAN)]
        assert ten == sorted(ten), "đệm 0 sai ⇒ thứ tự trang sẽ lộn khi sắp bằng chuỗi"
        assert ten[-1] == "pdf/0010.png"

    def test_anh_dung_ra_la_PNG_that_va_dung_canh_dai(self):
        (t,) = list(doc_pdf_anh(_pdf(1, cd=(600, 850)), **{**TRAN, "max_px": 800}))
        anh = Image.open(io.BytesIO(t.data))
        assert anh.format == "PNG"
        # Trang cao hơn rộng ⇒ cạnh dài là chiều cao, phải bằng đúng trần.
        assert max(anh.size) == pytest.approx(800, abs=2)

    def test_trang_nho_van_duoc_dung_len_khong_giu_nguyen_point(self):
        """Trang PDF tính bằng point; ở tỉ lệ 1.0 một trang A4 chỉ ra ~842px, quá nhỏ để OCR."""
        (t,) = list(doc_pdf_anh(_pdf(1, cd=(300, 400)), **TRAN))
        anh = Image.open(io.BytesIO(t.data))
        assert max(anh.size) == pytest.approx(1600, abs=2)


class TestChanPdfXau:
    def test_qua_nhieu_trang(self):
        with pytest.raises(ArchiveTooLarge, match="vượt trần"):
            doc_pdf_anh(_pdf(6), **{**TRAN, "max_pages": 3})

    def test_trang_dung_ra_qua_to(self):
        with pytest.raises(ArchiveTooLarge):
            list(doc_pdf_anh(_pdf(1), **{**TRAN, "max_page_bytes": 128}))


class TestKiemSom:
    def test_loi_no_ngay_luc_goi(self):
        """**Bài canh bẫy** — giống `archive.py`. KHÔNG bọc `list()`: đó là điểm mấu chốt."""
        with pytest.raises(ArchiveTooLarge):
            doc_pdf_anh(_pdf(6), **{**TRAN, "max_pages": 3})

    def test_pdf_tot_thi_tra_ve_thu_lap_duoc_chu_khong_phai_list(self):
        g = doc_pdf_anh(_pdf(2), **TRAN)
        assert not isinstance(g, list)
        assert len(list(g)) == 2


class TestPdfRong:
    def test_pdf_khong_co_trang_nao(self):
        """PDF 0 trang phải ném rõ ràng, không im lặng trả về rỗng ⇒ "tải lên thành công 0 trang"."""
        import pypdfium2 as pdfium

        doc = pdfium.PdfDocument.new()
        buf = io.BytesIO()
        doc.save(buf)
        doc.close()
        with pytest.raises((ArchiveEmpty, NotAnArchive)):
            doc_pdf_anh(buf.getvalue(), **TRAN)
