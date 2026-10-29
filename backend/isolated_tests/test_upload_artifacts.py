"""Cleanup decisions only; thread scheduling is stubbed, PostgreSQL is not claimed."""
import asyncio
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("upload_artifacts", Path(__file__).parents[1] / "app/services/upload_artifacts.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture(autouse=True)
def inline_storage_callback(monkeypatch):
    # Unit scope is the decision to delete/preserve. The sandbox prevents reliable
    # cross-thread asyncio wakeups; real Starlette scheduling stays unverified here.
    async def inline(function, *args):
        return function(*args)
    monkeypatch.setattr(module, "run_in_threadpool", inline)


class Session:
    def __init__(self):
        self.rollbacks = 0
    async def rollback(self):
        self.rollbacks += 1


class Storage:
    def __init__(self):
        self.deleted = []
    def delete_prefix(self, prefix):
        self.deleted.append(prefix)


def guard():
    instance = module.UploadArtifactGuard(Session(), "owner", "key")
    instance.project_id, instance.page_id = "private-project", "page"
    instance.storage = Storage()
    return instance


def fail(instance):
    async def run():
        async with instance:
            raise RuntimeError("original failure")
    with pytest.raises(RuntimeError, match="original failure"):
        asyncio.run(run())


def test_before_commit_failure_rolls_back_then_deletes_only_its_project():
    instance = guard()
    fail(instance)
    assert instance.session.rollbacks == 1
    assert instance.storage.deleted == ["projects/private-project/"]


@pytest.mark.parametrize("accepted", [False, True])
def test_uncertain_commit_checks_acceptance_before_deletion(accepted):
    instance = guard()
    instance.commit_attempted = True
    async def check():
        assert instance.session.rollbacks == 1
        assert instance.storage.deleted == []
        return accepted
    instance._accepted = check
    fail(instance)
    assert instance.storage.deleted == ([] if accepted else ["projects/private-project/"])


def test_unreachable_database_preserves_artifacts_and_reports_reconciliation(caplog):
    instance = guard()
    instance.commit_attempted = True
    async def check():
        raise OSError("database unreachable")
    instance._accepted = check
    fail(instance)
    assert instance.storage.deleted == []
    assert "reconciliation needed" in caplog.text
    assert "private-project" in caplog.text


@pytest.mark.parametrize("skip", ["committed", "legacy", "no_storage"])
def test_accepted_legacy_or_not_written_artifacts_are_not_deleted(skip):
    instance = guard()
    storage = instance.storage
    if skip == "committed":
        instance.committed = True
    elif skip == "legacy":
        instance.request_key = None
    else:
        instance.storage = None
    fail(instance)
    assert storage.deleted == []


def test_cleanup_error_does_not_hide_original_error(caplog):
    instance = guard()
    def broken(prefix):
        raise OSError("storage down")
    instance.storage.delete_prefix = broken
    fail(instance)
    assert "reconciliation needed" in caplog.text
