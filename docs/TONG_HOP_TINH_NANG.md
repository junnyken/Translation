# Tổng hợp năng lực — Tool dịch truyện tranh (Translation)

> **Tài liệu này viết để một trợ lý AI khác đọc và đề xuất hướng nâng cấp.** Nó tự đứng vững,
> không cần bối cảnh hội thoại nào khác.
>
> **Ngày chốt số liệu: 24-09-2026.** Mọi con số về API và hiệu năng ở đây **đo từ bản đang chạy
> thật trên production**, không chép từ tài liệu nội bộ.

---

## 1. Sản phẩm này là gì

Công cụ dịch truyện tranh (manga/manhua/comic) **EN · JA · ZH → Tiếng Việt**, chạy tự động cả
chuỗi: nhận diện khung chữ → đọc chữ → **xoá chữ gốc khỏi ảnh** → dịch theo mạch văn → tự canh cỡ
chữ cho vừa bong bóng → cho sửa tay → xuất cả chapter.

**Đây là công cụ nội bộ của một đội**, không phải SaaS bán cho người ngoài: có đăng nhập, không có
gói cước, không có hạn mức tính tiền.

### Ngăn xếp

| Tầng | Công nghệ |
|---|---|
| API | FastAPI + SQLAlchemy 2.0 (async) + Alembic |
| CSDL | PostgreSQL (managed) |
| Hàng đợi | Redis + Celery (`--pool=solo`) |
| Giao diện | React + Vite (SPA), phục vụ bằng nginx |
| Triển khai | Docker, hosting VibeHost |

### Các mô hình AI đang dùng

| Bước | Mô hình | Ghi chú |
|---|---|---|
| Nhận diện khung chữ | `comic-text-detector` (ONNX, CPU) | weight độc lập, không nhúng code GPL |
| Đọc chữ (OCR) | `manga-ocr` cho `ja` · `PaddleOCR` cho `zh`/`en` | chọn theo ngôn ngữ nguồn của chapter |
| Xoá chữ gốc | `LaMa` (ONNX, CPU) | sinh ảnh "sạch", **ảnh gốc luôn giữ nguyên** |
| Dịch | `google_fast` (miễn phí) hoặc `llm_context` (Gemini) | người dùng tự chọn, mặc định miễn phí |
| Canh chữ | Đo font-metrics thật (Pillow) | 4 font SIL OFL đã đo đủ 134 ký tự có dấu tiếng Việt |

---

## 2. Bề mặt API và các giá trị hợp lệ

Đo từ `openapi.json` của production, 24-09-2026:

- **78 đường dẫn · 83 thao tác**
- Nhóm lớn nhất: `pages` (17), `glossary` (15), `auth` (8), `batch` (7), `projects` (6)

| Tham số | Giá trị hợp lệ |
|---|---|
| Ngôn ngữ nguồn | `ja` · `zh` · `en` |
| **Ngôn ngữ đích** | **`vi` — CHỈ tiếng Việt** |
| Định dạng xuất | `png_single` · `cbz` · `zip` |
| Engine dịch | `google_fast` · `llm_context` |
| Mục đích sử dụng | `personal` · `study` · `other` (bắt buộc khai, không mặc định) |

---

## 3. Năng lực hiện có

### 3.1. Hai đường vào, song song

**A — "Dịch nhanh"** *(mặc định)*: một màn duy nhất. Chọn ngôn ngữ gốc + cách dịch + mục đích sử
dụng, thả file, xong **tự tải về**. Không đặt tên chapter, không tải từng trang, không tự bấm xuất.

**B — "Tạo chapter mới"**: đường đầy đủ, có rà soát, sửa tay, chốt thuật ngữ trước khi xuất.

### 3.2. Đầu vào

- Ảnh lẻ: PNG · JPG · WebP
- **Cả gói `.zip` / `.cbz`** — một chapter là một thao tác thay vì 24
- **PDF** — mỗi trang được **dựng lại thành ảnh** ở cạnh dài 1600px (không trích ảnh nhúng, vì
  trang có chữ vector thì trích ảnh sẽ mất chữ mà không báo lỗi)
- Thứ tự trang trong gói sắp bằng **khoá tự nhiên** (`p2` trước `p10`)
- Chặn sẵn: bom giải nén, đường dẫn thoát thư mục, gói lồng gói, ảnh cụt (thiếu dấu kết thúc
  JPEG/PNG)

### 3.3. Xử lý

- Chạy tự động một mạch qua 5 bước, không cần bấm giữa chừng
- **Chạy cả chapter bằng một mẻ**: tiến độ thật, thử lại lỗi tạm thời, chạy lại riêng trang hỏng
- Thứ tự đọc theo loại truyện (manga Nhật phải→trái, EN/ZH trái→phải); suy theo ngôn ngữ nguồn,
  ép được bằng cấu hình
- Tự kiểm lại việc xoá chữ bằng cách **đọc lại đúng vùng vừa xoá** — còn chữ thì đánh dấu cần rà
  soát chứ không âm thầm coi là xong
- Chống đẩy job trùng (một trang từng bị dịch 2 lần, lãng phí token)

