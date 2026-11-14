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


def loc_nhieu_net_ve_khoi_seg_crop(
    gray: np.ndarray,
    seg_u8: np.ndarray,
    img_hw: tuple[int, int] | None = None,
) -> np.ndarray:
    """Loại bỏ nét vẽ khuôn mặt, mắt, lông mày và đường viền dài khỏi mặt nạ `seg` trong một ô cắt."""
    import cv2

    if gray.ndim == 3:
        gray = cv2.cvtColor(gray, cv2.COLOR_RGB2GRAY)
    sh, sw = seg_u8.shape[:2]
    if sh < 8 or sw < 8:
        return ((seg_u8 > 0).astype(np.uint8)) * 255
    seg_b = seg_u8 > 0
    orig_sum = int(np.count_nonzero(seg_b))
    if orig_sum == 0:
        return np.zeros((sh, sw), dtype=np.uint8)

    seg_clean = seg_b.copy()
    ref_dim = max(img_hw) if img_hw else max(sh, sw)
    max_glyph_h = max(26, round(ref_dim / 1024 * 40))
    max_art_span = max(42, round(ref_dim / 1024 * 64))

    # 1. Nét mực tối (bỏ qua mảng đen đặc lớn như tóc/áo dày >= 7px hoặc nhiễu nền lan toàn khung) chỉ chạm mép `seg` (`low_scov` / `no_halo_eye`):
    blk_eroded = cv2.erode((gray <= 32).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)), iterations=1)
    nl_b, lbl_b, st_b, _ = cv2.connectedComponentsWithStats(blk_eroded, connectivity=8)
    large_blk = np.zeros((sh, sw), dtype=np.uint8)
    for bid in range(1, nl_b):
        if int(st_b[bid, cv2.CC_STAT_AREA]) >= 120:
            large_blk[lbl_b == bid] = 1
    near_large_blk = cv2.dilate(large_blk, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)), iterations=1) > 0
    dark = ((gray <= 165) & (~near_large_blk)).astype(np.uint8)
    nl_d, lbl_d, st_d, _ = cv2.connectedComponentsWithStats(dark, connectivity=8)
    max_comp_area = int(0.35 * sh * sw)
    k7_ring = np.ones((7, 7), np.uint8)
    for did in range(1, nl_d):
        area = int(st_d[did, cv2.CC_STAT_AREA])
        if area < 6 or area > max_comp_area:
            continue
        dx = int(st_d[did, cv2.CC_STAT_LEFT])
        dy = int(st_d[did, cv2.CC_STAT_TOP])
        dw = int(st_d[did, cv2.CC_STAT_WIDTH])
        dh = int(st_d[did, cv2.CC_STAT_HEIGHT])
        comp = lbl_d == did
        inter = int(np.count_nonzero(seg_clean & comp))
        if inter == 0:
            continue
        out_px = area - inter
        seg_cov = inter / float(area)
        touches_edge = dx <= 1 or dy <= 1 or (dx + dw) >= sw - 1 or (dy + dh) >= sh - 1
        if (
            seg_cov < 0.24
            or (out_px >= 10 and seg_cov < 0.80)
            or (out_px >= 5 and seg_cov < 0.78 and (dw >= 2.2 * dh or dh >= 2.2 * dw or touches_edge))
            or (touches_edge and seg_cov < 0.68 and (area >= 12 or max(dw, dh) >= 10))
        ):
            seg_clean[comp] = False
        elif dw >= 1.7 * dh and dh <= 9 and area <= 95:
            ly0, ly1 = max(0, dy - 4), min(sh, dy + dh + 4)
            lx0, lx1 = max(0, dx - 4), min(sw, dx + dw + 4)
            g_loc = gray[ly0:ly1, lx0:lx1]
            c_loc = comp[ly0:ly1, lx0:lx1]
            g_bg = g_loc[~c_loc]
            comp_u8 = comp.astype(np.uint8)
            ring = (cv2.dilate(comp_u8, k7_ring) > 0) & (~comp) & (dark == 0)
            if (
                g_bg.size >= 16
                and float((g_bg <= 35).mean()) < 0.15
                and float(np.median(g_bg)) >= 215.0
                and int(ring.sum()) >= 8
                and float((gray[ring] >= 245).mean()) < 0.28
            ):
                seg_clean[comp] = False

    # 2. Cụm `seg` dạng nét viền dài/cao mảnh (`tall_contour`) hoặc nhiễu nằm ngoài chữ:
    nl_s, lbl_s, st_s, _ = cv2.connectedComponentsWithStats(seg_clean.astype(np.uint8), connectivity=8)
    for sid in range(1, nl_s):
        sw_c = int(st_s[sid, cv2.CC_STAT_WIDTH])
        sh_c = int(st_s[sid, cv2.CC_STAT_HEIGHT])
        sa = int(st_s[sid, cv2.CC_STAT_AREA])
        fill_ratio = sa / max(1.0, float(sw_c * sh_c))
        if (sh_c > max_glyph_h and (fill_ratio < 0.40 or sw_c <= 5) and sw_c <= 0.70 * sh_c) or (
            max(sw_c, sh_c) > max_art_span and fill_ratio < 0.28
        ):
            seg_clean[lbl_s == sid] = False

    if int(np.count_nonzero(seg_clean)) < max(8, int(0.35 * orig_sum)):
        return (seg_b.astype(np.uint8)) * 255
    return (seg_clean.astype(np.uint8)) * 255


