"""E87 — chữ hiệu ứng vẽ TRÊN TRANH: xoá cẩn thận (chỉ nét có viền) + viền chữ dịch đáng tin.

Đo thật ja_E12P01 (production 16-10-2026, khung Gemini): カラン/コロン trên đống chai lọ ⇒ xoá cả
khung làm mất chai lọ; đo viền lấy nhầm màu chai (nâu, 17px) ⇒ chữ dịch thành một khối nâu.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from app.services.inpaint.lama import LamaInpainter
from app.services.inpaint.mat_na_net import mat_na_net_tren_tranh
from app.services.interfaces import BBox
from app.services.typeset.mau_chu import MauChu, _vien_tin_duoc


def _tranh_co_chu_vien_trang(rng):
    anh = rng.integers(40, 200, (300, 400, 3), dtype=np.uint8)  # "tranh" nhiều màu, không phẳng
    anh[120:180, 100:300] = (60, 110, 140)                        # ruột chữ (xanh đậm)
    anh[116:120, 96:304] = 255                                     # viền trắng trên/dưới
    anh[180:184, 96:304] = 255
    return anh


def test_mat_na_bam_net_vien_khong_ca_khung():
    anh = _tranh_co_chu_vien_trang(np.random.default_rng(0))
    m = mat_na_net_tren_tranh(anh, (60, 80, 340, 220))
    assert m is not None
    assert m[40:42, 60:200].all(), "viền trắng phải nằm trong mặt nạ"
    assert not m[0:10, 0:20].any(), "góc tranh xa chữ không được xoá"
    assert m.mean() < 0.7


def test_khong_co_vien_thi_xoa_ca_khung():
    anh = np.random.default_rng(1).integers(70, 180, (300, 400, 3), dtype=np.uint8)
    assert mat_na_net_tren_tranh(anh, (60, 80, 340, 220)) is None


def test_lama_chi_ve_lai_vung_net_tren_tranh(tmp_path):
    rng = np.random.default_rng(2)
    anh = _tranh_co_chu_vien_trang(rng)
    src = tmp_path / "t.png"
    Image.fromarray(anh).save(src)
    may = LamaInpainter(weights_path="/khong/co.onnx", dilate_ratio=0.0)
    may._chay_model = lambda rgb, m: np.full_like(rgb, 0.5)
    out = np.asarray(Image.open(may.inpaint(str(src), [BBox(60, 80, 280, 140)])))
    assert (out[117, 150] == 128).all(), "nét viền phải được vẽ lại"
    assert np.array_equal(out[85, 65], anh[85, 65]), "tranh trong khung, xa chữ, bị xoá oan"


def test_tat_co_thi_xoa_ca_khung(tmp_path):
    anh = _tranh_co_chu_vien_trang(np.random.default_rng(3))
    src = tmp_path / "t.png"
    Image.fromarray(anh).save(src)
    may = LamaInpainter(weights_path="/khong/co.onnx", dilate_ratio=0.0, xoa_net_tren_tranh=False)
    may._chay_model = lambda rgb, m: np.full_like(rgb, 0.5)
    out = np.asarray(Image.open(may.inpaint(str(src), [BBox(60, 80, 280, 140)])))
    assert (out[85, 65] == 128).all()


def test_vien_day_bat_thuong_thay_bang_vien_tuong_phan_mong():
    m = _vien_tin_duoc(MauChu(mau=(255, 255, 255), mau_vien=(122, 99, 74), vien=17.0), 1660)
    assert m.mau == (255, 255, 255) and m.mau_vien == (0, 0, 0) and m.vien <= 4


def test_vien_binh_thuong_giu_nguyen():
    goc = MauChu(mau=(0, 0, 0), mau_vien=(255, 255, 255), vien=4.0)
    assert _vien_tin_duoc(goc, 1660) == goc
