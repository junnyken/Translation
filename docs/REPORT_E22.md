# Báo cáo Mini-Spec E22 — Worker Memory/OOM: bản THU HẸP theo audit

**Project:** Translation · **Phase:** E — Hosted Reliability Hardening
**Ngày:** 2026-09-09 · **Nền:** sau E21/E21-LV

## 1. Summary

Test B&W tiếng Nhật (`manga_ocr`) trên production lộ ra 1 sự kiện worker bị `SIGKILL` (exit 137)
lúc 07:17 — worker tự phục hồi sau 10s, không ảnh hưởng tới test đang chạy lúc 07:39. Người dùng
đưa ra bản nháp mini-spec E22 đầy đủ (bảng `JobAttempt`, lease/heartbeat, Redis capacity-gate,
watchdog định kỳ, retry policy tự động — lấy mẫu từ một playbook hạ tầng tổng quát).

**Audit trước khi viết dòng code nào tìm ra bản nháp gốc phần lớn ĐÃ THỪA cho topology hiện tại**
(§2). Người dùng, sau khi xem audit, chọn hướng **thu hẹp theo bằng chứng**: không build
capacity-gate/`JobAttempt`/watchdog định kỳ — chỉ sửa 2 khoảng trống THẬT còn lại (§3). Kết quả:
4 field mới trên `Job` (`heartbeat_at`, `error_class`, `exit_signal` — cột DB — và
`processing_state` — suy luận lúc đọc), 2 module mới nhỏ, 1 dòng log sửa lại cho trung thực,
1 bảng wording mới ở frontend.

**Backend 1189 passed / 6 skipped / 0 failed, frontend 322 passed.**

## 2. Audit Before Build

Ba phát hiện đổi hướng thiết kế, đọc trực tiếp code thật (không suy đoán):

| Câu hỏi | Kết quả audit |
|---|---|
| Celery worker có thể chạy 2 job AI nặng cùng lúc không? | **Không** — `deploy-start.sh:28-30` chạy `--pool=solo` (một tiến trình, không fork). Redis capacity-gate của bản nháp gốc bảo vệ một kịch bản không xảy ra được về mặt cấu trúc. |
| Đã có cơ chế nào xử lý "worker chết giữa chừng, DB không biết" chưa? | **Có, từ trước E22** — `app/workers/hoi_phuc.py` (P3j): `worker_ready` signal tự gọi `don_job_mo_coi()` mỗi lần worker khởi động lại, đánh dấu mọi `Job.status=running` thành `failed` kèm lý do đọc được, lùi `Page.status` khỏi trạng thái tạm, **không tự chạy lại**. File tự ghi rõ điều kiện đúng: "chỉ đúng khi có ĐÚNG một worker" — khớp topology E22 tự cấm đổi. |
| `Job` là "logical work" hay "1 lần attempt"? | **1 lần attempt** — mỗi lần chạy lại một stage, code tạo `Job` MỚI (không update `Job` cũ, xem 10 điểm gọi `Job(type=..., page_id=..., status=queued)` trong `tasks.py`). Theo đúng điều kiện A2 mà bản nháp gốc tự cho phép ("chỉ chọn `JobAttempt` riêng nếu `Job` hiện tại KHÔNG đại diện 1 attempt") → không cần bảng mới. |
| Idempotency khi chạy lại một stage? | Xoá-rồi-tạo-mới cho `OCRResult`/`TranslationResult`/`TypesetResult` (không phải UPDATE) — an toàn cho retry, không cần thêm gì. |
| Có pattern Redis atomic nào tái dùng được không? | Có — `app/services/batch/gate.py` (M9 Gemini rate gate) dùng Lua script sliding-window, atomic. Không dùng tới trong E22 vì không cần capacity-gate, nhưng xác nhận pattern có sẵn nếu sau này cần. |
| `worker.trang_thai` có đáng tin làm liveness signal không? | **Không** — `deploy-start.sh:74` ghi `starting` một lần lúc khởi động `ROLE=all`, không có dòng nào update thành `running` sau khi celery lên thật; chỉ update thành `restarting` khi worker THOÁT. Xác nhận đúng nghi ngờ trong bản nháp gốc. |
| Dòng log "gần như chắc chắn hết bộ nhớ" có bằng chứng platform không? | **Không** — tự suy đoán từ mã thoát 137, không có xác nhận từ VibeHost/OOM-killer log. Vi phạm chính guardrail #2 của bản nháp gốc ("không được khẳng định exit 137 = OOM khi chưa có bằng chứng"). |

Kết luận trình lên người dùng (xem hội thoại 2026-09-09): build đầy đủ theo bản nháp gốc sẽ là
code đầu cơ cho kịch bản nhiều-worker không xảy ra trong phạm vi E22 (bản nháp tự cấm đổi
topology — không tách API/worker, không tăng RAM). Người dùng chọn **"Bản thu hẹp theo bằng
chứng"**.

