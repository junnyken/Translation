"""E20a phụ lục 2 — chữ đặt TRỰC TIẾP lên nền tranh phức tạp (không bong bóng trắng sạch).

E20a đo trên bong bóng nền trắng sạch: gần hoàn hảo. Phụ lục độ phân giải (`ocr_benchmark_
resolution_test.py`) cũng gần hoàn hảo tới tận 20px. Hai giả thuyết ĐÃ BỊ LOẠI. Script này kiểm
giả thuyết còn lại KHÔNG CẦN ảnh MangaPlus thật: lấy đúng 20 câu (10 uppercase_tight/Bangers +
10 italic/ShantellSans) đã có ground truth từ E20a, đặt trực tiếp lên nền tranh THẬT phức tạp cắt
từ 3 trang Pepper&Carrot (gỗ, kệ đồ, bầu trời sao — không phải bong bóng, không phải nền phẳng)
có viền chữ (như cách SFX/caption thật hay làm để giữ đọc được trên nền bận) — đúng mô phỏng tình
huống thật hơn nền trắng.
"""
from __future__ import annotations

import json
import sys
import time
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

GOC = Path(__file__).resolve().parents[2]
NGUON_THAT = GOC / "test_fixtures" / "external"
BACKEND_DIR = Path(__file__).resolve().parents[1]
RA = BACKEND_DIR / "test_fixtures" / "external" / "ocr_benchmark" / "busy_bg_test"
FONTS = BACKEND_DIR / "fonts"

# 6 vùng nền BẬN cắt từ 3 trang Pepper&Carrot — tránh hẳn vùng đã có bong bóng/SFX thật ở E20a,
# đa dạng: gỗ tối, kệ đồ có chai lọ, bầu trời sao, ánh sáng phép thuật, lông mèo, mảng cây xanh.
NEN_BAN = [
    ("go_toi", "pc_E01P01_1600.png", (100, 1000, 700, 1400)),
    ("ke_chai_lo", "pc_E01P02_1600.png", (150, 900, 750, 1300)),
    ("bau_troi_sao", "pc_E01P03_1600.png", (100, 100, 700, 600)),
    ("cua_so_sang", "pc_E01P01_1600.png", (350, 100, 950, 500)),
    ("may_xanh", "pc_E01P03_1600.png", (50, 1600, 650, 2000)),
    ("san_go", "pc_E01P02_1600.png", (100, 1700, 700, 2100)),
]

CAU = [
    ("NO OBSTACLES IN SIGHT.", "Bangers/Bangers-Regular.ttf", 46, "uppercase_tight"),
    ("WIND, NORTHWEST, LIGHT.", "Bangers/Bangers-Regular.ttf", 46, "uppercase_tight"),
    ("TARGET CONFIRMED, MOVING IN.", "Bangers/Bangers-Regular.ttf", 46, "uppercase_tight"),
    ("STAY SHARP, WE'RE NOT DONE YET.", "Bangers/Bangers-Regular.ttf", 46, "uppercase_tight"),
    ("THIS ENDS NOW, NO MORE GAMES.", "Bangers/Bangers-Regular.ttf", 46, "uppercase_tight"),
    ("HOLD THE LINE UNTIL BACKUP ARRIVES.", "Bangers/Bangers-Regular.ttf", 46, "uppercase_tight"),
    ("I WON'T LET YOU PASS THIS POINT.", "Bangers/Bangers-Regular.ttf", 46, "uppercase_tight"),
    ("EVERYONE DOWN, TAKE COVER NOW.", "Bangers/Bangers-Regular.ttf", 46, "uppercase_tight"),
    ("THE SIGNAL IS WEAK BUT STILL THERE.", "Bangers/Bangers-Regular.ttf", 46, "uppercase_tight"),
    ("ONE MORE STEP AND I WILL FIRE.", "Bangers/Bangers-Regular.ttf", 46, "uppercase_tight"),
    ("Maybe this wasn't such a good idea...", "ShantellSans/ShantellSans-Italic-VF.ttf", 40, "italic_stylized"),
    ("Something feels wrong about this place.", "ShantellSans/ShantellSans-Italic-VF.ttf", 40, "italic_stylized"),
    ("I can't believe he actually said that.", "ShantellSans/ShantellSans-Italic-VF.ttf", 40, "italic_stylized"),
    ("If only I had listened to her warning.", "ShantellSans/ShantellSans-Italic-VF.ttf", 40, "italic_stylized"),
    ("This is going to be harder than I thought.", "ShantellSans/ShantellSans-Italic-VF.ttf", 40, "italic_stylized"),
    ("Why does it always rain when I need it not to?", "ShantellSans/ShantellSans-Italic-VF.ttf", 40, "italic_stylized"),
    ("He's hiding something, I just know it.", "ShantellSans/ShantellSans-Italic-VF.ttf", 40, "italic_stylized"),
    ("There has to be another way out of here.", "ShantellSans/ShantellSans-Italic-VF.ttf", 40, "italic_stylized"),
    ("I never wanted things to end like this.", "ShantellSans/ShantellSans-Italic-VF.ttf", 40, "italic_stylized"),
    ("Just a little further, we're almost there.", "ShantellSans/ShantellSans-Italic-VF.ttf", 40, "italic_stylized"),
]


