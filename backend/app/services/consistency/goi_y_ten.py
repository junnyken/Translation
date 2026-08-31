"""E17 tầng 3 — gợi ý cách dịch danh xưng theo TÊN BỘ TRUYỆN, có cổng đối chiếu.

Đây là chỗ **duy nhất** trong hệ thống hỏi mô hình một câu mà câu trả lời không đến từ dữ liệu
của người dùng. Nên nó phải chịu ràng buộc chặt hơn mọi chỗ khác.

Vì sao không hỏi thẳng "truyện X có nhân vật nào":

    Model LUÔN trả lời, kể cả khi không biết. Truyện ít tiếng tăm hoặc trùng tên sẽ ra một dàn
    nhân vật nghe rất thật. Nó cũng không biết chapter NÀY có ai. Mà thuật ngữ đã duyệt là LUẬT
    dùng để quét cả chapter, nên một cái tên bịa được duyệt sẽ làm mọi lượt rà soát sau đó báo
    sai — hỏng đúng thứ E13 sinh ra để bảo vệ.

Nên câu hỏi bị đảo lại:

    KHÔNG hỏi:  "truyện X có những nhân vật nào?"          (không kiểm chứng được)
    MÀ hỏi:     "đây là những danh xưng CÓ THẬT trong chapter này của truyện X —
                 người ta thường dịch chúng sang tiếng Việt thế nào?"   (kiểm chứng được)

Hai lớp chặn, cả hai đều đo được:

1. **Danh sách thuật ngữ do TA đưa vào**, model không được thêm mục mới — nó chỉ điền cách dịch.
2. **Cổng đối chiếu**: mỗi dòng model trả về phải nhắc lại đúng thuật ngữ gốc đã hỏi. Nhắc sai
   hoặc nhắc một thứ không có trong danh sách ⇒ **loại thẳng** và đếm vào `dropped_count`.

`dropped_count > 0` là bằng chứng sống rằng model có bịa trong lượt đó. Giữ nguyên con số ấy.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.models.enums import TermType
from app.services.consistency.matching import chuan_hoa

logger = logging.getLogger(__name__)

#: Trần số thuật ngữ gửi đi hỏi một lượt. Giữ prompt ngắn để không đốt token vô ích.
TRAN_HOI = 30

_LOAI_HOP_LE = {t.value for t in TermType}

_DONG = re.compile(r"^\s*(\d{1,3})\s*[.)\]]\s*(.+?)\s*=>\s*(.*)$")


@dataclass(frozen=True)
class GoiY:
    source_term: str
    target_term: str
    term_type: str
    note: str

    def to_json(self) -> dict:
        return {
            "source_term": self.source_term,
            "target_term": self.target_term,
            "term_type": self.term_type,
            "note": self.note,
            #: Nhãn cố định, đi theo dữ liệu tới tận giao diện. Người dùng phải luôn thấy nó.
            "nguon": "goi_y_mo_hinh_chua_duyet",
        }


def dung_prompt(series_name: str, terms: list[str], source_lang: str) -> str:
    """Prompt cố ý hẹp: model chỉ được điền cách dịch cho ĐÚNG danh sách đã cho."""
    danh_sach = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(terms))
    return (
        "Bạn là biên tập viên truyện tranh tiếng Việt.\n"
        f'Bộ truyện: "{series_name}". Ngôn ngữ gốc: {source_lang}.\n\n'
        "Dưới đây là các danh xưng ĐƯỢC TRÍCH RA TỪ CHÍNH chapter này. Với mỗi mục, cho biết "
        "cách dịch/phiên âm sang tiếng Việt mà cộng đồng đọc truyện hay dùng.\n\n"
        "Quy tắc bắt buộc:\n"
        f"- Trả về ĐÚNG {len(terms)} dòng, đánh số 1..{len(terms)} theo đúng thứ tự đầu vào.\n"
        "- Định dạng mỗi dòng: `số. <thuật ngữ gốc> => <tiếng Việt> | <loại> | <giải nghĩa ngắn>`\n"
        "- Phải nhắc lại NGUYÊN VĂN thuật ngữ gốc trước dấu `=>`.\n"
        "- KHÔNG thêm mục mới, KHÔNG bỏ mục, KHÔNG đổi thứ tự.\n"
        f"- `<loại>` chọn trong: {', '.join(sorted(_LOAI_HOP_LE))}.\n"
        "- Nếu bạn KHÔNG biết bộ truyện này hoặc không chắc về một mục, để phần tiếng Việt là "
        "`?` — nói không biết là câu trả lời đúng, đoán bừa thì không.\n\n"
        f"### Danh xưng trong chapter\n{danh_sach}"
    )


def phan_tich_va_doi_chieu(text: str, terms: list[str]) -> tuple[list[GoiY], int]:
    """Tách phản hồi và **đối chiếu với danh sách đã hỏi**. Trả (gợi ý hợp lệ, số bị loại).

    Bị loại khi: số thứ tự nằm ngoài danh sách · thuật ngữ nhắc lại không khớp mục đã hỏi ·
    phần tiếng Việt trống hoặc `?` (model tự khai không biết — tôn trọng, không ép nó đoán).
    """
    khoa = [chuan_hoa(t).strip() for t in terms]
    ket_qua: dict[int, GoiY] = {}
    bi_loai = 0

    for raw in (text or "").splitlines():
        dong = raw.strip()
        if not dong or dong.startswith("#"):
            continue
        m = _DONG.match(dong)
        if not m:
            continue

        so = int(m.group(1))
        nhac_lai = chuan_hoa(m.group(2)).strip().strip("`*")
        phan_con_lai = m.group(3)

        if not (1 <= so <= len(khoa)):
            bi_loai += 1
            logger.warning("E17: model trả về số thứ tự %s ngoài danh sách đã hỏi -> loại", so)
            continue
        if nhac_lai != khoa[so - 1]:
            # Đây chính là cổng đối chiếu: model nhắc sai thuật ngữ nghĩa là nó đang nói về một
            # thứ không có trong chapter.
            bi_loai += 1
            logger.warning(
                "E17: dòng %s nhắc lại %r nhưng mục đã hỏi là %r -> loại", so, nhac_lai, khoa[so - 1]
            )
            continue

        phan = [p.strip() for p in phan_con_lai.split("|")]
        vi = phan[0] if phan else ""
        if not vi or vi in {"?", "??", "-"}:
            continue  # model tự khai không biết -> KHÔNG tính là bịa, cũng không tạo gợi ý

        loai = phan[1] if len(phan) > 1 else ""
        if loai not in _LOAI_HOP_LE:
            loai = TermType.general_term.value
        note = phan[2] if len(phan) > 2 else ""

        ket_qua[so] = GoiY(source_term=terms[so - 1], target_term=vi, term_type=loai, note=note)

    return [ket_qua[k] for k in sorted(ket_qua)], bi_loai
