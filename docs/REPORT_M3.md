# Báo cáo Mini-Spec M3 — Multi-Engine OCR Wiring (manga-ocr / PaddleOCR)

**Project:** Translation · **Phase:** MTE · **Ngày:** 2026-08-27
**Nền:** M1 `9d093be` (`v0.1-M1`) · M2 `dea4965` (`v0.2-M2`)

## 1. Summary

Pipeline nay tự chảy tới bước đọc chữ: detect xong → hệ thống tự xếp `Job(type=ocr)` → worker crop
từng `TextRegion` theo bbox của M2, chạy engine theo `Project.source_lang` (manga-ocr cho `ja`,
PaddleOCR cho `zh`/`en`), ghi `raw_text` + `confidence` vào `OCRResult` và đẩy `Page` sang `ocr_done`.
Không tạo bảng mới, không migration. 145 test pass (+5 test model thật, opt-in).

Live verification lộ ra **1 sự cố thật của framework** và **1 lỗ hổng thiết kế của chính task OCR** —
cả hai đã sửa và có test canh, chi tiết ở §7.

## 2. Audit Before Build (6 mục theo spec §5)

| # | Mục kiểm | Kết quả |
|---|---|---|
| 1 | `IOCREngine.recognize(image_path, bbox) -> tuple[str, float]` chưa đổi | Đạt, `MangaOCREngine`/`PaddleOCREngine` implement đúng |
| 2 | bbox của M2 crop ra đúng vùng chữ | **Đạt, kiểm bằng mắt trước khi viết code OCR**: crop 6 region thật từ DB của `many_bubbles.png` → cả 6 ảnh chứa trọn chữ trong bubble |
| 3 | manga-ocr + PaddleOCR cài được trong worker | Đạt (image worker 4,45GB) |
| 4 | manga-ocr có confidence không? | **KHÔNG** — đọc source 0.1.16: `MangaOcr.__call__` chỉ trả chuỗi |
| 5 | Xung đột dependency onnxruntime ↔ torch/paddle? | **Không xung đột**, nhưng lộ 2 bẫy thật (xem dưới) |
| 6 | Gap = `IOCREngine` chưa implement | Đúng phạm vi, không lấn sang M4 |

Hai bẫy dependency — hỏng **lúc chạy** chứ không hỏng lúc cài:

1. `torch` trên PyPI kéo theo cả stack CUDA (`nvidia-*`, `cuda-toolkit-13`, `triton`) — vô dụng trên máy CPU.
   → cài từ `--index-url https://download.pytorch.org/whl/cpu`.
2. `paddleocr` **không** kéo theo `paddlepaddle`. Cài xong vẫn "thành công" rồi chết lúc nhận diện.
   → khai `paddlepaddle==3.3.1` tường minh.

## 3. Design Choice

- **`confidence = NULL` cho manga-ocr** thay vì bịa số (đúng cảnh báo trong spec). Tiêu chí `needs_manual`
  thay thế: `raw_text` rỗng **hoặc không chứa ký tự có nghĩa**. Với PaddleOCR (có confidence thật)
  thêm điều kiện `confidence < OCR_CONF_THRESHOLD`. Ghi rõ ở `ARCH.md §6` để không ai tưởng NULL là bug.
- **Hướng A — auto-chain** (`OCR_AUTO_CHAIN=true`): detect xong tự xếp việc OCR, đúng tinh thần
  "một cú bấm là chạy". Vẫn có `POST /pages/{id}/retry-ocr` để can thiệp tay.
- **Batch theo Page**: 1 task xử lý toàn bộ region của trang, model nạp 1 lần/process (cache theo
  `(source_lang, device)`).
- **Tách image worker khỏi image api** (multi-stage `base` / `worker`): API 1,06GB không có torch/paddle,
  worker 4,45GB. Ranh giới "API không chạm model" thành sự thật ở tầng image, không chỉ là quy ước.
- **Crop: round trên toạ độ tuyệt đối** (`round(x)`, `round(x+w)`) chứ không `round(x)+round(w)` —
  tránh lệch 1px tích lũy. Không tự nới lề.
- **Timeout riêng cho OCR** (`OCR_TIMEOUT_SECONDS`, mặc định 600s code / 900s `.env`), không dùng chung
  biến với detect — có test canh 2 giá trị phải khác nhau.

## 4. Changed Files

