# ARCH.md — Translation (Phase MTE: Manga Translation Extension)

> Trạng thái: **M2 hoàn tất** (M1: data model + contract · M2: nhận diện khung chữ chạy thật trong worker).
> Chưa có OCR/inpaint/translate/typeset — thuộc M3–M6.

## 1. Bức tranh tổng thể

```
       upload ảnh                 job queue (Redis/Celery)
Client ──────────► FastAPI (api) ──────────────────────────► Worker(s)
                      │                                        │
                      │  SQLAlchemy 2.0 async                  │ M2 detect  (comic-text-detector)
                      ▼                                        │ M3 ocr     (manga-ocr / PaddleOCR)
                 Postgres (Supabase)  ◄──────────────────────► │ M4 inpaint (LaMa)
                      │                                        │ M5 translate (Google fast / LLM context)
                      ▼                                        │ M6 typeset (Pillow font-metrics)
              Storage ảnh (local volume ở M1)                  │ M8 export  (PNG/CBZ)
```

Quy tắc kiến trúc **giữ nguyên xuyên suốt Phase** (M1 chốt, M2–M10 không được vi phạm):

1. **Không nhúng code GPL** (BallonsTranslator / Koharu). Chỉ dùng model weight độc lập
   (comic-text-detector, manga-ocr, PaddleOCR, LaMa) qua interface riêng trong `app/services/interfaces.py`.
2. **Mỗi bước pipeline là service riêng**, test độc lập được, nối với nhau bằng job queue.
   Tuyệt đối không viết 1 hàm monolith chạy end-to-end.
3. **Evidence-first**: bước chưa chạy → field kết quả `NULL`; bước fail/confidence thấp →
   `detection_failed` / `low_confidence` / `needs_manual` / `overflow_warning`. Không bao giờ mặc định "done".
4. **Không xử lý AI đồng bộ trong HTTP request**. Endpoint kích hoạt AI trả `202 Accepted` + `job_id`.
5. **API versioned**: mọi route dưới `/api/v1/`.

## 2. Thành phần

| Thành phần | Công nghệ | Ghi chú |
|---|---|---|
| API | FastAPI 0.115 + Pydantic v2 | Swagger tự sinh tại `/docs` |
| ORM | SQLAlchemy 2.0 (async, asyncpg) | Không trả ORM object ra API — luôn qua Pydantic schema |
| Migration | Alembic (driver sync `psycopg`) | Đã test 2 chiều `upgrade head` / `downgrade base` |
| DB | Postgres 16 (local) hoặc Supabase managed | Đổi bằng `DATABASE_URL`, không sửa code |
| Queue | Redis + Celery | M1 chỉ ghi record `Job`; task Celery thật bắt đầu ở M2 |
| Storage | Volume local (`LocalObjectStorage`) | Adapter Supabase Storage **chưa implement** — xem §6 (nợ kỹ thuật) |
| Detector (M2) | comic-text-detector qua ONNX Runtime (CPU) | Chỉ chạy trong worker; tiến trình API không nạp model |

## 3. Data model (7 bảng, chốt ở M1)

```
Project 1─n Page 1─n TextRegion 1─1 OCRResult
                     │            1─1 TranslationResult
                     │            1─1 TypesetResult
            1─n Job
```

- `Project`: `source_lang(ja|zh|en)`, `target_lang(vi)`, `intended_use(personal|study|other)` —
  `intended_use` tạo sẵn từ M1 để M10 không phải migrate thêm cột.
- `Page.status`: state machine chính, khai báo **đủ 10 giá trị ngay ở M1**
  (`queued → detecting → detected/detection_failed → ocr_done → inpainted/inpaint_needs_review →
  translated → typeset_done → ready_for_export`) để tránh `ALTER TYPE` enum nhiều lần trên Postgres.
  Cạnh hợp lệ khai báo trong `PAGE_STATUS_TRANSITIONS` (`app/models/enums.py`) + helper `assert_transition`.
- `TextRegion`: `bbox_x/y/w/h` (pixel, gốc trên-trái), `confidence` NULL cho tới M2,
  `overlap_suspect` (cờ của M2), `reading_order` NULL cho tới M5.
- 3 bảng kết quả (`OCRResult`, `TranslationResult`, `TypesetResult`) đều `unique(region_id)`
  → rerun job là **idempotent theo region**, không sinh bản ghi trùng.
- `Job`: `type(detect|ocr|inpaint|translate|typeset|export)` khai báo đủ enum cho cả Phase từ M1;
  `retry_count` là placeholder của M9.
- **Chưa tạo** `APIKeyPool` (M5/M9) và `ExportJob` (M8) — đúng nguyên tắc chỉ tạo đủ cho mini-spec hiện tại.

## 4. Interface engine (contract cho M2–M6)

`app/services/interfaces.py` khai báo `BBox` + 5 Protocol: `IDetector.detect`, `IOCREngine.recognize`,
`IInpainter.inpaint`, `ITranslator.translate`, `ITypesetter.fit`.
Kèm 5 stub `Unimplemented*` — **ném `NotImplementedError` kèm tên mini-spec phụ trách**, không trả kết quả giả.
Implementation thật (M2–M6) phải giữ nguyên tên method để không phải sửa lại contract DB/API.

