# Báo cáo Mini-Spec E45 — Song song hoá tầng task (hướng A: chỉ ĐO)

**Project:** Translation · **Ngày:** 2026-09-24 · **Nền:** `669007d`
**Phạm vi:** Hướng **A** của `MINI_SPEC_E45` §3 — đo tính khả thi RAM ở máy dev, **không đổi mã
sản phẩm, không đụng production**.
**Kết luận:** **VỪA, nhưng chỉ với ĐÚNG MỘT cách chia việc, và biên an toàn NHỎ HƠN nhiễu đo.**

---

## 1. Câu trả lời ngắn

Hai tiến trình chuyên hoá (chỉ-nhận-diện + chỉ-xoá-chữ) chạy đồng thời đạt đỉnh **3109 MB**, so
với ngân sách thật **3950 MB**.

**Nhưng con số đó chưa phải câu trả lời cho sản phẩm**, vì nó mới phủ **2 trong 5 bước**. Khi tính
đủ cả 5 bước thì **cách chia việc quyết định vừa hay không** — xem §4. Chỉ **một** trong ba cách
chia là vừa.

---

## 2. Số đo — đỉnh RSS từng bước, tiến trình riêng

5 trang Pepper&Carrot CC BY-SA 1200×1660 (1,99 Mpx — đúng cỡ đọc production), 27 vùng chữ thật.

| Tiến trình | Đỉnh RSS (VmHWM) | Đối chiếu tài liệu cũ |
|---|---|---|
| Chỉ nhận diện | **1103 MB** | khớp `config.py` *"detector ~1,1 GB"* và E25 *"~1117MB"* |
| Chỉ đọc chữ (PaddleOCR `en`) | **730 MB** | khớp `config.py` *"PaddleOCR ~0,7 GB"* |
| Chỉ xoá chữ (LaMa) | **2239 MB** | gần `config.py` 2295 MB ở trần 1,6 Mpx |
| Phí nền mỗi worker (Celery + SQLAlchemy + models) | **77 MB** | chưa từng đo trước đây |

Chạy đồng thời nhận diện + xoá chữ:

| | |
|---|---|
| Đỉnh của TỔNG (lấy mẫu đồng thời, 1397 mẫu) | **3109 MB** |
| Chặn trên (cộng hai đỉnh riêng) | 3342 MB |
| Ngân sách thật | **3950 MB** = 4096 − ~104 (API, vì `ROLE=all`) |

**Tính toàn vẹn phép đo:** `exitcode` cả hai tiến trình = 0; **dự kiến 5 = đếm được 5** ở cả hai
nhánh; 27/27 vùng đọc ra chữ. Không có lượt nào bị suy ra từ giả định.

---

## 3. Sửa một hiểu sai của E25

E25 §2.8 kết luận *"RSS ~1117MB mỗi tiến trình ⇒ 2 worker ≈ 2,2GB, nhét được vào 4096MB"*.

**Con số 1117MB của E25 không sai — nhưng nó là RSS của tiến trình chỉ giữ detector.** Đo lại hôm
nay ra 1103 MB, khớp. Sai lầm nằm ở chỗ **coi đó là đỉnh của một worker**: worker phổ thông còn
phải chạy xoá chữ, và **riêng bước đó đã đỉnh 2239 MB**. Nhân đôi nhầm con số nhỏ nhất trong ba
con số.

---

## 4. Phần quan trọng nhất — cách chia việc quyết định vừa hay không

Pipeline có 5 bước. Dịch gọi API từ xa (không nạp model) và căn chữ vẽ bằng Pillow (không model),
nên chỉ **ba** bước giữ model. Cộng 77 MB phí nền mỗi worker:

| Cách chia | Worker A | Worker B | Tổng | 3950 MB? |
|---|---|---|---|---|
| **1** | nhận diện **1149** | đọc chữ + xoá chữ + dịch + căn chữ **2285** | **3434 MB** | ✅ **VỪA** (dư 516) |
| 2 | nhận diện + đọc chữ **1961** | xoá chữ + dịch + căn chữ **2285** | **4246 MB** | ❌ KHÔNG |
| 3 | hai worker phổ thông (như `--concurrency=2`) | | **~4682 MB** | ❌ KHÔNG |

