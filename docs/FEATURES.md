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
| E15 | Nhận biết **hướng chữ** (ngang/dọc/nghiêng/chưa rõ) kèm bằng chứng, hiện nhãn + bộ lọc + lý do đọc được, và đưa vùng khó vào rà soát thay vì lặng lẽ căn ngang | **LIVE phần nhận biết + giao diện** (Run A/C/D + 14/14 trên Chromium, dữ liệu thật) · ⛔ **dựng chữ dọc BLOCKED** — xem REPORT_E15 §9 |
| E1 | **Tiện ích Chrome** mở nhanh Translation từ trình duyệt: nút tạo chapter, xem trạng thái chapter đã ghim, nhảy thẳng vào màn rà soát/xuất — **không** đọc trang web bạn đang xem, **không** xin quyền website nào | **LIVE** (nạp thật vào Chromium 151, 41/41 mục đo — xem REPORT_E1) |
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

## Tiện ích Chrome — mở nhanh từ trình duyệt (E1)

Nạp thủ công từ thư mục `extension/` (`chrome://extensions` → Developer mode → Load unpacked).
Chưa phát hành lên Chrome Web Store.

**Làm được:**

- Bấm biểu tượng → Side Panel mở cạnh tab, không che web app.
- Nhập địa chỉ Translation local (chỉ `localhost` / `127.0.0.1` kèm cổng) và kiểm kết nối.
- **Tạo chapter mới** / **Mở Translation** → mở đúng màn của web app.
- Ghim tối đa **5 chapter** bằng mã, xem tên + trạng thái + số trang xuất được.
- **Xem tiến độ** / **Mở rà soát** (M7) / **Xuất** (M8) → nhảy đúng màn, không đi vòng qua M10.
- Xoá dữ liệu tiện ích — chỉ xoá trong trình duyệt, chapter và ảnh trong app **không** bị đụng.

**Cố ý KHÔNG làm** (đây là sự thật về sản phẩm, không phải thiếu sót tạm thời):

| Không làm | Vì sao |
|---|---|
| Đọc nội dung trang web đang xem | Không content script, `host_permissions` rỗng |
| Tải ảnh từ URL | Thuộc E2 — cần audit SSRF/nguồn/bản quyền riêng |
| Phủ bản dịch lên trang truyện | Thuộc E3 — cần content script + quyền từng site |
| Tải ảnh lên thẳng từ tiện ích | Upload vẫn đi qua form của web app |
| Nhớ API key / ảnh / chữ OCR / bản dịch | Xem `extension/PRIVACY.md` |
| Nối tới server LAN hoặc từ xa | Chỉ loopback |

**Hai giới hạn cần biết:**

- **Không tự thấy chapter.** Backend chưa có API liệt kê project (`GET /api/v1/projects` → 405),
  nên phải ghim bằng mã chép từ địa chỉ web app.
- **Bản dựng prod (nginx) chỉ mở link được.** nginx không chuyển tiếp `/api`, nên tiện ích không
  đọc được trạng thái — nó nói thẳng điều đó thay vì hiện danh sách rỗng. Bản docker dev
  (`127.0.0.1:5174`) thì đọc được ngay, không cần cấu hình gì.

## E15 — hai tầng kết luận (chốt 2026-08-30)

### E15-A — Orientation routing & UI: **CLOSED**

- Giao diện trạng thái/điều hướng hướng chữ hoàn chỉnh, dùng lại `StatusBadge` của E11 + khối
  giải thích theo khuôn E14.
- Huy hiệu hướng chữ **tách riêng** khỏi fit status (M6), quality (E12), consistency (E13) và
  safe-area (E14) — không gộp thành một icon.
- Có bộ lọc theo hướng chữ và bảng dịch mã lý do → diễn giải tiếng Việt (15 mã, khớp 1:1 với
  `LyDo.TAT_CA` của backend).
- Trạng thái "chưa kiểm / chưa xác định" hiển thị **riêng**, không bị gộp thành thành công.
- Run A (chữ ngang không hồi quy) và Run D (sửa tay + cảnh báo xuất) đạt.
- Đo giao diện trên Chromium đạt, số hiển thị **khớp CSDL**.
- Bộ hồi quy giữ xanh theo số đo thực tế tại thời điểm đóng (xem `TEST_LOG § E15.14`).

