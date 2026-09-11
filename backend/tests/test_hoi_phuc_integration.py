"""P3j — dọn job mồ côi khi worker khởi động lại.

Sinh ra từ sự cố thật ở pilot hosted 03/09: worker bị OOM killer giết giữa lúc chạy `inpaint`,
trang kẹt vĩnh viễn ở `ocr_done`, job biến mất không dấu vết, và **không có endpoint liệt kê job**
nên người vận hành không có cách nào biết vì sao.
"""
from __future__ import annotations

import uuid

import pytest

from app.core.db_sync import sync_session
from app.models import Job, Page
from app.models.enums import JobStatus, JobType, PageStatus
from app.workers.hoi_phuc import LY_DO, don_job_mo_coi


@pytest.fixture
async def du_lieu(client):
    r = await client.post("/api/v1/projects", json={
        "name": "P3j", "source_lang": "en", "target_lang": "vi", "intended_use": "personal"})
    pid = uuid.UUID(r.json()["id"])
    with sync_session() as s:
        page = Page(project_id=pid, image_path="a.png", order=1, status=PageStatus.ocr_done)
        s.add(page); s.flush()
        job = Job(type=JobType.inpaint, page_id=page.id, status=JobStatus.running)
        s.add(job); s.commit()
        return {"project_id": pid, "page_id": page.id, "job_id": job.id}


class TestDonJobMoCoi:
    async def test_che_do_chi_dem_KHONG_ghi_gi(self, du_lieu):
        with sync_session() as s:
            kq = don_job_mo_coi(s, ap_dung=False)
        assert kq.job_da_danh_dau >= 1
        with sync_session() as s:
            assert s.get(Job, du_lieu["job_id"]).status is JobStatus.running, \
                "chế độ chỉ-đếm đã GHI vào dữ liệu"

    async def test_job_mo_coi_bi_danh_dau_hong_KEM_LY_DO_doc_duoc(self, du_lieu):
        with sync_session() as s:
            don_job_mo_coi(s, ap_dung=True)
        with sync_session() as s:
            job = s.get(Job, du_lieu["job_id"])
            assert job.status is JobStatus.failed
            assert "worker_died" in job.error_log
            # Lý do phải viết cho NGƯỜI đọc, không chỉ là một mã lỗi.
            assert "hết bộ nhớ" in job.error_log
            assert "KHÔNG mất" in job.error_log, "phải trấn an rằng dữ liệu còn nguyên"

    async def test_KHONG_tu_chay_lai(self, du_lieu):
        """Tự chạy lại một job vừa làm chết worker vì hết bộ nhớ = giết nó lần nữa, thành vòng lặp."""
        with sync_session() as s:
            don_job_mo_coi(s, ap_dung=True)
        with sync_session() as s:
            con = [j for j in s.query(Job).filter(Job.page_id == du_lieu["page_id"]).all()]
            assert all(j.status is JobStatus.failed for j in con), "đã tự xếp lại việc"
            assert len(con) == 1, "đã tự tạo thêm job mới"

    async def test_KHONG_dung_toi_job_da_xong(self, client, du_lieu):
        """Job `done`/`failed` là lịch sử — dọn dẹp mà sửa lịch sử là hỏng bằng chứng."""
        with sync_session() as s:
            page_id = du_lieu["page_id"]
            xong = Job(type=JobType.detect, page_id=page_id, status=JobStatus.done)
            hong = Job(type=JobType.ocr, page_id=page_id, status=JobStatus.failed,
                       error_log="lý do cũ")
            s.add_all([xong, hong]); s.commit()
            id_xong, id_hong = xong.id, hong.id
        with sync_session() as s:
            don_job_mo_coi(s, ap_dung=True)
        with sync_session() as s:
            assert s.get(Job, id_xong).status is JobStatus.done
            assert s.get(Job, id_hong).error_log == "lý do cũ", "đã ghi đè lý do hỏng cũ"

    async def test_trang_ket_o_trang_thai_TAM_thi_duoc_lui(self, client):
        r = await client.post("/api/v1/projects", json={
            "name": "P3j kẹt", "source_lang": "en", "target_lang": "vi",
            "intended_use": "personal"})
        pid = uuid.UUID(r.json()["id"])
        with sync_session() as s:
            page = Page(project_id=pid, image_path="b.png", order=1, status=PageStatus.detecting)
            s.add(page); s.commit(); page_id = page.id
        with sync_session() as s:
            kq = don_job_mo_coi(s, ap_dung=True)
        assert kq.trang_da_lui >= 1
        with sync_session() as s:
            assert s.get(Page, page_id).status is PageStatus.queued

    async def test_KHONG_lui_trang_o_trang_thai_ON_DINH(self, du_lieu):
        """`ocr_done` là mốc ĐÃ XONG THẬT — job inpaint chết không làm nó sai đi.

        Lùi bừa ở đây là xoá mất công việc đã hoàn thành, tệ hơn hẳn việc để nguyên.
        """
        with sync_session() as s:
            don_job_mo_coi(s, ap_dung=True)
        with sync_session() as s:
            assert s.get(Page, du_lieu["page_id"]).status is PageStatus.ocr_done

    async def test_chay_lan_hai_khong_con_gi_de_don(self, du_lieu):
        with sync_session() as s:
            don_job_mo_coi(s, ap_dung=True)
        with sync_session() as s:
            assert don_job_mo_coi(s, ap_dung=True).tong == 0


