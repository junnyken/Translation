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
from app.models import Job, OCRResult, Page, Project, TextRegion
from app.models.enums import (
    JobStatus,
    JobType,
    OCRStatus,
    PageStatus,
    RegionStatus,
    assert_transition,
)
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()


class OCREngineFailedForEveryRegion(RuntimeError):
    """Engine hỏng chứ không phải trang không có chữ — phải báo failed, không giả vờ done."""

_SOFT_LIMIT = settings.detect_timeout_seconds
_HARD_LIMIT = settings.detect_timeout_seconds + 15
_OCR_SOFT_LIMIT = settings.ocr_timeout_seconds
_OCR_HARD_LIMIT = settings.ocr_timeout_seconds + 30

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


#: Engine OCR nạp 1 lần/process, cache theo (source_lang, device).
_ocr_engines: dict[tuple[str, str], object] = {}


def get_ocr_engine_cached(source_lang: str):
    """Trả engine OCR đã nạp sẵn cho source_lang (import trễ: API không nạp thư viện OCR)."""
    key = (source_lang, settings.ocr_device)
    if key not in _ocr_engines:
        from app.services.ocr.engines import get_ocr_engine

        _ocr_engines[key] = get_ocr_engine(
            source_lang,
            device=settings.ocr_device,
            paddle_enable_mkldnn=settings.ocr_paddle_enable_mkldnn,
        )
    return _ocr_engines[key]


