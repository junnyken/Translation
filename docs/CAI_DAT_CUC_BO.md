# Cài Translation trên máy của bạn (Docker, có hoặc không có GPU)

Tài liệu cho người tự cài Translation lên máy cá nhân. Bản chạy thật trên hosting **không** dùng
các tệp ở đây.

## 1. Cần có

| Thứ | Máy không GPU | Máy có GPU NVIDIA |
|---|---|---|
| Docker | Docker Desktop (Windows/macOS) hoặc Docker Engine (Linux) | như bên trái |
| GPU | — | Driver NVIDIA mới. Linux cần thêm **NVIDIA Container Toolkit**; Windows dùng Docker Desktop + WSL2 và bật GPU |
| RAM | ≥ 8 GB | ≥ 16 GB |
| VRAM | — | ≥ 8 GB cho SDXL (mặc định). FLUX.1 cần ≥ 16 GB |
| Đĩa trống | ~10 GB | ~25 GB (image GPU ~8 GB + model SDXL ~7 GB tải lần đầu) |

Kiểm GPU đã vào được Docker chưa:

```bash
docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu24.04 nvidia-smi
```

Lệnh in ra bảng GPU là được. Báo lỗi thì xử lý driver hoặc Container Toolkit trước, đừng đi tiếp.

## 2. Tải mã và model

```bash
git clone <repo> translation && cd translation
cp .env.example .env

mkdir -p models
curl -L -o models/comic-text-detector.onnx \
  https://huggingface.co/mayocream/comic-text-detector-onnx/resolve/main/comic-text-detector.onnx
curl -L -o models/lama-manga-dynamic.onnx \
  https://huggingface.co/ogkalu/lama-manga-onnx-dynamic/resolve/main/lama-manga-dynamic.onnx
```

## 3. Chọn cách dịch (sửa `.env`)

**a) LLM chạy trên máy — miễn phí, không cần mạng.** Cài [Ollama](https://ollama.com), tải một model
rồi khai:

```bash
ollama pull qwen3:14b          # hoặc gemma3:12b (đọc được ảnh)
```

```ini
TRANSLATE_DEFAULT_ENGINE=local_llm
LOCAL_LLM_BASE_URL=http://host.docker.internal:11434/v1
LOCAL_LLM_MODEL=qwen3:14b
# Model đọc được ảnh (gemma3, qwen2.5-vl…) thì bật để gửi kèm ảnh trang:
# LOCAL_LLM_VISION=true
```

Dùng LM Studio thì đổi cổng thành `1234`, dùng `llama-server` (llama.cpp) thì `8080`.

**b) API chính thức của OpenAI — tính tiền theo lượt.** Cũng qua engine `local_llm`:

```ini
TRANSLATE_DEFAULT_ENGINE=local_llm
LOCAL_LLM_BASE_URL=https://api.openai.com/v1
LOCAL_LLM_API_KEY=sk-...
LOCAL_LLM_MODEL=<tên model trong tài khoản OpenAI của bạn>
```

⚠️ Cách này **tốn tiền mỗi trang** và không qua cổng giới hạn nhịp gọi. Chỉ dùng trên máy của chính
người trả tiền.

**c) Gemini**: `TRANSLATE_DEFAULT_ENGINE=llm_context` + `GEMINI_API_KEYS=...`

**d) Miễn phí, không cần gì**: `TRANSLATE_DEFAULT_ENGINE=google_fast` (mặc định)

Cách (a), (b), (c) lỗi (máy chủ LLM chưa bật, hết hạn mức…) thì trang tự lùi về `google_fast` và được
đánh dấu "đã dùng đường dự phòng". Trang không bị hỏng.

## 4. Chạy

**Máy không GPU** (xoá chữ bằng LaMa trên CPU):

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

**Máy có GPU** (xoá chữ bằng SDXL, vẽ lại được cả nét vẽ dưới chữ):

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.gpu.yml up -d --build
```

Driver NVIDIA đời mới có thể dùng bản CUDA 13: `TORCH_CUDA=cu130 docker compose … up -d --build`.

Mở **http://localhost:5174**. Tài liệu API ở http://localhost:8010/docs.

Lần đầu xoá chữ bằng SDXL, máy tải model (~7 GB) vào volume `model_cache`. Các lần sau dùng lại bản
đã tải.

### Đổi model xoá chữ (tuỳ chọn)

```ini
# FLUX.1-schnell — giấy phép Apache-2.0, cần ≥16 GB VRAM
INPAINT_KT_MODEL=black-forest-labs/FLUX.1-schnell
INPAINT_KT_STEPS=4
INPAINT_KT_GUIDANCE=0
```

Không dùng được **FLUX.2-klein**: thư viện diffusers chưa có bản xoá vùng cho nó. Không dùng
**FLUX.1-dev** cho việc thương mại: giấy phép cấm.

## 5. Bật lại, xem log, dừng

```
Stack: translation
Bật lại:  docker compose -f deploy/docker-compose.yml [-f deploy/docker-compose.gpu.yml] -p translation up -d
Xem log:  docker compose -f deploy/docker-compose.yml -p translation logs -f --tail=100 worker
Dừng:     docker compose -f deploy/docker-compose.yml -p translation stop     # KHÔNG dùng `down -v` — mất dữ liệu
```

Lệnh bật lại phải kèm đúng các tệp `-f` đã dùng lúc cài. Bỏ `docker-compose.gpu.yml` khi bật lại thì
worker quay về LaMa.

## 6. Khi có lỗi

| Thông báo trên trang | Nghĩa | Làm gì |
|---|---|---|
| `khuech_tan_khong_co_gpu` | Worker không thấy GPU | Chạy lệnh kiểm ở mục 1; nhớ có `-f deploy/docker-compose.gpu.yml` |
| `khuech_tan_thieu_thu_vien` | Worker đang chạy image CPU | Build lại với tệp GPU (mục 4) |
| `khuech_tan_loi_suy_dien … out of memory` | Thiếu VRAM | Giảm `INPAINT_KT_MAX_SIDE=768`, hoặc đổi về SDXL |
| Dịch ra "đã dùng đường dự phòng" | Máy chủ LLM chưa bật hoặc sai địa chỉ | `ollama serve`; kiểm `LOCAL_LLM_BASE_URL` |
