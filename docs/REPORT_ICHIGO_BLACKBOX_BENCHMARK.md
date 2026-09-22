# REPORT — Black-box competitor benchmark: Ichigo Reader

**Ngày đo:** 2026-09-22 · **Giờ đo:** 07:47–07:59 UTC (14:47–14:59 giờ VN)
**Người thực hiện:** trieunt · **Đối tượng:** Ichigo LLC — "Manga Translator🍓" (ichigoreader.com, canonical `ichigo.moe`)
**Bằng chứng thô:** `docs/evidence/ichigo_blackbox_20260922/`

> **Quy ước nhãn kết luận** (bắt buộc đọc trước khi trích dẫn báo cáo này):
> **OBSERVED** = tôi tự nhìn thấy trên màn hình, có ảnh chụp · **DOCUMENTED** = có trên trang
> chính thức của họ (web, App Store, Play, Chrome Web Store, ToS) · **INFERRED** = suy luận từ
> hành vi/dấu hiệu, **chưa được xác nhận** · **UNKNOWN** = chưa có bằng chứng, **không được đoán**.
>
> Không có câu nào trong báo cáo này nói "Ichigo dùng mô hình X để làm Y" trừ khi chính họ công bố.

---

## 1. Phạm vi và giới hạn pháp lý/kỹ thuật

### 1.1. Việc ĐÃ làm

| Bước theo đề bài | Trạng thái |
|---|---|
| Bước 1 — Ghi nhận sản phẩm công khai | ✅ **XONG**, có ảnh chụp + giờ đo |
| Bước 2 — Chọn fixture | ✅ **XONG** — đã chọn, chưa dùng |
| Bước 3 — Chạy thử có kiểm soát | ➖ **NGOÀI PHẠM VI** đợt này (xem §1.2) |
| Bước 4 — Đánh giá output | ➖ **NGOÀI PHẠM VI** (phụ thuộc Bước 3) → mọi mục chấm điểm là **UNKNOWN** |
| Bước 5 — So sánh với tool của ta | ✅ **XONG**, nhưng cột "Ichigo" chỉ gồm điều quan sát/công bố được |
| Bước 6 — Phân loại kết luận | ✅ **XONG** |
| Bước 7 — Report | ✅ Chính là tài liệu này |

### 1.2. Phạm vi đã chốt: quan sát công khai, không chạy fixture

Đợt này chốt ở **nghiên cứu sản phẩm công khai**: trang web, bảng giá, bảng xếp hạng, mô tả trên
ba store, đánh giá người dùng. Đây là tài liệu Ichigo chủ động công bố, đọc bao nhiêu cũng được.

**Không có lượt upload nào được thực hiện** — Bước 3/4 để lại cho đợt sau nếu cần. Hệ quả trực tiếp:
mọi hạng mục chấm chất lượng output ở §5 là **UNKNOWN**, và điều đó được ghi nguyên như vậy chứ
không lấp bằng phỏng đoán.

Ba đề xuất đầu bảng (ĐX-1, ĐX-2, ĐX-3 ở §8) **không cần** dữ liệu Bước 3: chúng dựa trên khoảng
cách G1/G2/G3 đã có ảnh chụp làm bằng.

### 1.3. Ranh giới kỹ thuật đã tự áp

| Không làm | Xác nhận |
|---|---|
| Upload bất kỳ file nào | **0 file** đã gửi đi |
| Đăng nhập / tạo tài khoản | Không. Menu `Account → Log in` chỉ mở ra rồi đóng lại |
| Vượt quota / đúc token / lách cổng | Không. Bộ đếm `remaining: 20` không bị chạm |
| Đọc API nội bộ, chặn bắt network, trích key/session | Không. Chỉ đọc DOM đã render như một người dùng thường |
| Đọc/giải mã bundle JS của họ để dò cơ chế | Không — đề bài loại trừ reverse-engineer |
| Tự động lặp request / spam | Không. Tổng cộng **~20 lượt tải trang** trong 12 phút, thao tác tay |

### 1.4. Giới hạn kỹ thuật của phép đo

- Ichigo là **SPA React (Vite)**: mọi route trả về **cùng một** shell HTML 2.947 byte
  (`md5 9cf6f58c…` giống hệt nhau trên cả 4 URL). ⇒ `curl` **không** đọc được nội dung; bắt buộc
  phải render bằng trình duyệt thật. *(OBSERVED)*
- Workspace **không có trình duyệt chạy được** lúc bắt đầu: Chromium của Playwright thiếu 10+ thư
  viện hệ thống (`libnspr4.so`, `libnss3.so`, `libatk`, `libcups`, các lib X…). Đã phải
  `apt-get install` 15 gói mới mở được trang. Đây là lần tái diễn của sự cố "workspace mất gói giữa
  hai phiên" đã ghi nhận trước đây — **không phải** hạ tầng Ichigo có vấn đề.
- Trang chủ `/` timeout 2 lần với `networkidle` và `domcontentloaded` (script Stripe giữ kết nối mở);
  phải dùng `waitUntil: 'commit'` mới đọc được. Không ảnh hưởng 3 trang chính.

---

## 2. URL, thời gian, môi trường và fixture

