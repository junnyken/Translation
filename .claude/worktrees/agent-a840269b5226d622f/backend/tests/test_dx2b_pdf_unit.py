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


def _pdf_chu_vector(chu: str = "HELLO", cd: tuple[int, int] = (200, 200)) -> bytes:
    """PDF chỉ chứa **chữ vector**, KHÔNG có một ảnh nhúng nào.

    Dựng tay vì repo không có thư viện tạo PDF, và thêm một phụ thuộc chỉ để dựng fixture thì
    không đáng. PDF là định dạng văn bản nên viết tay được; phần duy nhất phải cẩn thận là bảng
    `xref` — nó ghi VỊ TRÍ BYTE của từng object, sai một byte là tệp hỏng.
    """
    rong, cao = cd
    noi_dung = f"BT /F1 48 Tf 20 {cao // 2} Td ({chu}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {rong} {cao}] /Contents 4 0 R "
        f"/Resources << /Font << /F1 5 0 R >> >> >>".encode(),
        b"<< /Length " + str(len(noi_dung)).encode() + b" >>\nstream\n" + noi_dung + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    ra = bytearray(b"%PDF-1.4\n")
    viTri = []
    for i, o in enumerate(objs, start=1):
        viTri.append(len(ra))
        ra += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    batDauXref = len(ra)
    ra += f"xref\n0 {len(objs) + 1}\n".encode() + b"0000000000 65535 f \n"
    for v in viTri:
        ra += f"{v:010d} 00000 n \n".encode()
    ra += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{batDauXref}\n%%EOF\n".encode()
    return bytes(ra)


class TestChuVectorKhongBiMat:
    """**Bài chứng minh quyết định thiết kế**, không phải bài kiểm cú pháp.

    `pdf.py` tuyên bố: phải DỰNG LẠI cả trang chứ không trích ảnh nhúng, vì trang truyện có thể
    là ảnh nền cộng chữ vector và trích ảnh sẽ **mất chữ mà không báo lỗi**. Mọi fixture PDF khác
    trong file này đều do Pillow dựng — tức là ảnh thuần, KHÔNG có một nét vector nào, nên chúng
    xanh kể cả khi ai đó đổi sang trích ảnh nhúng.

    Trang ở đây chỉ có chữ vector và không có ảnh nhúng nào. Đổi sang trích ảnh ⇒ ra trang
    TRẮNG TRƠN ⇒ bài này đỏ.
    """

    def test_chu_vector_phai_ra_MUC_that_tren_anh_dung_ra(self):
        (t,) = list(doc_pdf_anh(_pdf_chu_vector(), **TRAN))
        anh = Image.open(io.BytesIO(t.data)).convert("L")
        mau = anh.getcolors(maxcolors=256 * 256) or []
        so_diem_toi = sum(n for n, gia_tri in mau if gia_tri < 128)
        assert so_diem_toi > 50, (
            "Trang chỉ có chữ vector lại dựng ra gần như trắng trơn — nhiều khả năng đường dựng "
            f"đã bị đổi thành trích ảnh nhúng, và chữ bị mất im lặng (điểm tối: {so_diem_toi})"
        )

    def test_doi_chung_am_trang_that_su_trong_thi_KHONG_co_muc(self):
        """Chống xanh rỗng: nếu phép đếm điểm tối luôn dương thì bài trên vô nghĩa."""
        (t,) = list(doc_pdf_anh(_pdf_chu_vector(chu=" "), **TRAN))
        anh = Image.open(io.BytesIO(t.data)).convert("L")
        mau = anh.getcolors(maxcolors=256 * 256) or []
        assert sum(n for n, gia_tri in mau if gia_tri < 128) < 50


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
