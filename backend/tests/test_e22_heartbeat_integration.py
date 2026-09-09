"""E22 (thu hẹp theo audit) — `danh_dau_dang_chay()` phải đặt CẢ `heartbeat_at` lẫn `started_at`.

Chỉ MỘT bài test cho việc này: `danh_dau_dang_chay` đã có test riêng (E19,
`test_e19_che_do_chi_chu.py`) canh nó là điểm gọi DUY NHẤT đặt `status=running` — bài này chỉ
thêm đúng phần E22 cần, không lặp lại phần đã canh.
"""
from __future__ import annotations

import uuid

from app.core.db_sync import sync_session
from app.models import Job, Page
from app.models.enums import JobStatus, JobType, PageStatus
from app.workers.tasks import danh_dau_dang_chay


async def test_danh_dau_dang_chay_dat_heartbeat_bang_started_at(client):
    r = await client.post("/api/v1/projects", json={
        "name": "E22 heartbeat", "source_lang": "en", "target_lang": "vi",
        "intended_use": "personal"})
    pid = uuid.UUID(r.json()["id"])
    with sync_session() as s:
        page = Page(project_id=pid, image_path="a.png", order=1, status=PageStatus.queued)
        s.add(page); s.flush()
        job = Job(type=JobType.detect, page_id=page.id, status=JobStatus.queued)
        s.add(job); s.commit()
        job_id = job.id

    with sync_session() as s:
        job = s.get(Job, job_id)
        assert job.heartbeat_at is None, "chưa chạy thì chưa có nhịp tim"
        danh_dau_dang_chay(job)
        s.commit()

    with sync_session() as s:
        job = s.get(Job, job_id)
        assert job.status is JobStatus.running
        assert job.heartbeat_at is not None
        assert job.heartbeat_at == job.started_at, \
            "nhịp tim ban đầu phải trùng lúc bắt đầu chạy — không tính giây lẻ do 2 lệnh gán riêng"
