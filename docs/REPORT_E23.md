# Báo cáo Mini-Spec E23 — Chạy thử quy mô thật 24 trang

**Project:** Translation · **Phase:** E — Hosted Reliability & Performance
**Ngày:** 2026-09-10 · **Nền:** `faec936` (sau E25 đóng)
**Trạng thái:** **6 bản sửa** đã làm và kiểm live · lượt 24 trang **ĐÃ XONG 24/24** · 1 bản sửa **bị bác bỏ có lý do** · 1 "lỗi" hoá
ra **không phải lỗi production**

## 1. Summary

`REPORT_E25.md §6` ghi rõ con số "24 trang ≈ 54 phút" là **ngoại suy tuyến tính từ 6 trang**, chưa
ai chạy thật. E23 chạy thật một chapter 24 trang để kiểm ba điều: thời gian, bộ nhớ qua lượt dài,
và E22 dưới một lượt dài thật.

**Nó tìm ra thứ mà lượt 6 trang không thể tìm.** Một cú **SIGKILL thật** đã xảy ra ở phút ~10 —
đúng sự cố P1 của `PILOT_UAT_001`, lần đầu chạm vào E22 ngoài test tổng hợp.

| Phát hiện | Kết luận |
|---|---|
| SIGKILL để job kẹt `running`, trang kẹt `detecting` 20+ phút | **KHÔNG phải lỗi production** — tạo tác của pool local. §3 |
| Bàn thử dùng pool khác production | **LỖI THẬT, đã sửa** — §3 |
| Prefork + SIGKILL ⇒ job **mất hẳn**, không phải chậm | Đo được: qua mốc `visibility_timeout` vẫn không giao lại. §3.2 |
| `processing_state` của E22 dưới SIGKILL thật | **ĐÚNG** — trả `worker_interrupted`. §3.3 |
| `completed_pages` đứng 0 suốt >40 phút | **LỖI THẬT (gây hiểu sai), đã sửa** — §4 |
| Trang kẹt vĩnh viễn khi thiếu `_clean.png`, mọi nút bấm vô ích | **LỖI NẶNG NHẤT, đã sửa** — §4b |
| Mục mẻ kẹt `running` ⇒ mẻ đứng im 40 phút | **LỖI THẬT, đã sửa + kiểm live** — §4c |
| Một trang giết worker **4 lần**; cụm gộp thành cả trang ⇒ tiết kiệm bằng 0 | **LỖI THẬT, đã sửa + kiểm live** — §4d |
| Cờ `inpaint_needs_review` bật 29% số trang, **cả 11 vùng chỉ 1 ký tự** ⇒ báo động giả | **LỖI THẬT, đã sửa** — §4e |
| 25 job detect cho 24 trang | Lỗi thật nhưng **KHÔNG sửa** — cân không đáng, §5 |
| Mẻ không tự chạy tiếp sau sự cố (phải bấm "Chạy lại") | Giới hạn còn lại, có đường thoát — §4c.4 |
| **Câu hỏi khởi đầu: 24 trang ≈ 54 phút?** | **ĐÚNG** — trung vị 107,3s/trang × 24 × 1,25 = 53,6 phút, khớp E25. Nhưng p90 ⇒ ~99 phút. §4f |
| **RSS đỉnh 3604MB = 91% ngân sách production** | Số quan trọng nhất; lật lại quyết định giữ 4096MB ở E25. §6 |

## 2. Bàn thử — và một chỗ không dựng được

24 trang Pepper&Carrot (David Revoy, **CC BY-SA 4.0**, peppercarrot.com): 6 trang ep11 đã có +
18 trang tải thêm từ ep12/13/14, bỏ trang bìa `P00` để mọi trang đều là trang nội dung.
Ảnh ở `test_fixtures/external/` (đã `.gitignore`), **không** commit.

**Không bó được bộ nhớ container.** Định bó worker ở 3950MB cho khớp production (4096MB trừ ~104MB
uvicorn chiếm lúc rảnh — production dùng `ROLE=all`, một container chứa cả API lẫn worker). Môi
trường DinD từ chối: `cannot enter cgroupv2 "/sys/fs/cgroup/docker" with domain controllers -- it
is in threaded mode`, và container **không start nổi**. Đã khôi phục ngay.
`deploy/docker-compose.e23-mem.yml` giữ lại kèm ghi chú, vì trên một host Docker bình thường nó
đúng.

⇒ Lượt này **không** quan sát được hành vi hồi phục sau OOM. Nó chỉ **dự đoán**: đo RSS đỉnh rồi so
với ngân sách. Không được đọc thành "E22 hồi phục tốt".

**Bẫy đã tránh khi lấy trang:** peppercarrot.com trả HTTP **200** kèm một trang HTML 12481 byte cho
MỌI URL sai. Lượt dò đầu tiên "tìm thấy 36 trang" — toàn bộ là soft-404. Mã 200 không phải bằng
chứng có ảnh; phải kiểm magic byte JPEG + mở được bằng PIL.

**Một lỗi của tôi, ghi lại:** lượt tải đầu kiểm bằng `file --mime-type`, mà `file` **không có**
trong máy này ⇒ phép kiểm luôn thất bại ⇒ script **xoá sạch cả 18 ảnh thật vừa tải**.
"Không kiểm được" phải là **lỗi làm dừng**, không được tính thành phán quyết "tệp xấu".

## 3. Lỗi 1 — bàn thử lệch production ở đúng chế độ hỏng quan trọng nhất

### 3.1 Truy nguyên

Ở phút ~10: `Process 'ForkPoolWorker-1' pid:8 exited with 'signal 9 (SIGKILL)'` ⇒
`WorkerLostError: Worker exited prematurely: signal 9 (SIGKILL) Job: 13.`

20 phút sau, job đó vẫn `running`, trang vẫn `detecting`, `error_class`/`exit_signal` **rỗng**,
không có lượt quét job mồ côi nào chạy. Nhìn thì y như một lỗi hồi phục nghiêm trọng của E22.

Nhưng không phải:

| | Pool | SIGKILL giết gì | `worker_ready` phát lại? | Quét mồ côi |
|---|---|---|---|---|
| production (`deploy-start.sh`) | `--pool=solo` | **cả worker** ⇒ vòng `while true` bật lại sau 10s | **CÓ** | **chạy** |
| local (trước bản sửa) | `--concurrency=1` (prefork) | chỉ tiến trình **con** | KHÔNG | **không chạy** |

`don_job_mo_coi` gắn vào **duy nhất** tín hiệu `worker_ready` (`celery_app.py:47`). Với prefork,
Celery sinh tiến trình con thay thế và tiến trình chính sống tiếp ⇒ tín hiệu không bao giờ phát
lại ⇒ job mồ côi nằm lại vĩnh viễn. **Lỗi chỉ có ở local.**

Chuỗi hồi phục của production nguyên vẹn và đã đọc lại từng bước: `--pool=solo` → SIGKILL → mã
thoát 137 → `ghi_trang_thai restarting` (ghi cả mã thoát) → `sleep 10` → khởi động lại →
`worker_ready` → quét mồ côi gắn nhãn `resource_limit_suspected` + `SIGKILL(137)`.

