# Báo cáo Mini-Spec E25 — Truy tìm chỗ tối ưu thời gian inference

**Project:** Translation · **Phase:** E — Hosted Reliability & Performance
**Ngày:** 2026-09-10 · **Nền:** `4de39c3` (sau E21b LIVE)
**Trạng thái:** **KHÔNG SHIP GÌ** — bốn giả thuyết đều bị bác bỏ bằng số đo, và cần gạt còn lại
bị chặn ở tầng nền tảng. Đây là báo cáo của một cuộc truy tìm chủ yếu ra kết quả âm.

## 1. Summary

Câu hỏi khởi đầu của người dùng: *"chapter 24 trang thì dịch hết không, và 40-60 phút là quá lâu"*.

Đo thật trên 6 trang truyện: **134s/trang ⇒ 24 trang ≈ 54 phút**, khớp ước lượng ban đầu.

Bốn giả thuyết tối ưu được nêu và **cả bốn đều bị số đo bác bỏ**:

| # | Giả thuyết | Kết quả |
|---|---|---|
| H1 | ONNX bị quá tải luồng; đặt `intra_op_num_threads` thấp sẽ nhanh hơn | **SAI, ngược chiều** — đặt tường minh chậm hơn 2,5-3,5× |
| — | Giảm `input_size` của bộ nhận diện | **BỊ CHẶN** — model có shape đầu vào cố định 1024 |
| H2 | Model bị nhả rồi nạp lại mỗi trang | **SAI** — mỗi model nạp đúng 1 lần cho 6 trang |
| — | Lượng tử hoá động INT8 | **KHÔNG CHẠY ĐƯỢC** — ORT CPU thiếu kernel `ConvInteger` |
| — | Thêm CPU (tăng quota / đổi gói) | **BỊ BÁC BỎ 2 LỚP** — đã ở trần gói (`maxCpu == currentCpu == 2.6`), *và* 6× core chỉ cho 1,19× |

Cần gạt cuối cùng — thêm CPU — tưởng là cái chắc chắn nhất vì 84% thời gian là compute. Nó thất
bại hai lần: không có quota để tăng, **và** đường cong theo số core gần như phẳng (§2.7), nên dù
mua được hạ tầng lớn hơn cũng không nhanh lên đáng kể.

**Không đổi một dòng code nào, không deploy gì.** Giá trị của E25 nằm ở chỗ nó **đóng năm hướng**
để lần sau không ai đi lại, và ở một phép sửa số liệu quan trọng (§2.1).

**Đề xuất chốt: tạm chấp nhận ~54 phút, dừng đầu tư vào tốc độ.** Lý do không phải "đã hết cách"
mà là: mọi cách *rẻ* đã bị bác bỏ bằng số đo, cách còn lại có triển vọng nhất (song song hoá tầng
task, §2.8) **chưa đo được** và muốn đo phải đánh đổi lại chính phần độ tin cậy E22 vừa dựng, còn
cách cắt được 40% ngay (`chi_chu`) thì **đổi sản phẩm** chứ không phải đổi hiệu năng. Pipeline chạy
nền và E22 đã làm cho việc bị ngắt giữa chừng không mất dữ liệu — nên ~54 phút là **chậm nhưng
an toàn**, và đó là đánh đổi chấp nhận được cho tới khi có nhu cầu thật buộc phải nhanh hơn.

## 2. Số đo

### 2.1 Chi phí từng bước trên trang truyện THẬT — và một đính chính

6 trang Pepper&Carrot ep11 (1200×1660, 7-9 vùng chữ/trang), chạy tuần tự qua pipeline thật:

| Bước | Tổng 6 trang | TB/trang | Tỉ lệ | Các lượt (giây) |
|---|---|---|---|---|
| Nhận diện khung | 370,0s | 61,7s | **46%** | 55,9 · 51,7 · 52,0 · 53,8 · 77,1 · 79,5 |
| Xoá chữ (LaMa) | 304,1s | 50,7s | **38%** | 75,5 · 49,8 · 44,5 · 44,6 · 43,6 · 46,1 |
| Đọc chữ | 88,4s | 14,7s | 11% | 41,3 · 22,1 · 8,9 · 6,7 · 4,9 · 4,5 |
| Dịch | 25,4s | 4,2s | 3% | 7,1 · 7,1 · 2,0 · 4,5 · 3,0 · 1,7 |
| Căn chữ | 16,1s | 2,7s | 2% | 3,5 · 5,3 · 2,9 · 1,5 · 1,6 · 1,3 |
| **Tổng** | **804s (13,4 phút)** | **134s** | | |

