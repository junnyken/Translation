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


def _bao_ve_net_ve_va_da_trang_trong_o(
    anh_o: np.ndarray,
    seg_o: np.ndarray,
    net_no_o: np.ndarray,
) -> np.ndarray:
    """Giới hạn mặt nạ nở `net_no_o` trong ô `anh_o` để bảo toàn 100% nét vẽ nhân vật liên thông từ biên
    (ngón tay, xương hàm, vành tai, điếu thuốc, tia tốc độ) và không nở rộng viền halo qua da/mảng trắng hở (`open_white`).
    """
    import cv2

    sh, sw = seg_o.shape[:2]
    if sh < 8 or sw < 8:
        return net_no_o
    gray = cv2.cvtColor(anh_o, cv2.COLOR_RGB2GRAY) if anh_o.ndim == 3 else anh_o
    k3 = np.ones((3, 3), np.uint8)
    core = ((seg_o > 0) & (gray <= 175)).astype(np.uint8)
    if int(core.sum()) < 4:
        core = (seg_o > 0).astype(np.uint8)
    if int(core.sum()) == 0:
        return net_no_o

    # 1. Nét vẽ đen liên thông chạm biên ô cắt và nằm ngoài vùng lõi chữ -> khoá cứng không xoá:
    dark_line = ((gray <= 135) & (core == 0)).astype(np.uint8)
    nl_d, lbl_d, st_d, _ = cv2.connectedComponentsWithStats(dark_line, connectivity=8)
    art_block = np.zeros((sh, sw), dtype=bool)
    for did in range(1, nl_d):
        dx, dy = int(st_d[did, cv2.CC_STAT_LEFT]), int(st_d[did, cv2.CC_STAT_TOP])
        dw, dh = int(st_d[did, cv2.CC_STAT_WIDTH]), int(st_d[did, cv2.CC_STAT_HEIGHT])
        da = int(st_d[did, cv2.CC_STAT_AREA])
        if (dx <= 1 or dy <= 1 or dx + dw >= sw - 1 or dy + dh >= sh - 1) and (da >= 18 or max(dw, dh) >= 12):
            art_block[lbl_d == did] = True

    # 2. Mảng tóc/áo đen đặc thực sự (sống sót sau co 3x3, loại bỏ viền mảnh 1-2px của ngón tay/mặt):
    solid_blk_raw = cv2.erode(((gray <= 30) & (core == 0)).astype(np.uint8), k3, iterations=1)
    solid_blk_seed = np.zeros_like(solid_blk_raw)
    nl_sb, lbl_sb, st_sb, _ = cv2.connectedComponentsWithStats(solid_blk_raw, connectivity=8)
    for sbid in range(1, nl_sb):
        if int(st_sb[sbid, cv2.CC_STAT_AREA]) >= 20:
            solid_blk_seed[lbl_sb == sbid] = 1
    solid_blk_closed = cv2.morphologyEx(
        solid_blk_seed, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (23, 19))
    )
    near_solid_black = cv2.dilate(solid_blk_closed, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)), iterations=1) > 0

    # 3. Mảng da/nền trắng hở (`open_white`, dùng `blur3_nc` bỏ qua `core` để không tạo rãnh giả quanh chữ):
    core_buf5 = cv2.dilate(core, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)), iterations=1)
    g_no_core = np.where(core > 0, 255, gray)
    blur3_nc = cv2.blur(g_no_core.astype(np.float32), (3, 3))
    white_or_core = (((gray >= 242) & (blur3_nc >= 238) & (~art_block)) | (core > 0)).astype(np.uint8)
    white_or_core[(core_buf5 > 0) & near_solid_black] = 0
    k9_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    w_eroded = cv2.erode(white_or_core, k9_open, iterations=1)
    w_seed = np.zeros_like(w_eroded)
    nl_wo, lbl_wo, st_wo, _ = cv2.connectedComponentsWithStats(w_eroded, connectivity=4)
    for woid in range(1, nl_wo):
        if int(st_wo[woid, cv2.CC_STAT_AREA]) >= 6:
            wm = lbl_wo == woid
            wx, wy = int(st_wo[woid, cv2.CC_STAT_LEFT]), int(st_wo[woid, cv2.CC_STAT_TOP])
            ww, wh = int(st_wo[woid, cv2.CC_STAT_WIDTH]), int(st_wo[woid, cv2.CC_STAT_HEIGHT])
            touches_edge = wx <= 3 or wy <= 3 or (wx + ww) >= sw - 3 or (wy + wh) >= sh - 3
            if touches_edge or int(np.sum(wm & (core_buf5 == 0))) >= 6:
                w_seed[wm] = 1
    open_white = (
        (cv2.dilate(w_seed, k9_open, iterations=1) > 0)
        & (gray >= 240)
        & (core == 0)
        & (~art_block)
        & (~near_solid_black)
    )
    d1_core = cv2.dilate(core, k3, iterations=1) > 0
    cho_phep_tren_trang = (core > 0) | (d1_core & (gray < 245) & (~art_block))
    ket = net_no_o & (~art_block)
    ket = np.where(open_white, cho_phep_tren_trang, ket)
    return ket


