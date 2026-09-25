"""E48 — cảnh báo khi chạy truyện tiếng Nhật với engine nhận diện `ctd`.

## Vì sao cần cảnh báo

Đo 25-09 trên 13 vùng `comic-text-detector` khoanh ở 3 trang tiếng Nhật: luật E47 lọc được
**0/13**.

manga-ocr là mô hình **SINH**. Đưa vào một mảng ánh sáng lấp lánh, nó không trả chuỗi rỗng mà
**bịa ra chữ Nhật nghe rất hợp lý** (đọc ra 4–18 ký tự có nghĩa), và **không trả điểm tin cậy**
nên E47 không có tín hiệu nào để nghi ngờ. Đã thử tín hiệu thay thế (mật độ nét): chồng lấn hoàn
toàn, không ngưỡng nào cắt được.

⇒ Với tiếng Nhật, bước khoanh khung là lớp bảo vệ **DUY NHẤT**.

## Vì sao CẢNH BÁO chứ không CHẶN — bộ test đã bắt được lỗi thiết kế

Bản đầu tôi viết là **từ chối thẳng**. Bộ test đỏ **51 bài**: mặc định trong mã là `ctd` và phần
lớn bộ test dùng dự án tiếng Nhật, tức bản vá chặn đúng cấu hình dự án đã chạy suốt từ đầu.

Đó là bằng chứng ngược lại giả định của tôi: `ctd` + tiếng Nhật **rủi ro trên trang nhiều hiệu
ứng ánh sáng**, chứ **không hỏng phổ quát**. Suy rộng từ 3 trang xấu thành "luôn hỏng" là sai.

`test_KHONG_chan_luot_chay` khoá bài học đó lại — đừng đổi ngược về chặn.
"""
from __future__ import annotations

import pytest

from app.workers.tasks import run_detect_job

from tests.test_translate_task_integration import _region

pytestmark = pytest.mark.anyio

MA_CANH_BAO = "ja_voi_ctd"


@pytest.fixture(autouse=True)
def _reset_co(monkeypatch):
    """Cảnh báo chỉ ghi MỘT lần/tiến trình, nên phải hạ cờ trước mỗi bài."""
    from app.workers import tasks

    monkeypatch.setattr(tasks, "_da_canh_bao_ja_ctd", False)


async def _tao(client, anh, lang: str):
    proj = await client.post("/api/v1/projects", json={
        "name": f"E48-{lang}", "source_lang": lang, "intended_use": "study"})
    up = await client.post(f"/api/v1/projects/{proj.json()['id']}/pages",
                           files={"file": ("p.png", anh, "image/png")})
    return up.json()["page_id"], up.json()["job_id"]


class TestCoCanhBao:
    async def test_ja_voi_ctd_thi_CANH_BAO(
        self, client, sample_page_image, fake_detector, no_broker_for_chained_ocr,
        monkeypatch,
    ):
        from app.workers import tasks

        monkeypatch.setattr(tasks.settings, "detect_engine", "ctd")
        _pg, jid = await _tao(client, sample_page_image, "ja")
        fake_detector(regions=[_region(100, 100)])

        kq = run_detect_job(jid)

        assert kq["canh_bao"] == MA_CANH_BAO, f"không báo rủi ro ja + ctd: {kq}"
        assert kq["status"] == "done", "cảnh báo không được chặn lượt chạy"

    async def test_bao_o_MOI_job(
        self, client, sample_page_image, fake_detector, no_broker_for_chained_ocr,
        monkeypatch,
    ):
        """Log ghi MỘT lần/tiến trình (vấn đề cấu hình), nhưng trường `canh_bao` phải có ở
        MỌI job — đó là bằng chứng tra được cho từng trang."""
        from app.workers import tasks

        monkeypatch.setattr(tasks.settings, "detect_engine", "ctd")
        fake_detector(regions=[_region(100, 100)])
        ra = []
        for _ in range(3):
            _pg, jid = await _tao(client, sample_page_image, "ja")
            ra.append(run_detect_job(jid)["canh_bao"])

        assert ra == [MA_CANH_BAO] * 3, (
            f"phải báo ở MỌI job, không chỉ job đầu: {ra}"
        )


class TestKhongPhienNhieu:
    async def test_KHONG_chan_luot_chay(
        self, client, sample_page_image, fake_detector, no_broker_for_chained_ocr, monkeypatch,
    ):
        """**Bài canh quan trọng nhất.** Bản đầu chặn thẳng làm đỏ 51 bài — `ctd` + tiếng Nhật
        là cấu hình dự án đã chạy suốt từ đầu và cho kết quả tốt trên trang thường."""
        from app.workers import tasks

        monkeypatch.setattr(tasks.settings, "detect_engine", "ctd")
        _pg, jid = await _tao(client, sample_page_image, "ja")
        fake_detector(regions=[_region(100, 100)])

        assert run_detect_job(jid)["status"] == "done", "cảnh báo không được chặn lượt chạy"

    async def test_ja_voi_engine_AI_KHONG_canh_bao(
        self, client, sample_page_image, fake_detector, no_broker_for_chained_ocr,
        monkeypatch,
    ):
        """Đây là cấu hình production — cảnh báo ở đây là báo oan."""
        from app.workers import tasks

        monkeypatch.setattr(tasks.settings, "detect_engine", "ai_gemini")
        _pg, jid = await _tao(client, sample_page_image, "ja")
        fake_detector(regions=[_region(100, 100)])

        assert run_detect_job(jid)["canh_bao"] is None

    async def test_tieng_ANH_voi_ctd_KHONG_canh_bao(
        self, client, sample_page_image, fake_detector, no_broker_for_chained_ocr,
        monkeypatch,
    ):
        """PaddleOCR CÓ trả điểm tin cậy nên E47 đỡ được — cảnh báo ở đây là báo oan."""
        from app.workers import tasks

        monkeypatch.setattr(tasks.settings, "detect_engine", "ctd")
        _pg, jid = await _tao(client, sample_page_image, "en")
        fake_detector(regions=[_region(100, 100)])

        assert run_detect_job(jid)["canh_bao"] is None


class TestTatDuoc:
    async def test_tat_duoc_bang_cau_hinh(
        self, client, sample_page_image, fake_detector, no_broker_for_chained_ocr,
        monkeypatch,
    ):
        from app.workers import tasks

        monkeypatch.setattr(tasks.settings, "detect_engine", "ctd")
        monkeypatch.setattr(tasks.settings, "canh_bao_ctd_cho_tieng_nhat", False)
        _pg, jid = await _tao(client, sample_page_image, "ja")
        fake_detector(regions=[_region(100, 100)])

        assert run_detect_job(jid)["canh_bao"] is None

    async def test_mac_dinh_la_BAT(self):
        from app.core.config import Settings

        assert Settings(_env_file=None).canh_bao_ctd_cho_tieng_nhat is True
