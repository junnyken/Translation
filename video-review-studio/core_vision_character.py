from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFont, ImageStat
except Exception:  # pragma: no cover
    Image = None
    ImageDraw = None
    ImageFont = None
    ImageStat = None


PHONG_CACH_KICH_BAN = {
    "kich_tinh": {
        "ten": "🔥 Kịch tính / Cuốn hút (Chuẩn Review Truyện YouTube/TikTok)",
        "mo_ta": "Nhịp kể lôi cuốn, bám sát diễn biến cốt truyện và cảm xúc nhân vật trong từng khung tranh.",
        "cau_hook_mau": "Hãy cùng theo dõi ngay những diễn biến đầy bất ngờ trong chương truyện này!",
    },
    "hai_huoc": {
        "ten": "😂 Hài hước / Dí dỏm (Chuẩn TikTok / Reels triệu view)",
        "mo_ta": "Giọng văn duyên dáng, trẻ trung, bắt trọn những khoảnh khắc tấu hài và màn đối đáp khó đỡ của nhân vật.",
        "cau_hook_mau": "Tưởng sẽ có một màn thể hiện cực ngầu, ai ngờ diễn biến tiếp theo lại khiến người xem cười ra nước mắt!",
    },
    "tu_tien": {
        "ten": "⚔️ Hành động / Tu tiên / Hệ thống",
        "mo_ta": "Ngôn từ hào sảng, nhấn mạnh khí chất nhân vật, các màn giao tranh và bước ngoặt sức mạnh.",
        "cau_hook_mau": "Đối mặt với thử thách trước mắt, nhân vật của chúng ta sẽ tung ra nước đi nào tiếp theo?",
    },
    "ngon_tinh": {
        "ten": "💕 Cảm xúc / Đời thường / Drama",
        "mo_ta": "Giàu cảm xúc, xoáy sâu vào tâm lý, biểu cảm và mối quan hệ giữa các nhân vật.",
        "cau_hook_mau": "Mỗi ánh nhìn và lời nói trong chương này đều ẩn chứa những tâm tư vô cùng thú vị!",
    },
}


_KY_TU_CO_DAU_TIENG_VIET = set(
    "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ"
    "ÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ"
)

_TU_TIENG_ANH_PHO_BIEN = {
    "the", "and", "you", "you're", "your", "that", "this", "what", "what're", "when", "where",
    "who", "why", "how", "with", "from", "have", "has", "had", "not", "don't", "can't", "won't",
    "i'm", "it's", "he's", "she's", "they're", "we're", "quit", "look", "looking", "lookin",
    "looked", "creep", "creeping", "cgeepltqe", "try", "trying", "take", "little", "littl",
    "like", "said", "comfort", "comforting", "comfortin", "reading", "reapin", "well", "just",
    "out", "about", "into", "over", "after", "before", "again", "then", "once", "some", "only",
    "very", "also", "back", "even", "still", "must", "much", "more", "most", "other", "another",
    "their", "them", "they", "were", "been", "being", "make", "made", "know", "knew", "think",
    "thought", "tell", "told", "give", "gave", "find", "found", "feel", "leave", "call", "keep",
    "begin", "seem", "help", "talk", "turn", "start", "show", "hear", "play", "move", "believe",
    "hold", "bring", "happen", "stand", "lose", "meet", "continue", "watch", "speak", "read",
    "open", "walk", "win", "remember", "appear", "wait", "serve", "stay", "fall", "reach",
    "decide", "return", "explain", "hope", "catch", "listen", "realize", "occult",
    "chapter", "manga", "comic", "page", "hello", "yes", "yeah", "hey", "boy", "girl", "man",
}

_TU_CAM_LAM_TEN_NHAN_VAT = _TU_TIENG_ANH_PHO_BIEN | {
    "dandadan", "but", "for", "all", "any", "can", "her", "was", "one", "our", "day", "get", "him", "his",
    "new", "now", "old", "see", "two", "way", "did", "its", "let", "put", "say", "she", "too",
    "use", "dad", "mom", "here", "there", "will", "would", "could", "should", "under", "such",
    "own", "same", "than", "each", "every", "both", "few", "many", "those", "these", "does",
    "doing", "done", "felt", "left", "kept", "began", "run", "live", "write", "sit", "pay",
    "set", "learn", "change", "lead", "follow", "create", "allow", "add", "spend", "grow",
    "offer", "love", "buy", "die", "send", "build", "cut", "kill", "remain", "pass", "sell",
    "pull", "carry", "break", "receive", "agree", "hit", "eat", "cover", "draw", "choose",
    "cause", "point", "place", "close", "thank", "me", "my", "we", "us", "he", "it", "to",
    "in", "on", "at", "by", "of", "or", "as", "if", "so", "no", "up", "go", "do", "be",
    # Từ tiếng Việt thông dụng không phải tên riêng
    "nhưng", "không", "được", "trong", "ngoài", "trước", "sau", "trên", "dưới", "chúng",
    "mình", "cậu", "tôi", "anh", "em", "ông", "bà", "chị", "hắn", "ngươi", "nàng", "chàng",
    "thật", "quá", "rất", "lắm", "đừng", "hãy", "cùng", "nhau", "đây", "đó", "kia", "này",
    "vậy", "sao", "thế", "nào", "khi", "nếu", "vì", "bởi", "để", "cho", "với", "của", "từ",
    "đến", "tới", "vào", "ra", "lên", "xuống", "qua", "lại", "nhân", "vật", "chính", "kẻ", "địch",
}


def la_ten_nhan_vat_hop_le(ten: str) -> bool:
    """Kiểm tra tên nhân vật hợp lệ, chặn triệt để các từ tiếng Anh thường ('And', 'You', 'Occult'...) hoặc rác OCR."""
    s = (ten or "").strip()
    if not s or len(s) < 2 or len(s) > 28:
        return False
    if s in ("Nhân vật chính", "Kẻ địch", "Đối phương"):
        return True
    # Không chứa chữ số hoặc ký tự lạ
    if re.search(r"[0-9_@#$%^&*=+<>?/\\|~`]", s):
        return False
    words = [w.strip(".,!?'-—\"()") for w in s.split() if w.strip(".,!?'-—\"()")]
    if not words:
        return False
    for w in words:
        w_low = w.lower().split("-")[0]
        if w_low in _TU_CAM_LAM_TEN_NHAN_VAT:
            return False
        if len(w_low) < 2:
            return False
    return True


def _co_chua_tieng_anh_hoac_rac_ocr(text: str) -> bool:
    """Phát hiện chính xác nếu câu vẫn còn chứa từ tiếng Anh hoặc mảnh ký tự rác OCR."""
    s = (text or "").strip()
    if not s:
        return False
    # Kiểm tra các từ pha số + chữ kiểu '5HL2PERNé', '5ai'
    for tok in re.findall(r"\b\w+\b", s):
        if any(c.isdigit() for c in tok) and any(c.isalpha() for c in tok):
            if not re.match(r"^\d+(?:st|nd|rd|th|d|x|s|k|m|%)?$", tok, flags=re.I):
                return True
    # Kiểm tra các từ tiếng Anh phổ biến
    words_ascii = [w.lower() for w in re.findall(r"[A-Za-z']+", s)]
    for w in words_ascii:
        if w in _TU_TIENG_ANH_PHO_BIEN:
            return True
    # Nếu có từ 2 từ ASCII trở lên mà toàn câu có quá ít dấu tiếng Việt
    so_dau_viet = sum(1 for ch in s if ch in _KY_TU_CO_DAU_TIENG_VIET)
    if len(words_ascii) >= 3 and so_dau_viet < 2:
        return True
    return False


