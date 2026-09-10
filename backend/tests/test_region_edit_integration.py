"""Integration — sửa tay từng vùng (M7): PATCH region, re-fit, re-OCR, dịch lại."""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from PIL import Image

from app.core.db_sync import sync_session
from app.models import Job, OCRResult, Page, TextRegion, TranslationResult, TypesetResult
from app.models.enums import FitStatus, JobStatus, JobType, OCREngine, PageStatus
from app.services.detect.ctd import DetectedRegion
from app.services.interfaces import BBox
from app.services.typeset.paths import preview_relative_path
from app.workers.tasks import (
    run_detect_job,
    run_inpaint_job,
    run_ocr_job,
    run_refit_job,
    run_region_reocr_job,
    run_region_retranslate_job,
    run_translate_job,
    run_typeset_job,
)


def _region(x, y, w=200.0, h=80.0) -> DetectedRegion:
    return DetectedRegion(bbox=BBox(x=x, y=y, w=w, h=h), confidence=0.9, cls=0)


def _job_id(page_id: str, job_type: JobType) -> str:
    with sync_session() as s:
        job = s.execute(
            sa.select(Job)
            .where(Job.page_id == uuid.UUID(page_id), Job.type == job_type)
            .order_by(Job.created_at.desc())
        ).scalars().first()
        return str(job.id) if job else ""


def _regions(page_id: str) -> list[TextRegion]:
    with sync_session() as s:
        return list(
            s.execute(
                sa.select(TextRegion)
                .where(TextRegion.page_id == uuid.UUID(page_id))
                .order_by(TextRegion.reading_order)
            ).scalars()
        )


def _typeset(region_id) -> TypesetResult | None:
    with sync_session() as s:
        return s.execute(
            sa.select(TypesetResult).where(TypesetResult.region_id == region_id)
        ).scalars().first()


def _translation(region_id) -> TranslationResult | None:
    with sync_session() as s:
        return s.execute(
            sa.select(TranslationResult).where(TranslationResult.region_id == region_id)
        ).scalars().first()


def _md5(path) -> str:
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


@pytest.fixture
def trang_da_canh_chu(client, sample_page_image, fake_detector, fake_ocr_engine,
                      fake_inpainter, fake_translator, no_broker_for_chained_ocr):
    """Đưa 1 trang đi hết pipeline M2→M6, trả page_id."""
    async def _go(texts=None):
        proj = await client.post(
            "/api/v1/projects",
            json={"name": "M7", "source_lang": "en", "intended_use": "study"},
        )
        up = await client.post(
            f"/api/v1/projects/{proj.json()['id']}/pages",
            files={"file": ("p.png", sample_page_image, "image/png")},
        )
        page_id = up.json()["page_id"]
        fake_detector(regions=[_region(100, 120), _region(700, 1000)])
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
        run_typeset_job(_job_id(page_id, JobType.typeset))
        return page_id
    return _go


# ---------------- GET /pages/{id}/detail ----------------


async def test_detail_gom_du_moi_thu_cho_man_sua_tay(client, trang_da_canh_chu):
    page_id = await trang_da_canh_chu()
    r = await client.get(f"/api/v1/pages/{page_id}/detail")
    assert r.status_code == 200
    body = r.json()
    assert body["page"]["id"] == page_id
    assert body["preview_url"].endswith("/typeset-preview")
    assert "Bangers" in body["font_families"]
    assert body["min_font_size"] < body["max_font_size"]
    assert len(body["regions"]) == 2
    vung = body["regions"][0]
    for truong in ("bbox", "raw_text", "translated_text", "font_family", "font_size",
                   "fit_status", "typeset_edited_by_user", "translation_edited_by_user",
                   "ocr_status", "confidence", "overlap_suspect", "reading_order"):
        assert truong in vung, truong
    assert vung["raw_text"] == "HELLO"
    assert vung["typeset_edited_by_user"] is False, "kết quả tự động KHÔNG được đánh dấu sửa tay"


