# REPORT E38 · E39 · E40 — sửa ba lỗi do lượt chạy thật E35 phơi ra

**Ngày:** 2026-09-14 · **Trạng thái:** mã xong, test xanh, **CHƯA deploy** (mục Live
Verification còn `NULL` cho tới khi có bằng chứng từ host)

## Summary

E35 chạy một chapter tiếng Anh thật (ep39, 12 trang) trên production. Kết quả đóng được ba món nợ
cũ (E34, E16, E18) nhưng cũng phơi ra ba lỗi mà **không bộ test nào bắt được**, vì mã chạy đúng
như đã viết — chỉ là giả định nền sai:

| | Lỗi | Giả định sai |
|---|---|---|
| **E38** | Trang không có chữ bị loại khỏi file xuất ⇒ **truyện xuất ra thiếu trang** | "trang chưa chèn chữ = trang chưa xong" |
| **E39** | Trang bạt tài trợ đẻ ra danh xưng rác, làm ngập màn Thuật ngữ | "mọi vùng chữ đọc được đều là nguồn danh xưng" |
| **E40** | File `.cbz` tải về không mở được trên máy người dùng | "chọn đúng định dạng chuẩn là xong việc" |

Điểm chung: cả ba chỉ lộ ra khi có **một chapter thật có trang không phải truyện** và **một người
thật tải file về máy thật**. Đây là lần thứ hai trong dự án bấm-thử-thật tìm ra thứ 1500 test
không tìm ra.

## Audit Before Build

### E38 — bằng chứng và phân biệt an toàn

Giao diện gắn nhãn **"Hỏng"** cho trang 2 (`E39P02`) và cổng xuất báo *"2 trang sẽ bị BỎ QUA vì
chưa chèn chữ xong"*. Nhưng `E39P02` là **trang tranh thuần, không một bong bóng thoại nào** —
`no_region` là hành vi ĐÚNG, không phải lỗi.

Trước khi sửa phải chắc không mở cửa cho trang lỗi thật đi ra file. Phân biệt đó CÓ THẬT trong mã:

```
detect NỔ        -> PageStatus.detection_failed       (tasks.py:140)
detect CHẠY XONG -> PageStatus.detected, kể cả 0 vùng (tasks.py:206)
```

Nên `detected` **+ 0 vùng** nghĩa là *máy đã xem và xác nhận không có chữ* ⇒ ảnh gốc chính là
trang hoàn thiện. `detection_failed` thì vẫn phải bị bỏ.

### E39 — luật chạy đúng trên dữ liệu sai loại

Người dùng bấm "Tìm trong chapter" và nhận về:

| danh xưng | số lần | trang |
|---|---|---|
| David | 8 | 12 |
| Alex | 7 | 12 |
| AXE | 7 | **3, 5, 6, 7** |
| Christian | 7 | 12 |
| Michael | 7 | 12 |
| Paul | 6 | 12 |

Trang 12 là **trang bạt liệt kê người tài trợ**. Năm trong sáu mục là tên ê-kíp/người tài trợ,
chỉ ở trang 12, không một lần nào trong truyện. Ứng viên thật duy nhất (`AXE`) bị chôn giữa
chúng. Mỗi mục còn kéo theo ba trích dẫn dài **1389 ký tự**, nên trang màn hình dài hàng chục
nghìn ký tự.

Đây **không** phải lỗi của luật "viết hoa giữa câu": tên người tài trợ đúng là tên riêng viết
hoa. Lỗi ở **nguồn** — E17 coi mọi vùng chữ đọc được là lời nhân vật.

### E40 — tính năng đã có, lời chỉ đường thì không

`ExportFormat.zip` đã có từ M8 và `ExportPanel` đã có mục chọn ZIP. Nhưng `cbz` là **mặc định**
và dòng gợi ý chỉ nói *"đọc bằng ứng dụng truyện tranh"* — không nói thẳng rằng **Windows/macOS
bấm đúp sẽ không ra gì**, và không chỉ đường ra khỏi tình huống sau khi file đã tải về.

## Design Choice

### E39 — chọn phép đo, không chọn danh sách chặn

Ý đầu tiên là chặn theo từ (`"David"`, `"Alex"`…). Bỏ, vì đó là trò đuổi bắt không hồi kết — đúng
bài học đã ghi ở `_theo_sau_danh_xung_hop_le` khi luật cũ bắn vào `"of"` trong *King of Chaosah*.
Phải tìm một **thuộc tính cấu trúc** phân biệt danh sách với lời nói.

