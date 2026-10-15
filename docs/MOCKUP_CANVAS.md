# MOCKUP — Translation · Sửa tay kiểu canvas

## Live mockup
- URL: https://translation-mockup.b.matbao.ai
- Responsive: https://translation-mockup.b.matbao.ai/__device/
- Nguồn sửa: factory/translation/mockup/ (sửa file → refresh, không cần build)
- Thiết kế: factory/translation/docs/DESIGN-ARCH.md
- Cập nhật: 2026-10-15

## Màn có trong mockup
| id | Màn | Trạng thái |
|---|---|---|
| canvas | Sửa tay — chọn khung chữ | Chính |
| canvas-but-co | Sửa tay — cọ xoá chữ | Chính |
| canvas-rong | Chưa có trang | Rỗng |
| canvas-loi | Không tải được trang / không có WebGPU | Lỗi |

## Đã kiểm
Đã bấm thử trên Chromium (máy cục bộ):
- Cọ → màn cọ → "Xoá vùng đã tô" → về canvas.
- Nút Xuất mở hộp xuất.
- Trên điện thoại (390px), dải trang ẩn và bảng thuộc tính chuyển xuống dưới canvas.

Chưa mở được link B từ workspace: workspace không có đường mạng tới máy chủ B, mọi mockup B đều
không vào được. Cần mở từ mạng Mắt Bão.

## Việc của BA
Câu chữ trong mockup là bản nháp. BA rà soát và chốt wording trước khi DEV dựng thật.
