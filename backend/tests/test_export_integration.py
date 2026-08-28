"""Integration — xuất chapter thật trên DB + storage (M8)."""
from __future__ import annotations

import hashlib
import io
import uuid
import zipfile
from pathlib import Path

import pytest
import sqlalchemy as sa
from PIL import Image

from app.core.db_sync import sync_session
from app.models import ExportJob, Job, Page, TextRegion, TranslationResult, TypesetResult
from app.models.enums import ExportFormat, FitStatus, JobStatus, JobType, OCREngine, PageStatus
from app.services.detect.ctd import DetectedRegion
from app.services.export.paths import export_relative_dir
from app.services.interfaces import BBox
from app.workers.tasks import (
    run_detect_job,
    run_export_job,
    run_inpaint_job,
    run_ocr_job,
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


def _md5(path) -> str:
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


@pytest.fixture
def chapter(client, sample_page_image, fake_detector, fake_ocr_engine,
            fake_inpainter, fake_translator, no_broker_for_chained_ocr):
    """Dựng 1 project nhiều trang, mỗi trang đi hết pipeline M2→M6."""
    async def _go(so_trang=3, ten="Truyện Thử #1"):
        proj = await client.post(
            "/api/v1/projects",
            json={"name": ten, "source_lang": "en", "intended_use": "study"},
        )
        project_id = proj.json()["id"]
        page_ids = []
        for _ in range(so_trang):
            up = await client.post(
                f"/api/v1/projects/{project_id}/pages",
                files={"file": ("p.png", sample_page_image, "image/png")},
            )
            page_id = up.json()["page_id"]
            page_ids.append(page_id)

            fake_detector(regions=[_region(100, 120), _region(700, 1000)])
            run_detect_job(up.json()["job_id"])
            fake_ocr_engine(per_call=lambda i, bbox: (["HELLO", "BYE"][i % 2], 0.95),
                            engine_enum=OCREngine.manga_ocr)
            run_ocr_job(_job_id(page_id, JobType.ocr))
            fake_inpainter()
            fake_ocr_engine(results=("", None), engine_enum=OCREngine.manga_ocr)
            run_inpaint_job(_job_id(page_id, JobType.inpaint))
            fake_translator(prefix="")
            run_translate_job(_job_id(page_id, JobType.translate))
            run_typeset_job(_job_id(page_id, JobType.typeset))
        return project_id, page_ids
    return _go


async def _xuat(client, project_id: str, dinh_dang: str) -> dict:
    r = await client.post(f"/api/v1/projects/{project_id}/export", json={"format": dinh_dang})
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]
    ket_qua = run_export_job(job_id)
    ket_qua["job_id"] = job_id
    return ket_qua


# ---------------- xem trước ----------------


async def test_xem_truoc_dem_dung_so_trang(client, chapter):
    project_id, _ = await chapter(so_trang=3)
    r = await client.get(f"/api/v1/projects/{project_id}/export-preview")
    assert r.status_code == 200
    body = r.json()
    assert body == {
        "page_count": 3, "total_page_count": 3,
        "skipped_page_count": 0, "overflow_warning_count": 0,
    }


async def test_xem_truoc_dem_dung_vung_tran_khung(client, chapter):
    project_id, page_ids = await chapter(so_trang=2)
    with sync_session() as s:  # ép 1 vùng thành tràn khung
        ts = s.execute(
            sa.select(TypesetResult)
            .join(TextRegion, TextRegion.id == TypesetResult.region_id)
            .where(TextRegion.page_id == uuid.UUID(page_ids[0]))
        ).scalars().first()
        ts.fit_status = FitStatus.overflow_warning
        s.commit()
    body = (await client.get(f"/api/v1/projects/{project_id}/export-preview")).json()
    assert body["overflow_warning_count"] == 1


async def test_xem_truoc_bao_ro_trang_chua_canh_chu(client, chapter, sample_page_image):
    project_id, _ = await chapter(so_trang=2)
    await client.post(  # thêm 1 trang mới, chưa chạy pipeline
        f"/api/v1/projects/{project_id}/pages",
        files={"file": ("p.png", sample_page_image, "image/png")},
    )
    body = (await client.get(f"/api/v1/projects/{project_id}/export-preview")).json()
    assert body == {
        "page_count": 2, "total_page_count": 3,
        "skipped_page_count": 1, "overflow_warning_count": 0,
    }


async def test_xem_truoc_project_khong_ton_tai_tra_404(client):
    assert (await client.get(f"/api/v1/projects/{uuid.uuid4()}/export-preview")).status_code == 404


# ---------------- xuất CBZ / ZIP / PNG ----------------


async def test_xuat_cbz_dung_so_trang_dung_thu_tu(client, chapter, storage_root):
    project_id, _ = await chapter(so_trang=3)
    ket_qua = await _xuat(client, project_id, "cbz")
    assert ket_qua["status"] == "done" and ket_qua["page_count"] == 3

    duong_dan = Path(storage_root) / ket_qua["output_path"]
    assert duong_dan.is_file() and duong_dan.name.endswith(".cbz")
    assert zipfile.is_zipfile(duong_dan), "CBZ phải là ZIP hợp lệ (ứng dụng đọc truyện mới mở được)"
    with zipfile.ZipFile(duong_dan) as goi:
        assert goi.namelist() == ["001.png", "002.png", "003.png"]
        assert goi.testzip() is None
        for ten in goi.namelist():
            with Image.open(io.BytesIO(goi.read(ten))) as im:
                assert im.format == "PNG" and im.size == (1200, 1700)


