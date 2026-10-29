# Báo cáo Mini-Spec E17 — Gợi ý thuật ngữ & xưng hô rút từ chính chapter

**Ngày:** 2026-09-01 · **Trạng thái:** ✅ **DỰNG XONG TRÊN MÁY DEV — CHƯA DEPLOY, CHƯA VERIFY TRÊN HOST**
**Xuất phát:** yêu cầu của chủ dự án · **Thiết kế:** `docs/SPEC_E17_TERM_CANDIDATES.md`
**Đụng tới:** E13 (thuật ngữ & rà soát nhất quán) · **Migration:** `0011_e17`

> ⚠️ **Về thứ tự mini-spec.** `CLAUDE.md` quy định không mở mini-spec mới khi mini-spec trước
> chưa audit pass, mà P3h thì chưa verify được trên host (host `cmc-1` chết từ 31/08 19:00).
> Chủ dự án **đã quyết định làm E17 trước** khi được hỏi. Ghi ra đây để nó là một quyết định có
> chủ, không phải một quy ước bị bỏ qua trong im lặng. P3h vẫn còn nợ nguyên phần verify.

## 1. Summary

Màn "Thuật ngữ của chapter" và "Giọng nhân vật" là hai form trống: người dùng phải tự nhớ trong
chapter có danh xưng nào rồi gõ lại nguyên văn — trong khi chữ đã nằm sẵn trong
`ocr_result.raw_text` từ bước đọc chữ.

E17 chia đôi việc đó:

| Nửa việc | Ai làm | Trạng thái |
|---|---|---|
| Tìm ra có những danh xưng nào, ở đâu, bao nhiêu lần, trích nguyên văn | **Máy** | ✅ tầng 1 |
| Rút tín hiệu xưng hô có thật trong bản gốc (kính ngữ, đại từ) | **Máy** | ✅ tầng 2 |
| Gợi ý cách dịch theo tên bộ truyện, **có cổng đối chiếu** | Máy đề xuất | ✅ tầng 3 |
| Quyết cách dịch và xưng hô | **Người** | không đụng vào |

**Không** làm đúng câu chữ của yêu cầu gốc ("nhập tên bộ truyện → AI lấy dàn nhân vật") — §2.

## 2. Audit Before Build — vì sao đảo chiều câu hỏi

Hỏi thẳng *"truyện X có nhân vật nào"* vướng nguyên tắc số 3 (`CLAUDE.md`: evidence-first):

1. Model **luôn trả lời**, kể cả khi không biết. Truyện ít tiếng tăm hoặc trùng tên ⇒ ra một dàn
   nhân vật nghe rất thật.
2. Nó **không biết chapter NÀY có ai**. Bộ 200 nhân vật, chapter của bạn có 3.
3. Thuật ngữ đã duyệt là **luật** để quét cả chapter (`GlossaryStatus.approved`). Một tên bịa
   được duyệt ⇒ mọi lượt rà soát sau đó báo sai ⇒ hỏng đúng thứ E13 sinh ra để bảo vệ.

Nên câu hỏi bị đảo lại:

```
KHÔNG hỏi:  "truyện X có những nhân vật nào?"                      -> không kiểm chứng được
MÀ hỏi:     "đây là những danh xưng CÓ THẬT trong chapter này của
             truyện X — người ta thường dịch chúng thế nào?"        -> kiểm chứng được
```

## 3. Design Choice

### 3.1 Ba tầng, tầng dưới không phụ thuộc tầng trên

Tầng 1 và 2 **không gọi LLM**, chạy offline, tất định. Mô hình chết thì bảng danh xưng vẫn dùng
bình thường — giao diện nói thẳng điều đó khi tầng 3 hỏng.

### 3.2 Luật theo từng ngôn ngữ — và cái bẫy của tiếng Anh

| Ngôn ngữ | Tín hiệu |
|---|---|
| `ja` | katakana · **tên đứng trước hậu tố kính ngữ** (さん/様/ちゃん/くん/殿/先輩/先生) · cụm kanji lặp |
| `en` | tên **sau danh xưng** (Sir/Lord/Master…) · viết hoa giữa câu · (toàn-hoa: tần suất + chặn từ phổ thông) |
| `zh` | tên trước hậu tố xưng danh (大人/前辈/师父…) · tiền tố 小/老/阿 · n-gram 2–4 lặp |

