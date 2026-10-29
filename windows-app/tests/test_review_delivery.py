"""Review is manual; tests verify version binding and delivery contents, not translation quality."""
import hashlib
import io
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from production import ChapterLedger, NeedsAttention
import review_delivery as review


def image_bytes(color="white"):
    stream = io.BytesIO()
    Image.new("RGB", (32, 48), color).save(stream, "JPEG")
    return stream.getvalue()


def make_ledger(tmp_path, count=2):
    ledger = ChapterLedger(tmp_path / "chapter", [f"private-source-{i}" for i in range(count)],
                           {"engine": "test", "glossary": "confidential glossary"})
    for index in range(count):
        ledger.check_source(index, image_bytes())
        ledger.finish_page(index, image_bytes(), [{"chu_goc": "private text", "ban_dich": "Chào"}])
    ledger.ready_files()
    return ledger


def approve(ledger, index=0, **overrides):
    args = dict(decision="approved", reviewer="Reviewer entered by operator",
                expected_sha256=hashlib.sha256(ledger.output(index).read_bytes()).hexdigest(), confirmed=True)
    args.update(overrides)
    return review.record_review(ledger, index, **args)


def approve_all(ledger):
    for index in range(len(ledger.data["pages"])):
        approve(ledger, index)


def test_unapproved_and_partially_approved_chapters_cannot_deliver(tmp_path):
    with make_ledger(tmp_path) as ledger:
        destination = tmp_path / "delivery.zip"
        for partial in (False, True):
            if partial:
                approve(ledger, 0)
            with pytest.raises(NeedsAttention, match="Chưa đủ"):
                review.export_delivery(ledger, destination)
            assert not destination.exists()
            assert ledger.data["review_status"] == "pending"


@pytest.mark.parametrize("change", ["output", "regions", "source_hash", "config"])
def test_changed_content_invalidates_approval_and_blocks_delivery(tmp_path, change):
    with make_ledger(tmp_path, 1) as ledger:
        approve(ledger)
        if change == "output":
            ledger.output(0).write_bytes(image_bytes("red"))
        elif change == "regions":
            ledger.data["pages"][0]["regions"][0]["ban_dich"] = "Nội dung mới"
        elif change == "source_hash":
            ledger.data["pages"][0]["source_hash"] = "different source"
        else:
            ledger.data["config"]["glossary"] = "changed"
        assert review.chapter_status(ledger)["ready_for_delivery"] is False
        with pytest.raises(NeedsAttention):
            review.export_delivery(ledger, tmp_path / "delivery.zip")


def test_operational_note_and_timing_do_not_invalidate_content_review(tmp_path):
    with make_ledger(tmp_path, 1) as ledger:
        approve(ledger)
        ledger.data["pages"][0].update(elapsed_seconds=9, error=None)
        assert review.chapter_status(ledger)["ready_for_delivery"] is True


@pytest.mark.parametrize("overrides", [{"confirmed": False}, {"expected_sha256": "wrong"}, {"reviewer": " "}])
def test_approval_requires_human_confirmation_current_hash_and_reviewer(tmp_path, overrides):
    with make_ledger(tmp_path, 1) as ledger:
        with pytest.raises(NeedsAttention):
            approve(ledger, **overrides)
        assert review.chapter_status(ledger)["ready_for_delivery"] is False


def test_rejection_revokes_approval_and_survives_restart(tmp_path):
    with make_ledger(tmp_path, 1) as ledger:
        approve(ledger)
        review.record_review(ledger, 0, decision="changes_requested", reviewer="Operator", note="Sai tên nhân vật")
        folder = ledger.folder
    with review.open_chapter(folder) as ledger:
        assert review.chapter_status(ledger)["pages"][0]["review"] == "changes_requested"
        with pytest.raises(NeedsAttention):
            review.export_delivery(ledger, tmp_path / "delivery.zip")


