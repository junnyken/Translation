"""Cổng khoá truy cập (Auth slice A).

Trước lớp này, **65 thao tác API mở toang, 31 trong đó ghi/xoá** — ai có URL là tạo, sửa, xoá
được mọi chapter của mọi người. Đo trực tiếp trên bản chạy thật 2026-09-04.

## Đây là gì và KHÔNG phải gì

Là **một khoá chung cho cả hệ thống**: đủ để chặn người lạ, **không** phải hệ thống tài khoản.
Nó KHÔNG phân biệt ai làm gì, KHÔNG giới hạn ai xem chapter của ai, và KHÔNG chống được người
đã có khoá. Ai cầm khoá là làm được mọi thứ.

Nói rõ vậy để không ai nhìn thấy chữ "auth" rồi tưởng đã có phân quyền. Phân quyền thật (tài
khoản riêng, chapter có chủ) là slice B.

## Vì sao mặc định TẮT

`api_access_key` rỗng ⇒ cổng mở. Có chủ đích, vì hai lý do:

1. Máy phát triển và bộ test không phải mang khoá đi khắp nơi.
2. **Thứ tự triển khai an toàn**: đẩy mã lên trước (cổng còn tắt), deploy giao diện biết gửi
   khoá, RỒI mới đặt biến môi trường. Đặt khoá trước khi giao diện biết gửi là tự khoá mình
   ra ngoài chính hệ thống của mình.

Nhưng tắt im lặng là cái bẫy, nên lúc khởi động có **cảnh báo to** trong log.
"""
from __future__ import annotations

import hmac
import logging

from fastapi import Header, HTTPException, status

from app.core.config import get_settings

logger = logging.getLogger(__name__)

TEN_HEADER = "X-API-Key"


def canh_bao_neu_khong_khoa() -> None:
    """Gọi lúc khởi động. Cổng tắt phải nói ra, không được tắt im lặng."""
    if not get_settings().api_access_key:
        logger.warning(
            "CỔNG KHOÁ ĐANG TẮT — mọi thao tác API, kể cả xoá, đều không cần xác thực. "
            "Đặt API_ACCESS_KEY để bật. (Bình thường ở máy phát triển; KHÔNG bình thường trên "
            "bản chạy thật.)"
        )


async def cong_khoa(x_api_key: str | None = Header(default=None, alias=TEN_HEADER)) -> None:
    """Chặn request thiếu khoá đúng.

    **Chỉ gắn ở `POST /auth/register`** — đừng đọc câu này thành "cả API đều sau khoá chung".
    Từ slice B, thứ gắn ở tầng router cho toàn bộ `/api/v1` là cổng **đăng nhập**
    (`main.py`: `include_router(v1_router, dependencies=[Depends(nguoi_dung_hien_tai)])`).
    ## E52 — cổng này nay CÓ ĐIỀU KIỆN, và không còn là một dependency

    Từ E52, `POST /auth/register` **không** gắn `Depends(cong_khoa)` nữa: nó gọi hàm này trong
    THÂN hàm, và **chỉ khi hệ thống chưa có tài khoản nào**.

    Lý do: gác vô điều kiện làm người lạ không tự đăng ký được, trái §4.1 đặc tả — khách dùng hết
    hạn mức khách lạ không có đường nào lên hạn mức có tài khoản. Chỗ duy nhất còn cần khoá là
    lượt tạo tài khoản **ĐẦU TIÊN**: nó thành quản trị và nhận các chapter cũ chưa có chủ.

    Sau lượt đầu, đường đăng ký mở và được chặn bằng **trần theo địa chỉ mạng**
    (`services/han_muc_dang_ky.py`) — thiếu trần đó thì hạn mức trang của E49 thành vô nghĩa.

    ⇒ Đừng tìm `cong_khoa` trong cây phụ thuộc của endpoint để kết luận "có gác hay không";
    phép soi đó nay luôn trả về "không". Đo hành vi thật, như
    `test_bao_ve_integration::test_dang_ky_TAI_KHOAN_DAU_TIEN_van_duoc_khoa_chung_gac`.

    (Docstring cũ ghi "gắn ở tầng router nên không sót endpoint nào" — đúng với slice A, sai kể
    từ slice B. Một câu sai về bảo mật nguy hiểm hơn là không có câu nào.)
    """
    khoa = get_settings().api_access_key
    if not khoa:
        return

    # So sánh theo thời gian HẰNG ĐỊNH. So bằng `==` sẽ dừng ở byte đầu khác nhau, và chênh lệch
    # thời gian đó đủ để dò ra khoá từng ký tự một.
    hop_le = x_api_key is not None and hmac.compare_digest(
        x_api_key.encode("utf-8"), khoa.encode("utf-8")
    )
    if not hop_le:
        # Cùng MỘT thông báo cho "thiếu khoá" và "khoá sai": nói ra sự khác biệt là xác nhận cho
        # người dò biết họ đã đoán đúng định dạng.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Thiếu hoặc sai khoá truy cập. Gửi khoá ở header "
                f"`{TEN_HEADER}`. Nếu bạn là chủ hệ thống, khoá nằm ở biến API_ACCESS_KEY."
            ),
            headers={"WWW-Authenticate": TEN_HEADER},
        )
