import io
import json
import zipfile
from urllib.error import HTTPError

import pytest
from PIL import Image

from production import ChapterLedger, NeedsAttention, RunStopped, process_chapter, wait_for_page, require_private_backend, original_coordinates
from sources import archive_sources, chapter_links, image_links, local_image_sources, read_local_source


def image_bytes(color="white"):
    out = io.BytesIO()
    Image.new("RGB", (32, 48), color).save(out, "JPEG")
    return out.getvalue()


REGIONS = [{"chu_goc": "Hello", "ban_dich": "Chào", "x": 1, "y": 1, "w": 20, "h": 20}]


def run(ledger, **overrides):
    callbacks = dict(load=lambda _: image_bytes(),
                     submit=lambda *_: {"page_id": "page-1", "xong": True, "vung": REGIONS},
                     fetch=lambda _: {"page_id": "page-1", "xong": True, "vung": REGIONS},
                     render=lambda *_: image_bytes("red"), cancelled=lambda: False, log=lambda _: None)
    callbacks.update(overrides)
    return process_chapter(ledger, **callbacks)


def test_resume_checks_content_config_and_restores_context(tmp_path):
    seen = []
    with ChapterLedger(tmp_path, ["a", "b"], {"engine": "llm"}) as ledger:
        def submit(data, index, context):
            seen.append((index, list(context)))
            if index == 1:
                raise OSError("lost response")
            return {"page_id": "one", "xong": True, "vung": REGIONS}
        with pytest.raises(OSError):
            run(ledger, submit=submit)
        assert ledger.data["pages"][0]["status"] == "completed"
        assert ledger.data["pages"][1]["status"] == "submitting"
    with ChapterLedger(tmp_path, ["a", "b"], {"engine": "llm"}) as ledger:
        with pytest.raises(NeedsAttention, match="chưa xác định"):
            run(ledger, submit=lambda *_: pytest.fail("must not upload twice"))
    assert seen == [(0, []), (1, ["Hello = Chào"])]


def test_resume_polls_existing_id_without_resubmission(tmp_path):
    with ChapterLedger(tmp_path, ["a"], {}) as ledger:
        ledger.update(0, status="submitted", page_id="persisted")
    seen = []
    with ChapterLedger(tmp_path, ["a"], {}) as ledger:
        files = run(ledger, submit=lambda *_: pytest.fail("duplicate upload"),
                    fetch=lambda page_id: seen.append(page_id) or {"xong": True, "vung": REGIONS}, timeout=1)
        assert len(files) == 1
        assert seen == ["persisted"]


@pytest.mark.parametrize("change", ["config", "source_order", "source_bytes"])
def test_changed_inputs_do_not_overwrite(tmp_path, change):
    with ChapterLedger(tmp_path, ["a", "b"], {"font": "one"}) as ledger:
        run(ledger)
    original = (tmp_path / "001.jpg").read_bytes()
    with pytest.raises(NeedsAttention):
        with ChapterLedger(tmp_path, ["b", "a"] if change == "source_order" else ["a", "b"],
                           {"font": "two" if change == "config" else "one"}) as ledger:
            run(ledger, load=lambda _: image_bytes("blue"))
    assert (tmp_path / "001.jpg").read_bytes() == original


def test_edited_output_is_preserved(tmp_path):
    with ChapterLedger(tmp_path, ["a"], {}) as ledger:
        run(ledger)
        edited = image_bytes("blue")
        ledger.output(0).write_bytes(edited)
        with pytest.raises(NeedsAttention, match="bị đổi"):
            run(ledger)
        assert ledger.output(0).read_bytes() == edited


def test_old_unverified_files_are_not_assumed_complete(tmp_path):
    (tmp_path / "001.jpg").write_bytes(image_bytes())
    with pytest.raises(NeedsAttention, match="ảnh cũ"):
        ChapterLedger(tmp_path, ["a"], {})


def test_lock_prevents_two_clients_and_releases(tmp_path):
    with ChapterLedger(tmp_path, ["a"], {}):
        with pytest.raises(NeedsAttention, match="lượt chạy khác"):
            ChapterLedger(tmp_path, ["a"], {})
    with ChapterLedger(tmp_path, ["a"], {}):
        pass


