"""E47 — chỉ xoá chữ ở vùng ĐỌC RA CHỮ THẬT.

## Thiệt hại đã chứng minh, không phải lo xa

Khung nhận diện còn làm **mask cho LaMa**. Chạy bước xoá chữ với đúng các vùng
`comic-text-detector` khoanh trên một trang truyện có hiệu ứng phát sáng: **toàn bộ ánh sáng,
tia lấp lánh và vật phát quang bị xoá sạch**, chỉ còn nền tối phẳng. Model cũ khoanh 8 vùng thì
5 trong số đó là nét vẽ phát sáng, không phải chữ.

## Hai chiều đều phải canh

Bài dễ sai nhất ở đây là `test_vung_CHU_THAT_van_bi_xoa`: nới tay quá thì chữ gốc không được xoá,
và bước căn chữ sẽ vẽ chữ dịch **đè lên chữ gốc** — tệ hơn hẳn trạng thái ban đầu. Một bản vá chỉ
canh chiều "giữ nét vẽ" sẽ xanh trong khi sản phẩm hỏng theo chiều kia.
"""
from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from app.core.db_sync import sync_session
from app.models import Page
from app.models.enums import JobType, OCREngine, PageStatus
from app.workers.tasks import run_detect_job, run_inpaint_job, run_ocr_job

from tests.test_translate_task_integration import _job_id, _region

pytestmark = pytest.mark.anyio


async def _trang(client, anh):
    proj = await client.post("/api/v1/projects", json={
        "name": "E47", "source_lang": "en", "intended_use": "study"})
    pid = proj.json()["id"]
    up = await client.post(f"/api/v1/projects/{pid}/pages",
                           files={"file": ("p.png", anh, "image/png")})
    return pid, up.json()["page_id"], up.json()["job_id"]


def _clean_path(page_id):
    with sync_session() as s:
        return s.get(Page, uuid.UUID(page_id)).clean_image_path


class TestGiuNetVe:
    async def test_vung_NHIEU_khong_lot_vao_mask(
        self, client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter,
        no_broker_for_chained_ocr,
    ):
        """Vùng đọc ra rác ở điểm tin cậy thấp phải bị loại KHỎI MASK.

        Số đo đứng sau ngưỡng: trên 27 vùng thật, vùng nhiễu (nét khói vẽ) được 1 ký tự ở
        confidence 0,38; MỌI vùng chữ thật được 0,96 trở lên.
        """
        _pid, pg, dj = await _trang(client, sample_page_image)
        fake_detector(regions=[_region(100, 100), _region(400, 400)])
        run_detect_job(dj)
        # vùng 0 = chữ thật · vùng 1 = nhiễu (đúng con số đo được từ nét khói vẽ)
        fake_ocr_engine(
            per_call=lambda i, b: ("Pepper, you bring shame", 0.99) if i == 0 else ("2", 0.38),
            engine_enum=OCREngine.paddle_ocr,
        )
        run_ocr_job(_job_id(pg, JobType.ocr))
        inp = fake_inpainter()
        run_inpaint_job(_job_id(pg, JobType.inpaint))

        assert len(inp.calls) == 1, "phải chạy đúng một lượt xoá chữ"
        _duong_dan, masks = inp.calls[0][0], inp.calls[0][1]
        assert len(masks) == 1, (
            f"vùng nhiễu vẫn lọt vào mask ({len(masks)} vùng) — LaMa sẽ xoá mất nét vẽ"
        )
        assert masks[0].x == 100, "giữ nhầm vùng: phải giữ vùng CÓ CHỮ, bỏ vùng nhiễu"

    async def test_ca_trang_toan_NHIEU_thi_bo_qua_xoa_chu(
        self, client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter,
        no_broker_for_chained_ocr,
    ):
        """Không vùng nào có chữ ⇒ không chạy LaMa, và **KHÔNG** đặt `clean_image_path`.

        Trỏ `clean_image_path` sang ảnh gốc cho gọn là mở đường mất ảnh gốc: lượt chạy lại bước
        xoá chữ gọi `storage.delete(old_clean_rel)`.
        """
        _pid, pg, dj = await _trang(client, sample_page_image)
        fake_detector(regions=[_region(100, 100), _region(400, 400)])
        run_detect_job(dj)
        fake_ocr_engine(per_call=lambda i, b: ("2", 0.31), engine_enum=OCREngine.paddle_ocr)
        run_ocr_job(_job_id(pg, JobType.ocr))
        inp = fake_inpainter()
        run_inpaint_job(_job_id(pg, JobType.inpaint))

        assert inp.calls == [], "không được chạy LaMa khi chẳng có chữ nào để xoá"
        with sync_session() as s:
            page = s.get(Page, uuid.UUID(pg))
            assert page.status is PageStatus.inpainted, "vẫn phải đi tiếp, không kẹt"
            assert page.clean_image_path is None
            assert page.image_path, "ảnh gốc phải còn nguyên"


