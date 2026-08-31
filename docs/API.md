# API.md — Translation (prefix `/api/v1`)

Swagger tự sinh: `http://localhost:8010/docs` · OpenAPI JSON: `/openapi.json`

Nguyên tắc:
- Response **luôn** qua Pydantic schema (không trả SQLAlchemy object).
- Lỗi validate → `422` theo format mặc định FastAPI (không tự chế error format).
- Endpoint kích hoạt bước AI → `202 Accepted` + `job_id`, không trả kết quả trực tiếp.

## 1. `POST /api/v1/projects` → 201

Request:
```json
{ "name": "Chapter 01", "source_lang": "ja", "target_lang": "vi", "intended_use": "personal" }
```
- `source_lang`: `ja` | `zh` | `en` (bắt buộc)
- `target_lang`: `vi` (mặc định `vi`)
- `intended_use`: `personal` | `study` | `other` (**bắt buộc** — guardrail bản quyền của M10)

Response 201:
```json
{ "id": "…uuid…", "name": "Chapter 01", "source_lang": "ja", "target_lang": "vi",
  "intended_use": "personal", "status": "active", "created_at": "…", "updated_at": "…" }
```
Thiếu `name` / `source_lang` / `intended_use`, hoặc giá trị ngoài enum → `422`.

## 2. `GET /api/v1/projects/{project_id}` → 200

Trả project kèm tóm tắt page:
```json
{ "id": "…", "name": "…", "…": "…",
  "pages": [ { "id": "…", "order": 1, "status": "queued" } ] }
```
Không tồn tại → `404`.

## 3. `POST /api/v1/projects/{project_id}/pages` → 202

`multipart/form-data`, field `file` = ảnh trang (JPEG/PNG/WEBP, mặc định ≤ 25MB).

Hành vi: lưu file xuống storage → tạo `Page(status=queued, order=max+1)` →
tạo `Job(type=detect, status=queued)` → **đẩy job sang worker (M2)**. **Không** chạy detect trong request.

Nếu broker (Redis) chết: vẫn trả 202 (ảnh đã lưu), job đứng ở `queued` và `error_log` ghi
`enqueue_failed: …` — không giả vờ đã gửi. Chạy lại bằng `POST /pages/{id}/retry-detect`.

Response 202:
```json
{ "page_id": "…uuid…", "status": "queued", "job_id": "…uuid…" }
```
| Lỗi | Mã |
|---|---|
| project không tồn tại | 404 |
| file rỗng / không phải ảnh thật (kiểm magic bytes) | 422 |
| ảnh vượt `MAX_UPLOAD_MB` | 413 |

> `job_id` là field **thêm** so với bảng contract gốc của M1 (gốc: `{page_id, status}`) —
> thêm để client polling `GET /jobs/{id}` được ngay, không phải dò job của page. Ghi rõ ở báo cáo M1.

## 4. `GET /api/v1/pages/{page_id}` → 200

```json
{ "id": "…", "project_id": "…", "image_path": "projects/<pid>/pages/<page_id>.png",
  "clean_image_path": null, "order": 1, "status": "queued", "created_at": "…", "updated_at": "…" }
```
`clean_image_path` = `null` cho tới khi M4 (inpaint) chạy thật.

## 5. `GET /api/v1/pages/{page_id}/regions` → 200

```json
[ { "id": "…", "page_id": "…", "bbox": { "x": 0, "y": 0, "w": 0, "h": 0 },
    "confidence": null, "overlap_suspect": false, "reading_order": null, "status": "pending" } ]
```
Từ **M2** endpoint này trả dữ liệu thật sau khi job detect chạy xong (trước đó là `[]`, không bịa region).
Sắp xếp theo `reading_order` (NULL xuống cuối) rồi `created_at`.

- `confidence` < `CTD_CONF_THRESHOLD` → `status = "low_confidence"` (**vẫn trả về**, không bị lọc bỏ).
- 2 region chồng nhau > `CTD_OVERLAP_SUSPECT_RATIO` (so với box nhỏ hơn) → cả hai có `overlap_suspect = true`;
  hệ thống **chỉ gắn cờ**, không tự merge/xóa.
- `reading_order` là `null` cho tới khi job **translate (M5)** chạy; M5 là bước điền cột này
  (`ja` đọc phải→trái, `en`/`zh` trái→phải).

## 6. `POST /api/v1/pages/{page_id}/retry-detect` → 202 *(M2)*

Xếp lại việc detect cho 1 page (sau `detection_failed`, hoặc muốn chạy lại sau khi đổi tham số).
Tạo `Job(type=detect)` mới rồi enqueue — vẫn không chạy detect trong request.

```json
{ "page_id": "…", "status": "detected", "job_id": "…job mới…" }
```
| Lỗi | Mã |
|---|---|
| page không tồn tại | 404 |
| page đang `detecting` (tránh chạy trùng) | 409 |

Chạy lại là **idempotent**: region cũ của page bị xóa trước khi ghi region mới, không nhân đôi.

## 7. `GET /api/v1/pages/{page_id}/ocr` → 200 *(M3)*

Kết quả OCR theo từng vùng chữ của trang.

