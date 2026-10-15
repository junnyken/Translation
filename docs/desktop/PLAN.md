# PLAN — App Windows chạy offline của Translation

Ngày lập: 2026-10-15. Quyết định nền: `docs/desktop/DECISIONS.md`. Skill: `~/.claude/skills/desktop-app`.
Tổng công ước lượng: **~9–11 tuần một DEV** + thời gian người thật (bấm thử Windows, máy GPU).
Phase 0 là cổng: hỏng thì đổi D10/D11 trước khi đầu tư tiếp.

## Ràng buộc môi trường

- Workspace Linux, RAM container 10 GB, đĩa dùng chung ~3,6 GB trống, không Windows, không GPU.
  Workspace từng mất gói giữa hai phiên: đầu mỗi lượt chạy `command -v llvm-rc clang lld makensis cargo node`.
- **Mọi thứ chạy trên Windows là [CHƯA KIỂM] tới khi người thật thử.** Cách tự động duy nhất chạm Windows là
  GitHub Actions `windows-latest` (4 vCPU, 16 GB RAM, ~14 GB đĩa trống [SUY LUẬN — kiểm ở Phase 0]).
- PyInstaller không build chéo ⇒ sidecar và bộ cài build trên CI Windows; workspace không tải artifact về.

## Kiểm được ở đâu

| Trên Linux (workspace) | Chỉ trên CI Windows | Phải người thật trên Windows |
|---|---|---|
| pytest backend (Postgres docker), test chế độ máy bàn (token, tắt hạn mức, model manager giả, chọn provider giả) | Đóng băng PyInstaller; sidecar thật dịch 1 trang; kích thước/thời gian | Cài bộ cài, SmartScreen/AV, tài khoản admin vs thường, WebGPU, kéo-thả, tải tệp, GPU thật, gỡ cài |
| vitest, `vite build` | `npm run tauri build` (NSIS), `.sig` | Cập nhật thật 0.N→0.N+1, tắt máy đột ngột |
| `cargo test` module Rust thuần; `cargo check --target x86_64-pc-windows-msvc` | `cargo build` thật | Job Object kill cả cây khi đóng app |
| `python -m app.desktop serve` chạy thật với Postgres docker + broker filesystem, dịch 1 trang | | |

---

## Phase 0 — SPIKE: đóng băng backend + 1 trang end-to-end trên Windows CPU (1–2 tuần)

**Mục tiêu:** đo ba rủi ro lớn nhất trước khi viết Rust/UI: (1) PyInstaller đóng băng được backend có
paddle/torch/manga-ocr; (2) Postgres nhúng + Celery solo + broker filesystem chạy trên Windows;
(3) kích thước và thời gian thật.

**Việc:**
1. `backend/app/desktop/__init__.py`, `main.py` tối thiểu: `serve --port 0 --data-dir`, `worker --data-dir`,
   `initdb --data-dir` (giải nén Postgres nhúng, `initdb`, `pg_ctl start`, `alembic upgrade head`).
   Đặt env thay vì sửa `config.py` nhiều.
2. `backend/desktop.spec` (onedir) + `backend/scripts/build_sidecar.py` (sinh `MANIFEST.sha256`, in kích thước).
3. `.github/workflows/desktop-spike.yml` trên `windows-latest`: cài pip (torch CPU) → PyInstaller → `initdb`
   → `serve` + `worker` → tạo project + upload 1 trang EN (Pepper&Carrot trong `test_fixtures/`) → poll tới
   `typeset_done` → kiểm ≥1 vùng, `clean-image` 200, `typeset-preview` 200 → ghi `timing.json`, `size.json`
   → upload artifact. Hỏng ở đâu đỏ ở đó, không `except` nuốt.
4. Trên Linux: pytest hiện có vẫn xanh; chạy thật `app.desktop` với Postgres docker + broker filesystem.
5. Người thật: tải artifact zip, chạy tay trên 1 máy Windows tài khoản thường + 1 máy admin; ghi
   `docs/desktop/SPIKE-0.md`.

