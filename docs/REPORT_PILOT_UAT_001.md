# Báo cáo Pilot/UAT hosted — 6 trang (PILOT_UAT_001)

**Ngày chạy:** 2026-08-31 → 2026-09-03 · **Môi trường:** VibeHost hosted pilot / staging-production-like

> ⚠️ **Đây KHÔNG phải môi trường production-ready, và KHÔNG thay thế UAT chapter 10–20 trang.**
> Pilot 6 trang là phép thử kiểm soát rủi ro để có bằng chứng hỏng hóc thật trước.

---

## 1. Summary

| | |
|---|---|
| Web | `https://translation.cmc-1.vibenode.matbao.ai` |
| API | `https://translation-api.cmc-1.vibenode.matbao.ai` |
| Commit lúc bắt đầu pilot | `ac5460c` (= `origin/main`, worktree sạch) |
| Commit lúc kết thúc | `6e3ffa8` |
| Dữ liệu | Pepper&Carrot ep11 *"The Witches of Chaosah"* trang P01–P06 |
| Tác giả / giấy phép | **David Revoy** · **CC BY-SA 4.0** · https://www.peppercarrot.com |
| Số trang | **đúng 6 trang liên tục** |

**Kết quả tổng: DÙNG ĐƯỢC cho pilot hosted giới hạn này** — nhưng chỉ sau khi sửa một sự cố P1
(worker bị OOM killer giết) mà chính pilot phát hiện ra.

Workflow đầu-cuối chạy trọn: 6/6 trang qua detect → OCR → xoá chữ → dịch → canh chữ → rà soát →
xuất → tải về → mở được. **31/31 vùng** có OCR, bản dịch và kết quả canh chữ. **12/12 hiện vật**
mở thật được qua đường sản phẩm.

---

## 2. Audit Before Run (§5)

### 5.1 Git / triển khai
```
branch main · worktree sạch
HEAD          ac5460c80b6fb00e4709db0b90c306a76e729968
origin/main   ac5460c80b6fb00e4709db0b90c306a76e729968   (khớp)
```
Ứng dụng **không lộ build SHA**, nên chứng minh gián tiếp bằng hành vi tính năng của bản
post-`ac5460c` (§5.4). **Không bịa endpoint SHA, không khai một SHA là "đã deploy" mà thiếu bằng chứng.**

### 5.2 Sức khoẻ hosted
- Web: HTTP/2 **200**, `content-type: text/html`
- API `/healthz`: **200** · `content-type: application/json` · JSON đúng shape (`status`,`worker`) ·
  **không phải SPA HTML** của tên miền web
- **Bằng chứng worker độc lập với `worker.trang_thai=starting`**: log Celery cho thấy chuỗi tác
  vụ chạy trọn — `inpaint 15,8s` → `translate 1,3s (engine=google_fast)` → `typeset 0,4s`

### 5.3 CORS (Chromium thật, không chỉ curl)

| Origin | Đọc được API? |
|---|---|
| `https://translation.cmc-1.vibenode.matbao.ai` | **có** (ACAO đúng origin này) |
| `https://evil.example` | **không** — `TypeError: Failed to fetch` |
| `http://localhost:5174` | **không** |
| `null` (trang `data:`) | **không** |

Khẳng định: wildcard `ACAO: *` **0 lần** · `Access-Control-Allow-Credentials` **0 lần** · không
phản chiếu origin lạ.

### 5.4 Vòng đời hiện vật (dùng hiện vật CÓ SẴN, không tạo pilot thứ hai)

Hai hiện vật, gồm **cái lớn nhất 6,76 MB**:
- `Accept-Ranges: bytes` · ETag **ổn định** qua 2 lượt
- `Range: bytes=0-6999` → **206** + `Content-Range` đúng
- **Ghép đoạn + phần còn lại = SHA-256 của bản tải nguyên** · ảnh ghép mở được
- **Không có false-ready**: trang mất hiện vật báo đúng `ocr_done` + 404 khớp trạng thái

⚠️ Bằng chứng **bền qua redeploy** lấy từ báo cáo P3e (đã đo trước đó), **không tái kiểm trong
pilot này** — theo đúng §5.4 (không redeploy trong pre-flight).

### 5.5 Tiện ích E1 — `unverified`
Không có màn hình/`DISPLAY` trong workspace ⇒ **không bấm được icon toolbar**. Ghi `unverified`,
**không** suy ra "đạt" từ bằng chứng headless/API.

