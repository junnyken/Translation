"""E42 — không đẩy job trùng cho cùng một trang.

## Lỗi thật, đo trên HAI bộ dữ liệu độc lập

Production (E35, trang `a744aede`, 21 vùng):

    translate  2 job · token 935 + 959 = 1894   -> lãng phí 959 token (51%)
    typeset    4 job · mỗi lần "xoá 21 kết quả cũ" rồi ghi lại y hệt
    inpaint    2 job

DB dev, 38 trang — **xếp hạng chính là bằng chứng cho nguyên nhân**:

    typeset 2,92 · translate 1,68 · inpaint 1,42 · ocr 1,13 · detect 1,11 job/trang
                                                              ^^^^^^^^^^
                    `detect` là bước DUY NHẤT có trạng thái đang-chạy (`detecting`),
                    và nó trùng ÍT NHẤT. Bốn bước còn lại đều cao hơn.

## Vì sao KHÔNG phải luật toàn cục

Có 22 chỗ tạo `Job`. Nhiều chỗ theo **vùng** (`page_id=region.page_id`):
`enqueue_refit_after_retranslate` tạo một job `typeset` cho MỖI vùng — dịch lại 16 vùng ⇒ 16 job,
và đó là **đúng thiết kế**. 15 đường trong `routes.py` là do người dùng bấm. Chắn theo (trang,
loại) ở những chỗ đó là chặn oan, nên chắn chỉ đặt ở các đường TỰ ĐỘNG.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.db_sync import sync_session
from app.models import Job, Page, Project, TextRegion
from app.models.enums import (
    IntendedUse,
    JobStatus,
    JobType,
    PageStatus,
    SourceLang,
    TargetLang,
)
from app.services.job_status import job_chua_ket_thuc, nguong_qua_han_giay


@pytest.fixture
def khong_goi_broker(monkeypatch):
    """Chặn `apply_async`. Fixture `no_broker_for_chained_ocr` của conftest chỉ chặn `.delay`,
    còn `day_viec_buoc` (đường của MẺ) đẩy bằng `apply_async` — không chặn thì test ngồi retry
    Redis 20 lần rồi đỏ vì lý do chẳng liên quan gì tới thứ đang kiểm."""
    from app.workers import tasks

    da_day: list = []
    for ten in ("run_detect_job", "run_ocr_job", "run_inpaint_job", "run_translate_job",
                "run_typeset_job"):
        task = getattr(tasks, ten, None)
        if task is not None:
            monkeypatch.setattr(
                task, "apply_async",
                lambda args=None, countdown=0, **k: da_day.append((args, countdown)),
            )
    return da_day


def _trang_moi(s) -> Page:
    pr = Project(name=f"E42 {uuid.uuid4().hex[:8]}", source_lang=SourceLang.en,
                 target_lang=TargetLang.vi, intended_use=IntendedUse.study)
    s.add(pr)
    s.flush()
    pg = Page(project_id=pr.id, order=1, image_path=f"x/{uuid.uuid4().hex}.png",
              status=PageStatus.ocr_done)
    s.add(pg)
    s.flush()
    return pg


def _job(s, page_id, loai, status, tuoi_giay: float | None = None) -> Job:
    j = Job(type=loai, page_id=page_id, status=status)
    if tuoi_giay is not None:
        luc = datetime.now(timezone.utc) - timedelta(seconds=tuoi_giay)
        j.started_at = luc
        j.heartbeat_at = luc
    s.add(j)
    s.flush()
    return j


class TestNhanBietJobConSong:
    def test_khong_co_job_nao_thi_None(self):
        with sync_session() as s:
            pg = _trang_moi(s)
            assert job_chua_ket_thuc(s, pg.id, JobType.inpaint) is None

    def test_job_queued_la_con_song(self):
        with sync_session() as s:
            pg = _trang_moi(s)
            j = _job(s, pg.id, JobType.inpaint, JobStatus.queued)
            assert job_chua_ket_thuc(s, pg.id, JobType.inpaint).id == j.id

    def test_job_running_con_moi_la_con_song(self):
        with sync_session() as s:
            pg = _trang_moi(s)
            j = _job(s, pg.id, JobType.inpaint, JobStatus.running, tuoi_giay=5)
            assert job_chua_ket_thuc(s, pg.id, JobType.inpaint).id == j.id

    def test_job_running_QUA_HAN_la_mo_coi__phai_cho_day_lai(self):
        """Không có nhánh này thì MỘT lần worker chết sẽ chặn trang đó vĩnh viễn."""
        with sync_session() as s:
            pg = _trang_moi(s)
            qua = nguong_qua_han_giay(JobType.inpaint) + 60
            _job(s, pg.id, JobType.inpaint, JobStatus.running, tuoi_giay=qua)
            assert job_chua_ket_thuc(s, pg.id, JobType.inpaint) is None

    @pytest.mark.parametrize("tt", [JobStatus.done, JobStatus.failed])
    def test_job_da_ket_thuc_khong_chan(self, tt):
        with sync_session() as s:
            pg = _trang_moi(s)
            _job(s, pg.id, JobType.inpaint, tt)
            assert job_chua_ket_thuc(s, pg.id, JobType.inpaint) is None

    def test_khac_LOAI_thi_khong_chan(self):
        """Chắn theo loại: job dịch đang bay không được chặn việc xoá chữ."""
        with sync_session() as s:
            pg = _trang_moi(s)
            _job(s, pg.id, JobType.translate, JobStatus.queued)
            assert job_chua_ket_thuc(s, pg.id, JobType.inpaint) is None

    def test_khac_TRANG_thi_khong_chan(self):
        with sync_session() as s:
            a, b = _trang_moi(s), _trang_moi(s)
            _job(s, a.id, JobType.inpaint, JobStatus.queued)
            assert job_chua_ket_thuc(s, b.id, JobType.inpaint) is None

    def test_running_khong_co_moc_thoi_gian_thi_coi_la_con_song(self):
        """Job tạo trước E22 không có `started_at`/`heartbeat_at` — không đủ bằng chứng để gọi
        là mồ côi. Thà bỏ một lượt đẩy còn hơn đẩy trùng."""
        with sync_session() as s:
            pg = _trang_moi(s)
            j = _job(s, pg.id, JobType.inpaint, JobStatus.running)  # không set mốc
            assert job_chua_ket_thuc(s, pg.id, JobType.inpaint).id == j.id


class TestDuongTuDongKhongDayTrung:
    """Nối vào đường chạy THẬT — gọi đúng hàm mà pipeline gọi, không phải bản chép lại."""

    def test_enqueue_inpaint_goi_hai_lan_chi_ra_MOT_job(self, no_broker_for_chained_ocr):
        from app.workers.tasks import enqueue_inpaint_after_ocr

        with sync_session() as s:
            pg = _trang_moi(s)
            pid = pg.id
            s.commit()

        a = enqueue_inpaint_after_ocr(pid)
        b = enqueue_inpaint_after_ocr(pid)
        assert a is not None and a == b, f"lượt hai tạo job MỚI: {a} vs {b}"

        with sync_session() as s:
            n = s.query(Job).filter_by(page_id=pid, type=JobType.inpaint).count()
        assert n == 1, f"có {n} job inpaint cho một trang"

    def test_enqueue_translate_goi_hai_lan_chi_ra_MOT_job(self, no_broker_for_chained_ocr):
        """Bước ĐẮT NHẤT khi trùng: production đo được 959 token lãng phí cho một lượt."""
        from app.workers.tasks import enqueue_translate_after_inpaint

        with sync_session() as s:
            pg = _trang_moi(s)
            pid = pg.id
            s.commit()

        a = enqueue_translate_after_inpaint(pid)
        b = enqueue_translate_after_inpaint(pid)
        assert a == b
        with sync_session() as s:
            assert s.query(Job).filter_by(page_id=pid, type=JobType.translate).count() == 1

    def test_job_mo_coi_thi_VAN_day_lai_duoc(self, no_broker_for_chained_ocr):
        """Chống rỗng nghĩa theo chiều ngược: chắn không được biến thành khoá vĩnh viễn."""
        from app.workers.tasks import enqueue_inpaint_after_ocr

        with sync_session() as s:
            pg = _trang_moi(s)
            pid = pg.id
            qua = nguong_qua_han_giay(JobType.inpaint) + 60
            _job(s, pid, JobType.inpaint, JobStatus.running, tuoi_giay=qua)
            s.commit()

        moi = enqueue_inpaint_after_ocr(pid)
        assert moi is not None
        with sync_session() as s:
            assert s.query(Job).filter_by(page_id=pid, type=JobType.inpaint).count() == 2, (
                "job mồ côi đã chặn mất lượt đẩy lại"
            )


class TestKhongChanOanDuongTheoVUNG:
    """Ranh giới quan trọng nhất của E42 — và là chỗ suýt sửa sai."""

    def test_refit_hai_VUNG_khac_nhau_van_ra_HAI_job(self, no_broker_for_chained_ocr):
        """`enqueue_refit_after_retranslate` tạo job `typeset` theo VÙNG. Hai vùng ⇒ hai job.

        Nếu chắn E42 áp cả ở đây thì dịch lại vùng thứ hai sẽ **không căn lại chữ** — bản dịch
        mới nằm trong CSDL mà ảnh vẫn của bản cũ, đúng thứ hàm đó sinh ra để tránh.
        """
        from app.workers.tasks import enqueue_refit_after_retranslate

        with sync_session() as s:
            pg = _trang_moi(s)
            v1 = TextRegion(page_id=pg.id, bbox_x=10, bbox_y=10, bbox_w=80, bbox_h=40,
                            confidence=0.9, reading_order=1)
            v2 = TextRegion(page_id=pg.id, bbox_x=10, bbox_y=80, bbox_w=80, bbox_h=40,
                            confidence=0.9, reading_order=2)
            s.add_all([v1, v2])
            s.flush()
            pid, id1, id2 = pg.id, v1.id, v2.id
            s.commit()

        a = enqueue_refit_after_retranslate(id1)
        b = enqueue_refit_after_retranslate(id2)
        assert a is not None and b is not None and a != b

        with sync_session() as s:
            n = s.query(Job).filter_by(page_id=pid, type=JobType.typeset).count()
        assert n == 2, f"refit hai vùng chỉ ra {n} job — chắn đã chặn oan đường theo vùng"


class TestChongRongNghia:
    """Chứng minh các test trên đo ĐÚNG cái chắn, không phải đo một tình huống vô hại.

    Lần đầu tôi định chứng minh bằng cách sửa mã rồi chạy lại bằng tay. Làm thành test thường
    trú thì phép chứng minh còn sống mãi: ai bỏ chắn đi mà thấy bộ test vẫn xanh thì test này
    là cái đỏ.
    """

    def test_TAT_chan_thi_ra_HAI_job(self, monkeypatch):
        from app.workers import tasks

        with sync_session() as s:
            pg = _trang_moi(s)
            pid = pg.id
            s.commit()

        monkeypatch.setattr(tasks, "job_chua_ket_thuc", lambda *a, **k: None)
        a = tasks.enqueue_inpaint_after_ocr(pid)
        b = tasks.enqueue_inpaint_after_ocr(pid)
        assert a != b, "không có chắn mà vẫn ra một job ⇒ test kia xanh vì lý do khác"

        with sync_session() as s:
            n = s.query(Job).filter_by(page_id=pid, type=JobType.inpaint).count()
        assert n == 2, f"tắt chắn mà chỉ ra {n} job — phép chứng minh này vô nghĩa"

    def test_TAT_chan_thi_me_cung_day_trung(self, monkeypatch, khong_goi_broker):
        from app.services.batch import dispatch

        with sync_session() as s:
            pg = _trang_moi(s)
            pid = pg.id
            s.commit()

        monkeypatch.setattr(dispatch, "job_chua_ket_thuc", lambda *a, **k: None)
        a = dispatch.day_viec_buoc(pid, "inpaint")
        b = dispatch.day_viec_buoc(pid, "inpaint")
        assert a != b
        with sync_session() as s:
            assert s.query(Job).filter_by(page_id=pid, type=JobType.inpaint).count() == 2

    def test_BAT_chan_thi_me_chi_day_MOT_lan(self, khong_goi_broker):
        from app.services.batch import dispatch

        with sync_session() as s:
            pg = _trang_moi(s)
            pid = pg.id
            s.commit()

        a = dispatch.day_viec_buoc(pid, "inpaint")
        b = dispatch.day_viec_buoc(pid, "inpaint")
        assert a == b, f"mẻ vẫn đẩy trùng: {a} vs {b}"
        with sync_session() as s:
            assert s.query(Job).filter_by(page_id=pid, type=JobType.inpaint).count() == 1
