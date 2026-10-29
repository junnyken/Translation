"""Tính và lưu hướng chữ cho từng vùng (E15 · B4).

Chạy trong worker, sau khi đã có vùng an toàn (E14) và TRƯỚC bước căn chữ — vì hướng chữ là
đầu vào bố cục của bước đó.
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    OCRResult,
    RegionQualityAssessment,
    RegionSafeArea,
    RegionTextOrientation,
    TextRegion,
)
from app.services.orientation.analyzer import (
    VERSION,
    OrientationConfig,
    RegionOrientationAnalyzer,
)

logger = logging.getLogger(__name__)


class OrientationService:
    def __init__(self, config: OrientationConfig | None = None) -> None:
        self.analyzer = RegionOrientationAnalyzer(config)

    def analyze_page(self, session: Session, page_id: uuid.UUID) -> dict:
        vung = list(session.scalars(
            select(TextRegion).where(TextRegion.page_id == page_id).order_by(TextRegion.id)
        ))
        dem = {"tong": len(vung)}
        for r in vung:
            qd = self._tinh(session, r)
            dem[qd.orientation.value] = dem.get(qd.orientation.value, 0) + 1
            dem[f"tt_{qd.status.value}"] = dem.get(f"tt_{qd.status.value}", 0) + 1
        session.flush()
        return dem

    def analyze_region(self, session: Session, region_id: uuid.UUID) -> RegionTextOrientation | None:
        r = session.get(TextRegion, region_id)
        if r is None:
            return None
        ban = self._tinh(session, r)
        session.flush()
        return ban

    def _tinh(self, session: Session, r: TextRegion) -> RegionTextOrientation:
        ocr = session.scalar(select(OCRResult).where(OCRResult.region_id == r.id))
        at = session.scalar(select(RegionSafeArea).where(RegionSafeArea.region_id == r.id))
        cl = session.scalar(
            select(RegionQualityAssessment).where(RegionQualityAssessment.region_id == r.id)
        )
        qd = self.analyzer.analyze(
            bbox_w=r.bbox_w,
            bbox_h=r.bbox_h,
            # `None` (engine không cung cấp) khác hẳn `[]` (có hỏi, không có dòng nào) —
            # giữ nguyên sự phân biệt đó tới tận bộ phân tích.
            line_polygons=ocr.line_polygons if ocr is not None else None,
            ocr_status=ocr.status.value if ocr is not None and ocr.status else None,
            region_relevance=(cl.relevance.value if cl is not None and cl.relevance else None),
            safe_area_source=at.source.value if at is not None else None,
        )

        ban = session.scalar(
            select(RegionTextOrientation).where(RegionTextOrientation.region_id == r.id)
        )
        if ban is None:
            ban = RegionTextOrientation(region_id=r.id)
            session.add(ban)
        ban.algorithm_version = VERSION
        ban.orientation = qd.orientation
        ban.source = qd.source
        ban.status = qd.status
        ban.rotation_degrees = qd.rotation_degrees
        ban.line_count_estimate = qd.line_count_estimate
        ban.reason_codes = list(qd.reason_codes)
        ban.evidence_snapshot = dict(qd.evidence_snapshot)
        return ban
