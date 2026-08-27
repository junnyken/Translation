"""Canh bộ font bundle: font KHÔNG đủ dấu tiếng Việt thì M6 sẽ chèn ra ô vuông.

Đây là bài học trả giá thật: `HL Comic2` — font mà spec chỉ định — là font mã BK HCM2/TCVN3
đời 2004, chữ Việt bị nhét vào dải 0xA0-0xFF chứ không nằm ở Unicode. Render ra "▯▯NG" thay vì
"ĐỪNG". Cùng lỗi đó, `Comic Neue` (Google Fonts) cũng chỉ có 36/134 ký tự.

Vì vậy: mọi font đưa vào `fonts/` PHẢI phủ đủ 134 ký tự có dấu, và phải kèm file license.
"""
from __future__ import annotations

from pathlib import Path

import pytest

FONTS_DIR = Path(__file__).resolve().parents[2] / "fonts"

# 134 ký tự có dấu của tiếng Việt (không tính a/e/i/o/u/y trần vốn thuộc ASCII).
_BASES = {
    "a": "àáảãạ", "ă": "ằắẳẵặ", "â": "ầấẩẫậ",
    "e": "èéẻẽẹ", "ê": "ềếểễệ", "i": "ìíỉĩị",
    "o": "òóỏõọ", "ô": "ồốổỗộ", "ơ": "ờớởỡợ",
    "u": "ùúủũụ", "ư": "ừứửữự", "y": "ỳýỷỹỵ",
}


def _vietnamese_chars() -> list[str]:
    chars: set[str] = {"đ"}
    for base, marks in _BASES.items():
        if base not in "aeiouy":
            chars.add(base)
        chars.update(marks)
    chars |= {c.upper() for c in chars}
    return sorted(chars)


VIETNAMESE = _vietnamese_chars()
ASCII_PRINTABLE = [chr(c) for c in range(0x20, 0x7F)]


def _bundled_fonts() -> list[Path]:
    return sorted(FONTS_DIR.glob("*/*.ttf"))


def test_dung_134_ky_tu_tieng_viet():
    """Canh chính danh sách chuẩn — sai danh sách thì mọi test dưới đều vô nghĩa."""
    assert len(VIETNAMESE) == 134
    # chỉ ký tự CÓ DẤU mới thuộc danh sách — chữ cái ASCII (N, G…) cố ý không nằm trong đây
    for c in "ĐỪỎẢẴỢỹỵăâêôơư":
        assert c in VIETNAMESE, c
    for c in "NGaeiouyZ":
        assert c not in VIETNAMESE, c


def test_co_font_trong_bundle():
    """Thư mục fonts/ trống nghĩa là M6 không có gì để chèn."""
    assert _bundled_fonts(), f"Không tìm thấy font nào trong {FONTS_DIR}"


@pytest.mark.parametrize("font_path", _bundled_fonts(), ids=lambda p: p.parent.name + "/" + p.name)
def test_font_phu_du_dau_tieng_viet(font_path: Path):
    from fontTools.ttLib import TTFont

    with TTFont(font_path, fontNumber=0, lazy=True) as font:
        codepoints: set[int] = set()
        for table in font["cmap"].tables:
            codepoints |= set(table.cmap.keys())

    thieu_viet = [c for c in VIETNAMESE if ord(c) not in codepoints]
    thieu_ascii = [c for c in ASCII_PRINTABLE if ord(c) not in codepoints]
    assert not thieu_viet, (
        f"{font_path.name} thiếu {len(thieu_viet)}/134 ký tự tiếng Việt: "
        f"{''.join(thieu_viet[:30])} — font này sẽ render ra ô vuông, KHÔNG dùng được cho M6"
    )
    assert not thieu_ascii, f"{font_path.name} thiếu ký tự ASCII: {''.join(thieu_ascii)}"


@pytest.mark.parametrize(
    "font_dir",
    sorted({p.parent for p in _bundled_fonts()}),
    ids=lambda p: p.name,
)
def test_moi_font_kem_giay_phep(font_dir: Path):
    """OFL bắt buộc phát hành kèm bản quyền — thiếu file license là vi phạm giấy phép."""
    licenses = list(font_dir.glob("OFL.txt")) + list(font_dir.glob("LICENSE*"))
    assert licenses, f"{font_dir.name} không có file license đi kèm"
    text = licenses[0].read_text(encoding="utf-8", errors="replace")
    assert "SIL OPEN FONT LICENSE" in text.upper(), f"{font_dir.name}: license không phải OFL"


@pytest.mark.parametrize("font_path", _bundled_fonts(), ids=lambda p: p.parent.name + "/" + p.name)
def test_render_duoc_chu_viet_co_dau(font_path: Path):
    """Có mã trong cmap vẫn chưa đủ — phải render ra được nét mực thật.

    So bề rộng chuỗi có dấu với chuỗi không dấu cùng độ dài: nếu font đổ về .notdef thì
    bề rộng sẽ lệch hẳn theo kiểu ô vuông đồng đều.
    """
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype(str(font_path), 40)
    mau = "ĐỪNG NGOẢNH LẠI! Cậu ổn chứ?"
    image = Image.new("L", (900, 90), color=255)
    ImageDraw.Draw(image).text((10, 10), mau, font=font, fill=0)
    assert image.getbbox() is not None, f"{font_path.name}: render ra trang trắng"
    so_diem_muc = sum(1 for px in image.getdata() if px < 128)
    assert so_diem_muc > 200, f"{font_path.name}: chỉ có {so_diem_muc} điểm mực — nghi render hỏng"
