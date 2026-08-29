# Báo cáo Mini-Spec E14 — Vùng an toàn theo hình bong bóng

**Project:** Translation · **Phase:** E — nâng chất lượng bản dịch · **Ngày:** 2026-08-29
**Nền:** M1–M10 · E11 · E12 · E13 (`v1.3-E13`, `2120721`)

## 1. Summary

M6 căn chữ vào **bbox chữ nhật** của bộ nhận diện. Bong bóng thật thì tròn, méo, có đuôi — nên
chữ "vừa khung" về số học vẫn có thể chạm viền cong. E14 thêm một lớp hình học giữa bước xoá chữ
và bước căn chữ: tìm **lòng bong bóng thật**, ăn vào một lề, rồi đưa cho M6 một ô nằm gọn bên
trong đó.

Đo trên 9 vùng thật của Pepper&Carrot: **5/5 bong bóng thật** được nhận hình, **4/4 vùng không
phải bong bóng** lùi về khung dự phòng kèm lý do, **0 lần chọn nhầm**, và **5/5 khối chữ nằm trọn
trong đa giác bong bóng**. Cỡ chữ **tăng** ở 3/5 vùng.

1 bảng mới, 1 migration, **743 test backend + 95 test giao diện**.

## 2. Audit Before Build

10/10 mục có bằng chứng ở `TEST_LOG § E14.1`. Ba phát hiện đổi hẳn thiết kế:

- **Adapter CTD chỉ giải mã bbox.** Hai nhánh `seg`/`det` của model chưa bao giờ được đọc
  (`ctd.py:161-162`). Guardrail "đừng nhầm text mask thành bubble mask" vì thế là hiển nhiên —
  không có mask nào để mà nhầm.
- **Mảng vá của LaMa có màu khác lòng bong bóng**, nên nó rơi khỏi ngưỡng sáng và **đục một lỗ
  ngay giữa** vùng an toàn. Đây là lý do phải lấp lỗ theo từng ứng viên.
- **Enum `job_type` chưa từng được thêm giá trị** trong suốt M1–E13, và có test chốt đúng 10 task
  Celery. Nên E14 tính vùng an toàn **đồng bộ ở cuối bước xoá chữ**, đúng tiền lệ chấm chất lượng
  của E12 — không thêm task, không đụng enum.

**Cổng chặn của spec:** nếu thăm dò cho thấy heuristic chọn nhầm vùng trắng thì phải báo
`E14 blocked`. Kết quả thăm dò (5 vòng, `TEST_LOG § E14.2`): **không bị chặn**.

## 3. Design Choice

- **Ngưỡng CHẶT + lấp lỗ theo từng ứng viên.** Nới ngưỡng để cứu cái lỗ do LaMa tạo ra sẽ làm
  bong bóng dính vào nền sáng (đo được: thành phần phình gấp 4–7 lần bbox). Lấp lỗ trên cả vùng
  tìm kiếm thì nuốt luôn mảng tối bị nền sáng bao quanh.
- **Chọn đường viền KHÍT NHẤT chứa tâm bbox**, không phải to nhất. "Vùng trắng lớn nhất" là cách
  chắc chắn để có ngày chọn trúng nền trang.
- **Ô chữ nhật nội tiếp, không phải đa giác.** M6 ngắt dòng theo bề rộng, mà bề rộng trong một đa
  giác đổi theo từng dòng. Dựng bộ ngắt dòng thứ hai cho đa giác là mở ra **đường vẽ thứ hai** —
  đúng thứ spec cấm.
- **Ô đặt chữ tính MỘT lần ở worker rồi lưu lại.** Bước căn chữ, ảnh xem thử, file xuất và lớp
  phủ giao diện đều đọc cùng một ô. Tính lại ở mỗi nơi là bốn cơ hội để lệch nhau — và khiến tầng
  HTTP phải nạp OpenCV.
- **Dự phòng lấy đúng lề của M6.** Xem §5: đây là chỗ đo mới thấy.
- **Không dựng trình sửa đa giác.** M7 đã có sửa bbox tay; `manual_override` để dành.

## 4. Kết quả đo thật

`TEST_LOG § E14.5–7`. Điểm cốt lõi:

