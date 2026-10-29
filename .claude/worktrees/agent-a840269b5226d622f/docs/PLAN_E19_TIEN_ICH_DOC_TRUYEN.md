# KẾ HOẠCH E19 — tiện ích đọc truyện: bấm một cái, phủ chữ dịch lên bong bóng

*Lập 2026-09-05 · nối tiếp E1 (`REPORT_E1.md` — tiện ích Chrome hiện có)*

Người dùng đã chốt hai hướng:

1. **Phủ chữ dịch lên bong bóng**, giữ nguyên ảnh gốc (không xoá chữ, không căn chữ).
2. **Bất kỳ trang web nào** — tiện ích tự dò ảnh lớn nhất trên màn.

## 1. Phát hiện chặn đường, tìm ra trước khi viết dòng mã nào

Đo trên bản chạy thật, hai trang liên tiếp cùng một ảnh:

| Bước | Trang 1 | Trang 2 |
|---|---|---|
| Nhận diện | 49,5s | **49,5s — không nhanh lên chút nào** |
| OCR | 30,8s | 6,7s ✓ |
| Xoá chữ | 7,7s | 6,3s |
| Dịch | 0,5s | 0,5s |
| Căn chữ | 0,15s | 0,1s |

OCR nóng lên đúng như mong đợi. **Nhận diện thì không** — nó tốn 49,5 giây mỗi trang, mọi lần.

Log nói vì sao:

```
trang 1 · xoá chữ xong : RSS 1819,9 MB   ← LaMa nạp vào, sát trần
trang 2 · nhận diện    : RSS 1085,1 MB   ← tụt 735 MB: mô hình đã bị NHẢ
07:47:36  Nạp CTD ONNX        ← nạp lại bộ nhận diện
07:48:26  Nạp manga-ocr       ← nạp lại OCR
07:48:32  Nạp LaMa ONNX       ← nạp lại LaMa
```

**Mỗi trang nạp lại toàn bộ mô hình.** Van xả bộ nhớ — thứ thêm vào để chặn OOM sau ba lần worker
bị giết — đang nhả sạch mô hình sau mỗi trang. Nó làm đúng việc của nó; cái giá là thông lượng.

> Chậm không nằm ở pipeline. Nó nằm ở chỗ **máy chủ thiếu RAM nên phải nạp lại mô hình liên tục**.

## 2. Vì sao điều đó lại là tin tốt cho hướng đã chọn

LaMa (xoá chữ) chính là thứ đẩy RSS từ ~1000 MB lên ~1820 MB và làm van xả bật. Hướng **phủ chữ**
không cần LaMa.

> ⚠️ **Đoạn dưới đây đã được ĐO và nó SAI.** Giữ nguyên để thấy lập luận sai ở đâu; kết quả thật
> ở `docs/REPORT_E19_0_DO_COND_CHAN.md`.
>
> ~~**Giả thuyết:** bỏ bước xoá chữ ⇒ van xả không bật ⇒ bộ nhận diện và OCR nằm lại trong bộ
> nhớ ⇒ thời gian mỗi trang giảm **khoảng một bậc**.~~

**Đo ra:** nạp mô hình chỉ tốn **0,3–0,5 giây**, không phải 45 giây. Toàn bộ chi phí nằm ở phép
suy luận (~40–50s) và nó **không nóng lên**. Việc nạp lại mô hình *có* xảy ra như tôi đọc từ log,
nhưng nó gần như không tốn gì — tôi gán sai chi phí cho một hiện tượng có thật.

Bỏ bước xoá chữ **vẫn đáng làm**: cắt 6–17s mỗi trang và hạ RSS đỉnh ~800 MB. Nhưng nó **không**
đổi được bậc thời gian, và nút thắt là **CPU** chứ không phải RAM.

> **Đính chính 2026-09-10 (E25):** con số "6–17s" nói **thấp hơn thực tế ~8 lần** cho nội dung
> thật. Nó đo trên trang có rất ít vùng chữ; LaMa chạy theo **từng cụm chữ**, nên trên trang truyện
> thật 7–9 vùng bước xoá chữ tốn **~51s/trang (38% tổng thời gian)**. Câu "không đổi được bậc thời
> gian" vì vậy cũng sai theo: chế độ `chi_chu` cắt ~53s/trang, tức **~40%**. Số đo:
> `REPORT_E25.md §2.1`. Phần "nút thắt là CPU" thì đúng — và E25 đo thêm được rằng thêm CPU cũng
> **không** cứu được (§2.7).

⇒ Hình dung *"bấm là hiện chữ ngay"* **không sống được**. Hình dung thay thế, người dùng đã chọn
đi tiếp: **"bấm để xếp hàng, đọc tiếp, lát sau chữ hiện ra"** — dịch trước vài trang kế trong lúc
người đọc đang xem trang hiện tại. Với ~45s/trang và người đọc 1–2 phút/trang thì **kịp**, miễn là
bắt đầu sớm hơn một hai trang.

## 3. Vì sao KHÔNG dùng lại tiện ích E1

`extension/PRIVACY.md` đang hứa nguyên văn, và mã nguồn hiện đúng như vậy:

- *Không đọc trang web bạn đang xem* — không `content_scripts`, `host_permissions` **rỗng**
- *Không tự tải ảnh từ internet*
- *Không phủ bản dịch lên trang*

