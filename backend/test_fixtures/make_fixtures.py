"""Sinh ảnh test tổng hợp cho M2 — do repo tự tạo nên license rõ ràng (CC0), không dính bản quyền.

LƯU Ý: đây là trang giả lập để kiểm ĐƯỜNG ĐI của pipeline, KHÔNG phải trang manga scan thật.
Đo tỷ lệ nhận diện thật phải chạy trên bộ ảnh có license rõ do người dùng cung cấp (Manga109-s...).
Chạy: python test_fixtures/make_fixtures.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent


def _font(size: int):
    for p in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _bubble(d: ImageDraw.ImageDraw, box, lines, font_size=34):
    d.ellipse(box, fill="white", outline="black", width=5)
    f = _font(font_size)
    cx = (box[0] + box[2]) / 2
    total_h = len(lines) * (font_size + 8)
    y = (box[1] + box[3]) / 2 - total_h / 2
    for line in lines:
        w = d.textlength(line, font=f)
        d.text((cx - w / 2, y), line, fill="black", font=f)
        y += font_size + 8


def many_bubbles() -> tuple[str, int]:
    """6 bubble có chữ, bố cục 4 panel."""
    img = Image.new("RGB", (1400, 2000), "white")
    d = ImageDraw.Draw(img)
    for panel in [(40, 40, 1360, 640), (40, 680, 690, 1300), (720, 680, 1360, 1300), (40, 1340, 1360, 1960)]:
        d.rectangle(panel, outline="black", width=7)
        d.rectangle((panel[0] + 14, panel[1] + 14, panel[2] - 14, panel[3] - 14), fill="#e9e9e9")
    bubbles = [
        ((110, 90, 560, 330), ["GOOD", "MORNING"]),
        ((820, 130, 1290, 380), ["WHO", "ARE YOU?"]),
        ((90, 730, 600, 980), ["I AM", "HERE"]),
        ((780, 760, 1300, 1010), ["LOOK", "OUT!"]),
        ((110, 1400, 620, 1650), ["LET US", "GO NOW"]),
        ((800, 1620, 1310, 1900), ["THE END", "FOR NOW"]),
    ]
    for box, lines in bubbles:
        _bubble(d, box, lines)
    img.save(OUT / "many_bubbles.png")
    return "many_bubbles.png", len(bubbles)


def few_bubbles() -> tuple[str, int]:
    """2 bubble có chữ, trang thoáng."""
    img = Image.new("RGB", (1200, 1700), "white")
    d = ImageDraw.Draw(img)
    d.rectangle((40, 40, 1160, 1660), outline="black", width=7)
    d.rectangle((60, 60, 1140, 1640), fill="#efefef")
    bubbles = [((140, 150, 700, 430), ["HELLO", "THERE"]), ((520, 1150, 1080, 1440), ["GOODBYE"])]
    for box, lines in bubbles:
        _bubble(d, box, lines, font_size=40)
    img.save(OUT / "few_bubbles.png")
    return "few_bubbles.png", len(bubbles)


def loose_sfx() -> tuple[str, int]:
    """1 bubble + 3 cụm SFX rời (chữ nằm ngoài bubble) — case khó."""
    img = Image.new("RGB", (1300, 1800), "white")
    d = ImageDraw.Draw(img)
    d.rectangle((40, 40, 1260, 1760), outline="black", width=7)
    d.rectangle((60, 60, 1240, 1740), fill="#f2f2f2")
    _bubble(d, (120, 130, 640, 400), ["WAIT!"], font_size=44)
    for pos, txt, size in [((760, 260), "BOOM", 96), ((200, 900), "CRASH", 110), ((820, 1350), "ZAP", 88)]:
        d.text(pos, txt, fill="black", font=_font(size), stroke_width=4, stroke_fill="white")
    img.save(OUT / "loose_sfx.png")
    return "loose_sfx.png", 4  # 1 bubble + 3 SFX


if __name__ == "__main__":
    manifest = []
    for fn in (many_bubbles, few_bubbles, loose_sfx):
        name, count = fn()
        manifest.append((name, count))
        print(f"{name}: {count} vùng chữ đếm tay")
