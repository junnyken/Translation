"""Integration — cổng chất lượng chạy trên DB thật (E12)."""
from __future__ import annotations

import uuid

import sqlalchemy as sa

from app.core.db_sync import sync_session
from app.models import (
    OCRResult,
    RegionQualityAssessment,
    TextRegion,
    TranslationResult,
    TypesetResult,
)
from app.models.enums import (
    FitStatus,
    JobType,
    OCRStatus,
    OverallBand,
    RegionStatus,
    ReviewStatus,
)
from app.services.quality.gate import QualityGateService
from app.workers.tasks import run_typeset_job

from tests.test_export_integration import chapter, _job_id  # noqa: F401 - dùng lại fixture M8


def _vung(page_id: str) -> list[TextRegion]:
    with sync_session() as s:
        return list(s.execute(
            sa.select(TextRegion).where(TextRegion.page_id == uuid.UUID(page_id))
            .order_by(TextRegion.reading_order.nulls_last(), TextRegion.bbox_y)
        ).scalars())


def _danh_gia(page_id: str) -> list[RegionQualityAssessment]:
    with sync_session() as s:
        return list(s.execute(
            sa.select(RegionQualityAssessment)
            .join(TextRegion, TextRegion.id == RegionQualityAssessment.region_id)
            .where(TextRegion.page_id == uuid.UUID(page_id))
        ).scalars())


# ---------------- chấm tự động sau khi căn chữ ----------------


async def test_can_chu_xong_la_tu_cham_moi_vung(client, chapter):
    """Không phải bấm nút nào: căn chữ xong là có đánh giá."""
    _, page_ids = await chapter(so_trang=1)
    ds = _danh_gia(page_ids[0])
    assert len(ds) == len(_vung(page_ids[0])) > 0
    assert {d.assessment_version for d in ds} == {"e12-rules-v1"}


async def test_cham_lai_KHONG_tao_ban_ghi_trung(client, chapter):
    _, page_ids = await chapter(so_trang=1)
    truoc = len(_danh_gia(page_ids[0]))
    QualityGateService().assess_page(uuid.UUID(page_ids[0]), trigger="thu-lai")
    QualityGateService().assess_page(uuid.UUID(page_ids[0]), trigger="thu-lai-nua")
    assert len(_danh_gia(page_ids[0])) == truoc


async def test_khong_sua_gi_cua_M2_M6(client, chapter):
    """E12 chỉ ĐỌC. Sửa dữ liệu của bước khác là phá nguyên tắc lớn nhất của nó."""
    _, page_ids = await chapter(so_trang=1)
    with sync_session() as s:
        truoc = [
            (str(r.id), r.bbox_x, r.bbox_w, r.status,
             (s.execute(sa.select(OCRResult.raw_text).where(
                 OCRResult.region_id == r.id)).scalars().first()),
             (s.execute(sa.select(TranslationResult.translated_text).where(
                 TranslationResult.region_id == r.id)).scalars().first()))
            for r in _vung(page_ids[0])
        ]
    QualityGateService().assess_page(uuid.UUID(page_ids[0]))
    with sync_session() as s:
        sau = [
            (str(r.id), r.bbox_x, r.bbox_w, r.status,
             (s.execute(sa.select(OCRResult.raw_text).where(
                 OCRResult.region_id == r.id)).scalars().first()),
             (s.execute(sa.select(TranslationResult.translated_text).where(
                 TranslationResult.region_id == r.id)).scalars().first()))
            for r in _vung(page_ids[0])
        ]
    assert truoc == sau


# ---------------- API ----------------


async def test_api_tra_danh_gia_theo_thu_tu_doc_kem_cau_tieng_viet(client, chapter):
    _, page_ids = await chapter(so_trang=1)
    r = await client.get(f"/api/v1/pages/{page_ids[0]}/quality")
    assert r.status_code == 200
    body = r.json()
    assert body["assessment_version"] == "e12-rules-v1"
    assert body["summary"]["tong_vung"] == len(_vung(page_ids[0]))
    thu_tu = [v["reading_order"] for v in body["regions"] if v["reading_order"] is not None]
    assert thu_tu == sorted(thu_tu)
    for v in body["regions"]:
        for ly_do in v["ly_do"]:
            assert ly_do["nhan"] and not ly_do["nhan"].startswith("Dấu hiệu chưa có mô tả")


async def test_api_tom_tat_ca_chapter_khop_voi_DB(client, chapter):
    project_id, page_ids = await chapter(so_trang=2)
    r = await client.get(f"/api/v1/projects/{project_id}/quality-summary")
    assert r.status_code == 200
    body = r.json()
    tong_that = sum(len(_vung(p)) for p in page_ids)
    assert body["tong_vung"] == tong_that
    assert (body["ro_rang"] + body["can_ra_soat"] + body["chua_danh_gia"]
            + body["da_bo_qua"]) == tong_that


async def test_api_trang_khong_ton_tai_tra_404(client):
    assert (await client.get(f"/api/v1/pages/{uuid.uuid4()}/quality")).status_code == 404
    assert (await client.get(
        f"/api/v1/projects/{uuid.uuid4()}/quality-summary")).status_code == 404


# ---------------- quyết định của người dùng ----------------


