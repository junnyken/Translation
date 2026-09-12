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

import re

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


# ---------------------------------------------------------------------------
# E26-B2 — vùng LỚN lặp lại nguyên văn chữ của vùng NHỎ mà nó chồng lên
# ---------------------------------------------------------------------------
#
# `tim_vung_bao` ở trên chỉ nhìn HÌNH HỌC, nên bỏ sót đúng ca mà ảnh thật lộ ra (REPORT_E26 §7b):
#
#     e8e30ad4 '"Bright-Side" Potions / Smoke Potions..'   chứa 6aaf8a55 'Smoke Potions...'
#     nhưng chỉ chồng 69% (< 0.9) và chỉ có 1 vùng con (< 2)  ->  KHÔNG bắt được
#
# Không nới ngưỡng hình học được: hạ 0.9 hay hạ "tối thiểu 2" là bắt đầu **bỏ oan bong bóng thật**
# (xem `test_chua_TRON_mot_vung_thoi_cung_KHONG_du`). Cần một dấu hiệu KHÁC, và dấu hiệu đó là
# **nội dung**: nếu chữ của vùng nhỏ nằm nguyên trong chữ của vùng lớn thì vùng lớn đang lặp lại nó.
#
# ## Đo trước khi tin — 34 trang, 220 vùng, 8 cặp, 0 báo oan
#
#     0d47b661  e8e30ad4 lặp 6aaf8a55        (ca trong ảnh)
#     0d47b661  b8b24333 lặp 3 vùng          (đã bắt sẵn bằng hình học)
#     cc1fffc9  9b1850ee lặp 29ccbe1f
#     cc1fffc9  6787e037 lặp 73bce606        chữ Y HỆT nhau
#     6f0e8e0c  f483f70d lặp 79b0a30b        chữ Y HỆT nhau
#     29ab3d86  65ea2827 lặp 0b346c76
#
# ## Vì sao dùng chữ GỐC, không dùng bản dịch
#
# Bản dịch của cùng một câu ở hai vùng có thể khác nhau: đo thật, `Smoke Potions..` ra
# *"Độc dược khói.."* ở vùng lớn và *"Thuốc khói..."* ở vùng nhỏ. Chuẩn hoá xong vẫn không lồng
# nhau ⇒ dùng bản dịch là **mất tín hiệu**. Chữ gốc thì ổn định.

#: Phần diện tích vùng NHỎ nằm trong vùng LỚN. Thấp hơn `TI_LE_CHUA_TRON` vì ở đây đã có thêm
#: bằng chứng NỘI DUNG, không phải chỉ dựa vào hình học.
TI_LE_CHONG_TOI_THIEU = 0.5

#: Chữ ngắn hơn thì lồng nhau là ngẫu nhiên, không phải lặp (vd "us" nằm trong "just").
DO_DAI_TOI_THIEU = 6

#: Ngưỡng RIÊNG cho chữ Nhật/Trung. Một ký tự CJK chở lượng thông tin gấp nhiều lần một chữ cái
#: Latin: `超毛生え薬` (5 ký tự) là cả một danh từ ghép, còn 5 chữ cái Latin mới là "just" hay "nice".
#: Dùng chung ngưỡng 6 thì luật này gần như **không bao giờ chạy trên truyện Nhật** — đúng loại
#: truyện người dùng đang dịch. Phát hiện lúc viết test, không phải lúc thiết kế.
#:
#: ⚠️ Con số 3 là SUY RA từ mật độ thông tin, **chưa đo trên dữ liệu Nhật thật** (CSDL chưa có
#: project tiếng Nhật nào). Ba ràng buộc còn lại — chồng >= 50%, diện tích nhỏ hơn hẳn, chữ lồng
#: nguyên văn — mới là phần chịu lực chính.
DO_DAI_TOI_THIEU_CJK = 3

_CHI_GIU_CHU = re.compile(r"[^0-9a-z぀-ヿ一-鿿]+")
_LA_CJK = re.compile(r"[぀-ヿ一-鿿]")


def _nguong_do_dai(chu: str, mac_dinh: int, cjk: int) -> int:
    """Ngưỡng độ dài theo hệ chữ: quá nửa là ký tự CJK thì dùng ngưỡng CJK."""
    if not chu:
        return mac_dinh
    return cjk if len(_LA_CJK.findall(chu)) * 2 >= len(chu) else mac_dinh


def _chuan_hoa(s: str) -> str:
    """Bỏ dấu câu, khoảng trắng, xuống dòng — chỉ giữ chữ và số, hạ về chữ thường.

    Cần vì cùng một câu ở hai vùng hay khác nhau đúng phần đuôi: `Smoke Potions..` vs
    `Smoke Potions...`. So nguyên văn là trượt hết.
    """
    return _CHI_GIU_CHU.sub("", (s or "").lower())


def tim_vung_lap_noi_dung(
    boxes: dict,
    texts: dict,
    *,
    ti_le: float = TI_LE_CHONG_TOI_THIEU,
    do_dai_toi_thieu: int = DO_DAI_TOI_THIEU,
    do_dai_toi_thieu_cjk: int = DO_DAI_TOI_THIEU_CJK,
) -> set:
    """Trả tập id vùng LỚN đang lặp lại chữ của một vùng NHỎ hơn mà nó chồng lên.

    `boxes`: {region_id: BBox} · `texts`: {region_id: chữ GỐC (OCR)}.

    **Bất biến quan trọng — không bao giờ mất hết chữ.** Chỉ bỏ vùng có diện tích **lớn hơn hẳn**
    vùng bị lặp. Quan hệ "bỏ" vì thế luôn đi từ diện tích lớn xuống nhỏ, nên vùng nhỏ nhất trong
    mọi chuỗi **không bao giờ bị bỏ** — luôn còn ít nhất một bản của câu đó. Hai vùng bằng diện
    tích cũng không thể loại nhau. Có test riêng cho bất biến này.
    """
    chuan = {rid: _chuan_hoa(t) for rid, t in texts.items()}
    ket: set = set()
    for id_lon, lon in boxes.items():
        c_lon = chuan.get(id_lon, "")
        if not c_lon:
            continue
        dt_lon = lon.w * lon.h
        for id_nho, nho in boxes.items():
            if id_nho == id_lon:
                continue
            c_nho = chuan.get(id_nho, "")
            nguong = _nguong_do_dai(c_nho, do_dai_toi_thieu, do_dai_toi_thieu_cjk)
            if len(c_nho) < nguong or len(c_nho) > len(c_lon):
                continue
            if nho.w * nho.h >= dt_lon:      # phải NHỎ HƠN HẲN — giữ bất biến ở docstring
                continue
            if c_nho not in c_lon:
                continue
            if _ti_le_nam_trong(nho, lon) >= ti_le:
                ket.add(id_lon)
                break
    return ket
