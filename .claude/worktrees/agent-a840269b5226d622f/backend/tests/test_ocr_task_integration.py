"""Integration — Celery task OCR trên DB thật (engine giả lập).

Engine thật (manga-ocr/PaddleOCR) chạy trong container worker, xem tests/test_ocr_real_engine.py.
"""
from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from app.core.db_sync import sync_session
from app.models import Job, OCRResult, Page, TextRegion
from app.models.enums import JobStatus, JobType, OCREngine, OCRStatus, PageStatus, RegionStatus
from app.services.detect.ctd import DetectedRegion
from app.services.interfaces import BBox
from app.workers.tasks import run_detect_job, run_ocr_job


def _region(x, y, w, h, conf) -> DetectedRegion:
    return DetectedRegion(bbox=BBox(x=x, y=y, w=w, h=h), confidence=conf, cls=0)


async def _page_with_regions(client, sample_page_image, fake_detector, regions, source_lang="ja"):
    """Dựng 1 page đã detect xong (dùng lại đúng đường đi thật của M2)."""
    proj = await client.post(
        "/api/v1/projects",
        json={"name": "M3", "source_lang": source_lang, "intended_use": "study"},
    )
    up = await client.post(
        f"/api/v1/projects/{proj.json()['id']}/pages",
        files={"file": ("p.png", sample_page_image, "image/png")},
    )
    fake_detector(regions=regions)
    run_detect_job(up.json()["job_id"])
    return up.json()["page_id"]


def _ocr_job_for(page_id: str) -> str:
    with sync_session() as s:
        job = s.execute(
            sa.select(Job)
            .where(Job.page_id == uuid.UUID(page_id), Job.type == JobType.ocr)
            .order_by(Job.created_at.desc())
        ).scalars().first()
        return str(job.id)


def _ocr_rows(page_id: str):
    with sync_session() as s:
        return list(
            s.execute(
                sa.select(OCRResult)
                .join(TextRegion, TextRegion.id == OCRResult.region_id)
                .where(TextRegion.page_id == uuid.UUID(page_id))
            ).scalars()
        )


async def test_detect_xong_tu_dong_xep_viec_ocr(
    client, sample_page_image, fake_detector, no_broker_for_chained_ocr
):
    """Pipeline tự chảy: detect done -> Job(type=ocr, queued) được tạo và đẩy đi."""
    page_id = await _page_with_regions(
        client, sample_page_image, fake_detector, [_region(10, 10, 100, 50, 0.9)]
    )
    with sync_session() as s:
        jobs = list(
            s.execute(
                sa.select(Job).where(Job.page_id == uuid.UUID(page_id), Job.type == JobType.ocr)
            ).scalars()
        )
    assert len(jobs) == 1
    assert jobs[0].status is JobStatus.queued
    assert no_broker_for_chained_ocr == [str(jobs[0].id)]


async def test_moi_region_deu_co_ocrresult_ke_ca_low_confidence(
    client, sample_page_image, fake_detector, fake_ocr_engine
):
    """GUARDRAIL: region detect điểm thấp KHÔNG bị bỏ qua khi OCR."""
    page_id = await _page_with_regions(
        client,
        sample_page_image,
        fake_detector,
        [_region(10, 10, 100, 50, 0.95), _region(300, 300, 120, 60, 0.20)],
    )
    with sync_session() as s:
        statuses = {
            r.status
            for r in s.execute(
                sa.select(TextRegion).where(TextRegion.page_id == uuid.UUID(page_id))
            ).scalars()
        }
    assert RegionStatus.low_confidence in statuses  # có region điểm thấp thật

    fake = fake_ocr_engine(results=("こんにちは", None))
    result = run_ocr_job(_ocr_job_for(page_id))

    assert result["status"] == "done"
    assert result["regions"] == 2
    assert len(fake.calls) == 2, "region low_confidence bị bỏ qua khi OCR"
    assert len(_ocr_rows(page_id)) == 2
    with sync_session() as s:
        assert s.get(Page, uuid.UUID(page_id)).status is PageStatus.ocr_done


async def test_manga_ocr_ghi_confidence_null_va_status_ok(
    client, sample_page_image, fake_detector, fake_ocr_engine
):
    page_id = await _page_with_regions(
        client, sample_page_image, fake_detector, [_region(10, 10, 100, 50, 0.9)]
    )
    fake_ocr_engine(results=("お早う", None), engine_enum=OCREngine.manga_ocr)
    run_ocr_job(_ocr_job_for(page_id))

    row = _ocr_rows(page_id)[0]
    assert row.raw_text == "お早う"
    assert row.confidence is None  # không bịa số
    assert row.status is OCRStatus.ok
    assert row.ocr_engine is OCREngine.manga_ocr


