"""Pydantic schema cho response — KHÔNG bao giờ trả thẳng SQLAlchemy object ra API."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    IntendedUse,
    JobStatus,
    JobType,
    PageStatus,
    ProjectStatus,
    RegionStatus,
    SourceLang,
    TargetLang,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Project ----------
class ProjectCreate(BaseModel):
    """Field bắt buộc: name, source_lang, intended_use (M10 guardrail bản quyền)."""

    name: str = Field(min_length=1, max_length=255)
    source_lang: SourceLang
    target_lang: TargetLang = TargetLang.vi
    intended_use: IntendedUse


class ProjectRead(ORMModel):
    id: uuid.UUID
    name: str
    source_lang: SourceLang
    target_lang: TargetLang
    intended_use: IntendedUse
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime


class PageSummary(ORMModel):
    id: uuid.UUID
    order: int
    status: PageStatus


class ProjectDetail(ProjectRead):
    pages: list[PageSummary] = []


# ---------- Page ----------
class PageRead(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    image_path: str
    clean_image_path: str | None
    order: int
    status: PageStatus
    created_at: datetime
    updated_at: datetime


class PageAccepted(BaseModel):
    """202 Accepted — không xử lý AI đồng bộ trong request, chỉ nhận việc vào hàng đợi."""

    page_id: uuid.UUID
    status: PageStatus
    job_id: uuid.UUID


# ---------- TextRegion ----------
class BBoxOut(BaseModel):
    x: float
    y: float
    w: float
    h: float


class RegionRead(BaseModel):
    id: uuid.UUID
    page_id: uuid.UUID
    bbox: BBoxOut
    confidence: float | None
    overlap_suspect: bool
    reading_order: int | None
    status: RegionStatus

    @classmethod
    def from_model(cls, region) -> "RegionRead":
        return cls(
            id=region.id,
            page_id=region.page_id,
            bbox=BBoxOut(x=region.bbox_x, y=region.bbox_y, w=region.bbox_w, h=region.bbox_h),
            confidence=region.confidence,
            overlap_suspect=region.overlap_suspect,
            reading_order=region.reading_order,
            status=region.status,
        )


# ---------- Job ----------
class JobRead(ORMModel):
    id: uuid.UUID
    type: JobType
    page_id: uuid.UUID
    status: JobStatus
    retry_count: int
    error_log: str | None
    created_at: datetime
    updated_at: datetime