async def test_detail_khong_tra_link_preview_chet(client, sample_page_image, fake_detector,
                                                   no_broker_for_chained_ocr):
    proj = await client.post("/api/v1/projects",
                             json={"name": "M7", "source_lang": "en", "intended_use": "study"})
    up = await client.post(f"/api/v1/projects/{proj.json()['id']}/pages",
                           files={"file": ("p.png", sample_page_image, "image/png")})
    r = await client.get(f"/api/v1/pages/{up.json()['page_id']}/detail")
    assert r.status_code == 200 and r.json()["preview_url"] is None


async def test_detail_page_khong_ton_tai_tra_404(client):
    assert (await client.get(f"/api/v1/pages/{uuid.uuid4()}/detail")).status_code == 404


# ---------------- PATCH /regions/{id} ----------------


async def test_sua_text_ghi_dung_va_xep_viec_canh_lai(client, trang_da_canh_chu):
    page_id = await trang_da_canh_chu()
    vung = _regions(page_id)[0]
    r = await client.patch(f"/api/v1/regions/{vung.id}",
                           json={"translated_text": "Chào cậu nhé!"})
    assert r.status_code == 200
    body = r.json()
    assert body["region_id"] == str(vung.id)
    assert body["edited_fields"] == ["translated_text"]
    assert body["fit_status"] == "pending", "bản canh cũ không còn đúng ⇒ phải là pending"
    assert body["refit_job_id"]

    assert _translation(vung.id).translated_text == "Chào cậu nhé!"
    assert _translation(vung.id).edited_by_user is True


async def test_sua_bbox_ghi_dung_khung_moi(client, trang_da_canh_chu):
    page_id = await trang_da_canh_chu()
    vung = _regions(page_id)[0]
    r = await client.patch(f"/api/v1/regions/{vung.id}",
                           json={"bbox": {"x": 50, "y": 60, "w": 300, "h": 150}})
    assert r.status_code == 200 and r.json()["edited_fields"] == ["bbox"]
    sau = _regions(page_id)[0]
    assert (sau.bbox_x, sau.bbox_y, sau.bbox_w, sau.bbox_h) == (50.0, 60.0, 300.0, 150.0)


async def test_sua_font_va_co_chu(client, trang_da_canh_chu):
    page_id = await trang_da_canh_chu()
    vung = _regions(page_id)[0]
    r = await client.patch(f"/api/v1/regions/{vung.id}",
                           json={"font_family": "Mansalva", "font_size": 18})
    assert r.status_code == 200
    assert set(r.json()["edited_fields"]) == {"font_family", "font_size"}
    assert _typeset(vung.id).font_family == "Mansalva"


async def test_font_ngoai_whitelist_bi_tu_choi(client, trang_da_canh_chu):
    page_id = await trang_da_canh_chu()
    vung = _regions(page_id)[0]
    r = await client.patch(f"/api/v1/regions/{vung.id}", json={"font_family": "ComicSansGiaMao"})
    assert r.status_code == 422 and "font_not_found" in r.text


async def test_patch_rong_bi_tu_choi(client, trang_da_canh_chu):
    page_id = await trang_da_canh_chu()
    vung = _regions(page_id)[0]
    assert (await client.patch(f"/api/v1/regions/{vung.id}", json={})).status_code == 422


@pytest.mark.parametrize("body", [
    {"bbox": {"x": 0, "y": 0, "w": 0, "h": 10}},
    {"bbox": {"x": -5, "y": 0, "w": 10, "h": 10}},
    {"font_size": 0},
    {"truong_la": 1},
])
async def test_du_lieu_sai_bi_chan_o_tang_schema(client, trang_da_canh_chu, body):
    page_id = await trang_da_canh_chu()
    vung = _regions(page_id)[0]
    assert (await client.patch(f"/api/v1/regions/{vung.id}", json=body)).status_code == 422


async def test_patch_vung_khong_ton_tai_tra_404(client):
    r = await client.patch(f"/api/v1/regions/{uuid.uuid4()}", json={"translated_text": "x"})
    assert r.status_code == 404


