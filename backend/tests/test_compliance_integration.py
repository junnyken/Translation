"""Integration — cổng khai báo & cảnh báo trước khi xuất (M10), trên DB thật."""
from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from app.core.db_sync import sync_session
from app.models import ExportComplianceLog, OCRResult, TextRegion, TypesetResult
from app.models.enums import FitStatus, JobType, OCRStatus
from app.workers.tasks import run_export_job

from tests.test_export_integration import chapter, _job_id  # noqa: F401 - dùng lại fixture M8


def _ep_tran_khung(page_id: str, so_vung: int = 1) -> None:
    with sync_session() as s:
        ds = s.execute(
            sa.select(TypesetResult).join(TextRegion, TextRegion.id == TypesetResult.region_id)
            .where(TextRegion.page_id == uuid.UUID(page_id)).limit(so_vung)
        ).scalars().all()
        for ts in ds:
            ts.fit_status = FitStatus.overflow_warning
        s.commit()


def _ep_can_doc_lai(page_id: str, so_vung: int = 1) -> None:
    with sync_session() as s:
        ds = s.execute(
            sa.select(OCRResult).join(TextRegion, TextRegion.id == OCRResult.region_id)
            .where(TextRegion.page_id == uuid.UUID(page_id)).limit(so_vung)
        ).scalars().all()
        for o in ds:
            o.status = OCRStatus.needs_manual
        s.commit()


def _nhat_ky(project_id: str) -> list[ExportComplianceLog]:
    with sync_session() as s:
        return list(s.execute(
            sa.select(ExportComplianceLog)
            .where(ExportComplianceLog.project_id == uuid.UUID(project_id))
            .order_by(ExportComplianceLog.created_at)
        ).scalars())


# ---------------- khai báo lúc tạo chapter ----------------


async def test_tao_project_thieu_khai_bao_thi_bi_tu_choi(client):
    """Không có mặc định, không suy đoán hộ — thiếu là 422 ngay ở cửa."""
    r = await client.post("/api/v1/projects", json={"name": "Thiếu khai báo", "source_lang": "en"})
    assert r.status_code == 422
    assert "intended_use" in r.text


@pytest.mark.parametrize("gia_tri", ["commercial", "PERSONAL", ""])
async def test_tao_project_khai_bao_sai_thi_bi_tu_choi(client, gia_tri):
    r = await client.post("/api/v1/projects",
                          json={"name": "Sai", "source_lang": "en", "intended_use": gia_tri})
    assert r.status_code == 422


async def test_khai_bao_duoc_giu_nguyen_va_doc_lai_duoc(client):
    r = await client.post("/api/v1/projects",
                          json={"name": "Học tập", "source_lang": "en", "intended_use": "study"})
    assert r.status_code == 201
    pid = r.json()["id"]
    assert r.json()["intended_use"] == "study"
    assert (await client.get(f"/api/v1/projects/{pid}")).json()["intended_use"] == "study"


async def test_khong_co_duong_nao_sua_khai_bao_sau_khi_tao(client):
    """Khai báo mục đích là thứ người dùng tự chịu trách nhiệm — sửa được thì bằng chứng vô nghĩa."""
    r = await client.post("/api/v1/projects",
                          json={"name": "Không sửa được", "source_lang": "en",
                                "intended_use": "personal"})
    pid = r.json()["id"]
    for than in ({"intended_use": "other"}, {"name": "Đổi tên"}):
        for phuong_thuc in (client.patch, client.put):
            kq = await phuong_thuc(f"/api/v1/projects/{pid}", json=than)
            assert kq.status_code in (404, 405), f"{phuong_thuc} mở đường sửa project: {kq.text}"
    assert (await client.get(f"/api/v1/projects/{pid}")).json()["intended_use"] == "personal"


# ---------------- đếm cảnh báo ----------------


async def test_dem_dung_vung_tran_khung_va_vung_chua_doc_duoc(client, chapter):
    project_id, page_ids = await chapter(so_trang=2)
    _ep_tran_khung(page_ids[0], 1)
    _ep_can_doc_lai(page_ids[1], 2)

    r = await client.get(f"/api/v1/projects/{project_id}/export-warnings")
    assert r.status_code == 200
    body = r.json()
    assert body["overflow_warning_count"] == 1
    assert body["needs_manual_count"] == 2
    assert body["acknowledged"] is False
    assert body["acknowledged_at"] is None


async def test_chapter_sach_thi_khong_co_canh_bao_nhung_van_phai_hoi(client, chapter):
    """Không có vùng lỗi vẫn phải hiện nhắc bản quyền — đó mới là phần bắt buộc."""
    project_id, _ = await chapter(so_trang=1)
    body = (await client.get(f"/api/v1/projects/{project_id}/export-warnings")).json()
    assert body["overflow_warning_count"] == 0
    assert body["needs_manual_count"] == 0


async def test_project_khong_ton_tai_tra_404(client):
    r = await client.get(f"/api/v1/projects/{uuid.uuid4()}/export-warnings")
    assert r.status_code == 404


# ---------------- ghi nhận xác nhận ----------------


async def _xuat_va_lay_job(client, project_id: str) -> str:
    r = await client.post(f"/api/v1/projects/{project_id}/export", json={"format": "cbz"})
    assert r.status_code == 202
    return r.json()["job_id"]


