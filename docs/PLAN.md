# PLAN.md — Kế hoạch xây dựng Translation (Phase MTE, M1 → M10)

Nguồn: `MTE_Phase_Plan_MiniSpecs.pdf` + `M1_Data_Model_API_Contract.pdf`.
Quy tắc: **tuần tự**, mini-spec sau chỉ mở khi mini-spec trước đã xong + audit pass + có báo cáo.

## Bản đồ tổng

| ID | Nội dung | Đầu ra chính | Rủi ro lớn nhất | Trạng thái |
|---|---|---|---|---|
| **M1** | Nền dữ liệu + hợp đồng API + interface engine | 7 bảng, migration 2 chiều, 6 endpoint, 5 Protocol | Chốt sai schema → sửa giữa đường | ✅ **CLOSED — approved 2026-08-27** (`v0.1-M1`, `9d093be`) |
| **M2** | Nhận diện khung chữ (comic-text-detector) | `CTDDetector(IDetector)` + task Celery `detect` đầu tiên | Model weight + môi trường inference (CPU/GPU); bbox lệch → hỏng cả M3/M4 | ✅ **XONG** (`v0.2-M2`) — còn treo: đo trên manga thật |
| **M3** | OCR theo ngôn ngữ nguồn | `MangaOCREngine`, `PaddleOCREngine` + factory theo `source_lang` | Crop sai vùng → OCR đúng mà nội dung sai; RAM/model load lặp | ✅ **XONG** (`v0.3-M3`) — còn treo: đo trên manga thật |
| **M4** | Xoá chữ gốc (LaMa) | `LamaInpainter(IInpainter)`, `Page.clean_image_path` | CPU chậm; mask dilate quá tay ăn vào tranh | ✅ **XONG** (`v0.4-M4`) — còn treo: đo trên manga thật |
| **M5** | Dịch 2 đường + thứ tự đọc ⏭ kế tiếp | `GoogleTranslateEngine`, `LLMContextTranslator`, `ReadingOrderResolver`, bảng `APIKeyPool` | Lệch dòng khi ghép bản dịch về region; đốt token | Chưa |
| **M6** | Tự canh cỡ chữ vừa bubble | `FitToBoxTypesetter(ITypesetter)` | Đo font-metrics sai (tiếng Việt có dấu) → tràn khung | Chưa |
| **M7** | Màn sửa tay | `PATCH /regions/{id}` + Page Detail UI | Sửa 1 region đụng region khác; re-fit sai phạm vi | Chưa |
| **M8** | Xuất PNG/CBZ + lưu/mở project | `ExportJob`, `ChapterExporter` | Export dùng bản cũ sau khi đã sửa tay | Chưa |
| **M9** | Chạy cả chapter + xoay API key | `KeyRotationManager`, `BatchOrchestrator` | Vượt rate-limit provider; hết sạch key mà vẫn báo thành công | Chưa |
| **M10** | Guardrail bản quyền | modal nhắc + gate `intended_use` | Over-scope thành hệ kiểm duyệt nội dung | Field đã có từ M1 |

## Điều kiện tiên quyết cần chuẩn bị trước (không phải code)

| Cần | Dùng cho | Tình trạng |
|---|---|---|
| 3–5 trang **manga scan thật** (nhiều bubble / ít bubble / có SFX rời) | Đo tỷ lệ nhận diện M2, độ chính xác OCR M3 | **Chưa có — cần bạn cung cấp** |
| Model weight comic-text-detector | M2 | ✅ Đã tải (ONNX 91MB, xem ARCH.md §5) |
| Model weight LaMa | M4 | ✅ Đã tải (ONNX 197MB, MIT/Apache — xem ARCH.md §7) |
| API key dịch (Gemini/GPT) + key dự phòng | M5, M9 | Chưa có |
| File font HLCOMIC2 / HLCOMIC1 / MTO Comic / Anime Ace / Wild Words | M6 | Chưa có |
| Credential Supabase (DB + Storage) nếu muốn dùng Supabase managed | Toàn Phase | Chưa có (đang chạy Postgres local) |