## 3. Design Choice

**Mở rộng `Job`, không tạo bảng `JobAttempt`.** Đúng điều kiện A2 của bản nháp gốc — audit xác
nhận `Job` đã đại diện đúng 1 attempt.

**Heartbeat chỉ giải quyết "cửa sổ nói dối", không phải "chặn concurrency".** `Job.heartbeat_at`
đặt CÙNG lúc `started_at` trong `danh_dau_dang_chay()` (điểm gọi DUY NHẤT, đã có sẵn từ E19-3,
10 nơi dùng chung — không sửa 10 nơi). `app/services/job_status.py::suy_ra_trang_thai_hien_thi()`
suy luận LÚC ĐỌC: `running` lâu hơn hẳn `*_timeout_seconds` (trần Celery `soft_time_limit` THẬT
của chính loại job đó) + 20s đệm (2 lần chu kỳ restart `sleep 10` của `deploy-start.sh`) mà không
có nhịp tim mới ⇒ `processing_state="worker_interrupted"`. **Không đổi `Job.status` trong DB** —
đó vẫn là việc riêng của `hoi_phuc.py` khi worker khởi động lại thật.

**`processing_state` tính trong `JobRead.model_validator`, không phải ở từng route.** Có 3 endpoint
trả `JobRead` (`GET /jobs/{id}`, `GET /pages/{id}/jobs`, `GET /projects/{id}/failed-jobs`), hai cái
sau trả thẳng list `Job` ORM cho FastAPI tự convert. Tính ở route riêng lẻ thì chắc chắn sót —
đặt trong `model_validator(mode="after")` của schema thì MỌI đường đều nhất quán, kể cả đường mới
thêm sau này.

**Phân loại lỗi chỉ áp dụng cho đúng 1 nơi: job mồ côi.** `app/workers/trang_thai_worker.py` đọc
lại `ma_thoat_gan_nhat` mà `deploy-start.sh` **đã ghi sẵn** vào `WORKER_STATE_FILE` từ trước E22
(không cần sửa gì thêm ở phía ghi) → phân loại: 137 → `resource_limit_suspected` (NGHI NGỜ, cố
tình không có `_confirmed`), mã khác/không rõ → `worker_lost`. `hoi_phuc.don_job_mo_coi()` ghi 2
field này. Lỗi khác (timeout, input hỏng, …) vẫn dùng `error_log` tự do như cũ — không refactor
~15 điểm `job.status = JobStatus.failed` khác trong `tasks.py` vì mỗi chỗ đã có lý do cụ thể riêng,
không phải một câu cứng chung.

**Frontend: bảng `TT_XU_LY` riêng, không gộp vào `VIEC`.** `status-presentation.test.js` khoá cứng
`VIEC` đúng 4 giá trị thật của cột `job_status` — `processing_state` không phải giá trị DB, nhét
chung sẽ phá bài test ngăn giao diện tự bịa trạng thái.

## 4. Cố tình KHÔNG làm (và vì sao)

| Không làm | Vì sao |
|---|---|
| Bảng `JobAttempt`, `lease_token`, `worker_identity` | Audit §2: `Job` đã đóng đúng vai trò "1 attempt" |
| `HeavyWorkCapacityGate` (Redis atomic) | `--pool=solo` đã đảm bảo concurrency=1 về cấu trúc; chỉ có giá trị nếu sau này tách nhiều worker |
| `StaleAttemptWatchdog` chạy định kỳ (Celery beat) | Suy luận LÚC ĐỌC đủ cho mục đích hiển thị; `hoi_phuc.py` (chạy lúc `worker_ready`) đã là cơ chế quét+sửa DB thật |
| Retry tự động cho `worker_lost`/`resource_limit_suspected` | Giữ nguyên chủ ý gốc của `hoi_phuc.py`: tự chạy lại job vừa nghi ngờ làm chết worker là cách nhanh nhất giết nó lần nữa — có bằng chứng thật (07:17), không phải giả định |
| Đổi `deploy-start.sh` để ghi thêm state mới | Đã có sẵn `ma_thoat_gan_nhat` trong `WORKER_STATE_FILE` — chỉ cần đọc lại, không cần ghi thêm |

## 5. Changed Files

