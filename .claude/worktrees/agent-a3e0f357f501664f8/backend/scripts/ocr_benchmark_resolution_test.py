"""E20a phụ lục — có phải ĐỘ PHÂN GIẢI thấp mới là nguyên nhân thật, không phải font?

E20a (`docs/REPORT_E20a.md`) đo trên 45 crop RENDER Ở CỠ RỘNG RÃI (font 40-52px) và PaddleOCR đọc
gần như hoàn hảo — kể cả đúng font "chữ HOA sát nét" (Bangers) nghi ngờ gây lỗi MangaPlus. Ảnh
trang MangaPlus đo thật trong tiện ích chỉ **784×1145px cho CẢ TRANG** (xem debug panel v0.1.9) —
một bong bóng trong đó nhỏ hơn NHIỀU so với 46px font đã benchmark.

Script này lấy lại 20 mẫu `uppercase_tight`/`italic_stylized` đã có ground truth chắc chắn, THU
NHỎ xuống còn 60% / 35% / 20% kích thước gốc (mô phỏng bong bóng nhỏ trong một trang đầy đủ) rồi
OCR lại — tách bạch được "lỗi vì font cách điệu" khỏi "lỗi vì độ phân giải thấp" mà KHÔNG cần ảnh
MangaPlus thật (vẫn chưa có). Không đụng manifest gốc, không đụng DB, không đụng OCRResult.
"""
from __future__ import annotations

import json
import sys
import time
import unicodedata
from pathlib import Path

from PIL import Image

BACKEND_DIR = Path(__file__).resolve().parents[1]
RA = BACKEND_DIR / "test_fixtures" / "external" / "ocr_benchmark"
MANIFEST_GOC = RA / "manifest.jsonl"
CROPS_GOC = RA / "crops"
RA_SCALE = RA / "resolution_test"
CROPS_SCALE = RA_SCALE / "crops"

TI_LE = [1.0, 0.6, 0.35, 0.2]  # 1.0 = giữ nguyên (đối chứng), còn lại thu nhỏ


def nap_mau_goc() -> list[dict]:
    mau = []
    with MANIFEST_GOC.open(encoding="utf-8") as f:
        for dong in f:
            d = json.loads(dong)
            if d["lettering_style"] in ("uppercase_tight", "italic_stylized"):
                mau.append(d)
    return mau


def dung_bo_mau_thu_nho() -> list[dict]:
    CROPS_SCALE.mkdir(parents=True, exist_ok=True)
    goc = nap_mau_goc()
    ra: list[dict] = []
    for d in goc:
        img = Image.open(CROPS_GOC / d["crop_path"])
        w0, h0 = img.size
        for ti_le in TI_LE:
            if ti_le == 1.0:
                small = img
            else:
                w, h = max(1, round(w0 * ti_le)), max(1, round(h0 * ti_le))
                # LANCZOS mô phỏng đúng phép co ảnh chất lượng của trình duyệt/CDN thật, không
                # phải nearest-neighbor giả tạo dễ hơn thực tế.
                small = img.resize((w, h), Image.LANCZOS)
            sid = f"{d['sample_id']}_ti_le_{int(ti_le * 100)}"
            rel = f"{sid}.png"
            small.convert("RGB").save(CROPS_SCALE / rel)
            ra.append({
                "sample_id": sid,
                "goc": d["sample_id"],
                "ti_le": ti_le,
                "kich_thuoc": small.size,
                "lettering_style": d["lettering_style"],
                "crop_path": rel,
                "ground_truth": d["ground_truth"],
            })
    with (RA_SCALE / "manifest.jsonl").open("w", encoding="utf-8") as f:
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


def main() -> None:
    mau = dung_bo_mau_thu_nho()
    print(f"Đã tạo {len(mau)} mẫu thu nhỏ ({len(mau) // len(TI_LE)} gốc × {len(TI_LE)} tỉ lệ).")

    sys.path.insert(0, str(BACKEND_DIR))
    from app.services.ocr.engines import PaddleOCREngine
    from app.services.interfaces import BBox

    engine = PaddleOCREngine(lang="en", device="cpu")
    print("Nạp PaddleOCR (lang=en)...")

    ket_qua = []
    for i, d in enumerate(mau, 1):
        path = CROPS_SCALE / d["crop_path"]
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
        print(f"  [{i:2d}/{len(mau)}] {dau} {d['sample_id']:28s} cer={cer:.3f} {ms:.0f}ms")

    print("\n=== TỔNG HỢP THEO TỈ LỆ THU NHỎ ===")
    for ti_le in TI_LE:
        nhom = [k for k in ket_qua if k["ti_le"] == ti_le]
        dung = sum(1 for k in nhom if k["dung_tuyet_doi"])
        cer_tb = sum(k["cer"] for k in nhom) / len(nhom)
        w_tb = sum(k["kich_thuoc"][1] for k in nhom) / len(nhom)  # chiều cao trung bình
        print(f"  {int(ti_le*100):3d}% (cao TB {w_tb:.0f}px): "
              f"{dung}/{len(nhom)} đúng tuyệt đối ({100*dung/len(nhom):.0f}%), CER TB={cer_tb:.4f}")

    with (RA_SCALE / "ket_qua.json").open("w", encoding="utf-8") as f:
        json.dump(ket_qua, f, ensure_ascii=False, indent=2)
    print(f"\nĐã ghi {RA_SCALE / 'ket_qua.json'}")


if __name__ == "__main__":
    main()
