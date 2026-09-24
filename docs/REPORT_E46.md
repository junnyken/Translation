# Báo cáo Mini-Spec E46 — Nhận diện khung bong bóng bằng AI

**Project:** Translation · **Ngày:** 2026-09-24 · **Nền:** `41bf32c`
**Phạm vi:** Hướng **A** — 3 model × 5 trang × 3 lượt. Không đổi mã sản phẩm, không đụng production.
**Kết luận:** **Nhanh hơn 11–19× và tìm được gần hết chữ — NHƯNG khung quá rộng để làm mask xoá chữ.**

---

## 1. Câu trả lời ngắn

| Câu hỏi §2 của mini-spec | Trả lời |
|---|---|
| Nhanh hơn thật không? | **Có, rõ rệt.** 3,7s so với 42–70s cục bộ |
| Khung có dùng được không? | **Tìm chữ: được. Làm mask xoá chữ: CHƯA** |
| Tốn bao nhiêu? | 1280 token/trang (flash-lite) — hiện tốn 0 |
| Model nào tốt nhất? | **`gemini-3.1-flash-lite`** — xem §4 |

Giả thuyết của chủ dự án *"tôi nghĩ nó sẽ nhanh hơn"* — **đúng, và đo được**.

---

## 2. Số đo — 60 lượt gọi thật

| Model | Thành công | Độ trễ TB | Lâu nhất | Token TB | Khung TB |
|---|---|---|---|---|---|
| `gemini-3.1-flash-lite` | 15/15 | **3,78s** | 6,07s | **1280** | 4,8 |
| `gemini-3.8-flash` | 15/15 | 3,66s | 5,51s | 1386 | 5,5 |
| `gemini-3.1-pro-preview` | 15/15¹ | 8,49s | 14,25s | 1884 | 6,1 |
| **`comic-text-detector` (đang dùng)** | — | **42–70s** | — | **0** | 5,4 |

¹ 15 lượt đầu hỏng HTTP 400 vì cấu hình của tôi — xem §5.1. Chạy lại đủ 15/15.

**Token đếm THẬT từ `usageMetadata`, không ước lượng.** Với flash-lite: 1092 token ảnh + 65 nhắc
+ ~123 trả lời. Một chapter 24 trang ≈ **30.700 token** chỉ cho nhận diện — trong khi `llm_context`
chỉ-chữ đo được ~300 token/trang. Tức **nhận diện sẽ tốn gấp ~4 lần bước dịch**.

---

## 3. Một SỬA SAI phương pháp giữa chừng — IoU là chỉ số sai

Ban đầu tôi chấm bằng **IoU** với khung của model đương nhiệm. Kết quả: *"18/27 vùng được phủ"* —
nghe như AI sót một phần ba.

**Con số đó sai, và sai theo hướng phạt oan.** AI **gộp hai bong bóng liền nhau thành một khung**.
Khi đó mỗi khung cũ nằm *gọn bên trong* khung AI nhưng IoU vẫn thấp vì hai hình không trùng khớp.
Với bài này câu hỏi đúng là **"chữ có bị phủ không"**, không phải "hai khung có trùng khớp không".

Đo lại bằng **độ bao phủ diện tích**:

| Model | Phủ ≥90% | Phủ ≥50% | **Bỏ sót hẳn** (<10%) | **Diện tích thừa** |
|---|---|---|---|---|
| `gemini-3.1-flash-lite` | 21/27 | 25/27 | **2/27** | **1,74×** |
| `gemini-3.8-flash` | 26/27 | 26/27 | **1/27** | 2,70× |
| `gemini-3.1-pro-preview` | 25/27 | 25/27 | 2/27 | 2,18× |

IoU nói 18/27; độ bao phủ nói 25/27. **Giữ IoU thì tôi đã kết luận sai** rằng AI không dùng được.

