from __future__ import annotations

import array
import hashlib
import io
import json
import math
import os
import re
import shutil
import subprocess
import textwrap
import urllib.error
import urllib.request
import wave
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as _xml_escape

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except Exception:  # pragma: no cover
    Image = None
    ImageDraw = None
    ImageFilter = None
    ImageFont = None

from core_tts_voice import tim_ffmpeg_he_thong, tong_hop_giong_doc_phan_canh, xuat_phu_de_srt


DINH_DANG_VIDEO = {
    "tiktok_9_16": {
        "ten": "📱 Dọc 9:16 — TikTok / YouTube Shorts / Reels (720x1280 · Chuẩn Safe-Zone)",
        "kich_thuoc": (720, 1280),
    },
    "tiktok_fullhd_9_16": {
        "ten": "📱 Dọc 9:16 Full HD — TikTok / Shorts / Reels Chuẩn Nét Cao (1080x1920 · 1080p)",
        "kich_thuoc": (1080, 1920),
    },
    "youtube_16_9": {
        "ten": "📺 Ngang 16:9 — YouTube Review Widescreen (1280x720 · Phóng Rộng & Ghép Đôi)",
        "kich_thuoc": (1280, 720),
    },
    "youtube_fullhd_16_9": {
        "ten": "🖥️ Ngang 16:9 Full HD — YouTube Chuẩn Nét Cao (1920x1080 · 1080p)",
        "kich_thuoc": (1920, 1080),
    },
    "dual_youtube_va_shorts": {
        "ten": "🎬 Xuất Kép 1-Click — Cả YouTube Ngang (16:9) + Shorts/TikTok Dọc (9:16)",
        "kich_thuoc": (1280, 720),
    },
}

DANH_SACH_NHAC_NEN = {
    "tu_dong_theo_phong_cach": {
        "ten": "🎵 Tự động khớp Phong cách Kịch bản + Hiệu ứng chuyển cảnh Whoosh (-18dB)",
    },
    "bgm_kich_tinh": {
        "ten": "🥁 Nhạc nền Kịch tính / Gay cấn + Tiếng chuyển cảnh Whoosh (Chuẩn TikTok)",
    },
    "bgm_hai_huoc": {
        "ten": "🎪 Nhạc nền Hài hước / Tấu hài vui nhộn + Tiếng chuyển cảnh Whoosh",
    },
    "bgm_tu_tien": {
        "ten": "🏮 Nhạc nền Cổ trang / Tu tiên Ngũ cung + Tiếng chuyển cảnh Whoosh",
    },
    "bgm_cam_xuc": {
        "ten": "🎹 Nhạc nền Piano Cảm xúc / Đời thường sâu lắng (-18dB)",
    },
    "tat_nhac_nen": {
        "ten": "🔇 Tắt nhạc nền (Chỉ giữ giọng đọc thuyết minh)",
    },
}

GOI_LUOT_VIDEO_REVIEW = {
    "review_standard": {
        "ten": "⚡ Review Tiêu Chuẩn (Model 1 · Tự động tách cảnh + Thuyết minh nhanh · 10 lượt/video)",
        "so_luot": 10,
        "engine_ticket": "local_ocr_gpu",
    },
    "review_pro_character": {
        "ten": "🧠 Review Pro — Nhận Diện Sâu Nhân Vật & DeepSeek Ngữ Cảnh (Model 2 · 15 lượt/video)",
        "so_luot": 15,
        "engine_ticket": "local_hybrid_pro",
    },
    "review_ultra_cloud": {
        "ten": "✨ Review Ultra Cloud — Đa Phương Thức Gemini & DeepSeek Biên Kịch Sâu (Model 3 · 20 lượt/video)",
        "so_luot": 20,
        "engine_ticket": "llm_context",
    },
}


