# REPORT E50 — Vòng đời tệp: chapter tự xoá sau khi xong

**Ngày:** 2026-09-26 · **Nguồn yêu cầu:** `MINI_SPEC_HAN_MUC_VONG_DOI.md` §4 + `DAC_TA_TRANG_CHINH_VA_HAN_MUC.md` §2

---

## 1. Summary

Chapter đã chạy xong tự xoá sau **30 phút** (cấu hình được): ảnh gốc, ảnh đã xoá chữ, bản dịch,
tệp xuất — tất cả. Lịch chạy định kỳ là cơ chế **mới**, dự án trước đây không có cái nào.

**Mặc định TẮT** (`BAT_LICH_DON_TEP=false`). Đây là hành vi xoá dữ liệu không hoàn tác được, nên
nó phải bật tường minh sau khi đã quan sát mốc `het_han_luc` được ghi đúng trên bản chạy thật.

**Chưa làm:** tự động tải về (§3 đặc tả). Xem §7 — đây là phần **phải có trước khi bật** lịch dọn.

---

## 2. Audit Before Build — một "chỗ chặn" hoá ra không có thật

Đặc tả §6bis ghi một chỗ chặn:

> *"Kho lưu trữ có BA nền, mỗi nền xoá một kiểu. Production đang dùng nền nào thì CHƯA BIẾT.
> **Phải tra trước khi viết phần dọn dẹp.**"*

Đọc mã thì cả hai vế đều không đứng vững:

| Đặc tả nói | Mã thật |
|---|---|
| Ba nền lưu trữ | **Hai.** `supabase` chưa implement dòng nào — `build_storage` ném `SupabaseStorageNotConfigured` thẳng, nên production **không thể** đang chạy nền đó |
| Mỗi nền xoá một kiểu ⇒ phải biết nền nào | Cả hai nền đều hiện thực `IObjectStorage.delete_prefix()` cùng hợp đồng. Phần dọn viết trên interface là xong |

⇒ Không cần tra `STORAGE_BACKEND` của production. Chỗ chặn này **tự tan**.

### Nhưng có một chỗ đặc tả KHÔNG nhắc, và nó mới là chỗ dễ sai

Hiện vật của một chapter nằm ở **ba tiền tố**, không phải một:

| Tiền tố | Đánh theo | Chứa |
|---|---|---|
| `projects/{project_id}/` | chapter | ảnh gốc + ảnh đã xoá chữ |
| `exports/{project_id}` | chapter | tệp xuất |
| `previews/{page_id}/` | **TRANG** | ảnh xem thử đã căn chữ |

Viết `delete_prefix(f"projects/{id}")` rồi coi là xong sẽ **bỏ sót `previews/` vĩnh viễn** — đúng
kiểu "đĩa đầy dần trong im lặng" mà §2.5 đặc tả cấm. Và vì `previews/` đánh theo trang, phải lấy
danh sách `page_id` **trước** khi xoá chapter.

Có bài canh riêng cho đúng chỗ này. Đối chứng âm: bỏ tiền tố `previews/` ra ⇒ bài đỏ.

---

## 3. Design Choice

### 3.1. Đồng hồ bắt đầu khi CẢ CHAPTER xong

§2.3 đặc tả: một chapter 24 trang mất 30–40 phút để chạy, nên đếm từ lúc tải lên thì **tệp hết
hạn trước khi dịch xong** — người dùng chờ nửa tiếng rồi nhận về con số 0.

Cũng không đếm theo từng trang: trang 1 sẽ hết hạn trong khi trang 24 còn đang chạy.

**"Cả chapter xong" định nghĩa bằng: không còn job nào `queued`/`running`.** Cố ý KHÔNG định
nghĩa bằng `page.status` — một trang kẹt ở `detection_failed` không bao giờ đạt trạng thái cuối,
và chapter đó sẽ giữ tệp mãi mãi.

