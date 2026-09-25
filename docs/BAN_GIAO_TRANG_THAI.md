# Bàn giao trạng thái — Công cụ dịch truyện tranh

**Ngày:** 2026-09-25 · **Mục đích:** để một trợ lý khác đọc và xây tiếp.
**Nguyên tắc của tài liệu này:** mọi con số đều là **đo thật**, có ghi rõ điều kiện đo. Chỗ nào
chưa đo thì ghi **CHƯA ĐO**, không ước lượng cho đẹp.

---

# 1. Sản phẩm này là gì

Công cụ dịch truyện tranh (EN/JA/ZH → tiếng Việt). Người dùng tải trang truyện lên, hệ thống tự
làm trọn chuỗi và trả về trang đã dịch, chữ dịch được vẽ đè vào đúng bong bóng thoại.

**Đang chạy thật:**
- Giao diện: `translation.cmc-1.vibenode.matbao.ai`
- API: `translation-api.cmc-1.vibenode.matbao.ai`
- Hạ tầng: Vibe Host, **2,6 CPU · 4096 MB RAM**, không GPU. Một container chạy CẢ API lẫn worker.

---

# 2. Chuỗi xử lý — năm bước

| # | Bước | Chạy bằng gì | Thời gian/trang |
|---|---|---|---|
| 1 | **Nhận diện** khung chữ | Gemini API *(mới)* hoặc `comic-text-detector` ONNX | **~3s** / 42–70s |
| 2 | **Đọc chữ** | PaddleOCR (zh/en) · manga-ocr (ja) | ~8–45s |
| 3 | **Xoá chữ gốc** | LaMa ONNX | ~19–50s |
| 4 | **Dịch** | Gemini (`llm_context`) hoặc Google Translate (miễn phí) | ~2–4s |
| 5 | **Căn chữ** vào bong bóng | Pillow, không dùng model | ~2s |

Mỗi bước là một service riêng, nối với nhau qua Celery. Worker chạy `--pool=solo` — **đúng một
việc một lúc**.

**Một trang trọn chuỗi ≈ 70–100 giây.** Chapter 24 trang ≈ 30–40 phút.

---

# 3. Việc vừa làm xong — thay nhận diện bằng AI

## 3.1. Kết quả

| | Model cũ (ONNX cục bộ) | Engine AI (Gemini) |
|---|---|---|
| Thời gian | 42–70s | **~3s** |
| Chi phí | 0 | **~3,3 xu Mỹ / chapter 24 trang** |
| Cần mạng | không | **có** |

**Nhanh hơn 13–23 lần.** Đã chạy thật trên production, có log xác nhận.

## 3.2. Ba quyết định kỹ thuật KHÔNG được đảo

Mỗi cái đều có số đo đứng sau. Người xây tiếp cần biết để không "dọn dẹp" mất:

**(a) Bắt buộc dùng `responseSchema` (ép định dạng đầu ra).**
Xin JSON bằng lời nhắc **hỏng âm thầm**: đo được model dừng giữa mảng JSON, thiếu dấu đóng, mà
vẫn báo `finishReason: STOP` — tức nó tưởng đã trả lời xong. Tái hiện **7/7 lần trên cùng một
trang**, tức hỏng tất định theo trang. Không có ngoại lệ, không có mã lỗi, chỉ là **dữ liệu
thiếu** ⇒ trang đó im lặng mất vùng chữ.
Ép schema: **45/45 thành công** (so với 24/30) và *nhanh hơn*.

**(b) Lời nhắc phải đòi khung CHỮ, không đòi khung BONG BÓNG.**
Lời nhắc ban đầu nói *"speech balloon and text area"* — chính nó mời model khoanh cả bong bóng.
Diện tích ăn vào nét vẽ **gấp 2,7 lần**. Khung này còn làm **mask cho bước xoá chữ**, nên thừa
nghĩa là **xoá cả nét vẽ quanh bong bóng**. Đổi sang đòi khung bám sát nét chữ: còn **1,0×**,
ngang đúng model cũ.

