"""E90 — Gemini đọc chữ ngay lúc nhận diện, bước OCR dùng luôn (không nạp PaddleOCR).
E91 — ảnh trang quá lớn được thu nhỏ khi tải lên.

Đo production 16-10-2026: PaddleOCR 100–112 s/trang (15 vùng, trang 3112x4402); trang đó còn làm
worker hết bộ nhớ khi xoá chữ. A/B lời nhắc (5 trang × 2 lượt): khung lời thoại trùng lời nhắc cũ,
chữ Nhật đúng từng ký tự, đọc đúng chữ tượng thanh カラン/コロン mà PaddleOCR đọc thành 「やっぱり」.
"""
from __future__ import annotations

import io
import json
import uuid

import pytest
import sqlalchemy as sa
from PIL import Image

from app.core.db_sync import sync_session
from app.models import Job, OCRResult, TextRegion
from app.models.enums import JobType, OCREngine, OCRStatus
from app.services.detect.ai_gemini import SCHEMA, AIGeminiDetector
from app.services.detect.ctd import DetectedRegion
from app.services.interfaces import BBox
from app.services.storage import thu_nho_anh_trang


def _tra_loi(muc: list[dict]) -> dict:
    return {"candidates": [{"finishReason": "STOP", "content": {"parts": [
        {"text": json.dumps(muc)}]}}]}


@pytest.fixture
def anh(tmp_path):
    p = tmp_path / "trang.png"
    Image.new("RGB", (1200, 1660), (255, 255, 255)).save(p)
    return str(p)


def test_schema_co_text_nhung_khong_bat_buoc():
    assert SCHEMA["items"]["properties"]["text"]["type"] == "STRING"
    assert SCHEMA["items"]["required"] == ["box"], "thiếu text vẫn phải nhận khung (lùi về OCR)"


def test_doc_chu_kem_khung_va_bo_khung_chi_la_so(anh, monkeypatch):
    tra = _tra_loi([
        {"box": [100, 100, 200, 300], "text": "そうですね、\n  本当に"},
        {"box": [300, 100, 340, 140], "text": "18"},
        {"box": [400, 100, 450, 300], "text": "..."},
        {"box": [500, 100, 550, 300]},
    ])
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, timeout=None: io.BytesIO(json.dumps(tra).encode()))
    ra = AIGeminiDetector(api_keys=["k"]).detect_regions(anh)
    assert [r.chu for r in ra] == ["そうですね、 本当に", "...", None]


def _job(pid, t):
    with sync_session() as s:
        return str(s.execute(sa.select(Job).where(Job.page_id == uuid.UUID(pid), Job.type == t)
                             .order_by(Job.created_at.desc())).scalars().first().id)


async def _trang_da_nhan_dien(client, sample_page_image, fake_detector, vung):
    from app.workers.tasks import run_detect_job

    pr = await client.post("/api/v1/projects", json={"name": "c", "source_lang": "ja",
                                                      "intended_use": "study"})
    up = await client.post(f"/api/v1/projects/{pr.json()['id']}/pages",
                           files={"file": ("p.png", sample_page_image, "image/png")})
    fake_detector(regions=vung)
    run_detect_job(up.json()["job_id"])
    return up.json()["page_id"]


@pytest.mark.anyio
async def test_ocr_dung_chu_doc_san_khong_nap_engine(client, sample_page_image, fake_detector,
                                                    monkeypatch):
    from app.workers import tasks

    pid = await _trang_da_nhan_dien(client, sample_page_image, fake_detector, [
        DetectedRegion(bbox=BBox(100, 100, 200, 80), confidence=None, cls=0, chu="カラン"),
        DetectedRegion(bbox=BBox(600, 900, 200, 80), confidence=None, cls=0, chu="こんにちは"),
    ])

    def _cam(_lang):
        raise AssertionError("đã có chữ đọc sẵn mà vẫn nạp engine OCR")

    monkeypatch.setattr(tasks, "get_ocr_engine_cached", _cam)
    kq = tasks.run_ocr_job(_job(pid, JobType.ocr))
    assert kq["status"] == "done" and kq["chu_doc_san"] == 2 and kq["engine"] == "ai_gemini"
    with sync_session() as s:
        rows = s.execute(sa.select(OCRResult).join(TextRegion)
                         .where(TextRegion.page_id == uuid.UUID(pid))).scalars().all()
        assert sorted(r.raw_text for r in rows) == ["こんにちは", "カラン"]
        assert all(r.ocr_engine is OCREngine.ai_gemini and r.confidence is None for r in rows)
        assert all(r.status is OCRStatus.ok for r in rows)


