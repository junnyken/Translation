# DECISIONS — App Windows chạy offline của Translation

Ngày lập: 2026-10-15 · Trạng thái: ĐỀ XUẤT, chờ chủ dự án chốt các câu hỏi ở cuối `PLAN.md`.
Nhãn: không nhãn = đọc từ mã/đã chạy · [CHƯA KIỂM] = chưa ai chạy · [SUY LUẬN] = suy từ tài liệu.
Mọi thứ "chạy trên Windows" là [CHƯA KIỂM] cho tới khi người thật thử — workspace dev là Linux, không GPU.

Đã chốt với chủ dự án (15-10-2026): app đầy đủ chạy offline; phần cứng lẫn lộn ⇒ **tự dò GPU NVIDIA,
lùi CPU**; hai chế độ: CPU = bộ model nhẹ ONNX, GPU = thêm RF-DETR, PaddleOCR-VL, SDXL.

## 1. Bảng quyết định chuẩn của skill `desktop-app` (D1–D9)

| # | Quyết định | Lựa chọn | Lý do |
|---|---|---|---|
| D1 | Tauri 2 hay Electron | **Tauri 2** | Tiền lệ VidGrab + skill; WebView2 là Chromium nên canvas E76 (WebGPU, lùi 2D) chạy được [CHƯA KIỂM WebGPU trong WebView2]. Phần Rust nhỏ: spawn tiến trình, Job Object, lưu khoá, dialog lưu tệp, updater. |
| D2 | Đăng nhập | **Không có đăng nhập.** Một tài khoản cục bộ do sidecar tự tạo lần đầu; xác thực bằng token phiên cục bộ (D15). | App offline, một người dùng. Giữ nguyên mã slice B; thêm nhánh "chế độ máy bàn". |
| D3 | Hạn mức / chống lách | **Không.** Chế độ máy bàn tắt cổng hạn mức E49, trần IP, lịch dọn tệp. | Máy của người dùng, tài nguyên của họ. |
| D4 | Sidecar | **Có, và là thứ nặng nhất:** backend Python đóng băng PyInstaller **onedir** (D10) + Postgres nhúng (D11) + model (D12). Pin sha256 theo manifest tự sinh lúc build. | Không có công cụ exe đơn của bên thứ ba; phải tự build. |
| D5 | Tự cập nhật | **Bật từ bản đầu**. Nguồn: `latest.json` tĩnh trên GitHub Release. | Bản chưa có updater không tự lên được. Bộ cài lớn ⇒ cập nhật = tải lại ~1–1,5 GB; ghi rõ trên UI. |
| D6 | Ký mã Windows | **Không mua** (như VidGrab 09-10-2026). Dùng nội bộ ⇒ "More info → Run anyway" + nhờ IT allowlist. | Owner xác nhận ở Q2. |
| D7 | Tên miền được gọi | Webview: chỉ `http://127.0.0.1:<cổng>` + `ipc:` [CHƯA KIỂM cú pháp cổng động trong CSP WebView2]. Sidecar tự gọi ra ngoài: Google Translate, Gemini, OpenAI, Ollama `127.0.0.1:11434`, kho model (D12). | Webview không gọi internet trực tiếp. Bỏ link Google Fonts, bundle Be Vietnam Pro. |
| D8 | Nơi chứa bản phát hành | **GitHub Release ở repo công khai chỉ chứa release**. Trần 2 GB/asset ⇒ bộ cài CPU < 1,8 GB (cổng CI); gói GPU/model > 2 GB chia phần hoặc file share nội bộ (Q1). | Updater và Model Manager đọc công khai, không cần token. |
| D9 | Hệ điều hành | **Windows 10/11 x64**. Không macOS/ARM. | Máy công ty. |

## 2. Quyết định riêng cho app offline (D10–D16)

### D10 — Backend cục bộ: sidecar FastAPI đóng băng (PyInstaller onedir)

Chọn **PyInstaller onedir** của entry mới `backend/app/desktop/main.py` (lệnh con `serve` / `worker` /
`initdb` / `kiem-gpu` / `tai-model`), build trên GitHub Actions `windows-latest`, đặt trong
`bundle.resources` của Tauri, Rust spawn trong Job Object.

