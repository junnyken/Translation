# REPORT E66 — Prompt dịch không được bịa trôi chảy từ chữ rác

**Ngày:** 2026-09-28 · **Nguồn yêu cầu:** chủ dự án — *"tiếp trục chất lượng dịch (tên riêng chế,
câu lệch nghĩa), xem lại prompt dịch giúp tôi, tham khảo AI"*

---

## 1. Chẩn đoán — lỗi KHÔNG nằm ở bước dịch

Chạy **cùng một trang** (368×543) hai lần qua production. Chữ OCR đọc ra **khác nhau**:

| Vị trí | Lượt 1 | Lượt 2 |
|---|---|---|
| (13,13) | `あの妹山です` → "Đó là Seyama." | `あの暁山です` → **"Đó là núi Akatsuki."** |
| (11,1) | `あっこも天音が好きって言ってたから` → "Akko cũng nói rằng cô ấy thích Amane." | `あっでも元者が好きって行ってたから` → **"Ồ, nhưng tôi đi vì tôi thích người yêu cũ."** |
| (6,22) | `心の赤輪` → "vòng đỏ" | `心の家族` → **"gia đình"** |
| (3,15) | `待って！` → "cố lên!" | `やってー` → "Làm đi!" |

**Bản dịch không sai.** `あの暁山です` thật sự nghĩa là "đó là núi Akatsuki". Mô hình dịch trung
thành với thứ nó nhận được. Hai chỗ sai thật:

1. Chữ đọc từ ảnh 368px **không ổn định** — giới hạn của chính tấm ảnh.
2. Prompt **cho phép** mô hình tự sửa chữ rác, và **không cho nó đường nào** nói "tôi không chắc".

Lượt này sửa (2). Cần nhớ: (1) chưa được sửa, và nó là nguyên nhân gốc.

## 2. Ba chỗ sai trong prompt cũ

| Câu | Hại |
|---|---|
| *"Đầu vào là chữ do OCR đọc nên có thể sai chính tả; **tự suy luận và sửa khi dịch**."* | Cấp quyền chế. Đo được là nó chế thật |
| *"Không thêm giải thích, không thêm dòng nào ngoài danh sách đã đánh số."* | **Bịt miệng** mô hình: biết mình đang đoán cũng không được nói |
| *"Dùng ảnh để: (a) **sửa chữ bị đọc sai**…"* | Cộng hưởng với câu đầu — nhìn pixel mờ rồi "sửa" |

Không có luật nào cho **tên riêng**, nên `天音` (Amane) bị thay bằng danh từ chung "người yêu cũ".

## 3. Prompt mới

* **Vẫn cho sửa lỗi đọc NHỎ** (lệch một ký tự, thiếu dấu câu) — gỡ hẳn quyền sửa là đổi một lỗi
  lấy một lỗi khác: lệch một kana mà không cho sửa thì trang nào cũng đầy cảnh báo, và cảnh báo
  nào cũng như nhau thì không ai đọc.
* **Cấm bước nhảy** từ "sửa một ký tự" sang "đoán ra một TỪ KHÁC HẲN chỉ để câu có nghĩa".
* **Dấu `[?]`** ở đầu dòng = "dòng này tôi phải đoán". Vẫn dịch bản khả dĩ nhất — người đọc vẫn
  có chữ để đọc — nhưng vùng đó được gắn cờ.
* **`[?]` là NGOẠI LỆ DUY NHẤT** của luật "không thêm giải thích" (xem §5).
* **Luật tên riêng**: phiên âm và giữ nguyên là tên; không thay một cái tên bằng một danh từ chung.
* Mệnh đề về ảnh đổi từ *"sửa chữ bị đọc sai"* thành *"ĐỐI CHIẾU"*, và **chỉ xuất hiện khi thật sự
  có ảnh** — E32 đã chốt rằng nói về ảnh khi không gửi ảnh là mời mô hình bịa, và có bài canh riêng
  (`test_khong_anh_thi_prompt_KHONG_noi_ve_anh`). **Bài canh đó bắt được đúng lỗi này của tôi** ở
  bản nháp đầu.

## 4. Dấu `[?]` đi tới đâu

