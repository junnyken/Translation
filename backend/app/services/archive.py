"""ĐX-2 — đọc gói ZIP/CBZ thành danh sách trang ảnh theo đúng thứ tự.

Vì sao tách ra module riêng thay vì viết thẳng trong route: phần nguy hiểm của tính năng này
KHÔNG nằm ở HTTP mà nằm ở chỗ giải nén dữ liệu người lạ gửi lên. Tách ra thì test được từng
cạm bẫy bằng gói tự dựng, không cần dựng cả request.

**Bốn thứ được chặn, và chặn ở đâu:**

1. **Bom giải nén** — gói 1MB khai bung ra 50GB. Chặn bằng cách cộng `ZipInfo.file_size` của
   mọi mục **TRƯỚC KHI đọc byte nào**, rồi vẫn đọc có trần (`max_page_bytes + 1`) vì con số
   khai trong header là do kẻ gửi tự khai — tin nó một mình là hớ.
2. **Đường dẫn thoát thư mục** (`../../etc/passwd`, `/etc/passwd`). Lưu ý cho người đọc sau:
   ở đây đây là **phòng thủ theo chiều sâu, không phải lớp chặn duy nhất** — ảnh được lưu bằng
   `storage.save_page_image(project_id, page_id, ...)`, tức tên file trong gói **không bao giờ**
   được dùng làm đường dẫn ghi đĩa. Vẫn chặn vì lớp lưu trữ có thể đổi, và một cái tên như thế
   là dấu hiệu gói có ý đồ.
3. **Gói lồng gói** — `.zip` trong `.zip`. Không đệ quy: mục không phải ảnh thì bỏ qua.
4. **Quá nhiều mục** — gói chứa 100.000 file rỗng. Chặn bằng trần số trang.

**Thứ tự trang** dùng khoá tự nhiên: `p2.jpg` đứng trước `p10.jpg`. Sắp bằng thứ tự chuỗi thuần
sẽ ra `p10` trước `p2` — chapter đảo lộn trang mà không báo lỗi gì, đúng loại hỏng im lặng khó
phát hiện nhất vì file vẫn xuất ra bình thường.
"""

from __future__ import annotations

import io
import re
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import PurePosixPath

from app.services.storage import UnsupportedImage, sniff_image

#: Chữ ký đầu file của mọi biến thể ZIP. `.cbz` chỉ là `.zip` đổi đuôi — không có magic riêng.
_MAGIC_ZIP = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")

#: Thư mục rác macOS nhét vào mọi gói nén tạo trên Finder. Chứa file `._xxx` không phải ảnh.
_RAC = ("__MACOSX/", "__macosx/")


class ArchiveError(Exception):
    """Gốc cho mọi lỗi đọc gói. Route đổi thành HTTP 4xx kèm nguyên văn thông điệp."""


class NotAnArchive(ArchiveError):
    """Không phải ZIP/CBZ hợp lệ."""


class ArchiveTooLarge(ArchiveError):
    """Vượt trần: quá nhiều trang, hoặc bung ra quá lớn."""


class ArchiveEmpty(ArchiveError):
    """Đọc được gói nhưng bên trong không có ảnh nào dùng được."""


class ArchiveUnsafe(ArchiveError):
    """Gói chứa đường dẫn có ý đồ thoát thư mục."""


@dataclass(frozen=True)
class TrangTrongGoi:
    """Một trang đọc được từ gói.

    `ten` giữ nguyên đường dẫn trong gói để báo lỗi còn chỉ được đúng file nào, và để test
    khẳng định được thứ tự.
    """

    ten: str
    data: bytes
    ext: str


def la_goi_nen(data: bytes) -> bool:
    """Có phải ZIP/CBZ không — xét bằng **chữ ký đầu file**, không xét phần mở rộng.

    Đuôi file do người gửi đặt, đổi `.exe` thành `.cbz` mất một giây.
    """
    return data.startswith(_MAGIC_ZIP)


_SO = re.compile(r"(\d+)")


