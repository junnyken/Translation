# Báo cáo Mini-Spec M5 — Dịch 2 đường + Thứ tự đọc

**Project:** Translation · **Phase:** MTE · **Ngày:** 2026-08-27
**Nền:** M1 `9d093be` · M2 `dea4965` · M3 `4b3139e` · M4 `9906501` (`v0.4-M4`)

## 1. Summary

Pipeline nay chạy một mạch trọn vẹn tới bản dịch: upload → nhận diện khung → đọc chữ → xoá chữ gốc →
**dịch sang tiếng Việt theo đúng thứ tự đọc**. Worker sắp `TextRegion` theo hướng đọc của loại truyện
(`ja` phải→trái, `en`/`zh` trái→phải), **điền cột `TextRegion.reading_order`** (để NULL từ M1), rồi gọi
một trong hai engine tách rời: `google_fast` (miễn phí, theo dòng) hoặc `llm_context` (gộp cả trang gửi
Gemini, giữ mạch văn). Kết quả ghi vào `TranslationResult` kèm `token_cost` thật.

**Không tạo bảng mới, không migration** (`TranslationResult` đã có sẵn từ M1).
**256 test pass**, 6 skip (test model thật, opt-in) — tăng 64 test so với M4.

## 2. Audit Before Build

`ITranslator` (M1) nguyên vẹn, `TranslationResult` + enum `TranslationEngine`/`TranslationStatus` đã
chốt từ M1 nên không phải đụng schema. Gap đúng là: chưa có implement engine nào, `reading_order` chưa
ai điền, chưa có `JobType.translate` chạy thật.

**Hai giả định của spec bị thực tế bác bỏ ngay ở bước audit** (chi tiết `TEST_LOG § M5.4`):

| Spec giả định | Thực tế |
|---|---|
| Dùng `gemini-2.5-flash` | **404** — *"This model is no longer available to new users"*. Phải chuyển sang dòng 3.x. |
| Nhiều API key ⇒ nhiều quota | Gemini: *"Rate limits are applied per project, not per API key."* ⇒ xoay key **cùng project** không tăng hạn mức. |

Phát hiện thứ hai quan trọng vì nó làm **rỗng phần lớn giá trị của bảng `APIKeyPool`** mà PLAN dự tính.

## 3. Design Choice

- **Hai đường dịch cố ý tách rời**, không gộp thành một hàm chung có cờ: người dùng phải kiểm soát được
  khi nào tốn tiền, khi nào miễn phí.
- **Mặc định là bản miễn phí** (`TRANSLATE_DEFAULT_ENGINE=google_fast`) — hệ thống không bao giờ tự tiêu
  token của người dùng khi họ chưa chọn. Có test canh mặc định này: đổi sang `llm_context` sẽ làm đỏ test.
- **Tắt "thinking" mặc định** (`thinkingBudget=0`). Đo thật: không tắt thì 938 token suy nghĩ cho 6 dòng
  — **đắt gấp ~7,7 lần, chậm gấp 4 lần**, chất lượng tương đương. Nếu model vẫn trả `thoughtsTokenCount > 0`
  dù đã yêu cầu tắt, worker ghi cảnh báo vào log để hoá đơn không phình âm thầm.
- **`token_cost` ghi ở đúng 1 dòng đầu trang**: `llm_context` gọi 1 request cho cả trang, nên chi phí là
  của trang. Ghi vào từng dòng sẽ **nhân bản chi phí** khi cộng toàn bảng. Có test canh.
- **Không tạo bảng `APIKeyPool`** dù PLAN có nhắc: spec §4A của M5 không liệt kê bảng này, constraint 7
  buộc key chỉ nằm ở `.env`/secrets, và (xem §2) xoay key cùng project vốn không tăng quota. Đưa key vào
  Postgres sẽ kéo theo mã hoá + xoay khoá — đẩy sang M9 nếu thật sự cần chia trạng thái quota giữa worker.
  **3 guardrail test** quét toàn bộ file git-track để chặn key lọt vào commit.
- **Thứ tự đọc gom theo dải ngang** (cao ≈ trung vị chiều cao bbox × 0,6) thay vì so `y` tuyệt đối —
  bubble lệch nhau vài chục pixel vẫn phải tính là cùng một hàng.
- **Fallback có dán nhãn**: LLM lỗi/hết quota → lùi về `google_fast`, mọi dòng của trang mang
  `status=fallback_used`, `Job.error_log` ghi lý do gốc. Không bao giờ trả bản dịch rỗng rồi báo thành công.
- **Dòng model không trả về → `pending`**, không bịa nội dung. (`TranslationStatus` chốt ở M1 không có
  `needs_manual`, nên `pending` là "chưa có bản dịch", không phải "đã xong".)
- **Giữ nguyên `raw_text` của M3** làm đầu vào — để LLM tự sửa lỗi OCR theo ngữ cảnh. Kiểm chứng thật:
  `IAM` (OCR đọc sai `I AM`) được dịch đúng thành "Ta ở đây."
- **Timeout riêng** cho dịch (`TRANSLATE_TIMEOUT_SECONDS`), không dùng chung với detect/OCR/inpaint —
  nay là **bốn** timeout độc lập, có test canh.

