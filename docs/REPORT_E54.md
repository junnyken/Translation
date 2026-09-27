# REPORT E54 — Nói đúng chính sách giữ tệp, và màn tài khoản

**Ngày:** 2026-09-27 · **Nguồn yêu cầu:** chủ dự án chốt không bật lịch dọn (27-09) · `DAC_TA_TRANG_CHINH_VA_HAN_MUC.md` §4.4

---

## 1. Summary

Hai việc, cùng một nguyên tắc: **nói đúng thứ có thật**.

1. Giao diện thôi gõ cứng "30 phút" — máy chủ nói con số, và nói **theo từng người gọi**.
2. Màn tài khoản (§4.4): email, tên hiển thị, hạn mức đã dùng/còn lại, mốc reset. **Không** bịa
   hạng thành viên hay số liệu chưa có thật.

---

## 2. Lỗi đang vá — một câu SAI trên màn của bản đang chạy

E50 ship với `bat_lich_don_tep` mặc định **TẮT** (đúng: nó là công tắc xoá dữ liệu không hoàn tác
được, phải bật tường minh). Chủ dự án chốt 27-09 là **không bật**.

Nhưng trang chủ vẫn hứa: *"Kết quả chỉ giữ 30 phút… sau đó ảnh gốc, bản dịch và tệp đã gói đều bị
xoá."*

Tệp **không hề bị xoá**. Không mất dữ liệu, nhưng nó phá đúng thứ dự án coi là nguyên tắc: nói thật
về trạng thái. Và nó làm người dùng gấp gáp tải về vì một lý do không tồn tại.

---

## 3. Design Choice

### 3.1. Máy chủ nói chính sách, giao diện không gõ cứng

Thêm `giu_ket_qua_phut: int | null` vào `GET /han-muc` — endpoint trang chủ **đã gọi** sẵn, nên
không mở thêm bề mặt nào cho khách lạ.

`null` = **không tự xoá**.

### 3.2. Phải tính THEO NGƯỜI GỌI, không trả một hằng số

Ba biến quyết định, và kết quả khác nhau giữa hai người dùng trên **cùng một cấu hình**:

| `bat_lich_don_tep` | `tu_xoa_cho_tai_khoan` | Khách lạ | Đã đăng nhập |
|---|---|---|---|
| `false` | bất kỳ | `null` | `null` |
| `true` | `true` | `giu_ket_qua_phut` | `giu_ket_qua_phut` |
| `true` | `false` | `giu_ket_qua_phut` | **`null`** |

Giao diện **không có cách nào** tự suy ra hàng cuối. Thứ tự kiểm cũng quan trọng: lịch tắt thì
**không ai** bị xoá, kể cả khách lạ — có bài canh riêng cho đúng thứ tự đó.

### 3.3. "Không tự xoá" KHÔNG được nói thành "chỗ lưu trữ"

Khi `null`, giao diện nói: *"Kết quả không tự xoá theo giờ. Nhưng vẫn nên tải về ngay — đây không
phải chỗ lưu trữ lâu dài, và chính sách có thể đổi."*

Hứa giữ mãi là một câu sai khác, chỉ theo chiều ngược lại.

### 3.4. Màn tài khoản: ngắn và thật, hơn là đầy và bịa

§4.4 nói rõ: *"Không bịa thêm hạng thành viên hay số liệu chưa có thật."*

Nên màn này **không** có: hạng thành viên, tổng số trang đã dịch từ đầu, số chapter, ngày tham gia,
chuỗi ngày liên tiếp. Hệ thống **không lưu** những thứ đó. Có một bài test quét toàn bộ chữ trên màn
để chặn việc ai đó thêm chúng vào sau này.

Hạn mức lấy từ `/han-muc`, **không tự tính** `tran - da_dung`: `con_lai` là nhỏ nhất trong các chốt,
nên tự tính sẽ cho một con số khác với trang chủ — và người dùng thấy hai số vênh nhau trên cùng một
sản phẩm thì không biết tin cái nào. Khi hai số thật sự lệch, màn này **nói ra lý do** (lượt còn
tính theo địa chỉ mạng dùng chung) thay vì để người dùng tưởng mình tính sai.

---

## 4. Changed Files

| Tệp | Sửa gì |
|---|---|
| `backend/app/schemas/common.py` | `HanMucRead.giu_ket_qua_phut` |
| `backend/app/api/v1/routes.py` | `_giu_ket_qua_phut_cho()` — tính theo người gọi |
| `frontend/src/components/trang-chu/TrangChu.jsx` | Bỏ hằng số `GIU_PHUT`, nói theo máy chủ, hai chiều |
| `frontend/src/components/auth/ManTaiKhoan.jsx` (mới) | Màn tài khoản §4.4 |
| `frontend/src/App.jsx` | Bấm tên ở đầu trang mở màn tài khoản |
| `frontend/src/styles.css` | CSS `.man-tai-khoan` |

**Không có migration.**

---

## 5. Tests

5 bài backend (`test_e54_chinh_sach_giu_tep.py`) + 2 bài trang chủ + 9 bài màn tài khoản.

| Bài canh | Canh cái gì |
|---|---|
| `test_lich_TAT_thi_tra_None_chu_khong_tra_30` | Đúng trạng thái bản chạy 27-09 |
| `test_KHACH_bi_xoa_nhung_TAI_KHOAN_thi_khong` | Cùng cấu hình, hai câu trả lời |
| `test_lich_TAT_thi_KHONG_AI_bi_xoa_ke_ca_khach` | Thứ tự kiểm |
| `E54 — máy chủ nói KHÔNG tự xoá thì giao diện KHÔNG hứa xoá` | Câu trên màn phải khớp cấu hình |
| `E54 — máy chủ đổi số phút thì giao diện nói theo` | Không gõ cứng 30 |
| `KHÔNG bịa số liệu không có thật` | Quét toàn bộ chữ trên màn tài khoản |
| `KHÔNG tự tính con_lai — và NÓI RA khi nó thấp hơn phép trừ` | Hai số không được vênh |

