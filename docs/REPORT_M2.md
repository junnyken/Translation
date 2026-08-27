# Báo cáo Mini-Spec M2 — Comic Text Detector Integration (Bubble/Box Detection)

**Project:** Translation · **Phase:** MTE · **Ngày:** 2026-08-27 · **Nền:** M1 `9d093be` (tag `v0.1-M1`)

## 1. Summary

Bước nhận diện khung chữ đã chạy thật: worker Celery tiêu thụ `Job(type=detect)` do M1 tạo,
chạy comic-text-detector (ONNX, CPU) trên ảnh gốc, ghi `TextRegion` kèm `confidence` /
`overlap_suspect` và đẩy `Page` qua `queued → detecting → detected | detection_failed`.
`GET /pages/{id}/regions` từ chỗ luôn trả `[]` nay trả dữ liệu thật.
Không sửa 1 dòng schema nào của M1. 84 test pass (+3 test model thật chạy theo yêu cầu).

## 2. Audit Before Build (6 mục theo spec §5)

| # | Mục kiểm | Kết quả |
|---|---|---|
| 1 | `IDetector.detect(image_path) -> list[BBox]` còn nguyên | Đúng, `CTDDetector` implement không đổi tên method (xem §5 về `detect_regions`) |
| 2 | `TextRegion` đủ cột để ghi | Đủ: `bbox_x/y/w/h`, `confidence`, `overlap_suspect`, `status`. **Không cần migrate thêm cột nào** |
| 3 | `Job(type=detect, status=queued)` được tạo khi upload | Đúng — chạy lại flow upload thật, job tồn tại với `status=queued` trước khi viết consumer |
| 4 | Model weight đã có + `MODEL_WEIGHTS_PATH` đúng | Đã tải `comic-text-detector.onnx` (91MB) về `models/`, mount vào worker tại `/models`. **Không dùng weight giả** |
| 5 | `test_fixtures/` ≥3 ảnh, license rõ | **Chỉ đạt một phần** — xem §7 và §8. Ảnh hiện có là ảnh tổng hợp repo tự sinh (license rõ vì tự tạo), **không phải manga thật** |
| 6 | Gap = `IDetector` chưa implement | Đúng, và M2 chỉ làm đúng phần đó — không đụng OCR/M3 |

Thêm 1 phát hiện khi audit weight: **HF card của bản ONNX ghi `apache-2.0` nhưng repo gốc là GPL-3.0**
→ đã chốt xử lý theo điều kiện chặt hơn, ghi rõ trong `docs/ARCH.md §5`.

## 3. Design Choice

- **ONNX Runtime thay vì checkpoint `.pt`**: chạy weight không cần kéo torch + không đụng code inference
  GPL của repo gốc. Toàn bộ letterbox / giải mã YOLO / NMS / clamp bbox tự viết trong `app/services/detect/`.
- **Detector chỉ trả kết quả thô**: `conf_threshold` KHÔNG lọc trong `CTDDetector`; việc gắn
  `low_confidence` / `overlap_suspect` nằm ở Celery task. Giữ detector làm đúng 1 việc, dễ test.
- **Sàn nhiễu riêng `CTD_RAW_MIN_CONF=0.25`**, tách khỏi `CTD_CONF_THRESHOLD=0.5`: YOLO head trả 64.512 box
  mỗi ảnh, cần sàn để NMS chạy được — nhưng sàn phải **thấp hơn** ngưỡng low_confidence, nếu không
  region điểm thấp sẽ bị vứt trước khi kịp gắn cờ (đúng cái guardrail của spec).
- **`overlap_ratio` = giao / diện tích box NHỎ hơn** (không dùng IoU): case cần cảnh báo là "box này nằm
  gần trọn trong box kia" — IoU sẽ đánh giá thấp khi 2 box lệch nhiều về kích thước.
