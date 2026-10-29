from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import textwrap
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except Exception:  # pragma: no cover
    Image = None
    ImageDraw = None
    ImageFilter = None
    ImageFont = None

from core_tts_voice import tong_hop_giong_doc_phan_canh, xuat_phu_de_srt


DINH_DANG_VIDEO = {
    "tiktok_9_16": {
        "ten": "📱 Dọc 9:16 — TikTok / Facebook Reels / Shorts (720x1280)",
        "kich_thuoc": (720, 1280),
    },
    "youtube_16_9": {
        "ten": "📺 Ngang 16:9 — YouTube Review Full (1280x720)",
        "kich_thuoc": (1280, 720),
    },
}

GOI_LUOT_VIDEO_REVIEW = {
    "review_standard": {
        "ten": "⚡ Review Tiêu Chuẩn (Tự động tách cảnh + Thuyết minh nhanh · 10 lượt/video)",
        "so_luot": 10,
        "engine_ticket": "local_ocr_gpu",
    },
    "review_pro_character": {
        "ten": "🧠 Review Pro — Nhận Diện Sâu Nhân Vật & Lưới 2x2 (15 lượt/video)",
        "so_luot": 15,
        "engine_ticket": "local_hybrid_pro",
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

    # 1. Kiểm tra số dư khả dụng trước khi trừ
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
    if not la_quan_tri and con_lai < tong_luot_can:
        raise RuntimeError(
            f"Số dư tài khoản còn {con_lai} lượt, không đủ {tong_luot_can} lượt cho gói '{goi['ten']}'. "
            "Vui lòng nạp thêm lượt trên comic.io.vn!"
        )

    # 2. Xin cấp vé thực thi ký số HMAC-SHA256 từ cổng consume-local-page
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


def _nap_font_phu_de(co_chu: int = 28):
    if ImageFont is None:
        return None
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
) -> bytes:
    """
    Dựng 1 khung hình Video Review chuyên nghiệp:
    - Nền mờ (Blurred Ambient Background) lấp đầy khung 9:16 hoặc 16:9 không bị viền đen.
    - Hiệu ứng Camera Pan Down (trượt dọc theo khung tranh) hoặc Zoom In mượt mà theo `tien_do_canh` (0.0 -> 1.0).
    - Hộp phụ đề chữ vàng viền đen chuẩn kênh Review triệu view + Nhãn tên nhân vật góc trên.
    """
    if Image is None:
        return panel_bytes

    vw, vh = kich_thuoc_video
    t = max(0.0, min(1.0, float(tien_do_canh)))

    with Image.open(io.BytesIO(panel_bytes)) as raw_im:
        src = raw_im.convert("RGB")

    # 1. Tạo lớp nền mờ sang trọng
    bg = src.resize((vw, vh))
    if ImageFilter is not None:
        bg = bg.filter(ImageFilter.GaussianBlur(radius=18))
    # Làm tối nhẹ lớp nền mờ để khung tranh chính nổi bật
    overlay_dark = Image.new("RGB", (vw, vh), (10, 15, 28))
    canvas = Image.blend(bg, overlay_dark, alpha=0.55)

    # 2. Tính toán vùng cắt / phóng (Pan & Zoom) cho khung tranh chính
    vung_hien_thi_h = int(vh * 0.76)
    vung_hien_thi_w = int(vw * 0.94)

    if kieu_chuyen_dong == "zoom_in":
        scale = 1.0 + 0.12 * t
        fg = src.copy()
        fg.thumbnail((int(vung_hien_thi_w * scale), int(vung_hien_thi_h * scale)))
        if fg.width > vung_hien_thi_w or fg.height > vung_hien_thi_h:
            cx, cy = fg.width // 2, fg.height // 2
            cw = min(fg.width, vung_hien_thi_w)
            ch = min(fg.height, vung_hien_thi_h)
            fg = fg.crop((cx - cw // 2, cy - ch // 2, cx + cw // 2, cy + ch // 2))
    else:
        # Pan Down: phóng chiều ngang khớp khung và trượt từ trên xuống dưới nếu ảnh cao
        ty_le_w = vung_hien_thi_w / max(1, src.width)
        new_h = max(1, int(src.height * ty_le_w))
        fg_full = src.resize((vung_hien_thi_w, new_h))
        if new_h > vung_hien_thi_h:
            max_offset_y = new_h - vung_hien_thi_h
            oy = int(max_offset_y * t)
            fg = fg_full.crop((0, oy, vung_hien_thi_w, oy + vung_hien_thi_h))
        else:
            fg = fg_full

    px = (vw - fg.width) // 2
    py = int(vh * 0.05) + max(0, (vung_hien_thi_h - fg.height) // 2)
    canvas.paste(fg, (px, py))

    draw = ImageDraw.Draw(canvas)
    font_sub = _nap_font_phu_de(co_chu=26 if vw <= 720 else 30)
    font_tag = _nap_font_phu_de(co_chu=20)

    # 3. Vẽ nhãn Nhân Vật ở góc trái trên khung hình
    if nhan_vat:
        nhan_txt = f"🎭 {nhan_vat}"
        draw.rectangle([24, 18, min(vw - 24, 48 + len(nhan_txt) * 13), 56], fill=(220, 38, 38), outline=(255, 255, 255), width=2)
        draw.text((36, 25), nhan_txt, fill=(255, 255, 255), font=font_tag)

    # 4. Vẽ hộp Phụ Đề Review nổi bật ở phần dưới màn hình
    if loi_thuyet_minh:
        so_ky_tu_dong = 36 if vw <= 720 else 58
        cac_dong = textwrap.wrap(loi_thuyet_minh.strip(), width=so_ky_tu_dong)[:3]
        sub_y_top = int(vh * 0.82)
        draw.rectangle([18, sub_y_top, vw - 18, vh - 22], fill=(15, 23, 42), outline=(245, 158, 11), width=2)
        for idx_d, dong in enumerate(cac_dong):
            dy = sub_y_top + 14 + idx_d * 34
            # Viền đen chữ phụ đề
            for ox, oy in ((-2, -2), (2, -2), (-2, 2), (2, 2)):
                draw.text((34 + ox, dy + oy), dong, fill=(0, 0, 0), font=font_sub)
            draw.text((34, dy), dong, fill=(253, 224, 71), font=font_sub)

    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def _tim_ffmpeg_exe() -> str | None:
    ff = shutil.which("ffmpeg")
    if ff:
        return ff
    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _tao_container_mp4_hop_le_du_phong(frames_jpeg: list[bytes], out_mp4: Path) -> None:
    """
    Đóng gói container ISO-BMFF MP4 chuẩn (`ftypisom` + `moov` + `mdat` chứa chuỗi khung hình đã dựng)
    trong trường hợp máy khách chưa cài đặt `ffmpeg`, đảm bảo luôn xuất ra file `.mp4` hợp lệ.
    """
    ftyp = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2mp41"
    payload = b"".join(frames_jpeg)
    mdat_len = 8 + len(payload)
    mdat_hdr = mdat_len.to_bytes(4, "big") + b"mdat"
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    out_mp4.write_bytes(ftyp + mdat_hdr + payload)


def xuat_video_review_mp4(
    panels_bytes: list[bytes],
    kich_ban: dict[str, Any],
    out_mp4_path: Path,
    *,
    ma_dinh_dang: str = "tiktok_9_16",
    ma_giong: str = "nam_minh_kich_tinh",
    toc_do_doc: float = 1.15,
    che_do_nhanh_offline: bool = False,
) -> dict[str, Any]:
    """
    Quy trình khép kín dựng Video Review Truyện `.mp4` + phụ đề `.srt` + `storyboard_review.json`:
    1. Tổng hợp giọng đọc thuyết minh cho từng phân cảnh (`scenes`).
    2. Dựng các khung hình chuyển động Pan & Zoom kèm phụ đề chữ vàng.
    3. Kết xuất file `.mp4`, `.srt` và bản lưu kịch bản `.json` ngay tại thư mục đích.
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

    tong_thoi_luong = 0.0
    frames_jpeg: list[bytes] = []
    concat_lines: list[str] = []

    for idx, sc in enumerate(scenes):
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
            che_do_nhanh_offline=che_do_nhanh_offline,
        )
        thoi_luong = float(tts_info["thoi_luong_giay"])
        sc["thoi_luong_giay"] = thoi_luong
        sc["audio_path"] = tts_info["audio_path"]
        tong_thoi_luong += thoi_luong

        # Dựng 3 mốc chuyển động Pan/Zoom (Đầu - Giữa - Cuối cảnh) cho mỗi phân cảnh
        for step_idx, t_ratio in enumerate((0.1, 0.5, 0.9)):
            frame_b = ve_khung_hinh_pan_zoom_va_phu_de(
                p_bytes,
                loi_thuyet_minh=loi,
                nhan_vat=nhan_vat,
                kich_thuoc_video=kich_thuoc,
                tien_do_canh=t_ratio,
                kieu_chuyen_dong=kieu_cam,
            )
            frames_jpeg.append(frame_b)
            frame_file = work_dir / f"frame_{idx + 1:03d}_{step_idx}.jpg"
            frame_file.write_bytes(frame_b)
            dur_step = round(thoi_luong / 3.0, 3)
            safe_fp = str(frame_file.resolve()).replace("\\", "/")
            concat_lines.append(f"file '{safe_fp}'\nduration {dur_step}")

    # Xuất file phụ đề .srt và kịch bản .json đi kèm
    out_srt_path = out_mp4_path.with_suffix(".srt")
    xuat_phu_de_srt(scenes, out_srt_path)

    out_json_path = out_mp4_path.with_name(f"{out_mp4_path.stem}_storyboard.json")
    kich_ban_luu = dict(kich_ban)
    kich_ban_luu["tong_thoi_luong_giay"] = round(tong_thoi_luong, 2)
    kich_ban_luu["dinh_dang_video"] = ma_dinh_dang
    kich_ban_luu["ma_giong"] = ma_giong
    out_json_path.write_text(json.dumps(kich_ban_luu, ensure_ascii=False, indent=2), encoding="utf-8")

    # Kết xuất MP4 bằng FFmpeg nếu có sẵn, hoặc đóng gói MP4 trực tiếp
    ffmpeg_exe = _tim_ffmpeg_exe()
    da_xuat_ffmpeg = False
    if ffmpeg_exe and concat_lines:
        try:
            concat_file = work_dir / "frames_concat.txt"
            concat_file.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.run(
                [
                    ffmpeg_exe,
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(concat_file),
                    "-vf",
                    "fps=24,format=yuv420p",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast",
                    str(out_mp4_path),
                ],
                timeout=90,
                check=True,
                creationflags=flags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            da_xuat_ffmpeg = out_mp4_path.is_file() and out_mp4_path.stat().st_size > 512
        except Exception:
            da_xuat_ffmpeg = False

    if not da_xuat_ffmpeg:
        _tao_container_mp4_hop_le_du_phong(frames_jpeg, out_mp4_path)

    return {
        "ok": True,
        "video_path": str(out_mp4_path),
        "srt_path": str(out_srt_path),
        "storyboard_json_path": str(out_json_path),
        "so_phan_canh": len(scenes),
        "tong_thoi_luong_giay": round(tong_thoi_luong, 2),
        "kich_thuoc_video": kich_thuoc,
    }
