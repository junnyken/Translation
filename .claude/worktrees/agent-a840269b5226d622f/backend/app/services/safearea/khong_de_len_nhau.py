"""E27 — ô đặt chữ của vùng này KHÔNG được trùm lên khung chữ của vùng khác.

## Lỗi

Đo thật trên trang `0d47b661` (2026-09-12):

    392e16e2  khung chữ 466,25 173x27   ->  ô đặt chữ 399,3   497x156   (y 3–159)
    473212d5  khung chữ 391,69 274x32   ->  ô đặt chữ 379,33  636x130   (y 33–163)

Hai ô đặt chữ **chồng lên nhau**, và mỗi ô còn trùm lên **khung chữ của vùng kia**. Kết quả: chữ
của hai bong bóng vẽ đè nhau, không đọc được.

A1 nới ô đặt chữ ra **tới khi chạm nét vẽ** — đó là chủ đích và đo được là giảm tràn 3→2. Nhưng
nền ở chỗ này là **trời phẳng**: không có nét vẽ nào cản, nên nó nới tràn cả trang. Và A1 **không
coi vùng chữ khác là vật cản** — nó chỉ nhìn tranh, không nhìn các vùng chữ anh em.

## Hệ quả thứ hai, âm thầm hơn

Bộ căn chữ được đưa `place_rect` chứ không phải khung chữ, nên nó đo `40pt` vào ô `497x156` rồi
kết luận `fit_ok` — **đúng với ô nó nhận**, nhưng ô đó rộng gấp 16 lần khung thật. Người dùng thấy
nhãn *"Vừa khung"* trên một vùng mà chữ tràn ra đè vùng khác.

Bộ căn chữ KHÔNG nói dối; nó bị đưa sai đầu vào. Vá ở đây là vá cả hai triệu chứng.

## Cách vá: cắt bớt, KHÔNG bỏ hẳn việc nới

Bỏ nới ô là mất luôn cái A1 đem lại. Nên chỉ **cắt lại** ô đặt chữ đủ để nó không còn trùm lên
khung chữ của vùng khác, và **không bao giờ cắt vào khung chữ của chính nó** — cắt vào đó là làm
tệ hơn cả khi không nới.

Chọn nhát cắt **mất ít diện tích nhất** trong các nhát hợp lệ. Không nhát nào hợp lệ (vật cản đè
lên chính khung chữ của mình) thì **giữ nguyên**: đó là hai vùng nhận diện chồng nhau, việc của
E26-B/B2, không phải việc của module này.
"""
from __future__ import annotations

#: Chừa một chút để hai ô không dính sát nhau, chữ hai bên đỡ chạm nhau.
KHE_HO_PX = 1.0

_Rect = tuple[float, float, float, float]  # (x, y, w, h)


def _chong_nhau(a: _Rect, b: _Rect) -> bool:
    return not (
        a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0] or a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1]
    )


def _chua_tron(ngoai: _Rect, trong: _Rect) -> bool:
    return (
        ngoai[0] <= trong[0]
        and ngoai[1] <= trong[1]
        and ngoai[0] + ngoai[2] >= trong[0] + trong[2]
        and ngoai[1] + ngoai[3] >= trong[1] + trong[3]
    )


def _giao(a: _Rect, b: _Rect) -> _Rect | None:
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1 = min(a[0] + a[2], b[0] + b[2])
    y1 = min(a[1] + a[3], b[1] + b[3])
    if x1 <= x0 or y1 <= y0:
        return None
    return (x0, y0, x1 - x0, y1 - y0)


