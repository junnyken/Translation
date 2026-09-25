# MINI-SPEC: Hạn mức sử dụng, vòng đời tệp, tải kết quả an toàn

**Ngày:** 2026-09-25 · **Trạng thái:** luật đã chốt đủ, **chưa code dòng nào**
**Nguồn:** gộp từ `DAC_TA_TRANG_CHINH_VA_HAN_MUC.md` + bản đề xuất của chủ dự án, **đã đối chiếu
với mã thật** và loại phần không áp dụng cho dự án này.

> Tài liệu này **thay thế** bản đề xuất gốc. Mọi giá trị dưới đây đã chốt — không còn câu treo.

---

# 0. ĐÃ CHỐT — không cần hỏi lại

| | Chốt | Ghi chú |
|---|---|---|
| Hạn mức khách lạ | **6 trang/ngày** | 25-09 |
| Hạn mức có tài khoản | **10 trang/ngày** | |
| Đơn vị đếm | **TRANG** | không phải chapter/tệp/lần bấm |
| Nhận diện khách lạ | **cookie + IP** | trần IP phải CAO HƠN trần cookie |
| Mốc reset | **00:00 giờ Việt Nam** (UTC+7) | |
| Giữ kết quả | **30 phút kể từ lúc XONG** | |
| Ảnh gốc | **xoá cùng** | 25-09 |
| Trần **mỗi tệp** | **25 MB** — *giữ nguyên giá trị đã có* | |
| Trần **cả gói mỗi lượt** | **50 MB** — *hạ từ 500 MB* | 25-09 |

## Vì sao 50 MB lại là "hạ xuống"

Mã đã có sẵn `max_upload_mb = 25` (mỗi tệp) và `archive_max_total_mb = 500` (cả gói). Con số
50 MB chủ dự án đưa được hiểu là **tổng mỗi lượt tải lên**, vì đó mới là thứ bảo vệ worker: để
khách lạ ném 500 MB vào một worker 4096 MB đúng là rủi ro cần chặn.

⇒ Giữ mỗi tệp 25 MB (đã chặt hơn 50), hạ cả gói **500 → 50 MB**.

---

# 1. Những thứ ĐÃ CÓ — dùng lại, đừng dựng lại

| Đã có | Ở đâu |
|---|---|
| Đăng ký · đăng nhập · `/me` · đăng xuất | `POST /api/v1/auth/dang-ky`, `/login`, `GET /me`, `POST /logout` |
| Bảng người dùng | `email` · `ten_hien` · `mat_khau_bam` · `dang_hoat_dong` · `la_quan_tri` |
| Tải lên gói ZIP/CBZ/PDF + đếm trang | `POST /api/v1/projects/{id}/pages/archive` |
| Trần kích thước | `max_upload_mb` · `archive_max_pages` (200) · `archive_max_total_mb` |
| Hệ màu | `frontend/src/styles/tokens.css` |
| Dọn job mồ côi khi worker khởi động | `workers/hoi_phuc.py` |

---

# 2. ĐỐI CHIẾU VỚI MÃ THẬT — bốn giả định sai, một chặn

Quét mã 25-09. Bản đề xuất gốc vấp cả bốn chỗ này.

| Giả định | Sự thật |
|---|---|
| "Dùng scheduler **hiện có**" | ❌ **KHÔNG có lịch chạy định kỳ nào.** Quét `celery_app.py`, `deploy-start.sh`, compose — trống |
| "`429` theo quy ước sẵn có" | ❌ `429` **chưa dùng ở đâu**. Là mẫu MỚI |
| "Đừng thêm Pillow vào API container" | ❌ **Pillow đã có sẵn** và bước căn chữ đang dùng |
| "Khoá chống hai worker cùng dọn" | ⚠️ Chỉ có **MỘT** worker (`--pool=solo`). Không sai, nhưng là lo xa — **bỏ khỏi phạm vi** |

## 2.1. CHẶN: phải thêm mới lịch chạy định kỳ

Phần dọn 30 phút cần một cơ chế chạy nền theo chu kỳ, mà **không có cơ chế nào để tái dùng**.
Phải thêm mới (Celery beat hoặc tương đương). Đây là đầu việc thật.

Nó sẽ chạy **chung tiến trình worker** đang bó 4096 MB, mà worker **đã bị hệ điều hành giết 3
lần**. ⇒ Phép dọn phải **nhẹ** và **không chạy trùng lúc bước xoá chữ đang ở đỉnh** (~2295 MB).

## 2.2. Kho lưu trữ có BA nền

`storage_backend` ∈ {`local`, `postgres`, `supabase`}, mỗi nền một hàm `delete` riêng.
**Production đang dùng nền nào thì CHƯA BIẾT** — cổng quản trị chỉ trả tên biến, không trả giá
trị. **Phải tra trước khi viết phần dọn dẹp.**

---

# 3. Hạn mức

## 3.1. Sổ cái, không dùng bộ đếm đơn

```text
ĐÃ KIỂM TỆP → GIỮ CHỖ → ĐANG CHẠY → ĐÃ TIÊU
                            └→ ĐÃ HOÀN (lỗi hệ thống)
```

