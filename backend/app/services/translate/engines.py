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


#: E66 — dấu mô hình đặt ở đầu một dòng để nói "dòng này tôi phải ĐOÁN".
#:
#: Chọn `[?]` vì nó không bao giờ là chữ thật trong một câu thoại tiếng Việt, và nó không đụng
#: giao thức đánh số `1. …` của prompt.
DAU_KHONG_CHAC = "[?]"

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
        boi_canh: str = "",
        anh_trang: bytes | None = None,
        anh_mime: str = "image/jpeg",
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
        #: E31 — thuật ngữ + giọng nhân vật ĐÃ CHỐT của project (`translate/boi_canh.py`).
        #: Rỗng thì prompt không đổi một ký tự nào so với trước E31.
        self.boi_canh = (boi_canh or "").strip()
        #: E32 — ảnh trang gửi kèm. `None` ⇒ thân request giống HỆT trước E32.
        self.anh_trang = anh_trang or None
        self.anh_mime = anh_mime
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
        # E30 — DÀN PHẲNG dấu xuống dòng trước khi đánh số.
        #
        # Prompt này dùng giao thức "một dòng một mục" (`1. …`, `2. …`). Một mục có `\n` bên trong
        # sẽ trải ra nhiều dòng, và `parse_response` chỉ nhận chữ nằm trên dòng CÓ SỐ ⇒ phần còn
        # lại bị bỏ im lặng.
        #
        # Đo thật (2026-09-12, trang `29ab3d86`):
        #
        #     vào  "Whoo!\nI think it'll be a teeny tiny bit more complicated than I thought!"
        #     ra   "Whoo!"                                      <- MẤT CẢ CÂU
        #     vào  "Pfff!\n.. and I thought it'd be easier with an Air Dragon!"
        #     ra   "Phụt!"                                      <- MẤT CẢ CÂU
        #
        # `google_fast` dịch đủ cả hai phần, nên đây là chỗ `llm_context` TỆ HƠN hẳn — và tệ theo
        # kiểu im lặng, ảnh vẫn ra, chỉ thiếu chữ.
        #
        # Vì sao dàn phẳng là đúng chứ không phải đổi giao thức: E26-A đã gộp hết dấu xuống dòng
        # do bong bóng ngắt, nên `\n` còn lại là **ranh giới câu thật**. Nối bằng dấu cách thì mô
        # hình vẫn thấy đủ hai câu và tự chấm câu lại — đúng việc prompt đã yêu cầu nó làm. Còn
        # `google_fast` thì vẫn cần giữ `\n` (nó dịch từng câu theo dòng), nên chỉ dàn phẳng ở
        # ĐÂY, không sửa dữ liệu vào.
        numbered = "\n".join(
            f"{i + 1}. {' '.join((t or '').splitlines()).strip()}" for i, t in enumerate(texts)
        )
        return (
            "Bạn là người dịch truyện tranh chuyên nghiệp. Dịch các dòng thoại dưới đây "
            f"từ {source_lang} sang {target_lang}.\n"
            "Yêu cầu bắt buộc:\n"
            f"- Trả về ĐÚNG {len(texts)} dòng, đánh số 1..{len(texts)} như đầu vào.\n"
            "- Dịch theo mạch văn của cả trang, không dịch rời rạc từng dòng.\n"
            "- Bám sát nghĩa gốc: không bỏ sót ý, không suy diễn thêm nội dung không có trong câu "
            "gốc. Chỉ được đổi CÁCH DIỄN ĐẠT cho tự nhiên bằng tiếng Việt, không đổi Ý.\n"
            "- Giữ giọng điệu nhân vật; câu thoại ngắn gọn tự nhiên như truyện tranh tiếng Việt.\n"
            # E66 — dòng cũ ở đây là: "Đầu vào là chữ do OCR đọc nên có thể sai chính tả; tự
            # suy luận và sửa khi dịch."
            #
            # Nó CHO PHÉP mô hình chế, và đo được là nó chế thật: `あの暁山です` (chữ đọc sai)
            # thành "Đó là núi Akatsuki" — một câu đúng ngữ pháp, trôi chảy, và hoàn toàn không
            # có trong truyện. Mô hình làm đúng lệnh; lệnh mới là chỗ sai.
            #
            # Không gỡ hẳn quyền sửa: lỗi đọc NHỎ (lệch một kana, mất dấu câu) thì sửa được là
            # tốt. Chỗ phải chặn là bước nhảy từ "sửa một ký tự" sang "đoán ra một từ khác hẳn".
            # KHÔNG nhắc tới ẢNH ở khối luôn-bật này: E32 chốt rằng nói về ảnh khi không gửi
            # ảnh là mời mô hình bịa ra thứ nó không thấy, và có bài canh riêng cho điều đó
            # (`test_khong_anh_thi_prompt_KHONG_noi_ve_anh`). Mệnh đề về ảnh nằm ở khối dưới.
            "- Chữ đầu vào do máy ĐỌC TỰ ĐỘNG (OCR) nên có thể sai. Được sửa lỗi đọc NHỎ khi ngữ "
            "cảnh làm nghĩa rõ ràng (lệch một ký tự, thiếu dấu câu). KHÔNG được đoán ra một TỪ "
            "KHÁC HẲN chỉ để câu có nghĩa.\n"
            f"- Dòng nào bạn phải ĐOÁN mới dịch được — chữ gốc vô nghĩa, hoặc có nhiều cách hiểu "
            f"khác hẳn nhau — thì vẫn dịch bản khả dĩ nhất, NHƯNG đặt {DAU_KHONG_CHAC} ở ĐẦU "
            f"dòng đó. Dấu này là tín hiệu cho người biên tập: thà báo ra còn hơn để người đọc "
            f"tưởng một câu bịa là nội dung thật.\n"
            f"- TÊN RIÊNG (người, địa danh): phiên âm theo cách đọc và GIỮ NGUYÊN LÀ TÊN. Không "
            f"được thay một cái tên bằng một từ thường. Tên đọc không rõ thì giữ dạng phiên âm "
            f"gần nhất và đánh {DAU_KHONG_CHAC} — đừng biến nó thành một danh từ chung.\n"
            # E66 — câu này từng MÂU THUẪN với luật dấu `[?]` ở trên, và mâu thuẫn theo hướng
            # nguy hiểm: nó bịt miệng mô hình đúng lúc nó muốn báo là đang đoán, nên nó đành nhét
            # phần đoán vào một câu trôi chảy. (Chỗ này do một lượt phản biện của Gemini 3.1 Pro
            # chỉ ra — tôi thêm dấu `[?]` mà quên gỡ cái khoá miệng.)
            f"- Không thêm giải thích, không thêm dòng nào ngoài danh sách đã đánh số. Thứ DUY "
            f"NHẤT được thêm vào một dòng là đúng ba ký tự {DAU_KHONG_CHAC} ở đầu dòng — không "
            f"chú thích trong ngoặc, không chép lại chữ gốc, không dấu sao.\n"
            # E68 — đo thật 28-09: bảo `[?]` là "ngoại lệ của luật cấm giải thích" thì mô hình
            # hiểu thành ĐƯỢC PHÉP giải thích, và trả về `"* (Chữ trên ảnh là ごくごく - Ực ực)"`.
            # Câu đó mang ký tự Nhật ⇒ `MissingGlyph` ⇒ **bong bóng để trống** (lỗi F1). Nên phải
            # cấm thẳng ký tự ngoài tiếng Việt, không chỉ cấm "giải thích".
            "- Bản dịch chỉ được chứa chữ VIỆT, số và dấu câu. Tuyệt đối không để lại ký tự Nhật/"
            "Trung/Hàn trong bản dịch — font không vẽ được chúng và bong bóng sẽ bị bỏ trống.\n"
            # E68 — đo thật: `どうして` ("tại sao?") là tiếng Nhật sạch mà vẫn bị đánh dấu. Cảnh
            # báo gắn tràn lan thì người dùng tắt mắt với nó, đúng bài học đã ghi ở dự án SEO.
            f"- CHỈ đánh {DAU_KHONG_CHAC} khi chữ gốc thật sự không đọc ra nghĩa. Câu ngắn nhưng "
            f"rõ nghĩa (ví dụ một câu hỏi thông thường) thì KHÔNG đánh dấu.\n"
            # E32 — chỉ thêm dòng này KHI có ảnh. Không có ảnh mà vẫn bảo mô hình "xem trang" là
            # mời nó bịa ra thứ nó không thấy.
            + (
                "- Kèm theo là ẢNH của chính trang truyện. Dùng ảnh để: (a) ĐỐI CHIẾU chữ đọc "
                "được với chữ trên ảnh, (b) biết câu nào là của nhân vật nào, (c) nhận ra tiếng "
                "động vẽ cách điệu. Ảnh là để HIỂU ĐÚNG, không phải để thêm nội dung không có "
                f"trong danh sách. Ảnh mâu thuẫn với chữ đầu vào thì tin ẢNH và đánh "
                f"{DAU_KHONG_CHAC}.\n"
                if self.anh_trang else ""
            )
            + "\n"
            # E31 — bối cảnh đặt TRƯỚC danh sách chữ, sau phần yêu cầu. Đặt sau danh sách thì mô
            # hình đã đọc xong chữ mới thấy thuật ngữ, và nó không quay lại sửa.
            + (f"\n{self.boi_canh}\n" if self.boi_canh else "")
            + f"\n### {self.page_label}\n{numbered}"
        )

    @staticmethod
    def tach_dau_khong_chac(dong: list[str]) -> tuple[list[str], set[int]]:
        """Bóc dấu `[?]` khỏi từng dòng, trả (chữ sạch, tập chỉ số dòng bị đánh dấu).

        E66 — vì sao cần một dấu như thế này.

        Đo trên trang thật (368×543, 28-09): chạy CÙNG một trang hai lần cho ra chữ gốc KHÁC nhau,
        và bản dịch của cả hai đều trôi chảy, không có dấu hiệu gì cho người đọc biết chữ gốc đã
        sai:

            あの妹山です  -> "Đó là Seyama."
            あの暁山です  -> "Đó là núi Akatsuki."

        Bản dịch **không sai**: nó dịch đúng thứ nó nhận được. Cái sai là hệ thống **không có
        cách nào nói "tôi đang đoán"**. Mô hình được bảo "tự suy luận và sửa" nên nó sửa — im
        lặng, và ra một câu đọc rất xuôi.

        Dấu bóc ở đây **không** vứt bản dịch đi: vẫn giữ bản khả dĩ nhất để người đọc có cái mà
        đọc. Nó chỉ bật cờ để vùng đó hiện lên ở màn rà soát.
        """
        sach: list[str] = []
        danh_dau: set[int] = set()
        for i, d in enumerate(dong):
            t = (d or "").strip()
            # Dấu có thể đứng đầu (đúng chỉ dẫn) hoặc lọt vào giữa (mô hình gõ lệch). Bắt cả hai
            # rồi bỏ sạch: để sót một `[?]` trong chữ là nó bị nướng vào bong bóng trên ảnh.
            if DAU_KHONG_CHAC in t:
                danh_dau.add(i)
                t = t.replace(DAU_KHONG_CHAC, " ")
            sach.append(" ".join(t.split()))
        return sach, danh_dau

    @staticmethod
    def parse_response(text: str, expected: int) -> list[str]:
        """Tách các dòng đã đánh số về đúng `expected` phần tử.

        Thiếu dòng -> điền chuỗi rỗng (để caller đánh dấu cần xem lại), thừa -> cắt bớt.
        KHÔNG bịa nội dung cho dòng thiếu.

        E30 — CỐ Ý giữ nguyên việc bỏ dòng không có số, và đây là lý do.

        Lỗi mất chữ đo được ở trang `29ab3d86` (`"Whoo!\\nI think…"` → chỉ còn `"Whoo!"`) có nguyên
        nhân ở **`build_prompt`**, không ở đây: mục có `\\n` trải ra nhiều dòng nên prompt vỡ giao
        thức "một dòng một mục". Vá ở `build_prompt` là vá đúng nguyên nhân.

        Tôi đã thử sửa thêm chỗ này cho "nối dòng tiếp theo vào mục trước" — và nó **phá**
        `test_bo_qua_heading_va_dong_thua`: mô hình thêm một dòng tán gẫu ở cuối thì dòng đó lọt
        vào bong bóng cuối cùng. Hai yêu cầu kéo ngược chiều nhau, và không phân biệt được bằng
        vị trí dòng.

        Chọn giữ hành vi cũ vì nguyên nhân thật đã được vá ở chỗ khác — thêm hành vi phỏng đoán ở
        đây là đổi một lỗi đã hết lấy một lỗi mới.
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
        # E32 — ẢNH đứng TRƯỚC chữ trong `parts`.
        #
        # Thứ tự này là khuyến nghị của Gemini cho câu hỏi về một ảnh: mô hình đọc ảnh rồi mới đọc
        # yêu cầu, nên nó neo câu trả lời vào ảnh. Đảo lại thì ảnh dễ thành phần phụ bị bỏ qua.
        #
        # `anh_trang is None` ⇒ `parts` chỉ có phần chữ, tức thân request giống HỆT trước E32.
        parts: list[dict] = []
        if self.anh_trang:
            import base64

            parts.append({
                "inlineData": {
                    "mimeType": self.anh_mime,
                    "data": base64.b64encode(self.anh_trang).decode("ascii"),
                }
            })
        parts.append({"text": prompt})
        body = json.dumps(
            {
                "contents": [{"parts": parts}],
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

    def goi_prompt_tho(self, prompt: str) -> tuple[str, dict]:
        """Gửi một prompt tuỳ ý, trả (văn bản, usageMetadata).

        Mở ra cho E17 tầng 3 dùng lại phần hạ tầng đã kiểm của lớp này — xoay key khi hết nhịp,
        tắt "thinking", đọc usage — mà không phải chép lại. Đây là **đường duy nhất** ngoài
        `translate()` được phép gọi mô hình, để mọi lượt gọi đều đi qua cùng một chỗ đếm token.
        """
        return self._call_api(prompt)

    #: Chỉ số dòng mà mô hình tự báo là đang ĐOÁN (E66). Rỗng cho tới khi `translate` chạy.
    vung_khong_chac: set[int] = set()

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
        dong = self.parse_response(text, len(texts))
        # E66 — bóc dấu `[?]` và GHI LẠI vùng nào bị đánh, để bên gọi bật cờ "cần xem lại".
        # Đặt trên `self` thay vì đổi kiểu trả về: `google_fast` dùng chung giao diện `translate`
        # và không có khái niệm này. Bên gọi đọc bằng `getattr(..., set())`.
        dong, self.vung_khong_chac = self.tach_dau_khong_chac(dong)
        if self.vung_khong_chac:
            logger.info(
                "E66: %d/%d dòng mô hình tự báo là ĐOÁN", len(self.vung_khong_chac), len(dong),
            )
        return dong


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