**Bẫy TOÀN CHỮ HOA.** Chữ lồng truyện tranh tiếng Anh rất hay viết hoa hết; lúc đó tín hiệu "viết
hoa = tên riêng" **chết hoàn toàn** và luật ngây thơ trả về *mọi từ* trong chapter. Nên hệ thống
đo tỉ lệ chữ hoa của chính chapter trước (`NGUONG_CHU_HOA = 0.70`) rồi **đổi luật**, và **nói ra
trên giao diện** nó đang dùng luật nào.

### 3.3 Đầu câu: không phải bằng chứng, nhưng vẫn là một lần xuất hiện

Đây là chỗ tinh tế nhất của luật tiếng Anh, và nó chỉ lộ ra khi test đỏ:

```
"I met Pepper today. Pepper was tired."   -> Pepper: 2 lần   (không phải 1)
"Pepper was tired. Pepper slept."         -> không có gì
```

Một từ viết hoa **đầu câu** viết hoa vì ngữ pháp ⇒ tự nó không chứng minh gì. Nhưng nếu từ đó đã
được chứng minh ở chỗ khác thì những lần nó đứng đầu câu **vẫn là những lần xuất hiện thật** — bỏ
đi là đếm **thấp hơn sự thật**, mà đó đúng là con số người dùng dựa vào để duyệt. Hiện thực bằng
hai lượt: lượt 1 nhận bằng chứng đủ mạnh, lượt 2 đếm thêm các lần đầu câu của từ đã được chứng minh.

### 3.4 Bằng chứng đi kèm mọi ứng viên

`count` · `pages` · **trích nguyên văn** (tối đa 3, lấy thẳng từ `raw_text`) · `reasons` (vì sao
được nêu) · `type_guess` (chỉ để điền sẵn ô "Loại"). Không có bằng chứng thì đây chỉ là một danh
sách chữ, và người dùng không có cơ sở nào để duyệt.

`type_guess = character_name` **chỉ khi** có bằng chứng danh xưng (kính ngữ / chức danh). Katakana
đơn thuần ⇒ `general_term`: katakana cũng dùng cho từ mượn và tiếng động.

### 3.5 Cổng đối chiếu của tầng 3 — hai lớp

1. **Danh sách do TA đưa vào.** Model không được thêm mục; nó chỉ điền cách dịch.
2. **Đối chiếu ngược.** Mỗi dòng phải nhắc lại **nguyên văn** thuật ngữ đã hỏi. Nhắc sai, hoặc
   nhắc một thứ không có trong danh sách ⇒ **loại thẳng**, đếm vào `dropped_count`.

`dropped_count > 0` là **bằng chứng sống rằng model có bịa** trong lượt đó, và nó được lưu vào DB
chứ không chỉ log. Prompt cũng chừa đường cho model **nói "không biết"** (`?`) — và câu đó
**không** bị tính là bịa.

### 3.6 Ranh giới không được vượt

- Tầng 1+2 **không ghi một dòng nào** vào `glossary_entry` / `character_voice_profile` (có test).
- Tầng 3 lưu vào bảng riêng dưới nhãn `goi_y_mo_hinh_chua_duyet`, **không** tạo thuật ngữ.
- Giao diện **không có nút "Duyệt tất cả"**: `target_term` và `definition` là quyết định biên tập.
- Không có ứng viên nào ⇒ **không gọi mô hình** (hỏi suông vẫn tốn tiền, và câu trả lời cho một
  danh sách rỗng chắc chắn là bịa).

## 4. Changed Files

