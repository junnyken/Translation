# Quyền riêng tư — Translation Companion (E1)

Bản này đi kèm trong gói tiện ích. Nó mô tả **đúng thứ mã nguồn làm**, không phải ý định.
Kiểm chứng được: `manifest.json` và `src/` nằm ngay trong gói bạn nạp — không có bước build,
không có mã tải về lúc chạy.

## Tiện ích KHÔNG làm

- **Không đọc trang web bạn đang xem.** Không có `content_scripts` trong manifest, không dùng
  `chrome.scripting`, không đọc DOM, không chụp màn hình, không đọc URL/tiêu đề tab.
- **Không xin quyền website nào.** `host_permissions` để **rỗng**. Không `<all_urls>`,
  không `activeTab`, `tabs`, `scripting`, `webRequest`, `declarativeNetRequest`, `downloads`,
  `history`, `bookmarks`, `clipboardRead`.
- **Không tự tải ảnh từ internet**, không quét/thu thập trang truyện, không phủ bản dịch lên trang.
- **Không chạy mô hình AI nào.** Toàn bộ nhận diện / OCR / xoá chữ / dịch / căn chữ vẫn chạy ở
  backend Translation trên máy bạn.
- **Không gửi gì ra internet.** Địa chỉ duy nhất tiện ích được gọi là loopback
  (`http://localhost:<cổng>` hoặc `http://127.0.0.1:<cổng>`) mà chính bạn nhập vào.
- **Không có telemetry, không thống kê, không tự cập nhật từ máy chủ ngoài.**

## Quyền tiện ích xin — và dùng vào việc gì

| Quyền | Dùng để |
|---|---|
| `storage` | Nhớ địa chỉ Translation local + danh sách chapter bạn tự ghim |
| `sidePanel` | Mở giao diện cạnh tab khi bạn bấm biểu tượng |

Mở tab web app dùng `chrome.tabs.create()` — hàm này **không** cần quyền `tabs`, nên tiện ích
không xin quyền đó.

## Tiện ích lưu gì trong máy bạn

Tất cả nằm ở `chrome.storage.local`, đúng hai khoá:

**`caiDatV1`**
- `translationBaseUrl` — địa chỉ loopback bạn nhập
- `preferredLaunchSurface` — `side_panel` (E1 chỉ dựng Side Panel)
- `lastOpenedProjectId`, `lastOpenedPageId` — mã UUID của thứ bạn vừa mở
- `lastConnectionCheckAt` — mốc thời gian kiểm kết nối gần nhất

**`chapterGhimV1`** — tối đa **5** mục, mỗi mục:
- `projectId` (UUID), `title` (tên chapter), `status`, `updatedAt`, `cachedAt`
- Phần tên/trạng thái là **bản chụp**, hết hạn sau **24 giờ** thì tự bỏ, chỉ giữ lại mã.

## Tiện ích KHÔNG BAO GIỜ lưu

API key, mật khẩu, thông tin đăng nhập, ảnh gốc hay ảnh đã xử lý, chữ OCR, nội dung bản dịch,
tệp xuất, đường dẫn tệp trên máy, địa chỉ website bên thứ ba, cookie.

Đây **không** chỉ là lời hứa: `src/lib/storage-schema.js` có hàm `chotChanGhi()` ném lỗi nếu có
khoá nào ngoài khuôn được đưa vào kho, và bộ test canh đúng danh sách khoá cấm đó.

## Xoá dữ liệu

Side Panel → **Xoá dữ liệu extension**, hoặc trang Cài đặt → **Xoá cài đặt và metadata extension**.

Thao tác này chỉ xoá hai khoá ở trên **trong trình duyệt**. Chapter, ảnh và bản dịch trong ứng
dụng Translation **không** bị đụng tới — tiện ích không có đường nào xoá dữ liệu backend.

Lưu ý: `chrome.storage` sống dai hơn lệnh xoá lịch sử/bộ nhớ đệm thông thường của trình duyệt.
Đó chính là lý do khuôn dữ liệu ở trên được giữ nhỏ tới mức này.

## Phát hành

E1 **chưa** phát hành lên Chrome Web Store. Chỉ nạp thủ công (load unpacked). Việc phát hành cần
một mini-spec riêng về đóng gói, khai báo quyền riêng tư, extension ID cố định và CORS.
