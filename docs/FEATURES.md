# FEATURES.md — Translation

Tool dịch manga **EN/JP/CN → Tiếng Việt**: tự nhận diện khung chữ (bubble/box), xóa chữ gốc,
dịch theo mạch văn, tự canh cỡ chữ cho vừa khung, cho sửa tay rồi xuất chapter.

> Quy ước đọc bảng: **LIVE** = đã chạy thật và verify · **BUILT** = có code, chưa verify thật ·
> **CHƯA** = chưa làm (thuộc mini-spec ghi kèm). Không đánh dấu LIVE nếu chưa chạy thật một lần.

## Trạng thái theo mini-spec

| ID | Tính năng | Trạng thái |
|---|---|---|
| M1 | Data model 7 bảng + migration 2 chiều + API contract `/api/v1` + interface 5 engine | **LIVE** |
| M2 | Nhận diện khung chữ (comic-text-detector) → `TextRegion` + confidence | CHƯA |
| M3 | OCR theo ngôn ngữ nguồn (manga-ocr cho `ja`, PaddleOCR cho `zh`/`en`) | CHƯA |
| M4 | Xóa chữ gốc bằng LaMa → ảnh clean (giữ nguyên ảnh gốc) | CHƯA |
| M5 | Dịch 2 đường: `google_fast` (miễn phí) và `llm_context` (giữ mạch văn cả trang) + reading order | CHƯA |
| M6 | Tự tính cỡ chữ + xuống dòng cho vừa bubble (đo font-metrics thật) | CHƯA |
| M7 | Màn sửa tay: sửa bản dịch, kéo lại khung, đổi font/size | CHƯA |
| M8 | Xuất chapter PNG/CBZ + lưu/mở lại project | CHƯA |
| M9 | Chạy cả chapter theo hàng đợi + xoay API key khi hết quota | CHƯA |
| M10 | Khai báo mục đích sử dụng + nhắc trách nhiệm bản quyền khi export | Một phần: field `intended_use` đã **LIVE** từ M1; modal nhắc + gate export CHƯA |

## Những gì dùng được ngay hôm nay (sau M1)

- Tạo project dịch (chọn ngôn ngữ nguồn, mục đích sử dụng) qua API/Swagger.
- Upload từng trang ảnh: file được lưu thật, trang vào hàng đợi `queued`, sinh việc `detect` chờ xử lý.
- Xem trạng thái trang và trạng thái việc trong hàng đợi.
- Xem danh sách khung chữ của trang (hiện luôn rỗng — đúng, vì bước nhận diện thuộc M2).

## Những gì **chưa** dùng được (nói thẳng để không hiểu nhầm)

- Chưa dịch được chữ nào: chưa có nhận diện khung, OCR, xóa chữ, dịch, canh chữ.
- Chưa có giao diện người dùng — mới chỉ có Swagger để thao tác tay.
- Chưa có worker xử lý thật: việc `detect` nằm trong hàng đợi nhưng chưa ai làm (M2 mới có).
- Chưa lưu ảnh lên Supabase Storage (đang lưu trên ổ đĩa của server).
