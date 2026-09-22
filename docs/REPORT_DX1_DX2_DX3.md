# REPORT — ĐX-1 · ĐX-2 · ĐX-3

**Ngày:** 2026-09-22 · **Nguồn đề bài:** `docs/REPORT_ICHIGO_BLACKBOX_BENCHMARK.md` §8, hướng A đã duyệt
**Phạm vi:** ba khoảng cách thao tác G1/G2/G3 đo được từ benchmark — **không** đụng tới chất lượng dịch.

---

## 1. Summary

| ID | Việc | Trạng thái |
|---|---|---|
| **ĐX-1** | Đường "Dịch nhanh": một màn, thả ảnh **hoặc cả gói**, xong tự tải về | **BUILT** — test xanh, **chưa chạy thật một chapter nào** |
| **ĐX-2** | Nhận gói `.zip`/`.cbz` làm đầu vào (PDF **chưa**) | **BUILT** — như trên |
| **ĐX-3** | Chọn engine dịch ngay trên màn upload, hiện rõ cái nào tốn tiền | **BUILT** — như trên |

**Ngoài đề bài, tìm ra và sửa một lỗi có thật chưa từng lộ.** Cột `Page.translate_engine_override`
có chỗ **GHI** từ E19 nhưng pipeline đầy đủ **cố ý không ĐỌC** (`enqueue_translate_after_inpaint`
luôn truyền `engine=None`). Nghĩa là: nếu chỉ làm phần UI như đề bài mô tả, người dùng chọn engine
xong thì lựa chọn đó **rơi vào hư không, không một thông báo lỗi nào**, và mọi bài test kiểu "đã
lưu vào cột chưa" vẫn xanh. Đây đúng kiểu hỏng "hai đầu không gặp nhau".

> **Nhãn trung thực:** cả ba đều là **BUILT**, không phải LIVE. Chưa có worker nào chạy, chưa có
> chapter thật nào đi hết chuỗi qua đường mới. Theo quy ước `FEATURES.md`: *"Không đánh dấu LIVE
> nếu chưa chạy thật một lần."*

---

## 2. Audit Before Build

Năm điều kiểm ra được **trái với giả định ban đầu** — nếu tin giả định thì đã làm sai:

| Giả định | Sự thật đo được |
|---|---|
| `GET /api/v1/projects` chưa có (theo `FEATURES.md` §E1: "→ 405") | **Đã có** từ slice B (`routes.py:458`). Tài liệu lỗi thời |
| `_chapter_doc_nhanh` (E19) tái dùng được cho ĐX-1 | **Không** — nó khoá cứng `intended_use=personal` và `che_do_pipeline=chi_chu`. Dùng lại sẽ **âm thầm khai hộ mục đích sử dụng**, đúng thứ M10 sinh ra để chặn |
| Ghi engine vào cột là đủ | **Không** — pipeline đầy đủ không đọc cột đó (xem §1) |
| Có thư viện đọc PDF | **Không có** — chỉ `Pillow`. `fitz`/`pypdfium2`/`pdf2image`/`pypdf` đều vắng |
| `Alert` nhận `sac="tot"` / `"canh_bao"` | **Không** — chỉ `tin \| ok \| canh \| loi`. Viết sai sẽ ra class CSS không tồn tại, hộp thông báo mất màu mà không ai báo lỗi |

---

## 3. Design Choice

**ĐX-1 — đường SONG SONG, không thay thế.** Màn cũ còn nguyên, chỉ thêm một bộ chuyển hai tab.
Ai cần rà soát/sửa tay/chốt thuật ngữ vẫn đi đường cũ.

**Giữ nguyên M10 và đăng nhập** (chủ dự án chốt). Màn nhanh rút gọn *số bước điều phối* — đặt tên
chapter, tải từng trang, tự bấm xuất — chứ **không** rút gọn phần khai báo trách nhiệm bản quyền.
Ô "Mục đích sử dụng" **không chọn sẵn**, y như màn đầy đủ.

**Xuất bằng ZIP chứ không CBZ.** E40 đo được người dùng tải `.cbz` về **không mở được trên
Windows**. Một đường tên là "nhanh" mà giao ra file không mở được thì không nhanh.

**ĐX-2 — `doc_goi_anh` KHÔNG phải generator, phần sinh nằm ở `_sinh_trang`.** Thân một generator
không chạy dòng nào cho tới `next()` đầu tiên; viết `yield` thẳng vào sẽ khiến mọi phép kiểm trần
nổ **lúc route bắt đầu lặp** chứ không phải lúc gọi — sai chỗ bắt lỗi, và có khi đã ghi vài trang
vào CSDL rồi mới nổ. Có test riêng canh đúng bẫy này (`test_loi_no_ngay_luc_goi…`).

