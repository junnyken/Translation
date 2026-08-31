"""Lưu hiện vật: ảnh gốc, ảnh clean, ảnh xem thử, file xuất.

M1 hiện thực backend `local` (thư mục trên đĩa). Backend `supabase` CHƯA implement — khi cấu
hình STORAGE_BACKEND=supabase, app fail ngay lúc khởi tạo thay vì im lặng ghi sai chỗ.

## P3c — vì sao không còn `abs_path()`

Trước P3c, `abs_path()` là **hợp đồng đọc/ghi**: bên gọi xin một đường dẫn tuyệt đối rồi tự mở
tệp, hoặc đưa đường dẫn đó cho engine tự ghi vào. Hợp đồng ấy **trói chặt hệ thống vào một hệ
tệp cục bộ** — không kho đối tượng nào (Postgres, S3, Supabase) phục vụ được kiểu gọi đó.

P3c đã dò và kết luận VibeHost **không cấp được volume bền**, nên hiện vật ghi ra hệ tệp
container mất sạch mỗi lần triển khai lại. Lối thoát chỉ còn CSDL hoặc kho đối tượng ngoài — và
**cả hai đều đòi bỏ hợp đồng này trước**. Xem `docs/REPORT_P3c_STORAGE_CAPABILITY_PROBE.md`.

Thay bằng bộ primitive không giả định hệ tệp:

- đọc thẳng    : `read` / `open_read` / `exists` / `stat`
- ghi nguyên tử: `save` (temp + `os.replace`, không bao giờ để lại tệp ghi dở)
- liệt kê/xoá  : `list_prefix` / `delete_prefix` / `delete`
- **ranh giới vật chất hoá**: `workspace()` + `fetch_to()` — engine bên thứ ba (LaMa, OCR, PIL,
  bộ xuất) **bắt buộc** cần đường dẫn thật, nên ta chép hiện vật ra một thư mục tạm, để engine
  làm việc ở đó, rồi `save()` kết quả ngược vào kho. Thư mục tạm luôn bị dọn.

Chép thêm vài MB là cái giá rẻ so với một lượt chạy model — và nó là thứ khiến đổi backend chỉ
còn là viết một lớp mới, không phải sờ lại từng chỗ gọi.
"""
from __future__ import annotations

import os
import shutil
import stat as _stat
import tempfile
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import BinaryIO, NamedTuple, Protocol

from app.core.config import Settings, get_settings

# Magic bytes để xác nhận file thật sự là ảnh (không tin content-type client gửi).
_MAGIC = {
    b"\xff\xd8\xff": ("image/jpeg", ".jpg"),
    b"\x89PNG\r\n\x1a\n": ("image/png", ".png"),
}


class UnsupportedImage(ValueError):
    pass


class UnsafeObjectPath(ValueError):
    """Path tương đối vượt ra ngoài gốc lưu trữ — từ chối thay vì đọc/ghi nhầm chỗ."""


class ObjectStat(NamedTuple):
    """Siêu dữ liệu tối thiểu mà MỌI backend đều cấp được.

    `mtime` là epoch giây. Backend không có mtime thật (kho đối tượng) thì dùng thời điểm ghi
    bản hiện hành — điều kho vân tay E14 cần chỉ là "đổi khi nội dung đổi".
    """

    size: int
    mtime: int


def sniff_image(data: bytes) -> tuple[str, str]:
    """Trả (mime, extension) nếu là JPEG/PNG thật; ném UnsupportedImage nếu không."""
    for magic, (mime, ext) in _MAGIC.items():
        if data.startswith(magic):
            return mime, ext
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", ".webp"
    raise UnsupportedImage("File upload không phải ảnh JPEG/PNG/WEBP hợp lệ")


