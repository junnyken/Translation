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
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import (
    BatchItemStatus,
    ConfidenceState,
    OverallBand,
    RegionRelevance,
    ReviewStatus,
    TranslationState,
    BatchPipeline,
    BatchStatus,
    ExportFormat,
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
    #: Lần cuối trang này được xuất thành công (M8). NULL = chưa từng xuất — dùng để đối chiếu
    #: xem file đang cầm có cũ hơn lần sửa tay gần nhất không.
    exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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


class ExportJob(TimestampMixin, Base):
    """Một lần xuất chapter (M8). Tách khỏi bảng `Job` vì gắn với PROJECT, không gắn với 1 page."""

    __tablename__ = "export_job"

    id: Mapped[uuid.UUID] = _uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("project.id", ondelete="CASCADE"), nullable=False
    )
    format: Mapped[ExportFormat] = mapped_column(
        _enum(ExportFormat, "export_format"), nullable=False
    )
    #: Dùng chung enum `job_status` của M1 — trạng thái y hệt, không tạo enum trùng nghĩa.
    status: Mapped[JobStatus] = mapped_column(
        _enum(JobStatus, "job_status"), nullable=False, default=JobStatus.queued
    )
    #: File .cbz/.zip, hoặc THƯ MỤC khi format là png_single. NULL cho tới khi xuất xong.
    output_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Số vùng còn tràn khung TẠI THỜI ĐIỂM xuất — không chặn xuất, nhưng phải ghi lại.
    overflow_warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_log: Mapped[str | None] = mapped_column(Text, nullable=True)


class BatchRun(TimestampMixin, Base):
    """Một mẻ chạy cả project (M9).

    `status` ở đây là **kết quả suy ra** từ các `BatchItem`, không bao giờ được đặt tay để
    "cho đẹp". Còn một trang chưa xong mà báo `completed` là báo láo — đúng thứ evidence-first cấm.
    """

    __tablename__ = "batch_run"

    id: Mapped[uuid.UUID] = _uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("project.id", ondelete="CASCADE"), nullable=False
    )
    requested_pipeline: Mapped[BatchPipeline] = mapped_column(
        _enum(BatchPipeline, "batch_pipeline"), nullable=False
    )
    #: Chốt lựa chọn engine dịch NGAY LÚC TẠO mẻ; NULL khi mẻ không cần bước dịch.
    translation_engine: Mapped[TranslationEngine | None] = mapped_column(
        _enum(TranslationEngine, "translation_engine"), nullable=True
    )
    status: Mapped[BatchStatus] = mapped_column(
        _enum(BatchStatus, "batch_status"), nullable=False, default=BatchStatus.queued
    )
    total_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Bộ đếm để hiển thị nhanh — LUÔN phải đối chiếu lại từ BatchItem, không tin một mình nó.
    completed_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blocked_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: Tóm tắt lỗi đã lọc — TUYỆT ĐỐI không ghi API key hay nội dung nhạy cảm vào đây.
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    items: Mapped[list["BatchItem"]] = relationship(
        back_populates="batch_run", cascade="all, delete-orphan"
    )


class BatchItem(TimestampMixin, Base):
    """Một trang trong mẻ. `page_order` là ẢNH CHỤP lúc tạo mẻ — trang thêm sau không lọt vào."""

    __tablename__ = "batch_item"
    __table_args__ = (
        UniqueConstraint("batch_run_id", "page_id", name="uq_batch_item_run_page"),
        Index("ix_batch_item_run_status_order", "batch_run_id", "status", "page_order"),
        Index("ix_batch_item_current_job", "current_job_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    batch_run_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("batch_run.id", ondelete="CASCADE"), nullable=False
    )
    page_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("page.id", ondelete="CASCADE"), nullable=False
    )
    #: Chụp lại `Page.order` lúc tạo mẻ; sắp lại trang về sau KHÔNG làm đổi thứ tự của mẻ cũ.
    page_order: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[BatchItemStatus] = mapped_column(
        _enum(BatchItemStatus, "batch_item_status"), nullable=False, default=BatchItemStatus.pending
    )
    current_job_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("job.id", ondelete="SET NULL"), nullable=True
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Mã lỗi đã phân loại: quota_exhausted, provider_429, provider_5xx, timeout, permanent_*…
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    batch_run: Mapped["BatchRun"] = relationship(back_populates="items")


