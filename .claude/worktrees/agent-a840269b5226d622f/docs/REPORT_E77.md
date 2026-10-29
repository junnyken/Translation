# REPORT E77 — Bước kiểm "còn sót chữ" thôi gắn cờ giả trên ô đã xoá trắng trơn

**Ngày:** 2026-10-15 · **Nguồn:** log production sau lần deploy E76: cả hai trang chạy thật đều bị báo
"còn chữ ở 10/10 vùng", và gần như vùng nào cũng đọc ra cùng một câu `そういえば、`.

## Chẩn đoán

Sau khi xoá chữ, worker OCR lại từng vùng để kiểm còn sót chữ không. **manga-ocr nhìn ô trắng trơn vẫn
"đọc" ra một câu hay gặp.** Tái hiện trên trang thật `ja_E12P01`: vùng đã xoá có tỉ lệ mực 0,0000 mà
OCR vẫn trả `そういえば、`.

Hậu quả: mọi trang thành `inpaint_needs_review`, danh sách rà soát đầy cờ giả. Trang vẫn dịch và căn chữ
bình thường, nhưng không còn lọc ra được chỗ hỏng thật.

## Sửa

Chỉ tin kết quả đọc lại khi vùng đó **có mực thật**: tỉ lệ điểm lệch hơn 60 mức xám khỏi màu nền phải
≥ `INPAINT_VERIFY_MIN_MUC` (mặc định 0,015). Vùng trắng trơn thì bỏ qua và ghi log.

Ngưỡng lấy từ số đo trên 5 trang thật:

| | Tỉ lệ mực |
|---|---|
| Vùng còn chữ thật (ảnh gốc) | thấp nhất **0,084**, trung vị 0,170 |
| Vùng OCR đọc bịa (ảnh đã xoá) | **0 – 0,011** |

Vùng đã xoá mà đè lên tranh vẽ (nhiều mực) vẫn được kiểm như cũ, theo hướng thận trọng.

## Kiểm

- Hàm kiểm chạy với manga-ocr THẬT trên trang thật:
  - ảnh đã xoá: **0/7** vùng báo còn chữ (trước đây 7/7, đúng như production)
  - ảnh gốc còn chữ: vẫn bắt **7/7**
- Test mới "ô trắng trơn mà bộ đọc vẫn ra chữ thì KHÔNG gắn cờ". **Đối chứng âm:** ngưỡng 0 (hành vi cũ)
  ⇒ đỏ.
- Test cũ "đọc lại còn chữ thì gắn cờ" từng dùng ảnh "đã xoá" TRẮNG TINH, tức nó khoá đúng hành vi lỗi.
  Đã chuyển sang ảnh còn vết mực thật (`fake_inpainter(con_muc=True)`).
