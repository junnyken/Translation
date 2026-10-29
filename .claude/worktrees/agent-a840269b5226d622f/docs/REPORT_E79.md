# REPORT E79 — Xoá chữ theo NÉT CHỮ (mặt nạ `seg` của comic-text-detector)

**Ngày:** 2026-10-15 · **Nguồn:** tham khảo Koharu, mục 1. Model CTD của dự án trả về mặt nạ điểm ảnh của
chữ, nhưng trước giờ bị bỏ phí.

## Summary

CTD trả ba đầu ra: `blk` (khung), **`seg` [1,1,1024,1024]** (mặt nạ điểm ảnh của chữ) và `det`. Trước E79
chỉ dùng `blk`, nên LaMa xoá cả hình chữ nhật nới 8%, ăn vào nét vẽ quanh chữ.

Nay khi nhận diện, `seg` được đưa về cỡ ảnh gốc và lưu cạnh ảnh trang (`<trang>_mat_na_chu.png`). Khi xoá
chữ, vùng xoá = khung đã nới ∩ (mặt nạ nét, nở + bịt lỗ).

**Production đang nhận diện bằng Gemini nên không có mặt nạ, hành vi không đổi.** E79 có tác dụng khi
`DETECT_ENGINE=ctd`, tức bản cài cục bộ hoặc chế độ miễn phí. Tắt bằng `INPAINT_THEO_NET_CHU=false`.

## Design Choice

- Mặt nạ lưu theo đường suy ra từ ảnh trang, không thêm cột DB. Nhận diện lại bằng engine không có mặt
  nạ thì **xoá mặt nạ cũ**: không xoá thì bước xoá chữ sẽ dùng nét chữ của một bộ khung khác.
- Chỉ xoá **trong** khung đã nới, nên vùng E12 bỏ qua vẫn không bị đụng. Khung mà `seg` gần như không
  thấy chữ (dưới 3% diện tích khung) thì lùi về xoá cả khung: thà rộng còn hơn sót chữ.
- Bán kính nở = Koharu × **2** (`INPAINT_NET_CHU_HE_SO_NO`), xem phần đo dưới.
- Mã cần cv2 nằm ở `inpaint/mat_na_net.py`; `lama.py` vẫn không import cv2 (chốt của `test_no_ai_logic`).

## Live Verification — LaMa thật, trang thật

| Hệ số nở | Diện tích xoá so với cả khung (E13P02) | Chữ tiếng động trắng viền đen dày đè tranh |
|---|---|---|
| ×1 (đúng Koharu) | 68% | **Sót mảnh viền đen** — tệ hơn xoá cả khung |
| **×2 (chọn)** | **82%** | Gần như sạch, giữ được tranh hơn |
| ×3 | 91% | Sạch nhưng nhoè gần như xoá cả khung |

Với ×2, diện tích xoá trên 3 trang là 88%, 84% và 82% so với cả khung. Chữ trên nền phẳng ("WoooOoh")
sạch như cách cũ và giữ nhiều chi tiết nền hơn. LaMa chạy nhanh hơn: 24 giây so với 39 giây.

Mảnh "kf!" của "Klukf!" còn sót ở **mọi** cách, kể cả cách cũ. Nguyên nhân là khung nhận diện cắt lệch,
không phải mặt nạ.

## Tests

`test_e79_xoa_theo_net.py`, 7 test:
- đổi toạ độ letterbox về ảnh gốc
- chỉ xoá nét trong khung, giữ tranh, không đụng ngoài khung
- khung `seg` trống ⇒ xoá cả khung
- LaMa chỉ thay điểm ảnh trên nét
- mặt nạ sai cỡ ⇒ lùi về khung
- lưu/đọc/xoá mặt nạ trong worker
- tắt cờ

**Đối chứng âm:** tắt nhánh E79 trong LaMa ⇒ đỏ.

## Remaining Limits

1. Không áp dụng cho production hiện tại (Gemini không trả mặt nạ).
2. Hệ số ×2 chỉ đo trên 1 trang nhiều chữ tiếng động. Trang khác có thể cần chỉnh.
3. Cọ xoá chữ (E76) vẫn xoá đúng vùng tô, không dùng mặt nạ này.
