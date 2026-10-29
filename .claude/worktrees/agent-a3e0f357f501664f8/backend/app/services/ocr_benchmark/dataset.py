"""E20a — nạp + kiểm manifest benchmark OCR.

Manifest là JSONL local (`test_fixtures/external/ocr_benchmark/manifest.jsonl`, bị gitignore —
dựng lại bằng `scripts/ocr_benchmark_generate_dataset.py`), KHÔNG phải bảng CSDL. Cố ý: tách
hẳn dữ liệu benchmark khỏi dữ liệu chapter thật của người dùng, không lẫn lộn.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

TRUONG_BAT_BUOC = (
    "sample_id", "source_category", "license_scope", "language", "text_kind",
    "lettering_style", "rotation_bucket", "crop_path", "ground_truth", "notes",
    "include_in_public_report",
)

#: `ground_truth` được phép rỗng CHỈ khi sample cố ý đánh dấu vậy trong `notes` — hiện dataset
#: E20a không có ca nào, nhưng giữ cờ này để không phải sửa loader nếu sau này thêm "ảnh không
#: có chữ" làm ca âm tính.
CO_Y_RONG = "intentionally-empty"


class ManifestKhongHopLe(ValueError):
    """Một dòng manifest thiếu trường/sai kiểu — dừng nạp, không bỏ qua âm thầm."""


@dataclass(frozen=True)
class BenchmarkSample:
    sample_id: str
    source_category: str
    license_scope: str
    language: str
    text_kind: str
    lettering_style: str
    rotation_bucket: str
    crop_path: Path
    ground_truth: str
    notes: str
    include_in_public_report: bool


class OCRBenchmarkDatasetLoader:
    """Đọc `manifest.jsonl`, trả về danh sách `BenchmarkSample` với `crop_path` đã thành
    đường dẫn TUYỆT ĐỐI (tương đối tính từ thư mục chứa manifest, không phải cwd lúc chạy)."""

    def __init__(self, manifest_path: Path) -> None:
        self.manifest_path = Path(manifest_path)
        self.goc = self.manifest_path.parent

    def nap(self) -> list[BenchmarkSample]:
        if not self.manifest_path.exists():
            raise ManifestKhongHopLe(
                f"Không thấy manifest: {self.manifest_path}. Chạy "
                "scripts/ocr_benchmark_generate_dataset.py trước."
            )
        ket_qua: list[BenchmarkSample] = []
        for so_dong, dong in enumerate(
            self.manifest_path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            dong = dong.strip()
            if not dong:
                continue
            try:
                d = json.loads(dong)
            except json.JSONDecodeError as exc:
                raise ManifestKhongHopLe(f"Dòng {so_dong}: JSON hỏng — {exc}") from exc
            thieu = [t for t in TRUONG_BAT_BUOC if t not in d]
            if thieu:
                raise ManifestKhongHopLe(f"Dòng {so_dong}: thiếu trường {thieu}")
            if not isinstance(d["include_in_public_report"], bool):
                raise ManifestKhongHopLe(
                    f"Dòng {so_dong}: include_in_public_report phải là bool"
                )
            ket_qua.append(BenchmarkSample(
                sample_id=d["sample_id"],
                source_category=d["source_category"],
                license_scope=d["license_scope"],
                language=d["language"],
                text_kind=d["text_kind"],
                lettering_style=d["lettering_style"],
                rotation_bucket=d["rotation_bucket"],
                crop_path=self.goc / "crops" / d["crop_path"],
                ground_truth=d["ground_truth"],
                notes=d["notes"],
                include_in_public_report=d["include_in_public_report"],
            ))
        return ket_qua


class GroundTruthValidator:
    """Kiểm tra bộ mẫu ĐÃ NẠP, độc lập với `OCRBenchmarkDatasetLoader` — để test được từng phần
    riêng (loader hỏng vs dữ liệu hỏng là hai loại lỗi khác nhau, không nên trộn)."""

    @staticmethod
    def kiem(mau: list[BenchmarkSample]) -> list[str]:
        """Trả danh sách LỖI (rỗng = hợp lệ). Không raise — gọi nơi cần tự quyết định có dừng
        hay chỉ cảnh báo."""
        loi: list[str] = []

        da_thay: set[str] = set()
        for s in mau:
            if s.sample_id in da_thay:
                loi.append(f"trùng sample_id: {s.sample_id}")
            da_thay.add(s.sample_id)

            if not s.ground_truth.strip() and CO_Y_RONG not in s.notes:
                loi.append(f"{s.sample_id}: ground_truth rỗng mà không đánh dấu '{CO_Y_RONG}'")

            if not s.crop_path.exists():
                loi.append(f"{s.sample_id}: không thấy file crop {s.crop_path}")

            if not s.license_scope.strip():
                loi.append(f"{s.sample_id}: thiếu license_scope")

        return loi