async def test_text_rong_thi_needs_manual_van_giu_record(
    client, sample_page_image, fake_detector, fake_ocr_engine
):
    page_id = await _page_with_regions(
        client, sample_page_image, fake_detector, [_region(10, 10, 100, 50, 0.9)]
    )
    fake_ocr_engine(results=("   ", None))
    result = run_ocr_job(_ocr_job_for(page_id))

    assert result["needs_manual"] == 1
    rows = _ocr_rows(page_id)
    assert len(rows) == 1, "region OCR rỗng đã bị bỏ mất"
    assert rows[0].status is OCRStatus.needs_manual


async def test_paddle_confidence_thap_thi_needs_manual(
    client, sample_page_image, fake_detector, fake_ocr_engine
):
    page_id = await _page_with_regions(
        client, sample_page_image, fake_detector,
        [_region(10, 10, 100, 50, 0.9), _region(200, 200, 80, 40, 0.9)],
        source_lang="en",
    )
    fake_ocr_engine(
        engine_enum=OCREngine.paddle_ocr,
        per_call=lambda i, bbox: ("HELLO", 0.95) if i == 0 else ("H3LL0", 0.21),
    )
    result = run_ocr_job(_ocr_job_for(page_id))

    assert result["needs_manual"] == 1
    rows = {r.raw_text: r for r in _ocr_rows(page_id)}
    assert rows["HELLO"].status is OCRStatus.ok
    assert rows["H3LL0"].status is OCRStatus.needs_manual
    assert rows["H3LL0"].confidence == pytest.approx(0.21)


async def test_mot_region_loi_khong_giet_ca_trang(
    client, sample_page_image, fake_detector, fake_ocr_engine
):
    page_id = await _page_with_regions(
        client, sample_page_image, fake_detector,
        [_region(10, 10, 100, 50, 0.9), _region(200, 200, 80, 40, 0.9)],
    )

    def _per_call(i, bbox):
        if i == 1:
            raise RuntimeError("vùng crop hỏng")
        return ("OK TEXT", None)

    fake_ocr_engine(per_call=_per_call)
    result = run_ocr_job(_ocr_job_for(page_id))

    assert result["status"] == "done"
    rows = _ocr_rows(page_id)
    assert len(rows) == 2
    assert sum(1 for r in rows if r.status is OCRStatus.needs_manual) == 1


async def test_ocr_lai_khong_tao_ket_qua_trung_lap(
    client, sample_page_image, fake_detector, fake_ocr_engine
):
    """REGRESSION: idempotent theo region_id."""
    page_id = await _page_with_regions(
        client, sample_page_image, fake_detector,
        [_region(10, 10, 100, 50, 0.9), _region(200, 200, 80, 40, 0.9)],
    )
    fake_ocr_engine(results=("テスト", None))
    job_id = _ocr_job_for(page_id)

    run_ocr_job(job_id)
    first = {r.id for r in _ocr_rows(page_id)}
    second_result = run_ocr_job(job_id)
    second = {r.id for r in _ocr_rows(page_id)}

    assert len(first) == 2 and len(second) == 2, "OCR lại đã nhân đôi kết quả"
    assert first.isdisjoint(second)
    assert second_result["replaced_results"] == 2


async def test_ocr_loi_thi_page_giu_nguyen_detected(
    client, sample_page_image, fake_detector, monkeypatch
):
    """REGRESSION: lỗi giữa chừng KHÔNG được đẩy page sang ocr_done."""
    page_id = await _page_with_regions(
        client, sample_page_image, fake_detector, [_region(10, 10, 100, 50, 0.9)]
    )

    def _explode(source_lang):
        raise RuntimeError("model hỏng")

    monkeypatch.setattr("app.workers.tasks.get_ocr_engine_cached", _explode)
    result = run_ocr_job(_ocr_job_for(page_id))

    assert result["status"] == "failed"
    assert "model hỏng" in result["error"]
    with sync_session() as s:
        assert s.get(Page, uuid.UUID(page_id)).status is PageStatus.detected  # KHÔNG nhảy ocr_done
        job = s.get(Job, uuid.UUID(_ocr_job_for(page_id)))
        assert job.status is JobStatus.failed
        assert "model hỏng" in job.error_log
    assert _ocr_rows(page_id) == []


async def test_page_chua_detect_thi_job_ocr_bao_loi_ro(client, sample_page_image, fake_ocr_engine):
    proj = await client.post(
        "/api/v1/projects", json={"name": "M3", "source_lang": "ja", "intended_use": "study"}
    )
    up = await client.post(
        f"/api/v1/projects/{proj.json()['id']}/pages",
        files={"file": ("p.png", sample_page_image, "image/png")},
    )
    with sync_session() as s:
        job = Job(type=JobType.ocr, page_id=uuid.UUID(up.json()["page_id"]), status=JobStatus.queued)
        s.add(job)
        s.commit()
        job_id = str(job.id)

    fake_ocr_engine(results=("x", None))
    result = run_ocr_job(job_id)
    assert result["status"] == "failed"
    assert result["error"] == "no_region"


