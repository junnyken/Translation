# Spec E17 — Gợi ý thuật ngữ & xưng hô rút từ CHÍNH chapter

**Ngày:** 2026-08-31 · **Trạng thái:** 📋 **BẢN THIẾT KẾ — CHỜ CHỦ DỰ ÁN DUYỆT, CHƯA VIẾT MÃ**
**Xuất phát:** yêu cầu của chủ dự án — *"nhập tên bộ truyện để lấy tên + xưng hô nhân vật, chứ
ngồi nhập từng cái rất phiền"* · **Đụng tới:** E13 (thuật ngữ & rà soát nhất quán)

> ⚠️ **Cổng chặn theo `CLAUDE.md`:** *"Không mở mini-spec sau khi mini-spec trước chưa audit
> pass."* P3h **chưa** verify được trên host (host `cmc-1` đang chết). Nên tài liệu này dừng ở
> mức **thiết kế**; viết mã chỉ bắt đầu sau khi P3h đóng hoặc chủ dự án quyết định đảo ưu tiên.

## 1. Vấn đề thật

Màn "Thuật ngữ của chapter" và "Giọng nhân vật" hiện là **hai cái form trống**. Người dùng phải
tự nhớ ra trong chapter có những tên gì, tự gõ lại đúng nguyên văn, tự gõ giải nghĩa — cho **từng**
thuật ngữ. Với một chapter 20 trang thì đây là hàng chục lượt gõ trước khi rà soát chạy được lần
đầu.

Việc đó có hai nửa. Máy làm được một nửa, và đang không làm:

| Nửa việc | Ai làm được | Hiện trạng |
|---|---|---|
| **Tìm ra** trong chapter có những danh xưng nào, xuất hiện ở đâu, bao nhiêu lần | **Máy** — chữ đã nằm sẵn trong `ocr_result.raw_text` | ❌ bắt người tự nhớ |
| **Quyết** dịch nó thành gì, xưng hô ra sao | **Người** — đây là quyết định biên tập | ✅ đúng, giữ nguyên |

E17 chỉ nhận nửa trên.

## 2. Vì sao KHÔNG làm đúng như câu chữ của yêu cầu

Yêu cầu gốc là "nhập tên bộ truyện → AI lấy dàn nhân vật". Cách đó vướng nguyên tắc số 3 của dự
án (`CLAUDE.md`: *evidence-first, không điền giá trị mặc định giả*), vì ba lý do đo được:

1. **Model luôn trả lời, kể cả khi không biết.** Truyện ít tiếng tăm, truyện mới, hoặc trùng tên
   với tác phẩm khác ⇒ nó dựng ra một dàn nhân vật nghe rất thật.
2. **Nó không biết chapter NÀY có ai.** Bộ truyện 200 nhân vật, chapter của bạn có 3.
3. **Danh sách sai làm hỏng đúng thứ E13 sinh ra để bảo vệ.** Thuật ngữ đã duyệt là **luật** dùng
   để quét cả chapter (`GlossaryStatus.approved`). Duyệt nhầm một tên không tồn tại ⇒ mọi lượt rà
   soát sau đó báo sai, và người dùng mất niềm tin vào chính công cụ rà soát.

⇒ **Đảo chiều:** lấy dữ liệu từ chữ đã đọc được của chapter. Tên bộ truyện, nếu làm, chỉ là lớp
phụ trợ **có cổng đối chiếu** (§7).

## 3. Phạm vi

| | Nội dung | Trong E17? |
|---|---|---|
| **Tầng 1** | Rút **ứng viên thuật ngữ** từ `raw_text` của chapter, kèm bằng chứng | ✅ |
| **Tầng 2** | Rút **tín hiệu xưng hô** (hậu tố kính ngữ, đại từ nhân xưng) từ bản gốc | ✅ |
| **Tầng 3** | Nhập tên bộ truyện → gợi ý phiên âm, **chỉ hiện tên có thật trong chapter** | ⛔ để sau (§7) |
| — | Tự dịch tên, tự điền `target_term`, tự duyệt, tự sửa lời thoại | ⛔ **không bao giờ** |

**Không gọi LLM.** Toàn bộ E17 là luật tất định trên chuỗi — cùng đầu vào cho ra cùng đầu ra,
chạy offline, giải thích được cho người dùng. Đây cũng là lựa chọn E13 đã lấy (`scanner.py`).

