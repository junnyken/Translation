# Báo cáo Mini-Spec E15 — Hướng chữ, thoại dọc & SFX cách điệu

**Project:** Translation · **Phase:** E · **Ngày:** 2026-08-29
**Nền:** M1–M10 · E11–E14 (`6547d6c`)
**Trạng thái:** backend xong — **giao diện chưa dựng**; dựng chữ dọc **cố ý để TẮT**

## 1. Summary

Trước E15, mọi vùng chữ đều được căn ngang. Chữ dọc trong bong bóng hẹp, SFX cách điệu, chữ
nghiêng — tất cả bị xử lý y như thoại ngang bình thường và cho ra kết quả trông "đã xong".

E15 thêm một lớp **nhận biết hướng chữ có bằng chứng** rồi **điều hướng rà soát**. Nó cố ý
**không** hứa dựng được chữ dọc: nhận ra hướng và dựng được chữ theo hướng đó là hai chuyện khác
nhau, và điều kiện để hứa thì chưa đủ (xem §3).

2 bảng đổi (1 cột thêm + 1 bảng mới), 2 migration, **779 test backend pass** (+33).

## 2. Audit Before Build — bốn phát hiện đổi hẳn thiết kế

Chi tiết số đo: `TEST_LOG § E15.1–2`.

**a) Nguồn bằng chứng mà spec trông đợi không tồn tại.** Spec dựa vào "CTD line polygon / text
mask". Adapter thật chỉ giải mã bbox; hai nhánh `seg`/`det` chưa bao giờ được đọc.

**b) Xoá chữ xong là mất luôn dấu vết hướng chữ.** Spec cho phép đo trên ảnh clean. Đo thật số
điểm ảnh tối trong từng vùng: thoại trong bong bóng tụt từ 1 499 xuống **0**, một vùng khác còn
**4**. Đó chính là việc M4 phải làm. ⇒ **không thể** đoán hướng từ ảnh clean.

**c) ⇒ Bằng chứng hình học duy nhất là đường bao dòng của OCR**, lấy lúc chữ còn nguyên.
PaddleOCR vẫn tính nó để sắp thứ tự dòng rồi **vứt đi**. E15 giữ lại (cột `line_polygons`).
Đây là lý do phải đổi mã lý do so với spec: dùng tên `ctd_line_geometry_*` sẽ là **nói sai về
nguồn bằng chứng**, nên đặt lại thành `ocr_line_geometry_*`, và luôn ghi kèm
`ctd_geometry_unavailable` cho đúng sự thật.

**d) Góc thô của `minAreaRect` không phân biệt được 0° với 90°.** Đo trên hình biết trước đáp án:
hình vẽ ở 0° cho `angle = 90.0` (w/h đảo), hình vẽ ở 90° **cũng** cho `angle = 90.0`. Phải chuẩn
hoá bằng `w`/`h`. Có test khoá lại cả tiền đề này.

## 3. Vì sao dựng chữ dọc để TẮT

Spec đặt điều kiện dừng: *thiếu ảnh mẫu chữ dọc hợp pháp, hoặc thiếu bằng chứng hình học tin cậy,
hoặc thiếu renderer giữ được dấu tiếng Việt ⇒ chỉ làm routing và ghi rõ **vertical rendering
blocked**; không được ship renderer dọc giả để đánh dấu E15 xong.*

| Điều kiện | Thực tế đo được |
|---|---|
| Ảnh mẫu chữ dọc có license rõ | **KHÔNG CÓ** — kho chỉ có Pepper&Carrot (tiếng Anh, chữ ngang) |
| Hình học từ bộ nhận diện | **KHÔNG CÓ** (mục 2a) |
| Renderer giữ được dấu tiếng Việt | **CÓ** — Pillow không có RAQM nên `direction="ttb"` ném `KeyError` rõ ràng, nhưng `regex` có sẵn và vẽ theo grapheme cho ra dấu nguyên vẹn (đã nhìn tận mắt) |

Thiếu 2/3 ⇒ `e15_vertical_render_enabled = False`. Vùng nhận ra là chữ dọc sẽ mang trạng thái
**`unavailable`** kèm lý do `vertical_renderer_unavailable` — nói thẳng "nhận ra rồi nhưng chưa
dựng được", chứ không giả vờ đã xử lý.

## 4. Design Choice

- **Tỉ lệ khung không bao giờ tự quyết.** Chữ `PHEW!` viết thưa theo chiều dọc vẫn là chữ ngang
  cách điệu. Tỉ lệ chỉ được ghi làm *tín hiệu*; có test khoá.
- **Các dòng cãi nhau thì nói là mâu thuẫn**, không bỏ phiếu đa số.
- **`unknown` là câu trả lời hợp lệ và được ưu tiên** hơn một kết luận tự tin mà sai.
- **Ràng buộc đặt ở tầng kiểu dữ liệu**, không phải ở tầng gọi hàm: không thể dựng được một
  `vertical_ttb + ready` thiếu bằng chứng, cũng không thể tạo `rotated_horizontal` mà quên ghi
  "v1 không tự xoay".
- **Không thêm task Celery** — chạy đồng bộ sau vùng an toàn, đúng tiền lệ E12/E14.

## 5. Đã làm / Chưa làm

| Phần | Trạng thái |
|---|---|
| Giữ lại đường bao dòng của OCR (cột + 2 đường ghi) | ✅ |
| Bộ chuẩn hoá góc + test trên hình biết trước đáp án | ✅ |
| Bộ nhận biết hướng + ràng buộc ở tầng kiểu dữ liệu | ✅ 27 test |
| Bảng `region_text_orientation` + migration | ✅ nâng/hạ cấp đều sạch |
| Nối vào dây chuyền (sau vùng an toàn, trước căn chữ) | ✅ |
| 3 endpoint chỉ đọc | ✅ |
| Đếm hướng chữ ở `export-warnings`, tách riêng | ✅ |
| Chốt chặn kiến trúc | ✅ 6 test |
| **Giao diện (nhãn, bộ lọc, khối cảnh báo)** | ❌ **chưa dựng** |
| **Test integration** | ❌ chưa viết |
| **Bộ dựng chữ dọc** | ⛔ cố ý chưa dựng — xem §3 |
| **Run A–D** | ❌ chưa chạy (cần ảnh mẫu thật) |

## 6. Remaining Limits / Follow-ups

- **Chưa có ảnh mẫu chữ dọc hợp pháp** ⇒ chưa được tuyên bố hỗ trợ chữ dọc dưới bất kỳ hình thức
  nào. Có ảnh rồi mới bật cờ và chạy Run B.
- **manga-ocr (tiếng Nhật) không trả đường bao dòng** ⇒ đúng thứ tiếng có nhiều chữ dọc nhất lại
  là thứ tiếng E15 **không** có bằng chứng hình học. Kết quả sẽ là `unknown + needs_review`.
  Đây là giới hạn thật, không phải lỗi.
- Chữ nghiêng: chỉ điều hướng rà soát. Không xoay, không cong, không radial.
- Chưa có chỗ cho người tự đặt hướng — đúng phạm vi đã chốt.
