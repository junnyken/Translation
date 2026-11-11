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
_DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"

#: E71 — schema ép đầu ra của chế độ JSON (`LLMContextTranslator(json_mode=True)`).
#:
#: Vì sao ÉP schema chứ không xin JSON bằng lời: E46 đo trên chính dự án này — xin bằng lời thì
#: model dừng giữa mảng mà vẫn báo `STOP` và đổi tên khoá giữa chừng (24/30 lần đúng); ép schema
#: 45/45. Giao thức theo `id` lấy từ Koharu (`koharu-translator/src/prompt.rs`, MIT OR Apache-2.0):
#: ghép bản dịch về vùng bằng `id`, không bằng vị trí dòng.
#:
#: `doan` thay cho dấu `[?]` gõ trong chữ (E66): cờ nằm ở trường riêng thì không thể lọt vào
#: bong bóng, và không cần luật "thứ duy nhất được thêm vào dòng là ba ký tự…".
SCHEMA_DICH = {
    "type": "OBJECT",
    "properties": {
        "translations": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "id": {"type": "INTEGER"},
                    "text": {"type": "STRING"},
                    "doan": {"type": "BOOLEAN"},
                },
                "required": ["id", "text", "doan"],
            },
        },
    },
    "required": ["translations"],
}
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


_http_json_mac_dinh = _http_json


