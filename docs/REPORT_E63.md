# REPORT E63 — Tông màu xanh tím, phông tiếng Việt, và bố cục màn làm việc

**Ngày:** 2026-09-28 · **Nguồn yêu cầu:** chủ dự án, kèm ảnh màn hình màn đã đăng nhập và một ảnh
tham khảo (VoxDub Studio): *"trong này tôi còn thấy nó chưa được chỉnh chu và nhìn không được đẹp,
tham khảo vài nơi website điều chỉnh bố cục lại cho phù hợp hơn"* + *"điều chỉnh tổng màu thế và chữ
cũng như bố cục phù hợp hơn không, đi theo tông xanh tím"*

---

## 1. Một câu hỏi đã hỏi trước khi làm

Ảnh tham khảo là **nền tối**. Đổi cả app sang nền tối là việc khác hẳn về khối lượng (phải đo lại
tương phản cho mọi màu ngữ nghĩa, và **ảnh trang truyện** sẽ nằm trên nền tối — soi chữ trên ảnh
sáng giữa nền tối chói hơn hẳn). Chủ dự án chọn: **nền sáng, điểm nhấn xanh tím**.

---

## 2. Màu — chọn bằng SỐ ĐO, không bằng mắt

`tokens.css` tự khẳng định ở đầu tệp rằng mọi tỉ lệ tương phản đều đo bằng công thức WCAG. Trước
lượt này **không có gì bắt câu đó đúng** — nó chỉ là một dòng chú thích.

| Token | Cũ (xanh mực / ngà ấm) | Mới (xanh tím / trắng ngả tím) | Đo được |
|---|---|---|---|
| `--mau-chinh` | `#1e40af` | `#5546cc` | trắng trên nền này **6,70:1** |
| `--mau-chinh-dam` (màu liên kết) | `#1e3a8a` | `#43349f` | **8,83:1** trên nền |
| `--nen` | `#faf9f7` | `#f8f7fc` | — |
| `--chu` | `#1c1917` | `#191528` | **16,71:1** |
| `--mo` | `#6f6862` | `#6a6381` | **5,30:1** |
| `--mo-nhat` | `#948c85` | `#8d86a3` | **3,20:1** |

**Không quay lại đúng `#4f46e5`** — chính là màu mà lượt 24-09 đã bỏ vì "rực và lạnh". `#5546cc`
trầm hơn một bậc (6,70 so với 6,29) và **bỏ nền ngà ấm**: nền vàng ngà cạnh điểm nhấn tím làm cả hai
cùng bẩn màu, nên nền đổi sang trắng ngả tím lạnh, cùng họ với màu chính.

`--tin` **giữ nguyên** xanh ngọc: lý do gốc ("khối thông tin phải phân biệt được với nút hành động")
còn đúng nguyên vẹn, và xanh ngọc cách họ tím còn xa hơn cách họ xanh mực cũ.

### 2.1. Lời hứa trong chú thích thành bài test

`src/styles/tokens.test.js` (MỚI, 14 bài) **đọc giá trị thật trong `tokens.css` rồi tự tính lại** tỉ
lệ tương phản. Đổi màu làm tụt tương phản là đỏ ngay, kể cả khi người đổi quên sửa chú thích.

Ba chi tiết khiến bài này không phải bài xanh trang trí:

* **Có bài tự kiểm phép đo**: trắng/đen = 21:1, cùng màu = 1:1. Không có nó thì một lỗi trong chính
  hàm tính sẽ làm mọi khẳng định còn lại vô nghĩa mà vẫn xanh.
* **`--mo-nhat` bị kẹp HAI đầu**: `>= 3` và `< 4.5`. Đầu dưới giữ nó đủ sáng cho thành phần giao
  diện; đầu trên chặn việc ai đó lặng lẽ hạ `--mo` xuống mức này.
* **Đối chứng âm đã chạy**: đổi `--mo` thành `#c8c4d6` ⇒ **2 bài đỏ**; khôi phục ⇒ xanh lại.

Đọc token dạng hex mà không thấy thì bài **ném lỗi** chứ không lặng lẽ bỏ qua: đổi sang `color-mix()`
hay `rgb()` là phép đo hết hiệu lực, và người đổi phải biết điều đó.

---

## 3. Chữ — Be Vietnam Pro

Phông hệ thống đặt dấu tiếng Việt bằng thuật toán chung; cả giao diện này là chữ Việt dày dấu
(ế, ồ, ữ, ậ) ở cỡ 13–14px. Be Vietnam Pro được vẽ riêng cho tiếng Việt.

* `display=swap` + khai `system-ui` ngay sau trong `font-family`: mạng chặn Google Fonts thì rơi về
  **đúng phông cũ**, không rơi về serif mặc định.
* Thang cỡ chữ giãn ra: `1.65 / 1.12 / 0.98rem` → `1.75 / 1.2 / 1rem`. Bậc h2 và h3 cũ gần bằng nhau
  (1,12 vs 0,98) nên tiêu đề khối và tiêu đề con **không phân cấp được bằng mắt**.

**Phép đo:** `getComputedStyle(body).fontFamily` chỉ trả về **khai báo**, không nói phông đã tải hay
chưa — tôi đo nhầm bằng nó một lượt. Phép đo đúng: `document.fonts` báo `400/loaded`, và cùng một
chuỗi chữ rộng **211px** với Be Vietnam Pro so với **247px** với phông hệ thống.

---

