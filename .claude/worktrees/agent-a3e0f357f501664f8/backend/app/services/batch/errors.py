"""Phân loại lỗi và chính sách thử lại (M9).

Nguyên tắc: **chỉ thử lại lỗi tạm thời**. Thiếu font, thiếu model, mất ảnh gốc, sai cấu hình —
thử lại bao nhiêu lần cũng vẫn hỏng, chỉ tốn thời gian và làm người vận hành tưởng hệ thống
đang cố gắng.
"""
from __future__ import annotations

import hashlib
import random
import re
from enum import Enum


class ErrorClass(str, Enum):
    TRANSIENT_RATE_LIMIT = "transient_rate_limit"
    TRANSIENT_PROVIDER = "transient_provider"
    TRANSIENT_NETWORK = "transient_network"
    TRANSIENT_BROKER = "transient_broker"
    PERMANENT_INPUT = "permanent_input"
    PERMANENT_CONFIG = "permanent_config"
    PERMANENT_MODEL = "permanent_model"
    #: Hết quota nhà cung cấp — KHÔNG phải "tạm thời" (thử lại ngay vẫn hỏng) và cũng KHÔNG
    #: phải "vĩnh viễn" (quota hồi là chạy được). Phải là loại riêng.
    QUOTA_EXHAUSTED = "quota_exhausted"
    UNKNOWN = "unknown"


TAM_THOI = {
    ErrorClass.TRANSIENT_RATE_LIMIT,
    ErrorClass.TRANSIENT_PROVIDER,
    ErrorClass.TRANSIENT_NETWORK,
    ErrorClass.TRANSIENT_BROKER,
}

#: Mã lỗi (dạng chuỗi lưu trong DB) của các lỗi tạm thời.
MA_TAM_THOI = frozenset(e.value for e in TAM_THOI)

#: Dấu hiệu trong thân phản hồi cho biết đây là HẾT QUOTA chứ không phải quá nhịp tạm thời.
#: Gemini trả 429 cho CẢ HAI ca — M5 gộp làm một và xoay key, đó là chỗ M9 phải tách ra.
_DAU_HIEU_HET_QUOTA = (
    "quota_exceeded",
    "quota exceeded",
    "resource_exhausted",
    "exceeded your current quota",
    "daily limit",
    "quotafailure",
    "billing",
    "insufficient_quota",
)
#: Ngược lại — đây là quá nhịp trong chốc lát, chờ vài giây là chạy tiếp được.
_DAU_HIEU_QUA_NHIP = ("rate limit", "rate_limit", "too many requests", "try again", "retry after")


