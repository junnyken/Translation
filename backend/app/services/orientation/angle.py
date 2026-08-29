"""Chuẩn hoá góc của `cv2.minAreaRect` (E15).

Đây là chỗ **phải đo chứ không được đoán**, và đã đo trên hình biết trước đáp án
(`docs/TEST_LOG.md § E15.1`):

| Hình vẽ ở góc | `minAreaRect` trả về |
|---|---|
| 0° | w=40, h=200, **angle = 90.0** |
| 90° | w=200, h=40, **angle = 90.0** |

Hai hình **vuông góc với nhau** cho ra **cùng một góc thô**. Chỉ khác ở chỗ `w`/`h` hoán vị.
Nên lấy góc thô làm "sự thật về hướng" là sai ngay từ ca cơ bản nhất.
"""
from __future__ import annotations


def chuan_hoa_goc(w: float, h: float, angle: float) -> float:
    """Hướng của **cạnh dài** hình chữ nhật, quy về [0, 180).

    0 = nằm ngang, 90 = dựng đứng. Dùng `w`/`h` để gỡ chỗ mập mờ của góc thô.
    """
    goc = float(angle) if w >= h else float(angle) + 90.0
    return goc % 180.0


def la_ngang(goc: float, dung_sai: float) -> bool:
    """Gần 0 hoặc gần 180 đều là nằm ngang — 179° không phải là 'gần như dựng đứng'."""
    g = goc % 180.0
    return min(g, 180.0 - g) <= dung_sai


def la_doc(goc: float, dung_sai: float) -> bool:
    return abs((goc % 180.0) - 90.0) <= dung_sai
