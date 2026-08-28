# Báo cáo Mini-Spec E11 — Làm lại giao diện & luồng thao tác

**Project:** Translation · **Phase:** E — Product Experience Hardening (sau MTE M1–M10)
**Ngày:** 2026-08-29 · **Nền:** M10 `f433f5a` (`v1.0-M10`)

## 1. Summary

Giao diện cũ chạy được nhưng không nói cho người dùng biết điều gì đang xảy ra: tiêu đề là
*"Sửa tay bản dịch"* (tên một màn, không phải tên sản phẩm), ô chọn tệp là control mặc định của
trình duyệt, thẻ "Chapter gần đây" rỗng chiếm một phần ba màn hình, và nút hành động chính nhạt
tới mức trông như đang bị khoá.

E11 dựng lại bề mặt sản phẩm **mà không đụng một dòng nào ở backend**: không đổi API, schema,
enum, Celery hay mô hình AI. Toàn bộ 579 test backend giữ nguyên và vẫn pass.

Bốn thứ đáng kể hơn "trông đẹp hơn":

1. **Một nguồn duy nhất dịch trạng thái ra chữ** (`lib/status-presentation.js`), có test đối chiếu
   **từng giá trị enum trong `API.md`**. Không màn nào được tự gọi `typeset_done` là "hoàn tất"
   khi còn vùng tràn khung, và trạng thái lạ hiện là *"Trạng thái chưa được hỗ trợ"* kèm mã thô
   chứ không bị đoán là thành công.
2. **Ô chọn tệp thành vùng kéo-thả**, nhưng vẫn giữ `<input type="file">` thật (ẩn) — bàn phím,
   trình duyệt và trình đọc màn hình vẫn dùng đúng đường cũ. Mở được bằng cả Enter và Space.
3. **Nút bị khoá luôn nói vì sao**, ngay cạnh nút và nối bằng `aria-describedby`.
4. **Chữ hứa "3–6 phút/trang" bị gỡ** — con số đó chưa từng có trong bất kỳ phép đo nào của dự án
   (đo thật ở M9/M10 là ~40–100 giây/trang).

**57 test frontend** (bộ chạy test frontend trước E11 **chưa từng tồn tại**), **579 test backend**
pass, **15/15** phép kiểm trên Chromium thật ở 4 kích thước màn hình.

## 2. Audit Before Build

8/8 mục có bằng chứng đo được, chi tiết ở `TEST_LOG §E11.1`. Ba kết luận làm đổi cách làm:

| Mục | Kết quả |
|---|---|
| Stack | React 18.3.1 + Vite 6 + **CSS thuần**, không router, không thư viện icon, **không có bộ chạy test** ⇒ không thêm bộ khung giao diện nào; chỉ thêm `tokens.css` + bộ component tự viết, và thêm `vitest` (chỉ dùng khi phát triển) |
| Chỗ hỏng nặng nhất | **360px tràn ngang** (rộng cuộn 398 > 360) và **4 lỗi console** mỗi lần mở trang |
| Danh sách chapter | **Không có endpoint liệt kê project** — xem §7 |
| M7–M10 | Có sẵn `RegionPanel`, `BboxOverlay`, `ExportPanel`, `BatchPanel`, `ExportWarningModal` ⇒ **giữ nguyên và dùng lại**, không dựng trình sửa/xuất/mẻ thứ hai |

## 3. Design Choice

**Lấy luồng công việc làm trục, không làm bảng điều khiển.** Người dùng cần đi hết chuỗi: tạo
chapter → biết máy đang làm gì → sửa chỗ sai → xuất. Không thêm biểu đồ, không thêm trung tâm
cấu hình.

**Một chỗ dịch trạng thái, có test canh.** Đây là chỗ bảo vệ triết lý evidence-first của M1–M10 ở
tầng giao diện: rải chuỗi trạng thái khắp component là cách chắc chắn để sớm muộn có một màn gọi
`pending` là "xong".

