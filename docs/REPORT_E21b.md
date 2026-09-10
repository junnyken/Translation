# Báo cáo Mini-Spec E21b — Rà soát tay: chặn mất chữ đang gõ + bỏ việc canh lại thừa

**Project:** Translation · **Phase:** E — Hosted Reliability Hardening (OCR Quality Recovery)
**Ngày:** 2026-09-10 · **Nền:** `e5dec68` (sau E22 + phụ lục E20b)
**Trạng thái:** PARTIAL — build xong, test xanh, kiểm trình duyệt trên stack local; **chưa deploy**.

## 1. Summary

Bản nháp E21b đề nghị: hàng đợi review với `review_state`/`reviewed_at`, xếp ưu tiên theo điểm tin
cậy OCR, khung boundary riêng cho người rà soát, phím tắt scoped, chặn mất dữ liệu.

**Audit trước khi build bác bỏ hai phần ba đề bài** (§2): trạng thái review tường minh đã có đủ từ
E12, và xếp ưu tiên theo confidence là bất khả thi cho nguồn tiếng Nhật. Nhưng audit lộ ra **hai
lỗi thật chưa ai biết**, và đó là thứ E21b thực sự làm:

1. **Chữ đang gõ dở mất im lặng** khi đổi vùng — lỗi nằm trong đúng luồng mà E21 sinh ra để phục vụ.
2. **Sửa `raw_text` kéo theo một việc canh lại vô ích** — chiếm suất của worker `--pool=solo` và
   hạ nhầm `fit_status` từ `fit_ok` xuống `pending`.

Cộng thêm điều hướng Trước/Sau và bộ lọc theo trạng thái rà soát, cả hai **tái dùng** hạ tầng có
sẵn chứ không dựng mới.

Người dùng chọn phạm vi này sau khi xem audit ("Sửa 2 lỗi + điều hướng vùng").

**Backend 1193 passed / 6 skipped / 0 failed · frontend 331 passed.** Không migration.

## 2. Audit Before Build

| Hạng mục bản nháp đề nghị | Kết quả audit |
|---|---|
| `review_state` + `reviewed_at` + nút đánh dấu đã rà soát | **ĐÃ CÓ ĐỦ từ E12.** `ReviewStatus` đúng 4 giá trị `not_required/needs_review/reviewed_keep/reviewed_skip` (`enums.py`), bảng `region_quality_assessment`, endpoint `POST /regions/{id}/quality-review`, UI hai nút "Giữ để dịch"/"Bỏ qua vùng này". Docstring còn ghi sẵn nguyên tắc bản nháp nhấn mạnh: `reviewed_skip` CHỈ do người bấm. |
| Đếm + lý do ưu tiên trong hàng đợi | **ĐÃ CÓ** — `QualityPanel` + `GET /projects/{id}/quality-summary`, lý do dạng câu tiếng Việt. |
| Xếp ưu tiên theo điểm tin cậy OCR | **BẤT KHẢ THI cho tiếng Nhật.** `manga_ocr` trả `None`, code ghi thẳng "không bịa số" (`engines.py`); chỉ PaddleOCR (en/zh) có số thật. UI đã nói "Engine OCR không cung cấp điểm tin cậy". |
| Thứ tự đọc ổn định | **ĐÃ CÓ** — `TextRegion.reading_order`, deterministic. Lưu ý: sửa bbox tay **không** tính lại nó. |
| Danh sách vùng bấm-nhảy + filter theo trạng thái rà soát | **THIẾU** — danh sách chỉ lọc theo hướng chữ (E15); nút "Rà soát N vùng" nhảy về trang đầu, không tới vùng cụ thể. |
| Nút Trước/Sau giữa các vùng | **THIẾU** |
| Phím tắt scoped | **THIẾU hoàn toàn** — toàn repo chỉ có Escape đóng modal. |
| Chặn mất thay đổi chưa lưu | **THIẾU — và là LỖI**, xem §2.1. |
| Boundary override tách khỏi detector | **CHƯA CÓ tách.** Sửa bbox tay đã có (kéo chuột) nhưng **ghi đè thẳng** toạ độ detector, không cột nào giữ nguồn gốc. |

### 2.1 Lỗi 1 — mất dữ liệu im lặng

`App` gắn `key={region.id}` cho `RegionPanel` ⇒ đổi vùng là **remount**, state form bị vứt.
`RegionPanel` có cờ `daDoi` nhưng chỉ dùng để bật/tắt nút Lưu. Không `beforeunload`, không confirm.

