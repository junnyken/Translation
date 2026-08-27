# PLAN.md — Kế hoạch xây dựng Translation (Phase MTE, M1 → M10)

Nguồn: `MTE_Phase_Plan_MiniSpecs.pdf` + `M1_Data_Model_API_Contract.pdf`.
Quy tắc: **tuần tự**, mini-spec sau chỉ mở khi mini-spec trước đã xong + audit pass + có báo cáo.

## Bản đồ tổng

| ID | Nội dung | Đầu ra chính | Rủi ro lớn nhất | Trạng thái |
|---|---|---|---|---|
| **M1** | Nền dữ liệu + hợp đồng API + interface engine | 7 bảng, migration 2 chiều, 6 endpoint, 5 Protocol | Chốt sai schema → sửa giữa đường | ✅ **XONG** |
| **M2** | Nhận diện khung chữ (comic-text-detector) | `CTDDetector(IDetector)` + task Celery `detect` đầu tiên | Model weight + môi trường inference (CPU/GPU); bbox lệch → hỏng cả M3/M4 | ⏭ kế tiếp |
| **M3** | OCR theo ngôn ngữ nguồn | `MangaOCREngine`, `PaddleOCREngine` + factory theo `source_lang` | Crop sai vùng → OCR đúng mà nội dung sai; RAM/model load lặp | Chưa |
| **M4** | Xóa chữ gốc (LaMa) | `LamaInpainter(IInpainter)`, `Page.clean_image_path` | CPU chậm; mask dilate quá tay ăn vào tranh | Chưa |
| **M5** | Dịch 2 đường + thứ tự đọc | `GoogleTranslateEngine`, `LLMContextTranslator`, `ReadingOrderResolver`, bảng `APIKeyPool` | Lệch dòng khi ghép bản dịch về region; đốt token | Chưa |
| **M6** | Tự canh cỡ chữ vừa bubble | `FitToBoxTypesetter(ITypesetter)` | Đo font-metrics sai (tiếng Việt có dấu) → tràn khung | Chưa |
| **M7** | Màn sửa tay | `PATCH /regions/{id}` + Page Detail UI | Sửa 1 region đụng region khác; re-fit sai phạm vi | Chưa |
| **M8** | Xuất PNG/CBZ + lưu/mở project | `ExportJob`, `ChapterExporter` | Export dùng bản cũ sau khi đã sửa tay | Chưa |
| **M9** | Chạy cả chapter + xoay API key | `KeyRotationManager`, `BatchOrchestrator` | Vượt rate-limit provider; hết sạch key mà vẫn báo thành công | Chưa |
| **M10** | Guardrail bản quyền | modal nhắc + gate `intended_use` | Over-scope thành hệ kiểm duyệt nội dung | Field đã có từ M1 |

## Điều kiện tiên quyết cần chuẩn bị trước (không phải code)

| Cần | Dùng cho | Tình trạng |
|---|---|---|
| 3–5 trang **manga scan thật** (nhiều bubble / ít bubble / có SFX rời) | Đo tỷ lệ nhận diện M2, độ chính xác OCR M3 | **Chưa có — cần bạn cung cấp** |
| Model weight comic-text-detector | M2 | Chưa tải |
| Model weight LaMa | M4 | Chưa tải |
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

## Phác thảo M2 (mini-spec kế tiếp)

- Tải weight comic-text-detector, chạy trong worker Celery riêng (`-Q detect`), CPU fallback.
- `CTDDetector(IDetector)` — convert output `(x1,y1,x2,y2)` → `bbox(x,y,w,h)`, có unit test công thức.
- Ghi `TextRegion` + `confidence`; `confidence < ngưỡng` → `status=low_confidence` (**không** loại bỏ âm thầm).
- Chồng lấp > 80% diện tích → `overlap_suspect=true`.
- Timeout an toàn (~60s/ảnh) → `Page.status=detection_failed`, không treo worker.
- Page đi đúng đường `queued → detecting → detected | detection_failed` (dùng `assert_transition` đã có).
- Tiêu chí đạt: nhận đúng ≥90% bubble có chữ (đếm tay đối chiếu), không bbox âm/vượt kích thước ảnh.