**Xong khi (đo được):**
- CI xanh: 1 trang EN chạy trọn detect→ocr→inpaint→translate(google_fast)→typeset trên runner ≤ 15 phút.
- `size.json`: onedir ≤ 3,0 GB, zip ≤ 1,5 GB.
- Postgres nhúng khởi động được dưới cả tài khoản thường lẫn admin (người thật).
- Có bảng "hidden import đã thêm" thật.

**Rủi ro:** PyInstaller + paddlepaddle (DLL, import động). Nếu 3 ngày không đóng băng nổi ⇒ đề xuất đổi OCR
en/zh trên desktop sang `rapidocr-onnxruntime` (ONNX của PP-OCR, ~30 MB), đo lại chất lượng bằng
`backend/scripts/ocr_benchmark_run.py` trước khi chốt (Q3). Đĩa runner; Celery solo trên Windows [CHƯA KIỂM].

**Công:** 5–8 ngày DEV + 0,5 ngày người thật.

## Phase 1 — Backend "chế độ máy bàn" (1,5–2 tuần)

- `app/core/config.py`: `desktop_mode`, `desktop_token` (không log), `ctd_device`/`inpaint_device` nhận
  `auto|cpu|cuda|dml`; tệp trạng thái worker theo thư mục dữ liệu.
- Dependency máy bàn: Bearer == token ⇒ tài khoản cục bộ; gắn cho `v1_router` và `router_khach`;
  `/healthz` thêm `runtime`, `desktop`.
- Tắt cổng hạn mức khi `desktop_mode` (thêm trường, không đổi trường cũ).
- `app/workers/bo_nho.py`: RSS Windows qua `ctypes`.
- `ctd.py`, `lama.py`: chọn provider theo `auto` + log provider thực dùng.
- `app/desktop/model_manager.py` + `models.lock.json` + `/api/v1/desktop/models`; `app/desktop/gpu.py`.
- `app/desktop/main.py` đầy đủ: handshake stdout, log UTF-8 xoay, Postgres nhúng, dừng sạch.
- Workflow spike thành `sidecar.yml` (cache pip + model).

**Xong khi:** pytest cũ xanh; ≥ 25 test mới có đối chứng âm (thiếu token ⇒ 401 cả route khách; sha sai ⇒
từ chối, không để tệp lại; provider không có ⇒ lùi cpu + log); CI Windows vẫn dịch 1 trang có token.
**Công:** 8–10 ngày.

## Phase 2 — Vỏ Tauri (1,5 tuần)

`desktop/` theo skill: `backend.rs` (spawn `pg_ctl`, `serve`, `worker` trong Job Object; handshake; poll
`/healthz`; bật lại worker), `pins.rs` (kiểm `MANIFEST.sha256`), `secrets.rs` (Credential Manager),
`commands.rs` (`get_version`, `backend_status`, `gpu_info`, `save_export`, `open_data_dir`, `set_secret`,
`restart_backend`, `download_runtime_gpu`, `update_check`, `update_install`), `build.rs` theo template.
Viết `docs/desktop/CONTRACT.md` trước.

**Xong khi:** `cargo test` xanh trên Linux; CI ra `Translation_<v>_x64-setup.exe`; người thật: cài không UAC,
app sẵn sàng ≤ 60 s, đóng app không còn `postgres.exe`/sidecar trong Task Manager.
**Công:** 7–8 ngày + 0,5 ngày người thật.

## Phase 3 — Frontend trong webview (1 tuần)

`api.js` nhận base + token bơm; bỏ Google Fonts; tắt kiểm bản mới; ẩn hạn mức; màn **Cài đặt máy bàn**
(dựng UI qua agy theo luật tổ chức); nút lưu tệp xuất gọi `save_export`; banner backend khởi động/đang bật lại.
**Xong khi:** vitest + `vite build` xanh; người thật dịch 1 chapter từ kéo-thả tới lưu CBZ. **Công:** 5 ngày.

## Phase 4 — Build & phát hành (1 tuần)

`.github/workflows/desktop-release.yml`: job `sidecar-cpu` (cổng chạy thật 1 trang) → job `app`
(`tauri build`, `.sig`, cổng kích thước < 1,8 GB) → job `publish` khi tag `v*` (`latest.json`, bộ cài,
gói model ngoại tuyến + sha256). Owner sinh khoá updater, đặt GitHub Secrets.
**Xong khi:** release `v0.1.0-noi-bo` có `.exe` + `.sig` + `latest.json`, chữ ký kiểm "verified".
**Công:** 5 ngày + owner đặt secret.