**Bản đầu của mini-spec này SAI, và phép đo bắt được trước khi deploy.** Bản đầu chốt trần 20 từ
dựa trên **n = 3 lời thoại** của một chapter. Người dùng chặn lại, bắt viết mục "rủi ro sai" —
viết ra mới thấy chưa đo *bất kỳ* bong bóng ≥20 từ nào. Đo lại trên **211 vùng `OCRStatus.ok`
tiếng Anh thật** (3 chapter, DB dev, đọc thuần):

| nhóm (chỉ xét vùng ≥ 100 từ) | tỉ lệ từ nối |
|---|---|
| 6 khối trang bạt (146–723 từ) | **0,0 – 5,7%** |
| — ngưỡng **15%** — | lề 9,3 điểm (2,6×) |
| 4 vùng ≥ 20 từ được giữ (22–26 từ) | **19,2 – 54,2%** |
| trong đó lời thoại thật | 50,0 – 54,2% |

**Phân bố SỐ TỪ mới là phát hiện quyết định:**

```
vùng >= 20 từ:   10 / 211 (4,8%)     <- luật chỉ chạm 5% số vùng
nhóm được GIỮ:   22, 23, 24, 26 từ
nhóm bị BỎ:      146, 194, 402, 498, 503, 723 từ
                 ^^^ khoảng trống 26 -> 146 RỖNG HOÀN TOÀN
```

Đã thử trần 20/40/60/80/100/120/146 — **tất cả cho cùng 6 vùng bị bỏ**. Nên trần chốt **100 từ**,
không phải 20: không mất gì trên dữ liệu đã đo, mà có lề **3,8×** so với lời thoại dài nhất từng
thấy. Lề đó bảo vệ chapter CHƯA đo, và nó không phải lý thuyết — xem mục (d).

**Bằng chứng mạnh nhất — chạy lại trên chapter thật** (`04e7b2c1`, 163 vùng có chữ), lấy ứng viên
chốt (≥2 lần) đúng như `rut_ung_vien`:

| | ứng viên | top |
|---|---|---|
| không lọc | **726** | Alex(23), Michael(14), Alexander(13), Daniel(12) |
| có lọc | **25** | Potions(9), Chaosah(7), Pepper(6), Carrot(5), King(3) |

726 → 25, và 25 cái còn lại **đúng là thuật ngữ của truyện**. Trên hai chapter **không** có trang
bạt: không đổi một ứng viên nào — phép chứng minh luật không chạm vào chapter bình thường, thứ mà
đo trên một chapter duy nhất không bao giờ nói được.

Hai kết luận về tín hiệu:

1. **Viết hoa CHẾT** — cả hai loại ~100%. Đúng lý do nhánh `toan_hoa` của E17.3 phải tồn tại;
   nhưng nhánh đó chỉ đổi luật, không đổi *nguồn*.
2. **Tỉ lệ từ nối tách sạch hai đám.** Người nói thì có `and/you/the/that`; danh sách tên thì không.

Hai ràng buộc đặt về phía an toàn:

- **Chỉ xét khối ≥ 100 từ** (con số ĐO, xem trên). Trần theo *số từ*, không theo độ dài ký tự.
- **Chỉ dùng cho `en`.** `_CHAN_EN` là từ nối tiếng Anh; chữ Nhật/Trung cho 0% nên mọi vùng đủ
  dài sẽ bị bỏ sạch. Thà không lọc còn hơn lọc bằng ngưỡng vay từ ngôn ngữ khác — ngưỡng Latin áp
  cho CJK đã sai hai lần (`vung_bao`, `assessor`).

### (d) Rủi ro sai — ca false negative ĐÃ tìm ra và ĐÃ sửa

Người dùng hỏi thẳng: có lời thoại thật nào ít từ nối bị loại oan không. **Có, và bản đầu của tôi
loại oan nó thật.** Ca đó là nhân vật đọc một danh sách trong truyện:

```
"POTIONS, HERBS, CAULDRON, MANDRAKE ROOT, DRAGON SCALE, PHOENIX FEATHER, MOONSTONE, …"
21 từ · 0,0% từ nối

tran  20: -> BỊ LOẠI OAN
tran 100: -> được giữ
```

