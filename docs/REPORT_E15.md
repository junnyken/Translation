# Báo cáo Mini-Spec E15 — Hướng chữ, thoại dọc & SFX cách điệu

**Project:** Translation · **Phase:** E · **Ngày:** 2026-08-29
**Nền:** M1–M10 · E11–E14 (`6547d6c`)
**Trạng thái:** ✅ **ĐÓNG phần routing + giao diện** (2026-08-30) · ⛔ **dựng chữ dọc: BLOCKED**, xem §7

## 1. Summary

Trước E15, mọi vùng chữ đều được căn ngang. Chữ dọc trong bong bóng hẹp, SFX cách điệu, chữ
nghiêng — tất cả bị xử lý y như thoại ngang bình thường và cho ra kết quả trông "đã xong".

E15 thêm một lớp **nhận biết hướng chữ có bằng chứng** rồi **điều hướng rà soát**. Nó cố ý
**không** hứa dựng được chữ dọc: nhận ra hướng và dựng được chữ theo hướng đó là hai chuyện khác
nhau, và điều kiện để hứa thì chưa đủ (xem §3).

2 bảng đổi (1 cột thêm + 1 bảng mới), 2 migration, **779 test backend pass** (+33).

## 2. Audit Before Build — bốn phát hiện đổi hẳn thiết kế

Chi tiết số đo: `TEST_LOG § E15.1–2`.

**a) Nguồn bằng chứng mà spec trông đợi không tồn tại.** Spec dựa vào "CTD line polygon / text
mask". Adapter thật chỉ giải mã bbox; hai nhánh `seg`/`det` chưa bao giờ được đọc.

**b) Xoá chữ xong là mất luôn dấu vết hướng chữ.** Spec cho phép đo trên ảnh clean. Đo thật số
điểm ảnh tối trong từng vùng: thoại trong bong bóng tụt từ 1 499 xuống **0**, một vùng khác còn
**4**. Đó chính là việc M4 phải làm. ⇒ **không thể** đoán hướng từ ảnh clean.

**c) ⇒ Bằng chứng hình học duy nhất là đường bao dòng của OCR**, lấy lúc chữ còn nguyên.
PaddleOCR vẫn tính nó để sắp thứ tự dòng rồi **vứt đi**. E15 giữ lại (cột `line_polygons`).
Đây là lý do phải đổi mã lý do so với spec: dùng tên `ctd_line_geometry_*` sẽ là **nói sai về
nguồn bằng chứng**, nên đặt lại thành `ocr_line_geometry_*`, và luôn ghi kèm
`ctd_geometry_unavailable` cho đúng sự thật.

**d) Góc thô của `minAreaRect` không phân biệt được 0° với 90°.** Đo trên hình biết trước đáp án:
hình vẽ ở 0° cho `angle = 90.0` (w/h đảo), hình vẽ ở 90° **cũng** cho `angle = 90.0`. Phải chuẩn
hoá bằng `w`/`h`. Có test khoá lại cả tiền đề này.

## 3. Vì sao dựng chữ dọc để TẮT

Spec đặt điều kiện dừng: *thiếu ảnh mẫu chữ dọc hợp pháp, hoặc thiếu bằng chứng hình học tin cậy,
hoặc thiếu renderer giữ được dấu tiếng Việt ⇒ chỉ làm routing và ghi rõ **vertical rendering
blocked**; không được ship renderer dọc giả để đánh dấu E15 xong.*

| Điều kiện | Thực tế đo được |
|---|---|
| Ảnh mẫu chữ dọc có license rõ | **KHÔNG CÓ** — kho chỉ có Pepper&Carrot (tiếng Anh, chữ ngang) |
| Hình học từ bộ nhận diện | **KHÔNG CÓ** (mục 2a) |
| Renderer giữ được dấu tiếng Việt | **CÓ** — Pillow không có RAQM nên `direction="ttb"` ném `KeyError` rõ ràng, nhưng `regex` có sẵn và vẽ theo grapheme cho ra dấu nguyên vẹn (đã nhìn tận mắt) |

Thiếu 2/3 ⇒ `e15_vertical_render_enabled = False`. Vùng nhận ra là chữ dọc sẽ mang trạng thái
**`unavailable`** kèm lý do `vertical_renderer_unavailable` — nói thẳng "nhận ra rồi nhưng chưa
dựng được", chứ không giả vờ đã xử lý.

## 4. Design Choice

- **Tỉ lệ khung không bao giờ tự quyết.** Chữ `PHEW!` viết thưa theo chiều dọc vẫn là chữ ngang
  cách điệu. Tỉ lệ chỉ được ghi làm *tín hiệu*; có test khoá.