`LLMContextTranslator.translate()` bóc dấu khỏi chữ (sót một `[?]` là nó bị **nướng vào bong bóng**
trên ảnh người đọc tải về) và để lại chỉ số trên `self.vung_khong_chac`. `_run_translate` ánh xạ về
`region_id` rồi bật `OCRStatus.needs_manual`.

Hai quyết định ở đây:

* **Dùng `OCRStatus.needs_manual` có sẵn**, không thêm giá trị enum — thêm là một lượt `ALTER TYPE`
  trên production mà `CLAUDE.md` cảnh báo riêng. Nghĩa cũng khớp: "chữ đọc từ ảnh này cần người
  kiểm". Giao diện **đã** tô cảnh báo theo cờ đó (`BboxOverlay.jsx`), nên không phải nối thêm gì.
* **Ánh xạ chỉ số phải qua `chi_so_dich`**: mô hình đánh số theo danh sách ĐÃ GỬI ĐI, mà vùng SFX
  bị giữ nguyên không gửi ⇒ hai danh sách lệch nhau. Gắn cờ nhầm vùng còn tệ hơn không có cờ.

## 5. Tham vấn AI — lấy gì, bỏ gì

`codex` không đăng nhập được (401). `gemini` CLI đòi OAuth tương tác ngay cả khi đã có khoá, nên
tôi gọi thẳng REST API. Model: **gemini-3.1-pro-preview** (`gemini-2.5-pro` đã ngừng cho người dùng
mới).

**LẤY — và đây là đóng góp thật:** nó chỉ ra rằng *"Không thêm giải thích…"* **bịt miệng** mô hình,
mâu thuẫn với chính dấu `[?]` tôi vừa thêm. Tôi đã thêm dấu mà quên gỡ khoá miệng — hai luật kéo
ngược chiều nhau là chỗ mô hình chọn bừa. Đã vá, và có bài canh riêng.

**BỎ — kèm lý do đo được:** nó đề xuất tên riêng ghi kèm **Kanji gốc trong ngoặc** (`núi Akatsuki
[暁山?]`). Làm thế sẽ **phá pipeline này**: chữ Nhật lọt vào bản dịch ném `MissingGlyph` →
`FitStatus.font_missing_glyph` → **bong bóng để trống**. Đúng lỗi F1 đã có bài canh trong repo.

**CHƯA KẾT LUẬN ĐƯỢC:** nó cho rằng Vision LLM không cứu nổi OCR ở 368px và khuyên upscale bằng
**Real-ESRGAN trước khi OCR**. Tôi có số đo **bác bỏ bản phóng ảnh THƯỜNG** (E65 §2: phóng bicubic
lên 1200px làm OCR tệ đi rõ rệt), nhưng **không** bác bỏ được siêu phân giải bằng AI — đó là thứ
khác hẳn, và **chưa ai thử**. Ghi lại thành hướng mở, không tự nhận là đã bác bỏ.

## 6. Changed Files

| Tệp | Sửa gì |
|---|---|
| `app/services/translate/engines.py` | `DAU_KHONG_CHAC`; prompt mới; `tach_dau_khong_chac`; `vung_khong_chac` |
| `app/workers/tasks.py` | Ánh xạ chỉ số → `region_id`; bật `needs_manual` |
| `tests/test_e66_prompt_khong_bia.py` | **MỚI** — 13 bài |
| `tests/test_translate_engines_unit.py` | Bài canh cũ đổi hợp đồng có chủ đích (xem docstring) |

## 7. Remaining Limits

* **Chưa chạy trang thật sau khi vá** tại thời điểm viết — chưa biết mô hình dùng dấu `[?]` nhiều
  hay ít. Dùng quá tay thì cảnh báo mất giá trị (đúng bài học `feedback_chua_cau_hinh_khong_phai_
  su_co`: 144 thẻ/ngày làm người dùng tắt chuông).
* **Nguyên nhân gốc vẫn còn**: chữ đọc từ ảnh 368px không ổn định. E66 chỉ làm cho nó **nhìn thấy
  được**, không làm nó hết.
* Siêu phân giải bằng AI (Real-ESRGAN) trước bước OCR: **chưa thử**, là hướng mở số 1.
* Chưa có cơ chế ghim tên riêng xuyên chapter ở đường **Dịch nhanh** (bảng thuật ngữ E17/E31 chỉ
  dùng được ở đường tạo chapter đầy đủ).
