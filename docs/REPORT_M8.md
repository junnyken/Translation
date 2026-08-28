# Báo cáo Mini-Spec M8 — Chapter Export (PNG/CBZ) & Project Persistence

**Project:** Translation · **Phase:** MTE · **Ngày:** 2026-08-28
**Nền:** M1 `9d093be` · M2 `dea4965` · M3 `4b3139e` · M4 `9906501` · M5 `e4dbf74` ·
fonts `662bbcd` · M6 `689bcaf` · M7 `dffacbc` (`v0.7-M7`)

## 1. Summary

Chapter đã chèn chữ nay **xuất ra được thành file giao đi**: PNG từng trang, hoặc gói CBZ/ZIP đọc
được bằng ứng dụng truyện tranh. Xuất chạy trong worker, lấy **đúng `TypesetResult` mới nhất** (kể cả
phần vừa sửa tay ở M7), giữ **đúng thứ tự `Page.order`**, và **đếm rõ số vùng còn tràn khung** để
người dùng biết mình đang giao đi cái gì.

**Bảng mới `ExportJob` + cột `Page.exported_at`** — migration `0002_m8`, đã chạy thật
upgrade → downgrade → upgrade sạch. Không thêm phụ thuộc nào (`zipfile` là builtin).
**421 test pass**, 6 skip — tăng 55 test so với M7.

## 2. Audit Before Build

6/6 mục có bằng chứng ở `TEST_LOG § M8.1`. Điểm đáng chú ý:

- **`PagePreviewRenderer` của M6 chưa dùng lại được ngay**: `render()` chỉ ghi thẳng ra file, còn spec
  yêu cầu PNG binary trong RAM ⇒ tách `draw()` (trả ảnh) + `render()` (= `draw()` rồi ghi file).
  **Không nhân bản logic vẽ** — có guardrail quét mã chặn việc đó.
- **`zipfile` builtin**, không thêm phụ thuộc.
- `status` của `ExportJob` **dùng lại enum `job_status`** của M1 thay vì tạo enum trùng nghĩa.
- Worker ghi được `exports/`, API đọc được (kiểm bằng file thử trước khi viết logic), đĩa còn 66 GB.

**Về "Project Persistence" ở tiêu đề spec:** toàn bộ state đã nằm trong Postgres từ M1 — không có gì
giữ trong RAM hay file tạm để mất. Mở lại `GET /projects/{id}` là làm việc tiếp được ngay (M7 đã dùng
đúng đường đó). Vì vậy **cố ý không xây thêm cơ chế save/load** — thêm nữa là tạo bảng thứ hai lưu
cùng một sự thật, rồi hai bên lệch nhau.

## 3. Design Choice

- **Xuất là lớp file thứ tư, không đụng ba lớp trước.** Ảnh gốc (M1) · ảnh clean (M4) · ảnh xem thử
  (M6) · **file xuất (M8)** trong `exports/<project_id>/`. Có test so md5 trước/sau.
- **Dùng lại đúng `draw()` của M6.** Ảnh giao cho người đọc phải giống hệt ảnh người biên tập vừa
  duyệt trên màn sửa tay. Hai đường vẽ khác nhau là mầm mống lệch — có guardrail cấm `chapter.py`
  chạm tới `ImageDraw`/`multiline_text`/`getlength`.
- **Không vẽ khung đỏ cảnh báo lên ảnh xuất.** Khung đỏ là công cụ cho người biên tập (M6/M7), không
  phải thứ độc giả nên thấy. Cảnh báo đi bằng `overflow_warning_count` + `error_log`, không đi bằng
  vệt mực trên trang truyện.
- **Đánh số trang `001.png` có số 0 ở đầu.** Ứng dụng đọc truyện sắp trang **theo tên file**; thiếu số
  0 thì `10.png` chen lên trước `2.png`. Độ rộng số tự giãn theo tổng số trang.
- **Trang chưa canh chữ thì BỎ QUA, không xuất — nhưng nói rõ.** Xuất ảnh chưa có chữ là giao hàng
  hỏng. Số trang bỏ qua ghi vào `error_log` kèm lý do từng trang; không trang nào xuất được ⇒ job
  `failed` với `no_page_ready`. Job vẫn là `done` khi xuất được phần còn lại — kèm cảnh báo.
- **Tràn khung KHÔNG chặn xuất** (đúng spec) nhưng phải đếm đúng và hiện ở cả `export-preview`
  (trước khi xuất) lẫn `ExportJob` (sau khi xuất).
