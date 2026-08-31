"""P3f — đối chiếu bản ghi ↔ hiện vật.

Điều được kiểm gắt nhất ở đây KHÔNG phải "có sửa được không", mà là **chế độ chỉ-đếm tuyệt đối
không ghi gì**. Một công cụ sửa dữ liệu mà lỡ ghi trong lúc người ta tưởng nó chỉ đang đếm thì
tệ hơn hẳn việc không có công cụ nào.
"""
from __future__ import annotations

import uuid

import pytest

from app.core.db_sync import sync_session
from app.models import ExportJob, OCRResult, Page, TextRegion
from app.models.enums import ExportFormat, JobStatus, OCREngine, OCRStatus, PageStatus
from app.services.reconcile import doi_chieu_hien_vat
from app.services.storage import get_storage
from app.services.typeset.paths import preview_relative_path


def _trang(project_id, *, status, clean_rel, co_ocr=True) -> uuid.UUID:
    with sync_session() as s:
        page = Page(project_id=project_id, image_path="goc.png", order=1, status=status)
        page.clean_image_path = clean_rel
        s.add(page); s.flush()
        if co_ocr:
            r = TextRegion(page_id=page.id, bbox_x=1, bbox_y=1, bbox_w=9, bbox_h=9, confidence=0.9)
            s.add(r); s.flush()
            s.add(OCRResult(region_id=r.id, raw_text="hi",
                            ocr_engine=OCREngine.manga_ocr, status=OCRStatus.ok))
        s.commit()
        return page.id


@pytest.fixture
def project_id(client):
    async def _go():
        r = await client.post("/api/v1/projects", json={
            "name": "P3f", "source_lang": "en", "target_lang": "vi", "intended_use": "personal"})
        return uuid.UUID(r.json()["id"])
    return _go


async def test_che_do_chi_dem_KHONG_ghi_mot_chu_nao(project_id):
    pid = await project_id()
    page_id = _trang(pid, status=PageStatus.typeset_done, clean_rel="mat/tieu.png")

    with sync_session() as s:
        kq = doi_chieu_hien_vat(s, get_storage(), ap_dung=False)
    assert kq.trang_mat_anh_clean >= 1
    assert kq.da_ghi is False

    with sync_session() as s:
        page = s.get(Page, page_id)
        assert page.clean_image_path == "mat/tieu.png", "chế độ chỉ-đếm đã GHI vào dữ liệu"
        assert page.status is PageStatus.typeset_done


async def test_ap_dung_thi_rut_loi_khai_va_lui_ve_moc_con_bang_chung(project_id):
    pid = await project_id()
    page_id = _trang(pid, status=PageStatus.typeset_done, clean_rel="mat/tieu.png", co_ocr=True)

    with sync_session() as s:
        doi_chieu_hien_vat(s, get_storage(), ap_dung=True)

    with sync_session() as s:
        page = s.get(Page, page_id)
        assert page.clean_image_path is None
        # Có kết quả OCR trong CSDL ⇒ lùi tới `ocr_done`, KHÔNG lùi sạch về `queued`.
        assert page.status is PageStatus.ocr_done


async def test_khong_co_ocr_thi_lui_sau_hon(project_id):
    pid = await project_id()
    page_id = _trang(pid, status=PageStatus.translated, clean_rel="mat/tieu.png", co_ocr=False)
    with sync_session() as s:
        doi_chieu_hien_vat(s, get_storage(), ap_dung=True)
    with sync_session() as s:
        assert s.get(Page, page_id).status is PageStatus.queued


async def test_khong_dung_toi_trang_con_du_hien_vat(project_id, sample_page_image):
    """Trang lành lặn phải được để YÊN — công cụ sửa mà đụng nhầm là tệ nhất."""
    pid = await project_id()
    storage = get_storage()
    rel = f"p3f/{uuid.uuid4()}_clean.png"
    storage.save(rel, sample_page_image)
    page_id = _trang(pid, status=PageStatus.typeset_done, clean_rel=rel)
    storage.save(preview_relative_path(page_id), sample_page_image)

    with sync_session() as s:
        doi_chieu_hien_vat(s, get_storage(), ap_dung=True)

    with sync_session() as s:
        page = s.get(Page, page_id)
        assert page.clean_image_path == rel
        assert page.status is PageStatus.typeset_done


