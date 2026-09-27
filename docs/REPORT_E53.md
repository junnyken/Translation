# REPORT E53 — Trang chủ cho khách lạ + tự động tải về

**Ngày:** 2026-09-27 · **Nguồn yêu cầu:** `DAC_TA_TRANG_CHINH_VA_HAN_MUC.md` §3 và §4

---

## 1. Summary

Khách lạ mở trang là thấy **trang chủ**, thả ảnh là chạy, và nhận về **ảnh đã dịch** tải được.
Trang nói trước bốn thứ §4.2 đòi: còn bao nhiêu lượt + bao giờ có lại, **tệp chỉ giữ 30 phút** kèm
đúng mức hậu quả, định dạng/ngôn ngữ hỗ trợ, và **~30 giây mỗi trang**.

Dựng từ bộ primitive sẵn có (`Dropzone`, `Alert`, `Button`, `Icon`) và token sẵn có — **không thêm
màu mới**, nên nó cùng một hệ với phần còn lại của app.

---

## 2. Audit Before Build — cổng chặn ở cửa

`App.jsx` trước E53: `nguoiDung === null` ⇒ **chỉ** hiện màn đăng nhập.

Nghĩa là toàn bộ hạn mức khách lạ (E49), đường dịch cho khách (E51) và đường tự đăng ký (E52)
**không ai với tới được**. Backend mở, giao diện đóng — đúng thứ §4.1 cấm: *"Đăng ký là thứ người
dùng chọn khi muốn nhiều hơn, không phải cổng chặn ở cửa."*

---

## 3. Bốn lỗi THẬT tìm ra khi nối hai đầu

Cả bốn đều thuộc một họ: mỗi đầu đúng theo đặc tả của nó, nối lại thì không chạy. Và cả bốn
**không** bị bộ test backend bắt, vì chúng chỉ tồn tại ở ranh giới trình duyệt ↔ máy chủ.

### 3.1. Cookie khách CHƯA BAO GIỜ tới được API

`allow_credentials=False` ở CORS, và `api.js` không đặt `credentials` (đo: 0 chỗ). Giao diện và API
ở **hai tên miền**, nên mặc định `same-origin` của `fetch` **không gửi cookie sang**.

Hệ quả:

* mỗi request là một "khách mới" ⇒ chốt cookie không bao giờ cộng dồn;
* khách **không đọc lại được trang của chính mình** (`chu_khach` không khớp ⇒ 404).

Nó chạy khi thử bằng `curl` vì ở đó cookie được gửi tay — đúng kiểu lỗi **chỉ lộ trên trình duyệt
thật**.

Vá: `allow_credentials=True` + `credentials: 'include'`. An toàn dựa vào hai thứ khác, không dựa
vào cờ này: `allow_origins` là danh sách **tường minh** (không phải `*`), và cookie khách đặt
`SameSite=Lax` nên không đi theo POST từ trang lạ.

`api.js` có **một** hàm bọc duy nhất che `fetch` toàn cục, và cả 72 lời gọi đi qua đó — nên sửa
một chỗ là xong.

### 3.2. Khách không có đường nào biết `project_id`

E51 đã mở đường xuất gói cho khách, nhưng `TrangDocTruyen` **không trả `project_id`** và mọi
endpoint trả chapter đều đòi đăng nhập. ⇒ §3.3 (nhiều trang gói thành **một** tệp) không dùng
được, dù endpoint đã mở.

Vá: thêm `project_id` vào `TrangDocTruyen`, trả ở cả hai endpoint.

### 3.3. `a.download` bị BỎ QUA khi href trỏ sang nguồn khác

API khác tên miền giao diện, nên gán thẳng URL ảnh vào `<a download>` làm trình duyệt **mở ảnh**
thay vì lưu về — trông y như "không tải được" mà không có lỗi nào để đọc.

Vá: đi qua `blob:` (`taiVeBlobUrl` đã có sẵn), và thu hồi sau một nhịp — thu hồi ngay là có trình
duyệt huỷ luôn lượt tải đang chạy.

### 3.4. `doc()` biến thân lỗi CÓ CẤU TRÚC thành `[object Object]`

