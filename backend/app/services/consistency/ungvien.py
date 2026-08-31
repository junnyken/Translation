"""E17 — rút ứng viên thuật ngữ và tín hiệu xưng hô từ CHÍNH chữ của chapter.

Vì sao tệp này tồn tại: màn "Thuật ngữ của chapter" và "Giọng nhân vật" là hai form trống, bắt
người dùng tự nhớ ra trong chapter có danh xưng nào rồi gõ lại nguyên văn — trong khi chữ đã nằm
sẵn trong `ocr_result.raw_text` từ bước đọc chữ.

Việc đó có hai nửa, và bộ này **chỉ nhận nửa đầu**:

    tìm ra có những danh xưng nào, ở đâu, bao nhiêu lần   -> MÁY (tệp này)
    quyết dịch thành gì, xưng hô ra sao                   -> NGƯỜI (không đụng vào)

Nguyên tắc như `scanner.py` của E13: **luật tất định, không gọi LLM, không ghi một dòng nào vào
CSDL.** Cùng đầu vào cho ra cùng đầu ra, giải thích được cho người dùng, và không giả vờ biết
điều nó không biết.

Ranh giới quan trọng nhất: mọi ứng viên đều phải mang **bằng chứng** (đếm được bao nhiêu lần, ở
trang nào, trích nguyên văn câu chứa nó). Một danh sách chữ không kèm bằng chứng thì người dùng
không có cơ sở nào để duyệt, và duyệt nhầm một thuật ngữ không có thật sẽ làm mọi lượt rà soát
sau đó báo sai — hỏng đúng thứ E13 sinh ra để bảo vệ.
"""
from __future__ import annotations

import re
import uuid
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import GlossaryEntry, OCRResult, Page, Project, TextRegion
from app.models.enums import OCRStatus, SourceLang, TermType
from app.services.consistency.matching import chuan_hoa, khoa_thuat_ngu

#: Trần số ứng viên trả về một lượt. Con số CHỌN, chưa phải con số ĐO — chỉnh sau khi chạy thật.
TRAN_UNG_VIEN = 50

#: Số trích dẫn kèm theo mỗi ứng viên. Đủ để tin, không đủ để làm ngập màn hình.
SO_TRICH_DAN = 3

#: Tỉ lệ chữ hoa mà quá nó thì tín hiệu "viết hoa = tên riêng" của tiếng Anh coi như CHẾT.
#: Chữ lồng trong truyện tranh tiếng Anh rất hay viết hoa toàn bộ; lúc đó luật ngây thơ sẽ trả về
#: MỌI từ trong chapter. Ngưỡng này là con số chọn, phải đo lại trên fixture thật rồi mới chốt.
NGUONG_CHU_HOA = 0.70


class ChuaDocChu(Exception):
    """Chapter chưa có chữ nào đọc được — KHÁC với 'đã tìm mà không thấy gì'."""


# ---------------------------------------------------------------- kiểu dữ liệu


@dataclass(frozen=True)
class TrichDan:
    """Một câu THẬT trong `raw_text`, không phải chuỗi dựng lại."""

    page_order: int
    region_id: str
    text: str


@dataclass
class UngVien:
    term: str
    term_key: str
    count: int = 0
    pages: set[int] = field(default_factory=set)
    quotes: list[TrichDan] = field(default_factory=list)
    #: GỢI Ý loại, chỉ để điền sẵn ô "Loại" cho đỡ một cú bấm. Không phải kết luận.
    type_guess: TermType = TermType.general_term
    #: Vì sao nó được nêu ra — hiện thẳng cho người dùng đọc.
    reasons: set[str] = field(default_factory=set)
    #: (vùng, đầu, cuối) của từng lần xuất hiện ĐÃ đếm. Có nó vì nhiều luật cùng bắt được một
    #: chỗ: "ペッパーさん" khớp cả luật hậu tố kính ngữ lẫn luật katakana, và nếu cộng theo số
    #: lần KHỚP LUẬT thay vì số lần XUẤT HIỆN thì con số hiện cho người dùng bị thổi gấp đôi.
    #: Đây là con số họ dựa vào để duyệt, nên thổi nó lên là nói dối.
    vi_tri: set[tuple[str, int, int]] = field(default_factory=set, repr=False)


