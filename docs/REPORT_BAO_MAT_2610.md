# REPORT — Vá bảo mật & sửa lỗi theo đợt kiểm tra 26/10/2026

## Summary

Kiểm tra toàn bộ (đăng ký/đăng nhập, trang quản trị, phân quyền, nạp tiền, tải tệp, hạ tầng)
phát hiện 1 lỗi chức năng đang chạy trên production (`NameError: LoaiChuThe` ⇒ 500 ở cổng hạn
mức của tài khoản đăng nhập) và 5 lỗ hổng mức cao. Tất cả đã vá trong đợt này, kèm migration
`0035` chuyển đơn nạp từ tệp JSON vào CSDL và thêm nhật ký quản trị.

## Audit Before Build

| # | Mức | Lỗ | Chỗ |
|---|---|---|---|
| 1 | Lỗi 500 | `LoaiChuThe` dùng mà không import | `core/cong_han_muc.py:101` |
| 2 | Cao | "PoW" không có work: mã có chữ ký là đủ qua Turnstile, dùng lại vô hạn; token Turnstile sai vẫn qua nếu kèm mã | `xac_thuc_routes.py` |
| 3 | Cao | Email `thientrieu753@gmail.com` viết cứng tự lên quản trị; đăng ký không xác minh email; repo công khai | `services/tai_khoan.py` |
| 4 | Cao | Chapter vô chủ mở cho MỌI tài khoản; xoá user ⇒ chapter của họ thành của chung | `core/quyen.py`, `GET /projects` |
| 5 | Cao | Webhook nạp tiền không chống lặp; khớp tài khoản theo phần trước @ dễ cộng nhầm | `routes.py` webhook |
| 6 | Cao | SSRF: kiểm IP host đầu rồi để `urlopen` tự đi theo 302 | `developer_routes.py` |
| 7 | TB | Khoá bí mật Turnstile viết cứng trong repo công khai | `config.py`, `xac_thuc_routes.py` |
| 8 | TB | Đơn nạp đọc-sửa-ghi tệp JSON không khoá ⇒ duyệt 2 lần cộng 2 lần | `routes.py` |
| 9 | TB | Ảnh bom pixel (vài KB ⇒ hàng trăm MB khi giải mã) trong tiến trình API | `services/storage.py` |
| 10 | TB | Không có header bảo mật nào (CSP/HSTS/XFO/nosniff), lộ phiên bản nginx | `frontend/default.conf.template` |
| 11 | TB | Thao tác quản trị không có nhật ký | — |
| 12 | Thấp | Endpoint chết `/auth/xac-nhan-email` vẫn cấp phiên, mở khoá tài khoản bị khoá | `xac_thuc_routes.py` |
| 13 | Thấp | Tên miền email thử (`x.com`, `*.local`) được nhận ở production | `services/tai_khoan.py` |
| 14 | Thấp | Compose máy nhà mở Postgres/Redis ra `0.0.0.0`, thiếu nhãn tự tắt | `deploy/docker-compose.yml` |

## Design Choice

- **PoW thật**: `sha256("<mã>:<đáp án>")` phải có ≥16 bit 0 đầu (~65 nghìn lượt băm, 1–2 giây
  trên trình duyệt). Mỗi mã chỉ tạo được MỘT tài khoản: dùng `pow:<nonce>` làm khoá chống trùng
  của suất đăng ký trong `so_cai_han_muc` (không thêm bảng). PoW chỉ là đường lùi khi không có
  Turnstile (tiện ích, Turnstile không tải được); có token Turnstile thì token PHẢI đúng.
- **Phong quản trị**: `python -m app.scripts.phong_quan_tri <email>` hoặc biến
  `PHONG_QUAN_TRI_EMAIL` (chạy trong `deploy-start.sh`). Chỉ phong cho tài khoản ĐÃ có — không
  tự tạo, để không mở lại đúng lỗ cũ.
- **Chapter vô chủ**: chỉ quản trị thấy/nhận. `GET /projects` thêm điều kiện `chu_khach IS NULL`.
- **Đơn nạp**: bảng `don_nap_luot` (`trang_thai` là chuỗi, không enum Postgres — xem cảnh báo
  enum trong `CLAUDE.md`). Chuyển trạng thái = `UPDATE … WHERE trang_thai IN (…) RETURNING`;
  cộng/trừ lượt = `UPDATE … SET so_luot_mua_them = greatest(0, so_luot_mua_them + n)`.
  `ma_giao_dich_ngan_hang` UNIQUE ⇒ cổng gửi lại không cộng lần hai. Lượt cộng theo SỐ TIỀN THẬT.
  Đơn cũ trong `quan_tri/don_nap_luot.json` tự chép sang bảng ở lần đọc đầu (tệp giữ nguyên).
- **Pool worker**: GIỮ `threads`. `threads` cũng là một tiến trình như `solo` nên chuỗi hồi phục
  E22 (SIGKILL ⇒ bật lại ⇒ `worker_ready` ⇒ quét mồ côi) giữ nguyên, mà vẫn chạy song song được
  6 lượt gọi Gemini. Test và compose máy nhà sửa cho khớp.