**Backend:**
- `app/models/__init__.py` — `Job.heartbeat_at`, `Job.error_class`, `Job.exit_signal` (3 cột mới)
- `alembic/versions/0017_e22_job_heartbeat_error_evidence.py` — migration mới
- `app/workers/tasks.py` — `danh_dau_dang_chay()` đặt thêm `heartbeat_at`
- `app/workers/trang_thai_worker.py` — mới: đọc lại `WORKER_STATE_FILE`, phân loại mã thoát
- `app/workers/hoi_phuc.py` — `don_job_mo_coi()` ghi `error_class`/`exit_signal`
- `app/services/job_status.py` — mới: `suy_ra_trang_thai_hien_thi()` (suy luận lúc đọc)
- `app/schemas/common.py` — `JobRead` thêm 4 field + `model_validator` tự tính `processing_state`
- `deploy-start.sh` — sửa dòng log (bớt khẳng định OOM chưa có bằng chứng)

**Frontend:**
- `src/lib/status-presentation.js` — bảng `TT_XU_LY` mới (tách khỏi `VIEC`)
- `src/lib/status-presentation.test.js` — thêm `tt_xu_ly` vào `ENUM_BACKEND`
- `src/api.js` — `layLyDoDung()` nhận thêm nguồn thứ hai: job còn treo `running` mà máy chủ đánh
  giá `worker_interrupted` (job đã `failed` vẫn được ưu tiên trước)
- `src/components/chapter/ChapterProgress.jsx` — panel "Vì sao?" hiện đúng "Worker gián đoạn" thay
  vì câu nói dối cũ

**Test:**
- `backend/tests/test_e22_job_status_unit.py` — mới, 8 test đơn vị thuần
- `backend/tests/test_e22_trang_thai_worker_unit.py` — mới, 9 test đơn vị thuần
- `backend/tests/test_e22_heartbeat_integration.py` — mới, 1 test tích hợp
- `backend/tests/test_hoi_phuc_integration.py` — thêm 3 test (phân loại lỗi khi dọn mồ côi)

**Docs:** `API.md` (mục 25), `ARCH.md` (§E22), `FEATURES.md`, `TEST_LOG.md`.

## 6. New API / DB / State

**DB:** `job.heartbeat_at TIMESTAMPTZ NULL`, `job.error_class VARCHAR(64) NULL`,
`job.exit_signal VARCHAR(32) NULL` (migration `0017_e22`, không có ràng buộc NOT NULL nên không
cần `server_default`).

**API:** `GET /api/v1/jobs/{job_id}` (và `GET /pages/{id}/jobs`, `GET /projects/{id}/failed-jobs`
— cùng schema) thêm 4 field: `heartbeat_at`, `error_class`, `exit_signal`, `processing_state`.
Không đổi tên/xoá field nào đã chốt — chỉ CỘNG THÊM.

## 7. Tests

```
$ cd backend && ../.venv/bin/python -m pytest -q
1189 passed · 6 skipped · 0 failed   (1195 test thu thập được: 1176 nền E21 + 19 mới của E22)

$ cd frontend && npm test -- --run
322 passed                            (315 nền E21 + 7 mới của E22)
```

*(`pytest.ini` của repo đặt `addopts = -q` nên lượt chạy không in dòng tổng kết — số ở trên đối
chiếu từ `--collect-only` (1195) với số dấu chấm/`s` thật trong log lượt chạy đầy đủ, exit code 0.
6 test skip là các test đã skip sẵn từ trước E22, không phải test mới bị bỏ qua.)*

19 test mới của backend:
- `tests/test_e22_job_status_unit.py` (7) — suy luận `processing_state` lúc đọc: trạng thái khác
  `running` giữ nguyên; nhịp tim mới ⇒ `running`; quá ngưỡng ⇒ `worker_interrupted`; ranh giới
  đúng tại ngưỡng; job cũ chưa từng có nhịp tim KHÔNG bị suy diễn thành gián đoạn; ngưỡng khác
  nhau theo loại job; mọi `JobType` đều có ngưỡng riêng (khoá lại nếu thêm loại mới mà quên).
- `tests/test_e22_trang_thai_worker_unit.py` (8) — phân loại mã thoát (137 ⇒
  `resource_limit_suspected` chứ KHÔNG phải `_confirmed`; mã khác ⇒ `worker_lost`; không rõ ⇒
  `worker_lost`) + đọc tệp trạng thái (thiếu tệp/JSON hỏng ⇒ `khong_ro`, không raise).
- `tests/test_e22_heartbeat_integration.py` (1) — `danh_dau_dang_chay()` đặt `heartbeat_at` bằng
  đúng `started_at`.
- `tests/test_hoi_phuc_integration.py` (+3) — dọn job mồ côi ghi đúng `error_class`/`exit_signal`
  theo mã thoát thật; không có tệp trạng thái vẫn gắn `worker_lost`; chế độ chỉ-đếm KHÔNG ghi gì.

5 test mới của frontend:
- `src/components/chapter/lydodung.test.jsx` (+2) — panel "Vì sao?" khi worker gián đoạn: hiện
  "Worker gián đoạn", vẫn nói rõ BƯỚC NÀO, và **không** còn câu "đang chờ tới lượt"/"không có bước
  nào hỏng"; không dùng chữ "thất bại" (việc chưa mất).
