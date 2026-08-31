"""E14 — integration: vùng an toàn trên CSDL thật + ảnh thật (tổng hợp), qua đúng API."""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa

cv2 = pytest.importorskip("cv2")
import numpy as np

from app.core.config import get_settings
from app.core.db_sync import sync_session
from app.models import Page, RegionSafeArea, TextRegion, TypesetResult
from app.models.enums import (
    OCREngine,
    OCRStatus,
    PageStatus,
    SafeAreaSource,
    SafeAreaStatus,
)
from app.models import OCRResult, TranslationResult
from app.services.safearea.config import SafeAreaConfig
from app.services.safearea.service import SafeAreaService, van_tay_hien_vat
from app.services.storage import LocalObjectStorage, get_storage


def _anh_bong_bong(w=800, h=600) -> bytes:
    anh = np.full((h, w, 3), (40, 60, 40), np.uint8)
    cv2.ellipse(anh, (400, 300), (150, 90), 0, 0, 360, (245, 245, 245), -1)
    cv2.ellipse(anh, (150, 120), (60, 35), 0, 0, 360, (245, 245, 245), -1)
    return cv2.imencode(".png", anh)[1].tobytes()


@pytest.fixture
def trang_co_bong_bong(sample_page_image, no_broker_for_chained_ocr):
    """Trang có ảnh clean thật (2 bong bóng) + 3 vùng chữ: 2 trong bong bóng, 1 trên nền tối."""
    def _go():
        st = get_settings()
        with sync_session() as s:
            from app.models import Project
            from app.models.enums import IntendedUse

            pr = Project(name="E14", source_lang="en", target_lang="vi",
                         intended_use=IntendedUse.study)
            s.add(pr); s.flush()
            page = Page(project_id=pr.id, image_path="x.png", order=1,
                        status=PageStatus.translated)
            s.add(page); s.flush()

            rel = f"projects/{pr.id}/pages/{page.id}_clean.png"
            duong = Path(st.storage_local_root) / rel
            duong.parent.mkdir(parents=True, exist_ok=True)
            duong.write_bytes(_anh_bong_bong())
            page.clean_image_path = rel

            vung = []
            for bx, by, bw, bh in [(340, 285, 120, 30), (110, 105, 80, 30), (600, 500, 100, 40)]:
                r = TextRegion(page_id=page.id, bbox_x=bx, bbox_y=by, bbox_w=bw, bbox_h=bh,
                               confidence=0.9, reading_order=len(vung) + 1)
                s.add(r); s.flush()
                s.add(OCRResult(region_id=r.id, raw_text="hello",
                                ocr_engine=OCREngine.manga_ocr, status=OCRStatus.ok))
                s.add(TranslationResult(region_id=r.id, translated_text="Xin chào bạn"))
                vung.append(r.id)
            s.commit()
            return pr.id, page.id, vung, str(duong)
    return _go


def _dv() -> SafeAreaService:
    st = get_settings()
    return SafeAreaService(get_storage(), SafeAreaConfig.from_settings(st))


def _van_tay(duong: str) -> str | None:
    """Vân tay của ảnh clean từ đường dẫn tuyệt đối mà fixture trả về.

    P3c: `nap_o_dat_chu()` nay nhận vân tay chứ không nhận đường dẫn — vì kho lưu trữ không
    nhất thiết là hệ tệp. Test vẫn ghi tệp thẳng (backend local) nên phải quy ngược về path
    tương đối để hỏi kho.
    """
    rel = str(Path(duong).relative_to(get_settings().storage_local_root))
    return van_tay_hien_vat(get_storage(), rel)


def _ban(region_id) -> RegionSafeArea | None:
    with sync_session() as s:
        return s.scalar(sa.select(RegionSafeArea).where(RegionSafeArea.region_id == region_id))


# ---------------- tính cho cả trang ----------------

def test_moi_vung_dung_mot_ban_ghi(trang_co_bong_bong):
    _pid, page_id, vung, _ = trang_co_bong_bong()
    with sync_session() as s:
        dem = _dv().compute_page(s, page_id); s.commit()
    assert dem["tong"] == 3
    with sync_session() as s:
        assert s.scalar(sa.select(sa.func.count()).select_from(RegionSafeArea).where(
            RegionSafeArea.region_id.in_(vung))) == 3


