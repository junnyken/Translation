"""Nới khung chữ ra chỗ trống quanh nó, khi KHÔNG dựng được hình bong bóng (E14 · A1).

## Vì sao cần

E14 tách bong bóng bằng ngưỡng **sáng**: bong bóng trắng nổi trên nền vẽ. Cách đó chết trên
manga đen trắng — bong bóng trắng nằm trên **trang cũng trắng**, không có ranh giới sáng/tối nào
để tách. Đo thật 04/09 trên một trang manga tiếng Nhật: `shape_derived: 0/8` — không vùng nào
dựng được hình, cả 8 rơi về khung dự phòng.

Khung dự phòng chính là **bbox chữ gốc thụt vào**. Với manga chữ dọc, bbox đó là **cột chữ
Nhật**: cao và rất hẹp. Chữ Việt viết ngang nhét vào cột hẹp thì mỗi dòng được 2-3 ký tự, và
3/8 vùng tràn khung kể cả ở cỡ chữ nhỏ nhất. Bong bóng thật thì rộng gấp mấy lần.

## Cách làm

Không đi tìm bong bóng nữa — **nới khung ra tới khi chạm nét mực**. Viền bong bóng chính là nét
mực, nên phép nới tự dừng đúng ở mép trong của bong bóng, kể cả khi cả hai phía đều trắng.

Vùng chữ nằm trên nền vẽ (tiếng động, chữ ngoài bong bóng) thì nét vẽ chặn ngay — không nới
được mấy, và đó là kết quả đúng.

## Ba giới hạn cố ý

1. **Chỉ nới trong ROI** đã tính sẵn của E14 — không cho một bong bóng chạm mép panel nuốt luôn
   rãnh trắng giữa các panel rồi tràn sang panel bên cạnh.
2. **Chặn theo bội của bbox**: nới quá tay thì chữ rơi ra chỗ trống vô nghĩa của bong bóng lớn.
3. **Dải mới phải sạch HOÀN TOÀN** mới nhận. Không có ngưỡng "gần sạch": một nét mực lọt vào là
   chữ sẽ đè lên hình vẽ.
"""
from __future__ import annotations

from dataclasses import dataclass

#: Ba thứ tự nới cố định, thử cả ba rồi lấy ô LỚN NHẤT.
#:
#: Vì sao không dùng một thứ tự: nới luân phiên bốn phía trong một bong bóng tròn thì ô bị khoá
#: sớm ở dạng cao-hẹp — đo trên trang dựng thử: 44×280 chỉ nới ra 166×352, trong khi ưu tiên
#: chiều ngang cho ra ô rộng hơn hẳn. Mà chữ thì cần ô RỘNG: ô cao-hẹp là mỗi dòng một hai từ.
#:
#: Đây đúng là bài học E14 đã trả giá ở `layout.py` (`_CACH_NO`) — lặp lại ở đây thay vì để bộ
#: nới mới tự vấp lại một lần nữa.
_CACH_NO = (
    ("trai", "phai", "tren", "duoi"),
    ("trai", "phai", "trai", "phai", "tren", "duoi"),
    ("tren", "duoi", "trai", "phai"),
)


@dataclass(frozen=True)
class KetQuaNoi:
    x: int
    y: int
    w: int
    h: int
    #: Diện tích tăng bao nhiêu lần so với khung ban đầu. 1.0 = không nới được gì.
    he_so_dien_tich: float


def _no_theo_thu_tu(mat_na_trong, o, gioi_han, thu_tu, buoc):
    """Nới theo ĐÚNG một thứ tự phía cho trước. Trả `(x0, y0, x1, y1)`."""
    x0, y0, x1, y1 = o
    gx0, gy0, gx1, gy1 = gioi_han
    con_nhich = True
    while con_nhich:
        con_nhich = False
        for phia in thu_tu:
            if phia == "trai":
                moi = max(x0 - buoc, gx0)
                if moi == x0:
                    continue
                dai = mat_na_trong[y0:y1, moi:x0]
                if dai.size and dai.all():
                    x0, con_nhich = moi, True
            elif phia == "phai":
                moi = min(x1 + buoc, gx1)
                if moi == x1:
                    continue
                dai = mat_na_trong[y0:y1, x1:moi]
                if dai.size and dai.all():
                    x1, con_nhich = moi, True
            elif phia == "tren":
                moi = max(y0 - buoc, gy0)
                if moi == y0:
                    continue
                dai = mat_na_trong[moi:y0, x0:x1]
                if dai.size and dai.all():
                    y0, con_nhich = moi, True
            else:
                moi = min(y1 + buoc, gy1)
                if moi == y1:
                    continue
                dai = mat_na_trong[y1:moi, x0:x1]
                if dai.size and dai.all():
                    y1, con_nhich = moi, True
    return x0, y0, x1, y1


