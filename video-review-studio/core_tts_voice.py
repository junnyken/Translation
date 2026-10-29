from __future__ import annotations

import io
import math
import os
import shutil
import struct
import subprocess
import wave
from pathlib import Path
from typing import Any


DANH_SACH_GIONG_DOC: dict[str, dict[str, Any]] = {
    # --- CHẾ ĐỘ ĐẶC BIỆT: ĐA NHÂN VẬT & NHÁI GIỌNG ---
    "da_nhan_vat_thong_minh": {
        "ten": "🎭 Đa Nhân Vật Tự Động (Tự đổi giọng Nam / Nữ / Phản Diện theo từng cảnh)",
        "voice_id": "auto_role_cast",
        "preset_hf": "binh",
        "pitch_hz": "+0Hz",
        "gioi_tinh": "auto",
        "vung_mien": "Đa miền",
        "toc_do_mac_dinh": 1.15,
    },
    "clone_giong_mau_5s": {
        "ten": "🧬 Nhái Giọng Từ File Mẫu 5 Giây (Zero-Shot Voice Cloning — Giọng bất kỳ)",
        "voice_id": "zero_shot_clone",
        "preset_hf": "custom_clone",
        "pitch_hz": "+0Hz",
        "gioi_tinh": "custom",
        "vung_mien": "Theo mẫu",
        "toc_do_mac_dinh": 1.15,
    },
    # --- NHÓM GIỌNG NAM REVIEW & NHÂN VẬT NAM (BẮC / TRUNG / NAM) ---
    "nam_minh_kich_tinh": {
        "ten": "🎙️ Nam Minh — Nam Miền Bắc (Trầm Ngầu · Review Hành Động & Manhwa)",
        "voice_id": "vi-VN-NamMinhNeural",
        "preset_hf": "binh",
        "pitch_hz": "+0Hz",
        "gioi_tinh": "nam",
        "vung_mien": "Miền Bắc",
        "toc_do_mac_dinh": 1.15,
    },
    "hoang_binh_tu_tien": {
        "ten": "⚔️ Hoàng Bình — Nam Miền Bắc (Uy Nghiêm · Review Tu Tiên & Hệ Thống)",
        "voice_id": "vi-VN-NamMinhNeural",
        "preset_hf": "binh",
        "pitch_hz": "-6Hz",
        "gioi_tinh": "nam",
        "vung_mien": "Miền Bắc",
        "toc_do_mac_dinh": 1.15,
    },
    "bac_si_tuyen_trinh_tham": {
        "ten": "📜 Minh Tuyên — Nam Miền Bắc (Điềm Đạm · Kể Chuyện Trinh Thám & Lịch Sử)",
        "voice_id": "vi-VN-NamMinhNeural",
        "preset_hf": "tuyen",
        "pitch_hz": "-3Hz",
        "gioi_tinh": "nam",
        "vung_mien": "Miền Bắc",
        "toc_do_mac_dinh": 1.10,
    },
    "xuan_vinh_tong_tai": {
        "ten": "👑 Xuân Vĩnh — Nam Trầm Ấm (Bá Đạo · Tổng Tài & Đô Thị)",
        "voice_id": "vi-VN-NamMinhNeural",
        "preset_hf": "vinh",
        "pitch_hz": "-8Hz",
        "gioi_tinh": "nam",
        "vung_mien": "Miền Bắc",
        "toc_do_mac_dinh": 1.12,
    },
    "khoi_nguyen_mien_nam": {
        "ten": "🔥 Khôi Nguyên — Nam Miền Nam (Trẻ Trung · Review Hài Hước & Đời Sống)",
        "voice_id": "vi-VN-NamMinhNeural",
        "preset_hf": "nguyen",
        "pitch_hz": "+6Hz",
        "gioi_tinh": "nam",
        "vung_mien": "Miền Nam",
        "toc_do_mac_dinh": 1.20,
    },
    "quang_son_mien_trung": {
        "ten": "⛰️ Quang Sơn — Nam Miền Trung (Chất Phác · Kiếm Hiệp & Cổ Trang)",
        "voice_id": "vi-VN-NamMinhNeural",
        "preset_hf": "son",
        "pitch_hz": "-4Hz",
        "gioi_tinh": "nam",
        "vung_mien": "Miền Trung",
        "toc_do_mac_dinh": 1.15,
    },
    "hac_am_phan_dien": {
        "ten": "😈 Hắc Ám Lão Tổ — Giọng Trùm Phản Diện / Ma Tôn (Trầm Rền Uy Áp)",
        "voice_id": "vi-VN-NamMinhNeural",
        "preset_hf": "vinh",
        "pitch_hz": "-16Hz",
        "gioi_tinh": "nam",
        "vung_mien": "Cổ trang",
        "toc_do_mac_dinh": 1.05,
    },
    # --- NHÓM GIỌNG NỮ REVIEW & NHÂN VẬT NỮ (BẮC / NAM) ---
    "hoai_my_truyen_cam": {
        "ten": "🎙️ Hoài My — Nữ Miền Nam (Truyền Cảm · Review Ngôn Tình & Drama)",
        "voice_id": "vi-VN-HoaiMyNeural",
        "preset_hf": "doan",
        "pitch_hz": "+0Hz",
        "gioi_tinh": "nu",
        "vung_mien": "Miền Nam",
        "toc_do_mac_dinh": 1.15,
    },
    "ngoc_huyen_mien_bac": {
        "ten": "🌸 Ngọc Huyền — Nữ Miền Bắc (Trong Trẻo · Nữ Chính Thanh Xuân & Học Đường)",
        "voice_id": "vi-VN-HoaiMyNeural",
        "preset_hf": "ngoc",
        "pitch_hz": "+5Hz",
        "gioi_tinh": "nu",
        "vung_mien": "Miền Bắc",
        "toc_do_mac_dinh": 1.15,
    },
    "thuc_doan_ngot_ngao": {
        "ten": "🌺 Thục Đoan — Nữ Miền Nam (Ngọt Ngào · Chữa Lành & Xuyên Không)",
        "voice_id": "vi-VN-HoaiMyNeural",
        "preset_hf": "doan",
        "pitch_hz": "+3Hz",
        "gioi_tinh": "nu",
        "vung_mien": "Miền Nam",
        "toc_do_mac_dinh": 1.15,
    },
    "truc_ly_nu_cuong": {
        "ten": "❄️ Trúc Ly — Nữ Lạnh Lùng (Sắc Sảo · Nữ Cường & Báo Thù)",
        "voice_id": "vi-VN-HoaiMyNeural",
        "preset_hf": "ly",
        "pitch_hz": "-6Hz",
        "gioi_tinh": "nu",
        "vung_mien": "Miền Bắc",
        "toc_do_mac_dinh": 1.18,
    },
    "my_duyen_ca_khia": {
        "ten": "😂 Mỹ Duyên — Nữ Năng Động (Bắt Trend · Review Cà Khịa TikTok)",
        "voice_id": "vi-VN-HoaiMyNeural",
        "preset_hf": "duyen",
        "pitch_hz": "+8Hz",
        "gioi_tinh": "nu",
        "vung_mien": "Miền Nam",
        "toc_do_mac_dinh": 1.25,
    },
    "thu_huong_ke_chuyen": {
        "ten": "🌙 Thu Hương — Nữ Miền Bắc (Sâu Lắng · Kể Chuyện Tâm Lý & Bí Ẩn)",
        "voice_id": "vi-VN-HoaiMyNeural",
        "preset_hf": "huong",
        "pitch_hz": "-4Hz",
        "gioi_tinh": "nu",
        "vung_mien": "Miền Bắc",
        "toc_do_mac_dinh": 1.08,
    },
}