**(c) `confidence = None`, tuyệt đối không bịa số.**
Gemini không trả điểm tin cậy. Điền 1.0 cho gọn là bịa ra con số không tồn tại; coi `None` là
thấp thì gắn cờ rà soát **oan cho mọi vùng**. Hệ thống đã có sẵn `ConfidenceState.unavailable`
cho đúng tình huống này.

## 3.3. Độ chính xác — kết luận ngược với trực giác

Đây là phần dễ hiểu sai nhất, và tôi đã hiểu sai **ba lần** trong quá trình đo.

**Không được lấy model cũ làm chuẩn.** Nó là đương nhiệm, không phải chân lý.

Đo trên 5 trang tiếng Anh: AI "bỏ sót 1/27 vùng" so với model cũ. Truy đến tận nơi thì vùng đó là
**mấy nét khói vẽ bay lên từ tẩu thuốc** — 53×38px, chiếm 0,10% trang, OCR đọc ra đúng một ký tự
với độ tin cậy 0,38. **Không phải chữ.** Model cũ báo nhầm, AI bỏ qua đúng.

Đo trên 3 trang tiếng Nhật: AI "bỏ sót 7/13". Nhìn ảnh thì khung của model cũ phần lớn nằm trên
**hiệu ứng ánh sáng lấp lánh** (ánh lửa, tia sáng, vật phát quang), còn AI bắt đúng cả ba bong
bóng thoại thật.

⇒ **Trên các mẫu đã đo, engine AI không bỏ sót vùng chữ thật nào**, và nó **báo nhầm ít hơn hẳn**
model cũ trên tranh tối / tranh có hiệu ứng sáng.

⚠️ **Cách đo đúng:** với mỗi vùng chênh lệch, phải (1) chạy OCR xem có đọc ra chữ thật không, và
(2) **vẽ khung lên ảnh rồi nhìn**. Chỉ đếm số vùng thì "sót chữ thật" và "bỏ qua nhiễu" trông y
hệt nhau.

## 3.4. CHƯA ĐO — đừng coi là đã có

1. **Bố cục manga thật.** Mẫu tiếng Nhật đã đo là Pepper&Carrot bản ja — **chữ ngang trong bong
   bóng kiểu phương Tây**. **Chữ dọc (tategaki)**, bong bóng không viền, chữ tượng thanh đè lên
   nét vẽ — chưa thử lần nào.
2. **Chất lượng đọc chữ trong khung AI** so với khung cũ.
3. **Hành vi khi mất mạng.** Nhận diện giờ phụ thuộc Gemini; Gemini hỏng là cả dây chuyền đứng.
4. Mẫu rất nhỏ: **5 trang tiếng Anh + 3 trang tiếng Nhật**.

## 3.5. Đường lùi

Mặc định trong mã **vẫn là model cũ** (`DETECT_ENGINE=ctd`). Engine AI bật bằng biến môi trường
trên production. Muốn lùi: **xoá biến rồi deploy** — không sửa mã, không revert commit.

---

# 4. Những hướng tối ưu tốc độ ĐÃ ĐÓNG — đừng mở lại

Đã đo và bác bỏ. Mở lại là lặp công việc đã làm:

| Hướng | Kết quả đo |
|---|---|
| Giảm số luồng ONNX | **Ngược chiều** — chậm hơn 2,5–3,5× |
| Hạ độ phân giải đưa vào nhận diện | **Bất khả** — model có shape đầu vào tĩnh `[1,3,1024,1024]` |
| Model bị nạp lại mỗi trang | **Không xảy ra** — đã cache |
| Lượng tử hoá INT8 | **Không chạy được** — thiếu kernel `ConvInteger` |
| Thêm CPU | **Đã ở trần gói**, *và* 6× số nhân chỉ cho 1,19× |
| Chạy 2 worker song song | **Vô ích** — công việc CPU bảo toàn; đo 5 cặp, chênh 1,2%, dưới nhiễu |
| Hợp kết quả 2 model AI | **Vô ích** — cả hai sót cùng chỗ; diện tích ăn nét vẽ tăng gấp đôi |