Frontend **422 bài xanh**, build ra bundle thật (CSS 26,95 → 27,27 kB ⇒ style màn tài khoản đã vào
bundle chứ không chỉ vào `src`).

---

## 6. Live Verification — bấm tay trên production (27-09, Chrome thật)

Để kiểm §4.4 phải có phiên đăng nhập, nên tôi **tạo một tài khoản thật** qua đúng luồng người dùng.
Việc đó kiểm luôn E52 (tự đăng ký) lần đầu trên bản chạy thật.

| Đo cái gì | Kết quả |
|---|---|
| `POST /auth/register` | `201`, rồi `POST /auth/login` `200` — vào thẳng, không cần khoá mở cổng |
| Form đăng ký | **Không còn ô "khoá mở cổng"** — đúng thay đổi E52 |
| `la_quan_tri` của tài khoản mới | `false` — **chốt quan trọng nhất**: mở đăng ký công khai KHÔNG mở cửa quản trị |
| Màn tài khoản | Hiện đủ email, tên hiển thị, `10 / 10 trang còn lại (đã dùng 0)`, mốc reset `0h00` |
| Câu chính sách trên màn tài khoản | "Hiện **không tự xoá** theo giờ. Vẫn nên tải về: đây không phải chỗ lưu trữ lâu dài…" |
| Console | **0 thông báo** — không lỗi, không cảnh báo |
| Đóng hộp thoại | Esc **và** bấm ra ngoài đều đóng (hộp không có nút ✕ — hai đường này là cách ra) |
| Đăng xuất | Mã phiên cũ trả **401** — thu hồi ở **máy chủ**, không chỉ quên ở máy khách |

### Hai thứ chỉ đo được khi chạy thật

**1. Lời hứa "tạo tài khoản được nhiều lượt hơn" là THẬT, không phải câu tiếp thị.**
Cùng một trình duyệt: khách `tran: 6` → đăng nhập `tran: 10`.

**2. Máy chủ chọn đúng chốt khi có CẢ HAI danh tính.** Sau khi đăng nhập, trình duyệt vẫn gửi cookie
khách kèm bearer:

```
authorization: Bearer 7_Neyosg…      cookie: ma_khach=ek6t0aM5…
→ {"tran":10,"da_dung":0,"chot":[{"loai":"nguoi_dung",…}],"giu_ket_qua_phut":null}
```

Chỉ **một** chốt, và là `nguoi_dung`. Nếu nhánh `NguoiGoi` chọn cookie trước thì người đã đăng nhập
bị kẹt ở trần 6 của khách — **không có lỗi nào hiện ra**, chỉ là hết lượt sớm hơn 4 trang.
`da_dung: 0` cũng chứng minh 1 trang đã dùng lúc còn là khách **không** bị tính sang tài khoản.

---

## 7. Lỗi PHÁT HIỆN THÊM (chưa vá) — header tràn ở khổ điện thoại

Không thuộc E54, và **có từ trước** (`5df1b0f`, Auth slice B): E54 chỉ đổi tên hiển thị từ chữ tĩnh
thành nút, không làm rộng thêm. Nhưng nó nằm ngay trên đường vào màn tài khoản nên ghi lại.

Đo ở khung `390×844`: `.dieu-huong` là `display:flex; flex-wrap:nowrap`, nút tên không có
`max-width`/`text-overflow` ⇒ nav rộng 422px trong khung 390px.

| Tên hiển thị | Trang cuộn ngang? |
|---|---|
| `An` (2 ký tự) | không |
| `Nguyễn Văn A` (12) | **có** |
| `trieunt@matbao.com` (18) | **có** |

Tức là **không phải do tên thử của tôi dài** — hầu hết tên người Việt và mọi email đều tràn. Hậu quả
đo được: nút **"Đăng xuất" hiện 34/103 px (33%)**, và chỉ tới được sau khi cuộn ngang trang (cuộn tối
đa 48px) — người dùng không nghĩ tới việc cuộn ngang một cái header.

Hộp thoại tài khoản thì **không** bị: 358px trong khung 390px, lề 16px mỗi bên, còn 227px nền trên
và dưới để bấm đóng.

Vá là CSS: cho `.tai-khoan` một `min-width: 0` + nút tên `max-width` kèm `text-overflow: ellipsis`,
hoặc cho `.dieu-huong` `flex-wrap: wrap`. **Chưa làm** — chờ chủ dự án chốt, vì đây là màn chung của
cả app chứ không riêng E54.

---

## 8. Remaining Limits

* Header tràn ở khổ điện thoại (§7) — đã đo, **chưa vá**.
* Còn **một tài khoản thử thật** trên production: `kiemthu-man-tai-khoan@matbao.com`
  (`edaabedd-8eb5-42d2-8f0d-7b27c025db1f`). Xoá bằng `DELETE /api/v1/auth/users/{id}` với phiên quản
  trị. Tài khoản này **không có chapter nào** nên xoá không làm chapter của ai thành vô chủ.
* Màn tài khoản **chỉ đọc** — chưa đổi được tên hiển thị hay mật khẩu. §4.4 không đòi, nhưng người
  dùng sẽ hỏi.
* Nếu chủ dự án bật `BAT_LICH_DON_TEP` về sau, câu trên màn **tự đổi theo** — không phải sửa mã.
  Đó là điểm chính của mini-spec này.
