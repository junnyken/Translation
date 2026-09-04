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
    """Chặn mọi request thiếu khoá đúng. Gắn ở tầng router nên không sót endpoint nào."""
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
