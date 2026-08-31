"""P3h — đo và ghìm bộ nhớ worker.

Sinh ra sau một sự cố THẬT: pilot 6 trang trên host làm worker bị OOM killer giết (`exit 137`),
API tụt từ 3,4 ms xuống 10–42 s rồi tắt tiếng. Không ai thấy nó tới lúc chết vì hệ thống không
có một chỉ số bộ nhớ nào.
"""
from __future__ import annotations

import numpy as np
import pytest

from app.services.inpaint.lama import _DAI_TRON
from app.workers import bo_nho


class TestDoRSS:
    def test_doc_duoc_va_la_so_duong(self):
        r = bo_nho.rss_mb()
        assert r is not None and r > 0

    def test_khong_doc_duoc_thi_tra_None_chu_khong_phai_0(self, monkeypatch):
        """0 = 'đo được và bằng không'. None = 'không đo được'. Gộp hai thứ đó là cách nhanh
        nhất để có một biểu đồ nói dối."""
        def no(*a, **k):
            raise OSError("giả lập không đọc được")
        monkeypatch.setattr("builtins.open", no)
        assert bo_nho.rss_mb() is None


class TestVanXa:
    def test_nguong_0_thi_khong_bao_gio_nha(self, monkeypatch):
        monkeypatch.setattr(bo_nho, "rss_mb", lambda: 99_999.0)
        assert bo_nho.ep_giai_phong_neu_cang({"detector"}, 0) == []

    def test_duoi_nguong_thi_giu_nguyen_cache(self, monkeypatch):
        from app.workers import tasks
        monkeypatch.setattr(tasks, "_inpainter", object())
        monkeypatch.setattr(bo_nho, "rss_mb", lambda: 100.0)
        assert bo_nho.ep_giai_phong_neu_cang({"detector"}, 2200) == []
        assert tasks._inpainter is not None, "chưa căng mà đã nhả — mất tốc độ vô ích"

    def test_vuot_nguong_thi_nha_dung_thu_khong_can(self, monkeypatch):
        from app.workers import tasks
        monkeypatch.setattr(tasks, "_detector", object())
        monkeypatch.setattr(tasks, "_inpainter", object())
        monkeypatch.setattr(tasks, "_ocr_engines", {("en", "cpu"): object()})
        monkeypatch.setattr(bo_nho, "rss_mb", lambda: 9_999.0)

        da_nha = bo_nho.ep_giai_phong_neu_cang({"inpainter", "ocr"}, 2200)

        assert da_nha == ["detector"], "nhả nhầm thứ đang cần dùng"
        assert tasks._detector is None
        assert tasks._inpainter is not None, "đã nhả model của chính bước đang chạy"
        assert tasks._ocr_engines, "inpaint còn cần OCR để kiểm chứng xoá chữ"

    def test_nha_khong_no_khi_chua_nap_model_nao(self, monkeypatch):
        from app.workers import tasks
        monkeypatch.setattr(tasks, "_detector", None)
        monkeypatch.setattr(tasks, "_inpainter", None)
        monkeypatch.setattr(tasks, "_ocr_engines", {})
        assert bo_nho.giai_phong_model({"detector"}) == []


class TestTronTheoDai:
    """Khẳng định quan trọng nhất: tối ưu bộ nhớ KHÔNG được đổi lấy một pixel nào."""

    @pytest.mark.parametrize("h,w", [(1660, 1200), (300, 200), (_DAI_TRON, 64), (_DAI_TRON + 1, 64)])
    def test_ket_qua_giong_het_cach_lam_mot_biểu_thuc(self, h, w):
        rng = np.random.default_rng(11)
        rgb = rng.random((h, w, 3), dtype=np.float32)
        pred = rng.random((h, w, 3), dtype=np.float32)
        mask = (rng.random((h, w)) > 0.7).astype(np.float32)

        m3 = mask[:, :, None]
        mong_doi = ((rgb * (1.0 - m3) + pred * m3) * 255.0).round().astype(np.uint8)

        thuc_te = np.empty((h, w, 3), dtype=np.uint8)
        for y0 in range(0, h, _DAI_TRON):
            y1 = min(y0 + _DAI_TRON, h)
            m = mask[y0:y1, :, None]
            dai = rgb[y0:y1] * (1.0 - m)
            dai += pred[y0:y1] * m
            np.multiply(dai, 255.0, out=dai)
            np.round(dai, out=dai)
            thuc_te[y0:y1] = dai.astype(np.uint8)

        assert np.array_equal(thuc_te, mong_doi), "trộn theo dải làm đổi pixel"

    def test_ngoai_mask_giu_nguyen_anh_goc(self):
        """Bất biến của M4: pixel ngoài mask không được đụng tới."""
        h = w = 64
        rgb = np.full((h, w, 3), 0.25, dtype=np.float32)
        pred = np.full((h, w, 3), 0.99, dtype=np.float32)
        mask = np.zeros((h, w), dtype=np.float32)
        mask[:10, :10] = 1.0
        m3 = mask[:, :, None]
        ket = ((rgb * (1.0 - m3) + pred * m3) * 255.0).round().astype(np.uint8)
        assert (ket[20:, 20:] == round(0.25 * 255)).all()
        assert (ket[:10, :10] == round(0.99 * 255)).all()
