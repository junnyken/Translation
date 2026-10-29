# UI_REDESIGN — Rà soát và đề xuất làm lại UI/UX

Ngày rà: 2026-10-16. Phạm vi: `frontend/` (React 18 + Vite, CSS thuần). Chỉ đọc mã, chưa mở trình duyệt, chưa sửa mã.
Mọi câu chữ giao diện mới trong tài liệu này là **[ĐỀ XUẤT — chờ duyệt]** (BA chốt wording).

---

## 1. Kiểm kê

### 1.1 Màn hình / route

Không dùng router. `App.jsx` (969 dòng) chọn màn bằng state và `location.hash` (`#project=<id>`, `#page=<id>`; `App.jsx:40,123,243`).

| Màn | Điều kiện | File chính |
|---|---|---|
| Trang chủ dịch nhanh (khách) | chưa đăng nhập, chưa bấm "Đăng nhập" | `trang-chu/TrangChu.jsx` (598), `TheHanMuc.jsx` |
| Đăng nhập / đăng ký | `ManDangNhap` | `auth/ManDangNhap.jsx` |
| Tài khoản | `ManTaiKhoan` | `auth/ManTaiKhoan.jsx` |
| Trang chủ đã đăng nhập (2 tab: Dịch nhanh / Tạo chapter) + chapter gần đây | `oTrangChu` | `App.jsx:575-625`, `chapter/DichNhanh.jsx`, `ChapterCreateForm.jsx`, `ChapterRecentList.jsx` |
| Quản trị: người dùng, đăng nhập ChatGPT | `la_quan_tri` | `auth/QuanTriNguoiDung.jsx`, `DangNhapChatGPT.jsx` |
| Chapter (tổng quan) | `#project=` | `ChapterSummary`, `ChapterProgress`, `QualityPanel`, `BatchPanel`, `ExportPanel`, `ConsistencyPanel`, `GlossaryManager`, `VoiceProfileManager`, `TermCandidatePanel`, `ConsistencyReviewQueue`, `OrientationBox/SummaryCard`, `BangChuaCoChu` |
| Rà soát trang (bbox + panel vùng) | `#page=` | `ReviewToolbar`, `BboxOverlay`, `RegionPanel`, `RegionQualityBox`, `ZoomCropModal` |
| Sửa tay canvas WebGPU | `#project=...` mở canvas | `canvas/CanvasEditor.jsx` (577), `CanvasStage`, `DaiTrang`, `LopVaCo`, `ThuocTinh`, `renderer-webgpu.js` / `renderer-2d.js` |
| Hộp thoại | | `ui/Dialog`, `ExportWarningModal`, `ZoomCropModal` |
| Bộ ui dùng chung | | `ui/`: Alert, Button, Dialog, Dropzone, EmptyState, Field, Icon, ProgressStage, StatusBadge |

Có mockup cũ: `docs/mockup/trang_chinh.html`, `docs/MOCKUP_CANVAS.md` (mockup canvas, 4 màn).

### 1.2 CSS (đếm bằng grep trên `styles.css` 1023 dòng, `styles/canvas.css` 173 dòng, `styles/tokens.css` 116 dòng)

