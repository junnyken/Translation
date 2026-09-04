# REPORT B1 — Auth slice B: tài khoản thật, chapter có chủ

## Summary

Trước slice này, hệ thống có **một khoá chung** (slice A): ai cầm khoá là đọc, sửa, xoá được
chapter của mọi người. Đó đủ để chặn người lạ trên internet, nhưng **không** phải phân quyền —
và mục tiêu người dùng đặt ra là "muốn cho người khác dùng".

Slice B thay cổng đó bằng **tài khoản riêng + chapter có chủ**:

- Bảng `nguoi_dung` (mật khẩu băm scrypt) và `phien` (mã phiên băm SHA-256, thu hồi được).
- `project.chu_so_huu_id` — chapter có chủ; chapter tạo trước slice B để `NULL` (chưa có chủ).
- Cổng ở tầng router đổi từ khoá chung sang **phiên đăng nhập**. Khoá chung còn đúng một việc:
  gác `/auth/register`, để người lạ không tự tạo tài khoản.
- 61/65 endpoint được kiểm quyền sở hữu; 4 endpoint còn lại không đụng tài nguyên của ai.
- Giao diện: màn đăng nhập chắn trước ứng dụng, đường tạo tài khoản đầu tiên, đăng xuất.

**Đây là bước mạnh lên, không phải đổi ngang.** Từ nay chỉ cầm khoá chung thì **không đọc/ghi
được gì** — có test riêng chứng minh điều đó (`test_CHI_CO_KHOA_CHUNG_thi_KHONG_doc_duoc_du_lieu`).

## Audit Before Build

Đo trên chính mã nguồn và bảng route, không đoán:

| Đo cái gì | Kết quả |
|---|---|
| Tổng endpoint `/api/v1` | 65 |
| Tới chapter qua `project_id` | 16 |
| Tới chapter **gián tiếp** (`page_id` 19, id khác 13, `region_id` 7, `job_id` 4) | 43 |
| Không có id | 4 |
| Endpoint đi qua hàm "lấy hoặc 404" dùng chung | 37 |
| Endpoint tự tra tài nguyên bằng id riêng | 28 |

Hai phát hiện định hình cả thiết kế:

1. **43/65 endpoint tới chapter bằng đường gián tiếp.** Rải kiểm quyền thủ công ở từng chỗ là
   cách chắc chắn để sót. Nên dựng **một bộ giải quyền chung** đi ngược chuỗi
   `region → page → project` (`app/core/quyen.py`, bảng `_CHA`).
2. **`_get_project_or_404` được định nghĩa HAI lần** (dòng 162 và 988), nội dung giống hệt.
   Python lấy định nghĩa sau, nên cả 18 lời gọi chạy bản thứ hai. Gắn kiểm quyền nhầm bản thì
   kiểm sẽ **không chạy chút nào** mà không có dấu hiệu gì. Đã gộp còn một.

Môi trường: **không có** thư viện băm mật khẩu nào (`bcrypt`/`argon2`/`passlib` đều không cài),
cũng không có `jwt`.

## Design Choice

### Băm mật khẩu: `hashlib.scrypt` (thư viện chuẩn)

Không thêm phụ thuộc, đúng tiền lệ dự án (E17b dùng `urllib` thay vì kéo `httpx` về). scrypt là
KDF memory-hard đúng nghĩa. Tham số `n=2^14, r=8, p=1` (mức tối thiểu OWASP) — **đo được 83ms
mỗi lần băm**: đủ chậm để chống dò, đủ nhanh để đăng nhập.

Tham số được ghi kèm trong chuỗi băm (`scrypt$n$r$p$muối$băm`) nên tăng độ khó về sau không khoá
người dùng cũ ra ngoài. `maxmem` đặt tường minh: mặc định OpenSSL là 32MB và **báo lỗi** chứ
không tự nới.

### Mã phiên đục trong CSDL, KHÔNG dùng JWT

JWT không thu hồi được: bấm "đăng xuất" mà token vẫn sống tới lúc hết hạn là hành vi sai. Mã
phiên tra trong CSDL thì xoá một dòng là mất hiệu lực tức thì. Giá phải trả là một truy vấn mỗi
request — mà đằng nào mỗi request cũng đã mở một phiên CSDL.

**Mã phiên băm SHA-256, mật khẩu băm scrypt — không mâu thuẫn.** scrypt cố tình chậm để chống dò
thứ *người nghĩ ra* (ít entropy). Mã phiên là 256 bit ngẫu nhiên từ máy: không có gì để đoán.
Dùng scrypt ở đó chỉ tốn 83ms mỗi request mà không mua thêm chút an toàn nào. Vẫn phải băm trước
khi lưu — kẻ đọc được CSDL sẽ mạo danh được ngay mà không cần biết mật khẩu.