def tim_ffmpeg_he_thong() -> str | None:
    ff = shutil.which("ffmpeg")
    if ff:
        return ff
    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def kiem_tra_ha_tang_giong_doc_va_video() -> dict[str, Any]:
    co_edge_tts = False
    try:
        import edge_tts  # noqa: F401

        co_edge_tts = True
    except Exception:
        pass

    co_vieneu = False
    try:
        import vieneu  # noqa: F401

        co_vieneu = True
    except Exception:
        pass

    ffmpeg_exe = tim_ffmpeg_he_thong()
    return {
        "so_luong_giong_doc": len(DANH_SACH_GIONG_DOC),
        "neural_voice_ready": co_edge_tts,
        "onnx_pro_voice_ready": co_vieneu,
        "ffmpeg_ready": bool(ffmpeg_exe),
        "ffmpeg_path": ffmpeg_exe or "",
    }


def cai_dat_tu_dong_goi_giong_doc_va_mp4(cai_them_onnx_pro: bool = False) -> tuple[bool, str]:
    import sys

    ds_goi = ["Pillow", "edge-tts", "imageio-ffmpeg"]
    if cai_them_onnx_pro:
        ds_goi.append("vieneu")
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", *ds_goi],
            timeout=180,
            check=True,
            creationflags=flags,
        )
        return True, f"Đã cài đặt & đồng bộ thành công kho {len(DANH_SACH_GIONG_DOC)} giọng đọc AI ({', '.join(ds_goi)})"
    except Exception as exc:
        return False, f"Không thể tự động cài gói mở rộng: {exc}"