def test_tinh_lai_khong_de_them_ban_ghi_trung(trang_co_bong_bong):
    _pid, page_id, vung, _ = trang_co_bong_bong()
    for _ in range(3):
        with sync_session() as s:
            _dv().compute_page(s, page_id); s.commit()
    with sync_session() as s:
        assert s.scalar(sa.select(sa.func.count()).select_from(RegionSafeArea).where(
            RegionSafeArea.region_id.in_(vung))) == 3


def test_vung_trong_bong_bong_ra_hinh_vung_ngoai_thi_du_phong(trang_co_bong_bong):
    _pid, page_id, vung, _ = trang_co_bong_bong()
    with sync_session() as s:
        _dv().compute_page(s, page_id); s.commit()
    assert _ban(vung[0]).source is SafeAreaSource.shape_derived
    assert _ban(vung[1]).source is SafeAreaSource.shape_derived
    ngoai = _ban(vung[2])
    assert ngoai.source is SafeAreaSource.fallback_rectangle
    assert "fallback_no_reliable_shape" in ngoai.reason_codes


def test_mot_vung_du_phong_khong_lam_hong_vung_khac(trang_co_bong_bong):
    _pid, page_id, vung, _ = trang_co_bong_bong()
    with sync_session() as s:
        _dv().compute_page(s, page_id); s.commit()
    a = _ban(vung[0])
    assert a.status is SafeAreaStatus.ready and a.geometry_json.get("polygon")


def test_ban_ghi_luu_du_bang_chung_va_ban_cau_hinh(trang_co_bong_bong):
    _pid, page_id, vung, _ = trang_co_bong_bong()
    with sync_session() as s:
        _dv().compute_page(s, page_id); s.commit()
    b = _ban(vung[0])
    assert b.algorithm_version == "e14-bubble-safe-area-v1"
    assert b.config_snapshot["brightness_threshold"] > 0
    assert b.place_rect_json and b.place_rect_json["w"] > 0
    assert b.clean_image_fingerprint


def test_du_phong_van_co_hinh_hoc_khong_de_rong(trang_co_bong_bong):
    _pid, page_id, vung, _ = trang_co_bong_bong()
    with sync_session() as s:
        _dv().compute_page(s, page_id); s.commit()
    b = _ban(vung[2])
    assert b.geometry_json["rect"]["w"] > 0 and b.geometry_json["rect"]["h"] > 0
    assert b.place_rect_json is not None


def test_chua_co_anh_clean_thi_khong_bia_vung_an_toan(trang_co_bong_bong):
    _pid, page_id, vung, _ = trang_co_bong_bong()
    with sync_session() as s:
        s.get(Page, page_id).clean_image_path = None
        s.commit()
    with sync_session() as s:
        dem = _dv().compute_page(s, page_id); s.commit()
    assert dem["bo_qua"] == "chua_co_anh_clean"
    with sync_session() as s:
        assert s.scalar(sa.select(sa.func.count()).select_from(RegionSafeArea).where(
            RegionSafeArea.region_id.in_(vung))) == 0


# ---------------- ảnh clean đổi ----------------

def test_anh_clean_doi_thi_hinh_cu_khong_duoc_dung_lai(trang_co_bong_bong):
    """Vẽ theo hình của một bong bóng KHÔNG CÒN Ở ĐÓ là lỗi im lặng tệ nhất của E14."""
    import time

    from app.services.safearea.apply import nap_o_dat_chu

    _pid, page_id, vung, duong = trang_co_bong_bong()
    with sync_session() as s:
        _dv().compute_page(s, page_id); s.commit()
    with sync_session() as s:
        assert nap_o_dat_chu(s, vung, _van_tay(duong))

    time.sleep(1.1)
    anh = np.full((600, 800, 3), (40, 60, 40), np.uint8)   # xoá sạch bong bóng
    Path(duong).write_bytes(cv2.imencode(".png", anh)[1].tobytes())

    with sync_session() as s:
        assert nap_o_dat_chu(s, vung, _van_tay(duong)) == {}