### 2.1. URL đã đo

| URL | HTTP | Giờ đo (UTC) | Bằng chứng |
|---|---|---|---|
| `https://ichigoreader.com/upload` | 200 | 07:50:06 | `shot_upload.png`, `text_upload.txt`, `controls_upload.json` |
| `https://ichigoreader.com/leaderboard` | 200 | 07:50:14 | `shot_leaderboard.png`, `text_leaderboard.txt` |
| `https://ichigoreader.com/subscription` | 200 | 07:50:19 | `shot_subscription.png`, `text_subscription.txt` |
| `https://ichigoreader.com/tos` | 200 | 07:54:5x | `tos.txt` (29.226 ký tự) |
| `https://ichigoreader.com/privacy` | 200 | 07:54:5x | tải 147 KB, cùng nội dung template |
| `https://ichigoreader.com/terms`, `/legal` | **404** | 07:54:5x | route không tồn tại |
| App Store `id1641432177` | 200 | 07:57 | `store_apple.png/.txt` |
| Google Play `com.ichigoreadermobile` | 200 | 07:57 | `store_play.png/.txt` |
| Chrome Web Store `lepcfgkehgeiblekejomdmdklmjdmflp` | 200 | 07:59 | `store_cws.png/.txt` |

### 2.2. Môi trường đo

Chromium 1234 (Playwright build) headless, viewport 1366×900, locale `en-US`, không đăng nhập,
không cookie kế thừa, không extension. Mỗi trang chờ render 3–9 giây trước khi chụp.

### 2.3. Fixture — đã chọn xong, chưa dùng

Kiểm kê `test_fixtures/` cho ra hai nhóm:

| Nhóm | Nội dung | Ghi chú |
|---|---|---|
| `external/pc_E01P01–P03` (+ bản `_1600.png`) | **Pepper&Carrot** tập 1, David Revoy, peppercarrot.com | **CC BY-SA 4.0** — nhóm nên dùng cho mọi phép đo công bố được |
| `external/pilot_e23/`, `pilot_uat_001/`, `kiem_dich/`, `den_trang/` | 44 trang chapter manga thật | Có bản quyền, đã gitignore — chỉ dùng nội bộ, không đẩy ra dịch vụ ngoài |

Kế hoạch fixture nếu về sau chạy Bước 3 (giữ nguyên để tái lập):
`pc_E01P01_1600.png` (trang thoại thường) · `pc_E01P02_1600.png` (nhiều bubble) ·
`pc_E01P03_1600.png` (nền vẽ tay phức tạp, chữ nhỏ). Cỡ 1600px chính là cỡ các dịch vụ đọc truyện
phục vụ thật.

**Khoảng trống fixture đã biết:** repo **không có** trang tiếng Nhật nào có quyền sử dụng rõ ràng.
Toàn bộ mẫu tiếng Nhật hiện có (`kiem_dich/ja_E12P01.jpg`) thuộc nhóm có bản quyền. Cho nên kể cả
khi chạy Bước 3, hạng mục "trang tiếng Nhật" và "trang có SFX" trong đề bài **vẫn chưa có fixture
công bố được** — phải kiếm nguồn public-domain riêng trước. Đây là việc tồn đọng, và nó chặn cả
phép đo cho **tool của chính ta**, không riêng gì việc so với Ichigo.

---

## 3. Các feature quan sát được

### 3.1. Màn Upload — đây là câu trả lời cho "vì sao UX đơn giản" *(OBSERVED)*

Toàn bộ màn upload chỉ có **3 điều khiển + 1 vùng thả + 1 bộ đếm**. Không hơn.

```
translate to English ▾     GPT-5.6 Luna ▾     ☑ auto-download
┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐
│           Drag and drop or select files             │
│        pdf, zip, and images are supported           │
└ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
                                        remaining: 20
```

Những thứ **không có mặt** trên màn này — và đó mới là điều đáng học:

- Không có khái niệm "project" / "chapter" phải tạo trước.
- Không có bước khai báo mục đích sử dụng.
- **Không có tường đăng nhập.** Bộ đếm `remaining: 20` chạy cho khách vô danh.
- Không có nút "Xử lý" — thả file là chạy. `auto-download` **bật sẵn** ⇒ đường mặc định là
  thả vào → nhận file về, không cần bấm thêm lần nào. *(OBSERVED — trạng thái checkbox)*
- Không thấy màn rà soát/sửa tay nào trên đường công khai. *(→ nhưng xem §9: UNKNOWN, vì tôi
  không chạy được một lượt upload để biết cái gì hiện ra SAU khi xử lý xong)*

**Định dạng nhận vào** *(OBSERVED — thuộc tính `accept` của `<input type=file>`)*:
`.pdf .cbz .zip .png .webp .avif .jpeg .jpg .gif .bmp .tif .tiff`

**18 ngôn ngữ đích** *(OBSERVED — mở menu)*: English, Arabic, French, German, Hindi, Indonesian,
Italian, Japanese, Korean, Polish, Russian, Spanish, Thai, **Vietnamese**, Portuguese,
Portuguese (Brazil), Chinese (Simplified), Chinese (Traditional).

