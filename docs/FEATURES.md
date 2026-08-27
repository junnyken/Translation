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
| M3 | OCR theo ngôn ngữ nguồn (manga-ocr cho `ja`, PaddleOCR cho `zh`/`en`) | CHƯA |
| M4 | Xóa chữ gốc bằng LaMa → ảnh clean (giữ nguyên ảnh gốc) | CHƯA |
| M5 | Dịch 2 đường: `google_fast` (miễn phí) và `llm_context` (giữ mạch văn cả trang) + reading order | CHƯA |
| M6 | Tự tính cỡ chữ + xuống dòng cho vừa bubble (đo font-metrics thật) | CHƯA |
| M7 | Màn sửa tay: sửa bản dịch, kéo lại khung, đổi font/size | CHƯA |
| M8 | Xuất chapter PNG/CBZ + lưu/mở lại project | CHƯA |
| M9 | Chạy cả chapter theo hàng đợi + xoay API key khi hết quota | CHƯA |
| M10 | Khai báo mục đích sử dụng + nhắc trách nhiệm bản quyền khi export | Một phần: field `intended_use` đã **LIVE** từ M1; modal nhắc + gate export CHƯA |

## Những gì dùng được ngay hôm nay (sau M2)

- Tạo project dịch (chọn ngôn ngữ nguồn, mục đích sử dụng) qua API/Swagger.
- Upload từng trang ảnh: file được lưu thật, trang vào hàng đợi và **worker tự động nhận diện khung chữ**.
- Xem danh sách khung chữ đã nhận diện của từng trang: toạ độ khung + độ tin cậy + cảnh báo.
  Khung độ tin cậy thấp vẫn hiện (đánh dấu `low_confidence`), khung chồng nhau bị gắn cờ `overlap_suspect`.
- Xem trạng thái trang (`queued → detecting → detected | detection_failed`) và trạng thái việc.
- Chạy lại nhận diện cho 1 trang bằng `POST /pages/{id}/retry-detect` (không tạo khung trùng lặp).

## Những gì **chưa** dùng được (nói thẳng để không hiểu nhầm)

- Chưa dịch được chữ nào: mới nhận diện được **vị trí** khung chữ, chưa đọc chữ (M3), chưa xóa chữ gốc (M4),
  chưa dịch (M5), chưa canh chữ (M6).
- Chưa có giao diện người dùng — mới chỉ có Swagger để thao tác tay; chưa có ảnh vẽ khung để nhìn bằng mắt (M7).
- **Chưa đo trên trang manga scan thật**: số liệu nhận diện hiện có chỉ đo trên ảnh tổng hợp do repo tự sinh.
- Chưa tự chạy lại khi quá giờ (chỉ ghi `detection_failed`, phải bấm chạy lại) — auto-retry thuộc M9.
- Chưa lưu ảnh lên Supabase Storage (đang lưu trên ổ đĩa của server).
