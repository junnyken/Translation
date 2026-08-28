"""Integration — mẻ chạy thật trên DB (M9). Bộ đẩy việc được thay bằng bản giả để test nhanh."""
from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from app.core.db_sync import sync_session
from app.models import BatchItem, BatchRun, Job, Page, Project
from app.models.enums import (
    BatchItemStatus,
    BatchPipeline,
    BatchStatus,
    JobStatus,
    JobType,
    PageStatus,
)
from app.services.batch.orchestrator import BatchInvalid, BatchOrchestrator


class DayViecGia:
    """Ghi lại việc được đẩy, và cho phép ép trang đi tới trạng thái mong muốn."""

    def __init__(self):
        self.da_day: list[tuple[uuid.UUID, str]] = []
        #: Thời gian hẹn chờ của từng lần đẩy — lần thử lại phải > 0.
        self.cho_giay: list[float] = []

    def __call__(self, page_id, buoc, batch_run_id=None, cho_giay=0.0):
        self.da_day.append((page_id, buoc))
        self.cho_giay.append(cho_giay)
        with sync_session() as s:
            job = Job(type=JobType.detect, page_id=page_id, status=JobStatus.queued)
            s.add(job)
            s.commit()
            return job.id


def _dat_trang_thai(page_id, tt: PageStatus):
    with sync_session() as s:
        p = s.get(Page, page_id)
        p.status = tt
        s.commit()


@pytest.fixture
async def du_an(client, sample_page_image, no_broker_for_chained_ocr):
    """Project 4 trang, tất cả ở `queued`."""
    async def _go(so_trang=4, ten="Mẻ thử"):
        proj = await client.post("/api/v1/projects",
                                 json={"name": ten, "source_lang": "en", "intended_use": "study"})
        pid = proj.json()["id"]
        pages = []
        for _ in range(so_trang):
            r = await client.post(f"/api/v1/projects/{pid}/pages",
                                  files={"file": ("p.png", sample_page_image, "image/png")})
            pages.append(uuid.UUID(r.json()["page_id"]))
        return uuid.UUID(pid), pages
    return _go


def _me(me_id) -> BatchRun:
    with sync_session() as s:
        return s.get(BatchRun, me_id)


def _muc(me_id) -> list[BatchItem]:
    with sync_session() as s:
        return list(s.execute(
            sa.select(BatchItem).where(BatchItem.batch_run_id == me_id)
            .order_by(BatchItem.page_order)
        ).scalars())


# ---------------- tạo mẻ + ảnh chụp ----------------


async def test_tao_me_chup_dung_danh_sach_trang(du_an):
    pid, pages = await du_an(so_trang=4)
    day = DayViecGia()
    me_id = BatchOrchestrator(dispatcher=day).create_full_pipeline_run(pid, "google_fast")

    me = _me(me_id)
    assert me.total_pages == 4
    assert me.requested_pipeline is BatchPipeline.full_pipeline
    muc = _muc(me_id)
    assert [m.page_order for m in muc] == [1, 2, 3, 4]
    assert {m.page_id for m in muc} == set(pages)


async def test_trang_them_sau_khong_lot_vao_me_dang_chay(client, du_an, sample_page_image):
    """Nếu lọt vào thì tổng số trang nhảy giữa chừng, không ai biết mẻ xong chưa."""
    pid, _ = await du_an(so_trang=3)
    day = DayViecGia()
    me_id = BatchOrchestrator(dispatcher=day).create_full_pipeline_run(pid, "google_fast")

    await client.post(f"/api/v1/projects/{pid}/pages",
                      files={"file": ("them.png", sample_page_image, "image/png")})

    assert _me(me_id).total_pages == 3
    assert len(_muc(me_id)) == 3


async def test_project_khong_co_trang_thi_tu_choi(client):
    proj = await client.post("/api/v1/projects",
                             json={"name": "rỗng", "source_lang": "en", "intended_use": "study"})
    with pytest.raises(BatchInvalid, match="no_page"):
        BatchOrchestrator(dispatcher=DayViecGia()).create_full_pipeline_run(
            uuid.UUID(proj.json()["id"]), "google_fast"
        )


async def test_project_khong_ton_tai_thi_tu_choi(client):
    with pytest.raises(BatchInvalid, match="project_not_found"):
        BatchOrchestrator(dispatcher=DayViecGia()).create_full_pipeline_run(
            uuid.uuid4(), "google_fast"
        )