### Không phải chủ ⇒ **404**, không phải 403

403 nói "có tồn tại, nhưng bạn không được vào" — tức là xác nhận id đó có thật, và người dò sẽ
quét id để lập danh sách chapter tồn tại. 404 không phân biệt "không có" với "không phải của
bạn".

### Chapter chưa có chủ để NULL, không gán bừa

Chapter tạo trước slice B không có chủ, và lúc migration chạy thì **chưa có tài khoản nào** để
gán. Gán bừa là đoán mò; giấu đi là làm mất việc của người dùng. Nên: `NULL` = "chưa có chủ",
mọi tài khoản đăng nhập đều thấy, và **nhận về được** (`POST /projects/{id}/claim`). Nhận rồi thì
người khác mất quyền ngay, và không ai cướp lại được.

Từ slice B trở đi **không còn đường nào sinh ra chapter vô chủ** — `create_project` luôn đặt chủ.

### Đã đăng nhập thì KHÔNG cần khoá chung

Nếu bắt gửi cả hai, thì muốn cho ai dùng cũng phải phát cho họ khoá chung — mà cầm khoá chung là
tạo được tài khoản cho người khác. Vậy thì phân quyền chẳng còn ý nghĩa.

## Changed Files

| Tệp | Việc |
|---|---|
| `app/core/mat_khau.py` | **mới** — băm/kiểm mật khẩu bằng scrypt |
| `app/core/phien.py` | **mới** — sinh/băm/kiểm hạn mã phiên |
| `app/core/quyen.py` | **mới** — dependency đăng nhập + bộ giải quyền `_CHA` |
| `app/services/tai_khoan.py` | **mới** — đăng ký/đăng nhập/đăng xuất (thuần CSDL) |
| `app/api/v1/xac_thuc_routes.py` | **mới** — router `/auth/*`, router DUY NHẤT không đòi phiên |
| `app/models/__init__.py` | `NguoiDung`, `Phien`, `Project.chu_so_huu_id` |
| `app/schemas/common.py` | schema tài khoản; `ProjectRead.chu_so_huu_id` |
| `app/api/v1/routes.py` | gộp hàm trùng; 3 hàm điểm nghẽn nhận `nguoi`; 65 handler nhận `nguoi`; `GET /projects`; `POST /projects/{id}/claim` |
| `app/main.py` | cổng router đổi sang `nguoi_dung_hien_tai`; CORS thêm `Authorization` |
| `alembic/versions/0012_b1_*.py` | **mới** — 2 bảng + 1 cột |
| `frontend/src/api.js` | mã phiên + `Authorization`; 8 hàm auth mới |
| `frontend/src/components/auth/ManDangNhap.jsx` | **mới** — màn đăng nhập/đăng ký |
| `frontend/src/App.jsx` | chắn đăng nhập; thanh tài khoản; bỏ `HopNhapKhoa` (đã chết) |
| `frontend/src/styles.css` | lớp `man-dang-nhap`, `tai-khoan`, `nut-chu` |
| `tests/conftest.py` | fixture `client` (A) / `client_b` / `client_chua_dang_nhap` |
| `tests/test_bao_ve_integration.py` | viết lại theo hợp đồng mới của slice A |
| `tests/test_quyen_cheo_tai_khoan.py` | **mới** — dò chéo tài khoản toàn bảng route |

## New API / DB / State

**Bảng mới**

- `nguoi_dung` — `email` (duy nhất, lưu đã hạ chữ thường), `ten_hien`, `mat_khau_bam`,
  `dang_hoat_dong`, `la_quan_tri`.
- `phien` — `nguoi_dung_id`, `ma_bam` (duy nhất, có index), `het_han`, `dung_lan_cuoi`.
  `ON DELETE CASCADE` theo người dùng.

**Cột mới**: `project.chu_so_huu_id` → `nguoi_dung.id`, **NULL được**, `ON DELETE SET NULL`.
SET NULL có chủ đích: xoá tài khoản **không được** kéo theo chapter — đó là làm mất việc của
người khác.

**Endpoint mới**

| Method | Đường dẫn | Việc |
|---|---|---|
| POST | `/auth/register` | Tạo tài khoản (đòi khoá chung). Người đầu tiên thành quản trị |
| POST | `/auth/login` | Trả `ma_phien` — chuỗi thô chỉ xuất hiện đúng ở đây |
| POST | `/auth/logout` | Thu hồi phiên. **Luôn 204**, kể cả mã sai |
| GET | `/auth/me` | Phiên trong máy còn dùng được không |
| GET | `/auth/co-tai-khoan-chua` | Chỉ `true`/`false` — không trả số lượng hay email |
| GET | `/projects` | Chapter của tôi + chapter chưa có chủ |
| POST | `/projects/{id}/claim` | Nhận chapter chưa có chủ |

