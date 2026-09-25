"""Cổng hạn mức — nối `danh_tinh_khach` với sổ cái, và từ chối bằng **429**.

## Vì sao cổng nằm ở MÁY CHỦ chứ không ở giao diện

Dự án có tiền lệ đúng chỗ này: một bộ test đầy đủ vẫn xanh trong khi cổng chặn chỉ nằm ở giao
diện. Ẩn nút mà API vẫn nhận thì ai mở công cụ nhà phát triển cũng vượt được — và bộ test không
thấy gì, vì nó gọi API chứ không bấm nút.

## Hai phép kiểm, hai vai khác nhau — đừng nhầm

* `con_du_khong` — **chỉ đọc**, không khoá, không giữ chỗ. Dùng để **chặn sớm** một gói lớn
  trước khi ghi tệp nào xuống kho. Kết quả có thể cũ ngay khi trả về.
* `giu_cho_moi_chot` — **chốt chặn thật**: khoá theo chủ thể rồi ghi. Mọi đường tải lên phải đi
  qua hàm này, kể cả khi đã gọi `con_du_khong` ở trên.

Dùng `con_du_khong` làm cổng duy nhất là quay lại đúng lỗi "kiểm rồi ghi trong hai bước".

## Vì sao 429 mang theo `Set-Cookie`

Khách chưa có cookie mà bị từ chối ngay: nếu không cấp cookie trong chính phản hồi 429 thì mỗi
lần thử lại họ là "khách mới" và chốt cookie không bao giờ chạm trần. FastAPI **không** giữ lại
header mà dependency đặt vào `Response` khi route ném lỗi — nên cookie phải được đính thẳng vào
`HTTPException`.
"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, Response, status

from app.core.config import Settings
from app.core.danh_tinh_khach import Chot, DanhTinhHanMuc, dat_cookie_khach
from app.services.han_muc import bay_gio, moc_reset_ke_tiep, ngay_han_muc
from app.services.so_cai_han_muc import con_lai_bat_dong_bo, giu_cho_trang

MA_LOI = "vuot_han_muc"


def _header_cookie(danh_tinh: DanhTinhHanMuc, settings: Settings) -> dict[str, str]:
    """Dựng `Set-Cookie` cho phản hồi lỗi, dùng lại đúng bộ cờ bảo mật của đường thành công."""
    if not danh_tinh.cookie_moi:
        return {}
    tam = Response()
    dat_cookie_khach(tam, danh_tinh.cookie_moi, settings)
    return {"set-cookie": tam.headers["set-cookie"]}


def loi_vuot_han_muc(
    *, danh_tinh: DanhTinhHanMuc, settings: Settings, can: int, con_lai: int, chot: Chot
) -> HTTPException:
    """429 kèm đủ thứ người dùng cần để hiểu: cần bao nhiêu, còn bao nhiêu, bao giờ có lại.

    Thông báo mơ hồ kiểu "đã có lỗi" là thứ làm người dùng tưởng hệ thống hỏng rồi bấm lại liên
    tục — vừa vô ích cho họ vừa tốn tài nguyên của mình.
    """
    reset = moc_reset_ke_tiep()
    con_giay = max(0, int((reset - bay_gio()).total_seconds()))
    headers = {"Retry-After": str(con_giay), **_header_cookie(danh_tinh, settings)}
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        headers=headers,
        detail={
            "loi": MA_LOI,
            "can": can,
            "con_lai": con_lai,
            "tran": chot.tran,
            "co_tai_khoan": danh_tinh.co_tai_khoan,
            # Chốt nào chặn: `khach_ip` nghĩa là chặn vì DÙNG CHUNG địa chỉ mạng, không phải vì
            # chính người này dùng nhiều. Không nói ra thì người ở văn phòng/quán cà phê không
            # hiểu nổi vì sao mình bị chặn khi chưa dùng lượt nào.
            "chot": chot.loai.value,
            "reset_luc": reset.isoformat(),
            "reset_sau_giay": con_giay,
        },
    )


async def con_du_khong(
    session, danh_tinh: DanhTinhHanMuc, settings: Settings, *, so_trang: int
) -> None:
    """Chặn sớm, **trước khi** ghi tệp nào xuống kho. Không giữ chỗ.

    Chỉ để khỏi phí công ghi tệp cho một lượt chắc chắn bị từ chối. Không thay thế
    `giu_cho_moi_chot`.
    """
    ngay = ngay_han_muc()
    for chot in danh_tinh.chot:
        con = await con_lai_bat_dong_bo(session, chot.loai, chot.chu_the, ngay, chot.tran)
        if so_trang > con:
            raise loi_vuot_han_muc(
                danh_tinh=danh_tinh, settings=settings, can=so_trang, con_lai=con, chot=chot
            )


async def giu_cho_moi_chot(
    session, danh_tinh: DanhTinhHanMuc, settings: Settings, *, trang_id: uuid.UUID
) -> None:
    """Giữ chỗ một trang ở **mọi** chốt. Chốt nào không lọt ⇒ 429.

    Khách lạ có hai chốt và phải lọt qua **cả hai**. Không cần gỡ phần đã giữ ở chốt trước khi
    chốt sau từ chối: tất cả nằm trong **một giao dịch**, nơi gọi ném 429 ⇒ giao dịch bị huỷ ⇒
    không dòng nào ở lại. Đó cũng là lý do hàm này **không** tự `commit`.
    """
    ngay = ngay_han_muc()
    for chot in danh_tinh.chot:
        kq = await giu_cho_trang(
            session,
            trang_id=trang_id,
            loai=chot.loai,
            chu_the=chot.chu_the,
            ngay=ngay,
            tran=chot.tran,
        )
        if not kq.thanh_cong:
            raise loi_vuot_han_muc(
                danh_tinh=danh_tinh, settings=settings, can=1, con_lai=kq.con_lai, chot=chot
            )
