# REPORT F1 — Một dấu chấm kiểu Nhật không còn giết cả trang

*2026-09-04 · sửa sau sự cố đo được trên bản chạy thật*

## Summary

Chapter thật (`test 2`, 1 trang, nguồn `ja`) chạy hết pipeline rồi **chết ở bước cuối**:

```
typeset job f63573c0-60f4-4fcf-9616-2465762a4997 thất bại
MissingGlyph: font thiếu glyph cho '．' — sẽ render ra ô vuông
```

Một ký tự `．` (U+FF0E — dấu chấm **toàn rộng** của tiếng Nhật, không phải `.` U+002E) trong bản
dịch làm hỏng nguyên trang. Người dùng ngồi đợi **10 phút** một việc đã chết sau **0,034 giây**.

Sự cố lộ ra **ba khuyết tật độc lập**, sửa cả ba:

| # | Khuyết tật | Bản sửa |
|---|---|---|
| 1 | Engine dịch trả chữ Việt nhưng giữ dấu câu kiểu Nhật; không font nào có glyph | Gấp dấu câu toàn rộng/CJK về dạng nửa rộng **trước khi đo và vẽ** |
| 2 | Một vùng font không vẽ được thì **giết cả trang** — 7 vùng đạt cũng mất trắng | Vùng đó nhận `fit_status = font_missing_glyph`, các vùng khác vẫn đi tiếp |
| 3 | Lý do hỏng nằm sau nút "Vì sao?" phải bấm mới biết; màn hình quay vô hạn | Lỗi tự hiện ở màn tiến độ; trang có việc hỏng thì **thôi quay** |

## Audit Before Build

Đo trước khi sửa, không đoán:

- **Log worker thật** (`translation-api`, 04/09 12:27–12:29): detect 49,5s ✓ · OCR 39,4s ✓ ·
  inpaint 13,1s ✓ · translate 9,6s ✓ · **typeset 0,034s ✗**.
- **Đo glyph trên cả 7 font trong whitelist** bằng đúng phép kiểm sentinel của `fonts.py`:

  | | Ký tự |
  |---|---|
  | **Thiếu ở cả 7 font** | `．，！？：；（）「」『』。、・〜～－ー‥` |
  | **Có đủ ở cả 7 font** | `. , ! ? : ; ( ) " ' - ~ · — – … “ ” ‘ ’` |

  Nghĩa là mọi ký tự **đích** của bảng gấp đều an toàn — và bảng này không phải phỏng đoán.
- **Đọc lại vòng lặp `_run_typeset`**: `fit()` gọi trong vòng `for`, không ai bắt `MissingGlyph`
  → một vùng ném là cả job chết.
- **Đọc lại `ChapterProgress`**: `con_chay` chỉ nhìn `page.status`; `translated` không thuộc nhóm
  "đã xong" nên vòng hỏi lại 4 giây/lần chạy mãi, kể cả khi job đã `failed`.

## Design Choice

### Vì sao gấp dấu câu chứ không đổi font

Thêm font có glyph CJK thì bản dịch tiếng Việt lại hiện dấu câu Nhật — sai về mặt tiếng Việt, và
kéo theo một file font mới vài chục MB. `．` và `.` là cặp tương đương **tương thích** của Unicode,
chỉ khác bề rộng ô chữ — thứ chỉ có nghĩa khi xếp chữ dọc kiểu Nhật.

Bảng viết **tường minh** thay vì gọi `unicodedata.normalize("NFKC", …)`: NFKC còn đổi `㎏`→`kg`,
`①`→`1`, chữ ghép… rộng hơn hẳn thứ cần và khó test cho hết.

### Ranh giới: xếp chữ vs. dịch hộ

`ー` (U+30FC, dấu kéo dài âm của kana) **cố ý không** nằm trong bảng gấp. Nó thuộc về *từ* tiếng
Nhật chứ không phải dấu câu; đổi nó thành `—` là dịch hộ người dùng. Kana/kanji còn sót cũng vậy —
vùng đó phải kêu lên, và khuyết tật #2 lo phần kêu cho tử tế.

### Vì sao `font_missing_glyph` là trạng thái RIÊNG, không dùng lại `pending`

