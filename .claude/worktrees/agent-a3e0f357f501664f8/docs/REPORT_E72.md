# REPORT E72 — Dịch bằng LLM qua API kiểu OpenAI (máy chủ trên máy, hoặc API chính thức)

**Ngày:** 2026-10-15 · **Nguồn yêu cầu:** chủ dự án — "chạy cục bộ, cài local được", tham khảo
Koharu (provider `openai-compatible` / `lm-studio` cạnh llama.cpp nhúng).

## Summary

Engine mới `local_llm`: gọi `POST {LOCAL_LLM_BASE_URL}/chat/completions`, ép `json_schema`. Dùng được:

| Máy chủ | `LOCAL_LLM_BASE_URL` | `LOCAL_LLM_API_KEY` |
|---|---|---|
| Ollama | `http://host.docker.internal:11434/v1` | để trống |
| LM Studio | `http://host.docker.internal:1234/v1` | để trống |
| llama.cpp `llama-server` | `http://host.docker.internal:8080/v1` | để trống |
| **API chính thức OpenAI** | `https://api.openai.com/v1` | khoá API |

`LOCAL_LLM_MODEL` bắt buộc (vd `qwen3:14b`). Rỗng ⇒ engine báo lỗi rõ và lùi về `google_fast`;
không đoán model mặc định. Model đọc được ảnh thì đặt thêm `LOCAL_LLM_VISION=true` để gửi ảnh trang.

## Design Choice

- Kế thừa `LLMContextTranslator` và chỉ thay cách gửi (`_call_api`). Prompt là CÙNG prompt E71
  (`build_prompt_json`), cùng luật E66/E68, cùng bối cảnh thuật ngữ E31. Hai đường dịch không thể lệch
  luật với nhau. Một test so khớp từng ký tự prompt.
- Luôn ở chế độ JSON theo `id`: model nhỏ hỏng giao thức dòng đánh số nhiều hơn.
- Đường lùi `google_fast` nay áp cho **mọi** engine LLM (`ENGINE_LLM`), không riêng Gemini. Máy chủ
  trên máy chưa bật là chuyện thường ngày.

## Đăng nhập ChatGPT kiểu Codex — KHÔNG làm

Đã viết thử theo Koharu (device code bằng client id của ứng dụng Codex + `chatgpt.com/backend-api`).
Lớp kiểm duyệt an toàn của công cụ lập trình đã chặn giữa chừng, và chủ dự án chọn hướng thay thế: dùng
khoá API chính thức qua chính engine này. Mã thử đã gỡ trước khi commit; không có gì của nó còn trong
repo hay CSDL production.

## New API / DB / State

- Enum Postgres `translation_engine` thêm `local_llm` (migration `0026_e72`, không gỡ được khi downgrade:
  Postgres không có `DROP VALUE`).
- `/healthz` không đổi.

## Tests

- `test_e72_llm_cuc_bo.py`: 11 test gọi một **máy chủ HTTP thật dựng trong test**.
  - Kiểm thân request và `json_schema`.
  - Ghép theo `id`; không có thị giác thì không gửi ảnh.
  - Gửi `Bearer` khi có khoá.
  - Chưa đặt model thì không gọi mạng.
  - Máy chủ tắt, lỗi 500, JSON hỏng ⇒ `TranslationFailed`.
- `test_e58…::test_enum_chi_co…`: chốt cố ý đỏ khi thêm engine. Đã đọc lại các chỗ đối xử riêng với
  `google_fast` rồi mới cập nhật, ghi chú ngay trong test.

## Remaining Limits

1. **Chưa chạy với một Ollama/LM Studio thật.** Workspace không có máy chủ LLM nào.
2. Giao diện chưa có lựa chọn "LLM trên máy". Hiện chọn được qua API (`engine=local_llm`) hoặc đặt
   `TRANSLATE_DEFAULT_ENGINE=local_llm`.
3. ⚠️ Trỏ `local_llm` vào API trả tiền thì nó thành đường tốn tiền **không qua cổng nhịp**. Chỉ làm vậy ở
   bản cài của chính người trả tiền.
