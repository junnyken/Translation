# Hướng Dẫn Đưa Tiện Ích Lên Chrome Web Store (Duyệt Nhanh Lần Đầu)

Tài liệu này chứa sẵn **toàn bộ nội dung, giải trình quyền (Permission Justifications) và bộ ảnh chuẩn kích thước** trong thư mục `extension-doc-truyen/store-assets/` để bạn chỉ cần **Copy & Paste** lên trang **Chrome Web Store Developer Dashboard** (`https://chrome.google.com/webstore/devconsole`).

---

## 📦 Bước 1: File `.ZIP` Để Tải Lên Chrome Web Store

Sử dụng đúng file đã được đóng gói sạch (chỉ chứa `manifest.json` chuẩn Manifest V3 và `src/`, không chứa `node_modules` hay mã nguồn thừa):
- **Đường dẫn file tải lên:** `extension-doc-truyen/store-assets/comic-io-vn-chrome-web-store-v0.3.2.zip` (hoặc `extension-doc-truyen/dich-truyen-dang-doc.zip`).

---

## 📝 Bước 2: Nội Dung Tab "Store Listing" (Thông Tin Cửa Hàng)

### 1. Tên tiện ích (Title)
- **Bản Tiếng Việt:** `Dịch Truyện Tranh AI Trực Tiếp Trên Web — Comic.io.vn`
- **Bản Quốc tế (English):** `AI Comic & Manga Translator Overlay — Comic.io.vn`

### 2. Mô tả ngắn (Summary — tối đa 132 ký tự)
- **Tiếng Việt:**
  `Phủ chữ dịch Tiếng Việt & Quốc tế sắc nét ngay trên trang Manga, Manhwa, Manhua, Webtoon đang đọc chỉ với 1 phím tắt (Alt+Q).`
- **English:**
  `Instantly translate Raw Manga, Manhwa, Manhua & Webtoon pages directly in your browser with smart bubble inpainting & AI context.`

### 3. Mô tả chi tiết (Detailed Description)
```text
🚀 DỊCH TRUYỆN TRANH AI TRỰC TIẾP TRÊN WEB (MANGA / MANHWA / MANHUA / WEBTOON) — COMIC.IO.VN

Đọc truyện tranh Raw (Nhật, Hàn, Trung, Anh) mượt mà ngay trên trình duyệt mà không cần tải ảnh về máy! Chỉ cần nhấn Alt+Q (hoặc bấm biểu tượng tiện ích), hệ thống tự động nhận diện bóng thoại, xóa sạch chữ gốc trên nền màu phức tạp và phủ bản dịch chuẩn ngữ cảnh ngay trên trang bạn đang xem.

✨ TÍNH NĂNG NỔI BẬT:
• ⚡ Dịch siêu tốc 1 trang (Alt+Q) hoặc Tự động dịch đón đầu khi cuộn trang (Alt+W).
• 🎨 Tự động tái tạo nền (Smart Inpainting) và dàn chữ khớp từng bóng thoại với 4 bộ Font chuyên biệt (Hành động, Ngôn tình, Cổ trang, Hài hước).
• ✏️ Nhấp đúp vào bất kỳ bóng thoại nào ngay trên trang web để sửa nhanh câu dịch, kéo vị trí hoặc dùng cọ xóa vùng chữ sót.
• 🧠 Đồng bộ từ điển tên nhân vật & đại từ xưng hô xuyên suốt các chương.
• 🌏 Hỗ trợ dịch từ Tiếng Nhật (Manga), Tiếng Hàn (Manhwa/Webtoon), Tiếng Trung (Manhua), Tiếng Anh sang Tiếng Việt và Tiếng Anh Quốc tế.

🔒 QUYỀN RIÊNG TƯ & BẢO MẬT:
• Tiện ích CHỈ hoạt động khi bạn chủ động bấm nút dịch hoặc nhấn phím tắt.
• Không theo dõi lịch sử duyệt web, không đọc dữ liệu cá nhân hay mật khẩu.
• Trang chủ & Quản lý tài khoản: https://comic.io.vn
```

### 4. Danh mục (Category) & Ngôn ngữ
- **Category:** `Productivity` (Năng suất) hoặc `Tools` (Công cụ)
- **Language:** `Vietnamese` (hoặc `English`)

