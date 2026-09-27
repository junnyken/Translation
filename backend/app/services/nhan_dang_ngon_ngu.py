"""E57 — nhận dạng ngôn ngữ gốc từ CHỮ ĐÃ ĐỌC ĐƯỢC, không đoán từ ảnh.

## Vì sao làm được mà không cần model mới

Đo ngày 27-09-2026 trên từ điển của `PP-OCRv6_medium_rec` — **chính model mà pipeline đã nạp** cho
`source_lang` `zh` và `en` (`~/.paddlex/official_models/PP-OCRv6_medium_rec/inference.yml`,
18.708 ký tự):

| Khối Unicode | Có trong từ điển |
|---|---|
| Hiragana `U+3040–309F` | **86 / 96** |
| Katakana `U+30A0–30FF` | **94 / 96** |
| Hán `U+4E00–9FFF` | 15.565 |
| Latin ASCII | 94 / 95 |
| Hangul | **0 / 11.172** |

Thêm nữa, ở `paddleocr` 3.7.0 nhánh PP-OCRv6 (`_pipelines/ocr.py`, dòng ~354) thì `lang` bằng
`ch`, `en` **hay** `japan` đều trả về **cùng một cặp model**. Nghĩa là engine đang chạy sẵn đã đọc
được kana — nhận dạng ngôn ngữ chỉ còn là **đếm ký tự**, chạy offline, không gọi API, không tốn
tiền, không tải model mới.

## Kana là thứ phân biệt, KHÔNG phải chữ Hán

Trang tiếng Nhật có **rất nhiều** chữ Hán (kanji), nên "có chữ Hán" không nói được gì. Thứ tiếng
Trung **không bao giờ** có là hiragana/katakana. Nên thứ tự xét bắt buộc là kana trước, Hán sau —
đảo lại là gán mọi manga thành tiếng Trung.

## Giới hạn PHẢI nói ra

Từ điển có **0 ký tự Hangul**, nên một trang **tiếng Hàn** không đọc được thành tiếng Hàn: nó ra
chuỗi rác gồm Hán và Latin, và hàm này sẽ đoán thành `zh`. Hệ thống không hỗ trợ tiếng Hàn
(`SourceLang` chỉ có ja/zh/en) nên đây không phải lỗi mới, nhưng người dùng thả trang tiếng Hàn vào
sẽ nhận một kết luận **sai mà trông tự tin**. Vì vậy hàm luôn trả kèm `bang_chung` để giao diện
hiện ra con số, và ngưỡng được đặt để "không đủ chữ" ⇒ **không kết luận** chứ không đoán bừa.

Cùng lý do: từ điển chỉ có 2/90 ký tự Việt có dấu — đừng bao giờ dùng hàm này để nhận ra tiếng
Việt.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

from app.models.enums import SourceLang

#: Dưới ngưỡng này thì KHÔNG kết luận. Đoán ngôn ngữ từ 3 ký tự là tung xúc xắc rồi trình bày kết
#: quả như một phép đo — và người dùng sẽ tin, vì màn hình không nói ra là nó chỉ có 3 ký tự.
SO_KY_TU_TOI_THIEU = 8

#: Một ký tự kana lẻ có thể là rác OCR trên trang tiếng Trung (nét bị đọc nhầm). Hai ký tự trở lên
#: thì gần như chắc chắn là chữ Nhật thật — tiếng Trung KHÔNG có kana, nên rác phải trùng hợp hai
#: lần mới vượt ngưỡng này.
SO_KANA_TOI_THIEU = 2

#: Tỉ lệ chữ Hán trong tổng số ký tự có nghĩa, để gọi là tiếng Trung. Trang tiếng Anh bị đọc lẫn
#: vài chữ Hán không được thành tiếng Trung.
TI_LE_HAN_TOI_THIEU = 0.20

#: Tỉ lệ chữ Latin để gọi là tiếng Anh.
TI_LE_LATIN_TOI_THIEU = 0.60


@dataclass
class BangChung:
    """Số đo thô. Luôn trả ra để giao diện **hiện được** thay vì chỉ nói "đã nhận dạng"."""

    kana: int = 0
    han: int = 0
    latin: int = 0
    hangul: int = 0
    #: Chữ cái KHÔNG phải Latin và KHÔNG phải CJK — Cyrillic, Hy Lạp, Ả Rập, Thái…
    #: Gom chúng vào ô `latin` (bản đầu của tôi làm vậy) là kết luận một trang tiếng Nga thành
    #: tiếng Anh, **tự tin và sai**. Ô riêng này làm chúng không đủ ngưỡng nhóm nào ⇒ không kết luận.
    chu_cai_khac: int = 0
    tong_co_nghia: int = 0
    so_vung_doc_duoc: int = 0
    so_vung_da_thu: int = 0

    def nhu_dict(self) -> dict:
        return {
            "kana": self.kana,
            "han": self.han,
            "latin": self.latin,
            "hangul": self.hangul,
            "chu_cai_khac": self.chu_cai_khac,
            "tong_co_nghia": self.tong_co_nghia,
            "so_vung_doc_duoc": self.so_vung_doc_duoc,
            "so_vung_da_thu": self.so_vung_da_thu,
        }


@dataclass
class KetQuaNhanDang:
    """`ngon_ngu is None` nghĩa là **không kết luận** — không phải "không có chữ".

    Hai trạng thái đó khác nhau với người dùng: "trang này không có chữ" là bình thường (bìa
    chương), còn "đọc được chữ nhưng không đủ để chắc" là lúc phải hỏi lại.
    """

    ngon_ngu: SourceLang | None
    ly_do: str
    bang_chung: BangChung = field(default_factory=BangChung)

    @property
    def ket_luan_duoc(self) -> bool:
        return self.ngon_ngu is not None


def _la_kana(c: str) -> bool:
    return "぀" <= c <= "ヿ" and c not in "・ー"


def _la_han(c: str) -> bool:
    # Gồm cả khối mở rộng A và các ký tự tương thích — trang scan hay lọt vào đó.
    return (
        "一" <= c <= "鿿"
        or "㐀" <= c <= "䶿"
        or "豈" <= c <= "﫿"
    )


def _la_latin(c: str) -> bool:
    """CHỈ chữ cái Latin thật: ASCII + Latin-1 Supplement + Latin Extended-A/B.

    Không dùng `unicodedata.category(c).startswith("L")` cho ô này: `L*` là **mọi** loại chữ cái,
    nên Cyrillic và Hy Lạp cũng lọt vào và một trang tiếng Nga ra kết luận "tiếng Anh".
    """
    return (
        "a" <= c <= "z"
        or "A" <= c <= "Z"
        or "\u00c0" <= c <= "\u024f"
    )


def _la_hangul(c: str) -> bool:
    return "가" <= c <= "힣" or "ᄀ" <= c <= "ᇿ"


def dem_ky_tu(cac_chuoi: list[str]) -> BangChung:
    """Đếm ký tự theo khối Unicode.

    Bỏ qua chữ số, dấu câu và khoảng trắng: một bong bóng chỉ có `"!!!"` hay `"123"` không nói được
    gì về ngôn ngữ, mà đếm nó vào `tong_co_nghia` sẽ làm ngưỡng tỉ lệ bị loãng và đẩy kết luận sang
    hướng sai.
    """
    bc = BangChung(so_vung_da_thu=len(cac_chuoi))
    for chuoi in cac_chuoi:
        if (chuoi or "").strip():
            bc.so_vung_doc_duoc += 1
        for c in chuoi or "":
            if _la_kana(c):
                bc.kana += 1
                bc.tong_co_nghia += 1
            elif _la_han(c):
                bc.han += 1
                bc.tong_co_nghia += 1
            elif _la_hangul(c):
                bc.hangul += 1
                bc.tong_co_nghia += 1
            elif _la_latin(c):
                bc.latin += 1
                bc.tong_co_nghia += 1
            elif unicodedata.category(c).startswith("L"):
                # Chữ cái của hệ chữ KHÁC (Cyrillic, Hy Lạp, Ả Rập…). Đếm vào tổng để nó LÀM LOÃNG
                # tỉ lệ và đẩy kết luận về "không chắc" — đúng thứ ta muốn cho ngôn ngữ không hỗ trợ.
                bc.chu_cai_khac += 1
                bc.tong_co_nghia += 1
    return bc


def phan_loai(cac_chuoi: list[str]) -> KetQuaNhanDang:
    """Phân loại ngôn ngữ từ danh sách chuỗi OCR đọc được. Hàm THUẦN — test được không cần model.

    Thứ tự xét là phần quan trọng nhất, xem docstring của module: **kana trước, Hán sau**.
    """
    bc = dem_ky_tu(cac_chuoi)

    if bc.tong_co_nghia == 0:
        return KetQuaNhanDang(None, "khong_doc_duoc_chu_nao", bc)

    if bc.tong_co_nghia < SO_KY_TU_TOI_THIEU:
        return KetQuaNhanDang(
            None, f"qua_it_chu ({bc.tong_co_nghia} < {SO_KY_TU_TOI_THIEU})", bc
        )

    # 1) Kana ⇒ tiếng Nhật. Tiếng Trung KHÔNG có kana, nên đây là dấu hiệu quyết định.
    if bc.kana >= SO_KANA_TOI_THIEU:
        return KetQuaNhanDang(SourceLang.ja, f"co_{bc.kana}_kana", bc)

    ti_le_han = bc.han / bc.tong_co_nghia
    ti_le_latin = bc.latin / bc.tong_co_nghia

    # 2) Nhiều chữ Hán mà KHÔNG có kana ⇒ tiếng Trung.
    if ti_le_han >= TI_LE_HAN_TOI_THIEU:
        return KetQuaNhanDang(SourceLang.zh, f"han_{ti_le_han:.0%}_khong_kana", bc)

    # 3) Gần như toàn chữ cái Latin ⇒ tiếng Anh.
    if ti_le_latin >= TI_LE_LATIN_TOI_THIEU:
        return KetQuaNhanDang(SourceLang.en, f"latin_{ti_le_latin:.0%}", bc)

    # 4) Không nhóm nào chiếm đủ ⇒ KHÔNG đoán. Trả về để giao diện hỏi lại người dùng.
    return KetQuaNhanDang(
        None,
        f"khong_nhom_nao_du_nguong (han {ti_le_han:.0%}, latin {ti_le_latin:.0%})",
        bc,
    )

# ── Chạy trên ảnh thật ────────────────────────────────────────────────────────────────────

#: Model dùng để ĐỌC THỬ. `ch` là lựa chọn tường minh, không phải mặc định tình cờ: đó chính là
#: model đã đo từ điển ở docstring trên. Ở PP-OCRv6 thì `ch`/`en`/`japan` nạp cùng một model, nhưng
#: viết rõ `ch` để nếu paddleocr về sau tách chúng ra thì chỗ này còn trỏ đúng thứ đã đo.
LANG_DOC_THU = "ch"


def nhan_dang_tu_anh(image_path: str, *, engine=None) -> KetQuaNhanDang:
    """Đọc thử một ảnh rồi phân loại ngôn ngữ.

    `engine` để test tiêm bản giả — không có nó thì mọi bài test đều phải nạp 76MB model thật.

    KHÔNG bắt ngoại lệ ở đây: engine hỏng (thiếu thư viện, hết RAM) là **lỗi thật** và phải nổi lên
    để task ghi `failed`. Nuốt nó rồi trả "không kết luận" là biến một sự cố hạ tầng thành một câu
    trả lời bình thường — người dùng sẽ tưởng ảnh của mình có vấn đề.
    """
    if engine is None:
        from app.core.config import get_settings
        from app.services.ocr.engines import PaddleOCREngine

        st = get_settings()
        engine = PaddleOCREngine(
            lang=LANG_DOC_THU,
            device=st.ocr_device,
            enable_mkldnn=st.ocr_paddle_enable_mkldnn,
        )
    return phan_loai(engine.doc_toan_anh(image_path))