def khoa_tu_nhien(ten: str) -> tuple:
    """Khoá sắp xếp tự nhiên: tách cụm số ra so bằng số, phần còn lại so bằng chữ thường.

    `p2.jpg` < `p10.jpg` (so chuỗi thuần sẽ cho ngược lại).
    Trả tuple xen kẽ `(str, int, str, int, …)` nên hai tên khác cấu trúc vẫn so được với nhau
    mà không ném `TypeError`.
    """
    phan = _SO.split(PurePosixPath(ten).name.lower())
    return tuple(int(p) if p.isdigit() else p for p in phan)


def _an_toan(ten: str) -> bool:
    """Tên mục trong gói có vô hại không (phòng thủ theo chiều sâu — xem docstring module)."""
    chuan = ten.replace("\\", "/")
    if chuan.startswith("/"):
        return False
    p = PurePosixPath(chuan)
    if p.is_absolute() or any(phan == ".." for phan in p.parts):
        return False
    # Ổ đĩa kiểu Windows: `C:/…`. PurePosixPath không coi đây là tuyệt đối.
    return not re.match(r"^[a-zA-Z]:", chuan)


def _bo_qua(ten: str) -> bool:
    """Mục rác biết trước — bỏ qua lặng lẽ, không tính là lỗi của người dùng."""
    if ten.startswith(_RAC):
        return True
    ten_file = PurePosixPath(ten).name
    return not ten_file or ten_file.startswith(".")


def doc_goi_anh(
    data: bytes,
    *,
    max_pages: int,
    max_total_bytes: int,
    max_page_bytes: int,
) -> GoiAnh:
    """Đọc gói → `GoiAnh`: số mục ứng viên + đường **sinh lần lượt** từng trang theo thứ tự đọc.

    **Vì sao là generator chứ không trả về list:** gom cả gói vào một list giữ toàn bộ ảnh đã
    bung trong RAM cùng lúc — với trần 200MB thì đó là 200MB nằm trong tiến trình API, cộng thêm
    chính gói nén. Container API cố tình giữ mỏng (~1GB, không chứa thư viện AI) và dự án này
    **đã bị OOM giết worker hai lần** (E41) nên đây không phải lo xa. Sinh lần lượt thì lúc nào
    cũng chỉ có đúng MỘT trang (tối đa `max_page_bytes`) trong bộ nhớ.

    **Hàm này KHÔNG phải generator** (phần sinh nằm ở `_sinh_trang`), và đó là chủ đích: thân
    một generator không chạy một dòng nào cho tới lần `next()` đầu tiên, nên nếu viết thẳng
    `yield` vào đây thì mọi phép kiểm trần bên dưới sẽ **không nổ lúc gọi** mà nổ lúc route bắt
    đầu lặp — tức là sai chỗ bắt lỗi, và có khi đã ghi vài trang vào CSDL rồi mới nổ. Tách ra
    thế này thì gói xấu bị chặn ngay tại lời gọi, trước khi chạm vào CSDL.

    Ném `ArchiveError` (hoặc lớp con) khi gói không dùng được. Hết gói mà **không sinh được trang
    nào** thì ném `ArchiveEmpty` — tuyệt đối không im lặng kết thúc, vì thế sẽ thành "tải lên
    thành công 0 trang", một kiểu thành công giả.

    Mục không phải ảnh (`ComicInfo.xml`, `Thumbs.db`, gói lồng gói) bị **bỏ qua lặng lẽ**: gói
    CBZ thật hay kèm metadata, bắt lỗi cả gói vì một file xml là đuổi người dùng đi vô cớ.
    """
    if not la_goi_nen(data):
        raise NotAnArchive("File không phải gói ZIP/CBZ hợp lệ")

    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise NotAnArchive(f"Gói nén hỏng, không mở được: {exc}") from exc

    try:
        # Ném sớm nếu chính bảng mục lục đã có tên có ý đồ — kiểm TRƯỚC khi lọc rác, để một gói
        # độc không núp được sau cái tên trông như file rác.
        for info in zf.infolist():
            if not _an_toan(info.filename):
                raise ArchiveUnsafe(
                    f"Gói chứa đường dẫn không an toàn: {info.filename!r}"
                )

        ung_vien = [
            info
            for info in zf.infolist()
            if not info.is_dir() and not _bo_qua(info.filename)
        ]
        if len(ung_vien) > max_pages:
            raise ArchiveTooLarge(
                f"Gói có {len(ung_vien)} mục, vượt trần {max_pages} trang mỗi lần tải lên"
            )

        # Trần TỔNG dung lượng sau khi bung — cộng theo số khai trong header, tức là chặn được
        # bom giải nén mà KHÔNG phải bung thử cái gì.
        tong_khai = sum(info.file_size for info in ung_vien)
        if tong_khai > max_total_bytes:
            raise ArchiveTooLarge(
                f"Gói bung ra {tong_khai // (1024 * 1024)}MB, vượt trần "
                f"{max_total_bytes // (1024 * 1024)}MB"
            )
    except BaseException:
        # Kiểm hỏng thì đóng gói ngay — không có generator nào sẽ chạy để đóng hộ.
        zf.close()
        raise

    ung_vien.sort(key=lambda i: khoa_tu_nhien(i.filename))
    return GoiAnh(len(ung_vien), _sinh_trang(zf, ung_vien, max_page_bytes))


