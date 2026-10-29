# Kiểm thử tích hợp các đợt Production

Chỉ chạy trên PostgreSQL bỏ được. Fixture sẽ downgrade về base rồi upgrade head,
và TRUNCATE dữ liệu sau từng test. Guard chỉ nhận DB tên `translation_test` trên
localhost/127.0.0.1/::1 hoặc service `db-test`; không nhận query override host.
Không dùng thông tin kết nối DB của ứng dụng đang phục vụ người dùng.

Trong môi trường có Python dependencies và PostgreSQL test sẵn, từ gốc repo:

```bash
python3 -m venv /tmp/translation-integration-venv
source /tmp/translation-integration-venv/bin/activate
python3 -m pip install -r backend/requirements-dev.txt
# Đặt TEST_DATABASE_URL bằng cấu hình của DB test riêng, driver postgresql+asyncpg.
bash scripts/test_production_backend.sh
```

Nếu không đặt TEST_DATABASE_URL, fixture dùng localhost:5433/translation_test.
Script không tự tạo container, cài dependency, chạy deploy hay gọi provider.
API tests giả lập dispatch broker; các test publisher truyền hàm publish ghi nhận bản tin,
vì vậy dù pass cũng chỉ xác minh SQL transaction/claim, chưa chứng minh Redis/Celery thật.
Bước tiếp theo sau SQL: kiểm broker crash/replay và worker/provider trong môi trường cách ly.

## Kết quả phiên 28/10/2026 bổ sung

- 43 isolated tests pass, 2 cảnh báo thiếu cấu hình plugin pytest asyncio.
- Đã thêm 11 case guard DB; hai integration case concurrent publisher và publication
  commit failure/replay (không thêm quota/job).
- `bash -n` và Python compile đạt; runner fail sớm do thiếu asyncpg như dự kiến.
- Integration PostgreSQL/broker **CHƯA CHẠY**, không đánh dấu pass hoặc LIVE.
- Pip trong sandbox không phân giải được nguồn tải; Docker socket permission denied.
  Lần xin chạy pip ngoài sandbox không thực thi vì approval review lỗi503.


## Bộ chạy Docker cách ly (bổ sung 28/10/2026)

```bash
bash scripts/test_production_docker.sh
```

Bộ chạy tạo project Compose riêng cho mỗi lần chạy; PostgreSQL dùng tmpfs,
không publish port, không import `.env`, không gắn dữ liệu app hiện có. Network test
là internal để chặn kết nối provider bên ngoài lúc chạy test. Image chỉ copy mã,
migration, test và font; không copy `.env` hay storage. Build cần Internet tải image/dependency.
Khi kết thúc, script dọn container/network/volume của chính lần chạy và giữ exit code test;
image build có thể còn trong Docker cache. Không chạy worker, không tải model.

Đã kiểm cú pháp Bash, parse YAML và `docker compose ... config --quiet`: đạt.
Đã thử script thật: dừng tại Docker socket permission denied, không tạo được môi trường.
**Chưa build image/chạy SQL tests; không coi config validation là test tích hợp pass.**


### Xác nhận chạy lại từ log người dùng — 28/10/2026

Log người dùng cung cấp ghi `26 passed in 13.93s`, `tests-1 exited with code 0`
(project translation-integration-t6uwym). Toàn bộ26 test API/PostgreSQL trong bộ chạy
production đã đạt sau sửa test. Có kiểm migration trên PostgreSQL test, upload idempotency,
rollback/reconciliation và outbox SQL claim/publish giả lập. Broker/provider vẫn giả lập;
chưa xác nhận Redis/Celery/AI hoặc Windows end-to-end, chưa deploy/LIVE.
Bằng chứng: attachment84df740c-00a7-4fde-9bb7-dbbd636558e1/Pasted text.txt do user gửi.


## Kiểm Redis/Celery thật — bổ sung 28/10/2026

Docker runner hiện gồm Redis tạm và hai test `test_production_broker.py`:

- Giữ lần xử lý đầu đang chạy, giao message thứ hai cho cùng Job và kiểm duplicate
  bị chặn trước provider/callback; sau hoàn tất giao message trễ và kiểm kết quả không đổi.
- Outbox publisher gửi qua Redis thật, worker Celery claim trên PostgreSQL; bản ghi
  publication được commit và lần publish tiếp theo không gửi thêm.

Worker dùng threads/concurrency2 trong tiến trình test qua Celery testing worker,
queue riêng từng case. Disable startup sweep/publisher để không ảnh hưởng phép đo.
Provider và completion callback được thay bằng hàm kiểm thử. Test này KHÔNG chứng minh
beat, process kill/restart, broker mất dữ liệu, chất lượng OCR/dịch hoặc toàn pipeline AI.
26 test cũ đã pass theo log user; **hai test Redis mới chưa chạy được trong agent** vì
Docker socket permission denied. Compile, Compose config và43 isolated tests đạt.

Chạy lại cùng lệnh `bash scripts/test_production_docker.sh`; bộ hiện tại dự kiến có28 test.
Chỉ ghi pass sau khi có log thực tế. Redis không persistence/port và chỉ nằm trong network test.

### Nghiệm thu ảnh thật sau khi broker đạt

Dùng đơn thử riêng3–5 ảnh có quyền sử dụng, gồm trang ít/nhiều bong bóng và chữ hiệu ứng.
Ghi rõ engine/ngôn ngữ/preset/glossary; kiểm đủ số trang/thứ tự, OCR, tên nhân vật/xưng hô,
bố cục, chữ Việt, vùng bị xóa nhầm. Dừng/tiếp tục client để kiểm không upload/thu lượt lại.
Chỉ approve và xuất ZIP khi đã so từng trang; kiểm receipt và không ghi đè sản phẩm cũ.
Cần backend/provider hoạt động và Windows để chạy bước này; chưa thực hiện hoặc phát sinh
lượt gọi AI trong phiên bổ sung test broker. Không coi ảnh mẫu tổng hợp trong API tests
là bằng chứng chất lượng sản phẩm thật.


### Kết quả xác nhận cuối từ người dùng — 28/10/2026

Log attachment cdd91401-2be6-4fc1-b63c-7739068c1b11/Pasted text.txt ghi
**28 passed in 27.65s**, `tests-1 exited with code 0`. Bộ test API/PostgreSQL
và2 test Redis/Celery thật đã đạt. Xác minh duplicate đang chạy/sau hoàn tất và
outbox publish→consumer claim trong môi trường cách ly, provider/callback giả lập.
Chưa kiểm beat, process/broker restart, OCR/dịch thật, Windows hoặc deploy/LIVE.
Kết quả này thay thế trạng thái chờ chạy lại của các mục log trước đó.