def _bao_ve_net_ve_va_da_trang_trong_o(
    anh_o: np.ndarray,
    seg_o: np.ndarray,
    net_no_o: np.ndarray,
) -> np.ndarray:
    """Giới hạn mặt nạ nở `net_no_o` trong ô `anh_o` để bảo toàn 100% nét vẽ nhân vật liên thông từ biên
    và nét vẽ nội bộ (mắt, lông mày, ngón tay, xương hàm) cùng nền da/nền trắng quanh chữ nổi.
    """
    import cv2

    sh, sw = seg_o.shape[:2]
    if sh < 8 or sw < 8:
        return net_no_o
    gray = cv2.cvtColor(anh_o, cv2.COLOR_RGB2GRAY) if anh_o.ndim == 3 else anh_o
    if anh_o.ndim == 3:
        sac = anh_o.max(axis=2).astype(np.int16) - anh_o.min(axis=2).astype(np.int16)
    else:
        sac = np.zeros_like(gray, dtype=np.int16)
    seg_clean = loc_nhieu_net_ve_khoi_seg_crop(gray, seg_o)
    k3 = np.ones((3, 3), np.uint8)
    seg_pos = seg_clean > 0
    core = (seg_pos & (gray <= 175)).astype(np.uint8)
    if int(core.sum()) < 4:
        core = seg_pos.astype(np.uint8)
    if int(core.sum()) == 0:
        return net_no_o

    is_halo_on_black = (
        float((gray <= 32).mean()) >= 0.25
        and float((seg_pos & (gray >= 175)).mean()) >= 0.03
    )
    la_chu_den = (
        (not is_halo_on_black)
        and bool(seg_pos.any())
        and float((gray[seg_pos] <= 170).mean()) >= 0.28
    )

    # 1. Nét vẽ đen ngoài vùng lõi chữ (biên ô + nét nội bộ với chữ mực đen):
    nguong_net = 155 if la_chu_den else 135
    dark_line = ((gray <= nguong_net) & (core == 0)).astype(np.uint8)
    nl_d, lbl_d, st_d, _ = cv2.connectedComponentsWithStats(dark_line, connectivity=8)
    art_block = np.zeros((sh, sw), dtype=bool)
    max_art_comp = int(0.35 * sh * sw)
    for did in range(1, nl_d):
        dx, dy = int(st_d[did, cv2.CC_STAT_LEFT]), int(st_d[did, cv2.CC_STAT_TOP])
        dw, dh = int(st_d[did, cv2.CC_STAT_WIDTH]), int(st_d[did, cv2.CC_STAT_HEIGHT])
        da = int(st_d[did, cv2.CC_STAT_AREA])
        if da > max_art_comp:
            continue
        touches_edge = dx <= 1 or dy <= 1 or dx + dw >= sw - 1 or dy + dh >= sh - 1
        if (touches_edge and (da >= 15 or max(dw, dh) >= 10)) or (
            la_chu_den and da >= 10 and max(dw, dh) >= 7
        ):
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
    if la_chu_den:
        halo_zone = cv2.dilate(core, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)), iterations=1) > 0
        ket = net_no_o & ((core > 0) | ((d1_core | (halo_zone & (gray > 175))) & (~art_block)))
    else:
        ket = net_no_o & (~art_block)
    ket = np.where(open_white, cho_phep_tren_trang, ket)

    # Trường hợp chữ viền sáng trên mảng mực đen đặc (#18): tách nền trắng mở thật bên ngoài seg_clean
    def _tim_bien_panel_ngang(g_arr: np.ndarray, s_arr: np.ndarray) -> np.ndarray:
        h_a, w_a = g_arr.shape
        out = np.zeros((h_a, w_a), dtype=bool)
        if h_a < 28 or w_a < 28:
            return out
        b_span = max(6, int(h_a * 0.28))
        for edge_rows, g_bounds in (
            (range(1, min(h_a - 2, b_span)), lambda r: (max(0, r - 8), r)),
            (range(h_a - 2, max(1, h_a - 1 - b_span), -1), lambda r: (min(h_a, r + 1), min(h_a, r + 9))),
        ):
            for py_b in edge_rows:
                if float((g_arr[py_b] <= 105).mean()) < 0.52:
                    continue
                if float(g_arr[py_b, :4].min()) > 105 and float(g_arr[py_b, -4:].min()) > 105:
                    continue
                g0, g1 = g_bounds(py_b)
                if g1 <= g0:
                    continue
                has_gutter = bool(((g_arr[g0:g1] >= 225) & (s_arr[g0:g1] <= 26)).mean(axis=1).max() >= 0.72)
                if has_gutter:
                    y_lo = max(0, py_b - 1)
                    y_hi = min(h_a, py_b + 2)
                    out[y_lo:y_hi, :] |= g_arr[y_lo:y_hi, :] <= 115
        return out

    panel_border_mask = _tim_bien_panel_ngang(gray, sac) | _tim_bien_panel_ngang(gray.T, sac.T).T

    if is_halo_on_black:
        k7 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        w_open_seed = cv2.morphologyEx(
            ((gray >= 238) & (sac <= 26) & (~seg_pos)).astype(np.uint8),
            cv2.MORPH_OPEN,
            k7,
        )
        true_open_white = (
            (cv2.dilate(w_open_seed, k3, iterations=1) > 0)
            & (gray >= 235)
            & (sac <= 26)
            & (~art_block)
        )
        seg_dil = cv2.dilate(seg_pos.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))) > 0
        seg_3 = cv2.dilate(seg_pos.astype(np.uint8), k3, iterations=1) > 0
        # Bảo vệ mảng tóc / nền đen đặc nối ra ngoài vùng chữ (`p1 #7`) để viền chữ không liếm mất ngọn tóc
        hair_cand = (gray <= 52) & (~seg_pos)
        nl_hc, lbl_hc, st_hc, _ = cv2.connectedComponentsWithStats(hair_cand.astype(np.uint8), connectivity=8)
        solid_hair_out = np.zeros_like(seg_pos, dtype=bool)
        for hcid in range(1, nl_hc):
            area_h = int(st_hc[hcid, cv2.CC_STAT_AREA])
            if area_h < 10:
                continue
            comp_h = lbl_hc == hcid
            if bool((comp_h & (~seg_dil)).any()) or area_h >= 120:
                solid_hair_out |= comp_h
        if solid_hair_out.any():
            hair_edge = (cv2.dilate(solid_hair_out.astype(np.uint8), k3, iterations=1) > 0) & (~seg_pos) & (gray <= 95) & (core == 0)
            solid_hair_out |= hair_edge
        halo_w = (seg_dil & (gray >= 110) & (~true_open_white)) | (
            seg_dil & near_solid_black & (gray >= 28) & (~true_open_white) & (~solid_hair_out)
        )
        dark_in_seg = (seg_dil & (gray < 110) & (~solid_hair_out)).astype(np.uint8)
        nl_dc, lbl_dc, st_dc, _ = cv2.connectedComponentsWithStats(dark_in_seg, connectivity=8)
        enclosed_core = np.zeros_like(seg_dil, dtype=bool)
        for dc_id in range(1, nl_dc):
            da_c = int(st_dc[dc_id, cv2.CC_STAT_AREA])
            if da_c < 1 or da_c > 950:
                continue
            comp_dc = (lbl_dc == dc_id).astype(np.uint8)
            dil_dc = cv2.dilate(comp_dc, k3, iterations=1) > 0
            cham_ngoai_seg = bool((dil_dc & (~seg_dil)).any())
            ring_dc = dil_dc & (comp_dc == 0)
            ty_le_halo = float(halo_w[ring_dc].mean()) if ring_dc.any() else 0.0
            if (not cham_ngoai_seg) or ty_le_halo >= 0.55:
                enclosed_core |= comp_dc > 0
        mask_on_black = cv2.dilate((halo_w | enclosed_core).astype(np.uint8), k3, iterations=1) > 0
        near_open_w = cv2.dilate(true_open_white.astype(np.uint8), np.ones((5, 5), np.uint8), iterations=1) > 0
        ink_on_open_w = cv2.dilate(
            (seg_3 & (gray < 235) & near_open_w & (~solid_hair_out)).astype(np.uint8), k3, iterations=1
        ) > 0
        return (
            (mask_on_black | ink_on_open_w)
            & (~true_open_white)
            & (~solid_hair_out)
            & (~panel_border_mask)
            & (~(art_block & (~near_solid_black)))
        )

    # Tách đảo viền sáng (halo sticker) nằm gọn trên nền tối/sọc chéo (vd dấu `...` cuối câu "was...")
    bg_close = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)))
    bright_patch = ((bg_close >= 232) & (gray >= 195) & (sac <= 30) & (~near_solid_black)).astype(np.uint8)
    nl_wp, lbl_wp, st_wp, _ = cv2.connectedComponentsWithStats(bright_patch, connectivity=8)
    core_dil9 = cv2.dilate(core, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)), iterations=1) > 0
    k_ring9 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    halo_island = np.zeros((sh, sw), dtype=bool)
    max_island_area = int(0.42 * sh * sw)
    for wid in range(1, nl_wp):
        wa = int(st_wp[wid, cv2.CC_STAT_AREA])
        if wa < 12 or wa > max_island_area:
            continue
        wx = int(st_wp[wid, cv2.CC_STAT_LEFT])
        wy = int(st_wp[wid, cv2.CC_STAT_TOP])
        ww = int(st_wp[wid, cv2.CC_STAT_WIDTH])
        wh = int(st_wp[wid, cv2.CC_STAT_HEIGHT])
        if (wx <= 1 and (wx + ww) >= sw - 1) or (wy <= 1 and (wy + wh) >= sh - 1):
            continue
        wc = lbl_wp == wid
        if not np.any(wc & core_dil9):
            continue
        w_ring = (cv2.dilate(wc.astype(np.uint8), k_ring9, iterations=1) > 0) & (~wc) & (core == 0)
        if int(w_ring.sum()) >= 12 and float(np.median(gray[w_ring])) < 195.0:
            halo_island |= wc

    halo_erase = np.zeros((sh, sw), dtype=bool)
    if halo_island.any():
        halo_closed = cv2.morphologyEx(halo_island.astype(np.uint8), cv2.MORPH_CLOSE, k_ring9) > 0
        halo_fringe = (cv2.dilate(halo_closed.astype(np.uint8), k3, iterations=1) > 0) & (gray >= 125) & (~art_block)
        halo_erase = halo_closed | halo_fringe
        ket = ket & (~open_white)
        ket = np.where(open_white & (~halo_erase), cho_phep_tren_trang, ket)

    # Giữ nền giấy trắng / da trắng sạch giữa các dòng chữ: không đục lỗ lớn qua nền trắng sạch
    already_clean_white = (
        (bg_close >= 238)
        & (gray >= 240)
        & (sac <= 26)
        & (~near_solid_black)
        & (~art_block)
        & (~halo_erase)
    )
    ink_on_white = ((gray < 240) | (sac > 26)) & seg_pos
    ink_fringe = (cv2.dilate(ink_on_white.astype(np.uint8), k3, iterations=1) > 0) & (gray < 248) & (~art_block)
    ket = np.where(already_clean_white, ink_on_white | ink_fringe, ket)
    if halo_erase.any():
        ket = ket | halo_erase
    return ket & (~panel_border_mask)


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
    max_ch_glyph = max(27, round(max(cao, rong) / 1024 * 32))
    max_cw_glyph = max(175, round(max(cao, rong) / 1024 * 175))
    char_core = np.zeros_like(den_cc)
    for i_cc in range(1, n_cc):
        cx_c, cy_c, cw_c, ch_c, area_c = (int(v) for v in stats_cc[i_cc])
        if cw_c < 2 or cw_c > max_cw_glyph or ch_c < 2 or ch_c > max_ch_glyph or area_c < 3 or area_c > 2200:
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
        k_halo_nho = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        m_halo_nho = (char_core > 0) | ((cv2.dilate(char_core, k_halo_nho) > 0) & (sang >= 175))
        if m_halo_nho.mean() <= TI_LE_MAT_NA_TOI_DA:
            return m_halo_nho

    mau_sac_dam = sac >= 48
    k_sat = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 3, 2 * r + 3))
    if trang.mean() >= TI_LE_VIEN_TOI_THIEU and (den.mean() >= TI_LE_VIEN_TOI_THIEU or mau_sac_dam.mean() >= TI_LE_VIEN_TOI_THIEU):
        trang_no = cv2.dilate(trang.astype(np.uint8), k_sat) > 0
        den_no = cv2.dilate(den.astype(np.uint8), k_sat) > 0
        # Chỉ giữ các điểm ruột (đen hoặc màu đậm) nằm sát viền trắng VÀ các điểm viền trắng/đen nằm sát nhau
        loi_co_vien_trang = (den | mau_sac_dam) & trang_no
        vien_trang_co_loi = trang & (cv2.dilate(loi_co_vien_trang.astype(np.uint8), k_sat) > 0)
        loi_sang_co_vien_den = trang & den_no
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