### 3.2. Bộ chọn mô hình — khoá theo tier ngay trong menu *(OBSERVED)*

| Mô hình trong menu | Trạng thái với khách vô danh |
|---|---|
| GPT-5.6 Luna | **mở** (mặc định) |
| Kimi K2.6 · Muse Spark 1.2 · DeepSeek v4 Pro · Gemini 3.7 Flash | `(locked: tier 1)` |
| GPT-5.6 Sol · Gemini 3.1 Pro | `(locked: tier 2)` |

Điểm thiết kế đáng chú ý: mô hình bị khoá **vẫn hiện trong danh sách kèm chữ "locked: tier N"**,
không bị giấu đi. Người dùng thấy ngay thứ mình đang không có và giá của nó. *(OBSERVED)*

### 3.3. Các nền tảng công bố *(DOCUMENTED)*

| Nền tảng | Định danh | Số liệu công khai tại thời điểm đo |
|---|---|---|
| iOS/iPadOS/Mac | `id1641432177` | **4,5★ / 20 lượt** · 15,4 MB · 38 ngôn ngữ · Utilities |
| Android | `com.ichigoreadermobile` | **3,5★ / 298 lượt** · 10K+ lượt tải · cập nhật 09-09-2026 |
| Chrome extension | `lepcfgkehgeiblekejomdmdklmjdmflp` | **3,8★ / 550 lượt** · **40.000 người dùng** · v0.0.95 · cập nhật 11-08-2026 · 5,93 MiB · Featured |

Khẳng định tiếp thị họ tự đăng *(DOCUMENTED — là **claim của họ**, không phải phép đo của tôi)*:

- "Best-in-class manga translation and OCR quality" (App Store, CWS)
- "Highest quality text detection" (Play)
- **"Uses full-context on PDFs and ZIPs for max accuracy"** (App Store, CWS) — đây là khẳng định
  công khai duy nhất chạm tới cơ chế xử lý: dịch **theo ngữ cảnh cả tệp**, không phải từng trang rời.
- "Subscription service with a free trial—no registration required." (App Store, CWS)
- "Works on every manga site with the Unlocker or Panel Tool" (CWS)

---

## 4. Model / tier / quota / leaderboard được công khai

### 4.1. Bảng giá *(OBSERVED — `/subscription`, 07:50:19 UTC)*

| | **Free Trial** | **Tier 1** | **Tier 2** |
|---|---|---|---|
| Giá | **$0,00** | **$5,99/tháng** | **$19,99/tháng** |
| Mô hình | "Free models" | "Tier 1 models" | "Tier 2 models" (+ mọi thứ của Tier 1) |
| Extension | 40 lượt dịch **tổng cộng** | **Không giới hạn** * | như Tier 1 |
| Upload ảnh | 20 ảnh **tổng cộng** | **300 ảnh/giờ** | +150 lượt dịch ảnh Tier 2/giờ |
| OCR Nhật/Trung/Hàn | *(không nêu)* | ✅ có | ✅ có |
| **OCR tiếng Anh** | *(không nêu)* | *(không nêu)* | ✅ **chỉ Tier 2** |
| Watermark | *(không nêu)* | *(không nêu)* | ✅ **No watermark** |

\* Nguyên văn chú thích của họ: "Subject to terms of service."

**Ba điểm thiết kế thương mại đáng học** *(INFERRED — suy từ cấu trúc bảng giá, họ không giải thích)*:

1. Quota free là **tổng cộng trọn đời** (20 ảnh / 40 lượt), không phải theo ngày ⇒ dùng để *nếm thử*,
   không thể dùng free lâu dài.
2. Quota trả phí tính **theo giờ** (300/giờ) chứ không theo tháng ⇒ chặn lạm dụng mà vẫn nghe như
   "thoải mái".
3. **Năng lực bị bán theo tầng, không chỉ số lượng**: OCR tiếng Hàn/Nhật/Trung ở Tier 1, OCR tiếng
   Anh ở **Tier 2** — tức là ngôn ngữ nguồn cũng là một mặt hàng.

### 4.2. Leaderboard *(OBSERVED — `/leaderboard`, 07:50:14 UTC)*

Phương pháp họ **tự công bố**, nguyên văn:

> "Models are ranked by BLEU and by scoring with multiple leading frontier models acting as judges."

**Last run: August 31, 2026** — tức là **22 ngày trước** ngày đo. Cột: `Model | BLEU | Rank | Score`,
mặc định sắp xếp giảm dần theo `Score`. 21 dòng.

| # | Model | BLEU | Rank | Score |
|---|---|---|---|---|
| 1 | Gemini 3.1 Pro | 16,44 | 6,18 | **85,70** |
| 2 | GPT-5.6 Sol | 13,43 | 6,93 | 84,28 |
| 3 | Muse Spark 1.2 | 14,35 | 8,29 | 81,54 |
| 4 | GPT-5.6 Terra | 13,83 | 7,78 | 80,44 |
| 5 | Gemini 3.7 Flash | **16,66** | 8,19 | 80,29 |
| 6 | DeepSeek v4 Pro | 15,05 | 9,17 | 78,98 |
| 7 | Claude Fable 5 | 12,55 | 9,04 | 78,55 |
| 8 | GLM 5.3 | 13,60 | 9,51 | 77,97 |
| **9** | **GPT-5.6 Luna** | 12,40 | 9,80 | **77,37** ← *mô hình của bản miễn phí* |
| 10 | Gemini 3.8 Flash | 15,70 | 9,37 | 76,13 |
| 17 | Claude Opus 5 | 7,91 | 10,92 | 72,22 |
| 21 | DeepSeek v4 Flash | 9,33 | 14,84 | 60,93 |

