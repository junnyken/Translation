"""E26-A — gộp dòng của `raw_text` trước khi gửi đi dịch.

## Vì sao

Dấu xuống dòng trong `raw_text` là **chỗ chữ ngắt dòng trong bong bóng**, không mang nghĩa. Nhưng
nó được truyền thẳng cho bộ dịch, và Google Translate coi mỗi dòng là một câu riêng. Đo thật
(2026-09-11, trang `en_E12P01` của Pepper&Carrot):

| Gửi kèm `\\n` (hiện trạng) | Gộp dòng trước khi gửi |
|---|---|
| `... chỉ kể tên thôi\\nmột vài!` — **vô nghĩa** | `... chỉ kể tên một vài!` |
| `nó sẽ không tốt cho\\nnhững kẻ thích đùa nhỏ để tìm thấy nó` | `sẽ không tốt nếu những kẻ thích đùa tìm thấy nó` |
| `Tôi cần phải đi đến\\nchợ ở Komona.` | `Tôi cần đi chợ ở Komona.` |

7/14 vùng của trang đó là nhiều dòng ⇒ khoảng một nửa số thoại bị ảnh hưởng.

## KHÔNG sửa `raw_text` trong CSDL

E21 cho người dùng **gõ đè** `raw_text` khi OCR đọc sai; nó là bản ghi *"máy đọc được gì / người
sửa thành gì"*. Đổi nó ở đây là phá hợp đồng đó và làm người dùng thấy chữ khác cái họ đã gõ. Việc
gộp chỉ xảy ra **trên đường gửi đi dịch**.

Bước căn chữ (M6) vốn **tự ngắt dòng lại** theo khung, nên gộp ở đây không mất gì.

## Vì sao nối bằng DẤU CÁCH chứ không xoá trắng

Chữ Latin cần dấu cách giữa hai từ bị ngắt dòng (`to name just` + `a few` -> `to name just a few`).
Với tiếng Nhật/Trung thì dấu cách là dư, nhưng **vô hại**: cả hai engine dịch đều bỏ qua khoảng
trắng thừa, còn nối liền chữ Latin thì tạo ra từ không tồn tại (`justa`). Sai một chiều thì vô hại,
sai chiều kia thì hỏng nghĩa — nên chọn chiều vô hại.

## Giữ lại ranh giới CÂU

Dòng kết thúc bằng dấu câu (`.` `!` `?` `:` `…` và bản full-width) **được giữ dấu xuống dòng**: đó
là ranh giới câu thật, không phải chỗ bong bóng ngắt. Gộp cả những chỗ đó lại thì hai câu rời dính
thành một câu dài, và bộ dịch mất đúng thông tin nó cần để chấm câu.
"""
from __future__ import annotations

import re

#: Dấu câu kết thúc một câu — gồm cả bản full-width của tiếng Nhật/Trung.
_KET_CAU = ".!?:;…。！？：；"

_NHIEU_KHOANG_TRANG = re.compile(r"[ \t]+")


def gop_dong_de_dich(text: str) -> str:
    """Gộp các dòng bị bong bóng ngắt, GIỮ dấu xuống dòng ở ranh giới câu thật.

    >>> gop_dong_de_dich("... to name just\\na few!")
    '... to name just a few!'
    >>> gop_dong_de_dich("Exactly.\\nAs well it should be.")
    'Exactly.\\nAs well it should be.'
    >>> gop_dong_de_dich("")
    ''
    """
    if not text or "\n" not in text:
        return text or ""

    dong = [d.strip() for d in text.split("\n")]
    ra: list[str] = []
    for d in dong:
        if not d:
            continue  # dòng trống: bỏ, nó không mang nghĩa lẫn ranh giới
        if ra and not ra[-1].rstrip().endswith(tuple(_KET_CAU)):
            ra[-1] = f"{ra[-1]} {d}"
        else:
            ra.append(d)
    return _NHIEU_KHOANG_TRANG.sub(" ", "\n".join(ra)).strip()
