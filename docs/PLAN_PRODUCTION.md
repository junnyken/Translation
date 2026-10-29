# Kế hoạch phát triển Translation cho dịch vụ dịch tính tiền theo sản phẩm

Ngày: 27/10/2026. Trạng thái: user đã duyệt; đang triển khai từng đợt.
Mục tiêu user đã xác nhận: dùng app nhận việc dịch, thu tiền theo sản phẩm.

## Tiến độ triển khai 27/10/2026

Đợt PRODUCTION-01 đã có code và 62 kiểm thử desktop đạt, trạng thái **BUILT, chưa LIVE**.
Đã làm một phần P0–P2: đọc ZIP/CBZ, khôi phục theo từng trang, chống ghi đè kết quả,
xuất đủ trang và tách cấu hình backend. Chưa hoàn tất P0–P2 hoặc các chặng sau.
Năm kiểm thử API chưa chạy được do thiếu dependency; chưa kiểm Windows, migration và worker thật.
User yêu cầu tiếp tục không tạo task AI Factory. Các nội dung đề xuất/ghi nhận task bên dưới
là bối cảnh của bản kế hoạch ban đầu, không phải hành động đã thực hiện.
Chi tiết bằng chứng và giới hạn: [REPORT_PRODUCTION_01.md](REPORT_PRODUCTION_01.md).

Đợt PRODUCTION-02 đã bổ sung CLI duyệt từng trang và xuất ZIP giao có receipt, chống ghi đè,
không trộn bản nháp tự xuất với bản giao đã duyệt. Tổng kiểm thử desktop: **87 đạt**.
Chưa có GUI review/chỉnh ảnh hoặc nghiệm thu Windows/backend; xem
[REPORT_PRODUCTION_02.md](REPORT_PRODUCTION_02.md). P0–P2 vẫn chưa hoàn tất.

Đợt PRODUCTION-03 đã bổ sung server request key, lookup đối soát, client giữ payload/key,
và rollback artifact cleanup. **102 desktop + 19 isolated tests đạt**, nhưng 16 integration
scenarios mới chưa chạy được; chưa đánh dấu server idempotency LIVE hoặc hoàn tất P1.
Chi tiết: [REPORT_PRODUCTION_03.md](REPORT_PRODUCTION_03.md).

## 1. Định hướng và ranh giới

Ưu tiên truyện/ảnh/scan có quyền sử dụng; người vận hành duyệt trước khi giao.
Luồng: nhận file hoặc link được hỗ trợ → kiểm đầu vào + báo giá dự kiến → hàng đợi → dịch → rà soát → xuất bản giao → ghi nhận chi phí.
Không coi số tính năng hoặc OCR confidence là chứng minh chất lượng dịch. Chưa hứa tự chạy mọi website hoặc giao hàng không cần người xem.
Giữ FastAPI/SQLAlchemy/Postgres/Celery/React hiện có. Cải thiện app Python Windows hiện tại như client; không triển khai song song kế hoạch Tauri/offline 9–11 tuần tại docs/desktop/PLAN.md trong giai đoạn đầu.

## 2. Nguồn tham khảo và mức chắc chắn

- Immersive Translate: https://immersivetranslate.com/en/ — HTML chính thức đã đọc trong phiên 27/10/2026, bản lưu /tmp/translation-market-5.html; công bố dịch website/PDF/EPUB/ảnh/truyện, thuật ngữ/ngữ cảnh. Ảnh user gửi có PDF Pro, BabelDOC, truyện, ảnh, xuất phụ đề YouTube, đồng bộ cài đặt và hỗ trợ nhanh. Đây là tính năng công bố, không phải kết quả benchmark.
- manga-image-translator: https://github.com/zyddnys/manga-image-translator — README đã đọc trong phiên, bản lưu /tmp/translation-market-3.html. Có local batch, web/API, JSON config, detector/OCR/inpaint/render options, glossary, upscale, intermediate outputs và output formats. Trang repo hiển thị GPL-3.0; phải pin commit và đọc license/dependencies/weights thực tế trước mọi tích hợp.
- DeepL: https://www.deepl.com/en/features/document-translation — bản lưu /tmp/translation-market-1.html: file/bulk/layout/glossaries. Chưa xác nhận hợp đồng API cụ thể.
- Google Cloud: https://cloud.google.com/translate/docs/advanced/batch-translation — bản lưu /tmp/translation-market-2.html: batch text/HTML qua Cloud Storage; không coi trang này là bằng chứng dịch ảnh truyện hoặc giữ bố cục PDF.
- Ichigo: docs/REPORT_ICHIGO_BLACKBOX_BENCHMARK.md ngày 22/09/2026; upload PDF/ZIP/ảnh + auto-download là evidence lịch sử, chưa xác minh lại.
- Đợt đọc web bổ sung bị approval reviewer lỗi 503; chưa đọc mới license/API BabelDOC. Các tích hợp bên thứ ba dưới đây là spike có điều kiện, không phải dependency đã duyệt.

