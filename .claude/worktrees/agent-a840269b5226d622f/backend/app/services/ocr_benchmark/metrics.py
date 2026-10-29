"""E20a — tính độ chính xác OCR trên một tập kết quả (dự đoán, sự thật).

Mọi tỉ lệ đi kèm TỬ SỐ/MẪU SỐ tường minh trong `MetricsResult` — một con số phần trăm đứng một
mình không nói được "đo trên 2 mẫu" hay "đo trên 200 mẫu".

Chuẩn hoá Unicode NFC CHỈ để SO SÁNH — không sửa `ground_truth`/`predicted_text` gốc trong kết
quả trả về, để không ai tưởng nhầm hệ thống đã "sửa" OCR ở tầng đo.
"""
from __future__ import annotations

import unicodedata
from collections import Counter
from dataclasses import dataclass, field


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "")


def khoang_cach_levenshtein(a: str, b: str) -> int:
    """Số phép sửa (thêm/xoá/thay) ít nhất để biến `a` thành `b` — nền cho CER/WER.

    Cài tay (không thêm dependency mới): O(len(a)*len(b)) đủ dùng vì mỗi crop chỉ vài chục
    ký tự/từ, không phải văn bản dài.
    """
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    truoc = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        hien = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            chi_phi = 0 if ca == cb else 1
            hien[j] = min(
                truoc[j] + 1,        # xoá
                hien[j - 1] + 1,     # thêm
                truoc[j - 1] + chi_phi,  # thay (hoặc giữ nguyên)
            )
        truoc = hien
    return truoc[-1]


@dataclass
class KetQuaMotMau:
    sample_id: str
    lettering_style: str
    text_kind: str
    ground_truth: str
    predicted_text: str
    confidence: float | None
    runtime_seconds: float


@dataclass
class TiLe:
    """Một tỉ lệ kèm tử số/mẫu số — không để con số phần trăm đứng một mình."""

    tu_so: int
    mau_so: int

    @property
    def ti_le(self) -> float | None:
        return None if self.mau_so == 0 else self.tu_so / self.mau_so

    def __str__(self) -> str:
        if self.mau_so == 0:
            return "n/a (mẫu số = 0)"
        return f"{self.tu_so}/{self.mau_so} ({self.ti_le:.1%})"


@dataclass
class MetricsResult:
    n_samples: int
    exact_match: TiLe
    cer: float                     # tổng khoảng cách sửa / tổng số ký tự ground truth
    cer_tu_so_mau_so: tuple[int, int]
    wer: float | None              # None nếu không có mẫu tiếng Anh nào (dùng khoảng trắng tách từ)
    wer_tu_so_mau_so: tuple[int, int] | None
    missing_character_rate: float
    missing_char_tu_so_mau_so: tuple[int, int]
    missing_line_rate: TiLe | None  # None nếu không có mẫu nhiều dòng nào
    empty_output: TiLe
    runtime_avg_ms: float
    runtime_p50_ms: float
    runtime_p95_ms: float
    theo_nhom: dict[str, "MetricsResult"] = field(default_factory=dict)


def _phan_vi(gia_tri: list[float], p: float) -> float:
    if not gia_tri:
        return 0.0
    ds = sorted(gia_tri)
    idx = min(len(ds) - 1, max(0, round(p * (len(ds) - 1))))
    return ds[idx]


