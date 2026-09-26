# REPORT E49 — Hạn mức sử dụng: sổ cái, cổng chặn, quyết toán, đường khách lạ

**Ngày:** 2026-09-25 · **Nguồn yêu cầu:** `MINI_SPEC_HAN_MUC_VONG_DOI.md` + `DAC_TA_TRANG_CHINH_VA_HAN_MUC.md`

---

## 1. Summary

Hạn mức theo **trang/ngày** đã chạy đầu-cuối ở tầng máy chủ: khách lạ 6, có tài khoản 10, reset
00:00 giờ Việt Nam. Bốn phần:

| Phần | Trạng thái |
|---|---|
| Sổ cái (giữ chỗ / tiêu / hoàn, idempotent, an toàn khi song song) | **Xong** |
| Cổng chặn ở ba đường tải lên, trả 429 | **Xong** |
| Quyết toán: chốt lượt khi trang xong, hoàn khi hệ thống hỏng | **Xong** |
| Đường tải lên cho khách lạ (không cần đăng nhập) | **Xong** cho chế độ chỉ-chữ |

**Chưa làm:** vòng đời tệp 30 phút, tự động tải về, trang chủ. Xem §8.

---

## 2. Audit Before Build

Quét mã trước khi viết. Năm giả định phổ biến, **cả năm đều sai hoặc thiếu**:

| Giả định | Sự thật đo được |
|---|---|
| "Dùng bộ đếm `da_dung` trên bảng người dùng" | Sai ở 4 tình huống có thật — xem §3.1 |
| "`get_settings()` có `lru_cache` nên chụp lúc import là an toàn" | **Sai.** Cache xoá được, và `conftest` xoá nó. Xem §7 |
| "Cổng đăng nhập gắn ở từng endpoint" | Gắn ở **tầng router** (`main.py:140`), cố ý, cho 73 đường |
| "`chu_so_huu_id IS NULL` = chapter của khách lạ" | **Sai và nguy hiểm.** Nó đang nghĩa là "chapter cũ, mọi tài khoản đăng nhập đều dùng được" |
| "`429` đã có quy ước sẵn" | `429` chưa dùng ở đâu trong `api/v1/`. Là mẫu MỚI |

Điểm cuối là chỗ suýt tạo ra **rò rỉ dữ liệu hàng loạt** — xem §5.

---

## 3. Design Choice

### 3.1. Sổ cái, không phải bộ đếm

Một cột cộng dồn sai ở bốn tình huống, cả bốn đều có thật trong dự án này:

* **hai request song song** cùng đọc "còn 6" rồi cùng trừ ⇒ tiêu quá hạn mức;
* **HTTP thử lại** ⇒ trừ hai lần cho một lượt;
* **worker chết giữa chừng** ⇒ lượt đã trừ mà việc không chạy (worker **đã bị hệ điều hành giết
  3 lần**, không phải giả định);
* **mẻ thành công một phần** ⇒ không biết tiêu mấy trang, hoàn mấy trang.

Ba bảo đảm và cách giữ:

1. **Song song:** `pg_advisory_xact_lock` khoá **theo chủ thể** — hai request của cùng một người
   xếp hàng, người khác không bị ảnh hưởng. Khoá tự nhả khi giao dịch kết thúc, kể cả khi giao
   dịch đổ. *Không* dùng `SELECT ... FOR UPDATE`: người mới chưa có dòng nào để khoá.
2. **Idempotent:** `khoa_idempotency` **duy nhất** ở tầng CSDL. Thử lại thì tìm thấy dòng cũ và
   trả đúng kết quả cũ — không dựa vào "kiểm trước khi ghi", vì đó chính là thứ hỏng ở mục 1.
3. **Một phần:** hạ dòng giữ chỗ xuống phần thành công + ghi thêm dòng `da_hoan` cho phần còn
   lại. `da_hoan` **không** tính vào phần đã dùng nên phép cộng ra đúng.