# ---------------- đẩy việc theo giới hạn ----------------


async def test_chi_day_dung_so_trang_song_song(du_an):
    pid, _ = await du_an(so_trang=4)
    day = DayViecGia()
    BatchOrchestrator(max_concurrent_pages=2, dispatcher=day).create_full_pipeline_run(pid, "google_fast")
    assert len(day.da_day) == 2, f"đẩy {len(day.da_day)} việc, đáng lẽ 2"


async def test_moi_trang_bat_dau_tu_dung_buoc_dang_dung(du_an):
    """Không chạy lại từ đầu — máy trạng thái M1 không cho `translated -> detecting`."""
    pid, pages = await du_an(so_trang=3)
    _dat_trang_thai(pages[0], PageStatus.detected)
    _dat_trang_thai(pages[1], PageStatus.translated)
    _dat_trang_thai(pages[2], PageStatus.ocr_done)

    day = DayViecGia()
    BatchOrchestrator(max_concurrent_pages=3, dispatcher=day).create_full_pipeline_run(pid, "google_fast")
    buoc = {p: b for p, b in day.da_day}
    assert buoc[pages[0]] == "ocr"
    assert buoc[pages[1]] == "typeset"
    assert buoc[pages[2]] == "inpaint"


async def test_trang_da_xong_thi_bo_qua_khong_chay_lai(du_an):
    """Chạy lại trang đã xong sẽ xoá mất kết quả — kể cả phần vừa sửa tay ở M7."""
    pid, pages = await du_an(so_trang=2)
    _dat_trang_thai(pages[0], PageStatus.typeset_done)

    day = DayViecGia()
    me_id = BatchOrchestrator(max_concurrent_pages=2, dispatcher=day).create_full_pipeline_run(pid, "google_fast")
    muc = {m.page_id: m for m in _muc(me_id)}
    assert muc[pages[0]].status is BatchItemStatus.skipped
    assert muc[pages[0]].error_code == "da_xong"
    assert pages[0] not in [p for p, _ in day.da_day]


async def test_trang_dang_chay_thi_khong_day_them_va_KHONG_tinh_la_xong(du_an):
    """Lỗi thật do Run E tìm ra: từng đánh `skipped` cho trang đang chạy, khiến mẻ báo
    'hoàn thành 3/3' trong khi một trang vẫn kẹt ở `detecting` và chưa hề được xử lý."""
    pid, pages = await du_an(so_trang=1)
    _dat_trang_thai(pages[0], PageStatus.detecting)
    day = DayViecGia()
    me_id = BatchOrchestrator(dispatcher=day).create_full_pipeline_run(pid, "google_fast")
    muc = _muc(me_id)[0]
    assert muc.status is BatchItemStatus.pending, "đang chạy dở KHÔNG phải là xong"
    assert muc.error_code == "dang_chay"
    assert day.da_day == []
    assert _me(me_id).status is BatchStatus.running, "còn việc thì phải nói là còn việc"
    assert _me(me_id).completed_pages == 0


# ---------------- nhận kết quả, thử lại, chặn quota ----------------


async def test_buoc_xong_nhung_trang_chua_het_thi_chay_tiep(du_an):
    pid, pages = await du_an(so_trang=1)
    day = DayViecGia()
    dp = BatchOrchestrator(dispatcher=day)
    me_id = dp.create_full_pipeline_run(pid, "google_fast")
    assert day.da_day[-1][1] == "detect"

    _dat_trang_thai(pages[0], PageStatus.detected)
    dp.on_page_terminal(pages[0], None, "completed")
    assert day.da_day[-1][1] == "ocr", "phải chạy tiếp bước sau, không dừng"
    assert _me(me_id).status is BatchStatus.running


async def test_trang_di_het_pipeline_thi_muc_hoan_thanh(du_an):
    pid, pages = await du_an(so_trang=1)
    dp = BatchOrchestrator(dispatcher=DayViecGia())
    me_id = dp.create_full_pipeline_run(pid, "google_fast")
    _dat_trang_thai(pages[0], PageStatus.typeset_done)
    dp.on_page_terminal(pages[0], None, "completed")

    assert _muc(me_id)[0].status is BatchItemStatus.completed
    assert _me(me_id).status is BatchStatus.completed
    assert _me(me_id).completed_pages == 1
    assert _me(me_id).finished_at is not None