```json
[ { "region_id": "…", "raw_text": "こんにちは", "ocr_engine": "manga_ocr",
    "confidence": null, "status": "ok" } ]
```
- Trả `[]` khi job OCR chưa chạy — **không bịa text**.
- `ocr_engine`: `manga_ocr` (source_lang `ja`) hoặc `paddle_ocr` (`zh`/`en`).
- **`confidence: null` là bình thường với `manga_ocr`** — thư viện không cung cấp điểm tin cậy
  (xem ARCH.md §6). Với `paddle_ocr` đây là số thật, trung bình các dòng trong vùng.
- `status`: `ok` · `needs_manual` (text rỗng/không có ký tự có nghĩa, hoặc confidence dưới ngưỡng).
  Region `needs_manual` **vẫn được lưu**, không bị bỏ.
- Thứ tự giống `GET /pages/{id}/regions`.

## 8. `POST /api/v1/pages/{page_id}/retry-ocr` → 202 *(M3)*

Xếp lại việc OCR cho 1 page (sau khi sửa tham số, hoặc job trước lỗi). Chỉ enqueue.

| Lỗi | Mã |
|---|---|
| page không tồn tại | 404 |
| page chưa có vùng chữ nào (chưa detect) | 409 |

Chạy lại là **idempotent**: kết quả OCR cũ của đúng các region đó bị xóa trước khi ghi mới.

> Bình thường **không cần gọi tay**: detect xong hệ thống tự xếp việc OCR (`OCR_AUTO_CHAIN=true`).

## 9. `GET /api/v1/pages/{page_id}/clean-image` → 200 *(M4)*

Trả **file ảnh** đã xoá chữ gốc (`image/png`, binary).

| Lỗi | Mã |
|---|---|
| page không tồn tại | 404 |
| chưa chạy xoá chữ (chưa có `clean_image_path`) | 404 kèm lý do rõ |
| DB có đường dẫn nhưng file đã mất | 404 kèm đường dẫn để truy vết |
| `If-None-Match` khớp ETag | **304** (không gửi lại thân) |

> Ảnh **gốc không bao giờ bị thay** — ảnh clean là file riêng (`<tên gốc>_clean.png`).
> `GET /pages/{id}` vẫn trả `image_path` (gốc) và `clean_image_path` (clean) tách bạch.

**Phục vụ hiện vật (P3d).** Ba endpoint trả tệp (`clean-image`, `typeset-preview`,
`export-jobs/{id}/download`) nay đọc qua **luồng** thay vì mở tệp theo đường dẫn tuyệt đối, để
kho lưu trữ có thể không phải là hệ tệp. Kèm theo:

- `ETag` dựng từ `(kích thước, thời điểm ghi)` của hiện vật;
- gửi lại `If-None-Match` khớp ⇒ **`304 Not Modified`** (thân rỗng);
- `Content-Length` vẫn có ở mọi lượt trả 200.

Đây **không phải** tính năng thêm mà là giữ nguyên hành vi cũ: `typeset-preview` đặt
`Cache-Control: no-cache, must-revalidate`, tức trình duyệt hỏi lại server mỗi lượt xem —
không có ETag thì mỗi lượt hỏi lại là tải nguyên ~3MB thay vì một cái 304 rỗng.

⚠️ **Mất hỗ trợ `Range`** (tải tiếp đoạn giữa chừng) so với trước, vì `FileResponse` của
Starlette tự làm việc đó còn luồng thì không. Ảnh hưởng thật: tải lại từ đầu nếu đứt mạng giữa
chừng khi tải gói CBZ lớn. Chưa làm lại vì chưa ai gặp; ghi ra để không ai tưởng là lỗi.

## 10. `POST /api/v1/pages/{page_id}/retry-inpaint` → 202 *(M4)*

Xếp lại việc xoá chữ. Chỉ enqueue.

| Lỗi | Mã |
|---|---|
| page không tồn tại | 404 |
| page chưa OCR xong (không ở `ocr_done`/`inpainted`/`inpaint_needs_review`) | 409 |

Chạy lại là **idempotent**: ảnh clean cũ bị xoá trước khi ghi ảnh mới, không để file rác.

> Bình thường **không cần gọi tay**: OCR xong hệ thống tự xếp việc xoá chữ (`INPAINT_AUTO_CHAIN=true`).

## 11. `GET /api/v1/pages/{page_id}/translation` → 200 *(M5)*

```json
[ { "region_id": "…", "translated_text": "Chào buổi sáng.", "engine": "llm_context",
    "model_name": "gemini-3.1-flash-lite", "token_cost": 227,
    "edited_by_user": false, "status": "ok" } ]
```
Trả bản dịch của từng vùng chữ, **sắp theo đúng thứ tự đọc** (`reading_order` NULL xuống cuối).
Chưa dịch → `[]`, **không bịa bản dịch**.

- `status`: `ok` · `fallback_used` (LLM lỗi nên đã lùi về `google_fast`) · `pending` (model không trả
  dòng này ⇒ **chưa có bản dịch**, không phải "đã xong").
- `token_cost` là chi phí của **cả trang** (`llm_context` gọi 1 request/trang) nên chỉ ghi ở **đúng 1
  dòng đầu trang**, các dòng còn lại `null` — cộng `token_cost` toàn bảng vẫn ra tổng thật.
  `google_fast` miễn phí ⇒ luôn `null`.