**Lý do gốc:** mọi hướng trên đều *chia lại* cùng một khối tính toán. Chỉ hướng **bỏ hẳn khối đó
ra khỏi máy** (gọi AI) mới ăn thua.

---

# 5. Giao diện — trạng thái hiện tại

## 5.1. Vừa làm xong: đổi tone màu toàn app

Hệ thống có **một nguồn màu duy nhất** (`frontend/src/styles/tokens.css`), nên đổi tone lan ra
toàn bộ 55 component mà không đụng bố cục hay logic.

Tone mới: **xanh mực trầm `#1e40af` trên nền ngà ấm `#faf9f7`** (trước là tím indigo trên nền xám
lạnh). Lý do: công cụ này để ngồi đọc và soát chữ hàng giờ.

**Tương phản đo bằng công thức WCAG, không ước lượng bằng mắt:**

| | Tỷ lệ | |
|---|---|---|
| Chữ / nền | 16,62:1 | AAA |
| Màu chính / trắng | 8,72:1 | AAA |
| Chữ phụ / nền | 5,21:1 | AA |
| Các màu ngữ nghĩa | 4,84 – 5,91:1 | AA |

`--mo-nhat` chỉ đạt 3,14:1 nên **chỉ dùng cho chữ đã giảm nhấn hoặc đường kẻ trang trí** (bản cũ
còn tệ hơn: 2,45:1).

## 5.2. Bẫy đã gặp — người xây tiếp cần biết

**Phép quét màu gõ cứng chỉ tìm `#hex` sẽ MÙ với `rgba()`.** Build ra rồi kiểm bundle mới lòi ra
tím cũ còn sót dưới dạng `rgba(79, 70, 229, …)`, cùng favicon vẫn màu cũ. **Phải kiểm trên bản đã
build, không chỉ trên mã nguồn.**

`rgba()` không đọc được biến màu, nên mọi lớp phủ trong suốt phải có **token riêng**.

## 5.3. Nguyên tắc giao diện đang theo

- Màu **không bao giờ** là nguồn thông tin duy nhất — luôn kèm nhãn chữ + icon.
- Component **không viết mã màu trực tiếp**, chỉ đọc token.
- Vòng focus bàn phím luôn nhìn thấy được.

---

# 6. Tính năng hạn mức — ĐÃ CHỐT LUẬT, CHƯA XÂY

Đây là phần cần xây tiếp.

## 6.1. Luật đã chốt

| | Khách chưa đăng ký | Có tài khoản |
|---|---|---|
| Hạn mức | **3 trang/ngày** | **10 trang/ngày** |

- **Đơn vị đếm: TRANG** (không phải chapter). Chi phí thật tính theo trang.
- **Nhận diện khách lạ: cookie + IP.** Cookie để nhận ra trình duyệt, IP làm chốt chặn thứ hai.
  Trần theo IP nên đặt **cao hơn** trần theo cookie, vì văn phòng/quán cà phê dùng chung IP.
- **Reset: 0h giờ Việt Nam (UTC+7).**

## 6.2. Bốn thứ THIẾU thì tính năng tự gây hại

**(a) Chặn ở tầng máy chủ, không chỉ ẩn nút.**
Dự án đã có bài học đúng chỗ này: bộ test đầy đủ vẫn xanh khi cổng chặn chỉ nằm ở giao diện. Ẩn
nút mà API vẫn nhận thì ai mở công cụ nhà phát triển cũng vượt được.

**(b) Hoàn lượt khi xử lý hỏng.**
Nếu trừ hạn mức lúc *nhận* trang mà trang đó hỏng giữa chừng, người dùng mất lượt vì lỗi của hệ
thống. **Đây là chỗ dễ quên nhất.**

**(c) Nói rõ còn bao nhiêu và bao giờ có lại.**
Hiện `0/3` mà không nói "có lại lúc 0h" thì người ta tưởng hỏng.

