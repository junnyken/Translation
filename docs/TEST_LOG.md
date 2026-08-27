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

---

## M2 — Text Region Detection (comic-text-detector)

**Ngày:** 2026-08-27 · **Môi trường:** worker container (Celery, CPU-only, `--concurrency=1`),
onnxruntime 1.20.1, model `comic-text-detector.onnx` 91MB
(sha256 `1a86ace7…d718f`, nguồn `mayocream/comic-text-detector-onnx`).

### 1. Test tự động

```
$ cd backend && ../.venv/bin/python -m pytest
84 passed, 3 skipped in 13.67s
```
(3 skipped = test chạy ONNX thật, phải bật `MTE_RUN_MODEL_TESTS=1` vì mất ~40s/ảnh)

| Nhóm | File | Số test | Kết quả |
|---|---|---|---|
| Unit — hình học bbox (convert, clamp, overlap, NMS) | `tests/test_detect_geometry_unit.py` | 17 | pass |
| Unit — CTDDetector (Protocol, letterbox, giải mã, thiếu weight) | `tests/test_detect_ctd_unit.py` | 11 | pass |
| Integration — Celery task detect trên DB thật | `tests/test_detect_task_integration.py` | 11 | pass |
| Guardrail kiến trúc (M1 mở rộng cho M2) | `tests/test_no_ai_logic.py` | 5 | pass |
| Model thật trên fixture | `tests/test_detect_real_model.py` | 3 | skipped (opt-in) |
| Kế thừa M1 (schema, state machine, API, migration) | các file M1 | 40 | pass |

Bài test đáng chú ý của M2:
- `test_confidence_thap_van_duoc_luu_voi_low_confidence` — chặn việc lọc bỏ âm thầm region điểm thấp.
- `test_chay_lai_khong_tao_region_trung_lap` — chạy lại job không nhân đôi region.
- `test_timeout_ghi_failed_va_detection_failed` — quá giờ thì ghi `failed`/`detection_failed`, worker không treo.
- `test_upload_tra_202_ngay_khong_cho_detect_chay_xong` — cắm detector ngủ 5s, upload vẫn < 2s ⇒ không chạy đồng bộ.
- `test_import_app_khong_keo_theo_onnxruntime` — tiến trình API không nạp model.
- `test_nguong_bien_79_phan_tram` / `81_phan_tram` / `dung_80_phan_tram` — ngưỡng `overlap_suspect`.

### 2. Live verification — chạy model THẬT qua worker

Chạy qua đúng đường thật: `POST /pages` → Redis → Celery worker → ONNX CPU → DB.

| Ảnh | Kích thước | Vùng chữ đếm tay | Region detect được | bbox âm/vượt ảnh | low_confidence | overlap_suspect | Thời gian |
|---|---|---|---|---|---|---|---|
| `many_bubbles.png` | 1400×2000 | 6 | **6** | 0 | 1 | 0 | 39,6s |
| `few_bubbles.png` | 1200×1700 | 2 | **2** | 0 | 0 | 0 | 40,3s |
| `loose_sfx.png` | 1300×1800 | 4 (1 bubble + 3 SFX rời) | **4** | 0 | 0 | 0 | 40,1s |

Cả 3 page kết thúc ở `status=detected`, cả 3 job `status=done`, `error_log=null`.

Region của `many_bubbles.png` (toạ độ thật đọc từ API):

```
conf=0.88 pending         (240,164)  192x85
conf=0.85 pending         (964,1716) 183x82
conf=0.79 pending         (986,837)  108x83
conf=0.70 pending         (284,1481) 163x80
conf=0.56 pending         (959,212)  192x81
conf=0.50 low_confidence  (292,808)  106x85   <- dưới ngưỡng 0.5, VẪN được lưu, không bị bỏ
```

Region `low_confidence` này nằm đúng trên bubble "I AM / HERE" — là case khó thật (chữ nhỏ, nền xám),
không phải lỗi model.

**Idempotent — chạy lại thật:**
```
POST /pages/{id}/retry-detect                    -> 202, job mới eca4f4b5…
region TRƯỚC retry: 6 (id đầu 2b7e8c56…)
region SAU   retry: 6 (id đầu 333f6c32…)
worker log: "6 region (1 low_confidence, 0 overlap_suspect), xóa 6 region cũ, 44.6s"
page.status sau retry = detected
```
⇒ số region **không nhân đôi**, region cũ bị thay chứ không cộng dồn.

**Thời gian thật:** ~40s/ảnh trên CPU của workspace (`--concurrency=1`), nạp model lần đầu thêm ~1s.
Vì vậy `DETECT_TIMEOUT_SECONDS` trong `.env` đặt **120s** (mặc định trong code vẫn là 60s theo spec):
với 60s, một trang lớn hơn hoặc máy bận sẽ chạm timeout oan.

### 3. Giới hạn của lần đo này (đọc kỹ trước khi tin số)

- **Fixture là ảnh TỔNG HỢP do repo tự sinh** (`test_fixtures/make_fixtures.py`), không phải trang manga scan thật.
  Chúng chứng minh pipeline chạy đúng đầu-cuối và cách giải mã output của model là đúng —
  **không** chứng minh được tỷ lệ nhận diện trên manga thật.
- Tiêu chí "detect đúng ≥90% bubble có chữ thật" của M2 vì vậy **CHƯA được nghiệm thu**.
  Chặn: chưa có bộ ảnh có license rõ. Manga109-s trên Hugging Face đang `gated` (tải không token → HTTP 401);
  Roboflow cần API key. Cần bạn cấp bộ ảnh hoặc token để chạy lại chính bài đo này.
- Thời gian đo trên CPU của workspace, không phải GPU.