- `edited_by_user` dành cho M7 (sửa tay), tới M5 luôn `false`.

## 12. `POST /api/v1/pages/{page_id}/retry-translate` → 202 *(M5)*

Xếp lại việc dịch. Query param `engine` (tuỳ chọn): `google_fast` | `llm_context`.
Không truyền → dùng `TRANSLATE_DEFAULT_ENGINE` (**mặc định `google_fast`, miễn phí** — hệ thống không
tự tiêu token khi user chưa chọn). Chỉ enqueue, không dịch trong request.

```json
{ "page_id": "…", "status": "inpainted", "job_id": "…job mới…" }
```
| Lỗi | Mã |
|---|---|
| page không tồn tại | 404 |
| page chưa xoá chữ xong (không ở `inpainted`/`inpaint_needs_review`/`translated`) | 409 |
| `engine` không thuộc 2 giá trị đã chốt | 422 |

Chạy lại là **idempotent**: bản dịch cũ của page bị xoá trước khi ghi bản mới, không nhân đôi.
`reading_order` của `TextRegion` được **điền ở bước này** (từ M1 tới M4 cột này còn NULL).

## 13. `GET /api/v1/pages/{page_id}/typeset` → 200 *(M6)*

```json
[ { "region_id": "…", "font_family": "Bangers", "font_size": 30.0,
    "wrapped_text": "Chào buổi\nsáng.", "padding_ratio": 0.09,
    "fit_status": "fit_ok", "edited_by_user": false } ]
```
Kết quả canh chữ theo từng vùng, **sắp theo đúng thứ tự đọc**. Chưa canh → `[]`.

- `fit_status`: `fit_ok` · `overflow_warning` (không vừa dù đã xuống `TYPESET_MIN_FONT_SIZE` —
  **hệ thống không co chữ nhỏ hơn min**, để M7 sửa tay) · `pending` (vùng chưa có bản dịch nên
  chưa có gì để canh; `font_size` = `null`).
- Cảnh báo tràn khung **phải đọc được ở đây** — không bị ảnh preview đẹp che mất.
- `wrapped_text` là văn bản đã chèn ký tự xuống dòng; **nội dung bản dịch không bị sửa**.
- `edited_by_user` dành cho M7, kết quả tự động của M6 luôn `false`.

## 14. `GET /api/v1/pages/{page_id}/typeset-preview` → 200 *(M6)*

Ảnh xem thử: ảnh clean của M4 + chữ dịch đã canh. Kích thước **bằng đúng ảnh clean**.
Vùng `overflow_warning` được vẽ **khung đỏ** để cảnh báo nhìn thấy được.

| Lỗi | Mã |
|---|---|
| page không tồn tại | 404 |
| chưa render preview (typeset chưa chạy xong) | 404 |
| `If-None-Match` khớp ETag | **304** (không gửi lại thân) |

Endpoint này **chỉ phục vụ file đã render sẵn** — không bao giờ tự render (việc nặng thuộc worker,
và tiến trình API không nạp engine render).

Đây là **file thứ ba**, không đụng tới `image_path` (ảnh gốc) hay `clean_image_path` (ảnh sạch):
`previews/<page_id>/typeset.png`. Đường dẫn ổn định theo page nên chạy lại là ghi đè đúng file.

## 15. `POST /api/v1/pages/{page_id}/retry-typeset` → 202 *(M6)*

Xếp lại việc canh chữ. Chỉ enqueue, không render trong request.

```json
{ "page_id": "…", "status": "translated", "job_id": "…job mới…" }
```
| Lỗi | Mã |
|---|---|
| page không tồn tại | 404 |
| page chưa dịch xong (không ở `translated`/`typeset_done`) | 409 |

Chạy lại là **idempotent**: kết quả cũ bị xoá trước khi ghi mới, preview ghi đè đúng đường dẫn cũ
(ghi ra file tạm rồi đổi chỗ nguyên tử) — không nhân bản bản ghi, không để lại file rác.

## 16. `GET /api/v1/pages/{page_id}/detail` → 200 *(M7)*

Gom **tất cả** dữ liệu của 1 trang cho màn sửa tay — 1 lần gọi thay vì 5 lần.

```json
{ "page": { "…": "như mục 4" },
  "preview_url": "/api/v1/pages/…/typeset-preview",
  "font_families": ["Bangers", "Mansalva", "ShantellSans", "…"],
  "min_font_size": 10, "max_font_size": 40,
  "regions": [ { "id": "…", "bbox": {"x":240,"y":164,"w":192,"h":85},
     "confidence": 0.91, "overlap_suspect": false, "reading_order": 1, "status": "ok",
     "raw_text": "GOOD MORNING", "ocr_confidence": null, "ocr_status": "ok",
     "translated_text": "Chào buổi sáng.", "translation_status": "ok",
     "translation_edited_by_user": false,
     "font_family": "Bangers", "font_size": 30.0, "wrapped_text": "Chào buổi\nsáng.",
     "fit_status": "fit_ok", "typeset_edited_by_user": false } ] }
```

