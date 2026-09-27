# REPORT E57 — Tự nhận ngôn ngữ gốc

**Ngày:** 2026-09-27 · **Nguồn yêu cầu:** chủ dự án — *"thay vì chọn đầu vào là ngôn ngữ gì nó có
thể nhận định được ngôn ngữ, ai muốn dùng tính năng đó"*

> **Trạng thái:** XONG theo **cách A** (chủ dự án chốt 27-09). Đã chạy trên ảnh thật với model thật.

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

## 4. Đã chạy trên ẢNH THẬT với MODEL THẬT

Đây là chỗ bản nháp của báo cáo này tự ghi là "chưa làm", nên làm ngay. Dựng ba ảnh bằng Pillow +
phông `NotoSansCJK` rồi cho `nhan_dang_tu_anh()` chạy với PaddleOCR thật:

| Ảnh | Kết luận | Bằng chứng đo được |
|---|---|---|
| `おはようございます` / `俺の名前は田中だ` | **`ja`** | 12 kana, 5 Hán |
| `你今天吃饭了吗` / `我们一起去学校吧` | **`zh`** | 15 Hán, **0 kana** |
| `WHAT ARE YOU DOING` / `I can't believe it` | **`en`** | 29 Latin |

⇒ phép đo từ điển ở §2 **giữ đúng khi chạy thật**: PaddleOCR đọc ra kana, và luật phân loại kết luận
đúng cả ba.

**Vẫn còn giới hạn thật:** đây là **chữ sạch dựng sẵn**, không phải trang manga thật (phông cách
điệu, chữ dọc, nền screentone). Cái được chứng minh là *luật phân loại* và *khả năng đọc kana*; độ
bền trên trang thật thì chưa.

---

## 5. Cách nối — chọn CÁCH A

Chủ dự án chốt cách A. Lý do quyết định không phải "dễ hơn" mà là: §3.2 buộc phải có **đường hỏi
lại** khi không kết luận được. Cách B (cho `source_lang` nhận `NULL`, nhận dạng trong bước OCR)
không có chỗ nào để hỏi — nó phải tự chọn một trong ba hoặc để chapter kẹt, và "sai mà trông tự tin"
là đúng loại lỗi tệ nhất của tính năng này.

### 5.1. Bảng riêng, không dùng `job`

`job.page_id` là `NOT NULL` có khoá ngoại tới `page`, mà lượt đọc thử xảy ra **trước khi** có chapter
nào — chính vì chưa biết `source_lang` để tạo chapter. Nới ràng buộc đó chỉ để tiết kiệm một bảng là
làm yếu thứ đang bảo vệ cả pipeline.

Cũng không tạo `Project` tạm: tạo `Project` thì phải điền `source_lang`, đúng thứ chưa biết. Điền bừa
rồi sửa sau là ghi một giá trị **sai** vào CSDL và hy vọng không ai đọc nó trong khoảng giữa.

### 5.2. Trần RIÊNG, và vì sao KHÔNG trừ hạn mức trang

Đường này trả về **chữ đã đọc được** (qua `bang_chung`) nên nó *là* một dịch vụ OCR: không có trần
thì thành OCR miễn phí không giới hạn — đúng thứ E49 được dựng để chặn.

Nhưng trừ vào hạn mức **trang** cũng sai, và sai theo cách tự phá tính năng: khách có 6 lượt sẽ mất 1
lượt chỉ vì bấm "Tự nhận", nên tính năng **càng dùng càng đắt**; người ta sẽ tránh nó rồi quay lại
chọn tay sai — tức nó tự vô hiệu hoá đúng lúc cần nhất.

⇒ bộ đếm riêng, tiền tố `nhan-ngon-ngu:` trên cùng sổ cái, đúng khuôn `dang-ky:` của E52 (không thêm
giá trị enum mới vào một CSDL đang chạy). Ba tiền tố không bao giờ trùng: băm là 32 ký tự hex trần.

Trần đặt **20** — cao hơn hạn mức trang (khách 6) có chủ đích: nếu bộ đếm phụ trợ hết trước lượt dịch
thì người dùng bị ép quay lại chọn tay. Là **số đặt ra**, chưa hiệu chỉnh trên hành vi thật.

### 5.3. Ảnh bị xoá NGAY sau khi đọc, kể cả khi lỗi