**Sinh lần lượt thay vì trả list.** Gom cả gói vào list giữ tới hàng trăm MB ảnh đã bung trong
tiến trình API — ảnh `api` cố tình mỏng (~1GB) và dự án **đã bị OOM giết worker hai lần** (E41).
Sinh lần lượt thì lúc nào cũng chỉ một trang trong bộ nhớ.

**Thứ tự trang theo khoá tự nhiên.** `p2` trước `p10`. Sắp theo chuỗi thuần là hỏng **im lặng**:
file vẫn xuất ra bình thường, chỉ nội dung lộn trang.

**Chặn bom giải nén bằng số khai trong header, cộng TRƯỚC khi bung byte nào** — nhưng vẫn đọc có
trần vì con số đó do kẻ gửi tự khai.

**ĐX-3 — lưu `google_fast` TƯỜNG MINH, không quy về `NULL`** (khác đường E19). `NULL` nghĩa là
"theo mặc định hệ thống", nên đổi `translate_default_engine` một ngày nào đó sẽ âm thầm biến lựa
chọn *miễn phí* của người dùng thành engine tốn token.

---

## 4. Changed Files

**Backend**
- `app/services/archive.py` — **mới**. Đọc gói ZIP/CBZ + toàn bộ phép chặn gói độc.
- `app/api/v1/routes.py` — thêm `POST /projects/{id}/pages/archive`; `POST /projects/{id}/pages`
  nhận thêm field `engine`.
- `app/workers/tasks.py` — `enqueue_translate_after_inpaint` **đọc** `Page.translate_engine_override`.
- `app/schemas/common.py` — `ArchiveAccepted`, `TrangTrongGoiAccepted`.
- `app/core/config.py` — `archive_max_pages` (200), `archive_max_total_mb` (500).
- `app/models/__init__.py` — sửa bình luận đã sai về cột override.

**Frontend**
- `src/components/chapter/DichNhanh.jsx` — **mới**. Màn ĐX-1.
- `src/api.js` — `taiGoiLen`, `laGoiNen`; `taiTrangLen` nhận `engine`.
- `src/components/ui/Dropzone.jsx` — prop `chapNhanGoi` (mặc định `false`, mọi chỗ gọi cũ không đổi).
- `src/App.jsx` — bộ chuyển hai đường.
- `src/styles.css` — `.chon-duong`, `.nut-duong` (dùng token sẵn có, không chế màu mới).

**Test** — `test_dx2_goi_nen_unit.py`, `test_dx2_dx3_upload_goi_integration.py`,
`test_dx3_engine_pipeline_day_du.py`, `DichNhanh.test.jsx` (đều mới);
`test_quyen_cheo_tai_khoan.py` (sửa, xem §6).

**Tài liệu** — `ARCH.md`, `API.md`, `FEATURES.md`, `TEST_LOG.md`.

---

## 5. New API / DB / State

**API mới:** `POST /api/v1/projects/{project_id}/pages/archive` → 202. Đặc tả đầy đủ ở
`docs/API.md` §3b.

**API đổi:** `POST /api/v1/projects/{project_id}/pages` nhận thêm field `engine` (tuỳ chọn).
Không gửi ⇒ hành vi y như cũ.

**DB: KHÔNG có migration.** Dùng lại đúng cột `Page.translate_engine_override` có sẵn từ
`0015_e19b`. Việc cần làm không phải thêm cột, mà là **nối đường đọc** cho cột đã có.

**Cấu hình mới:** `ARCHIVE_MAX_PAGES` (200), `ARCHIVE_MAX_TOTAL_MB` (500). Trần mỗi trang dùng
chung `MAX_UPLOAD_MB`.

**Tương thích ngược:** trang cũ có `translate_engine_override IS NULL` ⇒ vẫn lùi về mặc định hệ
thống. Có test đối chứng riêng.

---

## 6. Tests

| Bộ | Số bài | Kết quả |
|---|---|---|
| `test_dx2_goi_nen_unit.py` (thuần, không CSDL) | 23 | xanh |
| `test_dx2_dx3_upload_goi_integration.py` | 15 | xanh |
| `test_dx3_engine_pipeline_day_du.py` | 4 | xanh |
| `DichNhanh.test.jsx` | 16 | xanh |
| **Toàn bộ frontend** | **386** (25 file) | **xanh** |
| **Toàn bộ backend** | **1618 passed · 6 skipped · 0 failed** | **xanh** (`PYTEST_EXIT=0`) |