---

## 🖼️ Bước 3: Bộ Ảnh Đồ Họa Chuẩn Kích Thước (Nằm Sẵn Trong `store-assets/`)

Chrome Web Store kiểm tra rất kỹ kích thước pixel và định dạng `24-bit PNG (không kênh trong suốt alpha)` đối với ảnh Promo. Toàn bộ ảnh dưới đây đã được xuất đúng chuẩn:

1. **Store Icon (`128 × 128 px`):** `extension-doc-truyen/store-assets/store-icon-128x128.png`
2. **Screenshots (`1280 × 800 px`, PNG 24-bit RGB):**
   - `extension-doc-truyen/store-assets/screenshot-1-1280x800.png` (Giao diện dịch trực tiếp trên trang truyện & thanh công cụ nổi)
   - `extension-doc-truyen/store-assets/screenshot-2-1280x800.png` (Giao diện cấu hình ngôn ngữ, bộ font & đồng bộ API Key)
3. **Small Promo Tile (`440 × 280 px`, PNG 24-bit RGB):**
   - `extension-doc-truyen/store-assets/promo-small-440x280.png`
4. **Marquee Promo Tile (`1400 × 560 px`, PNG 24-bit RGB):**
   - `extension-doc-truyen/store-assets/promo-marquee-1400x560.png`

---

## 🛡️ Bước 4: Nội Dung Tab "Privacy Practices" (Quan Trọng Nhất Để Được Duyệt Nhanh)

Khi Google hỏi lý do xin từng quyền trong `manifest.json`, hãy dán chính xác các đoạn dưới đây:

### 1. Single Purpose Description (Mục đích duy nhất của tiện ích)
```text
This extension has a single purpose: translating comic/manga/manhwa images on the active web page into the user's selected language and rendering the translated text overlay directly over the comic image when triggered by the user.
```

### 2. Permission Justifications (Giải trình từng quyền)

- **`activeTab` justification:**
  ```text
  Required to access the currently open comic/manga webpage ONLY when the user explicitly clicks the extension icon or presses the translation shortcut (Alt+Q) to locate comic page images and render the translated text overlay.
  ```

- **`scripting` justification:**
  ```text
  Required to inject the on-page translation overlay UI and bounding-box renderer into the active tab when the user triggers a comic page translation. No remote code is executed; all scripts are bundled locally inside the extension package.
  ```

- **`storage` justification:**
  ```text
  Required to save user preferences locally in chrome.storage.local, including preferred source/target languages, comic font style, and the user's authentication session token or API key for comic.io.vn.
  ```

- **`Host permission (<all_urls>)` justification:**
  ```text
  Users read comics, manga, and webtoons across thousands of independent scanlation, publisher, and webcomic domains worldwide, and comic images are frequently hosted on separate third-party CDNs (such as uploads.mangadex.org, pbs.twimg.com, cloudflare-ipfs, etc.). Host permission is strictly used to fetch the raw image bytes of the comic page the user requests to translate (bypassing canvas CORS tainting) and to send the image to the translation API (https://translation-api.vibe1.tinhgon.xyz / https://comic.io.vn).
  ```

- **Are you using remote code?**
  👉 Chọn: **`No, I am not using Remote code`** (Toàn bộ mã JavaScript và font chữ đều nằm sẵn bên trong gói `.zip`).

### 3. Data Usage Disclosures (Khai báo dữ liệu)
- Tick chọn: **`Authentication information`** (chỉ lưu token phiên đăng nhập hoặc API key `tr_live_...` do người dùng nhập) và **`Website content`** (chỉ gửi bức ảnh trang truyện mà người dùng bấm dịch lên máy chủ dịch).
- Tick chọn cả 3 ô cam kết của Google:
  - `[x]` I do not sell or transfer user data to third parties, outside of the approved use cases.
  - `[x]` I do not use or transfer user data for purposes that are unrelated to my item's single purpose.
  - `[x]` I do not use or transfer user data to determine creditworthiness or for lending purposes.

### 4. Privacy Policy URL (Đường dẫn Chính sách bảo mật)
- Điền URL: `https://comic.io.vn/?trang=chinh-sach` (hoặc `https://comic.io.vn/ket-noi-api`)
