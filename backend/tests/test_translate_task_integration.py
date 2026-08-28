"""Integration — Celery task dịch trên DB thật (translator giả lập)."""
from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from app.core.db_sync import sync_session
from app.models import Job, Page, TextRegion, TranslationResult
from app.models.enums import (
    JobStatus,
    JobType,
    OCREngine,
    PageStatus,
    TranslationEngine,
    TranslationStatus,
)
from app.services.detect.ctd import DetectedRegion
from app.services.interfaces import BBox
from app.workers.tasks import run_detect_job, run_inpaint_job, run_ocr_job, run_translate_job


def _region(x, y, w=200.0, h=80.0, conf=0.9) -> DetectedRegion:
    return DetectedRegion(bbox=BBox(x=x, y=y, w=w, h=h), confidence=conf, cls=0)


def _job_id(page_id: str, job_type: JobType) -> str:
    with sync_session() as s:
        job = s.execute(
            sa.select(Job)
            .where(Job.page_id == uuid.UUID(page_id), Job.type == job_type)
            .order_by(Job.created_at.desc())
        ).scalars().first()
        return str(job.id) if job else ""


def _rows(page_id: str):
    with sync_session() as s:
        return list(
            s.execute(
                sa.select(TranslationResult, TextRegion)
                .join(TextRegion, TextRegion.id == TranslationResult.region_id)
                .where(TextRegion.page_id == uuid.UUID(page_id))
                .order_by(TextRegion.reading_order)
            ).all()
        )


async def _page_ready_to_translate(
    client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter,
    regions=None, source_lang="ja", ocr_texts=None,
):
    """Đưa page đi hết detect → OCR → inpaint bằng đúng đường thật."""
    proj = await client.post(
        "/api/v1/projects",
        json={"name": "M5", "source_lang": source_lang, "intended_use": "study"},
    )
    up = await client.post(
        f"/api/v1/projects/{proj.json()['id']}/pages",
        files={"file": ("p.png", sample_page_image, "image/png")},
    )
    page_id = up.json()["page_id"]
    fake_detector(regions=regions or [_region(100, 100), _region(700, 100)])
    run_detect_job(up.json()["job_id"])

    texts = ocr_texts or ["TRAI", "PHAI"]
    counter = {"i": 0}

    def _per_call(i, bbox):
        counter["i"] += 1
        return (texts[i % len(texts)], 0.95)

    fake_ocr_engine(per_call=_per_call, engine_enum=OCREngine.manga_ocr)
    run_ocr_job(_job_id(page_id, JobType.ocr))

    fake_inpainter()
    fake_ocr_engine(results=("", None), engine_enum=OCREngine.manga_ocr)  # kiểm chứng: đã xoá sạch
    run_inpaint_job(_job_id(page_id, JobType.inpaint))
    return page_id


async def test_inpaint_xong_tu_dong_xep_viec_dich(
    client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter,
    no_broker_for_chained_ocr,
):
    page_id = await _page_ready_to_translate(
        client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter
    )
    with sync_session() as s:
        jobs = list(
            s.execute(
                sa.select(Job).where(
                    Job.page_id == uuid.UUID(page_id), Job.type == JobType.translate
                )
            ).scalars()
        )
    assert len(jobs) == 1
    assert jobs[0].status is JobStatus.queued


async def test_dich_du_moi_vung_va_ghi_thu_tu_doc(
    client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter, fake_translator
):
    """Manga Nhật: vùng bên PHẢI phải được dịch trước vùng bên TRÁI."""
    page_id = await _page_ready_to_translate(
        client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter,
        source_lang="ja",
    )
    made = fake_translator()
    result = run_translate_job(_job_id(page_id, JobType.translate))

    assert result["status"] == "done", result
    assert result["regions"] == 2
    rows = _rows(page_id)
    assert len(rows) == 2
    # reading_order phải được điền (M1 để NULL, M5 chịu trách nhiệm tính)
    assert [r.TextRegion.reading_order for r in rows] == [1, 2]
    # vùng x=700 (bên phải) đứng trước vì source_lang=ja
    assert rows[0].TextRegion.bbox_x == 700
    # thứ tự text gửi cho engine cũng phải theo thứ tự đọc
    assert made[0].calls[0] == ["PHAI", "TRAI"]
    with sync_session() as s:
        assert s.get(Page, uuid.UUID(page_id)).status is PageStatus.translated