*(Bảng đầy đủ 21 dòng trong `text_leaderboard.txt`.)*

**Quan sát có ý nghĩa kỹ thuật:** BLEU và Score **không đồng thuận**. Gemini 3.7 Flash có BLEU cao
nhất bảng (16,66) nhưng chỉ xếp thứ 5 theo Score; Claude Opus 5 có BLEU thấp nhất nhóm trên (7,91)
nhưng vẫn đứng trên 4 mô hình khác theo Score. *(OBSERVED)* ⇒ Trọng số của họ nghiêng về phía
LLM-judge chứ không phải BLEU. *(INFERRED — họ không công bố công thức)*

**Đòn thương mại ẩn trong bảng này** *(INFERRED)*: hai mô hình đứng **nhất và nhì** (Gemini 3.1 Pro,
GPT-5.6 Sol) đều là hàng **Tier 2 — $19,99**; bản miễn phí nhận mô hình hạng **9/21**. Bảng xếp hạng
vừa là tài liệu kỹ thuật, vừa là trang bán hàng: nó cho người dùng thấy chính xác mình đang bỏ lỡ
bao nhiêu điểm.

### 4.3. Quyền riêng tư & chi phí dữ liệu *(DOCUMENTED)*

| Nguồn | Nội dung công bố |
|---|---|
| Play "Data safety" | "No data shared with third parties" · có thu thập **Personal info** · "Data is encrypted in transit" · "You can request that data be deleted" |
| Chrome Web Store | Khai báo xử lý: **Personally identifiable information**, **Authentication information**, **Website content**. Cam kết không bán cho bên thứ ba |
| `/privacy` | Là **template chung cho app di động** ("Ichigo LLC built the Manga Translator app as a Commercial app"), nói về Log Data, cookie, Google Play Services |
| `/tos` §4 "Your Content" | **Chỉ nói về ý tưởng/góp ý/phản hồi.** Không có điều khoản nào về quyền sở hữu, thời gian lưu giữ, hay việc dùng **ảnh người dùng upload** để huấn luyện |

**Đây là một khoảng trống thật trong tài liệu của họ, không phải tôi tìm chưa kỹ:** đã grep toàn bộ
29.226 ký tự của `/tos` theo `upload / user content / retain / delete / store / train / image` —
**không có điều khoản nào nói ảnh manga bạn upload sẽ được giữ bao lâu hay bị dùng vào việc gì.**
Ngày cập nhật gần nhất ghi trên trang: **20-01-2025**. *(OBSERVED)*

### 4.4. Người dùng thật nói gì *(DOCUMENTED — là **lời của người dùng**, chưa kiểm chứng độc lập)*

- App Store, 16-10-2025: báo lỗi *"the English OCR error pops up despite the page not being in
  english"* — **nhà phát triển trả lời công khai xác nhận đã tái hiện được lỗi và sẽ vá**.
  ⇒ Chi tiết này khớp với việc OCR tiếng Anh bị khoá sau Tier 2 (§4.1): cổng ngôn ngữ nguồn của họ
  có va chạm thật ngoài đời. *(INFERRED)*
- Play, 16-06-2026 (khen): *"Amazing translations… google or others don't even compare"*, kèm mong
  muốn dịch liên tục thay vì phải bấm từng lần.
- Play, 07-01-2025 (chê, 20 người thấy hữu ích): than phiền mất **2–3 phút hoặc hơn** cho một lần
  dịch màn hình. Nhà phát triển trả lời **05-05-2026** rằng đã viết lại app và tính năng phủ chữ.
  ⇒ Độ trễ **từng là** điểm yếu công khai của họ. Không có bằng chứng về tốc độ hiện tại. *(UNKNOWN)*

---

## 5. Kết quả chạy fixture

**KHÔNG CÓ. Không một lượt chạy nào được thực hiện** (Bước 3 nằm ngoài phạm vi đợt này — §1.2).

Mọi ô trong bảng dưới đây lẽ ra là kết quả Bước 4. Để trống đúng như vậy là kết quả trung thực duy
nhất có thể ghi.