## 4. Thiết kế — Tầng 1: ứng viên thuật ngữ

### 4.1 Đầu vào

Toàn bộ `OCRResult.raw_text` của project, join qua `TextRegion` → `Page` (đúng truy vấn
`scanner.py:82` đang dùng), chỉ lấy region có `OCRStatus` đã xong.

### 4.2 Luật theo từng ngôn ngữ — mỗi thứ tiếng một bài toán khác nhau

Tái dùng `matching.chuan_hoa()` (NFC) và `khoa_thuat_ngu()`; **không** ghi ngược vào DB.

**`ja` — tín hiệu mạnh nhất, làm trước:**

| Luật | Ví dụ |
|---|---|
| Chuỗi katakana liền ≥ 2 ký tự | `ペッパー` |
| Chữ đứng **trước hậu tố kính ngữ** ⇒ cắt lấy phần tên | `カルロさん` → ứng viên `カルロ` |
| Chuỗi kanji 2–4 ký tự lặp ≥ 2 lần, không nằm trong danh sách chặn | `魔法` |

**`en` — có một cái bẫy phải xử ngay:**

Luật hiển nhiên là "chữ viết hoa giữa câu". **Nhưng chữ trong truyện tranh tiếng Anh rất hay được
lồng chữ TOÀN CHỮ HOA** — lúc đó tín hiệu viết hoa **chết hoàn toàn** và luật ngây thơ sẽ trả về
mọi từ trong chapter.

⇒ Bắt buộc: đo tỉ lệ chữ hoa của chính chapter đó trước. Vượt ngưỡng (đề xuất 70 %) ⇒ **chuyển
luật**: bỏ tín hiệu viết hoa, dùng *tần suất lặp + không nằm trong danh sách từ phổ thông tiếng
Anh + đứng cạnh danh xưng (`Sir`, `Lord`, `Master`, `Mr`, `Miss`)*. Ngưỡng này **phải đo trên
`test_fixtures/external/` (Pepper&Carrot) và trên `pilot_uat_001` rồi mới chốt**, không lấy theo
cảm tính.

**`zh` — yếu nhất, nói trước để không hứa quá:** không có khoảng trắng, không có chữ hoa. Chỉ còn
n-gram 2–4 ký tự lặp ≥ 2 lần + tiền tố xưng danh (`小`, `老`, `阿`) và hậu tố (`先生`, `大人`,
`前辈`). Nhiễu sẽ cao hơn hai thứ tiếng kia — **nói thẳng trên giao diện**, không giả vờ ba ngôn
ngữ chất lượng như nhau.

### 4.3 Mỗi ứng viên phải mang bằng chứng

Không có bằng chứng thì đây chỉ là một danh sách chữ, và người dùng không có cơ sở nào để duyệt:

```
{ "term": "ペッパー", "term_key": "ペッパー", "count": 7,
  "pages": [1, 2, 5],
  "quotes": [ {"page_order": 1, "region_id": "…", "text": "ペッパー、待って!"} ],   // tối đa 3
  "type_guess": "character_name",         // GỢI Ý, không phải kết luận
  "reason": "katakana_run | trước hậu tố さん (3 lần)" }
```

`type_guess` chỉ để điền sẵn ô "Loại" cho đỡ một cú bấm — người dùng đổi thoải mái.

### 4.4 Lọc và xếp hạng

- **Bỏ** thứ đã có trong glossary của project (so bằng `source_term_key`) — kể cả `rejected`.
- **Bỏ** ứng viên chỉ xuất hiện 1 lần *ở ngôn ngữ zh/en-toàn-hoa* (nhiễu cao); `ja` katakana thì
  giữ từ 1 lần vì tín hiệu mạnh.
- Xếp theo `count` giảm dần, **trần 50 mục** một lượt.

## 5. Thiết kế — Tầng 2: tín hiệu xưng hô

Xưng hô tiếng Việt **không** suy ra được từ danh sách tên — nó phụ thuộc quan hệ, tuổi, vai vế.
Nhưng bản gốc thường nói thẳng ra, và phần đó rút được bằng luật:

| Ngôn ngữ | Tín hiệu trong bản gốc | Gợi ý (kèm câu thật) |
|---|---|---|
| `ja` | `-様/さま`, `-殿` | ngài / đại nhân · `speech_register: formal` |
| `ja` | `-ちゃん`, `-くん` | em / cậu · `casual` |
| `ja` | `先輩`, `先生` | tiền bối / thầy |
| `ja` | 俺 · 僕 · 私 · わし · あたし | tao–tôi · tớ · tôi · lão phu · tui |
| `zh` | `大人`, `前辈`, `师父` · 本座 · 在下 | ngài · tiền bối · sư phụ · bổn toạ · tại hạ |
| `en` | `Sir/Lord/Lady/Master` · `thou/thee` | ngài / phu nhân · giọng cổ (`archaic`) |

Đầu ra là **gợi ý cho ô `vietnamese_pronoun_guidance` và `speech_register`**, luôn kèm câu thoại
gốc chứa tín hiệu và trang chứa nó.

### 5.1 Ranh giới không được vượt

`CharacterVoiceProfile` **cố ý không có trường "độ tin cậy"** (docstring model đã ghi: *đây là chỉ
dẫn biên tập của người dùng, không phải kết luận của máy*). Nên:

- E17 **không ghi** một dòng nào vào `character_voice_profile`.
- Gợi ý chỉ tồn tại trong **phản hồi API** và trên giao diện, cho tới khi người bấm nhận.
- Nhận rồi ⇒ nó thành chữ của người dùng trong form, sửa được, và vẫn phải bấm lưu như hiện tại.

## 6. Giao diện — bỏ đúng phần việc máy làm được

**Không có nút "Duyệt tất cả".** `target_term` (cách dịch đã chốt) và `definition` là quyết định
của người; máy điền vào đó là quay lại đúng cái bẫy §2.

Luồng đề xuất:

```
[Thuật ngữ của chapter]                        ← trạng thái rỗng hiện tại
   └── nút "Tìm trong chapter"  ────────────►  bảng ứng viên
                                                 ☐ ペッパー   7 lần   trang 1,2,5   "ペッパー、待って!"
                                                 ☐ 魔法       4 lần   trang 2,3     …
                                                        │
                                          chọn nhiều → mở lần lượt form "Thêm thuật ngữ"
                                          ĐÃ ĐIỀN SẴN: Thuật ngữ gốc · Loại · trích dẫn hiện bên cạnh
                                          NGƯỜI GÕ:    Cách dịch đã chốt · Giải nghĩa
```

Người dùng thôi phải *nhớ* và *gõ lại nguyên văn tiếng Nhật* — hai việc tốn công và dễ sai nhất.

**Trạng thái rỗng phải phân biệt được ba thứ** (nguyên tắc số 3, và là bài học đã trả giá ở
`worker: khong_ro` của E1a):

| Tình huống | Thông báo |
|---|---|
| Chapter chưa chạy OCR | "Chưa đọc chữ trong chapter — chạy xong bước đọc chữ rồi tìm lại" |
| Đã OCR, không có ứng viên nào | "Đã tìm trong N vùng chữ, không thấy danh xưng lặp lại nào" |
| Tất cả ứng viên đã có trong glossary | "Mọi danh xưng tìm được đều đã có trong danh sách thuật ngữ" |

Ba câu này **không được gộp** — "không có gì" và "chưa chạy" là hai chuyện khác nhau.

## 7. Tầng 3 (để sau) — nếu vẫn muốn dùng tên bộ truyện

Khi làm, cổng chặn bắt buộc: **chỉ hiện gợi ý cho những tên đã xuất hiện trong chữ của chapter
này** (đối chiếu với kết quả tầng 1). Tên nào model nghĩ ra mà chapter không có ⇒ loại thẳng,
người dùng không bao giờ nhìn thấy. Nhãn cố định: *gợi ý — chưa duyệt*.

Chính cổng đối chiếu đó biến "trí nhớ không kiểm chứng được" thành "gợi ý kiểm chứng được". Không
có nó thì đừng làm tầng 3.

## 8. API (dự kiến)

Cả hai **chỉ đọc, không ghi**, nên `200` chứ không `202` — nguyên tắc số 4 (`202`) áp cho bước AI,
còn đây là xử lý chuỗi trên dữ liệu có sẵn.

| Endpoint | Trả về |
|---|---|
| `GET /api/v1/projects/{project_id}/term-candidates` | danh sách ứng viên + bằng chứng + `da_quet_bao_nhieu_vung` |
| `GET /api/v1/projects/{project_id}/voice-signals` | tín hiệu xưng hô nhóm theo tên đã biết + câu gốc |