Đây đúng bài học E44 ở dạng khác: chỉ số chọn sai thì số nào cũng ra, và nó trông rất thuyết phục.

---

## 4. Model nào tốt nhất — và vì sao KHÔNG phải model mạnh nhất

**Khuyến nghị: `gemini-3.1-flash-lite`.**

| Tiêu chí | Vì sao flash-lite thắng |
|---|---|
| **Tính ổn định** | **Ổn định tuyệt đối**: 5/5/5 · 9/9/9 · 3/3/3 · 3/3/3 · 4/4/4 qua 3 lượt. `gemini-3.8-flash` **lệch hẳn** một trang: **8 → 3 → 4 khung** |
| Khung khít nhất | thừa **1,74×**, so với 2,18× (pro) và 2,70× (3.8-flash) |
| Rẻ nhất | 1280 token, so với 1386 và 1884 |
| Nhanh | 3,78s — ngang 3.8-flash, nhanh hơn pro 2,2× |
| Đã dùng sẵn | đúng model production đang chạy cho `llm_context` |

Cái giá: sót **2/27** vùng thay vì 1/27.

**Model mạnh nhất KHÔNG thắng.** `gemini-3.1-pro-preview` chậm hơn 2,2×, tốn thêm 47% token, và
**không** che phủ tốt hơn `3.8-flash`. Nó tìm ra nhiều khung nhất (10 khung ở trang đầu so với 7
của model cũ) nhưng vẫn **sót 2/7** — tức khung thừa của nó nằm ở chỗ khác, không phải chỗ có chữ.

Tính bất định là rủi ro **cố hữu** của hướng dùng LLM (ONNX không có chuyện này), nên việc
flash-lite tất định ở nhiệt độ 0 là điểm cộng lớn nhất, không phải phụ.

---

## 5. Ba cái bẫy đã gặp thật

### 5.1. `pro` từ chối `thinkingBudget: 0`

Cả 15 lượt gọi pro trả HTTP 400. **Đọc thân lỗi** thay vì đoán:

```
Budget 0 is invalid. This model only works in thinking mode.
```

Bỏ `thinkingConfig` đi thì chạy. Nhưng chế độ nghĩ làm nó **chậm hơn 2,2× và tốn gấp rưỡi token** —
tức đây không chỉ là lỗi cấu hình, nó là **đặc tính giá/tốc độ** của bậc pro.

### 5.2. Model không giữ tên khoá được yêu cầu

Tôi bảo trả `box_2d`; nó trả `box`. Script vỡ ngay lượt đầu. Với ONNX thì chuyện này không tồn tại.
Đã viết bộ bóc nhận mọi tên khoá thường gặp — nhưng đây là **chi phí vĩnh viễn** của hướng này nếu
đưa vào sản phẩm, không phải sự cố một lần.

### 5.3. Định dạng toạ độ — xác minh bằng MẮT trước

Gemini trả `[ymin, xmin, ymax, xmax]` thang 0–1000. Đoán sai thứ tự sẽ cho khung **trông hợp lý mà
sai hoàn toàn**, và mọi chỉ số tính từ đó là rác. Stop Rule 1 bắt vẽ khung lên ảnh nhìn trước khi
tính gì — đã làm, và đó là lý do phần còn lại của báo cáo này đáng tin.

---

## 6. Rào chặn thật: khung quá rộng cho việc xoá chữ

Nhìn ảnh có vẽ khung: ở cả ba ô thoại, khung AI **tràn ra ngoài bong bóng vào phần nét vẽ**. Số
liệu khớp: diện tích thừa **1,74×** (flash-lite) tới **2,70×** (3.8-flash).

Khung không chỉ để biết chữ ở đâu — nó **thành mask cho LaMa**. Thừa 74% diện tích nghĩa là LaMa
**xoá cả nét vẽ quanh bong bóng**. Đây đúng rủi ro §4.3 của mini-spec, và nó đã xuất hiện.