### E15-B — Dựng chữ dọc tiếng Việt: **BLOCKED (giới hạn bằng chứng ở tầng cấu trúc)**

Đây **không** phải chuyện thiếu ảnh mẫu. Chặn nằm ở tầng bằng chứng/hình học:

- `MangaOCREngine.recognize()` hiện chỉ trả `(text, None)`. Lớp này **không có**
  `recognize_with_layout`, nên hợp đồng OCR cho tiếng Nhật không mang theo hình học dòng chữ,
  metadata hướng chữ hay đa giác dòng nào.
- `analyzer` chỉ tới được `vertical_ttb` qua mã `ocr_line_geometry_vertical`. Không có nguồn đó
  thì **không có đường nào** đặt được `vertical_ttb + ready` — kể cả với ảnh tiếng Nhật hoàn hảo.
- Adapter CTD đang triển khai **không có** đường ghi kết quả hình học nào đã được kiểm chứng để
  thay thế nguồn trên.

**Phát hiện về môi trường:**

- RAQM trong worker: `False`.
- RAQM trong virtualenv của máy dev: `True`.

⇒ **Bất kỳ bộ dựng chữ dọc nào chỉ được kiểm trong virtualenv của máy dev đều KHÔNG có giá trị**
đối với đường dựng chữ thật đang chạy trong worker.

### Bảng năng lực

| Năng lực | Trạng thái |
|---|---|
| Thoại ngang (horizontal dialogue) | **Supported** |
| Nhận biết & điều hướng hướng chữ + giao diện | **Supported** |
| Điều hướng/rà soát SFX | **Supported**, nhưng mẫu thật hiện quá nhỏ để khẳng định rộng (n=9, `rotated_horizontal=0`) |
| Nhận biết/điều hướng chữ dọc có đủ bằng chứng | **Partial / chỉ để rà soát** |
| Dựng chữ dọc tiếng Việt | **Blocked** về mặt cấu trúc |
| Dựng chữ nghiêng/cách điệu | **Không hỗ trợ**; chỉ rà soát |
| E16 đặt chữ xoay | **Chưa được duyệt**; chưa đủ bằng chứng thật |

> **Run C là pass RỖNG.** 3/3 assertion đạt nhưng dữ liệu thật có **0** vùng chữ nghiêng trên
> n=9 — chúng chỉ chứng minh "không vùng nào vi phạm", **không** chứng minh đường xử lý chữ
> nghiêng đã được test thành công. Không được đọc thành "rotated text đã test xong".

## Lưu trữ ảnh: ảnh KHÔNG còn biến mất sau mỗi lần cập nhật (P3c → P3g)

Trước đây ảnh gốc, ảnh đã xoá chữ và ảnh xem thử **mất sạch mỗi lần hệ thống được cập nhật**,
trong khi dữ liệu chữ nghĩa thì còn nguyên — nên một trang ghi là "đã canh chữ xong" mà bấm xem
ảnh thì báo không còn. **Đã sửa xong và đã bật trên máy chủ** (31/08).

Đã dò ra nguyên nhân (P3c): nền tảng đang chạy **không cấp được ổ đĩa bền** để gắn vào chỗ chứa
ảnh. Đây là giới hạn của nền tảng, không phải lỗi cấu hình.

Đã làm được gì (P3d + P3e): **đã viết xong kho ảnh mới, đặt ảnh vào thẳng cơ sở dữ liệu** — nơi
duy nhất trên nền tảng này sống sót qua mỗi lần cập nhật. Gói dịch vụ 20 GB, hiện dùng 1,26 GB,
đủ chỗ cho khoảng **1.400 trang** nữa.

✅ **Đã bật trên máy chủ và đã thử đúng cách chắc chắn nhất:** tải một trang lên, chạy hết, rồi
**cập nhật lại hệ thống** — thao tác vốn xoá sạch ảnh — xong mở lại thì ảnh **vẫn còn**.