async def test_ten_file_theo_ten_project_khong_dau(client, chapter, storage_root):
    project_id, _ = await chapter(so_trang=1, ten="Truyện Hay #1")
    ket_qua = await _xuat(client, project_id, "cbz")
    assert ket_qua["output_path"].endswith("truyen_hay_1_chapter.cbz")


async def test_xuat_zip_giu_duoi_zip(client, chapter, storage_root):
    project_id, _ = await chapter(so_trang=2)
    ket_qua = await _xuat(client, project_id, "zip")
    assert ket_qua["output_path"].endswith(".zip")
    assert zipfile.is_zipfile(Path(storage_root) / ket_qua["output_path"])


async def test_xuat_png_single_ra_dung_so_file(client, chapter, storage_root):
    project_id, _ = await chapter(so_trang=3)
    ket_qua = await _xuat(client, project_id, "png_single")
    thu_muc = Path(storage_root) / ket_qua["output_path"]
    assert thu_muc.is_dir()
    files = sorted(p.name for p in thu_muc.iterdir())
    assert files == ["001.png", "002.png", "003.png"]
    for f in thu_muc.iterdir():
        with Image.open(f) as im:
            assert im.size == (1200, 1700)


async def test_anh_xuat_ra_co_chu_giong_anh_xem_thu(client, chapter, storage_root):
    """Ảnh giao cho người đọc phải KHÁC ảnh clean — giống hệt nghĩa là quên vẽ chữ."""
    project_id, page_ids = await chapter(so_trang=1)
    ket_qua = await _xuat(client, project_id, "png_single")
    with sync_session() as s:
        page = s.get(Page, uuid.UUID(page_ids[0]))
        clean = Path(storage_root) / page.clean_image_path
    xuat = next((Path(storage_root) / ket_qua["output_path"]).iterdir())
    assert _md5(clean) != _md5(xuat)


# ---------------- cảnh báo & bỏ qua ----------------


async def test_con_vung_tran_khung_van_xuat_nhung_ghi_lai(client, chapter):
    project_id, page_ids = await chapter(so_trang=2)
    with sync_session() as s:
        ts = s.execute(
            sa.select(TypesetResult)
            .join(TextRegion, TextRegion.id == TypesetResult.region_id)
            .where(TextRegion.page_id == uuid.UUID(page_ids[0]))
        ).scalars().first()
        ts.fit_status = FitStatus.overflow_warning
        s.commit()

    ket_qua = await _xuat(client, project_id, "cbz")
    assert ket_qua["status"] == "done", "vùng tràn khung KHÔNG được chặn xuất"
    assert ket_qua["overflow_warning_count"] == 1
    r = await client.get(f"/api/v1/export-jobs/{ket_qua['job_id']}")
    body = r.json()
    assert body["overflow_warning_count"] == 1
    assert "overflow_warning" in (body["error_log"] or ""), "xuất được nhưng phải ghi cảnh báo"


async def test_bo_qua_trang_chua_canh_chu_va_noi_ro(client, chapter, sample_page_image, storage_root):
    project_id, _ = await chapter(so_trang=2)
    await client.post(
        f"/api/v1/projects/{project_id}/pages",
        files={"file": ("p.png", sample_page_image, "image/png")},
    )
    ket_qua = await _xuat(client, project_id, "cbz")
    assert ket_qua["status"] == "done"
    assert ket_qua["page_count"] == 2, "không được xuất trang chưa có chữ"
    assert len(ket_qua["skipped_pages"]) == 1
    body = (await client.get(f"/api/v1/export-jobs/{ket_qua['job_id']}")).json()
    assert "skipped_pages" in (body["error_log"] or "")
    with zipfile.ZipFile(Path(storage_root) / ket_qua["output_path"]) as goi:
        assert len(goi.namelist()) == 2


async def test_khong_trang_nao_canh_chu_thi_that_bai_ro(client, sample_page_image,
                                                        no_broker_for_chained_ocr):
    proj = await client.post("/api/v1/projects",
                             json={"name": "Rỗng", "source_lang": "en", "intended_use": "study"})
    project_id = proj.json()["id"]
    await client.post(f"/api/v1/projects/{project_id}/pages",
                      files={"file": ("p.png", sample_page_image, "image/png")})
    ket_qua = await _xuat(client, project_id, "cbz")
    assert ket_qua["status"] == "failed"
    assert "no_page_ready" in ket_qua["error"]


# ---------------- idempotent & bảo toàn dữ liệu ----------------