**ĐÍNH CHÍNH:** trước đó tôi báo bước xoá chữ chỉ chiếm ~12% (10,7s), dựa trên **một trang tổng
hợp chỉ có 2 vùng chữ nhỏ** đo ngày 09-09. Trên trang thật 7-9 vùng, LaMa chạy theo từng cụm chữ
nên tốn **~51s/trang**. Vậy **nhận diện + xoá chữ = 84%**, không phải nhận diện một mình. Con số
"~12%" cũ là sai vì mẫu không đại diện.

Ghi chú: bước đọc chữ tự ấm dần đúng thiết kế (41,3s → 4,5s) — đó là chi phí nạp model được khấu
hao, không phải bất thường.

### 2.2 H1 — luồng ONNX: sai, và sai ngược chiều

Cùng một trang, ghim 3 core bằng `taskset` để mô phỏng quota 2,6 CPU:

| Cấu hình | Lượt 1 (gồm nạp model) | Lượt 2 (ấm) |
|---|---|---|
| `intra_op=0` — **hiện trạng**, ORT tự quyết | 50,14s | **46,72s** |
| `intra_op=4` | 148,79s | 119,56s |
| `intra_op=2` | 302,59s | 164,90s |

Trong ba mức đo: **càng ít luồng càng chậm**. Hiện trạng (không đặt) là cấu hình nhanh nhất, và
deploy `intra_op=2` lên production sẽ biến 54 phút thành khoảng 2,5-3 tiếng.

Kiểm chứng rằng đây không phải nhiễu do thay đổi kèm: nhánh `if self.intra_op_threads > 0` trong
`ctd.py:92-103` chỉ gán **duy nhất** `opts.intra_op_num_threads`, không đổi `execution_mode` hay
mức tối ưu graph. Nên hiệu ứng 2,5-3,5× là do số luồng, không do cái gì khác.

**Cơ chế thì tôi không giải thích được.** Đặt 4 luồng trên 3 core mà chậm hơn 2,5× so với để ORT
tự sinh ~12 luồng là phản trực giác cho một mạng tích chập. Tôi có số đo sạch và hiệu ứng lớn,
nhưng không có cơ chế — nên tôi **không** ngoại suy sang `intra_op=1`. Kết luận vận hành vẫn an
toàn vì hiện trạng là mức nhanh nhất đã đo, tức "không làm gì" là đúng.

**Tiền đề của H1 cũng sai:** giả thuyết dựa trên "ORT đếm 192 core trong khi quota 2,6". Con số 192
là `nproc` của **shell máy chủ**, đọc sai chỗ. Bên trong container `os.cpu_count()` báo **12**.
Không có chuyện sinh 192 luồng.

### 2.3 `input_size` — bị model khoá cứng

`CTDDetector.__init__` có tham số `input_size: int = 1024`, trông như một cần gạt. Nhưng graph ONNX
có shape đầu vào **tĩnh**: đưa 896 vào là lỗi thẳng

```
INVALID_ARGUMENT : Got invalid dimensions for input: images
  index: 2 Got: 896 Expected: 1024
```

Muốn đổi phải **xuất lại model**, ngoài phạm vi. Tham số đó thực chất chỉ có một giá trị hợp lệ.

### 2.4 H2 — không có chuyện nạp lại model mỗi trang

Đếm trên log worker của đúng lượt 6 trang ở §2.1:

| Sự kiện | Số lần / 6 trang |
|---|---|
| Nạp CTD (detector) | **1** |
| Nạp PaddleOCR | **1** |
| Nạp LaMa | **1** |
| Nhả model vì vượt ngưỡng | **1** |

