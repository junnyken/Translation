# MINI-SPEC ID: E44 — **VÔ HIỆU, KHÔNG THỰC HIỆN**

**Status:** ❌ **HUỶ ngay trong ngày tạo (24-09)** — trùng với E25 (10-09) và tiền đề đã bị bác.
**Đừng mở lại hướng này.** Lý do đầy đủ bên dưới.

---

## Vì sao huỷ

E44 định đo việc **hạ `ctd_input_size`** để rút ngắn bước nhận diện (60% thời gian một trang).

`REPORT_E25.md` §2.3 đã đóng hướng này từ 10-09, và tôi đã **kiểm lại trực tiếp trên model**
ngày 24-09:

```
models/comic-text-detector.onnx
   vào : images [1, 3, 1024, 1024]      ← TĨNH hoàn toàn
```

Shape đầu vào bị ghim cứng cả ba chiều. Đưa 896 vào là lỗi thẳng:

```
INVALID_ARGUMENT : Got invalid dimensions for input: images
  index: 2 Got: 896 Expected: 1024
```

⇒ `ctd_input_size` **trông như** một cần gạt nhưng chỉ có **đúng một giá trị hợp lệ**. Không có
gì để đo. Muốn đổi phải **xuất lại model** — việc đó là một mini-spec khác hẳn, không phải "đo
thử một tham số".

Ghi chú thêm: `[1, ...]` ở chiều đầu nghĩa là batch cũng bị ghim = 1 ⇒ **không gộp nhiều trang
vào một lượt inference** được, cùng lý do.

---

## Sai lầm đã mắc, ghi lại để không lặp

Chuỗi này sai **hai lần liên tiếp trong cùng một ngày**:

1. Tôi đề xuất *"hạ độ phân giải ảnh đưa vào nhận diện"* — sai, vì `ctd.py:_letterbox()` thu mọi
   trang về khung vuông cố định trước khi vào model, nên cỡ trang không ảnh hưởng thời gian.
2. Tôi sửa thành *"vặn `ctd_input_size`"* và viết hẳn mini-spec — **cũng sai**, vì shape model là
   tĩnh, và E25 đã đo và đóng hướng này 14 ngày trước.

**Gốc của cả hai lần: viết spec trước khi tra báo cáo cũ.** `REPORT_E25.md` có sẵn trong repo, tiêu
đề đúng chủ đề (*"Truy tìm chỗ tối ưu thời gian inference"*), và bảng tóm tắt §1 liệt kê thẳng
hướng này là BỊ CHẶN.

**Luật rút ra:** trước khi mở mini-spec tối ưu hiệu năng, **đọc `REPORT_E25.md` §1 trước** — nó
là bảng "những hướng đã đóng".

---

## Những hướng E25 đã đóng bằng số đo (đừng mở lại)

| Hướng | Kết quả đo |
|---|---|
| Đặt `intra_op_num_threads` thấp | **Ngược chiều** — chậm hơn 2,5–3,5× (50s → 119–165s) |
| Hạ `input_size` | **Bị chặn** — shape model tĩnh 1024 |
| Model bị nạp lại mỗi trang | **Không xảy ra** — mỗi model nạp đúng 1 lần |
| Lượng tử hoá INT8 | **Không chạy được** — ORT CPU thiếu kernel `ConvInteger` |
| Thêm CPU | **Đã ở trần gói**, *và* 6× số core chỉ cho **1,19×** |

## Hướng còn THỰC SỰ mở

Xem `REPORT_E25.md` §2.8: **song song hoá ở tầng task**. Phép đo của E25 **thất bại** (script đếm
lượt theo giả định nên in ra con số không có thật, + bàn thử nhiễu 4×), nên hướng này **chưa đo**
— không phải đã bác. Số duy nhất dùng được: **RSS ~1117MB/tiến trình** ⇒ 2 worker ≈ 2,2GB, vừa
trần 4096MB.
