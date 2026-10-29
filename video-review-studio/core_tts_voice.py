from __future__ import annotations

import io
import math
import os
import re
import shutil
import struct
import subprocess
import urllib.parse
import urllib.request
import wave
from pathlib import Path
from typing import Any


DANH_SACH_GIONG_DOC: dict[str, dict[str, Any]] = {
    # --- NHÓM GIỌNG THUẦN VIỆT CHUẨN REVIEW TRUYỆN (KHÔNG BAO GIỜ LỚ GIỌNG NƯỚC NGOÀI) ---
    "chi_google_review_chuan": {
        "ten": "🌟 Chị Google Review Truyện — Nữ Miền Bắc Quốc Dân (Chuẩn 100% Tiếng Việt · TikTok/YouTube Recap)",
        "voice_id": "google_vi_native",
        "preset_hf": "ngoc",
        "pitch_hz": "+0Hz",
        "atempo_mod": 1.0,
        "gioi_tinh": "nu",
        "vung_mien": "Miền Bắc (Thuần Việt)",
        "toc_do_mac_dinh": 1.20,
    },
    "nam_minh_kich_tinh": {
        "ten": "🎙️ Nam Minh (Thuần Việt) — Nam Miền Bắc Trầm Ấm (Đã khoá phiên âm Tiếng Việt 100%)",
        "voice_id": "vi-VN-NamMinhNeural",
        "preset_hf": "binh",
        "pitch_hz": "+0Hz",
        "atempo_mod": 1.0,
        "gioi_tinh": "nam",
        "vung_mien": "Miền Bắc",
        "toc_do_mac_dinh": 1.15,
    },
    "hoai_my_truyen_cam": {
        "ten": "🎙️ Hoài My (Thuần Việt) — Nữ Miền Nam Truyền Cảm (Đã khoá phiên âm Tiếng Việt 100%)",
        "voice_id": "vi-VN-HoaiMyNeural",
        "preset_hf": "doan",
        "pitch_hz": "+0Hz",
        "atempo_mod": 1.0,
        "gioi_tinh": "nu",
        "vung_mien": "Miền Nam",
        "toc_do_mac_dinh": 1.15,
    },
    "da_nhan_vat_thong_minh": {
        "ten": "🎭 Đa Nhân Vật Tự Động (Tự đổi giọng Nam / Nữ / Dẫn Chuyện theo từng cảnh)",
        "voice_id": "auto_role_cast",
        "preset_hf": "binh",
        "pitch_hz": "+0Hz",
        "atempo_mod": 1.0,
        "gioi_tinh": "auto",
        "vung_mien": "Đa miền",
        "toc_do_mac_dinh": 1.15,
    },
    "clone_giong_mau_5s": {
        "ten": "🧬 Nhái Giọng Từ File Mẫu 5 Giây (Zero-Shot Voice Cloning — Giọng bất kỳ)",
        "voice_id": "zero_shot_clone",
        "preset_hf": "custom_clone",
        "pitch_hz": "+0Hz",
        "atempo_mod": 1.0,
        "gioi_tinh": "custom",
        "vung_mien": "Theo mẫu",
        "toc_do_mac_dinh": 1.15,
    },
    # --- CÁC BIẾN THỂ GIỌNG ĐỌC THEO THỂ LOẠI TRUYỆN (GIỮ NGUYÊN DẤU THANH TIẾNG VIỆT +0Hz) ---
    "hoang_binh_tu_tien": {
        "ten": "⚔️ Hoàng Bình — Nam Miền Bắc (Kể Chuyện Hành Động & Tu Tiên)",
        "voice_id": "vi-VN-NamMinhNeural",
        "preset_hf": "binh",
        "pitch_hz": "+0Hz",
        "atempo_mod": 0.98,
        "gioi_tinh": "nam",
        "vung_mien": "Miền Bắc",
        "toc_do_mac_dinh": 1.15,
    },
    "bac_si_tuyen_trinh_tham": {
        "ten": "📜 Minh Tuyên — Nam Điềm Đạm (Kể Chuyện Trinh Thám & Lịch Sử)",
        "voice_id": "vi-VN-NamMinhNeural",
        "preset_hf": "tuyen",
        "pitch_hz": "+0Hz",
        "atempo_mod": 0.95,
        "gioi_tinh": "nam",
        "vung_mien": "Miền Bắc",
        "toc_do_mac_dinh": 1.10,
    },
    "xuan_vinh_tong_tai": {
        "ten": "👑 Xuân Vĩnh — Nam Trầm Ấm (Review Đô Thị & Học Đường)",
        "voice_id": "vi-VN-NamMinhNeural",
        "preset_hf": "vinh",
        "pitch_hz": "+0Hz",
        "atempo_mod": 0.97,
        "gioi_tinh": "nam",
        "vung_mien": "Miền Bắc",
        "toc_do_mac_dinh": 1.12,
    },
    "khoi_nguyen_mien_nam": {
        "ten": "🔥 Khôi Nguyên — Nam Trẻ Trung (Review Hài Hước & Thể Thao Nhịp Nhanh)",
        "voice_id": "vi-VN-NamMinhNeural",
        "preset_hf": "nguyen",
        "pitch_hz": "+0Hz",
        "atempo_mod": 1.05,
        "gioi_tinh": "nam",
        "vung_mien": "Miền Nam",
        "toc_do_mac_dinh": 1.20,
    },
    "quang_son_mien_trung": {
        "ten": "⛰️ Quang Sơn — Nam Chất Phác (Kiếm Hiệp & Cổ Trang)",
        "voice_id": "vi-VN-NamMinhNeural",
        "preset_hf": "son",
        "pitch_hz": "+0Hz",
        "atempo_mod": 0.98,
        "gioi_tinh": "nam",
        "vung_mien": "Miền Trung",
        "toc_do_mac_dinh": 1.15,
    },
    "hac_am_phan_dien": {
        "ten": "😈 Hắc Ám Lão Tổ — Giọng Trầm Uy Áp",
        "voice_id": "vi-VN-NamMinhNeural",
        "preset_hf": "vinh",
        "pitch_hz": "+0Hz",
        "atempo_mod": 0.92,
        "gioi_tinh": "nam",
        "vung_mien": "Cổ trang",
        "toc_do_mac_dinh": 1.05,
    },
    "ngoc_huyen_mien_bac": {
        "ten": "🌸 Ngọc Huyền — Nữ Miền Bắc (Trong Trẻo · Thanh Xuân & Học Đường)",
        "voice_id": "google_vi_native",
        "preset_hf": "ngoc",
        "pitch_hz": "+0Hz",
        "atempo_mod": 1.02,
        "gioi_tinh": "nu",
        "vung_mien": "Miền Bắc",
        "toc_do_mac_dinh": 1.18,
    },
    "thuc_doan_ngot_ngao": {
        "ten": "🌺 Thục Đoan — Nữ Miền Nam (Ngọt Ngào · Chữa Lành & Xuyên Không)",
        "voice_id": "vi-VN-HoaiMyNeural",
        "preset_hf": "doan",
        "pitch_hz": "+0Hz",
        "atempo_mod": 1.0,
        "gioi_tinh": "nu",
        "vung_mien": "Miền Nam",
        "toc_do_mac_dinh": 1.15,
    },
    "truc_ly_nu_cuong": {
        "ten": "❄️ Trúc Ly — Nữ Sắc Sảo (Nữ Cường & Nhịp Nhanh)",
        "voice_id": "google_vi_native",
        "preset_hf": "ly",
        "pitch_hz": "+0Hz",
        "atempo_mod": 1.05,
        "gioi_tinh": "nu",
        "vung_mien": "Miền Bắc",
        "toc_do_mac_dinh": 1.22,
    },
    "my_duyen_ca_khia": {
        "ten": "😂 Mỹ Duyên — Nữ Năng Động (Bắt Trend · Review Hài Hước TikTok)",
        "voice_id": "vi-VN-HoaiMyNeural",
        "preset_hf": "duyen",
        "pitch_hz": "+0Hz",
        "atempo_mod": 1.06,
        "gioi_tinh": "nu",
        "vung_mien": "Miền Nam",
        "toc_do_mac_dinh": 1.25,
    },
    "thu_huong_ke_chuyen": {
        "ten": "🌙 Thu Hương — Nữ Sâu Lắng (Kể Chuyện Tâm Lý & Đời Thường)",
        "voice_id": "vi-VN-HoaiMyNeural",
        "preset_hf": "huong",
        "pitch_hz": "+0Hz",
        "atempo_mod": 0.96,
        "gioi_tinh": "nu",
        "vung_mien": "Miền Nam",
        "toc_do_mac_dinh": 1.10,
    },
}