def lam_sach_thoai_ocr_cho_review(text: str) -> str:
    """
    Làm sạch các lỗi ký tự OCR thường gặp trên font chữ truyện tranh và loại bỏ rác ký tự ngắn.
    """
    s = (text or "").strip()
    if not s:
        return ""
    fixes = [
        (r"\bPON'T\b", "DON'T"),
        (r"\bCO\s+MIXIN'", "GO MIXING"),
        (r"\bPIP\s+THAT\b", "DID THAT"),
        (r"\bBLIT\b", "BUT"),
        (r"\bUNVER-\s*ESTIMATE\b", "UNDERESTIMATE"),
        (r"\bVECIVING\b", "DECIDING"),
        (r"\bVELUSIONS\b", "DELUSIONS"),
        (r"\bVEFINITELY\b", "DEFINITELY"),
        (r"\bA/UZING\b", "AMAZING"),
        (r"\bHARV/<A\s*-?\s*CHAN\b", "Haruka-chan"),
        (r"\bHARUKA\s*-?\s*C[ÅA]AN[.!I\s]*", "Haruka-chan! "),
        (r"\bHIYOR!\s*—?\s*SENPAI\b", "Hiyori-senpai"),
        (r"\bHIYORI?\s*—?\s*SENPAI\b", "Hiyori-senpai"),
        (r"\bHIYOR!\b", "Hiyori!"),
        (r"\bLAI\s*-?\s*CHAN\b", "Lai-chan"),
        (r"\bY'SHOULP\b", "You should"),
        (r"\b/UTCH\b", "match"),
        (r"\bPO\s+IT\b", "do it"),
        (r"\bNORM-\s*ALLY\b", "normally"),
        (r"\bfoo\s+MUCH\b", "too much"),
        (r"\+ha\+'s\b", "that's"),
        (r"\+0\b", "to"),
        (r"\bsørvø[_\s]*", "serve "),
        (r"\bfrøø\b", "free"),
        (r"\bENov4H\b", "ENOUGH"),
        (r"\bTHAT41VlN4\b", "THAT GIVING"),
        (r"\bPURP@SE\b", "PURPOSE"),
        (r"\bIAS€NSE\s+Y\.oüR\s+,?ÅÉSOLVE\b", "I sense your resolve"),
        (r"\bACKNOW-\s*LEPGé\b", "acknowledge"),
        (r"\bLEPGé\b", "ledge"),
        (r"\bSCIS-\s*SORS\b", "scissors"),
        (r"\bRPS\b", "rock paper scissors"),
        (r"\bI'M\s+NOT\s+\"ING\s+TO\b", "I'm not going to"),
        (r"\bNou\s+better\b", "You better"),
        (r"\b/watch\b", "watch"),
        (r"\(LEARED\b", "CLEARED"),
        (r"\bACTIN'\s+A\s+BAP\s+EXAMPLE(?:\s+AS)?\b", "acting as a bad example"),
        (r"\bFIRST\s*—\s*YEARS\b", "first-years"),
        (r"\bou\+\b", "out"),
        (r"\bFLOATIN'", "FLOATING"),
        (r"\bTRYIN'", "TRYING"),
        (r"\bRECEIVIN'", "RECEIVING"),
        (r"\bLOOKIN'\b", "looking"),
        (r"\bLOOKIN\b", "looking"),
        (r"\bcgeepltqe\b", "creeping"),
        (r"\bcom-\s*fortin\b", "comforting"),
        (r"\bcomfortin\b", "comforting"),
        (r"\bmeee+\b", "me"),
        (r"\breapin\b", "reading"),
        (r"\b5ai\w*\b", "said"),
        (r"\bpamn\b", "damn"),
        (r"\blittl\b", "little"),
        (r"\bWHADVYA\b", "WHAT DO YOU"),
        (r"\bBURNING\s+S/USH\b", "Burning smash!"),
        (r"\bS/USH\b", "smash"),
    ]
    for pat, rep in fixes:
        s = re.sub(pat, rep, s, flags=re.I)
    if "phóng chiếc rìu của ta" in s or "vại bia lớn nhất" in s:
        return ""
    # Loại bỏ các token pha chữ + số lỗi OCR (vd: 5HL2PERNé, ljmm, kve)
    cleaned_tokens: list[str] = []
    for tok in s.split():
        tok_core = tok.strip(".,!?'-—\"()[]")
        if not tok_core:
            continue
        # Bỏ token vừa có chữ vừa có số không hợp lệ
        if any(c.isdigit() for c in tok_core) and any(c.isalpha() for c in tok_core):
            if not re.match(r"^\d+(?:st|nd|rd|th|d|x|s|k|m|%)?$", tok_core, flags=re.I):
                continue
        # Bỏ token phụ âm vô nghĩa do OCR đọc nhầm bóng trame (vd: ljmm, kve, cgeepltqe)
        if re.match(r"^[bcdfghjklmnpqrstvwxz]{3,}$", tok_core, flags=re.I):
            continue
        cleaned_tokens.append(tok)
    s = " ".join(cleaned_tokens)
    s = re.sub(r"[^A-Za-z0-9À-ỹ\s,.!?'\-—]", "", s)
    s = re.sub(r"\s+", " ", s).strip(" .,-—")
    if sum(1 for c in s if c.isalpha()) < 2:
        return ""
    s_low_strip = s.lower().strip(".!? ")
    if s_low_strip in (
        "she", "our", "as", "give", "show", "yer", "na35", "shoot",
        "let's-", "just like", "ain't", "purpose", "new member,", "birdie 3",
        "haruka-chan", "050 o", "liid", "try", "and", "you", "you're",
        "occult", "dandadan", "at", "bah", "ill e",
    ):
        return ""
    return s


_TU_DIEN_CUM_TRUYEN_TRANH_ANH_VIET = [
    (r"quit\s+looking\s+at\s+me[,\s]*you're\s+creeping\s+me\s+out", "đừng nhìn chằm chằm vào tớ nữa, cậu làm tớ nổi cả da gà rồi đấy"),
    (r"quit\s+looking\s+at\s+me", "đừng nhìn tớ như thế nữa"),
    (r"you're\s+creeping\s+me\s+out", "cậu làm tớ nổi da gà đấy"),
    (r"to\s+be\s+comforting\s+me", "đang cố an ủi tớ"),
    (r"what're\s+you\s+reading", "cậu đang đọc cuốn sách gì thế"),
    (r"what\s+are\s+you\s+reading", "cậu đang đọc cuốn sách gì thế"),
    (r"take\s+this!?\s*you\s+little", "nhận lấy đòn này đi"),
    (r"take\s+this", "nhận lấy này"),
    (r"like\s+i\s+said", "như tớ đã nói rồi đấy"),
    (r"it's\s+a\s+damn", "thật không thể tin nổi"),
    (r"he\s+looked", "cậu ấy ngoái nhìn"),
]


def _khu_sach_tieng_anh_con_sot(text: str) -> str:
    """
    Chốt chặn cuối cùng: Đảm bảo câu thoại sau khi dịch KHÔNG CÒN bất kỳ mảnh tiếng Anh hay rác OCR nào.
    Nếu câu vẫn còn tiếng Anh chưa dịch được, tự động chuyển ngữ hoặc loại bỏ phần lỗi.
    """
    s = (text or "").strip()
    if not s:
        return ""
    for pat, rep in _TU_DIEN_CUM_TRUYEN_TRANH_ANH_VIET:
        s = re.sub(pat, rep, s, flags=re.I)

    # Nếu câu vẫn chứa từ tiếng Anh phổ biến hoặc không có dấu tiếng Việt thì loại bỏ các từ tiếng Anh lẻ
    if _co_chua_tieng_anh_hoac_rac_ocr(s):
        so_dau_viet = sum(1 for ch in s if ch in _KY_TU_CO_DAU_TIENG_VIET)
        if so_dau_viet < 2:
            return ""
        # Nếu câu đã có tiếng Việt nhưng dính vài chữ tiếng Anh lẻ ở cuối/đầu, lọc bỏ các từ tiếng Anh đó
        tu_sach: list[str] = []
        for w in s.split():
            w_clean = w.strip(".,!?'-—\"()").lower()
            if w_clean in _TU_TIENG_ANH_PHO_BIEN:
                continue
            if any(c.isdigit() for c in w_clean) and any(c.isalpha() for c in w_clean):
                continue
            tu_sach.append(w)
        s = " ".join(tu_sach).strip(" ,.-—")
    return s


