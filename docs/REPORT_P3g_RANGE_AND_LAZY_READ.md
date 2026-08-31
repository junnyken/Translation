# Báo cáo Mini-Spec P3g — Trả lại `Range`, bỏ nạp cả hiện vật vào RAM, đo độ trễ thật

**Ngày:** 2026-08-31 · **Trạng thái:** ✅ **XONG — đã deploy, đã đo trên host**
**Phụ thuộc:** P3e `ĐÃ DEPLOY` · P3d · P3c

## Summary

Đóng ba khoản nợ mà P3d/P3e đã **nhận có chủ đích**:

1. **Mất hỗ trợ `Range`** — P3d đổi `FileResponse` sang luồng thì mất tính năng Starlette tự lo.
2. **Mỗi lượt phục vụ giữ cả hiện vật trong RAM** — `open_read()` của backend CSDL trả `BytesIO`.
3. **Chưa đo độ trễ thật trên host.**

Hai cái đầu hoá ra là **một** bài toán: có `read_range()` thì có luôn cả hai.

## Design Choice

### `read_range()` là nền của cả hai

```
read_range(path, offset, length)
  ├── HTTP Range  → 206 / Content-Range
  └── luồng lười  → open_read() không còn nạp cả hiện vật
```

Backend `postgres` hiện thực bằng `substr()` **phía máy chủ**. Đây là chỗ
`SET STORAGE EXTERNAL` (migration 0010 của P3e) trả công: cột không bị nén nên Postgres giải
TOAST được **một phần**, thay vì phải bung cả hiện vật ra mới cắt được đoạn cần. Một quyết định
lấy ở P3e vì lý do CPU, nay lại là thứ khiến P3g khả thi.

### Luồng phải **tua được**, không chỉ đọc tuần tự

PIL (`Image.open`) tua tới lui trong header ảnh. Một luồng chỉ-đọc-tiếp sẽ làm hỏng mọi chỗ dùng
ảnh (`quality/gate.py`, bộ trích vùng an toàn, bộ vẽ). Nên `LuongHienVatLuoi` hiện thực
`seek/tell/readinto` đầy đủ, bọc trong `BufferedReader` (khối 256KB) để `.read(n)` nhỏ lẻ của
PIL không thành N lượt đi CSDL.

**Backend `local` không dùng lớp này** — tệp trên đĩa vốn đã lười và tua được.

### Quyết định về hành vi HTTP

| Tình huống | Trả về | Vì sao |
|---|---|---|
| Cú pháp `Range` hỏng | **200** nguyên tệp | RFC 9110 cho bỏ qua header hỏng. Ném lỗi vào mặt người dùng vì một header họ không tự gõ là tệ hơn |
| `Range` đa đoạn (`a-b, c-d`) | **200** nguyên tệp | Hợp lệ nhưng cần `multipart/byteranges`; chưa ai cần |
| Xin quá cuối tệp | **416** + `Content-Range: bytes */<size>` | Client cần biết kích thước thật để hỏi lại |
| `If-Range` **lệch** ETag | **200** nguyên tệp | Hiện vật đã đổi ⇒ nối đoạn của bản cũ vào phần đã tải sẽ tạo một **tệp lai không của ai cả** |
| `If-None-Match` khớp | **304** | Đã có bản mới nhất thì không cần đoạn nào |

Đoạn dài cũng **phát theo khối**, không nằm trọn trong RAM.

## Changed Files

| Tệp | Việc |
|---|---|
| `app/services/storage.py` | `LuongHienVatLuoi`; `read_range` vào Protocol + cả hai backend; `open_read` của postgres thành luồng lười |
| `app/api/v1/routes.py` | `_pha_range`, `_doc_mot_doan`, `Accept-Ranges`/206/416/`If-Range` |
| `tests/test_storage_unit.py` | +8 test hợp đồng (chạy 2 backend) +2 test đo byte thật |
| `tests/test_range_integration.py` | **Mới** — 10 test hành vi HTTP |

## Tests

```
856 passed, 6 skipped      (nền trước P3g: 832)
```

Ruff trên 2 tệp đã sửa: **84 → 83**.

### Hai test đo BYTE THẬT SỰ kéo về

Không có phép đếm này thì "đọc lười" chỉ là một khẳng định trong docstring:

- `test_doc_dau_tep_KHONG_keo_ca_hien_vat_ve` — đọc 100 byte đầu của hiện vật **2MB**, khẳng
  định tổng byte kéo từ CSDL **≤ 512KB** và **≤ 2 lượt**.
- `test_doc_het_tep_thi_chia_thanh_nhieu_luot` — mặt kia của cùng lời hứa: đọc hết 2MB phải là
  **nhiều lượt**, không phải một cú `SELECT data` khổng lồ.

### Một hồi quy do chính tôi tạo, test bắt được

`open_read()` mới gọi `stat()` trước — mà `stat()` **cố ý nuốt** `UnsafeObjectPath` và trả `None`
(nó là một câu hỏi, không phải một lệnh). Hệ quả: path nguy hiểm hiện ra thành "không tìm thấy",
**che mất tín hiệu bảo mật**. Test hợp đồng `test_moi_thao_tac_deu_tu_choi_...` bắt đúng ca này.
Sửa: kiểm path trước khi hỏi `stat()`.

## Live Verification — đã chạy trên host

