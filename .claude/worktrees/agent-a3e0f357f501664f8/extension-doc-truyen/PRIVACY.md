# Quyền riêng tư — Dịch truyện đang đọc (E19)

Bản này mô tả **đúng thứ mã nguồn làm**, không phải ý định. Kiểm chứng được: `manifest.json` và
`src/` nằm ngay trong gói bạn nạp — không có bước build, không có mã tải về lúc chạy.

## Đọc cái này trước nếu bạn đang dùng "Translation Companion"

Đây là tiện ích **khác**, không phải bản nâng cấp. Translation Companion (E1) hứa và giữ đúng ba
điều mà tiện ích này **cố ý làm ngược lại**:

| | Translation Companion (E1) | Tiện ích này (E19) |
|---|---|---|
| Đọc trang bạn đang xem | không bao giờ | **có** — khi bạn bấm biểu tượng |
| Quyền website | `host_permissions` rỗng | **`<all_urls>`** |
| Tải ảnh từ internet | không | **có** — ảnh trang truyện |
| Phủ nội dung lên trang | không | **có** — lớp chữ dịch |

Hai tiện ích chạy độc lập. Cài cái này **không** đổi hành vi của cái kia.

## Tiện ích làm gì, và khi nào

**Chỉ khi bạn bấm biểu tượng.** Không có `content_scripts` khai trong manifest — mã chỉ được tiêm
vào trang bằng `chrome.scripting.executeScript` trong đúng lần bấm đó. Mở 50 tab mà không bấm thì
không tab nào bị đụng tới.

Một lần bấm làm đúng chuỗi này:

1. Đọc danh sách `<img>` **trên tab hiện tại** để chọn đâu là trang truyện (kích thước, tỉ lệ,
   phần đang nằm trong khung nhìn). Không đọc chữ, không đọc form, không đọc cookie.
2. Tải **byte của đúng một ảnh** đó.
3. Gửi ảnh đó tới **máy chủ Translation mà bạn tự nhập địa chỉ**.
4. Hỏi lại máy chủ tới khi dịch xong.
5. Vẽ một lớp chữ dịch đè lên ảnh, **trong trang, ở máy bạn**.

## Tiện ích KHÔNG làm

- **Không gửi gì tới bất kỳ máy chủ nào khác** ngoài địa chỉ Translation bạn nhập. Không có địa
  chỉ nào viết cứng trong mã.
- **Không đọc trang khi bạn không bấm.**
- **Không chạm tới ảnh nào ngoài ảnh đã chọn.**
- **Không đọc chữ trên trang, không đọc URL/tiêu đề tab, không chụp màn hình.**
- **Không lưu mật khẩu.** Trang tuỳ chọn nhận mật khẩu, gửi thẳng cho máy chủ, rồi chỉ giữ lại
  **mã phiên** máy chủ cấp. Mã phiên thu hồi được (bấm Đăng xuất là mất hiệu lực ngay); mật khẩu
  thì không.
- **Không chạy mô hình AI nào.** Toàn bộ nhận diện / đọc chữ / dịch chạy ở máy chủ Translation.
- **Không telemetry, không thống kê, không tự cập nhật từ máy chủ ngoài.**

## Vì sao xin `<all_urls>`

Vì bạn đọc truyện ở đâu thì tiện ích phải dùng được ở đó. Đây là quyền **rộng nhất** Chrome cấp,
và cách duy nhất để không cần nó là chỉ chạy trên một danh sách trang cố định.

Hai thứ giới hạn nó lại trong mã:

- Không có `content_scripts` ⇒ không có mã nào tự chạy ở trang bạn mở.
- `<all_urls>` được dùng để **tải một ảnh** khi bạn bấm — đó là cách duy nhất vượt được CORS.
  Đọc ảnh qua `canvas` không được: ảnh khác nguồn làm nhiễm bẩn canvas và trình duyệt chặn.

## Dữ liệu lưu trên máy bạn

`chrome.storage.local` giữ đúng ba thứ: **địa chỉ máy chủ**, **mã phiên**, **email** (để hiện ra
cho bạn biết đang đăng nhập bằng tài khoản nào). Bấm Đăng xuất là xoá mã phiên và email.

Bản dịch đã lấy về được nhớ **trong bộ nhớ của tab**, mất khi đóng tab. Nó chỉ để bấm lại trên
đúng trang đó thì không phải chờ lại từ đầu.

## Ảnh gửi đi thì nằm ở đâu

Nằm trên máy chủ Translation của bạn, trong một chapter tên **"Đọc nhanh (tiện ích)"** thuộc tài
khoản bạn. Bạn mở, xem và xoá nó ở giao diện web như mọi chapter khác.

Chapter đó được tạo với mục đích sử dụng **`personal`** (cá nhân). Tiện ích **không** phải đường
vòng để né phần khai báo mục đích của bản web — đổi mục đích thì đổi ở đó.

## Điều tiện ích không làm được

- Trang vẽ truyện bằng `canvas` hoặc có chống sao chép: không có `<img>` để lấy ⇒ **không dùng
  được**. Tiện ích nói thẳng ra thay vì im lặng thất bại.
- Chọn nhầm ảnh (quảng cáo, banner) là chuyện **sẽ xảy ra**, vì nó phải đoán. Bảng báo luôn nói
  nó chọn theo lý do gì.