```
backend/app/services/ocr/{__init__.py,crop.py,engines.py}   (mới)
backend/app/workers/tasks.py        (sửa) + run_ocr_job, enqueue_ocr_after_detect, _classify_ocr
backend/app/api/v1/routes.py        (sửa) + GET /pages/{id}/ocr, POST /pages/{id}/retry-ocr
backend/app/services/dispatch.py    (sửa) + dispatch_ocr_job
backend/app/schemas/common.py       (sửa) + OCRResultRead
backend/app/core/config.py          (sửa) + 5 tham số M3
backend/Dockerfile                  (sửa) multi-stage base/worker
backend/requirements-worker.txt     (mới) manga-ocr, paddleocr, paddlepaddle
docker-compose.yml · .env · .env.example   (sửa) target build, volume model_cache, tham số M3
backend/tests/{test_ocr_crop_unit,test_ocr_engines_unit,test_ocr_task_integration,
               test_ocr_real_engine}.py    (mới)
backend/tests/{conftest.py,test_no_ai_logic.py}  (sửa) fixture engine giả + 5 guardrail M3
docs/{ARCH.md,API.md,FEATURES.md,PLAN.md,TEST_LOG.md}  (sửa) · docs/REPORT_M3.md (mới)
```

**DB migration: KHÔNG có.** Chỉ ghi vào cột `ocr_result` đã chốt ở M1.

## 5. New API / DB / State

- `GET /api/v1/pages/{id}/ocr` → 200, list `{region_id, raw_text, ocr_engine, confidence, status}`.
  Trả `[]` khi chưa chạy — không bịa text.
- `POST /api/v1/pages/{id}/retry-ocr` → 202 (409 nếu page chưa có region nào).
- State: `Page: detected → ocr_done` khi thành công. **Lỗi/timeout: Page GIỮ `detected`** (không nhảy
  `ocr_done`) để còn chạy lại — có regression test canh.

### Lệch/bổ sung so với spec — khai rõ

1. **`recognize()` trả `tuple[str, float | None]`** thay vì `tuple[str, float]` như Protocol M1.
   Lý do: manga-ocr không có confidence, mà M1 đã quy định "chưa có bằng chứng thì để NULL".
   Không đổi tên method, không đổi số tham số — chỉ nới kiểu trả về cho đúng sự thật.
2. **Thêm `OCR_PADDLE_ENABLE_MKLDNN` (mặc định `false`)** — bắt buộc, vì paddlepaddle 3.3.1 vỡ ở nhánh
   oneDNN trên CPU này (xem §7). Không có cờ này thì PaddleOCR không chạy được dòng nào.
3. **Tách image worker/api** (spec chỉ nói "không tách container OCR riêng" — vẫn 1 container worker
   như spec yêu cầu, chỉ khác *image*).
4. **`POST /pages/{id}/retry-ocr`** là endpoint optional của spec — **có implement**.
5. **Task ném lỗi khi engine hỏng trên MỌI region** (mới, không có trong spec) — xem §7.

## 6. Tests

145 pass + 5 skip (engine/model thật, opt-in). Guardrail nay có **10 bài**, thêm ở M3:
API process không nạp được `manga_ocr/paddleocr/torch/transformers`; import module engine **không**
kéo theo torch/paddle (phải là import trễ); OCR có timeout riêng khác detect; API không gọi thẳng engine.
Phân nhóm chi tiết: `docs/TEST_LOG.md § M3`.

## 7. Live Verification — và 2 lỗi thật nó lộ ra

Chạy đúng đường thật (upload → detect → **tự nối** OCR → DB), không mock gì.

| Nhánh | Bộ ảnh | Kết quả |
|---|---|---|
| `en` (PaddleOCR) | 2 trang tổng hợp, 8 vùng | **8/8 vùng đọc ra chữ** (`status=ok`), **7/8 khớp chính xác từng ký tự** với bản gốc; 13,1s + 8,0s |
| `ja` (manga-ocr) | ảnh mẫu tiếng Nhật thư viện đóng gói sẵn | chép lại gần như chính xác chuỗi kanji dọc, đúng chiều đọc phải→trái; `confidence=None` đúng thiết kế; 8,8s |

Chỗ lệch duy nhất: `IAM` thiếu dấu cách (bản gốc `I AM`) — **cố ý không sửa**, constraint 5 cấm
normalize `raw_text`. Idempotent chạy thật: `retry-ocr` xoá đúng 2 và 6 kết quả cũ, số record không đổi.
Toàn bộ số liệu + đối chiếu từng vùng: `docs/TEST_LOG.md § M3`.

### Live verification bắt được 2 lỗi mà 150 test giả lập KHÔNG bắt được

