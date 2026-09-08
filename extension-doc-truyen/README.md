# Dịch truyện đang đọc (E19)

Tiện ích Chrome MV3: bấm một cái, phủ chữ dịch tiếng Việt lên trang truyện đang mở.

**Không phải bản nâng cấp của `extension/`** (Translation Companion). Xem `PRIVACY.md` §đầu —
tiện ích này cố ý làm ngược ba lời hứa của cái kia, nên nó phải đứng riêng.

## Cài

1. `chrome://extensions` → bật **Chế độ dành cho nhà phát triển** → **Tải tiện ích đã giải nén** →
   chọn thư mục này. Không có bước build.
2. Mở trang truyện, bấm biểu tượng tiện ích → hiện popup: chọn **ngôn ngữ chữ trên trang** (Nhật/
   Trung/Anh) rồi bấm **Dịch trang này**. Chưa cấu hình địa chỉ máy chủ/đăng nhập thì tiện ích tự
   mở trang Tuỳ chọn (link "Địa chỉ máy chủ & đăng nhập…" trong popup cũng mở tay được).

**Cập nhật bản mới: giải nén ĐÈ LÊN cùng một thư mục, đừng tạo thư mục mới mỗi lần.** ID của
tiện ích unpacked tính theo đường dẫn thư mục — thư mục khác tên thành ID khác, Chrome coi là
**cài mới hoàn toàn**: mất phiên đăng nhập, mất quyền site đã cấp, phải làm lại từ đầu. Gói tải về
đặt tên **cố định** (`dich-truyen-dang-doc.zip`, không có số phiên bản trong tên) đúng vì lý do
này — xoá thư mục cũ trước khi giải nén gói mới vào **đúng đường dẫn cũ** (đừng để trình giải nén
tự đặt tên `(1)`), rồi bấm nút **Tải lại** (icon vòng tròn) trên đúng thẻ tiện ích ở
`chrome://extensions` — giữ nguyên ID, không mất gì.

## Biết trước cho khỏi thất vọng

Một trang tốn **khoảng 45 giây** — chủ yếu ở bước nhận diện bong bóng, và đó là chi phí CPU chứ
không phải chờ mạng (đo trong `docs/REPORT_E19_0_DO_COND_CHAN.md`). Các trang **xếp hàng**, worker
chạy một việc một lúc.

Nên cách dùng đúng là: bấm dịch trang kế **trong lúc đang đọc trang hiện tại**, không phải bấm rồi
ngồi nhìn.

## Chạy test

```bash
npm test        # 22 test cho hai module thuần: chọn ảnh và quy đổi toạ độ
```

Chỉ phần logic thuần có test. Phần vẽ lớp phủ và service worker chỉ sống trong trình duyệt thật —
chúng được giữ mỏng có chủ ý, và mọi thứ đáng test đều đã đẩy vào `src/lib/`.
