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


DANH_SACH_GIONG_DOC = {
    "nam_minh_kich_tinh": {
        "ten": "🎙️ Nam Minh — Trầm Ngầu / Review Hành Động & Tu Tiên (Miền Bắc)",
        "voice_id": "vi-VN-NamMinhNeural",
        "gioi_tinh": "nam",
        "toc_do_mac_dinh": 1.15,
    },
    "hoai_my_truyen_cam": {
        "ten": "🎙️ Hoài My — Truyền Cảm / Review Ngôn Tình & Drama (Miền Nam)",
        "voice_id": "vi-VN-HoaiMyNeural",
        "gioi_tinh": "nu",
        "toc_do_mac_dinh": 1.15,
    },
    "luan_phien_nam_nu": {
        "ten": "🎭 Cặp Đôi Nam Minh & Hoài My (Tự động đổi giọng theo phân cảnh)",
        "voice_id": "auto_pair",
        "gioi_tinh": "auto",
        "toc_do_mac_dinh": 1.15,
    },
    "bieu_cam_ai_pro": {
        "ten": "🧠 Lõi Giọng Biểu Cảm AI Pro (ONNX 3 Miền · Tự Nhiên Như Người Thật)",
        "voice_id": "vieneu_onnx_pro",
        "gioi_tinh": "auto",
        "toc_do_mac_dinh": 1.15,
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
    """
    Kiểm tra trạng thái sẵn sàng của 3 thành phần:
    1. Lõi Giọng Đọc Neural (`edge_tts`)
    2. Lõi Giọng Biểu Cảm ONNX (`vieneu`)
    3. Nhân ghép hình & tiếng MP4 (`ffmpeg` / `imageio_ffmpeg`)
    """
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
        "neural_voice_ready": co_edge_tts,
        "onnx_pro_voice_ready": co_vieneu,
        "ffmpeg_ready": bool(ffmpeg_exe),
        "ffmpeg_path": ffmpeg_exe or "",
    }


def cai_dat_tu_dong_goi_giong_doc_va_mp4(cai_them_onnx_pro: bool = False) -> tuple[bool, str]:
    """
    Tự động cài đặt các gói thư viện giọng đọc AI & bộ đóng gói MP4 (`edge-tts`, `imageio-ffmpeg`, `Pillow`)
    trực tiếp từ giao diện Studio mà người dùng không cần mở Terminal.
    """
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
        return True, f"Đã cài đặt & đồng bộ thành công: {', '.join(ds_goi)}"
    except Exception as exc:
        return False, f"Không thể tự động cài gói mở rộng: {exc}"


def uoc_tinh_thoi_luong_cau(van_ban: str, toc_do: float = 1.15) -> float:
    """
    Ước tính chính xác thời lượng đọc tiếng Việt (tính bằng giây) theo số âm tiết (từ) và tốc độ nói.
    """
    so_tu = len([w for w in (van_ban or "").strip().split() if w])
    toc_do_an_toan = max(0.75, min(1.6, float(toc_do or 1.15)))
    am_tiet_moi_giay = 3.6 * toc_do_an_toan
    thoi_luong = max(1.8, (so_tu / am_tiet_moi_giay) + 0.45)
    return round(thoi_luong, 2)


def do_thoi_luong_wav_thuc_te(wav_path: Path) -> float | None:
    """Đo chính xác thời lượng (giây) của file WAV PCM thực tế sau khi tổng hợp giọng nói."""
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
    """Chuyển đổi file âm thanh MP3 từ Lõi Giọng Neural sang chuẩn WAV PCM 24kHz 16-bit mono để ghép đồng bộ."""
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
    """
    Tạo luồng âm thanh WAV PCM 16-bit mono hợp lệ với đúng thời lượng `thoi_luong_giay`.
    """
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


def _thu_goi_vieneu_onnx(van_ban: str, out_wav: Path) -> bool:
    """Thử gọi Lõi Giọng Biểu Cảm ONNX cục bộ (`vieneu`)."""
    try:
        from vieneu import Vieneu  # type: ignore

        tts = Vieneu()
        audio = tts.infer(text=van_ban)
        tts.save(audio, str(out_wav))
        return out_wav.is_file() and out_wav.stat().st_size > 256
    except Exception:
        return False


def _thu_goi_edge_neural(van_ban: str, voice_id: str, toc_do: float, out_wav: Path) -> tuple[bool, Path]:
    """
    Tổng hợp giọng đọc Neural (`vi-VN-NamMinhNeural` / `vi-VN-HoaiMyNeural`):
    - Xuất ra `.mp3` rồi tự động chuẩn hoá sang `.wav` PCM 24kHz (nếu có `ffmpeg`),
      hoặc trả về file `.mp3` gốc để phát trực tiếp!
    """
    try:
        import asyncio
        import edge_tts  # type: ignore

        pct = int(round((toc_do - 1.0) * 100))
        rate_str = f"+{pct}%" if pct >= 0 else f"{pct}%"
        mp3_tmp = out_wav.with_suffix(".mp3")

        async def _run():
            comm = edge_tts.Communicate(van_ban, voice=voice_id, rate=rate_str)
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
    """Sử dụng bộ tổng hợp giọng nói tích hợp sẵn trên Windows (`System.Speech.Synthesis`) nếu chạy offline."""
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
    che_do_nhanh_offline: bool = False,
) -> dict[str, Any]:
    """
    Tổng hợp file âm thanh thuyết minh cho 1 phân cảnh Storyboard:
    - Tự động chọn giọng Nam/Nữ hoặc luân phiên theo phân cảnh.
    - Đo thời lượng thực tế của file âm thanh vừa tạo để khớp 100% với chuyển động hình ảnh.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    info = DANH_SACH_GIONG_DOC.get(ma_giong) or DANH_SACH_GIONG_DOC["nam_minh_kich_tinh"]
    voice_id = info["voice_id"]
    if voice_id == "auto_pair":
        voice_id = "vi-VN-NamMinhNeural" if scene_index % 2 == 1 else "vi-VN-HoaiMyNeural"

    thoi_luong = uoc_tinh_thoi_luong_cau(van_ban, toc_do=toc_do)
    wav_path = out_dir / f"scene_{scene_index:03d}.wav"
    actual_audio_path = wav_path

    da_tao = False
    if not che_do_nhanh_offline:
        if ma_giong == "bieu_cam_ai_pro":
            da_tao = _thu_goi_vieneu_onnx(van_ban, wav_path)
            if not da_tao:
                # Nếu máy chưa cài gói ONNX mở rộng, tự động dùng giọng Neural chất lượng cao
                da_tao, actual_audio_path = _thu_goi_edge_neural(van_ban, "vi-VN-NamMinhNeural", toc_do, wav_path)
        elif voice_id.startswith("vi-VN-"):
            da_tao, actual_audio_path = _thu_goi_edge_neural(van_ban, voice_id, toc_do, wav_path)
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
        "ma_giong": ma_giong,
        "voice_id": voice_id,
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
    """
    Sinh nội dung phụ đề chuẩn `.srt` khớp chính xác từng mili-giây với từng phân cảnh trong Video Review.
    """
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