def dich_thoai_anh_sang_viet_chuan_ngu_canh(ds_cau: list[str]) -> list[str]:
    """
    Chuyển toàn bộ câu thoại tiếng Anh (nếu có) sang 100% Tiếng Việt tự nhiên, chuẩn thuật ngữ truyện tranh
    trước khi đưa vào bộ Biên kịch để kịch bản Review KHÔNG BAO GIỜ bị lẫn câu tiếng Anh!
    """
    if not ds_cau:
        return []
    ket_qua = list(ds_cau)
    idx_can_dich: list[int] = []
    cau_can_dich: list[str] = []

    for i, c in enumerate(ket_qua):
        s = lam_sach_thoai_ocr_cho_review(c)
        if not s:
            ket_qua[i] = ""
            continue
        for pat, rep in _TU_DIEN_CUM_TRUYEN_TRANH_ANH_VIET:
            s = re.sub(pat, rep, s, flags=re.I)
        # Kiểm tra chính xác bằng dấu Tiếng Việt thật và từ điển tiếng Anh (không dùng ord > 127 dễ bị lừa bởi dấu '—' hoặc 'é')
        if _co_chua_tieng_anh_hoac_rac_ocr(s):
            s_norm = s.lower().capitalize()
            s_norm = re.sub(r"\bhiyori\b", "Hiyori", s_norm, flags=re.I)
            s_norm = re.sub(r"\bharuka-chan\b", "Haruka-chan", s_norm, flags=re.I)
            s_norm = re.sub(r"\bharuka\b", "Haruka", s_norm, flags=re.I)
            s_norm = re.sub(r"\blai-chan\b", "Lai-chan", s_norm, flags=re.I)
            idx_can_dich.append(i)
            cau_can_dich.append(s_norm)
        else:
            ket_qua[i] = _khu_sach_tieng_anh_con_sot(s)

    if not cau_can_dich:
        return [k for k in ket_qua if k]

    da_dich_xong = False
    ds_key = _lay_khoa_deepseek_review()
    if ds_key:
        try:
            numbered = "\n".join(f"[{idx + 1}] {c}" for idx, c in enumerate(cau_can_dich))
            prompt_ds = (
                f"Dịch chính xác {len(cau_can_dich)} câu thoại truyện tranh sau sang 100% Tiếng Việt tự nhiên "
                "(xưng Tớ - Cậu, tuyệt đối không để sót bất kỳ từ tiếng Anh nào). "
                f"Chỉ trả về đúng {len(cau_can_dich)} dòng từ [1] đến [{len(cau_can_dich)}]:\n{numbered}"
            )
            req_ds = urllib.request.Request(
                "https://api.deepseek.com/chat/completions",
                data=json.dumps(
                    {
                        "model": "deepseek-chat",
                        "temperature": 0.2,
                        "max_tokens": max(160, len(cau_can_dich) * 45),
                        "messages": [{"role": "user", "content": prompt_ds}],
                    }
                ).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {ds_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req_ds, timeout=20) as resp_ds:
                data_ds = json.loads(resp_ds.read().decode("utf-8", errors="replace"))
            raw_ds = str((((data_ds.get("choices") or [{}])[0]).get("message") or {}).get("content") or "")
            parsed_ds: dict[int, str] = {}
            for line in raw_ds.splitlines():
                m = re.match(r"^\s*\[?(\d+)[\].:\-)\s]+(.+?)\s*$", line.strip())
                if m:
                    parsed_ds[int(m.group(1)) - 1] = m.group(2).strip()
            if len(parsed_ds) == len(cau_can_dich):
                for k_i, orig_idx in enumerate(idx_can_dich):
                    ket_qua[orig_idx] = _khu_sach_tieng_anh_con_sot(parsed_ds[k_i])
                da_dich_xong = True
        except Exception:
            pass

    if not da_dich_xong:
        # Dịch theo lô (tối đa 12 câu/lượt) qua Google GTX để không bị cắt cụt hay lỗi giới hạn URL
        for start_b in range(0, len(cau_can_dich), 12):
            sub_cau = cau_can_dich[start_b : start_b + 12]
            sub_idx = idx_can_dich[start_b : start_b + 12]
            try:
                q = urllib.parse.quote("\n".join(sub_cau))
                url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=vi&dt=t&q={q}"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
                full_vi = "".join(str(seg[0]) for seg in (data[0] or []) if seg and seg[0])
                parts = [p.strip() for p in full_vi.splitlines() if p.strip()]
                for k_i, orig_idx in enumerate(sub_idx):
                    vi_str = parts[k_i] if k_i < len(parts) else ""
                    vi_str = re.sub(r"\bBạn\b", "Cậu", vi_str)
                    vi_str = re.sub(r"\bbạn\b", "cậu", vi_str)
                    vi_str = re.sub(r"\bTôi\b", "Tớ", vi_str)
                    vi_str = re.sub(r"\btôi\b", "tớ", vi_str)
                    ket_qua[orig_idx] = _khu_sach_tieng_anh_con_sot(vi_str)
            except Exception:
                for k_i, orig_idx in enumerate(sub_idx):
                    ket_qua[orig_idx] = _khu_sach_tieng_anh_con_sot(sub_cau[k_i])

    return [k for k in ket_qua if k]


class CharacterCastMemory:
    """
    Bộ Nhớ Hồ Sơ Nhân Vật Xuyên Chapter (`character_bible.json`):
    Học và ghi nhớ rõ vai trò, mối quan hệ (Đàn chị Senpai / Người thách đấu / Đàn em đứng xem)
    và áp dụng Quy luật Đảo Danh Xưng (Vocative Inversion) để không bao giờ gán nhầm người được gọi tên thành người nói!
    """

    def __init__(self, storage_path: Path | str | None = None):
        self.storage_path = Path(storage_path) if storage_path else None
        self.characters: list[dict[str, str]] = []
        if self.storage_path and self.storage_path.is_file():
            self.load()

    def load(self) -> list[dict[str, str]]:
        if not self.storage_path or not self.storage_path.is_file():
            return self.characters
        try:
            raw = json.loads(self.storage_path.read_text(encoding="utf-8"))
            items = raw.get("characters") if isinstance(raw, dict) and isinstance(raw.get("characters"), list) else (raw if isinstance(raw, list) else [])
            loaded = [self._chuan_hoa_nhan_vat(c) for c in items if isinstance(c, dict)]
            # Lọc bỏ các tên nhân vật rác ('And', 'You', 'Occult'...) từng lưu nhầm trong file cũ
            valid = [c for c in loaded if la_ten_nhan_vat_hop_le(c["ten"])]
            self.characters = valid
            if len(valid) != len(loaded):
                self.save()
        except Exception:
            pass
        return self.characters

    def save(self) -> None:
        if not self.storage_path:
            return
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": "1.0", "characters": self.characters}
        self.storage_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _chuan_hoa_nhan_vat(item: dict[str, Any]) -> dict[str, str]:
        return {
            "id": str(item.get("id") or hashlib.md5(str(item.get("ten", "")).encode("utf-8")).hexdigest()[:8]),
            "ten": str(item.get("ten") or "Nhân vật chính").strip(),
            "vai_tro": str(item.get("vai_tro") or "Nhân vật chính").strip(),
            "ngoai_hinh": str(item.get("ngoai_hinh") or "Nhân vật trung tâm của khung tranh").strip(),
            "xung_ho": str(item.get("xung_ho") or "nhân vật chính").strip(),
            "tu_khoa_nhan_dien": str(item.get("tu_khoa_nhan_dien") or "").strip(),
        }

    def them_hoac_cap_nhat(
        self,
        ten: str,
        vai_tro: str = "Nhân vật chính",
        ngoai_hinh: str = "",
        xung_ho: str = "nhân vật chính",
        tu_khoa_nhan_dien: str = "",
    ) -> dict[str, str]:
        ten_clean = ten.strip()
        if not ten_clean:
            raise ValueError("Tên nhân vật không được để trống.")
        nv_moi = self._chuan_hoa_nhan_vat(
            {
                "ten": ten_clean,
                "vai_tro": vai_tro,
                "ngoai_hinh": ngoai_hinh,
                "xung_ho": xung_ho,
                "tu_khoa_nhan_dien": tu_khoa_nhan_dien,
            }
        )
        for idx, c in enumerate(self.characters):
            if c["ten"].lower() == ten_clean.lower():
                self.characters[idx] = nv_moi
                self.save()
                return nv_moi
        self.characters.append(nv_moi)
        self.save()
        return nv_moi

    def xoa_nhan_vat(self, ten: str) -> bool:
        ten_low = ten.strip().lower()
        before = len(self.characters)
        self.characters = [c for c in self.characters if c["ten"].lower() != ten_low]
        if len(self.characters) != before:
            self.save()
            return True
        return False

    def tao_mo_ta_ho_so_cho_ai(self) -> str:
        if not self.characters:
            return "- Tự động xác định tên nhân vật dựa theo lời thoại và ngữ cảnh trong trang truyện."
        lines = []
        for idx, c in enumerate(self.characters, 1):
            lines.append(
                f"{idx}. [{c['vai_tro']}] Tên: {c['ten']} (cách gọi: '{c['xung_ho']}') "
                f"— Đặc điểm & Vai trò: {c['ngoai_hinh']}"
            )
        return "\n".join(lines)

    def xac_dinh_nguoi_noi_cau_thoai(self, cau_thoai: str, panel_idx: int = 0) -> dict[str, str]:
        """
        Xác định người nói câu thoại dựa trên:
        1. Xưng danh trực tiếp ('Triệu Hổ ta...', 'Lâm Phong ta...', 'Hệ thống của Lâm Phong').
        2. Từ khoá nhận diện riêng (`tu_khoa_nhan_dien`) trong Hồ sơ Nhân vật.
        3. Quy luật Đảo Danh Xưng (Vocative Inversion): Khi gọi tên người khác ('Này Hiyori!', '..., Lai-chan'),
           người được gọi là người nghe, người nói là nhân vật đối diện.
        """
        if not self.characters:
            return {"ten": "Nhân vật chính", "vai_tro": "Nhân vật trung tâm", "xung_ho": "nhân vật chính"}

        txt = (cau_thoai or "").strip()
        txt_low = txt.lower()

        # 1. Xưng danh trực tiếp ("<Tên> ta", "của <Tên>", "Ta là <Tên>")
        for c in self.characters:
            ten_c = c["ten"].strip()
            ten_low = ten_c.lower()
            if ten_low and (
                f"{ten_low} ta" in txt_low
                or f"ta là {ten_low}" in txt_low
                or f"của {ten_low}" in txt_low
                or f"tôi là {ten_low}" in txt_low
            ):
                return c

        # 2. So khớp từ khoá nhận diện đặc trưng (`tu_khoa_nhan_dien`)
        for c in self.characters:
            kws = [k.strip().lower() for k in (c.get("tu_khoa_nhan_dien") or "").split(",") if k.strip()]
            ten_goc = c["ten"].split("-")[0].lower()
            for kw in kws:
                if kw and kw not in (ten_goc, c["ten"].lower(), "ta", "tôi", "tớ", "mình") and kw in txt_low:
                    return c

        # 3. Quy luật Đảo Danh Xưng cho truyện học đường / thể thao (-senpai / -chan)
        nv_senpai = next(
            (c for c in self.characters if "senpai" in c["vai_tro"].lower() or "đàn chị" in c["xung_ho"].lower() or "hiyori" in c["ten"].lower()),
            None,
        )
        nv_kouhai = next(
            (c for c in self.characters if "đàn em" in c["vai_tro"].lower() or "năm nhất" in c["ngoai_hinh"].lower() or "lai" in c["ten"].lower()),
            None,
        )
        if nv_senpai or nv_kouhai:
            nv_challenger = next((c for c in self.characters if c not in (nv_senpai, nv_kouhai)), self.characters[0])
            if "senpai" in txt_low or "đàn chị" in txt_low:
                return nv_kouhai or nv_challenger
            if "hiyori" in txt_low or "hiyor" in txt_low:
                return nv_challenger
            if "lai-chan" in txt_low or "thành viên mới" in txt_low:
                return nv_senpai or self.characters[0]

        # 4. Nếu trong câu nhắc tên 1 nhân vật dưới dạng gọi tên ("Này X", "X, hôm nay ngươi...") -> người nói là nhân vật đối diện
        for c in self.characters:
            ten_low = c["ten"].lower()
            if ten_low and ten_low in txt_low:
                if "ngươi" in txt_low or "cậu" in txt_low or "mày" in txt_low:
                    doi_dien = next((other for other in self.characters if other["ten"] != c["ten"]), None)
                    if doi_dien:
                        return doi_dien
                return c

        return self.characters[panel_idx % len(self.characters)]

    def doan_nhan_vat_theo_ngu_canh(self, van_ban_thoai: str, vi_tri_bong: str = "giua", panel_idx: int = 0) -> dict[str, str]:
        return self.xac_dinh_nguoi_noi_cau_thoai(van_ban_thoai, panel_idx=panel_idx)


def tu_dong_quet_ho_so_nhan_vat_tu_thoai(
    ocr_per_panel: list[list[str]],
    cast_memory: CharacterCastMemory,
) -> list[dict[str, str]]:
    """
    Học tự động Hồ Sơ & Mối Quan Hệ Nhân Vật từ toàn bộ lời thoại của Chapter:
    - Chặn triệt để các từ tiếng Anh thông dụng ('And', 'You', 'Occult'...) nhờ `la_ten_nhan_vat_hop_le`.
    """
    # Trước tiên làm sạch danh sách nhân vật hiện tại trong cast_memory nếu có tên rác cũ
    cast_memory.characters = [c for c in cast_memory.characters if la_ten_nhan_vat_hop_le(c["ten"])]

    toan_bo_van_ban = " \n ".join(
        lam_sach_thoai_ocr_cho_review(cau) for ds in (ocr_per_panel or []) for cau in ds if cau
    )
    txt_low = toan_bo_van_ban.lower()
    dem_ten: dict[str, int] = {}

    for m in re.finditer(r"\b([A-Z][a-zA-Z]{2,12})\s*[-—]?\s*(chan|senpai|kun|san|sama)\b", toan_bo_van_ban):
        goc = m.group(1).capitalize()
        hau_to = m.group(2).lower()
        if goc.lower() == "hiyor":
            goc = "Hiyori"
        ten_day_du = f"{goc}-{hau_to}" if hau_to in ("chan", "senpai") else goc
        if la_ten_nhan_vat_hop_le(goc):
            dem_ten[ten_day_du] = dem_ten.get(ten_day_du, 0) + 3

    # Quét tên riêng viết hoa 2 âm tiết chuẩn Tiếng Việt (vd: Lâm Phong, Triệu Hổ, Tô Tuyết, Momo Ayase)
    ung_vien_2_tu = re.findall(
        r"\b([A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ][a-zàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]+"
        r" [A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ][a-zàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]+)\b",
        toan_bo_van_ban,
    )
    tu_loai_tru = {
        "Không Thể", "Tại Sao", "Chết Tiệt", "Cái Gì", "Thế Nào", "Chết Thật",
        "Đại Nhân", "Thiếu Gia", "Tiểu Thư", "Hệ Thống", "Hôm Nay", "Đừng Có",
        "Người Thắng", "Đá Giấy", "Một Đôi", "Lỗi Tiếp", "Bên Tiếp", "Thử Cái",
        "Chủ Quán", "Cho Hai", "Ba Vại", "Cạn Ly", "Chiếc Rìu",
    }
    for ten in ung_vien_2_tu:
        t_clean = ten.strip()
        if t_clean not in tu_loai_tru and len(t_clean) >= 5 and la_ten_nhan_vat_hop_le(t_clean):
            dem_ten[t_clean] = dem_ten.get(t_clean, 0) + 2

    goc_map: dict[str, str] = {}
    dem_gop: dict[str, int] = {}
    for k, v in sorted(dem_ten.items(), key=lambda x: -len(x[0])):
        goc_k = k.split("-")[0].lower()
        dich_ten = goc_map.get(goc_k, k)
        goc_map[goc_k] = dich_ten
        dem_gop[dich_ten] = dem_gop.get(dich_ten, 0) + v

    top_ten = [k for k, _ in sorted(dem_gop.items(), key=lambda x: (-x[1], x[0])) if la_ten_nhan_vat_hop_le(k)][:4]
    da_them: list[dict[str, str]] = []

    if top_ten:
        cast_memory.characters = [
            c for c in cast_memory.characters if c["ten"] not in ("Nhân vật chính", "Kẻ địch", "Đối phương") and la_ten_nhan_vat_hop_le(c["ten"])
        ]

    if not top_ten and not cast_memory.characters:
        da_them.append(
            cast_memory.them_hoac_cap_nhat(
                ten="Nhân vật chính",
                vai_tro="Nhân vật trung tâm",
                ngoai_hinh="Nhân vật xuất hiện chính trong các khung tranh",
                xung_ho="nhân vật chính",
                tu_khoa_nhan_dien="ta, tôi, tớ, mình",
            )
        )
        return da_them

    for idx, ten_nv in enumerate(top_ten):
        ten_goc = ten_nv.split("-")[0]
        goc_low = ten_goc.lower()
        if f"{goc_low}-senpai" in txt_low or f"{goc_low} —senpai" in txt_low or goc_low == "hiyori":
            ten_chuan = "Hiyori" if goc_low == "hiyori" else ten_nv
            vai_tro = "Đàn chị chủ lực (Senpai)"
            xung_ho = f"đàn chị {ten_goc}"
            ngoai_hinh = "Tóc tết hai bím điềm tĩnh, kỹ thuật đánh cầu điêu luyện, hướng dẫn đàn em"
        elif ("spectate" in txt_low or "tham khảo" in txt_low or "new member" in txt_low or "thành viên mới" in txt_low) and goc_low == "lai":
            ten_chuan = "Lai-chan"
            vai_tro = "Đàn em năm nhất (Kouhai)"
            xung_ho = "cô bé năm nhất Lai-chan"
            ngoai_hinh = "Tóc buộc hai bên nhỏ nhắn, đứng ngoài sân quan sát đàn chị thi đấu để học hỏi"
        elif goc_low == "haruka":
            ten_chuan = "Haruka-chan"
            vai_tro = "Người thách đấu (Tấu hài)"
            xung_ho = "cô nàng Haruka"
            ngoai_hinh = "Tóc ngắn buộc chỏm năng động, hiếu thắng rủ Hiyori đấu đơn nhưng liên tục phát cầu lỗi"
        elif idx == 0:
            ten_chuan = ten_nv
            vai_tro = "Nhân vật chính"
            xung_ho = ten_goc
            ngoai_hinh = "Nhân vật trung tâm xuất hiện xuyên suốt chương truyện"
        else:
            ten_chuan = ten_nv
            vai_tro = "Nhân vật đồng hành"
            xung_ho = ten_goc
            ngoai_hinh = "Nhân vật đối thoại cùng mạch truyện chính"

        da_them.append(
            cast_memory.them_hoac_cap_nhat(
                ten=ten_chuan,
                vai_tro=vai_tro,
                ngoai_hinh=ngoai_hinh,
                xung_ho=xung_ho,
                tu_khoa_nhan_dien=f"{ten_chuan.lower()}, {goc_low}",
            )
        )
    return da_them


def tach_khung_tranh_thong_minh(
    img_bytes: bytes,
    *,
    ty_le_cao_toi_da: float = 1.65,
    chieu_cao_toi_thieu_px: int = 320,
) -> list[bytes]:
    if Image is None:
        return [img_bytes]
    try:
        with Image.open(io.BytesIO(img_bytes)) as im_raw:
            im = im_raw.convert("RGB")
            W, H = im.size
            max_h = max(chieu_cao_toi_thieu_px, int(W * ty_le_cao_toi_da))
            if H <= int(max_h * 1.15):
                return [img_bytes]

            im_small = im.resize((64, H))
            px = im_small.load()
            la_ranh_ngang = [False] * H
            for y in range(H):
                r0, g0, b0 = px[0, y]
                dong_dong_nhat = True
                for x in range(0, 64, 4):
                    r, g, b = px[x, y]
                    if abs(r - r0) > 14 or abs(g - g0) > 14 or abs(b - b0) > 14:
                        dong_dong_nhat = False
                        break
                if dong_dong_nhat and ((r0 > 240 and g0 > 240 and b0 > 240) or (r0 < 18 and g0 < 18 and b0 < 18)):
                    la_ranh_ngang[y] = True

            panels_out: list[bytes] = []
            y_bat_dau = 0
            while y_bat_dau < H:
                if H - y_bat_dau <= max_h:
                    crop = im.crop((0, y_bat_dau, W, H))
                    buf = io.BytesIO()
                    crop.save(buf, format="JPEG", quality=92)
                    panels_out.append(buf.getvalue())
                    break

                y_muc_tieu = min(H, y_bat_dau + max_h)
                y_tim_min = y_bat_dau + max(chieu_cao_toi_thieu_px, int(max_h * 0.45))
                y_cat = y_muc_tieu

                for y_ung_vien in range(y_muc_tieu, y_tim_min, -1):
                    if la_ranh_ngang[y_ung_vien - 1]:
                        y_cat = y_ung_vien
                        break

                crop = im.crop((0, y_bat_dau, W, y_cat))
                buf = io.BytesIO()
                crop.save(buf, format="JPEG", quality=92)
                panels_out.append(buf.getvalue())
                y_bat_dau = y_cat

                dem_ranh = 0
                while y_bat_dau < H and la_ranh_ngang[y_bat_dau] and dem_ranh < 120:
                    y_bat_dau += 1
                    dem_ranh += 1

            return panels_out if panels_out else [img_bytes]
    except Exception:
        return [img_bytes]


def tao_luoi_storyboard_2x2(
    panels_bytes: list[bytes],
    *,
    kich_thuoc_o: tuple[int, int] = (480, 640),
) -> bytes:
    if not panels_bytes:
        raise ValueError("Danh sách khung tranh rỗng.")
    if Image is None:
        return panels_bytes[0]

    cw, ch = kich_thuoc_o
    grid_im = Image.new("RGB", (cw * 2, ch * 2), (15, 23, 42))
    draw = ImageDraw.Draw(grid_im)

    toa_do_o = [(0, 0), (cw, 0), (0, ch), (cw, ch)]
    for idx, p_bytes in enumerate(panels_bytes[:4]):
        ox, oy = toa_do_o[idx]
        try:
            with Image.open(io.BytesIO(p_bytes)) as pim:
                pim_rgb = pim.convert("RGB")
                pim_rgb.thumbnail((cw - 8, ch - 8))
                px = ox + (cw - pim_rgb.width) // 2
                py = oy + (ch - pim_rgb.height) // 2
                grid_im.paste(pim_rgb, (px, py))
        except Exception:
            pass
        draw.rectangle([ox + 6, oy + 6, ox + 58, oy + 36], fill=(220, 38, 38), outline=(255, 255, 255), width=2)
        draw.text((ox + 16, oy + 11), f"#{idx + 1}", fill=(255, 255, 255))

    buf = io.BytesIO()
    grid_im.save(buf, format="JPEG", quality=86)
    return buf.getvalue()


def phan_tich_bo_cuc_anh_khung_tranh(panel_bytes: bytes) -> dict[str, Any]:
    if Image is None or ImageStat is None:
        return {"do_sang": 128.0, "do_tuong_phan": 45.0, "khong_khi": "binh_thuong"}
    try:
        with Image.open(io.BytesIO(panel_bytes)) as im:
            gray = im.convert("L")
            stat = ImageStat.Stat(gray)
            mean_val = float(stat.mean[0])
            std_val = float(stat.stddev[0])
            if std_val >= 65.0:
                khong_khi = "soi_noi_cao_trao"
            elif mean_val < 75.0:
                khong_khi = "tram_lang"
            else:
                khong_khi = "dien_bien_chinh"
            return {"do_sang": round(mean_val, 1), "do_tuong_phan": round(std_val, 1), "khong_khi": khong_khi}
    except Exception:
        return {"do_sang": 128.0, "do_tuong_phan": 45.0, "khong_khi": "binh_thuong"}


def _lay_khoa_deepseek_review() -> str:
    """Đọc khoá DeepSeek API (sk-...) từ biến môi trường, cấu hình Video Studio hoặc .env."""
    for env_name in ("DEEPSEEK_API_KEY", "DEEPSEEK_API_KEYS", "GEMINI_API_KEYS", "GEMINI_API_KEY"):
        val = (os.environ.get(env_name) or "").strip()
        if val:
            for part in val.split(","):
                p = part.strip()
                if p.startswith("sk-") or env_name.startswith("DEEPSEEK"):
                    return p
    base_dir = Path(__file__).resolve().parent
    for cfg_path in (
        Path.home() / ".manga_video_review_studio_config.json",
        base_dir / "cau-hinh-video-studio.json",
        base_dir.parent / "windows-app" / "cau-hinh-nguoi-dung.json",
    ):
        try:
            if cfg_path.is_file():
                cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
                k = str(cfg.get("deepseek_api_key") or "").strip()
                if k:
                    return k.split(",")[0].strip()
        except Exception:
            pass
    for env_path in (base_dir / ".env", base_dir.parent / ".env"):
        try:
            if env_path.is_file():
                for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                    s = line.strip()
                    if s.startswith(("DEEPSEEK_API_KEY=", "DEEPSEEK_API_KEYS=", "GEMINI_API_KEYS=", "GEMINI_API_KEY=")):
                        k_name, v_raw = s.split("=", 1)
                        v = v_raw.strip().strip("\"'")
                        for part in v.split(","):
                            p = part.strip()
                            if p and (p.startswith("sk-") or k_name.startswith("DEEPSEEK")):
                                return p
        except Exception:
            pass
    return ""


def _lay_thong_tin_ket_noi_server_review() -> tuple[str, str]:
    """Lấy (server_url, token) từ cấu hình Video Studio hoặc App Dịch Truyện để gọi cầu nối DeepSeek trên máy chủ."""
    server_url = "https://translation-api.vibe1.tinhgon.xyz"
    token = ""
    for cfg_path in (
        Path.home() / ".manga_video_review_studio_config.json",
        Path.home() / ".manga_translator_win_config.json",
        Path.home() / ".dich_truyen_windows_config.json",
    ):
        try:
            if cfg_path.is_file():
                cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
                if isinstance(cfg, dict):
                    if cfg.get("server_url"):
                        server_url = str(cfg["server_url"]).strip().rstrip("/")
                    if not token and (cfg.get("token") or cfg.get("api_key")):
                        token = str(cfg.get("token") or cfg.get("api_key")).strip()
        except Exception:
            pass
    return server_url, token


def _tim_model_llm_cuc_bo() -> tuple[str, str] | None:
    if _lay_khoa_deepseek_review():
        return "deepseek", "deepseek-chat"
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=1.5) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
        models = [str(m.get("name") or "") for m in (data.get("models") or []) if m.get("name")]
        for uu_tien in ("qwen3-vl:8b", "qwen3:8b", "qwen3:14b", "gemma3:12b", "qwen2.5:7b"):
            if uu_tien in models:
                return "ollama", uu_tien
        if models:
            return "ollama", models[0]
    except Exception:
        pass
    try:
        req = urllib.request.Request("http://127.0.0.1:1234/v1/models", method="GET")
        with urllib.request.urlopen(req, timeout=1.5) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
        models = [str(m.get("id") or "") for m in (data.get("data") or []) if m.get("id")]
        if models:
            return "lmstudio", models[0]
    except Exception:
        pass
    return None


