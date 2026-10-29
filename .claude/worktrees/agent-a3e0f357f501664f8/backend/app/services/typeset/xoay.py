"""E16 — đổi góc hướng-đường thành góc XOAY CHỮ, và quyết định có xoay hay không.

## Vì sao cần một module riêng chỉ để đổi một con số

`RegionTextOrientation.rotation_degrees` **không phải** góc để xoay chữ. `chuan_hoa_goc` của E15
quy nó về **[0, 180)** và đó là hướng của **cạnh dài** hình chữ nhật — một **đường vô hướng**.
Docstring `la_ngang` nói thẳng: *"Gần 0 hoặc gần 180 đều là nằm ngang — 179° không phải là 'gần như
dựng đứng'"*.

Đo trên dữ liệu thật (lượt 24 trang E23, 11 vùng `rotated_horizontal`):

    25.0 · 66.6 · 126.9 · 149.0 · 158.6 · 160.2 · 162.2 · 165.0 · 165.4 · 166.0 · 166.7

**8 trong 11 nằm trong 149-167°.** Xoay chữ đúng theo những con số đó thì 8 vùng ra chữ **gần như
lộn ngược** — vì 165° và −15° là **cùng một đường**, chỉ đo từ đầu kia.

## Quy ước đã chọn, và điều nó KHÔNG biết

Quy về **(−90, 90]** — cách đọc *gần nằm ngang nhất*. Nhờ vậy chữ **không bao giờ** bị lộn ngược.

Nhưng phải nói rõ giới hạn: `cv2.minAreaRect` trả hình chữ nhật **vô hướng**, nên dữ liệu hiện lưu
**không mang** chiều đọc trên/dưới. Với chữ thật sự đọc ngược (hiếm trong truyện, nhưng có), quy
ước này sẽ xoay sai chiều. Muốn biết chắc thì phải lưu **đa giác dòng chữ có thứ tự** từ OCR —
PaddleOCR có trả, nhưng `RegionTextOrientation` chỉ lưu góc đã chuẩn hoá. Đó là việc của một slice
khác, không phải của E16.

Chiều sai của quy ước này là chiều an toàn: nó **không bao giờ tệ hơn** hiện trạng (không xoay gì).
"""
from __future__ import annotations

#: Dưới ngưỡng này thì coi như chữ đã nằm ngang — xoay vài độ chỉ làm nét chữ bị răng cưa mà mắt
#: không thấy khác.
#:
#: PHẢI khớp `Settings.e15_angle_tolerance_deg` (= 12.0), vì E15 dùng đúng con số đó trong
#: `la_ngang()` để kết luận một vùng là "nằm ngang". Đặt nhỏ hơn thì có cửa sổ mà E15 gọi là NGANG
#: nhưng E16 lại xoay — hai tầng nói hai điều khác nhau về cùng một vùng.
#:
#: (Bản đầu của tôi đặt 8.0. Test chéo lẽ ra bắt được, nhưng nó tra `orientation_horizontal_
#: tolerance_deg` — một tên KHÔNG tồn tại — nên `getattr` trả None và test tự `skip`. Một guard
#: bị skip là một guard không canh gì.)
NGUONG_XOAY_DO = 12.0


def goc_xoay_chu(goc_duong: float) -> float:
    """Đổi hướng-đường [0, 180) thành góc xoay chữ trong (-90, 90].

    >>> goc_xoay_chu(165.0)
    -15.0
    >>> goc_xoay_chu(25.0)
    25.0
    >>> goc_xoay_chu(90.0)
    90.0
    """
    g = float(goc_duong) % 180.0
    return g - 180.0 if g > 90.0 else g


def nen_xoay(goc_duong: float | None, *, nguong_do: float = NGUONG_XOAY_DO) -> bool:
    """Có đáng xoay không. `None` (chưa đo được góc) ⇒ KHÔNG xoay.

    Thiếu góc thì giữ nguyên hành vi cũ, chứ không đoán một góc rồi xoay theo — đoán ở đây là
    làm ảnh xấu đi ở chỗ không ai kiểm được.
    """
    if goc_duong is None:
        return False
    return abs(goc_xoay_chu(goc_duong)) > float(nguong_do)


def goc_pil(goc_duong: float) -> float:
    """Góc truyền cho `PIL.Image.rotate()` để chữ nghiêng ĐÚNG HƯỚNG với ảnh.

    **Dấu ngược với `goc_xoay_chu`** — và đây là số ĐO, không phải suy luận. Dựng dải chữ ngang,
    xoay ảnh một góc biết trước bằng `cv2.getRotationMatrix2D` (dương = ngược chiều kim đồng hồ),
    rồi cho chính `chuan_hoa_goc` đo lại:

        ảnh xoay +15°  ->  chuan_hoa_goc 165.0°  ->  goc_xoay_chu -15.0°
        ảnh xoay -15°  ->  chuan_hoa_goc  15.0°  ->  goc_xoay_chu +15.0°
        ảnh xoay +40°  ->  chuan_hoa_goc 140.0°  ->  goc_xoay_chu -40.0°
        ảnh xoay -40°  ->  chuan_hoa_goc  40.0°  ->  goc_xoay_chu +40.0°

    `PIL.Image.rotate(dương)` cũng quay ngược chiều kim đồng hồ, cùng quy ước với cv2. Nên để dựng
    lại đúng độ nghiêng mà analyzer đã thấy thì phải đảo dấu.

    Đoán dấu ở đây sẽ cho chữ nghiêng **sai hướng** — sai không kém gì lộn ngược, mà lại khó thấy
    hơn vì ảnh vẫn "trông có xoay".
    """
    return -goc_xoay_chu(goc_duong)