async def test_tick_xac_nhan_thi_ghi_lai_dung_so_lieu_dang_hien(client, chapter):
    project_id, page_ids = await chapter(so_trang=2)
    _ep_tran_khung(page_ids[0], 1)
    _ep_can_doc_lai(page_ids[0], 1)
    job_id = await _xuat_va_lay_job(client, project_id)

    r = await client.post(f"/api/v1/export-jobs/{job_id}/acknowledge",
                          json={"user_acknowledged": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user_acknowledged"] is True
    assert body["acknowledged_at"] is not None
    assert body["intended_use"] == "study"
    assert body["overflow_warning_count"] == 1
    assert body["needs_manual_count"] == 1
    assert body["export_job_id"] == job_id

    ds = _nhat_ky(project_id)
    assert len(ds) == 1 and ds[0].user_acknowledged is True


async def test_so_lieu_lay_tu_may_chu_chu_khong_nhan_tu_may_khach(client, chapter):
    """Số do giao diện gửi lên thì không còn là bằng chứng — phải tự đếm lại."""
    project_id, page_ids = await chapter(so_trang=1)
    _ep_tran_khung(page_ids[0], 2)
    job_id = await _xuat_va_lay_job(client, project_id)

    r = await client.post(f"/api/v1/export-jobs/{job_id}/acknowledge",
                          json={"user_acknowledged": True, "overflow_warning_count": 0})
    assert r.status_code == 422, "không được nhận số cảnh báo từ máy khách"

    r = await client.post(f"/api/v1/export-jobs/{job_id}/acknowledge",
                          json={"user_acknowledged": True})
    assert r.json()["overflow_warning_count"] == 2


async def test_khong_tick_van_duoc_ghi_lai_nhung_khong_co_moc_xac_nhan(client, chapter):
    """Mở cảnh báo ra rồi bỏ đi cũng là một sự thật đáng lưu — nhưng không được tính là đã xác nhận."""
    project_id, _ = await chapter(so_trang=1)
    job_id = await _xuat_va_lay_job(client, project_id)

    r = await client.post(f"/api/v1/export-jobs/{job_id}/acknowledge",
                          json={"user_acknowledged": False})
    assert r.status_code == 200
    assert r.json()["acknowledged_at"] is None

    canh_bao = (await client.get(f"/api/v1/projects/{project_id}/export-warnings")).json()
    assert canh_bao["acknowledged"] is False, "chưa tick mà đã coi là đã xác nhận"


async def test_da_xac_nhan_thi_lan_sau_khong_hoi_lai(client, chapter):
    """Cảnh báo hiện lại mỗi lần xuất là kiểu cảnh báo mà ai cũng bấm cho qua."""
    project_id, _ = await chapter(so_trang=1)
    job_id = await _xuat_va_lay_job(client, project_id)
    await client.post(f"/api/v1/export-jobs/{job_id}/acknowledge",
                      json={"user_acknowledged": True})

    body = (await client.get(f"/api/v1/projects/{project_id}/export-warnings")).json()
    assert body["acknowledged"] is True
    assert body["acknowledged_at"] is not None


async def test_xac_nhan_cho_viec_xuat_khong_ton_tai_tra_404(client):
    r = await client.post(f"/api/v1/export-jobs/{uuid.uuid4()}/acknowledge",
                          json={"user_acknowledged": True})
    assert r.status_code == 404


# ---------------- guardrail ----------------


async def test_xuat_KHONG_bi_chan_khi_chua_xac_nhan(client, chapter):
    """Đây là công cụ cá nhân: chặn cứng chỉ khiến người ta đi đường vòng.

    Cổng chặn nằm ở giao diện (nút mờ tới khi tick). Máy chủ ghi nhận, không cấm.
    """
    project_id, _ = await chapter(so_trang=1)
    job_id = await _xuat_va_lay_job(client, project_id)
    assert run_export_job(job_id)["status"] == "done"
    assert _nhat_ky(project_id) == [], "chưa xác nhận thì chưa có bản ghi nào"

    tai_ve = await client.get(f"/api/v1/export-jobs/{job_id}/download")
    assert tai_ve.status_code == 200, "tải về không được chặn"


async def test_nhat_ky_tuan_thu_khong_chua_noi_dung_export(client, chapter):
    """Chỉ lưu SỐ LIỆU. Có đường dẫn file hay bản dịch ở đây là đã lưu nội dung."""
    project_id, _ = await chapter(so_trang=1)
    job_id = await _xuat_va_lay_job(client, project_id)
    run_export_job(job_id)
    await client.post(f"/api/v1/export-jobs/{job_id}/acknowledge",
                      json={"user_acknowledged": True})

    cot = {c.name for c in ExportComplianceLog.__table__.columns}
    for cam in ("output_path", "file_path", "content", "translated_text", "image_path", "storage"):
        assert cam not in cot, f"bảng tuân thủ có cột {cam} — đang lưu nội dung export"
    assert cot == {
        "id", "project_id", "export_job_id", "intended_use", "overflow_warning_count",
        "needs_manual_count", "user_acknowledged", "acknowledged_at", "created_at", "updated_at",
    }