- `preview_url` là `null` khi **file preview chưa có thật** — không trả link chết.
- `font_families` lấy từ whitelist của M6; giao diện **chỉ được chọn trong danh sách này**.
- Mọi cảnh báo đều lộ ra và không bị ẩn: `status` (`low_confidence`), `ocr_status`
  (`needs_manual`), `translation_status` (`fallback_used`), `fit_status` (`overflow_warning`).
- Hai cờ `*_edited_by_user` cho biết chỗ nào người sửa, chỗ nào máy làm.

## 17. `PATCH /api/v1/regions/{region_id}` → 200 *(M7)*

Sửa tay 1 vùng rồi **canh lại đúng vùng đó** (không tính lại cả trang).

```json
{ "translated_text": "Chào cậu nhé!", "bbox": {"x":240,"y":164,"w":192,"h":85},
  "font_family": "Mansalva", "font_size": 16 }
```
Trường nào bỏ trống thì giữ nguyên trường đó. Body rỗng → `422`.

```json
{ "region_id": "…", "page_id": "…", "fit_status": "pending",
  "refit_job_id": "…", "edited_fields": ["translated_text"], "edited_by_user": true }
```

- **`fit_status` luôn trả `pending`**, không phải trạng thái cũ: bản canh cũ đã không còn đúng với
  nội dung vừa sửa, báo `fit_ok` lúc này là nói sai. Theo dõi `refit_job_id` để biết khi nào xong.
- **`font_size` = ghim cỡ chữ**: canh lại dùng **đúng** cỡ đó thay vì tự dò. Cỡ đó tràn khung thì
  vẫn giữ cỡ nhưng gắn `overflow_warning` — không giả vờ vừa. Bỏ trống = quay lại tự dò như M6.
- Ghi `edited_by_user=true` lên bản dịch và/hoặc kết quả canh chữ tương ứng.
- **Không đụng** `raw_text` của M3 và không đụng ảnh gốc/ảnh clean.

| Lỗi | Mã |
|---|---|
| vùng không tồn tại | 404 |
| không có trường nào để sửa / bbox rộng-cao ≤ 0 / trường lạ | 422 |
| `font_family` ngoài whitelist (`font_not_found`) | 422 |
| sửa bản dịch khi vùng chưa từng được dịch | 409 |

## 18. `POST /api/v1/regions/{region_id}/re-fit` → 202 *(M7)*

Canh lại 1 vùng mà không sửa gì (dùng khi đổi cấu hình font/padding).
Query `font_size` (tuỳ chọn) để ghim cỡ.

## 19. `POST /api/v1/regions/{region_id}/re-ocr` → 202 *(M7)*

Đọc lại chữ gốc của 1 vùng từ **ảnh gốc** (ảnh clean đã bị xoá chữ nên không dùng được).
**Không** tự dịch lại và **không** tự canh lại — vì cả hai đều ghi đè, có thể xoá mất phần người
dùng vừa sửa tay.

## 20. `POST /api/v1/regions/{region_id}/re-translate` → 202 *(M7)*

Dịch lại 1 vùng từ chữ gốc hiện tại. Query `engine` (tuỳ chọn): `google_fast` | `llm_context`.
**Ghi đè bản dịch**, kể cả bản đã sửa tay. Lưu ý: dịch lại một dòng lẻ thì `llm_context` mất lợi
thế ngữ cảnh cả trang.

Cả ba endpoint trên trả `{ "job_id": "…", "page_id": "…", "status": "queued" }`, `404` nếu vùng
không tồn tại, và **không bao giờ chạy đồng bộ trong request**.

## 21. `GET /api/v1/projects/{project_id}/export-preview` → 200 *(M8)*

Xem trước **trước khi** xuất, để quyết định xuất luôn hay quay lại sửa tay.

```json
{ "page_count": 4, "total_page_count": 5, "skipped_page_count": 1, "overflow_warning_count": 2 }
```
- `skipped_page_count`: trang chưa canh chữ xong sẽ **bị bỏ qua**, không xuất ảnh chưa có chữ.
- `overflow_warning_count`: vùng còn tràn khung. **Không chặn** xuất, nhưng phải hiện rõ ở đây.

## 22. `POST /api/v1/projects/{project_id}/export` → 202 *(M8)*

```json
{ "format": "cbz" }
```
`format`: `cbz` (1 file, ứng dụng đọc truyện mở được) · `zip` (giống cbz, đuôi `.zip`) ·
`png_single` (mỗi trang 1 ảnh trong một thư mục).

```json
{ "job_id": "…", "project_id": "…", "status": "queued" }
```
Chỉ enqueue — render nhiều trang là việc của worker. `404` nếu project không tồn tại,
`422` nếu `format` lạ hoặc body có trường lạ.

## 23. `GET /api/v1/export-jobs/{job_id}` → 200 *(M8)*

```json
{ "id": "…", "project_id": "…", "format": "cbz", "status": "done",
  "output_path": "exports/<project_id>/truyen_hay_chapter.cbz",
  "page_count": 4, "overflow_warning_count": 2,
  "error_log": "overflow_warning: 2 vùng còn tràn khung",
  "created_at": "…", "updated_at": "…" }
```
`status` đi `queued → running → done | failed`.