class TestKhongNoiTayQuaDa:
    async def test_vung_CHU_THAT_van_bi_xoa(
        self, client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter,
        no_broker_for_chained_ocr,
    ):
        """**Bài canh nguy hiểm nhất.** Nới tay quá thì chữ gốc không được xoá, và bước căn chữ
        vẽ chữ dịch ĐÈ LÊN chữ gốc — tệ hơn trạng thái ban đầu."""
        _pid, pg, dj = await _trang(client, sample_page_image)
        fake_detector(regions=[_region(100, 100), _region(400, 400)])
        run_detect_job(dj)
        fake_ocr_engine(per_call=lambda i, b: ("But...", 0.97), engine_enum=OCREngine.paddle_ocr)
        run_ocr_job(_job_id(pg, JobType.ocr))
        inp = fake_inpainter()
        run_inpaint_job(_job_id(pg, JobType.inpaint))

        assert len(inp.calls) == 1
        assert len(inp.calls[0][1]) == 2, "chữ thật ngắn ('But...') vẫn phải được xoá"

    async def test_engine_KHONG_tra_diem_thi_dem_ky_tu(
        self, client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter,
        no_broker_for_chained_ocr,
    ):
        """`manga-ocr` trả `confidence=None`. Lúc đó lùi về đếm ký tự — thô hơn, và đó là đánh
        đổi có ý thức: không có điểm thì không có gì chính xác hơn để dựa vào."""
        _pid, pg, dj = await _trang(client, sample_page_image)
        fake_detector(regions=[_region(100, 100), _region(400, 400)])
        run_detect_job(dj)
        fake_ocr_engine(
            per_call=lambda i, b: ("ドン", None) if i == 0 else ("", None),
            engine_enum=OCREngine.manga_ocr,
        )
        run_ocr_job(_job_id(pg, JobType.ocr))
        inp = fake_inpainter()
        run_inpaint_job(_job_id(pg, JobType.inpaint))

        assert len(inp.calls[0][1]) == 1, "2 ký tự tiếng Nhật là chữ thật; chuỗi rỗng thì không"


class TestTatDuocPhepLoc:
    async def test_dat_0_thi_quay_lai_hanh_vi_CU(
        self, client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter,
        no_broker_for_chained_ocr, monkeypatch,
    ):
        """Phải có đường lùi không cần sửa mã: nếu phép lọc bỏ oan trên một bộ truyện nào đó,
        người vận hành đặt ngưỡng về 0 là quay lại hành vi cũ ngay."""
        from app.workers import tasks

        monkeypatch.setattr(tasks.settings, "vung_xoa_min_conf", 0.0)
        _pid, pg, dj = await _trang(client, sample_page_image)
        fake_detector(regions=[_region(100, 100), _region(400, 400)])
        run_detect_job(dj)
        fake_ocr_engine(per_call=lambda i, b: ("2", 0.31), engine_enum=OCREngine.paddle_ocr)
        run_ocr_job(_job_id(pg, JobType.ocr))
        inp = fake_inpainter()
        run_inpaint_job(_job_id(pg, JobType.inpaint))

        assert len(inp.calls[0][1]) == 2, "đặt 0 phải xoá MỌI vùng như trước"