- **Các dòng cãi nhau thì nói là mâu thuẫn**, không bỏ phiếu đa số.
- **`unknown` là câu trả lời hợp lệ và được ưu tiên** hơn một kết luận tự tin mà sai.
- **Ràng buộc đặt ở tầng kiểu dữ liệu**, không phải ở tầng gọi hàm: không thể dựng được một
  `vertical_ttb + ready` thiếu bằng chứng, cũng không thể tạo `rotated_horizontal` mà quên ghi
  "v1 không tự xoay".
- **Không thêm task Celery** — chạy đồng bộ sau vùng an toàn, đúng tiền lệ E12/E14.

## 5. Đã làm / Chưa làm

| Phần | Trạng thái |
|---|---|
| Giữ lại đường bao dòng của OCR (cột + 2 đường ghi) | ✅ |
| Bộ chuẩn hoá góc + test trên hình biết trước đáp án | ✅ |
| Bộ nhận biết hướng + ràng buộc ở tầng kiểu dữ liệu | ✅ 27 test |
| Bảng `region_text_orientation` + migration | ✅ nâng/hạ cấp đều sạch |
| Nối vào dây chuyền (sau vùng an toàn, trước căn chữ) | ✅ |
| 3 endpoint chỉ đọc | ✅ |
| Đếm hướng chữ ở `export-warnings`, tách riêng | ✅ |
| Chốt chặn kiến trúc | ✅ 6 test |
| **Giao diện (nhãn, bộ lọc, khối giải thích, thẻ tổng hợp, cảnh báo xuất)** | ✅ **xong 2026-08-30** — §7 |
| **Test giao diện** | ✅ 63 test thành phần + 14 mục bấm thật trên Chromium |
| **Bộ dựng chữ dọc** | ⛔ cố ý chưa dựng — xem §3 và §7.2 |
| **Run A–D** | ✅ đã chạy 2026-08-30 — A/C/D đạt, **B bị chặn**, xem §7 |

## 6. Remaining Limits / Follow-ups

- **Chưa có ảnh mẫu chữ dọc hợp pháp** ⇒ chưa được tuyên bố hỗ trợ chữ dọc dưới bất kỳ hình thức
  nào. Có ảnh rồi mới bật cờ và chạy Run B.
- **manga-ocr (tiếng Nhật) không trả đường bao dòng** ⇒ đúng thứ tiếng có nhiều chữ dọc nhất lại
  là thứ tiếng E15 **không** có bằng chứng hình học. Kết quả sẽ là `unknown + needs_review`.
  Đây là giới hạn thật, không phải lỗi.
- Chữ nghiêng: chỉ điều hướng rà soát. Không xoay, không cong, không radial.
- Chưa có chỗ cho người tự đặt hướng — đúng phạm vi đã chốt.


---

# Phần 2 — Giao diện + Run A–D (2026-08-30)

**Nền:** E1 (`5bd3007`). **Kết quả:** 10/10 Run A/C/D · 14/14 giao diện trên Chromium ·
63 test thành phần. **Run B: BLOCKED.**

## 7. Audit — ba câu hỏi bắt buộc, trả lời bằng số đo

Mini-spec phần 2 yêu cầu trả lời rõ ba điểm trước khi dựng giao diện. Cả ba đều đo lại trên hệ
đang chạy, **không** lấy lại kết luận của báo cáo trước.

### 7.1 Renderer nào đã chọn cho `vertical_ttb`?

**Chưa chọn cái nào — và Option A đã bị loại bằng số đo.**

- **Option A** (Pillow `direction="ttb"` + libraqm): **không dùng được ở nơi cần dùng**, xem 7.2.
- **Option B** (vẽ theo grapheme): khả thi (`regex 2026.7.19` có sẵn trong worker, đã xác nhận
  giữ nguyên dấu tiếng Việt) nhưng **chưa dựng** — và cố ý chưa dựng, vì chưa có ảnh mẫu để đo
  thì dựng ra cũng không có cách nào biết nó đúng hay sai.

### 7.2 libraqm có trong worker không? — **KHÔNG. Và đây là phát hiện quan trọng nhất của phần này.**

```
PIL.features.check("raqm")
  worker  (nơi dựng chữ THẬT chạy) -> False
  api                              -> False
  máy dev (.venv)                  -> True     ← KHÁC
```

Thử vẽ thật với font trong `/fonts`:

```
worker : direction="ttb" -> KeyError: 'setting text direction, language or font features
                            is not supported without libraqm'   (cả tiếng Việt lẫn katakana)
máy dev: direction="ttb" -> VẼ ĐƯỢC              (cả tiếng Việt lẫn katakana)
```

