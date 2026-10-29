# Đính chính ba bản spec — đọc TRƯỚC khi làm theo

**Ngày:** 2026-09-25 · **Áp dụng cho:** `MINI_SPEC_E47_VERIFICATION` ·
`CHECKLIST_AUDIT_STORAGE_LIFECYCLE` · `MINI_SPEC_QUOTA_LEDGER_ENFORCEMENT`

Ba bản trên viết tốt, nhưng có **ba lỗi đối chiếu với mã thật**. Một trong ba sẽ khiến người kiểm
thử **kết luận sai mà không biết**.

---

# LỖI 1 — Bản E47_VERIFICATION kiểm nhầm cơ chế ⚠️ NGUY HIỂM NHẤT

## Sai ở đâu

Bản đó kỳ vọng thấy dòng log:

> *"vùng X đọc ra 1 ký tự — dưới ngưỡng 2, bỏ qua"*

**Đó là dòng của một cơ chế KHÁC, đã có từ trước E47.** Nó là `inpaint_verify_min_chars` — phép
**đọc lại SAU khi xoá** để xem còn sót chữ không.

## Vì sao nguy hiểm

Dòng đó **đã xuất hiện** trong log production ngày 25-09. Người chạy test theo bản spec sẽ thấy
nó, tick "PASS", và kết luận E47 hoạt động — **trong khi chưa kiểm gì cả**.

## Dòng ĐÚNG của E47

```text
trang <id>: bỏ qua N/M vùng không đọc ra chữ thật (giữ nét vẽ)
```

E47 chạy **TRƯỚC khi xoá**. Cơ chế kia chạy **SAU khi xoá**. Hai thứ khác nhau hoàn toàn.

---

# LỖI 2 — Ngưỡng ghi sai

## Sai ở đâu

Bản E47_VERIFICATION §D3 ghi luật là `len(text.strip()) < 2`.

## Luật THẬT

| Trường hợp | Phép quyết định |
|---|---|
| Engine **có** trả điểm tin cậy (PaddleOCR) | `confidence >= 0.5` — **điểm là tiêu chí chính** |
| Engine **không** trả điểm (manga-ocr) | đếm **ký tự có nghĩa** (lọc qua regex) `>= 2` |

Mã: `ocr/engines.py: vung_dang_xoa_chu()`.

## Vì sao khác biệt không vụn

- Vùng đọc `"OK"` ở độ tin cậy **0,2**: `len(strip())` **giữ** (2 ký tự) · luật thật **bỏ** (điểm thấp).
- `len(strip())` **đếm cả dấu câu**; `dem_ky_tu_co_nghia` thì không. Vùng đọc `"..."` bị hai bên
  xử khác nhau.

Số đo đứng sau ngưỡng 0,5: trên 27 vùng thật, vùng nhiễu được **0,38**, mọi vùng chữ thật
**0,96–1,00**.

---

# LỖI 3 — KHÔNG có môi trường staging

## Sai ở đâu

Cả **ba** bản đều dựa vào "chạy staging trước", và đặt nó trong Stop Rules.

## Sự thật

Dự án chỉ có **hai** website, **cả hai đều là production**:

- `translation-api.cmc-1.vibenode.matbao.ai`
- `translation.cmc-1.vibenode.matbao.ai`

**Không có staging.** Ai cầm spec đi làm sẽ kẹt ngay bước đầu.

## Cách đi thay thế

Kiểm **cục bộ** với mô hình thật (đã làm được cho E47 — xem `REPORT_E47_VERIFICATION.md`), rồi
mới chạm production một lượt nhỏ có kiểm soát. Không tự dựng staging trong phạm vi các spec này.

---

# LỖI 4 (nhẹ) — Checklist storage quá rộng

Bản checklist liệt kê S3, Google Cloud Storage, Azure Blob, MinIO. **Mã chỉ hỗ trợ ba nền:**

```python
storage_backend: Literal["local", "postgres", "supabase"] = "local"
```

`storage.py` có ba hàm `delete` tương ứng. Phần lớn checklist không áp dụng.

**Câu thật sự cần trả lời chỉ có một:** production đang đặt `STORAGE_BACKEND` bằng gì?

Không đọc được từ cổng quản trị — nó **chỉ trả tên biến, không trả giá trị**. Đây là câu người
quản trị hạ tầng trả lời nhanh hơn dò mã.

---

# Điều chỉnh trình tự 5 bước

**Bước 1 (kiểm chứng E47) — ĐÃ XONG**, bằng cách khác với bản spec đề xuất: chạy đối chứng cục bộ
với mô hình thật, so ảnh ba bản. Kết quả ở `REPORT_E47_VERIFICATION.md`.

Luật E47 vốn đã có **đối chứng âm** (gỡ phép lọc ⇒ 3 bài test đỏ), mạnh hơn một lượt chạy tay.
Thứ còn thiếu là **bằng chứng ảnh**, và giờ đã có.

**Bước 2 (audit storage)** bị chặn bởi đúng một câu hỏi ở LỖI 4.

**Bước 3–5** giữ nguyên thứ tự, nhưng bỏ mọi yêu cầu "staging pass" và thay bằng "kiểm cục bộ +
một lượt production có kiểm soát".
