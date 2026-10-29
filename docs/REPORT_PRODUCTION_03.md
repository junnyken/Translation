# PRODUCTION-03 — Mã yêu cầu bền và đối soát upload

Ngày 27/10/2026. **BUILT, chưa LIVE**. Tiếp tục một phần P1 trong kế hoạch đã duyệt;
chưa hoàn tất phục hồi server/worker hoặc đủ điều kiện nhận đơn thương mại.

## Summary

- Upload riêng của tài khoản có UUID `request_key`: cùng key/ảnh/lựa chọn trả lại trang cũ;
  khác nội dung trả 409. Bản ghi còn sau khi xoá trang: trả 410, không tạo lại việc cũ.
- Advisory transaction lock theo tài khoản + key, composite PK làm ràng buộc cuối.
  Key/page/quota/Job được commit cùng giao dịch; replay không enqueue hoặc giữ lượt thêm.
- Lookup GET theo tài khoản giúp desktop lấy lại page_id khi mất phản hồi POST.
- Desktop ghi key/protocol/payload version/ngữ cảnh trước POST, giữ nguyên qua restart.
  Mỗi resume chỉ gửi tối đa một POST/trang, vẫn key cũ; không loop retry hoặc tự đổi key.
- Ghi font/glossary sau quota. Cleanup artifact khi rollback; commit mơ hồ phải đối soát dưới
  cùng lock bằng kết nối primary mới trước khi quyết định xoá. Không đoán trạng thái DB.

## Audit Before Build

- User đã cho tiếp tục kế hoạch và trước đó yêu cầu không tạo task. Không tạo task/commit/deploy.
- Giữ các diff có sẵn của user, không thay public bundle hoặc renderer ngoài phạm vi controller.
- Phát hiện helper `_chapter_doc_nhanh` commit nội bộ: thêm `commit_project=False` riêng cho
  keyed upload để tránh nhả lock trước khi tạo page/quota/key.
- Quota/cache helpers đã đọc không có commit ngầm. Key chỉ được nhận cho tài khoản + private
  chapter; cache dịch cộng đồng không được dùng ở chế độ này.
- Backend test environment thiếu asyncpg/alembic/pytest-asyncio; socket localhost 5433/5432
  bị sandbox PermissionError. Không bypass quyền hoặc dùng SQLite thay cho PostgreSQL.

## Design Choice

- Fingerprint version 1: SHA256 raw image và JSON canonical của source/target lang, engine,
  pipeline, font, glossary, private flag. None và chuỗi rỗng cho trường tuỳ chọn là tương đương.
  Không phụ thuộc deployment/model default có thể thay đổi; replay trả bản đã nhận ban đầu.
  Đổi thuật toán cần giữ tương thích v1, không tự đổi cách hiểu key cũ.
- Scope tài khoản + UUID, không dựa token phiên hoặc URL nguồn. No TTL: record giữ tới khi
  xoá tài khoản, page/project deletion giữ tombstone. Cần duy trì chính sách này khi viết cleanup.
- Request chưa có key giữ hành vi cũ. Không tự cấp key cho upload mơ hồ của phiên bản desktop cũ.
- POST replay được kiểm trước engine admission/quota mới. Vẫn kiểm đăng nhập và quyền trang;
  GET lookup không tiết lộ record của người khác. Khi đổi chủ trang, quyền hiện tại vẫn có hiệu lực.
- Storage nằm ngoài SQL transaction. Trước commit thất bại: rollback và xoá prefix project riêng.
  Nếu đã thử commit: probe primary cùng bind, chờ cùng advisory lock rồi đọc key. Nếu đã nhận
  thì giữ artifact; DB/cleanup lỗi thì log project/request cần đối soát, không xoá đoán.
  Đây là cleanup best effort, chưa có durable orphan sweeper khi process bị kill.

## Changed Files

- Model UploadRequest; migration `0037_upload_request` nối `0036_cau_hinh_rieng`.
- Services `upload_identity.py`, `upload_requests.py`, `upload_artifacts.py`.
- Routes, schema TrangDocTruyen, health capability; thêm bảng vào test cleanup conftest.
- Windows production core và controller; tests client recovery/controller, identity/cleanup
  isolated và integration contract dùng PostgreSQL thật.
- Đồng bộ ARCH/API/FEATURES/TEST_LOG/PLAN và hướng dẫn production.

