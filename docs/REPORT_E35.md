# Báo cáo Mini-Spec E35 — Chạy chapter thật trên production

**Project:** Translation · **Phase:** E · **Ngày:** 2026-09-14
**Production:** `translation-api` v66, build từ `7d334236` · `translation-web` v35 (không deploy lại)
**Trạng thái:** **PARTIAL — chờ người dùng review chất lượng dịch** (§8.5)

## 1. Summary

| | |
|---|---|
| Chapter | `ba08c857-82d7-4639-8836-3c75cdb8d05a` — *"test dịch tiếng anh"* |
| Vật liệu | `ep39_The-Tavern`, Pepper&Carrot, bản EN, **12 trang**, CC-BY 4.0 (David Revoy) |
| Ngôn ngữ | Tiếng Anh → Việt · mục đích *Đọc cá nhân* |
| Engine | **Dịch theo ngữ cảnh** (`llm_context`), chốt vào mẻ `97bdb9d1` |
| Giới hạn gọi | 10 lượt/phút (mặc định, **không đổi**) |
| Thời lượng | **28 phút 48 giây** |
| Kết quả | **10/12 trang xong · 2 hỏng** |

**Và hai trang hỏng đều KHÔNG phải trang truyện:**

```
trang 2  = E39P02  ->  trang TOÀN TRANH, không một bong bóng thoại   (no_region)
trang 12 = E39P12  ->  trang BẠT, danh sách người tài trợ, 1200x2965 (crop_too_large)
```

⇒ **10/10 trang truyện chạy xong.** Con số "10/12 · 2 hỏng" nghe tệ hơn thực tế.

Việc hai lỗi rơi đúng vào hai trang đó cũng **xác nhận thứ tự trang đã đúng**: `E39P12` là tệp
duy nhất cỡ `1200x2965`, và nó nằm ở vị trí 12. Nếu thứ tự còn đảo (lúc đầu người dùng bị
`1 = E39P12`) thì lỗi phải rơi vào vị trí khác.

## 2. Audit Before Run

**Đã xác nhận trước khi chạy:**

```
v66 online · build từ 7d334236 (khớp commit E34) · 11/11 chặng
celery ready 04:38:16 · /healthz ok
llm_configured: true · translate_default_engine: llm_context
KHÔNG có biến E32_*/E34_* trên prod ⇒ mặc định trong mã có hiệu lực
KHÔNG deploy translation-web — `git diff -- frontend/` rỗng (nguyên tắc E26)
12 ảnh qua BA phép kiểm: HTTP 200 · magic byte ffd8ff · > 20 KB
```

### Hai chỗ trong spec KHÔNG thực hiện được như viết

**§3.1 đòi "Japanese + English if possible" — không diễn đạt được.** `Project.source_lang` là **một
giá trị**, không phải danh sách. Một chapter chỉ có một ngôn ngữ nguồn.

Và hai lựa chọn **kéo ngược nhau**: đo token tiết kiệm của E34 **chỉ làm được với tiếng Anh** (đã
đo: `manga-ocr` không trả điểm tin cậy cho 0/16 vùng ⇒ cờ chất lượng tiếng Nhật là suy đoán, luật
E34 bật 100% trang). Người dùng chọn **tiếng Anh**, phần tiếng Nhật tách thành **E35-JP**.

**§5.2.2 đòi "confirm E34 enabled in production" — không có cách kiểm tự chứng.** `/healthz` không
phơi cờ này, và §3.4/§10 cấm deploy trong lúc chạy nên không thể thêm trường. Dùng **log runtime**
làm bằng chứng chính — xem §5.

## 3. Run Execution

### Vì sao 28 phút — giải thích được bằng số

```
detect    ~50,6s/trang     ocr      ~40,7s/trang     inpaint  ~39,8s/trang
translate   ~3,3s/trang     typeset   ~1,7s/trang
                                    một trang ≈ 136s × 12 ≈ 27 phút
```