Hạn mức (429) và trần đăng ký trả một object đủ thông tin để nói câu tử tế: còn bao nhiêu, bao giờ
có lại, chốt nào chặn. `doc()` nội suy thẳng `body.detail` vào chuỗi nên nó thành `[object
Object]` — mất sạch, và giao diện chỉ còn cách nói "đã có lỗi".

Vá: giữ nguyên hình dạng thông điệp cũ cho `detail` dạng chuỗi (không phá chỗ nào đang đọc nó),
object thì đính vào `.chiTiet` và lấy `thong_diep` làm câu hiển thị.

---

## 4. Ba chỗ dễ nói SAI trên giao diện, và cách xử lý

### 4.1. `con_lai` KHÔNG bằng `tran - da_dung`

Nó là **nhỏ nhất** trong các chốt. Khách ở văn phòng đã chạm trần IP thì còn 0 dù chốt cookie còn
nguyên. Tự tính lại là **mời người ta thả 6 tệp lên rồi nhận 429**. Giao diện hiện đúng con số máy
chủ gửi, và có bài canh riêng.

### 4.2. Chốt `khach_ip` phải nói "địa chỉ mạng dùng chung"

Không nói "bạn đã hết lượt". Người chưa dịch trang nào mà bị chặn **không có cách nào tự đoán ra**
lý do. Giao diện đọc `chot[]`, tìm chốt có `con_lai <= 0`, rồi nói đúng loại.

### 4.3. Luật 30 phút phải nói ĐÚNG MỨC hậu quả

§2.9: sau 30 phút **ảnh gốc, bản dịch và tệp đã gói đều bị xoá** — không chạy lại được, không sửa
lại được, muốn làm lại phải tải lên từ đầu và **tốn thêm lượt**. Không nói mơ hồ kiểu "tệp sẽ được
dọn". Đồng hồ đếm ngược nhận **mốc tuyệt đối**, không nhận số giây: số giây là một ảnh chụp, tab để
mở 20 phút thì nó sai 20 phút mà nhìn vẫn hợp lý.

---

## 5. Điều KHÔNG làm được, và nói thẳng ra

§3.2 đặc tả đòi: *"Bị chặn thì nói ra, đừng im lặng coi như xong."*

**JavaScript không có cách nào biết trình duyệt đã chặn một lượt tải** — không sự kiện, không
ngoại lệ, không cờ. Nên ở đây **không giả vờ dò được**. Bản trung thực của yêu cầu đó là:

* nút tải thủ công **luôn** hiện, không ẩn sau điều kiện nào;
* sau lượt thử tự động, nói rõ: *"Đã thử tải tự động. **Nếu không thấy tệp nào**, trình duyệt đã
  chặn lượt tải không do bạn bấm — bấm nút trên là được."*
* chỉ thử tự động **một lần**: bấm tải nhiều lần là đúng thứ làm trình duyệt chặn hẳn về sau.

Viết mã "phát hiện bị chặn" rồi báo cáo là đã làm §3.2 sẽ là bịa một năng lực không có.

---

## 6. Changed Files

| Tệp | Sửa gì |
|---|---|
| `frontend/src/components/trang-chu/TrangChu.jsx` (mới) | Trang chủ |
| `frontend/src/components/trang-chu/TheHanMuc.jsx` (mới) | Thẻ hạn mức |
| `frontend/src/lib/dem-nguoc.js` (mới) | Đồng hồ đếm ngược theo mốc tuyệt đối |
| `frontend/src/App.jsx` | Chưa đăng nhập ⇒ TRANG CHỦ, không phải màn đăng nhập |
| `frontend/src/api.js` | `credentials: 'include'`; `doc()` giữ thân lỗi có cấu trúc; 5 hàm mới |
| `frontend/src/styles.css` | CSS trang chủ (token sẵn có, không thêm màu) |
| `backend/app/main.py` | `allow_credentials=True` |
| `backend/app/schemas/common.py` | `TrangDocTruyen.project_id` |
| `backend/app/api/v1/routes.py` | Trả `project_id` ở cả hai endpoint khách |

**Không có migration.**

---

## 7. Tests

14 bài frontend mới (`trang-chu.test.jsx`). Frontend **411 bài xanh**, build ra bundle thật (CSS
24,63 → 26,95 kB — kiểm được là style đã vào bundle, không chỉ vào `src`).

