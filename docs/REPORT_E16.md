# Báo cáo Mini-Spec E16 — Đặt chữ nghiêng

**Project:** Translation · **Phase:** E · **Ngày:** 2026-09-11
**Nền:** `48a8255` (sau E23/E24 LIVE)
**Trạng thái:** **nửa NGHIÊNG xong + kiểm live** · **nửa DỌC vẫn BỊ CHẶN, không sửa được bằng code**

## 1. Summary

`FEATURES.md` ghi E16 là *"Chưa được duyệt; chưa đủ bằng chứng thật"*. Audit tìm ra lý do chính xác
và nó **đã đổi** kể từ E15:

| | E15 (2026-08-29) | nay (sau lượt 24 trang của E23) |
|---|---|---|
| Mẫu `rotated_horizontal` | **0** — `REPORT_E15 §11.4` gọi Run C là "pass RỖNG" | **11 mẫu thật** |
| Mẫu `vertical_ttb` | 0 | 3 — nhưng **cả 3 là dương tính giả** (§3.2) |

⇒ Cổng chặn của nửa **nghiêng** đã mở (có dữ liệu để kiểm). Cổng chặn của nửa **dọc** thì không —
nó nằm ở tầng hợp đồng OCR, không phải ở chỗ thiếu ảnh.

E16 làm nửa nghiêng, và **hai chỗ có thể sai âm thầm đều được ĐO chứ không đoán** (§4).

## 2. Audit Before Build

### 2.1 `rotation_degrees` KHÔNG phải góc để xoay chữ

Đây là phát hiện quan trọng nhất. `chuan_hoa_goc` của E15 quy góc về **[0, 180)** và đó là hướng
của **cạnh dài** — một **đường vô hướng**. Docstring `la_ngang` nói thẳng: *"Gần 0 hoặc gần 180 đều
là nằm ngang — 179° không phải là 'gần như dựng đứng'"*. Và chính `RegionTextOrientation` ghi:
*"Chỉ có nghĩa với `rotated_horizontal`, và v1 **không** dùng nó để xoay chữ."*

11 góc thật trong CSDL:

```
25.0 · 66.6 · 126.9 · 149.0 · 158.6 · 160.2 · 162.2 · 165.0 · 165.4 · 166.0 · 166.7
```

**8/11 nằm trong 149-167°.** Xoay chữ đúng theo những con số đó ⇒ 8 vùng ra chữ **gần như lộn
ngược**, vì 165° và −15° là **cùng một đường**, chỉ đo từ đầu kia.

### 2.2 Renderer chưa có khả năng xoay

`typeset/preview.py` vẽ thẳng bằng `ImageDraw.multiline_text`. Không có `rotate`, không có
transform. Nên E16 phải thêm khả năng đó, và phải giữ được bất biến *"chữ bị cắt gọn trong khung
của chính nó"* mà M6/E14 dựng lên.

### 2.3 Ngưỡng của tôi ban đầu KHÔNG nhất quán với E15 — và test guard đã che mất

Tôi đặt `NGUONG_XOAY_DO = 8.0`, trong khi E15 dùng `e15_angle_tolerance_deg = 12.0` cho
`la_ngang()`. Có nghĩa cửa sổ 8-12° mà **E15 gọi là NGANG nhưng E16 lại xoay** — hai tầng nói hai
điều khác nhau về cùng một vùng.

Test chéo lẽ ra bắt được, nhưng nó tra `orientation_horizontal_tolerance_deg` — **một tên không tồn
tại** — nên `getattr` trả `None` và test tự `skip`. **Một guard bị skip là một guard không canh
gì.** Đã sửa ngưỡng về 12.0 và cho test đọc thẳng thuộc tính: thiếu là ĐỎ.

## 3. Nửa DỌC — vì sao KHÔNG làm, và nó không phải lựa chọn của tôi

### 3.1 Chặn ở tầng hợp đồng OCR (tiếng Nhật)

`REPORT_E15 §11.2` đã ghi, và nay đọc lại vẫn đúng: `MangaOCREngine.recognize()` chỉ trả
`(text, None)`. Lớp này **không có** `recognize_with_layout`, nên hợp đồng OCR cho tiếng Nhật
không mang hình học dòng chữ nào. Mà analyzer chỉ tới được `vertical_ttb` qua mã
`ocr_line_geometry_vertical` — không có nguồn đó thì **không có đường nào** đặt
`vertical_ttb + ready`, kể cả với ảnh tiếng Nhật hoàn hảo.

### 3.2 Và 3 mẫu `vertical_ttb` hiện có đều là DƯƠNG TÍNH GIẢ