- **CSP** ở chế độ `Report-Only`: `index.html` có script inline và trang gọi nhiều nguồn ngoài;
  chặn thẳng mà sót một nguồn là trắng trang. Xem console vài ngày rồi bật chặn.
- **Thông tin ngân hàng**: vẫn TẠM ẨN theo yêu cầu; chỉ sửa câu báo trong trang quản trị cho đúng.
- **Câu quảng cáo** "vượt Canvas DRM / chặn chuột phải / chống tải ảnh" đã bỏ khỏi trang giới
  thiệu tiện ích và trang hệ sinh thái. KHÔNG làm thêm tính năng vượt DRM.

## Changed Files

Backend: `api/v1/{routes,xac_thuc_routes,developer_routes}.py`, `core/{config,cong_han_muc,quyen}.py`,
`main.py`, `models/__init__.py`, `schemas/common.py`, `services/{tai_khoan,han_muc_dang_ky,storage}.py`,
mới: `services/{don_nap,nhat_ky_quan_tri}.py`, `scripts/phong_quan_tri.py`,
`alembic/versions/0035_bao_mat_don_nap_nhat_ky.py`, `deploy-start.sh`.
Frontend: `default.conf.template`, `src/{App.jsx,api.js}`, `components/auth/{ManDangNhap,QuanTriNguoiDung}.jsx`,
`components/trang-chu/{TrangTienIch,HeSinhThaiCongCu}.jsx`, mới: `lib/giai-pow.js`.
Tiện ích: `extension-doc-truyen/src/lib/api.js`, mới: `lib/giai-pow.js`.
Khác: `deploy/docker-compose.yml`.

## New API/DB/State

- Bảng `don_nap_luot`, `nhat_ky_quan_tri` (migration `0035_don_nap_nhat_ky`).
- `GET /auth/thach-thuc-bot` thêm trường `do_kho_pow`. `POST /auth/register` đòi
  `dap_an_thach_thuc` khi đi đường PoW.
- Webhook trả `{"ok": true, "trung_lap": true}` khi giao dịch đã xử lý; từ chối
  `transferType != "in"` và payload thiếu mã giao dịch.
- XOÁ: `POST /auth/xac-nhan-email`, schema `XacNhanEmailRequest`.
- Biến môi trường: `CLOUDFLARE_TURNSTILE_SECRET_KEY` nay BẮT BUỘC (thiếu ⇒ đăng ký qua Turnstile
  bị từ chối); `PHONG_QUAN_TRI_EMAIL` (tuỳ chọn).

## Tests

- Mới: `tests/test_va_bao_mat_audit_2610.py` (PoW, email chủ cũ, chapter vô chủ, webhook chống
  lặp + tiền ra + thiếu mã, duyệt đơn nguyên tử + nhật ký, SSRF CGNAT/302, ảnh bom) và
  `frontend/src/lib/giai-pow.test.js`.
- Cập nhật test theo luật mới (chapter vô chủ chỉ quản trị) và các danh sách đường công khai
  đã lệch từ E100–E107 (rà từng đường, ghi lý do tại chỗ).
- `conftest`: tài khoản test được đặt lại về "người thường, đang dùng" ở mỗi test — trước đây
  test phong quản trị mà không trả lại làm test sau đỏ theo THỨ TỰ chạy.
- Frontend: 582/582. Tiện ích: 36/36. Backend: xem lượt chạy cuối trong mô tả commit.

## Live Verification

Chưa deploy. Trước khi deploy phải: (1) xoay khoá Turnstile trên Cloudflare và đặt
`CLOUDFLARE_TURNSTILE_SECRET_KEY`; (2) migration `0035` tự chạy khi khởi động; (3) dựng lại
gói tiện ích Chrome (`dich-truyen-dang-doc.zip`) vì luồng đăng ký trong tiện ích đã đổi.

## Remaining Limits

- SSRF: còn cửa sổ DNS rebinding giữa lúc kiểm và lúc kết nối (chưa ghim IP).
- Developer API vẫn giả `Referer` để "vượt chặn hotlink" — chờ quyết định giữ/bỏ.
- `/healthz` công khai vẫn trả cấu hình nội bộ (giao diện, tiện ích và API.md đang dựa vào).
- Đăng ký vẫn báo "email đã có tài khoản" (dò được email); đăng nhập chỉ chặn theo IP.
- Mã phiên vẫn lưu `localStorage` — CSP chặn thật mới giảm được rủi ro XSS lấy phiên.
- Test cũ chưa sửa (không thuộc bảo mật, cần người nắm nghiệp vụ): `test_e19…test_engine_da_chon_THAT_SU_duoc_dung_khi_dich`
  (chế độ chỉ chữ không còn tạo job detect riêng), `test_inpaint_to_phang_unit`, `test_e84_to_phang_khung_sat_chu`
  (thuật toán xoá nét E-CCA đổi hành vi).