async def test_patch_chi_xep_mot_viec_khong_canh_lai_ca_trang(client, trang_da_canh_chu):
    """Sửa 1 vùng chỉ được tạo 1 job — không kéo theo canh lại cả trang."""
    page_id = await trang_da_canh_chu()
    with sync_session() as s:
        truoc = s.execute(
            sa.select(sa.func.count()).select_from(Job)
            .where(Job.page_id == uuid.UUID(page_id), Job.type == JobType.typeset)
        ).scalar()
    await client.patch(f"/api/v1/regions/{_regions(page_id)[0].id}",
                       json={"translated_text": "Chào"})
    with sync_session() as s:
        sau = s.execute(
            sa.select(sa.func.count()).select_from(Job)
            .where(Job.page_id == uuid.UUID(page_id), Job.type == JobType.typeset)
        ).scalar()
    assert sau == truoc + 1


# ---------------- task canh lại 1 vùng ----------------


async def test_canh_lai_mot_vung_khong_dung_vung_khac(client, trang_da_canh_chu, storage_root):
    page_id = await trang_da_canh_chu()
    vung_a, vung_b = _regions(page_id)
    truoc_b = _typeset(vung_b.id)
    chup_b = (truoc_b.font_size, truoc_b.wrapped_text, truoc_b.fit_status, truoc_b.edited_by_user)

    r = await client.patch(f"/api/v1/regions/{vung_a.id}", json={"translated_text": "Chào cậu nhé!"})
    run_refit_job(r.json()["refit_job_id"], str(vung_a.id))

    sau_a, sau_b = _typeset(vung_a.id), _typeset(vung_b.id)
    assert sau_a.wrapped_text and "Chào cậu nhé" in sau_a.wrapped_text
    assert sau_a.edited_by_user is True
    assert (sau_b.font_size, sau_b.wrapped_text, sau_b.fit_status, sau_b.edited_by_user) == chup_b, \
        "canh lại 1 vùng đã làm đổi vùng khác"


async def test_canh_lai_khong_tao_ban_trung(client, trang_da_canh_chu):
    page_id = await trang_da_canh_chu()
    vung = _regions(page_id)[0]
    for _ in range(3):
        r = await client.patch(f"/api/v1/regions/{vung.id}", json={"translated_text": "Chào"})
        run_refit_job(r.json()["refit_job_id"], str(vung.id))
    with sync_session() as s:
        dem = s.execute(
            sa.select(sa.func.count()).select_from(TypesetResult)
            .where(TypesetResult.region_id == vung.id)
        ).scalar()
    assert dem == 1


async def test_ghim_co_chu_thi_dung_dung_co_do(client, trang_da_canh_chu):
    page_id = await trang_da_canh_chu()
    vung = _regions(page_id)[0]
    r = await client.patch(f"/api/v1/regions/{vung.id}", json={"font_size": 14})
    ket_qua = run_refit_job(r.json()["refit_job_id"], str(vung.id), 14)
    assert ket_qua["font_size"] == 14.0
    assert ket_qua["pinned_size"] is True
    assert _typeset(vung.id).font_size == 14.0


async def test_ghim_co_qua_lon_thi_bao_tran_khong_gia_vo_vua(client, trang_da_canh_chu):
    """Người dùng ghim cỡ chữ to quá khung ⇒ vẫn dùng cỡ đó nhưng phải nói thật là tràn."""
    page_id = await trang_da_canh_chu()
    vung = _regions(page_id)[0]
    with sync_session() as s:
        row = s.execute(
            sa.select(TranslationResult).where(TranslationResult.region_id == vung.id)
        ).scalars().one()
        row.translated_text = "Một câu thoại dài kinh khủng không tài nào nhét vừa được đâu nhé"
        s.commit()
    r = await client.patch(f"/api/v1/regions/{vung.id}", json={"font_size": 40})
    ket_qua = run_refit_job(r.json()["refit_job_id"], str(vung.id), 40)
    assert ket_qua["fit_status"] == "overflow_warning"
    assert ket_qua["font_size"] == 40.0