| Hạng mục chấm theo đề bài | Kết quả | Nhãn |
|---|---|---|
| Detection — sót bubble / nhận nhầm vùng | *(không đo)* | **UNKNOWN** |
| OCR — ký tự/từ có đúng không | *(không đo)* | **UNKNOWN** |
| Context — câu ngắt dòng có dịch liền không | *(không đo)* | **UNKNOWN** |
| Translation — nghĩa, tên riêng, xưng hô, tiếng động | *(không đo)* | **UNKNOWN** |
| Inpaint/overlay — chữ gốc bị xoá hay bị che | *(không đo)* | **UNKNOWN** |
| Typeset — tràn khung, chồng chữ, font, độ đọc được | *(không đo)* | **UNKNOWN** |
| Export — định dạng, thứ tự trang, mở được không | *(không đo)* | **UNKNOWN** |
| Review/edit — sửa text/bbox/model | *(không đo)* | **UNKNOWN** |
| Thời gian xử lý, quota trước/sau | *(không đo)* | **UNKNOWN** |
| Privacy/cost — dữ liệu nào được gửi đi | Chỉ có phần **tài liệu** ở §4.3; phần **hành vi thật** không đo | **DOCUMENTED một phần** |

> ⚠️ **Cảnh báo dùng báo cáo:** câu hỏi mở đầu của đề bài là *"vì sao Ichigo có output manga đẹp"*.
> Báo cáo này **không trả lời được nửa "output đẹp"** — tôi chưa từng nhìn thấy một trang output nào
> của Ichigo. Nửa **"UX đơn giản"** thì trả lời được đầy đủ và có ảnh chụp (§3.1). Đừng trích báo
> cáo này như một bằng chứng về chất lượng dịch của họ.

---

## 6. Bảng so sánh với tool của chúng ta

Cột "Ichigo" chỉ ghi điều quan sát/công bố được. Cột "Ta" lấy từ `docs/FEATURES.md` và `README.md`.

### 6.1. Đầu vào & luồng thao tác

| Hạng mục | Ichigo | Tool của ta | Nhãn (Ichigo) | Khoảng cách |
|---|---|---|---|---|
| Số bước tới kết quả | Thả file → nhận file về (auto-download bật sẵn) | Tạo project → khai mục đích (M10) → upload từng trang → chờ → rà soát → xuất | OBSERVED | **Lớn** |
| Cần tài khoản | **Không** (20 ảnh vô danh) | Có cổng truy cập (A1) | OBSERVED | Lớn |
| Nhận ZIP/CBZ/PDF | ✅ `.pdf .cbz .zip` | ❌ chỉ từng ảnh | OBSERVED | **Lớn** |
| Định dạng ảnh | 9 loại (kể cả `.avif`, `.webp`, `.tiff`) | jpg/png | OBSERVED | Vừa |
| Số điều khiển trên màn chính | **3** | Nhiều hơn hẳn (màn rà soát nhiều tầng) | OBSERVED | Lớn |

### 6.2. Ngôn ngữ & mô hình

| Hạng mục | Ichigo | Tool của ta | Nhãn | Khoảng cách |
|---|---|---|---|---|
| Ngôn ngữ nguồn | Nhật, Trung, **Hàn** (+ Anh ở Tier 2) | Anh, Nhật, Trung — **không có Hàn** | DOCUMENTED | **Vừa–Lớn** (manhwa) |
| Ngôn ngữ đích | **18** (có Tiếng Việt) | **1** — Tiếng Việt | OBSERVED | Lớn về bề rộng, **không đáng đuổi** |
| Chọn mô hình | Menu ngay cạnh dropzone, 7 mô hình, ghi rõ tier khoá | Có 2 engine (`google_fast`, `llm_context`) nhưng đổi bằng **gọi API** | OBSERVED | **Vừa** |
| Dịch theo ngữ cảnh | "full-context on PDFs and ZIPs" | ✅ `llm_context` cả trang (E26) + E31 xuyên trang + E32 cho mô hình xem ảnh | DOCUMENTED (claim) | **Ta ngang hoặc hơn** |
| Công khai số đo mô hình | ✅ Leaderboard BLEU + LLM-judge | ❌ có `TEST_LOG` nội bộ, không có bảng so mô hình | OBSERVED | **Vừa** |

### 6.3. Chất lượng xử lý ảnh — phần lớn KHÔNG so được

| Hạng mục | Ichigo | Tool của ta | Nhãn (Ichigo) |
|---|---|---|---|
| Nhận diện khung chữ | "Highest quality text detection" (claim) | comic-text-detector, có confidence + cờ `overlap_suspect` | **UNKNOWN** (claim ≠ phép đo) |
| OCR | JA/ZH/KO ở Tier 1, EN ở Tier 2 | manga-ocr (ja) + PaddleOCR (zh/en) | **UNKNOWN** về chất lượng |
| Xoá chữ gốc (inpaint) | Không công bố gì | LaMa + **tự đọc lại vùng vừa xoá để kiểm** (`inpaint_needs_review`) | **UNKNOWN** — kể cả việc họ có inpaint hay chỉ phủ hộp |
| Canh chữ vào **lòng bong bóng** | Không công bố gì | ✅ E14 — 5/5 bong bóng thật, chữ nằm trọn | **UNKNOWN** |
| Nhận biết hướng chữ | Không công bố gì | ✅ E15 nhận biết + E16 dựng chữ **nghiêng** live; **chữ dọc vẫn BỊ CHẶN** | **UNKNOWN** |
| Chống chèn trùng / mất câu | Không công bố gì | ✅ E26/E30 (từng mất cả câu, đã vá) | **UNKNOWN** |
| Watermark | Có ở tier thấp (suy từ "No watermark" của Tier 2) | Không có watermark | INFERRED |

