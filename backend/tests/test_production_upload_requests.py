"""Requires real PostgreSQL migrations. Provider/broker are intentionally excluded."""
import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.db import get_session
from app.main import app
from app.models import Job, Page, Project, SoCaiHanMuc, UploadRequest, DetectOutbox
from app.api.v1 import routes


def fields(key, **overrides):
    data = dict(request_key=str(key), tao_chapter_rieng="true", source_lang="en",
                target_lang="vi", engine="google_fast", che_do="chi_chu",
                font_style="comic", tu_dien_rieng="Pepper = Tiêu")
    data.update(overrides)
    return data


async def post(client, image, key, **overrides):
    return await client.post("/api/v1/doc-truyen/trang", data=fields(key, **overrides),
                             files={"file": ("page.png", image, "image/png")})


async def counts(session):
    return [await session.scalar(select(func.count()).select_from(model))
            for model in (Project, Page, Job, SoCaiHanMuc, UploadRequest, DetectOutbox)]


async def test_replay_returns_original_without_creating_or_charging(client, session, sample_page_image, fake_dispatch):
    key = uuid.uuid4()
    first = await post(client, sample_page_image, key)
    assert first.status_code == 202
    before = await counts(session)
    second = await post(client, sample_page_image, key)
    assert second.status_code == 202
    assert second.json()["page_id"] == first.json()["page_id"]
    assert second.json()["request_key"] == str(key)
    assert await counts(session) == before
    assert len(fake_dispatch) == 1
    lookup = await client.get(f"/api/v1/doc-truyen/yeu-cau/{key}")
    assert lookup.status_code == 200
    assert lookup.json()["page_id"] == first.json()["page_id"]
    assert lookup.json()["request_key"] == str(key)


@pytest.mark.parametrize("override", [{"tu_dien_rieng": "changed"}, {"font_style": "romance"},
                                       {"target_lang": "en"}, {"che_do": "day_du"}])
async def test_same_key_changed_choices_is_conflict(client, session, sample_page_image, override):
    key = uuid.uuid4()
    assert (await post(client, sample_page_image, key)).status_code == 202
    before = await counts(session)
    response = await post(client, sample_page_image, key, **override)
    assert response.status_code == 409
    await session.rollback()  # test client shares session; production dependency closes it.
    assert await counts(session) == before


async def test_replay_precedes_engine_admission_checks(client, sample_page_image, monkeypatch):
    key = uuid.uuid4()
    assert (await post(client, sample_page_image, key)).status_code == 202
    def unavailable(*args, **kwargs):
        pytest.fail("accepted replay reached new-job admission")
    monkeypatch.setattr(routes, "_kiem_engine", unavailable)
    assert (await post(client, sample_page_image, key)).status_code == 202


async def test_deleted_page_retains_key_tombstone(client, session, sample_page_image):
    key = uuid.uuid4()
    response = await post(client, sample_page_image, key)
    assert response.status_code == 202
    project_id = uuid.UUID(response.json()["project_id"])
    await session.execute(delete(Project).where(Project.id == project_id))
    await session.commit()
    # SET NULL occurs in the database even for cascade project deletion.
    session.expire_all()
    row = await session.scalar(select(UploadRequest).where(UploadRequest.request_key == key))
    assert row is not None and row.page_id is None
    before = await counts(session)
    assert (await client.get(f"/api/v1/doc-truyen/yeu-cau/{key}")).status_code == 410
    assert (await post(client, sample_page_image, key)).status_code == 410
    await session.rollback()
    assert await counts(session) == before


async def test_different_owner_cannot_lookup_another_request(client, client_b, session, sample_page_image):
    # Fixtures share an AsyncSession sequentially; ownership is in each client's headers.
    key = uuid.uuid4()
    assert (await post(client, sample_page_image, key)).status_code == 202
    assert (await client_b.get(f"/api/v1/doc-truyen/yeu-cau/{key}")).status_code == 404
    second = await post(client_b, sample_page_image, key)
    assert second.status_code == 202
    assert await session.scalar(select(func.count()).select_from(UploadRequest)) == 2


@pytest.fixture
async def independent_client(engine, nguoi_a, session):
    # Unlike default API fixtures, EVERY HTTP request uses its own real DB transaction.
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async def independent_session():
        async with maker() as db:
            yield db
    app.dependency_overrides[get_session] = independent_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False),
                               base_url="http://test", headers={"Authorization": f"Bearer {nguoi_a[1]}"}) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


async def test_concurrent_same_key_creates_exactly_one_page(independent_client, session, sample_page_image, fake_dispatch):
    key = uuid.uuid4()
    first, second = await asyncio.wait_for(asyncio.gather(
        post(independent_client, sample_page_image, key), post(independent_client, sample_page_image, key)), timeout=20)
    assert first.status_code == second.status_code == 202
    assert first.json()["page_id"] == second.json()["page_id"]
    assert await counts(session) == [1, 1, 1, 1, 1, 1]
    assert len(fake_dispatch) == 1