## 4. Bố cục — năm thứ sửa, mỗi thứ vì một lý do nhìn thấy được

| Sửa gì | Vì sao |
|---|---|
| Ruột thanh đầu trang có khung rộng riêng (`.dau-trang-trong`) | Thanh chạy hết bề ngang màn nhưng nội dung nằm gọn giữa trang ⇒ ở màn 1876px, hiệu và ô tìm dạt ra sát hai mép, nhìn như hai trang chồng lên nhau |
| Hai tab thành **cụm hẹp trong một máng nền** | Bản cũ để chúng `flex: 1 1 240px` nên chúng dài hết bề ngang và trông y hệt hai thẻ nội dung bên dưới — người dùng đọc ra "hai mục", không đọc ra "chọn một trong hai" |
| Ba ô chọn nằm cùng MỘT hàng (`auto-fit`) | `1fr 1fr` cứng bẻ ba ô thành 2 + 1: ô thứ ba đứng một mình nửa hàng, cạnh một khoảng trống |
| "Chapter gần đây" lúc trống còn **một dòng** | Bản cũ dựng khối trống cao gần bằng cả cột form, với một **nút chính thứ hai** cạnh "Dịch ngay" — hai nút cùng màu đậm tranh nhau làm hành động chính |
| Bỏ hai câu dẫn lặp | Câu dưới `h1` và câu trong thẻ "Dịch nhanh" nói lại đúng thứ hai tab vừa nói — **ba lần cùng một nội dung** trên một màn |

### 4.1. Hai lỗi thật bắt được khi dựng lại

* **Mục "Tạo chapter" trên thanh đầu trang trước đây KHÔNG làm gì** khi đang mở một chapter. Nó chỉ
  `document.getElementById('nut-tao')?.scrollIntoView(...)`, mà `#nut-tao` **chỉ tồn tại trên trang
  chủ, ở tab "Tạo chapter mới"** — nên `?.` nuốt lời gọi, bấm không có gì xảy ra và không có lời giải
  thích nào. Nay: về trang chủ → mở đúng tab → rồi mới cuộn. Đo được: từ `#project=…`, sau khi bấm
  thì `hash` rỗng, khối hiện ra là "Tạo chapter mới", `#nut-tao` có mặt.
* **Ô chọn ngôn ngữ ở trang khách thiếu class `.o`** — đúng họ lỗi với ba ô của màn đăng nhập ở E62:
  một ô "trần" kiểu mặc định trình duyệt giữa một màn đã có ngôn ngữ thị giác riêng.

---

## 5. Changed Files

| Tệp | Sửa gì |
|---|---|
| `frontend/src/styles/tokens.css` | Cả bảng màu sang xanh tím; đổi luôn các `rgba()` thô (chúng không đi theo biến) |
| `frontend/src/styles/tokens.test.js` | **MỚI** — 14 bài đo tương phản từ chính tệp token |
| `frontend/index.html` | Be Vietnam Pro + `preconnect` |
| `frontend/src/styles.css` | Phông, thang cỡ chữ, `.dau-trang-trong`, cụm tab, `.hang-doi`, `.gan-day-trong` |
| `frontend/src/App.jsx` | Bọc ruột thanh đầu trang; vá mục "Tạo chapter"; gom tiêu đề + tab |
| `frontend/src/components/chapter/ChapterRecentList.jsx` | Khối trống còn một dòng; bỏ prop `onTaoMoi` đã chết |
| `frontend/src/components/chapter/DichNhanh.jsx` | Bỏ câu dẫn lặp |
| `frontend/src/components/trang-chu/TrangChu.jsx` | Ô chọn ngôn ngữ mang `.o` |

## 6. Live Verification — bản ĐÃ BUILD, Chrome thật

| Khổ màn / màn | Kết quả |
|---|---|
| 1876×960, đã đăng nhập | Thanh đầu trang thẳng cột với thân trang; tab gọn; ba ô chọn cùng hàng |
| 1876, tab "Tạo chapter mới" | Ba bước có nhãn tím, bố cục đều |
| 1280, trang khách | Ô chọn ngôn ngữ đã đúng kiểu `.o` |
| 1280, màn đăng nhập | Thẻ tím, chữ mới |
| 390×844, đã đăng nhập | `scrollWidth == innerWidth` (không tràn ngang); hai tab bằng nhau 348px trong máng 358px |
| Mục "Tạo chapter" từ trong một chapter | hash về rỗng, đúng tab, `#nut-tao` có mặt |

**457/457 bài test xanh** (443 cũ + 14 bài màu mới), không sửa bài cũ nào.

## 7. Remaining Limits

* **Phông tải từ Google Fonts** ⇒ phụ thuộc mạng của người dùng. Có `display=swap` và phông dự phòng
  nên hỏng thì xấu chứ không vỡ, nhưng chưa thử ở mạng chặn Google.
* **Chưa soi các màn sâu trong chapter** trong tông mới: màn sửa tay, rà soát nhất quán, bảng thuật
  ngữ. Chúng dùng chung token nên màu tự đổi theo, nhưng *bố cục* thì chưa được xem lại.
* **Lớp phủ trên ảnh trang** (`--phu-suy-ra`, `--phu-du-phong`) giữ nguyên xanh ngọc / hổ phách và
  **chưa đo lại** độ phân biệt của chúng với màu chính mới trên nền tranh nhiều màu.
* Chưa đo ở Safari/iOS thật.
