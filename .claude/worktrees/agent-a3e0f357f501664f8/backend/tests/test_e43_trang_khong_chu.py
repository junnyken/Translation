"""E43 — trang TRANH THUẦN (0 vùng chữ) phải đi hết chuỗi, không kẹt và không bị coi là lỗi.

Phát hiện từ lượt chạy chapter 24 trang THẬT trên production 24-09: chapter đứng im ở 19/24, 5
trang kẹt vĩnh viễn ở `detected`. Nguyên nhân: `detect` chạy xong xác nhận 0 vùng, rồi `_run_ocr`
đánh dấu job `failed` kèm thông điệp **sai sự thật** ("chạy detect trước" — trong khi detect đã
xong).

Bài nguy hiểm nhất trong file này là `test_detection_failed_VAN_bi_loai`: bản sửa này rất dễ
"sửa quá tay" thành nuốt luôn lỗi thật. `detected` + 0 vùng = **máy đã xem và xác nhận không có
chữ**; `detection_failed` = **máy xem hỏng**. Gộp hai thứ sẽ làm trang hỏng thật lặng lẽ trôi vào
file giao cho người đọc.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from app.core.db_sync import sync_session
from app.models import Job, Page
from app.models.enums import JobStatus, JobType, OCREngine, PageStatus
from app.workers.tasks import (
    khong_co_vung,
    run_detect_job,
    run_inpaint_job,
    run_ocr_job,
    run_translate_job,
    run_typeset_job,
    trang_khong_co_chu,
)

from tests.test_translate_task_integration import _job_id, _region

pytestmark = pytest.mark.anyio


async def _tao_trang(client, sample_page_image) -> tuple[str, str, str]:
    proj = await client.post("/api/v1/projects", json={
        "name": "E43", "source_lang": "en", "intended_use": "study",
    })
    pid = proj.json()["id"]
    up = await client.post(
        f"/api/v1/projects/{pid}/pages",
        files={"file": ("p.png", sample_page_image, "image/png")},
    )
    return pid, up.json()["page_id"], up.json()["job_id"]


def _trang_thai(page_id: str) -> PageStatus:
    with sync_session() as s:
        return s.get(Page, uuid.UUID(page_id)).status


def _job_hong(page_id: str) -> list[str]:
    with sync_session() as s:
        return [
            f"{j.type.value}: {j.error_log}"
            for j in s.execute(
                sa.select(Job).where(Job.page_id == uuid.UUID(page_id))
            ).scalars()
            if j.status is JobStatus.failed
        ]


class TestTrangTranhThuanDiHetChuoi:
    async def test_khong_ket_o_detected_va_KHONG_co_job_nao_hong(
        self, client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter,
        no_broker_for_chained_ocr,
    ):
        """Đúng kịch bản đã gãy trên production."""
        _pid, pg, detect_job = await _tao_trang(client, sample_page_image)

        fake_detector(regions=[])                      # trang tranh thuần: KHÔNG có bong bóng nào
        run_detect_job(detect_job)
        assert _trang_thai(pg) is PageStatus.detected
        assert khong_co_vung.__name__                   # helper tồn tại, dùng ở dưới

        # Chạy từng bước như worker thật sẽ làm (broker bị chặn trong test nên gọi tay).
        run_ocr_job(_job_id(pg, JobType.ocr))
        assert _trang_thai(pg) is PageStatus.ocr_done, "kẹt ngay ở bước đọc chữ"

        run_inpaint_job(_job_id(pg, JobType.inpaint))
        assert _trang_thai(pg) is PageStatus.inpainted

        run_translate_job(_job_id(pg, JobType.translate))
        assert _trang_thai(pg) is PageStatus.translated

        run_typeset_job(_job_id(pg, JobType.typeset))
        assert _trang_thai(pg) is PageStatus.typeset_done, "không về được đích"

        assert _job_hong(pg) == [], f"còn job bị đánh dấu hỏng: {_job_hong(pg)}"

    async def test_KHONG_dat_clean_image_path(
        self, client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter,
        no_broker_for_chained_ocr,
    ):
        """Ảnh clean phải để NULL: chưa từng có lượt xoá chữ nào chạy.

        Trỏ `clean_image_path` sang chính `image_path` cho gọn là **mất ảnh gốc**: lượt chạy lại
        bước xoá chữ gọi `storage.delete(old_clean_rel)`.
        """
        _pid, pg, detect_job = await _tao_trang(client, sample_page_image)
        fake_detector(regions=[])
        run_detect_job(detect_job)
        run_ocr_job(_job_id(pg, JobType.ocr))
        run_inpaint_job(_job_id(pg, JobType.inpaint))

        with sync_session() as s:
            page = s.get(Page, uuid.UUID(pg))
            assert page.clean_image_path is None
            assert page.image_path, "ảnh gốc phải còn nguyên"


class TestKhongNuotMatLoiThat:
    async def test_detection_failed_VAN_bi_loai(self, client, sample_page_image):
        """**Bài canh nguy hiểm nhất.** `detection_failed` KHÔNG được coi là 'trang không chữ'.

        Cả hai đều có 0 vùng. Phân biệt duy nhất là `page.status`. Bỏ phân biệt đó thì trang mà
        máy XEM HỎNG sẽ lặng lẽ trôi vào file giao cho người đọc.
        """
        _pid, pg, _j = await _tao_trang(client, sample_page_image)
        with sync_session() as s:
            page = s.get(Page, uuid.UUID(pg))
            page.status = PageStatus.detecting
            s.commit()
            page = s.get(Page, uuid.UUID(pg))
            page.status = PageStatus.detection_failed
            s.commit()

            page = s.get(Page, uuid.UUID(pg))
            assert khong_co_vung(s, page.id) is True, "đúng là 0 vùng"
            assert trang_khong_co_chu(s, page) is False, (
                "detection_failed bị nhận nhầm thành 'trang không có chữ' — "
                "trang hỏng sẽ trôi vào file xuất"
            )

    async def test_trang_CO_chu_khong_doi_hanh_vi(
        self, client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter,
        no_broker_for_chained_ocr,
    ):
        """Đối chứng hồi quy: trang có bong bóng vẫn đi đường cũ, không rẽ vào nhánh E43."""
        _pid, pg, detect_job = await _tao_trang(client, sample_page_image)
        fake_detector(regions=[_region(100, 100)])
        run_detect_job(detect_job)
        fake_ocr_engine(per_call=lambda i, b: ("HELLO", 0.95), engine_enum=OCREngine.manga_ocr)
        run_ocr_job(_job_id(pg, JobType.ocr))

        assert _trang_thai(pg) is PageStatus.ocr_done
        with sync_session() as s:
            assert khong_co_vung(s, uuid.UUID(pg)) is False


class TestDuongCuuTrangDaKet:
    """`retry-ocr` là đường DUY NHẤT cứu trang đã kẹt từ trước bản vá — không được chặn nó.

    Đo thật trên production 24-09: 5 trang kẹt, cả 5 lượt `retry-ocr` trả `409` kèm thông điệp
    "chạy detect trước" trong khi detect ĐÃ xong. Thông điệp sai sự thật đẩy người vận hành đi
    chạy lại detect — việc vô ích, vì detect sẽ lại cho ra đúng 0 vùng.

    Đây là chốt chặn thứ NĂM và là chốt duy nhất ở tầng API. Phép quét lần đầu của tôi **bỏ sót**
    nó, vì tôi chỉ quét `tasks.py` theo trí nhớ thay vì quét cả repo theo mẫu.
    """

    async def test_trang_tranh_thuan_retry_ocr_duoc(
        self, client, sample_page_image, fake_detector, no_broker_for_chained_ocr,
    ):
        _pid, pg, detect_job = await _tao_trang(client, sample_page_image)
        fake_detector(regions=[])
        run_detect_job(detect_job)
        assert _trang_thai(pg) is PageStatus.detected

        r = await client.post(f"/api/v1/pages/{pg}/retry-ocr")
        assert r.status_code == 202, (
            f"đường cứu trang kẹt bị chặn: {r.status_code} {r.text[:120]}"
        )

    async def test_trang_CHUA_detect_van_bi_chan(self, client, sample_page_image):
        """Chiều ngược: trang chưa detect xong thì 409 mới ĐÚNG — đó mới là 'chạy detect trước'."""
        _pid, pg, _j = await _tao_trang(client, sample_page_image)
        assert _trang_thai(pg) is PageStatus.queued        # chưa detect lần nào

        r = await client.post(f"/api/v1/pages/{pg}/retry-ocr")
        assert r.status_code == 409


class TestXemTruocKhopFileThat:
    async def test_export_preview_dem_ca_trang_khong_chu(
        self, client, sample_page_image, fake_detector, no_broker_for_chained_ocr,
    ):
        """Xem-trước phải đếm trang tranh thuần — chỗ E38 bỏ sót.

        Đo thật trên production 24-09: xem-trước báo 19 trang trong khi file ZIP có đủ 24.
        """
        pid, pg, detect_job = await _tao_trang(client, sample_page_image)
        fake_detector(regions=[])
        run_detect_job(detect_job)
        assert _trang_thai(pg) is PageStatus.detected      # dữ liệu CŨ: kẹt ở detected

        r = await client.get(f"/api/v1/projects/{pid}/export-preview")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["page_count"] == 1, (
            f"xem-trước bỏ sót trang không chữ: sẽ xuất {d['page_count']}/{d['total_page_count']}"
        )
        assert d["skipped_page_count"] == 0
