# Báo cáo Mini-Spec M10 — Khai báo mục đích & nhắc trách nhiệm trước khi giao file

**Project:** Translation · **Phase:** MTE · **Ngày:** 2026-08-28
**Nền:** M9 `d83c572` (`v0.9-M9`)

## 1. Summary

Trước M10, hai chỗ nói dối theo kiểu im lặng:

- Ô "mục đích sử dụng" **chọn sẵn `personal`** — ai bấm nhanh cũng thành "đọc cá nhân" mà chưa hề
  tự khai. Cột trong DB thì bắt buộc từ M1, nên nhìn vào dữ liệu tưởng ai cũng đã khai báo.
- Bấm xuất là ra file ngay, **không nói gì** về việc trong bản đó còn bao nhiêu bong bóng sẽ trống
  vì chưa đọc được chữ, hay bao nhiêu chỗ chữ tràn ra ngoài khung.

M10 sửa cả hai, theo đúng ranh giới của mini-spec: **cảnh báo, không chặn**.

- Khai báo mục đích **bắt buộc tự chọn**, không có giá trị mặc định, và **không sửa được** sau khi
  tạo chapter.
- Lần đầu xuất mỗi chapter: một hộp thoại nhắc trách nhiệm bản quyền **kèm số liệu thật** về chất
  lượng bản sắp giao. Nút xuất mờ tới khi tự tick.
- Việc tick được ghi vào bảng riêng `export_compliance_log` — **chỉ số liệu**, đúng 10 cột, không
  đường dẫn file, không ảnh, không bản dịch.
- **Máy chủ không cấm gì cả**: nó ghi nhận. Cổng chặn nằm ở giao diện. Có test canh cả hai đầu.

**1 bảng mới** (migration `0004_m10`, đã chạy thật up → down → up), **2 endpoint**, **1 hộp thoại**.
**579 test pass**, tăng 33 test so với M9. Chạy thật đầu-cuối trên chapter thật — số liệu ở
`TEST_LOG §M10`.

## 2. Audit Before Build

6/6 mục có bằng chứng. Hai kết luận làm thay đổi phạm vi:

| Mục | Kết quả audit |
|---|---|
| `Project.intended_use` | Đã `NOT NULL`, **không có default**, `ProjectCreate` cũng đã bắt buộc ⇒ **không cần migrate**. Mini-spec dự phòng "nếu nullable thì migrate" — không rơi vào ca đó |
| Chỗ hỏng thật | Nằm ở **giao diện**: `useState('personal')` chọn hộ người dùng. Đây mới là thứ M10 phải sửa |
| `ExportJob` | Không có trường tuân thủ nào ⇒ tạo bảng riêng |
| UI tạo chapter | Đã có form (M8) ⇒ sửa tại chỗ, không dựng modal mới |
| UI xuất | Đã có `ExportPanel` + xem trước ⇒ thêm hộp thoại, giữ nguyên luồng cũ |
| Sửa khai báo sau khi tạo | **Không có endpoint nào** cho sửa ⇒ đúng yêu cầu, thêm test canh cả `PATCH` lẫn `PUT` |
| Đếm cảnh báo | `export-preview` của M8 có `overflow_warning_count` nhưng **thiếu** `needs_manual_count` ⇒ endpoint mới của M10 trả đủ cả hai |

## 3. Design Choice

**Cảnh báo, không chặn — và ranh giới nằm ở đúng một chỗ.** Giao diện chặn (nút mờ tới khi tick);
máy chủ ghi nhận. Đảo lại — để máy chủ từ chối xuất khi chưa xác nhận — sẽ biến một công cụ cá
nhân thành cổng kiểm duyệt, và người dùng sẽ đi đường vòng (gọi API tay) chứ không đọc kỹ hơn.

**Số liệu trong bằng chứng do máy chủ đếm lại**, không nhận từ trình duyệt gửi lên (gửi kèm là
`422`). Số do máy khách gửi chỉ chứng minh trình duyệt nói gì, không chứng minh hệ thống lúc đó
thế nào.

**Chỉ đếm trên trang sẽ được xuất.** Vùng lỗi ở trang chưa chèn chữ xong không nằm trong file giao
đi; đếm vào chỉ làm con số phồng lên rồi người dùng bỏ qua cả cảnh báo thật.

