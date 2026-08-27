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