### 3.2 Đo thêm: prefork làm job MẤT HẲN, không phải chậm

Cấu hình có `task_acks_late=True` + `visibility_timeout=1800`, và ghi chú trong `celery_app.py`
nói "worker chết giữa chừng thì broker GIAO LẠI". Đã canh mốc đó bằng số đo: SIGKILL lúc
**09:36:06Z**, mốc giao lại **10:06:06Z**. Kết quả:

```
[10:04:43 UTC] vẫn running (lượt 36)
[10:06:46 UTC] vẫn running (lượt 42)   ← đã QUA mốc, không giao lại
```

⇒ Với prefork, tiến trình chính **sống sót nên nó tự xử lý `WorkerLostError`** và message không
còn nằm chờ giao lại. Job mất hẳn. Ghi chú kia **chỉ đúng cho pool không fork**, nơi SIGKILL giết
cả tiến trình nên không ai ack.

Đây là lý do bản sửa phải là **làm bàn thử khớp production**, không phải vá thêm đường hồi phục
cho một pool mà production không dùng.

### 3.3 Nửa hoạt động đúng — `processing_state` của E22

```json
"status": "running",                        ← cột DB giữ nguyên: đúng, không ai quan sát được nó dừng
"heartbeat_at": "2026-09-10T09:35:10Z",     ← nhịp tim đứng từ TRƯỚC lúc bị giết 09:36:06
"processing_state": "worker_interrupted"    ← suy ra LÚC ĐỌC, ĐÚNG
```

Lần đầu E22 được xác nhận dưới một cú gián đoạn **thật**. Phần người-dùng-thấy làm đúng việc, kể
cả trong cảnh mà đường tự hồi phục không chạy.

### 3.4 Bản sửa

`deploy/docker-compose.yml`: `--concurrency=1` → `--pool=solo`, kèm ghi chú giải thích.

`backend/tests/test_worker_pool_config_unit.py` (**mới**, 3 test) khoá bất biến:
`test_production_dung_pool_khong_fork`, `test_pool_celery_phai_khop_production`,
`test_quet_mo_coi_van_gan_vao_worker_ready`. Cùng họ `test_broker_config_unit.py` — hai tệp cấu
hình ở hai chỗ và **không ai nhắc ai**.

**Chính test này bắt lỗi của nó:** bản đầu của hàm `_pool` lọc theo từng dòng, mà
`deploy-start.sh` viết lệnh celery trên ba dòng và `--pool=solo` nằm ở dòng thứ hai — dòng đó có
chữ "celery" (trong `-Q celery`) nhưng **không** có chữ "worker". Test báo production dùng
`prefork`, sai. Đã nối dòng tiếp nối trước khi tìm.

### 3.5 Bản sửa đầu CHƯA ĐỦ — và tự làm bàn thử tệ hơn

Đổi sang `--pool=solo` một mình là **sai**: không service nào trong compose có `restart` policy,
nên SIGKILL sẽ giết **hẳn** container worker. Prefork ít nhất còn sinh tiến trình con thay thế và
worker vẫn phục vụ tiếp. Production chịu được solo *chỉ vì* `deploy-start.sh` có vòng `while true`
bật lại sau 10s — đó là **một phần của lựa chọn solo, không phải tuỳ chọn thêm**.

Đã thêm `restart: unless-stopped` cho service `worker`, và thêm test thứ tư
`test_pool_solo_o_local_phai_kem_co_che_bat_lai`. Test đó đã được **kiểm ngược**: tạm bỏ dòng
`restart` ⇒ test ĐỎ; khôi phục ⇒ xanh. Một test guard không đỏ được thì không chứng minh gì.

### 3.6 Live verification — chuỗi hồi phục đầy đủ, ĐẠT

Bàn thử này có một thứ hoá ra hữu ích: **workspace bị OOM kill định kỳ** (§6.1), tức một máy tiêm
lỗi tự nhiên, đúng cảnh production gặp. Dùng nó để kiểm thật.

Trạng thái TRƯỚC khi áp bản sửa: **3 job `running`** (1 detect + 2 inpaint — hai mồ côi từ hai cú
SIGKILL, một đang chạy thật), tất cả `error_class`/`exit_signal` rỗng; 1 trang kẹt `detecting`.

Áp bản sửa (`docker compose up -d worker` ⇒ container mới với `solo` + `restart: unless-stopped`):

```
RestartPolicy=unless-stopped · Cmd=… worker -l info -Q celery --pool=solo
[10:20:14] WARNING/MainProcess] dọn job mồ côi (ĐÃ SỬA): 3 job -> failed, 1 trang lùi khỏi trạng thái tạm
[10:20:14] INFO/MainProcess] celery@0d2ce98aedee ready.
```

Ở tầng dữ liệu:

| | trước | sau |
|---|---|---|
| job `running` mồ côi | 3 | **0** |
| job `failed` có `error_class` | 0 | **3** (`worker_lost`) |
| trang kẹt `detecting` | 1 | **0** (về `queued`, chạy lại được) |

**Và nó trung thực ở đúng chỗ khó:** `exit_signal` để **rỗng**, `error_class` là `worker_lost`
chứ **không phải** `resource_limit_suspected`. Vì local không có `WORKER_STATE_FILE` (tệp đó do
`deploy-start.sh` ghi) nên không có mã thoát để đọc — và `phan_loai_tu_ma_thoat(None)` trả
`("worker_lost", None)` đúng như thiết kế, **không bịa** ra SIGKILL. Trên production, cùng cảnh này
sẽ ra `SIGKILL(137)` + `resource_limit_suspected` vì mã thoát có thật ở đó.

Việc chạy lại sau hồi phục: inpaint 9 `queued` + 1 `running`, translate 18 `queued`.

**Trang hồi phục có được xếp lại — xác nhận bằng số đo, không bằng suy luận:**

```
quét mồ côi   10:20:14Z   trang cc1fffc9: detecting -> queued
xếp lại detect 10:33:11Z  (job detect mới cho đúng trang đó)
```

⇒ Chuỗi hồi phục hoàn tất đầu-cuối: SIGKILL → bật lại → `worker_ready` → quét mồ côi → job đánh
`failed` có phân loại trung thực → trang về trạng thái chạy lại được → mẻ xếp lại việc.

**Nhưng trễ ~13 phút.** Không phải lỗi: `dispatch_next` chỉ chạy khi một trang tới trạng thái cuối,
và mẻ giữ `batch_max_concurrent_pages=2`, nên trang hồi phục phải đợi chỗ trống. Đây là con số cần
biết khi hứa hẹn với người dùng về thời gian hồi phục — "tự chạy lại" không có nghĩa là "ngay".

## 4. Lỗi 2 — `completed_pages` đứng 0 gần hết lượt chạy

Đo ở phút 43: **22/24 trang đã qua bước đọc chữ**, mà `BatchPanel` hiện `0/24 trang xong` và thanh
tiến độ đứng **0%**. Nhìn y như máy đã treo.

