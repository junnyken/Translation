# Bản nâng cấp luồng sản xuất — candidate 27/10/2026

Đây là bản dùng thử có kiểm soát, chưa được xác nhận trên Windows thật hoặc API/worker thật.
Không thay thế bộ cài v1.0 đang có. Giữ toàn bộ các tệp Python đi kèm khi sao chép app.

## Trước khi dùng

- Máy Windows có Python 3.9+ và Pillow; mở bằng file `.bat` như bản cũ.
- Với dịch qua máy chủ: backend phải có migrations `0036_cau_hinh_rieng`, `0037_upload_request` và code tương ứng.
  App kiểm cả `private_context_v1` và `idempotent_upload_v1` trong
  `/healthz.translation_capabilities` trước khi gửi ảnh, rồi kiểm
  `cau_hinh_rieng` và xác nhận `request_key` từng trang. Backend cũ sẽ bị từ chối trước khi gửi nội dung khách.
- Không có thay đổi triển khai nào được thực hiện cùng bản code này. Cần kiểm thử tích hợp và
  Windows thật trước khi phát hành cho người dùng hoặc dùng cho đơn trả tiền.

## Luồng dùng thử

1. Chọn thư mục ảnh hoặc nút **Chọn file ZIP / CBZ**. PDF truyện vẫn dùng đường nhập file trên web;
   bản desktop này chưa thêm đọc PDF trực tiếp. PDF giữ bố cục tài liệu là chặng riêng.
2. Chọn ngôn ngữ, engine, font và thuật ngữ như cũ, chọn tên truyện/thư mục xuất riêng cho mỗi đơn.
3. Bấm bắt đầu. Ảnh/thư mục được sắp theo số: `1, 2, 10`. Thư mục và ZIP/CBZ tối đa 200 trang,
   50 MB tổng dữ liệu giải nén; mỗi ảnh tối đa 20 MB và 24 triệu pixel.
   Nếu có ảnh GIF/SVG/BMP/TIFF/AVIF/HEIC, chuyển sang JPG/PNG/WEBP trước; app sẽ báo dừng để tránh bỏ trang.
4. Với link: kiểm tra số trang trên nguồn và nhập lại để xác nhận. Không tự chạy mọi website,
   không xử lý CAPTCHA/DRM/paywall. Thứ tự và đúng nội dung vẫn phải người vận hành xem lại.
5. Chapter chỉ được đóng CBZ bản nháp khi mọi trang đã có kết quả hợp lệ.
   Bản tự xuất CBZ/PDF/dải ảnh có tên `-ban-nhap`; file cũ không tự được đổi tên. PDF/dải ảnh chỉ nhận đúng danh sách
   trang đã kiểm; không lấy lại dải ảnh cũ làm trang nguồn. Giới hạn bộ nhớ cho ghép PDF/dải ảnh.
6. Mở xem lại bản dịch, tên riêng, xưng hô, xoá chữ và chữ bị tràn trước khi giao.
   “Đã xử lý đủ” không đồng nghĩa bản dịch đã được duyệt chất lượng.
   Dùng công cụ `review_delivery.py` để duyệt từng trang và xuất ZIP giao; xem
   [HUONG-DAN-RA-SOAT.md](HUONG-DAN-RA-SOAT.md). Chưa có GUI review hoặc nhập ảnh sửa tay.

## Dừng và tiếp tục

- `trang-thai.json` lưu trạng thái, mã trang máy chủ, cấu hình, hash ảnh, ngữ cảnh và thời gian xử lý.
  File này có thuật ngữ/chữ dịch; giữ cùng dữ liệu đơn hàng, không đưa lên kho công khai.
  Token/API key không được ghi vào manifest.
- Mở lại cùng nguồn/cấu hình/thư mục sẽ tiếp tục hỏi trang đã gửi, không tải lại để trừ thêm lượt.
- Với cloud upload mới, app ghi UUID `request_key`, phiên bản và snapshot ngữ cảnh trước POST.
  Nếu mất phản hồi, mở lại lượt chạy: app tra mã này để lấy trang đã nhận. Nếu chưa có record,
  chỉ gửi lại đúng key/ảnh/cấu hình/ngữ cảnh cũ, tối đa một lần trong lượt resume.
- Backend giữ key theo tài khoản không có TTL; xoá trang vẫn giữ record và trả HTTP 410,
  không tự tạo lại. HTTP 409 nghĩa key đã gắn với nội dung khác: dừng để đối chiếu,
  không xoá key/ledger để tự gửi lại.
- Upload mơ hồ từ bản cũ chưa có key vẫn cần kiểm trên web, không thể nâng cấp an toàn bằng
  cách tạo key mới. ACK key không khớp thì giữ page_id để kiểm, không tự gửi tiếp.
- HTTP 401/403/413/429 cho phép thử lại sau khi xử lý tài khoản/hạn mức, vẫn giữ key nếu có.
  Timeout/HTTP 500 giữ trạng thái chưa rõ; lỗi GET lookup khác 404 không kích hoạt POST mới.
- Dừng không lưu ảnh đang dở; job đã gửi có thể vẫn chạy trên server.
- Đổi nguồn, ngôn ngữ, engine, thuật ngữ hoặc font: chọn thư mục/tên truyện mới. App không tự ghi
  đè ảnh đã chỉnh tay, ảnh khác hash hoặc thư mục ảnh cũ chưa có manifest.
- Chỉ một tiến trình xử lý một chapter tại một thời điểm. Khoá tự giải phóng khi tiến trình kết thúc;
  không cần xoá file `.processing.lock`.

## Giới hạn cần biết

- Không tự nhận trang “không chữ” là thành công nếu chưa có bằng chứng: hiện dừng để kiểm riêng.
- Tách cấu hình bằng một project riêng cho từng trang desktop. Đây là bước bảo vệ ban đầu;
  chưa phải hồ sơ đơn hàng hay thư viện thuật ngữ xuyên bộ truyện hoàn chỉnh.
- Chế độ riêng không lấy hoặc công bố cache cộng đồng. Các luồng cũ vẫn giữ hành vi cũ.
- Chống trùng upload không bảo đảm phí nhà cung cấp chỉ phát sinh một lần. Không loop retry POST.
- Chưa sửa khoảng DB đã nhận nhưng chưa enqueue; nếu gặp lỗi hàng đợi thì cần vận hành đối soát,
  không tạo key mới để ép chạy lại. Key là bằng chứng đối soát, không phải token đăng nhập.
- Chưa có outbox DB→broker, generation chống worker cũ ghi đè rerun, trần tiền theo model,
  đánh giá giấy phép thương mại hoàn tất, lịch chạy, hay PDF Pro.

## Kiểm thử

Từ gốc repo: `python3 -m pytest windows-app/tests -q`.
Đây là test luồng xử lý/headless trên Linux, không thay thế UAT Windows/AI thật.
API integration: `cd backend && python3 -m pytest tests/test_production_private_context.py tests/test_production_upload_requests.py -q`
với dependencies và PostgreSQL test theo hướng dẫn README. Chưa chạy được trong phiên triển khai.

Kiểm tra hash và quyết định cleanup độc lập DB: `python3 -m pytest backend/isolated_tests -o addopts='' -q`
từ gốc repo. Các bài này không chứng minh tính đúng advisory lock hoặc quota trên PostgreSQL.
Bộ integration reset DB test theo conftest; chỉ cấu hình TEST_DATABASE_URL tới DB test riêng.
