# PRODUCTION-02 — Duyệt từng trang và gói giao có phiên bản

Ngày 27/10/2026. **BUILT, chưa LIVE**. Đây là phần tiếp của P2/quy trình duyệt P4 trong
kế hoạch đã được duyệt; chưa hoàn tất P0/P1/P2 và không thay các blocker tích hợp trước đó.

## Summary

- Công cụ dòng lệnh `windows-app/review_delivery.py`: status, approve từng trang, reject, export ZIP.
- Duyệt gắn SHA256 ảnh, nguồn/hash nguồn, cấu hình, vùng dịch và trạng thái xử lý; lưu người
  rà soát, thời gian UTC, ghi chú trong ledger. Cần xác nhận đã xem và hash đúng phiên bản ảnh.
- Thay ảnh/cấu hình/vùng dịch làm approval mất hiệu lực. Reject thu hồi duyệt; không có approve-all.
- Export kiểm đủ trang duyệt và bytes thực sự ghi ZIP; gói không chứa dữ liệu nội bộ.
- Xuất tự động của desktop mang tên `-ban-nhap`, tách khỏi ZIP giao do công cụ review tạo.

## Audit Before Build

- Giữ nguyên các diff có sẵn của user trong shell, extension, bundle và renderer.
- PRODUCTION-01 đã qua review code và 62 test; còn thiếu Windows, API/DB/worker/migration thật.
  Không gọi đây là hoàn tất audit live hoặc tự động mở bán.
- User yêu cầu tiếp tục kế hoạch, trước đó yêu cầu không tạo task; không tạo task/commit/deploy.
- Không đổi DB/server trong đợt này, không tìm cách bypass lỗi Docker auto-review 503 ở lượt trước.

## Design Choice

- Tái dùng lock ChapterLedger, lưu duyệt tại mỗi trang; không tạo DB/hàng đợi cạnh tranh.
- `status` và `export` tính lại approval, không tin riêng `review_status` có thể đã cũ.
- Fingerprint canonical chứa signature, config, nguồn/hash nguồn, regions, trạng thái và hash ảnh.
  Thời gian xử lý/ghi chú lỗi vận hành không làm mất duyệt nội dung.
- Đọc ảnh thành bytes, kiểm hash rồi `writestr` đúng bytes ấy; trình sửa ngoài không thể thay
  bytes đã kiểm bằng lần đọc khác khi đóng ZIP. Nếu sửa sau khi đọc thì ZIP vẫn có đúng bản duyệt.
- Ghi ZIP tạm, flush/fsync, hard link độc quyền sang tên giao trong cùng filesystem. Đích tồn tại
  hoặc filesystem không hỗ trợ thì dừng, không fallback sang copy dở hay overwrite.
- Review chỉ là ghi nhận của người vận hành; chưa có trình xem/chỉnh ảnh, danh tính xác thực hay
  audit chống sửa file. Không phải chứng nhận chất lượng, chữ ký hoặc quyền giao tự động.

## Changed Files

- `windows-app/review_delivery.py`, `Ra-Soat-Ban-Giao.bat`, `HUONG-DAN-RA-SOAT.md` mới.
- `production.py`: thêm require_existing để review không khởi tạo hồ sơ đã mất; cập nhật cờ
  review tổng hợp về pending khi processing thay đổi trạng thái.
- Controller Windows: tên tự động CBZ/PDF/longstrip có `-ban-nhap`, log hướng tới rà soát.
- Packaging whitelist thêm công cụ/launcher/guide, chỉ đóng candidate ở /tmp.
- `tests/test_review_delivery.py` mới; docs ARCH/API/FEATURES/TEST_LOG/PLAN và guide production.

## New API/DB/State

Không đổi HTTP/DB/migration. Ledger version 1 thêm trường tuỳ chọn `pages[].review`:
`decision`, `snapshot`, `reviewer`, `reviewed_at`, `note`. Ledger cũ chưa có review = pending.
Trạng thái hiệu lực: pending / approved / changes_requested / stale / blocked.
`review_status` tổng hợp là thông tin lần ghi cuối, không phải nguồn xác nhận giao được.

ZIP gồm `001.jpg`… và `BAN-GIAO.json`: schema_version, delivery_id, created_at UTC,
list file + SHA256. Không đưa source URL, glossary, token, vùng OCR, người duyệt/ghi chú vào receipt.
Không ghi đè ZIP cũ, không tự gửi khách, không tự xoá/đổi tên bản CBZ cũ tên sạch.

## Tests

- 25 bài mới (24 review/delivery, 1 controller tên bản nháp): gate partial/unapproved, hash/config/regions/source thay đổi, xác nhận người duyệt,
  thu hồi/restart/rerender, lock, hồ sơ mất/hỏng, privacy receipt, đích tồn tại/đua ghi đích,
  hard link không hỗ trợ, sửa ảnh giữa status→archive và sau khi đọc bytes, CLI subprocess,
  lỗi ghi ledger/ZIP và kiểm controller tự xuất tên bản nháp.
- Review độc lập theo mb-plan trước code, mb-review sau code; bổ sung chống TOCTOU, hard-link
  fail-closed và cảnh báo bản nháp cũ. Reviewer chạy độc lập 22 bài mới: đạt, không thấy blocker.
- Bộ desktop: **87 passed in 3.97s**; compile và đóng candidate ZIP/CRC/hash đạt.
  Chi tiết bằng chứng trong TEST_LOG.

## Live Verification

Chưa chạy UI/launcher/lock/hard link trên Windows/NTFS thật, chưa chạy AI/chapter thật.
Kiểm CLI subprocess/ZIP/hash trên Linux là kiểm chức năng local, không phải UAT dịch truyện.
Không thực hiện yêu cầu Docker mới, migration, deploy hoặc thay link tải công khai.

## Remaining Limits

- Chưa có màn rà soát trực quan hoặc nhập ảnh sửa tay, không tự nhận ảnh đã sửa bên ngoài.
- Người có quyền sửa ledger có thể sửa ghi nhận: chưa có authenticated reviewer/audit log.
- Chưa có duyệt/đóng gói nhiều chapter theo đơn, profile khách, báo giá, sổ phí hoặc lịch chạy.
- Chưa hoàn tất server idempotency/outbox/generation/cost ceiling, giấy phép và baseline chất lượng.
- Rollback: ngừng dùng công cụ mới, giữ ZIP giao cũ; version 1 cũ bỏ qua trường review bổ sung.
  App cũ có thể xuất CBZ chưa qua duyệt nên không coi là thay thế tương đương cổng giao mới.
- Trước dùng trả phí: Windows UAT, backend integration/migration và pilot có người rà soát.
