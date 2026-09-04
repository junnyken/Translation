"""SQLAlchemy models — 7 bảng chốt ở M1 (Project, Page, TextRegion, OCRResult,
TranslationResult, TypesetResult, Job). Không tạo thêm bảng ngoài danh sách này."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
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
    OrientationSource,
    OrientationStatus,
    TextOrientation,
    SafeAreaGeometryType,
    SafeAreaSource,
    SafeAreaStatus,
    BatchItemStatus,
    ConsistencyTaskStatus,
    ConsistencyTaskType,
    GlossaryStatus,
    SpeechRegister,
    TermSuggestionStatus,
    TermType,
    VoiceProfileStatus,
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


class NguoiDung(TimestampMixin, Base):
    """Tài khoản thật (Auth slice B).

    Slice A chỉ có **một khoá chung**: ai cầm khoá là làm được mọi thứ với chapter của mọi
    người. Bảng này là thứ cho phép nói "chapter này của ai".

    `email` lưu **đã hạ chữ thường** — nếu không, `An@x.com` và `an@x.com` thành hai tài khoản
    khác nhau và người dùng sẽ không hiểu vì sao mật khẩu đúng mà không vào được.

    `mat_khau_bam` chứa cả tham số scrypt (xem `app.core.mat_khau`), nên đổi độ khó về sau
    không khoá người cũ ra ngoài.
    """

    __tablename__ = "nguoi_dung"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    ten_hien: Mapped[str] = mapped_column(String(120), nullable=False)
    mat_khau_bam: Mapped[str] = mapped_column(String(255), nullable=False)
    #: Khoá tài khoản mà không xoá dữ liệu của họ. Xoá người dùng sẽ kéo theo chapter (FK), nên
    #: "nghỉ việc" phải là tắt cờ này chứ không phải DELETE.
    dang_hoat_dong: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    #: Người đầu tiên đăng ký thành quản trị: có quyền nhận các chapter cũ chưa có chủ.
    la_quan_tri: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    phien: Mapped[list["Phien"]] = relationship(
        back_populates="nguoi_dung", cascade="all, delete-orphan"
    )


class Phien(TimestampMixin, Base):
    """Một lần đăng nhập còn hiệu lực.

    Lưu **băm** của mã phiên chứ không lưu mã thô: người đọc trộm được CSDL sẽ không mạo danh
    được ai (xem `app.core.phien` giải thích vì sao băm ở đây dùng SHA-256 chứ không scrypt).

    Có bảng này (thay vì JWT) để **thu hồi được**: đăng xuất là xoá một dòng, hiệu lực tức thì.
    """

    __tablename__ = "phien"
    __table_args__ = (Index("ix_phien_nguoi_dung", "nguoi_dung_id"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    nguoi_dung_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("nguoi_dung.id", ondelete="CASCADE"), nullable=False
    )
    ma_bam: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    het_han: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    #: Để người dùng nhìn thấy "thiết bị nào đang đăng nhập". NULL = chưa từng dùng lại sau khi tạo.
    dung_lan_cuoi: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    nguoi_dung: Mapped[NguoiDung] = relationship(back_populates="phien")


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
    #: Chủ của chapter. **Cho phép NULL** có chủ đích: chapter tạo trước slice B không có chủ,
    #: và gán bừa cho một tài khoản nào đó là đoán mò. NULL = "chưa có chủ", ai đăng nhập cũng
    #: thấy và quản trị có thể nhận về (xem `docs/REPORT_B1.md`).
    #: `ondelete=SET NULL`: xoá tài khoản KHÔNG được kéo theo chapter — mất việc của người khác.
    chu_so_huu_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("nguoi_dung.id", ondelete="SET NULL"), nullable=True,
        index=True,
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
    #: Đường bao từng dòng chữ do engine trả về, TOẠ ĐỘ ẢNH GỐC. `None` nghĩa là engine không
    #: cung cấp (manga-ocr chỉ trả chuỗi) — khác hẳn `[]` nghĩa là có hỏi nhưng không có dòng nào.
    #: Đây là bằng chứng hình học DUY NHẤT hệ thống có về hướng của chữ: bộ nhận diện chỉ cho
    #: khung chữ nhật, còn ảnh đã xoá chữ thì không còn chữ để đo (đo thật: còn 0–4 điểm ảnh).
    line_polygons: Mapped[list | None] = mapped_column(JSONB, nullable=True)
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
    "NguoiDung",
    "Phien",
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


class GlossaryEntry(TimestampMixin, Base):
    """Thuật ngữ đã chốt cho MỘT project (E13).

    Cố ý theo từng project: cách dịch chấp nhận được ở truyện này không được tự lan sang truyện
    khác — mỗi bộ truyện có thế giới riêng.

    `definition` là BẮT BUỘC: một cặp chữ trần trụi không đủ để giữ bản dịch nhất quán, người
    duyệt sau này cần biết thuật ngữ đó nghĩa là gì mới quyết được từng chỗ.
    """

    __tablename__ = "glossary_entry"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "source_lang", "source_term_key", name="uq_glossary_project_term"
        ),
        Index("ix_glossary_project_status", "project_id", "status"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("project.id", ondelete="CASCADE"), nullable=False
    )
    source_lang: Mapped[SourceLang] = mapped_column(_enum(SourceLang, "source_lang"), nullable=False)
    target_lang: Mapped[TargetLang] = mapped_column(_enum(TargetLang, "target_lang"), nullable=False)
    #: Nguyên văn người dùng nhập — hiển thị lại đúng như họ gõ.
    source_term: Mapped[str] = mapped_column(Text, nullable=False)
    #: Dạng đã chuẩn hoá, CHỈ dùng để so khớp và chống trùng. Không bao giờ hiển thị.
    source_term_key: Mapped[str] = mapped_column(Text, nullable=False)
    target_term: Mapped[str] = mapped_column(Text, nullable=False)
    term_type: Mapped[TermType] = mapped_column(_enum(TermType, "term_type"), nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    usage_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Các biến thể người dùng tự khai là CẤM. Chỉ để cảnh báo — không bao giờ tự thay chữ.
    prohibited_variants: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[GlossaryStatus] = mapped_column(
        _enum(GlossaryStatus, "glossary_status"), nullable=False, default=GlossaryStatus.draft
    )


class CharacterVoiceProfile(TimestampMixin, Base):
    """Hướng dẫn giọng cho một nhân vật (E13).

    Đây là **chỉ dẫn biên tập của người dùng**, không phải kết luận của máy — nên cố ý KHÔNG có
    trường "độ tin cậy". Máy không được suy ra tính cách nhân vật rồi tự sửa lời thoại.
    """

    __tablename__ = "character_voice_profile"
    __table_args__ = (
        UniqueConstraint("project_id", "character_name_key", name="uq_voice_project_name"),
        Index("ix_voice_project_status", "project_id", "status"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("project.id", ondelete="CASCADE"), nullable=False
    )
    character_name: Mapped[str] = mapped_column(Text, nullable=False)
    character_name_key: Mapped[str] = mapped_column(Text, nullable=False)
    aliases: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    speech_register: Mapped[SpeechRegister] = mapped_column(
        _enum(SpeechRegister, "speech_register"), nullable=False, default=SpeechRegister.neutral
    )
    #: Ví dụ "xưng ta, gọi ngươi" — do NGƯỜI đặt, không phải máy đoán.
    vietnamese_pronoun_guidance: Mapped[str | None] = mapped_column(Text, nullable=True)
    tone_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[VoiceProfileStatus] = mapped_column(
        _enum(VoiceProfileStatus, "voice_profile_status"),
        nullable=False,
        default=VoiceProfileStatus.draft,
    )


class ConsistencyReviewTask(TimestampMixin, Base):
    """Một việc cần người rà soát (E13) — KHÔNG BAO GIỜ tự áp dụng.

    `snapshot_hash` chốt bản dịch tại thời điểm tạo việc. Bản dịch đổi sau đó ⇒ việc thành
    `stale` và không được áp nữa; áp một đề xuất dựa trên bản dịch cũ là ghi đè mất công người
    khác vừa sửa.
    """

    __tablename__ = "consistency_review_task"
    __table_args__ = (
        # Postgres coi mỗi NULL là một giá trị KHÁC NHAU, nên `UNIQUE` thường vẫn cho chèn trùng
        # khi khoá ngoại để trống (đã kiểm chứng trên PG 16.15). `NULLS NOT DISTINCT` mới chặn
        # đúng — đây là điều kiện để quét lại không đẻ ra việc trùng.
        UniqueConstraint(
            "region_id", "task_type", "glossary_entry_id", "voice_profile_id", "snapshot_hash",
            name="uq_consistency_task_idem",
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_consistency_project_status_type", "project_id", "status", "task_type"),
        Index("ix_consistency_region", "region_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("project.id", ondelete="CASCADE"), nullable=False
    )
    region_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("text_region.id", ondelete="CASCADE"), nullable=False
    )
    glossary_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("glossary_entry.id", ondelete="CASCADE"), nullable=True
    )
    voice_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("character_voice_profile.id", ondelete="CASCADE"),
        nullable=True,
    )
    task_type: Mapped[ConsistencyTaskType] = mapped_column(
        _enum(ConsistencyTaskType, "consistency_task_type"), nullable=False
    )
    status: Mapped[ConsistencyTaskStatus] = mapped_column(
        _enum(ConsistencyTaskStatus, "consistency_task_status"),
        nullable=False,
        default=ConsistencyTaskStatus.open,
    )
    #: Bản dịch tại thời điểm tạo việc — để phát hiện việc đã cũ.
    current_text_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Đề xuất — chỉ là đề xuất, không bao giờ được ghi thẳng vào bản dịch.
    proposed_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Bằng chứng vì sao có việc này: thuật ngữ đã duyệt, đoạn khớp, biến thể đang dùng, lý do.
    #: TUYỆT ĐỐI không chứa khoá bí mật hay phản hồi thô của nhà cung cấp.
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RegionSafeArea(TimestampMixin, Base):
    """Vùng đặt chữ an toàn của một bong bóng (E14).

    Đây là dữ liệu **thêm vào**, không thay `TextRegion.bbox`: bbox là bằng chứng của bộ nhận
    diện M2 và còn dùng để đối chiếu, nên không được sửa lịch sử đó. Mỗi vùng chữ giữ đúng
    **một** bản hiện hành; muốn dựng lại bản cũ thì đã có `algorithm_version` + `config_snapshot`.
    """

    __tablename__ = "region_safe_area"

    id: Mapped[uuid.UUID] = _uuid_pk()
    region_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("text_region.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[SafeAreaSource] = mapped_column(
        _enum(SafeAreaSource, "safe_area_source"), nullable=False
    )
    status: Mapped[SafeAreaStatus] = mapped_column(
        _enum(SafeAreaStatus, "safe_area_status"), nullable=False
    )

    roi_x: Mapped[int] = mapped_column(Integer, nullable=False)
    roi_y: Mapped[int] = mapped_column(Integer, nullable=False)
    roi_w: Mapped[int] = mapped_column(Integer, nullable=False)
    roi_h: Mapped[int] = mapped_column(Integer, nullable=False)

    geometry_type: Mapped[SafeAreaGeometryType] = mapped_column(
        _enum(SafeAreaGeometryType, "safe_area_geometry_type"), nullable=False
    )
    #: Đỉnh đa giác hoặc hình chữ nhật, TOẠ ĐỘ ẢNH GỐC. Không bao giờ để rỗng — kể cả khi
    #: dự phòng, vì "không có hình" mà đọc thành "vừa khít" là đúng kiểu lỗi im lặng dự án này
    #: đang săn.
    geometry_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    safe_area_pixels: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox_coverage_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason_codes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    config_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    #: Ô chữ nhật THỰC SỰ dùng để đặt chữ, nằm gọn trong hình trên. Tính MỘT lần ở worker rồi
    #: lưu lại: bước căn chữ, ảnh xem thử, file xuất và lớp phủ trên giao diện đều đọc đúng ô
    #: này. Tính lại ở mỗi nơi là bốn cơ hội để lệch nhau.
    place_rect_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    #: Ảnh clean lúc tính. Ảnh clean đổi (chạy lại xoá chữ) ⇒ hình cũ hết hiệu lực.
    clean_image_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)


class RegionTextOrientation(TimestampMixin, Base):
    """Hướng chữ của một vùng + bằng chứng dẫn tới kết luận đó (E15).

    Chỉ để **căn chữ và điều hướng rà soát**. Không bao giờ sửa chữ OCR, không đảo thứ tự đọc,
    không xoay ảnh — những thứ đó thuộc hợp đồng của M3/M5 và ảnh gốc là bằng chứng.
    """

    __tablename__ = "region_text_orientation"

    id: Mapped[uuid.UUID] = _uuid_pk()
    region_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("text_region.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)
    orientation: Mapped[TextOrientation] = mapped_column(
        _enum(TextOrientation, "text_orientation"), nullable=False
    )
    source: Mapped[OrientationSource] = mapped_column(
        _enum(OrientationSource, "orientation_source"), nullable=False
    )
    status: Mapped[OrientationStatus] = mapped_column(
        _enum(OrientationStatus, "orientation_status"), nullable=False
    )
    #: Chỉ có nghĩa với `rotated_horizontal`, và v1 **không** dùng nó để xoay chữ.
    rotation_degrees: Mapped[float | None] = mapped_column(Float, nullable=True)
    line_count_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason_codes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    evidence_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class ArtifactBlob(Base):
    """Hiện vật nhị phân — ảnh gốc, ảnh clean, ảnh xem thử, file xuất — lưu THẲNG trong CSDL.

    P3e. Vì sao lại nhét ảnh vào CSDL, một việc bình thường là ý tồi:

    P3c đã dò và chứng minh VibeHost **không cấp được volume bền** (không có trong mô hình tài
    nguyên, không công cụ nào nhận khai báo volume, `appdata = 0` trên cả 12 dịch vụ). Hệ tệp
    container thì bị xoá sạch mỗi lần triển khai lại. CSDL là **nguyên thể bền duy nhất** nền
    tảng cấp — và nó đã tự chứng minh điều đó theo cách khó chịu nhất: sau mỗi lần redeploy,
    hàng `page` còn nguyên trong khi tệp ảnh biến mất, đẻ ra trang "đã canh chữ xong" mà bấm
    vào thì 404.

    Nói cách khác: đây **không phải** lựa chọn kiến trúc đẹp, mà là lựa chọn *khả thi* duy nhất
    còn lại. Đổi sang S3/Supabase sau này chỉ là viết thêm một lớp `IObjectStorage` — P3d đã dọn
    xong đường cho việc đó.

    `path` là khoá chính và **giữ nguyên chuỗi** mà backend `local` vẫn dùng
    (`projects/<pid>/pages/<page_id>.png`) ⇒ đổi backend không phải migrate dữ liệu bảng khác.
    """

    __tablename__ = "artifact_blob"

    path: Mapped[str] = mapped_column(Text, primary_key=True)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    #: Lưu tách khỏi `data` để `stat()` không phải kéo cả hiện vật lên chỉ để biết nó nặng bao nhiêu.
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class TermSuggestionRun(TimestampMixin, Base):
    """Một lượt xin gợi ý cách dịch danh xưng theo tên bộ truyện (E17 tầng 3).

    Vì sao có bảng riêng chứ không mượn `Job`: `Job.page_id` là NOT NULL còn việc này gắn với cả
    chapter; và quan trọng hơn, **kết quả phải lưu lại được để đối chất**. Đây là chỗ duy nhất
    trong hệ thống hỏi mô hình một câu mà câu trả lời không đến từ dữ liệu của người dùng, nên
    phải ghi lại: đã hỏi gì (`series_name`), model nào, nó trả về bao nhiêu mục, và **cổng đối
    chiếu đã loại bao nhiêu mục** (`dropped_count`).

    `dropped_count > 0` là bằng chứng sống rằng model có bịa — giữ con số đó, đừng làm tròn nó đi.
    """

    __tablename__ = "term_suggestion_run"
    __table_args__ = (Index("ix_term_suggestion_project", "project_id", "created_at"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("project.id", ondelete="CASCADE"), nullable=False
    )
    #: Nguyên văn người dùng gõ. Không chuẩn hoá, không đoán lại — để đối chất khi kết quả lạ.
    series_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TermSuggestionStatus] = mapped_column(
        _enum(TermSuggestionStatus, "term_suggestion_status"),
        nullable=False,
        default=TermSuggestionStatus.queued,
    )
    model_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    #: Danh sách gợi ý ĐÃ QUA cổng đối chiếu. NULL = chưa chạy xong; [] = chạy xong và không còn
    #: mục nào sống sót. Hai thứ đó khác nhau và không được gộp.
    suggestions: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    #: Số mục model trả về nhưng KHÔNG có trong chữ của chapter ⇒ bị loại thẳng.
    dropped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Số ứng viên đã gửi đi hỏi — để biết tỉ lệ model trả lời được.
    asked_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_log: Mapped[str | None] = mapped_column(Text, nullable=True)
