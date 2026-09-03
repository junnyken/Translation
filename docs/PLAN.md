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


## E15 — Hướng chữ & SFX cách điệu (2026-08-29)

✅ **Backend xong** (`779 test`): giữ lại đường bao dòng của OCR, bộ chuẩn hoá góc, bộ nhận biết
hướng có bằng chứng, bảng `region_text_orientation`, 3 endpoint, đếm riêng lúc xuất.

❌ **Chưa dựng giao diện**, chưa chạy Run A–D.

⛔ **Dựng chữ dọc cố ý để TẮT** — spec có điều kiện dừng, và thực tế thiếu 2/3 điều kiện: không
có ảnh mẫu chữ dọc hợp pháp, và bộ nhận diện không cho hình học dòng chữ.

Ba bài học:

- **Đường bao dòng của OCR là bằng chứng hình học DUY NHẤT về hướng chữ** — và nó chỉ tồn tại ở
  bước OCR. Sau khi xoá chữ, thoại trong bong bóng còn 0–4 điểm ảnh tối.
- **Góc thô của `minAreaRect` không phân biệt được 0° với 90°** (cùng cho `angle=90.0`, chỉ khác
  `w`/`h`). Đo trên hình biết trước đáp án, không đoán.
- **Nhận ra hướng ≠ dựng được chữ theo hướng đó.** Trạng thái `unavailable` sinh ra chính để nói
  điều này thay vì im lặng căn ngang.


## E1 — Tiện ích Chrome mở nhanh (2026-08-30)

✅ **Xong và đã đo thật** (`282 test đơn vị/thành phần + 41 mục bấm thật trên Chromium 151`):
tiện ích Manifest V3, 2 quyền (`storage`, `sidePanel`), `host_permissions` **rỗng**, không content
script, **không có bước build**, **không thêm/sửa một endpoint backend nào**.

Audit trước khi dựng làm hẹp phạm vi ở 4 chỗ; chi tiết `extension/README.md` §1.

Ba bài học đáng nhớ — cả ba chỉ lộ ra ở **lượt bấm thật**, không lượt test đơn vị nào bắt được:

- **Nút trong `<form>` mà để `type="button"` thì không bao giờ gửi form.** Màn đầu của tiện ích
  hoàn toàn vô dụng với người bấm chuột; test đơn vị `dispatchEvent(submit)` thẳng vào form nên
  đi vòng qua đúng cái nút hỏng.
- **`/healthz` ở cổng giao diện trả về trang HTML kèm 200 + `ACAO: *`.** Máy chủ dev của Vite trả
  SPA cho mọi đường lạ, nên một bộ kiểm chỉ nhìn mã 200 sẽ báo "đã kết nối" trong khi API đã chết.
  Phải gọi `/api/v1/*` — đường duy nhất thật sự đi xuống backend.
- **Trạng thái kết nối phải có BA giá trị.** Chỉ true/false thì panel nhấp nháy "Chưa kết nối"
  trong lúc đang kiểm — khẳng định một thất bại chưa hề đo được, đúng loại nói quá mà M1–M10 cấm.

Còn một chỗ đo sai ở lượt đầu và đã sửa lại trong tài liệu: **CORS không chặn** khi đi qua địa chỉ
web app (Vite proxy `/api` và tự thêm `ACAO: *`); chỉ bị chặn khi gọi thẳng API. Bản dựng prod
(nginx) thì ngược lại — không proxy `/api` nên tiện ích lùi về chế độ chỉ-mở-link.

⚠️ **Còn treo:** hành vi bấm biểu tượng để mở Side Panel chưa bấm được trong Chromium headless —
cần một lượt bấm tay để xác nhận.


## E15 phần 2 — Giao diện hướng chữ + Run A–D (2026-08-30)

✅ **Đóng phần routing + giao diện** (`158 test giao diện`, +63): nhãn hướng chữ đứng riêng cạnh
nhãn căn chữ/chất lượng/nhất quán/vùng an toàn, bộ lọc 5 mục, khối giải thích dịch đủ 15 mã lý do,
thẻ tổng hợp có ô riêng cho "chưa kiểm", khối cảnh báo xuất tách riêng.

Run A/C/D đạt 10/10 trên chapter thật; giao diện 14/14 bấm thật trên Chromium, số trên màn hình
**khớp đúng** số trong CSDL.

⛔ **Run B: BLOCKED.** Bốn vật cản độc lập, và cái đáng nhớ nhất **không phải** chuyện thiếu ảnh:
`MangaOCREngine.recognize()` trả `(text, None)` — không có đường bao dòng, mà đó là đường DUY NHẤT
tới được `vertical_ttb`. **Có ảnh tiếng Nhật hoàn hảo cũng không mở khoá được Run B.**

Ba bài học:

- **Worker không nạp lại mã Python khi tệp đổi.** Container chạy 44 giờ = khởi động trước khi E15
  được commit ⇒ toàn bộ mã E15 **chưa từng chạy một lần nào**, dù tệp đã nằm trên đĩa qua volume.
  Bảng rỗng sạch không phải vì luật sai, mà vì luật chưa bao giờ được gọi.
- **libraqm có trên máy dev, KHÔNG có trong worker.** Option A dựng chữ dọc sẽ xanh hết trên máy
  dev rồi hỏng im lặng ở nơi thật sự chạy. Đo ở máy dev là đo sai chỗ.
- **Test "đúng nhưng rỗng" phải được gọi tên.** Run C đạt 3/3 với **0 vùng chữ nghiêng** trong dữ
  liệu — nó chỉ chứng minh không ai vi phạm, không chứng minh đường xử lý chạy đúng.

⚠️ **Chưa đủ căn cứ mở E16** — tần suất chữ nghiêng đo được là 0/9, mẫu quá nhỏ.


## E15 — hai tầng kết luận (chốt 2026-08-30)

### E15-A — Orientation routing & UI: **CLOSED**

- Giao diện trạng thái/điều hướng hướng chữ hoàn chỉnh, dùng lại `StatusBadge` của E11 + khối
  giải thích theo khuôn E14.