**Đơn vị là MỘT DÒNG MỘT TRANG.** Nhờ vậy phần worker thành chuyện tầm thường: trang xong thì
`tieu`, trang hỏng hẳn thì `hoan` — không cần ai điều phối "cả mẻ xong chưa".

Vượt hạn mức ⇒ **từ chối nguyên mẻ**. Xử lý một phần âm thầm sẽ khiến người dùng nhận nửa
chapter mà không có cách nào biết thiếu trang nào.

### 3.2. Chỗ đặt giữ chỗ trên đường tải lên

**SAU** khi tệp qua kiểm (tệp hỏng/quá lớn không được mất lượt — §3.2(d) đặc tả) và **TRƯỚC** khi
ghi xuống kho (hết lượt thì không ghi tệp nào). Ném 429 ở đó ⇒ giao dịch huỷ ⇒ trang vừa flush
biến mất.

Gói nén có thêm một lớp: chặn sớm bằng phép **đọc** ngay sau khi mở gói (đừng dựng lại 24 ảnh PDF
rồi mới biết hết lượt), rồi giữ chỗ thật từng trang trong vòng lặp.

Nhân tiện vá một chỗ rò rỉ có sẵn: huỷ mẻ gói trước đây `rollback` gỡ dòng CSDL nhưng **để lại
tệp** — đĩa đầy dần trong im lặng. Nay `_huy_me_goi` dọn luôn tệp đã ghi.

### 3.3. Quyết toán đặt ở ĐÚNG MỘT điểm nghẽn

`workers/tasks.bao_ket_thuc_buoc` được gọi ở cuối **mọi** bước, cả thành công lẫn hỏng (17 chỗ).
Gắn vào đó nghĩa là thêm bước mới vào pipeline cũng không quên quyết toán.

Cách làm hỏng đã cố ý tránh: gắn vào từng chỗ đặt `page.status = ...`. Có **12** chỗ như vậy, và
sót một chỗ là người dùng mất lượt vĩnh viễn mà **không có triệu chứng nào** ngoài con số sai.

⚠️ Quyết toán chạy **trước** cổng `batch_enabled`: hạn mức áp cho cả trang tải lẻ — đúng đường
khách lạ dùng — mà trang lẻ không thuộc mẻ nào.

**Hoàn** chỉ khi hệ thống hỏng, đúng ba trường hợp §1.3(b) đặc tả nêu: worker chết (lượt dọn job
mồ côi), hết lượt thử lại của mẻ, bị chặn vì hết quota nhà cung cấp.

### 3.4. Nhận diện khách lạ: hai chốt

Cookie nhận ra trình duyệt, nhưng xoá cookie là một cú bấm — cookie một mình thì hạn mức chỉ là
gợi ý. IP là chốt thứ hai. Ngược lại IP một mình cũng không đủ: văn phòng, trường học, quán cà
phê dùng chung một IP, nên **trần IP phải cao hơn trần cookie** (25 so với 6), và request phải
lọt qua **cả hai**.

* **Băm HMAC-SHA256 có muối**, không lưu IP thô. Muối rỗng ⇒ WARNING: băm không muối thì cả
  không gian IPv4 (~4,3 tỉ) dựng bảng tra chỉ mất vài phút, tức băm gần như vô nghĩa.
* **Không tin `X-Forwarded-For` theo mặc định.** Header do client gửi; tin nó khi chưa có proxy
  ghi đè nghĩa là ai cũng tự đổi được "IP" của mình ⇒ chốt IP biến mất mà không ai thấy.
* Cookie chỉ chứa **mã ngẫu nhiên**, không chứa số lượt (client sửa được). `HttpOnly` ·
  `SameSite=Lax` · `Secure` (cấu hình được cho máy phát triển chạy HTTP thuần).

### 3.5. Mở đường cho khách: router riêng, danh sách cho phép tường minh

Cổng đăng nhập gắn ở tầng router chính là thứ giữ cho 73 đường còn lại **mặc định đóng**. Gỡ nó
ra rồi gắn lại từng chỗ thì sớm muộn cũng quên một đường — và đường bị quên sẽ là đường không ai
ngờ tới.

