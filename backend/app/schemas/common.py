"""Pydantic schema cho response — KHÔNG bao giờ trả thẳng SQLAlchemy object ra API."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    ExportFormat,
    IntendedUse,
    FitStatus,
    OCREngine,
    OCRStatus,
    TranslationEngine,
    TranslationStatus,
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


# ---------- OCRResult (M3) ----------
class OCRResultRead(ORMModel):
    region_id: uuid.UUID
    raw_text: str | None
    ocr_engine: OCREngine | None
    #: NULL khi engine không cung cấp confidence thật (manga-ocr) — KHÔNG phải bug.
    confidence: float | None
    status: OCRStatus


# ---------- TranslationResult (M5) ----------
class TranslationResultRead(ORMModel):
    region_id: uuid.UUID
    translated_text: str | None
    engine: TranslationEngine | None
    model_name: str | None
    #: Chi phí token của CẢ TRANG, ghi ở đúng 1 dòng đầu trang (các dòng khác NULL)
    #: để cộng toàn bảng vẫn ra tổng thật.
    token_cost: int | None
    edited_by_user: bool
    status: TranslationStatus


# ---------- TypesetResult (M6) ----------
class TypesetResultRead(ORMModel):
    region_id: uuid.UUID
    font_family: str | None
    #: NULL khi vùng chưa có bản dịch để canh (`fit_status=pending`) — KHÔNG phải bug.
    font_size: float | None
    wrapped_text: str | None
    padding_ratio: float | None
    #: `fit_ok` · `overflow_warning` (không vừa dù đã xuống cỡ nhỏ nhất) · `pending` (chưa có chữ).
    fit_status: FitStatus
    edited_by_user: bool


# ---------- M7: sửa tay từng vùng ----------
class BBoxIn(BaseModel):
    """Khung chữ do người dùng kéo lại. Rộng/cao phải dương — bbox âm là vô nghĩa."""

    x: float = Field(ge=0)
    y: float = Field(ge=0)
    w: float = Field(gt=0)
    h: float = Field(gt=0)


class RegionPatch(BaseModel):
    """Sửa tay 1 vùng. Trường nào bỏ trống thì giữ nguyên trường đó.

    `font_size` có nghĩa **ghim cỡ chữ**: canh lại sẽ dùng đúng cỡ đó thay vì tự dò.
    Bỏ trống `font_size` = quay lại chế độ tự dò cỡ.
    """

    model_config = ConfigDict(extra="forbid")

    translated_text: str | None = None
    bbox: BBoxIn | None = None
    font_family: str | None = None
    font_size: float | None = Field(default=None, gt=0)

    def co_thay_doi(self) -> bool:
        return any(
            v is not None
            for v in (self.translated_text, self.bbox, self.font_family, self.font_size)
        )


class JobAccepted(BaseModel):
    """Đã xếp việc vào hàng đợi. Kết quả tra bằng `GET /jobs/{job_id}` — không chạy trong request."""

    job_id: uuid.UUID
    page_id: uuid.UUID
    status: JobStatus


class RegionPatchAccepted(BaseModel):
    """Sửa xong là ghi ngay, nhưng canh chữ lại chạy nền — nên `fit_status` trả về là
    `pending`, KHÔNG phải trạng thái cũ (bản canh cũ đã không còn đúng với nội dung mới)."""

    region_id: uuid.UUID
    page_id: uuid.UUID
    fit_status: FitStatus
    refit_job_id: uuid.UUID
    edited_fields: list[str]
    edited_by_user: bool


class RegionDetail(ORMModel):
    """Gom mọi thứ của 1 vùng cho màn sửa tay: khung, chữ gốc, bản dịch, kết quả canh chữ."""

    id: uuid.UUID
    bbox: BBoxOut
    confidence: float | None
    overlap_suspect: bool
    reading_order: int | None
    status: RegionStatus
    #: Chữ gốc OCR đọc được (M3) — `null` nếu chưa chạy OCR.
    raw_text: str | None = None
    ocr_confidence: float | None = None
    ocr_status: OCRStatus | None = None
    translated_text: str | None = None
    translation_status: TranslationStatus | None = None
    translation_edited_by_user: bool = False
    font_family: str | None = None
    font_size: float | None = None
    wrapped_text: str | None = None
    fit_status: FitStatus | None = None
    typeset_edited_by_user: bool = False


class PageDetail(BaseModel):
    """Toàn bộ dữ liệu 1 trang cho màn sửa tay (M7) — gọi 1 lần thay vì 5 lần."""

    page: PageRead
    #: Đường dẫn ảnh xem thử. `null` khi chưa canh chữ xong.
    preview_url: str | None
    #: Danh sách font được phép chọn — lấy từ whitelist của M6, UI không tự chế thêm.
    font_families: list[str]
    min_font_size: int
    max_font_size: int
    regions: list[RegionDetail]


# ---------- M8: xuất chapter ----------
class ExportRequest(BaseModel):
    """Xin xuất chapter. `format` bắt buộc — không đoán thay người dùng."""

    model_config = ConfigDict(extra="forbid")

    format: ExportFormat


class ExportPreview(BaseModel):
    """Xem trước TRƯỚC khi xuất — để người dùng quyết định xuất luôn hay sửa tay tiếp."""

    #: Số trang thật sự sẽ được xuất (chỉ tính trang đã canh chữ xong).
    page_count: int
    total_page_count: int
    #: Trang chưa canh chữ xong sẽ bị BỎ QUA, không xuất ảnh chưa có chữ.
    skipped_page_count: int
    #: Số vùng còn tràn khung. Không chặn xuất, nhưng phải hiện rõ.
    overflow_warning_count: int


class ExportJobRead(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    format: ExportFormat
    status: JobStatus
    #: Đường dẫn file `.cbz`/`.zip`, hoặc THƯ MỤC khi format là `png_single`. NULL khi chưa xong.
    output_path: str | None
    page_count: int
    overflow_warning_count: int
    #: Khi `status=done` mà trường này khác NULL: xuất được nhưng CÓ cảnh báo
    #: (bỏ qua trang chưa canh chữ, hoặc còn vùng tràn khung).
    error_log: str | None
    created_at: datetime
    updated_at: datetime


class ExportJobAccepted(BaseModel):
    job_id: uuid.UUID
    project_id: uuid.UUID
    status: JobStatus
