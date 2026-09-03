# Báo cáo Mini-Spec P3j — Khôi phục job mồ côi khi worker chết

**Ngày:** 2026-09-03 · **Trạng thái:** ✅ **XONG** (chưa deploy lúc viết)
**Phụ thuộc:** P3h `ĐÃ DEPLOY` · Pilot `REPORT_PILOT_UAT_001.md` §6 P1-2

## Summary

Đóng **P1 duy nhất còn mở** của pilot hosted. Worker chết giữa chừng ⇒ job đang chạy biến mất:
không tự chạy lại, **không có tín hiệu lý do**, và không có endpoint nào để tra.

Đo được trong pilot: trang 1 chapter 002 kẹt vĩnh viễn ở `ocr_done` sau khi worker bị OOM killer
giết lúc đang `inpaint`. Giao diện chỉ hiện "5/6 trang" — đúng nhưng **không đủ để hành động**.

## Audit Before Build

Ba câu hỏi phải trả lời trước khi viết một dòng nào:

| Câu hỏi | Trả lời (đo từ mã, không đoán) |
|---|---|
| Phân biệt job mồ côi với job đang chạy hợp lệ bằng cách nào? | `deploy-start.sh:26` chạy celery `--pool=solo` — **một tiến trình, một container**. Nên lúc worker khởi động, tiến trình duy nhất có thể giữ một job `running` chính là tiến trình vừa chết |
| Trạng thái page nào bị kẹt? | Quét `tasks.py`: chỉ **`detecting`** là trạng thái TẠM. `detected`/`ocr_done`/`translated`/`typeset_done` đều chỉ được đặt **khi xong**, nên vẫn trung thực dù job chết |
| Đã dùng celery signal nào chưa? | Chưa — `worker_ready` là chỗ sạch để gắn |

Câu hỏi thứ hai đổi hẳn phạm vi: **phần lớn trạng thái page KHÔNG cần lùi.** Lùi bừa `ocr_done`
về `queued` là xoá mất công việc đã hoàn thành thật — tệ hơn hẳn việc để nguyên.

## Design Choice

### Chỉ đánh dấu hỏng, **không tự chạy lại**

Tự chạy lại một job vừa làm chết worker vì hết bộ nhớ là cách nhanh nhất để giết nó lần nữa — và
lần này thành **vòng lặp**. Hệ thống nói rõ chuyện gì đã xảy ra rồi trả quyền quyết định cho
người dùng, người đang nhìn được cả bối cảnh.

### Lý do viết cho NGƯỜI đọc

```
worker_died: tiến trình xử lý bị dừng giữa chừng nên việc này không chạy xong
(hay gặp nhất là container hết bộ nhớ). Dữ liệu của bạn KHÔNG mất — bấm chạy lại
bước này hoặc 'Chạy cả chapter' là tiếp tục được.
```

Có ba phần cố ý: **chuyện gì xảy ra** · **dữ liệu còn nguyên** (câu hỏi đầu tiên của bất kỳ ai) ·
**làm gì tiếp**. Một mã lỗi trần trụi thoả mãn người viết log, không thoả mãn người đang bị kẹt.

### Ràng buộc topology — ghi thành cờ, không ghi thành lời hứa

Tính đúng đắn của cả mini-spec phụ thuộc "chỉ có một worker". Nên nó là **cờ cấu hình**
`worker_sweep_orphan_jobs_on_start`, không phải một câu trong tài liệu:

> Ngày nào chạy nhiều worker, quét kiểu này sẽ giết job đang chạy hợp lệ của worker khác. Phải
> **tắt cờ trước**, rồi đổi sang cơ chế job-có-chủ (id worker + nhịp tim).

### Dọn dẹp hỏng KHÔNG được chặn worker

`worker_ready` bọc try/except: một worker chạy được mà chưa dọn còn hơn một worker không chạy.
Cùng nguyên tắc đã dùng ở P3f (`deploy-start.sh` không để lỗi đối chiếu chặn khởi động).

## Changed Files

| Tệp | Việc |
|---|---|
| `app/workers/hoi_phuc.py` | **Mới** — `don_job_mo_coi(session, ap_dung=)` |
| `app/workers/celery_app.py` | Gắn `worker_ready`, bọc try/except |
| `app/core/config.py` | `worker_sweep_orphan_jobs_on_start: bool = True` |
| `app/api/v1/routes.py` | **Mới** `GET /pages/{page_id}/jobs` — lịch sử job, mới nhất trước |
| `tests/test_hoi_phuc_integration.py` | **Mới** — 10 test |

## New API / DB / State

- **API mới:** `GET /api/v1/pages/{page_id}/jobs` → `list[JobRead]`, mới nhất trước, `404` nếu
  không có trang. Trước P3j chỉ tra được job **theo id** — mà id chỉ có ngay lúc bấm, nên trang
  đứng im vì worker chết nhìn **y hệt** trang đang chạy chậm.
- **DB:** không đổi bảng, không migration.
- **State:** `Job.running → failed` khi mồ côi · `Page.detecting → queued`.

## Tests

```
927 passed, 6 skipped   (nền trước P3j: 917)
```

Bốn test đáng kể nhất **không** kiểm việc dọn, mà kiểm việc **không đụng vào cái không được đụng**:

| Test | Vì sao quan trọng |
|---|---|
| `test_KHONG_dung_toi_job_da_xong` | Job `done`/`failed` là **lịch sử**. Dọn dẹp mà sửa lịch sử là hỏng bằng chứng — kiểm cả việc không ghi đè `error_log` cũ |
| `test_KHONG_lui_trang_o_trang_thai_ON_DINH` | `ocr_done` là mốc đã xong thật; job inpaint chết không làm nó sai đi. Lùi bừa = xoá công việc đã hoàn thành |
| `test_KHONG_tu_chay_lai` | Khẳng định không tự xếp lại việc và không đẻ job mới |
| `test_che_do_chi_dem_KHONG_ghi_gi` | Cùng bài học P3f: chế độ khô không được dựa vào tác dụng phụ của chế độ ướt |

Thêm: lý do phải **đọc được** (kiểm có cả `"hết bộ nhớ"` lẫn `"KHÔNG mất"`), idempotent, và
endpoint trả đúng thứ tự mới-nhất-trước.

## Live Verification

⛔ **Chưa deploy lúc viết báo cáo này.** Bằng chứng hiện có là 927 test trên máy phát triển với
Postgres thật — **không phải** bằng chứng chạy thật trên VibeHost.

Cách kiểm chứng thật sau khi deploy: đọc log worker lúc khởi động (`dọn job mồ côi: …`), và gọi
`GET /pages/{id}/jobs` trên đúng trang 1 chapter 002 — trang đang kẹt từ pilot.

## Remaining Limits

- **Chỉ đúng với một worker.** Nhiều worker phải tắt cờ và đổi cơ chế (xem Design Choice).
- **Không dọn `ExportJob`** — bảng riêng, trạng thái riêng, chưa quan sát thấy mồ côi trong pilot.
  Cố ý để ngoài phạm vi thay vì làm mò.
- **Không tự chạy lại** — có chủ đích, xem Design Choice. Người dùng phải tự bấm.
- **Giao diện chưa hiện lý do**: endpoint đã có, nhưng màn hình trang chưa gọi nó. Người vận hành
  hiện vẫn phải tra bằng API. Đây là việc kế tiếp gần nhất.
- Sự cố gốc (OOM) đã sửa ở P3h; P3j chỉ giới hạn **hậu quả**, không thay thế việc đó.
