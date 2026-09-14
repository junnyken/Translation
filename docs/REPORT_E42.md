# REPORT E42 — không đẩy job trùng cho cùng một trang

**Ngày:** 2026-09-14 · **Trạng thái:** mã xong, 16/16 test riêng xanh, chờ bộ đầy đủ rồi deploy

## Summary

Một trang từng bị **dịch 2 lần** (lãng phí 959 token đo trên production) và **căn chữ 4 lần** cho
đúng cùng một nội dung. Nguyên nhân: `PageStatus` chỉ có **một** trạng thái đang-chạy, nên hai bộ
đẩy việc độc lập (auto-chain và mẻ) cùng đẩy bước kế tiếp. Thêm một phép chắn đặt ở **đúng các
đường tự động**, dùng lại ngưỡng mồ côi E22 đã có.

## Audit Before Build

### Hiện tượng — hai bộ dữ liệu độc lập

Production (E35, trang `a744aede`, 21 vùng):

```
translate  2 job · token_cost 935 + 959 = 1894    -> lãng phí 959 token (51%)
typeset    4 JOB · mỗi lần "xoá 21 kết quả cũ" rồi ghi lại y hệt
inpaint    2 job
07:14      job inpaint CŨ nổ ra sau 24 PHÚT, bị chặn đúng:
           precondition_failed: page đang ở 'typeset_done', cần 'ocr_done'
```

DB dev, 38 trang:

| bước | job/trang | có trạng thái đang-chạy? |
|---|---|---|
| typeset | 2,92 | không |
| translate | 1,68 | không |
| inpaint | 1,42 | không |
| ocr | 1,13 | không |
| **detect** | **1,11** | **có** (`detecting`) |

**Xếp hạng này chính là phép kiểm chứng cho nguyên nhân.** `detect` là bước duy nhất có trạng thái
đang-chạy và nó trùng ít nhất. Nếu nguyên nhân là thứ khác thì không có lý gì thứ tự khớp đúng vậy.

### Nguyên nhân gốc — đọc mã

```
OCR xong -> Page.status = ocr_done, commit
  auto-chain đẩy inpaint                       tasks.py
  mẻ tick, đọc thấy ocr_done -> đẩy inpaint    orchestrator.py
  status VẪN ocr_done tới khi inpaint XONG -> mọi tick đẩy thêm một cái
```

`buoc_cho_trang` suy bước kế tiếp từ `Page.status`. Chú thích của nó nói rõ `detecting` trả `None`
*"có chủ đích: trang đang chạy dở"* — nhưng bốn bước còn lại không có trạng thái tương đương.

### Điều audit tìm ra và nó ĐỔI thiết kế

Có **22 chỗ tạo `Job`**, nhiều chỗ theo **vùng** (`page_id=region.page_id`).
`enqueue_refit_after_retranslate` tạo một job `typeset` cho **mỗi vùng** và gọi `run_refit_job`
(khác `run_typeset_job`). Dịch lại 16 vùng ⇒ 16 job, **đúng thiết kế** — đó chính là trang "16 job"
trong số đo.

⇒ **`typeset 2,92` KHÔNG phải toàn bộ là lãng phí**, và một luật chắn toàn cục theo (trang, loại)
sẽ làm vùng thứ hai không được căn lại chữ: bản dịch mới nằm trong CSDL mà ảnh vẫn của bản cũ —
đúng thứ hàm đó sinh ra để tránh.

## Design Choice

### Nơi đặt chắn quan trọng hơn luật chắn

| chỗ | có chắn? | vì sao |
|---|---|---|
| `day_viec_buoc` (mẻ) | **có** | nguồn trùng chính; bỏ một tick là **tự lành** — tick sau, job kia xong thì `Page.status` đã đổi |
| `enqueue_ocr_after_detect` | **có** | thuần tự động |
| `enqueue_inpaint_after_ocr` | **có** | mỗi lượt trùng ≈ 40s |
| `enqueue_translate_after_inpaint` | **có** | **đắt nhất**: 959 token/lượt trùng (`_after_ocr` gọi vào đây) |
| `enqueue_typeset_after_translate` | **không** | typeset 1,7s; chắn nó có thể bị job refit đang bay làm kẹt trang ở `translated` |
| `enqueue_refit_after_retranslate` | **không** | theo VÙNG, nhiều job cùng trang là đúng |
| 15 đường trong `routes.py` | **không** | bấm "chạy lại" mà không có gì xảy ra thì tệ hơn một job trùng |

### Ngưỡng mồ côi: dùng lại, không bịa

`job_chua_ket_thuc` coi là còn sống khi `queued`, hoặc `running` mà chưa quá
`nguong_qua_han_giay(loai)` — hàm E22 suy từ `*_timeout_seconds` đã cấu hình + 20s (= 2 lần chu kỳ
restart của `deploy-start.sh` cộng thời gian Celery kết nối lại, đo trong log thật).