Nên thay vì gỡ, thêm `router_khach` mounted **không** có cổng đăng nhập, và chuyển đúng hai
endpoint sang đó. Mặc định vẫn đóng; mở là việc phải làm tường minh. Một bài test khoá chặt danh
sách — thêm đường vào đó mà không sửa bài test thì bộ test đỏ.

---

## 4. Changed Files

**Mới**

| Tệp | Vai |
|---|---|
| `app/services/so_cai_han_muc.py` | Lõi sổ cái: giữ chỗ / tiêu / hoàn, bản đồng bộ + bất đồng bộ |
| `app/services/han_muc.py` | Ngày hạn mức + mốc reset theo giờ Việt Nam |
| `app/services/quyet_toan_han_muc.py` | Khi nào chốt, khi nào hoàn |
| `app/core/danh_tinh_khach.py` | Nhận diện chủ thể: tài khoản, hoặc cookie + IP đã băm |
| `app/core/cong_han_muc.py` | Cổng chặn + thân lỗi 429 |
| `alembic/versions/0019_e49…`, `0020_e49b…`, `0021_e49c…` | Bảng sổ cái, cột `trang_id`, cột `project.chu_khach` |

**Sửa**

| Tệp | Sửa gì |
|---|---|
| `app/core/quyen.py` | `NguoiGoi` + viết lại `duoc_dung_project` (xem §5) |
| `app/api/v1/routes.py` | Cắm cổng vào 3 đường tải lên; `router_khach`; dọn tệp khi huỷ mẻ |
| `app/main.py` | Gắn `router_khach` không kèm cổng đăng nhập |
| `app/workers/tasks.py` | Quyết toán ở `bao_ket_thuc_buoc` |
| `app/workers/hoi_phuc.py` | Hoàn lượt khi dọn job mồ côi |
| `app/services/batch/orchestrator.py` | Hoàn lượt khi hết lượt thử lại / hết quota nhà cung cấp |
| `app/core/config.py` | 8 biến mới, không gõ số cứng ở đâu |
| `tests/conftest.py` | `so_cai_han_muc` vào danh sách TRUNCATE giữa các test |

---

## 5. New API / DB / State

### API

`429 Too Many Requests` — **mẫu mới**, chưa endpoint nào dùng trước đây.

```json
{"detail": {
  "loi": "vuot_han_muc", "can": 1, "con_lai": 0, "tran": 6,
  "co_tai_khoan": false, "chot": "khach_ip",
  "reset_luc": "2026-09-26T00:00:00+07:00", "reset_sau_giay": 12345
}}
```

Kèm header `Retry-After`, và `Set-Cookie` khi khách chưa có cookie. Trường `chot` cố ý có mặt:
`khach_ip` nghĩa là bị chặn vì **dùng chung địa chỉ mạng**, không phải vì chính người này dùng
nhiều — không nói ra thì người ở văn phòng không hiểu nổi vì sao mình bị chặn khi chưa dùng lượt
nào.

**Hai endpoint không còn đòi đăng nhập:** `POST /api/v1/doc-truyen/trang` và
`GET /api/v1/doc-truyen/trang/{page_id}`.

### DB

* `so_cai_han_muc` — mỗi dòng một khoản: `khoa_idempotency` (duy nhất), `loai_chu_the`,
  `chu_the`, `ngay_han_muc`, `so_trang`, `trang_thai`, `ly_do_hoan`, `trang_id`.
* `project.chu_khach` — mã cookie đã băm.

`trang_id` **cố ý không có khoá ngoại**: trang bị xoá sau 30 phút, còn sổ cái là dấu vết hạn mức
và phải sống lâu hơn trang. `CASCADE` sẽ xoá luôn bằng chứng đã tiêu lượt (⇒ cho lượt từ hư
không), `RESTRICT` thì chặn mất phép dọn.

### Đổi nghĩa một trạng thái CŨ — đọc kỹ

`chu_so_huu_id IS NULL` trước đây nghĩa là **"chapter cũ chưa có chủ, mọi tài khoản đăng nhập đều
dùng được"**. Chapter của khách lạ cũng có `chu_so_huu_id IS NULL`.

