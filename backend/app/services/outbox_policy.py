"""Bounded delivery decisions. No SQL/Celery: published means broker accepted only."""
from datetime import timedelta

MAX_ATTEMPTS = 8


def retry_delay(attempt):
    return min(30 * 2 ** max(0, min(attempt - 1, 4)), 300)


def delivery_state(row, job_status, page_status):
    if job_status == "running":
        return "processing"
    if job_status in ("done", "failed"):
        return "finished"
    if row.abandoned_at is not None or job_status != "queued" or page_status != "queued":
        return "superseded"
    if row.published_at is not None:
        return "published"
    if row.attempts >= MAX_ATTEMPTS:
        return "needs_attention"
    return "retrying" if row.attempts else "pending"


def deliver_locked(row, *, job_status, page_status, publish, now):
    """Mutate a row already locked by SQL caller. Commit belongs to that caller.

    A crash after publish but before commit may replay; consumer must claim once.
    """
    if row.published_at is not None or row.abandoned_at is not None:
        return "skipped"
    if job_status != "queued" or page_status != "queued":
        row.abandoned_at = now
        row.last_error = "job_or_page_no_longer_queued"
        return "superseded"
    if row.attempts >= MAX_ATTEMPTS or row.next_attempt_at > now:
        return "skipped"
    row.attempts += 1
    try:
        accepted, reason = publish(row.job_id)
    except Exception as exc:
        accepted, reason = False, f"publish_error: {type(exc).__name__}"
    if accepted:
        row.published_at = now
        row.last_error = None
        return "published"
    # Keep broker exception text out of owner-facing API responses.
    row.last_error = str(reason or "broker_unavailable")[:2000]
    row.next_attempt_at = now + timedelta(seconds=retry_delay(row.attempts))
    return "needs_attention" if row.attempts >= MAX_ATTEMPTS else "retrying"