class ExportComplianceLog(TimestampMixin, Base):
    """Bằng chứng người dùng ĐÃ ĐỌC cảnh báo trước khi mang file đi (M10).

    Bảng riêng thay vì nhét vào `ExportJob.error_log`: đây là bản ghi tuân thủ, cần tra cứu được
    ("chapter này đã xác nhận chưa, lúc nào, khai báo dùng vào việc gì"), mà `error_log` là chỗ
    ghi lỗi kỹ thuật — trộn hai thứ vào nhau thì cả hai cùng khó đọc.

    **Chỉ lưu số liệu, tuyệt đối không lưu nội dung export.** Không có tên file gốc, không có ảnh,
    không có bản dịch ở đây.
    """

    __tablename__ = "export_compliance_log"
    __table_args__ = (
        Index("ix_export_compliance_project", "project_id", "acknowledged_at"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("project.id", ondelete="CASCADE"), nullable=False
    )
    #: Lần xuất được xác nhận. `SET NULL` để xoá bản ghi xuất không xoá mất bằng chứng tuân thủ.
    export_job_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("export_job.id", ondelete="SET NULL"), nullable=True
    )
    #: CHỤP LẠI lúc xác nhận. Đọc lại từ `Project` sẽ sai nếu về sau có mini-spec cho sửa khai báo.
    intended_use: Mapped[IntendedUse] = mapped_column(
        _enum(IntendedUse, "intended_use"), nullable=False
    )
    #: Số vùng còn tràn khung / chưa đọc được chữ **tại thời điểm xác nhận** — người dùng đã nhìn
    #: thấy đúng những con số này.
    overflow_warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    needs_manual_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Đã tick "Đã đọc và chấp nhận trách nhiệm bản quyền" hay chưa. Ghi cả `false` cũng có ý
    #: nghĩa: có người mở cảnh báo ra rồi bỏ đi.
    user_acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class RegionQualityAssessment(TimestampMixin, Base):
    """Đánh giá chất lượng của MỘT vùng chữ (E12) — bảng cộng thêm, không sửa gì của M1–M10.

    Đây chỉ là **lớp giải thích**: nó không đổi `raw_text` của M3, không đổi `translated_text`
    của M5, không xoá `TextRegion` của M2. Việc duy nhất nó làm là biến những dấu hiệu đã có
    sẵn trong DB (điểm tin cậy, trạng thái OCR, trạng thái dịch, hình học khung, kết quả căn
    chữ) thành lý do đọc được, để người vận hành biết nên nhìn vào vùng nào.

    Mỗi vùng giữ đúng MỘT đánh giá hiện hành (`unique(region_id)`), ghi đè khi chấm lại.
    Không làm bảng lịch sử: cần so sánh giữa các phiên bản luật là việc của mini-spec khác.
    """

    __tablename__ = "region_quality_assessment"
    __table_args__ = (
        Index("ix_rqa_review_band", "review_status", "overall_band"),
        Index("ix_rqa_relevance", "relevance"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    region_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("text_region.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    #: Phiên bản bộ luật đã chấm. Bắt buộc để biết một đánh giá cũ được sinh bởi luật nào.
    assessment_version: Mapped[str] = mapped_column(String(32), nullable=False)
    relevance: Mapped[RegionRelevance] = mapped_column(
        _enum(RegionRelevance, "region_relevance"), nullable=False
    )
    review_status: Mapped[ReviewStatus] = mapped_column(
        _enum(ReviewStatus, "review_status"), nullable=False, default=ReviewStatus.not_required
    )
    overall_band: Mapped[OverallBand] = mapped_column(
        _enum(OverallBand, "overall_band"), nullable=False, default=OverallBand.clear
    )
    detector_confidence_state: Mapped[ConfidenceState] = mapped_column(
        _enum(ConfidenceState, "confidence_state"), nullable=False
    )
    ocr_confidence_state: Mapped[ConfidenceState] = mapped_column(
        _enum(ConfidenceState, "confidence_state"), nullable=False
    )
    translation_state: Mapped[TranslationState] = mapped_column(
        _enum(TranslationState, "translation_state"), nullable=False
    )
    #: Danh sách mã lý do — CHỈ nhận giá trị trong bảng trắng của mã, không phải chữ tự do.
    reason_codes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    #: Số liệu thô làm bằng chứng (độ dài chữ, tỉ lệ khung, engine…). Không chứa khoá bí mật.
    evidence_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
