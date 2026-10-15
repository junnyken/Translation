"""E76 — xoá chữ theo mặt nạ NGƯỜI DÙNG TÔ (cọ trên màn canvas).

Tách khỏi `lama.py` vì cần OpenCV (tách các vệt tô thành thành phần liên thông), mà `lama.py` bị
CẤM import cv2 (`test_no_ai_logic::test_khong_lang_le_fallback_opencv_khi_lama_loi`) — chốt đó giữ
cho không ai lặng lẽ lùi về `cv2.inpaint` khi LaMa lỗi. Ở đây cv2 chỉ dùng để chia cụm, việc VẼ LẠI
vẫn là `_chay_model` của engine đang chọn.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from app.services.inpaint.lama import (
    InpaintFailed, LamaInpainter, _tron_theo_dai, gom_cum,
)
from app.services.inpaint.mask import InvalidMask
from app.services.interfaces import BBox
def xoa_theo_mat_na(inpainter: LamaInpainter, src: str, mat_na: np.ndarray, dich: str) -> int:
    """E76 — xoá chữ trong vùng NGƯỜI DÙNG TÔ (cọ trên màn canvas), ghi ảnh ra `dich`.

    Khác `inpaint()`: mặt nạ là điểm ảnh người dùng tô, không phải khung chữ. Không tô phẳng E69 (nó
    cần khung chữ nhật). Dùng lại đúng các bước của `inpaint()` — chia cụm theo thành phần liên
    thông, trần diện tích ô cắt, chỉ thay điểm ảnh trong mặt nạ — và `_chay_model` của engine đang
    chọn, nên SDXL (E74) cũng dùng được.

    `src` là ảnh SẠCH hiện tại (hoặc ảnh gốc khi chưa có). `dich` PHẢI khác `src`.
    Trả số cụm đã đưa vào model.
    """
    import cv2

    if Path(src).resolve() == Path(dich).resolve():
        raise InpaintFailed("Đích trùng nguồn — từ chối ghi đè")
    with Image.open(src) as im:
        anh = np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0
    cao, rong = anh.shape[:2]
    if mat_na.shape != (cao, rong):
        raise InvalidMask(f"Mặt nạ {mat_na.shape[::-1]} khác cỡ ảnh {rong}x{cao}")
    m = (mat_na > 0).astype(np.uint8)
    if not m.any():
        raise InvalidMask("Mặt nạ rỗng — chưa tô vùng nào")

    so, _nhan, stats, _tam = cv2.connectedComponentsWithStats(m, connectivity=8)
    khung = [BBox(x=float(x), y=float(y), w=float(w), h=float(h))
             for x, y, w, h, _s in stats[1:so]]
    cum = gom_cum(khung, rong, cao, inpainter.tile_margin)
    if cum:
        o_lon = max((x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in cum)
        inpainter._kiem_tran_o_cat(o_lon / 1e6, rong, cao, f"cụm lớn nhất trong {len(cum)} cụm")
    mf = m.astype(np.float32)
    du_doan = anh.copy()
    for x0, y0, x1, y1 in cum:
        if mf[y0:y1, x0:x1].max() <= 0:
            continue
        du_doan[y0:y1, x0:x1] = inpainter._chay_model(anh[y0:y1, x0:x1], mf[y0:y1, x0:x1])
    Path(dich).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(_tron_theo_dai(anh, du_doan, mf), mode="RGB").save(dich, format="PNG")
    return len(cum)
