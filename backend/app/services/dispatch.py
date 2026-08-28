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


def dispatch_inpaint_job(job_id: uuid.UUID) -> tuple[bool, str | None]:
    """Trả (đã_gửi, lý_do_lỗi). Cùng nguyên tắc: broker chết thì nói thật, không giả vờ."""
    try:
        from app.workers.tasks import run_inpaint_job

        run_inpaint_job.delay(str(job_id))
        return True, None
    except Exception as exc:  # noqa: BLE001
        reason = f"enqueue_failed: {type(exc).__name__}: {exc}"
        logger.error("Không đẩy được job inpaint %s: %s", job_id, reason)
        return False, reason


def dispatch_translate_job(job_id: uuid.UUID, engine: str | None = None) -> tuple[bool, str | None]:
    """Trả (đã_gửi, lý_do_lỗi). Broker chết thì nói thật, không giả vờ đã gửi."""
    try:
        from app.workers.tasks import run_translate_job

        run_translate_job.delay(str(job_id), engine)
        return True, None
    except Exception as exc:  # noqa: BLE001
        reason = f"enqueue_failed: {type(exc).__name__}: {exc}"
        logger.error("Không đẩy được job translate %s: %s", job_id, reason)
        return False, reason


def dispatch_typeset_job(job_id: uuid.UUID) -> tuple[bool, str | None]:
    """Trả (đã_gửi, lý_do_lỗi). Broker chết thì nói thật, không giả vờ đã gửi."""
    try:
        from app.workers.tasks import run_typeset_job

        run_typeset_job.delay(str(job_id))
        return True, None
    except Exception as exc:  # noqa: BLE001
        reason = f"enqueue_failed: {type(exc).__name__}: {exc}"
        logger.error("Không đẩy được job typeset %s: %s", job_id, reason)
        return False, reason


def dispatch_refit_job(
    job_id: uuid.UUID, region_id: uuid.UUID, font_size: float | None = None
) -> tuple[bool, str | None]:
    """Trả (đã_gửi, lý_do_lỗi). Broker chết thì nói thật, không giả vờ đã gửi."""
    try:
        from app.workers.tasks import run_refit_job

        run_refit_job.delay(str(job_id), str(region_id), font_size)
        return True, None
    except Exception as exc:  # noqa: BLE001
        reason = f"enqueue_failed: {type(exc).__name__}: {exc}"
        logger.error("Không đẩy được job refit %s: %s", job_id, reason)
        return False, reason


def dispatch_region_reocr_job(job_id: uuid.UUID, region_id: uuid.UUID) -> tuple[bool, str | None]:
    try:
        from app.workers.tasks import run_region_reocr_job

        run_region_reocr_job.delay(str(job_id), str(region_id))
        return True, None
    except Exception as exc:  # noqa: BLE001
        reason = f"enqueue_failed: {type(exc).__name__}: {exc}"
        logger.error("Không đẩy được job re-OCR %s: %s", job_id, reason)
        return False, reason


def dispatch_region_retranslate_job(
    job_id: uuid.UUID, region_id: uuid.UUID, engine: str | None = None
) -> tuple[bool, str | None]:
    try:
        from app.workers.tasks import run_region_retranslate_job

        run_region_retranslate_job.delay(str(job_id), str(region_id), engine)
        return True, None
    except Exception as exc:  # noqa: BLE001
        reason = f"enqueue_failed: {type(exc).__name__}: {exc}"
        logger.error("Không đẩy được job dịch lại vùng %s: %s", job_id, reason)
        return False, reason


def dispatch_export_job(job_id: uuid.UUID) -> tuple[bool, str | None]:
    """Trả (đã_gửi, lý_do_lỗi). Broker chết thì nói thật, không giả vờ đã gửi."""
    try:
        from app.workers.tasks import run_export_job

        run_export_job.delay(str(job_id))
        return True, None
    except Exception as exc:  # noqa: BLE001
        reason = f"enqueue_failed: {type(exc).__name__}: {exc}"
        logger.error("Không đẩy được job export %s: %s", job_id, reason)
        return False, reason
