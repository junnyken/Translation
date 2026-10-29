"""Chấm chất lượng cả một trang rồi ghi kết quả vào DB (E12).

Ranh giới: bộ chấm ở `assessor.py` là hàm thuần — nó không biết DB tồn tại. Tệp này lo phần
đọc/ghi. Tách ra để phần luật test được mà không cần dựng Postgres, và để không có đường nào
lén sửa dữ liệu của M2–M6 trong lúc chấm.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select

from app.core.db_sync import sync_session
from app.models import (
    OCRResult,
    Page,
    RegionQualityAssessment,
    TextRegion,
    TranslationResult,
    TypesetResult,
)
from app.models.enums import OverallBand, RegionRelevance, ReviewStatus
from app.services.quality.assessor import RegionQualityAssessor

logger = logging.getLogger(__name__)


@dataclass
class TomTatCham:
    so_vung: int
    ro_rang: int
    can_ra_soat: int
    chua_danh_gia: int
    da_bo_qua: int


class QualityGateService:
    def __init__(self, assessor: RegionQualityAssessor | None = None) -> None:
        self.assessor = assessor or RegionQualityAssessor()

    def assess_page(self, page_id: uuid.UUID, trigger: str = "typeset") -> TomTatCham:
        """Chấm mọi vùng của một trang. Ghi đè đánh giá cũ, KHÔNG tạo bản ghi trùng.

        Quyết định của NGƯỜI (`reviewed_keep`/`reviewed_skip`) được giữ nguyên khi chấm lại,
        trừ khi bằng chứng đổi — máy chấm lại mà xoá mất quyết định của người là mất công của họ.
        """
        with sync_session() as session:
            page = session.get(Page, page_id)
            if page is None:
                raise ValueError(f"page_not_found: {page_id}")

            kich_thuoc = self._kich_thuoc_trang(page)
            vung_list = list(session.execute(
                select(TextRegion).where(TextRegion.page_id == page_id)
                .order_by(TextRegion.reading_order.nulls_last(), TextRegion.bbox_y)
            ).scalars())

            chu_goc_truoc: str | None = None
            dem = {"ro_rang": 0, "can_ra_soat": 0, "chua_danh_gia": 0, "da_bo_qua": 0}

            for v in vung_list:
                ocr = session.execute(
                    select(OCRResult).where(OCRResult.region_id == v.id)).scalars().first()
                dich = session.execute(
                    select(TranslationResult).where(
                        TranslationResult.region_id == v.id)).scalars().first()
                canh = session.execute(
                    select(TypesetResult).where(
                        TypesetResult.region_id == v.id)).scalars().first()

                kq = self.assessor.assess(
                    region=v, ocr=ocr, translation=dich, typeset=canh,
                    page_dimensions=kich_thuoc, vung_ke_ben_truoc=chu_goc_truoc,
                )
                chu_goc_truoc = (ocr.raw_text if ocr else None)

                cu = session.execute(
                    select(RegionQualityAssessment).where(
                        RegionQualityAssessment.region_id == v.id)).scalars().first()
                quyet_dinh_nguoi = cu.review_status if cu and cu.review_status in (
                    ReviewStatus.reviewed_keep, ReviewStatus.reviewed_skip) else None
                # Bằng chứng đổi thì hỏi lại người; y hệt thì giữ quyết định cũ.
                bang_chung_doi = bool(cu and cu.evidence_snapshot != kq.evidence_snapshot)
                review = (quyet_dinh_nguoi
                          if quyet_dinh_nguoi and not bang_chung_doi
                          else kq.review_status)

                if cu is None:
                    cu = RegionQualityAssessment(region_id=v.id)
                    session.add(cu)
                cu.assessment_version = self.assessor.VERSION
                cu.relevance = kq.relevance
                cu.review_status = review
                cu.overall_band = kq.overall_band
                cu.detector_confidence_state = kq.detector_confidence_state
                cu.ocr_confidence_state = kq.ocr_confidence_state
                cu.translation_state = kq.translation_state
                cu.reason_codes = kq.reason_codes
                cu.evidence_snapshot = kq.evidence_snapshot

                if review is ReviewStatus.reviewed_skip:
                    dem["da_bo_qua"] += 1
                elif kq.overall_band is OverallBand.blocked:
                    dem["chua_danh_gia"] += 1
                elif review is ReviewStatus.needs_review:
                    dem["can_ra_soat"] += 1
                else:
                    dem["ro_rang"] += 1

            session.commit()

        logger.info("chấm chất lượng trang %s (%s): %d vùng, %d cần rà soát, %d chưa đánh giá",
                    page_id, trigger, len(vung_list), dem["can_ra_soat"], dem["chua_danh_gia"])
        return TomTatCham(so_vung=len(vung_list), **dem)

    @staticmethod
    def _kich_thuoc_trang(page: Page) -> tuple[int, int] | None:
        """Đọc kích thước ảnh gốc. Không đọc được thì trả None — bộ chấm sẽ báo `blocked`
        chứ không bịa ra một kích thước để tính tỉ lệ."""
        try:
            from PIL import Image

            from app.services.storage import get_storage

            # Đọc qua luồng, không qua đường dẫn tuyệt đối: PIL chỉ cần header để biết kích
            # thước, và kho lưu trữ không nhất thiết là hệ tệp (P3c).
            with get_storage().open_read(page.image_path) as fh, Image.open(fh) as im:
                return im.size
        except Exception as exc:  # noqa: BLE001
            # Mất ảnh gốc là chuyện CÓ THẬT trên bản chạy thật (container thay là mất tệp).
            # Không đọc được thì báo `blocked`, không bịa kích thước để tính tỉ lệ.
            logger.warning("không đọc được kích thước trang %s: %s", page.id, exc)
            return None