- Huy hiệu hướng chữ **tách riêng** khỏi fit status (M6), quality (E12), consistency (E13) và
  safe-area (E14) — không gộp thành một icon.
- Có bộ lọc theo hướng chữ và bảng dịch mã lý do → diễn giải tiếng Việt (15 mã, khớp 1:1 với
  `LyDo.TAT_CA` của backend).
- Trạng thái "chưa kiểm / chưa xác định" hiển thị **riêng**, không bị gộp thành thành công.
- Run A (chữ ngang không hồi quy) và Run D (sửa tay + cảnh báo xuất) đạt.
- Đo giao diện trên Chromium đạt, số hiển thị **khớp CSDL**.
- Bộ hồi quy giữ xanh theo số đo thực tế tại thời điểm đóng (xem `TEST_LOG § E15.14`).

### E15-B — Dựng chữ dọc tiếng Việt: **BLOCKED (giới hạn bằng chứng ở tầng cấu trúc)**

Đây **không** phải chuyện thiếu ảnh mẫu. Chặn nằm ở tầng bằng chứng/hình học:

- `MangaOCREngine.recognize()` hiện chỉ trả `(text, None)`. Lớp này **không có**
  `recognize_with_layout`, nên hợp đồng OCR cho tiếng Nhật không mang theo hình học dòng chữ,
  metadata hướng chữ hay đa giác dòng nào.
- `analyzer` chỉ tới được `vertical_ttb` qua mã `ocr_line_geometry_vertical`. Không có nguồn đó
  thì **không có đường nào** đặt được `vertical_ttb + ready` — kể cả với ảnh tiếng Nhật hoàn hảo.
- Adapter CTD đang triển khai **không có** đường ghi kết quả hình học nào đã được kiểm chứng để
  thay thế nguồn trên.

**Phát hiện về môi trường:**

- RAQM trong worker: `False`.
- RAQM trong virtualenv của máy dev: `True`.

⇒ **Bất kỳ bộ dựng chữ dọc nào chỉ được kiểm trong virtualenv của máy dev đều KHÔNG có giá trị**
đối với đường dựng chữ thật đang chạy trong worker.

### Bảng năng lực

| Năng lực | Trạng thái |
|---|---|
| Thoại ngang (horizontal dialogue) | **Supported** |
| Nhận biết & điều hướng hướng chữ + giao diện | **Supported** |
| Điều hướng/rà soát SFX | **Supported**, nhưng mẫu thật hiện quá nhỏ để khẳng định rộng (n=9, `rotated_horizontal=0`) |
| Nhận biết/điều hướng chữ dọc có đủ bằng chứng | **Partial / chỉ để rà soát** |
| Dựng chữ dọc tiếng Việt | **Blocked** về mặt cấu trúc |
| Dựng chữ nghiêng/cách điệu | **Không hỗ trợ**; chỉ rà soát |
| E16 đặt chữ xoay | **Chưa được duyệt**; chưa đủ bằng chứng thật |

> **Run C là pass RỖNG.** 3/3 assertion đạt nhưng dữ liệu thật có **0** vùng chữ nghiêng trên
> n=9 — chúng chỉ chứng minh "không vùng nào vi phạm", **không** chứng minh đường xử lý chữ
> nghiêng đã được test thành công. Không được đọc thành "rotated text đã test xong".


## E1a — Siết CORS API local & proxy Vite (2026-08-30)

✅ **CLOSED.** Trước E1a, **bất kỳ website nào** đang mở cũng đọc được `GET /api/v1/projects/{id}`
của Translation local: Vite 6.0.7 mặc định `server.cors: true` ⇒ gắn `ACAO: *` vào mọi phản hồi,
kể cả phản hồi proxy `/api` xuống backend.

Nay **chặn mặc định**: máy chủ dev không phát header CORS nào trừ khi có origin khai tường minh.
Giao diện web không ảnh hưởng (nó gọi API **cùng nguồn**). Tiện ích E1 lùi về **chỉ-mở-link** ở
cấu hình mặc định.

Đo thật trên Chromium **17/17, hai lần** (mặc định và đã-khai-origin): website lạ ở cổng 9999 và
`localhost.evil.example` (ánh xạ loopback) đều **không đọc được** API — kể cả sau khi khởi động
lại container.

Ba điều đáng nhớ:

- **Giao diện web chưa bao giờ cần CORS.** Cùng nguồn thì trình duyệt không chạy phép kiểm. Nên
  danh sách trắng **rỗng** mới là câu nói đúng sự thật, chứ không phải "khai sẵn origin giao diện".
- **`worker: khong_ro` không nói worker khoẻ hay chết** — nó nghĩa là *API không biết*. Đo sức
  khoẻ worker phải bằng `celery inspect ping` + throughput job.
- **`/healthz` ở cổng giao diện trả trang SPA kèm `text/html`** — 200 không phải bằng chứng API sống.

⚠️ **CORS không phải xác thực.** Vẫn chưa có auth/multi-user/TLS; phần siết này áp cho **máy chủ
dev local**, không được đọc thành "an toàn cho production". Chi tiết: `docs/SECURITY.md`.

⚠️ **Còn treo:** chưa bấm tay biểu tượng tiện ích (môi trường không có display server).


## Deploy 001 — lên GitHub + VibeHost (2026-08-30/31)

✅ Đẩy `7ca8af6..45c0af2` lên GitHub và triển khai: `translation-api` **v20→v21**,
`translation-web` **v12→v13**. Trước đó bản hosted chạy mã từ 29/08 15:49 — cũ hơn E1, E15 phần 2,
phần đóng E15 và E1a.

Smoke sau deploy **11/11 trên Chromium thật**; CORS hosted chặt y như trước deploy
(không wildcard, không phản chiếu, không credentials).

Ba điều đáng nhớ:

- **Push KHÔNG tự deploy.** VibeHost lấy nguồn từ GitHub nhưng phải bấm redeploy thủ công —
  `lastDeployedAt` không đổi sau khi push.
