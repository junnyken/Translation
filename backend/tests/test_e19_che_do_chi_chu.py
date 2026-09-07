"""E19 — chế độ `chi_chu`: đọc chữ xong đi thẳng sang dịch, bỏ xoá chữ và căn chữ.

Sinh ra cho tiện ích đọc truyện: nó **phủ** chữ dịch lên ảnh gốc trên trang web, nên không cần
xoá chữ gốc lẫn căn chữ vào bong bóng.

Đo 05/09 (`docs/REPORT_E19_0_DO_COND_CHAN.md`): bỏ hai bước đó cắt 6–17s mỗi trang và hạ RSS đỉnh
khoảng 800 MB. Nó **không** làm trang nhanh lên một bậc — nhận diện vẫn ~40–50s và đó mới là chỗ
tốn thời gian. Test này không khẳng định gì về tốc độ; nó chỉ khẳng định **đường đi đúng**.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa

from app.core.db_sync import sync_session
from app.models import Job, Page, Project
from app.models.enums import ChePipeline, JobStatus, JobType, PageStatus
from app.workers.tasks import run_detect_job, run_ocr_job, run_translate_job

from tests.test_translate_task_integration import _job_id, _region

pytestmark = pytest.mark.anyio


def _dat_che_do(project_id: str, che: ChePipeline) -> None:
    with sync_session() as s:
        s.get(Project, uuid.UUID(project_id)).che_do_pipeline = che
        s.commit()


def _viec(page_id: str, loai: JobType):
    with sync_session() as s:
        return list(s.execute(
            sa.select(Job).where(Job.page_id == uuid.UUID(page_id), Job.type == loai)
        ).scalars())


async def _den_ocr_xong(client, sample_page_image, fake_detector, fake_ocr_engine, che):
    """Chạy detect → OCR bằng đúng đường thật, với chapter ở chế độ `che`."""
    proj = await client.post(
        "/api/v1/projects",
        json={"name": "E19", "source_lang": "ja", "intended_use": "personal"},
    )
    pid = proj.json()["id"]
    _dat_che_do(pid, che)
    up = await client.post(
        f"/api/v1/projects/{pid}/pages",
        files={"file": ("p.png", sample_page_image, "image/png")},
    )
    page_id = up.json()["page_id"]
    fake_detector(regions=[_region(100, 100), _region(700, 100)])
    run_detect_job(up.json()["job_id"])
    fake_ocr_engine(per_call=lambda i, b: (["TRAI", "PHAI"][i % 2], 0.95))
    run_ocr_job(_job_id(page_id, JobType.ocr))
    return pid, page_id


class TestDuongDi:
    async def test_chi_chu_KHONG_xep_viec_xoa_chu(
        self, client, sample_page_image, fake_detector, fake_ocr_engine
    ):
        _, page_id = await _den_ocr_xong(
            client, sample_page_image, fake_detector, fake_ocr_engine, ChePipeline.chi_chu
        )
        assert _viec(page_id, JobType.inpaint) == [], "vẫn xếp việc xoá chữ ở chế độ chỉ-chữ"
        assert len(_viec(page_id, JobType.translate)) == 1, "không xếp việc dịch"

    async def test_day_du_VAN_xep_viec_xoa_chu(
        self, client, sample_page_image, fake_detector, fake_ocr_engine
    ):
        """Chốt chống hồi quy: chế độ cũ không được đổi hành vi."""
        _, page_id = await _den_ocr_xong(
            client, sample_page_image, fake_detector, fake_ocr_engine, ChePipeline.day_du
        )
        assert len(_viec(page_id, JobType.inpaint)) == 1
        assert _viec(page_id, JobType.translate) == [], "dịch trước khi xoá chữ là sai thứ tự"

    async def test_chi_chu_dich_duoc_tu_ocr_done_va_KHONG_can_chu(
        self, client, sample_page_image, fake_detector, fake_ocr_engine, fake_translator
    ):
        _, page_id = await _den_ocr_xong(
            client, sample_page_image, fake_detector, fake_ocr_engine, ChePipeline.chi_chu
        )
        with sync_session() as s:
            assert s.get(Page, uuid.UUID(page_id)).status is PageStatus.ocr_done

        run_translate_job(_job_id(page_id, JobType.translate))

        with sync_session() as s:
            assert s.get(Page, uuid.UUID(page_id)).status is PageStatus.translated
        assert _viec(page_id, JobType.typeset) == [], (
            "vẫn xếp việc căn chữ — đốt thời gian cho kết quả không ai xem"
        )

    async def test_day_du_dich_khi_CHUA_xoa_chu_thi_van_bi_tu_choi(
        self, client, sample_page_image, fake_detector, fake_ocr_engine, fake_translator
    ):
        """Nới điều kiện chỉ được nới cho `chi_chu`. Ở chế độ đầy đủ, dịch khi chưa xoá chữ vẫn sai."""
        pid, page_id = await _den_ocr_xong(
            client, sample_page_image, fake_detector, fake_ocr_engine, ChePipeline.day_du
        )
        with sync_session() as s:
            viec = Job(type=JobType.translate, page_id=uuid.UUID(page_id), status=JobStatus.queued)
            s.add(viec); s.commit(); jid = str(viec.id)
        kq = run_translate_job(jid)
        assert kq["status"] == "failed"
        assert "precondition_failed" in kq["error"]


class TestStartedAt:
    async def test_job_ghi_lai_luc_BAT_DAU_CHAY(
        self, client, sample_page_image, fake_detector, fake_ocr_engine
    ):
        """Không có mốc này thì từ API không phân biệt được 'đang xếp hàng' với 'đang chạy'."""
        _, page_id = await _den_ocr_xong(
            client, sample_page_image, fake_detector, fake_ocr_engine, ChePipeline.chi_chu
        )
        with sync_session() as s:
            xong = list(s.execute(
                sa.select(Job).where(Job.page_id == uuid.UUID(page_id),
                                     Job.status == JobStatus.done)
            ).scalars())
        assert xong, "chưa có job nào xong — test rỗng nghĩa"
        for j in xong:
            assert j.started_at is not None, f"job {j.type} xong mà không có started_at"
            assert j.started_at >= j.created_at

    async def test_API_tra_ra_started_at_chu_khong_giu_trong_CSDL(
        self, client, sample_page_image, fake_detector, fake_ocr_engine
    ):
        """Thêm cột mà quên lộ ra API thì E19-3 vô hình với tiện ích — đúng lỗi suýt mắc."""
        _, page_id = await _den_ocr_xong(
            client, sample_page_image, fake_detector, fake_ocr_engine, ChePipeline.chi_chu
        )
        tra = await client.get(f"/api/v1/pages/{page_id}/jobs")
        assert tra.status_code == 200, tra.text
        ds = tra.json()
        ds = ds if isinstance(ds, list) else ds.get("items", [])
        assert ds, "không có job nào — test rỗng nghĩa"
        assert all("started_at" in j for j in ds), "API không trả started_at"
        assert any(j["started_at"] for j in ds), "job đã chạy mà started_at vẫn rỗng"

    def test_KHONG_con_cho_nao_dat_running_bang_tay(self):
        """Quét mã nguồn: `status = running` từng có ở 12 chỗ. Sửa tay từng chỗ là chắc chắn sót
        một, và chỗ sót chỉ lộ ra khi người dùng thấy 'đang xếp hàng' trong lúc việc đã xong."""
        ma = Path("app/workers/tasks.py").read_text(encoding="utf-8")
        # Bỏ thân của chính `danh_dau_dang_chay` ra khỏi phạm vi quét: nó PHẢI chứa phép gán
        # trực tiếp. Phép thay hàng loạt lúc đầu đã thay luôn dòng đó và biến hàm thành đệ quy
        # vô hạn — bộ test nhận diện bắt được bằng `RecursionError`.
        ngoai_ham = re.sub(
            r"def danh_dau_dang_chay\(.*?\n(?=\n\ndef )", "", ma, flags=re.S
        )
        con = re.findall(r"^\s*job\.status = JobStatus\.running\s*$", ngoai_ham, re.M)
        assert con == [], f"{len(con)} chỗ đặt running bằng tay — dùng danh_dau_dang_chay()"
        assert "def danh_dau_dang_chay(" in ma
        assert ma.count("danh_dau_dang_chay(job)") >= 10, "quá ít chỗ gọi — có phải đã bị gỡ?"
