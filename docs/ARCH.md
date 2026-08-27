# ARCH.md — Translation (Phase MTE: Manga Translation Extension)

> Trạng thái: **M1 hoàn tất** (data model + API contract + interface engine).
> Chưa có logic AI thật — detect/OCR/inpaint/translate/typeset thuộc M2–M6.

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
| Storage | Volume local (`LocalObjectStorage`) | Adapter Supabase Storage **chưa implement** — xem §5 |

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

## 5. Giới hạn đã biết ở M1 (cố ý để lại)

- **Supabase Storage chưa có adapter.** M1 chạy `STORAGE_BACKEND=local` (đã verify thật).
  Khi đặt `STORAGE_BACKEND=supabase`, app **fail ngay** với thông báo rõ ràng thay vì im lặng ghi sai chỗ.
  Nối Supabase Storage cần credential thật → làm khi có key (ưu tiên trước M4 vì M4 sinh thêm ảnh clean).
- **Chưa dispatch Celery task**: upload page tạo `Job(type=detect, status=queued)` trong DB, chưa gửi lên broker.
  M2 sẽ bind task thật vào đúng record này.
- **Chưa có auth/user management** — nếu cần multi-user phải là mini-spec riêng, không nhét vào MTE.