Không phân biệt hai thứ đó thì **mọi người đăng nhập đọc được truyện của mọi khách lạ**. Đây là
rò rỉ dữ liệu, không phải chuyện tiện lợi.

Luật mới ở `duoc_dung_project`, ba nhánh, **nhánh giữa là nhánh dễ quên nhất**:

1. Khách lạ chỉ thấy chapter mang đúng mã khách của mình;
2. **Người đăng nhập KHÔNG thấy chapter của khách** (`chu_khach IS NOT NULL` ⇒ từ chối);
3. Người đăng nhập thấy chapter của mình, và chapter cũ chưa có chủ (`cả hai cột NULL`).

Đối chứng âm đã chạy: gỡ nhánh 2 ra thì người đăng nhập nhận **200 OK** trên trang của khách.

---

## 6. Tests

| Tệp | Số bài | Canh cái gì |
|---|---|---|
| `test_e49_ngay_han_muc.py` | 10 | Ngày + mốc reset theo giờ VN, **ép `TZ=UTC`** trong chính bài test |
| `test_e49b_so_cai_han_muc.py` | 13 | Giữ chỗ / tiêu / hoàn, idempotent, **hai luồng THẬT** |
| `test_e49c_danh_tinh_khach.py` | 16 | Băm có muối, luật tin proxy, hai chốt |
| `test_e49d_cong_han_muc.py` | 12 | 429 qua HTTP thật, tệp hỏng không mất lượt, gói không ghi rác |
| `test_e49e_quyet_toan_han_muc.py` | 12 | Chốt khi xong, hoàn khi worker chết, không hoàn dòng đã tiêu |
| `test_e49f_khach_la_tai_len.py` | 13 | Khách tải lên được; **không ai đọc được của ai**; danh sách đường mở |

### Hai bài canh CŨ đã đỏ — và đó là chúng làm đúng việc

Mở hai endpoint cho khách lạ làm đỏ ngay hai bài canh có sẵn:

* `test_bao_ve_integration::test_moi_endpoint_v1_deu_doi_dang_nhap` — soi **cây phụ thuộc**, thấy
  hai đường không còn `nguoi_dung_hien_tai`;
* `test_quyen_cheo_tai_khoan::test_moi_endpoint_deu_doi_dang_nhap` — gọi **thật**, thấy trả `404`
  thay vì `401`.

Đây đúng là thứ hai bài đó sinh ra để làm: **không cho mở endpoint một cách im lặng.** Chúng được
sửa có chủ ý, và sửa theo hướng **giữ nguyên sức canh**:

* bài thứ nhất: thêm hai đường vào `MIEN_TRU_DANG_NHAP` kèm lý do. Danh sách này và
  `test_e49f::test_CHI_hai_duong_nay_mo_cho_khach` là **hai ổ khoá riêng** — mở thêm một đường
  phải sửa đủ cả hai chỗ;
* bài thứ hai: **không bỏ qua** endpoint đó, chỉ đổi mã mong đợi sang `404`. Bỏ qua thì nó thành
  điểm mù, mà thứ thật sự đáng sợ ở đây là `200` chứ không phải `404`.

**Bốn đối chứng âm đã chạy** (dựng lại lỗi ⇒ bài canh phải đỏ):

1. Bỏ khoá tư vấn ⇒ hai luồng cùng xin 4 trên trần 6 đều lọt.
2. Chụp `get_settings()` lúc import ⇒ cả bài canh cấu hình lẫn bài 429 đỏ.
3. Đẩy quyết toán xuống sau cổng `batch_enabled` ⇒ trang lẻ không được chốt.
4. Gỡ nhánh 2 của `duoc_dung_project` ⇒ người đăng nhập đọc được truyện của khách (200 OK).

---

## 7. Một lỗi tự gây ra — đáng đọc trước khi viết phần sau

