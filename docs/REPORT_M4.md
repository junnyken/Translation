# Báo cáo Mini-Spec M4 — LaMa Inpainting Wiring cho Text Removal

**Project:** Translation · **Phase:** MTE · **Ngày:** 2026-08-27
**Nền:** M1 `9d093be` · M2 `dea4965` · M3 `4b3139e` (`v0.3-M3`)

## 1. Summary

Pipeline nay chạy thẳng một mạch: upload → nhận diện khung → đọc chữ → **xoá chữ gốc khỏi ảnh**.
Worker dựng mask từ `TextRegion.bbox` (nới ≤15%, clamp trong ảnh), chạy LaMa bản finetune manga qua
ONNX, ghép chỉ vùng mask lên ảnh gốc và lưu ra **file mới** `<tên gốc>_clean.png`, rồi **tự kiểm chứng
bằng cách OCR lại đúng vùng vừa xoá**. Sạch → `inpainted`; còn đọc ra chữ → `inpaint_needs_review`.

Không tạo bảng mới, không migration. 192 test pass (+6 test model thật, opt-in).

## 2. Audit Before Build (6 mục theo spec §5)

Chi tiết + bằng chứng: `docs/TEST_LOG.md § M4.1`. Tóm tắt: `IInpainter` nguyên vẹn;
`clean_image_path` đã nullable sẵn từ M1; weight 197MB mount được **không cần build lại image**;
LaMa **trả ảnh cùng kích thước ảnh vào**; đĩa còn 70GB; gap đúng là `IInpainter` chưa implement.

**Phát hiện quan trọng nhất của Audit 4:** LaMa **vỡ nếu cạnh ảnh không chia hết 8**
(`1401×2001` → `ONNXRuntimeError` ở node `Mul`). Nếu không phát hiện lúc audit thì mọi trang có kích
thước lẻ sẽ chết lúc chạy. → code luôn pad về bội số 8 rồi cắt lại.

## 3. Design Choice

- **Ghép ảnh thay vì lấy nguyên output model**: `kết quả = ảnh gốc×(1−mask) + LaMa×mask`.
  Ngoài vùng mask giữ **nguyên từng pixel** ảnh gốc, tránh model làm mềm/đổi màu cả trang.
  Có unit test canh (`test_chi_thay_pixel_trong_mask`).
- **Pad bằng `edge`** (nhân bản mép) chứ không pad 0 — pad đen sẽ tạo viền giả mà model phải "vẽ lại".
- **Kiểm chứng bằng OCR lại vùng đã xoá** (dùng luôn engine M3) — tiêu chí khách quan, đo được,
  thay cho đánh giá cảm tính "nhìn có artifact không".
- **Trần dilate cứng 15% ở tầng code** (`mask.MAX_DILATE_RATIO`): truyền ratio cao hơn bị kẹp xuống
  chứ không nới bừa ăn vào tranh.
- **Không fallback `cv2.inpaint`**: mặc định tắt, phải bật tường minh
  (`INPAINT_ALLOW_OPENCV_FALLBACK`). LaMa lỗi ⇒ job fail, không âm thầm hạ chất lượng.
- **Điều kiện tiên quyết chặt**: chỉ inpaint khi page `ocr_done` **và** mọi region đã có `OCRResult` —
  không xoá chữ trên dữ liệu dở dang (xoá xong là mất chữ gốc trong ảnh, khó cứu).
- Timeout **riêng** cho inpaint, không dùng chung biến với detect/OCR (có test canh).

## 4. Changed Files

```
backend/app/services/inpaint/{__init__.py,mask.py,lama.py}   (mới)
backend/app/workers/tasks.py     (sửa) + run_inpaint_job, enqueue_inpaint_after_ocr, _verify_text_removed
backend/app/api/v1/routes.py     (sửa) + GET /pages/{id}/clean-image, POST /pages/{id}/retry-inpaint
backend/app/services/dispatch.py (sửa) + dispatch_inpaint_job
backend/app/services/storage.py  (sửa) + delete/abs_path/to_relative
backend/app/core/config.py       (sửa) + 8 tham số M4
backend/app/models/enums.py      (sửa) + 1 cạnh state machine (xem §5)
.env · .env.example              (sửa) tham số M4
backend/tests/{test_inpaint_mask_unit,test_inpaint_lama_unit,test_inpaint_task_integration,
               test_inpaint_real_model}.py   (mới)
backend/tests/{conftest.py,test_no_ai_logic.py}  (sửa) fixture inpainter giả + 5 guardrail M4
docs/{ARCH.md,API.md,FEATURES.md,PLAN.md,TEST_LOG.md}  (sửa) · docs/REPORT_M4.md (mới)
```

**DB migration: KHÔNG có.** Chỉ ghi vào `page.clean_image_path` đã có từ M1.

## 5. New API / DB / State

- `GET /api/v1/pages/{id}/clean-image` → 200 ảnh PNG (404 nếu chưa inpaint hoặc file đã mất).
- `POST /api/v1/pages/{id}/retry-inpaint` → 202 (409 nếu page chưa OCR xong).
- State: `ocr_done → inpainted | inpaint_needs_review`. Lỗi ⇒ page **giữ nguyên** `ocr_done`,
  `clean_image_path` không được ghi.

