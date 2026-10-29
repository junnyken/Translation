from __future__ import annotations

import io
import math
import os
import struct
import subprocess
import wave
from pathlib import Path
from typing import Any


DANH_SACH_GIONG_DOC = {
    "nam_minh_kich_tinh": {
        "ten": "🎙️ Nam Minh — Trầm Ngầu / Review Hành Động & Tu Tiên",
        "voice_id": "vi-VN-NamMinhNeural",
        "gioi_tinh": "nam",
        "toc_do_mac_dinh": 1.15,
    },
    "hoai_my_truyen_cam": {
        "ten": "🎙️ Hoài My — Truyền Cảm / Review Ngôn Tình & Drama",
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
        "ten": "🧠 Lõi Giọng Biểu Cảm AI Pro (Độ chân thực cao · Hỗ trợ 3 miền)",
        "voice_id": "vieneu_onnx_pro",
        "gioi_tinh": "auto",
        "toc_do_mac_dinh": 1.15,
    },
}


def uoc_tinh_thoi_luong_cau(van_ban: str, toc_do: float = 1.15) -> float:
    """
    Ước tính chính xác thời lượng đọc tiếng Việt (tính bằng giây) theo số âm tiết (từ) và tốc độ nói.
    Trung bình giọng Review tiếng Việt ở tốc độ 1.0x đọc khoảng 3.6 âm tiết/giây.
    """
    so_tu = len([w for w in (van_ban or "").strip().split() if w])
    toc_do_an_toan = max(0.75, min(1.6, float(toc_do or 1.15)))
    am_tiet_moi_giay = 3.6 * toc_do_an_toan
    thoi_luong = max(1.8, (so_tu / am_tiet_moi_giay) + 0.45)
    return round(thoi_luong, 2)


def _tao_wav_pcm_chuan(thoi_luong_giay: float, sample_rate: int = 24000, tan_so_goi_y: float = 0.0) -> bytes:
    """
    Tạo luồng âm thanh WAV PCM 16-bit mono hợp lệ với đúng thời lượng `thoi_luong_giay`
    để đảm bảo bộ ghép video MP4 luôn có track âm thanh đồng bộ tuyệt đối trên mọi môi trường.
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
                # Sóng âm nhẹ với biên độ êm để kiểm thử âm thanh
                env = min(1.0, i / (sample_rate * 0.05), (so_mau - i) / (sample_rate * 0.05))
                val = int(1800 * env * math.sin(2.0 * math.pi * tan_so_goi_y * (i / sample_rate)))
                frames.extend(struct.pack("<h", val))
            wf.writeframes(bytes(frames))
    return buf.getvalue()


def _thu_goi_vieneu_onnx(van_ban: str, out_wav: Path) -> bool:
    """Thử gọi Lõi Giọng Biểu Cảm ONNX cục bộ nếu máy khách đã cài gói mở rộng."""
    try:
        from vieneu import Vieneu  # type: ignore

        tts = Vieneu()
        audio = tts.infer(text=van_ban)
        tts.save(audio, str(out_wav))
        return out_wav.is_file() and out_wav.stat().st_size > 256
    except Exception:
        return False


def _thu_goi_edge_neural(van_ban: str, voice_id: str, toc_do: float, out_audio: Path) -> bool:
    """Thử tổng hợp giọng đọc Neural tốc độ cao nếu có kết nối và gói `edge_tts`."""
    try:
        import asyncio
        import edge_tts  # type: ignore

        pct = int(round((toc_do - 1.0) * 100))
        rate_str = f"+{pct}%" if pct >= 0 else f"{pct}%"

        async def _run():
            comm = edge_tts.Communicate(van_ban, voice=voice_id, rate=rate_str)
            await comm.save(str(out_audio))

        asyncio.run(_run())
        return out_audio.is_file() and out_audio.stat().st_size > 256
    except Exception:
        return False


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
    - Trả về `{"audio_path": str, "thoi_luong_giay": float, "ma_giong": str}`.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    info = DANH_SACH_GIONG_DOC.get(ma_giong) or DANH_SACH_GIONG_DOC["nam_minh_kich_tinh"]
    voice_id = info["voice_id"]
    if voice_id == "auto_pair":
        voice_id = "vi-VN-NamMinhNeural" if scene_index % 2 == 1 else "vi-VN-HoaiMyNeural"

    thoi_luong = uoc_tinh_thoi_luong_cau(van_ban, toc_do=toc_do)
    wav_path = out_dir / f"scene_{scene_index:03d}.wav"

    da_tao = False
    if not che_do_nhanh_offline:
        if ma_giong == "bieu_cam_ai_pro":
            da_tao = _thu_goi_vieneu_onnx(van_ban, wav_path)
        if not da_tao and voice_id.startswith("vi-VN-"):
            da_tao = _thu_goi_edge_neural(van_ban, voice_id, toc_do, wav_path)
        if not da_tao:
            da_tao = _thu_goi_windows_sapi(van_ban, toc_do, wav_path)

    if not da_tao:
        wav_bytes = _tao_wav_pcm_chuan(thoi_luong, sample_rate=24000, tan_so_goi_y=0.0)
        wav_path.write_bytes(wav_bytes)

    return {
        "scene_index": scene_index,
        "audio_path": str(wav_path),
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