## 3. Học tính năng hay tích hợp sản phẩm

Immersive Translate là chuẩn tham khảo trải nghiệm. Không có bằng chứng API dùng lại quyền Pro; không lập kế hoạch tự động điều khiển tài khoản Pro để phục vụ khách.
manga-image-translator là chuẩn so sánh pipeline và cấu hình. CLAUDE.md cấm nhúng code GPL; ưu tiên tự hiện thực theo interface riêng. Gọi một process/service ngoài không tự giải quyết nghĩa vụ giấy phép.
BabelDOC là ứng viên riêng cho tài liệu PDF có chữ; xác minh upstream/release/license/model/runtime trước thử. Không hứa giữ nguyên tuyệt đối bảng, công thức, hyperlink, font hay cấu trúc.
DeepL/Google chỉ dùng qua API chính thức phù hợp, theo giá/quota/ngôn ngữ/quyền dữ liệu được xác nhận. Không phụ thuộc endpoint dịch công khai không có SLA cho đơn hàng trả tiền.

## 4. Ma trận đầu tư

Làm trước:
- Dịch file hàng loạt, preset cố định theo đơn hàng, tự tải/xuất an toàn.
- Hồ sơ bộ truyện: glossary, xưng hô nhân vật, ngữ cảnh xuyên chapter, import/export CSV/JSON.
- Hàng chờ rà soát lỗi, đối chiếu gốc/dịch, re-run đúng vùng/bước.
- Bộ lấy link theo từng nguồn; xem trước số chapter/trang, thứ tự, thumbnail, phát hiện thiếu/trùng.
- Lưu trạng thái bền vững, tiếp tục sau mất mạng/khởi động lại, giới hạn retry và chi phí.
- Đơn hàng tối giản: tên khách/mã đơn, source, preset, hạn giao, kết quả, giá thoả thuận; không dựng CRM/thanh toán đầy đủ.

Sau khi có dữ liệu sử dụng:
- Thư mục tự nhận file, lịch chạy danh sách chapter, hoàn tất thì hiện thông báo trong app/tạo gói giao. Tự gửi email/webhook chỉ cấu hình khi user cho phép.
- PDF tài liệu song ngữ/giữ bố cục qua pipeline riêng; thử BabelDOC hoặc API chính thức rồi mới chọn.
- OCR hai lượt hoặc gửi ảnh/model tốt hơn chỉ cho trang khó, có trần tiền.
- Xuất PSD chỉ xác nhận tương thích sau mở thử Photoshop/Photopea; hiện có code nên không xây lại.

Để sau khi có đơn hàng thật:
- Dịch SRT/VTT có sẵn, giữ timecode; YouTube chỉ thêm sau khi xác minh nguồn phụ đề hợp lệ/API và nhu cầu. Không gộp ASR/dubbing vào tính năng này.
- EPUB/DOCX qua parser/engine riêng; không đưa vào OCR truyện và tuyên bố giữ cấu trúc.
- Đồng bộ preset/thuật ngữ giữa máy (không đồng bộ token/API key), chính sách xung đột, phiên bản và sao lưu.
- Cổng khách hàng, nhiều nhân sự, thuê bao/thanh toán, app offline đầy đủ, GPU nâng cao.

