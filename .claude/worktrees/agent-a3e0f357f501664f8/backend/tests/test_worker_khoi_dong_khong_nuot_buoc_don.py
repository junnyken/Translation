"""Hàm khởi động worker phải chạy ĐỦ ba bước: ghi dấu sẵn sàng → dọn job mồ côi → đánh thức mẻ.

Lỗi thật thấy trong log production 15-10-2026 (có từ E55): một `import logging` nằm TRONG thân hàm
biến `logging` thành biến cục bộ của cả hàm ⇒ dòng ghi dấu sẵn sàng nổ `UnboundLocalError`, nổ tiếp
trong `except` của chính nó, văng ra ngoài ⇒ hai bước sau KHÔNG BAO GIỜ chạy: job mồ côi không được
dọn, mẻ dịch đứng im sau mỗi lần worker chết.
"""
from __future__ import annotations

import ast
import inspect
import textwrap

from app.workers import celery_app as mod


def test_khong_import_trong_than_ham_lam_bong_ten_logging():
    cay = ast.parse(textwrap.dedent(inspect.getsource(mod._don_job_mo_coi_luc_khoi_dong)))
    nhap = [n for n in ast.walk(cay) if isinstance(n, ast.Import)
            and any(a.name == "logging" for a in n.names)]
    assert nhap == []


def test_chay_du_ba_buoc(monkeypatch):
    goi = []
    monkeypatch.setattr("app.workers.trang_thai_worker.ghi_dau_san_sang",
                        lambda: goi.append("san_sang") or "luc")
    monkeypatch.setattr("app.workers.hoi_phuc.don_job_mo_coi",
                        lambda s, ap_dung: goi.append("don"))

    class _DieuPhoi:
        def danh_thuc_me_dang_do(self):
            goi.append("danh_thuc")

    monkeypatch.setattr("app.services.batch.factory.tao_dieu_phoi", lambda st: _DieuPhoi())
    monkeypatch.setattr(mod.settings, "worker_sweep_orphan_jobs_on_start", True)
    monkeypatch.setattr(mod.settings, "batch_enabled", True)
    monkeypatch.setattr(mod.settings, "batch_danh_thuc_khi_worker_khoi_dong", True)
    mod._don_job_mo_coi_luc_khoi_dong()
    assert goi == ["san_sang", "don", "danh_thuc"]


def test_buoc_dau_hong_van_chay_buoc_sau(monkeypatch):
    goi = []

    def _hong():
        raise RuntimeError("redis chết")
    monkeypatch.setattr("app.workers.trang_thai_worker.ghi_dau_san_sang", _hong)
    monkeypatch.setattr("app.workers.hoi_phuc.don_job_mo_coi", lambda s, ap_dung: goi.append("don"))
    monkeypatch.setattr(mod.settings, "worker_sweep_orphan_jobs_on_start", True)
    monkeypatch.setattr(mod.settings, "batch_enabled", False)
    mod._don_job_mo_coi_luc_khoi_dong()
    assert goi == ["don"]