class GoiAnh:
    """Kết quả mở gói: **số mục ứng viên** (biết ngay) + đường sinh từng trang.

    Vì sao cần `so_muc` chứ không chỉ trả iterator: người gọi cần nói được "gói 20 file mà chỉ
    vào 18 trang, 2 file kia bị bỏ qua". Không có con số này thì chỗ gọi hoặc phải im lặng, hoặc
    phải **đoán** — và một con số đoán hiển thị cho người dùng thì tệ hơn là không hiện gì.

    `so_muc` đếm mục ứng viên *sau* khi lọc thư mục và file rác biết trước (`__MACOSX/`,
    dotfile), *trước* khi thử đọc ảnh. Số trang thật chỉ biết sau khi lặp hết — hiệu hai số
    chính là số mục không phải ảnh (metadata, gói lồng gói).
    """

    def __init__(self, so_muc: int, nguon: Iterator[TrangTrongGoi]):
        self.so_muc = so_muc
        self._nguon = nguon

    def __iter__(self) -> Iterator[TrangTrongGoi]:
        return self._nguon

    def __next__(self) -> TrangTrongGoi:
        return next(self._nguon)


def _sinh_trang(
    zf: zipfile.ZipFile, ung_vien: list[zipfile.ZipInfo], max_page_bytes: int
) -> Iterator[TrangTrongGoi]:
    """Phần sinh lần lượt của `doc_goi_anh` — đã qua hết phép kiểm, chỉ còn đọc.

    Nhận `zf` đang mở và **chịu trách nhiệm đóng nó** (kể cả khi người gọi bỏ dở giữa chừng:
    `with` chạy khi generator bị dọn).
    """
    with zf:
        da_sinh = 0
        for info in ung_vien:
            with zf.open(info) as f:
                # Đọc dư 1 byte: đủ để biết file DÀI HƠN mức khai mà không nuốt cả file khổng lồ
                # vào bộ nhớ. Số `file_size` trong header là lời khai của kẻ gửi, không phải sự thật.
                noi_dung = f.read(max_page_bytes + 1)
            if len(noi_dung) > max_page_bytes:
                raise ArchiveTooLarge(
                    f"Trang {info.filename!r} vượt {max_page_bytes // (1024 * 1024)}MB"
                )
            try:
                _mime, ext = sniff_image(noi_dung)
            except UnsupportedImage:
                continue  # metadata, gói lồng gói, file rác — bỏ qua, không phải lỗi
            da_sinh += 1
            yield TrangTrongGoi(ten=info.filename, data=noi_dung, ext=ext)

        if da_sinh == 0:
            raise ArchiveEmpty(
                "Gói mở được nhưng không có ảnh JPEG/PNG/WEBP nào bên trong"
            )