Nguyên nhân: hàng đợi FIFO nên pipeline chạy gần như theo từng **bước** qua tất cả các trang, chứ
không xong hẳn từng trang. Sâu hơn: mẻ có `batch_max_concurrent_pages=2` nên nó chỉ theo dõi 1-2
trang một lúc, còn phần lớn công việc do **chuỗi tự chảy sau upload** làm — kiểm được ở bảng
`batch_item`: 23 mục `pending`, 1 `running`.

**Con số 0 KHÔNG sai** (thật sự chưa trang nào qua hết mọi bước). Nên bản sửa **không bịa ra một
phần trăm khác** — dự án có nguyên tắc không bịa phần trăm (`lib/chapter-progress.js`). Sửa bằng
cách nói rõ nó đếm gì:

- `0/24 trang xong` → `0/24 trang xong **hết mọi bước**`
- Khi đang chạy mà chưa trang nào xong: thêm một câu nói ô này đứng ở 0 gần hết lượt chạy, trang
  đang chạy dở không được tính, và chỉ sang **Tiến trình chapter** — nơi `tinhTienDoChapter` (E11)
  **đã** tính đúng "số trang đã qua từng bước".

`BatchPanel.test.jsx` (**mới**, 5 test) canh cả bốn cảnh **không** được hiện chú thích: đã có trang
xong, mẻ đã kết thúc (0/24 lúc đó là tin thật), và chapter một trang.

## 4b. Lỗi 3 — trang kẹt vĩnh viễn khi thiếu ảnh đã xoá chữ (nặng nhất)

**Hiện tượng:** 12 job `typeset` hỏng `FileNotFoundError: … _clean.png`, **tất cả thuộc cùng MỘT
trang** (`bb536dfa` = E11P01). Trang kẹt ở `translated`. Mục mẻ bị phân loại `permanent_model`.

**Nguyên nhân:** một cú SIGKILL vào bước xoá chữ để lại trang mang trạng thái như thể bước đó đã
xong, nhưng `<page_id>_clean.png` **không tồn tại** trong kho.

**Ba cơ chế đã có đều KHÔNG cứu được — đã kiểm từng cái:**

| Cơ chế | Vì sao không cứu |
|---|---|
| Quét job mồ côi (E22, lúc `worker_ready`) | Khôi phục trạng thái *job/trang*, **không** khôi phục *hiện vật*. Trạng thái trang này vẫn "hợp lệ" nên nó không đụng tới. |
| `doi_chieu_hien_vat` (P3f) | **Bắt được** — chạy thật, in đúng `page bb536dfa…: mất ảnh clean (…) · translated -> ocr_done`. Nhưng phải có người chạy tay: `RECONCILE_LEGACY` mặc định `off`. |
| Nút "Chạy lại trang hỏng" của mẻ | Chạy lại bước căn chữ, mà tệp vẫn thiếu ⇒ **hỏng tiếp**. Đây là lý do có tới 12 lần hỏng. |

⇒ **Người dùng thật không có đường nào tự thoát.** Đây là lỗi nặng nhất E23 tìm ra: không mất dữ
liệu, nhưng một trang chết cứng và mọi nút bấm đều vô ích.

### 4b.1 Bản sửa — để bước căn chữ tự dọn tại chỗ hỏng

`_lui_neu_mat_anh_clean()` chạy **trước** khi căn chữ: thấy `clean_image_path` trỏ tới tệp không
tồn tại thì lùi trang về mốc còn bằng chứng và báo lỗi nói rõ phải làm gì.

Bốn quyết định:

**Kiểm TRƯỚC, không bắt ở `except`.** Bắt theo `FileNotFoundError` là dựa vào kiểu/chuỗi của một
lỗi phát sinh sâu trong bước vẽ — giòn, và không phân biệt được "mất ảnh clean" với "mất font".

**Dùng lại ĐÚNG luật lùi của công cụ quét toàn bộ** (`_muc_lui_khi_mat_anh_clean`): có OCR trong
CSDL ⇒ `ocr_done`; chỉ có vùng chữ ⇒ `detected`; không gì ⇒ `queued`. Không lùi sạch, vì vùng chữ
và OCR nằm trong CSDL nên **không mất** — lùi quá tay là bắt chạy lại việc còn nguyên bằng chứng.
Có test theo cấu trúc canh việc dùng chung luật này, vì hai luật lùi sẽ lệch nhau khi ai đó sửa
một bên.

**KHÔNG nhồi ý định vào chuỗi lỗi.** `bao_ket_thuc_buoc` chỉ nhận chuỗi mô tả và bộ phân loại
đoán loại lỗi từ chuỗi đó. Có thể viết câu lỗi sao cho nó bị đoán thành "lỗi tạm" để mẻ **tự** chạy
lại — nhưng đó là lừa bộ phân loại và nói sai bản chất. Nên bản sửa chỉ làm nút "Chạy lại trang
hỏng" từ chỗ **vô ích** trở thành **có tác dụng**. Tự chạy lại là việc của slice sau.

**Câu lỗi phải nói cách thoát:** `missing_clean_image: thiếu ảnh đã xoá chữ (bước xoá chữ bị dừng
giữa chừng). Đã lùi trang về 'ocr_done' — chạy lại trang này sẽ xoá chữ lại rồi căn chữ.`

`test_e23_typeset_mat_anh_clean.py` (**mới**, 6 test) canh cả ba cảnh **không** được lùi: ảnh còn
nguyên, trang chưa từng xoá chữ (chế độ `chi_chu` của E19 bỏ hẳn bước này), job không còn tồn tại.
Lùi oan còn tệ hơn không lùi.

**Một tiền đề test của tôi sai, ghi lại:** bản đầu dựng `Job(page_id=None)` để mô phỏng job mồ
côi — CSDL từ chối vì `job.page_id` là `NOT NULL`. Cảnh "job không có trang" **không thể tồn tại**,
schema đã chặn sẵn; cảnh có thật là job bị xoá mất trong lúc task còn chờ trong hàng đợi.

### 4b.2 Đã sửa hiện trạng local

Chạy `doi_chieu_hien_vat --ap-dung` để E23 chạy tiếp (giữ nguyên output chế độ chỉ-đếm làm bằng
chứng ở trên): 1 trang được lùi `translated -> ocr_done`, và trang đó chạy lại được.

## 4c. Lỗi 4 — mục mẻ kẹt `running` làm MẺ ĐỨNG IM 40 phút

**Hiện tượng:** sau khi worker bị giết và bật lại, không còn job nào trong hàng đợi nhưng mẻ vẫn
`running` với 1 mục `running` + 4 mục `pending` chưa bao giờ tới lượt.

**Nguyên nhân, kiểm được ở tầng dữ liệu:**

```
BatchItem: running  →  current_job_id  →  job inpaint: FAILED (worker_lost)
```

Quét job mồ côi (E22) sửa **Job** và **Page**, nhưng **không** sửa `BatchItem`. Mẻ chờ một job đã
chết; mục `running` đó giữ mất chỗ chạy (`batch_max_concurrent_pages=2`) nên 4 mục `pending` đứng
im. Mẻ chỉ tự lành qua `thu_hoi_muc_mo_coi` sau `batch_stale_item_seconds` = **2400s (40 phút)**.