### Lệch/bổ sung so với spec — khai rõ

1. **Thêm 1 cạnh vào bảng state machine của M1**: `inpainted → inpaint_needs_review`.
   Lý do: chạy lại inpaint trên trang đã `inpainted` mà kết quả tệ hơn thì phải hạ được trạng thái.
   Chỉ thêm cạnh trong hằng số Python, **không đổi enum, không migration, không bỏ cạnh nào**.
2. **Điều kiện "mọi region phải có `OCRResult`"** — spec yêu cầu, đã implement thành lỗi
   `missing_ocr: k/N vùng có kết quả OCR` thay vì raise chung chung.
3. **`storage.to_relative()`** mới — đổi đường dẫn tuyệt đối của file clean về dạng tương đối để lưu DB
   cho khớp cách M1 lưu ảnh gốc.
4. **Ảnh clean luôn là PNG** (kể cả ảnh gốc JPG): tránh mỗi lần chạy lại nén mất chất lượng và
   tránh nhiễu JPEG làm sai bước kiểm chứng OCR.
5. **Không có endpoint mở khoá "bỏ qua kiểm chứng"** — nếu muốn tắt phải sửa `.env`
   (`INPAINT_VERIFY_BY_OCR=false`), không cho bỏ qua bằng tham số request.

## 6. Tests

192 pass + 6 skip. Guardrail nay **15 bài**; thêm ở M4: API không gọi thẳng inpainter, tiến trình API
không nạp `onnxruntime/torch/cv2`, import module `lama` **không** kéo theo onnxruntime (import trễ),
3 task có 3 timeout riêng, và cấm `cv2.inpaint` lọt vào `LamaInpainter`.

## 7. Live Verification

| Ảnh | Vùng | Kết quả | OCR lại còn chữ | Thời gian |
|---|---|---|---|---|
| `few_bubbles.png` | 2 (1,3% diện tích) | `inpainted` | **0/2** | 63,2s |
| `many_bubbles.png` | 6 (3,3% diện tích) | `inpainted` | **0/6** | 44,8s |

- **md5 ảnh gốc trước = sau** trên cả 2 trang → invariant quan trọng nhất giữ được.
- Thư mục `pages/` có đúng 4 file (2 gốc + 2 clean), **không file rác**.
- Chạy lại: số file vẫn 4, log ghi `xoá ảnh clean cũ=True`, ảnh gốc không đổi.
- **Nhìn bằng mắt**: 6 bubble sạch trơn, viền bubble + khung panel + nền giữ nguyên, không artifact.

Số liệu đầy đủ: `docs/TEST_LOG.md § M4.3`.

## 8. Success Criteria — đối chiếu thẳng

| Tiêu chí M4 §8 | Kết quả |
|---|---|
| 100% page `ocr_done` nhận được `clean_image_path` | ✅ Đạt — 2/2 page live, không rơi rớt |
| Không có trường hợp ảnh gốc bị ghi đè (verify checksum) | ✅ Đạt — md5 trùng khớp trước/sau, cả unit test lẫn live |
| OCR lại vùng mask trả rỗng cho ≥90% vùng | ✅ Đạt **trên ảnh tổng hợp** (8/8 = 100%); ⚠️ trên manga thật **chưa nghiệm thu** |
| Toàn bộ test M1+M2+M3 vẫn pass 100% | ✅ Đạt — 192 pass, không sửa test cũ để "cho qua" (2 guardrail phải mở rộng allowlist thư mục, ghi rõ) |
| Guardrail: API không import được thư viện inpaint | ✅ Đạt — 3 bài kiểm ở 3 tầng |
| Với ảnh thật: ≥90% vùng không còn chữ | ⚠️ **CHƯA NGHIỆM THU** — provisional trên ảnh tổng hợp |

## 9. Remaining Limits / Follow-ups

- **Chưa đo trên manga scan thật.** Ảnh tổng hợp có nền phẳng nên inpaint dễ hơn thực tế nhiều;
  trang thật có nét vẽ, halftone, viền bubble cách điệu. Không được suy ra kết quả sẽ tương đương.
  Cùng nút thắt với M2/M3 — nên chốt số liệu 3 mini-spec cùng lúc khi có ảnh.
- Chưa dùng output `seg` (mask chữ ở mức pixel) mà CTD đã trả sẵn từ M2 — hiện mask là hình chữ nhật
  theo bbox. Với bubble sát nét vẽ, mask pixel có thể sạch hơn; để hardening riêng nếu ảnh thật cho thấy cần.
- Chưa xử lý ảnh xoay/nghiêng, scan kém; chưa auto-retry khi lỗi (thuộc M9); chưa có UI xem ảnh clean (M7).
- ~45–63s/trang trên CPU; chưa tối ưu GPU.
- Storage vẫn volume local; `SupabaseStorageAdapter` vẫn là nợ kỹ thuật tracked từ M1.

**Mini-spec kế tiếp:** M5 — Context-Aware Translation (2 nhánh `google_fast`/`llm_context`,
`ReadingOrderResolver`, bảng `APIKeyPool` + xoay key). **Cần API key dịch trước khi bắt đầu.**