def chon_giong_theo_vai_tro_nhan_vat(vai_tro: str = "", ten_nhan_vat: str = "", scene_index: int = 1) -> str:
    """
    Khi người dùng bật chế độ `da_nhan_vat_thong_minh`:
    Tự động gán giọng đọc phù hợp nhất với vai trò nhân vật trong phân cảnh đó!
    """
    vt = (vai_tro or "").lower()
    ten = (ten_nhan_vat or "").lower()
    if any(k in vt or k in ten for k in ("nữ", "tiểu thư", "cô", "tuyết", "ly", "ngọc", "huyền", "my", "hương")):
        return "ngoc_huyen_mien_bac" if scene_index % 2 == 0 else "hoai_my_truyen_cam"
    if any(k in vt or k in ten for k in ("phản diện", "trùm", "ma tôn", "kẻ địch", "đối thủ", "lão", "hổ")):
        return "hac_am_phan_dien"
    if any(k in vt for k in ("hài", "phụ", "bạn")):
        return "khoi_nguyen_mien_nam"
    return "nam_minh_kich_tinh"


def uoc_tinh_thoi_luong_cau(van_ban: str, toc_do: float = 1.15) -> float:
    so_tu = len([w for w in (van_ban or "").strip().split() if w])
    toc_do_an_toan = max(0.75, min(1.6, float(toc_do or 1.15)))
    am_tiet_moi_giay = 3.6 * toc_do_an_toan
    thoi_luong = max(1.8, (so_tu / am_tiet_moi_giay) + 0.45)
    return round(thoi_luong, 2)