### 4c.1 Bản sửa

`don_job_mo_coi` nay đánh hỏng cả mục mẻ trỏ vào job đã tới trạng thái cuối.

**Đánh `failed`, KHÔNG đưa về `pending`.** `pending` nghĩa là mẻ tự xếp lại ngay — đúng điều mục
"Không tự chạy lại" ở đầu `hoi_phuc.py` cấm: *"Tự chạy lại một job vừa làm chết worker vì hết bộ
nhớ là cách nhanh nhất để giết nó lần nữa — và lần này thành vòng lặp."* `failed` vừa giải phóng
chỗ chạy, vừa giữ quyền quyết định cho người dùng. Mã lỗi dùng **đúng** `error_class` đã gắn cho
job (`worker_lost`) để hai tầng nói cùng một thứ, và có test canh nó **không** thuộc `MA_TAM_THOI`
— mã tạm thời sẽ bật đường tự thử lại, tức vòng lặp.

### 4c.2 Bản sửa ĐẦU của tôi bỏ sót đúng cảnh đang có

Bản đầu lọc theo "job vừa bị đánh mồ côi **trong lượt quét này**". Mục kẹt của E23 có job đã
`failed` từ một lượt quét **trước**, nên không nằm trong danh sách ⇒ **không được cứu**. Đã mở
rộng điều kiện thành *"mục `running` mà job của nó ĐÃ tới trạng thái cuối"* — không cần đoán, vì
quét chỉ chạy lúc worker khởi động khi không task nào đang chạy, nên không có cửa sổ "job vừa xong
mà `on_page_terminal` chưa kịp chạy" để giết oan. Có test riêng cho đúng cảnh này.

### 4c.3 Live verification

Khởi động lại worker để nạp code mới, trên chính mẻ đang kẹt:

```
dọn job mồ côi (ĐÃ SỬA): 0 job -> failed, 0 trang lùi khỏi trạng thái tạm, 1 mục mẻ -> failed
  mục mẻ bee79c4b… trang be643bb0…: running -> failed
```

`0 job` (chúng đã `failed` từ lượt quét trước) nhưng **1 mục mẻ** được cứu — chính cảnh bản đầu bỏ
sót. Mục mẻ sau đó: `failed | worker_lost`.

### 4c.4 Giới hạn còn lại — mẻ KHÔNG tự chạy tiếp sau sự cố

Giải phóng chỗ chạy **chưa đủ**: `dispatch_next` chỉ được gọi khi một trang tới trạng thái cuối,
mà lúc này không còn job nào chạy nên **không có gì kích hoạt nó**. Đo thật: sau lượt quét, 5 phút
liền không job nào vào hàng đợi.

Nhưng đường thoát của người dùng **thông suốt** — đã kiểm bằng lệnh thật, không suy luận:

```
POST /batch-runs/{id}/resume  ->  {"resumed_count": 2, "status": "running"}
sau 20s: inpaint | running | 1
```

⇒ Sau sự cố, mẻ **không tự chạy tiếp**; người dùng phải bấm "Chạy lại". Bản sửa này làm cho trạng
thái **nói thật** (mục hiện `failed` kèm lý do đọc được thay vì một mục `running` ma) — và đó chính
là thứ làm nút bấm kia có nghĩa.

Tự chạy tiếp **các trang còn lại** (khác hẳn tự chạy lại chính job đã giết worker — cái sau bị cấm)
là một quyết định về vòng đời của mẻ, nên để thành slice riêng chứ không nhét vào đây.

## 4d. Lỗi 5 — một trang giết worker 4 lần, và hai lần tôi tự sai trên đường sửa nó

### 4d.1 Hiện tượng và chẩn đoán

Trang `be643bb0` = **E13P07, 1200x2144 = 2,57 Mpx** — trang **lớn nhất** bộ (23 trang còn lại
1,99 Mpx) — có **4 job inpaint, tất cả `failed / worker_lost`** (10:05, 10:41, 11:10, 11:25). Mỗi
lần thử lại là **giết worker thêm một lần**, đúng vòng lặp mà docstring `hoi_phuc.py` cảnh báo — và
chính các lần tôi bấm "Chạy lại" đã tạo ra nó.

Code **đã có** cơ chế phòng: quá `inpaint_whole_page_max_mpx` = 2,5 thì chuyển sang xoá chữ theo
**cụm**. Log cho thấy nó có chạy: `Ảnh 1200x2144 (2.6 triệu điểm) vượt ngưỡng 2.5 -> xoá chữ theo
1 cụm`. Nhưng **"1 cụm"** là chỗ vỡ: trang có **11 vùng chữ trải khắp** (hộp bao chung 1039x2077 =
84% diện tích), và cơ chế gộp ô chồng nhau — vốn để tránh lộ đường nối giữa hai bong bóng sát nhau
— thu 11 vùng thành **một cụm phủ cả trang**. Đo trực tiếp: `số cụm: 1 · cụm lớn nhất: 2.57 Mpx`,
**đúng bằng cả trang**. Chạy theo cụm tiết kiệm **bằng 0**.

### 4d.2 Sai lần 1 — tôi dùng RSS-sau làm bằng chứng, nó không phải đỉnh

Log worker in `bộ nhớ [inpaint: sau]: RSS 1628.1 MB` và tôi đã định kết luận "trang chỉ cần
~1,5 GB, chẩn đoán 4 GB của tôi sai". **RSS *sau* là con số đã giải phóng mảng tạm — không phải
đỉnh.** Đo lại bằng `VmHWM` (high water mark) trên đúng trang đó:

```
trang        : 1200x2144 = 2.57 Mpx
số cụm       : 1        cụm lớn nhất : 2.57 Mpx
VmHWM ĐỈNH   : 3367.8 MB  (66.3s)
⇒ hệ số thật : 1.28 GB / triệu điểm
```

Đỉnh thật **gấp 2,07 lần** RSS-sau. Nếu tin RSS-sau thì đã kết luận ngược hoàn toàn.

### 4d.3 Sai lần 2 — tôi trình bày một lượt chạy làm bằng chứng cho code chưa tồn tại

Tôi báo rằng bản sửa đã được kiểm live vì lượt inpaint sau đó **thành công**. Đối chiếu mốc thời
gian thì không phải:

```
job inpaint thành công : 11:41:59Z
config.py sửa lúc      : 11:41:49Z
lama.py sửa lúc        : 11:42:43Z   ← SAU khi job đã chạy 44 giây
worker khởi động lúc   : 11:44:35Z   ← SAU cả hai
```

Lượt chạy đó diễn ra trên code **cũ**, trước khi phép canh tồn tại. Nó không nói gì về bản sửa.
Bài học: "sửa code rồi thấy nó chạy đúng" **chưa phải** bằng chứng — phải kiểm tiến trình đang chạy
có nạp đúng code đó chưa.

### 4d.4 Và hệ số của tôi sai theo chiều CÓ HẠI

