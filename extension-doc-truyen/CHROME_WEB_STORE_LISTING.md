# Chrome Web Store Submission Guide — Comic & Manga AI Translator (`v0.3.2`)

Tài liệu này chuẩn bị sẵn toàn bộ nội dung chuẩn SEO Quốc tế & Việt Nam để bạn chỉ cần **Copy & Paste** vào trang **Chrome Web Store Developer Dashboard** (`https://chrome.google.com/webstore/devconsole`).

---

## 1. File ZIP dùng để tải lên (Package Upload)
- Tệp tải lên: `dist/extension-doc-truyen-v0.3.2.zip` (hoặc `frontend/public/tai-ve/extension-doc-truyen.zip`).
- Đã tích hợp sẵn đa ngôn ngữ `_locales/en/messages.json` (Mặc định Quốc tế) và `_locales/vi/messages.json` (Tiếng Việt).

---

## 2. Store Listing — English (Default / Global)

### Title (Auto-filled from `_locales/en/messages.json`):
`Comic & Manga AI Translator — Auto Webtoon & Raw Translator`

### Summary (Auto-filled from `_locales/en/messages.json`):
`1-click AI Manga, Manhwa & Webtoon translator. Auto-clean speech bubbles & typeset into 9 languages directly on any comic site.`

### Detailed Description (Copy & Paste into Description box):
```text
Translate raw Manga, Manhwa, Manhua, and Webtoons directly in your browser with one click! Powered by Per-Frame Adaptive OCR, Smart Background Reconstruction, and Context-Aware AI Translation.

✨ KEY FEATURES:
• 1-Click Page & Full Chapter Translation: Press Alt+Q to translate the current page, Alt+A to translate the entire chapter, or Alt+W for hands-free Auto-Scroll translation.
• Works on Canvas / DRM-Protected Sites: Press Alt+S to snip and translate any region on screen.
• 4 Source Languages ➔ 9 Target Languages: Translate from Japanese (Manga), Korean (Manhwa/Webtoon), Chinese (Manhua), or English Comics into English, Vietnamese, Simplified/Traditional Chinese, Indonesian, Spanish, Portuguese, Thai, and French.
• Smart Speech Bubble Cleaning & Live Typesetting: Automatically removes original text while preserving artwork and screentones, rendering natural comic fonts inside each bubble.
• Double-Click Live Editor: Double-click any translated speech bubble right on the page to edit or fine-tune translations in real time. Hold Alt to peek at the original raw image.

🎁 FREE TO START:
• Instant Guest Trial: Try immediately without registration.
• Register a Free Account at https://comic.io.vn to receive 20 Free Credits!
• Upgrade anytime to Monthly Plans starting at just $2.99 (First-Time Offer -50% OFF) — shared across Web Studio, Chrome Extension, Windows Batch App, and Developer REST API.
```

---

## 3. Store Listing — Tiếng Việt (Vietnamese Locale)

### Detailed Description (Dán vào phần Mô tả Tiếng Việt):
```text
Dịch trực tiếp truyện tranh Raw (Manga Nhật, Manhwa Hàn, Manhua Trung, Webtoon, Comic) ngay trên trình duyệt chỉ với 1 phím bấm! Sử dụng lõi OCR Thích Ứng Theo Khung Hình, Xoá Chữ Tái Tạo Nền Thông Minh và AI Dịch Chuẩn Ngữ Cảnh Truyện Tranh.

✨ TÍNH NĂNG NỔI BẬT:
• Dịch 1 Chạm & Tự Dịch Khi Cuộn: Bấm Alt+Q dịch trang đang xem, Alt+A tự động dịch cả Chapter, hoặc Alt+W bật Tự dịch khi cuộn trang.
• Hỗ Trợ Cả Web Chống Copy / Canvas: Bấm Alt+S để kéo chuột khoanh vùng dịch bất kỳ khung tranh nào trên màn hình.
• Dịch Đa Ngôn Ngữ Quốc Tế (4 Nguồn ➔ 9 Đích): Dịch từ Nhật, Hàn, Trung, Anh sang Tiếng Việt, Tiếng Anh, Trung Giản/Phồn thể, Indonesia, Tây Ban Nha, Bồ Đào Nha, Thái, Pháp.
• Xoá Chữ Sạch & 4 Bộ Font Thể Loại: Tự động xoá chữ gốc giữ nguyên nét vẽ/screentone và điền lời dịch theo 4 phong cách (Hành động, Ngôn tình, Cổ trang, Hài hước).
• Nhấp Đúp Sửa Câu Trực Tiếp: Nhấp đúp chuột vào bất kỳ bóng thoại nào để sửa câu dịch ngay trên trang đọc. Giữ phím Alt để đối chiếu chữ gốc.

🎁 ĐĂNG KÝ NHẬN 20 CREDITS MIỄN PHÍ:
• Tạo tài khoản miễn phí tại https://comic.io.vn nhận ngay 20 Credits miễn phí!
• Gói Tháng ưu đãi lần đầu giảm 50% chỉ từ $2.99 (49.000đ) — dùng chung 1 ví duy nhất trên Web, Tiện ích Chrome, App Windows và Developer API.
```

---

## 4. Privacy Practices Tab (Dán vào tab Privacy khi Google hỏi lý do xin quyền)

### Single Purpose Description:
```text
This extension has a single purpose: translating comic, manga, manhwa, and webtoon images displayed on the active webpage into the user's selected language and overlaying the translated text onto the speech bubbles.
```

### Permission Justifications (Lý do sử dụng các quyền trong `manifest.json`):

1. **`activeTab`**:
   ```text
   Required to access the currently active tab when the user clicks the extension icon or presses the translation shortcut (Alt+Q / Alt+S) to capture and translate the comic image the user is currently viewing.
   ```
2. **`scripting`**:
   ```text
   Required to inject the translation overlay script (`src/content/index.js`) into the active comic reader page so translated speech bubbles and clean background layers can be rendered over the comic images.
   ```
3. **`storage`**:
   ```text
   Required to store the user's language preferences (source language, target language, comic font style, translation engine) and optional session token locally in `chrome.storage.local`.
   ```
4. **`Host permission (<all_urls>)`**:
   ```text
   Users read comics, manga, and webtoons across thousands of independent scanlation and publisher domains worldwide, and comic images are served from diverse CDN subdomains. `<all_urls>` is required only when the user triggers translation so the extension can fetch the comic image and overlay the translated text on any comic website the user visits.
   ```

### Privacy Policy URL:
`https://comic.io.vn/#bao-mat`