## 5. Các chặng và tiêu chí nghiệm thu

Thời gian dưới đây là khoảng công một DEV quen repo + người vận hành UAT, chưa phải cam kết deadline. Cần kiểm tra branch hiện tại và baseline trước khi chốt. P0–P4 là phạm vi lõi; P5/P6 tách riêng.

### P0 — Baseline + đo hiện trạng (2–3 ngày làm việc)

- Không sửa/ghi đè các file đang thay đổi; tách diff nền và phần việc mới. Đối chiếu code/test/bản chạy thật; dọn mâu thuẫn trạng thái README/FEATURES trong phạm vi tính năng sẽ làm.
- Lập mẫu kiểm có quyền: EN/JA/KO/ZH theo ngôn ngữ định bán; có ảnh màu/đen trắng, chữ nhỏ, dọc, nền khó và trang không chữ. Chỉ quảng bá ngôn ngữ đã đo.
- Kiểm giấy phép code, weights, font, nhà cung cấp và quyền nội dung. GPL không đồng nghĩa cấm kinh doanh; tôn trọng ràng buộc repo và xác minh riêng weight phi thương mại.
- Chốt vòng đời dữ liệu theo khách/mã đơn: provider nào được nhận nội dung, thời hạn lưu, cách xoá ảnh gốc/trung gian/cache/bản xuất, backup và quyền tải. Một tài khoản vận hành nhận nhiều khách thì ranh giới cache không được chỉ dựa tài khoản đăng nhập.
- Đo thời gian từng bước, RAM, lỗi, token input/output/ảnh theo model, chi phí thực tế và phút sửa tay. Giá nhà cung cấp được gắn phiên bản/ngày; không coi tổng token là tiền hoặc đoán đơn giá hiện tại.
- Xong: có baseline chạy thật và danh sách blocker; chưa đủ giấy phép thì không chọn engine đó cho đơn thương mại.

### P1 — Chạy đủ, báo đúng, phục hồi an toàn (5–8 ngày)

Neo code: windows-app/app_dich_truyen_windows.py; backend/app/services/batch/{orchestrator,dispatch}.py; backend/app/workers/hoi_phuc.py; backend/app/services/bo_nho_anh_dich.py; backend/app/api/v1/{routes,developer_routes}.py; backend/app/services/export/chapter.py.

- Lưu manifest bền theo chapter/trang: nguồn+hash, cấu hình+model/prompt version, trạng thái nhập/dịch/rà soát, job ID, output hash, lỗi và lần retry. Job ID từ backend là nguồn sự thật cho AI; desktop theo dõi file tải/lưu, không tạo một state machine AI cạnh tranh.
- Gửi lại cùng yêu cầu chỉ tạo một job/khấu trừ một lượt theo khoá idempotency; đặt rõ TTL/scope, atomically xử lý cả yêu cầu đồng thời. Reconcile trường hợp mất kết nối sau server đã nhận.
- Bao phủ cửa sổ DB commit → enqueue: backend/app/services/batch/dispatch.py commit Job trước apply_async; thử kill API/broker đúng khoảng này. Dùng cơ chế đối soát/outbox phù hợp để không mất job và xử lý phát lại không nhân kết quả.
- Mỗi lần chạy có generation/version; worker cũ hết quyền ghi khi cancel/chạy mới/sửa tay. Bản sửa tay và bản duyệt không bị kết quả muộn ghi đè; nội dung mới làm mất hiệu lực phê duyệt cũ. Test cancel → rerun → sửa tay → worker cũ trả kết quả.
- Không resume chỉ vì file >1 KB; kiểm mở được, đúng hash+cấu hình, trạng thái hoàn tất. Ghi tệp tạm rồi đổi tên nguyên tử.
- Deadline tổng cho poll, cancel không lưu trang dở, retry hữu hạn có backoff cho lỗi tạm; lỗi vĩnh viễn yêu cầu can thiệp.
- Cache phân biệt glossary/ngữ cảnh, model/prompt và render config; tách dữ liệu khách hàng. Có thể cache OCR/inpaint dùng chung khi phù hợp nhưng cache bản dịch riêng tư mặc định theo tenant/khách và không lấy bản sửa tay của khách khác.
- Không đóng gói âm thầm chapter thiếu trang. Phân biệt bản nháp xuất thiếu có xác nhận với bản giao đủ trang.
- Đặt giới hạn tối thiểu ngay ở P1: số trang, lần gọi provider, retry và tiền đã dự kiến; khi không xác định được chi phí thì tạm dừng để người vận hành quyết định. Không trừ lượt nội bộ hai lần không có nghĩa provider không tính tiền lại: timeout sau provider đã xử lý có thể có phí chưa biết. Ghi nhận usage chắc chắn/ước tính/chưa xác định, không hứa exactly-once phí ngoài nếu API không hỗ trợ.
- Xong: thử cắt mạng sau submit, restart client/worker, timeout, đĩa đầy, dừng giữa chừng, request trùng và trang lỗi; không mất/nhân trang, không thu lượt hai lần, không báo thành công sai.