Ảnh này là rác tạm: không ai tải về, không phải hiện vật của ai. Giữ lại là giữ ảnh có bản quyền
không vì mục đích gì. Xoá trong `finally` ⇒ lượt đọc hỏng cũng không để lại tệp. Tiền tố kho riêng
(`nhan-dang/`) để không lẫn vào cơ chế dọn theo hạn của E50, thứ chỉ biết `projects/`, `exports/`,
`previews/`.

### 5.4. "Không kết luận" ghi `done`, KHÔNG ghi `failed`

`done` + `ngon_ngu = NULL` = **đã đọc xong, không đủ căn cứ** (ảnh không chữ, quá ít chữ, hệ chữ không
hỗ trợ). `failed` = **không đọc được** (engine hỏng). Trộn hai cái là làm người dùng không phân biệt
được *"ảnh của tôi không có chữ"* với *"hệ thống đang lỗi"*.

### 5.5. Giao diện: HIỆN SỐ ĐO, và không bao giờ chọn bừa

Ô chọn có thêm `Tự nhận`. Giá trị `tu-nhan` **cố ý không phải** một `source_lang` hợp lệ, và nút "Dịch
trang" **bị khoá** khi ô còn ở đó: gửi nó lên đường dịch là nhận 422, tức người dùng đọc một lỗi kỹ
thuật cho một lựa chọn mà chính giao diện mời họ chọn.

Đoán xong thì hiện *"Đọc được 16 ký tự (11 chữ kana của tiếng Nhật). Ô chọn ở trên đã đổi theo. **Sai
thì bạn sửa lại**"*. Một kết luận không kèm số đo thì người dùng không có cách nào biết nên tin bao
nhiêu.

Không đoán được ⇒ **hỏi lại**, ô chọn ở nguyên `tu-nhan`, nút Dịch vẫn khoá. Không âm thầm chọn `ja`.

Chỉ đọc thử **trang đầu** (một chapter cùng một ngôn ngữ), và **phải bấm** — tự chạy khi người dùng
thả tệp là tự tiêu lượt của họ cho một việc họ chưa yêu cầu.

---

## 6. Changed Files

| Tệp | Sửa gì |
|---|---|
| `app/services/nhan_dang_ngon_ngu.py` | MỚI — `dem_ky_tu`, `phan_loai`, `nhan_dang_tu_anh` |
| `app/services/han_muc_nhan_dang.py` | MỚI — bộ đếm riêng, tiền tố `nhan-ngon-ngu:` |
| `app/services/ocr/engines.py` | `PaddleOCREngine.doc_toan_anh()` — đọc cả ảnh, không cần bbox |
| `app/models/__init__.py` + `0023_e57` | Bảng `yeu_cau_nhan_dang_ngon_ngu` |
| `app/workers/tasks.py` | `run_nhan_dang_ngon_ngu_job` |
| `app/services/dispatch.py` | `dispatch_nhan_dang_ngon_ngu` |
| `app/api/v1/routes.py` | `POST`/`GET /nhan-dang-ngon-ngu` |
| `app/core/cong_han_muc.py` | `loi_vuot_han_muc(tran=…)` — xem §7 |
| `app/core/config.py` | `so_lan_nhan_dang_ngon_ngu_mot_ngay`, `gio_giu_anh_nhan_dang` |
| `frontend/src/api.js` · `TrangChu.jsx` · `styles.css` | Lựa chọn "Tự nhận" + hiện bằng chứng |
| `tests/conftest.py` | Bảng mới vào `TABLES`; chặn `dispatch_nhan_dang_ngon_ngu` |

---

## 7. Hai lỗi bài test bắt được — cả hai sẽ lên production nếu thiếu bài đó

**1. `NameError: loi_vuot_han_muc`.** Tôi dùng hàm này mà quên import. **Chỉ hai bài hạn mức chạm tới
dòng đó** — mọi bài khác đi đường thành công. Không có chúng thì lỗi này nổ đúng lúc người dùng đầu
tiên hết lượt.

**2. 429 in ra một con số ĐÚNG ĐỊNH DẠNG nhưng SAI NỘI DUNG.** `loi_vuot_han_muc` lấy `chot.tran`, mà
`Chot.tran` luôn là trần hạn mức **trang**. Nên lượt vượt trần nhận dạng báo *"trần 10"* trong khi
trần thật là 20. Lộ ra vì bài test khẳng định vào `ct["tran"] == 2` chứ không chỉ `status_code == 429`.
Vá bằng tham số `tran=` tường minh, kèm cảnh báo trong docstring.

