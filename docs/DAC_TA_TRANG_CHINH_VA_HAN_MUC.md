# Đặc tả — Trang chính, tài khoản, hạn mức, và vòng đời tệp

**Ngày:** 2026-09-25 · **Viết cho:** người/trợ lý sẽ xây phần này.
**Trạng thái:** chưa xây dòng nào. Luật đã chốt, các bẫy đã ghi.

> **Đọc `docs/BAN_GIAO_TRANG_THAI.md` trước.** Tài liệu đó mô tả sản phẩm, kiến trúc, và các
> hướng đã đóng. Tài liệu này chỉ nói phần **sắp xây**.

---

# 0. Những thứ ĐÃ CÓ — dùng lại, đừng dựng lại

Đây là phần dễ lãng phí nhất nếu không kiểm trước.

| Đã có | Ở đâu |
|---|---|
| **Đăng ký tài khoản** | `POST /api/v1/auth/dang-ky` |
| **Đăng nhập** (trả `ma_phien` + hạn) | `POST /api/v1/auth/login` |
| **Lấy thông tin mình** | `GET /api/v1/auth/me` |
| **Đăng xuất** | `POST /api/v1/auth/logout` — luôn trả 204, kể cả mã sai |
| Bảng người dùng | `email` · `ten_hien` · `mat_khau_bam` · `dang_hoat_dong` · `la_quan_tri` |
| Hệ màu / design token | `frontend/src/styles/tokens.css` |
| Tải lên gói ZIP/CBZ/PDF | `POST /api/v1/projects/{id}/pages/archive` |

⇒ **Không cần xây lại xác thực.** Việc còn thiếu là **hạn mức**, **vòng đời tệp**, và **trang
chính**.

---

# 1. Hạn mức sử dụng

## 1.1. Luật đã chốt

| | Khách chưa đăng ký | Có tài khoản |
|---|---|---|
| Hạn mức | **6 trang/ngày** | **10 trang/ngày** |

- **Đơn vị: TRANG**, không phải chapter. Chi phí thật tính theo trang.
- **Nhận diện khách lạ: cookie + IP.** Cookie nhận ra trình duyệt; IP là chốt chặn thứ hai.
- **Reset: 00:00 giờ Việt Nam (UTC+7).**

## 1.2. Trần theo IP phải CAO HƠN trần theo cookie

Văn phòng, trường học, quán cà phê dùng chung một IP. Đặt trần IP bằng trần cookie sẽ **chặn oan
hàng loạt người dùng thật**. Gợi ý: cookie 6 · IP 20–30.

## 1.3. Bốn thứ THIẾU thì tính năng tự gây hại

**(a) Chặn ở tầng MÁY CHỦ, không chỉ ẩn nút.**
Dự án có bài học đúng chỗ này: bộ test đầy đủ vẫn xanh khi cổng chặn chỉ nằm ở giao diện. Ẩn nút
mà API vẫn nhận thì ai mở công cụ nhà phát triển cũng vượt được.

**(b) HOÀN LƯỢT khi xử lý hỏng.**
Trừ hạn mức lúc *nhận* trang, rồi trang đó hỏng giữa chừng ⇒ người dùng mất lượt vì lỗi của hệ
thống. **Đây là chỗ dễ quên nhất.** Worker của dự án đã bị hệ điều hành giết 3 lần — hỏng giữa
chừng là chuyện có thật, không phải giả định.

**(c) Nói rõ CÒN BAO NHIÊU và BAO GIỜ CÓ LẠI.**
Hiện `0/6` mà không nói "có lại lúc 0h" thì người ta tưởng hỏng.

**(d) Chặn trần KÍCH THƯỚC TỆP trước khi tính lượt.**
Không có thì một tệp rất lớn vừa đốt băng thông vừa có thể làm chết worker.

## 1.4. Bẫy múi giờ — ĐÃ CÓ TIỀN LỆ TRONG DỰ ÁN NÀY

**Container chạy giờ UTC. Máy làm việc là UTC+7.**

Bài test gom theo "giờ trong ngày" sẽ **xanh ở máy mà ĐỎ trên server**. Mốc reset phải ép múi giờ
tường minh, và **chính bài test cũng phải ép `TZ`** chứ không dựa vào giờ máy.

## 1.5. ĐÃ CHỐT — khách lạ 6 trang/ngày

Chủ dự án chốt (25-09): nới từ 3 lên **5–6**. Lấy **6** làm số khởi điểm vì truyện tranh thường
đọc theo cặp trang, 6 là 3 cặp trọn vẹn; và đầu rộng tay hơn thì chi phí chênh lệch không đáng kể.