| Tệp | Việc |
|---|---|
| `app/services/consistency/ungvien.py` | **Mới** — tầng 1+2, luật 3 ngôn ngữ, khử trùng theo vị trí |
| `app/services/consistency/goi_y_ten.py` | **Mới** — tầng 3: dựng prompt + cổng đối chiếu |
| `app/models/__init__.py`, `enums.py` | `TermSuggestionRun` + `TermSuggestionStatus` |
| `alembic/versions/0011_e17_term_suggestion.py` | **Mới** — 1 bảng, 1 enum, 1 index |
| `app/workers/tasks.py` | `run_term_suggestion_job` + `_run_term_suggestion` |
| `app/services/dispatch.py` | `dispatch_term_suggestion_job` |
| `app/services/translate/engines.py` | `goi_prompt_tho()` — mở lại hạ tầng xoay key/tắt thinking |
| `app/api/v1/routes.py`, `schemas/common.py` | 4 endpoint + 6 schema |
| `app/core/config.py` | `term_suggestion_timeout_seconds = 120` |
| `frontend/.../TermCandidatePanel.jsx` | **Mới** — bảng ứng viên + tầng 3 |
| `frontend/.../GlossaryManager.jsx` | nối panel, mở form đã điền sẵn, hiện bằng chứng trong form |
| `frontend/.../VoiceProfileManager.jsx` | tầng 2: tìm tín hiệu, tạo hồ sơ từ tín hiệu |
| `frontend/src/api.js`, `App.jsx` | 4 hàm + 4 callback |

## 5. New API / DB / State

| Endpoint | Mã | Ghi chú |
|---|---|---|
| `GET /projects/{id}/term-candidates` | 200 | chỉ đọc, **không gọi AI** |
| `GET /projects/{id}/voice-signals` | 200 | chỉ đọc |
| `POST /projects/{id}/term-suggestions` | **202** | có gọi AI ⇒ job nền (nguyên tắc số 4) |
| `GET /term-suggestion-runs/{id}` | 200 | `suggestions: null` = chưa xong · `[]` = xong mà rỗng |

**DB:** thêm bảng `term_suggestion_run` (project-level, nên không mượn `Job` vì `Job.page_id` là
NOT NULL). Lưu cả `series_name` nguyên văn, `asked_count`, `dropped_count`, `model_name` — để còn
đối chất khi kết quả lạ.

## 6. Tests

```
backend   913 passed, 6 skipped     exit 0     (nền trước E17: 869)
          +44 test: 28 unit (tests/test_e17_ungvien_unit.py) + 16 integration
frontend  44 passed  (bộ consistency: 29 cũ + 15 mới)
```

### 6.1 Backend — 28 unit + 16 integration

Những test đáng giá nhất không phải test "chạy được", mà là test **khoá lời hứa**:

| Test | Khoá điều gì |
|---|---|
| `test_KHONG_ghi_mot_dong_nao_vao_CSDL` | gọi cả 2 endpoint xong ⇒ `glossary_entry` và `character_voice_profile` vẫn **0 hàng** |
| `test_LOAI_dong_nhac_lai_mot_ten_KHONG_co_trong_danh_sach` | model trả về "Naruto Uzumaki" cho chapter Pepper&Carrot ⇒ **loại + đếm** |
| `test_cong_doi_chieu_loai_muc_bia_va_khong_tao_thuat_ngu` | cùng ca đó chạy qua worker thật, và `glossary_entry` vẫn 0 hàng |
| `test_khong_co_ung_vien_thi_KHONG_goi_mo_hinh` | monkeypatch `build_translator` thành hàm **ném lỗi** — gọi là đỏ |
| `test_toan_chu_hoa_KHONG_duoc_tra_ve_moi_tu` | bẫy TOÀN CHỮ HOA |
| `test_hai_luat_cung_bat_mot_cho_thi_KHONG_dem_hai_lan` | chống thổi số lần xuất hiện |
| `test_model_noi_khong_biet_thi_khong_tinh_la_bia` | `?` là câu trả lời trung thực |
| `test_chu_doc_chua_chac_thi_bi_bo_va_DEM_ra` | bỏ vùng `needs_manual` nhưng **nói ra con số** |
| 3 test trạng thái rỗng | "chưa đọc chữ" ≠ "không thấy" ≠ "đều đã có" |

### 6.2 Ba lỗi thật bắt được trong lúc viết test

**1. `OCRStatus.done` không tồn tại.** Enum thật là `pending | ok | needs_manual`. Bộ lọc của tôi
sẽ ném `AttributeError` ngay lượt gọi đầu tiên. Bắt được khi đọc fixture của E13 chứ không phải
khi chạy — nhưng nếu không đọc thì test integration đã bắt.
*Bài học: đừng đoán tên hằng số của enum, mở tệp ra đọc.*