### 2.2 Lỗi 2 — bản nháp khẳng định sai về hiện trạng

Bản nháp ghi "no background task enqueue" như một invariant đang có. Thực tế `PATCH /regions/{id}`
xếp `Job(type=typeset)` ở cuối **không điều kiện** (`routes.py`), kèm đặt `fit_status=pending` và
`edited_by_user=True` lên tầng typeset — kể cả lượt chỉ sửa `raw_text`.

E21 chỉ chứng minh "không tự **dịch** lại" (test có assert bản dịch không đổi), chưa bao giờ soi
job typeset. Nên đây là tác dụng phụ lọt lưới, không phải quyết định có chủ đích.

## 3. Design Choice

**Tái dùng `ReviewStatus` của E12, không dựng nguồn sự thật thứ hai.** Bộ lọc `LOC_RA_SOAT` đọc
thẳng `review_status`, đặt cạnh `LOC_HUONG_CHU` trong `lib/status-presentation.js` cho đồng bộ.
Hai hàng lọc đứng **riêng** vì trả lời hai câu hỏi khác nhau.

**Các ô lọc phải phủ kín miền giá trị.** Bản đầu thiếu `not_required` ⇒ "Tất cả 2" mà mọi ô con
đều 0. Nay 5 ô phủ kín + test canh.

**Báo cờ lên, không lôi state lên.** `RegionPanel` báo `daDoi` qua `onDoiTrangThaiSua` và để lại
hàm `luu` mới nhất trong ref `dieuKhien` — cập nhật sau MỌI lần render (không mảng phụ thuộc),
nếu không App sẽ lưu bản state cũ. Cách này tránh phải nhấc toàn bộ form lên App.

**Không tự lưu hộ.** Hộp thoại ba lựa chọn: *Lưu rồi chuyển · Bỏ thay đổi · Ở lại vùng này*. Lưu
ngầm thứ người dùng chưa xác nhận cũng là một kiểu mất kiểm soát.

**Điều kiện canh lại theo TRƯỜNG, không theo tên trường đặc biệt.** Canh lại ⟺ lượt sửa đụng
`bbox`/`translated_text`/`font_family`/`font_size`. Ca gộp (`raw_text` + `translated_text`) vẫn
canh lại.

## 4. Cố tình KHÔNG làm

| Không làm | Vì sao |
|---|---|
| `review_state`/`reviewed_at`/`reviewed_by` | Trùng `ReviewStatus` của E12 — audit §2 |
| Xếp ưu tiên theo confidence | `manga_ocr` trả `None`; dùng nó là im lặng vô hiệu với truyện Nhật |
| Phím tắt scoped | Ứng dụng chưa có phím tắt nào; thêm một hệ phím tắt cần audit xung đột trình duyệt/trợ năng riêng |
| Tách provenance cho bbox | Cần migration + quyết định về hành vi pipeline; không nhét vào lát cắt sửa lỗi |
| Bảng/endpoint review mới | Không có gì để thêm mà E12 chưa có |

## 5. Changed Files

**Backend:** `app/api/v1/routes.py` (điều kiện canh lại trong `patch_region`, docstring),
`app/schemas/common.py` (`RegionPatchAccepted.refit_job_id` nullable),
`tests/test_region_edit_integration.py` (+4 test).

**Frontend:** `src/App.jsx` (chặn mất dữ liệu, hộp thoại, Trước/Sau, lọc rà soát, bỏ chờ job khi
`refit_job_id=null`), `src/components/RegionPanel.jsx` (báo cờ + `dieuKhien`),
`src/lib/status-presentation.js` (`LOC_RA_SOAT`), `src/styles.css`,
`src/components/RegionPanel.test.jsx` (+6), `src/lib/status-presentation.test.js` (+3).

**Docs:** `API.md` (mục 17), `ARCH.md` (§E21b), `FEATURES.md`, `TEST_LOG.md`, báo cáo này.

## 6. New API / DB / State

**DB:** không đổi, không migration.

**API:** `PATCH /api/v1/regions/{region_id}` — `refit_job_id` giờ có thể là `null` (lượt sửa chỉ
đụng `raw_text`), và `fit_status` khi đó trả giá trị THẬT thay vì `pending`. Đây là **nới lỏng
kiểu dữ liệu của response**: máy khách phải kiểm `null` trước khi hỏi `/jobs/{id}`. Frontend trong
repo đã được sửa; máy khách ngoài repo (nếu có) cần biết điều này.

