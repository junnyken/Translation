"""Pydantic schema cho response — KHÔNG bao giờ trả thẳng SQLAlchemy object ra API."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
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


# ---------- M9: chạy cả mẻ ----------
class BatchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_pipeline: BatchPipeline = BatchPipeline.full_pipeline
    #: Chốt engine dịch NGAY LÚC TẠO mẻ. NULL = dùng mặc định trong cấu hình.
    translation_engine: TranslationEngine | None = None


class BatchAccepted(BaseModel):
    batch_run_id: uuid.UUID
    status: BatchStatus
    total_pages: int


class BatchRunRead(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    requested_pipeline: BatchPipeline
    translation_engine: TranslationEngine | None
    #: SUY RA từ các mục con — `completed` chỉ khi mọi trang đã xong.
    status: BatchStatus
    total_pages: int
    completed_pages: int
    failed_pages: int
    blocked_pages: int
    started_at: datetime | None
    finished_at: datetime | None
    #: Đã lọc bỏ thứ giống khoá bí mật trước khi lưu.
    error_summary: str | None
    created_at: datetime
    updated_at: datetime


class BatchItemRead(ORMModel):
    id: uuid.UUID
    page_id: uuid.UUID
    page_order: int
    status: BatchItemStatus
    current_job_id: uuid.UUID | None
    retry_count: int
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None


class BatchItemsPage(BaseModel):
    items: list[BatchItemRead]
    next_cursor: int | None


class BatchResumeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Bỏ trống = chạy lại MỌI mục failed/blocked_quota của mẻ.
    item_ids: list[uuid.UUID] | None = None


class BatchResumeAccepted(BaseModel):
    batch_run_id: uuid.UUID
    resumed_count: int
    status: BatchStatus


class BatchConfigRead(BaseModel):
    """Cấu hình mẻ cho giao diện — CHỈ true/false và các con số, **không bao giờ** có khoá.

    Có cái này thì giao diện mới nói được lý do thật ("chưa cấu hình khoá dịch") thay vì hiện
    một lựa chọn rồi để người dùng bấm vào và nhận 422.
    """

    llm_configured: bool
    llm_project_rpm: int
    batch_max_concurrent_pages: int
    batch_max_retries: int
    batch_retry_backoff_base_seconds: float
    batch_retry_backoff_max_seconds: float


class BatchRunList(BaseModel):
    runs: list[BatchRunRead]


# ---------- M10: khai báo mục đích & cảnh báo trước khi xuất ----------
class ExportWarningsRead(BaseModel):
    """Những gì phải hiện ra trước khi người dùng mang file đi.

    `acknowledged` cho giao diện biết chapter này đã xác nhận lần nào chưa — cảnh báo chỉ hiện
    **một lần**, hiện lại mỗi lần xuất là kiểu cảnh báo mà ai cũng bấm cho qua.

    Ba số của E12 nằm RIÊNG, không gộp vào hai số cũ: "cần rà soát" là chuyện chất lượng, còn
    xác nhận bản quyền là chuyện pháp lý — trộn vào nhau sẽ khiến người dùng tưởng tick một ô
    là xong cả hai.
    """

    overflow_warning_count: int
    needs_manual_count: int
    acknowledged: bool
    acknowledged_at: datetime | None
    #: E14 — bố cục: vùng đang căn theo khung chữ nhật dự phòng vì không xác định được hình
    #: bong bóng. KHÔNG gộp vào số tràn khung: tràn khung là chữ không vừa, còn đây là
    #: "không biết lòng bong bóng ở đâu" — hai chuyện khác nhau.
    shape_fallback_count: int = 0
    #: E14 — vùng chưa xác định được vùng an toàn và cần người xem.
    shape_needs_review_count: int = 0
    #: E15 — hướng chữ. TÁCH RIÊNG khỏi bố cục bong bóng (E14) và khỏi tràn khung: một vùng
    #: có thể vừa khít, đúng bong bóng, mà chữ vẫn đang bị căn sai hướng.
    orientation_vertical_rendered_count: int = 0
    orientation_review_count: int = 0
    orientation_unknown_count: int = 0
    #: E12 — vùng máy đề nghị xem lại trước khi xuất.
    quality_needs_review_count: int = 0
    #: E12 — vùng CHƯA đánh giá được. Không bao giờ gộp vào "rõ ràng".
    quality_unassessed_count: int = 0
    #: E12 — vùng người dùng đã chủ động bỏ qua.
    quality_reviewed_skip_count: int = 0


class AcknowledgeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Đã tick "Đã đọc và chấp nhận trách nhiệm bản quyền" hay chưa. Gửi `false` cũng được ghi
    #: nhận — có người mở cảnh báo ra rồi bỏ đi cũng là một sự thật đáng lưu.
    user_acknowledged: bool


class AcknowledgeRead(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    export_job_id: uuid.UUID | None
    intended_use: IntendedUse
    overflow_warning_count: int
    needs_manual_count: int
    user_acknowledged: bool
    acknowledged_at: datetime | None


# ---------- E12: cổng chất lượng từng vùng ----------
class LyDoRead(BaseModel):
    """Một dấu hiệu: mã để đếm, câu để đọc. Không bao giờ chỉ có mã."""

    ma: str
    nhan: str


class RegionQualityRead(ORMModel):
    region_id: uuid.UUID
    reading_order: int | None = None
    assessment_version: str
    relevance: RegionRelevance
    review_status: ReviewStatus
    overall_band: OverallBand
    detector_confidence_state: ConfidenceState
    ocr_confidence_state: ConfidenceState
    translation_state: TranslationState
    ly_do: list[LyDoRead] = []
    evidence_snapshot: dict = {}
    assessed_at: datetime


class QualitySummary(BaseModel):
    """Đếm theo nhóm. `chua_danh_gia` KHÔNG được gộp vào `ro_rang` — chưa chấm khác với chấm sạch."""

    tong_vung: int
    ro_rang: int
    can_ra_soat: int
    chua_danh_gia: int
    da_bo_qua: int
    vung_tran_khung: int
    theo_phan_loai: dict[str, int]


class PageQualityRead(BaseModel):
    page_id: uuid.UUID
    assessment_version: str | None
    summary: QualitySummary
    regions: list[RegionQualityRead]


class QualityReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: CHỈ nhận hai quyết định của người. Máy khách không được tự đặt mức, mã lý do hay bằng chứng.
    decision: Literal["keep", "skip"]


class QualityReviewRead(BaseModel):
    region_id: uuid.UUID
    review_status: ReviewStatus
    relevance: RegionRelevance
    overall_band: OverallBand


# ---------- E13: thuật ngữ, giọng nhân vật, rà soát nhất quán ----------
class GlossaryEntryCreate(BaseModel):
    """`definition` bắt buộc: một cặp chữ trần trụi không đủ để giữ bản dịch nhất quán."""

    model_config = ConfigDict(extra="forbid")

    source_term: str = Field(min_length=1, max_length=500)
    target_term: str = Field(min_length=1, max_length=500)
    term_type: TermType
    definition: str = Field(min_length=1, max_length=2000)
    usage_note: str | None = Field(default=None, max_length=2000)
    #: Chỉ để CẢNH BÁO — hệ thống không bao giờ tự thay chữ theo danh sách này.
    prohibited_variants: list[str] = Field(default_factory=list, max_length=20)


class GlossaryEntryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_term: str | None = Field(default=None, min_length=1, max_length=500)
    target_term: str | None = Field(default=None, min_length=1, max_length=500)
    term_type: TermType | None = None
    definition: str | None = Field(default=None, min_length=1, max_length=2000)
    usage_note: str | None = Field(default=None, max_length=2000)
    prohibited_variants: list[str] | None = Field(default=None, max_length=20)


class GlossaryEntryRead(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    source_lang: SourceLang
    target_lang: TargetLang
    source_term: str
    target_term: str
    term_type: TermType
    definition: str
    usage_note: str | None
    prohibited_variants: list[str]
    #: CHỈ `approved` mới được đem đi quét. Sửa nội dung đã duyệt sẽ quay về `draft`.
    status: GlossaryStatus
    created_at: datetime
    updated_at: datetime


class VoiceProfileCreate(BaseModel):
    """Hướng dẫn biên tập do NGƯỜI đặt — không phải suy luận của máy."""

    model_config = ConfigDict(extra="forbid")

    character_name: str = Field(min_length=1, max_length=200)
    aliases: list[str] = Field(default_factory=list, max_length=20)
    speech_register: SpeechRegister = SpeechRegister.neutral
    vietnamese_pronoun_guidance: str | None = Field(default=None, max_length=1000)
    tone_note: str | None = Field(default=None, max_length=1000)


class VoiceProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    character_name: str | None = Field(default=None, min_length=1, max_length=200)
    aliases: list[str] | None = Field(default=None, max_length=20)
    speech_register: SpeechRegister | None = None
    vietnamese_pronoun_guidance: str | None = Field(default=None, max_length=1000)
    tone_note: str | None = Field(default=None, max_length=1000)


class VoiceProfileRead(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    character_name: str
    aliases: list[str]
    speech_register: SpeechRegister
    vietnamese_pronoun_guidance: str | None
    tone_note: str | None
    status: VoiceProfileStatus
    created_at: datetime
    updated_at: datetime


class ConsistencyScanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: v1 chỉ có chế độ quét theo luật — không có chế độ nào gọi LLM ở đây.
    mode: Literal["rules"] = "rules"


class ConsistencySummary(BaseModel):
    """Chỉ đếm việc cần rà soát. **Không** có điểm chất lượng 0–100 — máy không đo được điều đó."""

    open_count: int
    accepted_count: int
    rejected_count: int
    stale_count: int
    resolved_no_change_count: int
    by_type: dict[str, int]
    approved_glossary_count: int
    active_voice_profile_count: int


class ConsistencyTaskRead(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    region_id: uuid.UUID
    glossary_entry_id: uuid.UUID | None
    voice_profile_id: uuid.UUID | None
    task_type: ConsistencyTaskType
    status: ConsistencyTaskStatus
    #: Bản dịch tại lúc tạo việc — khác bản hiện tại nghĩa là việc đã cũ.
    current_text_snapshot: str | None
    proposed_text: str | None
    #: Vì sao có việc này: thuật ngữ đã duyệt, đoạn khớp, bản dịch hiện tại, lý do bằng tiếng Việt.
    evidence: dict
    created_at: datetime
    resolved_at: datetime | None


class ConsistencyTasksPage(BaseModel):
    items: list[ConsistencyTaskRead]
    next_cursor: int | None


class TaskAcceptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Bỏ trống = dùng bản đề xuất. Có = dùng bản người dùng tự sửa.
    edited_text: str | None = Field(default=None, max_length=5000)


class TaskAcceptAccepted(BaseModel):
    """Giống hợp đồng của M7: canh lại chạy nền nên trạng thái vừa khung chưa biết ngay."""

    task_id: uuid.UUID
    region_id: uuid.UUID
    page_id: uuid.UUID
    refit_job_id: uuid.UUID | None
    applied_text: str


class TaskRejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolution: Literal["keep_current", "not_applicable"]


class SafeAreaRead(BaseModel):
    """Vùng đặt chữ an toàn của một vùng chữ (E14).

    KHÔNG bao giờ trả về điểm ảnh của ảnh gốc/ảnh sạch qua đây — chỉ hình học và lý do.
    """

    region_id: uuid.UUID
    algorithm_version: str
    source: str
    status: str
    geometry_type: str
    geometry: dict
    roi: dict
    safe_area_pixels: int | None = None
    bbox_coverage_ratio: float | None = None
    reason_codes: list[str] = Field(default_factory=list)
    config_summary: dict = Field(default_factory=dict)
    #: Ô chữ nhật thực sự dùng để đặt chữ, nằm gọn trong hình trên. Giao diện vẽ đúng ô này
    #: thay vì tự suy ra — suy ra ở hai nơi là hai kết quả khác nhau.
    place_rect: dict | None = None


class PageSafeAreaSummary(BaseModel):
    page_id: uuid.UUID
    total_regions: int
    shape_derived_count: int
    fallback_rectangle_count: int
    needs_review_count: int
    failed_count: int
    #: Vùng chưa từng được tính — khác hẳn "đã tính và không ra hình".
    not_computed_count: int


class OrientationRead(BaseModel):
    """Hướng chữ của một vùng + bằng chứng. Không trả điểm ảnh, không trả chữ OCR."""

    region_id: uuid.UUID
    algorithm_version: str
    orientation: str
    source: str
    status: str
    rotation_degrees: float | None = None
    line_count_estimate: int | None = None
    reason_codes: list[str] = Field(default_factory=list)
    evidence_summary: dict = Field(default_factory=dict)


class PageOrientationSummary(BaseModel):
    page_id: uuid.UUID
    total_regions: int
    horizontal_count: int
    vertical_ready_count: int
    vertical_review_count: int
    rotated_review_count: int
    unknown_count: int
    unavailable_count: int
    not_analyzed_count: int


# ---------- E17: ứng viên thuật ngữ & tín hiệu xưng hô ----------
class TrichDanRead(BaseModel):
    """Câu THẬT trong `raw_text`. Không phải chuỗi dựng lại — người dùng đối chiếu được."""

    page_order: int
    region_id: uuid.UUID
    text: str


class TermCandidateRead(BaseModel):
    source_term: str
    term_key: str
    #: Số lần xuất hiện trong toàn chapter — đếm được, không ước lượng.
    count: int
    pages: list[int]
    quotes: list[TrichDanRead]
    #: GỢI Ý loại để điền sẵn form. Người dùng đổi thoải mái.
    type_guess: TermType
    #: Vì sao nó được nêu ra. Hiện thẳng cho người đọc, không giấu trong log.
    reasons: list[str]


class TermCandidatesResponse(BaseModel):
    """Ba trạng thái rỗng KHÔNG được gộp — xem `trang_thai`."""

    ung_vien: list[TermCandidateRead]
    so_vung_da_quet: int
    so_vung_co_chu: int
    #: `chua_doc_chu` (chưa chạy bước đọc chữ) · `khong_thay` (đã tìm, không có) ·
    #: `deu_da_co` (tìm được nhưng đều đã nằm trong danh sách thuật ngữ) · `co_ung_vien`.
    trang_thai: Literal["chua_doc_chu", "khong_thay", "deu_da_co", "co_ung_vien"]
    so_bi_loc_vi_da_co: int
    #: Luật nào đã dùng cho ngôn ngữ này (vd tiếng Anh toàn chữ hoa thì đổi luật).
    ghi_chu_ngon_ngu: str | None = None
    #: Vùng có chữ nhưng máy tự khai đọc CHƯA CHẮC — không dùng để gợi ý, và nói ra chứ không giấu.
    so_vung_khong_chac: int = 0


class VoiceSignalRead(BaseModel):
    ma: str
    nhan: str
    goi_y_xung_ho: str
    speech_register_goi_y: SpeechRegister
    count: int
    #: Tên đi kèm tín hiệu, chỉ có với hậu tố kính ngữ gắn vào tên.
    ten_lien_quan: list[str]
    quotes: list[TrichDanRead]


class VoiceSignalsResponse(BaseModel):
    tin_hieu: list[VoiceSignalRead]
    so_vung_da_quet: int
    so_vung_co_chu: int
    trang_thai: Literal["chua_doc_chu", "khong_thay", "co_tin_hieu"]
    so_vung_khong_chac: int = 0


class TermSuggestionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Tên bộ truyện, nguyên văn người dùng gõ.
    series_name: str = Field(min_length=1, max_length=300)


class TermSuggestionRunRead(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    series_name: str
    status: TermSuggestionStatus
    model_name: str | None
    #: `None` = chưa chạy xong. `[]` = chạy xong và không mục nào qua được cổng đối chiếu.
    suggestions: list[dict] | None
    #: Số mục model trả về mà KHÔNG khớp danh sách đã hỏi ⇒ bị loại. `> 0` nghĩa là model có bịa.
    dropped_count: int
    asked_count: int
    error_log: str | None
    created_at: datetime
    updated_at: datetime
