"""Toàn bộ enum của pipeline MTE — tên/giá trị chốt ở M1, M2-M10 không được đổi âm thầm."""
from enum import Enum


class SourceLang(str, Enum):
    ja = "ja"
    zh = "zh"
    en = "en"


class TargetLang(str, Enum):
    vi = "vi"


class IntendedUse(str, Enum):
    personal = "personal"
    study = "study"
    other = "other"


class ProjectStatus(str, Enum):
    active = "active"
    archived = "archived"


class PageStatus(str, Enum):
    queued = "queued"
    detecting = "detecting"
    detected = "detected"
    detection_failed = "detection_failed"
    ocr_done = "ocr_done"
    inpainted = "inpainted"
    inpaint_needs_review = "inpaint_needs_review"
    translated = "translated"
    typeset_done = "typeset_done"
    ready_for_export = "ready_for_export"


class RegionStatus(str, Enum):
    pending = "pending"
    low_confidence = "low_confidence"
    confirmed = "confirmed"


class OCREngine(str, Enum):
    manga_ocr = "manga_ocr"
    paddle_ocr = "paddle_ocr"


class OCRStatus(str, Enum):
    pending = "pending"
    ok = "ok"
    needs_manual = "needs_manual"


class TranslationEngine(str, Enum):
    google_fast = "google_fast"
    llm_context = "llm_context"


class TranslationStatus(str, Enum):
    pending = "pending"
    ok = "ok"
    fallback_used = "fallback_used"


class FitStatus(str, Enum):
    pending = "pending"
    fit_ok = "fit_ok"
    overflow_warning = "overflow_warning"


class BatchPipeline(str, Enum):
    """M9 chỉ hỗ trợ đúng 2 ý định, không thêm chế độ mơ hồ."""

    full_pipeline = "full_pipeline"
    retry_failed = "retry_failed"


class BatchStatus(str, Enum):
    """Trạng thái gộp của cả mẻ — SUY RA từ các mục con, không bao giờ tự đặt.

    `completed` chỉ khi MỌI mục đã xong. Còn mục nào chưa xong mà báo `completed` là báo láo.
    """

    queued = "queued"
    running = "running"
    completed = "completed"
    partial_failed = "partial_failed"
    blocked_quota = "blocked_quota"
    failed = "failed"
    cancelled = "cancelled"


class BatchItemStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    #: Hết quota nhà cung cấp — KHÁC failed: chờ quota hồi là chạy lại được.
    blocked_quota = "blocked_quota"
    #: Bỏ qua có chủ đích (trang đã xong từ trước, hoặc đang chạy dở nên không đụng vào).
    skipped = "skipped"


class ExportFormat(str, Enum):
    """Định dạng xuất chapter. `cbz` thực chất là ZIP đổi đuôi — ứng dụng đọc truyện hiểu được."""

    png_single = "png_single"
    cbz = "cbz"
    zip = "zip"


class JobType(str, Enum):
    detect = "detect"
    ocr = "ocr"
    inpaint = "inpaint"
    translate = "translate"
    typeset = "typeset"
    export = "export"


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


#: State machine của Page — chỉ khai báo các bước hợp lệ, không "nhảy cóc".
#: M2-M6 mỗi mini-spec dùng đúng nhánh của mình, không tự thêm cạnh mới nếu không ghi trong báo cáo.
PAGE_STATUS_TRANSITIONS: dict[PageStatus, tuple[PageStatus, ...]] = {
    PageStatus.queued: (PageStatus.detecting,),
    PageStatus.detecting: (PageStatus.detected, PageStatus.detection_failed),
    PageStatus.detected: (PageStatus.ocr_done, PageStatus.detecting),
    PageStatus.detection_failed: (PageStatus.detecting,),
    PageStatus.ocr_done: (PageStatus.inpainted, PageStatus.inpaint_needs_review),
    # inpainted -> inpaint_needs_review: chạy lại inpaint ra kết quả tệ hơn (thêm ở M4)
    PageStatus.inpainted: (PageStatus.translated, PageStatus.inpaint_needs_review),
    PageStatus.inpaint_needs_review: (PageStatus.inpainted, PageStatus.translated),
    PageStatus.translated: (PageStatus.typeset_done,),
    PageStatus.typeset_done: (PageStatus.ready_for_export, PageStatus.translated),
    PageStatus.ready_for_export: (PageStatus.typeset_done,),
}


