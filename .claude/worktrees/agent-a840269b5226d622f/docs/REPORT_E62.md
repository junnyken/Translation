# REPORT E62 — Dựng lại màn đăng nhập / tạo tài khoản

**Ngày:** 2026-09-28 · **Nguồn yêu cầu:** chủ dự án — *"lần đầu tiên tôi thấy giao diện đăng ký xấu
như vậy, điều chỉnh lại giúp tôi đi, làm lại toàn bộ chuẩn chỉnh lại đẹp"* (kèm ảnh màn hình)

---

## 1. Summary

Màn đăng nhập là thứ **duy nhất** trong app chưa bao giờ đi qua một lượt dựng giao diện: nó vẫn là
`<form>` trần từ lượt Auth slice B. Lượt này dựng lại nó, và trong lúc đo đã bắt được **một lỗi CSS
có sẵn ảnh hưởng cả 7 chỗ khác trong app**, không riêng màn này.

443/443 bài test giao diện xanh, không phải sửa bài nào — mọi chuỗi và nhãn được bài test canh đều
giữ nguyên.

---

## 2. Audit Before Build — đo, không đoán

Ba khuyết điểm đo được trên bản đang chạy:

| Đo cái gì | Giá trị đo được | Vì sao hỏng |
|---|---|---|
| Class của ô nhập | **không có** `.o` | Mọi ô nhập khác trong app dùng `.o` (nền `--the`, viền `--vien-dam`, bo `--bo-nho`). Ba ô ở đây rơi về **kiểu mặc định của trình duyệt** ⇒ trông như trang chưa nạp CSS |
| Khung chứa | `max-width: 380px; margin: 48px auto` | Không có thẻ, không có nền. Một cột 380px dán vào mép trên một canvas rộng **1240px** trống trơn |
| Viền nút chữ | `1px solid rgb(214,211,209)` | `.nut-chu` khai `border: 0` mà **không có tác dụng** — xem §3 |

---

## 3. Phát hiện chính: `.nut-chu` chưa bao giờ hoạt động, ở CẢ 7 chỗ

```css
button:not(.nut):not(.the-vung):not(.nut-bo) { … border: 1px solid var(--vien-dam); … }   /* 0,3,1 */
.nut-chu { border: 0; padding: 0; … }                                                      /* 0,1,0 */
```

Ba `:not()` cho luật quét chung độ đặc hiệu **0,3,1** — cao hơn **bất kỳ** luật một-class nào. Nên
`.nut-chu` (ý định: *liên kết chữ*) hiện ra thành **viên thuốc có viền** ở mọi nơi dùng nó: trang chủ
("Đăng nhập hoặc tạo tài khoản"), thẻ hạn mức ("Thử lại"), bảng chapter chưa có chủ, thanh đầu trang
(tên tài khoản, "Đăng xuất") và chính màn này.

**Vì sao nó sống lâu:** một luật viết `border: 0` mà không có tác dụng **không báo lỗi gì cả** — không
đỏ test, không cảnh báo build, không sai lệch layout đủ lớn để ai phải hỏi. Nó chỉ lộ ra khi đặt hai
nút chữ cạnh một nút thật trên cùng một thẻ.

**Bản vá** — liệt kê ở đúng luật quét chung, không đi bơm độ đặc hiệu ở chỗ khác:

```css
button:not(.nut):not(.the-vung):not(.nut-bo):not(.nut-chu):not(.nut-trong-o) { … }
```

Hệ quả kéo theo đã xử: `.tai-khoan` nới `gap` 8 → 14px, vì hai liên kết gạch chân cạnh nhau ở khoảng
cách cũ đọc ra như **một cụm chữ**, trong khi trước đó chúng là hai viên thuốc tách bạch.

---

## 4. Design Choice

* **Một thẻ, căn giữa hai chiều.** `min-height: max(420px, calc(100vh - 160px))` — trừ theo chiều cao
  thật của màn thay vì một trần cứng (bản nháp đặt `min(76vh, 640px)` và thẻ đứng lệch hẳn lên trên
  ở màn cao 900px, chừa một khoảng trống chết bên dưới — **đo được rồi mới sửa**).
* **`justify-content: safe center`** khai sau `center`: form đăng ký + khối "chưa có tài khoản nào"
  cao **810px**, ở màn thấp hơn thì căn giữa thường **cắt mất phần đầu thẻ**. Trình duyệt chưa hiểu
  `safe` bỏ qua dòng đó và giữ dòng trên.
* **Nút gửi tràn ngang, đường "đổi chế độ" tách bằng một đường kẻ** — một hành động chính, một hành
  động phụ, không tranh nhau.