### `Range` chạy thật

```
Accept-Ranges: bytes
Range: bytes=10-19        -> 206 · Content-Range: bytes 10-19/14319 · Content-Length: 10
Range: bytes=999999999-   -> 416 · Content-Range: bytes */14319
```

Phép đo có ý nghĩa nhất — **tải dở rồi tải tiếp, ghép lại có ra đúng tệp không**:

```
tải 0-6999 + tải 7000-  ->  sha256 fd499c764f2bc034c140b5ad
tải nguyên tệp          ->  sha256 fd499c764f2bc034c140b5ad     KHỚP
ảnh ghép mở được: PNG (1200, 1700)
```

### Độ trễ thật

⚠️ **Phép đo đầu tiên của tôi sai.** Mỗi lượt `curl` bắt tay TLS lại từ đầu, và chi phí đó
(~130–220ms) **át hẳn** phần việc của máy chủ — đến mức hiệu số ra **số âm**. Đo lại bằng một kết
nối dùng lại, bỏ 5 lượt khởi động nguội:

| Mục | p50 | p95 | min |
|---|---|---|---|
| MỐC NỀN `/healthz` (không đọc hiện vật) | 3,4 ms | 4,0 | 3,0 |
| `clean-image` **304** (chỉ `stat`) | 6,8 ms | 13,6 | 6,2 |
| `clean-image` **Range 8KB** | 8,6 ms | 10,1 | 7,5 |
| `clean-image` đầy đủ (14 KB) | 9,6 ms | 14,4 | 8,2 |
| `typeset-preview` đầy đủ (16 KB) | 9,8 ms | 12,0 | 8,1 |

Trừ mốc nền ra:

```
stat() + dựng ETag                ≈ 3,4 ms
đọc + phát nguyên hiện vật        ≈ 6,2 ms
đọc một đoạn 8KB                  ≈ 5,2 ms
```

Nhưng 14 KB **không đại diện** cho một trang truyện thật. Đo lại trên hiện vật **6,76 MB**
(ảnh clean thật do LaMa sinh ra từ một trang 1400×2000 có nhiễu — lớn hơn cả mức trung bình
3,4 MB đo được ở P3b), n=25:

| Mục | p50 | p95 | min |
|---|---|---|---|
| MỐC NỀN `/healthz` | 3,7 ms | 8,3 | 3,3 |
| **304** (chỉ `stat`) | 6,8 ms | 7,4 | 6,3 |
| **Range 8 KB** (đầu tệp) | 8,6 ms | 19,0 | 7,4 |
| **Range 64 KB** (GIỮA tệp, offset 3.000.000) | 9,2 ms | 10,7 | 8,5 |
| Đầy đủ (6.763.787 byte) | 114,7 ms | 151,3 | 99,5 |

```
stat() + ETag                 ≈   3,1 ms
đọc 1 đoạn 8KB (đầu tệp)      ≈   4,8 ms
đọc 1 đoạn 64KB ở GIỮA tệp    ≈   5,5 ms
đọc + phát NGUYÊN hiện vật    ≈ 111,0 ms   (≈ 61 MB/s — giới hạn ở băng thông, không ở CSDL)
```

### Hai điều bảng này chứng minh, mà bảng 14 KB không chứng minh được

**1. `substr()` thật sự chỉ lấy đúng đoạn cần.** Đọc 64 KB ở **giữa** một hiện vật 6,76 MB tốn
**5,5 ms** — gần y hệt đọc 8 KB ở **đầu** (4,8 ms), và bằng **1/20** chi phí đọc nguyên tệp. Nếu
Postgres phải bung cả hiện vật ra rồi mới cắt, đoạn giữa đã phải tốn cỡ 111 ms. Đây là bằng chứng
thực nghiệm cho quyết định `SET STORAGE EXTERNAL` ở P3e — không nén thì giải TOAST được một phần.

**2. `size_bytes` tách cột là đúng.** `stat()` trên hiện vật 6,76 MB tốn **3,1 ms** — bằng đúng
`stat()` trên hiện vật 14 KB. Nếu nó phải chạm cột `data` thì con số này đã phải phình theo kích
thước.

**Kết luận:** CSDL **không phải** chỗ nghẽn. Chi phí đọc là 3–6 ms; phần còn lại của một lượt tải
đầy đủ là băng thông, và đó là thứ `Range` + `304` sinh ra để khỏi phải trả lại nhiều lần.

## Remaining Limits

- Range đa đoạn (`multipart/byteranges`) chưa phục vụ — trả nguyên tệp, vẫn đúng chuẩn.
- Trần `STORAGE_PG_MAX_ARTIFACT_MB` (96 MB) vẫn giữ, nhưng nay nó chỉ còn chặn kích thước **ghi**;
  đường đọc không còn phụ thuộc kích thước hiện vật.
- Đo từ workspace qua internet, không phải từ trong cùng mạng nội bộ với máy chủ — mốc nền
  `/healthz` dùng để trừ phần đó ra, nhưng nó không loại được hết nhiễu.
- Chưa đo dưới **tải đồng thời** — mọi con số trên là một người dùng một lúc.
- Hiện vật đo là **6,76 MB** (lớn hơn mức trung bình thật 3,4 MB), nên các số đọc-đầy-đủ là
  **cận trên**, không phải trung bình.
