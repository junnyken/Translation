# PRODUCTION-04 — durable first-detect dispatch

Ngày 28/10/2026. **BUILT một phần, chưa LIVE; chưa nghiệm thu tích hợp.**

## Summary

Lượt upload riêng có request_key lưu DetectOutbox cùng page/quota/key/Job.
API thử gửi sau commit; beat và worker-ready gửi lại intent chưa được broker nhận.
Không tạo trang/job hay trừ quota mới khi gửi lại. Không mở rộng sang các bước pipeline sau.

## Audit Before Build

PRODUCTION-03 chống upload trùng nhưng còn cửa sổ commit thành công rồi chết trước dispatch.
Celery task_id cố định không chống thực thi trùng. Wrapper detect cũ có thể sửa kết quả và
phát callback thất bại cả khi nhận bản tin trùng. File deploy-start.sh đã có thay đổi của user,
không sửa script hoặc giả định topology solo trong phần nâng cấp này.

## Design Choice

Publisher khóa outbox FOR UPDATE SKIP LOCKED xuyên publish/commit. Giao ít nhất một lần;
consumer claim queued→running bằng UPDATE có điều kiện, đặt start/heartbeat cùng giao dịch.
Duplicate/stale thoát trước provider/callback/failure handler; intent abandoned không được claim.
DB claim lỗi thử lại không giới hạn, backoff 30→300 giây, chưa gọi AI. Broker gửi lỗi tối đa
8 lần (30→300 giây); sau đó cần operator xem và reset. Không tự chạy lại job running/failed/done.
Review độc lập đã tìm và sửa retry claim hữu hạn gây kẹt job và claim intent abandoned.

## Changed Files

- models, migration 0038_detect_outbox, routes keyed upload, dispatch optional task_id.
- services/outbox_policy.py, upload_outbox.py; workers/tasks.py, celery_app.py.
- isolated tests policy/wrapper, integration upload tests và conftest; tài liệu liên quan.

## New API/DB/State

Không thêm HTTP endpoint/field. CLI nội bộ: `python -m app.services.upload_outbox status --limit 20`
và `python -m app.services.upload_outbox retry JOB_UUID` (chỉ intent hết lần gửi, chưa published,
chưa abandoned, Job/Page queued). Chạy trong thư mục backend, đúng env DB của worker.
Migration 0038 phải áp dụng trước khi API/worker mới chạy. Không backfill job cũ.
Beat schedule `production.dispatch_upload_outbox` mỗi 30 giây, giữ lịch cleanup hiện có.
Cần đúng một beat scheduler: worker có `-B` hiện có hoặc tiến trình
`celery -A app.workers.celery_app:celery_app beat`; không chạy cả hai.
Không triển khai hoặc chạy các lệnh vận hành này trong phiên này.

## Tests

- Desktop: **102 passed**.
- Isolated: **32 passed**, 2 cảnh báo config pytest asyncio plugin chưa có.
- Policy kiểm backoff, due, exhaustion, lỗi publish, replay sau mất commit; wrapper thật được
  trích AST để kiểm duplicate và claim-error không gọi provider/callback. Đây là dependency
  injection, không phải kiểm broker, SQL locking hoặc scheduling thật.
- Integration có bổ sung concurrent claim, abandoned rejection, published reset rejection,
  durable retry assertions. **Chưa chạy được**: thiếu asyncpg khi load conftest.
- Python compile và scoped whitespace check thực hiện; migration chưa áp dụng.

## Live Verification

Chưa có. Chưa kiểm PostgreSQL concurrency/migration, broker crash/replay, worker thật,
provider, Windows hoặc đơn hàng thực tế. Không commit/deploy/phát hành ZIP công khai.

## Remaining Limits

Published chỉ có nghĩa broker đã nhận; broker mất dữ liệu sau ACK vẫn cần đối soát vận hành.
Không có full generation fencing, lease phục hồi worker đang chạy, outbox downstream,
provider exactly-once/cost ceilings, status outbox trên giao diện hoặc orphan-file sweeper.
Claim DB retry cũng cần broker còn giữ được bản tin retry. Kiểm tra tích hợp là điều kiện
trước khi dùng cho đơn hàng trả tiền; không đánh dấu P1 hoàn tất.


## Bổ sung kiểm thử 28/10/2026

43 isolated tests đạt, gồm 11 case bảo vệ DB test trước downgrade/TRUNCATE.
Bổ sung integration concurrent publisher và publish accepted→commit failed→replay/claim.
Các integration chưa chạy: thiếu asyncpg; cài dependency bị chặn mạng và approval review503.
Runner: `bash scripts/test_production_backend.sh`; hướng dẫn [TEST_PRODUCTION_BACKEND.md](TEST_PRODUCTION_BACKEND.md).
Không deploy hoặc xác nhận broker/worker thật.


