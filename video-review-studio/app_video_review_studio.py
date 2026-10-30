from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import threading
import tkinter as tk
import zipfile
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Any

_STUDIO_DIR = str(Path(__file__).resolve().parent)
if _STUDIO_DIR not in sys.path:
    sys.path.insert(0, _STUDIO_DIR)
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

from core_tts_voice import (
    DANH_SACH_GIONG_DOC,
    cai_dat_tu_dong_goi_giong_doc_va_mp4,
    kiem_tra_ha_tang_giong_doc_va_video,
    lay_danh_sach_giong_elevenlabs,
    tong_hop_giong_doc_phan_canh,
)
from core_video_renderer import (
    DANH_SACH_NHAC_NEN,
    DINH_DANG_VIDEO,
    GOI_LUOT_VIDEO_REVIEW,
    ve_khung_hinh_pan_zoom_va_phu_de,
    xac_thuc_va_tru_luot_video_cloud,
    xuat_video_review_mp4,
)
from core_vision_character import (
    PHONG_CACH_KICH_BAN,
    CharacterCastMemory,
    lam_sach_thoai_ocr_cho_review,
    sinh_kich_ban_review_chuong,
    tach_khung_tranh_thong_minh,
    tu_dong_quet_ho_so_nhan_vat_tu_thoai,
)


CAU_HINH_STUDIO_PATH = Path.home() / ".manga_video_review_studio_config.json"
CAU_HINH_APP_DICH_PATH = Path.home() / ".manga_translator_win_config.json"


def doc_cau_hinh_studio() -> dict[str, Any]:
    mac_dinh: dict[str, Any] = {
        "server_url": "https://translation-api.vibe1.tinhgon.xyz",
        "token": "",
        "phong_cach": "hai_huoc",
        "dinh_dang": "tiktok_9_16",
        "ma_giong": "elevenlabs_auto_cam_xuc",
        "goi_luot": "review_standard",
        "toc_do_doc": 1.20,
        "elevenlabs_api_key": "",
        "elevenlabs_voice_id": "",
    }
    if CAU_HINH_APP_DICH_PATH.is_file():
        try:
            cfg_dich = json.loads(CAU_HINH_APP_DICH_PATH.read_text(encoding="utf-8"))
            if isinstance(cfg_dich, dict) and cfg_dich.get("token"):
                mac_dinh["token"] = str(cfg_dich["token"])
        except Exception:
            pass
    if CAU_HINH_STUDIO_PATH.is_file():
        try:
            cfg = json.loads(CAU_HINH_STUDIO_PATH.read_text(encoding="utf-8"))
            if isinstance(cfg, dict):
                mac_dinh.update({k: v for k, v in cfg.items() if v is not None})
        except Exception:
            pass
    return mac_dinh


def luu_cau_hinh_studio(data: dict[str, Any]) -> None:
    try:
        CAU_HINH_STUDIO_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _quet_ocr_nhanh_tren_anh(img_bytes: bytes) -> list[str]:
    """Dự phòng quét chữ trực tiếp trên ảnh nếu thư mục chưa có sẵn tệp trang-thai.json."""
    try:
        from rapidocr_onnxruntime import RapidOCR
        from PIL import Image
        with Image.open(io.BytesIO(img_bytes)) as im:
            im_rgb = im.convert("RGB")
            engine = RapidOCR()
            res, _ = engine(im_rgb, use_cls=False)
        if not res:
            return []
        lines: list[str] = []
        for item in res:
            if isinstance(item, (list, tuple)) and len(item) >= 3:
                txt = lam_sach_thoai_ocr_cho_review(str(item[1] or ""))
                score = float(item[2] or 0.0)
                if txt and score >= 0.45:
                    lines.append(txt)
        return lines
    except Exception:
        return []


