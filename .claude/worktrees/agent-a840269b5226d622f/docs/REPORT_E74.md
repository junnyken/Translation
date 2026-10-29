# REPORT E74 — Xoá chữ bằng mô hình khuếch tán (SDXL / FLUX.1) + gói cài Docker có GPU

**Ngày:** 2026-10-15 · **Nguồn yêu cầu:** chủ dự án, tham khảo Koharu (`flux2-klein`, `rorem-mixed`)
và muốn "chạy cục bộ, cài local được" trên máy cá nhân có GPU.

## Summary

- Engine xoá chữ mới `INPAINT_ENGINE=khuech_tan`: SDXL inpainting (mặc định) hoặc FLUX.1 qua
  `diffusers`, chạy trên **GPU NVIDIA**. Mặc định vẫn là `lama`.
- Gói cài: stage Dockerfile `worker-gpu`, `deploy/docker-compose.gpu.yml`, hướng dẫn
  `docs/CAI_DAT_CUC_BO.md`.
- `BUILT`. **Chưa chạy trên GPU thật**: workspace không có GPU, và đĩa máy chủ dùng chung còn 7 GB nên
  KHÔNG build image GPU ở đây.

## Audit Before Build — đã kiểm bằng thư viện thật, không theo trí nhớ

Cài `diffusers==0.41.0` vào thư mục tạm, import cùng torch 2.14 + transformers 5.17 của worker:

- `StableDiffusionXLInpaintPipeline.__call__` nhận đủ 10 tham số mà engine truyền.
- `AutoPipelineForInpainting` nhận các họ SD/SDXL/SD3/**FLUX.1** (`FluxInpaintPipeline`)/Qwen-Image/
  Z-Image.
- **FLUX.2-klein (thứ Koharu dùng) KHÔNG xoá vùng được qua diffusers**: `Flux2KleinPipeline` không có
  `mask_image`. Koharu chạy nó qua stable-diffusion.cpp. ⇒ Đường FLUX ở đây là FLUX.1. FLUX.1-schnell
  có giấy phép Apache-2.0; FLUX.1-dev cấm dùng thương mại.
- Index PyTorch: `cu126` và `cu130` có torch 2.14.1; `cu128` chỉ tới 2.11 ⇒ mặc định `cu126`.

## Design Choice

Kế thừa `LamaInpainter` và chỉ thay bước gọi model + bước nạp model. Giữ nguyên mọi thứ đã kiểm chứng:
- tô phẳng E69 trước (vùng nền phẳng không chiếm GPU)
- chia cụm
- chỉ thay điểm ảnh trong mặt nạ
- không ghi đè ảnh gốc
- bước OCR kiểm lại

Khác LaMa ở ba chỗ:
- Luôn chạy theo cụm.
- Mỗi ô được thu về cạnh dài ≤1024 (cạnh ngắn nâng lên ~256 nhưng **không bao giờ** để cạnh dài vượt
  trần — ô dẹt 2000×100 suýt bị phóng thành 5120px), rồi làm tròn bội 16.
- Chỉ truyền tham số mà pipeline nhận: mỗi họ model có chữ ký riêng.

Thiếu GPU hoặc thư viện ⇒ `InpaintFailed` nói rõ thiếu gì. Không lặng lẽ lùi về LaMa: đúng nguyên tắc
`InpaintWeightsMissing` của M4.

## Lỗi bắt được trong lúc làm

1. **Stage Dockerfile.** Production build không có `--target` nên lấy stage CUỐI. Thêm `worker-gpu`
   vào cuối tệp là lượt deploy kế tiếp build nhầm image GPU. Đã chuyển lên trước `app`; bài canh
   `test_e74_dockerfile.py` khoá thứ tự này.
2. **`inspect.signature(pipe.__call__)`** trả `(*args, **kwargs)` khi pipeline là một hàm, nên bước
   lọc tham số bị bỏ qua. Đổi sang `inspect.signature(pipe)`. Test chữ ký hẹp bắt được lỗi này.

## Tests

- `test_e74_khuech_tan_unit.py`: 14 test, dùng `torch`/`diffusers` GIẢ. Kiểm:
  - cỡ đưa vào model (6 ca)
  - chỉ thay điểm ảnh trong mặt nạ và không ghi đè gốc
  - luôn chạy theo cụm
  - vùng nền phẳng không nạp model
  - lỗi rõ khi không có GPU, thiếu thư viện, CUDA hết bộ nhớ
  - chọn engine theo cấu hình
  - lọc tham số theo chữ ký
  
  **Đối chứng âm:** bỏ trần cạnh dài ⇒ ca 2000×100 đỏ; cho chạy cả trang ⇒ ca chia cụm đỏ.
- `test_e74_dockerfile.py`: 3 test thứ tự stage.
- Các bộ có sẵn của xoá chữ, migration, cấu hình: 182 passed.

Các test này **không** chứng minh chất lượng vẽ của SDXL.

## Remaining Limits

1. **Chưa chạy SDXL/FLUX thật lần nào.** Lượt đầu trên máy GPU cần xem ảnh trước/sau trên trang thật
   và đo thời gian cùng VRAM.
2. Chưa build image `worker-gpu` lần nào. Build lần đầu có thể lộ lỗi cài đặt.
3. Lời nhắc mặc định lấy từ Koharu, chưa được tinh chỉnh cho truyện của dự án.