def can_transition(current: PageStatus, target: PageStatus) -> bool:
    """True nếu chuyển trạng thái Page hợp lệ theo state machine đã chốt."""
    return target in PAGE_STATUS_TRANSITIONS.get(current, ())


class InvalidPageTransition(ValueError):
    """Ném ra khi cố chuyển Page sang trạng thái không hợp lệ."""


def assert_transition(current: PageStatus, target: PageStatus) -> None:
    if not can_transition(current, target):
        raise InvalidPageTransition(f"Page không thể chuyển {current.value} -> {target.value}")


# ---------------- E12: cổng chất lượng từng vùng ----------------


class RegionRelevance(str, Enum):
    """Vùng này có khả năng là gì. **Cố ý không có `irrelevant`**: máy không được kết luận một
    vùng là rác rồi tự bỏ — nó chỉ được nói "có thể là", rồi đẩy cho người xem."""

    likely_translatable = "likely_translatable"
    possible_sfx = "possible_sfx"
    possible_number_or_decoration = "possible_number_or_decoration"
    uncertain = "uncertain"


class ReviewStatus(str, Enum):
    """Ai quyết định vùng này. `reviewed_skip` CHỈ do người bấm, không bao giờ do luật."""

    not_required = "not_required"
    needs_review = "needs_review"
    reviewed_keep = "reviewed_keep"
    reviewed_skip = "reviewed_skip"


class OverallBand(str, Enum):
    """Mức chung. `blocked` nghĩa là **không đánh giá được** (thiếu đầu vào), KHÔNG phải "dịch sai"."""

    clear = "clear"
    attention = "attention"
    blocked = "blocked"


class ConfidenceState(str, Enum):
    """Trạng thái điểm tin cậy. `unavailable` khác hẳn `low`: manga-ocr không trả điểm nào cả,
    và hiện "0%" cho trường hợp đó là bịa ra một con số không hề tồn tại."""

    available = "available"
    low = "low"
    unavailable = "unavailable"


class TranslationState(str, Enum):
    present = "present"
    missing = "missing"
    fallback_used = "fallback_used"
    not_attempted = "not_attempted"


# ---------------- E13: thuật ngữ, giọng nhân vật, rà soát nhất quán ----------------


class TermType(str, Enum):
    """Loại thuật ngữ. Cố ý HẸP — enum quá rộng thì không phân loại được gì."""

    character_name = "character_name"
    place = "place"
    organization = "organization"
    item = "item"
    skill = "skill"
    title_rank = "title_rank"
    honorific = "honorific"
    catchphrase = "catchphrase"
    general_term = "general_term"


class GlossaryStatus(str, Enum):
    """CHỈ `approved` mới được đem đi quét. Sửa nội dung đã duyệt phải quay về `draft`."""

    draft = "draft"
    approved = "approved"
    rejected = "rejected"
    archived = "archived"


class SpeechRegister(str, Enum):
    """Giọng nhân vật — là HƯỚNG DẪN biên tập do người đặt, không phải suy luận của máy."""

    neutral = "neutral"
    formal = "formal"
    casual = "casual"
    childlike = "childlike"
    rough = "rough"
    archaic = "archaic"
    comic = "comic"


class VoiceProfileStatus(str, Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class ConsistencyTaskType(str, Enum):
    """Nguồn gốc của việc cần rà soát — luôn nói rõ vì sao nó được tạo ra."""

    #: Nguồn có thuật ngữ đã duyệt nhưng bản dịch không dùng thuật ngữ đó.
    glossary_missing = "glossary_missing"
    #: Bản dịch dùng một biến thể khác với thuật ngữ đã duyệt.
    glossary_variant = "glossary_variant"
    #: Bản dịch dùng đúng biến thể mà người dùng đã ghi là CẤM.
    prohibited_variant = "prohibited_variant"
    voice_consistency_suspect = "voice_consistency_suspect"
    #: Do LLM gợi ý — vẫn phải người duyệt, không bao giờ tự áp.
    llm_suggestion = "llm_suggestion"


class ConsistencyTaskStatus(str, Enum):
    open = "open"
    accepted = "accepted"
    rejected = "rejected"
    #: Bản dịch đã đổi sau khi tạo việc ⇒ đề xuất cũ không còn dùng được.
    stale = "stale"
    resolved_no_change = "resolved_no_change"