Báo cáo trước ghi "Pillow không có RAQM" — đúng với worker, nhưng **không nói ra chỗ lệch**.
Chỗ lệch mới là thứ nguy hiểm: một người dựng Option B trên máy dev sẽ thấy chữ dọc vẽ ra đẹp,
merge, rồi nó hỏng im lặng trong worker. Đây đúng loại "test PASS giả vì máy dev có thư viện mà
production không có".

### 7.3 `vertical_ttb` trên dữ liệu thật là gì? — **chưa từng tồn tại một dòng nào.**

```
select count(*) from region_text_orientation;   ->  0        (trước khi chạy phần 2)
select count(*) from ocr_result
       where line_polygons is not null;         ->  0 / 97
```

**Lý do — và đây là lỗi vận hành, không phải lỗi mã:** container worker chạy liên tục **44 giờ**,
tức là khởi động **trước** khi E15 được commit. Celery nạp module lúc khởi động và không nạp lại,
nên toàn bộ mã E15 **chưa từng được thực thi một lần nào** dù tệp đã nằm trên đĩa (thư mục
`backend/` được mount làm volume).

⇒ Trước khi đo bất cứ thứ gì, phải `docker compose restart worker`. Sau khi nạp lại, dữ liệu thật
xuất hiện ngay ở lượt chạy pipeline kế tiếp.

## 8. Giao diện đã dựng (Section D của E15 gốc)

| Phần | Tệp | Ghi chú |
|---|---|---|
| D1 huy hiệu + bộ lọc | `App.jsx`, `lib/status-presentation.js` | huy hiệu hướng chữ đứng **riêng**, cạnh huy hiệu căn chữ/chất lượng/nhất quán/vùng an toàn |
| D2 khối giải thích | `components/OrientationBox.jsx` | dịch 15 mã lý do 1:1; lưới cột chữ **chỉ** hiện khi `status=ready` |
| D3 thẻ tổng hợp | `components/OrientationSummaryCard.jsx` | có ô riêng cho "chưa kiểm" |
| D3 cảnh báo xuất | `components/ExportWarningModal.jsx` | khối hướng chữ là khối **thứ năm**, tách khỏi tràn khung / E12 / E13 / E14 / bản quyền |
| D4 test | `components/orientation.test.jsx` | 63 test |

Dùng lại `StatusBadge` của E11 (thêm prop `dienGiai` cho các bảng không tra được bằng
`(loai, trangThai)`), dùng lại khuôn khối giải thích của E14. **Không** dựng editor mới.

Ba luật của giao diện, mỗi luật có test canh:

1. **`vertical_ttb + ready` là nhãn duy nhất được mang sắc thái thành công.** Mọi trạng thái
   khác của chữ dọc đều ra "Chữ dọc — cần kiểm tra thủ công".
2. **"Chưa kiểm" không bao giờ gộp vào "không sao".** Backend trả 404 cho vùng chưa phân tích;
   giao diện dịch thành `null` và bộ lọc "Cần kiểm tra hướng chữ" **có** bắt các vùng đó.
3. **Mã lý do lạ hiện nguyên mã thô**, không bị nuốt — backend thêm mã mới thì lần ra được ngay.

## 9. Run A–D — số đo thật

Chapter đo: `79b07f20-5afd-4e85-a816-7697240191b6` (3 trang Pepper&Carrot, 9 vùng).

### Run A — chữ ngang không hồi quy ✅ 6/6

| Mục | Kết quả |
|---|---|
| Chạy lại pipeline sinh đường bao dòng THẬT | ✅ 6 vùng |
| Hướng chữ được tính cho mọi vùng | ✅ |
| Truyện chữ ngang được nhận đúng là chữ ngang | ✅ 5 vùng |
| **0** vùng chữ ngang bị gọi nhầm thành chữ dọc | ✅ |
| Trang vẫn tới `typeset_done` (không hồi quy M6) | ✅ |
| `GET /pages/{id}/orientation-summary` trả đúng khuôn | ✅ |

### Run B — chữ dọc tiếng Nhật: **BLOCKED** ⛔

Bốn vật cản **độc lập**, mỗi cái đủ để chặn một mình:

1. **Dữ liệu** — không có ảnh chữ dọc tiếng Nhật license rõ trong kho.
2. **Kiến trúc** — `MangaOCREngine.recognize()` trả `(text, None)`: **không có đường bao dòng**.
   Mà `analyzer` chỉ tới được `vertical_ttb` qua `ocr_line_geometry_vertical`.
   ⇒ **Trang tiếng Nhật luôn ra `unknown`, kể cả khi có ảnh hoàn hảo.**