- **Không có service worker riêng.** Worker chạy chung trong `translation-api` (`ROLE=all`).
  Và `worker.trang_thai = "starting"` **không** chứng minh worker đang chạy: script chỉ ghi trạng
  thái đó một lần lúc khởi động, không bao giờ ghi `running`.
- **Không có build SHA để đối chiếu phiên bản.** Phải chứng minh gián tiếp: phân biệt route
  tồn tại/không tồn tại bằng **thân 404**, và tìm chuỗi giao diện E15 trong bundle đã build.

⚠️ **Còn treo:** tag `v1.5-E15-closed` + `v1.6-E1a-cors-hardening` chưa đẩy; Pilot/UAT chưa chạy;
`GEMINI_API_KEYS` trên host đang để `isSecret: false`; chưa xác minh volume lưu ảnh trên host.


## P3a — Sẵn sàng Pilot/UAT trên VibeHost (2026-08-31) ⛔ **BLOCKED**

Chạy **một** trang smoke tự vẽ qua giao diện hosted để kiểm điều kiện vận hành trước Pilot/UAT.

**Tin tốt:** pipeline hosted chạy trọn trong **157 giây**, không OOM. Worker chứng minh được là
tiêu thụ việc thật (log celery + 5 lần chuyển trạng thái + hiện vật ảnh), **không** dựa vào
`worker.trang_thai` (trường đó kẹt `starting` vĩnh viễn). LaMa gom cụm xong trong **11,4s** trên
host 4 GB. E15 chạy thật trên host (`horizontal_ltr=2, tt_ready=2`).

**Tin chặn:** sau một lần **Triển khai lại** (v22, cùng mã), **toàn bộ ảnh biến mất** trong khi
Postgres managed vẫn giữ bản ghi `typeset_done`:

```
clean-image  69.486 byte  ->  404 "Đường dẫn ảnh clean có trong DB nhưng file không còn"
preview      98.060 byte  ->  404
```

Đường lưu thật là **`/app/storage`** — lớp ghi của container, không phải volume bền.

⇒ Chapter rơi vào trạng thái **nói dối**: giao diện đọc CSDL thấy `typeset_done` nên trình bày như
đã xong, còn ảnh thì 404. Chapter cũ `ddc7019b…` (28/08) đã ở tình trạng đó từ lâu mà không ai biết.

**KHÔNG chạy Pilot/UAT 10–20 trang.** Mini-spec kế tiếp phải là **gắn volume bền cho
`/app/storage`** — chạy pilot trên lưu trữ tạm là cách chắc chắn nhất để mất công và mất lòng tin.

Một bài học phụ: **MCP từ chối redeploy cùng mã** (`NO_CHANGE`), nhưng nút "Triển khai lại" trên
giao diện thì không kiểm — hai đường có hành vi khác nhau.


## P3b — Lưu trữ hiện vật bền (2026-08-31) ⛔ **BLOCKED**

Audit xong, **không viết mã**. Lý do dừng: **VibeHost không có cơ chế volume bền** — không có
trên giao diện (chỉ có "Tạo database" và "Sao lưu"), không có công cụ MCP, và khoá không có
phạm vi lưu trữ. Theo §5.2(5) thì đây là điều kiện dừng.

Audit vẫn thu hẹp phạm vi đáng kể cho lần sau:

- **Đã có** lớp trừu tượng `IObjectStorage` — không cần dựng mới.
- **Không có** drift "ghi ở A đọc ở B": mọi nơi đọc chung `settings.storage_local_root`.
  Trên host biến môi trường ghi đè mặc định `/data/storage` thành `/app/storage` — đó là lựa
  chọn có chủ đích, không phải lỗi cấu hình.
- **M8 xuất dựng lại từ ảnh clean + TypesetResult, KHÔNG đọc preview**
  (`renderer.draw(clean_image_abs, regions)`) ⇒ cổng chặn xuất hẹp hơn spec giả định.
- `LocalObjectStorage._abs()` không kiểm traversal: `root / "/etc/passwd"` cho ra `/etc/passwd`.
  Chưa khai thác được (mọi lời gọi lấy giá trị từ CSDL) nhưng phải đóng khi làm tiếp.
- **Mã đã chừa sẵn lối thoát từ M1**: `storage_backend: Literal["local","supabase"]` +
  `SupabaseStorageNotConfigured`. Nếu nền tảng không có volume thì đây là đường đi.

⚠️ **Đính chính báo cáo P3a của chính tôi:** tôi từng viết chapter 28/08 "cũng bị orphan". Đo lại
thì nó có `clean_image_path: null` — chưa từng có ảnh clean để mất, nên 404 là đúng. Chỉ có
**một** orphan được chứng minh, không phải hai.

**Việc kế tiếp (một việc):** hỏi Vibe Host xem gói Pro có cấp volume bền gắn vào đường tuỳ ý
không. Câu trả lời quyết định mini-spec sau là "gắn volume 1 GB" (rẻ) hay "dựng adapter lưu trữ
đối tượng sau IObjectStorage" (đắt hơn nhiều).


## P3c — Dò năng lực lưu trữ VibeHost (2026-08-31) ✅ **HOÀN TẤT**

Chỉ đọc, không sửa gì. Trả lời dứt khoát câu hỏi khiến P3b dừng.

**Vibe Host Pro KHÔNG cấp được volume bền.** Và đây không phải chuyện thiếu quyền của một khoá —
nền tảng không có khái niệm đó trong mô hình tài nguyên. Bốn trục bằng chứng:

1. **Cả 4 tài khoản** (3 tài khoản thật sau 4 cổng MCP) có **đúng cùng** bộ phạm vi
   `read, deploy, runtime:write, env:write` — không khoá nào có phạm vi lưu trữ.
2. **`appdata = 0` trên cả 4** — 12 dịch vụ đang chạy, không cái nào từng cấp phát 1 byte. Hạng
   mục có trong sổ kế toán nhưng không có đường đổ dữ liệu vào (làm yếu hẳn manh mối P3b nêu).