async def test_tieng_anh_doc_trai_truoc(
    client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter, fake_translator
):
    page_id = await _page_ready_to_translate(
        client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter,
        source_lang="en",
    )
    made = fake_translator()
    run_translate_job(_job_id(page_id, JobType.translate))
    assert made[0].calls[0] == ["TRAI", "PHAI"]


async def test_token_cost_chi_ghi_o_mot_dong_de_cong_khong_bi_nhan_ban(
    client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter, fake_translator
):
    page_id = await _page_ready_to_translate(
        client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter
    )
    fake_translator(total_tokens=500)
    run_translate_job(_job_id(page_id, JobType.translate))

    costs = [r.TranslationResult.token_cost for r in _rows(page_id)]
    assert costs.count(500) == 1
    assert costs.count(None) == 1
    assert sum(c for c in costs if c) == 500  # cộng cả bảng ra đúng chi phí thật


async def test_llm_loi_thi_lui_ve_google_va_danh_dau_fallback(
    client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter, fake_translator
):
    """GUARDRAIL: hết quota KHÔNG được trả bản rỗng âm thầm."""
    page_id = await _page_ready_to_translate(
        client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter
    )
    made = fake_translator(raises_for="llm_context")

    result = run_translate_job(_job_id(page_id, JobType.translate), engine="llm_context")

    assert result["status"] == "done", result
    assert result["fallback"] is True
    assert result["engine"] == "google_fast"
    assert [m.engine_name for m in made] == ["llm_context", "google_fast"]
    rows = _rows(page_id)
    assert all(r.TranslationResult.status is TranslationStatus.fallback_used for r in rows)
    assert all(r.TranslationResult.translated_text for r in rows)
    with sync_session() as s:
        job = s.get(Job, uuid.UUID(_job_id(page_id, JobType.translate)))
        assert "fallback_used" in (job.error_log or "")


async def test_dong_model_khong_tra_thi_de_pending_khong_bia(
    client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter, monkeypatch
):
    page_id = await _page_ready_to_translate(
        client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter
    )
    from app.services.translate.engines import UsageStats
    from app.workers import tasks

    class _Half:
        model_name = "fake"
        usage = UsageStats(total_tokens=10)

        def translate(self, texts, source_lang, target_lang):
            return ["CÓ DỊCH", ""]  # model bỏ sót dòng 2

    monkeypatch.setattr(tasks, "build_translator", lambda engine: _Half())
    result = run_translate_job(_job_id(page_id, JobType.translate))

    assert result["empty_lines"] == 1
    statuses = {r.TranslationResult.status for r in _rows(page_id)}
    assert TranslationStatus.pending in statuses
    assert TranslationStatus.ok in statuses


async def test_dich_lai_khong_tao_ban_dich_trung_lap(
    client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter, fake_translator
):
    """REGRESSION: idempotent theo region_id."""
    page_id = await _page_ready_to_translate(
        client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter
    )
    fake_translator()
    job_id = _job_id(page_id, JobType.translate)
    run_translate_job(job_id)
    first = {r.TranslationResult.id for r in _rows(page_id)}
    second_result = run_translate_job(job_id)
    second = {r.TranslationResult.id for r in _rows(page_id)}

    assert len(first) == 2 and len(second) == 2
    assert first.isdisjoint(second)
    assert second_result["replaced_results"] == 2


async def test_loi_giua_chung_thi_page_giu_nguyen_inpainted(
    client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter, monkeypatch
):
    page_id = await _page_ready_to_translate(
        client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter
    )
    from app.workers import tasks

    def _boom(engine):
        raise RuntimeError("API dịch lăn ra chết")

    monkeypatch.setattr(tasks, "build_translator", _boom)
    result = run_translate_job(_job_id(page_id, JobType.translate))

    assert result["status"] == "failed"
    assert "API dịch lăn ra chết" in result["error"]
    with sync_session() as s:
        assert s.get(Page, uuid.UUID(page_id)).status is PageStatus.inpainted
    assert _rows(page_id) == []