- **Session sync riêng cho worker** (`app/core/db_sync.py`): app HTTP dùng async, Celery chạy đồng bộ —
  không nhét event loop vào worker.
- **Model nạp 1 lần/process** (`--concurrency=1`): weight 91MB, nạp lại mỗi ảnh sẽ giết hiệu năng.
- **API không bao giờ nạp model**: import detector đều là import trễ; `models/` chỉ mount vào service `worker`,
  không mount vào `api`. Có test canh điều này.

## 4. Changed Files

```
backend/app/services/detect/__init__.py      (mới)
backend/app/services/detect/geometry.py      (mới) build_bbox/clamp, overlap_ratio, mark_overlap_suspects, nms
backend/app/services/detect/ctd.py           (mới) CTDDetector + DetectedRegion + ModelWeightsMissing
backend/app/services/dispatch.py             (mới) enqueue job, broker chết thì ghi error_log
backend/app/core/db_sync.py                  (mới) session đồng bộ cho worker
backend/app/workers/tasks.py                 (mới) task detect.run_detect_job
backend/app/core/config.py                   (sửa) 9 tham số M2, đọc từ .env
backend/app/workers/celery_app.py            (sửa) include app.workers.tasks
backend/app/api/v1/routes.py                 (sửa) enqueue sau upload + POST /pages/{id}/retry-detect
backend/requirements.txt                     (sửa) onnxruntime, numpy, Pillow
backend/test_fixtures/{make_fixtures.py, many_bubbles.png, few_bubbles.png, loose_sfx.png}  (mới)
backend/tests/{test_detect_geometry_unit,test_detect_ctd_unit,test_detect_task_integration,
               test_detect_real_model}.py    (mới)
backend/tests/{conftest.py,test_no_ai_logic.py} (sửa) fixture detector giả + guardrail mở rộng cho M2
docker-compose.yml · .env.example · .env · .gitignore   (sửa) mount ./models, tham số M2, chặn commit weight
docs/{ARCH.md,API.md,FEATURES.md,TEST_LOG.md,PLAN.md}   (sửa) · docs/REPORT_M2.md (mới)
```

**DB migration: KHÔNG có.** M2 chỉ ghi vào cột đã tồn tại từ M1.

## 5. New API / DB / State

- **API mới:** `POST /api/v1/pages/{id}/retry-detect` → 202 (endpoint *optional* của spec — **có implement**,
  vì luồng `detection_failed` và việc chỉnh tham số rồi chạy lại cần nó; 409 nếu page đang `detecting`).
- **API đổi hành vi:** `POST /projects/{id}/pages` nay enqueue job thật; `GET /pages/{id}/regions` trả dữ liệu thật.
- **DB:** không đổi schema. Ghi dữ liệu vào `text_region` (+ `page.status`, `job.status/error_log`).
- **State:** dùng đúng `assert_transition` của M1; `detected → detecting` (chạy lại) là cạnh đã khai báo sẵn ở M1.

### Lệch/bổ sung so với spec — khai rõ

1. **`CTDDetector.detect_regions()`** (mới) trả `DetectedRegion(bbox, confidence, cls)`.
   Lý do: `IDetector.detect()` chốt ở M1 trả `list[BBox]`, mà `BBox` **không có chỗ chứa confidence** —
   trong khi M2 bắt buộc phải ghi confidence vào DB. Cách xử lý: **giữ nguyên Protocol M1**
   (`detect()` vẫn tồn tại, vẫn đúng signature) và bổ sung method giàu thông tin hơn. Không đổi tên, không xoá gì.
2. **Sàn `CTD_RAW_MIN_CONF`** không có trong spec — thêm vì lý do kỹ thuật ở §3. Mặc định 0.25 < 0.5.
3. **`DETECT_TIMEOUT_SECONDS` trong `.env` đặt 120s** (mặc định trong code vẫn 60s như spec).
   Lý do: đo thật ~40s/ảnh trên CPU này; để 60s là mời timeout oan. Số đo trong `TEST_LOG.md`.