| Bài canh | Canh cái gì |
|---|---|
| `hiện ĐÚNG con_lai của máy chủ, KHÔNG tự tính tran - da_dung` | §4.1 trên |
| `bị chốt IP chặn thì nói ĐỊA CHỈ MẠNG` | §4.2 trên |
| `nói ĐÚNG MỨC hậu quả của luật 30 phút` | §4.3 trên |
| `gửi trang kèm che_do=day_du` | Thiếu nó là không có ảnh nào để tải |
| `LUÔN có nút tải thủ công` | §5 trên |
| `CHƯA XONG thì KHÔNG có mốc hết hạn` | §2.3 — đếm từ lúc xong |

Hai bài test của tôi **từng đỏ vì chính chúng sai**, đáng ghi vì cùng một họ lỗi:

1. nhắm `userEvent.upload` vào DIV vùng thả (`id` của Dropzone gắn ở đó) thay vì ô
   `<input type="file">` thật — user-event báo *"The given DIV element does not accept file
   uploads"*;
2. `findByText` cho một câu **cố ý hiện hai chỗ** (cảnh báo trên màn + lý do nút bị khoá) ⇒ truy
   vấn mơ hồ. Sửa sang `findAllByText`, và thêm khẳng định mạnh hơn: nút **thật sự bị khoá**.

Và một lần tôi **dùng sai component**: `ProgressStage` nhận **mảng các bước** của dòng thời gian
chapter, còn `tien_do.buoc` là một **chuỗi** tên bước. Thay bằng `TienDoTrang` đọc đúng ba trường
máy chủ trả, và nhờ vậy nói được điều quan trọng hơn: **đang chờ** (còn N việc trước) khác **đang
chạy** — gộp hai thứ đó làm thanh tiến độ nói dối.

---

## 8. Remaining Limits

* **Đã bấm tay trên Chrome thật — xem §9.** Còn ba thứ chưa kiểm được, nêu ở đó.
* **Chưa chạy một trang thật đầu-cuối qua trang chủ.** `translate_default_engine` trên production
  là `llm_context` ⇒ tốn token Gemini thật, nên chưa chạy khi chưa được phép.
* **Lưu lựa chọn tự-tải-về (§3.4) chưa làm.** Khách lạ lưu ở trình duyệt thì không cần backend;
  theo tài khoản thì chưa có cột nào.
* Trang chủ **chỉ nhận ảnh rời**, chưa nhận gói ZIP/CBZ (`Dropzone` có cờ `chapNhanGoi` nhưng
  đường `POST /doc-truyen/trang` nhận một ảnh mỗi lượt).
* Chưa có màn tài khoản (§4.4).

---

## 9. Live Verification — Chrome thật, 27-09

Trên `https://translation.vibe1.tinhgon.xyz` (bundle `index-CNLunwH7.js`, CSS `index-DSgn-SMb.css`
— **trùng hash bản build cục bộ**, nên style đã tới người dùng chứ không chỉ nằm trong `src`).

### Lỗi CORS lộ ra ĐÚNG như dự đoán, trước khi bản vá lên

Lần mở đầu (API còn `allow_credentials=False`), Chrome ghi:

```
Access to fetch at '…/api/v1/han-muc' from origin 'https://translation.vibe1.tinhgon.xyz'
has been blocked by CORS policy: The value of the 'Access-Control-Allow-Credentials' header
in the response is '' which must be 'true' when the request's credentials mode is 'include'.
```

Đây là bằng chứng bằng số đo cho điều §3.1 nói: **`curl` không thay được trình duyệt.** Cùng lúc
đó `curl /han-muc` trả 200 bình thường, và tôi đã dựa vào nó để nói hạn mức "đã LIVE" — câu đó sai.

Giao diện **hiện lỗi ra** kèm nút "Thử lại" thay vì im lặng hiện `0/0`. Nếu nó nuốt lỗi thì tôi
không bao giờ thấy.

### Sau bản vá — chuỗi khách lạ chạy đầu-cuối

Request thật của Chrome tới `/api/v1/han-muc`:

```
cookie: ma_khach=ek6t0aM5AM1uZjJjDWpJb4JQoBYDAfI7
origin: https://translation.vibe1.tinhgon.xyz
sec-fetch-site: same-site
→ 200
   access-control-allow-credentials: true
   access-control-allow-origin: https://translation.vibe1.tinhgon.xyz
   vary: Origin
```

