"""Chọn ô đặt chữ nằm gọn trong vùng an toàn, rồi giao lại cho M6 canh chữ (E14 · B3).

M6 vẫn là nơi DUY NHẤT biết ngắt dòng và đo font. E14 chỉ đổi **vùng được phép chiếm**: thay vì
bbox chữ nhật của bộ nhận diện, đưa cho M6 một hình chữ nhật nội tiếp bên trong lòng bong bóng.

Vì sao là hình chữ nhật chứ không phải đa giác: M6 ngắt dòng theo bề rộng, mà bề rộng khả dụng
trong một đa giác thay đổi theo từng dòng. Dựng bộ ngắt dòng thứ hai cho đa giác là mở ra một
đường vẽ thứ hai — đúng thứ spec cấm. Hình chữ nhật nội tiếp giữ được một đường duy nhất.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.interfaces import BBox


@dataclass(frozen=True)
class OChuNhat:
    x: float
    y: float
    w: float
    h: float

    def to_bbox(self) -> BBox:
        return BBox(x=self.x, y=self.y, w=self.w, h=self.h)


def _no_theo_thu_tu(mask, cx: int, cy: int, thu_tu: tuple[str, ...], buoc: int = 2):
    """Nới ô quanh (cx, cy) theo ĐÚNG thứ tự phía đã cho, chừng nào cả ô còn nằm trong mặt nạ."""
    h, w = mask.shape[:2]
    x0 = x1 = cx
    y0 = y1 = cy
    con_nhich = True
    while con_nhich:
        con_nhich = False
        for phia in thu_tu:
            nx0, nx1, ny0, ny1 = x0, x1, y0, y1
            if phia == "trai":
                nx0 = max(x0 - buoc, 0)
            elif phia == "phai":
                nx1 = min(x1 + buoc, w - 1)
            elif phia == "tren":
                ny0 = max(y0 - buoc, 0)
            else:
                ny1 = min(y1 + buoc, h - 1)
            if (nx0, nx1, ny0, ny1) == (x0, x1, y0, y1):
                continue
            if mask[ny0:ny1 + 1, nx0:nx1 + 1].all():
                x0, x1, y0, y1 = nx0, nx1, ny0, ny1
                con_nhich = True
    return x0, y0, x1 - x0 + 1, y1 - y0 + 1


#: Ba cách nới cố định. Nới luân phiên cho ra ô gần VUÔNG, mà chữ thì cần ô RỘNG — nên thử cả
#: "ngang trước" rồi lấy ô lớn nhất. Danh sách cố định nên kết quả vẫn tất định.
_CACH_NO = (
    ("trai", "phai", "tren", "duoi"),
    ("trai", "phai", "trai", "phai", "tren", "duoi"),
    ("tren", "duoi", "trai", "phai"),
)


def _mo_rong_o(mask, cx: int, cy: int, buoc: int = 2) -> tuple[int, int, int, int]:
    """Ô lớn nhất trong ba cách nới. Hoà nhau thì lấy cách đứng trước — không có ngẫu nhiên."""
    tot = None
    for thu_tu in _CACH_NO:
        o = _no_theo_thu_tu(mask, cx, cy, thu_tu, buoc)
        if tot is None or o[2] * o[3] > tot[2] * tot[3]:
            tot = o
    return tot


def o_noi_tiep_trong_da_giac(polygon: list[list[float]]) -> OChuNhat | None:
    """Hình chữ nhật nằm gọn trong đa giác, quanh điểm xa biên nhất.

    `distanceTransform` đo khoảng cách tới điểm ảnh **bằng 0** gần nhất — đã đo tận tay chứ không
    đoán: ô vuông 11×11 giá trị 255 cho tâm 6.0, sát mép 1.0, ngoài ô 0.0 (`TEST_LOG` §E14.1).
    Nên mặt nạ phải để vùng cần đo mang giá trị khác 0.
    """
    import cv2
    import numpy as np

    if not polygon or len(polygon) < 3:
        return None
    pts = np.array(polygon, dtype=np.float64)
    x0, y0 = pts[:, 0].min(), pts[:, 1].min()
    x1, y1 = pts[:, 0].max(), pts[:, 1].max()
    w = int(round(x1 - x0)) + 1
    h = int(round(y1 - y0)) + 1
    if w < 2 or h < 2:
        return None

    mask = np.zeros((h, w), np.uint8)
    cv2.fillPoly(mask, [np.round(pts - [x0, y0]).astype(np.int32)], 255)
    if not mask.any():
        return None

    dt = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    _, _, _, diem = cv2.minMaxLoc(dt)
    ox, oy, ow, oh = _mo_rong_o(mask > 0, int(diem[0]), int(diem[1]))
    if ow < 2 or oh < 2:
        return None
    return OChuNhat(x=float(ox + x0), y=float(oy + y0), w=float(ow), h=float(oh))


def o_dat_chu(geometry: dict) -> OChuNhat | None:
    """Ô đặt chữ cuối cùng cho một vùng an toàn — dùng chung cho cả xem thử lẫn xuất file."""
    if "polygon" in geometry:
        return o_noi_tiep_trong_da_giac(geometry["polygon"])
    r = geometry.get("rect")
    if not r:
        return None
    return OChuNhat(x=float(r["x"]), y=float(r["y"]), w=float(r["w"]), h=float(r["h"]))


def chu_nam_gon_trong(
    polygon: list[list[float]] | None,
    o_chu: tuple[float, float, float, float],
) -> bool:
    """Toàn bộ ô chữ có nằm trong đa giác không — kiểm CẢ Ô, không phải mỗi điểm neo.

    Điểm neo nằm trong mà cả khối chữ vẫn thò ra ngoài là đúng kiểu lỗi M6 từng mắc (chỉ kẹp
    điểm bắt đầu), nên chỗ này cố ý kiểm theo điểm ảnh.
    """
    if not polygon:
        return True
    import cv2
    import numpy as np

    x, y, w, h = o_chu
    pts = np.array(polygon, dtype=np.float64)
    ox0, oy0 = pts[:, 0].min(), pts[:, 1].min()
    mw = int(round(pts[:, 0].max() - ox0)) + 1
    mh = int(round(pts[:, 1].max() - oy0)) + 1
    mask = np.zeros((mh, mw), np.uint8)
    cv2.fillPoly(mask, [np.round(pts - [ox0, oy0]).astype(np.int32)], 255)

    x0 = int(np.floor(x - ox0)); y0 = int(np.floor(y - oy0))
    x1 = int(np.ceil(x + w - ox0)); y1 = int(np.ceil(y + h - oy0))
    if x0 < 0 or y0 < 0 or x1 > mw or y1 > mh:
        return False
    return bool((mask[y0:y1, x0:x1] > 0).all())
