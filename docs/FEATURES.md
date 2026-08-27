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
| M5 | Dịch 2 đường: `google_fast` (miễn phí) và `llm_context` (giữ mạch văn cả trang) + reading order | CHƯA |
| M6 | Tự tính cỡ chữ + xuống dòng cho vừa bubble (đo font-metrics thật) | CHƯA |
| M7 | Màn sửa tay: sửa bản dịch, kéo lại khung, đổi font/size | CHƯA |
| M8 | Xuất chapter PNG/CBZ + lưu/mở lại project | CHƯA |
| M9 | Chạy cả chapter theo hàng đợi + xoay API key khi hết quota | CHƯA |
| M10 | Khai báo mục đích sử dụng + nhắc trách nhiệm bản quyền khi export | Một phần: field `intended_use` đã **LIVE** từ M1; modal nhắc + gate export CHƯA |

## Những gì dùng được ngay hôm nay (sau M4)

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

## Những gì **chưa** dùng được (nói thẳng để không hiểu nhầm)

- Chưa dịch được chữ nào: đã có ảnh sạch và chữ gốc, nhưng chưa dịch sang tiếng Việt (M5),
  chưa canh chữ vào khung (M6).
- Chưa có giao diện người dùng — mới chỉ có Swagger để thao tác tay; chưa có ảnh vẽ khung để nhìn bằng mắt (M7).
- **Chưa đo trên trang manga scan thật**: số liệu nhận diện (M2) và độ chính xác đọc chữ (M3)
  hiện chỉ đo trên ảnh tổng hợp do repo tự sinh — chưa nghiệm thu cuối cùng.
- Chưa tự chạy lại khi quá giờ (chỉ ghi `detection_failed`, phải bấm chạy lại) — auto-retry thuộc M9.
- Chưa lưu ảnh lên Supabase Storage (đang lưu trên ổ đĩa của server).