def dung_bo_mau() -> list[dict]:
    RA.mkdir(parents=True, exist_ok=True)
    (RA / "crops").mkdir(exist_ok=True)
    ra = []
    for i, (cau, font_rel, size, kieu) in enumerate(CAU, 1):
        ten_nen, src, box = NEN_BAN[i % len(NEN_BAN)]
        nen = Image.open(NGUON_THAT / src).convert("RGB").crop(box)
        font = ImageFont.truetype(str(FONTS / font_rel), size)

        d = ImageDraw.Draw(nen)
        bbox_chu = d.multiline_textbbox((0, 0), cau, font=font, align="center", spacing=6)
        w_chu, h_chu = bbox_chu[2] - bbox_chu[0], bbox_chu[3] - bbox_chu[1]
        # Canh giữa nền, cắt nền cho vừa khít khối chữ (+ lề) — không phóng to/co chữ.
        le = 14
        cx, cy = (nen.width - w_chu) // 2 - bbox_chu[0], (nen.height - h_chu) // 2 - bbox_chu[1]
        # Chữ trắng + viền đen — đúng cách lettering thật giữ đọc được trên nền bận.
        d.multiline_text((cx, cy), cau, font=font, fill=(255, 255, 255, 255), align="center",
                          spacing=6, stroke_width=3, stroke_fill=(10, 10, 10, 255))

        # Cắt sát khối chữ + lề, không giữ nguyên cả nền lớn — đúng kiểu crop_region thật.
        left = max(0, bbox_chu[0] + cx - le)
        top = max(0, bbox_chu[1] + cy - le)
        right = min(nen.width, bbox_chu[2] + cx + le)
        bottom = min(nen.height, bbox_chu[3] + cy + le)
        crop = nen.crop((left, top, right, bottom))

        sid = f"busybg_{i:02d}"
        rel = f"{sid}.png"
        crop.save(RA / "crops" / rel)
        ra.append({"sample_id": sid, "nen": ten_nen, "lettering_style": kieu,
                   "crop_path": rel, "ground_truth": cau, "kich_thuoc": crop.size})

    with (RA / "manifest.jsonl").open("w", encoding="utf-8") as f:
        for d in ra:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    return ra


def _khoang_cach_levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    n, m = len(a), len(b)
    if n == 0:
        return m
    if m == 0:
        return n
    truoc = list(range(m + 1))
    for i in range(1, n + 1):
        hien = [i] + [0] * m
        for j in range(1, m + 1):
            phi = 0 if a[i - 1] == b[j - 1] else 1
            hien[j] = min(truoc[j] + 1, hien[j - 1] + 1, truoc[j - 1] + phi)
        truoc = hien
    return truoc[m]


def _nap_hoac_dung(chi_dung: bool) -> list[dict]:
    """Chạy được ở HAI nơi: cục bộ (có ảnh nguồn `test_fixtures/external/`, KHÔNG có paddleocr)
    để dựng dữ liệu, và trong container worker (có paddleocr, KHÔNG mount được ảnh nguồn top-
    level) để chạy suy luận trên dữ liệu đã dựng sẵn. Có sẵn manifest thì đọc lại, không dựng lại
    (dựng lại cần `NGUON_THAT`, chỉ có ở máy cục bộ)."""
    manifest_path = RA / "manifest.jsonl"
    if manifest_path.exists():
        with manifest_path.open(encoding="utf-8") as f:
            return [json.loads(dong) for dong in f]
    if chi_dung:
        raise SystemExit(f"Chưa có {manifest_path} — chạy cục bộ trước (không --chi-chay-suy-luan)")
    return dung_bo_mau()


def main() -> None:
    chi_chay_suy_luan = "--chi-chay-suy-luan" in sys.argv
    mau = _nap_hoac_dung(chi_chay_suy_luan)
    print(f"{'Nạp lại' if chi_chay_suy_luan else 'Đã tạo'} {len(mau)} mẫu chữ-trên-nền-bận.")
    if "--chi-dung-du-lieu" in sys.argv:
        return

    sys.path.insert(0, str(BACKEND_DIR))
    from app.services.ocr.engines import PaddleOCREngine
    from app.services.interfaces import BBox

    engine = PaddleOCREngine(lang="en", device="cpu")
    print("Nạp PaddleOCR (lang=en)...")

    ket_qua = []
    for i, d in enumerate(mau, 1):
        path = RA / "crops" / d["crop_path"]
        w, h = d["kich_thuoc"]
        t0 = time.perf_counter()
        try:
            text, conf = engine.recognize(str(path), BBox(x=0, y=0, w=w, h=h))
        except Exception as e:  # noqa: BLE001
            text, conf = f"__LOI__:{e}", None
        ms = round((time.perf_counter() - t0) * 1000, 1)
        that = unicodedata.normalize("NFC", d["ground_truth"])
        doc = unicodedata.normalize("NFC", text or "")
        cer = _khoang_cach_levenshtein(that, doc) / max(len(that), 1)
        dung = that.strip() == doc.strip()
        ket_qua.append({**d, "predicted_text": text, "confidence": conf, "cer": cer,
                        "dung_tuyet_doi": dung, "runtime_ms": ms})
        dau = "✓" if dung else "✗"
        print(f"  [{i:2d}/{len(mau)}] {dau} {d['sample_id']:12s} nen={d['nen']:14s} cer={cer:.3f}")
        if not dung:
            print(f"        THẬT: {that!r}")
            print(f"        ĐỌC : {doc!r}")

    dung_tong = sum(1 for k in ket_qua if k["dung_tuyet_doi"])
    cer_tb = sum(k["cer"] for k in ket_qua) / len(ket_qua)
    print(f"\n=== TỔNG: {dung_tong}/{len(ket_qua)} đúng tuyệt đối "
          f"({100*dung_tong/len(ket_qua):.0f}%), CER TB={cer_tb:.4f} ===")

    with (RA / "ket_qua.json").open("w", encoding="utf-8") as f:
        json.dump(ket_qua, f, ensure_ascii=False, indent=2)
    print(f"Đã ghi {RA / 'ket_qua.json'}")


if __name__ == "__main__":
    main()