Mốc lưu **tuyệt đối** (`Project.het_han_luc`), không lưu "xong lúc nào" rồi cộng ở chỗ đọc: cộng
ở chỗ đọc nghĩa là đổi cấu hình sẽ dời hạn của cả những chapter đã xong từ trước.

Đặt mốc là **idempotent**: chapter đã có mốc thì không dời. Dời mốc mỗi lần chạy lại một bước sẽ
khiến chapter không bao giờ hết hạn. Ngược lại, chapter quay lại trạng thái đang chạy (người dùng
bấm "chạy lại") thì mốc bị **xoá** — chapter không được biến mất giữa chừng.

### 3.2. Đặt ở cùng một điểm nghẽn với quyết toán hạn mức

`workers/tasks.bao_ket_thuc_buoc` — hàm chạy ở cuối mọi bước. Cùng lý do như E49: thêm bước mới
vào pipeline cũng không quên.

Kiểm được thứ tự: `enqueue_ocr_after_detect` chạy **bên trong** `_run_detect`, tức trước điểm
nghẽn. Nên lúc đặt mốc, job kế tiếp đã nằm trong hàng đợi ⇒ không có mốc hết hạn giả giữa chừng.

### 3.3. Xoá tệp TRƯỚC, xoá dòng SAU

Xoá dòng trước rồi xoá tệp hỏng ⇒ mất luôn đường tìm lại tệp mồ côi (không còn `page_id` nào để
dựng tiền tố `previews/`). Xoá tệp trước mà xoá dòng hỏng ⇒ dòng trỏ vào tệp không còn — xấu,
nhưng **thấy được**, và lượt dọn sau dọn nốt.

Chọn cái hỏng nhìn thấy được, không chọn cái hỏng im lặng.

### 3.4. Hết hạn KHÔNG hoàn lượt — và vì sao nó chạy được

§2.8: hạn mức tiêu vào lúc **xử lý**, không phải lúc tải về.

Điều này đứng được là nhờ một quyết định từ E49: `so_cai_han_muc.trang_id` **cố ý không có khoá
ngoại**. Chapter bị xoá mà sổ cái vẫn nguyên. Có `ondelete="CASCADE"` thì xoá chapter sẽ xoá luôn
bằng chứng đã tiêu lượt ⇒ người dùng được lượt từ hư không. Có bài canh khoá điều này lại.

### 3.5. Lịch chạy: beat NHÚNG, không dựng tiến trình riêng

Topology là **đúng một** worker `--pool=solo` trên máy chủ đã bó 4096 MB, mà worker **đã bị hệ
điều hành giết 3 lần**. Dựng thêm một container beat là thêm một tiến trình Python cùng toàn bộ
thư viện AI — trả giá bộ nhớ thật để lấy một thứ chưa cần.

Đánh đổi đã biết: tài liệu Celery khuyên không dùng beat nhúng ở production vì nó không chịu được
nhiều worker. Với đúng một worker thì ràng buộc đó không áp. **Ngày nào chạy nhiều worker, phải
tách beat ra TRƯỚC** — nếu không mỗi worker tự chạy lịch của riêng nó và các lượt dọn chạy chồng
lên nhau.

`--schedule=/tmp/celerybeat-schedule`: mặc định beat ghi tệp lịch vào **thư mục làm việc**, mà
thư mục đó có thể chỉ-đọc trên nền tảng hosting ⇒ worker chết lúc khởi động vì một tệp phụ trợ.

Lịch chỉ được **đăng ký** khi `bat_lich_don_tep` bật. Để task tự kiểm cờ cũng được, nhưng như vậy
beat vẫn đánh thức worker mỗi 5 phút để chạy một hàm trả về ngay — tiếng ồn vô ích.

`-B` **có mặt sẵn** trong lệnh khởi động dù cờ mặc định tắt, nên bật tính năng là đổi **biến môi
trường**, không phải sửa lệnh rồi deploy lại.

---

## 4. Changed Files

