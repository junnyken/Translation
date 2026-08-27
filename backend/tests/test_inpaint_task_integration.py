"""Integration — Celery task inpaint trên DB thật (model giả lập)."""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa

from app.core.db_sync import sync_session
from app.models import Job, OCRResult, Page, TextRegion
from app.models.enums import JobStatus, JobType, OCREngine, OCRStatus, PageStatus
from app.services.detect.ctd import DetectedRegion
from app.services.interfaces import BBox
from app.workers.tasks import run_detect_job, run_inpaint_job, run_ocr_job


def _region(x, y, w, h, conf=0.9) -> DetectedRegion:
    return DetectedRegion(bbox=BBox(x=x, y=y, w=w, h=h), confidence=conf, cls=0)


async def _page_through_ocr(client, sample_page_image, fake_detector, fake_ocr_engine, regions=None):
    """Đưa 1 page đi hết detect + OCR bằng đúng đường thật, trả page_id."""
    proj = await client.post(
        "/api/v1/projects", json={"name": "M4", "source_lang": "en", "intended_use": "study"}
    )
    up = await client.post(
        f"/api/v1/projects/{proj.json()['id']}/pages",
        files={"file": ("p.png", sample_page_image, "image/png")},
    )
    page_id = up.json()["page_id"]
    fake_detector(regions=regions or [_region(20, 20, 100, 50), _region(300, 300, 120, 60)])
    run_detect_job(up.json()["job_id"])
    fake_ocr_engine(results=("HELLO", 0.95), engine_enum=OCREngine.paddle_ocr)
    run_ocr_job(_job_id(page_id, JobType.ocr))
    # Mặc định: bước kiểm chứng của M4 sẽ OCR lại vùng đã xoá và KHÔNG thấy chữ
    # (tức inpaint sạch). Test nào muốn mô phỏng "còn sót chữ" thì tự cắm lại engine.
    fake_ocr_engine(results=("", None), engine_enum=OCREngine.paddle_ocr)
    return page_id


def _job_id(page_id: str, job_type: JobType) -> str:
    with sync_session() as s:
        job = s.execute(
            sa.select(Job)
            .where(Job.page_id == uuid.UUID(page_id), Job.type == job_type)
            .order_by(Job.created_at.desc())
        ).scalars().first()
        return str(job.id) if job else ""


def _page(page_id: str) -> Page:
    with sync_session() as s:
        return s.get(Page, uuid.UUID(page_id))


def _md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


async def test_ocr_xong_tu_dong_xep_viec_inpaint(
    client, sample_page_image, fake_detector, fake_ocr_engine, no_broker_for_chained_ocr
):
    page_id = await _page_through_ocr(client, sample_page_image, fake_detector, fake_ocr_engine)
    with sync_session() as s:
        jobs = list(
            s.execute(
                sa.select(Job).where(
                    Job.page_id == uuid.UUID(page_id), Job.type == JobType.inpaint
                )
            ).scalars()
        )
    assert len(jobs) == 1
    assert jobs[0].status is JobStatus.queued
    assert str(jobs[0].id) in no_broker_for_chained_ocr


async def test_inpaint_sinh_anh_clean_va_chuyen_trang_thai(
    client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter, storage_root
):
    page_id = await _page_through_ocr(client, sample_page_image, fake_detector, fake_ocr_engine)
    fake_inpainter()

    result = run_inpaint_job(_job_id(page_id, JobType.inpaint))

    assert result["status"] == "done", result
    assert result["page_status"] == "inpainted", result
    page = _page(page_id)
    assert page.clean_image_path
    assert page.clean_image_path != page.image_path
    assert (Path(storage_root) / page.clean_image_path).is_file()
    assert page.status is PageStatus.inpainted


async def test_anh_goc_khong_bi_ghi_de(
    client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter, storage_root
):
    """REGRESSION — invariant quan trọng nhất của M4, so checksum trước/sau."""
    page_id = await _page_through_ocr(client, sample_page_image, fake_detector, fake_ocr_engine)
    original = Path(storage_root) / _page(page_id).image_path
    before = _md5(original)

    fake_inpainter()
    run_inpaint_job(_job_id(page_id, JobType.inpaint))

    assert original.is_file(), "ảnh gốc bị xoá sau khi inpaint"
    assert _md5(original) == before, "ảnh gốc bị ghi đè"
    clean = Path(storage_root) / _page(page_id).clean_image_path
    assert _md5(clean) != before


async def test_ocr_lai_con_chu_thi_danh_dau_can_review(
    client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter
):
    """Kiểm chứng khách quan: OCR lại vùng đã xoá mà còn chữ -> inpaint_needs_review."""
    page_id = await _page_through_ocr(client, sample_page_image, fake_detector, fake_ocr_engine)
    fake_inpainter()
    fake_ocr_engine(results=("CHỮ VẪN CÒN", 0.95), engine_enum=OCREngine.paddle_ocr)

    result = run_inpaint_job(_job_id(page_id, JobType.inpaint))

    assert result["status"] == "done"
    assert result["page_status"] == "inpaint_needs_review"
    assert result["regions_with_text_left"] == 2
    assert _page(page_id).status is PageStatus.inpaint_needs_review