@dataclass
class KetQuaUngVien:
    ung_vien: list[UngVien]
    so_vung_da_quet: int
    so_vung_co_chu: int
    #: `chua_doc_chu` · `khong_thay` · `deu_da_co` · `co_ung_vien`.
    #: Ba trạng thái rỗng KHÔNG được gộp: "chưa chạy" và "đã chạy mà trống" là hai chuyện khác
    #: nhau (bài học `worker: khong_ro` của E1a).
    trang_thai: str
    so_bi_loc_vi_da_co: int = 0
    #: Chỉ có với `en`: tỉ lệ chữ hoa đo được và luật nào đã dùng.
    ghi_chu_ngon_ngu: str | None = None
    #: Vùng có chữ nhưng máy tự khai đọc chưa chắc (`needs_manual`) — KHÔNG dùng để gợi ý.
    so_vung_khong_chac: int = 0


@dataclass
class TinHieuXungHo:
    ma: str
    nhan: str
    goi_y_xung_ho: str
    speech_register_goi_y: str
    count: int = 0
    #: Tên bị/được gọi kèm tín hiệu này, nếu tín hiệu là hậu tố kính ngữ gắn vào tên.
    ten_lien_quan: set[str] = field(default_factory=set)
    quotes: list[TrichDan] = field(default_factory=list)


@dataclass
class KetQuaXungHo:
    tin_hieu: list[TinHieuXungHo]
    so_vung_da_quet: int
    so_vung_co_chu: int
    trang_thai: str
    so_vung_khong_chac: int = 0


# ---------------------------------------------------------------- đọc chữ của chapter


@dataclass(frozen=True)
class DongChu:
    page_order: int
    region_id: str
    text: str


def doc_chu_chapter(session: Session, project_id: uuid.UUID) -> tuple[list[DongChu], int, int]:
    """Lấy mọi `raw_text` ĐÁNG TIN của chapter.

    Trả (các dòng có chữ, tổng số vùng, số vùng bị bỏ vì chữ đọc chưa chắc chắn).

    Dùng đúng đường join của `scanner.py`: region -> page (để biết số trang) -> ocr_result.

    **Chỉ nhận `OCRStatus.ok`.** `needs_manual` nghĩa là máy đọc được nhưng tự khai là không
    chắc — `scanner.py:112` cũng coi đó là chữ hỏng. Rút thuật ngữ từ chữ đọc sai sẽ đẻ ra ứng
    viên rác mà người dùng không có cách nào biết. Số vùng bị bỏ được đếm và trả ra, chứ không
    lặng lẽ biến mất.
    """
    hang = session.execute(
        select(TextRegion, OCRResult, Page.order)
        .join(Page, Page.id == TextRegion.page_id)
        .outerjoin(OCRResult, OCRResult.region_id == TextRegion.id)
        .where(Page.project_id == project_id)
        .order_by(Page.order, TextRegion.reading_order, TextRegion.id)
    ).all()

    dong: list[DongChu] = []
    khong_chac = 0
    for region, ocr, page_order in hang:
        if ocr is None:
            continue
        if ocr.status is OCRStatus.needs_manual:
            khong_chac += 1
            continue
        if ocr.status is not OCRStatus.ok:
            continue
        text = chuan_hoa(ocr.raw_text or "").strip()
        if not text:
            continue
        dong.append(DongChu(page_order=page_order, region_id=str(region.id), text=text))
    return dong, len(hang), khong_chac


# ---------------------------------------------------------------- luật theo ngôn ngữ

_KATAKANA = re.compile(r"[ァ-ヴー]{2,}")
_KANJI_RUN = re.compile(r"[一-龯]{2,4}")
#: Hậu tố kính ngữ tiếng Nhật — thứ đứng TRƯỚC nó gần như luôn là một cái tên.
_HAU_TO_JA = ("さん", "サン", "様", "さま", "ちゃん", "チャン", "くん", "君", "殿", "どの",
              "先輩", "せんぱい", "先生", "せんせい")
_TEN_TRUOC_HAU_TO_JA = re.compile(
    r"([ァ-ヴーぁ-ん一-龯]{1,10}?)(" + "|".join(_HAU_TO_JA) + r")"
)

#: Từ kanji quá phổ thông để làm thuật ngữ. Danh sách NGẮN có chủ đích: chặn hụt còn sửa được,
#: chặn thừa thì người dùng không bao giờ thấy thứ họ cần.
_CHAN_JA = {
    "自分", "大丈夫", "本当", "今日", "明日", "昨日", "今回", "一緒", "全部", "最後", "最初",
    "時間", "場合", "問題", "必要", "無理", "普通", "以上", "以下", "彼女", "彼氏",
}