E19 cần **cả ba**. Sửa E1 mà giữ PRIVACY.md là biến một tài liệu đang đúng thành tài liệu nói dối;
sửa cả PRIVACY.md thì người đã cài E1 vì đúng những lời hứa đó bị đổi bản chất dưới chân.

⇒ **Tiện ích riêng, tên riêng, tài liệu quyền riêng tư riêng.** E1 giữ nguyên.

## 4. Đường đi của một lần bấm dịch

```
1. content script  : tìm ảnh lớn nhất đang hiện trên màn
2. service worker  : tải BYTE của ảnh đó (host_permissions vượt được CORS)
3. → backend       : tải ảnh lên, chạy nhận diện → OCR → dịch  (KHÔNG xoá chữ, KHÔNG căn chữ)
4. ← backend       : danh sách vùng (toạ độ theo pixel ảnh) + chữ gốc + bản dịch
5. content script  : phủ lớp chữ Việt trong suốt lên đúng từng bong bóng
```

Bước 3 là chỗ backend phải đổi: hiện chuỗi việc **bắt buộc** đi qua xoá chữ, vì bước dịch được
xếp hàng từ trong task xoá chữ.

**Đã kiểm: bước dịch KHÔNG phụ thuộc bước xoá chữ.** `_run_translate` chỉ đọc `TextRegion` và
`OCRResult` từ CSDL, không chạm ảnh clean hay kho lưu trữ. Chúng chỉ đang được nối chuỗi theo thói
quen. Nên thêm một chế độ *chỉ-chữ* là nối lại dây, không phải viết lại logic.

## 5. Việc phải làm

| # | Việc | Ghi chú |
|---|---|---|
| **E19-0** | **Đo: bỏ xoá chữ thì mô hình có nằm lại không** | **cổng chặn** — sai thì dừng cả kế hoạch |
| E19-1 | Chế độ *chỉ-chữ*: sau OCR xếp thẳng việc dịch, bỏ qua xoá chữ + căn chữ | dây nối, không phải logic mới |
| E19-2 | Endpoint gộp cho tiện ích: nhận ảnh → trả vùng + chữ gốc + bản dịch | tránh bắt tiện ích tự nối 4 lời gọi |
| E19-3 | `started_at` cho job | hiện **không** phân biệt được "đang xếp hàng" với "đang chạy" — người đang chờ cần biết |
| E19-4 | Tiện ích mới: content script dò ảnh lớn nhất + lớp phủ | dự án riêng trong `extension-doc-truyen/` |
| E19-5 | Đăng nhập trong tiện ích | slice B bắt buộc mã phiên; không thể để tiện ích gọi API trần |
| E19-6 | PRIVACY.md mới, viết đúng thứ mã làm | E1 đã có tiền lệ tốt, theo đúng khuôn đó |
| E19-7 | Khai báo mục đích sử dụng như M10 | tiện ích không được là đường vòng né cổng khai báo của bản web |

## 6. Phần khó, đã biết trước

| Việc | Vì sao khó |
|---|---|
| **Dò "ảnh lớn nhất"** | quảng cáo, banner, ảnh nền đều có thể to hơn trang truyện. Cần thêm luật: tỉ lệ khung, vị trí trong luồng đọc, kích thước thật vs kích thước hiển thị |
| **Canvas bị nhiễm bẩn** | ảnh khác nguồn làm `toDataURL` ném lỗi bảo mật. Phải tải byte ở service worker bằng `host_permissions`, không đọc qua canvas |
| **Trang vẽ bằng canvas / chống sao chép** | không có `<img>` để lấy ⇒ chịu. Phải nói thẳng là không hỗ trợ, không im lặng thất bại |
| **Đặt lớp phủ đúng chỗ** | vùng trả về theo pixel ảnh gốc; trang hiển thị đã co giãn, có thể còn xoay/lật. Phải quy đổi theo `naturalWidth` vs `clientWidth`, và bám theo khi cuộn/đổi cỡ cửa sổ |
| **Chữ Việt dài hơn chữ Nhật** | phủ chữ không có bước căn chữ nên không kiểm được tràn. Cần cho chữ tự xuống dòng + cuộn trong lớp phủ, hoặc hiện dạng chú thích khi quá dài |
| **`<all_urls>`** | quyền rộng nhất Chrome cấp. Duyệt lên cửa hàng sẽ bị soi; và nó đòi tài liệu quyền riêng tư phải rất rõ |

## 7. Cách biết E19 thành công

1. **E19-0 trả lời được** — mô hình có nằm lại hay không, kèm số RSS trước/sau.
2. Trang **thứ hai trở đi** nhanh hơn trang đầu rõ rệt. Nếu trang nào cũng như trang đầu thì
   tiện ích không dùng được, và phải nói thẳng thay vì phát hành.
3. Dò trúng ảnh truyện trên vài trang thật, đếm số lần dò nhầm — **không** tự nhận "chạy tốt"
   dựa trên một trang.
4. Lớp phủ nằm đúng bong bóng sau khi cuộn và đổi cỡ cửa sổ.

## 8. Không làm trong E19

- **Không** đụng tiện ích E1.
- **Không** thay ảnh trên trang (đó là hướng còn lại, người dùng đã không chọn).
- **Không** tự động dịch cả chapter — mỗi lần một trang, do người bấm.
- **Không** nới van xả bộ nhớ để mô hình nằm lại. Van đó có sau ba lần worker bị giết vì OOM;
  nới nó là đổi một cái chậm lấy một cái chết.
