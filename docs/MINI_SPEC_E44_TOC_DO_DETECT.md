# MINI-SPEC ID: E44

**Name:** Đo đánh đổi tốc độ ↔ độ sót của `CTD_INPUT_SIZE`
**Author + Date:** Phiên Claude Opus 5 / 2026-09-24
**Status:** Audit xong — chờ duyệt trước khi chạy đo
**Nguồn:** Câu hỏi của chủ dự án — *"vì sao Ichigo chạy dưới 10 giây/trang mà ta mất 100 giây?"*

---

# 1. Context

## Số đo của ta (phiên 24-09, production `2,6 CPU · 4GB RAM`, không GPU)

| Bước | Thời gian | Tỉ trọng |
|---|---|---|
| **Nhận diện khung chữ** | 42–70 s | **~60%** |
| Xoá chữ gốc (LaMa) | ~19 s | ~26% |
| Đọc chữ | ~8 s | ~11% |
| Dịch + căn chữ | ~4 s | ~5% |

Một trang trọn chuỗi: **100 giây**.

**Nhận diện chiếm 60% thời gian.** Đó là chỗ duy nhất đáng động vào trước.

## Audit đã lật ngược giả định ban đầu

Ý tưởng khởi điểm là *"hạ độ phân giải ảnh đưa vào nhận diện"*. **Audit cho thấy ý đó sai.**

`ctd.py:_letterbox()` thu mọi ảnh vào **khung vuông cố định `ctd_input_size × ctd_input_size`**
rồi mới đưa vào ONNX:

```python
size = self.input_size          # mặc định 1024
scale = min(size / w, size / h)
canvas = Image.new("RGB", (size, size), ...)
```

⇒ Trang 1600×2213 và trang 1200×1660 **đều thành 1024×1024** khi vào model. **Độ phân giải trang
KHÔNG ảnh hưởng tới thời gian nhận diện.** Đưa ảnh nhỏ hơn vào không tiết kiệm được gì.

**Núm vặn thật là `ctd_input_size`, và nó ĐÃ TỒN TẠI:**

| | |
|---|---|
| Khai báo | `config.py:105` — `ctd_input_size: int = 1024` |
| Biến môi trường | `CTD_INPUT_SIZE` |
| Trên production | **CHƯA đặt** ⇒ đang chạy mặc định 1024 |

Không cần viết code mới. Đây là **một mini-spec ĐO**, không phải mini-spec xây.

## Vì sao đáng đo

Chi phí ONNX co giãn xấp xỉ theo **bình phương** cạnh:

| `ctd_input_size` | Số điểm ảnh so với 1024 | Kỳ vọng thời gian |
|---|---|---|
| 1024 (nay) | 1,00× | 42–70 s |
| 896 | 0,77× | ? |
| 768 | 0,56× | ? |
| 640 | 0,39× | ? |

> ⚠️ Cột cuối là **kỳ vọng suy từ lý thuyết, CHƯA đo**. Thời gian thật không nhất thiết co giãn
> đúng bình phương: còn tiền xử lý, hậu xử lý, và chi phí cố định của phiên ONNX. **Chính vì
> vậy mới phải đo.**

## Và đây là phép đo MIỄN PHÍ

Nhận diện **không tiêu token nào**. Khác hẳn Mini-Spec P3 (đo chất lượng dịch) vốn tốn tiền thật.
Đo được bao nhiêu lượt tuỳ ý, chỉ tốn thời gian CPU.

---

# 2. Goal

Trả lời bằng số: **hạ `ctd_input_size` tiết kiệm được bao nhiêu giây, và đánh đổi bằng bao nhiêu
bong bóng bị bỏ sót.**

**Không** phải mục tiêu: đổi giá trị mặc định. Mini-spec này **chỉ đo và báo cáo**; đổi hay không
là quyết định của chủ dự án sau khi thấy số.

---

# 3. Constraints

1. **Không đổi mã sản phẩm.** Núm vặn đã có; chỉ viết script đo và đọc kết quả.
2. **Không đổi `CTD_INPUT_SIZE` trên production** trong lúc đo. Đo ở máy dev.
3. Fixture phải **hợp pháp và công bố được** — Pepper&Carrot CC BY-SA.
4. **Không bịa số.** Mọi con số truy ngược về một lượt chạy thật.
5. **Không kết luận "tốt hơn/tệ hơn" từ số vùng đơn thuần** — xem §5.

---

# 4. Cách đo

## 4.1. Fixture

**5 trang Pepper&Carrot CC BY-SA** đã lọc sạch (bỏ 1 tệp cụt). Đây là toàn bộ fixture lành hiện
có.