async def test_job_ocr_khong_ton_tai_khong_lam_worker_chet(fake_ocr_engine):
    fake_ocr_engine(results=("x", None))
    assert run_ocr_job(str(uuid.uuid4()))["status"] == "job_not_found"


async def test_endpoint_ocr_tra_du_lieu_that(
    client, sample_page_image, fake_detector, fake_ocr_engine
):
    page_id = await _page_with_regions(
        client, sample_page_image, fake_detector,
        [_region(10, 10, 100, 50, 0.9), _region(200, 200, 80, 40, 0.9)],
    )

    before = await client.get(f"/api/v1/pages/{page_id}/ocr")
    assert before.status_code == 200 and before.json() == []  # chưa chạy -> không bịa text

    fake_ocr_engine(per_call=lambda i, b: (["こんにちは", "  "][i], None))
    run_ocr_job(_ocr_job_for(page_id))

    after = await client.get(f"/api/v1/pages/{page_id}/ocr")
    body = after.json()
    assert len(body) == 2
    assert {b["status"] for b in body} == {"ok", "needs_manual"}
    assert all(b["ocr_engine"] == "manga_ocr" for b in body)
    assert all(b["confidence"] is None for b in body)


async def test_retry_ocr_endpoint(client, sample_page_image, fake_detector, fake_ocr_engine):
    page_id = await _page_with_regions(
        client, sample_page_image, fake_detector, [_region(10, 10, 100, 50, 0.9)]
    )
    r = await client.post(f"/api/v1/pages/{page_id}/retry-ocr")
    assert r.status_code == 202
    assert r.json()["job_id"]


async def test_retry_ocr_khi_chua_co_region_tra_409(client, sample_page_image):
    proj = await client.post(
        "/api/v1/projects", json={"name": "M3", "source_lang": "ja", "intended_use": "study"}
    )
    up = await client.post(
        f"/api/v1/projects/{proj.json()['id']}/pages",
        files={"file": ("p.png", sample_page_image, "image/png")},
    )
    r = await client.post(f"/api/v1/pages/{up.json()['page_id']}/retry-ocr")
    assert r.status_code == 409


async def test_engine_hong_toan_tap_thi_bao_failed_khong_gia_vo_ocr_done(
    client, sample_page_image, fake_detector, fake_ocr_engine
):
    """GUARDRAIL: engine chết trên MỌI vùng ≠ 'trang này không có chữ'.

    Bug thật gặp lúc live M3: paddlepaddle ném NotImplementedError ở mọi region,
    task cũ ghi 100% needs_manual rồi tự nhận ocr_done — che mất sự cố.
    """
    page_id = await _page_with_regions(
        client, sample_page_image, fake_detector,
        [_region(10, 10, 100, 50, 0.9), _region(200, 200, 80, 40, 0.9)],
        source_lang="en",
    )
    fake_ocr_engine(
        raises=NotImplementedError("ConvertPirAttribute2RuntimeAttribute not support"),
        engine_enum=OCREngine.paddle_ocr,
    )

    result = run_ocr_job(_ocr_job_for(page_id))

    assert result["status"] == "failed"
    assert "toàn bộ" in result["error"]
    assert "ConvertPirAttribute" in result["error"]
    assert _ocr_rows(page_id) == [], "không được ghi kết quả rỗng khi engine hỏng"
    with sync_session() as s:
        assert s.get(Page, uuid.UUID(page_id)).status is PageStatus.detected
        assert s.get(Job, uuid.UUID(_ocr_job_for(page_id))).status is JobStatus.failed


async def test_mot_phan_vung_loi_van_hoan_thanh_binh_thuong(
    client, sample_page_image, fake_detector, fake_ocr_engine
):
    """Ngược lại: chỉ MỘT vùng lỗi thì vẫn chạy tiếp, không kéo cả trang xuống."""
    page_id = await _page_with_regions(
        client, sample_page_image, fake_detector,
        [_region(10, 10, 100, 50, 0.9), _region(200, 200, 80, 40, 0.9)],
    )

    def _per_call(i, bbox):
        if i == 0:
            raise RuntimeError("vùng này hỏng")
        return ("ちゃんと読めた", None)

    fake_ocr_engine(per_call=_per_call)
    result = run_ocr_job(_ocr_job_for(page_id))

    assert result["status"] == "done"
    assert result["needs_manual"] == 1
    with sync_session() as s:
        assert s.get(Page, uuid.UUID(page_id)).status is PageStatus.ocr_done
