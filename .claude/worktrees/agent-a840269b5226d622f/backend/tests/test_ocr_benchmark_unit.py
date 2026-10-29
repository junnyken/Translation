"""E20a — harness benchmark OCR: nạp manifest, kiểm dữ liệu, tính chỉ số.

CỐ Ý không phụ thuộc `test_fixtures/external/ocr_benchmark/` (bị gitignore, dựng bằng
`scripts/ocr_benchmark_generate_dataset.py`) — test ở đây tự dựng manifest/crop tối giản trong
`tmp_path`, để chạy được trên máy CHƯA từng chạy script dựng dataset (kể cả CI).
"""
from __future__ import annotations

import json

import pytest
from PIL import Image

from app.services.ocr_benchmark.dataset import (
    GroundTruthValidator,
    ManifestKhongHopLe,
    OCRBenchmarkDatasetLoader,
)
from app.services.ocr_benchmark.metrics import KetQuaMotMau, OCRMetricsCalculator, khoang_cach_levenshtein


def _dong_manifest(**ghi_de) -> dict:
    mac_dinh = {
        "sample_id": "s1", "source_category": "synthetic_test", "license_scope": "OFL-1.1",
        "language": "en", "text_kind": "dialogue", "lettering_style": "normal_handlettered",
        "rotation_bucket": "none", "crop_path": "s1.png", "ground_truth": "hello world",
        "notes": "", "include_in_public_report": True,
    }
    mac_dinh.update(ghi_de)
    return mac_dinh


def _dung_manifest(thu_muc, dong: list[dict]) -> None:
    (thu_muc / "crops").mkdir(exist_ok=True)
    with (thu_muc / "manifest.jsonl").open("w", encoding="utf-8") as f:
        for d in dong:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")


def _tao_anh(thu_muc, ten: str) -> None:
    Image.new("RGB", (40, 20), "white").save(thu_muc / "crops" / ten)


class TestOCRBenchmarkDatasetLoader:
    def test_nap_dung_thi_ra_du_so_mau(self, tmp_path):
        _dung_manifest(tmp_path, [_dong_manifest(sample_id="a"), _dong_manifest(sample_id="b")])
        mau = OCRBenchmarkDatasetLoader(tmp_path / "manifest.jsonl").nap()
        assert len(mau) == 2
        assert {m.sample_id for m in mau} == {"a", "b"}

    def test_crop_path_thanh_duong_dan_tuyet_doi_duoi_thu_muc_crops(self, tmp_path):
        _dung_manifest(tmp_path, [_dong_manifest(crop_path="con/s1.png")])
        mau = OCRBenchmarkDatasetLoader(tmp_path / "manifest.jsonl").nap()
        assert mau[0].crop_path == tmp_path / "crops" / "con" / "s1.png"

    def test_thieu_manifest_bao_ro_khong_im_lang(self, tmp_path):
        with pytest.raises(ManifestKhongHopLe):
            OCRBenchmarkDatasetLoader(tmp_path / "khong_ton_tai.jsonl").nap()

    def test_dong_json_hong_bao_ro(self, tmp_path):
        (tmp_path / "crops").mkdir()
        (tmp_path / "manifest.jsonl").write_text("{khong phai json}\n", encoding="utf-8")
        with pytest.raises(ManifestKhongHopLe):
            OCRBenchmarkDatasetLoader(tmp_path / "manifest.jsonl").nap()

    @pytest.mark.parametrize("truong_thieu", [
        "sample_id", "source_category", "license_scope", "language", "text_kind",
        "lettering_style", "rotation_bucket", "crop_path", "ground_truth", "notes",
        "include_in_public_report",
    ])
    def test_thieu_bat_ky_truong_bat_buoc_nao_deu_bi_chan(self, tmp_path, truong_thieu):
        dong = _dong_manifest()
        del dong[truong_thieu]
        _dung_manifest(tmp_path, [dong])
        with pytest.raises(ManifestKhongHopLe):
            OCRBenchmarkDatasetLoader(tmp_path / "manifest.jsonl").nap()

    def test_include_in_public_report_sai_kieu_bi_chan(self, tmp_path):
        _dung_manifest(tmp_path, [_dong_manifest(include_in_public_report="co")])
        with pytest.raises(ManifestKhongHopLe):
            OCRBenchmarkDatasetLoader(tmp_path / "manifest.jsonl").nap()