**M2 — `CTDDetector`:** implement đúng `IDetector.detect(image_path) -> list[BBox]`. Vì `BBox` không
có chỗ chứa confidence, M2 **bổ sung** `detect_regions()` trả `DetectedRegion(bbox, confidence, cls)`;
Protocol M1 giữ nguyên, không đổi tên method nào. Detector **không tự lọc** theo `conf_threshold` —
lọc/gắn cờ là việc của Celery task, để detector chỉ làm đúng 1 việc: trả kết quả thô.


## 5. Model weight (M2)

| Mục | Giá trị |
|---|---|
| Model | comic-text-detector (dmMaze) — YOLOv5 head + UNet mask + DBNet line |
| File dùng | `comic-text-detector.onnx` (~91 MB) |
| Nguồn tải | `https://huggingface.co/mayocream/comic-text-detector-onnx` (file `comic-text-detector.onnx`) |
| SHA-256 | `1a86ace74961413cbd650002e7bb4dcec4980ffa21b2f19b86933372071d718f` |
| License ghi trên HF card | `apache-2.0` |
| License repo gốc (dmMaze/comic-text-detector) | **GPL-3.0** |

**Xử lý mâu thuẫn license:** HF card của bản ONNX ghi `apache-2.0` nhưng repo gốc sinh ra weight này là
GPL-3.0 (bản convert SafeTensors `mayocream/comic-text-detector` cũng ghi GPL-3.0). Vì không chắc bản ONNX
được relicense hợp lệ, dự án **áp theo điều kiện chặt hơn (GPL-3.0)**:

- Dùng cho **mục đích cá nhân/nội bộ**, không phân phối lại file weight kèm sản phẩm.
- **Không** dùng cho SaaS thương mại nếu chưa xin phép nguồn gốc.
- **Không** copy code inference của repo gốc vào codebase — chỉ nạp weight qua `onnxruntime`;
  toàn bộ tiền/hậu xử lý (letterbox, giải mã YOLO, NMS, clamp bbox) do dự án tự viết trong
  `app/services/detect/`. Đây là ranh giới giữ đúng guardrail "không nhúng code GPL" của M1.

Weight **không commit vào git** (`.gitignore`: `models/`, `*.onnx`, `*.pt`). Cách lấy:

```bash
mkdir -p models
curl -L -o models/comic-text-detector.onnx \
  https://huggingface.co/mayocream/comic-text-detector-onnx/resolve/main/comic-text-detector.onnx
# docker-compose mount ./models -> /models (chỉ cho service worker, api không cần)
```

### Đường đi của bước detect

```
POST /pages  ──►  lưu ảnh + Job(detect, queued)  ──►  Celery (Redis)
                        │ 202 ngay, không chờ            │
                        ▼                                ▼
                    client polling                 worker: CTDDetector.detect_regions()
                    GET /jobs/{id}                    letterbox 1024 → ONNX → NMS → clamp
                                                        │
                                                        ▼
                                          xóa region cũ của page (idempotent)
                                          ghi TextRegion + confidence + overlap_suspect
                                          Page: queued → detecting → detected | detection_failed
```

Tham số điều chỉnh được qua `.env` (không hard-code): `CTD_CONF_THRESHOLD` (0.5 — dưới ngưỡng là
`low_confidence`, **vẫn lưu**), `CTD_RAW_MIN_CONF` (0.25 — sàn nhiễu trước NMS), `CTD_NMS_IOU` (0.45),
`CTD_OVERLAP_SUSPECT_RATIO` (0.8), `CTD_INPUT_SIZE` (1024), `DETECT_TIMEOUT_SECONDS`.

## 6. Giới hạn đã biết (cố ý để lại)

- **Supabase Storage chưa có adapter.** M1 chạy `STORAGE_BACKEND=local` (đã verify thật).
  Khi đặt `STORAGE_BACKEND=supabase`, app **fail ngay** với thông báo rõ ràng thay vì im lặng ghi sai chỗ.
  Nối Supabase Storage cần credential thật → làm khi có key (ưu tiên trước M4 vì M4 sinh thêm ảnh clean).
- ~~Chưa dispatch Celery task~~ → **đã xong ở M2**: upload page enqueue `detect.run_detect_job`.
  Nếu broker chết, job đứng ở `queued` kèm `error_log=enqueue_failed:…` (không giả vờ đã gửi).
- **NỢ KỸ THUẬT (tracked):** `SupabaseStorageAdapter` chưa viết — cần khi có credential Supabase.
  Nên làm trước M4 vì M4 bắt đầu sinh thêm ảnh clean. Hiện `STORAGE_BACKEND=supabase` fail có thông báo rõ.
- **Chưa có OCR/inpaint/translate/typeset** — M3–M6.
- **M2 chưa xử lý** ảnh xoay/nghiêng, scan chất lượng kém; chưa auto-retry khi timeout (thuộc M9);
  chưa có UI vẽ overlay box (thuộc M7).
- **Chưa có auth/user management** — nếu cần multi-user phải là mini-spec riêng, không nhét vào MTE.
