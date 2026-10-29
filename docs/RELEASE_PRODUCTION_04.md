# Gói cập nhật Production-04 — chờ phát hành công khai

Ngày28/10/2026. User đã cho phép cập nhật công khai cho người dùng hiện tại.
Đích là hosting tự build từ GitHub junnyken/Translation, không tạo stack app khác.

## Đã chuẩn bị

- App Windows v1.1 chứa production.py, sources.py, review_delivery.py và hướng dẫn rà soát.
- Extension v0.3.1 đóng gói manifest + src hiện tại, manifest/package version đồng bộ.
- Frontend trỏ link tải và nhãn tiện ích sang v0.3.1/Windows v1.1.
- ZIP có ở frontend/public/tai-ve và dist; release-production-04.json ghi SHA256/kích thước.
- Gói cũ giữ nguyên; bản sao của gói cũ tại dist/rollback-pre-production-04 (chưa commit).
- Kiểm CRC/hash/file content ZIP đạt; desktop102 tests đạt.
- Bộ API/Postgres/Redis28 tests đã đạt theo log user trước khi đóng gói (không phải AI/Windows UAT).

## Chưa phát hành

Không commit/push, không đổi hosting, không migrate DB thật, không deploy hoặc phát hành store.
Build frontend chưa đạt: node_modules thiếu @rollup/rollup-linux-x64-gnu.
Audit dependency không chạy được do npm registry DNS; GitHub ls-remote bị DNS.
Xin quyền ls-remote ngoài sandbox không được thực thi do automatic approval review timeout.
Skill vibe-sec được đọc nhưng references/checklist.md và helper script của skill không tồn tại;
chưa ghi checkpoint PASS hoặc kết luận public security gate đã đạt.

## Trước khi push kích hoạt hosting

1. Khôi phục truy cập mạng và chạy npm ci trong môi trường Linux build riêng, build/test frontend.
2. Hoàn tất audit dependency backend/frontend/extension và kiểm bảo mật theo gate public;
   xử lý HIGH/CRITICAL trước khi phát hành, không tự đánh dấu pass khi thiếu dữ liệu.
3. Xác nhận nhánh hosting theo dõi và cấu hình API/frontend hiện tại.
4. Backup DB/storage production; xác nhận worker/API không lệch schema khi áp dụng0036–0038.
5. Review toàn bộ diff cùng thay đổi user có sẵn, commit và push vào nhánh hosting đã xác nhận.
6. Theo dõi build/migration/worker beat; kiểm health capability và URL/hash hai gói mới.
7. Thử ảnh thật và Windows; không dùng test provider giả lập làm bằng chứng chất lượng dịch.

Các ZIP v1.1/v0.3.1 hiện chỉ là file trong workspace, chưa có trên website đang chạy.