**1. PaddleOCR không chạy được dòng nào.** paddlepaddle 3.3.1 ném
`NotImplementedError: ConvertPirAttribute2RuntimeAttribute ... onednn_instruction.cc` — vỡ ở nhánh
oneDNN/PIR trên CPU này. Biến môi trường `FLAGS_use_mkldnn=0` không cứu được; phải truyền
`enable_mkldnn=False` vào `PaddleOCR(...)`. → thêm `OCR_PADDLE_ENABLE_MKLDNN=false`.

**2. Thứ tự dòng bị đảo** (`"OUT!\nLOOK"`). Cắt đúng vùng ra nhìn bằng mắt thì LOOK nằm trên, nhưng
PaddleOCR báo ngược. Thủ phạm: bộ phân loại **hướng trang tài liệu** xoay crop 180° — crop 1 bubble
không có "hướng trang" nên nó đoán bừa. Tắt `use_doc_orientation_classify` + `use_doc_unwarping`
(giữ `use_textline_orientation`): đúng thứ tự, và nhanh hơn gấp 2-6 lần.

### Và 1 lỗ hổng trong chính code M3 mà sự cố 1 phơi ra

Task bắt exception theo từng vùng để "1 vùng hỏng không giết cả trang". Nhưng khi engine chết ở **mọi**
vùng, nó ghi 100% `needs_manual` rồi tự nhận `ocr_done` — nhìn từ ngoài **giống hệt** "trang này không
có chữ". Đúng kiểu bug che mất sự cố.

Đã sửa: mọi vùng đều lỗi ⇒ job `failed` + `error_log` ghi lỗi gốc, page giữ `detected`, **không** ghi
record rỗng. Có test canh. Đây là điểm bổ sung #5 trong danh sách lệch spec ở §5.

### Ghi nhận thêm: detect (M2) đo lại chậm hơn

61,4s và 57,5s/ảnh trên image worker mới (M2 đo ~40s). 61,4s đã **vượt mặc định 60s trong code** —
nhờ `.env` đặt `DETECT_TIMEOUT_SECONDS=120` (điểm lệch spec #3 của M2) mà job không chết oan.
Bằng chứng thực tế cho quyết định đó; giữ nguyên 120s.

## 8. Success Criteria — đối chiếu thẳng

| Tiêu chí M3 §8 | Kết quả |
|---|---|
| 100% `TextRegion` của 1 page nhận được `OCRResult`, kể cả `low_confidence` | ✅ Đạt — 8/8 vùng live (có 1 vùng `low_confidence` từ M2 vẫn được OCR); có test canh |
| Không có `OCRResult` trùng lặp theo `region_id` sau retry/re-run | ✅ Đạt — `unique(region_id)` từ M1 + xoá-trước-ghi; verify bằng regression test và chạy lại thật |
| Toàn bộ test M1+M2 vẫn pass 100% sau khi thêm M3 | ✅ Đạt — 150 pass, không sửa test cũ nào để "cho qua" (1 guardrail M2 phải mở rộng allowlist thư mục, ghi rõ ở §5) |
| Guardrail test xác nhận API process không import được thư viện OCR | ✅ Đạt — 3 bài: quét import, chạy tiến trình thật kiểm `sys.modules`, kiểm import trễ của engine |
| Với ảnh thật: ≥80% region đọc ra text đúng nghĩa | ⚠️ **CHƯA NGHIỆM THU** — mới đo trên ảnh tổng hợp (7/8 = 87,5% khớp tuyệt đối, 8/8 đọc ra chữ). Đánh dấu **provisional** đúng như spec §7.4 yêu cầu; chặn bởi cùng nút thắt ảnh manga thật của M2 |

## 9. Remaining Limits / Follow-ups

- **Chưa đo trên manga scan thật** — cùng nút thắt với M2 (ảnh có license rõ). Số liệu hiện tại là
  **provisional** trên ảnh tổng hợp, đúng như spec M3 §7.4 yêu cầu đánh dấu.
- Chưa xử lý bubble nhiều dòng khác font — để hardening riêng nếu gặp thật.
- Không có cơ chế "chọn engine tốt nhất" tự động — đã loại ở Design Choice.
- `torchvision` **đã thêm** vào image worker sau khi đo: thiếu nó manga-ocr chạy 55,8s/vùng thay vì 8,8s.
- Thời gian OCR đo trên CPU; chưa tối ưu GPU.
- Storage vẫn volume local; `SupabaseStorageAdapter` vẫn là nợ kỹ thuật tracked từ M1.

**Mini-spec kế tiếp:** M4 — Inpainting (LaMa): dùng `TextRegion.bbox` tạo mask xóa chữ gốc, sinh
`Page.clean_image_path`. Cân nhắc tận dụng output `seg` (mask chữ) mà CTD đã trả sẵn từ M2.
