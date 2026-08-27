# Translation — Tool dịch manga EN/JP/CN → Tiếng Việt

Nhận diện khung chữ (bubble/box) → xóa chữ gốc → dịch theo mạch văn → tự canh cỡ chữ cho vừa khung →
sửa tay khi cần → xuất chapter.

**Trạng thái: M2 xong** — đã tự nhận diện được khung chữ trên trang truyện; chưa đọc/dịch chữ.
Xem [docs/FEATURES.md](docs/FEATURES.md) để biết chính xác cái gì dùng được, cái gì chưa.

## Stack

FastAPI + SQLAlchemy 2.0 (async) + Alembic · Postgres (local hoặc Supabase) · Redis + Celery · Docker Compose.

## Chạy nhanh

```bash
cp .env.example .env            # sửa DATABASE_URL nếu dùng Supabase

# Model nhận diện khung chữ (91MB, KHÔNG nằm trong git)
mkdir -p models && curl -L -o models/comic-text-detector.onnx \
  https://huggingface.co/mayocream/comic-text-detector-onnx/resolve/main/comic-text-detector.onnx

docker compose up -d db redis   # hạ tầng
docker compose up -d api worker # API (tự chạy migration) + worker chạy detect
# Swagger: http://localhost:8010/docs
```

Thử nhanh: tạo project → `POST /projects/{id}/pages` (upload 1 trang) → đợi ~40s (CPU) →
`GET /pages/{id}/regions` để xem khung chữ đã nhận diện.

Cổng mặc định (đổi trong `.env`): API `8010`, Postgres `5433`, Redis `6380`.

## Chạy test

```bash
docker compose up -d db
cd backend
python3 -m venv ../.venv && ../.venv/bin/pip install -r requirements-dev.txt
../.venv/bin/python -m pytest          # 84 test: unit + integration + migration
MTE_RUN_MODEL_TESTS=1 ../.venv/bin/python -m pytest tests/test_detect_real_model.py  # chạy ONNX thật (~40s/ảnh)
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
| [docs/REPORT_M1.md](docs/REPORT_M1.md) · [REPORT_M2.md](docs/REPORT_M2.md) | Báo cáo bàn giao từng mini-spec |

## Bản quyền nội dung

Tool phục vụ dịch cho mục đích cá nhân/học tập. Mỗi project phải khai `intended_use`;
người dùng chịu trách nhiệm về bản quyền nội dung nguồn mình đưa vào (guardrail đầy đủ ở M10).