Bản đầu dùng `gb_per_mpx = 1,6` — số ghi trong `lama.py`, nhưng nó **đo ở M4 cho đường chạy CẢ
TRANG**, không phải đường cụm. Với 1,6 thì trang E13P07 được dự đoán cần 4,11 GB > ngân sách
3,85 GB ⇒ **bị chặn**, trong khi đo thật nó cần 3,37 GB và **chạy được**. Tức phép canh của tôi
sẽ chặn oan đúng trang nó sinh ra để cứu — chiều sai tệ nhất, và đúng thứ E24 §3 gọi là "banner
báo sai dạy người dùng phớt lờ".

Đã hiệu chỉnh về **1,28 GB/Mpx** (số đo ở §4d.2, n=1) và thay test đã mã hoá niềm tin sai: nay
có test canh trang E13P07 **KHÔNG** bị chặn, và test canh trang cỡ đọc 1600x2259 (3,6 Mpx) **bị**
chặn.

### 4d.5 Bản sửa

`LamaInpainter._kiem_ngan_sach_bo_nho()` chạy **trước** khi gọi model, kiểm **ô cắt lớn nhất** (chứ
không kiểm cỡ trang — chạy theo cụm chỉ tiết kiệm khi cụm nhỏ), và ném `InpaintFailed` với câu lỗi
nói cả cách xử lý.

Phép canh này **không đổi chất lượng đầu ra một chút nào**: nó chỉ chặn đúng những lượt trước đây
kết thúc bằng SIGKILL. Đổi "worker chết, mọi việc đang chạy thành mồ côi, vòng lặp thử lại" thành
"một trang hỏng có lý do đọc được". `mem_budget_gb <= 0` là tắt tường minh.

### 4d.6 Live verification — cấu hình production, code thật trong container

```
cấu hình thật: gb_per_mpx=1.28 · ngân sách=3.85 GB
trang 1600x2259 = 3,61 Mpx (cỡ đọc — lama.py ghi: "cần ~5,8 GB và bị hệ điều hành giết")
KẾT QUẢ: CHẶN ĐÚNG, worker không bị giết
  memory_budget_exceeded: xoá chữ trang 1600x2259 cần khoảng 4.5 GB (cụm lớn nhất trong 1 cụm:
  3.51 triệu điểm x 1.28 GB/triệu điểm) nhưng ngân sách chỉ 3.85 GB. Đã DỪNG trước khi chạy…
```

**Chưa live-verify được chiều "không chặn oan" trên production**, vì sau khi hiệu chỉnh thì
**không trang nào trong chapter này bị chặn** — chỉ có unit test cho chiều đó.

### 4d.7 ĐO LẠI n=6 — và cách tiếp cận "hệ số GB/Mpx" SAI TỪ GỐC

Hai giới hạn còn lại của bản sửa này ("chưa live-verify chiều không-chặn-oan" và "hệ số n=1") có
**cùng một gốc**: quan hệ bộ nhớ ↔ diện tích mới chỉ đo một điểm. Đo cả đường cong (`VmHWM`, mỗi cỡ
một tiến trình riêng để đỉnh không cộng dồn):

| Ô cắt (Mpx) | Đỉnh (MB) | % ngân sách 3850MB | GB/Mpx |
|---|---|---|---|
| 0,80 | 1697 | 44% | **2,07** |
| 1,40 | 2076 | 54% | 1,45 |
| 2,00 | 3367 | 87% | 1,64 |
| 2,57 | 3368 | 87% | **1,28** |
| 2,60 | 3710 | **96%** | 1,39 |
| 3,20 | **BỊ GIẾT** (`oom_kill` 111→112) | — | — |

**Đường cong CÓ BẬC, không trơn.** Từ 2,00 → 2,57 gần như phẳng (**+1 MB**), rồi 2,57 → 2,60 nhảy
**+342 MB** chỉ vì thêm 0,03 Mpx. Tỉ lệ GB/Mpx chạy từ **1,28 đến 2,07** tuỳ cỡ. Không hệ số tuyến
tính nào — có hay không có hằng số chặn — mô tả được hình dạng này.

⇒ **Sai của tôi không nằm ở con số mà ở cách tiếp cận.** Và tệ hơn: 1,28 tôi đã commit là tỉ lệ
**THẤP NHẤT** trong cả loạt, nên nó đánh giá thấp nhu cầu ở mọi cỡ khác và sẽ **cho lọt** đúng
những trang làm chết worker — chiều sai nguy hiểm, ngược hẳn với chiều tôi lo lúc đầu.

Đã thay công thức bằng **một tham số đo trực tiếp**: `inpaint_max_crop_mpx = 2.6` (ô lớn nhất đo
được là chạy xong). Một số đo trung thực hơn một công thức bịa.

### 4d.8 Một giải pháp nữa đã bị BÁC BỎ trước khi viết code

Hướng hấp dẫn nhất là **tách cụm quá lớn tại dải ngang không có mask** — làm vậy thì ô cắt bị chặn
trên *theo thiết kế*, không cần dự đoán gì, và không đổi chất lượng vì chỗ tách không có gì để xoá.
Đo trên đúng trang E13P07 trước khi viết:

```
cụm sau khi gộp : [(0, 0, 1200, 2144)]  => 1 cụm phủ cả trang
số dải ngang KHÔNG có mask : 3
trong đó đủ rộng để tách (>=192px, giữ lề 96 hai bên) : 0
```

**Không dải nào đủ rộng.** 11 vùng chữ cách nhau ~10px sau khi nở mask — quá dày. Hướng này không
dùng được cho chính trang sinh ra nó.

### 4d.9 Live verification — CẢ HAI CHIỀU

| Chiều | Bằng chứng |
|---|---|
| **Chặn đúng** cỡ thật sự giết worker | Ô 3,14 Mpx ⇒ `crop_too_large: … vượt trần 2.60 …`, `oom_kill` giữ nguyên 112, worker sống |
| **Không chặn oan** cỡ thật sự chạy được | Trang E13P07 (2,57 Mpx) **chạy xong thật** trong lượt 24/24 của chapter — mạnh hơn unit test |

### 4d.10 Ý nghĩa cho production

Trang lớn nhất của một chapter bình thường cần **3368 MB = 87%** ngân sách worker (~3850 MB), và
chỉ cần lớn hơn 0,03 Mpx nữa là lên **96%**. Trang cỡ đọc (1600x2259 hoặc 3,2 Mpx) thì **vượt
thật** — nay được báo hỏng tử tế thay vì kéo sập worker.

**QUYẾT ĐỊNH 2026-09-11 (người dùng): GIỮ 4096MB.** Đề nghị nới RAM bị từ chối, nên
`inpaint_max_crop_mpx = 2.6` **chính là lớp bảo vệ duy nhất** cho cảnh này: trang vượt trần sẽ được
báo hỏng tử tế thay vì kéo sập worker. Hệ quả phải chấp nhận: **trang cỡ đọc (≥2,6 Mpx) không xử lý
được** — người dùng phải hạ độ phân giải trước khi tải lên. Nâng trần mà không nới RAM là mở lại
đúng đường làm chết worker.

