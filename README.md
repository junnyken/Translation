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

docker compose up -d db redis   # hạ tầng
docker compose up -d api worker # API (tự chạy migration) + worker chạy detect
# Swagger: http://localhost:8010/docs
```

Thử nhanh: tạo project → `POST /projects/{id}/pages` (upload 1 trang) → pipeline tự chạy
detect rồi OCR (~1-2 phút trên CPU) → `GET /pages/{id}/regions` xem khung chữ,
`GET /pages/{id}/ocr` xem chữ đọc được, `GET /pages/{id}/clean-image` xem ảnh đã xoá chữ.

Image `worker` nặng ~4,5GB (torch CPU + manga-ocr + PaddleOCR); image `api` giữ 1,06GB vì
**không** chứa thư viện AI. Lần chạy đầu worker tải model OCR (~460MB) vào volume `model_cache`.

Cổng mặc định (đổi trong `.env`): API `8010`, Postgres `5433`, Redis `6380`.

## Chạy test

```bash
docker compose up -d db
cd backend
python3 -m venv ../.venv && ../.venv/bin/pip install -r requirements-dev.txt
../.venv/bin/python -m pytest          # 192 test: unit + integration + migration
MTE_RUN_MODEL_TESTS=1 ../.venv/bin/python -m pytest tests/test_detect_real_model.py  # ONNX thật (~40-60s/ảnh)
# Engine OCR thật phải chạy trong container worker:
docker compose exec worker sh -c "MTE_RUN_OCR_TESTS=1 python -m pytest tests/test_ocr_real_engine.py -q"
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
| [M1](docs/REPORT_M1.md) · [M2](docs/REPORT_M2.md) · [M3](docs/REPORT_M3.md) · [M4](docs/REPORT_M4.md) | Báo cáo bàn giao từng mini-spec |

## Bản quyền nội dung

Tool phục vụ dịch cho mục đích cá nhân/học tập. Mỗi project phải khai `intended_use`;
người dùng chịu trách nhiệm về bản quyền nội dung nguồn mình đưa vào (guardrail đầy đủ ở M10).