def test_rejection_works_even_after_external_image_is_corrupted(tmp_path):
    with make_ledger(tmp_path, 1) as ledger:
        approve(ledger)
        ledger.output(0).write_bytes(b"broken")
        review.record_review(ledger, 0, decision="changes_requested", reviewer="Operator", note="Ảnh hỏng")
        assert ledger.data["pages"][0]["review"]["decision"] == "changes_requested"
        assert review.chapter_status(ledger)["ready_for_delivery"] is False


def test_resume_does_not_erase_valid_review_but_rerender_requires_review(tmp_path):
    with make_ledger(tmp_path, 1) as ledger:
        approve(ledger)
        folder = ledger.folder
    with review.open_chapter(folder) as ledger:
        assert review.chapter_status(ledger)["ready_for_delivery"] is True
        ledger.finish_page(0, image_bytes("red"), [{"ban_dich": "Mới"}])
        assert review.chapter_status(ledger)["ready_for_delivery"] is False
        assert ledger.data["review_status"] == "pending"


def test_delivery_contains_only_reviewed_pages_and_minimal_receipt(tmp_path):
    with make_ledger(tmp_path) as ledger:
        approve_all(ledger)
        (ledger.folder / "unrelated.jpg").write_bytes(image_bytes("red"))
        destination = tmp_path / "delivery.zip"
        receipt = review.export_delivery(ledger, destination)
        with zipfile.ZipFile(destination) as archive:
            assert archive.testzip() is None
            assert archive.namelist() == ["001.jpg", "002.jpg", "BAN-GIAO.json"]
            assert json.loads(archive.read("BAN-GIAO.json")) == receipt
            text = archive.read("BAN-GIAO.json").decode()
            for secret in ("confidential", "private-source", "private text", "Reviewer", "glossary"):
                assert secret not in text
            for page in receipt["pages"]:
                assert hashlib.sha256(archive.read(page["file"])).hexdigest() == page["sha256"]
        assert not list(tmp_path.glob(".delivery-*"))


def test_existing_destination_is_never_overwritten(tmp_path):
    with make_ledger(tmp_path, 1) as ledger:
        approve(ledger)
        destination = tmp_path / "delivery.zip"
        destination.write_bytes(b"previous delivery")
        with pytest.raises(NeedsAttention, match="đã tồn tại"):
            review.export_delivery(ledger, destination)
        assert destination.read_bytes() == b"previous delivery"


def test_destination_created_during_export_is_preserved(tmp_path, monkeypatch):
    with make_ledger(tmp_path, 1) as ledger:
        approve(ledger)
        destination = tmp_path / "delivery.zip"
        link = os.link
        def competing_link(source, target):
            destination.write_bytes(b"other delivery")
            return link(source, target)
        monkeypatch.setattr(review.os, "link", competing_link)
        with pytest.raises(NeedsAttention, match="lượt khác"):
            review.export_delivery(ledger, destination)
        assert destination.read_bytes() == b"other delivery"
        assert not list(tmp_path.glob(".delivery-*"))


def test_hardlink_not_supported_does_not_fallback_to_partial_delivery(tmp_path, monkeypatch):
    with make_ledger(tmp_path, 1) as ledger:
        approve(ledger)
        def unsupported(*args):
            raise OSError("unsupported")
        monkeypatch.setattr(review.os, "link", unsupported)
        destination = tmp_path / "delivery.zip"
        with pytest.raises(NeedsAttention, match="nguyên tử"):
            review.export_delivery(ledger, destination)
        assert not destination.exists()
        assert not list(tmp_path.glob(".delivery-*"))


def test_external_edit_between_status_and_archive_is_not_packaged(tmp_path, monkeypatch):
    with make_ledger(tmp_path, 1) as ledger:
        approve(ledger)
        actual_status = review.chapter_status
        def race(ledger):
            result = actual_status(ledger)
            ledger.output(0).write_bytes(image_bytes("red"))
            return result
        monkeypatch.setattr(review, "chapter_status", race)
        destination = tmp_path / "delivery.zip"
        with pytest.raises(NeedsAttention, match="đã đổi"):
            review.export_delivery(ledger, destination)
        assert not destination.exists()
        assert not list(tmp_path.glob(".delivery-*"))