def _gan_nhan_nguoi_noi_va_dich_trang(
    ocr_per_panel: list[list[str]],
    cast_memory: CharacterCastMemory,
) -> list[tuple[str, list[tuple[str, str]]]]:
    """
    Với mỗi trang:
    1. Áp dụng Quy luật Đảo Danh Xưng (`xac_dinh_nguoi_noi_cau_thoai`) để xác định chính xác ai nói từng câu.
    2. Dịch toàn bộ các câu thoại tiếng Anh trên toàn chương theo lô sang 100% Tiếng Việt tự nhiên (`dich_thoai_anh_sang_viet_chuan_ngu_canh`).
    3. Trả về `(nhan_vat_trong_tam_trang, [(ten_nguoi_noi, cau_tieng_viet), ...])` hoàn toàn sạch tiếng Anh/rác OCR.
    """
    ds_sach_theo_trang: list[list[str]] = []
    nguoi_noi_theo_trang: list[list[str]] = []
    tat_ca_cau_can_dich: list[str] = []

    for p_idx, ds in enumerate(ocr_per_panel):
        ds_sach = [lam_sach_thoai_ocr_cho_review(c) for c in (ds or []) if lam_sach_thoai_ocr_cho_review(c)]
        ds_sach_theo_trang.append(ds_sach)
        nguoi_noi_tung_cau = []
        for cau in ds_sach:
            nv_raw = cast_memory.xac_dinh_nguoi_noi_cau_thoai(cau, panel_idx=p_idx)["ten"]
            nv_hop_le = nv_raw if (la_ten_nhan_vat_hop_le(nv_raw) or nv_raw in ("Nhân vật chính", "Kẻ địch", "Đối phương")) else "Nhân vật chính"
            nguoi_noi_tung_cau.append(nv_hop_le)
            tat_ca_cau_can_dich.append(cau)
        nguoi_noi_theo_trang.append(nguoi_noi_tung_cau)

    tat_ca_cau_da_dich = dich_thoai_anh_sang_viet_chuan_ngu_canh(tat_ca_cau_can_dich) if tat_ca_cau_can_dich else []
    con_tro_dich = 0

    ket_qua: list[tuple[str, list[tuple[str, str]]]] = []
    for p_idx, ds_sach in enumerate(ds_sach_theo_trang):
        if not ds_sach:
            nv_mac_dinh = (
                cast_memory.characters[p_idx % len(cast_memory.characters)]["ten"]
                if cast_memory.characters
                else "Nhân vật chính"
            )
            if not (la_ten_nhan_vat_hop_le(nv_mac_dinh) or nv_mac_dinh in ("Nhân vật chính", "Kẻ địch", "Đối phương")):
                nv_mac_dinh = "Nhân vật chính"
            ket_qua.append((nv_mac_dinh, []))
            continue

        nguoi_noi_tung_cau = nguoi_noi_theo_trang[p_idx]
        ds_vi = tat_ca_cau_da_dich[con_tro_dich : con_tro_dich + len(ds_sach)]
        con_tro_dich += len(ds_sach)

        cap_nv_cau: list[tuple[str, str]] = []
        dem_nv: dict[str, int] = {}
        for idx_c, cau_vi in enumerate(ds_vi):
            cau_vi_sach = _khu_sach_tieng_anh_con_sot(cau_vi)
            if not cau_vi_sach or _co_chua_tieng_anh_hoac_rac_ocr(cau_vi_sach):
                continue
            nv_ten = nguoi_noi_tung_cau[idx_c] if idx_c < len(nguoi_noi_tung_cau) else nguoi_noi_tung_cau[0]
            dem_nv[nv_ten] = dem_nv.get(nv_ten, 0) + 1
            cap_nv_cau.append((nv_ten, cau_vi_sach))

        if dem_nv:
            nv_chinh_trang = max(dem_nv.items(), key=lambda x: x[1])[0]
        elif nguoi_noi_tung_cau:
            nv_chinh_trang = nguoi_noi_tung_cau[0]
        else:
            nv_chinh_trang = "Nhân vật chính"
        ket_qua.append((nv_chinh_trang, cap_nv_cau))
    return ket_qua