async def test_loi_tam_thoi_thi_thu_lai_co_gioi_han(du_an):
    from app.services.batch.errors import RetryPolicy

    pid, pages = await du_an(so_trang=1)
    day = DayViecGia()
    dp = BatchOrchestrator(dispatcher=day, retry_policy=RetryPolicy(max_retries=2))
    me_id = dp.create_full_pipeline_run(pid, "google_fast")

    for lan in range(3):
        dp.on_page_terminal(pages[0], None, "failed", "HTTP 503: service unavailable")
    muc = _muc(me_id)[0]
    assert muc.retry_count == 2, "phải dừng đúng ở max_retries"
    assert muc.status is BatchItemStatus.failed
    assert _me(me_id).status is BatchStatus.failed


async def test_loi_vinh_vien_thi_hong_ngay_khong_thu_lai(du_an):
    pid, pages = await du_an(so_trang=1)
    dp = BatchOrchestrator(dispatcher=DayViecGia())
    me_id = dp.create_full_pipeline_run(pid, "google_fast")
    dp.on_page_terminal(pages[0], None, "failed", "FontNotFound: font_not_found family lạ")

    muc = _muc(me_id)[0]
    assert muc.retry_count == 0, "lỗi vĩnh viễn mà thử lại là phí thời gian"
    assert muc.status is BatchItemStatus.failed
    assert muc.error_code == "permanent_model"


async def test_het_quota_thi_chan_chu_khong_bao_hong(du_an):
    """`blocked_quota` khác `failed`: quota hồi là chạy lại được, không phải hỏng hẳn."""
    pid, pages = await du_an(so_trang=1)
    dp = BatchOrchestrator(dispatcher=DayViecGia())
    me_id = dp.create_full_pipeline_run(pid, "google_fast")
    dp.on_page_terminal(pages[0], None, "failed",
                        'HTTP 429: {"status":"RESOURCE_EXHAUSTED","message":"exceeded your current quota"}')

    muc = _muc(me_id)[0]
    assert muc.status is BatchItemStatus.blocked_quota
    assert muc.error_code == "quota_exhausted"
    assert muc.retry_count == 0, "hết quota mà thử lại là tốn tiền vô ích"
    assert _me(me_id).status is BatchStatus.blocked_quota


async def test_me_khong_bao_xong_khi_con_trang_chua_chay(du_an):
    """Điều kiện quan trọng nhất của M9."""
    pid, pages = await du_an(so_trang=3)
    dp = BatchOrchestrator(max_concurrent_pages=1, dispatcher=DayViecGia())
    me_id = dp.create_full_pipeline_run(pid, "google_fast")
    _dat_trang_thai(pages[0], PageStatus.typeset_done)
    dp.on_page_terminal(pages[0], None, "completed")

    assert _me(me_id).status is BatchStatus.running
    assert _me(me_id).status is not BatchStatus.completed


async def test_thong_diep_loi_bi_loc_khoa_bi_mat(du_an):
    pid, pages = await du_an(so_trang=1)
    dp = BatchOrchestrator(dispatcher=DayViecGia())
    me_id = dp.create_full_pipeline_run(pid, "google_fast")
    dp.on_page_terminal(pages[0], None, "failed",
                        "HTTP 401: key=AIzaSyD1234567890abcdefghij bị từ chối")
    loi = _muc(me_id)[0].error_message
    assert "AIzaSyD1234567890" not in loi
    assert "***" in loi


# ---------------- chạy lại / huỷ ----------------


async def test_chay_lai_chi_dung_muc_hong(du_an):
    pid, pages = await du_an(so_trang=3)
    dp = BatchOrchestrator(max_concurrent_pages=3, dispatcher=DayViecGia())
    me_id = dp.create_full_pipeline_run(pid, "google_fast")
    _dat_trang_thai(pages[0], PageStatus.typeset_done)
    dp.on_page_terminal(pages[0], None, "completed")
    dp.on_page_terminal(pages[1], None, "failed", "FontNotFound: font_not_found")
    dp.on_page_terminal(pages[2], None, "failed", "HTTP 429: RESOURCE_EXHAUSTED quota exceeded")

    dem = dp.resume_failed(me_id)
    assert dem == 2, "chỉ chạy lại failed + blocked_quota"
    muc = {m.page_id: m for m in _muc(me_id)}
    assert muc[pages[0]].status is BatchItemStatus.completed, "mục đã xong KHÔNG được đụng vào"
    assert muc[pages[1]].status in (BatchItemStatus.pending, BatchItemStatus.running)
    assert muc[pages[2]].status in (BatchItemStatus.pending, BatchItemStatus.running)