### 6.1. Đối chứng âm — test có thật sự bắt được lỗi không

Test xanh **không chứng minh gì** nếu nó xanh kể cả khi lỗi còn nguyên. Đã gỡ tạm bản vá ở
`enqueue_translate_after_inpaint` rồi chạy lại:

- 2 bài **đỏ đúng chữ ký lỗi**: nhận `None` thay vì engine đã chọn.
- 2 bài còn lại **xanh như kỳ vọng** (chúng kiểm tương thích ngược và sự tồn tại của job dịch,
  không phụ thuộc bản vá).

Khôi phục bản vá ⇒ 4/4 xanh lại.

### 6.2. Bộ test sẵn có tìm ra một thiếu sót của tôi

`test_quyen_cheo_tai_khoan.py` (phép dò quyền tự sinh) **đỏ** với endpoint mới, báo
*"rỗng nghĩa: POST …/pages/archive (A 422 / B 422)"*.

Nó đúng. Phép dò khoá cứng một file PNG cho mọi endpoint multipart, nên đường nhận gói ZIP trả
422 cho **cả hai** tài khoản ⇒ không chứng minh được endpoint có chặn tài khoản khác hay không.
Một đường GHI dữ liệu lọt qua như vậy có thể mang lỗ IDOR lên production mà bộ test vẫn xanh —
đúng kiểu lỗ E33 từng lọt.

Đã sửa phép dò: bảng `_MULTIPART` tra thân request hợp lệ theo **từng** endpoint (gói ZIP thật cho
đường gói). Sau khi sửa: 9/9 xanh, endpoint mới vào nhóm **chứng minh được**.

### 6.3. Toàn bộ backend

**1618 passed · 6 skipped · 0 failed · 0 error**, `PYTEST_EXIT=0`
(`pytest -q -p no:randomly`, Postgres + Redis đều chạy).

**Hai cái bẫy về ĐO ĐẠC gặp ngay trong lượt này**, ghi lại vì cả hai đều suýt cho ra một kết luận
sai mà trông rất giống kết luận đúng:

1. **Mã thoát giả.** Lượt chạy đầu in `exited with code 0` **trong khi có 4 bài đỏ** — mã thoát
   bắt được là của `tail` ở cuối chuỗi ống, không phải của `pytest`. Lượt sau ghi `$?` ngay sau
   `pytest`, **trước** khi qua ống. Ba trong bốn bài đỏ đó (`TestCongNhip`) chỉ vì **thiếu Redis**
   cổng 6380, không phải hồi quy; bài thứ tư là lỗi thật của tôi (§6.2).
2. **Thiếu dòng tổng kết.** Lượt cuối chạy hết 100% và thoát 0, nhưng file log **không có** dòng
   `N passed in …s` (có lẽ mất khi đệm stdout bị cắt). Tin mỗi `exit 0` rồi viết đại một con số
   là bịa. Con số trên đếm từ **chính ký tự tiến trình của lượt chạy đó**:
   1618 dấu `.`, 6 chữ `s`, **0 chữ `F`, 0 chữ `E`** — khớp với `PYTEST_EXIT=0`. Hai đường đo
   độc lập cùng chỉ một kết quả.

### 6.4. Kiểm bản ĐÃ BUILD

Test chạy trên `src`, người dùng chạy bundle. `npx vite build` xanh, và đã kiểm chuỗi thật nằm
trong `dist/assets/index-*.js`: `"Dịch nhanh"`, `"pages/archive"`, `"Tự tải về khi xong"`,
`"hệ thống không chọn hộ"`, `".cbz"` — đều **có mặt**.

---

## 7. Live Verification

**CHƯA CÓ.** Nói thẳng phần này vì nó là phần quan trọng nhất còn thiếu:

- ❌ **Chưa chạy một chapter thật nào** qua đường "Dịch nhanh" — chưa dựng worker + Redis + model
  weight để chạy đầu-cuối.
- ❌ **Chưa bấm tay trên trình duyệt thật.** Test frontend chạy trên jsdom, không phải Chromium.
- ❌ **Chưa thử một file `.cbz` thật** do phần mềm đọc truyện tạo ra — mọi gói trong test đều do
  `zipfile` của Python dựng. Gói thật có thể có cấu trúc thư mục, metadata, hoặc mã hoá tên file
  khác.