async def test_concurrent_different_payload_one_conflicts(independent_client, session, sample_page_image):
    key = uuid.uuid4()
    responses = await asyncio.wait_for(asyncio.gather(
        post(independent_client, sample_page_image, key),
        post(independent_client, sample_page_image, key, tu_dien_rieng="Other glossary")), timeout=20)
    assert sorted(response.status_code for response in responses) == [202, 409]
    assert await counts(session) == [1, 1, 1, 1, 1, 1]


async def test_failed_first_transaction_allows_same_key_recovery(independent_client, session, sample_page_image, monkeypatch):
    key = uuid.uuid4()
    original = routes.giu_cho_moi_chot
    calls = []
    async def fail_once(*args, **kwargs):
        await original(*args, **kwargs)
        calls.append(True)
        if len(calls) == 1:
            raise RuntimeError("simulate crash after quota reservation before commit")
    monkeypatch.setattr(routes, "giu_cho_moi_chot", fail_once)
    first = await post(independent_client, sample_page_image, key)
    assert first.status_code == 500
    assert await counts(session) == [0, 0, 0, 0, 0, 0]
    second = await post(independent_client, sample_page_image, key)
    assert second.status_code == 202
    assert await counts(session) == [1, 1, 1, 1, 1, 1]


async def test_enqueue_failure_replay_does_not_enqueue_or_charge_again(client, session, sample_page_image, monkeypatch):
    attempts = []
    def failed(job_id, **kwargs):
        attempts.append(job_id)
        return False, "enqueue_failed"
    monkeypatch.setattr(routes, "dispatch_detect_job", failed)
    key = uuid.uuid4()
    first = await post(client, sample_page_image, key)
    assert first.status_code == 202
    before = await counts(session)
    again = await post(client, sample_page_image, key)
    assert again.status_code == 202
    assert again.json()["page_id"] == first.json()["page_id"]
    assert len(attempts) == 1
    outbox = (await session.scalars(select(DetectOutbox))).one()
    assert outbox.attempts == 1
    assert outbox.published_at is None
    assert await counts(session) == before


async def test_quota_rejection_writes_no_private_artifacts(independent_client, session, sample_page_image, monkeypatch, storage_root):
    from fastapi import HTTPException
    from app.services.storage import LocalObjectStorage
    storage = LocalObjectStorage(storage_root)
    before = set(storage.list_prefix("projects/"))
    async def deny(*args, **kwargs):
        raise HTTPException(429, "quota exceeded")
    monkeypatch.setattr(routes, "giu_cho_moi_chot", deny)
    response = await post(independent_client, sample_page_image, uuid.uuid4())
    assert response.status_code == 429
    assert await counts(session) == [0, 0, 0, 0, 0, 0]
    assert set(storage.list_prefix("projects/")) == before


