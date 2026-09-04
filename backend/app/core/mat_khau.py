"""Băm mật khẩu bằng scrypt (Auth slice B).

## Vì sao scrypt chứ không phải bcrypt/argon2

Không có thư viện băm mật khẩu nào trong môi trường này (`bcrypt`, `argon2`, `passlib` đều
không cài). `hashlib.scrypt` nằm sẵn trong **thư viện chuẩn** và là KDF đúng nghĩa —
memory-hard, chống được máy đào chuyên dụng. Thêm phụ thuộc mới chỉ để băm mật khẩu là đánh
đổi tệ, đúng theo tiền lệ của dự án (E17b dùng `urllib` thay vì kéo `httpx` về).

**Tuyệt đối không** dùng `hashlib.sha256(mat_khau)`. SHA-256 nhanh — đó là ưu điểm cho
checksum và là lỗ hổng cho mật khẩu: card đồ hoạ thử hàng tỉ tổ hợp mỗi giây.

## Tham số

`n=2^14, r=8, p=1` — mức tối thiểu OWASP khuyến nghị cho scrypt, tốn ~16MB RAM mỗi lần băm.
`maxmem` phải đặt tường minh: mặc định của OpenSSL là 32MB và **báo lỗi** chứ không tự nới,
nên để mặc định là đặt bom hẹn giờ cho lần ai đó tăng `n`.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

#: Đổi các số này = mọi mật khẩu cũ vẫn đăng nhập được, vì tham số được ghi kèm trong chuỗi băm.
N = 2 ** 14
R = 8
P = 1
#: Dài 16 byte theo khuyến nghị scrypt; ngẫu nhiên **cho từng người**, không dùng chung.
DAI_MUOI = 16
#: Nới rộng gấp đôi nhu cầu thật (128*N*R*P = 16MB) để còn chỗ cho overhead của OpenSSL.
MAXMEM = 128 * N * R * P * 2

TIEN_TO = "scrypt"


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def bam(mat_khau: str, *, muoi: bytes | None = None) -> str:
    """Trả về chuỗi tự mô tả: `scrypt$n$r$p$muoi$bam`.

    Ghi kèm tham số để sau này đổi `N` mà không khoá người dùng cũ ra ngoài.
    """
    if not mat_khau:
        raise ValueError("mat_khau_rong: không băm chuỗi rỗng")
    muoi = muoi if muoi is not None else secrets.token_bytes(DAI_MUOI)
    dan_xuat = hashlib.scrypt(
        mat_khau.encode("utf-8"), salt=muoi, n=N, r=R, p=P, maxmem=MAXMEM
    )
    return f"{TIEN_TO}${N}${R}${P}${_b64(muoi)}${_b64(dan_xuat)}"


def kiem(mat_khau: str, chuoi_bam: str) -> bool:
    """So mật khẩu với chuỗi băm. Sai định dạng ⇒ False, **không** ném lỗi.

    Ném lỗi ở đây sẽ biến một bản ghi hỏng trong CSDL thành lỗi 500 lúc đăng nhập, và phân biệt
    được "tài khoản hỏng" với "sai mật khẩu" là rò rỉ thông tin cho người dò.
    """
    if not mat_khau or not chuoi_bam:
        return False
    phan = chuoi_bam.split("$")
    if len(phan) != 6 or phan[0] != TIEN_TO:
        return False
    try:
        n, r, p = int(phan[1]), int(phan[2]), int(phan[3])
        muoi = base64.b64decode(phan[4], validate=True)
        mong_doi = base64.b64decode(phan[5], validate=True)
    except (ValueError, TypeError):
        return False
    if n <= 1 or n & (n - 1) or r < 1 or p < 1:
        # scrypt đòi n là luỹ thừa của 2 và > 1; số rác sẽ làm hashlib ném lỗi.
        return False
    try:
        thuc_te = hashlib.scrypt(
            mat_khau.encode("utf-8"), salt=muoi, n=n, r=r, p=p,
            maxmem=max(MAXMEM, 128 * n * r * p * 2),
        )
    except (ValueError, MemoryError):
        # Tham số trong CSDL đòi nhiều RAM hơn máy cho phép — coi như không khớp, đừng sập.
        return False
    # So theo thời gian hằng định: `==` trên bytes dừng ở byte đầu khác nhau.
    return hmac.compare_digest(thuc_te, mong_doi)