def no_khung_ra_cho_trong(
    mat_na_trong,
    o_bat_dau: tuple[int, int, int, int],
    *,
    gioi_han: tuple[int, int, int, int],
    buoc: int = 2,
) -> KetQuaNoi | None:
    """Nới hình chữ nhật ra bốn phía chừng nào dải mới còn nằm trọn trong `mat_na_trong`.

    `mat_na_trong`: mảng bool/uint8 — True (khác 0) là chỗ ĐƯỢC PHÉP đặt chữ (trắng, không mực).
    `o_bat_dau`, `gioi_han`: `(x, y, w, h)` trong cùng hệ toạ độ với mặt nạ.

    Thử cả ba thứ tự ở `_CACH_NO` rồi lấy ô lớn nhất; hoà nhau thì lấy cách đứng trước, nên kết
    quả vẫn tất định.

    **Ô ban đầu luôn được coi là chỗ trống**, dù trong đó có mực hay không. Bản đầu của hàm này
    đòi ô ban đầu phải sạch tuyệt đối rồi mới nới — nghe có lý, và SAI với thực tế: ô ban đầu
    chính là chỗ chữ gốc vừa bị xoá, mà bước xoá chữ hầu như luôn để sót nét (log của trang thật
    04/09: `còn chữ ở 8/8 vùng`). Hậu quả đo được: trên đúng trang manga cần sửa, phép nới **từ
    chối chạy ở cả 8 vùng** và bản sửa thành vô dụng.

    Mực còn sót trong ô ban đầu không phải lý do để không nới: chữ dịch đằng nào cũng được vẽ đè
    lên đúng chỗ đó. Cái phải sạch là **dải nới thêm** — và điều đó vẫn giữ nguyên.

    Trả `None` khi ô ban đầu rỗng hoặc nằm ngoài mặt nạ.
    """
    h_mask, w_mask = mat_na_trong.shape[:2]
    gx, gy, gw, gh = gioi_han
    gx0, gy0 = max(int(gx), 0), max(int(gy), 0)
    gx1, gy1 = min(int(gx + gw), w_mask), min(int(gy + gh), h_mask)

    x, y, w, h = (int(round(v)) for v in o_bat_dau)
    x0, y0 = max(x, gx0), max(y, gy0)
    x1, y1 = min(x + w, gx1), min(y + h, gy1)
    if x1 - x0 < 1 or y1 - y0 < 1:
        return None

    # Coi ô ban đầu là chỗ trống — xem ghi chú ở docstring. Chép mặt nạ chứ không sửa tại chỗ:
    # bên gọi còn dùng lại nó cho vùng khác của cùng một trang.
    mat_na_trong = mat_na_trong.copy()
    mat_na_trong[y0:y1, x0:x1] = True

    dt_dau = (x1 - x0) * (y1 - y0)
    buoc = max(int(buoc), 1)
    tot = None
    for thu_tu in _CACH_NO:
        o = _no_theo_thu_tu(
            mat_na_trong, (x0, y0, x1, y1), (gx0, gy0, gx1, gy1), thu_tu, buoc)
        dt = (o[2] - o[0]) * (o[3] - o[1])
        if tot is None or dt > (tot[2] - tot[0]) * (tot[3] - tot[1]):
            tot = o

    bx0, by0, bx1, by1 = tot
    dt = (bx1 - bx0) * (by1 - by0)
    return KetQuaNoi(
        x=bx0, y=by0, w=bx1 - bx0, h=by1 - by0,
        he_so_dien_tich=round(dt / max(dt_dau, 1), 4),
    )


def gioi_han_no(
    bbox_x: float, bbox_y: float, bbox_w: float, bbox_h: float,
    roi: tuple[int, int, int, int],
    ty_le_toi_da: float,
    px_toi_da: int,
) -> tuple[int, int, int, int]:
    """Vùng được phép nới tới: bbox phình ra theo bội của **cạnh DÀI**, rồi cắt cho nằm trong ROI.

    Chặn theo bội của bbox chứ không theo một số pixel cố định: bong bóng của một trang 1600px
    và một trang 800px khác nhau hẳn về cỡ, mà cùng một con số pixel thì hoặc quá chật cho trang
    lớn, hoặc quá rộng cho trang nhỏ.

    Vì sao lấy cạnh DÀI cho cả hai chiều, không lấy cạnh tương ứng: cột chữ dọc kiểu Nhật rộng
    44px, cao 280px. Chặn chiều ngang theo chính bề rộng của nó (44×1,5 = 66px mỗi bên) thì
    khung không bao giờ vượt quá 176px — trong khi lòng bong bóng rộng hơn gấp đôi. Đo thật trên
    trang dựng thử: chặn theo cạnh ngắn cho ra ô 170×350, chặn theo cạnh dài cho ra ô rộng hơn
    hẳn và cỡ chữ nhảy từ 10 lên 27.

    Bong bóng thì gần vuông, còn khung chữ bên trong nó có thể rất dẹt — nên cạnh dài mới là
    thước đo đúng cho "bong bóng này to cỡ nào". Phần nới thừa vẫn bị ROI và nét mực chặn lại.
    """
    canh_dai = max(bbox_w, bbox_h)
    them_x = them_y = min(canh_dai * ty_le_toi_da, px_toi_da)
    rx, ry, rw, rh = roi
    x0 = max(int(bbox_x - them_x), rx)
    y0 = max(int(bbox_y - them_y), ry)
    x1 = min(int(bbox_x + bbox_w + them_x), rx + rw)
    y1 = min(int(bbox_y + bbox_h + them_y), ry + rh)
    return x0, y0, max(x1 - x0, 0), max(y1 - y0, 0)