async def test_storage_failure_cleans_glossary_and_image(independent_client, session, sample_page_image, monkeypatch, storage_root):
    from app.services.storage import LocalObjectStorage
    storage = LocalObjectStorage(storage_root)
    before = set(storage.list_prefix("projects/"))
    original = LocalObjectStorage.save_page_image
    def fail_after_write(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise OSError("failed after writing image")
    monkeypatch.setattr(LocalObjectStorage, "save_page_image", fail_after_write)
    assert (await post(independent_client, sample_page_image, uuid.uuid4())).status_code == 500
    assert await counts(session) == [0, 0, 0, 0, 0, 0]
    assert set(storage.list_prefix("projects/")) == before


@pytest.mark.parametrize("after_commit", [False, True])
async def test_commit_error_reconciles_before_deleting_artifacts(independent_client, session, sample_page_image,
                                                                 monkeypatch, storage_root, fake_dispatch, after_commit):
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.services.storage import LocalObjectStorage
    storage = LocalObjectStorage(storage_root)
    before = set(storage.list_prefix("projects/"))
    original = AsyncSession.commit
    failed = []
    async def uncertain_commit(self):
        # UploadRequest is already flushed when creating the outbox Job FK.
        # Query this transaction by its exact key rather than inspecting self.new.
        if not failed and await self.scalar(
            select(UploadRequest.request_key).where(UploadRequest.request_key == key)
        ) == key:
            failed.append(True)
            if after_commit:
                await original(self)
            raise OSError("commit outcome uncertain")
        await original(self)
    monkeypatch.setattr(AsyncSession, "commit", uncertain_commit)
    key = uuid.uuid4()
    assert (await post(independent_client, sample_page_image, key)).status_code == 500
    assert failed == [True]  # Verify the intended commit fault actually happened.
    if after_commit:
        assert await counts(session) == [1, 1, 1, 1, 1, 1]
        assert set(storage.list_prefix("projects/")) > before
        assert (await post(independent_client, sample_page_image, key)).status_code == 202
        assert len(fake_dispatch) == 0  # committed outbox survives; periodic publisher repairs this gap.
    else:
        assert await counts(session) == [0, 0, 0, 0, 0, 0]
        assert set(storage.list_prefix("projects/")) == before
        assert (await post(independent_client, sample_page_image, key)).status_code == 202
        assert len(fake_dispatch) == 1


async def test_outbox_claim_allows_only_one_consumer(client, session, sample_page_image, fake_dispatch):
    from starlette.concurrency import run_in_threadpool
    from app.services.upload_outbox import claim_detect_job
    response = await post(client, sample_page_image, uuid.uuid4())
    assert response.status_code == 202
    job_id = (await session.scalars(select(DetectOutbox.job_id))).one()
    claims = await asyncio.gather(*[run_in_threadpool(claim_detect_job, job_id) for _ in range(2)])
    assert sorted(claims) == ["claimed", "duplicate_or_stale"]
    await session.rollback()
    job = await session.get(Job, job_id)
    assert job.status.value == "running"
    assert job.started_at is not None and job.heartbeat_at is not None
    assert await run_in_threadpool(claim_detect_job, job_id) == "duplicate_or_stale"


async def test_publisher_reset_refuses_published_job(client, session, sample_page_image, fake_dispatch):
    from starlette.concurrency import run_in_threadpool
    from app.services.upload_outbox import retry_unpublished
    assert (await post(client, sample_page_image, uuid.uuid4())).status_code == 202
    job_id = (await session.scalars(select(DetectOutbox.job_id))).one()
    with pytest.raises(ValueError):
        await run_in_threadpool(retry_unpublished, job_id)


async def test_abandoned_intent_cannot_be_claimed(client, session, sample_page_image, fake_dispatch):
    from datetime import datetime, timezone
    from starlette.concurrency import run_in_threadpool
    from app.services.upload_outbox import claim_detect_job
    assert (await post(client, sample_page_image, uuid.uuid4())).status_code == 202
    outbox = (await session.scalars(select(DetectOutbox))).one()
    outbox.abandoned_at = datetime.now(timezone.utc)
    job_id = outbox.job_id
    await session.commit()
    assert await run_in_threadpool(claim_detect_job, job_id) == "duplicate_or_stale"


async def test_concurrent_publishers_publish_intent_once(client, session, sample_page_image, fake_dispatch):
    from starlette.concurrency import run_in_threadpool
    from app.services.upload_outbox import try_publish_job
    assert (await post(client, sample_page_image, uuid.uuid4())).status_code == 202
    outbox = (await session.scalars(select(DetectOutbox))).one()
    job_id = outbox.job_id
    outbox.published_at = None
    await session.commit()
    sent = []
    def publish(jid):
        sent.append(jid)
        return True, None
    results = await asyncio.gather(*[
        run_in_threadpool(try_publish_job, job_id, publish=publish) for _ in range(2)
    ])
    assert results.count('published') == 1
    assert len(sent) == 1


async def test_accepted_message_with_failed_publication_commit_can_replay(client, session, sample_page_image,
                                                                        fake_dispatch, monkeypatch):
    from contextlib import contextmanager
    from sqlalchemy import event
    from starlette.concurrency import run_in_threadpool
    from app.core import db_sync
    from app.services.upload_outbox import try_publish_job, claim_detect_job
    assert (await post(client, sample_page_image, uuid.uuid4())).status_code == 202
    outbox = (await session.scalars(select(DetectOutbox))).one()
    job_id = outbox.job_id
    outbox.published_at = None
    await session.commit()
    original_session = db_sync.sync_session
    sent = []
    def publish(jid):
        sent.append(jid)
        return True, None
    def fail_commit(_):
        raise RuntimeError('simulated process loss before publication commit')
    @contextmanager
    def failed_session():
        with original_session() as sync:
            event.listen(sync, 'before_commit', fail_commit, once=True)
            yield sync
    with monkeypatch.context() as patch:
        patch.setattr(db_sync, 'sync_session', failed_session)
        with pytest.raises(RuntimeError, match='simulated process loss'):
            await run_in_threadpool(try_publish_job, job_id, publish=publish)
    assert await run_in_threadpool(try_publish_job, job_id, publish=publish) == 'published'
    assert sent == [job_id, job_id]
    assert await run_in_threadpool(claim_detect_job, job_id) == 'claimed'
    assert await run_in_threadpool(claim_detect_job, job_id) == 'duplicate_or_stale'
