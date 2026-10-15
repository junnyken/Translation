# REPORT E75 — Xếp chữ theo hình bong bóng

**Ngày:** 2026-10-15 · **Nguồn:** kế hoạch tham khảo Koharu, mục 3 (`comic_line_breaks`: bề rộng
từng dòng lấy theo đường viền bong bóng).

## Summary

Vùng có đa giác bong bóng (E14) thì thử xếp chữ theo hình: dòng giữa rộng, dòng đầu và cuối hẹp,
mọi dòng căn trên một trục dọc chung. Chỉ nhận khi cho cỡ chữ **lớn hơn** khối chữ nhật hiện tại.
Không thì giữ nguyên cách cũ. `BUILT`, đã đo trên trang thật. Tắt bằng `E75_XEP_THEO_HINH=false`.

## Audit Before Build — đo trước khi làm

Đo trên 6 trang thật (CTD thật + bộ trích hình E14 trên ảnh đã xoá chữ):
- 8/38 vùng (21%) có đa giác.
- Ở các vùng đó, hình chữ nhật nội tiếp chỉ dùng **34–68%** diện tích bong bóng (trung vị ~0,5).

## Design Choice

- **Một đường vẽ (ràng buộc E14).** Bước căn chữ tính vị trí từng dòng và lưu vào
  `typeset_result.dong_json`. Ảnh xem thử và file xuất chỉ đọc lại. Cả hai dùng chung `do_dong()`
  để tính chiều cao và bước dòng.
- **Cùng thước đo với M6.** Lần đo đầu dùng chiều cao nét (dấu chồng tới chân chữ) làm bước dòng.
  Như vậy thưa hơn cách M6 đo, nên kết quả cho cỡ chữ **nhỏ hơn** cách cũ ở cả 3 bong bóng thử. Đã
  đổi sang đúng quy ước `multiline_text` của Pillow.
- **Một trục chung.** Lần thứ hai căn giữa từng dòng theo khoảng trống riêng của nó. Trên bong bóng có
  đuôi, các dòng lệch nhau trông như gõ sai. Nay trục là giữa khoảng ngang của dòng chính giữa, mỗi
  dòng đối xứng quanh trục đó.
- **Không đè chữ.** Bong bóng chứa TÂM của một vùng chữ khác thì không xếp theo hình. Bộ nhận diện hay
  cắt một bong bóng thành hai khung; xếp cả hai vào nguyên bong bóng là chữ đè nhau.
- Vùng bị xoay (E16) hoặc bản dịch có xuống dòng cứng thì giữ cách cũ.
- Sửa tay một vùng (refit) ghi `dong_json = NULL`, tức về khối chữ nhật như đường refit vốn làm.

## Live Verification — 8 bong bóng thật, cùng câu tiếng Việt

| Kiểu xếp | Thắng | Mức tăng cỡ chữ |
|---|---|---|
| Mỗi dòng một tâm (bản 2) | 7/8 | +2 đến +6px (11→17) — nhưng dòng lệch nhau |
| **Một trục chung (bản cuối)** | **6/8** | +1 đến +2px (11→13, 24→26, 13→14) |

Đã xem ảnh trước/sau: chữ nằm trong bong bóng, các dòng thẳng hàng. Hai ca còn lại hoà nên giữ cách cũ.

## Tests

`test_e75_xep_theo_hinh.py`: 11 test. Kiểm:
- mọi dòng nằm trọn trong đa giác, không mất từ
- bong bóng bầu dục cho cỡ chữ lớn hơn
- dòng giữa rộng hơn
- chung một trục
- từ quá dài hoặc có xuống dòng cứng thì không xếp theo hình
- chỉ nhận khi tốt hơn
- bộ vẽ đặt đúng chỗ đã lưu và nhân hệ số E65
- chạy trọn bước căn chữ trên DB thật: lưu `dong_json`, chốt chống đè, tắt cờ

**Đối chứng âm:**
- Gỡ chốt chống đè ⇒ đỏ. Bản đầu của bài này vẫn xanh khi gỡ chốt, vì dùng một bong bóng khổng lồ mà ở
  đó cách cũ đã chạm trần cỡ chữ. Đã sửa bài.
- Bộ vẽ bỏ qua `dong_json` ⇒ đỏ.

## Remaining Limits

1. Chỉ 21% vùng có đa giác. Muốn lợi nhiều hơn phải nâng tỉ lệ nhận ra hình bong bóng (E14/A2).
2. Ngắt dòng tham lam (đủ để biết xếp được hay không), chưa tối ưu độ đều như Koharu.
3. Chưa chạy trọn pipeline trên production.