| Đo gì | Kết quả |
|---|---|
| Bong bóng thật được nhận hình | **5/5** |
| Vùng không phải bong bóng lùi về dự phòng | **4/4**, có mã lý do đọc được |
| Chọn nhầm vùng trắng | **0** |
| Khối chữ nằm trọn trong đa giác (đo theo điểm ảnh, không phải điểm neo) | **5/5** |
| Cỡ chữ so với M6 | tăng ở 3/5, giữ nguyên 1, giảm 1 nấc ở 1 |
| Vùng dự phòng so với M6 | **giống hệt** (cỡ chữ + trạng thái) |
| Bất biến theo độ phân giải | 9/9 cùng quyết định ở 0.5× / 0.75× / 1× / 1.5× |

## 5. Một lệch thật do đo mới thấy

Đường dự phòng ban đầu dùng lề ăn-vào của E14 ⇒ cỡ chữ dòng bản quyền nhảy **14 → 16**. Tức là
E14 đổi bố cục ở ngay chỗ nó **không nhận ra hình gì cả** — không ai xin và không giải thích được.
Đã sửa để khung dự phòng dùng đúng `typeset_padding_ratio` của M6, và khoá lại bằng test.

Lỗi thứ hai, ở giao diện: hàm gọi API của E14 dùng một hàm `goi()` **không tồn tại**, và chính
khối `catch` của tôi nuốt mất `ReferenceError` đó — lớp phủ im lặng không vẽ gì. Chỉ lộ ra khi mở
trình duyệt thật và đếm số đa giác. Đã sửa để **chỉ** bỏ qua đúng 404, mọi lỗi khác ném ra.

## 6. Success Criteria — đối chiếu thẳng

| Tiêu chí | Kết quả |
|---|---|
| Mỗi vùng đúng một bản ghi, tính lại không đẻ bản trùng | ✅ có test |
| ≥90% vùng shape_derived có chữ nằm trọn trong bong bóng | ✅ **5/5 = 100%** |
| Ca khó chọn dự phòng/cần xem thay vì hình sai | ✅ 4/4, 0 chọn nhầm |
| Kiểm CẢ ô chữ chứ không mỗi điểm neo | ✅ đo theo điểm ảnh |
| Cỡ chữ đã ghim không bị tự đổi | ✅ đường ghim cỡ của M7 giữ nguyên |
| Sửa bbox ⇒ tính lại đúng vùng đó | ✅ có test integration; **chưa bấm tay trên trình duyệt** |
| Ảnh xem thử và file xuất dùng chung một bộ vẽ | ✅ cùng `draw()`, cùng ô đặt chữ đã lưu |
| Giao diện phân biệt được 4 trạng thái | ✅ lớp phủ + bảng bên phải, đã xem trên Chromium |
| Cảnh báo lúc xuất tách riêng khỏi E12/E13/tràn khung | ✅ khối "Bố cục trong bong bóng" |
| M1–E13 vẫn pass, không thêm model/gọi mạng | ✅ 743 pass, không nới lỏng kỳ vọng cũ |

## 7. Remaining Limits / Follow-ups

- **Chưa đo trên truyện đen trắng** — bong bóng trắng trên nền tối là ca phổ biến nhất của manga,
  và cũng là ca E14 v1 nhắm tới. Bộ ảnh đang có là Pepper&Carrot (bong bóng bạc hà trên tranh
  màu). Đây là khoảng trống bằng chứng lớn nhất còn lại.
- **Đa giác còn thô**: đúng bong bóng nhưng có khía lẹm vào, và ở một bong bóng thì cái đuôi cũng
  bị tính vào. Lẹm vào là *an toàn* (vùng nhỏ hơn lòng thật); cái đuôi thì bước tìm ô nội tiếp
  loại ra. E14 v1 cho **vị trí đặt chữ an toàn hơn**, không phải **nhận diện bong bóng chính xác**.
- Không hỗ trợ bong bóng tối/gradient, chữ dọc, SFX cong, ô kể chuyện không viền.
- Run C mới có test integration, chưa bấm kéo bbox tay trên trình duyệt.
- Không có trình sửa đa giác; `manual_override` để dành cho mini-spec sau.

**Mini-spec kế tiếp:** đo E14 trên chapter đen trắng thật trước khi mở rộng phạm vi.
