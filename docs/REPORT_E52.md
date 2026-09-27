# REPORT E52 — Người lạ tự đăng ký được, và trần chặn lạm dụng

**Ngày:** 2026-09-27 · **Nguồn yêu cầu:** `DAC_TA_TRANG_CHINH_VA_HAN_MUC.md` §4.1

---

## 1. Summary

`POST /api/v1/auth/register` nay **mở cho người lạ**, kèm trần **3 tài khoản mỗi địa chỉ mạng mỗi
ngày**. Tài khoản **đầu tiên** của hệ thống vẫn đòi khoá chung.

---

## 2. Lỗ đang vá

Trước E52, đường đăng ký gắn `dependencies=[Depends(cong_khoa)]` — đòi khoá chung
(`API_ACCESS_KEY`), mà khoá đó **đang được đặt** trên production. Nghĩa là **người lạ không tự tạo
tài khoản được**.

Trái §4.1 đặc tả: *"Đăng ký là thứ người dùng chọn khi muốn nhiều hơn, không phải cổng chặn ở
cửa."* Khách dùng hết 6 trang/ngày **không có đường nào** lên 10.

Giao diện cũng vướng đúng chỗ đó: ô "Khoá chung của hệ thống" hiện với **mọi** lượt tạo tài khoản,
nên người dùng tưởng phải đi xin khoá mới đăng ký được. Hai đầu cùng đóng.

---

## 3. Design Choice

### 3.1. Mở đăng ký mà KHÔNG có trần là tự vô hiệu hoá E49

Đây là phần quan trọng nhất của mini-spec này, và nó **không có trong đặc tả**.

Khách hết 6 trang chỉ cần tạo một tài khoản mới để có 10, rồi lặp vô hạn. Mở đăng ký mà quên con
số này không phải "làm thiếu" — nó là **tự tay vô hiệu hoá toàn bộ hạn mức vừa xây ở E49**.

⇒ `SO_TAI_KHOAN_MOI_MOI_IP_MOT_NGAY`, mặc định **3**. Đủ cho một gia đình hay vài người cùng
phòng, không đủ để biến việc tạo tài khoản thành cách lách hạn mức.

### 3.2. Tài khoản ĐẦU TIÊN vẫn đòi khoá chung

Tài khoản đầu tiên thành **quản trị** và nhận các chapter cũ chưa có chủ. Để người lạ chiếm chỗ đó
là giao quyền quản trị cho người bấm nhanh nhất.

### 3.3. Dùng lại sổ cái, KHÔNG thêm giá trị enum

Đơn vị ở đây là **tài khoản**, không phải trang — nhưng hình dạng dữ liệu y hệt. Nên dùng lại
`so_cai_han_muc` cùng toàn bộ phần khoá song song và chống trùng của nó, phân biệt bằng **tiền tố
chủ thể**:

```
loai_chu_the = khach_ip
chu_the      = "dang-ky:<băm-ip>"   ← bộ đếm TÀI KHOẢN
chu_the      = "<băm-ip>"           ← bộ đếm TRANG (không tiền tố)
```

Hai chuỗi không bao giờ trùng (băm là 32 ký tự hex trần, không chứa dấu hai chấm).

Vì sao không thêm `LoaiChuThe.dang_ky_ip`: thêm giá trị vào một enum Postgres **đang chạy** là một
lượt `ALTER TYPE` trên production, mà `CLAUDE.md` của dự án cảnh báo riêng về enum trong migration.
**E52 không có migration nào** — đổi một chuỗi lấy việc không phải mổ enum.

### 3.4. Không xác định được IP ⇒ `503`, KHÔNG mở tự do

Thà chặn còn hơn để đường tạo tài khoản không có trần nào — đó chính là đường vô hiệu hoá hạn mức.
Thân lỗi nói rõ và chỉ lối đi khác (liên hệ quản trị).

### 3.5. Lùi giao dịch TƯỜNG MINH — và vì sao nó không phải chuyện vặt

Email trùng hoặc mật khẩu yếu **không được** mất suất (cùng luật với "tệp hỏng không mất lượt" của
đường tải lên).

Về nguyên tắc `get_session` đóng phiên khi request nổ và `AsyncSession.close()` tự lùi giao dịch,
nên ở bản chạy thật suất vẫn được trả lại **dù không có dòng `rollback` nào**. Nhưng:

1. bảo đảm khi đó nằm ở **vòng đời của dependency**, cách xa chỗ đọc mã — ai sửa phần cấp phiên
   sau này sẽ phá nó mà không biết;
2. **bộ test ghi đè `get_session` bằng một phiên sống lâu, nên nó không bao giờ quan sát được phép
   lùi kia.** Đo được 27-09: hai bài canh đúng luật này **ĐỎ**, và đỏ vì bàn thử không thấy được,
   không phải vì sản phẩm sai.

⇒ Lùi ngay tại chỗ, để bảo đảm thành thứ **đọc được và kiểm được**. `upload_archive` đã làm đúng
như vậy ở các nhánh lỗi của nó.

---

## 4. Changed Files

| Tệp | Sửa gì |
|---|---|
| `app/services/han_muc_dang_ky.py` (mới) | Trần số tài khoản mỗi IP mỗi ngày |
| `app/api/v1/xac_thuc_routes.py` | Cổng khoá chung CÓ ĐIỀU KIỆN + trần IP + lùi tường minh |
| `app/core/config.py` | `so_tai_khoan_moi_moi_ip_mot_ngay` |
| `frontend/src/components/auth/ManDangNhap.jsx` | Ô khoá chung chỉ hiện cho tài khoản đầu tiên |

**Không có migration.**

---

## 5. New API

`POST /api/v1/auth/register` — không còn đòi `X-API-Key`, **trừ** khi hệ thống chưa có tài khoản.

Lỗi mới `429`:

```json
{"detail": {
  "loi": "vuot_tran_dang_ky", "tran_moi_ngay": 3,
  "reset_luc": "2026-09-28T00:00:00+07:00",
  "thong_diep": "Địa chỉ mạng này đã tạo đủ số tài khoản cho phép trong hôm nay. …"
}}
```

Kèm `Retry-After`. Thông điệp cố ý nói rõ **"địa chỉ mạng này"**: người ở văn phòng có thể bị chặn
dù chính họ chưa tạo tài khoản nào, và không có cách nào tự đoán ra.

`503` khi không xác định được IP — xem §3.4.

---

## 6. Tests

13 bài backend (`test_e52_tu_dang_ky.py`) + 1 bài frontend.

| Bài canh | Canh cái gì |
|---|---|
| `test_tran_theo_IP_lam_cho_han_muc_KHONG_bi_vo_hieu_hoa` | Không có trần ⇒ hạn mức E49 vô nghĩa |
| `test_tai_khoan_DAU_TIEN_van_doi_khoa_chung` | Không giao quyền quản trị cho người bấm nhanh nhất |
| `test_email_trung_KHONG_mat_suat` | Lượt bị từ chối không tiêu suất |
| `test_dang_ky_KHONG_an_vao_han_muc_TRANG` | Hai bộ đếm dùng chung `loai_chu_the`, không được lẫn |
| `E52 — đã có tài khoản thì màn TẠO MỚI không đòi khoá chung` (frontend) | Hai đầu phải gặp nhau |

**Hai đối chứng âm đã chạy:**

1. gỡ trần IP ⇒ `test_tran_theo_IP…` đỏ;
2. gỡ phép lùi tường minh ⇒ hai bài "không mất suất" đỏ.

---

## 7. Remaining Limits

* **Không có xác minh email.** Ai cũng đăng ký được bằng địa chỉ bất kỳ, kể cả không tồn tại. Trần
  theo IP là thứ duy nhất chặn lạm dụng — nó chặn được việc tạo hàng loạt, **không** chặn được
  email giả. Muốn chặn thì cần hạ tầng gửi thư, chưa có.
* **Trần 3 là số đoán**, chưa có dữ liệu hành vi thật.
* Người dùng **đổi mạng** (nhà → 4G) thì được suất mới. Đây là hệ quả bản chất của việc chặn theo
  IP, không sửa được mà không có xác minh email.
* ~~Chưa chạy thật trên production lần nào.~~ **ĐÃ chạy 27-09** qua đúng luồng người dùng trên
  Chrome thật: form đăng ký **không còn ô khoá mở cổng**, `POST /auth/register` → `201`, rồi
  `/auth/login` → `200` vào thẳng. Quan trọng nhất: `GET /auth/me` của tài khoản mới trả
  `"la_quan_tri": false` — **mở đăng ký công khai không mở cửa quản trị**. Trần 3 tài khoản/IP/ngày
  thì chưa chạm tới nên **chưa kiểm được** (mới tạo 1).
