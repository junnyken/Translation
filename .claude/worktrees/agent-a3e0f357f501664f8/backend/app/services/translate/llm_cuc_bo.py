"""E72 — dịch bằng LLM CHẠY TRÊN MÁY (Ollama / LM Studio / llama.cpp server) qua API kiểu OpenAI.

## Vì sao một lớp cho cả ba

Cả ba đều phục vụ `POST {base}/chat/completions` theo đúng hợp đồng OpenAI, và cả ba nhận
`response_format: {type: "json_schema"}` để ÉP đầu ra (llama.cpp và LM Studio dịch schema thành
ngữ pháp sinh; Ollama ≥0.5 cũng vậy). Koharu làm tương tự: provider `openai-compatible` /
`lm-studio` cạnh bản llama.cpp nhúng (`koharu-translator/src/provider.rs`).

## Dùng lại, không viết lại

Kế thừa `LLMContextTranslator` để dùng NGUYÊN prompt E71 (`build_prompt_json`) — cùng luật nội dung
E66/E68, cùng bối cảnh thuật ngữ E31 — và cùng `parse_response_json`. Chỉ thay đúng một chỗ: cách
gửi đi (`_call_api`). Hai đường dịch không thể lệch luật với nhau vì chúng là CÙNG một prompt.

Lỗi nào cũng thành `TranslationFailed` ⇒ đường lùi `google_fast` sẵn có bắt được (máy chủ cục bộ
chưa bật là chuyện thường ngày, không được làm hỏng cả trang).
"""
from __future__ import annotations

import base64
import json
import logging
import urllib.error
import urllib.request

from app.models.enums import TranslationEngine
from app.services.translate.engines import LLMContextTranslator, TranslationFailed

logger = logging.getLogger(__name__)

#: `SCHEMA_DICH` của E71 viết theo kiểu Gemini (`OBJECT`, `STRING`…). API kiểu OpenAI đòi JSON
#: Schema chuẩn (chữ thường) và `additionalProperties: false` khi `strict`.
SCHEMA_DICH_JSON = {
    "type": "object",
    "properties": {
        "translations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "text": {"type": "string"},
                    "doan": {"type": "boolean"},
                },
                "required": ["id", "text", "doan"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["translations"],
    "additionalProperties": False,
}


class OpenAICompatTranslator(LLMContextTranslator):
    """LLM cục bộ. Luôn ở chế độ JSON theo `id` (E71) — model nhỏ hỏng giao thức dòng đánh số nhiều."""

    engine_enum = TranslationEngine.local_llm

    def __init__(
        self,
        base_url: str,
        model_name: str,
        api_key: str = "",
        timeout: int = 300,
        temperature: float = 0.2,
        max_output_tokens: int = 4096,
        vision: bool = False,
        boi_canh: str = "",
        anh_trang: bytes | None = None,
        anh_mime: str = "image/jpeg",
    ) -> None:
        super().__init__(
            api_keys=[api_key or "khong-can"],
            model_name=model_name,
            timeout=timeout,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            thinking_budget=None,
            boi_canh=boi_canh,
            # Model không đọc ảnh mà vẫn được gửi ảnh thì llama.cpp trả 400 cả trang. Chỉ gửi khi
            # người cài đã khai model có thị giác.
            anh_trang=anh_trang if vision else None,
            anh_mime=anh_mime,
            json_mode=True,
        )
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _call_api(self, prompt: str, schema: dict | None = None) -> tuple[str, dict]:
        if not self.model_name:
            raise TranslationFailed("local_llm_chua_cau_hinh: chưa đặt LOCAL_LLM_MODEL")
        noi_dung: list[dict] = []
        if self.anh_trang:
            noi_dung.append({"type": "image_url", "image_url": {
                "url": f"data:{self.anh_mime};base64,"
                       + base64.b64encode(self.anh_trang).decode("ascii"),
            }})
        noi_dung.append({"type": "text", "text": prompt})
        than: dict = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": noi_dung}],
            "temperature": self.temperature,
            "max_tokens": self.max_output_tokens,
            "stream": False,
        }
        if schema is not None:
            than["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "ban_dich", "strict": True, "schema": SCHEMA_DICH_JSON},
            }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(than).encode("utf-8"), headers=headers, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            chi_tiet = exc.read().decode("utf-8", "replace")[:300]
            self.usage.errors.append(f"HTTP {exc.code}")
            raise TranslationFailed(f"local_llm HTTP {exc.code}: {chi_tiet}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            self.usage.errors.append(type(exc).__name__)
            raise TranslationFailed(
                f"local_llm_khong_ket_noi: không gọi được máy chủ LLM tại {self.base_url} "
                f"({exc}). Bật Ollama/LM Studio/llama.cpp server hoặc sửa LOCAL_LLM_BASE_URL."
            ) from exc
        except ValueError as exc:
            raise TranslationFailed(f"local_llm trả về không phải JSON: {exc}") from exc

        try:
            van_ban = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise TranslationFailed(f"local_llm trả về sai dạng: {str(data)[:200]}") from exc
        dung = data.get("usage") or {}
        # Đổi tên khoá về kiểu Gemini để `translate()` của lớp cha đọc được, không phải sửa nó.
        return van_ban, {
            "promptTokenCount": dung.get("prompt_tokens"),
            "candidatesTokenCount": dung.get("completion_tokens"),
            "totalTokenCount": dung.get("total_tokens"),
        }