---

## 8. Tests

**Backend 32 bài** (16 `test_e57_phan_loai_ngon_ngu.py` + 16 `test_e57_duong_nhan_dang.py`),
**frontend 8 bài**.

| Bài canh | Canh cái gì |
|---|---|
| `test_manga_co_kanji_van_la_TIENG_NHAT…` | Thứ tự xét kana↔Hán. Đảo lại là gán MỌI manga thành tiếng Trung |
| `test_KHONG_tru_han_muc_TRANG` | Cả thiết kế đứng trên chỗ này (§5.2) |
| `test_nguoi_dang_nhap_KHONG_doc_duoc_luot_cua_khach` | Nhánh GIỮA — thiếu nó là rò rỉ hàng loạt |
| `test_khong_ket_luan_ghi_DONE_khong_ghi_FAILED` | §5.4 |
| `test_task_chay_LAI_thi_bo_qua…` | Celery giao lại việc ⇒ lượt hai đọc ảnh ĐÃ XOÁ |
| `test_engine_hong_thi_ghi_FAILED_va_van_xoa_anh` | Lỗi hạ tầng không được thành "không kết luận" |
| `test_tieng_NGA_KHONG_bi_ket_luan_thanh_tieng_Anh` | Lỗi tôi tự gây (§3.3) |
| `KHONG_gui_duoc_khi_o_chon_con_o_tu_nhan` | Giao diện: khẳng định **không có lượt gửi trang nào** |
| `khong_ket_luan_thi_HOI_LAI_chu_khong_chon_bua` | Lý do cả cách A tồn tại |

### Đối chứng âm đã chạy — 5 lượt, mỗi lượt đỏ đúng bài

| Phá gì | Bài đỏ |
|---|---|
| Bỏ nhánh GIỮA của phép kiểm chủ sở hữu | `test_nguoi_dang_nhap_KHONG_doc_duoc…` |
| Dùng chung bộ đếm với hạn mức trang | `test_KHONG_tru_han_muc_TRANG` |
| Bỏ chốt chạy-lại của task | `test_task_chay_LAI…` (nổ `UnsafeObjectPath: Path hiện vật rỗng` — đúng hậu quả đã dự đoán) |
| Bỏ khoá nút Dịch khi ô còn `tu-nhan` | `KHONG_gui_duoc_khi_o_chon_con_o_tu_nhan` |
| Không kết luận thì chọn bừa `ja` | `khong_ket_luan_thi_HOI_LAI_chu_khong_chon_bua` |

---

## 9. Năm bài CANH có sẵn đã đỏ — và tôi làm một bài MẠNH HƠN thay vì miễn trừ

Thêm hai endpoint mở cho khách làm năm bài canh cấu trúc đỏ. Đó là **đúng việc chúng sinh ra để
làm**, nên phải cập nhật từng bài mà **không làm yếu** phép canh:

| Bài canh | Cách cập nhật |
|---|---|
| `test_CHI_nhung_duong_nay_mo_cho_khach` | Thêm 2 đường vào danh sách, **kèm lý do mở** ngay tại chỗ |
| `test_celery_da_dang_ky_dung_task_detect_cua_m2` | Khai task mới, kèm ghi rõ nó KHÔNG gọi mô hình ngoài và KHÔNG chạy theo lịch |
| `test_moi_endpoint_v1_deu_doi_dang_nhap` | Thêm vào `MIEN_TRU_DANG_NHAP` kèm lý do + trỏ tới bài chứng minh cách ly |
| `test_moi_endpoint_deu_doi_dang_nhap` | `MO_CHO_KHACH[GET] = 404` — **không bỏ qua**, vì thứ ta sợ là `200` |
| `test_khong_endpoint_nao_lo_du_lieu_sang_tai_khoan_khac` | Xem dưới |

### Bài cuối: cấp DỮ LIỆU THẬT thay vì miễn trừ

`GET /nhan-dang-ngon-ngu/{yeu_cau_id}` ban đầu rơi vào nhóm **"không dựng được đường dẫn"** — phép
quét không có id nào để thử, nên nó **không kiểm endpoint đó chút nào**. Im lặng bỏ trống đúng đường
trả về *chữ đã đọc từ ảnh của người khác*.