Khớp gần khít 28:48. **Thời lượng KHÔNG do lỗi** — đó là chi phí thật của ba bước nặng nhân 12
trang, chạy **tuần tự** vì worker dùng `pool=solo`.

⚠️ Tôi đã ước sai lúc đầu ("~25 phút"), vì dùng con số 107 s/trang của E23 — đó là **trung vị một
trang qua hết năm bước khi chạy liên tục**, không phải thời gian người dùng chờ từ lúc bấm.

### Job TRÙNG — lỗi E23 đã biết, đo được trên production

Trên trang `a744aede` (21 vùng):

```
translate  2 job   token_cost 935 + 959 = 1894      -> tốn thêm ~959 token
typeset    4 JOB   d7d65ee1 · 548f30e9 · 29a94fcf · 33a37be0
                   mỗi lần "xoá 21 kết quả cũ" rồi ghi lại y hệt
inpaint    2 job được đẩy
07:14      job inpaint CŨ nổ ra sau 24 PHÚT, bị chặn đúng:
           precondition_failed: page đang ở 'typeset_done', cần 'ocr_done'
```

**Nguyên nhân đã chẩn đoán** (đọc mã, không đoán):

```
PageStatus: queued · detecting · detected · detection_failed · ocr_done ·
            inpainted · inpaint_needs_review · translated · typeset_done · ready_for_export
                       ^^^^^^^^^
            CHỈ detect có trạng thái "đang chạy"
```

`buoc_cho_trang` suy bước kế tiếp **từ `Page.status`**. Chú thích của nó nói rõ `detecting` trả
`None` *"có chủ đích: trang đang chạy dở"*. Nhưng **bốn bước còn lại không có trạng thái đang-chạy
nào**, nên:

```
OCR xong -> Page.status = ocr_done, commit
  auto-chain đẩy job inpaint                    (tasks.py:472)
  mẻ tick, đọc thấy ocr_done -> đẩy job inpaint  (orchestrator.py:202)
  Page.status vẫn ocr_done cho tới khi inpaint XONG
  -> mọi tick trong khoảng đó đẩy thêm một job
```

**Không sửa trong lượt này** (§3.4/§10). Xem §7.

### Không có worker chết, không có vượt hạn mức

```
bộ nhớ [inpaint: trước] RSS 1454,6 MB -> [sau] 1471,1 MB
```

Dưới ngưỡng 1500 MB nên không phải nhả model. **Không có `worker_died` nào trong lượt này** —
khác E23 (worker chết 3 lần). Không có lỗi hạn mức.

## 4. Manual Review Findings

**CHỜ NGƯỜI DÙNG REVIEW.** Theo phân công đã chốt (phương án C), phán xét *"translation quality
acceptable"* (§8.5) là quyết định của người dùng, không phải của tôi.

Dữ liệu tổng hợp cả chapter (từ giao diện):

```
135 vùng chữ trong chapter
 78 vùng CẦN rà soát
 16 vùng không có dấu hiệu bất thường
 41 vùng CHƯA đánh giá được — chưa chấm khác với chấm sạch

máy đoán từng vùng là gì:  chưa chắc 72 · có khả năng là chữ cần dịch 16
                           có thể là hiệu ứng âm thanh 5 · có thể là số/trang trí 1
```

Cổng xuất file báo:

```
9/12 trang sẽ được xuất
  3 trang bị BỎ QUA vì chưa chèn chữ xong
  1 vùng còn tràn khung
  3 bong bóng TRỐNG vì chưa đọc được chữ gốc
  2 bong bóng TRỐNG vì font không có ký tự trong bản dịch   <- F1 kích hoạt
```

### 4.1 Danh sách trang cần người dùng rà soát (Bước 6b) — kết quả `NULL`

Cách chọn trang, và đây là phần phải nói rõ vì nó quyết định giá trị của cả mục: **tôi không truy
được production** để đọc từng trang (các endpoint đó cần token, mà token không được đưa vào
transcript). Nên danh sách dựng từ bằng chứng ĐÃ CÓ, không phải từ việc mở từng trang ra xem:

- **Trang 3, 5, 6, 7** — có bằng chứng trực tiếp là có lời thoại: ứng viên `AXE` khai đúng bốn
  trang này, kèm ba trích dẫn nguyên văn ở trang 3 (§5 mục E17).
- **Trang 1** — trang truyện đầu, detect ra 5 vùng (§5 M2). Trang mở đầu là chỗ danh xưng và
  giọng nhân vật được đặt ra, nên sai ở đây lan ra cả chapter.
- **Trang 2** — đối chứng âm: trang toàn tranh. Đúng ra phải hiện là **trang hoàn thiện**, hiện
  đang hiện "Hỏng" (E38, chưa deploy).
- **Trang 12** — đối chứng âm: trang bạt, `crop_too_large`. Không phải trang truyện, **không**
  phán xét chất lượng dịch ở đây.

Trang 4, 8, 9, 10, 11 **không có bằng chứng gì** để xếp ưu tiên — tôi không xếp bừa vào danh sách
để cho đủ số.

| # | Trang | Vì sao chọn | E27 `fit_ok` | E18 nới khung | Chất lượng dịch (§8.5) |
|---|---|---|---|---|---|
| 1 | **1** | trang mở đầu, 5 vùng | `NULL` | `NULL` | `NULL` |
| 2 | **3** | 3 trích dẫn thoại nguyên văn | `NULL` | `NULL` | `NULL` |
| 3 | **5** | có `AXE` | `NULL` | `NULL` | `NULL` |
| 4 | **6** | có `AXE` | `NULL` | `NULL` | `NULL` |
| 5 | **7** | có `AXE` | `NULL` | `NULL` | `NULL` |
| 6 | **2** | đối chứng: không có chữ | n/a | n/a | n/a — phải là "xong" |
| 7 | **12** | đối chứng: trang bạt | n/a | n/a | n/a — không phán xét |

**Ba câu hỏi cho mỗi trang truyện**, mỗi câu trả được bằng "đạt / không đạt":

| | Câu hỏi | "Đạt" nghĩa là |
|---|---|---|
| **E27** | Chữ có **nằm trong** bong bóng không? | Không chữ nào tràn ra khỏi viền bong bóng |
| **E18** | Khung chữ có **che nét vẽ** không? | Khung dừng ở viền bong bóng, không phình ra tranh |
| **§8.5** | Nghĩa có **đúng ngữ cảnh** không? | Đọc liền mạch; danh xưng và giọng nhất quán giữa các trang |

**Sáu vùng đã bị máy tự gắn cờ** (§4) cần tìm và xem riêng — máy đã tự khai là có vấn đề, nên đây
là chỗ chắc chắn có gì để xem:

| Số vùng | Máy tự khai | Cần người dùng quyết |
|---|---|---|
| **1** | còn **tràn khung** | sửa tay hay chấp nhận |
| **3** | bong bóng **trống** vì chưa đọc được chữ gốc | gõ tay chữ gốc, hay để trống |
| **2** | bong bóng **trống** vì **font thiếu ký tự** (F1) | sửa lại chữ dịch, hay đổi font |

Chưa truy được trang nào chứa vùng "tràn khung" — log của lượt chạy đã bị xoá (§7). Trên màn rà
soát, vùng bị cờ có nhãn riêng nên tìm được bằng mắt.

## 5. Legacy Debt Verification

### E34 — ĐÓNG. Bằng chứng tự chứng cho §5.2.2

```
E32/E34 trang a744aede-c11d-42f4-936e-1d08fe24c0fb: không gửi ảnh (du_sach_24%)
```

24% < ngưỡng 30% ⇒ **không gửi ảnh**, đúng luật. Dòng log này chỉ tồn tại trong mã E34, nên nó
chứng minh **cơ chế đang chạy thật**, không chỉ được cấu hình đúng.