async def test_page_chua_xoa_chu_thi_tu_choi_dich(
    client, sample_page_image, fake_detector, fake_ocr_engine, fake_translator
):
    proj = await client.post(
        "/api/v1/projects", json={"name": "M5", "source_lang": "ja", "intended_use": "study"}
    )
    up = await client.post(
        f"/api/v1/projects/{proj.json()['id']}/pages",
        files={"file": ("p.png", sample_page_image, "image/png")},
    )
    page_id = up.json()["page_id"]
    fake_detector(regions=[_region(100, 100)])
    run_detect_job(up.json()["job_id"])

    with sync_session() as s:
        job = Job(type=JobType.translate, page_id=uuid.UUID(page_id), status=JobStatus.queued)
        s.add(job)
        s.commit()
        job_id = str(job.id)

    fake_translator()
    result = run_translate_job(job_id)
    assert result["status"] == "failed"
    assert "precondition_failed" in result["error"]


async def test_job_translate_khong_ton_tai_khong_lam_worker_chet(fake_translator):
    fake_translator()
    assert run_translate_job(str(uuid.uuid4()))["status"] == "job_not_found"


async def test_endpoint_translation_tra_theo_thu_tu_doc(
    client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter, fake_translator
):
    page_id = await _page_ready_to_translate(
        client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter
    )
    before = await client.get(f"/api/v1/pages/{page_id}/translation")
    assert before.status_code == 200 and before.json() == []

    fake_translator(prefix="VI:")
    run_translate_job(_job_id(page_id, JobType.translate))

    after = await client.get(f"/api/v1/pages/{page_id}/translation")
    body = after.json()
    assert len(body) == 2
    assert body[0]["translated_text"] == "VI:PHAI"  # bên phải đọc trước (ja)
    assert body[0]["engine"] == "google_fast"
    assert all(b["edited_by_user"] is False for b in body)


async def test_retry_translate_chon_engine(
    client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter
):
    page_id = await _page_ready_to_translate(
        client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter
    )
    r = await client.post(f"/api/v1/pages/{page_id}/retry-translate?engine=llm_context")
    assert r.status_code == 202
    assert r.json()["job_id"]


async def test_retry_translate_khi_chua_xoa_chu_tra_409(client, sample_page_image):
    proj = await client.post(
        "/api/v1/projects", json={"name": "M5", "source_lang": "ja", "intended_use": "study"}
    )
    up = await client.post(
        f"/api/v1/projects/{proj.json()['id']}/pages",
        files={"file": ("p.png", sample_page_image, "image/png")},
    )
    r = await client.post(f"/api/v1/pages/{up.json()['page_id']}/retry-translate")
    assert r.status_code == 409


async def test_dich_lai_duoc_ca_trang_sau_khi_da_canh_chu(
    client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter,
    fake_translator, no_broker_for_chained_ocr,
):
    """Từ M6, pipeline tự nối chuỗi nên MỌI trang đều kết thúc ở `typeset_done`.

    Lỗi thật do M8 phát hiện: danh sách điều kiện của M5 viết trước khi `typeset_done` trở thành
    trạng thái cuối, nên endpoint dịch lại cả trang trả 409 vĩnh viễn — không trang nào dịch lại được.
    """
    from app.models.enums import PageStatus
    from app.workers.tasks import run_typeset_job

    page_id = await _page_ready_to_translate(
        client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter
    )
    fake_translator(prefix="VI:")
    run_translate_job(_job_id(page_id, JobType.translate))
    run_typeset_job(_job_id(page_id, JobType.typeset))

    with sync_session() as s:
        assert s.get(Page, uuid.UUID(page_id)).status is PageStatus.typeset_done

    r = await client.post(f"/api/v1/pages/{page_id}/retry-translate?engine=google_fast")
    assert r.status_code == 202, f"trang đã canh chữ phải dịch lại được, nhận: {r.text}"

    fake_translator(prefix="MOI:")
    ket_qua = run_translate_job(_job_id(page_id, JobType.translate))
    assert ket_qua["status"] == "done"
    assert all(row.translated_text.startswith("MOI:") for row, _t in _rows(page_id))
