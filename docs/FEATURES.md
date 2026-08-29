# FEATURES.md — Translation

Tool dịch manga **EN/JP/CN → Tiếng Việt**: tự nhận diện khung chữ (bubble/box), xóa chữ gốc,
dịch theo mạch văn, tự canh cỡ chữ cho vừa khung, cho sửa tay rồi xuất chapter.

> Quy ước đọc bảng: **LIVE** = đã chạy thật và verify · **BUILT** = có code, chưa verify thật ·
> **CHƯA** = chưa làm (thuộc mini-spec ghi kèm). Không đánh dấu LIVE nếu chưa chạy thật một lần.

## Trạng thái theo mini-spec

| ID | Tính năng | Trạng thái |
|---|---|---|
| M1 | Data model 7 bảng + migration 2 chiều + API contract `/api/v1` + interface 5 engine | **LIVE** |
| M2 | Nhận diện khung chữ (comic-text-detector) → `TextRegion` + confidence | **LIVE** (đo trên ảnh tổng hợp; ảnh manga thật chưa đo — xem TEST_LOG) |
| M3 | OCR theo ngôn ngữ nguồn (manga-ocr cho `ja`, PaddleOCR cho `zh`/`en`) | **LIVE** (đo trên ảnh tổng hợp — provisional, xem TEST_LOG) |
| M4 | Xoá chữ gốc bằng LaMa → ảnh clean (giữ nguyên ảnh gốc) | **LIVE** (đo trên ảnh tổng hợp — provisional, xem TEST_LOG) |
| M5 | Dịch 2 đường: `google_fast` (miễn phí) và `llm_context` (giữ mạch văn cả trang) + reading order | **LIVE** (đo trên ảnh tổng hợp thoại tiếng Anh; manga thật + tiếng Nhật chưa đo — xem TEST_LOG) |
| M6 | Tự tính cỡ chữ + xuống dòng cho vừa bubble (đo font-metrics thật) | **LIVE** (đo trên ảnh tổng hợp; manga thật chưa đo — xem TEST_LOG) |
| M7 | Màn sửa tay: sửa bản dịch, kéo lại khung, đổi font/size | **LIVE** (thao tác thật trên trình duyệt; xem TEST_LOG) |
| M8 | Xuất chapter PNG/CBZ + lưu/mở lại project | **LIVE** (xuất thật 4 trang; chưa mở bằng app đọc truyện thật) |
| M9 | Chạy **cả chapter bằng một mẻ**: tiến độ thật, thử lại lỗi tạm thời, cổng hạn mức, chạy lại trang hỏng | **LIVE** (4 Run bắt buộc trên truyện thật; giao diện chưa bấm tay — xem TEST_LOG §M9) |
| E13 | Chốt cách dịch thuật ngữ cho cả chapter, ghi hồ sơ giọng nhân vật, rà soát từng chỗ chưa theo thuật ngữ đã chốt — máy chỉ ra chỗ kèm lý do, **không tự sửa** | **LIVE** (Run A–D trên truyện thật + Chromium 17/17 — xem TEST_LOG §E13) |
| E14 | Tìm **lòng bong bóng thật** rồi căn chữ vào đó thay vì vào khung chữ nhật; không chắc thì nói thẳng là đang dùng khung dự phòng | **LIVE** (5/5 bong bóng thật, 0 chọn nhầm, 5/5 chữ nằm trọn trong bong bóng — xem TEST_LOG §E14) |
| E15 | Nhận biết **hướng chữ** (ngang/dọc/nghiêng/chưa rõ) kèm bằng chứng và đưa vùng khó vào rà soát thay vì lặng lẽ căn ngang | **LIVE phần nhận biết** — giao diện chưa dựng, **dựng chữ dọc cố ý để TẮT** (chưa có ảnh mẫu hợp pháp); xem REPORT_E15 |
| M10 | Khai báo mục đích sử dụng (bắt buộc, không mặc định) + nhắc trách nhiệm bản quyền & chất lượng trước khi xuất | **LIVE** (chạy thật đầu-cuối; giao diện chưa bấm tay — xem TEST_LOG §M10) |
| E11 | Làm lại giao diện: bố cục, bộ màu, vùng kéo-thả, dòng thời gian pipeline, diễn giải trạng thái trung thực, dùng được bằng bàn phím và trên điện thoại | **LIVE** (kiểm thật trên Chromium ở 4 kích thước — xem TEST_LOG §E11) |
| E12 | Chỉ ra vùng nào cần rà soát trước khi xuất, kèm lý do đọc được — không tự xoá vùng nào | **LIVE** (Run A–D 15/15 trên trang thật + Chromium 10/10 — xem TEST_LOG §E12) |