| Hạng mục | Thực tế |
|---|---|
| Token | Đã có `tokens.css`: màu chính/nền/chữ 3 mức/4 màu trạng thái (nền+viền+đậm), bo góc 3 bậc, bóng 3 bậc, lề theo 3 khổ màn. Có test đo tương phản (`styles/tokens.test.js`). Nền tảng tốt. |
| Hex cứng ngoài token | 13 lần, 2 giá trị: `#fff` (11 lần: `styles.css:53,124,133,302,307,343,582`, `canvas.css:31,74,87,155`) và `#a49cc6` (`canvas.css:63,120`). Không có `rgba()` thô ngoài token. |
| Cỡ chữ | **~19 giá trị px khác nhau** (9, 10, 10.5, 11, 11.5, 12, 12.5, 13, 13.5, 14, 14.5, 15, 16, 17, 18, 22, 24, 26, 32) cộng 1rem/1.2rem/1.75rem. Hay gặp nhất: 13px (32 lần), 14px (20), 12.5px (18), 13.5px (16). Không có thang token. Cỡ 9px ở nhãn công cụ (`canvas.css:28`), 10-10.5px ở chú giải. |
| Khoảng cách | Chỉ `--le`, `--khoang` thành token. Phần còn lại gõ tay: gap 2/4/5/6/8/10/12/14, padding 7/9/12/14/18... Nhiều giá trị lẻ không thuộc bội 4px (5, 7, 9, 10, 14). |
| Bo góc | Token `--bo-nho 8 / --bo 12 / --bo-lon 14` nhưng còn 6px (6 lần), 8px cứng (5), 4px, 3px, 2px, 10px, 12px cứng, 999px, 50%. |
| Dark mode | **Không có.** `tokens.css` ghi rõ "cố ý KHÔNG làm dark mode"; không có `prefers-color-scheme`/`data-theme`. Riêng khu canvas dùng `--nen-mo` (#1b1729) làm nền tối (`canvas.css:58`), phần chrome quanh nó vẫn sáng. |
| Breakpoint | 480, 560, 620, 700, 900, 1000, 1100 (`@media` trong styles.css/canvas.css). Không khớp bộ 375/768/1280; token lề dùng 768/1280. |
| Chuyển động | Duy nhất `quay` (spinner, có `prefers-reduced-motion`, `styles.css:158-160`) và `transition: width .25s` ở thanh tiến độ (`:340`, chưa tắt khi reduced-motion). |

### 1.3 Icon và font

- Icon: **một bộ SVG vẽ tay** trong `ui/Icon.jsx` (13 hình, stroke 2, `aria-hidden`) + thêm SVG inline riêng ở `CanvasEditor.jsx:20-33` (công cụ canvas) + chữ "T" làm icon (`:28`). **Không có emoji** trong JSX. Còn ký tự mũi tên Unicode trong chữ: `← Vùng trước` / `Vùng sau →` (`App.jsx:843,855`), "→" trong nhãn nguồn/đích (`ChapterProgress.jsx:72`, `VoiceProfileManager.jsx:141`). Hai nơi định nghĩa icon (Icon.jsx và CanvasEditor) là hai nguồn.
- Font: Be Vietnam Pro 400/500/600/700, nạp từ Google Fonts qua `<link>` (`index.html:12-17`); phụ `ui-monospace` cho mã (`styles.css:258`). Hai họ, đúng luật.

---

## 2. Rà soát theo checklist (mục 9)

Ký hiệu: Đạt / Chưa đạt / Chưa kiểm (cần trình duyệt).

### 2.1 Hệ thống

| Mục | Kết quả | Bằng chứng |
|---|---|---|
| Có token màu, bề mặt, chữ 3 mức, trạng thái | Đạt | `tokens.css:24-66` |
| Thang cỡ chữ định nghĩa | **Chưa đạt** | 19 cỡ px tuỳ ý, không token (đếm ở 1.2); chỉ h1-h3 có thang (`styles.css:30-35`) |
| Khoảng cách bội 4px | **Chưa đạt** | gap/padding 5, 7, 9, 10, 14 khắp `styles.css`; token chỉ có `--le`, `--khoang` |
| Bo góc / bóng token | Đạt một phần | token có (`tokens.css:93-104`) nhưng còn 6px/10px/12px/3px cứng |
| Sáng + tối | **Chưa đạt** | không có dark mode (`tokens.css:4`); canvas là khu tối duy nhất, không có chuyển theme |
| Một bộ icon, không trộn emoji | Đạt một phần | không emoji; nhưng 2 nơi vẽ icon + ký tự mũi tên Unicode + chữ "T" |
| Tối đa 2 họ font, thử dấu chồng | Đạt (họ) / Chưa kiểm (dấu chồng ở 9-11px) | `styles.css:15`, `canvas.css:28` nhãn 9px |
| Hex cứng ngoài token | Chưa đạt nhẹ | `#a49cc6` ×2 chưa thành token; `#fff` nên là `--tren-chinh` |

### 2.2 Trợ năng

| Mục | Kết quả | Bằng chứng |
|---|---|---|
| Tương phản ≥4.5:1 | Đạt cho token chữ chính/phụ; `--mo-nhat` 3.2:1 chỉ cho chữ giảm nhấn | `tokens.css:35-43`, đã có test `tokens.test.js`. Chưa kiểm: chỗ nào thực tế đang dùng `--mo-nhat` cho chữ cần đọc (vd `.ma` ở `styles.css:258`, chữ 12px) |
| Focus rõ | Đạt | `:where(...):focus-visible` toàn cục (`tokens.css:112`) |
| aria-label cho nút chỉ icon | Đạt ở canvas (`CanvasEditor.jsx:435`) | 50 `aria-label` trong JSX. Chưa kiểm hết các nút icon khác |
| Hộp thoại | Đạt một phần | `role="dialog"`, `aria-modal`, Esc đóng, focus vào hộp (`Dialog.jsx:11-24`). **Thiếu bẫy focus** (Tab ra phía sau) và trả focus về nút mở. `ExportWarningModal`/`ZoomCropModal` tự viết lại role riêng (`ExportWarningModal.jsx:54`, `ZoomCropModal.jsx:75`) thay vì dùng `Dialog` |
| Tab / bàn phím | **Chưa đạt** | `role="tablist"` ở `App.jsx:596` có `role="tab"` nhưng không có `tabpanel`, không có phím mũi tên, không `tabIndex` roving |
| Phím tắt canvas | Đạt | H/V/B/E/I, [ ] + - (`CanvasEditor.jsx:364-367`) |
| prefers-reduced-motion | Đạt một phần | chỉ tắt spinner; `transition: width` thanh tiến độ chưa tắt (`styles.css:340`) |
| Vùng báo trạng thái (aria-live) | Đạt một phần | 13 chỗ `aria-live/role=status/alert`; chưa kiểm phủ hết |
| Mục tiêu chạm ≥ 40-44px | **Chưa đạt ở canvas** | nút công cụ 38×38 (`canvas.css:20`), hàng cột trang 52px; nhiều nút 6px 12px / font 13px. Chưa kiểm thực đo ở 375px |
| Ảnh có alt | Đạt | `BboxOverlay.jsx:97`, `TrangChu.jsx:559` |

### 2.3 Trạng thái và dữ liệu

| Mục | Kết quả | Bằng chứng |
|---|---|---|
| Đang tải | Đạt rải rác, **không nhất quán** | chữ "Đang tải…" ở `App.jsx:784`, `ZoomCropModal.jsx:82`; hạn mức có trạng thái riêng `TheHanMuc.jsx:47`. Không có skeleton/mẫu dùng chung |
| Rỗng | Đạt | `ui/EmptyState.jsx` dùng chung; canvas có màn rỗng (docs/MOCKUP_CANVAS) |
| Lỗi | Đạt | `Alert` (loi/canh/tin), lỗi hiện ngay (`loi-hien-ngay.test.jsx`), "thử lại" ở `TheHanMuc` |
| Không có quyền | Đạt | 401 hết phiên (`App.jsx:563-570`), admin chỉ hiện với quản trị (`:582`), `khoa-truy-cap.test.jsx` |
| Một phần dữ liệu | Chưa kiểm | ví dụ chapter có trang lỗi một phần: có "chạy lại trang hỏng" (`BatchPanel.jsx:39`) nhưng cần xem trên màn |
| Không hiện 0 thay cho "chưa biết" | Chưa kiểm | cần soát từng số (đếm vùng, điểm chất lượng, hạn mức) |
| Nút khoá nói rõ lý do | Đạt | `Button.jsx` có `lyDoKhoa` |

### 2.4 Hành động ghi

| Mục | Kết quả | Bằng chứng |
|---|---|---|
| Nút đang chạy có spinner + khoá | Đạt | `Button.jsx` |
| Xác nhận việc phá huỷ / cảnh báo trước khi xuất | Đạt | `ExportWarningModal` |
| Phản hồi sau khi lưu | Chưa kiểm | cần bấm thử (toast vs `Alert` tĩnh `App.jsx:571`) |
| Không mất việc đang làm | Đạt một phần | thông báo "việc dở nằm trên máy chủ" (`App.jsx:566`); chưa kiểm cảnh báo rời canvas khi đang sửa chưa lưu |

### 2.5 Đáp ứng (375 / 768 / 1280)

| Mục | Kết quả | Bằng chứng |
|---|---|---|
| Breakpoint | **Chưa đạt chuẩn** | 7 điểm gãy lẻ (480…1100), không phải 375/768/1280 |
| Canvas trên điện thoại | Đạt theo tài liệu | dải trang ẩn, bảng thuộc tính xuống dưới (`canvas.css:165`, docs/MOCKUP_CANVAS.md) |
| Chiều cao canvas | Rủi ro | `height: calc(100vh - 64px)` (`canvas.css:4`): trình duyệt di động thanh địa chỉ co giãn nên tràn; nên dùng `100dvh`. Chưa kiểm |
| Bảng rộng | Rủi ro | `min-width: 560px` (`styles.css:420`) cần cuộn ngang ở 375px, chưa kiểm có bọc cuộn |
| Kiểm ở 375/768/1280 | **Chưa kiểm** | cần trình duyệt |

### 2.6 Giấy phép / phụ thuộc

| Mục | Kết quả | Bằng chứng |
|---|---|---|
| Phụ thuộc runtime | Rất gọn: chỉ react, react-dom | `package.json` |
| Font | Be Vietnam Pro (SIL OFL) nạp từ Google Fonts | `index.html:12`. Rủi ro: gọi bên thứ ba (riêng tư, mạng nội bộ chặn); nên tự lưu `woff2` (OFL cho phép) |
| Icon | Vẽ tay, không giấy phép bên ngoài | `Icon.jsx` |
| Tham chiếu hãng khác | Không sao chép thương hiệu | xem mục 4 |

---

## 3. Đề xuất theo khung mục 10

### (1) Brief và giả định còn thiếu

| Trường | Điền |
|---|---|
| Sản phẩm | Web dịch truyện tranh sang tiếng Việt: tải trang/gói → tự nhận diện, OCR, xoá chữ, dịch, đặt chữ → sửa tay → xuất CBZ/ZIP/PSD |
| Người dùng | Khách thử nhanh (không đăng nhập); nhóm dịch / người đọc làm chapter hàng loạt; quản trị |
| Việc chính | (a) thả file và nhận kết quả nhanh; (b) quản lý chapter và theo dõi mẻ chạy; (c) sửa tay trên ảnh lớn lâu (phiên dài) |
| Mật độ | Cân bằng: trang chủ thoáng, màn chapter vừa, canvas dày kiểu công cụ |
| Giữ | nhận diện tím-xanh `#5546cc`, Be Vietnam Pro, CSS thuần + biến, bộ `ui/` hiện có |
| Thiết bị | desktop chính; điện thoại cho trang chủ và xem kết quả; sửa tay trên điện thoại chỉ cần dùng được ở mức cơ bản |

Giả định cần chủ dự án xác nhận:
1. Có làm dark mode toàn app không, hay chỉ canvas tối? (đề xuất: có cả hai, mặc định theo hệ thống)
2. Mức ưu tiên thiết bị: sửa tay trên tablet có cần không?
3. Có logo/bộ nhận diện chính thức hơn chữ cái trong ô tím (`.hieu-dau`, `styles.css:51`)?
4. Có cho phép dùng `lucide-react` (một phụ thuộc mới) hay giữ SVG inline? (đề xuất ở mục 5)
5. Ngôn ngữ giao diện chỉ tiếng Việt?
6. Tập truyện của người dùng có tính nhạy cảm (ảnh bản quyền)? Ảnh nên không tải lên bên thứ ba nào ngoài hệ thống: giữ nguyên.

### (2) Hướng tham chiếu (mô tả cấu trúc)

| Hướng | Cấu trúc | Hợp với |
|---|---|---|
| A. Workspace công cụ chỉnh ảnh | Thanh trên mảnh + cột công cụ icon trái + khu trung tâm tối + panel thuộc tính phải thu gọn được + dải trang dưới/trái | Màn sửa tay. Hiện đã gần hướng này, cần hoàn thiện trạng thái, kích thước chạm, theme tối |
| B. Thư viện lưới thẻ | Lưới thẻ chapter có ảnh bìa (trang 1), thanh tiến độ mảnh, nhãn trạng thái; lọc/tìm phía trên; nút "Tạo chapter" cố định | Danh sách chapter, "Chapter gần đây" (đang là list chữ, `styles.css:256`) |
| C. Trang đích một việc | Hero một câu + một vùng thả file lớn; kết quả hiện tại chỗ; 3 bước "Cách hoạt động" bên dưới | Trang chủ khách. Giữ, chỉ chuẩn hoá khoảng cách và trạng thái |
| D. Dòng việc (pipeline) | Thanh bước nhìn thấy: Nhận diện → OCR → Xoá chữ → Dịch → Đặt chữ → Xong, mỗi bước có trạng thái | Tiến độ chapter và mẻ (đã có `ProgressStage`, nâng thành thành phần chuẩn dùng ở mọi nơi) |

Khuyến nghị: C cho trang chủ, B + D cho chapter, A cho sửa tay.

### (3) Token đề xuất

Nguyên tắc: giữ tên token tiếng Việt hiện có (không đổi hàng loạt), **thêm** thang chữ, khoảng cách, màu tối; dùng `oklch()` không bắt buộc, giữ hex cho khớp `tokens.test.js` đang đọc hex. Giá trị sáng giữ nguyên bản hiện tại (đã đo). Giá trị tối dưới đây là **đề xuất, cần chạy lại test tương phản trước khi nhận**.

**Màu (sáng, giữ nguyên) và tối (mới)**

| Token | Sáng | Tối |
|---|---|---|
| `--mau-chinh` | `#5546cc` | `#9b8cff` (nhấn sáng hơn cho nền tối) |
| `--mau-chinh-dam` (liên kết) | `#43349f` | `#b9aeff` |
| `--mau-chinh-nhat` | `#f0edfe` | `#2a2450` |
| `--tren-chinh` (chữ trên nút chính, MỚI, thay `#fff` cứng) | `#ffffff` | `#14102b` |
| `--nen` | `#f8f7fc` | `#12101c` |
| `--the` | `#ffffff` | `#1b1829` |
| `--the-mo` | `#f3f1fa` | `#242036` |
| `--vien` / `--vien-dam` | `#e6e3f2` / `#d2cee4` | `#2f2a45` / `#443e63` |
| `--chu` | `#191528` | `#ece9f8` |
| `--mo` (chữ phụ) | `#6a6381` | `#a8a1c4` |
| `--mo-nhat` (chỉ trang trí) | `#8d86a3` | `#7a7396` |
| `--ok` / `--canh` / `--loi` / `--tin` | `#047857 / #b45309 / #b91c1c / #0e7490` | `#34d399 / #fbbf24 / #f87171 / #22d3ee` |
| nền trạng thái | giữ `-nen` hiện có | `color-mix(in srgb, <màu> 14%, var(--the))` |
| `--nen-canvas` (MỚI, thay `--nen-mo` cho khu xem truyện) | `#1b1729` | `#0d0b14` |
| `--chu-tren-canvas` (MỚI, thay `#a49cc6`) | `#b4acd6` | `#b4acd6` |

Canvas luôn tối ở cả hai theme: nền trung tính (không viền màu) giúp soi màu trang truyện; chỉ chrome quanh nó đổi theo theme.

**Thang chữ (Be Vietnam Pro; gom 19 cỡ về 7 bậc)**

| Token | px / line-height | Dùng cho | Thay các cỡ cũ |
|---|---|---|---|
| `--cc-xs` | 12 / 1.4 | chú thích, mã, nhãn công cụ | 9, 10, 10.5, 11, 11.5, 12, 12.5 |
| `--cc-sm` | 13 / 1.45 | chữ phụ, panel đặc, bảng | 13, 13.5 |
| `--cc-md` | 14 / 1.55 | chữ thân bài, nút, ô nhập | 14, 14.5, 15 |
| `--cc-lg` | 16 / 1.5 | tiêu đề thẻ (h3) | 16, 17 |
| `--cc-xl` | 20 / 1.3 | tiêu đề khối (h2) | 18, 1.2rem |
| `--cc-2xl` | 28 / 1.2 | tiêu đề màn (h1) | 22, 24, 26, 1.75rem |
| `--cc-3xl` | 40 / 1.1 | chỉ hero trang chủ khách ≥1280px | 32 |

Sàn chữ 12px, không còn 9-11px. Nhãn phím công cụ (`H`, `V`) hiện 9px nên đưa lên 12px hoặc chuyển vào tooltip. Quy tắc: chữ có dấu chồng (Ướt, Quyết định, Nhượng quyền) thử ở 12px, line-height không dưới 1.4.

**Khoảng cách (bội 4)**: `--s-1: 4px; --s-2: 8px; --s-3: 12px; --s-4: 16px; --s-5: 20px; --s-6: 24px; --s-8: 32px; --s-10: 40px; --s-12: 48px`. Bỏ các giá trị 5, 7, 9, 10, 14 (gom xuống 4/8/12/16). `--le`/`--khoang` giữ.

**Bo góc**: `--bo-xs: 4px` (huy hiệu, ô nhỏ), `--bo-nho: 8px` (nút, ô nhập), `--bo: 12px` (thẻ), `--bo-lon: 16px` (hộp thoại, khối lớn), `--bo-tron: 999px`. Bỏ 2, 3, 6, 10, 14.

**Bóng**: giữ 3 bậc hiện có; ở tối thay bóng bằng viền sáng 1px (`--vien`) và bóng đậm hơn `rgba(0,0,0,.5)` cho hộp thoại.

**Breakpoint**: đúng bộ kiểm 375 / 768 / 1280 → `@media (min-width:768px)`, `(min-width:1280px)` mobile-first; xoá 480/560/620/700/900/1000/1100 dần theo từng màn.

**Chuyển động**: 120-200ms, chỉ cho báo trạng thái (đổi tab, mở hộp thoại, thanh tiến độ); bọc toàn bộ trong `@media (prefers-reduced-motion: no-preference)`. Không hiệu ứng trang trí trong tool.

**Mục tiêu chạm**: tối thiểu 40px desktop, 44px dưới 768px (nút công cụ canvas từ 38 → 40/44).

### (4) Thư viện / thành phần

Dùng:
- Giữ **React + CSS thuần + biến CSS**. Không đề xuất Tailwind/shadcn: chi phí viết lại ~1.250 dòng CSS và 60+ component, mất `tokens.test.js`, không có lợi tương xứng.
- **Icon: một bộ duy nhất.** Khuyến nghị A (không thêm phụ thuộc): mở rộng `ui/Icon.jsx` làm nguồn duy nhất, sao các đường vẽ từ Lucide (ISC, tương thích dùng thương mại) vào đó, ghi nguồn + giấy phép trong tệp; chuyển SVG của `CanvasEditor.jsx:20-33` sang `Icon`. Phương án B: `lucide-react` (tree-shake, ~1KB/icon) — cần chủ dự án duyệt vì thêm phụ thuộc. Mũi tên "←/→" trong chữ đổi thành `Icon`. Icon vẫn `aria-hidden` + nhãn chữ.
- Font: tự lưu Be Vietnam Pro `woff2` (400/500/600/700, subset latin + vietnamese) và `font-display: swap`, bỏ gọi Google Fonts. OFL cho phép, ghi vào `docs/FONTS.md`.
- Thành phần mới trong `ui/`: `Tabs` (đúng ARIA + phím mũi tên), `Skeleton`, `Toast`/vùng `aria-live`, `Card`/`ChapterCard`, `PipelineSteps`, `Toolbar`; nâng `Dialog` với bẫy focus + trả focus, rồi dùng cho `ExportWarningModal`, `ZoomCropModal`.
- Công cụ theme: thuộc tính `data-theme="light|dark"` trên `<html>`, mặc định theo `prefers-color-scheme`, nhớ lựa chọn trong `localStorage`. Thêm `color-scheme` để ô nhập/cuộn gốc đổi theo.

KHÔNG dùng:
- Emoji trong giao diện; ký tự Unicode làm icon.
- Thư viện UI nặng (MUI, Ant, Chakra), animation lib (Framer Motion) — hiệu ứng không thuộc tool vận hành.
- Hiệu ứng glassmorphism/gradient nền trong tool; chỉ trang chủ khách được có điểm nhấn nhẹ.
- Màu cứng và cỡ chữ cứng trong component (thêm quy tắc kiểm trong test token).

### (5) Trạng thái cần thiết kế từng màn

| Màn | Tải | Rỗng | Lỗi | Không quyền | Một phần |
|---|---|---|---|---|---|
| Trang chủ khách | thẻ hạn mức (đã có) | chưa có file | file không hợp lệ/quá lớn; hết hạn mức | hết hạn mức → mời đăng nhập | một số trang xong, một số lỗi |
| Đăng nhập / tài khoản | nút đang chạy | — | sai mật khẩu, mạng | phiên hết hạn | — |
| Danh sách chapter | skeleton lưới thẻ | chưa có chapter + nút tạo | không tải được + thử lại | — | thẻ có trang lỗi |
| Chapter tổng quan | skeleton khối | chapter 0 trang | lỗi tải/chạy | chapter của người khác | tiến độ x/y, vài trang hỏng |
| Mẻ chạy | thanh bước đang chạy | chưa chạy | trang hỏng + chạy lại | — | dừng giữa chừng, tiếp tục |
| Rà soát trang | tải ảnh | trang không có chữ (đã có `BangChuaCoChu`) | ảnh không tải | — | vùng chưa duyệt |
| Sửa tay canvas | tải ảnh/khởi tạo WebGPU | chưa có trang | không có WebGPU (fallback 2D), ảnh lỗi | — | lưu chưa xong, đang chạy lại vùng |
| Xuất | đang gói | chưa chọn định dạng | lỗi xuất, cảnh báo trước khi xuất | — | xuất thiếu trang |
| Quản trị | skeleton bảng | chưa có người dùng | lỗi | không phải quản trị (404) | — |

Nguyên tắc: không hiện `0` khi chưa biết, hiện `—` kèm nhãn "chưa có dữ liệu" **[ĐỀ XUẤT — chờ duyệt]**.

### (6) Rủi ro

| Loại | Rủi ro | Giảm |
|---|---|---|
| Giấy phép | icon Lucide (ISC), Be Vietnam Pro (OFL) | ghi nguồn trong `docs/FONTS.md` và `Icon.jsx`; không sao chép thương hiệu bên thứ ba |
| Hiệu năng | canvas WebGPU + ảnh lớn; thêm theme/skeleton không đụng canvas; font tự lưu giảm một lượt gọi ngoài | giữ renderer nguyên; đo lại tải trang đầu; `loading="lazy"` cho lưới thẻ; thumbnail bìa phải do backend cắt nhỏ (chưa biết có endpoint, cần hỏi DEV) |
| Trợ năng | dark mode làm tụt tương phản; nút chạm nhỏ; Tab/Dialog thiếu bàn phím | chạy lại `tokens.test.js` cho bộ màu tối; thêm Tabs/Dialog đúng ARIA; kiểm bàn phím |
| Hồi quy | đổi tên token/bo góc hàng loạt phá 60+ bài test hiện có | thêm token mới, ánh xạ cái cũ, đổi từng màn; không đổi tên token cũ |
| Chi phí | ~1.250 dòng CSS đang dùng cỡ chữ/khoảng cách rời | làm theo thứ tự mục 7; có thể thay bằng tìm-thay có kiểm |
| Phạm vi | thay mockup ≠ thay hành vi | UI mới không đổi API/luồng; wording mới qua BA |

### (7) Màn nên dựng mockup trước (ưu tiên)

Mockup phải có empty + error state theo hợp đồng BA/DEV, dựng bằng `/mockup` (mỗi màn một file `screens/<id>.html`), kiểm ở 375/768/1280, sáng + tối.

1. **Sửa tay canvas (ưu tiên 1)**. Thanh trên 48px: tên chapter/trang · hoàn tác/làm lại · zoom · Xuất. Cột công cụ trái 48-56px, nút 40px, icon + phím trong tooltip. Dải trang trái 84px (ẩn dưới 768px, thành dải ngang dưới canvas). Khu giữa nền `--nen-canvas`, không viền màu. Panel thuộc tính phải 280px thu gọn được; dưới 768px thành ngăn kéo từ đáy. Chấm trạng thái trang (ok/cảnh báo/lỗi) kèm icon, không chỉ màu. Thêm trạng thái: lưu xong/đang lưu, không WebGPU, chưa có trang. Cập nhật từ mockup đã có ở `docs/MOCKUP_CANVAS.md`.
2. **Trang chủ khách (dịch nhanh)**. Header gọn (logo, Đăng nhập). Hero một câu + vùng thả file lớn chiếm 2/3 chiều ngang ở 1280, toàn bề ngang ở 375. Dưới: thẻ hạn mức (đã có `TheHanMuc`), tiến độ theo bước (D), kết quả dạng lưới ảnh trang đã dịch + nút "Tải về", rồi "Cách hoạt động" 3 bước.
3. **Trang chủ đã đăng nhập + danh sách chapter**. Tab "Dịch nhanh / Tạo chapter" (Tabs chuẩn ARIA) bên trái; bên phải hoặc bên dưới ở <1280: lưới thẻ chapter (bìa = trang 1, tên, ngôn ngữ nguồn → Việt, thanh tiến độ, nhãn trạng thái, thời gian). Thanh tìm + lọc trạng thái. Rỗng: minh hoạ + "Tạo chapter".
4. **Chapter tổng quan**. Tiêu đề + hàng nút hành động (Chạy mẻ, Rà soát, Xuất). Thanh bước pipeline D. Cột chính: lưới trang (thumbnail + chấm trạng thái) với lọc; cột phụ: Chất lượng, Thuật ngữ/giọng nhân vật (gộp dưới tab), Mẻ chạy. Hiện cảnh báo trang hỏng một phần.
5. **Rà soát trang (bbox + vùng)**. Giống bố cục canvas: ảnh giữa nền tối, danh sách vùng bên phải (lọc: tất cả / cần xem), thanh trước/sau + phím tắt; hộp thoại phóng to cắt dùng `Dialog` mới.
6. **Xuất + hộp thoại cảnh báo**. Chọn định dạng (CBZ/ZIP/PSD) bằng nhóm radio dạng thẻ; danh sách cảnh báo trước khi xuất (icon + chữ, không chỉ màu); tiến trình gói; tải về. Trạng thái: lỗi, xuất thiếu trang.

Màn đăng nhập/tài khoản/quản trị làm sau, chỉ áp token mới (không cần mockup riêng).

### (8) Kế hoạch kiểm thử

Tự động (chạy được trong workspace):
- `npm test` (vitest): giữ xanh; mở rộng `tokens.test.js` đo tương phản cho bộ tối + thêm bài quét: không hex/px ngoài token trong component mới.
- Thêm bài test cho `Tabs` (phím mũi tên, `aria-selected`), `Dialog` (bẫy focus, trả focus, Esc), `Icon` (aria-hidden, nhãn đi kèm).

Thủ công (cần trình duyệt, **chưa kiểm được** ở lượt này):
- 375 / 768 / 1280 cho mọi màn ở mục 7, theme sáng và tối.
- Tab qua toàn bộ màn, nhìn vòng focus; dùng phím tắt canvas; đọc bằng trình đọc màn hình ở trang chủ và hộp thoại.
- Chữ có dấu chồng (Ướt, Quyết định, Nhượng quyền) ở cỡ 12px, không bị cắt dấu.
- Đo tương phản thực tế chữ `--mo-nhat` đang dùng ở chỗ nào.
- Canvas: `100dvh` trên điện thoại thật, chạm 44px, WebGPU và fallback 2D, ảnh lớn không giật khi đổi theme.
- Bấm thử từng trạng thái ở mục 5 (tải/rỗng/lỗi/không quyền/một phần), nhất là số `0` so với "chưa biết".
- Mockup B (`translation-mockup.b.matbao.ai`) từ workspace không vào được (xem `MOCKUP_CANVAS.md`): cần mở từ mạng Mắt Bão.
- Reduced motion: bật cài đặt hệ thống, xác nhận thanh tiến độ không chạy.

### Thứ tự thực hiện đề xuất

1. Thêm token (chữ, khoảng cách, bo góc, màu tối) vào `tokens.css`, chưa đổi component.
2. `Icon` hợp nhất, `Tabs`, `Dialog` chuẩn, `Skeleton`, `Toast`.
3. Dựng và duyệt mockup 6 màn (BA duyệt wording).
4. Áp từng màn: canvas → trang chủ khách → danh sách chapter → chapter → rà soát → xuất.
5. Bật dark mode, tự lưu font, dọn breakpoint cũ.
