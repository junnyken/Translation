"""E70 — chữ dịch mặc đúng "áo" của chữ gốc: màu chữ, màu viền, bề dày viền (cách đo từ Koharu).

Canh ba tầng:
1. `do_mau_chu` đo đúng trên chữ vẽ thật bằng font thật (không phải mảng số tự bịa).
2. Bộ vẽ dùng màu theo vùng, và nhân bề dày viền theo hệ số vẽ E65.
3. Chạy trọn bước căn chữ trên DB thật: cột được ghi, ảnh xem thử có đúng màu, sửa tay giữ màu,
   tắt cờ thì cột NULL như trước E70.
"""
from __future__ import annotations

import io
import uuid
from pathlib import Path

import numpy as np
import pytest
import sqlalchemy as sa
from PIL import Image, ImageDraw, ImageFont

from app.core.db_sync import sync_session
from app.models import Job, TextRegion, TypesetResult
from app.models.enums import JobStatus, JobType, OCREngine
from app.services.detect.ctd import DetectedRegion
from app.services.interfaces import BBox
from app.services.typeset.mau_chu import do_mau_chu
from app.services.typeset.paths import preview_relative_path
from app.services.typeset.preview import PagePreviewRenderer, RegionDraw

FONT = Path(__file__).resolve().parents[1] / "fonts" / "Bangers" / "Bangers-Regular.ttf"
VANG = (250, 220, 40)


def _ve(nen, chu, vien=None, day=0):
    im = Image.new("RGB", (300, 120), nen)
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(str(FONT), 40)
    d.text((20, 30), "HELLO WORLD", font=f, fill=chu, stroke_width=day, stroke_fill=vien)
    b = d.textbbox((20, 30), "HELLO WORLD", font=f, stroke_width=day)
    return np.asarray(im), BBox(b[0] - 3, b[1] - 3, b[2] - b[0] + 6, b[3] - b[1] + 6)


# ---------- 1. đo ----------

@pytest.mark.parametrize(
    "nen, chu, vien, day, ky_vong",
    [
        ("white", "black", None, 0, ((0, 0, 0), None, None)),
        ("white", (200, 30, 30), None, 0, ((200, 30, 30), None, None)),
        ("black", "white", None, 0, ((255, 255, 255), None, None)),
        ((60, 120, 200), "white", "black", 4, ((255, 255, 255), (0, 0, 0), 4.0)),
        # Khác Koharu: chữ vàng tươi KHÔNG bị quy thành trắng (chỉ quy màu gần xám).
        ((240, 180, 190), VANG, "black", 3, (VANG, (0, 0, 0), 3.0)),
    ],
)
def test_do_dung_ao_chu_ve_bang_font_that(nen, chu, vien, day, ky_vong):
    anh, bbox = _ve(nen, chu, vien, day)
    m = do_mau_chu(anh, bbox)
    assert (m.mau, m.mau_vien, m.vien) == ky_vong


def test_nhieu_jpeg_khong_bien_chu_den_thanh_xam():
    anh, bbox = _ve("white", "black")
    buf = io.BytesIO()
    Image.fromarray(anh).save(buf, "JPEG", quality=60)
    m = do_mau_chu(np.asarray(Image.open(buf).convert("RGB")), bbox)
    assert m.mau == (0, 0, 0) and m.mau_vien is None


def test_khung_nam_ngoai_anh_thi_khong_do():
    assert do_mau_chu(np.zeros((50, 50, 3), np.uint8), BBox(100, 100, 5, 5)) is None


# ---------- 2. bộ vẽ ----------

class _Font:
    def resolve(self, family, size):
        return ImageFont.truetype(str(FONT), size)


def _ve_mot_vung(tmp_path, k=1.0, **mau):
    sach = tmp_path / "sach.png"
    Image.new("RGB", (400, 200), "white").save(sach)
    r = RegionDraw(bbox=BBox(20, 20, 360, 160), wrapped_text="HELLO", font_family="Bangers",
                   font_size=60 * k, padding_ratio=0.05, **mau)
    may = PagePreviewRenderer(_Font(), line_spacing_ratio=0.18)
    return np.asarray(may.draw(str(sach), [r], he_so_ve=k))


def test_ve_dung_mau_chu_va_vien_theo_vung(tmp_path):
    out = _ve_mot_vung(tmp_path, text_color="#fadc28", stroke_color="#000000", stroke_width=4.0)
    assert (np.abs(out.astype(int) - VANG).max(axis=2) <= 6).sum() > 200, "phải có chữ vàng"
    assert (out.max(axis=2) < 30).sum() > 200, "phải có viền đen"


def test_khong_do_thi_ve_mau_mac_dinh_nhu_truoc(tmp_path):
    out = _ve_mot_vung(tmp_path)
    assert (out.max(axis=2) < 30).sum() > 200
    assert (np.abs(out.astype(int) - VANG).max(axis=2) <= 6).sum() == 0


def test_vien_nhan_theo_he_so_ve(tmp_path):
    def so_diem_den(k):
        out = _ve_mot_vung(tmp_path, k=k, text_color="#ffffff", stroke_color="#000000",
                           stroke_width=3.0)
        return int((out.max(axis=2) < 30).sum())
    # Phóng 2 lần: diện tích viền ~ x4 nếu viền được nhân, chỉ ~ x2 nếu bị quên nhân.
    assert so_diem_den(2.0) > 3.2 * so_diem_den(1.0)


