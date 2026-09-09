# Báo cáo Mini-Spec E21 — Gõ đè `raw_text` + phóng to đối chiếu ảnh gốc

**Project:** Translation · **Phase:** hậu-E20 (rà soát tay, thay engine tự động không có evidence)
**Ngày:** 2026-09-09 · **Nền:** `c6cac49` (sau E20a + E20b)

## 1. Summary

`REPORT_E20a.md`/`REPORT_E20b.md` chốt: chữ mảnh trên nền tranh phức tạp làm PaddleOCR đọc sai,
và **không path OCR tự động nào sửa được** (đã thử 5 kiểu tiền xử lý + 4 chế độ Tesseract, cả 9
đều 0/10 trên nhóm mục tiêu). Theo đúng "Decision gate sau E20" đã chốt trước trong kế hoạch gốc:
không path nào thắng ⇒ không đổi engine ⇒ chuyển hướng UX rà soát tay.

E21 làm đúng hướng đó: (1) `PATCH /regions/{id}` giờ nhận thêm `raw_text`, ghi vào `OCRResult` +
đánh dấu `edited_by_user` (cột mới, cùng mẫu với `TranslationResult`/`TypesetResult`), và (2)
`GET /pages/{id}/original-image` — endpoint mới phục vụ ảnh gốc CHƯA xoá chữ, để màn sửa tay có
gì đó đối chiếu (trước đó chỉ có `typeset-preview`/`clean-image`, cả hai đều đã xoá chữ gốc).
Frontend: `RegionPanel` đổi ô "chữ gốc" từ tĩnh sang sửa được, thêm modal `ZoomCropModal` vẽ bằng
canvas, phóng to đúng vùng bbox trên ảnh gốc kèm khung đỏ đánh dấu.

**1176/1176 test backend, 315/315 test frontend.** Chưa live-verify trên trình duyệt thật (công
cụ trình duyệt lỗi hạ tầng suốt phiên làm việc — xem §9).

## 2. Audit Before Build

Thực hiện qua 2 agent con (chỉ đọc, không sửa) trước khi viết dòng code nào:

| Câu hỏi | Kết quả audit |
|---|---|
| M7 hiện sửa được `raw_text` chưa? | Không — `RegionPatch` (`extra="forbid"`) không có trường đó; UI chỉ hiện `<div>` tĩnh, nhãn ghi rõ "không sửa ở đây" |
| Có cơ chế zoom/crop nào sẵn chưa? | Không — `grep -rniE "zoom\|crop\|lightbox"` trên `frontend/src` ra 0 kết quả |
| Indicator low_confidence/needs_manual đã có? | Có, `StatusBadge` + `status-presentation.js`, tái dùng nguyên |
| Backend có endpoint sửa `raw_text` chưa? | Không — `OCRResult` chưa có cột `edited_by_user`; docstring `PATCH /regions/{id}` ghi rõ "không đụng raw_text" |
| Màn M7 vẽ khung trên ảnh nào? | `typeset-preview` (`App.jsx:330-347` → `chiTiet.preview_url` → `routes.py:1237` hardcode path đó) — ảnh đã xoá chữ gốc, không đối chiếu OCR được |
| Có endpoint nào phục vụ `page.image_path` (ảnh gốc) ra ngoài chưa? | Không — chỉ có `clean-image` (M4) và `typeset-preview` (M6), cả hai đều KHÔNG phải ảnh gốc |

Kết luận: cả hai việc (sửa `raw_text`, phục vụ ảnh gốc) đều là khoảng trống thật, không trùng gì
đã chốt trước — đúng điều kiện để mở mini-spec mới.

## 3. Design Choice

**`edited_by_user` là BA cờ độc lập, không phải một.** `OCRResult.edited_by_user` đứng riêng,
không ăn theo `TranslationResult.edited_by_user`/`TypesetResult.edited_by_user` đã có. Sửa
`raw_text` không đụng cờ dịch; sửa dịch không đụng cờ OCR — mỗi tầng dữ liệu tự chịu trách nhiệm
về "ai sửa" của chính nó.

