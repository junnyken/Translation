# Báo cáo E21-LV — Live Verification & Closeout của E21

**Project:** Translation · **Phase:** hậu-E21 (đóng gói xác minh, không phải tính năng mới)
**Ngày:** 2026-09-09 · **Nền:** `bf8accc` (E21)

## 1. Summary

E21-LV là closeout verification cho E21 (gõ đè `raw_text` + phóng to đối chiếu ảnh gốc) —
**không thêm OCR engine, không đổi API/schema, không mở UAT lớn.** Chỉ kiểm đúng 13 tiêu chí đã
chốt trong kế hoạch, bằng Chromium thật.

**Kết quả: 25/25 kiểm đạt** (13 tiêu chí gốc + vài phép đối chiếu phụ). Ảnh chụp bằng chứng ở
`docs/evidence/E21-LV/`.

## 2. Tìm ra nguyên nhân thật của "MCP Chrome lỗi"

Kế hoạch dự trù 3 phương án khi MCP Chrome lỗi (bấm tay / Playwright local / headless CDP làm
bằng chứng phụ). Trước khi chọn phương án, thử lại `chrome-devtools` MCP và Playwright local —
cả hai đều báo cùng một lỗi `TargetClosedError` / "Target closed".

Đào sâu bằng cách launch Chromium trực tiếp qua Playwright (không qua MCP) với log chi tiết —
lộ ra nguyên nhân thật:

```
chrome-headless-shell: error while loading shared libraries: libnspr4.so: cannot open shared
object file: No such file or directory
```

**Không phải giới hạn hạ tầng vĩnh viễn — là thiếu gói hệ thống.** Sửa bằng:

```bash
.venv/bin/python -m playwright install-deps chromium   # cần sudo, có sẵn passwordless
```

Sau khi cài, Playwright launch Chromium headless thành công. Đây khả năng cao cũng là nguyên
nhân của các lần `chrome-devtools` MCP báo lỗi tương tự ở project `audit-ads` cùng phiên làm
việc này — cùng một môi trường, cùng một thiếu sót ở tầng hệ điều hành, không phải lỗi riêng của
từng project hay từng công cụ.

→ Áp dụng đúng thứ tự ưu tiên của kế hoạch: **Phương án 2 (Playwright local)** khả dụng, dùng nó
thay vì rơi xuống phương án 3 (chỉ chụp ảnh, không thay được review tương tác) hay phải dừng lại
chờ người dùng bấm tay.

## 3. Chuẩn bị dữ liệu kiểm — dùng dữ liệu thật có sẵn, không bịa mới

- Trang test: `page e3b458c7…` (project "Test E2E Pepper Carrot", đã `typeset_done` từ E13/E15),
  2 vùng đã có OCR + bản dịch thật.
- Vùng mục tiêu: `region 30234117…` (reading_order=2, bbox 174×100px) — vùng lớn nhất trên
  trang, khung đỏ dễ đối chiếu bằng mắt trên ảnh chụp.
- Tài khoản `test-e2e@local.test` (chủ sở hữu project đó) đã tồn tại nhưng không rõ mật khẩu
  gốc — đặt lại mật khẩu bằng đúng hàm băm `scrypt` của server
  (`backend/app/core/mat_khau.py:bam`), không đoán hay bỏ qua xác thực.

## 4. Cách kiểm — không chỉ nhìn ảnh chụp bằng mắt

`scripts/do_run_e21_lv.py` (mới, theo đúng khuôn `scripts/do_run_e15_ui.py` đã có):

- **Khung đỏ**: suy lại ĐỘC LẬP đúng công thức của `ZoomCropModal.jsx` (nới lề bbox 40%/tối
  thiểu 24px, tỉ lệ phóng tới cạnh dài nhất ≈900px, `Math.round` kiểu JS) từ kích thước ảnh gốc
  đo thật (1600×2213px, tải qua API), rồi lấy mẫu `getImageData` thật trên canvas ở đúng toạ độ
  tính ra — không so màu tuyệt đối (nét đè lên ảnh, alpha .85) mà so "đỏ trội" tại nhiều điểm dọc
  4 cạnh khung kỳ vọng.