`GET /projects` **trước đây không tồn tại** — giao diện tự nhớ id trong máy. Không có nó thì
người dùng mới đăng nhập trên máy khác sẽ không thấy gì cả.

## Tests

**Backend** — bộ `test_quyen_cheo_tai_khoan.py` là bằng chứng chính. Nó **tự sinh** phép thử từ
`app.openapi()`, nên endpoint thêm về sau cũng bị dò mà không ai phải nhớ cập nhật gì.

Cách chống "xanh giả": mỗi đường dẫn được gọi **hai lần** — bằng A (chủ thật) và bằng B — rồi
phân loại. Nếu A cũng không vào được thì phép dò **rỗng nghĩa** và test **đỏ**, chứ không cho nó
lẫn vào phần xanh.

Kết quả cuối: **63 endpoint chứng minh được, 0 rỗng nghĩa, 0 lỗ hổng.**

Bốn lần siết liên tiếp mới tới đó, mỗi lần đóng một kiểu rỗng nghĩa:

| Lượt | Chứng minh | Rỗng nghĩa | Đã sửa gì |
|---|---|---|---|
| 1 | 44 | 19 | — |
| 2 | 58 | 5 | Sinh thân request hợp khuôn từ OpenAPI (trước đó gửi `{}` ⇒ 422 trước khi chạm kiểm quyền) |
| 3 | 62 | 1 | Tạo hiện vật thật (ảnh clean, preview, file xuất) + gửi multipart cho upload |
| 4 | **63** | **0** | Hiểu `const` (`Literal` của Pydantic ra `const` chứ không phải `enum`) |

Ba test hành vi kèm theo: chapter vô chủ ai cũng thấy; nhận về rồi người khác mất quyền và không
cướp lại được; chapter tạo mới luôn có chủ.

**Frontend** — 18 test mới (màn đăng nhập + bảng nhận chapter), tổng **283 test xanh**, build sạch.

## Live Verification

Đo trên `translation-api.cmc-1.vibenode.matbao.ai` sau khi deploy, 2026-09-04.

### Điều quan trọng nhất: khoá chung không còn mở được dữ liệu

| Gửi gì | Kết quả |
|---|---|
| Chỉ `X-API-Key` (khoá chung, đúng) | **401** |
| Không gửi gì | **401** |
| `Authorization: Bearer <mã phiên>` | 200 |

Trước slice B, dòng đầu là "làm được mọi thứ".

### Cách ly giữa hai tài khoản, trên dữ liệu thật

| Thao tác | A (chủ) | B (người lạ) |
|---|---|---|
| `GET /projects/{id}` | 200 | **404** |
| `POST /projects/{id}/glossary` — **cùng một thân request** | **201** | **404** |
| `POST /projects/{id}/consistency-scans` | 202 | **404** |

Dòng giữa là bằng chứng chặt nhất: cùng thân request, khác nhau **chỉ ở người gửi**. Lượt thử
đầu tiên của tôi gửi sai khuôn nên **cả A lẫn B đều 422** — đúng kiểu phép dò rỗng nghĩa mà bộ
test được thiết kế để bắt; phải làm lại với thân đúng khuôn mới có kết luận.

### Dữ liệu cũ không mất

**25/25 chapter** có sẵn trên bản chạy thật hiện ra đầy đủ, gắn nhãn *chưa có chủ*.

### Nhận chapter, và đăng xuất

| Kiểm | Kết quả |
|---|---|
| B nhận một chapter vô chủ | 200 |
| A mở lại chapter đó | **404** |
| A "cướp lại" bằng `claim` | **404** |
| Đăng xuất B | 204 |
| Dùng lại mã phiên vừa đăng xuất | **401** — hiệu lực tức thì, không đợi hết hạn |

### Trên trình duyệt thật (Chromium)

| Bước | Kết quả |
|---|---|
| Mở trang chưa đăng nhập | Màn đăng nhập; **không lộ** ô tìm chapter |
| Sai mật khẩu | Hiện *"Email hoặc mật khẩu không đúng."* |
| Đúng mật khẩu | Vào ứng dụng, thanh tài khoản hiện tên |
| **Tải lại trang** | Vẫn ở trong ứng dụng — không nháy màn đăng nhập |
| Mở chapter vô chủ | Hiện nhãn *"Chapter này chưa có chủ"* + nút nhận |
| Đăng xuất | Về màn đăng nhập |

Không có lỗi console ngoài đúng một 401 — chính là lượt đăng nhập sai ở bước 2.

## B1a — hai lỗ hổng vận hành lộ ra từ chính lượt kiểm chứng

Kiểm chứng trên bản thật làm lộ hai chỗ B1 thiếu, và cả hai đều được phát hiện theo cách khó
chịu nhất: **tôi tự mắc phải chúng.**

### 1. `claim` là đường một chiều

