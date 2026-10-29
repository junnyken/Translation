"""Ước lượng một khung chứa được bao nhiêu ký tự tiếng Việt (E18 · hướng 2).

## Vì sao cần

Bong bóng manga được vẽ vừa đúng lượng chữ **tiếng Nhật** — thứ viết cực gọn (một kanji thay
cho cả một từ tiếng Việt). Bản dịch tiếng Việt dài gấp hai ba lần là chuyện thường, và lúc đó
**không có cách xếp chữ nào cứu được**: đo trên trang thật 04/09, một bong bóng chứa ~30 ký tự
Nhật nhận về bản dịch 105 ký tự, tràn khung kể cả sau khi đã nới khung hết cỡ (A1).

Bước dịch hiện KHÔNG hề biết bong bóng to bao nhiêu: nó dịch xong rồi mới có người đi tìm chỗ
nhét. Module này cung cấp con số còn thiếu — **sức chứa** — để bước dịch biết mà viết gọn lại.

## Đây là ƯỚC LƯỢNG, và nói thẳng ra như vậy

Bề rộng mỗi ký tự khác nhau ("i" với "M"), chỗ ngắt dòng phụ thuộc chỗ có dấu cách, nên không
con số nào đúng tuyệt đối. Cách làm ở đây: đo **bề rộng trung bình thật** của một mẫu chữ Việt
có dấu bằng chính font sẽ dùng, rồi nhân số dòng.

Vì vậy sức chứa **không phải lời hứa**. Sau khi dịch lại vẫn phải chạy `fit()` thật — bộ căn chữ
mới là bên có thẩm quyền nói vừa hay không, và nó vẫn báo tràn nếu vẫn tràn.
"""
from __future__ import annotations

from dataclasses import dataclass

#: Mẫu đo: chữ Việt có dấu, trộn hoa thường, đúng loại chữ sẽ xuất hiện trong bản dịch.
#: Cố định để phép đo tất định — đổi mẫu là đổi mọi con số sức chứa.
MAU_DO = "Đừng ngoảnh lại nhé cậu ổn chứ tôi thấy như mình đang đi đúng con đường"

#: Chữ không bao giờ lấp kín từng dòng: dòng cuối mỗi đoạn dở dang, và ngắt dòng theo TỪ nên
#: mép phải luôn so le. Đo trên các trang thật của M6-E14: khoảng 0,85.
HE_SO_LAP_DAY = 0.85


@dataclass(frozen=True)
class SucChua:
    #: Số ký tự ước tính vừa khung ở cỡ chữ mục tiêu.
    so_ky_tu: int
    #: Cỡ chữ dùng để ước lượng — cùng một khung, cỡ khác nhau cho sức chứa khác nhau.
    co_chu: int
    so_dong: int
    #: Bề rộng trung bình một ký tự ở cỡ đó, đo bằng chính font sẽ dùng.
    rong_tb: float


def co_chu_muc_tieu(min_size: int, max_size: int, ty_le: float) -> int:
    """Cỡ chữ dùng làm mốc đo sức chứa.

    KHÔNG lấy cỡ nhỏ nhất: sức chứa khi đó là "nhét được tối đa bao nhiêu", và bản dịch vừa vặn
    ở cỡ 10 là bản dịch không ai đọc nổi. Cũng không lấy cỡ lớn nhất: ép bản dịch ngắn tới mức
    mất nghĩa. Lấy một mốc giữa, để ngoài `.env` chỉnh được.
    """
    ty_le = min(max(ty_le, 0.0), 1.0)
    return int(round(min_size + (max_size - min_size) * ty_le))


def suc_chua_khung(
    rong: float,
    cao: float,
    font_resolver,
    font_family: str,
    co_chu: int,
    line_spacing_ratio: float,
    he_so_lap_day: float = HE_SO_LAP_DAY,
) -> SucChua:
    """Khung `rong × cao` chứa được bao nhiêu ký tự ở cỡ `co_chu`.

    Dùng đúng `FontResolver` của M6 nên số đo đến từ **chính file font sẽ vẽ**, không phải một
    bảng bề rộng đoán sẵn.
    """
    font = font_resolver.resolve(font_family, co_chu)
    rong_mau = font.getlength(MAU_DO)
    rong_tb = rong_mau / max(len(MAU_DO), 1)

    cao_dong = co_chu * (1.0 + max(line_spacing_ratio, 0.0))
    so_dong = max(int(cao // cao_dong), 1)
    ky_tu_moi_dong = max(int(rong // max(rong_tb, 0.1)), 1)

    return SucChua(
        so_ky_tu=max(int(so_dong * ky_tu_moi_dong * he_so_lap_day), 1),
        co_chu=co_chu,
        so_dong=so_dong,
        rong_tb=round(rong_tb, 3),
    )