## Những gì dùng được ngay hôm nay (sau E12)

- Tạo project dịch (chọn ngôn ngữ nguồn, mục đích sử dụng) qua API/Swagger.
- Upload từng trang ảnh: file được lưu thật, trang vào hàng đợi và **worker tự động nhận diện khung chữ**.
- Xem danh sách khung chữ đã nhận diện của từng trang: toạ độ khung + độ tin cậy + cảnh báo.
  Khung độ tin cậy thấp vẫn hiện (đánh dấu `low_confidence`), khung chồng nhau bị gắn cờ `overlap_suspect`.
- Xem trạng thái trang (`queued → detecting → detected | detection_failed`) và trạng thái việc.
- Chạy lại nhận diện cho 1 trang bằng `POST /pages/{id}/retry-detect` (không tạo khung trùng lặp).
- **Tự đọc chữ trong từng khung** ngay sau khi nhận diện xong (không phải bấm thêm nút):
  tiếng Nhật dùng manga-ocr, tiếng Trung/Anh dùng PaddleOCR theo ngôn ngữ nguồn của project.
- Xem chữ đã đọc được của từng khung qua `GET /pages/{id}/ocr`; vùng đọc không ra chữ được
  đánh dấu `needs_manual` để sửa tay sau, **không bị giấu đi**.
- **Tự xoá chữ gốc khỏi ảnh** ngay sau khi đọc xong, tạo ra ảnh "sạch" để lát nữa chèn chữ dịch.
  Xem/tải ảnh sạch qua `GET /pages/{id}/clean-image`. **Ảnh gốc luôn được giữ nguyên** thành file riêng.
- Hệ thống tự kiểm lại việc xoá bằng cách đọc lại đúng vùng vừa xoá: còn chữ thì trang bị đánh dấu
  `inpaint_needs_review` chứ không âm thầm coi là xong.
- **Dịch cả trang sang tiếng Việt** ngay sau khi xoá chữ xong, theo **đúng thứ tự đọc** của loại truyện
  (manga Nhật đọc phải→trái, truyện Anh/Trung đọc trái→phải) — thứ tự sai là hỏng mạch văn cả trang.
- **Chọn được cách dịch, biết trước cái nào tốn tiền:**
  - `google_fast` — **miễn phí**, dịch từng dòng, không nhìn ngữ cảnh câu trước sau.
  - `llm_context` — gộp cả trang gửi Gemini nên giữ được mạch văn và tự sửa lỗi đọc chữ, **có tốn token**.
  - Mặc định là bản **miễn phí**: hệ thống không bao giờ tự tiêu tiền của bạn khi bạn chưa chọn.
    Đổi bằng `POST /pages/{id}/retry-translate?engine=llm_context`.
- Xem bản dịch từng khung qua `GET /pages/{id}/translation`, kèm **số token đã tiêu thật** của trang đó.
- Nếu bên dịch AI hỏng hoặc hết lượt, hệ thống **tự lùi về bản miễn phí và dán nhãn `fallback_used`** —
  không bao giờ trả về bản dịch rỗng rồi báo là xong. Dòng nào AI không trả thì để `pending`.
- **Tự chèn chữ dịch vào đúng bong bóng** ngay sau khi dịch xong: hệ thống tự chọn cỡ chữ lớn nhất mà
  vẫn vừa khung, tự xuống dòng, căn giữa — và **xem được ngay bằng ảnh** qua
  `GET /pages/{id}/typeset-preview`. Đây là lần đầu có **trang truyện tiếng Việt hoàn chỉnh** để nhìn.
- **Chữ quá dài không bị bóp bé tí cho vừa**: xuống tới cỡ nhỏ nhất mà vẫn không vừa thì vùng đó được
  đánh dấu **cảnh báo tràn khung** (viền đỏ trên ảnh xem thử) để người biên tập sửa tay ở bước sau,
  chứ hệ thống không tự làm chữ bé đến mức không đọc nổi.
- **Không bao giờ ra ô vuông**: nếu font thiếu chữ có dấu tiếng Việt, hệ thống báo lỗi rõ thay vì vẽ
  ô vuông rồi báo thành công.
