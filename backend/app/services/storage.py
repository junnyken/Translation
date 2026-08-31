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

import io
import os
import shutil
import stat as _stat
import tempfile
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import BinaryIO, NamedTuple, Protocol

from sqlalchemy import delete as sa_delete, func, select

from app.core.config import Settings, get_settings

# Magic bytes để xác nhận file thật sự là ảnh (không tin content-type client gửi).
_MAGIC = {
    b"\xff\xd8\xff": ("image/jpeg", ".jpg"),
    b"\x89PNG\r\n\x1a\n": ("image/png", ".png"),
}


#: Khối đọc mặc định. 256KB: đủ lớn để một ảnh 3-4MB chỉ tốn ~15 lượt đi CSDL, đủ nhỏ để RAM
#: mỗi lượt phục vụ không phụ thuộc kích thước hiện vật.
_KHOI_DOC = 256 * 1024


class UnsupportedImage(ValueError):
    pass


class UnsafeObjectPath(ValueError):
    """Path tương đối vượt ra ngoài gốc lưu trữ — từ chối thay vì đọc/ghi nhầm chỗ."""


class ObjectStat(NamedTuple):
    """Siêu dữ liệu tối thiểu mà MỌI backend đều cấp được.

    `mtime` là **mốc phiên bản**, không phải một mốc thời gian để hiển thị: hai người dùng duy
    nhất của nó (vân tay E14 và ETag HTTP) chỉ hỏi "có khác lần trước không". Độ phân giải tuỳ
    backend — `local` dùng giây (đó là thứ `stat()` của hệ tệp cho), `postgres` dùng micro giây
    (chính xác hơn, và rẻ như nhau).

    Vì sao độ phân giải đáng bận tâm: vân tay là `(size, mtime)`. Ghi đè trong CÙNG một giây mà
    kích thước không đổi ⇒ vân tay không đổi ⇒ E14 dùng lại hình bong bóng cũ cho một ảnh clean
    đã khác. Với `local` đây là rủi ro có thật nhưng nhỏ (LaMa chạy lâu hơn 1 giây); với
    `postgres` thì micro giây loại hẳn nó.
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


class LuongHienVatLuoi(io.RawIOBase):
    """Luồng đọc **lười** trên một hiện vật: chỉ kéo về đúng đoạn được yêu cầu.

    Sinh ra để bỏ một cái giá mà P3e đã nhận có chủ đích: `open_read()` của backend CSDL nạp cả
    hiện vật vào RAM. Với gói CBZ vài chục MB và mấy người tải cùng lúc thì đó là một đường dẫn
    thẳng tới OOM.

    Vì sao phải **tua được** chứ không chỉ đọc tuần tự: PIL (`Image.open`) tua tới lui trong
    header ảnh. Một luồng chỉ-đọc-tiếp sẽ làm hỏng mọi chỗ dùng PIL.
    """

    def __init__(self, doc_doan, tong: int) -> None:
        self._doc_doan = doc_doan
        self._tong = tong
        self._vi_tri = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._vi_tri

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            moi = offset
        elif whence == io.SEEK_CUR:
            moi = self._vi_tri + offset
        elif whence == io.SEEK_END:
            moi = self._tong + offset
        else:
            raise ValueError(f"whence không hợp lệ: {whence}")
        self._vi_tri = max(0, moi)
        return self._vi_tri

    def readinto(self, b) -> int:
        con = self._tong - self._vi_tri
        if con <= 0:
            return 0
        n = min(len(b), con)
        du_lieu = self._doc_doan(self._vi_tri, n)
        b[: len(du_lieu)] = du_lieu
        self._vi_tri += len(du_lieu)
        return len(du_lieu)


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
        """Luồng đọc **tua được**, đọc lười. Bên gọi phải đóng (dùng `with`)."""
        ...

    def read_range(self, path: str, offset: int, length: int) -> bytes:
        """Đọc đúng một đoạn. Nền của HTTP `Range` và của luồng lười.

        Quá cuối tệp thì trả về ít byte hơn (hoặc rỗng) chứ không ném.
        """
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
        # Tệp trên đĩa vốn đã lười và tua được — không cần bọc thêm gì.
        return self._abs(path).open("rb")

    def read_range(self, path: str, offset: int, length: int) -> bytes:
        if length <= 0:
            return b""
        with self._abs(path).open("rb") as fh:
            fh.seek(max(0, offset))
            return fh.read(length)

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


class ArtifactTooLarge(ValueError):
    """Hiện vật vượt trần cấu hình — chặn ở đường GHI, không để phát hiện lúc đọc."""


def _mau_like_tien_to(prefix: str) -> str:
    """Đổi tiền tố thư mục thành mẫu LIKE, thoát ký tự đặc biệt của LIKE.

    Phải thoát `%` và `_`: `_` là ký tự đại diện MỘT ký tự bất kỳ, mà tên hiện vật của hệ thống
    này có `_` thật (`<page_id>_clean.png`).
    """
    an = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"{an}/%"


class PostgresObjectStorage:
    """Hiện vật nằm trong bảng `artifact_blob` của chính CSDL ứng dụng.

    Lý do tồn tại: P3c chứng minh VibeHost không cấp được volume bền, nên hệ tệp container không
    giữ được gì qua một lượt triển khai lại. CSDL là nguyên thể bền duy nhất nền tảng cấp.

    **Luôn dùng session ĐỒNG BỘ.** Worker Celery vốn đồng bộ; còn tầng HTTP async thì gọi lớp
    này qua `run_in_threadpool` (xem `routes.py`) thay vì để lớp kho phải có hai bản sync/async.
    Một lớp, một đường đọc — ít chỗ sai hơn hẳn.
    """

    def __init__(self, session_factory=None, max_bytes: int = 0) -> None:
        if session_factory is None:
            from app.core.db_sync import sync_session as session_factory  # noqa: PLC0415
        self._phien = session_factory
        self.max_bytes = max_bytes

    # ---------- ghi ----------
    def save(self, path: str, data: bytes) -> str:
        sach = chuan_hoa_path(path)
        if self.max_bytes and len(data) > self.max_bytes:
            raise ArtifactTooLarge(
                f"Hiện vật {sach!r} nặng {len(data) / 1e6:.1f} MB, vượt trần "
                f"{self.max_bytes / 1e6:.0f} MB (STORAGE_PG_MAX_ARTIFACT_MB)"
            )
        from sqlalchemy.dialects.postgresql import insert  # noqa: PLC0415

        from app.models import ArtifactBlob  # noqa: PLC0415

        with self._phien() as s:
            # Upsert: ghi đè là chuyện thường (chạy lại xoá chữ, vẽ lại ảnh xem thử) và phải
            # NGUYÊN TỬ — một câu lệnh, không "xoá rồi chèn" để lộ khoảng trống ở giữa.
            lenh = insert(ArtifactBlob).values(
                path=sach, data=data, size_bytes=len(data)
            )
            s.execute(
                lenh.on_conflict_do_update(
                    index_elements=[ArtifactBlob.path],
                    set_={
                        "data": lenh.excluded.data,
                        "size_bytes": lenh.excluded.size_bytes,
                        "updated_at": func.now(),
                    },
                )
            )
            s.commit()
        return sach

    def save_file(self, path: str, source: Path) -> str:
        return self.save(path, Path(source).read_bytes())

    def save_page_image(self, project_id: uuid.UUID, page_id: uuid.UUID, data: bytes, ext: str) -> str:
        return self.save(f"projects/{project_id}/pages/{page_id}{ext}", data)

    # ---------- đọc ----------
    def read(self, path: str) -> bytes:
        sach = chuan_hoa_path(path)
        from app.models import ArtifactBlob  # noqa: PLC0415

        with self._phien() as s:
            data = s.scalar(select(ArtifactBlob.data).where(ArtifactBlob.path == sach))
        if data is None:
            raise FileNotFoundError(f"Không có hiện vật {sach!r} trong kho")
        return bytes(data)

    def read_range(self, path: str, offset: int, length: int) -> bytes:
        """Đọc đúng một đoạn bằng `substr()` phía máy chủ — KHÔNG kéo cả hiện vật về.

        Đây là chỗ `SET STORAGE EXTERNAL` (migration 0010) trả công: cột không bị nén nên
        Postgres giải TOAST được **một phần**, thay vì phải bung cả hiện vật ra mới cắt được
        đoạn cần.
        """
        if length <= 0:
            return b""
        sach = chuan_hoa_path(path)
        from app.models import ArtifactBlob  # noqa: PLC0415

        with self._phien() as s:
            # substr của Postgres đánh số từ 1.
            doan = s.scalar(
                select(func.substr(ArtifactBlob.data, max(0, offset) + 1, length)).where(
                    ArtifactBlob.path == sach
                )
            )
        if doan is None:
            raise FileNotFoundError(f"Không có hiện vật {sach!r} trong kho")
        return bytes(doan)

    def open_read(self, path: str) -> BinaryIO:
        """Luồng LƯỜI: chỉ hỏi kích thước trước, byte thì kéo về theo từng khối khi được đọc.

        P3e từng nạp cả hiện vật vào RAM ở đây — có chủ đích, nhưng đó là một cái giá thật (gói
        CBZ vài chục MB × nhiều người tải cùng lúc). Nay đọc lười, nên RAM tỉ lệ với **khối
        đang đọc**, không phải với kích thước hiện vật.
        """
        # Kiểm path TRƯỚC khi hỏi `stat()`: `stat()` cố ý nuốt `UnsafeObjectPath` và trả None
        # (nó là một câu hỏi, không phải một lệnh). Nếu để nó nuốt ở đây thì một path nguy hiểm
        # sẽ hiện ra thành "không tìm thấy" — che mất tín hiệu bảo mật. Test bắt đúng ca này.
        sach = chuan_hoa_path(path)
        st = self.stat(sach)
        if st is None:
            raise FileNotFoundError(f"Không có hiện vật {sach!r} trong kho")
        raw = LuongHienVatLuoi(lambda off, n: self.read_range(sach, off, n), st.size)
        # Bọc BufferedReader để `.read(n)` nhỏ lẻ (PIL hay làm) không thành N lượt đi CSDL.
        return io.BufferedReader(raw, buffer_size=_KHOI_DOC)

    def exists(self, path: str) -> bool:
        try:
            sach = chuan_hoa_path(path)
        except UnsafeObjectPath:
            return False
        from app.models import ArtifactBlob  # noqa: PLC0415

        with self._phien() as s:
            return s.scalar(select(1).where(ArtifactBlob.path == sach)) is not None

    def stat(self, path: str) -> ObjectStat | None:
        try:
            sach = chuan_hoa_path(path)
        except UnsafeObjectPath:
            return None
        from app.models import ArtifactBlob  # noqa: PLC0415

        with self._phien() as s:
            # KHÔNG chọn cột `data`: hỏi kích thước mà kéo cả 3MB lên là tự bắn vào chân.
            hang = s.execute(
                select(ArtifactBlob.size_bytes, ArtifactBlob.updated_at).where(
                    ArtifactBlob.path == sach
                )
            ).first()
        if hang is None:
            return None
        return ObjectStat(size=int(hang[0]), mtime=int(hang[1].timestamp() * 1_000_000))

    def fetch_to(self, path: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(self.read(path))
        return dest

    # ---------- xoá / liệt kê ----------
    def delete(self, path: str) -> bool:
        try:
            sach = chuan_hoa_path(path)
        except UnsafeObjectPath:
            return False
        from app.models import ArtifactBlob  # noqa: PLC0415

        with self._phien() as s:
            n = s.execute(sa_delete(ArtifactBlob).where(ArtifactBlob.path == sach)).rowcount
            s.commit()
        return bool(n)

    def list_prefix(self, prefix: str) -> list[str]:
        try:
            sach = chuan_hoa_path(prefix)
        except UnsafeObjectPath:
            return []
        from app.models import ArtifactBlob  # noqa: PLC0415

        with self._phien() as s:
            return sorted(
                s.scalars(
                    select(ArtifactBlob.path).where(
                        ArtifactBlob.path.like(_mau_like_tien_to(sach), escape="\\")
                    )
                )
            )

    def delete_prefix(self, prefix: str) -> list[str]:
        da_xoa = self.list_prefix(prefix)
        if not da_xoa:
            return []
        from app.models import ArtifactBlob  # noqa: PLC0415

        with self._phien() as s:
            s.execute(sa_delete(ArtifactBlob).where(ArtifactBlob.path.in_(da_xoa)))
            s.commit()
        return da_xoa


class SupabaseStorageNotConfigured(RuntimeError):
    pass


def build_storage(settings: Settings | None = None) -> IObjectStorage:
    settings = settings or get_settings()
    if settings.storage_backend == "local":
        return LocalObjectStorage(settings.storage_local_root)
    if settings.storage_backend == "postgres":
        return PostgresObjectStorage(
            max_bytes=settings.storage_pg_max_artifact_mb * 1024 * 1024
        )
    raise SupabaseStorageNotConfigured(
        "STORAGE_BACKEND=supabase: adapter Supabase Storage chưa được implement ở M1 "
        "(xem docs/ARCH.md § Storage). Dùng STORAGE_BACKEND=local hoặc bổ sung adapter trước."
    )


def get_storage() -> IObjectStorage:
    return build_storage()