**⇒ Chưa dùng thay `comic-text-detector` cho đường dịch đầy đủ được.**

---

## 7. Nhưng hướng này CHƯA chết — ba cách dùng vẫn còn

1. **Chế độ `chi_chu` (E19) — dùng được NGAY.** Chế độ này **không chạy xoá chữ**, nên độ khít gần
   như không quan trọng. Ở đó AI cắt bước nhận diện từ 42–70s xuống 3,8s mà không mất gì.
2. **Chia vai: AI tìm, model cũ tinh chỉnh.** AI khoanh vùng thô trong 3,8s, rồi chỉ chạy nhận diện
   cục bộ **trong các vùng đó** thay vì cả trang. Chưa đo.
3. **Thu khung lại.** Khung AI rộng đều một cách có hệ thống (1,74×) — có thể co lại bằng heuristic
   hoặc bằng chính ảnh. Chưa đo.

Cả ba đều **chưa đo**, và không được tính là đã có.

---

## 8. Giới hạn của báo cáo này

1. **n=5 trang, tất cả tiếng Anh, khung tranh phương Tây.** Bong bóng truyện Nhật, **chữ dọc**,
   chữ tượng thanh chồng lên nét vẽ — **không** nằm trong mẫu. Đó lại đúng là chỗ model chuyên trị
   truyện tranh thường thắng model tổng quát, nên kết quả ở đây có thể **lạc quan hơn** thực tế.
2. **Chưa đo chất lượng đọc chữ trong khung AI.** Mới đo *"khung có phủ chữ không"*, chưa đo *"OCR
   đọc trong khung AI có tốt bằng trong khung cũ không"*.
3. **Chưa tính rủi ro vận hành**: hiện nhận diện chạy được khi mất mạng; đổi xong thì Gemini chết
   là cả dây chuyền chết. Trần gọi Gemini tính theo **project**, không theo key.
4. **Chi phí tiền thật chưa quy đổi** — báo cáo chỉ nêu token đếm được, không đoán đơn giá.

---

# 9. BỔ SUNG — chi phí tiền thật, và hai phép thu khung ĐỀU THẤT BẠI

## 9.1. Chi phí: tra được, và nó RẺ

Đơn giá lấy từ bảng giá chính thức Gemini API; token lấy từ `usageMetadata` đã đo.

| Model | $/trang | **$/chapter 24 trang** | $/1000 trang |
|---|---|---|---|
| `gemini-3.1-flash-lite` | 0,000489 | **0,0117** | 0,49 |
| `gemini-3.8-flash` | 0,001453 | 0,0349 | 1,45 |
| `gemini-3.1-pro-preview` | 0,004344 | 0,1043 | 4,34 |

**Đính chính §2.** Tôi viết *"nhận diện sẽ tốn gấp ~4 lần bước dịch"* — đúng về token nhưng **gây
hiểu nhầm về mức độ**. Quy ra tiền là **1,2 xu Mỹ một chapter**. **Chi phí KHÔNG phải lý do để
loại hướng này.**

## 9.2. Hai phép thu khung — đều KHÔNG ăn thua

Mục §7.3 liệt kê *"thu khung lại"* như một hướng còn mở. **Đã thử, và thất bại cả hai lần.**

| Cách | flash-lite | 3.8-flash | pro |
|---|---|---|---|
| Thô (nguyên bản) | 1,74× | 2,70× | 2,18× |
| Thu theo hàng/cột sáng | 1,63× | 2,14× | 2,04× |
| Tách theo vùng liên thông | 1,74× | 2,64× | 2,18× |

**Một lỗi của tôi trong lần thử đầu:** đặt ngưỡng sáng 180 theo cảm tính. Đo ra mới biết nền ô
tranh có **trung vị 174**, nên 33,6% nền lọt qua và **dính liền với bong bóng** — vùng liên thông
nuốt cả hai nên không thể thu. Lấy ngưỡng từ số đo (trong bong bóng trung vị **255**; ngưỡng 235
cho bong bóng 80,5% còn nền 2,7%) rồi chạy lại: **vẫn 1,74×**.

