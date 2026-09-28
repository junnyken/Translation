# REPORT E64 — Dựng lại TRANG KHÁCH (chưa đăng nhập)

**Ngày:** 2026-09-28 · **Nguồn yêu cầu:** chủ dự án, kèm ảnh màn hình trang khách:
*"đây là phiên bản hoàn chỉnh rồi sao, sao tôi không thấy nó thay đổi"*

---

## 1. Câu hỏi đúng, và câu trả lời thật

Màu và phông trên ảnh họ gửi **đúng là bản E63** (nút tím, ô thả tím, Be Vietnam Pro). Nhưng phần
**bố cục** của E63 làm ở màn **sau khi đăng nhập** — đúng màn họ chụp ở lượt trước. Trang khách hầu
như không đổi, nên nhìn vào thấy "y như cũ" là phản ứng đúng, không phải nhầm lẫn.

Lượt này làm chính trang đó.

---

## 2. Vì sao trang khách trông "chưa dựng xong" — đo được, không phải cảm giác

| Đo cái gì | Giá trị | Hệ quả |
|---|---|---|
| Số thẻ (`.the-lon` hay tương đương) trên trang | **0** | Ô thả ảnh, ô chọn ngôn ngữ, nút bấm là ba thứ rời trôi thẳng trên nền canvas — trong khi **mọi** màn sau khi đăng nhập đều nằm trong thẻ |
| Thanh đầu trang | **không có** | Không hiệu, không tên sản phẩm, không lối đăng nhập cố định |
| `max-width` của trang | 820px | Trên màn 1900px là một dải hẹp giữa hai mảng trắng lớn |
| Chiều cao nội dung / khung nhìn | ~730 / 940px | Trang **kết thúc ở 3/4 màn** rồi để trống — đọc ra như trang tải dở |
| Bề rộng nút chính | **hết bề ngang** (`.vung-gui` là flex-column ⇒ `align-items: stretch`) | Một thanh màu 790px, không ra nút |
| Số `<main>` trong DOM | **2** (lồng nhau) | `App` bọc `TrangChu` trong `<main className="than-trang">`, mà `TrangChu` tự nó đã là `<main>` — HTML không hợp lệ, trình đọc màn hình mất mốc "nội dung chính" |

---

## 3. Đã sửa gì

* **Thanh đầu trang cho khách**: hiệu + tên sản phẩm bên trái, nút **Đăng nhập** bên phải. Liên kết
  "Đăng nhập hoặc tạo tài khoản" cũ — một dòng gạch chân đứng trơ giữa khoảng trắng — bỏ đi, vì nay
  đã có chỗ đúng cho nó.
* **Khu gửi thành một thẻ thật** (nền `--the`, viền, bo góc, đổ bóng) — thống nhất với phần còn lại
  của app.
* **Nút chính hết tràn ngang** (`align-self: flex-start`). Cùng một cái bẫy flex đã gặp ở cụm tab
  của E63: `display: inline-flex` hay `inline-block` không cứu được, phải nói thẳng `align-self`.
* **Ô thả ảnh 220px → 180px** — nó đang là mảng màu lớn nhất trên màn trong khi chỉ là chỗ để thả.
* **`max-width` 820 → 960px**, cột hạn mức 300 → 340px (ở 300px, `"(0h00 giờ Việt Nam)"` bẻ dòng để
  lại mỗi chữ `"Nam)"` đứng một mình).
* **Dải "Cách hoạt động" (3 bước)** ở cuối trang, để trang có kết thúc. Ba bước trả lời đúng câu hỏi
  một người lần đầu vào phải tự đoán: thả ảnh xong thì **chuyện gì** xảy ra, và cuối cùng nhận được
  **cái gì**. Cố ý **không** nhắc lại "khoảng 30 giây mỗi trang" và "tệp giữ 30 phút" — khối
  `<details>` ngay trên đã nói cả hai.
* **Hết lồng `<main>`**: chỉ màn đăng nhập mới cần lớp bọc `.than-trang`.
* **Màn hẹp**: ẩn dòng mô tả dưới tên sản phẩm, để hiệu và nút Đăng nhập nằm cùng một hàng.

---

## 4. Changed Files

| Tệp | Sửa gì |
|---|---|
| `frontend/src/App.jsx` | Thanh đầu trang cho khách; bỏ lồng `<main>`; không truyền `onMoDangNhap` nữa |
| `frontend/src/components/trang-chu/TrangChu.jsx` | Bỏ prop `onMoDangNhap` + dòng đăng nhập cũ; thêm dải 3 bước |
| `frontend/src/styles.css` | `.vung-gui` thành thẻ; `.dau-phai`; `.ds-buoc`; các số đo ở §3 |

## 5. Live Verification — bản ĐÃ BUILD, Chrome thật

| Khổ màn | Kết quả |
|---|---|
| 1900×940, hạn mức thật (giả lập) | Thanh đầu trang + hero + thẻ gửi + `<details>` + 3 bước; trang lấp đầy màn |
| 390×844 | `scrollWidth == innerWidth`; hiệu và nút Đăng nhập **cùng một hàng** (header cao 37px) |
| Đếm `<main>` | **1** (trước là 2) |

**457/457 bài test xanh**, không sửa bài nào. Dòng đăng nhập cũ không nằm trong bài test nào nên gỡ
được an toàn — đã kiểm bằng cách tìm chuỗi đó trong `trang-chu.test.jsx` trước khi gỡ.

## 6. Remaining Limits

* **Dải 3 bước là chữ MỚI**, chưa ai đọc thử ngoài tôi. Nếu nó nói sai nhịp làm việc thật thì nó là
  chữ sai chứ không phải chữ thừa — đáng rà lại khi có người dùng thật.
* Các màn **sâu trong chapter** (sửa tay, rà soát, thuật ngữ) vẫn chưa được xem lại bố cục.
* Lớp phủ trên ảnh trang vẫn **chưa đo lại** độ phân biệt với màu chính tím mới.