`pending` = "không có chữ để chèn" (bản dịch rỗng). Vùng này **có chữ**, dịch xong hẳn hoi, nhưng
chèn không được. Gộp lại thì một bong bóng **mất chữ** trông y hệt một bong bóng vốn dĩ trống — và
người dùng mang file đi mà không biết mình mất gì. Trạng thái riêng thì **đếm được, hiện được,
chặn được ở cổng xuất**.

Giá phải trả: một giá trị enum mới trên Postgres (migration `0013_f1`) và 7 chỗ ở giao diện phải
biết tới nó. Chấp nhận, vì cái mất khi gộp là **im lặng làm mất chữ**.

### Cái gì KHÔNG đổi

- **Cả trang không vùng nào vẽ được** ⇒ job vẫn hỏng như cũ, trang giữ `translated`, không công
  bố preview. Công bố một trang trắng rồi gọi nó là "đã căn chữ" còn tệ hơn báo lỗi.
- **Đường sửa tay một vùng (`re-fit`)** vẫn ném lỗi như cũ. Người dùng đang yêu cầu đúng vùng đó;
  nuốt lỗi rồi trả "xong" là nói dối thẳng vào mặt người hỏi.
- **Bản dịch trong CSDL** không bị đụng tới. Chỉ chuỗi đem đo/vẽ (`wrapped_text`) được gấp.

## Changed Files

**Backend**

| File | Đổi gì |
|---|---|
| `app/services/typeset/fonts.py` | `_DAU_CAU_TOAN_RONG` + `normalize_for_layout()` gấp dấu câu |
| `app/services/typeset/fitter.py` | Hằng `FONT_MISSING_GLYPH` (fit() vẫn ném lỗi, không tự trả) |
| `app/workers/tasks.py` | `_run_typeset`: bắt `MissingGlyph` **theo từng vùng**, đếm, log cảnh báo; toàn bộ vùng hỏng ⇒ vẫn ném |
| `app/models/enums.py` | `FitStatus.font_missing_glyph` |
| `app/models/__init__.py` | `ExportComplianceLog.font_missing_count` |
| `alembic/versions/0013_f1_font_missing_glyph.py` | `ALTER TYPE` trong `autocommit_block` + cột đếm |
| `app/services/compliance/gate.py` | Đếm vùng bỏ trống, ghi vào bằng chứng xác nhận |
| `app/services/quality/reasons.py`, `quality/assessor.py` | Mã lý do `layout_font_missing_glyph` |
| `app/api/v1/routes.py` | `GET /projects/{id}/failed-jobs`; `font_missing_count` ở export-preview + warnings + acknowledge |
| `app/schemas/common.py` | `font_missing_count` ở 3 schema |

**Frontend**

| File | Đổi gì |
|---|---|
| `src/lib/status-presentation.js` | `CANH_CHU.font_missing_glyph` |
| `src/components/BboxOverlay.jsx`, `src/styles.css` | Vùng bỏ trống vẽ **gạch chéo đỏ** |
| `src/components/chapter/ChapterProgress.jsx` | Hỏi việc hỏng cả chapter, hiện lỗi ngay, thôi quay khi đã hỏng |
| `src/components/chapter/ChapterSummary.jsx`, `ExportWarningModal.jsx` | Đếm riêng bong bóng trống |
| `src/api.js` | `layViecHongCuaChapter()` |

## New API / DB / State

- **Enum**: `fit_status` thêm `font_missing_glyph`.
- **Cột**: `export_compliance_log.font_missing_count` (int, mặc định ở tầng ứng dụng).
- **Endpoint**: `GET /api/v1/projects/{project_id}/failed-jobs` → `list[JobRead]`, job hỏng **mới
  nhất của mỗi trang**.
- **Field mới** (đều mặc định `0`, không phá máy khách cũ): `font_missing_count` ở `ExportPreview`,
  `ExportWarningsRead`, `AcknowledgeRead`.
- **Mã lý do E12**: `layout_font_missing_glyph` (thứ 19).

## Tests

