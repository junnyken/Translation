"""Lưu file ảnh gốc/ảnh clean.

M1 hiện thực backend `local` (volume) và đã verify thật.
Backend `supabase` CHƯA implement (cần credential Supabase Storage) — khi cấu hình
STORAGE_BACKEND=supabase, app fail ngay lúc khởi tạo thay vì im lặng ghi sai chỗ.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Protocol

from app.core.config import Settings, get_settings

# Magic bytes để xác nhận file thật sự là ảnh (không tin content-type client gửi).
_MAGIC = {
    b"\xff\xd8\xff": ("image/jpeg", ".jpg"),
    b"\x89PNG\r\n\x1a\n": ("image/png", ".png"),
}


class UnsupportedImage(ValueError):
    pass


def sniff_image(data: bytes) -> tuple[str, str]:
    """Trả (mime, extension) nếu là JPEG/PNG thật; ném UnsupportedImage nếu không."""
    for magic, (mime, ext) in _MAGIC.items():
        if data.startswith(magic):
            return mime, ext
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", ".webp"
    raise UnsupportedImage("File upload không phải ảnh JPEG/PNG/WEBP hợp lệ")


class IObjectStorage(Protocol):
    def save_page_image(self, project_id: uuid.UUID, page_id: uuid.UUID, data: bytes, ext: str) -> str:
        """Lưu ảnh gốc, trả về path/URI đã lưu."""
        ...

    def read(self, path: str) -> bytes:
        ...

    def exists(self, path: str) -> bool:
        ...

    def delete(self, path: str) -> bool:
        """Xoá file (idempotent guard của M4). Trả True nếu có file để xoá."""
        ...

    def abs_path(self, path: str) -> str:
        """Đường dẫn tuyệt đối tương ứng path tương đối lưu trong DB."""
        ...


class LocalObjectStorage:
    """Lưu xuống volume: <root>/projects/<project_id>/pages/<page_id><ext>"""

    def __init__(self, root: str) -> None:
        self.root = Path(root)

    def _abs(self, rel: str) -> Path:
        return self.root / rel

    def save_page_image(self, project_id: uuid.UUID, page_id: uuid.UUID, data: bytes, ext: str) -> str:
        rel = f"projects/{project_id}/pages/{page_id}{ext}"
        target = self._abs(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return rel

    def read(self, path: str) -> bytes:
        return self._abs(path).read_bytes()

    def exists(self, path: str) -> bool:
        return self._abs(path).is_file()

    def delete(self, path: str) -> bool:
        target = self._abs(path)
        if target.is_file():
            target.unlink()
            return True
        return False

    def abs_path(self, path: str) -> str:
        return str(self._abs(path))

    def to_relative(self, absolute_path: str) -> str:
        """Đổi đường dẫn tuyệt đối về dạng tương đối để lưu DB (khớp cách M1 lưu ảnh gốc)."""
        try:
            return str(Path(absolute_path).resolve().relative_to(self.root.resolve()))
        except ValueError:
            return absolute_path


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