| Chữ | Khung | Lý do gắn cờ |
|---|---|---|
| `?!` | 36×45 | `bbox_aspect_vertical_signal` |
| `?!` | 37×48 | `ocr_line_geometry_vertical` |
| `SXXX` | 37×76 | `bbox_aspect_vertical_signal` |

Một dấu `?!` trong khung 36×45 **không phải** tategaki — nó bị gọi là "dọc" vì khung cao hơn rộng.
Xoay 90° những vùng này là làm ảnh **xấu đi**. Cả 3 đều mang `vertical_renderer_unavailable`.

⇒ Nửa dọc không có mẫu thật nào để phục vụ, và đường tới `ready` bị chặn ở tầng dưới. Làm nó bây
giờ là dựng một tính năng không có dữ liệu để kiểm đúng-sai — đúng sai lầm mà E25 đã tốn cả buổi
để bác bỏ.

## 4. Hai phép ĐO thay cho hai lần đoán

### 4.1 Quy ước góc: [0,180) → (−90, 90]

`goc_xoay_chu()` quy về khoảng *gần nằm ngang nhất*, nên chữ **không bao giờ** lộn ngược.

Giới hạn phải nói rõ: `cv2.minAreaRect` trả hình chữ nhật **vô hướng**, nên dữ liệu hiện lưu
**không mang** chiều đọc trên/dưới. Với chữ thật sự đọc ngược (hiếm, nhưng có), quy ước này xoay
sai chiều. Muốn biết chắc thì phải lưu **đa giác dòng chữ có thứ tự** từ OCR — PaddleOCR có trả,
nhưng `RegionTextOrientation` chỉ lưu góc đã chuẩn hoá. Đó là slice khác.

Chiều sai của quy ước này là chiều an toàn: **không bao giờ tệ hơn** hiện trạng (không xoay gì).

### 4.2 Chiều xoay: dấu NGƯỢC với `goc_xoay_chu`

Đây là chỗ thứ hai có thể sai âm thầm — sai chiều thì chữ nghiêng **ngược nét vẽ**, mà ảnh vẫn
"trông có xoay" nên rất dễ bỏ qua. Đo bằng cách dựng dải chữ ngang, xoay ảnh một góc **biết trước**
rồi cho chính `chuan_hoa_goc` đo lại:

```
ảnh xoay +15° (cv2 dương = ngược kim đồng hồ)  ->  chuan_hoa_goc 165.0°  ->  goc_xoay_chu -15.0°
ảnh xoay -15°                                  ->  chuan_hoa_goc  15.0°  ->  goc_xoay_chu +15.0°
ảnh xoay +40°                                  ->  chuan_hoa_goc 140.0°  ->  goc_xoay_chu -40.0°
ảnh xoay -40°                                  ->  chuan_hoa_goc  40.0°  ->  goc_xoay_chu +40.0°
```

`PIL.Image.rotate(dương)` cũng ngược kim đồng hồ ⇒ góc cho PIL là **`−goc_xoay_chu`**.
`goc_pil()` làm việc đó, và có test **vòng kín qua cv2** chứng minh dấu đúng mà không phải tin
lời tôi.

## 5. Changed Files

| Tệp | Việc |
|---|---|
| `backend/app/services/typeset/xoay.py` | **MỚI** — `goc_xoay_chu`, `goc_pil`, `nen_xoay` |
| `backend/app/services/orientation/apply.py` | **MỚI** — `nap_goc_nghieng()`, theo khuôn `safearea/apply.py` |
| `backend/app/services/typeset/preview.py` | `RegionDraw.rotation_degrees` + `_ve_xoay()` |
| `backend/app/core/config.py` | `e16_xoay_chu_nghieng: bool = True` |
| `backend/app/workers/tasks.py` | Nạp góc vào `RegionDraw` |
| `backend/tests/test_e16_xoay_chu_unit.py` | **MỚI** — 37 test cho phép đổi góc |
| `backend/tests/test_e16_ve_chu_xoay_unit.py` | **MỚI** — 20 test cho việc vẽ |

Không migration. Không đổi enum. Không đổi hợp đồng API.

## 6. Thu nhỏ cỡ chữ — đánh đổi có chủ đích

Hộp bao của chữ sau khi xoay **lớn hơn** chữ ngang (`w·|cosθ| + h·|sinθ|`). Cỡ chữ đã được bộ fit
tính cho khung ngang, nên xoay nguyên cỡ đó là bị ô cắt **gọt mất góc**. `_ve_xoay` thu nhỏ theo
đúng tỉ lệ hình học.

Thu nhỏ bằng cách **vẽ lại ở cỡ font nhỏ hơn**, KHÔNG co ảnh bitmap — co bitmap làm nét chữ nhoè,
mà đây là bước cuối người dùng nhìn thấy.

