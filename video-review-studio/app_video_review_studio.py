from __future__ import annotations

import json
import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Any

from core_tts_voice import DANH_SACH_GIONG_DOC
from core_video_renderer import (
    DINH_DANG_VIDEO,
    GOI_LUOT_VIDEO_REVIEW,
    xac_thuc_va_tru_luot_video_cloud,
    xuat_video_review_mp4,
)
from core_vision_character import (
    PHONG_CACH_KICH_BAN,
    CharacterCastMemory,
    sinh_kich_ban_review_chuong,
    tach_khung_tranh_thong_minh,
)


CAU_HINH_STUDIO_PATH = Path.home() / ".manga_video_review_studio_config.json"
CAU_HINH_APP_DICH_PATH = Path.home() / ".manga_translator_win_config.json"


def doc_cau_hinh_studio() -> dict[str, Any]:
    mac_dinh: dict[str, Any] = {
        "server_url": "https://translation-api.vibe1.tinhgon.xyz",
        "token": "",
        "phong_cach": "kich_tinh",
        "dinh_dang": "tiktok_9_16",
        "ma_giong": "nam_minh_kich_tinh",
        "goi_luot": "review_standard",
        "toc_do_doc": 1.15,
    }
    # Tự động kế thừa token từ App Dịch Truyện nếu người dùng đã đăng nhập trên cùng máy tính
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


def nap_danh_sach_anh_va_thoai_tu_thu_muc(folder_path: Path) -> tuple[list[bytes], list[list[str]]]:
    """
    Quét thư mục Chapter:
    - Nếu thư mục đã có sẵn dữ liệu vùng dịch (`_translation_ledger.json`), tự động trích xuất lời thoại đã dịch
      để AI biên kịch bám sát 100% nội dung!
    - Tự động cắt các trang Webtoon dài thành từng khung tranh (Panel) vừa vặn.
    """
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    files = sorted(
        [p for p in folder_path.iterdir() if p.is_file() and p.suffix.lower() in exts and not p.name.startswith("_")],
        key=lambda p: p.name.lower(),
    )
    if not files:
        raise ValueError(f"Không tìm thấy ảnh (.jpg/.png/.webp) trong thư mục: {folder_path}")

    thoai_theo_file: dict[str, list[str]] = {}
    ledger_file = folder_path / "_translation_ledger.json"
    if ledger_file.is_file():
        try:
            ledger_data = json.loads(ledger_file.read_text(encoding="utf-8"))
            for p in ledger_data.get("pages") or []:
                fname = str(p.get("output_name") or p.get("source") or "")
                ds_cau = [
                    str(r.get("ban_dich") or r.get("chu_goc") or "").strip()
                    for r in (p.get("regions") or [])
                    if isinstance(r, dict) and str(r.get("ban_dich") or r.get("chu_goc") or "").strip()
                ]
                if fname:
                    thoai_theo_file[Path(fname).name] = ds_cau
        except Exception:
            pass

    panels_out: list[bytes] = []
    ocr_per_panel: list[list[str]] = []
    for f in files:
        raw_b = f.read_bytes()
        sub_panels = tach_khung_tranh_thong_minh(raw_b)
        ds_thoai_trang = thoai_theo_file.get(f.name) or []
        for idx_p, pb in enumerate(sub_panels):
            panels_out.append(pb)
            if idx_p == 0 and ds_thoai_trang:
                ocr_per_panel.append(ds_thoai_trang)
            else:
                ocr_per_panel.append([])

    return panels_out, ocr_per_panel