def chuan_hoa_path(rel: str) -> str:
    """Kiểm và chuẩn hoá một path tương đối dùng làm khoá hiện vật.

    Chặn 3 thứ, vì `root / rel` của Path im lặng cho qua cả ba:
      - path tuyệt đối: `root / "/etc/passwd"` -> `/etc/passwd` (NUỐT luôn root)
      - `..`          : `root / "../../etc/passwd"` -> thoát khỏi root
      - path rỗng     : `root / ""` -> chính root
    """
    if not rel or not rel.strip():
        raise UnsafeObjectPath("Path hiện vật rỗng")
    p = PurePosixPath(rel.replace("\\", "/"))
    if p.is_absolute():
        raise UnsafeObjectPath(f"Path hiện vật phải là tương đối, nhận được: {rel!r}")
    if ".." in p.parts:
        raise UnsafeObjectPath(f"Path hiện vật chứa '..': {rel!r}")
    sach = "/".join(part for part in p.parts if part != ".")
    if not sach:
        raise UnsafeObjectPath(f"Path hiện vật rỗng sau khi chuẩn hoá: {rel!r}")
    return sach


@contextmanager
def workspace(prefix: str = "translation-ws-") -> Iterator[Path]:
    """Thư mục tạm cục bộ cho engine bên thứ ba làm việc. LUÔN được dọn, kể cả khi lỗi.

    Đây là chỗ duy nhất trong hệ thống được phép có "đường dẫn thật" — và nó nằm ngoài kho,
    nên không backend nào bị ràng buộc phải là hệ tệp.
    """
    d = Path(tempfile.mkdtemp(prefix=prefix))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


class IObjectStorage(Protocol):
    def save_page_image(self, project_id: uuid.UUID, page_id: uuid.UUID, data: bytes, ext: str) -> str:
        """Lưu ảnh gốc, trả về path tương đối đã lưu."""
        ...

    def save(self, path: str, data: bytes) -> str:
        """Ghi NGUYÊN TỬ. Trả path tương đối đã chuẩn hoá."""
        ...

    def save_file(self, path: str, source: Path) -> str:
        """Như `save` nhưng nguồn là một tệp cục bộ (khỏi nạp cả tệp lớn vào RAM)."""
        ...

    def read(self, path: str) -> bytes:
        ...

    def open_read(self, path: str) -> BinaryIO:
        """Luồng đọc. Bên gọi phải đóng (dùng `with`)."""
        ...

    def exists(self, path: str) -> bool:
        ...

    def stat(self, path: str) -> ObjectStat | None:
        """None nếu không có hiện vật — dùng cho vân tay E14 và Content-Length khi phục vụ HTTP."""
        ...

    def delete(self, path: str) -> bool:
        """Xoá (idempotent guard của M4). True nếu có gì để xoá."""
        ...

    def list_prefix(self, prefix: str) -> list[str]:
        """Path tương đối của mọi hiện vật dưới một tiền tố, đã sắp xếp."""
        ...

    def delete_prefix(self, prefix: str) -> list[str]:
        """Xoá mọi hiện vật dưới tiền tố. Trả danh sách đã xoá (để ghi log, không đoán)."""
        ...

    def fetch_to(self, path: str, dest: Path) -> Path:
        """Chép hiện vật ra một đường dẫn cục bộ trong `workspace()` cho engine dùng."""
        ...


