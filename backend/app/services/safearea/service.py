"""Tính và lưu vùng an toàn cho từng vùng chữ (E14 · B4).

Chạy trong worker. Ghi đè bản hiện hành thay vì đẻ bản mới: mỗi vùng chữ đúng **một** vùng an
toàn, và `algorithm_version` + `config_snapshot` đủ để dựng lại kết quả cũ khi cần.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Page, RegionSafeArea, TextRegion
from app.models.enums import SafeAreaStatus
from app.services.interfaces import BBox
from app.services.safearea.config import SafeAreaConfig
from app.services.safearea.extractor import VERSION, BubbleSafeAreaExtractor

logger = logging.getLogger(__name__)


def dau_van_tay_anh(duong_dan: str) -> str | None:
    """Vân tay ảnh clean: kích thước + thời điểm sửa.

    Đủ để biết ảnh đã bị thay (chạy lại xoá chữ) mà không phải băm cả tệp 4MB cho mỗi vùng.
    Ảnh đổi ⇒ hình cũ hết hiệu lực, không được dùng lại im lặng.
    """
    try:
        st = Path(duong_dan).stat()
    except OSError:
        return None
    return hashlib.sha256(f"{st.st_size}:{int(st.st_mtime)}".encode()).hexdigest()[:32]


class SafeAreaService:
    def __init__(self, storage_root: str, config: SafeAreaConfig) -> None:
        self.storage_root = Path(storage_root)
        self.config = config
        self.extractor = BubbleSafeAreaExtractor()

    def _duong_dan_clean(self, page: Page) -> str | None:
        if not page.clean_image_path:
            return None
        return str(self.storage_root / page.clean_image_path)

    def compute_page(self, session: Session, page_id: uuid.UUID) -> dict:
        """Tính cho mọi vùng của một trang. Trả bản tóm tắt để ghi log, không ném lỗi ra ngoài."""
        page = session.get(Page, page_id)
        if page is None:
            return {"tong": 0, "bo_qua": "khong_co_trang"}
        clean = self._duong_dan_clean(page)
        if not clean or not Path(clean).exists():
            # Chưa có ảnh sạch thì KHÔNG bịa vùng an toàn — để trống, bước căn chữ dùng M6.
            return {"tong": 0, "bo_qua": "chua_co_anh_clean"}

        from PIL import Image

        with Image.open(clean) as im:
            size = im.size
        van_tay = dau_van_tay_anh(clean)

        vung = list(session.scalars(
            select(TextRegion).where(TextRegion.page_id == page_id).order_by(TextRegion.id)
        ))
        dem = {"tong": len(vung), "shape_derived": 0, "fallback_rectangle": 0,
               "needs_review": 0, "failed": 0}
        for r in vung:
            qd = self.extractor.extract(
                clean, BBox(x=r.bbox_x, y=r.bbox_y, w=r.bbox_w, h=r.bbox_h), size, self.config
            )
            self._ghi(session, r.id, qd, van_tay)
            dem[qd.status.value] = dem.get(qd.status.value, 0) + 1
        session.flush()
        return dem

    def compute_region(self, session: Session, region_id: uuid.UUID) -> RegionSafeArea | None:
        r = session.get(TextRegion, region_id)
        if r is None:
            return None
        page = session.get(Page, r.page_id)
        clean = self._duong_dan_clean(page) if page else None
        if not clean or not Path(clean).exists():
            return None
        from PIL import Image

        with Image.open(clean) as im:
            size = im.size
        qd = self.extractor.extract(
            clean, BBox(x=r.bbox_x, y=r.bbox_y, w=r.bbox_w, h=r.bbox_h), size, self.config
        )
        ban = self._ghi(session, region_id, qd, dau_van_tay_anh(clean))
        session.flush()
        return ban

    def _ghi(self, session: Session, region_id: uuid.UUID, qd, van_tay: str | None) -> RegionSafeArea:
        ban = session.scalar(
            select(RegionSafeArea).where(RegionSafeArea.region_id == region_id)
        )
        if ban is None:
            ban = RegionSafeArea(region_id=region_id)
            session.add(ban)
        ban.algorithm_version = VERSION
        ban.source = qd.source
        ban.status = qd.status
        ban.roi_x, ban.roi_y, ban.roi_w, ban.roi_h = qd.roi
        ban.geometry_type = qd.geometry_type
        ban.geometry_json = qd.geometry
        ban.safe_area_pixels = qd.safe_area_pixels
        ban.bbox_coverage_ratio = qd.bbox_coverage_ratio
        ban.reason_codes = list(qd.reason_codes)
        # Tính ô đặt chữ NGAY tại đây, ở worker, rồi lưu lại — để tầng HTTP và giao diện chỉ
        # việc đọc, không phải nạp OpenCV và không có cơ hội tính ra một ô khác.
        from app.services.safearea.layout import o_dat_chu

        o = o_dat_chu(qd.geometry)
        ban.place_rect_json = (
            {"x": o.x, "y": o.y, "w": o.w, "h": o.h} if o is not None else None
        )
        ban.config_snapshot = self.config.snapshot()
        ban.clean_image_fingerprint = van_tay
        return ban


def vung_an_toan_dung_duoc(ban: RegionSafeArea | None, clean_image_abs: str | None) -> dict | None:
    """Hình học còn dùng được không — hay đã cũ so với ảnh clean hiện tại.

    Ảnh clean đã đổi mà vẫn vẽ theo hình cũ là lỗi im lặng tệ nhất của E14: chữ nằm đúng chỗ
    của một bong bóng KHÔNG CÒN Ở ĐÓ. Thà lùi về hành vi M6.
    """
    if ban is None or ban.status is SafeAreaStatus.failed:
        return None
    if clean_image_abs and ban.clean_image_fingerprint:
        if dau_van_tay_anh(clean_image_abs) != ban.clean_image_fingerprint:
            return None
    return ban.geometry_json