class GoogleTranslateEngine:
    """Implement Protocol `ITranslator` (M1). Dịch TỪNG DÒNG, không có ngữ cảnh liên câu."""

    engine_enum = TranslationEngine.google_fast
    model_name = "google-translate-public"

    def __init__(
        self,
        timeout: int = 20,
        user_agent: str = "Mozilla/5.0",
        max_workers: int = 6,
    ) -> None:
        self.timeout = timeout
        self.user_agent = user_agent
        self.max_workers = max(1, int(max_workers))
        self.usage = UsageStats(model_name=self.model_name)

    def _translate_one(self, text: str, source_lang: str, target_lang: str) -> str:
        if not text.strip():
            return ""
        tl_map = {"zh": "zh-CN", "zh-tw": "zh-TW", "zh_tw": "zh-TW"}
        tl_norm = tl_map.get((target_lang or "vi").lower(), target_lang or "vi")
        sl_norm = "zh-CN" if source_lang == "zh" else (source_lang or "auto")
        last_error: Exception | None = None
        for name, base in _GOOGLE_ENDPOINTS:
            try:
                if name == "clients5":
                    query = urllib.parse.urlencode(
                        {"client": "dict-chrome-ex", "sl": sl_norm, "tl": tl_norm, "q": text}
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
                    {"client": "gtx", "sl": sl_norm, "tl": tl_norm, "dt": "t", "q": text}
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
        """Trả list bản dịch ĐÚNG thứ tự và ĐÚNG số lượng input.

        E97 — Khi chạy mạng thật với nhiều bong bóng, gửi song song qua `ThreadPoolExecutor`
        và khử trùng lặp câu giống hệt nhau trong cùng trang để giảm thời gian dịch 14 bong bóng
        từ ~17.5s xuống ~2.2s. Khi `_http_json` đang được mock trong unit test thì chạy tuần tự
        để giữ nguyên thứ tự gọi hàm giả lập.
        """
        if not texts:
            return []
        if self.max_workers <= 1 or len(texts) <= 1 or _http_json is not _http_json_mac_dinh:
            return [self._translate_one(text, source_lang, target_lang) for text in texts]

        from concurrent.futures import ThreadPoolExecutor

        # Khử trùng lặp câu không rỗng trong cùng một trang (ví dụ SFX lặp lại カラン / ...)
        duy_nhat: list[str] = []
        da_thay: set[str] = set()
        for t in texts:
            s = (t or "").strip()
            if s and s not in da_thay:
                da_thay.add(s)
                duy_nhat.append(t)

        if not duy_nhat:
            return ["" for _ in texts]

        so_luong = min(self.max_workers, len(duy_nhat))
        with ThreadPoolExecutor(max_workers=so_luong) as ex:
            tuong_lai = {
                t.strip(): ex.submit(self._translate_one, t, source_lang, target_lang)
                for t in duy_nhat
            }
            bang_dich = {k: fut.result() for k, fut in tuong_lai.items()}

        return [bang_dich.get((t or "").strip(), "") for t in texts]


class LLMContextTranslator:
    """Gộp cả trang thành 1 request để giữ mạch văn, xoay API key khi hết quota.

    Prompt giữ đúng khung đã chốt: heading `### page.jpg` + các dòng đánh số 1..N,
    và yêu cầu trả về ĐÚNG số dòng — để ghép 1:1 ngược lại từng vùng.
    """

    engine_enum = TranslationEngine.llm_context

    #: Mã lỗi coi là "hết quota / quá nhịp / hết số dư" -> xoay sang key kế tiếp.
    QUOTA_STATUS = (429, 402)

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
        json_mode: bool = False,
    ) -> None:
        #: E71 — True: gửi đoạn dạng JSON có `id`, ép đầu ra theo `SCHEMA_DICH`, ghép theo `id`.
        #: False: giao thức dòng đánh số như trước E71 (giữ nguyên từng ký tự của prompt).
        self.json_mode = json_mode
        from app.services.tu_chua_lanh import sap_xep_khoa_ai_uu_tien_khoe_manh

        raw_keys = [k.strip() for k in api_keys if k and k.strip()]
        self._api_keys = sap_xep_khoa_ai_uu_tien_khoe_manh(raw_keys)
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

    _TEN_NGON_NGU_QUOC_TE = {
        "vi": "Tiếng Việt",
        "en": "natural Comic/Manga English",
        "zh": "Simplified Chinese (中文简体漫画对白)",
        "zh-tw": "Traditional Chinese (繁體中文漫畫對白)",
        "id": "natural Bahasa Indonesia (Komik/Manhwa)",
        "es": "natural Spanish (Español para Manga/Manhwa)",
        "pt": "natural Brazilian Portuguese (Português para Manga/Webtoon)",
        "th": "natural Thai (ภาษาไทยสำหรับการ์ตูน/มังงะ)",
        "fr": "natural French (Français pour Manga/BD)",
    }

    # ---------- prompt ----------
    def build_prompt_json(self, texts: list[str], source_lang: str, target_lang: str) -> str:
        """E71 — cùng các luật nội dung với `build_prompt`, khác ở GIAO THỨC vào/ra.

        Luật nội dung (bám nghĩa, OCR, tên riêng, chỉ chữ Việt, ảnh) phải giữ ĐỒNG BỘ với
        `build_prompt`; `test_e71_dich_json.py::test_luat_noi_dung_giong_che_do_cu` canh việc đó.
        Chỉ đổi những câu nói về định dạng và về dấu `[?]` (nay là trường `doan`).
        """
        doan_vao = [
            # E30 — vẫn dàn phẳng `\n`: trong JSON nó không còn phá giao thức, nhưng E26-A đã gộp
            # dòng do bong bóng ngắt nên `\n` còn lại là ranh giới câu, nối bằng dấu cách là đủ.
            {"id": i + 1, "text": " ".join((t or "").splitlines()).strip()}
            for i, t in enumerate(texts)
        ]
        tl_norm = (target_lang or "vi").strip()
        if tl_norm.lower() != "vi":
            ten_dich = self._TEN_NGON_NGU_QUOC_TE.get(tl_norm.lower(), tl_norm)
            return (
                f"You are an expert comic/manga/manhwa/manhua translator. Translate the following dialogue lines "
                f"from {source_lang} into {ten_dich}.\n"
                "Mandatory rules:\n"
                f"- Input has {len(texts)} items, each with an `id`. Return a JSON object with a `translations` array: "
                "EACH input `id` must appear EXACTLY ONCE. Never merge two items or split one item.\n"
                f"- Translate cohesively across the whole page into natural, expressive comic dialogue in {ten_dich}.\n"
                "- Stay 100% faithful to the original meaning and character tone; keep lines concise so they fit inside speech bubbles.\n"
                "- If OCR input has minor character recognition typos, infer the intended word from context.\n"
                "- Set `doan` = true ONLY when the source text is truly illegible/ambiguous; otherwise `doan` = false.\n"
                f"- `text` MUST contain ONLY the final translation in {ten_dich} (no explanations, no source text, no notes).\n"
                + (f"\n{self.boi_canh}\n" if self.boi_canh else "")
                + f"\n### {self.page_label}\n{json.dumps(doan_vao, ensure_ascii=False)}"
            )
        return (
            "Bạn là người dịch truyện tranh chuyên nghiệp. Dịch các đoạn thoại dưới đây "
            f"từ {source_lang} sang {target_lang}.\n"
            "Yêu cầu bắt buộc:\n"
            f"- Đầu vào là {len(texts)} đoạn, mỗi đoạn có `id`. Trả về JSON với mảng "
            "`translations`: MỖI `id` đầu vào xuất hiện ĐÚNG MỘT lần, không thêm id lạ. Không gộp "
            "hai đoạn làm một, không tách một đoạn làm hai — dù hai đoạn liền nhau là một câu.\n"
            "- Dịch theo mạch văn của cả trang, không dịch rời rạc từng dòng.\n"
            "- Bám sát nghĩa gốc: không bỏ sót ý, không suy diễn thêm nội dung không có trong câu "
            "gốc. Chỉ được đổi CÁCH DIỄN ĐẠT cho tự nhiên bằng tiếng Việt, không đổi Ý.\n"
            "- Giữ giọng điệu nhân vật; câu thoại ngắn gọn tự nhiên như truyện tranh tiếng Việt.\n"
            "- Chữ đầu vào do máy ĐỌC TỰ ĐỘNG (OCR) nên có thể sai. Được sửa lỗi đọc NHỎ khi ngữ "
            "cảnh làm nghĩa rõ ràng (lệch một ký tự, thiếu dấu câu). KHÔNG được đoán ra một TỪ "
            "KHÁC HẲN chỉ để câu có nghĩa.\n"
            "- Đoạn nào bạn phải ĐOÁN mới dịch được — chữ gốc vô nghĩa, hoặc có nhiều cách hiểu "
            "khác hẳn nhau — thì vẫn dịch bản khả dĩ nhất vào `text`, NHƯNG đặt `doan` = true. "
            "Đây là tín hiệu cho người biên tập: thà báo ra còn hơn để người đọc tưởng một câu bịa "
            "là nội dung thật.\n"
            "- TÊN RIÊNG (người, địa danh): phiên âm theo cách đọc và GIỮ NGUYÊN LÀ TÊN. Không "
            "được thay một cái tên bằng một từ thường. Tên đọc không rõ thì giữ dạng phiên âm "
            "gần nhất và đặt `doan` = true — đừng biến nó thành một danh từ chung.\n"
            "- `text` CHỈ chứa bản dịch: không giải thích, không chú thích trong ngoặc, không chép "
            "lại chữ gốc, không dấu sao, không đánh số.\n"
            # E71 — đo A/B 5+5 lượt: ở chế độ JSON mô hình hay BỎ dấu chấm cuối câu và viết thường
            # chữ đầu ("Đó là Akiyama đấy", "ực ực") — chế độ dòng đánh số thì không. Chuỗi trong
            # JSON trông như nhãn nên nó viết như nhãn; nói thẳng là câu thoại.
            "- Mỗi `text` là một CÂU THOẠI hoàn chỉnh: viết hoa chữ đầu, có dấu câu kết thúc "
            "(. ! ? …) như truyện tranh tiếng Việt.\n"
            "- Bản dịch chỉ được chứa chữ VIỆT, số và dấu câu. Tuyệt đối không để lại ký tự Nhật/"
            "Trung/Hàn trong bản dịch — font không vẽ được chúng và bong bóng sẽ bị bỏ trống.\n"
            "- CHỈ đặt `doan` = true khi chữ gốc thật sự không đọc ra nghĩa. Câu ngắn nhưng rõ "
            "nghĩa (ví dụ một câu hỏi thông thường) thì `doan` = false.\n"
            + (
                "- Kèm theo là ẢNH của chính trang truyện. Dùng ảnh để: (a) ĐỐI CHIẾU chữ đọc "
                "được với chữ trên ảnh, (b) biết câu nào là của nhân vật nào, (c) nhận ra tiếng "
                "động vẽ cách điệu. Ảnh là để HIỂU ĐÚNG, không phải để thêm nội dung không có "
                "trong danh sách. Ảnh mâu thuẫn với chữ đầu vào thì tin ẢNH và đặt `doan` = "
                "true.\n"
                if self.anh_trang else ""
            )
            + "\n"
            + (f"\n{self.boi_canh}\n" if self.boi_canh else "")
            + f"\n### {self.page_label}\n{json.dumps(doan_vao, ensure_ascii=False)}"
        )

    @staticmethod
    def parse_response_json(text: str, expected: int) -> tuple[list[str], set[int]]:
        """E71 — đọc JSON theo `id`. Trả (bản dịch theo thứ tự vào, tập chỉ số `doan`).

        - Thiếu id ⇒ chuỗi rỗng, như `parse_response`: bên gọi để vùng đó `pending`, KHÔNG bịa.
        - id ngoài 1..N hoặc lặp ⇒ bỏ (lấy lần đầu). Koharu cũng bỏ id lặp/lạ.
        - Không đọc được JSON ⇒ `TranslationFailed`: đường lùi `google_fast` sẵn có sẽ bắt. Với
          schema ép thì gần như không xảy ra — nhưng xảy ra thì phải BÁO, không trả trang rỗng.
        - `[?]` lọt vào `text` (mô hình quen tay) vẫn được bóc và tính là `doan`.
        """
        try:
            data = json.loads(text or "")
            muc = data["translations"]
            if not isinstance(muc, list):
                raise TypeError("translations không phải mảng")
        except (ValueError, KeyError, TypeError) as exc:
            from app.services.tu_chua_lanh import tu_sua_json_ban_dich

            dong_cuu_ho = tu_sua_json_ban_dich(text or "", expected)
            if dong_cuu_ho is not None:
                dong_sach, co_dau_cuu = LLMContextTranslator.tach_dau_khong_chac(dong_cuu_ho)
                return dong_sach, co_dau_cuu
            raise TranslationFailed(
                f"llm_json_invalid: không đọc được JSON bản dịch ({type(exc).__name__}): "
                f"{(text or '')[:200]!r}"
            ) from exc
        theo_id: dict[int, tuple[str, bool]] = {}
        for m in muc:
            if not isinstance(m, dict):
                continue
            try:
                i = int(m.get("id"))
            except (TypeError, ValueError):
                continue
            if 1 <= i <= expected and i not in theo_id:
                theo_id[i] = (str(m.get("text") or ""), bool(m.get("doan")))
        dong = [theo_id.get(i + 1, ("", False))[0] for i in range(expected)]
        doan = {i for i in range(expected) if theo_id.get(i + 1, ("", False))[1]}
        dong, co_dau = LLMContextTranslator.tach_dau_khong_chac(dong)
        return dong, doan | co_dau

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
        tl_norm = (target_lang or "vi").strip()
        if tl_norm.lower() != "vi":
            ten_dich = self._TEN_NGON_NGU_QUOC_TE.get(tl_norm.lower(), tl_norm)
            return (
                f"You are an expert comic/manga/manhwa/manhua translator. Translate the following dialogue lines "
                f"from {source_lang} into {ten_dich}.\n"
                "Mandatory rules:\n"
                f"- Return EXACTLY {len(texts)} lines, numbered 1..{len(texts)} matching the input.\n"
                f"- Translate cohesively across the whole page into natural, expressive comic dialogue in {ten_dich}.\n"
                "- Stay 100% faithful to the original meaning and character tone; keep lines concise so they fit inside speech bubbles.\n"
                "- Return ONLY the numbered translations without explanations or notes.\n"
                + (f"\n{self.boi_canh}\n" if self.boi_canh else "")
                + f"\n### {self.page_label}\n{numbered}"
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
    @staticmethod
    def _phan_tich_khoa_ai(raw_key: str, default_model: str = "gemini-3.1-flash-lite") -> dict:
        """Phân tích tiền tố hoặc định dạng khoá để định tuyến tới đúng nhà cung cấp AI.

        Hỗ trợ:
        - `custom|<base_url>|<model>|<api_key>`: Mọi API chuẩn OpenAI-compatible (Together, DashScope/Qwen, Mistral, xAI, vLLM...)
        - `oai|<model>|<api_key>` hoặc `oai:<api_key>` hoặc `sk-proj-...`: OpenAI / ChatGPT API
        - `groq|<model>|<api_key>` hoặc `groq:<api_key>` hoặc `gsk_...`: Groq LPU
        - `or|<model>|<api_key>` hoặc `or:<api_key>` hoặc `sk-or-...`: OpenRouter
        - `ds|<model>|<api_key>` hoặc `ds:<api_key>` hoặc `sk-...`: DeepSeek API
        - `gm|<model>|<api_key>` hoặc `gm:<api_key>` hoặc khoá khác (`AIza...`, `AQ.Ab...`): Google Gemini
        """
        s = (raw_key or "").strip()
        def_m = (default_model or "gemini-3.1-flash-lite").strip()

        if s.startswith("custom|"):
            parts = s.split("|", 3)
            if len(parts) == 4:
                _, base_url, model_c, clean_k = parts
                base_clean = base_url.strip().rstrip("/")
                if not base_clean.endswith("/chat/completions"):
                    endpoint = f"{base_clean}/chat/completions"
                else:
                    endpoint = base_clean
                m_final = model_c.strip() or "gpt-4o-mini"
                return {
                    "provider": "custom",
                    "ten_ncc": f"Model mở rộng ({m_final})",
                    "endpoint": endpoint,
                    "base_url": base_clean,
                    "model": m_final,
                    "api_key": clean_k.strip(),
                    "is_openai_compat": True,
                }

        if s.startswith("claude|"):
            parts = s.split("|", 2)
            if len(parts) == 3:
                m_final = parts[1].strip() or "claude-3-5-haiku-latest"
                return {
                    "provider": "claude",
                    "ten_ncc": f"Anthropic Claude ({m_final})",
                    "endpoint": "https://api.anthropic.com/v1/messages",
                    "model": m_final,
                    "api_key": parts[2].strip(),
                    "is_openai_compat": False,
                    "is_anthropic": True,
                }
        if s.startswith("claude:") or s.startswith("sk-ant-"):
            clean_k = s[7:].strip() if s.startswith("claude:") else s
            m_final = def_m if def_m.lower().startswith("claude-") else "claude-3-5-haiku-latest"
            return {
                "provider": "claude",
                "ten_ncc": f"Anthropic Claude ({m_final})",
                "endpoint": "https://api.anthropic.com/v1/messages",
                "model": m_final,
                "api_key": clean_k,
                "is_openai_compat": False,
                "is_anthropic": True,
            }

        if s.startswith("oai|"):
            parts = s.split("|", 2)
            if len(parts) == 3:
                m_final = parts[1].strip() or "gpt-4o-mini"
                return {
                    "provider": "openai",
                    "ten_ncc": f"OpenAI ({m_final})",
                    "endpoint": "https://api.openai.com/v1/chat/completions",
                    "model": m_final,
                    "api_key": parts[2].strip(),
                    "is_openai_compat": True,
                }
        if s.startswith("oai:") or s.startswith("sk-proj-") or s.startswith("sk-svcacct-"):
            clean_k = s[4:].strip() if s.startswith("oai:") else s
            m_final = def_m if def_m.lower().startswith(("gpt-", "o1", "o3", "o4")) else "gpt-4o-mini"
            return {
                "provider": "openai",
                "ten_ncc": f"OpenAI ({m_final})",
                "endpoint": "https://api.openai.com/v1/chat/completions",
                "model": m_final,
                "api_key": clean_k,
                "is_openai_compat": True,
            }

        if s.startswith("groq|"):
            parts = s.split("|", 2)
            if len(parts) == 3:
                m_final = parts[1].strip() or "llama-3.3-70b-versatile"
                return {
                    "provider": "groq",
                    "ten_ncc": f"Groq LPU ({m_final})",
                    "endpoint": "https://api.groq.com/openai/v1/chat/completions",
                    "model": m_final,
                    "api_key": parts[2].strip(),
                    "is_openai_compat": True,
                }
        if s.startswith("groq:") or s.startswith("gsk_"):
            clean_k = s[5:].strip() if s.startswith("groq:") else s
            return {
                "provider": "groq",
                "ten_ncc": "Groq LPU (llama-3.3-70b-versatile)",
                "endpoint": "https://api.groq.com/openai/v1/chat/completions",
                "model": "llama-3.3-70b-versatile",
                "api_key": clean_k,
                "is_openai_compat": True,
            }

        if s.startswith("or|"):
            parts = s.split("|", 2)
            if len(parts) == 3:
                m_final = parts[1].strip() or "google/gemini-2.5-flash"
                return {
                    "provider": "openrouter",
                    "ten_ncc": f"OpenRouter ({m_final})",
                    "endpoint": "https://openrouter.ai/api/v1/chat/completions",
                    "model": m_final,
                    "api_key": parts[2].strip(),
                    "is_openai_compat": True,
                }
        if s.startswith("or:") or s.startswith("sk-or-"):
            clean_k = s[3:].strip() if s.startswith("or:") else s
            return {
                "provider": "openrouter",
                "ten_ncc": "OpenRouter (google/gemini-2.5-flash)",
                "endpoint": "https://openrouter.ai/api/v1/chat/completions",
                "model": "google/gemini-2.5-flash",
                "api_key": clean_k,
                "is_openai_compat": True,
            }

        if s.startswith("ds|"):
            parts = s.split("|", 2)
            if len(parts) == 3:
                m_final = parts[1].strip() or "deepseek-chat"
                return {
                    "provider": "deepseek",
                    "ten_ncc": f"DeepSeek ({m_final})",
                    "endpoint": _DEEPSEEK_ENDPOINT,
                    "model": m_final,
                    "api_key": parts[2].strip(),
                    "is_openai_compat": True,
                }
        if s.startswith("ds:") or s.startswith("sk-") or def_m.lower().startswith("deepseek"):
            clean_k = s[3:].strip() if s.startswith("ds:") else s
            m_final = def_m if def_m.lower().startswith("deepseek") else "deepseek-chat"
            return {
                "provider": "deepseek",
                "ten_ncc": f"DeepSeek ({m_final})",
                "endpoint": _DEEPSEEK_ENDPOINT,
                "model": m_final,
                "api_key": clean_k,
                "is_openai_compat": True,
            }

        if s.startswith("gm|"):
            parts = s.split("|", 2)
            if len(parts) == 3:
                m_final = parts[1].strip() or "gemini-3.1-flash-lite"
                if m_final.lower() == "gemini-3.5-flash":
                    m_final = "gemini-3.5-flash-lite"
                elif m_final.lower() == "gemini-2.5-flash":
                    m_final = "gemini-3.1-flash-lite"
                clean_k = parts[2].strip()
                la_vertex_aq = clean_k.startswith("AQ.")
                ep_gm = (
                    f"https://aiplatform.googleapis.com/v1/publishers/google/models/{m_final}:generateContent?key={clean_k}"
                    if la_vertex_aq
                    else _GEMINI_ENDPOINT.format(model=m_final)
                )
                return {
                    "provider": "gemini",
                    "ten_ncc": f"Google Gemini ({m_final})",
                    "endpoint": ep_gm,
                    "model": m_final,
                    "api_key": clean_k,
                    "is_openai_compat": False,
                    "is_vertex_aq": la_vertex_aq,
                }
        clean_gm = s[3:].strip() if s.startswith("gm:") else s
        m_gm = def_m if not def_m.lower().startswith("deepseek") else "gemini-3.1-flash-lite"
        if m_gm.lower() == "gemini-3.5-flash":
            m_gm = "gemini-3.5-flash-lite"
        elif m_gm.lower() == "gemini-2.5-flash":
            m_gm = "gemini-3.1-flash-lite"
        la_vertex_aq = clean_gm.startswith("AQ.")
        ep_gm_def = (
            f"https://aiplatform.googleapis.com/v1/publishers/google/models/{m_gm}:generateContent?key={clean_gm}"
            if la_vertex_aq
            else _GEMINI_ENDPOINT.format(model=m_gm)
        )
        return {
            "provider": "gemini",
            "ten_ncc": f"Google Gemini ({m_gm})",
            "endpoint": ep_gm_def,
            "model": m_gm,
            "api_key": clean_gm,
            "is_openai_compat": False,
            "is_vertex_aq": la_vertex_aq,
        }

    @classmethod
    def _la_khoa_deepseek(cls, key: str, model_name: str = "") -> bool:
        info = cls._phan_tich_khoa_ai(key, model_name)
        return bool(info.get("is_openai_compat"))

    def _generation_config(self, schema: dict | None = None) -> dict:
        cfg: dict = {
            "temperature": self.temperature,
            "maxOutputTokens": self.max_output_tokens,
        }
        if self.thinking_budget is not None:
            cfg["thinkingConfig"] = {"thinkingBudget": self.thinking_budget}
        if schema is not None:
            cfg["responseMimeType"] = "application/json"
            cfg["responseSchema"] = schema
        return cfg

    def _call_api(self, prompt: str, schema: dict | None = None) -> tuple[str, dict]:
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
        gen_cfg = self._generation_config(schema)
        body = json.dumps(
            {
                "contents": [{"parts": parts}],
                "generationConfig": gen_cfg,
            }
        ).encode("utf-8")
        body_vertex = json.dumps(
            {
                "contents": [{"role": "user", "parts": parts}],
                "generationConfig": gen_cfg,
            }
        ).encode("utf-8")
        gen_cfg_no_think = {k: v for k, v in gen_cfg.items() if k != "thinkingConfig"}
        body_vertex_no_think = json.dumps(
            {
                "contents": [{"role": "user", "parts": parts}],
                "generationConfig": gen_cfg_no_think,
            }
        ).encode("utf-8")

        attempts = max(self.key_count, 1)
        last_error: Exception | None = None
        for _ in range(attempts):
            key = self._current_key()
            info_k = self._phan_tich_khoa_ai(key, self.model_name)
            la_oai_compat = bool(info_k.get("is_openai_compat"))
            la_anthropic = bool(info_k.get("is_anthropic"))
            la_vertex_aq = bool(info_k.get("is_vertex_aq"))
            if la_anthropic:
                import base64 as _b64_ant

                ant_content: list[dict] = []
                if self.anh_trang:
                    ant_content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": self.anh_mime or "image/jpeg",
                            "data": _b64_ant.b64encode(self.anh_trang).decode("ascii"),
                        },
                    })
                ant_prompt = prompt
                if schema is not None:
                    ant_prompt = f"{prompt}\n\nReturn ONLY valid JSON matching the requested schema, with no markdown code fences."
                ant_content.append({"type": "text", "text": ant_prompt})
                ant_payload = {
                    "model": info_k["model"],
                    "max_tokens": min(self.max_output_tokens, 8192),
                    "temperature": self.temperature,
                    "system": (
                        "Bạn là chuyên gia dịch truyện tranh đa ngôn ngữ (You are an expert multilingual "
                        "comic/manga/manhwa/manhua translator). Hãy dịch chính xác sang đúng ngôn ngữ đích "
                        "và định dạng được yêu cầu trong user prompt."
                    ),
                    "messages": [{"role": "user", "content": ant_content}],
                }
                request = urllib.request.Request(
                    info_k["endpoint"],
                    data=json.dumps(ant_payload).encode("utf-8"),
                    method="POST",
                    headers={
                        "x-api-key": info_k["api_key"],
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                        "User-Agent": "ComicTranslator/2.0",
                    },
                )
            elif la_oai_compat:
                clean_key = info_k["api_key"]
                endpoint_oai = info_k["endpoint"]
                ds_model = info_k["model"]
                user_content: str | list[dict] = prompt
                if self.anh_trang and info_k.get("provider") != "deepseek":
                    import base64 as _b64_oai

                    user_content = [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{self.anh_mime or 'image/jpeg'};base64,{_b64_oai.b64encode(self.anh_trang).decode('ascii')}",
                            },
                        },
                        {"type": "text", "text": prompt},
                    ]
                ds_payload: dict = {
                    "model": ds_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Bạn là chuyên gia dịch truyện tranh đa ngôn ngữ (You are an expert multilingual "
                                "comic/manga/manhwa/manhua translator). Hãy dịch chính xác sang đúng ngôn ngữ đích "
                                "và định dạng được yêu cầu trong user prompt."
                            ),
                        },
                        {"role": "user", "content": user_content},
                    ],
                    "temperature": self.temperature,
                    "max_tokens": min(self.max_output_tokens, 8192),
                    "stream": False,
                }
                if schema is not None:
                    ds_payload["response_format"] = {"type": "json_object"}
                request = urllib.request.Request(
                    endpoint_oai,
                    data=json.dumps(ds_payload).encode("utf-8"),
                    method="POST",
                    headers={
                        "Authorization": f"Bearer {clean_key}",
                        "Content-Type": "application/json",
                        "User-Agent": "ComicTranslator/2.0",
                    },
                )
            else:
                request = urllib.request.Request(
                    info_k["endpoint"],
                    data=body,
                    method="POST",
                    headers={"x-goog-api-key": info_k["api_key"], "Content-Type": "application/json"},
                )
            try:
                data = _http_json(request, self.timeout)
                if la_anthropic:
                    blocks = data.get("content") or []
                    txt_ant = "".join(str(b.get("text") or "") for b in blocks if isinstance(b, dict)).strip()
                    if txt_ant.startswith("```"):
                        txt_ant = txt_ant.strip("`")
                        if txt_ant.lower().startswith("json"):
                            txt_ant = txt_ant[4:].strip()
                    u_ant = data.get("usage") or {}
                    in_tok = int(u_ant.get("input_tokens") or 0)
                    out_tok = int(u_ant.get("output_tokens") or 0)
                    return txt_ant, {
                        "promptTokenCount": in_tok,
                        "candidatesTokenCount": out_tok,
                        "totalTokenCount": in_tok + out_tok,
                    }
                if la_oai_compat:
                    choice = (data.get("choices") or [{}])[0]
                    msg = choice.get("message") or {}
                    usage_ds = data.get("usage") or {}
                    return str(msg.get("content") or ""), {
                        "promptTokenCount": usage_ds.get("prompt_tokens"),
                        "candidatesTokenCount": usage_ds.get("completion_tokens"),
                        "totalTokenCount": usage_ds.get("total_tokens"),
                        "cachedContentTokenCount": usage_ds.get("prompt_cache_hit_tokens"),
                    }
                candidate = (data.get("candidates") or [{}])[0]
                parts_out = (candidate.get("content") or {}).get("parts") or []
                return "".join(p.get("text", "") for p in parts_out), data.get("usageMetadata", {})
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:300] if hasattr(exc, "read") else ""
                if (la_vertex_aq or (not la_oai_compat and not la_anthropic)) and exc.code in (400, 404) and self.key_count >= 1:
                    ck = info_k["api_key"]
                    m_cur = info_k["model"]
                    ds_thu_tiep = (
                        [
                            (f"https://aiplatform.googleapis.com/v1/publishers/google/models/{m_cur}:generateContent?key={ck}", body_vertex),
                            (_GEMINI_ENDPOINT.format(model="gemini-3.1-flash-lite-preview"), body),
                            (f"https://aiplatform.googleapis.com/v1/publishers/google/models/gemini-3.1-flash-lite-preview:generateContent?key={ck}", body_vertex_no_think),
                            (_GEMINI_ENDPOINT.format(model="gemini-2.5-flash-lite"), body),
                            (f"https://aiplatform.googleapis.com/v1/publishers/google/models/gemini-2.5-flash-lite:generateContent?key={ck}", body_vertex_no_think),
                            (_GEMINI_ENDPOINT.format(model="gemini-3.1-flash-image-preview"), body_vertex_no_think),
                            (f"https://aiplatform.googleapis.com/v1/publishers/google/models/gemini-3.1-flash-image-preview:generateContent?key={ck}", body_vertex_no_think),
                        ]
                        if la_vertex_aq
                        else (
                            [
                                (_GEMINI_ENDPOINT.format(model="gemini-3.1-flash-lite-preview"), body),
                                (_GEMINI_ENDPOINT.format(model="gemini-2.5-flash-lite"), body),
                                (_GEMINI_ENDPOINT.format(model="gemini-2.5-flash"), body),
                                (_GEMINI_ENDPOINT.format(model="gemini-3.1-flash-image-preview"), body_vertex_no_think),
                            ]
                            if len(ck) >= 16
                            else []
                        )
                    )
                    for fb_url, fb_body in ds_thu_tiep:
                        try:
                            fb_req = urllib.request.Request(
                                fb_url,
                                data=fb_body,
                                method="POST",
                                headers={"x-goog-api-key": ck, "Content-Type": "application/json"},
                            )
                            data = _http_json(fb_req, self.timeout)
                            candidate = (data.get("candidates") or [{}])[0]
                            parts_out = (candidate.get("content") or {}).get("parts") or []
                            return "".join(p.get("text", "") for p in parts_out), data.get("usageMetadata", {})
                        except urllib.error.HTTPError as fb_exc:
                            detail = fb_exc.read().decode("utf-8", "replace")[:300] if hasattr(fb_exc, "read") else detail
                        except Exception:
                            pass
                last_error = TranslationFailed(f"HTTP {exc.code}: {detail}")
                self.usage.errors.append(f"HTTP {exc.code}")
                detail_lower = detail.lower()
                la_loi_khoa_xoay_duoc = (
                    exc.code in self.QUOTA_STATUS
                    or (
                        self.key_count > 1
                        and (
                            exc.code in (401, 403)
                            or "api key not valid" in detail_lower
                            or "api_key_invalid" in detail_lower
                            or "key expired" in detail_lower
                        )
                    )
                )
                if la_loi_khoa_xoay_duoc:
                    from app.services.tu_chua_lanh import danh_dau_khoa_ai_tam_ngung

                    danh_dau_khoa_ai_tam_ngung(
                        api_key=key,
                        nha_cung_cap=info_k.get("provider", self.model_name),
                        ly_do=f"HTTP {exc.code}: {detail[:80]}",
                        thoi_gian_giay=60.0 if exc.code == 429 else 180.0,
                    )
                    logger.warning("Key hiện tại lỗi/hết nhịp (HTTP %s) -> xoay key", exc.code)
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
        if self.json_mode:
            prompt = self.build_prompt_json(texts, source_lang, target_lang)
            text, usage = self._call_api(prompt, SCHEMA_DICH)
        else:
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
        if self.json_mode:
            dong, self.vung_khong_chac = self.parse_response_json(text, len(texts))
        else:
            dong = self.parse_response(text, len(texts))
            # E66 — bóc dấu `[?]` và GHI LẠI vùng nào bị đánh, để bên gọi bật cờ "cần xem lại".
            # Đặt trên `self` thay vì đổi kiểu trả về: `google_fast` dùng chung giao diện
            # `translate` và không có khái niệm này. Bên gọi đọc bằng `getattr(..., set())`.
            dong, self.vung_khong_chac = self.tach_dau_khong_chac(dong)
        if self.vung_khong_chac:
            logger.info(
                "E66: %d/%d dòng mô hình tự báo là ĐOÁN", len(self.vung_khong_chac), len(dong),
            )
        # Bổ sung từ điển SFX tĩnh đa ngôn ngữ cho các dòng chữ tượng thanh bị bỏ trống hoặc giữ nguyên CJK
        from app.services.translate.sfx import tra_cuu_sfx_nhanh

        for idx_d, goc_d in enumerate(texts):
            if idx_d < len(dong) and (not dong[idx_d] or dong[idx_d].strip() == (goc_d or "").strip()):
                sfx_dich = tra_cuu_sfx_nhanh(goc_d, target_lang)
                if sfx_dich:
                    dong[idx_d] = sfx_dich
        return dong