Đây là lý do trần nâng lên 100, và có test canh đúng ca này
(`test_loi_thoai_cut_lun_dai_KHONG_bi_loai_oan`). Test tự canh cả tiền đề của nó (`>20 từ` và
`<15% từ nối`) nên nếu mẫu trôi thành vô hại thì nó đỏ chứ không xanh giả.

**Giới hạn còn lại của cỡ mẫu:** 211 vùng, 3 chapter, **một tác giả** (Pepper&Carrot). Chưa có
chapter tiếng Anh của tác giả khác, nên chưa biết văn phong khác có bong bóng ≥100 từ hay không.
Nếu có, nó sẽ bị xét — và chỉ được giữ nếu ≥15% từ nối.

Lọc **sau** nhánh `chua_doc_chu`: mọi vùng đều là danh sách ⇒ `khong_thay` ("đã đọc mà không có gì
dùng được"), KHÔNG phải `chua_doc_chu`. Cùng phân biệt ba-trạng-thái mà E17 dựng ra để bảo vệ.

Trích dẫn thì cắt cửa sổ 160 ký tự quanh chỗ khớp, dùng lại `span` **đã có sẵn** từ E17.4 (nó
sinh ra để khử đếm trùng) — không thêm dữ liệu mới. Bất biến: **không bao giờ cắt vào trong
`span`**.

### E38 — sửa hai chỗ, không phải một

`_thu_thap_trang` quyết định **nội dung file**; `thong_ke_xuat` quyết định **con số xem trước**.
Chỉ sửa chỗ đầu thì con số nói một chuyện mà file chứa chuyện khác — tệ hơn thiếu trang, vì người
dùng không có cách nào biết. Sửa cả hai, và có test canh đúng sự khớp đó.

### E40 — nói thật + đúng một cú bấm

Không đổi mặc định sang ZIP: CBZ là định dạng đúng cho ứng dụng đọc truyện, đổi mặc định là lấy
mất thứ đa số người dùng cần. Thay vào đó: nói thẳng CBZ **không mở sẵn được** *trước* khi xuất,
và sau khi xuất xong thì cho **một cú bấm "Xuất lại bằng ZIP"**.

Bẫy phải tránh: `setDinhDang('zip')` rồi gọi `xuat()` sẽ gửi lại đúng `cbz`, vì state React chỉ
đổi ở lượt vẽ sau. Nên `xuat` nhận định dạng **tường minh** (`xuat(false, 'zip')`).

## Changed Files

| Tệp | Việc |
|---|---|
| `backend/app/workers/tasks.py` | E38 — `trang_khong_co_chu()`; nối vào `_thu_thap_trang` + `thong_ke_xuat` |
| `backend/app/services/consistency/ungvien.py` | E39 — `la_khoi_liet_ke()`, `_cat_trich_dan()`, 3 hằng số có số đo, lọc trong `rut_ung_vien` + `rut_tin_hieu_xung_ho` |
| `backend/app/schemas/common.py` | E39 — `so_vung_liet_ke` trên 2 response |
| `backend/app/api/v1/routes.py` | E39 — trả trường mới |
| `frontend/src/components/consistency/TermCandidatePanel.jsx` | E39 — khai số khối đã bỏ + giải thích dấu hiệu |
| `frontend/src/components/consistency/VoiceProfileManager.jsx` | E39 — cùng việc cho bảng xưng hô |
| `frontend/src/components/ExportPanel.jsx` | E40 — lời chỉ đường + "Xuất lại bằng ZIP" + `xuat()` nhận định dạng tường minh |
| `docs/{ARCH,API,FEATURES,TEST_LOG}.md` | ARCH §E17.7–E17.8; API 2 endpoint; FEATURES E17 + M8 |

## New API / DB / State

- **API:** thêm `so_vung_liet_ke: int = 0` vào `TermCandidatesResponse` và `VoiceSignalsResponse`.
  Có mặc định ⇒ **tương thích ngược**, client cũ không vỡ.
- **DB:** không migration nào. E38/E39/E40 không thêm bảng, cột, enum.
- **State:** không trạng thái mới. E38 **dùng lại** phân biệt `detected` vs `detection_failed` đã
  có sẵn thay vì thêm giá trị mới.

## Tests

| Bộ | Số | Kết quả |
|---|---|---|
| `test_e38_trang_khong_co_chu_integration.py` | 13 | xanh |
| `test_e39_khoi_liet_ke_unit.py` | 17 | xanh, `pytest_exit=0` |
| `test_e17_integration.py` (thêm lớp E39) | 25 (5 mới) | xanh, `pytest_exit=0` |
| `mo-duoc-file-xuat.test.jsx` (E40) | 4 | xanh |
| `e17.test.jsx` (thêm E39) | 18 (3 mới) | xanh, `vitest_exit=0` |

Ba phép canh đáng nói, và vì sao chúng cần thiết:

- **Chống rỗng nghĩa** — `test_khong_loc_thi_ten_e_kip_thanh_ung_vien` chứng minh mẫu THẬT đẻ ra
  `david`/`alex` khi không lọc. Không có nó thì mọi test lọc đều có thể xanh vì mẫu vô hại.
- **Ngưỡng có lề hai phía** — `test_nguong_con_le_ve_ca_hai_phia` so ngưỡng với *đám* cao nhất và
  *đám* thấp nhất, không so từng mẫu. Ngưỡng đúng tình cờ thì đổi dữ liệu là đỏ mà không ai hiểu.
- **Tính chất, không phải một ca** — `_cat_trich_dan` thử ≥10 vị trí khác nhau trong cùng khối
  dài; mỗi lần phải giữ được chỗ khớp và không vượt 162 ký tự.

**Một lỗi của chính tôi trong lượt này, ghi lại:** lượt chạy test nối đầu tiên báo `exit code 0`
nhưng thực ra có **2 test ĐỎ** — mã thoát đó là của `tail` trong chuỗi ống, không phải của
`pytest`. Đúng cái bẫy đã ghi trong bộ nhớ. Lượt sau đo bằng `pytest ... > file; echo
"pytest_exit=$?"`. Hai test đỏ đó là do test của tôi gọi sai tên trường (`term` thay vì
`source_term`), không phải lỗi mã sản phẩm — nhưng nếu tin `exit 0` thì đã commit mà không biết.

## Live Verification

`NULL` — chưa deploy. Sẽ điền sau khi có bằng chứng THẬT từ host:

1. Xuất lại ep39 ⇒ phải ra **11/12 trang** (E38 đưa trang 2 vào; trang 12 vẫn hỏng vì
   `crop_too_large` — việc riêng, chưa làm).
2. Bấm "Tìm trong chapter" ⇒ `David`/`Alex`/`Christian`/`Michael`/`Paul` **biến mất**, `AXE` còn,
   và hiện dòng *"Bỏ qua N khối chữ không phải lời thoại"*.
3. Bấm "Xuất lại bằng ZIP" ⇒ tải về file `.zip` mở được.

## Remaining Limits

0. **E39: cỡ mẫu là 3 chapter của MỘT tác giả.** Xem (d). Đủ để chốt trần, chưa đủ để gọi là
   phổ quát.
1. **E39 chỉ chạy cho `en`.** Trang bạt tiếng Nhật/Trung vẫn đẻ ra rác. Cần một tín hiệu tương
   đương (trợ từ Nhật: は/が/を/に) và phải ĐO trước khi chốt ngưỡng, không vay ngưỡng tiếng Anh.
2. **Khối < 20 từ vẫn lọt.** Dòng ghi công ngắn (11 từ, 0% từ nối) không bị xét. Chọn có chủ đích.
3. **Trang 12 (`crop_too_large`, 1200×2965) vẫn kẹt `ocr_done`** ⇒ vẫn bị loại khỏi file xuất.
   E38 chỉ lo trang *không có chữ*, không lo trang *quá lớn*. Việc riêng, chưa mở.
4. **Chưa ai mở file xuất bằng app đọc truyện thật lần nào** — M8 ghi giới hạn này từ đầu và nó
   vẫn đúng. Lượt E40 sắp tới là cơ hội đóng nó.
5. **E14 phát hiện hình bong bóng: 0/21 trên tranh thật** (`shape_derived: 0`,
   `fallback_rectangle: 19`). Nợ MỚI do E35 phơi ra, chưa sửa — báo cáo E14 ghi "5/5" nhưng đó là
   ảnh tổng hợp.
6. **Job trùng** (4× typeset, ~959 token lãng phí/trang) — đã chẩn đoán nguyên nhân
   (auto-chain + batch orchestrator cùng đẩy bước sau), có công cụ (`Job.heartbeat_at` của E22),
   chưa sửa.
