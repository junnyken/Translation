"""Integration — Celery task detect chạy thật trên DB thật (detector giả lập).

Chạy model ONNX thật là test riêng (test_detect_real_model.py), vì mất ~40s/ảnh.
"""
from __future__ import annotations

import time
import uuid

import pytest
import sqlalchemy as sa
from celery.exceptions import SoftTimeLimitExceeded

from app.core.db_sync import sync_session
from app.models import Job, Page, TextRegion
from app.models.enums import JobStatus, PageStatus, RegionStatus
from app.services.detect.ctd import DetectedRegion
from app.services.interfaces import BBox
from app.workers.tasks import run_detect_job


def _region(x, y, w, h, conf, cls=0) -> DetectedRegion:
    return DetectedRegion(bbox=BBox(x=x, y=y, w=w, h=h), confidence=conf, cls=cls)


async def _make_page(client, sample_page_image) -> tuple[str, str]:
    proj = await client.post(
        "/api/v1/projects",
        json={"name": "M2", "source_lang": "ja", "intended_use": "personal"},
    )
    up = await client.post(
        f"/api/v1/projects/{proj.json()['id']}/pages",
        files={"file": ("p.png", sample_page_image, "image/png")},
    )
    body = up.json()
    return body["page_id"], body["job_id"]


def _db_counts(page_id):
    with sync_session() as s:
        regions = s.execute(
            sa.select(TextRegion).where(TextRegion.page_id == uuid.UUID(page_id))
        ).scalars().all()
        page = s.get(Page, uuid.UUID(page_id))
        return page, regions


async def test_detect_ghi_region_va_chuyen_page_sang_detected(
    client, sample_page_image, fake_detector
):
    page_id, job_id = await _make_page(client, sample_page_image)
    fake_detector(regions=[_region(10, 10, 100, 50, 0.9), _region(300, 300, 120, 60, 0.7)])

    result = run_detect_job(job_id)

    assert result["status"] == "done"
    assert result["regions"] == 2
    page, regions = _db_counts(page_id)
    assert page.status is PageStatus.detected
    assert len(regions) == 2
    assert {r.status for r in regions} == {RegionStatus.pending}
    with sync_session() as s:
        job = s.get(Job, uuid.UUID(job_id))
        assert job.status is JobStatus.done
        assert job.error_log is None


async def test_confidence_thap_van_duoc_luu_voi_low_confidence(
    client, sample_page_image, fake_detector
):
    """GUARDRAIL: region confidence thấp KHÔNG được biến mất âm thầm."""
    page_id, job_id = await _make_page(client, sample_page_image)
    fake_detector(regions=[_region(10, 10, 100, 50, 0.92), _region(400, 400, 80, 40, 0.31)])

    result = run_detect_job(job_id)

    assert result["low_confidence"] == 1
    _, regions = _db_counts(page_id)
    assert len(regions) == 2, "region confidence thấp đã bị xóa âm thầm"
    low = [r for r in regions if r.status is RegionStatus.low_confidence]
    assert len(low) == 1
    assert low[0].confidence == pytest.approx(0.31)


async def test_box_chong_lap_qua_nguong_bi_gan_co_nhung_khong_bi_xoa(
    client, sample_page_image, fake_detector
):
    page_id, job_id = await _make_page(client, sample_page_image)
    fake_detector(
        regions=[
            _region(0, 0, 200, 100, 0.9),
            _region(10, 5, 100, 90, 0.8),  # nằm gần trọn trong box trên
            _region(800, 800, 50, 50, 0.7),
        ]
    )

    result = run_detect_job(job_id)

    assert result["regions"] == 3, "không được tự merge/xóa box chồng lấp"
    assert result["overlap_suspect"] == 2
    _, regions = _db_counts(page_id)
    assert sum(1 for r in regions if r.overlap_suspect) == 2


async def test_chay_lai_khong_tao_region_trung_lap(client, sample_page_image, fake_detector):
    """REGRESSION: idempotent — retry job không nhân đôi TextRegion."""
    page_id, job_id = await _make_page(client, sample_page_image)
    fake_detector(regions=[_region(10, 10, 100, 50, 0.9), _region(300, 300, 120, 60, 0.8)])

    run_detect_job(job_id)
    _, first = _db_counts(page_id)
    second_result = run_detect_job(job_id)
    _, second = _db_counts(page_id)

    assert len(first) == 2
    assert len(second) == 2, "chạy lại đã nhân đôi region"
    assert second_result["replaced_regions"] == 2
    assert {r.id for r in first}.isdisjoint({r.id for r in second})


async def test_timeout_ghi_failed_va_detection_failed(client, sample_page_image, fake_detector):
    page_id, job_id = await _make_page(client, sample_page_image)
    fake_detector(raises=SoftTimeLimitExceeded())

    result = run_detect_job(job_id)

    assert result["status"] == "failed"
    assert "timeout" in result["error"]
    page, regions = _db_counts(page_id)
    assert page.status is PageStatus.detection_failed
    assert regions == []
    with sync_session() as s:
        job = s.get(Job, uuid.UUID(job_id))
        assert job.status is JobStatus.failed
        assert "timeout" in job.error_log


