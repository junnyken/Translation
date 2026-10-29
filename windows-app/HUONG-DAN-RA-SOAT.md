# Rà soát từng trang và tạo bản giao

Trạng thái: **BUILT, chưa nghiệm thu trên Windows thật**. Công cụ dòng lệnh dùng cùng
Python/Pillow với app; chưa có màn xem/chỉnh ảnh tích hợp. Không gọi AI, không tải lên,
không gửi khách. Chỉ dùng với chapter đã có `trang-thai.json` do bản app production tạo.

## Bản nháp và bản giao

App xuất tự động CBZ/PDF/dải ảnh với tên có `-ban-nhap`. Các file đã xuất bằng phiên bản
cũ vẫn giữ nguyên tên; tên file không chứng minh đã duyệt. **Chỉ ZIP do lệnh `export`
bên dưới tạo có `BAN-GIAO.json`** mới đi qua cổng duyệt này. CBZ cũ không tự được đổi tên/xoá.

`BAN-GIAO.json` chứa mã gói, giờ UTC và SHA256 từng ảnh. Đây là bản ghi đối chiếu phiên bản,
không phải chữ ký chống giả mạo, chứng nhận chất lượng hay xác nhận đã gửi/được khách nhận.
Tên người rà soát/ghi chú vẫn ở hồ sơ nội bộ, không nằm trong gói giao.

## Thực hiện trong PowerShell

Mở PowerShell tại thư mục app. Các đường dẫn dưới đây là ví dụ, thay bằng chapter thực tế.
Luôn đặt đường dẫn và tên có khoảng trắng trong dấu nháy.

1. Xem danh sách ảnh và hash hiện tại:

   ```powershell
   python .\review_delivery.py status "D:\DonDich\BoTruyen\Chapter-001"
   ```

   Hoặc dùng launcher: `.\Ra-Soat-Ban-Giao.bat status "D:\DonDich\BoTruyen\Chapter-001"`.
   Kết quả có đường dẫn từng ảnh, số trang, SHA256, trạng thái duyệt và `ready_for_delivery`.
   `blocked` = thiếu/hỏng/chưa hoàn thành/ảnh đã bị sửa; `stale` = nội dung hoặc cấu hình khác
   phiên bản từng được duyệt. Không sửa tay `trang-thai.json` để bỏ qua kiểm tra.

2. Mở từng ảnh trong trình xem ảnh, đối chiếu bản gốc; kiểm số trang, thứ tự, nghĩa, tên riêng,
   xưng hô, xoá chữ, chữ tràn và vùng bị bỏ sót. Công cụ không xác minh rằng bạn đã xem.
   Sau khi xem, sao chép **đúng SHA256** của trang từ `status` và ghi duyệt từng trang:

   ```powershell
   python .\review_delivery.py approve "D:\DonDich\BoTruyen\Chapter-001" --page 1 --reviewer "Ten nguoi ra soat" --sha256 "SHA256_CUA_TRANG_1" --confirm-reviewed --note "Da doi chieu ban goc"
   ```

   Lặp với trang 2, 3… Không có lệnh duyệt hàng loạt. SHA256 chỉ xác nhận phiên bản ảnh;
   cờ `--confirm-reviewed` là lời xác nhận của người vận hành, không phải kiểm chất lượng tự động.

3. Nếu cần sửa hoặc thu hồi duyệt, ghi lý do:

   ```powershell
   python .\review_delivery.py reject "D:\DonDich\BoTruyen\Chapter-001" --page 1 --reviewer "Ten nguoi ra soat" --note "Can sua ten nhan vat"
   ```

   Quyết định cũ bị thu hồi ngay. Luồng này chưa nhập ảnh sửa tay hoặc mở trình chỉnh chữ.
   Với nội dung cần sửa, xử lý lại bằng công cụ phù hợp vào chapter mới, rồi rà soát lại;
   không ghi đè ảnh đã duyệt hoặc tự sửa hash trong hồ sơ. Chưa có đồng bộ sửa tay desktop↔web.

4. Khi `status` báo tất cả trang đã duyệt, tạo ZIP giao phiên bản mới:

   ```powershell
   python .\review_delivery.py export "D:\DonDich\BoTruyen\Chapter-001" "D:\BanGiao\Chapter-001-v1.zip"
   ```

   Thư mục `D:\BanGiao` phải có sẵn. Không ghi đè file cũ; dùng `v2`, `v3` cho phiên bản khác.
   Mở ZIP, kiểm đủ ảnh và thứ tự bằng trình đọc thực tế trước khi giao thủ công.
   Chỉ có ảnh trong ledger và `BAN-GIAO.json`; không lấy nhầm dải ảnh cũ/ảnh khác trong thư mục.

## Khi gặp lỗi

- App còn đang chạy chapter: dừng/đợi app giải phóng khoá rồi rà soát; hai tiến trình không cùng ghi.
- Ảnh bị đổi/mất/hỏng: bản duyệt cũ không hợp lệ. Công cụ không tự nhận ảnh sửa hoặc ghi đè ảnh.
- Đổi glossary/cấu hình/vùng dịch: phải rà soát lại nội dung tương ứng.
- Xuất báo không hỗ trợ hard link: chọn ổ/thư mục hỗ trợ (ví dụ NTFS). Không tự fallback sang
  cách tạo ZIP dở ở tên giao. Cần thử thực tế Windows; kiểm thử mô phỏng không chứng minh ổ hiện tại hỗ trợ.
- Mã thoát 0 = thao tác thực hiện được, 1 = không thực hiện, 2 = sai cú pháp dòng lệnh.
  Chạy `python .\review_delivery.py --help` để xem lệnh.
- Hồ sơ `review_status` là thông tin tổng hợp ở lần ghi cuối. Dùng `status`/`export` để kiểm lại
  bytes thực tế; không dựa riêng cờ này sau khi có chỉnh sửa bên ngoài.

## Giới hạn

Chưa có khách hàng/đơn/báo giá/chi phí, lịch tự chạy, hoặc tự gửi bản giao.
Không có danh tính đăng nhập cho reviewer hay audit log chống chỉnh sửa: người có quyền sửa
file nội bộ có thể sửa hồ sơ. Tên reviewer do người vận hành nhập, không phải xác thực danh tính.
Duyệt trên Linux/headless chưa chứng minh launcher, lock và hard link hoạt động trên Windows.