Quá ngưỡng ⇒ cho đẩy lại. Không có nhánh này thì **một lần worker chết sẽ chặn trang đó vĩnh
viễn** — và worker vừa chết 2 lần trong ngày (E41), nên đây không phải ca lý thuyết.

**Sửa một hiểu sai của chính tôi.** Lúc đề xuất việc này tôi viết rằng `Job.heartbeat_at` phân
biệt được *"đang chạy với nhịp tim còn mới"* với *"mồ côi"*. **Sai:** nó chỉ được ghi MỘT LẦN lúc
job bắt đầu (`danh_dau_dang_chay`, `tasks.py:308`), nên tương đương `started_at`. Nếu tôi thiết kế
theo hiểu sai đó thì phép nhận mồ côi sẽ không bao giờ kích hoạt.

## Changed Files

| Tệp | Việc |
|---|---|
| `backend/app/services/job_status.py` | thêm `job_chua_ket_thuc` — một nguồn sự thật, đặt cạnh `nguong_qua_han_giay` đã có |
| `backend/app/workers/tasks.py` | chắn ở 3 hàm nối chuỗi (ocr · inpaint · translate) |
| `backend/app/services/batch/dispatch.py` | chắn ở `day_viec_buoc` |
| `backend/tests/test_e42_job_trung_integration.py` | **mới**, 16 test |
| `docs/{ARCH,FEATURES,TEST_LOG}.md` | ARCH §E42 · bảng tính năng · nhật ký test |

## New API / DB / State

Không có. Không endpoint mới, không trường mới, **không migration**, không trạng thái mới. Chắn
chỉ đọc `Job` và trả về bản ghi đang có.

## Tests

`16 passed`, `pytest_exit=0`.

Điều đáng nói là phép **chống rỗng nghĩa làm thành test thường trú** thay vì chứng minh bằng tay:

| test | canh gì |
|---|---|
| `test_TAT_chan_thi_ra_HAI_job` | tắt chắn ⇒ phải ra **2** job. Nếu vẫn 1 thì test kia xanh vì lý do khác |
| `test_TAT_chan_thi_me_cung_day_trung` | cùng việc đó cho đường của mẻ |
| `test_BAT_chan_thi_me_chi_day_MOT_lan` | bật chắn ⇒ đúng 1 |
| `test_job_mo_coi_thi_VAN_day_lai_duoc` | chống rỗng nghĩa **chiều ngược** — chắn không được thành khoá vĩnh viễn |
| `test_refit_hai_VUNG_khac_nhau_van_ra_HAI_job` | ranh giới suýt sửa sai: đường theo vùng không bị chặn |

**Một lỗi trong test của tôi, không phải lỗi mã sản phẩm:** hai test đường-mẻ đỏ lượt đầu với
`Connection to Redis lost: Retry (0/20)`. Fixture `no_broker_for_chained_ocr` của conftest chỉ chặn
`.delay`, còn `day_viec_buoc` đẩy bằng `apply_async`. Thêm fixture `khong_goi_broker`. Nếu tin
"đỏ = mã sai" thì đã đi sửa sai chỗ.

## Live Verification

`NULL` — chờ deploy. Không có trường tự chứng cho việc này (chắn không đổi schema), nên cách kiểm
là **đếm lại job trên một chapter thật** sau khi deploy:

```
chạy một chapter -> so job/trang với mốc trước:  translate 1,68 · inpaint 1,42
kỳ vọng: cả hai về ~1,0 với các trang chạy tự động
```

Và tìm dòng log `E42: trang ... đã có job ... — không đẩy trùng`.

## Remaining Limits

1. **Giảm trùng, KHÔNG loại tuyệt đối.** Chắn đọc rồi ghi mà không khoá; hai tiến trình đẩy đúng
   cùng thời điểm vẫn có thể không thấy job của nhau. Muốn tuyệt đối cần khoá tầng CSDL
   (`SELECT ... FOR UPDATE`, hoặc ràng buộc duy nhất một-phần trên `(page_id, type)` khi
   `status in (queued, running)`) — chưa làm, vì cần migration và sẽ đụng cả các đường theo vùng
   **được phép** trùng.
2. **`typeset` vẫn không chắn ở đường auto-chain.** Là lựa chọn có chủ đích (1,7s + nguy cơ kẹt
   trang vì refit), nhưng nghĩa là tỉ lệ 2,92 sẽ **không** về 1,0 sau lượt này.
3. **Nguyên nhân gốc vẫn chưa được chữa.** Chữa đúng gốc là thêm trạng thái đang-chạy cho bốn
   bước còn lại (`PageStatus`), để `buoc_cho_trang` tự biết. Việc đó cần migration enum, sửa ánh
   xạ giao diện và nhiều test — **chưa mở**. E42 là lớp chắn ở cửa, không phải bản chữa gốc.
4. **Chưa đo lại trên production.** Con số "về ~1,0" là kỳ vọng, chưa phải số đo.
