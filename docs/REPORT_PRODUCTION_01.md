# PRODUCTION-01 — Luồng xử lý file an toàn và cấu hình riêng

Ngày: 27/10/2026. Trạng thái **BUILT, chưa LIVE**. Đây là đợt đầu của kế hoạch đã duyệt,
không phải hoàn tất toàn bộ P0–P2 hoặc sẵn sàng nhận đơn thương mại.

## Summary

- Desktop có manifest bền, khoá chapter giữa các tiến trình, kiểm hash + decode ảnh trước resume,
  giữ page_id để hỏi kết quả cũ, giới hạn thời gian poll, ghi ảnh/CBZ nguyên tử.
- Không tự thử lại upload khi không rõ đã được nhận; các HTTP từ chối rõ ràng có thể thử lại.
- Không lưu khi đã dừng, không báo hoàn tất sai, không đóng CBZ chapter thiếu trang.
- Đọc ZIP/CBZ và sắp ảnh/chapter theo thứ tự số; kiểm trần dung lượng/trang và đường dẫn.
- HTML parser sửa link tương đối, lazy-load và giữ ảnh CDN không có đuôi. Link tổng quát phải có
  người xác nhận số trang từ nguồn; không coi parser là bằng chứng quét đầy đủ website.
- Backend nhận tuỳ chọn cấu hình riêng, tách project từng request, không lấy/công bố cache cộng đồng.
  App preflight trước upload và kiểm acknowledgement sau upload. Kích thước ảnh lưu được trả để
  quy đổi bbox về ảnh gốc. Lưu cấu hình riêng thất bại thì dừng, không lặng lẽ dịch sai glossary.

## Audit Before Build

- Branch ban đầu: `main`, workspace đã có diff tại deploy-start.sh, frontend entrypoint,
  extension, các ZIP và renderer Windows. Giữ nguyên các phần này; không commit chung hoặc deploy.
- Kế hoạch app offline/Tauri hiện có không bị thay thế; nhánh này cải thiện client Python.
- User yêu cầu không tạo task và tiếp tục; không tạo/start/done task AI Factory.
- Python hệ thống có pytest/Pillow, không có Tk hay asyncpg. Venv sao chép không chạy trực tiếp
  và thiếu binary dependencies. Không dùng mock để tuyên bố PostgreSQL/worker đã chạy thật.

## Design Choice

- Core xử lý tách Tk để test lỗi và recovery bằng các callback. Server page_id là nguồn tham chiếu
  công việc AI, desktop không giả một trạng thái server mới khi chỉ mất kết nối.
- Chế độ riêng dùng một project mỗi trang để glossary/font không bị request khác ghi đè.
  Cột Boolean bền trên DB, không suy riêng tư từ tên project hoặc cache trong RAM.
- Tạm thời tắt cache bản dịch cho chế độ riêng thay vì hứa cache đã có fingerprint đầy đủ.
  Luồng cũ giữ nguyên hành vi; chưa sửa toàn bộ chính sách cache của app.
- Không tự coi file >1 KB là kết quả, không tự nhận lại ảnh đã bị người sửa tay thay đổi.

## Changed Files

- `windows-app/{production.py,sources.py,app_dich_truyen_windows.py,tests/,HUONG-DAN-PRODUCTION.md}`.
- `backend/app/{main.py,api/v1/routes.py,models/__init__.py,schemas/common.py}`.
- `backend/app/services/{bo_nho_anh_dich.py,typeset/chon_font.py}`.
- `backend/alembic/versions/0036_cau_hinh_rieng.py`, test API mới.
- Script đóng gói candidate riêng; không cập nhật các ZIP public đang có diff của user.

## New API/DB/State

- Migration `0036_cau_hinh_rieng`: `project.cau_hinh_rieng BOOLEAN NOT NULL DEFAULT false`;
  downgrade bỏ cột. Chưa áp dụng hoặc chạy upgrade/downgrade trên PostgreSQL.
- `/healthz.translation_capabilities.private_context_v1 = true` là capability code, không phải
  chứng nhận worker/DB sẵn sàng hay thông báo migration đã được áp dụng.
- POST `/api/v1/doc-truyen/trang`: form `tao_chapter_rieng=false` mặc định. Khi true, tạo project
  riêng, intended_use=other; vẫn kiểm quyền/hạn mức và trả 202 như cũ.
- `TrangDocTruyen` thêm `cau_hinh_rieng`, `image_width`, `image_height` (hai trường kích thước có
  khi trang riêng đã xử lý xong). Không đổi tên/status cũ.
- Manifest local: pending/submitting/submitted/completed + error. Hoàn tất xử lý vẫn có
  `review_status=pending`; chưa có quy trình phê duyệt chất lượng bằng máy.

