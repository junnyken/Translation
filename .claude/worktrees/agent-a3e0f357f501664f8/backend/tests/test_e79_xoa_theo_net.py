"""E79 — xoá chữ theo NÉT CHỮ (mặt nạ `seg` của CTD) thay vì cả khung chữ nhật.

Canh:
1. Đổi `seg` letterbox về ảnh gốc đúng vị trí.
2. Chỉ xoá nét chữ TRONG khung; tranh quanh chữ trong khung giữ nguyên; ngoài khung không bao giờ đụng.
3. Khung mà `seg` không thấy chữ ⇒ lùi về xoá cả khung (thà rộng còn hơn sót chữ).
4. Worker: nhận diện có mặt nạ ⇒ lưu; engine không có mặt nạ ⇒ XOÁ mặt nạ cũ; xoá chữ dùng mặt nạ.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from app.services.inpaint.lama import LamaInpainter
from app.services.inpaint.mat_na_net import seg_ve_anh_goc, tinh_mat_na_xoa
from app.services.interfaces import BBox


def test_seg_letterbox_ve_dung_vi_tri_anh_goc():
    rong, cao, S = 400, 200, 128
    scale = min(S / rong, S / cao)
    nw, nh = round(rong * scale), round(cao * scale)
    px, py = (S - nw) // 2, (S - nh) // 2
    seg = np.zeros((S, S), np.float32)
    # một "chữ" ở góc trên-trái 1/4 ảnh gốc: x 0–100, y 0–50
    seg[py:py + round(50 * scale), px:px + round(100 * scale)] = 1.0
    m = seg_ve_anh_goc(seg, scale, px, py, rong, cao)
    assert m.shape == (cao, rong)
    assert m[10:40, 10:90].all() and not m[120:, 200:].any()


def _khung(x1, y1, x2, y2):
    m = np.zeros((300, 400), np.float32)
    m[y1:y2, x1:x2] = 1
    return m


def test_chi_xoa_net_chu_trong_khung():
    mk = _khung(100, 100, 300, 200)
    chu = np.zeros((300, 400), np.uint8)
    chu[140:160, 150:250] = 255          # nét chữ giữa khung
    chu[10:30, 10:30] = 255               # "chữ" NGOÀI mọi khung — không được xoá
    ra, lui = tinh_mat_na_xoa(mk, chu, [(100, 100, 300, 200)])
    assert lui == 0
    assert ra[150, 200] == 1, "nét chữ phải bị xoá"
    assert ra[105, 105] == 0, "tranh trong khung nhưng xa nét chữ phải được giữ"
    assert ra[20, 20] == 0, "ngoài khung không bao giờ bị xoá"
    assert ra[100:200, 100:300].mean() < 0.6


def test_khung_seg_khong_thay_chu_thi_xoa_ca_khung():
    mk = _khung(100, 100, 300, 200)
    ra, lui = tinh_mat_na_xoa(mk, np.zeros((300, 400), np.uint8), [(100, 100, 300, 200)])
    assert lui == 1 and ra[100:200, 100:300].all()


def test_lama_chi_thay_diem_anh_tren_net_chu(tmp_path):
    rng = np.random.default_rng(5)
    anh = rng.integers(0, 256, (300, 400, 3), dtype=np.uint8)  # nền tranh (không tô phẳng được)
    src = tmp_path / "t.png"
    Image.fromarray(anh).save(src)
    chu = np.zeros((300, 400), np.uint8)
    chu[140:160, 150:250] = 255
    may = LamaInpainter(weights_path="/khong/co.onnx", dilate_ratio=0.0)
    may._chay_model = lambda rgb, m: np.full_like(rgb, 128 / 255.0)
    out = np.asarray(Image.open(may.inpaint(str(src), [BBox(100, 100, 200, 100)], mat_na_chu=chu)))
    assert (out[150, 200] == 128).all()
    assert np.array_equal(out[105, 105], anh[105, 105]), "tranh quanh chữ bị xoá oan"


def test_mat_na_khac_co_anh_thi_lui_ve_khung(tmp_path):
    src = tmp_path / "t.png"
    Image.fromarray(np.random.default_rng(1).integers(0, 256, (300, 400, 3), dtype=np.uint8)).save(src)
    may = LamaInpainter(weights_path="/khong/co.onnx", dilate_ratio=0.0)
    may._chay_model = lambda rgb, m: np.full_like(rgb, 128 / 255.0)
    out = np.asarray(Image.open(may.inpaint(str(src), [BBox(100, 100, 200, 100)],
                                            mat_na_chu=np.zeros((10, 10), np.uint8))))
    assert (out[105, 105] == 128).all(), "mặt nạ sai cỡ ⇒ xoá cả khung như trước"


# ---------- worker ----------

def test_luu_va_xoa_mat_na_chu(storage_root):
    from pathlib import Path

    from app.workers.tasks import _doc_mat_na_chu, _luu_mat_na_chu, mat_na_chu_rel

    rel = "projects/p/pages/x.jpg"
    m = np.zeros((20, 30), np.uint8)
    m[5:10, 5:20] = 255
    _luu_mat_na_chu(rel, m)
    assert (Path(storage_root) / mat_na_chu_rel(rel)).is_file()
    assert np.array_equal(_doc_mat_na_chu(rel), m)
    _luu_mat_na_chu(rel, None)  # nhận diện lại bằng engine không có mặt nạ
    assert _doc_mat_na_chu(rel) is None, "mặt nạ cũ phải bị xoá"


def test_tat_co_thi_khong_dung_mat_na(storage_root, monkeypatch):
    from app.workers import tasks

    rel = "projects/p/pages/y.jpg"
    tasks._luu_mat_na_chu(rel, np.full((5, 5), 255, np.uint8))
    monkeypatch.setattr(tasks.settings, "inpaint_theo_net_chu", False)
    assert tasks._doc_mat_na_chu(rel) is None
