"""E79 — xoá chữ theo NÉT CHỮ thay vì cả khung chữ nhật.

`comic-text-detector` vốn trả hai thứ: khung (`blk`) và mặt nạ điểm ảnh của chữ (`seg`, 1024×1024).
Trước E79 Translation chỉ dùng khung, nên LaMa xoá cả hình chữ nhật nới 8% — ăn vào nét vẽ quanh chữ,
nặng nhất ở chữ tiếng động vẽ đè lên tranh. Koharu xoá theo mặt nạ chữ, nở + bịt lỗ theo cỡ trang
(`koharu-pipeline/src/stages/detection.rs`, bán kính round(max(W,H)/1024·6); MIT OR Apache-2.0).

Đo 15-10-2026 trên 3 trang thật: diện tích bị xoá giảm 25–32%, phần giữ lại toàn là tranh quanh chữ.

An toàn: chỉ xoá TRONG khung đã nới (vùng E12 bỏ qua vẫn không bị đụng). Khung nào mặt nạ gần như
trống (bộ nhận diện vẽ khung mà `seg` không thấy chữ) ⇒ xoá CẢ khung như trước — thà xoá rộng còn hơn
để sót chữ.
"""
from __future__ import annotations

import numpy as np

#: Ngưỡng xác suất của `seg` (giá trị 0–1).
NGUONG_SEG = 0.5
#: Khung có phần mặt nạ chữ nhỏ hơn tỉ lệ này ⇒ coi như `seg` bỏ sót, xoá cả khung.
TI_LE_TOI_THIEU_TRONG_KHUNG = 0.03


def seg_ve_anh_goc(seg: np.ndarray, scale: float, pad_x: int, pad_y: int,
                   rong: int, cao: int) -> np.ndarray:
    """`seg` letterbox (S×S, 0–1) ⇒ mặt nạ uint8 0/255 đúng cỡ ảnh gốc (bỏ phần đệm rồi phóng)."""
    import cv2

    nw, nh = round(rong * scale), round(cao * scale)
    cat = seg[pad_y:pad_y + nh, pad_x:pad_x + nw].astype(np.float32)
    ve = cv2.resize(cat, (rong, cao), interpolation=cv2.INTER_LINEAR)
    return ((ve > NGUONG_SEG).astype(np.uint8)) * 255


#: Nhân bán kính nở của Koharu. Đo 15-10-2026 bằng LaMa thật trên chữ tiếng động TRẮNG VIỀN ĐEN DÀY
#: đè lên tranh (`E13P02`, "shwwwwiiiing!"): ×1 (đúng Koharu) để SÓT mảnh viền đen của chữ — tệ hơn
#: xoá cả khung; ×2 gần như sạch, diện tích xoá 82% so với cả khung; ×3 sạch nhưng nhoè, 91% — gần
#: như xoá cả khung, mất ý nghĩa. `seg` phủ ruột chữ, không phủ hết viền dày.
HE_SO_NO_MAC_DINH = 2.0


def no_va_bit(mat_na: np.ndarray, he_so: float = HE_SO_NO_MAC_DINH) -> np.ndarray:
    """Nở + bịt lỗ theo cỡ trang (Koharu × `he_so`): phủ đủ quầng/viền chữ, nối nét rời."""
    import cv2

    cao, rong = mat_na.shape[:2]
    r = max(1, min(255, round(max(rong, cao) / 1024 * 6 * he_so)))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    return cv2.morphologyEx(cv2.dilate(mat_na, k), cv2.MORPH_CLOSE, k)


def tinh_mat_na_xoa(mat_na_khung: np.ndarray, mat_na_chu: np.ndarray,
                    khung: list[tuple[int, int, int, int]],
                    he_so_no: float = HE_SO_NO_MAC_DINH) -> tuple[np.ndarray, int]:
    """Mặt nạ xoá cuối cùng (float32 0/1) và số khung phải lùi về xoá cả khung.

    `mat_na_khung`: HW float (1 = trong khung đã nới). `mat_na_chu`: HW uint8 0/255 chưa nở.
    `khung`: các ô nguyên (x1, y1, x2, y2) của từng khung đã nới.
    """
    net = no_va_bit(mat_na_chu, he_so_no) > 0
    ra = np.zeros(mat_na_khung.shape, dtype=np.float32)
    lui = 0
    for x1, y1, x2, y2 in khung:
        if x2 <= x1 or y2 <= y1:
            continue
        o = net[y1:y2, x1:x2]
        if o.mean() < TI_LE_TOI_THIEU_TRONG_KHUNG:
            ra[y1:y2, x1:x2] = np.maximum(ra[y1:y2, x1:x2], mat_na_khung[y1:y2, x1:x2])
            lui += 1
        else:
            ra[y1:y2, x1:x2] = np.maximum(ra[y1:y2, x1:x2], o.astype(np.float32))
    return ra * (mat_na_khung > 0), lui