| Phương án | Ưu | Nhược | Kết luận |
|---|---|---|---|
| PyInstaller onedir (chọn) | Tiền lệ VoxDub; mã Python giữ nguyên; smoke test được trên runner | Không build chéo; ~2–2,5 GB [SUY LUẬN]; hidden-import paddle/transformers phải dò | Spike Phase 0 |
| PyInstaller onefile | Một exe | Giải nén hàng GB mỗi lần mở, AV chặn — VoxDub đã loại | Loại |
| Nhúng Python (python-build-standalone + site-packages) | Không cần hook PyInstaller | Cũng phải build trên Windows; to hơn; tự viết launcher | Dự phòng nếu PyInstaller kẹt ở paddle |
| Viết lại backend bằng Rust (kiểu Koharu) | Nhẹ | Bỏ 80+ mini-spec đã đo | Loại |

Hệ quả bắt buộc:
- Mỗi lần "build thật" là một lượt CI Windows (30–60 phút [SUY LUẬN]).
- Spec PyInstaller `collect_all` ít nhất: `paddleocr`, `paddlex`, `paddle`, `manga_ocr`, `unidic_lite`,
  `fugashi`, `transformers`, `onnxruntime`, `pypdfium2`, `kombu.transport.filesystem`, `celery`; dữ liệu:
  `alembic.ini` + `alembic/versions/*`, `fonts/`, `models/`. Danh sách cuối chỉ biết sau Phase 0.
- Loại khỏi bundle: `app/services/ocr_benchmark/` (gọi tesseract). `app/services/translate/codex.py` chưa
  nối dây, dùng `fcntl` (không có trên Windows) ⇒ khi nối (E73) phải thay khoá tệp bằng cách chạy được
  trên Windows.
- Rust đặt env cho sidecar `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8` (console Windows cp1252). Handshake
  stdout là JSON ASCII; log ghi tệp UTF-8.

### D11 — Thay Postgres/Redis/Celery

**Chọn: Postgres NHÚNG (không Docker) + Celery `--pool=solo` với broker `filesystem://` của kombu + bỏ Redis.**
Không đổi schema, không đổi test.

Mã hiện có phụ thuộc Postgres sâu:
- `app/models/__init__.py`: khoá chính `postgresql.UUID`, 9+ cột `JSONB`, enum native, `DateTime(timezone=True)`.
- 29 migration dùng `postgresql.ENUM(create_type=False)`, `ALTER TYPE … ADD VALUE` trong `autocommit_block`.
- `app/services/so_cai_han_muc.py`: `pg_advisory_xact_lock(hashtextextended(...))`.
- `tests/conftest.py`: DB Postgres thật, `downgrade base` + `upgrade head`.
- Redis chỉ cần cho `GeminiProjectRateGate` khi `LLM_PROJECT_RPM > 0` ⇒ desktop đặt `0`.
  `batch/dispatch.py` hỏi `celery_app.control.inspect()`; không trả lời ⇒ đã có nhánh lùi theo đồng hồ.

| Phương án | Tác động mã | Rủi ro | Kết luận |
|---|---|---|---|
| **Postgres nhúng** (binary zonky windows-amd64 ~30 MB nén [SUY LUẬN]) + Celery solo + broker filesystem | Gần 0: `DATABASE_URL`, `CELERY_BROKER_URL=filesystem://`, `LLM_PROJECT_RPM=0` | postgres.exe từ chối chạy dưới admin — phải qua `pg_ctl` [CHƯA KIỂM]; `initdb` lần đầu; AV; broker filesystem ít dùng [CHƯA KIỂM trên Windows] | **CHỌN** |
| SQLite + hàng đợi trong tiến trình | `with_variant` UUID/JSONB/Enum; bỏ advisory lock; datetime mất múi giờ ⇒ so sánh aware/naive nổ âm thầm; cơ chế migration thứ hai | Lỗi lớp "im lặng" rải trong `routes.py`/`tasks.py` | Dự phòng nếu spike Postgres hỏng |
| Docker Desktop trên máy người dùng | 0 | Đòi Docker + WSL2 — không còn "cài là chạy" | Loại (đã có `docs/CAI_DAT_CUC_BO.md`) |