async def test_ocr_lai_khong_con_chu_thi_pass(
    client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter
):
    page_id = await _page_through_ocr(client, sample_page_image, fake_detector, fake_ocr_engine)
    fake_inpainter()
    fake_ocr_engine(results=("   ", None), engine_enum=OCREngine.paddle_ocr)

    result = run_inpaint_job(_job_id(page_id, JobType.inpaint))

    assert result["regions_with_text_left"] == 0
    assert result["page_status"] == "inpainted"


async def test_chay_lai_xoa_anh_clean_cu_khong_de_file_rac(
    client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter, storage_root
):
    """REGRESSION: idempotent — không tích tụ file rác qua mỗi lần chạy lại."""
    page_id = await _page_through_ocr(client, sample_page_image, fake_detector, fake_ocr_engine)
    fake_inpainter()
    run_inpaint_job(_job_id(page_id, JobType.inpaint))

    clean_rel = _page(page_id).clean_image_path
    pages_dir = (Path(storage_root) / clean_rel).parent
    files_after_first = sorted(p.name for p in pages_dir.iterdir())

    retry = await client.post(f"/api/v1/pages/{page_id}/retry-inpaint")
    assert retry.status_code == 202
    result = run_inpaint_job(retry.json()["job_id"])

    assert result["replaced_old_clean_image"] is True
    files_after_second = sorted(p.name for p in pages_dir.iterdir())
    assert files_after_second == files_after_first, "chạy lại để lại file rác"
    assert _page(page_id).clean_image_path == clean_rel


async def test_page_chua_ocr_thi_tu_choi_inpaint(client, sample_page_image, fake_detector, fake_inpainter):
    """Không xoá chữ trên trang chưa đọc xong chữ."""
    proj = await client.post(
        "/api/v1/projects", json={"name": "M4", "source_lang": "en", "intended_use": "study"}
    )
    up = await client.post(
        f"/api/v1/projects/{proj.json()['id']}/pages",
        files={"file": ("p.png", sample_page_image, "image/png")},
    )
    page_id = up.json()["page_id"]
    fake_detector(regions=[_region(20, 20, 100, 50)])
    run_detect_job(up.json()["job_id"])  # dừng ở detected, chưa OCR

    with sync_session() as s:
        job = Job(type=JobType.inpaint, page_id=uuid.UUID(page_id), status=JobStatus.queued)
        s.add(job)
        s.commit()
        job_id = str(job.id)

    fake_inpainter()
    result = run_inpaint_job(job_id)

    assert result["status"] == "failed"
    assert "precondition_failed" in result["error"]
    assert _page(page_id).status is PageStatus.detected
    assert _page(page_id).clean_image_path is None


async def test_thieu_ket_qua_ocr_cua_mot_vung_thi_tu_choi(
    client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter
):
    page_id = await _page_through_ocr(client, sample_page_image, fake_detector, fake_ocr_engine)
    # xoá bớt 1 OCRResult -> dữ liệu dở dang
    with sync_session() as s:
        row = s.execute(
            sa.select(OCRResult)
            .join(TextRegion, TextRegion.id == OCRResult.region_id)
            .where(TextRegion.page_id == uuid.UUID(page_id))
        ).scalars().first()
        s.delete(row)
        s.commit()

    fake_inpainter()
    result = run_inpaint_job(_job_id(page_id, JobType.inpaint))

    assert result["status"] == "failed"
    assert "missing_ocr" in result["error"]
    assert _page(page_id).clean_image_path is None


async def test_loi_giua_chung_thi_page_giu_nguyen_trang_thai(
    client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter
):
    page_id = await _page_through_ocr(client, sample_page_image, fake_detector, fake_ocr_engine)
    fake_inpainter(raises=RuntimeError("LaMa lăn ra chết"))

    result = run_inpaint_job(_job_id(page_id, JobType.inpaint))

    assert result["status"] == "failed"
    assert "LaMa lăn ra chết" in result["error"]
    page = _page(page_id)
    assert page.status is PageStatus.ocr_done  # KHÔNG nhảy inpainted
    assert page.clean_image_path is None
    with sync_session() as s:
        assert s.get(Job, uuid.UUID(_job_id(page_id, JobType.inpaint))).status is JobStatus.failed


async def test_job_inpaint_khong_ton_tai_khong_lam_worker_chet(fake_inpainter):
    fake_inpainter()
    assert run_inpaint_job(str(uuid.uuid4()))["status"] == "job_not_found"


async def test_endpoint_clean_image(
    client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter
):
    page_id = await _page_through_ocr(client, sample_page_image, fake_detector, fake_ocr_engine)

    before = await client.get(f"/api/v1/pages/{page_id}/clean-image")
    assert before.status_code == 404  # chưa inpaint -> không bịa ảnh

    fake_inpainter()
    run_inpaint_job(_job_id(page_id, JobType.inpaint))

    after = await client.get(f"/api/v1/pages/{page_id}/clean-image")
    assert after.status_code == 200
    assert after.headers["content-type"] == "image/png"
    assert len(after.content) > 100


async def test_retry_inpaint_khi_page_chua_san_sang_tra_409(client, sample_page_image):
    proj = await client.post(
        "/api/v1/projects", json={"name": "M4", "source_lang": "en", "intended_use": "study"}
    )
    up = await client.post(
        f"/api/v1/projects/{proj.json()['id']}/pages",
        files={"file": ("p.png", sample_page_image, "image/png")},
    )
    r = await client.post(f"/api/v1/pages/{up.json()['page_id']}/retry-inpaint")
    assert r.status_code == 409
