# REPORT — Mini-Spec P0-P1

**Ngày:** 2026-09-24 · **Mini-Spec:** Decision Lock & Trust-Gap Remediation
**Trạng thái:** Phase 0 ĐÓNG · Phase 1 code xong, **chưa deploy**

---

## 1. Summary

**Phase 0** chốt **Hướng A**: đường "Dịch nhanh" hiện một dòng cảnh báo sau khi file đã tải về,
**không** chặn tải, **không** thêm nút bấm. Văn bản quyết định: `docs/DECISION_LOG_P0.md`.

**Phase 1** làm hai việc:

1. Đường nhanh hiện số vùng chữ nên xem lại — **dùng lại endpoint cảnh báo xuất đã có**, không
   dựng phép đếm mới.
2. `token_cost` hiện ở hai chỗ: cạnh từng vùng ở màn rà soát, và tổng cả chapter ở màn tóm tắt
   trước khi xuất.

> **Mini-Spec sai 4 tiền đề.** Audit phát hiện trước khi code, và chúng **đổi hẳn phạm vi** —
> chi tiết ở §3. Phần lớn công việc Mini-Spec mô tả **đã tồn tại sẵn** trong hệ thống.

---

## 2. Phase 0 Decision Log

| | |
|---|---|
| Ngày | 2026-09-24 |
| Hướng chọn | **A** — giữ "không tick hộ", chỉ thêm thông tin |
| Người quyết định | Nguyễn Thiên Triều (`trieunt@matbao.com`) |

Nguyên văn đầy đủ ở `docs/DECISION_LOG_P0.md`.

### Đính chính quan trọng về tiền đề của Phase 0

Mini-Spec dựng Phase 0 như cổng gỡ **mâu thuẫn** giữa Mục 5.3 và 5.5 của
`TONG_HOP_TINH_NANG.md`. **Mâu thuẫn đó không tồn tại**:

- **5.3** nói về bước **tick xác nhận trách nhiệm bản quyền** (`/export-jobs/{id}/acknowledge`)
- **5.5** nói về cờ **chất lượng** `needs_review`

Hai chuyện khác nhau. 5.3 cấm hệ thống **tick hộ**, không cấm **hiện thông tin**. Hướng A tương
thích với cả hai mục, không đảo quyết định nào.

Vì vậy Phase 0 thực chất không phải "gỡ xung đột" mà chỉ là trả lời: *có hiện thông tin không?*
Câu trả lời: **có**.

---

## 3. Audit Before Build — 4 tiền đề SAI của Mini-Spec

| Mini-Spec nói | Đo được |
|---|---|
| `ROADMAP_KHAC_PHUC_TOAN_DIEN.md` là nguồn sự thật, viện dẫn "vấn đề #1/#2/#19" | **File không tồn tại trong repo.** `MINI_SPEC_PLAYBOOK.pdf` cũng không. ⇒ Mọi số hiệu vấn đề **không truy ngược được**, không dùng làm căn cứ |
| `token_cost` chưa expose, cần thêm vào API | **Đã expose sẵn** ở `GET /pages/{id}/translation` (`schemas/common.py`). Đo thật trên production 24-09 |
| Đường nhanh có `batch_id`; dựng `QuickTranslateSummaryService.get_review_flag_summary(batch_id)` | **Đường nhanh KHÔNG tạo `BatchRun`.** Nó gọi `taoProject` → `taiTrangLen`/`taiGoiLen` → `xuatChapter`. Khoá đúng là `project_id` |
| Cờ OCR tên `ocr_needs_review` | **Không tồn tại.** Tên thật: **`needs_manual_count`** (trong `ExportWarningsRead`). Mini-Spec tự nghi ngờ điểm này — nghi ngờ đúng |

### Phát hiện lớn nhất: backend của B1 **đã tồn tại**

`GET /projects/{project_id}/export-warnings` (E12/E14/F1) đã trả sẵn mọi thứ B1 cần —
`needs_manual_count`, `quality_needs_review_count`, `overflow_warning_count`,
`font_missing_count` — và **khoá theo `project_id`**, đúng thứ đường nhanh có.

Dựng `QuickTranslateSummaryService` như Mini-Spec mô tả sẽ tạo ra đúng **"nguồn sự thật thứ hai"**
mà **Ràng buộc #4 của chính Mini-Spec cấm**. Nên không dựng; dùng lại cái đã có.

### Một đính chính của chính tôi giữa lượt

Sau khi thấy `token_cost` đã expose, tôi kết luận **"Phase 1 thuần frontend"**. **Sai.** Kiểm tiếp
thì thấy:

- `RegionDetail` (dữ liệu màn rà soát) **không** mang `token_cost`
- `ExportWarningsRead` **không** có tổng token

Nên vẫn cần hai bổ sung backend nhỏ — đều là **đọc/cộng giá trị đã lưu**, không tính lại token.

### Hành vi auto-download