class TestPhanLoaiLoiKhiDonMoCoi:
    """E22 (thu hẹp theo audit) — job mồ côi giờ có `error_class`/`exit_signal` có bằng chứng,
    thay vì chỉ một `error_log` cứng như nhau cho mọi nguyên nhân."""

    async def test_ma_thoat_137_gan_nhan_nghi_ngo_het_bo_nho(self, du_lieu, tmp_path, monkeypatch):
        p = tmp_path / "trang-thai.json"
        p.write_text(
            '{"trang_thai":"restarting","so_lan_chet":1,"ma_thoat_gan_nhat":137,'
            '"luc":"2026-09-09T07:17:29Z"}'
        )
        monkeypatch.setenv("WORKER_STATE_FILE", str(p))
        with sync_session() as s:
            don_job_mo_coi(s, ap_dung=True)
        with sync_session() as s:
            job = s.get(Job, du_lieu["job_id"])
            assert job.error_class == "resource_limit_suspected"
            assert job.exit_signal == "SIGKILL(137)"

    async def test_khong_co_tep_trang_thai_van_gan_worker_lost(
        self, du_lieu, tmp_path, monkeypatch,
    ):
        monkeypatch.setenv("WORKER_STATE_FILE", str(tmp_path / "khong-ton-tai.json"))
        with sync_session() as s:
            don_job_mo_coi(s, ap_dung=True)
        with sync_session() as s:
            job = s.get(Job, du_lieu["job_id"])
            assert job.error_class == "worker_lost"
            assert job.exit_signal is None

    async def test_che_do_chi_dem_KHONG_ghi_error_class(self, du_lieu, tmp_path, monkeypatch):
        p = tmp_path / "trang-thai.json"
        p.write_text('{"ma_thoat_gan_nhat":137}')
        monkeypatch.setenv("WORKER_STATE_FILE", str(p))
        with sync_session() as s:
            don_job_mo_coi(s, ap_dung=False)
        with sync_session() as s:
            job = s.get(Job, du_lieu["job_id"])
            assert job.error_class is None, "chế độ chỉ-đếm không được ghi gì"