async def test_nguoi_dung_bo_qua_mot_vung_thi_du_lieu_van_con_nguyen(client, chapter):
    """"Bỏ qua" là quyết định, KHÔNG phải xoá."""
    _, page_ids = await chapter(so_trang=1)
    vung = _vung(page_ids[0])[0]
    with sync_session() as s:
        chu_goc = s.execute(sa.select(OCRResult.raw_text).where(
            OCRResult.region_id == vung.id)).scalars().first()

    r = await client.post(f"/api/v1/regions/{vung.id}/quality-review", json={"decision": "skip"})
    assert r.status_code == 200
    assert r.json()["review_status"] == "reviewed_skip"

    with sync_session() as s:
        assert s.get(TextRegion, vung.id) is not None
        assert s.execute(sa.select(OCRResult.raw_text).where(
            OCRResult.region_id == vung.id)).scalars().first() == chu_goc
        assert s.execute(sa.select(TypesetResult).where(
            TypesetResult.region_id == vung.id)).scalars().first() is not None


async def test_may_khach_khong_duoc_tu_dat_muc_hay_ma_ly_do(client, chapter):
    _, page_ids = await chapter(so_trang=1)
    vung = _vung(page_ids[0])[0]
    for than in ({"decision": "skip", "overall_band": "clear"},
                 {"decision": "xoa"},
                 {"reason_codes": []}):
        r = await client.post(f"/api/v1/regions/{vung.id}/quality-review", json=than)
        assert r.status_code == 422, than


async def test_quyet_dinh_cua_nguoi_song_qua_lan_cham_lai(client, chapter):
    """Chấm lại mà xoá mất quyết định của người là mất công họ đã bỏ ra."""
    _, page_ids = await chapter(so_trang=1)
    vung = _vung(page_ids[0])[0]
    await client.post(f"/api/v1/regions/{vung.id}/quality-review", json={"decision": "skip"})
    QualityGateService().assess_page(uuid.UUID(page_ids[0]), trigger="cham-lai")
    with sync_session() as s:
        dg = s.execute(sa.select(RegionQualityAssessment).where(
            RegionQualityAssessment.region_id == vung.id)).scalars().first()
        assert dg.review_status is ReviewStatus.reviewed_skip


async def test_vung_chua_duoc_cham_thi_tu_choi_ghi_quyet_dinh(client, chapter):
    _, page_ids = await chapter(so_trang=1)
    vung = _vung(page_ids[0])[0]
    with sync_session() as s:
        s.execute(sa.delete(RegionQualityAssessment).where(
            RegionQualityAssessment.region_id == vung.id))
        s.commit()
    r = await client.post(f"/api/v1/regions/{vung.id}/quality-review", json={"decision": "keep"})
    assert r.status_code == 409


# ---------------- nối vào cổng xuất của M8/M10 ----------------


async def test_canh_bao_xuat_co_du_ba_so_cua_E12(client, chapter):
    project_id, page_ids = await chapter(so_trang=1)
    vung = _vung(page_ids[0])[0]
    await client.post(f"/api/v1/regions/{vung.id}/quality-review", json={"decision": "skip"})

    body = (await client.get(f"/api/v1/projects/{project_id}/export-warnings")).json()
    for khoa in ("quality_needs_review_count", "quality_unassessed_count",
                 "quality_reviewed_skip_count", "overflow_warning_count", "needs_manual_count"):
        assert khoa in body, khoa
    assert body["quality_reviewed_skip_count"] == 1


async def test_chua_danh_gia_KHONG_bao_gio_hien_thanh_khong_co_canh_bao(client, chapter):
    """Chấm hỏng thì phải nói là chưa đánh giá, không được trả 0 giả."""
    project_id, page_ids = await chapter(so_trang=1)
    with sync_session() as s:
        s.execute(sa.delete(RegionQualityAssessment))
        s.commit()
    body = (await client.get(f"/api/v1/projects/{project_id}/export-warnings")).json()
    assert body["quality_unassessed_count"] == len(_vung(page_ids[0])) > 0
    assert body["quality_needs_review_count"] == 0

    tom_tat = (await client.get(f"/api/v1/projects/{project_id}/quality-summary")).json()
    assert tom_tat["ro_rang"] == 0, "chưa chấm mà báo là rõ ràng"


# ---------------- chấm lại sau khi sửa tay ----------------


async def test_sua_tay_xong_thi_cham_lai_vung_do(client, chapter, no_broker_for_chained_ocr):
    """Sửa bản dịch xong mà cảnh báo cũ vẫn nằm đó thì người dùng không biết mình đã sửa được chưa."""
    from app.workers.tasks import run_refit_job

    _, page_ids = await chapter(so_trang=1)
    vung = _vung(page_ids[0])[0]
    r = await client.patch(f"/api/v1/regions/{vung.id}",
                           json={"translated_text": "M" + "ộ" * 400})
    assert r.status_code == 200
    run_refit_job(str(r.json()["refit_job_id"]), str(vung.id))

    with sync_session() as s:
        dg = s.execute(sa.select(RegionQualityAssessment).where(
            RegionQualityAssessment.region_id == vung.id)).scalars().first()
        assert dg is not None
        assert dg.review_status is ReviewStatus.needs_review
        assert "layout_overflow_warning" in dg.reason_codes