class OCRMetricsCalculator:
    def tinh(self, ket_qua: list[KetQuaMotMau]) -> MetricsResult:
        if not ket_qua:
            raise ValueError("Không có kết quả nào để tính — đừng công bố số liệu từ tập rỗng")

        dung_tuyet_doi = 0
        tong_khoang_cach = 0
        tong_ky_tu_that = 0
        tong_khoang_cach_tu = 0
        tong_so_tu_that = 0
        thieu_ky_tu = 0
        tong_ky_tu_dem_thieu = 0
        dong_thieu = 0
        tong_dong = 0
        rong = 0
        thoi_gian = []

        for r in ket_qua:
            that = _nfc(r.ground_truth)
            du_doan = _nfc(r.predicted_text)

            if du_doan.strip() == that.strip():
                dung_tuyet_doi += 1
            if du_doan.strip() == "":
                rong += 1

            tong_khoang_cach += khoang_cach_levenshtein(du_doan, that)
            tong_ky_tu_that += len(that)

            tu_that = that.split()
            tu_du_doan = du_doan.split()
            tong_khoang_cach_tu += _khoang_cach_tu(tu_du_doan, tu_that)
            tong_so_tu_that += len(tu_that)

            # "Thiếu ký tự": phần ký tự có trong sự thật mà bên dự đoán KHÔNG hề có (đếm theo đa
            # tập hợp) — khác CER ở chỗ không quan tâm THỨ TỰ/thay thế, chỉ đo nội dung bị RỚT.
            dem_that = Counter(that.replace(" ", "").replace("\n", ""))
            dem_du_doan = Counter(du_doan.replace(" ", "").replace("\n", ""))
            for ky_tu, so_luong in dem_that.items():
                con_lai = so_luong - dem_du_doan.get(ky_tu, 0)
                if con_lai > 0:
                    thieu_ky_tu += con_lai
            tong_ky_tu_dem_thieu += sum(dem_that.values())

            if "\n" in that:
                cac_dong = [d.strip() for d in that.split("\n") if d.strip()]
                tong_dong += len(cac_dong)
                for dong in cac_dong:
                    if dong not in du_doan:
                        dong_thieu += 1

            thoi_gian.append(r.runtime_seconds * 1000)

        n = len(ket_qua)
        return MetricsResult(
            n_samples=n,
            exact_match=TiLe(dung_tuyet_doi, n),
            cer=(tong_khoang_cach / tong_ky_tu_that) if tong_ky_tu_that else 0.0,
            cer_tu_so_mau_so=(tong_khoang_cach, tong_ky_tu_that),
            wer=(tong_khoang_cach_tu / tong_so_tu_that) if tong_so_tu_that else None,
            wer_tu_so_mau_so=(tong_khoang_cach_tu, tong_so_tu_that) if tong_so_tu_that else None,
            missing_character_rate=(thieu_ky_tu / tong_ky_tu_dem_thieu) if tong_ky_tu_dem_thieu else 0.0,
            missing_char_tu_so_mau_so=(thieu_ky_tu, tong_ky_tu_dem_thieu),
            missing_line_rate=TiLe(dong_thieu, tong_dong) if tong_dong else None,
            empty_output=TiLe(rong, n),
            runtime_avg_ms=sum(thoi_gian) / n,
            runtime_p50_ms=_phan_vi(thoi_gian, 0.50),
            runtime_p95_ms=_phan_vi(thoi_gian, 0.95),
        )

    def tinh_theo_nhom(
        self, ket_qua: list[KetQuaMotMau], *, truong: str = "lettering_style"
    ) -> MetricsResult:
        """Tổng thể + tách theo `lettering_style` (mặc định) — bắt buộc theo Success Criteria
        của E20a: không được chỉ báo trung bình chung, phải thấy rõ nhóm chữ HOA/nghiêng so với
        nhóm chữ bình thường."""
        tong = self.tinh(ket_qua)
        nhom: dict[str, list[KetQuaMotMau]] = {}
        for r in ket_qua:
            khoa = getattr(r, truong)
            nhom.setdefault(khoa, []).append(r)
        tong.theo_nhom = {k: self.tinh(v) for k, v in nhom.items()}
        return tong


def _khoang_cach_tu(a: list[str], b: list[str]) -> int:
    """Levenshtein trên danh sách TỪ (không phải ký tự) — dùng lại thuật toán trên bằng cách coi
    mỗi từ như một 'ký tự'."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    truoc = list(range(len(b) + 1))
    for i, wa in enumerate(a, start=1):
        hien = [i] + [0] * len(b)
        for j, wb in enumerate(b, start=1):
            chi_phi = 0 if wa == wb else 1
            hien[j] = min(truoc[j] + 1, hien[j - 1] + 1, truoc[j - 1] + chi_phi)
        truoc = hien
    return truoc[-1]
