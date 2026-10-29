"""E57 — trần số lượt "đọc thử để đoán ngôn ngữ" mỗi ngày.

## Vì sao đường này BẮT BUỘC có trần riêng

Nó nhận ảnh và trả về **chữ đã đọc được** (qua `bang_chung`), tức là một dịch vụ OCR. Không có trần
thì ai cũng dùng nó làm OCR miễn phí không giới hạn, và đó là đúng thứ hạn mức trang của E49 được
dựng để chặn.

## Vì sao KHÔNG trừ vào hạn mức TRANG

Người dùng chưa nhận được bản dịch nào. Trừ lượt dịch cho một phép đoán ngôn ngữ là bắt họ trả bằng
thứ họ quan tâm cho một bước phụ trợ — và tệ hơn: khách có 6 lượt sẽ mất 1 lượt chỉ vì bấm "Tự
nhận", nên **tính năng này càng dùng càng đắt**, người ta sẽ tránh nó và quay lại chọn tay sai.

⇒ bộ đếm **riêng**, trần riêng, không lẫn vào bộ đếm trang.

## Dùng lại sổ cái, KHÔNG thêm giá trị enum mới

Y hệt cách `han_muc_dang_ky.py` làm, và vì đúng cùng một lý do (thêm giá trị vào enum Postgres đang
chạy là một lượt `ALTER TYPE` trên production). Phân biệt bằng **tiền tố chủ thể**:

    chu_the = "nhan-ngon-ngu:<băm-ip>"   ← bộ đếm này
    chu_the = "dang-ky:<băm-ip>"         ← trần tạo tài khoản (E52)
    chu_the = "<băm-ip>"                 ← hạn mức TRANG (E49)

Ba chuỗi không bao giờ trùng: băm là 32 ký tự hex trần, không chứa dấu hai chấm.

## Đếm theo CHỐT NÀO

Theo **đúng các chốt của người gọi** — khách lạ có cả chốt cookie và chốt IP, người đăng nhập có chốt
tài khoản. Nếu chỉ đếm theo cookie thì xoá cookie là có suất mới, và trần thành trang trí.
"""
from __future__ import annotations

import uuid
from datetime import date

from app.core.danh_tinh_khach import Chot, DanhTinhHanMuc
from app.services.so_cai_han_muc import (
    KetQuaGiuCho,
    da_dung_bat_dong_bo,
    giu_cho_bat_dong_bo,
)

#: Tiền tố tách bộ đếm "số lượt đọc thử" khỏi hai bộ đếm kia trên cùng một chủ thể.
TIEN_TO = "nhan-ngon-ngu:"


def chu_the(chot: Chot) -> str:
    return f"{TIEN_TO}{chot.chu_the}"


async def da_dung_bao_nhieu(session, chot: Chot, ngay: date) -> int:
    """Số lượt chủ thể này đã dùng trong `ngay`. Chỉ ĐỌC."""
    return await da_dung_bat_dong_bo(session, chot.loai, chu_the(chot), ngay)


async def con_lai_it_nhat(session, danh_tinh: DanhTinhHanMuc, ngay: date, tran: int) -> int:
    """Số lượt còn lại — lấy **nhỏ nhất** trong các chốt, không phải của chốt đầu tiên.

    Lấy chốt đầu tiên sẽ báo "còn 3 lượt" rồi từ chối ngay lượt sau, vì chốt chặn là một chốt khác.
    """
    con = tran
    for c in danh_tinh.chot:
        con = min(con, tran - await da_dung_bao_nhieu(session, c, ngay))
    return max(0, con)


async def giu_mot_luot(
    session, *, danh_tinh: DanhTinhHanMuc, ngay: date, tran: int
) -> tuple[KetQuaGiuCho, Chot | None]:
    """Giữ MỘT lượt trên **mọi** chốt. Không tự commit — nơi gọi commit cùng lượt tạo bản ghi.

    Trả `(kết quả, chốt bị chặn)`. Chốt bị chặn có để giao diện nói đúng câu: hết lượt của *bạn*
    khác hẳn hết lượt của *địa chỉ mạng dùng chung*.

    Giữ trên MỌI chốt, không phải chốt đầu: bỏ sót một chốt là để lại đúng một đường lách.

    Khoá chống trùng là `uuid4()` mỗi lượt vì ở đây **không có** thao tác "thử lại cùng một việc" —
    mỗi lần bấm là một lượt đọc thử riêng, tốn công riêng.
    """
    khoa_chung = uuid.uuid4()
    cuoi: KetQuaGiuCho | None = None
    for c in danh_tinh.chot:
        kq = await giu_cho_bat_dong_bo(
            session,
            khoa=f"{TIEN_TO}{khoa_chung}:{c.loai.value}",
            loai=c.loai,
            chu_the=chu_the(c),
            ngay=ngay,
            so_trang=1,
            tran=tran,
        )
        if not kq.thanh_cong:
            return kq, c
        cuoi = kq

    if cuoi is None:
        # Không có chốt nào = không có gì chặn. Đây phải là KHÔNG THỂ xảy ra (`DanhTinhHanMuc` luôn
        # có ít nhất một chốt), nên nổ tường minh chứ đừng trả "thành công": một đường tải ảnh
        # không có trần nào là đúng lỗ mà module này tồn tại để bịt.
        raise RuntimeError("danh_tinh_khong_co_chot: không có chốt nào để giữ lượt nhận dạng")
    return cuoi, None
