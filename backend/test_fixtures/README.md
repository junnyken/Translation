# test_fixtures — ảnh dùng cho test M2

| File | Nguồn | License | Vùng chữ đếm tay |
|---|---|---|---|
| `many_bubbles.png` | Repo tự sinh bằng `make_fixtures.py` | CC0 / thuộc repo này | 6 |
| `few_bubbles.png` | Repo tự sinh bằng `make_fixtures.py` | CC0 / thuộc repo này | 2 |
| `loose_sfx.png` | Repo tự sinh bằng `make_fixtures.py` | CC0 / thuộc repo này | 4 (1 bubble + 3 SFX rời) |

Sinh lại: `python test_fixtures/make_fixtures.py`

## Cảnh báo khi đọc số liệu

Đây là **trang tổng hợp**, không phải manga scan thật. Chúng chứng minh pipeline chạy đúng đầu-cuối
(letterbox → ONNX → NMS → clamp → ghi DB) chứ **không** đo được chất lượng nhận diện trên manga thật.

## Muốn đo thật thì cần gì

Bỏ ảnh manga có license rõ vào thư mục này (hoặc `test_fixtures/external/`, đã được `.gitignore`),
rồi chỉnh `EXPECTED` trong `tests/test_detect_real_model.py` theo số bubble đếm tay của từng ảnh:

```bash
MTE_RUN_MODEL_TESTS=1 MODEL_WEIGHTS_PATH=../models/comic-text-detector.onnx \
  ../.venv/bin/python -m pytest tests/test_detect_real_model.py -q
```

**Không commit ảnh có bản quyền chưa xác nhận license.** Manga109-s (Hugging Face) đang `gated`:
tải không token trả HTTP 401 và bộ này chỉ cho dùng học thuật — kể cả khi tải được cũng **không**
commit vào repo, để ở `external/`.
