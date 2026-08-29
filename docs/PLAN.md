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
| **M5** | Dịch 2 đường + thứ tự đọc | `GoogleTranslateEngine`, `LLMContextTranslator`, `ReadingOrderResolver` (**không** tạo bảng `APIKeyPool` — key ở `.env`, xem ARCH §8) | Lệch dòng khi ghép bản dịch về region; đốt token | ✅ **XONG** (`v0.5-M5`) — còn treo: đo trên manga thật + trang JP |
| **M6** | Tự canh cỡ chữ vừa bubble | `FitToBoxTypesetter(ITypesetter)` + `FontResolver` + `PagePreviewRenderer` | Đo font-metrics sai (tiếng Việt có dấu) → tràn khung | ✅ **XONG** (`v0.6-M6`) — còn treo: Run B (font comic thật) không khả thi, Run C (manga thật) chưa chạy |
| **M7** | Màn sửa tay | `PATCH /regions/{id}` + Page Detail UI (React) | Sửa 1 region đụng region khác; re-fit sai phạm vi | ✅ **XONG** (`v0.7-M7`) — lộ ra 2 lỗi thật (khung vẽ lệch, chữ tràn ra ngoài trang) đã sửa |
| **M8** | Xuất PNG/CBZ + lưu/mở project | `ExportJob`, `ChapterExporter` | Export dùng bản cũ sau khi đã sửa tay | ✅ **XONG** (`v0.8-M8`) — rủi ro dự đoán KHÔNG xảy ra; lộ ra lỗi khác: retry-translate chết từ M6 |
| **M9** | Chạy cả chapter theo mẻ ✅ xong | `BatchOrchestrator`, `GeminiProjectRateGate`, `RetryPolicy` | Vượt hạn mức nhà cung cấp; báo mẻ xong khi còn trang chưa chạy; thử lại vô hạn | Đã gộp watchdog việc chết vì worker bị giết (hỏi broker, không đoán theo đồng hồ). **Bỏ** `KeyRotationManager`: M5 đã đo — xoay khoá cùng project Gemini không tăng hạn mức |
| **M10** | Khai báo mục đích + nhắc trách nhiệm trước khi xuất ✅ xong | `ComplianceGate`, `ExportComplianceLog` | Chặn cứng chức năng khiến người dùng đi đường vòng; cảnh báo lải nhải thì ai cũng bấm cho qua | Cảnh báo hiện **một lần/chapter**, máy chủ **ghi nhận** chứ không cấm; số liệu do máy chủ đếm lại, không nhận từ trình duyệt |
| **E12** | Cổng chất lượng vùng ✅ xong | `RegionQualityAssessor`, `RegionQualityAssessment` | Tự xoá vùng nghi ngờ; dùng LLM tự chấm chính nó; điểm số giả vờ chính xác | Luật thuần, 18 mã lý do có bảng trắng; quyết định bỏ qua là của NGƯỜI và không xoá dữ liệu |

## Điều kiện tiên quyết cần chuẩn bị trước (không phải code)

| Cần | Dùng cho | Tình trạng |
|---|---|---|
| 3–5 trang truyện tranh thật | Đo tỷ lệ nhận diện M2, độ chính xác OCR M3 | ✅ **Đã có** — Pepper&Carrot (CC BY-SA 4.0), Run C đã chạy, xem `TEST_LOG § Run C`. **Vẫn thiếu manga Nhật thật** (chữ dọc, đọc phải→trái) |
| Model weight comic-text-detector | M2 | ✅ Đã tải (ONNX 91MB, xem ARCH.md §5) |
| Model weight LaMa | M4 | ✅ Đã tải (ONNX 197MB, MIT/Apache — xem ARCH.md §7) |
| API key dịch (Gemini/GPT) + key dự phòng | M5, M9 | ✅ Đã có (`GEMINI_API_KEYS` trong `.env`) — lưu ý quota tính theo **project**, không theo key |
| File font cho M6 | M6 | ✅ **Đã có** — nhưng **không phải 3 font spec chỉ định**: HL Comic2 chỉ 38/134 ký tự Việt (font mã TCVN3 đời 2004), Anime Ace "Limited European Characters" + phải mua license, MTO Comic không tồn tại. Đã thay bằng **Bangers · Shantell Sans · Mansalva · Sigmar One** (SIL OFL, đo thật 134/134) trong `fonts/` — xem `docs/FONTS.md` |
| Credential Supabase (DB + Storage) nếu muốn dùng Supabase managed | Toàn Phase | Chưa có (đang chạy Postgres local) |