**Giữ input file thật.** Tự vẽ vùng thả rồi bỏ input là đánh đổi độ tin cậy lấy vẻ đẹp.

**Không thêm TypeScript.** Mini-spec viết ví dụ bằng `.ts`, nhưng dự án là JavaScript thuần; thêm
TypeScript là đổi cả hệ thống build — trái constraint 10 ("không rewrite toàn frontend") và
constraint 5 ("chọn một hướng duy nhất theo stack hiện có"). Kiểu dữ liệu được mô tả bằng tài liệu
hàm và **ràng bằng test**, chỗ mà TypeScript cũng không kiểm được: đối chiếu với enum thật.

**Không dark mode, không đổi theme, không Chrome Extension** — đúng phạm vi mini-spec.

## 4. Changed Files

| Tệp | Việc |
|---|---|
| `src/styles/tokens.css` | **mới** — màu, khoảng cách, bo góc, đổ bóng, vòng focus dùng chung |
| `src/styles.css` | viết lại trên nền token; giữ nguyên tên lớp mà M7–M10 đang dùng |
| `src/lib/status-presentation.js` | **mới** — 8 họ trạng thái, hạ mức khi còn cảnh báo |
| `src/lib/chapter-progress.js` | **mới** — suy dòng thời gian pipeline từ trạng thái trang thật |
| `src/components/ui/*` | **mới** — Button, Field/Input/Select, StatusBadge, EmptyState, Dropzone, ProgressStage, Dialog, Alert, Icon |
| `src/components/chapter/*` | **mới** — ChapterCreateForm, ChapterRecentList, ChapterProgress, ChapterSummary, ReviewToolbar |
| `src/App.jsx` | vỏ ứng dụng: đầu trang, điều hướng, bố cục 2 cột, ghép các màn |
| `src/api.js` | thêm 2 hàm gọi API của M10; **sửa lỗi kiên nhẫn** (§5) |
| `src/components/RegionPanel.jsx` | dùng huy hiệu mới, mỗi enum tra đúng bảng của nó |
| `src/components/NewProjectPanel.jsx`, `StatusBadge.jsx` | **xoá** — đã có bản thay thế |
| `index.html`, `public/favicon.svg`, `public/config.js` | tiêu đề đúng tên sản phẩm; hết 404 ở console |
| `vitest.config.js`, `src/test/setup.js` | **mới** — bộ chạy test frontend |
| `scripts/soi_giao_dien.py`, `scripts/kiem_e11.py` | **mới** — đo giao diện và chạy thao tác thật, lặp lại được |

**Không có tệp backend nào bị đổi.**

## 5. Bug tìm được & đã sửa

**Giao diện bỏ cuộc sớm hơn máy chủ rất nhiều** (lỗi có từ M7, chỉ lộ ra khi chạy thật):
`choJobXong` hỏi tối đa 60 lần × 700ms = **42 giây** rồi ném lỗi *"Việc chạy nền quá lâu, chưa xong"*.
Nhưng worker chạy **một việc một lúc**, nên khi đang có chapter khác chạy thì việc căn lại chữ
phải xếp hàng — đo được **108 và 110 giây**. Người dùng thấy báo lỗi và tưởng hỏng, trong khi việc
vẫn chạy và xong bình thường ngay sau đó.

Sửa: chờ tới 10 phút, hiện rõ **"đang chờ tới lượt — máy chủ đang bận việc khác"**, và nếu hết
kiên nhẫn thì nói *"vẫn đang chạy"* chứ **không** nói là hỏng. Có 4 test canh.

Hai lỗi nhỏ hơn cũng sửa: tràn ngang ở 360px, và 404 ở console mỗi lần mở trang.

**Một lỗi trong chính phép kiểm của tôi**, ghi lại vì nó nguy hiểm hơn cả ba lỗi trên: điều kiện
nhận ra ô "Tên chapter" khi đi bằng Tab so `endswith("input")` với chuỗi kiểu `input#:r1:` nên
**không bao giờ đúng** — vòng lặp tab quá tay, chữ gõ vào lạc chỗ (tên chapter lưu vào bị mất chữ
đầu), mà phép kiểm vẫn báo ĐẠT. Một phép kiểm luôn xanh còn tệ hơn không có phép kiểm nào. Đã sửa
để nhận ra ô bằng chính `placeholder` của nó, và **khẳng định chữ gõ vào đúng bằng chữ đã gõ**.

