"""E20b — `BenchmarkExperimentRunner` + `BenchmarkComparisonReport`, chạy 9 path trên dataset
"chữ mảnh trên nền bận" (xem `ocr_benchmark_e20b_generate_dataset.py`).

9 path đúng danh sách mini-spec E20b:
  PaddleOCR × {không đổi, xám hoá, phóng to 2x, tăng tương phản, ngưỡng thích nghi}   (5)
  Tesseract × {PSM 7, 8, 11, 13} trên ảnh KHÔNG tiền xử lý                            (4)

Chạy trong container worker (PaddleOCR đã có sẵn; Tesseract cài tạm 1 lần bằng apt-get, KHÔNG
đụng Dockerfile production — xem `tesseract_adapter.py`).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
MANIFEST = BACKEND_DIR / "test_fixtures" / "external" / "ocr_benchmark_e20b" / "manifest.jsonl"
RA_JSON = MANIFEST.parent / "ket_qua_e20b.json"

sys.path.insert(0, str(BACKEND_DIR))

from PIL import Image  # noqa: E402

from app.services.ocr_benchmark.dataset import (  # noqa: E402
    GroundTruthValidator,
    OCRBenchmarkDatasetLoader,
)
from app.services.ocr_benchmark.metrics import KetQuaMotMau, OCRMetricsCalculator  # noqa: E402
from app.services.ocr_benchmark import preprocess as tx  # noqa: E402
from app.services.ocr_benchmark.tesseract_adapter import (  # noqa: E402
    PSM_HO_TRO,
    TesseractOCREngineBenchmarkAdapter,
)

CAC_PHEP_TIEN_XU_LY_PADDLE = ["khong_doi", "xam_hoa", "phong_to_2x", "tang_tuong_phan", "nguong_thich_nghi"]


def main() -> None:
    loader = OCRBenchmarkDatasetLoader(MANIFEST)
    mau = loader.nap()
    loi = GroundTruthValidator.kiem(mau)
    if loi:
        raise SystemExit(f"Manifest E20b hỏng: {loi}")
    print(f"Manifest hợp lệ: {len(mau)} mẫu.")

    from app.services.ocr.engines import PaddleOCREngine
    from app.services.interfaces import BBox

    paddle = PaddleOCREngine(lang="en", device="cpu")
    print("Nạp PaddleOCR (lang=en)...")

    tinh = OCRMetricsCalculator()
    tat_ca_path: dict[str, dict] = {}

    # ---------- 5 path PaddleOCR × tiền xử lý ----------
    for ten_phep in CAC_PHEP_TIEN_XU_LY_PADDLE:
        ket_qua: list[KetQuaMotMau] = []
        for s in mau:
            img = Image.open(s.crop_path)
            img_xu_ly = tx.ap_dung(ten_phep, img)
            tmp = s.crop_path.parent / f"_tmp_{ten_phep}_{s.sample_id}.png"
            img_xu_ly.convert("RGB").save(tmp)
            t0 = time.perf_counter()
            try:
                text, conf = paddle.recognize(str(tmp), BBox(x=0, y=0, w=img_xu_ly.width, h=img_xu_ly.height))
            except Exception as e:  # noqa: BLE001
                text, conf = f"__LOI__:{e}", None
            rt = time.perf_counter() - t0
            tmp.unlink(missing_ok=True)
            ket_qua.append(KetQuaMotMau(s.sample_id, s.lettering_style, s.text_kind,
                                        s.ground_truth, text, conf, rt))
        path_id = f"paddleocr+{ten_phep}"
        tat_ca_path[path_id] = tinh.tinh_theo_nhom(ket_qua)
        print(f"  xong {path_id}")

    # ---------- 4 path Tesseract × PSM (ảnh gốc, không tiền xử lý) ----------
    for psm in PSM_HO_TRO:
        try:
            eng = TesseractOCREngineBenchmarkAdapter(psm=psm)
        except Exception as e:  # noqa: BLE001
            print(f"  BỎ QUA tesseract_psm{psm}: {e}")
            continue
        ket_qua = []
        for s in mau:
            img = Image.open(s.crop_path)
            t0 = time.perf_counter()
            try:
                text, conf = eng.recognize(img)
            except Exception as e:  # noqa: BLE001
                text, conf = f"__LOI__:{e}", None
            rt = time.perf_counter() - t0
            ket_qua.append(KetQuaMotMau(s.sample_id, s.lettering_style, s.text_kind,
                                        s.ground_truth, text, conf, rt))
        path_id = eng.ten_hien_thi()
        tat_ca_path[path_id] = tinh.tinh_theo_nhom(ket_qua)
        print(f"  xong {path_id}")

    # ---------- So sánh — BẮT BUỘC tách theo nhóm, không chỉ trung bình chung ----------
    print("\n=== SO SÁNH 9 PATH — theo nhóm (§ constraint E20b #7) ===\n")
    hang = ["path", "manh_exact", "manh_cer", "dam_exact", "dam_cer", "runtime_p50_ms"]
    print(f"{'path':28s} {'chữ MẢNH (mục tiêu)':>22s} {'chữ ĐẬM (đối chứng)':>22s} {'p50 ms':>9s}")
    for path_id, kq in tat_ca_path.items():
        manh = kq.theo_nhom.get("italic_thin_on_busy_bg")
        dam = kq.theo_nhom.get("bold_on_busy_bg")
        manh_s = f"{manh.exact_match} cer={manh.cer:.3f}" if manh else "n/a"
        dam_s = f"{dam.exact_match} cer={dam.cer:.3f}" if dam else "n/a"
        print(f"{path_id:28s} {manh_s:>22s} {dam_s:>22s} {kq.runtime_p50_ms:9.0f}")

    def _tu_dien(mr):
        if mr is None:
            return None
        d = {"n_samples": mr.n_samples, "exact_match": str(mr.exact_match), "cer": mr.cer,
             "wer": mr.wer, "runtime_p50_ms": mr.runtime_p50_ms}
        return d

    ra = {}
    for path_id, kq in tat_ca_path.items():
        ra[path_id] = {
            "tong": _tu_dien(kq),
            "theo_nhom": {k: _tu_dien(v) for k, v in kq.theo_nhom.items()},
        }
    RA_JSON.write_text(json.dumps(ra, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nĐã ghi {RA_JSON}")


if __name__ == "__main__":
    main()