### E16 chữ nghiêng — ĐÓNG. Lần đầu có mẫu thật

```
hướng chữ (inpaint) trang a744aede:
  {'tong': 21, 'horizontal_ltr': 17, 'tt_ready': 17,
   'rotated_horizontal': 4, 'tt_needs_review': 4}
```

**4 vùng chữ nghiêng.** `REPORT_E16` từng ghi *"chưa có mẫu thoại nghiêng nào — cả 11 mẫu đều là
SFX hoặc bảng chữ"*. Đây là mẫu thật đầu tiên.

### E18 / A1 nới khung — ĐÓNG. Đo trên truyện thật

20 vùng được nới, hệ số từ **1,0 đến 8,29**:

```
140x35  -> 348x76   (hệ số 8,2857)     101x29 -> 119x70  (hệ số 4,1817)
130x33  -> 127x81   (hệ số 3,5607)     241x67 -> 242x91  (hệ số 2,0222)
64x49   -> 52x40    (hệ số 1,0 — không nới, chạm nét vẽ ngay)
```

Sáu vùng có hệ số đúng 1,0 ⇒ phép nới **biết dừng khi chạm nét vẽ**, không phình bừa.

### E14 vùng an toàn — có số đo, và số đó KHÔNG đẹp

```
vùng an toàn (inpaint) trang a744aede:
  {'tong': 21, 'shape_derived': 0, 'fallback_rectangle': 19,
   'needs_review': 0, 'failed': 0, 'ready': 2}
```

**0/21 vùng tìm được hình bong bóng thật; 19 dùng khung chữ nhật dự phòng.** `REPORT_E14` từng ghi
*"5/5 bong bóng thật"* — nhưng đó là trên ảnh tổng hợp. Trên truyện thật, tỉ lệ là **0**.

Đây là món nợ MỚI phát hiện, không nằm trong danh sách bốn món nợ ban đầu của E35.

### E26-B/B2 chống vẽ trùng — chạy trên production

```
typeset trang a744aede: tổng 2 vùng KHÔNG vẽ chữ: ['256cdcf1', '0e30d819']
```

### E27 fit — trang này sạch

```
typeset job: 21 vùng (vừa 21, tràn 0, chưa có chữ 0, thiếu glyph 0), font=Bangers
```

Nhưng cổng xuất báo **1 vùng còn tràn khung** ở chapter ⇒ vùng đó ở trang khác, chưa truy được
(xem §7 về log bị xoá).

### E25 trần ô cắt — cổng chặn làm ĐÚNG việc

```
Ảnh 1200x2965 (3,6 triệu điểm) vượt ngưỡng 0.2 -> xoá chữ theo 1 cụm
crop_too_large: cần xử lý một ô 3,43 triệu điểm, vượt trần 2,60 triệu điểm đã đo là an toàn.
"Đã DỪNG trước khi chạy để không làm chết worker và mất các việc đang chạy khác."
```

Đây là trần `inpaint_max_crop_mpx = 2.6` đo ở E25. Nó **từ chối có chủ đích** thay vì để worker
chết — đúng thiết kế. Trang gây ra là **trang bạt**, không phải trang truyện.

### Kiểm chứng xoá chữ — ngưỡng E25 chạy đúng

```
kiểm chứng xoá chữ: vùng 3 đọc được 'a' (1 ký tự) — dưới ngưỡng 2, BỎ QUA   (x4 vùng)
inpaint job: 21 vùng, inpainted, còn chữ ở 0 vùng
```

### E17 term candidates — ĐÃ CHẠY. Route sống, nhưng kết quả gần như vô dụng

Người dùng bấm **"Tìm trong chapter"** lúc 14:4x ngày 14-09. Đường chạy **sống**:

```
Đã quét 132/135 vùng chữ
Bỏ qua 3 vùng chữ đọc chưa chắc chắn
Cách tìm cho ngôn ngữ này: chữ hoa 21% — dùng tín hiệu viết hoa giữa câu
```