async def test_preview_duoc_ve_lai_sau_khi_sua(client, trang_da_canh_chu, storage_root):
    page_id = await trang_da_canh_chu()
    preview = Path(storage_root) / preview_relative_path(uuid.UUID(page_id))
    truoc = _md5(preview)
    vung = _regions(page_id)[0]
    r = await client.patch(f"/api/v1/regions/{vung.id}",
                           json={"translated_text": "Một dòng chữ hoàn toàn khác trước"})
    run_refit_job(r.json()["refit_job_id"], str(vung.id))
    assert _md5(preview) != truoc, "preview không được vẽ lại sau khi sửa"


async def test_sua_vung_khong_dung_anh_goc_va_anh_clean(client, trang_da_canh_chu, storage_root):
    page_id = await trang_da_canh_chu()
    with sync_session() as s:
        page = s.get(Page, uuid.UUID(page_id))
        goc = str(Path(storage_root) / page.image_path)
        clean = str(Path(storage_root) / page.clean_image_path)
    md5_goc, md5_clean = _md5(goc), _md5(clean)

    vung = _regions(page_id)[0]
    r = await client.patch(f"/api/v1/regions/{vung.id}",
                           json={"translated_text": "Chữ mới", "bbox": {"x": 10, "y": 10, "w": 400, "h": 200}})
    run_refit_job(r.json()["refit_job_id"], str(vung.id))

    assert _md5(goc) == md5_goc, "ẢNH GỐC bị đổi — vi phạm nặng"
    assert _md5(clean) == md5_clean, "ảnh clean của M4 bị đổi"


async def test_sua_tay_khong_dung_chu_goc_ocr(client, trang_da_canh_chu):
    """Sửa bản dịch KHÔNG được đụng `raw_text` của M3 — còn phải đối chiếu về sau."""
    page_id = await trang_da_canh_chu()
    vung = _regions(page_id)[0]
    with sync_session() as s:
        truoc = s.execute(
            sa.select(OCRResult).where(OCRResult.region_id == vung.id)
        ).scalars().one().raw_text
    r = await client.patch(f"/api/v1/regions/{vung.id}", json={"translated_text": "Khác hẳn"})
    run_refit_job(r.json()["refit_job_id"], str(vung.id))
    with sync_session() as s:
        sau = s.execute(
            sa.select(OCRResult).where(OCRResult.region_id == vung.id)
        ).scalars().one().raw_text
    assert sau == truoc == "HELLO"


# ---------------- E21: gõ đè raw_text khi OCR đọc sai ----------------


async def test_sua_raw_text_ghi_dung_va_danh_dau_da_sua(client, trang_da_canh_chu):
    """REPORT_E20a/E20b: chữ mảnh trên nền bận không path OCR nào tự sửa được — lối thoát duy
    nhất là người dùng tự gõ đè. Sửa raw_text KHÔNG được đụng translated_text (chưa ai bảo dịch
    lại) — bản dịch cũ dựa trên chữ sai vẫn còn nguyên tới khi bấm "Dịch lại" tay."""
    page_id = await trang_da_canh_chu()
    vung = _regions(page_id)[0]
    with sync_session() as s:
        dich_truoc = s.execute(
            sa.select(TranslationResult).where(TranslationResult.region_id == vung.id)
        ).scalars().one().translated_text

    r = await client.patch(f"/api/v1/regions/{vung.id}", json={"raw_text": "HELLO THERE"})
    assert r.status_code == 200, r.text
    assert r.json()["edited_fields"] == ["raw_text"]

    with sync_session() as s:
        ocr = s.execute(
            sa.select(OCRResult).where(OCRResult.region_id == vung.id)
        ).scalars().one()
        assert ocr.raw_text == "HELLO THERE"
        assert ocr.edited_by_user is True
        dich_sau = s.execute(
            sa.select(TranslationResult).where(TranslationResult.region_id == vung.id)
        ).scalars().one().translated_text
    assert dich_sau == dich_truoc  # KHÔNG tự dịch lại


