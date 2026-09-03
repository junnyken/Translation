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