3. **Mô hình tài nguyên không có chiều đĩa** — `get_resources` chỉ trả CPU/RAM (min/max/free),
   `set_resources` chỉ nhận `cpu`+`ram`. Không có nút để vặn, chứ không phải bị khoá tay.
4. **Không công cụ ghi nào nhận khai báo volume, kể cả `create_project`.** Sinh ra đã không có
   thì sau không gắn thêm được. Không có `create_stack`, `list_stacks` trả `[]` ⇒ lối thoát
   docker-compose (compose tự khai báo volume) **không với tới được** từ API.

**Phát hiện đổi hướng việc kế tiếp:** nền tảng **có** lưu trữ bền — nhưng là **cơ sở dữ liệu**,
không phải đĩa (`postgresql` primary + `redis`, và `databases`/`backups` là hạng mục riêng trong
sổ lưu trữ). Chính lỗi orphan đã chứng minh CSDL sống sót qua deploy.

⚠️ **Bẫy đã ghi lại:** workspace có 4 cổng MCP trỏ 3 tài khoản khác nhau. Translation nằm ở
**`vibehost1`** (`trieunt1@`). P3b không ghi cổng nào — lần sau phải ghi.

**Khung quyết định đã đổi.** P3b đóng khung "CÓ thì rẻ / KHÔNG thì đắt". Trả lời là KHÔNG, còn
lại A (Postgres làm kho hiện vật) và B (kho đối tượng ngoài) — nhưng **cả hai gánh chung phần
việc nặng giống hệt nhau: `abs_path()` phải thôi làm hợp đồng đọc/ghi** (3 chỗ ghi, 3 chỗ đọc,
+ `SafeAreaService` nhận thẳng root). ⇒ **Chọn A hay B không phải thứ chặn việc** — làm xong
refactor rồi chốt cũng kịp.

**Việc kế tiếp:** một câu hỏi cho support (không phải mini-spec) — (a) bảng điều khiển/support có
đĩa bền nào không lộ ra ở API không, và (b) **hạn mức lưu trữ của gói là bao nhiêu** (`whoami`
không trả trường hạn mức, `canUpgrade: false`) — phương án A phụ thuộc con số (b).


## P3d — Bỏ `abs_path()` làm hợp đồng đọc/ghi (2026-08-31) ✅ **XONG, ĐÃ DEPLOY**

Làm **phần việc chung** mà P3c chỉ ra: Postgres (A) và kho đối tượng ngoài (B) đều bị chặn bởi
cùng một thứ, nên gỡ thứ đó trước, chốt A/B sau.

`abs_path()` **không còn tồn tại**. Viết adapter Postgres/S3 nay là viết **một lớp duy nhất**
hiện thực `IObjectStorage`, không phải sờ lại từng chỗ gọi.

**Phạm vi thật lớn hơn P3c ước lượng: 18 chỗ, không phải 7.** Chỗ bỏ sót là
`resolve_image_path()` — một hàm THỨ HAI làm đúng việc của `abs_path()` nhưng mang tên khác, nên
không lọt phép đếm theo tên. ⇒ đếm theo *hành vi*, đừng đếm theo *tên hàm*.

**Thiết kế:** ranh giới vật chất hoá — `kho → fetch_to() → thư mục tạm → engine → save_file() → kho`.
Engine bên thứ ba bắt buộc cần đường dẫn thật, nhưng chỗ đó **không được là lòng kho**; nếu là
lòng kho thì kho buộc phải là hệ tệp mãi mãi. Đã cân nhắc và loại phương án zero-copy cho backend
local vì nó giữ nguyên đúng cái bẫy cũ.

Được thêm (không phải mục tiêu, nhưng có thật):
- **Đóng lỗ path traversal**: `root / "/etc/passwd"` trước đây cho ra `/etc/passwd` — path tuyệt
  đối NUỐT luôn root. Có test dựng tệp thật ngoài kho rồi khẳng định nó không bị ghi đè.
- **Ghi nguyên tử ở mọi đường ghi** (trước chỉ có đường xuất).
- **Vân tay E14 rẻ đi**: trang 30 vùng từ 30 lượt `stat()` xuống còn 1.
- ETag/304 cho 3 endpoint trả tệp — **giữ nguyên** hành vi cũ chứ không phải thêm tính năng
  (`must-revalidate` mà không có ETag = tải lại nguyên ~3MB mỗi lượt xem).

**Đánh đổi đã nhận:** mất hỗ trợ `Range` (tải tiếp đoạn giữa chừng) ở 3 endpoint đó.

Test: **801 passed, 6 skipped** (nền 779) — +22 tệp mới `test_storage_unit.py`, **0 test bị xoá**.
Path ảnh clean **không đổi** ⇒ không migration.

⚠️ **P3d KHÔNG làm hiện vật bền** — nó dọn đường, không lát đường. Trên host ảnh vẫn mất sạch mỗi
lần triển khai lại. **Chưa deploy** (chưa có gì để deploy làm đổi thực trạng).

**Việc kế tiếp:** vẫn là câu hỏi cho support ở P3c — hạn mức lưu trữ của gói — rồi viết đúng một
lớp adapter (A hoặc B) và deploy cùng nó.


## P3e — Kho hiện vật trong Postgres (2026-08-31) ✅ **XONG, ĐÃ DEPLOY + đo thật**

Mảnh cuối khiến trang "đã canh chữ xong" mà bấm vào thì 404. P3c dò ra nền tảng không có volume
bền; P3d gỡ `abs_path()`; P3e **viết lớp kho** đặt hiện vật vào bảng `artifact_blob`.

**Chốt A (Postgres), không phải B.** Chủ dự án cung cấp con số P3c còn thiếu: **hạn mức 20 GB**.
Đang dùng 1,26 GB ⇒ còn ~18,7 GB ≈ **~1.400 trang**. Pilot 20 trang cần ~786 MB (đã tính hệ số
×3). B (S3/Supabase) đổi lấy nhà cung cấp mới + bộ khoá mới + chi phí chưa đo, để giải một bài
toán dung lượng **không tồn tại** ở quy mô này.

