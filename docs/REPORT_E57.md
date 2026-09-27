# REPORT E57 — Tự nhận ngôn ngữ gốc (phần LÕI xong, phần NỐI chờ chốt)

**Ngày:** 2026-09-27 · **Nguồn yêu cầu:** chủ dự án — *"thay vì chọn đầu vào là ngôn ngữ gì nó có
thể nhận định được ngôn ngữ, ai muốn dùng tính năng đó"*

> **Trạng thái:** bộ phân loại + 16 bài test **XONG**. Phần nối vào pipeline **CHƯA làm** — có hai
> cách, khác nhau ở thứ người dùng thấy và ở mức rủi ro, nên chờ chủ dự án chốt (§5).

---

## 1. Summary

Nhận dạng ngôn ngữ làm được **offline, không tải model mới, không gọi API, không tốn tiền**. Cơ sở
là một phép đo, không phải phỏng đoán.

---

## 2. Audit Before Build — phép đo quyết định

Bài toán trông như con-gà-quả-trứng: `source_lang` **chọn engine OCR** (`ja` → manga-ocr,
`zh`/`en` → PaddleOCR), nên muốn biết tiếng gì thì phải đọc chữ, mà muốn đọc chữ thì phải chọn
engine trước.

Đo từ điển của `PP-OCRv6_medium_rec` — **chính model pipeline đã nạp sẵn** cho `zh`/`en`
(`~/.paddlex/official_models/PP-OCRv6_medium_rec/inference.yml`, 18.708 ký tự):

| Khối Unicode | Có trong từ điển | Trên tổng |
|---|---|---|
| Hiragana `U+3040–309F` | **86** | 96 |
| Katakana `U+30A0–30FF` | **94** | 96 |
| Hán `U+4E00–9FFF` | 15.565 | 20.992 |
| Latin ASCII | 94 | 95 |
| Hangul | **0** | 11.172 |
| Ký tự Việt có dấu `U+1EA0–1EF9` | **2** | 90 |

Và ở `paddleocr` 3.7.0, nhánh PP-OCRv6 (`_pipelines/ocr.py` ~354): `lang` bằng `ch`, `en` **hay**
`japan` đều trả về **cùng một cặp model**.

⇒ **Engine đang chạy đã đọc được kana.** Nút thắt được mở: nhận dạng ngôn ngữ chỉ còn là đếm ký tự.

### Phát hiện phụ đáng ghi

Vì `ch` và `en` nạp **cùng một model**, hôm nay chọn sai giữa Trung và Anh **không** làm hỏng OCR —
chỉ làm sai `source_lang` truyền cho translator. Chọn sai thành **Nhật** mới hỏng thật, vì manga-ocr
là model khác hẳn. Nghĩa là rủi ro thật của ô chọn tay tập trung vào đúng một cặp: ja ↔ (zh|en).

---

## 3. Design Choice — bộ phân loại

### 3.1. Kana là thứ phân biệt, KHÔNG phải chữ Hán

Trang tiếng Nhật có **rất nhiều** kanji, nên "có chữ Hán" không nói được gì. Thứ tiếng Trung **không
bao giờ** có là hiragana/katakana. ⇒ thứ tự xét bắt buộc: **kana trước, Hán sau**. Đảo lại là gán
**mọi manga** thành tiếng Trung — và hậu quả là dùng PaddleOCR thay manga-ocr: chữ vẫn ra, vẫn dịch,
chỉ kém hơn hẳn và **không có lỗi nào hiện**. Có bài canh riêng cho đúng chỗ này.

### 3.2. Ngưỡng, và vì sao mỗi ngưỡng tồn tại

| Hằng số | Giá trị | Chặn cái gì |
|---|---|---|
| `SO_KY_TU_TOI_THIEU` | 8 | Đoán từ 3 ký tự rồi trình bày như một phép đo |
| `SO_KANA_TOI_THIEU` | 2 | Một kana lẻ là rác OCR trên trang tiếng Trung — không được lật kết luận |
| `TI_LE_HAN_TOI_THIEU` | 20% | Trang tiếng Anh lọt vài chữ Hán không thành tiếng Trung |
| `TI_LE_LATIN_TOI_THIEU` | 60% | — |

Không nhóm nào đủ ngưỡng ⇒ **trả `None`**, để giao diện hỏi lại. Chọn nhóm cao nhất rồi im lặng là
đúng thứ CLAUDE.md §3 cấm.

`ngon_ngu is None` có **hai** lý do khác nhau, và giao diện phải nói khác nhau:
`khong_doc_duoc_chu_nao` (bìa chương — bình thường) vs `qua_it_chu` / `khong_nhom_nao_du_nguong`
(đọc được nhưng không chắc — phải hỏi lại).

### 3.3. Lỗi tôi tự gây và tự sửa: "mọi chữ cái" ≠ "chữ Latin"

Bản đầu đếm chữ cái bằng `unicodedata.category(c).startswith("L")` — mà `L*` là **mọi** loại chữ
cái, nên Cyrillic và Hy Lạp cũng vào ô `latin`. Một trang **tiếng Nga** sẽ ra kết luận `en`, **tự
tin và sai**.