## Phase 5 — Gói GPU & model chỉ-GPU (1,5–2 tuần, CẦN máy NVIDIA thật)

Job `sidecar-gpu` (torch cu126 + `requirements-gpu.txt` + `rfdetr`); Rust tải/chọn sidecar GPU;
`app/services/detect/rf_detr.py` (cũng cấp lớp panel cho E82); bật SDXL; PaddleOCR-VL tuỳ chọn; bảng đo
trên máy GPU thật ⇒ chốt D14 theo số.
**Xong khi:** gói GPU cài qua Model Manager, `/healthz.runtime=cuda`; 1 trang SDXL ra ảnh;
`docs/desktop/BENCH-GPU.md`; máy không GPU chọn gói GPU ⇒ báo rõ, không chết.
**Công:** 8–10 ngày + 1 ngày người thật có GPU.

## Phase 6 — Click-through, chịu lỗi, hiệu năng (1 tuần + người thật)

Tài khoản thường/admin; AV công ty; máy không mạng; giết worker giữa chừng; tắt máy đột ngột; đĩa đầy;
8 GB RAM dịch chapter 24 trang không OOM; cập nhật 0.1→0.2 giữ dữ liệu; gỡ cài giữ/xoá đúng lựa chọn.
Mỗi lỗi ⇒ thêm test và xác nhận nó đỏ trước khi sửa.
**Công:** 5 ngày DEV + 2 ngày người thật (2 máy).

## Phase 7 — Phát hành nội bộ 0.1, vòng phản hồi

Owner đồng ý bản; đăng release; không nâng `latest.json` lên bản chưa thử Windows.

---

## Rủi ro & điều chưa biết

1. PyInstaller + paddle đóng băng được không, nặng bao nhiêu — biết sau Phase 0.
2. Postgres nhúng dưới admin, AV, tắt máy đột ngột [CHƯA KIỂM].
3. Celery solo + broker filesystem trên Windows [CHƯA KIỂM].
4. DirectML cho CTD/LaMa [CHƯA KIỂM].
5. Kích thước so với trần 2 GB của NSIS và GitHub [SUY LUẬN].
6. RF-DETR: chưa có số trên GPU; điều khoản Manga109 chỉ dùng nội bộ.
7. WebView2: WebGPU, CSP cổng động, tải blob, kéo-thả [CHƯA KIỂM].
8. `bo_nho.rss_mb()` trả None trên Windows cho tới khi vá ⇒ OOM máy 8 GB.
9. Máy công ty có thể thiếu WebView2 hoặc bị GPO chặn `%LOCALAPPDATA%\Programs`.
10. CI 30–60 phút/lượt; phút Windows tính ×2 với repo riêng tư.

## Việc cần người thật

- 2 máy Windows thử: laptop CPU-only 8 GB và máy NVIDIA ≥ 8 GB VRAM.
- Repo release công khai; sinh + sao lưu khoá updater 2 nơi; đặt GitHub Secrets.
- IT allowlist AV cho `Translation.exe`, `postgres.exe`, sidecar.
- BA duyệt wording màn Cài đặt máy bàn và hướng dẫn SmartScreen.

## Câu hỏi chủ dự án cần chốt

- **Q1 Phân phối:** GitHub Release công khai hay file share nội bộ? Gói GPU 3–4 GB vượt 2 GB/asset — chia phần hay để nội bộ?
- **Q2 Máy mục tiêu & ký mã:** RAM tối thiểu 8 hay 16 GB? Không mua chứng chỉ ký mã như VidGrab?
- **Q3 OCR EN/ZH:** nếu PaddleOCR không đóng băng nổi, chấp nhận RapidOCR (ONNX) cho bản desktop?
- **Q4 Dịch offline thật:** dựa vào Ollama/LM Studio người dùng tự cài, hay app tự kèm llama.cpp + model (+4–8 GB)?
- **Q5 Hạ tầng:** ai cấp máy Windows thử, phút GitHub Actions, repo release? Một người dùng/máy, không đồng bộ lên server — đúng không?