Nói thẳng: nhét ảnh vào CSDL bình thường là ý tồi — ở đây nó là lựa chọn *khả thi duy nhất còn
lại*. Nhờ P3d, đổi sang B về sau chỉ là viết thêm một lớp. **Ngưỡng nên xét đổi: quá ~10 GB hiện
vật, hoặc khi cần CDN.**

Bốn quyết định nhỏ, mỗi cái chữa một lỗi cụ thể: `SET STORAGE EXTERNAL` (PNG/ZIP đã nén, đừng nén
lại) · `size_bytes` tách khỏi `data` (`stat()` chạy ở mọi lượt phục vụ HTTP để dựng ETag) · index
`text_pattern_ops` (LIKE tiền tố không dùng được index dưới collation mặc định) · thoát `_`/`%`
khi dựng mẫu LIKE (tên thật **có** `_`: `…_clean.png`, quên thoát là xoá nhầm project khác).

Tầng HTTP async gọi kho đồng bộ qua `run_in_threadpool` — gọi thẳng sẽ chặn event loop.

Test: **823 passed** (nền 801). Hai thứ đáng kể:
- Fixture `kho` **parametrize 2 backend** ⇒ 19 test hợp đồng chạy hai lượt. Không làm vậy thì
  "thay backend được" mãi mãi chỉ là lời hứa.
- `test_storage_durability_integration.py` mô phỏng redeploy bằng cách **xoá sạch hệ tệp**, theo
  **cặp**: `postgres` sống sót (200, đúng byte) / `local` mất (404 trong khi DB vẫn khai có ảnh).
  Cái thứ hai khẳng định *điều sai đang xảy ra trên host*; ngày nào nó đỏ là nền tảng đã có volume.

⚠️ **CHƯA DEPLOY.** Deploy cần đúng 3 bước: push (xong) → đặt `STORAGE_BACKEND=postgres` trên
`translation-api` → redeploy (migration `0010_p3e` tự chạy lúc khởi động, hỏng là dừng hẳn).
Rollback = đặt lại `local` + redeploy, không mất gì.

**Còn một quyết định phải hỏi chủ dự án:** hàng dữ liệu cũ vẫn trỏ tới hiện vật đã mất. P3e làm
hiện vật **từ nay** bền, **không** hồi sinh được ảnh đã mất. Ba lựa chọn: để nguyên / dọn cho
`clean_image_path=NULL` + lùi status (§B2 `reconcile_legacy` của P3b) / xoá chapter cũ nạp lại từ
ảnh gốc. Đây là quyết định về **dữ liệu**, không phải kỹ thuật.


## P3f — Đối chiếu bản ghi ↔ hiện vật (2026-08-31) ✅ **XONG, ĐÃ CHẠY chế độ sửa (5 trang)**

P3e làm hiện vật từ nay bền nhưng **không hồi sinh được ảnh đã mất**, nên trang cũ vẫn khai "đã
canh chữ xong" mà bấm vào thì 404 — đúng thứ `CLAUDE.md §3` cấm. **Bản ghi là lời khai; hiện vật
là bằng chứng. Mất bằng chứng thì rút lời khai.**

Không xoá bản dịch (chúng ở trong CSDL, còn nguyên và vẫn đúng) — chỉ rút lời khai về ảnh, và lùi
`status` tới **mốc gần nhất còn bằng chứng**: còn OCR ⇒ `ocr_done`, còn vùng ⇒ `detected`, chưa
gì ⇒ `queued`. Mất riêng ảnh xem thử ⇒ `translated`. Cố ý không qua `assert_transition` vì đây là
sửa chữa, không phải một bước pipeline.

**Bẫy đã tránh:** `png_single` lưu `output_path` là một THƯ MỤC, mà `exists()` luôn False với thư
mục ở cả hai backend ⇒ hỏi mỗi `exists()` là kết oan mọi lần xuất PNG. Phải hỏi thêm `list_prefix`.

Chạy trên host bằng biến `RECONCILE_LEGACY` (`off|report|apply`) trong `deploy-start.sh`, vì nền
tảng không cho chạy lệnh trong container. Lỗi ở đây **không chặn khởi động** (khác migration).
Không làm thành endpoint HTTP: hệ thống chưa có auth.

Test: **831 passed** (nền 823). Test gắt nhất là *chế độ chỉ-đếm không ghi một chữ nào* — công cụ
sửa dữ liệu mà lỡ ghi lúc người ta tưởng nó chỉ đếm thì tệ hơn không có công cụ.

**Việc kế tiếp:** chạy `RECONCILE_LEGACY=report` trên host để xem thiệt hại thật, rồi mới `apply`.

### P3e + P3f — kết quả CHẠY THẬT trên host (2026-08-31)

Đã deploy và đo trên `translation-api` (vibehost1 / `trieunt1@`), `STORAGE_BACKEND=postgres`.

**Hiện vật đã bền — đo được:** tải một trang PNG thật lên, pipeline chạy hết tới `typeset_done`
(detect ra 2 vùng conf 0,774 / 0,573 — khớp 2 bong bóng đã vẽ, không phải trạng thái nhảy suông),
rồi **redeploy 3 lần**. Sau mỗi lần, `clean-image` và `typeset-preview` vẫn trả **200** với đúng
số byte (14.319 / 16.652), PNG thật 1200×1700; `If-None-Match` trả **304 / 0 byte**.

**Đối chứng đắt giá nhất** đến từ chính lượt quét đối chiếu: cùng một lần quét, cùng một máy —
**5 trang tạo TRƯỚC P3e mất hiện vật, trang tạo SAU P3e thì không.** Dữ liệu thật tự phân đôi
đúng theo ranh giới P3e; không bộ test nào dựng ra được đối chứng như vậy.

**Đã dọn 5 trang mồ côi:** tất cả về `status=ocr_done` + `clean_image_path=None`. Bản dịch và OCR
còn nguyên. `RECONCILE_LEGACY` đã đặt lại `off`.