async def test_loi_thieu_weight_ghi_ro_nguyen_nhan(client, sample_page_image, fake_detector):
    page_id, job_id = await _make_page(client, sample_page_image)
    fake_detector(raises=FileNotFoundError("Không thấy model weight tại '/models/x.onnx'"))

    result = run_detect_job(job_id)

    assert result["status"] == "failed"
    with sync_session() as s:
        job = s.get(Job, uuid.UUID(job_id))
        assert job.status is JobStatus.failed
        assert "FileNotFoundError" in job.error_log
        assert s.get(Page, uuid.UUID(page_id)).status is PageStatus.detection_failed


async def test_job_khong_ton_tai_khong_lam_worker_chet(fake_detector):
    fake_detector(regions=[])
    result = run_detect_job(str(uuid.uuid4()))
    assert result["status"] == "job_not_found"


async def test_endpoint_regions_tra_du_lieu_that_sau_khi_detect(
    client, sample_page_image, fake_detector
):
    page_id, job_id = await _make_page(client, sample_page_image)
    fake_detector(regions=[_region(12, 34, 100, 50, 0.9), _region(400, 400, 80, 40, 0.4)])
    run_detect_job(job_id)

    r = await client.get(f"/api/v1/pages/{page_id}/regions")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    first = next(b for b in body if b["bbox"]["x"] == 12)
    assert first["bbox"] == {"x": 12, "y": 34, "w": 100, "h": 50}
    assert first["confidence"] == pytest.approx(0.9)
    assert {b["status"] for b in body} == {"pending", "low_confidence"}


async def test_detect_chay_lai_tren_page_da_detected(client, sample_page_image, fake_detector):
    """REGRESSION: state machine cho phép detected -> detecting -> detected khi chạy lại."""
    page_id, job_id = await _make_page(client, sample_page_image)
    fake_detector(regions=[_region(10, 10, 50, 50, 0.9)])
    run_detect_job(job_id)

    retry = await client.post(f"/api/v1/pages/{page_id}/retry-detect")
    assert retry.status_code == 202
    new_job = retry.json()["job_id"]
    assert new_job != job_id

    result = run_detect_job(new_job)
    assert result["status"] == "done"
    page, regions = _db_counts(page_id)
    assert page.status is PageStatus.detected
    assert len(regions) == 1


async def test_upload_tra_202_ngay_khong_cho_detect_chay_xong(
    client, sample_page_image, fake_detector, monkeypatch
):
    """GUARDRAIL: detect KHÔNG được chạy đồng bộ trong API handler."""

    class _SlowDetector:
        conf_threshold = 0.5

        def detect_regions(self, image_path):
            time.sleep(5)
            return []

    from app.workers import tasks

    tasks._detector = _SlowDetector()

    proj = await client.post(
        "/api/v1/projects",
        json={"name": "M2", "source_lang": "ja", "intended_use": "personal"},
    )
    started = time.perf_counter()
    up = await client.post(
        f"/api/v1/projects/{proj.json()['id']}/pages",
        files={"file": ("p.png", sample_page_image, "image/png")},
    )
    elapsed = time.perf_counter() - started

    assert up.status_code == 202
    assert elapsed < 2.0, f"upload mất {elapsed:.1f}s — nghi ngờ detect chạy đồng bộ"
    page = await client.get(f"/api/v1/pages/{up.json()['page_id']}")
    assert page.json()["status"] == "queued"  # vẫn ở hàng đợi, chưa detect


async def test_broker_chet_thi_van_nhan_anh_va_ghi_ro_ly_do(
    client, sample_page_image, monkeypatch
):
    """Không giả vờ đã gửi job khi broker hỏng — ghi error_log, job vẫn ở queued."""
    from app.services import dispatch

    def _boom(_job_id):
        raise ConnectionRefusedError("broker unreachable")

    monkeypatch.setattr(dispatch, "run_detect_job", None, raising=False)
    monkeypatch.setattr("app.api.v1.routes.dispatch_detect_job", dispatch.dispatch_detect_job)
    monkeypatch.setattr(
        "app.services.dispatch.dispatch_detect_job",
        lambda job_id: (False, "enqueue_failed: ConnectionRefusedError: broker unreachable"),
    )
    monkeypatch.setattr(
        "app.api.v1.routes.dispatch_detect_job",
        lambda job_id: (False, "enqueue_failed: ConnectionRefusedError: broker unreachable"),
    )

    proj = await client.post(
        "/api/v1/projects",
        json={"name": "M2", "source_lang": "ja", "intended_use": "personal"},
    )
    up = await client.post(
        f"/api/v1/projects/{proj.json()['id']}/pages",
        files={"file": ("p.png", sample_page_image, "image/png")},
    )
    assert up.status_code == 202

    job = await client.get(f"/api/v1/jobs/{up.json()['job_id']}")
    assert job.json()["status"] == "queued"
    assert "enqueue_failed" in (job.json()["error_log"] or "")