Hệ quả nhìn thấy được: chữ nghiêng **nhỏ hơn** chữ ngang cùng vùng, rõ nhất ở góc gần 45°. Đó là
cái giá của việc không gọt mất chữ, không phải lỗi.

## 7. Tests

```
$ pytest tests/test_e16_xoay_chu_unit.py -q        37 passed
$ pytest tests/test_e16_ve_chu_xoay_unit.py -q     20 passed
```

Ba test đáng nói riêng:

- **`test_VONG_KIN_do_lai_muc_ra_dung_goc`** — vẽ ở góc biết trước rồi **đo lại mực trên ảnh** bằng
  đúng công cụ E15 dùng. Phép duy nhất bắt được lỗi sai chiều.
- **`test_sai_chieu_se_bi_bat`** — chứng minh phép trên **có tác dụng**: góc đảo dấu phải làm nó đỏ.
  Không có test này thì không biết dung sai 12° có rộng đến mức bỏ qua cả lỗi sai chiều.
- **`test_gan_nam_ngang_KHONG_xoay`** — vùng dưới ngưỡng phải cho ảnh **giống từng pixel** với bản
  không xoay. Bất biến "tắt cờ là không có nhánh nào đổi hành vi".

## 8. Live Verification — so với NÉT VẼ GỐC

Vẽ lại trang thật `0d47b661` (14 vùng, 3 vùng nghiêng). Ảnh đổi đúng ở ba vùng đó và chỉ ở đó:

```
tổng pixel khác cả trang: 6918
  vùng 5ea82bf8  162.9°  2585 pixel khác trong khung  chữ='Bám\nvào'
  vùng 34a57f8b  126.9°  2724 pixel khác trong khung  chữ='Kêu\nvang'
  vùng 7ed91cf0  166.0°  1921 pixel khác trong khung  chữ='tiếng kêu'
```

**Nhưng con số không đủ để kết luận** — phải so với **ảnh GỐC**, nơi chữ SFX còn nguyên, mới biết
chiều xoay có khớp nét vẽ không (ảnh clean đã xoá chữ nên không còn gì để so):

| Góc | Chữ gốc | E16 vẽ ra |
|---|---|---|
| 126,9° | `Clang` chúc **mạnh xuống phải** | `KÊU VANG` chúc xuống phải — **khớp** |
| 162,2° | `Cling` nghiêng nhẹ | `BÁM VÀO` nghiêng nhẹ cùng chiều |
| 166,0° | `Clong` gần ngang | `TIẾNG KÊU` gần ngang |

⇒ Chiều xoay khớp nét vẽ trên 3/3 vùng thật. Nếu đoán dấu thì cả ba sẽ nghiêng **ngược**.

**Một lỗi đo của tôi, ghi lại:** lượt kiểm đầu tôi đo góc mực trong từng vùng và thấy **giống hệt
nhau** giữa có-xoay và không-xoay (90,0° vs 90,0°), suýt kết luận là chưa xoay gì. Phép đo đó vô
dụng ở đây: các vùng nhỏ (85×97) và chữ là khối 2 dòng gần **vuông** (`Bám\nvào`), nên
`minAreaRect` của khối gần vuông cho góc vô nghĩa. Đếm pixel khác + xem ảnh mới là phép đúng cho
một tính năng thị giác.

## 9. Remaining Limits

- **Nửa dọc vẫn bị chặn** (§3) — không sửa được bằng code trong phạm vi E16. Mở nó cần
  `recognize_with_layout` cho `MangaOCREngine`, tức đổi hợp đồng OCR.
- **Chiều đọc trên/dưới không có trong dữ liệu** (§4.1). Quy ước "gần nằm ngang nhất" sẽ sai với
  chữ thật sự đọc ngược. Muốn chắc thì phải lưu đa giác dòng chữ có thứ tự.
- **Chưa kiểm trên chữ nghiêng THOẠI**, chỉ trên SFX: cả 11 mẫu thật đều là SFX (`Clang`, `CRACK!!`,
  `Shklak!`, `PHRoooOwwoww!!!`) hoặc bảng chữ (`APPROVED FOR`). Chưa có mẫu thoại nghiêng nào.
- **Chưa deploy.** Cần một lượt kiểm trên production trước, vì đây là thay đổi **nhìn thấy được**
  ở đầu ra cuối cùng.
- Chữ nghiêng nhỏ hơn chữ ngang (§6) — đánh đổi, không phải lỗi.
- Cờ rà soát của E15 **không** bị xoá: vùng nghiêng vẫn mang `needs_review` +
  `rotated_text_manual_review_only`. Người dùng vẫn được nhắc soi lại.