**`status=done` mà `error_log` khác `null` nghĩa là xuất được NHƯNG có cảnh báo** — đọc kỹ trước khi
giao file. Hai loại cảnh báo: `skipped_pages` (bỏ qua trang chưa canh chữ) và `overflow_warning`.
Không trang nào xuất được ⇒ `failed` với `no_page_ready`.

## 24. `GET /api/v1/export-jobs/{job_id}/download` → 200 *(M8)*

Tải file đã xuất. **Chỉ phục vụ file có sẵn** — không bao giờ tự render ở đây.

| Lỗi | Mã |
|---|---|
| job không tồn tại | 404 |
| chưa xuất xong, hoặc file không còn trên đĩa | 404 |
| `format=png_single` (nhiều file trong 1 thư mục, không tải một lần được) | 409 kèm hướng dẫn dùng `cbz`/`zip` |
| `If-None-Match` khớp ETag | **304** (không gửi lại thân) |

## 25. `GET /api/v1/jobs/{job_id}` → 200

```json
{ "id": "…", "type": "detect", "page_id": "…", "status": "queued",
  "retry_count": 0, "error_log": null, "created_at": "…", "updated_at": "…" }
```
Dùng chung cho mọi loại job xuyên suốt Phase. Không tồn tại → `404`.
Job detect/ocr/inpaint/translate/typeset: `status` đi `queued → running → done | failed`; khi `failed`, `error_log` ghi
nguyên nhân (`timeout: vượt Ns`, `FileNotFoundError: …`, `enqueue_failed: …`, `no_region: …`,
`precondition_failed: …`, `missing_ocr: …`).

Khi job OCR lỗi, `Page.status` **giữ nguyên `detected`** (không nhảy `ocr_done`) để còn chạy lại được.
Khi job inpaint lỗi, `Page.status` giữ nguyên `ocr_done` và `clean_image_path` **không** được ghi.
Khi job translate lỗi, `Page.status` giữ nguyên `inpainted` để còn chạy lại được.
Khi job typeset lỗi (thiếu font, timeout…), `Page.status` giữ nguyên `translated` và **không có preview
nửa vời** — ảnh chỉ được đổi chỗ sau khi vẽ xong.
Job translate lùi về `google_fast` vẫn là `done`, nhưng `error_log` ghi `fallback_used: <lý do gốc>`
và mọi dòng của trang mang `status=fallback_used` — thành công **có dán nhãn**, không im lặng.

`Page.status` sau khi xoá chữ: `inpainted` (OCR lại vùng đã xoá không còn chữ) hoặc
`inpaint_needs_review` (còn đọc ra chữ ⇒ xoá chưa sạch, cần xem lại).

## 26. `POST /api/v1/projects/{project_id}/batch-runs` → 202 *(M9)*

Chạy **cả chapter** bằng một mẻ theo dõi được.

```json
{ "requested_pipeline": "full_pipeline", "translation_engine": "google_fast" }
```
→ `202 { "batch_run_id": "…", "status": "queued", "total_pages": 3 }`

- Danh sách trang được **chụp lại ngay lúc tạo** theo `Page.order`. Trang tải lên sau đó **không**
  lẫn vào mẻ đang chạy — tổng số trang không nhảy giữa chừng.
- `translation_engine` cũng được **chốt lúc tạo**; đổi cấu hình giữa chừng không làm các trang
  trong cùng một mẻ dịch bằng hai engine khác nhau.
- Mỗi trang tiếp tục **từ đúng bước nó đang đứng** (`queued`→detect, `detected`→ocr,
  `ocr_done`→inpaint, `inpainted`/`inpaint_needs_review`→translate, `translated`→typeset).
  Trang đã `typeset_done`/`ready_for_export` được đánh `skipped`, **không** chạy lại (chạy lại là
  xoá mất kết quả đã có).
- `requested_pipeline=retry_failed`: chỉ lấy các trang **chưa** xong.

| Lỗi | Mã |
|---|---|
| project không tồn tại | 404 |
| project chưa có trang nào (`no_page`) | 422 |
| `retry_failed` mà mọi trang đã xong (`no_page_to_retry`) | 422 |
| chọn `llm_context` khi chưa cấu hình khoá dịch (`llm_not_configured`) | 422 — chặn **trước** khi xếp việc |

## 27. `GET /api/v1/batch-runs/{batch_run_id}` → 200 *(M9)*

```json
{ "id": "…", "project_id": "…", "requested_pipeline": "full_pipeline",
  "translation_engine": "google_fast", "status": "running",
  "total_pages": 3, "completed_pages": 1, "failed_pages": 0, "blocked_pages": 0,
  "started_at": "…", "finished_at": null, "error_summary": null, "created_at": "…", "updated_at": "…" }
```

`status` **luôn được suy ra từ các `BatchItem`**, không bao giờ đặt tay:

| Tình trạng các mục | `status` |
|---|---|
| còn mục `pending`/`running` | `running` (kể cả khi đã có mục hỏng) |
| tất cả xong/bỏ qua | `completed` |
| có xong + có hỏng | `partial_failed` |
| phần chưa xong đều kẹt quota | `blocked_quota` |
| hỏng sạch | `failed` |
| bị dừng tay | `cancelled` |