Run C **đã chạy** trên truyện tranh thật có giấy phép rõ (xem `TEST_LOG § Run C`): nhận diện 3/3 bong
bóng thoại, OCR đúng 3/3, canh chữ 5/5 vừa khung. Còn thiếu **manga Nhật thật** để kiểm đường chữ dọc.

## Cách chạy mỗi mini-spec (áp cho M2 trở đi)

1. **Audit trước khi build** — đọc code đã có, xác nhận đúng chỗ cần cắm, ghi rõ gap.
2. Code đúng phạm vi mini-spec, không mở rộng.
3. Test: unit + integration + regression (bảo vệ invariant của mini-spec trước) + **live verification chạy thật**.
4. Cập nhật `ARCH.md` / `API.md` / `FEATURES.md` / `TEST_LOG.md`.
5. Viết `docs/REPORT_M<n>.md` → chốt xong mới mở mini-spec kế.

## Phác thảo E13/E14 (tuỳ bằng chứng thật)

- **E13 — Thống nhất thuật ngữ & giọng nhân vật**: khoá danh sách thuật ngữ do người duyệt, giữ
  mạch xưng hô giữa các trang. **Không** để LLM tự sửa lại bản dịch.
- **E14 — Căn chữ theo hình bong bóng**: bbox chữ nhật không biết bong bóng là elip. Cần bằng
  chứng lỗi thật từ trang truyện trước khi làm.

<details>
<summary>Phác thảo E12 (đã hoàn thành)</summary>

- Cổng chất lượng vùng: 18 mã lý do, 4 nhóm phân loại, đẩy vùng đáng ngờ vào màn sửa tay.
- **Không** xoá vùng, **không** dùng LLM chấm bản dịch, **không** có điểm 0–100.
- Giới hạn đã ghi: luật độ dài không bắt được tiếng động dài như `SPLASH`.

</details>

<details>
<summary>Phác thảo E11 (đã hoàn thành)</summary>

- Làm lại bề mặt sản phẩm, **không đụng backend**: token màu, bộ component dùng chung, vùng
  kéo-thả, dòng thời gian pipeline, bảng dịch trạng thái tập trung có test canh.
- Lỗi thật tìm được: giao diện chỉ chờ 42 giây trong khi việc thật mất 108 giây khi worker bận.
- Khoảng trống chưa lấp: chưa có endpoint liệt kê chapter — xem `REPORT_E11.md §7`.

</details>

## Phác thảo M11 (nếu thật sự cần)

- **Nhiều người dùng & phân quyền**: hiện `edited_by_user` chỉ nói "có người sửa", không nói "ai".
  Chỉ làm khi có nhu cầu thật — thêm auth vào một công cụ một người dùng là tự tạo việc.
- Chưa làm và **cố ý** chưa làm: lưu nhiều phiên bản xuất, watermark/DRM, cảnh báo đa ngôn ngữ.

<details>
<summary>Phác thảo M10 (đã hoàn thành)</summary>

- Khai báo `intended_use` bắt buộc, **không mặc định** — chỗ hỏng thật nằm ở giao diện chứ không
  ở DB (cột đã `NOT NULL` từ M1).
- Nhắc trách nhiệm + chất lượng **một lần/chapter** trước khi xuất; máy chủ ghi nhận, không cấm.
- `ExportComplianceLog` chỉ lưu số liệu, không lưu nội dung export.

</details>

<details>
<summary>Phác thảo M6 (đã hoàn thành)</summary>

- `FitToBoxTypesetter(ITypesetter)` — chèn bản dịch của M5 vào ảnh clean của M4, tự tính cỡ chữ +
  ngắt dòng cho vừa `TextRegion.bbox`.
- **Đo font-metrics thật** (không ước lượng theo số ký tự): tiếng Việt có dấu nên chiều cao dòng
  khác hẳn tiếng Anh — đây là rủi ro lớn nhất của M6.
- Không vừa khung dù đã thu nhỏ tới ngưỡng ⇒ `TypesetResult.fit_status=overflow_warning`
  (enum đã chốt ở M1), **không tự cắt chữ**, không tự tràn ra ngoài bubble.
- Font: đã có sẵn trong `fonts/` (4 font OFL, đủ 134 ký tự Việt, có test canh). **Bangers không có chữ thường**;
  cần đậm/nghiêng thì dùng Shantell Sans. Chi tiết + bẫy: `docs/FONTS.md`.