def nap_danh_sach_anh_va_thoai_tu_thu_muc(folder_path: Path) -> tuple[list[bytes], list[list[str]]]:
    """
    Quét thư mục Chapter (hoặc file .zip/.cbz):
    - Đọc trực tiếp dữ liệu vùng thoại từ `trang-thai.json` (hoặc `_translation_ledger.json`) theo đúng thứ tự trang
      (`001.jpg` -> `pages[0]`, `002.jpg` -> `pages[1]`...) kèm cả `ban_dich` lẫn `chu_goc` để AI biên kịch hiểu đúng 100% cốt truyện!
    - Nếu thư mục ảnh chưa qua App dịch (chưa có `trang-thai.json`), tự động quét OCR trực tiếp trên ảnh.
    """
    folder_path = Path(folder_path)
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    if folder_path.is_file() and folder_path.suffix.lower() in (".zip", ".cbz"):
        panels_zip: list[bytes] = []
        ocr_zip: list[list[str]] = []
        with zipfile.ZipFile(folder_path, "r") as zf:
            names = sorted(
                [n for n in zf.namelist() if Path(n).suffix.lower() in exts and not Path(n).name.startswith("_")],
                key=lambda s: s.lower(),
            )
            for name in names:
                for pb in tach_khung_tranh_thong_minh(zf.read(name)):
                    panels_zip.append(pb)
                    ocr_zip.append(_quet_ocr_nhanh_tren_anh(pb))
        if not panels_zip:
            raise ValueError(f"Gói nén không chứa ảnh hợp lệ: {folder_path}")
        return panels_zip, ocr_zip

    files = sorted(
        [p for p in folder_path.iterdir() if p.is_file() and p.suffix.lower() in exts and not p.name.startswith("_")],
        key=lambda p: p.name.lower(),
    )
    if not files:
        raise ValueError(f"Không tìm thấy ảnh (.jpg/.png/.webp) trong thư mục: {folder_path}")

    thoai_theo_file: dict[str, list[str]] = {}
    for ten_ledger in ("trang-thai.json", "_translation_ledger.json"):
        ledger_file = folder_path / ten_ledger
        if not ledger_file.is_file():
            continue
        try:
            ledger_data = json.loads(ledger_file.read_text(encoding="utf-8"))
            pages = ledger_data.get("pages") or []
            for p_idx, p in enumerate(pages):
                regs = [r for r in (p.get("regions") or []) if isinstance(r, dict)]
                # Sắp xếp bóng thoại theo từng tầng khung tranh (mỗi tầng ~1100px trên trang chuẩn) và từ PHẢI sang TRÁI (-x) chuẩn Manga
                regs.sort(key=lambda r: (int(r.get("y") or 0) // 1100, -int(r.get("x") or 0), int(r.get("y") or 0)))

                # Gom các mảnh chữ ngắn (<= 22 ký tự) nằm trong cùng một tầng khung tranh bị tách rời
                merged_raw_goc: list[tuple[str, str]] = []
                cur_parts: list[tuple[int, int, str]] = []
                cur_dich: str = ""
                for r in regs:
                    rx = int(r.get("x") or 0)
                    ry = int(r.get("y") or 0)
                    rgoc = str(r.get("chu_goc") or "").strip()
                    rdich = str(r.get("ban_dich") or "").strip()
                    if not rgoc and not rdich:
                        continue
                    if cur_parts:
                        last_x, last_y, last_txt = cur_parts[-1]
                        if (ry // 1100 == last_y // 1100) and (len(last_txt) <= 22 and len(rgoc) <= 22):
                            cur_parts.append((rx, ry, rgoc))
                            if not cur_dich and rdich:
                                cur_dich = rdich
                            continue
                        else:
                            merged_raw_goc.append((" ".join(pt[2] for pt in cur_parts if pt[2]), cur_dich))
                            cur_parts = []
                            cur_dich = ""
                    cur_parts = [(rx, ry, rgoc)]
                    cur_dich = rdich
                if cur_parts:
                    merged_raw_goc.append((" ".join(pt[2] for pt in cur_parts if pt[2]), cur_dich))

                ds_cau: list[str] = []
                for raw_goc, raw_dich in merged_raw_goc:
                    goc = lam_sach_thoai_ocr_cho_review(raw_goc)
                    if raw_goc and not goc:
                        # Bỏ qua các vùng ký tự SFX / mảnh chữ rác đã bị bộ lọc loại bỏ
                        continue
                    if goc:
                        ds_cau.append(goc)
                    else:
                        dich = lam_sach_thoai_ocr_cho_review(raw_dich)
                        if dich:
                            ds_cau.append(dich)
                fname = str(p.get("output_name") or "")
                if fname:
                    thoai_theo_file[Path(fname).name] = ds_cau
                if p_idx < len(files):
                    thoai_theo_file[files[p_idx].name] = ds_cau
                thoai_theo_file[f"{p_idx + 1:03d}.jpg"] = ds_cau
            break
        except Exception:
            pass

    panels_out: list[bytes] = []
    ocr_per_panel: list[list[str]] = []
    for f in files:
        raw_b = f.read_bytes()
        sub_panels = tach_khung_tranh_thong_minh(raw_b)
        ds_thoai_trang = thoai_theo_file.get(f.name)
        if ds_thoai_trang is None:
            ds_thoai_trang = _quet_ocr_nhanh_tren_anh(raw_b)
        so_sub = len(sub_panels)
        for idx_p, pb in enumerate(sub_panels):
            panels_out.append(pb)
            if so_sub == 1:
                ocr_per_panel.append(ds_thoai_trang)
            else:
                # Chia đều các câu thoại theo thứ tự khung tranh con từ trên xuống dưới
                start_i = (idx_p * len(ds_thoai_trang)) // so_sub
                end_i = ((idx_p + 1) * len(ds_thoai_trang)) // so_sub
                ocr_per_panel.append(ds_thoai_trang[start_i:end_i])

    return panels_out, ocr_per_panel


class AppVideoReviewStudio(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🎬 Manga/Manhwa Video Review Studio v1.0 — Tự Động Biên Kịch, Nhận Diện Nhân Vật & Lồng Tiếng MP4")
        self.geometry("1220x780")
        self.configure(bg="#0b0f19")

        self.cau_hinh = doc_cau_hinh_studio()
        self.cast_memory = CharacterCastMemory(Path.home() / ".manga_video_character_bible.json")
        self.panels_bytes: list[bytes] = []
        self.ocr_per_panel: list[list[str]] = []
        self.kich_ban_hien_tai: dict[str, Any] = {}
        self.dang_xu_ly = False

        self._dung_giao_dien()

    def _dung_giao_dien(self):
        header = tk.Frame(self, bg="#111827", padx=16, pady=10)
        header.pack(fill="x")
        tk.Label(
            header,
            text="🎬 MANGA / MANHWA VIDEO REVIEW STUDIO",
            bg="#111827",
            fg="#f97316",
            font=("Segoe UI", 13, "bold"),
        ).pack(side="left")
        tk.Label(
            header,
            text="Biên kịch Thị giác 2x2 · Hồ sơ Nhân vật xuyên Chapter · Lồng tiếng AI & Xuất MP4 (TikTok 9:16 / YouTube 16:9)",
            bg="#111827",
            fg="#94a3b8",
            font=("Segoe UI", 9),
        ).pack(side="left", padx=12)

        main_body = tk.Frame(self, bg="#0b0f19", padx=14, pady=10)
        main_body.pack(fill="both", expand=True)

        left_col = tk.Frame(main_body, bg="#111827", width=470, padx=14, pady=12)
        left_col.pack(side="left", fill="y")
        left_col.pack_propagate(False)

        right_col = tk.Frame(main_body, bg="#0b0f19")
        right_col.pack(side="left", fill="both", expand=True, padx=(12, 0))

        # --- BƯỚC 1: TÀI KHOẢN & NGUỒN CHAPTER ---
        tk.Label(left_col, text="01 · NGUỒN ẢNH CHAPTER & TÀI KHOẢN VÍ LƯỢT", bg="#111827", fg="#38bdf8", font=("Segoe UI", 9, "bold")).pack(anchor="w")

        f_tok = tk.Frame(left_col, bg="#111827", pady=4)
        f_tok.pack(fill="x")
        tk.Label(f_tok, text="Mã Phiên / API Key:", bg="#111827", fg="#cbd5e1", width=16, anchor="w").pack(side="left")
        self.ent_token = tk.Entry(f_tok, bg="#1e293b", fg="#f8fafc", insertbackground="#fff", show="•")
        self.ent_token.insert(0, str(self.cau_hinh.get("token") or ""))
        self.ent_token.pack(side="left", fill="x", expand=True, padx=(4, 0))

        f_chap = tk.Frame(left_col, bg="#111827", pady=4)
        f_chap.pack(fill="x")
        tk.Label(f_chap, text="Nguồn Chapter:", bg="#111827", fg="#cbd5e1", width=16, anchor="w").pack(side="left")
        self.ent_folder = tk.Entry(f_chap, bg="#1e293b", fg="#f8fafc", insertbackground="#fff")
        self.ent_folder.pack(side="left", fill="x", expand=True, padx=4)
        tk.Button(f_chap, text="📂 Thư mục", bg="#2563eb", fg="#fff", relief="flat", padx=6, command=self._chon_thu_muc_chapter).pack(side="left", padx=2)
        tk.Button(f_chap, text="📦 ZIP/CBZ", bg="#334155", fg="#fff", relief="flat", padx=6, command=self._chon_file_zip_chapter).pack(side="left")

        f_meta = tk.Frame(left_col, bg="#111827", pady=4)
        f_meta.pack(fill="x")
        tk.Label(f_meta, text="Tên bộ truyện:", bg="#111827", fg="#cbd5e1", width=16, anchor="w").pack(side="left")
        self.ent_ten_truyen = tk.Entry(f_meta, bg="#1e293b", fg="#f8fafc", insertbackground="#fff")
        self.ent_ten_truyen.insert(0, "Siêu Phẩm Truyện Tranh")
        self.ent_ten_truyen.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # --- BƯỚC 2: HỒ SƠ NHÂN VẬT (CHỐNG NHẦM NGƯỜI NÓI) ---
        tk.Label(left_col, text="02 · HỒ SƠ NHÂN VẬT (ĐỊNH DANH NGƯỜI NÓI)", bg="#111827", fg="#34d399", font=("Segoe UI", 9, "bold"), pady=6).pack(anchor="w")
        f_cast_btns = tk.Frame(left_col, bg="#111827")
        f_cast_btns.pack(fill="x", pady=(0, 8))
        tk.Button(
            f_cast_btns,
            text="🎭 Mở Bảng Hồ Sơ Nhân Vật",
            bg="#059669",
            fg="#ffffff",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            pady=6,
            command=self._mo_cua_so_ho_so_nhan_vat,
        ).pack(side="left", fill="x", expand=True, padx=(0, 4))
        tk.Button(
            f_cast_btns,
            text="🔍 Tự Quét Nhân Vật",
            bg="#0d9488",
            fg="#ffffff",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            pady=6,
            command=self._tu_dong_quet_nhan_vat,
        ).pack(side="left", fill="x", expand=True)

        # --- BƯỚC 3: PHONG CÁCH KỊCH BẢN & GIỌNG ĐỌC ---
        tk.Label(left_col, text="03 · PHONG CÁCH REVIEW & LÕI GIỌNG ĐỌC AI", bg="#111827", fg="#fbbf24", font=("Segoe UI", 9, "bold"), pady=4).pack(anchor="w")

        tk.Label(left_col, text="Phong cách biên kịch thuyết minh:", bg="#111827", fg="#cbd5e1").pack(anchor="w")
        self.cmb_phong_cach = ttk.Combobox(
            left_col,
            values=[f"{k} — {v['ten']}" for k, v in PHONG_CACH_KICH_BAN.items()],
            state="readonly",
        )
        self.cmb_phong_cach.current(0)
        self.cmb_phong_cach.pack(fill="x", pady=(2, 5))

        tk.Label(left_col, text="Khung hình Video xuất bản:", bg="#111827", fg="#cbd5e1").pack(anchor="w")
        self.cmb_dinh_dang = ttk.Combobox(
            left_col,
            values=[f"{k} — {v['ten']}" for k, v in DINH_DANG_VIDEO.items()],
            state="readonly",
        )
        self.cmb_dinh_dang.current(0)
        self.cmb_dinh_dang.pack(fill="x", pady=(2, 5))

        f_el_key = tk.Frame(left_col, bg="#111827")
        f_el_key.pack(fill="x", pady=(2, 3))
        tk.Label(f_el_key, text="ElevenLabs Key:", bg="#111827", fg="#f97316", width=14, anchor="w", font=("Segoe UI", 8, "bold")).pack(side="left")
        self.ent_elevenlabs_key = tk.Entry(f_el_key, bg="#1e293b", fg="#f8fafc", insertbackground="#fff", show="•")
        self.ent_elevenlabs_key.insert(0, str(self.cau_hinh.get("elevenlabs_api_key") or ""))
        self.ent_elevenlabs_key.pack(side="left", fill="x", expand=True, padx=4)
        tk.Button(
            f_el_key,
            text="🔄 Nạp Giọng",
            bg="#ea580c",
            fg="#fff",
            font=("Segoe UI", 8, "bold"),
            relief="flat",
            padx=6,
            command=self._nap_danh_sach_giong_elevenlabs,
        ).pack(side="left")

        f_el_vid = tk.Frame(left_col, bg="#111827")
        f_el_vid.pack(fill="x", pady=(0, 4))
        tk.Label(f_el_vid, text="Voice ID (tuỳ chọn):", bg="#111827", fg="#94a3b8", width=16, anchor="w").pack(side="left")
        self.ent_elevenlabs_vid = tk.Entry(f_el_vid, bg="#1e293b", fg="#38bdf8", insertbackground="#fff")
        self.ent_elevenlabs_vid.insert(0, str(self.cau_hinh.get("elevenlabs_voice_id") or ""))
        self.ent_elevenlabs_vid.pack(side="left", fill="x", expand=True, padx=(4, 0))

        f_voice_row = tk.Frame(left_col, bg="#111827")
        f_voice_row.pack(fill="x", pady=(2, 5))
        tk.Label(
            f_voice_row,
            text=f"Kho Giọng Đọc AI (ElevenLabs Biểu Cảm + {len(DANH_SACH_GIONG_DOC)} Giọng Thuần Việt):",
            bg="#111827",
            fg="#cbd5e1",
        ).pack(anchor="w")
        self.cmb_giong = ttk.Combobox(
            f_voice_row,
            values=[f"{k} — {v['ten']}" for k, v in DANH_SACH_GIONG_DOC.items()],
            state="readonly",
        )
        self.cmb_giong.current(0)  # Mặc định ưu tiên ElevenLabs Auto Cảm Xúc (tự lùi về Thuần Việt nếu chưa điền Key)
        self.cmb_giong.pack(fill="x", pady=(2, 4))

        tk.Label(left_col, text="Nhạc nền không bản quyền (BGM -18dB) & Hiệu ứng chuyển cảnh:", bg="#111827", fg="#38bdf8").pack(anchor="w")
        self.cmb_nhac_nen = ttk.Combobox(
            left_col,
            values=[f"{k} — {v['ten']}" for k, v in DANH_SACH_NHAC_NEN.items()],
            state="readonly",
        )
        self.cmb_nhac_nen.current(0)
        self.cmb_nhac_nen.pack(fill="x", pady=(2, 4))

        f_clone = tk.Frame(left_col, bg="#111827")
        f_clone.pack(fill="x", pady=(0, 5))
        tk.Label(f_clone, text="Mẫu giọng Clone (5s):", bg="#111827", fg="#94a3b8", width=18, anchor="w").pack(side="left")
        self.ent_ref_audio = tk.Entry(f_clone, bg="#1e293b", fg="#f8fafc", insertbackground="#fff")
        self.ent_ref_audio.pack(side="left", fill="x", expand=True, padx=4)
        tk.Button(
            f_clone,
            text="🧬 Chọn WAV/MP3",
            bg="#6d28d9",
            fg="#fff",
            relief="flat",
            padx=6,
            command=self._chon_file_giong_mau,
        ).pack(side="left")

        f_spd = tk.Frame(left_col, bg="#111827")
        f_spd.pack(fill="x", pady=(0, 5))
        tk.Label(f_spd, text="Tốc độ giọng Review:", bg="#111827", fg="#cbd5e1").pack(side="left")
        self.cmb_toc_do = ttk.Combobox(
            f_spd,
            values=["1.00x (Chuẩn)", "1.15x (Chuẩn TikTok/YouTube Review)", "1.25x (Nhịp nhanh cuốn hút)", "1.35x (Siêu tốc Shorts)"],
            state="readonly",
            width=30,
        )
        self.cmb_toc_do.current(1)
        self.cmb_toc_do.pack(side="right")

        f_voice_tools = tk.Frame(left_col, bg="#111827")
        f_voice_tools.pack(fill="x", pady=(0, 6))
        tk.Button(
            f_voice_tools,
            text="🔊 Nghe Thử Giọng Này",
            bg="#0284c7",
            fg="#ffffff",
            font=("Segoe UI", 8, "bold"),
            relief="flat",
            pady=5,
            command=self._nghe_thu_giong_doc,
        ).pack(side="left", fill="x", expand=True, padx=(0, 4))
        tk.Button(
            f_voice_tools,
            text="⚙️ Cài / Đồng Bộ Giọng & MP4",
            bg="#475569",
            fg="#ffffff",
            font=("Segoe UI", 8, "bold"),
            relief="flat",
            pady=5,
            command=self._dong_bo_goi_giong_doc_va_mp4,
        ).pack(side="left", fill="x", expand=True)

        tk.Label(left_col, text="Gói xử lý Video (Tính vào Ví lượt tài khoản):", bg="#111827", fg="#cbd5e1").pack(anchor="w")
        self.cmb_goi_luot = ttk.Combobox(
            left_col,
            values=[f"{k} — {v['ten']}" for k, v in GOI_LUOT_VIDEO_REVIEW.items()],
            state="readonly",
        )
        self.cmb_goi_luot.current(0)
        self.cmb_goi_luot.pack(fill="x", pady=(2, 8))

        tk.Button(
            left_col,
            text="✨ BƯỚC 1: TẠO KỊCH BẢN STORYBOARD (DUYỆT TRƯỚC)",
            bg="#7c3aed",
            fg="#ffffff",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            pady=8,
            command=self._tao_kich_ban_storyboard,
        ).pack(fill="x", pady=3)

        tk.Button(
            left_col,
            text="🎬 BƯỚC 2: LỒNG TIẾNG & XUẤT VIDEO MP4",
            bg="#ea580c",
            fg="#ffffff",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            pady=9,
            command=self._xuat_video_mp4,
        ).pack(fill="x", pady=3)

        # --- CỘT PHẢI: STORYBOARD EDITOR & NHẬT KÝ ---
        sb_frame = tk.LabelFrame(
            right_col,
            text=" 📝 BẢNG DUYỆT & CHỈNH SỬA NHANH KỊCH BẢN THEO TỪNG KHUNG TRANH (STORYBOARD EDITOR) ",
            bg="#111827",
            fg="#38bdf8",
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=8,
        )
        sb_frame.pack(fill="both", expand=True)

        self.lst_scenes = tk.Listbox(sb_frame, height=11, bg="#0f172a", fg="#f8fafc", selectbackground="#2563eb", font=("Consolas", 10))
        self.lst_scenes.pack(fill="x", pady=(0, 6))
        self.lst_scenes.bind("<<ListboxSelect>>", self._khi_chon_phan_canh)

        f_edit = tk.Frame(sb_frame, bg="#111827")
        f_edit.pack(fill="x")
        tk.Label(f_edit, text="Nhân vật:", bg="#111827", fg="#fbbf24").pack(side="left")
        self.ent_nv_canh = tk.Entry(f_edit, width=18, bg="#1e293b", fg="#fbbf24", insertbackground="#fff")
        self.ent_nv_canh.pack(side="left", padx=4)
        tk.Label(f_edit, text="Ngữ điệu:", bg="#111827", fg="#38bdf8").pack(side="left", padx=(4, 2))
        self.cmb_cam_xuc_canh = ttk.Combobox(
            f_edit,
            values=["kich_tinh", "hai_huoc", "hoi_hop", "uy_ap", "cam_xuc", "mo_dau"],
            state="readonly",
            width=11,
        )
        self.cmb_cam_xuc_canh.current(0)
        self.cmb_cam_xuc_canh.pack(side="left", padx=4)
        tk.Button(f_edit, text="💾 Lưu sửa cảnh này", bg="#059669", fg="#fff", relief="flat", padx=8, command=self._luu_sua_phan_canh).pack(side="left", padx=4)
        tk.Button(f_edit, text="👁️ Xem Trước Khung Hình", bg="#2563eb", fg="#fff", relief="flat", padx=8, command=self._xem_truoc_khung_hinh_canh).pack(side="left")

        self.txt_loi_binh = scrolledtext.ScrolledText(sb_frame, height=5, bg="#1e293b", fg="#fde047", insertbackground="#fff", font=("Segoe UI", 10))
        self.txt_loi_binh.pack(fill="x", pady=6)

        log_frame = tk.LabelFrame(right_col, text=" 📟 NHẬT KÝ XỬ LÝ VIDEO STUDIO ", bg="#111827", fg="#94a3b8", font=("Segoe UI", 9, "bold"), padx=10, pady=6)
        log_frame.pack(fill="x", pady=(8, 0))
        self.txt_log = scrolledtext.ScrolledText(log_frame, height=8, bg="#090d16", fg="#a7f3d0", font=("Consolas", 9))
        self.txt_log.pack(fill="x")
        self.ghi_log("✅ Đã khởi động Manga/Manhwa Video Review Studio v1.0 (Độc lập 100% với luồng Dịch Truyện).")

    def ghi_log(self, msg: str) -> None:
        self.txt_log.insert("end", msg + "\n")
        self.txt_log.see("end")

    def _chon_thu_muc_chapter(self):
        d = filedialog.askdirectory(title="Chọn thư mục chứa ảnh Chapter truyện")
        if not d:
            return
        self.ent_folder.delete(0, "end")
        self.ent_folder.insert(0, d)
        p = Path(d)
        if p.parent.name:
            self.ent_ten_truyen.delete(0, "end")
            self.ent_ten_truyen.insert(0, p.parent.name)
        bible_local = p.parent / "character_bible.json"
        self.cast_memory = CharacterCastMemory(bible_local)
        self.ghi_log(f"📂 Đã chọn thư mục: {d} (Đã nạp {len(self.cast_memory.characters)} hồ sơ nhân vật).")

    def _chon_file_zip_chapter(self):
        f = filedialog.askopenfilename(title="Chọn gói ảnh Chapter (.zip / .cbz)", filetypes=[("Gói truyện", "*.zip *.cbz")])
        if not f:
            return
        self.ent_folder.delete(0, "end")
        self.ent_folder.insert(0, f)
        p = Path(f)
        self.ent_ten_truyen.delete(0, "end")
        self.ent_ten_truyen.insert(0, p.stem)
        bible_local = p.parent / "character_bible.json"
        self.cast_memory = CharacterCastMemory(bible_local)
        self.ghi_log(f"📦 Đã chọn gói truyện: {f}.")

    def _tu_dong_quet_nhan_vat(self):
        src_str = self.ent_folder.get().strip()
        if not src_str or not Path(src_str).exists():
            messagebox.showwarning("Chưa chọn nguồn ảnh", "Hãy chọn thư mục hoặc gói ZIP Chapter trước khi quét nhân vật!")
            return
        try:
            self.panels_bytes, self.ocr_per_panel = nap_danh_sach_anh_va_thoai_tu_thu_muc(Path(src_str))
            ds_quet = tu_dong_quet_ho_so_nhan_vat_tu_thoai(self.ocr_per_panel, self.cast_memory)
            ten_ds = ", ".join(c["ten"] for c in ds_quet)
            self.ghi_log(f"🔍 Đã tự động quét & cập nhật {len(ds_quet)} nhân vật vào Hồ sơ bộ truyện: {ten_ds}")
        except Exception as exc:
            messagebox.showerror("Lỗi quét nhân vật", str(exc))

    def _mo_cua_so_ho_so_nhan_vat(self):
        win = tk.Toplevel(self)
        win.title("🎭 Bảng Hồ Sơ Nhân Vật Xuyên Chapter (Chống nhầm người nói)")
        win.geometry("680x440")
        win.configure(bg="#0f172a")

        lst = tk.Listbox(win, height=8, bg="#1e293b", fg="#f8fafc", font=("Consolas", 10))
        lst.pack(fill="x", padx=14, pady=10)

        def _lam_moi():
            lst.delete(0, "end")
            for c in self.cast_memory.characters:
                lst.insert("end", f"[{c['vai_tro']}] {c['ten']} (Gọi: {c['xung_ho']}) — {c['ngoai_hinh']}")

        _lam_moi()

        form = tk.Frame(win, bg="#0f172a", padx=14)
        form.pack(fill="x")
        tk.Label(form, text="Tên nhân vật:", bg="#0f172a", fg="#cbd5e1").grid(row=0, column=0, sticky="w", pady=3)
        e_ten = tk.Entry(form, width=28, bg="#1e293b", fg="#fff", insertbackground="#fff")
        e_ten.grid(row=0, column=1, sticky="w", padx=6)

        tk.Label(form, text="Vai trò:", bg="#0f172a", fg="#cbd5e1").grid(row=0, column=2, sticky="w", pady=3)
        e_vai = tk.Entry(form, width=22, bg="#1e293b", fg="#fff", insertbackground="#fff")
        e_vai.insert(0, "Nam chính (Main)")
        e_vai.grid(row=0, column=3, sticky="w", padx=6)

        tk.Label(form, text="Cách gọi thuyết minh:", bg="#0f172a", fg="#cbd5e1").grid(row=1, column=0, sticky="w", pady=3)
        e_xung = tk.Entry(form, width=28, bg="#1e293b", fg="#fff", insertbackground="#fff")
        e_xung.insert(0, "thanh niên")
        e_xung.grid(row=1, column=1, sticky="w", padx=6)

        tk.Label(form, text="Ngoại hình nhận diện:", bg="#0f172a", fg="#cbd5e1").grid(row=2, column=0, sticky="w", pady=3)
        e_ngoai = tk.Entry(form, width=64, bg="#1e293b", fg="#fff", insertbackground="#fff")
        e_ngoai.insert(0, "Tóc đen ngắn, mặc áo khoác tối màu, cầm đoản kiếm")
        e_ngoai.grid(row=2, column=1, columnspan=3, sticky="ew", padx=6)

        def _them():
            if not e_ten.get().strip():
                return
            self.cast_memory.them_hoac_cap_nhat(
                ten=e_ten.get().strip(),
                vai_tro=e_vai.get().strip(),
                ngoai_hinh=e_ngoai.get().strip(),
                xung_ho=e_xung.get().strip(),
            )
            _lam_moi()
            self.ghi_log(f"🎭 Đã lưu nhân vật '{e_ten.get().strip()}' vào Hồ sơ bộ truyện.")

        tk.Button(win, text="➕ Lưu Nhân Vật Vào Bộ Nhớ Truyện", bg="#059669", fg="#fff", relief="flat", padx=14, pady=6, command=_them).pack(pady=10)

    def _nap_danh_sach_giong_elevenlabs(self):
        el_key = self.ent_elevenlabs_key.get().strip()
        if not el_key:
            messagebox.showwarning("Chưa nhập ElevenLabs Key", "Hãy dán khoá ElevenLabs API Key (xi-api-key) vào ô trước khi nạp giọng!")
            return
        self.cau_hinh["elevenlabs_api_key"] = el_key
        luu_cau_hinh_studio(self.cau_hinh)

        def _worker():
            self.ghi_log("🔄 Đang kết nối ElevenLabs API để tải danh sách giọng đọc trong tài khoản của bạn...")
            try:
                ds_v = lay_danh_sach_giong_elevenlabs(el_key)
                ds_hien_thi = [f"{k} — {v['ten']}" for k, v in DANH_SACH_GIONG_DOC.items()]
                self.cmb_giong["values"] = ds_hien_thi
                if ds_v:
                    ma_dau = ds_v[0]["ma_giong"]
                    for idx_v, item_str in enumerate(ds_hien_thi):
                        if item_str.startswith(ma_dau + " —"):
                            self.cmb_giong.current(idx_v)
                            break
                self.ghi_log(f"✅ Đã nạp thành công {len(ds_v)} giọng đọc từ tài khoản ElevenLabs của bạn! Hãy chọn trong danh sách Kho Giọng Đọc AI.")
            except Exception as exc:
                self.ghi_log(f"❌ Không nạp được giọng ElevenLabs: {exc}")

        threading.Thread(target=_worker, daemon=True).start()

    def _tao_kich_ban_storyboard(self):
        folder_str = self.ent_folder.get().strip()
        if not folder_str or not Path(folder_str).exists():
            messagebox.showwarning("Chưa chọn nguồn Chapter", "Hãy chọn thư mục hoặc file ZIP chứa ảnh Chapter trước!")
            return
        try:
            self.cau_hinh["token"] = self.ent_token.get().strip()
            self.cau_hinh["elevenlabs_api_key"] = self.ent_elevenlabs_key.get().strip()
            self.cau_hinh["elevenlabs_voice_id"] = self.ent_elevenlabs_vid.get().strip()
            luu_cau_hinh_studio(self.cau_hinh)

            p_folder = Path(folder_str)
            self.ghi_log("🧠 Đang quét thoại từng trang, nhận diện nhân vật & gọi DeepSeek biên kịch toàn Chapter...")
            self.panels_bytes, self.ocr_per_panel = nap_danh_sach_anh_va_thoai_tu_thu_muc(p_folder)
            tu_dong_quet_ho_so_nhan_vat_tu_thoai(self.ocr_per_panel, self.cast_memory)
            pc_key = self.cmb_phong_cach.get().split(" — ", 1)[0].strip()
            self.kich_ban_hien_tai = sinh_kich_ban_review_chuong(
                self.panels_bytes,
                self.ocr_per_panel,
                cast_memory=self.cast_memory,
                phong_cach=pc_key,
                ten_truyen=self.ent_ten_truyen.get().strip(),
                ten_chap=p_folder.stem if p_folder.is_file() else p_folder.name,
                thu_ket_noi_vision_cuc_bo=True,
            )
            self.lst_scenes.delete(0, "end")
            for sc in self.kich_ban_hien_tai.get("scenes") or []:
                cx_tag = sc.get("cam_xuc") or "kich_tinh"
                self.lst_scenes.insert(
                    "end",
                    f"Cảnh #{sc['scene_index']:02d} [{cx_tag}] · 🎭 {sc['nhan_vat']}: {sc['loi_thuyet_minh'][:72]}...",
                )
            self.ghi_log(
                f"✨ Đã sinh xong Kịch bản Storyboard bằng DeepSeek ({self.kich_ban_hien_tai['so_khung_tranh']} khung tranh, "
                f"đã gắn ngữ điệu cảm xúc từng cảnh). Bấm vào từng cảnh để duyệt/sửa hoặc nghe thử!"
            )
        except Exception as exc:
            messagebox.showerror("Lỗi tạo kịch bản", str(exc))

    def _khi_chon_phan_canh(self, _event=None):
        sel = self.lst_scenes.curselection()
        if not sel or not self.kich_ban_hien_tai:
            return
        idx = sel[0]
        sc = self.kich_ban_hien_tai["scenes"][idx]
        self.ent_nv_canh.delete(0, "end")
        self.ent_nv_canh.insert(0, sc.get("nhan_vat") or "")
        cx_val = sc.get("cam_xuc") or "kich_tinh"
        if cx_val in self.cmb_cam_xuc_canh["values"]:
            self.cmb_cam_xuc_canh.set(cx_val)
        self.txt_loi_binh.delete("1.0", "end")
        self.txt_loi_binh.insert("1.0", sc.get("loi_thuyet_minh") or "")

    def _luu_sua_phan_canh(self):
        sel = self.lst_scenes.curselection()
        if not sel or not self.kich_ban_hien_tai:
            return
        idx = sel[0]
        sc = self.kich_ban_hien_tai["scenes"][idx]
        sc["nhan_vat"] = self.ent_nv_canh.get().strip() or sc["nhan_vat"]
        sc["cam_xuc"] = self.cmb_cam_xuc_canh.get().strip() or sc.get("cam_xuc") or "kich_tinh"
        sc["loi_thuyet_minh"] = self.txt_loi_binh.get("1.0", "end").strip()
        cx_tag = sc["cam_xuc"]
        self.lst_scenes.delete(idx)
        self.lst_scenes.insert(
            idx,
            f"Cảnh #{sc['scene_index']:02d} [{cx_tag}] · 🎭 {sc['nhan_vat']}: {sc['loi_thuyet_minh'][:72]}...",
        )
        self.ghi_log(f"💾 Đã cập nhật lời thuyết minh & ngữ điệu [{cx_tag}] cho Cảnh #{sc['scene_index']:02d}.")

    def _xem_truoc_khung_hinh_canh(self):
        sel = self.lst_scenes.curselection()
        if not sel or not self.kich_ban_hien_tai or not self.panels_bytes:
            messagebox.showinfo("Chọn phân cảnh", "Hãy bấm chọn 1 phân cảnh trong danh sách Storyboard để xem trước!")
            return
        idx = sel[0]
        sc = self.kich_ban_hien_tai["scenes"][idx]
        dinh_dang_key = self.cmb_dinh_dang.get().split(" — ", 1)[0].strip()
        kich_thuoc = (DINH_DANG_VIDEO.get(dinh_dang_key) or DINH_DANG_VIDEO["tiktok_9_16"])["kich_thuoc"]
        frame_b = ve_khung_hinh_pan_zoom_va_phu_de(
            self.panels_bytes[min(idx, len(self.panels_bytes) - 1)],
            loi_thuyet_minh=sc.get("loi_thuyet_minh") or "",
            nhan_vat=sc.get("nhan_vat") or "",
            kich_thuoc_video=kich_thuoc,
            tien_do_canh=0.5,
            kieu_chuyen_dong=sc.get("hieu_ung_camera") or "pan_down",
        )
        tmp_preview = Path(tempfile.gettempdir()) / f"preview_scene_{idx + 1:02d}.jpg"
        tmp_preview.write_bytes(frame_b)
        if os.name == "nt":
            os.startfile(str(tmp_preview))
        self.ghi_log(f"👁️ Đã mở ảnh xem trước Cảnh #{idx + 1:02d} ({kich_thuoc[0]}x{kich_thuoc[1]}): {tmp_preview}")

    def _chon_file_giong_mau(self):
        f = filedialog.askopenfilename(
            title="Chọn file âm thanh mẫu 5-8 giây (.wav / .mp3) để AI nhái giọng",
            filetypes=[("File âm thanh mẫu", "*.wav *.mp3")],
        )
        if not f:
            return
        self.ent_ref_audio.delete(0, "end")
        self.ent_ref_audio.insert(0, f)
        self.cmb_giong.current(1)  # Tự động chuyển sang chế độ clone_giong_mau_5s
        self.ghi_log(f"🧬 Đã nạp mẫu giọng Clone (Zero-Shot): {f}")

    def _lay_toc_do_doc(self) -> float:
        raw = self.cmb_toc_do.get().split("x", 1)[0].strip()
        try:
            return float(raw)
        except Exception:
            return 1.15

    def _nghe_thu_giong_doc(self):
        giong_key = self.cmb_giong.get().split(" — ", 1)[0].strip()
        toc_do_val = self._lay_toc_do_doc()
        el_key = self.ent_elevenlabs_key.get().strip()
        el_vid = self.ent_elevenlabs_vid.get().strip()
        cam_xuc_val = self.cmb_cam_xuc_canh.get().strip() if hasattr(self, "cmb_cam_xuc_canh") else "kich_tinh"
        cau_thu = self.txt_loi_binh.get("1.0", "end").strip()
        if not cau_thu:
            cau_thu = (
                "Chào mừng các bạn đến với kênh Review Truyện Tranh! "
                "Tưởng chừng đã rơi vào tuyệt cảnh... nhưng khoảnh khắc tiếp theo của thanh niên lại khiến tất cả phải chấn động!"
            )

        def _worker():
            self.ghi_log(f"🔊 Đang tạo mẫu giọng thử '{giong_key}' (Ngữ điệu: {cam_xuc_val} · {toc_do_val:.2f}x)...")
            try:
                tmp_dir = Path(tempfile.gettempdir()) / "manga_video_voice_preview"
                kq = tong_hop_giong_doc_phan_canh(
                    cau_thu,
                    tmp_dir,
                    scene_index=999,
                    ma_giong=giong_key,
                    toc_do=toc_do_val,
                    cam_xuc=cam_xuc_val,
                    vai_tro_nhan_vat=self.ent_nv_canh.get().strip(),
                    ten_nhan_vat=self.ent_nv_canh.get().strip(),
                    file_giong_mau_clone=self.ent_ref_audio.get().strip() or None,
                    elevenlabs_api_key=el_key or None,
                    elevenlabs_voice_id=el_vid or None,
                )
                audio_p = kq["audio_path"]
                if os.name == "nt" and os.path.isfile(audio_p):
                    os.startfile(audio_p)
                self.ghi_log(f"✅ Đã phát mẫu giọng thử ({kq['thoi_luong_giay']}s): {audio_p}")
            except Exception as exc:
                self.ghi_log(f"⚠️ Chưa phát được mẫu giọng thử: {exc}")

        threading.Thread(target=_worker, daemon=True).start()

    def _dong_bo_goi_giong_doc_va_mp4(self):
        giong_key = self.cmb_giong.get().split(" — ", 1)[0].strip()
        can_onnx = giong_key == "clone_giong_mau_5s" or bool(self.ent_ref_audio.get().strip())

        def _worker():
            self.ghi_log("⚙️ Đang kiểm tra & tự động cài đặt Kho 15 Giọng Đọc AI + Nhân Render MP4...")
            ok, msg = cai_dat_tu_dong_goi_giong_doc_va_mp4(cai_them_onnx_pro=can_onnx)
            tt = kiem_tra_ha_tang_giong_doc_va_video()
            self.ghi_log(
                f"{'✅' if ok else '⚠️'} {msg}\n"
                f"   • Kho 15 Giọng Đọc Bắc/Trung/Nam & Đa Nhân Vật: {'Sẵn sàng' if tt['neural_voice_ready'] else 'Dự phòng Offline'}\n"
                f"   • Nhân Render MP4 (H.264 + AAC): {'Sẵn sàng' if tt['ffmpeg_ready'] else 'Dự phòng Container'}"
            )

        threading.Thread(target=_worker, daemon=True).start()

    def _xuat_video_mp4(self):
        if self.dang_xu_ly:
            return
        if not self.kich_ban_hien_tai or not self.panels_bytes:
            self._tao_kich_ban_storyboard()
            if not self.kich_ban_hien_tai:
                return

        src_p = Path(self.ent_folder.get().strip())
        out_folder = src_p.parent if src_p.is_file() else src_p
        ten_goc = src_p.stem if src_p.is_file() else src_p.name
        dinh_dang_key = self.cmb_dinh_dang.get().split(" — ", 1)[0].strip()
        giong_key = self.cmb_giong.get().split(" — ", 1)[0].strip()
        nhac_nen_key = self.cmb_nhac_nen.get().split(" — ", 1)[0].strip() if hasattr(self, "cmb_nhac_nen") else "tu_dong_theo_phong_cach"
        goi_key = self.cmb_goi_luot.get().split(" — ", 1)[0].strip()
        toc_do_val = self._lay_toc_do_doc()
        token_val = self.ent_token.get().strip()
        el_key_val = self.ent_elevenlabs_key.get().strip()
        el_vid_val = self.ent_elevenlabs_vid.get().strip()

        self.cau_hinh.update(
            {
                "token": token_val,
                "dinh_dang": dinh_dang_key,
                "ma_giong": giong_key,
                "ma_nhac_nen": nhac_nen_key,
                "goi_luot": goi_key,
                "toc_do_doc": toc_do_val,
                "elevenlabs_api_key": el_key_val,
                "elevenlabs_voice_id": el_vid_val,
            }
        )
        luu_cau_hinh_studio(self.cau_hinh)

        out_mp4 = out_folder / f"{ten_goc}_Video_Review_{dinh_dang_key}.mp4"
        self.dang_xu_ly = True

        def _worker():
            try:
                if token_val:
                    self.ghi_log("🔐 Đang kiểm tra hạn mức & cấp vé thực thi tạo Video trên Ví Cloud...")
                    kq_ve = xac_thuc_va_tru_luot_video_cloud(
                        self.cau_hinh.get("server_url") or "https://translation-api.vibe1.tinhgon.xyz",
                        token_val,
                        ma_goi=goi_key,
                        ma_dinh_danh_video=f"{ten_goc}:{dinh_dang_key}",
                    )
                    self.ghi_log(
                        f"✅ Đã xác thực gói '{goi_key}' (-{kq_ve['so_luot_da_tru']} lượt · Số dư còn {kq_ve['con_lai_sau_tru']} lượt)."
                    )
                self.ghi_log(f"🎙️ Đang tổng hợp giọng đọc ({toc_do_val:.2f}x), trộn nhạc nền ({nhac_nen_key}) & dựng MP4...")
                kq = xuat_video_review_mp4(
                    self.panels_bytes,
                    self.kich_ban_hien_tai,
                    out_mp4,
                    ma_dinh_dang=dinh_dang_key,
                    ma_giong=giong_key,
                    ma_nhac_nen=nhac_nen_key,
                    toc_do_doc=toc_do_val,
                    file_giong_mau_clone=self.ent_ref_audio.get().strip() or None,
                    elevenlabs_api_key=el_key_val or None,
                    elevenlabs_voice_id=el_vid_val or None,
                )
                self.ghi_log(
                    f"🎉 HOÀN TẤT! Đã xuất Video Review ({kq['tong_thoi_luong_giay']}s):\n"
                    f"   • Video MP4: {kq['video_path']}\n"
                    f"   • Audio Master WAV: {kq['audio_master_path']}\n"
                    f"   • Phụ đề SRT: {kq['srt_path']}"
                )
            except Exception as exc:
                self.ghi_log(f"❌ Lỗi xuất Video: {exc}")
            finally:
                self.dang_xu_ly = False

        threading.Thread(target=_worker, daemon=True).start()


if __name__ == "__main__":
    app = AppVideoReviewStudio()
    try:
        app.deiconify()
        app.lift()
        app.attributes("-topmost", True)
        app.after(400, lambda: app.attributes("-topmost", False))
        app.focus_force()
    except Exception:
        pass
    app.mainloop()
