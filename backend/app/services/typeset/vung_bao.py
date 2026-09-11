"""E26-B — tìm vùng "bao" chứa hẳn nhiều vùng khác, để KHÔNG chèn chữ lên nó.

## Vì sao

Đo thật trên trang `en_E12P01` (Pepper&Carrot, 2026-09-11): bộ nhận diện cho **14 vùng**, trong đó
một vùng `400,41 285x228` **chứa hẳn** hai vùng nhỏ khác và lặp lại nội dung của chúng:

    #2  400,41 285x228   'Luughing Fotlons / Mega-Hairgrowth Potions / Stink-bubble...'
    #4  421,159 250x72   '"Bright-Side" Potions / Smoke Potions..'      <- nằm TRỌN trong #2
    #5  452,211 215x29   'Smoke Potions...'                            <- nằm TRỌN trong #2

Chèn chữ cho cả bốn ⇒ cùng một câu bị vẽ **hai lần chồng lên nhau**. Và chính vùng bao đọc sai
nhiều nhất (`Luughing Fotlons`) vì nó gộp năm nhãn vào một khối.

## KHÔNG xoá, chỉ không vẽ

`mark_overlap_suspects` của M2 ghi rõ *"Chỉ GẮN CỜ, không merge/xóa box nào"*, và E12 ghi
*"máy không được kết luận một vùng là rác rồi tự bỏ — nó chỉ được nói 'có thể là', rồi đẩy cho
người xem"*. Module này giữ đúng nguyên tắc đó: dòng dữ liệu, kết quả OCR, cờ rà soát đều **còn
nguyên**; chỉ bước **vẽ** bỏ qua vùng bao.

## Vì sao đòi CHỨA ÍT NHẤT 2 vùng

Nếu chỉ dựa vào `overlap_suspect` thì sẽ bỏ oan một bong bóng lớn hợp lệ chỉ vì nó chồng nhẹ lên
một vùng khác. "Chứa trọn ≥2 vùng khác" mới là dấu hiệu của một khối gộp: một bong bóng thật không
chứa trọn hai bong bóng khác.
"""
from __future__ import annotations

from app.services.interfaces import BBox

#: Bao nhiêu phần diện tích vùng nhỏ phải nằm trong vùng lớn thì coi là "chứa trọn".
#: Không đòi 1.0 tuyệt đối vì box của bộ nhận diện lệch nhau vài pixel là chuyện thường.
TI_LE_CHUA_TRON = 0.9

#: Chứa ÍT NHẤT bao nhiêu vùng khác thì mới coi là vùng bao.
SO_VUNG_CON_TOI_THIEU = 2


def _ti_le_nam_trong(nho: BBox, lon: BBox) -> float:
    """Phần diện tích `nho` nằm trong `lon`, tính theo diện tích của `nho`."""
    dt = nho.w * nho.h
    if dt <= 0:
        return 0.0
    x0 = max(nho.x, lon.x)
    y0 = max(nho.y, lon.y)
    x1 = min(nho.x + nho.w, lon.x + lon.w)
    y1 = min(nho.y + nho.h, lon.y + lon.h)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return ((x1 - x0) * (y1 - y0)) / dt


def tim_vung_bao(
    boxes: dict,
    *,
    ti_le: float = TI_LE_CHUA_TRON,
    toi_thieu: int = SO_VUNG_CON_TOI_THIEU,
) -> set:
    """Trả tập id các vùng BAO (chứa trọn >= `toi_thieu` vùng khác **nhỏ hơn hẳn**).

    `boxes`: {region_id: BBox}.

    Chỉ tính vùng con có diện tích **nhỏ hơn** vùng bao — nếu không, hai box gần trùng nhau sẽ
    coi nhau là con của nhau và cả hai cùng bị bỏ, làm mất chữ.
    """
    ket: set = set()
    for id_lon, lon in boxes.items():
        dt_lon = lon.w * lon.h
        if dt_lon <= 0:
            continue
        so_con = 0
        for id_nho, nho in boxes.items():
            if id_nho == id_lon:
                continue
            if nho.w * nho.h >= dt_lon:
                continue
            if _ti_le_nam_trong(nho, lon) >= ti_le:
                so_con += 1
        if so_con >= toi_thieu:
            ket.add(id_lon)
    return ket