- **Ghi file tạm rồi `os.replace`** — đổi chỗ nguyên tử, không bao giờ lộ gói ZIP dở dang. Cùng cách
  M6 làm với ảnh xem thử.
- **Dọn sạch thư mục trước khi ghi**, kể cả khi đổi định dạng (cbz → png_single) — nếu không, chọn
  định dạng khác sẽ để lại file cũ và người dùng tải nhầm bản lỗi thời.
- **Tên file bỏ dấu tiếng Việt.** File này còn đi qua máy khác, ứng dụng đọc truyện, hệ tệp không
  Unicode. `Truyện Hay #1` → `truyen_hay_1_chapter.cbz`.
- **`png_single` trả `409` ở endpoint tải về**, kèm hướng dẫn chọn CBZ/ZIP — thay vì trả file sai hoặc
  âm thầm dựng ZIP mà người dùng không yêu cầu.
- **Timeout riêng** (`EXPORT_TIMEOUT_SECONDS=900`) — nay là **bảy** timeout độc lập, có test canh.

## 4. Changed Files

| File | Đổi gì |
|---|---|
| `backend/alembic/versions/0002_m8_export_chapter.py` | **mới** — bảng `export_job` + `page.exported_at`; sửa 2 bẫy enum |
| `backend/app/models/__init__.py`, `enums.py` | `ExportJob`, `ExportFormat`, `Page.exported_at` |
| `backend/app/services/export/chapter.py` | **mới** — `ChapterExporter`: render RAM, đóng gói, dọn file cũ |
| `backend/app/services/export/naming.py` | **mới** — đặt tên file an toàn với hệ tệp |
| `backend/app/services/export/paths.py` | **mới** — quy ước đường dẫn, không import Pillow |
| `backend/app/services/typeset/preview.py` | tách `draw()` khỏi `render()` để M8 dùng lại |
| `backend/app/workers/tasks.py` | `run_export_job`, `thong_ke_xuat`, `dem_vung_tran_khung`, `_thu_thap_trang` |
| `backend/app/api/v1/routes.py` | +4 endpoint export; **sửa lỗi** `retry-translate` chặn `typeset_done` |
| `backend/app/schemas/common.py` | `ExportRequest`, `ExportPreview`, `ExportJobRead`, `ExportJobAccepted` |
| `backend/app/core/config.py` | +`export_timeout_seconds` |
| `frontend/src/components/ExportPanel.jsx` | **mới** — xem trước cảnh báo → chọn định dạng → tiến trình → tải về |
| `backend/tests/test_export_*.py` | **mới** — 48 test |
| `backend/tests/test_no_ai_logic.py` | +6 guardrail M8 |

## 5. New API / DB / State

**API mới:** `GET /projects/{id}/export-preview` · `POST /projects/{id}/export` ·
`GET /export-jobs/{id}` · `GET /export-jobs/{id}/download`

**DB:** bảng `export_job` (mới) + cột `page.exported_at` (mới). Migration `0002_m8`.

**State:** `Page.status` **không đổi** khi xuất — trang vẫn `typeset_done` để còn sửa tiếp và xuất
lại. Chỉ ghi `exported_at`. Cố ý không dùng `ready_for_export`: nó không mang thêm thông tin gì so
với `exported_at`, mà lại làm phức tạp đường quay về sửa tay.

## 6. Tests

`421 passed, 6 skipped in 113.40s` — chi tiết ở `TEST_LOG § M8.2`.
55 test mới: 21 unit + 27 integration + 6 guardrail + 1 hồi quy cho lỗi §7.

## 7. Bugs tìm được & đã sửa

| Lỗi | Thuộc | Vì sao trốn được lâu | Xử lý |
|---|---|---|---|
| **`POST /pages/{id}/retry-translate` trả 409 với MỌI trang** | M5 + M6 | Danh sách điều kiện của M5 viết khi `typeset_done` chưa phải trạng thái tự động. Từ M6, pipeline nối chuỗi nên **mọi trang** đều dừng ở đó ⇒ endpoint chết hẳn, im lặng. M7 mở đường dịch lại **từng vùng** nên che mất triệu chứng | Thêm `typeset_done` vào danh sách cho phép + test canh |
| Alembic sinh `sa.Enum(name='job_status')` cho bảng mới | M8 | — | `postgresql.ENUM(create_type=False)`; bắt được nhờ chạy thử migration trước khi commit |
| `downgrade` không xoá `export_format` | M8 | — | `DROP TYPE IF EXISTS` (đúng bài học M1) |

