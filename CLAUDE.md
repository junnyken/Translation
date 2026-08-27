# CLAUDE.md — Translation (Phase MTE)

## Nguyên tắc không được vi phạm (chốt ở M1)

1. **Không nhúng code GPL** (BallonsTranslator, Koharu) vào repo. Chỉ dùng model weight độc lập
   (comic-text-detector, manga-ocr, PaddleOCR, LaMa) qua interface trong `backend/app/services/interfaces.py`.
2. **Mỗi bước pipeline là service riêng**, test độc lập được, nối qua Celery. Không viết hàm monolith end-to-end.
3. **Evidence-first**: chưa chạy → `NULL`; fail/confidence thấp → `detection_failed` / `low_confidence` /
   `needs_manual` / `overflow_warning`. Không tự nhận "done" khi thiếu bằng chứng, không điền giá trị mặc định giả.
4. **Không chạy AI đồng bộ trong HTTP request** — trả `202 Accepted` + `job_id`.
5. **API luôn có prefix `/api/v1`**. Response luôn qua Pydantic schema.
6. **Không đổi tên field/enum/method đã chốt** ở `docs/API.md` và `interfaces.py`. Cần đổi → ghi rõ lý do trong báo cáo mini-spec.
7. **Chỉ tạo bảng đủ cho mini-spec hiện tại** (`APIKeyPool` ở M5, `ExportJob` ở M8 — chưa tạo trước).

## Làm việc theo mini-spec

- Thứ tự bắt buộc M1 → M2 → … → M6 (pipeline lõi). M7–M10 có thể đảo nhẹ theo ưu tiên.
- Mỗi mini-spec kết thúc bằng báo cáo `docs/REPORT_M<n>.md` theo đúng khung:
  Summary · Audit Before Build · Design Choice · Changed Files · New API/DB/State · Tests ·
  Live Verification · Remaining Limits.
- Cập nhật `docs/ARCH.md`, `docs/API.md`, `docs/FEATURES.md`, `docs/TEST_LOG.md` **trong cùng mini-spec đó**,
  không để dồn.
- Không mở mini-spec sau khi mini-spec trước chưa audit pass.

## Lệnh hay dùng

```bash
docker compose up -d db redis api worker
cd backend && ../.venv/bin/python -m pytest
cd backend && ../.venv/bin/alembic revision --autogenerate -m "M<n> ..."   # LUÔN đọc lại file gen ra
```
Migration Postgres: enum type **không** tự mất khi drop table → downgrade phải `DROP TYPE` tường minh
(xem `alembic/versions/0001_m1_initial_schema.py`).