- **Ảnh gốc và ảnh sạch vẫn nguyên vẹn** — ảnh xem thử là file thứ ba, tách riêng.
- **Có màn hình để sửa tay** (giao diện đầu tiên của dự án, mở ở cổng 5174): nhìn thấy trang truyện
  đã chèn chữ, các khung chữ vẽ chồng lên ảnh, và bảng sửa cho từng vùng.
  - Sửa **bản dịch**, đổi **kiểu chữ**, **ghim cỡ chữ** nếu không ưng cỡ máy tự chọn.
  - **Kéo và co giãn khung chữ** ngay trên ảnh bằng chuột.
  - Bấm lưu là hệ thống **canh lại đúng vùng đó** rồi vẽ lại ảnh — không tính lại cả trang.
  - Có nút **đọc lại chữ gốc** và **dịch lại** cho riêng từng vùng.
- **Không giấu cảnh báo**: mỗi vùng hiện nhãn bằng chữ (“Tràn khung”, “Cần đọc lại”,
  “Khung kém tin cậy”) và có ô bật/tắt để tô cảnh báo lên ảnh.
- **Biết chỗ nào người sửa, chỗ nào máy làm**: mỗi vùng ghi rõ “máy dịch / đã sửa tay”.
- **Xuất cả chapter thành file giao được**: chọn **CBZ** (1 file, mở bằng app đọc truyện tranh),
  **ZIP**, hoặc **PNG** từng trang. Bấm xuất rồi tải về ngay trên màn hình.
- **Xem trước cảnh báo trước khi xuất**: sẽ xuất mấy trang, bỏ qua mấy trang chưa chèn chữ xong,
  còn mấy vùng chữ tràn khung — để bạn chọn xuất luôn hay sửa tay trước.
- **Trang chưa chèn chữ xong thì bỏ qua**, không xuất ảnh trắng không chữ; số trang bỏ qua được nói rõ.
- **Xuất lại bao nhiêu lần cũng được**, file cũ tự bị dọn, không đầy ổ đĩa. Dữ liệu gốc giữ nguyên
  nên sửa tiếp rồi xuất lại thoải mái.

## Những gì **chưa** dùng được (nói thẳng để không hiểu nhầm)

- **Chưa có đăng nhập**: ai mở được đường link là sửa được, và hệ thống chỉ ghi “có người sửa”
  chứ không ghi **ai** sửa.
- **Chưa lùi lại được**: sửa là đè lên bản cũ, không có lịch sử phiên bản. Dữ liệu gốc (khung chữ,
  chữ OCR, bản dịch máy) thì vẫn giữ để đối chiếu.
- **Chưa sửa được nhiều vùng cùng lúc.**
- **Chưa kéo khung được bằng bàn phím** — thao tác kéo khung hiện chỉ dùng chuột được.
- **File CBZ chưa được mở thử bằng app đọc truyện thật** (Tachiyomi/Perfect Viewer) — mới kiểm bằng
  công cụ giải nén, đúng cấu trúc và đúng thứ tự trang.
- **Xuất bằng bản dịch miễn phí có thể ra chữ chưa dịch**: nếu bước đọc chữ dính hai từ vào nhau
  (`IT IS` → `ITIS`), bản miễn phí sẽ để nguyên tiếng Anh. Hệ thống **chưa cảnh báo** điều này trước
  khi xuất — muốn chắc thì dịch lại bằng bản có ngữ cảnh rồi hãy xuất.
- **Nếu máy chủ hết bộ nhớ giữa chừng**, việc đang chạy sẽ treo mãi ở trạng thái “đang chạy” mà
  không báo lỗi — phải nhìn log mới biết.
- Chưa có giao diện người dùng — mới chỉ có Swagger để thao tác tay; chưa có ảnh vẽ khung để nhìn bằng mắt (M7).
- **Đã đo trên truyện tranh thật** (Pepper&Carrot, giấy phép mở): tìm đúng 3/3 bong bóng thoại,
  đọc chữ đúng 3/3, chèn chữ vừa khung 5/5. **Nhưng chưa thử manga Nhật** (chữ dọc, đọc phải→trái).
- **Nhận nhầm khoảng 2/7 vùng** trên ảnh thật (cây chổi, vệt sáng bị tưởng là chữ). Không lọt vào
  bản dịch vì độ tin cậy thấp, nhưng người biên tập vẫn phải bỏ qua bằng tay.