# Bộ từ điển phiên âm Tiếng Việt thuần bản xứ cho các tên nhân vật Nhật/Hàn/Anh và thuật ngữ:
# Giúp bộ đọc TTS KHÔNG BAO GIỜ tự động chuyển sang giọng người nước ngoài (Multilingual English Accent) giữa câu!
BANG_PHIEN_AM_THUAN_VIET: list[tuple[str, str]] = [
    (r"\bBad\s*-\s*Con\s*!?", "Bát Con"),
    (r"\bChapter\s*[-#]?\s*0*(\d+)\b", r"chương \1"),
    (r"\bChap\s*[-#]?\s*0*(\d+)\b", r"chương \1"),
    (r"\bHaruka\s*-\s*chan\b", "Ha ru ca"),
    (r"\bHaruka\b", "Ha ru ca"),
    (r"\bHiyori\s*-\s*senpai\b", "đàn chị Hi dô ri"),
    (r"\bHiyori\b", "Hi dô ri"),
    (r"\bHiyor\b", "Hi dô ri"),
    (r"\bLai\s*-\s*chan\b", "Lai"),
    (r"\bsenpai\b", "đàn chị"),
    (r"\bkouhai\b", "đàn em"),
    (r"\bsmash\b", "đập cầu"),
    (r"\bserve\b", "giao cầu"),
    (r"\bhandicap\b", "chấp điểm"),
    (r"\bcool\b", "ngầu"),
    (r"\bmain\b", "nhân vật chính"),
    (r"\bskill\b", "kỹ năng"),
    (r"\blevel\b", "cấp độ"),
    (r"\bparty\b", "tổ đội"),
    (r"\bdungeon\b", "hầm ngục"),
    (r"\bguild\b", "hội"),
    (r"\bquest\b", "nhiệm vụ"),
    (r"\brank\b", "hạng"),
    (r"\bSung\s+Jin\s*-?\s*Woo\b", "Sung Gin Gu"),
    (r"\bJin\s*-?\s*Woo\b", "Gin Gu"),
    (r"\bNaruto\b", "Na ru tô"),
    (r"\bSasuke\b", "Sa su kê"),
    (r"\bSakura\b", "Sa ku ra"),
    (r"\bLuffy\b", "Lúp phi"),
    (r"\bZoro\b", "Dô rô"),
    (r"\bGoku\b", "Gô ku"),
]