**Hai lỗi bắt được nhờ chạy thật:**
1. Chế độ chỉ-đếm **đếm một trang hai lần** (báo 10, thật ra 5) vì nó dựa vào tác dụng phụ của
   chế độ ghi. Đã sửa + test hồi quy. *Chế độ khô mà dựa vào tác dụng phụ của chế độ ướt thì sẽ
   nói dối đúng lúc người ta cần tin nó nhất.*
2. **Nhật ký chạy không sống sót qua deploy** — không có log của chính lượt sửa. Việc cần dấu vết
   kiểm toán phải ghi vào CSDL, không trông vào log.


## P3g — Trả lại `Range` + bỏ nạp cả hiện vật vào RAM + đo độ trễ (2026-08-31) ✅ **XONG, ĐÃ DEPLOY**

Đóng ba khoản nợ P3d/P3e đã nhận có chủ đích. Hai cái đầu hoá ra là **một** bài toán: có
`read_range()` thì có luôn cả `Range` lẫn luồng lười.

Backend CSDL đọc bằng `substr()` phía máy chủ; `open_read()` trả luồng **tua được** (PIL tua tới
lui trong header ảnh nên luồng chỉ-đọc-tiếp sẽ làm hỏng mọi chỗ dùng ảnh). RAM nay tỉ lệ với
**khối đang đọc** (256KB), không phải với kích thước hiện vật.

HTTP: `Accept-Ranges`, 206, 416 kèm kích thước thật, `If-Range` (lệch thì trả NGUYÊN tệp — nối
đoạn của bản cũ vào phần đã tải sẽ tạo một tệp lai không của ai cả), cú pháp hỏng thì bỏ qua
header theo RFC 9110 thay vì nổ.

Test: **856 passed** (nền 832). Hai test **đếm byte thật sự kéo về từ CSDL** — không có phép đếm
đó thì "đọc lười" chỉ là một khẳng định trong docstring.

**Đo thật trên host, hiện vật 6,76 MB** (kết nối dùng lại; mốc nền `/healthz` 3,7 ms):

```
stat() + ETag                      ≈   3,1 ms
Range 8KB (đầu tệp)                ≈   4,8 ms
Range 64KB (GIỮA tệp)              ≈   5,5 ms   <- bằng 1/20 đọc nguyên tệp
đọc + phát NGUYÊN hiện vật         ≈ 111,0 ms   (≈61 MB/s, nghẽn ở băng thông)
```

Đọc **giữa** tệp rẻ ngang đọc **đầu** tệp ⇒ `SET STORAGE EXTERNAL` (P3e) thật sự cho giải TOAST
một phần. Và `stat()` trên 6,76 MB tốn đúng bằng trên 14 KB ⇒ tách `size_bytes` ra cột riêng là
cần thật. **CSDL không phải chỗ nghẽn.**

Hai lỗi của chính tôi, đều bị bắt: (1) `open_read` che `UnsafeObjectPath` thành "không tìm thấy" —
hàm *hỏi han* được phép nuốt lỗi, hàm *ra lệnh* thì không; (2) phép đo độ trễ đầu tiên dùng `curl`
mỗi lượt một tiến trình nên bắt tay TLS lại từ đầu, chi phí đó át phần việc máy chủ tới mức ra
**số âm** — phép đo không tách được chi phí thiết lập kết nối thì không đo cái nó tưởng nó đo.


## P3h — Chặn OOM worker: tắt arena ONNX cho LaMa, trộn theo dải, đo được RAM (2026-08-31) ✅ **ĐÃ DEPLOY + KIỂM CHỨNG**

Sự cố THẬT trong Pilot 6 trang (Phase 3D): worker bị **OOM killer giết** (`exit 137`), API tụt từ
3,4 ms xuống 10–42 s rồi tắt tiếng; 8 lượt thăm dò chỉ 3 lượt thành công; log runtime nền tảng
cũng mất (`wings_error`).

**Nguyên nhân gốc:** LaMa là model **dynamic shape** và ta chạy nó theo từng cụm bong bóng — mỗi
cụm một kích thước. Session lại dùng `SessionOptions()` mặc định, tức **CPU memory arena BẬT**:
arena cấp một khối cho MỖI shape mới và **không trả lại**. Càng nhiều cụm/nhiều trang càng phình.
Nó giải thích đúng hình dạng sự cố mà "thiếu RAM" không giải thích được: **một** trang ở P3a chạy
trọn 157 s không sao, **sáu** trang thì chết.

Sửa ba việc: (1) `enable_cpu_mem_arena=False` cho LaMa, **giữ BẬT cho CTD** vì CTD letterbox về
một kích thước cố định nên chỉ có một shape — phân biệt có lý do, không phải tắt bừa; (2) trộn ảnh
theo dải 256 dòng thay vì một biểu thức cho cả trang; (3) `app/workers/bo_nho.py` đọc RSS từ
`/proc/self/statm`, ghi mốc ở ranh giới các bước, kèm **van xả** nhả model không cần cho bước đang
chạy khi vượt ngưỡng — và `/healthz` trả thêm `rss_mb`.

Đo lại hôm nay bằng `tracemalloc` (tái lập được, giống nhau **từng byte**):

| Cỡ trang | Một biểu thức | Theo dải | Giảm |
|---|---|---|---|
| 1200×1660 (cỡ trang pilot) | 71,7 MB | 14,6 MB | 80 % |
| 1400×2000 | 100,8 MB | 18,5 MB | 82 % |

Test **867 passed / 6 skipped** (nền 856), chạy lại hôm nay đúng con số đó; sau lượt hậu kiểm
tách `_tron_theo_dai()`: **869 passed / 6 skipped, exit 0**.

⛔ **Live Verification CHƯA CHẠY ĐƯỢC.** Lúc viết (31/08 ~19:00) host không phản hồi: `/healthz`
và cả **web tĩnh** đều treo >45 s, TCP 443 kết nối được nhưng **bắt tay TLS không hoàn tất**,
dashboard vẫn báo `online`, `get_runtime_logs` trả `wings_error`. Hai website khác nhau cùng node
chết cùng lúc ⇒ tầng nền tảng, không phải container mình OOM thêm lần nữa.

