# KẾ HOẠCH A2 — cắt khung chữ về trong lòng bong bóng

*Lập 2026-09-05 · nối tiếp A1 (`REPORT_A1_NOI_KHUNG.md`) và E14 (`REPORT_E14.md`)*

## 1. Vấn đề, nói bằng số

Người dùng báo: trên một trang thật, **một vùng** có khung chữ không khớp bong bóng, các vùng
khác thì đủ. Đối chiếu log của đúng trang đó:

```
nới khung vùng 124x293 tại (478,38): ô đầu 102x240 · giới hạn 563x730 · kết quả 102x240 (hệ số 1.0)
```

Đó là vùng **duy nhất trên trang có hệ số nới = 1,0** — không nới được một pixel nào. Bảy vùng
còn lại nới được 1,36 đến 6,13 lần.

Dựng lại bằng mặt nạ tổng hợp:

| Khung chữ ban đầu | Kết quả của A1 |
|---|---|
| nằm gọn trong bong bóng | nở đẹp, vẫn trong bong bóng ✓ |
| đã chồm qua viền | **vẫn tràn ra ngoài** |
| bao trùm cả bong bóng | **nở ra kín cả ảnh** (30×30 → 0,0 200×200) |

## 2. Vì sao A1 không tự sửa được

`no_khung_ra_cho_trong` **chỉ nới ra, không bao giờ thu vào**. Và nó cố ý đánh dấu **cả ô ban
đầu** là "chỗ trống" — quyết định đúng ở thời điểm đó, vì bước xoá chữ luôn để sót nét (`còn chữ
ở 8/8 vùng`) và không bỏ qua thì phép nới từ chối chạy ở toàn bộ vùng.

Nhưng cái giá là: **viền bong bóng nằm trong ô đó cũng bị xoá khỏi mặt nạ**, nên không còn gì
chặn phép nới.

Đã thử một bản sửa trong phiên trước — chỉ xoá vệt mực *nằm trọn* trong ô, giữ vệt kéo dài ra
ngoài. **Đo A/B trên 6 ca: không đổi kết quả ở ca nào.** Lý do: khung đã chồm ra ngoài thì phần
chồm ấy nằm ở vùng trắng thật, phép nới đi tiếp là đúng luật — sai nằm ở **điểm xuất phát**, không
nằm ở phép nới. Bản sửa đó đã bị bỏ.

⇒ **Không thể vá trong `grow.py`.** Cần một bước mới: biết lòng bong bóng ở đâu, rồi cắt khung về
trong đó.

## 3. Vì sao E14 không cho biết lòng bong bóng

E14 **đã có** bộ dò hình bong bóng (`extractor.py`): lọc điểm sáng theo HSV → morphology →
`findContours` → lấy contour **nhỏ nhất bao quanh tâm** vùng chữ.

Nó chưa **một lần nào** thành công: `shape_derived` = **0/8**, **0/12**, **0/2** trên ba trang
khác nhau — tổng 22 vùng, 0 lần.

Đo được nguyên nhân:

```
tỉ lệ điểm 'sáng' theo ngưỡng E14 đang dùng: 96,7% toàn trang
trần cho phép (max_roi_coverage_ratio):      75%
```

Manga đen trắng là **bong bóng trắng trên trang trắng**. Lọc theo độ sáng thì bong bóng và trang
là **cùng một khối**, nên contour bao quanh tâm chính là cả trang, và bị loại vì `FILLS_ROI`.

Lọc theo độ sáng là sai công cụ cho bài toán này, không phải sai tham số. Chỉnh ngưỡng không cứu
được: không có ngưỡng sáng nào tách được trắng khỏi trắng.

## 4. Hướng đề xuất — tô loang từ tâm trên mặt nạ MỰC

Bong bóng không khác trang ở **độ sáng**, nhưng có **viền mực bao quanh**. Vậy:

> Lòng bong bóng = vùng **không mực nối liền** chứa tâm vùng chữ.

Tô loang (`floodFill`) từ tâm vùng chữ trên mặt nạ "không mực". Nó tự dừng ở viền bong bóng, kể
cả khi hai bên viền đều trắng — đúng nguyên lý mà A1 đã dùng thành công để nới khung.

### Đã đo, không phải suy đoán

Trên ảnh clean thật của một trang có hai bong bóng vẽ sẵn kích thước biết trước:

| Bong bóng thật | Tô loang trả về |
|---|---|
| 380×240 tại (90,90) | **373×233 tại (94,94)** |
| 240×180 tại (520,120) | **233×173 tại (524,124)** |

Sai lệch đúng bằng bề dày nét viền. Trong khi cách hiện tại trả về **0 kết quả**.