Nội dung đề nghị đã bị từ chối, giữ lại để lần sau có dữ liệu mới thì mở lại:
**nới RAM worker 4096 → 5376MB.** `get_resources` xác nhận gói CÒN chỗ
(`maxRamMB: 5376`, `freeRamMB: 5376`), không tốn thêm tiền, không đổi code, không rủi ro chất
lượng. Nó đưa đỉnh 3710 MB từ **96% xuống ~71%** ngân sách, và cho phép nâng `inpaint_max_crop_mpx`
để nhận cả trang cỡ đọc.

Điều này **đảo lại quyết định ở E25 §2.6** (giữ 4096MB). Quyết định đó không sai lúc đó — nó dựa
trên lượt 6 trang với RSS phẳng ~1219MB. Nhưng 6 trang ấy **chưa bao giờ chạm bước xoá chữ hàng
loạt**, nơi đỉnh thật là 3710MB. Dữ liệu mới, kết luận mới.

## 4e. Lỗi 6 — cờ "cần rà soát" bật cho 29% số trang, gần như toàn báo động giả

Trong lượt 24 trang tôi ghi lại "7/23 trang ra `inpaint_needs_review` (~30%) — chưa soi vì sao".
Nay đã soi.

### 4e.1 Con số 30% là SỐ HỌC, không phải độ nhạy sai

Đếm trên log: **74 vùng chữ, 6 vùng bị gắn cờ = 8,1% mỗi VÙNG**, nhưng **4/9 trang = 44% mỗi
TRANG**. Một vùng hỏng là cả trang bị cờ, mỗi trang ~8 vùng ⇒ 1 − 0,92⁸ ≈ 49%. Tỉ lệ đáng quan tâm
là con số mỗi vùng, không phải mỗi trang.

### 4e.2 Nhưng bằng chứng cho thấy nó là báo động giả

Quét lại **toàn bộ 24 trang giao ra cuối cùng** (168 vùng) bằng đúng phép kiểm chứng đang chạy:

```
24 trang · 168 vùng · 11 vùng bị gắn cờ · 7 trang (29%) -> inpaint_needs_review
```

Và **cả 11 vùng đều đọc ra ĐÚNG MỘT ký tự**:

| Ký tự | Số lần |
|---|---|
| `O` | 4 |
| `X` | 2 |
| `G` · `1` · `C` · `è` · `中` | mỗi loại 1 |

Toàn `O`, `X`, `C`, `G`, `1` — đúng những hình OCR bịa ra từ nét cong/góc còn lại trên nền đã xoá
(viền bong bóng, khung panel). Có cả một **`中` trên trang TIẾNG ANH**. Chữ thật còn sót trong bong
bóng là một từ hoặc mảnh từ, không phải một ký tự đơn.

⇒ Tiêu chí `has_meaningful_text` (**≥1 ký tự**) quá lỏng cho mục đích này.

### 4e.3 Và cờ đó KHÔNG đưa ra bằng chứng nào

`_verify_text_removed` trả về **danh sách chữ đọc được**, nhưng `_run_inpaint` **chỉ dùng `len()`**
— chữ tìm được và vùng nào đều không lưu ở đâu, kể cả log lẫn kết quả job. Người dùng nhận được
"trang này cần rà soát" rồi phải tự soi cả 8-11 vùng để đoán vùng nào.

Đi ngược đúng nguyên tắc của chính dự án (`Button.jsx`): *"Nút mờ mà không nói vì sao là chỗ người
dùng đứng lại lâu nhất: họ không biết còn thiếu gì."*

### 4e.4 Bản sửa

**Siết ngưỡng CỤC BỘ**: `inpaint_verify_min_chars = 2`. Thêm `dem_ky_tu_co_nghia()` **riêng**,
**không** đụng `has_meaningful_text` — hàm đó còn dùng cho `needs_manual` của bước OCR, nơi một ký
tự đọc được VẪN là chữ thật. Hai câu hỏi khác nhau thì hai hàm khác nhau.

**Ghi lại bằng chứng**: `leftovers` nay mang `vùng N: '<chữ>'`, vào cả dòng log kết thúc lẫn kết
quả job (`text_left_evidence`). Vùng đọc được chữ nhưng **dưới** ngưỡng cũng được log ở mức info —
nếu ngưỡng đặt sai thì đó là chỗ duy nhất nhìn ra.

**Đánh đổi đã ghi thành test, không giấu:** ngưỡng 2 **bỏ sót chữ thật dài một ký tự** — "Ừ" là
một từ tiếng Việt hoàn chỉnh, và truyện tranh hay có tiếng thốt một chữ.
`test_DIEM_MU_da_biet_chu_that_MOT_ky_tu_bi_bo_sot` chốt điểm mù này lại. Vì sao vẫn chấp nhận:
bỏ sót nghĩa là một nét chữ đơn có thể còn lại — mà bước căn chữ vẽ chữ dịch đè lên **chính vùng
đó** nên gần như luôn bị che; còn gắn cờ oan 29% số trang thì dạy người dùng phớt lờ cờ, hỏng luôn
cả những lần đúng.

Hiệu quả trên chính dữ liệu đã đo: **11/11 vùng oan bị lọc ⇒ 7 trang gắn cờ về 0**.

### 4e.5 Chưa làm

- **Chưa live-verify chiều "vẫn bắt được chữ thật"** trên production: trong 24 trang không có vùng
  nào sót ≥2 ký tự, nên không có ca dương tính thật để kiểm. Chỉ có unit test.
- Bằng chứng mới vào **log và kết quả job**, chưa vào CSDL ⇒ **giao diện vẫn chưa chỉ được vùng nào
  cần soi**. Nối vào lớp đánh giá `RegionQualityAssessment` (E12) là slice riêng: nó cần quyết định
  bước xoá chữ có được ghi vào lớp giải thích của E12 hay không.

## 4f. Câu hỏi KHỞI ĐẦU của E23, nay đã trả lời được

`REPORT_E25 §6` ghi "24 trang ≈ 54 phút" là ngoại suy tuyến tính từ 6 trang. E23 sinh ra để kiểm
con số đó, nhưng §10 phải ghi "thời gian của lượt này **không dùng được**" vì có 3 cú OOM kill,
nhiều lần bấm resume, và các quãng mẻ đứng im.

**Thời gian TƯỜNG thì hỏng, nhưng thời gian MÁY LÀM VIỆC nằm sẵn trong bảng `job`.**

### 4f.1 Phải lọc bão thử lại trước

Đếm số lần mỗi trang chạy mỗi bước cho thấy tổng gộp bị thổi phồng — và nó định lượng luôn cái giá
của chính các lỗi đã sửa ở §4b-4e:

| Bước | 1 lần | 2 lần | 3-4 lần | 8 lần | 16 lần |
|---|---|---|---|---|---|
| detect | 23 | 1 | | | |
| ocr | 21 | 3 | | | |
| inpaint | 21 | 1 | 2 | | |
| translate | 20 | 2 | | 2 | |
| typeset | 9 | 11 | 3 | | **1** |