**Sửa `raw_text` KHÔNG tự dịch lại.** Cùng ranh giới với mọi thao tác M7 khác (E12: máy chỉ ra
chỗ, không tự sửa; E13: gợi ý phải người duyệt). Hai lý do cụ thể: (a) tốn token nếu tự động hoá
— người dùng có thể sửa nhiều vùng liền trước khi sẵn sàng dịch, và (b) có thể âm thầm xoá bản
dịch đã được sửa tay riêng ở `TranslationResult`.

**`re-ocr` (tự động, đọc lại từ ảnh) VẪN ghi đè `raw_text` đã gõ tay** — khác `re-translate` giữ
nguyên logic cũ "hành động tường minh trên 1 vùng được phép ghi đè". Không cần sửa gì ở
`_run_region_reocr`: hàm này vốn đã xoá-và-tạo-mới `OCRResult` (không phải UPDATE), nên
`edited_by_user` tự về `False` nhờ default của cột — không phải thêm logic reset thủ công.

**Ảnh gốc phục vụ qua route mới, không mở rộng `clean-image`.** Hai tấm ảnh có ý nghĩa khác hẳn
nhau (một cái CÓ chữ, một cái KHÔNG) — nhét chung một endpoint với tham số kiểu `?raw=true` sẽ
làm route đó trả hai loại nội dung khác nhau tuỳ query, khó audit/cache hơn hẳn so với hai route
riêng biệt, mỗi route luôn trả đúng MỘT thứ.

**Phóng to vẽ bằng canvas, không dùng CSS `background-position`/`clip-path`.** Canvas cho toạ độ
chính xác tuyệt đối theo pixel ảnh gốc (khớp thẳng đơn vị của `region.bbox`, không phải quy đổi
qua tỉ lệ hiển thị của trình duyệt), và `imageSmoothingEnabled=false` giữ được nét răng cưa thật
của chữ nhỏ thay vì trình duyệt tự làm mờ khi phóng to bằng CSS.

## 4. Changed Files

**Backend:**
- `app/models/__init__.py` — `OCRResult.edited_by_user` (cột mới)
- `app/schemas/common.py` — `OCRResultRead.edited_by_user`, `RegionDetail.ocr_edited_by_user`,
  `RegionPatch.raw_text`
- `app/api/v1/routes.py` — `patch_region` xử lý `raw_text`; endpoint mới `get_original_image`
- `alembic/versions/0016_e21_ocr_edited_by_user.py` — migration mới

**Frontend:**
- `src/api.js` — `duongDanAnhGoc(pageId)`
- `src/App.jsx` — truyền `pageId` xuống `RegionPanel`
- `src/components/RegionPanel.jsx` — ô chữ gốc sửa được, nút "Phóng to đối chiếu", dòng lịch sử
  thêm trạng thái OCR
- `src/components/ZoomCropModal.jsx` — mới
- `src/styles.css` — `.hop-thoai-rong`, `.khung-anh-phong-to`, `.hang-nhan-nut`; xoá `.chu-goc`
  (không còn dùng — ô tĩnh cũ đã thành textarea)

**Test:**
- `backend/tests/test_region_edit_integration.py` — 4 test mới
- `backend/tests/test_inpaint_task_integration.py` — 2 test mới
- `backend/tests/test_quyen_cheo_tai_khoan.py` — sửa fixture (thêm hiện vật thật cho
  `image_path`, xem §9 `TEST_LOG.md`)
- `frontend/src/components/RegionPanel.test.jsx` — mới, 7 test

**Docs:** `API.md` (mục 9b, 16, 17, 19), `ARCH.md` (§E21), `FEATURES.md`, `TEST_LOG.md`.

## 5. New API / DB / State

**DB:** `ocr_result.edited_by_user BOOLEAN NOT NULL DEFAULT false` (migration `0016_e21`).

