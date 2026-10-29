"""E20b — dataset MỤC TIÊU: "chữ mảnh trên nền tranh phức tạp" (không phải "chữ hoa cách điệu").

`REPORT_E20a.md` §10 đã đo và bác bỏ giả thuyết gốc của `PLAN E20`. Bằng chứng thật: chữ ĐẬM
(Bangers) miễn nhiễm với nền bận (100%), chữ MẢNH (ShantellSans-Italic) trên CÙNG nền bận hỏng
100% (0/10), đúng một mẫu hình mất ký tự ở hai đầu. E20b so engine/tiền xử lý phải nhắm ĐÚNG điều
kiện đã xác nhận này, không phải đề bài gốc.

Dataset: 20 mẫu, đúng khuôn schema E20a (`TRUONG_BAT_BUOC` trong `dataset.py`) để dùng lại được
`OCRBenchmarkDatasetLoader`/`OCRMetricsCalculator` đã có + test — không viết loader thứ hai.
- 10 mẫu `italic_thin_on_busy_bg` — MỤC TIÊU CHÍNH, PaddleOCR baseline đã biết = 0/10.
- 10 mẫu `bold_on_busy_bg` — ĐỐI CHỨNG cùng điều kiện nền, PaddleOCR baseline đã biết = 10/10.
  Giữ lại để phát hiện path nào "sửa được chữ mảnh nhưng phá luôn chữ đậm" (constraint E20b:
  không được cải thiện nhóm khó mà hại nhóm dễ).

KHÔNG chạy OCR ở đây — chỉ dựng dữ liệu (giống `ocr_benchmark_generate_dataset.py` của E20a).
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

GOC = Path(__file__).resolve().parents[2]
NGUON_THAT = GOC / "test_fixtures" / "external"
BACKEND_DIR = Path(__file__).resolve().parents[1]
RA = BACKEND_DIR / "test_fixtures" / "external" / "ocr_benchmark_e20b"
FONTS = BACKEND_DIR / "fonts"

NEN_BAN = [
    ("go_toi", "pc_E01P01_1600.png", (100, 1000, 700, 1400)),
    ("ke_chai_lo", "pc_E01P02_1600.png", (150, 900, 750, 1300)),
    ("bau_troi_sao", "pc_E01P03_1600.png", (100, 100, 700, 600)),
    ("cua_so_sang", "pc_E01P01_1600.png", (350, 100, 950, 500)),
    ("may_xanh", "pc_E01P03_1600.png", (50, 1600, 650, 2000)),
    ("san_go", "pc_E01P02_1600.png", (100, 1700, 700, 2100)),
]

CAU_MANH = [
    "Maybe this wasn't such a good idea...",
    "Something feels wrong about this place.",
    "I can't believe he actually said that.",
    "If only I had listened to her warning.",
    "This is going to be harder than I thought.",
    "Why does it always rain when I need it not to?",
    "He's hiding something, I just know it.",
    "There has to be another way out of here.",
    "I never wanted things to end like this.",
    "Just a little further, we're almost there.",
]
CAU_DAM = [
    "NO OBSTACLES IN SIGHT.",
    "WIND, NORTHWEST, LIGHT.",
    "TARGET CONFIRMED, MOVING IN.",
    "STAY SHARP, WE'RE NOT DONE YET.",
    "THIS ENDS NOW, NO MORE GAMES.",
    "HOLD THE LINE UNTIL BACKUP ARRIVES.",
    "I WON'T LET YOU PASS THIS POINT.",
    "EVERYONE DOWN, TAKE COVER NOW.",
    "THE SIGNAL IS WEAK BUT STILL THERE.",
    "ONE MORE STEP AND I WILL FIRE.",
]


def _dat_chu_len_nen(cau: str, font_path: Path, size: int, nen_idx: int, le: int = 14) -> Image.Image:
    ten_nen, src, box = NEN_BAN[nen_idx % len(NEN_BAN)]
    nen = Image.open(NGUON_THAT / src).convert("RGB").crop(box)
    font = ImageFont.truetype(str(font_path), size)
    d = ImageDraw.Draw(nen)
    bbox_chu = d.multiline_textbbox((0, 0), cau, font=font, align="center", spacing=6)
    w_chu, h_chu = bbox_chu[2] - bbox_chu[0], bbox_chu[3] - bbox_chu[1]
    cx = (nen.width - w_chu) // 2 - bbox_chu[0]
    cy = (nen.height - h_chu) // 2 - bbox_chu[1]
    d.multiline_text((cx, cy), cau, font=font, fill=(255, 255, 255, 255), align="center",
                      spacing=6, stroke_width=3, stroke_fill=(10, 10, 10, 255))
    left = max(0, bbox_chu[0] + cx - le)
    top = max(0, bbox_chu[1] + cy - le)
    right = min(nen.width, bbox_chu[2] + cx + le)
    bottom = min(nen.height, bbox_chu[3] + cy + le)
    return nen.crop((left, top, right, bottom)), ten_nen


def main() -> None:
    (RA / "crops").mkdir(parents=True, exist_ok=True)
    mau = []

    for i, cau in enumerate(CAU_MANH, 1):
        img, ten_nen = _dat_chu_len_nen(
            cau, FONTS / "ShantellSans/ShantellSans-Italic-VF.ttf", 40, i - 1)
        sid = f"e20b_manh_{i:02d}"
        img.save(RA / "crops" / f"{sid}.png")
        mau.append({
            "sample_id": sid, "source_category": "busy_bg_thin_font",
            "license_scope": "CC-BY-SA-4.0 (nền, David Revoy) + OFL-1.1 (font ShantellSans) + câu tự viết",
            "language": "en", "text_kind": "dialogue", "lettering_style": "italic_thin_on_busy_bg",
            "rotation_bucket": "none", "crop_path": f"{sid}.png",
            "ground_truth": unicodedata.normalize("NFC", cau),
            "notes": f"nền={ten_nen}, ĐÚNG mục tiêu đã xác nhận ở REPORT_E20a §10.2 (baseline PaddleOCR 0/10)",
            "include_in_public_report": True,
        })

    for i, cau in enumerate(CAU_DAM, 1):
        img, ten_nen = _dat_chu_len_nen(
            cau, FONTS / "Bangers/Bangers-Regular.ttf", 46, i - 1)
        sid = f"e20b_dam_{i:02d}"
        img.save(RA / "crops" / f"{sid}.png")
        mau.append({
            "sample_id": sid, "source_category": "busy_bg_bold_font_control",
            "license_scope": "CC-BY-SA-4.0 (nền, David Revoy) + OFL-1.1 (font Bangers) + câu tự viết",
            "language": "en", "text_kind": "dialogue", "lettering_style": "bold_on_busy_bg",
            "rotation_bucket": "none", "crop_path": f"{sid}.png",
            "ground_truth": unicodedata.normalize("NFC", cau),
            "notes": f"nền={ten_nen}, ĐỐI CHỨNG — baseline PaddleOCR 10/10, canh KHÔNG bị path nào phá",
            "include_in_public_report": True,
        })

    with (RA / "manifest.jsonl").open("w", encoding="utf-8") as f:
        for d in mau:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    print(f"Đã tạo {len(mau)} mẫu -> {RA}")


if __name__ == "__main__":
    main()