def test_corrupt_ledger_is_not_replaced(tmp_path):
    (tmp_path / "trang-thai.json").write_text("broken")
    with pytest.raises(NeedsAttention, match="hỏng"):
        ChapterLedger(tmp_path, ["a"], {})
    assert (tmp_path / "trang-thai.json").read_text() == "broken"


def test_partial_chapter_does_not_replace_existing_export(tmp_path):
    destination = tmp_path / "chapter.cbz"
    destination.write_bytes(b"previous delivery")
    with ChapterLedger(tmp_path / "pages", ["a", "b"], {}) as ledger:
        ledger.finish_page(0, image_bytes(), REGIONS)
        with pytest.raises(NeedsAttention, match="chưa đủ"):
            ledger.export_cbz(destination)
    assert destination.read_bytes() == b"previous delivery"


def test_export_contains_only_manifest_pages_not_old_longstrips(tmp_path):
    with ChapterLedger(tmp_path / "pages", ["a", "b"], {}) as ledger:
        run(ledger)
        (ledger.folder / "old_Webtoon_LongStrip.jpg").write_bytes(image_bytes())
        destination = tmp_path / "chapter.cbz"
        ledger.export_cbz(destination)
        with zipfile.ZipFile(destination) as archive:
            assert archive.namelist() == ["001.jpg", "002.jpg"]


def test_stop_after_submit_keeps_id_without_creating_output(tmp_path):
    stopped = [False]
    with ChapterLedger(tmp_path, ["a"], {}) as ledger:
        def submit(*_):
            stopped[0] = True
            return {"page_id": "one", "xong": True, "vung": REGIONS}
        with pytest.raises(RunStopped):
            run(ledger, submit=submit, cancelled=lambda: stopped[0])
        assert ledger.data["pages"][0]["page_id"] == "one"
        assert not ledger.output(0).exists()


@pytest.mark.parametrize("regions", [None, [], [{}], [{"ban_dich": ""}]])
def test_missing_translations_never_become_completed(tmp_path, regions):
    with ChapterLedger(tmp_path, ["a"], {}) as ledger:
        with pytest.raises(NeedsAttention, match="chưa có đủ"):
            run(ledger, submit=lambda *_: {"page_id": "one", "xong": True, "vung": regions})
        assert ledger.data["pages"][0]["status"] != "completed"
        assert not ledger.output(0).exists()


def test_old_backend_is_not_silently_used_for_private_work(tmp_path):
    with ChapterLedger(tmp_path, ["a"], {}) as ledger:
        with pytest.raises(NeedsAttention, match="tách cấu hình"):
            run(ledger, require_isolation=True)
        assert ledger.data["pages"][0]["page_id"] == "page-1"
        assert not ledger.output(0).exists()


def test_isolated_backend_can_complete(tmp_path):
    with ChapterLedger(tmp_path, ["a"], {}) as ledger:
        run(ledger, require_isolation=True,
            submit=lambda *_: {"page_id": "one", "xong": True, "vung": REGIONS, "cau_hinh_rieng": True,
                               "image_width": 32, "image_height": 48})
        assert ledger.completed(0)


def test_poll_has_overall_deadline_and_tolerates_get_failure():
    elapsed = [0.0]
    def offline(_):
        raise OSError("offline")
    with pytest.raises(TimeoutError):
        wait_for_page({"page_id": "one"}, offline, lambda: False,
                      timeout=3, clock=lambda: elapsed[0], sleep=lambda seconds: elapsed.__setitem__(0, elapsed[0] + seconds))
    assert elapsed[0] == 3


def test_failed_page_and_forbidden_poll_do_not_wait_forever():
    with pytest.raises(NeedsAttention, match="enqueue_failed"):
        wait_for_page({"page_id": "one", "loi": "enqueue_failed"}, None, lambda: False)
    def forbidden(_):
        raise HTTPError("https://api.invalid", 403, "Forbidden", {}, None)
    with pytest.raises(NeedsAttention, match="HTTP 403"):
        wait_for_page({"page_id": "one"}, forbidden, lambda: False, sleep=lambda _: None)


def test_parser_preserves_relative_chapter_base_and_lazy_image():
    chapters = chapter_links('<a href="chapter-2"><span>Chapter 2</span></a>', "https://example.org/book/")
    assert chapters[0]["url"] == "https://example.org/book/chapter-2"
    assert image_links('<img data-src="/001.jpg" src="/placeholder.png">', "https://example.org/chapter-1") == ["https://example.org/001.jpg"]
    assert image_links('<img src="/placeholder.png" data-src="/001.jpg">', "https://example.org/chapter-1") == ["https://example.org/001.jpg"]


