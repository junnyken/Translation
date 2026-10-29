"""E33 — gộp chapter KHÔNG được thành lỗ IDOR.

Đây là rủi ro an ninh cốt lõi của tính năng này: mỗi chapter có **chủ riêng** (auth slice B). Nếu
`create_export` chỉ kiểm chapter trên URL mà không kiểm từng id trong danh sách gộp, thì bất kỳ ai
cũng gộp được chapter của người khác vào file của mình rồi tải về.

Phép dò quyền tự sinh (`test_quyen_cheo_tai_khoan.py`) **không bắt được ca này**: nó thử từng
endpoint với id của A, còn ở đây id lạ nằm trong **thân request**, không nằm trên URL.
"""
from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.anyio


async def _tao_chapter(cl, ten: str) -> str:
    r = await cl.post("/api/v1/projects", json={
        "name": ten, "source_lang": "ja", "intended_use": "study"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_KHONG_gop_duoc_chapter_cua_nguoi_khac(client, client_b):
    """B gộp chapter của A vào bản xuất của B ⇒ phải bị chặn, không phải xuất ra file."""
    cua_a = await _tao_chapter(client, "Chapter của A")
    cua_b = await _tao_chapter(client_b, "Chapter của B")

    r = await client_b.post(f"/api/v1/projects/{cua_b}/export", json={
        "format": "cbz", "gop_project_ids": [cua_b, cua_a]})

    assert r.status_code == 404, (
        f"LỖ IDOR: B gộp được chapter của A (HTTP {r.status_code}) — {r.text[:200]}"
    )


async def test_chieu_NGUOC_lai_cung_bi_chan(client, client_b):
    """Kiểm cả hai phía: lỗ hổng một chiều vẫn là lỗ hổng."""
    cua_a = await _tao_chapter(client, "Chapter của A")
    cua_b = await _tao_chapter(client_b, "Chapter của B")

    r = await client.post(f"/api/v1/projects/{cua_a}/export", json={
        "format": "cbz", "gop_project_ids": [cua_a, cua_b]})
    assert r.status_code == 404


async def test_id_KHONG_TON_TAI_thi_tu_choi_ca_luot_xuat(client):
    """Không được lặng lẽ bỏ qua id lạ rồi xuất thiếu — người dùng sẽ tưởng đã gộp đủ."""
    cua_a = await _tao_chapter(client, "Chapter của A")

    r = await client.post(f"/api/v1/projects/{cua_a}/export", json={
        "format": "cbz", "gop_project_ids": [cua_a, str(uuid.uuid4())]})
    assert r.status_code == 404


async def test_gop_chapter_CUA_MINH_thi_duoc(client):
    """Chiều thuận phải chạy — nếu không thì test trên xanh một cách rỗng nghĩa."""
    a1 = await _tao_chapter(client, "Chương Một")
    a2 = await _tao_chapter(client, "Chương Hai")

    r = await client.post(f"/api/v1/projects/{a1}/export", json={
        "format": "cbz", "gop_project_ids": [a1, a2]})
    assert r.status_code == 202, r.text


async def test_luu_dung_THU_TU_nguoi_dung_chon(client, session):
    """Gộp 2 rồi 1 ra file khác hẳn gộp 1 rồi 2 — thứ tự là quyết định của người dùng."""
    import sqlalchemy as sa

    from app.models import ExportJob

    a1 = await _tao_chapter(client, "Chương Một")
    a2 = await _tao_chapter(client, "Chương Hai")

    r = await client.post(f"/api/v1/projects/{a1}/export", json={
        "format": "cbz", "gop_project_ids": [a2, a1]})
    assert r.status_code == 202
    job = (await session.execute(
        sa.select(ExportJob).where(ExportJob.id == uuid.UUID(r.json()["job_id"]))
    )).scalars().one()
    assert job.gop_project_ids == [a2, a1], "thứ tự bị đổi hoặc bị sắp lại"


async def test_KHONG_gop_thi_cot_de_NULL(client, session):
    """Bất biến: xuất một chapter phải giống HỆT trước E33."""
    import sqlalchemy as sa

    from app.models import ExportJob

    a1 = await _tao_chapter(client, "Chương Một")
    r = await client.post(f"/api/v1/projects/{a1}/export", json={"format": "cbz"})
    assert r.status_code == 202
    job = (await session.execute(
        sa.select(ExportJob).where(ExportJob.id == uuid.UUID(r.json()["job_id"]))
    )).scalars().one()
    assert job.gop_project_ids is None


async def test_tran_50_chapter(client):
    """Gộp quá nhiều thì file khổng lồ và lượt xuất chạy quá lâu — chặn ở schema."""
    a1 = await _tao_chapter(client, "Chương Một")
    r = await client.post(f"/api/v1/projects/{a1}/export", json={
        "format": "cbz", "gop_project_ids": [str(uuid.uuid4()) for _ in range(51)]})
    assert r.status_code == 422