# ---------- 3. chạy trọn bước căn chữ ----------

def _anh_trang() -> bytes:
    """Vùng 1: chữ VÀNG viền ĐEN trên nền xanh. Vùng 2: chữ đen trên nền trắng."""
    im = Image.new("RGB", (1200, 1700), "white")
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(str(FONT), 48)
    d.rectangle([60, 80, 360, 240], fill=(60, 120, 200))
    d.text((110, 130), "HELLO", font=f, fill=VANG, stroke_width=3, stroke_fill="black")
    d.text((720, 1010), "BYE", font=f, fill="black")
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def _job_id(page_id: str, job_type: JobType) -> str:
    with sync_session() as s:
        job = s.execute(
            sa.select(Job).where(Job.page_id == uuid.UUID(page_id), Job.type == job_type)
            .order_by(Job.created_at.desc())
        ).scalars().first()
        return str(job.id)


def _ket_qua(page_id: str):
    with sync_session() as s:
        return [
            (ts.text_color, ts.stroke_color, ts.stroke_width, r.id)
            for ts, r in s.execute(
                sa.select(TypesetResult, TextRegion)
                .join(TextRegion, TextRegion.id == TypesetResult.region_id)
                .where(TextRegion.page_id == uuid.UUID(page_id))
                .order_by(TextRegion.reading_order)
            ).all()
        ]


@pytest.fixture
def trang_da_dich(client, fake_detector, fake_ocr_engine, fake_inpainter, fake_translator,
                  no_broker_for_chained_ocr):
    from app.workers.tasks import run_detect_job, run_inpaint_job, run_ocr_job, run_translate_job

    async def _go():
        proj = await client.post("/api/v1/projects",
                                 json={"name": "E70", "source_lang": "en", "intended_use": "study"})
        up = await client.post(f"/api/v1/projects/{proj.json()['id']}/pages",
                               files={"file": ("p.png", _anh_trang(), "image/png")})
        page_id = up.json()["page_id"]
        fake_detector(regions=[
            DetectedRegion(bbox=BBox(x=100, y=120, w=200, h=80), confidence=0.9, cls=0),
            DetectedRegion(bbox=BBox(x=700, y=1000, w=200, h=80), confidence=0.9, cls=0),
        ])
        run_detect_job(up.json()["job_id"])
        fake_ocr_engine(per_call=lambda i, b: (["HELLO", "BYE"][i % 2], 0.95),
                        engine_enum=OCREngine.manga_ocr)
        run_ocr_job(_job_id(page_id, JobType.ocr))
        fake_inpainter()
        fake_ocr_engine(results=("", None), engine_enum=OCREngine.manga_ocr)
        run_inpaint_job(_job_id(page_id, JobType.inpaint))
        fake_translator(prefix="")
        run_translate_job(_job_id(page_id, JobType.translate))
        return page_id
    return _go


async def test_can_chu_ghi_ao_chu_va_ve_dung_mau(trang_da_dich, storage_root):
    from app.workers.tasks import run_typeset_job

    page_id = await trang_da_dich()
    assert run_typeset_job(_job_id(page_id, JobType.typeset))["status"] == "done"

    (m1, v1, d1, _), (m2, v2, d2, _) = _ket_qua(page_id)
    assert (m1, v1) == ("#fadc28", "#000000") and d1 is not None and d1 >= 2
    assert (m2, v2, d2) == ("#000000", None, None)

    with Image.open(Path(storage_root) / preview_relative_path(uuid.UUID(page_id))) as im:
        out = np.asarray(im.convert("RGB"))
    vang = np.abs(out.astype(int) - VANG).max(axis=2) <= 8
    # Ảnh clean giả là trắng tinh ⇒ điểm vàng chỉ có thể do bước vẽ chữ dịch tạo ra.
    assert vang.sum() > 50


async def test_sua_tay_giu_nguyen_ao_chu(trang_da_dich, storage_root):
    from app.workers.tasks import run_refit_job, run_typeset_job

    page_id = await trang_da_dich()
    run_typeset_job(_job_id(page_id, JobType.typeset))
    truoc = _ket_qua(page_id)[0]
    with sync_session() as s:
        job = Job(type=JobType.typeset, page_id=uuid.UUID(page_id), status=JobStatus.queued)
        s.add(job)
        s.commit()
        jid = str(job.id)
    assert run_refit_job(jid, str(truoc[3]), 30)["status"] == "done"
    assert _ket_qua(page_id)[0][:3] == truoc[:3]


async def test_tat_co_thi_cot_null_nhu_truoc_e70(trang_da_dich, monkeypatch):
    from app.workers import tasks
    from app.workers.tasks import run_typeset_job

    monkeypatch.setattr(tasks.settings, "e70_mau_chu_theo_vung", False)
    page_id = await trang_da_dich()
    run_typeset_job(_job_id(page_id, JobType.typeset))
    assert all(r[:3] == (None, None, None) for r in _ket_qua(page_id))