`132 + 3 = 135` ⇒ con số tự khớp, và nhánh `needs_manual` bị loại đúng như E17 thiết kế.
`chữ hoa 21%` ⇒ chọn nhánh "viết hoa giữa câu", không phải nhánh `toan_hoa`.

**Ứng viên trả về — 5/6 là rác:**

| danh xưng | số lần | trang | đúng? |
|---|---|---|---|
| David | 8 | **12** | sai — tên người tài trợ |
| Alex | 7 | **12** | sai — tên người tài trợ |
| **AXE** | 7 | **3, 5, 6, 7** | **ĐÚNG** — vũ khí trong truyện |
| Christian | 7 | **12** | sai — tên người tài trợ |
| Michael | 7 | **12** | sai — tên người tài trợ |
| Paul | 6 | **12** | sai — tên người tài trợ |

**Về con số "6": đó là số mục ĐỌC ĐƯỢC trên ảnh chụp của người dùng, KHÔNG phải tổng.** Ảnh bị
cắt giữa mục thứ sáu, và trần danh sách là `TRAN_UNG_VIEN = 50`. Nên số đúng phải ghi là
**≥6 ứng viên, trong đó 5 đã xác định là false positive**. Tổng thật: `NULL` — chưa đo.

**Nguyên nhân:** mọi vùng chữ đọc được đều bị coi là lời nhân vật, kể cả trang 12 là **trang bạt
liệt kê người tài trợ**. Luật "viết hoa giữa câu" chạy **đúng** — tên người tài trợ thật sự là
tên riêng viết hoa. Lỗi ở **nguồn dữ liệu**, không ở luật.

Thêm một hậu quả về khả năng đọc: mỗi ứng viên kéo theo ba trích dẫn dài **1389 ký tự** (nguyên cả
vùng chữ trang bạt), nên màn hình dài hàng chục nghìn ký tự và **không tìm nổi** chỗ nào chứa danh
xưng đang xét. Bằng chứng mạnh mà không dùng được thì không còn là bằng chứng.

**Fix đề xuất: E39 — CHỜ XÁC NHẬN, CHƯA DEPLOY.** Xem §7.

**Trạng thái món nợ E17:** tầng 1 (rút ứng viên) **đã kiểm thật, có kết quả, kết quả xấu**. Tầng 3
(đối chiếu AniList) vẫn **CHƯA kiểm thật lần nào**.

Hệ quả cho E31: người dùng **chưa duyệt** thuật ngữ nào ⇒ prompt **không** được nối gì — đúng bất
biến đã dựng ("chưa chốt gì thì prompt không đổi một ký tự"). Nên lượt này **vẫn không kiểm được
E31**.

### M2–M6 trên truyện thật

| Bước | Số đo | Nhận xét |
|---|---|---|
| M2 detect | 5 vùng (trang 1) · 21 vùng (`a744aede`) · **0 vùng** (trang 2) | 0 vùng ở trang 2 là ĐÚNG — trang đó không có chữ |
| M3 OCR | `5 region (0 needs_manual)` · engine `paddle_ocr` | 3 bong bóng trống vì chưa đọc được chữ (cả chapter) |
| M4 inpaint | `còn chữ ở 0 vùng`, 39,8s | sạch |
| M5 translate | `21 vùng (0 dòng rỗng)`, `engine=llm_context`, `fallback: False` | **chờ người dùng phán xét chất lượng** |
| M6 typeset | `vừa 21, tràn 0` (trang này); **1 vùng tràn** cả chapter | |

## 6. Token Cost Analysis

⚠️ **KHÔNG đo được đầy đủ, và đây là lý do.**

Dòng log người-đọc **bị nền tảng che số**:

```
translate job 7d7a44f8: 21 vùng, engine=llm_context, token=*** xoá 0 bản dịch cũ, 3.3s
```

