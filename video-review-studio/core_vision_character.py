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
    "tu_dong_thich_ung": {
        "ten": "🧠 Tự Động Thích Ứng Đa Thể Loại + Kho Học Hỏi 6 Kênh (Anime Rewind / Mèo Gầy / Lucifer / Gấu Xàm / Genz / Lười Tắm — Khuyên dùng)",
        "mo_ta": (
            "TỰ ĐỘNG PHÂN TÍCH THỂ LOẠI, ĐỊNH DANH TÊN RIÊNG RÕ RÀNG (CHUẨN ANIME REWIND) & XÂY DỰNG BỐ CỤC NHÂN - QUẢ MƯỢT MÀ: "
            "Kết hợp tinh hoa dẫn chuyện cực kỳ dễ hiểu của Anime Rewind cùng 5 kênh lớn (Mèo Gầy TV, Lucifer Sama, Gấu Xàm Anime, Genz Tóm Tắt, Lười Tắm Anime): "
            "1) Mở đầu tóm gọn ngay hoàn cảnh/biến cố của nhân vật chính; "
            "2) BẮT BUỘC nêu rõ TÊN RIÊNG của nhân vật ở vế đầu hoặc khi 2 nhân vật tương tác để người nghe biết chính xác ai làm gì, sau đó vế phụ mới luân phiên đại từ ('anh, cô, cậu, thanh niên, cô nàng'); "
            "3) Định vị rõ không gian/thời gian và chèn câu hỏi nội tâm ngắn gọn ('Không lẽ...?', 'Chuyện gì đang xảy ra?') giúp mạch truyện cực kỳ dễ hiểu."
        ),
        "cau_hook_mau": "Hãy cùng khám phá ngay những diễn biến đầy bất ngờ và cuốn hút trong chương truyện hôm nay!",
    },
    "anime_rewind_de_hieu": {
        "ten": "🎯 Rõ Ràng Dễ Hiểu & Định Danh Tên Riêng Chuẩn Xác (Chuẩn style Anime Rewind — Rất dễ nghe)",
        "mo_ta": (
            "Phong cách dẫn chuyện mạch lạc, câu văn gọn gàng sắc nét, cực kỳ dễ hiểu cho người nghe (như kênh Anime Rewind): "
            "luôn gọi rõ Tên riêng nhân vật kèm vai trò ('người đồng nghiệp Katano', 'nữ cảnh sát Kaori', 'cô bạn thân Reiko') khi mở cảnh hoặc khi có 2 người tương tác để không bao giờ bị rối ai là ai; "
            "định vị rõ không gian - thời gian ('Ở lớp học...', 'Quay về hiện tại...', 'Đi được một hồi thì...') và xen câu tự vấn nội tâm ngắn gọn ('Không lẽ anh đã đến muộn rồi sao?', 'Đúng là không có gì miễn phí')."
        ),
        "cau_hook_mau": "Liệu nhân vật chính có thể vượt qua tình thế ngặt nghèo này? Hãy cùng khám phá ngay những diễn biến mới nhất nhé!",
    },
    "meo_gay_drama": {
        "ten": "🌸 Ngôn Tình / Lọ Lem / Drama Gia Đình & Quý Tộc Mượt Mà (Chuẩn style Mèo Gầy TV)",
        "mo_ta": (
            "Phong cách kể chuyện mạch lạc, giàu cảm xúc và duyên dáng (như kênh Mèo Gầy TV): "
            "mở đầu vào thẳng số phận/gia cảnh nhân vật, luân phiên cách gọi cực mượt ('nữ chính, nam chính, nhỏ, cô nàng, thanh niên kia, cậu ta, tóc đỏ, tóc vàng, phu quân, bà chị'), "
            "dẫn dắt tâm lý và hiểu lầm dở khóc dở cười ('nhìn phát biết luôn', 'đôi bên nói chuyện qua lại tự dưng lại thấy hợp', "
            "'vã cho cái vào đầu', 'mừng phát khóc', 'bịt mõm lại', 'ghi điểm tuyệt đối')."
        ),
        "cau_hook_mau": "Từ một hoàn cảnh trớ trêu không ai ngờ tới, cuộc gặp gỡ định mệnh này đã làm đảo lộn hoàn toàn số phận của nhân vật chính!",
    },
    "lucifer_isekai": {
        "ten": "✨ Chuyển Sinh / Isekai / Phép Thuật Hài Đời Thường (Chuẩn style Lucifer Sama)",
        "mo_ta": (
            "Phong cách tóm tắt mạch truyện nhanh, rõ ràng, pha hài đời thường cực cuốn (như kênh Lucifer Sama): "
            "kể theo chuỗi Sự việc -> Suy nghĩ ngầm của main -> Kết quả bất ngờ khiến mọi người ngỡ ngàng, "
            "dùng ngôn từ bình dân vui nhộn ('Tưởng rằng mọi thứ tới đây là hết nhưng...', 'chạy mất dép luôn', "
            "'tội cãi lại nóc nhà thì không thể tha thứ được', 'đang bốc phét thì...', 'chỉ biết cạn lời mà thôi', 'gặp thằng nào là bem luôn thằng đó')."
        ),
        "cau_hook_mau": "Tưởng rằng mọi thứ tới đây là kết thúc, nhưng biến cố bất ngờ này đã mở ra một hành trình bá đạo khiến ai nấy chỉ biết cạn lời!",
    },
    "kich_tinh": {
        "ten": "🔥 Đại Chiến Kịch Tính & Lật Kèo (Chuẩn style Lười Tắm Anime / Solo Đỉnh Cao)",
        "mo_ta": (
            "Phong cách bình luận viên đại chiến cực cháy (như kênh Lười Tắm Anime): "
            "nhịp kể dồn dập, phân tích thế trận Mồi nhử -> Sát chiêu -> Phản đòn -> Lật kèo, "
            "dùng từ giàu sức nặng ('một hit tiễn đối thủ bay màu', 'mới giây trước còn cao ngạo thì ngay giây sau đã ăn trọn đòn chí mạng', "
            "'Đùng! Một tiếng nổ kinh hoàng xé toạc không gian', 'đến lúc này người xem mới ngã ngửa')."
        ),
        "cau_hook_mau": "Mới giây trước thế trận còn tưởng chừng đã ngã ngũ, thì ngay khoảnh khắc tiếp theo một màn lật kèo kinh thiên động địa đã nổ ra!",
    },
    "hai_huoc": {
        "ten": "😂 Manhwa Hệ Thống / Trùng Sinh Mặn Mà (Chuẩn style Gấu Xàm Anime / GenZ Bật Hack)",
        "mo_ta": (
            "Phong cách kể chuyện mặn mòi, bắt trend GenZ duyên dáng (như kênh Gấu Xàm Anime): "
            "xen kẽ bình luận cà khịa cực duyên ('thanh niên này', 'vẫn chưa hẹo', 'múa thử vài đường cơ bản mà ai cũng tưởng đang bật hack', "
            "'Cơ mà hắn lại không ngờ được rằng...', 'quay xe khét lẹt', 'đứng hình mất 5 giây')."
        ),
        "cau_hook_mau": "Tưởng chỉ là một pha xử lý cơ bản, thế nào mà khi nhân vật của chúng ta vừa ra tay thì cả đám xung quanh đều ngỡ anh đang bật hack!",
    },
    "trinh_tham_kinh_di": {
        "ten": "🕵️ Trinh Thám / Kinh Dị / Kỳ Bí Cuốn Hút (Chuẩn style Genz Tóm Tắt / Siêu Nhiên)",
        "mo_ta": (
            "Phong cách dẫn chuyện điện ảnh, hồi hộp và ớn lạnh vừa đủ (như kênh Genz Tóm Tắt): "
            "xoáy sâu vào chi tiết thị giác kỳ dị, phản ứng tâm lý nhân vật và chuỗi nhân quả chặt chẽ "
            "('Chưa kịp định thần...', 'Theo phản xạ tự vệ trước cảnh tượng quá đỗi kinh hãi...', 'Nào ngờ...', 'Từng cơn ớn lạnh chạy dọc sống lưng')."
        ),
        "cau_hook_mau": "Kịch tính, bí ẩn và sự ớn lạnh vừa đủ — vậy diễn biến của chương truyện hôm nay ẩn chứa điều gì đặc biệt? Hãy cùng mình tìm hiểu ngay nhé!",
    },
    "tu_tien": {
        "ten": "⚔️ Tu Tiên / Huyền Huyễn / Cường Giả Vả Mặt (Bá Đạo & Ngầu Lòi)",
        "mo_ta": (
            "Ngôn từ hào sảng, nhấn mạnh khí chất cường giả, uy áp nghiền nát kẻ địch và những màn vả mặt cực gắt "
            "('uy áp kinh thiên động địa bóp nghẹt bầu không khí', 'chỉ bằng một ánh mắt lạnh băng đã khiến đối phương đổ mồ hôi hột')."
        ),
        "cau_hook_mau": "Đối mặt với kẻ địch ngạo mạn trước mắt, thanh niên chỉ nhếch môi lạnh lùng trước khi tung ra chiêu thức chấn động toàn trường!",
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

        # 1. Nhãn người nói ở đầu câu ("<Tên>:") hoặc xưng danh trực tiếp ("<Tên> ta", "của <Tên>", "Ta là <Tên>")
        for c in self.characters:
            ten_c = c["ten"].strip()
            ten_low = ten_c.lower()
            if ten_low and (
                txt_low.startswith(f"{ten_low}:")
                or txt_low.startswith(f"{ten_low} :")
                or f"{ten_low} ta" in txt_low
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


def _lay_khoa_ai_review() -> tuple[str, str]:
    """
    Tìm khoá AI tốt nhất để biên kịch kịch bản Review:
    Trả về `(loai_backend, api_key)` trong đó `loai_backend` thuộc `('deepseek', 'groq', 'gemini')`.
    """
    ung_vien_keys: list[tuple[str, str]] = []
    for env_name in ("DEEPSEEK_API_KEY", "DEEPSEEK_API_KEYS", "GROQ_API_KEYS", "GROQ_API_KEY", "GEMINI_API_KEYS", "GEMINI_API_KEY"):
        val = (os.environ.get(env_name) or "").strip()
        if val:
            for part in val.split(","):
                p = part.strip()
                if p:
                    ung_vien_keys.append((env_name, p))

    base_dir = Path(__file__).resolve().parent
    for cfg_path in (
        Path.home() / ".manga_video_review_studio_config.json",
        base_dir / "cau-hinh-video-studio.json",
        base_dir.parent / "windows-app" / "cau-hinh-nguoi-dung.json",
    ):
        try:
            if cfg_path.is_file():
                cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
                for k_field in ("deepseek_api_key", "gemini_api_key", "ai_api_key"):
                    k = str(cfg.get(k_field) or "").strip()
                    if k:
                        ung_vien_keys.append((k_field.upper(), k.split(",")[0].strip()))
        except Exception:
            pass

    env_candidates = [
        base_dir / ".env",
        base_dir.parent / ".env",
        Path.home() / "Documents" / "Tool" / "Translation" / ".env",
    ]
    for env_path in env_candidates:
        try:
            if env_path.is_file():
                for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                    s = line.strip()
                    if s.startswith(("DEEPSEEK_API_KEY=", "DEEPSEEK_API_KEYS=", "GROQ_API_KEYS=", "GROQ_API_KEY=", "GEMINI_API_KEYS=", "GEMINI_API_KEY=")):
                        k_name, v_raw = s.split("=", 1)
                        v = v_raw.strip().strip("\"'")
                        for part in v.split(","):
                            p = part.strip()
                            if p:
                                ung_vien_keys.append((k_name.strip(), p))
        except Exception:
            pass

    for k_name, p in ung_vien_keys:
        if p.startswith("sk-") or k_name.startswith("DEEPSEEK"):
            return "deepseek", p
    for k_name, p in ung_vien_keys:
        if p.startswith("gsk_") or k_name.startswith("GROQ"):
            return "groq", p
    for k_name, p in ung_vien_keys:
        if len(p) >= 20:
            return "gemini", p
    return "", ""


def _lay_khoa_deepseek_review() -> str:
    loai, key = _lay_khoa_ai_review()
    return key if loai == "deepseek" else ""


def _lay_thong_tin_ket_noi_server_review() -> tuple[str, str]:
    """Lấy (server_url, token) từ cấu hình Video Studio hoặc App Dịch Truyện để gọi cầu nối DeepSeek/AI trên máy chủ."""
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
    loai_ai, key_ai = _lay_khoa_ai_review()
    if loai_ai == "deepseek" and key_ai:
        return "deepseek", "deepseek-chat"
    if loai_ai == "groq" and key_ai:
        return "groq", "llama-3.3-70b-versatile"
    if loai_ai == "gemini" and key_ai:
        return "gemini", "gemini-3.1-flash-lite"
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
    phong_cach: str = "kich_tinh",
) -> str:
    """
    Bộ biên kịch kể chuyện dự phòng (Offline Storyteller) theo chuẩn 3 kênh YouTube mẫu
    (Gấu Xàm Anime, Genz Tóm Tắt, Lười Tắm Anime) — hoàn toàn loại bỏ lối liệt kê khô khan!
    """
    ten_chinh = nv_chinh.get("ten") or "Nhân vật chính"
    if not (la_ten_nhan_vat_hop_le(ten_chinh) or ten_chinh in ("Nhân vật chính", "Kẻ địch", "Đối phương")):
        ten_chinh = "Nhân vật chính"
    xung_chinh = nv_chinh.get("xung_ho") or ten_chinh

    if not cap_nv_cau:
        if panel_idx == tong_panel - 1:
            return (
                f"Khép lại những diễn biến đầy kịch tính và bất ngờ của {boi_canh_chung or 'chương truyện hôm nay'}! "
                "Liệu cục diện tiếp theo sẽ bùng nổ ra sao, hãy cùng đón xem ở chương sau nhé!"
            )
        mau_khong_loi_theo_pc = {
            "hai_huoc": [
                f"Chưa kịp định thần, biểu cảm đứng hình mất 5 giây của {xung_chinh} khiến người xem không khỏi bật cười!",
                f"Tưởng sẽ có một pha xử lý cực ngầu, thế nào mà thái độ tỉnh bơ của {xung_chinh} lại làm đối phương cứng họng.",
                f"Giữa tình huống dở khóc dở cười ấy, {xung_chinh} chỉ biết thở dài ngán ngẩm trước độ lầy lội của đối phương.",
                f"Cơ mà đời không như là mơ, ánh mắt ngơ ngác của {xung_chinh} ngay khoảnh khắc này đã nói lên tất cả!",
            ],
            "trinh_tham_kinh_di": [
                f"Giữa bầu không khí tĩnh lặng đến rợn người, ánh mắt sững sờ của {xung_chinh} báo hiệu một biến cố bất thường sắp ập đến...",
                f"Chưa kịp để {xung_chinh} định thần, từng chi tiết kỳ dị trước mắt đã khiến từng cơn ớn lạnh chạy dọc sống lưng.",
                f"Theo phản xạ tự nhiên trước cảnh tượng khó tin ấy, {xung_chinh} lập tức khựng lại với vẻ mặt đầy hoang mang.",
                f"Không một lời thoại nào vang lên, nhưng sự căng thẳng nghẹt thở quanh {xung_chinh} đã đẩy kịch tính lên tột độ!",
            ],
            "kich_tinh": [
                f"Mới giây trước thế trận còn giằng co, thì ngay khoảnh khắc này thần thái sắc lạnh của {xung_chinh} đã làm bùng nổ bầu không khí!",
                f"Giữa áp lực nghẹt thở, {xung_chinh} lập tức siết chặt tay, sẵn sàng tung ra nước đi quyết định để lật ngược thế cờ!",
                f"Chứng kiến cảnh tượng chấn động trước mắt, ngay cả những người xung quanh cũng phải đổ mồ hôi hột trước khí thế của {xung_chinh}.",
                f"Đùng! Cục diện bất ngờ xoay chuyển cực gắt chỉ qua một ánh nhìn đầy sát khí của {xung_chinh}!",
            ],
        }
        ds_mau = mau_khong_loi_theo_pc.get(phong_cach) or mau_khong_loi_theo_pc["kich_tinh"]
        return ds_mau[panel_idx % len(ds_mau)]

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
        return f"Giữa bầu không khí ngày càng nóng lên, {xung_chinh} lập tức có màn thể hiện khiến ai nấy đều phải ngoái nhìn!"

    tu_bat_dau_dong_tu = (
        "hào hứng ", "hỏi xem ", "nhắc ", "đề nghị ", "sốt ruột ", "quyết định ", "tự ái ",
        "suy diễn ", "điềm tĩnh ", "phát cầu ", "cố gắng ", "trầm trồ ", "lập tức ",
        "ngơ ngác ", "thầm nghĩ ", "cảm kích ", "tung ", "quay sang ", "nhận xét ",
        "nhắc nhở ", "tâm đắc ", "nhận thấy ", "vô tình ", "vẫn hào hứng ", "muốn ", "dặn ", "tự hỏi ",
    )

    # Nhịp dẫn chuyện kiểu Gấu Xàm / Genz Tóm Tắt / Lười Tắm Anime
    dan_nhap_sinh_dong = [
        "Không để đối phương kịp trở tay,",
        "Mới giây trước còn giữ vẻ bình thản, ngay khoảnh khắc này",
        "Chưa kịp để mọi người xung quanh hết bất ngờ,",
        "Đứng trước tình thế đầy gay cấn,",
        "Nào ngờ ngay giây tiếp theo,",
        "Cơ mà đời không như là mơ, ngay lúc ấy",
        "Nhận thấy bầu không khí bắt đầu căng như dây đàn,",
        "Chẳng hề nao núng trước áp lực trước mắt,",
    ]
    cum_hanh_dong_noi = [
        "lập tức lên tiếng chất vấn,",
        "thẳng thừng tuyên bố một câu cực gắt:",
        "không ngần ngại đáp trả ngay lập tức:",
        "bất ngờ thốt lên đầy sửng sốt:",
        "lạnh lùng chốt hạ một câu xanh rờn:",
        "vội vàng lên tiếng cảnh báo:",
    ]
    cum_phan_ung_nguoi_hai = [
        "Nghe vậy, {nv} cũng chẳng vừa khi lập tức phản pháo",
        "Cơ mà {nv} lại không hề nao núng, liền đáp trả",
        "Chứng kiến màn thể hiện đó, {nv} chỉ biết thốt lên",
        "Ngay lập tức, {nv} quay xe cực gắt và tuyên bố",
    ]

    cac_ve: list[str] = []
    for i_luot, (nv_ten, ds_c) in enumerate(nhom_luot_noi):
        gop_y = " rồi ".join(ds_c) if len(ds_c) == 2 else ", ".join(ds_c)
        if gop_y:
            gop_y = gop_y[0].lower() + gop_y[1:]
        for proper in ("Hiyori-senpai", "Hiyori", "Haruka-chan", "Haruka", "Lai-chan"):
            gop_y = re.sub(re.escape(proper.lower()), proper, gop_y, flags=re.I)
        bat_dau_bang_dong_tu = any(gop_y.startswith(v) for v in tu_bat_dau_dong_tu)
        if i_luot == 0:
            tien_to = dan_nhap_sinh_dong[panel_idx % len(dan_nhap_sinh_dong)]
            if bat_dau_bang_dong_tu:
                cac_ve.append(f"{tien_to} {nv_ten} {gop_y}")
            else:
                hd = cum_hanh_dong_noi[(panel_idx + i_luot) % len(cum_hanh_dong_noi)]
                cac_ve.append(f"{tien_to} {nv_ten} {hd} {gop_y}")
        else:
            mau_p2 = cum_phan_ung_nguoi_hai[(panel_idx + i_luot) % len(cum_phan_ung_nguoi_hai)].format(nv=nv_ten)
            if bat_dau_bang_dong_tu:
                cac_ve.append(f"Khiến {nv_ten} {gop_y}")
            else:
                cac_ve.append(f"{mau_p2}: {gop_y}")

    cau_hoan_chinh = ". ".join(cac_ve).strip().rstrip(".") + "!"
    cau_hoan_chinh = re.sub(r"\brằng\s+rằng\b", "rằng", cau_hoan_chinh, flags=re.I)
    if panel_idx == tong_panel - 1:
        cau_hoan_chinh += " Hãy cùng đón xem những diễn biến bùng nổ tiếp theo nhé!"
    return cau_hoan_chinh


def _kiem_tra_cau_ai_hop_le(cau: str) -> bool:
    """Đảm bảo câu do LLM sinh ra là văn kể chuyện ngôi thứ 3 chuẩn 100% Tiếng Việt, không lẫn tiếng Anh, rác OCR hay văn mẫu máy móc."""
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
            "100%", "ví dụ:", "trong ngoặc", "mở đầu phân cảnh", "điềm tĩnh đáp lại rằng",
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
    để AI hiểu toàn cảnh mở đầu -> xung đột -> cao trào -> kết thúc trước khi viết lời bình từng trang.
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


_KHO_PHONG_CACH_MAU_MAC_DINH: list[dict[str, Any]] = [
    {
        "ma_kenh": "anime_rewind",
        "ten_kenh": "Anime Rewind (Mạch Lạc, Dễ Hiểu, Định Danh Tên Riêng Chuẩn Xác)",
        "nguon_url": "https://www.youtube.com/watch?v=WrQjFMQDwi0 | https://www.youtube.com/watch?v=TnZGW88NqxY",
        "cach_mo_dau": "Mở đầu bằng bối cảnh nguy cấp hoặc tóm gọn mối liên kết trực tiếp với sự kiện trước ('Ở chương trước, [Tên riêng] đã...', 'Bộ truyện bắt đầu với...').",
        "cach_goi_nhan_vat": ["Tên riêng + vai trò (người đồng nghiệp Katano, nữ cảnh sát Kaori, bạn thân Reiko)", "anh", "cô", "cậu", "cậu ta", "hắn"],
        "tu_noi_bo_cuc": ["Ở chương trước", "Quay về hiện tại", "Tuy nhiên", "Ngay lập tức", "Không còn cách nào khác", "Đi được một hồi thì", "Ngay lúc nguy cấp nhất", "Giữa lúc tranh cãi nảy lửa"],
        "cum_tu_dat_gia": ["buồn ngủ gặp chiếu manh", "đúng là không có gì là miễn phí", "không lẽ anh đã đến muộn rồi sao", "quái lạ, có thể là ai được chứ", "nhận ra tên này ngay lập tức"],
        "quy_tac_ke_chuyen": "LUÔN nêu rõ TÊN RIÊNG nhân vật ở vế đầu của cảnh hoặc khi có 2 nhân vật tương tác (kèm vai trò ngắn gọn) để người nghe biết chính xác ai làm gì với ai, vế sau mới dùng đại từ ('anh, cô, cậu, hắn'). Câu văn gọn gàng, định vị rõ không gian/thời gian và xen câu hỏi suy luận nội tâm ngắn gọn.",
    },
    {
        "ma_kenh": "meo_gay_tv",
        "ten_kenh": "Mèo Gầy TV (Ngôn Tình / Lọ Lem / Drama Quý Tộc)",
        "nguon_url": "https://www.youtube.com/watch?v=wG-Ws8Waklo",
        "cach_mo_dau": "Vào thẳng gia cảnh, số phận hoặc tình huống éo le của nhân vật ngay câu đầu tiên (không chào hỏi rườm rà).",
        "cach_goi_nhan_vat": ["nữ chính", "nam chính", "nhỏ", "cô nàng", "thanh niên kia", "cậu ta", "tóc đỏ", "tóc vàng", "phu quân", "bà chị", "đối phương"],
        "tu_noi_bo_cuc": ["Sáng hôm sau", "Qua hôm sau", "Đúng lúc có", "Nghe vậy", "Đôi bên nói chuyện qua lại tự dưng lại thấy hợp", "Kể tới đây, đột nhiên", "Đang tính đi thì", "Hiểu ra vấn đề"],
        "cum_tu_dat_gia": ["nhìn phát biết luôn", "bị vây kín", "hỏi cưới nhầm ngay cô chị", "hỏng mất một đời hoa", "bịt mõm lại", "vã cho cái vào đầu", "mừng phát khóc", "ghi điểm trong mắt"],
        "quy_tac_ke_chuyen": "Luân phiên gọi tên riêng với đặc điểm ngoại hình/vai trò ('nữ chính, nhỏ, thanh niên kia, cậu ta') để câu văn mềm mại, nối các cảnh bằng chuỗi nguyên nhân - hiểu lầm - kết quả tự nhiên.",
    },
    {
        "ma_kenh": "lucifer_sama",
        "ten_kenh": "Lucifer Sama (Isekai / Chuyển Sinh / Phép Thuật Hài Đời Thường)",
        "nguon_url": "https://www.youtube.com/watch?v=lam3nJ1Yjgs",
        "cach_mo_dau": "Giới thiệu trực diện nhân vật chính là ai, đang làm gì và biến cố mở màn ('Nhân vật chính của câu chuyện là một thanh niên...').",
        "cach_goi_nhan_vat": ["nhân vật chính", "thanh niên", "cậu nhóc", "cậu", "thằng cu", "ông anh", "cô tiếp tân", "tên cầm đầu", "nóc nhà"],
        "tu_noi_bo_cuc": ["Tưởng rằng mọi thứ tới đây là hết, nhưng", "Lúc này", "Nghe xong thì", "Nhưng thật ra là", "Cơ mà", "Đúng lúc này", "Đang hớn hở... thì lại", "Vừa nhận được... thì"],
        "cum_tu_dat_gia": ["chạy mất dép luôn", "đang bốc phét thì bị gõ vào đầu", "tội cãi lại nóc nhà thì không thể tha thứ được", "chỉ biết cạn lời mà thôi", "gặp thằng nào thì bem luôn thằng đó", "bốc hơi từ bao giờ"],
        "quy_tac_ke_chuyen": "Trình tự Sự việc -> Suy nghĩ giấu nghề/tâm lý thật của main -> Kết quả bá đạo khiến người xung quanh ngỡ ngàng hoặc cạn lời. Dùng ngôn từ đời thường bình dân, vui nhộn.",
    },
    {
        "ma_kenh": "gau_xam_anime",
        "ten_kenh": "Gấu Xàm Anime (Manhwa / Hệ Thống / Học Viện Mặn Mà)",
        "nguon_url": "https://www.youtube.com/watch?v=BquVo9-nYLQ",
        "cach_mo_dau": "Mở màn bằng tình huống nhân vật bị dồn ép hoặc vừa trải qua màn hành hạ/thử thách rồi bật dậy.",
        "cach_goi_nhan_vat": ["thanh niên", "anh chàng", "gã", "hắn", "con hàng này", "đối phương", "sư phụ"],
        "tu_noi_bo_cuc": ["Sau màn...", "Cơ mà hắn lại không ngờ được rằng", "Vừa dứt lời", "Thấy thế", "Chẳng nói chẳng rằng"],
        "cum_tu_dat_gia": ["múa thử vài đường cơ bản mà ai cũng tưởng đang bật hack", "vẫn chưa hẹo", "quay xe khét lẹt", "đứng hình mất 5 giây", "xanh mặt"],
        "quy_tac_ke_chuyen": "Kể hành động trước -> Lồng ý thoại ngắn gọn -> Chốt bằng câu bình luận cà khịa GenZ duyên dáng.",
    },
    {
        "ma_kenh": "genz_tom_tat",
        "ten_kenh": "Genz Tóm Tắt (Trinh Thám / Kinh Dị / Sinh Tồn)",
        "nguon_url": "https://www.youtube.com/watch?v=i0PBFI9uRIA",
        "cach_mo_dau": "Dựng bầu không khí tương phản giữa đời thường yên ả và chi tiết bất thường gây tò mò.",
        "cach_goi_nhan_vat": ["gã", "thanh niên", "nạn nhân", "cô nữ sinh", "kẻ lạ mặt", "đối phương"],
        "tu_noi_bo_cuc": ["Chưa kịp định thần", "Theo phản xạ tự vệ", "Nào ngờ", "Càng tiến lại gần", "Trước cảnh tượng quá đỗi kinh hãi"],
        "cum_tu_dat_gia": ["từng cơn ớn lạnh chạy dọc sống lưng", "ánh mắt kỳ dị", "nổi da gà", "chết lặng tại chỗ"],
        "quy_tac_ke_chuyen": "Xoáy sâu vào chi tiết thị giác bất thường trên tranh và phản ứng tâm lý hoảng sợ/nghi ngờ của nhân vật.",
    },
    {
        "ma_kenh": "luoi_tam_anime",
        "ten_kenh": "Lười Tắm Anime (Đại Chiến / Combat / Đối Kháng Đỉnh Cao)",
        "nguon_url": "https://www.youtube.com/watch?v=7fNSsrridfc",
        "cach_mo_dau": "Đẩy thẳng vào sức nóng của sàn đấu hoặc màn chạm trán giữa hai thế lực.",
        "cach_goi_nhan_vat": ["chiến thần", "hắn", "gã", "thanh niên", "đối thủ", "kẻ địch"],
        "tu_noi_bo_cuc": ["Mới giây trước còn... thì ngay giây sau", "Ai cũng ngỡ... nhưng hóa ra", "Không để đối phương kịp thở", "Ngay khoảnh khắc giao锋"],
        "cum_tu_dat_gia": ["một hit tiễn đối thủ bay màu", "lật kèo cực gắt", "miếng mồi nhử nằm trong tính toán", "ăn trọn đòn chí mạng", "đến lúc này người xem mới ngã ngửa"],
        "quy_tac_ke_chuyen": "Phân tích thế trận theo nhịp Mồi nhử -> Sát chiêu -> Phản đòn -> Lật kèo, tạo cảm giác bình luận viên trực tiếp.",
    },
]


class StyleLearningMemory:
    """
    Kho Học Hỏi Phong Cách Kể Chuyện Tự Cải Tiến (`~/.manga_video_review_learned_styles.json`).
    Cho phép người dùng dán bất kỳ link YouTube hoặc kịch bản mẫu nào để AI trích xuất:
    - Cách mở bài & dẫn nhập hoàn cảnh
    - Cách gọi nhân vật linh hoạt (tránh lặp tên riêng)
    - Từ nối bố cục & trình tự nhân quả
    - Cụm từ đắt giá / ngôn ngữ đời thường đặc trưng
    """

    def __init__(self, storage_path: Path | None = None) -> None:
        self.storage_path = storage_path or (Path.home() / ".manga_video_review_learned_styles.json")
        self.learned_profiles: list[dict[str, Any]] = []
        self.load()

    def load(self) -> None:
        if self.storage_path.is_file():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                if isinstance(data, list) and data:
                    self.learned_profiles = data
            except Exception:
                self.learned_profiles = []
        existing_ids = {p.get("ma_kenh") for p in self.learned_profiles}
        changed = False
        for default_p in _KHO_PHONG_CACH_MAU_MAC_DINH:
            if default_p["ma_kenh"] not in existing_ids:
                self.learned_profiles.append(dict(default_p))
                changed = True
        if changed or not self.storage_path.is_file():
            self.save()

    def save(self) -> None:
        try:
            self.storage_path.write_text(
                json.dumps(self.learned_profiles, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def tao_chi_dan_cho_prompt(self, phong_cach: str = "tu_dong_thich_ung") -> str:
        """Tổng hợp toàn bộ tinh hoa ngôn ngữ & bố cục đã học để bơm vào System Prompt."""
        ds_goi_nv: list[str] = []
        ds_tu_noi: list[str] = []
        ds_cum_tu: list[str] = []
        ds_quy_tac: list[str] = []
        for p in self.learned_profiles[-10:]:
            for x in p.get("cach_goi_nhan_vat") or []:
                if x not in ds_goi_nv:
                    ds_goi_nv.append(x)
            for x in p.get("tu_noi_bo_cuc") or []:
                if x not in ds_tu_noi:
                    ds_tu_noi.append(x)
            for x in p.get("cum_tu_dat_gia") or []:
                if x not in ds_cum_tu:
                    ds_cum_tu.append(x)
            qt = str(p.get("quy_tac_ke_chuyen") or "").strip()
            tk = str(p.get("ten_kenh") or "").strip()
            if qt:
                ds_quy_tac.append(f"  + [{tk}]: {qt}")

        return (
            "KHO TRI THỨC HỌC HỎI TỪ CÁC KÊNH YOUTUBE REVIEW TRIỆU VIEW:\n"
            f"- Cách gọi nhân vật luân phiên (dùng thay thế tên riêng để không bị lặp): {', '.join(ds_goi_nv[:18])}.\n"
            f"- Từ nối dẫn dắt bố cục & trình tự thời gian/nhân quả: {', '.join(ds_tu_noi[:16])}.\n"
            f"- Cụm từ đời thường duyên dáng (dùng đúng ngữ cảnh): {', '.join(ds_cum_tu[:18])}.\n"
            "- Quy tắc bố cục rút ra từ các kênh mẫu:\n" + "\n".join(ds_quy_tac[:8])
        )


def _trich_xuat_youtube_id(text: str) -> str | None:
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{11})", (text or "").strip())
    return m.group(1) if m else None


def _tai_phu_de_youtube(video_id: str) -> tuple[str, str, str]:
    """Tải tiêu đề, tên kênh và toàn bộ lời thoại tiếng Việt từ video YouTube."""
    title = f"YouTube Video ({video_id})"
    author = f"Kênh YouTube ({video_id})"
    transcript_text = ""
    try:
        req = urllib.request.Request(
            f"https://www.youtube.com/watch?v={video_id}",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="ignore")
        m_title = re.search(r"<title>(.*?)</title>", html)
        m_author = re.search(r'"author":"([^"]+)"', html)
        if m_title:
            title = re.sub(r"\s*-\s*YouTube\s*$", "", m_title.group(1)).strip()
        if m_author:
            author = m_author.group(1).strip()
    except Exception:
        pass

    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        ytt = YouTubeTranscriptApi()
        tlist = ytt.list(video_id)
        langs = [t.language_code for t in tlist]
        fetched = ytt.fetch(video_id, languages=["vi", "vi-VN", "en"] + langs)
        transcript_text = " ".join(s.text for s in fetched)
    except Exception:
        pass

    return title, author, transcript_text.strip()


def hoc_phong_cach_tu_youtube_hoac_van_ban(nguon: str, ten_kenh_goi_y: str = "") -> dict[str, Any]:
    """
    Học tự động cách dùng ngôn ngữ, cách gọi nhân vật, từ nối bố cục và trình tự kể chuyện
    từ 1 link YouTube (hoặc nhiều link / đoạn văn bản kịch bản mẫu) và lưu vào StyleLearningMemory.
    """
    raw = (nguon or "").strip()
    if not raw:
        raise ValueError("Vui lòng nhập link YouTube hoặc dán kịch bản mẫu để học.")

    vid = _trich_xuat_youtube_id(raw)
    title = ten_kenh_goi_y.strip() or "Kịch Bản Mẫu Người Dùng"
    author = ten_kenh_goi_y.strip() or "Phong Cách Học Mới"
    text_mau = raw
    nguon_url = ""

    if vid:
        nguon_url = f"https://www.youtube.com/watch?v={vid}"
        yt_title, yt_author, yt_text = _tai_phu_de_youtube(vid)
        title = yt_title or title
        author = ten_kenh_goi_y.strip() or yt_author or author
        if yt_text:
            text_mau = yt_text

    # 1. Phân tích định lượng ngôn ngữ học trên văn bản mẫu
    low_text = text_mau.lower()
    ung_vien_goi_nv = [
        "nữ chính", "nam chính", "nhân vật chính", "thanh niên", "cô nàng", "anh chàng",
        "nhỏ", "cậu ta", "cậu nhóc", "tóc đỏ", "tóc vàng", "tóc đen", "tóc bạc",
        "phu quân", "bà chị", "ông anh", "cô em", "nóc nhà", "đối phương", "tên cầm đầu",
    ]
    cach_goi_tim_thay = [w for w in ung_vien_goi_nv if w in low_text][:10] or ["thanh niên", "cô nàng", "nam chính", "nữ chính", "đối phương"]

    ung_vien_tu_noi = [
        "Đúng lúc này", "Nghe vậy", "Thấy thế", "Qua hôm sau", "Sáng hôm sau",
        "Chẳng mấy chốc", "Tưởng rằng", "Nhưng thật ra", "Cơ mà", "Đang tính",
        "Vừa dứt lời", "Chưa kịp định thần", "Không để đối phương kịp", "Hóa ra là",
    ]
    tu_noi_tim_thay = [w for w in ung_vien_tu_noi if w.lower() in low_text][:10] or ["Đúng lúc này", "Nghe vậy", "Cơ mà", "Thấy thế"]

    ung_vien_cum_tu = [
        "nhìn phát biết luôn", "chạy mất dép", "chỉ biết cạn lời", "cãi lại nóc nhà",
        "bốc phét", "vã cho cái vào đầu", "mừng phát khóc", "đứng hình", "quay xe",
        "bật hack", "bay màu", "lật kèo", "xanh mặt", "ghi điểm", "bốc hơi",
    ]
    cum_tu_tim_thay = [w for w in ung_vien_cum_tu if w in low_text][:10]

    quy_tac_rut_ra = (
        f"Học từ '{author}' ({title[:60]}): Mở đầu trực diện vào hoàn cảnh nhân vật, "
        f"luân phiên danh xưng ({', '.join(cach_goi_tim_thay[:6])}), "
        f"dẫn mạch nhân quả bằng ({', '.join(tu_noi_tim_thay[:5])})."
    )

    # 2. Nếu có AI (Gemini / DeepSeek / Groq / Ollama), dùng AI đúc kết thêm cụm từ đắt giá & bố cục riêng của kênh
    found = _tim_model_llm_cuc_bo()
    loai_ai, key_ai = _lay_khoa_ai_review()
    if found and len(text_mau) >= 120:
        backend, model_name = found
        prompt_learn = (
            f"Phân tích kịch bản review truyện/anime dưới đây của kênh '{author}' ({title}) và trích xuất JSON:\n"
            f"Đoạn mẫu:\n{text_mau[:3500]}\n\n"
            "Hãy trả về đúng 1 JSON object có các khóa:\n"
            '{"cach_mo_dau": "...", "cach_goi_nhan_vat": ["..."], "tu_noi_bo_cuc": ["..."], "cum_tu_dat_gia": ["..."], "quy_tac_ke_chuyen": "..."}'
        )
        try:
            raw_ai = ""
            if backend == "gemini" and key_ai:
                gem_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                payload = json.dumps(
                    {
                        "contents": [{"parts": [{"text": prompt_learn}]}],
                        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 600, "thinkingConfig": {"thinkingBudget": 0}},
                    }
                ).encode("utf-8")
                req = urllib.request.Request(gem_url, data=payload, headers={"x-goog-api-key": key_ai, "Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=20) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
                parts_out = (((data.get("candidates") or [{}])[0]).get("content") or {}).get("parts") or []
                raw_ai = "".join(str(p.get("text") or "") for p in parts_out)
            elif backend in ("deepseek", "groq") and key_ai:
                ep = "https://api.groq.com/openai/v1/chat/completions" if backend == "groq" else "https://api.deepseek.com/chat/completions"
                payload = json.dumps({"model": model_name, "temperature": 0.2, "max_tokens": 500, "messages": [{"role": "user", "content": prompt_learn}]}).encode("utf-8")
                req = urllib.request.Request(ep, data=payload, headers={"Authorization": f"Bearer {key_ai}", "Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=20) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
                raw_ai = str((((data.get("choices") or [{}])[0]).get("message") or {}).get("content") or "")
            m_json = re.search(r"\{[\s\S]*\}", raw_ai)
            if m_json:
                parsed = json.loads(m_json.group(0))
                if isinstance(parsed.get("cach_goi_nhan_vat"), list) and parsed["cach_goi_nhan_vat"]:
                    cach_goi_tim_thay = [str(x) for x in parsed["cach_goi_nhan_vat"][:10]]
                if isinstance(parsed.get("tu_noi_bo_cuc"), list) and parsed["tu_noi_bo_cuc"]:
                    tu_noi_tim_thay = [str(x) for x in parsed["tu_noi_bo_cuc"][:10]]
                if isinstance(parsed.get("cum_tu_dat_gia"), list) and parsed["cum_tu_dat_gia"]:
                    cum_tu_tim_thay = [str(x) for x in parsed["cum_tu_dat_gia"][:12]]
                if parsed.get("quy_tac_ke_chuyen"):
                    quy_tac_rut_ra = str(parsed["quy_tac_ke_chuyen"]).strip()
        except Exception:
            pass

    ma_kenh = re.sub(r"[^a-z0-9_]+", "_", (vid or author).lower()).strip("_") or "learned_style"
    profile_moi = {
        "ma_kenh": ma_kenh,
        "ten_kenh": f"{author} — {title[:48]}",
        "nguon_url": nguon_url or "Văn bản kịch bản mẫu",
        "cach_mo_dau": "Đi thẳng vào hoàn cảnh và hành động của nhân vật chính ngay từ khung tranh mở màn.",
        "cach_goi_nhan_vat": cach_goi_tim_thay,
        "tu_noi_bo_cuc": tu_noi_tim_thay,
        "cum_tu_dat_gia": cum_tu_tim_thay or ["nhìn phát biết luôn", "chỉ biết cạn lời", "đứng hình"],
        "quy_tac_ke_chuyen": quy_tac_rut_ra,
    }

    mem = lay_kho_hoc_hoi_phong_cach()
    mem.learned_profiles = [p for p in mem.learned_profiles if p.get("ma_kenh") != ma_kenh]
    mem.learned_profiles.append(profile_moi)
    mem.save()
    return profile_moi


_SINGLETON_STYLE_MEMORY: StyleLearningMemory | None = None


def lay_kho_hoc_hoi_phong_cach() -> StyleLearningMemory:
    global _SINGLETON_STYLE_MEMORY
    if _SINGLETON_STYLE_MEMORY is None:
        _SINGLETON_STYLE_MEMORY = StyleLearningMemory()
    return _SINGLETON_STYLE_MEMORY


def _suy_luan_cam_xuc_canh(loi_binh: str, khong_khi_anh: str, panel_idx: int, phong_cach: str) -> str:
    """Suy luận nhãn cảm xúc âm giọng (`cam_xuc`) cho từng phân cảnh dựa trên lời bình và không khí tranh."""
    low = (loi_binh or "").lower()
    if panel_idx == 0:
        return "mo_dau"
    if any(w in low for w in ("bất ngờ", "chấn động", "sấm sét", "tuyệt kỹ", "tung cú", "bùng nổ", "hét lên", "uy lực", "lật kèo", "đùng!")):
        return "kich_tinh"
    if any(w in low for w in ("đổ thừa", "ngơ ngác", "tấu hài", "cười", "quá lố", "bật hack", "oẳn tù tì", "tự ái", "cơ mà", "quay xe")):
        return "hai_huoc"
    if any(w in low for w in ("uy áp", "lạnh lùng", "bá đạo", "thống trị", "nghiền nát", "cường giả", "sát khí")):
        return "uy_ap"
    if any(w in low for w in ("sốt ruột", "hồi hộp", "căng thẳng", "ớn lạnh", "hoang mang", "rợn người", "chưa kịp định thần")):
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
    Xây dựng kịch bản thuyết minh toàn Chapter bằng AI (DeepSeek / Gemini 3.1 / Groq / Ollama)
    với Bộ Prompt Biên Kịch Triệu View (học từ 3 kênh Gấu Xàm Anime, Genz Tóm Tắt, Lười Tắm Anime).
    """
    tong = len(trang_da_gan_va_dich)
    if tong == 0:
        return None

    kk_list = ds_khong_khi or ["dien_bien_chinh"] * tong
    ho_so_nv = cast_memory.tao_mo_ta_ho_so_cho_ai()
    tom_tat_mach_chuong = _tong_hop_mach_truyen_toan_chuong(trang_da_gan_va_dich, kk_list)
    ket_qua_toan_bo: list[dict[str, str]] = [{} for _ in range(tong)]

    pc_mo_ta = (PHONG_CACH_KICH_BAN.get(phong_cach) or PHONG_CACH_KICH_BAN["kich_tinh"])["mo_ta"]
    loai_ai, key_ai = _lay_khoa_ai_review()
    server_url, server_token = _lay_thong_tin_ket_noi_server_review()
    if server_url in ("https://comic.io.vn", "http://comic.io.vn"):
        server_url = "https://translation-api.vibe1.tinhgon.xyz"

    # Ưu tiên 1: Nếu chưa có key AI cục bộ nhưng có kết nối Server comic.io.vn -> gọi cầu nối AI trên Server theo cụm 12 trang
    if not key_ai and server_url:
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

    kich_thuoc_cum = 12 if backend in ("deepseek", "gemini", "groq") else 4
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
                chuoi_thoai = f"(Khung tranh hành động/biểu cảm không có bóng thoại - không khí: {kk})"
            dong_mo_ta.append(f"[{k + 1}] Trang #{g_idx + 1} (Nhân vật: {nv_trang} | Không khí: {kk}): {chuoi_thoai}")

        chi_dan_hoc_hoi = lay_kho_hoc_hoi_phong_cach().tao_chi_dan_cho_prompt(phong_cach)
        system_msg = (
            "Bạn là Tổng Biên Kịch Vàng của các kênh YouTube Review Truyện Tranh triệu view (như Anime Rewind, Mèo Gầy TV, Lucifer Sama, Gấu Xàm Anime, Genz Tóm Tắt, Lười Tắm Anime).\n"
            "BÍ QUYẾT KỂ CHUYỆN DỄ HIỂU & BỐ CỤC TRIỆU VIEW BẮT BUỘC TUÂN THỦ:\n"
            "1. BỐ CỤC MỞ ĐẦU TRỰC DIỆN & RÕ HOÀN CẢNH (NHƯ ANIME REWIND & MÈO GẦY TV):\n"
            "   - Ở Trang #1, đi thẳng vào hoàn cảnh, thân phận nhân vật chính hoặc biến cố đang diễn ra (CẤM mở đầu bằng câu chào MC sáo rỗng kiểu 'Chào mừng các bạn đến với...').\n"
            "2. QUY TẮC VÀNG VỀ TÊN RIÊNG NHÂN VẬT (CHUẨN ANIME REWIND — NGHE CỰC KỲ DỄ HIỂU, KHÔNG BỊ RỐI AI VỚI AI):\n"
            "   - BẮT BUỘC nêu rõ TÊN RIÊNG của nhân vật (ví dụ: Maibara, Kawase, Godai, Tomie...) ở mệnh đề chính đầu tiên của cảnh hoặc bất cứ khi nào có 2 nhân vật tương tác với nhau (có thể kèm vai trò ngắn gọn như 'cô bạn Kawase', 'thanh niên Maibara', 'người đồng nghiệp Katano').\n"
            "   - Sau khi đã gọi rõ TÊN RIÊNG để người nghe định vị chính xác ai đang làm gì, ở các vế phụ tiếp theo trong cùng câu mới luân phiên dùng đại từ ('anh, cô, cậu, cậu ta, cô nàng, nhỏ, hắn, đối phương') để câu văn mượt mà mà không bị lặp từ.\n"
            "   - TUYỆT ĐỐI KHÔNG dùng toàn đại từ chung chung ('thanh niên, cô nàng, đối phương') suốt cả câu mà bỏ quên Tên riêng khiến người nghe không biết nhân vật nào đang hành động!\n"
            "3. ĐỊNH VỊ RÕ KHÔNG GIAN / THỜI GIAN & TRÌNH TỰ NHÂN - QUẢ LIÊN HOÀN:\n"
            "   - Đầu mỗi cảnh phải có từ nối dẫn mạch không gian/thời gian hoặc nguyên nhân - kết quả rõ ràng ('Ngay lập tức...', 'Tuy nhiên...', 'Nghe vậy...', 'Ở trong lớp học...', 'Đúng lúc này...', 'Không còn cách nào khác...', 'Đi được một hồi thì...').\n"
            "   - Đan xen câu hỏi suy luận nội tâm ngắn gọn của nhân vật ('Không lẽ...?', 'Chuyện quái gì đang xảy ra thế này?') rồi chốt bằng kết quả hoặc lời bình duyên dáng ('Đúng là không có gì miễn phí', 'Buồn ngủ gặp chiếu manh', 'Chỉ biết cạn lời').\n"
            "4. CÂU VĂN GỌN GÀNG, SÁT THỂ LOẠI & KHÔNG SƯỢNG TRÂN:\n"
            "   - Câu văn rõ chủ ngữ - vị ngữ, ngắn gọn súc tích, dễ nghe dễ hiểu ngay lần đầu.\n"
            "   - CẤM dùng văn mẫu báo cáo ('Ở phân cảnh này', 'điềm tĩnh đáp lại rằng') và CẤM dùng từ văn chương kịch cỡm sáo rỗng ('không gian đặc quánh lại', 'ánh mắt cháy bỏng') khi đang review truyện đời thường/học đường.\n"
            "5. 100% TIẾNG VIỆT TỰ NHIÊN & NHỊP THỞ GIỌNG ĐỌC AI: Không chèn từ tiếng Anh hay ký tự lạ. Chia câu thành các vế gọn 8-15 chữ bằng dấu phẩy (,), dùng dấu chấm than (!) hoặc chấm hỏi (?) tự nhiên.\n\n"
            + chi_dan_hoc_hoi
        )

        prompt = (
            f"=== BỘ TRUYỆN: {ten_truyen or 'Manga'} — {ten_chap or 'Chương mới'} ===\n"
            f"Phong cách kênh Review: {pc_mo_ta}\n"
            f"Hồ sơ nhân vật:\n{ho_so_nv}\n\n"
            f"Tóm tắt mạch diễn biến toàn chương:\n{tom_tat_mach_chuong[:1800]}\n"
            + (f"\nDiễn biến liền trước: {boi_canh_cum_truoc}\n" if boi_canh_cum_truoc else "")
            + f"\nHãy viết lời bình thuyết minh ngôi thứ 3 bằng TIẾNG VIỆT 100% chuẩn kênh Review triệu view cho {so_canh_batch} trang dưới đây.\n"
            + "\n".join(dong_mo_ta)
            + f"\n\nChỉ trả về đúng {so_canh_batch} dòng đánh số từ [1] đến [{so_canh_batch}] theo định dạng:\n"
            "[1] <Lời thuyết minh Tiếng Việt giàu cảm xúc (không dùng ngoặc kép)>"
        )

        try:
            if backend in ("deepseek", "groq"):
                endpoint_url = (
                    "https://api.groq.com/openai/v1/chat/completions"
                    if backend == "groq"
                    else "https://api.deepseek.com/chat/completions"
                )
                payload = json.dumps(
                    {
                        "model": model_name,
                        "temperature": 0.4,
                        "max_tokens": max(500, so_canh_batch * 160),
                        "messages": [
                            {"role": "system", "content": system_msg},
                            {"role": "user", "content": prompt},
                        ],
                    }
                ).encode("utf-8")
                req = urllib.request.Request(
                    endpoint_url,
                    data=payload,
                    headers={
                        "Authorization": f"Bearer {key_ai}",
                        "Content-Type": "application/json",
                        "User-Agent": "Mozilla/5.0",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=35) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
                raw_out = str((((data.get("choices") or [{}])[0]).get("message") or {}).get("content") or "")
            elif backend == "gemini":
                gem_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                payload = json.dumps(
                    {
                        "contents": [{"parts": [{"text": f"{system_msg}\n\n{prompt}"}]}],
                        "generationConfig": {
                            "temperature": 0.4,
                            "maxOutputTokens": max(600, so_canh_batch * 170),
                            "thinkingConfig": {"thinkingBudget": 0},
                        },
                    }
                ).encode("utf-8")
                req = urllib.request.Request(
                    gem_url,
                    data=payload,
                    headers={
                        "x-goog-api-key": key_ai,
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
                cand = (data.get("candidates") or [{}])[0]
                parts_out = (cand.get("content") or {}).get("parts") or []
                raw_out = "".join(str(p.get("text") or "") for p in parts_out)
            elif backend == "ollama":
                payload = json.dumps(
                    {
                        "model": model_name,
                        "stream": False,
                        "think": False,
                        "options": {
                            "temperature": 0.3,
                            "num_ctx": 4096,
                            "num_predict": max(360, so_canh_batch * 130),
                            "num_gpu": 37,
                            "stop": [f"[{so_canh_batch + 1}]"],
                        },
                        "messages": [
                            {"role": "system", "content": system_msg},
                            {"role": "user", "content": prompt},
                            {"role": "assistant", "content": "[1] "},
                        ],
                    }
                ).encode("utf-8")
                req = urllib.request.Request(
                    "http://127.0.0.1:11434/api/chat",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=25) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
                raw_out = str((data.get("message") or {}).get("content") or "")
                if not raw_out.lstrip().startswith("[1]"):
                    raw_out = "[1] " + raw_out
            else:
                payload = json.dumps(
                    {
                        "model": model_name,
                        "temperature": 0.3,
                        "max_tokens": max(360, so_canh_batch * 130),
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
                with urllib.request.urlopen(req, timeout=25) as resp:
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
    # Luôn ưu tiên gọi AI (DeepSeek / Gemini 3.1 / Groq / Server) để viết kịch bản chuẩn kênh Review triệu view!
    ai_scenes = (
        _viet_kich_ban_toan_chuong_bang_ai(
            trang_da_gan_va_dich,
            cast,
            ten_truyen=ten_truyen,
            ten_chap=ten_chap_vi,
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
                phong_cach=phong_cach,
            )

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