Lý do nới: một trang mất ~30 giây trọn chuỗi, nên 3 trang là chưa đầy 2 phút — khách lạ có thể rời
đi trước khi kịp thấy công cụ làm được gì. Chi phí thật chỉ **~0,3 xu Mỹ cho 6 trang**.

⇒ **Vẫn đừng viết số cứng vào mã.** `HAN_MUC_KHACH_LA` (6) · `HAN_MUC_CO_TAI_KHOAN` (10).
Còn phải tinh chỉnh theo hành vi thật, mà đổi biến môi trường thì không cần deploy lại mã.

---

# 2. Vòng đời tệp — tự xoá sau 30 phút

## 2.1. Luật

Truyện đã dịch xong **chỉ giữ 30 phút**, sau đó tự xoá.

## 2.2. Tính giờ theo THỜI LƯỢNG TRÔI QUA, không theo giờ đồng hồ

Lưu mốc `het_han_luc = thoi_diem_xong + 30 phút` rồi so với "bây giờ". **Không** gom theo giờ
trong ngày — làm vậy là rơi vào đúng bẫy §1.4.

## 2.3. Đếm từ lúc XONG, không phải lúc tải lên

Một chapter 24 trang mất 30–40 phút để chạy. Đếm từ lúc tải lên thì **tệp hết hạn trước khi dịch
xong** — người dùng chờ nửa tiếng rồi nhận được con số 0.

## 2.4. TUYỆT ĐỐI không xoá thứ đang chạy dở

Phép dọn phải bỏ qua mọi trang còn job đang chạy. Xoá tệp giữa lúc worker đang đọc là cách chắc
chắn tạo ra lỗi không tái hiện được.

## 2.5. Xoá cả TỆP lẫn DÒNG trong cơ sở dữ liệu

Xoá tệp mà để lại dòng ⇒ giao diện hiện chapter có thật nhưng bấm vào thì hỏng. Xoá dòng mà để
lại tệp ⇒ **đĩa đầy dần trong im lặng**, không ai thấy cho tới khi hỏng.

## 2.6. Xoá hỏng thì phải THỬ LẠI và GHI LẠI

Nếu lượt dọn thất bại mà không ai biết, đĩa đầy dần. Phải ghi log đếm được: *đã xoá N, thất bại
M*. `M > 0` kéo dài là dấu hiệu cần người xem.

## 2.7. Phải BÁO TRƯỚC, không âm thầm

Người dùng cần biết luật này **trước khi bắt đầu**, không phải sau khi mất tệp. Hiện rõ trên trang
chính và trên màn kết quả, kèm **đồng hồ đếm ngược**.

## 2.8. Hết hạn KHÔNG hoàn lượt

Hạn mức tiêu vào lúc **xử lý**, không phải lúc tải về. Tệp hết hạn vì người dùng không tải kịp thì
lượt vẫn đã dùng. Khác hẳn §1.3(b) — ở đó là **hệ thống hỏng**, nên phải hoàn.

Phải nói rõ luật này trên giao diện, vì nó dễ gây bức xúc nếu người dùng chỉ phát hiện sau khi mất.

## 2.9. ĐÃ CHỐT — xoá luôn cả ảnh gốc

Chủ dự án chốt (25-09): **xoá cả ảnh gốc người dùng tải lên**, không giữ lại.

### Hệ quả phải nói rõ với người dùng

Sau 30 phút, **toàn bộ chapter biến mất** — ảnh gốc, ảnh đã xoá chữ, bản dịch, tệp xuất. Người
dùng **không chạy lại được** và **không sửa lại được**. Muốn làm lại thì phải tải lên từ đầu và
**tốn thêm hạn mức**.

Điều này vô hiệu hoá các tính năng sửa tay sau 30 phút: sửa chữ OCR đọc sai, chỉnh khung vùng,
chạy lại từng bước. Trong 30 phút thì vẫn dùng bình thường.

⇒ Câu cảnh báo trên giao diện phải nói đúng mức đó, **không** nói mơ hồ kiểu "tệp sẽ được dọn".

### Điều này KHÔNG làm hỏng luật hoàn lượt

Xử lý hỏng giữa chừng ⇒ trang **chưa xong** ⇒ đồng hồ 30 phút **chưa bắt đầu** ⇒ ảnh gốc **vẫn
còn**. Nên lượt được hoàn ở §1.3(b) vẫn dùng lại được. Hai luật không đá nhau — nhưng **chỉ đúng
khi đồng hồ đếm từ lúc XONG** như §2.3 đã chốt. Đổi sang đếm từ lúc tải lên là phá luôn cả điều
này.