Một trang chạy typeset **16 lần** (đúng trang thiếu `_clean.png`, §4b), hai trang translate 8 lần,
hai trang inpaint 4 lần (§4d). Tổng gộp thời gian job: **75,7 phút** — trong đó phần lớn là làm
lại vô ích.

### 4f.2 Và phải dùng TRUNG VỊ, không dùng trung bình

Lọc còn các trang chạy **đúng một lần** mỗi bước rồi tính trung bình vẫn lệch: bước `ocr` có một
job **595,7 giây** trong khi min là **3,0 giây**. Một ngoại lệ như vậy kéo trung bình từ 13,9 lên
60,6. Dữ liệu lệch thế này thì trung vị mới là con số đại diện.

| Bước | Trung vị | p90 | E25 (6 trang) |
|---|---|---|---|
| inpaint | 44,2s | 96,0s | 50,7s |
| detect | 41,7s | 51,8s | 61,7s |
| ocr | 13,9s | 37,6s | 14,7s |
| dịch | 4,6s | 8,5s | 4,2s |
| căn chữ | 2,9s | 4,1s | 2,7s |
| **tổng/trang** | **107,3s** | **198,0s** | 134,0s |

### 4f.3 Trả lời: ~54 phút là ĐÚNG, và đó là TRUNG VỊ chứ không phải bảo đảm

```
local  : 107,3s × 24 = 42,9 phút
× 1,25 (hệ số production, §7: local nhanh hơn vì detect 36-41s so với 50,6s)
production ≈ 53,6 phút
```

`REPORT_E25` ngoại suy độc lập từ 6 trang ra **53,6 phút**. Hai phép đo khác nhau, trên hai bộ dữ
liệu khác nhau, ra cùng một con số. Con số 54 phút **đứng vững**.

Nhưng phải nói thêm phần mà ngoại suy cũ không nói: **p90 cho 198s/trang ⇒ ~79 phút local ⇒ ~99
phút production**. Tức 54 phút là trường hợp điển hình, còn một chapter nhiều trang nặng có thể
gần **100 phút**. Hứa "khoảng một tiếng" là đúng; hứa "54 phút" là hứa quá.

### 4f.4 Vì sao KHÔNG chạy lại một lượt sạch

Bàn thử không đủ chỗ, và đo được chứ không phỏng đoán:

```
/sys/fs/cgroup/memory.stat   anon 6,07 GiB (không thu hồi được) · file/cache 2,40 GiB
/sys/fs/cgroup/memory.max    10 GiB
⇒ chỗ thật còn ≈ 3,9 GiB   vs   đỉnh pipeline 3,71 GB
```

Biên ~200MB, mà bộ nhớ phía IDE (pyrefly ~1,1GB, node ~1,1GB) dao động liên tục — đó chính là lý
do lượt trước bị giết 3 lần. Chạy lại 50 phút để nhiều khả năng lấy thêm một con số hỏng nữa là
đốt thời gian. Trả lời bằng dữ liệu đã có thì vừa rẻ hơn vừa không kém tin cậy hơn.

Muốn một lượt sạch thì cần host có **≥6 GiB trống**, không phải bàn thử này.

## 5. Lỗi 7 — job detect trùng: ĐÃ THỬ SỬA HAI CÁCH, BÁC BỎ CẢ HAI

**Hiện tượng:** 25 job detect cho 24 trang. Một trang (`0bc631f8`) chạy detect hai lần.

**Nguyên nhân:** bộ điều phối chọn bước kế tiếp theo **trạng thái TRANG**, nhưng trang chỉ chuyển
`queued → detecting` khi worker *bắt đầu* chạy. Trong cửa sổ giữa "upload đã xếp job detect" và
"worker bắt đầu", trang vẫn `queued` nên mẻ thấy còn thiếu detect và xếp job thứ hai.

**KHÔNG hỏng dữ liệu.** Log lần thứ hai cho `replaced_regions: 9` và trang đó có đúng **9** vùng,
không phải 18 — logic thay vùng cũ chạy đúng. Thiệt hại: **~40s công vô ích trên ~45 phút ≈ 1,5%**.

**Cách 1 — chặn ở bộ điều phối** (bỏ qua nếu đã có job chưa xong): test đỏ ngay
`test_chi_day_dung_so_trang_song_song` — *"đẩy 0 việc, đáng lẽ 2"*. Vì `du_an` upload qua API và
upload **tự tạo job detect thật**, phép canh chặn mẻ đẩy việc cho **mọi** trang, tức đổi hẳn ngữ
nghĩa "ai điều phối sau upload".

**Cách 2 — `day_viec_buoc` idempotent** (thấy job còn sống thì trả lại id đó, không tạo row mới):
ngữ nghĩa mẻ không đổi, đường thu hồi mồ côi vẫn an toàn (nó đánh job cũ `failed` *trước* khi xếp
lại, nên phép canh không thấy job sống). Nhưng nó **tạo một chế độ kẹt mới**: nếu task của job
`queued` kia đã mất (broker flush), tái dùng job mà không `apply_async` nghĩa là **không bao giờ có
ai chạy nó** ⇒ trang kẹt vĩnh viễn. Trước bản sửa, mẻ đẻ job thứ hai và trang vẫn chạy được.

**Quyết định: KHÔNG sửa.** Đổi 1,5% thời gian lấy một chế độ kẹt mới, trong đúng subsystem có lịch
sử lỗi treo đã phải sửa nhiều lần (`TEST_LOG § M9`: "mẻ đứng im", "mẻ báo 3/3 hoàn thành" trong khi
một trang còn kẹt), là cân không đáng. Cả hai nhánh code đã **revert sạch**
(`git diff` xác nhận `dispatch.py` và `orchestrator.py` về nguyên trạng); batch test 41/41 xanh
lại.

Sửa cho đúng cần trả lời câu "sau upload thì ai điều phối" — đó là một mini-spec riêng, không phải
một bản vá.

## 6. Số đo bộ nhớ — phát hiện quan trọng nhất của E23

| Mốc | RSS đỉnh | % ngân sách production (3950MB) |
|---|---|---|
| phút 1-9 (detect) | 1277,8MB | 32% |
| phút 18,8 (LaMa nạp) | 1912,5MB | 48% |
| phút 43 (inpaint) | 2575,3MB | 65% |
| phút 51,5 (inpaint) | **3323,0MB** | **84%** |

**Đây là con số đáng lo.** Ở production, container 4096MB chứa cả uvicorn (~110MB lúc rảnh) lẫn
worker ⇒ 3323 + 110 = **3433MB ≈ 84% của 4096MB**, **và vẫn đang leo** khi bị cắt. Nó không nói
production *sẽ* OOM, nhưng nó nói khoảng an toàn đã mỏng hơn nhiều so với hình dung từ lượt 6
trang (đỉnh 1219MB ≈ 31%). Đây là lý lẽ mạnh nhất để xem lại quyết định giữ 4096MB ở E25 §2.6 —
quyết định đó dựa trên số đo 6 trang, mà 6 trang **không** chạm tới bước inpaint hàng loạt.