def tinh_mat_na_xoa(mat_na_khung: np.ndarray, mat_na_chu: np.ndarray,
                    khung: list[tuple[int, int, int, int]],
                    he_so_no: float = HE_SO_NO_MAC_DINH,
                    anh_rgb: np.ndarray | None = None) -> tuple[np.ndarray, int]:
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
            if anh_rgb is not None and anh_rgb.shape[:2] == mat_na_khung.shape[:2]:
                o = _bao_ve_net_ve_va_da_trang_trong_o(
                    anh_rgb[y1:y2, x1:x2], mat_na_chu[y1:y2, x1:x2], o
                )
            ra[y1:y2, x1:x2] = np.maximum(ra[y1:y2, x1:x2], o.astype(np.float32))
    return ra * (mat_na_khung > 0), lui


#: E87 — chữ nằm TRÊN TRANH (không bong bóng, không tô phẳng được) mà không có mặt nạ `seg`
#: (nhận diện bằng Gemini chỉ cho khung). Chữ hiệu ứng truyện tranh gần như luôn có VIỀN trắng
#: hoặc đen đậm ⇒ lấy các điểm rất trắng / rất đen trong khung, nở ra để phủ cả phần ruột màu của
#: nét, rồi chỉ xoá chừng đó thay vì cả khung. Đo thật ja_E12P01 (カラン/コロン trên đống chai lọ):
#: xoá cả khung ⇒ LaMa xoá mất mấy chai lọ; mặt nạ này phủ 41% khung, bám đúng chữ.
SANG_TRANG = 225
SAC_DO_TRANG_TOI_DA = 30
TOI_DEN = 60
#: Viền chiếm ít hơn mức này ⇒ không phải chữ có viền ⇒ xoá cả khung như cũ.
TI_LE_VIEN_TOI_THIEU = 0.03
#: Mặt nạ sau khi nở mà phủ quá mức này ⇒ không tiết kiệm được gì / nghi ngờ ⇒ xoá cả khung.
TI_LE_MAT_NA_TOI_DA = 0.7


