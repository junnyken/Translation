---
name: "payment-integration-vn-global"
description: "Use when building, changing or reviewing paid plans and payment flows (VietQR/SePay bank transfer, Stripe, PayPal): orders, webhooks, idempotency, upgrades, pricing, reconciliation."
---

# Tích hợp thanh toán Việt Nam + Quốc tế — chuẩn an toàn

Skill này đúc kết từ việc xây và sửa hệ thống thanh toán thật (bán gói theo kỳ, VietQR/SePay, Stripe, PayPal) và các lỗi thật đã gặp, đã vá và đã chạy trên production. Áp dụng cho mọi stack (ví dụ minh hoạ dùng Python/FastAPI + Postgres + Redis). Mục tiêu: **không bao giờ giao quyền lợi khi chưa chắc đã nhận đủ tiền, và không bao giờ nhận tiền mà khách không được phục vụ mà không ai biết.**

## Khi nào dùng
- Xây mới hoặc sửa: bảng giá, tạo đơn, trang thanh toán, webhook, nâng/hạ/gia hạn gói, khuyến mãi lần đầu.
- Review code thanh toán có sẵn (chạy mục 15 "Quy trình review").
- Trước khi mở bán, xoay secret, hoặc deploy bất kỳ thay đổi nào chạm tới tiền.

---

## 1. Mười nguyên tắc vàng

1. **Chỉ tin máy chủ cổng thanh toán.** Quyền lợi chỉ được cấp khi server xác minh trực tiếp: webhook có chữ ký hợp lệ, hoặc server tự gọi API cổng. Không tin redirect, query string, dữ liệu do trình duyệt gửi.
2. **Năm phép kiểm trước khi cấp quyền lợi** — thiếu một là KHÔNG cấp:
   (a) nguồn/chữ ký hợp lệ; (b) số tiền ≥ số tiền của đơn; (c) đúng loại tiền tệ; (d) đúng người nhận (tài khoản/merchant của mình); (e) giao dịch gắn với đúng đơn nội bộ và đơn đó thuộc đúng user.
3. **Idempotency bằng ràng buộc UNIQUE trong DB, chiếm chỗ TRƯỚC khi đổi quyền lợi.** INSERT vào sổ sự kiện với UNIQUE(provider, provider_event_id). Trùng → coi là đã xử lý, dừng. Lỗi DB khác → trả 5xx để cổng gửi lại (fail-closed). Không SELECT-rồi-INSERT.
4. **Đơn hàng có máy trạng thái, chuyển bằng compare-and-set:** `UPDATE ... SET status='paid' WHERE id=? AND status='pending'`. Không có dòng nào bị cập nhật → đã có tiến trình khác xử lý.
5. **Mọi tình huống "đã nhận tiền nhưng chưa giao quyền lợi" → hàng chờ duyệt tay + cảnh báo ngay.** Không bao giờ chỉ ghi log rồi thôi.
6. **Một nguồn giá duy nhất.** Giá hiển thị và giá thu phải đi qua cùng một hàm. Số tiền được chốt vào đơn lúc tạo. Hai gói không được trùng giá trên cùng kênh chuyển khoản.
7. **Tiền là số nguyên ở đơn vị nhỏ nhất** (VND = đồng, USD = cent). Parse bằng `Decimal`, không bao giờ `int(float(x)*100)`.
8. **Không có secret mặc định trong code.** Thiếu secret → tắt cổng đó (404/503). Secret đã từng lọt vào git → phải đổi.
9. **Quy tắc gói rõ ràng:** không hạ gói khi gói cao hơn còn hạn; mua lại cùng gói → cộng dồn ngày; nâng lên gói cao hơn → theo chính sách đã định.
10. **Cột quyền lợi (tier, hạn dùng, trạng thái billing) chỉ server được ghi** (RLS/trigger chặn client tự sửa). Cờ bật/tắt tính năng trả phí phải kiểm ở backend, không chỉ ẩn nút trên giao diện.