- **Không lệch khi ảnh load xong**: đo lại sau 600ms, kỳ vọng khớp y hệt lần đầu.
- **Không méo khi resize**: so tỉ lệ khung hiển thị (`getBoundingClientRect`) với tỉ lệ raster
  canvas ở 2 kích thước khác nhau trong lúc modal đang mở.
- **raw_text lưu được + không lan dịch**: sửa qua UI thật, bấm Lưu, đợi job xong qua polling
  thật (không giả lập), refresh trình duyệt thật, rồi đối chiếu `translated_text` và số job
  `type='translate'` **trực tiếp trong Postgres** trước/sau — không tin vào việc UI "trông có vẻ
  đúng".
- **Không tràn ngang**: đo `scrollWidth` vs `clientWidth` ở 3 kích thước (375/768/1440px), cả
  lúc modal đóng và đang mở.
- **Console sạch**: gắn listener `console`/`pageerror` suốt toàn phiên, không chỉ lúc mở modal.

## 5. Kết quả (25/25 đạt)

| Nhóm | Tiêu chí | Đạt? |
|---|---|---|
| Ảnh gốc & modal | Endpoint tải được, modal mở, canvas render đúng kích thước tính tay (sai số ≤1px) | ✅ |
| Khung đỏ | Đúng vị trí lúc mở, không lệch sau 600ms, không méo/lệch khi resize 2 lần | ✅ (12/12 điểm mẫu mỗi lần đo) |
| Sửa raw_text | Nút Lưu bật đúng lúc, lưu xong không lỗi, sống sót qua refresh trình duyệt thật | ✅ |
| Không lan tác dụng phụ | Bản dịch không đổi (đối chiếu CSDL), không sinh job `translate` mới, trang không lỗi hiển thị | ✅ |
| Responsive | Không tràn ngang ở mobile/tablet/desktop, kể cả khi modal đang mở | ✅ (6/6) |
| Console | Không lỗi JS console suốt phiên | ✅ |

Ảnh chụp bằng chứng: `docs/evidence/E21-LV/01_truoc_khi_mo_modal.png`,
`02_modal_mo_desktop.png` (khung đỏ áp sát đúng chữ "...mmm probably not strong enough." trên
bong bóng thoại — đối chiếu mắt xác nhận đúng phép đo pixel), `03_sau_khi_luu_va_refresh.png`,
`04_responsive_{mobile,tablet,desktop}.png`.

## 6. Dọn dẹp sau kiểm

Bước "sửa raw_text, bấm lưu" ghi thật vào Postgres của project fixture dùng chung cho nhiều
mini-spec trước (E12/E13/E15/E20). Sau khi xác nhận đạt, đã **phục hồi `raw_text` và
`edited_by_user` về đúng giá trị trước khi kiểm** — fixture sạch cho lần sau, không để lại dấu
vết kiểm thử trong dữ liệu dùng chung. Tài khoản `test-e2e@local.test` giữ mật khẩu mới đặt (dùng
cho các script kiểm UI thật sau này thay vì phải đặt lại mỗi lần).

## 7. Trạng thái sau E21-LV

UI/browser pass toàn bộ (25/25, có bằng chứng ảnh + phép đo độc lập) ⇒ theo đúng bảng quyết định
trong kế hoạch: **đóng E21: CLOSED.** `FEATURES.md` cập nhật từ **BUILT** lên **LIVE**.

## 8. Remaining Limits

- Chưa đo trên ĐÚNG ảnh MangaPlus thật gây ra chuỗi E20/E21 — vẫn giữ nguyên giới hạn đã ghi ở
  `REPORT_E21.md §9`, E21-LV chỉ xác minh UX trên dữ liệu fixture có sẵn.
- Phép kiểm "đỏ trội" là suy luận màu sắc (ngưỡng R so G/B), không phải so khớp pixel-perfect
  tuyệt đối — đủ chắc cho mọi ảnh nghệ thuật thông thường, nhưng một nền ảnh cực đỏ (hiếm trong
  manga) có thể cho dương tính giả về mặt lý thuyết. Ảnh chụp màn hình đi kèm để đối chiếu mắt
  khi cần.
- `libnspr4.so` được cài ở tầng hệ điều hành của workspace hiện tại (không phải trong Dockerfile
  của project) — nếu workspace bị tạo lại từ image gốc, bước `playwright install-deps` cần chạy
  lại. Chưa ghi việc này vào Dockerfile/CI vì ngoài scope E21-LV.
