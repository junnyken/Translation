# Báo cáo Mini-Spec E12 — Cổng chất lượng từng vùng & định tuyến rà soát

**Project:** Translation · **Phase:** E — Translation Quality Hardening
**Ngày:** 2026-08-29 · **Nền:** E11 `26f9082` (`v1.1-E11`)

## 1. Summary

Trước E12, người dùng nhìn thấy một chapter "đã dịch xong" mà **không biết chỗ nào đáng ngờ**:
một vùng OCR đọc ra rỗng, một vùng bị nhận diện nhầm số trang, một bản dịch phải lùi về đường dự
phòng — tất cả trông giống hệt một vùng dịch tốt.

E12 thêm một lớp **giải thích**: sau khi căn chữ xong, mỗi vùng chữ được chấm bằng **luật thuần**,
rồi nói ra bằng câu tiếng Việt vì sao nên nhìn lại nó.

Bốn ranh giới quan trọng hơn bản thân tính năng:

1. **Máy không kết luận thay người.** Không xoá vùng nào, không tự bỏ tiếng động/số/chữ hoa.
   Nó chỉ nói *"có thể là"* rồi đẩy cho người xem. `reviewed_skip` **chỉ** do người bấm, và bỏ qua
   **không xoá** dữ liệu.
2. **Không hỏi thêm một con AI.** Nhờ LLM chấm chính bản dịch của LLM là để nó tự khen mình; kết
   quả không lặp lại được và tốn token. Bằng chứng đã nằm sẵn trong DB — việc cần làm là nói nó ra.
3. **Không có điểm 0–100.** Một con số gộp nhiều thứ khác bản chất nghe như đo được chính xác
   nhưng không giải thích được gì.
4. **"Chưa chấm" khác "chấm sạch".** Vùng chưa được đánh giá được đếm riêng, không bao giờ gộp
   vào "rõ ràng", và không bao giờ hiện thành 0 cảnh báo.

**1 bảng mới** (migration `0005_e12`, chạy thật up → down → up trên DB đã có dữ liệu M1–M10),
**3 endpoint**, **3 trường thêm** vào cảnh báo xuất, **2 bề mặt giao diện**.
**633 test backend + 66 test frontend** pass. Live: Run A–D **15/15**, Chromium **10/10**.

## 2. Audit Before Build

9/9 mục có bằng chứng (`TEST_LOG §E12`). Ba kết luận đổi cách làm:

| Mục | Kết quả |
|---|---|
| `reading_order` của M5 | **Có thật và ổn định** (1-2-3-4 trên trang thật) ⇒ luật "từ bị ngắt dòng sang vùng kế bên" làm được, không phải hoãn |
| Enum `job_type` | M1 đã khai đủ 6 loại từ đầu; thêm loại mới cần `ALTER TYPE` — **không an toàn trong một giao dịch Alembic** ⇒ chấm chạy bằng **móc trong worker**, không tạo `Job` mới |
| 3 ca thật để chốt test | Lấy từ trang đã chạy hết pipeline: thoại sạch (tin cậy 0,87–0,93), **OCR rỗng + `needs_manual`** (tin cậy 0,63), **`SPLASH/18` + tin cậy khung 0,384** |
| Vẽ lại khi vùng bị bỏ qua | Đổi hợp đồng render của M6/M8 ⇒ spec cho phép hoãn phần hiển thị, **giữ phần quyết định**. Tôi hoãn và ghi rõ |

## 3. Design Choice

**Luật thuần, tách hẳn khỏi DB.** `assessor.py` là hàm không chạm DB/mạng/không sửa đầu vào — nhờ
vậy 41 test đơn vị chạy không cần Postgres, và không có đường nào lén ghi đè dữ liệu M2–M6 trong
lúc chấm. Phần đọc/ghi nằm riêng ở `gate.py`.

**Bảng trắng 18 mã lý do.** Mã đi thẳng ra giao diện và vào bảng đếm; cho phép chữ tự do là sớm
muộn hai chỗ viết hai kiểu rồi không đếm được nữa. Có test bắt cả hai chiều: sinh mã ngoài bảng,
và mã thiếu câu tiếng Việt.

**`ocr_confidence_unavailable` chỉ để biết.** manga-ocr không bao giờ trả điểm tin cậy; coi đó là
dấu hiệu xấu sẽ bắt rà soát **toàn bộ** trang tiếng Nhật. Giao diện nói *"Engine OCR không cung cấp
điểm tin cậy"*, không bao giờ hiện 0%.

**Đếm ký tự hiển thị, không đếm byte.** `Đừng` là 4 ký tự nhưng 7 byte; đếm byte sẽ khiến mọi bản
dịch tiếng Việt trông như "dài bất thường".

**Giữ quyết định của người khi chấm lại**, trừ khi bằng chứng đổi (so `evidence_snapshot`).

## 4. Changed Files

| Tệp | Việc |
|---|---|
| `app/models/enums.py` | + 5 enum (`RegionRelevance`, `ReviewStatus`, `OverallBand`, `ConfidenceState`, `TranslationState`) |
| `app/models/__init__.py` | + `RegionQualityAssessment` (unique theo vùng, 2 index) |
| `alembic/versions/0005_e12_quality.py` | migration cộng-thêm, 2 chiều |
| `app/services/quality/reasons.py` | bảng trắng 18 mã + câu tiếng Việt |
| `app/services/quality/assessor.py` | bộ chấm thuần, `e12-rules-v1` |
| `app/services/quality/gate.py` | đọc/ghi DB, gộp số |
| `app/workers/tasks.py` | móc sau căn chữ và sau sửa tay |
| `app/api/v1/routes.py` | 3 endpoint + 3 số thêm vào cảnh báo xuất |
| `app/schemas/common.py` | 6 schema |
| `frontend/src/lib/status-presentation.js` | + 4 bảng dịch trạng thái E12 |
| `frontend/src/components/chapter/QualityPanel.jsx` | bảng "Vùng cần rà soát" (mới) |
| `frontend/src/components/RegionQualityBox.jsx` | hộp đánh giá + 2 nút quyết định (mới) |
| `frontend/src/App.jsx`, `api.js`, `ExportWarningModal.jsx`, `styles.css` | nối vào |
| `scripts/do_run_e12.py` | đo Run B/C/D, lặp lại được |

