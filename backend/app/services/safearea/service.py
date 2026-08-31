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
from app.services.storage import IObjectStorage, workspace

logger = logging.getLogger(__name__)


def van_tay_hien_vat(storage: IObjectStorage, rel: str | None) -> str | None:
    """Vân tay ảnh clean: kích thước + thời điểm ghi, lấy qua `stat()` của kho.

    Đủ để biết ảnh đã bị thay (chạy lại xoá chữ) mà không phải băm cả tệp 4MB cho mỗi vùng.
    Ảnh đổi ⇒ hình cũ hết hiệu lực, không được dùng lại im lặng.

    P3c: trước đây hàm này gọi `Path(duong_dan).stat()` — chỉ chạy được trên hệ tệp cục bộ.
    Nay đi qua `storage.stat()`, nên kho nào cũng cấp được cặp số này.
    """
    if not rel:
        return None
    st = storage.stat(rel)
    if st is None:
        return None
    return hashlib.sha256(f"{st.size}:{st.mtime}".encode()).hexdigest()[:32]


class SafeAreaService:
    def __init__(self, storage: IObjectStorage, config: SafeAreaConfig) -> None:
        self.storage = storage
        self.config = config
        self.extractor = BubbleSafeAreaExtractor()

    def _rel_clean(self, page: Page | None) -> str | None:
        """Path TƯƠNG ĐỐI của ảnh clean — bộ trích hình sẽ nhận bản đã vật chất hoá."""
        if page is None or not page.clean_image_path:
            return None
        rel = page.clean_image_path
        return rel if self.storage.exists(rel) else None

    def compute_page(self, session: Session, page_id: uuid.UUID) -> dict:
        """Tính cho mọi vùng của một trang. Trả bản tóm tắt để ghi log, không ném lỗi ra ngoài."""
        page = session.get(Page, page_id)
        if page is None:
            return {"tong": 0, "bo_qua": "khong_co_trang"}
        rel = self._rel_clean(page)
        if not rel:
            # Chưa có ảnh sạch thì KHÔNG bịa vùng an toàn — để trống, bước căn chữ dùng M6.
            return {"tong": 0, "bo_qua": "chua_co_anh_clean"}

        from PIL import Image

        van_tay = van_tay_hien_vat(self.storage, rel)
        vung = list(session.scalars(
            select(TextRegion).where(TextRegion.page_id == page_id).order_by(TextRegion.id)
        ))
        dem = {"tong": len(vung), "shape_derived": 0, "fallback_rectangle": 0,
               "needs_review": 0, "failed": 0}
        # Vật chất hoá MỘT lần cho cả trang: bộ trích hình dùng OpenCV nên cần đường dẫn thật,
        # nhưng chép lại ảnh cho từng vùng thì với kho từ xa là N lượt tải cho một trang.
        with workspace() as ws:
            clean = str(self.storage.fetch_to(rel, ws / Path(rel).name))
            with Image.open(clean) as im:
                size = im.size
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
        rel = self._rel_clean(page)
        if not rel:
            return None
        from PIL import Image

        with workspace() as ws:
            clean = str(self.storage.fetch_to(rel, ws / Path(rel).name))
            with Image.open(clean) as im:
                size = im.size
            qd = self.extractor.extract(
                clean, BBox(x=r.bbox_x, y=r.bbox_y, w=r.bbox_w, h=r.bbox_h), size, self.config
            )
        ban = self._ghi(session, region_id, qd, van_tay_hien_vat(self.storage, rel))
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


def vung_an_toan_dung_duoc(ban: RegionSafeArea | None, van_tay_hien_tai: str | None) -> dict | None:
    """Hình học còn dùng được không — hay đã cũ so với ảnh clean hiện tại.

    Ảnh clean đã đổi mà vẫn vẽ theo hình cũ là lỗi im lặng tệ nhất của E14: chữ nằm đúng chỗ
    của một bong bóng KHÔNG CÒN Ở ĐÓ. Thà lùi về hành vi M6.

    P3c: nhận **vân tay đã tính sẵn** thay vì đường dẫn ảnh. Trước đây hàm tự `stat()` lại tệp
    cho MỖI vùng — với kho từ xa thì một trang 30 vùng là 30 lượt hỏi kho cho cùng một tệp.
    """
    if ban is None or ban.status is SafeAreaStatus.failed:
        return None
    if van_tay_hien_tai and ban.clean_image_fingerprint:
        if van_tay_hien_tai != ban.clean_image_fingerprint:
            return None
    return ban.geometry_json
