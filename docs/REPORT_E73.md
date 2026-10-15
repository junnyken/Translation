# REPORT E73 — Dịch bằng tài khoản ChatGPT, đăng nhập kiểu Codex (chỉ bản cài cục bộ)

## Summary
Engine dịch mới `chatgpt_codex`: người cài đăng nhập tài khoản ChatGPT của chính họ bằng device-code
(như Codex CLI), worker gọi `chatgpt.com/backend-api/codex/responses` (luồng SSE), ép JSON theo `id`
như E71. Chủ dự án yêu cầu thử nghiệm (15-10-2026) sau khi được báo rủi ro điều khoản.

## Audit Before Build
- Giao thức chuyển từ Koharu `crates/koharu-agent/src/codex/*` (MIT OR Apache-2.0) — chỉ chuyển cách
  làm, viết lại bằng Python `urllib`, ghi nguồn trong docstring `services/translate/codex.py`.
- Khuôn E72 (`local_llm`): enum Postgres + `ENGINE_LLM` (lỗi ⇒ lùi `google_fast`) + `build_translator`.

## Design Choice
- **Ranh giới cứng**: `CHE_DO_CAI_CUC_BO=false` (mặc định, production) ⇒ engine từ chối TRƯỚC khi gọi
  mạng, mọi endpoint chọn engine trả 422 `codex_chi_cai_cuc_bo`, API đăng nhập 404. Khách lạ ⇒ 403 kể
  cả ở bản cài cục bộ. Chỉ quản trị đăng nhập/đăng xuất (người khác 404).
- Token: tệp JSON quyền 600, thư mục 700, volume riêng `codex_secrets` (`/secrets/codex`), ghi nguyên
  tử; khoá liên tiến trình khi làm mới (fcntl; msvcrt trên Windows cho app desktop). API chỉ trả mã
  thiết bị, email, gói — không bao giờ trả token; `/healthz` chỉ hai cờ true/false.
- Gộp 6 chỗ kiểm engine trùng lặp trong `routes.py` thành `_kiem_engine` (thêm luôn cho hai endpoint
  dịch lại trang/vùng vốn chưa kiểm).

## Changed Files
- `app/services/translate/codex.py` (mới), `app/api/v1/codex_routes.py` (mới), `app/main.py`
  (router + `/healthz.codex`), `app/api/v1/routes.py` (`_kiem_engine`), `app/models/enums.py`,
  `app/core/config.py` (`che_do_cai_cuc_bo`, `codex_*`), `app/services/translate/engines.py`,
  `app/workers/tasks.py`, `alembic/versions/0030_e73_codex.py`, `deploy/docker-compose.yml`,
  `docs/CAI_DAT_CUC_BO.md`, frontend (màn đăng nhập ChatGPT + lựa chọn engine).

## New API/DB/State
- Enum `translation_engine` + `chatgpt_codex` (migration `0030_e73_codex`, revises `0029_e78_psd`).
- `GET/DELETE /api/v1/codex`, `POST /api/v1/codex/dang-nhap`, `POST /api/v1/codex/dang-nhap/hoi`.
- `/healthz.codex = {bat, da_dang_nhap}`.

## Tests
`tests/test_e73_codex.py` — 12 test, máy chủ HTTP THẬT trong test đóng vai auth.openai.com +
chatgpt.com: đăng nhập hai bước + quyền 600; SSE + ép schema + bỏ model ẩn; 401 ⇒ làm mới một lần
với token mới; luồng đứt ⇒ lỗi; cờ tắt ⇒ không gọi mạng; chưa đăng nhập ⇒ lỗi rõ; worker đọc đúng cấu
hình; API 404 (cờ tắt / không phải quản trị); API không lộ token; 422 trên máy chủ chung; khách 403.

## Live Verification
CHƯA chạy với tài khoản ChatGPT thật — cần chủ dự án đăng nhập trên bản cài cục bộ của mình.
Production KHÔNG bật (`che_do_cai_cuc_bo=false`).

## Remaining Limits
- Giao thức không công khai, có thể đổi bất cứ lúc nào; tài khoản có thể bị giới hạn.
- Không gọi OpenAI thu hồi token khi đăng xuất (chỉ xoá khỏi máy).