def test_unknown_index_does_not_pretend_to_be_a_chapter():
    with pytest.raises(NeedsAttention, match="Chưa nhận diện"):
        chapter_links("<html></html>", "https://example.org/book/")


def test_directory_and_archive_use_natural_order(tmp_path):
    for name in ("10.jpg", "2.jpg", "1.jpg"):
        (tmp_path / name).write_bytes(image_bytes())
    assert [source.rsplit("/", 1)[-1] for source in local_image_sources(tmp_path)] == ["1.jpg", "2.jpg", "10.jpg"]
    archive_path = tmp_path / "test.cbz"
    with zipfile.ZipFile(archive_path, "w") as archive:
        for name in ("10.jpg", "2.jpg", "1.jpg"):
            archive.writestr(f"chapter/{name}", image_bytes())
    sources = archive_sources(archive_path)
    assert [json.loads(source.split("::", 1)[1])[1] for source in sources] == ["chapter/1.jpg", "chapter/2.jpg", "chapter/10.jpg"]
    assert read_local_source(sources[0]) == image_bytes()


@pytest.mark.parametrize("name", ["../bad.jpg", "/bad.jpg", "C:/bad.jpg", "dir/../../bad.jpg"])
def test_archive_rejects_unsafe_paths(tmp_path, name):
    path = tmp_path / "bad.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(name, image_bytes())
    with pytest.raises(NeedsAttention, match="không an toàn"):
        archive_sources(path)


def test_archive_limit_checked_before_translation(tmp_path, monkeypatch):
    import sources
    monkeypatch.setattr(sources, "MAX_PAGES", 1)
    path = tmp_path / "big.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("1.jpg", image_bytes())
        archive.writestr("2.jpg", image_bytes())
    with pytest.raises(NeedsAttention, match="200 trang"):
        archive_sources(path)


def test_legacy_backend_rejects_resume_without_private_ack(tmp_path):
    with ChapterLedger(tmp_path, ["a"], {}) as ledger:
        ledger.update(0, status="submitted", page_id="old", isolated=False)
        with pytest.raises(NeedsAttention, match="tách cấu hình"):
            run(ledger, require_isolation=True, submit=lambda *_: pytest.fail("must not resubmit"))


def test_preflight_failure_sends_no_customer_data_and_remains_retryable(tmp_path):
    with ChapterLedger(tmp_path, ["a"], {}) as ledger:
        with pytest.raises(NeedsAttention, match="Máy chủ chưa hỗ trợ"):
            run(ledger, preflight=lambda: require_private_backend({"status": "ok"}),
                submit=lambda *_: pytest.fail("customer data must not leave before preflight"))
        assert ledger.data["pages"][0]["status"] == "pending"
        run(ledger, preflight=lambda: require_private_backend({"translation_capabilities": {"private_context_v1": True}}))
        assert ledger.completed(0)


@pytest.mark.parametrize("code", [401, 403, 413, 429])
def test_explicitly_rejected_upload_can_be_retried(tmp_path, code):
    with ChapterLedger(tmp_path, ["a"], {}) as ledger:
        def rejected(*_):
            raise HTTPError("https://api.invalid", code, "rejected", {}, None)
        with pytest.raises(HTTPError):
            run(ledger, submit=rejected)
        assert ledger.data["pages"][0]["status"] == "pending"
        run(ledger)
        assert ledger.completed(0)


def test_server_error_after_upload_is_ambiguous(tmp_path):
    with ChapterLedger(tmp_path, ["a"], {}) as ledger:
        def failed(*_):
            raise HTTPError("https://api.invalid", 500, "failed", {}, None)
        with pytest.raises(HTTPError):
            run(ledger, submit=failed)
        with pytest.raises(NeedsAttention, match="chưa xác định"):
            run(ledger, submit=lambda *_: pytest.fail("must not repeat ambiguous upload"))


def test_image_endpoint_without_extension_is_not_silently_lost():
    assert image_links('<img src="/1.jpg"><img src="/page/2">', "https://example.org/chapter-1") == [
        "https://example.org/1.jpg", "https://example.org/page/2"]


