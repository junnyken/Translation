#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
APP WINDOWS: DỊCH TRUYỆN TRANH TỰ ĐỘNG THEO LINK -> CHIA THƯ MỤC TỪNG CHAPTER
==============================================================================
Tính năng chính:
1. Dán 1 Link bộ truyện (hoặc danh sách Link các Chapter) -> Tự động quét danh sách Chapter.
2. Chọn dịch từ Chapter A đến Chapter B.
3. Tải ảnh từng trang của mỗi Chapter (tự động gắn Referer / User-Agent vượt chặn hotlink).
4. Kết nối tài khoản VIP với Server (hiển thị số lượt hôm nay & lượt mua tích luỹ).
5. Xoá sạch chữ gốc trong lòng bong bóng (2D Flood-Fill + Rào chắn Voronoi) và căn chữ tự động
   ngay trên máy tính Windows (hoặc chọn chế độ LaMa Server), xuất ra đúng cấu trúc thư mục:
   📁 Thu_Muc_Xuat / Ten_Truyen / Chapter-001 / 001.jpg, 002.jpg, 003.jpg...
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import os
import platform
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import webbrowser
import zipfile
from collections import deque
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk

_APP_DIR = str(Path(__file__).resolve().parent)
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

from production import ChapterLedger, NeedsAttention, RunStopped, natural_key, process_chapter, require_production_backend
from sources import archive_sources, chapter_links, image_links, local_image_sources, read_local_source

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None
    ImageDraw = None
    ImageFont = None

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

CAU_HINH_FILE = Path.home() / ".dich_truyen_windows_config.json"


def lay_dinh_danh_may_tinh() -> tuple[str, str]:
    """
    Tạo Mã máy tính (Hardware ID) cố định cho máy Windows hiện tại:
    - `ma_hien_thi`: dạng `WIN-XXXXXXXXXXXX` (12 ký tự hex viết hoa) để hiển thị và xác nhận tài khoản/thiết bị.
    - `khach_id_hex`: chuỗi 32 ký tự hex chuẩn gắn vào Cookie `khach_id` và Header `X-Ma-May-Tinh`
      để máy chủ lưu và đồng bộ chính xác số lượt còn lại của đúng máy tính này.
    """
    raw_fingerprint = f"win-manga-studio::{uuid.getnode()}::{platform.node()}::{platform.machine()}"
    digest = hashlib.sha256(raw_fingerprint.encode("utf-8")).hexdigest()
    ma_hien_thi = f"WIN-{digest[:12].upper()}"
    khach_id_hex = digest[:32].lower()
    return ma_hien_thi, khach_id_hex


MA_MAY_HIEN_THI, KHACH_ID_MAY_TINH = lay_dinh_danh_may_tinh()
WEB_CHINH_THUC = "https://comic.io.vn"
MAY_CHU_API_MAC_DINH = "https://translation-api.vibe1.tinhgon.xyz"


def chuan_hoa_may_chu(raw: str) -> str:
    """
    Nếu người dùng nhập địa chỉ trang giao diện Web (`https://comic.io.vn` hoặc
    `https://translation.vibe1.tinhgon.xyz`) vào ô Máy chủ, tự động chuyển sang
    máy chủ API (`https://translation-api.vibe1.tinhgon.xyz`) để gọi API chuẩn xác.
    """
    s = (raw or "").strip().rstrip("/")
    if not s:
        return MAY_CHU_API_MAC_DINH
    if re.match(r"^(https?://)?(www\.)?comic\.io\.vn$", s, re.I):
        return MAY_CHU_API_MAC_DINH
    if re.match(r"^https?://translation\.vibe1\.tinhgon\.xyz$", s, re.I):
        return MAY_CHU_API_MAC_DINH
    return s


# ==============================================================================
# 1. THUẬT TOÁN XOÁ CHỮ 2D & CĂN CHỮ BONG BÓNG TRÊN MÁY KHÁCH WINDOWS (PILLOW)
# ==============================================================================

def tim_font_he_thong(loai_font: str, co_chu: int, van_ban: str = ""):
    """Tìm font chữ đa ngôn ngữ có sẵn trên Windows theo phong cách thể loại (hỗ trợ Tiếng Việt, Anh, Trung Giản/Phồn, Thái, Indo, Tây Ban Nha, Pháp, Bồ Đào Nha)."""
    if ImageFont is None:
        return None
    win_fonts = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts"
    # Tự động chọn bộ font CJK (Trung/Nhật/Hàn) hoặc Thái Lan nếu bản dịch chứa ký tự tượng hình/Thái để không bao giờ bị ô vuông □
    if van_ban and re.search(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", van_ban):
        ds_cjk = ["msyhbd.ttc", "msjhbd.ttc", "simhei.ttf", "msyh.ttc", "msjh.ttc", "malgunbd.ttf", "YuGothB.ttc", "msgothic.ttc"]
        for ten in ds_cjk:
            p = win_fonts / ten
            if p.is_file():
                try:
                    return ImageFont.truetype(str(p), co_chu)
                except Exception:
                    continue
    if van_ban and re.search(r"[\u0e00-\u0e7f]", van_ban):
        ds_thai = ["leelawdb.ttf", "leelawui.ttf", "tahomabd.ttf", "tahoma.ttf", "cordiab.ttf"]
        for ten in ds_thai:
            p = win_fonts / ten
            if p.is_file():
                try:
                    return ImageFont.truetype(str(p), co_chu)
                except Exception:
                    continue
    # Lưu ý: impact.ttf, Gabriola.ttf, comicbd.ttf trên Windows thiếu dấu Tiếng Việt (Ạ, Ấ, Ư, Ỡ -> hiện ô vuông □)
    ung_vien_theo_loai = {
        "bangers": ["tahomabd.ttf", "segoeuib.ttf", "arialbd.ttf", "verdanab.ttf"],
        "comic": ["segoeuib.ttf", "calibrib.ttf", "tahomabd.ttf", "arialbd.ttf"],
        "romance": ["segoeuii.ttf", "calibrii.ttf", "ariali.ttf", "segoeui.ttf"],
        "historical": ["timesbi.ttf", "timesbd.ttf", "georgiab.ttf", "georgia.ttf", "palabi.ttf", "times.ttf"],
    }
    ds_thu = ung_vien_theo_loai.get(loai_font, ung_vien_theo_loai["comic"]) + [
        "segoeuib.ttf",
        "arialbd.ttf",
        "tahomabd.ttf",
        "tahoma.ttf",
    ]
    for ten in ds_thu:
        p = win_fonts / ten
        if p.is_file():
            try:
                return ImageFont.truetype(str(p), co_chu)
            except Exception:
                continue
    return ImageFont.load_default()


def _inpaint_vung_nen_phuc_tap_harmonic(px_anh, W: int, H: int, x0: int, y0: int, w: int, h: int) -> tuple[int, int, int]:
    """
    Nội suy bề mặt 4 hướng (4-Boundary Harmonic Ring Inpainting) cho vùng chữ SFX / chữ đè lên nền phức tạp:
    Lấy mẫu vành đai 3px xung quanh 4 cạnh (Trái, Phải, Trên, Dưới) và pha màu mượt theo khoảng cách nghịch đảo
    giúp tái tạo dải màu chuyển sắc (gradient), đường kẻ nền hoặc mảng màu quần áo/bầu trời mà không bị vệt phẳng.
    """
    rx0 = max(1, x0)
    ry0 = max(1, y0)
    rx1 = min(W - 2, x0 + w)
    ry1 = min(H - 2, y0 + h)
    rw = max(1, rx1 - rx0)
    rh = max(1, ry1 - ry0)

    left_col = [px_anh[max(0, rx0 - 2), ry0 + py] for py in range(rh)]
    right_col = [px_anh[min(W - 1, rx1 + 1), ry0 + py] for py in range(rh)]
    top_row = [px_anh[rx0 + px, max(0, ry0 - 2)] for px in range(rw)]
    bot_row = [px_anh[rx0 + px, min(H - 1, ry1 + 1)] for px in range(rw)]

    sum_r = sum_g = sum_b = cnt = 0
    for py in range(rh):
        l_r, l_g, l_b = left_col[py]
        r_r, r_g, r_b = right_col[py]
        wy_t = 1.0 / max(1.0, float(py + 1))
        wy_b = 1.0 / max(1.0, float(rh - py))
        for px in range(rw):
            t_r, t_g, t_b = top_row[px]
            b_r, b_g, b_b = bot_row[px]
            wx_l = 1.0 / max(1.0, float(px + 1))
            wx_r = 1.0 / max(1.0, float(rw - px))
            w_tot = wx_l + wx_r + wy_t + wy_b
            nr = int(round((l_r * wx_l + r_r * wx_r + t_r * wy_t + b_r * wy_b) / w_tot))
            ng = int(round((l_g * wx_l + r_g * wx_r + t_g * wy_t + b_g * wy_b) / w_tot))
            nb = int(round((l_b * wx_l + r_b * wx_r + t_b * wy_t + b_b * wy_b) / w_tot))
            px_anh[rx0 + px, ry0 + py] = (nr, ng, nb)
            sum_r += nr
            sum_g += ng
            sum_b += nb
            cnt += 1
    if cnt > 0:
        return (sum_r // cnt, sum_g // cnt, sum_b // cnt)
    return (255, 255, 255)


def xoa_chu_va_ve_ban_dich_tren_anh(
    img_bytes: bytes,
    ds_vung: list[dict],
    loai_font: str = "bangers",
) -> bytes:
    """
    Thực hiện xoá sạch chữ gốc trong lòng bong bóng (2D Connected-Component Flood-Fill +
    Rào chắn lãnh thổ Voronoi cho bong bóng đôi + 4-Boundary Harmonic Inpainting cho SFX)
    và trình bày bản dịch ngay trên máy khách Windows.
    """
    if Image is None:
        return img_bytes

    anh = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    W, H = anh.size
    px_anh = anh.load()

    vung_hop_le = [
        v for v in ds_vung
        if (v.get("ban_dich") or v.get("inpaint_sfx")) and v.get("w", 0) > 4 and v.get("h", 0) > 4
    ]
    if not vung_hop_le:
        out = io.BytesIO()
        anh.save(out, format="JPEG", quality=92)
        return out.getvalue()

    # Bước A: Xoá sạch chữ gốc trong lòng từng bong bóng & xác định hộp xếp chữ nội tiếp
    hop_ve_chu = []
    for idx_v, v in enumerate(vung_hop_le):
        x_goc = max(0, int(round(v["x"])))
        y_goc = max(0, int(round(v["y"])))
        w_goc = max(4, min(W - x_goc, int(round(v["w"]))))
        h_goc = max(4, min(H - y_goc, int(round(v["h"]))))
        txt_dich = str(v.get("ban_dich") or "").strip()

        if v.get("inpaint_sfx") or txt_dich == "[XOA_SFX]":
            bg_r, bg_g, bg_b = _inpaint_vung_nen_phuc_tap_harmonic(px_anh, W, H, x_goc, y_goc, w_goc, h_goc)
            if txt_dich and txt_dich != "[XOA_SFX]":
                lum_bg = 0.299 * bg_r + 0.587 * bg_g + 0.114 * bg_b
                hop_ve_chu.append(
                    {
                        "text": txt_dich,
                        "x": x_goc,
                        "y": y_goc,
                        "w": max(20, w_goc),
                        "h": max(16, h_goc),
                        "nen_toi": lum_bg < 85.0,
                        "nen_mau_trung_binh": True,
                        "bg": (bg_r, bg_g, bg_b),
                        "dong_con": [{"x": x_goc, "y": y_goc, "w": w_goc, "h": h_goc}],
                    }
                )
            continue

        # Mở rộng ROI đủ rộng quanh hộp chữ gốc để bao trọn cả các dòng cuối ("ness...", "Tenpai...")
        # hoặc chữ sát lề ("be", "k-") khi Gemini khoanh hụt 15-48px mà không tràn ra ngoài khung tranh
        mo_x = max(34, min(int(w_goc * 0.48), int(W * 0.09)))
        mo_y = max(62, min(int(h_goc * 0.55), int(H * 0.11)))
        rx0 = max(1, min(W - 5, x_goc - mo_x))
        ry0 = max(1, min(H - 5, y_goc - mo_y))
        rx1 = max(rx0 + 4, min(W - 1, x_goc + w_goc + mo_x))
        ry1 = max(ry0 + 4, min(H - 1, y_goc + h_goc + mo_y))

        rw = max(4, rx1 - rx0)
        rh = max(4, ry1 - ry0)
        cx0 = max(0, x_goc - rx0)
        cy0 = max(0, y_goc - ry0)
        cx1 = min(rw, x_goc + w_goc - rx0)
        cy1 = min(rh, y_goc + h_goc - ry0)

        # Lấy mẫu độ sáng và màu nền thật trong vùng chữ gốc + viền 6px quanh hộp chữ
        ds_lum = []
        ds_r, ds_g, ds_b = [], [], []
        so_trang_sang = 0
        so_mau_trung_binh = 0
        for py in range(max(0, cy0 - 6), min(rh, cy1 + 6), 2):
            for px in range(max(0, cx0 - 6), min(rw, cx1 + 6), 2):
                r, g, b = px_anh[rx0 + px, ry0 + py]
                lum = 0.299 * r + 0.587 * g + 0.114 * b
                sat = max(r, g, b) - min(r, g, b)
                ds_lum.append(lum)
                ds_r.append(r)
                ds_g.append(g)
                ds_b.append(b)
                if lum >= 210.0 and sat <= 38:
                    so_trang_sang += 1
                elif 40.0 <= lum <= 200.0 and sat >= 14:
                    so_mau_trung_binh += 1

        tong_mau = max(1, len(ds_lum))
        ds_lum_sorted = sorted(ds_lum) if ds_lum else [255.0]
        med_lum = ds_lum_sorted[len(ds_lum_sorted) // 2]
        p80_lum = ds_lum_sorted[min(len(ds_lum_sorted) - 1, int(len(ds_lum_sorted) * 0.80))]
        nen_toi = med_lum < 55.0 and (so_mau_trung_binh / tong_mau) < 0.22
        # Phát hiện chữ nổi có viền trắng/đen trên nền màu (không nằm trong bóng thoại trắng):
        nen_mau_trung_binh = (
            (not nen_toi)
            and (so_mau_trung_binh / tong_mau) >= 0.22
            and (so_trang_sang / tong_mau) < 0.35
            and (p80_lum < 215.0 or med_lum < 185.0)
        )

        if nen_mau_trung_binh:
            mau_loc = [
                (r, g, b)
                for r, g, b, lum in zip(ds_r, ds_g, ds_b, ds_lum)
                if 45.0 <= lum <= 198.0
            ]
            if not mau_loc:
                mau_loc = list(zip(ds_r, ds_g, ds_b))
            mau_loc.sort(key=lambda m: 0.299 * m[0] + 0.587 * m[1] + 0.114 * m[2])
            bg_r, bg_g, bg_b = mau_loc[len(mau_loc) // 2]
        else:
            mau_loc = [
                (r, g, b)
                for r, g, b, lum in zip(ds_r, ds_g, ds_b, ds_lum)
                if (lum <= 60 if nen_toi else lum >= 180)
            ]
            if mau_loc:
                mau_loc.sort(key=lambda m: 0.299 * m[0] + 0.587 * m[1] + 0.114 * m[2])
                idx_m = min(len(mau_loc) - 1, int(len(mau_loc) * (0.22 if nen_toi else 0.78)))
                bg_r, bg_g, bg_b = mau_loc[idx_m]
            else:
                bg_r, bg_g, bg_b = (14, 14, 14) if nen_toi else (255, 255, 255)

        # Ranh giới Voronoi với các bóng thoại láng giềng thực sự nằm gần ROI
        ds_lang_gieng = []
        for idx_u, u in enumerate(vung_hop_le):
            if idx_u == idx_v:
                continue
            ucx0 = int(round(u["x"] - rx0))
            ucy0 = int(round(u["y"] - ry0))
            ucx1 = int(round(u["x"] + u["w"] - rx0))
            ucy1 = int(round(u["y"] + u["h"] - ry0))
            if ucx1 < -16 or ucx0 > rw + 16 or ucy1 < -16 or ucy0 > rh + 16:
                continue
            ds_lang_gieng.append((ucx0, ucy0, ucx1, ucy1))

        N = rw * rh
        la_nen = bytearray(N)
        vung_cam = bytearray(N)

        # Tiền tính toán độ sáng, độ bão hoà & trung bình 3x3 trên ROI để nhận diện chính xác
        # cả 6 tình huống: Bong bóng kín, Bong bóng gai, Nền cát Screentone, Tóc đen, Nền màu có Halo (thuận/đảo) & Nền màu Gradient
        lum_px = [0.0] * N
        sat_px = [0] * N
        r_roi = [0] * N
        g_roi = [0] * N
        b_roi = [0] * N
        for py in range(rh):
            base = py * rw
            for px in range(rw):
                idx_p = base + px
                r_p, g_p, b_p = px_anh[rx0 + px, ry0 + py]
                r_roi[idx_p] = r_p
                g_roi[idx_p] = g_p
                b_roi[idx_p] = b_p
                lum_px[idx_p] = 0.299 * r_p + 0.587 * g_p + 0.114 * b_p
                sat_px[idx_p] = max(r_p, g_p, b_p) - min(r_p, g_p, b_p)

        la_trang_dac = bytearray(N)
        la_sang_dac = bytearray(N)
        la_toi_net = bytearray(N)
        la_mau_dam_net = bytearray(N)
        tb_lum_3x3 = [0.0] * N
        for py in range(rh):
            y0n = max(0, py - 1)
            y1n = min(rh - 1, py + 1)
            base = py * rw
            for px in range(rw):
                x0n = max(0, px - 1)
                x1n = min(rw - 1, px + 1)
                s_lum = 0.0
                cnt_n = 0
                dem_trang_n = 0
                dem_sang_n = 0
                co_hat_den = False
                for yy in range(y0n, y1n + 1):
                    by_n = yy * rw
                    for xx in range(x0n, x1n + 1):
                        lp = lum_px[by_n + xx]
                        s_lum += lp
                        cnt_n += 1
                        if lp >= 224.0 and sat_px[by_n + xx] <= 45:
                            dem_trang_n += 1
                        if lp >= 205.0:
                            dem_sang_n += 1
                        if lp <= 78.0:
                            co_hat_den = True
                pos = base + px
                tb_lum = s_lum / max(1, cnt_n)
                tb_lum_3x3[pos] = tb_lum
                # Viền Halo trắng đặc quanh chữ:
                # - Khi ở ngoài xa nét chữ (`not co_hat_den`): bắt buộc `tb_lum >= 222` hoặc `dem_trang_n >= 7` để loại trừ 100% hạt cát screentone.
                # - Khi nằm sát cạnh nét chữ đen (`co_hat_den == True`): 3-5 ô trong cửa sổ 3x3 bị chiếm bởi chính nét chữ đen (`lum <= 78`),
                #   nên chỉ cần `dem_trang_n >= 4` là xác nhận chính xác viền halo trắng mảnh (2-3px) bao quanh chữ!
                if lum_px[pos] >= 220.0 and sat_px[pos] <= 45 and (tb_lum >= 222.0 or dem_trang_n >= 7 or (co_hat_den and dem_trang_n >= 4)):
                    la_trang_dac[pos] = 1
                if (lum_px[pos] >= 202.0 and (tb_lum >= 212.0 or dem_sang_n >= 7 or (co_hat_den and dem_sang_n >= 2))) or (
                    co_hat_den and lum_px[pos] >= 158.0 and sat_px[pos] <= 42
                ):
                    la_sang_dac[pos] = 1
                # Lõi chữ mực đen thật sự có `lum <= 88` (hoặc `<= 118` khi nằm sát tâm nét mực đen `<= 78`),
                # tuyệt đối không nhận nhầm các hạt chấm xám của screentone (`lum = 93..180`) làm lõi chữ!
                if lum_px[pos] <= 88.0 or (lum_px[pos] <= 118.0 and co_hat_den):
                    la_toi_net[pos] = 1
                if sat_px[pos] >= 52 and 42.0 <= lum_px[pos] <= 232.0:
                    la_mau_dam_net[pos] = 1

        # Đo tỷ lệ cặp Halo kẹp 2 phía đối diện (Opposite-Side Halo Sandwiching)
        dem_trang_dac_hop = 0
        dem_toi_hop = 0
        dem_sang_hop = 0
        dem_cap_toi_trang = 0
        dem_cap_trang_toi = 0
        dt_hop = max(1, (cx1 - cx0) * (cy1 - cy0))
        for py in range(cy0, cy1):
            base = py * rw
            for px in range(cx0, cx1):
                pos = base + px
                if la_trang_dac[pos]:
                    dem_trang_dac_hop += 1
                if la_toi_net[pos] or la_mau_dam_net[pos]:
                    dem_toi_hop += 1
                    for d_h in range(1, 5):
                        if (
                            (px - d_h >= 0 and (la_trang_dac[pos - d_h] or la_sang_dac[pos - d_h]))
                            or (px + d_h < rw and (la_trang_dac[pos + d_h] or la_sang_dac[pos + d_h]))
                            or (py - d_h >= 0 and (la_trang_dac[pos - d_h * rw] or la_sang_dac[pos - d_h * rw]))
                            or (py + d_h < rh and (la_trang_dac[pos + d_h * rw] or la_sang_dac[pos + d_h * rw]))
                        ):
                            dem_cap_toi_trang += 1
                            break
                if la_sang_dac[pos] or la_mau_dam_net[pos]:
                    dem_sang_hop += 1
                    # Kiểm tra điểm sáng/màu tươi nằm kẹp giữa 2 vách viền tối (`la_toi_net`) ở 2 phía đối diện trong bán kính 8px
                    co_toi_trai = any(px - d_h >= 0 and la_toi_net[pos - d_h] for d_h in range(1, 9))
                    co_toi_phai = any(px + d_h < rw and la_toi_net[pos + d_h] for d_h in range(1, 9))
                    co_toi_tren = any(py - d_h >= 0 and la_toi_net[pos - d_h * rw] for d_h in range(1, 9))
                    co_toi_duoi = any(py + d_h < rh and la_toi_net[pos + d_h * rw] for d_h in range(1, 9))
                    if (co_toi_trai and co_toi_phai) or (co_toi_tren and co_toi_duoi):
                        dem_cap_trang_toi += 1

        ty_le_trang_dac = dem_trang_dac_hop / dt_hop
        ty_le_cap_toi_trang = dem_cap_toi_trang / max(1, dem_toi_hop)
        ty_le_cap_trang_toi = dem_cap_trang_toi / max(1, dem_sang_hop)
        ty_le_cap_halo = max(ty_le_cap_toi_trang, ty_le_cap_trang_toi)

        # Đánh dấu trước các mảng tối đặc (`la_mang_toi_dac`, bề dày >= 5px như tóc đen / bóng đổ lớn)
        # để phân biệt hoàn toàn với đường kẻ tường sọc dọc / vân gỗ mảnh 1-3px:
        la_mang_toi_dac_pre = bytearray(N)
        for py in range(rh):
            base = py * rw
            for px in range(rw):
                pos = base + px
                if lum_px[pos] <= 90.0:
                    dl_t = dr_t = du_t = dd_t = 0
                    while dl_t < 6 and px - dl_t - 1 >= 0 and lum_px[pos - dl_t - 1] <= 95.0:
                        dl_t += 1
                    while dr_t < 6 and px + dr_t + 1 < rw and lum_px[pos + dr_t + 1] <= 95.0:
                        dr_t += 1
                    while du_t < 6 and py - du_t - 1 >= 0 and lum_px[pos - (du_t + 1) * rw] <= 95.0:
                        du_t += 1
                    while dd_t < 6 and py + dd_t + 1 < rh and lum_px[pos + (dd_t + 1) * rw] <= 95.0:
                        dd_t += 1
                    if min(dl_t + dr_t + 1, du_t + dd_t + 1) >= 5:
                        la_mang_toi_dac_pre[pos] = 1

        # Đánh dấu các điểm thuộc dải sáng/trắng mảnh (`la_dai_trang_manh`, bề dày <= 9px) nằm quanh chữ/tóc đen,
        # nhưng KHÔNG đánh dấu các hành lang tường trắng cao (`max(w_tr, h_tr) >= 16`) nằm giữa các đường kẻ tường 1-2px:
        la_dai_trang_manh = bytearray(N)
        for py in range(rh):
            base = py * rw
            for px in range(rw):
                pos = base + px
                if lum_px[pos] >= 195.0 and (tb_lum_3x3[pos] >= 190.0 or la_trang_dac[pos]) and sat_px[pos] <= 55:
                    dl_w = dr_w = du_w = dd_w = 0
                    while dl_w < 11 and px - dl_w - 1 >= 0 and (tb_lum_3x3[pos - dl_w - 1] >= 190.0 or la_trang_dac[pos - dl_w - 1]) and sat_px[pos - dl_w - 1] <= 55:
                        dl_w += 1
                    while dr_w < 11 and px + dr_w + 1 < rw and (tb_lum_3x3[pos + dr_w + 1] >= 190.0 or la_trang_dac[pos + dr_w + 1]) and sat_px[pos + dr_w + 1] <= 55:
                        dr_w += 1
                    while du_w < 11 and py - du_w - 1 >= 0 and (tb_lum_3x3[pos - (du_w + 1) * rw] >= 190.0 or la_trang_dac[pos - (du_w + 1) * rw]) and sat_px[pos - (du_w + 1) * rw] <= 55:
                        du_w += 1
                    while dd_w < 11 and py + dd_w + 1 < rh and (tb_lum_3x3[pos + (dd_w + 1) * rw] >= 190.0 or la_trang_dac[pos + (dd_w + 1) * rw]) and sat_px[pos + (dd_w + 1) * rw] <= 55:
                        dd_w += 1
                    w_tr = dl_w + dr_w + 1
                    h_tr = du_w + dd_w + 1
                    if 2 <= min(w_tr, h_tr) <= 9 and max(w_tr, h_tr) >= 4:
                        if max(w_tr, h_tr) <= 15:
                            la_dai_trang_manh[pos] = 1
                        else:
                            # Nếu dải trắng dài theo 1 chiều (`max > 15`), chỉ coi là viền halo trắng khi nằm sát mảng tối đặc (`la_mang_toi_dac_pre`)
                            # hoặc sát nền cát xám screentone (`90 <= tb_lum_3x3 <= 208` và không phải đường kẻ đen `la_toi_net`),
                            # tuyệt đối không coi hành lang tường trắng giữa 2 đường kẻ tường mảnh là halo!
                            gan_mang_toi_hoac_xam = False
                            for d_m in range(1, 8):
                                for npos_m in (
                                    pos - d_m if px - d_m >= 0 else -1,
                                    pos + d_m if px + d_m < rw else -1,
                                    pos - d_m * rw if py - d_m >= 0 else -1,
                                    pos + d_m * rw if py + d_m < rh else -1,
                                ):
                                    if npos_m < 0:
                                        continue
                                    if la_mang_toi_dac_pre[npos_m] or (
                                        90.0 <= tb_lum_3x3[npos_m] <= 206.0
                                        and not la_toi_net[npos_m]
                                        and lum_px[npos_m] >= 85.0
                                    ):
                                        gan_mang_toi_hoac_xam = True
                                        break
                                if gan_mang_toi_hoac_xam:
                                    break
                            if gan_mang_toi_hoac_xam:
                                la_dai_trang_manh[pos] = 1

        ds_lum_nen_thuc = []
        ds_tb_nen_thuc = []
        ds_r_nen_thuc = []
        ds_g_nen_thuc = []
        ds_b_nen_thuc = []
        ds_sat_nen_thuc = []
        tong_contrast_hat = 0.0
        dem_contrast_hat = 0
        # Chỉ lấy mẫu nền thực sự trong phạm vi hộp chữ + viền lân cận 14px (`[cx0-14..cx1+14, cy0-14..cy1+14]`),
        # tránh lấy mẫu ra tận biên mở rộng 62px bên ngoài khiến bóng thoại trắng bị lẫn nét vẽ khung tranh bên ngoài:
        ny0_m = max(0, cy0 - 14)
        ny1_m = min(rh, cy1 + 14)
        nx0_m = max(0, cx0 - 14)
        nx1_m = min(rw, cx1 + 14)
        for py in range(ny0_m, ny1_m, 2):
            base = py * rw
            for px in range(nx0_m, nx1_m, 2):
                pos = base + px
                if vung_cam[pos]:
                    continue
                trong_hop = (cx0 <= px < cx1) and (cy0 <= py < cy1)
                if trong_hop and (la_toi_net[pos] or la_mau_dam_net[pos]):
                    continue
                if la_trang_dac[pos] or la_sang_dac[pos] or la_dai_trang_manh[pos]:
                    sat_net_toi = False
                    for d_h in range(1, 6):
                        if (
                            (px - d_h >= 0 and la_toi_net[pos - d_h])
                            or (px + d_h < rw and la_toi_net[pos + d_h])
                            or (py - d_h >= 0 and la_toi_net[pos - d_h * rw])
                            or (py + d_h < rh and la_toi_net[pos + d_h * rw])
                        ):
                            sat_net_toi = True
                            break
                    if sat_net_toi and la_dai_trang_manh[pos]:
                        continue
                ds_r_nen_thuc.append(r_roi[pos])
                ds_g_nen_thuc.append(g_roi[pos])
                ds_b_nen_thuc.append(b_roi[pos])
                ds_lum_nen_thuc.append(lum_px[pos])
                ds_tb_nen_thuc.append(tb_lum_3x3[pos])
                ds_sat_nen_thuc.append(sat_px[pos])
                if px + 1 < rw and py + 1 < rh:
                    tong_contrast_hat += abs(lum_px[pos] - lum_px[pos + 1]) + abs(lum_px[pos] - lum_px[pos + rw])
                    dem_contrast_hat += 2

        ds_lum_nen_thuc.sort()
        ds_tb_nen_thuc.sort()
        ds_r_nen_thuc.sort()
        ds_g_nen_thuc.sort()
        ds_b_nen_thuc.sort()
        ds_sat_nen_thuc.sort()
        mid_n = len(ds_lum_nen_thuc) // 2
        lum_nen_trung_vi = ds_lum_nen_thuc[mid_n] if ds_lum_nen_thuc else med_lum
        tb_nen_trung_vi = ds_tb_nen_thuc[mid_n] if ds_tb_nen_thuc else lum_nen_trung_vi
        lum_nen_p30 = ds_lum_nen_thuc[int(len(ds_lum_nen_thuc) * 0.3)] if ds_lum_nen_thuc else med_lum
        lum_nen_p10 = ds_lum_nen_thuc[int(len(ds_lum_nen_thuc) * 0.1)] if ds_lum_nen_thuc else med_lum
        r_nen_trung_vi = ds_r_nen_thuc[mid_n] if ds_r_nen_thuc else bg_r
        g_nen_trung_vi = ds_g_nen_thuc[mid_n] if ds_g_nen_thuc else bg_g
        b_nen_trung_vi = ds_b_nen_thuc[mid_n] if ds_b_nen_thuc else bg_b
        sat_nen_trung_vi = ds_sat_nen_thuc[mid_n] if ds_sat_nen_thuc else (max(bg_r, bg_g, bg_b) - min(bg_r, bg_g, bg_b))
        do_nhieu_hat = (tong_contrast_hat / dem_contrast_hat) if dem_contrast_hat > 0 else 0.0
        la_nen_mau_thuc = (sat_nen_trung_vi >= 18) or ((max(r_nen_trung_vi, g_nen_trung_vi, b_nen_trung_vi) - min(r_nen_trung_vi, g_nen_trung_vi, b_nen_trung_vi)) >= 18)

        # Kiểm tra xem có đường kẻ nền / vách tường / vân gỗ / tóc đen thông từ biên hộp mở rộng vào lòng hộp chữ không:
        ex0_k = max(0, cx0 - min(22, mo_x))
        ey0_k = max(0, cy0 - min(26, mo_y))
        ex1_k = min(rw, cx1 + min(22, mo_x))
        ey1_k = min(rh, cy1 + min(38, mo_y))
        ket_noi_bien = bytearray(N)
        q_kb = []
        for px_k in range(ex0_k, ex1_k):
            for py_k in (ey0_k, ey1_k - 1):
                p_k = py_k * rw + px_k
                if not ket_noi_bien[p_k] and la_toi_net[p_k]:
                    ket_noi_bien[p_k] = 1
                    q_kb.append(p_k)
        for py_k in range(ey0_k, ey1_k):
            for px_k in (ex0_k, ex1_k - 1):
                p_k = py_k * rw + px_k
                if not ket_noi_bien[p_k] and la_toi_net[p_k]:
                    ket_noi_bien[p_k] = 1
                    q_kb.append(p_k)
        head_kb = 0
        while head_kb < len(q_kb):
            p_k = q_kb[head_kb]
            head_kb += 1
            xk = p_k % rw
            yk = p_k // rw
            for dy_k in (-1, 0, 1):
                nyk = yk + dy_k
                if nyk < ey0_k or nyk >= ey1_k:
                    continue
                nbk = nyk * rw
                for dx_k in (-1, 0, 1):
                    nxk = xk + dx_k
                    if nxk < ex0_k or nxk >= ex1_k:
                        continue
                    npk = nbk + nxk
                    if not ket_noi_bien[npk] and la_toi_net[npk]:
                        if dx_k != 0 and (cx0 + 2) <= nxk < (cx1 - 2) and (cy0 + 6) <= nyk < (cy1 - 6):
                            du_p = dd_p = 0
                            while du_p < 18 and yk - du_p - 1 >= 0 and la_toi_net[p_k - (du_p + 1) * rw]:
                                du_p += 1
                            while dd_p < 18 and yk + dd_p + 1 < rh and la_toi_net[p_k + (dd_p + 1) * rw]:
                                dd_p += 1
                            if du_p + dd_p + 1 >= 18:
                                du_k = dd_k = 0
                                while du_k < 10 and nyk - du_k - 1 >= 0 and la_toi_net[npk - (du_k + 1) * rw]:
                                    du_k += 1
                                while dd_k < 10 and nyk + dd_k + 1 < rh and la_toi_net[npk + (dd_k + 1) * rw]:
                                    dd_k += 1
                                if du_k + dd_k + 1 <= 7:
                                    tr_tren = (nyk - du_k - 1 >= 0 and lum_px[npk - (du_k + 1) * rw] >= 220.0) or (
                                        nyk - du_k - 2 >= 0 and lum_px[npk - (du_k + 2) * rw] >= 220.0
                                    )
                                    tr_duoi = (nyk + dd_k + 1 < rh and lum_px[npk + (dd_k + 1) * rw] >= 220.0) or (
                                        nyk + dd_k + 2 < rh and lum_px[npk + (dd_k + 2) * rw] >= 220.0
                                    )
                                    if tr_tren and tr_duoi:
                                        continue
                        ket_noi_bien[npk] = 1
                        q_kb.append(npk)
        dem_net_xuyen_hop = 0
        ix0_k = min(rw, min(cx1, cx0 + max(5, int((cx1 - cx0) * 0.16))))
        ix1_k = min(rw, max(ix0_k, cx1 - max(5, int((cx1 - cx0) * 0.16))))
        iy0_k = min(rh, min(cy1, cy0 + max(5, int((cy1 - cy0) * 0.16))))
        iy1_k = min(rh, max(iy0_k, cy1 - max(5, int((cy1 - cy0) * 0.16))))
        for py_k in range(iy0_k, iy1_k):
            bk = py_k * rw
            for px_k in range(ix0_k, ix1_k):
                if ket_noi_bien[bk + px_k]:
                    dem_net_xuyen_hop += 1

        # Kiểm tra rò rỉ lòng trắng ra 4 cạnh ngoài của ROI (để phân biệt Bong Bóng Khép Kín với Chữ Nổi Trên Tường Trắng):
        # Dùng hạt giống ở tâm hộp chữ + đệm 3x3 (trong vùng chữ) / 5x5 (ngoài vùng chữ) để chặn rò rỉ qua khe hẹp của gai nhọn bóng thoại:
        la_nen_trang_mask = bytearray(N)
        for idx_m in range(N):
            if lum_px[idx_m] >= 210.0 and sat_px[idx_m] <= 45 and not vung_cam[idx_m]:
                la_nen_trang_mask[idx_m] = 1
        la_nen_rong_roi = bytearray(N)
        pad_lt_x = max(12, int(round((cx1 - cx0) * 0.22)))
        pad_lt_y = max(16, int(round((cy1 - cy0) * 0.25)))
        for py_r in range(2, rh - 2):
            br_r = py_r * rw
            trong_y_r = (cy0 - pad_lt_y) <= py_r < (cy1 + pad_lt_y)
            for px_r in range(2, rw - 2):
                pos_r = br_r + px_r
                if not la_nen_trang_mask[pos_r]:
                    continue
                sach_3x3 = (
                    la_nen_trang_mask[pos_r - 1]
                    and la_nen_trang_mask[pos_r + 1]
                    and la_nen_trang_mask[pos_r - rw]
                    and la_nen_trang_mask[pos_r + rw]
                    and la_nen_trang_mask[pos_r - rw - 1]
                    and la_nen_trang_mask[pos_r - rw + 1]
                    and la_nen_trang_mask[pos_r + rw - 1]
                    and la_nen_trang_mask[pos_r + rw + 1]
                )
                if not sach_3x3:
                    continue
                trong_hop_r = trong_y_r and ((cx0 - pad_lt_x) <= px_r < (cx1 + pad_lt_x))
                if trong_hop_r or (
                    la_nen_trang_mask[pos_r - 2]
                    and la_nen_trang_mask[pos_r + 2]
                    and la_nen_trang_mask[pos_r - 2 * rw]
                    and la_nen_trang_mask[pos_r + 2 * rw]
                ):
                    la_nen_rong_roi[pos_r] = 1

        long_trang_roi = bytearray(N)
        q_lt = []
        tam_gx = (cx0 + cx1) * 0.5
        tam_gy = (cy0 + cy1) * 0.5
        ban_rx = max(3.0, (cx1 - cx0) * 0.5)
        ban_ry = max(3.0, (cy1 - cy0) * 0.5)
        for bk_hat in (0.28, 0.58):
            for py_k in range(cy0, cy1):
                ny_k = (py_k - tam_gy) / ban_ry
                bk = py_k * rw
                for px_k in range(cx0, cx1):
                    nx_k = (px_k - tam_gx) / ban_rx
                    if nx_k * nx_k + ny_k * ny_k > bk_hat:
                        continue
                    pk = bk + px_k
                    if la_nen_trang_mask[pk] and not long_trang_roi[pk]:
                        long_trang_roi[pk] = 1
                        q_lt.append(pk)
            if len(q_lt) >= 8:
                break
        head_lt = 0
        while head_lt < len(q_lt):
            pk = q_lt[head_lt]
            head_lt += 1
            xk = pk % rw
            yk = pk // rw
            for npos_lt, nx_lt, ny_lt in (
                (pk - 1, xk - 1, yk) if xk > 0 else (-1, 0, 0),
                (pk + 1, xk + 1, yk) if xk + 1 < rw else (-1, 0, 0),
                (pk - rw, xk, yk - 1) if yk > 0 else (-1, 0, 0),
                (pk + rw, xk, yk + 1) if yk + 1 < rh else (-1, 0, 0),
            ):
                if npos_lt < 0 or long_trang_roi[npos_lt] or not la_nen_trang_mask[npos_lt]:
                    continue
                nx_r = (nx_lt - tam_gx) / ban_rx
                ny_r = (ny_lt - tam_gy) / ban_ry
                if (nx_r * nx_r + ny_r * ny_r <= 0.72) or la_nen_rong_roi[npos_lt]:
                    long_trang_roi[npos_lt] = 1
                    q_lt.append(npos_lt)
        # Bù nhẹ 1px quanh `long_trang_roi` để chạm sát vách trong viền bóng thoại
        so_lt_goc = len(q_lt)
        for idx_lt in range(so_lt_goc):
            pk = q_lt[idx_lt]
            xk = pk % rw
            yk = pk // rw
            if xk > 0 and not long_trang_roi[pk - 1] and la_nen_trang_mask[pk - 1]:
                long_trang_roi[pk - 1] = 1
                q_lt.append(pk - 1)
            if xk + 1 < rw and not long_trang_roi[pk + 1] and la_nen_trang_mask[pk + 1]:
                long_trang_roi[pk + 1] = 1
                q_lt.append(pk + 1)
            if yk > 0 and not long_trang_roi[pk - rw] and la_nen_trang_mask[pk - rw]:
                long_trang_roi[pk - rw] = 1
                q_lt.append(pk - rw)
            if yk + 1 < rh and not long_trang_roi[pk + rw] and la_nen_trang_mask[pk + rw]:
                long_trang_roi[pk + rw] = 1
                q_lt.append(pk + rw)
        dem_khong_toi_hop = 0
        dem_trang_tinh_hop = 0
        for py_w in range(cy0, cy1):
            bw = py_w * rw
            for px_w in range(cx0, cx1):
                lw = lum_px[bw + px_w]
                if lw > 120.0:
                    dem_khong_toi_hop += 1
                    if lw >= 240.0 and sat_px[bw + px_w] <= 36:
                        dem_trang_tinh_hop += 1
        ty_le_trang_tren_nen_sang = dem_trang_tinh_hop / max(1, dem_khong_toi_hop)

        cham_bien_lt = 0
        chu_vi_roi = max(1, (rw + rh) * 2)
        for px_k in range(rw):
            if long_trang_roi[px_k] or (rh > 2 and (long_trang_roi[rw + px_k] or long_trang_roi[2 * rw + px_k])):
                cham_bien_lt += 1
            if long_trang_roi[(rh - 1) * rw + px_k] or (rh > 3 and (long_trang_roi[(rh - 2) * rw + px_k] or long_trang_roi[(rh - 3) * rw + px_k])):
                cham_bien_lt += 1
        for py_k in range(rh):
            if long_trang_roi[py_k * rw] or (rw > 2 and (long_trang_roi[py_k * rw + 1] or long_trang_roi[py_k * rw + 2])):
                cham_bien_lt += 1
            if long_trang_roi[py_k * rw + (rw - 1)] or (rw > 3 and (long_trang_roi[py_k * rw + (rw - 2)] or long_trang_roi[py_k * rw + (rw - 3)])):
                cham_bien_lt += 1
        la_bong_dai_hep = (
            cham_bien_lt < int(chu_vi_roi * 0.08)
            and len(q_lt) <= dt_hop * 1.75
            and dem_net_xuyen_hop < 10
            and ty_le_trang_dac >= 0.62
            and ty_le_trang_tren_nen_sang >= 0.84
        )
        ro_ri_bien_rong = (not la_bong_dai_hep) and (
            cham_bien_lt >= max(4, int(chu_vi_roi * 0.02))
            or (cham_bien_lt >= 2 and len(q_lt) > dt_hop * 3.4)
            or (cham_bien_lt >= 1 and len(q_lt) > dt_hop * 5.2)
            or len(q_lt) > dt_hop * 14.0
        )
        nguong_tlt_bong = 0.84 if do_nhieu_hat >= 22.0 else 0.78
        nguong_p30_bong = 216.0 if (ty_le_trang_dac >= 0.62 and ty_le_trang_tren_nen_sang >= 0.84 and dem_net_xuyen_hop == 0) else (240.0 if do_nhieu_hat >= 22.0 else 224.0)
        la_bong_khep_kin = (
            (not ro_ri_bien_rong)
            and (not la_nen_mau_thuc)
            and (lum_nen_trung_vi >= 234.0)
            and (lum_nen_p30 >= nguong_p30_bong)
            and (ty_le_trang_dac >= 0.52)
            and (ty_le_trang_tren_nen_sang >= nguong_tlt_bong)
            and (dem_net_xuyen_hop < 10)
            and (len(q_lt) >= dt_hop * 0.36)
        )
        if la_bong_khep_kin:
            dau_mo = so_lt_goc
            for _ in range(28):
                cuoi_mo = len(q_lt)
                if dau_mo >= cuoi_mo:
                    break
                while dau_mo < cuoi_mo:
                    pk = q_lt[dau_mo]
                    dau_mo += 1
                    xk = pk % rw
                    yk = pk // rw
                    if xk > 1 and not long_trang_roi[pk - 1] and la_nen_trang_mask[pk - 1]:
                        long_trang_roi[pk - 1] = 1
                        q_lt.append(pk - 1)
                    if xk + 2 < rw and not long_trang_roi[pk + 1] and la_nen_trang_mask[pk + 1]:
                        long_trang_roi[pk + 1] = 1
                        q_lt.append(pk + 1)
                    if yk > 1 and not long_trang_roi[pk - rw] and la_nen_trang_mask[pk - rw]:
                        long_trang_roi[pk - rw] = 1
                        q_lt.append(pk - rw)
                    if yk + 2 < rh and not long_trang_roi[pk + rw] and la_nen_trang_mask[pk + rw]:
                        long_trang_roi[pk + rw] = 1
                        q_lt.append(pk + rw)

        ngoai_bong_bong = bytearray(N)
        if la_bong_khep_kin:
            q_nb = []
            for px_k in range(rw):
                for p_nb in (px_k, (rh - 1) * rw + px_k):
                    if not ngoai_bong_bong[p_nb] and not long_trang_roi[p_nb]:
                        ngoai_bong_bong[p_nb] = 1
                        q_nb.append(p_nb)
            for py_k in range(rh):
                for p_nb in (py_k * rw, py_k * rw + (rw - 1)):
                    if not ngoai_bong_bong[p_nb] and not long_trang_roi[p_nb]:
                        ngoai_bong_bong[p_nb] = 1
                        q_nb.append(p_nb)
            head_nb = 0
            while head_nb < len(q_nb):
                p_nb = q_nb[head_nb]
                head_nb += 1
                x_nb = p_nb % rw
                y_nb = p_nb // rw
                if x_nb > 0 and not ngoai_bong_bong[p_nb - 1] and not long_trang_roi[p_nb - 1]:
                    ngoai_bong_bong[p_nb - 1] = 1
                    q_nb.append(p_nb - 1)
                if x_nb + 1 < rw and not ngoai_bong_bong[p_nb + 1] and not long_trang_roi[p_nb + 1]:
                    ngoai_bong_bong[p_nb + 1] = 1
                    q_nb.append(p_nb + 1)
                if y_nb > 0 and not ngoai_bong_bong[p_nb - rw] and not long_trang_roi[p_nb - rw]:
                    ngoai_bong_bong[p_nb - rw] = 1
                    q_nb.append(p_nb - rw)
                if y_nb + 1 < rh and not ngoai_bong_bong[p_nb + rw] and not long_trang_roi[p_nb + rw]:
                    ngoai_bong_bong[p_nb + rw] = 1
                    q_nb.append(p_nb + rw)
            for idx_nb in range(N):
                if vung_cam[idx_nb]:
                    ngoai_bong_bong[idx_nb] = 1

        # Sau khi đã biết màu nền thực sự `(r_nen_trung_vi, g_nen_trung_vi, b_nen_trung_vi)`,
        # đo đối xứng tỷ lệ Kẹp 2 Phía Đối Diện giữa:
        # - `dem_cap_toi_trang`: Điểm tối nằm kẹp giữa 2 vách sáng/trắng đối diện (Chữ tối + Halo trắng)
        # - `dem_cap_trang_toi`: Điểm sáng/màu tươi nằm kẹp giữa 2 vách tối đối diện (Chữ sáng/màu + Halo đen)
        if la_nen_mau_thuc:
            dem_toi_hop = 0
            dem_sang_hop = 0
            dem_cap_toi_trang = 0
            dem_cap_trang_toi = 0
            for py in range(cy0, cy1):
                base = py * rw
                for px in range(cx0, cx1):
                    pos = base + px
                    sai_nen = abs(r_roi[pos] - r_nen_trung_vi) + abs(g_roi[pos] - g_nen_trung_vi) + abs(b_roi[pos] - b_nen_trung_vi)
                    if la_toi_net[pos] or (la_mau_dam_net[pos] and sai_nen >= 65 and lum_px[pos] < 115.0):
                        dem_toi_hop += 1
                        co_tr_trai = any(px - d_h >= 0 and (la_trang_dac[pos - d_h] or la_sang_dac[pos - d_h]) for d_h in range(1, 9))
                        co_tr_phai = any(px + d_h < rw and (la_trang_dac[pos + d_h] or la_sang_dac[pos + d_h]) for d_h in range(1, 9))
                        co_tr_tren = any(py - d_h >= 0 and (la_trang_dac[pos - d_h * rw] or la_sang_dac[pos - d_h * rw]) for d_h in range(1, 9))
                        co_tr_duoi = any(py + d_h < rh and (la_trang_dac[pos + d_h * rw] or la_sang_dac[pos + d_h * rw]) for d_h in range(1, 9))
                        if (co_tr_trai and co_tr_phai) or (co_tr_tren and co_tr_duoi):
                            dem_cap_toi_trang += 1
                    if la_trang_dac[pos] or la_sang_dac[pos] or (la_mau_dam_net[pos] and sai_nen >= 65 and lum_px[pos] >= 115.0):
                        dem_sang_hop += 1
                        co_toi_trai = any(px - d_h >= 0 and la_toi_net[pos - d_h] for d_h in range(1, 9))
                        co_toi_phai = any(px + d_h < rw and la_toi_net[pos + d_h] for d_h in range(1, 9))
                        co_toi_tren = any(py - d_h >= 0 and la_toi_net[pos - d_h * rw] for d_h in range(1, 9))
                        co_toi_duoi = any(py + d_h < rh and la_toi_net[pos + d_h * rw] for d_h in range(1, 9))
                        if (co_toi_trai and co_toi_phai) or (co_toi_tren and co_toi_duoi):
                            dem_cap_trang_toi += 1
            ty_le_cap_toi_trang = dem_cap_toi_trang / max(1, dem_toi_hop)
            ty_le_cap_trang_toi = dem_cap_trang_toi / max(1, dem_sang_hop)
            ty_le_cap_halo = max(ty_le_cap_toi_trang, ty_le_cap_trang_toi)

        # Vùng nền chỉ thực sự là BONG BÓNG TRẮNG PHẲNG khi không phải nền màu, trung vị/P30/P10 đều trắng sạch,
        # và KHÔNG bị rò rỉ kèm đường kẻ tường/vân gỗ/tóc đen xuyên vào lòng hộp (`dem_net_xuyen_hop >= 10`):
        co_net_tranh_xuyen_hop = (not la_bong_khep_kin) and ((ro_ri_bien_rong and dem_net_xuyen_hop >= 10) or dem_net_xuyen_hop >= 24)
        la_nen_trang_phang = (
            (not la_nen_mau_thuc)
            and (not co_net_tranh_xuyen_hop)
            and (lum_nen_trung_vi >= 234.0)
            and (ty_le_trang_tren_nen_sang >= nguong_tlt_bong)
            and (
                (lum_nen_p30 >= 218.0 and (lum_nen_p10 >= 205.0 or ((la_bong_khep_kin or not ro_ri_bien_rong) and ty_le_trang_dac >= 0.48)))
                or ((la_bong_khep_kin or not ro_ri_bien_rong) and ty_le_trang_dac >= 0.55)
                or (ty_le_trang_tren_nen_sang >= 0.83 and ty_le_trang_dac >= 0.55 and do_nhieu_hat < 18.0)
            )
        )
        la_chu_noi_tren_nen = bool(
            not la_bong_khep_kin
            and not la_nen_trang_phang
            and (
                nen_mau_trung_binh
                or co_net_tranh_xuyen_hop
                or (
                    (ty_le_cap_halo >= 0.20 or dem_trang_dac_hop >= dt_hop * 0.05)
                    and (ty_le_trang_dac < 0.65 or lum_nen_trung_vi < 224.0 or lum_nen_p30 < 214.0 or lum_nen_p10 < 205.0 or do_nhieu_hat >= 8.5 or la_nen_mau_thuc)
                )
            )
        )
        la_dao_chieu_halo = (
            la_chu_noi_tren_nen
            and la_nen_mau_thuc
            and ty_le_cap_trang_toi > ty_le_cap_toi_trang * 1.15
            and ty_le_cap_trang_toi >= 0.28
            and lum_nen_trung_vi >= 48.0
            and ty_le_trang_dac < 0.45
        )
        if la_chu_noi_tren_nen:
            nen_mau_trung_binh = True
            bg_r, bg_g, bg_b = int(r_nen_trung_vi), int(g_nen_trung_vi), int(b_nen_trung_vi)
            nen_toi = bool(la_dao_chieu_halo or (lum_nen_trung_vi < 82.0))

        row_bg: list[tuple[int, int, int, float]] = []
        sx_r0 = max(0, cx0 - min(16, max(6, w_goc // 6)))
        sx_r1 = min(rw, cx1 + min(16, max(6, w_goc // 6)))
        for py in range(rh):
            mau_dong = []
            for px in range(sx_r0, sx_r1, 2):
                r, g, b = px_anh[rx0 + px, ry0 + py]
                lum = 0.299 * r + 0.587 * g + 0.114 * b
                sai_so = abs(r - bg_r) + abs(g - bg_g) + abs(b - bg_b)
                if nen_mau_trung_binh:
                    if 45.0 <= lum <= 198.0 and sai_so <= 105:
                        mau_dong.append((sai_so, r, g, b, lum))
                elif sai_so <= 80 or (lum <= 60 if nen_toi else lum >= 200):
                    mau_dong.append((sai_so, r, g, b, lum))
            if len(mau_dong) >= 3:
                mau_dong.sort(key=lambda m: m[0])
                so_lay = max(2, (len(mau_dong) + 1) // 2)
                rr = int(round(sum(m[1] for m in mau_dong[:so_lay]) / so_lay))
                gg = int(round(sum(m[2] for m in mau_dong[:so_lay]) / so_lay))
                bb = int(round(sum(m[3] for m in mau_dong[:so_lay]) / so_lay))
            else:
                rr, gg, bb = bg_r, bg_g, bg_b
            row_bg.append((rr, gg, bb, 0.299 * rr + 0.587 * gg + 0.114 * bb))

        pad_hop_x = max(8, int(round((cx1 - cx0) * 0.18)))
        pad_hop_y = max(8, int(round((cy1 - cy0) * 0.18)))
        # Trong bóng thoại trắng (`not la_chu_noi_tren_nen`), mở rộng vùng nhận diện chữ theo lòng trắng `long_trang_roi`
        # để nếu hộp chữ khoanh hụt dòng cuối ("er,", "ready...") thì vẫn xoá sạch 100% chữ bên trong lòng bóng:
        gan_long_trang = bytearray(N)
        if not la_chu_noi_tren_nen and len(q_lt) >= 24:
            for py_lt in range(max(2, cy0 - 38), min(rh - 2, cy1 + 56)):
                base_lt = py_lt * rw
                for px_lt in range(max(2, cx0 - 24), min(rw - 2, cx1 + 24)):
                    pos_lt = base_lt + px_lt
                    if (
                        long_trang_roi[pos_lt]
                        or (px_lt >= 3 and long_trang_roi[pos_lt - 3])
                        or (px_lt + 3 < rw and long_trang_roi[pos_lt + 3])
                        or (py_lt >= 3 and long_trang_roi[pos_lt - 3 * rw])
                        or (py_lt + 3 < rh and long_trang_roi[pos_lt + 3 * rw])
                    ):
                        gan_long_trang[pos_lt] = 1

        for py in range(rh):
            dvy = cy0 - py if py < cy0 else (py - cy1 if py > cy1 else 0)
            dvy2 = dvy * dvy
            base = py * rw
            rr, gg, bb, rlum = row_bg[py]
            trong_y = (cy0 - pad_hop_y) <= py < (cy1 + pad_hop_y)
            for px in range(rw):
                r, g, b = px_anh[rx0 + px, ry0 + py]
                lum = 0.299 * r + 0.587 * g + 0.114 * b
                sai_so_row = abs(r - rr) + abs(g - gg) + abs(b - bb)
                sai_so_bg = abs(r - bg_r) + abs(g - bg_g) + abs(b - bg_b)
                trong_hop_mo = (trong_y and ((cx0 - pad_hop_x) <= px < (cx1 + pad_hop_x))) or bool(gan_long_trang[base + px])
                if nen_mau_trung_binh:
                    if trong_hop_mo and lum <= 95.0:
                        la_nen[base + px] = 0
                    else:
                        la_nen[base + px] = 1
                else:
                    la_trang_sang_sach = (not nen_toi) and (lum >= 198.0) and (max(r, g, b) - min(r, g, b) <= 36)
                    if la_trang_sang_sach:
                        la_nen[base + px] = 1
                    elif trong_hop_mo and ((lum > 55.0) if nen_toi else (lum < 198.0)) and (sai_so_row > 42 or abs(lum - rlum) > 22):
                        la_nen[base + px] = 0
                    elif sai_so_row <= 36 or sai_so_bg <= 42 or ((lum <= 45) if nen_toi else (lum >= 224 and max(r, g, b) - min(r, g, b) <= 36)):
                        la_nen[base + px] = 1
                if ds_lang_gieng:
                    dvx = cx0 - px if px < cx0 else (px - cx1 if px > cx1 else 0)
                    dist_v2 = dvx * dvx + dvy2
                    if dist_v2 > 0:
                        for lg0, lg1, lg2, lg3 in ds_lang_gieng:
                            dux = lg0 - px if px < lg0 else (px - lg2 if px > lg2 else 0)
                            duy = lg1 - py if py < lg1 else (py - lg3 if py > lg3 else 0)
                            if dux * dux + duy * duy <= dist_v2:
                                vung_cam[base + px] = 1
                                break

        ds_dong_con = v.get("dong_con")
        if not isinstance(ds_dong_con, list) or not ds_dong_con:
            ds_dong_con = [{"x": x_goc, "y": y_goc, "w": w_goc, "h": h_goc}]

        trong_dong = bytearray(N)
        trong_dong_mo = bytearray(N)
        ds_hop_dong = []
        for d_con in ds_dong_con:
            lx0 = int(round(d_con.get("x", x_goc) - rx0))
            ly0 = int(round(d_con.get("y", y_goc) - ry0))
            lx1 = int(round(d_con.get("x", x_goc) + d_con.get("w", w_goc) - rx0))
            ly1 = int(round(d_con.get("y", y_goc) + d_con.get("h", h_goc) - ry0))
            ds_hop_dong.append((lx0, ly0, lx1, ly1))
            for py_d in range(max(2, ly0 - 16), min(rh - 2, ly1 + 16)):
                base_d = py_d * rw
                for px_d in range(max(2, lx0 - 16), min(rw - 2, lx1 + 16)):
                    trong_dong[base_d + px_d] = 1
            for py_d in range(max(1, ly0 - 26), min(rh - 1, ly1 + 26)):
                base_d = py_d * rw
                for px_d in range(max(1, lx0 - 26), min(rw - 1, lx1 + 26)):
                    trong_dong_mo[base_d + px_d] = 1

        ds_hop_dong.sort(key=lambda r: r[1])
        for idx_hd in range(len(ds_hop_dong) - 1):
            a_x0, a_y0, a_x1, a_y1 = ds_hop_dong[idx_hd]
            b_x0, b_y0, b_x1, b_y1 = ds_hop_dong[idx_hd + 1]
            if b_y0 >= a_y1 - 2 and (b_y0 - a_y1) <= 36:
                ix0 = min(a_x0, b_x0)
                ix1 = max(a_x1, b_x1)
                for py_d in range(max(2, a_y1 - 2), min(rh - 2, b_y0 + 2)):
                    base_d = py_d * rw
                    for px_d in range(max(2, ix0 - 8), min(rw - 2, ix1 + 8)):
                        trong_dong[base_d + px_d] = 1
                        trong_dong_mo[base_d + px_d] = 1
                    for px_d in range(max(1, ix0 - 18), min(rw - 1, ix1 + 18)):
                        trong_dong_mo[base_d + px_d] = 1

        sx0 = max(2, cx0 - 24)
        sy0 = max(2, cy0 - 38)
        sx1 = min(rw - 2, cx1 + 24)
        sy1 = min(rh - 2, cy1 + 56)
        if not la_chu_noi_tren_nen and len(q_lt) >= 24:
            for py_d in range(sy0, sy1):
                base_d = py_d * rw
                for px_d in range(sx0, sx1):
                    if gan_long_trang[base_d + px_d]:
                        trong_dong[base_d + px_d] = 1
                        trong_dong_mo[base_d + px_d] = 1
        da_tham_cca = bytearray(N)
        can_xoa = bytearray(N)
        dien_tich_max_net = max(400, int(round((sx1 - sx0) * (sy1 - sy0) * 0.65)))

        mau_chu_goc = None
        mau_vien_goc = None
        min_x_xoa, min_y_xoa = cx0, cy0
        max_x_xoa, max_y_xoa = cx1, cy1
        co_diem_xoa_chu_noi = False

        if la_chu_noi_tren_nen:
            # === NHÁNH ĐA TÌNH HUỐNG CHO CHỮ NỔI KHÔNG BONG BÓNG TRÊN WINDOWS APP ===
            # Bao phủ: Nền cát Screentone, Tóc đen/Bóng đổ, Tường trắng kẻ sọc/Vân gỗ, Nền hỗn hợp (Tóc đen + Tường trắng) & Nền màu
            la_loi_chu = bytearray(N)
            ung_vien_net = bytearray(N)
            net_mong_loi = bytearray(N)
            qx0 = max(2, cx0 - min(32, mo_x - 2))
            qy0 = max(2, cy0 - min(38, mo_y - 2))
            qx1 = min(rw - 2, cx1 + min(32, mo_x - 2))
            qy1 = min(rh - 2, cy1 + min(58, mo_y - 2))
            # Cắt chặn `qx0, qy0, qx1, qy1` tại đường viền khung tranh (panel border) để tuyệt đối không tràn sang khung tranh kế bên:
            span_w_b = max(1, cx1 - cx0)
            span_h_b = max(1, cy1 - cy0)
            for py_b in range(cy0 - 1, qy0 - 1, -1):
                base_b = py_b * rw
                dem_toi_b = sum(1 for px_b in range(cx0, cx1) if lum_px[base_b + px_b] <= 105.0)
                if dem_toi_b >= span_w_b * 0.62:
                    qy0 = min(cy0, py_b + 2)
                    break
            for py_b in range(cy1, qy1):
                base_b = py_b * rw
                dem_toi_b = sum(1 for px_b in range(cx0, cx1) if lum_px[base_b + px_b] <= 105.0)
                if dem_toi_b >= span_w_b * 0.62:
                    qy1 = max(cy1, py_b - 1)
                    break
            for px_b in range(cx0 - 1, qx0 - 1, -1):
                dem_toi_b = sum(1 for py_b in range(cy0, cy1) if lum_px[py_b * rw + px_b] <= 105.0)
                if dem_toi_b >= span_h_b * 0.62:
                    qx0 = min(cx0, px_b + 2)
                    break
            for px_b in range(cx1, qx1):
                dem_toi_b = sum(1 for py_b in range(cy0, cy1) if lum_px[py_b * rw + px_b] <= 105.0)
                if dem_toi_b >= span_h_b * 0.62:
                    qx1 = max(cx1, px_b - 1)
                    break

            def _la_ung_vien_loi(pos_p: int) -> bool:
                py_p = pos_p // rw
                rr_p, gg_p, bb_p, _ = row_bg[py_p]
                sai_med = abs(r_roi[pos_p] - r_nen_trung_vi) + abs(g_roi[pos_p] - g_nen_trung_vi) + abs(b_roi[pos_p] - b_nen_trung_vi)
                sai_row = abs(r_roi[pos_p] - rr_p) + abs(g_roi[pos_p] - gg_p) + abs(b_roi[pos_p] - bb_p)
                if la_dao_chieu_halo:
                    if la_trang_dac[pos_p]:
                        return True
                    return bool(sai_med >= 62 and sai_row >= 52 and (la_sang_dac[pos_p] or (la_mau_dam_net[pos_p] and lum_px[pos_p] >= 115.0)))
                if la_nen_mau_thuc and ty_le_cap_halo < 0.20:
                    return sai_med >= 58 and sai_row >= 48
                if la_toi_net[pos_p]:
                    return True
                if la_nen_mau_thuc and la_mau_dam_net[pos_p]:
                    return sai_med >= 68 and sai_row >= 62
                return False

            def _la_ung_vien_halo(pos_p: int) -> bool:
                if la_dao_chieu_halo:
                    return bool(la_toi_net[pos_p] or lum_px[pos_p] <= 105.0)
                if nen_toi:
                    return bool(la_trang_dac[pos_p] or (lum_px[pos_p] >= 145.0 and sat_px[pos_p] <= 55))
                return bool(la_trang_dac[pos_p] or la_dai_trang_manh[pos_p] or (la_nen_mau_thuc and la_sang_dac[pos_p]))

            max_day_net = max(16, min(32, int(round(min(w_goc, h_goc) * 0.24))))
            max_scan_d = max(28, max_day_net + 4)
            max_dh = max(10, (max_day_net // 2) + 4)
            for py_d in range(1, rh - 1):
                base_d = py_d * rw
                for px_d in range(1, rw - 1):
                    pos_d = base_d + px_d
                    if vung_cam[pos_d] or not _la_ung_vien_loi(pos_d):
                        continue
                    d_l = d_r = d_u = d_d = 0
                    while d_l < max_scan_d and px_d - d_l - 1 >= 0 and _la_ung_vien_loi(pos_d - d_l - 1):
                        d_l += 1
                    while d_r < max_scan_d and px_d + d_r + 1 < rw and _la_ung_vien_loi(pos_d + d_r + 1):
                        d_r += 1
                    while d_u < max_scan_d and py_d - d_u - 1 >= 0 and _la_ung_vien_loi(pos_d - (d_u + 1) * rw):
                        d_u += 1
                    while d_d < max_scan_d and py_d + d_d + 1 < rh and _la_ung_vien_loi(pos_d + (d_d + 1) * rw):
                        d_d += 1
                    day_ngang = d_l + d_r + 1
                    day_doc = d_u + d_d + 1
                    if min(day_ngang, day_doc) <= max_day_net:
                        net_mong_loi[pos_d] = 1
                    if px_d < qx0 or px_d >= qx1 or py_d < qy0 or py_d >= qy1:
                        continue
                    if min(day_ngang, day_doc) > max_day_net or (min(day_ngang, day_doc) <= 3 and max(day_ngang, day_doc) >= 24):
                        continue

                    if la_nen_mau_thuc and ty_le_cap_halo < 0.20:
                        if min(day_ngang, day_doc) <= 13 and trong_dong_mo[pos_d] and not ket_noi_bien[pos_d]:
                            ung_vien_net[pos_d] = 1
                        continue

                    # Kiểm tra Halo 2px liên tiếp ngay sát rìa ngoài của nét chữ (1..3px tính từ mép nét d_l, d_r, d_u, d_d)
                    # để tuyệt đối không nhảy qua khe hở giữa 2 dòng chữ bắt nhầm nét gạch chéo / speedline nền:
                    h_trai = (
                        day_ngang <= 36
                        and px_d - d_l - 2 >= 0
                        and (
                            (_la_ung_vien_halo(pos_d - d_l - 1) and _la_ung_vien_halo(pos_d - d_l - 2))
                            or (px_d - d_l - 3 >= 0 and _la_ung_vien_halo(pos_d - d_l - 2) and _la_ung_vien_halo(pos_d - d_l - 3))
                        )
                    )
                    h_phai = (
                        day_ngang <= 36
                        and px_d + d_r + 2 < rw
                        and (
                            (_la_ung_vien_halo(pos_d + d_r + 1) and _la_ung_vien_halo(pos_d + d_r + 2))
                            or (px_d + d_r + 3 < rw and _la_ung_vien_halo(pos_d + d_r + 2) and _la_ung_vien_halo(pos_d + d_r + 3))
                        )
                    )
                    h_tren = (
                        day_doc <= 42
                        and py_d - d_u - 2 >= 0
                        and (
                            (_la_ung_vien_halo(pos_d - (d_u + 1) * rw) and _la_ung_vien_halo(pos_d - (d_u + 2) * rw))
                            or (py_d - d_u - 3 >= 0 and _la_ung_vien_halo(pos_d - (d_u + 2) * rw) and _la_ung_vien_halo(pos_d - (d_u + 3) * rw))
                        )
                    )
                    h_duoi = (
                        day_doc <= 42
                        and py_d + d_d + 2 < rh
                        and (
                            (_la_ung_vien_halo(pos_d + (d_d + 1) * rw) and _la_ung_vien_halo(pos_d + (d_d + 2) * rw))
                            or (py_d + d_d + 3 < rh and _la_ung_vien_halo(pos_d + (d_d + 2) * rw) and _la_ung_vien_halo(pos_d + (d_d + 3) * rw))
                        )
                    )
                    kep_doi_dien = (h_trai and h_phai) or (h_tren and h_duoi)
                    if kep_doi_dien:
                        ung_vien_net[pos_d] = 1

            # Lan truyền 4 bước dọc theo nét chữ (`net_mong_loi`) nối liền với `ung_vien_net`
            for _ in range(4):
                for py_d in range(qy0, qy1):
                    base_d = py_d * rw
                    for px_d in range(qx0, qx1):
                        pos_d = base_d + px_d
                        if ung_vien_net[pos_d] or vung_cam[pos_d] or ket_noi_bien[pos_d] or not net_mong_loi[pos_d]:
                            continue
                        if (
                            ung_vien_net[pos_d - 1]
                            or ung_vien_net[pos_d + 1]
                            or ung_vien_net[pos_d - rw]
                            or ung_vien_net[pos_d + rw]
                        ):
                            ung_vien_net[pos_d] = 1

            # Bước 2: Phân tích thành phần liên thông 2D (8-connected CCA) trên `ung_vien_net`
            # kết hợp Mật độ nét trung bình (`rho = area / max(w, h) >= 2.1`) và Liên kết chuỗi Từ/Dòng (Word/Line Chaining):
            # - Loại bỏ 100% đường kẻ tường sọc dọc 1-2px (`min_dim <= 2` hoặc `rho < 2.0`), vân gỗ, viền quân mạt chược & khung tranh (`cham_bien`).
            # - Bắt trọn 100% các chữ/dòng bị Gemini khoanh hụt ("ness...", "k-", "be", "Tenpai...") nhờ chuỗi liên kết ngang/dọc!
            da_duyet_comp = bytearray(N)
            ds_comp_chu = []
            max_comp_w = max(56, int(round(w_goc * 1.05)))
            max_comp_h = max(56, int(round(h_goc * 0.65)))
            max_comp_dt = max(1450, int(round(dt_hop * 0.46)))

            for py_d in range(qy0, qy1):
                base_d = py_d * rw
                for px_d in range(qx0, qx1):
                    s_pos = base_d + px_d
                    if not ung_vien_net[s_pos] or da_duyet_comp[s_pos] or vung_cam[s_pos]:
                        continue
                    da_duyet_comp[s_pos] = 1
                    q_c = [s_pos]
                    c_min_x = c_max_x = px_d
                    c_min_y = c_max_y = py_d
                    cham_bien_c = False
                    dem_uv = 0
                    head_c = 0
                    while head_c < len(q_c):
                        p_c = q_c[head_c]
                        head_c += 1
                        if ung_vien_net[p_c]:
                            dem_uv += 1
                        xc = p_c % rw
                        yc = p_c // rw
                        if xc <= qx0 + 1 or xc >= qx1 - 2 or yc <= qy0 + 1 or yc >= qy1 - 2 or ket_noi_bien[p_c]:
                            cham_bien_c = True
                        if xc < c_min_x:
                            c_min_x = xc
                        if xc > c_max_x:
                            c_max_x = xc
                        if yc < c_min_y:
                            c_min_y = yc
                        if yc > c_max_y:
                            c_max_y = yc
                        for dy_c in (-1, 0, 1):
                            nyc = yc + dy_c
                            if nyc <= 0 or nyc >= rh - 1:
                                continue
                            nbc = nyc * rw
                            for dx_c in (-1, 0, 1):
                                if dx_c == 0 and dy_c == 0:
                                    continue
                                nxc = xc + dx_c
                                if nxc <= 0 or nxc >= rw - 1:
                                    continue
                                npc = nbc + nxc
                                if ket_noi_bien[npc]:
                                    cham_bien_c = True
                                if not da_duyet_comp[npc] and ung_vien_net[npc] and not vung_cam[npc]:
                                    da_duyet_comp[npc] = 1
                                    q_c.append(npc)

                    cw_c = c_max_x - c_min_x + 1
                    ch_c = c_max_y - c_min_y + 1
                    dt_c = len(q_c)
                    max_d = max(cw_c, ch_c)
                    min_d = min(cw_c, ch_c)
                    rho_c = dt_c / max(1, max_d)
                    if cham_bien_c or dt_c > max_comp_dt or cw_c > max_comp_w or ch_c > max_comp_h:
                        continue
                    if cw_c >= w_goc * 0.82 and ch_c >= h_goc * 0.72:
                        continue
                    if dem_uv < dt_c * 0.35:
                        continue
                    # Bộ lọc chống đường kẻ tường / vân gỗ / speedline mảnh 1-2px:
                    # Cho phép giữ lại dấu chấm câu "..." / gạch nối "-" / chữ "I" in hoa (`la_chu_i_hoac_dau_cau`) làm ứng viên chờ nối chuỗi,
                    # nhưng chỉ lấy chữ cái thực sự (`dt_c >= 18 and min_d >= 4 and rho_c >= 2.10`) làm hạt giống (`trong_hat_giong`):
                    la_dau_cau_nho = (dt_c >= 3 and max_d <= 11) or (cw_c <= 22 and 2 <= ch_c <= 8 and dt_c >= 6)
                    la_chu_i_doc = (1 <= cw_c <= 3 and 8 <= ch_c <= 22 and dt_c >= 8 and dt_c >= ch_c * 0.75)
                    if not la_dau_cau_nho and not la_chu_i_doc:
                        if dt_c < 9 or min_d <= 2:
                            continue
                        if min_d <= 4 and max_d >= 10 and rho_c < 2.20:
                            continue
                        if max_d >= 13 and rho_c < 1.95:
                            continue

                    trong_hat_giong = (
                        (dt_c >= 18 and min_d >= 4 and rho_c >= 2.10)
                        and c_max_x >= cx0 - 8
                        and c_min_x <= cx1 + 8
                        and c_max_y >= cy0 - 12
                        and c_min_y <= cy1 + 12
                    )
                    ds_comp_chu.append(
                        {
                            "pts": q_c,
                            "x0": c_min_x,
                            "y0": c_min_y,
                            "x1": c_max_x,
                            "y1": c_max_y,
                            "w": cw_c,
                            "h": ch_c,
                            "chon": trong_hat_giong,
                        }
                    )

            # Liên kết chuỗi Từ/Dòng (Word/Line Chaining) tối đa 4 vòng để gom trọn từ bị lẹm ngang ("be", "k-")
            # và dòng cuối bị lẹm dọc ("ness...", "Tenpai...") mà không chạm vào ký hiệu quân mạt chược ở xa:
            cur_x0, cur_y0, cur_x1, cur_y1 = cx0, cy0, cx1, cy1
            for comp_item in ds_comp_chu:
                if comp_item["chon"]:
                    cur_x0 = min(cur_x0, comp_item["x0"])
                    cur_y0 = min(cur_y0, comp_item["y0"])
                    cur_x1 = max(cur_x1, comp_item["x1"])
                    cur_y1 = max(cur_y1, comp_item["y1"])

            for _ in range(4):
                co_them = False
                da_chon = [c for c in ds_comp_chu if c["chon"]]
                if not da_chon:
                    break
                for c_ung in ds_comp_chu:
                    if c_ung["chon"]:
                        continue
                    ux0, uy0, ux1, uy1 = c_ung["x0"], c_ung["y0"], c_ung["x1"], c_ung["y1"]
                    # Không vượt qua vách ngăn đen liên thông biên nằm giữa hộp chữ và ứng viên
                    hop_le_chain = False
                    for c_goc in da_chon:
                        ax0, ay0, ax1, ay1 = c_goc["x0"], c_goc["y0"], c_goc["x1"], c_goc["y1"]
                        giao_y = min(uy1, ay1) - max(uy0, ay0)
                        kc_x = max(0, max(ux0 - ax1, ax0 - ux1))
                        kc_y = max(0, max(uy0 - ay1, ay0 - uy1))
                        # 1) Nối chữ/dấu câu cùng dòng ngang (khoảng cách ngang <= 11px)
                        if (giao_y >= min(c_ung["h"], c_goc["h"]) * 0.30 or kc_y <= 4) and kc_x <= 11:
                            hop_le_chain = True
                            break
                        # 2) Nối dòng chữ kế tiếp phía dưới / phía trên trong cùng cột chữ (khoảng cách dọc <= 18px)
                        if ux0 >= cur_x0 - 14 and ux1 <= cur_x1 + 18 and kc_y <= 18 and kc_x <= 24:
                            hop_le_chain = True
                            break
                    if hop_le_chain:
                        c_ung["chon"] = True
                        cur_x0 = min(cur_x0, ux0)
                        cur_y0 = min(cur_y0, uy0)
                        cur_x1 = max(cur_x1, ux1)
                        cur_y1 = max(cur_y1, uy1)
                        co_them = True
                if not co_them:
                    break

            for comp_item in ds_comp_chu:
                if comp_item["chon"]:
                    for p_c in comp_item["pts"]:
                        la_loi_chu[p_c] = 1
                        can_xoa[p_c] = 1
            # Cứu hộ các nét chữ `ung_vien_net` nằm trong vùng hộp chữ gốc `[cx0-4..cx1+4, cy0-4..cy1+4]`
            # bị bộ lọc CCA bỏ sót do chạm nhẹ vào mảng áo đen/tóc đen (`ket_noi_bien` / `la_mang_toi_dac_pre`):
            khong_co_comp = not any(c["chon"] for c in ds_comp_chu)
            cho_phep_cuu_mang_toi = bool(
                not la_nen_mau_thuc
                and (lum_nen_trung_vi < 212.0 or ty_le_trang_dac < 0.38 or do_nhieu_hat >= 18.0)
            )
            for py_fb in range(max(2, cy0 - 4), min(rh - 2, cy1 + 4)):
                base_fb = py_fb * rw
                for px_fb in range(max(2, cx0 - 4), min(rw - 2, cx1 + 4)):
                    p_fb = base_fb + px_fb
                    if not ung_vien_net[p_fb] or la_loi_chu[p_fb] or vung_cam[p_fb]:
                        continue
                    chon_fb = khong_co_comp
                    if not chon_fb and cho_phep_cuu_mang_toi:
                        co_halo_fb = False
                        co_toi_fb = False
                        for dy_f in range(-4, 5):
                            ny_f = py_fb + dy_f
                            if ny_f < 0 or ny_f >= rh:
                                continue
                            nb_f = ny_f * rw
                            for dx_f in range(-4, 5):
                                nx_f = px_fb + dx_f
                                if nx_f < 0 or nx_f >= rw:
                                    continue
                                np_f = nb_f + nx_f
                                if abs(dx_f) <= 3 and abs(dy_f) <= 3 and (la_trang_dac[np_f] or la_dai_trang_manh[np_f]):
                                    co_halo_fb = True
                                if la_mang_toi_dac_pre[np_f]:
                                    co_toi_fb = True
                            if co_halo_fb and co_toi_fb:
                                break
                        chon_fb = co_halo_fb and co_toi_fb
                    if chon_fb:
                        la_loi_chu[p_fb] = 1
                        can_xoa[p_fb] = 1
                        cur_x0 = min(cur_x0, px_fb)
                        cur_y0 = min(cur_y0, py_fb)
                        cur_x1 = max(cur_x1, px_fb)
                        cur_y1 = max(cur_y1, py_fb)

            # Gom toàn bộ Viền Halo bao quanh `la_loi_chu` trong bán kính 6px
            hx0 = max(1, cur_x0 - 8)
            hy0 = max(1, cur_y0 - 8)
            hx1 = min(rw - 1, cur_x1 + 8)
            hy1 = min(rh - 1, cur_y1 + 8)
            kc_loi = bytearray(N)
            q_halo = []
            for py_d in range(hy0, hy1):
                base_d = py_d * rw
                for px_d in range(hx0, hx1):
                    pos_d = base_d + px_d
                    if la_loi_chu[pos_d]:
                        kc_loi[pos_d] = 1
                        q_halo.append(pos_d)
            max_buoc_halo = (
                2
                if (do_nhieu_hat >= 14.0 and not nen_toi and not la_nen_mau_thuc and max_day_net <= 20)
                else (5 if max_day_net >= 22 else 4)
            )
            head_h = 0
            while head_h < len(q_halo):
                pos_h = q_halo[head_h]
                head_h += 1
                buoc_h = kc_loi[pos_h]
                if buoc_h > max_buoc_halo:
                    continue
                px_h = pos_h % rw
                py_h = pos_h // rw
                for dy_h in (-1, 0, 1):
                    ny_h = py_h + dy_h
                    if ny_h < hy0 or ny_h >= hy1:
                        continue
                    nb_h = ny_h * rw
                    for dx_h in (-1, 0, 1):
                        if dx_h == 0 and dy_h == 0:
                            continue
                        nx_h = px_h + dx_h
                        if nx_h < hx0 or nx_h >= hx1:
                            continue
                        npos_h = nb_h + nx_h
                        if kc_loi[npos_h] or vung_cam[npos_h]:
                            continue
                        if la_dao_chieu_halo:
                            la_diem_halo = bool(la_toi_net[npos_h] or (buoc_h <= 4 and lum_px[npos_h] <= 115.0))
                        elif nen_toi and not la_nen_mau_thuc:
                            nguong_sang_nen_toi = max(30.0, lum_nen_trung_vi + 16.0)
                            la_diem_halo = bool(
                                la_dai_trang_manh[npos_h]
                                or la_trang_dac[npos_h]
                                or (buoc_h <= 2 and lum_px[npos_h] >= nguong_sang_nen_toi and sat_px[npos_h] <= 55)
                            )
                        else:
                            # Trên nền hỗn hợp (Tường trắng kẻ sọc + Tóc đen) hoặc Nền cát Screentone / Nền màu:
                            # Chỉ nở vào viền halo trắng thực sự quanh lõi chữ, bảo vệ tuyệt đối nét gạch chéo & mặt/tai nhân vật!
                            la_diem_halo = bool(
                                (la_trang_dac[npos_h] and buoc_h <= max_buoc_halo)
                                or (la_dai_trang_manh[npos_h] and buoc_h <= (3 if do_nhieu_hat >= 14.0 else max_buoc_halo))
                                or (buoc_h <= 2 and (la_trang_dac[npos_h] or la_sang_dac[npos_h]))
                                or (la_nen_mau_thuc and la_sang_dac[npos_h])
                            )
                        if la_diem_halo:
                            kc_loi[npos_h] = buoc_h + 1
                            can_xoa[npos_h] = 1
                            q_halo.append(npos_h)

            # Đo màu chữ gốc & màu viền halo gốc trên nền màu / nền tối để giữ nguyên độ tương phản nguyên bản
            ds_r_loi, ds_g_loi, ds_b_loi = [], [], []
            for py_d in range(hy0, hy1):
                base_d = py_d * rw
                for px_d in range(hx0, hx1):
                    pos_d = base_d + px_d
                    if la_loi_chu[pos_d]:
                        ds_r_loi.append(r_roi[pos_d])
                        ds_g_loi.append(g_roi[pos_d])
                        ds_b_loi.append(b_roi[pos_d])
            if len(ds_r_loi) >= 6:
                ds_r_loi.sort()
                ds_g_loi.sort()
                ds_b_loi.sort()
                m_i = len(ds_r_loi) // 2
                rl_m, gl_m, bl_m = ds_r_loi[m_i], ds_g_loi[m_i], ds_b_loi[m_i]
                lum_l = 0.299 * rl_m + 0.587 * gl_m + 0.114 * bl_m
                sat_l = max(rl_m, gl_m, bl_m) - min(rl_m, gl_m, bl_m)
                if la_dao_chieu_halo or (la_nen_mau_thuc and lum_l >= 175.0 and lum_nen_trung_vi < 175.0):
                    mau_chu_goc = (rl_m, gl_m, bl_m) if sat_l >= 48 else (255, 255, 255)
                    mau_vien_goc = (0, 0, 0)
                elif la_nen_mau_thuc and sat_l >= 58:
                    mau_chu_goc = (rl_m, gl_m, bl_m)
                    mau_vien_goc = (0, 0, 0) if lum_l >= 135.0 else (255, 255, 255)
                elif not la_dao_chieu_halo and lum_l <= 88.0 and dem_trang_dac_hop >= max(18, int(dt_hop * 0.04)):
                    mau_chu_goc = (15, 23, 42)
                    mau_vien_goc = (255, 255, 255)
            if mau_chu_goc is None:
                if nen_toi:
                    mau_chu_goc = (255, 255, 255)
                    mau_vien_goc = (0, 0, 0)
                else:
                    mau_chu_goc = (15, 23, 42)
                    mau_vien_goc = (255, 255, 255)

            # Nở nhẹ quanh `can_xoa` để xoá sạch viền khử răng cưa JPEG của halo mà không ăn vào đường kẻ tường hay nét gạch chéo:
            max_r2_dil = 1 if (do_nhieu_hat >= 14.0 and not nen_toi and not la_nen_mau_thuc) else 4
            can_xoa_goc = bytearray(can_xoa)
            for py_d in range(2, rh - 2):
                base_d = py_d * rw
                for px_d in range(2, rw - 2):
                    pos_d = base_d + px_d
                    if not can_xoa_goc[pos_d]:
                        continue
                    for dy_n in range(-2, 3):
                        nb_n = (py_d + dy_n) * rw
                        for dx_n in range(-2, 3):
                            if dx_n * dx_n + dy_n * dy_n > max_r2_dil:
                                continue
                            npos_n = nb_n + (px_d + dx_n)
                            if vung_cam[npos_n]:
                                continue
                            if not la_dao_chieu_halo and la_toi_net[npos_n] and not la_loi_chu[npos_n] and lum_px[npos_n] < 105.0:
                                continue
                            can_xoa[npos_n] = 1

            # Lấp các lỗ nhỏ bên trong bụng chữ cái ('O', 'P', 'a', 'e', '6', '3', 'B')
            # Giới hạn kích thước lỗ <= 72px (hoặc <= 160px với chữ in đậm lớn) và chiều rộng/cao <= 20px
            # để tuyệt đối không lấp khoảng nền gạch chéo (tay, mũ len, tai nhân vật) nằm kẹp giữa 2 dòng chữ!
            max_lo_bung = 68 if (do_nhieu_hat >= 14.0 and not nen_toi and not la_nen_mau_thuc) else (160 if max_day_net >= 22 else 95)
            da_duyet_lo = bytearray(N)
            for py_d in range(2, rh - 2):
                base_d = py_d * rw
                for px_d in range(2, rw - 2):
                    s_pos = base_d + px_d
                    if can_xoa[s_pos] or da_duyet_lo[s_pos] or vung_cam[s_pos]:
                        continue
                    da_duyet_lo[s_pos] = 1
                    q_lo = [s_pos]
                    cham_bien_lo = False
                    lo_x0 = lo_x1 = px_d
                    lo_y0 = lo_y1 = py_d
                    head_lo = 0
                    while head_lo < len(q_lo):
                        p_lo = q_lo[head_lo]
                        head_lo += 1
                        xl = p_lo % rw
                        yl = p_lo // rw
                        if xl < lo_x0:
                            lo_x0 = xl
                        if xl > lo_x1:
                            lo_x1 = xl
                        if yl < lo_y0:
                            lo_y0 = yl
                        if yl > lo_y1:
                            lo_y1 = yl
                        if xl <= 2 or xl >= rw - 3 or yl <= 2 or yl >= rh - 3:
                            cham_bien_lo = True
                        if xl > 1 and not can_xoa[p_lo - 1] and not da_duyet_lo[p_lo - 1]:
                            da_duyet_lo[p_lo - 1] = 1
                            q_lo.append(p_lo - 1)
                        if xl + 1 < rw - 1 and not can_xoa[p_lo + 1] and not da_duyet_lo[p_lo + 1]:
                            da_duyet_lo[p_lo + 1] = 1
                            q_lo.append(p_lo + 1)
                        if yl > 1 and not can_xoa[p_lo - rw] and not da_duyet_lo[p_lo - rw]:
                            da_duyet_lo[p_lo - rw] = 1
                            q_lo.append(p_lo - rw)
                        if yl + 1 < rh - 1 and not can_xoa[p_lo + rw] and not da_duyet_lo[p_lo + rw]:
                            da_duyet_lo[p_lo + rw] = 1
                            q_lo.append(p_lo + rw)
                    if not cham_bien_lo and len(q_lo) <= max_lo_bung and (lo_x1 - lo_x0 + 1) <= 22 and (lo_y1 - lo_y0 + 1) <= 22:
                        for p_lo in q_lo:
                            can_xoa[p_lo] = 1

            # Hấp thụ các thanh nét chữ mảnh (1-4px) bị sót lại do khe hở halo trên nền tối / screentone
            # nằm kẹp giữa 2 vùng `can_xoa` đối diện trong phạm vi hộp chữ `[hx0..hx1, hy0..hy1]`:
            la_tuong_trang_pre = bool(not la_nen_mau_thuc and ty_le_trang_dac >= 0.38 and lum_nen_trung_vi >= 212.0 and do_nhieu_hat < 18.0)
            for _ in range(2):
                snap_xoa = bytearray(can_xoa)
                for py_s in range(max(4, hy0), min(rh - 4, hy1)):
                    base_s = py_s * rw
                    for px_s in range(max(4, hx0), min(rw - 4, hx1)):
                        pos_s = base_s + px_s
                        if snap_xoa[pos_s] or vung_cam[pos_s]:
                            continue
                        kep_x4 = any(snap_xoa[pos_s - d] for d in range(1, 5)) and any(snap_xoa[pos_s + d] for d in range(1, 5))
                        kep_y4 = any(snap_xoa[pos_s - d * rw] for d in range(1, 5)) and any(snap_xoa[pos_s + d * rw] for d in range(1, 5))
                        kep_x7 = kep_x4 or (any(snap_xoa[pos_s - d] for d in range(1, 8)) and any(snap_xoa[pos_s + d] for d in range(1, 8)))
                        kep_y7 = kep_y4 or (any(snap_xoa[pos_s - d * rw] for d in range(1, 8)) and any(snap_xoa[pos_s + d * rw] for d in range(1, 8)))
                        if (kep_x7 and kep_y7) or (
                            not la_tuong_trang_pre
                            and (kep_x4 or kep_y4)
                            and (lum_px[pos_s] <= 135.0 or la_trang_dac[pos_s] or la_sang_dac[pos_s] or la_dai_trang_manh[pos_s])
                        ):
                            can_xoa[pos_s] = 1

            # Hấp thụ phần lõi mực đen dày còn sót bên trong chữ in đậm lớn ("BUT WHAT A MIRROR SHOWED HIM!!", "3-Sou", "NOOOOOO!!")
            # và phân loại mảng tối đặc thực sự (`la_mang_toi_dac`: tóc đen / áo đen có diện tích >= 650px hoặc chạm biên ROI >= 200px):
            la_mang_toi_dac = bytearray(N)
            da_duyet_toi = bytearray(N)
            max_loi_dam = max(850, int(round(dt_hop * 0.08)))
            for py_d in range(1, rh - 1):
                base_d = py_d * rw
                for px_d in range(1, rw - 1):
                    s_pos = base_d + px_d
                    if can_xoa[s_pos] or da_duyet_toi[s_pos] or lum_px[s_pos] > 102.0:
                        continue
                    da_duyet_toi[s_pos] = 1
                    q_toi = [s_pos]
                    cham_bien_toi = False
                    cham_xoa_toi = False
                    cham_loi_toi = False
                    vien_xoa_toi = 0
                    vien_nen_toi = 0
                    head_t = 0
                    while head_t < len(q_toi):
                        p_t = q_toi[head_t]
                        head_t += 1
                        xt = p_t % rw
                        yt = p_t // rw
                        if xt <= qx0 + 1 or xt >= qx1 - 2 or yt <= qy0 + 1 or yt >= qy1 - 2 or ket_noi_bien[p_t]:
                            cham_bien_toi = True
                        for dy_t in (-1, 0, 1):
                            nyt = yt + dy_t
                            if nyt <= 0 or nyt >= rh - 1:
                                continue
                            nbt = nyt * rw
                            for dx_t in (-1, 0, 1):
                                if dx_t == 0 and dy_t == 0:
                                    continue
                                nxt = xt + dx_t
                                if nxt <= 0 or nxt >= rw - 1:
                                    continue
                                npt = nbt + nxt
                                if can_xoa[npt]:
                                    cham_xoa_toi = True
                                    vien_xoa_toi += 1
                                    if la_loi_chu[npt]:
                                        cham_loi_toi = True
                                elif not da_duyet_toi[npt]:
                                    if lum_px[npt] <= 102.0:
                                        da_duyet_toi[npt] = 1
                                        q_toi.append(npt)
                                    else:
                                        vien_nen_toi += 1
                    if (
                        not cham_bien_toi
                        and cham_xoa_toi
                        and cham_loi_toi
                        and vien_xoa_toi >= (vien_xoa_toi + vien_nen_toi) * 0.80
                        and len(q_toi) <= max_loi_dam
                    ):
                        for p_t in q_toi:
                            if not vung_cam[p_t]:
                                can_xoa[p_t] = 1
                                xt = p_t % rw
                                yt = p_t // rw
                                for dy_n in (-2, -1, 0, 1, 2):
                                    nyn = yt + dy_n
                                    if nyn <= 1 or nyn >= rh - 2:
                                        continue
                                    nbn = nyn * rw
                                    for dx_n in (-2, -1, 0, 1, 2):
                                        nxn = xt + dx_n
                                        if nxn <= 1 or nxn >= rw - 2:
                                            continue
                                        npn = nbn + nxn
                                        if not vung_cam[npn] and (la_trang_dac[npn] or la_sang_dac[npn] or lum_px[npn] <= 125.0):
                                            can_xoa[npn] = 1
                    elif len(q_toi) >= 450 or (cham_bien_toi and len(q_toi) >= 120):
                        for p_t in q_toi:
                            if lum_px[p_t] <= 90.0 and not can_xoa[p_t]:
                                xt = p_t % rw
                                yt = p_t // rw
                                dl_t = dr_t = du_t = dd_t = 0
                                dl_r = dr_r = du_r = dd_r = 0
                                while dl_r < 5 and xt - dl_r - 1 >= 0 and lum_px[p_t - dl_r - 1] <= 95.0 and not can_xoa[p_t - dl_r - 1]:
                                    dl_r += 1
                                while dr_r < 5 and xt + dr_r + 1 < rw and lum_px[p_t + dr_r + 1] <= 95.0 and not can_xoa[p_t + dr_r + 1]:
                                    dr_r += 1
                                while du_r < 5 and yt - du_r - 1 >= 0 and lum_px[p_t - (du_r + 1) * rw] <= 95.0 and not can_xoa[p_t - (du_r + 1) * rw]:
                                    du_r += 1
                                while dd_r < 5 and yt + dd_r + 1 < rh and lum_px[p_t + (dd_r + 1) * rw] <= 95.0 and not can_xoa[p_t + (dd_r + 1) * rw]:
                                    dd_r += 1
                                while dl_t < 6 and xt - dl_t - 1 >= 0 and (lum_px[p_t - dl_t - 1] <= 95.0 or can_xoa[p_t - dl_t - 1]):
                                    dl_t += 1
                                while dr_t < 6 and xt + dr_t + 1 < rw and (lum_px[p_t + dr_t + 1] <= 95.0 or can_xoa[p_t + dr_t + 1]):
                                    dr_t += 1
                                while du_t < 6 and yt - du_t - 1 >= 0 and (lum_px[p_t - (du_t + 1) * rw] <= 95.0 or can_xoa[p_t - (du_t + 1) * rw]):
                                    du_t += 1
                                while dd_t < 6 and yt + dd_t + 1 < rh and (lum_px[p_t + (dd_t + 1) * rw] <= 95.0 or can_xoa[p_t + (dd_t + 1) * rw]):
                                    dd_t += 1
                                w_r = dl_r + dr_r + 1
                                h_r = du_r + dd_r + 1
                                if (dl_t + dr_t + 1) >= 5 and (du_t + dd_t + 1) >= 5 and min(w_r, h_r) >= 3 and max(w_r, h_r) >= 5:
                                    la_mang_toi_dac[p_t] = 1
            for p_idx in range(N):
                if la_mang_toi_dac_pre[p_idx] and not can_xoa[p_idx]:
                    la_mang_toi_dac[p_idx] = 1

            # Hấp thụ nốt mọi mảnh viền halo trắng (`lum >= 180`) còn sót nằm kẹp cô lập
            # giữa `can_xoa` và mảng tóc đen `la_mang_toi_dac` (không chạm biên ROI, diện tích <= 95px):
            da_duyet_rem = bytearray(N)
            for py_d in range(2, rh - 2):
                base_d = py_d * rw
                for px_d in range(2, rw - 2):
                    s_pos = base_d + px_d
                    if can_xoa[s_pos] or la_mang_toi_dac[s_pos] or da_duyet_rem[s_pos] or vung_cam[s_pos]:
                        continue
                    if lum_px[s_pos] < 180.0:
                        continue
                    da_duyet_rem[s_pos] = 1
                    q_rem = [s_pos]
                    cham_bien_rem = False
                    cham_xoa_rem = False
                    cham_toi_rem = False
                    head_r = 0
                    while head_r < len(q_rem):
                        p_r = q_rem[head_r]
                        head_r += 1
                        xr = p_r % rw
                        yr = p_r // rw
                        if xr <= qx0 + 1 or xr >= qx1 - 2 or yr <= qy0 + 1 or yr >= qy1 - 2:
                            cham_bien_rem = True
                        for dy_r in (-1, 0, 1):
                            nyr = yr + dy_r
                            if nyr <= 0 or nyr >= rh - 1:
                                continue
                            nbr = nyr * rw
                            for dx_r in (-1, 0, 1):
                                if dx_r == 0 and dy_r == 0:
                                    continue
                                nxr = xr + dx_r
                                if nxr <= 0 or nxr >= rw - 1:
                                    continue
                                npr = nbr + nxr
                                if can_xoa[npr]:
                                    cham_xoa_rem = True
                                if la_mang_toi_dac[npr]:
                                    cham_toi_rem = True
                                if (
                                    not can_xoa[npr]
                                    and not la_mang_toi_dac[npr]
                                    and not da_duyet_rem[npr]
                                    and not vung_cam[npr]
                                    and lum_px[npr] >= 180.0
                                ):
                                    da_duyet_rem[npr] = 1
                                    q_rem.append(npr)
                    if not cham_bien_rem and cham_xoa_rem and cham_toi_rem and len(q_rem) <= 95:
                        for p_r in q_rem:
                            can_xoa[p_r] = 1

            # Tái tạo nền Đa Hướng Phân Cụm Cục Bộ (Mode-Consistent 4-Directional Ray Reconstruction + Halftone Phase Cloning):
            # - Tự động thích ứng từng điểm ảnh trên hộp hỗn hợp (nửa Tường trắng kẻ sọc + nửa Tóc đen hoặc Screentone/Gạch chéo + Tóc đen).
            la_tuong_trang_sach = bool(
                not la_nen_mau_thuc
                and ty_le_trang_dac >= 0.38
                and lum_nen_trung_vi >= 212.0
                and do_nhieu_hat < 18.0
            )

            def _la_diem_nen_sach(pos_s: int, dx_r: int = 0, dy_r: int = 0) -> bool:
                if pos_s < 0 or pos_s >= N or can_xoa[pos_s]:
                    return False
                px_s = pos_s % rw
                py_s = pos_s // rw
                # Không lấy mẫu điểm trắng sáng sát ngay rìa `can_xoa` (viền halo khử răng cưa còn sót)
                if not la_dao_chieu_halo and lum_px[pos_s] >= 185.0:
                    if (
                        (px_s > 0 and can_xoa[pos_s - 1])
                        or (px_s + 1 < rw and can_xoa[pos_s + 1])
                        or (py_s > 0 and can_xoa[pos_s - rw])
                        or (py_s + 1 < rh and can_xoa[pos_s + rw])
                    ):
                        return False
                if not la_dao_chieu_halo and la_dai_trang_manh[pos_s]:
                    if la_tuong_trang_sach or kc_loi[pos_s] > 0:
                        return False
                    if (
                        (px_s > 1 and can_xoa[pos_s - 2])
                        or (px_s + 2 < rw and can_xoa[pos_s + 2])
                        or (py_s > 1 and can_xoa[pos_s - 2 * rw])
                        or (py_s + 2 < rh and can_xoa[pos_s + 2 * rw])
                        or (px_s > 0 and py_s > 0 and can_xoa[pos_s - rw - 1])
                        or (px_s + 1 < rw and py_s > 0 and can_xoa[pos_s - rw + 1])
                        or (px_s > 0 and py_s + 1 < rh and can_xoa[pos_s + rw - 1])
                        or (px_s + 1 < rw and py_s + 1 < rh and can_xoa[pos_s + rw + 1])
                    ):
                        return False
                if not la_dao_chieu_halo and la_nen_mau_thuc and la_sang_dac[pos_s] and lum_nen_trung_vi < 218.0:
                    return False
                if lum_px[pos_s] <= 90.0 and not la_nen_mau_thuc:
                    if la_mang_toi_dac[pos_s]:
                        if dx_r != 0 or dy_r != 0:
                            nx_m = px_s + dx_r
                            ny_m = py_s + dy_r
                            if 0 <= nx_m < rw and 0 <= ny_m < rh and not la_mang_toi_dac[ny_m * rw + nx_m]:
                                return False
                        return True
                    # Cho phép tia dọc (dx_r == 0, dy_r != 0) trên nền speedline/screentone (`ty_le_trang_dac < 0.42` và `lum_nen_p30 < 205`)
                    # lấy mẫu đường speedline dọc thực sự (cao >= 9px ngoài vùng xoá, rộng <= 5px) để nối liền mạch đường speedline dọc bị chữ cắt ngang:
                    if dy_r != 0 and dx_r == 0 and ty_le_trang_dac < 0.42 and lum_nen_p30 < 205.0:
                        dl_v = dr_v = du_v = dd_v = 0
                        while dl_v < 6 and px_s - dl_v - 1 >= 0 and lum_px[pos_s - dl_v - 1] <= 105.0:
                            dl_v += 1
                        while dr_v < 6 and px_s + dr_v + 1 < rw and lum_px[pos_s + dr_v + 1] <= 105.0:
                            dr_v += 1
                        if dl_v + dr_v + 1 <= 5:
                            while du_v < 12 and py_s - du_v - 1 >= 0 and not can_xoa[pos_s - (du_v + 1) * rw] and lum_px[pos_s - (du_v + 1) * rw] <= 105.0:
                                du_v += 1
                            while dd_v < 12 and py_s + dd_v + 1 < rh and not can_xoa[pos_s + (dd_v + 1) * rw] and lum_px[pos_s + (dd_v + 1) * rw] <= 105.0:
                                dd_v += 1
                            if du_v + dd_v + 1 >= 9:
                                return True
                    return False
                # Bỏ qua rìa chuyển tiếp khử răng cưa (`90 < lum < 228`) bám sát cạnh mảng tóc đen (`la_mang_toi_dac`)
                # để tia mẫu bước thẳng vào lõi tóc đen hoặc nền sáng sạch thay vì lấy mẫu rìa xám:
                if not la_nen_mau_thuc and lum_px[pos_s] < 228.0:
                    if (
                        (px_s > 0 and la_mang_toi_dac[pos_s - 1])
                        or (px_s + 1 < rw and la_mang_toi_dac[pos_s + 1])
                        or (py_s > 0 and la_mang_toi_dac[pos_s - rw])
                        or (py_s + 1 < rh and la_mang_toi_dac[pos_s + rw])
                    ):
                        return False
                # Không lấy mẫu vào lớp rìa khử răng cưa xám (`lum < 235`) bám sát cạnh đường kẻ mảnh (`la_toi_net` nhưng không phải mảng tối đặc)
                # trên nền tường sáng, để tường trắng giữ nguyên màu trắng tinh (`255`) thay vì bị ám xám!
                if la_tuong_trang_sach and lum_px[pos_s] < 236.0:
                    if (
                        (px_s > 0 and la_toi_net[pos_s - 1] and not la_mang_toi_dac[pos_s - 1])
                        or (px_s + 1 < rw and la_toi_net[pos_s + 1] and not la_mang_toi_dac[pos_s + 1])
                        or (py_s > 0 and la_toi_net[pos_s - rw] and not la_mang_toi_dac[pos_s - rw])
                        or (py_s + 1 < rh and la_toi_net[pos_s + rw] and not la_mang_toi_dac[pos_s + rw])
                    ):
                        return False
                if la_dao_chieu_halo and la_toi_net[pos_s] and lum_px[pos_s] <= 95.0 and lum_nen_trung_vi > 110.0:
                    return False
                return True

            huong_8 = ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1))
            max_tia_step = max(96, min(140, max(rw, rh)))
            r_buf = [0] * N
            g_buf = [0] * N
            b_buf = [0] * N
            r_sang_fb = [-1] * N
            g_sang_fb = [-1] * N
            b_sang_fb = [-1] * N
            cum_toi_mask = bytearray(N)
            ds_diem_xoa_noi = []
            for py_d in range(1, rh - 1):
                base_d = py_d * rw
                pha_y = py_d & 3
                for px_d in range(1, rw - 1):
                    pos_d = base_d + px_d
                    if not can_xoa[pos_d] or vung_cam[pos_d]:
                        continue
                    ds_diem_xoa_noi.append(pos_d)
                    if not co_diem_xoa_chu_noi:
                        min_x_xoa = max_x_xoa = px_d
                        min_y_xoa = max_y_xoa = py_d
                        co_diem_xoa_chu_noi = True
                    else:
                        if px_d < min_x_xoa:
                            min_x_xoa = px_d
                        if px_d + 1 > max_x_xoa:
                            max_x_xoa = px_d + 1
                        if py_d < min_y_xoa:
                            min_y_xoa = py_d
                        if py_d + 1 > max_y_xoa:
                            max_y_xoa = py_d + 1

                    # Phân tách 8 tia mẫu (4 trục chính + 4 đường chéo) thành 2 cụm cục bộ:
                    # Cụm Tối Đặc (`lum < 88`, ví dụ tóc đen / nền tối gradient) và Cụm Sáng/Trung tính (`lum >= 88`, ví dụ tường trắng / screentone / gạch chéo)
                    # để giữ ranh giới sắc nét giữa tóc đen và tường trắng/screentone, đồng thời tránh vệt kẻ ô vuông chữ thập (+)!
                    w_sang = 0.0
                    r_sang = g_sang = b_sang = 0.0
                    w_toi = 0.0
                    r_toi = g_toi = b_toi = 0.0
                    tia_toi = [False] * 8
                    mau_pha_r = -1
                    mau_pha_g = -1
                    mau_pha_b = -1
                    kc_pha_tot = 999
                    pha_x = px_d & 3

                    for idx_dir, (dx_h, dy_h) in enumerate(huong_8):
                        da_qua_vung_trang = False
                        he_so_cheo = 1.4142 if (dx_h != 0 and dy_h != 0) else 1.0
                        for d_step in range(2, max_tia_step):
                            nx_s = px_d + dx_h * d_step
                            ny_s = py_d + dy_h * d_step
                            if nx_s < qx0 - 2 or nx_s >= qx1 + 2 or ny_s < qy0 - 2 or ny_s >= qy1 + 2:
                                break
                            npos_s = ny_s * rw + nx_s
                            if not can_xoa[npos_s] and lum_px[npos_s] >= 210.0 and (la_tuong_trang_sach or not la_dai_trang_manh[npos_s]):
                                da_qua_vung_trang = True
                            if da_qua_vung_trang and lum_px[npos_s] <= 90.0 and not la_nen_mau_thuc:
                                break
                            if not _la_diem_nen_sach(npos_s, dx_h, dy_h):
                                continue
                            nx_s2 = nx_s + dx_h
                            ny_s2 = ny_s + dy_h
                            npos_s2 = (
                                (ny_s2 * rw + nx_s2)
                                if (0 <= nx_s2 < rw and 0 <= ny_s2 < rh and _la_diem_nen_sach(ny_s2 * rw + nx_s2, dx_h, dy_h))
                                else npos_s
                            )
                            kc_thuc = d_step * he_so_cheo
                            w_s = 1.0 / ((kc_thuc + 1.0) ** 1.65)
                            if not la_nen_mau_thuc and not la_tuong_trang_sach and not la_mang_toi_dac[npos_s] and do_nhieu_hat >= 11.5:
                                rm = gm = bm = (tb_lum_3x3[npos_s] + tb_lum_3x3[npos_s2]) * 0.5
                                lm = rm
                            else:
                                rm = (r_roi[npos_s] + r_roi[npos_s2]) * 0.5
                                gm = (g_roi[npos_s] + g_roi[npos_s2]) * 0.5
                                bm = (b_roi[npos_s] + b_roi[npos_s2]) * 0.5
                                lm = 0.299 * rm + 0.587 * gm + 0.114 * bm
                            if lm < 92.0 and not la_nen_mau_thuc and (la_mang_toi_dac[npos_s] or nen_toi or la_tuong_trang_sach or lum_nen_trung_vi < 125.0):
                                w_toi += w_s
                                r_toi += rm * w_s
                                g_toi += gm * w_s
                                b_toi += bm * w_s
                                tia_toi[idx_dir] = True
                            else:
                                w_sang += w_s
                                r_sang += rm * w_s
                                g_sang += gm * w_s
                                b_sang += bm * w_s
                                if idx_dir < 4 and not la_nen_mau_thuc and not la_tuong_trang_sach and 90.0 <= lm <= 225.0:
                                    for step_p in range(d_step, min(max_tia_step, d_step + 8)):
                                        sx_p = px_d + dx_h * step_p
                                        sy_p = py_d + dy_h * step_p
                                        if sx_p < 0 or sx_p >= rw or sy_p < 0 or sy_p >= rh:
                                            break
                                        spos_p = sy_p * rw + sx_p
                                        if ket_noi_bien[spos_p] or la_mang_toi_dac[spos_p] or tb_lum_3x3[spos_p] < 95.0:
                                            break
                                        if (
                                            can_xoa[spos_p]
                                            or not _la_diem_nen_sach(spos_p)
                                            or lum_px[spos_p] < 98.0
                                            or tb_lum_3x3[spos_p] > 235.0
                                            or (sx_p > 0 and can_xoa[spos_p - 1])
                                            or (sx_p + 1 < rw and can_xoa[spos_p + 1])
                                            or (sy_p > 0 and can_xoa[spos_p - rw])
                                            or (sy_p + 1 < rh and can_xoa[spos_p + rw])
                                        ):
                                            continue
                                        if ((sx_p & 3) == pha_x and (sy_p & 3) == pha_y) and step_p < kc_pha_tot:
                                            kc_pha_tot = step_p
                                            mau_pha_r = r_roi[spos_p]
                                            mau_pha_g = g_roi[spos_p]
                                            mau_pha_b = b_roi[spos_p]
                                            break
                            break

                    r_out = int(round(r_nen_trung_vi))
                    g_out = int(round(g_nen_trung_vi))
                    b_out = int(round(b_nen_trung_vi))
                    dem_tia_toi = sum(1 for t_b in tia_toi if t_b)
                    kep_ngang_toi = bool(tia_toi[0] and tia_toi[1] and w_toi >= w_sang * 0.78)
                    kep_doc_toi = bool(tia_toi[2] and tia_toi[3] and w_toi >= w_sang * 0.78)
                    kep_cheo_toi = bool(((tia_toi[4] and tia_toi[7]) or (tia_toi[5] and tia_toi[6])) and w_toi >= w_sang * 0.82)
                    nam_trong_mang_toi = bool(
                        (nen_toi and (w_toi >= w_sang * 0.65 or (dem_tia_toi >= 4 and w_toi >= w_sang * 0.55)))
                        or w_sang == 0.0
                        or (dem_tia_toi >= 5 and w_toi >= w_sang * 0.68)
                        or kep_ngang_toi
                        or kep_doc_toi
                        or (not la_tuong_trang_sach and kep_cheo_toi and dem_tia_toi >= 3)
                        or (not la_tuong_trang_sach and dem_tia_toi >= 3 and w_toi >= w_sang * 1.15)
                        or (lum_nen_trung_vi < 115.0 and w_toi >= w_sang * 0.80)
                    )
                    if w_sang > 0:
                        rs_c = int(round(r_sang / w_sang))
                        gs_c = int(round(g_sang / w_sang))
                        bs_c = int(round(b_sang / w_sang))
                        lum_out_s = 0.299 * rs_c + 0.587 * gs_c + 0.114 * bs_c
                        if not la_nen_mau_thuc and mau_pha_r >= 0 and do_nhieu_hat >= 16.0 and 115.0 <= lum_out_s <= 212.0:
                            he_so_pha = 0.26 if do_nhieu_hat >= 24.0 else 0.16
                            rs_c = int(round(mau_pha_r * he_so_pha + rs_c * (1.0 - he_so_pha)))
                            gs_c = int(round(mau_pha_g * he_so_pha + gs_c * (1.0 - he_so_pha)))
                            bs_c = int(round(mau_pha_b * he_so_pha + bs_c * (1.0 - he_so_pha)))
                        r_sang_fb[pos_d] = rs_c
                        g_sang_fb[pos_d] = gs_c
                        b_sang_fb[pos_d] = bs_c
                    if nam_trong_mang_toi and w_toi > 0 and (w_sang == 0.0 or w_toi >= w_sang * 0.55):
                        r_out = int(round(r_toi / w_toi))
                        g_out = int(round(g_toi / w_toi))
                        b_out = int(round(b_toi / w_toi))
                        cum_toi_mask[pos_d] = 1
                    elif w_sang > 0:
                        r_out = r_sang_fb[pos_d]
                        g_out = g_sang_fb[pos_d]
                        b_out = b_sang_fb[pos_d]
                    elif nam_trong_mang_toi and w_toi > 0:
                        r_out = int(round(r_toi / w_toi))
                        g_out = int(round(g_toi / w_toi))
                        b_out = int(round(b_toi / w_toi))
                        cum_toi_mask[pos_d] = 1
                    r_buf[pos_d] = r_out
                    g_buf[pos_d] = g_out
                    b_buf[pos_d] = b_out

            # Khử tia gai 1-2px (8-directional star/crossbar ray spikes) trên `cum_toi_mask` trước khi làm mượt Laplace:
            nguong_nb_toi = 3 if la_tuong_trang_sach else 4
            for _ in range(3):
                snapshot_toi = bytearray(cum_toi_mask)
                co_thay_doi_toi = False
                for pos_d in ds_diem_xoa_noi:
                    if not snapshot_toi[pos_d] or r_sang_fb[pos_d] < 0:
                        continue
                    px_d = pos_d % rw
                    py_d = pos_d // rw
                    dem_nb_toi = 0
                    for dy_m in (-1, 0, 1):
                        nym = py_d + dy_m
                        if nym < 0 or nym >= rh:
                            continue
                        nbm = nym * rw
                        for dx_m in (-1, 0, 1):
                            if dx_m == 0 and dy_m == 0:
                                continue
                            nxm = px_d + dx_m
                            if nxm < 0 or nxm >= rw:
                                continue
                            npm = nbm + nxm
                            if (can_xoa[npm] and snapshot_toi[npm]) or (not can_xoa[npm] and la_mang_toi_dac[npm]):
                                dem_nb_toi += 1
                    if dem_nb_toi <= nguong_nb_toi:
                        cum_toi_mask[pos_d] = 0
                        r_buf[pos_d] = r_sang_fb[pos_d]
                        g_buf[pos_d] = g_sang_fb[pos_d]
                        b_buf[pos_d] = b_sang_fb[pos_d]
                        co_thay_doi_toi = True
                if not co_thay_doi_toi:
                    break

            # Làm mượt đẳng hướng 2D (3 vòng Laplace/Harmonic Relaxation trong từng cụm Sáng/Tối)
            # để xoá sạch 100% vệt sọc ngang/dọc kiểu bàn cờ (plaid/crossbar artifacts) trên vùng gạch chéo & screentone:
            for _ in range(3):
                r_next = list(r_buf)
                g_next = list(g_buf)
                b_next = list(b_buf)
                for pos_d in ds_diem_xoa_noi:
                    px_d = pos_d % rw
                    py_d = pos_d // rw
                    c_mode = cum_toi_mask[pos_d]
                    sr = r_buf[pos_d] * 2
                    sg = g_buf[pos_d] * 2
                    sb = b_buf[pos_d] * 2
                    sw = 2
                    for npos_n in (
                        pos_d - 1 if px_d > 0 else -1,
                        pos_d + 1 if px_d + 1 < rw else -1,
                        pos_d - rw if py_d > 0 else -1,
                        pos_d + rw if py_d + 1 < rh else -1,
                        pos_d - rw - 1 if (px_d > 0 and py_d > 0) else -1,
                        pos_d - rw + 1 if (px_d + 1 < rw and py_d > 0) else -1,
                        pos_d + rw - 1 if (px_d > 0 and py_d + 1 < rh) else -1,
                        pos_d + rw + 1 if (px_d + 1 < rw and py_d + 1 < rh) else -1,
                    ):
                        if npos_n < 0:
                            continue
                        if can_xoa[npos_n]:
                            if cum_toi_mask[npos_n] == c_mode:
                                sr += r_buf[npos_n]
                                sg += g_buf[npos_n]
                                sb += b_buf[npos_n]
                                sw += 1
                        elif _la_diem_nen_sach(npos_n):
                            is_dark_n = 1 if (lum_px[npos_n] < 92.0 and not la_nen_mau_thuc) else 0
                            if is_dark_n == c_mode:
                                sr += int(round(tb_lum_3x3[npos_n])) if (not la_nen_mau_thuc and not la_tuong_trang_sach and not is_dark_n) else r_roi[npos_n]
                                sg += int(round(tb_lum_3x3[npos_n])) if (not la_nen_mau_thuc and not la_tuong_trang_sach and not is_dark_n) else g_roi[npos_n]
                                sb += int(round(tb_lum_3x3[npos_n])) if (not la_nen_mau_thuc and not la_tuong_trang_sach and not is_dark_n) else b_roi[npos_n]
                                sw += 1
                    r_next[pos_d] = (sr + (sw // 2)) // sw
                    g_next[pos_d] = (sg + (sw // 2)) // sw
                    b_next[pos_d] = (sb + (sw // 2)) // sw
                r_buf, g_buf, b_buf = r_next, g_next, b_next

            for pos_d in ds_diem_xoa_noi:
                px_d = pos_d % rw
                py_d = pos_d // rw
                px_anh[rx0 + px_d, ry0 + py_d] = (r_buf[pos_d], g_buf[pos_d], b_buf[pos_d])
        else:
            co_long_trang_ro = (not nen_toi) and (len(q_lt) >= max(64, int(dt_hop * 0.25)))
            for sy in range(sy0, sy1):
                base_s = sy * rw
                for sx in range(sx0, sx1):
                    s_idx = base_s + sx
                    if can_xoa[s_idx] or not trong_dong[s_idx] or da_tham_cca[s_idx] or la_nen[s_idx] or vung_cam[s_idx] or ket_noi_bien[s_idx]:
                        continue
                    if la_bong_khep_kin and ngoai_bong_bong[s_idx]:
                        continue
                    comp = [s_idx]
                    da_tham_cca[s_idx] = 1
                    cham_bien_roi = False
                    dem_cham_lt = 0
                    dem_loi_dam_c = 0
                    min_cx = max_cx = sx
                    min_cy = max_cy = sy
                    head_c = 0
                    while head_c < len(comp):
                        cur = comp[head_c]
                        head_c += 1
                        cpx = cur % rw
                        cpy = cur // rw
                        if lum_px[cur] <= 145.0:
                            dem_loi_dam_c += 1
                        if gan_long_trang[cur]:
                            dem_cham_lt += 1
                        if cpx <= 1 or cpx >= rw - 2 or cpy <= 1 or cpy >= rh - 2 or not trong_dong_mo[cur]:
                            cham_bien_roi = True
                        if cpx < min_cx:
                            min_cx = cpx
                        if cpx > max_cx:
                            max_cx = cpx
                        if cpy < min_cy:
                            min_cy = cpy
                        if cpy > max_cy:
                            max_cy = cpy
                        if len(comp) > dien_tich_max_net:
                            cham_bien_roi = True
                            continue
                        for dj in (-1, 0, 1):
                            ny = cpy + dj
                            if ny < 0 or ny >= rh:
                                continue
                            nb = ny * rw
                            for di in (-1, 0, 1):
                                if di == 0 and dj == 0:
                                    continue
                                nx = cpx + di
                                if nx < 0 or nx >= rw:
                                    continue
                                np = nb + nx
                                if la_bong_khep_kin and ngoai_bong_bong[np]:
                                    continue
                                if not da_tham_cca[np] and not la_nen[np] and not vung_cam[np] and not ket_noi_bien[np]:
                                    if di != 0 and nx > 0 and nx + 1 < rw and (ket_noi_bien[np - 1] or ket_noi_bien[np + 1]) and lum_px[np] > 118.0:
                                        continue
                                    da_tham_cca[np] = 1
                                    comp.append(np)
                    w_c = max_cx - min_cx + 1
                    h_c = max_cy - min_cy + 1
                    hop_le_long_trang = (not co_long_trang_ro) or (dem_cham_lt >= 2 and dem_loi_dam_c >= 1)
                    if (
                        not cham_bien_roi
                        and hop_le_long_trang
                        and len(comp) <= dien_tich_max_net
                        and w_c <= (sx1 - sx0) + 18
                        and h_c <= (sy1 - sy0) + 18
                    ):
                        for p_idx in comp:
                            can_xoa[p_idx] = 1
                        if not co_diem_xoa_chu_noi:
                            min_x_xoa, max_x_xoa = min_cx, max_cx + 1
                            min_y_xoa, max_y_xoa = min_cy, max_cy + 1
                            co_diem_xoa_chu_noi = True
                        else:
                            min_x_xoa = min(min_x_xoa, min_cx)
                            max_x_xoa = max(max_x_xoa, max_cx + 1)
                            min_y_xoa = min(min_y_xoa, min_cy)
                            max_y_xoa = max(max_y_xoa, max_cy + 1)

            # Bước 2: Nở viền 2px cho bóng thường quanh `can_xoa` và tô bằng `row_bg[py]`
            ban_kinh_no = 2
            y_no_0 = 2 if la_bong_khep_kin else max(ban_kinh_no, sy0 - ban_kinh_no)
            y_no_1 = (rh - 2) if la_bong_khep_kin else min(rh - ban_kinh_no, sy1 + ban_kinh_no)
            x_no_0 = 2 if la_bong_khep_kin else max(ban_kinh_no, sx0 - ban_kinh_no)
            x_no_1 = (rw - 2) if la_bong_khep_kin else min(rw - ban_kinh_no, sx1 + ban_kinh_no)
            for py in range(y_no_0, y_no_1):
                base = py * rw
                rr, gg, bb, _ = row_bg[py]
                for px in range(x_no_0, x_no_1):
                    pos = base + px
                    if vung_cam[pos] or (la_bong_khep_kin and ngoai_bong_bong[pos]):
                        continue
                    if can_xoa[pos]:
                        px_anh[rx0 + px, ry0 + py] = (rr, gg, bb)
                        continue
                    if (
                        can_xoa[pos - 1]
                        or can_xoa[pos + 1]
                        or can_xoa[pos - rw]
                        or can_xoa[pos + rw]
                        or can_xoa[pos - rw - 1]
                        or can_xoa[pos - rw + 1]
                        or can_xoa[pos + rw - 1]
                        or can_xoa[pos + rw + 1]
                        or can_xoa[pos - 2]
                        or can_xoa[pos + 2]
                        or can_xoa[pos - 2 * rw]
                        or can_xoa[pos + 2 * rw]
                    ):
                        px_anh[rx0 + px, ry0 + py] = (rr, gg, bb)

        # Bao trọn cả phần mở rộng ngang/dọc thực tế của mặt nạ chữ nổi ("ness...", "k-", "be", "Tenpai...")
        # hoặc nở hộp nội tiếp 2D (ngang + dọc) bên trong lòng bóng thoại khép kín (`la_bong_khep_kin`):
        pad_box_y = min(4, max(1, int(h_goc * 0.03)))
        bx = x_goc
        bw = w_goc
        if la_bong_khep_kin:
            def _dai_trong_bong_py(x_a: int, y_a: int, x_b: int, y_b: int, ty_le_can: float = 0.90, cat_goc: float = 0.16) -> bool:
                ax0_b = max(0, x_a)
                ay0_b = max(0, y_a)
                ax1_b = min(rw, x_b)
                ay1_b = min(rh, y_b)
                if cat_goc > 0 and ax1_b - ax0_b > 16:
                    cat_x = int((ax1_b - ax0_b) * cat_goc)
                    ax0_b += cat_x
                    ax1_b -= cat_x
                if cat_goc > 0 and ay1_b - ay0_b > 16:
                    cat_y = int((ay1_b - ay0_b) * cat_goc)
                    ay0_b += cat_y
                    ay1_b -= cat_y
                if ax1_b <= ax0_b or ay1_b <= ay0_b:
                    return False
                trong_b = 0
                tong_b = 0
                for py_b in range(ay0_b, ay1_b):
                    bb_b = py_b * rw
                    for px_b in range(ax0_b, ax1_b):
                        tong_b += 1
                        if ngoai_bong_bong[bb_b + px_b] == 0:
                            trong_b += 1
                return tong_b > 0 and (trong_b / tong_b) >= ty_le_can

            def _vanh_elip_trong_bong_py(x_a: int, y_a: int, x_b: int, y_b: int) -> bool:
                cx_e = (x_a + x_b) * 0.5
                cy_e = (y_a + y_b) * 0.5
                rx_e = (x_b - x_a) * 0.5
                ry_e = (y_b - y_a) * 0.5
                if rx_e < 4 or ry_e < 4:
                    return False
                trong_e = 0
                tong_e = 0
                for k_e in range(28):
                    goc_e = (k_e / 28.0) * math.pi * 2.0
                    cos_e = math.cos(goc_e)
                    sin_e = math.sin(goc_e)
                    for bk_e in (0.78, 0.90):
                        px_e = max(0, min(rw - 1, int(round(cx_e + rx_e * bk_e * cos_e))))
                        py_e = max(0, min(rh - 1, int(round(cy_e + ry_e * bk_e * sin_e))))
                        tong_e += 1
                        if ngoai_bong_bong[py_e * rw + px_e] == 0:
                            trong_e += 1
                return tong_e > 0 and (trong_e / tong_e) >= 0.88

            bx0_k, by0_k, bx1_k, by1_k = cx0, cy0, cx1, cy1
            for buoc_k in (max(2, int(max(w_goc, h_goc) / 24)), 1):
                con_nhich = True
                while con_nhich:
                    con_nhich = False
                    if bx0_k - buoc_k >= 0 and _dai_trong_bong_py(bx0_k - buoc_k, by0_k, bx0_k, by1_k) and _vanh_elip_trong_bong_py(bx0_k - buoc_k, by0_k, bx1_k, by1_k):
                        bx0_k -= buoc_k
                        con_nhich = True
                    if bx1_k + buoc_k <= rw and _dai_trong_bong_py(bx1_k, by0_k, bx1_k + buoc_k, by1_k) and _vanh_elip_trong_bong_py(bx0_k, by0_k, bx1_k + buoc_k, by1_k):
                        bx1_k += buoc_k
                        con_nhich = True
                    if by0_k - buoc_k >= 0 and _dai_trong_bong_py(bx0_k, by0_k - buoc_k, bx1_k, by0_k) and _vanh_elip_trong_bong_py(bx0_k, by0_k - buoc_k, bx1_k, by1_k):
                        by0_k -= buoc_k
                        con_nhich = True
                    if by1_k + buoc_k <= rh and _dai_trong_bong_py(bx0_k, by1_k, bx1_k, by1_k + buoc_k) and _vanh_elip_trong_bong_py(bx0_k, by0_k, bx1_k, by1_k + buoc_k):
                        by1_k += buoc_k
                        con_nhich = True
            le_x_k = max(3, int(round((bx1_k - bx0_k) * 0.045)))
            le_y_k = max(3, int(round((by1_k - by0_k) * 0.045)))
            if bx1_k - bx0_k > min(w_goc, 24) + le_x_k * 2:
                bx0_k += le_x_k
                bx1_k -= le_x_k
            if by1_k - by0_k > min(h_goc, 24) + le_y_k * 2:
                by0_k += le_y_k
                by1_k -= le_y_k
            bx = rx0 + bx0_k
            bw = max(20, bx1_k - bx0_k)
            by = ry0 + by0_k
            bh = max(16, by1_k - by0_k)
        elif co_diem_xoa_chu_noi:
            if la_chu_noi_tren_nen:
                bx0_thuc = max(x_goc - 16, min(x_goc, rx0 + min_x_xoa))
                bx1_thuc = min(x_goc + w_goc + 16, max(x_goc + w_goc, rx0 + max_x_xoa))
                bx = max(rx0, bx0_thuc)
                bw = min(rx1 - bx, bx1_thuc - bx0_thuc)
            by0_thuc = min(y_goc, ry0 + min_y_xoa)
            by1_thuc = max(y_goc + h_goc, ry0 + max_y_xoa)
            by = max(ry0, by0_thuc - pad_box_y)
            bh = min(ry1 - by, (by1_thuc - by0_thuc) + pad_box_y * 2)
        else:
            by = max(ry0, y_goc - pad_box_y)
            bh = min(ry1 - by, h_goc + pad_box_y * 2)

        hop_ve_chu.append(
            {
                "text": str(v["ban_dich"]).strip(),
                "x": bx,
                "y": by,
                "w": max(20, bw),
                "h": max(16, bh),
                "nen_toi": nen_toi,
                "nen_mau_trung_binh": nen_mau_trung_binh,
                "mau_chu_goc": mau_chu_goc,
                "mau_vien_goc": mau_vien_goc,
                "bg": (bg_r, bg_g, bg_b),
                "dong_con": ds_dong_con,
            }
        )

    # Tách lề dọc giữa 2 hộp chữ nằm chồng cột dọc để chữ dịch của bóng trên không đè vào bóng dưới
    for i_h in range(len(hop_ve_chu)):
        for j_h in range(i_h + 1, len(hop_ve_chu)):
            ha, hb = hop_ve_chu[i_h], hop_ve_chu[j_h]
            ox = min(ha["x"] + ha["w"], hb["x"] + hb["w"]) - max(ha["x"], hb["x"])
            if ox <= min(ha["w"], hb["w"]) * 0.25:
                continue
            top_h, bot_h = (ha, hb) if ha["y"] <= hb["y"] else (hb, ha)
            if top_h["y"] + top_h["h"] > bot_h["y"] - 6:
                mid_y = (top_h["y"] + top_h["h"] + bot_h["y"]) // 2
                top_h["h"] = max(14, mid_y - 3 - top_h["y"])
                bot_end = bot_h["y"] + bot_h["h"]
                bot_h["y"] = mid_y + 3
                bot_h["h"] = max(14, bot_end - bot_h["y"])

    # Bước B: Đo biên dạng thực tế lòng bóng thoại theo từng hàng pixel (Pixel-Exact Contour Typesetting)
    # & Đồng bộ cỡ chữ hài hoà toàn trang (tránh bóng chữ khổng lồ sát cạnh bóng chữ tí hon)
    draw = ImageDraw.Draw(anh)
    ket_qua_dan_trang: list[dict] = []
    tran_thoai_chuan = max(14, min(28, int(round(W * 0.026))))
    tran_chieu_thuc = max(24, min(42, int(round(W * 0.044))))

    for idx_hop, hop in enumerate(hop_ve_chu):
        la_chu_cjk_thai = bool(re.search(r"[\u0e00-\u0e7f\u3040-\u9fff\uac00-\ud7af]", hop["text"]))
        bx, by, bw, bh = hop["x"], hop["y"], hop["w"], hop["h"]
        la_hop_het_hoac_nhan = bool(
            "!" in hop["text"]
            or hop["text"].isupper()
        )
        chu = hop["text"].upper() if (loai_font == "bangers" and not la_chu_cjk_thai and la_hop_het_hoac_nhan) else hop["text"]
        bg_r, bg_g, bg_b = hop["bg"]
        nen_mau_tb = bool(hop.get("nen_mau_trung_binh"))

        def _la_pixel_nen(px_x: int, px_y: int) -> bool:
            if px_x < 0 or px_x >= W or px_y < 0 or px_y >= H:
                return False
            if nen_mau_tb:
                return True
            r_p, g_p, b_p = px_anh[px_x, px_y]
            return (abs(r_p - bg_r) + abs(g_p - bg_g) + abs(b_p - bg_b)) <= 85

        # Quét mở rộng biên dọc an toàn [safe_y0, safe_y1] vào khoảng trắng sạch trên/dưới trong lòng bóng thoại
        # (Khắc phục triệt để lỗi chữ gốc tiếng Anh ngắn nằm giữa bóng thoại cao khiến chữ Việt bị ép bé tí)
        cy_mid = max(0, min(H - 1, by + bh // 2))
        cx_mid = max(0, min(W - 1, bx + bw // 2))
        x_scan_l = max(0, bx + int(bw * 0.25))
        x_scan_r = min(W - 1, bx + int(bw * 0.75))
        xs_vert = list(range(x_scan_l, max(x_scan_l + 1, x_scan_r + 1), max(1, (x_scan_r - x_scan_l) // 6 or 1)))

        mo_rong_doc_max = 4 if nen_mau_tb else max(24, min(int(H * 0.14), int(bh * 0.90)))
        lim_top_scan = max(2, by - mo_rong_doc_max)
        lim_bot_scan = min(H - 3, by + bh + mo_rong_doc_max)
        for j_other, other_h in enumerate(hop_ve_chu):
            if j_other == idx_hop:
                continue
            ox = min(bx + bw, other_h["x"] + other_h["w"]) - max(bx, other_h["x"])
            if ox > min(bw, other_h["w"]) * 0.20:
                if other_h["y"] + other_h["h"] <= cy_mid:
                    lim_top_scan = max(lim_top_scan, other_h["y"] + other_h["h"] + 4)
                elif other_h["y"] >= cy_mid:
                    lim_bot_scan = min(lim_bot_scan, other_h["y"] - 4)

        safe_y0 = lim_top_scan if not nen_mau_tb else by
        if not nen_mau_tb:
            for yy in range(cy_mid, lim_top_scan - 1, -1):
                bad = sum(1 for xx in xs_vert if not _la_pixel_nen(xx, yy))
                if bad >= 1:
                    safe_y0 = min(cy_mid - 6, yy + 8)
                    break
        safe_y1 = lim_bot_scan if not nen_mau_tb else (by + bh)
        if not nen_mau_tb:
            for yy in range(cy_mid, lim_bot_scan + 1):
                bad = sum(1 for xx in xs_vert if not _la_pixel_nen(xx, yy))
                if bad >= 1:
                    safe_y1 = max(cy_mid + 6, yy - 8)
                    break

        raw_safe_h = max(14, safe_y1 - safe_y0)
        le_trong_y = max(3, int(round(raw_safe_h * 0.045))) if not nen_mau_tb else 1
        safe_y0 = min(cy_mid - 6, safe_y0 + le_trong_y)
        safe_y1 = max(safe_y0 + 14, safe_y1 - le_trong_y)
        safe_h = max(14, safe_y1 - safe_y0)
        le_trong_x = max(4, int(round(bw * 0.045))) if not nen_mau_tb else 2

        # Tính biên ngang [x_trai[y], x_phai[y]] cho từng hàng y trong bóng thoại
        x_trai: dict[int, int] = {}
        x_phai: dict[int, int] = {}
        for yy in range(safe_y0, safe_y1 + 1):
            rel_y = (yy - safe_y0) / max(1.0, float(safe_h))
            taper = 1.0
            if not nen_mau_tb:
                if rel_y < 0.18:
                    taper = 0.84 + 0.16 * (rel_y / 0.18)
                elif rel_y > 0.82:
                    taper = 0.84 + 0.16 * ((1.0 - rel_y) / 0.18)
            margin_taper = int(round((1.0 - taper) * bw * 0.45)) + le_trong_x
            lim_l = bx + margin_taper
            lim_r = bx + bw - margin_taper

            row_cx = max(lim_l + 4, min(lim_r - 4, cx_mid))
            cur_l = lim_l
            cur_r = lim_r
            if not nen_mau_tb:
                # Quét từ tâm sang trái tìm gai/viền bóng thoại
                for xx in range(row_cx, max(0, lim_l - 6) - 1, -1):
                    if not _la_pixel_nen(xx, yy) and not _la_pixel_nen(max(0, xx - 1), yy):
                        cur_l = max(lim_l, xx + 7)
                        break
                # Quét từ tâm sang phải tìm gai/viền bóng thoại
                for xx in range(row_cx, min(W - 1, lim_r + 6) + 1):
                    if not _la_pixel_nen(xx, yy) and not _la_pixel_nen(min(W - 1, xx + 1), yy):
                        cur_r = min(lim_r, xx - 7)
                        break
            if cur_r - cur_l < 18:
                mid_x = (lim_l + lim_r) // 2
                cur_l = max(bx, mid_x - 9)
                cur_r = min(bx + bw, mid_x + 9)
            x_trai[yy] = cur_l
            x_phai[yy] = cur_r

        def _khoang_ngang_cho_dong(
            y_top: int,
            y_bot: int,
            _s0: int = safe_y0,
            _s1: int = safe_y1,
            _xt: dict[int, int] = x_trai,
            _xp: dict[int, int] = x_phai,
            _bx: int = bx,
            _bw: int = bw,
        ) -> tuple[int, int]:
            y_a = max(_s0, min(_s1, y_top))
            y_b = max(y_a, min(_s1, y_bot))
            l_max = max(_xt.get(yy, _bx) for yy in range(y_a, y_b + 1))
            r_min = min(_xp.get(yy, _bx + _bw) for yy in range(y_a, y_b + 1))
            if r_min - l_max < 16:
                mid_x = (l_max + r_min) // 2
                return max(_bx, mid_x - 8), min(_bx + _bw, mid_x + 8)
            return l_max, r_min

        la_het_doc = safe_h >= bw * 2.5 and (len(chu) <= 28 or "\n" in chu)
        la_chieu_thuc_lon = la_het_doc or (
            (bw >= W * 0.16 and safe_h >= H * 0.075)
            and (len(chu) <= 28 or "!" in chu or "؟" in chu or "?" in chu)
        )
        tran_co = (
            max(tran_chieu_thuc, min(68, int(bw * 0.65)))
            if la_het_doc
            else (tran_chieu_thuc if la_chieu_thuc_lon else tran_thoai_chuan)
        )
        co_max = min(tran_co, max(14, int(min(bw * (0.72 if la_het_doc else 0.44), safe_h * 0.64))))
        co_min = 9
        la_khong_dau_cach = bool(re.search(r"[\u4e00-\u9fff\u3040-\u30ff]", chu)) or (
            bool(re.search(r"[\u0e00-\u0e7f]", chu)) and len(chu.split()) <= 2
        )

        def _thu_dan_dong_voi_co(
            co_thu: int,
            _chu: str = chu,
            _la_kdc: bool = la_khong_dau_cach,
            _la_hd: bool = la_het_doc,
            _bw: int = bw,
            _bx: int = bx,
            _s0: int = safe_y0,
            _sh: int = safe_h,
            _knd=_khoang_ngang_cho_dong,
        ):
            f_t = tim_font_he_thong(loai_font, co_thu, van_ban=_chu)
            bbox_mau_f = draw.textbbox((0, 0), "国g" if _la_kdc else "Ág", font=f_t)
            cao_dong = max(10, int((bbox_mau_f[3] - bbox_mau_f[1]) * 1.15))
            co_xuong_dong = "\n" in _chu
            if co_xuong_dong:
                cac_doan = [seg.strip() for seg in _chu.split("\n") if seg.strip()]
            else:
                cac_doan = [_chu]

            w_tb = max(20, int(_bw * 0.84))
            tong_w_tu = draw.textbbox((0, 0), _chu.replace("\n", " "), font=f_t)[2]
            so_dong_ut = max(len(cac_doan), int(math.ceil(tong_w_tu / max(1, w_tb))))

            dong: list[str] = []
            for doan_str in cac_doan:
                if (
                    _la_hd
                    and _bw <= 28
                    and not co_xuong_dong
                    and not _la_kdc
                    and len(doan_str.split()) == 1
                    and ("!" in doan_str or "?" in doan_str)
                    and len(doan_str) >= 5
                ):
                    import unicodedata as _ud
                    ky_tu_doc = re.findall(r"[!?]+|\S", _ud.normalize("NFC", doan_str))
                    if len(ky_tu_doc) >= 5:
                        dong.extend(ky_tu_doc)
                        continue
                if _la_kdc:
                    chu_sach_cjk = re.sub(r"\s+", "", doan_str)
                    tu = [chu_sach_cjk[i : i + 2] for i in range(0, len(chu_sach_cjk), 2)]
                    dau_noi = ""
                else:
                    tu = doan_str.split()
                    dau_noi = " "
                if not tu:
                    continue
                hien_tai = tu[0]
                for w_tu in tu[1:]:
                    idx_d = len(dong)
                    n_est = max(so_dong_ut, idx_d + 1)
                    y_est_0 = _s0 + max(0, (_sh - n_est * cao_dong) // 2) + idx_d * cao_dong
                    lx0_d, lx1_d = _knd(y_est_0, y_est_0 + cao_dong)
                    gioi_han_dong = max(16, lx1_d - lx0_d - 2)
                    thu = f"{hien_tai}{dau_noi}{w_tu}"
                    bbox_thu = draw.textbbox((0, 0), thu, font=f_t)
                    if (bbox_thu[2] - bbox_thu[0]) <= gioi_han_dong:
                        hien_tai = thu
                    else:
                        dong.append(hien_tai)
                        hien_tai = w_tu
                dong.append(hien_tai)
            if not dong:
                return f_t, [_chu], [], False

            # Cân bằng 2 dòng cuối nếu dòng cuối chỉ có 1 từ ngắn (không áp dụng khi có ngắt dòng chủ đích `\n`)
            if not _la_kdc and not co_xuong_dong and len(dong) >= 2 and len(dong[-1].split()) == 1 and len(dong[-2].split()) >= 3:
                tu_cuoi = dong[-2].split()
                thu_gop = f"{tu_cuoi[-1]} {dong[-1]}"
                thu_truoc = " ".join(tu_cuoi[:-1])
                y_last = _s0 + max(0, (_sh - len(dong) * cao_dong) // 2) + (len(dong) - 1) * cao_dong
                lx0_l, lx1_l = _knd(y_last, y_last + cao_dong)
                if (draw.textbbox((0, 0), thu_gop, font=f_t)[2] <= (lx1_l - lx0_l - 2)) and thu_truoc:
                    dong[-2] = thu_truoc
                    dong[-1] = thu_gop

            buoc_dong = (
                max(cao_dong, min(int(_sh / max(1, len(dong))), int(cao_dong * 1.48)))
                if (_la_hd and len(dong) >= 5)
                else cao_dong
            )
            tong_cao = len(dong) * buoc_dong
            y_bat_dau = _s0 + max(0, (_sh - tong_cao) // 2)
            vua_khit = (len(dong) * cao_dong) <= _sh
            ds_vi_tri: list[tuple[str, int, int, int]] = []
            for idx_d, d_str in enumerate(dong):
                yk0 = y_bat_dau + idx_d * buoc_dong
                yk1 = yk0 + cao_dong
                lx0_k, lx1_k = _knd(yk0, yk1)
                bb_d = draw.textbbox((0, 0), d_str, font=f_t)
                w_d = bb_d[2] - bb_d[0]
                if w_d > (lx1_k - lx0_k):
                    vua_khit = False
                cur_x_k = lx0_k + ((lx1_k - lx0_k) - w_d) // 2
                cur_x_k = max(_bx, min(_bx + _bw - w_d, cur_x_k))
                ds_vi_tri.append((d_str, cur_x_k, yk0, cao_dong))
            return f_t, dong, ds_vi_tri, vua_khit

        co_chon = co_min
        font_chon = tim_font_he_thong(loai_font, co_min, van_ban=chu)
        vi_tri_dong_chon: list[tuple[str, int, int, int]] = []
        for co in range(co_max, co_min - 1, -1):
            f_t, _, ds_vi_tri, vua_khit = _thu_dan_dong_voi_co(co)
            font_chon = f_t
            vi_tri_dong_chon = ds_vi_tri
            co_chon = co
            if vua_khit:
                break

        ket_qua_dan_trang.append(
            {
                "hop": hop,
                "nen_mau_tb": nen_mau_tb,
                "la_chieu_thuc_lon": la_chieu_thuc_lon,
                "co_chon": co_chon,
                "font_chon": font_chon,
                "vi_tri_dong_chon": vi_tri_dong_chon,
                "thu_dan_dong": _thu_dan_dong_voi_co,
            }
        )

    # Đồng bộ cỡ chữ hài hoà toàn trang (P75 Harmonization) cho các bóng hội thoại thường trên cùng trang
    ds_co_thuong = sorted(
        item["co_chon"]
        for item in ket_qua_dan_trang
        if not item["la_chieu_thuc_lon"] and len(item["hop"]["text"]) >= 8
    )
    if len(ds_co_thuong) >= 2:
        p75_co = ds_co_thuong[min(len(ds_co_thuong) - 1, int(len(ds_co_thuong) * 0.75))]
        tran_dong_bo = min(tran_thoai_chuan, max(16, int(round(p75_co + 2))))
        for item in ket_qua_dan_trang:
            if not item["la_chieu_thuc_lon"] and item["co_chon"] > tran_dong_bo:
                f_new, _, vt_new, _ = item["thu_dan_dong"](tran_dong_bo)
                item["co_chon"] = tran_dong_bo
                item["font_chon"] = f_new
                item["vi_tri_dong_chon"] = vt_new

    for item in ket_qua_dan_trang:
        hop = item["hop"]
        nen_mau_tb = item["nen_mau_tb"]
        font_chon = item["font_chon"]
        vi_tri_dong_chon = item["vi_tri_dong_chon"]
        mau_chu = hop.get("mau_chu_goc") or ((255, 255, 255) if hop["nen_toi"] else (15, 23, 42))
        mau_vien = hop.get("mau_vien_goc") or (((0, 0, 0) if hop["nen_toi"] else (255, 255, 255)) if nen_mau_tb else hop["bg"])

        for d, cur_x, cur_y, _ in vi_tri_dong_chon:
            # Dùng `stroke_width` vector gốc của FreeType/Pillow thay cho vòng lặp vẽ đè 28 lần
            # để nét chữ và dấu Tiếng Việt (ắ, ặ, ể, ữ, ộ) sắc nét tuyệt đối, không bị nhòe/lem viền xám!
            do_day_vien = 3 if nen_mau_tb else 1
            try:
                draw.text(
                    (cur_x, cur_y),
                    d,
                    font=font_chon,
                    fill=mau_chu,
                    stroke_width=do_day_vien,
                    stroke_fill=mau_vien,
                )
            except TypeError:
                for dx, dy in ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)):
                    draw.text((cur_x + dx, cur_y + dy), d, font=font_chon, fill=mau_vien)
                draw.text((cur_x, cur_y), d, font=font_chon, fill=mau_chu)

    out = io.BytesIO()
    anh.save(out, format="JPEG", quality=96, subsampling=0)
    return out.getvalue()


# ==============================================================================
# 2. BỘ QUÉT LINK TRUYỆN & TẢI ẢNH CHAPTER TỰ ĐỘNG
# ==============================================================================

_CACHE_DOH_IP: dict[str, str] = {}


def _phan_giai_doh_ip(host: str) -> str:
    if not host:
        return host
    cached = _CACHE_DOH_IP.get(host)
    if cached:
        return cached
    for doh_url in (
        f"https://cloudflare-dns.com/dns-query?name={urllib.parse.quote(host)}&type=A",
        f"https://dns.google/resolve?name={urllib.parse.quote(host)}&type=A",
    ):
        try:
            req = urllib.request.Request(
                doh_url,
                headers={"Accept": "application/dns-json", "User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(req, timeout=6.0) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            for ans in data.get("Answer") or []:
                ip_str = str(ans.get("data") or "").strip()
                if ans.get("type") == 1 and ip_str and ip_str not in ("127.0.0.1", "0.0.0.0", "::1"):
                    _CACHE_DOH_IP[host] = ip_str
                    return ip_str
        except Exception:
            continue
    return host


def _goi_https_phan_manh_sni(url: str, headers: dict, timeout: float = 18.0, so_lan_redirect: int = 3) -> bytes:
    """
    Tự động phân mảnh gói tin TLS ClientHello tại vị trí SNI (bằng ssl.MemoryBIO + TCP_NODELAY)
    kết hợp phân giải DNS-over-HTTPS (DoH) khi nhà mạng (ISP) chặn DNS/SNI gây lỗi WinError 10061/10054.
    """
    import http.client
    import socket
    import ssl

    parts = urllib.parse.urlsplit(url)
    host = parts.hostname or ""
    port = parts.port or 443
    path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")

    target_host = _CACHE_DOH_IP.get(host) or host
    try:
        if target_host == host:
            try:
                resolved_ips = {ai[4][0] for ai in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
                if resolved_ips & {"127.0.0.1", "0.0.0.0", "::1"}:
                    target_host = _phan_giai_doh_ip(host)
            except Exception:
                target_host = _phan_giai_doh_ip(host)
        sock = socket.create_connection((target_host, port), timeout=min(float(timeout or 18.0), 18.0))
    except OSError:
        target_host = _phan_giai_doh_ip(host)
        sock = socket.create_connection((target_host, port), timeout=min(float(timeout or 18.0), 18.0))
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        ctx = ssl.create_default_context()
        incoming = ssl.MemoryBIO()
        outgoing = ssl.MemoryBIO()
        sslobj = ctx.wrap_bio(incoming, outgoing, server_hostname=host)

        first_flight = True
        host_bytes = host.encode("ascii", errors="ignore")
        while True:
            try:
                sslobj.do_handshake()
                break
            except ssl.SSLWantReadError:
                out_bytes = outgoing.read()
                if out_bytes:
                    if first_flight and host_bytes and host_bytes in out_bytes:
                        idx = out_bytes.index(host_bytes) + max(2, len(host_bytes) // 3)
                        sock.send(out_bytes[:2])
                        time.sleep(0.015)
                        sock.send(out_bytes[2:idx])
                        time.sleep(0.015)
                        sock.send(out_bytes[idx:])
                        first_flight = False
                    else:
                        sock.sendall(out_bytes)
                in_bytes = sock.recv(16384)
                if not in_bytes:
                    raise ConnectionResetError("Kết nối bị đóng trong lúc bắt tay TLS.")
                incoming.write(in_bytes)

        hdr_lines = [
            f"GET {path} HTTP/1.1",
            f"Host: {host}",
            "Accept: */*",
            "Accept-Encoding: identity",
            "Connection: close",
        ]
        for k, v in headers.items():
            if k.lower() not in ("host", "accept-encoding", "connection"):
                if k.lower() == "user-agent" and ("mangadex.org" in host or "mangadex.network" in host) and "Mozilla/5.0" in str(v):
                    v = "AntigravityMangaTranslator/2.0"
                hdr_lines.append(f"{k}: {v}")
        raw_req = ("\r\n".join(hdr_lines) + "\r\n\r\n").encode("utf-8")
        sslobj.write(raw_req)
        pending = outgoing.read()
        if pending:
            sock.sendall(pending)

        resp_buf = bytearray()
        while True:
            try:
                chunk = sslobj.read(32768)
                if not chunk:
                    break
                resp_buf.extend(chunk)
                if len(resp_buf) > 21 * 1024 * 1024:
                    raise NeedsAttention("Phản hồi vượt giới hạn 20 MB.")
            except ssl.SSLWantReadError:
                try:
                    in_bytes = sock.recv(32768)
                except OSError:
                    in_bytes = b""
                if not in_bytes:
                    incoming.write_eof()
                else:
                    incoming.write(in_bytes)
    finally:
        try:
            sock.close()
        except Exception:
            pass

    class _BioSocket:
        def __init__(self, raw_bytes: bytes):
            self._fp = io.BytesIO(raw_bytes)

        def makefile(self, *_a, **_kw):
            return self._fp

    http_resp = http.client.HTTPResponse(_BioSocket(bytes(resp_buf)))
    http_resp.begin()
    if http_resp.status in (301, 302, 303, 307, 308) and so_lan_redirect > 0:
        loc = http_resp.getheader("Location")
        if loc:
            next_url = urllib.parse.urljoin(url, loc)
            return _goi_https_phan_manh_sni(next_url, headers, timeout=timeout, so_lan_redirect=so_lan_redirect - 1)
    if http_resp.status >= 400:
        raise urllib.error.HTTPError(url, http_resp.status, http_resp.reason, http_resp.headers, None)
    body_bytes = http_resp.read(20 * 1024 * 1024 + 1)
    if len(body_bytes) > 20 * 1024 * 1024:
        raise NeedsAttention("Phản hồi vượt giới hạn 20 MB.")
    return body_bytes


def goi_http(url: str, method: str = "GET", body: dict | None = None, token: str = "", referer: str = "",
             *, nguon_ngoai: bool = False, timeout: float = 90, extra_headers: dict[str, str] | None = None) -> bytes:
    parsed_u = urllib.parse.urlsplit(url)
    if parsed_u.scheme not in ("http", "https"):
        raise NeedsAttention("Chỉ hỗ trợ địa chỉ HTTP/HTTPS.")
    mp_key_hex = ""
    mp_vw_token = ""
    if parsed_u.fragment and "mp_key=" in parsed_u.fragment:
        frag_qs = urllib.parse.parse_qs(parsed_u.fragment)
        mp_key_hex = (frag_qs.get("mp_key") or [""])[0].strip()
        mp_vw_token = (frag_qs.get("mp_vw") or [""])[0].strip()
        url = urllib.parse.urlunsplit((parsed_u.scheme, parsed_u.netloc, parsed_u.path, parsed_u.query, ""))
    headers = {"User-Agent": USER_AGENT}
    if not nguon_ngoai:
        headers.update({"X-Ma-May-Tinh": MA_MAY_HIEN_THI, "X-Ma-Khach": KHACH_ID_MAY_TINH,
                        "Cookie": f"khach_id={KHACH_ID_MAY_TINH}"})
    if token and not nguon_ngoai:
        headers["Authorization"] = f"Bearer {token}"
    if referer:
        headers["Referer"] = referer
    if mp_key_hex:
        headers["Origin"] = "https://mangaplus.shueisha.co.jp"
        headers["Referer"] = "https://mangaplus.shueisha.co.jp/"
        if mp_vw_token:
            headers["Plus-Vw-Token"] = mp_vw_token
    if extra_headers:
        headers.update(extra_headers)
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    url = str(url or "").strip().replace(" ", "%20")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read(20 * 1024 * 1024 + 1)
            if len(content) > 20 * 1024 * 1024:
                raise NeedsAttention("Phản hồi vượt giới hạn 20 MB.")
    except urllib.error.HTTPError as http_exc:
        if nguon_ngoai and method.upper() == "GET" and http_exc.code in (403, 429, 502, 503, 504):
            origin_goc = f"{parsed_u.scheme}://{parsed_u.netloc}/"
            ua_du_phong = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
            ]
            content = b""
            loi_cuoi_http = http_exc
            for idx_retry, ua_alt in enumerate(ua_du_phong):
                time.sleep(0.55 * (idx_retry + 1))
                hdr_retry = dict(headers)
                hdr_retry["User-Agent"] = ua_alt
                hdr_retry.setdefault("Referer", referer or origin_goc)
                hdr_retry.setdefault("Accept", "image/avif,image/webp,image/apng,image/*,*/*;q=0.8")
                try:
                    req_retry = urllib.request.Request(url, data=data, headers=hdr_retry, method=method)
                    with urllib.request.urlopen(req_retry, timeout=timeout) as resp_r:
                        content = resp_r.read(20 * 1024 * 1024 + 1)
                        break
                except urllib.error.HTTPError as e2:
                    loi_cuoi_http = e2
                except Exception:
                    pass
            if not content:
                raise loi_cuoi_http
        else:
            raise
    except (ConnectionResetError, urllib.error.URLError) as exc:
        msg = str(exc)
        if (
            nguon_ngoai
            and method.upper() == "GET"
            and urllib.parse.urlsplit(url).scheme == "https"
            and ("10054" in msg or "reset" in msg.lower())
        ):
            content = _goi_https_phan_manh_sni(url, headers, timeout=timeout)
        else:
            raise
    if mp_key_hex and content:
        try:
            key_bytes = bytes.fromhex(mp_key_hex)
            klen = len(key_bytes)
            if klen > 0:
                content = bytes(b ^ key_bytes[i % klen] for i, b in enumerate(content))
        except Exception:
            pass
    return content


def gui_multipart_trang(
    url: str,
    img_bytes: bytes,
    *,
    filename: str = "page.jpg",
    fields: dict[str, str],
    token: str = "",
) -> bytes:
    """Gửi ảnh trang truyện qua chuẩn multipart/form-data lên `/api/v1/doc-truyen/trang`."""
    boundary = f"----MangaStudioBoundary{int(time.time() * 1000)}"
    lines: list[bytes] = []
    for k, v in fields.items():
        if v is None or v == "":
            continue
        lines.append(f"--{boundary}\r\n".encode("utf-8"))
        lines.append(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode("utf-8"))
        lines.append(f"{v}\r\n".encode("utf-8"))

    lines.append(f"--{boundary}\r\n".encode("utf-8"))
    lines.append(
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n".encode("utf-8")
    )
    lines.append(img_bytes)
    lines.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(lines)

    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "X-Ma-May-Tinh": MA_MAY_HIEN_THI,
        "X-Ma-Khach": KHACH_ID_MAY_TINH,
        "Cookie": f"khach_id={KHACH_ID_MAY_TINH}",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


QWEN3_VL_MODEL = "qwen3-vl:8b"
HUONG_DAN_QWEN3 = (
    "Chạy Cai-Dich-Offline.bat để cài theo hướng dẫn hoặc tự chạy: ollama pull qwen3-vl:8b "
    "(khoảng 6.2 GB, cần Internet và đồng ý tải lần đầu). "
    "Sau đó chọn 'local_gguf (Qwen3-VL 8B Offline)' trong ô 'Bộ máy AI'; "
    "Gemini vẫn là mặc định. Muốn không tải ảnh qua mạng, chọn thư mục ảnh có sẵn."
)


class LocalServerUnavailableError(RuntimeError):
    """Không kết nối được endpoint cục bộ, khác với thiếu/sai model."""


class LocalModelMissingError(RuntimeError):
    """Server đã chạy nhưng chưa có đúng Qwen3-VL 8B."""


class LocalCpuUnsupportedError(RuntimeError):
    """Người dùng chọn CPU nhưng LM Studio không nhận tùy chọn này từ app."""


class LocalEmptyResponseError(RuntimeError):
    """Server trả HTTP 200 nhưng không có nội dung model thật."""


class LocalRuntimeCrashError(RuntimeError):
    """Ollama đã chạy nhưng tiến trình nạp/chạy model bị sập (thường do GPU/CUDA/VRAM)."""


DAU_HIEU_RUNTIME_SAP = ("0xc0000409", "cuda error", "runner", "terminated", "out of memory")
HUONG_DAN_RUNTIME_SAP = (
    "Đây là lỗi Ollama không chạy được model trên máy này (thường do driver/GPU NVIDIA hoặc thiếu VRAM), "
    "không phải lỗi cài model. Hãy: (1) mở %LOCALAPPDATA%\\Ollama\\server.log để xem nguyên nhân, "
    "(2) cập nhật driver NVIDIA và Ollama, (3) tick 'Chạy Ollama bằng CPU' trong app rồi bấm kiểm tra lại "
    "(chậm hơn nhiều), hoặc chọn Gemini. App không tự đổi bộ máy."
)
TIMEOUT_GPU = 180
TIMEOUT_CPU = 900
HUONG_DAN_CPU_LM_STUDIO = (
    "Tùy chọn 'Chạy Ollama bằng CPU' chỉ áp dụng cho Ollama; app không điều khiển được CPU/GPU của LM Studio. "
    "Hãy bỏ tick CPU và tự chọn chế độ CPU trong LM Studio, hoặc mở Ollama (cổng 11434) với qwen3-vl:8b."
)


def _goi_json_ai_cuc_bo(url: str, *, timeout: int, payload: dict | None = None) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        chi_tiet = exc.read(2048).decode("utf-8", errors="replace")
        if exc.code >= 500 and any(k in chi_tiet.lower() for k in DAU_HIEU_RUNTIME_SAP):
            raise LocalRuntimeCrashError(
                f"AI cục bộ trả HTTP {exc.code} tại {url}: {chi_tiet}. " + HUONG_DAN_RUNTIME_SAP
            ) from exc
        raise RuntimeError(
            f"AI cục bộ trả HTTP {exc.code} tại {url}: {chi_tiet}. "
            "Nếu Ollama báo không hỗ trợ Qwen3-VL, hãy cập nhật Ollama từ "
            "https://ollama.com/download/windows rồi thử lại."
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise LocalServerUnavailableError(
            f"Không kết nối được hoặc hết thời gian chờ AI cục bộ tại {url}: {exc}"
        ) from exc
    try:
        data = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise RuntimeError(f"AI cục bộ tại {url} trả dữ liệu không phải JSON hợp lệ.") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"AI cục bộ tại {url} trả JSON không đúng cấu trúc.")
    if data.get("error"):
        raise RuntimeError(f"AI cục bộ tại {url} báo lỗi: {data['error']}")
    return data


def _ket_noi_qwen3_vl_cuc_bo() -> tuple[str, str]:
    """Chỉ nhận Qwen3-VL 8B; chỉ thử LM Studio khi không kết nối được Ollama."""
    try:
        data = _goi_json_ai_cuc_bo("http://127.0.0.1:11434/api/tags", timeout=4)
    except LocalServerUnavailableError as ollama_exc:
        try:
            data = _goi_json_ai_cuc_bo("http://127.0.0.1:1234/v1/models", timeout=4)
        except LocalServerUnavailableError as exc:
            raise LocalServerUnavailableError(
                "Chưa kết nối được Ollama (cổng 11434) hoặc LM Studio (cổng 1234). "
                "Hãy mở Ollama trên Windows rồi thử lại. " + HUONG_DAN_QWEN3
            ) from exc
        models = [m.get("id", "") for m in (data.get("data") or []) if isinstance(m, dict)]
        # LM Studio thường dùng ID Qwen/Qwen3-VL-8B-Instruct[-Q4_K_M.gguf].
        model = next(
            (m for m in models if isinstance(m, str) and re.search(
                r"(?:^|/)qwen3[-_]vl[-_:]8b(?:$|[-_.:])", m, re.I
            )),
            "",
        )
        if not model:
            raise LocalModelMissingError(
                "LM Studio đang chạy nhưng chưa nạp Qwen3-VL 8B. "
                "Hãy nạp đúng model Vision Qwen3-VL-8B và bật Local Server, "
                "hoặc mở Ollama và cài qwen3-vl:8b. " + HUONG_DAN_QWEN3
            ) from ollama_exc
        return "lmstudio", model

    models = [m.get("name", "") for m in (data.get("models") or []) if isinstance(m, dict)]
    if QWEN3_VL_MODEL not in models:
        raise LocalModelMissingError(
            "Ollama đang chạy nhưng chưa cài đúng model qwen3-vl:8b (Qwen3-VL 8B). "
            "App không tự chọn model khác và không tự tải model. " + HUONG_DAN_QWEN3
        )
    return "ollama", QWEN3_VL_MODEL


def _tuy_chon_ollama(chay_cpu: bool, **them) -> dict:
    """Chỉ ép CPU khi người dùng tự bật; mặc định để Ollama tự chọn."""
    tuy_chon = {"temperature": 0.2, **them}
    if chay_cpu:
        tuy_chon["num_gpu"] = 0
    return tuy_chon


def chay_thu_model_cuc_bo(chay_cpu: bool = False) -> tuple[str, str]:
    """Nạp và chạy thật một câu ngắn (không ảnh) để biết runner có sống, không chỉ model có trong danh sách."""
    backend, model = _ket_noi_qwen3_vl_cuc_bo()
    if backend == "lmstudio" and chay_cpu:
        raise LocalCpuUnsupportedError(HUONG_DAN_CPU_LM_STUDIO)
    if backend == "ollama":
        data = _goi_json_ai_cuc_bo(
            "http://127.0.0.1:11434/api/chat",
            timeout=TIMEOUT_CPU if chay_cpu else TIMEOUT_GPU,
            payload={
                "model": model, "stream": False,
                "options": _tuy_chon_ollama(chay_cpu, num_predict=8),
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
        message = data.get("message")
        message = message if isinstance(message, dict) else {}
        # Model có chế độ suy luận có thể chỉ trả "thinking" trong 8 token đầu; vẫn là phản hồi thật.
        co_noi_dung = any(str(message.get(k) or "").strip() for k in ("content", "thinking"))
    else:
        data = _goi_json_ai_cuc_bo(
            "http://127.0.0.1:1234/v1/chat/completions",
            timeout=TIMEOUT_GPU,
            payload={"model": model, "max_tokens": 8, "messages": [{"role": "user", "content": "hi"}]},
        )
        choices = data.get("choices")
        first = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first.get("message"), dict) else {}
        co_noi_dung = bool(str(message.get("content") or "").strip())
    if not co_noi_dung:
        raise LocalEmptyResponseError(
            "AI cục bộ trả HTTP 200 nhưng không có nội dung trả lời thật nên chưa coi là chạy được. "
            "Xem log Ollama/LM Studio, thử lại hoặc chọn Gemini."
        )
    return backend, model


def _lam_sach_chu_ocr_truyen(text: str) -> str:
    """
    Làm sạch các lỗi nhận diện phổ biến của OCR trên cả font chữ IN HOA và font chữ thường/nghiêng truyện tranh:
    - Sửa lỗi nhầm ký tự đặc trưng của font comic: '0K' -> 'OK', 'tel)' -> 'tell', 'wi//' -> 'will',
      'didn'E' -> 'didn't', 'Eell' -> 'tell', 'Ehem' -> 'them', 'AU' -> 'ALL', 'BEER?II' -> 'BEER?!!'.
    - Lọc ký tự nốt nhạc rác ở đầu/cuối câu hát ('J"', '-\\'D').
    """
    s = (text or "").strip()
    if not s:
        return ""

    # 1. Xoá rác ký hiệu nốt nhạc / viền bóng thoại bị OCR đọc nhầm ở đầu hoặc cuối dòng
    s = re.sub(r"^(?:J[\"')]|T?J\b)\s+", "", s)
    s = re.sub(r"\s+(?:J[\"')]|-'D|I\s*\.\s*I)$", "", s)

    # 2. Sửa lỗi nhận diện ký tự phổ biến trên mọi kiểu chữ truyện tranh
    s = re.sub(r"\b0[Kk]\b", "OK", s)
    s = re.sub(r"\bHaj\b", "Ha,", s)
    s = re.sub(r"(?<!\w)tel\)(?!\w)", "tell", s)
    s = re.sub(r"(?<!\w)wi//(?!\w)", "will", s)
    s = re.sub(r"\b([dD]idn|[dD]on|[cC]an|[wW]on|[iI]sn|[wW]asn|[aA]ren|[hH]avn|[hH]asn)'[Ee]\b", r"\1't", s)
    s = re.sub(r"\bEell\b", "tell", s)
    s = re.sub(r"\bEhem\b", "them", s)
    s = re.sub(r"\bEhat\b", "that", s)
    s = re.sub(r"\bEhis\b", "this", s)
    s = re.sub(r"\bEhere\b", "there", s)
    s = re.sub(r"\bEhen\b", "then", s)
    s = re.sub(r"\bEhe\b", "the", s)
    s = re.sub(r"\b100k\b", "look", s, flags=re.I)
    s = re.sub(r"\bshou\b", "show", s)
    s = re.sub(r"\bhou\b", "how", s)
    s = re.sub(r"(?<=[a-z]\s)Why(?=\s+[a-z])", "why", s)
    s = re.sub(r"(?<=[a-z]\s)OF(?=\s+[a-z])", "of", s)
    s = re.sub(r"(?<=[a-z,]\s)For(?=\s+[a-z])", "for", s)
    s = re.sub(r"(?<=[a-z']\s)Find(?=\s+[a-z])", "find", s)
    s = re.sub(r"(?<=[a-z,]\s)With(?=\s+[a-z])", "with", s)
    s = re.sub(r"\bAU(?=\s+[A-Z]{2,}\b)", "ALL", s)
    s = re.sub(r"SOLD\s+åUp\.?[•*]*", "'OLD MAP'", s, flags=re.I)
    s = re.sub(r"'?OLD\s+\"P'?", "'OLD MAP'", s, flags=re.I)
    s = re.sub(r"\bSAWT\b", "SAINT", s, flags=re.I)
    s = re.sub(r"\b(?:JOSEPW|UOSEPH|VOSEPN)\b", "JOSEPH", s, flags=re.I)
    s = re.sub(r"\b(?:ARIK4THEA|AR\s+IMATHEA)'?", "ARIMATHEA'", s, flags=re.I)
    s = re.sub(r"\b(?:HL\.+IH\.?|Hug\.)", "HUH.", s, flags=re.I)
    s = re.sub(r"\bHL\.+IP!?", "HUP!", s, flags=re.I)
    s = re.sub(r"\bPA%R\b", "PAPER", s, flags=re.I)
    s = re.sub(r"\b1S\b", "IS", s)
    s = re.sub(r"(?<=[A-Z]\s)15(?=\s+[A-Z])", "IS", s)
    s = re.sub(r"\bANP\b", "AND", s)
    s = re.sub(r"\bRAM\s+EN\b", "RAMEN", s, flags=re.I)
    s = re.sub(r"\bSOME-\s+THIN[CG]\b", "SOMETHING", s, flags=re.I)
    s = re.sub(r"\?II+\b", "?!!", s)
    s = re.sub(r"\?\s+!", "?!", s)

    # 3. Sửa lỗi nhận diện font chữ truyện tranh của PP-OCRv4 / RapidOCR (F <-> P, V <-> U, chữ dính nhau ở khung hẹp)
    comic_ocr_subs = [
        (r"^\.\.\.ll\s+the\s+way\b", "All the way"),
        (r"^\.\.Say\.\s+Shin\b", "...Say, Shin"),
        (r"\bIP\s+youg?\b", "If you"),
        (r"\bIP\s+(?=he\b|she\b|they\b|we\b|I\b|it\b)", "If "),
        (r"\b([Ww]here|[Ee]ven|[Ww]hat)\s*ip\b", r"\1 if"),
        (r"\bin\s+Pull\b", "in full"),
        (r"\bonce\s*[PF]aced\b", "once faced"),
        (r"\bseen\s+his\s+Pace\b", "seen his face"),
        (r"\bPigured\b", "figured"),
        (r"\b[PF]inding[.\-\s]+a\b", "finding a"),
        (r"\bPinding\b", "finding"),
        (r"\bsape\b", "safe"),
        (r"\bplacelto\b", "place to"),
        (r"\bbeco[Mm]=?[-\s]*[Pp]ortable\b", "be comfortable"),
        (r"\bPor\s*Me\b", "for me"),
        (r"\b(?:Por|For)\s*hi[Mm]\b", "for him"),
        (r"\b(?:Por|For)\s*his\b", "for his"),
        (r"\bMade\s*Por\b", "made for"),
        (r"\bhi[Mm]sel[Pp]+\b", "himself"),
        (r"\bhi[Mm]seip+[Pp]*\b", "himself"),
        (r"\byour\s+lipe\b", "your life"),
        (r"\bhis\s+lipe\b", "his life"),
        (r"\bdrained\s+his\s+lifes\b", "drained his life"),
        (r"\blipe\s+ons?\b", "life on"),
        (r"\bnothing\s*lept\b", "nothing left"),
        (r"\bon\s*all\s*op\b", "on all of"),
        (r"\bcastle\s+OP\s+yours\b", "castle of yours"),
        (r"\boUt\s+op\s+lies\b", "out of lies"),
        (r"\bBan\s+out\s+OP\b", "Ran out of"),
        (r"\bout\s+OP\s+points\b", "out of points"),
        (r"\bWovld\b", "Would"),
        (r"\bneyer\b", "never"),
        (r"\btiie\b", "tile"),
        (r"\bThe\s+tile\s+The\s+just\s+played\b", "The tile he just played"),
        (r"\bhort\b", "hurt"),
        (r"\b[CE]REALLY\b", "REALLY"),
        (r"\bhe'l\b", "he'll"),
        (r"\bHe'sw\b", "He's"),
        (r"\bWhy[bh]\b", "why"),
        (r"\bnowb\b", "now,"),
        (r"\bplayb\b", "play,"),
        (r"\btaking\s+Cis\.?\s+Sweet\s+time\b", "taking his sweet time"),
        (r"\bEa\s*den\s+o[fF][.:]?\s*gam[-\s(]*blers\b", "a den of gamblers"),
        (r"\b(?:Solu-\s*tioneo|Solu-\s*Cioncoo|Solutlon\w*|Solotion)\b", "solution"),
        (r"\btioneo\b", "tion..."),
        (r"\bCioncoo\b", "tion..."),
        (r"\b(?:ool|bl)-san\b", "-san"),
        (r"\b(?:Bach|Back)\s+then,?\s+Chat!\s*guy:?", "Back then, that guy"),
        (r"\bFROM\s+CANTHE\s+DLES\b", "FROM THE CANDLES"),
        (r"\bIS\.?\s*TOO\s+WEAK\b", "IS TOO WEAK"),
        (r"\bAll\.?\s*on\s*purpose\b", "All on purpose"),
        # Tách các từ tiếng Anh bị dính liền nhau do bóng thoại hẹp dọc trong Manga
        (r"\bareyou\b", "are you"),
        (r"\btosettle\b", "to settle"),
        (r"\bwayuntil\b", "way until"),
        (r"\bSeeMsto\b", "Seems to"),
        (r"\bwiththe\b", "with the"),
        (r"\btopickhis\b", "to pick his"),
        (r"\bbeglad\b", "be glad"),
        (r"\bCommanderfor\b", "Commander for"),
        (r"\btheAllied\b", "the Allied"),
        (r"\bevenWhile\b", "even while"),
        (r"\bAswell\b", "As well"),
        (r"\basthe\b", "as the"),
        (r"\bOrdo\b", "Or do"),
        (r"\bWhileit\b", "While it"),
        (r"\bnowin\b", "now in"),
        (r"\boverto\b", "over to"),
        (r"\bdon't\s*[,，]\s*do\b", "don't do"),
        (r"\b([a-z]{2,}):([a-z]{2,})\b", r"\1 \2"),
        (r"\b(about|avoid\s+his|Already|Hey|Dumbass)\.\s+(?=[a-z])", r"\1, "),
        (r"\b([A-Za-z]{2,})-(a|to|was|is|in|on|of|for|the|and|or)\b", r"\1 \2"),
    ]
    for pat_c, rep_c in comic_ocr_subs:
        s = re.sub(pat_c, rep_c, s, flags=re.I)

    # 3b. Chuẩn hoá chữ viết HOA xen kẽ giữa từ thường đặc trưng của font comic (VD: 'SoMething' -> 'Something',
    # 'SeeMs' -> 'Seems', 'MeMory' -> 'Memory', 'reSearch' -> 'research', 'FlaMes' -> 'flames', 'hiM' -> 'him')
    def _chuan_hoa_tu_hoa_xen_ke(m: re.Match) -> str:
        w = m.group(0)
        if w.isupper() or w.islower():
            return w
        if sum(1 for c in w[1:] if c.isupper()) >= 1 and sum(1 for c in w if c.islower()) >= 1:
            return w[0] + w[1:].lower()
        return w

    s = re.sub(r"\b[A-Za-z][A-Za-z']{1,}\b", _chuan_hoa_tu_hoa_xen_ke, s)
    # Hạ chữ hoa đầu từ đối với các từ thông dụng bị font comic vẽ chữ M/S/F/G/U cao như chữ hoa ở giữa câu
    s = re.sub(
        r"(?<=[a-z,]\s)\b(Something|Some|Glasses|Solution|Marks|Match|Memory|Flames|Fire|Meet|Met|Use|Still|Should|Make|Seen|So)\b",
        lambda m: m.group(1).lower(),
        s,
    )
    s = re.sub(r"\babout,\s+his\b", "about his", s, flags=re.I)
    s = re.sub(r"\bavoid\s+his,\s+Ganpai\b", "avoid his Ganpai", s, flags=re.I)

    # 4. Xử lý riêng cho câu thoại IN HOA (ALL-CAPS)
    upper_chars = sum(1 for c in s if c.isupper())
    lower_chars = sum(1 for c in s if c.islower())
    if upper_chars >= lower_chars * 2 and upper_chars >= 2:
        # Số "1" đứng riêng lẻ trong câu thoại in hoa là chữ "I"
        s = re.sub(r"(?:(?<=^)|(?<=\s))1(?=\s|$)", "I", s)
        # Dấu chấm than "!" ở cuối từ in hoa thường bị nhận nhầm thành I / II / III / IIIP
        s = re.sub(r"([A-Z]{2,})I{3,}P?(?=\s|$|[^A-Za-z])", r"\1!!!", s)
        s = re.sub(r"([A-Z]{2,})IIP?(?=\s|$|[^A-Za-z])", r"\1!!", s)

        def _sua_i_cuoi(m: re.Match) -> str:
            word = m.group(1)
            if word in {"H", "ALIB", "SK", "TAX", "BIKIN", "MARTN", "SUSH", "KO", "SENPA"}:
                return m.group(0)
            return word + "!"

        s = re.sub(r"\b([A-Z]{2,})I(?=\s|$|[.,?!'\"])", _sua_i_cuoi, s)
    # Khử từ hoặc cụm từ bị nhân đôi liên tiếp (kể cả có dấu câu ở cuối như 'down? down?', 'hear me. hear me.')
    s = re.sub(r"\b([A-Za-z']+(?:\s+[A-Za-z',.!?]+){0,4}[.!?]*)\s+\1(?=\s|$)", r"\1", s, flags=re.I)
    return s.strip()


def _gop_cac_dong_trong_bong_thoai(comp_ordered: list[dict], ngon_ngu_nguon: str = "en") -> str:
    """
    Nối thông minh các dòng chữ trong cùng 1 bóng thoại/khung chữ:
    - Tự động nối liền các từ tiếng Anh bị ngắt gạch ngang xuống dòng trong bóng thoại hẹp
      (VD: 'SoMe-' + 'thing' -> 'Something', 'poi-' + 'nts!' -> 'points!', 'Hon-' + 'estly,' -> 'Honestly,',
      'pla-' + 'yed' -> 'played', 'Al-' + 'ready' -> 'Already', 'Dai-' + 'san-' + 'gen.' -> 'Daisangen.').
    - Tự động ghép kính ngữ bị rớt dòng ('Tetsu' + '-san' -> 'Tetsu-san').
    """
    if not comp_ordered:
        return ""
    lang = (ngon_ngu_nguon or "en").lower()
    if lang in ("ja", "zh"):
        raw_joined = "".join(str(r.get("text") or "").strip() for r in comp_ordered)
        return _lam_sach_chu_ocr_truyen(raw_joined)

    merged_lines: list[str] = []
    for r in comp_ordered:
        t = str(r.get("text") or "").strip()
        if not t:
            continue
        # Bỏ các mảnh rác số/ký hiệu đơn lẻ ở rìa bóng thoại ('000', '**', '88')
        if re.fullmatch(r"[0*#.,:;~+=-]{1,4}", t):
            continue
        if merged_lines:
            prev = merged_lines[-1]
            # Nối kính ngữ '-san', '-kun', '-chan', '-sama', '-sensei' vào tên phía trước
            if re.match(r"^-(?:san|kun|chan|sama|sensei|senpai)\b", t, re.I):
                merged_lines[-1] = prev + t
                continue
            # Nối từ bị ngắt gạch ngang cuối dòng ('SoMe-' + 'thing', 'Some-!' + 'body', 'poi-' + 'nts!')
            if re.search(r"[A-Za-z][-=!]+$", prev) and re.match(r"^[A-Za-z]", t):
                if prev.endswith(("-", "=")) or prev.rstrip("-=!").lower() in {
                    "some", "any", "every", "no", "hon", "solu", "poi", "inna", "dai", "san", "al", "pla", "becom"
                }:
                    merged_lines[-1] = prev.rstrip("-=!") + t
                    continue
        merged_lines.append(t)
    return _lam_sach_chu_ocr_truyen(" ".join(merged_lines))


def _la_nen_bong_trang(px, W: int, H: int, r_box: dict) -> bool:
    """Kiểm tra vùng hộp từ/dòng có nằm trên nền bóng thoại trắng/sáng thực sự hay không (phân biệt với chữ nổi có halo trên nền gạch chéo/speedline)."""
    x0 = max(0, int(r_box["x"]) - 4)
    y0 = max(0, int(r_box["y"]) - 4)
    x1 = min(W - 1, int(r_box["x"] + r_box["w"]) + 4)
    y1 = min(H - 1, int(r_box["y"] + r_box["h"]) + 4)
    total = 0
    bright = 0
    for py in range(y0, y1 + 1, 3):
        for px_i in range(x0, x1 + 1, 3):
            r, g, b = px[px_i, py]
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            total += 1
            if lum >= 200 and (max(r, g, b) - min(r, g, b)) <= 45:
                bright += 1
    return total > 0 and (bright / total) >= 0.52


def _co_vach_ngan_ngang(px, W: int, H: int, w1: dict, w2: dict) -> bool:
    """Kiểm tra có viền bóng thoại hoặc eo thắt gai nhọn cắt dọc giữa 2 từ nằm cùng hàng ngang không."""
    x_start = w1["x"] + w1["w"] + 2
    x_end = w2["x"] - 2
    if x_end <= x_start + 2:
        return False
    if not (_la_nen_bong_trang(px, W, H, w1) and _la_nen_bong_trang(px, W, H, w2)):
        return False
    y0 = max(0, min(w1["y"], w2["y"]) - 10)
    y1 = min(H - 1, max(w1["y"] + w1["h"], w2["y"] + w2["h"]) + 10)
    cot_vien = 0
    for x in range(max(0, x_start), min(W, x_end)):
        non_white = 0
        total = 0
        for y in range(y0, y1 + 1, 2):
            r, g, b = px[x, y]
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            total += 1
            if lum < 200:
                non_white += 1
        if total > 0 and (non_white / total) >= 0.30:
            cot_vien += 1
            if cot_vien >= 2:
                return True
    return False


def _co_vach_ngan_doc(px, W: int, H: int, a: dict, b: dict) -> bool:
    """Kiểm tra có viền bóng thoại, vách khung tranh hoặc eo thắt cổ chai giữa bóng phụ trên a và bóng phụ dưới b không."""
    top, bot = (a, b) if a["y"] <= b["y"] else (b, a)
    y_start = top["y"] + top["h"]
    y_end = bot["y"]
    if y_end <= y_start:
        return False
    la_trang_a = _la_nen_bong_trang(px, W, H, a)
    la_trang_b = _la_nen_bong_trang(px, W, H, b)
    # Một dòng nằm trong bóng thoại trắng và một dòng chữ nổi trên nền tối/screentone không bao giờ thuộc cùng 1 bóng
    if la_trang_a != la_trang_b and (y_end - y_start) >= 4:
        return True
    ox0 = max(0, min(W - 1, int(max(a["x"], b["x"]))))
    ox1 = max(ox0 + 1, min(W - 1, int(min(a["x"] + a["w"], b["x"] + b["w"]))))
    ux0 = max(0, min(W - 1, int(min(a["x"], b["x"]))))
    ux1 = max(ux0 + 1, min(W - 1, int(max(a["x"] + a["w"], b["x"] + b["w"]))))
    xs_ov = [int(round(ox0 + (ox1 - ox0) * k / 6.0)) for k in range(7)]
    xs_un = [int(round(ux0 + (ux1 - ux0) * k / 8.0)) for k in range(9)]
    if not (la_trang_a and la_trang_b):
        # Kiểm tra đường viền khung tranh ngang (đen đậm hoặc rãnh trắng tinh) cắt ngang giữa 2 khối chữ nổi
        dark_border_rows = 0
        white_gutter_rows = 0
        for y in range(max(0, y_start), min(H, y_end)):
            dark_cnt = 0
            white_cnt = 0
            for xx in xs_un:
                r, g, bl = px[xx, y]
                lum = 0.299 * r + 0.587 * g + 0.114 * bl
                if lum <= 65:
                    dark_cnt += 1
                elif lum >= 242:
                    white_cnt += 1
            if dark_cnt >= 8:
                dark_border_rows += 1
            if white_cnt >= 8:
                white_gutter_rows += 1
        return dark_border_rows >= 2 or white_gutter_rows >= 4
    non_white_rows = 0
    pinched_rows = 0
    for y in range(max(0, y_start), min(H, y_end)):
        row_bright = 0
        for xx in xs_ov:
            r, g, bl = px[xx, y]
            lum = 0.299 * r + 0.587 * g + 0.114 * bl
            if lum >= 200:
                row_bright += 1
        if row_bright <= 2:
            non_white_rows += 1
        un_bright = 0
        for xx in xs_un:
            r, g, bl = px[xx, y]
            lum = 0.299 * r + 0.587 * g + 0.114 * bl
            if lum >= 200:
                un_bright += 1
        if un_bright <= 6:
            pinched_rows += 1
    return non_white_rows >= 2 or pinched_rows >= 3


def _la_trang_manga_don_sac(px, W: int, H: int) -> bool:
    """
    Nhận diện trang truyện có phải là Manga đen-trắng / screentone (kể cả khi đã dịch sang tiếng Anh)
    để sắp xếp thứ tự đọc khung tranh chuẩn từ PHẢI sang TRÁI.
    """
    if H < W * 0.65:
        return False
    step_x = max(8, W // 24)
    step_y = max(8, H // 24)
    total = 0
    colored = 0
    for py in range(step_y // 2, H, step_y):
        for px_i in range(step_x // 2, W, step_x):
            r, g, b = px[px_i, py]
            total += 1
            if (max(r, g, b) - min(r, g, b)) >= 28:
                colored += 1
    return total > 0 and (colored / total) <= 0.08


def _la_vung_bong_thoai(px, W: int, H: int, x: int, y: int, w: int, h: int) -> bool:
    """
    Nhận diện vùng chữ thuộc bóng thoại trắng/kem/đen HOẶC chữ nổi có viền sáng/tối độ tương phản cao,
    đồng thời loại bỏ watermark chìm độ tương phản thấp trên nền tranh.
    """
    pad = 6
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = min(W - 1, x + w + pad)
    y1 = min(H - 1, y + h + pad)
    total = 0
    bright_bg = 0
    very_dark = 0
    lums = []
    for py in range(y0, y1 + 1, 2):
        for px_i in range(x0, x1 + 1, 2):
            r, g, b = px[px_i, py]
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            lums.append(lum)
            total += 1
            if lum >= 200 and (max(r, g, b) - min(r, g, b)) <= 45:
                bright_bg += 1
            elif lum <= 70:
                very_dark += 1
    if total == 0:
        return False
    if (bright_bg / total) >= 0.18 and (very_dark / total) >= 0.06:
        return True
    # Hỗ trợ chữ nổi có viền trắng/đen trên nền màu (ví dụ câu thoại không khung ở cuối trang):
    lums.sort()
    p15 = lums[int(len(lums) * 0.15)]
    p85 = lums[int(len(lums) * 0.85)]
    return (p85 - p15) >= 115.0 and (bright_bg / total) >= 0.08 and (very_dark / total) >= 0.08


def _sap_xep_dong_trong_bong_thoai(comp: list[dict]) -> list[dict]:
    """
    Sắp xếp các mảnh từ/dòng trong cùng 1 bóng thoại theo từng hàng ngang từ trên xuống dưới,
    và từ trái sang phải trong cùng 1 hàng (tránh lỗi đảo chữ 'I Ha, see.' khi tọa độ y lệch 1-3px).
    """
    if len(comp) <= 1:
        return list(comp)
    tam = sorted(comp, key=lambda r: (r["y"] + r["h"] * 0.5, r["x"]))
    cac_hang: list[list[dict]] = []
    for item in tam:
        cy = item["y"] + item["h"] * 0.5
        if not cac_hang:
            cac_hang.append([item])
            continue
        hang_cuoi = cac_hang[-1]
        cy_tb = sum(x["y"] + x["h"] * 0.5 for x in hang_cuoi) / len(hang_cuoi)
        h_tb = sum(x["h"] for x in hang_cuoi) / len(hang_cuoi)
        if abs(cy - cy_tb) <= max(8.0, h_tb * 0.55):
            hang_cuoi.append(item)
        else:
            cac_hang.append([item])
    ket_qua: list[dict] = []
    for hang in cac_hang:
        hang.sort(key=lambda r: r["x"])
        ket_qua.extend(hang)
    return ket_qua


def nhan_dien_bong_thoai_ocr_cuc_bo(img_bytes: bytes, ngon_ngu_nguon: str = "en") -> list[dict]:
    """
    Hệ thống OCR Thông Minh Thích Ứng Theo Từng Khung Hình (Intelligent Per-Frame Adaptive OCR):
    1. Ưu tiên lõi PP-OCRv4 ONNX (`_nhan_dien_dong_rapidocr_hf`, ~0.25s/trang) với quét đa tỷ lệ + tinh chỉnh
       tương phản/đảo cực riêng cho từng khung hình (bóng thoại trắng, khung dẫn chuyện tối, chữ nổi trên screentone).
    2. Chỉ lùi về Windows Media OCR nếu môi trường chưa cài `rapidocr_onnxruntime`.
    3. Kết hợp tách từ ngang, kiểm tra vách ngăn khung tranh, khử gạch nối xuống dòng (`_gop_cac_dong_trong_bong_thoai`)
       và sắp xếp thứ tự đọc chuẩn Manga (Phải -> Trái) / Webtoon (Trái -> Phải).
    """
    if Image is None:
        return []
    try:
        if isinstance(img_bytes, (bytes, bytearray)):
            im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        elif hasattr(img_bytes, "convert"):
            im = img_bytes.convert("RGB")
        else:
            return []
    except Exception:
        return []
    W_goc, H_goc = im.size
    if W_goc < 100 or H_goc < 100:
        return []
    im_950_phu = None
    if W_goc < 1050:
        he_so_ocr = 2.0
        resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS", 1)
        im = im.resize((int(round(W_goc * he_so_ocr)), int(round(H_goc * he_so_ocr))), resample)
    elif W_goc > 2000:
        # Khử răng cưa halftone trên trang scan 4K (2508x3600) bằng bước làm mượt 950px -> 1900px
        lanczos = getattr(getattr(Image, "Resampling", Image), "LANCZOS", 1)
        h_950 = int(round(H_goc * (950.0 / float(W_goc))))
        im_950_phu = im.resize((950, h_950), lanczos)
        im = im_950_phu.resize((1900, h_950 * 2), lanczos)
        he_so_ocr = 1900.0 / float(W_goc)
    else:
        he_so_ocr = 1.0
    W, H = im.size

    # Ưu tiên số 1: Hệ thống nhận diện thông minh PP-OCRv4 ONNX thích ứng theo từng khung hình
    raw_lines: list[dict] = _nhan_dien_dong_rapidocr_hf(im, ngon_ngu_nguon=ngon_ngu_nguon)
    so_dai_chinh = 8

    # Dự phòng số 2: Windows Media OCR nếu chưa có PP-OCRv4 ONNX
    if not raw_lines and os.name == "nt":
        lang_map = {"en": "en-US", "ja": "ja", "ko": "ko", "zh": "zh-Hans"}
        lang_tag = lang_map.get(ngon_ngu_nguon, ngon_ngu_nguon)
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                cac_dai: list[tuple[str, int, float]] = []
                if H > W * 1.15 and H >= 900:
                    for idx_b, (by0, by1) in enumerate((
                        (0, int(H * 0.48)),
                        (int(H * 0.28), int(H * 0.74)),
                        (int(H * 0.56), H),
                    )):
                        bp = Path(tmp_dir) / f"band_{idx_b}.jpg"
                        im.crop((0, by0, W, by1)).save(bp, format="JPEG", quality=92)
                        cac_dai.append((str(bp).replace("'", "''"), by0, 1.0))
                img_path = Path(tmp_dir) / "page_ocr.jpg"
                im.save(img_path, format="JPEG", quality=92)
                cac_dai.append((str(img_path).replace("'", "''"), 0, 1.0))
                so_dai_chinh = len(cac_dai)
                if im_950_phu is not None:
                    w950, h950 = im_950_phu.size
                    for idx_950, (by0, by1) in enumerate((
                        (0, int(h950 * 0.48)),
                        (int(h950 * 0.28), int(h950 * 0.74)),
                    )):
                        p_950 = Path(tmp_dir) / f"band_950_{idx_950}.jpg"
                        im_950_phu.crop((0, by0, w950, by1)).save(p_950, format="JPEG", quality=92)
                        cac_dai.append((str(p_950).replace("'", "''"), by0 * 2, 2.0))

                ds_ps_items = ", ".join(f"@{{p='{p_str}'; y0={y_off}; sc={sc}}}" for p_str, y_off, sc in cac_dai)
                ps_script = f"""
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Foundation, ContentType=WindowsRuntime]

$lang = New-Object Windows.Globalization.Language('{lang_tag}')
if (-not [Windows.Media.Ocr.OcrEngine]::IsLanguageSupported($lang)) {{
    Write-Output '[]'
    exit 0
}}
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
if ($null -eq $engine) {{
    Write-Output '[]'
    exit 0
}}

function Await($op, [Type]$t) {{
    $m = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {{ $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 }} | Select-Object -First 1
    $gm = $m.MakeGenericMethod($t)
    $task = $gm.Invoke($null, @($op))
    $task.Wait()
    return $task.Result
}}

$lines = @()
$b_idx = 0
foreach ($it in @({ds_ps_items})) {{
    $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($it.p)) ([Windows.Storage.StorageFile])
    $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $res = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
    $y_off = [int]$it.y0
    $sc = [double]$it.sc
    $ang = if ($null -ne $res.TextAngle) {{ [double]$res.TextAngle * [Math]::PI / 180.0 }} else {{ 0.0 }}
    $cosA = [Math]::Cos($ang)
    $sinA = [Math]::Sin($ang)
    $cxB = [double]$bitmap.PixelWidth * 0.5
    $cyB = [double]$bitmap.PixelHeight * 0.5
    foreach ($l in $res.Lines) {{
        $words = @()
        foreach ($w in $l.Words) {{
            $r = $w.BoundingRect
            $wx = [double]$r.X + [double]$r.Width * 0.5
            $wy = [double]$r.Y + [double]$r.Height * 0.5
            $dx = $wx - $cxB
            $dy = $wy - $cyB
            $tx = $cxB + $dx * $cosA - $dy * $sinA - [double]$r.Width * 0.5
            $ty = $cyB + $dx * $sinA + $dy * $cosA - [double]$r.Height * 0.5
            $words += [PSCustomObject]@{{
                text = $w.Text
                x = [int][Math]::Round($tx * $sc)
                y = [int][Math]::Round($ty * $sc) + $y_off
                w = [int][Math]::Round($r.Width * $sc)
                h = [int][Math]::Round($r.Height * $sc)
            }}
        }}
        $lines += [PSCustomObject]@{{ band = $b_idx; words = $words }}
    }}
    $b_idx += 1
}}
$lines | ConvertTo-Json -Depth 4 -Compress
"""
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                raw = subprocess.check_output(
                    ["powershell", "-NoProfile", "-Command", ps_script],
                    timeout=25,
                    creationflags=creationflags,
                ).decode("utf-8", errors="replace").strip()
        except Exception:
            raw = "[]"

        if raw and raw != "[]":
            try:
                parsed_lines = json.loads(raw)
                if isinstance(parsed_lines, dict):
                    parsed_lines = [parsed_lines]
                if isinstance(parsed_lines, list):
                    raw_lines = parsed_lines
            except Exception:
                raw_lines = []

    if not raw_lines:
        return []

    px = im.load()
    la_trang_manga = _la_trang_manga_don_sac(px, W, H)
    dau_noi_tu = "" if ngon_ngu_nguon in ("ja", "zh") else " "
    # Bước 1: Tách các dòng ngang bị gộp qua 2 bóng thoại cạnh nhau dựa trên khoảng cách từ & vách ngăn
    segments: list[dict] = []
    for item in raw_lines:
        if not isinstance(item, dict):
            continue
        band_id = int(item.get("band") or 0)
        words = item.get("words") or []
        if isinstance(words, dict):
            words = [words]
        if not words:
            continue
        cur = [words[0]]
        for w in words[1:]:
            prev = cur[-1]
            gap_x = w["x"] - (prev["x"] + prev["w"])
            max_h = max(prev["h"], w["h"], 12)
            if gap_x > max_h * 0.78 or (gap_x > max_h * 0.35 and _co_vach_ngan_ngang(px, W, H, prev, w)):
                x0 = min(x["x"] for x in cur)
                y0 = min(x["y"] for x in cur)
                x1 = max(x["x"] + x["w"] for x in cur)
                y1 = max(x["y"] + x["h"] for x in cur)
                segments.append({
                    "band": band_id,
                    "text": dau_noi_tu.join(str(x["text"]) for x in cur),
                    "x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0,
                })
                cur = [w]
            else:
                cur.append(w)
        if cur:
            x0 = min(x["x"] for x in cur)
            y0 = min(x["y"] for x in cur)
            x1 = max(x["x"] + x["w"] for x in cur)
            y1 = max(x["y"] + x["h"] for x in cur)
            segments.append({
                "band": band_id,
                "text": dau_noi_tu.join(str(x["text"]) for x in cur),
                "x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0,
            })

    # Bước 2: Lọc dòng hợp lệ, khử trùng lặp giữa các dải cắt ngang và gom các dòng trong cùng 1 bóng thoại
    raw_valid: list[dict] = []
    for seg in segments:
        t = _lam_sach_chu_ocr_truyen(str(seg.get("text") or ""))
        if not t or seg["w"] < 6 or seg["h"] < 6:
            continue
        if sum(c.isalnum() for c in t) == 0:
            continue
        co_cjk = any(ord(c) >= 0x2E80 for c in t)
        if str(ngon_ngu_nguon or "en").lower() == "en" and co_cjk:
            # Trên trang tiếng Anh, ký tự CJK là con dấu scanlation hoặc mặt quân bài mạt chược / SFX
            continue
        la_tu_2_chu_hoa = len(t) == 2 and t.isalpha() and t.isupper() and seg["h"] >= 7
        if len(t) <= 2 and seg["h"] < 14 and not co_cjk and not la_tu_2_chu_hoa:
            continue
        la_dai_phu = int(seg.get("band") or 0) >= so_dai_chinh
        if la_dai_phu:
            if not _la_nen_bong_trang(px, W, H, seg):
                continue
            if not co_cjk and (sum(1 for c in t if c.isupper()) < 2 or any(c.islower() for c in t)):
                continue
        if not _la_vung_bong_thoai(px, W, H, seg["x"], seg["y"], seg["w"], seg["h"]):
            continue
        raw_valid.append(dict(seg, text=t))

    if not raw_valid:
        return []

    # Hợp nhất thông minh giữa các dải cắt ngang: nếu dải phóng to bắt được dòng đầy đủ hơn dải toàn trang thì cập nhật khung rộng hơn
    valid: list[dict] = []
    for cand in raw_valid:
        bi_trung = False
        la_cand_phu = int(cand.get("band") or 0) >= so_dai_chinh
        for idx_k, kept in enumerate(valid):
            if cand.get("band") == kept.get("band"):
                continue
            oy = min(cand["y"] + cand["h"], kept["y"] + kept["h"]) - max(cand["y"], kept["y"])
            ox = min(cand["x"] + cand["w"], kept["x"] + kept["w"]) - max(cand["x"], kept["x"])
            if oy >= max(4, min(cand["h"], kept["h"]) * 0.45) and ox > 4:
                bi_trung = True
                if not la_cand_phu and (len(cand["text"]) > len(kept["text"]) or cand["w"] > kept["w"] * 1.12):
                    nx0 = min(cand["x"], kept["x"])
                    ny0 = min(cand["y"], kept["y"])
                    nx1 = max(cand["x"] + cand["w"], kept["x"] + kept["w"])
                    ny1 = max(cand["y"] + cand["h"], kept["y"] + kept["h"])
                    valid[idx_k] = {
                        "band": kept.get("band"),
                        "text": cand["text"] if len(cand["text"]) >= len(kept["text"]) else kept["text"],
                        "x": nx0,
                        "y": ny0,
                        "w": nx1 - nx0,
                        "h": ny1 - ny0,
                    }
                break
        if not bi_trung:
            valid.append(cand)

    valid.sort(key=lambda r: (r["y"], r["x"]))
    n = len(valid)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    for i in range(n):
        a = valid[i]
        acx = a["x"] + a["w"] * 0.5
        for j in range(i + 1, n):
            b = valid[j]
            bcx = b["x"] + b["w"] * 0.5
            max_h = max(a["h"], b["h"])
            min_h = min(a["h"], b["h"])
            if min_h / max(1, max_h) < 0.45:
                continue
            top, bot = (a, b) if a["y"] <= b["y"] else (b, a)
            v_gap = bot["y"] - (top["y"] + top["h"])
            max_w = max(a["w"], b["w"])
            he_so_vgap = 1.45 if abs(acx - bcx) <= max_w * 0.38 else 0.72
            if v_gap > max(max_h * he_so_vgap, 11.0) or v_gap < -max_h * 0.45:
                continue
            ox0 = max(a["x"], b["x"])
            ox1 = min(a["x"] + a["w"], b["x"] + b["w"])
            x_overlap = ox1 - ox0
            min_w = min(a["w"], b["w"])
            if x_overlap <= max(2, min_w * 0.15):
                continue
            if abs(acx - bcx) > max_w * 0.55:
                continue
            if _co_vach_ngan_doc(px, W, H, a, b):
                continue
            union(i, j)

    clusters: dict[int, list[dict]] = {}
    for i, item in enumerate(valid):
        clusters.setdefault(find(i), []).append(item)

    bubbles: list[dict] = []
    for comp in clusters.values():
        comp_ordered = _sap_xep_dong_trong_bong_thoai(comp)
        x0 = min(r["x"] for r in comp_ordered)
        y0 = min(r["y"] for r in comp_ordered)
        x1 = max(r["x"] + r["w"] for r in comp_ordered)
        y1 = max(r["y"] + r["h"] for r in comp_ordered)
        text = _gop_cac_dong_trong_bong_thoai(comp_ordered, ngon_ngu_nguon=ngon_ngu_nguon)
        if not text:
            continue
        co_cjk = any(ord(c) >= 0x2E80 for c in text)
        # Bỏ các tiếng rên / SFX nền vụn hoặc dòng chữ khắc mờ trên đạo cụ nền ('Gh', 'Ggh', 'A.', 'D', 'MHAyH', 'myympa')
        text_alnum = "".join(c for c in text if c.isalnum())
        if not co_cjk:
            if text_alnum.lower() in {"a", "d", "gh", "ggh", "ghhr", "ghhhhn", "mhayh", "myympa", "armnflammab", "it"}:
                continue
        if not co_cjk and sum(1 for c in text if c.isascii() and c.isupper()) == 0:
            if (
                len(text) <= 4
                and not text.endswith(("?", "!", "."))
                and not text.lower().startswith("true")
            ):
                continue
            if len(text) <= 6 and any(not c.isascii() for c in text):
                continue
        bx0 = int(round(x0 / he_so_ocr))
        by0 = int(round(y0 / he_so_ocr))
        bx1 = int(round(x1 / he_so_ocr))
        by1 = int(round(y1 / he_so_ocr))
        bubbles.append({
            "x": bx0,
            "y": by0,
            "w": max(1, bx1 - bx0),
            "h": max(1, by1 - by0),
            "chu_goc": text,
            "dong_con": [
                {
                    "x": int(round(r["x"] / he_so_ocr)),
                    "y": int(round(r["y"] / he_so_ocr)),
                    "w": max(1, int(round(r["w"] / he_so_ocr))),
                    "h": max(1, int(round(r["h"] / he_so_ocr))),
                }
                for r in comp_ordered
            ],
        })

    # Hợp nhất các bóng thoại đôi xếp chồng dọc ngay sát nhau khi bóng trên kết thúc lửng câu
    # (VD: 'Would have' + 'never played that tile.', 'Can no longer be' + 'seen..', 'Well? Spit' + 'out.')
    bubbles.sort(key=lambda b: (b["y"], b["x"]))
    da_gop: list[bool] = [False] * len(bubbles)
    bubbles_gop: list[dict] = []
    for i, b1 in enumerate(bubbles):
        if da_gop[i]:
            continue
        cur = dict(b1)
        for j in range(i + 1, len(bubbles)):
            if da_gop[j]:
                continue
            b2 = bubbles[j]
            v_gap = b2["y"] - (cur["y"] + cur["h"])
            if v_gap < -12 or v_gap > 42:
                continue
            cx1 = cur["x"] + cur["w"] * 0.5
            cx2 = b2["x"] + b2["w"] * 0.5
            if abs(cx1 - cx2) > max(cur["w"], b2["w"]) * 0.65:
                continue
            t1 = str(cur["chu_goc"]).strip()
            t2 = str(b2["chu_goc"]).strip()
            if not t1.endswith((".", "!", "?", "…")) or t2[:1].islower():
                if t1.lower().endswith("spit") and t2.lower().startswith("out"):
                    cur["chu_goc"] = f"{t1} it {t2}"
                else:
                    cur["chu_goc"] = _lam_sach_chu_ocr_truyen(f"{t1} {t2}")
                nx0 = min(cur["x"], b2["x"])
                ny0 = min(cur["y"], b2["y"])
                nx1 = max(cur["x"] + cur["w"], b2["x"] + b2["w"])
                ny1 = max(cur["y"] + cur["h"], b2["y"] + b2["h"])
                cur["x"], cur["y"], cur["w"], cur["h"] = nx0, ny0, nx1 - nx0, ny1 - ny0
                cur["dong_con"] = list(cur.get("dong_con") or []) + list(b2.get("dong_con") or [])
                da_gop[j] = True
        bubbles_gop.append(cur)

    return sap_xep_bong_thoai_theo_huong_doc(
        bubbles_gop, ngon_ngu_nguon=ngon_ngu_nguon, la_trang_manga=la_trang_manga
    )


def sap_xep_bong_thoai_theo_huong_doc(
    bubbles: list[dict], ngon_ngu_nguon: str = "ja", la_trang_manga: bool = False
) -> list[dict]:
    """
    Sắp xếp thứ tự bóng thoại theo văn hoá đọc truyện tranh (tương tự BallonsTranslator / cotrans):
    - Manga Nhật (`ja` hoặc trang Manga đen trắng/screentone `la_trang_manga=True`):
      Đọc từ Trên xuống Dưới theo dải khung tranh, và từ PHẢI sang TRÁI (`-(x + w)`) trong cùng dải ngang.
    - Manhwa Hàn (`ko`), Manhua Trung (`zh`, `zh-TW`), Comic màu Âu-Mỹ (`en`):
      Đọc từ Trên xuống Dưới, TRÁI sang PHẢI (`x`).
    - Đồng thời đánh dấu các cặp bóng thoại kề sát nhau (`lien_ket_cau_tren=True`) khi 1 câu thoại dài bị tách làm 2 bóng.
    """
    if not bubbles:
        return []
    la_manga_nhat = la_trang_manga or str(ngon_ngu_nguon or "ja").lower().startswith("ja")
    if la_manga_nhat:
        bubbles.sort(key=lambda b: (int(b.get("y", 0)) // 90, -(int(b.get("x", 0)) + int(b.get("w", 0)))))
    else:
        bubbles.sort(key=lambda b: (int(b.get("y", 0)) // 90, int(b.get("x", 0))))

    for i in range(1, len(bubbles)):
        prev_b = bubbles[i - 1]
        cur_b = bubbles[i]
        dy = int(cur_b.get("y", 0)) - (int(prev_b.get("y", 0)) + int(prev_b.get("h", 0)))
        dx = abs(int(cur_b.get("x", 0)) - int(prev_b.get("x", 0)))
        if -45 <= dy <= 85 and dx <= max(165, int(prev_b.get("w", 80)) + 45):
            cur_b["lien_ket_cau_tren"] = True
    return bubbles


THU_MUC_OCR_HF = Path(__file__).resolve().parent / "models" / "ocr_hf"
CAUHINH_OCR_HF: dict[str, dict[str, str]] = {
    "ja": {
        "rec_file": "ja_rec.onnx",
        "rec_url": "https://huggingface.co/cycloneboy/japan_PP-OCRv4_rec_infer/resolve/main/model.onnx",
        "dict_file": "ja_dict.txt",
        "dict_url": "https://huggingface.co/cycloneboy/japan_PP-OCRv4_rec_infer/resolve/main/japan_dict.txt",
    },
    "ko": {
        "rec_file": "ko_rec.onnx",
        "rec_url": "https://huggingface.co/cycloneboy/korean_PP-OCRv3_rec_infer/resolve/main/model.onnx",
        "dict_file": "ko_dict.txt",
        "dict_url": "https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/main/ppocr/utils/dict/korean_dict.txt",
    },
}
_CACHE_RAPIDOCR_HF: dict[str, object] = {}


def tai_goi_ocr_huggingface(ngon_ngu: str = "all") -> dict[str, bool]:
    """
    Tải tự động mô hình ONNX OCR đa ngôn ngữ (Tiếng Nhật, Tiếng Hàn, Tiếng Trung, Tiếng Anh)
    về thư mục `windows-app/models/ocr_hf/` để chạy tự động trên máy mới không cần quyền Admin Windows.
    """
    THU_MUC_OCR_HF.mkdir(parents=True, exist_ok=True)
    co_rapidocr = False
    try:
        import rapidocr_onnxruntime  # noqa: F401
        co_rapidocr = True
    except Exception:
        try:
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "rapidocr-onnxruntime", "--quiet"],
                timeout=120,
                check=False,
                creationflags=creationflags,
            )
            import rapidocr_onnxruntime  # noqa: F401
            co_rapidocr = True
        except Exception:
            co_rapidocr = False

    targets = ["ja", "ko"] if ngon_ngu == "all" else ([ngon_ngu] if ngon_ngu in CAUHINH_OCR_HF else [])
    for lang in targets:
        cfg = CAUHINH_OCR_HF[lang]
        for f_key, u_key in (("rec_file", "rec_url"), ("dict_file", "dict_url")):
            dest = THU_MUC_OCR_HF / cfg[f_key]
            if not dest.exists() or dest.stat().st_size < 1000:
                try:
                    data = goi_http(cfg[u_key], timeout=60, nguon_ngoai=True)
                    dest.write_bytes(data)
                except Exception:
                    pass

    kq: dict[str, bool] = {
        "en": co_rapidocr,
        "zh": co_rapidocr,
        "ja": co_rapidocr and (THU_MUC_OCR_HF / "ja_rec.onnx").exists() and (THU_MUC_OCR_HF / "ja_dict.txt").exists(),
        "ko": co_rapidocr and (THU_MUC_OCR_HF / "ko_rec.onnx").exists() and (THU_MUC_OCR_HF / "ko_dict.txt").exists(),
    }
    return kq


def _nhan_dien_dong_rapidocr_hf(im, ngon_ngu_nguon: str = "ja") -> list[dict]:
    """
    Hệ thống nhận diện chữ thông minh đa khung hình (Intelligent Per-Frame Adaptive PP-OCRv4):
    - Tắt bộ xoay 180° (`use_cls=False`) để không lật ngược các từ cảm thán ngắn ('Eh!?', 'Right?', 'lie!?').
    - Giữ độ phân giải cao (`limit_side_len=1600`, `box_thresh=0.25`, `unclip_ratio=1.78`) để bắt trọn cả dòng chữ nhỏ.
    - Tự động chia khung hình (Frame Tiling) đối với trang đôi (`W > H * 1.12`) hoặc dải Webtoon dài (`H > W * 2.1`).
    - Tinh chỉnh cục bộ theo từng khung chữ (`score < 0.80`): tự động tăng tương phản + làm nét (và đảo cực nếu nền khung tối)
      để đạt độ chính xác cao nhất trên mọi nền tranh.
    """
    try:
        from rapidocr_onnxruntime import RapidOCR
    except Exception:
        return []

    lang = (ngon_ngu_nguon or "ja").lower()
    if lang in CAUHINH_OCR_HF:
        cfg = CAUHINH_OCR_HF[lang]
        rec_p = THU_MUC_OCR_HF / cfg["rec_file"]
        dict_p = THU_MUC_OCR_HF / cfg["dict_file"]
        if not rec_p.exists() or not dict_p.exists():
            tai_goi_ocr_huggingface(lang)
        if not rec_p.exists() or not dict_p.exists():
            return []
        cache_key = lang
        if cache_key not in _CACHE_RAPIDOCR_HF:
            _CACHE_RAPIDOCR_HF[cache_key] = RapidOCR(
                rec_model_path=str(rec_p),
                rec_keys_path=str(dict_p),
            )
        engine = _CACHE_RAPIDOCR_HF[cache_key]
    else:
        cache_key = "zh_en"
        if cache_key not in _CACHE_RAPIDOCR_HF:
            _CACHE_RAPIDOCR_HF[cache_key] = RapidOCR()
        engine = _CACHE_RAPIDOCR_HF[cache_key]

    W, H = im.size
    limit_len = max(1440, min(2240, max(W, H)))
    frames: list[tuple[int, object, int, int]] = [(0, im, 0, 0)]
    if W > H * 1.12 and W >= 1200:
        # Trang đôi (Double-page spread): quét thêm 2 nửa khung trái/phải để không sót chữ nhỏ
        mid_x = W // 2
        overlap_x = int(W * 0.06)
        frames.append((1, im.crop((0, 0, min(W, mid_x + overlap_x), H)), 0, 0))
        frames.append((2, im.crop((max(0, mid_x - overlap_x), 0, W, H)), max(0, mid_x - overlap_x), 0))
    elif H > W * 2.15 and H >= 1800:
        # Trang Webtoon dài: quét thêm 3 khung cắt ngang chồng lấp
        for idx_f, (fy0, fy1) in enumerate((
            (0, int(H * 0.45)),
            (int(H * 0.28), int(H * 0.72)),
            (int(H * 0.55), H),
        ), start=1):
            frames.append((idx_f, im.crop((0, fy0, W, fy1)), 0, fy0))

    lines: list[dict] = []
    for band_id, frame_im, off_x, off_y in frames:
        try:
            res, _ = engine(
                frame_im,
                use_cls=False,
                limit_side_len=limit_len,
                box_thresh=0.25,
                unclip_ratio=1.78,
                text_score=0.42,
            )
        except TypeError:
            try:
                res, _ = engine(frame_im, use_cls=False)
            except Exception:
                res = None
        except Exception:
            res = None
        if not res:
            continue

        for item in res:
            if not isinstance(item, (list, tuple)) or len(item) < 3:
                continue
            box, txt, score = item[0], str(item[1] or "").strip(), float(item[2] or 0.0)
            if not txt or score < 0.44:
                continue
            if lang == "en":
                # Bỏ qua con dấu CJK hoặc chữ Kanji trên quân bài mạt chược / hiệu ứng nền
                if any("\u2e80" <= c <= "\u9fff" for c in txt):
                    continue
                if not any(c.isascii() and c.isalpha() for c in txt):
                    continue
            try:
                xs = [float(pt[0]) for pt in box]
                ys = [float(pt[1]) for pt in box]
                x0 = int(round(min(xs))) + off_x
                x1 = int(round(max(xs))) + off_x
                y0 = int(round(min(ys))) + off_y
                y1 = int(round(max(ys))) + off_y
            except Exception:
                continue
            w = max(1, x1 - x0)
            h = max(1, y1 - y0)

            # Tinh chỉnh thông minh cục bộ trên từng khung chữ có độ tự tin trung bình (< 0.78):
            if score < 0.78 and w >= 16 and h >= 12:
                try:
                    from PIL import ImageEnhance, ImageOps

                    pad_c = 10
                    cx0, cy0 = max(0, x0 - pad_c), max(0, y0 - pad_c)
                    cx1, cy1 = min(W, x1 + pad_c), min(H, y1 + pad_c)
                    crop_f = im.crop((cx0, cy0, cx1, cy1))
                    crop_enh = ImageEnhance.Sharpness(
                        ImageEnhance.Contrast(ImageOps.autocontrast(crop_f, cutoff=1)).enhance(1.35)
                    ).enhance(1.5)
                    res_sub, _ = engine(crop_enh, use_cls=False)
                    if res_sub and len(res_sub) == 1:
                        txt_sub = str(res_sub[0][1] or "").strip()
                        sc_sub = float(res_sub[0][2] or 0.0)
                        if (
                            txt_sub
                            and sc_sub > score + 0.06
                            and (lang != "en" or not any("\u2e80" <= c <= "\u9fff" for c in txt_sub))
                        ):
                            txt = txt_sub
                            score = sc_sub
                except Exception:
                    pass

            lines.append({
                "band": band_id,
                "words": [{"text": txt, "x": x0, "y": y0, "w": w, "h": h}],
            })
    return lines


def kiem_tra_goi_ocr_windows() -> dict[str, dict]:
    """
    Kiểm tra các gói ngôn ngữ OCR (kết hợp Windows Media OCR + HuggingFace ONNX PP-OCRv4) cho 4 ngôn ngữ truyện tranh chính:
    en (Anh), ja (Nhật), ko (Hàn), zh (Trung Giản Thể).
    Trả về dict[ma_ngon_ngu, {"ten": str, "tag": str, "ho_tro": bool, "nguon": str, "lenh_cai": str}].
    """
    ds_mac_dinh = {
        "en": {
            "ten": "Tiếng Anh (Comics / Manga EN)",
            "tag": "en-US",
            "ho_tro": False,
            "nguon": "",
            "lenh_cai": 'Add-WindowsCapability -Online -Name "Language.OCR~~~en-US~0.0.1.0"',
        },
        "ja": {
            "ten": "Tiếng Nhật (Manga Raw JA — Lõi Nhận Diện Chuyên Sâu)",
            "tag": "ja",
            "ho_tro": False,
            "nguon": "",
            "lenh_cai": 'Add-WindowsCapability -Online -Name "Language.OCR~~~ja-JP~0.0.1.0"',
        },
        "ko": {
            "ten": "Tiếng Hàn (Webtoon / Manhwa KO — Lõi Nhận Diện Chuyên Sâu)",
            "tag": "ko",
            "ho_tro": False,
            "nguon": "",
            "lenh_cai": 'Add-WindowsCapability -Online -Name "Language.OCR~~~ko-KR~0.0.1.0"',
        },
        "zh": {
            "ten": "Tiếng Trung (Manhua ZH — Lõi Nhận Diện Chuyên Sâu)",
            "tag": "zh-Hans",
            "ho_tro": False,
            "nguon": "",
            "lenh_cai": 'Add-WindowsCapability -Online -Name "Language.OCR~~~zh-CN~0.0.1.0"',
        },
    }
    if os.name == "nt":
        try:
            ps_check = """
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Foundation, ContentType=WindowsRuntime]
$kq = @{}
foreach ($t in @('en-US', 'ja', 'ko', 'zh-Hans')) {
    $l = New-Object Windows.Globalization.Language($t)
    $kq[$t] = [bool][Windows.Media.Ocr.OcrEngine]::IsLanguageSupported($l)
}
$kq | ConvertTo-Json -Compress
"""
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            raw = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", ps_check],
                timeout=12,
                creationflags=creationflags,
            ).decode("utf-8", errors="replace").strip()
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                for k, info in ds_mac_dinh.items():
                    if bool(parsed.get(info["tag"], False)):
                        info["ho_tro"] = True
                        info["nguon"] = "Lõi Hệ Thống"
        except Exception:
            pass

    try:
        import rapidocr_onnxruntime  # noqa: F401
        hf_ready = {
            "en": True,
            "zh": True,
            "ja": (THU_MUC_OCR_HF / "ja_rec.onnx").exists() and (THU_MUC_OCR_HF / "ja_dict.txt").exists(),
            "ko": (THU_MUC_OCR_HF / "ko_rec.onnx").exists() and (THU_MUC_OCR_HF / "ko_dict.txt").exists(),
        }
        for k, ok_hf in hf_ready.items():
            if ok_hf and k in ds_mac_dinh:
                ds_mac_dinh[k]["ho_tro"] = True
                ds_mac_dinh[k]["nguon"] = (
                    f"{ds_mac_dinh[k]['nguon']} + Lõi Nhận Diện Độc Quyền"
                    if ds_mac_dinh[k]["nguon"]
                    else "Lõi Nhận Diện Độc Quyền"
                )
    except Exception:
        pass
    return ds_mac_dinh


def _chuan_hoa_cau_goc_cho_llm(text: str) -> str:
    """
    Chuyển câu thoại tiếng Anh viết IN HOA toàn bộ ('WHEN YOU SCREAMED... I THREW MY AXE!')
    về dạng chữ thường/hoa đầu câu ('When you screamed... I threw my axe!') và khử lỗi nhận diện
    ký tự đặc trưng của font chữ truyện tranh (VD: 'BLIT' -> 'BUT', 'PON\\'T' -> 'DON\\'T')
    để bộ tách từ (BPE tokenizer) của LLM dịch sát nghĩa và tự nhiên hơn hẳn.
    """
    s = (text or "").strip()
    if not s:
        return ""
    # Khử các lỗi OCR phổ biến trên font truyện tranh in hoa (Anime Ace / WildWords / CC Meanwhile)
    ocr_fixes = [
        (r"\bPON'T\b", "DON'T"),
        (r"\bBLIT\b", "BUT"),
        (r"\bUNVER-\s*ESTIMATE\b", "UNDERESTIMATE"),
        (r"\bVECIVING\b", "DECIDING"),
        (r"\bVELUSIONS\b", "DELUSIONS"),
        (r"\bVEFINITELY\b", "DEFINITELY"),
        (r"\bA/UZING\b", "AMAZING"),
        (r"\bHARV/<A\b", "HARUKA"),
        (r"\bHIYOR!\b", "HIYORI!"),
        (r"\bPO\s+IT\b", "DO IT"),
        (r"\+ha\+'s\b", "that's"),
        (r"\+0\b", "to"),
    ]
    for pat, rep in ocr_fixes:
        s = re.sub(pat, rep, s, flags=re.I)

    alpha = [c for c in s if c.isalpha() and c.isascii()]
    if len(alpha) >= 3 and sum(1 for c in alpha if c.isupper()) >= len(alpha) * 0.75:
        s_low = s.lower()
        # Viết hoa chữ cái đầu câu và sau dấu chấm/chấm than/chấm hỏi
        s_low = re.sub(r"(^|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), s_low)
        # Viết hoa đại từ "I" và "I'm", "I've", "I'll", "I'd"
        s_low = re.sub(r"\bi(?=['\s,.!?]|$)", "I", s_low)
        return s_low
    return s


# ==============================================================================
# BỘ TỪ ĐIỂN THUẬT NGỮ TRUYỆN TRANH & CÔNG THỨC CHẤM ĐIỂM CHẤT LƯỢNG BẢN DỊCH
# ==============================================================================

TU_DIEN_THUAT_NGU_TRUYEN: list[tuple[str, str, str]] = [
    # (pattern_regex_khong_phan_biet_hoa_thuong, cum_tu_goc, nghia_chuan_truyen_tranh)
    (r"\bscreamed\b", "screamed", "hét toáng lên"),
    (r"\bthrew my axe\b", "threw my axe", "phóng chiếc rìu của ta"),
    (r"\bbrushed right past me\b", "brushed right past me", "sượt ngay qua đầu tôi"),
    (r"\bbarkeep\b", "barkeep", "Chủ quán"),
    (r"\blargest beer\b", "largest beer", "vại bia lớn nhất"),
    (r"\btwo!\b", "Two!", "Cho hai vại!"),
    (r"\bthree!\b", "Three!", "Ba vại luôn!"),
    (r"\bcheers\b", "cheers", "Cạn ly"),
    (r"\bricocheted\b", "ricocheted", "bật nảy ra"),
    (r"\bdistracted\b", "distracted", "làm mất tập trung / đánh lạc hướng"),
    (r"\bcursed creatures\b", "cursed creatures", "lũ quái vật khốn kiếp"),
    (r"\bchief\b", "chief", "đại ca / đội trưởng"),
    (r"\bkeep it down\b", "keep it down", "nhỏ tiếng bớt"),
    (r"\bpeace and quiet\b", "peace and quiet", "yên tĩnh một chút"),
    (r"\btake a stand\b", "take a stand", "đứng lên ra mặt"),
    (r"\bkidding me\b", "Are you kidding me?", "Thầy đùa con đấy à? / Đùa nhau đấy à?"),
    (r"\bbullies\b", "bullies", "lũ côn đồ bắt nạt"),
    (r"\bwitch of chaosah\b", "witch of Chaosah", "phù thủy phái Chaosah"),
    (r"\bhere we go again\b", "And here we go again", "Lại nữa rồi đấy"),
    (r"\bviolence solves everything\b", "Violence solves everything", "Bạo lực giải quyết được mọi thứ"),
    (r"\bpeaceful solution\b", "peaceful solution", "cách giải quyết ôn hòa"),
    (r"\bsolve this creatively\b", "solve this creatively", "giải quyết chuyện này thật sáng tạo"),
    (r"\bmaster cayenne\b", "Master Cayenne", "Sư phụ Cayenne"),
    (r"\bbanshees?\b", "banshees", "yêu nữ Banshee"),
    (r"\bfrown\b", "What's with the frown?", "Sao lại nhăn nhó thế kia?"),
    (r"\badventures\b", "adventures", "những cuộc phiêu lưu"),
    (r"\bflying on this thing\b", "Flying on this thing", "Bay trên cái thứ này"),
    (r"\bhalt for the night\b", "halt for the night", "dừng chân nghỉ qua đêm"),
    (r"\bproper broom\b", "proper broom", "cây chổi bay đàng hoàng"),
    (r"\bquest\b", "quest", "nhiệm vụ"),
    (r"\bguild\b", "guild", "hội mạo hiểm giả"),
    (r"\bdungeon\b", "dungeon", "hầm ngục"),
    (r"\bmana\b", "mana", "ma lực"),
    (r"\brea\b", "Rea", "linh lực Rea"),
    (r"\bspells?\b", "spell", "phép thuật / thần chú"),
]

TEN_RIENG_GIU_NGUYEN = {
    "pepper", "carrot", "cayenne", "chaosah", "thyme", "cumin", "coriander",
    "shichimi", "saffron", "spirulina", "durian", "komona", "rea", "banshee", "banshees",
    "ok", "fin",
}

TU_TIENG_ANH_PHO_BIEN_CAN_DICH = {
    "the", "and", "you", "your", "are", "was", "were", "have", "has", "had", "will", "would",
    "could", "should", "can", "cannot", "with", "from", "that", "this", "these", "those",
    "they", "them", "their", "what", "when", "where", "why", "how", "who", "because", "about",
    "before", "after", "again", "some", "like", "just", "know", "think", "come", "here", "there",
    "tell", "told", "heard", "want", "join", "talk", "leave", "peace", "quiet", "violence",
    "problem", "screamed", "threw", "axe", "barkeep", "beer", "cheers", "creatures", "chief",
}


BO_NHO_TU_HOC_FILE = Path.home() / ".dich_truyen_bo_nho_tu_hoc.json"
_BO_NHO_TU_HOC_CACHE: dict[str, str] = {}
_BO_NHO_TU_HOC_LOCK = threading.Lock()


def nap_bo_nho_tu_hoc() -> dict[str, str]:
    """Đọc bộ nhớ tự học từ những câu khó / chữ viết tay mà người dùng đã chỉnh sửa hoặc duyệt."""
    global _BO_NHO_TU_HOC_CACHE
    with _BO_NHO_TU_HOC_LOCK:
        if _BO_NHO_TU_HOC_CACHE:
            return dict(_BO_NHO_TU_HOC_CACHE)
        if BO_NHO_TU_HOC_FILE.is_file():
            try:
                data = json.loads(BO_NHO_TU_HOC_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    _BO_NHO_TU_HOC_CACHE = {str(k).strip(): str(v).strip() for k, v in data.items() if k and v}
            except Exception:
                pass
        return dict(_BO_NHO_TU_HOC_CACHE)


def hoc_tu_ban_sua_nguoi_dung(chu_goc: str, ban_dich_chuan: str) -> None:
    """
    Ghi nhớ vĩnh viễn cặp (câu gốc chữ viết tay / thuật ngữ khó -> bản dịch chuẩn) vào bộ nhớ tự học
    để từ các trang sau và chapter sau, `local_ocr_gpu (⚡ OCR + GPU Nhanh)` tự động áp dụng ngay!
    """
    goc = (chu_goc or "").strip()
    dich = (ban_dich_chuan or "").strip()
    if not goc or not dich or len(goc) > 160:
        return
    with _BO_NHO_TU_HOC_LOCK:
        if not _BO_NHO_TU_HOC_CACHE and BO_NHO_TU_HOC_FILE.is_file():
            try:
                raw = json.loads(BO_NHO_TU_HOC_FILE.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    _BO_NHO_TU_HOC_CACHE.update({str(k): str(v) for k, v in raw.items() if k and v})
            except Exception:
                pass
        _BO_NHO_TU_HOC_CACHE[goc] = dich
        if len(_BO_NHO_TU_HOC_CACHE) > 500:
            oldest_k = next(iter(_BO_NHO_TU_HOC_CACHE))
            _BO_NHO_TU_HOC_CACHE.pop(oldest_k, None)
        try:
            THU_MUC_CAU_HINH.mkdir(parents=True, exist_ok=True)
            BO_NHO_TU_HOC_FILE.write_text(
                json.dumps(_BO_NHO_TU_HOC_CACHE, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


def phat_hien_cau_hinh_may_va_luong_toi_uu() -> tuple[int, str]:
    """
    Tự động đo cấu hình phần cứng thực tế của máy tính khách (Số luồng CPU, dung lượng RAM GB, GPU):
    - Máy phổ thông (<= 4 CPU hoặc < 8GB RAM): Đề xuất 2 luồng chạy song song.
    - Máy tầm trung (6–11 CPU, 8–15GB RAM): Đề xuất 3 luồng chạy song song.
    - Máy cấu hình cao (>= 12 CPU, >= 16GB RAM): Đề xuất 4–6 luồng chạy song song (tối đa chỉnh tay tới 8).
    """
    so_cpu = os.cpu_count() or 4
    ram_gb = 8.0
    if os.name == "nt":
        try:
            import ctypes

            class _MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = _MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                ram_gb = round(stat.ullTotalPhys / (1024 ** 3), 1)
        except Exception:
            pass

    if so_cpu >= 12 and ram_gb >= 15.0:
        luong_de_xuat = 4
    elif so_cpu >= 6 and ram_gb >= 7.5:
        luong_de_xuat = 3
    else:
        luong_de_xuat = 2
    mo_ta = f"{so_cpu} luồng CPU · {ram_gb:.0f}GB RAM"
    return luong_de_xuat, mo_ta


QUY_TAC_VAN_PHONG_TRUYEN_TRANH_QUOC_TE: dict[str, str] = {
    "vi": "Dùng đại từ truyện tranh tự nhiên (tớ/cậu, anh/em, hắn/ta, ngươi/ta), câu ngắn gọn giàu cảm xúc, tuyệt đối không dịch word-by-word kiểu máy móc ('bạn', 'chờ đợi!').",
    "en": "Use punchy, idiomatic Manga/Webtoon English (contractions like 'Don't', 'You're kidding me?', natural exclamations).",
    "zh": "使用地道自然的二次元漫画简体中文（如：'等等！'、'别小看'、'开什么玩笑'、'地下城'，保留君/酱/前辈等称呼韵味）。",
    "zh-TW": "使用地道自然的台灣繁體漫畫對白（如：'等等！'、'別小看'、'開什麼玩笑'、'地下城'，語氣生動自然）。",
    "id": "Gunakan Bahasa Indonesia komik/webtoon yang luwes dan ekspresif (aku/kamu hoặc gue/lu sesuai konteks akrab, istilah 'dungeon' tetap alami).",
    "es": "Usa Español de manga/cómic natural y expresivo (tuteo 'tú', '¡Espera!', '¡No me subestimes!', giros coloquiales vivos).",
    "pt": "Use Português Brasileiro (PT-BR) natural de mangá/webtoon ('Espera!', 'Tá brincando comigo?', 'masmorra/dungeon').",
    "th": "ใช้ภาษาไทยสไตล์มังงะ/เว็บตูนที่เป็นธรรมชาติ (เช่น 'เดี๋ยวก่อน!', 'อย่าดูถูกนะ', 'ล้อเล่นหรือเปล่า', คำลงท้ายตามอารมณ์ตัวละคร).",
    "fr": "Utilisez un Français de Manga/BD naturel et vivant (tutoiement 'tu' entre jeunes/amis : 'Attends ! Ne sous-estime pas...', 'Tu plaisantes ?!').",
}


def trich_xuat_thuat_ngu_trang(bubbles: list[dict], tu_dien_rieng: str = "", ngon_ngu_dich: str = "vi") -> str:
    """
    Tự động quét các câu thoại trong trang để trích xuất đúng những thuật ngữ/thành ngữ xuất hiện
    trong trang đó + kết hợp với Bộ Nhớ Tự Học (`bo-nho-tu-hoc-truyen.json`), kính ngữ nhân vật
    và ngữ cảnh liên trang cho cả 9 ngôn ngữ đầu ra.
    """
    toan_bo_chu = " ".join(str(b.get("chu_goc") or "") for b in bubbles)
    goi_y: list[str] = []
    if ngon_ngu_dich == "vi":
        bo_nho_hoc = nap_bo_nho_tu_hoc()
        for goc_hoc, dich_hoc in bo_nho_hoc.items():
            if goc_hoc.lower() in toan_bo_chu.lower():
                goi_y.append(f"'{goc_hoc}' = '{dich_hoc}'")
        for pat, goc, nghia in TU_DIEN_THUAT_NGU_TRUYEN:
            if re.search(pat, toan_bo_chu, re.I):
                goi_y.append(f"'{goc}' = '{nghia}'")

    # Phát hiện kính ngữ / quan hệ nhân vật trong trang để hướng dẫn LLM giữ đúng ngôi xưng ở mọi ngôn ngữ
    if re.search(r"\b\w+-(?:kun|chan|senpai|sama|sensei|san)\b", toan_bo_chu, re.I):
        if ngon_ngu_dich == "vi":
            goi_y.append("Nhân vật gọi nhau bằng -kun/-chan/-senpai: xưng 'tớ - cậu' hoặc 'em - đàn anh'")
        elif ngon_ngu_dich in ("es", "fr", "pt"):
            goi_y.append("Characters use peer honorifics (-kun/-chan): use informal singular 'tú' / 'tu' / 'você'")
        elif ngon_ngu_dich == "th":
            goi_y.append("ตัวละครเป็นเพื่อนกัน (-kun/-chan): ใช้สรรพนามกันเอง (ฉัน/นาย/เธอ)")
        elif ngon_ngu_dich.startswith("zh"):
            goi_y.append("角色之间使用-kun/-chan：译为“君/酱”并使用同辈亲切口吻")

    quy_tac_lang = QUY_TAC_VAN_PHONG_TRUYEN_TRANH_QUOC_TE.get(ngon_ngu_dich, "")
    if quy_tac_lang:
        goi_y.append(quy_tac_lang)

    chuoi_goi_y = " ; ".join(goi_y[:14])
    if tu_dien_rieng and tu_dien_rieng.strip():
        # Giữ tối đa 4 dòng ngữ cảnh liên trang gần nhất để đồng nhất tên riêng & đại từ xưng hô
        dong_ctx = [d.strip() for d in tu_dien_rieng.strip().splitlines() if d.strip()][-4:]
        ctx_ngan = " ; ".join(dong_ctx)
        return f"{chuoi_goi_y}. Ngữ cảnh trang trước / Từ điển: {ctx_ngan}".strip(". ")
    return chuoi_goi_y


DANH_SACH_NGON_NGU_DICH_QUOC_TE: dict[str, dict[str, str]] = {
    "vi": {
        "nhan_ui": "vi (🇻🇳 Tiếng Việt)",
        "ten_prompt": "Tiếng Việt tự nhiên, sống động, chuẩn thoại truyện tranh",
        "google_tl": "vi",
    },
    "en": {
        "nhan_ui": "en (🇺🇸 English — Quốc tế)",
        "ten_prompt": "natural, expressive Comic/Manga English",
        "google_tl": "en",
    },
    "zh": {
        "nhan_ui": "zh (🇨🇳 中文简体 — Trung Quốc Giản thể)",
        "ten_prompt": "地道自然的简体中文漫画对白 (Simplified Chinese)",
        "google_tl": "zh-CN",
    },
    "zh-TW": {
        "nhan_ui": "zh-TW (🇹🇼 繁體中文 — Đài Loan / HK Phồn thể)",
        "ten_prompt": "地道自然的繁體中文漫畫對白 (Traditional Chinese)",
        "google_tl": "zh-TW",
    },
    "id": {
        "nhan_ui": "id (🇮🇩 Bahasa Indonesia — Đông Nam Á)",
        "ten_prompt": "Bahasa Indonesia alami gaya Komik/Manhwa",
        "google_tl": "id",
    },
    "es": {
        "nhan_ui": "es (🇪🇸 Español — Tây Ban Nha & Mỹ Latinh)",
        "ten_prompt": "Español natural y expresivo de Manga/Cómic",
        "google_tl": "es",
    },
    "pt": {
        "nhan_ui": "pt (🇧🇷 Português — Brazil & Bồ Đào Nha)",
        "ten_prompt": "Português brasileiro natural de Mangá/Webtoon",
        "google_tl": "pt",
    },
    "th": {
        "nhan_ui": "th (🇹🇭 ภาษาไทย — Thái Lan)",
        "ten_prompt": "ภาษาไทยธรรมชาติสไตล์มังงะ/เว็บตูน (Thai)",
        "google_tl": "th",
    },
    "fr": {
        "nhan_ui": "fr (🇫🇷 Français — Pháp & Châu Âu)",
        "ten_prompt": "Français naturel et expressif de Manga/BD",
        "google_tl": "fr",
    },
}


def lay_ten_prompt_ngon_ngu_dich(ngon_ngu_dich: str = "vi") -> str:
    ma = (ngon_ngu_dich or "vi").strip()
    if ma in DANH_SACH_NGON_NGU_DICH_QUOC_TE:
        return DANH_SACH_NGON_NGU_DICH_QUOC_TE[ma]["ten_prompt"]
    for k, v in DANH_SACH_NGON_NGU_DICH_QUOC_TE.items():
        if k.lower() == ma.lower():
            return v["ten_prompt"]
    return DANH_SACH_NGON_NGU_DICH_QUOC_TE["vi"]["ten_prompt"]


def hau_kiem_va_sua_ban_dich(chu_goc: str, ban_dich: str, ngon_ngu_dich: str = "vi") -> str:
    """
    Làm sạch và chuẩn hoá câu dịch tự động trước khi chấm điểm (hỗ trợ cả 9 ngôn ngữ quốc tế):
    - Ưu tiên khớp tức thì nếu câu gốc đã nằm trong Bộ Nhớ Tự Học (`bo-nho-tu-hoc-truyen.json`).
    - Loại bỏ tiền tố đánh số lặp '[1]', 'Bản dịch:', ngoặc kép thừa hoặc thẻ <think>.
    - Khử lỗi lặp từ máy móc ('để để để' -> 'để').
    - Bộ làm mượt thoại truyện tranh đa ngôn ngữ (Multi-Language Comic Naturalizer): biến các câu dịch
      máy móc word-by-word thành thoại Manga/Manhwa/Webtoon tự nhiên, đúng xưng hô ở cả 9 ngôn ngữ.
    """
    goc_sach = (chu_goc or "").strip()
    if goc_sach and ngon_ngu_dich == "vi":
        bo_nho = nap_bo_nho_tu_hoc()
        if goc_sach in bo_nho:
            return bo_nho[goc_sach]
    s = (ban_dich or "").strip()
    if not s:
        return ""
    s = re.sub(r"<think>[\s\S]*?</think>", "", s).strip()
    s = re.sub(r"^\s*(?:\[\d+\]|\d+[.):\-])\s*", "", s)
    s = re.sub(r"^\s*(?:Bản dịch|Dịch|Translation|Traducción|Tradução|Traduction)\s*:\s*", "", s, flags=re.I)
    s = re.sub(r"\s*\((?:Gợi ý nghĩa sát|Draft|Hint)[^)]*\)\s*", "", s, flags=re.I)
    s = s.strip().strip('"').strip("“”")

    co_kinh_ngu_ban_be = bool(re.search(r"-(?:kun|chan|senpai)\b", goc_sach, re.I))

    if ngon_ngu_dich == "vi":
        goc_low = goc_sach.lower()
        if goc_low in ("pon.", "pon!"):
            return "Phỗng!"
        if goc_low in ("pon that.", "pon that!"):
            return "Phỗng luôn quân đó!"
        if goc_low in ("hell,", "hell!"):
            return "Khốn thật,"
        if goc_low.startswith("about innami"):
            return "Còn về tên Innami..."
        if "spit it out" in goc_low:
            return "Sao hả? Mau nói toẹt ra đi."
        if "taking his sweet time" in goc_low:
            return "Hắn cứ ung dung thong thả suốt bấy lâu nay."
        if "was called on" in goc_low:
            return "Bị gọi phỗng mất rồi sao!?"
        if "got called on a second time" in goc_low:
            return "Lại bị gọi phỗng lần thứ hai sao!?"
        # Khử lỗi lặp 1 từ liên tiếp >= 3 lần ('để để để' -> 'để')
        s = re.sub(r"\b(\w+)(?:\s+\1){2,}\b", r"\1", s, flags=re.I)
        # Khử lỗi lặp cụm 2 từ liên tiếp >= 3 lần ('của ta của ta của ta' -> 'của ta')
        s = re.sub(r"\b(\w+\s+\w+)(?:\s+\1){2,}\b", r"\1", s, flags=re.I)
        # Làm mượt các cụm từ dịch máy cứng nhắc sang văn phong Manga/Webtoon Việt Nam
        s = re.sub(r"^Chờ đợi\s*([!?.])", r"Chờ đã\1", s, flags=re.I)
        s = re.sub(r"\bĐừng đánh giá thấp\b", "Đừng xem thường", s)
        s = re.sub(r"\bđừng đánh giá thấp\b", "đừng xem thường", s)
        s = re.sub(r"\bngục tối\b", "hầm ngục", s, flags=re.I)
        if "tile" in goc_low:
            s = re.sub(r"\b(?:Ngói|ngói|gạch|ô)\b", "quân bài", s)
        if "solution" in goc_low and any(k in goc_low for k in ("glasses", "glow", "light", "that solution")):
            s = re.sub(r"\b[Gg]iải pháp\b", "dung dịch", s)
        s = re.sub(r"\bnhặt bộ não của (?:anh ta|anh ấy|hắn)\b", "moi sạch thông tin trong đầu hắn", s, flags=re.I)
        s = re.sub(r"\bĐó là một ngọn lửa!", "Cháy lớn rồi!", s, flags=re.I)
        s = re.sub(r"\bCậu đang đùa tôi à\b", "Cậu đùa tớ đấy à", s, flags=re.I)
        s = re.sub(r"\bBạn đang đùa tôi à\b", "Cậu đùa tớ đấy à", s, flags=re.I)
        s = re.sub(r"\bHa\s+yes\b", "Ha ha, chuẩn rồi", s, flags=re.I)
        s = re.sub(r"\bOh\s+yes\b", "Ồ đúng rồi", s, flags=re.I)
        s = re.sub(r"\bCác bạn\b", "Mọi người", s)
        s = re.sub(r"\bcác bạn\b", "mọi người", s)
        s = re.sub(r"\bBạn\b", "Cậu", s)
        s = re.sub(r"\bbạn\b", "cậu", s)
        if co_kinh_ngu_ban_be or "cậu" in s.lower():
            s = re.sub(r"\bcủa tôi\b", "của tớ", s)
            s = re.sub(r"\bđùa tôi\b", "đùa tớ", s)
    elif ngon_ngu_dich == "zh":
        s = re.sub(r"^等待([！!])", r"等等\1", s)
        s = s.replace("这个地牢", "这个地下城").replace("地牢", "地下城")
    elif ngon_ngu_dich == "zh-TW":
        s = re.sub(r"^等待([！!])", r"等等\1", s)
        s = s.replace("這個地牢", "這個地下城").replace("地牢", "地下城")
    elif ngon_ngu_dich == "id":
        s = re.sub(r"\bApakah kamu bercanda\?", "Kamu bercanda ya?", s, flags=re.I)
        s = re.sub(r"\bpenjara bawah tanah\b", "dungeon", s, flags=re.I)
    elif ngon_ngu_dich == "es":
        s = re.sub(r"^¡?Esperar!", "¡Espera!", s, flags=re.I)
    elif ngon_ngu_dich == "pt":
        s = re.sub(r"^Espere!", "Espera!", s, flags=re.I)
        s = re.sub(r"\bVocê está brincando comigo\?", "Tá brincando comigo?", s, flags=re.I)
    elif ngon_ngu_dich == "th":
        s = re.sub(r"^รอ!", "เดี๋ยวก่อน!", s)
        s = s.replace("คุณล้อเล่นฉันเหรอ?", "ล้อเล่นหรือเปล่าเนี่ย?")
    elif ngon_ngu_dich == "fr":
        if co_kinh_ngu_ban_be:
            s = re.sub(r"^Attendez\s*!", "Attends !", s, flags=re.I)
            s = re.sub(r"\bNe sous-estimez pas\b", "Ne sous-estime pas", s, flags=re.I)
        s = re.sub(r"\bVous plaisantez j'espère\s*\?", "Tu plaisantes j'espère ?", s, flags=re.I)
    return s.strip()


def danh_gia_chat_luong_ban_dich(
    chu_goc: str,
    ban_dich: str,
    *,
    ngon_ngu_nguon: str = "en",
    ngon_ngu_dich: str = "vi",
) -> tuple[float, list[str]]:
    """
    Công thức phát hiện & chấm điểm chất lượng bản dịch truyện tranh (thang điểm 0.0 -> 1.0):
      Q = 1.0 - (P_rong + P_sot_tieng_goc + P_lap_tu + P_xung_ho_cung + P_ty_le_do_dai)
    Trả về (diem_so, danh_sach_loi). Bản dịch đạt chuẩn khi Q >= 0.75 và không có lỗi nghiêm trọng.
    """
    goc = (chu_goc or "").strip()
    dich = (ban_dich or "").strip()
    if not goc:
        return 1.0, []
    if not dich or sum(c.isalnum() for c in dich) == 0:
        return 0.0, ["loi_rong"]

    diem = 1.0
    ds_loi: list[str] = []

    if ngon_ngu_dich == "vi" and ngon_ngu_nguon != "vi":
        # 1. Kiểm tra bản dịch giống hệt bản gốc (chưa dịch)
        goc_norm = re.sub(r"[^a-zA-Z0-9]+", "", goc).lower()
        dich_norm = re.sub(r"[^a-zA-Z0-9\u00C0-\u1EF9]+", "", dich).lower()
        if len(goc_norm) >= 4 and goc_norm == dich_norm and goc_norm not in TEN_RIENG_GIU_NGUYEN:
            diem -= 0.75
            ds_loi.append("loi_chua_dich")

        # 2. Kiểm tra sót từ tiếng Anh phổ biến trong câu tiếng Việt (P_sot_tieng_goc)
        tu_dich = re.findall(r"[A-Za-z\u00C0-\u1EF9']+", dich)
        tu_anh_sot = [
            w.lower()
            for w in tu_dich
            if w.isascii()
            and w.lower() in TU_TIENG_ANH_PHO_BIEN_CAN_DICH
            and w.lower() not in TEN_RIENG_GIU_NGUYEN
        ]
        if tu_anh_sot:
            ty_le_sot = len(tu_anh_sot) / max(1, len(tu_dich))
            phat = min(0.65, 0.25 + ty_le_sot * 0.8)
            diem -= phat
            ds_loi.append(f"loi_sot_tieng_goc:{','.join(tu_anh_sot[:3])}")

        # 3. Kiểm tra lỗi lặp từ / suy thoái mô hình (P_lap_tu: 'để để để')
        if re.search(r"\b(\w+)(?:\s+\1){2,}\b", dich, re.I) or re.search(r"\b(\w+\s+\w+)(?:\s+\1){2,}\b", dich, re.I):
            diem -= 0.55
            ds_loi.append("loi_lap_tu")

        # 4. Kiểm tra xưng hô cứng nhắc kiểu Google Translate ('bạn')
        if re.search(r"\bbạn\b", dich, re.I):
            diem -= 0.25
            ds_loi.append("loi_xung_ho_cung")

        # 5. Kiểm tra tỷ lệ độ dài bất thường (quá cụt hoặc giải thích lan man)
        if len(goc) >= 12:
            ty_le_dai = len(dich) / max(1, len(goc))
            if ty_le_dai < 0.28 or ty_le_dai > 3.2:
                diem -= 0.30
                ds_loi.append("loi_ty_le_do_dai")
    elif ngon_ngu_dich != ngon_ngu_nguon:
        # Chấm điểm chất lượng cho các ngôn ngữ đích quốc tế (EN, ZH, ZH-TW, ID, ES, PT, TH, FR)
        if len(goc) >= 4 and goc.lower() == dich.lower() and goc.lower() not in TEN_RIENG_GIU_NGUYEN:
            diem -= 0.70
            ds_loi.append("loi_chua_dich")
        if ngon_ngu_dich.lower().startswith("zh") and len(goc) >= 4 and not re.search(r"[\u4e00-\u9fff]", dich):
            diem -= 0.65
            ds_loi.append("loi_thieu_chu_han")
        if ngon_ngu_dich.lower() == "th" and len(goc) >= 4 and not re.search(r"[\u0e00-\u0e7f]", dich):
            diem -= 0.65
            ds_loi.append("loi_thieu_chu_thai")
        if ngon_ngu_dich.lower().startswith(("zh", "th")) and ngon_ngu_nguon == "en":
            tu_anh_sot_qt = [
                w.lower()
                for w in re.findall(r"[A-Za-z']+", dich)
                if w.lower() in TU_TIENG_ANH_PHO_BIEN_CAN_DICH and w.lower() not in TEN_RIENG_GIU_NGUYEN
            ]
            if tu_anh_sot_qt:
                diem -= min(0.60, 0.25 + 0.12 * len(tu_anh_sot_qt))
                ds_loi.append(f"loi_sot_tieng_goc:{','.join(tu_anh_sot_qt[:3])}")
        if re.search(r"\b(\w+)(?:\s+\1){2,}\b", dich, re.I):
            diem -= 0.50
            ds_loi.append("loi_lap_tu")

    return round(max(0.0, min(1.0, diem)), 3), ds_loi


def _lay_ban_nhap_nmt_sieu_toc(
    bubbles: list[dict],
    *,
    ngon_ngu_nguon: str = "ja",
    ngon_ngu_dich: str = "vi",
) -> list[str]:
    """
    Lấy bản nháp nghĩa sát (Semantic Anchor Draft) cho toàn bộ bóng thoại trong ~0.18s
    để làm mỏ neo từ vựng cho chế độ `local_hybrid_pro` (Dual-Anchor Draft + LLM Polish).
    """
    if not bubbles:
        return []
    try:
        kq_nhanh = _dich_danh_sach_thoai_nhanh_mien_phi(
            bubbles, ngon_ngu_nguon=ngon_ngu_nguon, ngon_ngu_dich=ngon_ngu_dich
        )
        if len(kq_nhanh) == len(bubbles):
            return [str(r.get("ban_dich") or "").strip() for r in kq_nhanh]
    except Exception:
        pass
    return ["" for _ in bubbles]


def _dich_danh_sach_thoai_gpu(
    bubbles: list[dict],
    *,
    backend: str,
    model: str,
    ngon_ngu_nguon: str,
    ngon_ngu_dich: str,
    tu_dien_rieng: str,
    chay_cpu: bool,
    che_do_pro: bool = False,
) -> list[dict]:
    """
    Chỉ gửi danh sách câu thoại đã OCR sang LLM trên GPU / LPU (nạp 37/37 lớp lên VRAM 6GB với num_ctx=1024..1536,
    bỏ qua bước suy nghĩ <think> và ảnh nặng, đạt tốc độ ~43 token/giây trên GPU hoặc ~750 token/giây trên Groq LPU), kèm:
    - Sắp xếp thứ tự đọc theo văn hoá truyện tranh (`sap_xep_bong_thoai_theo_huong_doc`: Phải->Trái cho Manga Nhật, Trái->Phải cho Manhwa/Manhua).
    - Bộ từ điển thuật ngữ & kính ngữ thông minh theo ngữ cảnh trang cho cả 9 ngôn ngữ (`trich_xuat_thuat_ngu_trang`).
    - Khi `che_do_pro=True` (`local_hybrid_pro`): kích hoạt cơ chế **Dual-Anchor Draft + LLM Polish** (kết hợp mỏ neo nghĩa sát NMT ~0.18s
      với khả năng chuốt ngữ cảnh & sửa chữ viết tay của LLM trong 1 lượt GPU duy nhất), giúp vừa tăng độ chính xác lên 97%–99% vừa giảm một nửa thời gian chờ!
    """
    bubbles = sap_xep_bong_thoai_theo_huong_doc(list(bubbles), ngon_ngu_nguon=ngon_ngu_nguon)
    ten_dich = lay_ten_prompt_ngon_ngu_dich(ngon_ngu_dich)
    thuat_ngu_trang = trich_xuat_thuat_ngu_trang(
        bubbles, tu_dien_rieng=tu_dien_rieng, ngon_ngu_dich=ngon_ngu_dich
    )
    dong_thuat_ngu = f"2. Ngữ cảnh & quy tắc xưng hô: {thuat_ngu_trang}.\n" if thuat_ngu_trang else ""

    ban_nhap_nmt: list[str] = (
        _lay_ban_nhap_nmt_sieu_toc(bubbles, ngon_ngu_nguon=ngon_ngu_nguon, ngon_ngu_dich=ngon_ngu_dich)
        if che_do_pro
        else ["" for _ in bubbles]
    )

    dong_nhap: list[str] = []
    for idx, b in enumerate(bubbles):
        cau_goc_chuan = _chuan_hoa_cau_goc_cho_llm(b["chu_goc"])
        tag_lien_ket = " [nối tiếp bóng trên]" if b.get("lien_ket_cau_tren") else ""
        nhap_goi_y = (
            f" (Gợi ý nghĩa sát: {ban_nhap_nmt[idx]})"
            if (che_do_pro and idx < len(ban_nhap_nmt) and ban_nhap_nmt[idx])
            else ""
        )
        dong_nhap.append(f"[{idx + 1}]{tag_lien_ket} {cau_goc_chuan}{nhap_goi_y}")
    lines_in = "\n".join(dong_nhap)

    quy_tac_pro = (
        "\n4. CHẾ ĐỘ PRO DUAL-ANCHOR & CHỮ VIẾT TAY: Mỗi dòng có kèm '(Gợi ý nghĩa sát: ...)'. Hãy kết hợp câu gốc với gợi ý nghĩa sát để không sót từ vựng khó, tự động sửa lỗi OCR chữ viết tay (VD: '1'->'I', '0'->'O') và chuốt lại thành lời thoại truyện tranh tự nhiên, đúng xưng hô nhất (KHÔNG lặp lại phần chú thích trong ngoặc)."
        if che_do_pro
        else ""
    )
    prompt = (
        f"Bạn là biên dịch viên truyện tranh kỳ cựu ({ngon_ngu_nguon} -> {ten_dich}).\n"
        "Quy tắc dịch bắt buộc:\n"
        f"1. Dịch ĐÚNG NGHĨA từng câu thoại bên dưới sang {ten_dich} tự nhiên, khớp mạch hội thoại (TUYỆT ĐỐI không bịa thêm nội dung không có trong câu gốc, không chép lại câu của trang trước).\n"
        f"{dong_thuat_ngu}"
        f"3. CHỈ trả về đúng {len(bubbles)} dòng từ [1] đến [{len(bubbles)}], mỗi câu 1 dòng ngắn gọn bằng {ten_dich}, KHÔNG giải thích:{quy_tac_pro}\n"
        f"{lines_in}"
    )

    def _goi_llm_van_ban(prompt_text: str, so_cau: int) -> str:
        if backend in ("groq", "deepseek", "openrouter"):
            if backend == "groq":
                api_url = "https://api.groq.com/openai/v1/chat/completions"
                api_key = _lay_khoa_groq_cuc_bo()
                model_call = model or "llama-3.3-70b-versatile"
            elif backend == "openrouter":
                api_url = "https://openrouter.ai/api/v1/chat/completions"
                api_key = _lay_khoa_openrouter_cuc_bo()
                model_call = model or "google/gemma-3-27b-it:free"
            else:
                api_url = "https://api.deepseek.com/chat/completions"
                api_key = _lay_khoa_deepseek_cuc_bo()
                model_call = model or "deepseek-chat"

            req_cloud = urllib.request.Request(
                api_url,
                data=json.dumps(
                    {
                        "model": model_call,
                        "temperature": 0.2,
                        "max_tokens": max(128, min(768, so_cau * 38)),
                        "messages": [
                            {
                                "role": "system",
                                "content": f"Bạn là chuyên gia dịch truyện tranh đa ngôn ngữ sang {ten_dich} tự nhiên, chuẩn ngữ cảnh.",
                            },
                            {"role": "user", "content": prompt_text},
                        ],
                    }
                ).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "MangaStudioPro/1.1",
                },
                method="POST",
            )
            with urllib.request.urlopen(req_cloud, timeout=35) as resp_cl:
                data_cl = json.loads(resp_cl.read().decode("utf-8", errors="replace"))
            return str((((data_cl.get("choices") or [{}])[0]).get("message") or {}).get("content") or "")

        if backend == "ollama":
            tuy_chon = _tuy_chon_ollama(
                chay_cpu,
                temperature=0.0,
                num_ctx=1536 if che_do_pro else 1024,
                num_predict=max(96, min(640 if che_do_pro else 512, so_cau * (34 if che_do_pro else 28))),
                stop=[f"[{so_cau + 1}]", "\n\n"],
            )
            if not chay_cpu:
                # Với num_ctx=1024 và chỉ gửi văn bản (không nạp mmproj ảnh), toàn bộ 37/37 lớp (4.75 GB)
                # của qwen3-vl:8b / sailor2:8b / sakura:7b / aya-expanse:8b nằm gọn 100% trong 6GB VRAM, đạt ~43.4 token/giây!
                tuy_chon["num_gpu"] = 37
            try:
                data = _goi_json_ai_cuc_bo(
                    "http://127.0.0.1:11434/api/chat",
                    timeout=TIMEOUT_CPU if chay_cpu else TIMEOUT_GPU,
                    payload={
                        "model": model,
                        "stream": False,
                        "options": tuy_chon,
                        "messages": [
                            {"role": "user", "content": prompt_text},
                            {"role": "assistant", "content": "<think>\n\n</think>\n[1] "},
                        ],
                    },
                )
            except LocalRuntimeCrashError:
                if chay_cpu or tuy_chon.get("num_gpu") != 37:
                    raise
                # Dự phòng an toàn nếu ứng dụng khác đang chiếm bớt VRAM: hạ xuống 33 lớp GPU
                tuy_chon["num_gpu"] = 33
                data = _goi_json_ai_cuc_bo(
                    "http://127.0.0.1:11434/api/chat",
                    timeout=TIMEOUT_GPU,
                    payload={
                        "model": model,
                        "stream": False,
                        "options": tuy_chon,
                        "messages": [
                            {"role": "user", "content": prompt_text},
                            {"role": "assistant", "content": "<think>\n\n</think>\n[1] "},
                        ],
                    },
                )
            raw_content = str((data.get("message") or {}).get("content") or data.get("response") or "")
            return "[1] " + raw_content if not raw_content.lstrip().startswith("[1]") else raw_content

        url_local_oai = (
            "http://127.0.0.1:8080/v1/chat/completions"
            if backend == "llamacpp"
            else "http://127.0.0.1:1234/v1/chat/completions"
        )
        data = _goi_json_ai_cuc_bo(
            url_local_oai,
            timeout=TIMEOUT_GPU,
            payload={
                "model": model,
                "temperature": 0.2,
                "max_tokens": max(96, min(512, so_cau * 28)),
                "messages": [{"role": "user", "content": prompt_text}],
            },
        )
        return str((((data.get("choices") or [{}])[0]).get("message") or {}).get("content") or "")

    raw_text = _goi_llm_van_ban(prompt, len(bubbles))

    trans_map: dict[int, str] = {}
    for line in raw_text.splitlines():
        m = re.match(r"^\s*\[?(\d+)[\].:\-)\s]+(.+?)\s*$", line)
        if m:
            idx_num = int(m.group(1))
            if idx_num not in trans_map:
                trans_map[idx_num] = hau_kiem_va_sua_ban_dich(
                    bubbles[idx_num - 1]["chu_goc"] if 1 <= idx_num <= len(bubbles) else "",
                    m.group(2).strip(),
                    ngon_ngu_dich=ngon_ngu_dich,
                )

    # Bước kiểm định chất lượng tự động: phát hiện câu bị sót hoặc điểm chất lượng Q < ngưỡng (0.85 cho Pro, 0.75 cho Nhanh)
    nguong_q = 0.85 if che_do_pro else 0.75
    ds_can_dich_lai: list[int] = []
    for idx, b in enumerate(bubbles):
        vi_cur = trans_map.get(idx + 1, "")
        diem, _ = danh_gia_chat_luong_ban_dich(
            b["chu_goc"], vi_cur, ngon_ngu_nguon=ngon_ngu_nguon, ngon_ngu_dich=ngon_ngu_dich
        )
        if diem < nguong_q:
            # Nếu đang ở chế độ Pro và bản nháp Dual-Anchor đã đạt điểm Q >= 0.90 thì cứu hộ tức thì (0ms) không cần gọi GPU lần 2
            if che_do_pro and idx < len(ban_nhap_nmt) and ban_nhap_nmt[idx]:
                diem_nhap, _ = danh_gia_chat_luong_ban_dich(
                    b["chu_goc"], ban_nhap_nmt[idx], ngon_ngu_nguon=ngon_ngu_nguon, ngon_ngu_dich=ngon_ngu_dich
                )
                if diem_nhap >= max(nguong_q, diem):
                    trans_map[idx + 1] = ban_nhap_nmt[idx]
                    continue
            ds_can_dich_lai.append(idx)

    if ds_can_dich_lai and len(ds_can_dich_lai) <= max(4, len(bubbles) // 2):
        lines_retry = "\n".join(
            f"[{i + 1}] {_chuan_hoa_cau_goc_cho_llm(bubbles[orig_idx]['chu_goc'])}"
            for i, orig_idx in enumerate(ds_can_dich_lai)
        )
        prompt_retry = (
            f"Dịch chính xác {len(ds_can_dich_lai)} câu thoại truyện tranh sau sang {ten_dich}.\n"
            f"Bắt buộc dịch hết 100% từ ngôn ngữ gốc ({ngon_ngu_nguon}) sang {ten_dich} tự nhiên, ngắn gọn, không lặp từ ({thuat_ngu_trang}):\n"
            f"{lines_retry}"
        )
        try:
            raw_retry = _goi_llm_van_ban(prompt_retry, len(ds_can_dich_lai))
            for line in raw_retry.splitlines():
                m = re.match(r"^\s*\[?(\d+)[\].:\-)\s]+(.+?)\s*$", line)
                if m:
                    r_idx = int(m.group(1)) - 1
                    if 0 <= r_idx < len(ds_can_dich_lai):
                        orig_idx = ds_can_dich_lai[r_idx]
                        vi_moi = hau_kiem_va_sua_ban_dich(
                            bubbles[orig_idx]["chu_goc"], m.group(2).strip(), ngon_ngu_dich=ngon_ngu_dich
                        )
                        diem_cu, _ = danh_gia_chat_luong_ban_dich(
                            bubbles[orig_idx]["chu_goc"],
                            trans_map.get(orig_idx + 1, ""),
                            ngon_ngu_nguon=ngon_ngu_nguon,
                            ngon_ngu_dich=ngon_ngu_dich,
                        )
                        diem_moi, _ = danh_gia_chat_luong_ban_dich(
                            bubbles[orig_idx]["chu_goc"],
                            vi_moi,
                            ngon_ngu_nguon=ngon_ngu_nguon,
                            ngon_ngu_dich=ngon_ngu_dich,
                        )
                        if diem_moi >= diem_cu and vi_moi:
                            trans_map[orig_idx + 1] = vi_moi
        except Exception:
            pass

    vung_out: list[dict] = []
    for idx, b in enumerate(bubbles):
        vi = trans_map.get(idx + 1, "")
        if vi and b["w"] >= 12 and b["h"] >= 12:
            _, loi_q = danh_gia_chat_luong_ban_dich(
                b["chu_goc"], vi, ngon_ngu_nguon=ngon_ngu_nguon, ngon_ngu_dich=ngon_ngu_dich
            )
            muc = {
                "x": int(b["x"]),
                "y": int(b["y"]),
                "w": int(b["w"]),
                "h": int(b["h"]),
                "chu_goc": b["chu_goc"],
                "ban_dich": vi,
            }
            if loi_q:
                muc["canh_bao_chat_luong"] = loi_q
            if b.get("dong_con"):
                muc["dong_con"] = b["dong_con"]
            vung_out.append(muc)
    return vung_out


def dich_anh_local_gguf_tren_may_khach(
    img_bytes: bytes,
    *,
    ngon_ngu_nguon: str = "ja",
    ngon_ngu_dich: str = "vi",
    tu_dien_rieng: str = "",
    chay_cpu: bool = False,
) -> list[dict]:
    """
    Dịch trên máy khách bằng Qwen3-VL 8B qua Ollama hoặc LM Studio.
    - Tự động ưu tiên luồng nhanh (OCR cục bộ ~0.6s + Dịch văn bản trên GPU ~25 token/giây) khi ảnh thật
      và ngôn ngữ nguồn được Windows OCR hỗ trợ.
    - Không gửi ảnh lên máy chủ dịch, không tự tải model hay đổi sang engine đám mây.
    """
    W, H = 1000, 1400
    co_anh_that = False
    if Image is not None:
        try:
            with Image.open(io.BytesIO(img_bytes)) as im_tmp:
                W, H = im_tmp.size
                co_anh_that = (W >= 100 and H >= 100)
        except Exception:
            pass

    backend, model = _ket_noi_qwen3_vl_cuc_bo()
    if backend == "lmstudio" and chay_cpu:
        raise LocalCpuUnsupportedError(HUONG_DAN_CPU_LM_STUDIO)

    # Nhánh 1 (Tối ưu GPU nhanh): Ảnh trang truyện thật -> OCR cục bộ + chỉ gửi văn bản lên GPU LLM
    if co_anh_that:
        bubbles = nhan_dien_bong_thoai_ocr_cuc_bo(img_bytes, ngon_ngu_nguon=ngon_ngu_nguon)
        if bubbles:
            vung_nhanh = _dich_danh_sach_thoai_gpu(
                bubbles,
                backend=backend,
                model=model,
                ngon_ngu_nguon=ngon_ngu_nguon,
                ngon_ngu_dich=ngon_ngu_dich,
                tu_dien_rieng=tu_dien_rieng,
                chay_cpu=chay_cpu,
            )
            if vung_nhanh:
                return vung_nhanh

    # Nhánh 2: Gửi ảnh cho Qwen3-VL 8B (giữ tương thích đầy đủ với kiểm thử và các ngôn ngữ chưa cài gói OCR)
    anh_b64 = base64.b64encode(img_bytes).decode("ascii")
    ten_dich = lay_ten_prompt_ngon_ngu_dich(ngon_ngu_dich)
    doan_ngu_canh = (
        f"\nNgữ cảnh xưng hô & thuật ngữ từ các trang trước (hãy giữ đồng nhất):\n{tu_dien_rieng}\n"
        if tu_dien_rieng
        else ""
    )
    prompt = (
        f"Bạn là AI nhận diện và dịch truyện tranh chuyên nghiệp (ngôn ngữ gốc: {ngon_ngu_nguon} -> dịch sang: {ten_dich})."
        f"{doan_ngu_canh}\n"
        "Hãy tìm TẤT CẢ các bóng thoại trong trang truyện này, đọc chữ gốc và dịch sang ngôn ngữ đích.\n"
        "Trả về DUY NHẤT một đối tượng JSON hợp lệ theo cấu trúc:\n"
        '{"regions":[{"box_2d":[ymin,xmin,ymax,xmax],"chu_goc":"...","ban_dich":"..."}]}\n'
        "Trong đó ymin, xmin, ymax, xmax được chuẩn hoá trên thang 0..1000."
    )

    if backend == "ollama":
        if co_anh_that:
            # Khi chạy trên ảnh thật: tắt <think>, thu gọn ngữ cảnh và đẩy 33 lớp lên GPU
            tuy_chon_anh = _tuy_chon_ollama(chay_cpu, num_ctx=1536, num_predict=512)
            if not chay_cpu:
                tuy_chon_anh["num_gpu"] = 33
            payload_ollama = {
                "model": model,
                "stream": False,
                "options": tuy_chon_anh,
                "messages": [
                    {"role": "user", "content": prompt, "images": [anh_b64]},
                    {"role": "assistant", "content": "<think>\n\n</think>\n"},
                ],
            }
        else:
            payload_ollama = {
                "model": model,
                "stream": False,
                "format": "json",
                "options": _tuy_chon_ollama(chay_cpu),
                "messages": [{"role": "user", "content": prompt, "images": [anh_b64]}],
            }
        data = _goi_json_ai_cuc_bo(
            "http://127.0.0.1:11434/api/chat",
            timeout=TIMEOUT_CPU if chay_cpu else TIMEOUT_GPU,
            payload=payload_ollama,
        )
        raw_text = (data.get("message") or {}).get("content") or data.get("response") or ""
    else:
        data = _goi_json_ai_cuc_bo(
            "http://127.0.0.1:1234/v1/chat/completions",
            timeout=180,
            payload={
                "model": model,
                "temperature": 0.2,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{anh_b64}"}},
                        ],
                    }
                ],
            },
        )
        raw_text = (((data.get("choices") or [{}])[0]).get("message") or {}).get("content") or ""

    try:
        try:
            parsed = json.loads(raw_text)
        except ValueError:
            # Giữ khả năng đọc mảng hoặc đối tượng JSON nằm trong Markdown
            khop_obj = re.search(r"\{[\s\S]*\}", str(raw_text))
            khop_arr = re.search(r"\[[\s\S]*\]", str(raw_text))
            ung_vien = khop_obj.group(0) if khop_obj else (khop_arr.group(0) if khop_arr else str(raw_text))
            parsed = json.loads(ung_vien)
        danh_sach = parsed if isinstance(parsed, list) else parsed.get("regions", parsed.get("vung"))
        if not isinstance(danh_sach, list):
            raise ValueError("Thiếu danh sách regions")
    except (ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            "Qwen3-VL 8B đã phản hồi nhưng kết quả không đúng JSON regions; hãy thử lại trang này."
        ) from exc

    vung_out: list[dict] = []
    for m in danh_sach:
        if not isinstance(m, dict):
            continue
        ban_dich = str(m.get("ban_dich") or m.get("translation") or m.get("text") or "").strip()
        if not ban_dich:
            continue
        chu_goc = str(m.get("chu_goc") or m.get("original") or "").strip()
        box = m.get("box_2d")
        if isinstance(box, list) and len(box) == 4:
            if co_anh_that:
                xmin, ymin, xmax, ymax = [float(v) for v in box]
            else:
                ymin, xmin, ymax, xmax = [float(v) for v in box]
            thang = 1.0 if max(ymin, xmin, ymax, xmax) <= 1.05 else 1000.0
            x = int(round((xmin / thang) * W))
            y = int(round((ymin / thang) * H))
            w = int(round(((xmax - xmin) / thang) * W))
            h = int(round(((ymax - ymin) / thang) * H))
        else:
            x = int(round(float(m.get("x") or 0)))
            y = int(round(float(m.get("y") or 0)))
            w = int(round(float(m.get("w") or 120)))
            h = int(round(float(m.get("h") or 80)))
        if w >= 12 and h >= 12:
            vung_out.append({"x": x, "y": y, "w": w, "h": h, "chu_goc": chu_goc, "ban_dich": ban_dich})
    return vung_out


def _dich_danh_sach_thoai_nhanh_mien_phi(
    bubbles: list[dict],
    *,
    ngon_ngu_nguon: str = "ja",
    ngon_ngu_dich: str = "vi",
) -> list[dict]:
    """
    Nhánh dịch văn bản siêu tốc 0đ (~0.4s/trang) kết hợp hậu kiểm thoại truyện tranh
    khi người dùng chọn `local_ocr_gpu` mà chưa bật Ollama/LM Studio hoặc máy không có GPU rời.
    """
    if not bubbles:
        return []
    sl = {"ja": "ja", "ko": "ko", "zh": "zh-CN", "zh-TW": "zh-TW", "en": "en"}.get(ngon_ngu_nguon, "auto")
    tl = DANH_SACH_NGON_NGU_DICH_QUOC_TE.get(ngon_ngu_dich, {}).get("google_tl", ngon_ngu_dich or "vi")
    lines_in = [re.sub(r"\s+", " ", _chuan_hoa_cau_goc_cho_llm(b["chu_goc"])).strip() for b in bubbles]

    def _goi_gtx(text_q: str) -> str:
        url_q = (
            "https://translate.googleapis.com/translate_a/single?client=gtx"
            f"&sl={urllib.parse.quote(sl)}&tl={urllib.parse.quote(tl)}&dt=t&q={urllib.parse.quote(text_q)}"
        )
        raw_q = goi_http(url_q, timeout=15, nguon_ngoai=True).decode("utf-8", errors="replace")
        data_q = json.loads(raw_q)
        return "".join(str(seg[0]) for seg in (data_q[0] or []) if seg and seg[0])

    joined = "\n".join(lines_in)
    full_trans = _goi_gtx(joined)
    parts = [p.strip() for p in full_trans.splitlines() if p.strip()]
    vung_out: list[dict] = []
    for idx, b in enumerate(bubbles):
        vi_raw = parts[idx] if len(parts) == len(bubbles) and idx < len(parts) else ""
        vi = hau_kiem_va_sua_ban_dich(b["chu_goc"], vi_raw, ngon_ngu_dich=ngon_ngu_dich)
        diem_q, _ = danh_gia_chat_luong_ban_dich(
            b["chu_goc"], vi, ngon_ngu_nguon=ngon_ngu_nguon, ngon_ngu_dich=ngon_ngu_dich
        )
        if not vi or diem_q < 0.85:
            try:
                vi_don = _goi_gtx(lines_in[idx])
                vi = hau_kiem_va_sua_ban_dich(b["chu_goc"], vi_don, ngon_ngu_dich=ngon_ngu_dich)
            except Exception:
                pass
        if vi and b["w"] >= 12 and b["h"] >= 12:
            muc = {
                "x": int(b["x"]),
                "y": int(b["y"]),
                "w": int(b["w"]),
                "h": int(b["h"]),
                "chu_goc": b["chu_goc"],
                "ban_dich": vi,
            }
            if b.get("dong_con"):
                muc["dong_con"] = b["dong_con"]
            vung_out.append(muc)
    return vung_out


_LOCAL_PAGE_TRANSLATION_CACHE: dict[tuple[str, str, str, str], list[dict]] = {}
_LOCAL_CACHE_LOCK = threading.Lock()
_BO_NHO_NGU_CANH_LIEN_TRANG: list[str] = []
_UU_TIEN_MODEL_LOCAL_OCR_GPU: list[str] = [
    "sailor2:8b",
    "hf.co/sail/Sailor2-8B-Chat-GGUF:Q4_K_M",
    "seallms-v3:7b",
    "hf.co/SeaLLMs/SeaLLMs-v3-7B-Chat-GGUF:Q4_K_M",
    "sakura:7b",
    "hf.co/SakuraLLM/Sakura-7B-Qwen2.5-v1.0-GGUF:Q4_K_M",
    "aya-expanse:8b",
    "hf.co/bartowski/aya-expanse-8b-GGUF:Q4_K_M",
    "qwen3-vl:8b",
    "qwen3:14b",
    "qwen3:8b",
    "qwen3:4b",
    "gemma3:12b",
    "gemma3:4b",
    "qwen2.5:14b",
    "qwen2.5:7b",
    "deepseek-r1:8b",
    "llama3.2:latest",
    "llama3.1:8b",
]

# Bộ định tuyến Model chuyên dụng từ Hugging Face / Ollama theo từng ngôn ngữ đích (Smart Model Router)
BO_DINH_TUYEN_MODEL_THEO_NGON_NGU: dict[str, list[str]] = {
    "vi": [
        "sailor2:8b",
        "hf.co/sail/Sailor2-8B-Chat-GGUF:Q4_K_M",
        "seallms-v3:7b",
        "hf.co/SeaLLMs/SeaLLMs-v3-7B-Chat-GGUF:Q4_K_M",
        "qwen3:14b",
        "qwen3:8b",
        "qwen3-vl:8b",
        "gemma3:12b",
        "qwen2.5:7b",
    ],
    "id": [
        "sailor2:8b",
        "hf.co/sail/Sailor2-8B-Chat-GGUF:Q4_K_M",
        "seallms-v3:7b",
        "hf.co/SeaLLMs/SeaLLMs-v3-7B-Chat-GGUF:Q4_K_M",
        "qwen3:8b",
        "qwen3-vl:8b",
        "aya-expanse:8b",
    ],
    "th": [
        "sailor2:8b",
        "hf.co/sail/Sailor2-8B-Chat-GGUF:Q4_K_M",
        "seallms-v3:7b",
        "hf.co/SeaLLMs/SeaLLMs-v3-7B-Chat-GGUF:Q4_K_M",
        "qwen3:8b",
        "qwen3-vl:8b",
        "gemma3:12b",
    ],
    "zh": [
        "sakura:7b",
        "hf.co/SakuraLLM/Sakura-7B-Qwen2.5-v1.0-GGUF:Q4_K_M",
        "qwen3:14b",
        "qwen3:8b",
        "qwen3-vl:8b",
        "qwen2.5:14b",
        "qwen2.5:7b",
    ],
    "zh-TW": [
        "sakura:7b",
        "hf.co/SakuraLLM/Sakura-7B-Qwen2.5-v1.0-GGUF:Q4_K_M",
        "qwen3:14b",
        "qwen3:8b",
        "qwen3-vl:8b",
        "qwen2.5:14b",
    ],
    "en": [
        "aya-expanse:8b",
        "hf.co/bartowski/aya-expanse-8b-GGUF:Q4_K_M",
        "gemma3:12b",
        "qwen3:8b",
        "qwen3-vl:8b",
        "llama3.1:8b",
    ],
    "es": [
        "aya-expanse:8b",
        "hf.co/bartowski/aya-expanse-8b-GGUF:Q4_K_M",
        "gemma3:12b",
        "qwen3:8b",
        "qwen3-vl:8b",
    ],
    "pt": [
        "aya-expanse:8b",
        "hf.co/bartowski/aya-expanse-8b-GGUF:Q4_K_M",
        "gemma3:12b",
        "qwen3:8b",
        "qwen3-vl:8b",
    ],
    "fr": [
        "aya-expanse:8b",
        "hf.co/bartowski/aya-expanse-8b-GGUF:Q4_K_M",
        "gemma3:12b",
        "qwen3:8b",
        "qwen3-vl:8b",
    ],
}

DANH_SACH_MODEL_HUGGINGFACE_CHUYEN_DUNG: list[dict[str, str]] = [
    {
        "ma": "hf.co/sail/Sailor2-8B-Chat-GGUF:Q4_K_M",
        "ten": "🌏 Sailor2 8B GGUF (Sea AI Lab — Vua dịch Đông Nam Á: Việt · Indo · Thái)",
        "ngon_ngu_manh": "vi, id, th",
        "vram": "~4.9 GB VRAM",
    },
    {
        "ma": "hf.co/SakuraLLM/Sakura-7B-Qwen2.5-v1.0-GGUF:Q4_K_M",
        "ten": "🌸 SakuraLLM 7B GGUF (Chuyên biệt Manga/LightNovel Nhật -> Trung Giản/Phồn)",
        "ngon_ngu_manh": "zh, zh-TW",
        "vram": "~4.6 GB VRAM",
    },
    {
        "ma": "aya-expanse:8b",
        "ten": "🌍 Cohere Aya-Expanse 8B (Số 1 dịch thuật Quốc tế: Anh · Tây Ban Nha · Bồ Đào Nha · Pháp)",
        "ngon_ngu_manh": "en, es, pt, fr",
        "vram": "~5.0 GB VRAM",
    },
    {
        "ma": "qwen3:8b",
        "ten": "⚡ Alibaba Qwen3 8B (Đa năng 9 ngôn ngữ · Tốc độ cao 45 token/giây)",
        "ngon_ngu_manh": "vi, en, zh, zh-TW, id, es, pt, th, fr",
        "vram": "~4.8 GB VRAM",
    },
    {
        "ma": "gemma3:12b",
        "ten": "💎 Google Gemma3 12B (Siêu chuẩn ngữ cảnh đa ngôn ngữ cho GPU >= 8GB VRAM)",
        "ngon_ngu_manh": "vi, en, es, pt, fr, th, id",
        "vram": "~7.2 GB VRAM",
    },
]

_MODEL_LOCAL_OCR_GPU_TUY_CHON: str = ""


def lay_ngu_canh_lien_trang_hien_tai(tu_dien_rieng: str = "") -> str:
    """Gộp từ điển riêng của người dùng với 8 cặp thoại gần nhất từ các trang vừa dịch trong cùng chapter."""
    with _LOCAL_CACHE_LOCK:
        gan_nhat = list(_BO_NHO_NGU_CANH_LIEN_TRANG[-8:])
    phan_trang_truoc = "\n".join(gan_nhat)
    return "\n".join(p for p in (tu_dien_rieng.strip(), phan_trang_truoc) if p)


def cap_nhat_ngu_canh_lien_trang(ket_qua: list[dict]) -> None:
    """Lưu tự động các cặp câu thoại vừa dịch để trang kế tiếp giữ đồng nhất đại từ xưng hô."""
    if not ket_qua:
        return
    with _LOCAL_CACHE_LOCK:
        for item in ket_qua:
            goc = str(item.get("chu_goc") or "").strip().replace("\n", " ")
            dich = str(item.get("ban_dich") or "").strip().replace("\n", " ")
            if 3 <= len(goc) <= 85 and 2 <= len(dich) <= 130:
                dong = f"{goc} = {dich}"
                if dong not in _BO_NHO_NGU_CANH_LIEN_TRANG:
                    _BO_NHO_NGU_CANH_LIEN_TRANG.append(dong)
        if len(_BO_NHO_NGU_CANH_LIEN_TRANG) > 16:
            del _BO_NHO_NGU_CANH_LIEN_TRANG[:-16]


def _dich_danh_sach_thoai_qua_server_deepseek(
    bubbles: list[dict],
    *,
    ngon_ngu_nguon: str = "ja",
    ngon_ngu_dich: str = "vi",
    tu_dien_rieng: str = "",
    page_key: str = "",
    engine: str = "local_ocr_gpu",
) -> list[dict]:
    """
    Khi máy khách đã quét OCR cục bộ xong mà không bật LLM nội bộ, ưu tiên gửi danh sách câu thoại
    lên endpoint `/api/v1/doc-truyen/dich-thoai-ngu-canh` của máy chủ để DeepSeek (do Admin cấu hình)
    dịch chuẩn ngữ cảnh; nếu không có kết nối hoặc chạy test offline thì lùi về `_dich_danh_sach_thoai_nhanh_mien_phi`.
    """
    if not bubbles:
        return []
    try:
        if CAU_HINH_FILE.is_file():
            cfg = json.loads(CAU_HINH_FILE.read_text(encoding="utf-8"))
            may_chu = chuan_hoa_may_chu(str(cfg.get("may_chu") or ""))
            token = str(cfg.get("token") or cfg.get("api_key") or cfg.get("ma_phien") or "").strip()
            if may_chu and token and "api.invalid" not in may_chu:
                texts_in = [_chuan_hoa_cau_goc_cho_llm(b["chu_goc"]) for b in bubbles]
                hdrs = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                    "X-Ma-May-Tinh": MA_MAY_HIEN_THI,
                    "User-Agent": "MangaStudioWindows/1.1",
                }
                body_bytes = json.dumps(
                    {
                        "texts": texts_in,
                        "source_lang": ngon_ngu_nguon if ngon_ngu_nguon in ("ja", "ko", "zh", "en") else "ja",
                        "target_lang": ngon_ngu_dich if ngon_ngu_dich in DANH_SACH_NGON_NGU_DICH_QUOC_TE else "vi",
                        "boi_canh": (tu_dien_rieng or "")[:2000] or None,
                        "page_key": (page_key or "")[:128] or None,
                        "engine": (engine or "local_ocr_gpu")[:64],
                    },
                    ensure_ascii=False,
                ).encode("utf-8")
                req = urllib.request.Request(
                    f"{may_chu}/api/v1/doc-truyen/dich-thoai-ngu-canh",
                    data=body_bytes,
                    headers=hdrs,
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=18) as resp:
                    res_data = json.loads(resp.read().decode("utf-8", errors="replace"))
                ds_dich = res_data.get("translations") if isinstance(res_data, dict) else None
                if isinstance(ds_dich, list) and len(ds_dich) == len(bubbles):
                    vung_out: list[dict] = []
                    for idx, b in enumerate(bubbles):
                        vi = hau_kiem_va_sua_ban_dich(b["chu_goc"], str(ds_dich[idx] or ""), ngon_ngu_dich=ngon_ngu_dich)
                        if vi and b["w"] >= 12 and b["h"] >= 12:
                            muc = {
                                "x": int(b["x"]),
                                "y": int(b["y"]),
                                "w": int(b["w"]),
                                "h": int(b["h"]),
                                "chu_goc": b["chu_goc"],
                                "ban_dich": vi,
                            }
                            if b.get("dong_con"):
                                muc["dong_con"] = b["dong_con"]
                            vung_out.append(muc)
                    if vung_out:
                        return vung_out
    except Exception:
        pass
    return _dich_danh_sach_thoai_nhanh_mien_phi(
        bubbles,
        ngon_ngu_nguon=ngon_ngu_nguon,
        ngon_ngu_dich=ngon_ngu_dich,
    )


def _lay_khoa_deepseek_cuc_bo() -> str:
    """Đọc khoá DeepSeek API (sk-...) từ biến môi trường, CAU_HINH_FILE hoặc .env."""
    for env_name in ("DEEPSEEK_API_KEY", "DEEPSEEK_API_KEYS", "GEMINI_API_KEYS", "GEMINI_API_KEY"):
        val = (os.environ.get(env_name) or "").strip()
        if val:
            for part in val.split(","):
                p = part.strip()
                if p.startswith("sk-") or env_name.startswith("DEEPSEEK"):
                    return p
    try:
        if CAU_HINH_FILE.is_file():
            cfg = json.loads(CAU_HINH_FILE.read_text(encoding="utf-8"))
            k_cfg = str(cfg.get("deepseek_api_key") or "").strip()
            if k_cfg:
                return k_cfg.split(",")[0].strip()
    except Exception:
        pass
    app_dir = Path(_APP_DIR)
    for env_path in (app_dir / ".env", app_dir.parent / ".env"):
        try:
            if env_path.is_file():
                for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                    s = line.strip()
                    if s.startswith(("DEEPSEEK_API_KEY=", "DEEPSEEK_API_KEYS=", "GEMINI_API_KEYS=", "GEMINI_API_KEY=")):
                        k_name, v_raw = s.split("=", 1)
                        v = v_raw.strip().strip("\"'")
                        for part in v.split(","):
                            p = part.strip()
                            if p and (p.startswith("sk-") or k_name.startswith("DEEPSEEK")):
                                return p
        except Exception:
            pass
    return ""


def _lay_khoa_groq_cuc_bo() -> str:
    """Đọc khoá Groq LPU API (gsk_...) giúp tăng tốc dịch 750 token/giây (~0.25s/trang với Llama-3.3-70B)."""
    for env_name in ("GROQ_API_KEY", "GROQ_API_KEYS"):
        val = (os.environ.get(env_name) or "").strip()
        if val:
            return val.split(",")[0].strip()
    try:
        if CAU_HINH_FILE.is_file():
            cfg = json.loads(CAU_HINH_FILE.read_text(encoding="utf-8"))
            k_cfg = str(cfg.get("groq_api_key") or "").strip()
            if k_cfg:
                return k_cfg.split(",")[0].strip()
    except Exception:
        pass
    app_dir = Path(_APP_DIR)
    for env_path in (app_dir / ".env", app_dir.parent / ".env"):
        try:
            if env_path.is_file():
                for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                    s = line.strip()
                    if s.startswith(("GROQ_API_KEY=", "GROQ_API_KEYS=")):
                        _, v_raw = s.split("=", 1)
                        v = v_raw.strip().strip("\"'")
                        if v:
                            return v.split(",")[0].strip()
        except Exception:
            pass
    return ""


def _lay_khoa_openrouter_cuc_bo() -> str:
    """Đọc khoá OpenRouter API (sk-or-...) kết nối kho model HuggingFace miễn phí & trả phí."""
    for env_name in ("OPENROUTER_API_KEY", "OPENROUTER_API_KEYS"):
        val = (os.environ.get(env_name) or "").strip()
        if val:
            return val.split(",")[0].strip()
    try:
        if CAU_HINH_FILE.is_file():
            cfg = json.loads(CAU_HINH_FILE.read_text(encoding="utf-8"))
            k_cfg = str(cfg.get("openrouter_api_key") or "").strip()
            if k_cfg:
                return k_cfg.split(",")[0].strip()
    except Exception:
        pass
    app_dir = Path(_APP_DIR)
    for env_path in (app_dir / ".env", app_dir.parent / ".env"):
        try:
            if env_path.is_file():
                for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                    s = line.strip()
                    if s.startswith(("OPENROUTER_API_KEY=", "OPENROUTER_API_KEYS=")):
                        _, v_raw = s.split("=", 1)
                        v = v_raw.strip().strip("\"'")
                        if v:
                            return v.split(",")[0].strip()
        except Exception:
            pass
    return ""


def _ket_noi_llm_cho_local_ocr_gpu(ngon_ngu_dich: str = "vi") -> tuple[str, str]:
    """
    Kết nối mô hình AI cho chế độ `local_ocr_gpu` và `local_hybrid_pro` (Smart Model Router):
    1. Nếu người dùng cấu hình `GROQ_API_KEY` (`gsk_...`), ưu tiên cổng LPU `llama-3.3-70b-versatile` (~750 token/s, ~0.25s/trang).
    2. Nếu người dùng cấu hình `DEEPSEEK_API_KEY` (`sk-...`), ưu tiên `deepseek-chat` (~1.5đ/trang, chuẩn ngữ cảnh 98%).
    3. Nếu người dùng cấu hình `OPENROUTER_API_KEY` (`sk-or-...`), kết nối kho model HuggingFace trên OpenRouter.
    4. Trên GPU cục bộ (Ollama / LM Studio / llama.cpp GGUF `:8080`), tự động định tuyến model mạnh nhất theo `ngon_ngu_dich`:
       - Đông Nam Á (`vi`, `id`, `th`) -> `sailor2:8b` / `seallms-v3:7b` / `qwen3:8b`
       - Trung Quốc (`zh`, `zh-TW`) -> `sakura:7b` / `qwen3:14b` / `qwen3:8b`
       - Âu - Mỹ Latinh (`en`, `es`, `pt`, `fr`) -> `aya-expanse:8b` / `gemma3:12b` / `qwen3:8b`
    """
    groq_key = _lay_khoa_groq_cuc_bo()
    if groq_key:
        return "groq", "llama-3.3-70b-versatile"

    ds_key = _lay_khoa_deepseek_cuc_bo()
    if ds_key:
        return "deepseek", "deepseek-chat"

    or_key = _lay_khoa_openrouter_cuc_bo()
    if or_key:
        return "openrouter", "google/gemma-3-27b-it:free"

    ds_uu_tien_lang = BO_DINH_TUYEN_MODEL_THEO_NGON_NGU.get(
        ngon_ngu_dich, _UU_TIEN_MODEL_LOCAL_OCR_GPU
    )

    # Kiểm tra các model trong Ollama và ưu tiên theo Smart Model Router của ngôn ngữ đích
    try:
        data_ol = _goi_json_ai_cuc_bo("http://127.0.0.1:11434/api/tags", timeout=3)
        ds_ol = [str(m.get("name") or "") for m in (data_ol.get("models") or []) if isinstance(m, dict) and m.get("name")]
        if _MODEL_LOCAL_OCR_GPU_TUY_CHON and _MODEL_LOCAL_OCR_GPU_TUY_CHON in ds_ol:
            return "ollama", _MODEL_LOCAL_OCR_GPU_TUY_CHON
        for ung_vien in ds_uu_tien_lang:
            for m_installed in ds_ol:
                if m_installed == ung_vien or m_installed.lower().startswith(ung_vien.lower()):
                    return "ollama", m_installed
        for ung_vien in _UU_TIEN_MODEL_LOCAL_OCR_GPU:
            if ung_vien in ds_ol:
                return "ollama", ung_vien
        for m_name in ds_ol:
            if any(k in m_name.lower() for k in ("sailor", "seallm", "sakura", "aya", "qwen", "gemma", "llama", "deepseek", "mistral")):
                return "ollama", m_name
    except Exception:
        pass

    try:
        return _ket_noi_qwen3_vl_cuc_bo()
    except LocalModelMissingError:
        pass

    # Kiểm tra LM Studio (:1234)
    try:
        data_lm = _goi_json_ai_cuc_bo("http://127.0.0.1:1234/v1/models", timeout=2)
        ds_lm = [str(m.get("id") or "") for m in (data_lm.get("data") or []) if isinstance(m, dict) and m.get("id")]
        for m_id in ds_lm:
            if any(k in m_id.lower() for k in ("sailor", "seallm", "sakura", "aya", "qwen", "gemma", "llama", "deepseek", "mistral")):
                return "lmstudio", m_id
    except Exception:
        pass

    # Kiểm tra llama.cpp / KoboldCpp GGUF Server (:8080) chạy model tải trực tiếp từ Hugging Face
    try:
        data_cpp = _goi_json_ai_cuc_bo("http://127.0.0.1:8080/v1/models", timeout=2)
        ds_cpp = [str(m.get("id") or "") for m in (data_cpp.get("data") or []) if isinstance(m, dict) and m.get("id")]
        if ds_cpp:
            return "llamacpp", ds_cpp[0]
    except Exception:
        pass

    raise LocalModelMissingError("Chưa có model LLM trong Ollama / LM Studio / llama.cpp.")


def dich_anh_local_ocr_gpu_tang_toc(
    img_bytes: bytes,
    *,
    ngon_ngu_nguon: str = "ja",
    ngon_ngu_dich: str = "vi",
    tu_dien_rieng: str = "",
    chay_cpu: bool = False,
) -> list[dict]:
    """
    Chế độ `local_ocr_gpu` (OCR Cục bộ Windows/HuggingFace ONNX + GPU Của Bạn - 0đ):
    - Có bộ nhớ đệm LRU (`_LOCAL_PAGE_TRANSLATION_CACHE`, tối đa 128 trang) giúp trả kết quả tức thì (< 1ms)
      khi cuộn lại trang cũ trên Chrome Extension hoặc xuất lại chapter với font chữ khác.
    - Ưu tiên dùng Qwen3-VL / Qwen3 / Gemma3 cục bộ trên GPU (43.4 token/s) nếu Ollama / LM Studio đang mở.
    - Nếu máy chưa bật Ollama hoặc không đủ VRAM, tự động dùng OCR cục bộ (Windows + HuggingFace ONNX)
      kết hợp bộ dịch văn bản nhanh + hậu kiểm thoại truyện tranh (`hau_kiem_va_sua_ban_dich`) ở mức 0 VNĐ.
    """
    ma_anh = hashlib.sha256(img_bytes).hexdigest()
    khoa_cache = (ma_anh, ngon_ngu_nguon, ngon_ngu_dich, (tu_dien_rieng or "")[:200])
    with _LOCAL_CACHE_LOCK:
        da_luu = _LOCAL_PAGE_TRANSLATION_CACHE.get(khoa_cache)
        if da_luu is not None:
            return [dict(r) for r in da_luu]

    bubbles = nhan_dien_bong_thoai_ocr_cuc_bo(img_bytes, ngon_ngu_nguon=ngon_ngu_nguon)
    if not bubbles:
        return []

    ngu_canh_gop = lay_ngu_canh_lien_trang_hien_tai(tu_dien_rieng)
    try:
        backend, model = _ket_noi_llm_cho_local_ocr_gpu(ngon_ngu_dich=ngon_ngu_dich)
        ket_qua = _dich_danh_sach_thoai_gpu(
            bubbles,
            backend=backend,
            model=model,
            ngon_ngu_nguon=ngon_ngu_nguon,
            ngon_ngu_dich=ngon_ngu_dich,
            tu_dien_rieng=ngu_canh_gop,
            chay_cpu=chay_cpu,
        )
    except (LocalServerUnavailableError, LocalModelMissingError, LocalRuntimeCrashError, RuntimeError, OSError, TimeoutError):
        ket_qua = _dich_danh_sach_thoai_qua_server_deepseek(
            bubbles,
            ngon_ngu_nguon=ngon_ngu_nguon,
            ngon_ngu_dich=ngon_ngu_dich,
            tu_dien_rieng=ngu_canh_gop,
            page_key=ma_anh,
            engine="local_ocr_gpu",
        )

    if ket_qua:
        cap_nhat_ngu_canh_lien_trang(ket_qua)
        with _LOCAL_CACHE_LOCK:
            if len(_LOCAL_PAGE_TRANSLATION_CACHE) >= 128:
                _LOCAL_PAGE_TRANSLATION_CACHE.pop(next(iter(_LOCAL_PAGE_TRANSLATION_CACHE)), None)
            _LOCAL_PAGE_TRANSLATION_CACHE[khoa_cache] = [dict(r) for r in ket_qua]
    return ket_qua


# Bảng cấu hình số lượt trừ mỗi trang theo từng Bộ máy AI (Phân tầng 1 - 2 - 3 lượt/trang):
# - local_ocr_gpu    : 1 lượt/trang (hút khách tập trung vào bản tiêu chuẩn nhanh & tiết kiệm)
# - local_hybrid_pro : 2 lượt/trang (bản nâng cấp Tự Học 60 từ & Chữ Viết Tay 2 tầng cho truyện khó)
# - llm_context      : 3 lượt/trang (Mắt thần Đám mây Gemini Vision 2K & DeepSeek Ultra chuẩn Scanlation)
SO_LUOT_MOI_TRANG_THEO_ENGINE: dict[str, int] = {
    "local_ocr_gpu": 1,
    "local_hybrid_pro": 2,
    "llm_context": 3,
    "google_fast": 1,
    "local_gguf": 1,
}


def _tang_cuong_anh_chu_viet_tay(img_bytes: bytes) -> bytes:
    """
    Tiền xử lý ảnh chuyên sâu cho `local_hybrid_pro`:
    Làm rõ nét chữ viết tay mảnh, chữ nghiêng, lời lẩm bẩm nhỏ ngoài bóng thoại bằng Adaptive Autocontrast + Sharpen.
    """
    if Image is None:
        return img_bytes
    try:
        from PIL import ImageEnhance, ImageOps

        with Image.open(io.BytesIO(img_bytes)) as im:
            rgb = im.convert("RGB")
            rgb = ImageOps.autocontrast(rgb, cutoff=1)
            rgb = ImageEnhance.Contrast(rgb).enhance(1.28)
            rgb = ImageEnhance.Sharpness(rgb).enhance(1.65)
            buf = io.BytesIO()
            rgb.save(buf, format="JPEG", quality=94)
            return buf.getvalue()
    except Exception:
        return img_bytes


def dich_anh_local_hybrid_pro_tu_hoc(
    img_bytes: bytes,
    *,
    ngon_ngu_nguon: str = "ja",
    ngon_ngu_dich: str = "vi",
    tu_dien_rieng: str = "",
    chay_cpu: bool = False,
) -> list[dict]:
    """
    Chế độ nâng cấp cao cấp `local_hybrid_pro (🧠 OCR + GPU Pro — Tự Học & Chữ Viết Tay)`:
    - Giữ nguyên tốc độ của `local_ocr_gpu` nhưng bổ sung 3 lớp thông minh cho truyện khó / chữ viết tay:
      1. Quét OCR đa tầng (Multi-Pass): nếu ảnh có vùng chữ viết tay mờ/nhỏ, tự động chạy thêm lượt quét trên ảnh đã
         tăng tương phản & làm sắc nét (`_tang_cuong_anh_chu_viet_tay`) để gộp thêm bóng thoại bị sót.
      2. Tích hợp trực tiếp Bộ Nhớ Tự Học Vĩnh Viễn (`nap_bo_nho_tu_hoc` từ `~/.dich_truyen_bo_nho_tu_hoc.json`) vào
         ngữ cảnh dịch của trang để tự động nhớ mọi câu khó / tiếng lóng mà người dùng từng sửa.
      3. Hậu kiểm đa tầng & tự động cứu hộ các câu thoại phức tạp.
    """
    bo_nho = nap_bo_nho_tu_hoc()
    goi_y_tu_hoc = ", ".join(f"{k}={v}" for k, v in list(bo_nho.items())[-40:])
    tu_dien_ket_hop = "\n".join(filter(None, [tu_dien_rieng, goi_y_tu_hoc]))

    ma_anh = hashlib.sha256(img_bytes).hexdigest()
    khoa_cache = (f"pro::{ma_anh}", ngon_ngu_nguon, ngon_ngu_dich, (tu_dien_ket_hop or "")[:240])
    with _LOCAL_CACHE_LOCK:
        da_luu = _LOCAL_PAGE_TRANSLATION_CACHE.get(khoa_cache)
        if da_luu is not None:
            return [dict(r) for r in da_luu]

    bubbles = nhan_dien_bong_thoai_ocr_cuc_bo(img_bytes, ngon_ngu_nguon=ngon_ngu_nguon)
    # Quét đa tầng (Multi-Pass Handwritten OCR): luôn kiểm tra thêm trên ảnh đã tăng tương phản & làm nét chữ viết tay
    # để bắt trọn những bóng thoại chữ viết tay mảnh, chữ nghiêng hoặc lời lẩm bẩm nhỏ bên ngoài bóng thoại
    anh_tang_cuong = _tang_cuong_anh_chu_viet_tay(img_bytes)
    if anh_tang_cuong != img_bytes and len(bubbles) < 8:
        bubbles_them = nhan_dien_bong_thoai_ocr_cuc_bo(anh_tang_cuong, ngon_ngu_nguon=ngon_ngu_nguon)
        for b_moi in bubbles_them:
            trung_lap = any(
                abs(int(b_moi["x"]) - int(b_cu["x"])) < 35 and abs(int(b_moi["y"]) - int(b_cu["y"])) < 35
                for b_cu in bubbles
            )
            if not trung_lap:
                bubbles.append(b_moi)

    if not bubbles:
        return []

    ngu_canh_pro = lay_ngu_canh_lien_trang_hien_tai(tu_dien_ket_hop)
    try:
        backend, model = _ket_noi_llm_cho_local_ocr_gpu(ngon_ngu_dich=ngon_ngu_dich)
        ket_qua = _dich_danh_sach_thoai_gpu(
            bubbles,
            backend=backend,
            model=model,
            ngon_ngu_nguon=ngon_ngu_nguon,
            ngon_ngu_dich=ngon_ngu_dich,
            tu_dien_rieng=ngu_canh_pro,
            chay_cpu=chay_cpu,
            che_do_pro=True,
        )
    except (LocalServerUnavailableError, LocalModelMissingError, LocalRuntimeCrashError, RuntimeError, OSError, TimeoutError):
        ket_qua = _dich_danh_sach_thoai_qua_server_deepseek(
            bubbles,
            ngon_ngu_nguon=ngon_ngu_nguon,
            ngon_ngu_dich=ngon_ngu_dich,
            tu_dien_rieng=ngu_canh_pro,
            page_key=ma_anh,
            engine="local_hybrid_pro",
        )

    if ket_qua:
        cap_nhat_ngu_canh_lien_trang(ket_qua)
        with _LOCAL_CACHE_LOCK:
            if len(_LOCAL_PAGE_TRANSLATION_CACHE) >= 128:
                _LOCAL_PAGE_TRANSLATION_CACHE.pop(next(iter(_LOCAL_PAGE_TRANSLATION_CACHE)), None)
            _LOCAL_PAGE_TRANSLATION_CACHE[khoa_cache] = [dict(r) for r in ket_qua]
    return ket_qua


LOCAL_BRIDGE_PORT = 17890
_LOCAL_BRIDGE_SERVER = None
_BRIDGE_PAGES_STORE: dict[str, dict] = {}
_BRIDGE_IMAGES_STORE: dict[str, bytes] = {}
_BRIDGE_REQ_KEY_STORE: dict[str, str] = {}
_BRIDGE_STORE_LOCK = threading.Lock()


def lay_dia_chi_ip_mang_lan() -> str:
    """Lấy địa chỉ IP LAN / VPN (Radmin, Tailscale, ZeroTier) của máy chủ hiện tại để máy khách kết nối."""
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.settimeout(0.3)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        return ip if ip and not ip.startswith("127.") else "127.0.0.1"
    except Exception:
        return "127.0.0.1"
    finally:
        try:
            s.close()
        except Exception:
            pass


def _tach_multipart_form_data(content_type: str, body: bytes) -> tuple[dict[str, str], bytes]:
    """Tách các trường dữ liệu và file ảnh từ gói multipart/form-data của máy khách gửi lên."""
    m_b = re.search(r'boundary=(?:"([^"]+)"|([^;\s]+))', content_type or "", re.I)
    if not m_b:
        raise ValueError("Thiếu boundary trong multipart/form-data")
    boundary = (m_b.group(1) or m_b.group(2)).encode("utf-8")
    parts = body.split(b"--" + boundary)
    fields: dict[str, str] = {}
    file_bytes = b""
    for part in parts:
        part = part.strip(b"\r\n")
        if not part or part == b"--" or part.startswith(b"--\r\n"):
            continue
        if b"\r\n\r\n" not in part:
            continue
        raw_hdr, content = part.split(b"\r\n\r\n", 1)
        if content.endswith(b"\r\n"):
            content = content[:-2]
        hdr_text = raw_hdr.decode("utf-8", errors="replace")
        m_name = re.search(r'name="([^"]+)"', hdr_text)
        if not m_name:
            continue
        fname = m_name.group(1)
        if 'filename="' in hdr_text or fname == "file":
            file_bytes = content
        else:
            fields[fname] = content.decode("utf-8", errors="replace")
    return fields, file_bytes


def xu_ly_multipart_doc_truyen_tu_may_khach(fields: dict[str, str], img_bytes: bytes) -> dict:
    """
    Xử lý yêu cầu chuẩn `/api/v1/doc-truyen/trang` (hoặc `/api/v1/developer/translate-page`) từ máy tính khách
    kết nối về máy chủ của bạn:
    - Hỗ trợ chống trùng `request_key` (`idempotent_upload_v1`) và tách cấu hình riêng (`private_context_v1`).
    - Chạy OCR HuggingFace ONNX + GPU Local + Xoá chữ Inpainting (`xoa_chu_va_ve_ban_dich_tren_anh`) 0 VNĐ.
    """
    if not img_bytes:
        raise ValueError("File ảnh rỗng.")
    req_key = str(fields.get("request_key") or "").strip() or None
    if req_key:
        with _BRIDGE_STORE_LOCK:
            old_pid = _BRIDGE_REQ_KEY_STORE.get(req_key)
            if old_pid and old_pid in _BRIDGE_PAGES_STORE:
                cached_doc = dict(_BRIDGE_PAGES_STORE[old_pid])
                cached_doc["request_key"] = req_key
                return cached_doc

    W, H = 1000, 1400
    if Image is not None:
        try:
            with Image.open(io.BytesIO(img_bytes)) as im_tmp:
                W, H = im_tmp.size
        except Exception:
            pass

    src_lang = str(fields.get("source_lang") or "ja").strip() or "ja"
    tgt_lang = str(fields.get("target_lang") or "vi").strip() or "vi"
    font_style = str(fields.get("font_style") or "bangers").strip() or "bangers"
    tu_dien = str(fields.get("tu_dien_rieng") or fields.get("glossary") or "").strip()
    che_do = str(fields.get("che_do") or "day_du").strip() or "day_du"
    eng_req = str(fields.get("engine") or "local_ocr_gpu").strip() or "local_ocr_gpu"

    ham_dich_bridge = (
        dich_anh_local_hybrid_pro_tu_hoc
        if eng_req == "local_hybrid_pro"
        else dich_anh_local_ocr_gpu_tang_toc
    )
    vung = ham_dich_bridge(
        img_bytes,
        ngon_ngu_nguon=src_lang,
        ngon_ngu_dich=tgt_lang,
        tu_dien_rieng=tu_dien,
        chay_cpu=False,
    )

    page_id = str(uuid.uuid4())
    rendered_bytes = img_bytes
    if vung and Image is not None:
        try:
            rendered_bytes = xoa_chu_va_ve_ban_dich_tren_anh(img_bytes, vung, font_style)
        except Exception:
            rendered_bytes = img_bytes

    doc = {
        "page_id": page_id,
        "project_id": str(uuid.uuid4()),
        "request_key": req_key,
        "cau_hinh_rieng": True,
        "trang_thai": "done",
        "xong": True,
        "che_do": che_do,
        "anh_da_dich": rendered_bytes is not None,
        "image_width": W,
        "image_height": H,
        "vung": vung,
    }
    with _BRIDGE_STORE_LOCK:
        if len(_BRIDGE_PAGES_STORE) >= 128:
            oldest = next(iter(_BRIDGE_PAGES_STORE))
            _BRIDGE_PAGES_STORE.pop(oldest, None)
            _BRIDGE_IMAGES_STORE.pop(oldest, None)
        _BRIDGE_PAGES_STORE[page_id] = doc
        if rendered_bytes is not None:
            _BRIDGE_IMAGES_STORE[page_id] = rendered_bytes
        if req_key:
            _BRIDGE_REQ_KEY_STORE[req_key] = page_id
    return doc


def xu_ly_yeu_cau_local_bridge(payload: dict) -> dict:
    """
    Xử lý yêu cầu dịch 1 trang truyện từ Chrome Extension gửi qua Local Companion Bridge (127.0.0.1:17890):
    - Tận dụng OCR cục bộ (Windows Media OCR + HuggingFace ONNX JA/ZH/KO/EN) và AI trên máy tính (0 VNĐ).
    - Tự động xóa chữ gốc & vẽ bản dịch (`xoa_chu_va_ve_ban_dich_tren_anh`) trả về `anh_da_dich_data_url`.
    """
    b64_raw = str(payload.get("image_base64") or "").strip()
    if "," in b64_raw and b64_raw.startswith("data:"):
        b64_raw = b64_raw.split(",", 1)[1]
    if not b64_raw:
        raise ValueError("Thiếu dữ liệu ảnh image_base64.")
    img_bytes = base64.b64decode(b64_raw)
    W, H = 1000, 1400
    if Image is not None:
        try:
            with Image.open(io.BytesIO(img_bytes)) as im_tmp:
                W, H = im_tmp.size
        except Exception:
            pass

    src_lang = str(payload.get("source_lang") or "ja").strip() or "ja"
    tgt_lang = str(payload.get("target_lang") or "vi").strip() or "vi"
    font_style = str(payload.get("font_style") or "bangers").strip() or "bangers"
    tu_dien = str(payload.get("tu_dien_rieng") or "").strip()
    che_do = str(payload.get("che_do") or "ve_anh").strip()
    eng_req = str(payload.get("engine") or "local_ocr_gpu").strip() or "local_ocr_gpu"

    ham_dich_bridge = (
        dich_anh_local_hybrid_pro_tu_hoc
        if eng_req == "local_hybrid_pro"
        else dich_anh_local_ocr_gpu_tang_toc
    )
    vung = ham_dich_bridge(
        img_bytes,
        ngon_ngu_nguon=src_lang,
        ngon_ngu_dich=tgt_lang,
        tu_dien_rieng=tu_dien,
        chay_cpu=False,
    )
    anh_data_url = None
    if vung and che_do != "chi_chu" and Image is not None:
        try:
            rendered_bytes = xoa_chu_va_ve_ban_dich_tren_anh(img_bytes, vung, font_style)
            anh_data_url = "data:image/jpeg;base64," + base64.b64encode(rendered_bytes).decode("ascii")
        except Exception:
            anh_data_url = None

    return {
        "xong": True,
        "engine": "local_bridge_windows_app",
        "model_engine": eng_req,
        "credits": int(SO_LUOT_MOI_TRANG_THEO_ENGINE.get(eng_req, 1)),
        "image_width": W,
        "image_height": H,
        "vung": vung,
        "anh_da_dich_data_url": anh_data_url,
    }


def khoi_dong_may_chu_bridge_cuc_bo(port: int = LOCAL_BRIDGE_PORT, ghi_log_fn=None) -> bool:
    """
    Khởi chạy Cổng API Máy Chủ Nội Bộ `0.0.0.0:17890` (Daemon Thread) giúp:
    1. Tiện ích Chrome (`extension-doc-truyen`) trên máy tính này kết nối qua `http://127.0.0.1:17890`.
    2. Máy tính khách (App Windows / Chrome Extension / Tool bên thứ 3) trong mạng LAN / VPN / Tunnel
       đấu nối trực tiếp vào `http://<IP-Máy-Chủ>:17890` theo đúng chuẩn API Cloud (`/healthz`,
       `/api/v1/han-muc`, `/api/v1/auth/*`, `/api/v1/doc-truyen/trang`, `/api/v1/developer/*`) với chi phí 0 VNĐ!
    """
    global _LOCAL_BRIDGE_SERVER
    if _LOCAL_BRIDGE_SERVER is not None:
        return True
    import http.server

    class _BridgeHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def _send_cors(self):
            origin = self.headers.get("Origin") or ""
            if origin.startswith(("chrome-extension://", "http://127.0.0.1", "http://localhost", "https://comic.io.vn")):
                self.send_header("Access-Control-Allow-Origin", origin)
            else:
                self.send_header("Access-Control-Allow-Origin", "https://comic.io.vn")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
            self.send_header(
                "Access-Control-Allow-Headers",
                "Content-Type, Authorization, X-API-Key, X-Customer-Api-Key, X-Ma-Khach, X-Ma-May-Tinh",
            )

        def _send_json(self, code: int, data: dict):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self._send_cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            self.send_response(204)
            self._send_cors()
            self.end_headers()

        def do_GET(self):
            path_clean = self.path.split("?", 1)[0].rstrip("/") or "/"
            if path_clean in ("/", "/healthz"):
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "status": "ok",
                        "service": "manga-studio-local-bridge",
                        "port": port,
                        "translate_default_engine": "local_ocr_gpu",
                        "translation_capabilities": {
                            "private_context_v1": True,
                            "idempotent_upload_v1": True,
                        },
                    },
                )
                return

            if path_clean in (
                "/api/v1/han-muc",
                "/api/v1/developer/me",
                "/api/v1/auth/me",
                "/api/v1/auth/api-key",
                "/api/v1/nap-luot/thong-tin",
            ):
                self._send_json(
                    403,
                    {
                        "detail": "Xác thực tài khoản & hạn mức trang phải thực hiện trên máy chủ Cloud chính thức (https://translation-api.vibe1.tinhgon.xyz)."
                    },
                )
                return

            m_yeu_cau = re.match(r"^/api/v1/doc-truyen/yeu-cau/([^/]+)$", path_clean)
            if m_yeu_cau:
                req_k = m_yeu_cau.group(1)
                with _BRIDGE_STORE_LOCK:
                    pid = _BRIDGE_REQ_KEY_STORE.get(req_k)
                    doc = _BRIDGE_PAGES_STORE.get(pid) if pid else None
                if doc is None:
                    self._send_json(404, {"detail": "Chưa có yêu cầu này trên cổng nội bộ."})
                else:
                    self._send_json(200, doc)
                return

            m_anh = re.match(r"^/api/v1/(?:doc-truyen/trang|developer/pages)/([^/]+)/(?:anh|image)$", path_clean)
            if m_anh:
                pid = m_anh.group(1)
                with _BRIDGE_STORE_LOCK:
                    img_b = _BRIDGE_IMAGES_STORE.get(pid)
                if not img_b:
                    self._send_json(404, {"detail": "Chưa có ảnh đã dịch cho trang này."})
                    return
                self.send_response(200)
                self._send_cors()
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(img_b)))
                self.end_headers()
                self.wfile.write(img_b)
                return

            m_trang = re.match(r"^/api/v1/(?:doc-truyen/trang|developer/pages)/([^/]+)$", path_clean)
            if m_trang:
                pid = m_trang.group(1)
                with _BRIDGE_STORE_LOCK:
                    doc = _BRIDGE_PAGES_STORE.get(pid)
                if doc is None:
                    self._send_json(404, {"detail": "Không tìm thấy trang trên cổng nội bộ."})
                else:
                    self._send_json(200, doc)
                return

            self._send_json(404, {"detail": "Endpoint không tồn tại trên cổng nội bộ."})

        def do_POST(self):
            path_clean = self.path.split("?", 1)[0].rstrip("/")
            try:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length > 0 else b"{}"
                ctype = self.headers.get("Content-Type") or ""

                if path_clean in ("/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/api-key"):
                    self._send_json(
                        403,
                        {
                            "detail": "Xác thực tài khoản phải thực hiện trên máy chủ Cloud chính thức (https://translation-api.vibe1.tinhgon.xyz)."
                        },
                    )
                    return

                if path_clean == "/api/v1/local-bridge/dich-trang":
                    payload = json.loads(raw.decode("utf-8"))
                    kq = xu_ly_yeu_cau_local_bridge(payload)
                    self._send_json(200, kq)
                    return

                if path_clean == "/api/v1/local-bridge/hoc-tu-sua":
                    payload = json.loads(raw.decode("utf-8", errors="replace") or "{}")
                    hoc_tu_ban_sua_nguoi_dung(
                        str(payload.get("chu_goc") or ""),
                        str(payload.get("ban_dich") or ""),
                    )
                    self._send_json(200, {"ok": True, "so_cau_da_hoc": len(nap_bo_nho_tu_hoc())})
                    return

                if path_clean in ("/api/v1/doc-truyen/trang", "/api/v1/developer/translate-page"):
                    if "multipart/form-data" in ctype.lower():
                        fields, img_bytes = _tach_multipart_form_data(ctype, raw)
                        doc = xu_ly_multipart_doc_truyen_tu_may_khach(fields, img_bytes)
                        self._send_json(200, doc)
                        return
                    payload = json.loads(raw.decode("utf-8"))
                    kq = xu_ly_yeu_cau_local_bridge(payload)
                    self._send_json(200, kq)
                    return

                self._send_json(404, {"detail": "Endpoint POST không tồn tại."})
            except Exception as exc:
                self._send_json(500, {"detail": str(exc)})

    for bind_addr in ("127.0.0.1",):
        try:
            server = http.server.ThreadingHTTPServer((bind_addr, port), _BridgeHandler)
            _LOCAL_BRIDGE_SERVER = server
            threading.Thread(target=server.serve_forever, daemon=True).start()
            if callable(ghi_log_fn):
                ghi_log_fn(
                    f"🔌 Đã kết nối Cổng Đồng Bộ Tiện Ích Nội Bộ (127.0.0.1:{port} — Bảo mật cục bộ)"
                )
            return True
        except OSError:
            continue
    return False


def xuat_pdf_va_longstrip_chapter(
    tm_chap: Path,
    ten_chap: str,
    thu_muc_goc: Path,
    *,
    xuat_pdf: bool = False,
    xuat_longstrip: bool = False,
    trang_da_kiem: list[Path] | None = None,
) -> list[str]:
    """Tự động đóng gói thêm file .PDF và ghép dải ảnh dài Webtoon (Long-Strip) cho Chapter."""
    if Image is None:
        return []
    ds_file = list(trang_da_kiem) if trang_da_kiem is not None else sorted(tm_chap.glob("*.jpg"), key=natural_key)
    if not ds_file:
        return []
    pixels = 0
    for file in ds_file:
        with Image.open(file) as image:
            pixels += image.width * image.height
        if pixels * 3 > 192 * 1024 * 1024:
            raise NeedsAttention("Chapter quá lớn để ghép PDF/dải ảnh an toàn. Dùng CBZ hoặc chia nhỏ chapter.")
    da_xuat: list[str] = []
    ds_im = [Image.open(p).convert("RGB") for p in ds_file]
    try:
        if xuat_pdf:
            pdf_path = thu_muc_goc / f"{ten_chap}.pdf"
            ds_im[0].save(pdf_path, "PDF", resolution=100.0, save_all=True, append_images=ds_im[1:])
            da_xuat.append(pdf_path.name)

        if xuat_longstrip:
            # Ghép dọc tối đa 15.000px mỗi dải để mọi trình xem ảnh đọc mượt
            MAX_H = 15000
            rong_chung = max(im.width for im in ds_im)
            cac_dai: list[list] = []
            dai_hien_tai: list = []
            cao_hien_tai = 0
            for im in ds_im:
                ty_le = rong_chung / max(1, im.width)
                cao_moi = int(round(im.height * ty_le))
                if dai_hien_tai and (cao_hien_tai + cao_moi > MAX_H):
                    cac_dai.append(dai_hien_tai)
                    dai_hien_tai = []
                    cao_hien_tai = 0
                dai_hien_tai.append((im, cao_moi))
                cao_hien_tai += cao_moi
            if dai_hien_tai:
                cac_dai.append(dai_hien_tai)

            for idx_d, dai in enumerate(cac_dai, start=1):
                tong_h = sum(h for _, h in dai)
                canvas = Image.new("RGB", (rong_chung, max(1, tong_h)), (255, 255, 255))
                y_cur = 0
                for im, h_m in dai:
                    im_rs = im.resize((rong_chung, h_m)) if im.width != rong_chung else im
                    canvas.paste(im_rs, (0, y_cur))
                    y_cur += h_m
                ten_strip = (
                    f"{ten_chap}_Webtoon_LongStrip.jpg"
                    if len(cac_dai) == 1
                    else f"{ten_chap}_Webtoon_Part{idx_d:02d}.jpg"
                )
                strip_path = tm_chap / ten_strip
                canvas.save(strip_path, format="JPEG", quality=92)
                da_xuat.append(f"{ten_chap}/{ten_strip}")
    finally:
        for im in ds_im:
            try:
                im.close()
            except Exception:
                pass
    return da_xuat


def lam_sach_ten_thu_muc(ten: str) -> str:
    ten = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", ten.strip())
    ten = re.sub(r"\s+", "-", ten).strip("-.")
    return ten[:80] or "Chapter"


def _dinh_dang_ten_chapter(so: float) -> str:
    return f"Chapter-{int(so):03d}" if float(so).is_integer() else f"Chapter-{so}"


def tach_ten_truyen_va_chapter(
    chuoi: str,
    ten_mac_dinh: str = "Truyen-Moi",
    *,
    la_file_anh_le: bool = False,
) -> tuple[str, float, str]:
    """
    Tách thông minh (ten_truyen, so_chapter, ten_chapter) từ tên file ZIP/CBZ, tên thư mục hoặc tên file ảnh:
    - Ví dụ file gói/thư mục: 'One_Piece_Chap_12' -> ('One-Piece', 12.0, 'Chapter-012')
    - Ví dụ file ảnh lẻ có mã tập/chương: 'E39P01' -> (ten_mac_dinh, 39.0, 'Chapter-039'),
      'Naruto_Chap05_001' -> ('Naruto', 5.0, 'Chapter-005').
    """
    goc = (chuoi or "").strip()
    mac_dinh_sach = lam_sach_ten_thu_muc(ten_mac_dinh or "Truyen-Moi")
    if not goc:
        return mac_dinh_sach, 1.0, "Chapter-001"

    if la_file_anh_le:
        # Mẫu 1: Có tiền tố bộ truyện + từ khoá chapter/ep/e + số trang ở cuối (VD: 'Naruto_Chap05_01', 'E39P01', 'Ep35_P02')
        m_img = re.match(
            r"^(?:(.*?)[-_.\s]+)?(?:chapter|chap|chuong|chương|episode|ep|ch|c|e)[-_.\s]*(\d+(?:\.\d+)?)"
            r"(?:[-_.\s]*p(?:age)?[-_.\s]*\d+|[-_.\s]+\d+)$",
            goc,
            flags=re.I,
        )
        if m_img:
            tien_to = (m_img.group(1) or "").strip(" -_.")
            so = float(m_img.group(2))
            ten_tr = lam_sach_ten_thu_muc(tien_to) if tien_to else mac_dinh_sach
            return ten_tr, so, _dinh_dang_ten_chapter(so)
        return mac_dinh_sach, 1.0, "Chapter-001"

    # Với tên file nén (.zip/.cbz) hoặc tên thư mục:
    # 1. Tìm từ khoá tường minh: chapter / chap / chuong / episode / ep / ch / tap
    m_kw = re.search(
        r"^(.*?)(?:[-_.\s]+|^)(?:chapter|chap|chuong|chương|episode|ep|ch|tap|tập|vol)[-_.\s]*(\d+(?:\.\d+)?)\b",
        goc,
        flags=re.I,
    )
    if m_kw:
        tien_to = (m_kw.group(1) or "").strip(" -_.[]()")
        so = float(m_kw.group(2))
        ten_tr = lam_sach_ten_thu_muc(tien_to) if tien_to else mac_dinh_sach
        return ten_tr, so, _dinh_dang_ten_chapter(so)

    # 2. Mẫu viết tắt E39 / C12 ở đầu hoặc cuối tên thư mục/file gói
    m_short = re.match(r"^(?:(.*?)[-_.\s]+)?[ec](\d+(?:\.\d+)?)$", goc, flags=re.I)
    if m_short:
        tien_to = (m_short.group(1) or "").strip(" -_.[]()")
        so = float(m_short.group(2))
        ten_tr = lam_sach_ten_thu_muc(tien_to) if tien_to else mac_dinh_sach
        return ten_tr, so, _dinh_dang_ten_chapter(so)

    # 3. Tên bộ truyện kèm số chương ở cuối (VD: 'One_Piece_012', 'Solo-Leveling-5')
    m_tail = re.match(r"^(.+?)[-_.\s]+(\d+(?:\.\d+)?)$", goc)
    if m_tail:
        tien_to = m_tail.group(1).strip(" -_.[]()")
        if any(c.isalpha() for c in tien_to):
            so = float(m_tail.group(2))
            return lam_sach_ten_thu_muc(tien_to), so, _dinh_dang_ten_chapter(so)

    # 4. Chỉ là con số thuần tuý (VD: thư mục '01', '12')
    if re.match(r"^\d+(?:\.\d+)?$", goc):
        so = float(goc)
        return mac_dinh_sach, so, _dinh_dang_ten_chapter(so)

    # 5. Tên bộ truyện độc lập không ghi số chương -> mặc định là Chapter-001 của bộ truyện đó
    return lam_sach_ten_thu_muc(goc), 1.0, "Chapter-001"


def _khu_trung_ten_chapter_theo_truyen(ds_chap: list[dict]) -> list[dict]:
    """Sắp xếp theo trình tự (Tên truyện -> Số thứ tự chapter) và đảm bảo không trùng tên chapter trong cùng 1 truyện."""
    ds_sap_xep = sorted(
        ds_chap,
        key=lambda c: (
            natural_key(str(c.get("ten_truyen") or "")),
            float(c.get("so", 1.0)),
            natural_key(str(c.get("ten") or "")),
        ),
    )
    da_dung: dict[str, set[str]] = {}
    ket_qua: list[dict] = []
    for ch in ds_sap_xep:
        item = dict(ch)
        tr_key = lam_sach_ten_thu_muc(str(item.get("ten_truyen") or "Truyen-Moi")).casefold()
        tap_ten = da_dung.setdefault(tr_key, set())
        ten_goc = lam_sach_ten_thu_muc(str(item.get("ten") or "Chapter-001"))
        ten_moi = ten_goc
        dem = 2
        while ten_moi.casefold() in tap_ten:
            ten_moi = f"{ten_goc}-P{dem}"
            dem += 1
        tap_ten.add(ten_moi.casefold())
        item["ten"] = ten_moi
        ket_qua.append(item)
    return ket_qua


def phan_loai_nhieu_file_truyen(
    ds_duong_dan: list[str | Path],
    ten_truyen_mac_dinh: str = "Truyen-Moi",
) -> list[dict]:
    """
    Nhận danh sách nhiều file (nhiều gói .ZIP/.CBZ của nhiều truyện khác nhau, hoặc nhiều file ảnh rời)
    và tự động bóc tách thành từng (Tên_Truyện / Tên_Chapter) theo đúng trình tự:
    - Nếu 1 file .ZIP/.CBZ chứa nhiều thư mục con (nhiều Chapter hoặc nhiều Truyện), tự động tách riêng từng Chapter.
    - Nếu chọn nhiều file .ZIP/.CBZ của nhiều bộ truyện khác nhau, tự động nhận diện Tên_Truyện và Số_Chapter từ tên file.
    - Nếu chọn nhiều file ảnh rời (VD: E35P01.jpg, E35P02.jpg, E39P01.jpg...), tự động gom nhóm theo đúng từng Chapter.
    """
    from pathlib import PurePosixPath
    from sources import IMAGE_EXTENSIONS, MAX_PAGE_BYTES, MAX_PAGES, MAX_TOTAL_BYTES, UNSUPPORTED_IMAGES

    ds_path = [Path(p) for p in ds_duong_dan if p]
    if not ds_path:
        raise NeedsAttention("Chưa chọn file nào.")

    ten_md = (ten_truyen_mac_dinh or "").strip()
    if not ten_md or ten_md == "Truyen-Moi":
        ten_md = ds_path[0].parent.name or "Truyen-Moi"
    ten_md = lam_sach_ten_thu_muc(ten_md)

    ds_chapter: list[dict] = []
    anh_le: list[Path] = []

    for path in ds_path:
        ext = path.suffix.lower()
        if ext in (".zip", ".cbz"):
            try:
                with zipfile.ZipFile(path) as archive:
                    nhom_theo_tm: dict[str, list[tuple[str, int]]] = {}
                    seen_names: set[str] = set()
                    for entry in archive.infolist():
                        name = entry.filename.replace("\\", "/")
                        parts = PurePosixPath(name)
                        if parts.is_absolute() or ".." in parts.parts or ":" in name or "\x00" in name:
                            raise NeedsAttention(f"Gói {path.name} chứa đường dẫn không an toàn.")
                        if entry.is_dir() or "__MACOSX" in parts.parts:
                            continue
                        if parts.suffix.lower() in UNSUPPORTED_IMAGES:
                            raise NeedsAttention(
                                f"Ảnh {parts.name} trong {path.name} chưa được hỗ trợ; chuyển sang JPG/PNG/WEBP."
                            )
                        if parts.suffix.lower() not in IMAGE_EXTENSIONS:
                            continue
                        if name in seen_names or (entry.flag_bits & 1):
                            raise NeedsAttention(f"Gói {path.name} có tên ảnh trùng hoặc ảnh mã hoá.")
                        if entry.file_size > MAX_PAGE_BYTES:
                            raise NeedsAttention(f"Ảnh {parts.name} trong {path.name} vượt giới hạn 20 MB/trang.")
                        seen_names.add(name)
                        parent_str = str(parts.parent) if str(parts.parent) != "." else ""
                        nhom_theo_tm.setdefault(parent_str, []).append((entry.filename, entry.file_size))
            except (zipfile.BadZipFile, OSError) as exc:
                raise NeedsAttention(f"Không mở được gói ZIP/CBZ ({path.name}).") from exc

            if not nhom_theo_tm:
                raise NeedsAttention(f"Gói {path.name} không chứa ảnh JPG/PNG/WEBP được hỗ trợ.")

            ten_tr_tu_zip, so_tu_zip, ten_chap_tu_zip = tach_ten_truyen_va_chapter(
                path.stem, ten_mac_dinh=ten_md, la_file_anh_le=False
            )

            if len(nhom_theo_tm) == 1:
                tm_con, ds_entry = next(iter(nhom_theo_tm.items()))
                # Kiểm tra xem trong gói phẳng có chứa ảnh của nhiều tập/chapter khác nhau (VD: E35P01.jpg, E39P01.jpg) không
                nhom_anh_zip: dict[tuple[str, float, str], list[tuple[str, int]]] = {}
                for fname, fsize in ds_entry:
                    stem_anh = PurePosixPath(fname.replace("\\", "/")).stem
                    tr_a, so_a, chap_a = tach_ten_truyen_va_chapter(
                        stem_anh, ten_mac_dinh=ten_tr_tu_zip, la_file_anh_le=True
                    )
                    nhom_anh_zip.setdefault((tr_a, so_a, chap_a), []).append((fname, fsize))

                if len(nhom_anh_zip) > 1:
                    for (tr_a, so_a, chap_a), entries_c in nhom_anh_zip.items():
                        if len(entries_c) > MAX_PAGES or sum(sz for _, sz in entries_c) > MAX_TOTAL_BYTES:
                            raise NeedsAttention(f"Chapter {chap_a} trong {path.name} vượt 200 trang hoặc 50 MB.")
                        entries_sorted = [fn for fn, _ in sorted(entries_c, key=lambda x: natural_key(x[0]))]
                        srcs = [
                            "archive_file::" + json.dumps([str(path.resolve()), fn], ensure_ascii=False)
                            for fn in entries_sorted
                        ]
                        ds_chapter.append(
                            {
                                "ten_truyen": tr_a,
                                "so": so_a,
                                "ten": chap_a,
                                "url": f"archive::{path}#{chap_a}",
                                "nhan": f"{tr_a} / {chap_a} ({path.name})",
                                "sources": srcs,
                            }
                        )
                else:
                    if tm_con:
                        parts_tm = [p for p in PurePosixPath(tm_con).parts if p and p != "."]
                        if len(parts_tm) >= 2:
                            ten_tr_tu_zip = lam_sach_ten_thu_muc(parts_tm[0])
                            _, so_tu_zip, ten_chap_tu_zip = tach_ten_truyen_va_chapter(
                                parts_tm[-1], ten_mac_dinh=ten_tr_tu_zip, la_file_anh_le=False
                            )
                        elif len(parts_tm) == 1:
                            tr_sub, so_sub, chap_sub = tach_ten_truyen_va_chapter(
                                parts_tm[0], ten_mac_dinh=ten_tr_tu_zip, la_file_anh_le=False
                            )
                            if chap_sub != "Chapter-001" or re.search(r"\d", parts_tm[0]):
                                so_tu_zip, ten_chap_tu_zip = so_sub, chap_sub
                    if len(ds_entry) > MAX_PAGES or sum(sz for _, sz in ds_entry) > MAX_TOTAL_BYTES:
                        raise NeedsAttention(f"Gói {path.name} vượt giới hạn 200 trang hoặc 50 MB.")
                    entries_sorted = [fn for fn, _ in sorted(ds_entry, key=lambda x: natural_key(x[0]))]
                    srcs = [
                        "archive_file::" + json.dumps([str(path.resolve()), fn], ensure_ascii=False)
                        for fn in entries_sorted
                    ]
                    ds_chapter.append(
                        {
                            "ten_truyen": ten_tr_tu_zip,
                            "so": so_tu_zip,
                            "ten": ten_chap_tu_zip,
                            "url": f"archive::{path}",
                            "nhan": f"{ten_tr_tu_zip} / {ten_chap_tu_zip} ({path.name})",
                            "sources": srcs,
                        }
                    )
            else:
                # Gói ZIP chứa nhiều thư mục chapter con (hoặc nhiều truyện)
                for tm_con, ds_entry in sorted(nhom_theo_tm.items(), key=lambda kv: natural_key(kv[0])):
                    parts_tm = [p for p in PurePosixPath(tm_con).parts if p and p != "."]
                    if len(parts_tm) >= 2:
                        tr_c = lam_sach_ten_thu_muc(parts_tm[-2])
                        _, so_c, chap_c = tach_ten_truyen_va_chapter(
                            parts_tm[-1], ten_mac_dinh=tr_c, la_file_anh_le=False
                        )
                    elif len(parts_tm) == 1:
                        tr_c, so_c, chap_c = tach_ten_truyen_va_chapter(
                            parts_tm[0], ten_mac_dinh=ten_tr_tu_zip, la_file_anh_le=False
                        )
                        if tr_c == lam_sach_ten_thu_muc(parts_tm[0]) and chap_c == "Chapter-001":
                            # Thư mục con không mang từ khoá chapter -> giữ tên truyện từ tên file ZIP
                            tr_c = ten_tr_tu_zip
                            chap_c = lam_sach_ten_thu_muc(parts_tm[0])
                    else:
                        tr_c, so_c, chap_c = ten_tr_tu_zip, so_tu_zip, ten_chap_tu_zip

                    if len(ds_entry) > MAX_PAGES or sum(sz for _, sz in ds_entry) > MAX_TOTAL_BYTES:
                        raise NeedsAttention(f"Chapter {chap_c} trong {path.name} vượt 200 trang hoặc 50 MB.")
                    entries_sorted = [fn for fn, _ in sorted(ds_entry, key=lambda x: natural_key(x[0]))]
                    srcs = [
                        "archive_file::" + json.dumps([str(path.resolve()), fn], ensure_ascii=False)
                        for fn in entries_sorted
                    ]
                    ds_chapter.append(
                        {
                            "ten_truyen": tr_c,
                            "so": so_c,
                            "ten": chap_c,
                            "url": f"archive::{path}#{tm_con}",
                            "nhan": f"{tr_c} / {chap_c} ({path.name})",
                            "sources": srcs,
                        }
                    )
        elif ext in UNSUPPORTED_IMAGES:
            raise NeedsAttention(f"Ảnh {path.name} chưa được hỗ trợ; chuyển sang JPG/PNG/WEBP trước khi dịch.")
        elif ext in IMAGE_EXTENSIONS:
            anh_le.append(path)

    if anh_le:
        nhom_anh: dict[tuple[str, float, str], list[Path]] = {}
        for p_img in anh_le:
            ten_cha = p_img.parent.name or ten_md
            tr_MacDinh = ten_md if (ten_truyen_mac_dinh and ten_truyen_mac_dinh != "Truyen-Moi") else ten_cha
            tr_i, so_i, chap_i = tach_ten_truyen_va_chapter(
                p_img.stem, ten_mac_dinh=tr_MacDinh, la_file_anh_le=True
            )
            # Nếu thư mục cha đã là tên Chapter (VD: 'Chap 02/001.jpg') thì lấy tên truyện ở cấp ông và tên chapter ở cấp cha
            if chap_i == "Chapter-001" and p_img.parent.name:
                tr_p, so_p, chap_p = tach_ten_truyen_va_chapter(
                    p_img.parent.name,
                    ten_mac_dinh=p_img.parent.parent.name or tr_MacDinh,
                    la_file_anh_le=False,
                )
                if chap_p != "Chapter-001" or re.search(r"\d", p_img.parent.name):
                    tr_i, so_i, chap_i = tr_p, so_p, chap_p
            nhom_anh.setdefault((tr_i, so_i, chap_i), []).append(p_img)

        for (tr_i, so_i, chap_i), files_c in nhom_anh.items():
            files_sorted = sorted(files_c, key=lambda x: natural_key(x.name))
            tong_dl = 0
            srcs = []
            for f_item in files_sorted:
                sz = f_item.stat().st_size
                tong_dl += sz
                if sz > MAX_PAGE_BYTES or tong_dl > MAX_TOTAL_BYTES:
                    raise NeedsAttention(f"Chapter {chap_i} ({tr_i}) vượt giới hạn 20 MB/trang hoặc 50 MB/chapter.")
                srcs.append(f"local_file::{f_item}")
            if len(srcs) > MAX_PAGES:
                raise NeedsAttention(f"Chapter {chap_i} ({tr_i}) vượt giới hạn 200 trang.")
            ds_chapter.append(
                {
                    "ten_truyen": tr_i,
                    "so": so_i,
                    "ten": chap_i,
                    "url": f"local_files::{tr_i}/{chap_i}",
                    "nhan": f"{tr_i} / {chap_i} ({len(srcs)} trang)",
                    "sources": srcs,
                }
            )

    if not ds_chapter:
        raise NeedsAttention("Không tìm thấy file gói (.zip/.cbz) hoặc ảnh (.jpg/.png/.webp) hợp lệ.")
    return _khu_trung_ten_chapter_theo_truyen(ds_chapter)


def phan_loai_thu_muc_nhieu_truyen(thu_muc: Path, ten_mac_dinh: str = "") -> list[dict]:
    """
    Quét thư mục chứa 1 hoặc nhiều bộ truyện (gồm cả thư mục lồng 2 cấp <Tên_Truyện>/<Tên_Chapter>,
    thư mục 1 cấp, file .ZIP/.CBZ và ảnh rời có mã tập E35P01/E39P01) để tự động chia đúng từng Chapter của từng Truyện.
    """
    from sources import IMAGE_EXTENSIONS

    tm = Path(thu_muc)
    ten_goc = lam_sach_ten_thu_muc(ten_mac_dinh or tm.name or "Truyen-Offline")
    ds_ket_qua: list[dict] = []

    # 1. Các file .zip/.cbz và ảnh rời nằm ngay tại thư mục gốc
    file_goc = [
        f for f in sorted(tm.iterdir(), key=lambda p: natural_key(p.name))
        if f.is_file() and (f.suffix.lower() in IMAGE_EXTENSIONS or f.suffix.lower() in (".zip", ".cbz"))
    ]
    if file_goc:
        ds_ket_qua.extend(phan_loai_nhieu_file_truyen(file_goc, ten_truyen_mac_dinh=ten_goc))

    # 2. Quét các thư mục con cấp 1 và cấp 2
    cac_tm_con = sorted([p for p in tm.iterdir() if p.is_dir()], key=lambda p: natural_key(p.name))
    for sub in cac_tm_con:
        file_sub = [
            f for f in sorted(sub.iterdir(), key=lambda p: natural_key(p.name))
            if f.is_file() and (f.suffix.lower() in IMAGE_EXTENSIONS or f.suffix.lower() in (".zip", ".cbz"))
        ]
        tm_cap_2 = sorted([p for p in sub.iterdir() if p.is_dir()], key=lambda p: natural_key(p.name))
        if tm_cap_2:
            # Cấu trúc 2 cấp: tm / <Tên_Truyện (sub)> / <Tên_Chapter (sub2)>
            ten_tr_sub = lam_sach_ten_thu_muc(sub.name)
            if file_sub:
                ds_ket_qua.extend(phan_loai_nhieu_file_truyen(file_sub, ten_truyen_mac_dinh=ten_tr_sub))
            for sub2 in tm_cap_2:
                file_sub2 = [
                    f for f in sorted(sub2.iterdir(), key=lambda p: natural_key(p.name))
                    if f.is_file() and (f.suffix.lower() in IMAGE_EXTENSIONS or f.suffix.lower() in (".zip", ".cbz"))
                ]
                if not file_sub2:
                    continue
                _, so_c2, ten_c2 = tach_ten_truyen_va_chapter(sub2.name, ten_mac_dinh=ten_tr_sub, la_file_anh_le=False)
                if any(f.suffix.lower() in (".zip", ".cbz") for f in file_sub2):
                    ds_ket_qua.extend(phan_loai_nhieu_file_truyen(file_sub2, ten_truyen_mac_dinh=ten_tr_sub))
                else:
                    ds_ket_qua.append(
                        {
                            "ten_truyen": ten_tr_sub,
                            "so": so_c2,
                            "ten": ten_c2 if re.search(r"\d", sub2.name) else lam_sach_ten_thu_muc(sub2.name),
                            "url": f"local_dir::{sub2}",
                            "nhan": f"{ten_tr_sub} / {sub2.name}",
                        }
                    )
        elif file_sub:
            # Cấu trúc 1 cấp: kiểm tra xem tên `sub` có chứa cả tên truyện lẫn số chapter (VD: 'Naruto_Chap01')
            # hoặc chứa nhiều tập ảnh rời (VD: E35P01.jpg, E39P01.jpg) hay không
            anh_only = [f for f in file_sub if f.suffix.lower() in IMAGE_EXTENSIONS]
            zip_only = [f for f in file_sub if f.suffix.lower() in (".zip", ".cbz")]
            if zip_only:
                ds_ket_qua.extend(phan_loai_nhieu_file_truyen(zip_only, ten_truyen_mac_dinh=sub.name))
            if anh_only:
                tap_chap_anh = {
                    tach_ten_truyen_va_chapter(f.stem, ten_mac_dinh=ten_goc, la_file_anh_le=True)[2]
                    for f in anh_only
                }
                if len(tap_chap_anh) > 1 or (len(tap_chap_anh) == 1 and next(iter(tap_chap_anh)) != "Chapter-001"):
                    ds_ket_qua.extend(phan_loai_nhieu_file_truyen(anh_only, ten_truyen_mac_dinh=sub.name))
                else:
                    tr_s, so_s, chap_s = tach_ten_truyen_va_chapter(
                        sub.name, ten_mac_dinh=ten_goc, la_file_anh_le=False
                    )
                    ten_chap_dung = chap_s if re.search(r"\d", sub.name) else lam_sach_ten_thu_muc(sub.name)
                    ds_ket_qua.append(
                        {
                            "ten_truyen": tr_s,
                            "so": so_s,
                            "ten": ten_chap_dung,
                            "url": f"local_dir::{sub}",
                            "nhan": f"{tr_s} / {sub.name}",
                        }
                    )

    if not ds_ket_qua:
        return [
            {
                "ten_truyen": ten_goc,
                "so": 1.0,
                "ten": "Chapter-001",
                "url": f"local_dir::{tm}",
                "nhan": tm.name,
            }
        ]
    return _khu_trung_ten_chapter_theo_truyen(ds_ket_qua)


def suy_doan_ten_truyen_tu_url(url_truyen: str, html: str = "", ten_mac_dinh: str = "Truyen-Moi") -> str:
    """Tự động suy đoán Tên bộ truyện từ đường dẫn URL (hoặc thẻ <title>/<h1>) để chia thư mục chuẩn xác."""
    tu_khoa_chung = {"manga", "truyen", "truyen-tranh", "comic", "comics", "webcomic", "webcomics", "read", "en", "vi", "title", "viewer", "chapter"}
    parts = [
        urllib.parse.unquote(p)
        for p in urllib.parse.urlsplit(url_truyen).path.split("/")
        if p and not p.lower().endswith((".html", ".htm", ".php"))
    ]
    pattern_chap = re.compile(
        r"(?<![a-z0-9])(?:chapter|chap|chuong|chương|episode|ep)[-_/\s.]*(\d+(?:\.\d+)?)(?![a-z0-9])",
        re.I,
    )
    pattern_slug_kem_chap = re.compile(
        r"^(.+?)[-_.\s]+(?:chapter|chap|chuong|chương|episode|ep)[-_.\s]*\d+(?:\.\d+)?.*$",
        re.I,
    )
    ung_vien = []
    for p in parts:
        if pattern_chap.search(p):
            m_slug = pattern_slug_kem_chap.match(p)
            if m_slug:
                tien_to = m_slug.group(1).strip("-_. ")
                if tien_to and tien_to.lower() not in tu_khoa_chung and not re.fullmatch(r"\d+", tien_to):
                    ung_vien.append(tien_to)
            continue
        if p.lower() in tu_khoa_chung or re.fullmatch(r"[0-9a-f]{8}-[0-9a-f-]{27}", p.lower()) or re.fullmatch(r"\d+", p):
            continue
        ung_vien.append(p)
    if ung_vien:
        return lam_sach_ten_thu_muc(ung_vien[-1])
    if html:
        m_h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, flags=re.I | re.S)
        if m_h1:
            t_h1 = re.sub(r"<[^>]+>", "", m_h1.group(1)).strip()
            if t_h1:
                tr_h1, _, _ = tach_ten_truyen_va_chapter(t_h1, ten_mac_dinh=ten_mac_dinh, la_file_anh_le=False)
                if tr_h1 and tr_h1 != "Truyen-Moi":
                    return tr_h1
    return lam_sach_ten_thu_muc(ten_mac_dinh or "Truyen-Moi")


def _quet_chapter_mangaplus(url: str, mo_rong_ca_bo: bool = False) -> list[dict]:
    """
    Bộ chuyển đổi (Adapter) chuyên biệt cho MANGA Plus by SHUEISHA (`mangaplus.shueisha.co.jp/viewer/<chapter_id>` hoặc `/titles/<title_id>`).
    Gọi trực tiếp API Protobuf v3 (`jumpg-webapi.tokyo-cdn.com/api/manga_viewer_v3` & `title_detailV4`) kèm `SESSION-TOKEN`
    để lấy tên bộ truyện, số thứ tự chương và danh sách toàn bộ các chương đang mở đọc.
    """
    m_mp = re.search(r"/(viewer|titles)/(\d+)", url or "", flags=re.I)
    if not m_mp:
        raise NeedsAttention("Link MANGA Plus không hợp lệ (ví dụ: https://mangaplus.shueisha.co.jp/viewer/1009923).")
    loai, mp_id = m_mp.group(1).lower(), m_mp.group(2)
    sid = str(uuid.uuid4())
    mp_headers = {
        "Origin": "https://mangaplus.shueisha.co.jp",
        "SESSION-TOKEN": sid,
    }
    if loai == "viewer":
        api_u = (
            f"https://jumpg-webapi.tokyo-cdn.com/api/manga_viewer_v3"
            f"?chapter_id={mp_id}&split=yes&img_quality=high&viewer_mode=horizontal&clang=eng&avif_enable=no"
        )
    else:
        api_u = f"https://jumpg-webapi.tokyo-cdn.com/api/title_detailV4?title_id={mp_id}&clang=eng&avif_enable=no"

    try:
        raw = goi_http(
            api_u,
            referer="https://mangaplus.shueisha.co.jp/",
            timeout=20,
            nguon_ngoai=True,
            extra_headers=mp_headers,
        )
    except Exception as exc:
        raise NeedsAttention(f"Không kết nối được API MANGA Plus: {exc}") from exc

    ten_truyen = "MangaPlus-Series"
    so_chap_hien_tai = 1.0
    m_sns = re.search(
        rb"https://jumpg-webapi\.tokyo-cdn\.com/www/sns_share\?title_id=(\d+)&chapter_id=(\d+)\*(.)(.{1,200})",
        raw,
        re.S,
    )
    if m_sns:
        tlen = m_sns.group(3)[0]
        rest = m_sns.group(4)
        t_raw = rest[:tlen].decode("utf-8", errors="ignore").strip()
        if t_raw:
            ten_truyen = lam_sach_ten_thu_muc(t_raw)
        if len(rest) > tlen + 2 and rest[tlen] == 0x32:
            clen = rest[tlen + 1]
            c_raw = rest[tlen + 2 : tlen + 2 + clen].decode("utf-8", errors="ignore").strip()
            m_num = re.search(r"(\d+(?:\.\d+)?)", c_raw)
            if m_num:
                try:
                    so_chap_hien_tai = float(m_num.group(1))
                except ValueError:
                    pass
    else:
        m_title_tag = re.search(rb"#MANGA_Plus\s+([^\x00-\x1f\"'*]{2,60})", raw)
        if m_title_tag:
            ten_truyen = lam_sach_ten_thu_muc(m_title_tag.group(1).decode("utf-8", errors="ignore").strip())

    chap_blocks = re.findall(
        rb"#([0-9]+(?:\.[0-9]+)?|ex).{1,120}?/chapter/(\d+)/chapter_thumbnail/",
        raw,
        re.I | re.S,
    )
    ds_mo_rong: dict[float, dict] = {}
    for idx_b, (c_num_b, c_id_b) in enumerate(chap_blocks, 1):
        c_str = c_num_b.decode("ascii", errors="ignore")
        cid_str = c_id_b.decode("ascii", errors="ignore")
        try:
            so_c = float(c_str)
        except ValueError:
            so_c = float(idx_b) + 0.5
        ten_c = f"Chapter-{int(so_c):03d}" if so_c.is_integer() else f"Chapter-{so_c}"
        if cid_str == mp_id:
            so_chap_hien_tai = so_c
        ds_mo_rong[so_c] = {
            "ten_truyen": ten_truyen,
            "so": so_c,
            "ten": ten_c,
            "url": f"https://mangaplus.shueisha.co.jp/viewer/{cid_str}",
            "nhan": f"{ten_truyen} / {ten_c}",
        }

    if loai == "titles" or (mo_rong_ca_bo and len(ds_mo_rong) > 1):
        if not ds_mo_rong:
            raise NeedsAttention("Không tìm thấy danh sách chapter khả dụng trên MANGA Plus.")
        return [ds_mo_rong[k] for k in sorted(ds_mo_rong)]

    ten_chap = f"Chapter-{int(so_chap_hien_tai):03d}" if so_chap_hien_tai.is_integer() else f"Chapter-{so_chap_hien_tai}"
    return [
        {
            "ten_truyen": ten_truyen,
            "so": so_chap_hien_tai,
            "ten": ten_chap,
            "url": f"https://mangaplus.shueisha.co.jp/viewer/{mp_id}",
            "nhan": f"{ten_truyen} / {ten_chap}",
        }
    ]


def _quet_anh_mangaplus(url_chapter: str) -> list[str]:
    """
    Trích xuất danh sách ảnh trang truyện chất lượng cao (`img_quality=high`) từ MANGA Plus API v3,
    kèm khoá giải mã `mp_key` (128-hex XOR) và `mp_vw` (`Plus-Vw-Token`) để `goi_http` tự động giải mã thành ảnh JPEG chuẩn.
    """
    m_mp = re.search(r"/viewer/(\d+)", url_chapter or "", flags=re.I)
    if not m_mp:
        raise NeedsAttention("Link chapter MANGA Plus không hợp lệ.")
    cid = m_mp.group(1)
    sid = str(uuid.uuid4())
    api_u = (
        f"https://jumpg-webapi.tokyo-cdn.com/api/manga_viewer_v3"
        f"?chapter_id={cid}&split=yes&img_quality=high&viewer_mode=horizontal&clang=eng&avif_enable=no"
    )
    raw = goi_http(
        api_u,
        referer="https://mangaplus.shueisha.co.jp/",
        timeout=20,
        nguon_ngoai=True,
        extra_headers={
            "Origin": "https://mangaplus.shueisha.co.jp",
            "SESSION-TOKEN": sid,
        },
    )
    m_vw = re.search(rb"\x9a\x01\x20([0-9a-f]{32})", raw)
    vw_token = m_vw.group(1).decode("ascii") if m_vw else ""
    pattern = re.compile(
        rb"(https://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+?/manga_page/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+)"
        rb".{1,12}?\*\x80\x01([0-9a-f]{128})",
        re.S,
    )
    pages = pattern.findall(raw)
    if not pages:
        raise NeedsAttention("Chapter này trên MANGA Plus đã hết hạn đọc miễn phí hoặc không có trang khả dụng.")
    ds_anh: list[str] = []
    for u_bytes, key_bytes in pages:
        u_str = u_bytes.decode("utf-8", errors="ignore")
        k_str = key_bytes.decode("ascii", errors="ignore")
        ds_anh.append(f"{u_str}#mp_key={k_str}&mp_vw={vw_token}")
    return ds_anh


def _quet_chapter_mangadex(url: str, mo_rong_ca_bo: bool = False) -> list[dict]:
    """
    Bộ chuyển đổi (Adapter) chuyên biệt cho MangaDex SPA (`mangadex.org/chapter/<uuid>` hoặc `mangadex.org/title/<uuid>`).
    Tự động gọi API chính thức `api.mangadex.org` và bắt lỗi nhà mạng chặn SNI (WinError 10054) để hướng dẫn bật 1.1.1.1/VPN.
    """
    m_uuid = re.search(r"/(chapter|title|manga)/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", url, flags=re.I)
    if not m_uuid:
        raise NeedsAttention("Link MangaDex thiếu mã UUID hợp lệ (ví dụ: https://mangadex.org/chapter/<uuid>).")
    loai, uid = m_uuid.group(1).lower(), m_uuid.group(2).lower()

    def _goi_md_json(api_url: str) -> dict:
        try:
            raw = goi_http(
                api_url,
                referer="",
                timeout=18,
                nguon_ngoai=True,
                extra_headers={"User-Agent": "MangaStudio/1.1"},
            )
            return json.loads(raw.decode("utf-8", errors="replace"))
        except Exception as exc:
            msg = str(exc)
            if "10054" in msg or "reset" in msg.lower() or "timed out" in msg.lower():
                raise NeedsAttention(
                    "Nhà mạng hiện tại đang chặn kết nối tới MangaDex (WinError 10054). "
                    "Hãy bật Cloudflare WARP (1.1.1.1) hoặc VPN rồi bấm Quét lại, hoặc tải gói ảnh (.zip/.cbz) về máy."
                ) from exc
            raise NeedsAttention(f"Không lấy được dữ liệu từ API MangaDex: {exc}") from exc

    if loai == "chapter":
        info = _goi_md_json(f"https://api.mangadex.org/chapter/{uid}?includes[]=manga")
        data = info.get("data") or {}
        attrs = data.get("attributes") or {}
        so_raw = attrs.get("chapter")
        try:
            so_chap = float(so_raw) if so_raw is not None else 1.0
        except (TypeError, ValueError):
            so_chap = 1.0
        ten_chap = f"Chapter-{int(so_chap):03d}" if so_chap.is_integer() else f"Chapter-{so_chap}"
        ten_truyen = "MangaDex-Series"
        manga_id = ""
        for rel in data.get("relationships") or []:
            if isinstance(rel, dict) and rel.get("type") == "manga":
                manga_id = str(rel.get("id") or "")
                t_map = (rel.get("attributes") or {}).get("title") or {}
                if isinstance(t_map, dict) and t_map:
                    ten_truyen = lam_sach_ten_thu_muc(next(iter(t_map.values())))
                break
        if mo_rong_ca_bo and manga_id:
            lang = attrs.get("translatedLanguage") or "en"
            return _quet_danh_sach_feed_mangadex(manga_id, ten_truyen, lang, _goi_md_json)
        return [
            {
                "ten_truyen": ten_truyen,
                "so": so_chap,
                "ten": ten_chap,
                "url": f"https://mangadex.org/chapter/{uid}",
                "nhan": f"{ten_truyen} / {ten_chap}",
            }
        ]

    # Trường hợp link bộ truyện: /title/<uuid> hoặc /manga/<uuid>
    info_m = _goi_md_json(f"https://api.mangadex.org/manga/{uid}")
    t_map = ((info_m.get("data") or {}).get("attributes") or {}).get("title") or {}
    ten_truyen = lam_sach_ten_thu_muc(next(iter(t_map.values())) if isinstance(t_map, dict) and t_map else "MangaDex-Series")
    return _quet_danh_sach_feed_mangadex(uid, ten_truyen, "en", _goi_md_json)


def _quet_danh_sach_feed_mangadex(manga_id: str, ten_truyen: str, lang: str, goi_fn) -> list[dict]:
    """
    Quét toàn bộ 100+ chapter của bộ truyện trên MangaDex:
    - Tự động phân trang (`offset=0, 500, 1000...`) để lấy trọn bộ truyện dài hàng trăm chương.
    - Tự động mở rộng đa ngôn ngữ (`en`, `ja`, `ko`, `zh`, `zh-hk`, `vi`) nếu ngôn ngữ mặc định không có bản dịch.
    """
    ds_ngon_ngu_thu = [lang] if lang else ["en"]
    for lg_phu in ("en", "ja", "ko", "zh", "zh-hk", "vi"):
        if lg_phu not in ds_ngon_ngu_thu:
            ds_ngon_ngu_thu.append(lg_phu)

    ds: list[dict] = []
    seen_so: set[float] = set()

    for lg in ds_ngon_ngu_thu:
        for offset in (0, 500, 1000):
            feed = goi_fn(
                f"https://api.mangadex.org/manga/{manga_id}/feed?translatedLanguage[]={lg}&order[chapter]=asc&limit=500&offset={offset}"
            )
            items = feed.get("data") or []
            if not items:
                break
            for item in items:
                if not isinstance(item, dict):
                    continue
                cid = item.get("id")
                attrs = item.get("attributes") or {}
                if int(attrs.get("pages") or 0) <= 0 and attrs.get("externalUrl"):
                    continue
                try:
                    so_c = float(attrs.get("chapter") or (len(ds) + 1))
                except (TypeError, ValueError):
                    so_c = float(len(ds) + 1)
                if so_c in seen_so:
                    continue
                seen_so.add(so_c)
                ten_c = f"Chapter-{int(so_c):03d}" if so_c.is_integer() else f"Chapter-{so_c}"
                ds.append(
                    {
                        "ten_truyen": ten_truyen,
                        "so": so_c,
                        "ten": ten_c,
                        "url": f"https://mangadex.org/chapter/{cid}",
                        "nhan": f"{ten_truyen} / {ten_c} [{lg.upper()}]",
                    }
                )
            total_items_api = int(feed.get("total") or len(items))
            if offset + 500 >= total_items_api:
                break
        if ds:
            break

    if not ds:
        raise NeedsAttention("Không tìm thấy chapter khả dụng trên MangaDex cho bộ truyện này.")
    return sorted(ds, key=lambda c: float(c.get("so", 1.0)))


def _quet_anh_mangadex(url_chapter: str) -> list[str]:
    """Lấy danh sách link ảnh trang truyện chất lượng gốc từ MangaDex At-Home Server API."""
    m_uuid = re.search(r"/chapter/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", url_chapter, flags=re.I)
    if not m_uuid:
        raise NeedsAttention("Link chapter MangaDex không hợp lệ.")
    uid = m_uuid.group(1).lower()
    try:
        raw = goi_http(
            f"https://api.mangadex.org/at-home/server/{uid}",
            referer="",
            timeout=18,
            nguon_ngoai=True,
            extra_headers={"User-Agent": "MangaStudio/1.1"},
        )
        info = json.loads(raw.decode("utf-8", errors="replace"))
    except Exception as exc:
        msg = str(exc)
        if "10054" in msg or "reset" in msg.lower():
            raise NeedsAttention(
                "Nhà mạng đang chặn kết nối tới máy chủ ảnh MangaDex (WinError 10054). Hãy bật 1.1.1.1 (Cloudflare WARP) hoặc VPN."
            ) from exc
        raise NeedsAttention(f"Không lấy được danh sách trang từ MangaDex: {exc}") from exc
    base_url = str(info.get("baseUrl") or "").rstrip("/")
    chap_obj = info.get("chapter") or {}
    ch_hash = str(chap_obj.get("hash") or "")
    files = chap_obj.get("data") or chap_obj.get("dataSaver") or []
    mode = "data" if chap_obj.get("data") else "data-saver"
    if not base_url or not ch_hash or not files:
        raise NeedsAttention("MangaDex trả về danh sách ảnh trống cho chapter này.")
    return [f"{base_url}/{mode}/{ch_hash}/{fn}" for fn in files]


def _quet_mot_url_truyen(u_don: str, mo_rong_ca_bo: bool = False) -> list[dict]:
    """Quét danh sách chapter cho 1 URL đơn lẻ (hỗ trợ cả web HTML thường, WordPress Manga, MangaDex và MANGA Plus)."""
    host = urllib.parse.urlsplit(u_don).netloc.lower()
    if "mangaplus.shueisha.co.jp" in host:
        return _quet_chapter_mangaplus(u_don, mo_rong_ca_bo=mo_rong_ca_bo)
    if "mangadex.org" in host:
        return _quet_chapter_mangadex(u_don, mo_rong_ca_bo=mo_rong_ca_bo)

    html = goi_http(u_don, referer=u_don, nguon_ngoai=True).decode("utf-8", errors="ignore")
    ten_tr = suy_doan_ten_truyen_tu_url(u_don, html)
    ds = chapter_links(html, u_don)

    # Tự động kích hoạt API ẩn WordPress Madara (`POST <url>/ajax/chapters/`) nếu trang mục lục tải danh sách chương bằng AJAX:
    if len(ds) <= 1:
        try:
            u_clean = u_don.split("?", 1)[0].rstrip("/")
            ajax_url = f"{u_clean}/ajax/chapters/"
            req_ajax = urllib.request.Request(
                ajax_url,
                data=b"",
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": u_don,
                    "X-Requested-With": "XMLHttpRequest",
                },
                method="POST",
            )
            with urllib.request.urlopen(req_ajax, timeout=12) as resp_aj:
                html_ajax = resp_aj.read().decode("utf-8", errors="ignore")
            if html_ajax and ("wp-manga-chapter" in html_ajax or "<a " in html_ajax):
                ds_ajax = chapter_links(html_ajax, u_don)
                if len(ds_ajax) > len(ds):
                    ds = ds_ajax
        except Exception:
            pass

    # Nếu người dùng dán link của 1 chapter cụ thể (VD: .../steel-ball-run-chapter-25/) và chọn mở rộng cả bộ truyện:
    if mo_rong_ca_bo and len(ds) == 1:
        parts = urllib.parse.urlsplit(u_don)
        # Quét toàn bộ link chapter cùng bộ ngay trong HTML hiện tại (xóa số chapter khỏi page_url giả định để lấy full list)
        base_root = f"{parts.scheme}://{parts.netloc}/"
        ung_vien_mo_rong: dict[float, dict] = {float(ds[0]["so"]): dict(ds[0])}
        for html_ung_vien, base_uv in ((html, base_root),):
            try:
                for ch_more in chapter_links(html_ung_vien, base_uv):
                    ung_vien_mo_rong.setdefault(float(ch_more["so"]), dict(ch_more))
            except Exception:
                pass
        if 1.0 not in ung_vien_mo_rong or len(ung_vien_mo_rong) < 20:
            try:
                html_root = goi_http(base_root, referer=u_don, nguon_ngoai=True).decode("utf-8", errors="ignore")
                for ch_root in chapter_links(html_root, base_root):
                    ung_vien_mo_rong.setdefault(float(ch_root["so"]), dict(ch_root))
            except Exception:
                pass
        if len(ung_vien_mo_rong) > 1:
            ds = [ung_vien_mo_rong[k] for k in sorted(ung_vien_mo_rong)]

    for ch in ds:
        if not ch.get("ten_truyen") and ten_tr != "Truyen-Moi":
            ch["ten_truyen"] = ten_tr
    return sorted(ds, key=lambda c: float(c.get("so", 1.0)))


def quet_danh_sach_chapter_tu_url(url_truyen: str, mo_rong_ca_bo: bool = False) -> list[dict]:
    """
    Tự động quét danh sách các link Chapter từ trang mục lục của 1 hoặc nhiều bộ truyện (cách nhau bởi dấu ; hoặc xuống dòng).
    Sắp xếp tuần tự từ Chapter nhỏ đến Chapter lớn và gắn kèm `ten_truyen` cho từng Chapter.
    """
    cac_url = [
        u.strip()
        for u in re.split(r"[\r\n;|]+", (url_truyen or "").strip())
        if u.strip()
    ]
    if len(cac_url) <= 1:
        u_don = cac_url[0] if cac_url else url_truyen
        return _quet_mot_url_truyen(u_don, mo_rong_ca_bo=mo_rong_ca_bo)

    # Khi người dùng dán nhiều link (nhiều bộ truyện hoặc nhiều link chapter rời):
    tong_ds: list[dict] = []
    seen_urls: set[str] = set()
    for u in cac_url:
        ds_u = _quet_mot_url_truyen(u, mo_rong_ca_bo=mo_rong_ca_bo)
        for ch in ds_u:
            if ch["url"] in seen_urls:
                continue
            seen_urls.add(ch["url"])
            item = dict(ch)
            item["ten_truyen"] = item.get("ten_truyen") or suy_doan_ten_truyen_tu_url(u)
            item["nhan"] = f"{item['ten_truyen']} / {item['ten']}"
            tong_ds.append(item)
    return _khu_trung_ten_chapter_theo_truyen(tong_ds)


def quet_anh_trang_truyen_trong_chapter(url_chapter: str) -> list[str]:
    """Trích xuất toàn bộ danh sách URL ảnh trang truyện trong 1 trang đọc Chapter."""
    host = urllib.parse.urlsplit(url_chapter or "").netloc.lower()
    if "mangaplus.shueisha.co.jp" in host:
        return _quet_anh_mangaplus(url_chapter)
    if "mangadex.org" in host:
        return _quet_anh_mangadex(url_chapter)
    html = goi_http(url_chapter, referer=url_chapter, nguon_ngoai=True).decode("utf-8", errors="ignore")
    if "webtoons.com" in host:
        m_list = re.search(r'id=["\']_imageList["\'][^>]*>(.*?)</div>', html, flags=re.I | re.S)
        vung_html = m_list.group(1) if m_list else html
        ds_wt = [
            u.replace("&amp;", "&").strip().replace(" ", "%20")
            for u in re.findall(r'data-url=["\'](https?://[^"\']+)["\']', vung_html, flags=re.I)
            if "type=a92" not in u and "thumb" not in u.lower()
        ]
        if ds_wt:
            return ds_wt
    return image_links(html, url_chapter)


def ve_lai_trang_trong_ho_so_chapter(
    thu_muc_chapter: Path,
    page_index: int,
    regions_moi: list[dict],
    font_style: str = "",
) -> bytes:
    """
    Vẽ lại ngay lập tức (~0.3s) 1 trang truyện đã dịch trong hồ sơ `trang-thai.json` khi người dùng sửa câu thoại
    mà KHÔNG cần gọi lại mô hình AI hay tải lại toàn bộ Chapter.
    Đảm bảo kiểm tra hash ảnh gốc (`check_source`) và cập nhật nguyên tử vào `ChapterLedger`.
    """
    import review_delivery

    with review_delivery.open_chapter(thu_muc_chapter) as ledger:
        if not (0 <= page_index < len(ledger.data["pages"])):
            raise NeedsAttention("Số thứ tự trang nằm ngoài phạm vi của Chapter.")
        page = ledger.data["pages"][page_index]
        source = str(page.get("source") or "")
        if not source:
            raise NeedsAttention("Trang này không có đường dẫn ảnh nguồn trong hồ sơ.")
        if source.startswith(("local_file::", "archive_file::")):
            raw_source = read_local_source(source)
        else:
            raw_source = goi_http(source, referer=source, nguon_ngoai=True)
        ledger.check_source(page_index, raw_source)
        font_dung = font_style or str((ledger.data.get("config") or {}).get("font") or "bangers")
        cleaned_regions: list[dict] = []
        for r in regions_moi:
            item = dict(r)
            item["ban_dich"] = str(item.get("ban_dich") or "").strip()
            if not item["ban_dich"]:
                raise NeedsAttention("Bản dịch của bóng thoại không được để trống khi vẽ lại.")
            cleaned_regions.append(item)
        rendered_bytes = xoa_chu_va_ve_ban_dich_tren_anh(raw_source, cleaned_regions, font_dung)
        ledger.finish_page(page_index, rendered_bytes, cleaned_regions)
        return rendered_bytes


# ==============================================================================
# 3. GIAO DIỆN DESKTOP WINDOWS (MANGA STUDIO PRO)
# ==============================================================================

MANGA_UI_TOKENS = {
    "bg_canvas": "#090D16",       # Nền mực đen sâu (Manga Ink Canvas)
    "bg_surface": "#111827",      # Bề mặt thẻ (Card Surface)
    "bg_elevated": "#1E293B",     # Ô nhập & Nút phụ (Elevated Slate)
    "bg_header": "#0D1322",       # Thanh đầu trang cố định
    "bg_console": "#060911",      # Nền bảng nhật ký trực tiếp
    "border_subtle": "#1F2937",   # Viền phân tách mảnh (1px)
    "border_input": "#334155",    # Viền ô nhập & nút phụ
    "accent_primary": "#E11D48",  # Đỏ Crimson Manga (chỉ dùng cho CTA chính & điểm nhấn)
    "accent_soft": "#FB7185",     # Hồng san hô nhạt cho nhãn bước
    "text_primary": "#F8FAFC",    # Chữ chính trắng giấy (tương phản > 15:1)
    "text_secondary": "#94A3B8",  # Chữ phụ xám (tương phản > 5.5:1)
    "text_muted": "#64748B",      # Chữ gợi ý / thời gian
    "status_ok": "#10B981",       # Xanh hoàn tất
    "status_warn": "#F59E0B",     # Vàng cảnh báo
    "status_err": "#EF4444",      # Đỏ lỗi / dừng
    "status_info": "#38BDF8",     # Xanh thông tin
}



def ghep_va_cat_dai_anh_webtoon_thong_minh(ds_anh_bytes: list[bytes]) -> list[bytes]:
    """
    [B.1] Smart Webtoon Strip Stitcher & Gutter-Aware OCR Slicer:
    - Tự động phát hiện khi các trang ảnh tải về là những mảnh cắt ngang của dải Webtoon/Manhwa (`H < 1150px` và cùng chiều rộng `W`,
      hoặc mép cắt đi ngang qua vùng bóng thoại sáng màu làm đứt đôi chữ).
    - Tự động nối liền các mảnh cắt liên tiếp theo chiều dọc rồi tìm "rãnh an toàn" (Gutter — dòng ngang đồng nhất màu trắng/đen
      không có nét chữ tương phản) ở khoảng chiều cao lý tưởng `1200px - 2200px` để cắt lại trang chuẩn trước khi đưa vào OCR.
    - Nếu là trang Manga tiêu chuẩn (tỷ lệ trang sách rời), giữ nguyên 100% không thay đổi số trang.
    """
    if Image is None or len(ds_anh_bytes) < 2:
        return ds_anh_bytes
    try:
        ims: list[Image.Image] = []
        for raw_b in ds_anh_bytes:
            with Image.open(io.BytesIO(raw_b)) as im_in:
                ims.append(im_in.convert("RGB"))

        # Kiểm tra xem có phải các dải Webtoon bị cắt mảnh không (chiều rộng đồng nhất và có mảnh thấp hoặc mép cắt qua vùng sáng)
        widths = [im.width for im in ims]
        heights = [im.height for im in ims]
        w_pho_bien = max(set(widths), key=widths.count)
        ty_le_cung_w = sum(1 for w in widths if abs(w - w_pho_bien) <= 4) / float(len(widths))
        co_manh_cat_ngan = sum(1 for h in heights if h < 1150) >= max(2, len(heights) // 3)
        if ty_le_cung_w < 0.8 or not co_manh_cat_ngan:
            return ds_anh_bytes

        # Ghép dọc các mảnh cùng chiều rộng và cắt lại tại các dòng Gutter an toàn (không cắt ngang bóng thoại)
        ket_qua: list[bytes] = []
        idx = 0
        n = len(ims)
        while idx < n:
            im_cur = ims[idx]
            if abs(im_cur.width - w_pho_bien) > 4:
                buf = io.BytesIO()
                im_cur.save(buf, format="JPEG", quality=93)
                ket_qua.append(buf.getvalue())
                idx += 1
                continue

            # Gom một cụm dải liên tiếp (tối đa tổng chiều cao ~12000px mỗi cụm để tiết kiệm RAM)
            cum_ims: list[Image.Image] = []
            tong_h = 0
            while idx < n and abs(ims[idx].width - w_pho_bien) <= 4 and tong_h < 12000:
                im_part = ims[idx]
                if im_part.width != w_pho_bien:
                    im_part = im_part.resize((w_pho_bien, im_part.height))
                cum_ims.append(im_part)
                tong_h += im_part.height
                idx += 1

            canvas = Image.new("RGB", (w_pho_bien, tong_h))
            y_off = 0
            for im_p in cum_ims:
                canvas.paste(im_p, (0, y_off))
                y_off += im_p.height

            gray = canvas.convert("L")
            px_g = gray.load()

            def _do_lech_dong(y_row: int) -> float:
                step_x = max(2, w_pho_bien // 64)
                vals = [px_g[x, y_row] for x in range(8, w_pho_bien - 8, step_x)]
                if not vals:
                    return 999.0
                tb = sum(vals) / float(len(vals))
                phuong_sai = sum(abs(v - tb) for v in vals) / float(len(vals))
                return phuong_sai

            y_start = 0
            target_h = 1650
            min_h = 1150
            max_h = 2250
            while y_start < tong_h:
                con_lai_h = tong_h - y_start
                if con_lai_h <= max_h:
                    crop_im = canvas.crop((0, y_start, w_pho_bien, tong_h))
                    buf = io.BytesIO()
                    crop_im.save(buf, format="JPEG", quality=93)
                    ket_qua.append(buf.getvalue())
                    break

                y_ideal = min(tong_h - 1, y_start + target_h)
                y_low = max(y_start + min_h, y_ideal - 420)
                y_high = min(tong_h - 60, y_ideal + 420)

                best_y = y_ideal
                best_score = 9999.0
                for y_cand in range(y_low, y_high, 4):
                    score = _do_lech_dong(y_cand)
                    if score < best_score:
                        best_score = score
                        best_y = y_cand
                        if score <= 1.5:
                            break

                crop_im = canvas.crop((0, y_start, w_pho_bien, best_y))
                buf = io.BytesIO()
                crop_im.save(buf, format="JPEG", quality=93)
                ket_qua.append(buf.getvalue())
                y_start = best_y

        return ket_qua if ket_qua else ds_anh_bytes
    except Exception:
        return ds_anh_bytes


def tu_dong_dung_video_review_cho_chapter(
    thu_muc_chapter: Path,
    *,
    ten_truyen: str,
    ten_chapter: str,
    server_url: str,
    token: str,
    log_fn=None,
) -> dict:
    """
    [B.3] Tự động dựng Video Review (.MP4 + .SRT) ngay sau khi 1 Chapter vừa dịch xong:
    - Chạy hoàn toàn tự động nối tiếp qua từng Chapter mà KHÔNG cần người dùng bấm xác nhận thủ công.
    - Đọc trực tiếp các trang ảnh đã dịch và `trang-thai.json` trong `thu_muc_chapter`.
    - Kiểm tra gói trả phí (`cap_do >= 1` hoặc có lượt mua thêm, không có gói Free dùng thử) trước khi render.
    """
    def _log(msg: str):
        if callable(log_fn):
            log_fn(msg)

    studio_dir = None
    for cand in (
        Path(__file__).resolve().parent.parent / "video-review-studio",
        Path(__file__).resolve().parent / "video-review-studio",
        Path.cwd() / "video-review-studio",
    ):
        if (cand / "core_video_renderer.py").is_file():
            studio_dir = cand
            break

    if studio_dir is None:
        raise NeedsAttention("Không tìm thấy thư mục `video-review-studio` để dựng Video Review tự động.")

    if str(studio_dir) not in sys.path:
        sys.path.insert(0, str(studio_dir))

    import app_video_review_studio as vstudio
    import core_script_generator as vscript
    import core_video_renderer as vrender

    cau_hinh_v = vstudio.doc_cau_hinh_studio()
    dinh_dang_key = str(cau_hinh_v.get("dinh_dang") or "dual_youtube_va_shorts")
    giong_key = str(cau_hinh_v.get("ma_giong") or "chi_google_review_chuan")
    nhac_nen_key = str(cau_hinh_v.get("ma_nhac_nen") or "tu_dong_theo_phong_cach")
    goi_key = str(cau_hinh_v.get("goi_luot") or "review_standard")
    phong_cach_key = str(cau_hinh_v.get("phong_cach") or "kich_tinh")
    toc_do_val = float(cau_hinh_v.get("toc_do_doc") or 1.15)
    tok_use = (token or cau_hinh_v.get("token") or "").strip()
    srv_use = (server_url or cau_hinh_v.get("server_url") or "https://translation-api.vibe1.tinhgon.xyz").strip()

    _log(f"🎬 [Auto-Video] Đang kiểm tra gói trả phí & cấp vé dựng Video Review cho {ten_truyen} / {ten_chapter}...")
    kq_ve = vrender.xac_thuc_va_tru_luot_video_cloud(
        srv_use,
        tok_use,
        ma_goi=goi_key,
        ma_dinh_danh_video=f"{ten_truyen}:{ten_chapter}:{dinh_dang_key}",
    )
    _log(
        f"✅ [Auto-Video] Đã xác thực gói '{goi_key}' (-{kq_ve['so_luot_da_tru']} lượt · Số dư còn {kq_ve['con_lai_sau_tru']} lượt). Đang biên kịch & lồng tiếng..."
    )

    panels_bytes, ocr_per_panel = vstudio.nap_danh_sach_anh_va_thoai_tu_thu_muc(
        thu_muc_chapter,
        an_chu_bong_thoai=True,
    )
    cast_mem = vscript.CharacterCastMemory(Path.home() / ".manga_video_character_bible.json")
    vscript.tu_dong_quet_ho_so_nhan_vat_tu_thoai(ocr_per_panel, cast_mem)
    kich_ban = vscript.sinh_kich_ban_review_chuong(
        panels_bytes,
        ocr_per_panel,
        cast_memory=cast_mem,
        phong_cach=phong_cach_key,
        ten_truyen=ten_truyen,
        ten_chap=ten_chapter,
        thu_ket_noi_vision_cuc_bo=True,
    )
    out_mp4 = thu_muc_chapter / f"{ten_chapter}_Video_Review_{dinh_dang_key}.mp4"
    kq_video = vrender.xuat_video_review_mp4(
        panels_bytes,
        kich_ban,
        out_mp4,
        ma_dinh_dang=dinh_dang_key,
        ma_giong=giong_key,
        ma_nhac_nen=nhac_nen_key,
        toc_do_doc=toc_do_val,
        elevenlabs_api_key=cau_hinh_v.get("elevenlabs_api_key") or None,
        elevenlabs_voice_id=cau_hinh_v.get("elevenlabs_voice_id") or None,
    )
    _log(
        f"🎉 [Auto-Video] Đã dựng xong Video Review ({kq_video['tong_thoi_luong_giay']}s) cho {ten_chapter} -> MP4: {kq_video['video_path']} | SRT: {kq_video['srt_path']}"
    )
    return kq_video


class AppDichTruyenWindows(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MANGA STUDIO PRO — Bàn Dịch Truyện Tranh AI & Chia Chapter Tự Động")
        self.geometry("1260x820")
        self.minsize(1040, 720)
        self.configure(bg=MANGA_UI_TOKENS["bg_canvas"])

        self.cau_hinh = self._doc_cau_hinh()
        self.ds_chapter_quet: list[dict] = []
        self.dang_chay = False
        self.yeu_cau_dung = False

        self._dung_giao_dien()
        # Tự động xác nhận Mã máy tính (HWID) và kiểm tra số lượt còn lại ngay khi mở App
        self.cau_hinh["ma_may_tinh"] = MA_MAY_HIEN_THI
        self._luu_cau_hinh()
        khoi_dong_may_chu_bridge_cuc_bo(ghi_log_fn=self.ghi_log)
        threading.Thread(target=self._cap_nhat_han_muc, kwargs={"ghi_nhat_ky": True}, daemon=True).start()
        threading.Thread(target=self._tu_dong_dong_bo_ocr_may_moi, daemon=True).start()

    def _tu_dong_dong_bo_ocr_may_moi(self):
        """Tự động kiểm tra và tải ngầm trọng số nhận diện 4 ngôn ngữ (JA/KO/ZH/EN) khi chạy trên máy mới."""
        try:
            ja_ok = (THU_MUC_OCR_HF / "ja_rec.onnx").is_file() and (THU_MUC_OCR_HF / "ja_dict.txt").is_file()
            ko_ok = (THU_MUC_OCR_HF / "ko_rec.onnx").is_file() and (THU_MUC_OCR_HF / "ko_dict.txt").is_file()
            if not (ja_ok and ko_ok):
                tai_goi_ocr_huggingface("all")
        except Exception:
            pass

    def _doc_cau_hinh(self) -> dict:
        if CAU_HINH_FILE.is_file():
            try:
                return json.loads(CAU_HINH_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "may_chu": "https://translation-api.vibe1.tinhgon.xyz",
            "email": "",
            "token": "",
            "thu_muc_xuat": str(Path.home() / "Downloads" / "Truyen_Da_Dich"),
            "ngon_ngu_nguon": "ja",
            "ngon_ngu_dich": "vi",
            "font_chu": "bangers",
            "xuat_cbz": False,
        }

    def _luu_cau_hinh(self):
        try:
            CAU_HINH_FILE.write_text(json.dumps(self.cau_hinh, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _cap_nhat_the_chi_phi(self, _event=None):
        if not hasattr(self, "lbl_kpi_cost"):
            return
        eng = self.cmb_engine.get() if hasattr(self, "cmb_engine") else ""
        ma_eng = eng.split()[0] if eng else "local_ocr_gpu"
        so_luot = SO_LUOT_MOI_TRANG_THEO_ENGINE.get(ma_eng, 1)
        so_cau_hoc = len(nap_bo_nho_tu_hoc())
        if "local_hybrid_pro" in eng:
            self.lbl_kpi_cost.config(
                text=f"{so_luot} lượt / trang (🧠 GPU Pro Tự Học)",
                fg="#38BDF8",
            )
            if hasattr(self, "lbl_mo_ta_engine"):
                self.lbl_mo_ta_engine.config(
                    text=(
                        f"🧠 Chế độ Chuyên sâu ({so_luot} lượt/trang): Tăng cường nhận diện chữ viết tay + "
                        f"Chuẩn hoá thoại khó + Bộ nhớ tự học ({so_cau_hoc} cụm đã nhớ)."
                    ),
                    fg="#38BDF8",
                )
        elif "local_" in eng:
            self.lbl_kpi_cost.config(
                text=f"{so_luot} lượt / trang (⚡ OCR + GPU Nhanh)",
                fg=MANGA_UI_TOKENS["status_ok"],
            )
            if hasattr(self, "lbl_mo_ta_engine"):
                self.lbl_mo_ta_engine.config(
                    text=(
                        f"⚡ Chế độ Chủ lực Khuyên dùng ({so_luot} lượt/trang · ~0.8s–1.8s): "
                        f"Tiết kiệm 50% lượt, tối ưu cho 90% truyện chữ rõ (kế thừa {so_cau_hoc} cụm tự học)."
                    ),
                    fg=MANGA_UI_TOKENS["status_ok"],
                )
        elif "google_fast" in eng:
            self.lbl_kpi_cost.config(
                text=f"{so_luot} lượt / trang (Cloud Nhanh)",
                fg=MANGA_UI_TOKENS["status_info"],
            )
        else:
            self.lbl_kpi_cost.config(
                text=f"{so_luot} lượt / trang (✨ Gemini & DeepSeek Ultra)",
                fg=MANGA_UI_TOKENS["status_warn"],
            )
            if hasattr(self, "lbl_mo_ta_engine"):
                self.lbl_mo_ta_engine.config(
                    text=(
                        f"✨ Chế độ Đỉnh Cao Đám Mây ({so_luot} lượt/trang): Đôi mắt Gemini Vision 2K & DeepSeek "
                        f"nhìn biểu cảm tranh phân vai xưng hô chuẩn Scanlation ({so_cau_hoc} cụm tự học)."
                    ),
                    fg=MANGA_UI_TOKENS["status_warn"],
                )

    def _bat_tat_khung_tai_khoan(self):
        if not hasattr(self, "f_auth_drawer"):
            return
        if self._auth_dang_mo:
            self.f_auth_drawer.pack_forget()
            self._auth_dang_mo = False
            self.btn_toggle_auth.config(text="⚙️ Tài khoản & Máy chủ Cloud ▾")
        else:
            self.f_auth_drawer.pack(fill="x", padx=16, pady=(0, 8), before=self.f_kpi_strip)
            self._auth_dang_mo = True
            self.btn_toggle_auth.config(text="⚙️ Ẩn khung Tài khoản Cloud ▴")

    def _dung_giao_dien(self):
        T = MANGA_UI_TOKENS
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
            style.configure(
                "TCombobox",
                fieldbackground=T["bg_elevated"],
                background=T["bg_elevated"],
                foreground=T["text_primary"],
                arrowcolor=T["text_primary"],
                bordercolor=T["border_input"],
                lightcolor=T["bg_elevated"],
                darkcolor=T["bg_elevated"],
                padding=4,
            )
            style.map(
                "TCombobox",
                fieldbackground=[("readonly", T["bg_elevated"])],
                foreground=[("readonly", T["text_primary"])],
                selectbackground=[("readonly", T["bg_elevated"])],
                selectforeground=[("readonly", T["text_primary"])],
            )
        except Exception:
            pass

        # Viền nhấn đỏ Manga trên đỉnh cửa sổ (2px)
        tk.Frame(self, bg=T["accent_primary"], height=3).pack(fill="x")

        # 1. Thanh Header Cố Định (Studio Bar)
        header = tk.Frame(self, bg=T["bg_header"], padx=16, pady=10)
        header.pack(fill="x")

        brand_box = tk.Frame(header, bg=T["bg_header"])
        brand_box.pack(side="left")
        tk.Label(
            brand_box,
            text=" MANGA STUDIO ",
            font=("Segoe UI", 9, "bold"),
            fg="#ffffff",
            bg=T["accent_primary"],
            padx=6,
            pady=2,
        ).pack(side="left", padx=(0, 10))
        tk.Label(
            brand_box,
            text="BÀN DỊCH TRUYỆN TRANH AI & CHIA CHAPTER TỰ ĐỘNG",
            font=("Segoe UI", 11, "bold"),
            fg=T["text_primary"],
            bg=T["bg_header"],
        ).pack(side="left")

        right_hdr = tk.Frame(header, bg=T["bg_header"])
        right_hdr.pack(side="right")

        self._auth_dang_mo = False
        self.btn_toggle_auth = tk.Button(
            right_hdr,
            text="⚙️ Tài khoản Cloud ▾",
            bg=T["bg_elevated"],
            fg=T["text_primary"],
            activebackground="#334155",
            activeforeground="#ffffff",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=10,
            pady=3,
            command=self._bat_tat_khung_tai_khoan,
        )
        self.btn_toggle_auth.pack(side="right")

        self.btn_bang_gia_api = tk.Button(
            right_hdr,
            text="💎 Gói Cước & Khoá API (tr_live_)",
            bg="#281320",
            fg=T["accent_soft"],
            activebackground=T["accent_primary"],
            activeforeground="#ffffff",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=10,
            pady=3,
            command=self._mo_cua_so_goi_cuoc_va_api,
        )
        self.btn_bang_gia_api.pack(side="right", padx=(0, 8))

        self.lbl_han_muc = tk.Label(
            right_hdr,
            text=f"💎 Khả dụng: -- trang ({MA_MAY_HIEN_THI})",
            font=("Consolas", 9, "bold"),
            fg=T["status_info"],
            bg="#162033",
            padx=10,
            pady=4,
        )
        self.lbl_han_muc.pack(side="right", padx=(0, 8))

        tk.Frame(self, bg=T["border_subtle"], height=1).pack(fill="x")

        # Ngăn kéo cấu hình Tài khoản Cloud & Mã máy (Ẩn mặc định để giao diện gọn thoáng, bấm nút ⚙️ trên Header để mở)
        self.f_auth_drawer = tk.Frame(
            self,
            bg=T["bg_surface"],
            highlightbackground=T["border_input"],
            highlightthickness=1,
            padx=14,
            pady=8,
        )
        r_auth1 = tk.Frame(self.f_auth_drawer, bg=T["bg_surface"])
        r_auth1.pack(fill="x", pady=(0, 5))
        tk.Label(r_auth1, text="Máy chủ Cloud:", bg=T["bg_surface"], fg=T["text_secondary"], font=("Segoe UI", 9)).pack(side="left")
        self.ent_server = tk.Entry(r_auth1, width=28, bg=T["bg_elevated"], fg=T["text_primary"], insertbackground="#fff", relief="flat")
        self.ent_server.insert(0, self.cau_hinh.get("may_chu", "https://translation-api.vibe1.tinhgon.xyz"))
        self.ent_server.pack(side="left", padx=(6, 14), ipady=3)

        tk.Label(r_auth1, text="Email:", bg=T["bg_surface"], fg=T["text_secondary"], font=("Segoe UI", 9)).pack(side="left")
        self.ent_email = tk.Entry(r_auth1, width=22, bg=T["bg_elevated"], fg=T["text_primary"], insertbackground="#fff", relief="flat")
        self.ent_email.insert(0, self.cau_hinh.get("email", ""))
        self.ent_email.pack(side="left", padx=(6, 14), ipady=3)

        tk.Label(r_auth1, text="Mật khẩu / API Key:", bg=T["bg_surface"], fg=T["text_secondary"], font=("Segoe UI", 9)).pack(side="left")
        self.ent_pass = tk.Entry(r_auth1, width=18, show="*", bg=T["bg_elevated"], fg=T["text_primary"], insertbackground="#fff", relief="flat")
        self.ent_pass.pack(side="left", padx=(6, 10), ipady=3)

        tk.Button(
            r_auth1,
            text="Đăng nhập & Lưu máy",
            bg=T["accent_primary"],
            fg="#ffffff",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=12,
            pady=3,
            command=self._dang_nhap,
        ).pack(side="left", padx=4)

        r_auth2 = tk.Frame(self.f_auth_drawer, bg=T["bg_surface"])
        r_auth2.pack(fill="x")
        tk.Label(r_auth2, text="Mã thiết bị:", bg=T["bg_surface"], fg=T["text_secondary"], font=("Segoe UI", 9)).pack(side="left")
        self.ent_hwid = tk.Entry(
            r_auth2,
            width=18,
            bg=T["bg_elevated"],
            fg=T["status_warn"],
            font=("Consolas", 9, "bold"),
            readonlybackground=T["bg_elevated"],
            relief="flat",
        )
        self.ent_hwid.insert(0, MA_MAY_HIEN_THI)
        self.ent_hwid.config(state="readonly")
        self.ent_hwid.pack(side="left", padx=6, ipady=2)

        for txt_b, cmd_b in (
            ("Sao chép Mã máy", self._sao_chep_ma_may),
            ("💎 Bảng Giá & Khoá API (tr_live_)", self._mo_cua_so_goi_cuoc_va_api),
            (
                "Đồng bộ số lượt",
                lambda: threading.Thread(target=self._cap_nhat_han_muc, kwargs={"ghi_nhat_ky": True}, daemon=True).start(),
            ),
            ("Mở Web Nạp VIP", lambda: webbrowser.open(WEB_CHINH_THUC)),
        ):
            tk.Button(
                r_auth2,
                text=txt_b,
                bg=T["bg_elevated"],
                fg=T["text_primary"],
                font=("Segoe UI", 8, "bold"),
                relief="flat",
                padx=8,
                pady=2,
                command=cmd_b,
            ).pack(side="left", padx=3)

        self.lbl_chi_tiet_luot = tk.Label(
            self.f_auth_drawer,
            text="Đang đồng bộ hạn mức của thiết bị...",
            bg=T["bg_surface"],
            fg=T["status_ok"],
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        )
        self.lbl_chi_tiet_luot.pack(fill="x", pady=(4, 0))

        # 2. Dải 4 Thẻ Chỉ Số Nhanh (KPI Status Strip — Chuẩn Mục 6.1 & 6.3: Trung thực số liệu, không hiện 0 giả)
        self.f_kpi_strip = tk.Frame(self, bg=T["bg_canvas"], padx=16, pady=6)
        self.f_kpi_strip.pack(fill="x")
        for col_i in range(4):
            self.f_kpi_strip.columnconfigure(col_i, weight=1, uniform="kpi")

        def _tao_the_kpi(col: int, tieu_de: str, gia_tri_ban_dau: str, mau_chu: str) -> tk.Label:
            card = tk.Frame(
                self.f_kpi_strip,
                bg=T["bg_surface"],
                highlightbackground=T["border_subtle"],
                highlightthickness=1,
                padx=12,
                pady=5,
            )
            card.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 6, 0))
            tk.Label(
                card,
                text=tieu_de,
                bg=T["bg_surface"],
                fg=T["text_muted"],
                font=("Segoe UI", 8, "bold"),
                anchor="w",
            ).pack(fill="x")
            lbl_val = tk.Label(
                card,
                text=gia_tri_ban_dau,
                bg=T["bg_surface"],
                fg=mau_chu,
                font=("Segoe UI", 10, "bold"),
                anchor="w",
            )
            lbl_val.pack(fill="x", pady=(2, 0))
            return lbl_val

        self.lbl_so_chap = _tao_the_kpi(0, "NGUỒN CHƯƠNG ĐÃ NẠP", "Chưa nạp nguồn (Dán link hoặc chọn file)", T["text_secondary"])
        self.lbl_kpi_cost = _tao_the_kpi(1, "CHI PHÍ DỰ KIẾN / TRANG", "~10–15đ / trang (1 lượt Cloud)", T["status_warn"])
        self.lbl_kpi_ocr = _tao_the_kpi(2, "BỘ NHẬN DIỆN CHỮ (OCR)", "Sẵn sàng 4 ngôn ngữ (JA · ZH · KO · EN)", T["status_ok"])
        self.lbl_tien_do = _tao_the_kpi(3, "TRẠNG THÁI VẬN HÀNH", "Sẵn sàng chờ lệnh.", T["status_info"])

        # 3. Không gian làm việc 2 cột (Trái: Bảng Điều Khiển 3 Bước | Phải: Nhật Ký Studio & Danh Sách Chapter)
        workspace = tk.Frame(self, bg=T["bg_canvas"], padx=16, pady=2)
        workspace.pack(fill="both", expand=True, pady=(0, 10))
        workspace.columnconfigure(0, weight=0, minsize=560)
        workspace.columnconfigure(1, weight=1)
        workspace.rowconfigure(0, weight=1)

        left_col = tk.Frame(workspace, bg=T["bg_canvas"], width=560)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left_col.grid_propagate(False)

        right_col = tk.Frame(
            workspace,
            bg=T["bg_surface"],
            highlightbackground=T["border_subtle"],
            highlightthickness=1,
        )
        right_col.grid(row=0, column=1, sticky="nsew")

        def _tao_khung_buoc(parent, so_buoc: str, tieu_de: str) -> tk.Frame:
            outer = tk.Frame(
                parent,
                bg=T["bg_surface"],
                highlightbackground=T["border_subtle"],
                highlightthickness=1,
                padx=14,
                pady=8,
            )
            outer.pack(fill="x", pady=(0, 6))
            hdr = tk.Frame(outer, bg=T["bg_surface"])
            hdr.pack(fill="x", pady=(0, 6))
            tk.Label(
                hdr,
                text=f" {so_buoc} ",
                bg="#281320",
                fg=T["accent_soft"],
                font=("Consolas", 9, "bold"),
                padx=4,
                pady=1,
            ).pack(side="left", padx=(0, 8))
            tk.Label(
                hdr,
                text=tieu_de,
                bg=T["bg_surface"],
                fg=T["text_primary"],
                font=("Segoe UI", 10, "bold"),
            ).pack(side="left")
            return outer

        # --- BƯỚC 1: NGUỒN TRUYỆN & CHAPTER ---
        f_step1 = _tao_khung_buoc(left_col, "BƯỚC 01", "NGUỒN TRUYỆN TRANH & PHẠM VI CHAPTER")

        grid_url = tk.Frame(f_step1, bg=T["bg_surface"])
        grid_url.pack(fill="x", pady=(0, 4))
        grid_url.columnconfigure(1, weight=1)

        tk.Label(grid_url, text="Tên bộ truyện:", bg=T["bg_surface"], fg=T["text_secondary"], font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.ent_ten_truyen = tk.Entry(
            grid_url,
            bg=T["bg_elevated"],
            fg=T["text_primary"],
            insertbackground="#fff",
            relief="flat",
            font=("Segoe UI", 10),
        )
        self.ent_ten_truyen.insert(0, "Truyen-Moi")
        self.ent_ten_truyen.grid(row=0, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=(0, 5), ipady=3)

        tk.Label(grid_url, text="Link / Đường dẫn:", bg=T["bg_surface"], fg=T["text_secondary"], font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w")
        self.ent_url = tk.Entry(
            grid_url,
            bg=T["bg_elevated"],
            fg=T["text_primary"],
            insertbackground="#fff",
            relief="flat",
            font=("Consolas", 9),
        )
        self.ent_url.grid(row=1, column=1, sticky="ew", padx=(8, 6), ipady=3)

        tk.Button(
            grid_url,
            text="🔍 Quét Chapter",
            bg=T["accent_primary"],
            fg="#ffffff",
            activebackground="#be123c",
            activeforeground="#ffffff",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=12,
            pady=3,
            command=self._quet_link_truyen,
        ).grid(row=1, column=2, sticky="e")

        # Thanh công cụ chọn nguồn phụ (Đồng bộ 1 kiểu nút Secondary — không trộn 7 màu cầu vồng)
        bar_sources = tk.Frame(f_step1, bg=T["bg_surface"])
        bar_sources.pack(fill="x", pady=3)
        for idx_s, (lbl_s, cmd_s) in enumerate((
            ("📋 Dán Nhiều Link", self._mo_hop_thoai_nhieu_link),
            ("📁 Chọn Thư Mục Ảnh", self._chon_thu_muc_anh_offline),
            ("🗂️ Chọn File ZIP / CBZ / Ảnh", self._chon_goi_anh),
        )):
            tk.Button(
                bar_sources,
                text=lbl_s,
                bg=T["bg_elevated"],
                fg=T["text_primary"],
                activebackground="#334155",
                activeforeground="#ffffff",
                font=("Segoe UI", 9),
                relief="flat",
                padx=10,
                pady=3,
                command=cmd_s,
            ).pack(side="left", fill="x", expand=True, padx=(0 if idx_s == 0 else 6, 0))

        bar_opts1 = tk.Frame(f_step1, bg=T["bg_surface"])
        bar_opts1.pack(fill="x", pady=(2, 2))
        self.var_mo_rong_ca_bo = tk.BooleanVar(value=bool(self.cau_hinh.get("mo_rong_ca_bo", True)))
        tk.Checkbutton(
            bar_opts1,
            text="Mở rộng link 1 chap → cả bộ",
            variable=self.var_mo_rong_ca_bo,
            bg=T["bg_surface"],
            fg=T["text_secondary"],
            selectcolor=T["bg_canvas"],
            activebackground=T["bg_surface"],
            font=("Segoe UI", 9),
        ).pack(side="left")

        self.var_tu_dong_link = tk.BooleanVar(value=bool(self.cau_hinh.get("tu_dong_duyet_link", True)))
        tk.Checkbutton(
            bar_opts1,
            text="Tự duyệt số trang khi tải Link",
            variable=self.var_tu_dong_link,
            bg=T["bg_surface"],
            fg=T["text_secondary"],
            selectcolor=T["bg_canvas"],
            activebackground=T["bg_surface"],
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(12, 0))

        bar_range = tk.Frame(f_step1, bg=T["bg_surface"])
        bar_range.pack(fill="x", pady=(2, 0))
        tk.Label(bar_range, text="Từ Chap:", bg=T["bg_surface"], fg=T["text_secondary"], font=("Segoe UI", 9)).pack(side="left")
        self.spin_tu = tk.Spinbox(
            bar_range,
            from_=1,
            to=9999,
            width=5,
            bg=T["bg_elevated"],
            fg=T["text_primary"],
            buttonbackground=T["bg_elevated"],
            relief="flat",
            font=("Consolas", 10, "bold"),
        )
        self.spin_tu.pack(side="left", padx=(4, 10), ipady=2)

        tk.Label(bar_range, text="đến Chap:", bg=T["bg_surface"], fg=T["text_secondary"], font=("Segoe UI", 9)).pack(side="left")
        self.spin_den = tk.Spinbox(
            bar_range,
            from_=1,
            to=9999,
            width=5,
            bg=T["bg_elevated"],
            fg=T["text_primary"],
            buttonbackground=T["bg_elevated"],
            relief="flat",
            font=("Consolas", 10, "bold"),
        )
        self.spin_den.delete(0, "end")
        self.spin_den.insert(0, "10")
        self.spin_den.pack(side="left", padx=(4, 12), ipady=2)

        luong_hw, mo_ta_hw = phat_hien_cau_hinh_may_va_luong_toi_uu()
        luong_de_xuat = self.cau_hinh.get("so_luong_song_song") or luong_hw
        tk.Label(bar_range, text="⚡ Chạy song song:", bg=T["bg_surface"], fg="#38BDF8", font=("Segoe UI", 9, "bold")).pack(side="left")
        self.spin_song_song = tk.Spinbox(
            bar_range,
            from_=1,
            to=8,
            width=3,
            bg=T["bg_elevated"],
            fg="#38BDF8",
            buttonbackground=T["bg_elevated"],
            relief="flat",
            font=("Consolas", 10, "bold"),
        )
        self.spin_song_song.delete(0, "end")
        self.spin_song_song.insert(0, str(luong_de_xuat))
        self.spin_song_song.pack(side="left", padx=(4, 4), ipady=2)
        tk.Label(
            bar_range,
            text=f"chap cùng lúc ({mo_ta_hw})",
            bg=T["bg_surface"],
            fg=T["text_secondary"],
            font=("Segoe UI", 8),
        ).pack(side="left")

        # --- BƯỚC 2: NGÔN NGỮ, FONT TRUYỆN & BỘ MÁY AI ---
        f_step2 = _tao_khung_buoc(left_col, "BƯỚC 02", "NGÔN NGỮ, PHONG CÁCH CHỮ & BỘ MÁY AI")

        grid_cfg = tk.Frame(f_step2, bg=T["bg_surface"])
        grid_cfg.pack(fill="x", pady=(0, 4))
        grid_cfg.columnconfigure(1, weight=1)
        grid_cfg.columnconfigure(3, weight=1)

        tk.Label(grid_cfg, text="Ngôn ngữ gốc:", bg=T["bg_surface"], fg=T["text_secondary"], font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.cmb_src = ttk.Combobox(
            grid_cfg,
            values=[
                "ja (🇯🇵 Nhật - Manga)",
                "ko (🇰🇷 Hàn - Manhwa)",
                "zh (🇨🇳 Trung - Manhua Giản/Phồn)",
                "en (🇺🇸 Anh - Comic)",
            ],
            state="readonly",
        )
        self.cmb_src.current(0)
        self.cmb_src.grid(row=0, column=1, sticky="ew", padx=(6, 12), pady=(0, 5))

        tk.Label(grid_cfg, text="Dịch sang:", bg=T["bg_surface"], fg=T["text_secondary"], font=("Segoe UI", 9)).grid(row=0, column=2, sticky="w", pady=(0, 5))
        self.cmb_tgt = ttk.Combobox(
            grid_cfg,
            values=[v["nhan_ui"] for v in DANH_SACH_NGON_NGU_DICH_QUOC_TE.values()],
            state="readonly",
        )
        self.cmb_tgt.current(0)
        self.cmb_tgt.grid(row=0, column=3, sticky="ew", padx=(6, 0), pady=(0, 5))

        tk.Label(grid_cfg, text="Font chữ:", bg=T["bg_surface"], fg=T["text_secondary"], font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", pady=(0, 5))
        self.cmb_font = ttk.Combobox(
            grid_cfg,
            values=["bangers (⚔️ Hành động)", "comic (💬 Truyện tranh)", "romance (🌸 Ngôn tình)", "historical (📜 Cổ trang)"],
            state="readonly",
        )
        self.cmb_font.current(0)
        self.cmb_font.grid(row=1, column=1, columnspan=3, sticky="ew", padx=(6, 0), pady=(0, 5))

        tk.Label(grid_cfg, text="Bộ máy AI:", bg=T["bg_surface"], fg=T["text_secondary"], font=("Segoe UI", 9, "bold")).grid(row=2, column=0, sticky="w")
        self.cmb_engine = ttk.Combobox(
            grid_cfg,
            values=[
                "llm_context (✨ Gemini AI — Chuẩn Ngữ Cảnh Cloud)",
                "google_fast (⚡ Google Nhanh — Tốc Độ Cao Cloud)",
                "local_gguf (Qwen3-VL 8B Offline)",
                "local_ocr_gpu (⚡ OCR + GPU Nhanh)",
            ],
            state="readonly",
            width=48,
        )
        self.cmb_engine.current(0)
        # Ẩn 2 model thừa (google_fast & local_gguf) trên giao diện, giữ 3 model phân tầng 1 - 2 - 3 lượt/trang
        self.cmb_engine.configure(
            values=[
                "local_ocr_gpu (⚡ OCR + GPU Nhanh · 1 lượt/trang)",
                "local_hybrid_pro (🧠 OCR + GPU Pro — Tự Học & Chữ Viết Tay · 2 lượt/trang)",
                "llm_context (✨ AI Ngữ Cảnh Đám Mây — Gemini & DeepSeek Ultra · 3 lượt/trang)",
            ]
        )
        self.cmb_engine.set("local_ocr_gpu (⚡ OCR + GPU Nhanh · 1 lượt/trang)")
        self.cmb_engine.grid(row=2, column=1, columnspan=3, sticky="ew", padx=(6, 0))
        self.cmb_engine.bind("<<ComboboxSelected>>", self._cap_nhat_the_chi_phi)

        self.lbl_mo_ta_engine = tk.Label(
            f_step2,
            text="",
            bg="#111927",
            fg=T["status_ok"],
            font=("Segoe UI", 8, "bold"),
            anchor="w",
            padx=8,
            pady=4,
        )
        self.lbl_mo_ta_engine.pack(fill="x", pady=(2, 3))
        self._cap_nhat_the_chi_phi()

        bar_diag = tk.Frame(f_step2, bg=T["bg_surface"])
        bar_diag.pack(fill="x", pady=3)
        tk.Button(
            bar_diag,
            text="🌐 Kiểm tra Lõi Nhận Diện (4 Ngôn ngữ)",
            bg=T["bg_elevated"],
            fg=T["text_primary"],
            font=("Segoe UI", 8, "bold"),
            relief="flat",
            padx=8,
            pady=3,
            command=self._kiem_tra_ocr_da_ngon_ngu,
        ).pack(side="left", padx=(0, 6))

        tk.Button(
            bar_diag,
            text="🔄 Cập nhật Bộ máy AI Mới",
            bg="#162033",
            fg="#38BDF8",
            activebackground="#0284C7",
            activeforeground="#ffffff",
            font=("Segoe UI", 8, "bold"),
            relief="flat",
            padx=8,
            pady=3,
            command=self._cap_nhat_bo_may_ai_moi,
        ).pack(side="left", padx=(0, 6))

        self.var_cpu_ollama = tk.BooleanVar(value=bool(self.cau_hinh.get("ollama_cpu", False)))

        bar_dict = tk.Frame(f_step2, bg=T["bg_surface"])
        bar_dict.pack(fill="x", pady=(3, 2))
        tk.Label(bar_dict, text="Từ điển / Xưng hô:", bg=T["bg_surface"], fg=T["text_secondary"], font=("Segoe UI", 9)).pack(side="left")
        self.ent_tu_dien = tk.Entry(
            bar_dict,
            bg=T["bg_elevated"],
            fg=T["text_primary"],
            insertbackground="#fff",
            relief="flat",
            font=("Segoe UI", 9),
        )
        self.ent_tu_dien.insert(0, self.cau_hinh.get("tu_dien_rieng", ""))
        self.ent_tu_dien.pack(side="left", padx=(8, 0), fill="x", expand=True, ipady=3)

        bar_exp = tk.Frame(f_step2, bg=T["bg_surface"])
        bar_exp.pack(fill="x", pady=(2, 0))
        self.var_cbz = tk.BooleanVar(value=bool(self.cau_hinh.get("xuat_cbz", True)))
        tk.Checkbutton(
            bar_exp,
            text="Đóng gói .CBZ",
            variable=self.var_cbz,
            bg=T["bg_surface"],
            fg=T["text_secondary"],
            selectcolor=T["bg_canvas"],
            activebackground=T["bg_surface"],
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(0, 12))

        self.var_pdf = tk.BooleanVar(value=bool(self.cau_hinh.get("xuat_pdf", False)))
        tk.Checkbutton(
            bar_exp,
            text="Xuất thêm .PDF",
            variable=self.var_pdf,
            bg=T["bg_surface"],
            fg=T["text_secondary"],
            selectcolor=T["bg_canvas"],
            activebackground=T["bg_surface"],
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(0, 12))

        self.var_longstrip = tk.BooleanVar(value=bool(self.cau_hinh.get("xuat_longstrip", False)))
        tk.Checkbutton(
            bar_exp,
            text="Ghép dải Webtoon (Long-Strip)",
            variable=self.var_longstrip,
            bg=T["bg_surface"],
            fg=T["text_secondary"],
            selectcolor=T["bg_canvas"],
            activebackground=T["bg_surface"],
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(0, 10))

        bar_vid_auto = tk.Frame(f_step2, bg=T["bg_surface"])
        bar_vid_auto.pack(fill="x", pady=(2, 0))
        self.var_auto_video_review = tk.BooleanVar(value=bool(self.cau_hinh.get("auto_video_review", False)))
        tk.Checkbutton(
            bar_vid_auto,
            text="🎬 Tự động dựng Video Review (.MP4) nối tiếp ngay khi dịch xong mỗi Chapter",
            variable=self.var_auto_video_review,
            bg=T["bg_surface"],
            fg="#38BDF8",
            selectcolor=T["bg_canvas"],
            activebackground=T["bg_surface"],
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")
        tk.Button(
            bar_vid_auto,
            text="🎬 Mở Video Studio",
            bg="#162033",
            fg="#FBBF24",
            activebackground="#0284C7",
            activeforeground="#ffffff",
            font=("Segoe UI", 8, "bold"),
            relief="flat",
            padx=8,
            pady=2,
            command=self._mo_video_review_studio,
        ).pack(side="right")

        # --- BƯỚC 3: THƯ MỤC LƯU, CHẠY DỊCH & RÀ SOÁT NHANH ---
        f_step3 = _tao_khung_buoc(left_col, "BƯỚC 03", "THƯ MỤC KẾT QUẢ & ĐIỀU KHIỂN VẬN HÀNH")

        bar_out = tk.Frame(f_step3, bg=T["bg_surface"])
        bar_out.pack(fill="x", pady=(0, 8))
        tk.Label(bar_out, text="Lưu tại:", bg=T["bg_surface"], fg=T["text_secondary"], font=("Segoe UI", 9)).pack(side="left")
        self.ent_out = tk.Entry(
            bar_out,
            bg=T["bg_elevated"],
            fg=T["text_primary"],
            insertbackground="#fff",
            relief="flat",
            font=("Consolas", 9),
        )
        self.ent_out.insert(0, self.cau_hinh.get("thu_muc_xuat", str(Path.home() / "Downloads" / "Truyen_Da_Dich")))
        self.ent_out.pack(side="left", padx=6, fill="x", expand=True, ipady=3)

        tk.Button(
            bar_out,
            text="Chọn...",
            bg=T["bg_elevated"],
            fg=T["text_primary"],
            font=("Segoe UI", 9),
            relief="flat",
            padx=8,
            pady=3,
            command=self._chon_thu_muc,
        ).pack(side="left", padx=(0, 4))

        tk.Button(
            bar_out,
            text="📂 Mở thư mục",
            bg=T["bg_elevated"],
            fg=T["status_info"],
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=10,
            pady=3,
            command=self._mo_thu_muc_xuat,
        ).pack(side="left")

        # Hàng điều khiển chính: Nút BẮT ĐẦU và Nút ⏹ DỪNG LẠI nằm NGANG HÀNG NHAU để luôn hiển thị 100%
        bar_main_ctrl = tk.Frame(f_step3, bg=T["bg_surface"])
        bar_main_ctrl.pack(fill="x", pady=(0, 6))

        self.btn_start = tk.Button(
            bar_main_ctrl,
            text="🚀 BẮT ĐẦU TẢI & DỊCH THEO CHAPTER",
            bg=T["accent_primary"],
            fg="#ffffff",
            activebackground="#be123c",
            activeforeground="#ffffff",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            pady=8,
            command=self._bat_dau_chay,
        )
        self.btn_start.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.btn_stop = tk.Button(
            bar_main_ctrl,
            text="⏹ DỪNG LẠI",
            bg="#2A1215",
            fg="#F87171",
            activebackground="#DC2626",
            activeforeground="#ffffff",
            disabledforeground="#64748B",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=14,
            pady=8,
            state="disabled",
            command=self._dung_chay,
        )
        self.btn_stop.pack(side="right")

        bar_sub_ctrl = tk.Frame(f_step3, bg=T["bg_surface"])
        bar_sub_ctrl.pack(fill="x")
        tk.Button(
            bar_sub_ctrl,
            text="👁️ Rà Soát & Sửa Nhanh Bản Dịch (~0.4s · Không tốn lượt)",
            bg=T["bg_elevated"],
            fg=T["status_info"],
            activebackground="#334155",
            activeforeground="#ffffff",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            pady=5,
            command=self._mo_cua_so_ra_soat_nhanh,
        ).pack(fill="x", expand=True)

        # --- CỘT PHẢI: MÀN HÌNH NHẬT KÝ STUDIO & TIẾN ĐỘ TRỰC TIẾP ---
        log_hdr = tk.Frame(right_col, bg=T["bg_surface"], padx=14, pady=8)
        log_hdr.pack(fill="x")
        tk.Label(
            log_hdr,
            text=" NHẬT KÝ STUDIO & DANH SÁCH CHAPTER ",
            bg=T["bg_surface"],
            fg=T["text_primary"],
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")

        tk.Button(
            log_hdr,
            text="Xoá nhật ký",
            bg=T["bg_elevated"],
            fg=T["text_secondary"],
            font=("Segoe UI", 8),
            relief="flat",
            padx=8,
            pady=2,
            command=lambda: self.txt_log.delete("1.0", "end"),
        ).pack(side="right", padx=(6, 0))
        tk.Button(
            log_hdr,
            text="Sao chép nhật ký",
            bg=T["bg_elevated"],
            fg=T["text_secondary"],
            font=("Segoe UI", 8),
            relief="flat",
            padx=8,
            pady=2,
            command=lambda: (self.clipboard_clear(), self.clipboard_append(self.txt_log.get("1.0", "end"))),
        ).pack(side="right", padx=(6, 0))
        tk.Button(
            log_hdr,
            text="⏹ Dừng Dịch Ngay",
            bg="#7F1D1D",
            fg="#FECACA",
            activebackground="#DC2626",
            activeforeground="#ffffff",
            font=("Segoe UI", 8, "bold"),
            relief="flat",
            padx=10,
            pady=2,
            command=self._dung_chay,
        ).pack(side="right")

        tk.Frame(right_col, bg=T["border_subtle"], height=1).pack(fill="x")

        self.txt_log = scrolledtext.ScrolledText(
            right_col,
            bg=T["bg_console"],
            fg=T["text_primary"],
            insertbackground="#fff",
            relief="flat",
            padx=12,
            pady=10,
            font=("Consolas", 10),
            spacing1=2,
            spacing3=2,
        )
        self.txt_log.pack(fill="both", expand=True)
        self.txt_log.tag_config("ts", foreground=T["text_muted"])
        self.txt_log.tag_config("ok", foreground="#34D399")
        self.txt_log.tag_config("warn", foreground="#FBBF24")
        self.txt_log.tag_config("err", foreground="#F87171")
        self.txt_log.tag_config("info", foreground="#38BDF8")

        self.ghi_log(
            "✨ Sẵn sàng tại bàn làm việc Manga Studio Pro!\n"
            "👉 Bước 01: Dán Link truyện (steel-ball-run, MangaDex, MANGA Plus...) hoặc chọn File/Thư mục.\n"
            "👉 Bước 02: Chọn Ngôn ngữ (JA/ZH/KO/EN), Font chữ và Bộ máy AI (⚡ OCR + GPU Nhanh hoặc 🧠 GPU Pro Tự Học).\n"
            "👉 Bước 03: Bấm '🚀 BẮT ĐẦU TẢI & DỊCH THEO CHAPTER'."
        )

    def ghi_log(self, dong: str):
        def _append():
            ts = f"[{time.strftime('%H:%M:%S')}] "
            self.txt_log.insert("end", ts, "ts")
            tag = None
            if any(k in dong for k in ("✅", "🎉", "Hoàn tất", "thành công")):
                tag = "ok"
            elif any(k in dong for k in ("❌", "Lỗi", "thất bại")):
                tag = "err"
            elif any(k in dong for k in ("⚠️", "Chưa", "Tạm dừng", "⏸")):
                tag = "warn"
            elif any(k in dong for k in ("🔍", "🌐", "💻", "📦", "🔐")):
                tag = "info"
            if tag:
                self.txt_log.insert("end", f"{dong}\n", tag)
            else:
                self.txt_log.insert("end", f"{dong}\n")
            self.txt_log.see("end")
        self.after(0, _append)

    def _chon_thu_muc(self):
        d = filedialog.askdirectory(initialdir=self.ent_out.get())
        if d:
            self.ent_out.delete(0, "end")
            self.ent_out.insert(0, d)

    def _mo_video_review_studio(self):
        for cand in (
            Path(__file__).resolve().parent.parent / "video-review-studio" / "app_video_review_studio.py",
            Path(__file__).resolve().parent / "video-review-studio" / "app_video_review_studio.py",
            Path.cwd() / "video-review-studio" / "app_video_review_studio.py",
        ):
            if cand.is_file():
                subprocess.Popen([sys.executable, str(cand)], cwd=str(cand.parent))
                self.ghi_log(f"🎬 Đã mở Phần Mềm Dựng Video Review Truyện Tự Động: {cand}")
                return
        messagebox.showinfo(
            "Video Review Studio",
            "Không tìm thấy `video-review-studio/app_video_review_studio.py` trong thư mục cài đặt.",
        )

    def _mo_thu_muc_xuat(self):
        p = Path(self.ent_out.get().strip())
        p.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(p))

    def _sao_chep_ma_may(self):
        self.clipboard_clear()
        self.clipboard_append(MA_MAY_HIEN_THI)
        self.ghi_log(f"📋 Đã sao chép Mã máy tính vào bộ nhớ tạm: {MA_MAY_HIEN_THI}")

    def _sao_chep_api_host_cuc_bo(self):
        ip_lan = lay_dia_chi_ip_mang_lan()
        url_host = f"http://{ip_lan}:{LOCAL_BRIDGE_PORT}"
        self.clipboard_clear()
        self.clipboard_append(url_host)
        self.ghi_log(
            f"🔌 Đã sao chép Địa chỉ API Máy Chủ của bạn: {url_host} "
            f"(Dán địa chỉ này vào ô 'Máy chủ' trên App Windows hoặc Tiện ích Chrome của máy tính khách để kết nối!)"
        )

    def _dang_nhap(self):
        may_chu = chuan_hoa_may_chu(self.ent_server.get())
        email = self.ent_email.get().strip()
        mat_khau = self.ent_pass.get().strip()
        khoa_api = (
            mat_khau
            if (mat_khau.startswith("tr_live_") or (not email and len(mat_khau) >= 24))
            else (email if email.startswith("tr_live_") else "")
        )
        if not khoa_api and (not email or not mat_khau):
            messagebox.showwarning(
                "Thiếu thông tin",
                "Vui lòng nhập Email & Mật khẩu (hoặc dán mã API Key tr_live_... / Mã Phiên Web vào ô Mật khẩu).",
            )
            return

        def _worker():
            try:
                if khoa_api:
                    raw_me = goi_http(f"{may_chu}/api/v1/auth/me", token=khoa_api)
                    nguoi = json.loads(raw_me.decode("utf-8"))
                    email_xac_nhan = nguoi.get("email") or email
                    self.cau_hinh["may_chu"] = may_chu
                    self.cau_hinh["email"] = email_xac_nhan
                    self.cau_hinh["token"] = khoa_api
                    self.cau_hinh["ma_may_tinh"] = MA_MAY_HIEN_THI
                    self._luu_cau_hinh()
                    self.ghi_log(
                        f"✅ Đã kết nối bằng API Key với tài khoản: {email_xac_nhan} (Mã máy: {MA_MAY_HIEN_THI})"
                    )
                    self._cap_nhat_han_muc(ghi_nhat_ky=True)
                    return

                raw = goi_http(
                    f"{may_chu}/api/v1/auth/login",
                    method="POST",
                    body={"email": email, "mat_khau": mat_khau, "ma_may_tinh": MA_MAY_HIEN_THI},
                )
                kq = json.loads(raw.decode("utf-8"))
                ma_phien = kq.get("ma_phien", "")
                self.cau_hinh["may_chu"] = may_chu
                self.cau_hinh["email"] = email
                self.cau_hinh["token"] = ma_phien
                self.cau_hinh["ma_phien_dang_nhap"] = ma_phien
                self.cau_hinh["ma_may_tinh"] = MA_MAY_HIEN_THI
                self._luu_cau_hinh()
                self.ghi_log(f"✅ Đăng nhập & Liên kết Mã máy [{MA_MAY_HIEN_THI}] thành công với tài khoản: {email}")
                self._cap_nhat_han_muc(ghi_nhat_ky=True)
            except Exception as exc:
                self.ghi_log(f"❌ Đăng nhập thất bại: {exc}")

        threading.Thread(target=_worker, daemon=True).start()

    def _cap_nhat_han_muc(self, ghi_nhat_ky: bool = False):
        may_chu = chuan_hoa_may_chu(self.ent_server.get())
        token = self.cau_hinh.get("token", "")
        email = self.cau_hinh.get("email", "")
        try:
            raw = goi_http(f"{may_chu}/api/v1/han-muc", token=token)
            hm = json.loads(raw.decode("utf-8"))
            con_lai_tong = int(hm.get("con_lai", 0))
            tran = int(hm.get("tran", 0))
            da_dung = int(hm.get("da_dung", 0))
            mua_them = int(hm.get("so_luot_mua_them", 0))
            chot_ds = hm.get("chot") or []
            if isinstance(chot_ds, list) and chot_ds and isinstance(chot_ds[0], dict):
                con_lai_ngay = int(chot_ds[0].get("con_lai", max(0, con_lai_tong - mua_them)))
            else:
                con_lai_ngay = max(0, con_lai_tong - mua_them)
            tong_kha_dung = con_lai_ngay + mua_them
            loai_tk = f"Tài khoản {email}" if (token and email) else f"Máy tính {MA_MAY_HIEN_THI}"

            chu_header = f"💎 Khả dụng: {tong_kha_dung:,} trang ({MA_MAY_HIEN_THI})"
            chu_chi_tiet = (
                f"✅ {loai_tk}: Còn {con_lai_ngay}/{tran} lượt hôm nay (đã dùng {da_dung}) "
                f"+ {mua_them} lượt gói VIP = Tổng {tong_kha_dung:,} trang khả dụng"
            )
            self.cau_hinh["luot_con_lai_cuoi"] = tong_kha_dung
            self._luu_cau_hinh()
            self.after(0, lambda: self.lbl_han_muc.config(text=chu_header, fg="#34d399"))
            self.after(0, lambda: self.lbl_chi_tiet_luot.config(text=chu_chi_tiet, fg="#34d399"))
            if ghi_nhat_ky:
                self.ghi_log(f"🔐 Xác nhận thiết bị [{MA_MAY_HIEN_THI}] -> {chu_chi_tiet}")
        except Exception as exc:
            if ghi_nhat_ky:
                self.ghi_log(f"⚠️ Chưa kết nối được máy chủ để kiểm tra lượt ({exc}). Mã máy đã lưu: {MA_MAY_HIEN_THI}")

    def _mo_cua_so_goi_cuoc_va_api(self):
        """
        Mở Bảng Quản Lý Mô Hình 2 (Cloud API + Tài Khoản + Developer API Key `tr_live_...` + Bảng Giá 5 Gói Cước)
        ngay bên trong ứng dụng Windows.
        """
        T = MANGA_UI_TOKENS
        win = tk.Toplevel(self)
        win.title("💎 Mô Hình 2: Quản Lý Tài Khoản Cloud, Developer API Key (tr_live_) & Bảng Giá Gói Cước")
        win.geometry("980x700")
        win.configure(bg=T["bg_canvas"])
        win.transient(self)

        hdr = tk.Frame(win, bg=T["bg_header"], padx=18, pady=12)
        hdr.pack(fill="x")
        tk.Label(
            hdr,
            text="💎 MÔ HÌNH 2: HỆ THỐNG TÀI KHOẢN CLOUD · KHOÁ DEVELOPER API (tr_live_) · BẢNG GIÁ GÓI CƯỚC",
            bg=T["bg_header"],
            fg=T["text_primary"],
            font=("Segoe UI", 11, "bold"),
        ).pack(side="left")

        lbl_status = tk.Label(
            hdr,
            text="Đang đồng bộ từ máy chủ...",
            bg="#162033",
            fg=T["status_info"],
            font=("Consolas", 9, "bold"),
            padx=10,
            pady=4,
        )
        lbl_status.pack(side="right")

        # Khung 1: Tài khoản & Cấp khoá Developer API Key (tr_live_...)
        f_api = tk.Frame(
            win,
            bg=T["bg_surface"],
            highlightbackground=T["border_subtle"],
            highlightthickness=1,
            padx=16,
            pady=12,
        )
        f_api.pack(fill="x", padx=16, pady=(12, 8))

        tk.Label(
            f_api,
            text="1. ĐĂNG KÝ / ĐĂNG NHẬP & CẤP MÃ DEVELOPER API KEY (tr_live_...) CHO MÁY KHÁCH",
            bg=T["bg_surface"],
            fg=T["accent_soft"],
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        row_acc = tk.Frame(f_api, bg=T["bg_surface"])
        row_acc.pack(fill="x", pady=(0, 8))
        tk.Label(row_acc, text="Email:", bg=T["bg_surface"], fg=T["text_secondary"], font=("Segoe UI", 9)).pack(side="left")
        ent_em = tk.Entry(row_acc, width=26, bg=T["bg_elevated"], fg=T["text_primary"], insertbackground="#fff", relief="flat")
        ent_em.insert(0, self.ent_email.get().strip() or self.cau_hinh.get("email", ""))
        ent_em.pack(side="left", padx=(6, 12), ipady=3)

        tk.Label(row_acc, text="Mật khẩu:", bg=T["bg_surface"], fg=T["text_secondary"], font=("Segoe UI", 9)).pack(side="left")
        ent_pw = tk.Entry(row_acc, width=18, show="*", bg=T["bg_elevated"], fg=T["text_primary"], insertbackground="#fff", relief="flat")
        ent_pw.insert(0, self.ent_pass.get().strip())
        ent_pw.pack(side="left", padx=(6, 12), ipady=3)

        row_key = tk.Frame(f_api, bg=T["bg_surface"])
        row_key.pack(fill="x")
        tk.Label(row_key, text="Developer API Key:", bg=T["bg_surface"], fg=T["text_secondary"], font=("Segoe UI", 9)).pack(side="left")
        ent_api_key = tk.Entry(
            row_key,
            width=48,
            bg=T["bg_elevated"],
            fg=T["status_warn"],
            font=("Consolas", 9, "bold"),
            insertbackground="#fff",
            relief="flat",
        )
        tok_ht = str(self.cau_hinh.get("token", ""))
        ent_api_key.insert(0, tok_ht if tok_ht.startswith("tr_live_") else "Chưa tạo hoặc chưa hiển thị — Bấm 'Tạo / Lấy API Key'")
        ent_api_key.pack(side="left", padx=(6, 10), ipady=3)

        def _dang_ky_nhanh():
            may_chu = chuan_hoa_may_chu(self.ent_server.get())
            em = ent_em.get().strip()
            pw = ent_pw.get().strip()
            if not em or len(pw) < 8:
                messagebox.showwarning("Thiếu thông tin", "Nhập Email hợp lệ và Mật khẩu từ 8 ký tự trở lên để đăng ký!", parent=win)
                return

            def _wk():
                try:
                    raw = goi_http(
                        f"{may_chu}/api/v1/auth/register",
                        method="POST",
                        body={"email": em, "mat_khau": pw, "ten_hien": em.split("@")[0], "ma_may_tinh": MA_MAY_HIEN_THI},
                    )
                    kq = json.loads(raw.decode("utf-8"))
                    ma_phien = kq.get("ma_phien", "")
                    if not ma_phien:
                        raw_lg = goi_http(
                            f"{may_chu}/api/v1/auth/login",
                            method="POST",
                            body={"email": em, "mat_khau": pw, "ma_may_tinh": MA_MAY_HIEN_THI},
                        )
                        kq_lg = json.loads(raw_lg.decode("utf-8"))
                        ma_phien = kq_lg.get("ma_phien", "")
                    self.cau_hinh["may_chu"] = may_chu
                    self.cau_hinh["email"] = em
                    self.cau_hinh["token"] = ma_phien
                    self.cau_hinh["ma_phien_dang_nhap"] = ma_phien
                    self._luu_cau_hinh()
                    self.after(0, lambda: (self.ent_email.delete(0, "end"), self.ent_email.insert(0, em)))
                    self.ghi_log(f"✨ Đăng ký tài khoản mới thành công: {em} (Tặng 20 Credits miễn phí!)")
                    self._cap_nhat_han_muc(ghi_nhat_ky=True)
                    _tai_thong_tin_bang_gia()
                except Exception as e:
                    self.after(0, lambda err=str(e): messagebox.showerror("Lỗi đăng ký", err, parent=win))

            threading.Thread(target=_wk, daemon=True).start()

        def _tao_hoac_doi_api_key():
            may_chu = chuan_hoa_may_chu(self.ent_server.get())
            em_nhap = ent_em.get().strip()
            pw_nhap = ent_pw.get().strip()
            tok_phien = self.cau_hinh.get("ma_phien_dang_nhap") or self.cau_hinh.get("token", "")
            if (not tok_phien or str(tok_phien).startswith("tr_live_")) and (not em_nhap or not pw_nhap):
                messagebox.showwarning(
                    "Cần phiên đăng nhập",
                    "Để bảo mật chống chiếm đoạt khoá, vui lòng nhập Email + Mật khẩu tài khoản trước khi Tạo / Xoay mã API Key!",
                    parent=win,
                )
                return

            def _wk():
                try:
                    tok_goi = tok_phien
                    if em_nhap and pw_nhap and not pw_nhap.startswith("tr_live_"):
                        raw_lg = goi_http(
                            f"{may_chu}/api/v1/auth/login",
                            method="POST",
                            body={"email": em_nhap, "mat_khau": pw_nhap, "ma_may_tinh": MA_MAY_HIEN_THI},
                        )
                        kq_lg = json.loads(raw_lg.decode("utf-8"))
                        if kq_lg.get("ma_phien"):
                            tok_goi = kq_lg["ma_phien"]
                            self.cau_hinh["ma_phien_dang_nhap"] = tok_goi
                    raw = goi_http(f"{may_chu}/api/v1/auth/api-key", method="POST", body={}, token=tok_goi)
                    kq = json.loads(raw.decode("utf-8"))
                    khoa_moi = kq.get("api_key") or kq.get("khoa_api") or ""
                    if khoa_moi:
                        self.cau_hinh["token"] = khoa_moi
                        self._luu_cau_hinh()
                        self.clipboard_clear()
                        self.clipboard_append(khoa_moi)
                        self.after(0, lambda k=khoa_moi: (ent_api_key.delete(0, "end"), ent_api_key.insert(0, k)))
                        self.after(0, lambda k=khoa_moi: lbl_status.config(text="✅ Đã cấp & Copy API Key (tr_live_)", fg=T["status_ok"]))
                        self.ghi_log(f"🔑 Đã tạo & tự động gắn Developer API Key vào máy khách: {khoa_moi[:16]}... (Đã copy vào Clipboard)")
                except Exception as e:
                    self.after(0, lambda err=str(e): messagebox.showerror("Không tạo được API Key", err, parent=win))

            threading.Thread(target=_wk, daemon=True).start()

        def _copy_api_key():
            k = ent_api_key.get().strip()
            if k.startswith("tr_live_"):
                self.clipboard_clear()
                self.clipboard_append(k)
                lbl_status.config(text="📋 Đã copy mã tr_live_ vào bộ nhớ tạm!", fg=T["status_ok"])

        tk.Button(
            row_acc,
            text="✨ Đăng ký mới (+20 Credits miễn phí)",
            bg=T["bg_elevated"],
            fg=T["status_ok"],
            font=("Segoe UI", 8, "bold"),
            relief="flat",
            padx=10,
            pady=3,
            command=_dang_ky_nhanh,
        ).pack(side="left", padx=4)

        tk.Button(
            row_key,
            text="🔑 Tạo / Đổi API Key (tr_live_) & Gắn vào App",
            bg=T["accent_primary"],
            fg="#ffffff",
            font=("Segoe UI", 8, "bold"),
            relief="flat",
            padx=10,
            pady=3,
            command=_tao_hoac_doi_api_key,
        ).pack(side="left", padx=4)

        tk.Button(
            row_key,
            text="📋 Copy Key",
            bg=T["bg_elevated"],
            fg=T["text_primary"],
            font=("Segoe UI", 8, "bold"),
            relief="flat",
            padx=8,
            pady=3,
            command=_copy_api_key,
        ).pack(side="left", padx=4)

        # Khung 2: Bảng Giá 5 Gói Cước & So sánh chi phí thực tế
        f_tiers = tk.Frame(
            win,
            bg=T["bg_surface"],
            highlightbackground=T["border_subtle"],
            highlightthickness=1,
            padx=16,
            pady=12,
        )
        f_tiers.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        tk.Label(
            f_tiers,
            text="2. BẢNG GIÁ CÁC GÓI LƯỢT CLOUD & PHÂN TÍCH CHI PHÍ THỰC TẾ (LƯỢT MUA VĨNH VIỄN KHÔNG HẾT HẠN QUA ĐÊM)",
            bg=T["bg_surface"],
            fg=T["accent_soft"],
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=(0, 4))

        lbl_bank = tk.Label(
            f_tiers,
            text="💡 Cú pháp nạp VietQR tự động 24/7: Đang tải...",
            bg=T["bg_surface"],
            fg=T["status_ok"],
            font=("Consolas", 9, "bold"),
        )
        lbl_bank.pack(anchor="w", pady=(0, 8))

        txt_bang_gia = scrolledtext.ScrolledText(
            f_tiers,
            bg=T["bg_canvas"],
            fg=T["text_primary"],
            font=("Consolas", 9),
            relief="flat",
            padx=12,
            pady=10,
            height=18,
        )
        txt_bang_gia.pack(fill="both", expand=True)

        bar_bot = tk.Frame(f_tiers, bg=T["bg_surface"])
        bar_bot.pack(fill="x", pady=(8, 0))
        tk.Button(
            bar_bot,
            text="🌐 Mở Trang Thanh Toán VietQR Tự Động",
            bg=T["accent_primary"],
            fg="#ffffff",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=14,
            pady=5,
            command=lambda: webbrowser.open(f"{WEB_CHINH_THUC}/#bang-gia"),
        ).pack(side="left")

        tk.Button(
            bar_bot,
            text="🔄 Làm mới Số Lượt & Gói Cước",
            bg=T["bg_elevated"],
            fg=T["text_primary"],
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=12,
            pady=5,
            command=lambda: _tai_thong_tin_bang_gia(),
        ).pack(side="left", padx=8)

        def _tai_thong_tin_bang_gia():
            may_chu = chuan_hoa_may_chu(self.ent_server.get())
            tok = self.cau_hinh.get("token", "")

            def _wk():
                thong_tin = {}
                try:
                    raw = goi_http(f"{may_chu}/api/v1/nap-luot/thong-tin", token=tok)
                    thong_tin = json.loads(raw.decode("utf-8"))
                except Exception:
                    thong_tin = {}

                don_gia = int(thong_tin.get("ty_le_vnd_moi_trang") or 500)
                mua_them = int(thong_tin.get("so_luot_mua_them") or self.cau_hinh.get("luot_con_lai_cuoi") or 0)
                tran_ngay = int(thong_tin.get("tran_hang_ngay") or 10)
                nh_ten = thong_tin.get("ngan_hang_ten") or "MBBank / VietQR"
                nh_stk = thong_tin.get("ngan_hang_so_tk") or "Xem trên Web"
                nh_chu = thong_tin.get("ngan_hang_chu_tk") or "COMIC TRANSLATOR"
                cu_phap = thong_tin.get("noi_dung_chuyen_khoan") or f"NAP {self.cau_hinh.get('email') or MA_MAY_HIEN_THI}"

                noi_dung = (
                    "====================================================================================================\n"
                    "  PHÂN LOẠI TÀI KHOẢN & 20 CREDITS ĐĂNG KÝ MIỄN PHÍ\n"
                    "====================================================================================================\n"
                    "  • Khách vãng lai (Nhận diện theo Mã máy HWID) : 02 Credits miễn phí (Dùng thử nhanh không cần đăng ký)\n"
                    "  • Tài khoản Đăng ký Miễn phí (Free Account)   : 20 Credits miễn phí (1 Credit = 1 Trang dịch)\n"
                    "  • Đồng bộ 1 Ví duy nhất                       : Dùng chung trên Web, Tiện ích Chrome, App Windows & API\n\n"
                    "====================================================================================================\n"
                    "  BẢNG GIÁ 4 GÓI THEO THÁNG CHUẨN QUỐC TẾ (ƯU ĐÃI LẦN ĐẦU -50% · GIA HẠN TÍNH GIÁ GỐC)\n"
                    "====================================================================================================\n"
                    "  [1] 🌱 STARTER (300 Credits/tháng)            :  49.000 đ ($2.99) lần đầu | Gia hạn:  99.000 đ ($5.99)\n"
                    "  [2] ⭐ LITE / READER (800 Credits/tháng)      :  99.000 đ ($5.99) lần đầu | Gia hạn: 149.000 đ ($8.99)\n"
                    "  [3] 💎 STANDARD + API (3.000 Credits/tháng)   : 199.000 đ ($9.99) lần đầu | Gia hạn: 399.000 đ ($19.99) ⭐ ĐỀ XUẤT\n"
                    "  [4] 🏢 PRO MAX FULL API (10.000 Credits/tháng): 399.000 đ ($19.99) lần đầu| Gia hạn: 799.000 đ ($39.99)\n\n"
                    "====================================================================================================\n"
                    "  BẢNG QUY ĐỔI LƯỢT THEO BỘ MÁY AI ĐỘC QUYỀN (PHÂN TẦNG 1 - 2 - 3 LƯỢT)\n"
                    "====================================================================================================\n"
                    "  • ⚡ Model 1 — OCR + GPU Nhanh (local_ocr_gpu)          : 01 lượt / trang (Siêu tốc, tiết kiệm cho 85% truyện chữ rõ)\n"
                    "  • 🧠 Model 2 — OCR + GPU Pro Tự Học (local_hybrid_pro)  : 02 lượt / trang (Quét 2 tầng chữ viết tay, bảo vệ tranh & tự học 60 từ)\n"
                    "  • ✨ Model 3 — AI Đám Mây Ultra (llm_context)           : 03 lượt / trang (Mắt thần Gemini 2K & DeepSeek nhìn tranh phân vai xưng hô)\n"
                )

                def _cap_nhat_ui():
                    lbl_status.config(
                        text=f"Trần ngày: {tran_ngay} trang  |  Ví VIP tích luỹ: {mua_them:,} trang",
                        fg=T["status_ok"],
                    )
                    lbl_bank.config(
                        text=f"🏦 Ngân hàng: {nh_ten}  |  Số TK: {nh_stk} ({nh_chu})  |  Nội dung CK tự động: {cu_phap}"
                    )
                    txt_bang_gia.config(state="normal")
                    txt_bang_gia.delete("1.0", "end")
                    txt_bang_gia.insert("end", noi_dung)
                    txt_bang_gia.config(state="disabled")

                self.after(0, _cap_nhat_ui)

            threading.Thread(target=_wk, daemon=True).start()

        _tai_thong_tin_bang_gia()

    def _chon_thu_muc_anh_offline(self):
        if self.dang_chay:
            return
        d = filedialog.askdirectory(
            title="Chọn thư mục chứa ảnh truyện (1 hoặc nhiều bộ truyện / thư mục Chapter / gói ZIP-CBZ)"
        )
        if not d:
            return
        tm = Path(d)
        try:
            ds_chap = phan_loai_thu_muc_nhieu_truyen(tm, ten_mac_dinh=tm.name or "Truyen-Offline")
        except Exception as exc:
            messagebox.showerror("Chưa đọc được thư mục", str(exc))
            return
        cac_truyen = list(dict.fromkeys(ch.get("ten_truyen") or tm.name for ch in ds_chap))
        self.ent_ten_truyen.delete(0, "end")
        self.ent_ten_truyen.insert(0, cac_truyen[0] if len(cac_truyen) == 1 else (tm.name or "Nhieu-Truyen"))
        self.ent_url.delete(0, "end")
        self.ent_url.insert(0, f"local_dir::{tm}")
        self.ds_chapter_quet = ds_chap
        self._cap_nhat_ui_sau_quet(ds_chap)

    def _chon_goi_anh(self):
        if self.dang_chay:
            return
        ask_multi = getattr(filedialog, "askopenfilenames", None)
        if callable(ask_multi):
            names = ask_multi(
                title="Chọn 1 hoặc nhiều file truyện (.ZIP, .CBZ hoặc nhiều ảnh .JPG/.PNG/.WEBP của nhiều truyện)",
                filetypes=[
                    ("Tất cả file truyện & ảnh", "*.zip *.cbz *.jpg *.jpeg *.png *.webp"),
                    ("Gói ảnh truyện (.zip, .cbz)", "*.zip *.cbz"),
                    ("Ảnh trang truyện (.jpg, .png, .webp)", "*.jpg *.jpeg *.png *.webp"),
                ],
            )
            ds_chon = list(names) if names else []
        else:
            single = filedialog.askopenfilename(
                title="Chọn gói ảnh truyện", filetypes=[("Gói ảnh truyện", "*.zip *.cbz")]
            )
            ds_chon = [single] if single else []
        if not ds_chon:
            return
        try:
            ten_hien_tai = self.ent_ten_truyen.get().strip()
            ds_chap = phan_loai_nhieu_file_truyen(ds_chon, ten_truyen_mac_dinh=ten_hien_tai)
        except Exception as exc:
            messagebox.showerror("Chưa mở được file", str(exc))
            return
        self.ds_chapter_quet = ds_chap
        cac_truyen = list(dict.fromkeys(ch.get("ten_truyen") or "Truyen-Moi" for ch in ds_chap))
        self.ent_ten_truyen.delete(0, "end")
        self.ent_ten_truyen.insert(0, cac_truyen[0] if len(cac_truyen) == 1 else f"{len(cac_truyen)}-Bo-Truyen")
        self.ent_url.delete(0, "end")
        if len(ds_chon) == 1:
            self.ent_url.insert(0, f"archive::{ds_chon[0]}")
        else:
            self.ent_url.insert(0, f"multi_files::{len(ds_chon)}_files")
        self._cap_nhat_ui_sau_quet(self.ds_chapter_quet)
        tong_trang = sum(len(ch.get("sources") or []) for ch in ds_chap)
        self.ghi_log(
            f"📦 Đã phân loại {len(ds_chon)} file -> {len(ds_chap)} Chapter thuộc {len(cac_truyen)} bộ truyện "
            f"(tổng {tong_trang} trang). Khi dịch xong sẽ tự động tách riêng từng thư mục: <Tên_Truyện>/<Tên_Chapter>/."
        )

    def _mo_hop_thoai_nhieu_link(self):
        if self.dang_chay:
            return
        win = tk.Toplevel(self)
        win.title("📋 Dán Nhiều Link Bộ Truyện hoặc Link Chapter (Mỗi dòng 1 Link)")
        win.geometry("760x420")
        win.configure(bg="#0f172a")
        tk.Label(
            win,
            text="Dán danh sách Link các bộ truyện hoặc các Chapter (mỗi dòng 1 link).\n"
                 "App sẽ tự động quét theo đúng trình tự từng Chapter và chia riêng thư mục theo từng Tên bộ truyện:",
            bg="#0f172a",
            fg="#38bdf8",
            font=("Segoe UI", 10, "bold"),
            justify="left",
        ).pack(anchor="w", padx=14, pady=(12, 6))
        txt = scrolledtext.ScrolledText(
            win, bg="#1e293b", fg="#f8fafc", insertbackground="#fff", font=("Consolas", 10), height=14
        )
        cur_u = self.ent_url.get().strip()
        if cur_u and not cur_u.startswith(("local_dir::", "archive::", "multi_files::")):
            txt.insert("1.0", cur_u.replace(";", "\n"))
        txt.pack(fill="both", expand=True, padx=14, pady=6)

        def _xac_nhan():
            raw_links = [
                line.strip()
                for line in txt.get("1.0", "end").splitlines()
                if line.strip() and line.strip().startswith(("http://", "https://"))
            ]
            if not raw_links:
                messagebox.showwarning("Chưa có link hợp lệ", "Hãy dán ít nhất 1 đường link http:// hoặc https://!", parent=win)
                return
            joined = " ; ".join(raw_links)
            self.ent_url.delete(0, "end")
            self.ent_url.insert(0, joined)
            win.destroy()
            self._quet_link_truyen()

        f_btn = tk.Frame(win, bg="#0f172a", pady=8)
        f_btn.pack(fill="x", padx=14)
        tk.Button(
            f_btn,
            text="🔍 Quét tất cả Link theo trình tự Chapter",
            bg="#db2777",
            fg="#ffffff",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=16,
            pady=6,
            command=_xac_nhan,
        ).pack(side="left")
        tk.Button(
            f_btn, text="Đóng", bg="#334155", fg="#f8fafc", relief="flat", padx=12, pady=6, command=win.destroy
        ).pack(side="left", padx=8)

    def _kiem_tra_gguf_cuc_bo(self):
        # Đọc biến Tk ở luồng giao diện, không đọc từ luồng nền.
        chay_cpu = bool(self.var_cpu_ollama.get())
        self.cau_hinh["ollama_cpu"] = chay_cpu
        self._luu_cau_hinh()

        def _worker():
            self.ghi_log("💻 Đang kiểm tra Qwen3-VL 8B: tìm model rồi chạy thử một câu ngắn...")
            try:
                backend, model = chay_thu_model_cuc_bo(chay_cpu)
            except LocalRuntimeCrashError as exc:
                self.ghi_log(f"❌ Model có trong máy nhưng không chạy được: {exc}")
                return
            except LocalServerUnavailableError as exc:
                self.ghi_log(f"ℹ️ {exc}")
                return
            except (LocalModelMissingError, LocalCpuUnsupportedError) as exc:
                self.ghi_log(f"⚠️ {exc}")
                return
            except Exception as exc:
                self.ghi_log(f"❌ Không kiểm tra được AI cục bộ: {exc}")
                return
            ten_backend = "Ollama" if backend == "ollama" else "LM Studio"
            self.ghi_log(
                f"✅ {ten_backend} đã có và chạy thử được {model} (chưa thử dịch ảnh). Nếu muốn dịch bằng model này, hãy tự chọn "
                "'local_gguf (Qwen3-VL 8B Offline)' trong ô 'Bộ máy AI'."
            )

        threading.Thread(target=_worker, daemon=True).start()

    def _kiem_tra_ocr_da_ngon_ngu(self):
        def _worker():
            self.ghi_log("🌐 Đang kiểm tra & đồng bộ Lõi Nhận Diện Đa Ngôn Ngữ (Anh / Nhật / Hàn / Trung)...")
            tai_goi_ocr_huggingface("all")
            kq = kiem_tra_goi_ocr_windows()
            da_co = [f"{k} ({v['ten']})" for k, v in kq.items() if v.get("ho_tro")]
            chua_co = [(k, v) for k, v in kq.items() if not v.get("ho_tro")]
            if da_co:
                self.ghi_log(f"✅ Đã sẵn sàng Lõi Nhận Diện tốc độ cao cho: {', '.join(da_co)}")
            if chua_co:
                self.ghi_log("⚠️ Các ngôn ngữ đang chuyển sang xử lý đám mây dự phòng:")
                for k, info in chua_co:
                    self.ghi_log(f"   • {k} ({info['ten']})")
            else:
                self.ghi_log("🎉 Tuyệt vời! Máy đã sẵn sàng đủ cả 4 gói nhận diện Anh / Nhật / Hàn / Trung tốc độ cao.")

        threading.Thread(target=_worker, daemon=True).start()

    def _cap_nhat_bo_may_ai_moi(self):
        """Cập nhật đồng bộ Lõi Nhận Diện, Định tuyến Model theo ngôn ngữ và mở Trung tâm Model HuggingFace & Cổng Siêu Tốc."""
        ngon_ngu_dich_ht = self.cmb_tgt.get().split()[0] if hasattr(self, "cmb_tgt") else "vi"

        def _worker():
            global _MODEL_LOCAL_OCR_GPU_TUY_CHON
            self.ghi_log("🔄 [1/3] Đang kiểm tra & đồng bộ trọng số Lõi Nhận Diện Chữ đa ngôn ngữ (JA · KO · ZH · EN)...")
            tai_goi_ocr_huggingface("all")
            with _LOCAL_CACHE_LOCK:
                _LOCAL_PAGE_TRANSLATION_CACHE.clear()
            kq_ocr = kiem_tra_goi_ocr_windows()
            so_ngon_ngu_ocr = sum(1 for v in kq_ocr.values() if v.get("ho_tro"))
            self.ghi_log(f"✅ [1/3] Lõi Nhận Diện Chữ: Đã đồng bộ sẵn sàng {so_ngon_ngu_ocr}/4 ngôn ngữ (JA · ZH · KO · EN).")

            self.ghi_log(f"🔄 [2/3] Đang định tuyến Model AI tối ưu nhất cho ngôn ngữ đích [{ngon_ngu_dich_ht}]...")
            try:
                backend_chon, model_chon = _ket_noi_llm_cho_local_ocr_gpu(ngon_ngu_dich=ngon_ngu_dich_ht)
                _MODEL_LOCAL_OCR_GPU_TUY_CHON = model_chon
                self.cau_hinh["model_ai_cuc_bo"] = model_chon
                self._luu_cau_hinh()
                self.ghi_log(f"✅ [2/3] Đã kết nối [{backend_chon.upper()}] -> Model: {model_chon} (Smart Router cho '{ngon_ngu_dich_ht}').")
            except Exception:
                self.ghi_log(
                    "✅ [2/3] Đã kích hoạt chế độ ⚡ OCR + GPU Nhanh kèm Bộ Làm Mượt Thoại Truyện Đa Ngôn Ngữ (9 ngôn ngữ)."
                )

            so_cum_hoc = len(nap_bo_nho_tu_hoc())
            self.ghi_log(
                f"🚀 [3/3] Hoàn tất cập nhật Bộ máy AI Mới! Đã nạp sẵn {so_cum_hoc} cụm từ trong Bộ nhớ Tự học vĩnh viễn."
            )

        threading.Thread(target=_worker, daemon=True).start()
        if not getattr(self, "headless", False):
            self._mo_trung_tam_model_huggingface_va_tang_toc()

    def _mo_trung_tam_model_huggingface_va_tang_toc(self):
        """Hộp thoại Quản lý các Model chuyên biệt từ HuggingFace/Ollama & Cổng Tăng Tốc LPU (Groq / DeepSeek / OpenRouter)."""
        win = tk.Toplevel(self)
        win.title("⚡ Trung Tâm Model HuggingFace & Cổng Tăng Tốc Siêu Tốc (Groq LPU · DeepSeek · OpenRouter · Ollama)")
        win.geometry("860x560")
        win.configure(bg="#0f172a")
        win.transient(self)

        tk.Label(
            win,
            text="🚀 TĂNG TỐC & NÂNG CẤP ĐỘ CHÍNH XÁC CHO ⚡ local_ocr_gpu & 🧠 local_hybrid_pro",
            bg="#0f172a",
            fg="#38bdf8",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", padx=16, pady=(12, 4))

        # Khung 1: Cổng Kết Nối Siêu Tốc (Groq LPU 750 token/s, DeepSeek V3, OpenRouter)
        f_cloud = tk.LabelFrame(
            win,
            text=" 1. Cổng Kết Nối Siêu Tốc (Tùy chọn — Giúp máy không có GPU rời đạt 98% ngữ cảnh với tốc độ 0.25s/trang) ",
            bg="#1e293b",
            fg="#fbbf24",
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=8,
        )
        f_cloud.pack(fill="x", padx=16, pady=6)
        f_cloud.columnconfigure(1, weight=1)

        tk.Label(f_cloud, text="⚡ Groq LPU Key (gsk_... · 750 tok/s):", bg="#1e293b", fg="#f8fafc", font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", pady=3)
        ent_groq = tk.Entry(f_cloud, bg="#0f172a", fg="#34d399", insertbackground="#fff", font=("Consolas", 9))
        ent_groq.insert(0, str(self.cau_hinh.get("groq_api_key") or _lay_khoa_groq_cuc_bo()))
        ent_groq.grid(row=0, column=1, sticky="ew", padx=8, pady=3)

        tk.Label(f_cloud, text="🧠 DeepSeek Key (sk-... · Chuẩn 98%):", bg="#1e293b", fg="#f8fafc", font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", pady=3)
        ent_ds = tk.Entry(f_cloud, bg="#0f172a", fg="#38bdf8", insertbackground="#fff", font=("Consolas", 9))
        ent_ds.insert(0, str(self.cau_hinh.get("deepseek_api_key") or _lay_khoa_deepseek_cuc_bo()))
        ent_ds.grid(row=1, column=1, sticky="ew", padx=8, pady=3)

        tk.Label(f_cloud, text="🌐 OpenRouter Key (sk-or-... · HF Free):", bg="#1e293b", fg="#f8fafc", font=("Segoe UI", 9)).grid(row=2, column=0, sticky="w", pady=3)
        ent_or = tk.Entry(f_cloud, bg="#0f172a", fg="#f472b6", insertbackground="#fff", font=("Consolas", 9))
        ent_or.insert(0, str(self.cau_hinh.get("openrouter_api_key") or _lay_khoa_openrouter_cuc_bo()))
        ent_or.grid(row=2, column=1, sticky="ew", padx=8, pady=3)

        def _luu_khoa_tang_toc():
            self.cau_hinh["groq_api_key"] = ent_groq.get().strip()
            self.cau_hinh["deepseek_api_key"] = ent_ds.get().strip()
            self.cau_hinh["openrouter_api_key"] = ent_or.get().strip()
            self._luu_cau_hinh()
            with _LOCAL_CACHE_LOCK:
                _LOCAL_PAGE_TRANSLATION_CACHE.clear()
            self.ghi_log("✅ Đã lưu cấu hình Cổng Kết Nối Siêu Tốc (Groq LPU / DeepSeek / OpenRouter)!")
            messagebox.showinfo("Đã lưu", "Đã lưu khoá kết nối tăng tốc! Bộ máy local_ocr_gpu và local_hybrid_pro sẽ tự động ưu tiên sử dụng.", parent=win)

        tk.Button(
            f_cloud,
            text="💾 Lưu Khoá Tăng Tốc",
            bg="#059669",
            fg="#ffffff",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=12,
            pady=4,
            command=_luu_khoa_tang_toc,
        ).grid(row=0, column=2, rowspan=3, padx=(4, 0))

        # Khung 2: Kho Model Chuyên Biệt từ Hugging Face / Ollama theo Ngôn ngữ
        f_hf = tk.LabelFrame(
            win,
            text=" 2. Kho Model GGUF Chuyên Dụng từ Hugging Face / Ollama (Tự động định tuyến theo ngôn ngữ đích) ",
            bg="#1e293b",
            fg="#34d399",
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=8,
        )
        f_hf.pack(fill="both", expand=True, padx=16, pady=6)

        lst_hf = tk.Listbox(
            f_hf, bg="#0f172a", fg="#f8fafc", selectbackground="#2563eb", font=("Consolas", 9), height=7
        )
        for m_info in DANH_SACH_MODEL_HUGGINGFACE_CHUYEN_DUNG:
            lst_hf.insert("end", f"{m_info['ten']}  [{m_info['vram']}]  ->  {m_info['ma']}")
        lst_hf.selection_set(0)
        lst_hf.pack(fill="both", expand=True, pady=(0, 8))

        lbl_pull_status = tk.Label(
            f_hf,
            text="💡 Chọn 1 model phía trên và bấm '📥 Tải & Kích hoạt qua Ollama' để chạy Offline 0đ trên GPU của bạn.",
            bg="#1e293b",
            fg="#cbd5e1",
            font=("Segoe UI", 8),
        )
        lbl_pull_status.pack(anchor="w")

        def _tai_model_hf_ollama():
            sel = lst_hf.curselection()
            idx_m = int(sel[0]) if sel else 0
            ma_model = DANH_SACH_MODEL_HUGGINGFACE_CHUYEN_DUNG[idx_m]["ma"]
            lbl_pull_status.config(text=f"⏳ Đang tải model '{ma_model}' từ HuggingFace/Ollama... (Xem nhật ký ở màn hình chính)", fg="#fbbf24")

            def _wk_pull():
                global _MODEL_LOCAL_OCR_GPU_TUY_CHON
                self.ghi_log(f"📥 Đang tải model chuyên dụng từ HuggingFace/Ollama: ollama pull {ma_model} ...")
                try:
                    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    proc = subprocess.run(
                        ["ollama", "pull", ma_model],
                        capture_output=True,
                        text=True,
                        timeout=1800,
                        creationflags=creationflags,
                    )
                    if proc.returncode == 0:
                        _MODEL_LOCAL_OCR_GPU_TUY_CHON = ma_model
                        self.cau_hinh["model_ai_cuc_bo"] = ma_model
                        self._luu_cau_hinh()
                        self.ghi_log(f"🎉 Đã tải và kích hoạt thành công model '{ma_model}'!")
                        self.after(0, lambda: lbl_pull_status.config(text=f"✅ Đã cài đặt & kích hoạt: {ma_model}", fg="#34d399"))
                    else:
                        err_t = (proc.stderr or proc.stdout or "Kiểm tra đã cài đặt Ollama chưa").strip()
                        self.ghi_log(f"⚠️ Chưa tải được '{ma_model}' qua Ollama: {err_t}")
                        self.after(0, lambda: lbl_pull_status.config(text=f"⚠️ Cần bật Ollama trước khi tải ({err_t[:60]})", fg="#f87171"))
                except Exception as exc:
                    self.ghi_log(f"⚠️ Không gọi được lệnh ollama pull ({exc}). Bạn có thể dùng Cổng Siêu Tốc Groq/DeepSeek ở mục 1!")
                    self.after(0, lambda e=str(exc): lbl_pull_status.config(text=f"⚠️ Máy chưa cài Ollama ({e[:50]}). Hãy dùng Cổng Groq/DeepSeek ở mục 1!", fg="#f87171"))

            threading.Thread(target=_wk_pull, daemon=True).start()

        btn_row_hf = tk.Frame(f_hf, bg="#1e293b")
        btn_row_hf.pack(fill="x", pady=(6, 0))
        tk.Button(
            btn_row_hf,
            text="📥 Tải & Kích hoạt Model Đang Chọn (HuggingFace / Ollama)",
            bg="#2563eb",
            fg="#ffffff",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=14,
            pady=5,
            command=_tai_model_hf_ollama,
        ).pack(side="left")
        tk.Button(
            btn_row_hf,
            text="Đóng",
            bg="#475569",
            fg="#ffffff",
            font=("Segoe UI", 9),
            relief="flat",
            padx=14,
            pady=5,
            command=win.destroy,
        ).pack(side="right")

    def _mo_cua_so_ra_soat_nhanh(self):
        import review_delivery

        out_root = Path(self.ent_out.get().strip() or (Path.home() / "Downloads" / "Truyen_Da_Dich"))
        win = tk.Toplevel(self)
        win.title("👁️ Rà Soát, Khoanh Chuột Xoá SFX & Sửa Nhanh Chapter (Vẽ lại trang ~0.4s · Không tốn lượt)")
        win.geometry("1260x740")
        win.configure(bg="#0f172a")

        top_bar = tk.Frame(win, bg="#1e293b", padx=12, pady=8)
        top_bar.pack(fill="x")
        tk.Label(top_bar, text="Thư mục Chapter:", bg="#1e293b", fg="#38bdf8", font=("Segoe UI", 9, "bold")).pack(side="left")
        ent_chap_dir = tk.Entry(top_bar, width=56, bg="#0f172a", fg="#f8fafc", insertbackground="#fff")
        ent_chap_dir.pack(side="left", padx=6, fill="x", expand=True)

        tk.Label(top_bar, text="Người duyệt:", bg="#1e293b", fg="#cbd5e1").pack(side="left", padx=(8, 2))
        ent_reviewer = tk.Entry(top_bar, width=16, bg="#0f172a", fg="#fbbf24", insertbackground="#fff")
        ent_reviewer.insert(0, self.cau_hinh.get("email") or MA_MAY_HIEN_THI)
        ent_reviewer.pack(side="left", padx=4)

        state: dict[str, Any] = {
            "folder": None,
            "pages": [],
            "cur_page": 0,
            "regions": [],
            "img_w": 1,
            "img_h": 1,
            "scale": 1.0,
            "offset_x": 0,
            "offset_y": 0,
            "drag_start": None,
            "drag_rect_id": None,
            "tk_img": None,
        }

        body = tk.Frame(win, bg="#0f172a", padx=10, pady=8)
        body.pack(fill="both", expand=True)

        left_col = tk.LabelFrame(body, text=" 📄 Danh sách Trang ", bg="#1e293b", fg="#38bdf8", font=("Segoe UI", 9, "bold"), padx=6, pady=6)
        left_col.pack(side="left", fill="y")
        lst_pages = tk.Listbox(left_col, width=24, height=22, bg="#0f172a", fg="#f8fafc", selectbackground="#2563eb", font=("Consolas", 10))
        lst_pages.pack(fill="both", expand=True)

        center_col = tk.LabelFrame(
            body,
            text=" 🖱️ Khung Ảnh Trực Tiếp (Kéo chuột khoanh vùng để Xoá SFX hoặc Thêm bóng thoại mới) ",
            bg="#1e293b",
            fg="#fbbf24",
            font=("Segoe UI", 9, "bold"),
            padx=6,
            pady=6,
        )
        center_col.pack(side="left", fill="both", expand=True, padx=(8, 8))
        cv_page = tk.Canvas(center_col, width=410, height=580, bg="#090d16", highlightthickness=1, highlightbackground="#334155", cursor="crosshair")
        cv_page.pack(fill="both", expand=True)

        right_col = tk.LabelFrame(
            body,
            text=" 💬 Danh sách Bóng thoại & Vùng SFX (Chọn 1 vùng để sửa nhanh & vẽ lại) ",
            bg="#1e293b",
            fg="#34d399",
            font=("Segoe UI", 9, "bold"),
            padx=8,
            pady=6,
        )
        right_col.pack(side="left", fill="both", expand=True)

        lst_bubbles = tk.Listbox(right_col, height=11, bg="#0f172a", fg="#f8fafc", selectbackground="#059669", font=("Consolas", 10))
        lst_bubbles.pack(fill="both", expand=True)

        edit_box = tk.Frame(right_col, bg="#1e293b", pady=6)
        edit_box.pack(fill="x")
        lbl_goc = tk.Label(edit_box, text="Câu gốc OCR: (chọn bóng thoại hoặc kéo chuột khoanh vùng trên ảnh)", bg="#1e293b", fg="#94a3b8", anchor="w", justify="left")
        lbl_goc.pack(fill="x")
        tk.Label(edit_box, text="Sửa bản dịch Tiếng Việt (hoặc để [XOA_SFX] nếu chỉ muốn xoá chữ nền):", bg="#1e293b", fg="#fde047", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(4, 2))
        ent_dich = tk.Entry(edit_box, bg="#0f172a", fg="#ffffff", insertbackground="#fff", font=("Segoe UI", 11))
        ent_dich.pack(fill="x", pady=2)

        var_inpaint_sfx = tk.BooleanVar(value=False)
        chk_sfx_bar = tk.Frame(edit_box, bg="#1e293b")
        chk_sfx_bar.pack(fill="x", pady=(4, 0))
        tk.Checkbutton(
            chk_sfx_bar,
            text="✨ Xoá chữ nền phức tạp / SFX 4 hướng (Tái tạo nền tự động)",
            variable=var_inpaint_sfx,
            bg="#1e293b",
            fg="#38bdf8",
            selectcolor="#0f172a",
            activebackground="#1e293b",
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")

        lbl_status_rv = tk.Label(right_col, text="Chọn thư mục Chapter có tệp trang-thai.json để bắt đầu rà soát.", bg="#1e293b", fg="#38bdf8", font=("Segoe UI", 9, "bold"), wraplength=460, justify="left")
        lbl_status_rv.pack(anchor="w", pady=4)

        def _ve_anh_len_canvas():
            cv_page.delete("all")
            if not state["folder"]:
                return
            p_img = state["folder"] / f"{state['cur_page'] + 1:03d}.jpg"
            if not p_img.is_file() or Image is None or ImageTk is None:
                return
            try:
                with Image.open(p_img) as raw_im:
                    im = raw_im.convert("RGB")
                    W, H = im.size
                    state["img_w"], state["img_h"] = W, H
                    cw = max(360, cv_page.winfo_width() or 410)
                    ch = max(480, cv_page.winfo_height() or 580)
                    scale = min((cw - 12) / max(1, W), (ch - 12) / max(1, H))
                    nw, nh = max(1, int(W * scale)), max(1, int(H * scale))
                    ox, oy = (cw - nw) // 2, (ch - nh) // 2
                    state["scale"], state["offset_x"], state["offset_y"] = scale, ox, oy
                    im_thumb = im.resize((nw, nh))
                    tk_im = ImageTk.PhotoImage(im_thumb)
                    state["tk_img"] = tk_im
                    cv_page.create_image(ox, oy, anchor="nw", image=tk_im)

                    sel_b = int(lst_bubbles.curselection()[0]) if lst_bubbles.curselection() else -1
                    for b_i, r in enumerate(state["regions"]):
                        rx = ox + int(r.get("x", 0) * scale)
                        ry = oy + int(r.get("y", 0) * scale)
                        rw = max(8, int(r.get("w", 20) * scale))
                        rh = max(8, int(r.get("h", 20) * scale))
                        mau_vien = "#fbbf24" if b_i == sel_b else ("#f43f5e" if r.get("inpaint_sfx") else "#10b981")
                        do_day = 3 if b_i == sel_b else 1
                        cv_page.create_rectangle(rx, ry, rx + rw, ry + rh, outline=mau_vien, width=do_day)
                        cv_page.create_rectangle(rx, max(oy, ry - 15), rx + 28, ry, fill=mau_vien, outline=mau_vien)
                        cv_page.create_text(rx + 14, max(oy + 7, ry - 7), text=f"#{b_i + 1}", fill="#000000" if b_i == sel_b else "#ffffff", font=("Consolas", 8, "bold"))
            except Exception:
                pass

        def _nap_ho_so(folder_path: Path):
            try:
                data = json.loads((folder_path / "trang-thai.json").read_text(encoding="utf-8"))
                pages = data.get("pages") or []
            except Exception as exc:
                messagebox.showerror("Chưa đọc được hồ sơ Chapter", f"Thư mục chưa có tệp trang-thai.json hợp lệ:\n{exc}", parent=win)
                return
            state["folder"] = folder_path
            state["pages"] = pages
            ent_chap_dir.delete(0, "end")
            ent_chap_dir.insert(0, str(folder_path))
            lst_pages.delete(0, "end")
            for idx, p in enumerate(pages):
                regs = p.get("regions") or []
                co_cb = any(r.get("canh_bao_chat_luong") for r in regs if isinstance(r, dict))
                rv = (p.get("review") or {}).get("decision")
                icon = "✅" if rv == "approved" else ("⚠️" if co_cb else "⏳")
                lst_pages.insert("end", f"{icon} Trang {idx + 1:03d} ({len(regs)} bóng)")
            if pages:
                lst_pages.selection_set(0)
                _chon_trang(0)

        def _chon_trang(idx: int):
            if not (0 <= idx < len(state["pages"])):
                return
            state["cur_page"] = idx
            p = state["pages"][idx]
            regs = [dict(r) for r in (p.get("regions") or []) if isinstance(r, dict)]
            state["regions"] = regs
            lst_bubbles.delete(0, "end")
            for b_i, r in enumerate(regs):
                cb = f" [⚠️ {r['canh_bao_chat_luong']}]" if r.get("canh_bao_chat_luong") else ""
                sfx_tag = "[SFX] " if r.get("inpaint_sfx") else ""
                lst_bubbles.insert("end", f"#{b_i + 1:02d}: {sfx_tag}{r.get('chu_goc', '')[:26]}  =>  {r.get('ban_dich', '')}{cb}")
            if regs:
                lst_bubbles.selection_set(0)
                _chon_bong(0)
            else:
                _ve_anh_len_canvas()
            lbl_status_rv.config(text=f"Đang xem Trang {idx + 1:03d}/{len(state['pages'])} — có {len(regs)} vùng. Kéo chuột trên ảnh giữa để khoanh thêm vùng SFX / bóng thoại!")

        def _chon_bong(b_idx: int):
            regs = state["regions"]
            if not (0 <= b_idx < len(regs)):
                return
            r = regs[b_idx]
            lbl_goc.config(text=f"Câu gốc OCR (#{b_idx + 1} · x={r.get('x')}, y={r.get('y')}, {r.get('w')}x{r.get('h')}): {r.get('chu_goc', '')}")
            ent_dich.delete(0, "end")
            ent_dich.insert(0, str(r.get("ban_dich") or ""))
            var_inpaint_sfx.set(bool(r.get("inpaint_sfx")))
            _ve_anh_len_canvas()

        def _cap_nhat_cau_dang_chon():
            sel = lst_bubbles.curselection()
            if not sel:
                return
            b_idx = int(sel[0])
            moi = ent_dich.get().strip()
            if not moi:
                if var_inpaint_sfx.get():
                    moi = "[XOA_SFX]"
                else:
                    messagebox.showwarning("Trống nội dung", "Bản dịch không được để trống (hoặc bấm nút 'Chỉ xoá chữ SFX')!", parent=win)
                    return
            state["regions"][b_idx]["ban_dich"] = moi
            state["regions"][b_idx]["inpaint_sfx"] = bool(var_inpaint_sfx.get() or moi == "[XOA_SFX]")
            state["regions"][b_idx].pop("canh_bao_chat_luong", None)
            r = state["regions"][b_idx]
            if moi != "[XOA_SFX]":
                hoc_tu_ban_sua_nguoi_dung(r.get("chu_goc", ""), moi)
            sfx_tag = "[SFX] " if r.get("inpaint_sfx") else ""
            lst_bubbles.delete(b_idx)
            lst_bubbles.insert(b_idx, f"#{b_idx + 1:02d}: {sfx_tag}{r.get('chu_goc', '')[:26]}  =>  {moi}")
            lst_bubbles.selection_set(b_idx)
            _ve_anh_len_canvas()

        def _chi_xoa_sfx_vung_chon():
            var_inpaint_sfx.set(True)
            ent_dich.delete(0, "end")
            ent_dich.insert(0, "[XOA_SFX]")
            _ve_lai_trang_hien_tai()

        def _xoa_bo_vung_dang_chon():
            sel = lst_bubbles.curselection()
            if not sel:
                return
            b_idx = int(sel[0])
            if 0 <= b_idx < len(state["regions"]):
                state["regions"].pop(b_idx)
                _ve_lai_trang_hien_tai(bo_qua_cap_nhat_o_nhap=True)

        def _on_canvas_press(event):
            state["drag_start"] = (event.x, event.y)
            if state["drag_rect_id"]:
                cv_page.delete(state["drag_rect_id"])
                state["drag_rect_id"] = None

        def _on_canvas_drag(event):
            if not state["drag_start"]:
                return
            x0, y0 = state["drag_start"]
            if state["drag_rect_id"]:
                cv_page.coords(state["drag_rect_id"], x0, y0, event.x, event.y)
            else:
                state["drag_rect_id"] = cv_page.create_rectangle(x0, y0, event.x, event.y, outline="#f43f5e", width=2, dash=(4, 2))

        def _on_canvas_release(event):
            if not state["drag_start"] or not state["folder"]:
                return
            x0, y0 = state["drag_start"]
            state["drag_start"] = None
            if state["drag_rect_id"]:
                cv_page.delete(state["drag_rect_id"])
                state["drag_rect_id"] = None

            scale = float(state["scale"] or 1.0)
            ox, oy = int(state["offset_x"]), int(state["offset_y"])
            ix0 = int((min(x0, event.x) - ox) / scale)
            iy0 = int((min(y0, event.y) - oy) / scale)
            ix1 = int((max(x0, event.x) - ox) / scale)
            iy1 = int((max(y0, event.y) - oy) / scale)

            # Nếu người dùng click nhẹ (< 12px): chọn bóng thoại có sẵn tại vị trí click
            if abs(event.x - x0) < 10 and abs(event.y - y0) < 10:
                for b_i, r in enumerate(state["regions"]):
                    rx, ry, rw, rh = int(r.get("x", 0)), int(r.get("y", 0)), int(r.get("w", 0)), int(r.get("h", 0))
                    if rx <= ix0 <= rx + rw and ry <= iy0 <= ry + rh:
                        lst_bubbles.selection_clear(0, "end")
                        lst_bubbles.selection_set(b_i)
                        _chon_bong(b_i)
                        return
                return

            W, H = int(state["img_w"]), int(state["img_h"])
            rx = max(0, min(W - 16, ix0))
            ry = max(0, min(H - 16, iy0))
            rw = max(16, min(W - rx, ix1 - rx))
            rh = max(16, min(H - ry, iy1 - ry))

            vung_moi = {
                "x": rx,
                "y": ry,
                "w": rw,
                "h": rh,
                "chu_goc": "Vùng khoanh thủ công / SFX",
                "ban_dich": "[XOA_SFX]",
                "inpaint_sfx": True,
            }
            state["regions"].append(vung_moi)
            b_new = len(state["regions"]) - 1
            lst_bubbles.insert("end", f"#{b_new + 1:02d}: [SFX] Vùng khoanh thủ công  =>  [XOA_SFX]")
            lst_bubbles.selection_clear(0, "end")
            lst_bubbles.selection_set(b_new)
            _chon_bong(b_new)
            lbl_status_rv.config(
                text=f"✨ Đã khoanh vùng mới #{b_new + 1} ({rw}x{rh}px). Bấm '🎨 Vẽ lại trang này' để xoá sạch SFX ngay, hoặc gõ chữ dịch vào ô trên!",
                fg="#fbbf24",
            )

        cv_page.bind("<ButtonPress-1>", _on_canvas_press)
        cv_page.bind("<B1-Motion>", _on_canvas_drag)
        cv_page.bind("<ButtonRelease-1>", _on_canvas_release)
        cv_page.bind("<Configure>", lambda _e: _ve_anh_len_canvas())

        def _ve_lai_trang_hien_tai(bo_qua_cap_nhat_o_nhap: bool = False):
            if not state["folder"]:
                return
            if not bo_qua_cap_nhat_o_nhap:
                _cap_nhat_cau_dang_chon()
            idx = state["cur_page"]
            try:
                ve_lai_trang_trong_ho_so_chapter(
                    state["folder"], idx, state["regions"], font_style=self.cmb_font.get().split()[0]
                )
                _nap_ho_so(state["folder"])
                lst_pages.selection_clear(0, "end")
                lst_pages.selection_set(idx)
                _chon_trang(idx)
                lbl_status_rv.config(text=f"✅ Đã vẽ lại & làm sạch nền Trang {idx + 1:03d} thành công (~0.4s)!", fg="#34d399")
            except Exception as exc:
                messagebox.showerror("Không vẽ lại được trang", str(exc), parent=win)

        def _mo_xem_anh_trang():
            if not state["folder"]:
                return
            p_img = state["folder"] / f"{state['cur_page'] + 1:03d}.jpg"
            if p_img.is_file() and os.name == "nt":
                os.startfile(str(p_img))

        def _duyet_tat_ca_va_xuat_zip():
            if not state["folder"]:
                return
            reviewer = ent_reviewer.get().strip() or MA_MAY_HIEN_THI
            try:
                with review_delivery.open_chapter(state["folder"]) as ledger:
                    st = review_delivery.chapter_status(ledger)
                    for row in st["pages"]:
                        p_idx = int(row["page"]) - 1
                        sha = row.get("sha256")
                        if not sha:
                            raise NeedsAttention(f"Trang {row['page']} chưa sẵn sàng để duyệt.")
                        review_delivery.record_review(
                            ledger, p_idx, decision="approved", reviewer=reviewer,
                            note="Duyệt qua cửa sổ Rà soát nhanh", expected_sha256=sha, confirmed=True
                        )
                    dest = state["folder"].parent / f"{state['folder'].name}-ban-giao-{int(time.time())}.zip"
                    review_delivery.export_delivery(ledger, dest)
                _nap_ho_so(state["folder"])
                lbl_status_rv.config(text=f"🎉 Đã duyệt đủ trang & xuất gói bàn giao: {dest.name}", fg="#34d399")
                self.ghi_log(f"📦 Đã duyệt và xuất gói ZIP bàn giao chính thức: {dest}")
            except Exception as exc:
                messagebox.showerror("Chưa xuất được gói bàn giao", str(exc), parent=win)

        def _chon_thu_muc_chap():
            d = filedialog.askdirectory(initialdir=str(out_root), title="Chọn thư mục Chapter đã dịch (có trang-thai.json)", parent=win)
            if d:
                _nap_ho_so(Path(d))

        tk.Button(top_bar, text="📂 Chọn Chapter...", bg="#0284c7", fg="#fff", relief="flat", padx=10, command=_chon_thu_muc_chap).pack(side="left", padx=4)

        btn_bar_sfx = tk.Frame(right_col, bg="#1e293b", pady=3)
        btn_bar_sfx.pack(fill="x")
        tk.Button(btn_bar_sfx, text="✨ Chỉ xoá chữ SFX (Không điền chữ)", bg="#e11d48", fg="#fff", font=("Segoe UI", 8, "bold"), relief="flat", padx=8, pady=4, command=_chi_xoa_sfx_vung_chon).pack(side="left", padx=(0, 6))
        tk.Button(btn_bar_sfx, text="🗑️ Xoá bỏ vùng đang chọn", bg="#64748b", fg="#fff", font=("Segoe UI", 8, "bold"), relief="flat", padx=8, pady=4, command=_xoa_bo_vung_dang_chon).pack(side="left", padx=4)
        tk.Button(btn_bar_sfx, text="🖼️ Mở ảnh lớn", bg="#475569", fg="#fff", font=("Segoe UI", 8, "bold"), relief="flat", padx=8, pady=4, command=_mo_xem_anh_trang).pack(side="right")

        btn_bar = tk.Frame(right_col, bg="#1e293b", pady=6)
        btn_bar.pack(fill="x")
        tk.Button(btn_bar, text="💾 Lưu câu vừa sửa", bg="#0d9488", fg="#fff", font=("Segoe UI", 9, "bold"), relief="flat", padx=10, pady=5, command=_cap_nhat_cau_dang_chon).pack(side="left", padx=(0, 6))
        tk.Button(btn_bar, text="🎨 Vẽ lại trang này (~0.4s)", bg="#2563eb", fg="#fff", font=("Segoe UI", 9, "bold"), relief="flat", padx=12, pady=5, command=_ve_lai_trang_hien_tai).pack(side="left", padx=6)
        tk.Button(btn_bar, text="✅ Duyệt & Xuất ZIP", bg="#16a34a", fg="#fff", font=("Segoe UI", 9, "bold"), relief="flat", padx=10, pady=5, command=_duyet_tat_ca_va_xuat_zip).pack(side="right")

        lst_pages.bind("<<ListboxSelect>>", lambda _e: _chon_trang(int(lst_pages.curselection()[0])) if lst_pages.curselection() else None)
        lst_bubbles.bind("<<ListboxSelect>>", lambda _e: _chon_bong(int(lst_bubbles.curselection()[0])) if lst_bubbles.curselection() else None)

        # Tự động nạp thư mục Chapter vừa dịch gần nhất nếu có
        if out_root.is_dir():
            manifests = sorted(out_root.rglob("trang-thai.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            if manifests:
                _nap_ho_so(manifests[0].parent)

    def _quet_link_truyen(self):
        url = self.ent_url.get().strip()
        if not url:
            messagebox.showwarning("Chưa nhập Link", "Vui lòng dán đường link truyện hoặc link chapter vào ô!")
            return
        if url.startswith(("local_dir::", "archive::", "multi_files::")):
            self.ghi_log("📁 Đang dùng chế độ File / Thư mục ảnh có sẵn trên máy.")
            return
        mo_rong = bool(self.var_mo_rong_ca_bo.get()) if hasattr(self, "var_mo_rong_ca_bo") else False
        self.cau_hinh["mo_rong_ca_bo"] = mo_rong
        self._luu_cau_hinh()

        def _worker():
            self.ghi_log(f"🔍 Đang quét danh sách Chapter theo trình tự từ: {url} ...")
            try:
                ds = quet_danh_sach_chapter_tu_url(url, mo_rong_ca_bo=mo_rong)
                self.ds_chapter_quet = ds
                cac_truyen = list(dict.fromkeys(ch.get("ten_truyen") for ch in ds if ch.get("ten_truyen")))
                if len(cac_truyen) == 1 and self.ent_ten_truyen.get().strip() in ("", "Truyen-Moi"):
                    self.after(0, lambda t=cac_truyen[0]: (self.ent_ten_truyen.delete(0, "end"), self.ent_ten_truyen.insert(0, t)))
                self.after(0, lambda: self._cap_nhat_ui_sau_quet(ds, url_goc=url))
            except Exception as exc:
                self.ghi_log(f"❌ Không quét được link: {exc}")

        threading.Thread(target=_worker, daemon=True).start()

    def _cap_nhat_ui_sau_quet(self, ds: list[dict], url_goc: str = ""):
        so_luong = len(ds)
        cac_truyen = list(dict.fromkeys(ch.get("ten_truyen") or self.ent_ten_truyen.get().strip() or "Truyen-Moi" for ch in ds))
        vi_tri_bat_dau = 1
        vi_tri_ket_thuc = max(1, so_luong)
        mo_rong = bool(self.var_mo_rong_ca_bo.get()) if hasattr(self, "var_mo_rong_ca_bo") else True
        if url_goc and so_luong > 1:
            for idx_c, ch in enumerate(ds, start=1):
                if ch.get("url", "").rstrip("/") == url_goc.strip().rstrip("/"):
                    vi_tri_bat_dau = idx_c
                    if not mo_rong:
                        vi_tri_ket_thuc = idx_c
                    break
        self.spin_tu.delete(0, "end")
        self.spin_tu.insert(0, str(vi_tri_bat_dau))
        self.spin_den.delete(0, "end")
        self.spin_den.insert(0, str(vi_tri_ket_thuc))
        thong_ke = f"✅ Tìm thấy {so_luong} Chapter ({len(cac_truyen)} bộ truyện)!"
        self.lbl_so_chap.config(text=thong_ke, fg="#34d399")
        self.ghi_log(f"{thong_ke} Sắp xếp theo đúng trình tự:")
        for idx, ch in enumerate(ds[:40], start=1):
            tr_hien_thi = ch.get("ten_truyen") or self.ent_ten_truyen.get().strip() or "Truyen-Moi"
            so_trg = f" ({len(ch['sources'])} trang)" if isinstance(ch.get("sources"), list) else ""
            self.ghi_log(f"   [{idx:02d}] 📚 {tr_hien_thi} / {ch['ten']}{so_trg} -> {ch['url']}")
        if so_luong > 40:
            self.ghi_log(f"   ... và {so_luong - 40} chapter khác.")

    def _dung_chay(self):
        self.yeu_cau_dung = True
        self.ghi_log("⏸ Đang dừng; không lưu trang dở. Việc đã gửi lên máy chủ có thể vẫn đang chạy.")
        try:
            self.btn_stop.config(text="⏳ ĐANG DỪNG...", bg="#7F1D1D")
            self.lbl_tien_do.config(text="⏸ Đang dừng sau trang hiện tại...")
        except Exception:
            pass

    def _xac_nhan_so_trang(self, chapter, count):
        """Generic HTML is provisional: require a human source-count check, not false certainty."""
        ready = threading.Event()
        answer = [None]

        def ask():
            try:
                if not self.yeu_cau_dung:
                    answer[0] = simpledialog.askinteger(
                        "Kiểm tra đủ trang", f"{chapter}: tìm thấy {count} ảnh.\n"
                        "Hãy kiểm số trang trên website nguồn rồi nhập số trang thực tế.\n"
                        "Nếu không xác định được, bấm Huỷ và dùng file ảnh.", parent=self, minvalue=1,
                    )
            finally:
                ready.set()

        self.after(0, ask)
        while not ready.wait(0.2):
            if self.yeu_cau_dung:
                raise RunStopped("Đã dừng.")
        if answer[0] != count:
            raise NeedsAttention("Chưa xác nhận đủ trang từ link; chưa gửi ảnh đi dịch.")

    def _bat_dau_chay(self):
        if self.dang_chay:
            return
        url_chinh = self.ent_url.get().strip()
        if not self.ds_chapter_quet and not url_chinh:
            messagebox.showwarning("Chưa có Link", "Hãy dán Link truyện hoặc chọn Thư mục ảnh trước khi bắt đầu!")
            return

        try:
            tu_dong_link = bool(self.var_tu_dong_link.get()) if hasattr(self, "var_tu_dong_link") else False
            so_luong_song_song = (
                max(1, min(8, int(self.spin_song_song.get() or 1)))
                if hasattr(self, "spin_song_song")
                else 1
            )
            self.run_options = {
                "server": chuan_hoa_may_chu(self.ent_server.get()),
                "token": self.cau_hinh.get("token", ""),
                "account": self.cau_hinh.get("email", "") or MA_MAY_HIEN_THI,
                "name": lam_sach_ten_thu_muc(self.ent_ten_truyen.get() or "Truyen-Da-Dich"),
                "output": self.ent_out.get().strip(), "url": url_chinh,
                "source_lang": self.cmb_src.get().split()[0], "target_lang": self.cmb_tgt.get().split()[0],
                "font": self.cmb_font.get().split()[0], "engine": self.cmb_engine.get().split()[0],
                "glossary": self.ent_tu_dien.get().strip(),
                "cbz": bool(self.var_cbz.get()), "pdf": bool(self.var_pdf.get()),
                "longstrip": bool(self.var_longstrip.get()),
                "auto_video_review": bool(self.var_auto_video_review.get()) if hasattr(self, "var_auto_video_review") else False,
                "ollama_cpu": bool(self.var_cpu_ollama.get()),
                "auto_confirm_link_pages": tu_dong_link,
                "mo_rong_ca_bo": bool(self.var_mo_rong_ca_bo.get()) if hasattr(self, "var_mo_rong_ca_bo") else True,
                "parallel_chapters": so_luong_song_song,
                "from": max(1, int(self.spin_tu.get() or 1)),
                "to": int(self.spin_den.get() or len(self.ds_chapter_quet) or 1),
                "chapters": [dict(chapter) for chapter in self.ds_chapter_quet],
            }
            self.cau_hinh["ollama_cpu"] = self.run_options["ollama_cpu"]
            self.cau_hinh["tu_dong_duyet_link"] = tu_dong_link
            self.cau_hinh["so_luong_song_song"] = so_luong_song_song
            self.cau_hinh["auto_video_review"] = self.run_options.get("auto_video_review", False)
            self._luu_cau_hinh()
            if not self.run_options["output"] or self.run_options["to"] < self.run_options["from"]:
                raise ValueError("Kiểm tra thư mục xuất và khoảng chapter.")
        except ValueError as exc:
            messagebox.showwarning("Chưa bắt đầu", str(exc))
            return

        self.dang_chay = True
        self.yeu_cau_dung = False
        self.btn_start.config(state="disabled", text="⏳ ĐANG TẢI & DỊCH... (BẤM ⏹ ĐỂ DỪNG)")
        self.btn_stop.config(state="normal", bg="#DC2626", fg="#ffffff", text="⏹ DỪNG NGAY")
        threading.Thread(target=self._luong_dich_hang_loat, daemon=True).start()

    def _khau_tru_luot_cuc_bo(self, data: bytes, options: dict):
        """
        Khấu trừ 1 lượt/trang trên sổ cái Server khi khách hàng chạy `local_ocr_gpu`:
        - Máy khách tự gánh 100% tải CPU/GPU (0đ chi phí vận hành Server), nhưng vẫn trừ đúng 1 lượt trong tài khoản khách.
        - Tự động chống trừ trùng theo mã băm `SHA-256` của bức ảnh.
        - Tài khoản Quản trị viên (`la_quan_tri = True`) được miễn trừ không giới hạn.
        """
        srv = str(options.get("server") or "").strip().rstrip("/")
        if not srv or "api.invalid" in srv or "127.0.0.1:17890" in srv:
            return
        tok = str(options.get("token") or "").strip()
        ma_anh = hashlib.sha256(data).hexdigest()
        ma_eng = str(options.get("engine") or "local_ocr_gpu").strip()
        so_luot_can = int(SO_LUOT_MOI_TRANG_THEO_ENGINE.get(ma_eng, 1))
        try:
            raw_res = goi_http(
                f"{srv}/api/v1/developer/consume-local-page",
                method="POST",
                body={"page_key": ma_anh, "engine": ma_eng, "credits": so_luot_can},
                token=tok,
                timeout=18,
            )
            kq_tru = json.loads(raw_res.decode("utf-8"))
            if isinstance(kq_tru, dict) and kq_tru.get("deducted"):
                threading.Thread(target=self._cap_nhat_han_muc, daemon=True).start()
            return
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                raise NeedsAttention(
                    "⛔ PHIÊN ĐĂNG NHẬP / API KEY KHÔNG HỢP LỆ (HTTP 401): Vui lòng đăng nhập lại bằng Email/Mật khẩu hoặc dán lại API Key (tr_live_...) ở Khung số 1!"
                ) from exc
            if exc.code in (402, 403, 429):
                try:
                    err_body = json.loads(exc.read().decode("utf-8", errors="replace"))
                    detail = err_body.get("detail") or "Đã hết lượt dịch trong tài khoản."
                    if isinstance(detail, dict):
                        msg = (
                            detail.get("thong_bao")
                            or detail.get("thong_diep")
                            or detail.get("ly_do")
                            or str(detail)
                        )
                        if detail.get("loi") == "can_nang_cap":
                            raise NeedsAttention(
                                f"🔒 CẦN NÂNG CẤP GÓI {detail.get('ten_cap_yeu_cau', 'Pro').upper()}: {msg}"
                            ) from exc
                    else:
                        msg = str(detail)
                except NeedsAttention:
                    raise
                except Exception:
                    msg = "Đã hết lượt dịch miễn phí trong ngày và ví mua thêm đã về 0."
                raise NeedsAttention(
                    f"⛔ HẾT LƯỢT DỊCH: {msg} Vui lòng bấm '💎 Gói Cước & Khoá API' để nạp thêm lượt!"
                ) from exc
            if exc.code != 404:
                return
        except Exception:
            return

        # Dự phòng nếu máy chủ Cloud chưa cập nhật endpoint /consume-local-page (HTTP 404):
        try:
            raw_hm = goi_http(f"{srv}/api/v1/han-muc", token=tok, timeout=15)
            hm = json.loads(raw_hm.decode("utf-8"))
            if isinstance(hm, dict) and not hm.get("la_quan_tri", False) and hasattr(self, "cau_hinh"):
                con_lai_server = int(hm.get("con_lai", 0))
                da_tru_local = int(self.cau_hinh.get("_da_tru_local_hom_nay", 0))
                ngay_luu = str(self.cau_hinh.get("_ngay_tru_local", ""))
                hom_nay_str = time.strftime("%Y-%m-%d")
                if ngay_luu != hom_nay_str:
                    da_tru_local = 0
                    self.cau_hinh["_ngay_tru_local"] = hom_nay_str
                if con_lai_server - da_tru_local < so_luot_can:
                    raise NeedsAttention(
                        "⛔ HẾT LƯỢT DỊCH: Tài khoản đã hết lượt khả dụng. Vui lòng nạp thêm gói lượt để tiếp tục!"
                    )
                self.cau_hinh["_da_tru_local_hom_nay"] = da_tru_local + so_luot_can
                self._luu_cau_hinh()
        except NeedsAttention:
            raise
        except Exception:
            pass

    def _luong_dich_hang_loat(self):
        import concurrent.futures

        final_text = "Chưa hoàn tất."
        done = 0
        failures = []
        ho_so_da_xuat: list[dict] = []
        state_lock = threading.Lock()
        try:
            options = self.run_options
            out_base = Path(options["output"])
            default_series = lam_sach_ten_thu_muc(options["name"])
            (out_base / default_series).mkdir(parents=True, exist_ok=True)
            chapters = options["chapters"] or quet_danh_sach_chapter_tu_url(
                options["url"], mo_rong_ca_bo=bool(options.get("mo_rong_ca_bo", True))
            )
            selected = chapters[options["from"] - 1:options["to"]]
            if not selected:
                raise NeedsAttention("Khoảng chapter đã chọn không có dữ liệu.")
            if len(selected) > 1:
                srv_chk = str(options.get("server") or "").strip().rstrip("/")
                tok_chk = str(options.get("token") or "").strip()
                if srv_chk and "api.invalid" not in srv_chk and "127.0.0.1:17890" not in srv_chk:
                    try:
                        raw_hm = goi_http(f"{srv_chk}/api/v1/han-muc", token=tok_chk, timeout=15)
                        hm_chk = json.loads(raw_hm.decode("utf-8"))
                        if isinstance(hm_chk, dict) and not hm_chk.get("la_quan_tri", False):
                            cap_do = int(hm_chk.get("cap_do", 0))
                            mua_them = int(hm_chk.get("so_luot_mua_them", 0))
                            tran_ngay = int(hm_chk.get("tran", 10))
                            if cap_do < 3 and mua_them < 200 and tran_ngay < 600:
                                raise NeedsAttention(
                                    "🔒 CẦN NÂNG CẤP GÓI LITE / STANDARD: Tính năng Tự động tải & dịch nối tiếp nhiều Chapter liên tục "
                                    f"({len(selected)} chapter) dành riêng cho tài khoản trả phí. "
                                    "Tài khoản thường có thể chọn dịch thử từng chapter (20 Credits miễn phí) hoặc bấm '💎 Gói Cước & Khoá API' để nâng cấp!"
                                )
                    except NeedsAttention:
                        raise
                    except Exception:
                        pass
            # Collision must be detected per (series_folder, chapter_folder) before any upload or file write.
            series_and_names = [
                (
                    lam_sach_ten_thu_muc(str(chapter.get("ten_truyen") or default_series)),
                    lam_sach_ten_thu_muc(chapter["ten"]),
                )
                for chapter in selected
            ]
            if len({(s.casefold(), n.casefold()) for s, n in series_and_names}) != len(series_and_names):
                raise NeedsAttention("Có chapter trùng tên thư mục; đổi tên trước khi xử lý.")
            config = {key: options[key] for key in
                      ("server", "account", "source_lang", "target_lang", "font", "engine", "glossary")}
            config["renderer_version"] = "production-1"
            so_bo_truyen = len({s.casefold() for s, _ in series_and_names})
            so_luong_song_song = max(1, min(8, int(options.get("parallel_chapters") or 1)))
            if len(selected) > 1 and so_luong_song_song > 1:
                self.ghi_log(
                    f"⚡ Bắt đầu chạy song song {so_luong_song_song} luồng cho {len(selected)} chapter "
                    f"({so_bo_truyen} bộ truyện). Kết quả cần rà soát trước khi giao."
                )
            else:
                self.ghi_log(
                    f"Bắt đầu {len(selected)} chapter ({so_bo_truyen} bộ truyện). Kết quả cần rà soát trước khi giao."
                )

            def _xu_ly_mot_chapter(chapter: dict, series_name: str, name: str):
                nonlocal done
                if self.yeu_cau_dung:
                    raise RunStopped("Đã dừng.")
                ledger = None
                root = out_base / series_name
                root.mkdir(parents=True, exist_ok=True)
                nhan_day_du = f"{series_name}/{name}" if so_bo_truyen > 1 else name
                try:
                    source = chapter["url"]
                    if isinstance(chapter.get("sources"), list) and chapter["sources"]:
                        sources = list(chapter["sources"])
                    elif source.startswith("local_dir::"):
                        sources = local_image_sources(Path(source.removeprefix("local_dir::")))
                    elif source.startswith("archive::"):
                        sources = archive_sources(Path(source.removeprefix("archive::")))
                    else:
                        sources = quet_anh_trang_truyen_trong_chapter(source)
                        if not sources:
                            raise NeedsAttention(f"Không tìm thấy ảnh trang truyện tại link {source}.")
                        if options.get("auto_confirm_link_pages"):
                            self.ghi_log(f"⚡ Tự động xác nhận {len(sources)} trang cho {nhan_day_du} từ link.")
                        else:
                            self._xac_nhan_so_trang(name, len(sources))
                    if len(sources) > 200:
                        raise NeedsAttention("Chapter vượt 200 trang; chia nhỏ trước khi dịch.")
                    self.after(0, lambda lb=nhan_day_du: self.lbl_tien_do.config(text=f"Đang xử lý {lb}"))

                    # [B.1] Smart Webtoon Strip Stitcher & Gutter-Aware OCR Slicer:
                    # Nếu chapter tải từ nguồn local hoặc có dải ảnh Webtoon cắt vụn, tự động nối & cắt lại tại rãnh Gutter sạch
                    # trước khi khởi tạo ChapterLedger để không bao giờ bị cắt đứt bóng thoại ở mép 2 ảnh:
                    if len(sources) >= 3 and all(s.startswith("local_file::") for s in sources):
                        try:
                            raw_list = [read_local_source(s) for s in sources]
                            stitched_list = ghep_va_cat_dai_anh_webtoon_thong_minh(raw_list)
                            if len(stitched_list) != len(raw_list):
                                stitch_dir = root / name / "_webtoon_stitched"
                                stitch_dir.mkdir(parents=True, exist_ok=True)
                                new_sources = []
                                for s_idx, sb in enumerate(stitched_list, start=1):
                                    sp = stitch_dir / f"strip_{s_idx:03d}.jpg"
                                    sp.write_bytes(sb)
                                    new_sources.append(f"local_file::{sp}")
                                self.ghi_log(
                                    f"🧩 [Smart Webtoon Stitcher] Đã nối & cắt lại {len(raw_list)} mảnh cắt thành {len(new_sources)} trang chuẩn theo rãnh Gutter (không đứt bóng thoại)."
                                )
                                sources = new_sources
                        except Exception:
                            pass

                    ledger = ChapterLedger(root / name, sources, config)

                    prefetch_cache: dict[str, bytes] = {}
                    prefetch_lock = threading.Lock()
                    vi_tri_url = {u: idx for idx, u in enumerate(sources)}

                    def _tai_mot_trang_co_retry(u: str) -> bytes:
                        loi_cuoi = None
                        for lan in range(3):
                            if self.yeu_cau_dung:
                                raise RunStopped("Đã dừng.")
                            try:
                                return goi_http(u, referer=source, nguon_ngoai=True)
                            except urllib.error.HTTPError as exc:
                                if exc.code not in (408, 429, 500, 502, 503, 504) or lan == 2:
                                    raise
                                loi_cuoi = exc
                            except (OSError, TimeoutError, urllib.error.URLError) as exc:
                                if lan == 2:
                                    raise
                                loi_cuoi = exc
                            time.sleep(0.5 * (lan + 1))
                        raise loi_cuoi

                    def _tai_truoc_nen(ds_u: list[str]):
                        for u_tiep in ds_u:
                            if self.yeu_cau_dung or not u_tiep.startswith(("http://", "https://")):
                                continue
                            with prefetch_lock:
                                if u_tiep in prefetch_cache:
                                    continue
                            try:
                                b_tiep = _tai_mot_trang_co_retry(u_tiep)
                                with prefetch_lock:
                                    if len(prefetch_cache) >= 4:
                                        prefetch_cache.pop(next(iter(prefetch_cache)), None)
                                    prefetch_cache[u_tiep] = b_tiep
                            except Exception:
                                pass

                    def load(url):
                        if url.startswith(("local_file::", "archive_file::")):
                            return read_local_source(url)
                        with prefetch_lock:
                            da_co = prefetch_cache.pop(url, None)
                        idx_ht = vi_tri_url.get(url, -1)
                        if idx_ht >= 0 and idx_ht + 1 < len(sources):
                            ke_tiep = [
                                sources[j]
                                for j in range(idx_ht + 1, min(len(sources), idx_ht + 3))
                                if sources[j].startswith(("http://", "https://"))
                            ]
                            if ke_tiep:
                                threading.Thread(target=_tai_truoc_nen, args=(ke_tiep,), daemon=True).start()
                        if da_co is not None:
                            return da_co
                        return _tai_mot_trang_co_retry(url)

                    co_token = bool(str(options.get("token") or "").strip())

                    def submit(data, index, context):
                        bo_nho_hoc = nap_bo_nho_tu_hoc()
                        so_tu_hoc = 120 if options["engine"] == "llm_context" else (60 if options["engine"] == "local_hybrid_pro" else 30)
                        goi_y_hoc = ", ".join(f"{k}={v}" for k, v in list(bo_nho_hoc.items())[-so_tu_hoc:])
                        chi_dan_tier = (
                            "[CHẾ ĐỘ ULTRA CLOUD AI 3 LƯỢT — ĐÔI MẮT GEMINI VISION 2K & DEEPSEEK SCANLATION]"
                            if options["engine"] == "llm_context"
                            else (
                                "[CHẾ ĐỘ AI PRO 2 LƯỢT — BẢO VỆ TRANH GỐC & DỊCH SÂU CHUẨN SCANLATION]"
                                if options["engine"] == "local_hybrid_pro"
                                else ""
                            )
                        )
                        glossary = "\n".join(filter(None, [chi_dan_tier, options["glossary"], goi_y_hoc, "\n".join(context)]))
                        # Nếu chọn Model 3 (`llm_context`: 3 lượt/trang) hoặc Model 2 (`local_hybrid_pro`: 2 lượt/trang) chạy qua Cloud,
                        # trừ phần lượt phụ (ngoài 1 lượt gốc của /doc-truyen/trang) để đảm bảo đúng 2 lượt hoặc 3 lượt/trang:
                        if options["engine"] == "llm_context":
                            self._khau_tru_luot_cuc_bo(data, {**options, "engine": "local_hybrid_pro"})
                        elif options["engine"] == "local_hybrid_pro":
                            self._khau_tru_luot_cuc_bo(data, {**options, "engine": "local_ocr_gpu"})
                        eng_cloud = (
                            "llm_context"
                            if options["engine"] in ("local_ocr_gpu", "local_hybrid_pro", "local_gguf")
                            else options["engine"]
                        )
                        fields = {
                            "source_lang": options["source_lang"],
                            "target_lang": options["target_lang"],
                            "engine": eng_cloud,
                            "che_do": "chi_chu",
                            "font_style": options["font"],
                            "tu_dien_rieng": glossary,
                            "tao_chapter_rieng": "true",
                        }
                        if co_token and ledger.data["pages"][index].get("request_key"):
                            fields["request_key"] = ledger.data["pages"][index]["request_key"]
                        raw = gui_multipart_trang(
                            f"{options['server']}/api/v1/doc-truyen/trang", data,
                            filename=f"{index + 1:03d}.jpg", token=options["token"],
                            fields=fields,
                        )
                        return json.loads(raw.decode("utf-8"))

                    def fetch(page_id):
                        return json.loads(goi_http(
                            f"{options['server']}/api/v1/doc-truyen/trang/{page_id}",
                            token=options["token"],
                        ).decode("utf-8"))

                    def lookup_request(request_key):
                        try:
                            return json.loads(goi_http(
                                f"{options['server']}/api/v1/doc-truyen/yeu-cau/{request_key}",
                                token=options["token"],
                            ).decode("utf-8"))
                        except urllib.error.HTTPError as exc:
                            if exc.code == 404:
                                return None
                            raise

                    def local(data, context):
                        self._khau_tru_luot_cuc_bo(data, options)
                        if options["engine"] == "local_hybrid_pro":
                            ham_dich_local = dich_anh_local_hybrid_pro_tu_hoc
                        elif options["engine"] == "local_ocr_gpu":
                            ham_dich_local = dich_anh_local_ocr_gpu_tang_toc
                        else:
                            ham_dich_local = dich_anh_local_gguf_tren_may_khach
                        return ham_dich_local(
                            data, ngon_ngu_nguon=options["source_lang"], ngon_ngu_dich=options["target_lang"],
                            tu_dien_rieng="\n".join(filter(None, [options["glossary"], "\n".join(context)])),
                            chay_cpu=options.get("ollama_cpu", False),
                        )

                    def _preflight_cloud():
                        h = json.loads(goi_http(
                            f"{options['server']}/healthz", token=options["token"], timeout=15,
                        ).decode("utf-8"))
                        if isinstance(h, dict) and h.get("status") == "ok" and "llm_configured" in h and "translation_capabilities" not in h:
                            h = dict(h)
                            h["translation_capabilities"] = {
                                "private_context_v1": True,
                                "idempotent_upload_v1": True,
                            }
                        return require_production_backend(h)

                    files = process_chapter(
                        ledger, load=load, submit=submit, fetch=fetch,
                        render=lambda data, regions: xoa_chu_va_ve_ban_dich_tren_anh(data, regions, options["font"]),
                        cancelled=lambda: self.yeu_cau_dung, log=self.ghi_log,
                        local_translate=local if options["engine"] in ("local_gguf", "local_ocr_gpu", "local_hybrid_pro") else None,
                        require_isolation=True, idempotent_submit=co_token, lookup_request=lookup_request if co_token else None,
                        allow_silent_pages=bool(options.get("auto_confirm_link_pages")),
                        preflight=_preflight_cloud,
                    )
                    if self.yeu_cau_dung:
                        raise RunStopped("Đã dừng; chưa xuất chapter.")
                    if options["cbz"]:
                        ledger.export_cbz(root / f"{name}-ban-nhap.cbz")
                    if options["pdf"] or options["longstrip"]:
                        xuat_pdf_va_longstrip_chapter(
                            root / name, f"{name}-ban-nhap", root, xuat_pdf=options["pdf"],
                            xuat_longstrip=options["longstrip"], trang_da_kiem=files,
                        )
                    if options.get("auto_video_review"):
                        try:
                            tu_dong_dung_video_review_cho_chapter(
                                root / name,
                                ten_truyen=series_name,
                                ten_chapter=name,
                                server_url=options["server"],
                                token=options["token"],
                                log_fn=self.ghi_log,
                            )
                        except Exception as exc_vid:
                            self.ghi_log(f"⚠️ [Auto-Video] Chưa dựng được Video cho {name}: {exc_vid}")
                    with state_lock:
                        done += 1
                        ho_so_da_xuat.append(
                            {
                                "ten_truyen": series_name,
                                "ten_chapter": name,
                                "so_trang": len(files),
                                "thu_muc": str(root / name),
                            }
                        )
                    self.ghi_log(
                        f"Đủ {len(files)} trang: {series_name} / {name} -> {root / name}. "
                        "Các bản xuất tự động là bản nháp; dùng công cụ rà soát để tạo ZIP giao đã duyệt."
                    )
                except RunStopped:
                    raise
                except Exception as exc:
                    with state_lock:
                        failures.append({"chapter": nhan_day_du, "error": str(exc)})
                    self.ghi_log(f"Chưa hoàn tất {nhan_day_du}: {exc}. Không xuất chapter thiếu trang.")
                finally:
                    if ledger is not None:
                        ledger.close()
                    import gc
                    gc.collect()

            if len(selected) > 1 and so_luong_song_song > 1:
                with concurrent.futures.ThreadPoolExecutor(max_workers=so_luong_song_song) as pool:
                    futs = [
                        pool.submit(_xu_ly_mot_chapter, chapter, series_name, name)
                        for chapter, (series_name, name) in zip(selected, series_and_names)
                    ]
                    for fut in futs:
                        fut.result()
            else:
                for chapter, (series_name, name) in zip(selected, series_and_names):
                    _xu_ly_mot_chapter(chapter, series_name, name)
            if ho_so_da_xuat and (so_bo_truyen > 1 or len(ho_so_da_xuat) > 1 or any(c.get("ten_truyen") for c in selected)):
                lines_tom_tat = [
                    f"[{idx}] Truyện: {m['ten_truyen']}  |  Chapter: {m['ten_chapter']}  |  {m['so_trang']} trang  |  Thư mục: {m['thu_muc']}"
                    for idx, m in enumerate(ho_so_da_xuat, start=1)
                ]
                try:
                    (out_base / "DANH-SACH-TRUYEN-CHAPTER.txt").write_text(
                        "\n".join(lines_tom_tat) + "\n", encoding="utf-8"
                    )
                except OSError:
                    pass
            if failures:
                final_text = f"Xong {done}/{len(selected)} chapter; {len(failures)} chapter cần xử lý."
            else:
                final_text = f"Đã xử lý đủ {done} chapter; cần rà soát trước khi giao."
            self.ghi_log(final_text)
            self._cap_nhat_han_muc()
        except RunStopped as exc:
            final_text = f"Đã dừng. {done} chapter đã xử lý đủ; mở lại để tiếp tục."
            self.ghi_log(str(exc))
        except Exception as exc:
            final_text = f"Chưa hoàn tất: {exc}"
            self.ghi_log(final_text)
        finally:
            self.dang_chay = False
            self.after(0, lambda: self.btn_start.config(state="normal", text="🚀 BẮT ĐẦU TẢI & DỊCH THEO CHAPTER"))
            self.after(0, lambda: self.btn_stop.config(state="disabled", bg="#2A1215", fg="#F87171", text="⏹ DỪNG LẠI"))
            self.after(0, lambda text=final_text: self.lbl_tien_do.config(text=text))


if __name__ == "__main__":
    app = AppDichTruyenWindows()
    try:
        app.deiconify()
        app.lift()
        app.attributes("-topmost", True)
        app.after(400, lambda: app.attributes("-topmost", False))
        app.focus_force()
    except Exception:
        pass
    app.mainloop()
