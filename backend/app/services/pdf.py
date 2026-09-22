"""ĐX-2b — dựng ảnh từng trang PDF, để PDF vào được cùng đường với gói ZIP/CBZ.

Vì sao phải *dựng ảnh* chứ không "trích ảnh có sẵn": một trang truyện trong PDF có thể là một
ảnh nhúng, mà cũng có thể là nhiều ảnh ghép lại, hoặc ảnh nền cộng chữ vẽ vector. Trích ảnh nhúng
sẽ ra đúng trong trường hợp đầu và **sai im lặng** ở hai trường hợp sau — mất chữ, lệch khung,
hoặc ra một mảnh vụn của trang. Dựng lại cả trang cho ra đúng thứ người đọc nhìn thấy, luôn luôn.

**Ràng buộc bộ nhớ.** Dựng ảnh là chỗ dễ nổ nhất của cả tính năng: một trang PDF khổ lớn dựng ở
độ phân giải in có thể ra hàng trăm MB *cho một trang*. Ảnh `api` cố tình giữ mỏng (~1GB) và dự án
này **đã bị OOM giết worker hai lần** (E41). Nên:

- dựng theo **cạnh dài cố định** (`max_px`), không theo DPI của tài liệu;
- sinh **lần lượt từng trang**, không gom cả tập vào danh sách;
- vẫn có trần byte cho mỗi trang sau khi nén PNG.

Giống `archive.py`, hàm chính **không** phải generator: mọi phép kiểm chạy ngay lúc gọi, phần
sinh nằm ở `_sinh_trang_pdf`.
"""

from __future__ import annotations

import io
from collections.abc import Iterator

from app.services.archive import (
    ArchiveEmpty,
    ArchiveError,
    ArchiveTooLarge,
    NotAnArchive,
    TrangTrongGoi,
)

#: Mọi PDF hợp lệ bắt đầu bằng chuỗi này.
_MAGIC_PDF = b"%PDF"


class PdfCoKhoa(ArchiveError):
    """PDF đặt mật khẩu — không mở được, và **không** thử đoán mật khẩu."""


def la_pdf(data: bytes) -> bool:
    """Xét bằng chữ ký đầu file, không xét đuôi — đuôi do người gửi đặt."""
    return data.startswith(_MAGIC_PDF)


def doc_pdf_anh(
    data: bytes,
    *,
    max_pages: int,
    max_page_bytes: int,
    max_px: int,
) -> "GoiPdf":
    """Mở PDF → `GoiPdf`: số trang + đường sinh lần lượt từng trang đã dựng thành PNG.

    Ném `ArchiveError` (hoặc lớp con) khi không dùng được, để route đổi sang HTTP 4xx bằng đúng
    một chỗ xử lý chung với đường ZIP/CBZ.
    """
    if not la_pdf(data):
        raise NotAnArchive("File không phải PDF hợp lệ")

    try:
        import pypdfium2 as pdfium
    except ImportError as exc:  # pragma: no cover - chỉ xảy ra khi image dựng thiếu gói
        raise ArchiveError(
            "pdf_thieu_thu_vien: máy chủ chưa cài pypdfium2 nên chưa đọc được PDF"
        ) from exc

    try:
        tai_lieu = pdfium.PdfDocument(io.BytesIO(data))
    except pdfium.PdfiumError as exc:
        # pypdfium2 gộp cả "hỏng" lẫn "có mật khẩu" vào một loại lỗi; phân biệt bằng nội dung để
        # người dùng biết phải làm gì (gỡ mật khẩu vs. xuất lại file).
        if "password" in str(exc).lower():
            raise PdfCoKhoa(
                "PDF này đặt mật khẩu — hãy gỡ mật khẩu rồi tải lên lại"
            ) from exc
        raise NotAnArchive(f"PDF hỏng, không mở được: {exc}") from exc

    try:
        so_trang = len(tai_lieu)
        if so_trang == 0:
            raise ArchiveEmpty("PDF không có trang nào")
        if so_trang > max_pages:
            raise ArchiveTooLarge(
                f"PDF có {so_trang} trang, vượt trần {max_pages} trang mỗi lần tải lên"
            )
    except BaseException:
        tai_lieu.close()
        raise

    return GoiPdf(so_trang, _sinh_trang_pdf(tai_lieu, so_trang, max_page_bytes, max_px))


def _ti_le(rong: float, cao: float, max_px: int) -> float:
    """Hệ số dựng sao cho cạnh DÀI ra đúng `max_px`.

    Không bao giờ phóng to trang nhỏ lên (`min(..., 1.0)` phía gọi không làm việc đó vì trang PDF
    tính bằng point chứ không phải pixel — 1 point ở tỉ lệ 1.0 ra 1 pixel, nên trang A4 ra ~842px
    và việc nâng lên 1600 là cần thiết, không phải phóng đại dữ liệu).
    """
    canh_dai = max(rong, cao)
    if canh_dai <= 0:
        return 1.0
    return max_px / canh_dai


def _sinh_trang_pdf(
    tai_lieu, so_trang: int, max_page_bytes: int, max_px: int
) -> Iterator[TrangTrongGoi]:
    """Dựng từng trang một. Chịu trách nhiệm đóng tài liệu kể cả khi người gọi bỏ dở."""
    try:
        for i in range(so_trang):
            trang = tai_lieu[i]
            rong, cao = trang.get_size()
            anh = trang.render(scale=_ti_le(rong, cao, max_px)).to_pil()
            buf = io.BytesIO()
            anh.save(buf, format="PNG")
            noi_dung = buf.getvalue()
            # Giải phóng ngay: trang sau không có lý do gì phải chờ trang trước được dọn.
            anh.close()
            trang.close()

            if len(noi_dung) > max_page_bytes:
                raise ArchiveTooLarge(
                    f"Trang {i + 1} của PDF dựng ra {len(noi_dung) // (1024 * 1024)}MB, "
                    f"vượt trần {max_page_bytes // (1024 * 1024)}MB"
                )
            # Tên đặt theo số thứ tự có đệm 0 để thứ tự tự nhiên trùng luôn với thứ tự trang gốc.
            yield TrangTrongGoi(
                ten=f"pdf/{i + 1:04d}.png", data=noi_dung, ext=".png"
            )
    finally:
        tai_lieu.close()


class GoiPdf:
    """Kết quả mở PDF: **số trang thật** + đường sinh lần lượt.

    Cùng hình dạng với `GoiAnh` của `archive.py` (`so_muc` + lặp được) nên route dùng chung đúng
    một nhánh xử lý cho cả PDF lẫn ZIP/CBZ, thay vì hai nhánh gần giống nhau rồi lệch dần.
    """

    def __init__(self, so_trang: int, nguon: Iterator[TrangTrongGoi]):
        #: PDF không có mục "không phải ảnh" nào để bỏ qua ⇒ `so_muc` luôn bằng số trang thật,
        #: nên `bo_qua` mà route tính ra luôn là 0. Đó là sự thật, không phải chỗ chưa làm.
        self.so_muc = so_trang
        self._nguon = nguon

    def __iter__(self) -> Iterator[TrangTrongGoi]:
        return self._nguon

    def __next__(self) -> TrangTrongGoi:
        return next(self._nguon)