def reset_ocr_engines() -> None:
    """Dùng trong test để cắm engine giả lập."""
    _ocr_engines.clear()


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

    ocr_job_id = enqueue_ocr_after_detect(page_id) if settings.ocr_auto_chain else None

    return {
        "status": "done",
        "job_id": str(job_id),
        "page_id": str(page_id),
        "regions": len(regions),
        "low_confidence": low_conf,
        "overlap_suspect": sum(flags),
        "replaced_regions": deleted,
        "elapsed_seconds": round(elapsed, 2),
        "ocr_job_id": str(ocr_job_id) if ocr_job_id else None,
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


# ============================ M3: OCR ============================


def enqueue_ocr_after_detect(page_id: uuid.UUID) -> uuid.UUID | None:
    """Nối chuỗi: detect xong → tự xếp việc OCR cho page (pipeline tự chảy).

    Không để lỗi enqueue làm hỏng kết quả detect đã ghi — ghi rõ error_log rồi đi tiếp.
    """
    with sync_session() as session:
        job = Job(type=JobType.ocr, page_id=page_id, status=JobStatus.queued)
        session.add(job)
        session.commit()
        job_id = job.id

    try:
        run_ocr_job.delay(str(job_id))
    except Exception as exc:  # noqa: BLE001
        reason = f"enqueue_failed: {type(exc).__name__}: {exc}"
        logger.error("Không đẩy được job ocr %s: %s", job_id, reason)
        with sync_session() as session:
            job = session.get(Job, job_id)
            if job is not None:
                job.error_log = reason
                session.commit()
    return job_id


def _classify_ocr(text: str, confidence: float | None) -> OCRStatus:
    """Quy tắc chốt trạng thái 1 kết quả OCR.

    - Text rỗng / không có ký tự có nghĩa → needs_manual (áp cho MỌI engine).
    - Có confidence thật (PaddleOCR) và dưới ngưỡng → needs_manual.
    - confidence=None (manga-ocr không trả confidence) KHÔNG bị coi là thất bại.
    """
    from app.services.ocr.engines import has_meaningful_text

    if not has_meaningful_text(text):
        return OCRStatus.needs_manual
    if confidence is not None and confidence < settings.ocr_conf_threshold:
        return OCRStatus.needs_manual
    return OCRStatus.ok


def _run_ocr(job_id: uuid.UUID) -> dict:
    started = time.perf_counter()
    with sync_session() as session:
        job = session.get(Job, job_id)
        if job is None:
            logger.warning("Job %s không tồn tại", job_id)
            return {"status": "job_not_found", "job_id": str(job_id)}
        if job.type is not JobType.ocr:
            return {"status": "wrong_job_type", "job_id": str(job_id), "type": job.type.value}

        page = session.get(Page, job.page_id)
        if page is None:
            job.status = JobStatus.failed
            job.error_log = "page_not_found"
            session.commit()
            return {"status": "page_not_found", "job_id": str(job_id)}

        project = session.get(Project, page.project_id)
        page_id = page.id
        source_lang = project.source_lang.value
        image_path = resolve_image_path(page.image_path)

        # Lấy TẤT CẢ region, kể cả low_confidence: detect yếu không đồng nghĩa OCR sẽ hỏng.
        regions = list(
            session.execute(
                select(TextRegion).where(TextRegion.page_id == page_id).order_by(TextRegion.created_at)
            ).scalars()
        )
        region_specs = [
            (r.id, r.bbox_x, r.bbox_y, r.bbox_w, r.bbox_h, r.status is RegionStatus.low_confidence)
            for r in regions
        ]

        job.status = JobStatus.running
        session.commit()

    if not region_specs:
        with sync_session() as session:
            job = session.get(Job, job_id)
            job.status = JobStatus.failed
            job.error_log = "no_region: page chưa có TextRegion nào (chạy detect trước)"
            session.commit()
        return {"status": "failed", "job_id": str(job_id), "error": "no_region"}

    engine = get_ocr_engine_cached(source_lang)
    from app.services.interfaces import BBox

    results = []
    errors: list[str] = []
    for region_id, x, y, w, h, is_low in region_specs:
        try:
            text, confidence = engine.recognize(image_path, BBox(x=x, y=y, w=w, h=h))
        except Exception as exc:  # noqa: BLE001 - 1 vùng hỏng không được giết cả trang
            logger.warning("OCR region %s lỗi: %s", region_id, exc)
            errors.append(f"{type(exc).__name__}: {exc}")
            results.append((region_id, None, None, OCRStatus.needs_manual))
            continue
        results.append((region_id, text, confidence, _classify_ocr(text, confidence)))

    # MỌI region đều ném lỗi => engine hỏng, KHÔNG phải "trang này không có chữ".
    # Báo job failed thay vì ghi 100% needs_manual rồi tự nhận ocr_done (che mất sự cố).
    if errors and len(errors) == len(region_specs):
        raise OCREngineFailedForEveryRegion(
            f"Engine OCR lỗi trên toàn bộ {len(errors)} vùng. Lỗi đầu tiên: {errors[0]}"
        )

    elapsed = time.perf_counter() - started

    with sync_session() as session:
        region_ids = [r[0] for r in results]
        # Idempotent guard: xóa kết quả cũ của đúng các region này trước khi ghi mới.
        deleted = session.execute(
            delete(OCRResult).where(OCRResult.region_id.in_(region_ids))
        ).rowcount
        for region_id, text, confidence, status in results:
            session.add(
                OCRResult(
                    region_id=region_id,
                    raw_text=text,
                    ocr_engine=engine.engine_enum,
                    confidence=confidence,
                    status=status,
                )
            )

        page = session.get(Page, page_id)
        if page.status is not PageStatus.ocr_done:
            assert_transition(page.status, PageStatus.ocr_done)
            page.status = PageStatus.ocr_done

        job = session.get(Job, job_id)
        job.status = JobStatus.done
        job.error_log = None
        session.commit()

    needs_manual = sum(1 for r in results if r[3] is OCRStatus.needs_manual)
    logger.info(
        "ocr job %s: %d region (%d needs_manual), engine=%s, xóa %d kết quả cũ, %.1fs",
        job_id, len(results), needs_manual, engine.engine_enum.value, deleted, elapsed,
    )
    return {
        "status": "done",
        "job_id": str(job_id),
        "page_id": str(page_id),
        "regions": len(results),
        "needs_manual": needs_manual,
        "engine": engine.engine_enum.value,
        "replaced_results": deleted,
        "elapsed_seconds": round(elapsed, 2),
    }


@celery_app.task(
    bind=True,
    name="ocr.run_ocr_job",
    soft_time_limit=_OCR_SOFT_LIMIT,
    time_limit=_OCR_HARD_LIMIT,
)
def run_ocr_job(self, job_id: str) -> dict:
    """OCR toàn bộ region của 1 page trong 1 lần chạy (batch theo Page).

    Lỗi/timeout: Job=failed + error_log, Page GIỮ NGUYÊN `detected` (không nhảy `ocr_done`)
    để còn retry được.
    """
    jid = uuid.UUID(str(job_id))
    try:
        return _run_ocr(jid)
    except SoftTimeLimitExceeded:
        reason = f"timeout: vượt {_OCR_SOFT_LIMIT}s"
        logger.error("ocr job %s %s", jid, reason)
        _mark_job_failed(jid, reason)
        return {"status": "failed", "job_id": str(jid), "error": reason}
    except Exception as exc:  # noqa: BLE001
        reason = f"{type(exc).__name__}: {exc}"
        logger.exception("ocr job %s thất bại", jid)
        _mark_job_failed(jid, reason)
        return {"status": "failed", "job_id": str(jid), "error": reason}


def _mark_job_failed(job_id: uuid.UUID, reason: str) -> None:
    """Ghi job thất bại bằng session mới. KHÔNG đụng Page.status — page giữ trạng thái cũ."""
    with sync_session() as session:
        job = session.get(Job, job_id)
        if job is not None:
            job.status = JobStatus.failed
            job.error_log = reason[:4000]
        session.commit()
