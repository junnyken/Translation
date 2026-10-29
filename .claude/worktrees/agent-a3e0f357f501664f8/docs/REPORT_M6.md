# Báo cáo Mini-Spec M6 — Dynamic Font-Size & Text-Wrap Fit-to-Bubble Engine

**Project:** Translation · **Phase:** MTE · **Ngày:** 2026-08-27
**Nền:** M1 `9d093be` · M2 `dea4965` · M3 `4b3139e` · M4 `9906501` · M5 `e4dbf74` (`v0.5-M5`)
**Font bundle:** `662bbcd`

## 1. Summary

Pipeline nay chạy trọn vẹn tới **trang truyện có chữ Việt**: upload → nhận diện khung → đọc chữ →
xoá chữ gốc → dịch → **canh cỡ chữ + ngắt dòng cho vừa bubble và render ảnh xem thử**.

Với mỗi `TextRegion` của Page đã `translated`, worker đo bằng **font metrics thật** (Pillow
`getlength` / `multiline_textbbox`), chọn cỡ chữ lớn nhất mà bản dịch vẫn nằm trong bbox trừ padding,
ghi `TypesetResult`, rồi vẽ **một ảnh preview riêng** từ ảnh clean của M4. Không vừa dù đã xuống cỡ
nhỏ nhất ⇒ `overflow_warning`, **không co chữ nhỏ hơn min để giả vờ vừa khung**.

**Không tạo bảng mới, không migration** (`TypesetResult` đã có từ M1).
**329 test pass**, 6 skip — tăng 57 test so với M5.

## 2. Audit Before Build

7/7 mục có bằng chứng trong `TEST_LOG § M6.1`. Tóm tắt: `ITypesetter` + `TypesetResult` + `FitStatus`
+ `JobType.typeset` nguyên vẹn từ M1 ⇒ không cần migration; bbox đúng pixel ảnh clean (max `1147×1798`
trong `1400×2000`); Pillow 11.0.0 có đủ API cần và **đã gỡ hẳn `textsize`/`getsize`**; worker ghi được
và API đọc được cùng volume; đĩa còn 68 GB; `typeset_result` có 0 record.

**Hai phát hiện làm đổi thiết kế:**

1. **`raqm` KHÔNG có trong worker** (workspace thì có). Đo thật: chuỗi **NFD render sai**
   (`ĐỪNG` → `ĐUNG`, `LẠI` → `LAỊ`) trong khi `getlength()` **vẫn trả đúng con số của NFC** — nghĩa là
   sai không lộ ra qua bất kỳ phép đo nào. Dữ liệu M5 hiện là NFC nhưng Gemini không cam kết điều đó.
2. **`fonts/` chưa được mount vào worker** — đã bổ sung `./fonts:/fonts:ro` + `FONT_DIR`.

## 3. Design Choice

- **Giảm dần 1px, KHÔNG tìm kiếm nhị phân.** Spec §6 cho phép nhị phân *nếu* quan hệ vừa-khung đơn điệu.
  Đo trên 8 ca: **2 ca không đơn điệu**. `"Cẩn thận!"` trong bubble 108×84 vừa ở cỡ 25, **hỏng ở 26, lại
  vừa ở 27** (ngắt dòng nhảy rời rạc giữa 1 và 2 dòng). Nhị phân dừng ở 25, bỏ sót 27. → chọn **một**
  thuật toán duy nhất là giảm 1px, có test khoá lại chính ca đó. Bảng đo: `TEST_LOG § M6.4`.
- **Chuẩn hoá NFC trong đường đo/vẽ** (`normalize_for_layout`). NFC và NFD là **cùng một văn bản** theo
  chuẩn Unicode nên đây không phải "sửa nội dung bản dịch" — và tuyệt đối **không ghi ngược** vào
  `TranslationResult`. Cách khác là cài `raqm` vào image worker; đã chọn chuẩn hoá vì rẻ, tất định, và
  không phụ thuộc vào việc dựng lại image.
- **Chặn tofu chủ động.** `FontResolver.assert_can_render()` vẽ từng ký tự rồi so với ký tự chắc chắn
  không tồn tại; giống nhau ⇒ ném `font_missing_glyph`. Không dùng `fontTools` để khỏi thêm phụ thuộc
  runtime cho worker, và cách này kiểm đúng thứ ta quan tâm: **vẽ ra có thành ô vuông không**.
  *Bản đầu tiên của hàm này có `except: return` và đã âm thầm tắt luôn phép kiểm — đúng loại lỗi im lặng
  mà nó sinh ra để chống. Nay cố ý không bắt exception.*