async def test_chay_lai_muc_da_xong_thi_tu_choi(du_an):
    pid, pages = await du_an(so_trang=1)
    dp = BatchOrchestrator(dispatcher=DayViecGia())
    me_id = dp.create_full_pipeline_run(pid, "google_fast")
    _dat_trang_thai(pages[0], PageStatus.typeset_done)
    dp.on_page_terminal(pages[0], None, "completed")

    with pytest.raises(BatchInvalid, match="item_not_resumable"):
        dp.resume_failed(me_id, [_muc(me_id)[0].id])


async def test_chay_lai_muc_cua_me_khac_thi_tu_choi(du_an):
    pid, _ = await du_an(so_trang=1)
    dp = BatchOrchestrator(dispatcher=DayViecGia())
    me_id = dp.create_full_pipeline_run(pid, "google_fast")
    with pytest.raises(BatchInvalid, match="item_not_in_batch"):
        dp.resume_failed(me_id, [uuid.uuid4()])


async def test_huy_thi_dung_day_viec_moi(du_an):
    pid, _ = await du_an(so_trang=4)
    day = DayViecGia()
    dp = BatchOrchestrator(max_concurrent_pages=1, dispatcher=day)
    me_id = dp.create_full_pipeline_run(pid, "google_fast")
    truoc = len(day.da_day)

    dp.cancel(me_id)
    assert _me(me_id).status is BatchStatus.cancelled
    assert dp.dispatch_next(me_id) == 0
    assert len(day.da_day) == truoc, "huỷ rồi vẫn đẩy việc là sai"
    cho = [m for m in _muc(me_id) if m.status is BatchItemStatus.pending]
    assert cho == [], "mọi mục đang chờ phải chuyển sang bỏ qua"


# ---------------- API ----------------


async def test_api_tao_va_theo_doi_me(client, du_an, monkeypatch):
    pid, _ = await du_an(so_trang=3)
    day = DayViecGia()
    monkeypatch.setattr("app.services.batch.dispatch.day_viec_buoc", day, raising=False)
    monkeypatch.setattr("app.services.batch.orchestrator.BatchOrchestrator._dispatcher", day, raising=False)

    r = await client.post(f"/api/v1/projects/{pid}/batch-runs",
                          json={"requested_pipeline": "full_pipeline",
                                "translation_engine": "google_fast"})
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["total_pages"] == 3

    tt = await client.get(f"/api/v1/batch-runs/{body['batch_run_id']}")
    assert tt.status_code == 200
    assert tt.json()["total_pages"] == 3

    ds = await client.get(f"/api/v1/batch-runs/{body['batch_run_id']}/items")
    assert ds.status_code == 200
    assert len(ds.json()["items"]) == 3
    assert [i["page_order"] for i in ds.json()["items"]] == [1, 2, 3]


async def test_api_llm_chua_cau_hinh_thi_tu_choi_ngay(client, du_an, monkeypatch):
    """Báo ngay chứ không xếp việc rồi mới hỏng ở trang đầu tiên."""
    from app.core.config import get_settings

    pid, _ = await du_an(so_trang=1)
    s = get_settings()
    monkeypatch.setattr(s, "gemini_api_keys", "")
    r = await client.post(f"/api/v1/projects/{pid}/batch-runs",
                          json={"translation_engine": "llm_context"})
    assert r.status_code == 422
    assert "llm_not_configured" in r.text


async def test_api_me_khong_ton_tai_tra_404(client):
    assert (await client.get(f"/api/v1/batch-runs/{uuid.uuid4()}")).status_code == 404
    assert (await client.get(f"/api/v1/batch-runs/{uuid.uuid4()}/items")).status_code == 404
    assert (await client.post(f"/api/v1/batch-runs/{uuid.uuid4()}/cancel")).status_code == 404


@pytest.mark.parametrize("body", [{"requested_pipeline": "la"}, {"la": 1},
                                  {"translation_engine": "khong-co"}])
async def test_api_du_lieu_sai_bi_chan(client, du_an, body):
    pid, _ = await du_an(so_trang=1)
    r = await client.post(f"/api/v1/projects/{pid}/batch-runs", json=body)
    assert r.status_code == 422