### 6.4. Sau khi dịch xong — đây là chỗ TA mạnh

| Hạng mục | Ichigo | Tool của ta | Nhãn (Ichigo) | Ai hơn |
|---|---|---|---|---|
| Sửa tay bản dịch | Không thấy trên đường công khai | ✅ M7/E21: sửa bản dịch, **gõ đè chữ OCR đọc sai**, kéo lại khung, đổi font/size | **UNKNOWN** | **Ta** (nếu họ thật sự không có) |
| Hàng đợi rà soát có lý do | Không thấy | ✅ E12: chỉ ra vùng cần rà soát kèm lý do đọc được, **không tự xoá** | **UNKNOWN** | **Ta** |
| Thuật ngữ & giọng nhân vật | Không thấy | ✅ E13: chốt thuật ngữ cả chapter + hồ sơ giọng, máy chỉ chỗ lệch **không tự sửa** | **UNKNOWN** | **Ta** |
| Nói thật khi hỏng | Không đo được | ✅ `fallback_used`, `needs_manual`, E22 phân loại worker chết có bằng chứng | **UNKNOWN** | **Ta** |
| Xuất chapter | auto-download (định dạng ra: **UNKNOWN**) | PNG/CBZ/ZIP + cảnh báo trước khi xuất (E40 vá `.cbz` không mở được trên Windows) | **UNKNOWN** | Chưa kết luận được |
| Tốc độ | Review 2023–2025 than 2–3 phút; **hiện tại UNKNOWN** | Trung vị **107,3 s/trang**, p90 ⇒ ~99 phút/chapter 24 trang (E23) | UNKNOWN | **Không so được** |

### 6.5. Phân phối & mô hình kinh doanh

| Hạng mục | Ichigo | Tool của ta | Nhãn |
|---|---|---|---|
| Nền tảng | Web + iOS + Android + Chrome extension (**40.000 người dùng**) | Web + extension **nạp tay**, chưa lên CWS; không có app di động | DOCUMENTED |
| Phủ chữ lên trang web đang đọc | ✅ extension "Unlocker/Panel Tool", hoạt động trên site manga | ✅ E19 "Dịch truyện đang đọc" — **đã chạy thật** trên `reddit.com/r/translator` | DOCUMENTED |
| Mô hình tiền | Subscription $5,99 / $19,99 | Tự vận hành, không thu tiền | OBSERVED |

---

## 7. Khoảng cách có bằng chứng

Chỉ liệt kê khoảng cách **chứng minh được bằng quan sát trực tiếp**. Mọi thứ dựa trên phỏng đoán
chất lượng output đã bị loại khỏi mục này.

| # | Khoảng cách | Bằng chứng | Nhãn |
|---|---|---|---|
| **G1** | Ta bắt người dùng đi qua project + khai mục đích + upload từng trang; họ chỉ cần thả file | `shot_upload.png` vs `README.md` §Chạy nhanh | OBSERVED |
| **G2** | Ta **không nhận** ZIP/CBZ/PDF — chapter 24 trang là 24 lần thao tác | `accept=".pdf,.cbz,.zip,…"` trong `controls_upload.json` | OBSERVED |
| **G3** | Đổi engine dịch ở ta phải gọi `POST /pages/{id}/retry-translate?engine=…`; họ có menu ngay cạnh dropzone | `menu_model.png` vs `docs/FEATURES.md` | OBSERVED |
| **G4** | Ta không có **ngôn ngữ nguồn tiếng Hàn**; họ bán nó từ Tier 1 | `text_subscription.txt` + mô tả Play | DOCUMENTED |
| **G5** | Ta không có số liệu so mô hình công khai; họ có leaderboard cập nhật 31-08-2026 | `shot_leaderboard.png` | OBSERVED |
| **G6** | Ta không có mặt trên CWS/App Store/Play; extension của ta phải nạp tay và **chỉ nối `localhost`** | `docs/FEATURES.md` §E1 vs 3 store listing | DOCUMENTED |
| **G7** | Họ cho dùng thử **không cần đăng ký**; ta có cổng truy cập chặn trước | `remaining: 20` không đăng nhập + "no registration required" | OBSERVED + DOCUMENTED |

**Và khoảng cách theo chiều ngược lại** — những thứ ta có mà **không tìm thấy dấu vết công khai**
nào ở họ (nhãn **UNKNOWN**, không phải "họ không có"): sửa tay bản dịch và chữ OCR, hàng đợi rà soát
kèm lý do, bảng thuật ngữ + giọng nhân vật chốt cho cả chapter, canh chữ vào lòng bong bóng thật,
nhãn trung thực khi engine tụt về bản miễn phí.

---

## 8. Đề xuất cải tiến — tối đa 5, xếp theo ROI

> **Trạng thái: ĐÃ DUYỆT hướng A** (22-09-2026) — chốt báo cáo quan sát công khai làm kết quả cuối,
> ĐX-1 → ĐX-3 vào hàng đợi triển khai. Tại thời điểm viết báo cáo này chưa dòng code nào bị sửa (§10).

### ĐX-1 — Đường "Dịch nhanh": một màn, ba điều khiển, tải về luôn 🥇

