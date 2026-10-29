"""Whitelist font — module này CỐ Ý không import Pillow.

API cần đọc danh sách font hợp lệ (M7: dropdown chọn font, validate PATCH) nhưng **không được
nạp engine render**. Vì vậy bảng đăng ký tách khỏi `fonts.py`.
"""
from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class FontSpec:
    #: Đường dẫn tương đối trong FONT_DIR.
    relative_path: str
    #: Tên nét của font biến thiên. BẪY: file nghiêng dùng tên "Bold Italic", KHÔNG phải "Bold".
    variation: str | None = None


#: Whitelist family → file. Thêm font mới PHẢI kèm test `test_fonts_vietnamese.py` (đủ 134 dấu).
FONT_REGISTRY: dict[str, FontSpec] = {
    "Bangers": FontSpec("Bangers/Bangers-Regular.ttf"),
    "ShantellSans": FontSpec("ShantellSans/ShantellSans-Roman-VF.ttf", "Regular"),
    "ShantellSans-Bold": FontSpec("ShantellSans/ShantellSans-Roman-VF.ttf", "Bold"),
    "ShantellSans-Italic": FontSpec("ShantellSans/ShantellSans-Italic-VF.ttf", "Italic"),
    "ShantellSans-BoldItalic": FontSpec("ShantellSans/ShantellSans-Italic-VF.ttf", "Bold Italic"),
    "Mansalva": FontSpec("Mansalva/Mansalva-Regular.ttf"),
    "SigmarOne": FontSpec("SigmarOne/SigmarOne-Regular.ttf"),
}