def get_translator(engine: str, api_keys: list[str] | None = None, **kwargs):
    """Factory theo tên engine. Giá trị lạ → raise rõ ràng, không fallback âm thầm."""
    value = engine.value if isinstance(engine, TranslationEngine) else str(engine)
    if value == TranslationEngine.google_fast.value:
        return GoogleTranslateEngine(**{k: v for k, v in kwargs.items() if k in ("timeout", "user_agent")})
    if value == TranslationEngine.llm_context.value:
        return LLMContextTranslator(api_keys=api_keys or [], **kwargs)
    if value == TranslationEngine.local_llm.value:
        from app.services.translate.llm_cuc_bo import OpenAICompatTranslator

        return OpenAICompatTranslator(**kwargs)
    if value == TranslationEngine.chatgpt_codex.value:
        from app.services.translate.codex import CodexTranslator

        return CodexTranslator(**kwargs)
    raise UnsupportedTranslationEngine(
        f"engine '{value}' không được hỗ trợ "
        "(google_fast / llm_context / local_llm / chatgpt_codex)"
    )


#: Các engine là MÔ HÌNH NGÔN NGỮ: lỗi thì lùi về `google_fast` (M5), nhận bối cảnh E31, nhận ảnh E32.
ENGINE_LLM = frozenset({
    TranslationEngine.llm_context.value,
    TranslationEngine.local_llm.value,
    TranslationEngine.chatgpt_codex.value,
})
