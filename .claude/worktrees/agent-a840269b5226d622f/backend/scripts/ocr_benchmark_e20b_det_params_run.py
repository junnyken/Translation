"""E20b phụ lục — đo tham số DETECTION của PaddleOCR trên đúng bộ mẫu đã cho ra 0/10.

Khác 9 path của `ocr_benchmark_e20b_run.py`: ở đó biến số là **pixel đầu vào**; ở đây pixel giữ
NGUYÊN (không tiền xử lý gì) và biến số là **tham số bộ detect của chính PaddleOCR** — cần gạt
chưa từng thử, nhắm thẳng nguyên nhân gốc đã chốt ở `REPORT_E20a.md §10`.

Chạy trong container worker (PaddleOCR có sẵn):

    docker compose -f deploy/docker-compose.yml run --rm -e PYTHONPATH=/app worker \
        python scripts/ocr_benchmark_e20b_det_params_run.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
MANIFEST = BACKEND_DIR / "test_fixtures" / "external" / "ocr_benchmark_e20b" / "manifest.jsonl"
RA_JSON = MANIFEST.parent / "ket_qua_e20b_det_params.json"

sys.path.insert(0, str(BACKEND_DIR))

from PIL import Image  # noqa: E402

from app.services.ocr_benchmark.dataset import (  # noqa: E402
    GroundTruthValidator,
    OCRBenchmarkDatasetLoader,
)
from app.services.ocr_benchmark.metrics import KetQuaMotMau, OCRMetricsCalculator  # noqa: E402
from app.services.ocr_benchmark.paddle_tuned import (  # noqa: E402
    CAC_CAU_HINH,
    LY_DO_BO_LIMIT_SIDE_LEN,
    PaddleOCRDetectTuned,
)


def main() -> None:
    loader = OCRBenchmarkDatasetLoader(MANIFEST)
    mau = loader.nap()
    loi = GroundTruthValidator.kiem(mau)
    if loi:
        raise SystemExit(f"Manifest E20b hỏng: {loi}")
    print(f"Manifest hợp lệ: {len(mau)} mẫu.")
    print(f"Bỏ text_det_limit_side_len khỏi thí nghiệm — {LY_DO_BO_LIMIT_SIDE_LEN}.\n")

    from app.services.interfaces import BBox  # noqa: E402

    tinh = OCRMetricsCalculator()
    tat_ca: dict[str, dict] = {}

    for ch in CAC_CAU_HINH:
        print(f"Nạp PaddleOCR [{ch.ten}] {ch.mo_ta_tham_so()}")
        eng = PaddleOCRDetectTuned(ch, lang="en", device="cpu")
        ket_qua: list[KetQuaMotMau] = []
        for s in mau:
            with Image.open(s.crop_path) as im:
                w, h = im.size
            t0 = time.perf_counter()
            try:
                # Ảnh KHÔNG qua tiền xử lý: biến số duy nhất so với baseline là tham số detect.
                text, conf = eng.recognize(str(s.crop_path), BBox(x=0, y=0, w=w, h=h))
            except Exception as e:  # noqa: BLE001
                text, conf = f"__LOI__:{e}", None
            rt = time.perf_counter() - t0
            ket_qua.append(KetQuaMotMau(s.sample_id, s.lettering_style, s.text_kind,
                                        s.ground_truth, text, conf, rt))
        tat_ca[ch.ten] = {"cau_hinh": ch.tham_so, "gia_thuyet": ch.gia_thuyet,
                          "kq": tinh.tinh_theo_nhom(ket_qua)}
        print(f"  xong {ch.ten}")

    print("\n=== THAM SỐ DETECTION — theo nhóm (cột MẢNH là cột quyết định) ===\n")
    print(f"{'cấu hình':16s} {'chữ MẢNH (mục tiêu)':>22s} {'chữ ĐẬM (đối chứng)':>22s} {'p50 ms':>9s}")
    for ten, o in tat_ca.items():
        kq = o["kq"]
        manh = kq.theo_nhom.get("italic_thin_on_busy_bg")
        dam = kq.theo_nhom.get("bold_on_busy_bg")
        manh_s = f"{manh.exact_match} cer={manh.cer:.3f}" if manh else "n/a"
        dam_s = f"{dam.exact_match} cer={dam.cer:.3f}" if dam else "n/a"
        print(f"{ten:16s} {manh_s:>22s} {dam_s:>22s} {kq.runtime_p50_ms:9.0f}")

    def _tu_dien(mr):
        if mr is None:
            return None
        return {"n_samples": mr.n_samples, "exact_match": str(mr.exact_match), "cer": mr.cer,
                "wer": mr.wer, "runtime_p50_ms": mr.runtime_p50_ms}

    ra = {}
    for ten, o in tat_ca.items():
        kq = o["kq"]
        ra[ten] = {
            "cau_hinh": o["cau_hinh"],
            "gia_thuyet": o["gia_thuyet"],
            "tong": _tu_dien(kq),
            "theo_nhom": {k: _tu_dien(v) for k, v in kq.theo_nhom.items()},
        }
    ra["_ghi_chu"] = {"bo_limit_side_len": LY_DO_BO_LIMIT_SIDE_LEN}
    RA_JSON.write_text(json.dumps(ra, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nĐã ghi {RA_JSON}")


if __name__ == "__main__":
    main()