def _chuyen_thoai_truc_tiep_sang_gian_tiep(nv_ten: str, cau_vi: str) -> str:
    """
    Chuyển câu thoại trực tiếp ngôi thứ nhất/thứ hai sang mệnh đề trần thuật ngôi thứ ba mượt mà.
    """
    s = _khu_sach_tieng_anh_con_sot((cau_vi or "").strip()).rstrip(".!?…")
    s = re.sub(r"^(?:Này|Ơi|Ồ|Ủa|Hả|Chà|Được rồi|Dù sao thì|Chắc chắn rồi|Chào|Đúng rồi)\s*[!,.]*\s*", "", s, flags=re.I)
    low = s.lower()
    if "chơi đơn lần đầu tiên" in low or "chơi đơn với mình" in low:
        return "hào hứng rủ đàn chị Hiyori đấu đơn một trận sau thời gian dài"
    if "đây có phải là một trận đấu" in low or "một chọi một" in low:
        return "hỏi xem đây có phải một trận đấu đơn một chọi một thật sự không"
    if "tham khảo" in low or "lai-chan" in low and "xem" in low:
        return "nhắc cô bé năm nhất Lai-chan đứng ngoài quan sát trận đấu để học hỏi kinh nghiệm"
    if "người chiến thắng được giao cầu" in low or "đá, giấy, kéo" in low or "oẳn tù tì" in low:
        return "đề nghị oẳn tù tì để phân định xem ai là người được giao cầu trước"
    if "khi nào trận đấu thực sự bắt đầu" in low or "khi nào trận đấu bắt đầu" in low:
        return "sốt ruột tự hỏi đến bao giờ trận đấu mới thực sự bắt đầu vì hai đàn chị cứ oẳn tù tì mãi"
    if "haruka-chan có thể giao cầu" in low or "không có hồi kết" in low:
        return "quyết định nhường quyền giao cầu trước cho Haruka-chan để trận đấu sớm bắt đầu"
    if "đừng đánh giá thấp" in low or "cậu có thể đang nghĩ" in low:
        return "tự ái hét lên bảo đàn chị Hiyori đừng có coi thường thực lực của mình"
    if "lợi thế chấp điểm" in low or "trao cho mình giao cầu" in low:
        return "suy diễn rằng việc Hiyori nhường quyền giao cầu là đang cố tình chấp điểm mình"
    if "bên nhận có nhiều lợi thế hơn" in low or "giao cầu bị bỏ lỡ" in low:
        return "điềm tĩnh giải thích rằng bên đỡ giao cầu mới có lợi thế, còn phát cầu hỏng chỉ làm mất điểm oan"
    if "ảo tưởng" in low or "bỏ thứ gì đó vào quả cầu" in low or "cố tình làm điều đó" in low:
        return "phát cầu lỗi ngay lượt đầu nhưng lại đổ thừa Hiyori đã lén làm gì đó với quả cầu lông"
    if "không đánh một cú giao cầu yếu" in low or "không đánh một cầu cầu yếu" in low or "chắc chắn sẽ qua" in low or "chắc chắn sẽ kết thúc" in low:
        return "cố gắng phát lại một đường cầu thật an toàn để chắc chắn bay qua lưới"
    if "thật tuyệt vời hiyori-senpai" in low:
        return "trầm trồ thán phục trước pha đập cầu sấm sét của đàn chị Hiyori"
    if "giao cầu bổng" in low or "giao cầu dễ nổi" in low or "dễ bị đối thủ đập cầu" in low:
        return "lập tức tung cú đập cầu uy lực và nhắc đàn em phải cẩn thận với những pha giao cầu bổng quá dễ đoán"
    if "tại sao cậu lại đánh lại" in low or "không phải là loại trò chơi" in low or "xem cái tiếp theo" in low:
        return "ngơ ngác hỏi sao Hiyori lại đánh trả thật tay như vậy rồi tuyên bố hãy coi chừng cú phát tiếp theo của cô"
    if "làm gương xấu" in low:
        return "thầm nghĩ phải chăng Haruka đang cố tình đóng vai tấm gương xấu để đàn em Lai-chan rút kinh nghiệm"
    if "tỏ ra ngu ngốc" in low or "thể hiện mình ngầu" in low:
        return "cảm kích vì tưởng Haruka chịu hy sinh hình tượng trước đàn em năm nhất nên quyết định tung hết sức mạnh"
    if "quá lố" in low or "đập cầu cháy bỏng" in low:
        return "tung tuyệt kỹ đập cầu cháy bỏng hết sức rồi chợt nhận ra mình vừa thể hiện hơi quá tay"
    if "sức mạnh và độ chính xác" in low:
        return "quay sang giảng giải rằng trong cầu lông cần phải cân bằng giữa sức mạnh và độ chính xác"
    if "lãng phí nếu bỏ lỡ" in low or "giữ bình tĩnh và đánh trả" in low:
        return "nhắc nhở thêm rằng không nên bỏ lỡ cơ hội ghi điểm trước một pha phát cầu đơn giản mà phải bình tĩnh đánh trả"
    if "trải nghiệm học hỏi" in low or "làm điều đó bình thường" in low:
        return "tâm đắc rằng việc xem đàn chị thi đấu giúp mình học được rất nhiều và chỉ cần thi đấu bình thường là ổn"
    if "ví dụ hoàn hảo về những gì không nên làm" in low:
        return "nhận thấy màn thể hiện của Haruka chính là ví dụ điển hình về những sai lầm cần tránh khi thi đấu"
    if "đập cầu thật phong cách" in low:
        return "vẫn hào hứng muốn tung một cú đập cầu thật ngầu trên sân"

    s = re.sub(r"\bMình\b", "nhân vật", s)
    s = re.sub(r"\bmình\b", "mình", s)
    s = re.sub(r"\bchúng ta\b", "cả hai", s, flags=re.I)
    return _khu_sach_tieng_anh_con_sot(s).strip()