Không tồn tại → `404`.

## 28. `GET /api/v1/batch-runs/{batch_run_id}/items` → 200 *(M9)*

`?status=&limit=&cursor=` — lọc theo trạng thái mục, sắp theo `page_order` đã chụp lúc tạo mẻ.

```json
{ "items": [ { "id": "…", "page_id": "…", "page_order": 1, "status": "completed",
               "current_job_id": "…", "retry_count": 0, "error_code": null,
               "error_message": null, "started_at": "…", "finished_at": "…" } ],
  "next_cursor": null }
```

`error_message` **đã lọc** thứ trông giống khoá bí mật (`AIza…`, `Bearer …`) và cắt còn 2000 ký tự.
`error_code` là loại lỗi đã phân: `quota_exhausted`, `transient_rate_limit`, `transient_provider`,
`transient_network`, `transient_broker`, `permanent_input`, `permanent_config`, `permanent_model`,
`unknown`, `stale_reclaimed`, `stale_page`, `da_xong`, `dang_chay`, `cancelled`.

## 29. `POST /api/v1/batch-runs/{batch_run_id}/resume` → 202 *(M9)*

```json
{ "item_ids": ["…"] }        // bỏ trống = chạy lại MỌI mục failed/blocked_quota
```
→ `202 { "batch_run_id": "…", "resumed_count": 2, "status": "running" }`

- **Chỉ** nhận mục `failed`/`blocked_quota`. Mục đã `completed` giữ nguyên kết quả, không bị chạy lại.
- Chọn nhầm mục `completed` hoặc mục của mẻ khác → **422**, không im lặng bỏ qua (im lặng bỏ qua
  khiến người dùng tưởng đã chạy lại).
- Gọi không kèm `item_ids` còn **thu hồi** các mục kẹt `running` quá lâu vì worker chết.

| Lỗi | Mã |
|---|---|
| mẻ không tồn tại | 404 |
| `item_not_in_batch` / `item_not_resumable` | 422 |

## 30. `POST /api/v1/batch-runs/{batch_run_id}/cancel` → 202 *(M9)*

Trả về **cả đối tượng mẻ** (dạng như §27) với `status="cancelled"` — rộng hơn hợp đồng tối thiểu
`{batch_run_id, status}` của mini-spec, không thiếu trường nào.

Dừng **đẩy việc mới**; việc đang chạy **được chạy nốt** — cắt ngang giữa chừng dễ để lại kết quả
dở dang. Mục còn `pending` chuyển `skipped` với `error_code=cancelled`.

Không tồn tại → `404`.

## 31. `GET /api/v1/batch-config` → 200 *(M9 — thêm ngoài hợp đồng mini-spec)*

```json
{ "llm_configured": false, "llm_project_rpm": 10, "batch_max_concurrent_pages": 1,
  "batch_max_retries": 3, "batch_retry_backoff_base_seconds": 2.0,
  "batch_retry_backoff_max_seconds": 120.0 }
```

Vì sao cần: §4D của mini-spec buộc giao diện phải **tắt lựa chọn LLM kèm lý do rõ** khi chưa cấu
hình. Không có endpoint này thì giao diện phải đoán — hoặc để người dùng bấm rồi nhận 422.
`llm_configured` **chỉ là true/false**; không có khoá, không có tên khoá, không có độ dài khoá.

## 32. `GET /api/v1/projects/{project_id}/batch-runs` → 200 *(M9 — thêm ngoài hợp đồng mini-spec)*

`?limit=` (mặc định 10) → `{ "runs": [ …như §27…, mới nhất trước ] }`

Vì sao cần: không có nó thì giao diện phải tự nhớ mã mẻ trong trình duyệt — tải lại trang là mất
dấu mẻ đang chạy và người vận hành không còn cách nào nhìn thấy tiến độ.

Project không tồn tại → `404`.

## 33. `GET /api/v1/projects/{project_id}/export-warnings` → 200 *(M10)*

Những gì người dùng **phải nhìn thấy trước** khi mang file đi.

```json
{ "overflow_warning_count": 1, "needs_manual_count": 2,
  "acknowledged": true, "acknowledged_at": "2026-08-28T16:30:23.592881Z" }
```

- Chỉ đếm trên các trang **sẽ được xuất** (`typeset_done`/`ready_for_export`). Vùng lỗi ở trang
  chưa chèn chữ xong không nằm trong file giao đi — đếm vào chỉ làm người dùng bỏ qua cả cảnh
  báo thật.
- `overflow_warning_count`: chữ dịch **tràn ra ngoài** bong bóng.
- `needs_manual_count`: vùng **chưa đọc được chữ gốc** ⇒ bong bóng đó sẽ **trống** trong file xuất.
- `acknowledged`: chapter này đã xác nhận trách nhiệm bản quyền lần nào chưa — để giao diện hiện
  nhắc **một lần**, không lải nhải mỗi lần xuất.

Project không tồn tại → `404`.

## 34. `POST /api/v1/export-jobs/{job_id}/acknowledge` → 200 *(M10)*

