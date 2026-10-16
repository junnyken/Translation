"""E85 — ảnh thu nhỏ của trang (ảnh bìa thẻ chapter) + đếm vùng tràn khung / cần xem theo trang.

Canh:
1. `/thumbnail` trả JPEG cạnh dài ≤ 480px, lấy ảnh ĐÃ DỊCH nếu có; tạo một lần rồi giữ (ETag ổn
   định); ảnh nguồn đổi ⇒ ảnh thu nhỏ mới, bản cũ bị xoá khỏi kho.
2. `GET /projects/{id}`: trang CHƯA canh/chấm ⇒ NULL (chưa biết), không phải 0; có dữ liệu ⇒ đếm
   đúng; trang đã canh mà không vùng nào tràn ⇒ 0.
"""
from __future__ import annotations

import io
import uuid

import pytest
from PIL import Image

from app.models import RegionQualityAssessment, TextRegion, TypesetResult
from app.models.enums import (
    ConfidenceState,
    FitStatus,
    RegionRelevance,
    ReviewStatus,
    TranslationState,
)

pytestmark = pytest.mark.anyio


async def _trang(client, sample_page_image) -> tuple[str, str]:
    pr = await client.post("/api/v1/projects", json={"name": "c", "source_lang": "ja",
                                                      "intended_use": "study"})
    up = await client.post(f"/api/v1/projects/{pr.json()['id']}/pages",
                           files={"file": ("p.png", sample_page_image, "image/png")})
    return pr.json()["id"], up.json()["page_id"]


async def test_thumbnail_jpeg_nho_va_on_dinh(client, client_b, sample_page_image):
    _pid, page_id = await _trang(client, sample_page_image)
    r = await client.get(f"/api/v1/pages/{page_id}/thumbnail")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    im = Image.open(io.BytesIO(r.content))
    assert max(im.size) <= 480 and im.size[1] > im.size[0], "giữ tỉ lệ trang dọc"
    r2 = await client.get(f"/api/v1/pages/{page_id}/thumbnail")
    assert r2.headers["etag"] == r.headers["etag"], "lần hai phải dùng lại bản đã tạo"
    assert (await client_b.get(f"/api/v1/pages/{page_id}/thumbnail")).status_code == 404


async def test_thumbnail_uu_tien_anh_da_dich_va_don_ban_cu(client, sample_page_image):
    from app.services.storage import get_storage
    from app.services.typeset.paths import preview_relative_path

    pid, page_id = await _trang(client, sample_page_image)
    cu = await client.get(f"/api/v1/pages/{page_id}/thumbnail")
    b = io.BytesIO()
    Image.new("RGB", (600, 900), (10, 200, 10)).save(b, "PNG")
    get_storage().save(preview_relative_path(uuid.UUID(page_id)), b.getvalue())
    moi = await client.get(f"/api/v1/pages/{page_id}/thumbnail")
    assert moi.headers["etag"] != cu.headers["etag"]
    assert Image.open(io.BytesIO(moi.content)).convert("RGB").getpixel((5, 5))[1] > 150, \
        "phải lấy ảnh đã dịch (xanh lá), không phải ảnh gốc (trắng)"
    con = get_storage().list_prefix(f"projects/{pid}/thumbs/{page_id}/")
    assert len(con) == 1, f"bản thu nhỏ cũ chưa bị xoá: {con}"


async def test_dem_vung_theo_trang_null_khi_chua_biet(client, session, sample_page_image):
    pid, page_id = await _trang(client, sample_page_image)
    pg = (await client.get(f"/api/v1/projects/{pid}")).json()["pages"][0]
    assert pg["so_vung_tran_khung"] is None and pg["so_vung_can_xem"] is None

    vung = [TextRegion(page_id=uuid.UUID(page_id), bbox_x=i * 10, bbox_y=0, bbox_w=5, bbox_h=5)
            for i in range(3)]
    session.add_all(vung)
    await session.flush()
    session.add_all([
        TypesetResult(region_id=vung[0].id, fit_status=FitStatus.overflow_warning),
        TypesetResult(region_id=vung[1].id, fit_status=FitStatus.overflow_warning),
        TypesetResult(region_id=vung[2].id, fit_status=FitStatus.fit_ok),
        RegionQualityAssessment(
            region_id=vung[0].id, assessment_version="v1",
            relevance=RegionRelevance.likely_translatable, review_status=ReviewStatus.needs_review,
            detector_confidence_state=ConfidenceState.available,
            ocr_confidence_state=ConfidenceState.available, translation_state=TranslationState.present,
        ),
        RegionQualityAssessment(
            region_id=vung[1].id, assessment_version="v1",
            relevance=RegionRelevance.likely_translatable, review_status=ReviewStatus.reviewed_keep,
            detector_confidence_state=ConfidenceState.available,
            ocr_confidence_state=ConfidenceState.available, translation_state=TranslationState.present,
        ),
    ])
    await session.commit()
    pg = (await client.get(f"/api/v1/projects/{pid}")).json()["pages"][0]
    assert pg["so_vung_tran_khung"] == 2 and pg["so_vung_can_xem"] == 1


async def test_da_canh_khong_vung_nao_tran_la_0(client, session, sample_page_image):
    pid, page_id = await _trang(client, sample_page_image)
    v = TextRegion(page_id=uuid.UUID(page_id), bbox_x=0, bbox_y=0, bbox_w=5, bbox_h=5)
    session.add(v)
    await session.flush()
    session.add(TypesetResult(region_id=v.id, fit_status=FitStatus.fit_ok))
    await session.commit()
    pg = (await client.get(f"/api/v1/projects/{pid}")).json()["pages"][0]
    assert pg["so_vung_tran_khung"] == 0 and pg["so_vung_can_xem"] is None