Nhưng chỉ cứu được **ảnh từ đó trở đi**. Những trang đã mất ảnh thì **không dựng lại được** vì ảnh
gốc đã không còn. Đã dọn riêng một lượt (P3f): **5 trang** cũ bị ảnh hưởng, nay được đưa về đúng
trạng thái thật (lùi về "đã đọc chữ xong", bỏ khai báo ảnh không tồn tại) — tức chúng **thôi nói
dối là đã xong**. Bản dịch và chữ đã đọc của những trang đó vẫn còn nguyên.

Kèm theo, hai thứ đã tốt lên ngay:

- **Xem ảnh đỡ tốn dữ liệu.** Mỗi lần mở lại ảnh xem thử, trình duyệt hỏi lại máy chủ; trước đây
  lần nào cũng tải nguyên ảnh ~3MB, nay nếu ảnh chưa đổi thì máy chủ chỉ trả lời "chưa đổi".
- **Không còn ảnh ghi dở.** Nếu quá trình ghi ảnh hỏng giữa chừng, bản cũ được giữ nguyên thay vì
  để lại một tệp cụt trông như ảnh thật.

~~Một đánh đổi: tải gói CBZ lớn mà đứt mạng giữa chừng thì phải tải lại từ đầu.~~ → **đã sửa**:
tải tiếp được như cũ. Đã thử thật trên máy chủ: tải một nửa, tải nốt nửa sau, ghép lại ra đúng
từng byte của tệp gốc và mở được thành ảnh.

Tốc độ thì đã đo trên máy chủ thật với một trang cỡ 6,7 MB: mở ảnh mất khoảng **0,11 giây**, mà
phần lớn là thời gian truyền qua mạng chứ không phải thời gian lấy ảnh ra khỏi cơ sở dữ liệu
(việc lấy chỉ tốn khoảng **0,005 giây**). Xem lại một ảnh đã xem rồi thì gần như tức thì vì máy
chủ chỉ trả lời "chưa đổi".

## Khỏi phải ngồi gõ tay từng thuật ngữ (E17)

Trước đây màn **Thuật ngữ của chapter** và **Giọng nhân vật** là hai ô trống: bạn phải tự nhớ
trong chapter có tên nhân vật nào, rồi gõ lại đúng nguyên văn từng cái. Với chapter 20 trang thì
đó là vài chục lượt gõ trước khi rà soát chạy được lần đầu.

Nay có nút **“Tìm trong chapter”**: máy đọc lại chữ đã nhận được rồi liệt kê những danh xưng lặp
lại, kèm **số lần xuất hiện, số trang, và câu trích nguyên văn**. Bấm một mục là mở luôn form
thêm thuật ngữ đã điền sẵn phần máy biết.

**Máy làm nửa việc, bạn giữ nửa còn lại:**

| Việc | Ai làm |
|---|---|
| Tìm ra trong chapter có danh xưng nào, ở đâu, bao nhiêu lần | **Máy** |
| Quyết dịch nó thành gì, xưng hô thế nào | **Bạn** |

Vì thế **cố ý không có nút “Duyệt tất cả”** — cách dịch là quyết định biên tập, máy điền vào đó
là chỗ bắt đầu của mọi sai lầm.

**Tìm cách xưng hô:** ở màn Giọng nhân vật có nút **“Tìm tín hiệu xưng hô”**. Máy chỉ ra những
tín hiệu **có thật trong bản gốc** — hậu tố kính ngữ tiếng Nhật (様, さん, ちゃん), đại từ nhân
xưng (俺, 僕, 私), chức danh tiếng Anh (Sir, Lord) — kèm câu gốc chứa nó, và gợi ý cách xưng hô
tiếng Việt tương ứng. Hệ thống **chưa biết ai nói câu nào**, nên đây là “trong chapter có tín
hiệu này”, không phải “nhân vật X xưng thế này với Y”.

