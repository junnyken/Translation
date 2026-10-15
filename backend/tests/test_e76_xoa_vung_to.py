"""E76 — cọ xoá chữ trên màn canvas: xoá đúng vùng người dùng tô, trên ảnh SẠCH hiện tại.

Canh:
1. Chỉ điểm ảnh trong mặt nạ đổi; mặt nạ rỗng / sai cỡ / đích trùng nguồn ⇒ từ chối.
2. API kiểm mặt nạ NGAY (sai cỡ, rỗng, trùm quá nửa trang ⇒ 422) và trả 202 + job.
3. Chạy trọn task trên DB thật: ảnh sạch đổi đúng vùng tô, ẢNH GỐC KHÔNG ĐỔI, tệp mặt nạ bị dọn,
   vùng an toàn E14 giữ hiệu lực (không làm mất cỡ chữ người dùng đã ghim), ảnh xem thử vẽ lại.
"""
from __future__ import annotations

import hashlib
import io
import uuid
from pathlib import Path

import numpy as np
import pytest
import sqlalchemy as sa
from PIL import Image

from app.core.db_sync import sync_session
from app.models import Job, Page, RegionSafeArea, TextRegion
from app.models.enums import (
    JobStatus, JobType, OCREngine, SafeAreaGeometryType, SafeAreaSource, SafeAreaStatus,
)
from app.services.detect.ctd import DetectedRegion
from app.services.inpaint.lama import LamaInpainter
from app.services.inpaint.mat_na_co import xoa_theo_mat_na
from app.services.inpaint.mask import InvalidMask
from app.services.interfaces import BBox


def _model_xam(rgb, mask):
    return np.full_like(rgb, 128 / 255.0)


def _may():
    m = LamaInpainter(weights_path="/khong/co.onnx")
    m._chay_model = _model_xam
    return m


# ---------- 1. thuật toán ----------

def test_chi_doi_diem_anh_trong_mat_na(tmp_path):
    src = tmp_path / "s.png"
    goc = np.random.default_rng(0).integers(0, 256, (200, 300, 3), dtype=np.uint8)
    Image.fromarray(goc).save(src)
    mn = np.zeros((200, 300), bool)
    mn[50:70, 40:90] = True
    mn[150:160, 200:280] = True
    may = _may()
    may.tile_margin = 8  # lề mặc định 96px gộp hai vệt gần nhau thành MỘT cụm (đúng — lấy ngữ cảnh)
    so_cum = xoa_theo_mat_na(may, str(src), mn, str(tmp_path / "d.png"))
    out = np.asarray(Image.open(tmp_path / "d.png"))
    assert (out[mn] == 128).all()
    assert np.array_equal(out[~mn], goc[~mn])
    assert so_cum == 2


@pytest.mark.parametrize("mn, loi", [
    (np.zeros((200, 300), bool), "rỗng"),
    (np.ones((100, 100), bool), "khác cỡ"),
])
def test_tu_choi_mat_na_hong(tmp_path, mn, loi):
    src = tmp_path / "s.png"
    Image.new("RGB", (300, 200), "white").save(src)
    with pytest.raises(InvalidMask, match=loi):
        xoa_theo_mat_na(_may(), str(src), mn, str(tmp_path / "d.png"))


def test_khong_ghi_de_nguon(tmp_path):
    from app.services.inpaint.lama import InpaintFailed

    src = tmp_path / "s.png"
    Image.new("RGB", (30, 20), "white").save(src)
    with pytest.raises(InpaintFailed, match="trùng nguồn"):
        xoa_theo_mat_na(_may(), str(src), np.ones((20, 30), bool), str(src))


# ---------- 2–3. API + task trên DB thật ----------

def _job_id(page_id, loai):
    with sync_session() as s:
        return str(s.execute(sa.select(Job.id).where(Job.page_id == uuid.UUID(page_id), Job.type == loai)
                             .order_by(Job.created_at.desc())).scalars().first())