def test_completed_resume_reuses_context_for_next_page(tmp_path):
    with ChapterLedger(tmp_path, ["a", "b"], {}) as ledger:
        ledger.check_source(0, image_bytes())
        ledger.finish_page(0, image_bytes("red"), REGIONS)
    contexts = []
    with ChapterLedger(tmp_path, ["a", "b"], {}) as ledger:
        run(ledger, submit=lambda data, index, context: contexts.append((index, list(context)))
            or {"page_id": "second", "xong": True, "vung": REGIONS})
    assert contexts == [(1, ["Hello = Chào"])]


def test_coordinates_scale_back_to_original_upload():
    regions = original_coordinates(REGIONS, image_bytes(), {"image_width": 16, "image_height": 24})
    assert regions[0]["x"] == 2
    assert regions[0]["w"] == 40
    assert REGIONS[0]["w"] == 20  # input response is not mutated


def test_truncated_jpeg_is_not_accepted_as_completed_image(tmp_path):
    from production import verify_image
    with pytest.raises(OSError):
        verify_image(image_bytes()[:-20])


def test_reader_url_is_not_replaced_by_previous_and_next_navigation():
    url = "https://example.org/book/chapter-12.5?reader=1"
    html = '<a href="chapter-12">Previous chapter</a><a href="chapter-13">Next chapter</a>'
    chapters = chapter_links(html, url)
    assert len(chapters) == 1
    assert chapters[0]["url"] == url
    assert chapters[0]["so"] == 12.5


def test_empty_srcset_falls_back_to_src_instead_of_crashing():
    assert image_links('<img srcset=" , " src="/page.jpg">', "https://example.org/chapter-1") == [
        "https://example.org/page.jpg"]


@pytest.mark.parametrize("suffix", ["gif", "svg", "tiff", "avif"])
@pytest.mark.parametrize("kind", ["directory", "archive"])
def test_mixed_supported_and_unsupported_images_do_not_silently_lose_pages(tmp_path, suffix, kind):
    if kind == "directory":
        (tmp_path / "1.jpg").write_bytes(image_bytes())
        (tmp_path / f"2.{suffix}").write_bytes(b"unsupported page")
        discover = lambda: local_image_sources(tmp_path)
    else:
        path = tmp_path / "chapter.cbz"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("1.jpg", image_bytes())
            archive.writestr(f"2.{suffix}", b"unsupported page")
        discover = lambda: archive_sources(path)
    with pytest.raises(NeedsAttention, match="chưa được hỗ trợ"):
        discover()


@pytest.mark.parametrize("limit", ["MAX_PAGES", "MAX_TOTAL_BYTES", "MAX_PAGE_BYTES"])
def test_directory_limits_checked_before_translation(tmp_path, monkeypatch, limit):
    import sources
    (tmp_path / "1.jpg").write_bytes(image_bytes())
    (tmp_path / "2.jpg").write_bytes(image_bytes())
    monkeypatch.setattr(sources, limit, 1)
    with pytest.raises(NeedsAttention, match="giới hạn"):
        local_image_sources(tmp_path)


def test_empty_directory_is_explicitly_rejected(tmp_path):
    (tmp_path / "README.txt").write_text("metadata")
    with pytest.raises(NeedsAttention, match="không chứa ảnh"):
        local_image_sources(tmp_path)


def test_poll_does_not_start_another_network_call_at_deadline():
    elapsed = [0.0]
    calls = []
    def fetch(page_id):
        calls.append(page_id)
        return {"page_id": page_id, "xong": False}
    with pytest.raises(TimeoutError):
        wait_for_page({"page_id": "one"}, fetch,
                      lambda: False, timeout=1, interval=2, clock=lambda: elapsed[0],
                      sleep=lambda seconds: elapsed.__setitem__(0, elapsed[0] + seconds))
    assert calls == ["one"]


@pytest.mark.parametrize("slug", ["step-1", "concept-2", "mychapter-3"])
def test_chapter_marker_inside_series_word_does_not_replace_index(slug):
    chapters = chapter_links('<a href="chapter-2">Chapter 2</a><a href="chapter-3">Chapter 3</a>',
                             f"https://example.org/manga/{slug}/")
    assert [chapter["so"] for chapter in chapters] == [2, 3]


def test_last_chapter_marker_identifies_current_page():
    chapters = chapter_links('<a href="../chapter-11">Previous</a>',
                             "https://example.org/chapter-1-series/chapter-12")
    assert chapters[0]["so"] == 12