**Nhập tên bộ truyện để được gợi ý cách dịch:** có, nhưng nó hoạt động khác cách bạn nghĩ, và
khác vì một lý do quan trọng. Hệ thống **không hỏi** mô hình “truyện này có nhân vật nào” — hỏi
thế thì mô hình **luôn trả lời, kể cả khi nó không biết**, và bạn sẽ nhận một dàn nhân vật nghe
rất thật nhưng không có trong chapter của bạn. Thay vào đó nó đưa mô hình **đúng danh sách danh
xưng vừa tìm được trong chapter bạn** và hỏi cách dịch quen thuộc. Mục nào mô hình trả về mà
chapter không có sẽ **bị loại thẳng**, và số mục bị loại được hiện ra cho bạn thấy.

Mọi gợi ý của mô hình đều mang nhãn **“gợi ý · chưa duyệt”** và không bao giờ tự thành thuật ngữ.

**Ba câu trả lời khác nhau khi không có gì hiện ra** — đọc kỹ, chúng không giống nhau:

| Máy nói | Nghĩa là |
|---|---|
| “Chưa đọc được chữ trong chapter” | Bước đọc chữ chưa xong. **Chưa kết luận được gì cả** |
| “Đã tìm, không thấy danh xưng nào lặp lại” | Đã quét thật, chapter không có |
| “Mọi danh xưng tìm được đều đã có trong danh sách” | Không còn gì mới để thêm |

⚠️ **Chưa cập nhật lên máy chủ.** Phần này mới xong trên máy phát triển, và **chưa từng chạy thử
với chữ của một chapter thật** — mới kiểm bằng dữ liệu dựng sẵn. Riêng phần gợi ý theo tên bộ
truyện thì **chưa từng gọi mô hình thật lần nào**.

Vài giới hạn nói trước cho khỏi bất ngờ:

- **Tiếng Trung nhiễu hơn hẳn** tiếng Nhật/Anh, vì không có khoảng trắng và không có chữ hoa.
- **Tên chỉ từng đứng đầu câu** (trong truyện tiếng Anh chữ thường) sẽ không tìm ra — đầu câu thì
  từ nào cũng viết hoa, không phân biệt được với danh từ thường.
- **Chữ đọc sai thì gợi ý sai.** Những vùng máy tự khai đọc chưa chắc chắn bị bỏ qua, và số vùng
  bị bỏ được hiện ra chứ không giấu.

## Vì sao chạy nhiều trang liên tiếp lại làm hệ thống "đứng hình" (P3h)

Chạy thử **6 trang liên tiếp** trên máy chủ ngày 31/08: bộ phận xử lý ảnh bị hệ điều hành **giết
vì hết bộ nhớ**, hệ thống chậm dần từ vài mili-giây lên hàng chục giây rồi im hẳn. Một trang thì
không sao — đúng sáu trang liên tiếp mới lộ.

**Nguyên nhân đã tìm ra, không phải "máy yếu":** phần xoá chữ xử lý từng cụm bong bóng một, mỗi
cụm một kích thước khác nhau, và thư viện AI **giữ lại một vùng nhớ riêng cho mỗi kích thước mới
mà không bao giờ trả lại**. Càng nhiều bong bóng, càng nhiều trang thì càng phình, tới lúc bị giết.

Đã sửa: tắt cơ chế giữ nhớ đó cho phần xoá chữ (giữ nguyên cho phần nhận diện khung chữ vì ở đó
nó vô hại và còn nhanh hơn), ghép ảnh theo từng dải ngang thay vì cả trang một lúc (**giảm 80 %
bộ nhớ đỉnh, ảnh ra giống nhau từng điểm ảnh**), và thêm chỗ **nhìn thấy mức bộ nhớ** — trước đây
hệ thống không có một chỉ số bộ nhớ nào, nên không ai thấy gì cho tới lúc nó chết.

⚠️ **Chưa cập nhật lên máy chủ, nên chưa dùng được.** Bản sửa mới xong và mới kiểm trên máy phát
triển. Tính tới **31/08 19:10, máy chủ đang không phản hồi** (cả trang web lẫn phần xử lý, kể cả
trang tĩnh không dính AI) — đây là sự cố ở tầng nhà cung cấp máy chủ, không phải hệ thống lại hết
bộ nhớ lần nữa. Chừng nào máy chủ chưa sống lại và chưa chạy lại đúng bài thử 6 trang thì
**không được coi là đã chữa xong**.