**Bộ đếm đơn sai khi có request song song, chạy lại, hoặc worker chết** — mà worker ở đây đã chết
3 lần thật. Sổ cái cho phép truy vết từng lần trừ/hoàn và làm mọi thao tác **idempotent**.

- **GIỮ CHỖ** sau khi tệp qua kiểm, **trước khi** xếp việc — chặn hai request song song ăn cùng lượt.
- **ĐÃ TIÊU** khi trang đạt trạng thái thành công cuối.
- **ĐÃ HOÀN** khi lỗi do hệ thống: worker chết, hết lượt thử lại, job mồ côi bị dọn.
- **Chạy lại cùng một khoá không được trừ/hoàn hai lần.**
- Chapter nhiều trang thành công một phần ⇒ tiêu lượt trang xong, **hoàn lượt trang hỏng**.

## 3.2. Bốn thứ thiếu thì tính năng tự gây hại

**(a) Chặn ở tầng MÁY CHỦ, không chỉ ẩn nút.** Dự án có tiền lệ: bộ test đầy đủ vẫn xanh khi cổng
chặn chỉ nằm ở giao diện. Gọi thẳng API phải bị từ chối.

**(b) HOÀN LƯỢT khi hệ thống hỏng.** Chỗ dễ quên nhất.

**(c) Nói rõ CÒN BAO NHIÊU và BAO GIỜ CÓ LẠI.** Hiện `0/6` mà không nói "có lại lúc 0h" thì người
ta tưởng hỏng.

**(d) Kiểm tệp TRƯỚC khi giữ chỗ.** Tệp bị từ chối vì kích thước/định dạng **không được mất lượt**.

## 3.3. Ba điểm an toàn

- **Không tin `X-Forwarded-For` thô từ client.** Chỉ tin khi proxy đã cấu hình đúng.
- Cookie khách đặt `Secure` · `HttpOnly` · `SameSite`; **không chứa số lượt** (client sửa được).
- **Băm IP**, không lưu thô.

## 3.4. Bẫy múi giờ — ĐÃ CÓ TIỀN LỆ

Container chạy **UTC**, máy làm việc **UTC+7**. Bài test gom theo "giờ trong ngày" sẽ **xanh ở máy
mà ĐỎ trên server**. Mốc reset phải ép `Asia/Ho_Chi_Minh` tường minh, và **chính bài test cũng
phải ép `TZ`**.

## 3.5. Mã lỗi

Chưa có quy ước — dùng **`429`** cho vượt hạn mức. Thân lỗi phải nêu: cần bao nhiêu trang, còn bao
nhiêu, reset lúc nào. **Không** trả thông báo mơ hồ kiểu "đã có lỗi".

## 3.6. Biến môi trường — không viết số cứng

`HAN_MUC_KHACH_LA=6` · `HAN_MUC_CO_TAI_KHOAN=10` · `HAN_MUC_IP_KHACH_LA` (20–30) ·
`MUI_GIO_HAN_MUC=Asia/Ho_Chi_Minh` · `ARCHIVE_MAX_TOTAL_MB=50`

---

# 4. Vòng đời tệp 30 phút

## 4.1. Luật

- `het_han_luc = thoi_diem_xong + 30 phút`, **timestamp tuyệt đối**.
- **Đếm từ lúc XONG, không phải lúc tải lên.** Chapter 24 trang mất 30–40 phút — đếm từ lúc tải
  lên là **tệp hết hạn trước khi dịch xong**.
- `THOI_GIAN_GIU_KET_QUA_PHUT=30`, đổi được.

## 4.2. Xoá gì

Theo quyết định 25-09: **xoá cả ảnh gốc** — ảnh gốc, ảnh đã xoá chữ, bản dịch, tệp xuất, ảnh
xem trước, và **dòng trong CSDL** theo thứ tự không tạo khoá ngoại mồ côi.

**Hệ quả phải nói thẳng với người dùng:** sau 30 phút toàn bộ chapter **biến mất**, không chạy lại
và không sửa lại được. Muốn làm lại phải tải lên từ đầu và **tốn thêm hạn mức**. Điều này vô hiệu
hoá các tính năng sửa tay (sửa chữ OCR đọc sai, chỉnh khung vùng) sau mốc đó.

## 4.3. TUYỆT ĐỐI không xoá thứ đang chạy dở

Bỏ qua mọi trang còn job ở trạng thái đang chờ/đang chạy/đang thử lại. Xoá tệp giữa lúc worker
đang đọc là cách chắc chắn tạo ra lỗi không tái hiện được.

## 4.4. Thứ tự an toàn

```text
nhận phần việc → xác nhận không còn chạy → xoá tệp → xoá/đánh dấu dòng CSDL
```

Xoá tệp hỏng ⇒ **giữ dòng lại để thử lần sau**. Tệp đã mất mà dòng còn ⇒ lượt sau phải xử lý
được, không nổ.

## 4.5. Phải ghi lại và đếm được

Log có cấu trúc: `đã xoá N · bỏ qua vì đang chạy M · thất bại K`. **`K > 0` kéo dài là dấu hiệu
cần người xem.** Không có phần này thì đĩa đầy dần trong im lặng — đúng thứ luật này sinh ra để
tránh.

