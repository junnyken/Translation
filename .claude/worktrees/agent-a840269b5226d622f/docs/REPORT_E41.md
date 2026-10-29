# REPORT E41 — hạ trần bộ nhớ bước xoá chữ (hướng B)

**Ngày:** 2026-09-14 · **Quyết định của người dùng:** hướng **B** (hạ trần), **KHÔNG** nâng RAM

## Summary

Worker production bị `SIGKILL/137` **hai lần**. Người dùng chọn hạ trần diện tích thay vì nâng
RAM, nên trần **là lớp bảo vệ duy nhất**. Hạ `2,6 → 1,6 Mpx` trên **cả hai** trần, dựa trên phép
đo lại — kèm hai phát hiện làm đổi hẳn kết luận so với dự định ban đầu.

| | |
|---|---|
| Đỉnh bộ nhớ ở trần cũ (2,6 Mpx) | 3710–3912 MB = **96–102%** ngân sách worker (~3850 MB) |
| Đỉnh bộ nhớ ở trần mới (1,6 Mpx) | 2401 MB (xấu nhất trong vùng cho phép) = **62%** |
| Giá phải trả | **thêm đúng 1 trang trên 38** bị từ chối (2/38 thay vì 1/38) |
| Migration | không |

## Audit Before Build

### Hiện tượng

`/healthz` của `translation-api`:

```
worker: trang_thai "restarting" · so_lan_chet 2 · ma_thoat_gan_nhat 137
        rss_mb 1479.4 tại mốc "inpaint: trước"
```

Log container xác nhận:

```
07:37:41Z  deploy-start.sh: 1195 Killed   celery -A app.workers.celery_app ... --pool=solo
07:37:41Z  [worker] BỊ GIẾT (SIGKILL/137) — nghi ngờ hết bộ nhớ
07:37:41Z  [worker] đã thoát (mã 137), lần chết thứ 2 — bật lại sau 10s
```

RAM container: **4096 MB**. `get_resources`: `maxRamMB` 5376, `freeRamMB` 5376 (còn chỗ nâng —
người dùng chốt KHÔNG nâng).

### Chỗ không được suy đoán

Lúc 06:50 cổng E23 đã **từ chối đúng** một ô 3,43 Mpx (`crop_too_large`) — nó làm đúng việc. Cái
chết lúc 07:37 là **một việc khác, đã qua được trần 2,6**. Ô đó bao nhiêu điểm thì **không biết**:
log của nó đã bị cuốn khỏi 500 dòng cuối. Nên kết luận đúng là *"trần 2,6 không đủ"*, chứ không
phải một con số cụ thể nào.

### Máy đo của E23 đã mục — chưa ai đo lại được từ E23 tới nay

```
TypeError: LamaInpainter.__init__() got an unexpected keyword argument 'mem_budget_gb'
```

E23 đổi phép canh từ hệ số GB/Mpx sang trần diện tích mà không sửa
`scripts/do_duong_cong_bo_nho_inpaint.py`. Đã sửa (`max_crop_mpx=0` để tắt phép canh khi đo).

## Design Choice

### Đo lại trên hai máy đo độc lập

| ô cắt | E23 (cgroup 4096) | đo lại 14-09 (không giới hạn) | lệch |
|---|---|---|---|
| 1,4 Mpx | 2076 MB | **2401 MB** | +15,7% |
| 1,6 Mpx | — | **2295 MB** | — |
| 1,8 Mpx | — | **2951 MB** | — |
| 2,0 Mpx | 3367 MB | **2985 MB** | **−11,3%** |
| 2,6 Mpx | 3710 MB | **3912 MB** | +5,4% |

Lệch **+16% / −11% / +5%** ⇒ đây là **nhiễu ±15% của allocator**, KHÔNG phải độ lệch môi trường
có hướng. Hệ quả phương pháp: **không quy được thang máy này về thang máy kia**, phải lấy giá trị
**xấu nhất** của cả hai loạt tại mỗi cỡ. Đường cong cũng **không đơn điệu** (1,6 tốn ít hơn 1,4),
đúng như E23 đã ghi ("có bậc, không trơn") ⇒ không nội suy, phải đo từng điểm.

