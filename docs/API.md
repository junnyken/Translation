# API.md — Translation (prefix `/api/v1`)

Swagger tự sinh: `http://localhost:8010/docs` · OpenAPI JSON: `/openapi.json`

Nguyên tắc:
- Response **luôn** qua Pydantic schema (không trả SQLAlchemy object).
- Lỗi validate → `422` theo format mặc định FastAPI (không tự chế error format).
- Endpoint kích hoạt bước AI → `202 Accepted` + `job_id`, không trả kết quả trực tiếp.

## 1. `POST /api/v1/projects` → 201

Request:
```json
{ "name": "Chapter 01", "source_lang": "ja", "target_lang": "vi", "intended_use": "personal" }
```
- `source_lang`: `ja` | `zh` | `en` (bắt buộc)
- `target_lang`: `vi` (mặc định `vi`)
- `intended_use`: `personal` | `study` | `other` (**bắt buộc** — guardrail bản quyền của M10)

Response 201:
```json
{ "id": "…uuid…", "name": "Chapter 01", "source_lang": "ja", "target_lang": "vi",
  "intended_use": "personal", "status": "active", "created_at": "…", "updated_at": "…" }
```
Thiếu `name` / `source_lang` / `intended_use`, hoặc giá trị ngoài enum → `422`.

## 2. `GET /api/v1/projects/{project_id}` → 200

Trả project kèm tóm tắt page:
```json
{ "id": "…", "name": "…", "…": "…",
  "pages": [ { "id": "…", "order": 1, "status": "queued" } ] }
```
Không tồn tại → `404`.

## 3. `POST /api/v1/projects/{project_id}/pages` → 202

`multipart/form-data`, field `file` = ảnh trang (JPEG/PNG/WEBP, mặc định ≤ 25MB).

Hành vi: lưu file xuống storage → tạo `Page(status=queued, order=max+1)` →
tạo `Job(type=detect, status=queued)` → **đẩy job sang worker (M2)**. **Không** chạy detect trong request.

Nếu broker (Redis) chết: vẫn trả 202 (ảnh đã lưu), job đứng ở `queued` và `error_log` ghi
`enqueue_failed: …` — không giả vờ đã gửi. Chạy lại bằng `POST /pages/{id}/retry-detect`.

Response 202:
```json
{ "page_id": "…uuid…", "status": "queued", "job_id": "…uuid…" }
```
| Lỗi | Mã |
|---|---|
| project không tồn tại | 404 |
| file rỗng / không phải ảnh thật (kiểm magic bytes) | 422 |
| ảnh vượt `MAX_UPLOAD_MB` | 413 |

> `job_id` là field **thêm** so với bảng contract gốc của M1 (gốc: `{page_id, status}`) —
> thêm để client polling `GET /jobs/{id}` được ngay, không phải dò job của page. Ghi rõ ở báo cáo M1.

## 4. `GET /api/v1/pages/{page_id}` → 200

```json
{ "id": "…", "project_id": "…", "image_path": "projects/<pid>/pages/<page_id>.png",
  "clean_image_path": null, "order": 1, "status": "queued", "created_at": "…", "updated_at": "…" }
```
`clean_image_path` = `null` cho tới khi M4 (inpaint) chạy thật.

## 5. `GET /api/v1/pages/{page_id}/regions` → 200

```json
[ { "id": "…", "page_id": "…", "bbox": { "x": 0, "y": 0, "w": 0, "h": 0 },
    "confidence": null, "overlap_suspect": false, "reading_order": null, "status": "pending" } ]
```
Từ **M2** endpoint này trả dữ liệu thật sau khi job detect chạy xong (trước đó là `[]`, không bịa region).
Sắp xếp theo `reading_order` (NULL xuống cuối) rồi `created_at`.

- `confidence` < `CTD_CONF_THRESHOLD` → `status = "low_confidence"` (**vẫn trả về**, không bị lọc bỏ).
- 2 region chồng nhau > `CTD_OVERLAP_SUSPECT_RATIO` (so với box nhỏ hơn) → cả hai có `overlap_suspect = true`;
  hệ thống **chỉ gắn cờ**, không tự merge/xóa.
- `reading_order` vẫn `null` cho tới M5.

## 6. `POST /api/v1/pages/{page_id}/retry-detect` → 202 *(M2)*