</details>

<details>
<summary>Phác thảo M5 (đã hoàn thành)</summary>

- 2 nhánh dịch: `google_fast` (miễn phí, theo dòng) và `llm_context` (gộp cả trang, giữ mạch văn).
- `ReadingOrderResolver`: JP đọc phải→trái, EN trái→phải — **cấu hình theo `source_lang`**, không hard-code.
- Xoay key khi hết quota; hết sạch key ⇒ báo rõ, không âm thầm hạ cấp.
  **Đã bỏ bảng `APIKeyPool`**: spec §4A của M5 không liệt kê bảng này và constraint 7 buộc key chỉ nằm
  ở `.env`/secrets — đưa key vào Postgres sẽ kéo theo mã hoá + xoay khoá, đẩy sang M9 nếu thật sự cần.
- Giữ nguyên `raw_text` của M3 làm đầu vào (lỗi OCR để LLM tự sửa theo ngữ cảnh) — **đã kiểm chứng thật**:
  `IAM` (OCR đọc sai `I AM`) được LLM dịch đúng thành "Ta ở đây."

</details>

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

## E13 — Thuật ngữ & rà soát nhất quán (2026-08-29)

✅ **Xong cả backend lẫn giao diện** (`697 test backend + 91 test giao diện`): 3 bảng, 13 endpoint,
quét theo luật tất định, áp/từ chối có chốt chặn bản-đã-đổi; giao diện D1–D5 (bảng nhất quán, quản
lý thuật ngữ, hồ sơ giọng, hàng đợi rà soát, khối cảnh báo riêng lúc xuất).

Run A + Run B chạy thật trên Pepper&Carrot — tự tìm ra đúng lỗi `SPLASH` → "TUYỆT VỜI" mà M8 Run C
từng phát hiện bằng tay. Run C + Run D bấm thật trên Chromium: **17/17 đạt**, 0 lỗi console, và
bản dịch trong CSDL **y nguyên** sau khi chỉ xem hồ sơ giọng.

Hai bài học kỹ thuật đáng nhớ:

- **`UNIQUE` thường của Postgres KHÔNG chống được trùng khi cột có NULL** — phải dùng
  `UNIQUE NULLS NOT DISTINCT`. Đo thật, xem `TEST_LOG § E13.2`.
- **Phần tử `position: absolute` chỉ bị cắt bởi khung cuộn CÓ ĐỊNH VỊ.** Một tiêu đề cột ẩn cho
  trình đọc màn hình đủ để kéo cả trang trôi ngang 23px trên điện thoại mà mắt gần như không thấy
  — chỉ `window.scrollX` mới nói ra. Xem `TEST_LOG § E13.9`.


## E14 — Vùng an toàn theo hình bong bóng (2026-08-29)

✅ **Xong backend + giao diện** (`743 test backend + 95 test giao diện`): bảng `region_safe_area`,
bộ trích hình bong bóng, lớp chọn ô đặt chữ, 3 endpoint, lớp phủ trong màn sửa tay, khối cảnh báo
riêng lúc xuất.

Đo thật trên 9 vùng Pepper&Carrot: 5/5 bong bóng nhận được hình, 4/4 vùng không phải bong bóng
lùi về dự phòng, **0 lần chọn nhầm**, 5/5 khối chữ nằm trọn trong đa giác. Cỡ chữ tăng ở 3/5 vùng.

Ba bài học đáng nhớ:

- **Ngưỡng chặt + lấp lỗ theo từng ứng viên.** Nới ngưỡng để cứu lỗ do LaMa vá sẽ làm bong bóng
  dính vào nền sáng; lấp lỗ trên cả vùng tìm kiếm thì nuốt luôn mảng tối bị nền sáng bao quanh.
- **Nhân hình thái phải bám bbox, không bám ROI.** Bám ROI thì mỗi lần nới ROI là một thuật toán
  khác, kết quả nhảy không đơn điệu (2 → 1 → 3).
- **Đường dự phòng phải giống HỆT hành vi cũ.** Lệch lề làm cỡ chữ đổi ở ngay chỗ E14 không nhận
  ra hình gì — thay đổi không ai xin và không giải thích được.

⚠️ **Khoảng trống lớn nhất còn lại:** chưa đo trên truyện **đen trắng** (bong bóng trắng nền tối).