### P2 — File thành sản phẩm giao được (4–6 ngày)

Neo code: backend/app/services/{archive,pdf}.py; backend/app/services/quality/; backend/app/services/consistency/; frontend/src/components/{chapter,consistency,ExportPanel.jsx}; windows-app/.

- Một đường nhận ảnh/thư mục/ZIP/CBZ/PDF truyện; natural sort 1,2,10, phát hiện trùng/tệp hỏng, preview số trang và trần dữ liệu. Giữ kiểm zip-bomb/path traversal/pdf memory hiện có.
- Mỗi chapter/đơn có project riêng: tránh _chapter_doc_nhanh tái dùng cùng project rồi ghi đè glossary/font khi nhiều việc chạy đồng thời.
- Preset Nhanh/Rà soát kỹ/Tuỳ chỉnh mô tả engine, giới hạn tiền và chất lượng; lưu snapshot bất biến cho mỗi run. Chất lượng cao là mục tiêu benchmark, không là nhãn bảo đảm.
- Dùng lại glossary/voice profiles/review hiện có. Glossary dùng chung ở cấp bộ truyện/đơn được version; rerun hay resume không mất ngữ cảnh đã duyệt.
- Gói giao: đủ ảnh theo thứ tự, CBZ/ZIP, PDF ảnh nếu cần; giữ riêng báo cáo lỗi/thuật ngữ; PSD chỉ khi kiểm tương thích.
- Xong: ít nhất 3 đơn mẫu từ nhập file đến mở gói giao bằng app thật; PDF truyện không quảng bá text-selectable hay giữ cấu trúc tài liệu.
- Chạy pilot file nhỏ ngay tại mốc này: ghi phút sửa tay, chi phí và chất lượng; nếu chưa giảm công thực tế thì sửa P1/P2 trước khi đầu tư P3/P4. Chỉ nhận đơn thương mại giới hạn sau khi qua kiểm giấy phép và nghiệm thu, có người rà soát.

### P3 — Link đáng tin trên nguồn đã chọn (5–8 ngày, phụ thuộc website)

Neo code: windows-app/app_dich_truyen_windows.py:quet_danh_sach_chapter_tu_url/quet_anh_trang_truyen_trong_chapter; module dự kiến windows-app/sources/; backend developer_routes.py nếu tải server.

- Bắt đầu 2–3 nguồn do người vận hành có quyền truy cập lựa chọn, bộ lấy dữ liệu riêng từng nguồn; HTML parser, urljoin đúng URL trang, ưu tiên data-src, srcset, lazy-loading, phân trang mục lục.
- Xem trước và xác nhận danh sách chapter/trang/thumbnail trước khi dịch; so số trang kỳ vọng, loại logo/placeholder, giữ thứ tự. Không tìm được mục lục phải báo unsupported/needs_review, không giả vờ đó là chapter.
- JS-rendered chỉ làm adapter/browser hợp lệ khi thực sự cần; không vượt CAPTCHA/paywall/DRM. Cookie nguồn nếu có phải lưu an toàn, không đưa vào log hoặc đồng bộ mặc định.
- Rate-limit theo host, retry hữu hạn, resume tải và checksum; phía server giữ SSRF protections cho redirect/DNS, giới hạn dung lượng/timeout.
- Xong: mỗi nguồn có fixture contract + kiểm một chapter thật được phép; website đổi cấu trúc thì báo rõ, không xuất nhầm thành công. Không cam kết mọi link.

