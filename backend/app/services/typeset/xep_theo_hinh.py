"""E75 — xếp chữ theo HÌNH bong bóng: dòng giữa rộng, dòng trên/dưới hẹp theo đường viền.

## Vì sao

E14 đặt chữ vào hình chữ nhật NỘI TIẾP trong đa giác bong bóng. Đo trên 6 trang thật (15-10-2026):
8/38 vùng có đa giác, và ở đó hình chữ nhật chỉ dùng được **34–68%** diện tích bong bóng (trung vị
~0,5). Bong bóng bầu dục mà xếp chữ thành khối vuông thì hai đầu trên/dưới bỏ trống, chữ bị thu nhỏ.

Koharu (`koharu-renderer/src/layout.rs`, `comic_line_breaks`, MIT OR Apache-2.0) lấy bề rộng TỪNG
DÒNG từ đường viền bong bóng. Ở đây làm cùng ý đó, bản đơn giản: mỗi dòng nhận khoảng ngang của đa
giác tại đúng dải cao của nó, ngắt từ tham lam vào các khoảng đó.

## Một đường duy nhất (ràng buộc của E14)

E14 từ chối đa giác vì "dựng bộ ngắt dòng thứ hai là mở ra một đường vẽ thứ hai". Ở đây KHÔNG có
đường vẽ thứ hai: bước căn chữ tính vị trí từng dòng và LƯU (`typeset_result.dong_json`); ảnh xem
thử và file xuất chỉ ĐỌC lại. Hai bên dùng chung `do_dong()` nên chiều cao dòng không thể lệch.

## Không thụt lùi

Bên gọi chỉ dùng kết quả này khi nó cho cỡ chữ LỚN HƠN cách cũ. Không xếp được (từ dài hơn bề rộng
dòng, có xuống dòng cứng…) ⇒ trả None ⇒ giữ hình chữ nhật như trước.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

#: Chuỗi dò chiều cao dòng: có dấu chồng cao nhất của tiếng Việt và chân chữ thấp nhất.
CHUOI_DO = "ẪỸỆgjpqy"


@dataclass(frozen=True)
class KetQuaXepHinh:
    font_size: float
    wrapped_text: str
    #: (tâm x, đỉnh dải dòng y) của từng dòng — toạ độ ĐÃ nhân hệ số vẽ (cùng hệ với đa giác vào).
    dong: tuple[tuple[float, float], ...]


def do_dong(font, stroke: int, gian: int) -> tuple[int, int, int]:
    """(độ lệch đỉnh, chiều cao nét, bước dòng) — DÙNG CHUNG cho bước căn và bước vẽ.

    - Vẽ một dòng có đỉnh nét tại `y` ⇔ `draw.text((x, y - lech), …, anchor="la")`.
    - Chiều cao nét: từ dấu chồng cao nhất tới chân chữ thấp nhất — dải này phải nằm TRONG đa giác.
    - Bước dòng: ĐÚNG quy ước `multiline_text` của Pillow mà M6 đo (`getbbox("A")` đáy + 2·viền +
      khoảng dòng). Lần đo đầu dùng chiều cao nét làm bước dòng ⇒ thưa hơn M6 ⇒ cỡ chữ NHỎ HƠN cách
      cũ trên cả 3 bong bóng thử. Hai cách phải cùng một thước đo thì so mới công bằng.
    """
    _l, t, _r, b = font.getbbox(CHUOI_DO, anchor="la", stroke_width=stroke)
    buoc = int(font.getbbox("A", stroke_width=stroke)[3]) + 2 * stroke + gian
    return int(t), int(b - t), buoc


def be_rong_dong(font, dong: str, stroke: int) -> float:
    return font.getlength(dong) + 2 * stroke


def _mat_na(polygon: list[list[float]], le: float):
    """Mặt nạ đa giác (toạ độ cục bộ) đã co vào `le` px, kèm gốc (x0, y0) và điểm neo xa biên nhất."""
    import cv2

    pts = np.asarray(polygon, dtype=np.float64)
    x0, y0 = np.floor(pts.min(axis=0))
    w = int(np.ceil(pts[:, 0].max() - x0)) + 1
    h = int(np.ceil(pts[:, 1].max() - y0)) + 1
    if w < 4 or h < 4:
        return None
    m = np.zeros((h, w), np.uint8)
    cv2.fillPoly(m, [np.round(pts - [x0, y0]).astype(np.int32)], 255)
    dt = cv2.distanceTransform(m, cv2.DIST_L2, 5)
    trong = dt > le
    if not trong.any():
        return None
    _, _, _, diem = cv2.minMaxLoc(dt)
    return trong, float(x0), float(y0), int(diem[0]), int(diem[1])


def _khoang_ngang(trong: np.ndarray, r0: int, r1: int, cx: int,
                  doi_xung: bool = True) -> tuple[int, int] | None:
    """Khoảng cột liền mạch chứa `cx` mà MỌI hàng trong [r0, r1) đều nằm trong mặt nạ."""
    h, w = trong.shape
    if r0 < 0 or r1 > h or r1 <= r0:
        return None
    hang = trong[r0:r1].all(axis=0)
    if not hang[cx]:
        return None
    trai = cx
    while trai > 0 and hang[trai - 1]:
        trai -= 1
    phai = cx
    while phai < w - 1 and hang[phai + 1]:
        phai += 1
    # ĐỐI XỨNG quanh trục `cx`: mọi dòng cùng một tâm. Lần đo đầu lấy nguyên khoảng trống của từng
    # dòng ⇒ bong bóng có đuôi/không đối xứng cho các dòng lệch tâm so với nhau ("KHOAN ĐÃ!" lệch
    # trái, "CHUYỆN NÀY" lệch phải) — nhìn như gõ sai. Chữ thoại căn giữa trên một trục chung.
    if not doi_xung:
        return trai, phai + 1
    nua = min(cx - trai, phai + 1 - cx)
    return cx - nua, cx + nua


def _ngat(tu: list[str], khoang: list[tuple[int, int]], font, stroke: int) -> list[str] | None:
    """Ngắt tham lam vào đúng `len(khoang)` dòng. Từ nào dài hơn dòng của nó ⇒ None (KHÔNG cắt từ, E60)."""
    dong: list[str] = []
    i = 0
    for trai, phai in khoang:
        rong = phai - trai
        hien = ""
        while i < len(tu):
            thu = f"{hien} {tu[i]}".strip()
            if be_rong_dong(font, thu, stroke) <= rong:
                hien = thu
                i += 1
            else:
                break
        if not hien:
            return None
        dong.append(hien)
    return dong if i == len(tu) else None


def xep_trong_da_giac(
    text: str,
    polygon: list[list[float]],
    font_resolver,
    font_family: str,
    co_nho_nhat: int,
    co_lon_nhat: int,
    ti_le_gian_dong: float,
    stroke: int = 0,
    #: Đa giác E14 vốn đã là lòng bong bóng thu vào (bước ăn mòn) — chỉ chừa thêm chút cho khử răng cưa.
    le: float = 1.0,
) -> KetQuaXepHinh | None:
    """Cỡ chữ LỚN NHẤT xếp được toàn bộ `text` vào trong đa giác, không cắt từ. Không được ⇒ None."""
    if not text or not text.strip() or "\n" in text.strip():
        return None
    tu = text.split()
    mn = _mat_na(polygon, le)
    if mn is None:
        return None
    trong, x0, y0, cx, cy = mn
    hang_co = np.flatnonzero(trong.any(axis=1))
    giua_doc = int((hang_co[0] + hang_co[-1]) // 2)
    cao = int(hang_co[-1] - hang_co[0] + 1)

    for co in range(int(co_lon_nhat), int(co_nho_nhat) - 1, -1):
        font = font_resolver.resolve(font_family, co)
        gian = int(round(co * ti_le_gian_dong))
        _lech, cao_net, buoc = do_dong(font, stroke, gian)
        for n in range(1, len(tu) + 1):
            tong = (n - 1) * buoc + cao_net
            if tong > cao:
                break
            for tam in (cy, giua_doc):
                dinh = int(round(tam - tong / 2))
                # Trục dọc chung = giữa khoảng ngang của dòng CHÍNH GIỮA khối. Lấy điểm xa biên nhất
                # làm trục thì nó thường lệch khỏi giữa bong bóng (đo: 17px tụt còn 13px).
                giua = _khoang_ngang(trong, dinh + (n - 1) // 2 * buoc,
                                     dinh + (n - 1) // 2 * buoc + cao_net, cx, doi_xung=False)
                if giua is None:
                    continue
                truc = (giua[0] + giua[1]) // 2
                khoang = []
                for k in range(n):
                    r0 = dinh + k * buoc
                    kh = _khoang_ngang(trong, r0, r0 + cao_net, truc)
                    if kh is None:
                        break
                    khoang.append(kh)
                if len(khoang) != n:
                    continue
                dong = _ngat(tu, khoang, font, stroke)
                if dong is None:
                    continue
                return KetQuaXepHinh(
                    font_size=float(co),
                    wrapped_text="\n".join(dong),
                    dong=tuple(
                        (x0 + (t + p) / 2.0, y0 + dinh + k * buoc)
                        for k, (t, p) in enumerate(khoang)
                    ),
                )
    return None


def tam_nam_trong(polygon: list[list[float]], diem: tuple[float, float]) -> bool:
    import cv2

    return cv2.pointPolygonTest(np.asarray(polygon, np.float32), diem, False) >= 0
