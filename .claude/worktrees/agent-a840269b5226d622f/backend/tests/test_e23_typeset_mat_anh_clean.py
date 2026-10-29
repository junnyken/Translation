"""E23 — bước căn chữ tự thoát khi thiếu ảnh đã xoá chữ.

## Lỗi thật đo được (lượt 24 trang, 2026-09-10)

Một cú SIGKILL vào bước xoá chữ để lại trang mang trạng thái như thể bước đó đã xong, nhưng
`<page_id>_clean.png` **không tồn tại** trong kho. Bước căn chữ sau đó hỏng
`FileNotFoundError: … _clean.png` — **12 lần cho cùng một trang** — bị phân loại `permanent_model`,
và trang kẹt ở `translated`.

Ba cơ chế đã có đều KHÔNG cứu được:
- **Quét job mồ côi** (E22, chạy lúc `worker_ready`): khôi phục trạng thái *job/trang*, không
  khôi phục *hiện vật*. Trang này trạng thái vẫn "hợp lệ".
- **`doi_chieu_hien_vat`** (P3f): bắt được — đã kiểm thật, in đúng `translated -> ocr_done` — nhưng
  phải có người chạy tay; `RECONCILE_LEGACY` mặc định `off`.
- **Nút "Chạy lại trang hỏng"** của mẻ: chạy lại bước căn chữ, mà tệp vẫn thiếu ⇒ hỏng tiếp.

⇒ Người dùng thật **không có đường nào tự thoát**. Bản sửa để chính bước căn chữ dọn tại chỗ hỏng.
"""
from __future__ import annotations

import uuid

import pytest

from app.core.db_sync import sync_session
from app.models import Job, OCRResult, Page, TextRegion
from app.models.enums import JobStatus, JobType, PageStatus

pytestmark = pytest.mark.anyio


def _job_typeset(page_id: uuid.UUID) -> uuid.UUID:
    with sync_session() as s:
        job = Job(type=JobType.typeset, page_id=page_id, status=JobStatus.queued)
        s.add(job)
        s.commit()
        return job.id


def _dat(page_id: uuid.UUID, *, status: PageStatus, clean: str | None) -> None:
    with sync_session() as s:
        p = s.get(Page, page_id)
        p.status = status
        p.clean_image_path = clean
        s.commit()


def _doc_trang(page_id: uuid.UUID) -> tuple[PageStatus, str | None]:
    with sync_session() as s:
        p = s.get(Page, page_id)
        return p.status, p.clean_image_path


async def test_thieu_anh_clean_thi_lui_trang_ve_moc_con_bang_chung(client, sample_page_image):
    """Có kết quả OCR trong CSDL ⇒ lùi về `ocr_done`, KHÔNG lùi sạch về `queued`.

    Vùng chữ và kết quả OCR nằm trong CSDL nên chúng không mất. Lùi quá tay là bắt người dùng
    chạy lại những bước vẫn còn nguyên bằng chứng.
    """
    from app.workers.tasks import _lui_neu_mat_anh_clean

    proj = await client.post("/api/v1/projects",
                             json={"name": "E23", "source_lang": "en", "intended_use": "study"})
    pid = proj.json()["id"]
    r = await client.post(f"/api/v1/projects/{pid}/pages",
                          files={"file": ("p.png", sample_page_image, "image/png")})
    page_id = uuid.UUID(r.json()["page_id"])

    with sync_session() as s:
        vung = TextRegion(page_id=page_id, bbox_x=1, bbox_y=1, bbox_w=10, bbox_h=10,
                          reading_order=1)
        s.add(vung)
        s.flush()
        s.add(OCRResult(region_id=vung.id, raw_text="hello"))
        s.commit()

    _dat(page_id, status=PageStatus.translated, clean="projects/x/pages/khong-ton-tai_clean.png")
    cau_loi = _lui_neu_mat_anh_clean(_job_typeset(page_id))

    assert cau_loi is not None
    assert "missing_clean_image" in cau_loi
    # Câu lỗi phải nói người dùng làm gì tiếp — "hỏng" mà không nói cách thoát là chỗ họ đứng lại.
    assert "chạy lại" in cau_loi.lower()

    tt, clean = _doc_trang(page_id)
    assert tt is PageStatus.ocr_done, "phải lùi tới mốc còn bằng chứng, không lùi sạch"
    assert clean is None, "đường dẫn ảnh clean sai phải được xoá, nếu không lần sau lại tin nó"


