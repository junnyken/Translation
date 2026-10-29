# REPORT E81 · E82 — Ngắt dòng đều trong bong bóng · Thứ tự đọc theo khung tranh

**Ngày:** 2026-10-15 · **Nguồn:** tham khảo Koharu, mục 5 và mục 3.

## E81 — Ngắt dòng đều (quy hoạch động) cho chữ xếp theo hình bong bóng (E75)

- **Trước:** ngắt tham lam, dồn từ lên dòng trên, nên hay ra dòng đầu một chữ ("Tôi" / "đã nói rồi mà…").
- **Nay (`_ngat_deu`):** quy hoạch động chọn cách chia từ vào đúng n dòng, dòng nào cũng vừa, mà **đều
  nhất**. Phạt (khoảng trống/bề rộng)², phạt dòng một từ, thưởng ngắt sau dấu câu. Ý tưởng từ Koharu
  `comic_line_breaks`.
- Ở cùng cỡ chữ, xét số dòng ít nhất xếp được và hơn nó một dòng, cùng hai vị trí khối, rồi lấy cách đều
  nhất. Nếu vẫn có dòng một chữ, được hạ **tối đa 2px** để tránh. Chữ to nhất vẫn là ưu tiên số một.
- Khả năng xếp không giảm: cách tham lam còn dùng để loại nhanh những cách chia không thể vừa.

**Tốc độ.** Bản quy hoạch động đầu tiên chậm: câu 42 từ mất 500ms, vì đo lại cùng cụm từ cho mọi lượt
thử. Đã sửa bằng `_BoDo`, bộ nhớ đo dùng chung cho mọi lượt thử ở một cỡ chữ, cộng giới hạn số dòng thử.

| Câu | Tham lam cũ | Quy hoạch động bản đầu | Bản cuối |
|---|---|---|---|
| 42 từ | 211 ms | 500 ms | **234 ms** |
| 11 từ | 6 ms | 12 ms | **6 ms** |

**Kết quả trên bong bóng cao hẹp:** "Tôi đã / nói rồi mà, / cậu không / chịu nghe / gì cả!" ở cỡ 39, trước
đây "Tôi" đứng riêng một dòng ở cỡ 40.

Tests: thêm 2 test (đều hơn tham lam, không xếp được ⇒ None). Bộ E75 13/13, chạy riêng 22 giây.

## E82 — Thứ tự đọc theo khung tranh

- **Trước:** chia cả trang thành dải ngang. Với bố cục khung cao bên phải và hai khung chồng nhau bên
  trái, bong bóng các khung bị **đan xen**. Test tái hiện đúng: cũ "phải-trên, trái-trên, phải-dưới,
  trái-dưới".
- **Nay:** tìm khung bằng **cắt XY theo rãnh trắng** (`translate/khung_tranh.py`). Hàng đọc trên → dưới;
  cột đọc phải → trái với manga Nhật, trái → phải với EN/CN. Bong bóng gán vào khung chứa tâm (tràn qua
  rãnh thì gán khung gần nhất); trong khung vẫn sắp như cũ.
- Koharu có lớp "panel" từ model RF-DETR. Translation chưa có model đó (mục 2 bị chặn vì đĩa máy chủ
  đầy), nên dùng cắt XY.
- Trang không có rãnh trắng (nền tối, tranh tràn lề, khung nghiêng) ⇒ một khung ⇒ **y như trước**.

**Kiểm trên 4 trang thật** (ảnh minh hoạ trong phiên): tìm đúng 4, 5, 3, 3 khung. Trang tiếng Nhật đọc
đúng hướng phải → trái ở hàng dưới.

Tests: 6 test (bố cục chuẩn, bố cục làm cách cũ hỏng, trang không rãnh, bong bóng tràn rãnh, tắt cờ, lỗi
đọc ảnh). Tắt bằng `E82_THU_TU_THEO_KHUNG=false`.

## Remaining Limits

- E82: khung nghiêng hoặc không có rãnh thì không tách được (lùi về cách cũ). Chỉ đo trên 4 trang.
- E81: chưa tách bong bóng dính nhau (kỹ thuật "neck decomposition" của Koharu).