### 3.4. Chất lượng dịch

- **Hai engine, người dùng tự chọn, hiện rõ cái nào tốn tiền.** Mặc định là bản miễn phí — hệ
  thống không bao giờ tự tiêu tiền khi chưa được chọn
- `llm_context` gộp cả trang gửi LLM nên giữ được mạch văn và tự sửa lỗi đọc chữ
- Nối **bảng thuật ngữ + hồ sơ giọng nhân vật đã duyệt** vào prompt để dịch nhất quán xuyên trang
- Câu bị ngắt giữa hai dòng được dịch nguyên câu
- **Tiếng động (SFX) giữ nguyên**, không dịch bậy
- Engine AI hỏng hoặc hết lượt thì **tự lùi về bản miễn phí và dán nhãn `fallback_used`** — không
  bao giờ trả bản dịch rỗng rồi báo là xong
- Ghi lại **số token tiêu thật** của từng trang

### 3.5. Canh chữ

- Tính cỡ chữ + xuống dòng bằng đo font-metrics thật
- Tìm **lòng bong bóng thật** rồi căn chữ vào đó, thay vì căn vào khung chữ nhật
- Nới khung tới khi chạm nét vẽ; bản dịch dài quá thì **dịch lại ngắn hơn cho vừa**
- Ô đặt chữ không trùm lên khung chữ của vùng khác
- Nhận biết hướng chữ (ngang/dọc/nghiêng) kèm bằng chứng; **đặt được chữ nghiêng**

### 3.6. Rà soát và sửa tay

- Sửa bản dịch, **gõ đè chữ OCR đọc sai**, kéo lại khung, đổi font/cỡ
- Phóng to đối chiếu với **ảnh gốc chưa xoá chữ**
- Hàng đợi rà soát chỉ ra vùng nào cần xem lại **kèm lý do đọc được** — không tự xoá vùng nào
- Gợi ý thuật ngữ & danh xưng rút từ chính chapter, đối chiếu CSDL nhân vật AniList
- Cảnh báo trước khi xuất: tràn khung, vùng chưa rà soát, chưa chốt thuật ngữ

### 3.7. Xuất

- `zip` · `cbz` · `png_single`
- Trang **không có chữ** vẫn nằm trong file xuất (trang tranh thuần không bị loại)
- Gộp nhiều chapter vào một file

### 3.8. Vận hành & an toàn

- Đăng nhập bắt buộc, gắn ở **tầng router** cho toàn bộ `/api/v1`
- Chapter có chủ sở hữu; có bài test **tự sinh** dò quyền chéo tài khoản trên mọi endpoint, và nó
  **đỏ khi phép dò rỗng nghĩa** (không cho "không chứng minh được" trôi qua như "an toàn")
- Khai báo mục đích sử dụng bắt buộc + nhắc trách nhiệm bản quyền
- Job mồ côi sau khi worker chết được dọn khi worker khởi động lại
- Trần bộ nhớ cho bước xoá chữ (đã từng bị OOM giết worker)

---

## 4. Số đo thật

### Production, 24-09-2026

Một trang (1600×2213) chạy trọn `queued → typeset_done`: **100 giây**, tìm được 2 vùng chữ.

### Máy phát triển (CPU, chậm hơn production)

| Bước | Thời gian/trang |
|---|---|
| Nhận diện khung chữ | 42–70 s |
| Đọc chữ (PaddleOCR, `en`) | ~8 s |
| Xoá chữ gốc | ~19 s |
| Dịch (`google_fast`) | ~2 s |
| Canh chữ | ~2 s |

Một chapter 3 trang đi trọn từ lúc bấm tới lúc file về máy: **230 giây**.

Đo cũ trên chapter 24 trang: trung vị **107,3 s/trang**, p90 ⇒ **~99 phút** cho cả chapter.

### Bộ test

**Backend 1.631 passed / 6 skipped / 0 failed** · **Frontend 390 passed**.

---

## 5. Giới hạn — chia theo bản chất

### 5.1. Chặn ở tầng cấu trúc (không phải thiếu thời gian)

| Việc | Vì sao chặn |
|---|---|
| **Dựng chữ dọc tiếng Việt** | `MangaOCREngine.recognize()` chỉ trả `(text, None)` — **không mang theo hình học dòng chữ**. Không có nguồn đó thì không đường nào xác định được hướng dọc kèm bằng chứng. Đây **không** phải chuyện thiếu ảnh mẫu |
| Dựng chữ nghiêng/cách điệu | Không hỗ trợ; chỉ đưa vào rà soát |

### 5.2. Chưa làm