⚠️ **Không log nội dung truyện / chữ OCR / bản dịch.**

## 4.6. Hết hạn KHÔNG hoàn lượt

Hạn mức tiêu vào lúc **xử lý**, không phải lúc tải về. Khác hẳn §3.2(b) — ở đó là **hệ thống
hỏng** nên phải hoàn. Phải nói rõ trên giao diện.

**Hai luật không đá nhau:** xử lý hỏng ⇒ trang chưa xong ⇒ đồng hồ chưa chạy ⇒ ảnh gốc vẫn còn ⇒
lượt hoàn lại dùng được. **Chỉ đúng khi đếm từ lúc XONG** (§4.1).

---

# 5. Tự động tải về

Luật 30 phút **bắt buộc** phải đi cùng khả năng tải về đáng tin. Làm luật 30 phút mà không có
phần này là bày ra một cái bẫy.

- Tự tải là **nỗ lực tốt nhất** — trình duyệt thường chặn tải không do người bấm.
- **LUÔN** hiện nút "Tải ngay" hoạt động được, kể cả khi đã bật tự tải.
- Bị chặn ⇒ **nói ra**: *"Trình duyệt đã chặn tải tự động. Hãy bấm Tải ngay."*
- **Không** coi việc kích hoạt tải là bằng chứng tệp đã ghi xuống máy. Chỉ được nói "đã yêu cầu tải".
- Nhiều trang ⇒ **một tệp nén**, không kích hoạt 24 lượt tải rời.
- Lưu lựa chọn: khách lạ ở trình duyệt; có tài khoản thì theo tài khoản.

---

# 6. Giao diện

## Trước khi tải lên — nói bằng chữ + icon, không chỉ bằng màu

1. "Còn X/6 trang hôm nay" · "Làm mới lúc 00:00 giờ Việt Nam"
2. **"Kết quả chỉ giữ 30 phút sau khi xong, sau đó xoá hẳn cả ảnh gốc"**
3. Đăng ký thì được 10 trang
4. Định dạng hỗ trợ · trần **25 MB mỗi tệp, 50 MB mỗi lượt**
5. **~30 giây một trang** — để người ta không tưởng máy treo

## Khi chạy

Tiến độ phải thấy được. Thiếu nó người dùng tưởng hỏng và bấm lại — **tốn thêm hạn mức oan**.

## Khi xong

Nút "Tải ngay" rõ ràng · đồng hồ đếm ngược theo `het_han_luc` **do máy chủ trả** (client chỉ hiển
thị) · hết hạn thì nói rõ đã bị dọn và **không hoàn lượt**.

---

# 7. Điều kiện nghiệm thu

Phải **chứng minh được**, không phải tự nhận:

1. Hết hạn mức ⇒ **gọi thẳng API bị từ chối** (không chỉ ẩn nút).
2. Xoá cookie ⇒ vẫn bị trần IP chặn.
3. Tệp vượt 50 MB ⇒ từ chối **trước khi** giữ chỗ; **lượt không đổi**.
4. Xử lý hỏng ⇒ **lượt hoàn đúng một lần** (gọi hoàn lặp không hoàn hai lần).
5. Chapter hỏng một phần ⇒ tiêu trang xong, hoàn trang hỏng.
6. Quá 30 phút ⇒ **cả tệp lẫn dòng CSDL biến mất**.
7. Job đang chạy qua mốc ⇒ **không bị xoá**.
8. Bài test mốc reset **ép `TZ` tường minh**.
9. Tự tải bị chặn ⇒ có thông báo + nút tải tay vẫn dùng được.
10. Toàn bộ test hiện có vẫn xanh.

---

# 8. Đã LOẠI khỏi phạm vi

Ghi lại để không ai thêm vào rồi tưởng là thiếu:

| Loại | Vì sao |
|---|---|
| Khoá chống nhiều worker cùng dọn | Chỉ có MỘT worker `--pool=solo` |
| Ràng buộc "không thêm Pillow" | Pillow đã có và đang dùng — ràng buộc này không thuộc dự án này |
| Thanh toán / gói cước / theo dõi tiếp thị | Ngoài mục tiêu |
| Chính sách người dùng tự huỷ | **Chưa có luật.** Gặp thì DỪNG và hỏi, đừng tự đặt |

---

# 9. Stop Rules

1. **Tra `storage_backend` thật của production TRƯỚC** khi viết phần dọn dẹp (§2.2).
2. Phát hiện model/route/trạng thái thật khác giả định ⇒ **DỪNG**, báo cáo, đừng đoán rồi code.
3. Gặp việc cần luật mới (tự huỷ, tin proxy, băm riêng tư) ⇒ **DỪNG và hỏi**.
4. Không deploy phần dọn dẹp khi chưa có đường lùi và chưa chạy thử ở môi trường giống production
   — **xoá nhầm là không lấy lại được**.
5. Làm xong ghi `docs/REPORT_HAN_MUC_VONG_DOI.md` rồi **DỪNG**, không tự mở phần trang chính.