### Bộ phân biệt "có bong bóng" vs "chữ nằm trên nền vẽ"

Trên 3 ảnh manga trong `test_fixtures/`:

| Tâm rơi vào | Diện tích vùng tô loang |
|---|---|
| trong bong bóng | 4,4% – 5,8% trang |
| nền vẽ trống | **75% – 82% trang** (rò ra cả trang) |

Hai nhóm cách nhau hơn một bậc độ lớn ⇒ một trần diện tích tách được, và ca rò ra thì rơi về
khung dự phòng như hiện nay.

### Ca quyết định — đúng lỗi người dùng báo

Mặt nạ dựng riêng: bong bóng sát mép panel, bbox chữ chồm qua viền phải.

| | Khung | Điểm mực nằm trong khung |
|---|---|---|
| A1 hiện tại | (260,110) 140×80 | **400** — khung đè lên viền |
| Cắt về lòng bong bóng | (260,110) **118**×80 | **0** |

## 5. Việc phải làm

| # | Việc | Ghi chú |
|---|---|---|
| A2-1 | Hàm `long_bong_bong(mat_na_muc, tam, roi, cfg)` — tô loang, trả `(rect, so_diem, ly_do)` | thuần hàm, test không cần ảnh thật |
| A2-2 | **Dời tâm khi tâm rơi trúng mực** — tâm bbox chữ có thể trúng nét chữ còn sót | thử vài điểm quanh tâm, hết thì trả `None` kèm lý do |
| A2-3 | Trần diện tích + trần so với bbox chữ ⇒ quyết định *có bong bóng* hay *rò* | tái dùng ý của `FILLS_ROI`, thêm mã lý do riêng |
| A2-4 | Cắt khung sau A1 về giao với lòng bong bóng | chỉ cắt, **không** nới thêm — A1 vẫn giữ nguyên vai trò |
| A2-5 | Ghi `source=shape_derived` khi tô loang thành công | lần đầu tiên trường này khác 0; phải kèm hình học thật |
| A2-6 | Log một dòng mỗi vùng: tâm, diện tích, kết luận, khung trước/sau khi cắt | A1 đã có tiền lệ và nó đã cứu chính lượt gỡ lỗi này |
| A2-7 | Cờ bật/tắt trong config, **mặc định TẮT** cho tới khi đo xong trên trang thật | đổi hình học là đổi thứ người dùng nhìn thấy |

## 6. Rủi ro đã biết, và cách kiểm

| Rủi ro | Vì sao đáng lo | Kiểm thế nào |
|---|---|---|
| **Lưới chấm (screentone)** làm mặt nạ mực vỡ vụn | 3 ảnh đã đo đều là ảnh dựng, **chưa có ảnh manga in thật** | Phải chạy trên trang thật của người dùng trước khi bật |
| Nét chữ còn sót chia đôi lòng bong bóng | inpaint để sót ở 8/8 vùng | đóng hình thái học trước khi tô loang; đo số vùng bị chia |
| Bong bóng chạm nhau / có đuôi nhọn | tô loang tràn sang bong bóng bên cạnh | trần diện tích + trần so với bbox |
| Cắt quá tay làm chữ nhỏ đi | vùng vốn đã tràn khung sẽ tràn nặng hơn | đo số vùng tràn trước/sau; tràn tăng thì **không bật** |
| Bong bóng bị mép panel cắt | đúng ca đang lỗi | đã dựng mặt nạ riêng ở §4, giữ làm test hồi quy |

## 7. Cách biết A2 thành công

Đo **trên đúng trang manga của người dùng**, trước và sau:

1. `shape_derived` đi từ **0/n** lên một con số khác 0 — nếu vẫn 0 thì A2 vô dụng, phải nói thẳng.
2. **Số điểm mực nằm trong khung chữ** giảm — đây là thước đo trực tiếp của "khung có lọt trong
   bong bóng không", và là con số đã dùng để chứng minh ở §4.
3. **Số vùng tràn khung không tăng.** Cắt khung nhỏ lại có thể làm chữ tràn thêm; nếu tràn tăng
   thì đánh đổi sai và A2 phải ở lại trạng thái tắt.
4. Nhìn tận mắt ảnh xem thử trên trình duyệt — E18 đã cho thấy đo số không thay được nhìn ảnh.

## 8. Không làm trong A2

- **Không** sửa `grow.py`. A1 làm đúng việc của nó; A2 chỉ thêm một bước cắt sau đó.
- **Không** đụng bộ dò chữ. Bbox lệch là chuyện của bộ nhận diện, A2 chỉ sửa hậu quả.
- **Không** bật mặc định cho tới khi có số đo trên trang thật.