`services/han_muc.py` chụp `settings = get_settings()` ở mức module. `get_settings` có
`@lru_cache`, **nhưng cache đó xoá được** và `tests/conftest.py` gọi `cache_clear()`. Ảnh chụp
trỏ mãi vào đối tượng `Settings` cũ.

Đo được: `han_muc_cho(True)` trả **10** trong khi cấu hình app đang là **2**. Cổng vẫn chạy, chỉ
là theo trần sai — và **không bài test nào đỏ**.

Hỏng kiểu này tệ hơn lỗi thường: lỗi thường làm test đỏ, còn cái này làm *bộ test mất khả năng
phát hiện lỗi thật*. Tôi loại bỏ giả thuyết này sớm vì thấy `@lru_cache` và kết luận "chắc chắn
cùng một đối tượng", rồi đi đoán ba chỗ khác trước khi chịu **in `id()` ra mà so**.

⇒ Knob **chính sách** (trần, cờ, ngưỡng) phải đọc `get_settings()` **trong thân hàm**. Chỉ chuỗi
kết nối mới được chụp lúc import.

---

## 8. Live Verification

**CHƯA CHẠY THẬT LẦN NÀO.** Không có bằng chứng từ bản đang chạy.

Toàn bộ §6 là bộ test trên máy (Postgres thật, HTTP thật qua ASGI, nhưng **không** phải bản đã
deploy). Không có lượt nào gọi Gemini thật — bộ test thay `urllib.request.urlopen` bằng hàm giả.

Lý do chưa deploy: workspace bị chặn ở tầng mạng khi gọi Vibe Host (403 cho mọi đường, kể cả
trang chủ không kèm xác thực). Cần chủ dự án gỡ chặn hoặc deploy tay.

**Phải kiểm sau khi deploy** — những thứ chỉ bản chạy thật mới trả lời được:

1. `request.client` có thật sự ra IP người dùng không, hay ra IP của Traefik. Nếu là IP proxy
   thì **mọi khách chung một chốt IP** ⇒ chặn oan hàng loạt. Đây là rủi ro số một.
2. Đặt `MUOI_BAM_KHACH` (chưa đặt ⇒ log WARNING mỗi lần khởi động).
3. Quyết định `TIN_HEADER_PROXY`. Bật **chỉ khi** chắc chắn Traefik ghi đè `X-Forwarded-For`.
4. `COOKIE_KHACH_SECURE=true` trên HTTPS (mặc định đã đúng).
5. Chạy thật một trang đầu-cuối để thấy `giu_cho -> da_tieu`.

---

## 9. Remaining Limits

**Thuộc phạm vi hạn mức, chưa làm:**

* **Trang hỏng hẳn ở đường tải lẻ không được hoàn.** Trang lẻ không có trạng thái "hỏng vĩnh
  viễn" — `detection_failed` vẫn chạy lại được. Lượt nằm ở `giu_cho` cho tới nửa đêm. Đây là
  lựa chọn bảo thủ (không cho lượt từ hư không), không phải bỏ sót.
* **Các endpoint `retry-*` không qua cổng hạn mức.** Chạy lại một trang là miễn phí. Hợp lý khi
  lỗi do hệ thống, nhưng là lỗ hổng nếu ai đó bấm chạy lại liên tục để đốt tài nguyên.
* **Khách lạ mới dùng được chế độ chỉ-chữ.** Gói ZIP/PDF và các đường ảnh vẫn đòi đăng nhập.
* Trần IP 25 là **số đoán**, chưa có dữ liệu hành vi thật để chỉnh.

**Ngoài phạm vi, vẫn còn nguyên:**

* Vòng đời tệp 30 phút (§2 đặc tả) — **cần thêm mới lịch chạy định kỳ**, dự án chưa có cơ chế
  nào để tái dùng.
* Tự động tải về (§3 đặc tả) — đi liền với luật 30 phút; làm luật mà không có phần này là bày ra
  một cái bẫy.
* Trang chủ (§4 đặc tả).
* `STORAGE_BACKEND` production là `local` | `postgres` | `supabase` — **vẫn chưa biết**, mà ba
  nền xoá khác nhau. Chặn phần dọn tệp.