def mat_na_net_tren_tranh(anh: np.ndarray, o: tuple[int, int, int, int]) -> np.ndarray | None:
    """Mặt nạ bool (cao×rộng của ô `o`) các nét chữ có viền trắng/đen; None = không chắc ⇒ cả khung."""
    import cv2

    x1, y1, x2, y2 = o
    vung = anh[y1:y2, x1:x2].astype(np.int16)
    if vung.size == 0:
        return None
    sang = vung.mean(axis=2)
    sac = vung.max(axis=2) - vung.min(axis=2)
    trang = (sang >= SANG_TRANG) & (sac <= SAC_DO_TRANG_TOI_DA)
    den = sang <= TOI_DEN

    cao, rong = anh.shape[:2]
    r = max(2, round(max(rong, cao) / 1024 * 2.8))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))

    # 1. Trường hợp chữ nổi có cặp [Ruột đen/màu + Viền halo trắng] hoặc [Ruột trắng/màu + Viền halo đen]
    # trên nền screentone / tóc đen / tia tốc độ (speedlines) / nền tranh màu:
    # Thay vì lấy giao giản đơn `(den & trang_no)` (sẽ bắt nhầm toàn bộ tia tốc độ đen-trắng xen kẽ hoặc nét vẽ trên áo trắng),
    # lọc theo Thành phần liên thông (Connected Components) của lõi chữ: chiều cao 1 dòng chữ (`2 <= ch <= 27`),
    # không chạm biên vùng cắt, và có vành đai trắng (`sang >= 180`) bao bọc >= 70% chu vi nét chữ!
    den_cc = (sang < 135).astype(np.uint8)
    n_cc, labels_cc, stats_cc, _ = cv2.connectedComponentsWithStats(den_cc, connectivity=8)
    sh_v, sw_v = sang.shape[:2]
    char_core = np.zeros_like(den_cc)
    for i_cc in range(1, n_cc):
        cx_c, cy_c, cw_c, ch_c, area_c = (int(v) for v in stats_cc[i_cc])
        if cw_c < 2 or cw_c > 175 or ch_c < 2 or ch_c > 27 or area_c < 3 or area_c > 2200:
            continue
        if cx_c <= 1 or cy_c <= 1 or cx_c + cw_c >= sw_v - 1 or cy_c + ch_c >= sh_v - 1:
            continue
        comp_m = (labels_cc == i_cc).astype(np.uint8)
        d1 = cv2.dilate(comp_m, np.ones((3, 3), np.uint8))
        d2 = cv2.dilate(comp_m, np.ones((7, 7), np.uint8))
        ring = (d2 > 0) & (d1 == 0) & (den_cc == 0)
        if ring.sum() >= 6 and float((sang[ring] >= 180).mean()) >= 0.70:
            char_core[comp_m > 0] = 1
    if char_core.mean() >= 0.01:
        k_halo = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        vung_halo = (cv2.dilate(char_core, k_halo) > 0) & (sang >= 175)
        m_chu_halo = (char_core > 0) | vung_halo
        m_chu_halo = cv2.dilate(m_chu_halo.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
        if m_chu_halo.mean() <= TI_LE_MAT_NA_TOI_DA:
            return m_chu_halo

    mau_sac_dam = sac >= 48
    k_sat = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 3, 2 * r + 3))
    if trang.mean() >= TI_LE_VIEN_TOI_THIEU and (den.mean() >= TI_LE_VIEN_TOI_THIEU or mau_sac_dam.mean() >= TI_LE_VIEN_TOI_THIEU):
        trang_no = cv2.dilate(trang.astype(np.uint8), k_sat) > 0
        den_no = cv2.dilate(den.astype(np.uint8), k_sat) > 0
        # Chỉ giữ các điểm ruột (đen hoặc màu đậm) nằm sát viền trắng VÀ các điểm viền trắng/đen nằm sát nhau
        loi_co_vien_trang = (den | mau_sac_dam) & trang_no
        vien_trang_co_loi = trang & (cv2.dilate(loi_co_vien_trang.astype(np.uint8), k_sat) > 0)
        loi_sang_co_vien_den = (trang | mau_sac_dam) & den_no
        vien_den_co_loi = den & (cv2.dilate(loi_sang_co_vien_den.astype(np.uint8), k_sat) > 0)
        cap_net = loi_co_vien_trang | vien_trang_co_loi | loi_sang_co_vien_den | vien_den_co_loi
        if cap_net.mean() >= TI_LE_VIEN_TOI_THIEU:
            m_cap = cv2.morphologyEx(cv2.dilate(cap_net.astype(np.uint8), k), cv2.MORPH_CLOSE, k) > 0
            if m_cap.mean() <= TI_LE_MAT_NA_TOI_DA:
                return m_cap

    # 2. Trường hợp chữ nổi không viền (hoặc chữ màu) đặt trên nền màu chuyển sắc (gradient) / đám mây màu:
    # So sánh độ lệch màu RGB của từng điểm ảnh với màu nền làm mượt cục bộ (15x15).
    k_blur = max(9, (min(vung.shape[0], vung.shape[1]) // 4) | 1)
    nen_muot = cv2.GaussianBlur(vung.astype(np.float32), (k_blur, k_blur), 0)
    lech_mau_cuc_bo = np.abs(vung.astype(np.float32) - nen_muot).sum(axis=2)
    net_tuong_phan_mau = lech_mau_cuc_bo >= 62.0
    if TI_LE_VIEN_TOI_THIEU <= net_tuong_phan_mau.mean() <= 0.38:
        m_mau = cv2.morphologyEx(cv2.dilate(net_tuong_phan_mau.astype(np.uint8), k), cv2.MORPH_CLOSE, k) > 0
        if TI_LE_VIEN_TOI_THIEU <= m_mau.mean() <= TI_LE_MAT_NA_TOI_DA:
            return m_mau

    vien = trang if (trang.mean() >= TI_LE_VIEN_TOI_THIEU and (trang.mean() >= den.mean() or den.mean() > 0.45)) else den
    if vien.mean() < TI_LE_VIEN_TOI_THIEU:
        return None
    m = cv2.morphologyEx(cv2.dilate(vien.astype(np.uint8), k), cv2.MORPH_CLOSE, k) > 0
    if m.mean() > TI_LE_MAT_NA_TOI_DA:
        return None
    return m


def xoa_chu_noi_bao_toan_nen(
    anh: np.ndarray,
    o: tuple[int, int, int, int],
    kieu_nen: str = "auto",
) -> None:
    """Xoá chữ nổi có viền halo trực tiếp trên `anh` (in-place RGB uint8) mà KHÔNG làm nhòe hình chữ nhật:
    - Bảo toàn 100% nét vẽ nhân vật (vai, áo, khuôn mặt, tóc, quân bài mạt chược) nằm ngoài nét chữ.
    - Nền hạt screentone (`screentone_halo`): nhân bản đúng pha lưới hạt 4×4 (`py & 3, px & 3`) từ vùng screentone sạch.
    - Nền tia tốc độ (`dark_halo`): nối tiếp sọc tia tốc độ dọc từ phía trên và chuyển mượt (gradient fade) sang nền trắng/áo ở phía dưới.
    """
    import cv2

    x1, y1, x2, y2 = o
    H_full, W_full = anh.shape[:2]
    x1 = max(0, x1 - 6)
    y1 = max(0, y1 - 6)
    x2 = min(W_full, x2 + 6)
    y2 = min(H_full, y2 + 6)
    sh, sw = y2 - y1, x2 - x1
    if sh <= 4 or sw <= 4:
        return
    sub_rgb = anh[y1:y2, x1:x2].copy()
    sub = cv2.cvtColor(sub_rgb, cv2.COLOR_RGB2GRAY)
    blur3 = cv2.blur(sub, (3, 3))
    min3 = cv2.erode(sub, np.ones((3, 3), np.uint8))

    dark = (sub < 135).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(dark, connectivity=8)
    char_core = np.zeros_like(dark)
    for i in range(1, n):
        cx, cy, cw, ch, area = (int(v) for v in stats[i])
        if cw < 2 or cw > 175 or ch < 2 or ch > 27 or area < 3 or area > 2200:
            continue
        if cx <= 1 or cy <= 1 or cx + cw >= sw - 1 or cy + ch >= sh - 1:
            continue
        comp = (labels == i).astype(np.uint8)
        d1 = cv2.dilate(comp, np.ones((3, 3), np.uint8))
        d2 = cv2.dilate(comp, np.ones((7, 7), np.uint8))
        ring = (d2 > 0) & (d1 == 0) & (dark == 0)
        if ring.sum() >= 6 and float((sub[ring] >= 180).mean()) >= 0.72:
            char_core[comp > 0] = 255

    if kieu_nen == "auto":
        # Nếu trung vị vùng ngoài chữ nằm trong dải xám 135..220 và ít mảng đen đặc ở đỉnh -> screentone_halo
        top_med = float(np.median(sub[: max(4, sh // 4), :]))
        kieu_nen = "dark_halo" if top_med < 120 else "screentone_halo"

    if kieu_nen == "screentone_halo":
        bright_dots = (sub > 190).astype(np.uint8)
        nb, lb, sb, _ = cv2.connectedComponentsWithStats(bright_dots, connectivity=8)
        shadow_dots = np.zeros_like(dark)
        for i in range(1, nb):
            cx, cy, cw, ch, area = (int(v) for v in sb[i])
            if 3 <= cw <= 24 and 3 <= ch <= 12 and 6 <= area <= 180:
                comp = (lb == i).astype(np.uint8)
                ring = (cv2.dilate(comp, np.ones((5, 5), np.uint8)) > 0) & (comp == 0)
                if ring.sum() > 0 and float((sub[ring] < 80).mean()) >= 0.75:
                    shadow_dots[comp > 0] = 255

        max_halo_zone = (cv2.dilate(char_core, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (23, 23))) > 0) & (sub >= 150)
        halo_seed = cv2.dilate(char_core, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))) > 0
        near_core_11 = cv2.dilate(char_core, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))) > 0
        # Phát hiện mảng da trắng / quân bài trắng mở rộng của tranh gốc (ngăn cách bởi nét mực đen `dark`)
        # để không nở halo rộng 11px rồi dán nhầm screentone xám lên cánh tay trắng của nhân vật:
        open_white_cand = (sub >= 246) & (blur3 >= 248) & (dark == 0) & (char_core == 0)
        n_ow, l_ow, s_ow, _ = cv2.connectedComponentsWithStats(open_white_cand.astype(np.uint8), connectivity=4)
        vung_trang_tranh = np.zeros_like(char_core, dtype=bool)
        for i_ow in range(1, n_ow):
            ox, oy, ow, oh, oarea = (int(v) for v in s_ow[i_ow])
            if oarea < 95:
                continue
            comp_ow = l_ow == i_ow
            touches_b = ox <= 1 or oy <= 1 or (ox + ow) >= sw - 1 or (oy + oh) >= sh - 1
            if touches_b or int((comp_ow & (~near_core_11)).sum()) >= 42:
                vung_trang_tranh |= comp_ow

        white_cand = max_halo_zone & (~vung_trang_tranh) & ((min3 >= 220) | (blur3 >= 230) | (halo_seed & (sub >= 210)))
        nw, lw, _, _ = cv2.connectedComponentsWithStats(white_cand.astype(np.uint8), connectivity=8)
        halo_mask = np.zeros_like(char_core, dtype=bool)
        for i in range(1, nw):
            comp = lw == i
            if (comp & halo_seed).any():
                halo_mask |= comp
        # Phần nét chữ đè trực tiếp lên vùng da trắng / quân bài trắng được trả thẳng về nền trắng 255:
        core_on_white_skin = ((char_core > 0) | halo_seed) & (cv2.dilate(vung_trang_tranh.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0) & ((dark == 0) | (char_core > 0))
        sub_rgb[core_on_white_skin] = [255, 255, 255]
        mask = ((char_core > 0) | halo_mask) & (~core_on_white_skin)
        mask_dil = cv2.dilate(mask.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))) > 0
        mask = mask | (mask_dil & (sub >= 135) & (~vung_trang_tranh) & (dark == 0))
        inv = (~mask).astype(np.uint8)
        nh, lh, sh_stats, _ = cv2.connectedComponentsWithStats(inv, connectivity=4)
        for i in range(1, nh):
            cx, cy, cw, ch, area = (int(v) for v in sh_stats[i])
            if cx > 0 and cy > 0 and cx + cw < sw and cy + ch < sh and area <= 120:
                hole_m = lh == i
                if not (hole_m & ((dark > 0) & (char_core == 0))).any() and not (hole_m & vung_trang_tranh).any():
                    mask[hole_m] = True

        if shadow_dots.any():
            sd_mask = cv2.dilate(shadow_dots, np.ones((5, 5), np.uint8)) > 0
            sub_rgb[sd_mask] = [28, 28, 28]

        clean_donor = (~mask) & (min3 <= 224) & (blur3 >= 145) & (sub >= 115)
        clean_donor = cv2.erode(clean_donor.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
        ys, xs = np.where(mask)
        for py, px in zip(ys, xs):
            pha_y, pha_x = int(py) & 3, int(px) & 3
            best_d = 999999
            best_val = None
            for rad in range(4, 110, 4):
                y0_s, y1_s = max(0, int(py) - rad), min(sh, int(py) + rad + 1)
                x0_s, x1_s = max(0, int(px) - rad), min(sw, int(px) + rad + 1)
                for sy in range(y0_s + ((pha_y - y0_s) & 3), y1_s, 4):
                    for sx in range(x0_s + ((pha_x - x0_s) & 3), x1_s, 4):
                        if clean_donor[sy, sx]:
                            d2 = (sy - int(py)) ** 2 + (sx - int(px)) ** 2
                            if d2 < best_d:
                                best_d = d2
                                best_val = sub_rgb[sy, sx]
                if best_val is not None:
                    break
            if best_val is not None:
                sub_rgb[py, px] = best_val
    else:
        n_c, l_c, s_c, _ = cv2.connectedComponentsWithStats(char_core, connectivity=8)
        lower_letters = np.zeros_like(char_core)
        speedline_letters = np.zeros_like(char_core)
        for i in range(1, n_c):
            cx, cy, cw, ch, area = (int(v) for v in s_c[i])
            if cy >= sh * 0.58:
                lower_letters[l_c == i] = 255
            else:
                speedline_letters[l_c == i] = 255

        solid_black_hair = cv2.morphologyEx((sub < 50).astype(np.uint8), cv2.MORPH_OPEN, np.ones((9, 9), np.uint8)) > 0
        near_hair = cv2.dilate(solid_black_hair.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (17, 17))) > 0

        if lower_letters.any():
            ll_mask = cv2.dilate(lower_letters, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))) > 0
            ll_halo = (cv2.dilate(lower_letters, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))) > 0) & (sub >= 140)
            x_grid = np.arange(sw)[None, :]
            y_grid = np.arange(sh)[:, None]
            hair_overlap = (ll_mask | ll_halo) & near_hair & (y_grid < int(sh * 0.74)) & (x_grid >= int(sw * 0.58))
            sub_rgb[ll_mask & (~hair_overlap)] = [255, 255, 255]
            sub[ll_mask & (~hair_overlap)] = 255
            sub_rgb[hair_overlap] = [15, 15, 15]
            sub[hair_overlap] = 15

        if speedline_letters.any():
            near_sl = cv2.dilate(speedline_letters, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (23, 23))) > 0
            sl_halo = near_sl & (sub >= 135)
            cloud = (speedline_letters > 0) | sl_halo
            cloud = cv2.morphologyEx(cloud.astype(np.uint8), cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))) > 0
            cloud = cv2.dilate(cloud.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))) > 0
            inv_c = (~cloud).astype(np.uint8)
            nh, lh, sh_stats, _ = cv2.connectedComponentsWithStats(inv_c, connectivity=4)
            for i in range(1, nh):
                cx, cy, cw, ch, area = (int(v) for v in sh_stats[i])
                if cx > 0 and cy > 0 and cx + cw < sw and cy + ch < sh and area <= 250:
                    cloud[lh == i] = True

            ys, xs = np.where(cloud)
            cloud_y_max = int(ys.max()) if ys.size > 0 else sh
            for py, px in zip(ys, xs):
                tex_val = None
                for step in range(2, sh):
                    sy = int(py) - step
                    sx = (int(px) + int(round(step * 0.09))) % sw
                    if sy < 0:
                        break
                    if not cloud[sy, sx] and sub[sy, sx] < 210:
                        band_y = max(1, sy - ((int(py) - sy) % 16))
                        band_x = min(sw - 1, max(0, sx + int(round((sy - band_y) * 0.09))))
                        if not cloud[band_y, band_x]:
                            tex_val = sub_rgb[band_y, band_x].astype(np.float32)
                        else:
                            tex_val = sub_rgb[sy, sx].astype(np.float32)
                        break
                if tex_val is None:
                    tex_val = np.array([35.0, 35.0, 35.0], dtype=np.float32)
                dist_from_bot = cloud_y_max - int(py)
                if dist_from_bot < 28:
                    alpha = ((28.0 - dist_from_bot) / 28.0) ** 1.4
                    if near_hair[py, px] and int(px) >= int(sw * 0.62):
                        tex_val = tex_val * (1.0 - alpha) + 15.0 * alpha
                    else:
                        tex_val = tex_val * (1.0 - alpha) + 255.0 * alpha
                sub_rgb[py, px] = np.clip(tex_val, 0, 255).astype(np.uint8)

    anh[y1:y2, x1:x2] = sub_rgb