* **Vệt sáng mờ sau thẻ** (`radial-gradient` màu `--mau-chinh-nhat`): trên nền ngà phẳng, thẻ trắng
  gần như tàng hình.
* **Màn hẹp bỏ căn giữa dọc** — bàn phím ảo ăn mất nửa màn, căn giữa lúc đó đẩy ô email lên khuất.

## 5. Hai thứ sửa được luôn vì đang ở đây (không phải trang trí)

* **`onQuayLai` — đường quay lại trang chủ.** E53 cho khách lạ dùng trang chủ không cần tài khoản,
  nhưng bấm "Đăng nhập" xong thì **không có đường nào quay lại**: `App` bật `muonDangNhap` và màn này
  không hề nhận hàm đảo lại ⇒ người đổi ý chỉ còn cách tải lại trang. Prop là **tuỳ chọn**, nên nơi
  không truyền (các bài test) vẫn không thấy liên kết đó.
* **Nút hiện/ẩn mật khẩu.** Gõ sai mà không xem lại được là lý do phổ biến nhất của một lượt đăng nhập
  hỏng — ở đây nó còn tốn một lượt gọi máy chủ.

Câu dẫn dưới tiêu đề nói **cái lợi đo được** của tài khoản: khách lạ chịu thêm một chốt theo **địa chỉ
mạng dùng chung** (`LoaiChuThe.khach_ip`, `danh_tinh_khach.py:158`), tài khoản thì chỉ có chốt của
riêng mình (`danh_tinh_khach.py:203`). Không viết lời mời suông.

---

## 6. Changed Files

| Tệp | Sửa gì |
|---|---|
| `frontend/src/components/auth/ManDangNhap.jsx` | Dựng lại: thẻ, dấu hiệu sản phẩm, `.o` cho mọi ô, hiện/ẩn mật khẩu, `onQuayLai` |
| `frontend/src/styles.css` | Khối `.man-dang-nhap` viết lại; vá luật quét chung `button:not(…)`; `.tai-khoan` gap 8→14 |
| `frontend/src/App.jsx` | Truyền `onQuayLai={() => setMuonDangNhap(false)}` |

---

## 7. Live Verification — bản ĐÃ BUILD, Chrome thật

Chạy `npm run build` rồi `vite preview`, soi bằng Chrome thật (không phải jsdom), **bốn** trạng thái:

| Trạng thái | Cách dựng | Kết quả |
|---|---|---|
| Đăng nhập, 1280×900 | bấm thật từ trang chủ | Thẻ căn giữa, ô nhập đúng `.o`, nút chữ hết viền |
| Tạo tài khoản, 1280×900 | bấm "Chưa có tài khoản? Tạo mới" | 3 ô + ghi chú "Ít nhất 8 ký tự." |
| Tài khoản ĐẦU TIÊN + lỗi sai khoá | `initScript` chặn `fetch` trả `da_co:false` và 403 | Khối tin + ô khoá chung + khối lỗi đỏ, thẻ cao 810px vẫn **không bị cắt đầu** |
| 390×844 (điện thoại) | `resize_page` | `scrollWidth > innerWidth` = **false** — không tràn ngang |

Thanh đầu trang khi **đã đăng nhập** cũng soi lại (giả phiên bằng `initScript`) vì bản vá §3 chạm tới
nó: tên tài khoản + "Đăng xuất" nay là hai liên kết chữ tách bạch.

## 8. Tests

`npx vitest run` — **443/443 xanh**, 27 tệp. Không sửa bài nào: mọi nhãn (`Email`, `Mật khẩu`,
`Khoá chung của hệ thống`), mọi tên nút (`Đăng nhập`, `Tạo tài khoản`, `Chưa có tài khoản? Tạo mới`)
và chuỗi `Chưa có tài khoản nào` giữ nguyên. Nút "Hiện" mang `aria-label` riêng nên không đụng
`getByLabelText('Mật khẩu')`.

## 9. Remaining Limits

* **Không có bài test nào canh lỗi §3.** Đây là lỗi thị giác thuần: `border` sai không làm đỏ bài test
  nào, và jsdom không tính cascade đủ để bắt. Lần sau có ai thêm `:not()` vào luật quét chung rồi quên
  liệt kê một class thì nó lại im lặng như cũ.
* **Màn hình sau khi ĐÃ đăng nhập vẫn là bố cục cũ** ("Dịch nhanh / Tạo chapter mới", danh sách
  chapter, màn rà soát, hộp thoại tài khoản). E61 dựng lại trang chủ cho khách, E62 dựng lại màn
  đăng nhập — phần bên trong chưa động tới.
* Chưa đo ở Safari/iOS thật; `justify-content: safe center` chọn theo đúng lý do đó nhưng chưa có lượt
  chạy trên máy Apple để khẳng định.