## 5. Tests

| Nhóm | Số | Ghi chú |
|---|---|---|
| Backend | **633** | E12 thêm 54 (41 đơn vị + 13 tích hợp) |
| Frontend | **66** | E12 thêm 9 |
| Live Run A–D | **15/15** | trên trang truyện thật + bơm lỗi có kiểm soát |
| Chromium | **10/10** | hai bề mặt giao diện, console 0 lỗi |

## 6. Một chỗ tôi sửa TEST chứ không sửa luật

Test đầu tiên khẳng định `SPLASH` phải bị gắn "có thể là hiệu ứng âm thanh" — và nó **đỏ**, vì
`SPLASH` dài 6 ký tự còn ngưỡng của spec là ≤5.

Nới ngưỡng lên 6 để test xanh chính là **sửa luật cho vừa test**. Tôi giữ ngưỡng, sửa test cho
đúng sự thật, và thêm một test dựng lại đúng ca thật: trên trang thật, vùng `SPLASH/18` **vẫn**
được đẩy đi rà soát — vì điểm nhận diện khung chỉ 0,384, không phải vì độ dài. Giới hạn này ghi
thẳng ở §9 chứ không giấu.

## 7. Success Criteria — đối chiếu thẳng

| Tiêu chí (spec §8) | Kết quả |
|---|---|
| Mỗi vùng sau căn chữ có đúng một đánh giá, chấm lại không tạo bản trùng | ✅ test tích hợp |
| Tất định, giải thích được, mọi đường không-sạch đều có mã lý do hiện ra | ✅ test tất định + bảng-lái 18 mã |
| Không xoá/sửa dữ liệu nào; không tự bỏ tiếng động/số/chữ ngắn/chữ hoa | ✅ test so sánh toàn bộ dữ liệu trước–sau |
| `NULL` confidence của manga-ocr là "không có điểm", không phải 0%/thấp | ✅ test đơn vị + test giao diện |
| Bảng tổng hợp & cổng xuất đếm đúng; chưa đánh giá không thành 0 cảnh báo | ✅ Run B (API=DB=4; 7 vùng chưa đánh giá) |
| Người dùng giữ/bỏ qua được; bỏ qua giữ nguyên dữ liệu và sống qua khởi động lại | ✅ Run C |
| Sửa một vùng thì chấm lại đúng vùng đó, vùng khác không đổi | ✅ Run D |
| Hồi quy M1–M10 + E11 pass; không thêm lời gọi LLM nào | ✅ 633 test; bộ chấm không có mạng |
| Tài liệu cập nhật đủ | ✅ ARCH §13, API §35–37, FEATURES, PLAN, TEST_LOG §E12 |

## 8. Hai sự cố trên bản chạy thật phát hiện trong lúc làm E12

Không thuộc E12 nhưng phải ghi lại:

1. **Worker bị giết vì hết bộ nhớ ở bước xoá chữ** — `SIGKILL/137` ở cả mức 2 GB lẫn 4 GB RAM.
   Mọi chapter đứng ở "Xoá chữ gốc", việc nằm lại `running` mà không ai báo lỗi. Đã nâng RAM
   2048 → 4096 và ép chế độ xoá chữ **theo cụm nhỏ** (`INPAINT_WHOLE_PAGE_MAX_MPX=0.25`,
   `INPAINT_INTRA_OP_THREADS=1`). **Chưa xác minh** — cần một trang thật chạy qua mới biết.
2. **Deploy là mất sạch ảnh đã tải lên** — `FileNotFoundError` cho ảnh gốc sau khi container được
   thay. Ảnh gốc/ảnh sạch/preview/file xuất đều nằm trong container. Cần ổ đĩa bền của nền tảng;
   chưa xử lý, và **không** nên lấp bằng mã ứng dụng.

## 9. Remaining Limits / Follow-ups

- **Luật độ dài không nhận ra tiếng động dài** (`SPLASH`, `CRASH!!`) — chỉ được đẩy đi rà soát khi
  có dấu hiệu khác. Nhận ra tiếng động theo *nghĩa* là việc của mô hình, không phải của luật.
- **Vùng "bỏ qua" vẫn được vẽ** vào ảnh xem thử và file xuất. E12 chỉ ghi quyết định; đổi cách vẽ
  là sửa hợp đồng render của M6/M8.
- **Chưa có endpoint chấm lại thủ công** — chấm lại đi kèm bước căn chữ, vì thêm loại `Job` mới
  cần `ALTER TYPE` không an toàn trong một giao dịch.
- **Không xử lý chữ dọc/xoay, bong bóng elip** — mini-spec khác.
- **Không có lịch sử ai quyết định** — hệ thống chưa có đăng nhập; `reviewed_skip` chỉ nói "người
  vận hành đã quyết", không nói ai.
- E12 **không** bảo đảm bản dịch đúng nghĩa. Nó chỉ đưa bằng chứng tới đúng chỗ người xem.