⚠️ **Cách 1 vừa được là NHỜ van xả RSS**, không phải tự nhiên. Worker B chạy đọc chữ (730 MB) rồi
mới nạp LaMa; nếu PaddleOCR **vẫn thường trú** thì B đỉnh 730+2239 = 2969 MB và tổng thành
**4118 MB — không vừa**. `worker_rss_soft_limit_mb = 1500` sinh ra đúng để nhả model không cần cho
bước đang chạy, nên cơ chế **có sẵn** — nhưng hành vi của nó trong worker **chuyên hoá** thì
**chưa đo**.

### Biên an toàn nhỏ hơn nhiễu đo

Cách 1 dư 516 MB trên 3950, tức **13%**. `config.py:405-420` đã ghi nhận **nhiễu allocator ±15%**.

⇒ **Biên nằm TRONG dải nhiễu.** Không được đọc "dư 516 MB" như một vùng an toàn. Đọc đúng là:
*không có bằng chứng nó tràn, cũng không có bằng chứng nó đủ biên.*

---

## 5. Điều báo cáo này KHÔNG trả lời

1. **Thông lượng — chưa đo, và có dấu hiệu xấu.** Máy đo có **12 nhân không hạn ngạch**;
   production có **2,6 CPU**. Ngay trên máy 12 nhân, bước nhận diện đã **chậm đi 33%** khi chạy
   cùng xoá chữ (211,4s → 281,0s cho 5 trang). Trên 2,6 CPU mức tranh chấp sẽ nặng hơn hẳn.
   **Không được suy ra "2 worker = 2× nhanh".** Thời gian tường 281,5s của lượt này **không**
   chuyển sang production được.
2. **Van xả RSS trong worker chuyên hoá** — §4 phụ thuộc vào nó mà chưa ai đo.
3. **Worker Celery thật dưới tải** — phép đo này gọi thẳng service, không qua Celery/Redis/DB.
   Phí nền 77 MB đã đo, nhưng hành vi bộ nhớ khi chạy dài qua broker thì chưa.
4. **Job-có-chủ** — vẫn là điều kiện bắt buộc trước khi bật worker thứ hai
   (`MINI_SPEC_E45` §1.3). Chưa làm gì ở phần này.

---

## 6. Đề xuất

**Hướng A đã trả lời xong câu hỏi chặn: RAM không phải bức tường tuyệt đối — có đúng một cách chia
việc vừa được.** Nhưng kết quả **không đủ mạnh để đi thẳng sang hướng B**, vì hai lý do độc lập:
biên nằm trong dải nhiễu (§4), và tranh chấp CPU chưa đo trong khi dấu hiệu ban đầu là xấu (§5.1).

Thứ tự hợp lý nếu chủ dự án muốn đi tiếp — **đo trước, xây sau**:

1. **Đo tranh chấp CPU ở 2,6 nhân** (bó cgroup hoặc `taskset`). Rẻ, không đổi mã. Nếu thông lượng
   không tăng thì mọi thứ phía sau là vô ích và ta dừng tại đây — không tốn công xây job-có-chủ.
2. Chỉ khi (1) dương mới tính tới hướng B (job-có-chủ + chuyên hoá hàng đợi), và khi đó phải theo
   **cách chia 1** chứ không phải cách nào khác.

**Không khuyến nghị** bật `--concurrency=2` trong mọi trường hợp: cách chia 3 cần ~4682 MB, vượt
ngân sách rõ ràng.

---

## 7. Tệp phụ trợ

Script đo nằm ở scratchpad, **không đưa vào repo** — đúng tiền lệ E25: chỉ promote khi nó đã được
dùng lại lần thứ hai và tự kiểm được số lượt. Cả ba script đều đếm lượt thật và kiểm `exitcode`.

Hai lỗi tự bắt được trong lúc viết script, ghi lại vì cùng họ với lỗi đã giết lượt đo của E25:
- `is_alive()` gọi `waitpid(WNOHANG)` nên **thu xác tiến trình con ngay**, khiến `/proc/<pid>` biến
  mất và `VmHWM` đọc sau vòng lặp **luôn trả `None`**. Phải bám đỉnh ngay trong vòng lấy mẫu.
- Lần chạy thứ hai sẽ **nuốt cả ảnh `_clean`** của lần trước vào mẫu đo, làm số trang phình lên
  âm thầm.