Xếp lại việc detect cho 1 page (sau `detection_failed`, hoặc muốn chạy lại sau khi đổi tham số).
Tạo `Job(type=detect)` mới rồi enqueue — vẫn không chạy detect trong request.

```json
{ "page_id": "…", "status": "detected", "job_id": "…job mới…" }
```
| Lỗi | Mã |
|---|---|
| page không tồn tại | 404 |
| page đang `detecting` (tránh chạy trùng) | 409 |

Chạy lại là **idempotent**: region cũ của page bị xóa trước khi ghi region mới, không nhân đôi.

## 7. `GET /api/v1/pages/{page_id}/ocr` → 200 *(M3)*

Kết quả OCR theo từng vùng chữ của trang.

```json
[ { "region_id": "…", "raw_text": "こんにちは", "ocr_engine": "manga_ocr",
    "confidence": null, "status": "ok" } ]
```
- Trả `[]` khi job OCR chưa chạy — **không bịa text**.
- `ocr_engine`: `manga_ocr` (source_lang `ja`) hoặc `paddle_ocr` (`zh`/`en`).
- **`confidence: null` là bình thường với `manga_ocr`** — thư viện không cung cấp điểm tin cậy
  (xem ARCH.md §6). Với `paddle_ocr` đây là số thật, trung bình các dòng trong vùng.
- `status`: `ok` · `needs_manual` (text rỗng/không có ký tự có nghĩa, hoặc confidence dưới ngưỡng).
  Region `needs_manual` **vẫn được lưu**, không bị bỏ.
- Thứ tự giống `GET /pages/{id}/regions`.

## 8. `POST /api/v1/pages/{page_id}/retry-ocr` → 202 *(M3)*

Xếp lại việc OCR cho 1 page (sau khi sửa tham số, hoặc job trước lỗi). Chỉ enqueue.

| Lỗi | Mã |
|---|---|
| page không tồn tại | 404 |
| page chưa có vùng chữ nào (chưa detect) | 409 |

Chạy lại là **idempotent**: kết quả OCR cũ của đúng các region đó bị xóa trước khi ghi mới.

> Bình thường **không cần gọi tay**: detect xong hệ thống tự xếp việc OCR (`OCR_AUTO_CHAIN=true`).

## 9. `GET /api/v1/jobs/{job_id}` → 200

```json
{ "id": "…", "type": "detect", "page_id": "…", "status": "queued",
  "retry_count": 0, "error_log": null, "created_at": "…", "updated_at": "…" }
```
Dùng chung cho mọi loại job xuyên suốt Phase. Không tồn tại → `404`.
Job detect/ocr: `status` đi `queued → running → done | failed`; khi `failed`, `error_log` ghi nguyên nhân
(`timeout: vượt Ns`, `FileNotFoundError: …`, `enqueue_failed: …`, `no_region: …`).

Khi job OCR lỗi, `Page.status` **giữ nguyên `detected`** (không nhảy `ocr_done`) để còn chạy lại được.

## Bảng enum (chốt ở M1, M2–M10 không đổi âm thầm)

| Enum | Giá trị |
|---|---|
| `source_lang` | ja, zh, en |
| `target_lang` | vi |
| `intended_use` | personal, study, other |
| `project_status` | active, archived |
| `page_status` | queued, detecting, detected, detection_failed, ocr_done, inpainted, inpaint_needs_review, translated, typeset_done, ready_for_export |
| `region_status` | pending, low_confidence, confirmed |
| `ocr_engine` | manga_ocr, paddle_ocr |
| `ocr_status` | pending, ok, needs_manual |
| `translation_engine` | google_fast, llm_context |
| `translation_status` | pending, ok, fallback_used |
| `fit_status` | pending, fit_ok, overflow_warning |
| `job_type` | detect, ocr, inpaint, translate, typeset, export |
| `job_status` | queued, running, done, failed |

## Endpoint sẽ thêm ở mini-spec sau (chưa tồn tại)

`GET /pages/{id}/clean-image` (M4) ·
`POST|GET /pages/{id}/translate|translation` (M5) · `POST /pages/{id}/typeset`, `GET /pages/{id}/typeset-preview` (M6) ·
`PATCH /regions/{id}` (M7) · `POST /projects/{id}/export`, `GET /export-jobs/{id}` (M8) ·
`POST /projects/{id}/run-batch`, `GET /projects/{id}/batch-status` (M9).
