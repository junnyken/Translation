"""ĐX-3 — nửa ĐỌC: pipeline ĐẦY ĐỦ có thật sự dùng engine người dùng đã chọn không.

**Vì sao file này tồn tại riêng.** Cột `Page.translate_engine_override` có từ E19, nhưng lúc đó
chỉ nhánh `chi_chu` đọc nó — `enqueue_translate_after_inpaint` cố ý truyền thẳng `engine=None`.
Nghĩa là trước ĐX-3 cột này có chỗ **GHI** mà đường chạy thường không có chỗ **ĐỌC**: người dùng
chọn engine cho cả chapter thì lựa chọn đó rơi vào hư không, không một thông báo lỗi nào, và mọi
bài test chỉ kiểm "đã lưu vào cột chưa" đều xanh.

Bài test ở `test_dx2_dx3_upload_goi_integration.py` là nửa GHI. File này là nửa ĐỌC. Thiếu một
trong hai nửa thì tính năng chết im lặng mà bộ test vẫn xanh.

Cách kiểm: đè `run_translate_job.delay` để bắt **tham số thật đã gửi**. Tự gọi
`run_translate_job(...)` tay sẽ bỏ qua đúng thứ cần kiểm (`.delay()` có được gọi với đúng engine
không) — ARCH.md §E19 ghi lại chuyện một bài từng xanh GIẢ đúng vì lý do đó.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from app.core.db_sync import sync_session
from app.models import Job
from app.models.enums import JobType, OCREngine
from app.workers.tasks import run_detect_job, run_inpaint_job, run_ocr_job

from tests.test_translate_task_integration import _job_id, _region

pytestmark = pytest.mark.anyio


async def _chay_toi_truoc_buoc_dich(
    client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter, engine=None
) -> str:
    """Chạy detect → OCR → xoá chữ bằng ĐÚNG đường thật, với `engine` chọn lúc upload.

    Khác `_page_ready_to_translate` ở chỗ nó truyền `engine` vào form upload — đó chính là thứ
    đang cần kiểm.
    """
    proj = await client.post(
        "/api/v1/projects",
        json={"name": "DX3", "source_lang": "ja", "intended_use": "study"},
    )
    up = await client.post(
        f"/api/v1/projects/{proj.json()['id']}/pages",
        files={"file": ("p.png", sample_page_image, "image/png")},
        data={"engine": engine} if engine else None,
    )
    assert up.status_code == 202, up.text
    page_id = up.json()["page_id"]

    fake_detector(regions=[_region(100, 100)])
    run_detect_job(up.json()["job_id"])
    fake_ocr_engine(per_call=lambda i, b: ("XIN CHAO", 0.95), engine_enum=OCREngine.manga_ocr)
    run_ocr_job(_job_id(page_id, JobType.ocr))
    fake_inpainter()
    fake_ocr_engine(results=("", None), engine_enum=OCREngine.manga_ocr)
    run_inpaint_job(_job_id(page_id, JobType.inpaint))
    return page_id


class TestPipelineDayDuDocCotOverride:
    async def test_engine_nguoi_dung_chon_di_TOI_lenh_xep_viec_dich(
        self, client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter,
        monkeypatch,
    ):
        """**Bài canh lỗi gốc.** Chọn `llm_context` lúc upload ⇒ `.delay()` phải nhận đúng nó.

        Nếu ai đó khôi phục hành vi cũ (pipeline đầy đủ luôn truyền `engine=None`) thì tham số
        bắt được sẽ là `None`, job dịch lùi về `translate_default_engine` — và bài này đỏ.
        """
        from app.core.config import get_settings
        from app.workers import tasks

        monkeypatch.setattr(get_settings(), "gemini_api_keys", "khoa-gia")
        goi: list[tuple[str, str | None]] = []
        monkeypatch.setattr(
            tasks.run_translate_job, "delay",
            lambda job_id, engine=None: goi.append((job_id, engine)),
        )

        await _chay_toi_truoc_buoc_dich(
            client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter,
            engine="llm_context",
        )

        assert goi, "chưa từng gọi run_translate_job.delay — pipeline không tới được bước dịch"
        assert goi[-1][1] == "llm_context", (
            "pipeline đầy đủ KHÔNG đọc Page.translate_engine_override — lựa chọn engine của "
            f"người dùng bị bỏ rơi im lặng (nhận được {goi[-1][1]!r})"
        )

    async def test_chon_google_fast_cung_di_toi_noi(
        self, client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter,
        monkeypatch,
    ):
        """`google_fast` chọn tường minh cũng phải được truyền đi, KHÔNG quy về `None`.

        Khác biệt có ý nghĩa thật: `None` nghĩa là "theo mặc định hệ thống", nên đổi
        `translate_default_engine` sẽ âm thầm biến lựa chọn miễn phí của người dùng thành engine
        tốn token. Truyền tường minh thì lựa chọn của họ được giữ nguyên.
        """
        from app.workers import tasks

        goi: list[tuple[str, str | None]] = []
        monkeypatch.setattr(
            tasks.run_translate_job, "delay",
            lambda job_id, engine=None: goi.append((job_id, engine)),
        )

        await _chay_toi_truoc_buoc_dich(
            client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter,
            engine="google_fast",
        )
        assert goi and goi[-1][1] == "google_fast"

    async def test_khong_chon_gi_thi_van_truyen_None_nhu_cu(
        self, client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter,
        monkeypatch,
    ):
        """Đối chứng tương thích ngược: trang không chọn engine phải giữ NGUYÊN hành vi cũ.

        Không có bài này thì bản vá có thể vô tình đổi hành vi của mọi chapter đang chạy.
        """
        from app.workers import tasks

        goi: list[tuple[str, str | None]] = []
        monkeypatch.setattr(
            tasks.run_translate_job, "delay",
            lambda job_id, engine=None: goi.append((job_id, engine)),
        )

        await _chay_toi_truoc_buoc_dich(
            client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter,
        )
        assert goi and goi[-1][1] is None

    async def test_job_dich_that_su_duoc_tao(
        self, client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter,
        no_broker_for_chained_ocr,
    ):
        """Đối chứng âm cho ba bài trên: nếu pipeline không tới được bước dịch thì chúng xanh
        rỗng (`goi` trống) — bài này khẳng định job dịch có tồn tại thật."""
        page_id = await _chay_toi_truoc_buoc_dich(
            client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter,
            engine="google_fast",
        )
        with sync_session() as s:
            jobs = list(s.execute(
                sa.select(Job).where(
                    Job.page_id == uuid.UUID(page_id), Job.type == JobType.translate
                )
            ).scalars())
        assert len(jobs) == 1