class AppVideoReviewStudio(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🎬 Manga/Manhwa Video Review Studio v1.0 — Tự Động Biên Kịch, Nhận Diện Nhân Vật & Lồng Tiếng MP4")
        self.geometry("1180x760")
        self.configure(bg="#0b0f19")

        self.cau_hinh = doc_cau_hinh_studio()
        self.cast_memory = CharacterCastMemory(Path.home() / ".manga_video_character_bible.json")
        self.panels_bytes: list[bytes] = []
        self.ocr_per_panel: list[list[str]] = []
        self.kich_ban_hien_tai: dict[str, Any] = {}
        self.dang_xu_ly = False

        self._dung_giao_dien()

    def _dung_giao_dien(self):
        # Thanh Header trên cùng
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

        # Khung chia 2 cột: Cột trái (Cấu hình & Nhân vật) | Cột phải (Bảng Storyboard Duyệt Kịch Bản & Nhật ký)
        main_body = tk.Frame(self, bg="#0b0f19", padx=14, pady=10)
        main_body.pack(fill="both", expand=True)

        left_col = tk.Frame(main_body, bg="#111827", width=460, padx=14, pady=12)
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
        tk.Label(f_chap, text="Thư mục Chapter:", bg="#111827", fg="#cbd5e1", width=16, anchor="w").pack(side="left")
        self.ent_folder = tk.Entry(f_chap, bg="#1e293b", fg="#f8fafc", insertbackground="#fff")
        self.ent_folder.pack(side="left", fill="x", expand=True, padx=4)
        tk.Button(f_chap, text="📂 Chọn", bg="#2563eb", fg="#fff", relief="flat", padx=8, command=self._chon_thu_muc_chapter).pack(side="left")

        f_meta = tk.Frame(left_col, bg="#111827", pady=4)
        f_meta.pack(fill="x")
        tk.Label(f_meta, text="Tên bộ truyện:", bg="#111827", fg="#cbd5e1", width=16, anchor="w").pack(side="left")
        self.ent_ten_truyen = tk.Entry(f_meta, bg="#1e293b", fg="#f8fafc", insertbackground="#fff")
        self.ent_ten_truyen.insert(0, "Siêu Phẩm Truyện Tranh")
        self.ent_ten_truyen.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # --- BƯỚC 2: HỒ SƠ NHÂN VẬT (CHỐNG NHẦM NGƯỜI NÓI) ---
        tk.Label(left_col, text="02 · HỒ SƠ NHÂN VẬT (ĐỊNH DANH NGƯỜI NÓI)", bg="#111827", fg="#34d399", font=("Segoe UI", 9, "bold"), pady=6).pack(anchor="w")
        tk.Button(
            left_col,
            text="🎭 Mở Bảng Hồ Sơ Nhân Vật (Tên + Ngoại hình + Xưng hô)",
            bg="#059669",
            fg="#ffffff",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            pady=6,
            command=self._mo_cua_so_ho_so_nhan_vat,
        ).pack(fill="x", pady=(0, 8))

        # --- BƯỚC 3: PHONG CÁCH KỊCH BẢN & GIỌNG ĐỌC ---
        tk.Label(left_col, text="03 · PHONG CÁCH REVIEW & LÕI GIỌNG ĐỌC AI", bg="#111827", fg="#fbbf24", font=("Segoe UI", 9, "bold"), pady=4).pack(anchor="w")

        tk.Label(left_col, text="Phong cách biên kịch thuyết minh:", bg="#111827", fg="#cbd5e1").pack(anchor="w")
        self.cmb_phong_cach = ttk.Combobox(
            left_col,
            values=[f"{k} — {v['ten']}" for k, v in PHONG_CACH_KICH_BAN.items()],
            state="readonly",
        )
        self.cmb_phong_cach.current(0)
        self.cmb_phong_cach.pack(fill="x", pady=(2, 6))

        tk.Label(left_col, text="Khung hình Video xuất bản:", bg="#111827", fg="#cbd5e1").pack(anchor="w")
        self.cmb_dinh_dang = ttk.Combobox(
            left_col,
            values=[f"{k} — {v['ten']}" for k, v in DINH_DANG_VIDEO.items()],
            state="readonly",
        )
        self.cmb_dinh_dang.current(0)
        self.cmb_dinh_dang.pack(fill="x", pady=(2, 6))

        tk.Label(left_col, text="Giọng đọc thuyết minh AI:", bg="#111827", fg="#cbd5e1").pack(anchor="w")
        self.cmb_giong = ttk.Combobox(
            left_col,
            values=[f"{k} — {v['ten']}" for k, v in DANH_SACH_GIONG_DOC.items()],
            state="readonly",
        )
        self.cmb_giong.current(0)
        self.cmb_giong.pack(fill="x", pady=(2, 6))

        tk.Label(left_col, text="Gói xử lý Video (Tính vào Ví lượt tài khoản):", bg="#111827", fg="#cbd5e1").pack(anchor="w")
        self.cmb_goi_luot = ttk.Combobox(
            left_col,
            values=[f"{k} — {v['ten']}" for k, v in GOI_LUOT_VIDEO_REVIEW.items()],
            state="readonly",
        )
        self.cmb_goi_luot.current(0)
        self.cmb_goi_luot.pack(fill="x", pady=(2, 10))

        # Hai nút hành động chính
        tk.Button(
            left_col,
            text="✨ BƯỚC 1: TẠO KỊCH BẢN STORYBOARD (DUYỆT TRƯỚC)",
            bg="#7c3aed",
            fg="#ffffff",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            pady=8,
            command=self._tao_kich_ban_storyboard,
        ).pack(fill="x", pady=4)

        tk.Button(
            left_col,
            text="🎬 BƯỚC 2: LỒNG TIẾNG & XUẤT VIDEO MP4",
            bg="#ea580c",
            fg="#ffffff",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            pady=10,
            command=self._xuat_video_mp4,
        ).pack(fill="x", pady=4)

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

        self.lst_scenes = tk.Listbox(sb_frame, height=12, bg="#0f172a", fg="#f8fafc", selectbackground="#2563eb", font=("Consolas", 10))
        self.lst_scenes.pack(fill="x", pady=(0, 6))
        self.lst_scenes.bind("<<ListboxSelect>>", self._khi_chon_phan_canh)

        f_edit = tk.Frame(sb_frame, bg="#111827")
        f_edit.pack(fill="x")
        tk.Label(f_edit, text="Nhân vật cảnh này:", bg="#111827", fg="#fbbf24").pack(side="left")
        self.ent_nv_canh = tk.Entry(f_edit, width=22, bg="#1e293b", fg="#fbbf24", insertbackground="#fff")
        self.ent_nv_canh.pack(side="left", padx=6)
        tk.Button(f_edit, text="💾 Lưu sửa cảnh này", bg="#059669", fg="#fff", relief="flat", padx=10, command=self._luu_sua_phan_canh).pack(side="left")

        self.txt_loi_binh = scrolledtext.ScrolledText(sb_frame, height=5, bg="#1e293b", fg="#fde047", insertbackground="#fff", font=("Segoe UI", 10))
        self.txt_loi_binh.pack(fill="x", pady=6)

        log_frame = tk.LabelFrame(right_col, text=" 📟 NHẬT KÝ XỬ LÝ VIDEO STUDIO ", bg="#111827", fg="#94a3b8", font=("Segoe UI", 9, "bold"), padx=10, pady=6)
        log_frame.pack(fill="x", pady=(8, 0))
        self.txt_log = scrolledtext.ScrolledText(log_frame, height=8, bg="#090d16", fg="#a7f3d0", font=("Consolas", 9))
        self.txt_log.pack(fill="x")
        self.ghi_log("✅ Đã khởi động Manga/Manhwa Video Review Studio độc lập (An toàn 100%, tách biệt với luồng Dịch Truyện).")

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

    def _tao_kich_ban_storyboard(self):
        folder_str = self.ent_folder.get().strip()
        if not folder_str or not Path(folder_str).is_dir():
            messagebox.showwarning("Chưa chọn thư mục", "Hãy chọn thư mục chứa ảnh Chapter trước!")
            return
        try:
            p_folder = Path(folder_str)
            self.panels_bytes, self.ocr_per_panel = nap_danh_sach_anh_va_thoai_tu_thu_muc(p_folder)
            pc_key = self.cmb_phong_cach.get().split(" — ", 1)[0].strip()
            self.kich_ban_hien_tai = sinh_kich_ban_review_chuong(
                self.panels_bytes,
                self.ocr_per_panel,
                cast_memory=self.cast_memory,
                phong_cach=pc_key,
                ten_truyen=self.ent_ten_truyen.get().strip(),
                ten_chap=p_folder.name,
            )
            self.lst_scenes.delete(0, "end")
            for sc in self.kich_ban_hien_tai.get("scenes") or []:
                loai = "[Hành động]" if sc.get("la_canh_hanh_dong") else "[Có thoại]"
                self.lst_scenes.insert(
                    "end",
                    f"Cảnh #{sc['scene_index']:02d} {loai} · 🎭 {sc['nhan_vat']}: {sc['loi_thuyet_minh'][:75]}...",
                )
            self.ghi_log(
                f"✨ Đã sinh xong Kịch bản Storyboard ({self.kich_ban_hien_tai['so_khung_tranh']} khung tranh, "
                f"{self.kich_ban_hien_tai['so_luoi_storyboard_2x2']} lưới 2x2). Bạn có thể bấm vào từng cảnh để duyệt/sửa nhanh!"
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
        self.txt_loi_binh.delete("1.0", "end")
        self.txt_loi_binh.insert("1.0", sc.get("loi_thuyet_minh") or "")

    def _luu_sua_phan_canh(self):
        sel = self.lst_scenes.curselection()
        if not sel or not self.kich_ban_hien_tai:
            return
        idx = sel[0]
        sc = self.kich_ban_hien_tai["scenes"][idx]
        sc["nhan_vat"] = self.ent_nv_canh.get().strip() or sc["nhan_vat"]
        sc["loi_thuyet_minh"] = self.txt_loi_binh.get("1.0", "end").strip()
        loai = "[Hành động]" if sc.get("la_canh_hanh_dong") else "[Có thoại]"
        self.lst_scenes.delete(idx)
        self.lst_scenes.insert(
            idx,
            f"Cảnh #{sc['scene_index']:02d} {loai} · 🎭 {sc['nhan_vat']}: {sc['loi_thuyet_minh'][:75]}...",
        )
        self.ghi_log(f"💾 Đã cập nhật lời thuyết minh Cảnh #{sc['scene_index']:02d}.")

    def _xuat_video_mp4(self):
        if self.dang_xu_ly:
            return
        if not self.kich_ban_hien_tai or not self.panels_bytes:
            self._tao_kich_ban_storyboard()
            if not self.kich_ban_hien_tai:
                return

        folder_p = Path(self.ent_folder.get().strip())
        dinh_dang_key = self.cmb_dinh_dang.get().split(" — ", 1)[0].strip()
        giong_key = self.cmb_giong.get().split(" — ", 1)[0].strip()
        goi_key = self.cmb_goi_luot.get().split(" — ", 1)[0].strip()
        token_val = self.ent_token.get().strip()

        self.cau_hinh.update(
            {
                "token": token_val,
                "dinh_dang": dinh_dang_key,
                "ma_giong": giong_key,
                "goi_luot": goi_key,
            }
        )
        luu_cau_hinh_studio(self.cau_hinh)

        out_mp4 = folder_p / f"{folder_p.name}_Video_Review_{dinh_dang_key}.mp4"
        self.dang_xu_ly = True

        def _worker():
            try:
                if token_val:
                    self.ghi_log("🔐 Đang kiểm tra hạn mức & cấp vé thực thi tạo Video trên Ví Cloud...")
                    kq_ve = xac_thuc_va_tru_luot_video_cloud(
                        self.cau_hinh.get("server_url") or "https://translation-api.vibe1.tinhgon.xyz",
                        token_val,
                        ma_goi=goi_key,
                        ma_dinh_danh_video=f"{folder_p.name}:{dinh_dang_key}",
                    )
                    self.ghi_log(
                        f"✅ Đã xác thực gói '{goi_key}' (-{kq_ve['so_luot_da_tru']} lượt · Số dư còn {kq_ve['con_lai_sau_tru']} lượt)."
                    )
                self.ghi_log("🎙️ Đang tổng hợp giọng đọc thuyết minh & dựng chuyển động Pan/Zoom MP4...")
                kq = xuat_video_review_mp4(
                    self.panels_bytes,
                    self.kich_ban_hien_tai,
                    out_mp4,
                    ma_dinh_dang=dinh_dang_key,
                    ma_giong=giong_key,
                    toc_do_doc=1.15,
                )
                self.ghi_log(
                    f"🎉 HOÀN TẤT! Đã xuất Video Review ({kq['tong_thoi_luong_giay']}s):\n"
                    f"   • Video MP4: {kq['video_path']}\n"
                    f"   • Phụ đề SRT: {kq['srt_path']}"
                )
            except Exception as exc:
                self.ghi_log(f"❌ Lỗi xuất Video: {exc}")
            finally:
                self.dang_xu_ly = False

        threading.Thread(target=_worker, daemon=True).start()


if __name__ == "__main__":
    app = AppVideoReviewStudio()
    app.mainloop()