### P4 — Tự động hoá có giới hạn + quản lý lời/lỗ (4–6 ngày)

- Bổ sung đơn hàng tối giản và snapshot báo giá được người vận hành duyệt. Phân biệt giá thu khách và chi phí engine.
- Hàng đợi có giới hạn chạy đồng thời theo RAM/quota; file watcher chờ ghi xong/rename rồi nhận, dedupe theo content+config.
- Lịch chạy được lưu bền, một scheduler chủ, không chạy lại đơn khi restart; thư mục đầu vào/đầu ra tách riêng tránh lặp vô hạn.
- Trần tiền/run/ngày; hết trần thì dừng và xin quyết định, không âm thầm đổi sang bản miễn phí/chất lượng thấp. Chi phí chưa có bằng chứng thì để chưa xác định.
- Lưu log theo đơn, tiến độ thật, lỗi cần người xử lý; tự xử lý rồi vào hàng rà soát, người duyệt mới thành bản giao.
- Xong: chạy qua đêm với lỗi chủ động, không cần click từng trang; sáng thấy đủ kết quả hoặc danh sách lỗi có thể tiếp tục. Không tự gửi khách hay tự xuất bản.

### P5 — Pilot dịch vụ, quyết định mở bán (3–5 ngày + thời gian nhận phản hồi)

- Mục tiêu 10–20 chapter/đơn tương đương, đa dạng thuộc phạm vi đã công bố; không coi sample này là bảo đảm mọi dữ liệu.
- Bắt buộc 0 thiếu/trùng/sai thứ tự không báo; 0 completed giả; 0 rò nội dung/thuật ngữ chéo khách; mất mạng/restart không tính lượt trùng.
- Bản giao phải được rà soát; so lỗi nghĩa/tên/xưng hô còn lại và phút sửa tay với cách làm cũ trên cùng mẫu, do người đánh giá đủ năng lực ngôn ngữ. Mục tiêu thử: giảm >=30% thời gian thao tác+sửa mà không tăng lỗi nghiêm trọng; nếu không đạt thì điều chỉnh workflow/engine trước mở rộng.
- Chỉ nhận mức tải đã đo; lấy số thời gian p50/p95 và RAM để xác định năng lực, buffer deadline. Tính lãi gồm AI, hạ tầng phân bổ, công sửa, hỗ trợ, làm lại.
- Nếu thay đổi dịch vụ public: security review/vibe-sec và quy trình gate hiện hành trước release; kế hoạch này không cấp quyền deploy.

### P6 — Spike PDF tài liệu giữ bố cục (3–5 ngày, quyết định đầu tư riêng)

- Tách document pipeline khỏi services/pdf.py đang rasterize truyện. Bắt đầu PDF có lớp chữ; scan là phạm vi đánh giá riêng.
- Khảo sát BabelDOC và API chính thức (khả năng tiếng Việt, file size, font, giá, quyền dữ liệu, license). Tên dự kiến backend/app/services/documents/ với interface riêng; chưa chọn engine hoặc pin version trước evidence.
- Thử 5–10 PDF được phép, có 2 cột/bảng/công thức/scan. So original vs translated/bilingual: đủ trang, giữ hình, không chồng chữ, bảng/công thức không mất, font Việt, text search/select theo capability công bố.
- Kiểm khả năng sửa đầu ra thực tế và thời gian sửa: đẹp khi xem nhưng không sửa được hoặc mất quá nhiều công thì chưa phù hợp dịch vụ.
- Đo công sửa và chi phí; nếu sửa nhiều hơn làm thủ công thì chưa cung cấp dịch vụ đó. EPUB/DOCX/subtitle/cloud sync là mini-spec tiếp, chỉ mở khi có nhu cầu trả tiền xác nhận.