- ❌ **Chưa đo bộ nhớ thật** khi nhận gói lớn. Trần đặt theo suy luận từ E41, **chưa đo lại**.
- ✅ Đã kiểm bản build (§6.4) và phép dò quyền chéo tài khoản (§6.2).

---

## 8. Remaining Limits

1. **PDF chưa nhận.** Cần thêm phụ thuộc vào ảnh `api` — quyết định riêng, chưa xin. Gửi PDF nhận
   `422 pdf_chua_ho_tro` nói đúng lý do, không phải lỗi khó hiểu.
2. **Chưa chạy thật** — xem §7. Đây là thứ chặn việc đổi nhãn `BUILT` → `LIVE`.
3. **Màn nhanh hỏi lại máy chủ mỗi 3 giây** trong lúc chờ. Chapter 24 trang ≈ một tiếng (E23) ⇒
   khoảng 1.200 lượt hỏi cho một chapter. Chạy được, nhưng chưa phải cách hay.
4. **Trần gói đặt theo suy luận**, chưa đo: 200 trang, bung 500MB. Con số 500MB **chưa** được đo
   đối chiếu với RAM thật của container.
5. **Đường nhanh không có chỗ rà soát.** Cố ý — ai cần thì bấm sang đường đầy đủ. Nhưng nghĩa là
   trang bị gắn cờ "cần rà soát" (E12) vẫn **lặng lẽ đi thẳng vào file xuất**.
6. **Đường nhanh KHÔNG có bước ghi nhận trách nhiệm trước khi xuất**
   (`POST /export-jobs/{id}/acknowledge`, thuộc họ M10) — **chủ dự án đã chốt chấp nhận như vậy
   (22-09)**. Đường đầy đủ vẫn hiện cảnh báo chất lượng + bản quyền rồi để người dùng tự tick;
   đường nhanh xuất thẳng.

   Ghi lại cho người đọc sau, vì đây là một lựa chọn có đánh đổi chứ không phải bỏ sót:
   - Hệ thống **không bao giờ tự tick hộ**. Tick hộ sẽ biến một lời cam kết của người dùng thành
     một dòng mã — đúng thứ M10 sinh ra để chặn. Không có bước đó thì là **không có**, chứ không
     phải "có nhưng máy làm thay".
   - Cổng M10 còn lại vẫn nguyên ở đường nhanh: **khai mục đích sử dụng, không chọn sẵn**, gắn
     với chapter và không sửa được.
   - Muốn quay lại: thêm một ô tick trước bước xuất trong `DichNhanh.jsx`, gọi `api.xacNhanXuat`.
     Backend không cần đổi gì — `download_export` vốn không xét cờ này.
6. **Mặc định màn chính nay là "Dịch nhanh"** thay vì màn tạo chapter. Người dùng cũ sẽ thấy khác
   ngay lượt đầu — đổi một dòng (`useState('nhanh')` trong `App.jsx`) là quay về như cũ.

---

## 9. Chốt

| Hạng mục | Kết quả |
|---|---|
| Toàn bộ backend | **1618 passed · 6 skipped · 0 failed**, `PYTEST_EXIT=0` |
| Toàn bộ frontend | **386 passed**, 25 file |
| `vite build` | xanh; chuỗi của tính năng mới **có mặt trong `dist/`** |
| Đối chứng âm cho bản vá ĐX-3 | đạt — gỡ vá ⇒ 2 bài đỏ đúng chữ ký lỗi |
| Phép dò quyền chéo tài khoản | 9/9, endpoint mới vào nhóm **chứng minh được** |
| Migration CSDL | **không có** — dùng lại cột `0015_e19b` sẵn có |

**Nhãn cuối: `BUILT`, KHÔNG phải `LIVE`.** Bộ test xanh chứng minh mã làm đúng thứ nó được viết
để làm; nó **không** chứng minh một chapter thật đi hết chuỗi qua đường mới. Chưa có lượt chạy
thật nào (§7). Đổi nhãn sang `LIVE` chỉ sau khi dựng worker + model weight và chạy trọn một
chapter.

**Quyết định của chủ dự án đã ghi vào tài liệu** (22-09): đường nhanh **không có** bước tick xác
nhận trách nhiệm trước khi xuất — xem §8.6.

**Không commit, không deploy** — theo đúng ràng buộc ban đầu. Mọi thay đổi nằm ở cây làm việc.
