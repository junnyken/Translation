# REPORT E19-0 — cổng chặn: 49,5 giây kia là nạp mô hình hay là suy luận?

*2026-09-05 · phép đo quyết định ý tưởng tiện ích đọc truyện sống hay chết*

## Kết luận ngắn

**Là suy luận. Giả thuyết của tôi SAI.**

Tôi đã viết trong `PLAN_E19` rằng bỏ bước xoá chữ sẽ giúp mô hình nằm lại trong bộ nhớ và
thời gian mỗi trang "giảm khoảng một bậc". Đo ra thì **nạp mô hình chỉ tốn 0,3–0,5 giây** —
không phải 45 giây. Toàn bộ chi phí nằm ở phép suy luận, và nó **không nóng lên** qua các lượt.

## Số đo

Mô hình nạp lười (`_get_session`) nên bấm giờ tách được hai phần — thứ log trên bản chạy không
làm được, vì ở đó nạp và suy luận nằm chung một task.

| | Nạp mô hình (94 MB) | Suy luận |
|---|---|---|
| 12 nhân | **0,3–0,5s** | 40–47s |
| 3 luồng (ghìm cho giống bản chạy) | 0,3–0,4s | 112–114s |
| **Bản chạy thật (2,6 CPU)** | — | **49,5s** |

Bản chạy khớp với cột 12 nhân ⇒ container thấy hết nhân của máy chủ, `--concurrency=1` giới hạn
số **task** chứ không giới hạn số luồng của ONNX.

Suy luận lặp lại ba lượt trên cùng một phiên: **114,6s · 112,7s · 113,2s** — không có dấu hiệu
nóng lên nào.

## Vì sao tôi đoán sai

Log trên bản chạy cho thấy RSS tụt 1819,9 → 1085,1 MB giữa hai trang, kèm ba dòng `Nạp ... ONNX`.
Tôi đọc đúng hiện tượng (**mô hình thật sự bị nhả và nạp lại mỗi trang**) nhưng **gán sai chi phí**
cho nó. Việc nạp lại có xảy ra; nó chỉ không tốn gì đáng kể.

Bài học: một hiện tượng có thật đứng cạnh một con số lớn không có nghĩa nó là nguyên nhân của
con số đó. Phải đo riêng phần bị nghi ngờ.

## Ba cần gạt đã thử

| Cần gạt | Kết quả |
|---|---|
| **Hạ kích thước đầu vào** (1024 → 640) | **không có cần gạt này** — mô hình xuất với đầu vào **cố định 1024×1024**, đưa cỡ khác vào là ONNX từ chối |
| **Lượng tử hoá INT8** (`QInt8`) | **chạy không được** — onnxruntime CPU bản này thiếu `ConvInteger` |
| **Lượng tử hoá `QUInt8`** | **1,31x** — 49,1s → 37,3s (trung vị 3 lượt xen kẽ), lệch toạ độ ≤ 7 px, cùng số vùng |

Lượt đo đầu của `QUInt8` ra 1,01x rồi 1,70x trên hai ảnh — mâu thuẫn, và lượt FP32 khi đó (56,8s)
lệch hẳn so với 40,5s đo trước đó cùng loại việc. Đó là nhiễu máy. Chỉ sau khi **đo lặp, xen kẽ
hai mô hình** mới ra con số dùng được. Ghi lại vì suýt nữa đã báo cáo 1,70x.

## Ý tưởng tiện ích còn sống không

Ở mức "bấm là đọc được ngay": **không**.

Đường phủ chữ (nhận diện → OCR → dịch), lấy số tốt nhất đo được:

```
nhận diện  ~37s  (QUInt8)      ← chiếm gần hết
OCR         ~7s  (khi đã nóng)
dịch        ~0,5s
            ~45s một trang
```

Và `--concurrency=1` nghĩa là các trang **xếp hàng**, không chạy song song.

Bỏ bước xoá chữ **vẫn đáng làm** — nó cắt 6–17s và hạ RSS đỉnh khoảng 800 MB — nhưng nó
**không** đổi được bậc thời gian như tôi đã viết trong kế hoạch. Câu đó trong `PLAN_E19` §2 sai
và phải sửa.

## Còn đường nào