| Bộ | Nội dung |
|---|---|
| `backend/tests/test_typeset_dau_cau_toan_rong.py` (mới) | 32 test: từng ký tự trong bảng gấp · nguyên câu như engine trả về · **không** đụng kana/kanji/`ー` · **không** đụng katakana nửa rộng (U+FF61+) · vẫn đưa về NFC · tái hiện đúng chuỗi đã gây sự cố · chữ Nhật thật **vẫn** phải ném lỗi |
| `frontend/src/components/chapter/loi-hien-ngay.test.jsx` (mới) | 6 test: lỗi hiện không cần bấm · trang hỏng thôi quay · không có lỗi thì giữ nguyên hành vi cũ · gọi API hỏng vẫn không trắng trang · đếm riêng bong bóng trống |
| `frontend/src/lib/status-presentation.test.js` | Danh sách enum `canh_chu` thêm giá trị mới — tấm lưới chặn "backend thêm trạng thái mà giao diện không biết" |

Một test đáng nói: bản đầu của `test_truoc_khi_gap_font_that_su_thieu_glyph` gọi
`assert_can_render` để chứng minh font thiếu glyph — và **đỏ**, vì chính hàm đó nay đã gấp dấu câu
trước khi kiểm. Đã đổi sang đọc thẳng bảng `cmap` bằng `fontTools`: hỏi font, không hỏi cái hàm
mình vừa sửa.

## Live Verification

**Chạy thật trên bản chạy 2026-09-04, không phải máy phát triển.** `translation-api` bản 42
(migration `0013_f1` chạy lúc khởi động — `deploy-start.sh` cho container **thoát hẳn** nếu
migration hỏng, container `online` nên nó đã chạy được), `translation-web` bản 21.

Chapter kiểm chứng: `F1 — kiểm chứng font thiếu glyph`, 1 trang thật (Pepper&Carrot E01P01),
đi hết pipeline thật trên máy chủ (detect 49,3s → OCR → xoá chữ → dịch → căn chữ), rồi **cố ý**
đặt hai bản dịch để chạm đúng hai nhánh của F1.

### Nhánh 1 — dấu câu toàn rộng (đúng thứ đã gây sự cố)

Đặt bản dịch vùng 1 = `Cậu ổn chứ？　Tớ về đây．` (dấu `？`, khoảng trắng `　`, dấu `．` — toàn rộng).

```
GET /pages/{id}/typeset
  fit_ok   cỡ=23.0   chữ='Cậu ổn chứ?\nTớ về đây.'
```

Dấu câu đã gấp về nửa rộng, chữ căn được ở cỡ 23. **Trước F1 chính chuỗi này giết cả trang.**

### Nhánh 2 — chữ Nhật thật, một vùng hỏng KHÔNG giết cả trang

Đặt bản dịch vùng 2 = `坂本さん` (kanji + kana — font không thể vẽ, và cố ý không gấp).

Log worker của lượt căn lại cả trang:

```
typeset job 2b749c5c: 1/2 vùng KHÔNG chèn được chữ vì font thiếu glyph — '坂本さん'
typeset job 2b749c5c: 2 vùng (vừa 1, tràn 0, chưa có chữ 0, thiếu glyph 1) … 0,6s
Task typeset.run_typeset_job succeeded: {'status': 'done', 'fit_ok': 1, 'font_missing_glyph': 1}
```

Job **`done`**, trang vẫn `typeset_done`, vùng vẽ được vẫn có chữ. Vùng hỏng:

```
  font_missing_glyph   cỡ=None   chữ=None
```

Không ghi chữ mà thực tế không vẽ được — đúng thiết kế.

### Vùng hỏng có kêu lên ở mọi chỗ người dùng nhìn vào không

| Đường | Kết quả thật |
|---|---|
| `GET /projects/{id}/export-warnings` | `font_missing_count = 1`, `overflow = 0` — **đếm riêng**, không lẫn |
| `GET /projects/{id}/export-preview` | `{…, "overflow_warning_count":0, "font_missing_count":1}` |
| `GET /pages/{id}/quality` | `layout_font_missing_glyph → "Chưa chèn được chữ: font không có ký tự trong bản dịch."` |
| Log chấm chất lượng | `2 vùng, 1 cần rà soát` (trước khi sửa: `0 cần rà soát`) |
| `GET /projects/{id}/failed-jobs` *(endpoint mới)* | trả job hỏng kèm lý do đọc được |