class TestGroundTruthValidator:
    def test_du_lieu_hop_le_khong_co_loi(self, tmp_path):
        _dung_manifest(tmp_path, [_dong_manifest(sample_id="a", crop_path="a.png")])
        _tao_anh(tmp_path, "a.png")
        mau = OCRBenchmarkDatasetLoader(tmp_path / "manifest.jsonl").nap()
        assert GroundTruthValidator.kiem(mau) == []

    def test_bat_duoc_trung_sample_id(self, tmp_path):
        _dung_manifest(tmp_path, [
            _dong_manifest(sample_id="a", crop_path="a.png"),
            _dong_manifest(sample_id="a", crop_path="a2.png"),
        ])
        _tao_anh(tmp_path, "a.png")
        _tao_anh(tmp_path, "a2.png")
        mau = OCRBenchmarkDatasetLoader(tmp_path / "manifest.jsonl").nap()
        loi = GroundTruthValidator.kiem(mau)
        assert any("trùng sample_id" in l for l in loi)

    def test_bat_duoc_ground_truth_rong_khong_danh_dau(self, tmp_path):
        _dung_manifest(tmp_path, [_dong_manifest(sample_id="a", crop_path="a.png", ground_truth="  ")])
        _tao_anh(tmp_path, "a.png")
        mau = OCRBenchmarkDatasetLoader(tmp_path / "manifest.jsonl").nap()
        loi = GroundTruthValidator.kiem(mau)
        assert any("ground_truth rỗng" in l for l in loi)

    def test_ground_truth_rong_CO_danh_dau_thi_qua(self, tmp_path):
        _dung_manifest(tmp_path, [_dong_manifest(
            sample_id="a", crop_path="a.png", ground_truth="",
            notes="intentionally-empty: khung không chữ",
        )])
        _tao_anh(tmp_path, "a.png")
        mau = OCRBenchmarkDatasetLoader(tmp_path / "manifest.jsonl").nap()
        loi = GroundTruthValidator.kiem(mau)
        assert not any("ground_truth rỗng" in l for l in loi)

    def test_bat_duoc_thieu_file_crop(self, tmp_path):
        _dung_manifest(tmp_path, [_dong_manifest(sample_id="a", crop_path="khong-ton-tai.png")])
        mau = OCRBenchmarkDatasetLoader(tmp_path / "manifest.jsonl").nap()
        loi = GroundTruthValidator.kiem(mau)
        assert any("không thấy file crop" in l for l in loi)

    def test_bat_duoc_thieu_license_scope(self, tmp_path):
        _dung_manifest(tmp_path, [_dong_manifest(sample_id="a", crop_path="a.png", license_scope="")])
        _tao_anh(tmp_path, "a.png")
        mau = OCRBenchmarkDatasetLoader(tmp_path / "manifest.jsonl").nap()
        loi = GroundTruthValidator.kiem(mau)
        assert any("thiếu license_scope" in l for l in loi)


class TestKhoangCachLevenshtein:
    def test_giong_het_thi_bang_0(self):
        assert khoang_cach_levenshtein("abc", "abc") == 0

    def test_mot_ky_tu_khac_thi_bang_1(self):
        assert khoang_cach_levenshtein("abc", "abd") == 1

    def test_chuoi_rong_bang_do_dai_chuoi_kia(self):
        assert khoang_cach_levenshtein("", "abc") == 3
        assert khoang_cach_levenshtein("abc", "") == 3

    def test_vi_du_kinh_dien_kitten_sitting(self):
        assert khoang_cach_levenshtein("kitten", "sitting") == 3


