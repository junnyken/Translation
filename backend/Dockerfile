# ---------- stage base: dùng cho service `api` (nhẹ, KHÔNG có thư viện AI) ----------
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ---------- stage worker: base + engine OCR (M3) ----------
FROM base AS worker

# opencv (paddleocr kéo theo opencv-contrib-python) cần libGL/glib
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# torch + torchvision bản CPU trước, để manga-ocr không kéo bản CUDA từ PyPI.
# torchvision là BẮT BUỘC về mặt tốc độ: thiếu nó, transformers lùi về bộ tiền xử lý ảnh PIL
# và manga-ocr chạy 55,8s/ảnh thay vì 8,8s (đo thật, xem docs/TEST_LOG.md § M3).
RUN pip install --no-cache-dir --timeout 300 --retries 10 \
        --index-url https://download.pytorch.org/whl/cpu torch torchvision

COPY requirements-worker.txt .
RUN pip install --no-cache-dir --timeout 300 --retries 10 -r requirements-worker.txt

# Model tải lúc chạy (manga-ocr ~440MB từ HuggingFace, PaddleOCR ~20MB) -> cache vào volume
ENV HF_HOME=/model-cache/hf \
    PADDLE_PDX_CACHE_HOME=/model-cache/paddle

# ---------- stage api: NHẸ, không có thư viện AI. Đây là stage CUỐI CÙNG có chủ đích ----------
# `docker build` không có --target sẽ build stage cuối. Nền tảng hosting build thư mục `backend/`
# nên phải là stage nhẹ này (1,06 GB), KHÔNG phải stage worker (4,47 GB).
FROM base AS api

# Chạy migration rồi mới phục vụ. Không dùng --reload khi chạy thật.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
