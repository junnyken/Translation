# REPORT E51 — Khách lạ nhận ảnh đã dịch, và gói nhiều trang thành một tệp

**Ngày:** 2026-09-26 · **Nguồn yêu cầu:** chủ dự án chốt 26-09 · `DAC_TA_TRANG_CHINH_VA_HAN_MUC.md` §2.9, §3.3, §4.1

---

## 1. Summary

Khách lạ gửi kèm `che_do=day_du` thì chapter chạy **hết** pipeline (xoá chữ gốc bằng LaMa + căn
chữ Việt vào bong bóng) ⇒ có **ảnh đã dịch** tải về được, và nhiều trang gói thành **một** tệp
`.cbz`/`.zip`.

Bề mặt cho khách lạ lên **7 đường**. An toàn không dựa vào cổng đăng nhập mà dựa vào `chu_khach`.

**Chưa làm:** phần giao diện tự động tải về (§3) và trang chủ (§4). Xem §7.

---

## 2. Audit Before Build — lỗ mà E49/E50 để lại

E49 mở đường tải lên cho khách, E50 làm luật 30 phút. Cả hai đứng trên một tiền đề mà **không ai
kiểm**: rằng khách có tệp để mất.

Đo bằng cách đọc mã (`tasks.py:564`): chapter của khách chạy `ChePipeline.chi_chu` — bỏ **hẳn**
bước xoá chữ và căn chữ, dừng ở `translated`, chỉ trả **toạ độ + chữ dịch** cho tiện ích Chrome
phủ lên ảnh gốc trên trang web.

⇒ Khách **không có tệp nào**. §3 đặc tả (tự động tải về) chẳng có gì để tải, và luật 30 phút của
E50 chỉ xoá ảnh gốc với mấy dòng chữ.

Đây là dạng lỗi "hai đầu không gặp nhau": mỗi phần đúng theo đặc tả của nó, nhưng nối lại thì
thiếu một khúc mà không đặc tả nào nói ra.

---

## 3. Design Choice

### 3.1. Tham số hoá chế độ, không tách endpoint mới

`POST /doc-truyen/trang` nhận thêm `che_do`. Mặc định **giữ nguyên** `chi_chu`: tiện ích E19 đang
chạy thật và không gửi trường này. Đổi mặc định là bắt nó chạy thêm hai bước đắt nhất — hai bước
duy nhất cần mô hình LaMa 1,5 GB — cho một thứ nó không dùng tới (nó phủ chữ lên ảnh gốc, không
cần ảnh đã xoá chữ).

