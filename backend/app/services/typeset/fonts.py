"""Chọn file font theo tên family — whitelist, KHÔNG hard-code đường dẫn (M6 constraint 5).

Vì sao phải whitelist thay vì quét bừa thư mục: font binary có giấy phép riêng, và
**nhiều font truyện tranh không đủ glyph tiếng Việt** — render ra ô vuông mà không báo lỗi.
Xem `docs/FONTS.md`: font `HL Comic2` mà spec chỉ định chỉ có 38/134 ký tự có dấu.
Vì vậy font sai/thiếu phải là **lỗi quan sát được**, không im lặng đổi font khác.
"""
from __future__ import annotations

import logging
import threading
import unicodedata
from pathlib import Path

from PIL import ImageFont

logger = logging.getLogger(__name__)


class FontNotFound(RuntimeError):
    """Family không nằm trong whitelist, hoặc file font không có trên đĩa."""


class MissingGlyph(RuntimeError):
    """Font thiếu glyph cho ký tự trong text — render sẽ ra ô vuông (tofu)."""


from app.services.typeset.registry import FONT_REGISTRY, FontSpec

#: Ký tự chắc chắn không font nào có glyph — dùng làm mẫu đối chiếu để phát hiện tofu.
_SENTINEL = ""


def normalize_for_layout(text: str) -> str:
    """Đưa về NFC **chỉ để đo/vẽ** — không bao giờ ghi ngược lại `TranslationResult`.

    Đo thật trong worker (Pillow không có raqm): chuỗi NFD render sai hẳn — `ĐỪNG` ra `ĐUNG`,
    `LẠI` ra `LAỊ` — mà `getlength()` vẫn trả **đúng con số của NFC**, nên sai không lộ ra qua
    phép đo. NFC và NFD là cùng một văn bản theo chuẩn Unicode nên đây không phải sửa nội dung.
    """
    return unicodedata.normalize("NFC", text or "")


class FontResolver:
    """Map family → `ImageFont.FreeTypeFont`. Có cache vì nạp font là việc tốn kém."""

    def __init__(
        self,
        font_dir: str,
        default_family: str,
        allow_fallback: bool = False,
    ) -> None:
        self.font_dir = Path(font_dir)
        self.default_family = default_family
        self.allow_fallback = allow_fallback
        self._cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}
        self._lock = threading.Lock()

    def known_families(self) -> list[str]:
        return sorted(FONT_REGISTRY)

    def path_for(self, family: str) -> Path:
        spec = FONT_REGISTRY.get(family)
        if spec is None:
            raise FontNotFound(
                f"font_not_found: family '{family}' không nằm trong whitelist "
                f"({', '.join(self.known_families())})"
            )
        path = self.font_dir / spec.relative_path
        if not path.is_file():
            raise FontNotFound(
                f"font_not_found: family '{family}' có trong whitelist nhưng thiếu file "
                f"'{path}'. Kiểm tra FONT_DIR và volume mount của worker."
            )
        return path

    def resolve(self, family: str, size: int) -> ImageFont.FreeTypeFont:
        key = (family, int(size))
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        try:
            path = self.path_for(family)
            spec = FONT_REGISTRY[family]
        except FontNotFound:
            if not (self.allow_fallback and family != self.default_family):
                raise
            # Chỉ hạ cấp khi được bật TƯỜNG MINH, và phải kêu to trong log.
            logger.warning(
                "ALLOW_FONT_FALLBACK=true: không dùng được font '%s' -> lùi về '%s'",
                family, self.default_family,
            )
            path = self.path_for(self.default_family)
            spec = FONT_REGISTRY[self.default_family]

        font = ImageFont.truetype(str(path), int(size))
        if spec.variation:
            font.set_variation_by_name(spec.variation)
        with self._lock:
            self._cache[key] = font
        return font

    @staticmethod
    def _ve_ky_tu(font: ImageFont.FreeTypeFont, char: str) -> bytes:
        """Vẽ 1 ký tự ra ảnh xám nhỏ, trả bytes pixel để so sánh."""
        from PIL import Image, ImageDraw

        size = max(int(font.size) * 2, 16)
        image = Image.new("L", (size, size), color=0)
        ImageDraw.Draw(image).text((2, 2), char, font=font, fill=255)
        return image.tobytes()

    def assert_can_render(self, font: ImageFont.FreeTypeFont, text: str) -> None:
        """Chặn tofu: ký tự nào vẽ ra y hệt ký tự-không-tồn-tại nghĩa là font thiếu glyph.

        Không dùng `fontTools` để khỏi thêm phụ thuộc runtime cho worker — cách này kiểm đúng
        thứ ta thật sự quan tâm: **vẽ ra có thành ô vuông không**.

        Cố ý KHÔNG bắt exception ở đây: nếu bản thân phép kiểm hỏng thì phải nổ ra. Bản đầu tiên
        của hàm này có `except: return` và đã âm thầm tắt luôn phép kiểm (getmask trả ImagingCore
        không có .tobytes) — đúng loại lỗi im lặng mà nó sinh ra để chống.
        """
        sentinel = self._ve_ky_tu(font, _SENTINEL)
        missing = [
            char
            for char in dict.fromkeys(normalize_for_layout(text))
            if not char.isspace()
            and char != _SENTINEL
            and self._ve_ky_tu(font, char) == sentinel
        ]
        if missing:
            raise MissingGlyph(
                f"font_missing_glyph: font thiếu glyph cho {''.join(missing)!r} — "
                "sẽ render ra ô vuông. Xem docs/FONTS.md để chọn font đủ 134 ký tự tiếng Việt."
            )