## Tests

- **43 passed**: `python3 -m pytest windows-app/tests -q` trên Linux. Bao phủ lỗi mạng/poll,
  không lặp POST mơ hồ, retry sau bị từ chối, cancel, output hỏng/bị sửa, cấu hình đổi, lock,
  context resume, cache acknowledgement, preflight, bbox scaling, ZIP an toàn/natural sort,
  wiring controller với widget giả và export đúng danh sách.
- Python compile cho các file code/migration/test liên quan: đạt.
- Diff whitespace check giới hạn các file của đợt này: đạt. Whitespace CRLF trong diff shell có
  sẵn của user không bị sửa trong lượt này.
- **5 API integration tests đã viết, chưa chạy**: lệnh pytest dừng ở conftest do thiếu `asyncpg`.
  Hai lượt xin kiểm tra Docker bị hệ thống auto-review hết thời gian; Docker/DB chưa được truy cập.
- Một vòng review độc lập + kiểm lại ba sửa: URL ảnh không đuôi, preflight trước POST và phân biệt
  lỗi upload bị từ chối/mơ hồ. Không thấy blocker mới trong phạm vi kiểm lại bằng đọc code.

## Live Verification

Chưa chạy Windows thật, chưa gọi AI provider, chưa chạy chapter thật qua API/worker,
chưa áp migration, chưa build bộ cài, chưa deploy hoặc thay link tải công khai.
ZIP candidate chỉ được kiểm cấu trúc/CRC/hash, không phải bản release đã nghiệm thu.

## Remaining Limits

- P0 benchmark/chi phí/giấy phép và UAT còn thiếu. Không có căn cứ định giá hoặc hứa chất lượng.
- P1 chưa có idempotency đối soát POST phía server, outbox enqueue, generation của worker cũ,
  trần tiền/provider metrics. Khi upload mơ hồ phải người kiểm trên web.
- P2 chưa có hồ sơ khách/đơn, UI glossary xuyên bộ đầy đủ, approval workflow và PDF desktop.
- Trang không chữ chưa tự được duyệt; PDF/dải ảnh lớn bị từ chối để tránh OOM.
- P3 adapters từng website, P4 scheduler/watcher, P5 pilot và P6 PDF Pro chưa triển khai.
- Trước dùng thật: khôi phục test environment, chạy API tests + migration upgrade/downgrade,
  thử Windows end-to-end với backend staging, dùng dữ liệu được phép và rà soát giấy phép.
- Rollback: giữ app/bundle cũ; rollback backend theo migration thông thường. Downgrade bỏ cột
  làm mất cờ riêng tư, nên không downgrade DB rồi chạy code cũ với dữ liệu riêng mà chưa có
  kế hoạch giữ/tách/xoá dữ liệu đó. Không áp rollback tự động trong bản này.

## Bổ sung cùng ngày — kiểm đầu vào và polling

Sau yêu cầu tiếp tục, bộ test desktop tăng từ 43 lên **62 passed** (19 bài mới).
- Link chapter trực tiếp giữ chapter đang yêu cầu, không thay bằng previous/next trong HTML.
  Marker có ranh giới để `step-1`, `concept-2`, `mychapter-3` không bị coi là chapter;
  khi path có nhiều marker thì lấy marker cuối. Đây vẫn là heuristic, chưa phải adapter website.
- Srcset rỗng không làm parser lỗi; fallback về src nếu có.
- Thư mục ảnh áp cùng trần 200 trang, 20 MB/trang và 50 MB/chapter như archive.
  Thư mục rỗng bị từ chối rõ ràng; folder/archive có GIF/SVG/BMP/TIFF/AVIF/HEIC báo dừng
  để chuyển định dạng thay vì bỏ qua ảnh và giao thiếu trang. Metadata không phải ảnh vẫn bỏ qua.
- Poll hỏi trạng thái lần đầu ngay, không khởi chạy GET mới sau deadline; GET đang chạy vẫn
  chịu timeout HTTP riêng, không có cơ chế huỷ request tức thì.
- Review độc lập tìm một regression ranh giới marker; đã sửa và thêm bốn bài kiểm thử.
- `python3 -m pytest windows-app/tests -q`: **62 passed in 1.23s**.
- Compile hai module và đóng lại candidate ZIP/CRC/hash: đạt; chưa phát hành.
- Thử kiểm tra container bằng `docker ps` bị từ chối tại socket trong sandbox.
  Xin quyền kiểm tra bị hệ thống automatic approval review lỗi **503 Service Unavailable**,
  nên lệnh có quyền chưa thực thi. Không bypass; DB/migration/worker vẫn chưa được xác minh.
