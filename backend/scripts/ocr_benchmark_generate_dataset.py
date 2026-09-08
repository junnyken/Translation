"""E20a — dựng dataset benchmark OCR (crop + ground truth) cho chữ truyện tranh cách điệu.

Chạy MỘT LẦN cục bộ để tái tạo `test_fixtures/external/ocr_benchmark/` (thư mục này bị
`.gitignore` — không đưa ảnh lên git, đúng quy ước đã có với `test_fixtures/external/`).
Script này CÓ commit — ai chạy lại cũng ra đúng bộ dữ liệu (trừ 6 crop thật từ Pepper&Carrot,
cần có sẵn `test_fixtures/external/pc_E01P0{1,2,3}_1600.png`, xem `NGUON.md` cùng thư mục).

Không đụng DB, không đụng OCRResult production, không gọi PaddleOCR/manga-ocr ở đây — script
này CHỈ dựng dữ liệu. Chạy suy luận nằm ở `ocr_benchmark_run.py` (dùng đúng adapter M3).

## Vì sao vừa ảnh thật vừa ảnh tự tạo

`PLAN E20a` cho phép "Pepper&Carrot CC BY-SA, text tự tạo hoặc nguồn có license rõ" cho phần
public. Pepper&Carrot chỉ có 3 trang mẫu sẵn trong repo (đo cho E14/Run C trước đây), tổng cộng
5 bong bóng thoại thật + 1 SFX thật — không đủ để phủ nhóm "chữ HOA cách điệu, sát nhau" (đúng
kiểu chữ đang gây lỗi thật trên MangaPlus — xem `docs/ARCH.md` §E19.6g). Nhóm đó và các nhóm còn
thiếu mẫu thật (SFX, narration, chữ nghiêng, ảnh nhiễu) được TỰ TẠO bằng font OFL đã có sẵn
trong `backend/fonts/` (Bangers = chữ HOA đậm sát nét — đúng kiểu lettering truyện tranh chính
thức; ShantellSans-Italic = chữ nghiêng) + câu tự viết. Ground truth vì vậy CHẮC CHẮN đúng 100%
(không phải chép tay từ ảnh) — mạnh hơn yêu cầu tối thiểu của mini-spec.
"""
from __future__ import annotations

import json
import random
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

GOC = Path(__file__).resolve().parents[2]  # thư mục gốc repo (trên cả backend/)
NGUON_THAT = GOC / "test_fixtures" / "external"
RA = GOC / "backend" / "test_fixtures" / "external" / "ocr_benchmark"
CROPS = RA / "crops"
FONTS = GOC / "backend" / "fonts"

random.seed(20260908)  # tái lập được — cùng seed ra cùng nhiễu mỗi lần chạy lại


@dataclass
class Sample:
    sample_id: str
    source_category: str
    license_scope: str
    language: str
    text_kind: str          # dialogue | sfx | narration
    lettering_style: str    # normal_handlettered | uppercase_tight | italic_stylized |
                             # outlined | noisy_partial
    rotation_bucket: str    # none | slight | angled
    crop_path: str          # tương đối so với RA
    ground_truth: str
    notes: str
    include_in_public_report: bool


MAU_CHU = (15, 15, 20, 255)
MAU_NEN_BONG_BONG = (255, 255, 255, 255)