def _cat_mot_vat_can(o: _Rect, phai_giu: _Rect, vat_can: _Rect, khe: float) -> _Rect:
    """Cắt `o` cho hết chồng `vat_can`, giữ trọn `phai_giu`. Không cắt được thì trả nguyên `o`."""
    if not _chong_nhau(o, vat_can):
        return o

    ox, oy, ow, oh = o
    vx, vy, vw, vh = vat_can
    gx, gy, gw, gh = phai_giu
    # E83 — cắt ở ĐƯỜNG GIỮA khoảng trống giữa phần phải giữ và vật cản, không phải sát vật cản.
    # Vùng bên kia cũng tự cắt về đúng đường giữa đó ⇒ hai ô KHÔNG chồng nhau. Cắt sát vật cản
    # (trước E83) thì cả hai ô cùng chiếm khoảng trống ⇒ chữ căn giữa ô đè lên nhau (đo thật
    # 16-10-2026, sáu câu trong một bong bóng mây). Vật cản đã chạm phần phải giữ ⇒ không có khoảng
    # trống để chia, cắt sát như cũ.
    phai = min(vx - khe, (gx + gw + vx) / 2) if vx >= gx + gw else vx - khe
    trai = max(vx + vw + khe, (vx + vw + gx) / 2) if vx + vw <= gx else vx + vw + khe
    duoi = min(vy - khe, (gy + gh + vy) / 2) if vy >= gy + gh else vy - khe
    tren = max(vy + vh + khe, (vy + vh + gy) / 2) if vy + vh <= gy else vy + vh + khe
    ung_vien: list[_Rect] = [
        (ox, oy, max(0.0, phai - ox), oh),                 # cắt bên PHẢI
        (trai, oy, max(0.0, ox + ow - trai), oh),          # cắt bên TRÁI
        (ox, oy, ow, max(0.0, duoi - oy)),                 # cắt bên DƯỚI
        (ox, tren, ow, max(0.0, oy + oh - tren)),          # cắt bên TRÊN
    ]
    hop_le = [
        c for c in ung_vien
        if c[2] > 0 and c[3] > 0 and _chua_tron(c, phai_giu) and not _chong_nhau(c, vat_can)
    ]
    if not hop_le:
        # Vật cản đè lên chính khung chữ của mình ⇒ cắt kiểu gì cũng mất chữ. Giữ nguyên và để
        # E26-B/B2 xử lý ở bước vẽ.
        return o
    return max(hop_le, key=lambda c: c[2] * c[3])


def cat_o_dat_chu(
    o_dat: dict,
    khung: dict,
    *,
    khe_ho: float = KHE_HO_PX,
) -> dict:
    """Cắt lại từng ô đặt chữ để nó không trùm lên **khung chữ** của vùng khác.

    `o_dat`: {region_id: (x, y, w, h)} — ô đặt chữ A1 tính ra, có thể thiếu vài vùng.
    `khung`: {region_id: (x, y, w, h)} — khung chữ gốc của MỌI vùng trên trang.

    Trả dict mới cùng khoá với `o_dat`. Vùng không có khung chữ của chính nó thì giữ nguyên —
    thiếu bằng chứng thì không cắt, chứ không đoán.
    """
    ra: dict = {}
    for rid, o in o_dat.items():
        khung_minh = khung.get(rid)
        if khung_minh is None or o[2] <= 0 or o[3] <= 0:
            ra[rid] = o
            continue
        # Phần PHẢI GIỮ là **giao** của ô đặt chữ với khung chữ của chính vùng đó, chứ không phải
        # cả khung chữ.
        #
        # Đo thật trên `0d47b661`: với bong bóng thật, vùng an toàn là LÒNG bong bóng đã ăn mòn
        # nên nó **hẹp hơn** khung chữ (`e8e30ad4`: ô x 423–660 so với khung x 421–671). Nếu đòi ô
        # phải bao trọn khung chữ thì module này **không chạm tới phần lớn bong bóng thật** — chỉ
        # chạy đúng mấy ca dự phòng nới tràn. Lấy phần giao thì đúng cho cả hai kiểu.
        phai_giu = _giao(o, khung_minh)
        if phai_giu is None:
            # Ô đặt chữ không dính gì tới khung chữ của chính nó — ngoài dự tính, không cắt.
            ra[rid] = o
            continue
        moi = o
        # Cắt theo vật cản LỚN trước: cắt cái to trước thì nhát sau ít khi phải cắt nữa.
        vat_can = sorted(
            ((k, b) for k, b in khung.items() if k != rid),
            key=lambda kv: kv[1][2] * kv[1][3],
            reverse=True,
        )
        for _k, b in vat_can:
            moi = _cat_mot_vat_can(moi, phai_giu, b, khe_ho)
        ra[rid] = moi
    return _tach_o_chong_nhau(ra, khung)