## 4. Changed Files

| File | Đổi gì |
|---|---|
| `backend/app/services/translate/engines.py` | **mới** (275 dòng) — `GoogleTranslateEngine`, `LLMContextTranslator`, xoay key, `UsageStats`, factory |
| `backend/app/services/translate/reading_order.py` | **mới** (88 dòng) — hướng đọc theo `source_lang`, gom dải ngang |
| `backend/app/services/translate/__init__.py` | **mới** — export công khai của package |
| `backend/app/workers/tasks.py` | +239 — task `run_translate_job`, nối chuỗi sau inpaint, `build_translator` |
| `backend/app/api/v1/routes.py` | +72 — `GET /pages/{id}/translation`, `POST /pages/{id}/retry-translate` |
| `backend/app/core/config.py` | +25 — 10 biến M5 + `gemini_api_key_list` (không log, không trả ra API) |
| `backend/app/schemas/common.py` | +15 — `TranslationResultRead` |
| `backend/app/services/dispatch.py` | +13 — `dispatch_translate_job` (broker chết thì nói thật) |
| `backend/tests/test_translate_*.py` | **mới** (632 dòng) — 58 test |
| `backend/tests/test_no_ai_logic.py` | +87 — 6 guardrail M5 (rò key, mặc định miễn phí, tắt thinking, 4 timeout) |
| `backend/tests/conftest.py` | +41 — fixture translator giả |
| `.env.example`, `docs/{ARCH,API,FEATURES,PLAN,TEST_LOG}.md` | cấu hình + tài liệu |

## 5. New API / DB / State

**API mới:** `GET /api/v1/pages/{id}/translation` · `POST /api/v1/pages/{id}/retry-translate?engine=`

**DB:** không bảng mới, không migration. M5 **ghi** vào `translation_result` và **điền**
`text_region.reading_order`.

**State:** `inpainted | inpaint_needs_review → translated`. Job translate lỗi ⇒ `Page` **giữ nguyên**
`inpainted` để còn chạy lại. Fallback vẫn là `done` nhưng có nhãn `fallback_used`.

## 6. Tests

`256 passed, 6 skipped in 34.28s` — chi tiết từng nhóm ở `TEST_LOG § M5.1`.
64 test mới: 30 engine · 15 thứ tự đọc · 13 integration task/API · 6 guardrail kiến trúc.

## 7. Live Verification

Chạy đúng đường thật (HTTP → Redis → worker Celery → HTTPS → DB), số liệu đầy đủ ở `TEST_LOG § M5.2`:

- **`llm_context` trên trang 6 bubble (en→vi)**: 6/6 dòng dịch đúng nghĩa, `reading_order` điền 1..6,
  `SUM(token_cost)` = **227** (ghi ở 1 dòng, không nhân bản), LLM tự sửa lỗi OCR `IAM` → "Ta ở đây."
- **Đối chứng 2 engine trên cùng một trang**: `HELLO/THERE` → `google_fast` cho **"Xin chào / ĐÓ"** (vô
  nghĩa vì dịch rời từng dòng), `llm_context` cho **"Chào nhé."** (164 token). Đây là bằng chứng thật cho
  lý do tồn tại của 2 đường, không phải suy đoán.
- Chạy lại trên cùng page **thay thế** bản dịch cũ, không tích luỹ bản trùng.

## 8. Success Criteria — đối chiếu thẳng

| Tiêu chí spec | Kết quả |
|---|---|
| 2 engine độc lập, chọn được | ✅ verify thật cả 2 trên cùng 1 trang |
| Không lệch dòng khi ghép bản dịch về region | ✅ ghép 1:1 theo số thứ tự; thiếu dòng → `pending`, không đẩy dồn |
| Thứ tự đọc theo `source_lang`, không hard-code | ✅ `ja`→rtl, `en`/`zh`→ltr, ép được bằng env |
| Hết quota không âm thầm hạ cấp | ✅ `fallback_used` + `error_log` ghi lý do gốc |
| Không đốt token ngoài ý muốn | ✅ mặc định miễn phí + tắt thinking + ghi `token_cost` thật, đều có test canh |
| Key không lọt vào DB/git/API | ✅ 3 guardrail test quét toàn repo |
| **Chất lượng dịch trên manga thật** | ❌ **CHƯA nghiệm thu** — mới đo trên ảnh tổng hợp thoại tiếng Anh |

## 9. Remaining Limits / Follow-ups

- **Chưa đo trên trang manga scan thật** — nút thắt chung với M2/M3/M4, vẫn chờ ảnh thật.
- **Đường tiếng Nhật (rtl) chưa chạy thật đầu-cuối** — mới verify bằng unit test; các page `ja` trong DB
  đang dừng ở `detected`.
- **Nhánh `fallback_used` chưa gặp tình huống thật** — mới verify bằng integration test giả lập lỗi.
- **Xoay key chỉ có tác dụng khi key thuộc project khác nhau** (giới hạn của Gemini, không sửa được ở code).
- `google_fast` dùng endpoint công khai không có SLA — có thể bị đổi/chặn bất cứ lúc nào; đã có endpoint
  dự phòng và test canh nhánh này.