Tài khoản thử B nhận nhầm một chapter **thật** của người dùng. Không có đường nào trả lại: `claim`
có mà `release` không, và `_get_project_or_404` đã chặn mọi người khác từ trước. Cách duy nhất là
sửa tay trong CSDL — mà CSDL trên VibeHost không với tới được từ máy phát triển.

⇒ Thêm `POST /projects/{id}/release`: chủ nhả chapter về *chưa có chủ*.

### 2. Phát tài khoản ra được, không thu lại được

`la_quan_tri` có trong bảng từ B1 nhưng **chưa endpoint nào dùng tới**. Muốn khoá hay gỡ một
người phải sửa tay trong CSDL. "Cho người khác dùng" mà không thu hồi được thì mới xong một nửa.

⇒ Thêm `GET/PATCH/DELETE /auth/users` cho quản trị. Hai điểm thiết kế đáng nói:

- **Khoá thì cắt luôn phiên đang mở.** Khoá mà để phiên cũ sống tiếp là khoá trên giấy: người đó
  vẫn thao tác bình thường tới khi phiên hết hạn — tối đa 14 ngày.
- **Xoá tài khoản KHÔNG xoá chapter của họ** (`ON DELETE SET NULL`) — chapter về *chưa có chủ*.
  Xoá kèm là xoá việc của người khác chỉ vì gỡ một tài khoản.

### 3. Phép dò tự phá dữ liệu của chính nó

Thêm `/release` xong, phép dò chéo **tụt từ 63 chứng minh được xuống 4**, kèm 18 "lỗ hổng". Không
phải lỗ hổng thật: phép dò gọi `/release` dưới danh nghĩa A, nhả luôn chapter thành vô chủ, nên
mọi lượt kiểm sau đó B truy cập được là **đúng**.

Sửa bằng cách đặt lại chủ sở hữu sau **mỗi** lượt, nên phép dò miễn nhiễm với mọi endpoint đổi
quyền sở hữu trong tương lai. Kết quả: **64/64 chứng minh được, 0 rỗng nghĩa, 0 lỗ hổng.**

### 4. Test cấu trúc soi nông, báo đỏ nhầm

`test_moi_endpoint_v1_deu_doi_dang_nhap` chỉ nhìn **phụ thuộc trực tiếp**, nên báo ba endpoint
quản trị "không đòi đăng nhập" — trong khi lời gọi thật cho **401**, tức chúng được bảo vệ đúng
(chúng phụ thuộc `quan_tri_hien_tai`, mà cái đó mới phụ thuộc `nguoi_dung_hien_tai`).

Đã sửa thành đi **đệ quy** cả cây phụ thuộc, và thêm một test gọi **thật** bên cạnh: soi cấu trúc
trả lời được "có gắn cổng không", chỉ lời gọi thật mới trả lời được "cổng có chặn không".

## Remaining Limits

1. **Chưa có đổi mật khẩu và quên mật khẩu.** Quản trị phát mật khẩu cho người mới, và người đó
   **không đổi được**. Đây là hạn chế nặng nhất còn lại của slice B.
   *(Quản lý người dùng thì đã có ở B1a — xem mục trên.)*
2. **Chưa có chia sẻ chapter giữa các tài khoản.** Một chapter đúng một chủ. Muốn hai người cùng
   làm một chapter thì phải có bảng thành viên — chưa dựng.
3. **`phien` chỉ được dọn khi có ai gọi `don_phien_het_han`, mà hiện chưa ai gọi.** Không sai về
   tính đúng (hạn được kiểm lúc tra), nhưng bảng sẽ phình dần.
4. **Chưa giới hạn số lần đăng nhập sai.** scrypt 83ms/lần làm việc dò chậm đi đáng kể nhưng
   không phải là chặn. Cần thêm đếm và khoá tạm.
5. **Mã phiên nằm ở `localStorage`.** Chống được đọc trộm CSDL, không chống được XSS. Đổi sang
   cookie `HttpOnly` sẽ cần xử lý CSRF — chưa làm.
6. **Chưa đo trên bản chạy thật.** Mọi con số ở trên đến từ máy phát triển.

## Phát hiện ngoài phạm vi (chưa sửa)

Phép dò chéo làm lộ một lỗi có sẵn, **không** do slice B gây ra:

> `PATCH /glossary/{entry_id}` đổi thuật ngữ trùng với thuật ngữ đã có trong cùng chapter ⇒
> **500**, kèm nguyên câu SQL trong log. Đúng ra phải là **409**. Ràng buộc
> `uq_glossary_project_term` bị vi phạm mà không có ai bắt `IntegrityError`.

Ghi lại ở đây chứ chưa sửa: nó nằm ngoài phạm vi slice B, và sửa lẫn vào đây sẽ làm mờ ranh giới
"slice B đổi những gì".
