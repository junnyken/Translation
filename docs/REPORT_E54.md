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

## 6. Remaining Limits

* **Chưa bấm tay** màn tài khoản trên trình duyệt thật.
* Màn tài khoản **chỉ đọc** — chưa đổi được tên hiển thị hay mật khẩu. §4.4 không đòi, nhưng người
  dùng sẽ hỏi.
* Nếu chủ dự án bật `BAT_LICH_DON_TEP` về sau, câu trên màn **tự đổi theo** — không phải sửa mã.
  Đó là điểm chính của mini-spec này.
