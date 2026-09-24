# MINI-SPEC ID: E43

**Name:** Trang không có chữ làm kẹt pipeline và làm xem-trước báo sai
**Author + Date:** Phiên Claude Opus 5 / 2026-09-24
**Status:** Audit xong — chờ duyệt trước khi code
**Phát hiện từ:** Lượt chạy chapter 24 trang trên production (Phase 2b)

---

# 1. Hiện tượng

Chapter 24 trang chạy trên production **đứng im ở 19/24** hơn 15 phút. 5 trang kẹt vĩnh viễn ở
`detected`.

`order` của 5 trang kẹt: **[2, 7, 12, 17, 22]** — cách đều đúng 5. Gói dựng từ **5 trang gốc lặp
lại**, nên cả 5 là **cùng MỘT ảnh**. Không ngẫu nhiên: **một ảnh cụ thể luôn kẹt**, tái hiện 5/5.

```
detect  → done    · kết quả: 0 vùng chữ  (trang tranh thuần, không thoại)
ocr     → failed  · "no_region: page chưa có TextRegion nào (chạy detect trước)"
```

---

# 2. Nguyên nhân

## 2.1. Gốc: OCR coi "không có chữ" là LỖI

`tasks.py:397` — `_run_ocr` gặp 0 vùng thì đánh dấu job `failed` và dừng chuỗi. Cùng khuôn ở
`tasks.py:791` (xoá chữ) và `tasks.py:1097` (dịch).

Thông báo lỗi còn **nói sai sự thật**: nó bảo *"chạy detect trước"* trong khi detect **đã chạy
xong và thành công**. Người đọc log sẽ đi sửa nhầm chỗ.

## 2.2. E38 đã giải đúng bài này — nhưng chỉ ở MỘT nửa hệ thống

E38 (14-09) đã thêm sẵn hàm phân biệt, và nó **đúng chính xác**:

```python
def trang_khong_co_chu(session, page) -> bool:
    if page.status is not PageStatus.detected:
        return False
    return not session.scalar(select(TextRegion.id).where(...).limit(1))
```

Docstring của nó ghi rõ: *"`detected` + 0 vùng nghĩa là máy đã xem trang và xác nhận không có
chữ, không phải 'chưa xem' hay 'xem hỏng'. Với trang như thế, ảnh gốc CHÍNH LÀ kết quả hoàn
thiện."*

**Nhưng hàm đó chỉ được gọi ở 2 chỗ, cả hai đều trong `tasks.py`:**

| Nơi | Có dùng `trang_khong_co_chu`? |
|---|---|
| `tasks.py:2199` — cổng xuất của worker | ✅ có |
| `tasks.py:2251` — dựng file xuất | ✅ có |
| **`routes.py:1720` — endpoint `export-preview`** | ❌ **KHÔNG** — vẫn so trạng thái trần |
| **`tasks.py:397/791/1097` — pipeline** | ❌ **KHÔNG** — vẫn coi là lỗi |

Đây đúng kiểu hỏng *"sửa một tệp mà không quét cả repo"*.

---

# 3. Mức nghiêm trọng — ĐO ĐƯỢC, không suy đoán

> ⚠️ **Đính chính một kết luận sai của chính lượt điều tra này.** Ban đầu tôi báo *"file xuất
> thiếu 5 trang — mất dữ liệu"*. Con số đó lấy từ `export-preview`, tức **chính đường bị lỗi**.
> Chạy xuất thật rồi đếm trong ZIP mới ra sự thật.

| Phép đo trên production | Kết quả |
|---|---|
| `export-preview` báo | **19 trang** · bỏ qua 5 |
| **File ZIP xuất thật** | **24 trang** |

**⇒ KHÔNG mất dữ liệu.** E38 hoạt động đúng ở đường xuất thật.

## Ba hậu quả thật, xếp theo mức nặng

| # | Hậu quả | Mức |
|---|---|---|
| 1 | **Màn "Dịch nhanh" treo.** `demTienDo` xếp `detected` hạng 2, cần hạng 6 ⇒ không bao giờ thấy xong ⇒ hỏi lại tới hết trần **2.400 lượt × 3 giây = 2 tiếng** rồi mới bỏ cuộc. Trang tranh thuần rất phổ biến (bìa chương, trang splash) ⇒ **ĐX-1 sẽ treo với phần lớn chapter thật** | **CAO** |
| 2 | **Xem-trước báo sai số.** Người dùng thấy "sẽ xuất 19, bỏ qua 5" rồi nhận file 24 trang. Cảnh báo sai làm người ta mất tin vào mọi cảnh báo khác | Trung bình |
| 3 | **Job OCR bị đánh dấu `failed`** kèm thông báo sai sự thật, làm bẩn lịch sử job và panel "Vì sao?" | Thấp |