**2. Đếm hai lần.** `ペッパーさん` khớp **cả** luật hậu tố kính ngữ **lẫn** luật katakana, và tôi
cộng theo số lần **khớp luật** thay vì số lần **xuất hiện** ⇒ con số hiện cho người dùng bị thổi
gấp đôi. Đúng loại bẫy mà chế độ chỉ-đếm của P3f đã dính. Sửa bằng khử trùng theo `(vùng, vị trí)`.
*Bài học: con số nào người dùng dùng để ra quyết định thì con số đó phải đếm đúng sự vật, không
phải đếm số lần mã chạm vào sự vật.*

**3. Luật tiếng Anh vứt bằng chứng thật** (§3.3) — lộ ra vì một test integration đỏ.

### 6.3 Hai lỗi của chính test, không phải của mã

Ghi ra để lần sau đọc lại không tưởng là mã từng sai:

- Test khẳng định `"PEPPER" in kho` trong khi khoá tiếng Anh **đã hạ chữ thường** (`pepper`).
- Hàm dựng dữ liệu đặt `region_id` trùng nhau giữa hai lần gọi ⇒ bộ khử trùng coi hai vùng là
  một. Vùng thật là UUID nên không dính. **Fixture trùng id là một cách âm thầm làm test nói dối.**

## 7. Live Verification — ⛔ CHƯA CHẠY ĐƯỢC

Host `cmc-1` vẫn không phản hồi (xem `REPORT_P3h` §6). Nên **chưa** có: chạy trên chapter thật,
đo độ trễ hai endpoint, và **chưa có lượt gọi mô hình thật nào cho tầng 3** — toàn bộ tầng 3 mới
được kiểm bằng mô hình giả trong test.

Khi host sống lại, phải làm đúng ba việc sau trước khi coi E17 là đóng:

1. Chạy `term-candidates` trên **chapter thật** (`test_fixtures/external/`, Pepper&Carrot) rồi
   **đối chiếu bằng mắt**: ứng viên có đúng là danh xưng không, `count` có khớp không.
2. **Đo tỉ lệ chữ hoa thật** của fixture để chốt `NGUONG_CHU_HOA` — hiện là con số **chọn**, chưa
   phải con số **đo**.
3. Gọi tầng 3 **một lượt thật** với `series_name = "Pepper&Carrot"`, ghi lại `asked/kept/dropped`
   và token tiêu thụ.

## 8. Remaining Limits — nói thẳng

1. **Chưa verify trên host, chưa từng gọi mô hình thật** (§7).
2. **`NGUONG_CHU_HOA = 0.70` và `TRAN_UNG_VIEN = 50` là số chọn, không phải số đo.**
3. **Tên chỉ từng đứng đầu câu (tiếng Anh chữ thường) sẽ không tìm ra được** — có test khoá
   (`test_ten_CHI_dung_dau_cau_thi_KHONG_tim_ra_duoc`). Đoán bừa ở đây sẽ kéo theo mọi danh từ
   đầu câu.
4. **`zh` nhiễu cao hơn hẳn** `ja`/`en` — n-gram không có ranh giới từ. Giao diện nói thẳng.
5. **OCR sai thì ứng viên sai.** E17 không sửa OCR, không gộp gần đúng (gộp gần đúng là quyết
   định về nghĩa — việc của người). Vùng `needs_manual` bị bỏ nhưng có đếm và báo ra.
6. **Không biết ai nói câu nào** ⇒ tín hiệu xưng hô là "chapter có tín hiệu này", không phải
   "nhân vật X xưng thế này với Y".
7. **Thứ đã bỏ qua sẽ hiện lại ở lượt sau** — chưa lưu trạng thái "đã bỏ qua" (chỉ lọc theo
   `glossary_entry`). Chờ dùng thật xem có phiền không rồi mới thêm bảng.
8. **Danh sách chặn từ phổ thông còn ngắn** (`_CHAN_EN` ~110 từ, `_CHAN_JA`/`_CHAN_ZH` ~20-30):
   chặn hụt thì sửa được, chặn thừa thì người dùng không bao giờ thấy thứ họ cần — nên cố ý để ngắn.
9. **Chưa đo độ trễ**, nên chưa chứng minh được chạy đồng bộ (`200`) là đúng cho chapter lớn. Có
   chạy trong `run_in_threadpool` để không chặn event loop, nhưng đó là phòng xa, không phải phép đo.