def do_thoi_luong_wav_thuc_te(wav_path: Path) -> float | None:
    if not wav_path.is_file():
        return None
    try:
        with wave.open(str(wav_path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate > 0 and frames > 0:
                return round(frames / float(rate), 2)
    except Exception:
        return None
    return None


def _chuyen_mp3_sang_wav_chuan(mp3_path: Path, out_wav: Path) -> bool:
    ff = tim_ffmpeg_he_thong()
    if not ff or not mp3_path.is_file():
        return False
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.run(
            [
                ff,
                "-y",
                "-i",
                str(mp3_path),
                "-ar",
                "24000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(out_wav),
            ],
            timeout=20,
            check=True,
            creationflags=flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return out_wav.is_file() and out_wav.stat().st_size > 512
    except Exception:
        return False


def _tao_wav_pcm_chuan(thoi_luong_giay: float, sample_rate: int = 24000, tan_so_goi_y: float = 0.0) -> bytes:
    so_mau = max(int(sample_rate * 0.5), int(sample_rate * thoi_luong_giay))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        if tan_so_goi_y <= 0:
            wf.writeframes(b"\x00\x00" * so_mau)
        else:
            frames = bytearray()
            for i in range(so_mau):
                env = min(1.0, i / (sample_rate * 0.05), (so_mau - i) / (sample_rate * 0.05))
                val = int(1800 * env * math.sin(2.0 * math.pi * tan_so_goi_y * (i / sample_rate)))
                frames.extend(struct.pack("<h", val))
            wf.writeframes(bytes(frames))
    return buf.getvalue()


def _thu_goi_vieneu_onnx(
    van_ban: str,
    out_wav: Path,
    *,
    preset_voice: str = "binh",
    ref_audio_path: str | Path | None = None,
) -> bool:
    """
    Gọi Lõi Giọng Đọc Biểu Cảm ONNX (`vieneu` từ HuggingFace):
    - Hỗ trợ cả 10+ giọng Preset 3 miền (`binh`, `tuyen`, `vinh`, `nguyen`, `son`, `ngoc`, `doan`, `ly`, `duyen`, `huong`)
    - Hỗ trợ Zero-Shot Voice Cloning (`ref_audio_path`) nhái bất kỳ giọng nào chỉ từ mẫu âm thanh 5 giây!
    """
    try:
        from vieneu import Vieneu  # type: ignore

        tts = Vieneu()
        if ref_audio_path and Path(ref_audio_path).is_file():
            audio = tts.infer(text=van_ban, ref_audio=str(ref_audio_path))
        else:
            try:
                audio = tts.infer(text=van_ban, voice=preset_voice)
            except TypeError:
                audio = tts.infer(text=van_ban)
        tts.save(audio, str(out_wav))
        return out_wav.is_file() and out_wav.stat().st_size > 256
    except Exception:
        return False


def _thu_goi_edge_neural(
    van_ban: str,
    voice_id: str,
    toc_do: float,
    out_wav: Path,
    *,
    pitch_hz: str = "+0Hz",
) -> tuple[bool, Path]:
    """
    Tổng hợp giọng đọc Neural kết hợp điều biến âm sắc/cao độ (`pitch_hz`) cho từng nhân vật:
    - Trùm phản diện (`-16Hz` trầm rền), Tổng tài (`-8Hz`), Nữ chính thanh xuân (`+5Hz`), Cà khịa TikTok (`+8Hz`).
    """
    try:
        import asyncio
        import edge_tts  # type: ignore

        pct = int(round((toc_do - 1.0) * 100))
        rate_str = f"+{pct}%" if pct >= 0 else f"{pct}%"
        mp3_tmp = out_wav.with_suffix(".mp3")

        async def _run():
            comm = edge_tts.Communicate(van_ban, voice=voice_id, rate=rate_str, pitch=pitch_hz)
            await comm.save(str(mp3_tmp))

        asyncio.run(_run())
        if mp3_tmp.is_file() and mp3_tmp.stat().st_size > 256:
            if _chuyen_mp3_sang_wav_chuan(mp3_tmp, out_wav):
                try:
                    mp3_tmp.unlink()
                except Exception:
                    pass
                return True, out_wav
            return True, mp3_tmp
    except Exception:
        pass
    return False, out_wav


def _thu_goi_windows_sapi(van_ban: str, toc_do: float, out_wav: Path) -> bool:
    if os.name != "nt":
        return False
    try:
        rate_sapi = max(-4, min(6, int(round((toc_do - 1.0) * 10))))
        safe_txt = van_ban.replace("'", " ").replace('"', " ").replace("\n", " ")
        safe_path = str(out_wav).replace("'", "''")
        ps_cmd = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = {rate_sapi}
$synth.SetOutputToWaveFile('{safe_path}')
$synth.Speak('{safe_txt}')
$synth.Dispose()
"""
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            timeout=15,
            check=True,
            creationflags=flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return out_wav.is_file() and out_wav.stat().st_size > 512
    except Exception:
        return False


def tong_hop_giong_doc_phan_canh(
    van_ban: str,
    out_dir: Path,
    *,
    scene_index: int = 1,
    ma_giong: str = "nam_minh_kich_tinh",
    toc_do: float = 1.15,
    vai_tro_nhan_vat: str = "",
    ten_nhan_vat: str = "",
    file_giong_mau_clone: str | Path | None = None,
    che_do_nhanh_offline: bool = False,
) -> dict[str, Any]:
    """
    Tổng hợp file âm thanh thuyết minh cho 1 phân cảnh Storyboard với kho 15 giọng đọc:
    - Nếu chọn `da_nhan_vat_thong_minh`: tự động đổi giọng theo vai trò nhân vật (Main / Nữ chính / Phản diện).
    - Nếu chọn `clone_giong_mau_5s`: nhái giọng từ file mẫu 5 giây bằng Lõi ONNX.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    ma_giong_thuc = ma_giong
    if ma_giong == "da_nhan_vat_thong_minh":
        ma_giong_thuc = chon_giong_theo_vai_tro_nhan_vat(vai_tro_nhan_vat, ten_nhan_vat, scene_index)

    info = DANH_SACH_GIONG_DOC.get(ma_giong_thuc) or DANH_SACH_GIONG_DOC["nam_minh_kich_tinh"]
    voice_id = str(info.get("voice_id") or "vi-VN-NamMinhNeural")
    preset_hf = str(info.get("preset_hf") or "binh")
    pitch_hz = str(info.get("pitch_hz") or "+0Hz")

    thoi_luong = uoc_tinh_thoi_luong_cau(van_ban, toc_do=toc_do)
    wav_path = out_dir / f"scene_{scene_index:03d}.wav"
    actual_audio_path = wav_path

    da_tao = False
    if not che_do_nhanh_offline:
        # 1. Nếu chọn Nhái giọng 5s hoặc máy đã cài Lõi ONNX HuggingFace (VieNeu)
        if ma_giong == "clone_giong_mau_5s" or file_giong_mau_clone:
            da_tao = _thu_goi_vieneu_onnx(
                van_ban, wav_path, preset_voice=preset_hf, ref_audio_path=file_giong_mau_clone
            )
        if not da_tao:
            da_tao = _thu_goi_vieneu_onnx(van_ban, wav_path, preset_voice=preset_hf)
        # 2. Tổng hợp bằng Lõi Giọng Đọc Neural kèm tinh chỉnh âm sắc nhân vật (Pitch/Timbre)
        if not da_tao and voice_id.startswith("vi-VN-"):
            da_tao, actual_audio_path = _thu_goi_edge_neural(
                van_ban, voice_id, toc_do, wav_path, pitch_hz=pitch_hz
            )
        if not da_tao:
            da_tao = _thu_goi_windows_sapi(van_ban, toc_do, wav_path)
            actual_audio_path = wav_path

    if not da_tao:
        wav_bytes = _tao_wav_pcm_chuan(thoi_luong, sample_rate=24000, tan_so_goi_y=0.0)
        wav_path.write_bytes(wav_bytes)
        actual_audio_path = wav_path
    elif actual_audio_path.suffix.lower() == ".wav":
        thoi_luong_thuc = do_thoi_luong_wav_thuc_te(actual_audio_path)
        if thoi_luong_thuc and thoi_luong_thuc >= 0.8:
            thoi_luong = thoi_luong_thuc

    return {
        "scene_index": scene_index,
        "audio_path": str(actual_audio_path),
        "thoi_luong_giay": thoi_luong,
        "ma_giong": ma_giong_thuc,
        "voice_id": voice_id,
        "preset_hf": preset_hf,
    }


def _dinh_dang_moc_srt(giay: float) -> str:
    tong_ms = max(0, int(round(giay * 1000)))
    gio = tong_ms // 3_600_000
    tong_ms %= 3_600_000
    phut = tong_ms // 60_000
    tong_ms %= 60_000
    s = tong_ms // 1000
    ms = tong_ms % 1000
    return f"{gio:02d}:{phut:02d}:{s:02d},{ms:03d}"


def xuat_phu_de_srt(scenes: list[dict[str, Any]], out_srt_path: Path | None = None) -> str:
    blocks: list[str] = []
    moc_hien_tai = 0.0
    for idx, sc in enumerate(scenes, 1):
        thoi_luong = float(sc.get("thoi_luong_giay") or uoc_tinh_thoi_luong_cau(str(sc.get("loi_thuyet_minh") or "")))
        bat_dau = moc_hien_tai
        ket_thuc = moc_hien_tai + thoi_luong
        moc_hien_tai = ket_thuc
        loi = str(sc.get("loi_thuyet_minh") or "").strip()
        nhan_vat = str(sc.get("nhan_vat") or "").strip()
        dong_hien_thi = f"[{nhan_vat}] {loi}" if nhan_vat else loi
        blocks.append(f"{idx}\n{_dinh_dang_moc_srt(bat_dau)} --> {_dinh_dang_moc_srt(ket_thuc)}\n{dong_hien_thi}\n")

    srt_content = "\n".join(blocks)
    if out_srt_path is not None:
        out_srt_path.parent.mkdir(parents=True, exist_ok=True)
        out_srt_path.write_text(srt_content, encoding="utf-8")
    return srt_content
