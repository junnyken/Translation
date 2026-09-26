"""Trần số TÀI KHOẢN mới tạo từ một địa chỉ mạng mỗi ngày.

## Vì sao phần này BẮT BUỘC đi cùng việc mở đường tự đăng ký

Không có trần này thì hạn mức trang của E49 **trở thành vô nghĩa**: khách dùng hết 6 trang chỉ
cần tạo một tài khoản mới để có 10, rồi lặp vô hạn. Mở đăng ký mà quên con số này không phải là
"làm thiếu" — nó là tự tay vô hiệu hoá cả tính năng vừa xây.

## Dùng lại sổ cái, KHÔNG thêm giá trị enum mới

Đơn vị ở đây là **tài khoản**, không phải trang — nhưng hình dạng dữ liệu y hệt: "một chủ thể đã
tiêu bao nhiêu đơn vị trong một ngày". Nên dùng lại `so_cai_han_muc` cùng toàn bộ phần khoá song
song và chống trùng của nó.

Phân biệt bằng **tiền tố chủ thể**, không bằng `loai_chu_the` mới:

    loai_chu_the = khach_ip
    chu_the      = "dang-ky:<băm-ip>"     ← tiền tố này
    chu_the      = "<băm-ip>"             ← hạn mức TRANG, không tiền tố

Hai chuỗi không bao giờ trùng nhau (băm là 32 ký tự hex trần, không chứa dấu hai chấm), và
`da_dung_*` lọc theo đúng `chu_the` nên hai bộ đếm không lẫn vào nhau.

Vì sao không thêm `LoaiChuThe.dang_ky_ip`: thêm giá trị vào một enum Postgres ĐANG CHẠY là một
lượt `ALTER TYPE` trên production, mà `CLAUDE.md` của dự án đã cảnh báo riêng về enum trong
migration. Đổi một chuỗi lấy việc không phải mổ enum là món hời.

## Vì sao mỗi lượt đăng ký một khoá mới

Khác hạn mức trang, ở đây **không có** thao tác "thử lại cùng một việc": mỗi lần đăng ký là một
sự kiện riêng. Nên khoá chống trùng là một `uuid4()` mới mỗi lượt, không phải khoá suy từ dữ liệu.

## Suất chỉ mất khi tài khoản THẬT SỰ được tạo

Hàng giữ suất được thêm vào **cùng phiên** với lượt tạo tài khoản. Email trùng hay mật khẩu yếu
⇒ ngoại lệ ⇒ giao dịch bị huỷ ⇒ hàng đó biến mất. Cùng một luật với "tệp hỏng không mất lượt"
của đường tải lên.
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

#: Tiền tố tách bộ đếm "số tài khoản" khỏi bộ đếm "số trang" trên cùng một chủ thể IP.
TIEN_TO = "dang-ky:"

#: Cùng `loai_chu_the` với chốt IP của hạn mức trang — xem docstring module.
LOAI = LoaiChuThe.khach_ip


def chu_the_dang_ky(ip_da_bam: str) -> str:
    return f"{TIEN_TO}{ip_da_bam}"


async def da_tao_bao_nhieu(session, ip_da_bam: str, ngay: date) -> int:
    """Số tài khoản địa chỉ mạng này đã tạo trong `ngay`. Chỉ ĐỌC."""
    return await da_dung_bat_dong_bo(session, LOAI, chu_the_dang_ky(ip_da_bam), ngay)


async def giu_suat_dang_ky(
    session, *, ip_da_bam: str, ngay: date, tran: int
) -> KetQuaGiuCho:
    """Giữ MỘT suất tạo tài khoản. Không tự commit — nơi gọi commit cùng lượt tạo tài khoản.

    Trả `thanh_cong=False` kèm `ly_do="vuot_han_muc"` khi địa chỉ mạng này đã chạm trần.
    """
    return await giu_cho_bat_dong_bo(
        session,
        khoa=f"{TIEN_TO}{uuid.uuid4()}",
        loai=LOAI,
        chu_the=chu_the_dang_ky(ip_da_bam),
        ngay=ngay,
        so_trang=1,
        tran=tran,
    )
