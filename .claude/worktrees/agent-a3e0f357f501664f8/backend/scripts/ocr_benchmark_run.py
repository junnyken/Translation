"""E20a — chạy PaddleOCR baseline thật trên bộ benchmark, in + ghi kết quả.

Cần `paddleocr` cài sẵn — chỉ có trong image `worker` (xem `deploy/Dockerfile`), KHÔNG có trong
`.venv` cục bộ (M3 import trễ có chủ đích). Chạy bằng:

    docker compose -f deploy/docker-compose.yml run --rm worker \
        python scripts/ocr_benchmark_run.py

Đọc-only: không mở kết nối DB/Redis nào (không import `app.core.db`, không import
`app.workers.tasks`) — chỉ dùng đúng `PaddleOCREngine` từ `app.services.ocr.engines`, đúng
adapter M3 mà không cần cả hạ tầng job/queue.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.services.ocr.engines import PaddleOCREngine
from app.services.ocr_benchmark.dataset import GroundTruthValidator, OCRBenchmarkDatasetLoader
from app.services.ocr_benchmark.metrics import KetQuaMotMau, MetricsResult, OCRMetricsCalculator
from app.services.ocr_benchmark.runner import OCRBenchmarkRunner

#: Thư mục `backend/` — cục bộ là `<repo>/backend`, trong container worker là `/app` (Dockerfile
#: `COPY . .` từ context `../backend`, không có lớp `backend/` lồng bên trong). Tính theo
#: `parents[1]` (thư mục CHA của `scripts/`) để đúng cả hai nơi, không hardcode "backend".
BACKEND_DIR = Path(__file__).resolve().parents[1]
MANIFEST = BACKEND_DIR / "test_fixtures" / "external" / "ocr_benchmark" / "manifest.jsonl"
KET_QUA_RA = MANIFEST.parent / "ket_qua_paddleocr_baseline.json"


def _tom_tat(m: MetricsResult) -> dict:
    return {
        "n_samples": m.n_samples,
        "exact_match": str(m.exact_match),
        "cer": round(m.cer, 4),
        "cer_tu_so_mau_so": list(m.cer_tu_so_mau_so),
        "wer": round(m.wer, 4) if m.wer is not None else None,
        "wer_tu_so_mau_so": list(m.wer_tu_so_mau_so) if m.wer_tu_so_mau_so else None,
        "missing_character_rate": round(m.missing_character_rate, 4),
        "missing_char_tu_so_mau_so": list(m.missing_char_tu_so_mau_so),
        "missing_line_rate": str(m.missing_line_rate) if m.missing_line_rate else None,
        "empty_output": str(m.empty_output),
        "runtime_avg_ms": round(m.runtime_avg_ms, 1),
        "runtime_p50_ms": round(m.runtime_p50_ms, 1),
        "runtime_p95_ms": round(m.runtime_p95_ms, 1),
    }


def main() -> None:
    loader = OCRBenchmarkDatasetLoader(MANIFEST)
    mau = loader.nap()
    loi = GroundTruthValidator.kiem(mau)
    if loi:
        print(f"DỪNG — manifest có {len(loi)} lỗi, không chạy benchmark trên dữ liệu hỏng:")
        for l in loi:
            print(f"  - {l}")
        raise SystemExit(1)
    print(f"Manifest hợp lệ: {len(mau)} mẫu.")

    engine = PaddleOCREngine(lang="en")
    print("Nạp PaddleOCR (lang=en)... (lần đầu chậm, model nạp lười)")
    runner = OCRBenchmarkRunner(engine)

    ket_qua: list[KetQuaMotMau] = []
    for i, m in enumerate(mau, 1):
        r = runner.chay_mot(m)
        ket_qua.append(r)
        dung = "✓" if r.predicted_text.strip() == r.ground_truth.strip() else "✗"
        print(f"  [{i:2d}/{len(mau)}] {dung} {m.sample_id} ({m.lettering_style}) "
              f"{r.runtime_seconds*1000:.0f}ms")

    calc = OCRMetricsCalculator()
    tong = calc.tinh_theo_nhom(ket_qua)

    print("\n=== TỔNG THỂ ===")
    print(json.dumps(_tom_tat(tong), ensure_ascii=False, indent=2))
    print("\n=== THEO lettering_style ===")
    for nhom, m in sorted(tong.theo_nhom.items()):
        print(f"\n-- {nhom} --")
        print(json.dumps(_tom_tat(m), ensure_ascii=False, indent=2))

    ra = {
        "engine": "paddle_ocr(lang=en)",
        "tong_the": _tom_tat(tong),
        "theo_nhom": {k: _tom_tat(v) for k, v in tong.theo_nhom.items()},
        "chi_tiet_tung_mau": [
            {
                "sample_id": r.sample_id, "lettering_style": r.lettering_style,
                "ground_truth": r.ground_truth, "predicted_text": r.predicted_text,
                "confidence": r.confidence, "runtime_ms": round(r.runtime_seconds * 1000, 1),
                "dung_tuyet_doi": r.predicted_text.strip() == r.ground_truth.strip(),
            }
            for r in ket_qua
        ],
    }
    KET_QUA_RA.write_text(json.dumps(ra, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nĐã ghi {KET_QUA_RA}")


if __name__ == "__main__":
    main()
