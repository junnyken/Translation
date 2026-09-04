# Báo cáo Mini-Spec A1 — Cổng khoá truy cập (auth slice A)

**Ngày:** 2026-09-04 · **Trạng thái:** ✅ **XONG — chưa bật trên host** (xem §Triển khai)

## Summary

Đo trên bản chạy thật trước khi làm: **65 thao tác API, 100% không cần xác thực, 31 trong đó
ghi/xoá.** Ai có URL là tạo, sửa, xoá được mọi chapter của mọi người.

A1 đặt **một khoá chung cho cả hệ thống** trước toàn bộ `/api/v1`.

## Đây là gì và KHÔNG phải gì

**Là:** một bức tường chặn người lạ.
**Không phải:** hệ thống tài khoản.

Nó **không** phân biệt ai làm gì, **không** giới hạn ai xem chapter của ai, và **không** chống
được người đã có khoá. Ai cầm khoá là làm được mọi thứ, kể cả xoá sạch.

Viết rõ vậy để không ai nhìn thấy chữ "auth" rồi tưởng đã có phân quyền. Phân quyền thật là
**slice B** (tài khoản riêng, chapter có chủ).

## Design Choice

### Gắn ở tầng ROUTER, không gắn từng endpoint

62 đường dẫn thì kiểu gì cũng quên một cái — và cái bị quên sẽ là cái không ai ngờ tới. Gắn một
lần vào `include_router(...)`, và có **test quét toàn bộ route** khẳng định không sót:

```python
def test_moi_endpoint_v1_deu_co_cong(self):   # + test khẳng định danh sách route KHÔNG rỗng
```

Test thứ hai quan trọng ngang test thứ nhất: một test "không có gì thiếu" chạy trên danh sách
rỗng thì luôn xanh và chẳng chứng minh gì.

### So sánh theo thời gian hằng định

`hmac.compare_digest`, không phải `==`. So bằng `==` dừng ở byte đầu khác nhau, và chênh lệch
thời gian đó đủ để dò ra khoá **từng ký tự một**.

### "Thiếu khoá" và "khoá sai" trả lời Y HỆT nhau

Nói ra sự khác biệt là xác nhận cho người dò biết họ đã đoán đúng định dạng. Có test khẳng định
hai trường hợp cho ra cùng mã lỗi **và cùng nội dung**.

### Mặc định TẮT — và tắt thì phải kêu to

`api_access_key` rỗng ⇒ cổng mở. Có chủ đích, vì máy phát triển và bộ test không phải mang khoá
đi khắp nơi, **và** vì thứ tự triển khai an toàn (xem dưới). Nhưng tắt im lặng là cái bẫy, nên
lúc khởi động có cảnh báo:

```
CỔNG KHOÁ ĐANG TẮT — mọi thao tác API, kể cả xoá, đều không cần xác thực.
```

### Giao diện: bọc `fetch` MỘT chỗ

Mọi lời gọi API nằm trong `api.js`. Định nghĩa một hàm cục bộ tên `fetch` che hàm toàn cục trong
phạm vi module ⇒ **~40 chỗ gọi tự động mang khoá, không phải sửa một dòng nào**. Sửa 40 chỗ là
chắc chắn quên một chỗ, và chỗ quên đó sẽ hỏng đúng lúc đang cần.

### Chỉ hỏi khoá KHI máy chủ đòi

Ô nhập khoá chỉ hiện khi gặp 401. Máy chủ chưa bật khoá thì người dùng không bao giờ thấy nó —
bắt người ta nhập khoá cho một hệ thống không đòi khoá là bắt họ làm một việc vô nghĩa.

Và **thử một lời gọi thật trước khi báo thành công**: lưu rồi nói "xong" mà khoá sai thì người
dùng chỉ gặp lại đúng màn này ở thao tác kế tiếp, không hiểu vì sao.

## Changed Files

| Tệp | Việc |
|---|---|
| `app/core/bao_ve.py` | **Mới** — `cong_khoa` + cảnh báo khởi động |
| `app/core/config.py` | `api_access_key: str = ""` |
| `app/main.py` | Gắn cổng ở router · thêm `X-API-Key` vào CORS `allow_headers` |
| `frontend/src/api.js` | Bọc `fetch`, lưu/đọc/xoá khoá, `laLoiThieuKhoa`, `kiemKhoa` |
| `frontend/src/App.jsx` | `HopNhapKhoa` — hiện khi 401 |
| `tests/test_bao_ve_integration.py` | **Mới** — 11 test |
| `frontend/src/components/khoa-truy-cap.test.jsx` | **Mới** — 7 test |

`X-API-Key` **phải** có trong CORS `allow_headers`, nếu không trình duyệt chặn ngay ở preflight
và giao diện không bao giờ gửi được khoá đi.

## ⚠️ Triển khai — ĐÚNG THỨ TỰ, nếu không sẽ tự khoá mình ra ngoài

```
1. Đẩy mã + deploy API   (cổng vẫn TẮT — api_access_key rỗng)
2. Deploy giao diện       (đã biết gửi X-API-Key)
3. RỒI MỚI đặt API_ACCESS_KEY trên host + redeploy
```

Đảo bước 3 lên trước bước 2 là giao diện cũ không gửi khoá ⇒ **toàn bộ hệ thống trả 401 cho
chính chủ**. Đường thoát vẫn có (xoá biến môi trường rồi redeploy) nhưng mất vài phút chết.

Khoá nên dài và ngẫu nhiên (≥32 ký tự). Đặt bằng công cụ của nền tảng, **không** commit vào repo.

## Tests

```
frontend: 258 passed   (nền: 251)
backend : xem TEST_LOG
```

Bốn test đáng kể nhất **không** kiểm việc chặn, mà kiểm việc **chặn cho đúng chỗ**:

| Test | Vì sao |
|---|---|
| `test_moi_endpoint_v1_deu_co_cong` | quét toàn bộ route — gắn ở router là để không sót, test chứng minh điều đó |
| `test_co_dang_kiem_that_chu_khong_phai_danh_sach_rong` | chống chính test trên tự lừa mình |
| `test_thieu_khoa_va_khoa_sai_bao_Y_HET_nhau` | không rò rỉ tín hiệu cho người dò |
| `TestDuongSONG_phai_mo` | `/` và `/healthz` phải mở — khoá chúng lại là tự làm hỏng deploy |

## Remaining Limits

- **Không phải phân quyền.** Một khoá cho tất cả; không biết ai làm gì; không giới hạn ai xem gì.
- **Khoá nằm ở `localStorage`** — không có phiên đăng nhập, không hết hạn, không thu hồi từng
  người. Đổi khoá là đổi cho tất cả.
- **Chưa bật trên host.** Bật là việc của bước 3 ở trên.
- **Không chống được chính người có khoá** làm sai — kể cả xoá.
- `/openapi.json` và `/docs` vẫn mở: chúng lộ *hình dạng* API chứ không lộ dữ liệu. Cân nhắc đóng
  ở slice B.