- `src/api.test.js` (+3) — thứ tự ưu tiên: job `failed` (lý do đã chốt) thắng suy luận theo nhịp
  tim; không có job hỏng mới lấy job `worker_interrupted`; job đang chạy BÌNH THƯỜNG không bị coi
  là lý do đứng im.

Migration `0017_e22`: chạy `alembic upgrade head` thật qua container `worker`
(`docker compose run --rm worker alembic upgrade head`) — sạch, không lỗi.

## 8. Live Verification

**Màn tiêu thụ `processing_state`: panel "Vì sao?" của `ChapterProgress`.** Đây đúng là chỗ chứa
câu nói dối tệ nhất trước E22: khi worker chết giữa chừng, job còn treo `running` nên
`layLyDoDung()` không tìm thấy job `failed` nào ⇒ panel trả về **"Không có bước nào hỏng — trang
này đang chờ tới lượt."** Thật ra chẳng chờ ai cả, worker đã chết. Sau E22 panel này nói đúng:
"Bước *xoá chữ gốc*: Worker gián đoạn — đang đánh giá khôi phục… Chưa cần thao tác gì."

Chính câu nói dối đó tôi đã tự nhìn thấy trong lượt test B&W tiếng Nhật (2026-09-09) — panel hiện
"Không có bước nào hỏng — trang này đang chờ tới lượt" trong khi thật ra trang đang xếp hàng bình
thường; nếu đúng lúc đó worker chết thì câu chữ vẫn y hệt, không phân biệt được.

Sự kiện SIGKILL thật duy nhất quan sát được (07:17, trước khi E22 tồn tại) đã dùng làm bằng chứng
audit — không dựng lại fault-injection thật trên production trong mini-spec này (đúng đề nghị ban
đầu của bản nháp gốc: ưu tiên local/isolated trước, hosted chỉ khi có xác nhận riêng — và ở đây
không cần vì cơ chế cốt lõi đã có từ trước E22, không phải thứ E22 mới dựng lên).

## 9. Success Criteria

| Tiêu chí | Đạt? |
|---|---|
| Không còn job hiển thị "đang xử lý" vô thời hạn sau khi worker chết — cửa sổ rút ngắn còn đúng thời gian suy luận được (timeout thật + 20s) | ✅ (test đơn vị `test_e22_job_status_unit.py`) |
| Lý do job hỏng vì worker chết có phân loại bằng chứng, không phải một câu đoán cứng | ✅ (`error_class`/`exit_signal`, test tích hợp `test_hoi_phuc_integration.py`) |
| Không khẳng định OOM khi chưa có bằng chứng platform | ✅ (`resource_limit_suspected`, không có `_confirmed`; dòng log `deploy-start.sh` sửa lại) |
| Không đổi hành vi cũ (idempotency M2-M8, `hoi_phuc.py` không tự chạy lại, `danh_dau_dang_chay` vẫn 10 điểm gọi) | ✅ (toàn bộ regression xanh: 1189 passed, 0 failed) |
| Không build code đầu cơ cho kịch bản chưa xảy ra | ✅ (§4 — quyết định có ghi lý do, không phải bỏ sót) |
| Docs cập nhật cùng lúc | ✅ (API.md/ARCH.md/FEATURES.md/TEST_LOG.md) |

## 10. Remaining Limits

- Ngưỡng "gián đoạn" (`*_timeout_seconds` + 20s) suy từ cấu hình Celery thật, nhưng CHƯA đo bằng
  fault-injection thật có chủ đích trên production — chỉ có bằng chứng quan sát tự nhiên (07:17).
- `processing_state` mới nối vào ĐÚNG MỘT màn (panel "Vì sao?" của `ChapterProgress`) — các màn
  tiến độ khác vẫn đọc `Page.status` như cũ, chưa phân biệt được "worker gián đoạn". Đó là chủ ý:
  panel "Vì sao?" là chỗ duy nhất trước đây nói sai hẳn; các màn kia chỉ nói chung chung về bước
  đang chạy nên không sai, chỉ là chưa chi tiết.
- Nếu sau này topology đổi (nhiều worker, tách API/worker khỏi container), điều kiện an toàn của
  `hoi_phuc.py` KHÔNG còn đúng — phải làm lại đúng phần capacity-gate/lease đã audit ở đây TRƯỚC
  khi đổi topology, không phải sau. Đây là quyết định có ghi lại, không phải bị bỏ sót.
- Không đổi `worker.trang_thai` (vẫn đứng ở `starting` mãi nếu worker không chết) — ngoài phạm vi
  đã chọn của E22 thu hẹp; nếu cần fix riêng, đó là mini-spec quan sát/health khác.