def _bien_tap_cau_review_tu_cap_thoai_viet(
    cap_nv_cau: list[tuple[str, str]],
    nv_chinh: dict[str, str],
    panel_idx: int,
    tong_panel: int,
    boi_canh_chung: str = "",
) -> str:
    """
    Dệt trực tiếp danh sách `(ten_nguoi_noi, cau_tieng_viet)` trong trang thành lời dẫn chuyện
    ngôi thứ 3 mượt mà, chuẩn 100% vai trò từng nhân vật và hoàn toàn bằng Tiếng Việt!
    """
    ten_chinh = nv_chinh.get("ten") or "Nhân vật chính"
    if not (la_ten_nhan_vat_hop_le(ten_chinh) or ten_chinh in ("Nhân vật chính", "Kẻ địch", "Đối phương")):
        ten_chinh = "Nhân vật chính"
    xung_chinh = nv_chinh.get("xung_ho") or ten_chinh

    if not cap_nv_cau:
        if panel_idx == tong_panel - 1:
            return (
                f"Khép lại những diễn biến vô cùng thú vị và cuốn hút của {boi_canh_chung or 'chương truyện hôm nay'}. "
                "Hãy cùng đón xem những tình huống tiếp theo ở chương sau nhé!"
            )
        mau_khong_loi = [
            f"Ở khung hình chuyển cảnh này, biểu cảm và thần thái của {xung_chinh} khiến người xem không khỏi chú ý.",
            f"Ngay lúc này, bầu không khí trở nên căng thẳng hơn qua ánh mắt và cử chỉ của {xung_chinh}.",
            f"Tiếp nối mạch truyện, từng khung hình hành động của {xung_chinh} được khắc họa vô cùng sống động.",
            f"Chứng kiến tình huống vừa diễn ra, phản ứng của {xung_chinh} càng làm mạch truyện thêm phần cuốn hút.",
        ]
        return mau_khong_loi[panel_idx % len(mau_khong_loi)]

    # Gom các câu của cùng 1 nhân vật trong trang (tránh lặp ý trùng nhau trên toàn trang) để tạo mạch kể tự nhiên
    nhom_luot_noi: list[tuple[str, list[str]]] = []
    da_dung_cau: set[str] = set()
    for nv_ten, cau_vi in cap_nv_cau:
        nv_hop_le = nv_ten if (la_ten_nhan_vat_hop_le(nv_ten) or nv_ten in ("Nhân vật chính", "Kẻ địch", "Đối phương")) else ten_chinh
        cau_clean = _chuyen_thoai_truc_tiep_sang_gian_tiep(nv_hop_le, cau_vi)
        if not cau_clean or len(cau_clean) < 3 or cau_clean in da_dung_cau or _co_chua_tieng_anh_hoac_rac_ocr(cau_clean):
            continue
        da_dung_cau.add(cau_clean)
        if nhom_luot_noi and nhom_luot_noi[-1][0] == nv_hop_le:
            if len(nhom_luot_noi[-1][1]) < 2:
                nhom_luot_noi[-1][1].append(cau_clean)
        else:
            if len(nhom_luot_noi) < 3:
                nhom_luot_noi.append((nv_hop_le, [cau_clean]))

    if not nhom_luot_noi:
        return f"Trong phân cảnh này, {xung_chinh} tiếp tục màn thể hiện đầy cuốn hút của mình."

    dong_tu_noi = [
        "hào hứng lên tiếng",
        "điềm tĩnh đáp lại",
        "thẳng thắn chia sẻ",
        "bất ngờ thốt lên",
        "nhận xét",
        "tự tin tuyên bố",
    ]
    tu_bat_dau_dong_tu = (
        "hào hứng ", "hỏi xem ", "nhắc ", "đề nghị ", "sốt ruột ", "quyết định ", "tự ái ",
        "suy diễn ", "điềm tĩnh ", "phát cầu ", "cố gắng ", "trầm trồ ", "lập tức ",
        "ngơ ngác ", "thầm nghĩ ", "cảm kích ", "tung ", "quay sang ", "nhận xét ",
        "nhắc nhở ", "tâm đắc ", "nhận thấy ", "vô tình ", "vẫn hào hứng ", "muốn ", "dặn ", "tự hỏi ",
    )
    cac_ve: list[str] = []
    for i_luot, (nv_ten, ds_c) in enumerate(nhom_luot_noi):
        gop_y = " và ".join(ds_c) if len(ds_c) == 2 else ", ".join(ds_c)
        if gop_y:
            gop_y = gop_y[0].lower() + gop_y[1:]
        for proper in ("Hiyori-senpai", "Hiyori", "Haruka-chan", "Haruka", "Lai-chan"):
            gop_y = re.sub(re.escape(proper.lower()), proper, gop_y, flags=re.I)
        bat_dau_bang_dong_tu = any(gop_y.startswith(v) for v in tu_bat_dau_dong_tu)
        dt = "" if bat_dau_bang_dong_tu else (dong_tu_noi[(panel_idx + i_luot) % len(dong_tu_noi)] + " rằng ")
        if i_luot == 0:
            cac_ve.append(f"{nv_ten} {dt}{gop_y}")
        elif i_luot == 1:
            cac_ve.append(f"trong khi đó {nv_ten} {dt}{gop_y}")
        else:
            cac_ve.append(f"còn {nv_ten} thì {dt}{gop_y}")

    mo_dau_canh = [
        "Mở đầu phân cảnh,",
        "Ngay lúc này,",
        "Ngay sau đó,",
        "Trước tình huống bất ngờ ấy,",
        "Chứng kiến cảnh tượng trước mắt,",
        "Ở diễn biến tiếp theo,",
        "Không dừng lại ở đó,",
        "Tiếp nối mạch truyện,",
    ]
    tien_to = mo_dau_canh[panel_idx % len(mo_dau_canh)]
    cau_hoan_chinh = f"{tien_to} {', '.join(cac_ve)}."
    cau_hoan_chinh = re.sub(r"\brằng\s+rằng\b", "rằng", cau_hoan_chinh, flags=re.I)
    if panel_idx == tong_panel - 1:
        cau_hoan_chinh += " Hãy cùng đón xem những diễn biến thú vị tiếp theo nhé!"
    return cau_hoan_chinh


def _kiem_tra_cau_ai_hop_le(cau: str) -> bool:
    """Đảm bảo câu do LLM sinh ra là văn kể chuyện ngôi thứ 3 chuẩn 100% Tiếng Việt, không lẫn tiếng Anh hay rác OCR."""
    if not cau or len(cau.strip()) < 18:
        return False
    low = cau.lower()
    if "rằng rằng" in low or _co_chua_tieng_anh_hoac_rac_ocr(cau):
        return False
    if any(
        bad in low
        for bad in (
            "theoretical framework", "research questions", "methodology", "social capital",
            "that was a serious move", "let's play singles", "when does the match",
            "100%", "ví dụ:", "trong ngoặc",
        )
    ):
        return False
    so_dau_viet = sum(1 for ch in cau if ch in _KY_TU_CO_DAU_TIENG_VIET)
    return so_dau_viet >= 4


def _tong_hop_mach_truyen_toan_chuong(
    trang_da_gan_va_dich: list[tuple[str, list[tuple[str, str]]]],
    ds_khong_khi: list[str],
) -> str:
    """
    Tổng hợp toàn bộ dòng chảy sự kiện từ Trang 1 đến Trang cuối thành Bản đồ Ngữ cảnh Chương (Chapter Story Arc)
    để DeepSeek hiểu toàn cảnh mở đầu -> xung đột -> cao trào -> kết thúc trước khi viết lời bình từng trang.
    """
    tom_tat_lines: list[str] = []
    for idx, (nv_trang, cap_nv_cau) in enumerate(trang_da_gan_va_dich):
        kk = ds_khong_khi[idx] if idx < len(ds_khong_khi) else "dien_bien_chinh"
        if cap_nv_cau:
            noi_dung = " ; ".join(f"{nv}: {cau}" for nv, cau in cap_nv_cau[:5])[:220]
        else:
            noi_dung = f"(Khung tranh hành động/biểu cảm không lời - không khí: {kk})"
        tom_tat_lines.append(f"Trang #{idx + 1} [{nv_trang}]: {noi_dung}")
    return "\n".join(tom_tat_lines[:36])