| Hướng | Đánh giá |
|---|---|
| Đổi kỳ vọng: "bấm rồi đọc tiếp, lát sau quay lại" | **khả thi ngay** — không cần đổi gì về kỹ thuật, chỉ đổi cách tiện ích trình bày việc chờ |
| Dùng `QUInt8` | 1,31x, rẻ, nhưng phải đo lại **trên bản chạy** vì tỉ lệ này đo ở máy 12 nhân |
| Thêm CPU cho máy chủ | chặn — gói đã kịch trần (`QUOTA_EXCEEDED`, `canUpgrade: false`) |
| Xuất lại mô hình ở cỡ nhỏ hơn | cần trọng số gốc và quy trình xuất của `comic-text-detector` — việc lớn, chưa khảo sát |
| Đổi sang bộ nhận diện nhẹ hơn | việc lớn, và đánh đổi chất lượng chưa đo được |

## Đề nghị

Không dựng tiện ích theo hình dung "bấm là hiện chữ ngay" — với 45 giây một trang thì nó sẽ bị
bỏ sau lần thử thứ hai.

Nếu vẫn muốn làm, làm theo hình dung khác: **bấm để xếp hàng, đọc tiếp, lát sau chữ hiện ra** —
và tiện ích phải nói rõ đang xếp hàng thứ mấy. Việc đó lại cần `started_at` cho job (E19-3), thứ
hiện chưa có.

---

# Kiểm chứng trên bản chạy thật (2026-09-07)

Sau khi deploy E19-1/2/3, gửi một trang qua đúng đường tiện ích
(`POST /api/v1/doc-truyen/trang`).

## Chuỗi việc rẽ đúng — log của chính worker nói

```
detect     succeeded in 49.17s  → ocr_job_id: ff1060e5…
ocr        succeeded in 28.38s  → inpaint_job_id: None   ← bỏ xoá chữ
                                   translate_job_id: ffcdb8a8…
translate  succeeded in  0.90s  → typeset_job_id: None   ← bỏ căn chữ
```

Và tra `GET /pages/{id}/jobs`: đúng **ba** việc chạy (`detect`, `ocr`, `translate`), cả ba đều có
`started_at`. Không có việc xoá chữ, không có việc căn chữ.

Trang dừng ở `translated` và endpoint trả `xong: true` — đúng đích của chế độ chỉ-chữ, không chờ
`typeset_done` (thứ không bao giờ tới).

## Con số thật, và nó KHÔNG đẹp như tôi ước

| Bước | Thời gian |
|---|---|
| Nhận diện | **49,2s** |
| OCR | **28,4s** (nguội — lượt nóng đo trước đó là 6,7s) |
| Dịch | 0,9s |
| **Tổng công thật** | **78,5s** |
| Tường (gồm cả xếp hàng sau 4 việc) | 165s |

So với đường đầy đủ đo hôm trước (nhận diện 49,5 + OCR 6,7 + xoá chữ 6,3 + dịch 0,5 + căn chữ
0,1 = **63,1s** khi mọi thứ đã nóng): chế độ chỉ-chữ cắt được **6,4s** — đúng khoảng "6–17s" đã
dự đoán, **không hơn**.

Ước lượng thật cho tiện ích, lấy lượt OCR nóng: **~57 giây một trang**, chứ không phải 45 giây
như tôi đã nói. Con số 45 kia lấy từ OCR nóng cộng bước nhận diện đã lượng tử hoá — mà lượng tử
hoá thì **chưa triển khai**, nó mới chỉ được đo ở máy phát triển.

## Điều này đổi gì cho hình dung "bấm rồi đọc tiếp"

Vẫn sống, nhưng biên hẹp hơn tôi nói. Với ~57s/trang và người đọc 1–2 phút/trang, tiện ích phải
bắt đầu dịch **sớm hơn ít nhất một trang** mới kịp — và nếu hàng đợi có sẵn việc khác thì không
kịp. `so_viec_cho_truoc` trong phản hồi chính là để người dùng thấy điều đó thay vì ngồi đoán:
lượt đo này bắt đầu với `chờ sau 4` và mất 165 giây tường.

## Còn nợ

Chưa thử tiện ích trên **trang truyện thật**. Toàn bộ số trên đo bằng ảnh dựng gửi qua `curl`;
phần chọn ảnh và lớp phủ mới chỉ có test đơn vị, chưa lần nào chạm một trang web thật.
