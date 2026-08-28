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

# ---------- stage api: NHẸ, không có thư viện AI (docker-compose máy nhà dùng stage này) ----------
FROM base AS api

# Chạy migration rồi mới phục vụ. Không dùng --reload khi chạy thật.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]

# ---------- stage app: API + worker CHUNG một container. Stage CUỐI có chủ đích ----------
# `docker build` không có --target lấy stage cuối, và nền tảng hosting CHỈ nhận thư mục con
# `backend` hoặc `frontend` làm gốc build — nên bản chạy thật phải nằm ở đây.
# Vì sao gộp: 7 endpoint của API phục vụ file do worker ghi ra, mà mỗi website trên hosting là
# một container ĐĨA RIÊNG. Tách ra là mọi ảnh và file xuất đều 404. Xem deploy-start.sh.
FROM worker AS app

# Model weight KHÔNG nằm trong git (289MB) -> tải lúc build.
RUN mkdir -p /models \
    && curl -fL --retry 5 -o /models/comic-text-detector.onnx \
       https://huggingface.co/mayocream/comic-text-detector-onnx/resolve/main/comic-text-detector.onnx \
    && curl -fL --retry 5 -o /models/lama-manga-dynamic.onnx \
       https://huggingface.co/ogkalu/lama-manga-onnx-dynamic/resolve/main/lama-manga-dynamic.onnx

# Font chèn chữ (SIL OFL, có trong git).
COPY fonts /fonts
COPY deploy-start.sh /usr/local/bin/deploy-start.sh
RUN chmod +x /usr/local/bin/deploy-start.sh

ENV FONT_DIR=/fonts \
    CTD_WEIGHTS_PATH=/models/comic-text-detector.onnx \
    INPAINT_WEIGHTS_PATH=/models/lama-manga-dynamic.onnx

EXPOSE 8000
CMD ["/usr/local/bin/deploy-start.sh"]
