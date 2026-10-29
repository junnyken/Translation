# REPORT E78 — Xuất PSD nhiều lớp

**Ngày:** 2026-10-15 · **Nguồn:** tham khảo Koharu (`koharu-psd`), mục 6. Viết theo đặc tả công khai của
Adobe, không chép mã Koharu (Koharu là MIT OR Apache-2.0).

## Summary

Định dạng xuất mới `psd`: một `.zip` chứa `<thứ tự>.psd` cho mỗi trang. Khi gộp chapter (E33) thì nằm trong
`01_ten_chapter/001.psd`. Các lớp từ dưới lên:
1. **"Ảnh gốc"**: **ẩn**.
2. **"Đã xoá chữ"**.
3. **"Vùng {n}: {bản dịch, rút gọn 40 ký tự}"**: mỗi vùng có chữ một lớp RGBA trong suốt.

Ảnh ghép trong tệp PSD trùng **từng điểm ảnh** với bản xuất PNG của cùng trang.

## Design Choice

- **Bộ ghi PSD tự viết** (`services/export/psd.py`, `struct` + numpy, không thêm thư viện):
  - Phiên bản 1, 8-bit RGB, nén RAW.
  - Lớp RGBA có kênh -1, cắt gọn theo vùng có alpha.
  - Tên lớp ghi bằng Pascal ASCII và khối `luni` UTF-16BE.
  - Ghi thẳng vào mục ZIP qua generator, không giữ mọi lớp trong RAM cùng lúc.
- **Một đường vẽ:** thân vòng lặp `draw()` tách thành `_ve_vung`. `draw()` dùng nó lên ảnh clean,
  `draw_lop_vung` dùng nó cho từng vùng lên canvas RGBA. E16, E65, E70, E75 đi chung đường.
  - Canvas RGBA dùng `alpha_composite`, vì `paste` làm alpha ở mép chữ bị bình phương.
  - **Đối chứng âm:** dùng `paste` thì ghép lại lệch 61 mức màu; bản sửa lệch ≤ 2.
- Ảnh gốc và ảnh clean qua `mo_nen()` (LANCZOS, cùng hàm với `draw()`), cùng cỡ canvas đã phóng.
- Cổng xuất, cảnh báo, đếm vùng tràn, `/download` giữ nguyên.

## New API / DB / State

- Enum Postgres `export_format` thêm `psd` (migration `0029_e78_psd`, down_revision `0027_e75`).
  Downgrade không gỡ giá trị: Postgres không có `DROP VALUE`.
- `POST /api/v1/projects/{id}/export` nhận `{"format":"psd"}`.

## Tests

- `test_export_psd.py`: 10 passed.
  - Bộ đọc trong test kiểm chữ ký `8BPS`, cỡ canvas, số lớp, tên lớp, cờ ẩn chỉ ở lớp ảnh gốc.
  - **Pillow mở được**: ảnh ghép đúng từng điểm ảnh, `im.layers` đúng tên và hộp bao.
  - Tích hợp DB: ZIP có đủ PSD, số lớp = 2 + số vùng có chữ, ảnh ghép = bản xuất PNG.
- Bộ xuất và vẽ: 137 passed. Migration, e33, e38: 24 passed.
- Frontend: 499 vitest, `vite build` OK.

## Remaining Limits

1. Lớp chữ là **raster**, chưa sửa chữ được trong Photoshop (chưa làm khối `TySh`).
2. **Chưa mở bằng Photoshop/Photopea thật.** Cần kéo `001.psd` vào photopea.com kiểm lớp và tên lớp có dấu.
3. Nén RAW nên tệp to: ~23 MB chưa nén mỗi trang 1200×1700, nhân thêm `he_so_ve²`. RAM worker khi xuất
   chưa đo.
4. Canvas > 30000px ⇒ lỗi `PsdQuaLon` (chưa làm PSB).
5. Pillow không đọc được lớp 1. Khi cả hai cạnh canvas đều lẻ, Pillow đọc lệch các lớp sau do byte đệm nó
   tự thêm (không có trong đặc tả). Photoshop không bị ảnh hưởng.