Điều hai máy đo nói **giống nhau**: ở 2,6 Mpx đỉnh là **3710–3912 MB**, tức 96–102% ngân sách
worker. Cộng API ~115 MB thường trú **cùng container** thì không vừa. Đó là xác nhận độc lập cho
cái chết 137 — và là lý do thật để hạ trần, không phải suy đoán.

### Phát hiện 1 — chặn trên sai gấp 7 lần, và nó gần làm tôi chọn sai

Lượt đầu tôi ước giá phải trả bằng **chặn trên**: bbox trùm mọi vùng chữ của trang + lề.

```
chặn trên:      trần 1,6 -> 14/38 trang có thể bị từ chối (37%)
gom_cum thật:   trần 1,6 ->  2/38 trang bị từ chối (5%)
```

**Sai 7 lần.** Chặn trên giả định mọi vùng gộp một cụm, trong khi `gom_cum` tách chúng. Với con số
37% tôi đã gần kết luận "1,6 quá đắt, phải chọn 2,0". Bài học: chốt trần bằng chặn trên là chốt
bằng con số sai — phải chạy đúng hàm mà đường thật chạy.

Ô cắt lớn nhất THẬT trên 38 trang:

```
2,70 Mpx (trang bạt, 11 vùng -> 1 cụm) · 1,96 Mpx (5 vùng -> 1 cụm) · rồi TỤT xuống <= 1,06 Mpx
```

| trần | trang bị từ chối |
|---|---|
| 1,4 / 1,6 / 1,8 | **2/38 (5%)** |
| 2,0 / 2,6 | 1/38 (3%) |

Khoảng **1,06 → 1,96 rỗng** ⇒ mọi trần trong đó từ chối đúng cùng một tập trang.

### Vì sao chọn 1,6

| trần | đỉnh xấu nhất trong vùng cho phép | % ngân sách | trang bị từ chối |
|---|---|---|---|
| 1,4 | 2401 MB | 62% | 2/38 |
| **1,6** | **2401 MB** | **62%** | **2/38** |
| 1,8 | 2951 MB | 77% | 2/38 |
| 2,0 | 3367 MB | 87% | 1/38 |
| 2,6 (cũ) | 3912 MB | **102%** | 1/38 |

- **1,8 bị loại thẳng:** không mua thêm được trang nào so với 1,6 mà đỉnh nhảy +550 MB.
- **2,0 giữ được 1 trang nữa nhưng ở 87%** — worker đã chết ở 96%, nên 87% không phải biên an toàn
  khi còn API và các phần thường trú khác trong cùng container.
- **1,6 trên 1,4** vì cùng đỉnh, cùng số trang, mà cách mức thường thấy của trang thật (1,06 Mpx)
  một khoảng 1,5× — lề đó bảo vệ những trang chưa đo.

### Phát hiện 2 — hạ MỘT trần là làm chết tính năng

Đường xoá **cả trang** cũng đi qua `_kiem_tran_o_cat`, và nó nộp **diện tích cả trang**
(`lama.py:275`):

```
trang <= whole_page_max_mpx  ->  chạy cả trang  ->  _kiem_tran_o_cat(DIỆN TÍCH CẢ TRANG)
trang >  whole_page_max_mpx  ->  chia cụm       ->  _kiem_tran_o_cat(ô lớn nhất)
```

Nên nếu chỉ hạ `inpaint_max_crop_mpx` xuống 1,6 mà để `inpaint_whole_page_max_mpx` ở 2,5 thì
**mọi trang giữa 1,6 và 2,5 bị từ chối thẳng** — kể cả trang truyện cỡ đọc 1200×1800 (2,16 Mpx),
tức gần như toàn bộ. Đó là làm chết đúng tính năng mình đang cứu.

**Bất biến mới: `inpaint_whole_page_max_mpx` ≤ `inpaint_max_crop_mpx`.** Đặt cả hai = 1,6: trang
≤1,6 chạy cả trang và qua được trần; trang >1,6 chuyển sang chia cụm và được lợi từ việc chia.

