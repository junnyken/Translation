"""Lọc chữ tượng thanh (SFX) và chữ nhiễu OCR trên nền tranh phức tạp (theo ngữ cảnh trang).

Mục tiêu:
1. Bảo toàn 100% hội thoại, hộp dẫn chuyện chữ nhật, tiếng hét trong bóng gai nhọn và suy nghĩ /
   độc thoại nội tâm không viền có câu chữ rõ ràng (như suy nghĩ trên nền tóc tối).
2. Bỏ qua từ gốc (KHÔNG xoá LaMa, KHÔNG dịch, KHÔNG vẽ đè) hai nhóm gây xấu tranh:
   - Chữ tượng thanh / từ láy âm thanh (SFX) trôi nổi ngoài bóng thoại đè lên nền screentone,
     tia tốc độ, tường gạch, tóc, áo giáp (`GULP`, `주절`, `픽`, `꼬르르`, `ビュウ ガタガタ`, `グキ`...).
   - Chữ nhiễu do OCR đọc nhầm nét cọ SFX ngoại ngữ hoặc nét vẽ phức tạp ngoài bóng thoại
     (`LA UMa Z`, `Mi P`, `#? -- - 로 나 까`, `1 피`).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import numpy as np

from app.services.interfaces import BBox

try:
    from app.services.ocr.engines import vung_dang_xoa_chu
except ModuleNotFoundError:
    _RE_CO_CHU_SO = re.compile(
        r"[0-9A-Za-z\u3040-\u30ff\u3400-\u9fff\uff00-\uffef\u00c0-\u024f\u1e00-\u1eff\uac00-\ud7af]"
    )

    def vung_dang_xoa_chu(
        text: str,
        confidence: float | None,
        min_conf: float = 0.42,
        min_ky_tu: int = 2,
    ) -> bool:
        ky_tu = _RE_CO_CHU_SO.findall(text or "")
        if not ky_tu:
            return False
        if confidence is None:
            return True
        if len(ky_tu) < min_ky_tu:
            return confidence >= max(min_conf, 0.78)
        return confidence >= min_conf


@dataclass(frozen=True)
class ThongTinNenVung:
    """Thông tin nền hình học quanh 1 khung chữ."""

    trong_bong_kin: bool
    nen_tranh_phuc_tap: bool


_RE_TACH_DAU_SFX = re.compile(r"^[!！?？.。…~〜～ー―\-・♡♥♪♫*\s]+|[!！?？.。…~〜～ー―\-・♡♥♪♫*\s]+$")
_RE_LATIN_CO_NGHIA = re.compile(r"[A-Za-z]")
_RE_TU_LATIN = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
_RE_PHA_HOA_THUONG = re.compile(r"(?:[a-z][A-Z]|[A-Z]{2,}[a-z])")
_RE_KATAKANA_ONLY = re.compile(r"^[\u30a0-\u30ff\uff66-\uff9fー]+$")
_RE_HIRAGANA_ONLY = re.compile(r"^[\u3040-\u309fー]+$")
_RE_HIRAGANA_LAY = re.compile(r"^([\u3041-\u3096]{2})\1$")
_RE_HIRAGANA_KEO_DAI = re.compile(r"([\u3041-\u3096])\1{2,}")
_RE_HANGUL_ONLY = re.compile(r"^[\uac00-\ud7af]+$")
_RE_HANGUL_ABAB = re.compile(r"^([\uac00-\ud7af]{2})\1$")
_RE_HANGUL_ABB_SFX = re.compile(r"^[\uac00-\ud7af]([르들덜글블슬])\1$")
_RE_CUM_CHU_CJK_KO = re.compile(r"[\uac00-\ud7af\u3040-\u30ff\u3400-\u9fff\uff66-\uff9f]+")
_RE_KY_HIEU_NHIEU = re.compile(r"[#~*+=_|/\\<>^\`-]")
_RE_CHU_SO_HOAC_THUONG_CJK_KO = re.compile(r"[\uac00-\ud7af\u3040-\u30ff\u3400-\u9fff]")

TU_DIEN_SFX_EN: frozenset[str] = frozenset({
    "gulp", "boom", "bam", "wham", "slam", "thud", "thump", "clang", "clank",
    "cling", "clong", "clink", "crash", "crack", "crackle", "kraak", "krak",
    "slash", "slice", "swoosh", "whoosh", "fwoosh", "woosh", "swish", "shing",
    "zap", "zip", "zing", "bzzt", "zzzt", "zzt", "bzz", "pow", "kaboom", "karoom",
    "rumble", "roar", "grrr", "grr", "screech", "shriek", "snap", "pop", "poof",
    "puff", "rustle", "creak", "clatter", "shatter", "sizzle", "hiss", "fizz",
    "gasp", "huff", "pant", "sniff", "sob", "splash", "splrsh", "splat", "spurt",
    "stomp", "tap", "tak", "thwack", "smack", "whack", "drip", "drop", "tick",
    "tock", "ding", "dong", "ring", "beep", "click", "clack", "chomp", "munch",
    "slurp", "glug", "doki", "gogo", "ba-dump", "ba-dum", "thump-thump", "fwip",
    "fump", "shwa", "brr", "vrr", "whirr",
})

#: Tập từ tượng thanh Hiragana phổ biến (tránh gắn nhầm từ thoại ngắn như はい, なに, まさか).
TU_DIEN_SFX_JA_HIRA: frozenset[str] = frozenset({
    "どきどき", "どきっ", "ざわざわ", "ざわっ", "ぶるぶる", "がたがた", "がたっ",
    "ごろごろ", "ぱちぱち", "ぱちっ", "ぴくっ", "ぴきっ", "ぐきっ", "ごくっ",
    "ごくごく", "はぁはぁ", "わくわく", "にやにや", "じろじろ", "ぼそっ", "ぼそぼそ",
    "びくん", "ぎゃああ", "ずしん", "どごぉん",
})

#: Tập từ tượng thanh / tượng hình tiếng Hàn (`의성어·의태어`) hay vẽ đè lên nền tranh Manhwa.
TU_DIEN_SFX_KO: frozenset[str] = frozenset({
    "주절", "준절", "주절주절", "중얼", "중얼중얼", "수군", "수군수군",
    "웅성", "웅성웅성", "소곤", "소곤소곤", "속삭", "투덜", "투덜투덜",
    "두근", "두근두근", "콩닥", "콩닥콩닥", "덜컥", "달그락", "드르륵",
    "스윽", "슥", "스르륵", "샤악", "휙", "휘익", "팍", "퍽", "퍼억",
    "쾅", "쿵", "쿠궁", "콰앙", "콰아앙", "쿠구구", "쿠구구궁",
    "우르르", "와르르", "번쩍", "반짝", "찌릿", "움찔", "흠칫",
    "휘청", "비틀", "털썩", "풀썩", "철컥", "찰칵", "딸깍", "똑똑",
    "짝", "픽", "피식", "컥", "켁", "꿀꺽", "꼬르륵", "꼬르르", "꾸르륵",
    "부들", "부들부들", "덜덜", "바스락", "사각", "타닥", "탁", "툭", "톡",
    "통", "탕", "빵", "펑", "쉬이익", "치이익", "지잉", "징", "웅", "윙",
})

#: Tập từ tượng thanh tiếng Hàn chắc chắn KHÔNG BAO GIỜ là thoại trong bóng (lầm bầm/tim đập/sôi bụng...).
TU_DIEN_SFX_KO_CHAC: frozenset[str] = frozenset({
    "주절", "준절", "주절주절", "중얼", "중얼중얼", "수군", "수군수군",
    "웅성", "웅성웅성", "소곤", "소곤소곤", "꼬르르", "꼬르륵", "꾸르륵",
    "두근", "두근두근", "콩닥", "콩닥콩닥", "우르르", "와르르",
    "콰아앙", "쿠구구", "쿠구구궁", "번쩍", "꿀꺽", "부들", "부들부들", "덜덜",
})

#: Ký tự tượng thanh thuần tiếng Trung (nếu đứng riêng outside bubble không có lời thoại đi kèm).
KY_TU_SFX_ZH: frozenset[str] = frozenset(
    "轰隆砰啪嗖咔嚓哗啦咚叮当哐咣嗡嘶嗒滴答咕噜扑通嘭刷唰飕嗖咻"
)

#: Từ tiếng Anh ngắn 1–2 chữ cái hợp lệ trong hội thoại/UI (tránh lọc nhầm thoại thật ngắn).
TU_EN_NGAN_HOP_LE: frozenset[str] = frozenset({
    "a", "i", "am", "an", "as", "at", "be", "by", "do", "go", "he", "hi",
    "if", "in", "is", "it", "me", "my", "no", "of", "oh", "ok", "on", "or",
    "so", "to", "up", "us", "we", "ah", "eh", "ha", "hm", "mm", "mr", "ms",
    "ow", "oy", "sh", "uh", "um", "yo", "ma", "pa", "ew", "aw", "dr", "st",
    "vs", "tv", "pc", "hp", "mp", "xp", "ko",
})


class BanDoBongThoaiTrang:
    """Bản đồ thành phần nền sáng/tối của 1 trang truyện để phân biệt bóng thoại kín với nền tranh."""

    def __init__(self, gray: np.ndarray) -> None:
        import cv2

        self.gray = gray
        self.H, self.W = gray.shape[:2]

        # Nền giấy trắng tinh (>=238), co nhẹ 2x2 để cắt các khe hở mảnh qua tia tốc độ / rãnh khung.
        white_er = cv2.erode((gray >= 238).astype(np.uint8), np.ones((2, 2), np.uint8))
        _, self._w_lbl, self._w_stats, _ = cv2.connectedComponentsWithStats(white_er, connectivity=4)

        # Lòng hộp dẫn chuyện / bóng thoại nền tối đặc đồng nhất (<=38).
        dark_er = cv2.erode((gray <= 38).astype(np.uint8), np.ones((2, 2), np.uint8))
        _, self._d_lbl, self._d_stats, _ = cv2.connectedComponentsWithStats(dark_er, connectivity=4)

        # Bản đồ độ lớn biên Sobel chuẩn hoá cho kiểm tra độ rối nền.
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        self._edge_mag = np.abs(gx) + np.abs(gy)

    def _kiem_tra_bong_sang(self, bx0: int, by0: int, bx1: int, by1: int) -> bool:
        import cv2

        box_area = max(1, (bx1 - bx0) * (by1 - by0))
        roi = self.gray[by0:by1, bx0:bx1]
        if float((roi >= 238).mean()) < 0.45:
            return False

        box_lbls = self._w_lbl[by0:by1, bx0:bx1]
        vals, counts = np.unique(box_lbls[box_lbls > 0], return_counts=True)
        if len(vals) == 0:
            return False
        best = int(vals[int(np.argmax(counts))])
        cx, cy, cw, ch, carea = (int(v) for v in self._w_stats[best])

        # Chặn vùng quá nhỏ (đốm sáng quanh SFX rời như `픽`) và vùng nền khung lớn / chạm mép trang.
        if cx <= 3 or cy <= 3 or cx + cw >= self.W - 4 or cy + ch >= self.H - 4:
            return False
        if cw < 58 or ch < 58 or carea < max(2400, int(box_area * 1.35)):
            return False
        if cw >= self.W * 0.36 and ch >= self.H * 0.16:
            return False

        # Kiểm tra lỗ thủng nội bộ của thành phần trắng: bóng thoại chỉ chứa nét chữ nhỏ (<14% diện tích).
        sub_comp = (self._w_lbl[cy : cy + ch, cx : cx + cw] == best).astype(np.uint8)
        inv = (1 - sub_comp).astype(np.uint8)
        pad_inv = cv2.copyMakeBorder(inv, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=1)
        ni, li, si, _ = cv2.connectedComponentsWithStats(pad_inv, connectivity=8)
        ext = int(li[0, 0])
        comp_box_area = max(1, cw * ch)
        if float(carea) / comp_box_area < 0.42:
            return False
        for hi in range(1, ni):
            if hi == ext:
                continue
            if float(si[hi, 4]) / comp_box_area >= 0.14:
                return False

        pad = 10
        rx0, ry0 = max(0, bx0 - pad), max(0, by0 - pad)
        rx1, ry1 = min(self.W, bx1 + pad), min(self.H, by1 + pad)
        ring_mask = np.ones((ry1 - ry0, rx1 - rx0), dtype=bool)
        ring_mask[by0 - ry0 : by1 - ry0, bx0 - rx0 : bx1 - rx0] = False
        if not np.any(ring_mask):
            return False

        same_ring = float((self._w_lbl[ry0:ry1, rx0:rx1][ring_mask] == best).mean())
        dark_ring = float((self.gray[ry0:ry1, rx0:rx1][ring_mask] <= 200).mean())
        return same_ring >= 0.50 and dark_ring <= 0.25

    def _kiem_tra_bong_toi(self, bx0: int, by0: int, bx1: int, by1: int) -> bool:
        box_area = max(1, (bx1 - bx0) * (by1 - by0))
        roi = self.gray[by0:by1, bx0:bx1]
        if float((roi <= 42).mean()) < 0.68:
            return False

        box_lbls = self._d_lbl[by0:by1, bx0:bx1]
        vals, counts = np.unique(box_lbls[box_lbls > 0], return_counts=True)
        if len(vals) == 0:
            return False
        best = int(vals[int(np.argmax(counts))])
        cx, cy, cw, ch, carea = (int(v) for v in self._d_stats[best])
        if cx <= 3 or cy <= 3 or cx + cw >= self.W - 4 or cy + ch >= self.H - 4:
            return False
        if cw < 58 or ch < 58 or carea < max(2400, int(box_area * 1.20)):
            return False
        if cw >= self.W * 0.42 and ch >= self.H * 0.22:
            return False

        pad = 8
        rx0, ry0 = max(0, bx0 - pad), max(0, by0 - pad)
        rx1, ry1 = min(self.W, bx1 + pad), min(self.H, by1 + pad)
        ring_mask = np.ones((ry1 - ry0, rx1 - rx0), dtype=bool)
        ring_mask[by0 - ry0 : by1 - ry0, bx0 - rx0 : bx1 - rx0] = False
        if not np.any(ring_mask):
            return False

        dark_ring = self.gray[ry0:ry1, rx0:rx1][ring_mask]
        same_ring = float((self._d_lbl[ry0:ry1, rx0:rx1][ring_mask] == best).mean())
        return same_ring >= 0.62 and float((dark_ring <= 48).mean()) >= 0.65

    def kiem_tra_vung(self, bbox: BBox) -> ThongTinNenVung:
        """Trả về thông tin khung có nằm trọn trong bóng thoại khép kín và có đè lên nền rối không."""
        bx0 = max(0, int(round(bbox.x)))
        by0 = max(0, int(round(bbox.y)))
        bx1 = min(self.W, int(round(bbox.x + bbox.w)))
        by1 = min(self.H, int(round(bbox.y + bbox.h)))
        if bx1 - bx0 < 4 or by1 - by0 < 4:
            return ThongTinNenVung(trong_bong_kin=False, nen_tranh_phuc_tap=True)

        trong_bong = self._kiem_tra_bong_sang(bx0, by0, bx1, by1) or self._kiem_tra_bong_toi(
            bx0, by0, bx1, by1
        )
        if trong_bong:
            return ThongTinNenVung(trong_bong_kin=True, nen_tranh_phuc_tap=False)

        pad = 12
        rx0, ry0 = max(0, bx0 - pad), max(0, by0 - pad)
        rx1, ry1 = min(self.W, bx1 + pad), min(self.H, by1 + pad)
        ring_mask = np.ones((ry1 - ry0, rx1 - rx0), dtype=bool)
        ring_mask[by0 - ry0 : by1 - ry0, bx0 - rx0 : bx1 - rx0] = False
        if not np.any(ring_mask):
            return ThongTinNenVung(trong_bong_kin=False, nen_tranh_phuc_tap=False)

        ring_gray = self.gray[ry0:ry1, rx0:rx1][ring_mask]
        ring_edge = self._edge_mag[ry0:ry1, rx0:rx1][ring_mask]
        grad_ring = float((ring_edge > 90.0).mean())
        std_ring = float(np.std(ring_gray))
        med_ring = float(np.median(ring_gray))
        phuc_tap = (grad_ring >= 0.14) or (std_ring >= 36.0) or (170.0 <= med_ring <= 232.0)
        return ThongTinNenVung(trong_bong_kin=False, nen_tranh_phuc_tap=phuc_tap)


def tao_ban_do_bong_thoai_tu_anh(
    image_or_path: str | Path | np.ndarray | None,
) -> BanDoBongThoaiTrang | None:
    """Dựng `BanDoBongThoaiTrang` từ đường dẫn ảnh hoặc mảng numpy (RGB/BGR/Gray)."""
    if image_or_path is None:
        return None
    try:
        import cv2

        if isinstance(image_or_path, np.ndarray):
            arr = image_or_path
            if arr.size == 0:
                return None
            if arr.ndim == 2:
                gray = arr.astype(np.uint8, copy=False)
            elif arr.ndim == 3 and arr.shape[2] >= 3:
                gray = cv2.cvtColor(arr[:, :, :3], cv2.COLOR_RGB2GRAY)
            else:
                return None
        else:
            p = Path(image_or_path)
            if not p.is_file():
                return None
            gray = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        if gray is None or gray.size == 0:
            return None
        return BanDoBongThoaiTrang(gray)
    except Exception:  # noqa: BLE001
        return None


def _tach_token_sfx(text: str) -> list[str]:
    tho = str(text or "").strip()
    if not tho:
        return []
    parts = [p for p in re.split(r"[\s.!！?？…~〜～ー―・♡♥♪♫*]+", tho) if p]
    out: list[str] = []
    for p in parts:
        cleaned = _RE_TACH_DAU_SFX.sub("", p)
        if cleaned:
            out.append(cleaned)
    return out


def la_chu_tuong_thanh_sfx(text: str, source_lang: str | None = None) -> bool:
    """Kiểm tra chuỗi OCR có mang đặc trưng chữ tượng thanh / từ láy SFX không."""
    tho = str(text or "").strip()
    if not tho:
        return False
    lang = (source_lang or "").strip().lower()

    # Tách giữ nguyên gạch nối nội từ cho các ca như "ba-dump", "thump-thump",
    # đồng thời bỏ gạch nối rời dạng "주절 - -" hoặc "주절 ~".
    raw_tokens = [t.strip("!！?？.。…~〜～・♡♥♪♫* ") for t in tho.split()]
    tokens = [t.strip("-―ー") for t in raw_tokens if t.strip("-―ー!！?？.。…~〜～・♡♥♪♫* ")]
    if not tokens:
        return False

    # 1. Kiểm tra SFX tiếng Anh / Latin
    if 1 <= len(tokens) <= 3:
        low_toks = [t.lower() for t in tokens]
        if all(t in TU_DIEN_SFX_EN for t in low_toks):
            return True
    if 1 <= len(tokens) <= 2 and lang in ("", "en"):
        if all(re.fullmatch(r"[A-Z]{3,12}", t) for t in tokens) and any(
            re.search(r"([A-Z])\1{2,}", t) for t in tokens
        ):
            return True

    # 2. Kiểm tra SFX Katakana / Hiragana (Nhật — cũng xuất hiện trên scanlation EN chưa xoá SFX)
    gon = re.sub(r"[\s!！?？.。…~〜～ー―\-・♡♥♪♫*]+", "", tho)
    if 1 <= len(tokens) <= 2 and all(
        _RE_KATAKANA_ONLY.match(t) and len(t) <= 8 for t in tokens
    ):
        return True
    if _RE_KATAKANA_ONLY.match(gon) and len(gon) <= 10:
        return True
    if _RE_HIRAGANA_ONLY.match(gon):
        if gon in TU_DIEN_SFX_JA_HIRA or _RE_HIRAGANA_LAY.match(gon):
            return True
        if len(gon) <= 6 and _RE_HIRAGANA_KEO_DAI.search(gon):
            return True

    # 3. Kiểm tra từ tượng thanh tiếng Hàn (`의성어·의태어`)
    ko_tokens = [re.sub(r"[!！?？.。…~〜～ー―\-・♡♥♪♫*]+", "", t) for t in tokens]
    ko_tokens = [t for t in ko_tokens if t]
    if ko_tokens and 1 <= len(ko_tokens) <= 2 and all(_RE_HANGUL_ONLY.match(t) for t in ko_tokens):
        if all(
            (t in TU_DIEN_SFX_KO) or _RE_HANGUL_ABAB.match(t) or _RE_HANGUL_ABB_SFX.match(t)
            for t in ko_tokens
        ):
            return True

    # 4. Kiểm tra chữ tượng thanh thuần tiếng Trung khi không kèm dấu ba chấm nối câu thoại
    if lang in ("", "zh", "zh-tw"):
        if "…" not in tho and "..." not in tho and ".." not in tho:
            if 1 <= len(gon) <= 3 and all(ch in KY_TU_SFX_ZH for ch in gon):
                return True

    return False


def _co_nhieu_ocr_en_ngoai_bong(
    text: str,
    confidence: float | None,
    nen_tranh_phuc_tap: bool,
) -> bool:
    """Chặn chữ Latin vô nghĩa do OCR đọc nhầm nét cọ SFX Katakana trên scanlation tiếng Anh."""
    if not _RE_LATIN_CO_NGHIA.search(text or ""):
        return True
    if not nen_tranh_phuc_tap:
        return False

    tu = _RE_TU_LATIN.findall(text or "")
    if not tu:
        return True
    conf_thap_hoac_trung = confidence is None or confidence < 0.86
    if not conf_thap_hoac_trung:
        return False

    # a) Từ pha hoa-thường bất thường ở giữa từ (như `'LA UMa Z'` `conf=0.66`), trừ họ `Mc...` và số nhiều `'...s'`.
    if len(tu) <= 4:
        for w in tu:
            base_w = re.sub(r"'[A-Za-z]+$", "", w)
            if (base_w.startswith("Mc") and len(base_w) >= 4) or re.fullmatch(r"[A-Z]{2,}s", base_w):
                continue
            if _RE_PHA_HOA_THUONG.search(base_w):
                return True

    # b) Cụm ngắn 1..3 từ đều chỉ dài 1..2 chữ cái mà có từ vô nghĩa (`'Mi P'` `conf=0.65`).
    if 1 <= len(tu) <= 3 and all(len(w) <= 2 for w in tu):
        if (confidence is None or confidence < 0.84) and any(
            w.lower() not in TU_EN_NGAN_HOP_LE for w in tu
        ):
            return True

    return False


def _co_nhieu_ocr_cjk_ko_ngoai_bong(
    text: str,
    confidence: float | None,
    nen_tranh_phuc_tap: bool,
) -> bool:
    """Chặn mảnh OCR vỡ kèm nhiều ký hiệu nhiễu từ SFX uốn lượn (`'#? -- - 로 나 까'`, `'1 피'`)."""
    tho = str(text or "").strip()
    cum = _RE_CUM_CHU_CJK_KO.findall(tho)
    if not cum:
        return False

    so_ky_hieu_nhieu = len(_RE_KY_HIEU_NHIEU.findall(tho))
    # 1) Mảnh âm tiết đơn lẻ rời rạc + nhiều ký hiệu rác (`'#? -- - 로 나 까'`, `conf=0.77`)
    if 1 <= len(cum) <= 4 and all(len(c) == 1 for c in cum):
        if so_ky_hieu_nhieu >= 2 or tho[0] in "#~-*_":
            if confidence is None or confidence < 0.84:
                return True

    # 2) Đúng 1 chữ đơn lẻ kèm chữ số/ký hiệu với độ tin cậy thấp (`'1 피'`, `conf=0.52`)
    so_chu_cjk_ko = len(_RE_CHU_SO_HOAC_THUONG_CJK_KO.findall(tho))
    if so_chu_cjk_ko == 1 and re.search(r"[\d#~*+\-]", tho):
        if confidence is not None and confidence < 0.78:
            return True
        if nen_tranh_phuc_tap and confidence is not None and confidence < 0.82:
            return True

    return False


def _tach_tu_chuan_sfx(text: str) -> list[str]:
    tho = str(text or "").strip()
    if not tho:
        return []
    raw_tokens = [t.strip("!！?？.。…~〜～・♡♥♪♫* ") for t in tho.split()]
    return [
        t.strip("-―ー")
        for t in raw_tokens
        if t.strip("-―ー!！?？.。…~〜～・♡♥♪♫* ")
    ]


def _la_sfx_ko_chac_chan(text: str) -> bool:
    tokens = _tach_tu_chuan_sfx(text)
    if not (1 <= len(tokens) <= 2):
        return False
    ko_tokens = [re.sub(r"[!！?？.。…~〜～ー―\-・♡♥♪♫*]+", "", t) for t in tokens]
    ko_tokens = [t for t in ko_tokens if t]
    return bool(ko_tokens) and (1 <= len(ko_tokens) <= 2) and all(
        t in TU_DIEN_SFX_KO_CHAC for t in ko_tokens
    )


def vung_can_thiet_dich(
    text: str,
    confidence: float | None,
    min_conf: float = 0.42,
    min_ky_tu: int = 2,
    *,
    source_lang: str | None = None,
    bbox: BBox | None = None,
    ban_do_bong: Any | None = None,
) -> bool:
    """Quyết định 1 vùng có thực sự CẦN XOÁ & DỊCH trên trang hay nên giữ nguyên nét vẽ gốc."""
    if not vung_dang_xoa_chu(text, confidence, min_conf, min_ky_tu):
        return False

    if _la_sfx_ko_chac_chan(text):
        return False

    if ban_do_bong is None or bbox is None:
        return True

    nen = ban_do_bong.kiem_tra_vung(bbox)
    if nen.trong_bong_kin:
        return True

    lang = (source_lang or "").strip().lower()
    if la_chu_tuong_thanh_sfx(text, lang):
        return False

    if lang == "en":
        if _co_nhieu_ocr_en_ngoai_bong(text, confidence, nen.nen_tranh_phuc_tap):
            return False
    elif lang in ("ko", "ja", "zh", "zh-tw"):
        if _co_nhieu_ocr_cjk_ko_ngoai_bong(text, confidence, nen.nen_tranh_phuc_tap):
            return False

    return True