| Tệp | Sửa gì |
|---|---|
| `app/services/don_tep_het_han.py` (mới) | Đặt mốc + lượt dọn |
| `alembic/versions/0022_e50_het_han_luc.py` (mới) | `project.het_han_luc` + chỉ mục |
| `app/models/__init__.py` | Cột `het_han_luc` |
| `app/core/config.py` | 4 biến: `giu_ket_qua_phut`, `tu_xoa_cho_tai_khoan`, `don_tep_moi_giay`, `bat_lich_don_tep` |
| `app/workers/tasks.py` | Nối vào điểm nghẽn + task `vong_doi.don_tep_het_han` |
| `app/workers/celery_app.py` | `beat_schedule` có điều kiện |
| `backend/deploy-start.sh`, `deploy/docker-compose.yml` | `-B --schedule=/tmp/celerybeat-schedule` |

---

## 5. Một câu CHƯA CHỐT — và tôi đã chọn mặc định nào

**Luật 30 phút có áp cho tài khoản đã đăng ký không?**

Đặc tả §2.1 viết không phân biệt: *"Truyện đã dịch xong chỉ giữ 30 phút."* Nhưng §2.9 nói rõ hậu
quả: sau đó người dùng **không chạy lại được và không sửa lại được**. Áp điều đó cho người đã
đăng ký là một quyết định sản phẩm, không phải chi tiết kỹ thuật.

Đã làm: `TU_XOA_CHO_TAI_KHOAN`, **mặc định `true`** (đúng đặc tả). Đặt `false` thì chỉ chapter
của khách lạ bị dọn, chapter của người đã đăng ký giữ nguyên.

⇒ **Chủ dự án cần chốt câu này trước khi bật `BAT_LICH_DON_TEP`.** Đổi sau khi đã xoá thì không
lấy lại được gì.

---

## 6. Tests

19 bài mới (`test_e50_don_tep_het_han.py`). Bốn bài canh nặng nhất:

| Bài | Canh cái gì |
|---|---|
| `test_KHONG_xoa_chapter_con_viec_dang_chay` | §2.4 — xoá tệp giữa lúc worker đang đọc tạo lỗi không tái hiện được |
| `test_xoa_DU_CA_BA_tien_to` | `previews/` đánh theo trang, là cái dễ sót nhất |
| `test_het_han_KHONG_hoan_luot_han_muc` | §2.8 — thêm khoá ngoại vào `trang_id` thì bài này đỏ |
| `test_dong_ho_dem_tu_luc_XONG_khong_phai_luc_tai_len` | §2.3 |

**Đối chứng âm đã chạy:** bỏ tiền tố `previews/` ra ⇒ `test_xoa_DU_CA_BA_tien_to` đỏ.

---

## 7. Remaining Limits

**PHẢI có trước khi bật `BAT_LICH_DON_TEP`:**

* **Tự động tải về (§3 đặc tả) — CHƯA LÀM.** Đặc tả nói thẳng: *"Làm luật 30 phút mà không có tự
  tải về là bày ra một cái bẫy."* Người dùng đóng tab rồi quên là mất hẳn. **Bật lịch dọn trước
  khi có phần này là cố ý dựng cái bẫy đó.**
* **Báo trước trên giao diện (§2.7)** — đồng hồ đếm ngược + câu cảnh báo đúng mức §2.9. Chưa có.
* Chốt câu §5 ở trên.

**Chưa chạy thật lần nào.** Toàn bộ §6 là bộ test trên máy. Phải kiểm sau khi deploy:

1. Mốc `het_han_luc` có được ghi đúng sau khi một chapter thật chạy xong không (bật `-B` nhưng
   vẫn để `BAT_LICH_DON_TEP=false` — beat chạy không lịch, chỉ quan sát cột).
2. Beat nhúng có khởi động được trong container không (kiểm tệp `/tmp/celerybeat-schedule`).
3. Rồi mới bật lịch, và theo dõi `tep_that_bai` trong log — `> 0` kéo dài là dấu hiệu cần người
   xem (§2.6).