### Bộ chạy nghiệm thu cách ly — 28/10/2026

Thêm Dockerfile.integration, deploy/docker-compose.production-tests.yml và
scripts/test_production_docker.sh: DB tmpfs riêng, không port/.env/volume app,
network internal, exit code test được giữ khi dọn tài nguyên. Docker compose config,
Bash syntax đạt; isolated tests vẫn43 đạt. Thử chạy bị chặn Docker socket; lần xin
tải dependency tiếp tục không thực thi do approval review503. Chưa build hoặc chạy
PostgreSQL/broker. Xem TEST_PRODUCTION_BACKEND.md.


### Log tích hợp người dùng gửi — 28/10/2026

Log Docker do người dùng cung cấp: **19 passed, 7 failed trong 14.75s**.
Năm failure do counts đã thêm DetectOutbox (6 bảng) nhưng expected còn5 bảng.
Hai failure do fault injection kiểm UploadRequest trong session.new sau khi đã flush,
nên không gây lỗi commit như dự định. Đã cập nhật expected đủ6 bảng; fault injection
truy vấn đúng request_key trong transaction, thêm assert xác nhận fault đã kích hoạt.
Không giảm yêu cầu rollback/chống trùng, không thay logic ứng dụng theo các failure này.
Compile và43 isolated tests đạt sau sửa. **Chưa có kết quả Docker chạy lại sau bản sửa**;
không đánh dấu integration pass. Chạy lại `bash scripts/test_production_docker.sh`.


### Xác nhận chạy lại từ log người dùng — 28/10/2026

Log người dùng cung cấp ghi `26 passed in 13.93s`, `tests-1 exited with code 0`
(project translation-integration-t6uwym). Toàn bộ26 test API/PostgreSQL trong bộ chạy
production đã đạt sau sửa test. Có kiểm migration trên PostgreSQL test, upload idempotency,
rollback/reconciliation và outbox SQL claim/publish giả lập. Broker/provider vẫn giả lập;
chưa xác nhận Redis/Celery/AI hoặc Windows end-to-end, chưa deploy/LIVE.
Bằng chứng: attachment84df740c-00a7-4fde-9bb7-dbbd636558e1/Pasted text.txt do user gửi.


### Bổ sung phép kiểm broker — 28/10/2026

Thêm Redis tạm vào stack test và2 case Celery worker thật (threads/concurrency2):
duplicate trong lúc xử lý/sau hoàn tất và outbox→Redis→consumer claim. Provider/callback
được thay ở ranh giới kiểm thử; startup hooks được cô lập. Đã compile/config validation,
43 isolated đạt; 2 case broker mới CHƯA CHẠY do quyền Docker trong agent. 26 case SQL/API
cũ đã đạt theo log user. Chưa kiểm beat/restart/AI thật/Windows hoặc deploy.
Hướng dẫn và tiêu chí ảnh mẫu: TEST_PRODUCTION_BACKEND.md.


### Log Redis/Celery người dùng gửi — 28/10/2026

Project translation-integration-uekhlp: **27 passed, 1 failed trong27.42s**.
Test duplicate đang chạy/sau hoàn tất đã đạt với Redis/Celery thật. Test outbox đã
publish và worker nhận thành công, lỗi tại đọc persisted published_at từ session
fixture giữ row cũ (expire_on_commit=False; rollback khi không còn transaction
không expire cache). Đã đổi xác nhận sang AsyncSession mới, vẫn yêu cầu published_at
khácNULL. Chưa có log chạy lại sau sửa; chưa đánh dấu28/28.
Bằng chứng: attachment87953237-4117-40ab-8c1f-70ef002bca41/Pasted text.txt do user gửi.


### Kết quả xác nhận cuối từ người dùng — 28/10/2026

Log attachment cdd91401-2be6-4fc1-b63c-7739068c1b11/Pasted text.txt ghi
**28 passed in 27.65s**, `tests-1 exited with code 0`. Bộ test API/PostgreSQL
và2 test Redis/Celery thật đã đạt. Xác minh duplicate đang chạy/sau hoàn tất và
outbox publish→consumer claim trong môi trường cách ly, provider/callback giả lập.
Chưa kiểm beat, process/broker restart, OCR/dịch thật, Windows hoặc deploy/LIVE.
Kết quả này thay thế trạng thái chờ chạy lại của các mục log trước đó.