Trigger từ **frontend**, trong `DichNhanh.jsx` sau khi job xuất xong. Lời gọi cảnh báo đặt **sau**
bước tải, và bọc `try/catch` — hỏng ở đó không được nuốt mất màn kết quả.

---

## 4. Design Choice

**Dùng lại `export-warnings` thay vì dựng service mới.** Một nguồn sự thật cho "vùng cần rà soát".

**Đếm theo VÙNG CHỮ, không theo trang.** Mini-Spec viết mẫu `"2/12 trang"`, nhưng backend đếm
theo **vùng**. Viết "N trang" là bịa ra một con số không ai kiểm chứng được.

**Gộp 4 loại cờ thành một số** ở đường nhanh: với người đi đường nhanh, cả bốn dẫn tới cùng một
hành động (mở màn rà soát). Chi tiết từng loại đã có ở đường đầy đủ. **Không** cộng
`shape_fallback_count` — đó là "không biết lòng bong bóng ở đâu", đã căn bằng khung dự phòng,
không phải lỗi cần sửa; cộng vào sẽ thổi số và làm người ta bỏ qua cảnh báo thật.

**`NULL` ≠ `0` cho token.** `NULL` = engine miễn phí hoặc chưa dịch ⇒ giao diện im lặng. `0` sẽ
mang nghĩa "đã dùng engine tốn tiền mà tốn hết 0 token". Giữ `SUM` trả `NULL` của Postgres thay vì
ép về 0.

**Tổng token đếm CẢ chapter**, khác mọi số khác trong `ExportWarningsRead` (chỉ đếm trang sẽ
xuất). Có chủ đích: token đã tiêu là tiền đã mất, kể cả ở trang không lọt vào file. Đã ghi chú
ngay trong schema vì nó đếm theo quy tắc khác.

**Im lặng khi sạch.** Không hiện "0 vùng cần xem lại — mọi thứ ổn": đó là lời khẳng định phép đo
hiện tại không chứng minh được.

---

## 5. Changed Files

**Backend**
- `app/schemas/common.py` — `RegionDetail.token_cost`, `ExportWarningsRead.token_cost_total`
- `app/api/v1/routes.py` — truyền `token_cost` vào `RegionDetail` (dùng lại `TranslationResult`
  đã có trong lượt join ⇒ **không tốn thêm truy vấn**); cộng tổng token ở `export-warnings`

**Frontend**
- `src/components/chapter/DichNhanh.jsx` — `demVungDangNgo()` + gọi `layCanhBaoXuat` sau khi tải
  xong + một dòng cảnh báo
- `src/components/chapter/ChapterSummary.jsx` — dòng tổng token
- `src/components/RegionPanel.jsx` — token của từng vùng

**Test**
- `backend/tests/test_p1_token_cost_integration.py` — **mới**, 8 bài
- `frontend/src/components/chapter/DichNhanh.test.jsx` — +6 bài

**Tài liệu**
- `docs/DECISION_LOG_P0.md` — **mới**
- `docs/REPORT_P0_P1.md` — file này

**KHÔNG đổi:** engine dịch, pipeline 6 bước, ngưỡng gắn cờ, hành vi auto-download, cổng M10,
`TextRegion`/`OCRResult`/`TranslationResult`/`TypesetResult`.

---

## 6. Tests

| Bộ | Kết quả |
|---|---|
| `test_p1_token_cost_integration.py` (mới) | **8 passed** |
| Toàn bộ frontend | **396 passed** (từ 390, +6) |
| Toàn bộ backend | **1.649 passed · 6 skipped · 0 failed · 0 error** (`PYTEST_EXIT=0`) |

Mini-Spec ghi mốc hồi quy là "1.631 backend + 390 frontend". Con số backend nay là **1.649** vì
giữa hai lượt đã có thêm test của các commit trước P0-P1 (`auto` cho hướng đọc, chữ vector trong
PDF, ảnh cụt) cộng 8 bài mới của P1. **Không bài cũ nào đỏ.**

### Một bài đỏ, và nó là lỗi CỦA TÔI chứ không phải sản phẩm hở

`test_chapter_nguoi_khac_van_bi_chan` đỏ với `200` thay vì `404`. Nguyên nhân: fixture dựng project
**thẳng vào CSDL** nên nó **không có chủ**, mà chapter không chủ được hệ thống **cố ý** cho mọi tài
khoản thấy (để chapter tạo trước slice B không biến mất).

Suýt đi sửa sản phẩm cho vừa cái test. Đã sửa **fixture**: tạo chapter **qua API** để có chủ thật,
rồi mới kiểm. Sau khi sửa: tài khoản A `200`, tài khoản B `404` — đúng.

---

## 7. Live Verification — chạy thật trên production 24-09

Deploy xong rồi mới đo. Tất cả số dưới đây lấy từ `translation-api/web.cmc-1.vibenode.matbao.ai`.

### ✅ Trường mới có mặt và mang số thật