**ROI: rất cao · Độ khó: thấp–trung bình · Rủi ro: thấp · Chi phí: không tốn thêm tiền API**

Thêm **một đường vào song song**, giữ nguyên đường chuyên nghiệp hiện có: thả ảnh → chọn ngôn ngữ
nguồn → nhận file về, không tạo project, không qua màn rà soát. Lấy đúng hình mẫu §3.1.

*Vì sao đáng làm nhất:* toàn bộ pipeline (detect → OCR → inpaint → dịch → canh chữ → xuất) **đã LIVE
và đã chạy chapter thật**. Khoảng cách G1 thuần tuý nằm ở lớp điều phối phía trên, không phải ở năng
lực xử lý. Đây là món rẻ nhất trên bàn.
*Cạm bẫy phải giữ:* M10 (khai báo mục đích + nhắc bản quyền) là **có chủ đích**, không được bỏ để
cho giống Ichigo — chuyển nó thành một dòng xác nhận trong luồng thay vì một màn chặn riêng.

### ĐX-2 — Nhận ZIP/CBZ/PDF làm đầu vào 🥈

**ROI: rất cao · Độ khó: trung bình · Rủi ro: trung bình (zip-bomb, path traversal, thứ tự trang) · Chi phí: thấp**

Giải G2. Một chapter là **một** thao tác thay vì 24. Bắt buộc kèm: giới hạn số trang/dung lượng giải
nén, chuẩn hoá thứ tự trang theo tên tệp tự nhiên, chặn đường dẫn thoát thư mục.
*Lưu ý:* ta **đã xuất** được CBZ/ZIP (M8) — đây là dựng chiều ngược lại, dùng lại được nhiều.

### ĐX-3 — Đưa lựa chọn engine dịch lên thẳng màn upload, ghi rõ cái nào tốn tiền 🥉

**ROI: cao · Độ khó: thấp · Rủi ro: rất thấp · Chi phí: gần như bằng 0**

Giải G3. Backend **đã có sẵn** `google_fast` (miễn phí) và `llm_context` (tốn token) — hiện chỉ đổi
được qua API. Đưa lên UI như Ichigo, kèm nhãn chi phí thật.
*Ta có thể làm tốt hơn họ ngay:* ta đã đo được **số token tiêu thật của từng trang** và mặc định là
bản miễn phí — Ichigo không hiển thị chi phí ở đâu cả. Hiện con số đó ra là điểm hơn, không phải
điểm đuổi theo.

### ĐX-4 — Bộ đo mô hình nội bộ (mini-leaderboard) trên fixture hợp pháp

**ROI: trung bình–cao · Độ khó: trung bình · Rủi ro: thấp · Chi phí: tốn token đo**

Giải G5. Chạy bộ fixture **CC BY-SA** (Pepper&Carrot) qua các engine, chấm bằng số, công bố nội bộ.
Không cần bắt chước BLEU + LLM-judge của họ — chọn thước đo hợp với cặp ngôn ngữ EN/JA→VI.
*Giá trị thật:* chọn mô hình dịch bằng **số đo của chính ta** thay vì theo bảng của đối thủ — bảng
của họ đo sang tiếng Anh, **không** đo sang tiếng Việt (§9).
*Điều kiện tiên quyết:* phải kiếm được fixture tiếng Nhật public-domain — hiện repo **chưa có** (§2.3).

### ĐX-5 — Tiếng Hàn làm ngôn ngữ nguồn (manhwa)

**ROI: trung bình về dài hạn · Độ khó: CAO · Rủi ro: cao · Chi phí: cao**

Giải G4. Đây là món **đắt nhất và ít chắc chắn nhất** trong 5 đề xuất: cần OCR tiếng Hàn, cần đo
lại toàn bộ chuỗi, và manhwa là truyện **cuộn dọc** — khác hẳn giả định trang/khung mà E14/E15/E16
đang dựa vào. Xếp thứ 5 là có chủ ý: **đừng khởi động cái này trước khi ĐX-1→ĐX-3 xong.**

---

## 9. Những điều CHƯA BIẾT — và không được suy đoán

Danh sách này quan trọng ngang phần kết luận. Mỗi dòng là một chỗ **cấm** viết phỏng đoán ra ngoài.

### 9.1. Về cơ chế kỹ thuật của Ichigo — UNKNOWN toàn bộ

1. **Họ dùng mô hình gì để PHÁT HIỆN khung chữ và để OCR.** Leaderboard **chỉ nói về mô hình DỊCH**.
   Không có một dòng công khai nào về detection/OCR. Câu "Ichigo dùng X để nhận diện khung chữ" là
   câu **không được phép viết**.
2. **Họ có thật sự xoá chữ gốc (inpaint) hay chỉ phủ một hộp màu lên trên.** Không có bằng chứng
   nào theo hướng nào.
3. **Cách họ canh chữ vào bubble**, xử lý tràn khung, chữ dọc, SFX.
4. **Watermark ở tier thấp trông thế nào** và đặt ở đâu — chỉ suy ra là *có*, từ dòng "No watermark"
   của Tier 2.