def _tach_o_chong_nhau(o_dat: dict, khung: dict) -> dict:
    """E83 — lượt hai: hai Ô ĐẶT CHỮ còn chồng nhau thì chia ở đường giữa hai khung chữ.

    Lượt một chỉ cắt khi ô của mình trùm lên KHUNG CHỮ vùng kia. Đo thật (ja_E12P01): ô câu 6 tự
    nó dừng ở y=257, không chạm khung câu 5 (đáy 237) nên không bị cắt; ô câu 5 thì nới xuống tới
    270 ⇒ hai ô chồng 13px, chữ căn giữa mỗi ô đè lên nhau. Ở đây chọn trục mà hai khung chữ cách
    nhau XA nhất, cắt cả hai ô về đường giữa. Hai khung tự chồng nhau (không có khoảng trống trên
    trục nào) ⇒ giữ nguyên, việc của E26-B/B2.
    """
    ra = dict(o_dat)
    ids = [k for k in ra if k in khung]
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            oa, ob = ra[a], ra[b]
            if not _chong_nhau(oa, ob):
                continue
            ka, kb = khung[a], khung[b]
            ung_vien = []
            if ka[1] + ka[3] <= kb[1]:    # a TRÊN b
                ung_vien.append((kb[1] - (ka[1] + ka[3]), "y", a, b))
            if kb[1] + kb[3] <= ka[1]:    # b TRÊN a
                ung_vien.append((ka[1] - (kb[1] + kb[3]), "y", b, a))
            if ka[0] + ka[2] <= kb[0]:    # a TRÁI b
                ung_vien.append((kb[0] - (ka[0] + ka[2]), "x", a, b))
            if kb[0] + kb[2] <= ka[0]:    # b TRÁI a
                ung_vien.append((ka[0] - (kb[0] + kb[2]), "x", b, a))
            if not ung_vien:
                continue
            _khe, truc, dau, sau = max(ung_vien)
            kd, ks = khung[dau], khung[sau]
            od, os_ = ra[dau], ra[sau]
            if truc == "y":
                giua = (kd[1] + kd[3] + ks[1]) / 2
                day_dau = min(od[1] + od[3], giua)
                ra[dau] = (od[0], od[1], od[2], max(0.0, day_dau - od[1]))
                dinh_sau = max(os_[1], giua)
                ra[sau] = (os_[0], dinh_sau, os_[2], max(0.0, os_[1] + os_[3] - dinh_sau))
            else:
                giua = (kd[0] + kd[2] + ks[0]) / 2
                phai_dau = min(od[0] + od[2], giua)
                ra[dau] = (od[0], od[1], max(0.0, phai_dau - od[0]), od[3])
                trai_sau = max(os_[0], giua)
                ra[sau] = (trai_sau, os_[1], max(0.0, os_[0] + os_[2] - trai_sau), os_[3])
    return ra


def kep_trong_khung_tranh(o_dat: dict, khung: dict, khung_tranh: list) -> dict:
    """E86 — ô đặt chữ không được vượt ra ngoài KHUNG TRANH chứa nó.

    Đo thật (ja_E12P01): bong bóng chạm mép khung tranh ⇒ lòng trắng bong bóng nối liền lề trắng
    của trang ⇒ A1 nới ô tràn ra lề ⇒ chữ vẽ ra ngoài khung tranh, có câu rớt khỏi mép trang.

    `khung_tranh`: danh sách (x0, y0, x1, y1) — lá của cắt XY (E82). Chỉ kẹp ở CẠNH mà khung chữ của
    chính vùng nằm trong khung tranh: bong bóng cố ý tràn qua mép khung (rất hay gặp) thì cạnh đó để
    nguyên. Không khung tranh nào chứa tâm khung chữ ⇒ giữ nguyên.
    """
    ra = dict(o_dat)
    for rid, o in o_dat.items():
        k = khung.get(rid)
        if k is None:
            continue
        cx, cy = k[0] + k[2] / 2, k[1] + k[3] / 2
        tranh = next((t for t in khung_tranh if t[0] <= cx < t[2] and t[1] <= cy < t[3]), None)
        if tranh is None or len(khung_tranh) < 2:
            continue
        x0, y0, x1, y1 = o[0], o[1], o[0] + o[2], o[1] + o[3]
        if k[0] >= tranh[0]:
            x0 = max(x0, tranh[0])
        if k[1] >= tranh[1]:
            y0 = max(y0, tranh[1])
        if k[0] + k[2] <= tranh[2]:
            x1 = min(x1, tranh[2])
        if k[1] + k[3] <= tranh[3]:
            y1 = min(y1, tranh[3])
        if x1 > x0 and y1 > y0:
            ra[rid] = (x0, y0, x1 - x0, y1 - y0)
    return ra