| Phép đo | Kết quả |
|---|---|
| `token_cost` từng vùng (`GET /pages/{id}/detail`) | `[1416, None, None, None]` |
| `token_cost_total` (`GET /projects/{id}/export-warnings`) | `1416` |
| Engine thật đã chạy | `llm_context` · `gemini-3.5-flash` |

**Đây là bằng chứng cho ba thứ cùng lúc:**

1. Hai trường mới hoạt động, mang số thật
2. **Phân biệt `NULL` với `0` đúng** — vùng đầu tiêu 1.416 token, **ba vùng còn lại `None` chứ
   không phải `0`**. Đúng nghĩa: `llm_context` gộp cả trang gửi một lượt nên chi phí ghi ở một
   vùng, ba vùng kia không tiêu riêng
3. Tổng cộng đúng

### ✅ Giao diện hiện đúng — bấm tay trên Chromium thật

- **Chapter `llm_context`:** màn tóm tắt hiện *"Chapter này đã tiêu **1.416 token** cho bản dịch
  AI. Tính cả trang không lọt vào file xuất — token đã tiêu là đã mất."* Đúng định dạng số
  tiếng Việt (`1.416`)
- **Chapter `google_fast`:** **không nhắc tới token ở bất kỳ đâu** — không phải "0 token". Đây là
  trường hợp quan trọng nhất và nó đúng
- **Cảnh báo cờ:** chapter thử có `needs_manual_count = 1`, màn tóm tắt hiện *"1 bong bóng sẽ
  trống vì chưa đọc được chữ gốc"*
- **0 lỗi console** ở cả hai lượt

### ✅ Xác nhận lại ĐX-3 theo CHIỀU NGƯỢC

Production đặt mặc định `translate_default_engine: llm_context`.

- Sáng 24-09: chọn `google_fast` → chạy **`google_fast`**, 0 token (khác mặc định)
- Lượt này: chọn `llm_context` → chạy **`llm_context`**, 1.416 token

**Cả hai chiều đều đúng** — pipeline đọc thật cột `Page.translate_engine_override`, không phải
tình cờ trùng mặc định.

### ⚠️ Còn một mục CHƯA kiểm live

**Dòng cảnh báo trên chính màn "Dịch nhanh"** chưa được nhìn thấy trên production. Lý do: đường
nhanh tự tạo chapter riêng mỗi lượt, và chapter nó tạo ra phải *tình cờ* có cờ thì dòng đó mới
hiện — hai lượt thử đầu đều sạch.

Phần **dữ liệu** của đường đó đã verify live (`layCanhBaoXuat` trả `needs_manual_count: 1` thật).
Phần **hiển thị** mới chỉ có 3 bài test tự động. Không nâng lên "đã kiểm live".

### Chi phí đã tiêu để có phép đo này

**1.416 token Gemini** (`gemini-3.5-flash`). Chính con số đó là bằng chứng cần tìm.

---

## 8. Remaining Limits

1. **Chưa quy đổi token → tiền** (VNĐ/USD). Cố ý ngoài phạm vi.
2. **Cảnh báo gộp 4 loại thành một số** ở đường nhanh — người dùng không biết là loại nào cho tới
   khi mở màn rà soát.
3. **Đếm theo vùng, không theo trang.** "5 vùng chữ" không cho biết rải trên bao nhiêu trang.
4. **Không thêm cảnh báo vào đường đầy đủ** — đường đó đã có màn rà soát riêng.
5. **Mọi số hiệu "#1/#2/#19" của Mini-Spec không dùng được**, vì tài liệu gốc không tồn tại trong
   repo. Nếu `ROADMAP_KHAC_PHUC_TOAN_DIEN.md` có thật ở đâu đó, cần đưa vào repo rồi đối chiếu lại.

---

## 9. Commit / Deploy State

| | |
|---|---|
| Commit | `ab0ed15` — đã push lên `origin/main` |
| `translation-api` | deploy **succeeded**, `healthz` 200, hai trường mới trả đúng |
| `translation-web` | deploy **succeeded**, bundle `index-lN110W1i.js` chứa đủ chuỗi P1 |
| Thứ tự deploy | **backend trước**, chờ `healthz` 200 rồi mới frontend |
| Rollback | redeploy về v70 (api) / v37 (web) — bản deploy sáng 24-09 |

Thay đổi API là **cộng thêm trường**, không đổi trường nào đang có ⇒ client cũ (kể cả tiện ích
Chrome) không vỡ.

Theo Stop Rule #3 của Mini-Spec: **DỪNG** sau báo cáo. Không tự mở Phase 2 (xác minh PDF / chapter
24 trang) hay Phase 3 (benchmark chất lượng dịch).

### Việc cần làm ngay, ngoài phạm vi Mini-Spec

**Khoá tài khoản `kiemthu-dx3@matbao.com`.** Nó được tạo để kiểm thử, mật khẩu đã đi qua kênh chat,
và nó đã tạo 2 chapter thật trên production (`42830a4f…` google_fast, `4c42cf17…` llm_context).
Xoá luôn hai chapter đó nếu không cần giữ làm mẫu.