Định dạng gốc là `token=%s, xoá %d` — phần che ăn cả giá trị lẫn dấu phẩy. Số thật **chỉ đọc được
từ dict kết quả task Celery**:

```
'token_cost': 935      (job 7d7a44f8)
'token_cost': 959      (job 30abc556 — job TRÙNG của cùng trang)
```

**Và bộ đệm log chỉ giữ phần cuối lượt chạy** — `nextCursor: null` khi lật ngược. Log của 11 trang
kia **đã bị xoá**. `token_cost` từng trang cũng lấy được qua `GET /pages/{id}/translation`, nhưng
đường đó **cần đăng nhập** mà tôi không có.

⇒ **Số đo có được: 1 trang / 12.** Không suy ra 12 trang từ một trang rồi trình bày như số đo.

Trang đo được: **935 token cho 21 vùng, KHÔNG gửi ảnh** (`du_sach_24%`). Nếu trang này gửi ảnh thì
theo hằng số +1166 đo ở E32, nó sẽ là ~2101 token. Đây là **số suy ra**, không phải số đo.

## 7. Remaining Limits / Follow-ups

> **Ba mục dưới đây (E38 · E39 · E40) là follow-up PHÁT SINH trong lúc chạy E35, KHÔNG phải
> phần "đã sửa" của E35.** Trạng thái chung: *phát hiện trong lúc chạy E35, chờ mini-spec riêng,
> **CHƯA deploy***. Mã của E38/E39 đã viết và test xanh (1551 passed · 6 skipped ·
> `pytest_exit=0`) nhưng **chưa commit, chưa push, chưa tới production** — đang chờ người dùng
> xác nhận từng mục. E40 đã được cho phép đi cùng lượt deploy sau.

### E38 (follow-up, CHƯA deploy) — trang không có chữ bị loại khỏi file xuất

Trang 2 (`E39P02`) **toàn tranh, không một bong bóng thoại**. `no_region` là **hành vi đúng**.
Nhưng:

```
giao diện xếp nó: "Hỏng"
cổng xuất:        "3 trang sẽ bị BỎ QUA vì chưa chèn chữ xong"
```

⇒ **truyện xuất ra thiếu trang.** Một trang không có chữ thì đúng ra là *"xong, không có gì để
dịch"* và **phải nằm trong file xuất y như ảnh gốc**. Đây là mất dữ liệu ở đầu ra, và là phát hiện
đáng giá nhất của E35.

### E39 (follow-up, CHƯA deploy) — trang bạt đẻ ra danh xưng rác

Hiện tượng và số đo ở §5 (mục E17). Phép phân biệt đề xuất: **tỉ lệ từ nối** — người nói thì có
`and/you/the/that`, danh sách tên thì không.

**Món nợ bằng chứng ban đầu: cỡ mẫu n = 3.** Đã ĐÓNG — đo lại trên **211 vùng `OCRStatus.ok`
tiếng Anh thật** (3 chapter, DB dev). Kết quả đổi chính thiết kế:

```
vùng >= 20 từ:   10 / 211 (4,8%)
nhóm được GIỮ:   22, 23, 24, 26 từ      (từ nối 19,2 - 54,2%)
nhóm bị BỎ:      146 ... 723 từ         (từ nối  0,0 -  5,7%)
                 ^^^ khoảng trống 26 -> 146 RỖNG
```

⇒ **trần nâng 20 → 100 từ.** Cùng kết quả trên dữ liệu đã đo (đã thử 20/40/60/80/100/120/146:
đều bỏ đúng 6 vùng), nhưng có lề 3,8× so với lời thoại dài nhất. Và lề đó không phải lý thuyết:
mẫu lời thoại-đọc-danh-sách 21 từ / 0% từ nối **bị loại oan ở trần 20**, được giữ ở trần 100.
Đúng ca false negative mà người dùng chỉ ra ở mục (d) — **spec đầu của tôi có lỗi thật, phép đo
bắt được trước khi deploy.**

