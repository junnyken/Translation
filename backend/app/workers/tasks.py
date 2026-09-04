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
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

from celery.exceptions import SoftTimeLimitExceeded
from PIL import Image
from sqlalchemy import delete, func, select

from app.core.config import get_settings
from app.core.db_sync import sync_session
from app.models import (
    ExportJob,
    Job,
    OCRResult,
    Page,
    Project,
    TextRegion,
    TranslationResult,
    TypesetResult,
)
from app.models.enums import (
    ExportFormat,
    FitStatus,
    JobStatus,
    JobType,
    OCRStatus,
    PageStatus,
    RegionStatus,
    TranslationEngine,
    TranslationStatus,
    assert_transition,
)
from app.services.safearea.service import van_tay_hien_vat
from app.services.storage import get_storage, workspace
from app.services.typeset.paths import preview_relative_path
from app.workers.bo_nho import ep_giai_phong_neu_cang, ghi_moc
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
            cpu_mem_arena=settings.ctd_cpu_mem_arena,
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


@contextmanager
def anh_cuc_bo(rel: str):
    """Vật chất hoá một hiện vật ra đường dẫn cục bộ cho engine bên thứ ba dùng.

    P3c: thay cho `resolve_image_path()` cũ (ghép gốc kho + path tương đối). Các engine
    (comic-text-detector, manga-ocr, PaddleOCR, LaMa) đều nhận **đường dẫn tệp**, nên phải có
    một tệp thật ở đâu đó — nhưng chỗ đó KHÔNG được là lòng kho, nếu không kho buộc phải là hệ
    tệp cục bộ mãi mãi. Chép ra thư mục tạm, dọn ngay khi xong.
    """
    with workspace() as ws:
        yield str(get_storage().fetch_to(rel, ws / PurePosixPath(rel).name))


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
        image_rel = page.image_path

        job.status = JobStatus.running
        if page.status is not PageStatus.detecting:
            assert_transition(page.status, PageStatus.detecting)
            page.status = PageStatus.detecting
        session.commit()

    # Van xả chống OOM: bước này chỉ cần detector, nên nếu bộ nhớ đã căng thì nhả LaMa/OCR ra.
    ep_giai_phong_neu_cang({"detector"}, settings.worker_rss_soft_limit_mb)
    ghi_moc("detect: trước")
    detector = get_detector()
    with anh_cuc_bo(image_rel) as image_path:
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
        kq = _run_detect(jid)
        bao_ket_thuc_buoc(
            _page_cua_job(jid), jid,
            "completed" if kq.get("status") == "done" else "failed",
            kq.get("error"),
        )
        return kq
    except SoftTimeLimitExceeded:
        reason = f"timeout: vượt {_SOFT_LIMIT}s"
        logger.error("detect job %s %s", jid, reason)
        _mark_failed(jid, page_id, reason)
        bao_ket_thuc_buoc(page_id or _page_cua_job(jid), jid, "failed", reason)
        return {"status": "failed", "job_id": str(jid), "error": reason}
    except Exception as exc:  # noqa: BLE001 - ghi lại mọi lỗi, không nuốt im lặng
        reason = f"{type(exc).__name__}: {exc}"
        logger.exception("detect job %s thất bại", jid)
        _mark_failed(jid, page_id, reason)
        bao_ket_thuc_buoc(page_id or _page_cua_job(jid), jid, "failed", reason)
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
        image_rel = page.image_path

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

    ep_giai_phong_neu_cang({"ocr"}, settings.worker_rss_soft_limit_mb)
    ghi_moc("ocr: trước")
    engine = get_ocr_engine_cached(source_lang)
    from app.services.interfaces import BBox

    results = []
    errors: list[str] = []
    # Một lượt vật chất hoá cho CẢ trang: mỗi vùng một lượt tải thì với kho từ xa là
    # 30 lượt tải cùng một ảnh cho một trang 30 vùng.
    with anh_cuc_bo(image_rel) as image_path:
        for region_id, x, y, w, h, is_low in region_specs:
            try:
                # Engine nào cung cấp được đường bao từng dòng thì lấy luôn — đó là bằng chứng
                # hình học duy nhất về hướng chữ, và nó chỉ tồn tại ở ĐÂY: sau bước xoá chữ thì
                # trong bong bóng không còn chữ để đo nữa. Engine không có thì `None`, không bịa.
                co_layout = getattr(engine, "recognize_with_layout", None)
                if co_layout is not None:
                    text, confidence, polys = co_layout(image_path, BBox(x=x, y=y, w=w, h=h))
                else:
                    text, confidence = engine.recognize(image_path, BBox(x=x, y=y, w=w, h=h))
                    polys = None
            except Exception as exc:  # noqa: BLE001 - 1 vùng hỏng không được giết cả trang
                logger.warning("OCR region %s lỗi: %s", region_id, exc)
                errors.append(f"{type(exc).__name__}: {exc}")
                results.append((region_id, None, None, OCRStatus.needs_manual, None))
                continue
            results.append((region_id, text, confidence, _classify_ocr(text, confidence), polys))

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
        for region_id, text, confidence, status, polys in results:
            session.add(
                OCRResult(
                    region_id=region_id,
                    raw_text=text,
                    line_polygons=polys,
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

    inpaint_job_id = enqueue_inpaint_after_ocr(page_id) if settings.inpaint_auto_chain else None

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
        "inpaint_job_id": str(inpaint_job_id) if inpaint_job_id else None,
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
        kq = _run_ocr(jid)
        bao_ket_thuc_buoc(
            _page_cua_job(jid), jid,
            "completed" if kq.get("status") == "done" else "failed",
            kq.get("error"),
        )
        return kq
    except SoftTimeLimitExceeded:
        reason = f"timeout: vượt {_OCR_SOFT_LIMIT}s"
        logger.error("ocr job %s %s", jid, reason)
        _mark_job_failed(jid, reason)
        bao_ket_thuc_buoc(_page_cua_job(jid), jid, "failed", reason)
        return {"status": "failed", "job_id": str(jid), "error": reason}
    except Exception as exc:  # noqa: BLE001
        reason = f"{type(exc).__name__}: {exc}"
        logger.exception("ocr job %s thất bại", jid)
        _mark_job_failed(jid, reason)
        bao_ket_thuc_buoc(_page_cua_job(jid), jid, "failed", reason)
        return {"status": "failed", "job_id": str(jid), "error": reason}


def _page_cua_job(job_id: uuid.UUID) -> uuid.UUID | None:
    with sync_session() as session:
        job = session.get(Job, job_id)
        return job.page_id if job else None


def bao_ket_thuc_buoc(page_id: uuid.UUID | None, job_id: uuid.UUID, outcome: str,
                      mo_ta_loi: str | None = None) -> None:
    """Báo cho bộ điều phối mẻ (M9) biết một bước vừa kết thúc.

    Gọi ở CHỖ DUY NHẤT này thay vì rải logic mẻ vào từng task — task của M2–M6 không cần biết
    gì về mẻ. Trang chạy lẻ (không thuộc mẻ nào) thì hàm này không làm gì.
    """
    if page_id is None or not settings.batch_enabled:
        return
    try:
        from app.services.batch.factory import tao_dieu_phoi

        tao_dieu_phoi(settings).on_page_terminal(page_id, job_id, outcome, mo_ta_loi)
    except Exception:  # noqa: BLE001
        # Mẻ hỏng KHÔNG được kéo theo việc của trang — trang vẫn phải xong.
        logger.exception("không cập nhật được mẻ cho trang %s", page_id)


def tinh_vung_an_toan(page_id: uuid.UUID | None, trigger: str) -> dict | None:
    """Tính vùng đặt chữ an toàn cho cả trang (E14), chạy ngay sau khi xoá chữ xong.

    Cố ý KHÔNG thêm task Celery mới: enum `job_type` chưa từng được thêm giá trị trong suốt
    M1–E13, và có test guardrail chốt đúng danh sách task. Chạy đồng bộ ở cuối bước xoá chữ là
    đủ sớm — bước căn chữ còn ở tận sau bước dịch.

    Tính hỏng thì KHÔNG được kéo theo bước xoá chữ: trang vẫn xong, chỉ là chưa có vùng an toàn,
    và bước căn chữ sẽ lùi về khung chữ nhật của M6.
    """
    if page_id is None or not settings.e14_safe_area_enabled:
        return None
    try:
        from app.services.safearea.config import SafeAreaConfig
        from app.services.safearea.service import SafeAreaService

        dv = SafeAreaService(get_storage(), SafeAreaConfig.from_settings(settings))
        with sync_session() as session:
            dem = dv.compute_page(session, page_id)
            session.commit()
        logger.info("vùng an toàn (%s) trang %s: %s", trigger, page_id, dem)
        return dem
    except Exception:  # noqa: BLE001
        logger.exception("không tính được vùng an toàn cho trang %s", page_id)
        return None


def nhan_biet_huong_chu(page_id: uuid.UUID | None, trigger: str) -> dict | None:
    """Nhận biết hướng chữ cho cả trang (E15), chạy ngay sau khi có vùng an toàn.

    Phải chạy TRƯỚC bước căn chữ vì hướng chữ là đầu vào bố cục. Cũng như E14: chạy đồng bộ
    ở đây thay vì thêm một loại việc mới vào enum — enum `job_type` chưa từng được thêm giá
    trị suốt M1–E14 và có test chốt đúng danh sách task.

    Hỏng thì KHÔNG kéo theo bước trước: trang vẫn xong, chỉ là chưa có nhãn hướng chữ.
    """
    if page_id is None or not settings.e15_orientation_enabled:
        return None
    try:
        from app.services.orientation.analyzer import OrientationConfig
        from app.services.orientation.service import OrientationService

        dv = OrientationService(OrientationConfig(
            angle_tolerance_deg=settings.e15_angle_tolerance_deg,
            min_agreement_ratio=settings.e15_min_agreement_ratio,
            vertical_render_enabled=settings.e15_vertical_render_enabled,
        ))
        with sync_session() as session:
            dem = dv.analyze_page(session, page_id)
            session.commit()
        logger.info("hướng chữ (%s) trang %s: %s", trigger, page_id, dem)
        return dem
    except Exception:  # noqa: BLE001
        logger.exception("không nhận biết được hướng chữ cho trang %s", page_id)
        return None


def cham_chat_luong(page_id: uuid.UUID | None, trigger: str) -> None:
    """Chấm chất lượng từng vùng của trang (E12) sau khi đã căn chữ xong.

    Chạy TRONG worker chứ không trong request HTTP, và chỉ là luật thuần — không gọi mô hình,
    không gọi mạng, nên không tốn token và không làm chậm pipeline.

    Chấm hỏng thì KHÔNG được kéo theo việc căn chữ: trang vẫn giữ nguyên kết quả, chỉ là chưa
    có đánh giá. Bảng tổng hợp sẽ nói "chưa đánh giá" thay vì báo 0 cảnh báo.
    """
    if page_id is None:
        return
    try:
        from app.services.quality.gate import QualityGateService

        QualityGateService().assess_page(page_id, trigger=trigger)
    except Exception:  # noqa: BLE001
        logger.exception("không chấm được chất lượng cho trang %s", page_id)


def _mark_job_failed(job_id: uuid.UUID, reason: str) -> None:
    """Ghi job thất bại bằng session mới. KHÔNG đụng Page.status — page giữ trạng thái cũ."""
    with sync_session() as session:
        job = session.get(Job, job_id)
        if job is not None:
            job.status = JobStatus.failed
            job.error_log = reason[:4000]
        session.commit()


# ============================ M4: Inpaint (xoá chữ gốc) ============================


class InpaintPreconditionFailed(RuntimeError):
    """Page chưa đủ điều kiện để inpaint — báo rõ thay vì xoá chữ trên dữ liệu dở dang."""


#: Inpainter nạp 1 lần/process (weight ~197MB).
_inpainter = None


def get_inpainter():
    """Import trễ để tiến trình API không bao giờ nạp onnxruntime/model inpaint."""
    global _inpainter
    if _inpainter is None:
        from app.services.inpaint.lama import LamaInpainter

        _inpainter = LamaInpainter(
            weights_path=settings.inpaint_weights_path,
            device=settings.inpaint_device,
            dilate_ratio=settings.inpaint_dilate_ratio,
            intra_op_threads=settings.inpaint_intra_op_threads,
            cpu_mem_arena=settings.inpaint_cpu_mem_arena,
            whole_page_max_mpx=settings.inpaint_whole_page_max_mpx,
            tile_margin=settings.inpaint_tile_margin,
        )
    return _inpainter


def reset_inpainter() -> None:
    """Dùng trong test để cắm inpainter giả lập."""
    global _inpainter
    _inpainter = None


def enqueue_inpaint_after_ocr(page_id: uuid.UUID) -> uuid.UUID | None:
    """Nối chuỗi: OCR xong → tự xếp việc xoá chữ gốc (pipeline tự chảy)."""
    with sync_session() as session:
        job = Job(type=JobType.inpaint, page_id=page_id, status=JobStatus.queued)
        session.add(job)
        session.commit()
        job_id = job.id

    try:
        run_inpaint_job.delay(str(job_id))
    except Exception as exc:  # noqa: BLE001
        reason = f"enqueue_failed: {type(exc).__name__}: {exc}"
        logger.error("Không đẩy được job inpaint %s: %s", job_id, reason)
        with sync_session() as session:
            job = session.get(Job, job_id)
            if job is not None:
                job.error_log = reason
                session.commit()
    return job_id


def _advance_page(page: Page, target: PageStatus) -> None:
    """Đổi trạng thái page qua đúng state machine của M1 (chạy lại cùng trạng thái = no-op)."""
    if page.status is target:
        return
    assert_transition(page.status, target)
    page.status = target


def _verify_text_removed(clean_abs_path: str, dilated: list, source_lang: str) -> list[str]:
    """Kiểm chứng KHÁCH QUAN: OCR lại đúng vùng vừa xoá trên ảnh clean.

    Trả danh sách text còn đọc được. Rỗng = xoá sạch. Không dựa vào cảm nhận "nhìn thấy artifact".
    """
    from app.services.ocr.engines import has_meaningful_text

    engine = get_ocr_engine_cached(source_lang)
    leftovers: list[str] = []
    for bbox in dilated:
        try:
            text, _confidence = engine.recognize(clean_abs_path, bbox)
        except Exception as exc:  # noqa: BLE001 - lỗi kiểm chứng không được giết job inpaint
            logger.warning("Kiểm chứng OCR trên vùng %s lỗi: %s", bbox, exc)
            continue
        if has_meaningful_text(text):
            leftovers.append(text.strip())
    return leftovers


def _run_inpaint(job_id: uuid.UUID) -> dict:
    started = time.perf_counter()
    from app.services.interfaces import BBox

    with sync_session() as session:
        job = session.get(Job, job_id)
        if job is None:
            logger.warning("Job %s không tồn tại", job_id)
            return {"status": "job_not_found", "job_id": str(job_id)}
        if job.type is not JobType.inpaint:
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
        image_rel = page.image_path
        old_clean_rel = page.clean_image_path

        if page.status not in (PageStatus.ocr_done, PageStatus.inpainted, PageStatus.inpaint_needs_review):
            job.status = JobStatus.failed
            job.error_log = (
                f"precondition_failed: page đang ở '{page.status.value}', "
                "cần 'ocr_done' (chạy OCR trước khi xoá chữ)"
            )
            session.commit()
            return {"status": "failed", "job_id": str(job_id), "error": job.error_log}

        regions = list(
            session.execute(
                select(TextRegion).where(TextRegion.page_id == page_id).order_by(TextRegion.created_at)
            ).scalars()
        )
        if not regions:
            job.status = JobStatus.failed
            job.error_log = "no_region: page chưa có TextRegion nào (chạy detect trước)"
            session.commit()
            return {"status": "failed", "job_id": str(job_id), "error": "no_region"}

        ocr_count = session.scalar(
            select(func.count(OCRResult.id)).where(
                OCRResult.region_id.in_([r.id for r in regions])
            )
        )
        if not ocr_count or ocr_count < len(regions):
            job.status = JobStatus.failed
            job.error_log = (
                f"missing_ocr: {ocr_count or 0}/{len(regions)} vùng có kết quả OCR — "
                "không xoá chữ khi chưa đọc xong (chạy lại OCR trước)"
            )
            session.commit()
            return {"status": "failed", "job_id": str(job_id), "error": job.error_log}

        boxes = [BBox(x=r.bbox_x, y=r.bbox_y, w=r.bbox_w, h=r.bbox_h) for r in regions]
        job.status = JobStatus.running
        session.commit()

    storage = get_storage()

    # Idempotent guard: xoá ảnh clean cũ trước khi ghi mới, không để file rác.
    deleted_old = False
    if old_clean_rel:
        deleted_old = storage.delete(old_clean_rel)

    # Bước nặng nhất. Giữ lại OCR vì `inpaint_verify_by_ocr` cần nó ngay sau đó — nhả rồi nạp
    # lại trong cùng một job là tự chuốc lấy cái giá vô ích.
    ep_giai_phong_neu_cang({"inpainter", "ocr"}, settings.worker_rss_soft_limit_mb)
    ghi_moc("inpaint: trước")
    inpainter = get_inpainter()
    leftovers: list[str] = []
    # LaMa đọc ảnh gốc rồi tự ghi ảnh clean CẠNH nó — nên cho nó làm việc đó trong thư mục tạm,
    # xong mới đưa kết quả vào kho. Path tương đối của ảnh clean vẫn suy ra từ ảnh gốc nên
    # KHÔNG đổi so với trước P3c (`projects/<pid>/pages/<page_id>_clean.png`) — không cần migrate
    # dữ liệu cũ.
    with workspace() as ws:
        image_abs = str(storage.fetch_to(image_rel, ws / PurePosixPath(image_rel).name))
        clean_abs = inpainter.inpaint(image_abs, boxes)
        clean_rel = str(PurePosixPath(image_rel).parent / PurePosixPath(clean_abs).name)
        storage.save_file(clean_rel, Path(clean_abs))

        if settings.inpaint_verify_by_ocr:
            with Image.open(image_abs) as im:
                width, height = im.size
            dilated = inpainter.dilated_masks(width, height, boxes)
            leftovers = _verify_text_removed(clean_abs, dilated, source_lang)

    ghi_moc("inpaint: sau")
    elapsed = time.perf_counter() - started
    target_status = PageStatus.inpaint_needs_review if leftovers else PageStatus.inpainted

    with sync_session() as session:
        page = session.get(Page, page_id)
        page.clean_image_path = clean_rel
        _advance_page(page, target_status)

        job = session.get(Job, job_id)
        job.status = JobStatus.done
        job.error_log = None
        session.commit()

    # Vùng an toàn phải có TRƯỚC bước căn chữ, vì nó là đầu vào bố cục của bước đó.
    tinh_vung_an_toan(page_id, "inpaint")
    # Hướng chữ cũng vậy, và nó cần đường bao dòng của OCR (đã có từ bước trước) cộng với
    # vùng an toàn vừa tính xong.
    nhan_biet_huong_chu(page_id, "inpaint")

    translate_job_id = (
        enqueue_translate_after_inpaint(page_id) if settings.translate_auto_chain else None
    )

    logger.info(
        "inpaint job %s: %d vùng, %s, còn chữ ở %d vùng, xoá ảnh clean cũ=%s, %.1fs",
        job_id, len(boxes), target_status.value, len(leftovers), deleted_old, elapsed,
    )
    return {
        "status": "done",
        "job_id": str(job_id),
        "page_id": str(page_id),
        "regions": len(boxes),
        "clean_image_path": clean_rel,
        "page_status": target_status.value,
        "regions_with_text_left": len(leftovers),
        "replaced_old_clean_image": deleted_old,
        "elapsed_seconds": round(elapsed, 2),
        "translate_job_id": str(translate_job_id) if translate_job_id else None,
    }


@celery_app.task(
    bind=True,
    name="inpaint.run_inpaint_job",
    soft_time_limit=settings.inpaint_timeout_seconds,
    time_limit=settings.inpaint_timeout_seconds + 30,
)
def run_inpaint_job(self, job_id: str) -> dict:
    """Xoá chữ gốc khỏi ảnh, sinh ảnh clean MỚI (không đụng ảnh gốc).

    Lỗi/timeout: Job=failed + error_log, Page GIỮ NGUYÊN trạng thái cũ (không nhảy `inpainted`).
    """
    jid = uuid.UUID(str(job_id))
    try:
        kq = _run_inpaint(jid)
        bao_ket_thuc_buoc(
            _page_cua_job(jid), jid,
            "completed" if kq.get("status") == "done" else "failed",
            kq.get("error"),
        )
        return kq
    except SoftTimeLimitExceeded:
        reason = f"timeout: vượt {settings.inpaint_timeout_seconds}s"
        logger.error("inpaint job %s %s", jid, reason)
        _mark_job_failed(jid, reason)
        bao_ket_thuc_buoc(_page_cua_job(jid), jid, "failed", reason)
        return {"status": "failed", "job_id": str(jid), "error": reason}
    except Exception as exc:  # noqa: BLE001
        reason = f"{type(exc).__name__}: {exc}"
        logger.exception("inpaint job %s thất bại", jid)
        _mark_job_failed(jid, reason)
        bao_ket_thuc_buoc(_page_cua_job(jid), jid, "failed", reason)
        return {"status": "failed", "job_id": str(jid), "error": reason}


# ============================ M5: Dịch ============================


def enqueue_translate_after_inpaint(page_id: uuid.UUID) -> uuid.UUID | None:
    """Nối chuỗi: xoá chữ xong → tự xếp việc dịch."""
    with sync_session() as session:
        job = Job(type=JobType.translate, page_id=page_id, status=JobStatus.queued)
        session.add(job)
        session.commit()
        job_id = job.id

    try:
        run_translate_job.delay(str(job_id))
    except Exception as exc:  # noqa: BLE001
        reason = f"enqueue_failed: {type(exc).__name__}: {exc}"
        logger.error("Không đẩy được job translate %s: %s", job_id, reason)
        with sync_session() as session:
            job = session.get(Job, job_id)
            if job is not None:
                job.error_log = reason
                session.commit()
    return job_id


def build_translator(engine: str):
    """Tạo translator theo tên engine. Import trễ; key chỉ đọc từ settings (.env)."""
    from app.services.translate.engines import get_translator

    if engine == TranslationEngine.llm_context.value:
        return get_translator(
            engine,
            api_keys=settings.gemini_api_key_list,
            model_name=settings.llm_model_name,
            timeout=settings.translate_timeout_seconds,
            temperature=settings.llm_temperature,
            max_output_tokens=settings.llm_max_output_tokens,
            thinking_budget=settings.llm_thinking_budget,
        )
    return get_translator(engine)


def _cong_nhip(engine_name: str) -> None:
    """Giữ nhịp gọi Gemini theo hạn mức của PROJECT, chung cho mọi worker (M9).

    Không dùng `rate_limit` của Celery vì nó giới hạn theo từng worker instance — hai worker
    cùng đặt 10 lượt/phút thành 20 lượt/phút đập vào nhà cung cấp.
    Bị chặn thì ném lỗi 429 và **không gọi provider** — đó là toàn bộ mục đích của cổng.
    """
    if engine_name != TranslationEngine.llm_context.value or settings.llm_project_rpm <= 0:
        return
    from app.services.batch.gate import GeminiProjectRateGate
    from app.services.translate.engines import TranslationFailed

    cong = GeminiProjectRateGate(settings.redis_url, rpm=settings.llm_project_rpm)
    ket = cong.acquire(cong.khoa_project(settings.llm_model_name, "gemini"))
    if not ket.cho_phep:
        raise TranslationFailed(
            f"HTTP 429: rate limit — cổng nhịp chặn ({ket.ly_do}), "
            f"còn {ket.con_lai} lượt, thử lại sau ~{ket.cho_giay:.0f}s"
        )


def _run_translate(job_id: uuid.UUID, engine_override: str | None = None) -> dict:
    started = time.perf_counter()
    from app.services.translate.engines import QuotaExhausted, TranslationFailed
    from app.services.translate.reading_order import calculate_reading_order

    with sync_session() as session:
        job = session.get(Job, job_id)
        if job is None:
            logger.warning("Job %s không tồn tại", job_id)
            return {"status": "job_not_found", "job_id": str(job_id)}
        if job.type is not JobType.translate:
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
        target_lang = project.target_lang.value

        if page.status not in (
            PageStatus.inpainted,
            PageStatus.inpaint_needs_review,
            PageStatus.translated,
            PageStatus.typeset_done,  # dịch lại trang ĐÃ canh chữ (M6 auto-chain đưa mọi trang tới đây)
        ):
            job.status = JobStatus.failed
            job.error_log = (
                f"precondition_failed: page đang ở '{page.status.value}', "
                "cần 'inpainted' (chạy xoá chữ trước khi dịch)"
            )
            session.commit()
            return {"status": "failed", "job_id": str(job_id), "error": job.error_log}

        regions = list(
            session.execute(
                select(TextRegion).where(TextRegion.page_id == page_id).order_by(TextRegion.created_at)
            ).scalars()
        )
        if not regions:
            job.status = JobStatus.failed
            job.error_log = "no_region: page chưa có TextRegion nào"
            session.commit()
            return {"status": "failed", "job_id": str(job_id), "error": "no_region"}

        ocr_map = {
            row.region_id: row
            for row in session.execute(
                select(OCRResult).where(OCRResult.region_id.in_([r.id for r in regions]))
            ).scalars()
        }
        if len(ocr_map) < len(regions):
            job.status = JobStatus.failed
            job.error_log = (
                f"missing_ocr: {len(ocr_map)}/{len(regions)} vùng có kết quả OCR — "
                "không dịch khi chưa đọc xong chữ"
            )
            session.commit()
            return {"status": "failed", "job_id": str(job_id), "error": job.error_log}

        # Thứ tự đọc: tính TRƯỚC khi gửi dịch, và ghi luôn vào TextRegion.reading_order
        # (cột này để NULL từ M1, M5 là bước chịu trách nhiệm điền).
        ordered = calculate_reading_order(
            regions, source_lang, settings.reading_direction_override or None
        )
        for position, region in enumerate(ordered, start=1):
            region.reading_order = position

        ordered_specs = [
            (r.id, (ocr_map[r.id].raw_text or ""), position)
            for position, r in enumerate(ordered, start=1)
        ]
        job.status = JobStatus.running
        session.commit()

    engine_name = engine_override or settings.translate_default_engine
    texts = [text for _rid, text, _pos in ordered_specs]

    used_engine = engine_name
    fallback_reason: str | None = None
    translator = build_translator(engine_name)
    try:
        # Cổng nhịp chỉ áp cho đường TỐN TIỀN (`google_fast` miễn phí nên không qua cổng).
        # Đặt TRONG khối try có chủ đích: bị chặn thì đi đúng đường lùi-về-google của M5 và
        # được dán nhãn `fallback_used`, thay vì làm hỏng cả job. Đặt ngoài try là mất đường lùi.
        _cong_nhip(engine_name)
        translated = translator.translate(texts, source_lang, target_lang)
    except (QuotaExhausted, TranslationFailed) as exc:
        if engine_name != TranslationEngine.llm_context.value or not settings.llm_fallback_to_google:
            raise
        # Không âm thầm trả bản rỗng: lùi về google_fast và ĐÁNH DẤU fallback_used.
        fallback_reason = f"{type(exc).__name__}: {exc}"
        logger.warning("LLM lỗi (%s) -> lùi về google_fast", fallback_reason[:200])
        used_engine = TranslationEngine.google_fast.value
        translator = build_translator(used_engine)
        translated = translator.translate(texts, source_lang, target_lang)

    usage = getattr(translator, "usage", None)
    elapsed = time.perf_counter() - started

    with sync_session() as session:
        region_ids = [rid for rid, _t, _p in ordered_specs]
        deleted = session.execute(
            delete(TranslationResult).where(TranslationResult.region_id.in_(region_ids))
        ).rowcount

        empty = 0
        for index, ((region_id, _src, _pos), text) in enumerate(zip(ordered_specs, translated, strict=False)):
            is_empty = not (text or "").strip()
            empty += int(is_empty)
            session.add(
                TranslationResult(
                    region_id=region_id,
                    translated_text=text or None,
                    engine=TranslationEngine(used_engine),
                    model_name=getattr(translator, "model_name", None),
                    # Chi phí token là của CẢ TRANG (1 request) -> ghi vào đúng 1 dòng đầu
                    # để cộng token_cost toàn bảng vẫn ra tổng thật, không nhân bản.
                    token_cost=(usage.total_tokens if usage and index == 0 else None),
                    status=(
                        TranslationStatus.pending
                        if is_empty
                        else (
                            TranslationStatus.fallback_used
                            if fallback_reason
                            else TranslationStatus.ok
                        )
                    ),
                )
            )

        page = session.get(Page, page_id)
        if page.status is not PageStatus.translated:
            assert_transition(page.status, PageStatus.translated)
            page.status = PageStatus.translated

        job = session.get(Job, job_id)
        job.status = JobStatus.done
        job.error_log = f"fallback_used: {fallback_reason}"[:4000] if fallback_reason else None
        session.commit()

    typeset_job_id = (
        enqueue_typeset_after_translate(page_id) if settings.typeset_auto_chain else None
    )

    logger.info(
        "translate job %s: %d vùng (%d dòng rỗng), engine=%s%s, token=%s, xoá %d bản dịch cũ, %.1fs",
        job_id, len(ordered_specs), empty, used_engine,
        " (fallback)" if fallback_reason else "",
        usage.total_tokens if usage else None, deleted, elapsed,
    )
    return {
        "status": "done",
        "job_id": str(job_id),
        "page_id": str(page_id),
        "regions": len(ordered_specs),
        "engine": used_engine,
        "fallback": bool(fallback_reason),
        "empty_lines": empty,
        "token_cost": usage.total_tokens if usage else None,
        "thought_tokens": usage.thought_tokens if usage else None,
        "key_rotations": usage.key_rotations if usage else 0,
        "replaced_results": deleted,
        "elapsed_seconds": round(elapsed, 2),
        "typeset_job_id": str(typeset_job_id) if typeset_job_id else None,
    }


@celery_app.task(
    bind=True,
    name="translate.run_translate_job",
    soft_time_limit=settings.translate_timeout_seconds,
    time_limit=settings.translate_timeout_seconds + 30,
)
def run_translate_job(self, job_id: str, engine: str | None = None) -> dict:
    """Dịch toàn bộ vùng chữ của 1 page theo đúng thứ tự đọc.

    Lỗi/timeout: Job=failed + error_log, Page GIỮ `inpainted` để còn chạy lại.
    """
    jid = uuid.UUID(str(job_id))
    try:
        kq = _run_translate(jid, engine)
        bao_ket_thuc_buoc(
            _page_cua_job(jid), jid,
            "completed" if kq.get("status") == "done" else "failed",
            kq.get("error"),
        )
        return kq
    except SoftTimeLimitExceeded:
        reason = f"timeout: vượt {settings.translate_timeout_seconds}s"
        logger.error("translate job %s %s", jid, reason)
        _mark_job_failed(jid, reason)
        bao_ket_thuc_buoc(_page_cua_job(jid), jid, "failed", reason)
        return {"status": "failed", "job_id": str(jid), "error": reason}
    except Exception as exc:  # noqa: BLE001
        reason = f"{type(exc).__name__}: {exc}"
        logger.exception("translate job %s thất bại", jid)
        _mark_job_failed(jid, reason)
        bao_ket_thuc_buoc(_page_cua_job(jid), jid, "failed", reason)
        return {"status": "failed", "job_id": str(jid), "error": reason}


# ============================ M6: Canh chữ vào bubble ============================


def enqueue_typeset_after_translate(page_id: uuid.UUID) -> uuid.UUID | None:
    """Nối chuỗi: dịch xong → tự xếp việc canh chữ."""
    with sync_session() as session:
        job = Job(type=JobType.typeset, page_id=page_id, status=JobStatus.queued)
        session.add(job)
        session.commit()
        job_id = job.id

    try:
        run_typeset_job.delay(str(job_id))
    except Exception as exc:  # noqa: BLE001
        reason = f"enqueue_failed: {type(exc).__name__}: {exc}"
        logger.error("Không đẩy được job typeset %s: %s", job_id, reason)
        with sync_session() as session:
            job = session.get(Job, job_id)
            if job is not None:
                job.error_log = reason
                session.commit()
    return job_id


def build_typesetter(padding_ratio: float | None = None):
    """Dựng typesetter + resolver từ config. Import TRỄ để API không kéo theo Pillow/font.

    `padding_ratio` chỉ được truyền vào ở đường E14, nơi vùng đặt chữ đã thụt vào từ trước.
    """
    from app.services.typeset.fitter import FitToBoxTypesetter
    from app.services.typeset.fonts import FontResolver

    resolver = FontResolver(
        font_dir=settings.font_dir,
        default_family=settings.default_font_family,
        allow_fallback=settings.allow_font_fallback,
    )
    typesetter = FitToBoxTypesetter(
        font_resolver=resolver,
        min_font_size=settings.typeset_min_font_size,
        max_font_size=settings.typeset_max_font_size,
        padding_ratio=(settings.typeset_padding_ratio if padding_ratio is None
                       else float(padding_ratio)),
        line_spacing_ratio=settings.typeset_line_spacing_ratio,
        stroke_width=settings.typeset_stroke_width,
    )
    return typesetter, resolver


def render_page_preview(page_id: uuid.UUID, resolver=None) -> str:
    """Vẽ lại preview CẢ TRANG từ đúng những gì đang có trong DB.

    Dùng chung cho M6 (canh cả trang) và M7 (sửa tay 1 vùng). Cố ý **luôn vẽ cả trang** dù chỉ
    sửa một vùng: vẽ từng phần dễ sinh lỗi hình khi các bubble chồng nhau, và vẽ cả trang mới
    bảo đảm ảnh khớp DB.
    """
    from app.services.interfaces import BBox
    from app.services.typeset.preview import PagePreviewRenderer, RegionDraw

    if resolver is None:
        _typesetter, resolver = build_typesetter()

    with sync_session() as session:
        page = session.get(Page, page_id)
        if page is None or not page.clean_image_path:
            raise RuntimeError(f"no_clean_image: page {page_id} chưa có ảnh clean của M4")
        clean_rel = page.clean_image_path
        rows = list(
            session.execute(
                select(TextRegion, TypesetResult)
                .join(TypesetResult, TypesetResult.region_id == TextRegion.id)
                .where(TextRegion.page_id == page_id)
                .order_by(TextRegion.reading_order.nulls_last(), TextRegion.created_at)
            ).all()
        )
        from app.services.safearea.apply import nap_o_dat_chu
        from app.services.storage import get_storage as _lay_kho

        o_dat = nap_o_dat_chu(
            session, [r.id for r, _ts in rows], van_tay_hien_vat(_lay_kho(), clean_rel)
        )
        ve = [
            RegionDraw(
                bbox=BBox(x=r.bbox_x, y=r.bbox_y, w=r.bbox_w, h=r.bbox_h),
                wrapped_text=ts.wrapped_text or "",
                font_family=ts.font_family or settings.default_font_family,
                font_size=ts.font_size,
                padding_ratio=ts.padding_ratio if ts.padding_ratio is not None else settings.typeset_padding_ratio,
                overflow=ts.fit_status is FitStatus.overflow_warning,
                place_rect=o_dat.get(r.id),
            )
            for r, ts in rows
        ]

    storage = get_storage()
    preview_rel = preview_relative_path(page_id)
    # Bộ vẽ M6 đọc/ghi bằng đường dẫn thật, nên cả ảnh vào lẫn ảnh ra đều đi qua thư mục tạm;
    # ảnh xem thử chỉ vào kho khi đã vẽ XONG (P3c: `save_file` là một lượt đổi chỗ nguyên tử,
    # nên không còn cửa sổ nào người dùng thấy ảnh vẽ dở).
    with workspace() as ws:
        clean_abs = str(storage.fetch_to(clean_rel, ws / PurePosixPath(clean_rel).name))
        dich = ws / "typeset.png"
        PagePreviewRenderer(
            font_resolver=resolver,
            line_spacing_ratio=settings.typeset_line_spacing_ratio,
            text_color=settings.typeset_text_color,
            stroke_color=settings.typeset_stroke_color,
            stroke_width=settings.typeset_stroke_width,
        ).render(
            clean_image_path=clean_abs,
            regions=ve,
            target_path=str(dich),
        )
        storage.save_file(preview_rel, dich)
    return preview_rel


def _run_typeset(job_id: uuid.UUID) -> dict:
    started = time.perf_counter()
    from app.services.interfaces import BBox
    from app.services.typeset.fitter import FONT_MISSING_GLYPH
    from app.services.typeset.fonts import MissingGlyph

    with sync_session() as session:
        job = session.get(Job, job_id)
        if job is None:
            logger.warning("Job %s không tồn tại", job_id)
            return {"status": "job_not_found", "job_id": str(job_id)}
        if job.type is not JobType.typeset:
            return {"status": "wrong_job_type", "job_id": str(job_id), "type": job.type.value}

        page = session.get(Page, job.page_id)
        if page is None:
            job.status = JobStatus.failed
            job.error_log = "page_not_found"
            session.commit()
            return {"status": "page_not_found", "job_id": str(job_id)}

        page_id = page.id
        clean_rel = page.clean_image_path

        if page.status not in (PageStatus.translated, PageStatus.typeset_done):
            job.status = JobStatus.failed
            job.error_log = (
                f"precondition_failed: page đang ở '{page.status.value}', "
                "cần 'translated' (chạy dịch trước khi canh chữ)"
            )
            session.commit()
            return {"status": "failed", "job_id": str(job_id), "error": job.error_log}

        if not clean_rel:
            job.status = JobStatus.failed
            job.error_log = "no_clean_image: page chưa có ảnh clean của M4"
            session.commit()
            return {"status": "failed", "job_id": str(job_id), "error": job.error_log}

        regions = list(
            session.execute(
                select(TextRegion)
                .where(TextRegion.page_id == page_id)
                .order_by(TextRegion.reading_order.nulls_last(), TextRegion.created_at)
            ).scalars()
        )
        if not regions:
            job.status = JobStatus.failed
            job.error_log = "no_region: page chưa có TextRegion nào"
            session.commit()
            return {"status": "failed", "job_id": str(job_id), "error": "no_region"}

        translations = {
            row.region_id: row
            for row in session.execute(
                select(TranslationResult).where(
                    TranslationResult.region_id.in_([r.id for r in regions])
                )
            ).scalars()
        }
        if len(translations) < len(regions):
            # Thiếu bản dịch ⇒ KHÔNG tạo preview nửa vời.
            job.status = JobStatus.failed
            job.error_log = (
                f"missing_translation: {len(translations)}/{len(regions)} vùng có bản dịch — "
                "không canh chữ khi chưa dịch xong"
            )
            session.commit()
            return {"status": "failed", "job_id": str(job_id), "error": job.error_log}

        from app.services.safearea.apply import nap_o_dat_chu
        from app.services.storage import get_storage as _lay_kho

        van_tay_clean = van_tay_hien_vat(_lay_kho(), clean_rel)
        o_dat = nap_o_dat_chu(session, [r.id for r in regions], van_tay_clean)
        # Tự chữa lành: vùng nào chưa có hình dùng được (chưa tính bao giờ, hoặc ảnh clean đã
        # đổi sau lần tính) thì tính lại NGAY tại đây. Nhờ vậy "tính lại vùng an toàn" chỉ là
        # chạy lại bước căn chữ — không phải thêm một loại việc mới vào enum.
        thieu = [r.id for r in regions if r.id not in o_dat]
        if thieu and settings.e14_safe_area_enabled:
            try:
                from app.services.safearea.config import SafeAreaConfig
                from app.services.safearea.service import SafeAreaService

                dv = SafeAreaService(get_storage(), SafeAreaConfig.from_settings(settings))
                for rid in thieu:
                    dv.compute_region(session, rid)
                session.commit()
                o_dat = nap_o_dat_chu(session, [r.id for r in regions], van_tay_clean)
            except Exception:  # noqa: BLE001
                logger.exception("không tính lại được vùng an toàn cho trang %s", page_id)
        specs = [
            (
                r.id,
                BBox(x=r.bbox_x, y=r.bbox_y, w=r.bbox_w, h=r.bbox_h),
                translations[r.id].translated_text or "",
                o_dat.get(r.id),
            )
            for r in regions
        ]
        job.status = JobStatus.running
        session.commit()

    # ---- tính toán NGOÀI transaction: nạp font + đo chữ là việc nặng ----
    typesetter, resolver = build_typesetter()
    # Vùng an toàn của E14 ĐÃ thụt vào sẵn (bước ăn mòn), nên canh chữ trong đó phải dùng
    # padding = 0. Trừ lề hai lần thì chữ tự nhiên bé lại mà không ai giải thích được vì sao.
    typesetter_an_toan = build_typesetter(padding_ratio=0.0)[0]
    font_family = settings.default_font_family
    ket_qua: list[tuple[uuid.UUID, BBox, dict]] = []
    #: Vùng font không vẽ được — giữ lại để báo cáo, KHÔNG nuốt im lặng.
    thieu_glyph: list[tuple[uuid.UUID, str]] = []
    for region_id, bbox, text, o in specs:
        if o is None:
            khung, ts = bbox, typesetter
        else:
            khung, ts = BBox(x=o[0], y=o[1], w=o[2], h=o[3]), typesetter_an_toan
        try:
            ket_qua.append((region_id, bbox, ts.fit(text, khung, font_family)))
        except MissingGlyph as exc:
            # MỘT vùng font không vẽ được KHÔNG được giết cả trang.
            #
            # Đo thật 04/09: một dấu `．` trong 8 vùng làm hỏng nguyên trang — 7 vùng còn lại
            # dịch đúng, căn được, nhưng người dùng không nhận được gì cả và ngồi đợi một việc
            # đã chết sau 34 mili-giây. Bản sửa dấu câu (`_DAU_CAU_TOAN_RONG`) chặn đúng nguyên
            # nhân hay gặp nhất, nhưng chữ Nhật còn sót thì font thiếu glyph là thiếu THẬT.
            #
            # Vùng hỏng được ghi trạng thái riêng `font_missing_glyph` (không phải `pending`)
            # để nó đếm được, hiện được, và chặn ở cổng xuất file.
            thieu_glyph.append((region_id, str(exc)))
            ket_qua.append(
                (region_id, bbox,
                 {"font_size": None, "wrapped_text": None, "fit_status": FONT_MISSING_GLYPH}),
            )

    # Cả trang không vùng nào căn được thì đừng công bố một trang trắng và gọi đó là "đã căn
    # chữ": để job hỏng như cũ, trang giữ nguyên `translated`, không đụng vào preview.
    if thieu_glyph and len(thieu_glyph) == len(specs):
        raise MissingGlyph(
            f"toàn bộ {len(specs)} vùng của trang không chèn được chữ — {thieu_glyph[0][1]}"
        )

    with sync_session() as session:
        region_ids = [rid for rid, _b, _f in ket_qua]
        deleted = session.execute(
            delete(TypesetResult).where(TypesetResult.region_id.in_(region_ids))
        ).rowcount
        dem = {"fit_ok": 0, "overflow_warning": 0, "pending": 0, "font_missing_glyph": 0}
        for region_id, _bbox, fit in ket_qua:
            dem[fit["fit_status"]] = dem.get(fit["fit_status"], 0) + 1
            session.add(
                TypesetResult(
                    region_id=region_id,
                    font_family=font_family,
                    font_size=fit["font_size"],
                    wrapped_text=fit["wrapped_text"] or None,
                    padding_ratio=settings.typeset_padding_ratio,
                    fit_status=FitStatus(fit["fit_status"]),
                    edited_by_user=False,
                )
            )
        session.commit()

    # Vẽ preview từ ĐÚNG những gì vừa ghi xuống DB — cùng một hàm mà M7 dùng lại khi
    # sửa tay 1 vùng, nên preview luôn phản ánh trạng thái DB, không có 2 đường vẽ khác nhau.
    preview_rel = render_page_preview(page_id, resolver)
    elapsed = time.perf_counter() - started

    with sync_session() as session:
        page = session.get(Page, page_id)
        if page.status is not PageStatus.typeset_done:
            assert_transition(page.status, PageStatus.typeset_done)
            page.status = PageStatus.typeset_done

        job = session.get(Job, job_id)
        job.status = JobStatus.done
        job.error_log = None
        session.commit()

    cham_chat_luong(page_id, "typeset")

    if thieu_glyph:
        # Cảnh báo, KHÔNG phải thông tin phụ: trang được công bố là "đã căn chữ" trong khi có
        # bong bóng bị bỏ trống, nên chỗ này phải để lại dấu vết đọc được trong log.
        logger.warning(
            "typeset job %s: %d/%d vùng KHÔNG chèn được chữ vì font thiếu glyph — %s",
            job_id, len(thieu_glyph), len(ket_qua), thieu_glyph[0][1],
        )
    logger.info(
        "typeset job %s: %d vùng (vừa %d, tràn %d, chưa có chữ %d, thiếu glyph %d), font=%s, "
        "xoá %d kết quả cũ, preview=%s, %.1fs",
        job_id, len(ket_qua), dem["fit_ok"], dem["overflow_warning"], dem["pending"],
        dem["font_missing_glyph"], font_family, deleted, preview_rel, elapsed,
    )
    return {
        "status": "done",
        "job_id": str(job_id),
        "page_id": str(page_id),
        "regions": len(ket_qua),
        "fit_ok": dem["fit_ok"],
        "overflow_warning": dem["overflow_warning"],
        "pending": dem["pending"],
        "font_missing_glyph": dem["font_missing_glyph"],
        # Lý do của vùng ĐẦU TIÊN hỏng — đủ để biết thiếu ký tự gì mà không đổ cả trang log
        # vào một trường. Chi tiết từng vùng nằm ở `fit_status` trong DB.
        "font_missing_reason": thieu_glyph[0][1] if thieu_glyph else None,
        "font_family": font_family,
        "preview_path": preview_rel,
        "replaced_results": deleted,
        "elapsed_seconds": round(elapsed, 2),
    }


@celery_app.task(
    bind=True,
    name="typeset.run_typeset_job",
    soft_time_limit=settings.typeset_timeout_seconds,
    time_limit=settings.typeset_timeout_seconds + 30,
)
def run_typeset_job(self, job_id: str) -> dict:
    """Canh cỡ chữ + ngắt dòng cho mọi vùng của 1 page, rồi render ảnh preview riêng.

    Lỗi/timeout/thiếu font: Job=failed + error_log, Page GIỮ `translated`, KHÔNG công bố
    preview dở dang (ảnh chỉ được đổi chỗ nguyên tử sau khi vẽ xong).
    """
    jid = uuid.UUID(str(job_id))
    try:
        kq = _run_typeset(jid)
        bao_ket_thuc_buoc(
            _page_cua_job(jid), jid,
            "completed" if kq.get("status") == "done" else "failed",
            kq.get("error"),
        )
        return kq
    except SoftTimeLimitExceeded:
        reason = f"timeout: vượt {settings.typeset_timeout_seconds}s"
        logger.error("typeset job %s %s", jid, reason)
        _mark_job_failed(jid, reason)
        bao_ket_thuc_buoc(_page_cua_job(jid), jid, "failed", reason)
        return {"status": "failed", "job_id": str(jid), "error": reason}
    except Exception as exc:  # noqa: BLE001
        reason = f"{type(exc).__name__}: {exc}"
        logger.exception("typeset job %s thất bại", jid)
        _mark_job_failed(jid, reason)
        bao_ket_thuc_buoc(_page_cua_job(jid), jid, "failed", reason)
        return {"status": "failed", "job_id": str(jid), "error": reason}


# ============================ M7: Sửa tay theo từng vùng ============================


def _job_for_region(region_id: uuid.UUID, job_type: JobType) -> tuple[uuid.UUID, uuid.UUID] | None:
    """Tạo Job gắn với page của region. Trả (job_id, page_id), None nếu region không tồn tại."""
    with sync_session() as session:
        region = session.get(TextRegion, region_id)
        if region is None:
            return None
        job = Job(type=job_type, page_id=region.page_id, status=JobStatus.queued)
        session.add(job)
        session.commit()
        return job.id, region.page_id


def _region_context(session, region_id: uuid.UUID):
    """Gom region + page + project trong 1 lần đọc. None nếu thiếu mắt xích nào."""
    region = session.get(TextRegion, region_id)
    if region is None:
        return None
    page = session.get(Page, region.page_id)
    if page is None:
        return None
    return region, page, session.get(Project, page.project_id)


def _run_refit(job_id: uuid.UUID, region_id: uuid.UUID, font_size_override: float | None = None) -> dict:
    """Canh lại chữ cho ĐÚNG MỘT vùng, rồi vẽ lại preview cả trang.

    `font_size_override`: người dùng ghim cỡ chữ cụ thể (đổi font/size thủ công). Có ghim thì
    KHÔNG dò cỡ nữa — dùng đúng cỡ đó rồi báo thật là vừa hay tràn.
    """
    started = time.perf_counter()
    from app.services.interfaces import BBox

    with sync_session() as session:
        job = session.get(Job, job_id)
        if job is None:
            logger.warning("Job %s không tồn tại", job_id)
            return {"status": "job_not_found", "job_id": str(job_id)}
        if job.type is not JobType.typeset:
            return {"status": "wrong_job_type", "job_id": str(job_id), "type": job.type.value}

        ctx = _region_context(session, region_id)
        if ctx is None:
            job.status = JobStatus.failed
            job.error_log = f"region_not_found: {region_id}"
            session.commit()
            return {"status": "failed", "job_id": str(job_id), "error": job.error_log}
        region, page, _project = ctx

        translation = session.execute(
            select(TranslationResult).where(TranslationResult.region_id == region_id)
        ).scalars().first()
        if translation is None:
            # Không canh chữ cho vùng chưa từng được dịch — không bịa nội dung.
            job.status = JobStatus.failed
            job.error_log = "missing_translation: vùng này chưa có bản dịch, không thể canh chữ"
            session.commit()
            return {"status": "failed", "job_id": str(job_id), "error": job.error_log}

        cu = session.execute(
            select(TypesetResult).where(TypesetResult.region_id == region_id)
        ).scalars().first()
        font_family = (cu.font_family if cu and cu.font_family else settings.default_font_family)
        page_id = page.id
        bbox = BBox(x=region.bbox_x, y=region.bbox_y, w=region.bbox_w, h=region.bbox_h)
        text = translation.translated_text or ""
        job.status = JobStatus.running
        session.commit()

    typesetter, resolver = build_typesetter()
    if font_size_override is not None:
        fit = typesetter.fit_at_size(text, bbox, font_family, float(font_size_override))
    else:
        fit = typesetter.fit(text, bbox, font_family)

    with sync_session() as session:
        # Idempotent: xoá kết quả cũ của ĐÚNG vùng này rồi ghi mới, không đụng vùng khác.
        session.execute(delete(TypesetResult).where(TypesetResult.region_id == region_id))
        session.add(
            TypesetResult(
                region_id=region_id,
                font_family=font_family,
                font_size=fit["font_size"],
                wrapped_text=fit["wrapped_text"] or None,
                padding_ratio=settings.typeset_padding_ratio,
                fit_status=FitStatus(fit["fit_status"]),
                edited_by_user=True,  # đây là đường sửa tay — luôn đánh dấu để còn audit
            )
        )
        session.commit()

    preview_rel = render_page_preview(page_id, resolver)
    elapsed = time.perf_counter() - started

    with sync_session() as session:
        job = session.get(Job, job_id)
        job.status = JobStatus.done
        job.error_log = None
        session.commit()

    logger.info(
        "refit vùng %s: cỡ=%s (%s%s), font=%s, preview=%s, %.2fs",
        region_id, fit["font_size"], fit["fit_status"],
        ", cỡ do người dùng ghim" if font_size_override is not None else "",
        font_family, preview_rel, elapsed,
    )
    cham_chat_luong(page_id, "refit")

    return {
        "status": "done",
        "job_id": str(job_id),
        "region_id": str(region_id),
        "page_id": str(page_id),
        "font_family": font_family,
        "font_size": fit["font_size"],
        "fit_status": fit["fit_status"],
        "pinned_size": font_size_override is not None,
        "preview_path": preview_rel,
        "elapsed_seconds": round(elapsed, 2),
    }


@celery_app.task(
    bind=True,
    name="typeset.run_refit_job",
    soft_time_limit=settings.refit_timeout_seconds,
    time_limit=settings.refit_timeout_seconds + 30,
)
def run_refit_job(self, job_id: str, region_id: str, font_size: float | None = None) -> dict:
    """Canh lại chữ cho 1 vùng sau khi người dùng sửa tay. Preview vẽ lại CẢ TRANG."""
    jid = uuid.UUID(str(job_id))
    try:
        return _run_refit(jid, uuid.UUID(str(region_id)), font_size)
    except SoftTimeLimitExceeded:
        reason = f"timeout: vượt {settings.refit_timeout_seconds}s"
        logger.error("refit job %s %s", jid, reason)
        _mark_job_failed(jid, reason)
        return {"status": "failed", "job_id": str(jid), "error": reason}
    except Exception as exc:  # noqa: BLE001
        reason = f"{type(exc).__name__}: {exc}"
        logger.exception("refit job %s thất bại", jid)
        _mark_job_failed(jid, reason)
        return {"status": "failed", "job_id": str(jid), "error": reason}


def _run_region_reocr(job_id: uuid.UUID, region_id: uuid.UUID) -> dict:
    """Đọc lại chữ gốc của MỘT vùng từ ảnh GỐC (không phải ảnh clean — ảnh clean đã xoá chữ)."""
    started = time.perf_counter()
    from app.services.interfaces import BBox

    with sync_session() as session:
        job = session.get(Job, job_id)
        if job is None:
            return {"status": "job_not_found", "job_id": str(job_id)}
        if job.type is not JobType.ocr:
            return {"status": "wrong_job_type", "job_id": str(job_id), "type": job.type.value}
        ctx = _region_context(session, region_id)
        if ctx is None:
            job.status = JobStatus.failed
            job.error_log = f"region_not_found: {region_id}"
            session.commit()
            return {"status": "failed", "job_id": str(job_id), "error": job.error_log}
        region, page, project = ctx
        bbox = BBox(x=region.bbox_x, y=region.bbox_y, w=region.bbox_w, h=region.bbox_h)
        image_rel = page.image_path
        source_lang = project.source_lang.value
        job.status = JobStatus.running
        session.commit()

    engine = get_ocr_engine_cached(source_lang)
    # Đọc lại một vùng cũng phải lấy đường bao dòng, nếu không thì vùng vừa sửa tay sẽ mất
    # bằng chứng hướng chữ trong khi các vùng khác vẫn còn — lệch nhau không ai giải thích được.
    co_layout = getattr(engine, "recognize_with_layout", None)
    with anh_cuc_bo(image_rel) as image_path:
        if co_layout is not None:
            text, confidence, polys = co_layout(image_path, bbox)
        else:
            text, confidence = engine.recognize(image_path, bbox)
            polys = None
    trang_thai = _classify_ocr(text, confidence)

    with sync_session() as session:
        session.execute(delete(OCRResult).where(OCRResult.region_id == region_id))
        session.add(
            OCRResult(
                region_id=region_id,
                raw_text=text,
                line_polygons=polys,
                ocr_engine=getattr(engine, "engine_enum", None),
                confidence=confidence,
                status=trang_thai,
            )
        )
        job = session.get(Job, job_id)
        job.status = JobStatus.done
        job.error_log = None
        session.commit()

    elapsed = time.perf_counter() - started
    logger.info("re-OCR vùng %s: %r (%s), %.2fs", region_id, (text or "")[:40], trang_thai.value, elapsed)
    return {
        "status": "done", "job_id": str(job_id), "region_id": str(region_id),
        "raw_text": text, "confidence": confidence, "ocr_status": trang_thai.value,
        "elapsed_seconds": round(elapsed, 2),
    }


@celery_app.task(
    bind=True,
    name="ocr.run_region_reocr_job",
    soft_time_limit=settings.ocr_timeout_seconds,
    time_limit=settings.ocr_timeout_seconds + 30,
)
def run_region_reocr_job(self, job_id: str, region_id: str) -> dict:
    """Đọc lại chữ gốc của 1 vùng. KHÔNG tự dịch lại — người dùng chủ động bấm tiếp."""
    jid = uuid.UUID(str(job_id))
    try:
        return _run_region_reocr(jid, uuid.UUID(str(region_id)))
    except SoftTimeLimitExceeded:
        reason = f"timeout: vượt {settings.ocr_timeout_seconds}s"
        _mark_job_failed(jid, reason)
        return {"status": "failed", "job_id": str(jid), "error": reason}
    except Exception as exc:  # noqa: BLE001
        reason = f"{type(exc).__name__}: {exc}"
        logger.exception("re-OCR job %s thất bại", jid)
        _mark_job_failed(jid, reason)
        return {"status": "failed", "job_id": str(jid), "error": reason}


def _run_region_retranslate(job_id: uuid.UUID, region_id: uuid.UUID, engine_override: str | None) -> dict:
    """Dịch lại MỘT vùng từ `OCRResult.raw_text` hiện tại.

    Dịch lại 1 dòng lẻ thì `llm_context` mất hết lợi thế ngữ cảnh cả trang — đây là đánh đổi
    có ý thức của việc sửa tay từng vùng, ghi rõ trong REPORT_M7.
    """
    started = time.perf_counter()
    from app.services.translate.engines import QuotaExhausted, TranslationFailed

    with sync_session() as session:
        job = session.get(Job, job_id)
        if job is None:
            return {"status": "job_not_found", "job_id": str(job_id)}
        if job.type is not JobType.translate:
            return {"status": "wrong_job_type", "job_id": str(job_id), "type": job.type.value}
        ctx = _region_context(session, region_id)
        if ctx is None:
            job.status = JobStatus.failed
            job.error_log = f"region_not_found: {region_id}"
            session.commit()
            return {"status": "failed", "job_id": str(job_id), "error": job.error_log}
        _region, _page, project = ctx

        ocr = session.execute(
            select(OCRResult).where(OCRResult.region_id == region_id)
        ).scalars().first()
        if ocr is None or not (ocr.raw_text or "").strip():
            job.status = JobStatus.failed
            job.error_log = "missing_ocr: vùng này chưa đọc được chữ gốc, không có gì để dịch"
            session.commit()
            return {"status": "failed", "job_id": str(job_id), "error": job.error_log}

        raw_text = ocr.raw_text
        source_lang = project.source_lang.value
        target_lang = project.target_lang.value
        job.status = JobStatus.running
        session.commit()

    engine_name = engine_override or settings.translate_default_engine
    used_engine, fallback_reason = engine_name, None
    translator = build_translator(engine_name)
    try:
        dich = translator.translate([raw_text], source_lang, target_lang)
    except (QuotaExhausted, TranslationFailed) as exc:
        if engine_name != TranslationEngine.llm_context.value or not settings.llm_fallback_to_google:
            raise
        fallback_reason = f"{type(exc).__name__}: {exc}"
        logger.warning("LLM lỗi khi dịch lại vùng (%s) -> lùi về google_fast", fallback_reason[:200])
        used_engine = TranslationEngine.google_fast.value
        translator = build_translator(used_engine)
        dich = translator.translate([raw_text], source_lang, target_lang)

    text = (dich[0] if dich else "") or ""
    usage = getattr(translator, "usage", None)

    with sync_session() as session:
        session.execute(delete(TranslationResult).where(TranslationResult.region_id == region_id))
        session.add(
            TranslationResult(
                region_id=region_id,
                translated_text=text or None,
                engine=TranslationEngine(used_engine),
                model_name=getattr(translator, "model_name", None),
                token_cost=(usage.total_tokens if usage else None),
                status=(
                    TranslationStatus.pending
                    if not text.strip()
                    else (TranslationStatus.fallback_used if fallback_reason else TranslationStatus.ok)
                ),
                edited_by_user=False,  # máy dịch lại, KHÔNG phải người gõ tay
            )
        )
        job = session.get(Job, job_id)
        job.status = JobStatus.done
        job.error_log = f"fallback_used: {fallback_reason}"[:4000] if fallback_reason else None
        session.commit()

    elapsed = time.perf_counter() - started
    logger.info("dịch lại vùng %s: %r engine=%s, %.2fs", region_id, text[:40], used_engine, elapsed)
    return {
        "status": "done", "job_id": str(job_id), "region_id": str(region_id),
        "translated_text": text, "engine": used_engine, "fallback": bool(fallback_reason),
        "token_cost": usage.total_tokens if usage else None,
        "elapsed_seconds": round(elapsed, 2),
    }


@celery_app.task(
    bind=True,
    name="translate.run_region_retranslate_job",
    soft_time_limit=settings.translate_timeout_seconds,
    time_limit=settings.translate_timeout_seconds + 30,
)
def run_region_retranslate_job(self, job_id: str, region_id: str, engine: str | None = None) -> dict:
    """Dịch lại 1 vùng. KHÔNG tự canh chữ lại — người dùng chủ động bấm tiếp."""
    jid = uuid.UUID(str(job_id))
    try:
        return _run_region_retranslate(jid, uuid.UUID(str(region_id)), engine)
    except SoftTimeLimitExceeded:
        reason = f"timeout: vượt {settings.translate_timeout_seconds}s"
        _mark_job_failed(jid, reason)
        return {"status": "failed", "job_id": str(jid), "error": reason}
    except Exception as exc:  # noqa: BLE001
        reason = f"{type(exc).__name__}: {exc}"
        logger.exception("dịch lại vùng %s thất bại", jid)
        _mark_job_failed(jid, reason)
        return {"status": "failed", "job_id": str(jid), "error": reason}


# ============================ M8: Xuất chapter ============================

#: Trang chỉ được xuất khi đã canh chữ xong — xuất bản chưa qua canh là giao ảnh chưa có chữ.
TRANG_XUAT_DUOC = (PageStatus.typeset_done, PageStatus.ready_for_export)


def dem_vung_tran_khung(session, page_ids: list[uuid.UUID]) -> int:
    """Đếm số vùng còn `overflow_warning` trong cả chapter, TẠI THỜI ĐIỂM xuất."""
    if not page_ids:
        return 0
    return session.execute(
        select(func.count())
        .select_from(TypesetResult)
        .join(TextRegion, TextRegion.id == TypesetResult.region_id)
        .where(TextRegion.page_id.in_(page_ids), TypesetResult.fit_status == FitStatus.overflow_warning)
    ).scalar() or 0


def thong_ke_xuat(session, project_id: uuid.UUID) -> dict:
    """Xem trước trước khi xuất: bao nhiêu trang xuất được, bao nhiêu vùng còn tràn khung."""
    tat_ca = list(
        session.execute(
            select(Page).where(Page.project_id == project_id).order_by(Page.order)
        ).scalars()
    )
    xuat_duoc = [p for p in tat_ca if p.status in TRANG_XUAT_DUOC]
    return {
        "page_count": len(xuat_duoc),
        "total_page_count": len(tat_ca),
        "skipped_page_count": len(tat_ca) - len(xuat_duoc),
        "overflow_warning_count": dem_vung_tran_khung(session, [p.id for p in xuat_duoc]),
    }


def _thu_thap_trang(session, project_id: uuid.UUID):
    """Gom dữ liệu vẽ cho từng trang xuất được, theo ĐÚNG `Page.order`."""
    from app.services.export.chapter import TrangCanXuat
    from app.services.interfaces import BBox
    from app.services.safearea.apply import nap_o_dat_chu
    from app.services.typeset.preview import RegionDraw

    storage = get_storage()
    trang_list = []
    bo_qua: list[str] = []

    for page in session.execute(
        select(Page).where(Page.project_id == project_id).order_by(Page.order)
    ).scalars():
        if page.status not in TRANG_XUAT_DUOC:
            bo_qua.append(f"trang {page.order} ({page.status.value})")
            continue
        if not page.clean_image_path:
            bo_qua.append(f"trang {page.order} (thiếu ảnh clean)")
            continue

        rows = session.execute(
            select(TextRegion, TypesetResult)
            .join(TypesetResult, TypesetResult.region_id == TextRegion.id)
            .where(TextRegion.page_id == page.id)
            .order_by(TextRegion.reading_order.nulls_last(), TextRegion.created_at)
        ).all()
        # ĐÚNG hàm mà ảnh xem thử dùng: người xem thấy sao thì file tải về phải y như vậy.
        o_dat_xuat = nap_o_dat_chu(
            session, [r.id for r, _ts in rows], van_tay_hien_vat(storage, page.clean_image_path)
        )
        trang_list.append(
            TrangCanXuat(
                page_id=str(page.id),
                order=page.order,
                clean_image_rel=page.clean_image_path,
                regions=[
                    RegionDraw(
                        bbox=BBox(x=r.bbox_x, y=r.bbox_y, w=r.bbox_w, h=r.bbox_h),
                        wrapped_text=ts.wrapped_text or "",
                        font_family=ts.font_family or settings.default_font_family,
                        font_size=ts.font_size,
                        padding_ratio=(
                            ts.padding_ratio
                            if ts.padding_ratio is not None
                            else settings.typeset_padding_ratio
                        ),
                        # Ảnh GIAO CHO NGƯỜI ĐỌC: không vẽ khung đỏ cảnh báo lên đó.
                        overflow=False,
                        place_rect=o_dat_xuat.get(r.id),
                    )
                    for r, ts in rows
                ],
            )
        )
    return trang_list, bo_qua


def _run_export(job_id: uuid.UUID) -> dict:
    started = time.perf_counter()
    from pathlib import Path as _Path

    from app.services.export.chapter import ChapterExporter
    from app.services.export.naming import ten_file_export
    from app.services.export.paths import export_relative_dir
    from app.services.typeset.preview import PagePreviewRenderer

    with sync_session() as session:
        job = session.get(ExportJob, job_id)
        if job is None:
            logger.warning("ExportJob %s không tồn tại", job_id)
            return {"status": "job_not_found", "job_id": str(job_id)}

        project = session.get(Project, job.project_id)
        if project is None:
            job.status = JobStatus.failed
            job.error_log = "project_not_found"
            session.commit()
            return {"status": "failed", "job_id": str(job_id), "error": job.error_log}

        project_id, project_name, dinh_dang = project.id, project.name, job.format
        trang_list, bo_qua = _thu_thap_trang(session, project_id)
        so_tran = dem_vung_tran_khung(session, [uuid.UUID(t.page_id) for t in trang_list])

        if not trang_list:
            job.status = JobStatus.failed
            job.error_log = (
                "no_page_ready: không có trang nào đã canh chữ xong để xuất"
                + (f" (bỏ qua: {', '.join(bo_qua)})" if bo_qua else "")
            )
            session.commit()
            return {"status": "failed", "job_id": str(job_id), "error": job.error_log}

        job.status = JobStatus.running
        job.overflow_warning_count = so_tran
        session.commit()

    storage = get_storage()
    _typesetter, resolver = build_typesetter()
    exporter = ChapterExporter(
        storage=storage,
        renderer=PagePreviewRenderer(
            font_resolver=resolver,
            line_spacing_ratio=settings.typeset_line_spacing_ratio,
            text_color=settings.typeset_text_color,
            stroke_color=settings.typeset_stroke_color,
            stroke_width=settings.typeset_stroke_width,
        ),
    )
    thu_muc_kho = export_relative_dir(project_id)
    # Dọn bản xuất cũ Ở KHO, trước khi ghi bản mới. Trước P3c việc này do bộ xuất tự làm bằng
    # cách quét thư mục thật — nay kho là thứ duy nhất biết mình đang giữ những gì.
    da_xoa = storage.delete_prefix(thu_muc_kho)

    # Bộ xuất vẽ ra thư mục tạm; chỉ những gì vẽ XONG mới được đưa vào kho.
    with workspace() as ws:
        if dinh_dang is ExportFormat.png_single:
            duong_dan = exporter.export_png_single(ws, trang_list)
            output_rel = f"{thu_muc_kho}/png"
            for tep in sorted(_Path(duong_dan).iterdir()):
                if tep.is_file():
                    storage.save_file(f"{output_rel}/{tep.name}", tep)
        else:
            duoi = "cbz" if dinh_dang is ExportFormat.cbz else "zip"
            ten = ten_file_export(project_name, duoi)
            duong_dan = (
                exporter.export_cbz(ws, trang_list, ten)
                if dinh_dang is ExportFormat.cbz
                else exporter.export_zip(ws, trang_list, ten)
            )
            output_rel = storage.save_file(f"{thu_muc_kho}/{ten}", _Path(duong_dan))
    elapsed = time.perf_counter() - started

    with sync_session() as session:
        job = session.get(ExportJob, job_id)
        job.status = JobStatus.done
        job.output_path = output_rel
        job.page_count = len(trang_list)
        job.overflow_warning_count = so_tran
        # Xuất vẫn THÀNH CÔNG khi có trang bị bỏ qua / vùng tràn khung — nhưng phải ghi lại,
        # không để người dùng tưởng đã xuất đủ cả chapter.
        canh_bao = []
        if bo_qua:
            canh_bao.append(f"skipped_pages: bỏ qua {len(bo_qua)} trang chưa canh chữ ({', '.join(bo_qua)})")
        if so_tran:
            canh_bao.append(f"overflow_warning: {so_tran} vùng còn tràn khung")
        job.error_log = " | ".join(canh_bao)[:4000] if canh_bao else None

        moc = datetime.now(timezone.utc)
        for trang in trang_list:
            page = session.get(Page, uuid.UUID(trang.page_id))
            if page is not None:
                page.exported_at = moc
        session.commit()

    logger.info(
        "export job %s: %d trang -> %s (%s), %d vùng tràn khung, bỏ qua %d trang, "
        "xoá %d thứ cũ, %.1fs",
        job_id, len(trang_list), output_rel, dinh_dang.value, so_tran, len(bo_qua),
        len(da_xoa), elapsed,
    )
    return {
        "status": "done",
        "job_id": str(job_id),
        "project_id": str(project_id),
        "format": dinh_dang.value,
        "output_path": output_rel,
        "page_count": len(trang_list),
        "skipped_pages": bo_qua,
        "overflow_warning_count": so_tran,
        "replaced_old_files": da_xoa,
        "elapsed_seconds": round(elapsed, 2),
    }


@celery_app.task(
    bind=True,
    name="export.run_export_job",
    soft_time_limit=settings.export_timeout_seconds,
    time_limit=settings.export_timeout_seconds + 30,
)
def run_export_job(self, job_id: str) -> dict:
    """Xuất cả chapter ra PNG/CBZ/ZIP. Lỗi/timeout: ExportJob=failed + error_log rõ nguyên nhân."""
    jid = uuid.UUID(str(job_id))
    try:
        return _run_export(jid)
    except SoftTimeLimitExceeded:
        reason = f"timeout: vượt {settings.export_timeout_seconds}s"
        logger.error("export job %s %s", jid, reason)
        _danh_dau_export_that_bai(jid, reason)
        return {"status": "failed", "job_id": str(jid), "error": reason}
    except Exception as exc:  # noqa: BLE001
        reason = f"{type(exc).__name__}: {exc}"
        logger.exception("export job %s thất bại", jid)
        _danh_dau_export_that_bai(jid, reason)
        return {"status": "failed", "job_id": str(jid), "error": reason}


def _danh_dau_export_that_bai(job_id: uuid.UUID, reason: str) -> None:
    with sync_session() as session:
        job = session.get(ExportJob, job_id)
        if job is not None:
            job.status = JobStatus.failed
            job.error_log = reason[:4000]
            session.commit()


# ============================ E13: rà soát nhất quán ============================


def _run_consistency_scan(job_id: uuid.UUID, project_id: uuid.UUID) -> dict:
    """Quét theo luật tất định. KHÔNG gọi mạng, KHÔNG sửa bản dịch."""
    started = time.perf_counter()
    from app.services.consistency.scanner import ConsistencyScanner

    with sync_session() as session:
        job = session.get(Job, job_id)
        if job is None:
            logger.warning("Job %s không tồn tại", job_id)
            return {"status": "job_not_found", "job_id": str(job_id)}
        job.status = JobStatus.running
        session.commit()

    with sync_session() as session:
        tom_tat = ConsistencyScanner(session).scan_project(project_id)

    elapsed = time.perf_counter() - started
    with sync_session() as session:
        job = session.get(Job, job_id)
        job.status = JobStatus.done
        job.error_log = None
        session.commit()

    logger.info(
        "quét nhất quán %s: xét %d vùng (bỏ qua %d), tạo mới %d, giữ %d, đánh dấu cũ %d, %.1fs",
        project_id, tom_tat.so_vung_xet, tom_tat.so_vung_bo_qua,
        tom_tat.tao_moi, tom_tat.giu_nguyen, tom_tat.danh_dau_cu, elapsed,
    )
    return {
        "status": "done",
        "job_id": str(job_id),
        "project_id": str(project_id),
        "version": tom_tat.version,
        "regions_scanned": tom_tat.so_vung_xet,
        "regions_skipped": tom_tat.so_vung_bo_qua,
        "tasks_created": tom_tat.tao_moi,
        "tasks_unchanged": tom_tat.giu_nguyen,
        "tasks_marked_stale": tom_tat.danh_dau_cu,
        "by_type": tom_tat.theo_loai,
        "elapsed_seconds": round(elapsed, 2),
    }


@celery_app.task(
    bind=True,
    name="consistency.run_consistency_scan_job",
    soft_time_limit=settings.consistency_scan_timeout_seconds,
    time_limit=settings.consistency_scan_timeout_seconds + 30,
)
def run_consistency_scan_job(self, job_id: str, project_id: str) -> dict:
    """Quét nhất quán cả chapter theo luật. Không gọi LLM, không sửa gì."""
    jid = uuid.UUID(str(job_id))
    try:
        return _run_consistency_scan(jid, uuid.UUID(str(project_id)))
    except SoftTimeLimitExceeded:
        reason = f"timeout: vượt {settings.consistency_scan_timeout_seconds}s"
        logger.error("quét nhất quán %s %s", jid, reason)
        _mark_job_failed(jid, reason)
        return {"status": "failed", "job_id": str(jid), "error": reason}
    except Exception as exc:  # noqa: BLE001
        reason = f"{type(exc).__name__}: {exc}"
        logger.exception("quét nhất quán %s thất bại", jid)
        _mark_job_failed(jid, reason)
        return {"status": "failed", "job_id": str(jid), "error": reason}


# ==================================================================== E17 tầng 3


def _run_term_suggestion(run_id: uuid.UUID) -> dict:
    """Hỏi mô hình cách dịch cho các danh xưng CÓ THẬT trong chapter, rồi đối chiếu lại.

    Không ghi một dòng nào vào `glossary_entry`: kết quả nằm trong `term_suggestion_run` dưới
    nhãn `goi_y_mo_hinh_chua_duyet` cho tới khi người dùng tự tay nhận.
    """
    from app.models import TermSuggestionRun
    from app.models.enums import TermSuggestionStatus
    from app.services.consistency.goi_y_ten import TRAN_HOI, dung_prompt, phan_tich_va_doi_chieu
    from app.services.consistency.ungvien import rut_ung_vien
    from app.services.translate.engines import QuotaExhausted, TranslationFailed

    started = time.perf_counter()
    with sync_session() as session:
        run = session.get(TermSuggestionRun, run_id)
        if run is None:
            return {"status": "failed", "run_id": str(run_id), "error": "run_not_found"}
        run.status = TermSuggestionStatus.running
        project_id = run.project_id
        series_name = run.series_name
        session.commit()

        ket = rut_ung_vien(session, project_id)
        terms = [uv.term for uv in ket.ung_vien][:TRAN_HOI]
        lang = session.get(Project, project_id).source_lang.value

        if not terms:
            # Không có danh xưng nào để hỏi thì KHÔNG gọi mô hình — hỏi suông vẫn tốn tiền, và
            # câu trả lời cho một danh sách rỗng chắc chắn là bịa.
            run.status = TermSuggestionStatus.done
            run.suggestions = []
            run.asked_count = 0
            run.error_log = f"khong_co_ung_vien:{ket.trang_thai}"
            session.commit()
            return {"status": "done", "run_id": str(run_id), "asked": 0, "kept": 0,
                    "reason": ket.trang_thai}

    prompt = dung_prompt(series_name, terms, lang)
    try:
        _cong_nhip(TranslationEngine.llm_context.value)
        translator = build_translator(TranslationEngine.llm_context.value)
        text, usage = translator.goi_prompt_tho(prompt)
    except (QuotaExhausted, TranslationFailed) as exc:
        with sync_session() as session:
            run = session.get(TermSuggestionRun, run_id)
            run.status = TermSuggestionStatus.failed
            run.error_log = f"{type(exc).__name__}: {exc}"
            run.asked_count = len(terms)
            session.commit()
        return {"status": "failed", "run_id": str(run_id), "error": str(exc)}

    goi_y, bi_loai = phan_tich_va_doi_chieu(text, terms)

    with sync_session() as session:
        run = session.get(TermSuggestionRun, run_id)
        run.status = TermSuggestionStatus.done
        run.suggestions = [g.to_json() for g in goi_y]
        run.asked_count = len(terms)
        run.dropped_count = bi_loai
        run.model_name = settings.llm_model_name
        session.commit()

    elapsed = time.perf_counter() - started
    if bi_loai:
        # Con số này là bằng chứng model có bịa trong lượt đó — ghi ra, không nuốt.
        logger.warning("E17 tầng 3: loại %s mục không khớp danh sách đã hỏi (run %s)", bi_loai, run_id)
    logger.info(
        "E17 tầng 3 xong run=%s hỏi=%s giữ=%s loại=%s token=%s trong %.1fs",
        run_id, len(terms), len(goi_y), bi_loai, usage.get("totalTokenCount"), elapsed,
    )
    return {"status": "done", "run_id": str(run_id), "asked": len(terms),
            "kept": len(goi_y), "dropped": bi_loai, "elapsed_seconds": round(elapsed, 2)}


@celery_app.task(
    bind=True,
    name="consistency.run_term_suggestion_job",
    soft_time_limit=settings.term_suggestion_timeout_seconds,
    time_limit=settings.term_suggestion_timeout_seconds + 30,
)
def run_term_suggestion_job(self, run_id: str) -> dict:
    """E17 tầng 3. Hỏi mô hình, đối chiếu, LƯU dưới nhãn chưa duyệt — không tự tạo thuật ngữ."""
    from app.models import TermSuggestionRun
    from app.models.enums import TermSuggestionStatus

    rid = uuid.UUID(str(run_id))
    try:
        return _run_term_suggestion(rid)
    except SoftTimeLimitExceeded:
        reason = f"timeout: vượt {settings.term_suggestion_timeout_seconds}s"
    except Exception as exc:  # noqa: BLE001
        reason = f"{type(exc).__name__}: {exc}"
        logger.exception("E17 tầng 3 run %s thất bại", rid)
    with sync_session() as session:
        run = session.get(TermSuggestionRun, rid)
        if run is not None:
            run.status = TermSuggestionStatus.failed
            run.error_log = reason
            session.commit()
    return {"status": "failed", "run_id": str(rid), "error": reason}