**(d) Chặn trần kích thước tệp TRƯỚC khi tính lượt.**
Không có thì một tệp rất lớn vừa đốt băng thông vừa có thể làm chết worker.

## 6.3. Bẫy múi giờ — đã có tiền lệ trong dự án này

**Container chạy giờ UTC, máy làm việc là UTC+7.** Bài test gom theo "giờ trong ngày" sẽ **xanh ở
máy mà đỏ trên server**. Mốc reset phải ép múi giờ tường minh, và **chính bài test cũng phải ép
`TZ`** chứ không dựa vào giờ máy.

## 6.4. Cân nhắc về con số 3

3 trang/ngày là **rất ít để cảm nhận sản phẩm** — một trang mất ~30 giây trọn chuỗi, nên khách lạ
dùng hết hạn mức trong chưa đầy 2 phút. Chi phí thật chỉ ~0,14 xu cho 3 trang, nên nếu mục tiêu là
*mời người ta đăng ký* thì con số rộng tay hơn gần như không tốn thêm gì.

⇒ **Để nó thành biến môi trường đổi được, đừng viết số cứng vào mã.**

---

# 7. Ràng buộc hạ tầng — không thương lượng được

| | |
|---|---|
| RAM | **4096 MB** cho CẢ API lẫn worker. Chủ dự án đã chốt **KHÔNG nâng** (hai lần) |
| Ngân sách thật của worker | ~3950 MB (API chiếm ~104 MB) |
| Đỉnh RSS một worker | ~2295 MB ở bước xoá chữ |
| Worker đã bị OOM giết | **3 lần** |
| CPU | 2,6 — **đã ở trần gói**, không tăng được |

⇒ **Không chạy thêm worker.** Hai worker phổ thông cần ~4682 MB, vượt rõ ràng.

---

# 8. Nguyên tắc làm việc của dự án

Người xây tiếp nên giữ, vì chúng sinh ra từ lỗi thật:

1. **Evidence-first.** Chưa chạy → `NULL`. Hỏng → nêu đúng lý do. **Không điền giá trị mặc định
   giả.**
2. **Hỏng thì báo, không lặng lẽ lùi về đường cũ.** Người dùng sẽ tưởng đang chạy thứ mình chọn,
   và sự cố kéo dài sẽ không ai thấy.
3. **Kiểm trên bản đã build**, không chỉ trên mã nguồn.
4. **Phép quét cũng phải tự kiểm.** Quét thiếu một dạng viết là bỏ sót im lặng.
5. **Đọc thân lỗi HTTP**, đừng đoán theo mã. Một lỗi `400` hoá ra là *"model only works in
   thinking mode"* — đoán theo mã số thì chẩn sai.
6. **Kết quả âm cũng là kết quả.** Dự án đã có nhiều lần "không ship gì" vì số đo bác bỏ giả
   thuyết — đó là bình thường, không phải thất bại.

---

# 9. Ảnh dùng để đo — chính sách bản quyền

Dùng **Pepper&Carrot** (tác giả David Revoy, **CC BY-SA 4.0**), gồm cả bản dịch tiếng Nhật chính
thức. Lý do ghi trong `test_fixtures/external/NGUON.md`:

> *"Trang chép từ dịch vụ có bản quyền thì đo xong cũng không công bố được."*

⇒ **Không dùng trang truyện chép từ dịch vụ đọc truyện** để đo và công bố số liệu.

---

# 10. Việc nên làm tiếp, theo thứ tự

1. **Xây tính năng hạn mức** (§6) — đã chốt luật, đủ để bắt tay.
2. **Dựng mặt ngoài cho người dùng mới**: một màn, thả tệp là chạy, không bắt khai báo gì trước.
   ⚠️ **Thiết kế riêng.** Không sao chép giao diện của sản phẩm cạnh tranh.
3. **Đo trên bố cục manga thật** (chữ dọc) trước khi mở rộng cho truyện Nhật — §3.4.
4. Xử lý việc worker bị OOM lần thứ ba (§7) — chưa ai truy nguyên nhân gốc.