```json
{ "user_acknowledged": true }
```
→ `200` bản ghi tuân thủ: `{id, project_id, export_job_id, intended_use,
overflow_warning_count, needs_manual_count, user_acknowledged, acknowledged_at}`

- **Không chặn xuất.** Đây là công cụ cá nhân; chặn cứng chỉ khiến người ta đi đường vòng mà
  chẳng bảo vệ được ai. Cổng chặn nằm ở **giao diện** (nút xuất mờ tới khi tick); máy chủ **ghi
  nhận**, không cấm.
- Số cảnh báo được **đếm lại tại máy chủ**, không nhận từ máy khách gửi lên — số do trình duyệt
  gửi thì không còn là bằng chứng. Gửi kèm trường lạ → `422`.
- `user_acknowledged=false` **vẫn được ghi** (có người mở cảnh báo rồi bỏ đi cũng là sự thật đáng
  lưu), nhưng `acknowledged_at` để `null` và chapter **không** được coi là đã xác nhận.
- Việc xuất không tồn tại → `404`.

## 35. `GET /api/v1/pages/{page_id}/quality` → 200 *(E12)*

Đánh giá chất lượng từng vùng của một trang, sắp theo thứ tự đọc.

```json
{ "page_id": "…", "assessment_version": "e12-rules-v1",
  "summary": { "tong_vung": 4, "ro_rang": 2, "can_ra_soat": 2, "chua_danh_gia": 0,
               "da_bo_qua": 0, "vung_tran_khung": 0,
               "theo_phan_loai": { "likely_translatable": 2, "uncertain": 2 } },
  "regions": [ { "region_id": "…", "reading_order": 3,
                 "relevance": "uncertain", "review_status": "needs_review",
                 "overall_band": "attention",
                 "detector_confidence_state": "available",
                 "ocr_confidence_state": "unavailable",
                 "translation_state": "missing",
                 "ly_do": [ { "ma": "ocr_empty",
                              "nhan": "OCR không đọc được nội dung nào." } ],
                 "evidence_snapshot": { "so_ky_tu_goc": 0, "ty_le_dien_tich": 0.00566 },
                 "assessed_at": "…" } ] }
```

- Mỗi lý do luôn có **cả mã lẫn câu tiếng Việt** — mã để đếm, câu để đọc.
- `chua_danh_gia` đếm riêng, **không** gộp vào `ro_rang`: chưa chấm khác với chấm sạch.
- `ocr_confidence_state: "unavailable"` nghĩa là engine **không cung cấp** điểm (manga-ocr),
  **không** phải điểm 0.
- Trang không tồn tại → `404`.

## 36. `GET /api/v1/projects/{project_id}/quality-summary` → 200 *(E12)*

Cùng cấu trúc `summary` của §35, gộp cho cả chapter. Dùng ở màn chapter và hộp thoại xuất.
Project không tồn tại → `404`.

## 37. `POST /api/v1/regions/{region_id}/quality-review` → 200 *(E12)*

```json
{ "decision": "keep" }     // hoặc "skip"
```
→ `200 { region_id, review_status, relevance, overall_band }`

- Chỉ nhận đúng hai giá trị. Gửi kèm `overall_band`/`reason_codes`/`evidence` → **422**:
  mức và lý do là kết luận của bộ luật, máy khách không được tự đặt.
- `skip` là **quyết định**, không phải xoá: `TextRegion`, `OCRResult`, `TranslationResult`,
  `TypesetResult` giữ nguyên. Có test canh đúng điều này.
- Vùng chưa được chấm → **409** kèm hướng dẫn chạy lại bước căn chữ (không tự tạo đánh giá rỗng).

`GET /projects/{id}/export-warnings` (§33) **thêm 3 trường**, giữ nguyên các trường cũ:
`quality_needs_review_count`, `quality_unassessed_count`, `quality_reviewed_skip_count`.
Ba số này để **riêng** khỏi phần bản quyền của M10 — trộn vào nhau sẽ khiến người dùng tưởng
tick một ô là xong cả hai chuyện.

## Bảng enum (chốt ở M1, M2–M10 không đổi âm thầm)

| Enum | Giá trị |
|---|---|
| `source_lang` | ja, zh, en |
| `target_lang` | vi |
| `intended_use` | personal, study, other |
| `project_status` | active, archived |
| `page_status` | queued, detecting, detected, detection_failed, ocr_done, inpainted, inpaint_needs_review, translated, typeset_done, ready_for_export |
| `region_status` | pending, low_confidence, confirmed |
| `ocr_engine` | manga_ocr, paddle_ocr |
| `ocr_status` | pending, ok, needs_manual |
| `translation_engine` | google_fast, llm_context |
| `translation_status` | pending, ok, fallback_used |
| `fit_status` | pending, fit_ok, overflow_warning |
| `job_type` | detect, ocr, inpaint, translate, typeset, export |
| `export_format` | png_single, cbz, zip |
| `job_status` | queued, running, done, failed |
| `batch_pipeline` *(M9)* | full_pipeline, retry_failed |
| `batch_status` *(M9)* | queued, running, completed, partial_failed, blocked_quota, failed, cancelled |
| `batch_item_status` *(M9)* | pending, running, completed, failed, blocked_quota, skipped |
| `region_relevance` *(E12)* | likely_translatable, possible_sfx, possible_number_or_decoration, uncertain |
| `review_status` *(E12)* | not_required, needs_review, reviewed_keep, reviewed_skip |
| `overall_band` *(E12)* | clear, attention, blocked |
| `confidence_state` *(E12)* | available, low, unavailable |
| `translation_state` *(E12)* | present, missing, fallback_used, not_attempted |

