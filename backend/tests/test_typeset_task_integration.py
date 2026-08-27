"""Integration — task canh chữ chạy trên DB thật + render preview thật (M6)."""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from PIL import Image

from app.core.db_sync import sync_session
from app.models import Job, Page, TextRegion, TranslationResult, TypesetResult
from app.models.enums import FitStatus, JobStatus, JobType, OCREngine, PageStatus
from app.services.detect.ctd import DetectedRegion
from app.services.interfaces import BBox
from app.services.typeset.paths import preview_relative_path
from app.workers.tasks import (
    run_detect_job,
    run_inpaint_job,
    run_ocr_job,
    run_translate_job,
    run_typeset_job,
)


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


def _typeset_rows(page_id: str):
    with sync_session() as s:
        return list(
            s.execute(
                sa.select(TypesetResult, TextRegion)
                .join(TextRegion, TextRegion.id == TypesetResult.region_id)
                .where(TextRegion.page_id == uuid.UUID(page_id))
                .order_by(TextRegion.reading_order)
            ).all()
        )


def _page(page_id: str) -> Page:
    with sync_session() as s:
        return s.get(Page, uuid.UUID(page_id))


def _md5(path: str) -> str:
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


async def _page_translated(
    client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter, fake_translator,
    regions=None, texts=None,
) -> str:
    """Đưa page đi hết detect → OCR → inpaint → translate bằng đúng đường thật."""
    proj = await client.post(
        "/api/v1/projects",
        json={"name": "M6", "source_lang": "en", "intended_use": "study"},
    )
    up = await client.post(
        f"/api/v1/projects/{proj.json()['id']}/pages",
        files={"file": ("p.png", sample_page_image, "image/png")},
    )
    page_id = up.json()["page_id"]

    fake_detector(regions=regions or [_region(100, 120), _region(700, 1000)])
    run_detect_job(up.json()["job_id"])

    nguon = texts or ["HELLO", "GOODBYE"]
    fake_ocr_engine(per_call=lambda i, bbox: (nguon[i % len(nguon)], 0.95),
                    engine_enum=OCREngine.manga_ocr)
    run_ocr_job(_job_id(page_id, JobType.ocr))

    fake_inpainter()
    fake_ocr_engine(results=("", None), engine_enum=OCREngine.manga_ocr)
    run_inpaint_job(_job_id(page_id, JobType.inpaint))

    fake_translator(prefix="")
    run_translate_job(_job_id(page_id, JobType.translate))
    assert _page(page_id).status is PageStatus.translated
    return page_id


@pytest.fixture
def full_pipeline(client, sample_page_image, fake_detector, fake_ocr_engine,
                  fake_inpainter, fake_translator, no_broker_for_chained_ocr):
    async def _go(**kw):
        return await _page_translated(
            client, sample_page_image, fake_detector, fake_ocr_engine,
            fake_inpainter, fake_translator, **kw,
        )
    return _go


async def test_dich_xong_tu_dong_xep_viec_canh_chu(full_pipeline):
    page_id = await full_pipeline()
    with sync_session() as s:
        jobs = list(s.execute(
            sa.select(Job).where(Job.page_id == uuid.UUID(page_id), Job.type == JobType.typeset)
        ).scalars())
    assert len(jobs) == 1 and jobs[0].status is JobStatus.queued


async def test_moi_vung_co_dung_mot_ket_qua_va_page_thanh_typeset_done(full_pipeline):
    page_id = await full_pipeline()
    ket_qua = run_typeset_job(_job_id(page_id, JobType.typeset))
    assert ket_qua["status"] == "done"
    rows = _typeset_rows(page_id)
    assert len(rows) == 2
    assert {r.region_id for r, _t in rows} == {t.id for _r, t in rows}
    for row, _region in rows:
        assert row.font_family == "Bangers"
        assert row.padding_ratio is not None
        assert row.edited_by_user is False
        assert row.fit_status in (FitStatus.fit_ok, FitStatus.overflow_warning)
    assert _page(page_id).status is PageStatus.typeset_done


async def test_ket_qua_sap_theo_thu_tu_doc(full_pipeline):
    page_id = await full_pipeline()
    run_typeset_job(_job_id(page_id, JobType.typeset))
    rows = _typeset_rows(page_id)
    assert [t.reading_order for _r, t in rows] == [1, 2]


