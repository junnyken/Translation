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
        """Ngắt dòng theo bề rộng pixel. Giữ chữ ký cũ — trả về CHUỖI."""
        return self.wrap_bao_cat_tu(text, font, max_width)[0]

    def wrap_bao_cat_tu(
        self, text: str, font: ImageFont.FreeTypeFont, max_width: int
    ) -> tuple[str, bool]:
        """Như `wrap_to_width` nhưng trả thêm **có phải cắt GIỮA TỪ hay không** (E60).

        ## Vì sao cần biết điều đó

        Cắt theo ký tự làm bề rộng **luôn vừa**, nên phép kiểm `w <= rect.width` của bộ căn cỡ chữ
        gần như luôn qua — bộ căn **không bao giờ nhìn thấy** rằng khung quá hẹp. Nó chỉ thấy chiều
        cao sai, bèn thu nhỏ cỡ chữ, và cho ra chữ bé tí **vẫn vỡ từng ký tự**.

        Đo trên trang manga thật (chủ dự án gửi 28-09-2026): bong bóng **dọc hẹp** kiểu Nhật làm
        `max_width` rất nhỏ, nên từ tiếng Việt bình thường cũng rơi vào nhánh cắt ký tự —
        `VÒNG QUA` thành `VỌN / G QUA`, `TRẮNG` thành `TRẢ / NG`. Nhánh dự phòng viết cho "URL, tên
        chiêu thức" trở thành đường đi CHÍNH.

        Với chữ Việt, cắt giữa từ là **hỏng nội dung**, không phải "hơi xấu": từ tiếng Việt ngắn và
        có dấu, cắt ra là mất nghĩa hoàn toàn. Người đọc thà đọc chữ nhỏ còn hơn đọc `VỌN G`.

        ⇒ Bên gọi dùng cờ này để coi cỡ chữ đó là **chưa vừa** và tiếp tục thu nhỏ. Chỉ khi đã tới
        cỡ nhỏ nhất mà vẫn phải cắt thì mới chấp nhận cắt, và lúc đó gắn cảnh báo tràn.

        Ký tự xuống dòng có sẵn trong bản dịch được **giữ nguyên** làm ngắt cứng.
        """
        text = normalize_for_layout(text)
        if not text.strip():
            return "", False
        if max_width <= 0:
            return text, False

        da_cat_tu = False
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
                # Token đơn lẻ vẫn quá rộng -> cắt theo ký tự, và NÓI RA là đã phải cắt.
                if font.getlength(tu) > max_width:
                    da_cat_tu = True
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
        return "\n".join(lines), da_cat_tu

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