## 6. Tests

| Nhóm | Số | Ghi chú |
|---|---|---|
| Frontend đơn vị + component | **57** | trước E11 **chưa có** bộ chạy test frontend nào |
| Backend M1–M10 hồi quy | **579** | không sửa một kỳ vọng cũ nào |
| Kiểm trên Chromium thật | **15/15** | 4 kích thước màn hình, thao tác bằng bàn phím, sửa tay, xuất |

## 7. Khoảng trống API — không tự lấp trong E11

**Chưa có `GET /api/v1/projects`** (liệt kê chapter). Danh sách "Chapter gần đây" hiện lấy từ bộ
nhớ trình duyệt, nên mở ở máy khác là **không thấy gì**.

E11 **không** tự thêm endpoint (constraint 1 của mini-spec). Giao diện xử lý bằng cách **nói thật**:
ghi rõ *"Ghi nhớ trên trình duyệt này. Mở ở máy khác thì dùng mã chapter."*, và khi trống thì hiện
chỗ trống có ích kèm nút tạo chapter, thay vì một thẻ rỗng chiếm chỗ.

Đề xuất mini-spec backend hẹp sau này: `GET /projects?limit=&cursor=` trả `id, name, source_lang,
số trang, trạng thái gộp, created_at` — vừa đủ cho danh sách, không kèm nội dung trang.

## 8. Success Criteria — đối chiếu thẳng

| Tiêu chí (spec §8) | Kết quả |
|---|---|
| Nhìn Home hiểu ngay tool làm gì, tải ảnh thế nào, bấm gì để bắt đầu | ✅ tiêu đề + mô tả + form 3 khối đánh số |
| Dropzone/list file thay control mặc định | ✅ input thật vẫn còn (ẩn), mở bằng Enter/Space |
| CTA có tương phản, có trạng thái chờ, có lý do khi bị khoá | ✅ có test canh cả lý do lẫn `aria-describedby` |
| Mọi trạng thái có nhãn Việt + icon + sắc thái nhất quán | ✅ 8 họ enum, test đối chiếu `API.md` |
| Các màn dùng chung token/component | ✅ một tệp token, một bộ component |
| Dùng được ở 360/768/1280/1600, không tràn ngang, đi được bằng bàn phím | ✅ đo thật, 0 tràn ngang |
| Ảnh xem thử sau khi sửa tay không cũ | ✅ `?v=1 → ?v=2` sau khi việc xong |
| Không đổi backend; hồi quy M1–M10 pass | ✅ 0 tệp backend bị sửa, 579 test pass |
| Tài liệu cập nhật đủ | ✅ ARCH §12, FEATURES, PLAN, TEST_LOG §E11, báo cáo này |

## 9. Remaining Limits / Follow-ups

- **Chưa kiểm bằng trình đọc màn hình thật** (NVDA/VoiceOver) — mới kiểm nhãn liên kết, vòng focus
  và thao tác bàn phím bằng máy.
- **Chưa có endpoint liệt kê chapter** (§7) — cần mini-spec backend hẹp, không lén thêm ở E11.
- **Không có chế độ tối / bộ nhận diện thương hiệu đầy đủ** — cố ý bỏ ngoài phạm vi.
- **Không có Chrome Extension, dán URL ảnh, hay lớp phủ dịch trên web** — đó là phase riêng.
- Màn sửa tay của M7 giữ nguyên cách làm việc; E11 chỉ thêm vỏ điều hướng quanh nó. Việc gộp
  thao tác sửa nhiều vùng cùng lúc vẫn là việc chưa làm.
- **Chất lượng nhận diện / OCR / dịch không đổi** — đó là E12.