Hai chế độ sinh **hai chapter riêng** cho cùng một người ("Đọc nhanh (tiện ích) — ja" và "Dịch
nhanh — ja"). Để chung một chapter thì trang phủ-chữ và trang đã-căn-chữ lẫn vào nhau, mà hai loại
có đích khác nhau nên cổng xuất không biết trang nào xuất được.

### 3.2. Cờ `xong` KHÔNG được là một danh sách trạng thái cứng

Đây là lỗi **sẽ phát sinh ngay** khi mở chế độ đầy đủ, và nó sai im lặng:

| Chế độ | `translated` nghĩa là |
|---|---|
| `chi_chu` | **ĐÍCH** — không bao giờ tới `typeset_done`, chờ nó là chờ mãi |
| `day_du` | **GIỮA ĐƯỜNG** — chưa căn chữ, chưa có ảnh nào |

Danh sách cứng `(translated, typeset_done, ready_for_export)` làm chế độ đầy đủ **báo xong sớm một
bước**, và client đi lấy một ảnh chưa tồn tại. Nay cờ suy từ `che_do_pipeline` của chapter.

`anh_da_dich` để `null` khi chưa có, **không** trả một đường dẫn sẽ 404: client không phân biệt
được "chưa xong" với "hỏng" nếu cả hai đều là 404.

### 3.3. Hai lý do 404 phải nói KHÁC nhau

`GET .../anh` trả 404 ở hai tình huống, và chúng cần hành động khác nhau:

* **chưa căn chữ xong** ⇒ hỏi lại sau;
* **chapter chạy `chi_chu`** ⇒ hỏi lại bao nhiêu lần cũng vô ích, phải gửi lại với `day_du`.

Nói gộp thành một câu là để người dùng chờ vô ích. Mỗi lý do có thân lỗi riêng, và có bài test
khoá từng câu.

### 3.4. Gói tải về: dùng lại đường xuất có sẵn

§3.3 đặc tả: tải 24 tệp rời là 24 lần bị trình duyệt hỏi, gần như chắc chắn bị chặn. Một tệp nén
là một lần.

Đường xuất của M8 đã làm đúng việc đó (worker gộp, `cbz`/`zip`), nên mở nó cho khách thay vì dựng
lại. Dựng ZIP ngay trong request là việc nặng trong HTTP — điều dự án cấm — và 24 trang × ~1 MB
nằm trong bộ nhớ tiến trình API.

### 3.5. Bề mặt 7 đường — vì sao an toàn

An toàn **không** dựa vào cổng đăng nhập mà dựa vào `bao_dam_quyen`, nay nhận cả `NguoiGoi`:
`ExportJob` có mặt trong bảng `_CHA` của `core/quyen.py` nên nó lần được về chapter, và chapter của
khách mang `chu_khach` riêng ⇒ hỏi của người khác là 404.

Danh sách bị khoá ở **ba** nơi. Mở thêm một đường phải sửa đủ cả ba — cố ý làm cho khó.

---

## 4. Changed Files

| Tệp | Sửa gì |
|---|---|
| `app/api/v1/routes.py` | `che_do` + `_ten_chapter_nhanh` + cờ `xong` theo chế độ + `GET .../anh`; chuyển 4 endpoint sang `router_khach` |
| `app/schemas/common.py` | `TrangDocTruyen.che_do`, `.anh_da_dich` |
| `tests/test_e49f…`, `test_bao_ve_integration`, `test_quyen_cheo_tai_khoan` | Ba ổ khoá danh sách đường mở |

Không có migration. Không đổi bảng nào.

---

## 5. New API

Chi tiết ở `API.md` §E51. Tóm lại:

* `POST /doc-truyen/trang` — thêm `che_do` (`chi_chu` mặc định | `day_du`);
* `GET /doc-truyen/trang/{page_id}` — thêm `che_do`, `anh_da_dich`; **`xong` đổi nghĩa** theo chế
  độ (không phá client cũ: chế độ `chi_chu` giữ đúng hành vi trước đây);
* `GET /doc-truyen/trang/{page_id}/anh` → `image/png` (mới, mở cho khách);
* `POST /projects/{id}/export`, `GET /export-jobs/{id}`, `GET /export-jobs/{id}/download` — mở cho
  khách, không đổi hợp đồng.

---

## 6. Tests

15 bài mới (`test_e51_khach_lay_ket_qua.py`). Ba bài canh nặng nhất:

| Bài | Canh cái gì |
|---|---|
| `test_che_do_day_du_KHONG_bao_xong_o_translated` | Cờ `xong` phải theo chế độ |
| `test_MAC_DINH_van_la_chi_chu` | Tiện ích E19 không bị đổi hành vi |
| `test_khach_KHONG_xuat_duoc_chapter_cua_nguoi_khac` | Lỗ IDOR ở đường gộp chapter |

**Đối chứng âm đã chạy:** dựng lại danh sách trạng thái cứng ⇒ `test_che_do_day_du_KHONG_bao_xong…`
đỏ (`assert True is False`).

### Một ĐIỂM MÙ của bộ dò quyền tự sinh — phải biết trước khi mở endpoint POST cho khách

`test_quyen_cheo_tai_khoan::test_moi_endpoint_deu_doi_dang_nhap` gửi `json={}` cho mọi đường. Với
endpoint POST có thân bắt buộc, FastAPI kiểm thân **trước** khi vào hàm ⇒ trả `422` và **không bao
giờ tới phép kiểm quyền**.

Trước E51 điều đó không lộ ra, vì cổng đăng nhập ở tầng router chạy trước cả phép kiểm thân. Mở
endpoint cho khách là mất lớp đó, và `POST /projects/{id}/export` thành điểm mù.

⇒ Phần chứng minh thật nằm ở `test_e51::test_khach_KHONG_xuat_duoc_chapter_cua_nguoi_khac`, chỗ
gửi thân **hợp lệ**. Ai mở thêm endpoint POST cho khách phải làm đúng như vậy, và bài test
`test_quyen_cheo` ghi rõ mã `422` kèm lý do thay vì bỏ qua đường đó.

---

## 7. Remaining Limits

**Chưa làm, và là phần CHẶN việc bật E50:**

* **Tự động tải về (§3) — phần giao diện.** Backend đã có đủ đường; phần còn lại là trình duyệt:
  nỗ lực tốt nhất, **luôn** kèm nút tải thủ công, và **nói ra khi bị chặn** (§3.2). Đây là việc
  frontend — theo quy ước của tổ chức thì dựng bằng `agy`/`/mb-frontend`, không gõ bằng Opus.
* **Trang chủ (§4).** Cũng là frontend.
* **Lưu lựa chọn tự-tải-về theo tài khoản (§3.4).** Chưa có cột nào; khách lạ thì lưu ở trình
  duyệt nên không cần backend.

**Chưa chạy thật lần nào.** Riêng E51 có một rủi ro mới cần đo trên bản chạy thật:

1. **Chế độ `day_du` cho khách nghĩa là lưu lượng ẩn danh kích hoạt LaMa.** Đo ở E45: đỉnh RSS
   bước xoá chữ ~2239 MB trên trần 3950 MB. Worker chạy `--pool=solo` nên **một việc một lúc** ⇒
   rủi ro OOM **không** tăng, nhưng **hàng đợi dài ra**. Hạn mức (6 trang/cookie, 25/IP mỗi ngày)
   là thứ giữ cho nó có trần.
2. Mỗi trang tốn thêm ~6–17s so với `chi_chu` (đo 05/09).
3. Chưa đo lần nào: một trang đi hết chế độ `day_du` từ đầu đến cuối **qua đường của khách lạ**.
