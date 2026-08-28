# FEATURES.md — Translation

Tool dịch manga **EN/JP/CN → Tiếng Việt**: tự nhận diện khung chữ (bubble/box), xóa chữ gốc,
dịch theo mạch văn, tự canh cỡ chữ cho vừa khung, cho sửa tay rồi xuất chapter.

> Quy ước đọc bảng: **LIVE** = đã chạy thật và verify · **BUILT** = có code, chưa verify thật ·
> **CHƯA** = chưa làm (thuộc mini-spec ghi kèm). Không đánh dấu LIVE nếu chưa chạy thật một lần.

## Trạng thái theo mini-spec

| ID | Tính năng | Trạng thái |
|---|---|---|
| M1 | Data model 7 bảng + migration 2 chiều + API contract `/api/v1` + interface 5 engine | **LIVE** |
| M2 | Nhận diện khung chữ (comic-text-detector) → `TextRegion` + confidence | **LIVE** (đo trên ảnh tổng hợp; ảnh manga thật chưa đo — xem TEST_LOG) |
| M3 | OCR theo ngôn ngữ nguồn (manga-ocr cho `ja`, PaddleOCR cho `zh`/`en`) | **LIVE** (đo trên ảnh tổng hợp — provisional, xem TEST_LOG) |
| M4 | Xoá chữ gốc bằng LaMa → ảnh clean (giữ nguyên ảnh gốc) | **LIVE** (đo trên ảnh tổng hợp — provisional, xem TEST_LOG) |
| M5 | Dịch 2 đường: `google_fast` (miễn phí) và `llm_context` (giữ mạch văn cả trang) + reading order | **LIVE** (đo trên ảnh tổng hợp thoại tiếng Anh; manga thật + tiếng Nhật chưa đo — xem TEST_LOG) |
| M6 | Tự tính cỡ chữ + xuống dòng cho vừa bubble (đo font-metrics thật) | **LIVE** (đo trên ảnh tổng hợp; manga thật chưa đo — xem TEST_LOG) |
| M7 | Màn sửa tay: sửa bản dịch, kéo lại khung, đổi font/size | **LIVE** (thao tác thật trên trình duyệt; xem TEST_LOG) |
| M8 | Xuất chapter PNG/CBZ + lưu/mở lại project | **LIVE** (xuất thật 4 trang; chưa mở bằng app đọc truyện thật) |
| M9 | Chạy cả chapter theo hàng đợi + xoay API key khi hết quota | CHƯA |
| M10 | Khai báo mục đích sử dụng + nhắc trách nhiệm bản quyền khi export | Một phần: field `intended_use` đã **LIVE** từ M1; modal nhắc + gate export CHƯA |

## Những gì dùng được ngay hôm nay (sau M8)

- Tạo project dịch (chọn ngôn ngữ nguồn, mục đích sử dụng) qua API/Swagger.
- Upload từng trang ảnh: file được lưu thật, trang vào hàng đợi và **worker tự động nhận diện khung chữ**.
- Xem danh sách khung chữ đã nhận diện của từng trang: toạ độ khung + độ tin cậy + cảnh báo.
  Khung độ tin cậy thấp vẫn hiện (đánh dấu `low_confidence`), khung chồng nhau bị gắn cờ `overlap_suspect`.
- Xem trạng thái trang (`queued → detecting → detected | detection_failed`) và trạng thái việc.
- Chạy lại nhận diện cho 1 trang bằng `POST /pages/{id}/retry-detect` (không tạo khung trùng lặp).
- **Tự đọc chữ trong từng khung** ngay sau khi nhận diện xong (không phải bấm thêm nút):
  tiếng Nhật dùng manga-ocr, tiếng Trung/Anh dùng PaddleOCR theo ngôn ngữ nguồn của project.
- Xem chữ đã đọc được của từng khung qua `GET /pages/{id}/ocr`; vùng đọc không ra chữ được
  đánh dấu `needs_manual` để sửa tay sau, **không bị giấu đi**.