## Endpoint sẽ thêm ở mini-spec sau (chưa tồn tại)

M8 và M9 đã xong — xem §21–24 (xuất chapter) và §26–32 (chạy cả mẻ).

Tên endpoint mẻ **khác** phác thảo cũ (`run-batch` / `batch-status`): mẻ là một **tài nguyên** có
mã riêng, chạy lại và dừng được, nên đặt theo lối tài nguyên `batch-runs/{id}` thay vì hai động từ
rời. Lý do đầy đủ: `docs/REPORT_M9.md` §Design Choice.

M10 đã xong — xem §33–34. `POST /projects` (§1) **bắt buộc** `intended_use`, không có giá trị
mặc định; thiếu hoặc sai giá trị → `422`. Không có endpoint nào sửa `intended_use` sau khi tạo:
khai báo sửa được thì bằng chứng vô nghĩa.

M11 (nếu cần) — auth & nhiều người dùng: chưa có endpoint nào.


## E14 — vùng an toàn theo hình bong bóng

| Method | Path | Ghi chú |
|---|---|---|
| GET | `/api/v1/regions/{region_id}/safe-area` | Hình học + mã lý do + ô đặt chữ. **404 nếu chưa tính** — không trả hình rỗng để khỏi bị đọc nhầm thành "vừa khít" |
| GET | `/api/v1/pages/{page_id}/safe-area-summary` | Đếm theo trạng thái; `not_computed_count` để RIÊNG |
| POST | `/api/v1/pages/{page_id}/retry-safe-area` | 202 — xoá bản cũ rồi xếp lại việc căn chữ (bước này tự tính lại vùng nào thiếu) |

`export-warnings` thêm hai số **tách riêng** khỏi tràn khung và khỏi chất lượng E12:
`shape_fallback_count`, `shape_needs_review_count`.

Tầng HTTP **không** chạm xử lý ảnh: ô đặt chữ được worker tính sẵn và lưu vào bản ghi.


## E15 — hướng chữ

| Method | Path | Ghi chú |
|---|---|---|
| GET | `/api/v1/regions/{region_id}/orientation` | Hướng + nguồn + mã lý do + bằng chứng. **404 nếu chưa phân tích** |
| GET | `/api/v1/pages/{page_id}/orientation-summary` | Đếm theo hướng; `not_analyzed_count` để RIÊNG |
| POST | `/api/v1/pages/{page_id}/retry-orientation` | 202 — xoá kết quả cũ rồi xếp lại việc căn chữ |

`export-warnings` thêm ba số, **tách riêng** khỏi tràn khung, bố cục E14, chất lượng E12 và
nhất quán E13: `orientation_vertical_rendered_count`, `orientation_review_count`,
`orientation_unknown_count`.

`OCRResult` thêm `line_polygons` (JSONB, toạ độ ảnh gốc): `null` = engine không cung cấp,
`[]` = có hỏi nhưng không có dòng nào. Hai thứ đó **khác nhau** và không được gộp.

**Không** có endpoint nào cho phép người dùng tự đặt hướng chữ — ngoài phạm vi E15 v1.


---

## E1 — Tiện ích Chrome: KHÔNG có endpoint mới

E1 **không thêm, không sửa, không bỏ** một endpoint nào. Nó chỉ tiêu thụ hai đường đã có:

| Dùng để | Endpoint | Ghi chú |
|---|---|---|
| Kiểm máy chủ sống chưa | `GET /api/v1/health` | đã có sẵn, `include_in_schema=False`, có kiểm CSDL |
| Lấy chi tiết + tiến độ chapter | `GET /api/v1/projects/{project_id}` | `ProjectDetail` |

Tiện ích **chỉ đọc**: không `POST`, không `PATCH`, không upload. Mọi lượt ghi vẫn đi qua giao diện
web app như cũ, nên các cổng chặn của M10 (khai báo mục đích) và M8 (điều kiện xuất) không có
đường nào bị đi vòng.

**Không dùng `/healthz`.** Đo ngày 2026-08-30: `/healthz` ở cổng **giao diện** trả về trang HTML
của SPA kèm `200` và `Access-Control-Allow-Origin: *` — tức "200 OK" ngay cả khi API đã chết. Chỉ
các đường `/api/v1/*` mới thật sự đi xuống backend qua proxy.

**Không có `/api/v1/extension/*`.** Backend hiện **không** có endpoint liệt kê project
(`GET /api/v1/projects` → 405 Method Not Allowed). Tiện ích chấp nhận giới hạn đó (người dùng ghim
chapter bằng mã) thay vì đẻ ra một mặt API riêng cho tiện ích. Nếu muốn bỏ bước ghim tay thì đó là
một mini-spec backend riêng: `GET /api/v1/projects` chỉ-đọc, có phân trang.