`sec-fetch-site: same-site` cũng **xác nhận bằng số đo** một điều trước đó chỉ là suy luận: hai
hostname (`translation.` và `translation-api.`) cùng site dưới `tinhgon.xyz`, nên cookie
`SameSite=Lax` đi qua được. Nếu chúng khác site thì `Lax` sẽ chặn và phải đổi sang `SameSite=None`.

### Đo được trên màn

| Thứ | Giá trị đọc từ cây trợ năng |
|---|---|
| Hạn mức | **"6 / 6 trang còn lại"** |
| Mốc reset | **"Có lại sau 19 giờ 52 phút (0h00 giờ Việt Nam)"** |
| Luật 30 phút | *"ảnh gốc, bản dịch và tệp đã gói đều bị xoá: không chạy lại được, không sửa lại được. Muốn làm lại phải tải lên từ đầu và tốn thêm lượt."* |
| Thời gian mỗi trang | *"Mỗi trang mất khoảng 30 giây. Máy không treo — cứ để tab mở."* |
| Nút Dịch khi chưa chọn tệp | `disabled` kèm **lý do đọc được**: "Chọn ít nhất một trang" |
| Console | **sạch** (0 lỗi, 0 cảnh báo) |

### Chạy THẬT một trang đầu-cuối qua trang chủ (được chủ dự án cho phép)

Ảnh thử: 900×1280, hai bong bóng thoại chữ Anh trên nền có khối xám (để bước xoá chữ có việc thật,
không phải ảnh trắng trơn). Chọn ngôn ngữ **Tiếng Anh**, bấm "Dịch 1 trang".

| Đo được | Giá trị |
|---|---|
| Tiến độ giữa lượt | *"Tiến độ — xong 0/1 trang"* · bước **"Đọc chữ gốc…"** ⇒ nhận diện đã tìm được vùng chữ |
| Ô chọn ngôn ngữ lúc đang chạy | `disabled` — không cho đổi giữa dòng |
| Về đích | *"Tiến độ — xong 1/1 trang"* · **"Xong"** |
| Đồng hồ 30 phút | *"Còn 30 phút trước khi toàn bộ kết quả bị xoá"* — đếm từ lúc XONG, đúng §2.3 |
| **Ảnh khác nguồn** | `naturalWidth` = **900×1280** ⇒ tải được THẬT (cookie đi qua được cả trên request `<img>`) |
| **Lượt tải tự động** | *"Đã lưu trang-thu-e53-da-dich.png"* ⇒ **không bị chặn** trong Chrome headless |
| Nút thủ công | Có, và **không** bị khoá |
| Console | sạch |

### Mắt xích cuối của E49 — TIÊU LƯỢT — cũng đã chạy thật

Gọi lại `/han-muc` sau khi trang xong:

```json
{"tran": 6, "da_dung": 1, "con_lai": 5,
 "chot": [{"loai":"khach_cookie","da_dung":1},{"loai":"khach_ip","da_dung":1}]}
```

Giữ chỗ lúc tải lên → pipeline chạy → **tiêu** khi tới trạng thái cuối → hạn mức phản ánh đúng, và
**cả hai chốt** đều tăng. Đây là lần đầu toàn bộ sổ cái E49 chạy thật.

### Điều PHẢI nói rõ về lượt tải tự động

Nó không bị chặn **trong Chrome headless**. Chính sách chặn tải của trình duyệt headless **khác**
trình duyệt người dùng thật, nên kết quả này **không** chứng minh nó sẽ chạy trên máy người dùng.
Đó đúng là lý do nút thủ công luôn hiện và câu "nếu không thấy tệp nào…" luôn ở đó — xem §5.

### Còn chưa kiểm: lịch dọn tệp chạy thật

`BAT_LICH_DON_TEP` vẫn **TẮT**. Bộ phân loại an toàn của Claude Code từ chối bật nó (đúng — đây là
công tắc bật xoá dữ liệu không hoàn tác được), nên cần chủ dự án tự bật.

Khi bật, chapter thử ở trên là thứ đầu tiên bị dọn (mốc hết hạn = lúc xong + 30 phút). Đó cũng là
phép kiểm E50 rẻ nhất: theo dõi `GET /doc-truyen/trang/{id}` cho tới khi nó trả 404.
