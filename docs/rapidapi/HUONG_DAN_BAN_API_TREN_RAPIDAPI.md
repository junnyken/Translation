# Hướng Dẫn Đưa API Lên Chợ Quốc Tế RapidAPI (Kiếm Tiền USD B2B)

Hệ thống của bạn đã được tích hợp sẵn xác thực cổng **RapidAPI Proxy** và đóng gói sẵn file đặc tả **OpenAPI 3.0 (`frontend/public/tai-ve/openapi-rapidapi.json`)**. Bạn có thể niêm yết API lên **RapidAPI Hub** (chợ API lớn nhất thế giới với hơn 4 triệu lập trình viên) chỉ trong 5 phút theo 4 bước dưới đây:

---

## 🚀 Bước 1: Tạo API Mới Trên RapidAPI Studio (Import 1-Click)

1. Truy cập **RapidAPI Provider Studio**: `https://rapidapi.com/provider` (đăng nhập bằng tài khoản GitHub hoặc Google).
2. Bấm **`Add New API`** ở góc trên bên phải:
   - **API Name:** `AI Comic Manga & Webtoon Translator`
   - **Short Description:** `Automated Manga, Manhwa, Manhua & Webtoon page translation API with smart bubble inpainting, OCR, and AI typesetting.`
   - **Category:** `Artificial Intelligence / Machine Learning` (hoặc `Translation`)
   - **Specify using:** Chọn **`OpenAPI`** → Tải lên file `frontend/public/tai-ve/openapi-rapidapi.json` (hoặc tải trực tiếp tại `https://comic.io.vn/tai-ve/openapi-rapidapi.json`).
3. Bấm **`Add API`** — Toàn bộ 6 Endpoint (`/quota`, `/translate-image`, `/translate-chapter`, `/projects/{project_id}`, `/pages/{page_id}`, `/translate-text`) sẽ tự động được tạo đầy đủ!

---

## 🔗 Bước 2: Cấu Hình Base URL & Khoá Kết Nối Với Máy Chủ Của Bạn

Trong mục **Hub Listing → Gateway / Base URL** trên RapidAPI Studio:
1. **Base URL:** Điền `https://translation-api.vibe1.tinhgon.xyz`
2. **Header tự động gửi kèm (Transformations / Secret Headers):**
   - Tạo 1 tài khoản đại diện cho kênh RapidAPI trên trang `https://comic.io.vn/admin` → Tab **Tài khoản** → Bấm **`⚡ Tạo Key`** để lấy mã `tr_live_...` (và cấp sẵn hạn mức lượt lớn cho tài khoản cổng này).
   - Trên RapidAPI Studio → **Security / Headers**, thêm một Header cố định gửi từ RapidAPI về server của bạn:
     - **Header Name:** `X-Customer-Api-Key`
     - **Header Value:** `tr_live_<MÃ_KEY_CỦA_BẠN>`
   - Hệ thống của bạn tại [`_xac_thuc_developer`](file:///c:/Users/trieunt/Documents/Tool/Translation/backend/app/api/v1/developer_routes.py) cũng tự động nhận diện thêm các header chuẩn của RapidAPI (`X-RapidAPI-User`, `X-RapidAPI-Subscription`) để ghi nhật ký từng khách hàng quốc tế gọi qua RapidAPI!

---

## 💰 Bước 3: Thiết Lập Các Gói Giá Thuê Bao USD (Monetization → Plans & Pricing)

Trong tab **Monetization** trên RapidAPI Studio, cấu hình 4 gói chuẩn quốc tế (RapidAPI tự thu thẻ Visa/Mastercard/PayPal của khách quốc tế và chuyển tiền USD về PayPal/Payoneer của bạn):

| Tên Gói (Plan) | Giá thuê tháng (USD) | Hạn mức (Quota) | Phí vượt mức (Overage) | Đối tượng khách hàng |
| :--- | :--- | :--- | :--- | :--- |
| **Basic (Free Trial)** | **$0.00 / tháng** | `20 requests / tháng` (Hard Limit) | Không | Lập trình viên test thử chất lượng API |
| **Pro (Scanlation)** | **$19.00 / tháng** | `600 requests / tháng` | `$0.04 / request` | Nhóm dịch truyện nhỏ, Bot Discord/Telegram |
| **Ultra (Aggregator)** | **$49.00 / tháng** | `2,000 requests / tháng` | `$0.03 / request` | Website đọc truyện tự động (WordPress Madara) |
| **Mega (Enterprise)** | **$149.00 / tháng** | `8,000 requests / tháng` | `$0.02 / request` | Hệ thống App đọc truyện di động & Cổng truyện lớn |

---

## 🌍 Bước 4: Bật Công Khai (Make API Public)

Vào tab **General** → Chuyển công tắc **API Visibility** sang **`Public`** để API của bạn xuất hiện trên kết quả tìm kiếm toàn cầu của RapidAPI với các từ khóa: `manga translator`, `comic translation`, `manhwa ocr`, `webtoon inpainting`.
