"""Đo màu chữ, màu viền và bề dày viền của chữ GỐC trong một vùng — để chữ dịch mặc đúng "áo" cũ.

## Nguồn

Chuyển từ Koharu (`crates/koharu-pipeline/src/stages/detection.rs`: `infer_typography`,
`infer_text_paint`, `infer_outline`, `color_clusters`, `measured_stroke_width`,
`normalize_text_color`; MIT OR Apache-2.0, © Mayo Takanashi and Koharu contributors). Viết lại
bằng numpy + OpenCV, giữ nguyên các hằng số và thứ tự quyết định.

## Cách làm (giữ đúng tinh thần Koharu)

1. Lấy ô = khung chữ nới 2px. Màu NỀN gợi ý = trung vị dải 2px sát mép ô.
2. Gom màu trong ô thành 4 cụm, khởi tạo bằng: nền, điểm tối nhất, điểm sáng nhất, và màu xa ba
   màu kia nhất; chạy 4 vòng k-means trên bảng màu đã lượng tử 16 mức/kênh.
3. **Viền chữ được nhận ra bằng HÌNH, không bằng màu**: một cụm S là viền nếu nó bao kín một cụm
   F (có điểm F không đi ra được mép ô mà không băng qua S). Chỉ màu thôi không đủ: lõi chữ đen
   có thể trùng màu với nét vẽ đen bên ngoài viền trắng.
4. Bề dày viền = trung vị khoảng cách từ các điểm viền phía NGOÀI tới lõi chữ gần nhất; dưới 2px
   thì coi như không có viền.
5. Không thấy viền ⇒ màu chữ = cụm "đậm mực" nhất (xa nền nhất × nhiều điểm nhất).
6. Màu gần đen/gần trắng thì quy hẳn về đen/trắng (độ sáng ≤64 / ≥191) — nhiễu JPEG không được
   biến chữ đen thành xám đậm. Riêng ở đây chỉ quy khi màu gần xám (xem `_chuan_hoa`).

Đầu ra luôn có màu chữ; viền chỉ có khi đo được (None = không viền).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.services.interfaces import BBox

LE_LAY_MAU = 2
SO_CUM = 4
KHOANG_CACH_CUM_TOI_THIEU_BP = 32 * 32
DIEM_CUC_TRI_TOI_THIEU = 4
VIEN_TOI_THIEU = 2
DO_SANG_DEN = 64 * 256
DO_SANG_TRANG = 191 * 256
#: Chênh lệch kênh tối đa để còn coi là "gần xám" (được quy về đen/trắng).
DO_LECH_KENH_XAM = 48


@dataclass(frozen=True)
class MauChu:
    mau: tuple[int, int, int]
    mau_vien: tuple[int, int, int] | None = None
    #: Bề dày viền theo điểm ảnh của ẢNH GỐC (chưa nhân hệ số vẽ E65).
    vien: float | None = None


def hex_mau(m: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*m)


def _do_sang(c) -> int:
    return int(c[0]) * 54 + int(c[1]) * 183 + int(c[2]) * 19


def _kc2(a, b) -> int:
    d = np.asarray(a, np.int64) - np.asarray(b, np.int64)
    return int((d * d).sum())


def _chuan_hoa(c) -> tuple[int, int, int]:
    # Khác Koharu: chỉ quy về đen/trắng khi màu GẦN XÁM. Koharu chỉ xét độ sáng nên chữ vàng tươi
    # (250,220,40 — độ sáng ~213) bị quy thành trắng; đo trên ca thử E70 đúng như vậy.
    if max(c) - min(c) > DO_LECH_KENH_XAM:
        return tuple(int(v) for v in c)
    s = _do_sang(c)
    if s <= DO_SANG_DEN:
        return (0, 0, 0)
    if s >= DO_SANG_TRANG:
        return (255, 255, 255)
    return tuple(int(v) for v in c)


def _trung_vi(px: np.ndarray) -> tuple[int, int, int]:
    """Trung vị từng kênh kiểu Koharu: trung bình hai phần tử giữa, làm tròn xuống."""
    s = np.sort(px.astype(np.int64), axis=0)
    n = s.shape[0]
    lo, hi = s[(n - 1) // 2], s[n // 2]
    return tuple(int(v) for v in (lo + hi) // 2)


def _nam_giua(ung_vien, dau, cuoi) -> bool:
    """Màu `ung_vien` nằm trên đoạn thẳng dau→cuoi trong không gian màu (sai số 24/kênh)."""
    a, b, c = (np.asarray(x, np.float64) for x in (dau, cuoi, ung_vien))
    huong = b - a
    dai2 = float(huong @ huong)
    if dai2 <= 1e-12:
        return False
    t = float((c - a) @ huong) / dai2
    if not 0.0 <= t <= 1.0:
        return False
    lech = c - (a + huong * t)
    return float(lech @ lech) <= 24.0 ** 2 * 3.0


def _gom_cum(px: np.ndarray, nen) -> tuple[np.ndarray, np.ndarray]:
    """Trả (tâm 4×3, nhãn từng điểm). `px`: N×3 uint8."""
    q = (px >> 4).astype(np.int64)
    ma = (q[:, 0] << 8) | (q[:, 1] << 4) | q[:, 2]
    ma_bin, nghich, dem = np.unique(ma, return_inverse=True, return_counts=True)
    tong = np.zeros((ma_bin.size, 3), np.int64)
    np.add.at(tong, nghich, px.astype(np.int64))
    mau_bin = (tong + dem[:, None] // 2) // dem[:, None]
    sang = mau_bin @ np.array([54, 183, 19])

    def cuc_tri(toi: bool):
        chon = dem >= DIEM_CUC_TRI_TOI_THIEU
        if not chon.any():
            chon = np.ones_like(chon)
        idx = np.flatnonzero(chon)
        return mau_bin[idx[np.argmin(sang[idx])] if toi else idx[np.argmax(sang[idx])]]

    toi, sang_nhat = cuc_tri(True), cuc_tri(False)
    goc = np.array([nen, toi, sang_nhat], np.int64)
    kc_min = ((mau_bin[:, None, :] - goc[None]) ** 2).sum(2).min(1)
    xa = mau_bin[np.argmax(kc_min * np.minimum(dem, 64))]
    tam = np.array([nen, toi, sang_nhat, xa], np.int64)

    for _ in range(4):
        gan = ((mau_bin[:, None, :] - tam[None]) ** 2).sum(2).argmin(1)
        for k in range(SO_CUM):
            m = gan == k
            if m.any():
                n = int(dem[m].sum())
                tam[k] = (tong[m].sum(0) + n // 2) // n
    nhan = ((px.astype(np.int64)[:, None, :] - tam[None]) ** 2).sum(2).argmin(1)
    return tam, nhan


def _do_vien(
    nhan: np.ndarray, tam: np.ndarray, anh: np.ndarray, trong_khung: np.ndarray, nen
) -> MauChu | None:
    import cv2

    co_diem = [int((nhan == k).sum()) for k in range(SO_CUM)]
    ung_nen = [k for k in range(SO_CUM) if co_diem[k]]
    if not ung_nen:
        return None
    i_nen = min(ung_nen, key=lambda k: _kc2(tam[k], nen))

    tot = None
    for s in range(SO_CUM):
        if co_diem[s] < 8 or s == i_nen:
            continue
        # "Ra được mép mà không băng qua S": thêm viền 1px đi được quanh ô (như Koharu) rồi lấy
        # thành phần liên thông 4 hướng chứa góc.
        di_duoc = np.pad((nhan != s).astype(np.uint8), 1, constant_values=1)
        _n, tp = cv2.connectedComponents(di_duoc, connectivity=4)
        ngoai = (tp == tp[0, 0])[1:-1, 1:-1]
        mat_s = (nhan == s).astype(np.uint8)
        _ns, tp_s = cv2.connectedComponents(mat_s, connectivity=8)
        for f in range(SO_CUM):
            if f == s or not co_diem[f]:
                continue
            bi_bao = (nhan == f) & ~ngoai
            if int(bi_bao.sum()) < 8:
                continue
            # Điểm viền = các mảng S (8 hướng) chạm vào lõi bị bao.
            cham = cv2.dilate(bi_bao.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
            nhan_cham = np.unique(tp_s[cham & (mat_s > 0)])
            vien = np.isin(tp_s, nhan_cham[nhan_cham > 0]) & (mat_s > 0)
            if int(vien.sum()) < 8:
                continue
            mau_f, mau_s = _trung_vi(anh[bi_bao]), _trung_vi(anh[vien])
            tuong_phan = _kc2(mau_f, mau_s)
            if (
                tuong_phan < KHOANG_CACH_CUM_TOI_THIEU_BP
                or _kc2(mau_f, nen) < KHOANG_CACH_CUM_TOI_THIEU_BP
                or _kc2(mau_s, nen) < KHOANG_CACH_CUM_TOI_THIEU_BP
                or _nam_giua(mau_s, mau_f, nen)
                or _nam_giua(mau_f, mau_s, nen)
            ):
                continue
            f_chuan, s_chuan = _chuan_hoa(mau_f), _chuan_hoa(mau_s)
            if f_chuan == s_chuan:
                continue
            day = _be_day_vien(vien, bi_bao, ngoai)
            if day is None:
                continue
            bang_chung = int(bi_bao.sum()) + int((bi_bao & trong_khung).sum())
            diem = tuong_phan * min(bang_chung, 4096)
            if tot is None or diem > tot[0]:
                tot = (diem, MauChu(mau=f_chuan, mau_vien=s_chuan, vien=day))
    return tot[1] if tot else None


def _be_day_vien(vien: np.ndarray, loi: np.ndarray, ngoai: np.ndarray) -> float | None:
    import cv2

    # Khoảng cách tới điểm LÕI gần nhất (cv2 đo tới điểm 0 ⇒ đặt lõi = 0).
    kc = cv2.distanceTransform(np.where(loi, 0, 255).astype(np.uint8), cv2.DIST_L2, 5)
    kc = np.minimum(np.round(kc), 255).astype(np.int64)
    # Chỉ lấy điểm viền nằm ở MÉP NGOÀI (8 hướng chạm vùng "ngoài") — đó là nơi đo được bề dày.
    sat_ngoai = cv2.dilate(ngoai.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    d = kc[vien & sat_ngoai]
    d = d[d > 0]
    if d.size < 8:
        return None
    s = np.sort(d)
    day = int((s[(s.size - 1) // 2] + s[s.size // 2]) // 2)
    return float(day) if day >= VIEN_TOI_THIEU else None


def do_mau_chu(anh: np.ndarray, bbox: BBox) -> MauChu | None:
    """Đo trên ẢNH GỐC (chưa xoá chữ). `anh`: HWC uint8 RGB. None nếu khung rỗng sau khi kẹp."""
    cao, rong = anh.shape[:2]
    x1 = max(0, int(np.floor(bbox.x - LE_LAY_MAU)))
    y1 = max(0, int(np.floor(bbox.y - LE_LAY_MAU)))
    x2 = min(rong, int(np.ceil(bbox.x + bbox.w + LE_LAY_MAU)))
    y2 = min(cao, int(np.ceil(bbox.y + bbox.h + LE_LAY_MAU)))
    if x2 - x1 < 3 or y2 - y1 < 3:
        return None
    o = anh[y1:y2, x1:x2]
    h, w = o.shape[:2]

    mep = np.zeros((h, w), bool)
    mep[:LE_LAY_MAU], mep[-LE_LAY_MAU:], mep[:, :LE_LAY_MAU], mep[:, -LE_LAY_MAU:] = (True,) * 4
    nen = _trung_vi(o[mep])

    # "Trong mặt nạ" của Koharu = điểm của chính vùng chữ. Ở đây chỉ có khung ⇒ trong khung.
    trong = np.zeros((h, w), bool)
    trong[
        max(0, int(np.floor(bbox.y)) - y1): int(np.ceil(bbox.y + bbox.h)) - y1,
        max(0, int(np.floor(bbox.x)) - x1): int(np.ceil(bbox.x + bbox.w)) - x1,
    ] = True

    px = o.reshape(-1, 3)
    tam, nhan_phang = _gom_cum(px, nen)
    nhan = nhan_phang.reshape(h, w)

    co_vien = _do_vien(nhan, tam, o, trong, nen)
    if co_vien is not None:
        return co_vien

    co = [k for k in range(SO_CUM) if (nhan == k).any()]
    if len(co) == 1:
        return MauChu(mau=_chuan_hoa(tam[co[0]]))
    i_nen = min(co, key=lambda k: _kc2(tam[k], nen))

    def diem_muc(k: int) -> int:
        m = nhan == k
        n_trong = int((m & trong).sum())
        bang_chung = n_trong + int(m.sum()) if n_trong >= 8 else int(m.sum())
        return _kc2(tam[k], nen) * min(bang_chung, 4096)

    khac = [k for k in co if k != i_nen]
    if not khac:
        return MauChu(mau=_chuan_hoa(tam[i_nen]))
    k = max(khac, key=diem_muc)
    m = nhan == k
    m_trong = m & trong
    mau = _trung_vi(o[m_trong]) if int(m_trong.sum()) >= 8 else _trung_vi(o[m])
    return MauChu(mau=_chuan_hoa(mau))