async def test_sua_raw_text_vung_chua_ocr_bao_loi_ro(client, trang_da_canh_chu):
    page_id = await trang_da_canh_chu()
    vung = _regions(page_id)[0]
    with sync_session() as s:
        s.execute(sa.delete(OCRResult).where(OCRResult.region_id == vung.id))
        s.commit()
    r = await client.patch(f"/api/v1/regions/{vung.id}", json={"raw_text": "abc"})
    assert r.status_code == 409
    assert "chưa đọc chữ" in r.json()["detail"]


# ---------------- E21b: chỉ canh lại khi lượt sửa thật sự đổi bản vẽ ----------------


def _dem_job_typeset(page_id: str) -> int:
    with sync_session() as s:
        return len(s.execute(
            sa.select(Job).where(
                Job.page_id == uuid.UUID(page_id), Job.type == JobType.typeset,
            )
        ).scalars().all())


def _typeset_cua(region_id) -> TypesetResult:
    with sync_session() as s:
        return s.execute(
            sa.select(TypesetResult).where(TypesetResult.region_id == region_id)
        ).scalars().one()


async def test_sua_raw_text_KHONG_xep_viec_canh_lai(client, trang_da_canh_chu):
    """Chữ được VẼ vào bong bóng là bản dịch, không phải chữ gốc OCR — nên sửa `raw_text` không
    làm bản vẽ khác đi một pixel nào.

    Trước E21b, mỗi lượt sửa chữ gốc vẫn xếp một việc canh lại: chiếm mất một suất của worker
    `--pool=solo` (mỗi lúc đúng một việc, `REPORT_E22`) cho một việc vẽ lại y hệt cái đang có, và
    hạ `fit_status` đang `fit_ok` xuống `pending` không vì lý do gì. Test E21 cũ chỉ khoá "không
    tự DỊCH lại" nên tác dụng phụ này lọt qua.
    """
    page_id = await trang_da_canh_chu()
    vung = _regions(page_id)[0]
    truoc = _typeset_cua(vung.id)
    fit_truoc, sua_tay_truoc = truoc.fit_status, truoc.edited_by_user
    so_job_truoc = _dem_job_typeset(page_id)

    r = await client.patch(f"/api/v1/regions/{vung.id}", json={"raw_text": "HELLO THERE"})
    assert r.status_code == 200, r.text
    js = r.json()

    assert js["refit_job_id"] is None, "vẫn xếp việc canh lại cho một lượt sửa không đổi bản vẽ"
    assert _dem_job_typeset(page_id) == so_job_truoc, "đã tạo thêm job typeset"

    sau = _typeset_cua(vung.id)
    assert sau.fit_status is fit_truoc, "hạ nhầm trạng thái canh chữ dù không canh lại"
    assert js["fit_status"] == fit_truoc.value, "API trả `pending` dù không có gì để canh"
    assert sau.edited_by_user is sua_tay_truoc, \
        "gắn nhầm 'người sửa' lên tầng typeset — người dùng chỉ sửa chữ gốc OCR"

    # Phần sửa vẫn phải được ghi thật (trước đây nó được commit ké theo job).
    with sync_session() as s:
        assert s.execute(
            sa.select(OCRResult).where(OCRResult.region_id == vung.id)
        ).scalars().one().raw_text == "HELLO THERE"


