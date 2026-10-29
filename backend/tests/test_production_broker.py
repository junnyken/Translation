"""Real Redis + Celery worker + SQL claim, with a deterministic provider boundary.

Only run via the disposable Docker test stack. This is not an AI quality test.
"""
import os
import uuid
from threading import Event, Lock

import pytest

from celery.contrib.testing.worker import start_worker
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.concurrency import run_in_threadpool

from app.models import DetectOutbox, Job, Page
from app.models.enums import JobStatus, PageStatus
from test_production_upload_requests import post


@pytest.fixture(autouse=True)
def isolate_startup_hooks(monkeypatch):
    # Explicit publication below must be the only source of messages in these tests.
    from app.services import upload_outbox
    from app.workers.celery_app import settings
    monkeypatch.setattr(upload_outbox, 'publish_due', lambda **kwargs: {})
    monkeypatch.setattr(settings, 'worker_sweep_orphan_jobs_on_start', False)
    monkeypatch.setattr(settings, 'batch_danh_thuc_khi_worker_khoi_dong', False)


async def test_real_broker_duplicate_runs_provider_and_callback_once(client, session, sample_page_image,
                                                                     fake_dispatch, monkeypatch):
    assert os.environ.get('PRODUCTION_BROKER_TEST') == '1', 'Use the isolated Docker runner for this test.'
    from app.workers import tasks
    from app.workers.celery_app import celery_app
    from app.core.db_sync import sync_session

    response = await post(client, sample_page_image, uuid.uuid4())
    assert response.status_code == 202
    job_id = (await session.scalars(select(DetectOutbox.job_id))).one()
    calls, callbacks = [], []
    lock = Lock()
    entered, release = Event(), Event()

    def provider(jid, *, outbox_claimed=False):
        assert outbox_claimed
        with lock:
            calls.append(jid)
        entered.set()
        assert release.wait(20), "test did not release provider boundary"
        with sync_session() as sync:
            job = sync.get(Job, jid)
            assert job.status == JobStatus.running
            assert job.started_at is not None and job.heartbeat_at is not None
            job.status = JobStatus.done
            sync.get(Page, job.page_id).status = PageStatus.translated
            sync.commit()
        return {'status': 'done', 'job_id': str(jid)}

    def callback(*args, **kwargs):
        with lock:
            callbacks.append((args, kwargs))

    monkeypatch.setattr(tasks, '_run_detect', provider)
    monkeypatch.setattr(tasks, 'bao_ket_thuc_buoc', callback)
    queue = f'production-test-{uuid.uuid4().hex}'

    def consume():
        with start_worker(celery_app, pool='threads', concurrency=2, queues=[queue],
                          perform_ping_check=False, shutdown_timeout=30):
            first = tasks.run_detect_job.apply_async(args=[str(job_id)], queue=queue)
            try:
                assert entered.wait(15), "worker never reached provider boundary"
                duplicate = tasks.run_detect_job.apply_async(args=[str(job_id)], queue=queue)
                assert duplicate.get(timeout=15)['status'] == 'duplicate_ignored'
                assert callbacks == []  # First provider is still running.
                with sync_session() as sync:
                    assert sync.get(Job, job_id).status == JobStatus.running
            finally:
                release.set()
            assert first.get(timeout=30)['status'] == 'done'
            # A late delivery must not change finished results or emit callbacks.
            late = tasks.run_detect_job.apply_async(args=[str(job_id)], queue=queue).get(timeout=30)
            assert late['status'] == 'duplicate_ignored'
        assert calls == [job_id]
        assert len(callbacks) == 1
        assert callbacks[0][0][2] == 'completed'

    await run_in_threadpool(consume)
    await session.rollback()
    job = await session.get(Job, job_id)
    assert job.status == JobStatus.done
    page = await session.get(Page, job.page_id)
    assert page.status == PageStatus.translated


async def test_outbox_publishes_through_real_redis(client, session, sample_page_image, fake_dispatch, monkeypatch):
    assert os.environ.get('PRODUCTION_BROKER_TEST') == '1', 'Use the isolated Docker runner for this test.'
    from app.services.upload_outbox import try_publish_job
    from app.workers import tasks
    from app.workers.celery_app import celery_app

    assert (await post(client, sample_page_image, uuid.uuid4())).status_code == 202
    row = (await session.scalars(select(DetectOutbox))).one()
    job_id = row.job_id
    row.published_at = None
    await session.commit()
    queue = f'production-test-{uuid.uuid4().hex}'
    # This case checks publication/claim only. Provider and completion callback remain stubbed.
    monkeypatch.setattr(tasks, '_run_detect', lambda jid, **kwargs: {'status': 'done', 'job_id': str(jid)})
    monkeypatch.setattr(tasks, 'bao_ket_thuc_buoc', lambda *args, **kwargs: None)

    def consume():
        delivery = []
        def publish(jid):
            delivery.append(tasks.run_detect_job.apply_async(args=[str(jid)], task_id=str(jid), queue=queue))
            return True, None
        with start_worker(celery_app, pool='threads', concurrency=2, queues=[queue],
                          perform_ping_check=False, shutdown_timeout=30):
            assert try_publish_job(job_id, publish=publish) == 'published'
            assert delivery[0].get(timeout=30)['status'] == 'done'
            assert try_publish_job(job_id, publish=publish) == 'skipped'
            assert len(delivery) == 1

    await run_in_threadpool(consume)
    # The API fixture uses expire_on_commit=False. After its commit there is no
    # active transaction to roll back, so rollback() need not expire cached row.
    # Read from a new session to verify the publisher's committed DB state.
    async with async_sessionmaker(session.bind)() as verify:
        persisted = await verify.get(DetectOutbox, job_id)
        assert persisted is not None
        assert persisted.published_at is not None