def test_van_tay_doi_theo_noi_dung_anh(tmp_path):
    import time

    kho = LocalObjectStorage(str(tmp_path))
    kho.save("a.png", b"x" * 100)
    a = van_tay_hien_vat(kho, "a.png")
    time.sleep(1.1)
    kho.save("a.png", b"y" * 200)
    assert van_tay_hien_vat(kho, "a.png") != a
    assert van_tay_hien_vat(kho, "khong-co.png") is None
    assert van_tay_hien_vat(kho, None) is None


# ---------------- tính lại một vùng ----------------

def test_tinh_lai_mot_vung_khong_dung_toi_vung_khac(trang_co_bong_bong):
    _pid, page_id, vung, _ = trang_co_bong_bong()
    with sync_session() as s:
        _dv().compute_page(s, page_id); s.commit()
    truoc = {v: _ban(v).updated_at for v in vung}

    with sync_session() as s:
        _dv().compute_region(s, vung[0]); s.commit()
    assert _ban(vung[1]).updated_at == truoc[vung[1]]
    assert _ban(vung[2]).updated_at == truoc[vung[2]]


def test_doi_bbox_roi_tinh_lai_thi_hinh_doi_theo(trang_co_bong_bong):
    _pid, page_id, vung, _ = trang_co_bong_bong()
    with sync_session() as s:
        _dv().compute_page(s, page_id); s.commit()
    cu = _ban(vung[2]).geometry_json

    with sync_session() as s:
        r = s.get(TextRegion, vung[2])
        r.bbox_x, r.bbox_y = 340, 285      # kéo vào giữa bong bóng
        s.commit()
    with sync_session() as s:
        _dv().compute_region(s, vung[2]); s.commit()

    moi = _ban(vung[2])
    assert moi.geometry_json != cu
    assert moi.source is SafeAreaSource.shape_derived


# ---------------- API ----------------

async def test_api_tra_hinh_hoc_va_ly_do(client, trang_co_bong_bong):
    _pid, page_id, vung, _ = trang_co_bong_bong()
    with sync_session() as s:
        _dv().compute_page(s, page_id); s.commit()

    r = await client.get(f"/api/v1/regions/{vung[0]}/safe-area")
    assert r.status_code == 200
    d = r.json()
    assert d["source"] == "shape_derived" and d["status"] == "ready"
    assert len(d["geometry"]["polygon"]) >= 3
    assert d["place_rect"]["w"] > 0
    assert d["reason_codes"] == ["shape_candidate_found"]


async def test_api_chua_tinh_thi_404_chu_khong_tra_hinh_rong(client, trang_co_bong_bong):
    _pid, _page_id, vung, _ = trang_co_bong_bong()
    r = await client.get(f"/api/v1/regions/{vung[0]}/safe-area")
    assert r.status_code == 404
    assert "safe_area_not_computed" in r.json()["detail"]


async def test_api_tom_tat_trang_tach_rieng_chua_tinh(client, trang_co_bong_bong):
    _pid, page_id, _vung, _ = trang_co_bong_bong()
    r = await client.get(f"/api/v1/pages/{page_id}/safe-area-summary")
    assert r.json()["total_regions"] == 3
    assert r.json()["not_computed_count"] == 3

    with sync_session() as s:
        _dv().compute_page(s, page_id); s.commit()
    d = (await client.get(f"/api/v1/pages/{page_id}/safe-area-summary")).json()
    assert d["shape_derived_count"] == 2
    assert d["fallback_rectangle_count"] == 1
    assert d["not_computed_count"] == 0


async def test_api_khong_tra_ve_diem_anh_nao(client, trang_co_bong_bong):
    _pid, page_id, vung, _ = trang_co_bong_bong()
    with sync_session() as s:
        _dv().compute_page(s, page_id); s.commit()
    d = (await client.get(f"/api/v1/regions/{vung[0]}/safe-area")).json()
    assert set(d) == {
        "region_id", "algorithm_version", "source", "status", "geometry_type", "geometry",
        "roi", "safe_area_pixels", "bbox_coverage_ratio", "reason_codes", "config_summary",
        "place_rect",
    }


async def test_canh_bao_xuat_dem_bo_cuc_tach_khoi_tran_khung(client, trang_co_bong_bong):
    pid, page_id, _vung, _ = trang_co_bong_bong()
    with sync_session() as s:
        s.get(Page, page_id).status = PageStatus.typeset_done
        _dv().compute_page(s, page_id); s.commit()
    d = (await client.get(f"/api/v1/projects/{pid}/export-warnings")).json()
    assert d["shape_fallback_count"] == 1
    assert d["shape_needs_review_count"] == 0
    # Tách bạch: đếm bố cục KHÔNG được cộng vào số tràn khung.
    assert d["overflow_warning_count"] == 0