Cơ chế nhả model **có** hoạt động: `RSS 1927.6 MB vượt ngưỡng 1500 MB — đã nhả model detector,
còn 1010.6 MB`.

### 6.1 Ai giết worker — và vì sao bàn thử này không đo được bộ nhớ cho production

Hai cú SIGKILL, không phải một: **09:36:06** (`ForkPoolWorker-1` pid 8, đang detect) và
**10:10:51** (`ForkPoolWorker-2` pid 245, đang inpaint). Container local **không** có giới hạn RAM
và host còn 28,9GB rảnh — nên thoạt trông vô lý. Thủ phạm là **trần cgroup của chính workspace**:

```
/sys/fs/cgroup/memory.max      10737418240   = 10 GiB
/sys/fs/cgroup/memory.current   9354854400   =  8,7 GiB (87%)
/sys/fs/cgroup/memory.events    oom 2256 · oom_kill 99
```

Cả workspace dùng chung 10 GiB: VS Code server, node, pyrefly (~1,0GB), claude, DinD, Postgres,
Redis, và worker. Worker ~2,4-3,3GB là miếng to nhất nên kernel chọn nó. `free -m` báo RAM của
**host** (64GB) nên không thấy trần này — đó là chỗ dễ chẩn đoán sai nhất.

⇒ **Bàn thử này không đo được câu "production có OOM không".** Nó giết worker ở nơi production
(4096MB riêng) sẽ không giết. Số RSS đỉnh vẫn dùng được (đó là nhu cầu thật của workload), nhưng
**các cú giết thì không đại diện**, và tổng thời gian của lượt chạy thì vô giá trị.

Muốn trả lời câu OOM cho production thì phải chạy trên production, hoặc trên một host Docker cho
bó `mem_limit` (§2).

Đang leo, và lượt chạy chưa xong ⇒ **chưa được kết luận** "production an toàn". Đây là số quan
trọng nhất còn phải theo nốt.

**Khiếm khuyết trong script theo dõi của tôi:** điều kiện in cũ (`rss > dinh_rss - 1`) im lặng
**đúng lúc RSS tụt xuống**, làm mất dấu 9,5 phút — che chính cái vết lõm đáng xem. Đỉnh vẫn đáng
tin (theo dõi đơn điệu). Đã sửa: in khi có thay đổi thật **hoặc** cứ 2 phút một dòng, kèm cả đáy.

## 7. Đính chính một phát biểu của tôi

Tôi đã nói với người dùng: *"local ≈ production vì pipeline không scale theo core"*. Đo thật thì
Celery ăn **762% CPU** (~7,6 core) và detect ở đây mất **36-41s** so với **50,6s** trên production
⇒ local nhanh hơn **~1,25×**. Con số đó *khớp* đường cong 1,19× của E25 nên không mâu thuẫn, nhưng
nó nghĩa là **thời gian đo ở local phải nhân ~1,25 mới ra production**, không dùng trực tiếp.

## 8. Changed Files

| Tệp | Việc |
|---|---|
| `deploy/docker-compose.yml` | `--concurrency=1` → `--pool=solo` (khớp production) |
| `deploy/docker-compose.e23-mem.yml` | **MỚI** — bó RAM cho khớp production; ghi rõ DinD không chạy được |
| `backend/tests/test_worker_pool_config_unit.py` | **MỚI** — 3 test khoá bất biến pool |
| `backend/scripts/chay_e23_quy_mo_that.py` | **MỚI** — runner + theo dõi RSS/tiến độ |
| `frontend/src/components/BatchPanel.jsx` | Nói rõ ô đếm là "hết mọi bước" + chú thích khi đứng 0 |
| `frontend/src/components/BatchPanel.test.jsx` | **MỚI** — 5 test |
| `backend/app/services/reconcile.py` | Thêm `sua_mot_trang_mat_anh_clean()` — bản một-trang, dùng lại luật lùi có sẵn |
| `backend/app/workers/tasks.py` | `_lui_neu_mat_anh_clean()` + gọi nó trước khi căn chữ |
| `backend/tests/test_e23_typeset_mat_anh_clean.py` | **MỚI** — 6 test |
| `backend/app/workers/hoi_phuc.py` | Quét mồ côi đánh hỏng cả `BatchItem` trỏ vào job đã kết thúc |
| `backend/tests/test_hoi_phuc_integration.py` | +8 test (`TestMucMeTroVaoJobMoCoi`) |
| `backend/app/services/inpaint/lama.py` | `_kiem_ngan_sach_bo_nho()` — báo hỏng trước khi chạy, kiểm ô cắt lớn nhất |
| `backend/app/core/config.py` | `inpaint_gb_per_mpx` (1,28 — đo lại ở E23) + `inpaint_mem_budget_gb` |
| `backend/tests/test_inpaint_lama_unit.py` | +6 test (`TestNganSachBoNho`) |

Không migration. Không đổi hợp đồng API. Không đổi giá trị enum nào.

## 9. Tests

```
$ cd backend && pytest tests/test_batch_integration.py -q      41 passed
$ pytest tests/test_worker_pool_config_unit.py tests/test_broker_config_unit.py -q   7 passed
$ cd frontend && npm test -- --run                             361 passed (23 file)
```

Toàn bộ suite backend **chưa chạy lại** — máy đang chạy E23 (load average ~19) nên một lượt đầy sẽ
chậm và dễ đỏ giả vì hết giờ. Code backend **không đổi** nên bề mặt ảnh hưởng chỉ là tệp test mới;
vẫn phải chạy đủ trước khi đóng E23.

## 10. Remaining Limits

- ~~Câu hỏi khởi đầu chưa trả lời được~~ — **ĐÃ TRẢ LỜI ở §4f**: trung vị 107,3s/trang, ×24×1,25
  = 53,6 phút trên production, khớp với ngoại suy độc lập của E25. Thời gian **tường** của lượt
  chạy vẫn không dùng được (3 cú OOM kill + bão thử lại), nhưng thời gian **máy làm việc** thì lấy
  được từ bảng `job`.
- Chưa chạy được một lượt **sạch** để đo trực tiếp: bàn thử chỉ còn ~3,9 GiB trống (anon 6,07 GiB
  trên trần 10 GiB) so với đỉnh pipeline 3,71 GB — biên ~200MB. Cần host có ≥6 GiB trống (§4f.4).
- **Bản sửa pool chưa được kiểm live.** Khởi động lại worker để áp `--pool=solo` sẽ kích hoạt
  `worker_ready` và quét mồ côi — vừa áp bản sửa vừa chứng minh nó — nhưng làm giữa lượt chạy sẽ
  phá nốt phép đo. Để sau khi E23 dừng.
- Không bó được RAM (§2) ⇒ hành vi hồi phục sau OOM **vẫn chưa quan sát được** trên bàn thử nào.
- Toàn bộ đo trên **trang tiếng Anh** (PaddleOCR). Chapter tiếng Nhật dùng `manga_ocr` với chi phí
  nạp model lớn hơn hẳn.
- 1 trang ra `inpaint_needs_review` — chưa soi vì sao.