Thiếu 4 mục đầu thì M2/M4/M5/M6 **không thể verify thật** — sẽ chỉ có code chưa được chứng minh.

## Cách chạy mỗi mini-spec (áp cho M2 trở đi)

1. **Audit trước khi build** — đọc code đã có, xác nhận đúng chỗ cần cắm, ghi rõ gap.
2. Code đúng phạm vi mini-spec, không mở rộng.
3. Test: unit + integration + regression (bảo vệ invariant của mini-spec trước) + **live verification chạy thật**.
4. Cập nhật `ARCH.md` / `API.md` / `FEATURES.md` / `TEST_LOG.md`.
5. Viết `docs/REPORT_M<n>.md` → chốt xong mới mở mini-spec kế.

## Phác thảo M5 (mini-spec kế tiếp)

- 2 nhánh dịch: `google_fast` (miễn phí, theo dòng) và `llm_context` (gộp cả trang, giữ mạch văn).
- `ReadingOrderResolver`: JP đọc phải→trái, EN trái→phải — **cấu hình theo `source_lang`**, không hard-code.
- Bảng mới `APIKeyPool` + xoay key khi hết quota; hết sạch key ⇒ `blocked_quota`, không âm thầm hạ cấp.
- Giữ nguyên `raw_text` của M3 làm đầu vào (lỗi OCR để LLM tự sửa theo ngữ cảnh).
- Cần trước khi làm: **API key dịch + key dự phòng**.

<details>
<summary>Phác thảo M4 (đã hoàn thành)</summary>

- `LamaInpainter(IInpainter)` — mask từ `TextRegion.bbox`, dilate ≤15%, xử lý **theo Page** (1 lần gọi model).
- Ghi `Page.clean_image_path`; **không ghi đè ảnh gốc** (có test regression canh).
- Artifact rõ → `Page.status=inpaint_needs_review`, không tự pass.
- Kiểm chứng bằng cách OCR lại chính vùng đã xóa: kỳ vọng trả rỗng.
- Cân nhắc dùng output `seg` (mask chữ) mà CTD đã trả sẵn ở M2 thay vì chỉ dựa vào bbox chữ nhật.

<details>
<summary>Phác thảo M3 (đã hoàn thành)</summary>

- `MangaOCREngine` (`ja`) / `PaddleOCREngine` (`zh`,`en`) + factory chọn theo `Project.source_lang`.
- Crop theo `TextRegion.bbox` đã có từ M2 — **đối chiếu tay vài mẫu crop trước khi code OCR** (crop lệch thì OCR đúng cũng vô nghĩa).
- OCR rỗng / điểm thấp → `OCRResult.status=needs_manual`, không bỏ qua region.
- Không tự sửa/normalize `raw_text` — để M5 xử lý theo ngữ cảnh.
- Batch theo Page, nạp model 1 lần/worker; idempotent theo `region_id` (`unique` đã có sẵn từ M1).

<details>
<summary>Phác thảo M2 (đã hoàn thành)</summary>


- Tải weight comic-text-detector, chạy trong worker Celery riêng (`-Q detect`), CPU fallback.
- `CTDDetector(IDetector)` — convert output `(x1,y1,x2,y2)` → `bbox(x,y,w,h)`, có unit test công thức.
- Ghi `TextRegion` + `confidence`; `confidence < ngưỡng` → `status=low_confidence` (**không** loại bỏ âm thầm).
- Chồng lấp > 80% diện tích → `overlap_suspect=true`.
- Timeout an toàn (~60s/ảnh) → `Page.status=detection_failed`, không treo worker.
- Page đi đúng đường `queued → detecting → detected | detection_failed` (dùng `assert_transition` đã có).
- Tiêu chí đạt: nhận đúng ≥90% bubble có chữ (đếm tay đối chiếu), không bbox âm/vượt kích thước ảnh.
</details>
</details>
</details>
