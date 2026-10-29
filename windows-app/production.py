"""Durable chapter processing, independent of Tk and of the translation provider.

The ledger records what we know, including ambiguous submissions. A lost upload
response must never cause an automatic second, potentially billable submission.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import re
import tempfile
import time
import zipfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError

from PIL import Image


class RunStopped(RuntimeError):
    pass


class NeedsAttention(RuntimeError):
    pass


def natural_key(value):
    return tuple((1, int(p)) if p.isdigit() else (0, p.casefold())
                 for p in re.split(r"(\d+)", str(value)))


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def verify_image(data: bytes) -> None:
    with Image.open(io.BytesIO(data)) as image:
        if image.width * image.height > 24_000_000:
            raise NeedsAttention("Ảnh vượt 24 triệu điểm ảnh; giảm kích thước hoặc chia nhỏ trước khi dịch.")
        image.verify()
    # JPEG.verify() alone does not decode pixels and accepts some truncated files.
    with Image.open(io.BytesIO(data)) as image:
        image.load()


def require_private_backend(health):
    capabilities = health.get("translation_capabilities") if isinstance(health, dict) else None
    if (not isinstance(health, dict)
            or not isinstance(capabilities, dict) or capabilities.get("private_context_v1") is not True):
        raise NeedsAttention("Máy chủ chưa hỗ trợ tách cấu hình. Cập nhật backend trước khi gửi nội dung khách hàng.")


def require_production_backend(health):
    require_private_backend(health)
    if health["translation_capabilities"].get("idempotent_upload_v1") is not True:
        raise NeedsAttention("Máy chủ chưa hỗ trợ phục hồi theo mã yêu cầu; cập nhật backend trước khi gửi ảnh.")


def original_coordinates(regions, data, result):
    width, height = result.get("image_width"), result.get("image_height")
    if (not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0):
        raise NeedsAttention("Máy chủ chưa trả kích thước ảnh; chưa thể đặt chữ đúng vị trí.")
    with Image.open(io.BytesIO(data)) as image:
        sx, sy = image.width / width, image.height / height
    adjusted = []
    for region in regions:
        item = dict(region)
        for key, scale in (("x", sx), ("y", sy), ("w", sx), ("h", sy)):
            value = item.get(key)
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise NeedsAttention("Toạ độ vùng dịch không hợp lệ.")
            item[key] = value * scale
        if item["w"] <= 0 or item["h"] <= 0:
            raise NeedsAttention("Vùng dịch không có diện tích hợp lệ.")
        adjusted.append(item)
    return adjusted


def wait_for_page(initial, fetch, cancelled, *, timeout=900, interval=1.5,
                  clock=time.monotonic, sleep=time.sleep):
    """Poll an existing page only. Transient GET failures never repeat the upload."""
    deadline = clock() + timeout
    result = initial
    last_error = None
    first_query = True
    while True:
        if cancelled():
            raise RunStopped("Đã dừng; trang đang chạy trên máy chủ được giữ để tiếp tục.")
        if not isinstance(result, dict):
            raise NeedsAttention("Máy chủ trả kết quả không hợp lệ.")
        if result.get("xong") is True:
            return result
        if result.get("loi") or result.get("trang_thai") in ("failed", "detection_failed"):
            raise NeedsAttention(str(result.get("loi") or "Trang xử lý lỗi trên máy chủ."))
        remaining = deadline - clock()
        if remaining <= 0:
            raise TimeoutError("Hết thời gian chờ; mở lại lượt chạy để hỏi trang cũ, không tải lại."
                               + (f" Lỗi kết nối cuối: {type(last_error).__name__}." if last_error else ""))
        if not first_query:
            sleep(min(interval, remaining))
        first_query = False
        if cancelled():
            raise RunStopped("Đã dừng.")
        if clock() >= deadline:
            raise TimeoutError("Hết thời gian chờ; mở lại lượt chạy để hỏi trang cũ, không tải lại.")
        try:
            result = fetch(result["page_id"])
            last_error = None
        except HTTPError as exc:
            if exc.code < 500 and exc.code != 429:
                raise NeedsAttention(f"Máy chủ từ chối tra trang (HTTP {exc.code}); kiểm tra tài khoản/quyền truy cập.") from exc
            last_error = exc
        except (OSError, TimeoutError) as exc:
            last_error = exc


class ChapterLedger:
    VERSION = 1

    def __init__(self, folder: Path, sources: list[str], config: dict, *, require_existing=False):
        self.folder = Path(folder)
        self.path = self.folder / "trang-thai.json"
        self.folder.mkdir(parents=True, exist_ok=True)
        self._lock = (self.folder / ".processing.lock").open("a+b")
        try:
            self._lock.seek(0, os.SEEK_END)
            if self._lock.tell() == 0:
                self._lock.write(b"0")
                self._lock.flush()
            self._lock.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self._lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self._lock.close()
            raise NeedsAttention("Chapter đang được một lượt chạy khác sử dụng.") from exc
        try:
            self._initialize(sources, config, require_existing=require_existing)
        except Exception:
            self.close()
            raise

    def _initialize(self, sources, config, *, require_existing=False):
        if not sources or len(set(sources)) != len(sources):
            raise NeedsAttention("Danh sách trang rỗng hoặc trùng nguồn; kiểm tra lại trước khi dịch.")
        signature = fingerprint({"sources": sources, "config": config})
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except (ValueError, OSError) as exc:
                raise NeedsAttention("Tệp trạng thái hỏng; giữ nguyên dữ liệu và chọn thư mục mới.") from exc
            if (not isinstance(self.data, dict) or self.data.get("version") != self.VERSION
                    or self.data.get("signature") != signature):
                raise NeedsAttention("Nguồn/cấu hình đã đổi hoặc trạng thái không tương thích. "
                                     "Chọn tên truyện/thư mục xuất mới để không ghi đè bản cũ.")
            pages = self.data.get("pages")
            if (not isinstance(pages, list) or len(pages) != len(sources)
                    or any(not isinstance(p, dict) or p.get("source") != src
                           for p, src in zip(pages, sources))):
                raise NeedsAttention("Danh sách trang trong tệp trạng thái không hợp lệ.")
        else:
            if require_existing:
                raise NeedsAttention("Hồ sơ chapter đã mất; không tạo mới khi rà soát.")
            # Old images have no evidence of source/configuration. Never silently adopt them.
            if any(self.folder.glob("*.jpg")):
                raise NeedsAttention("Thư mục có ảnh cũ chưa có trạng thái kiểm chứng. "
                                     "Chọn tên truyện/thư mục xuất mới.")
            self.data = {"version": self.VERSION, "signature": signature,
                         "config": config, "status": "pending", "review_status": "pending",
                         "pages": [{"source": src, "status": "pending"} for src in sources]}
            self.save()

    def close(self):
        if not self._lock.closed:
            if os.name == "nt":
                import msvcrt
                self._lock.seek(0)
                msvcrt.locking(self._lock.fileno(), msvcrt.LK_UNLCK, 1)
            self._lock.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def save(self):
        self.data["updated_at"] = datetime.now(timezone.utc).isoformat()
        atomic_write(self.path, json.dumps(self.data, ensure_ascii=False, indent=2).encode())

    def output(self, index):
        return self.folder / f"{index + 1:03d}.jpg"

    def check_source(self, index, data):
        digest = hashlib.sha256(data).hexdigest()
        page = self.data["pages"][index]
        if page.get("source_hash") and page["source_hash"] != digest:
            raise NeedsAttention("Nội dung nguồn đã thay đổi. Chọn thư mục xuất mới.")
        page["source_hash"] = digest
        self.save()

    def completed(self, index):
        page = self.data["pages"][index]
        if page.get("status") != "completed":
            return False
        try:
            data = self.output(index).read_bytes()
            verify_image(data)
            if hashlib.sha256(data).hexdigest() == page.get("output_hash"):
                return True
        except (OSError, ValueError, SyntaxError):
            pass
        # A manually edited image must not be silently overwritten, either.
        raise NeedsAttention("Ảnh kết quả bị đổi, mất hoặc hỏng; kiểm tra trước khi tiếp tục.")

    def update(self, index, **values):
        self.data["pages"][index].update(values)
        self.data["status"] = "incomplete"
        self.data["review_status"] = "pending"
        self.save()

    def finish_page(self, index, data, regions):
        verify_image(data)
        atomic_write(self.output(index), data)
        self.update(index, status="completed", output_hash=hashlib.sha256(data).hexdigest(),
                    regions=regions, error=None)

    def ready_files(self):
        files = []
        for i in range(len(self.data["pages"])):
            if not self.completed(i):
                raise NeedsAttention("Chapter chưa đủ trang; chưa xuất bản giao.")
            files.append(self.output(i))
        self.data["status"] = "completed"
        self.save()
        return files

    def export_cbz(self, destination: Path):
        files = self.ready_files()
        fd, temporary = tempfile.mkstemp(prefix=".chapter-", suffix=".cbz", dir=destination.parent)
        os.close(fd)
        try:
            with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
                for file in files:
                    archive.write(file, arcname=file.name)
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def process_chapter(ledger, *, load, submit, fetch, render, cancelled, log,
                    local_translate=None, timeout=900, require_isolation=False, preflight=None,
                    idempotent_submit=False, lookup_request=None, allow_silent_pages=False):
    """One sequential chapter; existing page IDs survive client restarts.

    submit receives immutable per-page context. Never retry an ambiguous POST.
    A successful file is not a human approval of its translation quality.
    """
    context = []
    for i, page in enumerate(ledger.data["pages"]):
        started = time.monotonic()
        if cancelled():
            raise RunStopped("Đã dừng.")
        try:
            data = load(page["source"])
            verify_image(data)
            ledger.check_source(i, data)
            if ledger.completed(i):
                regions = page.get("regions", [])
                log(f"⏭ Trang {i + 1}: đã kiểm tra ảnh và cấu hình, giữ kết quả.")
            else:
                if local_translate:
                    regions = local_translate(data, context[-10:])
                else:
                    ambiguous = page.get("status") == "submitting"
                    keyed = (page.get("request_key") and
                             page.get("request_protocol") == "idempotent_upload_v1" and
                             page.get("request_payload_version") == 1 and
                             isinstance(page.get("request_context"), list))
                    if ambiguous and not (idempotent_submit and keyed):
                        raise NeedsAttention("Lần gửi trước chưa xác định có được máy chủ nhận hay không. "
                                             "Kiểm tra trên web trước khi gửi lại để tránh trừ lượt hai lần.")
                    if page.get("page_id"):
                        initial = {"page_id": page["page_id"], "xong": False}
                    else:
                        if preflight:
                            preflight()
                        elif idempotent_submit:
                            raise NeedsAttention("Thiếu bước kiểm khả năng phục hồi của máy chủ; chưa gửi ảnh.")
                        initial = None
                        if ambiguous and lookup_request:
                            initial = lookup_request(page["request_key"])
                        if initial is None:
                            if idempotent_submit:
                                # Never upgrade an old ambiguous upload with a freshly minted key.
                                if page.get("request_key") and not keyed:
                                    raise NeedsAttention("Hồ sơ mã yêu cầu không tương thích; chưa gửi lại ảnh.")
                                if not keyed:
                                    ledger.update(i, request_key=str(uuid.uuid4()),
                                                  request_protocol="idempotent_upload_v1",
                                                  request_payload_version=1, request_context=list(context[-10:]))
                            ledger.update(i, status="submitting")
                            try:
                                # At most one POST per page per run. Retry only on explicit resume,
                                # always retaining this key and unchanged source/configuration.
                                initial = submit(data, i, page["request_context"] if idempotent_submit else context[-10:])
                            except HTTPError as exc:
                                if exc.code in (401, 403, 413, 429):
                                    ledger.update(i, status="pending")
                                raise
                        if not isinstance(initial, dict) or not initial.get("page_id"):
                            raise NeedsAttention("Phản hồi tải lên thiếu mã trang; chưa tự gửi lại.")
                        # Preserve page ID even if the response failed to acknowledge the key.
                        ledger.update(i, status="submitted", page_id=initial["page_id"],
                                      isolated=initial.get("cau_hinh_rieng") is True,
                                      request_ack=(initial.get("request_key") == page.get("request_key")))
                    if idempotent_submit and page.get("request_key") and not page.get("request_ack"):
                        raise NeedsAttention("Máy chủ chưa xác nhận đúng mã yêu cầu; giữ mã trang để kiểm tra, không gửi lại.")
                    if require_isolation and not page.get("isolated"):
                        raise NeedsAttention("Máy chủ chưa xác nhận tách cấu hình. Cần cập nhật backend "
                                             "trước khi dùng bản app này để nhận việc.")
                    result = wait_for_page(initial, fetch, cancelled, timeout=timeout)
                    regions = result.get("vung")
                if cancelled():
                    raise RunStopped("Đã dừng, chưa lưu ảnh đang xử lý.")
                if isinstance(regions, list) and not regions and allow_silent_pages:
                    output = data
                else:
                    if (not isinstance(regions, list) or not regions
                            or any(not isinstance(r, dict) or not str(r.get("ban_dich") or "").strip()
                                   for r in regions)):
                        raise NeedsAttention("Trang chưa có đủ bản dịch. Trang không chữ cần được kiểm tra riêng.")
                    if not local_translate and require_isolation:
                        regions = original_coordinates(regions, data, result)
                    output = render(data, regions)
                if cancelled():
                    raise RunStopped("Đã dừng, chưa lưu ảnh đang xử lý.")
                ledger.finish_page(i, output, regions)
                ledger.update(i, elapsed_seconds=round(time.monotonic() - started, 3))
                if not regions and allow_silent_pages:
                    log(f"✓ Đã lưu trang {i + 1}/{len(ledger.data['pages'])} (trang tranh không thoại, giữ nguyên ảnh gốc).")
                else:
                    log(f"✓ Đã lưu trang {i + 1}/{len(ledger.data['pages'])}; cần rà soát trước khi giao.")
            for region in regions:
                original = str(region.get("chu_goc") or "").strip()
                translated = str(region.get("ban_dich") or "").strip()
                if original and translated and len(original) <= 80 and len(translated) <= 120:
                    pair = f"{original} = {translated}"
                    if pair not in context:
                        context.append(pair)
        except Exception as exc:
            # Retain page_id/submitting state; the next run can poll, never guess.
            ledger.update(i, error=str(exc)[:1000])
            raise
    if cancelled():
        raise RunStopped("Đã dừng.")
    return ledger.ready_files()