class TransientErrorClassifier:
    """Xếp một lỗi vào đúng loại. Không đoán mò: không nhận ra thì trả `UNKNOWN` và KHÔNG thử lại."""

    def classify(self, exc: BaseException | None = None, *, mo_ta: str | None = None) -> ErrorClass:
        text = (mo_ta if mo_ta is not None else f"{type(exc).__name__}: {exc}").lower()

        ma = self._ma_http(text)
        if ma == 429:
            # Cùng một mã 429 nhưng hai nghĩa hoàn toàn khác nhau — phải đọc thân phản hồi.
            if any(d in text for d in _DAU_HIEU_HET_QUOTA):
                return ErrorClass.QUOTA_EXHAUSTED
            if any(d in text for d in _DAU_HIEU_QUA_NHIP):
                return ErrorClass.TRANSIENT_RATE_LIMIT
            # Không có dấu hiệu nào: coi là quá nhịp tạm thời. Thử lại vài lần rồi cũng dừng,
            # rẻ hơn là chặn nhầm cả mẻ vì tưởng hết quota.
            return ErrorClass.TRANSIENT_RATE_LIMIT
        if ma == 408 or "timeout" in text or "timed out" in text:
            return ErrorClass.TRANSIENT_NETWORK
        if ma is not None and 500 <= ma <= 599:
            return ErrorClass.TRANSIENT_PROVIDER
        if ma in (400, 401, 403, 404, 422):
            return ErrorClass.PERMANENT_CONFIG if ma in (401, 403) else ErrorClass.PERMANENT_INPUT

        if any(k in text for k in ("connection refused", "connection reset", "dns", "socket",
                                   "temporarily unavailable", "connectionerror")):
            return ErrorClass.TRANSIENT_NETWORK
        if any(k in text for k in ("brokerconnection", "redis", "amqp", "kombu")):
            return ErrorClass.TRANSIENT_BROKER
        if any(k in text for k in ("font_not_found", "font_missing_glyph", "weights",
                                   "inpaintweightsmissing", "no such file", "filenotfound")):
            return ErrorClass.PERMANENT_MODEL
        if any(k in text for k in ("unsupported", "invalidmask", "no_region", "missing_ocr",
                                   "missing_translation", "precondition_failed", "no_page_ready",
                                   "validation", "unsupportedimage")):
            return ErrorClass.PERMANENT_INPUT
        if "llm_not_configured" in text or "chưa cấu hình" in text:
            return ErrorClass.PERMANENT_CONFIG
        return ErrorClass.UNKNOWN

    @staticmethod
    def _ma_http(text: str) -> int | None:
        m = re.search(r"http\s*(\d{3})", text) or re.search(r"\b(4\d\d|5\d\d)\b", text)
        return int(m.group(1)) if m else None


class RetryPolicy:
    """Lùi dần theo cấp số nhân, có nhiễu ngẫu nhiên, có TRẦN — không bao giờ thử lại vô hạn."""

    def __init__(
        self,
        max_retries: int = 3,
        backoff_base_seconds: float = 2.0,
        backoff_max_seconds: float = 120.0,
        jitter: bool = True,
    ) -> None:
        self.max_retries = max_retries
        self.backoff_base_seconds = backoff_base_seconds
        self.backoff_max_seconds = backoff_max_seconds
        self.jitter = jitter

    def should_retry(self, error_class: ErrorClass, retry_count: int) -> bool:
        """Chỉ lỗi tạm thời mới thử lại, và chỉ trong giới hạn số lần.

        Hết quota KHÔNG thử lại: quota chưa hồi thì thử bao nhiêu lần cũng hỏng, mà mỗi lần thử
        lại đều là một lời gọi tính tiền. Người vận hành sẽ tự chạy lại khi quota về.
        """
        return error_class in TAM_THOI and retry_count < self.max_retries

    def next_delay_seconds(self, retry_count: int, khoa_nhieu: str | None = None) -> float:
        """Thời gian chờ trước lần thử kế tiếp.

        `khoa_nhieu` cho phép nhiễu **tất định theo khoá** — nhờ vậy test khẳng định được nhiễu
        có thật mà vẫn lặp lại y hệt, thay vì phải chấp nhận số ngẫu nhiên không kiểm được.
        """
        cho = min(self.backoff_base_seconds * (2 ** max(retry_count, 0)), self.backoff_max_seconds)
        if not self.jitter:
            return cho
        if khoa_nhieu is None:
            ty_le = random.random()  # noqa: S311 - chỉ để giãn thời điểm gọi lại, không phải mật mã
        else:
            h = hashlib.sha256(f"{khoa_nhieu}:{retry_count}".encode()).digest()
            ty_le = int.from_bytes(h[:4], "big") / 0xFFFFFFFF
        # Nhiễu MỘT NỬA: nửa mốc là thời gian chờ chắc chắn, nửa còn lại mới ngẫu nhiên.
        # Từng dùng nhiễu toàn phần (0..cho) và đo được thật ở Run B: lần thử lại chỉ chờ **0,2s**
        # sau khi nhà cung cấp vừa báo lỗi — chờ như không chờ. Nhiễu vẫn cần để nhiều trang không
        # gọi lại đúng cùng một thời điểm, nhưng không được phép rơi về gần 0.
        return cho / 2 + (cho / 2) * ty_le