Ba điều đáng nhớ:

- **`rss_mb` của `/healthz` là RSS tiến trình API, KHÔNG phải worker.** `ROLE=all` chạy celery ở
  tiến trình nền riêng, và **celery mới là thứ bị giết**. RSS worker hiện chỉ vào log — thứ đang
  không lấy được và không sống sót qua deploy. Lỗ hổng quan sát **chưa đóng hẳn**.
- **Hai test phần trộn theo dải chép lại thuật toán vào trong test** thay vì gọi mã sản xuất
  (vòng lặp thật nằm inline trong `LamaInpainter.inpaint()`), nên chúng chứng minh *thuật toán*
  đúng chứ không chứng minh *mã đang chạy* đúng. ✅ **Đã đóng cùng ngày:** tách `_tron_theo_dai()`,
  hai bên gọi chung, thêm 2 test **đo đỉnh bộ nhớ** — trong đó một test có **assert đối chứng**
  bắt mốc cũ phải leo theo chiều cao trang, để phép đo không thể xanh nhầm. Bẫy bắt được lúc đóng:
  mốc đối chiếu chép "cho gọn" (bỏ biến trung gian `blended`) làm mốc **dễ hơn thực tế 1,5 lần** —
  trong numpy một cái tên biến là một mảng chưa được giải phóng.
- **Không cần đặt biến môi trường nào khi deploy** — host không có `INPAINT_CPU_MEM_ARENA` /
  `WORKER_RSS_SOFT_LIMIT_MB` nên cả hai lấy mặc định trong mã. Đổi lại, muốn tắt bản sửa để đối
  chứng thì phải thêm biến.

⚠️ **Còn treo:** chưa push `64c006a`; chưa deploy; chưa chạy lại pilot 6 trang; ngưỡng 2200 MB
chưa có số đo nào chống lưng; van xả chưa từng nổ trong một lượt chạy thật; chưa đo lại tốc độ
inpaint sau khi tắt arena. Chi tiết: `docs/REPORT_P3h_WORKER_MEMORY.md`.


## E17 — Gợi ý thuật ngữ & xưng hô rút từ chính chapter (2026-09-01) ✅ **ĐÃ DEPLOY + KIỂM CHỨNG LIVE**

Yêu cầu của chủ dự án: *"nhập tên bộ truyện để lấy tên + xưng hô nhân vật, chứ ngồi nhập từng cái
rất phiền"*. Màn Thuật ngữ / Giọng nhân vật hiện là hai form trống, người dùng phải tự nhớ và gõ
lại nguyên văn từng danh xưng trước khi rà soát chạy được lần đầu.

**Không làm đúng câu chữ của yêu cầu, và đây là lý do:** hỏi model "truyện X có nhân vật nào" thì
nó **luôn trả lời**, kể cả khi không biết — truyện ít tiếng tăm hoặc trùng tên sẽ ra một dàn nhân
vật nghe rất thật; nó cũng không biết chapter NÀY có ai. Mà thuật ngữ đã duyệt là **luật** dùng để
quét cả chapter, nên duyệt nhầm một tên không tồn tại làm mọi lượt rà soát sau đó báo sai. Vướng
nguyên tắc số 3 (`CLAUDE.md`: evidence-first).

**Đảo chiều:** chữ đã nằm sẵn trong `ocr_result.raw_text`. Máy tìm ứng viên + đếm + trích dẫn
(việc máy làm được); người quyết cách dịch và xưng hô (việc chỉ người làm được). Tầng 3 — nhập tên
bộ truyện — để sau, và nếu làm thì bắt buộc có **cổng đối chiếu**: chỉ hiện tên thật sự xuất hiện
trong chapter này. Cổng đó là thứ biến trí nhớ không kiểm chứng được thành gợi ý kiểm chứng được.

Ba điều đáng nhớ trong bản thiết kế:

- **Bẫy TOÀN CHỮ HOA của tiếng Anh:** chữ lồng trong truyện tranh hay viết hoa hết, lúc đó tín
  hiệu "viết hoa giữa câu" chết sạch và luật ngây thơ sẽ trả về **mọi từ** trong chapter. Phải đo
  tỉ lệ chữ hoa rồi chuyển luật — và ngưỡng phải đo trên fixture thật, không lấy theo cảm tính.
- **Không có nút "Duyệt tất cả".** `target_term` và `definition` là quyết định biên tập; máy điền
  vào đó là quay lại đúng cái bẫy trên. Máy chỉ điền sẵn *thuật ngữ gốc* + *loại* + *trích dẫn*.
- **Ba trạng thái rỗng không được gộp:** "chưa đọc chữ" ≠ "đã tìm, không có" ≠ "đều đã có trong
  glossary" — cùng một bài học với `worker: khong_ro` của E1a.

Tầng 1+2: không bảng mới, không migration, không gọi LLM. Tầng 3 (chốt làm luôn) thì có cả
ba: bảng `term_suggestion_run`, migration `0011_e17`, và một lượt gọi mô hình chạy nền.
ET dự kiến 8,0 h.

**Chủ dự án chốt: làm trọn gói, kèm cả tầng 3.** Việc chạy trước khi P3h đóng là quyết định của
chủ dự án khi được hỏi — ghi ra để nó không thành một quy ước bị bỏ qua trong im lặng.

Đã dựng đủ ba tầng: 2 endpoint chỉ-đọc (`200`) + 1 job nền cho tầng 3 (`202`, nguyên tắc số 4),
bảng `term_suggestion_run` (migration `0011_e17`), bảng ứng viên + tìm tín hiệu xưng hô trên giao
diện. **Ba lỗi thật bắt được nhờ test:** `OCRStatus.done` không tồn tại · đếm hai lần khi hai luật
cùng bắt một chỗ (cùng họ với bẫy P3f) · luật tiếng Anh vứt mất bằng chứng của từ đứng đầu câu.

