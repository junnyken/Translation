"""Durable keyed-upload detect publishing. Requires migration 0038 and beat.

Only committed outbox rows are published. PostgreSQL locks coordinate publishers;
worker-side claim handles the unavoidable publish/commit ambiguity.
"""
from datetime import datetime, timezone
import argparse
import json
import logging
import uuid

from app.services.outbox_policy import MAX_ATTEMPTS, deliver_locked, delivery_state

log = logging.getLogger(__name__)


def _publish(job_id):
    from app.services.dispatch import dispatch_detect_job
    return dispatch_detect_job(job_id, task_id=str(job_id))


def try_publish_job(job_id, *, publish=None):
    from sqlalchemy import select
    from app.core.db_sync import sync_session
    from app.models import DetectOutbox, Job, Page

    with sync_session() as session:
        row = session.scalar(select(DetectOutbox).where(DetectOutbox.job_id == job_id)
                             .with_for_update(skip_locked=True))
        if row is None:
            return "busy_or_missing"
        job = session.get(Job, job_id)
        page = session.get(Page, job.page_id) if job else None
        state = deliver_locked(row, job_status=job.status.value if job else None,
                               page_status=page.status.value if page else None,
                               publish=publish or _publish, now=datetime.now(timezone.utc))
        session.commit()
        return state


def publish_due(*, limit=20):
    from sqlalchemy import select
    from app.core.db_sync import sync_session
    from app.models import DetectOutbox

    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    with sync_session() as session:
        ids = list(session.scalars(select(DetectOutbox.job_id).where(
            DetectOutbox.published_at.is_(None), DetectOutbox.abandoned_at.is_(None),
            DetectOutbox.attempts < MAX_ATTEMPTS,
            DetectOutbox.next_attempt_at <= datetime.now(timezone.utc),
        ).order_by(DetectOutbox.next_attempt_at, DetectOutbox.job_id).limit(limit)))
    counts = {}
    for job_id in ids:
        state = try_publish_job(job_id)
        counts[state] = counts.get(state, 0) + 1
        # Avoid waiting on the same broker outage once for every row in this batch.
        if state in ("retrying", "needs_attention"):
            break
    return counts


def claim_detect_job(job_id):
    """Legacy jobs bypass gate. Outbox jobs may transition queued→running once.

    No outbox lock is taken here: publishers lock Outbox first, so a subsequent
    Job→Outbox lock would create an inverted lock order. Timestamps are atomic.
    """
    from sqlalchemy import select, update
    from app.core.db_sync import sync_session
    from app.models import DetectOutbox, Job, Page
    from app.models.enums import JobStatus, JobType, PageStatus

    with sync_session() as session:
        if session.get(DetectOutbox, job_id) is None:
            return "legacy"
        queued_page = select(Page.id).where(Page.id == Job.page_id, Page.status == PageStatus.queued).exists()
        active_intent = select(DetectOutbox.job_id).where(
            DetectOutbox.job_id == Job.id, DetectOutbox.abandoned_at.is_(None),
        ).exists()
        now = datetime.now(timezone.utc)
        result = session.execute(update(Job).where(
            Job.id == job_id, Job.type == JobType.detect, Job.status == JobStatus.queued, queued_page, active_intent,
        ).values(status=JobStatus.running, started_at=now, heartbeat_at=now))
        session.commit()
        return "claimed" if result.rowcount == 1 else "duplicate_or_stale"


def retry_unpublished(job_id):
    from sqlalchemy import select
    from app.core.db_sync import sync_session
    from app.models import DetectOutbox, Job, Page
    from app.models.enums import JobStatus, PageStatus

    with sync_session() as session:
        row = session.scalar(select(DetectOutbox).where(DetectOutbox.job_id == job_id).with_for_update())
        job = session.get(Job, job_id)
        page = session.get(Page, job.page_id) if job else None
        if (row is None or row.published_at is not None or row.abandoned_at is not None
                or row.attempts < MAX_ATTEMPTS or job is None or job.status != JobStatus.queued
                or page is None or page.status != PageStatus.queued):
            raise ValueError("Chỉ thử lại việc hết lần gửi, chưa được broker nhận và còn đang chờ.")
        row.attempts = 0
        row.next_attempt_at = datetime.now(timezone.utc)
        row.last_error = None
        session.commit()


def status_rows(limit):
    from sqlalchemy import select
    from app.core.db_sync import sync_session
    from app.models import DetectOutbox, Job, Page

    with sync_session() as session:
        rows = session.execute(select(DetectOutbox, Job.status, Page.status).join(
            Job, Job.id == DetectOutbox.job_id).join(Page, Page.id == Job.page_id)
            .order_by(DetectOutbox.created_at).limit(limit)).all()
        return [{"job_id": str(row.job_id), "state": delivery_state(row, job.value, page.value),
                 "attempts": row.attempts, "next_attempt_at": row.next_attempt_at.isoformat()}
                for row, job, page in rows]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Kiểm tra/thử lại gửi việc riêng đã được nhận; không tạo trang/lượt mới.")
    sub = parser.add_subparsers(dest="command", required=True)
    status = sub.add_parser("status")
    status.add_argument("--limit", type=int, choices=range(1, 101), default=20)
    retry = sub.add_parser("retry")
    retry.add_argument("job_id", type=uuid.UUID)
    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            result = status_rows(args.limit)
        else:
            retry_unpublished(args.job_id)
            result = {"job_id": str(args.job_id), "state": "pending"}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        log.exception("outbox operator command failed")
        print(f"Chưa thực hiện: {type(exc).__name__}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