async def test_xuat_lai_khong_tich_tu_file_rac(client, chapter, storage_root):
    project_id, _ = await chapter(so_trang=2)
    await _xuat(client, project_id, "cbz")
    thu_muc = Path(storage_root) / export_relative_dir(uuid.UUID(project_id))
    truoc = sorted(p.name for p in thu_muc.iterdir())

    for _ in range(2):
        await _xuat(client, project_id, "cbz")
    assert sorted(p.name for p in thu_muc.iterdir()) == truoc
    assert not any(p.name.endswith(".tmp") for p in thu_muc.iterdir())


async def test_doi_dinh_dang_thi_don_file_cu(client, chapter, storage_root):
    project_id, _ = await chapter(so_trang=1)
    await _xuat(client, project_id, "cbz")
    await _xuat(client, project_id, "png_single")
    thu_muc = Path(storage_root) / export_relative_dir(uuid.UUID(project_id))
    assert sorted(p.name for p in thu_muc.iterdir()) == ["png"], "file cbz cũ chưa bị dọn"


async def test_xuat_khong_dung_anh_goc_va_anh_clean(client, chapter, storage_root):
    project_id, page_ids = await chapter(so_trang=2)
    with sync_session() as s:
        cap = [
            (str(Path(storage_root) / p.image_path), str(Path(storage_root) / p.clean_image_path))
            for p in s.execute(
                sa.select(Page).where(Page.project_id == uuid.UUID(project_id))
            ).scalars()
        ]
    truoc = [(_md5(g), _md5(c)) for g, c in cap]
    await _xuat(client, project_id, "cbz")
    assert [(_md5(g), _md5(c)) for g, c in cap] == truoc


async def test_xuat_khong_xoa_du_lieu_goc(client, chapter):
    """Xuất xong vẫn phải sửa tiếp/xuất lại được — không được dọn dữ liệu nguồn."""
    project_id, _ = await chapter(so_trang=2)
    def _dem():
        with sync_session() as s:
            return tuple(
                s.execute(sa.select(sa.func.count()).select_from(bang)).scalar()
                for bang in (TextRegion, TranslationResult, TypesetResult)
            )
    truoc = _dem()
    await _xuat(client, project_id, "cbz")
    assert _dem() == truoc


async def test_ghi_moc_thoi_gian_xuat(client, chapter):
    project_id, page_ids = await chapter(so_trang=2)
    await _xuat(client, project_id, "cbz")
    with sync_session() as s:
        for pid in page_ids:
            assert s.get(Page, uuid.UUID(pid)).exported_at is not None


# ---------------- endpoint trạng thái & tải về ----------------


async def test_tai_ve_file_cbz(client, chapter):
    project_id, _ = await chapter(so_trang=2)
    ket_qua = await _xuat(client, project_id, "cbz")
    r = await client.get(f"/api/v1/export-jobs/{ket_qua['job_id']}/download")
    assert r.status_code == 200
    assert zipfile.is_zipfile(io.BytesIO(r.content))
    assert "no-cache" in r.headers.get("cache-control", "")


async def test_tai_ve_khi_chua_xong_tra_404(client, chapter):
    project_id, _ = await chapter(so_trang=1)
    r = await client.post(f"/api/v1/projects/{project_id}/export", json={"format": "cbz"})
    job_id = r.json()["job_id"]
    assert (await client.get(f"/api/v1/export-jobs/{job_id}/download")).status_code == 404


async def test_tai_ve_png_single_tra_409_kem_huong_dan(client, chapter):
    project_id, _ = await chapter(so_trang=1)
    ket_qua = await _xuat(client, project_id, "png_single")
    r = await client.get(f"/api/v1/export-jobs/{ket_qua['job_id']}/download")
    assert r.status_code == 409 and "cbz" in r.text


async def test_trang_thai_job_tra_du_field(client, chapter):
    project_id, _ = await chapter(so_trang=2)
    ket_qua = await _xuat(client, project_id, "cbz")
    body = (await client.get(f"/api/v1/export-jobs/{ket_qua['job_id']}")).json()
    assert set(body) == {
        "id", "project_id", "format", "status", "output_path",
        "page_count", "overflow_warning_count", "error_log", "created_at", "updated_at",
    }
    assert body["status"] == "done" and body["page_count"] == 2


async def test_job_khong_ton_tai_tra_404(client):
    assert (await client.get(f"/api/v1/export-jobs/{uuid.uuid4()}")).status_code == 404
    assert (await client.get(f"/api/v1/export-jobs/{uuid.uuid4()}/download")).status_code == 404


async def test_export_project_khong_ton_tai_tra_404(client):
    r = await client.post(f"/api/v1/projects/{uuid.uuid4()}/export", json={"format": "cbz"})
    assert r.status_code == 404


@pytest.mark.parametrize("body", [{"format": "pdf"}, {}, {"format": "cbz", "la": 1}])
async def test_yeu_cau_sai_bi_chan_o_schema(client, chapter, body):
    project_id, _ = await chapter(so_trang=1)
    r = await client.post(f"/api/v1/projects/{project_id}/export", json=body)
    assert r.status_code == 422


async def test_job_export_khong_ton_tai_khong_lam_worker_chet():
    assert run_export_job(str(uuid.uuid4()))["status"] == "job_not_found"