Lần nhả duy nhất: `RSS 1948.0 MB vượt ngưỡng 1500 MB — đã nhả model detector, còn 1031.6 MB`, và
model bị nhả đó **không cần nạp lại** (số lần nạp vẫn là 1). RSS lên ~1219MB rồi **đứng phẳng**
suốt các trang sau. Cơ chế `bo_nho.py` đang hoạt động đúng chứ không gây thrash.

⇒ Nâng `worker_rss_soft_limit_mb` sẽ **không** mua được tốc độ nào, nên không đáng đánh đổi rủi ro
OOM. Đây là lý do H2 bị bỏ.

### 2.5 Lượng tử hoá động — không chạy được, không phải chậm

`quantize_dynamic(..., QuantType.QInt8)` chạy xong và tạo được model INT8, nhưng nạp thì lỗi:

```
NOT_IMPLEMENTED : Could not find an implementation for ConvInteger(10) node
                  with name 'Conv_0_quant'
```

Nó **có** lượng tử hoá các lớp tích chập (Conv → ConvInteger) nhưng CPU provider của
`onnxruntime 1.20.1` không có kernel cho `ConvInteger`. Đường còn lại là lượng tử hoá **tĩnh
(QDQ)** sinh `QLinearConv` — cần bộ dữ liệu hiệu chuẩn và phải kiểm lại chất lượng nhận diện theo
kỷ luật E20b. Đó là một mini-spec riêng, chưa mở.

Ghi chú môi trường: image production **thiếu package `onnx`** nên không tạo được model lượng tử hoá
tại chỗ — nhưng điều đó **không chặn**: `onnx` chỉ cần để *tạo*, còn để *chạy* thì `onnxruntime` là
đủ. Nếu sau này QDQ thắng, production chỉ cần **một file model khác**, không thêm dependency.

### 2.6 Trần tài nguyên — cần gạt chắc chắn nhất đã hết đường

`get_resources` cho `translation-api`:

```
currentCpu   : 2.6      maxCpu    : 2.6      ← ĐÃ Ở TRẦN
currentRamMB : 4096     maxRamMB  : 5376     ← còn nới +1280MB
```

**CPU không tăng được qua cổng tài nguyên.** Muốn thêm thì phải đổi gói/hạ tầng — quyết định mua
sắm ở tầng nền tảng, ngoài phạm vi mini-spec này.

RAM nới được nhưng **không mua tốc độ cho một trang** (§2.4: bộ nhớ không phải chỗ tắc của một
trang). Nó mua khoảng an toàn chống OOM — liên quan sự cố P1 của `PILOT_UAT_001` và cú SIGKILL
09-09 — tức độ tin cậy.

**QUYẾT ĐỊNH 2026-09-10 (người dùng): GIỮ 4096MB, không nới.** E25 đóng tại đây. Lý do giữ được:
§2.4 cho thấy cơ chế `bo_nho.py` đang làm đúng việc — RSS lên ~1219MB rồi đứng phẳng qua 6 trang,
chỉ nhả model 1 lần và không phải nạp lại. Tức 4096MB **không** phải chỗ đang bị ép. Nếu sau này
đi hướng song song hoá (§2.8) thì mở lại mục này, vì lúc đó RAM thành điều kiện cần.

> **Sửa lại phát biểu này:** ban đầu tôi viết RAM "chỉ mua độ tin cậy, không mua tốc độ". Nói vậy
> là quá mạnh. Nếu đi hướng song song hoá tầng task (§2.8) thì RSS ~1117MB **mỗi** worker biến RAM
> thành **điều kiện cần** để có tốc độ, chứ không phải thứ vô can. Đúng hơn: RAM không mua tốc độ
> *một trang*, nhưng có thể mua *thông lượng* — điều kiện là hướng §2.8 chứng minh được đã.

### 2.7 Đường cong theo số core — thêm CPU KHÔNG mua được tốc độ

Vì CPU đã ở trần gói, câu hỏi còn lại không phải "có nên tăng quota" (không tăng được) mà **"đổi
sang gói/hạ tầng lớn hơn có đáng không"**. Đo bằng cách ghim `taskset` vào 2/3/4/6/8/12 core, mỗi
mức 1 lượt làm ấm + 2 lượt tính giờ, cùng một trang:

| Core | Lượt ấm (min/max) |
|---|---|
| 2 | 53,04s / 70,70s |
| 3 | 70,52s / 71,08s |
| 4 | 44,99s / 57,45s |
| 6 | 51,28s / 51,58s |
| 8 | **76,58s / 85,03s** ← chậm nhất trong cả bảng |
| 12 | 44,38s / 50,69s |

**Không có xu hướng.** Tăng 6× số core (2→12) đổi được 53,04s → 44,38s, tức **1,19×**, và điểm
chậm nhất lại là 8 core. Độ tản **giữa** các mức (44-85s) lớn hơn bất kỳ xu hướng đơn điệu nào,
nên bảng này không đo được hiệu ứng nhỏ. Nhưng nó **đủ để trả lời câu cần trả lời**: nếu nhiều core
cho nhanh gấp 3 thì mức 2 core phải ra ~150s. Không có gì gần như vậy.

Confound đã loại trước khi tin bảng này: nếu container local có cgroup quota thì nới `taskset` sẽ
vô tác dụng và bảng phẳng chỉ là tạo tác của quota. Đã kiểm: `cpu.max = "max 100000"`,
`CpuQuota=0`, `CpusetCpus` rỗng — không có quota, `taskset` là ràng buộc duy nhất.

**Quy ra tiền cho E27** (đọc theo hướng rộng tay nhất với phương án mua thêm CPU):

| | Hiện tại | Giả sử được 1,19× |
|---|---|---|
| Nhận diện /trang | 61,7s | 51,8s |
| Xoá chữ /trang (giả định scale y hệt, **chưa đo**) | 50,7s | 42,6s |
| **24 trang** | **~53,6 phút** | **~46,4 phút** |

⇒ 6× số core mua được **~13% thời gian**, và con số đó nằm *trong* dải nhiễu. Không phải thứ người
dùng cần khi nói "quá lâu". **Bằng chứng không ủng hộ việc đổi hạ tầng vì tốc độ.**

### 2.8 Song song hoá ở tầng task — PHÉP ĐO THẤT BẠI, vẫn CHƯA ĐO

Đường cong phẳng ở §2.7 là dấu hiệu kinh điển của workload nên song song hoá ở tầng **task** chứ
không phải tầng **op**: nếu thêm core không làm một trang nhanh hơn, thì chạy nhiều trang cùng lúc
mới là cần gạt. Worker hiện là `--pool=solo` — đúng một task một lúc.

Đo thử trên cùng ngân sách 3 core cho mọi nhánh (`scratchpad/do_song_song.py`, **không** đưa vào
repo, lý do bên dưới):

| Song song | Tường | Thông lượng | Lượt lẻ | RSS |
|---|---|---|---|---|
| 1 | 175,4s / 2 lượt | 0,0114 lượt/s | 45,9-129,3s | 1117MB |
| 2 | 510,0s / 4 lượt | 0,0078 lượt/s | 102-406s | 2231MB |
| 3 | 257,5s / **4** lượt (không phải 6) | 0,0155 lượt/s | 108-149s | 2236MB |

**Kết quả này KHÔNG dùng được, vì hai lý do độc lập.**

*Lý do 1 — lỗi trong script đo của chính tôi.* Ở nhánh n=3, chỉ 2 trong 3 tiến trình con báo về
(`[0]` và `[2]`; `RSS_tổng` = 2×1118 chứ không phải 3×1118) — một tiến trình đã chết. Nhưng script
chia thời gian tường cho `so_tien_trinh * SO_LUOT` = 6 **theo giả định**, trong khi chỉ 4 lượt thật
sự chạy. Nó in ra "42,9s/trang", trông y hệt một cú thắng gấp 2, và **con số đó không có thật**
(số thật: 257,5/4 = 64,4s). `p.join()` không kiểm mã thoát, `ket_qua` chỉ được lấp một phần.
Đây đúng là lỗi loại "tính một con số từ giả định thay vì từ cái đã xảy ra" — nên script bị giữ
ở scratchpad, không promote vào repo cho tới khi nó đếm lượt thật và kiểm `p.exitcode`.