## Changed Files

| Tệp | Việc |
|---|---|
| `backend/app/core/config.py` | `inpaint_max_crop_mpx` 2,6 → 1,6 · `inpaint_whole_page_max_mpx` 2,5 → 1,6, kèm bảng số đo và bất biến |
| `backend/app/main.py` | `/healthz` thêm `inpaint_tran_mpx` (tín hiệu tự chứng + nói ra lớp bảo vệ) |
| `backend/scripts/do_duong_cong_bo_nho_inpaint.py` | sửa máy đo đã mục từ E23 |
| `backend/tests/test_inpaint_lama_unit.py` | lớp `TestE41HaTranBoNho` — 5 test |
| `backend/tests/test_d_healthz_llm_configured_integration.py` | canh bất biến qua HTTP |
| `docs/{API,FEATURES,TEST_LOG}.md` | API §E41 · bảng tính năng · nhật ký test |

## New API / DB / State

- **API:** `/healthz` thêm `inpaint_tran_mpx` — cộng thêm, không đụng trường nào đang có.
- **DB:** không migration.
- **State:** không trạng thái mới. `crop_too_large` đã tồn tại từ E23.

## Tests

`30 passed` cho hai tệp liên quan, `pytest_exit=0`. Bộ đầy đủ: xem §Live Verification.

Ba test canh đúng cái bẫy ở Phát hiện 2, và chúng **đọc `Settings()` chứ không truyền số cứng**:

| test | canh gì |
|---|---|
| `test_tran_ca_trang_KHONG_duoc_lon_hon_tran_o_cat` | bất biến trên cấu hình THẬT |
| `test_trang_truyen_co_doc_binh_thuong_van_chay_voi_cau_hinh_THAT` | 1200×1800 phải chạy — hạ một trần thì ĐỎ |
| `test_cau_hinh_LECH_thi_chan_oan__chong_rong_nghia` | cấu hình lệch thì **cùng trang đó** bị chặn ⇒ hai test trên không rỗng nghĩa |

Cộng `test_healthz_khai_hai_tran_bo_nho_inpaint`: bất biến được canh thêm một lần **từ ngoài qua
HTTP**, vì đây là lớp bảo vệ duy nhất và nó phải nói ra được.

## Live Verification

Điền sau khi deploy — điều kiện chờ là **trường tự chứng**, không phải chữ "deploy thành công":

```
/healthz  ->  inpaint_tran_mpx = { "ca_trang": 1.6, "o_cat": 1.6 }
```

## Remaining Limits

1. **Không biết ô nào đã giết worker.** Log đã bị cuốn. Nên 1,6 là chọn theo *ngân sách*, không
   phải theo *ca đã gây lỗi*. Nếu còn chết ở 62% thì nguyên nhân nằm ngoài bước xoá chữ.
2. **Thêm 1 trang trên 38 bị xếp "Hỏng"** — trang 1,96 Mpx. Nó bị từ chối *sạch* (có câu lỗi nói
   cách xử lý) chứ không làm chết worker, nhưng người dùng vẫn thấy "Hỏng". Việc *trang quá lớn
   nên xuống thang êm thay vì báo hỏng* là món nợ riêng, **chưa mở**.
3. **Cỡ mẫu 38 trang, 3 chapter, một tác giả.** Chưa biết truyện khổ khác (trang đôi, webtoon
   dọc) có phân bố cụm thế nào.
4. **Nhiễu đo ±15%** nghĩa là mọi con số MB ở đây chỉ đáng tin tới ~±350 MB. Kết luận "2,6 không
   vừa" vẫn vững vì cả hai máy đo đều cho 96%+; nhưng đừng dùng bảng này để tinh chỉnh 100 MB.
5. **Giả thuyết chưa kiểm: job trùng của E35 có thể CÙNG một lỗi với cái chết này** — worker chết
   rồi bật lại trong khi Celery còn giữ việc chưa ack thì việc bị chạy lại. Nếu đúng thì sửa riêng
   phần điều phối sẽ không hết. Chưa đo.
