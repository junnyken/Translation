"""Sinh và kiểm mã phiên đăng nhập (Auth slice B).

## Vì sao KHÔNG dùng JWT

JWT không thu hồi được. Người dùng bấm "đăng xuất" hoặc bị đổi mật khẩu mà token vẫn còn hiệu
lực tới lúc hết hạn là hành vi sai. Mã phiên đục (opaque) tra trong CSDL thì xoá một dòng là
tức thì mất hiệu lực. Đổi lại là một lượt truy vấn mỗi request — chấp nhận được, và đằng nào
mỗi request cũng đã mở một phiên CSDL rồi.

## Vì sao băm mã phiên bằng SHA-256 mà mật khẩu lại dùng scrypt

Không mâu thuẫn. scrypt cố tình chậm để chống **dò mật khẩu người nghĩ ra** — vốn ít entropy
("123456", tên thú cưng). Mã phiên là 256 bit **ngẫu nhiên từ máy**: không có gì để đoán, dò
cạn kiệt là bất khả thi bất kể hàm băm nhanh cỡ nào. Dùng scrypt ở đây chỉ tốn 83ms mỗi
request mà không mua thêm được chút an toàn nào.

Vẫn **phải băm** trước khi lưu: kẻ đọc được CSDL (bản sao lưu rò rỉ, SQL injection) sẽ cầm
được mã phiên còn hạn và mạo danh ngay, không cần biết mật khẩu.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

#: 32 byte = 256 bit entropy.
DAI_MA = 32
#: Phiên hết hạn sau 14 ngày. Đủ dài để không phải đăng nhập lại mỗi ngày, đủ ngắn để một máy
#: bị bỏ quên không mở cửa mãi mãi.
HAN_NGAY = 14


def sinh_ma() -> str:
    """Mã phiên thô — trả cho người dùng **đúng một lần**, không lưu ở đâu dạng thô."""
    return secrets.token_urlsafe(DAI_MA)


def bam_ma(ma: str) -> str:
    """Dạng lưu trong CSDL. Xác định (không muối) để tra cứu được bằng index."""
    return hashlib.sha256(ma.encode("utf-8")).hexdigest()


def han_moi(*, bay_gio: datetime | None = None) -> datetime:
    bay_gio = bay_gio or datetime.now(timezone.utc)
    return bay_gio + timedelta(days=HAN_NGAY)


def con_han(het_han: datetime, *, bay_gio: datetime | None = None) -> bool:
    """Còn hạn không. Nhận cả mốc thời gian **không mang múi giờ** (Postgres trả về như vậy
    khi cột là `TIMESTAMP WITHOUT TIME ZONE`) — coi đó là UTC, vì mọi mốc đều được ghi bằng
    `datetime.now(timezone.utc)`."""
    bay_gio = bay_gio or datetime.now(timezone.utc)
    if het_han.tzinfo is None:
        het_han = het_han.replace(tzinfo=timezone.utc)
    return het_han > bay_gio