⛔ **Chưa deploy, chưa chạy trên chapter thật, và tầng 3 chưa từng gọi mô hình thật.** Ba việc bắt
buộc trước khi đóng: `docs/REPORT_E17_TERM_CANDIDATES.md` §7. Thiết kế gốc:
`docs/SPEC_E17_TERM_CANDIDATES.md`.


## P3i — Cảnh báo thiếu thuật ngữ ở cổng xuất (2026-09-03) ✅ **XONG, ĐÃ DEPLOY**

Sinh ra **từ bằng chứng pilot**, không phải từ ý tưởng: chạy thật 6 trang Pepper&Carrot trên host
cho ra nhân vật *Pepper* → **"Hạt tiêu"** (tên gia vị), mà cổng xuất **không hé một lời**.

Gốc rễ: khối "Nhất quán thuật ngữ" chỉ render khi có việc rà soát — mà không có thuật ngữ thì
không sinh việc nào. **Hệ thống im lặng đúng lúc rủi ro cao nhất.**

Sửa: `export-warnings` trả thêm `glossary_approved_count` (chỉ đếm mục **đã duyệt**, vì chỉ mục đã
duyệt mới được dùng khi rà soát); giao diện hiện khối cảnh báo khi bằng 0, **nêu hậu quả kèm ví dụ
có thật** thay vì chỉ nói "chưa có gì".

917 backend + 245 frontend passed. Đã deploy cả API lẫn web, kiểm chứng live: cổng xuất hiện đủ
**5 nhóm có nhãn riêng**.

### Pilot/UAT hosted 6 trang — xem `docs/REPORT_PILOT_UAT_001.md`

Kết quả: **dùng được cho pilot hosted giới hạn**, sau khi sửa một P1 mà chính pilot phát hiện.
6/6 trang · 31/31 vùng đủ OCR+dịch+canh chữ · 12/12 hiện vật mở thật · **parity xuất↔xem thử 3/3
trang trùng từng byte** sau khi đã sửa tay · CBZ CRC toàn vẹn · M10 cưỡng chế thật.

**P1 còn mở duy nhất — cũng là mini-spec kế tiếp được đề xuất:** worker chết ⇒ job đang chạy biến
mất, trang kẹt vĩnh viễn, **không tự chạy lại và không có tín hiệu lý do** (không có endpoint liệt
kê job). Sửa OOM chỉ giảm *tần suất*, không giảm *hậu quả*.

⚠️ **Đính chính trong báo cáo:** tôi từng báo 3 phát hiện UX, **2 trong đó sai** — cả hai do tôi đo
sai (test bằng profile trắng thay vì mở lại phiên; và đo chính thời gian mình tự ngồi chờ). Chi
tiết ở §5.1 của báo cáo pilot.


## P3j — Khôi phục job mồ côi khi worker chết (2026-09-03) ✅ **XONG**

Đóng **P1 duy nhất còn mở** của pilot. Worker chết ⇒ job đang chạy biến mất, trang kẹt vĩnh viễn,
không tự chạy lại, **không có tín hiệu lý do**, và không có endpoint nào để tra.

**Audit đổi hẳn phạm vi.** Ba câu hỏi trả lời từ mã, không đoán:
- `--pool=solo`, **một tiến trình, một container** ⇒ lúc worker khởi động, mọi job `running` đều
  là mồ côi của tiến trình vừa chết. Không có worker thứ hai để giết nhầm.
- Quét `tasks.py`: **chỉ `detecting`** là trạng thái TẠM. Các mốc khác chỉ đặt **khi xong** nên
  vẫn trung thực dù job chết ⇒ **phần lớn trạng thái page KHÔNG cần lùi**. Lùi bừa `ocr_done` về
  `queued` là xoá công việc đã hoàn thành thật.
- Chưa dùng celery signal nào ⇒ `worker_ready` là chỗ sạch.

**Chỉ đánh dấu hỏng, KHÔNG tự chạy lại** — tự chạy lại một job vừa làm chết worker vì hết bộ nhớ
là giết nó lần nữa, thành vòng lặp. Lý do viết cho NGƯỜI đọc, đủ ba phần: chuyện gì xảy ra · dữ
liệu còn nguyên · làm gì tiếp.

Ràng buộc "chỉ một worker" ghi thành **cờ** `worker_sweep_orphan_jobs_on_start`, không ghi thành
lời hứa trong tài liệu. Dọn dẹp hỏng **không chặn** worker nhận việc.

API mới: `GET /pages/{page_id}/jobs`. Test: **927 passed** (nền 917) — bốn test đáng kể nhất kiểm
việc **không đụng vào cái không được đụng** (job đã xong là lịch sử, trạng thái ổn định không lùi,
không tự chạy lại, chế độ chỉ-đếm không ghi).

⛔ **Chưa deploy lúc ghi dòng này.** Giao diện cũng chưa gọi endpoint mới — người vận hành vẫn
phải tra bằng API. Đó là việc kế tiếp gần nhất.

### Kiểm chứng live E17 (2026-09-03)

E17 **chạy đúng trên host** — thử trên đúng chapter pilot, nó rút được chính cái tên đã hỏng:

| Thuật ngữ | Lần | Trang | Lý do |
|---|---|---|---|
| Chaosah | 4 | 1,2,3 | viết hoa giữa câu |
| King | 3 | 3,4 | viết hoa giữa câu |
| **Pepper** | 3 | 1,2,6 | viết hoa giữa câu, đứng đầu câu |

Nhưng lộ **hai khiếm khuyết** (chưa sửa, ghi vào tồn đọng):
- **Dương tính giả**: ứng viên `"of"` bị đoán là `character_name`, lý do *"đứng sau danh xưng
  king"* — luật "chữ sau danh xưng = tên nhân vật" bắn nhầm vào "King **of** …"
- **Bỏ sót**: `Cayenne` là tên nhân vật có thật trong chữ gốc (*"Cayenne is right…"*) nhưng không
  được liệt kê