def _do_chu(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def _ve_bong_bong(text: str, font: ImageFont.FreeTypeFont, *, le: int = 22) -> Image.Image:
    """Nền trắng bầu dục quanh chữ — giống crop bong bóng thoại thật (đủ để OCR thấy nền đơn giản,
    không phải mô phỏng thẩm mỹ)."""
    tmp = Image.new("RGBA", (10, 10))
    d = ImageDraw.Draw(tmp)
    box = d.multiline_textbbox((0, 0), text, font=font, align="center", spacing=6)
    w, h = int(box[2] - box[0]), int(box[3] - box[1])
    img = Image.new("RGBA", (w + le * 2, h + le * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, img.width, img.height], fill=MAU_NEN_BONG_BONG)
    d.multiline_text((le - box[0], le - box[1]), text, font=font, fill=MAU_CHU,
                      align="center", spacing=6)
    return img


def _ve_chu_tran(text: str, font: ImageFont.FreeTypeFont, *, mau=MAU_CHU,
                  vien: tuple | None = None) -> Image.Image:
    """Chữ trên nền TRẮNG (không trong suốt) — dùng cho SFX vẽ thẳng lên khung nền.

    Trước để nền trong suốt rồi `.convert("RGB")` — PIL tự nền ĐEN khi làm phẳng alpha, trông
    giả tạo và không giống nền tranh vẽ thật. Nền trắng ít nhất trung tính, không đánh lừa mắt.
    """
    tmp = Image.new("RGBA", (10, 10))
    d = ImageDraw.Draw(tmp)
    box = d.textbbox((0, 0), text, font=font, stroke_width=6 if vien else 0)
    w, h = int(box[2] - box[0]), int(box[3] - box[1])
    pad = 14
    img = Image.new("RGBA", (w + pad * 2, h + pad * 2), (255, 255, 255, 255))
    d = ImageDraw.Draw(img)
    if vien:
        d.text((pad - box[0], pad - box[1]), text, font=font, fill=vien, stroke_width=6,
               stroke_fill=vien)
        d.text((pad - box[0], pad - box[1]), text, font=font, fill=mau)
    else:
        d.text((pad - box[0], pad - box[1]), text, font=font, fill=mau)
    return img


def _ve_khung_tuong_thuat(text: str, font: ImageFont.FreeTypeFont) -> Image.Image:
    """Hộp chữ nhật nền vàng nhạt — kiểu khung tường thuật/caption, khác hẳn bong bóng tròn."""
    tmp = Image.new("RGBA", (10, 10))
    d = ImageDraw.Draw(tmp)
    box = d.multiline_textbbox((0, 0), text, font=font, align="left", spacing=5)
    w, h = int(box[2] - box[0]), int(box[3] - box[1])
    pad = 16
    img = Image.new("RGBA", (w + pad * 2, h + pad * 2), (250, 240, 200, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, img.width - 1, img.height - 1], outline=(40, 30, 10, 255), width=3)
    d.multiline_text((pad - box[0], pad - box[1]), text, font=font, fill=(20, 15, 5, 255),
                      align="left", spacing=5)
    return img


def _xoay(img: Image.Image, do: float) -> Image.Image:
    return img.rotate(do, expand=True, fillcolor=(0, 0, 0, 0), resample=Image.BICUBIC)


def _luu(img: Image.Image, duong: Path) -> None:
    """Làm phẳng RGBA → RGB trên nền TRẮNG (không phải `.convert('RGB')` trần — PIL tự nền ĐEN
    ở chỗ trong suốt, lộ ra rõ nhất sau khi xoay vì góc mở rộng luôn trong suốt)."""
    nen = Image.new("RGBA", img.size, (255, 255, 255, 255))
    Image.alpha_composite(nen, img.convert("RGBA")).convert("RGB").save(duong)


def _lam_nhieu(img: Image.Image, *, do_mo: float = 0.0, muoi_tieu: float = 0.0,
               cat_canh: float = 0.0) -> Image.Image:
    """Mô phỏng ảnh chụp/nén kém: làm mờ, thêm nhiễu hạt, và/hoặc cắt mất một cạnh."""
    out = img.convert("RGBA")
    if do_mo > 0:
        out = out.filter(ImageFilter.GaussianBlur(do_mo))
    if muoi_tieu > 0:
        import numpy as np
        arr = np.array(out).astype("int16")
        nhieu = (np.random.default_rng(0).normal(0, muoi_tieu, arr[..., :3].shape)).astype("int16")
        arr[..., :3] = (arr[..., :3] + nhieu).clip(0, 255)
        out = Image.fromarray(arr.astype("uint8"), "RGBA")
    if cat_canh > 0:
        w, h = out.size
        out = out.crop((0, 0, int(w * (1 - cat_canh)), h))
    return out


def main() -> None:
    (CROPS / "real").mkdir(parents=True, exist_ok=True)
    (CROPS / "synthetic").mkdir(parents=True, exist_ok=True)
    mau: list[Sample] = []

    # ---------- 1. THẬT — Pepper&Carrot (CC BY-SA 4.0, xem NGUON.md) ----------
    that = [
        ("pc_p1_b1", "pc_E01P01_1600.png", (680, 40, 980, 210), "...and the last\ntouch.", "dialogue"),
        ("pc_p1_b2", "pc_E01P01_1600.png", (665, 775, 970, 935), "...mmm\nprobably not\nstrong enough.", "dialogue"),
        ("pc_p2_b1", "pc_E01P02_1600.png", (1120, 185, 1300, 300), "ha...\nperfect.", "dialogue"),
        ("pc_p2_b2", "pc_E01P02_1600.png", (720, 795, 1030, 945), "NO!\nDon't even think\nabout it.", "dialogue"),
        ("pc_p3_b1", "pc_E01P03_1600.png", (470, 880, 675, 970), "Happy?!", "dialogue"),
        ("pc_p2_sfx1", "pc_E01P02_1600.png", (880, 1855, 1040, 1935), "SPLASH", "sfx"),
    ]
    for sid, src, box, text, kind in that:
        img = Image.open(NGUON_THAT / src).convert("RGB")
        crop = img.crop(box)
        rel = f"real/{sid}.png"
        crop.save(CROPS / rel)
        mau.append(Sample(
            sample_id=sid, source_category="pepper_carrot_real",
            license_scope="CC-BY-SA-4.0 (David Revoy, peppercarrot.com) — xem NGUON.md",
            language="en",
            text_kind=kind,
            lettering_style="normal_handlettered" if kind == "dialogue" else "outlined",
            rotation_bucket="none",
            crop_path=rel, ground_truth=text,
            notes=f"crop tay từ {src}, bbox={box} (không nới lề, giống crop_region production)",
            include_in_public_report=True,
        ))

    # ---------- 2. TỰ TẠO — chữ HOA cách điệu, sát nét (Bangers) — ĐÚNG kiểu gây lỗi thật ----------
    bangers = _do_chu(FONTS / "Bangers/Bangers-Regular.ttf", 46)
    cau_hoa = [
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
    for i, cau in enumerate(cau_hoa, 1):
        sid = f"syn_uc_{i:02d}"
        img = _ve_bong_bong(cau, bangers, le=20)
        rel = f"synthetic/{sid}.png"
        _luu(img, CROPS / rel)
        mau.append(Sample(
            sample_id=sid, source_category="synthetic_bangers_uppercase",
            license_scope="OFL-1.1 (font Bangers) + câu tự viết",
            language="en", text_kind="dialogue", lettering_style="uppercase_tight",
            rotation_bucket="none", crop_path=rel, ground_truth=cau,
            notes="Bangers — chữ HOA đậm, sát nét mặc định của font, mô phỏng lettering "
                  "truyện tranh chính thức (đúng loại đã gây lỗi thật trên MangaPlus)",
            include_in_public_report=True,
        ))

    # ---------- 3. TỰ TẠO — chữ nghiêng cách điệu (ShantellSans-Italic) ----------
    italic = _do_chu(FONTS / "ShantellSans/ShantellSans-Italic-VF.ttf", 40)
    cau_nghieng = [
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
    goc_xoay = [0, -4, 3, -6, 5, 0, -3, 4, -5, 2]
    for i, (cau, do) in enumerate(zip(cau_nghieng, goc_xoay, strict=True), 1):
        sid = f"syn_it_{i:02d}"
        img = _ve_bong_bong(cau, italic, le=18)
        if do:
            img = _xoay(img, do)
        rel = f"synthetic/{sid}.png"
        _luu(img, CROPS / rel)
        mau.append(Sample(
            sample_id=sid, source_category="synthetic_shantell_italic",
            license_scope="OFL-1.1 (font ShantellSans) + câu tự viết",
            language="en", text_kind="dialogue", lettering_style="italic_stylized",
            rotation_bucket="none" if do == 0 else ("slight" if abs(do) <= 5 else "angled"),
            crop_path=rel, ground_truth=cau,
            notes=f"ShantellSans-Italic, xoay {do}°",
            include_in_public_report=True,
        ))

    # ---------- 4. TỰ TẠO — SFX thêm (Bangers, xoay mạnh, có viền) ----------
    sigmar = _do_chu(FONTS / "SigmarOne/SigmarOne-Regular.ttf", 52)
    sfx_font_goc = [
        ("BANG!", bangers, 60, -12),
        ("CRASH!", sigmar, 52, 8),
        ("WHOOSH!", bangers, 50, -18),
        ("THUD!", sigmar, 56, 15),
    ]
    for i, (cau, font_ho, size, do) in enumerate(sfx_font_goc, 1):
        sid = f"syn_sfx_{i:02d}"
        f = _do_chu(Path(font_ho.path), size)
        img = _ve_chu_tran(cau, f, mau=(230, 140, 20, 255), vien=(20, 10, 0, 255))
        img = _xoay(img, do)
        rel = f"synthetic/{sid}.png"
        _luu(img, CROPS / rel)
        mau.append(Sample(
            sample_id=sid, source_category="synthetic_sfx",
            license_scope=f"OFL-1.1 (font {'Bangers' if font_ho is bangers else 'SigmarOne'}) + từ tự chọn",
            language="en", text_kind="sfx", lettering_style="outlined",
            rotation_bucket="angled", crop_path=rel, ground_truth=cau,
            notes=f"xoay {do}°, có viền — mô phỏng SFX truyện tranh",
            include_in_public_report=True,
        ))

    # ---------- 5. TỰ TẠO — khung tường thuật/caption (5) ----------
    tuong_thuat_font = _do_chu(FONTS / "ShantellSans/ShantellSans-Roman-VF.ttf", 30)
    cau_tuong_thuat = [
        "Three days later, at the edge of town.",
        "Meanwhile, across the city.",
        "The following morning, before sunrise.",
        "Later that night, in an empty alley.",
        "Two weeks earlier.",
    ]
    for i, cau in enumerate(cau_tuong_thuat, 1):
        sid = f"syn_narr_{i:02d}"
        img = _ve_khung_tuong_thuat(cau, tuong_thuat_font)
        rel = f"synthetic/{sid}.png"
        _luu(img, CROPS / rel)
        mau.append(Sample(
            sample_id=sid, source_category="synthetic_narration",
            license_scope="OFL-1.1 (font ShantellSans) + câu tự viết",
            language="en", text_kind="narration", lettering_style="normal_handlettered",
            rotation_bucket="none", crop_path=rel, ground_truth=cau,
            notes="khung chữ nhật nền vàng nhạt, khác cấu trúc bong bóng tròn",
            include_in_public_report=True,
        ))

    # ---------- 6. TỰ TẠO — bổ sung nhóm "bình thường" cho đủ 10 (Mansalva, viết tay) ----------
    mansalva = _do_chu(FONTS / "Mansalva/Mansalva-Regular.ttf", 38)
    cau_binh_thuong = [
        "I think we should turn back now.",
        "Wait, did you hear that too?",
        "Let's just wait here until morning.",
        "I told you this was a bad plan.",
        "Everything will be fine, I promise.",
    ]
    for i, cau in enumerate(cau_binh_thuong, 1):
        sid = f"syn_norm_{i:02d}"
        img = _ve_bong_bong(cau, mansalva, le=20)
        rel = f"synthetic/{sid}.png"
        _luu(img, CROPS / rel)
        mau.append(Sample(
            sample_id=sid, source_category="synthetic_mansalva_normal",
            license_scope="OFL-1.1 (font Mansalva) + câu tự viết",
            language="en", text_kind="dialogue", lettering_style="normal_handlettered",
            rotation_bucket="none", crop_path=rel, ground_truth=cau,
            notes="chữ viết tay bình thường — bổ sung nhóm 'normal' cho đủ 10 mẫu "
                  "(chỉ có 5 bong bóng thật trong 3 trang Pepper&Carrot hiện có)",
            include_in_public_report=True,
        ))

    # ---------- 7. Suy biến — lấy lại 5 mẫu cách điệu ở trên rồi làm nhiễu/cắt cạnh ----------
    nguon_kho = [s for s in mau if s.lettering_style in ("uppercase_tight", "italic_stylized")][:5]
    kieu_nhieu = [
        {"do_mo": 1.6},
        {"muoi_tieu": 28},
        {"cat_canh": 0.22},
        {"do_mo": 0.8, "muoi_tieu": 14},
        {"cat_canh": 0.15, "do_mo": 0.6},
    ]
    for i, (goc, tham_so) in enumerate(zip(nguon_kho, kieu_nhieu, strict=True), 1):
        sid = f"syn_noisy_{i:02d}"
        img = Image.open(CROPS / goc.crop_path).convert("RGBA")
        img = _lam_nhieu(img, **tham_so)
        rel = f"synthetic/{sid}.png"
        _luu(img, CROPS / rel)
        mau.append(Sample(
            sample_id=sid, source_category="synthetic_degraded",
            license_scope=goc.license_scope,
            language="en", text_kind=goc.text_kind, lettering_style="noisy_partial",
            rotation_bucket=goc.rotation_bucket, crop_path=rel, ground_truth=goc.ground_truth,
            notes=f"suy biến từ {goc.sample_id} bằng {tham_so} — ground_truth giữ nguyên CHỮ ĐẦY "
                  f"ĐỦ dù ảnh bị cắt/mờ, để đo đúng khả năng chịu nhiễu chứ không giảm độ khó",
            include_in_public_report=True,
        ))

    # ---------- Ghi manifest ----------
    with (RA / "manifest.jsonl").open("w", encoding="utf-8") as f:
        for s in mau:
            d = asdict(s)
            d["ground_truth"] = unicodedata.normalize("NFC", d["ground_truth"])
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    theo_nhom: dict[str, int] = {}
    for s in mau:
        theo_nhom[s.lettering_style] = theo_nhom.get(s.lettering_style, 0) + 1
    print(f"Đã tạo {len(mau)} mẫu -> {RA}")
    for k, v in sorted(theo_nhom.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
