# Worker AI — build từ GỐC repo (không phải từ `backend/`) vì cần cả `backend/`, `fonts/`
# và model weight. Nền tảng hosting build một Dockerfile cho mỗi thư mục, nên:
#   thư mục gốc  -> worker  (file này)
#   backend/     -> api     (backend/Dockerfile, stage cuối là `api`)
#   frontend/    -> giao diện
FROM python:3.12-slim AS worker

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq5 curl libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# torch + torchvision bản CPU trước, để manga-ocr không kéo bản CUDA từ PyPI.
# torchvision là BẮT BUỘC về mặt tốc độ: thiếu nó, transformers lùi về bộ tiền xử lý ảnh PIL
# và manga-ocr chạy 55,8s/ảnh thay vì 8,8s (đo thật, xem docs/TEST_LOG.md § M3).
RUN pip install --no-cache-dir --timeout 300 --retries 10 \
        --index-url https://download.pytorch.org/whl/cpu torch torchvision

COPY backend/requirements-worker.txt .
RUN pip install --no-cache-dir --timeout 300 --retries 10 -r requirements-worker.txt

# Model weight KHÔNG nằm trong git (289MB, xem .gitignore) -> tải lúc build.
# Ghim theo repo + tên file; đổi nguồn phải cập nhật cả docs/ARCH.md.
RUN mkdir -p /models \
    && curl -fL --retry 5 -o /models/comic-text-detector.onnx \
       https://huggingface.co/mayocream/comic-text-detector-onnx/resolve/main/comic-text-detector.onnx \
    && curl -fL --retry 5 -o /models/lama-manga-dynamic.onnx \
       https://huggingface.co/ogkalu/lama-manga-onnx-dynamic/resolve/main/lama-manga-dynamic.onnx

# Font chèn chữ (SIL OFL, có trong git) — chỉ worker cần.
COPY fonts /fonts
COPY backend /app

# Model OCR tải lúc chạy (manga-ocr ~440MB, PaddleOCR ~20MB) -> cache lại để lần sau không tải nữa.
ENV HF_HOME=/model-cache/hf \
    PADDLE_PDX_CACHE_HOME=/model-cache/paddle \
    FONT_DIR=/fonts \
    CTD_WEIGHTS_PATH=/models/comic-text-detector.onnx \
    INPAINT_WEIGHTS_PATH=/models/lama-manga-dynamic.onnx

CMD ["celery", "-A", "app.workers.celery_app.celery_app", "worker", "-l", "info", "-Q", "celery", "--concurrency=1"]