**Ngoài phạm vi nhưng phải ghi:** worker bị **OOM giết (SIGKILL)** giữa lúc xoá chữ, job kẹt
`status=running` **vĩnh viễn**, `error_log` rỗng. Không có gì đánh dấu `failed` khi worker chết —
pipeline đứng im mà nhìn vào không biết vì sao. Chi tiết ở `TEST_LOG § M8.4`.

## 8. Phát hiện lớn nhất — chất lượng bản dịch trong file giao đi

File CBZ đầu tiên **có chữ tiếng Anh chưa dịch**. Xuất không sai — nó phản ánh trung thực thứ
pipeline tạo ra. Nguyên nhân là mặc định `google_fast`:

| OCR đọc được | `google_fast` (miễn phí) | `llm_context` (Gemini) |
|---|---|---|
| `ITIS` / `TOO LATE` | **`CNTT`** / `QUÁ TRỄ` | Muộn quá rồi. |
| `THE SUN` / `ISUP` | `MẶT TRỜI` / **`ISUP`** | Mặt trời lên rồi. |
| `HOLDON` / `TIGHT` | **`HOLDON`** / `CHẮC CHẮN` | Bám chắc vào. |
| `ISEE` / `THE END` | **`ISEE`** / `KẾT THÚC` | Tôi thấy đích rồi. |

OCR dính chữ là chuyện thường; `google_fast` dịch từng dòng rời nên gặp token lạ thì bỏ nguyên tiếng
Anh, thậm chí đoán bậy (`ITIS` → `CNTT`). `llm_context` nhìn cả trang nên tự sửa — **386 token cho
2 trang**. Mặc định miễn phí vẫn đúng nguyên tắc, nhưng **cần cảnh báo trước khi giao file**.
Việc này thuộc mini-spec sau, không mở rộng M8 giữa chừng.

## 9. Success Criteria — đối chiếu thẳng

| Tiêu chí spec | Kết quả |
|---|---|
| CBZ/ZIP mở được, đúng số PNG theo `Page.order` | ✅ ZIP hợp lệ, `001…004.png`, sắp theo tên = đúng thứ tự |
| PNG single đúng số file, mỗi file mở được | ✅ có test |
| `overflow_warning_count` đúng với thực tế | ✅ khớp cả ở `export-preview` lẫn `ExportJob` |
| Xuất lại ⇒ file cũ bị xoá, không tích tụ rác | ✅ chạy 3 lần + đổi định dạng, thư mục vẫn 1 kết quả |
| Toàn bộ test M1–M7 vẫn pass | ✅ 421 pass, không sửa kỳ vọng cũ để lách |
| Guardrail chặn xuất bản chưa qua canh chữ | ✅ chốt danh sách trạng thái + test |
| Live: xuất CBZ/PNG thành công, file mở được | ✅ `TEST_LOG § M8.3` |
| **File mở bằng ứng dụng đọc truyện thật** | ❌ **chưa** — mới kiểm bằng `zipfile` + Pillow |

## 10. Remaining Limits / Follow-ups

- **Chưa mở CBZ bằng ứng dụng đọc truyện thật** (Tachiyomi / Perfect Viewer). Cấu trúc đã đúng chuẩn
  ZIP nhưng đó chưa phải bằng chứng cuối.
- **Run C vẫn treo** — vẫn ảnh tổng hợp. Lần này ảnh mẫu còn có nhược điểm mới: chữ nguồn quá nhỏ nên
  bbox chỉ ~50×34 px, chữ dịch trong ảnh xuất trông rất nhỏ (không phải lỗi xuất).
- **Chưa đo trên chapter lớn** — mọi con số đều từ 4 trang (1,0 s).
- **Chưa cảnh báo "chapter này dịch bằng bản miễn phí"** trước khi xuất — xem §8.
- **Chưa có watchdog cho job chết vì OOM** — job kẹt `running` vĩnh viễn.
- **Chưa có auth**, **chưa lưu nhiều phiên bản export**, **chưa đẩy file lên cloud storage**,
  **chưa xuất nhiều chapter cùng lúc** (M9).

**Mini-spec kế tiếp:** M9 — Batch Processing & API Key Rotation Hardening. Nên gộp thêm:
watchdog job chết, và cảnh báo chất lượng dịch trước khi xuất.