### 5.6 Dữ liệu pilot
6 tệp JPEG · **1200×1660** (min=med=max) · **1,99 MPx**/trang · tổng **3,70 MB** ·
`.gitignore:14 test_fixtures/external/` ⇒ đã xác nhận **không** bị Git theo dõi/stage.

---

## 3. Flow Executed

Toàn bộ qua **E11 UI thật** trong Chromium (không curl/Postman/DB/Celery trực tiếp).
E1 **không** được dùng. Không scrape web, không import URL ảnh.

Ba chapter đã chạy — ghi đúng số, không giấu:

| Chapter | Mục đích | Kết quả |
|---|---|---|
| **001** `9b4dcaa2` | Round 1 lần đầu | 6 trang tới `typeset_done` rồi **API sập** — worker OOM |
| **002** `c0fd0b69` | Round 1 chạy lại (sau bản sửa arena) | **5/6**, trang 1 kẹt `ocr_done` vì OOM lúc inpaint → bấm "Chạy cả chapter" → **6/6** |
| **003** `126e131b` | Kiểm chứng bản sửa ngưỡng | **6/6 từ đầu, worker KHÔNG chết** |

Thứ tự upload: `E11P01 … E11P06`, UI xác nhận đủ 6 tệp trước khi bấm.
Ngôn ngữ gốc `en`, **mục đích sử dụng `study` do người dùng tự khai** (hệ thống để trống mặc định).

---

## 4. Metrics Table

### 4.1 Trạng thái cuối theo trang (chapter 003)

| Trang | Trạng thái | Vùng | OCR | Dịch | Canh chữ | Ảnh clean | Ảnh xem thử |
|---|---|---|---|---|---|---|---|
| 1 | `typeset_done` | 7 | 7 | 7 | 7 | 200 · 2.579.067 B | 200 · 2.611.416 B |
| 2 | `typeset_done` | 9 | 9 | 9 | 9 | 200 · 2.527.683 B | 200 · 2.593.801 B |
| 3 | `typeset_done` | 3 | 3 | 3 | 3 | 200 · 2.858.722 B | 200 · 2.893.097 B |
| 4 | `typeset_done` | 4 | 4 | 4 | 4 | 200 · 2.878.829 B | 200 · 2.899.367 B |
| 5 | `typeset_done` | 4 | 4 | 4 | 4 | 200 · 2.676.163 B | 200 · 2.694.676 B |
| 6 | `typeset_done` | 4 | 4 | 4 | 4 | 200 · 2.744.237 B | 200 · 2.765.721 B |
| **Tổng** | **6/6** | **31** | **31/31** | **31/31** | **31/31** | **6/6 mở được** | **6/6 mở được** |

### 4.2 Cảnh báo (số do hệ thống tự báo ở cổng xuất)

| Nhóm | Số | Mẫu số |
|---|---|---|
| E12 chưa đọc được chữ gốc | 3 | /31 vùng |
| E12 cần rà soát | 6 | /31 vùng |
| E14 dùng khung chữ nhật dự phòng | 21 | /31 vùng |
| E14 cần xem lại hình bong bóng | 0 | /31 vùng |
| E15 cần kiểm tra hướng chữ | 1 | /31 vùng |
| E15 chưa xác định hướng | 1 | /31 vùng |
| M6 tràn khung | **0** | /31 vùng |
| E13 thuật ngữ đã duyệt | **0** | — |

**E15 chữ dọc: `no-data`.** Nguồn Pepper&Carrot là truyện Âu, 7/7 vùng trang 1 là **chữ ngang**.
**Không** dùng việc vắng dữ liệu để kết luận E15 hỗ trợ chữ dọc/nghiêng.

### 4.3 Thời gian & UX (§7.3)

| Chỉ số | Đo được |
|---|---|
| Mở form → upload được chấp nhận | **14,8s** / **20,4s** / **18,6s** (3 chapter) |
| Cả chapter: submit → 6/6 trạng thái cuối | **≈ 5,5 phút** (chapter 003) |
| Sửa 1 vùng → ảnh xem thử mới | **1,16 s** |
| Job xuất | **6,1 s** |
| Tải về + mở được | **1/1 lần thử** |
| Parity xuất ↔ xem thử | **3/3 trang** trùng **từng pixel và từng byte** |
| Tỉ lệ sửa tay | **2/31 vùng** (1 sửa chữ, 1 đổi font) |
| Tìm lại chapter sau khi mở lại trình duyệt | **có** — mục "gần đây" hiện đúng |
| Phụ thuộc ngoài UI | **không** ở Round 2 (không mở log/mã/DB trong lượt vận hành) |

