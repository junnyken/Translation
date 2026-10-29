# Báo cáo Mini-Spec M1 — MTE Core Data Model & Service Contract Foundation

**Project:** Translation · **Phase:** MTE · **Ngày:** 2026-08-27

## 1. Summary

Dựng xong nền greenfield của tool dịch manga: repo + docker-compose (api/worker/redis/db),
7 bảng dữ liệu với migration Alembic 2 chiều, 6 endpoint `/api/v1` (Swagger tự sinh),
5 interface engine trừu tượng cho M2–M6, và 4 tài liệu nền (ARCH/API/FEATURES/TEST_LOG).
**Không có một dòng logic AI nào** — đúng phạm vi M1, và có test tự động canh điều đó.

## 2. Audit Before Build

M1 là mini-spec đầu, không có code cũ để audit. Đã xác nhận trước khi viết model:

| Điều kiện | Kết quả |
|---|---|
| Repo có cấu trúc `backend/` (FastAPI + SQLAlchemy + Alembic) | Tạo mới, đạt |
| `docker-compose.yml` có `api`, `worker`, `redis`, `db` | Tạo mới, đạt |
| `docker compose up` chạy được `db` (+ `redis`) trước khi viết model | Đạt — cả 2 container `healthy` |
| Biến môi trường kết nối DB nằm trong `.env.example`, không hard-code credential | Đạt |
| Gap: DB chưa có bảng nào → M1 additive 100% | Đúng, không có invariant cũ cần bảo vệ |

## 3. Design Choice

- **Postgres quan hệ** (local container, đổi sang Supabase chỉ bằng `DATABASE_URL`) — dữ liệu có quan hệ rõ
  Project→Page→Region→3 kết quả.
- **`Page.status` khai báo đủ 10 giá trị ngay ở M1** để không phải `ALTER TYPE` enum nhiều lần trên Postgres.
  Kèm bảng cạnh hợp lệ `PAGE_STATUS_TRANSITIONS` + `assert_transition()` để M2–M6 không nhảy trạng thái tùy tiện.
- **`unique(region_id)`** trên cả 3 bảng kết quả → rerun job idempotent theo region ngay từ tầng DB,
  không phụ thuộc code của mini-spec sau nhớ kiểm tra.
- **Stub engine `Unimplemented*`** ném `NotImplementedError` kèm tên mini-spec phụ trách — thà fail to
  còn hơn trả kết quả giả.
- **Kiểm ảnh bằng magic bytes**, không tin `content-type` client gửi.

## 4. Changed Files (mới 100%)

```
Translation/
├── docker-compose.yml · .env.example · .gitignore · README.md · CLAUDE.md
├── backend/
│   ├── Dockerfile · requirements.txt · requirements-dev.txt · pytest.ini · alembic.ini
│   ├── alembic/env.py · alembic/script.py.mako
│   ├── alembic/versions/0001_m1_initial_schema.py
│   ├── app/main.py
│   ├── app/core/{config.py,db.py}
│   ├── app/models/{__init__.py,enums.py}
│   ├── app/schemas/common.py
│   ├── app/api/v1/routes.py
│   ├── app/services/{interfaces.py,storage.py}
│   ├── app/workers/celery_app.py
│   └── tests/{conftest.py,test_schemas_unit.py,test_state_machine_unit.py,
│              test_interfaces_unit.py,test_no_ai_logic.py,
│              test_api_integration.py,test_migration.py}
└── docs/{ARCH.md,API.md,FEATURES.md,TEST_LOG.md,PLAN.md,REPORT_M1.md}
```

## 5. New API / DB / State

**API (6 endpoint, tất cả dưới `/api/v1`)** — chi tiết ở `docs/API.md`:
`POST /projects` · `GET /projects/{id}` · `POST /projects/{id}/pages` (202) ·
`GET /pages/{id}` · `GET /pages/{id}/regions` · `GET /jobs/{id}`.

**DB:** 7 bảng `project`, `page`, `text_region`, `ocr_result`, `translation_result`, `typeset_result`, `job`
+ 13 enum type. Migration `0001_m1`, chạy sạch cả 2 chiều.

**State:** `PageStatus` 10 trạng thái + bảng cạnh hợp lệ; `RegionStatus`, `OCRStatus`,
`TranslationStatus`, `FitStatus`, `JobStatus` theo đúng danh sách đã chốt.

### Lệch so với spec — khai báo minh bạch (constraint #6 của M1)

1. **Thêm `job_id` vào response 202 của `POST /projects/{id}/pages`** (spec ghi `{page_id, status}`).
   Lý do: client polling `GET /jobs/{id}` được ngay, khỏi phải dò job theo page. Additive, không phá contract.
2. **`ocr_result.ocr_engine` và `translation_result.engine` để nullable** (spec không nói rõ).
   Lý do: đúng nguyên tắc evidence-first — chưa chạy engine nào thì không được điền tên engine giả.
3. **Thêm endpoint `GET /api/v1/health`** (ẩn khỏi Swagger, `include_in_schema=False`) để healthcheck hạ tầng.
4. **Thêm index** `ix_page_project_order`, `ix_job_page_id`, `ix_text_region_page_id` — thuần hiệu năng, không đổi contract.

## 6. Tests

42 test pass — chi tiết phân nhóm và số liệu ở `docs/TEST_LOG.md`.
Đáng chú ý: có 2 test **guardrail tự động** chặn vi phạm phạm vi M1 —
`test_khong_co_import_model_ai_trong_pham_vi_m1` (quét toàn bộ `app/` tìm import model AI) và
`test_celery_chua_dang_ky_task_that`.

## 7. Live Verification

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

## 8. Remaining Limits (cố ý để lại)

- Chưa có logic AI nào (detect/OCR/inpaint/translate/typeset) — phạm vi M2–M6.
- Chưa có `APIKeyPool` (M5/M9), `ExportJob` (M8) — sẽ tạo khi tới mini-spec đó.
- Chưa có authentication / user management — nếu cần multi-user phải là mini-spec riêng.
- Chưa có task Celery thật: upload page ghi `Job(type=detect, status=queued)` vào DB nhưng chưa dispatch lên broker.
- **Chưa nối Supabase**: đang chạy Postgres container + storage ổ đĩa local.
  Adapter Supabase Storage chưa viết; đặt `STORAGE_BACKEND=supabase` sẽ fail có thông báo rõ, không ghi sai chỗ im lặng.
- Ảnh dùng verify là trang mẫu tự dựng, **chưa phải manga scan thật** — M2 cần ảnh thật để đo tỷ lệ nhận diện.

**Mini-spec kế tiếp:** M2 — Text Region Detection (`CTDDetector(IDetector)` + task Celery `detect` đầu tiên).