def test_edit_after_bytes_checked_cannot_change_zip_content(tmp_path, monkeypatch):
    with make_ledger(tmp_path, 1) as ledger:
        approve(ledger)
        original = ledger.output(0).read_bytes()
        writestr = zipfile.ZipFile.writestr
        def race(archive, name, data, *args, **kwargs):
            if name == "001.jpg":
                ledger.output(0).write_bytes(image_bytes("red"))
            return writestr(archive, name, data, *args, **kwargs)
        monkeypatch.setattr(zipfile.ZipFile, "writestr", race)
        destination = tmp_path / "delivery.zip"
        review.export_delivery(ledger, destination)
        with zipfile.ZipFile(destination) as archive:
            assert archive.read("001.jpg") == original
        assert review.chapter_status(ledger)["ready_for_delivery"] is False


def test_review_lock_blocks_processing_and_other_reviewers(tmp_path):
    with make_ledger(tmp_path, 1) as ledger:
        with pytest.raises(NeedsAttention, match="lượt chạy khác"):
            review.open_chapter(ledger.folder)


def test_missing_and_corrupt_ledgers_are_not_initialized(tmp_path):
    with pytest.raises(NeedsAttention):
        review.open_chapter(tmp_path / "missing")
    assert not (tmp_path / "missing").exists()
    (tmp_path / "trang-thai.json").write_text("broken")
    with pytest.raises(NeedsAttention):
        review.open_chapter(tmp_path)
    assert (tmp_path / "trang-thai.json").read_text() == "broken"


def test_deleted_manifest_is_not_recreated_after_review_read(tmp_path, monkeypatch):
    with make_ledger(tmp_path, 1) as ledger:
        folder = ledger.folder
    original = review.ChapterLedger
    def race(*args, **kwargs):
        (folder / "trang-thai.json").unlink()
        return original(*args, **kwargs)
    monkeypatch.setattr(review, "ChapterLedger", race)
    with pytest.raises(NeedsAttention, match="đã mất"):
        review.open_chapter(folder)
    assert not (folder / "trang-thai.json").exists()


def test_cli_status_approve_export_and_error_codes(tmp_path):
    with make_ledger(tmp_path, 1) as ledger:
        folder = ledger.folder
    script = Path(review.__file__)
    def cli(*args):
        return subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True)
    result = cli("status", folder)
    assert result.returncode == 0
    status = json.loads(result.stdout)
    assert status["ready_for_delivery"] is False
    failed = cli("export", folder, tmp_path / "delivery.zip")
    assert failed.returncode == 1
    approved = cli("approve", folder, "--page", "1", "--reviewer", "Operator",
                   "--sha256", status["pages"][0]["sha256"], "--confirm-reviewed")
    assert approved.returncode == 0, approved.stderr
    delivered = cli("export", folder, tmp_path / "delivery.zip")
    assert delivered.returncode == 0, delivered.stderr
    duplicate = cli("export", folder, tmp_path / "delivery.zip")
    assert duplicate.returncode == 1


def test_failed_review_save_does_not_leave_an_in_memory_approval(tmp_path, monkeypatch):
    with make_ledger(tmp_path, 1) as ledger:
        before = ledger.path.read_bytes()
        def disk_full():
            raise OSError("disk full")
        monkeypatch.setattr(ledger, "save", disk_full)
        with pytest.raises(OSError, match="disk full"):
            approve(ledger)
        assert review.chapter_status(ledger)["ready_for_delivery"] is False
        assert ledger.path.read_bytes() == before


def test_zip_write_failure_cleans_temporary_and_leaves_no_delivery(tmp_path, monkeypatch):
    with make_ledger(tmp_path, 1) as ledger:
        approve(ledger)
        def disk_full(*args, **kwargs):
            raise OSError("disk full")
        monkeypatch.setattr(zipfile.ZipFile, "writestr", disk_full)
        destination = tmp_path / "delivery.zip"
        with pytest.raises(OSError, match="disk full"):
            review.export_delivery(ledger, destination)
        assert not destination.exists()
        assert not list(tmp_path.glob(".delivery-*"))
        assert review.chapter_status(ledger)["ready_for_delivery"] is True
