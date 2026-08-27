"""Hai đường dịch độc lập (M5).

- `google_fast`  : dịch từng dòng qua endpoint Google Translate công khai — miễn phí, nhanh,
                   KHÔNG có ngữ cảnh liên câu.
- `llm_context`  : gộp cả trang thành 1 request Gemini để giữ mạch văn, có xoay API key.

Hai path CỐ Ý tách rời, không gộp thành 1 hàm chung: người dùng phải kiểm soát được
khi nào tốn token, khi nào miễn phí.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from app.models.enums import TranslationEngine

logger = logging.getLogger(__name__)

_GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
#: Endpoint dịch công khai. `clients5` chạy được từ hạ tầng này, `translate.googleapis.com`
#: trả 429 (xem docs/TEST_LOG.md § M5) nên để làm phương án 2.
_GOOGLE_ENDPOINTS = (
    ("clients5", "https://clients5.google.com/translate_a/t"),
    ("gtx", "https://translate.googleapis.com/translate_a/single"),
)


class UnsupportedTranslationEngine(ValueError):
    """engine không thuộc 2 giá trị đã chốt — không fallback âm thầm."""


class TranslationFailed(RuntimeError):
    pass


class QuotaExhausted(TranslationFailed):
    """Mọi API key đều hết quota — phải báo rõ, không trả bản dịch rỗng."""


@dataclass
class UsageStats:
    """Số liệu thật của lần gọi gần nhất — dùng ghi `token_cost` và canh bẫy 'thinking'."""

    prompt_tokens: int | None = None
    output_tokens: int | None = None
    thought_tokens: int | None = None
    total_tokens: int | None = None
    model_name: str | None = None
    key_rotations: int = 0
    errors: list[str] = field(default_factory=list)


def _http_json(request: urllib.request.Request, timeout: int) -> dict:
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


class GoogleTranslateEngine:
    """Implement Protocol `ITranslator` (M1). Dịch TỪNG DÒNG, không có ngữ cảnh liên câu."""

    engine_enum = TranslationEngine.google_fast
    model_name = "google-translate-public"

    def __init__(self, timeout: int = 20, user_agent: str = "Mozilla/5.0") -> None:
        self.timeout = timeout
        self.user_agent = user_agent
        self.usage = UsageStats(model_name=self.model_name)

    def _translate_one(self, text: str, source_lang: str, target_lang: str) -> str:
        if not text.strip():
            return ""
        last_error: Exception | None = None
        for name, base in _GOOGLE_ENDPOINTS:
            try:
                if name == "clients5":
                    query = urllib.parse.urlencode(
                        {"client": "dict-chrome-ex", "sl": source_lang, "tl": target_lang, "q": text}
                    )
                    data = _http_json(
                        urllib.request.Request(f"{base}?{query}", headers={"User-Agent": self.user_agent}),
                        self.timeout,
                    )
                    if isinstance(data, list) and data:
                        first = data[0]
                        return first if isinstance(first, str) else str(first)
                    raise TranslationFailed(f"Định dạng trả về lạ từ {name}: {str(data)[:100]}")

                query = urllib.parse.urlencode(
                    {"client": "gtx", "sl": source_lang, "tl": target_lang, "dt": "t", "q": text}
                )
                data = _http_json(
                    urllib.request.Request(f"{base}?{query}", headers={"User-Agent": self.user_agent}),
                    self.timeout,
                )
                return "".join(seg[0] for seg in data[0] if seg and seg[0])
            except Exception as exc:  # noqa: BLE001 - thử endpoint kế tiếp
                last_error = exc
                logger.warning("Endpoint %s lỗi: %s", name, exc)
        raise TranslationFailed(f"Cả {len(_GOOGLE_ENDPOINTS)} endpoint dịch đều lỗi: {last_error}")

    def translate(self, texts: list[str], source_lang: str, target_lang: str) -> list[str]:
        """Trả list bản dịch ĐÚNG thứ tự và ĐÚNG số lượng input."""
        out: list[str] = []
        for text in texts:
            out.append(self._translate_one(text, source_lang, target_lang))
        return out


class LLMContextTranslator:
    """Gộp cả trang thành 1 request để giữ mạch văn, xoay API key khi hết quota.

    Prompt giữ đúng khung đã chốt: heading `### page.jpg` + các dòng đánh số 1..N,
    và yêu cầu trả về ĐÚNG số dòng — để ghép 1:1 ngược lại từng vùng.
    """

    engine_enum = TranslationEngine.llm_context

    #: Mã lỗi coi là "hết quota / quá nhịp" -> xoay sang key kế tiếp.
    QUOTA_STATUS = (429,)

    def __init__(
        self,
        api_keys: list[str],
        model_name: str = "gemini-3.1-flash-lite",
        timeout: int = 120,
        temperature: float = 0.3,
        max_output_tokens: int = 8192,
        thinking_budget: int | None = 0,
        page_label: str = "page.jpg",
    ) -> None:
        self._api_keys = [k.strip() for k in api_keys if k and k.strip()]
        self.model_name = model_name
        self.timeout = timeout
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        #: 0 = TẮT hẳn "thinking". Không tắt thì model đốt hàng trăm token suy nghĩ cho mỗi
        #: trang mà chất lượng dịch không hơn (đo thật: 938 vs 0 thought-token, xem TEST_LOG § M5).
        self.thinking_budget = thinking_budget
        self.page_label = page_label
        self._index = 0
        self._lock = threading.Lock()
        self.usage = UsageStats(model_name=model_name)

    # ---------- key rotation ----------
    @property
    def key_count(self) -> int:
        return len(self._api_keys)

    def _current_key(self) -> str:
        if not self._api_keys:
            raise QuotaExhausted("Chưa cấu hình API key nào (GEMINI_API_KEYS rỗng)")
        return self._api_keys[self._index % len(self._api_keys)]

    def _rotate_key(self) -> None:
        with self._lock:
            self._index = (self._index + 1) % max(len(self._api_keys), 1)
            self.usage.key_rotations += 1

    # ---------- prompt ----------
    def build_prompt(self, texts: list[str], source_lang: str, target_lang: str) -> str:
        numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(texts))
        return (
            "Bạn là người dịch truyện tranh chuyên nghiệp. Dịch các dòng thoại dưới đây "
            f"từ {source_lang} sang {target_lang}.\n"
            "Yêu cầu bắt buộc:\n"
            f"- Trả về ĐÚNG {len(texts)} dòng, đánh số 1..{len(texts)} như đầu vào.\n"
            "- Dịch theo mạch văn của cả trang, không dịch rời rạc từng dòng.\n"
            "- Giữ giọng điệu nhân vật; câu thoại ngắn gọn tự nhiên như truyện tranh tiếng Việt.\n"
            "- Đầu vào là chữ do OCR đọc nên có thể sai chính tả; tự suy luận và sửa khi dịch.\n"
            "- Không thêm giải thích, không thêm dòng nào ngoài danh sách đã đánh số.\n\n"
            f"### {self.page_label}\n{numbered}"
        )

    @staticmethod
    def parse_response(text: str, expected: int) -> list[str]:
        """Tách các dòng đã đánh số về đúng `expected` phần tử.

        Thiếu dòng -> điền chuỗi rỗng (để caller đánh dấu cần xem lại), thừa -> cắt bớt.
        KHÔNG bịa nội dung cho dòng thiếu.
        """
        result: dict[int, str] = {}
        for raw_line in (text or "").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("###"):
                continue
            match = re.match(r"^(\d{1,3})\s*[.)\]-]\s*(.*)$", line)
            if match:
                idx = int(match.group(1))
                if 1 <= idx <= expected:
                    result[idx] = match.group(2).strip()
        return [result.get(i + 1, "") for i in range(expected)]

    # ---------- gọi API ----------
    def _generation_config(self) -> dict:
        cfg: dict = {
            "temperature": self.temperature,
            "maxOutputTokens": self.max_output_tokens,
        }
        if self.thinking_budget is not None:
            cfg["thinkingConfig"] = {"thinkingBudget": self.thinking_budget}
        return cfg

    def _call_api(self, prompt: str) -> tuple[str, dict]:
        body = json.dumps(
            {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": self._generation_config(),
            }
        ).encode("utf-8")

        attempts = max(self.key_count, 1)
        last_error: Exception | None = None
        for _ in range(attempts):
            key = self._current_key()
            request = urllib.request.Request(
                _GEMINI_ENDPOINT.format(model=self.model_name),
                data=body,
                method="POST",
                headers={"x-goog-api-key": key, "Content-Type": "application/json"},
            )
            try:
                data = _http_json(request, self.timeout)
                candidate = (data.get("candidates") or [{}])[0]
                parts = (candidate.get("content") or {}).get("parts") or []
                return "".join(p.get("text", "") for p in parts), data.get("usageMetadata", {})
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:300] if hasattr(exc, "read") else ""
                last_error = TranslationFailed(f"HTTP {exc.code}: {detail}")
                self.usage.errors.append(f"HTTP {exc.code}")
                if exc.code in self.QUOTA_STATUS:
                    logger.warning("Key hiện tại hết nhịp/quota (HTTP %s) -> xoay key", exc.code)
                    self._rotate_key()
                    continue
                raise last_error from exc
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                self.usage.errors.append(type(exc).__name__)
                raise
        raise QuotaExhausted(f"Đã thử hết {attempts} key, tất cả đều hết quota. Lỗi cuối: {last_error}")

    def translate(self, texts: list[str], source_lang: str, target_lang: str) -> list[str]:
        if not texts:
            return []
        prompt = self.build_prompt(texts, source_lang, target_lang)
        text, usage = self._call_api(prompt)

        self.usage.prompt_tokens = usage.get("promptTokenCount")
        self.usage.output_tokens = usage.get("candidatesTokenCount")
        self.usage.thought_tokens = usage.get("thoughtsTokenCount")
        self.usage.total_tokens = usage.get("totalTokenCount")
        if self.thinking_budget == 0 and (self.usage.thought_tokens or 0) > 0:
            # Cảnh báo sớm: model phớt lờ yêu cầu tắt thinking -> hoá đơn phình mà không ai biết.
            logger.warning(
                "Model %s vẫn đốt %s token 'thinking' dù đã yêu cầu thinkingBudget=0",
                self.model_name, self.usage.thought_tokens,
            )
        return self.parse_response(text, len(texts))


def get_translator(engine: str, api_keys: list[str] | None = None, **kwargs):
    """Factory theo tên engine. Giá trị lạ → raise rõ ràng, không fallback âm thầm."""
    value = engine.value if isinstance(engine, TranslationEngine) else str(engine)
    if value == TranslationEngine.google_fast.value:
        return GoogleTranslateEngine(**{k: v for k, v in kwargs.items() if k in ("timeout", "user_agent")})
    if value == TranslationEngine.llm_context.value:
        return LLMContextTranslator(api_keys=api_keys or [], **kwargs)
    raise UnsupportedTranslationEngine(
        f"engine '{value}' không được hỗ trợ (chỉ google_fast / llm_context)"
    )