_TITLE_EN = ("sir", "lord", "lady", "master", "mr", "mrs", "ms", "miss", "dr", "captain",
             "king", "queen", "prince", "princess", "father", "mother", "uncle", "aunt")
_TU_EN = re.compile(r"[A-Za-z][A-Za-z'\-]*")
_CAU_EN = re.compile(r"[.!?…]+\s*")

#: Từ tiếng Anh phổ thông — dùng ở nhánh TOÀN CHỮ HOA, khi tín hiệu viết hoa đã chết.
_CHAN_EN = {
    "the", "and", "you", "your", "yours", "that", "this", "these", "those", "with", "from",
    "have", "has", "had", "will", "would", "could", "should", "what", "when", "where", "why",
    "how", "who", "whom", "not", "but", "for", "are", "was", "were", "been", "being", "its",
    "it's", "i'm", "don't", "can't", "won't", "didn't", "let's", "there", "here", "just",
    "like", "know", "think", "want", "come", "going", "get", "got", "one", "two", "all",
    "now", "then", "than", "them", "they", "their", "she", "her", "his", "him", "our", "out",
    "about", "into", "over", "back", "down", "off", "yes", "no", "okay", "ok", "hey", "well",
    "right", "left", "good", "bad", "big", "small", "old", "new", "very", "much", "many",
    "more", "most", "some", "any", "every", "never", "always", "again", "still", "even",
    "only", "too", "also", "because", "before", "after", "while", "does", "did", "done",
    "make", "made", "take", "took", "give", "gave", "say", "said", "see", "saw", "look",
    "need", "help", "stop", "wait", "please", "thank", "thanks", "sorry", "hello", "goodbye",
}

_CJK = re.compile(r"[一-鿿]{2,}")
_TIEN_TO_ZH = ("小", "老", "阿")
_HAU_TO_ZH = ("先生", "大人", "前辈", "師父", "师父", "姑娘", "公子", "少爷", "小姐")
_CHAN_ZH = {
    "什么", "怎么", "这个", "那个", "我们", "你们", "他们", "自己", "现在", "已经", "可以",
    "不是", "没有", "知道", "时候", "因为", "所以", "但是", "如果", "这样", "那样", "一个",
    "起来", "出来", "过来", "回来", "还是", "真的", "东西", "地方", "问题", "开始",
}


def _ratio_chu_hoa(texts: list[str]) -> float:
    """Tỉ lệ chữ cái Latin viết hoa. Không có chữ cái nào ⇒ 0.0 (không phải 1.0)."""
    hoa = sum(1 for t in texts for c in t if c.isalpha() and c.isupper())
    thuong = sum(1 for t in texts for c in t if c.isalpha() and c.islower())
    tong = hoa + thuong
    return (hoa / tong) if tong else 0.0


def _them(kho: dict[str, UngVien], term: str, lang: str, dong: DongChu, ly_do: str,
          loai: TermType | None = None, span: tuple[int, int] | None = None) -> None:
    """Ghi nhận MỘT lần xuất hiện. `span` là vị trí trong `dong.text` — bắt buộc để không đếm
    trùng khi hai luật cùng bắt được một chỗ."""
    term = term.strip()
    if not term:
        return
    key = khoa_thuat_ngu(term, lang)
    if not key:
        return
    uv = kho.get(key)
    if uv is None:
        uv = UngVien(term=term, term_key=key)
        kho[key] = uv

    dau_vet = (dong.region_id, *(span or (-1, -1)))
    moi_thay = dau_vet not in uv.vi_tri
    uv.vi_tri.add(dau_vet)
    if moi_thay:
        uv.count += 1
    uv.pages.add(dong.page_order)
    uv.reasons.add(ly_do)
    if loai is not None:
        # Bằng chứng gắn với danh xưng (kính ngữ, chức danh) thắng phỏng đoán chung chung.
        uv.type_guess = loai
    if len(uv.quotes) < SO_TRICH_DAN and all(q.text != dong.text for q in uv.quotes):
        uv.quotes.append(TrichDan(dong.page_order, dong.region_id, dong.text))