Lượt 3 trang hôm qua **không thể** tìm ra, vì cả 3 trang đều có thoại. Đúng như E23 đã ghi: lượt
dài lôi ra thứ lượt ngắn không thể.

---

# 4. Hướng sửa đề xuất

## 4.1. Sửa GỐC, không sửa triệu chứng

Nếu pipeline cho trang không chữ đi hết chuỗi tới `typeset_done`, thì **cả ba hậu quả tự hết**:
màn Dịch nhanh đếm đủ, xem-trước khớp, job không còn `failed`. Sửa ở ngọn (vá riêng frontend hoặc
riêng `export-preview`) sẽ để lại hai chỗ kia.

Chuỗi hợp lệ theo `PAGE_STATUS_TRANSITIONS`:

```
detected → ocr_done → inpainted → translated → typeset_done
```

Mỗi bước **không có gì để làm** với trang 0 vùng. Cần quyết một trong hai:

| Cách | Ưu | Nhược |
|---|---|---|
| **A — mỗi bước tự nhận "không có việc" rồi nối tiếp** | Đúng kiến trúc "mỗi bước một service, nối qua Celery" (CLAUDE.md §2). Giữ nguyên khả năng chạy lại từng bước | Sửa 3 chỗ; chạy 3 job rỗng |
| **B — rẽ tắt ngay ở bước OCR, đẩy thẳng tới `typeset_done`** | Sửa 1 chỗ, không tốn job rỗng | Nhảy nhiều bậc trạng thái trong một lượt; lệch kiến trúc |

**Khuyến nghị: A.** Dự án đã chốt nguyên tắc mỗi bước là service riêng, và cách A giữ được khả
năng quan sát/chạy lại từng bước.

## 4.2. Dùng lại `trang_khong_co_chu`, KHÔNG viết phép kiểm mới

Hàm đã có, docstring đã giải thích đầy đủ, đã được 2 nơi tin dùng. Viết phép kiểm thứ hai cho
cùng khái niệm là tạo nguồn sự thật thứ hai — đúng thứ vừa tránh được ở Mini-Spec P0-P1.

## 4.3. Quét CẢ repo

`routes.py:1720` bị sót vì E38 chỉ sửa trong `tasks.py`. Lần này phải **quét hết** mọi nơi so
`status in (typeset_done, ready_for_export)` và xét xem chỗ đó có cần `trang_khong_co_chu` không.

---

# 5. Rủi ro của bản sửa

| Rủi ro | Cách chặn |
|---|---|
| **Nuốt mất lỗi thật.** Gộp "detect xong, 0 vùng" với "detect hỏng nên không có vùng" sẽ làm trang hỏng thật lặng lẽ trôi vào file xuất | `trang_khong_co_chu` đã phân biệt bằng `page.status is detected`; `detection_failed` vẫn rơi ra. **Bắt buộc có test đối chứng cho `detection_failed`** |
| Trang 0 vùng đi tới `typeset_done` mà **không có ảnh căn chữ** | E38 đã xử: *"ảnh gốc CHÍNH LÀ kết quả hoàn thiện"*. Cần xác nhận đường xuất lấy đúng ảnh gốc — **audit trước khi code** |
| Đổi hành vi pipeline ảnh hưởng chapter đang chạy | Chỉ đổi nhánh 0 vùng; trang có vùng không đi qua nhánh mới |

---

# 6. Test bắt buộc

- Trang `detected` + 0 vùng → đi hết chuỗi tới `typeset_done`, **không** job nào `failed`
- Trang `detection_failed` → **vẫn** bị loại, **vẫn** không xuất (đối chứng chống nuốt lỗi)
- Trang có vùng → hành vi **không đổi** (đối chứng hồi quy)
- `export-preview` và file xuất thật trả **cùng một con số** — chính chỗ đang lệch
- `demTienDo` ở frontend đếm trang 0 vùng là đã xong
- Toàn bộ 1.649 backend + 396 frontend vẫn xanh

---

# 7. Stop Rules

1. Audit đường lấy ảnh cho trang 0 vùng **trước khi** viết code — không đoán.
2. Quét cả repo tìm mọi nơi so trạng thái xuất, không chỉ sửa 2 chỗ đã biết.
3. Phát hiện mới ngoài phạm vi ⇒ DỪNG, báo cáo 4 phần.
4. Không deploy nếu chưa chạy thật lại một chapter có trang không chữ.
