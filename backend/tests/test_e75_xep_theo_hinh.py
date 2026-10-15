"""E75 — xếp chữ theo hình bong bóng (dòng giữa rộng, dòng đầu/cuối hẹp).

Canh:
1. Mọi dòng nằm TRỌN trong đa giác, không cắt giữa từ (E60), không mất chữ.
2. Bong bóng bầu dục ngang cho cỡ chữ LỚN HƠN hình chữ nhật nội tiếp (đo 15-10-2026: 40 so với 35).
3. Chỉ nhận khi tốt hơn — không thụt lùi.
4. Bộ vẽ đặt chữ đúng chỗ bước căn đã lưu, nhân hệ số E65.
5. Chạy trọn bước căn trên DB thật: ghi `dong_json`; bong bóng chứa tâm vùng khác ⇒ KHÔNG xếp theo
   hình (chữ hai vùng sẽ đè nhau); tắt cờ ⇒ NULL.
"""
from __future__ import annotations

import math
import uuid
from pathlib import Path

import numpy as np
import pytest
import sqlalchemy as sa
from PIL import Image

from app.core.db_sync import sync_session
from app.models import Job, RegionSafeArea, TextRegion, TypesetResult
from app.models.enums import (
    JobType, OCREngine, SafeAreaGeometryType, SafeAreaSource, SafeAreaStatus,
)
from app.services.detect.ctd import DetectedRegion
from app.services.interfaces import BBox
from app.services.safearea.layout import o_dat_chu
from app.services.typeset.fitter import FitToBoxTypesetter
from app.services.typeset.fonts import FontResolver
from app.services.typeset.preview import PagePreviewRenderer, RegionDraw
from app.services.typeset.xep_theo_hinh import (
    be_rong_dong, do_dong, tam_nam_trong, xep_trong_da_giac,
)

FONT_DIR = str(Path(__file__).resolve().parents[1] / "fonts")


@pytest.fixture(scope="module")
def fr():
    return FontResolver(font_dir=FONT_DIR, default_family="Bangers", allow_fallback=False)


def _elip(cx, cy, a, b, n=48):
    return [[cx + a * math.cos(2 * math.pi * i / n), cy + b * math.sin(2 * math.pi * i / n)]
            for i in range(n)]


CAU = "Khoan đã! Chuyện vẫn chưa xong đâu."


# ---------- 1–3. thuật toán ----------

def test_moi_dong_nam_tron_trong_bong_bong_va_khong_mat_chu(fr):
    pg = _elip(300, 300, 150, 90)
    kq = xep_trong_da_giac(CAU, pg, fr, "Bangers", 10, 40, 0.18)
    assert kq is not None
    assert kq.wrapped_text.split() == CAU.split(), "không mất, không cắt từ nào"
    font = fr.resolve("Bangers", int(kq.font_size))
    _lech, cao, _buoc = do_dong(font, 0, int(round(kq.font_size * 0.18)))
    for chu, (tx, dy) in zip(kq.wrapped_text.split("\n"), kq.dong, strict=True):
        w = be_rong_dong(font, chu, 0)
        for goc in ((tx - w / 2, dy), (tx + w / 2, dy), (tx - w / 2, dy + cao), (tx + w / 2, dy + cao)):
            assert tam_nam_trong(pg, goc), f"dòng '{chu}' thò ra ngoài bong bóng ở {goc}"


def test_bong_bong_bau_duc_ngang_cho_chu_to_hon_hinh_chu_nhat(fr):
    pg = _elip(300, 300, 150, 90)
    cu = FitToBoxTypesetter(fr, 10, 40, 0.0, 0.18).fit(CAU, o_dat_chu({"polygon": pg}).to_bbox(),
                                                       "Bangers")
    moi = xep_trong_da_giac(CAU, pg, fr, "Bangers", 10, 40, 0.18)
    assert moi.font_size > cu["font_size"]


def test_dong_giua_rong_hon_dong_dau(fr):
    kq = xep_trong_da_giac("Tôi đã nói rồi mà, cậu không chịu nghe gì cả!", _elip(300, 300, 90, 150),
                           fr, "Bangers", 10, 40, 0.18)
    font = fr.resolve("Bangers", int(kq.font_size))
    rong = [be_rong_dong(font, d, 0) for d in kq.wrapped_text.split("\n")]
    assert max(rong) > rong[0] and max(rong) > rong[-1]


def test_tu_dai_hon_bong_bong_thi_khong_xep(fr):
    assert xep_trong_da_giac("Siêuuuuuuuuuuuuuuuuuuuuuuuuuuuuuu", _elip(100, 100, 30, 30),
                             fr, "Bangers", 10, 40, 0.18) is None


def test_co_xuong_dong_cung_thi_de_cach_cu(fr):
    assert xep_trong_da_giac("Một\nHai", _elip(300, 300, 150, 90), fr, "Bangers", 10, 40, 0.18) is None


