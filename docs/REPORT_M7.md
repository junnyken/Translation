# Báo cáo Mini-Spec M7 — Region Edit Panel (Text/Box/Font Override)

**Project:** Translation · **Phase:** MTE · **Ngày:** 2026-08-28
**Nền:** M1 `9d093be` · M2 `dea4965` · M3 `4b3139e` · M4 `9906501` · M5 `e4dbf74` ·
fonts `662bbcd` · M6 `689bcaf` (`v0.6-M6`)

## 1. Summary

Từ M7, người biên tập **sửa được bằng tay** những chỗ máy làm chưa đạt: sửa bản dịch, kéo/co giãn
khung chữ ngay trên ảnh, đổi kiểu chữ và ghim cỡ chữ. Mỗi lần sửa chỉ **canh lại đúng vùng đó**
(không tính lại cả trang) rồi vẽ lại ảnh xem thử, và luôn đóng dấu `edited_by_user=true` để về sau
còn phân biệt đâu là máy làm, đâu là người sửa.

Kèm theo là **giao diện đầu tiên của dự án** (React + Vite): ảnh xem thử có khung chữ chồng lên,
bảng sửa từng vùng, nhãn cảnh báo, và dòng lịch sử "máy dịch / đã sửa tay".

**Không tạo bảng mới, không migration, không thêm cột.** `edited_by_user` đã có từ M1;
`TimestampMixin.updated_at` đã ghi sẵn thời điểm sửa.
**366 test pass**, 6 skip — tăng 37 test so với M6.

## 2. Audit Before Build

6/6 mục có bằng chứng ở `TEST_LOG § M7.1`. Tóm tắt: `edited_by_user` có sẵn ở cả hai bảng và
**16/16 record trong DB đều `false`**; `fit()` của M6 nguyên vẹn nên M7 gọi lại chứ không viết lại;
chuẩn hoá NFC giữ nguyên; không có `PATCH` nào và không có thư mục frontend nào.

Hai điểm khác với mô tả trong spec, đã kiểm chứng:
- `TextRegion.bbox_x/y/w/h` là **`nullable=False`**, không phải nullable. Không ảnh hưởng.
- **Không cần thêm cột nào** (spec §4A yêu cầu nêu rõ): `updated_at` đã có `onupdate`, và chưa có
  auth nên không có user id để lưu.

**Phát hiện của audit:** endpoint preview của M6 thiếu `Cache-Control`, mà đường dẫn lại cố định
theo page ⇒ sửa xong trình duyệt vẫn hiện ảnh cũ, phạm constraint 8. Đã sửa cả hai đầu.

## 3. Design Choice

- **Backend trước, UI sau** (spec §6). Toàn bộ API + task + test backend xong và xanh trước khi
  viết dòng React đầu tiên; UI chỉ là bên tiêu thụ API.
- **`PATCH` trả `fit_status = pending`, không trả trạng thái cũ.** Sửa xong là bản canh cũ không còn
  đúng với nội dung mới, nên báo `fit_ok` lúc đó là **nói sai**. API ghi phần sửa, hạ trạng thái
  xuống `pending`, trả kèm `refit_job_id` để UI theo dõi. Không canh chữ trong request.
- **`font_size` nghĩa là *ghim cỡ chữ*, không phải gợi ý.** Người dùng đổi cỡ tay là vì tự dò chưa
  vừa ý, nên `fit_at_size()` dùng **đúng** cỡ đó — nhưng vẫn nói thật: tràn thì gắn
  `overflow_warning`, không giả vờ vừa. Bỏ trống ô "tự chọn" = quay lại tự dò như M6.
  Chọn cách này thay vì thêm cột `font_size_locked`: spec §4A không cho tự thêm cột, và UI luôn gửi
  kèm cỡ đang hiển thị nên người dùng thấy đúng như kỳ vọng.
- **Canh lại theo vùng, vẽ lại cả trang.** Tính toán chỉ chạy cho 1 vùng (~0,1s), nhưng ảnh xem thử
  luôn vẽ lại toàn trang từ đúng những gì đang có trong DB — vẽ từng phần dễ sai khi các bubble
  chồng nhau. Hàm `render_page_preview()` dùng chung cho cả M6 lẫn M7 nên **không có hai đường vẽ
  khác nhau**.