@pytest.mark.anyio
async def test_vung_thieu_chu_van_chay_ocr(client, sample_page_image, fake_detector,
                                          fake_ocr_engine):
    from app.workers import tasks

    pid = await _trang_da_nhan_dien(client, sample_page_image, fake_detector, [
        DetectedRegion(bbox=BBox(100, 100, 200, 80), confidence=None, cls=0, chu="カラン"),
        DetectedRegion(bbox=BBox(600, 900, 200, 80), confidence=None, cls=0),
    ])
    fake = fake_ocr_engine(results=("OCR đọc", 0.9), engine_enum=OCREngine.paddle_ocr)
    kq = tasks.run_ocr_job(_job(pid, JobType.ocr))
    assert kq["chu_doc_san"] == 1 and len(fake.calls) == 1, "chỉ vùng thiếu chữ mới qua OCR"
    with sync_session() as s:
        rows = {r.raw_text: r.ocr_engine for r in s.execute(
            sa.select(OCRResult).join(TextRegion).where(TextRegion.page_id == uuid.UUID(pid))
        ).scalars()}
    assert rows == {"カラン": OCREngine.ai_gemini, "OCR đọc": OCREngine.paddle_ocr}


@pytest.mark.anyio
async def test_tat_co_thi_ocr_nhu_cu(client, sample_page_image, fake_detector, fake_ocr_engine,
                                    monkeypatch):
    from app.workers import tasks

    monkeypatch.setattr(tasks.settings, "ocr_dung_chu_nhan_dien", False)
    pid = await _trang_da_nhan_dien(client, sample_page_image, fake_detector, [
        DetectedRegion(bbox=BBox(100, 100, 200, 80), confidence=None, cls=0, chu="カラン"),
    ])
    fake = fake_ocr_engine(results=("OCR đọc", 0.9), engine_enum=OCREngine.paddle_ocr)
    tasks.run_ocr_job(_job(pid, JobType.ocr))
    assert len(fake.calls) == 1


def _jpeg(w, h):
    b = io.BytesIO()
    Image.new("RGB", (w, h), (200, 100, 50)).save(b, "JPEG", quality=95)
    return b.getvalue()


def test_thu_nho_giu_dinh_dang_va_ti_le():
    ra = thu_nho_anh_trang(_jpeg(3112, 4402), ".jpg", 3000)
    im = Image.open(io.BytesIO(ra))
    assert im.format == "JPEG" and max(im.size) == 3000
    assert abs(im.size[0] / im.size[1] - 3112 / 4402) < 0.002


def test_anh_nho_giu_nguyen_tung_byte():
    goc = _jpeg(1200, 1700)
    assert thu_nho_anh_trang(goc, ".jpg", 3000) is goc
    assert thu_nho_anh_trang(_jpeg(4000, 10), ".jpg", 0) is not None


@pytest.mark.anyio
async def test_tai_len_trang_lon_luu_ban_da_thu_nho(client, monkeypatch):
    from app.core.config import get_settings
    from app.services.storage import get_storage

    monkeypatch.setattr(get_settings(), "anh_trang_canh_dai_toi_da", 1000)
    pr = await client.post("/api/v1/projects", json={"name": "c", "source_lang": "ja",
                                                      "intended_use": "study"})
    up = await client.post(f"/api/v1/projects/{pr.json()['id']}/pages",
                           files={"file": ("p.jpg", _jpeg(1500, 2400), "image/jpeg")})
    assert up.status_code == 202, up.text
    r = await client.get(f"/api/v1/pages/{up.json()['page_id']}")
    duong = r.json()["image_path"]
    assert max(Image.open(io.BytesIO(get_storage().read(duong))).size) == 1000


def test_anh_hong_giu_nguyen_khong_no():
    """Bài kiểm quyền chéo gửi "PNG" = chữ ký + rác: thu nhỏ KHÔNG được làm request 500."""
    hong = b"\x89PNG\r\n\x1a\n" + b"0" * 64
    assert thu_nho_anh_trang(hong, ".png", 3000) is hong
