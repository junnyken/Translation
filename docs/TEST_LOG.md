# TEST_LOG.md — Translation

Ghi **số liệu thật** của từng lần chạy. Không ước lượng, không ghi "pass" khi chưa chạy.

---

## M1 — Project Scaffolding & Pipeline Contract

**Ngày:** 2026-08-27 · **Môi trường:** workspace `trieunt-c`, Docker 29.1.3, Python 3.12.3,
Postgres 16-alpine (container `translation-db-1`), Redis 7-alpine.

### 1. Test tự động

```
$ cd backend && ../.venv/bin/python -m pytest
42 passed in 5.52s
```

| Nhóm | File | Số test | Kết quả |
|---|---|---|---|
| Unit — Pydantic schema | `tests/test_schemas_unit.py` | 12 | pass |
| Unit — state machine Page | `tests/test_state_machine_unit.py` | 6 | pass |
| Unit — interface engine | `tests/test_interfaces_unit.py` | 6 | pass |
| Guardrail — không có logic AI ở M1 | `tests/test_no_ai_logic.py` | 2 | pass |
| Integration — HTTP + Postgres thật | `tests/test_api_integration.py` | 12 | pass |
| Migration — upgrade/downgrade thật | `tests/test_migration.py` | 4 | pass |

Ghi chú: integration test chạy trên **Postgres thật** (DB `translation_test`), không dùng SQLite/mock;
ảnh upload trong test là **PNG thật do Pillow render**, không phải file rỗng.

### 2. Migration 2 chiều (chạy tay, ngoài test)

```
$ alembic upgrade head      → tạo 7 bảng + alembic_version   (OK)
$ alembic downgrade base    → 0 bảng, 0 enum type còn sót     (OK)
$ alembic upgrade head      → dựng lại sạch, không lỗi "type already exists" (OK)
```

### 3. Live verification (chạy thật qua HTTP trên container)

```
POST /api/v1/projects                      -> 201  id=416da44c… name="MTE Live Test Chapter" source_lang=ja intended_use=personal
POST /api/v1/projects/{id}/pages           -> 202  {"page_id":"2bfbe09f…","status":"queued","job_id":"388e42be…"}
     (upload ảnh JPEG THẬT 148.593 byte, 1400x2000)
GET  /api/v1/pages/{page_id}               -> 200  status=queued, order=1, clean_image_path=null
GET  /api/v1/pages/{page_id}/regions       -> 200  []            (đúng: M2 chưa chạy, không bịa region)
GET  /api/v1/jobs/{job_id}                 -> 200  type=detect, status=queued, retry_count=0, error_log=null
GET  /api/v1/jobs/<uuid không tồn tại>     -> 404
POST /api/v1/projects (thiếu intended_use) -> 422
GET  /docs                                 -> 200  (Swagger liệt kê đúng 6 endpoint /api/v1)
```

Đối chiếu dữ liệu thật sau flow trên:

| Kiểm | Kết quả |
|---|---|
| File lưu trên volume | `/data/storage/projects/<pid>/pages/<page_id>.jpg`, 148.593 byte |
| md5 ảnh gốc vs ảnh đã lưu | `4beff20947efb0152fb9d2f68e1d5d89` — **trùng khớp**, không hỏng byte |
| `page` trong Postgres | order=1, status=`queued`, `clean_image_path` = NULL |
| `job` trong Postgres | type=`detect`, status=`queued`, retry_count=0 |
| `text_region` / `ocr_result` / `translation_result` / `typeset_result` | **0 record** — đúng, chưa bước nào chạy |

Ghi chú trung thực: ảnh dùng để verify là **trang mẫu tự dựng bằng Pillow** (khung panel + bubble trắng,
chữ Latin), **không phải trang manga scan thật**. Đủ để chứng minh đường đi upload → lưu file → vào hàng đợi
của M1; **không đủ** để kết luận gì về chất lượng nhận diện — M2 cần ảnh manga thật.

### 4. Regression

**N/A — Mini-Spec đầu tiên của Phase**, chưa có invariant cũ để bảo vệ.

### 5. Giới hạn của lần đo này

- Ảnh dùng để verify là **trang mẫu tự dựng**, chưa phải trang manga scan thật.
  Đủ cho M1 (chỉ kiểm lưu file + tạo job), **không đủ** cho M2 — M2 cần ảnh manga thật để đo tỷ lệ miss.
- Chưa đo thời gian xử lý/trang (chưa có bước AI nào chạy).