**Bảng riêng thay vì `ExportJob.error_log`.** Bản ghi tuân thủ cần tra cứu được ("chapter này đã
xác nhận chưa, lúc nào, khai để dùng vào việc gì"); `error_log` là chỗ ghi lỗi kỹ thuật.
`export_job_id` để `SET NULL`: xoá file đã xuất **không được** xoá mất bằng chứng.

**Ghi cả lần KHÔNG tick.** Có người mở cảnh báo ra rồi bỏ đi cũng là một sự thật đáng lưu — nhưng
`acknowledged_at` để trống và chapter không được coi là đã xác nhận.

**Hiện một lần mỗi chapter.** Cảnh báo hiện lại mỗi lần xuất là kiểu cảnh báo mà ai cũng bấm cho
qua — hiện một lần thì nó còn được đọc.

**Không watermark/DRM.** Nó không giúp gì cho việc tuân thủ bản quyền thật, chỉ làm hỏng ảnh của
chính người dùng. Có guardrail quét mã để không ai lén thêm.

## 4. Changed Files

| Tệp | Việc |
|---|---|
| `app/models/__init__.py` | + `ExportComplianceLog` (10 cột, 1 index) |
| `alembic/versions/0004_m10_compliance.py` | migration 2 chiều; dùng **lại** enum `intended_use` của M1, không tạo type trùng nghĩa |
| `app/services/compliance/gate.py` | `ComplianceGate`: validate khai báo, đếm cảnh báo, ghi bằng chứng |
| `app/api/v1/routes.py` | 2 endpoint (§33–34 của `API.md`) |
| `app/schemas/common.py` | 3 schema |
| `frontend/src/components/ExportWarningModal.jsx` | hộp thoại nhắc (mới) |
| `frontend/src/components/ExportPanel.jsx` | gọi hộp thoại, ghi nhận sau khi tạo việc xuất |
| `frontend/src/components/NewProjectPanel.jsx` | bỏ mặc định, mô tả từng lựa chọn, nút mờ khi chưa chọn |
| `frontend/src/App.jsx`, `api.js`, `styles.css` | hiện khai báo ở màn chapter + 2 hàm gọi API + CSS hộp thoại |
| `tests/test_compliance_unit.py`, `tests/test_compliance_integration.py` | 27 test |
| `tests/test_no_ai_logic.py` | 6 guardrail M10 + sửa 1 guardrail kêu sai |
| `scripts/do_run_m10.py` | đo live, lặp lại được |
| `docs/*` | ARCH §11, API §33–34, FEATURES, PLAN, TEST_LOG §M10 |

## 5. New API / DB / State

**DB:** `export_compliance_log` — 10 cột, index `(project_id, acknowledged_at)`.
Không sửa bảng nào có sẵn, **không** migrate `Project`.

**API:** §33 `GET /projects/{id}/export-warnings`, §34 `POST /export-jobs/{id}/acknowledge`.
`POST /projects` (§1) không đổi hợp đồng — `intended_use` vốn đã bắt buộc từ M1; M10 chỉ làm cho
giao diện ngừng chọn hộ.

**State:** không thêm trạng thái nào vào `Page`/`Job`/`ExportJob`. "Đã xác nhận" là **suy ra** từ
việc có bản ghi `user_acknowledged=true`, không phải một cờ đặt tay.

## 6. Tests

**579 pass** (M9: 546). Riêng M10: 27 test + 6 guardrail.

Đáng chú ý: guardrail M10 canh **cả hai đầu** của nguyên tắc "cảnh báo, không chặn" —
một test khẳng định nút trong hộp thoại mờ khi chưa tick, một test khác khẳng định **máy chủ vẫn
cho xuất và cho tải về** khi chưa xác nhận. Thiếu vế thứ hai thì rất dễ có ngày ai đó "siết cho
chắc" ở tầng API và phá đúng nguyên tắc của mini-spec.

## 7. Bugs tìm được & đã sửa

1. **Giao diện chọn hộ mục đích sử dụng** (`useState('personal')`) — đây là lỗi mà M10 sinh ra để
   sửa, nhưng đáng ghi vì nó cho thấy ràng buộc ở DB không đủ: cột `NOT NULL` vẫn có thể được điền
   bằng một giá trị người dùng chưa từng chọn.
2. **Bộ quét khoá bí mật kêu sai** vì một khoá **giả** viết liền trong test của M9 — chỉ lộ ra sau
   khi M9 được commit (bộ quét chỉ soi file git đã theo dõi). Sửa bằng cách ghép chuỗi lúc chạy,
   **không** nới lỏng bộ quét: một cảnh báo kêu sai là một cảnh báo sẽ bị tắt.
3. **Guardrail "không watermark" đỏ vì chính đoạn văn giải thích "không làm watermark"** — soi lời
   văn thay vì soi mã. Sửa: bỏ chú thích và chuỗi tài liệu bằng `tokenize` rồi mới quét.

## 8. Success Criteria — đối chiếu thẳng

| Tiêu chí (spec §8) | Kết quả |
|---|---|
| Tạo chapter bắt buộc khai báo, không default, không suy đoán hộ | ✅ live: 422 cho thiếu/sai/rỗng, 201 cho hợp lệ; giao diện bỏ mặc định + guardrail canh |
| Bắt buộc tick mới xuất được | ✅ ở **giao diện** (`disabled={!daTick}`, có guardrail). Máy chủ cố ý **không** cấm — đúng constraint 8 |
| Hộp thoại hiện đúng số vùng tràn khung & chưa đọc được | ✅ live: 1 và 2, số thật, tạo bằng thao tác thật |
| Log xác nhận chỉ metadata, không lưu nội dung | ✅ đúng 10 cột, guardrail liệt kê tên cột |
| M1–M9 hồi quy pass | ✅ 579/579 |
| Guardrail chặn xuất khi chưa tick | ✅ ở giao diện; kèm test khẳng định máy chủ vẫn cho xuất |
| Live: tạo chapter + xuất, cảnh báo đúng, log được ghi | ✅ `TEST_LOG §M10.2–4` |

## 9. Remaining Limits / Follow-ups

- **Giao diện chưa bấm tay trên trình duyệt** — hộp thoại đã dựng và build sạch, nhưng chưa có
  phiên thao tác thật như M7 đã làm.
- **Chưa đo trên hệ thật** ca chapter hoàn toàn sạch (0 cảnh báo) và ca bấm "Để sau"
  (`user_acknowledged=false`) — mới kiểm bằng test tích hợp.
- Chưa có auth/nhiều người dùng: `edited_by_user` vẫn chỉ nói "có người sửa", không nói "ai".
- Chưa lưu nhiều phiên bản xuất; chưa có cảnh báo đa ngôn ngữ — cố ý để lại, không làm ở M10.
- Không watermark/DRM — và đây là **quyết định**, không phải việc còn nợ.