4. **Hành vi khi broker chết**: upload vẫn 202, job đứng `queued` + `error_log=enqueue_failed: …`.
   Spec không nói tới case này; chọn "ghi rõ, không giả vờ đã gửi".
5. **Không mount `models/` vào service `api`** — cố ý, để tiến trình API không thể chạm model.

## 6. Tests

84 pass + 3 skip (model thật, bật bằng `MTE_RUN_MODEL_TESTS=1`). Phân nhóm và các bài đáng chú ý:
xem `docs/TEST_LOG.md § M2`. Giữ truyền thống guardrail của M1, nay có **5 test guardrail**.

## 7. Live Verification

Chạy thật qua Redis + worker + ONNX (không mock): **6/6, 2/2, 4/4** vùng chữ khớp đếm tay trên 3 fixture,
**0 bbox âm hoặc vượt kích thước ảnh**, ~40s/ảnh, retry không nhân đôi region (6 → vẫn 6, id đổi,
log ghi "xóa 6 region cũ"). Số liệu chi tiết + toạ độ từng region: `docs/TEST_LOG.md § M2`.

## 8. Success Criteria — đối chiếu thẳng

| Tiêu chí M2 §8 | Kết quả |
|---|---|
| Detect đúng ≥90% bubble có chữ thật, đối chiếu đếm tay | ⚠️ **CHƯA NGHIỆM THU trên manga thật.** Trên 3 ảnh tổng hợp: 12/12 = 100%, nhưng đó không phải manga scan. Chặn: chưa có bộ ảnh license rõ |
| Không có region bbox âm hoặc vượt kích thước ảnh | ✅ Đạt — 0 vi phạm live + có test biên |
| Page không kẹt ở `detecting` quá timeout | ✅ Đạt — task có soft/hard limit, test timeout ghi đúng `failed`/`detection_failed` |
| Retry không tạo region trùng lặp | ✅ Đạt — regression test + chạy lại thật |
| Upload page (M1) vẫn trả 202 tức thời | ✅ Đạt — test cắm detector ngủ 5s, upload vẫn < 2s |
| `ARCH.md` ghi rõ nguồn weight + license | ✅ Đạt — `docs/ARCH.md §5`, gồm cả mâu thuẫn license Apache/GPL |

**Cần bạn cấp để đóng tiêu chí đầu tiên:** bộ ảnh manga có license rõ (Manga109-s trên Hugging Face đang
`gated` — tải không token trả HTTP 401; Roboflow cần API key). Có ảnh là chạy lại đúng bài đo này,
chỉ mất ~40s/ảnh, không phải sửa code.

## 9. Remaining Limits / Follow-ups

- Chưa đo trên manga thật (mục §8 ở trên) — **việc còn treo duy nhất của M2**.
- Chưa xử lý ảnh xoay/nghiêng, scan kém — cần mini-spec hardening riêng nếu tỷ lệ miss cao trên ảnh thật.
- Chưa auto-retry khi timeout (chỉ ghi `detection_failed`, phải gọi retry tay) — thuộc M9.
- Chưa có UI vẽ overlay box — thuộc M7.
- Storage vẫn là volume local; `SupabaseStorageAdapter` vẫn là nợ kỹ thuật đã tracked trong `ARCH.md`.
- Chưa dùng 2 output còn lại của model (`seg` mask, `det` line map) — M4 (inpaint) nhiều khả năng cần `seg`.
- Chạy CPU ~40s/ảnh; muốn nhanh thì đổi `CTD_DEVICE=cuda` + image có CUDA (follow-up, không làm ở M2).

**Mini-spec kế tiếp:** M3 — OCR Extraction (`manga_ocr` cho `ja`, PaddleOCR cho `zh`/`en`), crop theo
`TextRegion.bbox` đã có từ M2.