### 4.4 Tài nguyên / worker (§6.3)

```
TRƯỚC bản sửa   so_lan_chet = 3 · exit 137 (SIGKILL/OOM) · API 3,4ms -> 10–42s -> mất phản hồi
SAU  bản sửa    so_lan_chet = 0 · RSS worker 1631,5 -> 1631,7 -> 1631,7 -> 1631,7 MB (phẳng)
```

### 4.5 Một phát hiện phụ: pipeline **tất định**

Chapter 002 và 003 là hai lượt chạy **độc lập** trên cùng 6 ảnh (project và page_id đều khác) —
hiện vật ra **trùng khít từng byte**. Chạy lại an toàn và tái lập được.

---

## 5. UX Findings

### 5.1 ⚠️ Hai phát hiện tôi đã báo SAI — đính chính

Trong lượt Round 2 đầu tiên tôi báo 3 phát hiện UX. **Hai trong đó sai, cả hai do tôi đo sai.**
Ghi lại vì một báo cáo UAT giấu lỗi của chính người kiểm thì vô dụng.

| Tôi đã báo | Sự thật | Vì sao tôi sai |
|---|---|---|
| *"Không tìm lại được chapter — UX BLOCKER"* | **Sai.** Tính năng "chapter gần đây" đã có sẵn (`luuChapter` → localStorage, 12 mục) và chạy đúng | Tôi test bằng context Playwright **mới tinh** ⇒ localStorage rỗng. Đó là *"đổi máy / xoá dữ liệu trang"*, không phải *"mở lại phiên"* như §7.2.3 yêu cầu |
| *"Chỉ báo tiến trình hụt 20 giây"* | **Sai.** `t=0,25s 'Đang lưu và căn lại chữ…'` → `t=1,00s 'Xong'`, nút khoá suốt | Con số "21,3s" là **thời gian tôi tự ngồi chờ** (`wait_for_timeout(20000)`), không phải thời lượng job |

**Bài học:** phép đo phải tái hiện đúng kịch bản người dùng, và không được đo chính độ trễ mình
tự tạo ra.

### 5.2 Phát hiện thật (đã sửa trong pilot này)

**Tên riêng bị dịch nghĩa đen, mà cổng xuất im lặng.** Nhân vật *Pepper* ra thành **"Hạt tiêu"**
(tên gia vị). Cổng xuất không hé một lời: khối "Nhất quán thuật ngữ" chỉ hiện khi **có việc rà
soát**, mà chapter không có thuật ngữ nào thì **không sinh việc nào** — hệ thống im lặng đúng lúc
rủi ro cao nhất. Đã sửa (`6e3ffa8`) và kiểm chứng trên host.

### 5.3 Responsive (§9.2)

| Kích thước | Tràn ngang | Điều khiển | Lỗi console | Trạng thái nói thật |
|---|---|---|---|---|
| 360×800 · 768×1024 · 1280×900 · 1600×1100 | **0px** ở cả 4 | dùng được | **0** ở cả 4 | 6/6 hiện đúng |

Lớp phủ M7: **9 khung, 0 khung lệch ra ngoài ảnh** ở cả 360px lẫn 1280px (ảnh co giãn
290×400 → 694×959, khung bám đúng).

---

## 6. Defects

### P1-1 — Worker bị OOM killer giết · **ĐÃ SỬA, ĐÃ KIỂM CHỨNG**

**Tái hiện:** upload 6 trang 1200×1660 qua UI, để pipeline tự chạy.
**Triệu chứng:** `exit 137`, API tụt 3,4ms → 10–42s → mất phản hồi hoàn toàn; log nền tảng
`wings_error`. 8 lượt thăm dò chỉ 3 lượt thành công.
**Tần suất:** 3/3 lượt trước khi sửa.

**Gốc rễ:** LaMa là model *dynamic shape* chạy theo từng cụm bong bóng, mỗi cụm một kích thước.
Session dùng `SessionOptions()` mặc định ⇒ **CPU memory arena bật** ⇒ cấp khối mới cho **mỗi
shape** và không trả lại. Cộng thêm ba model cùng thường trú:

```
detector ~1,1 GB + PaddleOCR ~0,7 GB = 1914,6 MB, rồi nạp LaMa ~1,2 GB  ⇒ vỡ trần 4 GB
```

**Đã sửa** (`64c006a`, `831cb32`): tắt arena cho LaMa (giữ bật cho CTD vì CTD chỉ có **một**
shape) · trộn ảnh theo dải 256 dòng (đỉnh 71,7 → 14,6 MB, kết quả **y hệt từng byte**) · thêm đo
RSS + van xả nhả model · `/healthz` trả `rss_mb`.

**Bằng chứng đã khỏi:** chapter 003 chạy trọn 6 trang, `so_lan_chet = 0`, RSS **phẳng tuyệt đối**
`1631,5 → 1631,7 → 1631,7 → 1631,7 MB`.

⚠️ **Một lỗi của chính bản sửa:** ngưỡng van xả ban đầu đặt **2200 MB**, cao hơn 1914,6 MB nên van
**không mở** — nó chết đúng ở chỗ nó sinh ra để cứu. Đã hạ về **1500 MB** theo số đo, kèm 2 test
neo con số. *Ngưỡng phải tính theo model sắp nạp, không theo trần container.*

### P1-2 — Job đang chạy bị mất khi worker chết, **không có cơ chế chạy lại** · **CHƯA SỬA**

Trang 1 chapter 002 kẹt vĩnh viễn ở `ocr_done`. Đường **tự nối tiếp sau upload** không thử lại;
đường **"Chạy cả chapter"** thì có (*"lỗi tạm thời thử lại tối đa 3 lần"*).
**Không có endpoint liệt kê job** ⇒ người vận hành không tra được *lý do* trang dừng — giao diện
chỉ hiện "5/6 trang" và nhãn trạng thái, không nói job đã chết.

### P2-1 — Cổng xuất im lặng khi chưa chốt thuật ngữ · **ĐÃ SỬA** (`6e3ffa8`)

Xem §5.2. Kiểm chứng live: 5 nhóm cảnh báo đều có nhãn riêng, nhóm E13 nêu hậu quả kèm ví dụ thật.

### P3-1 — "Chapter gần đây" chỉ nằm trong localStorage một trình duyệt

Xoá dữ liệu trang / đổi máy / đổi trình duyệt ⇒ mất danh sách, phải có UUID. **Không** khắc phục
bằng endpoint liệt kê toàn hệ thống: **chưa có auth**, làm vậy là lộ công việc của mọi người dùng
cho nhau — sửa một lỗi UX bằng cách đẻ ra một lỗ hổng.

---

## 7. What Passed (chỉ điều có bằng chứng)

- Pipeline 6 trang đầu-cuối, **31/31 vùng** đủ OCR + dịch + canh chữ
- **12/12 hiện vật mở thật** qua đường sản phẩm — không dùng trạng thái DB làm bằng chứng
- **Parity xuất ↔ xem thử: 3/3 trang trùng từng pixel và từng byte**, *sau khi* đã sửa tay ⇒
  **file xuất phản ánh đúng bản mới nhất** (đây là rủi ro P1 mà §8 nêu, và nó KHÔNG xảy ra)
- CBZ hợp lệ, **CRC toàn vẹn**, 6 ảnh đúng thứ tự `001…006.png`
- **M10 cưỡng chế thật**: nút xuất TẮT cho tới khi tick cam kết
- CORS exact-origin, không wildcard, không credentials
- `Range`/`ETag`/`304` hoạt động trên kho CSDL, resume ghép lại khớp SHA-256
- Responsive 4 kích thước, 0 lỗi console, lớp phủ M7 bám đúng
- Pipeline **tất định**: hai lượt độc lập ra hiện vật trùng từng byte

## 8. What Did Not Pass / Unknown

- **E15 dựng chữ dọc tiếng Việt: vẫn BLOCKED về cấu trúc.** Pilot **không** thay đổi kết luận này
- **Chưa có auth / RBAC / đa người dùng / TLS riêng.** **CORS không phải xác thực**
- **6 trang không chứng minh** được khả năng chịu tải, sao lưu hay khôi phục thảm hoạ
- `no-data`: E15 chữ dọc & chữ nghiêng (nguồn là truyện Âu, toàn chữ ngang) · E13 việc rà soát
  nhất quán (chưa cấu hình thuật ngữ) · M6 tràn khung (0 vùng — **không kết luận** được nhóm cảnh
  báo này có tồn tại hay không)