def test_chi_nhan_khi_tot_hon(fr):
    from app.workers.tasks import _thu_xep_theo_hinh

    ts = FitToBoxTypesetter(fr, 10, 40, 0.0, 0.18)
    pg = _elip(150, 150, 75, 45)  # toạ độ ảnh gốc; he_so 2 ⇒ giống elip 300x180 ở trên
    tot = _thu_xep_theo_hinh({"font_size": 20.0, "wrapped_text": "x", "fit_status": "fit_ok"},
                             CAU, pg, 2.0, ts, fr, "Bangers")
    assert tot["font_size"] > 20 and tot["dong"]
    assert all(0 < x < 300 and 0 < y < 300 for x, y in tot["dong"]), "dong lưu ở toạ độ ẢNH GỐC"
    giu = {"font_size": 40.0, "wrapped_text": "x", "fit_status": "fit_ok"}
    assert _thu_xep_theo_hinh(giu, CAU, pg, 2.0, ts, fr, "Bangers") is giu


# ---------- 4. bộ vẽ ----------

def test_bo_ve_dat_chu_dung_cho_da_luu_va_nhan_he_so(tmp_path, fr):
    sach = tmp_path / "s.png"
    Image.new("RGB", (300, 200), "white").save(sach)
    # "Ẫ" có dấu chồng cao nhất ⇒ nét mực chạm ĐÚNG đỉnh dải dòng đã lưu. (Chữ không dấu thì nét bắt
    # đầu thấp hơn đỉnh dải đúng bằng phần dành cho dấu — lần viết đầu bài này dùng "ABC" và kỳ vọng sai.)
    r = RegionDraw(bbox=BBox(0, 0, 300, 200), wrapped_text="ẪBC", font_family="Bangers",
                   font_size=40, padding_ratio=0.0, dong=[[50.0, 20.0]])
    out = np.asarray(PagePreviewRenderer(fr, 0.18).draw(str(sach), [r], he_so_ve=2.0))
    den = np.argwhere(out.max(axis=2) < 100)
    assert len(den) > 50
    cy, cx = den.mean(axis=0)
    assert abs(cx - 100) < 15, "tâm dòng phải ở x = 50 × hệ số 2"
    assert 38 <= den[:, 0].min() <= 46, "đỉnh dòng phải ở y ≈ 20 × 2"


# ---------- 5. chạy trọn bước căn chữ ----------

def _job_id(page_id, loai):
    with sync_session() as s:
        return str(s.execute(sa.select(Job.id).where(Job.page_id == uuid.UUID(page_id),
                                                      Job.type == loai)
                             .order_by(Job.created_at.desc())).scalars().first())


def _gan_da_giac(region_id, pg):
    with sync_session() as s:
        ban = s.scalar(sa.select(RegionSafeArea).where(RegionSafeArea.region_id == region_id))
        if ban is None:
            ban = RegionSafeArea(region_id=region_id)
            s.add(ban)
        o = o_dat_chu({"polygon": pg})
        ban.algorithm_version, ban.source = "test-e75", SafeAreaSource.shape_derived
        ban.status, ban.geometry_type = SafeAreaStatus.ready, SafeAreaGeometryType.polygon
        ban.roi_x = ban.roi_y = 0
        ban.roi_w = ban.roi_h = 1
        ban.geometry_json = {"polygon": pg}
        ban.place_rect_json = {"x": o.x, "y": o.y, "w": o.w, "h": o.h}
        ban.reason_codes, ban.config_snapshot, ban.clean_image_fingerprint = [], {}, None
        s.commit()


def _ket_qua(page_id):
    with sync_session() as s:
        return [ts.dong_json for ts, _r in s.execute(
            sa.select(TypesetResult, TextRegion).join(TextRegion, TextRegion.id == TypesetResult.region_id)
            .where(TextRegion.page_id == uuid.UUID(page_id)).order_by(TextRegion.reading_order)).all()]


@pytest.fixture
def trang(client, sample_page_image, fake_detector, fake_ocr_engine, fake_inpainter,
          fake_translator, no_broker_for_chained_ocr):
    from app.workers.tasks import run_detect_job, run_inpaint_job, run_ocr_job, run_translate_job

    async def _go():
        proj = await client.post("/api/v1/projects",
                                 json={"name": "E75", "source_lang": "en", "intended_use": "study"})
        up = await client.post(f"/api/v1/projects/{proj.json()['id']}/pages",
                               files={"file": ("p.png", sample_page_image, "image/png")})
        page_id = up.json()["page_id"]
        fake_detector(regions=[
            DetectedRegion(bbox=BBox(x=100, y=120, w=200, h=80), confidence=0.9, cls=0),
            DetectedRegion(bbox=BBox(x=700, y=1000, w=200, h=80), confidence=0.9, cls=0),
        ])
        run_detect_job(up.json()["job_id"])
        fake_ocr_engine(per_call=lambda i, b: ("KHOAN DA", 0.95), engine_enum=OCREngine.manga_ocr)
        run_ocr_job(_job_id(page_id, JobType.ocr))
        fake_inpainter()
        fake_ocr_engine(results=("", None), engine_enum=OCREngine.manga_ocr)
        run_inpaint_job(_job_id(page_id, JobType.inpaint))
        fake_translator(prefix="Khoan đã! Chuyện vẫn chưa xong đâu ")
        run_translate_job(_job_id(page_id, JobType.translate))
        with sync_session() as s:
            ids = list(s.scalars(sa.select(TextRegion.id).where(TextRegion.page_id == uuid.UUID(page_id))
                                 .order_by(TextRegion.reading_order)))
        return page_id, ids
    return _go