- **`re-ocr` và `re-translate` cố ý KHÔNG tự dây chuyền.** Đọc lại chữ gốc xong không tự dịch lại,
  dịch lại xong không tự canh lại — vì cả hai đều **ghi đè**, có thể xoá mất phần người dùng vừa gõ
  tay. Người dùng chủ động bấm tiếp.
- **Chặn font ở tầng API bằng chính whitelist của M6.** Gửi font lạ ⇒ `422 font_not_found`.
  Muốn thêm font thì qua `.env` + `FONT_REGISTRY`, không qua UI (spec §6).
- **Tách `typeset/registry.py` không import Pillow.** API cần đọc danh sách font để validate và để
  đổ dropdown, nhưng **không được nạp engine render** — nếu để chung `fonts.py` thì `import app.main`
  sẽ kéo Pillow vào. Cùng lý do đã tách `typeset/paths.py` ở M6.
- **Chống ảnh cũ hai lớp:** server trả `Cache-Control: no-cache`, client thêm `?v=` đổi sau mỗi lần
  vẽ lại. Một lớp là đủ trên lý thuyết, nhưng đây là lỗi "người dùng tưởng bấm không ăn" — rất khó
  phát hiện, nên chấp nhận thừa.
- **Cảnh báo hiện bằng CHỮ, không chỉ bằng màu** (`Tràn khung`, `Cần đọc lại`, `Khung kém tin cậy`)
  — người mù màu vẫn đọc được, và ảnh chụp màn hình vẫn kiểm chứng được.

## 4. Changed Files

| File | Đổi gì |
|---|---|
| `backend/app/workers/tasks.py` | `render_page_preview()` (tách ra dùng chung), `run_refit_job`, `run_region_reocr_job`, `run_region_retranslate_job` |
| `backend/app/services/typeset/fitter.py` | +`fit_at_size()` — canh ở đúng cỡ người dùng ghim |
| `backend/app/services/typeset/preview.py` | **sửa lỗi**: vẽ mỗi vùng vào ô riêng bằng bbox rồi dán đè ⇒ chữ tràn bị cắt gọn |
| `backend/app/services/typeset/registry.py` | **mới** — whitelist font, không import Pillow |
| `backend/app/api/v1/routes.py` | +5 endpoint; thêm `Cache-Control` cho preview |
| `backend/app/schemas/common.py` | `RegionPatch`, `BBoxIn`, `RegionPatchAccepted`, `RegionDetail`, `PageDetail`, `JobAccepted` |
| `backend/app/services/dispatch.py` | 3 hàm dispatch mới |
| `backend/app/core/config.py` | +`refit_timeout_seconds` |
| `frontend/` | **mới** — React 18 + Vite: `App.jsx`, `BboxOverlay.jsx`, `RegionPanel.jsx`, `StatusBadge.jsx`, `api.js`, `styles.css`, `Dockerfile` |
| `docker-compose.yml` | +service `frontend` (cổng 5174) |
| `backend/tests/test_region_edit_integration.py` | **mới** — 31 test |
| `backend/tests/test_no_ai_logic.py` | +5 guardrail M7 |
| `backend/tests/test_typeset_task_integration.py` | +1 test bất biến "chữ không ra ngoài khung" |

## 5. New API / DB / State

**API mới:**
`GET /api/v1/pages/{id}/detail` · `PATCH /api/v1/regions/{id}` ·
`POST /api/v1/regions/{id}/re-fit` · `.../re-ocr` · `.../re-translate`

**DB:** không bảng mới, không cột mới, không migration. M7 **ghi** `edited_by_user=true` và cập nhật
`TextRegion.bbox_*`, `TranslationResult.translated_text`, `TypesetResult.*`.

**State:** `Page.status` **không đổi** — sửa tay diễn ra khi trang đã `typeset_done` và giữ nguyên
trạng thái đó. Job canh lại lỗi ⇒ `Job.status=failed` + `error_log`, dữ liệu vùng giữ nguyên.

## 6. Tests

`366 passed, 6 skipped in 72.99s` — chi tiết ở `TEST_LOG § M7.2`.
37 test mới: 31 integration + 5 guardrail + 1 bất biến render.

## 7. Live Verification

Chạy Chromium thật, thao tác thật trên giao diện, đối chiếu DB + md5 ảnh. Bảng đầy đủ:
`TEST_LOG § M7.3`.