async def test_bo_qua_trang_dau_van_phai_chay_tiep_trang_sau(du_an):
    """Lỗi thật do live verification tìm ra: mẻ treo vĩnh viễn.

    Trang đầu đang chạy dở (pipeline tự chảy sau upload đã khởi động) nên bị bỏ qua. Vòng đẩy
    việc kết thúc mà không đẩy được gì, và không có sự kiện nào đánh thức lại — các trang sau
    nằm `pending` mãi mãi.
    """
    pid, pages = await du_an(so_trang=3)
    _dat_trang_thai(pages[0], PageStatus.detecting)      # đang chạy dở -> bỏ qua
    _dat_trang_thai(pages[1], PageStatus.typeset_done)   # đã xong -> bỏ qua

    day = DayViecGia()
    me_id = BatchOrchestrator(max_concurrent_pages=1, dispatcher=day).create_full_pipeline_run(
        pid, "google_fast"
    )
    assert [p for p, _ in day.da_day] == [pages[2]], "phải nhảy qua 2 trang đầu để đẩy trang 3"
    muc = {m.page_id: m.status for m in _muc(me_id)}
    assert muc[pages[0]] is BatchItemStatus.pending      # đang chạy dở, chưa xong
    assert muc[pages[1]] is BatchItemStatus.skipped      # đã xong thật
    assert muc[pages[2]] is BatchItemStatus.running


async def test_moi_muc_deu_bo_qua_thi_me_ket_thuc_chu_khong_treo(du_an):
    pid, pages = await du_an(so_trang=2)
    for p in pages:
        _dat_trang_thai(p, PageStatus.typeset_done)
    day = DayViecGia()
    me_id = BatchOrchestrator(dispatcher=day).create_full_pipeline_run(pid, "google_fast")
    assert day.da_day == []
    assert _me(me_id).status is BatchStatus.completed, "bỏ qua hết = xong, không phải treo"


async def test_thu_hoi_muc_ket_running_khi_worker_chet(du_an):
    """Lỗi thật do Run E tìm ra: worker khởi động lại giữa chừng ⇒ mục kẹt `running` VĨNH VIỄN.

    `resume` chỉ nhận failed/blocked_quota nên bấm 'chạy lại' cũng không cứu được — mẻ đứng im
    mà nhìn vào không biết vì sao. Cùng triệu chứng đã ghi ở REPORT_M8 §7 nhưng ở mức Job.
    """
    from datetime import datetime, timedelta, timezone

    pid, pages = await du_an(so_trang=2)
    day = DayViecGia()
    dp = BatchOrchestrator(max_concurrent_pages=1, dispatcher=day, stale_item_seconds=60)
    me_id = dp.create_full_pipeline_run(pid, "google_fast")

    # giả lập worker chết: mục vẫn `running` nhưng đã bắt đầu từ lâu
    with sync_session() as s:
        m = s.execute(
            sa.select(BatchItem).where(
                BatchItem.batch_run_id == me_id, BatchItem.status == BatchItemStatus.running
            )
        ).scalars().one()
        m.started_at = datetime.now(timezone.utc) - timedelta(seconds=600)
        s.commit()

    assert dp.thu_hoi_muc_mo_coi(me_id) == 1
    muc = {m.id: m for m in _muc(me_id)}
    mo_coi = [m for m in muc.values() if m.error_code == "stale_reclaimed"]
    assert len(mo_coi) == 1
    assert mo_coi[0].status is BatchItemStatus.pending


async def test_chay_lai_cuu_duoc_ca_muc_ket_running(du_an):
    from datetime import datetime, timedelta, timezone

    pid, _ = await du_an(so_trang=1)
    day = DayViecGia()
    dp = BatchOrchestrator(dispatcher=day, stale_item_seconds=60)
    me_id = dp.create_full_pipeline_run(pid, "google_fast")
    with sync_session() as s:
        m = s.execute(sa.select(BatchItem).where(BatchItem.batch_run_id == me_id)).scalars().one()
        m.started_at = datetime.now(timezone.utc) - timedelta(seconds=600)
        s.commit()

    assert dp.resume_failed(me_id) == 1, "chạy lại phải cứu được cả mục kẹt running"