@pytest.mark.parametrize("truong,gia_tri", [
    ("translated_text", "Xin chào"),
    ("bbox", {"x": 10.0, "y": 12.0, "w": 150.0, "h": 60.0}),
])
async def test_sua_thu_doi_ban_ve_VAN_xep_viec_canh_lai(
    client, trang_da_canh_chu, truong, gia_tri,
):
    """Chốt ranh giới từ phía ngược lại: E21b chỉ được bỏ việc canh lại cho ĐÚNG trường hợp
    `raw_text`. Bản dịch và khung chữ vẫn phải canh lại như cũ, nếu không thì bản vẽ trên trang
    sẽ lệch hẳn với dữ liệu."""
    page_id = await trang_da_canh_chu()
    vung = _regions(page_id)[0]
    so_job_truoc = _dem_job_typeset(page_id)

    r = await client.patch(f"/api/v1/regions/{vung.id}", json={truong: gia_tri})
    assert r.status_code == 200, r.text
    js = r.json()

    assert js["refit_job_id"] is not None, f"sửa {truong} mà không xếp việc canh lại"
    assert _dem_job_typeset(page_id) == so_job_truoc + 1
    assert js["fit_status"] == FitStatus.pending.value


async def test_sua_raw_text_KEM_ban_dich_thi_VAN_canh_lai(client, trang_da_canh_chu):
    """Lượt sửa gộp: có `raw_text` nhưng cũng có `translated_text` ⇒ vẫn phải canh lại. Điều kiện
    là 'có trường nào đổi bản vẽ không', không phải 'có raw_text không'."""
    page_id = await trang_da_canh_chu()
    vung = _regions(page_id)[0]
    so_job_truoc = _dem_job_typeset(page_id)

    r = await client.patch(
        f"/api/v1/regions/{vung.id}",
        json={"raw_text": "SOURCE", "translated_text": "Bản dịch mới"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["refit_job_id"] is not None
    assert _dem_job_typeset(page_id) == so_job_truoc + 1


async def test_detail_tra_dung_co_ocr_edited_by_user(client, trang_da_canh_chu):
    page_id = await trang_da_canh_chu()
    vung = _regions(page_id)[0]

    truoc = await client.get(f"/api/v1/pages/{page_id}/detail")
    assert truoc.json()["regions"][0]["ocr_edited_by_user"] is False

    await client.patch(f"/api/v1/regions/{vung.id}", json={"raw_text": "sửa tay"})
    sau = await client.get(f"/api/v1/pages/{page_id}/detail")
    vung_sau = next(r for r in sau.json()["regions"] if r["id"] == str(vung.id))
    assert vung_sau["ocr_edited_by_user"] is True
    assert vung_sau["raw_text"] == "sửa tay"


async def test_re_ocr_reset_edited_by_user_ve_false(client, trang_da_canh_chu, fake_ocr_engine):
    """Đọc lại chữ gốc từ ảnh (máy đọc) phải xoá cờ 'người tự gõ' — nếu không, dữ liệu sẽ nói dối
    là 'người sửa' trong khi thực ra máy vừa ghi đè lại theo `_run_region_reocr` (xoá-tạo-mới)."""
    page_id = await trang_da_canh_chu()
    vung = _regions(page_id)[0]
    await client.patch(f"/api/v1/regions/{vung.id}", json={"raw_text": "gõ tay"})

    fake_ocr_engine(results=("MÁY ĐỌC LẠI", 0.9), engine_enum=OCREngine.manga_ocr)
    r = await client.post(f"/api/v1/regions/{vung.id}/re-ocr")
    run_region_reocr_job(r.json()["job_id"], str(vung.id))

    with sync_session() as s:
        ocr = s.execute(
            sa.select(OCRResult).where(OCRResult.region_id == vung.id)
        ).scalars().one()
        assert ocr.raw_text == "MÁY ĐỌC LẠI"
        assert ocr.edited_by_user is False


async def test_canh_lai_vung_chua_co_ban_dich_thi_bao_loi_ro(client, trang_da_canh_chu):
    page_id = await trang_da_canh_chu()
    vung = _regions(page_id)[0]
    with sync_session() as s:
        s.execute(sa.delete(TranslationResult).where(TranslationResult.region_id == vung.id))
        s.commit()
    with sync_session() as s:
        job = Job(type=JobType.typeset, page_id=uuid.UUID(page_id), status=JobStatus.queued)
        s.add(job); s.commit(); jid = str(job.id)
    ket_qua = run_refit_job(jid, str(vung.id))
    assert ket_qua["status"] == "failed" and "missing_translation" in ket_qua["error"]


async def test_canh_lai_vung_khong_ton_tai_khong_lam_worker_chet(trang_da_canh_chu, client):
    page_id = await trang_da_canh_chu()
    with sync_session() as s:
        job = Job(type=JobType.typeset, page_id=uuid.UUID(page_id), status=JobStatus.queued)
        s.add(job); s.commit(); jid = str(job.id)
    ket_qua = run_refit_job(jid, str(uuid.uuid4()))
    assert ket_qua["status"] == "failed" and "region_not_found" in ket_qua["error"]


# ---------------- re-OCR / dịch lại theo vùng ----------------


async def test_doc_lai_chu_goc_mot_vung(client, trang_da_canh_chu, fake_ocr_engine):
    page_id = await trang_da_canh_chu()
    vung = _regions(page_id)[0]
    r = await client.post(f"/api/v1/regions/{vung.id}/re-ocr")
    assert r.status_code == 202

    fake_ocr_engine(results=("HELLO THERE", 0.99), engine_enum=OCREngine.manga_ocr)
    ket_qua = run_region_reocr_job(r.json()["job_id"], str(vung.id))
    assert ket_qua["status"] == "done", ket_qua
    assert ket_qua["raw_text"] == "HELLO THERE"
    with sync_session() as s:
        dem = s.execute(
            sa.select(sa.func.count()).select_from(OCRResult)
            .where(OCRResult.region_id == vung.id)
        ).scalar()
    assert dem == 1, "đọc lại không được tạo bản trùng"


async def test_dich_lai_mot_vung(client, trang_da_canh_chu, fake_translator):
    page_id = await trang_da_canh_chu()
    vung = _regions(page_id)[0]
    r = await client.post(f"/api/v1/regions/{vung.id}/re-translate")
    assert r.status_code == 202

    fake_translator(prefix="MỚI:")
    ket_qua = run_region_retranslate_job(r.json()["job_id"], str(vung.id))
    assert ket_qua["status"] == "done"
    assert _translation(vung.id).translated_text == "MỚI:HELLO"
    assert _translation(vung.id).edited_by_user is False, "máy dịch KHÔNG phải người sửa tay"


async def test_dich_lai_khi_chua_co_chu_goc_thi_bao_loi(client, trang_da_canh_chu, fake_translator):
    page_id = await trang_da_canh_chu()
    vung = _regions(page_id)[0]
    with sync_session() as s:
        s.execute(sa.delete(OCRResult).where(OCRResult.region_id == vung.id))
        s.commit()
    r = await client.post(f"/api/v1/regions/{vung.id}/re-translate")
    fake_translator()
    ket_qua = run_region_retranslate_job(r.json()["job_id"], str(vung.id))
    assert ket_qua["status"] == "failed" and "missing_ocr" in ket_qua["error"]


async def test_re_fit_khong_sua_gi(client, trang_da_canh_chu):
    page_id = await trang_da_canh_chu()
    vung = _regions(page_id)[0]
    r = await client.post(f"/api/v1/regions/{vung.id}/re-fit")
    assert r.status_code == 202 and r.json()["status"] == "queued"


@pytest.mark.parametrize("duong_dan", ["re-fit", "re-ocr", "re-translate"])
async def test_endpoint_vung_khong_ton_tai_tra_404(client, duong_dan):
    assert (await client.post(f"/api/v1/regions/{uuid.uuid4()}/{duong_dan}")).status_code == 404


# ---------------- preview không được cache ----------------


async def test_preview_co_header_chong_cache(client, trang_da_canh_chu):
    """Đường dẫn preview cố định ⇒ thiếu header này là người dùng thấy ảnh cũ sau khi sửa."""
    page_id = await trang_da_canh_chu()
    r = await client.get(f"/api/v1/pages/{page_id}/typeset-preview")
    assert r.status_code == 200
    assert "no-cache" in r.headers.get("cache-control", "")