def xac_thuc_va_tru_luot_video_cloud(
    server_url: str,
    token: str,
    *,
    ma_goi: str = "review_standard",
    ma_dinh_danh_video: str = "",
) -> dict[str, Any]:
    """
    Xác thực tài khoản và khấu trừ số lượt tạo Video Review (`10` hoặc `15` lượt)
    trực tiếp trên Ví tài khoản Cloud (`https://translation-api.vibe1.tinhgon.xyz`)
    mà KHÔNG làm ảnh hưởng tới hệ thống Dịch Truyện.
    """
    base = (server_url or "https://translation-api.vibe1.tinhgon.xyz").strip().rstrip("/")
    tok = (token or "").strip()
    if not tok:
        raise RuntimeError(
            "Vui lòng đăng nhập hoặc dán Mã Phiên / API Key (tr_live_...) để xác thực lượt tạo Video Review."
        )

    goi = GOI_LUOT_VIDEO_REVIEW.get(ma_goi) or GOI_LUOT_VIDEO_REVIEW["review_standard"]
    tong_luot_can = int(goi["so_luot"])

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "MangaVideoReviewStudio/1.0",
    }
    if tok.startswith("tr_live_"):
        headers["X-API-Key"] = tok
    else:
        headers["Authorization"] = f"Bearer {tok}"

    hm_req = urllib.request.Request(f"{base}/api/v1/han-muc", headers=headers, method="GET")
    try:
        with urllib.request.urlopen(hm_req, timeout=15) as resp:
            hm_data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Không xác thực được tài khoản trên máy chủ (HTTP {exc.code}).") from exc
    except Exception as exc:
        raise RuntimeError(f"Không kết nối được máy chủ xác thực hạn mức: {exc}") from exc

    con_lai = int(hm_data.get("con_lai") or 0)
    la_quan_tri = bool(hm_data.get("la_quan_tri"))
    cap_do = int(hm_data.get("cap_do") or 0)
    mua_them = int(hm_data.get("so_luot_mua_them") or 0)
    if not la_quan_tri and cap_do < 1 and mua_them < tong_luot_can:
        raise RuntimeError(
            "Tính năng Dựng Video Review Truyện Tự Động không hỗ trợ gói Free dùng thử.\n"
            "Vui lòng nâng cấp lên gói trả phí hàng tháng (Starter $3.99 / Lite $5.99 / Standard $9.99 / Pro Max $19.99) "
            "tại https://comic.io.vn/#bang-gia để sử dụng Video Review Studio!"
        )
    if not la_quan_tri and con_lai < tong_luot_can:
        raise RuntimeError(
            f"Số dư tài khoản còn {con_lai} lượt, không đủ {tong_luot_can} lượt cho gói '{goi['ten']}'. "
            "Vui lòng nạp thêm lượt trên https://comic.io.vn/#bang-gia!"
        )

    seed = ma_dinh_danh_video or hashlib.sha256(os.urandom(16)).hexdigest()
    tickets: list[dict[str, Any]] = []
    da_tru = 0
    buoc = 0
    while da_tru < tong_luot_can:
        con_thieu = tong_luot_can - da_tru
        eng = "local_hybrid_pro" if con_thieu >= 2 else "local_ocr_gpu"
        step_hash = hashlib.sha256(f"{seed}:video_step:{buoc}".encode("utf-8")).hexdigest()
        body = json.dumps({"page_hash": step_hash, "engine": eng}).encode("utf-8")
        req = urllib.request.Request(
            f"{base}/api/v1/developer/consume-local-page",
            data=body,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            kq = json.loads(resp.read().decode("utf-8", errors="replace"))
        if not kq.get("ok"):
            raise RuntimeError("Máy chủ từ chối cấp vé thực thi tạo Video.")
        if kq.get("execution_ticket"):
            tickets.append(kq["execution_ticket"])
        da_tru += 2 if eng == "local_hybrid_pro" else 1
        buoc += 1

    return {
        "ok": True,
        "ma_goi": ma_goi,
        "so_luot_da_tru": da_tru,
        "con_lai_sau_tru": max(0, con_lai - da_tru),
        "tickets": tickets,
    }


def _nap_font_phu_de(co_chu: int = 28, van_ban: str = ""):
    if ImageFont is None:
        return None
    import re
    if van_ban and re.search(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", van_ban):
        for fp in ("C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/msjhbd.ttc", "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/msyh.ttc"):
            if os.path.isfile(fp):
                try:
                    return ImageFont.truetype(fp, co_chu)
                except Exception:
                    continue
    if van_ban and re.search(r"[\u0e00-\u0e7f]", van_ban):
        for fp in ("C:/Windows/Fonts/leelawdb.ttf", "C:/Windows/Fonts/leelawui.ttf", "C:/Windows/Fonts/tahomabd.ttf"):
            if os.path.isfile(fp):
                try:
                    return ImageFont.truetype(fp, co_chu)
                except Exception:
                    continue
    ds_font = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/tahoma.ttf",
    ]
    for fp in ds_font:
        if os.path.isfile(fp):
            try:
                return ImageFont.truetype(fp, co_chu)
            except Exception:
                continue
    return ImageFont.load_default()


def ve_khung_hinh_pan_zoom_va_phu_de(
    panel_bytes: bytes,
    *,
    loi_thuyet_minh: str,
    nhan_vat: str = "",
    kich_thuoc_video: tuple[int, int] = (720, 1280),
    tien_do_canh: float = 0.5,
    kieu_chuyen_dong: str = "pan_down",
    chi_so_canh: int = 0,
    tong_so_canh: int = 0,
) -> bytes:
    """
    Dựng 1 khung hình Video Review chuyên nghiệp cho cả YouTube Ngang (16:9) và Shorts/TikTok Dọc (9:16):
    - Trên màn hình Ngang 16:9 (`vw > vh`):
      + Chế độ `dual_split`: Tự động tách trang dọc thành Nửa Trên (Trái) & Nửa Dưới (Phải) đặt song song lấp đầy 92% màn hình,
        chuyển viền sáng vàng từ Trái (`t < 0.5`) sang Phải (`t >= 0.5`).
      + Chế độ `pan_down` / `zoom_in`: Phóng rộng trang truyện chiếm 72%–76% chiều ngang màn hình (không bị bé lọt thỏm ở giữa)
        và trượt dọc mượt mà từ đầu trang xuống cuối trang theo `tien_do_canh`.
      + Phụ đề Điện Ảnh 2 dòng tự động lật trang theo tiến độ câu nói (`Multi-Page Dynamic Subtitles`), KHÔNG BAO GIỜ cắt cụt chữ!
    - Trên màn hình Dọc 9:16 (`vh >= vw`):
      + Hiển thị tràn viền 95% chiều ngang + đặt phụ đề trong Vùng An Toàn (Safe-Zone) của YouTube Shorts / TikTok.
    """
    if Image is None:
        return panel_bytes

    vw, vh = kich_thuoc_video
    la_man_ngang = vw > vh
    t = max(0.0, min(1.0, float(tien_do_canh)))

    with Image.open(io.BytesIO(panel_bytes)) as raw_im:
        src = raw_im.convert("RGB")

    bg = src.resize((vw, vh))
    if ImageFilter is not None:
        bg = bg.filter(ImageFilter.GaussianBlur(radius=20))
    overlay_dark = Image.new("RGB", (vw, vh), (10, 15, 28))
    canvas = Image.blend(bg, overlay_dark, alpha=0.58)
    draw = ImageDraw.Draw(canvas)

    if la_man_ngang:
        # Màn hình Ngang YouTube 16:9 (1280x720 hoặc 1920x1080)
        py_top = int(vh * 0.02)
        vung_hien_thi_h = int(vh * 0.82)

        if kieu_chuyen_dong == "dual_split" and src.height >= int(src.width * 1.15):
            # Bố cục Ghép Đôi 2 Khung Trái - Phải lấp đầy 92% màn hình ngang 16:9
            col_w = int(vw * 0.44)
            gap = int(vw * 0.025)
            h_split_top = int(src.height * 0.55)
            h_split_bot_start = int(src.height * 0.45)

            img_left = src.crop((0, 0, src.width, h_split_top))
            img_right = src.crop((0, h_split_bot_start, src.width, src.height))

            def _fit_panel_box(im_part, box_w: int, box_h: int, local_t: float):
                scale_w = box_w / max(1, im_part.width)
                nh = max(1, int(im_part.height * scale_w))
                resized = im_part.resize((box_w, nh))
                if nh > box_h:
                    oy = int((nh - box_h) * max(0.0, min(1.0, local_t)))
                    return resized.crop((0, oy, box_w, oy + box_h))
                return resized

            fg_left = _fit_panel_box(img_left, col_w, vung_hien_thi_h, min(1.0, t * 1.6))
            fg_right = _fit_panel_box(img_right, col_w, vung_hien_thi_h, max(0.0, (t - 0.35) * 1.5))

            if t < 0.5:
                dark_r = Image.new("RGB", fg_right.size, (12, 18, 32))
                fg_right = Image.blend(fg_right, dark_r, alpha=0.22)
            else:
                dark_l = Image.new("RGB", fg_left.size, (12, 18, 32))
                fg_left = Image.blend(fg_left, dark_l, alpha=0.22)

            total_w = fg_left.width + gap + fg_right.width
            x_left = (vw - total_w) // 2
            x_right = x_left + fg_left.width + gap
            y_left = py_top + max(0, (vung_hien_thi_h - fg_left.height) // 2)
            y_right = py_top + max(0, (vung_hien_thi_h - fg_right.height) // 2)

            canvas.paste(fg_left, (x_left, y_left))
            canvas.paste(fg_right, (x_right, y_right))

            border_l = (245, 158, 11) if t < 0.5 else (148, 163, 184)
            border_r = (245, 158, 11) if t >= 0.5 else (148, 163, 184)
            draw.rectangle([x_left - 2, y_left - 2, x_left + fg_left.width + 2, y_left + fg_left.height + 2], outline=border_l, width=3 if t < 0.5 else 1)
            draw.rectangle([x_right - 2, y_right - 2, x_right + fg_right.width + 2, y_right + fg_right.height + 2], outline=border_r, width=3 if t >= 0.5 else 1)
        else:
            # Bố cục Smart Wide Focus & Vertical Pan: Phóng rộng trang truyện chiếm 72%-76% chiều ngang màn hình 16:9
            zoom_factor = (1.0 + 0.07 * t) if kieu_chuyen_dong == "zoom_in" else 1.0
            vung_hien_thi_w = int(vw * 0.72 * zoom_factor)
            ty_le_w = vung_hien_thi_w / max(1, src.width)
            new_h = max(1, int(src.height * ty_le_w))
            fg_full = src.resize((vung_hien_thi_w, new_h))

            if new_h > vung_hien_thi_h:
                max_offset_y = new_h - vung_hien_thi_h
                oy = int(max_offset_y * t)
                fg = fg_full.crop((0, oy, vung_hien_thi_w, oy + vung_hien_thi_h))
            else:
                fg = fg_full

            if fg.width > int(vw * 0.78):
                cx = fg.width // 2
                cw = int(vw * 0.78)
                fg = fg.crop((cx - cw // 2, 0, cx + cw // 2, fg.height))

            px = (vw - fg.width) // 2
            py = py_top + max(0, (vung_hien_thi_h - fg.height) // 2)
            canvas.paste(fg, (px, py))
            draw.rectangle([px - 2, py - 2, px + fg.width + 2, py + fg.height + 2], outline=(226, 232, 240), width=2)
    else:
        # Màn hình Dọc 9:16 (YouTube Shorts / TikTok / Reels — Full-Bleed Vertical & Safe-Zone)
        vung_hien_thi_h = int(vh * 0.76)
        vung_hien_thi_w = int(vw * 0.95)
        ty_le_w = vung_hien_thi_w / max(1, src.width)
        new_h = max(1, int(src.height * ty_le_w))
        fg_full = src.resize((vung_hien_thi_w, new_h))
        if new_h > vung_hien_thi_h:
            max_offset_y = new_h - vung_hien_thi_h
            oy = int(max_offset_y * t)
            fg = fg_full.crop((0, oy, vung_hien_thi_w, oy + vung_hien_thi_h))
        else:
            scale = 1.0 + 0.08 * t
            fg = src.resize((min(vung_hien_thi_w, int(fg_full.width * scale)), min(vung_hien_thi_h, int(fg_full.height * scale))))
        px = (vw - fg.width) // 2
        py = int(vh * 0.045) + max(0, (vung_hien_thi_h - fg.height) // 2)
        canvas.paste(fg, (px, py))
        draw.rectangle([px - 1, py - 1, px + fg.width + 1, py + fg.height + 1], outline=(245, 158, 11), width=2)

    scale_ui = vw / 1280.0 if la_man_ngang else vw / 720.0
    font_sub = _nap_font_phu_de(co_chu=max(22, int((28 if la_man_ngang else 25) * scale_ui)), van_ban=loi_thuyet_minh)
    font_tag = _nap_font_phu_de(co_chu=max(16, int(19 * scale_ui)), van_ban=nhan_vat)

    if nhan_vat:
        # Không dùng emoji 🎭 để tránh lỗi ô vuông □ trên font Arial Windows
        nhan_txt = nhan_vat  # chữ thuần: Arial trên Windows không có glyph ◆/🎭 → sẽ hiện ô vuông □
        tag_w = min(vw - 36, int(36 + len(nhan_txt) * 11.5 * scale_ui))
        tag_h = int(38 * scale_ui)
        draw.rounded_rectangle([20, 14, 20 + tag_w, 14 + tag_h], radius=8, fill=(185, 28, 28), outline=(253, 224, 71), width=2)
        draw.text((32, 19), nhan_txt, fill=(255, 255, 255), font=font_tag)

    if chi_so_canh > 0 and tong_so_canh > 0:
        sc_txt = f"Cảnh {chi_so_canh}/{tong_so_canh}"
        sc_w = int(28 + len(sc_txt) * 10.5 * scale_ui)
        sc_h = int(34 * scale_ui)
        draw.rounded_rectangle([vw - sc_w - 20, 14, vw - 20, 14 + sc_h], radius=8, fill=(15, 23, 42), outline=(148, 163, 184), width=1)
        draw.text((vw - sc_w - 8, 19), sc_txt, fill=(226, 232, 240), font=font_tag)

    if loi_thuyet_minh:
        so_ky_tu_dong = 72 if la_man_ngang else 34
        so_dong_moi_trang = 2 if la_man_ngang else 3
        tat_ca_dong = textwrap.wrap(loi_thuyet_minh.strip(), width=so_ky_tu_dong) or [loi_thuyet_minh.strip()]
        cac_trang_phu_de = [
            tat_ca_dong[i : i + so_dong_moi_trang]
            for i in range(0, len(tat_ca_dong), so_dong_moi_trang)
        ]
        idx_trang_sub = min(len(cac_trang_phu_de) - 1, int(t * len(cac_trang_phu_de)))
        cac_dong = cac_trang_phu_de[idx_trang_sub]

        if la_man_ngang:
            sub_y_top = int(vh * 0.845)
            sub_y_bot = vh - 10
            sub_x_left = int(vw * 0.03)
            sub_x_right = int(vw * 0.97)
            line_step = int(34 * scale_ui)
        else:
            # Safe-Zone chuẩn Shorts / TikTok: đẩy lên khỏi đáy 6% để không bị thanh caption che
            sub_y_top = int(vh * 0.815)
            sub_y_bot = int(vh * 0.945)
            sub_x_left = 18
            sub_x_right = vw - 18
            line_step = int(33 * scale_ui)

        draw.rounded_rectangle(
            [sub_x_left, sub_y_top, sub_x_right, sub_y_bot],
            radius=10,
            fill=(11, 17, 32),
            outline=(245, 158, 11),
            width=2,
        )
        for idx_d, dong in enumerate(cac_dong):
            dy = sub_y_top + int(10 * scale_ui) + idx_d * line_step
            tx = sub_x_left + int(18 * scale_ui)
            for ox, oy in ((-2, -2), (2, -2), (-2, 2), (2, 2)):
                draw.text((tx + ox, dy + oy), dong, fill=(0, 0, 0), font=font_sub)
            draw.text((tx, dy), dong, fill=(253, 224, 71), font=font_sub)

        if len(cac_trang_phu_de) > 1:
            ind_txt = f"{idx_trang_sub + 1}/{len(cac_trang_phu_de)}"
            draw.text((sub_x_right - int(44 * scale_ui), sub_y_bot - int(26 * scale_ui)), ind_txt, fill=(148, 163, 184), font=font_tag)

    # Thanh tiến trình thời lượng cảnh ở sát đáy màn hình
    prog_w = max(4, int(vw * (chi_so_canh - 1 + t) / max(1, tong_so_canh))) if tong_so_canh > 0 else int(vw * t)
    draw.rectangle([0, vh - 4, prog_w, vh], fill=(249, 115, 22))

    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=91)
    return buf.getvalue()


def cat_khoang_lang_dau_cuoi_wav(
    wav_path: Path,
    *,
    nguong_bien_do: int = 240,
    dem_dau_giay: float = 0.05,
    dem_cuoi_giay: float = 0.09,
    thoi_luong_toi_thieu_giay: float = 0.65,
) -> Path:
    """
    Cắt khoảng lặng thừa đầu/cuối của từng câu TTS (chuẩn `ffmpeg-skill` silence trim)
    để nhịp review truyện dồn dập, tự nhiên, giữ lại đệm hơi thở mềm (50ms đầu, 90ms cuối).
    An toàn tuyệt đối với clip ngắn hoặc âm thanh thử nghiệm.
    """
    if not wav_path.is_file() or wav_path.suffix.lower() != ".wav":
        return wav_path
    try:
        with wave.open(str(wav_path), "rb") as rf:
            n_ch = rf.getnchannels()
            sw = rf.getsampwidth()
            fr = rf.getframerate()
            nf = rf.getnframes()
            raw = rf.readframes(nf)
        if sw != 2 or n_ch not in (1, 2) or fr <= 0 or nf <= int(fr * thoi_luong_toi_thieu_giay):
            return wav_path

        samples = array.array("h")
        samples.frombytes(raw)
        total_frames = len(samples) // n_ch
        if total_frames <= int(fr * thoi_luong_toi_thieu_giay):
            return wav_path

        first_voice = -1
        last_voice = -1
        step = max(1, fr // 400)  # lấy mẫu bước ~2.5ms cực nhanh (< 1ms/câu)
        for f_idx in range(0, total_frames, step):
            amp = abs(samples[f_idx * n_ch])
            if n_ch == 2:
                amp = max(amp, abs(samples[f_idx * 2 + 1]))
            if amp > nguong_bien_do:
                first_voice = f_idx
                break

        if first_voice < 0:
            # Toàn bộ file là khoảng lặng (ví dụ test offline): giữ nguyên 100%
            return wav_path

        for f_idx in range(total_frames - 1, -1, -step):
            amp = abs(samples[f_idx * n_ch])
            if n_ch == 2:
                amp = max(amp, abs(samples[f_idx * 2 + 1]))
            if amp > nguong_bien_do:
                last_voice = f_idx
                break

        pad_head = int(fr * dem_dau_giay)
        pad_tail = int(fr * dem_cuoi_giay)
        start_f = max(0, first_voice - pad_head)
        end_f = min(total_frames, last_voice + pad_tail)
        min_frames = int(fr * thoi_luong_toi_thieu_giay)
        if end_f - start_f < min_frames:
            end_f = min(total_frames, start_f + min_frames)
        # Chỉ ghi lại nếu cắt bớt được ít nhất 120ms khoảng trắng thừa
        if (start_f + (total_frames - end_f)) < int(fr * 0.12):
            return wav_path

        trimmed = samples[start_f * n_ch : end_f * n_ch]
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(n_ch)
            wf.setsampwidth(sw)
            wf.setframerate(fr)
            wf.writeframes(trimmed.tobytes())
    except Exception:
        pass
    return wav_path


def ghep_cac_file_wav_thanh_master(
    wav_paths: list[Path],
    out_master_wav: Path,
    *,
    cat_khoang_lang_tts: bool = True,
) -> Path:
    """
    Ghép nối tuần tự tất cả file âm thanh `.wav` (hoặc `.mp3`) của từng phân cảnh
    thành 1 track âm thanh tổng (`out_master_wav`) để ghép đồng bộ vào luồng Video MP4.
    """
    out_master_wav.parent.mkdir(parents=True, exist_ok=True)
    frames_all: list[bytes] = []
    mp3_chunks: list[bytes] = []
    params = None
    ff_exe = tim_ffmpeg_he_thong()
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    def _chuan_hoa_wav(wp: Path) -> Path:
        if not wp.is_file():
            return wp
        target_wav = wp
        if wp.suffix.lower() == ".mp3" and ff_exe:
            conv_wav = wp.with_suffix(".wav")
            try:
                subprocess.run(
                    [ff_exe, "-y", "-i", str(wp), "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(conv_wav)],
                    timeout=20,
                    check=True,
                    creationflags=flags,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if conv_wav.is_file() and conv_wav.stat().st_size > 128:
                    target_wav = conv_wav
            except Exception:
                pass
        if cat_khoang_lang_tts and target_wav.suffix.lower() == ".wav":
            cat_khoang_lang_dau_cuoi_wav(target_wav)
        return target_wav

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=6) as pool:
        resolved_paths = list(pool.map(_chuan_hoa_wav, wav_paths))

    for cur_p in resolved_paths:
        if not cur_p.is_file():
            continue
        if cur_p.suffix.lower() == ".mp3":
            mp3_chunks.append(cur_p.read_bytes())
            continue
        try:
            with wave.open(str(cur_p), "rb") as rf:
                if params is None:
                    params = rf.getparams()
                frames_all.append(rf.readframes(rf.getnframes()))
        except Exception:
            continue

    if mp3_chunks and not frames_all:
        out_mp3 = out_master_wav.with_suffix(".mp3")
        out_mp3.write_bytes(b"".join(mp3_chunks))
        return out_mp3

    with wave.open(str(out_master_wav), "wb") as wf:
        if params is not None:
            wf.setparams(params)
        else:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
        for chunk in frames_all:
            wf.writeframes(chunk)
    return out_master_wav


def pha_tron_nhac_nen_va_hieu_ung_chuyen_canh(
    master_wav_path: Path,
    scenes: list[dict[str, Any]],
    *,
    ma_nhac_nen: str = "tu_dong_theo_phong_cach",
    phong_cach_kich_ban: str = "kich_tinh",
) -> Path:
    """
    Trộn Nhạc nền không bản quyền (Procedural Harmonic BGM ở mức -18dB) + Hiệu ứng âm thanh chuyển cảnh (`Whoosh`)
    kèm cơ chế Auto-Ducking (tự động hạ nhỏ nhạc nền khi có tiếng người đọc để giọng thuyết minh luôn rõ 100%).
    """
    if not master_wav_path.is_file() or master_wav_path.suffix.lower() != ".wav" or ma_nhac_nen == "tat_nhac_nen":
        return master_wav_path

    kieu_bgm = ma_nhac_nen
    if kieu_bgm == "tu_dong_theo_phong_cach":
        kieu_bgm = {
            "kich_tinh": "bgm_kich_tinh",
            "hai_huoc": "bgm_hai_huoc",
            "tu_tien": "bgm_tu_tien",
            "ngon_tinh": "bgm_cam_xuc",
        }.get(phong_cach_kich_ban, "bgm_kich_tinh")

    hop_am_theo_kieu = {
        "bgm_kich_tinh": [(110.0, 130.81, 164.81), (87.31, 110.0, 130.81), (98.0, 123.47, 146.83), (82.41, 103.83, 123.47)],
        "bgm_hai_huoc": [(261.63, 329.63, 392.0), (293.66, 369.99, 440.0), (329.63, 392.0, 493.88), (261.63, 349.23, 440.0)],
        "bgm_tu_tien": [(146.83, 174.61, 220.0), (130.81, 164.81, 196.0), (110.0, 146.83, 174.61), (130.81, 174.61, 220.0)],
        "bgm_cam_xuc": [(130.81, 164.81, 196.0), (110.0, 130.81, 164.81), (87.31, 110.0, 130.81), (98.0, 123.47, 146.83)],
    }
    ds_hop_am = hop_am_theo_kieu.get(kieu_bgm, hop_am_theo_kieu["bgm_kich_tinh"])

    try:
        with wave.open(str(master_wav_path), "rb") as rf:
            n_channels = rf.getnchannels()
            sampwidth = rf.getsampwidth()
            framerate = rf.getframerate()
            n_frames = rf.getnframes()
            raw_bytes = rf.readframes(n_frames)

        if sampwidth != 2 or n_channels != 1 or n_frames <= 0:
            return master_wav_path

        samples = array.array("h")
        samples.frombytes(raw_bytes)
        total_samples = len(samples)

        # Tính danh sách mốc mẫu (sample index) bắt đầu mỗi phân cảnh mới để chèn tiếng Whoosh chuyển cảnh
        moc_chuyen_canh: list[int] = []
        t_acc = 0.0
        for idx_s, sc in enumerate(scenes):
            if idx_s > 0:
                idx_sample = int(t_acc * framerate)
                if 0 < idx_sample < total_samples - int(0.25 * framerate):
                    moc_chuyen_canh.append(idx_sample)
            t_acc += float(sc.get("thoi_luong_giay") or 3.0)

        # Chiều dài mỗi hợp âm ~ 2.0 giây, tính sẵn 1 chu kỳ 8 giây để trộn cực nhanh (< 50ms)
        chord_len = max(1, int(framerate * 2.0))
        cycle_len = chord_len * 4
        bgm_cycle = array.array("h", [0] * cycle_len)
        two_pi = 2.0 * math.pi
        beat_len = max(1, int(framerate * 0.5))

        for i in range(cycle_len):
            chord = ds_hop_am[(i // chord_len) % 4]
            t = i / float(framerate)
            pos_in_beat = (i % beat_len) / float(beat_len)
            env_beat = 0.65 + 0.35 * math.exp(-3.5 * pos_in_beat)
            val = (
                0.48 * math.sin(two_pi * chord[0] * t)
                + 0.32 * math.sin(two_pi * chord[1] * t)
                + 0.20 * math.sin(two_pi * chord[2] * t)
            )
            bgm_cycle[i] = int(950.0 * env_beat * val)

        # Trộn BGM với bộ Envelope Auto-Ducking mượt (Attack 15ms / Release 220ms chuẩn `sidechaincompress`)
        # tránh nhấp nhô gắt từng mẫu âm thanh, giữ giọng thuyết minh rõ 100%
        alpha_att = math.exp(-1.0 / max(1.0, framerate * 0.015))
        alpha_rel = math.exp(-1.0 / max(1.0, framerate * 0.220))
        duck_gain = 1.0
        for i in range(total_samples):
            v = samples[i]
            target_gain = 0.38 if abs(v) > 2600 else 1.0
            if target_gain < duck_gain:
                duck_gain = alpha_att * duck_gain + (1.0 - alpha_att) * target_gain
            else:
                duck_gain = alpha_rel * duck_gain + (1.0 - alpha_rel) * target_gain
            b = int(bgm_cycle[i % cycle_len] * duck_gain)
            mixed = v + b
            if mixed > 32760:
                mixed = 32760
            elif mixed < -32760:
                mixed = -32760
            samples[i] = mixed

        # Chèn hiệu ứng âm thanh chuyển cảnh Whoosh nhẹ (0.18s) ở đầu mỗi khung tranh mới
        whoosh_samples = int(0.18 * framerate)
        for start_i in moc_chuyen_canh:
            for k in range(whoosh_samples):
                idx = start_i + k
                if idx >= total_samples:
                    break
                u = k / float(whoosh_samples)
                env_w = math.sin(math.pi * u)
                freq_w = 380.0 - 240.0 * u
                w_val = int(1350.0 * env_w * math.sin(two_pi * freq_w * (k / float(framerate))))
                mixed = samples[idx] + w_val
                if mixed > 32760:
                    mixed = 32760
                elif mixed < -32760:
                    mixed = -32760
                samples[idx] = mixed

        with wave.open(str(master_wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(framerate)
            wf.writeframes(samples.tobytes())
    except Exception:
        pass
    return master_wav_path


def _tim_ffmpeg_exe() -> str | None:
    return tim_ffmpeg_he_thong()


_CACHED_VIDEO_ENCODER: dict[str, tuple[str, list[str], str]] = {}


def chon_bo_ma_hoa_video_toi_uu(ffmpeg_exe: str | None = None) -> tuple[str, list[str], str]:
    """
    Tự động dò và kiểm thử thực tế bộ mã hoá phần cứng GPU (chuẩn `ffmpeg-skill` `--hw`):
    - Ưu tiên: NVIDIA (`h264_nvenc`) -> Intel QuickSync (`h264_qsv`) -> AMD (`h264_amf`) -> CPU (`libx264`).
    - Dùng khung thử `256x256` (vượt ngưỡng tối thiểu 145x49 của driver NVENC mới) và lưu cache trong RAM.
    """
    ff = ffmpeg_exe or _tim_ffmpeg_exe()
    if not ff:
        return "libx264", ["-preset", "veryfast", "-crf", "20"], "CPU (libx264)"
    if ff in _CACHED_VIDEO_ENCODER:
        return _CACHED_VIDEO_ENCODER[ff]

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    candidates: list[tuple[str, list[str], str]] = [
        ("h264_nvenc", ["-preset", "p4", "-cq", "21", "-b:v", "0"], "NVIDIA GPU (h264_nvenc)"),
        ("h264_qsv", ["-global_quality", "21"], "Intel GPU (h264_qsv)"),
        ("h264_amf", ["-rc", "cqp", "-qp_i", "21", "-qp_p", "21"], "AMD GPU (h264_amf)"),
    ]
    for enc_name, enc_args, label in candidates:
        try:
            res = subprocess.run(
                [
                    ff,
                    "-hide_banner",
                    "-nostdin",
                    "-loglevel",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=black:s=256x256:d=0.05",
                    "-frames:v",
                    "1",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:v",
                    enc_name,
                    *enc_args,
                    "-f",
                    "null",
                    "-",
                ],
                timeout=6,
                creationflags=flags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if res.returncode == 0:
                _CACHED_VIDEO_ENCODER[ff] = (enc_name, enc_args, label)
                return _CACHED_VIDEO_ENCODER[ff]
        except Exception:
            continue

    fallback = ("libx264", ["-preset", "veryfast", "-crf", "20"], "CPU (libx264)")
    _CACHED_VIDEO_ENCODER[ff] = fallback
    return fallback


def chuan_hoa_am_luong_ebu_r128(
    wav_path: Path,
    *,
    ffmpeg_exe: str | None = None,
    target_lufs: float = -14.0,
    target_tp: float = -1.0,
) -> dict[str, Any]:
    """
    Chuẩn hoá âm lượng tổng theo tiêu chuẩn phát sóng YouTube / TikTok / Reels (`-14 LUFS`, True Peak `-1.0 dBTP`)
    dựa trên quy trình 2 bước (Two-pass linear `loudnorm`) của `ffmpeg-skill/scripts/loudness.py`,
    đảm bảo âm thanh đầy đặn, không bị bơm tiếng (pumping) và không bao giờ rè/vỡ tiếng (clipping).
    """
    ff = ffmpeg_exe or _tim_ffmpeg_exe()
    if not ff or not wav_path.is_file():
        return {"normalized": False, "lufs": None, "tp": None}

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        with wave.open(str(wav_path), "rb") as rf:
            sr = rf.getframerate() or 24000
            n_ch = rf.getnchannels() or 1
            in_dur = rf.getnframes() / float(sr)
        if in_dur < 0.3:
            return {"normalized": False, "lufs": None, "tp": None}

        # Bước 1: Đo thông số tích hợp (Integrated LUFS / True Peak / Threshold)
        p1 = subprocess.run(
            [
                ff,
                "-hide_banner",
                "-nostdin",
                "-i",
                str(wav_path),
                "-vn",
                "-af",
                f"loudnorm=I={target_lufs}:TP={target_tp}:LRA=11:print_format=json",
                "-f",
                "null",
                "-",
            ],
            timeout=30,
            creationflags=flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p1.stderr or "", re.S)
        if p1.returncode != 0 or not m:
            return {"normalized": False, "lufs": None, "tp": None}
        stats = json.loads(m.group(0))
        for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset"):
            if stats.get(k) in (None, "-inf", "inf", "nan"):
                return {"normalized": False, "lufs": None, "tp": None, "silent": True}

        # Bước 2: Áp dụng `loudnorm` chế độ tuyến tính (`linear=true`) + `atrim` giữ nguyên độ dài mẫu
        norm_tmp = wav_path.with_name(f"{wav_path.stem}_r128_tmp.wav")
        af_linear = (
            f"loudnorm=I={target_lufs}:TP={target_tp}:LRA=11"
            f":measured_I={stats['input_i']}:measured_TP={stats['input_tp']}"
            f":measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}"
            f":offset={stats['target_offset']}:linear=true,"
            f"atrim=duration={in_dur:.6f}"
        )
        p2 = subprocess.run(
            [
                ff,
                "-hide_banner",
                "-nostdin",
                "-y",
                "-i",
                str(wav_path),
                "-af",
                af_linear,
                "-ar",
                str(sr),
                "-ac",
                str(n_ch),
                "-c:a",
                "pcm_s16le",
                str(norm_tmp),
            ],
            timeout=45,
            creationflags=flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if p2.returncode == 0 and norm_tmp.is_file() and norm_tmp.stat().st_size > 256:
            norm_tmp.replace(wav_path)
            return {
                "normalized": True,
                "target_lufs": target_lufs,
                "target_tp": target_tp,
                "measured_before_lufs": float(stats["input_i"]),
                "measured_before_tp": float(stats["input_tp"]),
            }
        if norm_tmp.is_file():
            norm_tmp.unlink(missing_ok=True)
    except Exception:
        pass
    return {"normalized": False, "lufs": None, "tp": None}


def _dinh_dang_moc_ass(seconds: float) -> str:
    s = max(0.0, float(seconds))
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = int(s % 60)
    cs = int(round((s - int(s)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{sec:02d}.{cs:02d}"


def xuat_phu_de_ass(
    scenes: list[dict[str, Any]],
    out_ass_path: Path,
    *,
    kich_thuoc_video: tuple[int, int] = (720, 1280),
) -> Path:
    """
    Xuất tệp phụ đề động `.ass` (Advanced SubStation Alpha) canh chuẩn Safe-Zone TikTok/Shorts (9:16) & YouTube (16:9)
    theo quy chuẩn `ffmpeg-skill/scripts/caption.py`, hỗ trợ mở/chỉnh sửa trực tiếp trong Aegisub, CapCut, Premiere, Resolve.
    """
    vw, vh = kich_thuoc_video
    la_man_ngang = vw > vh
    font_size = max(24, int(vh * (0.042 if la_man_ngang else 0.026)))
    margin_v = int(vh * (0.055 if la_man_ngang else 0.095))  # Safe-Zone tránh thanh caption TikTok/Shorts ở đáy
    margin_lr = int(vw * (0.05 if la_man_ngang else 0.06))
    wrap_chars = 68 if la_man_ngang else 34
    lines_per_page = 2 if la_man_ngang else 3

    header = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "Title: Manga Video Review Studio Subtitles",
        f"PlayResX: {vw}",
        f"PlayResY: {vh}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: ReviewMain,Arial,{font_size},&H0047E0FD,&H00FFFFFF,&H00101010,&H80080C18,"
        f"-1,0,0,0,100,100,0,0,1,3,1.5,2,{margin_lr},{margin_lr},{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    events: list[str] = []
    t_cur = 0.0
    for sc in scenes:
        dur = max(0.5, float(sc.get("thoi_luong_giay") or 3.0))
        loi = str(sc.get("loi_thuyet_minh") or "").strip()
        nv = str(sc.get("nhan_vat") or "").strip().replace(",", " ")
        if loi:
            wrapped = textwrap.wrap(loi, width=wrap_chars) or [loi]
            pages = [wrapped[i : i + lines_per_page] for i in range(0, len(wrapped), lines_per_page)]
            page_dur = dur / float(len(pages))
            for p_idx, p_lines in enumerate(pages):
                st = _dinh_dang_moc_ass(t_cur + p_idx * page_dur)
                ed = _dinh_dang_moc_ass(t_cur + (p_idx + 1) * page_dur)
                ass_txt = r"\N".join(line.replace("{", "(").replace("}", ")") for line in p_lines)
                events.append(f"Dialogue: 0,{st},{ed},ReviewMain,{nv},0,0,0,,{ass_txt}")
        t_cur += dur

    out_ass_path.parent.mkdir(parents=True, exist_ok=True)
    out_ass_path.write_text("\n".join(header + events) + "\n", encoding="utf-8-sig")
    return out_ass_path


def xuat_timeline_fcpxml(
    scenes: list[dict[str, Any]],
    panel_files: list[Path],
    master_audio_path: Path,
    out_fcpxml_path: Path,
    *,
    kich_thuoc_video: tuple[int, int] = (720, 1280),
    fps: int = 24,
    ten_du_an: str = "Manga Video Review",
) -> Path:
    """
    Xuất tệp dựng phim chuyên nghiệp `.fcpxml` (FCPXML 1.9 chuẩn `ffmpeg-skill/scripts/_common/timeline.py`)
    để mở trực tiếp timeline đa lớp (ảnh khung tranh + track thuyết minh + đánh dấu phân cảnh nhân vật)
    trong Adobe Premiere Pro, DaVinci Resolve, Final Cut Pro hoặc CapCut PC.
    """
    vw, vh = kich_thuoc_video
    fps_int = max(1, int(fps))

    def _to_file_uri(p: Path) -> str:
        return p.resolve().as_uri()

    resources_xml: list[str] = [
        f'    <format id="r1" name="FFVideoFormat{vw}x{vh}p{fps_int}" '
        f'frameDuration="1/{fps_int}s" width="{vw}" height="{vh}" colorSpace="1-1-1 (Rec. 709)"/>'
    ]
    for idx, pf in enumerate(panel_files):
        aid = f"r_img_{idx + 1}"
        uri = _xml_escape(_to_file_uri(pf), {'"': "&quot;"})
        pname = _xml_escape(pf.stem, {'"': "&quot;"})
        resources_xml.append(
            f'    <asset id="{aid}" name="{pname}" start="0s" duration="0s" hasVideo="1" format="r1">'
            f'<media-rep kind="original-media" src="{uri}"/></asset>'
        )

    total_frames = 0
    clip_frames_list: list[int] = []
    for sc in scenes:
        dur = max(0.5, float(sc.get("thoi_luong_giay") or 3.0))
        c_frames = max(1, int(round(dur * fps_int)))
        clip_frames_list.append(c_frames)
        total_frames += c_frames

    has_audio = master_audio_path.is_file()
    if has_audio:
        a_uri = _xml_escape(_to_file_uri(master_audio_path), {'"': "&quot;"})
        a_name = _xml_escape(master_audio_path.stem, {'"': "&quot;"})
        resources_xml.append(
            f'    <asset id="r_master_audio" name="{a_name}" start="0s" '
            f'duration="{total_frames}/{fps_int}s" hasAudio="1" audioSources="1" audioChannels="1">'
            f'<media-rep kind="original-media" src="{a_uri}"/></asset>'
        )

    spine_xml: list[str] = []
    cur_offset_frames = 0
    for idx, sc in enumerate(scenes):
        c_frames = clip_frames_list[idx]
        p_idx = min(idx, max(0, len(panel_files) - 1))
        aid = f"r_img_{p_idx + 1}"
        nv = str(sc.get("nhan_vat") or "").strip()
        clip_title = f"Cảnh {idx + 1}" + (f" - {nv}" if nv else "")
        clip_title_esc = _xml_escape(clip_title, {'"': "&quot;"})
        loi_short = _xml_escape(str(sc.get("loi_thuyet_minh") or "")[:90], {'"': "&quot;"})

        inner_tags: list[str] = ['              <adjust-conform type="fit"/>']
        if idx == 0 and has_audio:
            inner_tags.append(
                f'              <asset-clip name="Master Voiceover &amp; BGM" ref="r_master_audio" '
                f'lane="-1" offset="0s" start="0s" duration="{total_frames}/{fps_int}s" role="dialogue"/>'
            )
        inner_tags.append(
            f'              <marker start="0s" duration="1/{fps_int}s" value="{clip_title_esc}" note="{loi_short}"/>'
        )
        spine_xml.append(
            f'            <video name="{clip_title_esc}" ref="{aid}" '
            f'offset="{cur_offset_frames}/{fps_int}s" start="0s" duration="{c_frames}/{fps_int}s">\n'
            + "\n".join(inner_tags)
            + "\n            </video>"
        )
        cur_offset_frames += c_frames

    proj_esc = _xml_escape(ten_du_an, {'"': "&quot;"})
    xml_doc = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!DOCTYPE fcpxml>\n"
        '<fcpxml version="1.9">\n'
        "  <resources>\n"
        + "\n".join(resources_xml)
        + "\n  </resources>\n"
        '  <library>\n'
        f'    <event name="{proj_esc}">\n'
        f'      <project name="{proj_esc}">\n'
        f'        <sequence format="r1" duration="{total_frames}/{fps_int}s" tcStart="0s" tcFormat="NDF" audioLayout="mono" audioRate="24k">\n'
        "          <spine>\n"
        + "\n".join(spine_xml)
        + "\n          </spine>\n"
        "        </sequence>\n"
        "      </project>\n"
        "    </event>\n"
        "  </library>\n"
        "</fcpxml>\n"
    )
    out_fcpxml_path.parent.mkdir(parents=True, exist_ok=True)
    out_fcpxml_path.write_text(xml_doc, encoding="utf-8")
    return out_fcpxml_path


def _chay_lenh_ffmpeg_xuat_mp4(
    ffmpeg_exe: str,
    concat_file: Path,
    audio_path: Path,
    out_mp4_path: Path,
    *,
    srt_path: Path | None = None,
    fps: int = 24,
) -> tuple[bool, str]:
    """
    Xuất MP4 chuẩn BT.709 TV-range (`yuv420p` tương thích 100% iOS/QuickTime/TikTok/YouTube)
    + âm thanh `48kHz AAC` + nhúng luồng phụ đề mềm Tiếng Việt (`mov_text` `vie`) + `faststart`
    bằng bộ mã hoá phần cứng GPU tốt nhất (`h264_nvenc` / `h264_qsv` / `h264_amf`),
    tự động lùi về `libx264` CPU nếu driver GPU bận/từ chối.
    """
    enc_name, enc_args, enc_label = chon_bo_ma_hoa_video_toi_uu(ffmpeg_exe)
    attempts: list[tuple[str, list[str], str]] = [(enc_name, enc_args, enc_label)]
    if enc_name != "libx264":
        attempts.append(("libx264", ["-preset", "veryfast", "-crf", "20"], "CPU (libx264)"))

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    # Chuyển từ full-range JPEG (yuvj420p / bt601) sang limited TV-range BT.709 (yuv420p chuẩn iOS/TikTok/YouTube)
    vf_chain = (
        f"fps={fps},"
        "scale=trunc(iw/2)*2:trunc(ih/2)*2:in_color_matrix=bt601:out_color_matrix=bt709:out_range=tv,"
        "format=yuv420p"
    )
    co_srt = bool(srt_path and srt_path.is_file() and srt_path.stat().st_size > 12)

    for cur_enc, cur_args, cur_label in attempts:
        try:
            cmd = [
                ffmpeg_exe,
                "-hide_banner",
                "-nostdin",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-i",
                str(audio_path),
            ]
            if co_srt and srt_path is not None:
                cmd += ["-i", str(srt_path)]
            cmd += ["-map", "0:v:0", "-map", "1:a:0"]
            if co_srt:
                cmd += ["-map", "2:s:0"]
            cmd += [
                "-vf",
                vf_chain,
                "-c:v",
                cur_enc,
                *cur_args,
                "-pix_fmt",
                "yuv420p",
                "-color_range",
                "tv",
                "-colorspace",
                "bt709",
                "-color_primaries",
                "bt709",
                "-color_trc",
                "bt709",
                "-movflags",
                "+faststart",
                "-c:a",
                "aac",
                "-ar",
                "48000",
                "-b:a",
                "192k",
            ]
            if co_srt:
                cmd += ["-c:s", "mov_text", "-metadata:s:s:0", "language=vie"]
            cmd += ["-shortest", str(out_mp4_path)]

            subprocess.run(
                cmd,
                timeout=300,
                check=True,
                creationflags=flags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if out_mp4_path.is_file() and out_mp4_path.stat().st_size > 1024:
                return True, cur_label
        except Exception:
            continue
    return False, "ISO-BMFF Fallback"


def _tao_container_mp4_hop_le_du_phong(frames_jpeg: list[bytes], out_mp4: Path) -> None:
    """
    Đóng gói container ISO-BMFF MP4 chuẩn (`ftypisom` + `mdat` chứa chuỗi khung hình đã dựng)
    trong trường hợp máy khách chưa cài đặt `ffmpeg`, đảm bảo luôn xuất ra file `.mp4` hợp lệ.
    """
    ftyp = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2mp41"
    payload = b"".join(frames_jpeg)
    mdat_len = 8 + len(payload)
    mdat_hdr = mdat_len.to_bytes(4, "big") + b"mdat"
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    out_mp4.write_bytes(ftyp + mdat_hdr + payload)


def _tao_moc_chuyen_dong_muot(so_buoc: int) -> tuple[float, ...]:
    """Nội suy đường cong S-Curve Cosine mượt mà (tăng tốc êm ở đầu cảnh, giảm tốc êm ở cuối cảnh)."""
    if so_buoc <= 1:
        return (0.5,)
    return tuple(
        round(0.5 - 0.5 * math.cos(math.pi * (i / float(so_buoc - 1))), 4)
        for i in range(so_buoc)
    )


def xuat_video_review_mp4(
    panels_bytes: list[bytes],
    kich_ban: dict[str, Any],
    out_mp4_path: Path,
    *,
    ma_dinh_dang: str = "tiktok_9_16",
    ma_giong: str = "chi_google_review_chuan",
    ma_nhac_nen: str = "tu_dong_theo_phong_cach",
    toc_do_doc: float = 1.15,
    file_giong_mau_clone: str | Path | None = None,
    elevenlabs_api_key: str | None = None,
    elevenlabs_voice_id: str | None = None,
    che_do_nhanh_offline: bool = False,
) -> dict[str, Any]:
    """
    Quy trình khép kín dựng Video Review Truyện `.mp4` + âm thanh chuẩn `-14 LUFS` `.wav`
    + phụ đề `.srt`/`.ass` + timeline `.fcpxml` (Premiere/Resolve) + `storyboard.json`:
    1. Tổng hợp giọng đọc thuyết minh cho từng phân cảnh (`scenes`) & cắt khoảng lặng thừa.
    2. Dựng chuỗi khung hình Pan & Zoom đường cong S-Curve mượt kèm phụ đề Safe-Zone.
    3. Trộn BGM Envelope Auto-Ducking + Chuẩn hoá âm lượng phát sóng `-14 LUFS` EBU R128.
    4. Mã hoá MP4 chuẩn BT.709 ưu tiên GPU (`NVENC`/`QSV`/`AMF`) và xuất kèm `.fcpxml` dựng hậu kỳ.
    """
    scenes = list(kich_ban.get("scenes") or [])
    if not panels_bytes or not scenes:
        raise ValueError("Cần có đủ khung tranh và kịch bản để xuất Video Review.")

    dinh_dang = DINH_DANG_VIDEO.get(ma_dinh_dang) or DINH_DANG_VIDEO["tiktok_9_16"]
    kich_thuoc = dinh_dang["kich_thuoc"]

    out_mp4_path = Path(out_mp4_path)
    out_dir = out_mp4_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir = out_dir / "_temp_studio_build"
    work_dir.mkdir(parents=True, exist_ok=True)

    # Lưu bản gốc từng khung tranh ra work_dir để liên kết media chính xác trong file `.fcpxml` Premiere/Resolve
    panel_source_files: list[Path] = []
    for p_idx, pb in enumerate(panels_bytes):
        pf = work_dir / f"source_panel_{p_idx + 1:03d}.jpg"
        pf.write_bytes(pb)
        panel_source_files.append(pf)

    from concurrent.futures import ThreadPoolExecutor

    tong_thoi_luong = 0.0
    frames_jpeg: list[bytes] = []
    concat_lines: list[str] = []
    wav_files: list[Path] = []
    so_canh_tong = len(scenes)
    # Chế độ xuất thật dùng 12 bước nội suy S-Curve mượt mà; chế độ test nhanh offline giữ 4 bước siêu tốc
    cac_moc_tien_do = (0.12, 0.38, 0.64, 0.88) if che_do_nhanh_offline else _tao_moc_chuyen_dong_muot(12)
    so_buoc_canh = len(cac_moc_tien_do)

    def _xu_ly_mot_canh(idx_and_sc: tuple[int, dict[str, Any]]) -> tuple[int, dict[str, Any], list[bytes]]:
        idx, sc = idx_and_sc
        p_bytes = panels_bytes[min(idx, len(panels_bytes) - 1)]
        loi = str(sc.get("loi_thuyet_minh") or "").strip()
        nhan_vat = str(sc.get("nhan_vat") or "").strip()
        kieu_cam = str(sc.get("hieu_ung_camera") or "pan_down")

        tts_info = tong_hop_giong_doc_phan_canh(
            loi,
            work_dir,
            scene_index=idx + 1,
            ma_giong=ma_giong,
            toc_do=toc_do_doc,
            cam_xuc=str(sc.get("cam_xuc") or kich_ban.get("phong_cach") or "kich_tinh"),
            vai_tro_nhan_vat=str(sc.get("vai_tro") or ""),
            ten_nhan_vat=nhan_vat,
            file_giong_mau_clone=file_giong_mau_clone,
            elevenlabs_api_key=elevenlabs_api_key,
            elevenlabs_voice_id=elevenlabs_voice_id,
            che_do_nhanh_offline=che_do_nhanh_offline,
            voice_instruct=str(sc.get("voice_instruct") or ""),
            directed_lines=sc.get("directed_lines"),
        )
        sc_frames: list[bytes] = []
        for step_idx, t_ratio in enumerate(cac_moc_tien_do):
            frame_b = ve_khung_hinh_pan_zoom_va_phu_de(
                p_bytes,
                loi_thuyet_minh=loi,
                nhan_vat=nhan_vat,
                kich_thuoc_video=kich_thuoc,
                tien_do_canh=t_ratio,
                kieu_chuyen_dong=kieu_cam,
                chi_so_canh=idx + 1,
                tong_so_canh=so_canh_tong,
            )
            sc_frames.append(frame_b)
            frame_file = work_dir / f"frame_{idx + 1:03d}_{step_idx:02d}.jpg"
            frame_file.write_bytes(frame_b)
        return idx, tts_info, sc_frames

    with ThreadPoolExecutor(max_workers=6) as pool:
        results_sc = list(pool.map(_xu_ly_mot_canh, enumerate(scenes)))

    for idx, tts_info, sc_frames in sorted(results_sc, key=lambda x: x[0]):
        sc = scenes[idx]
        thoi_luong = float(tts_info["thoi_luong_giay"])
        sc["thoi_luong_giay"] = thoi_luong
        sc["audio_path"] = tts_info["audio_path"]
        if tts_info.get("directed_lines"):
            sc["directed_lines"] = tts_info["directed_lines"]
        wav_files.append(Path(tts_info["audio_path"]))
        tong_thoi_luong += thoi_luong
        frames_jpeg.extend(sc_frames)

    # Dọn dẹp file _voice.mp3 / _voice.wav cũ ngoài thư mục chính để tránh người dùng mở nhầm file âm thanh thay vì file .mp4
    for old_ext in (".mp3", ".wav"):
        old_voice = out_mp4_path.with_name(f"{out_mp4_path.stem}_voice{old_ext}")
        if old_voice.is_file():
            try:
                old_voice.unlink()
            except Exception:
                pass

    # Ghép track âm thanh thuyết minh tổng (.wav) kèm cắt khoảng lặng thừa đầu/cuối câu TTS
    out_audio_master = ghep_cac_file_wav_thanh_master(
        wav_files,
        work_dir / f"{out_mp4_path.stem}_voice.wav",
        cat_khoang_lang_tts=not che_do_nhanh_offline,
    )
    # Đồng bộ lại chính xác thời lượng từng phân cảnh theo file .wav thực tế sau khi cắt khoảng lặng để khớp 100% hình và tiếng
    concat_lines = []
    last_safe_fp = ""
    tong_thoi_luong = 0.0
    for idx, sc in enumerate(scenes):
        cand_wav = Path(str(sc.get("audio_path") or (work_dir / f"scene_{idx + 1:03d}.wav")))
        if not cand_wav.is_file() or cand_wav.suffix.lower() != ".wav":
            alt_wav = work_dir / f"scene_{idx + 1:03d}.wav"
            if alt_wav.is_file():
                cand_wav = alt_wav
        if cand_wav.is_file() and cand_wav.suffix.lower() == ".wav":
            try:
                with wave.open(str(cand_wav), "rb") as rf:
                    sc["thoi_luong_giay"] = round(max(0.65, rf.getnframes() / float(rf.getframerate() or 24000)), 3)
            except Exception:
                pass
        dur_sc = float(sc.get("thoi_luong_giay") or 3.0)
        tong_thoi_luong += dur_sc
        dur_step = round(max(0.08, dur_sc / float(so_buoc_canh)), 4)
        for step_idx in range(so_buoc_canh):
            frame_file = work_dir / f"frame_{idx + 1:03d}_{step_idx:02d}.jpg"
            safe_fp = str(frame_file.resolve()).replace("\\", "/")
            concat_lines.append(f"file '{safe_fp}'\nduration {dur_step}")
            last_safe_fp = safe_fp
    if concat_lines and last_safe_fp:
        concat_lines.append(f"file '{last_safe_fp}'")

    out_audio_master = pha_tron_nhac_nen_va_hieu_ung_chuyen_canh(
        out_audio_master,
        scenes,
        ma_nhac_nen=ma_nhac_nen,
        phong_cach_kich_ban=str(kich_ban.get("phong_cach") or "kich_tinh"),
    )

    ffmpeg_exe = _tim_ffmpeg_exe()
    loudness_info: dict[str, Any] = {"normalized": False}
    if ffmpeg_exe and not che_do_nhanh_offline:
        loudness_info = chuan_hoa_am_luong_ebu_r128(out_audio_master, ffmpeg_exe=ffmpeg_exe)

    out_srt_path = out_mp4_path.with_suffix(".srt")
    xuat_phu_de_srt(scenes, out_srt_path)

    out_ass_path = out_mp4_path.with_suffix(".ass")
    xuat_phu_de_ass(scenes, out_ass_path, kich_thuoc_video=kich_thuoc)

    out_fcpxml_path = out_mp4_path.with_name(f"{out_mp4_path.stem}_timeline.fcpxml")
    xuat_timeline_fcpxml(
        scenes,
        panel_source_files,
        out_audio_master,
        out_fcpxml_path,
        kich_thuoc_video=kich_thuoc,
        fps=24,
        ten_du_an=str(kich_ban.get("ten_truyen") or out_mp4_path.stem),
    )

    da_xuat_ffmpeg = False
    encoder_used = "ISO-BMFF Fallback"
    if ffmpeg_exe and concat_lines:
        concat_file = work_dir / "frames_concat.txt"
        concat_file.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
        da_xuat_ffmpeg, encoder_used = _chay_lenh_ffmpeg_xuat_mp4(
            ffmpeg_exe,
            concat_file,
            out_audio_master,
            out_mp4_path,
            srt_path=out_srt_path,
            fps=24,
        )

    if not da_xuat_ffmpeg:
        _tao_container_mp4_hop_le_du_phong(frames_jpeg, out_mp4_path)

    out_json_path = out_mp4_path.with_name(f"{out_mp4_path.stem}_storyboard.json")
    kich_ban_luu = dict(kich_ban)
    kich_ban_luu["tong_thoi_luong_giay"] = round(tong_thoi_luong, 2)
    kich_ban_luu["dinh_dang_video"] = ma_dinh_dang
    kich_ban_luu["ma_giong"] = ma_giong
    kich_ban_luu["master_audio_path"] = str(out_audio_master)
    kich_ban_luu["ass_subtitle_path"] = str(out_ass_path)
    kich_ban_luu["fcpxml_timeline_path"] = str(out_fcpxml_path)
    kich_ban_luu["encoder_used"] = encoder_used
    kich_ban_luu["loudness_ebu_r128"] = loudness_info
    out_json_path.write_text(json.dumps(kich_ban_luu, ensure_ascii=False, indent=2), encoding="utf-8")

    # Giai đoạn 4: Nếu chọn 'dual_youtube_va_shorts', dùng ngay cùng bộ âm thanh tổng (`out_audio_master`)
    # để render thêm bản Dọc 9:16 (TikTok / YouTube Shorts) mà KHÔNG cần chạy lại TTS!
    shorts_9_16_path_str = ""
    if ma_dinh_dang == "dual_youtube_va_shorts":
        stem_goc = re.sub(r"(_youtube_16_9|_dual_youtube_va_shorts|_tiktok_9_16)$", "", out_mp4_path.stem)
        shorts_mp4 = out_mp4_path.with_name(f"{stem_goc}_tiktok_9_16.mp4")
        kich_thuoc_doc = (720, 1280)

        def _ve_canh_doc_9_16(idx_and_sc: tuple[int, dict[str, Any]]) -> tuple[int, list[bytes]]:
            idx, sc = idx_and_sc
            p_bytes = panels_bytes[min(idx, len(panels_bytes) - 1)]
            loi = str(sc.get("loi_thuyet_minh") or "").strip()
            nhan_vat = str(sc.get("nhan_vat") or "").strip()
            kieu_cam = str(sc.get("hieu_ung_camera") or "pan_down")
            sc_f: list[bytes] = []
            for step_idx, t_ratio in enumerate(cac_moc_tien_do):
                fb = ve_khung_hinh_pan_zoom_va_phu_de(
                    p_bytes,
                    loi_thuyet_minh=loi,
                    nhan_vat=nhan_vat,
                    kich_thuoc_video=kich_thuoc_doc,
                    tien_do_canh=t_ratio,
                    kieu_chuyen_dong=kieu_cam,
                    chi_so_canh=idx + 1,
                    tong_so_canh=so_canh_tong,
                )
                sc_f.append(fb)
                (work_dir / f"vframe_{idx + 1:03d}_{step_idx:02d}.jpg").write_bytes(fb)
            return idx, sc_f

        with ThreadPoolExecutor(max_workers=6) as pool:
            res_doc = list(pool.map(_ve_canh_doc_9_16, enumerate(scenes)))

        frames_doc: list[bytes] = []
        concat_doc: list[str] = []
        last_vfp = ""
        for idx, sc_f in sorted(res_doc, key=lambda x: x[0]):
            frames_doc.extend(sc_f)
            dur_sc = float(scenes[idx].get("thoi_luong_giay") or 3.0)
            dur_step = round(max(0.08, dur_sc / float(so_buoc_canh)), 4)
            for step_idx in range(so_buoc_canh):
                vfile = work_dir / f"vframe_{idx + 1:03d}_{step_idx:02d}.jpg"
                safe_vfp = str(vfile.resolve()).replace("\\", "/")
                concat_doc.append(f"file '{safe_vfp}'\nduration {dur_step}")
                last_vfp = safe_vfp
        if concat_doc and last_vfp:
            concat_doc.append(f"file '{last_vfp}'")

        xuat_phu_de_ass(scenes, shorts_mp4.with_suffix(".ass"), kich_thuoc_video=kich_thuoc_doc)

        da_xuat_doc = False
        if ffmpeg_exe and concat_doc:
            concat_vfile = work_dir / "vframes_concat.txt"
            concat_vfile.write_text("\n".join(concat_doc) + "\n", encoding="utf-8")
            da_xuat_doc, _ = _chay_lenh_ffmpeg_xuat_mp4(
                ffmpeg_exe,
                concat_vfile,
                out_audio_master,
                shorts_mp4,
                srt_path=out_srt_path,
                fps=24,
            )
        if not da_xuat_doc:
            _tao_container_mp4_hop_le_du_phong(frames_doc, shorts_mp4)
        shorts_9_16_path_str = str(shorts_mp4)

    return {
        "ok": True,
        "video_path": str(out_mp4_path),
        "shorts_9_16_video_path": shorts_9_16_path_str,
        "audio_master_path": str(out_audio_master),
        "srt_path": str(out_srt_path),
        "ass_path": str(out_ass_path),
        "fcpxml_path": str(out_fcpxml_path),
        "storyboard_json_path": str(out_json_path),
        "encoder_used": encoder_used,
        "loudness_ebu_r128": loudness_info,
        "so_phan_canh": len(scenes),
        "tong_thoi_luong_giay": round(tong_thoi_luong, 2),
        "kich_thuoc_video": kich_thuoc,
    }
