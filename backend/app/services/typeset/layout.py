"""Ngắt dòng và đo kích thước text theo **font metrics thật** (M6 constraint 2).

Không bao giờ ước lượng theo số ký tự: chữ cái tiếng Việt có dấu chồng làm chiều cao dòng
khác hẳn tiếng Anh, và font truyện tranh có kerning riêng. Dùng `ImageFont.getlength` và
`ImageDraw.multiline_textbbox` — cả hai trả số đo **pixel**.
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from app.services.typeset.fonts import normalize_for_layout

#: Canvas 1x1 dùng chung để đo — `multiline_textbbox` không cần vùng vẽ thật.
_MEASURE_DRAW = ImageDraw.Draw(Image.new("L", (1, 1)))


class TextLayoutEngine:
    """Ngắt dòng + đo khối nhiều dòng. Không đụng DB, không render — thuần để test đơn vị."""

    def wrap_to_width(self, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:
        """Ngắt dòng theo bề rộng pixel. Ưu tiên ngắt ở khoảng trắng.

        Token dài quá khổ (URL, tên chiêu thức) được cắt theo **ký tự** để không vượt bề rộng —
        đây là thêm ký tự xuống dòng, KHÔNG sửa nội dung text.
        Ký tự xuống dòng có sẵn trong bản dịch được **giữ nguyên** làm ngắt cứng.
        """
        text = normalize_for_layout(text)
        if not text.strip():
            return ""
        if max_width <= 0:
            return text

        lines: list[str] = []
        for doan in text.split("\n"):
            if not doan.strip():
                lines.append("")
                continue
            dong_hien_tai = ""
            for tu in doan.split():
                thu = f"{dong_hien_tai} {tu}".strip()
                if font.getlength(thu) <= max_width:
                    dong_hien_tai = thu
                    continue
                if dong_hien_tai:
                    lines.append(dong_hien_tai)
                    dong_hien_tai = ""
                # Token đơn lẻ vẫn quá rộng -> cắt theo ký tự.
                if font.getlength(tu) > max_width:
                    phan = ""
                    for ky_tu in tu:
                        if phan and font.getlength(phan + ky_tu) > max_width:
                            lines.append(phan)
                            phan = ky_tu
                        else:
                            phan += ky_tu
                    dong_hien_tai = phan
                else:
                    dong_hien_tai = tu
            if dong_hien_tai:
                lines.append(dong_hien_tai)
        return "\n".join(lines)

    def measure_multiline(
        self,
        wrapped_text: str,
        font: ImageFont.FreeTypeFont,
        spacing: int = 0,
        stroke_width: int = 0,
    ) -> tuple[int, int]:
        """Trả (rộng, cao) pixel của cả khối, đã tính khoảng cách dòng + viền chữ.

        Dùng `multiline_textbbox` chứ không cộng tay từng dòng: hàm này tính đúng cả phần
        nhô lên của dấu (accent) và phần thò xuống (descender).
        """
        if not wrapped_text:
            return 0, 0
        left, top, right, bottom = _MEASURE_DRAW.multiline_textbbox(
            (0, 0),
            wrapped_text,
            font=font,
            spacing=spacing,
            stroke_width=stroke_width,
            align="center",
        )
        return int(right - left), int(bottom - top)