Trong lúc đó, **chạy cả chapter nhiều trang trên máy chủ vẫn là việc nên tránh.**

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
- **Nếu máy chủ hết bộ nhớ giữa chừng**, việc đang chạy vẫn treo mãi ở trạng thái “đang chạy” mà
  không báo lỗi. P3h **chưa sửa điều này** — nó chỉ làm cho việc hết bộ nhớ **ít xảy ra hơn** và
  **nhìn thấy được** (số lần bộ phận xử lý bị giết nay hiện ở đường kiểm tra sức khoẻ). Trang bị
  kẹt vẫn phải xử bằng tay.
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
- Chưa lưu ảnh lên Supabase Storage. Ảnh **không** còn nằm trên ổ đĩa máy chủ nữa mà nằm trong
  cơ sở dữ liệu (P3e) — đó là nơi duy nhất trên nền tảng này sống sót qua mỗi lần cập nhật.

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

## Nhắc thuật ngữ trước khi mang file đi (P3i)

Trước đây, nếu bạn chưa khai thuật ngữ nào thì màn hình trước khi tải file **không nói gì cả** —
và tên riêng có thể đã bị dịch theo nghĩa đen từ lâu mà bạn không biết. Chạy thử thật trên máy chủ
ngày 03/09 bắt được đúng chuyện đó: một nhân vật tên **Pepper** biến thành **"Hạt tiêu"**.

Nay màn hình đó nói thẳng: *"Chưa chốt thuật ngữ nào cho chapter này — tên nhân vật, vật phẩm,
chiêu thức có thể đang bị dịch theo nghĩa đen"*, kèm luôn ví dụ để bạn nhận ra vấn đề mà không
phải đọc tài liệu.

Nó **không chặn** bạn xuất file — chỉ nói cho bạn biết trước khi mang đi.

## Cho người khác cùng dùng, mà không ai đụng vào chapter của ai (B1)

Trước đây hệ thống chỉ có **một khoá chung**. Đưa khoá cho người khác nghĩa là đưa luôn quyền
đọc, sửa và **xoá** mọi chapter — kể cả của bạn. Nên thực tế là không đưa được cho ai.

Giờ mỗi người một tài khoản riêng:

- **Đăng nhập bằng email + mật khẩu.** Nhớ trong 14 ngày, không phải gõ lại mỗi lần.
- **Chapter bạn tạo là của bạn.** Người khác đăng nhập vào cùng hệ thống sẽ không thấy nó, và
  cũng không mở được kể cả khi có đường dẫn đầy đủ.
- **Đăng xuất là mất hiệu lực ngay**, kể cả trên máy khác.

### Tạo tài khoản cho người khác

Tự đăng ký thì cần **khoá chung của hệ thống** — hỏi người quản trị. Chủ ý là vậy: không có nó
thì ai mở được địa chỉ web cũng tự tạo tài khoản và dùng hạ tầng của bạn.

Tài khoản **đầu tiên** của hệ thống là tài khoản quản trị.

### Chapter làm từ trước thì sao

Chapter tạo trước bản này **không thuộc về ai cả** — lúc đó chưa có tài khoản nào để ghi vào.
Chúng không bị giấu đi và cũng không bị gán bừa cho ai: mọi người đăng nhập đều thấy, kèm nhãn
*chưa có chủ*, và bấm **nhận** là về mình. Nhận rồi thì người khác không mở được nữa.

### Những gì bản này CHƯA có

- **Đổi mật khẩu và quên mật khẩu.** Quên là phải nhờ người quản trị sửa thẳng trong CSDL.
- **Chia sẻ một chapter cho hai người cùng làm.** Mỗi chapter đúng một chủ.
- **Khoá tài khoản từ giao diện.** Phải sửa tay trong CSDL.
- **Chặn dò mật khẩu.** Mỗi lần thử tốn 83ms nên dò rất chậm, nhưng chưa có khoá tạm sau N lần sai.
