"""P3h — đo và ghìm bộ nhớ worker.

Sinh ra sau một sự cố THẬT: pilot 6 trang trên host làm worker bị OOM killer giết (`exit 137`),
API tụt từ 3,4 ms xuống 10–42 s rồi tắt tiếng. Không ai thấy nó tới lúc chết vì hệ thống không
có một chỉ số bộ nhớ nào.
"""
from __future__ import annotations

import tracemalloc

import numpy as np
import pytest
from app.services.inpaint.lama import _DAI_TRON, _tron_theo_dai
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
    """Gọi ĐÚNG hàm mà đường chạy thật dùng (`_tron_theo_dai`).

    Bản đầu của bộ test này **chép lại vòng lặp vào trong test** rồi so với công thức cũ — nó
    chứng minh *thuật toán* tương đương chứ không chứng minh *mã đang chạy* làm đúng thuật toán
    đó: sửa bản sao mà quên sửa bản thật thì test vẫn xanh. Nay `lama.py` tách hàm ra và cả hai
    bên gọi chung một chỗ.
    """

    @staticmethod
    def _mot_bieu_thuc(rgb, pred, mask):
        """Mốc đối chiếu — chép ĐÚNG mã cũ trước P3h (`lama.py` ở commit `ac5460c`).

        Kể cả việc **gán tên cho mảng trung gian**: chỉ vì có biến `blended` giữ tham chiếu mà
        mảng đó còn sống trong lúc numpy dựng mảng tiếp theo — đo được đỉnh 100,8 MB thay vì
        67,2 MB nếu viết liền một biểu thức (1400x2000). Chép mốc đối chiếu "cho gần đúng" là
        cách âm thầm làm phép so sánh dễ hơn thực tế.
        """
        m3 = mask[:, :, None]
        blended = rgb * (1.0 - m3) + pred * m3
        return (blended * 255.0).round().astype(np.uint8)

    @staticmethod
    def _du_lieu(h, w, seed=11):
        rng = np.random.default_rng(seed)
        rgb = rng.random((h, w, 3), dtype=np.float32)
        pred = rng.random((h, w, 3), dtype=np.float32)
        mask = (rng.random((h, w)) > 0.7).astype(np.float32)
        return rgb, pred, mask

    @staticmethod
    def _dinh_mb(fn, *args):
        """Đỉnh cấp phát của riêng `fn` (đầu vào đã cấp phát trước khi bật đo)."""
        tracemalloc.start()
        tracemalloc.reset_peak()
        ket = fn(*args)
        _, dinh = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return ket, dinh / 1e6

    @pytest.mark.parametrize("h,w", [(1660, 1200), (300, 200), (_DAI_TRON, 64), (_DAI_TRON + 1, 64)])
    def test_ket_qua_giong_het_cach_lam_mot_bieu_thuc(self, h, w):
        """Khẳng định quan trọng nhất: tối ưu bộ nhớ KHÔNG được đổi lấy một pixel nào."""
        rgb, pred, mask = self._du_lieu(h, w)
        mong_doi = self._mot_bieu_thuc(rgb, pred, mask)

        thuc_te = _tron_theo_dai(rgb, pred, mask)

        assert thuc_te.shape == (h, w, 3) and thuc_te.dtype == np.uint8
        assert np.array_equal(thuc_te, mong_doi), "trộn theo dải làm đổi pixel"

    def test_ngoai_mask_giu_nguyen_anh_goc(self):
        """Bất biến của M4: pixel ngoài mask không được đụng tới — đo trên chính hàm sản xuất."""
        h = w = 64
        rgb = np.full((h, w, 3), 0.25, dtype=np.float32)
        pred = np.full((h, w, 3), 0.99, dtype=np.float32)
        mask = np.zeros((h, w), dtype=np.float32)
        mask[:10, :10] = 1.0

        ket = _tron_theo_dai(rgb, pred, mask)

        assert (ket[20:, 20:] == round(0.25 * 255)).all(), "pixel ngoài mask bị đổi"
        assert (ket[:10, :10] == round(0.99 * 255)).all(), "pixel trong mask không được thay"

    def test_re_hon_han_cach_viet_mot_bieu_thuc(self):
        """Không có phép đo này thì 'tiết kiệm bộ nhớ' chỉ là một khẳng định trong docstring."""
        rgb, pred, mask = self._du_lieu(2000, 1400)

        _, dinh_cu = self._dinh_mb(self._mot_bieu_thuc, rgb, pred, mask)
        if dinh_cu < 10.0:
            pytest.skip(f"tracemalloc không theo dõi cấp phát của numpy ở môi trường này ({dinh_cu:.1f} MB)")
        _, dinh_moi = self._dinh_mb(_tron_theo_dai, rgb, pred, mask)

        assert dinh_moi < dinh_cu * 0.4, f"đỉnh {dinh_moi:.1f} MB không rẻ hơn hẳn {dinh_cu:.1f} MB"

    def test_dinh_bo_nho_KHONG_leo_theo_chieu_cao_trang(self):
        """Điểm đáng giá không phải 'nhỏ hơn' mà là 'không phụ thuộc cỡ trang'.

        Gấp đôi chiều cao: cách cũ tốn gấp đôi; cách mới chỉ tăng đúng phần ảnh KẾT QUẢ
        (`h*w*3` byte uint8), còn vùng đệm trung gian đứng yên theo `_DAI_TRON`.
        """
        rgb1, pred1, mask1 = self._du_lieu(800, 1400)
        rgb2, pred2, mask2 = self._du_lieu(1600, 1400)

        _, dinh_cu_thap = self._dinh_mb(self._mot_bieu_thuc, rgb1, pred1, mask1)
        if dinh_cu_thap < 10.0:
            pytest.skip(f"tracemalloc không theo dõi cấp phát của numpy ở môi trường này ({dinh_cu_thap:.1f} MB)")
        _, dinh_cu_cao = self._dinh_mb(self._mot_bieu_thuc, rgb2, pred2, mask2)
        _, dinh_moi_thap = self._dinh_mb(_tron_theo_dai, rgb1, pred1, mask1)
        _, dinh_moi_cao = self._dinh_mb(_tron_theo_dai, rgb2, pred2, mask2)

        # Đối chứng: cách cũ PHẢI leo gần gấp đôi — nếu không thì phép đo này không đo cái nó tưởng.
        assert dinh_cu_cao > dinh_cu_thap * 1.8, (
            f"mốc đối chiếu không leo như dự kiến ({dinh_cu_thap:.1f} -> {dinh_cu_cao:.1f} MB) "
            "— phép đo đang không đo cái nó tưởng nó đang đo"
        )
        assert dinh_moi_cao < dinh_moi_thap * 1.5, (
            f"đỉnh vẫn leo theo chiều cao trang ({dinh_moi_thap:.1f} -> {dinh_moi_cao:.1f} MB)"
        )