def _rut_ja(dong: list[DongChu], kho: dict[str, UngVien]) -> None:
    for d in dong:
        for m in _TEN_TRUOC_HAU_TO_JA.finditer(d.text):
            _them(kho, m.group(1), "ja", d, f"đứng trước hậu tố {m.group(2)}",
                  TermType.character_name, m.span(1))
        for m in _KATAKANA.finditer(d.text):
            _them(kho, m.group(0), "ja", d, "chuỗi katakana", span=m.span())
        for m in _KANJI_RUN.finditer(d.text):
            if m.group(0) not in _CHAN_JA:
                _them(kho, m.group(0), "ja", d, "cụm kanji lặp lại", span=m.span())


def _rut_en(dong: list[DongChu], kho: dict[str, UngVien], toan_hoa: bool) -> None:
    """Hai lượt, và sự phân biệt giữa chúng mới là phần quan trọng.

    Một từ viết hoa ở **đầu câu** viết hoa vì ngữ pháp, nên tự nó KHÔNG phải bằng chứng tên
    riêng. Nhưng nếu chính từ đó đã được chứng minh ở chỗ khác (giữa câu, hoặc sau một danh
    xưng) thì những lần nó đứng đầu câu **vẫn là những lần xuất hiện thật** — bỏ đi là làm con
    số đếm thấp hơn sự thật, mà con số đó là thứ người dùng dựa vào để duyệt.

        "I met Pepper today. Pepper was tired."   -> Pepper: 2 lần (không phải 1)
        "Wonderful day. Terrible night."          -> không có gì (chưa từng có bằng chứng)
    """
    hang: list[tuple[DongChu, list, set[int]]] = []
    for d in dong:
        tu = list(_TU_EN.finditer(d.text))
        dau_cau = {0}
        for m in _CAU_EN.finditer(d.text):
            dau_cau.add(m.end())
        hang.append((d, tu, dau_cau))

    # ---- Lượt 1: chỉ nhận bằng chứng ĐỦ MẠNH ----
    for d, tu, dau_cau in hang:
        for i, m in enumerate(tu):
            w = m.group(0)
            truoc = tu[i - 1].group(0).lower().rstrip(".") if i > 0 else ""

            if truoc in _TITLE_EN:
                _them(kho, w, "en", d, f"đứng sau danh xưng {truoc}",
                      TermType.character_name, m.span())
                continue
            if toan_hoa:
                # Tín hiệu viết hoa đã chết -> chỉ còn tần suất + không phải từ phổ thông.
                if len(w) >= 3 and w.lower() not in _CHAN_EN:
                    _them(kho, w, "en", d, "lặp lại, không phải từ phổ thông", span=m.span())
            elif w[0].isupper() and len(w) >= 2 and w.lower() not in _CHAN_EN \
                    and m.start() not in dau_cau:
                _them(kho, w, "en", d, "viết hoa giữa câu", span=m.span())

    if toan_hoa:
        return  # không có khái niệm "đầu câu" khi mọi thứ đều viết hoa

    # ---- Lượt 2: đếm thêm những lần đứng ĐẦU CÂU của từ ĐÃ có bằng chứng ----
    da_chung_minh = set(kho)
    for d, tu, dau_cau in hang:
        for m in tu:
            if m.start() not in dau_cau:
                continue
            w = m.group(0)
            if w[0].isupper() and khoa_thuat_ngu(w, "en") in da_chung_minh:
                _them(kho, w, "en", d, "đứng đầu câu (đã có bằng chứng ở chỗ khác)",
                      span=m.span())


def _rut_zh(dong: list[DongChu], kho: dict[str, UngVien]) -> None:
    for d in dong:
        for m in _CJK.finditer(d.text):
            doan = m.group(0)
            goc = m.start()
            for ht in _HAU_TO_ZH:
                vt = doan.find(ht)
                if vt >= 2:
                    dau = max(0, vt - 3)
                    _them(kho, doan[dau:vt], "zh", d, f"đứng trước {ht}",
                          TermType.character_name, (goc + dau, goc + vt))
            for tt in _TIEN_TO_ZH:
                if doan.startswith(tt) and len(doan) >= 2:
                    het = min(len(doan), 3)
                    _them(kho, doan[:het], "zh", d, f"bắt đầu bằng {tt}",
                          TermType.character_name, (goc, goc + het))
            for n in (2, 3, 4):
                for i in range(len(doan) - n + 1):
                    cum = doan[i:i + n]
                    if cum not in _CHAN_ZH:
                        _them(kho, cum, "zh", d, "cụm lặp lại", span=(goc + i, goc + i + n))


