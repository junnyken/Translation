# REPORT B1c — Ảnh trang và file xuất trả 401 từ khi bật đăng nhập

*2026-09-04 · lỗi hồi quy của Auth slice B, tìm ra bằng cách mở trình duyệt thật*

## Summary

Từ khi slice B gắn cổng đăng nhập ở tầng router, **hai đường ra chính của ứng dụng cùng chết**:

| Đường | Hậu quả |
|---|---|
| `GET /pages/{id}/typeset-preview` | Màn sửa tay **trắng trơn** — không nhìn được trang, không kéo được khung, không rà soát được vùng nào |
| `GET /export-jobs/{id}/download` | Nút "Tải file về" bấm vào **không ra gì** |

Nguyên nhân không nằm ở máy chủ: `<img src>` và `<a href>` do **trình duyệt** tự tải, và không có
cách nào gắn header `Authorization` vào chúng. Mã phiên nằm trong `localStorage` và chỉ được gắn
bởi hàm `fetch` bọc trong `api.js` — hai thẻ HTML kia không đi qua đó.

Đo trên bản chạy 04/09:

```
GET /pages/{id}/typeset-preview                  → 401 · application/json
GET /pages/{id}/typeset-preview  (kèm mã phiên)  → 200 · image/png · 2.154.188 bytes
GET /export-jobs/{id}/download                   → 401
GET /export-jobs/{id}/download   (kèm mã phiên)  → 200 · 2.153.406 bytes
```

## Audit Before Build

**Vì sao 304 test giao diện không bắt được.** Không test nào tải một tài nguyên **thật**: ảnh
được mock, nút tải chỉ được kiểm là "có thẻ `<a>` với đúng href". Href đúng — và vẫn 401.

Đây là loại lỗi chỉ lộ ra khi **mở trình duyệt vào bản đang chạy**. Nó cũng giải thích vì sao lỗi
sống sót qua cả một mini-spec: người viết slice B kiểm bằng `curl` (curl thì gắn header được) và
bằng test (test thì mock).

**Phạm vi quét:** tìm mọi chỗ dựng URL của máy chủ để trình duyệt tự tải — đúng hai chỗ
(`App.jsx` cho ảnh preview, `ExportPanel.jsx` cho link tải). Không còn chỗ thứ ba.

## Design Choice

### Vì sao KHÔNG nhét mã phiên vào query string

Cách nhanh nhất là `?ma_phien=…`. Không làm, vì URL nằm lại ở **lịch sử duyệt web**, **log máy
chủ**, và header **`Referer`** khi trang gọi ra ngoài. Mã phiên sống 14 ngày, nên đó là biến một
thứ bí mật thành một thứ đọc trộm được ở ba nơi.

### Vì sao không mở cổng cho hai endpoint đó

Ảnh trang **là** nội dung của người dùng — ai mở được ảnh thì đọc được cả chapter. Mở cổng để
tiện hiển thị là xoá đúng thứ slice B vừa dựng lên.

### Cách đã chọn: tự tải bằng `fetch` rồi dựng `blob:` URL

Trình duyệt không gắn được header, nhưng mã của ta thì gắn được. Tải về bằng `fetch` (đi qua đúng
hàm bọc đã có mã phiên), rồi giao cho trình duyệt một `blob:` URL — thứ nó hiển thị/tải được mà
không cần biết gì về xác thực.

Giá phải trả: ảnh nằm trong bộ nhớ tab (2MB/ảnh), nên **phải thu hồi** bằng `URL.revokeObjectURL`
khi đổi trang — không thì xem 30 trang là 60MB nằm lại.

Với file tải về: đọc tên file từ `Content-Disposition` của máy chủ chứ không tự đặt tên cho đẹp —
đặt tên khác tên thật là làm người dùng mất dấu file của chính họ.

## Changed Files

| File | Đổi gì |
|---|---|
| `frontend/src/api.js` | `taiVeBlobUrl()` + `taiFileXuatVe()` |
| `frontend/src/App.jsx` | Ảnh preview nạp qua blob, thu hồi khi đổi trang; phân biệt **"đang tải"** với **"chưa có ảnh"** |
| `frontend/src/components/ExportPanel.jsx` | Link tải → nút gọi `taiFileXuatVe`; thêm cảnh báo bong bóng trống (lỗi F1 bỏ sót) |
| `frontend/src/components/anh-va-file-co-khoa.test.jsx` | 6 test mới |

## Tests

| Test | Khẳng định |
|---|---|
| `gửi mã phiên khi tải ảnh, và trả blob URL` | header `Authorization: Bearer …` có mặt trong lời gọi |
| `máy chủ từ chối thì NÓI RA, không trả blob rỗng` | 401 phải ném lỗi, không trả một ảnh trắng |
| `lấy tên file từ Content-Disposition của máy chủ` | không tự đặt tên đè lên tên thật |
| `KHÔNG được nói "không có cảnh báo nào" khi có bong bóng trống` | lỗi F1 bỏ sót |
| `sạch thật thì mới được nói là sạch` | chống sửa quá tay thành cảnh báo lải nhải |
| `nút tải file gọi đường CÓ mã phiên` | không quay lại thẻ `<a href>` trần |

Frontend: **304 passed** (nền 298).

## Live Verification

Chromium thật (Playwright), tài khoản thật, bản chạy thật — sau khi deploy `translation-web`:

- **Ảnh trang hiện ra**: trang truyện Pepper&Carrot, bong bóng 1 có chữ Việt
  `CẬU ỔN CHỨ? TỚ VỀ ĐÂY.`, bong bóng 2 vẽ khung đỏ gạch chéo (vùng font không vẽ được).
  Lớp CSS đọc từ DOM: `['khung dang-chon', 'khung thieu-font']`.
- **Tải file**: bấm "Xuất chapter" → tick xác nhận bản quyền → bấm "Tải file về" ⇒ trình duyệt
  nhận file thật:

  ```
  TÊN FILE máy chủ đặt: chapter-f553ee0a-a234-4583-bbaa-6c711ea0fc0b.cbz
  KÍCH THƯỚC thật:      2.153.406 bytes
  CBZ hợp lệ:           True · nội dung: ['001.png']
  ```
- Console trình duyệt: **không lỗi nào**.

## Remaining Limits

1. **Ảnh nằm trọn trong bộ nhớ trước khi hiện.** Với trang 2MB thì không sao; chapter ảnh rất
   lớn sẽ thấy khựng một nhịp so với `<img>` tải dần. Đổi lại thì phải có URL ký hạn ngắn ở máy
   chủ — việc của mini-spec khác.
2. **Không có bộ nhớ đệm của trình duyệt cho ảnh nữa.** Mỗi lần mở lại trang là tải lại; trước
   đây `<img>` còn dùng được cache. Chưa đo ảnh hưởng thật.
3. **Tiện ích Chrome (E1)**: đã grep mã nguồn (`extension/src`) — không nhúng ảnh hay đường tải
   nào của máy chủ, nên không dính lỗi này. Chưa mở tiện ích ra bấm thử.
