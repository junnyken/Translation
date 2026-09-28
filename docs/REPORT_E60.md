# REPORT E60 — Chữ vỡ từng ký tự, và khung đỏ lọt vào tệp người đọc

**Ngày:** 2026-09-28 · **Nguồn:** chủ dự án chạy một **trang manga thật** rồi gửi ảnh kết quả

---

## 1. Summary

Hai lỗi nhìn thấy trên đúng một trang. Lỗi thứ hai nghiêm trọng hơn vẻ ngoài của nó: nó **tự che mắt
chính phép đo** dùng để phát hiện nó.

---

## 2. Lỗi 1 — khung đỏ nằm giữa truyện

`PagePreviewRenderer` vẽ khung đỏ quanh vùng **tràn khung** (`mark_overflow`, mặc định `True`). Đó là
dấu cho người **rà soát** trên ảnh xem thử.

`_run_export` — đường sinh tệp người đọc tải về — dựng đúng renderer đó mà **không truyền
`mark_overflow=False`**, nên nhận mặc định `True`. Tham số đã có sẵn từ đầu; **không ai từng truyền
nó** (`grep` toàn repo: chỉ 3 lần xuất hiện, tất cả trong `preview.py`).

Docstring của `export/chapter.py` nói lý do dùng chung renderer là *"hai đường vẽ khác nhau là mầm
mống lệch giữa ảnh xem thử và ảnh giao cho người đọc"* — đúng, nhưng dùng chung cũng kéo **dấu chẩn
đoán** vào sản phẩm.

**Vá:** `_run_export` truyền `mark_overflow=False`. Thông tin không mất: số vùng tràn vẫn được đếm
vào `job.overflow_warning_count`, và ảnh xem thử vẫn vẽ khung đỏ đầy đủ.

---

## 3. Lỗi 2 — chữ vỡ từng ký tự, mà hệ thống báo là "VỪA KHUNG"

Triệu chứng trên trang thật: `VÒNG QUA` → `VỌN / G QUA`, `TRẮNG` → `TRẢ / NG`.

### 3.1. Cơ chế

`wrap_to_width` cắt token theo **ký tự** khi token rộng hơn khung. Chú thích gốc nói nhánh đó dành cho
*"URL, tên chiêu thức"* — token dài bất thường.

Nhưng bong bóng **dọc hẹp** kiểu Nhật làm `max_width` rất nhỏ, nên **từ tiếng Việt bình thường** cũng
rơi vào nhánh đó. Nhánh dự phòng trở thành đường đi **chính**.

### 3.2. Và đây là phần tệ nhất — lỗi tự che mắt phép đo

Cắt theo ký tự làm bề rộng **luôn vừa**. Vòng dò cỡ chữ của `fit()` kiểm `w <= rect.width and
h <= rect.height`; vế bề rộng **luôn đúng**, nên nó **không bao giờ biết** khung quá hẹp. Nó chỉ thấy
chiều cao sai, bèn thu nhỏ chữ, rồi trả **`FIT_OK`**.

Đo lại trên đúng hình dạng đó (bong bóng `64×420`, câu `VÒNG QUA ĐÂY ĐI`):

```
TRƯỚC   cỡ chữ 38   VÒ / N / G / Q / UA / ĐÂ / Y / ĐI     fit_status = fit_ok
SAU     cỡ chữ 18   VÒNG / QUA / ĐÂY / ĐI                 fit_status = fit_ok
```

⇒ Phần lớn chữ hỏng trên trang của chủ dự án **còn không được gắn khung đỏ** — hệ thống coi là thành
công. Khung đỏ chỉ xuất hiện ở chỗ băm ra rồi **vẫn** quá cao.

### 3.3. Vá — cắt giữa từ là lựa chọn CUỐI, không phải đường đi thường

`wrap_bao_cat_tu()` trả thêm cờ **đã phải cắt giữa từ**. Vòng dò cỡ chữ coi cờ đó là **chưa vừa** và
tiếp tục thu nhỏ. Chỉ khi tới cỡ nhỏ nhất mà vẫn phải cắt thì mới chấp nhận cắt — và lúc đó gắn cảnh
báo tràn, tức nói thật.

Với chữ Việt, cắt giữa từ là **hỏng nội dung**, không phải "hơi xấu": từ tiếng Việt ngắn và có dấu,
cắt ra là mất nghĩa. Người đọc thà đọc chữ nhỏ còn hơn đọc `VỌN G`.

`wrap_to_width` giữ nguyên chữ ký cũ (trả chuỗi) — nhiều nơi đang gọi nó.

---

## 4. Tests

12 bài (`test_e60_khong_cat_giua_tu.py`).

| Bài canh | Canh cái gì |
|---|---|
| `test_BONG_BONG_DOC_HEP_khong_con_vo_tung_ky_tu` | Tái hiện đúng hình dạng đã gây lỗi |
| `test_khung_hep_thi_THU_NHO_chu_chu_khong_cat_tu` | Hệ quả: hẹp hơn ⇒ chữ nhỏ hơn, không phải băm chữ |
| `test_khung_rong_KHONG_bi_thu_nho_oan` | **Đối chứng ngược** — bản vá không được làm mọi trang xấu đi |
| `test_mot_tu_dai_khong_khoang_trang_van_cat_duoc` | Nhánh gốc (URL) vẫn sống |
| `test_khung_qua_hep_cho_CA_CO_NHO_NHAT…` | Hẹp tới mức không vẽ đúng được thì **vẫn hiện chữ** + báo tràn |
| `test_duong_XUAT_TEP_khong_ve_khung_do_con_XEM_THU_thi_co` | Soi CẢ HAI hàm, kỳ vọng ngược nhau |

**Đối chứng âm:** bỏ điều kiện `not cat_tu` ⇒ **3 bài đỏ**; bỏ `mark_overflow=False` ⇒ **1 bài đỏ**.

**Bài canh cấu trúc bắt lỗi của tôi lúc viết:** tôi vá đúng chỗ (`_run_export`) nhưng bài canh đọc
nhầm `run_export_job` (hàm task bao ngoài), nên nó đỏ dù mã đã đúng. Sửa bài thành soi cả hai hàm —
và cặp kỳ vọng ngược nhau đó mạnh hơn bản đầu: nó chặn luôn cái sai ngược lại (tắt nhầm ở xem thử).

Toàn bộ **1930 bài backend xanh** — không bài cũ nào vỡ, dù đây là thay đổi vào lõi căn chữ.

---

## 5. Remaining Limits

* **Chưa chạy lại đúng trang của chủ dự án.** Ảnh gửi là KẾT QUẢ, không phải ảnh gốc; tôi không có
  trang nguồn để dựng lại. Số đo ở §3.2 lấy từ bong bóng dựng đúng hình dạng đó, không phải từ chính
  trang đó.
* **Chữ sẽ NHỎ ĐI trên bong bóng hẹp.** Đó là đánh đổi có chủ đích — đọc được nhưng nhỏ, thay vì to
  mà vô nghĩa. Nếu nhỏ quá thì đòn tiếp theo là **rút gọn bản dịch** (E18 đã có, hiện chỉ chạy khi
  người dùng bấm) hoặc **nới ô đặt chữ** (A1).
* Bong bóng **dọc** của manga vốn không hợp chữ Việt ngang. E16 nửa chữ dọc vẫn **bị chặn** ở tầng
  hợp đồng OCR — đó mới là lời giải gốc, chưa làm được.
