# MINI-SPEC ID: E46

**Name:** Đo thử nhận diện khung bong bóng bằng AI thay cho ONNX cục bộ
**Author + Date:** Phiên Claude Opus 5 / 2026-09-24
**Status:** Audit xong — **CHỜ DUYỆT ở §6**, chưa chạy lượt tính tiền nào
**Nguồn:** Chất vấn của chủ dự án sau khi E45 đóng hướng song song hoá

---

# 1. Vì sao hướng này khác mọi hướng đã đóng

E25 và E45 đã đóng **sáu** hướng. Nhìn lại thì cả sáu có chung một hình dạng: **chia lại cùng một
khối tính toán** (đổi số luồng, đổi số nhân, đổi cách xếp lịch, chia cho hai worker). Đều thất bại
vì cùng một lý do — khối tính toán ấy không đổi.

§8.2 của `REPORT_E45.md` đo được cơ chế: nhận diện và xoá chữ là **tính toán thuần**, không lúc nào
chờ đĩa hay mạng, nên ống dẫn không có chỗ rảnh để tận dụng.

Hướng này **bỏ hẳn khối tính toán đó ra khỏi máy**. Nếu nhận diện thành lượt gọi mạng thì CPU rảnh
xuất hiện — và đúng cái vừa làm hỏng E45 lại trở thành có lãi.

> ⚠️ **Đây là giả thuyết của chủ dự án, chưa phải kết luận.** Lượt gọi mạng *có thể* nhanh hơn
> 42–70s CPU, và điều đó nghe hợp lý — nhưng toàn bộ mục đích của E46 là **đo chứ không tin sẵn**.
> Hoàn toàn có khả năng model trả khung kém tới mức không dùng được, và khi đó nhanh hơn cũng vô
> nghĩa.

## Hạ tầng đã có sẵn — không phải xây từ đầu

E32 đã dựng đường gửi ảnh trang cho Gemini và giải quyết sẵn các bài khó:

| Đã có | Ở đâu |
|---|---|
| Thu ảnh về 1024px cạnh dài để chặn chi phí (Gemini tính tiền theo ô 768×768) | `translate/anh_kem.py` |
| Gửi ảnh + chữ trong một request, ảnh đứng TRƯỚC chữ | `translate/engines.py:270` |
| Xoay API key, đếm token, `token_cost` lưu theo vùng | đã LIVE |
| **Hỏng thì trả `None`, KHÔNG nổ** | `anh_kem.py` §Luật |

---

# 2. Câu hỏi cần trả lời

1. **Nhanh hơn thật không?** Độ trễ một lượt gọi so với 42–70s nhận diện cục bộ.
2. **Khung có dùng được không?** Đây mới là câu chặn — xem §4.
3. **Tốn bao nhiêu?** Nhận diện hiện **tốn 0 đồng**; đổi sang API là mỗi trang đều mất tiền.
4. **Model nào tốt nhất cho việc này?** (yêu cầu trực tiếp của chủ dự án)

---

# 3. Model đem so — tên đã TRA, không đoán

Truy vấn endpoint `models` bằng key thật: **44 model gọi được**. Ba ứng viên:

| Model | Vai trong phép đo |
|---|---|
| `gemini-3.1-flash-lite` | **Mốc** — đúng model production đang dùng để dịch |
| `gemini-3.8-flash` | Bậc flash mới nhất |
| `gemini-3.1-pro-preview` | Bậc mạnh nhất — để biết trần chất lượng ở đâu |

Cộng **mốc thứ tư: `comic-text-detector` hiện tại** (27 vùng trên 5 trang, đã đo).

---

# 4. Phần khó nhất — "khung tốt" nghĩa là gì

## 4.1. Không có chân lý nền, và KHÔNG được lấy model cũ làm chân lý

`comic-text-detector` là **đương nhiệm**, không phải chân lý. Lấy nó làm chuẩn thì mọi khác biệt
đều bị chấm là "sai", kể cả khi AI đúng hơn.

E44 đã ghi đúng cái bẫy này: **ít vùng hơn KHÔNG tự động là tệ hơn** — có thể là sót bong bóng
thật (tệ), cũng có thể là bớt bắt nhiễu (tốt), và **đếm vùng thì hai chuyện đó trông giống hệt
nhau**. E23 từng bật cờ rà soát oan 29% số trang vì 11 vùng chỉ đọc ra một ký tự nhiễu.

## 4.2. Hai phép kiểm khách quan, dùng hạ tầng đã có

**(a) Vùng có chữ thật không — chấm bằng OCR.**
Chạy PaddleOCR trên từng khung do AI đề xuất. Đọc ra chữ ⇒ vùng thật. Không ⇒ nhiều khả năng là
nhiễu. Đây là tiêu chí **tự động và khách quan**, và hạ tầng đã chạy được: lượt đo E45 cho
**27/27 vùng đều đọc ra chữ**.

**(b) Nhìn tận mắt.** Vẽ khung lên trang rồi xem. Bắt được đúng thứ số liệu che: khung lệch, khung
bao cả ô tranh, khung cắt mất nửa câu.

Hai phép này bù nhau: (a) chạy được hàng loạt nhưng mù với chuyện *khung đặt sai chỗ*; (b) thấy
được điều đó nhưng không nhân rộng.

## 4.3. Độ khít của khung — rủi ro CHẶN, không phải rủi ro phụ

Khung không chỉ để biết chữ ở đâu; nó **thành mask cho LaMa xoá chữ**. Hệ quả hai chiều:

- Khung **rộng quá** ⇒ LaMa xoá cả nét vẽ quanh bong bóng.
- Khung **chặt quá** ⇒ còn sót chữ gốc, chữ dịch đè lên chữ cũ.

Model thị giác tổng quát nổi tiếng là **trả khung xấp xỉ**. Đây là chỗ dễ làm cả hướng này chết,
và phải đo riêng chứ không gộp vào "có/không tìm ra vùng": đo **IoU** với khung đương nhiệm, và
nhìn tận mắt theo §4.2(b).

> 💡 **Nếu khung quá lỏng cho việc xoá chữ thì hướng này VẪN chưa chết.** Chế độ `chi_chu` (E19)
> **không chạy xoá chữ** — nó trả bản dịch dạng chú thích. Ở đó độ khít gần như không quan trọng.
> Nên kết quả có thể là *"dùng được cho `chi_chu`, chưa dùng được cho đường đầy đủ"*, và đó vẫn là
> một kết quả có giá trị.

---

# 5. Thiết kế phép đo

## 5.1. Mẫu

5 trang Pepper&Carrot CC BY-SA 1200×1660 đã dùng suốt E45 — **cùng mẫu nên so được trực tiếp** với
mốc 27 vùng đã đo.

> ⚠️ n=5 là mẫu nhỏ, và cả 5 đều **tiếng Anh, khung tranh phương Tây**. Bong bóng truyện Nhật,
> chữ dọc, chữ tượng thanh chồng lên nét vẽ — **không** nằm trong mẫu này. Mọi kết luận phải ghi
> kèm giới hạn đó.

## 5.2. Chống ba lỗi đặc thù của việc gọi LLM

1. **Định dạng toạ độ.** Gemini trả toạ độ chuẩn hoá theo quy ước riêng (thường `[ymin, xmin,
   ymax, xmax]` thang 0–1000). Đoán sai thứ tự hay thang sẽ cho ra khung **trông hợp lý mà sai
   hoàn toàn**. ⇒ **Phải xác minh bằng cách vẽ khung lên ảnh và nhìn**, trước khi tính bất kỳ chỉ
   số nào. Không có bước này thì mọi con số phía sau là rác.
2. **Không tất định.** Cùng ảnh, cùng prompt, hai lượt có thể khác nhau — khác hẳn ONNX. ⇒ **Chạy
   lặp 3 lượt mỗi trang mỗi model**, báo cáo độ dao động. Nếu chính nó đã dao động lớn thì khác
   biệt giữa các model là vô nghĩa.
3. **Token đếm THẬT.** Lấy từ `usageMetadata` trong phản hồi, **không** ước lượng. Dự án đã có
   tiền lệ token_cost lưu theo vùng.

## 5.3. Chi phí của chính phép đo

5 trang × 3 model × 3 lượt = **45 lượt gọi**. Ảnh đã thu về 1024px theo `anh_kem.py`.
**Tôi sẽ báo con số token và chi phí thật sau khi chạy, không ước lượng trước.**

---

# 6. QUYẾT ĐỊNH CẦN CHỦ DỰ ÁN CHỌN

| | Phạm vi | Chi phí |
|---|---|---|
| **A** ⟵ khuyến nghị | Chạy đủ §5: 3 model × 5 trang × 3 lượt, có bước xác minh toạ độ và nhìn tận mắt | 45 lượt gọi |
| **B** | Gọn hơn: chỉ `gemini-3.1-flash-lite` (model production) × 5 trang × 3 lượt | 15 lượt gọi |
| **C** | Không làm | 0 |

**Khuyến nghị A**, vì chủ dự án hỏi thẳng *"model nào tốt trong việc nhận diện chỗ chữ"* — câu đó
chỉ trả lời được khi có ít nhất ba bậc để so. B trả lời được "có khả thi không" nhưng **không**
trả lời được "model nào".

---

# 7. Kết quả cần có

| Model | Độ trễ/trang (từng lượt) | Token/trang | Vùng tìm được | Vùng CÓ CHỮ THẬT | IoU với đương nhiệm | Dao động giữa 3 lượt |
|---|---|---|---|---|---|---|

Cộng ảnh có vẽ khung của **ít nhất một trang mỗi model**, để người đọc tự nhìn thay vì tin bảng số.

---

# 8. Stop Rules

1. **Xác minh định dạng toạ độ TRƯỚC** khi tính bất kỳ chỉ số nào. Chưa vẽ ra nhìn thì chưa được
   tin con số nào.
2. **Đọc `REPORT_E25.md` §1 và `REPORT_E45.md` §8 trước khi mở rộng phạm vi** — đó là bảng những
   hướng đã đóng. Bỏ bước này là đúng cách E44 ra đời và chết trong cùng một ngày.
3. Ba lượt cùng model dao động lớn hơn khác biệt giữa các model ⇒ báo **"chưa đo được"**, cấm xếp
   hạng model.
4. **Không đổi mã sản phẩm trong E46.** Đây là mini-spec ĐO. Thay `comic-text-detector` là việc
   của một mini-spec khác, và chỉ được mở nếu E46 cho kết quả dương.
5. Kết quả âm ⇒ **báo đúng như vậy**. E25 và E45 đều đã khép với kết quả âm; đó là tiền lệ bình
   thường, không phải thất bại.
6. Phát hiện mới ngoài phạm vi ⇒ DỪNG, báo cáo 4 phần, không tự mở mini-spec giữa lượt.