async def test_muc_dang_chay_binh_thuong_thi_khong_bi_thu_hoi(du_an):
    """Thu hồi sớm là cắt ngang việc đang chạy đúng — tệ hơn là để nó chạy nốt."""
    pid, _ = await du_an(so_trang=1)
    dp = BatchOrchestrator(dispatcher=DayViecGia(), stale_item_seconds=3600)
    me_id = dp.create_full_pipeline_run(pid, "google_fast")
    assert dp.thu_hoi_muc_mo_coi(me_id) == 0


async def test_trang_ket_o_trang_thai_tam_qua_lau_thi_bao_hong_chu_khong_treo(du_an):
    """Máy trạng thái M1 không cho đi tiếp từ `detecting`. Đánh hỏng CÓ LÝ DO còn hơn treo mãi."""
    from datetime import datetime, timedelta, timezone

    pid, pages = await du_an(so_trang=1)
    _dat_trang_thai(pages[0], PageStatus.detecting)
    dp = BatchOrchestrator(dispatcher=DayViecGia(), stale_item_seconds=60)
    me_id = dp.create_full_pipeline_run(pid, "google_fast")
    with sync_session() as s:
        m = s.execute(sa.select(BatchItem).where(BatchItem.batch_run_id == me_id)).scalars().one()
        m.created_at = datetime.now(timezone.utc) - timedelta(seconds=600)
        s.commit()

    assert dp.thu_hoi_muc_mo_coi(me_id) == 1
    muc = _muc(me_id)[0]
    assert muc.status is BatchItemStatus.failed
    assert muc.error_code == "stale_page"
    assert "kẹt" in (muc.error_message or "")


# ---------------- báo kết quả về mẻ ở nhánh LỖI ----------------


async def test_do_khung_hong_thi_muc_hong_ngay_chu_khong_treo(du_an, fake_detector):
    """Lỗi thật: `run_detect_job` chỉ báo về mẻ ở nhánh THÀNH CÔNG.

    Dò khung là bước đầu tiên của mẻ và cũng là bước hay hỏng nhất. Hỏng mà không báo về thì
    mục nằm lại `running` tới khi bộ thu hồi mồ côi chạm mốc 2400s — suốt 40 phút đó giao diện
    hiện "đang chạy" trong khi thật ra không còn gì chạy cả.
    """
    from app.workers.tasks import run_detect_job

    pid, pages = await du_an(so_trang=1)
    day = DayViecGia()
    me_id = BatchOrchestrator(max_concurrent_pages=1, dispatcher=day).create_full_pipeline_run(
        pid, "google_fast"
    )
    dang_chay = [m for m in _muc(me_id) if m.status is BatchItemStatus.running]
    assert len(dang_chay) == 1
    job_id = dang_chay[0].current_job_id
    assert job_id is not None

    fake_detector(raises=RuntimeError("mô hình dò khung hỏng"))
    kq = run_detect_job(str(job_id))
    assert kq["status"] == "failed"

    muc = _muc(me_id)[0]
    assert muc.status is BatchItemStatus.failed, "mục vẫn kẹt `running` — mẻ treo"
    assert muc.finished_at is not None
    assert _me(me_id).status is BatchStatus.failed


# ---------------- cấu hình + danh sách mẻ (giao diện cần) ----------------


async def test_api_cau_hinh_me_khong_lo_khoa(client):
    """Giao diện cần biết CÓ dùng được LLM không — nhưng chỉ được biết true/false."""
    r = await client.get("/api/v1/batch-config")
    assert r.status_code == 200
    body = r.json()
    assert body["llm_configured"] is False, "test không cấu hình khoá"
    assert isinstance(body["batch_max_retries"], int)
    tho = str(body).lower()
    for cam in ("aiza", "api_key", "gemini_api_keys", "secret"):
        assert cam not in tho, f"cấu hình lộ {cam}"


async def test_api_liet_ke_me_cua_project_moi_nhat_truoc(du_an, client):
    """Tải lại trang không được làm mất dấu mẻ đang chạy."""
    pid, pages = await du_an(so_trang=2)
    day = DayViecGia()
    dp = BatchOrchestrator(max_concurrent_pages=1, dispatcher=day)
    me1 = dp.create_full_pipeline_run(pid, "google_fast")
    me2 = dp.create_full_pipeline_run(pid, "google_fast")

    r = await client.get(f"/api/v1/projects/{pid}/batch-runs")
    assert r.status_code == 200
    ids = [m["id"] for m in r.json()["runs"]]
    assert ids[0] == str(me2) and str(me1) in ids, "phải mới nhất trước"