class TestOCRMetricsCalculator:
    def test_tat_ca_dung_tuyet_doi(self):
        kq = [
            KetQuaMotMau("a", "normal_handlettered", "dialogue", "hello", "hello", 0.9, 0.1),
            KetQuaMotMau("b", "normal_handlettered", "dialogue", "world", "world", 0.9, 0.1),
        ]
        m = OCRMetricsCalculator().tinh(kq)
        assert m.exact_match.tu_so == 2 and m.exact_match.mau_so == 2
        assert m.cer == 0.0
        assert m.wer == 0.0
        assert m.empty_output.tu_so == 0

    def test_cer_tinh_dung_tren_vi_du_biet_truoc(self):
        # "kitten" -> "sitting": khoảng cách 3, độ dài ground truth "sitting" = 7 ký tự.
        kq = [KetQuaMotMau("a", "x", "dialogue", "sitting", "kitten", None, 0.0)]
        m = OCRMetricsCalculator().tinh(kq)
        assert m.cer_tu_so_mau_so == (3, 7)
        assert m.cer == pytest.approx(3 / 7)

    def test_wer_tinh_theo_tu_khong_theo_ky_tu(self):
        kq = [KetQuaMotMau("a", "x", "dialogue", "the quick brown fox", "the quick red fox", None, 0.0)]
        m = OCRMetricsCalculator().tinh(kq)
        # 1 từ khác ("brown" vs "red") trong 4 từ ground truth.
        assert m.wer_tu_so_mau_so == (1, 4)

    def test_output_rong_tinh_dung_ti_le(self):
        kq = [
            KetQuaMotMau("a", "x", "dialogue", "hello", "", None, 0.0),
            KetQuaMotMau("b", "x", "dialogue", "world", "world", None, 0.0),
        ]
        m = OCRMetricsCalculator().tinh(kq)
        assert m.empty_output.tu_so == 1 and m.empty_output.mau_so == 2

    def test_missing_character_rate_dem_dung(self):
        # ground truth "abcde" (5 ký tự), dự đoán chỉ có "ace" -> thiếu 'b' và 'd' = 2/5.
        kq = [KetQuaMotMau("a", "x", "dialogue", "abcde", "ace", None, 0.0)]
        m = OCRMetricsCalculator().tinh(kq)
        assert m.missing_char_tu_so_mau_so == (2, 5)
        assert m.missing_character_rate == pytest.approx(2 / 5)

    def test_missing_line_rate_chi_tinh_tren_mau_nhieu_dong(self):
        kq = [
            KetQuaMotMau("a", "x", "dialogue", "line one\nline two", "line one\nline two", None, 0.0),
            KetQuaMotMau("b", "x", "dialogue", "single line", "single line", None, 0.0),
        ]
        m = OCRMetricsCalculator().tinh(kq)
        assert m.missing_line_rate is not None
        assert m.missing_line_rate.mau_so == 2  # chỉ đếm 2 dòng của mẫu "a"

    def test_khong_co_mau_nhieu_dong_thi_missing_line_rate_la_none(self):
        kq = [KetQuaMotMau("a", "x", "dialogue", "single line", "single line", None, 0.0)]
        m = OCRMetricsCalculator().tinh(kq)
        assert m.missing_line_rate is None

    def test_rong_thi_bao_loi_khong_tra_so_lieu_gia(self):
        with pytest.raises(ValueError):
            OCRMetricsCalculator().tinh([])

    def test_tinh_theo_nhom_tach_dung_lettering_style(self):
        kq = [
            KetQuaMotMau("a", "normal_handlettered", "dialogue", "hi", "hi", None, 0.0),
            KetQuaMotMau("b", "uppercase_tight", "dialogue", "HI", "XX", None, 0.0),
        ]
        tong = OCRMetricsCalculator().tinh_theo_nhom(kq)
        assert tong.n_samples == 2
        assert set(tong.theo_nhom) == {"normal_handlettered", "uppercase_tight"}
        assert tong.theo_nhom["normal_handlettered"].exact_match.tu_so == 1
        assert tong.theo_nhom["uppercase_tight"].exact_match.tu_so == 0

    def test_runtime_percentile_hop_ly(self):
        kq = [
            KetQuaMotMau(f"s{i}", "x", "dialogue", "a", "a", None, giay)
            for i, giay in enumerate([0.1, 0.2, 0.3, 0.4, 0.5])
        ]
        m = OCRMetricsCalculator().tinh(kq)
        assert m.runtime_avg_ms == pytest.approx(300.0)
        assert m.runtime_p50_ms == pytest.approx(300.0)
        assert m.runtime_p95_ms == pytest.approx(500.0)