⇒ Không phải chọn sai tham số. **Hai cách tiếp cận đều không đúng bài.**

## 9.3. Chỉ số "diện tích thừa" của tôi CONFLATE hai thứ khác nhau

Đây là chỗ tôi đã làm chính mình lạc hướng suốt §6 và §9.2.

"Thừa 1,74×" so khung AI với khung **CHỮ** của model cũ. Nhưng AI khoanh **BONG BÓNG**, mà bong
bóng vốn to hơn chữ trong nó. Nên một phần của 1,74× là **hợp lệ và vô hại** — xoá phần trắng trơn
trong bong bóng không phá gì cả.

Đo đúng thứ cần đo — bao nhiêu diện tích rơi vào chỗ **không phải bong bóng** (ngưỡng 235):

| Khung | % không phải bong bóng | Diện tích tuyệt đối | So model cũ |
|---|---|---|---|
| Model cũ (khoanh chữ) | 22% | 75k px | — |
| `gemini-3.1-flash-lite` | **23%** | 109k px | **1,5×** |
| `gemini-3.8-flash` | 35% | 293k px | **3,9×** |
| `gemini-3.1-pro-preview` | 23% | 160k px | 2,1× |

flash-lite ở **23%**, gần như y hệt model cũ (22%) — khung của nó **không** tệ hơn về tỉ lệ, chỉ to
hơn nên diện tích tuyệt đối gấp 1,5×. `gemini-3.8-flash` ở 35% / 3,9× thì **rõ ràng là xấu**.

⇒ **§6 vẫn đúng về hướng nhưng đã NÓI QUÁ mức độ.** Rủi ro xoá lẹm nét vẽ là thật, nhưng với
flash-lite nó ở mức **1,5× model cũ**, không phải thảm hoạ. Kiểm bằng mắt xác nhận khung có tràn
sang vành mũ ở hai ô và nuốt mảng nền ở ô gộp — có thật, nhưng cục bộ.

## 9.4. ĐÍNH CHÍNH: hướng "chia vai" ở §7.2 đã CHẾT

§7.2 đề xuất *"AI khoanh vùng thô, rồi chỉ chạy nhận diện cục bộ trong các vùng đó"*. **Không chạy
được, và lý do đã nằm sẵn trong E44.**

`ctd.py:_letterbox()` thu **mọi** đầu vào về khung vuông cố định 1024×1024 trước khi vào ONNX. Nên
chạy nhận diện trên một ô cắt nhỏ **tốn đúng bằng chạy cả trang**. Chạy trên 5 ô cắt = **5 lần**
chi phí cả trang, tức **chậm hơn** hiện trạng chứ không nhanh hơn.

Tôi viết §7.2 mà quên đúng phát hiện của chính mình hai giờ trước. Gạch bỏ.

## 9.5. Còn lại gì

| Hướng | Trạng thái |
|---|---|
| **Chế độ `chi_chu` (E19)** | **Dùng được ngay** — không xoá chữ nên độ khít không quan trọng; 42–70s → 3,8s |
| Thay hẳn cho đường đầy đủ | **Chưa** — cần giải bài khung lẹm 1,5×, mà 2 heuristic đã thử đều trượt |
| Chia vai AI + model cũ | **CHẾT** (§9.4) |
| Thu khung bằng heuristic | **Đã thử 2 cách, trượt cả hai** |

Cách chưa thử: yêu cầu model trả khung **CHỮ** thay vì khung **BONG BÓNG** (lời nhắc hiện tại nói
"speech balloon and text area" — chính nó mời model khoanh cả bong bóng). Đây là thay đổi **một
dòng lời nhắc**, rẻ nhất trong mọi hướng còn lại, và **chưa ai thử**.
