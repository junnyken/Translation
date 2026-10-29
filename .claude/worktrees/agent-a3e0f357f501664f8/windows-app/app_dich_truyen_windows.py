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
from tkinter import filedialog, messagebox, scrolledtext, ttk

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

def tim_font_he_thong(loai_font: str, co_chu: int):
    """Tìm font chữ tiếng Việt có sẵn trên Windows theo phong cách thể loại."""
    if ImageFont is None:
        return None
    win_fonts = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts"
    ung_vien_theo_loai = {
        "bangers": ["impact.ttf", "arialbd.ttf", "segoeuib.ttf", "tahomabd.ttf"],
        "comic": ["comicbd.ttf", "comic.ttf", "segoeuib.ttf", "arialbd.ttf"],
        "romance": ["Gabriola.ttf", "segoeuii.ttf", "calibrii.ttf", "ariali.ttf", "segoeui.ttf"],
        "historical": ["timesbi.ttf", "timesbd.ttf", "georgia.ttf", "palabi.ttf", "times.ttf"],
    }
    ds_thu = ung_vien_theo_loai.get(loai_font, ung_vien_theo_loai["comic"]) + [
        "arialbd.ttf",
        "segoeui.ttf",
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


def xoa_chu_va_ve_ban_dich_tren_anh(
    img_bytes: bytes,
    ds_vung: list[dict],
    loai_font: str = "bangers",
) -> bytes:
    """
    Thực hiện xoá sạch chữ gốc trong lòng bong bóng (2D Connected-Component Flood-Fill +
    Rào chắn lãnh thổ Voronoi cho bong bóng đôi) và trình bày bản dịch ngay trên máy khách Windows.
    """
    if Image is None:
        return img_bytes

    anh = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    W, H = anh.size
    px_anh = anh.load()

    vung_hop_le = [v for v in ds_vung if v.get("ban_dich") and v.get("w", 0) > 4 and v.get("h", 0) > 4]
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
        canh_dai = max(w_goc, h_goc)

        mo_x = min(max(int(canh_dai * 1.35), int(W * 0.09)), int(W * 0.24))
        mo_y = min(max(int(canh_dai * 1.35), int(H * 0.08)), int(H * 0.20))
        rx0 = max(1, x_goc - mo_x)
        ry0 = max(1, y_goc - mo_y)
        rx1 = min(W - 1, x_goc + w_goc + mo_x)
        ry1 = min(H - 1, y_goc + h_goc + mo_y)

        rw = max(4, rx1 - rx0)
        rh = max(4, ry1 - ry0)
        cx0 = max(0, x_goc - rx0)
        cy0 = max(0, y_goc - ry0)
        cx1 = min(rw, x_goc + w_goc - rx0)
        cy1 = min(rh, y_goc + h_goc - ry0)

        # Lấy mẫu độ sáng và màu nền thật trong vùng chữ gốc
        ds_lum = []
        ds_r, ds_g, ds_b = [], [], []
        for py in range(cy0, cy1, 2):
            for px in range(cx0, cx1, 2):
                r, g, b = px_anh[rx0 + px, ry0 + py]
                lum = 0.299 * r + 0.587 * g + 0.114 * b
                ds_lum.append(lum)
                ds_r.append(r)
                ds_g.append(g)
                ds_b.append(b)

        ds_lum_sorted = sorted(ds_lum) if ds_lum else [255.0]
        nen_toi = ds_lum_sorted[len(ds_lum_sorted) // 2] < 95.0

        mau_loc = [
            (r, g, b)
            for r, g, b, lum in zip(ds_r, ds_g, ds_b, ds_lum)
            if (lum <= 82 if nen_toi else lum >= 180)
        ]
        if mau_loc:
            mau_loc.sort(key=lambda m: 0.299 * m[0] + 0.587 * m[1] + 0.114 * m[2])
            idx_m = min(len(mau_loc) - 1, int(len(mau_loc) * (0.22 if nen_toi else 0.78)))
            bg_r, bg_g, bg_b = mau_loc[idx_m]
        else:
            bg_r, bg_g, bg_b = (14, 14, 14) if nen_toi else (255, 255, 255)

        # Ranh giới Voronoi với các bóng thoại láng giềng
        ds_lang_gieng = []
        for idx_u, u in enumerate(vung_hop_le):
            if idx_u == idx_v:
                continue
            ucx0 = int(round(u["x"] - rx0))
            ucy0 = int(round(u["y"] - ry0))
            ucx1 = int(round(u["x"] + u["w"] - rx0))
            ucy1 = int(round(u["y"] + u["h"] - ry0))
            if ucx1 < -rw or ucx0 > rw * 2 or ucy1 < -rh or ucy0 > rh * 2:
                continue
            ds_lang_gieng.append((ucx0, ucy0, ucx1, ucy1))

        N = rw * rh
        la_nen = bytearray(N)
        vung_cam = bytearray(N)

        for py in range(rh):
            dvy = cy0 - py if py < cy0 else (py - cy1 if py > cy1 else 0)
            dvy2 = dvy * dvy
            base = py * rw
            for px in range(rw):
                r, g, b = px_anh[rx0 + px, ry0 + py]
                lum = 0.299 * r + 0.587 * g + 0.114 * b
                if (lum <= 72) if nen_toi else (lum >= 192):
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

        # Bước 1: Loang `long_trang` từ hộp chữ gốc ra toàn bộ lòng bong bóng
        long_trang = bytearray(N)
        q = deque()
        for py in range(cy0, cy1):
            base = py * rw
            for px in range(cx0, cx1):
                pos = base + px
                if la_nen[pos] and not long_trang[pos]:
                    long_trang[pos] = 1
                    q.append(pos)

        def la_nen_an_toan(px: int, py: int) -> bool:
            pos = py * rw + px
            if not la_nen[pos] or vung_cam[pos]:
                return False
            if cx0 <= px < cx1 and cy0 <= py < cy1:
                return True
            dem = 0
            if px > 0 and la_nen[pos - 1]:
                dem += 1
            if px + 1 < rw and la_nen[pos + 1]:
                dem += 1
            if py > 0 and la_nen[pos - rw]:
                dem += 1
            if py + 1 < rh and la_nen[pos + rw]:
                dem += 1
            return dem >= 3

        da_duyet = list(q)
        while q:
            pos = q.popleft()
            px = pos % rw
            py = pos // rw
            for nx, ny, npos in (
                (px - 1, py, pos - 1),
                (px + 1, py, pos + 1),
                (px, py - 1, pos - rw),
                (px, py + 1, pos + rw),
            ):
                if 0 <= nx < rw and 0 <= ny < rh and not long_trang[npos]:
                    if la_nen_an_toan(nx, ny):
                        long_trang[npos] = 1
                        q.append(npos)
                        da_duyet.append(npos)

        for pos in da_duyet:
            px = pos % rw
            py = pos // rw
            if px > 0 and la_nen[pos - 1] and not vung_cam[pos - 1]:
                long_trang[pos - 1] = 1
            if px + 1 < rw and la_nen[pos + 1] and not vung_cam[pos + 1]:
                long_trang[pos + 1] = 1
            if py > 0 and la_nen[pos - rw] and not vung_cam[pos - rw]:
                long_trang[pos - rw] = 1
            if py + 1 < rh and la_nen[pos + rw] and not vung_cam[pos + rw]:
                long_trang[pos + rw] = 1

        # Kiểm tra rò rỉ biên (chữ ngoài bong bóng)
        cham_bien = sum(long_trang[px] + long_trang[(rh - 1) * rw + px] for px in range(rw)) + sum(
            long_trang[py * rw] + long_trang[py * rw + rw - 1] for py in range(rh)
        )
        ro_ri_bien = (cham_bien / max(1, (rw + rh) * 2)) > 0.24
        if ro_ri_bien:
            tam_gx = (cx0 + cx1) * 0.5
            tam_gy = (cy0 + cy1) * 0.5
            bk_x = max(12.0, (cx1 - cx0) * 0.5 + max(10, int(w_goc * 0.25)))
            bk_y = max(12.0, (cy1 - cy0) * 0.5 + max(10, int(h_goc * 0.25)))
            for py in range(rh):
                dy = (py - tam_gy) / bk_y
                base = py * rw
                for px in range(rw):
                    dx = (px - tam_gx) / bk_x
                    if dx * dx + dy * dy > 1.0:
                        long_trang[base + px] = 0

        # Bước 2: Loang ngược `ngoai_bong` từ 4 biên ROI
        ngoai_bong = bytearray(N)
        q_out = deque()

        def day_ngoai(pos: int):
            if ngoai_bong[pos] or long_trang[pos]:
                return
            if vung_cam[pos] and la_nen[pos]:
                return
            ngoai_bong[pos] = 1
            q_out.append(pos)

        for px in range(rw):
            day_ngoai(px)
            day_ngoai((rh - 1) * rw + px)
        for py in range(rh):
            day_ngoai(py * rw)
            day_ngoai(py * rw + rw - 1)

        le_x = max(2, int((cx1 - cx0) * 0.08))
        le_y = max(2, int((cy1 - cy0) * 0.08))
        tx0, ty0, tx1, ty1 = cx0 + le_x, cy0 + le_y, cx1 - le_x, cy1 - le_y

        while q_out:
            pos = q_out.popleft()
            px = pos % rw
            py = pos // rw
            for nx, ny, npos in (
                (px - 1, py, pos - 1),
                (px + 1, py, pos + 1),
                (px, py - 1, pos - rw),
                (px, py + 1, pos + rw),
            ):
                if 0 <= nx < rw and 0 <= ny < rh:
                    if not (tx0 <= nx <= tx1 and ty0 <= ny <= ty1):
                        day_ngoai(npos)

        for i in range(N):
            if vung_cam[i]:
                ngoai_bong[i] = 1

        # Bước 2.5: Phân tích thành phần liên thông 2D (Connected Component Analysis - CCA)
        # Quét nới rộng 25% quanh bbox chữ gốc `cx0..cy1` để gom sạch mọi nét chữ hoặc dấu câu
        # bị Gemini cắt hụt thò ra ngoài bbox, rồi nở viền (dilate) 4px chống răng cưa.
        pad_cca_x = max(10, int(round((cx1 - cx0) * 0.25)))
        pad_cca_y = max(10, int(round((cy1 - cy0) * 0.25)))
        sx0 = max(1, cx0 - pad_cca_x)
        sy0 = max(1, cy0 - pad_cca_y)
        sx1 = min(rw - 1, cx1 + pad_cca_x)
        sy1 = min(rh - 1, cy1 + pad_cca_y)
        da_tham_cca = bytearray(N)
        dien_tich_max_net = max(160, int(round((cx1 - cx0) * (cy1 - cy0) * 0.35)))

        for sy in range(sy0, sy1):
            base_s = sy * rw
            for sx in range(sx0, sx1):
                s_idx = base_s + sx
                if da_tham_cca[s_idx] or la_nen[s_idx] or vung_cam[s_idx]:
                    continue
                comp = [s_idx]
                da_tham_cca[s_idx] = 1
                cham_bien_roi = False
                min_cx = max_cx = sx
                min_cy = max_cy = sy
                head_c = 0
                while head_c < len(comp):
                    cur = comp[head_c]
                    head_c += 1
                    cpx = cur % rw
                    cpy = cur // rw
                    if cpx <= 1 or cpx >= rw - 2 or cpy <= 1 or cpy >= rh - 2:
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
                        continue
                    for dj in (-1, 0, 1):
                        ny = cpy + dj
                        if ny < sy0 or ny >= sy1:
                            continue
                        nb = ny * rw
                        for di in (-1, 0, 1):
                            if di == 0 and dj == 0:
                                continue
                            nx = cpx + di
                            if nx < sx0 or nx >= sx1:
                                continue
                            np = nb + nx
                            if not da_tham_cca[np] and not la_nen[np] and not vung_cam[np]:
                                da_tham_cca[np] = 1
                                comp.append(np)
                w_c = max_cx - min_cx + 1
                h_c = max_cy - min_cy + 1
                if (
                    not cham_bien_roi
                    and len(comp) <= dien_tich_max_net
                    and w_c < (sx1 - sx0) * 0.90
                    and h_c < (sy1 - sy0) * 0.90
                ):
                    for p_idx in comp:
                        ngoai_bong[p_idx] = 0

        # Nở viền (Dilation 3px) quanh toàn bộ các điểm `ngoai_bong == 0` để xoá sạch viền mờ JPEG
        ban_goc_ngoai = bytes(ngoai_bong)
        for py in range(2, rh - 2):
            base = py * rw
            for px in range(2, rw - 2):
                pos = base + px
                if ban_goc_ngoai[pos] == 0:
                    for dj in range(-3, 4):
                        nb = (py + dj) * rw
                        for di in range(-3, 4):
                            if di * di + dj * dj <= 10:
                                np = nb + (px + di)
                                if 0 <= np < N and not vung_cam[np]:
                                    ngoai_bong[np] = 0

        # Tô sạch lòng bong bóng (`ngoai_bong == 0`) bằng màu nền `(bg_r, bg_g, bg_b)`
        min_x, min_y, max_x, max_y = cx0, cy0, cx1, cy1
        tong_x, tong_y, dem_trong = 0, 0, 0
        for py in range(rh):
            base = py * rw
            for px in range(rw):
                if ngoai_bong[base + px] == 0:
                    px_anh[rx0 + px, ry0 + py] = (bg_r, bg_g, bg_b)
                    if px < min_x:
                        min_x = px
                    if px + 1 > max_x:
                        max_x = px + 1
                    if py < min_y:
                        min_y = py
                    if py + 1 > max_y:
                        max_y = py + 1
                    tong_x += px
                    tong_y += py
                    dem_trong += 1

        if ro_ri_bien or dem_trong < 16:
            bx = rx0 + max(0, cx0 - int(w_goc * 0.12))
            by = ry0 + max(0, cy0 - int(h_goc * 0.10))
            bw = min(W - bx, int(w_goc * 1.24))
            bh = min(H - by, int(h_goc * 1.20))
        else:
            tam_x = tong_x / dem_trong
            tam_y = tong_y / dem_trong
            # Đo bán kính lòng bong bóng từ tâm trọng lượng `(tam_x, tam_y)`
            half_w = max(w_goc * 0.55, min(tam_x - min_x, max_x - tam_x) * 0.84)
            half_h = max(h_goc * 0.55, min(tam_y - min_y, max_y - tam_y) * 0.84)
            bx = int(round(rx0 + max(min_x, tam_x - half_w)))
            by = int(round(ry0 + max(min_y, tam_y - half_h)))
            bw = max(20, int(round(half_w * 2)))
            bh = max(20, int(round(half_h * 2)))

        hop_ve_chu.append(
            {
                "text": str(v["ban_dich"]).strip(),
                "x": bx,
                "y": by,
                "w": bw,
                "h": bh,
                "nen_toi": nen_toi,
                "bg": (bg_r, bg_g, bg_b),
            }
        )

    # Bước B: Trình bày chữ đã dịch vào đúng tâm từng bong bóng
    draw = ImageDraw.Draw(anh)
    for hop in hop_ve_chu:
        chu = hop["text"].upper() if loai_font == "bangers" else hop["text"]
        bw, bh = hop["w"], hop["h"]
        pad_x = max(4, int(bw * 0.08))
        pad_y = max(3, int(bh * 0.07))
        max_w = max(16, bw - pad_x * 2)
        max_h = max(16, bh - pad_y * 2)

        co_max = min(42, max(14, int(min(bw, bh) * 0.34)))
        co_min = 11
        font_chon = tim_font_he_thong(loai_font, co_min)
        dong_chon = [chu]

        for co in range(co_max, co_min - 1, -1):
            f = tim_font_he_thong(loai_font, co)
            tu = chu.split()
            if not tu:
                break
            dong = []
            hien_tai = tu[0]
            for w_tu in tu[1:]:
                thu = f"{hien_tai} {w_tu}"
                bbox_thu = draw.textbbox((0, 0), thu, font=f)
                if (bbox_thu[2] - bbox_thu[0]) <= max_w:
                    hien_tai = thu
                else:
                    dong.append(hien_tai)
                    hien_tai = w_tu
            dong.append(hien_tai)

            cao_dong = int(co * 1.22)
            tong_cao = len(dong) * cao_dong
            rong_lon_nhat = max((draw.textbbox((0, 0), d, font=f)[2] for d in dong), default=0)
            if tong_cao <= max_h and rong_lon_nhat <= max_w:
                font_chon = f
                dong_chon = dong
                break
            font_chon = f
            dong_chon = dong

        bbox_mau = draw.textbbox((0, 0), "Ág", font=font_chon)
        cao_1_dong = max(12, int((bbox_mau[3] - bbox_mau[1]) * 1.22))
        tong_cao = len(dong_chon) * cao_1_dong
        cur_y = hop["y"] + (bh - tong_cao) // 2
        mau_chu = (255, 255, 255) if hop["nen_toi"] else (15, 23, 42)
        mau_vien = hop["bg"]

        for d in dong_chon:
            bb = draw.textbbox((0, 0), d, font=font_chon)
            w_d = bb[2] - bb[0]
            cur_x = hop["x"] + (bw - w_d) // 2
            # Viền mảnh bảo vệ độ nét
            for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                draw.text((cur_x + dx, cur_y + dy), d, font=font_chon, fill=mau_vien)
            draw.text((cur_x, cur_y), d, font=font_chon, fill=mau_chu)
            cur_y += cao_1_dong

    out = io.BytesIO()
    anh.save(out, format="JPEG", quality=93)
    return out.getvalue()


# ==============================================================================
# 2. BỘ QUÉT LINK TRUYỆN & TẢI ẢNH CHAPTER TỰ ĐỘNG
# ==============================================================================

def goi_http(url: str, method: str = "GET", body: dict | None = None, token: str = "", referer: str = "") -> bytes:
    headers = {
        "User-Agent": USER_AGENT,
        "X-Ma-May-Tinh": MA_MAY_HIEN_THI,
        "X-Ma-Khach": KHACH_ID_MAY_TINH,
        "Cookie": f"khach_id={KHACH_ID_MAY_TINH}",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if referer:
        headers["Referer"] = referer
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read()


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


def dich_anh_local_gguf_tren_may_khach(
    img_bytes: bytes,
    *,
    ngon_ngu_nguon: str = "ja",
    ngon_ngu_dich: str = "vi",
    tu_dien_rieng: str = "",
) -> list[dict]:
    """
    Dịch trên máy khách bằng Qwen3-VL 8B qua Ollama hoặc LM Studio.
    Không gửi ảnh lên máy chủ dịch, không tự tải model hay đổi sang engine khác.
    """

    W, H = 1000, 1400
    if Image is not None:
        try:
            with Image.open(io.BytesIO(img_bytes)) as im_tmp:
                W, H = im_tmp.size
        except Exception:
            pass

    anh_b64 = base64.b64encode(img_bytes).decode("ascii")
    ten_dich = "English" if ngon_ngu_dich == "en" else "Tiếng Việt tự nhiên, chuẩn phong cách truyện tranh"
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

    backend, model = _ket_noi_qwen3_vl_cuc_bo()
    if backend == "ollama":
        data = _goi_json_ai_cuc_bo(
            "http://127.0.0.1:11434/api/chat",
            timeout=180,
            payload={
                "model": model,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.2},
                "messages": [{"role": "user", "content": prompt, "images": [anh_b64]}],
            },
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
            # Giữ khả năng đọc mảng JSON nằm trong Markdown như bản app cũ.
            khop = re.search(r"\[[\s\S]*\]", str(raw_text))
            parsed = json.loads(khop.group(0) if khop else str(raw_text))
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


def xuat_pdf_va_longstrip_chapter(
    tm_chap: Path,
    ten_chap: str,
    thu_muc_goc: Path,
    *,
    xuat_pdf: bool = False,
    xuat_longstrip: bool = False,
) -> list[str]:
    """Tự động đóng gói thêm file .PDF và ghép dải ảnh dài Webtoon (Long-Strip) cho Chapter."""
    if Image is None:
        return []
    ds_file = sorted(tm_chap.glob("*.jpg"))
    if not ds_file:
        return []
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


def quet_danh_sach_chapter_tu_url(url_truyen: str) -> list[dict]:
    """
    Tự động quét danh sách các link Chapter từ trang mục lục của 1 bộ truyện.
    Nếu đường link truyền vào đã là 1 link Chapter trực tiếp thì trả về chính nó.
    """
    html = goi_http(url_truyen, referer=url_truyen).decode("utf-8", errors="ignore")
    parsed_goc = urllib.parse.urlparse(url_truyen)
    base_origin = f"{parsed_goc.scheme}://{parsed_goc.netloc}"

    # Tìm tất cả thẻ <a href="..."> có chứa chữ chapter / chap / chuong / ep
    ung_vien = []
    da_thay = set()
    for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.I | re.S):
        href = m.group(1).strip()
        text = re.sub(r"<[^>]+>", " ", m.group(2)).strip()
        full_url = urllib.parse.urljoin(base_origin, href)
        if not full_url.startswith(("http://", "https://")):
            continue
        if urllib.parse.urlparse(full_url).netloc != parsed_goc.netloc:
            continue

        chuoi_kiem = f"{full_url} {text}".lower()
        khop_chap = re.search(r"(?:chapter|chap|chuong|chương|episode|ep)[-_/\s.]*(\d+(?:\.\d+)?)", chuoi_kiem)
        if not khop_chap:
            continue
        if full_url in da_thay:
            continue
        da_thay.add(full_url)
        so_chap = float(khop_chap.group(1))
        ten_chap = f"Chapter-{int(so_chap):03d}" if so_chap.is_integer() else f"Chapter-{so_chap}"
        ung_vien.append({"so": so_chap, "ten": ten_chap, "url": full_url, "nhan": text or ten_chap})

    if not ung_vien:
        # Coi chính URL vừa dán là 1 Chapter đơn lẻ
        khop_le = re.search(r"(?:chapter|chap|chuong|ep)[-_/\s.]*(\d+(?:\.\d+)?)", url_truyen.lower())
        so = float(khop_le.group(1)) if khop_le else 1.0
        ten = f"Chapter-{int(so):03d}" if so.is_integer() else f"Chapter-{so}"
        return [{"so": so, "ten": ten, "url": url_truyen, "nhan": ten}]

    ung_vien.sort(key=lambda x: x["so"])
    return ung_vien


def quet_anh_trang_truyen_trong_chapter(url_chapter: str) -> list[str]:
    """Trích xuất toàn bộ danh sách URL ảnh trang truyện trong 1 trang đọc Chapter."""
    html = goi_http(url_chapter, referer=url_chapter).decode("utf-8", errors="ignore")
    ds_anh = []
    da_co = set()

    # Quét toàn bộ thuộc tính data-src, data-original, data-lazy-src, src của thẻ <img>
    for m in re.finditer(
        r'<img[^>]+(?:data-src|data-original|data-lazy-src|data-url|src)=["\']([^"\']+)["\']',
        html,
        re.I,
    ):
        raw = m.group(1).strip()
        if not raw or raw.startswith("data:"):
            continue
        full = urllib.parse.urljoin(url_chapter, raw)
        low = full.lower()
        if any(bo in low for bo in ("logo", "avatar", "banner", "icon", "ads", "facebook", "discord", ".svg", ".gif")):
            continue
        if any(duoi in low for duoi in (".jpg", ".jpeg", ".png", ".webp")) or "chapter" in low or "manga" in low:
            if full not in da_co:
                da_co.add(full)
                ds_anh.append(full)
    return ds_anh


# ==============================================================================
# 3. GIAO DIỆN DESKTOP WINDOWS (MANGA STUDIO PRO)
# ==============================================================================

class AppDichTruyenWindows(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("⚡ Manga Studio Pro — App Dịch Truyện Tự Động Theo Link & Chia Thư Mục Chapter (Windows)")
        self.geometry("1040x760")
        self.configure(bg="#0f172a")

        self.cau_hinh = self._doc_cau_hinh()
        self.ds_chapter_quet: list[dict] = []
        self.dang_chay = False
        self.yeu_cau_dung = False

        self._dung_giao_dien()
        # Tự động xác nhận Mã máy tính (HWID) và kiểm tra số lượt còn lại ngay khi mở App
        self.cau_hinh["ma_may_tinh"] = MA_MAY_HIEN_THI
        self._luu_cau_hinh()
        threading.Thread(target=self._cap_nhat_han_muc, kwargs={"ghi_nhat_ky": True}, daemon=True).start()

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

    def _dung_giao_dien(self):
        # Thanh tiêu đề Manga Studio
        header = tk.Frame(self, bg="#1e1b4b", padx=18, pady=12)
        header.pack(fill="x")
        tk.Label(
            header,
            text="🎌 MANGA STUDIO WINDOWS — DỊCH TỰ ĐỘNG THEO LINK & CHIA THƯ MỤC CHAPTER",
            font=("Segoe UI", 13, "bold"),
            fg="#f8fafc",
            bg="#1e1b4b",
        ).pack(side="left")
        self.lbl_han_muc = tk.Label(
            header,
            text=f"🖥️ Mã máy: {MA_MAY_HIEN_THI} · 💎 Đang kiểm tra số lượt...",
            font=("Segoe UI", 10, "bold"),
            fg="#38bdf8",
            bg="#1e1b4b",
        )
        self.lbl_han_muc.pack(side="right")

        # Khung 1: Kết nối Máy chủ, Xác nhận Mã Máy Tính & Tài khoản VIP
        f_auth = tk.LabelFrame(
            self,
            text=" 1. Xác nhận Mã Máy Tính & Tài khoản VIP (Đồng bộ lượt dịch với Web & Tiện ích Chrome) ",
            bg="#1e293b",
            fg="#38bdf8",
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=8,
        )
        f_auth.pack(fill="x", padx=14, pady=(10, 6))

        tk.Label(f_auth, text="Máy chủ:", bg="#1e293b", fg="#cbd5e1").grid(row=0, column=0, sticky="w")
        self.ent_server = tk.Entry(f_auth, width=28, bg="#0f172a", fg="#f8fafc", insertbackground="#fff")
        self.ent_server.insert(0, self.cau_hinh.get("may_chu", "https://translation-api.vibe1.tinhgon.xyz"))
        self.ent_server.grid(row=0, column=1, padx=6)

        tk.Label(f_auth, text="Email:", bg="#1e293b", fg="#cbd5e1").grid(row=0, column=2, sticky="w")
        self.ent_email = tk.Entry(f_auth, width=24, bg="#0f172a", fg="#f8fafc", insertbackground="#fff")
        self.ent_email.insert(0, self.cau_hinh.get("email", ""))
        self.ent_email.grid(row=0, column=3, padx=6)

        tk.Label(f_auth, text="Mật khẩu:", bg="#1e293b", fg="#cbd5e1").grid(row=0, column=4, sticky="w")
        self.ent_pass = tk.Entry(f_auth, width=18, show="*", bg="#0f172a", fg="#f8fafc", insertbackground="#fff")
        self.ent_pass.grid(row=0, column=5, padx=6)

        tk.Button(
            f_auth,
            text="🔑 Đăng nhập & Lưu máy",
            bg="#2563eb",
            fg="#ffffff",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=10,
            command=self._dang_nhap,
        ).grid(row=0, column=6, padx=6)

        # Hàng xác nhận Mã máy tính & Kiểm tra số lượt còn lại
        hang_hwid = tk.Frame(f_auth, bg="#1e293b", pady=6)
        hang_hwid.grid(row=1, column=0, columnspan=7, sticky="ew")
        tk.Label(
            hang_hwid,
            text="🖥️ Mã máy tính xác nhận:",
            bg="#1e293b",
            fg="#fbbf24",
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")
        self.ent_hwid = tk.Entry(
            hang_hwid,
            width=20,
            bg="#0f172a",
            fg="#fbbf24",
            font=("Consolas", 10, "bold"),
            readonlybackground="#0f172a",
        )
        self.ent_hwid.insert(0, MA_MAY_HIEN_THI)
        self.ent_hwid.config(state="readonly")
        self.ent_hwid.pack(side="left", padx=6)

        tk.Button(
            hang_hwid,
            text="📋 Sao chép Mã máy",
            bg="#334155",
            fg="#f8fafc",
            font=("Segoe UI", 8, "bold"),
            relief="flat",
            padx=8,
            command=self._sao_chep_ma_may,
        ).pack(side="left", padx=4)

        tk.Button(
            hang_hwid,
            text="🔄 Xác nhận Mã máy & Kiểm tra số lượt còn lại",
            bg="#059669",
            fg="#ffffff",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=10,
            command=lambda: threading.Thread(
                target=self._cap_nhat_han_muc, kwargs={"ghi_nhat_ky": True}, daemon=True
            ).start(),
        ).pack(side="left", padx=6)

        tk.Button(
            hang_hwid,
            text="🌐 Mở Web comic.io.vn (Nạp VIP / API Key)",
            bg="#7c3aed",
            fg="#ffffff",
            font=("Segoe UI", 8, "bold"),
            relief="flat",
            padx=8,
            command=lambda: webbrowser.open(WEB_CHINH_THUC),
        ).pack(side="left", padx=4)

        self.lbl_chi_tiet_luot = tk.Label(
            hang_hwid,
            text="Đang đồng bộ hạn mức của thiết bị...",
            bg="#1e293b",
            fg="#34d399",
            font=("Segoe UI", 9, "bold"),
        )
        self.lbl_chi_tiet_luot.pack(side="left", padx=10)

        # Khung 2: Nhập Link Truyện / Danh sách Chapter & Quét tự động
        f_link = tk.LabelFrame(
            self,
            text=" 2. Dán Link Bộ Truyện (hoặc nhiều Link Chapter, mỗi dòng 1 link) ",
            bg="#1e293b",
            fg="#f472b6",
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=8,
        )
        f_link.pack(fill="x", padx=14, pady=6)

        hang_url = tk.Frame(f_link, bg="#1e293b")
        hang_url.pack(fill="x")
        tk.Label(hang_url, text="Tên bộ truyện:", bg="#1e293b", fg="#cbd5e1").pack(side="left")
        self.ent_ten_truyen = tk.Entry(hang_url, width=25, bg="#0f172a", fg="#f8fafc", insertbackground="#fff")
        self.ent_ten_truyen.insert(0, "Truyen-Moi")
        self.ent_ten_truyen.pack(side="left", padx=(6, 14))

        tk.Label(hang_url, text="Link truyện / Chapter:", bg="#1e293b", fg="#cbd5e1").pack(side="left")
        self.ent_url = tk.Entry(hang_url, width=52, bg="#0f172a", fg="#f8fafc", insertbackground="#fff")
        self.ent_url.pack(side="left", padx=6, fill="x", expand=True)

        tk.Button(
            hang_url,
            text="🔍 Quét danh sách Chapter",
            bg="#db2777",
            fg="#ffffff",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=12,
            command=self._quet_link_truyen,
        ).pack(side="left", padx=4)

        tk.Button(
            hang_url,
            text="📁 Chọn Thư Mục Ảnh Có Sẵn (Offline)",
            bg="#0d9488",
            fg="#ffffff",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=10,
            command=self._chon_thu_muc_anh_offline,
        ).pack(side="left", padx=4)

        hang_chon_chap = tk.Frame(f_link, bg="#1e293b", pady=6)
        hang_chon_chap.pack(fill="x")
        tk.Label(hang_chon_chap, text="Dịch từ Chapter thứ:", bg="#1e293b", fg="#cbd5e1").pack(side="left")
        self.spin_tu = tk.Spinbox(hang_chon_chap, from_=1, to=9999, width=6, bg="#0f172a", fg="#f8fafc")
        self.spin_tu.pack(side="left", padx=6)
        tk.Label(hang_chon_chap, text="đến Chapter thứ:", bg="#1e293b", fg="#cbd5e1").pack(side="left")
        self.spin_den = tk.Spinbox(hang_chon_chap, from_=1, to=9999, width=6, bg="#0f172a", fg="#f8fafc")
        self.spin_den.delete(0, "end")
        self.spin_den.insert(0, "10")
        self.spin_den.pack(side="left", padx=6)

        self.lbl_so_chap = tk.Label(
            hang_chon_chap,
            text="(Hoặc bấm '📁 Chọn Thư Mục Ảnh Có Sẵn' để dịch ảnh có sẵn trên máy)",
            bg="#1e293b",
            fg="#94a3b8",
        )
        self.lbl_so_chap.pack(side="left", padx=12)

        # Khung 3: Cấu hình Ngôn ngữ, Font chữ & Thư mục xuất file
        f_cfg = tk.LabelFrame(
            self,
            text=" 3. Tuỳ chọn Dịch thuật, Font chữ & Thư mục chia file Chapter ",
            bg="#1e293b",
            fg="#34d399",
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=8,
        )
        f_cfg.pack(fill="x", padx=14, pady=6)

        r1 = tk.Frame(f_cfg, bg="#1e293b")
        r1.pack(fill="x", pady=2)
        tk.Label(r1, text="Ngôn ngữ gốc:", bg="#1e293b", fg="#cbd5e1").pack(side="left")
        self.cmb_src = ttk.Combobox(r1, values=["ja (Nhật)", "ko (Hàn)", "zh (Trung)", "en (Anh)"], width=14, state="readonly")
        self.cmb_src.current(0)
        self.cmb_src.pack(side="left", padx=(6, 16))

        tk.Label(r1, text="Dịch sang:", bg="#1e293b", fg="#cbd5e1").pack(side="left")
        self.cmb_tgt = ttk.Combobox(r1, values=["vi (Tiếng Việt)", "en (English Quốc tế)"], width=18, state="readonly")
        self.cmb_tgt.current(0)
        self.cmb_tgt.pack(side="left", padx=(6, 16))

        tk.Label(r1, text="Font chữ:", bg="#1e293b", fg="#cbd5e1").pack(side="left")
        self.cmb_font = ttk.Combobox(
            r1,
            values=["bangers (⚔️ Hành động)", "comic (💬 Truyện tranh)", "romance (🌸 Ngôn tình)", "historical (📜 Cổ trang)"],
            width=20,
            state="readonly",
        )
        self.cmb_font.current(0)
        self.cmb_font.pack(side="left", padx=(6, 12))

        tk.Label(r1, text="Bộ máy AI:", bg="#1e293b", fg="#cbd5e1").pack(side="left")
        self.cmb_engine = ttk.Combobox(
            r1,
            values=[
                "llm_context (✨ Gemini AI)",
                "google_fast (⚡ Google Nhanh)",
                "local_gguf (Qwen3-VL 8B Offline)",
            ],
            width=30,
            state="readonly",
        )
        self.cmb_engine.current(0)
        self.cmb_engine.pack(side="left", padx=6)

        tk.Button(
            r1,
            text="💻 Kiểm tra Qwen3-VL 8B",
            bg="#15803d",
            fg="#ffffff",
            font=("Segoe UI", 8, "bold"),
            relief="flat",
            padx=8,
            command=self._kiem_tra_gguf_cuc_bo,
        ).pack(side="left", padx=4)

        r_export = tk.Frame(f_cfg, bg="#1e293b", pady=4)
        r_export.pack(fill="x")
        self.var_cbz = tk.BooleanVar(value=bool(self.cau_hinh.get("xuat_cbz", True)))
        tk.Checkbutton(
            r_export,
            text="📦 Đóng gói .CBZ",
            variable=self.var_cbz,
            bg="#1e293b",
            fg="#e2e8f0",
            selectcolor="#0f172a",
            activebackground="#1e293b",
        ).pack(side="left", padx=(0, 12))

        self.var_pdf = tk.BooleanVar(value=bool(self.cau_hinh.get("xuat_pdf", False)))
        tk.Checkbutton(
            r_export,
            text="📕 Xuất thêm .PDF",
            variable=self.var_pdf,
            bg="#1e293b",
            fg="#e2e8f0",
            selectcolor="#0f172a",
            activebackground="#1e293b",
        ).pack(side="left", padx=(0, 12))

        self.var_longstrip = tk.BooleanVar(value=bool(self.cau_hinh.get("xuat_longstrip", False)))
        tk.Checkbutton(
            r_export,
            text="📜 Ghép dải ảnh dài Webtoon (Long-Strip)",
            variable=self.var_longstrip,
            bg="#1e293b",
            fg="#e2e8f0",
            selectcolor="#0f172a",
            activebackground="#1e293b",
        ).pack(side="left", padx=(0, 16))

        tk.Label(r_export, text="📖 Xưng hô / Từ điển cố định:", bg="#1e293b", fg="#cbd5e1").pack(side="left")
        self.ent_tu_dien = tk.Entry(r_export, bg="#0f172a", fg="#f8fafc", insertbackground="#fff")
        self.ent_tu_dien.insert(0, self.cau_hinh.get("tu_dien_rieng", ""))
        self.ent_tu_dien.pack(side="left", padx=6, fill="x", expand=True)

        r2 = tk.Frame(f_cfg, bg="#1e293b", pady=6)
        r2.pack(fill="x")
        tk.Label(r2, text="Thư mục lưu trên máy:", bg="#1e293b", fg="#cbd5e1").pack(side="left")
        self.ent_out = tk.Entry(r2, bg="#0f172a", fg="#f8fafc", insertbackground="#fff")
        self.ent_out.insert(0, self.cau_hinh.get("thu_muc_xuat", str(Path.home() / "Downloads" / "Truyen_Da_Dich")))
        self.ent_out.pack(side="left", padx=6, fill="x", expand=True)

        tk.Button(
            r2,
            text="📂 Chọn thư mục...",
            bg="#334155",
            fg="#f8fafc",
            relief="flat",
            padx=10,
            command=self._chon_thu_muc,
        ).pack(side="left", padx=4)

        tk.Button(
            r2,
            text="🗂️ Mở thư mục kết quả",
            bg="#059669",
            fg="#ffffff",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=10,
            command=self._mo_thu_muc_xuat,
        ).pack(side="left", padx=4)

        # Thanh nút Điều khiển chính
        f_ctrl = tk.Frame(self, bg="#0f172a", padx=14, pady=6)
        f_ctrl.pack(fill="x")
        self.btn_start = tk.Button(
            f_ctrl,
            text="🚀 BẮT ĐẦU TỰ ĐỘNG TẢI & DỊCH THEO CHAPTER",
            bg="#2563eb",
            fg="#ffffff",
            font=("Segoe UI", 11, "bold"),
            relief="flat",
            padx=18,
            pady=8,
            command=self._bat_dau_chay,
        )
        self.btn_start.pack(side="left")

        self.btn_stop = tk.Button(
            f_ctrl,
            text="⏹ Dừng lại (Giữ nguyên các trang đã dịch)",
            bg="#dc2626",
            fg="#ffffff",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=14,
            pady=8,
            state="disabled",
            command=self._dung_chay,
        )
        self.btn_stop.pack(side="left", padx=10)

        self.lbl_tien_do = tk.Label(
            f_ctrl,
            text="Sẵn sàng.",
            bg="#0f172a",
            fg="#38bdf8",
            font=("Segoe UI", 10, "bold"),
        )
        self.lbl_tien_do.pack(side="right")

        # Khung Nhật ký tiến độ trực tiếp
        f_log = tk.LabelFrame(
            self,
            text=" 📋 Nhật ký tiến độ & Danh sách Chapter ",
            bg="#1e293b",
            fg="#94a3b8",
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=6,
        )
        f_log.pack(fill="both", expand=True, padx=14, pady=(2, 12))

        self.txt_log = scrolledtext.ScrolledText(
            f_log,
            bg="#090d16",
            fg="#e2e8f0",
            insertbackground="#fff",
            font=("Consolas", 10),
        )
        self.txt_log.pack(fill="both", expand=True)
        self.ghi_log(
            "✨ Chào mừng bạn đến với App Windows Dịch Truyện Tự Động Theo Link!\n"
            "👉 Bước 1: Dán Link bộ truyện (hoặc link 1 chương) vào ô 'Link truyện / Chapter' rồi bấm '🔍 Quét danh sách Chapter'.\n"
            "👉 Bước 2: Chọn dịch từ Chapter A đến Chapter B và bấm '🚀 BẮT ĐẦU TỰ ĐỘNG TẢI & DỊCH THEO CHAPTER'.\n"
            "👉 Mỗi Chapter sẽ tự động được lưu gọn gàng vào: <Thư_mục_lưu>/<Tên_Truyện>/Chapter-001/001.jpg, 002.jpg...\n"
            "Dịch cục bộ Qwen3-VL 8B: " + HUONG_DAN_QWEN3
        )

    def ghi_log(self, dong: str):
        def _append():
            self.txt_log.insert("end", f"[{time.strftime('%H:%M:%S')}] {dong}\n")
            self.txt_log.see("end")
        self.after(0, _append)

    def _chon_thu_muc(self):
        d = filedialog.askdirectory(initialdir=self.ent_out.get())
        if d:
            self.ent_out.delete(0, "end")
            self.ent_out.insert(0, d)

    def _mo_thu_muc_xuat(self):
        p = Path(self.ent_out.get().strip())
        p.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(p))

    def _sao_chep_ma_may(self):
        self.clipboard_clear()
        self.clipboard_append(MA_MAY_HIEN_THI)
        self.ghi_log(f"📋 Đã sao chép Mã máy tính vào bộ nhớ tạm: {MA_MAY_HIEN_THI}")

    def _dang_nhap(self):
        may_chu = chuan_hoa_may_chu(self.ent_server.get())
        email = self.ent_email.get().strip()
        mat_khau = self.ent_pass.get().strip()
        khoa_api = mat_khau if mat_khau.startswith("tr_live_") else (email if email.startswith("tr_live_") else "")
        if not khoa_api and (not email or not mat_khau):
            messagebox.showwarning(
                "Thiếu thông tin",
                "Vui lòng nhập Email & Mật khẩu (hoặc dán mã API Key tr_live_... vào ô Mật khẩu).",
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
                self.cau_hinh["may_chu"] = may_chu
                self.cau_hinh["email"] = email
                self.cau_hinh["token"] = kq.get("ma_phien", "")
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
            con_lai = int(hm.get("con_lai", 0))
            tran = int(hm.get("tran", 0))
            da_dung = int(hm.get("da_dung", 0))
            mua_them = int(hm.get("so_luot_mua_them", 0))
            tong_kha_dung = con_lai + mua_them
            loai_tk = f"Tài khoản {email}" if (token and email) else f"Máy tính {MA_MAY_HIEN_THI}"

            chu_header = f"🖥️ {MA_MAY_HIEN_THI} · 💎 Tổng còn: {tong_kha_dung} trang (Ngày: {con_lai}/{tran} · VIP: {mua_them})"
            chu_chi_tiet = (
                f"✅ {loai_tk}: Còn {con_lai}/{tran} lượt hôm nay (đã dùng {da_dung}) "
                f"+ {mua_them} lượt gói VIP = Tổng {tong_kha_dung} trang khả dụng"
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

    def _chon_thu_muc_anh_offline(self):
        d = filedialog.askdirectory(title="Chọn thư mục chứa ảnh truyện (hoặc chứa các thư mục Chapter) trên máy tính")
        if not d:
            return
        tm = Path(d)
        self.ent_ten_truyen.delete(0, "end")
        self.ent_ten_truyen.insert(0, tm.name or "Truyen-Offline")
        self.ent_url.delete(0, "end")
        self.ent_url.insert(0, f"local_dir::{tm}")

        # Kiểm tra xem trong thư mục có các thư mục con (Chapter) hay chứa ảnh trực tiếp
        cac_tm_con = sorted([p for p in tm.iterdir() if p.is_dir()])
        ds_chap = []
        if cac_tm_con:
            for idx, sub in enumerate(cac_tm_con, start=1):
                co_anh = any(
                    f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
                    for f in sub.iterdir()
                    if f.is_file()
                )
                if co_anh:
                    ds_chap.append(
                        {
                            "so": float(idx),
                            "ten": sub.name,
                            "url": f"local_dir::{sub}",
                            "nhan": sub.name,
                        }
                    )
        if not ds_chap:
            ds_chap.append(
                {
                    "so": 1.0,
                    "ten": "Chapter-001",
                    "url": f"local_dir::{tm}",
                    "nhan": tm.name,
                }
            )
        self.ds_chapter_quet = ds_chap
        self._cap_nhat_ui_sau_quet(ds_chap)

    def _kiem_tra_gguf_cuc_bo(self):
        def _worker():
            self.ghi_log("💻 Đang kiểm tra Qwen3-VL 8B trên Ollama/LM Studio cục bộ...")
            try:
                backend, model = _ket_noi_qwen3_vl_cuc_bo()
            except LocalServerUnavailableError as exc:
                self.ghi_log(f"ℹ️ {exc}")
                return
            except LocalModelMissingError as exc:
                self.ghi_log(f"⚠️ {exc}")
                return
            except Exception as exc:
                self.ghi_log(f"❌ Không kiểm tra được AI cục bộ: {exc}")
                return
            ten_backend = "Ollama" if backend == "ollama" else "LM Studio"
            self.ghi_log(
                f"✅ {ten_backend} đã có {model}. Nếu muốn dịch bằng model này, hãy tự chọn "
                "'local_gguf (Qwen3-VL 8B Offline)' trong ô 'Bộ máy AI'."
            )

        threading.Thread(target=_worker, daemon=True).start()

    def _quet_link_truyen(self):
        url = self.ent_url.get().strip()
        if not url:
            messagebox.showwarning("Chưa nhập Link", "Vui lòng dán đường link truyện hoặc link chapter vào ô!")
            return
        if url.startswith("local_dir::"):
            self.ghi_log("📁 Đang dùng chế độ Thư mục ảnh có sẵn trên máy.")
            return

        def _worker():
            self.ghi_log(f"🔍 Đang quét danh sách Chapter từ: {url} ...")
            try:
                ds = quet_danh_sach_chapter_tu_url(url)
                self.ds_chapter_quet = ds
                self.after(0, lambda: self._cap_nhat_ui_sau_quet(ds))
            except Exception as exc:
                self.ghi_log(f"❌ Không quét được link: {exc}")

        threading.Thread(target=_worker, daemon=True).start()

    def _cap_nhat_ui_sau_quet(self, ds: list[dict]):
        so_luong = len(ds)
        self.spin_tu.delete(0, "end")
        self.spin_tu.insert(0, "1")
        self.spin_den.delete(0, "end")
        self.spin_den.insert(0, str(so_luong))
        self.lbl_so_chap.config(text=f"✅ Tìm thấy {so_luong} Chapter!", fg="#34d399")
        self.ghi_log(f"✅ Đã tìm thấy {so_luong} Chapter:")
        for idx, ch in enumerate(ds[:30], start=1):
            self.ghi_log(f"   [{idx}] {ch['ten']} -> {ch['url']}")
        if so_luong > 30:
            self.ghi_log(f"   ... và {so_luong - 30} chapter khác.")

    def _dung_chay(self):
        self.yeu_cau_dung = True
        self.ghi_log("⏸ Đang dừng sau khi hoàn tất trang hiện tại...")

    def _bat_dau_chay(self):
        if self.dang_chay:
            return
        url_chinh = self.ent_url.get().strip()
        if not self.ds_chapter_quet and not url_chinh:
            messagebox.showwarning("Chưa có Link", "Hãy dán Link truyện hoặc chọn Thư mục ảnh trước khi bắt đầu!")
            return

        self.dang_chay = True
        self.yeu_cau_dung = False
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        threading.Thread(target=self._luong_dich_hang_loat, daemon=True).start()

    def _luong_dich_hang_loat(self):
        try:
            may_chu = chuan_hoa_may_chu(self.ent_server.get())
            token = self.cau_hinh.get("token", "")
            ten_truyen = lam_sach_ten_thu_muc(self.ent_ten_truyen.get() or "Truyen-Da-Dich")
            thu_muc_goc = Path(self.ent_out.get().strip()) / ten_truyen
            thu_muc_goc.mkdir(parents=True, exist_ok=True)

            ngon_ngu_nguon = self.cmb_src.get().split()[0].strip()
            ngon_ngu_dich = self.cmb_tgt.get().split()[0].strip()
            loai_font = self.cmb_font.get().split()[0].strip()
            engine_dich = self.cmb_engine.get().split()[0].strip()
            tu_dien_goc = self.ent_tu_dien.get().strip()
            xuat_cbz = bool(self.var_cbz.get())
            xuat_pdf = bool(self.var_pdf.get())
            xuat_longstrip = bool(self.var_longstrip.get())

            if not self.ds_chapter_quet:
                self.ds_chapter_quet = quet_danh_sach_chapter_tu_url(self.ent_url.get().strip())

            tu_idx = max(1, int(self.spin_tu.get() or 1))
            den_idx = min(len(self.ds_chapter_quet), int(self.spin_den.get() or len(self.ds_chapter_quet)))
            ds_chay = self.ds_chapter_quet[tu_idx - 1 : den_idx]

            che_do_ten = (
                "💻 QWEN3-VL 8B TRÊN MÁY BẠN (không trừ lượt dịch)"
                if engine_dich == "local_gguf"
                else f"☁️ Máy chủ AI ({engine_dich})"
            )
            self.ghi_log(f"🚀 Bắt đầu dịch {len(ds_chay)} Chapter [{che_do_ten}] -> Lưu tại: {thu_muc_goc}")

            for i_chap, chap in enumerate(ds_chay, start=1):
                if self.yeu_cau_dung:
                    break
                ten_chap = lam_sach_ten_thu_muc(chap["ten"])
                url_chap = chap["url"]
                tm_chap = thu_muc_goc / ten_chap
                tm_chap.mkdir(parents=True, exist_ok=True)

                # Bộ nhớ ngữ cảnh xuyên trang trong cùng Chapter (giữ đồng nhất xưng hô & tên nhân vật)
                bo_nho_ngu_canh_chap: list[str] = []

                if url_chap.startswith("local_dir::"):
                    tm_nguon = Path(url_chap.replace("local_dir::", "", 1))
                    ds_anh = [
                        f"local_file::{p}"
                        for p in sorted(tm_nguon.iterdir())
                        if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
                    ]
                else:
                    self.ghi_log(f"📂 [{i_chap}/{len(ds_chay)}] Đang quét ảnh trong {ten_chap} ({url_chap})...")
                    ds_anh = quet_anh_trang_truyen_trong_chapter(url_chap)

                if not ds_anh:
                    self.ghi_log(f"⚠️ Không tìm thấy ảnh trang truyện trong {url_chap}, bỏ qua.")
                    continue

                self.ghi_log(f"   -> Tìm thấy {len(ds_anh)} trang ảnh. Bắt đầu xử lý...")
                for i_trang, url_anh in enumerate(ds_anh, start=1):
                    if self.yeu_cau_dung:
                        break
                    file_dich = tm_chap / f"{i_trang:03d}.jpg"
                    if file_dich.is_file() and file_dich.stat().st_size > 1024:
                        self.ghi_log(f"   ⏭ Trang {i_trang:03d}.jpg đã có sẵn, bỏ qua (Resume).")
                        continue

                    self.after(
                        0,
                        lambda c=ten_chap, p=i_trang, t=len(ds_anh): self.lbl_tien_do.config(
                            text=f"Đang dịch {c}: Trang {p}/{t}"
                        ),
                    )
                    try:
                        if url_anh.startswith("local_file::"):
                            img_bytes = Path(url_anh.replace("local_file::", "", 1)).read_bytes()
                        else:
                            img_bytes = goi_http(url_anh, referer=url_chap)

                        # Gộp từ điển cố định của người dùng + bộ nhớ ngữ cảnh 10 câu gần nhất của chapter
                        ngu_canh_gop = "\n".join(
                            [s for s in [tu_dien_goc, "\n".join(bo_nho_ngu_canh_chap[-10:])] if s.strip()]
                        )

                        if engine_dich == "local_gguf":
                            vung = dich_anh_local_gguf_tren_may_khach(
                                img_bytes,
                                ngon_ngu_nguon=ngon_ngu_nguon,
                                ngon_ngu_dich=ngon_ngu_dich,
                                tu_dien_rieng=ngu_canh_gop,
                            )
                        else:
                            raw_post = gui_multipart_trang(
                                f"{may_chu}/api/v1/doc-truyen/trang",
                                img_bytes,
                                filename=f"{i_trang:03d}.jpg",
                                fields={
                                    "source_lang": ngon_ngu_nguon,
                                    "target_lang": ngon_ngu_dich,
                                    "engine": engine_dich,
                                    "che_do": "chi_chu",
                                    "font_style": loai_font,
                                    "tu_dien_rieng": ngu_canh_gop,
                                },
                                token=token,
                            )
                            trang_kq = json.loads(raw_post.decode("utf-8"))
                            page_id = trang_kq.get("page_id")

                            while not trang_kq.get("xong") and not self.yeu_cau_dung:
                                time.sleep(1.5)
                                raw_poll = goi_http(f"{may_chu}/api/v1/doc-truyen/trang/{page_id}", token=token)
                                trang_kq = json.loads(raw_poll.decode("utf-8"))

                            if trang_kq.get("trang_thai") == "failed":
                                raise RuntimeError(trang_kq.get("loi") or "Trang dịch lỗi trên máy chủ")

                            vung = trang_kq.get("vung") or []

                        # Cập nhật bộ nhớ ngữ cảnh xuyên trang
                        for item_v in vung:
                            cg = str(item_v.get("chu_goc") or "").strip()
                            bd = str(item_v.get("ban_dich") or "").strip()
                            if cg and bd and len(cg) <= 80 and len(bd) <= 120:
                                dong_nc = f"{cg} = {bd}"
                                if dong_nc not in bo_nho_ngu_canh_chap:
                                    bo_nho_ngu_canh_chap.append(dong_nc)

                        anh_out = xoa_chu_va_ve_ban_dich_tren_anh(img_bytes, vung, loai_font=loai_font)
                        file_dich.write_bytes(anh_out)
                        if engine_dich != "local_gguf":
                            self._cap_nhat_han_muc()
                        self.ghi_log(
                            f"   ✅ Đã lưu {ten_chap}/{file_dich.name} ({len(vung)} bóng thoại)"
                        )
                    except Exception as exc_trang:
                        self.ghi_log(f"   ❌ Lỗi trang {i_trang:03d}: {exc_trang}")

                if xuat_cbz and not self.yeu_cau_dung:
                    cbz_path = thu_muc_goc / f"{ten_chap}.cbz"
                    with zipfile.ZipFile(cbz_path, "w", zipfile.ZIP_DEFLATED) as zf:
                        for f_jpg in sorted(tm_chap.glob("*.jpg")):
                            zf.write(f_jpg, arcname=f_jpg.name)
                    self.ghi_log(f"📦 Đã đóng gói {cbz_path.name}")

                if (xuat_pdf or xuat_longstrip) and not self.yeu_cau_dung:
                    ds_them = xuat_pdf_va_longstrip_chapter(
                        tm_chap,
                        ten_chap,
                        thu_muc_goc,
                        xuat_pdf=xuat_pdf,
                        xuat_longstrip=xuat_longstrip,
                    )
                    if ds_them:
                        self.ghi_log(f"✨ Đã xuất thêm: {', '.join(ds_them)}")

            self._cap_nhat_han_muc()
            self.ghi_log(f"🎉 HOÀN TẤT! Toàn bộ các Chapter đã được chia vào thư mục: {thu_muc_goc}")
        except Exception as exc:
            self.ghi_log(f"❌ Lỗi luồng dịch: {exc}")
        finally:
            self.dang_chay = False
            self.after(0, lambda: self.btn_start.config(state="normal"))
            self.after(0, lambda: self.btn_stop.config(state="disabled"))
            self.after(0, lambda: self.lbl_tien_do.config(text="Đã xong."))


if __name__ == "__main__":
    app = AppDichTruyenWindows()
    app.mainloop()