async def test_can_chu_luu_vi_tri_dong_khi_xep_theo_hinh(trang):
    from app.workers.tasks import run_typeset_job

    page_id, (r1, _r2) = await trang()
    _gan_da_giac(r1, _elip(200, 160, 150, 90))
    assert run_typeset_job(_job_id(page_id, JobType.typeset))["status"] == "done"
    d1, d2 = _ket_qua(page_id)
    assert d1 and all(len(p) == 2 for p in d1)
    assert d2 is None, "vùng không có đa giác giữ khối chữ nhật"


async def test_bong_bong_chua_tam_vung_khac_thi_khong_xep_theo_hinh(trang):
    from app.workers.tasks import run_typeset_job

    page_id, (r1, r2) = await trang()
    # CÙNG bong bóng với ca thành công ở trên (ở đó xếp theo hình THẮNG), rồi dời khung vùng 2 vào
    # trong nó. Lần viết đầu dùng một bong bóng khổng lồ: khối chữ nhật đã chạm trần cỡ chữ nên xếp
    # theo hình không thắng — gỡ chốt đi bài vẫn xanh, tức bài KHÔNG canh gì cả (đối chứng âm lộ ra).
    _gan_da_giac(r1, _elip(200, 160, 150, 90))
    with sync_session() as s:
        v2 = s.get(TextRegion, r2)
        v2.bbox_x, v2.bbox_y, v2.bbox_w, v2.bbox_h = 230.0, 170.0, 40.0, 20.0
        s.commit()
    run_typeset_job(_job_id(page_id, JobType.typeset))
    assert _ket_qua(page_id)[0] is None


async def test_tat_co_thi_null(trang, monkeypatch):
    from app.workers import tasks

    monkeypatch.setattr(tasks.settings, "e75_xep_theo_hinh", False)
    page_id, (r1, _r2) = await trang()
    _gan_da_giac(r1, _elip(200, 160, 150, 90))
    tasks.run_typeset_job(_job_id(page_id, JobType.typeset))
    assert _ket_qua(page_id) == [None, None]


def test_moi_dong_cung_mot_truc_doc(fr):
    """Chữ thoại căn giữa trên MỘT trục. Bản đầu lấy tâm riêng từng dòng ⇒ trên bong bóng thật có
    đuôi, các dòng lệch nhau trông như gõ sai (xem REPORT_E75)."""
    kq = xep_trong_da_giac("Tôi đã nói rồi mà, cậu không chịu nghe gì cả!", _elip(300, 300, 90, 150),
                           fr, "Bangers", 10, 40, 0.18)
    tam = {round(x, 3) for x, _y in kq.dong}
    assert len(tam) == 1


# ---------- E81 — ngắt dòng đều (quy hoạch động) ----------

def test_ngat_deu_khong_de_dong_mot_chu_khi_tranh_duoc(fr):
    from app.services.typeset.xep_theo_hinh import _ngat, _ngat_deu

    font = fr.resolve("Bangers", 30)
    tu = "Tôi đã nói rồi mà cậu không nghe".split()
    # Bề rộng dòng phải vừa CẢ HAI nửa, không thì không cách chia nào xếp được (lần viết đầu sai chỗ này).
    w = int(max(be_rong_dong(font, "Tôi đã nói rồi", 0), be_rong_dong(font, "mà cậu không nghe", 0))) + 2
    khoang = [(0, w), (0, w)]
    tham_lam = _ngat(tu, khoang, font, 0)
    deu, _phat = _ngat_deu(tu, khoang, font, 0)
    assert " ".join(deu).split() == tu, "không mất / đổi từ"
    rong = [be_rong_dong(font, d, 0) for d in deu]
    assert all(r <= w for r in rong)
    # đều hơn tham lam: chênh lệch bề rộng hai dòng nhỏ hơn (hoặc bằng)
    rong_tl = [be_rong_dong(font, d, 0) for d in tham_lam]
    assert abs(rong[0] - rong[1]) <= abs(rong_tl[0] - rong_tl[1])


def test_ngat_deu_khong_xep_duoc_thi_none(fr):
    from app.services.typeset.xep_theo_hinh import _ngat_deu

    font = fr.resolve("Bangers", 30)
    assert _ngat_deu(["Siêuuuuuuuuuuuuuuu"], [(0, 20)], font, 0) is None
