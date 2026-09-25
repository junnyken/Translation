# Báo cáo — Kiểm chứng đầu-cuối luật E47

**Ngày:** 2026-09-25 · **Nền:** `db9a992` (E47 đã deploy) · **Kết luận:** **ĐẠT**

---

## 1. Kết quả

Cùng một trang, cùng model cũ (`comic-text-detector`), chạy hai lượt xoá chữ — một lượt **có**
luật E47, một lượt **không**.

| Bản | Nét khói vẽ cạnh tẩu thuốc |
|---|---|
| Gốc | có |
| **Không luật** | **bị xoá sạch** — nền phẳng, thân tẩu còn bị cắt cụt |
| **Có luật E47** | **giữ nguyên**, y hệt bản gốc |

Ảnh so sánh ba bản: `scratchpad/e45/e47_sosanh.png` (phóng to 4×).

## 2. Quyết định từng vùng

Model cũ khoanh **7 vùng**. Luật xoá 6, bỏ qua 1:

| Vùng | Kích thước | Độ tin cậy | Ký tự có nghĩa | Quyết định |
|---|---|---|---|---|
| 0 | 246×130 | 1,00 | 76 | xoá |
| 1 | 270×77 | 0,99 | 45 | xoá |
| 2 | 162×24 | 0,98 | 10 | xoá |
| 3 | 182×50 | 1,00 | 28 | xoá |
| 4 | 56×22 | 0,97 | 3 | xoá |
| **5** | **53×38** | **0,38** | **1** | **BỎ QUA** |
| 6 | 286×21 | 0,98 | 31 | xoá |

Vùng 5 tại `(297, 1084)` đọc ra `'2'` — chính là **nét khói vẽ** bay lên từ tẩu thuốc.

**Tách bạch hoàn toàn:** vùng nhiễu 0,38 · mọi vùng chữ thật ≥ 0,97. Không có vùng nào ở vùng
xám.

## 3. Vì sao dùng trang tiếng Anh

`manga-ocr` chưa cài ở máy đo, nên không đọc được tiếng Nhật. Dùng PaddleOCR trên trang tiếng
Nhật sẽ cho **mọi** vùng ra rác — kể cả vùng chữ thật — và phép kiểm thành vô nghĩa.

⇒ Chưa kiểm được luật trên dữ liệu tiếng Nhật. Ghi là **CHƯA ĐO**.

## 4. ĐỪNG NHẦM với cơ chế đã có sẵn

Có một dòng log **rất giống** nhưng thuộc cơ chế khác:

```
kiểm chứng xoá chữ: vùng 5 đọc được 't' (1 ký tự) — dưới ngưỡng 2, BỎ QUA
```

Đó là `inpaint_verify_min_chars` — phép **đọc lại SAU khi xoá** để xem còn sót chữ không. Nó đã
có từ trước E47.

Luật E47 chạy **TRƯỚC khi xoá** và ghi dòng khác:

```
trang <id>: bỏ qua N/M vùng không đọc ra chữ thật (giữ nét vẽ)
```

**Thấy dòng đầu mà kết luận "E47 hoạt động" là sai.** Tôi đã suýt tự lừa mình bằng đúng dòng đó.

## 5. Luật thật — không phải `len(text.strip()) < 2`

| Trường hợp | Phép quyết định |
|---|---|
| Engine **có** trả điểm (PaddleOCR) | `confidence >= 0.5` — **điểm là tiêu chí chính** |
| Engine **không** trả điểm (manga-ocr) | đếm **ký tự có nghĩa** (lọc regex) `>= 2` |

Khác biệt không vụn: vùng đọc `"OK"` ở độ tin cậy 0,2 thì `len(strip())` **giữ** còn luật thật
**bỏ**. Và `len(strip())` đếm cả dấu câu, `dem_ky_tu_co_nghia` thì không.

## 6. Bằng chứng bổ sung đã có từ trước

- **Đối chứng âm**: gỡ phép lọc ra ⇒ 3 bài test đỏ; 2 bài "phải xoá" vẫn xanh (bộ test phân biệt
  được cả hai chiều).
- **Thiệt hại đã chứng minh**: chạy xoá chữ với 8 vùng model cũ khoanh trên trang tiếng Nhật có
  hiệu ứng phát sáng ⇒ toàn bộ ánh sáng và tia lấp lánh bị xoá sạch.

## 7. Giới hạn

1. **Chưa kiểm trên tiếng Nhật** (§3) — `manga-ocr` chưa cài.
2. **Chưa kiểm qua đường Celery/CSDL trên production.** Đường đó do bộ test đơn vị phủ (có đối
   chứng âm); lượt này kiểm **hiệu quả thật của luật lên ảnh**.
3. Mẫu: **một trang, 7 vùng**.
4. Không có môi trường staging — dự án chỉ có `translation-api` và `translation-web`, cả hai đều
   là production.
