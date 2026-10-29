"""Trần số lần ĐĂNG NHẬP SAI từ một địa chỉ mạng mỗi ngày (chống dò mật khẩu brute-force).

## Vì sao chỉ trừ suất khi đăng nhập THẤT BẠI

Nếu trừ suất cho mọi lượt gọi `/auth/login`, một văn phòng nhiều người cùng đăng nhập đúng sẽ chặn
nhau, hoặc kẻ tấn công chỉ cần gửi 10 lượt sai là khoá luôn người dùng thật đang dùng chung mạng
không đăng nhập đúng được nữa? Khoan — trần theo IP cho lượt SAI chặn cả việc thử mật khẩu tiếp từ
cùng IP đó, nhưng:
1. Người đăng nhập ĐÚNG ngay từ đầu không bao giờ làm tăng bộ đếm.
2. Khi IP đã chạm trần `so_lan_dang_nhap_sai_moi_ip_mot_ngay`, từ chối 429 TRƯỚC khi băm `scrypt`
   (mỗi lượt băm tốn ~83ms CPU) để kẻ dò mật khẩu không làm nghẽn CPU của máy chủ.

## Dùng lại sổ cái `so_cai_han_muc`, phân biệt bằng tiền tố

Cùng nguyên tắc với `han_muc_dang_ky.py` và `han_muc_nhan_dang.py`:

    loai_chu_the = khach_ip
    chu_the      = "dang-nhap-sai:<băm-ip>"

Không thêm giá trị vào enum Postgres `LoaiChuThe` (tránh `ALTER TYPE`), không lẫn với bộ đếm trang
(`<băm-ip>` trần) hay bộ đếm tạo tài khoản (`dang-ky:<băm-ip>`).
"""
from __future__ import annotations

import uuid
from datetime import date

from app.models.enums import LoaiChuThe
from app.services.so_cai_han_muc import (
    KetQuaGiuCho,
    da_dung_bat_dong_bo,
    giu_cho_bat_dong_bo,
)

#: Tiền tố tách bộ đếm "đăng nhập sai" khỏi bộ đếm trang và bộ đếm tạo tài khoản.
TIEN_TO = "dang-nhap-sai:"

LOAI = LoaiChuThe.khach_ip


def chu_the_dang_nhap_sai(ip_da_bam: str) -> str:
    return f"{TIEN_TO}{ip_da_bam}"


async def da_sai_bao_nhieu(session, ip_da_bam: str, ngay: date) -> int:
    """Số lần địa chỉ mạng này đã đăng nhập sai trong `ngay`. Chỉ ĐỌC."""
    return await da_dung_bat_dong_bo(session, LOAI, chu_the_dang_nhap_sai(ip_da_bam), ngay)


async def ghi_nhan_dang_nhap_sai(
    session, *, ip_da_bam: str, ngay: date, tran: int
) -> KetQuaGiuCho:
    """Ghi nhận MỘT lần đăng nhập sai vào sổ cái.

    Trả `thanh_cong=False` kèm `ly_do="vuot_han_muc"` khi địa chỉ mạng đã chạm trần.
    """
    return await giu_cho_bat_dong_bo(
        session,
        khoa=f"{TIEN_TO}{uuid.uuid4()}",
        loai=LOAI,
        chu_the=chu_the_dang_nhap_sai(ip_da_bam),
        ngay=ngay,
        so_trang=1,
        tran=tran,
    )
