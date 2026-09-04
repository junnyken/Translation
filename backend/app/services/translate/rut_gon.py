"""Dịch lại NGẮN HƠN cho vừa bong bóng (E18).

## Vì sao có bước này

Bong bóng manga được vẽ vừa đúng lượng chữ tiếng Nhật. Bản dịch tiếng Việt dài gấp hai ba lần
là chuyện thường — đo trên trang thật 04/09: một bong bóng chứa ~30 ký tự Nhật nhận về bản dịch
**105 ký tự**, và tràn khung kể cả sau khi đã nới khung hết cỡ (A1).

Tới đó thì **không có cách xếp chữ nào cứu được nữa**: chữ dài hơn chỗ chứa là chuyện vật lý.
Chỗ duy nhất còn sửa được là **chính bản dịch** — và bước dịch hiện không hề biết bong bóng to
bao nhiêu, nó dịch xong rồi mới có người đi tìm chỗ nhét.

## Ranh giới

- **Không tự chạy.** Rút gọn là làm mất chữ của bản dịch đầy đủ, nên phải do người dùng bấm.
- **Không đụng vùng người dùng đã sửa tay.** Đè lên chữ người ta tự gõ là việc không ai xin.
- **Không hứa là sẽ vừa.** Rút gọn xong vẫn chạy `fit()` thật; vẫn tràn thì vẫn báo tràn.
- **Đưa cả chữ gốc vào prompt**: để model dịch lại cho gọn theo nghĩa gốc, chứ không phải cắt
  cụt câu tiếng Việt đang có — cắt cụt thì mất nghĩa mà vẫn sai.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

#: `số. <bản dịch ngắn>` — cùng khuôn với các prompt khác của hệ thống.
_DONG = re.compile(r"^(\d{1,3})\s*[.)\]-]\s*(.*)$")


@dataclass(frozen=True)
class MucRutGon:
    """Một vùng cần rút gọn: chữ gốc, bản dịch hiện tại, và sức chứa đo được."""

    chu_goc: str
    ban_dich: str
    suc_chua: int


def dung_prompt(muc: list[MucRutGon], source_lang: str) -> str:
    danh_sach = "\n".join(
        f"{i + 1}. [tối đa {m.suc_chua} ký tự] gốc: {m.chu_goc or '(không đọc được)'}\n"
        f"   bản dịch hiện tại ({len(m.ban_dich)} ký tự): {m.ban_dich}"
        for i, m in enumerate(muc)
    )
    return (
        "Bạn là biên tập viên truyện tranh tiếng Việt.\n\n"
        "Những câu thoại dưới đây **dài hơn bong bóng chứa được**, nên đang bị tràn ra ngoài "
        "khung. Hãy viết lại NGẮN HƠN cho vừa, dựa vào chữ gốc.\n\n"
        "Quy tắc bắt buộc:\n"
        f"- Trả về ĐÚNG {len(muc)} dòng, đánh số 1..{len(muc)} theo đúng thứ tự đầu vào.\n"
        "- Mỗi dòng KHÔNG vượt quá số ký tự ghi trong ngoặc vuông của mục đó.\n"
        "- Giữ ĐÚNG Ý và giọng điệu nhân vật. Được bỏ từ đệm, gộp câu, dùng từ ngắn hơn; "
        "KHÔNG được bỏ mất thông tin chính (tên riêng, con số, câu hỏi vẫn phải là câu hỏi).\n"
        "- Thoại truyện tranh vốn ngắn gọn — viết như người Việt nói, không viết văn.\n"
        "- Nếu bản dịch hiện tại đã đủ ngắn, chép lại nguyên văn.\n"
        "- Không thêm giải thích, không thêm dòng nào ngoài danh sách đã đánh số.\n\n"
        f"### Ngôn ngữ gốc: {source_lang}\n{danh_sach}"
    )


def phan_tich(text: str, muc: list[MucRutGon]) -> list[str | None]:
    """Tách phản hồi thành đúng `len(muc)` phần tử. `None` = KHÔNG dùng được, giữ bản cũ.

    Bị loại khi: thiếu dòng · dòng rỗng · **dài hơn bản dịch hiện tại** (model viết dài thêm thì
    rút gọn không còn nghĩa gì).

    Cố ý KHÔNG loại dòng chỉ vì vượt quá sức chứa vài ký tự: sức chứa là ước lượng, còn bên có
    thẩm quyền nói vừa hay không là `fit()` chạy ngay sau đó. Loại ở đây là vứt đi một bản dịch
    ngắn hơn hẳn chỉ vì lệch con số ước lượng.
    """
    thu: dict[int, str] = {}
    for raw in (text or "").splitlines():
        dong = raw.strip()
        if not dong or dong.startswith("#"):
            continue
        m = _DONG.match(dong)
        if not m:
            continue
        i = int(m.group(1))
        if 1 <= i <= len(muc):
            thu[i] = m.group(2).strip()

    ket: list[str | None] = []
    for i, cu in enumerate(muc, start=1):
        moi = thu.get(i, "")
        if not moi or len(moi) >= len(cu.ban_dich):
            ket.append(None)
        else:
            ket.append(moi)
    return ket