Phát hiện được vì một bài test của tôi đỏ với lý do tôi không đoán trước (tôi tưởng `фффф` không
được đếm). Vá: tách ô `chu_cai_khac` cho chữ cái không-Latin không-CJK; chúng vẫn vào
`tong_co_nghia` để **làm loãng** tỉ lệ và đẩy kết luận về "không chắc" — đúng thứ ta muốn cho một
ngôn ngữ không hỗ trợ. Có bài canh: `test_tieng_NGA_KHONG_bi_ket_luan_thanh_tieng_Anh`.

### 3.4. Giới hạn PHẢI nói ra: tiếng Hàn

Từ điển có **0/11.172** ký tự Hangul ⇒ trang tiếng Hàn không bao giờ đọc ra Hangul, nó ra chuỗi rác.
Hệ thống chỉ hỗ trợ ja/zh/en nên đây không phải lỗi mới, nhưng người dùng thả trang tiếng Hàn vào
**sẽ nhận một kết luận trông tự tin**. Đã ghim thành bài test (`test_tieng_han_bi_nhan_SAI…`) chứ
không chỉ ghi trong tài liệu: giấu giới hạn trong tài liệu thì không ai đọc.

Cùng lý do, từ điển chỉ có 2/90 ký tự Việt có dấu — **đừng bao giờ** dùng hàm này để nhận ra tiếng
Việt.

---

## 4. Changed Files (phần đã làm)

| Tệp | Sửa gì |
|---|---|
| `app/services/nhan_dang_ngon_ngu.py` | MỚI — `dem_ky_tu`, `phan_loai`, `BangChung`, `KetQuaNhanDang` |
| `tests/test_e57_phan_loai_ngon_ngu.py` | MỚI — 16 bài, hàm thuần nên không cần model/CSDL |

Chưa có migration, chưa sửa pipeline, chưa sửa giao diện.

---

## 5. Phần NỐI — hai cách, chờ chốt

Trở ngại: `Project.source_lang` là `nullable=False` và được đọc ở ~10 chỗ trong `workers/tasks.py`.
Lúc người dùng thả tệp thì **chưa biết** ngôn ngữ, nên phải quyết cất "chưa biết" ở đâu.

### Cách A — đường nhận dạng RIÊNG, chạy TRƯỚC khi tạo chapter

`POST /api/v1/nhan-dang-ngon-ngu` (ảnh) → `202` + `job_id`; task chạy CTD detect (offline, không
phụ thuộc ngôn ngữ) + PaddleOCR trên ~6 vùng → `phan_loai()`. Giao diện **hiện kết quả kèm bằng
chứng** ("đọc được 42 ký tự, 11 kana ⇒ tiếng Nhật"), người dùng xác nhận hoặc sửa, rồi mới tạo
chapter với `source_lang` đã chốt.

* Không sửa schema, không sửa pipeline ⇒ **không đụng gì vào 1.867 bài test đang xanh**.
* Người dùng **thấy** máy nhận ra gì trước khi tốn hạn mức — và §3.2 nói rõ có trường hợp không kết
  luận được, lúc đó bắt buộc phải hỏi lại. Cách này có sẵn chỗ để hỏi.
* Tốn thêm: một lượt OCR mẫu trên ~6 vùng của **một** trang.
* Phải thêm trần riêng cho đường này (tiền tố sổ cái mới, đúng khuôn `dang-ky:` của E52) — không có
  trần thì nó thành dịch vụ OCR miễn phí không giới hạn.

### Cách B — `source_lang` thành nullable, nhận dạng trong bước OCR

Thêm cột `ngon_ngu_tu_nhan` + `ngon_ngu_bang_chung`, cho `source_lang` nhận `NULL` ("chưa nhận
được" — đúng chữ của CLAUDE.md §3: *chưa chạy → NULL*), bước OCR tự nhận rồi ghi vào.

* Nhận dạng **miễn phí hoàn toàn**: dùng luôn lượt OCR thật, không có lượt mẫu.
* Nhưng phải sửa ~10 chỗ `project.source_lang.value` + `ProjectRead.source_lang` (đổi hợp đồng API,
  CLAUDE.md §6 đòi ghi lý do), và `GlossaryEntry` có ràng buộc `UNIQUE(project_id, source_lang,
  source_term_key)` — `NULL` trong UNIQUE của Postgres **không** trùng nhau, nên phải rà cẩn thận.
* Người dùng **không** thấy trước; biết mình bị nhận sai chỉ khi đọc bản dịch sai. Mà lúc đó hạn
  mức đã trừ và tệp đã sinh.

### Tôi khuyên cách A

Không phải vì dễ hơn, mà vì §3.2 buộc phải có **đường hỏi lại** khi không kết luận được. Cách B
không có chỗ để hỏi: nó phải tự chọn một trong ba hoặc để chapter kẹt. Và "sai mà trông tự tin" là
đúng loại lỗi tệ nhất của tính năng này.

---

## 6. Remaining Limits

* **Chưa chạy trên ảnh thật lần nào.** Mọi bài test hiện tại cho `phan_loai()` chuỗi dựng sẵn —
  chúng canh đúng luật phân loại, **không** chứng minh PaddleOCR đọc ra kana trên một trang manga
  thật. Phép đo từ điển ở §2 nói rằng nó *có thể*; chỉ một trang thật mới nói nó *có*.
* Ngưỡng ở §3.2 là **số đặt ra**, chưa hiệu chỉnh trên tập ảnh thật.
* Tiếng Hàn và tiếng Nga: xem §3.3, §3.4.
