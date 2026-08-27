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
tạo `Job(type=detect, status=queued)`. **Không** chạy detect trong request.

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
**M1 luôn trả `[]`** vì chưa có M2 — không bịa region. Sắp xếp theo `reading_order` (NULL xuống cuối) rồi `created_at`.

## 6. `GET /api/v1/jobs/{job_id}` → 200

```json
{ "id": "…", "type": "detect", "page_id": "…", "status": "queued",
  "retry_count": 0, "error_log": null, "created_at": "…", "updated_at": "…" }
```
Dùng chung cho mọi loại job xuyên suốt Phase. Không tồn tại → `404`.

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

`GET /pages/{id}/ocr` (M3) · `GET /pages/{id}/clean-image` (M4) ·
`POST|GET /pages/{id}/translate|translation` (M5) · `POST /pages/{id}/typeset`, `GET /pages/{id}/typeset-preview` (M6) ·
`PATCH /regions/{id}` (M7) · `POST /projects/{id}/export`, `GET /export-jobs/{id}` (M8) ·
`POST /projects/{id}/run-batch`, `GET /projects/{id}/batch-status` (M9).