**API:**
- `PATCH /api/v1/regions/{region_id}` — thêm trường tuỳ chọn `raw_text` trong body; response
  `edited_fields` có thể chứa `"raw_text"`. Lỗi mới: `409` khi vùng chưa từng OCR.
- `GET /api/v1/pages/{page_id}/original-image` → 200 — **mới**, chưa từng tồn tại trước E21.

Không đổi tên/xoá field nào đã chốt (đúng CLAUDE.md #6) — chỉ CỘNG THÊM.

## 6. Tests

Xem chi tiết đầy đủ (bao gồm 1 lượt đỏ giữa chừng và cách tìm ra nguyên nhân thật) ở
`docs/TEST_LOG.md` phần "E21". Tóm tắt:

```
Backend:  1176 passed
Frontend: 315 passed
```

## 7. Live Verification

**Chưa chạy được** — công cụ trình duyệt (chrome-devtools MCP) báo lỗi
`Protocol error (Target.setDiscoverTargets): Target closed` mọi lần thử, không phục hồi trong
suốt phiên làm việc. Đây là lỗi hạ tầng môi trường, không phải lỗi ở code hay ở cách gọi.

Đã bù bằng cách khác trong khả năng: chạy backend qua Docker thật (`docker compose run api`, có
log xác nhận migration + endpoint hoạt động qua `curl` thủ công ở các mini-spec trước đó cùng
ngày), và bộ test frontend giả lập DOM/canvas đầy đủ. Nhưng **không có gì thay thế được việc bấm
thật trên UI** — test tự động không bắt được lỗi bố cục CSS thật (vd modal chồng lấn, canvas vẽ
lệch trên trình duyệt thật khác jsdom).

## 8. Success Criteria

| Tiêu chí | Đạt? |
|---|---|
| `raw_text` sửa được qua `PATCH /regions/{id}`, có audit trail (`edited_by_user`) | ✅ |
| Không tự dịch lại khi sửa `raw_text` | ✅ (test `test_sua_raw_text_ghi_dung_va_danh_dau_da_sua`) |
| Ảnh gốc (chưa xoá chữ) phục vụ ra ngoài được, có gác quyền đúng chủ sở hữu | ✅ (`get_original_image` qua `_get_page_or_404`, dò chéo tài khoản xanh — sau khi sửa fixture) |
| UI cho phép phóng to đúng vùng, đối chiếu trước khi sửa | ✅ (chưa live-verify, xem §7) |
| Không phá vỡ hành vi cũ (M7 sửa translated_text/bbox/font vẫn nguyên) | ✅ (test cũ `test_sua_tay_khong_dung_chu_goc_ocr` vẫn xanh không sửa) |
| Docs cập nhật cùng lúc (API/ARCH/FEATURES/TEST_LOG) | ✅ |

## 9. Remaining Limits

- **Chưa live-verify UI** (xem §7) — `FEATURES.md` xếp E21 ở mức **BUILT**, chưa **LIVE**.
- Ảnh gốc phục vụ nguyên khổ, không nén/resize server-side — trang gốc rất lớn (hiếm) sẽ tải
  nguyên qua modal phóng to.
- Chưa đo trên ĐÚNG ảnh MangaPlus thật gây ra toàn bộ chuỗi E20/E21 — vẫn đang chờ người dùng
  tìm được cách chuyển file (MangaPlus chặn cả chuột phải lẫn DevTools, xem `REPORT_E20a.md §9`).
  Tính năng E21 được thiết kế để giải quyết ĐÚNG lớp vấn đề đó nhưng chưa thử trên ca gốc.
- Chưa có cách nào "hàng loạt" gõ lại nhiều vùng cùng lúc — mỗi lần một vùng, đúng chủ ý (không
  tự động hoá sửa OCR hàng loạt, tránh gõ sai một mẫu rồi áp cho nhiều vùng khác nhau).