---

# 3. Tự động tải về

## 3.1. Vì sao nó THIẾT YẾU chứ không phải tiện ích

Vì có luật 30 phút. Người dùng đóng tab rồi quên là **mất hẳn**. Hai tính năng này phải đi cùng
nhau; làm luật 30 phút mà không có tự tải về là bày ra một cái bẫy.

## 3.2. Trình duyệt sẽ CHẶN tải tự động

Tải về **không do người bấm** thường bị trình duyệt chặn. Hệ quả thiết kế:

- Đây là **nỗ lực tốt nhất**, không phải bảo đảm.
- **Luôn** hiện nút tải thủ công bên cạnh, kể cả khi đã bật tự tải.
- Bị chặn thì **nói ra**, đừng im lặng coi như xong.

## 3.3. Nhiều trang thì gói thành một tệp

Tải 24 tệp rời là 24 lần bị hỏi, gần như chắc chắn bị chặn. Một tệp nén là một lần.

## 3.4. Lưu lựa chọn này ở đâu

Khách lạ: lưu trong trình duyệt. Có tài khoản: lưu theo tài khoản để đổi máy vẫn còn.

---

# 4. Trang chính

## 4.1. Nguyên tắc

**Thả tệp là chạy. Không bắt khai báo gì trước.** Đăng ký là thứ người dùng chọn khi muốn nhiều
hơn, không phải cổng chặn ở cửa.

⚠️ **Thiết kế riêng.** Không sao chép giao diện của sản phẩm cạnh tranh — vừa là vấn đề bản quyền,
vừa vì điều khoản của họ cấm dùng cho mục đích cạnh tranh.

## 4.2. Cần nói rõ ngay trên trang chính

Người dùng phải biết **trước khi bắt đầu**:

1. Còn bao nhiêu lượt hôm nay, và bao giờ có lại.
2. **Tệp chỉ giữ 30 phút.**
3. Đăng ký thì được bao nhiêu.
4. Hỗ trợ ngôn ngữ nào, định dạng nào, trần kích thước bao nhiêu.
5. Một trang mất bao lâu — **~30 giây**, để người ta không tưởng máy treo.

## 4.3. Trạng thái phải thấy được

Chuỗi mất hàng chục giây tới hàng chục phút. Thiếu chỉ báo tiến độ thì người dùng tưởng hỏng và
bấm lại — tốn thêm hạn mức oan.

## 4.4. Màn tài khoản

Hiện đúng những gì có thật: email, tên hiển thị, hạn mức đã dùng / còn lại, mốc reset. **Không**
bịa thêm hạng thành viên hay số liệu chưa có thật.

---

# 5. Điều kiện nghiệm thu

Làm xong phải chứng minh được, không phải tự nhận:

1. Khách lạ dùng hết hạn mức ⇒ **API từ chối**, không chỉ ẩn nút. Kiểm bằng cách gọi thẳng API.
2. Xoá cookie ⇒ vẫn bị IP chặn.
3. Xử lý hỏng giữa chừng ⇒ **lượt được hoàn**.
4. Tệp quá 30 phút ⇒ **cả tệp lẫn dòng trong CSDL đều biến mất**.
5. Trang đang chạy dở ⇒ **không bị xoá**.
6. Bài test mốc reset **ép `TZ` tường minh**, không dựa giờ máy.
7. Tự tải về bị chặn ⇒ có thông báo + nút tải thủ công vẫn dùng được.

---

# 6. Nguyên tắc của dự án — giữ khi xây tiếp

1. **Evidence-first.** Chưa chạy → `NULL`. Hỏng → nêu đúng lý do. Không điền giá trị mặc định giả.
2. **Hỏng thì báo, không lặng lẽ lùi về đường cũ.**
3. **Kiểm trên bản đã build**, không chỉ trên mã nguồn.
4. **Phép quét cũng phải tự kiểm** — quét thiếu một dạng viết là bỏ sót im lặng.
5. Màu **không bao giờ** là nguồn thông tin duy nhất — luôn kèm nhãn chữ + icon.
6. **Kết quả âm cũng là kết quả.**

---

# 7. Đã chốt — không còn câu nào treo

| Câu | Chốt (25-09) |
|---|---|
| Ảnh gốc có xoá cùng sau 30 phút? | **Có, xoá luôn** — §2.9 |
| Hạn mức khách lạ | **6 trang/ngày** — §1.5 |

Đủ điều kiện bắt tay xây.