# ---------------------------------------------------------------- API của service


def rut_ung_vien(session: Session, project_id: uuid.UUID) -> KetQuaUngVien:
    """Ứng viên thuật ngữ của MỘT chapter. Không ghi gì vào CSDL."""
    du_an = session.get(Project, project_id)
    if du_an is None:
        raise ChuaDocChu(f"project_not_found: {project_id}")

    dong, so_vung, khong_chac = doc_chu_chapter(session, project_id)
    lang = du_an.source_lang.value if isinstance(du_an.source_lang, SourceLang) else str(du_an.source_lang)

    if not dong:
        return KetQuaUngVien([], so_vung, 0, "chua_doc_chu", so_vung_khong_chac=khong_chac)

    kho: dict[str, UngVien] = {}
    ghi_chu = None
    if lang == "ja":
        _rut_ja(dong, kho)
    elif lang == "en":
        ty_le = _ratio_chu_hoa([d.text for d in dong])
        toan_hoa = ty_le >= NGUONG_CHU_HOA
        ghi_chu = (
            f"chữ hoa {ty_le:.0%} — "
            + ("chữ lồng gần như toàn chữ hoa nên KHÔNG dùng được tín hiệu viết hoa, "
               "đang lọc theo tần suất và danh xưng"
               if toan_hoa else "dùng tín hiệu viết hoa giữa câu")
        )
        _rut_en(dong, kho, toan_hoa)
    elif lang == "zh":
        _rut_zh(dong, kho)
        ghi_chu = ("tiếng Trung không có khoảng trắng và không có chữ hoa nên chỉ lọc được theo "
                   "cụm lặp lại — nhiễu cao hơn tiếng Nhật/Anh")

    # Ngưỡng lặp: katakana/kính ngữ là tín hiệu mạnh nên giữ từ 1 lần; còn lại phải lặp.
    toi_thieu = 1 if lang == "ja" else 2
    ung_vien = [
        uv for uv in kho.values()
        if uv.count >= toi_thieu or uv.type_guess == TermType.character_name
    ]

    # Bỏ thứ đã có trong glossary — MỌI trạng thái, kể cả `rejected`: người dùng đã cân nhắc rồi.
    da_co = {
        k for (k,) in session.execute(
            select(GlossaryEntry.source_term_key).where(GlossaryEntry.project_id == project_id)
        ).all()
    }
    con_lai = [uv for uv in ung_vien if uv.term_key not in da_co]
    so_bi_loc = len(ung_vien) - len(con_lai)

    con_lai.sort(key=lambda uv: (-uv.count, uv.term_key))
    cat = con_lai[:TRAN_UNG_VIEN]

    if cat:
        trang_thai = "co_ung_vien"
    elif so_bi_loc > 0:
        trang_thai = "deu_da_co"
    else:
        trang_thai = "khong_thay"

    return KetQuaUngVien(cat, so_vung, len(dong), trang_thai, so_bi_loc, ghi_chu, khong_chac)


# ---------------------------------------------------------------- tầng 2: xưng hô

