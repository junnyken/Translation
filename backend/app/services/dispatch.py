"""Đẩy job vào hàng đợi từ tầng API.

Import Celery task theo kiểu trễ để tiến trình API không kéo theo onnxruntime/model.
Nếu broker chết: KHÔNG làm hỏng request upload (ảnh đã lưu, Job đã ghi) nhưng phải ghi
rõ lý do vào Job.error_log — job đứng ở queued để retry được, không giả vờ đã gửi.
"""
from __future__ import annotations

import logging
import uuid

logger = logging.getLogger(__name__)


def dispatch_detect_job(job_id: uuid.UUID) -> tuple[bool, str | None]:
    """Trả (đã_gửi, lý_do_lỗi)."""
    try:
        from app.workers.tasks import run_detect_job

        run_detect_job.delay(str(job_id))
        return True, None
    except Exception as exc:  # noqa: BLE001
        reason = f"enqueue_failed: {type(exc).__name__}: {exc}"
        logger.error("Không đẩy được job detect %s: %s", job_id, reason)
        return False, reason


def dispatch_ocr_job(job_id: uuid.UUID) -> tuple[bool, str | None]:
    """Trả (đã_gửi, lý_do_lỗi). Cùng nguyên tắc với detect: broker chết thì nói thật."""
    try:
        from app.workers.tasks import run_ocr_job

        run_ocr_job.delay(str(job_id))
        return True, None
    except Exception as exc:  # noqa: BLE001
        reason = f"enqueue_failed: {type(exc).__name__}: {exc}"
        logger.error("Không đẩy được job ocr %s: %s", job_id, reason)
        return False, reason