Chạy lại trên chapter thật `04e7b2c1` (163 vùng): **726 ứng viên → 25**, và 25 cái còn lại đúng
là thuật ngữ truyện (Potions, Chaosah, Pepper, Carrot, King). Hai chapter không có trang bạt:
**không đổi một ứng viên nào**.

### E40 (follow-up, được phép deploy cùng lượt sau) — file `.cbz` tải về không mở được

`ExportFormat.zip` đã có từ M8 ⇒ lỗi **chỉ đường**, không phải thiếu tính năng. Không endpoint
mới: nút gọi `POST /projects/{id}/export` với `{"format": "zip"}`.

### Job trùng — đã chẩn đoán, có công cụ mới

4× typeset, 2× translate (~959 token lãng phí/trang), 2× inpaint. Nguyên nhân ở §3.

Hai lần thử sửa trước đều tệ hơn (một lần làm đỏ test đẩy song song, một lần tạo kiểu kẹt vĩnh
viễn mới). **Nhưng E22 đã thêm `Job.heartbeat_at`** — cột đó chưa tồn tại khi thử hai lần trước, và
nó phân biệt được đúng thứ trước đây không phân biệt được:

| | job `running` + nhịp tim MỚI | job `running` + nhịp tim CŨ |
|---|---|---|
| Nghĩa | đang chạy thật | worker đã chết, job mồ côi |
| Nên làm | **đừng đẩy** | **đẩy lại** |

### Trang quá lớn (trang bạt) bị hỏng thay vì bỏ qua êm

`crop_too_large` là cổng chặn làm đúng, nhưng kết quả là một trang **"Hỏng"** đỏ. Trang bạt không
cần dịch; đúng ra nên hạ độ phân giải rồi chạy, hoặc xếp *"bỏ qua, trang không cần dịch"*.

### Giao diện tải ảnh KHÔNG sắp theo tên và KHÔNG cho kéo đổi thứ tự

`Dropzone` nối thêm theo đúng thứ tự trình duyệt trả về (`onDoi([...files, ...nhan])`), trong khi
giao diện khẳng định *"thứ tự dưới đây chính là thứ tự trang"*. Người dùng đã vào đúng bẫy này
trong lượt E35 và phải làm lại. Hậu quả nếu không phát hiện: **truyện đảo trang, không cảnh báo**.

### E14 tìm hình bong bóng: 0/21 trên truyện thật

Xem §5. Món nợ MỚI.

### Chưa làm được trong lượt này

- ~~**E17 term candidates**~~ — ĐÃ chạy 14-09, xem §5. Tầng 3 (AniList) vẫn chưa kiểm
- ~~**Phân bố tỉ lệ từ nối trên ≥100 vùng**~~ — ĐÃ đo 211 vùng, xem §7 (E39)
- **E31 nhất quán xuyên trang** — chưa chốt thuật ngữ nào nên không có gì để kiểm
- **token từng trang** — 1/12 (§6)
- **Chất lượng dịch** — chờ người dùng (§4)
- **1 vùng tràn khung** của chapter — chưa truy được trang nào (log đã xoá)

### KHÔNG kết luận

Theo §3.6: **một chapter không phải bằng chứng thống kê.** Không kết luận "sẵn sàng production"
từ lượt này.

## 8. Commit / Deploy State

```
translation-api  v66 · commit 7d334236 · deploy 04:33 → 04:38
translation-web  v35 · KHÔNG deploy lại (git diff frontend rỗng)
Chapter          ba08c857 — GIỮ LÀM BẰNG CHỨNG, không xoá (§3.9)
Trong lúc chạy   KHÔNG đổi mã, KHÔNG đổi cấu hình, KHÔNG deploy (§3.4, §10)
```

**E35 = PARTIAL.** Không đánh CLOSED vì §4 (chất lượng dịch) chờ người dùng, và E17 chưa chạy.