## New API/DB/State

- POST `/api/v1/doc-truyen/trang`: multipart optional `request_key: UUID`.
  Có key bắt buộc đăng nhập và `tao_chapter_rieng=true`; 401/422 nếu không đáp ứng.
  Hợp lệ/cùng request: 202 + TrangDocTruyen có request_key xác nhận. Khác request: 409;
  record có trang bị xoá: 410. Upload size được đọc có trần trước khi tạo project mới.
- GET `/api/v1/doc-truyen/yeu-cau/{request_key}`: TrangDocTruyen + request_key;
  401 chưa đăng nhập, 404 không có/không thuộc tài khoản, 410 trang đã xoá.
- Health thêm `translation_capabilities.idempotent_upload_v1=true`, chỉ capability code,
  không chứng minh migration/DB/worker đã sẵn sàng.
- Bảng upload_request: PK(owner_id, request_key), request_hash, page_id nullable,
  created_at/updated_at. Owner FK CASCADE; page FK SET NULL + index.
- Desktop ledger vẫn version 1, thêm optional request_key/request_protocol/
  request_payload_version/request_context/request_ack. Không lưu token/API secret trong các trường này.

## Tests

- `python3 -m pytest windows-app/tests -q`: **102 passed in 3.81s**.
  Thêm 15 bài gồm controller mất POST→GET lookup, giữ key/context qua restart,
  404→gửi cùng key, lỗi lookup không POST, ACK sai, nguồn đổi và backend cũ bị chặn.
- `python3 -m pytest backend/isolated_tests -o addopts='' -q`:
  **19 passed, 2 warnings in 0.13s**. 11 bài hash/lock ID; 8 bài quyết định cleanup.
  Warning do thiếu pytest-asyncio nên config asyncio không được nhận. Cleanup unit stub phần
  scheduling thread, không kiểm Starlette event loop hay query PostgreSQL. Lần thử thread thật
  bị treo khi chờ callback trong sandbox, đã ngắt, không tính đạt.
- **16 integration scenarios mới đã viết nhưng chưa chạy**, cộng 5 privacy tests trước.
  Bao phủ replay/count quota/job, options conflict, admission disabled, owner scope,
  tombstone khi xoá project, hai session đồng thời cùng/khác payload, rollback trước commit,
  enqueue failure, quota/storage failure và commit error trước/sau commit thực tế.
  Lệnh pytest integration dừng ở conftest vì `ModuleNotFoundError: asyncpg`.
- Review độc lập trước/sau code; finding artifact riêng bị orphan khi quota/rollback đã xử lý,
  kiểm lại bằng đọc code không thấy blocker mới. Không tuyên bố concurrent PostgreSQL đã đạt.
- Compile Python/diff check và candidate ZIP/CRC/hash ghi kết quả ở TEST_LOG.

## Live Verification

Chưa chạy migration, PostgreSQL concurrency/rollback thật, broker/worker/AI thật,
Windows/NTFS hoặc chapter thật. Không deploy hay cập nhật link tải công khai.
Bộ candidate cần backend đã áp 0036 + 0037 trước khi thử cloud upload mới.

## Remaining Limits

- Commit DB→enqueue vẫn có cửa sổ mất job. Replay không enqueue lại: trang đã nhận nhưng
  chưa chạy cần vận hành đối soát, không xoá key rồi gửi mới. Outbox/dispatch recovery là việc còn lại.
- Không hứa exactly-once phí provider; chưa có generation ngăn worker cũ ghi đè, trần tiền,
  benchmark/giấy phép, khách hàng/đơn, scheduler hoặc adapters website đã nghiệm thu.
- Object storage và SQL chưa phải một giao dịch nguyên tử. Process kill hoặc DB/storage outage
  có thể cần dọn artifact tồn; chưa có sweeper bền. Cleanup legacy không có key không được mở rộng.
- Hai request đồng thời có thể phải chờ lock; chưa đo tải/lock contention thật.
- Schema/ACK mới chưa được xác minh trên dịch vụ thật, health không phải readiness.
- Rollback không được drop bảng key rồi tự resend request cũ: sẽ mất bằng chứng chống trùng.
  Nếu quay về backend cũ phải dừng keyed uploads và giữ ledger/page_id/DB backup để đối soát.
  Không áp rollback hoặc migration trong phiên này.