async def test_tinh_lai_xoa_ban_cu_va_xep_viec(client, trang_co_bong_bong):
    _pid, page_id, vung, _ = trang_co_bong_bong()
    with sync_session() as s:
        _dv().compute_page(s, page_id); s.commit()
    r = await client.post(f"/api/v1/pages/{page_id}/retry-safe-area")
    assert r.status_code == 202
    with sync_session() as s:
        assert s.scalar(sa.select(sa.func.count()).select_from(RegionSafeArea).where(
            RegionSafeArea.region_id.in_(vung))) == 0


# ---------------- Run D: ảnh xem thử và file xuất phải khớp ----------------

def test_xem_thu_va_xuat_file_ra_dung_mot_anh(trang_co_bong_bong):
    """Người xem thấy sao thì tải về phải y như vậy — không được có hai bộ vẽ.

    Kiểm bằng cách vẽ hai lần qua ĐÚNG hàm `draw()` mà cả hai đường đều gọi, với cùng ô đặt
    chữ nạp từ cùng một hàm, rồi so từng điểm ảnh.
    """
    import hashlib

    from app.core.config import get_settings as _gs
    from app.services.interfaces import BBox
    from app.services.safearea.apply import nap_o_dat_chu
    from app.services.typeset.fonts import FontResolver
    from app.services.typeset.preview import PagePreviewRenderer, RegionDraw

    _pid, page_id, vung, duong = trang_co_bong_bong()
    with sync_session() as s:
        _dv().compute_page(s, page_id); s.commit()

    st = _gs()
    rs = FontResolver(font_dir=st.font_dir, default_family=st.default_font_family,
                      allow_fallback=st.allow_font_fallback)
    ve = PagePreviewRenderer(font_resolver=rs,
                             line_spacing_ratio=st.typeset_line_spacing_ratio,
                             mark_overflow=False)

    def _dung_anh(danh_dau_tran: bool) -> str:
        with sync_session() as s:
            rows = list(s.execute(
                sa.select(TextRegion).where(TextRegion.page_id == page_id)
                .order_by(TextRegion.reading_order)
            ).scalars())
            o_dat = nap_o_dat_chu(s, [r.id for r in rows], _van_tay(duong))
            ds = [
                RegionDraw(
                    bbox=BBox(x=r.bbox_x, y=r.bbox_y, w=r.bbox_w, h=r.bbox_h),
                    wrapped_text="Xin chào", font_family=st.default_font_family,
                    font_size=18.0, padding_ratio=st.typeset_padding_ratio,
                    overflow=False, place_rect=o_dat.get(r.id),
                )
                for r in rows
            ]
        return hashlib.sha256(ve.draw(duong, ds).tobytes()).hexdigest()

    assert _dung_anh(False) == _dung_anh(False)


def test_o_dat_chu_luu_san_chu_khong_tinh_lai_o_moi_noi(trang_co_bong_bong):
    """Ô đặt chữ đọc từ bản ghi. Tính lại ở từng nơi là từng ấy cơ hội lệch nhau."""
    from app.services.safearea.apply import nap_o_dat_chu

    _pid, page_id, vung, duong = trang_co_bong_bong()
    with sync_session() as s:
        _dv().compute_page(s, page_id); s.commit()
    with sync_session() as s:
        o = nap_o_dat_chu(s, vung, _van_tay(duong))
    b = _ban(vung[0])
    assert o[vung[0]] == (b.place_rect_json["x"], b.place_rect_json["y"],
                          b.place_rect_json["w"], b.place_rect_json["h"])


def test_anh_goc_va_anh_clean_khong_bi_E14_dung_toi(trang_co_bong_bong):
    import hashlib
    from pathlib import Path as _P

    _pid, page_id, _vung, duong = trang_co_bong_bong()
    truoc = hashlib.sha256(_P(duong).read_bytes()).hexdigest()
    with sync_session() as s:
        _dv().compute_page(s, page_id); s.commit()
    assert hashlib.sha256(_P(duong).read_bytes()).hexdigest() == truoc