⚠️ **Phải đo độ trễ trước khi chốt chạy đồng bộ.** Chapter 20 trang × ~30 vùng = ~600 chuỗi ngắn —
dự kiến rẻ, nhưng *dự kiến* không phải *đo được*. Nếu p95 vượt 500 ms thì chuyển sang job nền như
mọi bước nặng khác.

**DB: không bảng mới, không migration.** Ứng viên tính tại chỗ mỗi lượt gọi. Đổi lại, thứ người
dùng đã bỏ qua sẽ hiện lại ở lượt sau — chấp nhận ở bản đầu; nếu thực tế thấy phiền thì mới thêm
một bảng nhỏ ghi "đã bỏ qua" (đúng nguyên tắc số 7: chỉ tạo bảng đủ cho mini-spec hiện tại).

## 9. Test bắt buộc

| Nhóm | Test |
|---|---|
| Tất định | cùng đầu vào ⇒ cùng thứ tự đầu ra (chạy 2 lần) |
| `ja` | katakana · cắt đúng phần tên trước `さん/様/ちゃん` · **không** cắt nhầm khi hậu tố nằm giữa từ |
| `en` | **bẫy TOÀN CHỮ HOA**: chapter toàn chữ hoa ⇒ không được trả về mọi từ; luật dự phòng chạy |
| `zh` | n-gram lặp ra ứng viên; từ phổ thông bị chặn |
| Lọc | thuật ngữ đã có trong glossary (mọi `status`, kể cả `rejected`) không hiện lại |
| Bằng chứng | `count` khớp số lần đếm tay; `quotes` là **nguyên văn** trong `raw_text`, không phải chuỗi dựng lại |
| Rỗng | 3 tình huống ở §6 cho ra 3 thông báo khác nhau |
| Ranh giới | gọi API xong ⇒ **0 dòng** được ghi vào `glossary_entry` và `character_voice_profile` |

Test cuối cùng là cái gắt nhất: nó khoá lời hứa "máy không tự duyệt gì cả".

## 10. Ước lượng (giờ-AI, theo `/task-et`)

| Phần | ET |
|---|---|
| Rút ứng viên `ja` + `en` (kèm bẫy toàn-hoa) + test | 2,0 h |
| Rút ứng viên `zh` + test | 1,0 h |
| Tín hiệu xưng hô 3 ngôn ngữ + test | 1,5 h |
| 2 endpoint + schema + test hợp đồng | 1,0 h |
| Giao diện: bảng ứng viên, chọn nhiều, điền sẵn form, 3 trạng thái rỗng | 2,0 h |
| Đo độ trễ thật + báo cáo | 0,5 h |
| **Tổng** | **8,0 h** |

Đề xuất chia hai lượt: **E17a** = `ja`+`en` + endpoint + giao diện (5 h, đủ dùng cho dữ liệu thật
đang có); **E17b** = `zh` + xưng hô (3 h).

## 11. Giới hạn đã biết — nói trước

1. **OCR sai thì ứng viên sai.** Tên bị đọc nhầm một ký tự sẽ thành một ứng viên rác, hoặc thành
   hai ứng viên gần giống nhau. E17 **không** sửa OCR và không gộp gần đúng (gộp gần đúng là một
   quyết định về nghĩa — việc của người).
2. **Không biết ai nói câu nào.** Hệ thống chưa gán lời thoại cho nhân vật, nên tín hiệu xưng hô
   là "trong chapter có tín hiệu này", không phải "nhân vật X xưng thế này với Y".
3. **`zh` nhiễu cao hơn** `ja`/`en` — sẽ ghi thẳng trên giao diện.
4. **Không có tri thức ngoài chapter** ở tầng 1+2. Tên viết tắt, biệt danh chỉ xuất hiện ở chapter
   khác thì không tìm ra được.
5. Trần 50 ứng viên/lượt là con số **chọn**, chưa phải con số **đo**; chỉnh sau khi chạy thật.

## 12. Chờ chủ dự án chốt

1. Làm **E17a trước** (`ja`+`en`, 5 h) hay làm trọn gói 8 h?
2. Có cần tầng 3 (tên bộ truyện) không, hay tầng 1+2 đã đủ giảm phiền?
3. E17 **xếp trước hay sau** việc đóng P3h trên host? (Theo `CLAUDE.md` thì P3h phải audit pass
   trước; đảo thứ tự là quyết định của chủ dự án, không phải của tôi.)
