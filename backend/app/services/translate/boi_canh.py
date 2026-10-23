"""E31 — nối BẢNG THUẬT NGỮ và HỒ SƠ GIỌNG NHÂN VẬT vào prompt của `llm_context`.

## Vì sao

`llm_context` gộp cả trang thành một request, nên nó nhất quán **trong một trang**. Nhưng nó
**không thấy trang khác**, và đó là giới hạn đã ghi ở `REPORT_E26 §9`:

> *"nó gộp ngữ cảnh trong MỘT trang, không phải cả chapter. Muốn nhất quán xuyên trang thì đó là
> việc của bảng thuật ngữ (E17), không phải của D."*

Đo thật trên tiếng Anh (trang `29ab3d86`): `Air Dragon` được `llm_context` dịch là `Rồng Gió` —
hay, nhưng **không có gì bảo đảm trang sau nó không dịch thành `Rồng Không Khí`**. Bảng thuật ngữ
là chỗ duy nhất giữ được quyết định đó xuyên trang.

E13 và E17 đã dựng sẵn hai bảng này. Module này chỉ **nối chúng vào prompt** — lại đúng cái khuôn
đã gặp ở E26: hạ tầng có rồi, chưa ai cắm dây.

## Hai luật

**1. CHỈ nạp mục người dùng đã chốt.** Thuật ngữ phải `approved`, giọng nhân vật phải `active`.
Bản `draft` là **gợi ý của máy chưa ai duyệt** — đưa nó vào prompt là để máy tự xác nhận phỏng
đoán của chính nó, và biến một gợi ý sai thành cái sai lặp lại trên cả chapter. Đúng nguyên tắc
E13: *"máy chỉ ra chỗ kèm lý do, KHÔNG tự sửa"*.

**2. Không có gì đã chốt thì KHÔNG thêm dòng nào vào prompt.** Prompt rỗng phần này phải giống hệt
prompt trước E31 — để lượt dịch không có thuật ngữ hành xử y như cũ, không có nhánh nào đổi âm
thầm.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CharacterVoiceProfile, GlossaryEntry, OCRResult, Page, TextRegion, TranslationResult
from app.models.enums import GlossaryStatus, OCRStatus, TranslationStatus, VoiceProfileStatus

#: Chặn prompt phình vô hạn. Chapter dài có thể có hàng trăm thuật ngữ, mà mỗi token trong prompt
#: đều tính tiền ở MỌI trang. Lấy theo thứ tự bảng chữ cái để lượt nào cũng ra cùng một tập —
#: cắt theo thứ tự ngẫu nhiên thì trang này thấy thuật ngữ A, trang kia thấy thuật ngữ B, và nhất
#: quán xuyên trang — đúng thứ module này sinh ra để lo — lại vỡ.
SO_THUAT_NGU_TOI_DA = 60
SO_NHAN_VAT_TOI_DA = 20
#: E95 — số cặp câu thoại (gốc → dịch) tối đa lấy từ trang liền trước làm ngữ cảnh trượt liên trang.
SO_CAU_TRANG_TRUOC_TOI_DA = 8


def _dong_thuat_ngu(e: GlossaryEntry) -> str:
    phan = [f"- {e.source_term} → {e.target_term}"]
    if e.term_type is not None:
        phan.append(f"({e.term_type.value})")
    if e.prohibited_variants:
        phan.append("— KHÔNG dùng: " + ", ".join(str(v) for v in e.prohibited_variants[:5]))
    return " ".join(phan)


def _dong_nhan_vat(v: CharacterVoiceProfile) -> str:
    phan = [f"- {v.character_name}"]
    if v.aliases:
        phan.append("(còn gọi: " + ", ".join(str(a) for a in v.aliases[:4]) + ")")
    if v.speech_register is not None:
        phan.append(f"giọng {v.speech_register.value}")
    if v.vietnamese_pronoun_guidance:
        phan.append(f"— xưng hô: {v.vietnamese_pronoun_guidance}")
    if v.tone_note:
        phan.append(f"— {v.tone_note}")
    return " ".join(phan)


def nap_boi_canh_trang_truoc(
    session: Session,
    project_id: uuid.UUID,
    page_id: uuid.UUID,
    so_cau_toi_da: int = SO_CAU_TRANG_TRUOC_TOI_DA,
) -> list[tuple[str, str]]:
    """E95 — Lấy các cặp `(chữ gốc, bản dịch)` sạch của trang liền trước trong cùng chapter.

    Giải quyết bài toán đọc liên tục nhiều trang trên tiện ích (`doc-truyen`): người dùng không
    vào trang quản trị để duyệt bảng thuật ngữ trước, nên nếu trang N không thấy trang N-1 đã dịch
    thế nào thì đại từ xưng hô (*Ta – bà*, *Anh – em*) và cách phiên âm tên riêng sẽ bị nhảy giữa
    các trang.

    Chỉ lấy các câu thoả mãn CẢ HAI điều kiện:
    1. `OCRResult.status == OCRStatus.ok` (không lấy câu bị đánh dấu `needs_manual` / đoán mò `[?]`).
    2. `TranslationResult.status == TranslationStatus.ok` (không lấy bản dịch lùi `fallback_used`).
    """
    if so_cau_toi_da <= 0:
        return []
    trang_hien_tai = session.get(Page, page_id)
    if trang_hien_tai is None or trang_hien_tai.project_id != project_id:
        return []

    cac_trang_truoc = list(
        session.scalars(
            select(Page)
            .where(
                Page.project_id == project_id,
                Page.id != page_id,
                Page.order <= trang_hien_tai.order,
            )
            .order_by(Page.order.desc(), Page.created_at.desc())
            .limit(2)
        )
    )
    if not cac_trang_truoc:
        return []

    id_trang_truoc = [p.id for p in reversed(cac_trang_truoc)]
    rows = session.execute(
        select(OCRResult.raw_text, TranslationResult.translated_text)
        .join(TextRegion, TextRegion.id == OCRResult.region_id)
        .join(TranslationResult, TranslationResult.region_id == TextRegion.id)
        .join(Page, Page.id == TextRegion.page_id)
        .where(
            TextRegion.page_id.in_(id_trang_truoc),
            OCRResult.status == OCRStatus.ok,
            TranslationResult.status == TranslationStatus.ok,
        )
        .order_by(
            Page.order.asc(),
            Page.created_at.asc(),
            TextRegion.reading_order.nulls_last(),
            TextRegion.created_at.asc(),
        )
    ).all()

    cap_hop_le: list[tuple[str, str]] = []
    for chu_goc, ban_dich in rows:
        goc = " ".join((chu_goc or "").splitlines()).strip()
        dich = " ".join((ban_dich or "").splitlines()).strip()
        if goc and dich:
            cap_hop_le.append((goc, dich))
    return cap_hop_le[-so_cau_toi_da:]


def nap_boi_canh_du_an(
    session: Session,
    project_id: uuid.UUID,
    page_id: uuid.UUID | None = None,
    *,
    kem_trang_truoc: bool = True,
) -> str:
    """Khối chữ mô tả thuật ngữ + giọng nhân vật ĐÃ CHỐT của project (+ thoại trang liền trước).

    Trả chuỗi rỗng khi chưa có gì được chốt và không có ngữ cảnh trang trước — bên gọi nối thẳng
    vào prompt, nên chuỗi rỗng nghĩa là prompt không đổi một ký tự nào so với trước E31.
    """
    thuat_ngu = list(
        session.scalars(
            select(GlossaryEntry)
            .where(
                GlossaryEntry.project_id == project_id,
                GlossaryEntry.status == GlossaryStatus.approved,
            )
            .order_by(GlossaryEntry.source_term_key)
            .limit(SO_THUAT_NGU_TOI_DA)
        )
    )
    nhan_vat = list(
        session.scalars(
            select(CharacterVoiceProfile)
            .where(
                CharacterVoiceProfile.project_id == project_id,
                CharacterVoiceProfile.status == VoiceProfileStatus.active,
            )
            .order_by(CharacterVoiceProfile.character_name_key)
            .limit(SO_NHAN_VAT_TOI_DA)
        )
    )
    thoai_trang_truoc = (
        nap_boi_canh_trang_truoc(session, project_id, page_id)
        if page_id is not None and kem_trang_truoc
        else []
    )
    if not thuat_ngu and not nhan_vat and not thoai_trang_truoc:
        return ""

    khoi: list[str] = []
    if thuat_ngu:
        khoi.append(
            "### Thuật ngữ đã chốt cho bộ truyện này — BẮT BUỘC dùng đúng, không tự đổi cách dịch:"
        )
        khoi.extend(_dong_thuat_ngu(e) for e in thuat_ngu)
    if nhan_vat:
        if khoi:
            khoi.append("")
        khoi.append("### Giọng và xưng hô của nhân vật — giữ đúng khi câu đó là lời của họ:")
        khoi.extend(_dong_nhan_vat(v) for v in nhan_vat)
    if thoai_trang_truoc:
        if khoi:
            khoi.append("")
        khoi.append(
            "### Thoại đã dịch ở trang liền trước — tham khảo để giữ ĐỒNG NHẤT đại từ xưng hô "
            "(Ta/Bà/Tôi/Cậu…) và cách dịch tên riêng sang trang này:"
        )
        khoi.extend(f"- {goc} → {dich}" for goc, dich in thoai_trang_truoc)
    return "\n".join(khoi)