- **Dòng ghi công của tác giả bị coi là chữ cần dịch** — cần luật loại trừ vùng ở rìa trang.
- **Chữ chỉ nằm ngang**: chưa hỗ trợ chữ dọc, chữ xoay nghiêng hay chữ tượng thanh (SFX) cách điệu.
- **Bong bóng dẹt có thể bị chạm mép**: hệ thống tính theo khung chữ nhật bao quanh bong bóng, nên với
  bong bóng rất dẹt chữ vẫn có thể chạm mép cong. Chưa gặp trên ảnh mẫu, cần thử ảnh thật.
- **Đường dịch tiếng Nhật (phải→trái) chưa chạy thật đầu-cuối** — mới verify bằng test tự động.
- Nhiều API key **không** làm tăng hạn mức nếu các key thuộc cùng một project Google
  (Gemini tính giới hạn theo project, không theo key).
- Tự thử lại **chỉ** với lỗi tạm thời (mạng, quá nhịp, 5xx) và **có trần** 3 lần. Lỗi vĩnh viễn
  (thiếu font, thiếu model, mất ảnh) hỏng ngay — thử lại chỉ tốn thời gian.
- Chưa tự thử lại khi **chất lượng** kém (đọc sai, dịch sai, xoá chữ chưa sạch) — đó không phải
  lỗi hạ tầng, vẫn phải sửa tay ở màn sửa.
- Chưa lưu ảnh lên Supabase Storage (đang lưu trên ổ đĩa của server).

## Chỉ ra chỗ cần rà soát (E12)

- Sau khi căn chữ xong, hệ thống **tự chấm từng vùng chữ** rồi nói rõ vùng nào nên xem lại và
  **vì sao** — bằng câu tiếng Việt, không phải mã kỹ thuật.
- Ví dụ lý do: *"OCR không đọc được nội dung"*, *"Khung chữ có điểm nhận diện thấp"*,
  *"Bản dịch dài bất thường so với chữ gốc"*, *"Chữ dịch chưa vừa khung"*,
  *"Có thể là số hoặc ký hiệu trang trí"*.
- Mỗi vùng được xếp vào một trong bốn nhóm: **có khả năng là chữ cần dịch**, *có thể là hiệu ứng
  âm thanh*, *có thể là số/trang trí*, *chưa chắc*. Máy chỉ nói "có thể" — **quyết định là của bạn**.
- Hai nút ở màn sửa tay: **Giữ để dịch** và **Bỏ qua vùng này**. Bỏ qua chỉ ghi lại quyết định —
  khung chữ, chữ gốc và bản dịch **vẫn được giữ nguyên**, không xoá gì.
- **Không tự bỏ** tiếng động, số trang hay chữ viết hoa. `NO!`, `PHEW!`, `18` đều có thể là chữ
  cần dịch tuỳ truyện.
- Vùng **chưa được đánh giá** được đếm riêng, không bao giờ bị coi là "sạch".
- Với engine OCR không trả điểm tin cậy (tiếng Nhật), hệ thống nói đúng là *"engine không cung cấp
  điểm tin cậy"* — **không** hiện thành 0%.
- Hộp thoại xuất hiện thêm ba số: bao nhiêu vùng cần rà soát, bao nhiêu chưa đánh giá, bao nhiêu
  bạn đã chủ động bỏ qua — **tách riêng** khỏi phần nhắc trách nhiệm bản quyền.
- Đây là kết quả của một **bộ luật đọc bằng chứng**, không phải lời bảo đảm dịch đúng nghĩa.

## Giao diện & luồng thao tác (E11)

- **Trang chủ nói rõ tool làm gì**: tiêu đề, mô tả một câu, và form tạo chapter chia **3 bước
  đánh số** (thông tin → chọn trang → bắt đầu).
- **Chọn ảnh bằng cách kéo-thả hoặc bấm**, kèm danh sách trang có số thứ tự, dung lượng và nút bỏ
  từng trang. Dùng được **hoàn toàn bằng bàn phím** (Enter/Space mở hộp chọn tệp).
- **Nút bị mờ luôn nói vì sao** ngay bên dưới: "Cần đặt tên cho chapter", "Cần chọn ít nhất một
  ảnh PNG hoặc JPG"…
- **Dòng thời gian xử lý** cho cả chapter: tải lên → nhận diện → đọc chữ → xoá chữ → dịch → căn
  chữ, mỗi bước ghi rõ **bao nhiêu/bao nhiêu trang** đã qua. Không có thanh phần trăm giả.
