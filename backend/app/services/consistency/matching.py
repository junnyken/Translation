"""So khớp thuật ngữ theo từng ngôn ngữ (E13).

Ba nguyên tắc:

1. **Không bao giờ sửa văn bản đã lưu.** Chuẩn hoá chỉ diễn ra trong bộ nhớ để so khớp;
   `OCRResult.raw_text` và `TranslationResult.translated_text` giữ nguyên từng ký tự.
2. **NFC làm dạng chuẩn.** M6 đã trả giá cho bài học này: chuỗi NFD trông y hệt NFC nhưng
   `"ừ"` tách rời không bằng `"ừ"` dựng sẵn, nên so khớp sẽ trượt mà nhìn mắt thường không ra.
3. **Mỗi ngôn ngữ một luật.** Tiếng Anh có khoảng trắng nên so theo ranh giới từ; tiếng
   Nhật/Trung KHÔNG có khoảng trắng nên phải so chuỗi con, và phải ưu tiên thuật ngữ dài trước
   để `"ma thuật"` không bị `"ma"` nuốt mất.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

#: Ngôn ngữ dùng khoảng trắng để tách từ. Các ngôn ngữ còn lại so chuỗi con.
NGON_NGU_CO_KHOANG_TRANG = {"en"}


def chuan_hoa(text: str) -> str:
    """Đưa về NFC. Dùng cho MỌI phép so khớp, không bao giờ ghi ngược lại DB."""
    return unicodedata.normalize("NFC", text or "")


def khoa_thuat_ngu(text: str, lang: str) -> str:
    """Khoá dùng để chống trùng trong glossary.

    Tiếng Anh: hạ chữ thường + gom khoảng trắng. Tiếng Nhật/Trung: **không** hạ chữ thường
    (`casefold` của tiếng Việt/Latin không có nghĩa với chữ tượng hình, và còn làm hỏng một số
    ký tự), chỉ bỏ khoảng trắng thừa.
    """
    s = chuan_hoa(text).strip()
    s = re.sub(r"\s+", " ", s)
    if lang in NGON_NGU_CO_KHOANG_TRANG:
        s = s.casefold()
    return s


@dataclass(frozen=True)
class DoanKhop:
    """Một chỗ khớp trong văn bản GỐC (chỉ số tính trên chuỗi đã chuẩn hoá NFC)."""

    bat_dau: int
    ket_thuc: int
    doan: str

    @property
    def span(self) -> tuple[int, int]:
        return (self.bat_dau, self.ket_thuc)


def _mau_tieng_anh(term: str) -> re.Pattern:
    """Ranh giới từ cho tiếng Anh, giữ nguyên hành vi của dấu nháy và gạch nối.

    `\\b` của Python coi `'` và `-` là ranh giới, nên `"Don't"` sẽ khớp cả trong `"Don't"` lẫn
    `"Dont"`-liền-chữ nếu dùng thẳng. Ở đây chèn ranh giới thủ công: hai đầu phải là đầu/cuối
    chuỗi hoặc một ký tự KHÔNG phải chữ-số-nháy-gạch.
    """
    lien = r"[^\W_]|['’\-]"
    return re.compile(
        rf"(?<!{lien})" + re.escape(term) + rf"(?!{lien})",
        re.IGNORECASE | re.UNICODE,
    )


def tim_khop(text: str, term: str, lang: str) -> list[DoanKhop]:
    """Tìm mọi chỗ `term` xuất hiện trong `text`, theo luật của `lang`."""
    t = chuan_hoa(text)
    k = chuan_hoa(term).strip()
    if not t or not k:
        return []

    if lang in NGON_NGU_CO_KHOANG_TRANG:
        return [DoanKhop(m.start(), m.end(), m.group(0)) for m in _mau_tieng_anh(k).finditer(t)]

    # Nhật/Trung: so chuỗi con, không giả định có khoảng trắng.
    ket: list[DoanKhop] = []
    i = t.find(k)
    while i != -1:
        ket.append(DoanKhop(i, i + len(k), t[i : i + len(k)]))
        i = t.find(k, i + len(k))  # không chồng lấn chính nó
    return ket


def khop_uu_tien_dai_truoc(text: str, terms: list[tuple[str, str]], lang: str) -> dict[str, list[DoanKhop]]:
    """So nhiều thuật ngữ cùng lúc, **thuật ngữ dài được ưu tiên**.

    Không có luật này thì với glossary chứa cả `"ma"` và `"ma thuật"`, chuỗi `"ma thuật"` sẽ bị
    tính là hai lần khớp `"ma"` — đếm sai và đề xuất sai. Đoạn đã bị thuật ngữ dài chiếm thì
    thuật ngữ ngắn không được lấy lại.
    """
    t = chuan_hoa(text)
    da_chiem = [False] * len(t)
    ket: dict[str, list[DoanKhop]] = {}

    for khoa, term in sorted(terms, key=lambda x: len(chuan_hoa(x[1])), reverse=True):
        giu: list[DoanKhop] = []
        for d in tim_khop(t, term, lang):
            if any(da_chiem[d.bat_dau : d.ket_thuc]):
                continue  # đã bị một thuật ngữ dài hơn chiếm
            for i in range(d.bat_dau, d.ket_thuc):
                da_chiem[i] = True
            giu.append(d)
        if giu:
            ket[khoa] = giu
    return ket


def chua_thuat_ngu_dich(translated: str, target_term: str) -> bool:
    """Bản dịch có chứa thuật ngữ tiếng Việt đã duyệt không.

    So không phân biệt hoa thường vì tiếng Việt hay viết hoa đầu câu, nhưng **giữ nguyên dấu** —
    bỏ dấu để so sẽ khiến `"ma"` khớp với `"mà"`, `"má"`, `"mã"`… và tạo hàng loạt cảnh báo sai.
    """
    return chuan_hoa(target_term).strip().casefold() in chuan_hoa(translated).casefold()