3. **Môi trường** — libraqm vắng mặt trong worker (§7.2).
4. **Glyph** — không có font nào trên máy (kể cả trong worker) có glyph kana/kanji.

Vật cản 2 là cái đáng chú ý nhất: **có ảnh cũng không mở khoá được Run B.** Đây là giới hạn cấu
trúc, không phải thiếu dữ liệu. Muốn làm thật thì cần một mini-spec riêng cho nguồn hình học
tiếng Nhật (ví dụ chạy PaddleOCR `lang='japan'` song song chỉ để lấy đường bao dòng).

Chốt chặn đã đo: `select count(*) ... where orientation='vertical_ttb' and status='ready'` → **0**.

**Kết luận: `E15 — vertical rendering: BLOCKED`. Chỉ đóng phần routing + giao diện.**

### Run C — SFX / chữ nghiêng ✅ 3/3, nhưng mẫu quá nhỏ để kết luận tần suất

| Mục | Kết quả |
|---|---|
| Không vùng nào bị bỏ qua im lặng | ✅ 9/9 vùng đều có phán quyết |
| Mọi vùng nghiêng ghi rõ "chỉ rà soát thủ công" | ✅ (0 vùng thiếu mã) |
| Mọi vùng nghiêng kèm góc đã chuẩn hoá | ✅ (0 vùng thiếu góc) |

**Tần suất đo được trên toàn bộ dữ liệu đã phân tích: `horizontal_ltr=7 · unknown=2 ·
rotated_horizontal=0`.**

⚠️ Spec yêu cầu tối thiểu **5 ví dụ SFX**; dữ liệu thật cho **0**. Hai phép C2/C3 vì thế là
**đúng nhưng rỗng** (vacuously true) — chúng không chứng minh được đường xử lý chữ nghiêng chạy
đúng, chỉ chứng minh không có vùng nào vi phạm. n=9 quá nhỏ để nói bất cứ điều gì về tần suất
gặp chữ nghiêng trong truyện thật.

⇒ **Không đủ căn cứ mở E16.** Muốn mở thì phải đo trên tập ảnh có SFX thật trước.

### Run D — sửa tay + cảnh báo xuất ✅ 4/4

| Mục | Kết quả |
|---|---|
| `GET /projects/{id}/export-warnings` trả 200 | ✅ |
| Khối hướng chữ **tách riêng** trong cảnh báo | ✅ `{vertical_rendered: 0, review: 0, unknown: 2}` |
| Sửa tay vùng (M7) vẫn chạy | ✅ HTTP 200 |
| Xuất chapter (M8) vẫn chạy | ✅ HTTP 202 |

### Đo giao diện trên Chromium ✅ 14/14

Bấm thật trên `http://localhost:5174/#page=98e5c3bc…` (4 vùng: 3 ngang + 1 chưa rõ):

- Số trên thẻ tổng hợp **khớp đúng CSDL** (3 ngang / 1 chưa rõ).
- Mỗi vùng có ≥2 huy hiệu tách biệt (căn chữ + hướng chữ) — không gộp một icon.
- Bộ lọc đủ 5 mục; "Chữ dọc" lọc còn 0 và **nói rõ** thay vì để bảng trắng; "Cần kiểm tra hướng
  chữ" bắt đúng 1 vùng.
- Khối giải thích hiện căn cứ + lý do **bằng tiếng Việt**, không lộ mã máy.
- Không có vùng dọc `ready` ⇒ công tắc lưới cột chữ **vắng mặt** đúng như thiết kế.
- 0 lỗi JS.

## 10. Remaining Limits sau phần 2

1. **Chữ dọc: BLOCKED.** Bốn vật cản ở §9/Run B. Không được quảng bá là đã hỗ trợ dưới bất kỳ
   hình thức nào. Trạng thái thực tế của mọi vùng dọc (nếu có) là `unavailable`.
2. **Chưa đủ căn cứ mở E16** — dữ liệu thật cho 0 vùng chữ nghiêng trên n=9.
3. **Chưa có ảnh mẫu tiếng Nhật** — và kể cả có, vật cản 2 vẫn chặn.
4. **Chưa có chỗ cho người tự đặt hướng chữ** — đúng phạm vi đã chốt, không tự thêm.
5. **Bẫy vận hành đã ghi lại:** worker không nạp lại mã Python khi tệp đổi. Mọi mini-spec đụng
   vào worker phải `docker compose restart worker` trước khi đo, nếu không sẽ đo nhầm mã cũ.