### Đường sửa tay MỘT vùng vẫn ném lỗi — đúng như đã thiết kế

`PATCH /regions/{id}` với `坂本さん` ⇒ refit job `failed` sau **0,011 giây**, lý do ghi nguyên văn
vào `error_log`. Người dùng yêu cầu đúng vùng đó, nên nuốt lỗi rồi trả "xong" là nói dối.

### Giao diện — đã bấm tay bằng trình duyệt thật

Chromium (Playwright) mở thẳng vào bản đang chạy, đăng nhập thật, ảnh chụp lưu lại:

| Thấy gì | Ở đâu |
|---|---|
| *"**1 bong bóng sẽ trống** vì font không có ký tự trong bản dịch (thường là chữ Nhật còn sót) — sửa lại chữ ở vùng đó rồi căn lại"* | thẻ tóm tắt chapter |
| Bước **Căn chữ vào bong bóng** mang icon cảnh báo thay vì dấu tick | dòng thời gian pipeline |
| *"Bước **căn chữ** hỏng: MissingGlyph: font thiếu glyph cho '坂本さん'…"* — **hiện sẵn, không phải bấm** | thẻ tiến độ, dòng của Trang 1 |
| *"Không còn việc nào đang chạy — có bước đã hỏng, xem lý do ở từng trang bên trên"*, và **không còn** chữ "đang cập nhật…" | cuối thẻ tiến độ |
| Vùng 2 vẽ **khung đỏ gạch chéo** trên ảnh; vùng 1 có chữ Việt `CẬU ỔN CHỨ? TỚ VỀ ĐÂY.` nằm trong bong bóng | màn sửa tay |
| Nhãn *"⚠ Chưa chèn được chữ"* cạnh vùng 2 | danh sách vùng |
| *"**1 bong bóng sẽ trống hoàn toàn** — font không có ký tự nào đó trong bản dịch…"* | hộp thoại trước khi tải file |

Lớp `khung thieu-font` đọc thẳng từ DOM: `['khung dang-chon', 'khung thieu-font']`. Console không
có lỗi nào.

### Bấm tay lôi ra HAI lỗi mà 304 test không bắt được

1. **Bảng xuất vẫn nói "Không có cảnh báo nào"** trong khi cùng màn hình đó đang báo "1 bong bóng
   sẽ trống" — nó chỉ đếm tràn khung và vùng chưa đọc được chữ. Đúng loại nói dối mà F1 sinh ra
   để diệt, và F1 tự chừa lại một chỗ. Đã sửa.
2. **Ảnh trang và file xuất trả 401 từ khi bật đăng nhập (slice B)** — nặng hơn hẳn, và không
   thuộc F1. Xem `REPORT_B1C_ANH_VA_FILE.md`.

Không có bước "bấm tay" thì cả hai lỗi này đều đã lên bản chạy và nằm đó.

## Remaining Limits

1. **Vùng bỏ trống vẫn phải sửa tay.** Hệ thống chỉ ra chỗ, không tự xoá ký tự lạ khỏi bản dịch —
   xoá hộ là sửa nội dung sau lưng người dùng.
2. **Bảng gấp chỉ phủ dấu câu Nhật/CJK.** Ký hiệu hiếm (♪, ★, mũi tên…) mà font không có vẫn rơi
   vào đường #2. Đúng thiết kế, nhưng nghĩa là danh sách này sẽ còn phải dài ra theo thực tế.
3. **`quality-summary` chưa đếm vùng bỏ trống** thành một con số riêng ở màn chất lượng — nó chỉ
   xuất hiện qua mã lý do của từng vùng và ở cổng xuất. Gộp vào bảng tổng E12 là việc của mini-spec
   khác vì phải đổi schema `QualitySummary`.
4. **`ー` và chữ Nhật còn sót là vấn đề của bước DỊCH, không phải bước căn chữ.** F1 chỉ làm cho
   hậu quả nhìn thấy được. Vì sao engine trả về kana trong bản dịch tiếng Việt thì chưa điều tra.