def _png(mn: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(mn.astype(np.uint8) * 255).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def trang(client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter,
          fake_translator, no_broker_for_chained_ocr):
    from app.workers.tasks import (
        run_detect_job, run_inpaint_job, run_ocr_job, run_translate_job, run_typeset_job,
    )

    async def _go():
        proj = await client.post("/api/v1/projects",
                                 json={"name": "E76", "source_lang": "en", "intended_use": "study"})
        up = await client.post(f"/api/v1/projects/{proj.json()['id']}/pages",
                               files={"file": ("p.png", sample_page_image, "image/png")})
        page_id = up.json()["page_id"]
        fake_detector(regions=[DetectedRegion(bbox=BBox(x=100, y=120, w=200, h=80),
                                              confidence=0.9, cls=0)])
        run_detect_job(up.json()["job_id"])
        fake_ocr_engine(per_call=lambda i, b: ("HELLO", 0.95), engine_enum=OCREngine.manga_ocr)
        run_ocr_job(_job_id(page_id, JobType.ocr))
        fake_inpainter()
        fake_ocr_engine(results=("", None), engine_enum=OCREngine.manga_ocr)
        run_inpaint_job(_job_id(page_id, JobType.inpaint))
        fake_translator(prefix="")
        run_translate_job(_job_id(page_id, JobType.translate))
        run_typeset_job(_job_id(page_id, JobType.typeset))
        return page_id
    return _go


def _co_trang(page_id):
    from app.services.storage import get_storage

    with sync_session() as s:
        p = s.get(Page, uuid.UUID(page_id))
        rel = p.image_path
    with get_storage().open_read(rel) as f, Image.open(f) as im:
        return im.size


@pytest.mark.parametrize("kieu", ["RGBA_trang_den_duc", "RGBA_trong_suot", "L"])
def test_doc_mat_na_dung_moi_kieu(kieu):
    """Màn canvas xuất RGBA trắng/đen ĐỤC — lỗi thật bắt được khi bấm trên hệ thống chạy thật."""
    from app.api.v1.routes import _doc_mat_na

    mn = np.zeros((20, 30), bool)
    mn[5:10, 8:20] = True
    if kieu == "RGBA_trang_den_duc":
        a = np.zeros((20, 30, 4), np.uint8)
        a[..., 3] = 255
        a[mn, :3] = 255
        im = Image.fromarray(a, "RGBA")
    elif kieu == "RGBA_trong_suot":
        a = np.zeros((20, 30, 4), np.uint8)
        a[mn] = 255
        im = Image.fromarray(a, "RGBA")
    else:
        im = Image.fromarray(mn.astype(np.uint8) * 255)
    assert np.array_equal(_doc_mat_na(im), mn)


async def test_api_kiem_mat_na_ngay(client, trang):
    page_id = await trang()
    w, h = _co_trang(page_id)
    url = f"/api/v1/pages/{page_id}/xoa-vung-to"

    async def gui(mn):
        return await client.post(url, files={"file": ("m.png", _png(mn), "image/png")})

    r = await gui(np.zeros((h, w), bool))
    assert r.status_code == 422 and "Chưa tô" in r.json()["detail"]
    r = await gui(np.ones((h // 2, w // 2), bool))
    assert r.status_code == 422 and "khác cỡ" in r.json()["detail"]
    r = await gui(np.ones((h, w), bool))
    assert r.status_code == 422 and "quá rộng" in r.json()["detail"]


async def test_chay_tron_xoa_dung_vung_giu_anh_goc_va_vung_an_toan(
        client, trang, monkeypatch, storage_root):
    from app.services.dispatch import dispatch_xoa_vung_to_job  # noqa: F401 — đường thật phải import được
    from app.workers import tasks

    page_id = await trang()
    w, h = _co_trang(page_id)
    with sync_session() as s:
        p = s.get(Page, uuid.UUID(page_id))
        goc_rel, sach_rel = p.image_path, p.clean_image_path
        rid = s.scalar(sa.select(TextRegion.id).where(TextRegion.page_id == p.id))
        ban = s.scalar(sa.select(RegionSafeArea).where(RegionSafeArea.region_id == rid))
        if ban is None:
            ban = RegionSafeArea(region_id=rid, algorithm_version="t", roi_x=0, roi_y=0, roi_w=1,
                                 roi_h=1, reason_codes=[], config_snapshot={})
            s.add(ban)
        from app.services.safearea.service import van_tay_hien_vat
        from app.services.storage import get_storage

        ban.source, ban.status = SafeAreaSource.fallback_rectangle, SafeAreaStatus.fallback_rectangle
        ban.geometry_type = SafeAreaGeometryType.rect
        ban.geometry_json = {"rect": {"x": 100.0, "y": 120.0, "w": 200.0, "h": 80.0}}
        ban.clean_image_fingerprint = van_tay_hien_vat(get_storage(), sach_rel)
        s.commit()
    md5_goc = hashlib.md5((Path(storage_root) / goc_rel).read_bytes()).hexdigest()

    gui_di = {}
    monkeypatch.setattr("app.api.v1.routes.dispatch_xoa_vung_to_job",
                        lambda jid, rel: (gui_di.update(jid=jid, rel=rel) or (True, None)))
    mn = np.zeros((h, w), bool)
    mn[300:340, 400:520] = True
    r = await client.post(f"/api/v1/pages/{page_id}/xoa-vung-to",
                          files={"file": ("m.png", _png(mn), "image/png")})
    assert r.status_code == 202
    assert (Path(storage_root) / gui_di["rel"]).is_file(), "mặt nạ phải được lưu cho worker"

    # `fake_inpainter` (dùng trong `trang`) đã thay `get_inpainter` — thay lại bằng LaMa thật có
    # model giả, để chạy ĐÚNG `xoa_theo_mat_na` của engine thật.
    monkeypatch.setattr(tasks, "get_inpainter", _may)
    kq = tasks.run_xoa_vung_to_job(str(gui_di["jid"]), gui_di["rel"])
    assert kq["status"] == "done", kq
    assert kq["preview_path"], "trang đã căn chữ ⇒ phải vẽ lại ảnh xem thử"

    sach = np.asarray(Image.open(Path(storage_root) / sach_rel).convert("RGB"))
    assert (sach[300:340, 400:520] == 128).all()
    assert hashlib.md5((Path(storage_root) / goc_rel).read_bytes()).hexdigest() == md5_goc, \
        "ẢNH GỐC bị ghi đè"
    assert not (Path(storage_root) / gui_di["rel"]).exists(), "tệp mặt nạ phải được dọn"
    with sync_session() as s:
        assert s.get(Job, gui_di["jid"]).status is JobStatus.done
        ban = s.scalar(sa.select(RegionSafeArea).where(RegionSafeArea.region_id == rid))
        assert ban.clean_image_fingerprint == van_tay_hien_vat(get_storage(), sach_rel), \
            "vùng an toàn phải còn hiệu lực với ảnh sạch MỚI"


# ---------- kéo khung trên canvas: chữ phải đi theo khung (lỗi thấy khi bấm thật) ----------

def _kq_refit(region_id):
    from app.models import TypesetResult

    with sync_session() as s:
        return s.scalar(sa.select(TypesetResult).where(TypesetResult.region_id == region_id))


async def test_keo_khung_thi_vung_an_toan_cu_bi_bo_va_tinh_lai_quanh_khung_moi(client, trang):
    from app.services.safearea.apply import nap_o_dat_chu
    from app.workers.tasks import run_refit_job

    page_id = await trang()
    with sync_session() as s:
        rid = s.scalar(sa.select(TextRegion.id).where(TextRegion.page_id == uuid.UUID(page_id)))
        ban = s.scalar(sa.select(RegionSafeArea).where(RegionSafeArea.region_id == rid))
        if ban is None:
            ban = RegionSafeArea(region_id=rid, algorithm_version="t", roi_x=0, roi_y=0, roi_w=1,
                                 roi_h=1, reason_codes=[], config_snapshot={})
            s.add(ban)
        ban.source, ban.status = SafeAreaSource.fallback_rectangle, SafeAreaStatus.fallback_rectangle
        ban.geometry_type = SafeAreaGeometryType.rect
        ban.geometry_json = {"rect": {"x": 100.0, "y": 120.0, "w": 200.0, "h": 80.0}}
        ban.place_rect_json = {"x": 100.0, "y": 120.0, "w": 200.0, "h": 80.0}
        ban.clean_image_fingerprint = None
        s.commit()

    r = await client.patch(f"/api/v1/regions/{rid}", json={"bbox": {"x": 700, "y": 1000, "w": 200, "h": 80}})
    assert r.status_code in (200, 202), r.text
    with sync_session() as s:
        assert s.scalar(sa.select(RegionSafeArea).where(RegionSafeArea.region_id == rid)) is None, \
            "khung đổi mà vùng an toàn quanh khung CŨ vẫn còn ⇒ chữ đứng yên chỗ cũ"
        jid = str(s.scalar(sa.select(Job.id).where(Job.page_id == uuid.UUID(page_id))
                           .order_by(Job.created_at.desc())))
    assert run_refit_job(jid, str(rid))["status"] == "done"
    with sync_session() as s:
        o = nap_o_dat_chu(s, [rid], None).get(rid)
    assert o is not None, "vùng an toàn phải được tính lại quanh khung mới"

    def chua(x, y):
        return o[0] <= x <= o[0] + o[2] and o[1] <= y <= o[1] + o[3]
    assert chua(800, 1040), f"ô đặt chữ {o} không chứa tâm khung MỚI"
    assert not chua(200, 160), f"ô đặt chữ {o} vẫn chứa tâm khung CŨ"


async def test_can_lai_mot_vung_nhan_he_so_ve_nhu_can_ca_trang(client, trang, monkeypatch):
    from app.models import Page
    from app.workers import tasks
    from app.workers.tasks import run_refit_job

    monkeypatch.setattr(tasks.settings, "e14_safe_area_enabled", False)
    page_id = await trang()
    with sync_session() as s:
        rid = s.scalar(sa.select(TextRegion.id).where(TextRegion.page_id == uuid.UUID(page_id)))
        s.execute(sa.delete(RegionSafeArea).where(RegionSafeArea.region_id == rid))
        # Khung NHỎ: với khung 200×80 chữ ngắn chạm trần cỡ 40 ngay ở hệ số 1 ⇒ không so được.
        v = s.get(TextRegion, rid)
        v.bbox_w, v.bbox_h = 60.0, 24.0
        s.commit()

    async def can_lai_voi(k):
        with sync_session() as s:
            s.get(Page, uuid.UUID(page_id)).he_so_ve = k
            j = Job(type=JobType.typeset, page_id=uuid.UUID(page_id), status=JobStatus.queued)
            s.add(j)
            s.commit()
            jid = str(j.id)
        assert run_refit_job(jid, str(rid))["status"] == "done"
        return _kq_refit(rid).font_size

    nho, lon = await can_lai_voi(1.0), await can_lai_voi(2.0)
    assert lon > nho, "bộ vẽ phóng ảnh ×2 ⇒ cỡ chữ (px ảnh đã phóng) phải lớn hơn; trước đây bằng nhau"