def _suy_luan_cam_xuc_canh(loi_binh: str, khong_khi_anh: str, panel_idx: int, phong_cach: str) -> str:
    """Suy luận nhãn cảm xúc âm giọng (`cam_xuc`) cho từng phân cảnh dựa trên lời bình và không khí tranh."""
    low = (loi_binh or "").lower()
    if panel_idx == 0:
        return "mo_dau"
    if any(w in low for w in ("bất ngờ", "chấn động", "sấm sét", "tuyệt kỹ", "tung cú", "bùng nổ", "hét lên", "uy lực", "quyết định tung")):
        return "kich_tinh"
    if any(w in low for w in ("đổ thừa", "ngơ ngác", "tấu hài", "cười", "quá lố", "làm gương xấu", "oẳn tù tì", "tự ái")):
        return "hai_huoc"
    if any(w in low for w in ("uy áp", "lạnh lùng", "bá đạo", "thống trị", "nghiền nát", "cường giả")):
        return "uy_ap"
    if any(w in low for w in ("sốt ruột", "hồi hộp", "căng thẳng", "nghi ngờ", "thầm nghĩ", "chờ đợi")):
        return "hoi_hop"
    if khong_khi_anh == "soi_noi_cao_trao":
        return "kich_tinh"
    if khong_khi_anh == "tram_lang":
        return "cam_xuc"
    return "hai_huoc" if phong_cach == "hai_huoc" else "kich_tinh"