def chuan_hoa_van_ban_thuan_viet_cho_tts(van_ban: str) -> str:
    """
    Chuyển đổi mọi từ tiếng Anh / hậu tố Nhật-Hàn (-chan, -senpai, -kun, Chapter-003, smash...)
    sang âm đọc thuần Việt 100% trước khi đưa vào bộ phát âm TTS.
    Nhờ đó bộ đọc Neural giữ nguyên 100% ngữ điệu người Việt bản xứ, tuyệt đối không bị lớ giọng Tây!
    """
    s = (van_ban or "").strip()
    if not s:
        return ""
    for pat, rep in BANG_PHIEN_AM_THUAN_VIET:
        s = re.sub(pat, rep, s, flags=re.I)
    # Xoá các hậu tố Nhật còn sót như -chan, -kun, -san, -sama để tránh đọc thành âm tiếng Anh
    s = re.sub(r"\b([A-Za-zÀ-ỹ]+)\s*-\s*(?:chan|kun|san|sama)\b", r"\1", s, flags=re.I)
    # Thay ký hiệu & và / bằng từ tiếng Việt
    s = s.replace("&", " và ").replace("/", " hoặc ")
    # Loại bỏ các dấu ngoặc hoặc ký tự đặc biệt làm ngắt nhịp máy móc
    s = re.sub(r"[\"*#_~`<>|]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


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
        "neural_voice_ready": True,
        "edge_neural_ready": co_edge_tts,
        "onnx_pro_voice_ready": co_vieneu,
        "ffmpeg_ready": bool(ffmpeg_exe),
        "ffmpeg_path": ffmpeg_exe or "",
    }


def cai_dat_tu_dong_goi_giong_doc_va_mp4(cai_them_onnx_pro: bool = False) -> tuple[bool, str]:
    import sys

    ds_goi = ["Pillow", "edge-tts", "imageio-ffmpeg", "rapidocr-onnxruntime"]
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
        return True, f"Đã cài đặt & đồng bộ thành công kho {len(DANH_SACH_GIONG_DOC)} giọng đọc Thuần Việt ({', '.join(ds_goi)})"
    except Exception as exc:
        return False, f"Không thể tự động cài gói mở rộng: {exc}"


