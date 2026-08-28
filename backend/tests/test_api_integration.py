"""Integration — round-trip THẬT qua HTTP + Postgres (M1 §7.2)."""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa

from app.models.enums import JobStatus, JobType, PageStatus


async def _create_project(client, **over):
    payload = {"name": "Test Chapter", "source_lang": "ja", "intended_use": "personal"} | over
    return await client.post("/api/v1/projects", json=payload)


async def test_tao_project_hop_le_tra_201_va_luu_dung_db(client, session):
    r = await _create_project(client)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["source_lang"] == "ja"
    assert body["target_lang"] == "vi"
    assert body["intended_use"] == "personal"
    assert body["status"] == "active"

    row = (
        await session.execute(sa.text("SELECT name, source_lang, intended_use, status FROM project"))
    ).one()
    assert row == ("Test Chapter", "ja", "personal", "active")


async def test_tao_project_thieu_field_bat_buoc_tra_422(client):
    r = await client.post("/api/v1/projects", json={"name": "X", "source_lang": "ja"})
    assert r.status_code == 422
    r2 = await client.post("/api/v1/projects", json={"name": "X", "intended_use": "personal"})
    assert r2.status_code == 422


async def test_upload_page_tra_202_status_queued_va_tao_job_detect(
    client, session, sample_page_image, storage_root
):
    project_id = (await _create_project(client)).json()["id"]

    r = await client.post(
        f"/api/v1/projects/{project_id}/pages",
        files={"file": ("page_001.png", sample_page_image, "image/png")},
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == PageStatus.queued.value
    page_id, job_id = body["page_id"], body["job_id"]

    page = await client.get(f"/api/v1/pages/{page_id}")
    assert page.status_code == 200
    page_body = page.json()
    assert page_body["status"] == "queued"
    assert page_body["order"] == 1
    # Bước inpaint (M4) chưa chạy -> phải NULL, không giá trị giả.
    assert page_body["clean_image_path"] is None

    # File thật đã nằm đúng path đã ghi trong DB.
    saved = Path(storage_root) / page_body["image_path"]
    assert saved.is_file()
    assert saved.read_bytes() == sample_page_image

    job = await client.get(f"/api/v1/jobs/{job_id}")
    assert job.status_code == 200
    jb = job.json()
    assert jb["type"] == JobType.detect.value
    assert jb["status"] == JobStatus.queued.value
    assert jb["retry_count"] == 0
    assert jb["error_log"] is None


async def test_regions_tra_rong_khi_chua_co_m2(client, sample_page_image):
    project_id = (await _create_project(client)).json()["id"]
    up = await client.post(
        f"/api/v1/projects/{project_id}/pages",
        files={"file": ("p.png", sample_page_image, "image/png")},
    )
    page_id = up.json()["page_id"]
    r = await client.get(f"/api/v1/pages/{page_id}/regions")
    assert r.status_code == 200
    assert r.json() == []


async def test_page_order_tang_dan_theo_thu_tu_upload(client, sample_page_image):
    project_id = (await _create_project(client)).json()["id"]
    orders = []
    for i in range(3):
        up = await client.post(
            f"/api/v1/projects/{project_id}/pages",
            files={"file": (f"p{i}.png", sample_page_image, "image/png")},
        )
        page = await client.get(f"/api/v1/pages/{up.json()['page_id']}")
        orders.append(page.json()["order"])
    assert orders == [1, 2, 3]


async def test_upload_file_khong_phai_anh_tra_422(client):
    project_id = (await _create_project(client)).json()["id"]
    r = await client.post(
        f"/api/v1/projects/{project_id}/pages",
        files={"file": ("fake.png", b"khong-phai-anh", "image/png")},
    )
    assert r.status_code == 422


async def test_upload_page_vao_project_khong_ton_tai_tra_404(client, sample_page_image):
    r = await client.post(
        f"/api/v1/projects/{uuid.uuid4()}/pages",
        files={"file": ("p.png", sample_page_image, "image/png")},
    )
    assert r.status_code == 404


async def test_get_job_khong_ton_tai_tra_404(client):
    r = await client.get(f"/api/v1/jobs/{uuid.uuid4()}")
    assert r.status_code == 404


async def test_get_page_khong_ton_tai_tra_404(client):
    r = await client.get(f"/api/v1/pages/{uuid.uuid4()}")
    assert r.status_code == 404


async def test_get_project_tra_kem_danh_sach_page(client, sample_page_image):
    project_id = (await _create_project(client)).json()["id"]
    await client.post(
        f"/api/v1/projects/{project_id}/pages",
        files={"file": ("p.png", sample_page_image, "image/png")},
    )
    r = await client.get(f"/api/v1/projects/{project_id}")
    assert r.status_code == 200
    assert len(r.json()["pages"]) == 1
    assert r.json()["pages"][0]["status"] == "queued"


async def test_openapi_co_dung_6_endpoint_cua_m1(client):
    spec = (await client.get("/openapi.json")).json()
    paths = {
        (p, m)
        for p, item in spec["paths"].items()
        for m in item
    }
    expected = {
        ("/api/v1/projects", "post"),
        ("/api/v1/projects/{project_id}", "get"),
        ("/api/v1/projects/{project_id}/pages", "post"),
        ("/api/v1/pages/{page_id}", "get"),
        ("/api/v1/pages/{page_id}/regions", "get"),
        ("/api/v1/jobs/{job_id}", "get"),
    }
    assert expected <= paths
    # Mọi endpoint NGHIỆP VỤ phải nằm dưới /api/v1 để còn đánh phiên bản được.
    # Ngoại lệ duy nhất: `/healthz` — endpoint vận hành cho nền tảng hosting thăm dò,
    # không có phiên bản vì nó không thuộc hợp đồng API.
    NGOAI_LE = {"/healthz"}
    la = {p for p, _ in paths if not p.startswith("/api/v1/")} - NGOAI_LE
    assert not la, f"endpoint nằm ngoài /api/v1: {la}"