async def test_mat_rieng_anh_xem_thu_thi_chi_lui_ve_translated(project_id, sample_page_image):
    pid = await project_id()
    storage = get_storage()
    rel = f"p3f/{uuid.uuid4()}_clean.png"
    storage.save(rel, sample_page_image)          # ảnh clean CÒN
    page_id = _trang(pid, status=PageStatus.typeset_done, clean_rel=rel)   # ảnh xem thử thì không

    with sync_session() as s:
        kq = doi_chieu_hien_vat(s, get_storage(), ap_dung=True)
    assert kq.trang_mat_preview >= 1

    with sync_session() as s:
        page = s.get(Page, page_id)
        assert page.clean_image_path == rel, "mất ảnh xem thử mà xoá luôn ảnh clean"
        assert page.status is PageStatus.translated


async def test_lan_xuat_mat_file_bi_ha_xuong_failed(project_id):
    pid = await project_id()
    with sync_session() as s:
        job = ExportJob(project_id=pid, format=ExportFormat.cbz,
                        status=JobStatus.done, output_path="exports/khong-co/a.cbz")
        s.add(job); s.commit()
        job_id = job.id

    with sync_session() as s:
        kq = doi_chieu_hien_vat(s, get_storage(), ap_dung=True)
    assert kq.job_xuat_mat_file >= 1

    with sync_session() as s:
        job = s.get(ExportJob, job_id)
        assert job.status is JobStatus.failed
        assert "artifact_lost" in job.error_log


async def test_png_single_la_THU_MUC_khong_bi_ket_oan(project_id, sample_page_image):
    """`exists()` luôn False với một thư mục ⇒ hỏi mỗi `exists()` là kết oan mọi lần xuất PNG."""
    pid = await project_id()
    storage = get_storage()
    thu_muc = f"exports/{uuid.uuid4()}/png"
    storage.save(f"{thu_muc}/001.png", sample_page_image)
    with sync_session() as s:
        job = ExportJob(project_id=pid, format=ExportFormat.png_single,
                        status=JobStatus.done, output_path=thu_muc)
        s.add(job); s.commit()
        job_id = job.id

    with sync_session() as s:
        doi_chieu_hien_vat(s, get_storage(), ap_dung=True)

    with sync_session() as s:
        assert s.get(ExportJob, job_id).status is JobStatus.done, "lần xuất png_single bị kết oan"


async def test_chay_lan_hai_khong_con_gi_de_sua(project_id):
    """Idempotent — chạy lại trên dữ liệu đã dọn phải ra toàn số 0."""
    pid = await project_id()
    _trang(pid, status=PageStatus.typeset_done, clean_rel="mat/tieu.png")
    with sync_session() as s:
        doi_chieu_hien_vat(s, get_storage(), ap_dung=True)
    with sync_session() as s:
        lai = doi_chieu_hien_vat(s, get_storage(), ap_dung=True)
    assert lai.tong == 0


async def test_che_do_chi_dem_KHONG_dem_mot_trang_hai_lan(project_id):
    """Lỗi thật bắt được trên bản chạy thật 31/08.

    Trang `typeset_done` mất ảnh clean thì cũng mất luôn ảnh xem thử. Ở chế độ sửa, bước 1 đặt
    `clean_image_path=None` nên bước 2 bỏ qua trang đó. Ở chế độ chỉ-đếm thì không ghi gì, nên
    nếu chỉ dựa vào `clean_image_path is None` thì cùng một trang bị đếm HAI lần — báo cáo nói
    10 trong khi thiệt hại thật là 5.
    """
    pid = await project_id()
    _trang(pid, status=PageStatus.typeset_done, clean_rel="mat/tieu.png")

    with sync_session() as s:
        dem = doi_chieu_hien_vat(s, get_storage(), ap_dung=False)
    with sync_session() as s:
        sua = doi_chieu_hien_vat(s, get_storage(), ap_dung=True)

    assert dem.trang_mat_anh_clean == sua.trang_mat_anh_clean
    assert dem.trang_mat_preview == sua.trang_mat_preview
    assert dem.tong == sua.tong, "chế độ chỉ-đếm không dự đoán đúng việc chế độ sửa làm"