> ⚠️ **n=5 là mẫu rất nhỏ.** Mọi kết luận phải ghi kèm cỡ mẫu. Dự án đã có tiền lệ `Run C là pass
> RỖNG` — 3/3 assertion đạt trên n=9 mà không chứng minh được gì.

## 4.2. Biến đo

Với mỗi `ctd_input_size ∈ {1024, 896, 768, 640}`, chạy **cùng 5 trang**, ghi:

- thời gian nhận diện **từng trang** (không lấy trung bình vội — xem phân bố trước)
- số vùng tìm được
- số vùng `low_confidence`
- số vùng `overlap_suspect`
- RSS đỉnh

**Lặp ít nhất 2 lượt mỗi giá trị** để biết dao động của chính phép đo. Nếu hai lượt cùng cấu hình
đã lệch nhau nhiều thì chênh lệch giữa các cấu hình **không có ý nghĩa**.

## 4.3. Chạy tuần tự, không song song

Chạy song song sẽ làm các lượt tranh CPU của nhau và **mọi con số thời gian thành rác**.

---

# 5. Cạm bẫy diễn giải — phần quan trọng nhất

**Ít vùng hơn KHÔNG tự động là tệ hơn.**

Cỡ nhỏ hơn có thể bỏ sót bong bóng nhỏ (**tệ**), nhưng cũng có thể bớt báo nhầm nhiễu thành vùng
chữ (**tốt**). Chỉ đếm số vùng thì hai chuyện này **trông giống hệt nhau**.

Dự án đã dính đúng bẫy này: E23 ghi nhận cờ "cần rà soát" bật oan **29% số trang** vì cả 11 vùng
chỉ đọc ra MỘT ký tự nhiễu — tức là **nhiều vùng hơn mà tệ hơn**.

**Cách phân biệt, bắt buộc làm:**

1. Lấy kết quả ở 1024 làm **mốc**.
2. Với mỗi vùng **mất đi** khi hạ cỡ: vùng đó ở mốc có đọc ra chữ thật không (`OCRResult.raw_text`
   có nội dung, không phải `needs_manual`)?
   - Mất vùng **có chữ thật** ⇒ **sót thật**, tính là mất mát
   - Mất vùng **không đọc ra chữ** ⇒ nhiều khả năng là nhiễu, **không** tính là mất mát
3. Báo cáo **hai con số riêng**, tuyệt đối không gộp thành một "điểm chất lượng".

---

# 6. Kết quả cần có

Một bảng, mỗi dòng một cấu hình:

```text
ctd_input_size | thời gian/trang (từng trang) | vùng | vùng có chữ thật | sót thật so với mốc
```

Kèm: ngày, commit, cấu hình máy, cỡ mẫu, số lượt lặp.

---

# 7. Điều mini-spec này KHÔNG trả lời

1. **Không nói được vì sao Ichigo nhanh.** Benchmark ghi nhãn **UNKNOWN** cho việc họ dùng model
   gì để nhận diện, và **UNKNOWN** cho việc họ có xoá chữ gốc hay chỉ phủ hộp màu. Nếu họ bỏ hẳn
   bước xoá chữ thì họ tiết kiệm 19 giây mà ta **không thể** bắt chước bằng cách vặn núm này.
2. **Không đụng tới GPU.** Nhận diện chạy CPU là lựa chọn hạ tầng; đổi nó là quyết định về máy và
   chi phí, không thuộc phạm vi ở đây. **Nếu có GPU thì hướng đó gần như chắc chắn ăn đứt việc
   vặn `input_size`** — 60% thời gian nằm ở inference.
3. **Không đo song song hoá.** Worker chạy `--pool=solo` một trang một lúc; chạy song song sẽ rút
   ngắn cả chapter nhưng vướng RAM (mỗi worker ~1,2GB, container 4GB, chủ dự án đã chốt không
   nâng RAM).

---

# 8. Stop Rules

1. Hai lượt lặp cùng cấu hình lệch nhau lớn ⇒ **DỪNG**, báo cáo rằng phép đo chưa đủ ổn định để
   kết luận, đừng ép ra kết luận.
2. Không tự đổi `CTD_INPUT_SIZE` ở bất kỳ môi trường nào sau khi đo — chỉ báo cáo số.
3. Phát hiện vấn đề mới ngoài phạm vi ⇒ DỪNG, báo cáo 4 phần.
4. Nếu số đo cho thấy hạ cỡ **không** tiết kiệm đáng kể ⇒ **báo đúng như vậy**. Kết quả âm cũng
   là kết quả — dự án đã có tiền lệ E25 (`KHÔNG SHIP GÌ`, 4 giả thuyết đều bị số đo bác bỏ).