async def test_api_liet_ke_me_cua_project_khong_ton_tai_tra_404(client):
    r = await client.get(f"/api/v1/projects/{uuid.uuid4()}/batch-runs")
    assert r.status_code == 404


async def test_thu_lai_phai_cho_lui_dan_chu_khong_goi_ngay(du_an):
    """Lỗi thật: `next_delay_seconds` được viết ra nhưng KHÔNG chỗ nào gọi.

    Nghĩa là mọi lần thử lại đều gọi lại ngay lập tức. Gọi lại ngay sau khi nhà cung cấp vừa báo
    "quá nhịp" là cách chắc chắn nhất để bị chặn tiếp — và mini-spec §3.4 buộc phải có lùi dần
    kèm nhiễu.
    """
    from app.services.batch.errors import RetryPolicy

    pid, pages = await du_an(so_trang=1)
    day = DayViecGia()
    dp = BatchOrchestrator(
        max_concurrent_pages=1, dispatcher=day,
        retry_policy=RetryPolicy(max_retries=3, backoff_base_seconds=2, backoff_max_seconds=120),
    )
    me_id = dp.create_full_pipeline_run(pid, "google_fast")
    assert day.cho_giay == [0.0], "lần đầu không phải thử lại thì không chờ"

    dp.on_page_terminal(pages[0], None, "failed", "HTTP 429: rate limit, try again")
    assert len(day.cho_giay) == 2
    assert day.cho_giay[1] > 0, "lần thử lại thứ nhất phải chờ"

    dp.on_page_terminal(pages[0], None, "failed", "HTTP 503: provider tạm thời")
    assert len(day.cho_giay) == 3
    assert day.cho_giay[2] > 0

    # Nhiễu là tất định theo mã mục nên đo lại vẫn ra đúng con số, nhưng vẫn phải nằm trong trần.
    assert all(c <= 120 for c in day.cho_giay), "không được vượt trần cấu hình"


async def test_buoc_sau_khi_thu_lai_thanh_cong_thi_KHONG_bi_cho_oan(du_an):
    """Lỗi thật đo ở Run B: sau khi thử lại thành công, bước KẾ TIẾP vẫn bị hẹn chờ.

    Log thật: `đẩy bước typeset …, chờ 3.7s` — canh chữ chẳng liên quan gì tới lỗi mạng lúc dịch,
    nhưng vì lấy thẳng `retry_count` làm căn cứ nên mọi bước còn lại của trang đều bị phạt.
    """
    from app.services.batch.errors import RetryPolicy

    pid, pages = await du_an(so_trang=1)
    day = DayViecGia()
    dp = BatchOrchestrator(max_concurrent_pages=1, dispatcher=day,
                           retry_policy=RetryPolicy(backoff_base_seconds=10))
    me_id = dp.create_full_pipeline_run(pid, "google_fast")

    dp.on_page_terminal(pages[0], None, "failed", "HTTP 429: rate limit, try again")
    assert day.cho_giay[-1] > 0, "lần thử lại thì phải chờ"

    # Bước chạy được ⇒ trang đi tiếp một bước, và lần đẩy kế KHÔNG phải là thử lại.
    _dat_trang_thai(pages[0], PageStatus.detected)
    dp.on_page_terminal(pages[0], None, "completed")
    assert day.cho_giay[-1] == 0, f"bước kế tiếp bị chờ oan {day.cho_giay[-1]}s"
    with sync_session() as s:
        m = s.execute(sa.select(BatchItem).where(BatchItem.batch_run_id == me_id)).scalars().one()
        assert m.retry_count == 1, "vẫn phải giữ số lần đã thử làm bằng chứng"
        assert m.error_code is None