def chon_giong_theo_vai_tro_nhan_vat(vai_tro: str = "", ten_nhan_vat: str = "", scene_index: int = 1) -> str:
    vt = (vai_tro or "").lower()
    ten = (ten_nhan_vat or "").lower()
    if any(k in vt or k in ten for k in ("nữ", "tiểu thư", "cô", "đàn chị", "đàn em", "haruka", "hiyori", "lai", "tuyết", "ly", "ngọc", "huyền", "my", "hương")):
        return "chi_google_review_chuan" if scene_index % 2 == 1 else "hoai_my_truyen_cam"
    if any(k in vt or k in ten for k in ("phản diện", "trùm", "ma tôn", "kẻ địch", "đối thủ", "lão", "hổ")):
        return "hac_am_phan_dien"
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


def _chuyen_mp3_sang_wav_chuan(mp3_path: Path, out_wav: Path, *, atempo: float = 1.0) -> bool:
    ff = tim_ffmpeg_he_thong()
    if not ff or not mp3_path.is_file():
        return False
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        atempo_clamped = max(0.75, min(1.65, float(atempo or 1.0)))
        cmd = [ff, "-y", "-i", str(mp3_path)]
        if abs(atempo_clamped - 1.0) >= 0.03:
            cmd.extend(["-filter:a", f"atempo={atempo_clamped:.2f}"])
        cmd.extend(["-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(out_wav)])
        subprocess.run(
            cmd,
            timeout=25,
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


def _chia_doan_ngan_google_tts(van_ban: str, max_chars: int = 175) -> list[str]:
    """Chia câu dài thành các mệnh đề <= 175 ký tự theo dấu chấm/phẩy để gọi Google Native Vietnamese TTS mượt mà."""
    cau_tach = re.split(r"(?<=[.!?;,])\s+", van_ban.strip())
    chunks: list[str] = []
    cur = ""
    for c in cau_tach:
        if not c:
            continue
        if len(cur) + len(c) + 1 <= max_chars:
            cur = f"{cur} {c}".strip() if cur else c
        else:
            if cur:
                chunks.append(cur)
            if len(c) <= max_chars:
                cur = c
            else:
                words = c.split()
                cur = ""
                for w in words:
                    if len(cur) + len(w) + 1 <= max_chars:
                        cur = f"{cur} {w}".strip() if cur else w
                    else:
                        if cur:
                            chunks.append(cur)
                        cur = w
    if cur:
        chunks.append(cur)
    return chunks or [van_ban[:max_chars]]


def _thu_goi_google_viet_native(
    van_ban: str,
    toc_do: float,
    out_wav: Path,
) -> tuple[bool, Path]:
    """
    Tổng hợp giọng đọc "Chị Google Review Truyện" (Chuẩn 100% người Việt bản xứ `tl=vi`,
    không bao giờ bị lớ giọng Tây kể cả khi câu có tên riêng).
    """
    try:
        van_ban_viet = chuan_hoa_van_ban_thuan_viet_cho_tts(van_ban)
        chunks = _chia_doan_ngan_google_tts(van_ban_viet)
        mp3_parts: list[bytes] = []
        for ch in chunks:
            q = urllib.parse.quote(ch)
            url = f"https://translate.googleapis.com/translate_tts?ie=UTF-8&q={q}&tl=vi&client=tw-ob"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0"},
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = resp.read()
                if data and len(data) > 128:
                    mp3_parts.append(data)
        if not mp3_parts:
            return False, out_wav
        mp3_tmp = out_wav.with_suffix(".mp3")
        mp3_tmp.write_bytes(b"".join(mp3_parts))
        if _chuyen_mp3_sang_wav_chuan(mp3_tmp, out_wav, atempo=toc_do):
            try:
                mp3_tmp.unlink()
            except Exception:
                pass
            return True, out_wav
        return True, mp3_tmp
    except Exception:
        return False, out_wav


def _thu_goi_vieneu_onnx(
    van_ban: str,
    out_wav: Path,
    *,
    preset_voice: str = "binh",
    ref_audio_path: str | Path | None = None,
) -> bool:
    try:
        from vieneu import Vieneu  # type: ignore

        van_ban_viet = chuan_hoa_van_ban_thuan_viet_cho_tts(van_ban)
        tts = Vieneu()
        if ref_audio_path and Path(ref_audio_path).is_file():
            audio = tts.infer(text=van_ban_viet, ref_audio=str(ref_audio_path))
        else:
            try:
                audio = tts.infer(text=van_ban_viet, voice=preset_voice)
            except TypeError:
                audio = tts.infer(text=van_ban_viet)
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
    Tổng hợp giọng đọc Neural (`vi-VN-NamMinhNeural` / `vi-VN-HoaiMyNeural`) sau khi đã
    chuyển phiên âm 100% sang âm tiết Tiếng Việt (`chuan_hoa_van_ban_thuan_viet_cho_tts`)
    và giữ nguyên dấu thanh tự nhiên (`pitch_hz='+0Hz'`) để không bị lớ giọng nước ngoài.
    """
    try:
        import asyncio
        import edge_tts  # type: ignore

        van_ban_viet = chuan_hoa_van_ban_thuan_viet_cho_tts(van_ban)
        pct = int(round((toc_do - 1.0) * 100))
        rate_str = f"+{pct}%" if pct >= 0 else f"{pct}%"
        mp3_tmp = out_wav.with_suffix(".mp3")

        async def _run():
            comm = edge_tts.Communicate(van_ban_viet, voice=voice_id, rate=rate_str, pitch="+0Hz")
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


def tong_hop_giong_doc_phan_canh(
    van_ban: str,
    out_dir: Path,
    *,
    scene_index: int = 1,
    ma_giong: str = "chi_google_review_chuan",
    toc_do: float = 1.15,
    vai_tro_nhan_vat: str = "",
    ten_nhan_vat: str = "",
    file_giong_mau_clone: str | Path | None = None,
    che_do_nhanh_offline: bool = False,
) -> dict[str, Any]:
    """
    Tổng hợp file âm thanh thuyết minh Thuần Việt cho 1 phân cảnh Storyboard:
    - Tự động chuẩn hoá phiên âm Tiếng Việt (`chuan_hoa_van_ban_thuan_viet_cho_tts`) để tuyệt đối không bị giọng Tây đọc Tiếng Việt.
    - Hỗ trợ giọng Chị Google Review Quốc Dân (`chi_google_review_chuan`), Giọng Nam Minh / Hoài My Thuần Việt, và Nhái giọng 5s.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    ma_giong_thuc = ma_giong
    if ma_giong == "da_nhan_vat_thong_minh":
        ma_giong_thuc = chon_giong_theo_vai_tro_nhan_vat(vai_tro_nhan_vat, ten_nhan_vat, scene_index)

    info = DANH_SACH_GIONG_DOC.get(ma_giong_thuc) or DANH_SACH_GIONG_DOC["chi_google_review_chuan"]
    voice_id = str(info.get("voice_id") or "google_vi_native")
    preset_hf = str(info.get("preset_hf") or "ngoc")
    pitch_hz = str(info.get("pitch_hz") or "+0Hz")
    atempo_mod = float(info.get("atempo_mod") or 1.0)
    toc_do_thuc = round(max(0.8, min(1.55, float(toc_do or 1.15) * atempo_mod)), 2)

    thoi_luong = uoc_tinh_thoi_luong_cau(van_ban, toc_do=toc_do_thuc)
    wav_path = out_dir / f"scene_{scene_index:03d}.wav"
    actual_audio_path = wav_path

    da_tao = False
    if not che_do_nhanh_offline:
        # 1. Nếu chọn Nhái giọng 5s hoặc máy đã cài Lõi ONNX (VieNeu)
        if ma_giong == "clone_giong_mau_5s" or file_giong_mau_clone:
            da_tao = _thu_goi_vieneu_onnx(
                van_ban, wav_path, preset_voice=preset_hf, ref_audio_path=file_giong_mau_clone
            )
        # 2. Nếu chọn dòng giọng Chị Google Review Chuẩn Thuần Việt (hoặc Ngọc Huyền / Trúc Ly)
        if not da_tao and voice_id == "google_vi_native":
            da_tao, actual_audio_path = _thu_goi_google_viet_native(van_ban, toc_do_thuc, wav_path)
        # 3. Nếu chọn giọng Neural đã khoá phiên âm Thuần Việt (Nam Minh / Hoài My)
        if not da_tao and voice_id.startswith("vi-VN-"):
            da_tao, actual_audio_path = _thu_goi_edge_neural(
                van_ban, voice_id, toc_do_thuc, wav_path, pitch_hz=pitch_hz
            )
        # 4. Dự phòng an toàn luôn dùng giọng Chị Google Thuần Việt (TUYỆT ĐỐI không gọi Windows SAPI tiếng Anh)
        if not da_tao:
            da_tao, actual_audio_path = _thu_goi_google_viet_native(van_ban, toc_do_thuc, wav_path)

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