*Lý do 2 — bàn thử quá nhiễu, độc lập với lỗi trên.* Cùng một tiến trình, cùng một trang, lượt dao
động **45,9-129,3s** (n=1) và **102-406s** (n=2) — biên độ tới 4×, lớn hơn mọi hiệu ứng cần đo.
Máy chủ dùng chung lúc đó đang chạy việc khác (37/62GB RAM). Bằng chứng nội tại cho thấy đây là
nhiễu: thông lượng n=2 *tệ hơn* n=1 nhưng n=3 lại *tốt hơn* n=1 — không có mô hình vật lý nào cho
hình dạng đó.

**Vì vậy: song song hoá tầng task vẫn CHƯA ĐO.** Không được nói nó cho 2×, cũng không được nói nó
vô ích. Một số duy nhất rút ra được vì nó không phụ thuộc thời gian: **RSS ~1117MB mỗi tiến trình**
(ổn định qua cả ba nhánh) ⇒ 2 worker ≈ 2,2GB, nhét được vào 4096MB; 3 worker ≈ 3,4GB thì sát trần
khi cộng tiến trình API.

Muốn đo cho đúng thì cần: máy chủ rảnh, script đếm lượt **thật** + kiểm `p.exitcode`, và cuối cùng
là một lượt deploy 2 worker thật — vì `--pool=solo` + `worker_prefetch_multiplier=1` là **lựa chọn
độ tin cậy có chủ đích** (một SIGKILL chỉ mất tối đa một job, xem E22), nên đổi nó không phải bật
một cờ mà là đánh đổi lại phần E22 vừa dựng.

## 3. Ghi chú phương pháp — hai chỗ dễ tự lừa

**Bàn thử phải mô phỏng đúng quota, nếu không đo vô nghĩa.** Container local **không giới hạn CPU**
(`NanoCpus=0`) trên máy chủ nhiều core, nên đo trực tiếp sẽ nhanh và **không tái hiện** production.
Dùng `taskset -c 0-2` mới ra 38-50s, khớp 50,6s đo trên production. Đây là điều làm mọi số ở trên
đáng tin.

Hạn chế đã biết của bàn thử: `taskset` **ghim core**, còn production dùng **cgroup quota** (điều
tiết tổng thời gian CPU). Hai cơ chế không giống nhau. Lý do vẫn tin được: mức 3 core tái hiện
đúng thời gian production.

**Dải nhiễu ~30%.** Cùng cấu hình FP32 qua các lượt ra 38,7 / 42,0 / 42,0 / 46,7 / 50,1s. Bất kỳ
"cải thiện" nào dưới mức đó là nhiễu, không phải kết quả.

**Một lỗi đo của tôi, ghi lại để không lặp:** lần đầu đếm số lần nạp model tôi viết
`docker logs ... 2>&1 > /tmp/w.log`. Thứ tự đó đưa stderr về terminal *trước* rồi mới đưa stdout
vào file — mà log Celery đi qua stderr, nên file gần như rỗng và mọi `grep -c` ra **0**. Nếu tin
con số đó thì đã kết luận "không có nạp lại" từ một file trống. Cái cứu là đoạn log thật hiện ra ở
stdout đã mâu thuẫn với số 0. Thứ tự đúng: `> file 2>&1`.

## 4. Changed Files

- `backend/scripts/do_luong_onnx_detect.py` — mới, A/B `intra_op_num_threads` dưới `taskset` (§2.2).
- `backend/scripts/do_luong_scale_cpu.py` — mới, đường cong theo số core (§2.7), kèm ghi chú
  confound cgroup quota phải loại trước khi tin kết quả.

Không đổi code production. Không migration. Không deploy. Hai script trên chỉ để đo, không nằm
trong đường chạy của pipeline.

## 5. Cần gạt còn lại