- **Mọi trạng thái có nhãn tiếng Việt + icon**, không chỉ dựa vào màu. Trạng thái mà giao diện
  chưa biết thì hiện "Trạng thái chưa được hỗ trợ" chứ không bị coi là đã xong.
- **Căn chữ xong mà còn vùng lỗi thì KHÔNG gọi là hoàn tất** — hiện "Đã căn chữ, còn vùng cần sửa"
  kèm số vùng, và nút "Mở để rà soát" được ưu tiên hơn nút xuất.
- **Chờ việc chạy nền một cách trung thực**: nói rõ "đang chờ tới lượt — máy chủ đang bận việc
  khác", và nếu quá lâu thì nói "vẫn đang chạy" chứ không báo hỏng.
- **Dùng được trên điện thoại** (360px) tới màn rộng (1600px), không phải cuộn ngang.
- Khi sửa tay có **đường dẫn phân cấp** và nút chuyển **trang trước / trang sau**.

## Khai báo mục đích & nhắc trách nhiệm (M10)

- Tạo chapter **bắt buộc tự khai mục đích sử dụng** (đọc cá nhân / học tập / khác). Hệ thống
  **không chọn hộ** — ô này để trống tới khi bạn chọn, và nút tạo chưa bấm được.
- Khai báo hiện ở màn chapter và **không sửa được** về sau.
- Lần đầu xuất một chapter, hệ thống hiện một nhắc gọn: bạn chịu trách nhiệm về bản quyền nội
  dung gốc, công cụ dành cho mục đích cá nhân/học tập, file chỉ nằm trên máy bạn — hệ thống
  **không** tự đăng công khai hay chia sẻ cho ai.
- Cùng lúc đó hiện luôn **chất lượng bản sắp xuất**: bao nhiêu vùng chữ tràn ra ngoài bong bóng,
  bao nhiêu bong bóng sẽ **trống** vì chưa đọc được chữ gốc.
- Tick ô xác nhận thì nút xuất mới sáng. **Không chặn** bạn — tick là xuất được ngay, và việc tick
  được ghi lại kèm đúng những con số vừa hiện.
- Nhắc chỉ hiện **một lần cho mỗi chapter**, lần sau xuất đi thẳng.
- Nhật ký chỉ lưu **số liệu** (mục đích đã khai, số vùng lỗi, thời điểm xác nhận) — **không** lưu
  nội dung, ảnh hay bản dịch của bạn.
- **Không** watermark, **không** khoá file: chúng không giúp gì cho việc tuân thủ bản quyền thật,
  chỉ làm hỏng ảnh của chính bạn.

## Chạy cả chapter (M9)

- Một nút **Chạy cả chapter**: chọn cách dịch (nhanh & miễn phí, hoặc theo ngữ cảnh), hệ thống
  chạy lần lượt mọi trang qua đủ các bước.
- **Danh sách trang được chụp lại ngay lúc bấm** — trang tải lên sau đó không lẫn vào mẻ đang chạy,
  nên tổng số trang không nhảy lung tung giữa chừng.
- Mỗi trang **tiếp tục từ đúng bước nó đang dừng**; trang đã xong được bỏ qua chứ không làm lại.
- Tiến độ nói thật: bao nhiêu trang xong / hỏng / bị chặn vì hết lượt gọi, đang làm tới trang nào.
  **Không bao giờ hiện 100% khi còn trang chưa xong.**
- Lỗi tạm thời (mạng chập chờn, nhà cung cấp quá tải) tự thử lại, có chờ giãn dần, tối đa 3 lần.
- Hết lượt gọi ⇒ báo rõ **"bị chặn vì hạn mức"** chứ không báo hỏng, và **không** gọi thêm lần nào
  ra nhà cung cấp. Hạn mức hồi thì bấm **Chạy lại** là chạy tiếp đúng những trang đó.
- Máy chủ bị khởi động lại giữa chừng vẫn cứu được: bấm Chạy lại là mẻ đi tiếp, không làm lại
  trang đã xong và không tạo file trùng.
- **Dừng mẻ**: không đẩy thêm trang mới, trang đang chạy vẫn chạy nốt cho khỏi dở dang.
- Mẻ **không tự xuất chapter** — xuất vẫn là việc bạn chủ động bấm, để không phát hành nhầm bản
  còn tràn khung.