| Việc | Ghi chú |
|---|---|
| **Ngôn ngữ nguồn tiếng Hàn** | Manhwa là thị phần lớn. Cần OCR tiếng Hàn + đo lại cả chuỗi. Khó hơn vẻ ngoài: manhwa là truyện **cuộn dọc**, khác hẳn giả định trang/khung mà phần canh chữ đang dựa vào |
| **Ngôn ngữ đích ngoài tiếng Việt** | Hiện chỉ `vi` |
| **Bộ đo so sánh mô hình** | Đang chọn engine theo cảm giác, không có số nào. Có sẵn hạ tầng đo và fixture CC BY-SA hợp pháp |
| **Hiện chi phí token trên giao diện** | Backend đã ghi `token_cost` từng trang nhưng **không hiện ở đâu cả** |
| Ứng dụng di động | Không có |
| Tiện ích trình duyệt phát hành chính thức | Có tiện ích Chrome nhưng phải **nạp tay**, và bản production chỉ mở được link (không đọc được trạng thái) |
| Phủ bản dịch lên trang web bất kỳ | Có bản chạy được nhưng chưa phát hành |

### 5.3. Cố ý không làm (là quyết định, không phải thiếu sót)

| Việc | Vì sao |
|---|---|
| Cho dùng vô danh, không đăng nhập | Công cụ nội bộ, không phải SaaS |
| Bỏ khai báo mục đích sử dụng | Đây là cổng nhắc trách nhiệm bản quyền |
| Tiện ích đọc nội dung trang web đang xem | Không content script, `host_permissions` rỗng |
| Tiện ích nhớ API key / ảnh / bản dịch | Chính sách riêng tư |
| Đường "Dịch nhanh" có bước tick xác nhận trước khi xuất | Chủ dự án chốt chấp nhận. Hệ thống **không tick hộ** người dùng |

### 5.4. Đã làm nhưng CHƯA chứng minh đầy đủ

| Việc | Còn thiếu bằng chứng gì |
|---|---|
| Nhận PDF | Có đủ test kể cả bài chứng minh chữ vector không bị mất, nhưng **chưa chạy với một PDF truyện thật nào** |
| Chapter dài | Lượt 24 trang **chưa chạy trọn một lần** đầu-cuối |
| Rà soát SFX | Mẫu thật quá nhỏ (n=9) để khẳng định rộng |

### 5.5. Điểm yếu của đường "Dịch nhanh"

Đường này **bỏ qua bước rà soát**. Trang bị gắn cờ "cần rà soát" vẫn **đi thẳng vào file xuất**.
Đây là đánh đổi có chủ đích (ai cần rà soát thì bấm sang đường đầy đủ), nhưng người dùng không
được cảnh báo gì trên đường nhanh.

---

## 6. Quy ước nhãn — đọc kỹ trước khi tin bất kỳ con số nào

Dự án phân biệt ba mức, và **không** nâng mức khi chưa có bằng chứng:

- **LIVE** — đã chạy thật một lần và kiểm được kết quả
- **BUILT** — có code, test xanh, **chưa chạy thật**
- **BLOCKED** — chặn ở tầng cấu trúc, nêu rõ chặn ở đâu

Nguyên tắc xuyên suốt: *"chưa chạy → `NULL`; hỏng → nêu đúng lý do; không tự nhận done khi thiếu
bằng chứng; không điền giá trị mặc định giả."*

> ⚠️ File `docs/FEATURES.md` giữ bảng chi tiết từng mốc theo lịch sử. **Một số nhãn ở đó có thể
> lỗi thời** so với bản đang chạy. Tài liệu bạn đang đọc là bản chốt mới nhất, đo từ production.

---

## 7. Gợi ý cho người đọc tài liệu này

Khi đề xuất nâng cấp, xin cân nhắc mấy điều đã biết trước:

1. **Chữ dọc tiếng Việt bị chặn ở hợp đồng OCR, không phải ở phần canh chữ.** Đề xuất "cải thiện
   bộ dựng chữ dọc" sẽ không gỡ được nút thắt; phải đi từ chỗ OCR trả về hình học dòng chữ.
2. **Tiếng Hàn kéo theo mô hình bố cục khác** (cuộn dọc), không chỉ là thêm một engine OCR.
3. Đây là **công cụ nội bộ**. Đề xuất kiểu gói cước, hạn mức, quota vô danh sẽ lệch mục tiêu.
4. Dự án **cố ý không nhúng code GPL**; chỉ dùng weight mô hình độc lập qua interface riêng.
5. Ảnh container API cố tình giữ mỏng — **không kéo thư viện nặng (kể cả Pillow) vào tiến trình
   API**. Đề xuất xử lý ảnh ở tầng API cần tính tới ràng buộc này.
6. Ràng buộc bộ nhớ là thật: đã từng bị OOM giết worker, và trần bộ nhớ hiện là lớp bảo vệ duy
   nhất (chủ dự án chốt **không nâng RAM**).

### Ba câu hỏi đáng trả lời nhất

1. Với một công cụ đã chạy được cả chuỗi, **đâu là thứ làm người dùng bỏ cuộc nhiều nhất** — tốc
   độ (~100 giây/trang), chất lượng dịch, hay công sức rà soát?
2. Nên mở rộng **bề rộng** (thêm tiếng Hàn, thêm ngôn ngữ đích) hay đào sâu **chất lượng** trên
   cặp ngôn ngữ đang có?
3. Có cách nào **đo được chất lượng dịch** một cách tái lập, để chọn engine bằng số thay vì cảm
   giác — mà không tốn quá nhiều token?
