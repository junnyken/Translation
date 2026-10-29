"""Pure delivery policy; does not verify PostgreSQL locks or Celery delivery."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("outbox_policy", Path(__file__).parents[1] / "app/services/outbox_policy.py")
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)
MAX_ATTEMPTS = policy.MAX_ATTEMPTS
deliver_locked = policy.deliver_locked
delivery_state = policy.delivery_state
retry_delay = policy.retry_delay

NOW = datetime(2026, 10, 28, tzinfo=timezone.utc)


def row(**kwargs):
    fields = dict(job_id='job', attempts=0, next_attempt_at=NOW,
                  published_at=None, abandoned_at=None, last_error=None)
    fields.update(kwargs)
    return SimpleNamespace(**fields)


def deliver(r, publish=lambda _: (True, None), **kwargs):
    return deliver_locked(r, job_status=kwargs.get('job', 'queued'),
                          page_status=kwargs.get('page', 'queued'), publish=publish, now=NOW)


def test_backoff_is_bounded():
    assert [retry_delay(i) for i in range(1, 9)] == [30, 60, 120, 240, 300, 300, 300, 300]


def test_success_is_not_published_twice():
    r = row()
    sent = []
    assert deliver(r, lambda j: (sent.append(j) is None, None)) == 'published'
    assert deliver(r, lambda j: (sent.append(j) is None, None)) == 'skipped'
    assert sent == ['job']
    assert r.attempts == 1
    assert delivery_state(r, 'queued', 'queued') == 'published'
    assert delivery_state(r, 'running', 'detecting') == 'processing'


def test_failure_retries_then_requires_operator():
    r = row(attempts=MAX_ATTEMPTS - 1)
    assert deliver(r, lambda _: (False, 'offline')) == 'needs_attention'
    assert r.next_attempt_at == NOW + timedelta(seconds=300)
    assert delivery_state(r, 'queued', 'queued') == 'needs_attention'
    assert deliver(r) == 'skipped'


def test_exception_does_not_leak_exception_message():
    def fail(_):
        raise RuntimeError('secret broker credential')
    r = row()
    assert deliver(r, fail) == 'retrying'
    assert r.last_error == 'publish_error: RuntimeError'


@pytest.mark.parametrize('changes', [dict(next_attempt_at=NOW + timedelta(seconds=1)),
                                      dict(published_at=NOW), dict(abandoned_at=NOW)])
def test_ineligible_rows_do_not_publish(changes):
    def unexpected(_):
        pytest.fail('must not publish')
    assert deliver(row(**changes), unexpected) == 'skipped'


@pytest.mark.parametrize('job,page', [('running', 'queued'), ('done', 'done'), ('queued', 'detecting')])
def test_progressed_work_is_abandoned(job, page):
    r = row()
    assert deliver(r, lambda _: pytest.fail('must not publish'), job=job, page=page) == 'superseded'
    assert r.abandoned_at == NOW
    assert r.attempts == 0


def test_publish_before_database_commit_can_replay():
    # Simulate losing the in-memory transaction after broker accepted. Consumer
    # claim is separately responsible for suppressing duplicate AI execution.
    sent = []
    publish = lambda j: (sent.append(j) is None, None)
    assert deliver(row(), publish) == 'published'
    assert deliver(row(), publish) == 'published'
    assert sent == ['job', 'job']