- **Whitelist font, không hard-code đường dẫn.** `FONT_REGISTRY` map family → file + tên nét.
  Font lạ/thiếu file ⇒ `font_not_found`. `ALLOW_FONT_FALLBACK` mặc định **false**: không âm thầm đổi font.
- **`pending` cho vùng chưa có bản dịch — lệch spec, có chủ ý.** Spec §4B đề nghị `overflow_warning`
  hoặc fail. Cả hai đều nói sai sự thật: vùng không có chữ thì **không có gì tràn cả**, và fail cả job
  vì một dòng M5 chưa trả về là quá tay. Enum `FitStatus` của M1 đã có sẵn `pending` = "chưa xử lý",
  khớp nghĩa. Số lượng `pending` được đếm riêng trong log + kết quả job nên không bị giấu.
- **Preview là file thứ ba, đổi chỗ nguyên tử.** Ghi ra `.tmp.png` rồi `os.replace` — preview cũ chỉ bị
  thay khi ảnh mới đã ghi xong, không bao giờ lộ ảnh vẽ dở. Đường dẫn ổn định `previews/<page_id>/typeset.png`
  nên chạy lại là ghi đè đúng file, **không thêm cột vào `TypesetResult`** (đúng khuyến nghị spec §4A).
- **Vùng tràn được vẽ khung đỏ** trên preview: cảnh báo phải nhìn thấy được, không để ảnh đẹp che mất.
- **`typeset/paths.py` tách riêng, không import Pillow.** API cần biết chỗ đặt preview nhưng
  **không được nạp engine render** — nếu để chung `preview.py` thì `import app.main` sẽ kéo Pillow vào.
  Package `__init__.py` cũng chỉ export `paths` vì lý do đó.
- **Trần cỡ chữ mặc định 28 → 40.** Chạy Run A với 28 (spec đề xuất): **5/6 vùng dừng đúng ở 28** ⇒ trần
  đang chặn chứ không phải bubble. Nới lên 40 thì không vùng nào chạm trần; trên 40 kết quả không đổi.
  Bảng đo: `TEST_LOG § M6.5`.
- **Timeout riêng cho typeset** — nay là **năm** timeout độc lập, có test canh.

## 4. Changed Files

| File | Đổi gì |
|---|---|
| `backend/app/services/typeset/fonts.py` | **mới** — `FontResolver` (whitelist), chặn tofu, chuẩn hoá NFC |
| `backend/app/services/typeset/layout.py` | **mới** — `TextLayoutEngine`: ngắt dòng + đo khối nhiều dòng |
| `backend/app/services/typeset/fitter.py` | **mới** — `FitToBoxTypesetter(ITypesetter)`, giảm 1px |
| `backend/app/services/typeset/preview.py` | **mới** — `PagePreviewRenderer`, ghi nguyên tử |
| `backend/app/services/typeset/paths.py` | **mới** — quy ước đường dẫn, CỐ Ý không import Pillow |
| `backend/app/workers/tasks.py` | +~230 — `run_typeset_job`, nối chuỗi sau translate, `build_typesetter` |
| `backend/app/api/v1/routes.py` | +~75 — `GET /typeset`, `GET /typeset-preview`, `POST /retry-typeset` |
| `backend/app/core/config.py` | +~20 — 12 biến M6 |
| `backend/app/schemas/common.py` | +~15 — `TypesetResultRead` |
| `backend/app/services/dispatch.py` | +13 — `dispatch_typeset_job` |
| `docker-compose.yml` | +2 — mount `./fonts:/fonts:ro` cho worker (API không mount) |
| `backend/tests/test_typeset_*.py` | **mới** — 51 test |
| `backend/tests/test_no_ai_logic.py` | +6 guardrail M6 |
| `.env`, `.env.example`, `docs/*` | cấu hình + tài liệu |

## 5. New API / DB / State

**API mới:** `GET /api/v1/pages/{id}/typeset` · `GET /api/v1/pages/{id}/typeset-preview` ·
`POST /api/v1/pages/{id}/retry-typeset`

**DB:** không bảng mới, không migration. M6 **ghi** vào `typeset_result`.

**State:** `translated → typeset_done`. Job lỗi/thiếu font/timeout ⇒ Page **giữ** `translated`,
không có preview nửa vời. Vùng `overflow_warning` **không** chặn `typeset_done` (M7 sẽ sửa tay).

## 6. Tests

