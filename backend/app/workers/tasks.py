"""Celery task của M2 — tiêu thụ Job(type=detect) đã được tạo từ M1.

Nguyên tắc:
- Detect CHỈ chạy ở đây, không bao giờ chạy đồng bộ trong API handler.
- Idempotent: chạy lại trên cùng Page thì xóa region cũ trước khi ghi mới, không nhân đôi.
- Evidence-first: confidence thấp vẫn LƯU với status=low_confidence; lỗi/timeout ghi
  Job.status=failed + error_log và Page.status=detection_failed, không im lặng.
"""
from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.db_sync import sync_session
from app.models import Job, Page, TextRegion
from app.models.enums import JobStatus, JobType, PageStatus, RegionStatus, assert_transition
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()

_SOFT_LIMIT = settings.detect_timeout_seconds
_HARD_LIMIT = settings.detect_timeout_seconds + 15

#: Detector nạp 1 lần/process (weight ~91MB) — nạp lại mỗi ảnh sẽ rất chậm.
_detector = None


def get_detector():
    """Tạo detector dùng chung cho worker process. Import trễ để API không nạp onnxruntime."""
    global _detector
    if _detector is None:
        from app.services.detect.ctd import CTDDetector

        _detector = CTDDetector(
            weights_path=settings.model_weights_path,
            device=settings.ctd_device,
            conf_threshold=settings.ctd_conf_threshold,
            raw_min_conf=settings.ctd_raw_min_conf,
            nms_iou=settings.ctd_nms_iou,
            input_size=settings.ctd_input_size,
            intra_op_threads=settings.ctd_intra_op_threads,
        )
    return _detector


def reset_detector() -> None:
    """Dùng trong test để thay detector giả lập."""
    global _detector
    _detector = None


def resolve_image_path(image_path: str) -> str:
    """Ghép path tương đối trong DB với gốc storage (M1 lưu path tương đối)."""
    p = Path(image_path)
    if p.is_absolute():
        return str(p)
    return str(Path(settings.storage_local_root) / p)


def _mark_failed(job_id: uuid.UUID, page_id: uuid.UUID | None, reason: str) -> None:
    """Ghi thất bại bằng session MỚI (session cũ có thể đang hỏng vì exception)."""
    with sync_session() as session:
        job = session.get(Job, job_id)
        if job is not None:
            job.status = JobStatus.failed
            job.error_log = reason[:4000]
        if page_id is not None:
            page = session.get(Page, page_id)
            if page is not None:
                page.status = PageStatus.detection_failed
        session.commit()


def _run_detect(job_id: uuid.UUID) -> dict:
    started = time.perf_counter()
    with sync_session() as session:
        job = session.get(Job, job_id)
        if job is None:
            logger.warning("Job %s không tồn tại", job_id)
            return {"status": "job_not_found", "job_id": str(job_id)}
        if job.type is not JobType.detect:
            return {"status": "wrong_job_type", "job_id": str(job_id), "type": job.type.value}

        page = session.get(Page, job.page_id)
        if page is None:
            job.status = JobStatus.failed
            job.error_log = "page_not_found"
            session.commit()
            return {"status": "page_not_found", "job_id": str(job_id)}

        page_id = page.id
        image_path = resolve_image_path(page.image_path)

        job.status = JobStatus.running
        if page.status is not PageStatus.detecting:
            assert_transition(page.status, PageStatus.detecting)
            page.status = PageStatus.detecting
        session.commit()

    detector = get_detector()
    regions = detector.detect_regions(image_path)
    elapsed = time.perf_counter() - started

    from app.services.detect.geometry import mark_overlap_suspects

    flags = mark_overlap_suspects([r.bbox for r in regions], settings.ctd_overlap_suspect_ratio)

    with sync_session() as session:
        # Idempotent guard: xóa region cũ của page trước khi ghi mới (retry không nhân đôi).
        deleted = session.execute(
            delete(TextRegion).where(TextRegion.page_id == page_id)
        ).rowcount
        low_conf = 0
        for region, overlap in zip(regions, flags, strict=True):
            is_low = region.confidence < settings.ctd_conf_threshold
            low_conf += int(is_low)
            session.add(
                TextRegion(
                    page_id=page_id,
                    bbox_x=region.bbox.x,
                    bbox_y=region.bbox.y,
                    bbox_w=region.bbox.w,
                    bbox_h=region.bbox.h,
                    confidence=region.confidence,
                    overlap_suspect=overlap,
                    status=RegionStatus.low_confidence if is_low else RegionStatus.pending,
                )
            )

        page = session.get(Page, page_id)
        assert_transition(page.status, PageStatus.detected)
        page.status = PageStatus.detected

        job = session.get(Job, job_id)
        job.status = JobStatus.done
        job.error_log = None
        session.commit()

    logger.info(
        "detect job %s: %d region (%d low_confidence, %d overlap_suspect), xóa %d region cũ, %.1fs",
        job_id, len(regions), low_conf, sum(flags), deleted, elapsed,
    )
    return {
        "status": "done",
        "job_id": str(job_id),
        "page_id": str(page_id),
        "regions": len(regions),
        "low_confidence": low_conf,
        "overlap_suspect": sum(flags),
        "replaced_regions": deleted,
        "elapsed_seconds": round(elapsed, 2),
    }


@celery_app.task(
    bind=True,
    name="detect.run_detect_job",
    soft_time_limit=_SOFT_LIMIT,
    time_limit=_HARD_LIMIT,
)
def run_detect_job(self, job_id: str) -> dict:
    jid = uuid.UUID(str(job_id))
    page_id = None
    try:
        with sync_session() as session:
            job = session.get(Job, jid)
            page_id = job.page_id if job is not None else None
        return _run_detect(jid)
    except SoftTimeLimitExceeded:
        reason = f"timeout: vượt {_SOFT_LIMIT}s"
        logger.error("detect job %s %s", jid, reason)
        _mark_failed(jid, page_id, reason)
        return {"status": "failed", "job_id": str(jid), "error": reason}
    except Exception as exc:  # noqa: BLE001 - ghi lại mọi lỗi, không nuốt im lặng
        reason = f"{type(exc).__name__}: {exc}"
        logger.exception("detect job %s thất bại", jid)
        _mark_failed(jid, page_id, reason)
        return {"status": "failed", "job_id": str(jid), "error": reason}
