"""Local human-review gate. Receipts are traceability records, not signatures.

No provider calls, uploads or customer notifications. Run --help for CLI usage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from production import ChapterLedger, NeedsAttention, fingerprint, verify_image


def now():
    return datetime.now(timezone.utc).isoformat()


def open_chapter(folder):
    """Open existing evidence only; never initialize a new chapter from this tool."""
    folder = Path(folder)
    try:
        data = json.loads((folder / "trang-thai.json").read_text(encoding="utf-8"))
        sources = [page["source"] for page in data["pages"]]
        config = data["config"]
        if not isinstance(config, dict) or any(not isinstance(source, str) for source in sources):
            raise ValueError("Invalid chapter")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise NeedsAttention("Không đọc được hồ sơ chapter có sẵn; không tạo mới hoặc sửa hồ sơ hỏng.") from exc
    return ChapterLedger(folder, sources, config, require_existing=True)


def page_bytes(ledger, index):
    if not 0 <= index < len(ledger.data["pages"]):
        raise NeedsAttention("Số trang nằm ngoài chapter.")
    page = ledger.data["pages"][index]
    if page.get("status") != "completed":
        raise NeedsAttention("Trang chưa xử lý xong.")
    try:
        data = ledger.output(index).read_bytes()
        verify_image(data)
    except (OSError, ValueError, SyntaxError) as exc:
        raise NeedsAttention("Ảnh kết quả mất hoặc hỏng; chưa thể duyệt/giao.") from exc
    if hashlib.sha256(data).hexdigest() != page.get("output_hash"):
        raise NeedsAttention("Ảnh kết quả đã đổi; chưa thể dùng phê duyệt cũ hoặc tự nhận ảnh sửa tay.")
    return data


def snapshot(ledger, index, data):
    page = ledger.data["pages"][index]
    return fingerprint({"signature": ledger.data["signature"], "config": ledger.data["config"],
                        "source": page["source"], "source_hash": page.get("source_hash"),
                        "regions": page.get("regions"), "status": page.get("status"),
                        "output_hash": hashlib.sha256(data).hexdigest()})


def review_state(ledger, index, data):
    review = ledger.data["pages"][index].get("review")
    if not isinstance(review, dict):
        return "pending"
    if review.get("decision") == "changes_requested":
        return "changes_requested"
    if review.get("snapshot") != snapshot(ledger, index, data):
        return "stale"
    decision = review.get("decision")
    return decision if decision in ("approved", "changes_requested") else "pending"


def chapter_status(ledger):
    result = []
    for index, page in enumerate(ledger.data["pages"]):
        row = {"page": index + 1, "file": str(ledger.output(index).resolve()),
               "processing": page.get("status"), "review": "pending"}
        try:
            data = page_bytes(ledger, index)
            row.update(sha256=hashlib.sha256(data).hexdigest(), review=review_state(ledger, index, data))
        except NeedsAttention as exc:
            row.update(review="blocked", reason=str(exc))
        result.append(row)
    return {"pages": result, "ready_for_delivery": bool(result) and
            all(row["review"] == "approved" for row in result)}


def record_review(ledger, index, *, decision, reviewer, note="", expected_sha256=None, confirmed=False):
    if decision not in ("approved", "changes_requested"):
        raise NeedsAttention("Quyết định rà soát không hợp lệ.")
    reviewer, note = reviewer.strip(), note.strip()
    if not reviewer or len(reviewer) > 200 or len(note) > 2000:
        raise NeedsAttention("Cần tên người rà soát (tối đa 200 ký tự); ghi chú tối đa 2000 ký tự.")
    if not 0 <= index < len(ledger.data["pages"]):
        raise NeedsAttention("Số trang nằm ngoài chapter.")
    if decision == "approved":
        if not confirmed:
            raise NeedsAttention("Cần xác nhận đã xem nội dung, thứ tự và chất lượng trang trước khi duyệt.")
        data = page_bytes(ledger, index)
        digest = hashlib.sha256(data).hexdigest()
        if expected_sha256 != digest:
            raise NeedsAttention("Mã SHA256 không khớp ảnh đã xem; kiểm tra lại trước khi duyệt.")
        version = snapshot(ledger, index, data)
    else:
        # Revocation must work even if an external editor damaged/replaced the image.
        if not note:
            raise NeedsAttention("Cần ghi lý do yêu cầu sửa.")
        version = None
    page = ledger.data["pages"][index]
    previous = page.get("review")
    previous_status = ledger.data.get("review_status", "pending")
    review = {"decision": decision, "snapshot": version, "reviewer": reviewer,
              "reviewed_at": now(), "note": note}
    page["review"] = review
    try:
        # Decode the full chapter only when all pages have a candidate approval,
        # not once per approval (quadratic image decoding on long chapters).
        all_candidates = all(isinstance(p.get("review"), dict) and
                             p["review"].get("decision") == "approved" for p in ledger.data["pages"])
        ledger.data["review_status"] = ("approved" if all_candidates and
                                        chapter_status(ledger)["ready_for_delivery"] else "pending")
        ledger.save()
    except Exception:
        ledger.data["review_status"] = previous_status
        if previous is None:
            page.pop("review", None)
        else:
            page["review"] = previous
        raise
    return review


def export_delivery(ledger, destination):
    """Publish atomically without replacing any existing destination.

    Check the exact bytes passed to writestr, never hash then reopen with write(path).
    A simultaneous external edit cannot inject unreviewed bytes into the package.
    """
    destination = Path(destination)
    if destination.suffix.lower() != ".zip":
        raise NeedsAttention("Bản giao dùng đuôi .zip.")
    if destination.exists() or destination.is_symlink():
        raise NeedsAttention("Tệp giao đã tồn tại; chọn tên phiên bản mới, không ghi đè.")
    if not chapter_status(ledger)["ready_for_delivery"]:
        raise NeedsAttention("Chưa đủ trang được duyệt hợp lệ; chưa thể xuất bản giao.")
    fd, temporary = tempfile.mkstemp(prefix=".delivery-", suffix=".zip", dir=destination.parent)
    try:
        receipt = {"schema_version": 1, "delivery_id": str(uuid.uuid4()), "created_at": now(), "pages": []}
        with os.fdopen(fd, "w+b") as stream:
            with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
                for index in range(len(ledger.data["pages"])):
                    data = page_bytes(ledger, index)
                    if review_state(ledger, index, data) != "approved":
                        raise NeedsAttention("Ảnh hoặc nội dung duyệt đã đổi; cần rà soát lại.")
                    name = ledger.output(index).name
                    archive.writestr(name, data)
                    receipt["pages"].append({"file": name, "sha256": hashlib.sha256(data).hexdigest()})
                archive.writestr("BAN-GIAO.json", json.dumps(receipt, ensure_ascii=False, indent=2))
            stream.flush()
            os.fsync(stream.fileno())
        # Same filesystem; link is exclusive and atomic, unlike copying into final name.
        # On filesystems lacking hard links fail closed, no non-atomic fallback.
        try:
            os.link(temporary, destination)
        except FileExistsError as exc:
            raise NeedsAttention("Tệp giao vừa được tạo bởi lượt khác; không ghi đè.") from exc
        except OSError as exc:
            raise NeedsAttention("Không tạo được bản giao nguyên tử; chọn thư mục hỗ trợ hard link (ví dụ NTFS).") from exc
        return receipt
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Rà soát từng trang và xuất ZIP đã duyệt; không tự gửi khách.")
    commands = parser.add_subparsers(dest="command", required=True)
    status = commands.add_parser("status", help="Xem trang cần rà soát và SHA256 của ảnh.")
    status.add_argument("folder", type=Path)
    for command in ("approve", "reject"):
        action = commands.add_parser(command)
        action.add_argument("folder", type=Path)
        action.add_argument("--page", type=int, required=True, help="Số trang, bắt đầu từ 1")
        action.add_argument("--reviewer", required=True)
        action.add_argument("--note", default="")
        if command == "approve":
            action.add_argument("--sha256", required=True, help="Hash ảnh đã mở xem từ status")
            action.add_argument("--confirm-reviewed", action="store_true", required=True)
    export = commands.add_parser("export", help="Xuất bản giao ZIP chỉ khi đủ trang đã duyệt.")
    export.add_argument("folder", type=Path)
    export.add_argument("destination", type=Path)
    args = parser.parse_args(argv)
    try:
        with open_chapter(args.folder) as ledger:
            if args.command == "status":
                result = chapter_status(ledger)
            elif args.command == "export":
                result = export_delivery(ledger, args.destination)
            else:
                result = record_review(ledger, args.page - 1,
                                       decision="approved" if args.command == "approve" else "changes_requested",
                                       reviewer=args.reviewer, note=args.note,
                                       expected_sha256=getattr(args, "sha256", None),
                                       confirmed=getattr(args, "confirm_reviewed", False))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (NeedsAttention, OSError, ValueError) as exc:
        print(f"Chưa thực hiện: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