class LocalObjectStorage:
    """Lưu xuống thư mục: <root>/projects/<project_id>/pages/<page_id><ext>"""

    def __init__(self, root: str) -> None:
        self.root = Path(root)

    # ---------- nội bộ ----------
    def _abs(self, rel: str) -> Path:
        """Đường dẫn thật. **Nội bộ** — không lộ ra ngoài lớp này (xem docstring đầu tệp)."""
        sach = chuan_hoa_path(rel)
        goc = self.root.resolve()
        dich = (goc / sach).resolve()
        # Chặn cả trường hợp symlink trong kho trỏ ra ngoài.
        if dich != goc and goc not in dich.parents:
            raise UnsafeObjectPath(f"Path hiện vật thoát khỏi gốc lưu trữ: {rel!r}")
        return dich

    # ---------- ghi ----------
    def save(self, path: str, data: bytes) -> str:
        sach = chuan_hoa_path(path)
        target = self._abs(sach)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tam = tempfile.mkstemp(dir=str(target.parent), prefix=".ghi-do-", suffix=".part")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tam, target)  # nguyên tử trên cùng filesystem
        except BaseException:
            Path(tam).unlink(missing_ok=True)
            raise
        return sach

    def save_file(self, path: str, source: Path) -> str:
        sach = chuan_hoa_path(path)
        target = self._abs(sach)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tam = tempfile.mkstemp(dir=str(target.parent), prefix=".ghi-do-", suffix=".part")
        try:
            with os.fdopen(fd, "wb") as out, Path(source).open("rb") as src:
                shutil.copyfileobj(src, out)
                out.flush()
                os.fsync(out.fileno())
            os.replace(tam, target)
        except BaseException:
            Path(tam).unlink(missing_ok=True)
            raise
        return sach

    def save_page_image(self, project_id: uuid.UUID, page_id: uuid.UUID, data: bytes, ext: str) -> str:
        return self.save(f"projects/{project_id}/pages/{page_id}{ext}", data)

    # ---------- đọc ----------
    def read(self, path: str) -> bytes:
        return self._abs(path).read_bytes()

    def open_read(self, path: str) -> BinaryIO:
        return self._abs(path).open("rb")

    def exists(self, path: str) -> bool:
        try:
            return self._abs(path).is_file()
        except UnsafeObjectPath:
            return False

    def stat(self, path: str) -> ObjectStat | None:
        try:
            st = self._abs(path).stat()
        except (OSError, UnsafeObjectPath):
            return None
        if not _stat.S_ISREG(st.st_mode):
            return None
        return ObjectStat(size=st.st_size, mtime=int(st.st_mtime))

    def fetch_to(self, path: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with self.open_read(path) as src, dest.open("wb") as out:
            shutil.copyfileobj(src, out)
        return dest

    # ---------- xoá / liệt kê ----------
    def delete(self, path: str) -> bool:
        try:
            target = self._abs(path)
        except UnsafeObjectPath:
            return False
        if target.is_file():
            target.unlink()
            return True
        return False

    def list_prefix(self, prefix: str) -> list[str]:
        try:
            base = self._abs(prefix)
        except UnsafeObjectPath:
            return []
        if not base.is_dir():
            return []
        goc = self.root.resolve()
        return sorted(str(p.relative_to(goc)) for p in base.rglob("*") if p.is_file())

    def delete_prefix(self, prefix: str) -> list[str]:
        da_xoa = self.list_prefix(prefix)
        for rel in da_xoa:
            self.delete(rel)
        # Dọn thư mục rỗng còn lại, sâu trước — để lần xuất sau không thấy rác cấu trúc.
        try:
            base = self._abs(prefix)
        except UnsafeObjectPath:
            return da_xoa
        if base.is_dir():
            for d in sorted((p for p in base.rglob("*") if p.is_dir()), reverse=True):
                try:
                    d.rmdir()
                except OSError:
                    pass
        return da_xoa


class SupabaseStorageNotConfigured(RuntimeError):
    pass


def build_storage(settings: Settings | None = None) -> IObjectStorage:
    settings = settings or get_settings()
    if settings.storage_backend == "local":
        return LocalObjectStorage(settings.storage_local_root)
    raise SupabaseStorageNotConfigured(
        "STORAGE_BACKEND=supabase: adapter Supabase Storage chưa được implement ở M1 "
        "(xem docs/ARCH.md § Storage). Dùng STORAGE_BACKEND=local hoặc bổ sung adapter trước."
    )


def get_storage() -> IObjectStorage:
    return build_storage()