#: (mã, mẫu regex, nhãn, gợi ý xưng hô, giọng gợi ý). Mỗi dòng phải là một tín hiệu CÓ THẬT trong
#: bản gốc — không suy diễn tính cách nhân vật.
_TIN_HIEU: dict[str, list[tuple[str, str, str, str, str]]] = {
    "ja": [
        ("ja_sama", r"([ァ-ヴーぁ-ん一-龯]{1,10}?)(様|さま)", "hậu tố 様/さま", "ngài / đại nhân", "formal"),
        ("ja_dono", r"([ァ-ヴーぁ-ん一-龯]{1,10}?)(殿|どの)", "hậu tố 殿", "ngài", "archaic"),
        ("ja_san", r"([ァ-ヴーぁ-ん一-龯]{1,10}?)(さん)", "hậu tố さん", "anh / chị / cô", "neutral"),
        ("ja_chan", r"([ァ-ヴーぁ-ん一-龯]{1,10}?)(ちゃん)", "hậu tố ちゃん", "em / bé", "casual"),
        ("ja_kun", r"([ァ-ヴーぁ-ん一-龯]{1,10}?)(くん|君)", "hậu tố くん", "cậu / em", "casual"),
        ("ja_senpai", r"(先輩|せんぱい)", "先輩", "tiền bối / anh chị khoá trên", "formal"),
        ("ja_sensei", r"(先生|せんせい)", "先生", "thầy / cô / tiên sinh", "formal"),
        ("ja_ore", r"(俺)", "đại từ 俺", "tao / tôi (thô, nam)", "rough"),
        ("ja_boku", r"(僕)", "đại từ 僕", "tớ / em (nhã, thường là nam trẻ)", "casual"),
        ("ja_watashi", r"(私|わたし)", "đại từ 私", "tôi", "neutral"),
        ("ja_washi", r"(わし)", "đại từ わし", "lão phu / ta (người già)", "archaic"),
        ("ja_atashi", r"(あたし)", "đại từ あたし", "tui / tớ (nữ, suồng sã)", "casual"),
    ],
    "zh": [
        ("zh_daren", r"(大人)", "大人", "đại nhân", "formal"),
        ("zh_qianbei", r"(前辈|前輩)", "前辈", "tiền bối", "formal"),
        ("zh_shifu", r"(师父|師父)", "师父", "sư phụ", "formal"),
        ("zh_benzuo", r"(本座|本尊)", "本座", "bổn toạ", "archaic"),
        ("zh_zaixia", r"(在下)", "在下", "tại hạ", "archaic"),
        ("zh_wo", r"(我)", "đại từ 我", "tôi / ta", "neutral"),
    ],
    "en": [
        ("en_sir", r"\b(sir|lord)\b", "Sir / Lord", "ngài", "formal"),
        ("en_lady", r"\b(lady|madam|ma'am)\b", "Lady / Madam", "phu nhân / bà", "formal"),
        ("en_master", r"\b(master)\b", "Master", "chủ nhân / sư phụ", "formal"),
        ("en_thou", r"\b(thou|thee|thy|thine)\b", "thou/thee", "ngươi / khanh (giọng cổ)", "archaic"),
    ],
}


def rut_tin_hieu_xung_ho(session: Session, project_id: uuid.UUID) -> KetQuaXungHo:
    """Tín hiệu xưng hô CÓ THẬT trong bản gốc. Không ghi gì, không đoán tính cách.

    Giới hạn phải nói trước: hệ thống chưa gán lời thoại cho nhân vật, nên đây là "trong chapter
    có tín hiệu này", KHÔNG phải "nhân vật X xưng thế này với Y".
    """
    du_an = session.get(Project, project_id)
    if du_an is None:
        raise ChuaDocChu(f"project_not_found: {project_id}")

    dong, so_vung, khong_chac = doc_chu_chapter(session, project_id)
    if not dong:
        return KetQuaXungHo([], so_vung, 0, "chua_doc_chu", khong_chac)

    lang = du_an.source_lang.value if isinstance(du_an.source_lang, SourceLang) else str(du_an.source_lang)
    luat = _TIN_HIEU.get(lang, [])
    gom: dict[str, TinHieuXungHo] = {}
    cd_theo_ma: dict[str, set[str]] = defaultdict(set)

    for ma, mau, nhan, goi_y, giong in luat:
        pat = re.compile(mau, re.IGNORECASE if lang == "en" else 0)
        for d in dong:
            for m in pat.finditer(d.text):
                th = gom.get(ma)
                if th is None:
                    th = TinHieuXungHo(ma=ma, nhan=nhan, goi_y_xung_ho=goi_y,
                                       speech_register_goi_y=giong)
                    gom[ma] = th
                th.count += 1
                # Nhóm 1 chỉ tồn tại ở các mẫu "tên + hậu tố" -> mới có tên để gắn.
                if m.re.groups >= 2 and m.group(1):
                    th.ten_lien_quan.add(m.group(1))
                if len(th.quotes) < SO_TRICH_DAN and d.text not in cd_theo_ma[ma]:
                    cd_theo_ma[ma].add(d.text)
                    th.quotes.append(TrichDan(d.page_order, d.region_id, d.text))

    tin_hieu = sorted(gom.values(), key=lambda t: (-t.count, t.ma))
    return KetQuaXungHo(tin_hieu, so_vung, len(dong),
                        "co_tin_hieu" if tin_hieu else "khong_thay", khong_chac)
