"""E22 (thu hẹp theo audit) — đọc lại bằng chứng thoát tiến trình do `deploy-start.sh` ghi sẵn.

Đơn vị thuần: không cần Redis/Postgres, chỉ thao tác file tạm + biến môi trường.
"""
from __future__ import annotations

import json

import pytest

from app.workers.trang_thai_worker import (
    doc_trang_thai_worker,
    doc_va_phan_loai,
    phan_loai_tu_ma_thoat,
)


class TestPhanLoaiTuMaThoat:
    def test_137_la_nghi_ngo_het_bo_nho_KHONG_phai_chac_chan(self):
        error_class, exit_signal = phan_loai_tu_ma_thoat(137)
        assert error_class == "resource_limit_suspected"
        assert "confirmed" not in error_class, "chưa có bằng chứng nền tảng — không được nói chắc"
        assert exit_signal == "SIGKILL(137)"

    def test_ma_khac_137_la_worker_lost(self):
        error_class, exit_signal = phan_loai_tu_ma_thoat(1)
        assert error_class == "worker_lost"
        assert exit_signal == "exit(1)"

    def test_khong_biet_ma_thoat_van_la_worker_lost(self):
        """Không có mã thoát không có nghĩa là không có gì xảy ra — sweep chỉ chạy vì worker
        VỪA chết (xem docstring `hoi_phuc.py`), chỉ là thiếu chi tiết mã thoát."""
        error_class, exit_signal = phan_loai_tu_ma_thoat(None)
        assert error_class == "worker_lost"
        assert exit_signal is None


class TestDocTrangThaiWorker:
    def test_tep_khong_ton_tai_tra_khong_ro_khong_raise(self, tmp_path, monkeypatch):
        monkeypatch.setenv("WORKER_STATE_FILE", str(tmp_path / "khong-ton-tai.json"))
        assert doc_trang_thai_worker() == {"trang_thai": "khong_ro"}

    def test_tep_hong_json_tra_khong_ro_khong_raise(self, tmp_path, monkeypatch):
        p = tmp_path / "hong.json"
        p.write_text("{khong phai json")
        monkeypatch.setenv("WORKER_STATE_FILE", str(p))
        assert doc_trang_thai_worker() == {"trang_thai": "khong_ro"}

    def test_doc_dung_dinh_dang_deploy_start_ghi(self, tmp_path, monkeypatch):
        p = tmp_path / "trang-thai.json"
        p.write_text(json.dumps({
            "trang_thai": "restarting", "so_lan_chet": 2, "ma_thoat_gan_nhat": 137,
            "luc": "2026-09-09T07:17:29Z",
        }))
        monkeypatch.setenv("WORKER_STATE_FILE", str(p))
        assert doc_trang_thai_worker()["ma_thoat_gan_nhat"] == 137


class TestDocVaPhanLoai:
    def test_gop_doc_va_phan_loai_dung_luong(self, tmp_path, monkeypatch):
        p = tmp_path / "trang-thai.json"
        p.write_text(json.dumps({
            "trang_thai": "restarting", "so_lan_chet": 1, "ma_thoat_gan_nhat": 137,
            "luc": "2026-09-09T07:17:29Z",
        }))
        monkeypatch.setenv("WORKER_STATE_FILE", str(p))
        assert doc_va_phan_loai() == ("resource_limit_suspected", "SIGKILL(137)")

    def test_khong_co_tep_thi_worker_lost_khong_ro_tin_hieu(self, tmp_path, monkeypatch):
        monkeypatch.setenv("WORKER_STATE_FILE", str(tmp_path / "khong-co.json"))
        assert doc_va_phan_loai() == ("worker_lost", None)
