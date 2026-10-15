"""E82 — tìm KHUNG TRANH (panel) bằng cắt XY theo rãnh trắng, để sắp thứ tự đọc theo khung.

## Vì sao

`order_items` chia cả trang thành dải ngang rồi đọc trái/phải trong dải. Bố cục manga rất hay gặp —
một khung cao bên phải trải qua nhiều hàng, bên trái hai khung nhỏ chồng nhau — làm bong bóng của
các khung khác nhau đan xen theo độ cao. Koharu sắp theo khung tranh → bong bóng → chữ
(`koharu-pipeline/src/stages/detection.rs`, `detection_order`; MIT OR Apache-2.0), nhờ model
nhận diện có lớp "panel". Translation chưa có model đó (RF-DETR — bị chặn vì đĩa máy chủ đầy), nên
tự tìm khung bằng cắt XY: rãnh trắng chạy SUỐT chiều ngang ⇒ ranh giới hàng; trong hàng, rãnh trắng
chạy suốt chiều dọc ⇒ ranh giới cột; đệ quy.

## Giới hạn có chủ đích

Khung nghiêng, khung không có rãnh trắng (tranh tràn lề), nền trang tối ⇒ không cắt được ⇒ trả MỘT
khung là cả trang ⇒ thứ tự đọc y như trước E82. Không bao giờ tệ hơn cách cũ ở những trang đó.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

#: Điểm sáng hơn mức này là "trắng" (giấy / rãnh).
NGUONG_TRANG = 225
#: Một hàng/cột được coi là rãnh khi tỉ lệ điểm trắng trên nó đạt mức này (chịu được chút bụi in).
TI_LE_RANH = 0.985
#: Độ dày rãnh tối thiểu (tỉ lệ cạnh ngắn của trang) — nét mảnh trắng trong tranh không phải rãnh.
TI_LE_KHE = 0.006
#: Khung nhỏ hơn tỉ lệ này của cạnh trang theo chiều bị cắt ⇒ coi là nhiễu, bỏ.
TI_LE_KHUNG_NHO = 0.04
DO_SAU_TOI_DA = 5


@dataclass
class Nut:
    x0: int
    y0: int
    x1: int
    y1: int
    #: "hang" = con xếp TRÊN → DƯỚI; "cot" = con xếp TRÁI ↔ PHẢI; None = lá (một khung tranh).
    kieu: str | None = None
    con: list["Nut"] = field(default_factory=list)


def _doan_khong_trang(la_ranh: np.ndarray, khe_min: int) -> list[tuple[int, int]]:
    """Các đoạn KHÔNG phải rãnh, ngăn bởi rãnh dày ≥ `khe_min`. Rãnh mỏng hơn ⇒ coi như liền."""
    n = len(la_ranh)
    doan, bat_dau, i = [], None, 0
    while i < n:
        if la_ranh[i]:
            j = i
            while j < n and la_ranh[j]:
                j += 1
            if j - i >= khe_min:
                if bat_dau is not None:
                    doan.append((bat_dau, i))
                    bat_dau = None
            elif bat_dau is None and i > 0:
                bat_dau = i
            i = j
        else:
            if bat_dau is None:
                bat_dau = i
            i += 1
    if bat_dau is not None:
        doan.append((bat_dau, n))
    return doan


def _cat(trang: np.ndarray, nut: Nut, truc: int, khe_min: int, nho: tuple[int, int],
         do_sau: int) -> None:
    o = trang[nut.y0:nut.y1, nut.x0:nut.x1]
    if o.size == 0 or do_sau > DO_SAU_TOI_DA:
        return
    for thu in (truc, 1 - truc):  # thử hướng được gợi ý trước, không được thì hướng kia
        la_ranh = o.mean(axis=1 - thu) >= TI_LE_RANH  # thu=0: theo hàng (cắt ngang); 1: theo cột
        doan = [(a, b) for a, b in _doan_khong_trang(la_ranh, khe_min) if b - a >= nho[thu]]
        if len(doan) >= 2:
            nut.kieu = "hang" if thu == 0 else "cot"
            for a, b in doan:
                con = (Nut(nut.x0, nut.y0 + a, nut.x1, nut.y0 + b) if thu == 0
                       else Nut(nut.x0 + a, nut.y0, nut.x0 + b, nut.y1))
                nut.con.append(con)
                _cat(trang, con, 1 - thu, khe_min, nho, do_sau + 1)
            return


def tim_khung_tranh(xam: np.ndarray) -> Nut:
    """Cây khung tranh của trang. `xam`: HW uint8. Không cắt được ⇒ gốc là một lá (cả trang)."""
    cao, rong = xam.shape[:2]
    trang = xam >= NGUONG_TRANG
    khe_min = max(3, round(min(cao, rong) * TI_LE_KHE))
    goc = Nut(0, 0, rong, cao)
    _cat(trang, goc, 0, khe_min, (round(cao * TI_LE_KHUNG_NHO), round(rong * TI_LE_KHUNG_NHO)), 0)
    return goc


def la_theo_thu_tu(nut: Nut, rtl: bool) -> list[Nut]:
    """Các khung lá theo thứ tự đọc: hàng trên → dưới; cột phải → trái (rtl) hoặc trái → phải."""
    if not nut.con:
        return [nut]
    con = list(nut.con)
    if nut.kieu == "cot" and rtl:
        con.reverse()
    ra: list[Nut] = []
    for c in con:
        ra.extend(la_theo_thu_tu(c, rtl))
    return ra


def chi_so_khung(khung: list[Nut], cx: float, cy: float) -> int:
    """Khung lá chứa điểm; không khung nào chứa (bong bóng tràn qua rãnh) ⇒ khung gần nhất."""
    tot, kc_tot = 0, float("inf")
    for i, k in enumerate(khung):
        if k.x0 <= cx < k.x1 and k.y0 <= cy < k.y1:
            return i
        dx = max(k.x0 - cx, 0, cx - k.x1)
        dy = max(k.y0 - cy, 0, cy - k.y1)
        if dx * dx + dy * dy < kc_tot:
            tot, kc_tot = i, dx * dx + dy * dy
    return tot