async def test_preview_dung_kich_thuoc_va_khong_dung_anh_goc(full_pipeline, storage_root):
    page_id = await full_pipeline()
    page = _page(page_id)
    goc = str(Path(storage_root) / page.image_path)
    clean = str(Path(storage_root) / page.clean_image_path)
    md5_goc, md5_clean = _md5(goc), _md5(clean)

    run_typeset_job(_job_id(page_id, JobType.typeset))

    preview = Path(storage_root) / preview_relative_path(uuid.UUID(page_id))
    assert preview.is_file(), "phải có ảnh preview"
    with Image.open(preview) as pv, Image.open(clean) as cl:
        assert pv.size == cl.size, "preview phải đúng kích thước ảnh clean"
    assert _md5(goc) == md5_goc, "ẢNH GỐC bị đổi — vi phạm nặng"
    assert _md5(clean) == md5_clean, "ảnh clean của M4 bị đổi"
    # Đường dẫn ảnh trong DB không đổi.
    sau = _page(page_id)
    assert sau.image_path == page.image_path
    assert sau.clean_image_path == page.clean_image_path


async def test_preview_that_su_co_ve_chu_len(full_pipeline, storage_root):
    """Preview phải KHÁC ảnh clean — nếu y hệt nghĩa là không vẽ được chữ nào."""
    page_id = await full_pipeline()
    run_typeset_job(_job_id(page_id, JobType.typeset))
    page = _page(page_id)
    clean = Path(storage_root) / page.clean_image_path
    preview = Path(storage_root) / preview_relative_path(uuid.UUID(page_id))
    assert _md5(str(clean)) != _md5(str(preview))


async def test_chay_lai_khong_tao_ban_trung_va_khong_de_file_rac(full_pipeline, storage_root):
    page_id = await full_pipeline()
    run_typeset_job(_job_id(page_id, JobType.typeset))
    thu_muc = (Path(storage_root) / preview_relative_path(uuid.UUID(page_id))).parent
    truoc_so_ban_ghi = len(_typeset_rows(page_id))
    truoc_so_file = sorted(p.name for p in thu_muc.iterdir())

    for _ in range(2):
        run_typeset_job(_job_id(page_id, JobType.typeset))

    assert len(_typeset_rows(page_id)) == truoc_so_ban_ghi, "chạy lại làm nhân bản kết quả"
    assert sorted(p.name for p in thu_muc.iterdir()) == truoc_so_file, "còn sót file tạm"
    assert not any(p.name.endswith(".tmp.png") for p in thu_muc.iterdir())


async def test_vung_chua_co_ban_dich_thi_pending_khong_phai_overflow(full_pipeline):
    page_id = await full_pipeline()
    with sync_session() as s:  # bắt chước M5 khi model không trả dòng nào
        region = s.execute(
            sa.select(TextRegion).where(TextRegion.page_id == uuid.UUID(page_id))
            .order_by(TextRegion.reading_order)
        ).scalars().first()
        row = s.execute(
            sa.select(TranslationResult).where(TranslationResult.region_id == region.id)
        ).scalars().one()
        row.translated_text = None
        s.commit()

    run_typeset_job(_job_id(page_id, JobType.typeset))
    rows = _typeset_rows(page_id)
    assert rows[0][0].fit_status is FitStatus.pending
    assert rows[0][0].font_size is None


async def test_thieu_ban_dich_cua_mot_vung_thi_tu_choi_canh_chu(full_pipeline, storage_root):
    page_id = await full_pipeline()
    with sync_session() as s:
        region = s.execute(
            sa.select(TextRegion).where(TextRegion.page_id == uuid.UUID(page_id))
        ).scalars().first()
        s.execute(sa.delete(TranslationResult).where(TranslationResult.region_id == region.id))
        s.commit()

    ket_qua = run_typeset_job(_job_id(page_id, JobType.typeset))
    assert ket_qua["status"] == "failed"
    assert "missing_translation" in ket_qua["error"]
    assert _page(page_id).status is PageStatus.translated, "page phải giữ translated để chạy lại"
    assert not (Path(storage_root) / preview_relative_path(uuid.UUID(page_id))).exists()


async def test_thieu_font_thi_job_failed_va_khong_co_preview_nua_voi(
    full_pipeline, storage_root, monkeypatch
):
    page_id = await full_pipeline()
    from app.workers import tasks

    monkeypatch.setattr(tasks.settings, "font_dir", "/duong-dan-khong-ton-tai")
    ket_qua = run_typeset_job(_job_id(page_id, JobType.typeset))
    assert ket_qua["status"] == "failed"
    assert "font_not_found" in ket_qua["error"]
    assert _page(page_id).status is PageStatus.translated
    assert not (Path(storage_root) / preview_relative_path(uuid.UUID(page_id))).exists()


