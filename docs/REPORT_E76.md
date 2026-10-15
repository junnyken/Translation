# REPORT E76 — Màn sửa tay kiểu canvas (WebGPU) + cọ xoá chữ

**Ngày:** 2026-10-15 · **Nguồn:** mockup đã được chủ dự án duyệt (`docs/MOCKUP_CANVAS.md`), lấy cảm hứng
từ editor của Koharu.

## Summary

- **Frontend:** màn mới `#canvas=<page_id>`, hoặc `#canvas=&project=<id>` để mở theo chapter. Màn cũ
  `#page=<id>` giữ nguyên làm đường lùi và có nút "Mở chế độ canvas".
  - Canvas nhiều lớp: ảnh gốc, ảnh đã xoá chữ, chữ dịch, mặt nạ cọ. Mỗi lớp ẩn/hiện được và chỉnh được
    độ mờ.
  - Vẽ bằng WebGPU; máy không hỗ trợ thì tự lùi về Canvas 2D và hiện banner.
  - Kéo, đổi cỡ khung chữ. Sửa chữ gốc, bản dịch, font, ghim cỡ chữ. Dịch lại và đọc lại từng vùng.
  - Hoàn tác/làm lại, thu phóng, phím tắt.
- **Backend:**
  - `POST /api/v1/pages/{id}/xoa-vung-to`: cọ xoá chữ, chạy nền.
  - `RegionDetail` thêm `text_color`, `stroke_color`, `stroke_width` (E70) và `xep_theo_hinh` (E75).
    Đây là thay đổi cộng thêm, không đổi trường cũ.

## Cọ xoá chữ — thiết kế

- Xoá trên **ảnh sạch hiện tại** (chưa có thì trên ảnh gốc). Ảnh gốc không bao giờ bị ghi đè.
- Kiểm mặt nạ NGAY trong request: đúng cỡ ảnh gốc, không rỗng, không trùm quá 50% trang. Sai thì 422
  kèm lý do đọc được.
- Dùng `_chay_model` của engine đang chọn, nên LaMa và SDXL (E74) đều dùng được.
- Vùng an toàn E14 được **giữ hiệu lực** (cập nhật vân tay ảnh) thay vì tính lại. Cọ chỉ xoá nét chữ
  sót, không đổi hình bong bóng; tính lại sẽ kéo theo căn chữ lại cả trang và xoá mất cỡ chữ người
  dùng đã ghim.
- Hàm xoá nằm ở `inpaint/mat_na_co.py`, KHÔNG nằm trong `lama.py`: `lama.py` bị cấm import cv2 để không
  ai lặng lẽ lùi về `cv2.inpaint`.

## Tests

- Backend `test_e76_xoa_vung_to.py`, 6 test:
  - chỉ điểm ảnh trong mặt nạ đổi
  - mặt nạ hỏng bị từ chối
  - API kiểm mặt nạ ngay
  - chạy trọn trên DB thật: ảnh gốc không đổi, mặt nạ được dọn, vùng an toàn còn hiệu lực, ảnh xem thử
    vẽ lại
  
  **Đối chứng âm:** bỏ bước giữ hiệu lực vùng an toàn ⇒ đỏ.
- Phép dò chéo quyền giữa các tài khoản bao trùm endpoint mới: A dừng ở nghiệp vụ, B bị chặn 404.
- Frontend: 495/495 vitest (trước ~390), `vite build` thành công.
- Bộ backend đầy đủ: 3 chốt đỏ khi mới thêm (task chưa đăng ký, cv2 trong `lama.py`, phép dò quyền rỗng
  nghĩa) — đã xử lý cả ba.

## Live Verification

Bấm thật trên Chromium (bản build, API giả lập bằng dữ liệu mẫu):
- Màn mở được, không lỗi console.
- Không có WebGPU ⇒ lùi Canvas 2D và hiện banner.
- Kéo khung ⇒ `PATCH /regions/r1 {"bbox":{"x":289,"y":235,…}}`. Khớp đúng tỉ lệ đang vẽ (0,595: kéo 65px
  màn hình = 109px ảnh gốc).
- Tô cọ ⇒ `POST /pages/p1/xoa-vung-to`.

## Remaining Limits

1. **WebGPU chưa chạy trên GPU thật** (Chromium headless không có). Đường 2D đã chạy thật.
2. Khi thông báo hiện ra làm vùng canvas đổi cỡ, màn tự căn lại vừa khung và mất mức zoom người dùng
   đang để.
3. Thiếu so với mockup:
   - dải trang không có ảnh thu nhỏ
   - chưa có hộp xuất riêng (nút Xuất dẫn về trang chapter)
   - chưa có cảnh báo "máy đang đoán" (E66 chưa có trường API)
   - chưa xoay khung, chưa thêm chữ mới
4. Chữ trong giao diện mới do DEV viết tạm. BA cần rà wording.
5. Mặt nạ cọ của trang rất lớn (~4000×6000) tốn ~100 MB bộ nhớ trình duyệt.

## Bổ sung — chạy thật đầu-cuối (15-10-2026, sau lần deploy đầu)

Chủ dự án mở production mà **không tìm thấy nút canvas**. Sau đó tôi dựng nguyên hệ thống thật trên máy
dev (Postgres, Redis, API, worker với CTD, manga-ocr, LaMa, Google dịch) và bấm trên Chromium với một
trang manga tiếng Nhật thật. Phát hiện và đã sửa 3 lỗi:

1. **Nút "Mở chế độ canvas" khó thấy.** Nó nằm lẫn giữa các ô tick, dạng nút phụ. Đã chuyển lên thanh
   đầu màn sửa tay, dạng nút chính, kèm test.
2. **Cọ xoá chữ luôn bị 422 "Vùng tô chiếm 100% trang".** Màn canvas xuất mặt nạ RGBA trắng/đen
   **đục**; máy chủ đọc "điểm không trong suốt" thành điểm xoá. Test hai phía đều xanh vì mỗi phía tự kiểm
   theo cách hiểu riêng. Sửa: điểm xoá = sáng VÀ đục. Có test cho cả 3 kiểu mặt nạ.
3. **Kéo khung mà chữ đứng yên ở chỗ cũ.** Có hai nguyên nhân:
   - Đổi khung không bỏ vùng an toàn E14 quanh khung cũ.
   - Căn lại một vùng đo trong khung gốc, không theo ô E14 và không nhân hệ số E65, trong khi bộ vẽ làm
     cả hai. Đây là lỗi đã ghi từ đầu phiên.

   Sửa: đổi khung thì xoá vùng an toàn; căn lại một vùng đi CÙNG đường với căn cả trang (tự tính lại
   vùng an toàn, căn trong ô đặt chữ, nhân hệ số vẽ, tính viền). 2 test kèm đối chứng âm.

Hệ quả lên hai test cũ:
- `test_ghim_co_qua_lon…` trước đây "tràn" chỉ vì lỗi số 3. Đã dùng câu dài hơn để vẫn tràn thật.
- Phép dò quyền chéo phải dựng lại vùng an toàn sau mỗi lượt.

Kết quả bấm thật sau khi sửa, lần nào cũng kiểm lại bằng dữ liệu trên máy chủ:
- Nút canvas hiện trong khung nhìn.
- Kéo khung ⇒ máy chủ ghi khung mới, chữ vẽ đúng chỗ mới.
- Sửa bản dịch ⇒ máy chủ ghi đúng.
- Cọ ⇒ việc xoá chạy xong, ảnh sạch đổi.
- 0 lỗi HTTP, 0 lỗi console.

Chưa thử trên GPU có WebGPU thật.