- Sửa bản dịch: cỡ chữ tự đổi **30 → 13 → 40** theo độ dài, ảnh vẽ lại **cả 4 lần**.
- Đổi font `Mansalva` + ghim cỡ **16** → lưu đúng.
- **Kéo khung bằng chuột**: kéo 60 px màn hình ⇒ bbox dịch **84 px ảnh gốc** = đúng tỷ lệ 1000/1400.
- Ghim cỡ **40** cho câu dài ⇒ `overflow_warning`, nhãn đỏ, bộ đếm "1 vùng tràn khung".
- Bật/tắt cảnh báo: 1 → 0 → 1 khung cảnh báo.
- **0 lỗi JavaScript** trong toàn bộ phiên; md5 ảnh gốc + ảnh clean không đổi.

## 8. Bugs tìm được & đã sửa

| Lỗi | Thuộc | Vì sao không lộ ra sớm hơn | Đã sửa |
|---|---|---|---|
| Khung chữ vẽ **lệch hẳn khỏi bubble**, vùng 2 và 4 nằm ngoài ảnh | M7 (UI) | Tỷ lệ quy đổi tính khi ảnh **chưa tải xong** ⇒ `naturalWidth=0`, tỷ lệ kẹt ở 1. Không test tự động nào bắt được — chỉ nhìn ảnh mới thấy | Overlay tự sở hữu `<img>`, tính lại lúc `load`; chưa đo được thì **không vẽ khung nào** |
| Chữ tràn khung **chạy dọc suốt trang**, đè lên khung tranh khác | **M6** | Ca tràn ở M6 nằm ở cỡ nhỏ nhất (10 px) nên khối chữ gần bằng bbox. Chỉ khi M7 cho **ghim cỡ 40** mới lộ | Vẽ mỗi vùng vào ô riêng bằng bbox rồi dán đè ⇒ chữ bị cắt gọn. Thêm test so **từng pixel** ngoài bbox |
| Ảnh xem thử bị trình duyệt nhớ bản cũ | M6 | Backend test dùng HTTP client không có bộ nhớ đệm nên không bao giờ tái hiện | `Cache-Control: no-cache` ở server + `?v=` ở client |
| `OCRResult(engine=…)` — sai tên cột (đúng là `ocr_engine`) | M7 | — | Test integration bắt ngay lần chạy đầu |

## 9. Success Criteria — đối chiếu thẳng

| Tiêu chí spec | Kết quả |
|---|---|
| PATCH region thành công, trả đúng `region_id`, `fit_status` mới, không 500 | ✅ trả `pending` + `refit_job_id` (giải thích ở §3) |
| `edited_by_user=true` khi sửa tay, **không** bị set khi auto-fit | ✅ có guardrail quét mã nguồn cả hai nhánh |
| Preview vẽ lại sau khi sửa, không dùng ảnh cũ | ✅ md5 đổi cả 4 lần + chống cache hai lớp |
| Sửa 1 vùng không làm đổi vùng khác | ✅ chụp nguyên trạng vùng B trước/sau |
| Toàn bộ test M1–M6 vẫn pass | ✅ 366 pass, không sửa kỳ vọng cũ để lách |
| Checksum ảnh gốc / ảnh clean không đổi | ✅ có test tự động |
| Live: sửa text/bbox/font/size thành công, preview vẽ lại đúng | ✅ `TEST_LOG § M7.3` |

## 10. Remaining Limits / Follow-ups

- **Chưa có auth** — ai mở được URL là sửa được; `edited_by_user` chỉ nói "có người sửa", không nói
  **ai** sửa. Mini-spec riêng, ngoài Phase MTE.
- **Chưa có lịch sử phiên bản** — sửa là đè lên bản cũ, không lùi lại được. Dữ liệu gốc của M2/M3/M5
  vẫn còn nguyên để đối chiếu.
- **Chưa sửa hàng loạt** (nhiều vùng một lúc) — follow-up.
- **Giao diện mới thử ở 1600×1100 trên Chromium** — chưa thử màn hình nhỏ, trình duyệt khác, và
  **chưa làm được thao tác kéo khung bằng bàn phím** (người không dùng được chuột sẽ vướng).
- **Chưa export PNG/CBZ** — M8.
- **Run B / Run C vẫn treo**: cần font comic đủ dấu tiếng Việt được duyệt và ảnh scan có license rõ.

**Mini-spec kế tiếp:** M8 — Chapter Export (PNG/CBZ) & Project Save/Load.
