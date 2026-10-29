# REPORT E56 — Tự đổi tên hiển thị và mật khẩu

**Ngày:** 2026-09-27 · **Nguồn yêu cầu:** chủ dự án ("màn tài khoản vẫn chỉ đọc") · giới hạn đã tự ghi ở `REPORT_E54.md` §8

---

## 1. Summary

`PATCH /api/v1/auth/me` — người dùng tự đổi **tên hiển thị** và **mật khẩu** của chính mình. Màn
tài khoản (§4.4) từ chỗ chỉ đọc nay sửa được.

---

## 2. Audit Before Build — lỗ nghiêm trọng hơn tôi tưởng

Tôi vào định thêm một ô nhập. Đọc code thì thấy đây không phải chuyện tiện lợi:

* `PATCH /auth/users/{id}` là đường của **quản trị** và **cố ý** không nhận `ten_hien`/`mat_khau`.
  Docstring nói thẳng lý do: *"quản trị được phép chặn người khác, nhưng không được phép **hoá
  trang thành họ**. Đổi email hay mật khẩu của người khác là làm đúng việc đó."*
* Không có đường nào khác đổi mật khẩu.

⇒ Trước E56, **một mật khẩu đã lộ là không thể xoay**. Không phải "bất tiện" — người dùng không có
cách nào tự bảo vệ, và cũng không ai làm hộ được.

### Một thứ tôi nghi sai, và kiểm nên không báo oan

Màn đăng nhập hiện chữ *"Ít nhất 8 ký tự"*, mà `DangKyRequest.mat_khau` khai `min_length=1`. Tôi
nghi đây là câu trên màn hứa một luật không có thật (đúng họ lỗi của E54). Tra tiếp thì
`services/tai_khoan.py:27` có `DAI_MAT_KHAU_TOI_THIEU = 8` và `dang_ky()` gọi
`kiem_mat_khau_du_manh()` — luật **được máy chủ ép thật**. E56 dùng lại đúng hàm đó thay vì viết
ngưỡng mới: hai đường hai ngưỡng là một cửa sau để đặt mật khẩu 1 ký tự.

---

## 3. Design Choice

### 3.1. Đường RIÊNG, không nhét vào đường của quản trị

`PATCH /auth/me` **không có tham số `{id}`**. Đó không phải chuyện thẩm mỹ URL: không có id thì về
cấu trúc đã **không nhắm được vào ai khác**, nên không cần một phép kiểm quyền có thể viết sai. So
với việc thêm `ten_hien` vào `PATCH /users/{id}` — nơi mà quên một dòng `if id != minh` là cho phép
quản trị hoá trang thành người khác.

`SuaTaiKhoanRequest` cũng cố ý **không có** `la_quan_tri`/`dang_hoat_dong`: nhận là lỗ tự phong
quyền.

### 3.2. Đổi mật khẩu PHẢI có mật khẩu cũ

Không đòi thì một phiên bị mượn (máy công cộng chưa đăng xuất, mã phiên bị lấy) **chiếm hẳn** được
tài khoản: kẻ kia đặt mật khẩu mới và chính chủ mất đường vào. Đòi mật khẩu cũ biến "mượn được
phiên" thành "vẫn không đổi được khoá".

### 3.3. Thu hồi mọi phiên KHÁC, giữ lại phiên đang dùng

