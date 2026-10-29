"""Client contract only; real PostgreSQL concurrency is tested separately."""
import json
from urllib.error import HTTPError

import pytest

from production import ChapterLedger, NeedsAttention, require_production_backend
from test_production import image_bytes, run, REGIONS


HEALTH = {"translation_capabilities": {"private_context_v1": True, "idempotent_upload_v1": True}}


def keyed_run(ledger, **overrides):
    options = dict(idempotent_submit=True, preflight=lambda: require_production_backend(HEALTH))
    options.update(overrides)
    return run(ledger, **options)


def result(ledger, index=0):
    return {"page_id": f"page-{index}", "request_key": ledger.data["pages"][index]["request_key"],
            "cau_hinh_rieng": True, "xong": True, "vung": REGIONS}


def lose_response(ledger):
    def lost(*args):
        # Durable key + protocol/context are present BEFORE the upload is called.
        persisted = json.loads(ledger.path.read_text())["pages"][0]
        assert persisted["request_key"] == ledger.data["pages"][0]["request_key"]
        assert persisted["request_payload_version"] == 1
        assert persisted["status"] == "submitting"
        raise OSError("response lost")
    with pytest.raises(OSError):
        keyed_run(ledger, submit=lost)
    return ledger.data["pages"][0]["request_key"]


def test_restart_reconciles_existing_key_without_posting_again(tmp_path):
    with ChapterLedger(tmp_path, ["a"], {}) as ledger:
        key = lose_response(ledger)
    with ChapterLedger(tmp_path, ["a"], {}) as ledger:
        looked_up = []
        def lookup(request_key):
            looked_up.append(request_key)
            return result(ledger)
        keyed_run(ledger, lookup_request=lookup, submit=lambda *_: pytest.fail("must not repost an accepted page"))
        assert looked_up == [key]
        assert ledger.completed(0)


def test_missing_lookup_reposts_identical_key_and_bytes_once_on_resume(tmp_path):
    with ChapterLedger(tmp_path, ["a"], {}) as ledger:
        key = lose_response(ledger)
        calls = []
        def submit(data, index, context):
            calls.append((data, ledger.data["pages"][index]["request_key"], list(context)))
            return result(ledger)
        keyed_run(ledger, lookup_request=lambda _: None, submit=submit)
        assert calls == [(image_bytes(), key, [])]
        assert ledger.completed(0)


def test_repeated_network_failure_never_changes_key_or_loops_post(tmp_path):
    with ChapterLedger(tmp_path, ["a"], {}) as ledger:
        key = lose_response(ledger)
        count = []
        def failed(*args):
            count.append(True)
            raise OSError("offline")
        with pytest.raises(OSError):
            keyed_run(ledger, lookup_request=lambda _: None, submit=failed)
        assert len(count) == 1
        assert ledger.data["pages"][0]["request_key"] == key


@pytest.mark.parametrize("code", [401, 403, 429, 500, 410])
def test_lookup_errors_do_not_trigger_post_or_generate_new_key(tmp_path, code):
    with ChapterLedger(tmp_path, ["a"], {}) as ledger:
        key = lose_response(ledger)
        def lookup(_):
            raise HTTPError("https://api.invalid", code, "error", {}, None)
        with pytest.raises(HTTPError):
            keyed_run(ledger, lookup_request=lookup, submit=lambda *_: pytest.fail("must not repost after lookup error"))
        assert ledger.data["pages"][0]["request_key"] == key


@pytest.mark.parametrize("wrong", [None, "other-key"])
def test_missing_or_wrong_key_ack_keeps_server_id_but_blocks_rendering(tmp_path, wrong):
    with ChapterLedger(tmp_path, ["a"], {}) as ledger:
        def submit(*args):
            response = result(ledger)
            response["request_key"] = wrong
            return response
        with pytest.raises(NeedsAttention, match="mã yêu cầu"):
            keyed_run(ledger, submit=submit, render=lambda *_: pytest.fail("must not render wrong acknowledgement"))
        assert ledger.data["pages"][0]["page_id"] == "page-0"
        assert not ledger.output(0).exists()
        with pytest.raises(NeedsAttention, match="mã yêu cầu"):
            keyed_run(ledger, submit=lambda *_: pytest.fail("must not repost known page ID"))


def test_old_ambiguous_upload_cannot_be_upgraded_with_a_new_key(tmp_path):
    with ChapterLedger(tmp_path, ["a"], {}) as ledger:
        ledger.update(0, status="submitting")
        with pytest.raises(NeedsAttention, match="chưa xác định"):
            keyed_run(ledger, submit=lambda *_: pytest.fail("old ambiguous upload has no server key"))
        assert "request_key" not in ledger.data["pages"][0]


def test_legacy_backend_prevents_keyed_upload_before_customer_data_is_sent(tmp_path):
    with ChapterLedger(tmp_path, ["a"], {}) as ledger:
        with pytest.raises(NeedsAttention, match="phục hồi"):
            keyed_run(ledger, preflight=lambda: require_production_backend(
                {"translation_capabilities": {"private_context_v1": True}}),
                submit=lambda *_: pytest.fail("no upload to legacy server"))
        assert ledger.data["pages"][0]["status"] == "pending"
        assert "request_key" not in ledger.data["pages"][0]


def test_changed_source_stops_before_reconcile_or_resubmit(tmp_path):
    with ChapterLedger(tmp_path, ["a"], {}) as ledger:
        lose_response(ledger)
        with pytest.raises(NeedsAttention, match="nguồn đã thay đổi"):
            keyed_run(ledger, load=lambda _: image_bytes("red"),
                      lookup_request=lambda _: pytest.fail("changed source"),
                      submit=lambda *_: pytest.fail("changed source"))


def test_submission_context_is_frozen_when_key_is_created(tmp_path):
    with ChapterLedger(tmp_path, ["a", "b"], {}) as ledger:
        def submit(data, index, context):
            if index == 1:
                raise OSError("lost")
            return result(ledger, index)
        with pytest.raises(OSError):
            keyed_run(ledger, submit=submit)
        saved_context = list(ledger.data["pages"][1]["request_context"])
        assert saved_context == ["Hello = Chào"]
        # A metadata correction to a preceding page must not change the already submitted payload.
        ledger.data["pages"][0]["regions"] = [{"chu_goc": "Hello", "ban_dich": "Xin chào"}]
        seen = []
        def resubmit(data, index, context):
            seen.append(list(context))
            return result(ledger, index)
        keyed_run(ledger, lookup_request=lambda _: None, submit=resubmit)
        assert seen == [saved_context]
