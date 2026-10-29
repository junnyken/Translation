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

---

# 8. BỔ SUNG 24-09 — đã đo tranh chấp CPU (việc §6 đề xuất)

Chạy dưới `taskset -c 0-2` (3 nhân, xấp xỉ 2,6 của production). Hai nhánh xen kẽ NT/SS, **5 cặp**
tổng cộng: 2 cặp ở lượt đo đầu + 3 cặp ở lượt đo lại có thêm **1 vòng làm ấm không tính giờ**.

## 8.1. Thời gian tường — KHÔNG có lợi ích

| Nhánh | Các lượt (giây) | Trung bình |
|---|---|---|
| **Nối tiếp** (hiện trạng `--pool=solo`) | 157,8 · 182,0 · 191,5 · 205,9 · 206,5 | **188,7s** |
| **Song song** (2 worker chuyên hoá) | 168,3 · 173,7 · 176,5 · 202,9 · 211,0 | **186,5s** |

Chênh **+2,3s (+1,2%)** — dưới xa biên độ nhiễu (42,7s). Theo luật đặt trước khi chạy: **chưa đo
được**, KHÔNG phải "không có tác dụng".

**Nhưng câu hỏi cần trả lời thì đã trả lời được.** Nếu song song cho 2× thì nhánh nối tiếp phải ra
~380s so với ~190s. Không có gì gần như vậy. ⇒ **Một cú thắng LỚN bị loại trừ dứt khoát**; chỉ
hiệu ứng nhỏ (~vài %) là không phân giải nổi trên bàn thử này. Và hiệu ứng vài % không phải thứ
đáng đánh đổi bằng việc xây job-có-chủ.

## 8.2. Cơ chế — vì sao bằng nhau, đo được rõ

Từng bước **chậm đi rất nhiều** khi chạy song song, tách bạch hoàn toàn giữa hai nhánh:

| Bước | Chạy một mình | Chạy song song | Chậm đi |
|---|---|---|---|
| Nhận diện | 120,2 · 141,8 · 137,1s | 210,6 · 202,6 · 168,0s | **+40…55%** |
| Xoá chữ | 70,8 · 63,6 · 69,0s | 154,2 · 134,7 · 120,1s | **+90…115%** |

Đây là **bảo toàn công việc CPU**. Nối tiếp: tường = detect + inpaint. Song song: tường =
max(detect, inpaint), nhưng chính detect đã phình lên xấp xỉ (detect + inpaint) vì phải chia CPU.
Hai vế hội tụ về cùng một số.

**Ống dẫn chỉ có lãi khi một chặng đang RẢNH CPU.** Cả hai bước ở đây là tính toán thuần, không
chờ đĩa hay mạng, nên không có chỗ rảnh nào để tận dụng.

Điều này cũng giải thích bảng §2.7 của E25 mà lúc đó chưa ai giải thích: **6× số nhân chỉ cho
1,19×**. Workload đã bão hoà CPU thì thêm nhân không giúp, mà chia nhân cũng không giúp — cùng
một hiện tượng nhìn từ hai phía.

## 8.3. Một giả thuyết của tôi bị bác

Tôi cho rằng nhiễu 24,2s ở lượt đo đầu là do **quên vòng làm ấm**, và thêm vòng ấm sẽ siết nhiễu
lại. **Sai.** Lượt đo lại có vòng ấm mà nhiễu còn **tăng** (42,7s), vì tải máy dùng chung cao suốt
lượt đo (loadavg 17–25). Nhiễu đến từ **máy dùng chung**, không phải từ warm-up. Đúng thứ E25 đã
gặp.

## 8.4. Kết luận cho hướng B

**KHÔNG khuyến nghị xây.** Hướng A cho thấy RAM vừa (chỉ với một cách chia, biên trong dải nhiễu);
§8 cho thấy **không có thông lượng để mà lấy**. Xây job-có-chủ (id worker + nhịp tim) là việc đụng
thẳng vào phần E22 dựng để chống mất việc — làm việc đó để đổi lấy ~1% là lỗ rõ ràng.

**E45 khép lại ở đây với kết quả âm**, cùng dạng với E25. Giá trị của nó là **đóng thêm một
hướng** để lần sau không ai đi lại, và sửa hai hiểu sai của E25 (§3, §8.2).

## 8.5. Hướng thay thế — đổi BẢN CHẤT công việc, không chia lại nó

Mọi hướng đã đóng đều cố chia lại cùng một khối tính toán. Hướng chưa ai thử là **bỏ khối tính toán
đó ra khỏi máy**: gọi AI nhận diện khung bong bóng thay vì chạy ONNX cục bộ.

Nếu nhận diện thành lượt gọi mạng thì **CPU rảnh xuất hiện** — và đúng cái vừa làm hỏng §8 lại trở
thành có lãi. Hạ tầng đã có sẵn: E32 đã gửi ảnh trang cho Gemini (`anh_kem.py`, thu nhỏ 1024px
chặn chi phí, xoay key, hỏng thì trả `None`).

**Chưa đo, chưa được tin.** Bốn ẩn số: chất lượng khung của model tổng quát so với model chuyên trị
truyện tranh; chi phí token (nhận diện hiện tốn 0 đồng); phụ thuộc mạng (hiện chạy offline được);
trần gọi Gemini tính theo *project*.
