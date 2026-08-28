# Translation — Tool dịch manga EN/JP/CN → Tiếng Việt

Nhận diện khung chữ (bubble/box) → xóa chữ gốc → dịch theo mạch văn → tự canh cỡ chữ cho vừa khung →
sửa tay khi cần → xuất chapter.

**Trạng thái: M4 xong** — tự nhận diện khung chữ, đọc chữ, **và xoá chữ gốc khỏi ảnh**; chưa dịch.
Xem [docs/FEATURES.md](docs/FEATURES.md) để biết chính xác cái gì dùng được, cái gì chưa.

## Stack

FastAPI + SQLAlchemy 2.0 (async) + Alembic · Postgres (local hoặc Supabase) · Redis + Celery · Docker Compose.

## Chạy nhanh

```bash
cp .env.example .env            # sửa DATABASE_URL nếu dùng Supabase

# Model (KHÔNG nằm trong git): nhận diện khung chữ 91MB + xoá chữ 197MB
mkdir -p models
curl -L -o models/comic-text-detector.onnx \
  https://huggingface.co/mayocream/comic-text-detector-onnx/resolve/main/comic-text-detector.onnx
curl -L -o models/lama-manga-dynamic.onnx \
  https://huggingface.co/ogkalu/lama-manga-onnx-dynamic/resolve/main/lama-manga-dynamic.onnx

docker compose -f deploy/docker-compose.yml up -d db redis      # hạ tầng
docker compose -f deploy/docker-compose.yml up -d api worker    # API (tự chạy migration) + worker chạy pipeline
docker compose -f deploy/docker-compose.yml up -d frontend      # màn sửa tay (M7)
# Swagger:      http://localhost:8010/docs
# Màn sửa tay:  http://localhost:5174
```

Font chèn chữ nằm sẵn trong `fonts/` (SIL OFL, đã đo đủ 134 ký tự có dấu tiếng Việt —
xem `docs/FONTS.md`), được mount vào worker qua `FONT_DIR`.

Thử nhanh: tạo project → `POST /projects/{id}/pages` (upload 1 trang) → pipeline tự chạy một mạch
detect → OCR → xoá chữ → dịch → canh chữ (~2-3 phút trên CPU) → mở
`http://localhost:5174/#page=<page_id>` để xem trang đã chèn bản dịch và **sửa tay** những chỗ chưa đạt.

Xem bằng API: `GET /pages/{id}/regions` (khung chữ) · `/ocr` (chữ gốc) · `/translation` (bản dịch) ·
`/typeset` (cỡ chữ + cảnh báo tràn khung) · `/clean-image`, `/typeset-preview` (ảnh).

Xong thì **xuất cả chapter**: mở `http://localhost:5174/#project=<project_id>` → xem trước cảnh báo →
chọn CBZ/ZIP/PNG → tải về. Hoặc qua API: `POST /projects/{id}/export` → `GET /export-jobs/{id}` →
`GET /export-jobs/{id}/download`.

Image `worker` nặng ~4,5GB (torch CPU + manga-ocr + PaddleOCR); image `api` giữ 1,06GB vì
**không** chứa thư viện AI. Lần chạy đầu worker tải model OCR (~460MB) vào volume `model_cache`.

> `docker-compose.yml` nằm ở `deploy/` chứ không phải gốc repo: nền tảng hosting quét gốc, thấy
> file compose là từ chối build với lỗi *"compose: chưa hỗ trợ deploy stack"*.

Cổng mặc định (đổi trong `.env`): API `8010`, màn sửa tay `5174`, Postgres `5433`, Redis `6380`.

## Chạy test

```bash
docker compose -f deploy/docker-compose.yml up -d db
cd backend
python3 -m venv ../.venv && ../.venv/bin/pip install -r requirements-dev.txt
../.venv/bin/python -m pytest          # 421 test: unit + integration + migration + guardrail
MTE_RUN_MODEL_TESTS=1 ../.venv/bin/python -m pytest tests/test_detect_real_model.py  # ONNX thật (~40-60s/ảnh)
# Engine OCR thật phải chạy trong container worker:
docker compose -f deploy/docker-compose.yml exec worker sh -c "MTE_RUN_OCR_TESTS=1 python -m pytest tests/test_ocr_real_engine.py -q"
```
Test dùng **Postgres thật** (DB `translation_test`), không mock.

## Tài liệu

| File | Nội dung |
|---|---|
| [docs/ARCH.md](docs/ARCH.md) | Kiến trúc, data model, quy tắc bất di bất dịch của Phase |
| [docs/API.md](docs/API.md) | Hợp đồng API `/api/v1` + bảng enum |
| [docs/FEATURES.md](docs/FEATURES.md) | Tính năng theo mini-spec, trạng thái thật |
| [docs/PLAN.md](docs/PLAN.md) | Kế hoạch xây dựng M1 → M10 |
| [docs/TEST_LOG.md](docs/TEST_LOG.md) | Nhật ký test, số liệu thật |
| [M1](docs/REPORT_M1.md) · [M2](docs/REPORT_M2.md) · [M3](docs/REPORT_M3.md) · [M4](docs/REPORT_M4.md) · [M5](docs/REPORT_M5.md) · [M6](docs/REPORT_M6.md) · [M7](docs/REPORT_M7.md) · [M8](docs/REPORT_M8.md) · [M9](docs/REPORT_M9.md) | Báo cáo bàn giao từng mini-spec |

## Bản quyền nội dung

Tool phục vụ dịch cho mục đích cá nhân/học tập. Mỗi project phải khai `intended_use`;
người dùng chịu trách nhiệm về bản quyền nội dung nguồn mình đưa vào (guardrail đầy đủ ở M10).