async def test_bi_chan_nhip_het_luot_thu_thi_bao_chan_chu_khong_bao_hong(du_an):
    """Hết lượt thử lại vì bị chặn nhịp ⇒ `blocked_quota`, không phải `failed`.

    Gọi nó là "hỏng" sẽ khiến người vận hành đi tìm lỗi ở chỗ không có lỗi, trong khi việc cần làm
    chỉ là chờ hạn mức hồi rồi bấm chạy lại.
    """
    from app.services.batch.errors import RetryPolicy

    pid, pages = await du_an(so_trang=1)
    dp = BatchOrchestrator(max_concurrent_pages=1, dispatcher=DayViecGia(),
                           retry_policy=RetryPolicy(max_retries=2))
    me_id = dp.create_full_pipeline_run(pid, "llm_context")
    for _ in range(3):
        dp.on_page_terminal(pages[0], None, "failed",
                            "HTTP 429: rate limit — cổng nhịp chặn (rate_limited)")

    muc = _muc(me_id)[0]
    assert muc.status is BatchItemStatus.blocked_quota
    assert muc.error_code == "transient_rate_limit", "vẫn phải phân biệt quá-nhịp với hết-quota"
    assert muc.retry_count == 2
    assert _me(me_id).status is BatchStatus.blocked_quota


async def test_bam_chay_lai_ngay_sau_su_co_phai_cuu_duoc_muc_ket_running(du_an, monkeypatch):
    """Lỗi thật do Run E tìm ra: worker bị giết lúc đang xoá chữ ⇒ bấm "chạy lại" trả về
    `resumed_count=0` và mẻ đứng im ở 2/3.

    Vì thu hồi chỉ dựa vào ĐỒNG HỒ (mục `running` quá 2400s mới coi là mồ côi), mà người vận hành
    thì bấm ngay sau sự cố. Cách đúng: hỏi broker xem việc đó có còn chạy thật không.
    """
    from app.services.batch import orchestrator as mod

    pid, pages = await du_an(so_trang=2)
    day = DayViecGia()
    dp = BatchOrchestrator(max_concurrent_pages=1, dispatcher=day, stale_item_seconds=2400)
    me_id = dp.create_full_pipeline_run(pid, "google_fast")
    assert [m.status for m in _muc(me_id)].count(BatchItemStatus.running) == 1

    # Broker trả lời: KHÔNG có việc nào đang chạy (worker vừa khởi động lại).
    monkeypatch.setattr(mod, "viec_dang_song", lambda: set())
    assert dp.resume_failed(me_id) == 1, "bấm chạy lại ngay sau sự cố phải cứu được"

    muc = _muc(me_id)
    assert any(m.error_code == "stale_reclaimed" for m in muc) or any(
        m.status is BatchItemStatus.running for m in muc
    )
    assert _me(me_id).status is BatchStatus.running


async def test_khong_thu_hoi_viec_van_dang_chay_that(du_an, monkeypatch):
    """Ngược lại: việc CÒN chạy thì tuyệt đối không được xếp lại — sẽ thành hai job cùng ghi
    lên một trang."""
    from app.services.batch import orchestrator as mod

    pid, pages = await du_an(so_trang=1)
    dp = BatchOrchestrator(max_concurrent_pages=1, dispatcher=DayViecGia())
    me_id = dp.create_full_pipeline_run(pid, "google_fast")
    m = _muc(me_id)[0]
    assert m.status is BatchItemStatus.running

    monkeypatch.setattr(mod, "viec_dang_song", lambda: {str(m.current_job_id)})
    assert dp.thu_hoi_muc_mo_coi(me_id, hoi_broker=True) == 0
    assert _muc(me_id)[0].status is BatchItemStatus.running


async def test_khong_hoi_duoc_broker_thi_van_cho_mot_khoang_an_toan(du_an, monkeypatch):
    """Không worker nào trả lời: có thể broker đang trục trặc chứ không hẳn việc đã chết.
    Chờ một khoảng ngắn còn hơn xếp lại nhầm một việc đang chạy."""
    from datetime import datetime, timedelta, timezone

    from app.services.batch import orchestrator as mod

    pid, pages = await du_an(so_trang=1)
    dp = BatchOrchestrator(max_concurrent_pages=1, dispatcher=DayViecGia())
    me_id = dp.create_full_pipeline_run(pid, "google_fast")
    monkeypatch.setattr(mod, "viec_dang_song", lambda: None)
    assert dp.thu_hoi_muc_mo_coi(me_id, hoi_broker=True) == 0, "vừa mới chạy thì chưa thu hồi"

    with sync_session() as s:
        m = s.execute(sa.select(BatchItem).where(BatchItem.batch_run_id == me_id)).scalars().one()
        m.started_at = datetime.now(timezone.utc) - timedelta(seconds=120)
        s.commit()
    assert dp.thu_hoi_muc_mo_coi(me_id, hoi_broker=True) == 1