`329 passed, 6 skipped in 44.22s` — chi tiết từng nhóm ở `TEST_LOG § M6.2`.
57 test mới: 21 layout/font · 13 thuật toán fit · 17 integration task+API · 6 guardrail.

## 7. Live Verification

Run A chạy đúng đường thật (HTTP → Redis → worker → Pillow → DB + file). Số liệu đầy đủ:
`TEST_LOG § M6.3`.

- **6/6 vùng `fit_ok`**, cỡ chữ 27–36 (không vùng nào chạm trần), 1–2 dòng, **0,5–0,6 s/trang**.
- Chữ Việt **đủ dấu**, căn giữa hai chiều, không chạm viền bubble — kiểm bằng mắt qua preview.
- **Checksum ảnh gốc + ảnh clean không đổi**; preview là file thứ ba, đúng 1400×2000.
- **Ca tràn có chủ ý**: câu 208 ký tự trong bubble 192×81 ⇒ cỡ **đúng 10 = min**, `overflow_warning`,
  7 dòng, khung đỏ trên preview, chữ không tràn ra trang.
- **Idempotent**: chạy lại 2 lần ⇒ vẫn 6 bản ghi, vẫn đúng 1 file preview, không sót `.tmp.png`.

## 8. Success Criteria — đối chiếu thẳng

| Tiêu chí spec | Kết quả |
|---|---|
| 100% region có TranslationResult nhận đúng 1 TypesetResult, không duplicate khi retry | ✅ 6/6, retry ×2 vẫn 6 |
| `fit_ok` ⇒ mọi dòng nằm trong content rectangle | ✅ có test đo lại sau khi fit |
| Không fit ⇒ `font_size` ≥ min và `fit_status` hiện rõ ở API | ✅ dừng đúng ở 10, đọc được ở `GET /typeset` |
| Preview đúng kích thước ảnh clean; checksum `image_path` + `clean_image_path` không đổi | ✅ md5 khớp trước/sau |
| Page chỉ `typeset_done` sau khi ghi xong result + preview; font missing/timeout ⇒ job failed, Page giữ `translated` | ✅ có test cho cả 2 nhánh |
| Toàn bộ test M1–M5 vẫn pass; API không nạp engine render | ✅ 329 pass; guardrail canh `import app.main` |
| Live Run A có evidence thật | ✅ `TEST_LOG § M6.3` |
| **Run B — font comic mà spec chỉ định** | ❌ **KHÔNG chạy được** (xem §9) |
| **Run C — manga scan thật** | ❌ **CHƯA chạy** — vẫn thiếu ảnh có license rõ |

## 9. Remaining Limits / Follow-ups

- **Run B không thể thực hiện như spec mô tả.** Cả 3 font spec chỉ định đều không dùng được cho tiếng
  Việt: `HL Comic2` chỉ 38/134 ký tự (font mã TCVN3 đời 2004), `Anime Ace` "Limited European Characters"
  + phải mua license, `MTO Comic` không tồn tại. Chi tiết + bằng chứng đo: `docs/FONTS.md`.
  M6 đang chạy bằng **Bangers** — font comic thật, SIL OFL, đủ 134/134 dấu — **không phải** font hệ thống
  chữa cháy, nên không đánh dấu `provisional_font=true` theo nghĩa spec. **Nhưng** typography vẫn **chưa
  được người làm truyện duyệt**, và nếu sau này có bản `HL-Comic2unicode` chính chủ thì nên chạy lại.
- **Run C vẫn treo** — mọi số liệu M2–M6 đều đo trên ảnh tổng hợp nền phẳng. Không được tuyên bố
  "production-ready" từ đây.
- **bbox là hình chữ nhật, bubble là ellipse** — chữ căn giữa vẫn có thể chạm mép cong ở bubble dẹt.
  Fixture chưa lộ ra; cần Run C xác nhận. Nếu thành failure mode lớn ⇒ mini-spec hardening riêng.
- **Chưa có text dọc / chữ xoay / SFX** — đúng phạm vi spec, để mini-spec sau.
- **Font per-project chưa có** — đang dùng `DEFAULT_FONT_FAMILY` cho cả hệ thống; override theo project
  thuộc M7 như spec ghi.
- **Chưa có UI sửa tay** (M7) và **chưa export** (M8).

**Mini-spec kế tiếp:** M7 — Manual Review & Edit UI: sửa bản dịch/bbox/font từng vùng, chạy lại fit đúng
vùng đó và giữ `edited_by_user=true`.