Topology = production `ROLE=all`: **API uvicorn + worker Celery `--pool=solo`**, hai tiến trình cùng
bundle. Rust thay vòng `while true` của `deploy-start.sh`: đếm số lần chết, bật lại sau 10 s, báo lên UI.
Không bật beat.

Phải vá cho Windows:
- `worker_rss_file` / `worker_ready_file` / `WORKER_STATE_FILE` đang ở `/tmp/*.json` ⇒ chuyển vào thư mục dữ liệu.
- `bo_nho.rss_mb()` đọc `/proc/self/statm` ⇒ `None` trên Windows ⇒ van xả bộ nhớ không bao giờ mở ⇒
  máy 8 GB dễ OOM. Thêm nhánh `ctypes` `GetProcessMemoryInfo`.

### D12 — Phân phối model

| Model | Kích thước | Cách giao |
|---|---|---|
| comic-text-detector ONNX | 91 MB | Đóng gói trong bộ cài |
| LaMa manga ONNX | 197 MB | Đóng gói trong bộ cài |
| manga-ocr (Apache-2.0) | ~440 MB | Tải lần đầu qua Model Manager |
| PaddleOCR det/rec | ~20 MB | Tải lần đầu |
| SDXL inpaint | ~7 GB | Chỉ gói GPU, tải theo yêu cầu |
| RF-DETR Seg 2XL (Manga109, điều khoản học thuật) | 161 MB + torch | Chỉ gói GPU, cờ "nội bộ", ghi giấy phép trong lock |
| PaddleOCR-VL | ~2 GB [SUY LUẬN] | Chỉ gói GPU, tắt mặc định |

Một đường tải duy nhất `app/desktop/model_manager.py`: manifest `models.lock.json` (url, sha256, size,
license), tải vào `.part`, băm, rồi mới đổi tên; endpoint `/api/v1/desktop/models` báo tiến độ; **nhập từ
tệp zip** cho máy không có internet. Mirror model lên release của ta thay vì để máy người dùng tải thẳng
từ Hugging Face (không pin được sha256 cả snapshot).

### D13 — Runtime, dò GPU, đóng gói torch CUDA

1. **Bộ cài CPU (mặc định, ~1–1,5 GB nén [SUY LUẬN])**: onnxruntime CPU (CTD, LaMa), torch CPU (manga-ocr),
   paddle CPU. Số đã đo trên 2,6 nhân: CTD 40–70 s, manga-ocr 6–35 s, LaMa 11–40 s ⇒ ~1,5–3 phút/trang.
2. **DirectML (tuỳ chọn)**: `onnxruntime-directml` cho CTD + LaMa trên mọi GPU DX12 không cần CUDA
   [CHƯA KIỂM: shape động của LaMa, mức tăng tốc]. Chọn một trong hai gói ort sau khi đo trên máy thật.
3. **Gói GPU NVIDIA (tải thêm)**: sidecar thứ hai đóng băng từ stage `worker-gpu` (torch cu126 + diffusers +
   rfdetr), ~3–4 GB nén [SUY LUẬN]. Rust chọn sidecar theo cài đặt + kết quả dò GPU.

Tự dò và lùi: sidecar đọc `ort.get_available_providers()` (+ `torch.cuda` trong bản GPU), thứ tự
`cuda → dml → cpu`, ghi log + trường `runtime` trong `/healthz`. `ctd_device`/`inpaint_device` nhận `auto`.
SDXL **không lùi** CPU (giữ luật E74). Rust dò `nvidia-smi.exe` để gợi ý "Máy có GPU X (Y GB), cài gói GPU?".

### D14 — Model nào chạy ở chế độ nào

