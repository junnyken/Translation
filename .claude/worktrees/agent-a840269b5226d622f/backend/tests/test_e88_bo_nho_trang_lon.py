"""E88 — trang lớn xoá chữ theo cụm KHÔNG được dựng ảnh số thực cỡ nguyên trang.

Production 16-10-2026: trang 3112x4402 (13,7 triệu điểm) ⇒ worker bị giết (137) hai lần khi chạy
LaMa. Riêng hai bản float32 cả trang (`rgb`, `pred_hwc`) đã ~330 MB. Đo tracemalloc (model giả):
cách cũ đỉnh 447 MB, cách mới 110 MB, ảnh ra giống từng byte.
"""
from __future__ import annotations

import tracemalloc

import numpy as np
from PIL import Image

from app.services.inpaint.lama import LamaInpainter
from app.services.interfaces import BBox


def test_dinh_bo_nho_khong_leo_theo_anh_so_thuc_ca_trang(tmp_path):
    cao, rong = 3000, 2000
    src = tmp_path / "t.png"
    Image.fromarray(np.random.default_rng(0).integers(0, 256, (cao, rong, 3), dtype=np.uint8)).save(src)
    may = LamaInpainter(weights_path="/khong/co.onnx", whole_page_max_mpx=0.25, max_crop_mpx=1.6,
                        flat_fill=False, xoa_net_tren_tranh=False)
    may._chay_model = lambda rgb, m: np.full_like(rgb, 0.5)
    khung = [BBox(100 + 700 * (i % 3), 200 + 900 * (i // 3), 400, 250) for i in range(9)]
    tracemalloc.start()
    try:
        out = may.inpaint(str(src), khung)
        dinh = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    mot_ban_float = cao * rong * 3 * 4
    assert dinh < 1.5 * mot_ban_float, f"đỉnh {dinh / 1e6:.0f} MB — đang giữ ảnh số thực cả trang"
    ra = np.asarray(Image.open(out))
    assert (ra[250, 200] == 128).all(), "vùng trong khung phải được vẽ lại"
    goc = np.asarray(Image.open(src))
    assert np.array_equal(ra[0:50, 0:50], goc[0:50, 0:50]), "ngoài khung phải giữ nguyên"