Cách dễ là ghi nó vào `MIEN_TRU`. Cách đúng là **dựng một bản ghi thật của A** trong `_dung_du_lieu`
và trả `yeu_cau_id`. Làm vậy thì phép quét tự sinh nay **thật sự** thử "B gọi vào lượt của A" và đòi
non-2xx. Phép canh mạnh hơn trước, không phải yếu đi.

Chỉ `POST` được miễn trừ, và vì một lý do khác hẳn: nó **không nhận id nào** — nó tạo một bản ghi mới
thuộc chính người gọi, nên "B nhận 202" là **đúng**. Mô hình *"B được 2xx = lọt"* không áp được cho
đường tạo mới. Ghi lý do đó ngay tại mục miễn trừ.

---

## 10. Live Verification — production, 27-09

Dấu hiệu bản mới đã lên: `POST /api/v1/nhan-dang-ngon-ngu` trả **422** (thiếu tệp) thay vì **404**
(bản cũ không có route). `con_lai_hom_nay: 19` ở lượt đầu chứng minh migration đã chạy và bộ đếm riêng
hoạt động.

### Qua API, ảnh tiếng Nhật THẬT

```
POST /nhan-dang-ngon-ngu  (ảnh おはようございます / 俺の名前は田中だ)
→ 202 {"trang_thai":"queued","con_lai_hom_nay":19}
GET  /nhan-dang-ngon-ngu/{id}   (~30s sau — lần đầu worker phải nạp model)
→ {"trang_thai":"done","ngon_ngu":"ja","ly_do":"co_12_kana",
   "bang_chung":{"kana":12,"han":5,"latin":0,"tong_co_nghia":17,"so_vung_doc_duoc":2}}
```

| Chốt | Đo được trên production |
|---|---|
| Khách **khác** đọc lượt đó | **404** — cách ly chạy đúng với cookie thật |
| Ảnh **trắng** (không chữ) | `done` + `ngon_ngu: null` + `ly_do: khong_doc_duoc_chu_nao`, `loi: null` — **không** phải `failed` |

### Bấm tay trên Chrome thật

| Bước | Kết quả |
|---|---|
| Chọn "Tự nhận" | Hiện nút "Đọc thử trang đầu" + câu "Không tính vào lượt dịch" |
| Nút "Dịch trang" lúc đó | **Bị khoá**, lý do: *"Bấm \"Đọc thử trang đầu\", hoặc chọn tay một ngôn ngữ"* |
| Bấm đọc thử (ảnh Nhật) | *"Máy đoán: Tiếng Nhật — Đọc được 17 ký tự (12 chữ kana của tiếng Nhật). Ô chọn ở trên đã đổi theo. **Sai thì bạn sửa lại**…"* |
| Sau đó | Ô chọn = `ja`, nút "Dịch trang" **mở ra** |
| Ảnh trắng | *"Máy không đoán được — Trang này máy không đọc ra chữ nào… Bạn chọn tay ở ô trên giúp nhé"*; ô chọn **ở nguyên** `tu-nhan`, nút Dịch **vẫn khoá** |
| Console | **0 thông báo** |

Nhánh cuối là thứ đáng nhất: máy **không** âm thầm chọn một ngôn ngữ khi không chắc, và giao diện
không để người dùng đi tiếp bằng một giá trị vô nghĩa.

---

## 11. Remaining Limits

* ~~Chưa bấm tay trên production.~~ **ĐÃ kiểm** — §10.
* Chỉ đọc thử **trang đầu**. Một chapter trộn nhiều ngôn ngữ sẽ nhận theo trang đầu — chấp nhận
  được, nhưng là một giả định chưa nói với người dùng.
* Ngưỡng ở §3.2 và trần 20 ở §5.2 là **số đặt ra**, chưa hiệu chỉnh trên dữ liệu thật.
* Chưa chạy trên **trang manga thật** (§4) — phông cách điệu, chữ dọc, screentone đều chưa thử.
* Tiếng Hàn và tiếng Nga: §3.3, §3.4.
* Chưa có lượt dọn định kỳ cho ảnh tạm còn sót (khi `storage.delete` thất bại). `gio_giu_anh_nhan_dang`
  đã có trong cấu hình nhưng **chưa ai đọc nó** — ghi ra để không ai tưởng đã có phép dọn.