| Bước | CPU | GPU (gói NVIDIA) |
|---|---|---|
| Nhận diện | CTD ONNX (mặc định); `ai_gemini` nếu có khoá | CTD CUDA; **RF-DETR Seg 2XL** — bật mặc định chỉ khi đo ≤ 2× thời gian CTD và không sót vùng hơn |
| OCR | manga-ocr (ja), PaddleOCR (en/zh) | như CPU trên CUDA; PaddleOCR-VL tuỳ chọn |
| Xoá chữ | LaMa ONNX (+ tô phẳng E69, theo nét E79) | LaMa CUDA; SDXL (`khuech_tan`), VRAM ≥ 8 GB |
| Dịch | google_fast (cần mạng) · Gemini/OpenAI (khoá) · local_llm (Ollama/LM Studio) · ChatGPT kiểu Codex (E73, khi nối xong) | như CPU |
| Canh chữ, xuất | Pillow, không model | như CPU |

Khởi động kiểm tổ hợp: cấu hình đòi GPU mà máy không có ⇒ UI báo "cần gói GPU", không chạy mò.

### D15 — UI: tái dùng frontend React trong webview

- Vite build vào `frontendDist`. Rust bơm `window.__API_BASE__` và token phiên qua `initialization_script`.
- **Cổng ngẫu nhiên + token**: Rust sinh token 32 byte, truyền cho sidecar qua env; sidecar bind
  `127.0.0.1:0`, in handshake `{port,pid}`; mọi route (kể cả route khách) đòi `Authorization: Bearer`,
  so sánh thời gian hằng; `/healthz` mở.
- CORS: `http://tauri.localhost`, `https://tauri.localhost` (+ test preflight có Origin thật).
- CSP: `connect-src ipc: http://ipc.localhost http://127.0.0.1:*`; `img-src 'self' blob: data:`; `font-src 'self'`.
- Cửa sổ `visible:false` tới khi backend sẵn sàng; `dragDropEnabled:false` [CHƯA KIỂM].
- Lưu tệp xuất qua lệnh Rust `save_export(job_id)` (dialog phía Rust), không tin `<a download>` blob trong WebView2.
- Tắt kiểm bản mới của web, ẩn thẻ hạn mức, thêm màn **Cài đặt máy bàn** (engine, khoá API qua Credential
  Manager, GPU/runtime, Model Manager, thư mục dữ liệu, dọn dẹp, cập nhật). Chữ hiển thị: BA review.
- WebGPU: giữ lùi 2D + banner; không chặn phát hành.

### D16 — Dữ liệu người dùng, dọn dẹp, gỡ cài

- Cài vào `%LOCALAPPDATA%\Programs\Translation\` (NSIS `currentUser`, không UAC).
- Dữ liệu `%LOCALAPPDATA%\<identifier>\`: `pgdata/`, `storage/`, `models/`, `runtime-gpu/`, `queue/`,
  `logs/` (xoay 10×5 MB), `state/`, `config.json` (không có bí mật). Mật khẩu Postgres + khoá API ở
  Credential Manager.
- Không tự xoá tệp người dùng; màn Dọn dẹp hiện dung lượng từng mục.
- Gỡ cài giữ dữ liệu mặc định, hỏi "Xoá cả dữ liệu, model (N GB)?" [CHƯA KIỂM `installerHooks`].
  Ghim major Postgres giữa các bản; nâng major là mini-spec riêng.
- Đĩa: CPU ~3 GB + model 0,8 GB; gói GPU +6–8 GB; SDXL +7 GB [SUY LUẬN]. RAM tối thiểu 8 GB.

## 3. Hướng đã đóng (đừng thử lại khi chưa đọc lý do)

- PaddleOCR-VL trên CPU: >13 phút chưa xong 7 vùng, RAM chạm trần 10 GB (đo 15-10-2026).
- RF-DETR Seg 2XL trên CPU trong workspace: bị OOM-kill (exit 137) ở trần 10 GB (đo 15-10-2026).
- FLUX.2-klein: diffusers không có pipeline xoá vùng; FLUX.1-dev cấm thương mại.
- Build bộ cài có sidecar Python từ workspace Linux: PyInstaller không build chéo, đĩa còn ~3,6 GB.

Chưa đóng: ChatGPT kiểu Codex (E73) — `codex.py` đã viết, chờ chủ dự án cấp quyền để nối dây.