Đúng cùng lý do `PATCH /users/{id}` xoá phiên khi khoá tài khoản (*"khoá mà để phiên cũ sống tiếp
là khoá trên giấy"*). Người ta đổi mật khẩu **chính vì** nghi có người khác đang vào được; giữ
phiên của người đó lại là phá đúng mục đích của thao tác.

Nhưng **giữ lại phiên đang gọi**: đăng xuất chính người vừa đổi mật khẩu là hình phạt cho hành vi
đúng, và họ sẽ tưởng thao tác thất bại.

Trả `so_phien_khac_da_thu_hoi` để giao diện nói ra **hệ quả**. Không có con số này thì người dùng
thấy điện thoại đòi đăng nhập lại và tưởng hệ thống lỗi.

### 3.4. Ô "nhập lại mật khẩu mới" là BẮT BUỘC

Hệ thống **không có hạ tầng gửi thư** (giới hạn đã ghi ở `REPORT_E52.md`) ⇒ **không có đường lấy
lại mật khẩu**. Gõ sai mật khẩu mới một lần là **mất tài khoản vĩnh viễn** — mất dữ liệu, không
phải bất tiện. Ô nhập lại là thứ duy nhất chặn được, và nó so **ngay ở trình duyệt** để người dùng
biết trước khi bấm.

### 3.5. Mật khẩu mới trùng mật khẩu cũ bị từ chối

Cho qua thì người dùng tin mình đã xoay khoá trong khi khoá y nguyên — và lượt thu hồi phiên kèm
theo làm họ **tin tưởng sai chỗ**: tưởng đã đẩy kẻ kia ra, trong khi kẻ kia chỉ cần đăng nhập lại
bằng đúng mật khẩu cũ.

### 3.6. KHÔNG cho đổi email

Email là danh tính đăng nhập, và không có hạ tầng xác minh địa chỉ mới. Cho đổi mà không xác minh
là cho người ta tự gõ sai rồi mất hẳn đường vào. Màn hình **nói ra** điều này thay vì im lặng không
có ô — một ô thiếu không giải thích thì người dùng tưởng hỏng.

### 3.7. Đổi tên hiển thị KHÔNG đòi mật khẩu

Tên hiển thị đổi lại được trong một giây và không cho ai thêm quyền gì. Đòi mật khẩu cho một thao
tác vô hại là dạy người dùng gõ mật khẩu vào bất cứ ô nào hỏi ra — đó là huấn luyện cho lừa đảo,
không phải bảo mật.

### 3.8. Thêm trường lỗi MỚI cho giao diện, không đổi trường cũ

`doc()` trong `api.js` đặt `message` dạng `"400: câu của máy chủ"`, và `laLoiThieuKhoa()` dò
`startsWith('401')` trên chính chuỗi đó. Nhưng dán mã HTTP vào một ô nhập mật khẩu là bắt người
dùng đọc thứ dành cho lập trình viên. ⇒ thêm `loi.cauNguoiDoc`, để `message` nói đúng thứ nó vẫn
nói. Cùng nguyên tắc với `trang_thai_thuc` ở E55.

---

## 4. Changed Files

| Tệp | Sửa gì |
|---|---|
| `app/services/tai_khoan.py` | `_ten_hien_chuan`, `doi_ten_hien`, `doi_mat_khau` |
| `app/schemas/common.py` | `SuaTaiKhoanRequest` (+ validator cặp mật khẩu), `SuaTaiKhoanResponse` |
| `app/api/v1/xac_thuc_routes.py` | `PATCH /auth/me` |
| `frontend/src/api.js` | `suaTaiKhoanCuaToi`, `loi.cauNguoiDoc` |
| `frontend/src/components/auth/ManTaiKhoan.jsx` | `OTenHien`, `OMatKhau` |
| `frontend/src/App.jsx` | `onDoiNguoiDung` — đổi tên xong header cập nhật ngay |
| `frontend/src/styles.css` | `.khoi-sua`, `.hang-nut` |

**Không** có migration: E56 không thêm bảng hay cột nào.

---

## 5. New API

`PATCH /api/v1/auth/me` — gửi cái nào đổi cái đó; đổi mật khẩu phải gửi **cả hai** trường.

```json
{"ten_hien": "…", "mat_khau_cu": "…", "mat_khau_moi": "…"}
→ {"nguoi_dung": {…}, "da_doi_mat_khau": true, "so_phien_khac_da_thu_hoi": 2}
```

| Mã | Khi nào |
|---|---|
| `400` | sai mật khẩu hiện tại · mật khẩu mới < 8 ký tự · mật khẩu mới trùng cũ |
| `422` | gửi nửa cặp mật khẩu · body rỗng (không có gì để đổi) |
| `401` | chưa đăng nhập |

---

## 6. Tests

**Backend 18 bài** (`test_e56_tu_sua_tai_khoan.py`), **frontend 9 bài** (thêm vào
`man-tai-khoan.test.jsx`, tổng tệp đó 18).

| Bài canh | Canh cái gì |
|---|---|
| `test_doi_mat_khau_THU_HOI_cac_phien_khac` | Nặng nhất — đổi mật khẩu mà để phiên cũ sống là đổi TRÊN GIẤY |
| `test_sai_mat_khau_cu_thi_KHONG_doi_duoc` | Phiên bị mượn không chiếm được tài khoản |
| `test_bi_tu_choi_thi_ten_hien_cung_KHONG_bi_luu` | Một lượt bị từ chối không lưu nửa vời |
| `test_doi_mat_khau_GIU_LAI_phien_dang_dung` | Không đăng xuất chính người vừa đổi |
| `test_dang_nhap_lai_bang_mat_khau_MOI` | Vòng tròn đủ: "đã ghi vào CSDL" ≠ "dùng được thật" |
| `test_KHONG_tu_phong_quyen_quan_tri_duoc` | Lỗ leo thang quyền |
| `KHONG_gui_duoc_khi_hai_o_mat_khau_lech_nhau` | Giao diện: khẳng định **không có lượt PATCH nào**, không chỉ khẳng định có chữ đỏ |

Bài test dùng **tài khoản riêng cho từng bài**, không dùng `nguoi_a` của conftest: bảng `nguoi_dung`
KHÔNG bị TRUNCATE giữa các test, nên một bài đổi mật khẩu của tài khoản dùng chung sẽ rò trạng thái
sang mọi bài xếp sau — biểu hiện là "xanh khi chạy riêng, đỏ khi chạy chung", thứ khó truy nhất.

### Đối chứng âm đã chạy — 4 lượt, mỗi lượt đỏ đúng bài

| Phá gì | Bài đỏ |
|---|---|
| Bỏ phép kiểm mật khẩu cũ | `test_sai_mat_khau_cu…` + `test_bi_tu_choi_thi_ten_hien…` |
| Không thu hồi phiên nào | `test_doi_mat_khau_THU_HOI_cac_phien_khac` |
| Thu hồi CẢ phiên đang dùng | `…THU_HOI_cac_phien_khac` + `…GIU_LAI_phien_dang_dung` |
| Tắt phép so hai ô mật khẩu (giao diện) | `KHONG_gui_duoc_khi_hai_o_mat_khau_lech_nhau` |

CSS vào bundle thật: 27,27 → **27,52 kB**.

---

## 7. Live Verification — bấm tay trên production (27-09, Chrome thật)

Dấu hiệu bản mới đã lên: `PATCH /api/v1/auth/me` trả **401** (đường tồn tại, đòi đăng nhập) thay vì
**405** của bản cũ. Bundle web công khai chứa đủ các chuỗi mới (`Nhập lại mật khẩu mới`,
`cauNguoiDoc`…), CSS `index-4S5XyKkB.css` khớp đúng bản build cục bộ.

| Đo cái gì | Kết quả |
|---|---|
| Đổi tên hiển thị | Lưu được; **header cập nhật NGAY**, không phải tải lại trang |
| Sai mật khẩu hiện tại | Hiện đúng câu *"Mật khẩu hiện tại không đúng."*, **không** kèm `400:`, **không** báo thành công giả, form vẫn mở để thử lại |
| Cảnh báo thiết bị khác | Hiện **trước** khi bấm, không phải báo sau |
| Nút khoá lúc chưa đủ ô | `disabled` ngay khi mở form |

### Chứng minh phần thu hồi phiên bằng một phiên THẬT thứ hai

Tạo phiên B qua `POST /auth/login` (curl), xác nhận nó sống (`/auth/me` → 200), rồi đổi mật khẩu
**trên trình duyệt**:

| Bước | Kết quả |
|---|---|
| Giao diện báo | *"Đã đăng xuất **1** thiết bị khác."* — đúng số phiên thật |
| Phiên B sau khi đổi | **401** — thu hồi ở máy chủ, không phải chỉ trên màn |
| Đăng nhập bằng mật khẩu CŨ | **401** |
| Đăng nhập bằng mật khẩu MỚI | **200** |
| Phiên **đang dùng** (trình duyệt) | **200** — vẫn đăng nhập, không bị đẩy ra màn đăng nhập |

## 8. Lỗi console tìm được khi bấm tay — ĐÃ VÁ

Chrome ghi `[DOM] Password field is not contained in a form` (3 lần). Hậu quả thật **không phải** cái
cảnh báo: **trình quản lý mật khẩu không nhận ra đây là lượt đổi mật khẩu**, nên nó giữ nguyên mật
khẩu CŨ đã lưu — lần đăng nhập sau nó tự điền sai và người dùng tưởng việc đổi đã thất bại.

Vá: bọc cả hai khối sửa trong `<form onSubmit>` thật, nút thành `type="submit"`. Được thêm phím
Enter để gửi — thứ mọi người đều thử.

Thêm 3 bài canh, gồm một bài **cấu trúc** (`closest('form')` phải khác `null`) và một bài canh
`onSubmit` phải tôn trọng đúng điều kiện khoá của nút — bọc form mà quên chỗ đó là mở lại đúng lỗ
vừa bịt: gõ lệch hai ô rồi bấm Enter là mất tài khoản. Đối chứng âm: bỏ `<form>` ⇒ **4 bài đỏ**.

### Và bước HAI của cùng vấn đề đó — cũng đã vá

Bọc `<form>` xong, kiểm lại console thì cảnh báo cũ hết nhưng Chrome nêu ngay cảnh báo **kế tiếp**:

> *Password forms should have (optionally hidden) username fields for accessibility*

Đây **không** phải chuyện khác: không có ô tên đăng nhập thì trình quản lý mật khẩu biết đây là form
mật khẩu nhưng **không biết của tài khoản nào**, nên vẫn không cập nhật đúng bản ghi — đúng cái hại
mà việc bọc `<form>` định vá. Bản vá của tôi **chưa đủ**, và chỉ biết vì đọc lại console sau khi vá
thay vì tin là đã xong.

Vá: thêm `<input autocomplete="username" readOnly tabIndex={-1} aria-hidden class="an-di">` mang
email. Ẩn khỏi mắt và khỏi bàn phím, nhưng **vẫn trong DOM** — trình quản lý mật khẩu đọc DOM, không
đọc cây a11y. Thêm 1 bài canh.

Bộ giao diện: **435 bài xanh**.

---

## 9. Remaining Limits
* Không đổi được email (§3.6) và không có đường lấy lại mật khẩu quên. Cả hai chờ hạ tầng gửi thư.
* Không có danh sách "các thiết bị đang đăng nhập" để thu hồi từng cái. Đổi mật khẩu là cách duy
  nhất để đẩy hết. Đủ cho nhu cầu hiện tại, nhưng thô.
* Không giới hạn số lần thử mật khẩu cũ ở đường này. Kẻ đã có phiên hợp lệ có thể dò mật khẩu cũ
  không giới hạn — nhưng scrypt ~83ms/lượt làm việc dò rất chậm, và kẻ đó **đã** vào được tài khoản
  nên mật khẩu không phải thứ chặn thêm được gì. Ghi lại để không ai tưởng đã có chống dò.
