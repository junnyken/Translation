"""Tìm LÒNG bong bóng bằng cách tô loang từ tâm vùng chữ (A2).

## Vì sao không dùng lại bộ dò hình của E14

E14 tìm bong bóng bằng **độ sáng**: lọc điểm sáng trong HSV, rồi lấy contour nhỏ nhất bao quanh
tâm vùng chữ. Cách đó chưa **một lần nào** thành công trên dữ liệu thật — đo được `shape_derived`
= 0/8, 0/12, 0/2 trên ba trang khác nhau, tổng 22 vùng, 0 lần.

Nguyên nhân đo được, không phải suy đoán:

```
tỉ lệ điểm vượt ngưỡng sáng của E14 : 96,7% toàn trang
trần cho phép (max_roi_coverage)    : 75%
```

Manga đen trắng là **bong bóng trắng nằm trên trang trắng**. Lọc theo độ sáng thì bong bóng và
trang là *cùng một khối*, nên ứng viên bao quanh tâm chính là cả trang và bị loại vì `FILLS_ROI`.
Đây là **sai công cụ, không phải sai tham số**: không có ngưỡng sáng nào tách được trắng khỏi
trắng.

## Cách của A2

Bong bóng không khác trang ở độ sáng, nhưng **có viền mực bao quanh**. Vậy:

> lòng bong bóng = vùng **không-mực nối liền** chứa tâm vùng chữ.

Tô loang từ tâm trên mặt nạ không-mực. Nó tự dừng ở viền bong bóng kể cả khi hai bên viền đều
trắng — đúng nguyên lý A1 (`grow.py`) đã dùng thành công để nới khung.

Đo trên ảnh có bong bóng biết trước kích thước:

| Bong bóng thật | Tô loang trả về |
|---|---|
| 380×240 tại (90,90) | 373×233 tại (94,94) |
| 240×180 tại (520,120) | 233×173 tại (524,124) |

Sai lệch đúng bằng bề dày nét viền.

## Chữ nằm trên nền vẽ thì sao

Không có viền nào chặn ⇒ tô loang **rò ra cả trang**. Đo trên 3 ảnh trong `test_fixtures/`: tâm
trong bong bóng cho 4,4–5,8% diện tích trang, tâm trên nền vẽ cho 75–82%. Hai nhóm cách nhau
hơn một bậc độ lớn, nên một trần diện tích tách được — và ca rò thì rơi về khung dự phòng như cũ.

**Hàm này KHÔNG tự quyết định.** Nó trả về hình chữ nhật và diện tích kèm lý do; việc nhận hay
loại là của bên gọi.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.safearea.decision import ReasonCode

#: Bán kính (px) dò tâm thay thế khi tâm rơi trúng mực. Đủ để nhảy qua một nét chữ còn sót sau
#: khi xoá chữ, không đủ để nhảy sang bong bóng bên cạnh.
BAN_KINH_DOI_TAM = 12


@dataclass(frozen=True)
class KetQuaLoang:
    """`rect` theo hệ toạ độ của chính mặt nạ truyền vào, KHÔNG phải toạ độ ảnh gốc."""

    rect: tuple[int, int, int, int]
    so_diem: int
    tam_da_dung: tuple[int, int]
    #: Tâm ban đầu rơi trúng mực và đã phải dời — bên gọi nên coi kết quả kém chắc chắn hơn.
    da_doi_tam: bool


def _tam_thay_the(mat_na_trong, cx: int, cy: int, ban_kinh: int):
    """Dò xoáy trôn ốc quanh tâm tìm điểm không-mực gần nhất.

    Tâm bbox chữ **rất hay** rơi trúng mực: nó nằm giữa khối chữ, mà bước xoá chữ luôn để sót nét
    (đo 04/09: `còn chữ ở 8/8 vùng`). Không dời tâm thì A2 hỏng đúng ở những vùng nó cần chạy nhất.

    Đi theo bán kính tăng dần nên luôn lấy điểm gần tâm nhất, và duyệt theo thứ tự cố định nên
    kết quả **tất định** — cùng ảnh cho cùng kết quả ở mọi máy.
    """
    h, w = mat_na_trong.shape[:2]
    for r in range(1, ban_kinh + 1):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if max(abs(dx), abs(dy)) != r:
                    continue  # chỉ duyệt viền của ô vuông bán kính r
                x, y = cx + dx, cy + dy
                if 0 <= x < w and 0 <= y < h and mat_na_trong[y, x]:
                    return x, y
    return None


def long_bong_bong(mat_na_trong, tam: tuple[int, int], *, ban_kinh_doi_tam: int = BAN_KINH_DOI_TAM):
    """Tô loang từ `tam` trên `mat_na_trong` (True = không mực).

    Trả `(KetQuaLoang, [])` khi tô được, hoặc `(None, [mã lý do])` khi không.
    """
    import cv2
    import numpy as np

    h, w = mat_na_trong.shape[:2]
    cx, cy = int(tam[0]), int(tam[1])
    if not (0 <= cx < w and 0 <= cy < h):
        return None, [ReasonCode.SHAPE_INVALID_GEOMETRY]

    da_doi = False
    if not mat_na_trong[cy, cx]:
        moi = _tam_thay_the(mat_na_trong, cx, cy, ban_kinh_doi_tam)
        if moi is None:
            # Quanh tâm toàn mực trong cả bán kính dò — không có lòng nào để tô.
            return None, [ReasonCode.SHAPE_EROSION_ELIMINATED_AREA]
        cx, cy = moi
        da_doi = True

    anh = (np.asarray(mat_na_trong, dtype=bool)).astype(np.uint8) * 255
    mask = np.zeros((h + 2, w + 2), np.uint8)
    so_diem, _, _, rect = cv2.floodFill(
        anh, mask, (cx, cy), 128, 0, 0, cv2.FLOODFILL_FIXED_RANGE
    )
    if so_diem <= 0:
        return None, [ReasonCode.SHAPE_EROSION_ELIMINATED_AREA]
    return KetQuaLoang(rect=tuple(int(v) for v in rect), so_diem=int(so_diem),
                       tam_da_dung=(cx, cy), da_doi_tam=da_doi), []


def du_tin_lam_bong_bong(
    kq: KetQuaLoang,
    *,
    dien_tich_roi: int,
    bbox_wh: tuple[float, float],
    tran_ti_le_roi: float,
    tran_boi_bbox: float,
) -> list[str]:
    """Trả danh sách lý do LOẠI; rỗng nghĩa là nhận.

    Hai trần, và cần cả hai:

    - **theo ROI**: chữ nằm trên nền vẽ thì tô loang rò ra cả trang (đo được 75–82% diện tích).
    - **theo bbox chữ**: bong bóng lớn bất thường so với khối chữ trong nó thường là đã rò sang
      panel hoặc sang bong bóng bên cạnh, dù tính theo ROI vẫn chưa chạm trần.
    """
    ly_do: list[str] = []
    if dien_tich_roi > 0 and kq.so_diem > tran_ti_le_roi * dien_tich_roi:
        ly_do.append(ReasonCode.SHAPE_CANDIDATE_FILLS_ROI)
    dt_bbox = max(bbox_wh[0] * bbox_wh[1], 1.0)
    if kq.so_diem > tran_boi_bbox * dt_bbox:
        ly_do.append(ReasonCode.SHAPE_CANDIDATE_FILLS_ROI)
    return ly_do
