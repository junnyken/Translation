"""SQLAlchemy models — 7 bảng chốt ở M1 (Project, Page, TextRegion, OCRResult,
TranslationResult, TypesetResult, Job). Không tạo thêm bảng ngoài danh sách này."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import (
    FitStatus,
    IntendedUse,
    JobStatus,
    JobType,
    OCREngine,
    OCRStatus,
    PageStatus,
    ProjectStatus,
    RegionStatus,
    SourceLang,
    TargetLang,
    TranslationEngine,
    TranslationStatus,
)


def _enum(py_enum, name: str) -> SAEnum:
    """Postgres native enum lưu đúng *value* (không lưu tên biến Python)."""
    return SAEnum(py_enum, name=name, values_callable=lambda e: [m.value for m in e])


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Project(TimestampMixin, Base):
    __tablename__ = "project"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_lang: Mapped[SourceLang] = mapped_column(_enum(SourceLang, "source_lang"), nullable=False)
    target_lang: Mapped[TargetLang] = mapped_column(
        _enum(TargetLang, "target_lang"), nullable=False, default=TargetLang.vi
    )
    intended_use: Mapped[IntendedUse] = mapped_column(
        _enum(IntendedUse, "intended_use"), nullable=False
    )
    status: Mapped[ProjectStatus] = mapped_column(
        _enum(ProjectStatus, "project_status"), nullable=False, default=ProjectStatus.active
    )

    pages: Mapped[list["Page"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="Page.order"
    )


class Page(TimestampMixin, Base):
    __tablename__ = "page"
    __table_args__ = (Index("ix_page_project_order", "project_id", "order"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("project.id", ondelete="CASCADE"), nullable=False
    )
    image_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    # NULL cho tới khi M4 (inpaint) chạy thật — không đặt giá trị giả.
    clean_image_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PageStatus] = mapped_column(
        _enum(PageStatus, "page_status"), nullable=False, default=PageStatus.queued
    )

    project: Mapped[Project] = relationship(back_populates="pages")
    regions: Mapped[list["TextRegion"]] = relationship(
        back_populates="page", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["Job"]] = relationship(back_populates="page", cascade="all, delete-orphan")


class TextRegion(TimestampMixin, Base):
    __tablename__ = "text_region"

    id: Mapped[uuid.UUID] = _uuid_pk()
    page_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("page.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bbox_x: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_w: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_h: Mapped[float] = mapped_column(Float, nullable=False)
    # NULL cho tới khi M2 chạy detect thật.
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    overlap_suspect: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # NULL cho tới khi M5 tính reading order.
    reading_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[RegionStatus] = mapped_column(
        _enum(RegionStatus, "region_status"), nullable=False, default=RegionStatus.pending
    )

    page: Mapped[Page] = relationship(back_populates="regions")


class OCRResult(TimestampMixin, Base):
    __tablename__ = "ocr_result"

    id: Mapped[uuid.UUID] = _uuid_pk()
    region_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("text_region.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # 1 region <-> 1 OCRResult => rerun job idempotent (M3)
    )
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_engine: Mapped[OCREngine | None] = mapped_column(_enum(OCREngine, "ocr_engine"), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[OCRStatus] = mapped_column(
        _enum(OCRStatus, "ocr_status"), nullable=False, default=OCRStatus.pending
    )


class TranslationResult(TimestampMixin, Base):
    __tablename__ = "translation_result"

    id: Mapped[uuid.UUID] = _uuid_pk()
    region_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("text_region.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    translated_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    engine: Mapped[TranslationEngine | None] = mapped_column(
        _enum(TranslationEngine, "translation_engine"), nullable=True
    )
    model_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    token_cost: Mapped[int | None] = mapped_column(Integer, nullable=True)
    edited_by_user: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[TranslationStatus] = mapped_column(
        _enum(TranslationStatus, "translation_status"),
        nullable=False,
        default=TranslationStatus.pending,
    )


class TypesetResult(TimestampMixin, Base):
    __tablename__ = "typeset_result"

    id: Mapped[uuid.UUID] = _uuid_pk()
    region_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("text_region.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    font_family: Mapped[str | None] = mapped_column(String(255), nullable=True)
    font_size: Mapped[float | None] = mapped_column(Float, nullable=True)
    wrapped_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    padding_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    fit_status: Mapped[FitStatus] = mapped_column(
        _enum(FitStatus, "fit_status"), nullable=False, default=FitStatus.pending
    )
    edited_by_user: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Job(TimestampMixin, Base):
    __tablename__ = "job"

    id: Mapped[uuid.UUID] = _uuid_pk()
    type: Mapped[JobType] = mapped_column(_enum(JobType, "job_type"), nullable=False)
    page_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("page.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[JobStatus] = mapped_column(
        _enum(JobStatus, "job_status"), nullable=False, default=JobStatus.queued
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_log: Mapped[str | None] = mapped_column(Text, nullable=True)

    page: Mapped[Page] = relationship(back_populates="jobs")


__all__ = [
    "Base",
    "Project",
    "Page",
    "TextRegion",
    "OCRResult",
    "TranslationResult",
    "TypesetResult",
    "Job",
]