## 6. Kiểm tra và bàn giao DEV

- Test backend integration với Postgres/Celery phù hợp: idempotency concurrent, cache config+tenant, restart, quota, export đầy đủ; test parser fixture không thay thế chạy nguồn thật.
- UI/Windows end-to-end: nhập→tiến độ→ngắt mạng→mở lại→rà soát→xuất→mở file. Linux/mock không chứng minh chạy trên Windows; cần máy Windows thật.
- Chạy các bộ test có liên quan + required checks; không dùng số lượng test làm chất lượng sản phẩm. Không thay test để hợp thức hoá lỗi đã biết.
- Mỗi chặng: scope/API/state/DB migration additive nếu cần, rollback, test evidence và giới hạn; cập nhật docs/ARCH.md, API.md, FEATURES.md, TEST_LOG.md theo convention mini-spec. Không đánh LIVE trước chạy thật.
- Trước sửa repo: xác định task/start_task theo quy ước workspace. Hiện phiên không có MCP task callable, nên chưa ghi nhận task; không tuyên bố đã start/done. Kế hoạch chỉ ở /tmp và trả trong hội thoại, chưa tạo task, sửa code, commit hay deploy.

## 7. Ước lượng và ưu tiên chốt

P0–P4: 20–31 ngày công (~4–6,5 tuần nếu một DEV tập trung), chưa gồm pilot, phụ thuộc nguồn và sửa phát sinh. P5 thêm 3–5 ngày thực thi và thời gian phản hồi; P6 là 3–5 ngày spike, không là cam kết hoàn thiện PDF Pro.
Đây là ước lượng sơ bộ có độ chắc chắn thấp trước baseline; riêng P1 có thể vượt 5–8 ngày vì đụng nhiều luồng API/queue/Windows. Re-estimate sau P0, chưa gắn deadline.
Mốc nhỏ đầu tiên nên làm: P0+P1 rồi P2, có thể nhận việc thủ công có kiểm soát sau khi nghiệm thu; không chờ tất cả tính năng mở rộng.
Không cộng kế hoạch offline/Tauri vào phạm vi này. Chốt nguồn link, ngôn ngữ, đầu ra và mẫu benchmark sau P0; deadline/calendar chỉ chốt khi có capacity/task thực tế.

## 8. Review độc lập

Đã hoàn thành một vòng phản biện read-only theo skill mb-plan. Đã nhận cả sáu bổ sung: khoảng trống commit→enqueue; generation ngăn worker cũ ghi đè sửa tay; trần tiền tối thiểu ngay P1; phân biệt phí provider với lượt nội bộ; vòng đời dữ liệu theo mã khách/đơn; pilot file sau P2 và đo khả năng sửa PDF. Không phát sinh đề xuất cần bỏ. Ước lượng giữ ở mức sơ bộ, không tự triển khai sau khi có kế hoạch.


## Bổ sung PRODUCTION-04

Đợt PRODUCTION-04 đã xây dựng outbox cho first detect của keyed private upload và consumer claim chống bản tin trùng. **102 desktop + 32 isolated đạt**; chưa chạy integration PostgreSQL/broker. P1 chưa hoàn tất. Xem [REPORT_PRODUCTION_04.md](REPORT_PRODUCTION_04.md).


### Kết quả xác nhận cuối từ người dùng — 28/10/2026

Log attachment cdd91401-2be6-4fc1-b63c-7739068c1b11/Pasted text.txt ghi
**28 passed in 27.65s**, `tests-1 exited with code 0`. Bộ test API/PostgreSQL
và2 test Redis/Celery thật đã đạt. Xác minh duplicate đang chạy/sau hoàn tất và
outbox publish→consumer claim trong môi trường cách ly, provider/callback giả lập.
Chưa kiểm beat, process/broker restart, OCR/dịch thật, Windows hoặc deploy/LIVE.
Kết quả này thay thế trạng thái chờ chạy lại của các mục log trước đó.