async def test_page_chua_dich_thi_tu_choi(client, sample_page_image, fake_detector,
                                          fake_ocr_engine, no_broker_for_chained_ocr):
    proj = await client.post("/api/v1/projects",
                             json={"name": "M6", "source_lang": "en", "intended_use": "study"})
    up = await client.post(f"/api/v1/projects/{proj.json()['id']}/pages",
                           files={"file": ("p.png", sample_page_image, "image/png")})
    page_id = up.json()["page_id"]
    fake_detector(regions=[_region(100, 120)])
    run_detect_job(up.json()["job_id"])

    with sync_session() as s:
        job = Job(type=JobType.typeset, page_id=uuid.UUID(page_id), status=JobStatus.queued)
        s.add(job); s.commit(); jid = str(job.id)
    ket_qua = run_typeset_job(jid)
    assert ket_qua["status"] == "failed"
    assert "precondition_failed" in ket_qua["error"]


async def test_job_typeset_khong_ton_tai_khong_lam_worker_chet():
    assert run_typeset_job(str(uuid.uuid4()))["status"] == "job_not_found"


async def test_endpoint_typeset_tra_du_field(client, full_pipeline):
    page_id = await full_pipeline()
    run_typeset_job(_job_id(page_id, JobType.typeset))
    r = await client.get(f"/api/v1/pages/{page_id}/typeset")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    for item in body:
        assert set(item) == {
            "region_id", "font_family", "font_size", "wrapped_text",
            "padding_ratio", "fit_status", "edited_by_user",
        }


async def test_endpoint_typeset_chua_chay_tra_rong(client, full_pipeline):
    page_id = await full_pipeline()
    r = await client.get(f"/api/v1/pages/{page_id}/typeset")
    assert r.status_code == 200 and r.json() == []


async def test_endpoint_preview_tra_anh_va_404_khi_chua_render(client, full_pipeline):
    page_id = await full_pipeline()
    chua = await client.get(f"/api/v1/pages/{page_id}/typeset-preview")
    assert chua.status_code == 404

    run_typeset_job(_job_id(page_id, JobType.typeset))
    r = await client.get(f"/api/v1/pages/{page_id}/typeset-preview")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    import io
    with Image.open(io.BytesIO(r.content)) as im:
        assert im.size[0] > 0


async def test_retry_typeset_tra_202(client, full_pipeline):
    page_id = await full_pipeline()
    r = await client.post(f"/api/v1/pages/{page_id}/retry-typeset")
    assert r.status_code == 202
    assert r.json()["page_id"] == page_id


async def test_retry_typeset_khi_chua_dich_tra_409(client, sample_page_image, fake_detector,
                                                   no_broker_for_chained_ocr):
    proj = await client.post("/api/v1/projects",
                             json={"name": "M6", "source_lang": "en", "intended_use": "study"})
    up = await client.post(f"/api/v1/projects/{proj.json()['id']}/pages",
                           files={"file": ("p.png", sample_page_image, "image/png")})
    r = await client.post(f"/api/v1/pages/{up.json()['page_id']}/retry-typeset")
    assert r.status_code == 409


async def test_khong_dung_toi_du_lieu_cua_m2_m5(full_pipeline):
    """M6 chỉ ĐỌC kết quả các bước trước — không được sửa bản dịch/OCR/thứ tự đọc."""
    page_id = await full_pipeline()
    with sync_session() as s:
        truoc = [
            (t.id, t.reading_order, t.bbox_x, t.bbox_y, tr.translated_text, tr.token_cost)
            for t, tr in s.execute(
                sa.select(TextRegion, TranslationResult)
                .join(TranslationResult, TranslationResult.region_id == TextRegion.id)
                .where(TextRegion.page_id == uuid.UUID(page_id))
                .order_by(TextRegion.reading_order)
            ).all()
        ]
    run_typeset_job(_job_id(page_id, JobType.typeset))
    with sync_session() as s:
        sau = [
            (t.id, t.reading_order, t.bbox_x, t.bbox_y, tr.translated_text, tr.token_cost)
            for t, tr in s.execute(
                sa.select(TextRegion, TranslationResult)
                .join(TranslationResult, TranslationResult.region_id == TextRegion.id)
                .where(TextRegion.page_id == uuid.UUID(page_id))
                .order_by(TextRegion.reading_order)
            ).all()
        ]
    assert sau == truoc