**Không đổi:** detector geometry, kết quả pipeline, `ReviewStatus`, hành vi M7 refit, E15, E22.

## 7. Tests

```
$ cd backend && ../.venv/bin/python -m pytest -q
1193 passed · 6 skipped · 0 failed    (1199 thu thập = 1195 nền E22 + 4 mới)

$ cd frontend && npm test -- --run
331 passed (20 file)                   (322 nền E22 + 9 mới)
```

Chi tiết từng test + một báo động giả đáng ghi lại (lệnh nền báo "failed" nhưng mã 1 đến từ
`grep -c` đếm được 0 lỗi) ở `TEST_LOG.md` mục E21b.

## 8. Live Verification — Chromium thật, stack local

**KHÔNG chạm production.** Trang fixture `e3b458c7…` (2 vùng) có sẵn trong DB local; đặt lại mật
khẩu tài khoản fixture **chỉ trên DB local** bằng đúng hàm băm scrypt của server.

- Gõ dở chữ gốc → bấm sang vùng khác ⇒ hộp thoại chặn, chữ **còn nguyên**, vẫn ở Vùng 1, "1 / 2".
- "Ở lại vùng này" giữ nguyên chữ; "Bỏ thay đổi" mới chuyển và bỏ.
- Trước/Sau đúng cả hai biên (ở 1/2 tắt "Trước", ở 2/2 tắt "Sau").
- Console 0 lỗi JS.

**Lỗi bắt được nhờ bấm thật:** bộ lọc thiếu ô `not_required` ⇒ "Tất cả 2" mà mọi ô con đều 0. Không
bộ test nào bắt được vì `App.jsx` không có unit test. Đã sửa + thêm test canh tính phủ kín.

## 9. Success Criteria

| Tiêu chí | Đạt? |
|---|---|
| Audit xác nhận vòng đời E21 và khoảng trống thật; báo trùng lặp thay vì làm lại | ✅ §2 |
| Sửa chữ gốc KHÔNG kéo theo OCR/dịch/canh chữ/xuất/job nào | ✅ test `test_sua_raw_text_KHONG_xep_viec_canh_lai` |
| Thay đổi chưa lưu không mất im lặng | ✅ §8, hộp thoại + `beforeunload` |
| Lọc/chọn vùng theo thứ tự ổn định, lý do chỉ từ bằng chứng có thật | ✅ tái dùng `reading_order` + `ReviewStatus`, không bịa confidence |
| Trạng thái "đã rà soát" không bị coi là "OCR đúng" | ✅ giữ nguyên wording E12, không đụng |
| Không đổi detector geometry / kết quả pipeline | ✅ §6 |
| Toàn bộ test xanh | ✅ §7 |
| Live verification không side effect pipeline | ✅ §8 (local, không production) |
| Docs phản ánh đúng thực tế và giới hạn | ✅ §10 |

Chưa đạt (cố ý ngoài phạm vi đã chọn): phím tắt, boundary provenance.

## 10. Remaining Limits

- **`App.jsx` không có unit test nào** (tình trạng có từ trước E21b). Wiring hộp thoại/điều
  hướng/lọc dựa hoàn toàn vào lượt kiểm trình duyệt ở §8. Cơ chế cốt lõi thì có test.
- Hộp thoại chặn khi đổi vùng và khi đóng tab/tải lại. **Chưa chặn** đường đổi trang hoặc đổi bộ
  lọc làm vùng đang mở rơi khỏi danh sách.
- Sửa bbox vẫn ghi đè toạ độ detector, không có provenance — nguyên trạng, ngoài phạm vi.
- Rà soát tay vẫn là việc của người; E21b **không** làm OCR chính xác hơn.
- "Đã quyết" chỉ có nghĩa người dùng đã bấm, **không** có nghĩa OCR đúng.
- Vision LLM vẫn chưa đánh giá — cần mini-spec riêng.

## 11. Commit / Deploy State

- **Chưa commit, chưa push, chưa deploy** tại thời điểm viết báo cáo.
- Deploy cần duyệt riêng vì có **đổi hợp đồng API** (`refit_job_id` nullable): backend phải lên
  trước hoặc cùng lúc frontend, nếu không frontend cũ sẽ hỏi `/jobs/null` khi người dùng sửa
  `raw_text`.
- Không có migration ⇒ rollback là quay lại commit trước, không cần đụng CSDL.