| Hướng | Payoff | Chi phí | Ai quyết |
|---|---|---|---|
| ~~Đổi gói/hạ tầng nhiều CPU hơn~~ | **BỊ BÁC BỎ** — §2.7: 6× core = 1,19×, trong dải nhiễu | Tiền + di chuyển hạ tầng | Không nên làm |
| QDQ static quantization | Không chắc; có thể ra 0 như E20b | Nhiều ngày công + benchmark chất lượng | Mở mini-spec riêng |
| Chế độ `chi_chu` sẵn có | **Cắt ~53s/trang ≈ 40%** (bỏ xoá chữ + căn chữ) | Không | Nhưng **đổi sản phẩm**: không có ảnh đã xoá chữ, không nung chữ vào ảnh, không xuất được bản có chữ trong bong bóng |
| Nới RAM 4096→5376 | Không mua tốc độ | Trong gói, miễn phí | Mua độ tin cậy chống OOM |
| Song song hoá tầng task (2 worker) | **CHƯA ĐO** (§2.8) — hứa hẹn nhất về lý lẽ, nhưng bàn thử hỏng | Đánh đổi lại `--pool=solo` của E22 + deploy thật để đo | Người dùng, khi có nhu cầu |
| **Chấp nhận ~54 phút** ← *đề xuất* | — | — | Pipeline chạy nền; E22 đảm bảo bị ngắt thì không mất việc và tiếp tục được |

**Một con số cũ đã sửa.** `PLAN_E19_TIEN_ICH_DOC_TRUYEN.md:54` và `REPORT_E19_0_DO_COND_CHAN.md`
ghi chế độ `chi_chu` tiết kiệm "6–17s mỗi trang". Số đó **không sai với mẫu của nó** (trang đó xoá
chữ chỉ tốn 6,3s) — nó sai khi **khái quát hoá**: LaMa chạy theo từng cụm chữ, nên trang thật 7–9
vùng tốn ~51s. Lệch ~8×. Đã thêm ghi chú đính chính có ngày vào `PLAN_E19` (không xoá chữ gốc, để
giữ dấu vết vì sao khi đó tin như vậy).

Hệ quả **quan trọng hơn cả phần còn lại của E25**: `chi_chu` không phải cần gạt nhỏ như tài liệu
mô tả — nó cắt ~40% thời gian, và nó **đã tồn tại, đã chạy được**. Đây là cần gạt duy nhất còn lại
mà có số đo đứng sau — nhưng nó đánh đổi *sản phẩm*, không phải hiệu năng (xem hàng `chi_chu` ở
bảng trên), nên đó là quyết định của người dùng chứ không phải của tôi.

## 6. Remaining Limits

- Đường cong §2.7 chỉ đo **bước nhận diện (46%)**. Bước xoá chữ (38%) **chưa đo scaling**. Cơ sở
  để giả định nó giống: `inpaint/lama.py:170-182` dùng **đúng cùng đường** — `onnxruntime`, cùng
  mặc định `intra_op_threads: int = 0`, cùng provider, cùng loại mạng tích chập. Đó là tương đồng
  cấu trúc, **không phải số đo**; con số 46,4 phút ở §2.7 mang giả định này nên không được trích
  ra ngoài mà bỏ nhãn.
- Đường cong quá nhiễu để loại một hiệu ứng **nhỏ**: nếu thật ra nhiều core cho 1,3-1,5× thì phép
  đo này không thấy. Nhưng nó đủ loại hiệu ứng **lớn** (3×) — và chỉ hiệu ứng lớn mới đáng đổi
  hạ tầng.
- Điểm 8 core (76-85s, chậm nhất bảng) chưa có lời giải thích. Khả năng cao nhất là **tải khác
  trên máy chủ dùng chung** trong lúc đo — tôi không kiểm soát được biến này. Không loại được khả
  năng có gì đó thật ở mức 8 core, nhưng nó không đổi kết luận (nếu 8 core *chậm hơn* thì càng
  không có lý do mua thêm core).
- Mọi số ở đây đo trên **trang tiếng Anh** (PaddleOCR). Chapter tiếng Nhật dùng `manga_ocr` với chi
  phí nạp model lớn hơn hẳn (~19s theo log 09-09), nên cơ cấu thời gian có thể khác.
- Chưa đo trên 24 trang thật; con số 54 phút là ngoại suy tuyến tính từ 6 trang.
