"""Đặt tên file xuất — phải an toàn với mọi hệ tệp (M8 constraint 8).

Tên project là tiếng Việt có dấu và có thể chứa `/`, `:`… Đưa thẳng vào tên file là hỏng
đường dẫn hoặc tạo file rác ở chỗ không ngờ.
"""
from __future__ import annotations

import re
import unicodedata

#: Tên rỗng sau khi lọc (ví dụ project tên toàn ký tự lạ) vẫn phải ra một tên dùng được.
_MAC_DINH = "chapter"
_DAI_TOI_DA = 80


def slugify(text: str) -> str:
    """Bỏ dấu tiếng Việt, hạ chữ thường, chỉ giữ [a-z0-9_], gộp gạch dưới.

    Cố ý KHÔNG giữ dấu tiếng Việt trong tên file: file này còn được tải về máy khác, nhét vào
    ứng dụng đọc truyện, hoặc đi qua hệ tệp không hỗ trợ Unicode.
    """
    text = unicodedata.normalize("NFD", text or "")
    # `đ`/`Đ` không tách được bằng NFD nên phải thay tay.
    text = text.replace("đ", "d").replace("Đ", "D")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()
    text = re.sub(r"_+", "_", text)[:_DAI_TOI_DA].strip("_")
    return text or _MAC_DINH


def ten_file_export(project_name: str, duoi: str) -> str:
    """`Truyện Hay #1` + `cbz` -> `truyen_hay_1_chapter.cbz`.

    Tên đã kết thúc bằng `chapter` thì không nối thêm nữa, tránh `..._chapter_chapter.cbz`.
    """
    ten = slugify(project_name)
    if not ten.endswith("chapter"):
        ten = f"{ten}_chapter"
    return f"{ten}.{duoi}"
