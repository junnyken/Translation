"""E34 — chỉ gửi ảnh cho trang THẬT SỰ cần, thay vì mọi trang.

## Số đo làm nền

E32 đo được ảnh tốn gần như **cố định +1166 token/trang** (`prompt` 383→1549 ở trang EN,
215→1381 ở trang JA). Nhưng **lợi ích không rải đều**: nó dồn vào trang bộ đọc chữ làm kém —
ca rõ nhất là `どなどは` (rác hoàn toàn) chỉ được sửa thành `Đổ ào ào` khi có ảnh.

Trả +1166 token cho trang mà OCR đã đọc sạch là trả tiền cho thứ không đổi gì.

```
24 trang, chỉ chữ            9.600 token
24 trang, ảnh MỌI trang     37.584 token
24 trang, ảnh 5 trang       15.430 token      -> tiết kiệm 22.154 (59%)
```

## Vì sao CHỈ dùng cờ đã tồn tại, chưa dò "chuỗi rác"

Cách hiển nhiên là dò chuỗi rác bằng danh sách mẫu (`どなどは`, `Luughing Fotlons`…). Tôi cố ý
**không** làm: đó là mấy mẫu tình cờ gặp, không phải luật. Danh sách cứng bỏ sót mọi chuỗi rác
khác và không bao giờ tự phát hiện ca mới — mã trông như có tác dụng mà không ai đo được.

Ba cờ dưới đây là **tín hiệu thật đã có trong CSDL**, do chính pipeline ghi ra:

| Cờ | Nghĩa |
|---|---|
| `PageStatus.inpaint_needs_review` | bước xoá chữ tự thấy kết quả đáng ngờ |
| `RegionStatus.low_confidence` | bộ đọc chữ trả điểm tin cậy thấp |
| `OCRStatus.needs_manual` | bộ đọc không ra chữ có nghĩa |

Bước tiếp theo (sau khi ĐO) là xem ba cờ này bỏ sót bao nhiêu trang OCR kém thật. Chỉ khi có số
đó mới đáng thêm luật mới.

## GIỚI HẠN ĐO ĐƯỢC: tiếng Nhật không tiết kiệm được gì

```
ja / manga_ocr    16 vùng    0 vùng có điểm tin cậy     8 low_confidence
en / paddle_ocr  220 vùng  218 vùng có điểm tin cậy    27 low_confidence
```

`manga-ocr` **không trả điểm tin cậy cho vùng nào** (0/16). Nên với tiếng Nhật, `low_confidence`
**không đến từ điểm tin cậy** — nó là cờ suy từ tiêu chí dự phòng (chữ rỗng / không có ký tự có
nghĩa). Một cờ suy từ phép đo **không tồn tại** thì không mang thông tin về chất lượng đọc chữ.

Kết quả: tỉ lệ vùng bị cờ ở trang tiếng Nhật là 33%, 33%, 50%, 63% — **mọi** ngưỡng còn giữ được
ca `どなどは` (33%) cũng sẽ bật cho cả ba trang kia. Nên **E34 không tiết kiệm token cho tiếng
Nhật**, và đó là giới hạn của dữ liệu, không phải của luật.

Muốn tiết kiệm cho tiếng Nhật thì phải có một tín hiệu chất lượng đọc chữ THẬT — ví dụ chạy
PaddleOCR `lang='japan'` song song chỉ để lấy điểm tin cậy. Việc đó cần bằng chứng riêng.

## Trả kèm LÝ DO, không chỉ true/false

Bên gọi ghi lý do vào log. Không có lý do thì sau này không ai biết trang nào được gửi ảnh vì cờ
nào, và câu hỏi "cờ nào đáng giữ" thành không trả lời được.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import OCRResult, Page, TextRegion
from app.models.enums import OCRStatus, PageStatus, RegionStatus


#: Bao nhiêu phần vùng của trang phải bị gắn cờ thì mới gửi ảnh.
#:
#: **Luật "có MỘT vùng bị cờ" của bản spec đầu tự bão hoà** — đo được: 12% vùng tiếng Anh bị cờ,
#: ~9 vùng/trang ⇒ `1-(0.88^9) ≈ 68%` trang bật (đo thật 50%). Chọn lọc kiểu đó gần bằng gửi hết.
#:
#: Con số 0.3 **neo vào ca duy nhất chứng minh được ảnh có tác dụng**: trang tiếng Nhật có
#: `どなどは` (OCR đọc rác, chỉ ảnh sửa được thành `Đổ ào ào`) có tỉ lệ đúng **33%**. Ngưỡng 0.5 —
#: trông chặt chẽ hơn — sẽ **loại bỏ chính ca đó**, tức bỏ đi lý do duy nhất để làm E32.
#:
#: Đo trên dữ liệu thật với ngưỡng này:
#:
#:     tiếng Anh   9/34 trang = 26%   (so với 50% của luật "có một vùng")
#:     tiếng Nhật  4/4  trang = 100%  -> KHÔNG tiết kiệm được gì, xem chú thích dưới
TI_LE_DANG_NGO_TOI_THIEU = 0.3


def can_gui_anh(session: Session, page_id: uuid.UUID) -> tuple[bool, str]:
    """`(có nên gửi ảnh, lý do)`. Không có cờ nào ⇒ `(False, "khong_co_dau_hieu")`.

    Thiếu dữ liệu (trang không tồn tại) ⇒ **không** gửi: thiếu bằng chứng thì không tiêu token,
    chứ không đoán.
    """
    page = session.get(Page, page_id)
    if page is None:
        return False, "khong_thay_trang"

    if page.status is PageStatus.inpaint_needs_review:
        return True, "inpaint_needs_review"

    vung_ids = list(
        session.scalars(select(TextRegion.id).where(TextRegion.page_id == page_id))
    )
    if not vung_ids:
        return False, "trang_khong_co_vung"

    dang_ngo = len(set(
        list(session.scalars(
            select(TextRegion.id).where(
                TextRegion.id.in_(vung_ids),
                TextRegion.status == RegionStatus.low_confidence,
            )
        ))
        + list(session.scalars(
            select(OCRResult.region_id).where(
                OCRResult.region_id.in_(vung_ids),
                OCRResult.status == OCRStatus.needs_manual,
            )
        ))
    ))
    ti_le = dang_ngo / len(vung_ids)
    if ti_le >= TI_LE_DANG_NGO_TOI_THIEU:
        return True, f"ti_le_dang_ngo_{ti_le:.0%}"
    return False, f"du_sach_{ti_le:.0%}"