- **Tự xoá chữ gốc khỏi ảnh** ngay sau khi đọc xong, tạo ra ảnh "sạch" để lát nữa chèn chữ dịch.
  Xem/tải ảnh sạch qua `GET /pages/{id}/clean-image`. **Ảnh gốc luôn được giữ nguyên** thành file riêng.
- Hệ thống tự kiểm lại việc xoá bằng cách đọc lại đúng vùng vừa xoá: còn chữ thì trang bị đánh dấu
  `inpaint_needs_review` chứ không âm thầm coi là xong.
- **Dịch cả trang sang tiếng Việt** ngay sau khi xoá chữ xong, theo **đúng thứ tự đọc** của loại truyện
  (manga Nhật đọc phải→trái, truyện Anh/Trung đọc trái→phải) — thứ tự sai là hỏng mạch văn cả trang.
- **Chọn được cách dịch, biết trước cái nào tốn tiền:**
  - `google_fast` — **miễn phí**, dịch từng dòng, không nhìn ngữ cảnh câu trước sau.
  - `llm_context` — gộp cả trang gửi Gemini nên giữ được mạch văn và tự sửa lỗi đọc chữ, **có tốn token**.
  - Mặc định là bản **miễn phí**: hệ thống không bao giờ tự tiêu tiền của bạn khi bạn chưa chọn.
    Đổi bằng `POST /pages/{id}/retry-translate?engine=llm_context`.
- Xem bản dịch từng khung qua `GET /pages/{id}/translation`, kèm **số token đã tiêu thật** của trang đó.
- Nếu bên dịch AI hỏng hoặc hết lượt, hệ thống **tự lùi về bản miễn phí và dán nhãn `fallback_used`** —
  không bao giờ trả về bản dịch rỗng rồi báo là xong. Dòng nào AI không trả thì để `pending`.
- **Tự chèn chữ dịch vào đúng bong bóng** ngay sau khi dịch xong: hệ thống tự chọn cỡ chữ lớn nhất mà
  vẫn vừa khung, tự xuống dòng, căn giữa — và **xem được ngay bằng ảnh** qua
  `GET /pages/{id}/typeset-preview`. Đây là lần đầu có **trang truyện tiếng Việt hoàn chỉnh** để nhìn.
- **Chữ quá dài không bị bóp bé tí cho vừa**: xuống tới cỡ nhỏ nhất mà vẫn không vừa thì vùng đó được
  đánh dấu **cảnh báo tràn khung** (viền đỏ trên ảnh xem thử) để người biên tập sửa tay ở bước sau,
  chứ hệ thống không tự làm chữ bé đến mức không đọc nổi.
- **Không bao giờ ra ô vuông**: nếu font thiếu chữ có dấu tiếng Việt, hệ thống báo lỗi rõ thay vì vẽ
  ô vuông rồi báo thành công.
- **Ảnh gốc và ảnh sạch vẫn nguyên vẹn** — ảnh xem thử là file thứ ba, tách riêng.
- **Có màn hình để sửa tay** (giao diện đầu tiên của dự án, mở ở cổng 5174): nhìn thấy trang truyện
  đã chèn chữ, các khung chữ vẽ chồng lên ảnh, và bảng sửa cho từng vùng.
  - Sửa **bản dịch**, đổi **kiểu chữ**, **ghim cỡ chữ** nếu không ưng cỡ máy tự chọn.
  - **Kéo và co giãn khung chữ** ngay trên ảnh bằng chuột.
  - Bấm lưu là hệ thống **canh lại đúng vùng đó** rồi vẽ lại ảnh — không tính lại cả trang.
  - Có nút **đọc lại chữ gốc** và **dịch lại** cho riêng từng vùng.
- **Không giấu cảnh báo**: mỗi vùng hiện nhãn bằng chữ (“Tràn khung”, “Cần đọc lại”,
  “Khung kém tin cậy”) và có ô bật/tắt để tô cảnh báo lên ảnh.