async def test_khong_co_ocr_thi_lui_ve_detected(client, sample_page_image):
    """Chỉ có vùng chữ, chưa có OCR ⇒ mốc còn bằng chứng là `detected`."""
    from app.workers.tasks import _lui_neu_mat_anh_clean

    proj = await client.post("/api/v1/projects",
                             json={"name": "E23b", "source_lang": "en", "intended_use": "study"})
    pid = proj.json()["id"]
    r = await client.post(f"/api/v1/projects/{pid}/pages",
                          files={"file": ("p.png", sample_page_image, "image/png")})
    page_id = uuid.UUID(r.json()["page_id"])

    with sync_session() as s:
        s.add(TextRegion(page_id=page_id, bbox_x=1, bbox_y=1, bbox_w=10, bbox_h=10,
                         reading_order=1))
        s.commit()

    _dat(page_id, status=PageStatus.translated, clean="projects/x/pages/mat_clean.png")
    assert _lui_neu_mat_anh_clean(_job_typeset(page_id)) is not None
    assert _doc_trang(page_id)[0] is PageStatus.detected


class TestKhongDuocLuiOan:
    """Lùi sai còn tệ hơn không lùi: nó xoá công đã làm và bắt chạy lại vô cớ."""

    async def test_anh_clean_con_thi_KHONG_lui(self, client, sample_page_image):
        from app.workers.tasks import _lui_neu_mat_anh_clean

        proj = await client.post("/api/v1/projects",
                                 json={"name": "E23c", "source_lang": "en",
                                       "intended_use": "study"})
        pid = proj.json()["id"]
        r = await client.post(f"/api/v1/projects/{pid}/pages",
                             files={"file": ("p.png", sample_page_image, "image/png")})
        page_id = uuid.UUID(r.json()["page_id"])

        # Dùng chính ảnh gốc đã tải lên làm "ảnh clean": nó CÓ thật trong kho.
        with sync_session() as s:
            p = s.get(Page, page_id)
            co_that = p.image_path
            p.status = PageStatus.translated
            p.clean_image_path = co_that
            s.commit()

        assert _lui_neu_mat_anh_clean(_job_typeset(page_id)) is None
        tt, clean = _doc_trang(page_id)
        assert tt is PageStatus.translated, "ảnh còn nguyên thì không được đụng vào trang"
        assert clean == co_that

    async def test_trang_chua_tung_xoa_chu_thi_KHONG_lui(self, client, sample_page_image):
        """`clean_image_path` rỗng nghĩa là chưa chạy bước xoá chữ — không phải mất hiện vật.

        Đây là cảnh chế độ `chi_chu` (E19) bỏ hẳn bước xoá chữ. Lùi ở đây là hiểu sai hoàn toàn.
        """
        from app.workers.tasks import _lui_neu_mat_anh_clean

        proj = await client.post("/api/v1/projects",
                                 json={"name": "E23d", "source_lang": "en",
                                       "intended_use": "study"})
        pid = proj.json()["id"]
        r = await client.post(f"/api/v1/projects/{pid}/pages",
                             files={"file": ("p.png", sample_page_image, "image/png")})
        page_id = uuid.UUID(r.json()["page_id"])

        _dat(page_id, status=PageStatus.translated, clean=None)
        assert _lui_neu_mat_anh_clean(_job_typeset(page_id)) is None
        assert _doc_trang(page_id)[0] is PageStatus.translated

    async def test_job_khong_ton_tai_thi_KHONG_no(self):
        """Job không còn trong CSDL (đã bị dọn) không được làm task đổ.

        Bản đầu của test này dựng `Job(page_id=None)` để mô phỏng job mồ côi — CSDL từ chối vì
        `job.page_id` là NOT NULL. Tức cảnh "job không có trang" **không thể tồn tại**, schema đã
        chặn sẵn. Cảnh có thật là job bị xoá mất giữa lúc task đang chờ trong hàng đợi.
        """
        from app.workers.tasks import _lui_neu_mat_anh_clean

        assert _lui_neu_mat_anh_clean(uuid.uuid4()) is None


async def test_dung_chung_luat_lui_voi_cong_cu_quet_toan_bo():
    """Phải có ĐÚNG MỘT luật chọn mốc lùi. Hai luật sẽ lệch nhau lúc ai đó sửa một bên.

    Test theo cấu trúc (không theo hành vi) vì đây là ràng buộc thiết kế: bản một-trang bắt buộc
    gọi lại `_muc_lui_khi_mat_anh_clean` của công cụ quét toàn bộ.
    """
    import inspect

    from app.services import reconcile

    ma = inspect.getsource(reconcile.sua_mot_trang_mat_anh_clean)
    assert "_muc_lui_khi_mat_anh_clean" in ma, (
        "bản sửa một-trang không dùng lại luật chọn mốc lùi của `doi_chieu_hien_vat` ⇒ hai luật "
        "sẽ lệch nhau"
    )