- **E1 toolbar: `unverified`** — không có màn hình
- **Chưa tái kiểm** tính bền qua redeploy trong pilot này (lấy từ báo cáo P3e)
- **Nhiễu đã biết:** trong lượt Round 1 đầu có **một phiên khác dùng chung host** (project
  "test lần 2", giao diện poll 7 endpoint mỗi 5 giây) trên container `ROLE=all` 1,6 CPU

## 9. One Recommended Next Mini-Spec

### **Khôi phục job khi worker chết — và nói cho người dùng biết**

**Vấn đề:** worker chết giữa chừng ⇒ job đang chạy biến mất, trang kẹt vĩnh viễn ở trạng thái
giữa, **không tự chạy lại và không có tín hiệu lý do**. Không có endpoint liệt kê job nên người
vận hành không tra được.

**Bằng chứng độ nghiêm trọng/tần suất:** đo trực tiếp trong pilot — trang 1 chapter 002 kẹt
`ocr_done`; worker chết 3 lần trong ngày. §8 xếp *"job stuck/running forever"* và *"worker
OOM/restart no recovery"* là **P1**. Đây là **P1 duy nhất còn mở**.

**Vì sao xếp trên các lựa chọn khác:** P1-1 đã sửa và kiểm chứng; P2-1 đã sửa; P3-1 là tiện nghi.
Còn cái này biến **một sự cố tạm thời thành mất mát vĩnh viễn** — và nó vẫn xảy ra kể cả khi
không còn OOM (nền tảng restart, hết hạn mức, mất kết nối). Sửa OOM chỉ giảm **tần suất**, không
giảm **hậu quả**.

**Ranh giới phạm vi (nghiêm ngặt):**
- CÓ: phát hiện job `running` mồ côi khi worker khởi động lại; đánh dấu `failed` kèm lý do đọc
  được; cho đường chạy lại; endpoint liệt kê job theo trang/chapter để giao diện hiện lý do
- KHÔNG: đổi kiến trúc hàng đợi, không thêm Celery beat, không đụng `ROLE=all`, không mở E2/E3/E16

**Câu hỏi audit đầu tiên:** *khi worker khởi động lại, có phân biệt được job `running` mồ côi với
job đang chạy hợp lệ của một worker khác không* — vì đánh dấu nhầm sẽ giết job đang chạy tốt.

## 10. Remaining Limits

- **Tính bền hiện vật**: đã chứng minh ở P3e (sống qua 3 lần redeploy), **không tái kiểm** ở pilot này
- **Topology `ROLE=all`**: API và worker chung một container 2,6 CPU / 4 GB. RAM **đã chạm trần
  gói** (`QUOTA_EXCEEDED` khi thử nâng lên 5376 MB)
- **Telemetry worker**: `worker.trang_thai` kẹt `starting` là hạn chế đã biết; `rss_mb` trong
  `/healthz` là RSS của **tiến trình API**, không phải worker — RSS worker chỉ có trong log
- **E15**: chữ dọc BLOCKED, chữ nghiêng/cách điệu chỉ ở mức rà soát
- **Tiện ích E1**: chỉ là launcher/điều hướng; **không** đọc DOM, **không** import URL, **không**
  overlay trang web. Bấm icon toolbar `unverified`
- **Nhật ký nền tảng là phù du** — không sống sót qua một lần deploy; việc cần dấu vết kiểm toán
  phải ghi vào CSDL

## 11. Git / Deploy State

```
Mã đổi do pilot   : CÓ — 2 bản sửa sinh ra TỪ bằng chứng pilot:
                      P3h  chặn OOM worker            (64c006a, 831cb32)
                      P3i  cảnh báo thiếu thuật ngữ   (6e3ffa8)
Deploy            : CÓ — translation-api và translation-web
Commit tài liệu   : báo cáo này
```

⚠️ Pilot này **không** là giấy phép để push/deploy thêm bất cứ thứ gì. **Không tạo release tag.**
**Không redeploy sau pilot nếu chưa có xác nhận mới của chủ dự án.**

**Về dữ liệu:** báo cáo này **không** chứa ảnh gốc, không chứa signed URL, không chứa secret,
không chứa đường dẫn hệ tệp của host. Ảnh pilot nằm trong `test_fixtures/external/` **đã gitignore**.
Trích dẫn lời thoại giới hạn ở một câu ngắn của tác phẩm **CC BY-SA 4.0** có ghi công đầy đủ.