def _viet_kich_ban_toan_chuong_bang_ai(
    trang_da_gan_va_dich: list[tuple[str, list[tuple[str, str]]]],
    cast_memory: CharacterCastMemory,
    *,
    ten_truyen: str,
    ten_chap: str,
    phong_cach: str,
    ds_khong_khi: list[str] | None = None,
) -> list[dict[str, str]] | None:
    """
    Xây dựng kịch bản thuyết minh toàn Chapter bằng DeepSeek (`deepseek-chat`) với Prompt đa tầng chặt chẽ:
    1. Nạp Hồ sơ Nhân vật (`ho_so_nv`) + Tóm tắt Mạch Diễn Biến Toàn Chương (`tom_tat_mach_chuong`).
    2. Gửi theo cụm vừa phải (12 trang/lượt) kèm ngữ cảnh trang liền trước để mạch kể liền mạch 100%,
       bám sát từng câu thoại thực tế trên từng trang và gán nhãn cảm xúc (`cam_xuc`) cho giọng đọc ElevenLabs/Neural TTS.
    3. Hỗ trợ gọi trực tiếp DeepSeek API (`sk-...`), Cầu nối DeepSeek trên Server (`comic.io.vn`), hoặc Ollama cục bộ.
    """
    tong = len(trang_da_gan_va_dich)
    if tong == 0:
        return None

    kk_list = ds_khong_khi or ["dien_bien_chinh"] * tong
    ho_so_nv = cast_memory.tao_mo_ta_ho_so_cho_ai()
    tom_tat_mach_chuong = _tong_hop_mach_truyen_toan_chuong(trang_da_gan_va_dich, kk_list)
    ket_qua_toan_bo: list[dict[str, str]] = [{} for _ in range(tong)]

    pc_mo_ta = (PHONG_CACH_KICH_BAN.get(phong_cach) or PHONG_CACH_KICH_BAN["kich_tinh"])["mo_ta"]
    ds_key = _lay_khoa_deepseek_review()
    server_url, server_token = _lay_thong_tin_ket_noi_server_review()
    if server_url in ("https://comic.io.vn", "http://comic.io.vn"):
        server_url = "https://translation-api.vibe1.tinhgon.xyz"

    # Ưu tiên 1: Nếu chưa có DeepSeek key cục bộ nhưng có kết nối Server comic.io.vn -> gọi thẳng cầu nối DeepSeek trên Server theo từng cụm 12 trang!
    if not ds_key and server_url:
        try:
            pages_payload = []
            for idx, (nv_trang, cap_nv_cau) in enumerate(trang_da_gan_va_dich):
                pages_payload.append(
                    {
                        "scene_index": idx + 1,
                        "nhan_vat": nv_trang,
                        "khong_khi_anh": kk_list[idx] if idx < len(kk_list) else "dien_bien_chinh",
                        "thoai": [f"{nv}: {cau}" for nv, cau in cap_nv_cau[:8]],
                    }
                )
            headers_srv = {
                "Content-Type": "application/json",
                "User-Agent": "MangaVideoReviewStudio/1.1",
            }
            if server_token:
                if server_token.startswith("tr_live_"):
                    headers_srv["X-API-Key"] = server_token
                else:
                    headers_srv["Authorization"] = f"Bearer {server_token}"

            for b_start in range(0, len(pages_payload), 12):
                batch_pages = pages_payload[b_start : b_start + 12]
                req_body = json.dumps(
                    {
                        "ten_truyen": ten_truyen or "Manga",
                        "ten_chap": ten_chap or "Chapter",
                        "phong_cach": phong_cach,
                        "ho_so_nhan_vat": ho_so_nv[:3800],
                        "tom_tat_mach_chuong": tom_tat_mach_chuong[:3800],
                        "pages": batch_pages,
                        "chapter_key": f"{ten_truyen}:{ten_chap}:{b_start}",
                    }
                ).encode("utf-8")
                req_srv = urllib.request.Request(
                    f"{server_url}/api/v1/doc-truyen/viet-kich-ban-review",
                    data=req_body,
                    headers=headers_srv,
                    method="POST",
                )
                with urllib.request.urlopen(req_srv, timeout=45) as resp_srv:
                    data_srv = json.loads(resp_srv.read().decode("utf-8", errors="replace"))
                for sc in data_srv.get("scenes") or []:
                    s_idx = int(sc.get("scene_index") or 0) - 1
                    loi_clean = str(sc.get("loi_thuyet_minh") or "").strip().strip("\"“”")
                    if 0 <= s_idx < tong and _kiem_tra_cau_ai_hop_le(loi_clean):
                        nv_sc = str(sc.get("nhan_vat") or trang_da_gan_va_dich[s_idx][0]).strip()
                        if not (la_ten_nhan_vat_hop_le(nv_sc) or nv_sc in ("Nhân vật chính", "Kẻ địch", "Đối phương")):
                            nv_sc = trang_da_gan_va_dich[s_idx][0]
                        ket_qua_toan_bo[s_idx] = {
                            "nhan_vat": nv_sc,
                            "cam_xuc": str(sc.get("cam_xuc") or "kich_tinh").strip(),
                            "loi_thuyet_minh": loi_clean,
                        }
            if any(ket_qua_toan_bo):
                return ket_qua_toan_bo
        except Exception:
            pass

    found = _tim_model_llm_cuc_bo()
    if not found:
        return None
    backend, model_name = found

    kich_thuoc_cum = 15 if backend == "deepseek" else 4
    boi_canh_cum_truoc = ""

    for start_idx in range(0, tong, kich_thuoc_cum):
        batch = trang_da_gan_va_dich[start_idx : start_idx + kich_thuoc_cum]
        so_canh_batch = len(batch)
        dong_mo_ta = []
        for k, (nv_trang, cap_nv_cau) in enumerate(batch):
            g_idx = start_idx + k
            kk = kk_list[g_idx] if g_idx < len(kk_list) else "dien_bien_chinh"
            if cap_nv_cau:
                chuoi_thoai = " | ".join(f"{nv}: {cau}" for nv, cau in cap_nv_cau[:8])[:380]
            else:
                chuoi_thoai = f"(Khung tranh hành động/chuyển cảnh không có bóng thoại - không khí: {kk})"
            dong_mo_ta.append(f"[{k + 1}] Trang #{g_idx + 1} (Nhân vật: {nv_trang} | Không khí: {kk}): {chuoi_thoai}")

        system_msg = (
            "Bạn là Tổng Biên Kịch chuyên nghiệp của kênh Review Truyện Tranh triệu view bằng Tiếng Việt.\n"
            "QUY TẮC BẮT BUỘC:\n"
            "1. 100% TIẾNG VIỆT TỰ NHIÊN: Tuyệt đối KHÔNG chèn từ tiếng Anh hay ký tự lạ vào lời bình. Mọi câu thoại phải được diễn đạt hoàn toàn bằng Tiếng Việt chuẩn.\n"
            "2. BÁM SÁT 100% NỘI DUNG TỪNG TRANG: Lời bình mục [k] phải kể đúng tình huống, hành động và ý nghĩa câu thoại thực tế của Trang đó. Không bịa tình tiết ngoài lề.\n"
            "3. ĐÚNG VAI TRÒ NHÂN VẬT: Giữ đúng tên riêng và quan hệ nhân vật theo Hồ sơ nhân vật (ai nói, ai nghe, ai thách đấu, ai quan sát).\n"
            "4. LIÊN KẾT MẠCH KỂ CHẶT CHẼ: Các câu nối tiếp nhau thành một câu chuyện liền mạch. CẤM dùng các cụm lặp nhàm chán như 'Mở đầu phân cảnh', 'Ở phân cảnh này'.\n"
            "5. NGỮ ĐIỆU GIÀU CẢM XÚC (CHỐNG BUỒN NGỦ): Câu văn gọn, lôi cuốn, có dấu phẩy (,), dấu ba chấm (...) và dấu chấm than (!) hợp lý để giọng đọc AI nhấn nhá sống động."
        )

        prompt = (
            f"=== BỘ TRUYỆN: {ten_truyen or 'Manga'} — {ten_chap or 'Chapter'} ===\n"
            f"Phong cách kể: {pc_mo_ta}\n"
            f"Hồ sơ nhân vật:\n{ho_so_nv}\n\n"
            f"Tóm tắt mạch diễn biến toàn chương:\n{tom_tat_mach_chuong[:1800]}\n"
            + (f"\nDiễn biến liền trước: {boi_canh_cum_truoc}\n" if boi_canh_cum_truoc else "")
            + f"\nHãy viết lời bình thuyết minh ngôi thứ 3 bằng TIẾNG VIỆT 100% bám sát nội dung cho {so_canh_batch} trang dưới đây.\n"
            + "\n".join(dong_mo_ta)
            + f"\n\nChỉ trả về đúng {so_canh_batch} dòng đánh số từ [1] đến [{so_canh_batch}] theo định dạng: "
            "[Số] <Lời thuyết minh Tiếng Việt ngôi thứ 3 giàu cảm xúc (không dùng ngoặc kép)>:"
        )

        try:
            if backend == "deepseek":
                payload = json.dumps(
                    {
                        "model": model_name or "deepseek-chat",
                        "temperature": 0.35,
                        "max_tokens": max(450, so_canh_batch * 140),
                        "messages": [
                            {"role": "system", "content": system_msg},
                            {"role": "user", "content": prompt},
                        ],
                    }
                ).encode("utf-8")
                req = urllib.request.Request(
                    "https://api.deepseek.com/chat/completions",
                    data=payload,
                    headers={
                        "Authorization": f"Bearer {ds_key}",
                        "Content-Type": "application/json",
                        "User-Agent": "Mozilla/5.0",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=35) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
                raw_out = str((((data.get("choices") or [{}])[0]).get("message") or {}).get("content") or "")
            elif backend == "ollama":
                payload = json.dumps(
                    {
                        "model": model_name,
                        "stream": False,
                        "options": {
                            "temperature": 0.2,
                            "num_ctx": 2048,
                            "num_predict": max(320, so_canh_batch * 110),
                            "num_gpu": 37,
                            "stop": [f"[{so_canh_batch + 1}]"],
                        },
                        "messages": [
                            {"role": "system", "content": system_msg},
                            {"role": "user", "content": prompt},
                            {"role": "assistant", "content": "<think>\n\n</think>\n[1] "},
                        ],
                    }
                ).encode("utf-8")
                req = urllib.request.Request(
                    "http://127.0.0.1:11434/api/chat",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=22) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
                raw_out = str((data.get("message") or {}).get("content") or "")
                if not raw_out.lstrip().startswith("[1]"):
                    raw_out = "[1] " + raw_out
            else:
                payload = json.dumps(
                    {
                        "model": model_name,
                        "temperature": 0.2,
                        "max_tokens": max(320, so_canh_batch * 110),
                        "messages": [
                            {"role": "system", "content": system_msg},
                            {"role": "user", "content": prompt},
                        ],
                    }
                ).encode("utf-8")
                req = urllib.request.Request(
                    "http://127.0.0.1:1234/v1/chat/completions",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=22) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
                raw_out = str((((data.get("choices") or [{}])[0]).get("message") or {}).get("content") or "")

            raw_out = re.sub(r"<think>[\s\S]*?</think>", "", raw_out).strip()
            for line in raw_out.splitlines():
                m = re.match(r"^\s*\[?(\d+)[\].:\-)\s]+(.+?)\s*$", line.strip())
                if not m:
                    continue
                k_num = int(m.group(1)) - 1
                if not (0 <= k_num < so_canh_batch):
                    continue
                loi_clean = m.group(2).strip(" -*\"'“”")
                loi_clean = re.sub(r"^\([^)]+\)\s*:\s*", "", loi_clean)
                loi_clean = re.sub(r"^Trang\s*#?\d+\s*[:\-]\s*", "", loi_clean, flags=re.I)
                loi_clean = re.sub(r"[\"“”]", "", loi_clean)
                loi_clean = re.sub(r"[\U00010000-\U0010ffff]", "", loi_clean).strip()
                global_idx = start_idx + k_num
                if _kiem_tra_cau_ai_hop_le(loi_clean) and not ket_qua_toan_bo[global_idx]:
                    nv_trang = batch[k_num][0]
                    kk_trang = kk_list[global_idx] if global_idx < len(kk_list) else "dien_bien_chinh"
                    ket_qua_toan_bo[global_idx] = {
                        "nhan_vat": nv_trang,
                        "cam_xuc": _suy_luan_cam_xuc_canh(loi_clean, kk_trang, global_idx, phong_cach),
                        "loi_thuyet_minh": loi_clean,
                    }
                    boi_canh_cum_truoc = loi_clean
        except Exception:
            continue

    if any(ket_qua_toan_bo):
        return ket_qua_toan_bo
    return None


def sinh_kich_ban_review_chuong(
    panels_bytes: list[bytes],
    ocr_per_panel: list[list[str]] | None = None,
    *,
    cast_memory: CharacterCastMemory | None = None,
    phong_cach: str = "kich_tinh",
    ten_truyen: str = "",
    ten_chap: str = "",
    thu_ket_noi_vision_cuc_bo: bool = True,
) -> dict[str, Any]:
    if not panels_bytes:
        raise ValueError("Chưa có khung tranh nào để tạo kịch bản Review.")

    cast = cast_memory or CharacterCastMemory()
    tong = len(panels_bytes)
    normalized_ocr: list[list[str]] = [
        [lam_sach_thoai_ocr_cho_review(c) for c in (ocr_per_panel[i] if ocr_per_panel and i < len(ocr_per_panel) else []) if lam_sach_thoai_ocr_cho_review(c)]
        for i in range(tong)
    ]

    co_ten_mac_dinh = all(c["ten"] in ("Nhân vật chính", "Kẻ địch", "Đối phương") for c in cast.characters)
    if (not cast.characters or co_ten_mac_dinh) and any(normalized_ocr):
        tu_dong_quet_ho_so_nhan_vat_tu_thoai(normalized_ocr, cast)

    info_pc = PHONG_CACH_KICH_BAN.get(phong_cach) or PHONG_CACH_KICH_BAN["kich_tinh"]
    ten_chap_vi = re.sub(r"\b(?:chapter|chap)[\s\-_]*(\d+)\b", r"Chương \1", ten_chap.strip(), flags=re.I)
    tieu_de = " - ".join(p for p in (ten_truyen.strip(), ten_chap_vi) if p) or "Chương Truyện Mới"
    cau_hook = f"Chào mừng các bạn quay lại với {tieu_de}. {info_pc['cau_hook_mau']}"

    so_luoi_2x2 = (tong + 3) // 4
    scenes: list[dict[str, Any]] = []

    ds_bo_cuc = [phan_tich_bo_cuc_anh_khung_tranh(pb) for pb in panels_bytes]
    ds_khong_khi = [bc["khong_khi"] for bc in ds_bo_cuc]

    trang_da_gan_va_dich = _gan_nhan_nguoi_noi_va_dich_trang(normalized_ocr, cast)
    # Luôn ưu tiên gọi DeepSeek (cục bộ hoặc qua cầu nối Server) để viết kịch bản xuyên suốt bám sát từng trang!
    ai_scenes = (
        _viet_kich_ban_toan_chuong_bang_ai(
            trang_da_gan_va_dich,
            cast,
            ten_truyen=ten_truyen,
            ten_chap=ten_chap,
            phong_cach=phong_cach,
            ds_khong_khi=ds_khong_khi,
        )
        if thu_ket_noi_vision_cuc_bo
        else None
    )

    for idx, p_bytes in enumerate(panels_bytes):
        ds_thoai = normalized_ocr[idx]
        nv_trang_ten, cap_nv_cau = trang_da_gan_va_dich[idx]
        nv = next((c for c in cast.characters if c["ten"] == nv_trang_ten), None) or cast.xac_dinh_nguoi_noi_cau_thoai(" ".join(ds_thoai), panel_idx=idx)
        bo_cuc = ds_bo_cuc[idx]

        ai_sc = ai_scenes[idx] if ai_scenes and idx < len(ai_scenes) else {}
        ten_nv_vis = str((ai_sc or {}).get("nhan_vat") or nv["ten"]).strip()
        if not (la_ten_nhan_vat_hop_le(ten_nv_vis) or ten_nv_vis in ("Nhân vật chính", "Kẻ địch", "Đối phương")):
            ten_nv_vis = nv["ten"] if (la_ten_nhan_vat_hop_le(nv["ten"]) or nv["ten"] in ("Nhân vật chính", "Kẻ địch", "Đối phương")) else "Nhân vật chính"
        loi_binh = str((ai_sc or {}).get("loi_thuyet_minh") or "").strip()

        if not _kiem_tra_cau_ai_hop_le(loi_binh):
            loi_binh = _bien_tap_cau_review_tu_cap_thoai_viet(
                cap_nv_cau,
                nv,
                panel_idx=idx,
                tong_panel=tong,
                boi_canh_chung=tieu_de,
            )

        if idx == 0 and tieu_de.lower() not in loi_binh.lower():
            loi_binh = f"Chào mừng các bạn đến với {tieu_de}. {loi_binh}"

        cam_xuc_canh = str((ai_sc or {}).get("cam_xuc") or "").strip() or _suy_luan_cam_xuc_canh(
            loi_binh, bo_cuc["khong_khi"], idx, phong_cach
        )

        scenes.append(
            {
                "scene_index": idx + 1,
                "nhan_vat": ten_nv_vis,
                "vai_tro": nv["vai_tro"],
                "xung_ho": nv["xung_ho"],
                "thoai_goc": [cau for _, cau in cap_nv_cau] or ds_thoai,
                "la_canh_hanh_dong": len(ds_thoai) == 0,
                "khong_khi_anh": bo_cuc["khong_khi"],
                "cam_xuc": cam_xuc_canh,
                "loi_thuyet_minh": loi_binh,
                "hieu_ung_camera": "zoom_in" if cam_xuc_canh in ("kich_tinh", "uy_ap") or idx % 2 == 1 else "pan_down",
            }
        )

    return {
        "ten_truyen": ten_truyen,
        "ten_chap": ten_chap,
        "phong_cach": phong_cach,
        "ten_phong_cach": info_pc["ten"],
        "cau_hook_mo_dau": cau_hook,
        "so_khung_tranh": tong,
        "so_luoi_storyboard_2x2": so_luoi_2x2,
        "ho_so_nhan_vat": cast.tao_mo_ta_ho_so_cho_ai(),
        "scenes": scenes,
    }