class TestEndpointLietKeJob:
    async def test_tra_lich_su_job_kem_ly_do(self, client, du_lieu):
        with sync_session() as s:
            don_job_mo_coi(s, ap_dung=True)
        r = await client.get(f"/api/v1/pages/{du_lieu['page_id']}/jobs")
        assert r.status_code == 200
        js = r.json()
        assert len(js) >= 1
        hong = [j for j in js if j["status"] == "failed"]
        assert hong and "worker_died" in hong[0]["error_log"], \
            "giao diện không tra được LÝ DO trang đứng im"

    async def test_trang_khong_ton_tai_tra_404(self, client):
        r = await client.get(f"/api/v1/pages/{uuid.uuid4()}/jobs")
        assert r.status_code == 404

    async def test_moi_nhat_truoc(self, client, du_lieu):
        with sync_session() as s:
            s.add(Job(type=JobType.typeset, page_id=du_lieu["page_id"], status=JobStatus.done))
            s.commit()
        r = await client.get(f"/api/v1/pages/{du_lieu['page_id']}/jobs")
        moc = [j["created_at"] for j in r.json()]
        assert moc == sorted(moc, reverse=True), "không sắp mới nhất trước"


class TestMucMeTroVaoJobMoCoi:
    """E23 — mục mẻ trỏ vào job mồ côi phải nói thật, nếu không MẺ ĐỨNG IM 40 phút.

    Đo thật (lượt 24 trang, 2026-09-10): sau khi worker bị giết và bật lại, job được đánh `failed`
    đúng nhưng `BatchItem` vẫn `running` và trỏ vào đúng job đó. Kết quả: không job nào trong hàng
    đợi, 4 mục `pending` không bao giờ tới lượt vì chỗ chạy bị mục `running` kia giữ. Mẻ chỉ tự
    lành sau `batch_stale_item_seconds` = 2400s.
    """

    @staticmethod
    def _me_voi_muc(project_id, page_id, job_id, trang_thai_muc):
        from app.models import BatchItem, BatchRun
        from app.models.enums import BatchPipeline, BatchStatus

        with sync_session() as s:
            me = BatchRun(project_id=project_id, requested_pipeline=BatchPipeline.full_pipeline,
                          status=BatchStatus.running, total_pages=1)
            s.add(me); s.flush()
            muc = BatchItem(batch_run_id=me.id, page_id=page_id, page_order=1,
                            status=trang_thai_muc, current_job_id=job_id)
            s.add(muc); s.commit()
            return me.id, muc.id

    async def test_muc_running_bi_danh_hong_kem_ly_do(self, du_lieu):
        from app.models import BatchItem
        from app.models.enums import BatchItemStatus

        _, muc_id = self._me_voi_muc(du_lieu["project_id"], du_lieu["page_id"],
                                     du_lieu["job_id"], BatchItemStatus.running)
        with sync_session() as s:
            kq = don_job_mo_coi(s, ap_dung=True)
        assert kq.muc_me_da_danh_dau == 1

        with sync_session() as s:
            muc = s.get(BatchItem, muc_id)
        assert muc.status is BatchItemStatus.failed, "mục vẫn `running` ⇒ mẻ sẽ đứng im"
        assert muc.error_message == LY_DO[:1000]
        assert muc.finished_at is not None

    async def test_KHONG_dua_ve_pending(self, du_lieu):
        """`pending` = mẻ tự xếp lại NGAY, đúng thứ nguyên tắc "Không tự chạy lại" của tệp này cấm.

        Xếp lại một job vừa làm chết worker vì hết bộ nhớ là cách nhanh nhất để giết nó lần nữa.
        """
        from app.models import BatchItem
        from app.models.enums import BatchItemStatus

        _, muc_id = self._me_voi_muc(du_lieu["project_id"], du_lieu["page_id"],
                                     du_lieu["job_id"], BatchItemStatus.running)
        with sync_session() as s:
            don_job_mo_coi(s, ap_dung=True)
        with sync_session() as s:
            assert s.get(BatchItem, muc_id).status is not BatchItemStatus.pending

    async def test_ma_loi_KHONG_thuoc_nhom_tam_thoi(self, du_lieu):
        """Mã tạm thời sẽ bật đường tự thử lại của mẻ — đúng cái phải tránh."""
        from app.models import BatchItem
        from app.models.enums import BatchItemStatus
        from app.services.batch.errors import MA_TAM_THOI

        _, muc_id = self._me_voi_muc(du_lieu["project_id"], du_lieu["page_id"],
                                     du_lieu["job_id"], BatchItemStatus.running)
        with sync_session() as s:
            don_job_mo_coi(s, ap_dung=True)
        with sync_session() as s:
            ma = s.get(BatchItem, muc_id).error_code
        assert ma, "phải có mã lỗi để giao diện nói được vì sao"
        assert ma not in MA_TAM_THOI, f"'{ma}' là mã tạm thời ⇒ mẻ sẽ tự xếp lại, thành vòng lặp"

    async def test_che_do_chi_dem_KHONG_doi_muc_me(self, du_lieu):
        from app.models import BatchItem
        from app.models.enums import BatchItemStatus

        _, muc_id = self._me_voi_muc(du_lieu["project_id"], du_lieu["page_id"],
                                     du_lieu["job_id"], BatchItemStatus.running)
        with sync_session() as s:
            kq = don_job_mo_coi(s, ap_dung=False)
        assert kq.muc_me_da_danh_dau == 1, "chế độ chỉ-đếm vẫn phải ĐẾM được"
        with sync_session() as s:
            assert s.get(BatchItem, muc_id).status is BatchItemStatus.running, \
                "chế độ chỉ-đếm đã GHI vào mục mẻ"

    async def test_muc_da_xong_KHONG_bi_dung_toi(self, du_lieu):
        """Mục đã `completed` mà bị đánh hỏng thì mẻ báo sai và người dùng chạy lại việc đã xong."""
        from app.models import BatchItem
        from app.models.enums import BatchItemStatus

        _, muc_id = self._me_voi_muc(du_lieu["project_id"], du_lieu["page_id"],
                                     du_lieu["job_id"], BatchItemStatus.completed)
        with sync_session() as s:
            kq = don_job_mo_coi(s, ap_dung=True)
        assert kq.muc_me_da_danh_dau == 0
        with sync_session() as s:
            assert s.get(BatchItem, muc_id).status is BatchItemStatus.completed

    async def test_muc_ket_tu_luot_quet_TRUOC_van_duoc_cuu(self, du_lieu):
        """Job đã `failed` từ lượt quét trước mà mục vẫn `running` — bản sửa đầu BỎ SÓT cảnh này.

        Bản đầu lọc theo "job vừa bị đánh mồ côi trong lượt NÀY", nên mục kẹt từ lần khởi động
        trước không bao giờ được cứu và mẻ vẫn đứng im. Đúng cảnh đo được trên bàn thử E23.
        """
        from app.models import BatchItem
        from app.models.enums import BatchItemStatus

        # Giả lập: lượt quét trước đã đánh job hỏng, nhưng mục mẻ thì chưa ai đụng tới.
        with sync_session() as s:
            s.get(Job, du_lieu["job_id"]).status = JobStatus.failed
            s.commit()
        _, muc_id = self._me_voi_muc(du_lieu["project_id"], du_lieu["page_id"],
                                     du_lieu["job_id"], BatchItemStatus.running)

        with sync_session() as s:
            kq = don_job_mo_coi(s, ap_dung=True)
        assert kq.job_da_danh_dau == 0, "không còn job `running` nào để đánh"
        assert kq.muc_me_da_danh_dau == 1, "mục kẹt từ lượt trước vẫn phải được cứu"
        with sync_session() as s:
            assert s.get(BatchItem, muc_id).status is BatchItemStatus.failed

    async def test_muc_running_co_job_DANG_chay_thi_KHONG_dung_toi(self, du_lieu):
        """Job vẫn `queued` (chưa chạy) thì mục `running` chưa phải là cũ — đừng giết oan."""
        from app.models import BatchItem
        from app.models.enums import BatchItemStatus

        with sync_session() as s:
            job = Job(type=JobType.inpaint, page_id=du_lieu["page_id"], status=JobStatus.queued)
            s.add(job); s.commit()
            job_id = job.id
        _, muc_id = self._me_voi_muc(du_lieu["project_id"], du_lieu["page_id"],
                                     job_id, BatchItemStatus.running)

        with sync_session() as s:
            don_job_mo_coi(s, ap_dung=True)
        with sync_session() as s:
            assert s.get(BatchItem, muc_id).status is BatchItemStatus.running