5. **Họ có màn sửa tay / sửa bbox / đổi mô hình sau khi dịch không.** Không thấy trên đường công
   khai **không có nghĩa là không có** — tôi không chạy được một lượt upload để biết màn kết quả ra
   cái gì.
6. **Định dạng file mà `auto-download` trả về**, thứ tự trang, có mở được không.
7. **Thời gian xử lý thật** năm 2026. Con số "2–3 phút" là review **tháng 01-2025**, và nhà phát
   triển đã tuyên bố viết lại app từ 05-2026. Dùng con số đó như hiện trạng là **sai**.

### 9.2. Về bảng xếp hạng của họ

8. **`Score` tính thế nào** — thang điểm, trọng số giữa BLEU và LLM-judge, đều không công bố.
9. **`Rank` chính xác là gì** — nhìn như thứ hạng trung bình của các giám khảo (số nhỏ = tốt), nhưng
   **họ không định nghĩa**. Đây là suy luận, không phải sự thật.
10. **Bộ dữ liệu đo là gì, bao nhiêu mẫu, cặp ngôn ngữ nào.** Gần như chắc chắn đo **sang tiếng Anh**
    (mô tả Play: "translate… to English") ⇒ **thứ hạng đó không tự động đúng cho tiếng Việt.**
    Đây là lý do ĐX-4 tồn tại.
11. **"Muse Spark 1.2", "Hy4 Preview", "GLM 5.3"…** — tôi ghi lại đúng như bảng hiển thị và
    **không xác nhận** các mô hình này là gì hay của ai.
12. Bảng đã **22 ngày** không chạy lại tính tới ngày đo.

### 9.3. Về dữ liệu người dùng

13. **Ảnh manga bạn upload được giữ bao lâu.** Không có điều khoản. Đã grep toàn bộ ToS.
14. **Ảnh upload có được dùng để huấn luyện không.** Không có điều khoản.
15. **Xử lý ở đâu, gửi qua nhà cung cấp mô hình nào.** Không công bố. Play nói "No data shared with
    third parties", nhưng dịch bằng mô hình bên thứ ba thì nội dung phải đi đâu đó — **hai điều này
    tôi không hoà giải được bằng bằng chứng công khai**, và không được tự hoà giải bằng suy đoán.

### 9.4. Về chính phép so sánh này

16. **Không có một phép đo cạnh-kề-cạnh nào tồn tại trong báo cáo này.** Bảng §6 so **năng lực công
    bố** với **năng lực đã đo của ta** — đó là hai loại bằng chứng khác hạng. Cột của ta chặt hơn
    cột của họ, và điều đó **không** có nghĩa là ta hơn.
17. **Câu "vì sao output của Ichigo đẹp" vẫn chưa được trả lời** (§5).

---

## 10. Trạng thái và điều cần anh quyết

### 10.1. Tuân thủ đề bài

| Ràng buộc | Trạng thái |
|---|---|
| Không tự sửa code | ✅ **0 file mã nguồn bị chạm** |
| Không commit | ✅ không chạy `git commit` |
| Không deploy | ✅ không chạy deploy |
| Dừng sau report, chờ phê duyệt | ✅ **đang dừng tại đây** |

File duy nhất được tạo: báo cáo này + thư mục bằng chứng `docs/evidence/ichigo_blackbox_20260922/`
(9 ảnh chụp + 9 tệp văn bản). *(Gói `apt` đã cài vào workspace để mở được trình duyệt — xem §1.4 —
là thay đổi môi trường, không phải thay đổi sản phẩm.)*

### 10.2. Quyết định (22-09-2026): hướng A

Chủ dự án chốt **hướng A**: nhận báo cáo quan sát công khai này làm kết quả cuối của đợt benchmark,
**không** chạy Bước 3/4, và chuyển sang triển khai ĐX-1 → ĐX-3.

| Việc | Trạng thái sau quyết định |
|---|---|
| Đợt benchmark Ichigo | ✅ **ĐÓNG** — báo cáo này là kết quả cuối |
| ĐX-1 Đường "Dịch nhanh" một màn | → vào hàng đợi triển khai |
| ĐX-2 Nhận ZIP/CBZ/PDF | → vào hàng đợi triển khai |
| ĐX-3 Chọn engine trên UI + hiện chi phí | → vào hàng đợi triển khai |
| ĐX-4 Mini-leaderboard nội bộ | ⏸ chờ — cần fixture tiếng Nhật public-domain trước |
| ĐX-5 Tiếng Hàn làm ngôn ngữ nguồn | ⏸ chưa khởi động, theo đúng khuyến nghị §8 |

**Việc tồn đọng độc lập với quyết định trên:** kiếm fixture manga tiếng Nhật public-domain. Thiếu nó
thì hạng mục "trang tiếng Nhật" và "trang có SFX" không đo được cho *bất kỳ* tool nào, kể cả tool
của chính ta (§2.3) — đây là điều kiện tiên quyết của ĐX-4.

---

*Hết báo cáo. Mọi số liệu trong tài liệu này truy ngược được về `docs/evidence/ichigo_blackbox_20260922/`
với giờ đo kèm theo. Chỗ nào không có bằng chứng thì ghi UNKNOWN, không ghi phỏng đoán.*