- **Biết chỗ nào người sửa, chỗ nào máy làm**: mỗi vùng ghi rõ “máy dịch / đã sửa tay”.
- **Xuất cả chapter thành file giao được**: chọn **CBZ** (1 file, mở bằng app đọc truyện tranh),
  **ZIP**, hoặc **PNG** từng trang. Bấm xuất rồi tải về ngay trên màn hình.
- **Xem trước cảnh báo trước khi xuất**: sẽ xuất mấy trang, bỏ qua mấy trang chưa chèn chữ xong,
  còn mấy vùng chữ tràn khung — để bạn chọn xuất luôn hay sửa tay trước.
- **Trang chưa chèn chữ xong thì bỏ qua**, không xuất ảnh trắng không chữ; số trang bỏ qua được nói rõ.
- **Xuất lại bao nhiêu lần cũng được**, file cũ tự bị dọn, không đầy ổ đĩa. Dữ liệu gốc giữ nguyên
  nên sửa tiếp rồi xuất lại thoải mái.

## Những gì **chưa** dùng được (nói thẳng để không hiểu nhầm)

- **Chưa có đăng nhập**: ai mở được đường link là sửa được, và hệ thống chỉ ghi “có người sửa”
  chứ không ghi **ai** sửa.
- **Chưa lùi lại được**: sửa là đè lên bản cũ, không có lịch sử phiên bản. Dữ liệu gốc (khung chữ,
  chữ OCR, bản dịch máy) thì vẫn giữ để đối chiếu.
- **Chưa sửa được nhiều vùng cùng lúc.**
- **Chưa kéo khung được bằng bàn phím** — thao tác kéo khung hiện chỉ dùng chuột được.
- **File CBZ chưa được mở thử bằng app đọc truyện thật** (Tachiyomi/Perfect Viewer) — mới kiểm bằng
  công cụ giải nén, đúng cấu trúc và đúng thứ tự trang.
- **Xuất bằng bản dịch miễn phí có thể ra chữ chưa dịch**: nếu bước đọc chữ dính hai từ vào nhau
  (`IT IS` → `ITIS`), bản miễn phí sẽ để nguyên tiếng Anh. Hệ thống **chưa cảnh báo** điều này trước
  khi xuất — muốn chắc thì dịch lại bằng bản có ngữ cảnh rồi hãy xuất.
- **Nếu máy chủ hết bộ nhớ giữa chừng**, việc đang chạy sẽ treo mãi ở trạng thái “đang chạy” mà
  không báo lỗi — phải nhìn log mới biết.
- Chưa có giao diện người dùng — mới chỉ có Swagger để thao tác tay; chưa có ảnh vẽ khung để nhìn bằng mắt (M7).
- **Chưa đo trên trang manga scan thật**: số liệu nhận diện (M2), độ chính xác đọc chữ (M3),
  xoá chữ (M4), chất lượng dịch (M5) và canh chữ (M6) hiện chỉ đo trên ảnh tổng hợp do repo tự sinh —
  chưa nghiệm thu cuối cùng.
- **Chữ chỉ nằm ngang**: chưa hỗ trợ chữ dọc, chữ xoay nghiêng hay chữ tượng thanh (SFX) cách điệu.
- **Bong bóng dẹt có thể bị chạm mép**: hệ thống tính theo khung chữ nhật bao quanh bong bóng, nên với
  bong bóng rất dẹt chữ vẫn có thể chạm mép cong. Chưa gặp trên ảnh mẫu, cần thử ảnh thật.
- **Đường dịch tiếng Nhật (phải→trái) chưa chạy thật đầu-cuối** — mới verify bằng test tự động.
- Nhiều API key **không** làm tăng hạn mức nếu các key thuộc cùng một project Google
  (Gemini tính giới hạn theo project, không theo key).
- Chưa tự chạy lại khi quá giờ (chỉ ghi `detection_failed`, phải bấm chạy lại) — auto-retry thuộc M9.
- Chưa lưu ảnh lên Supabase Storage (đang lưu trên ổ đĩa của server).
