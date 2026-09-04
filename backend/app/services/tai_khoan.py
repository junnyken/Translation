"""Đăng ký, đăng nhập, đăng xuất (Auth slice B).

Tách khỏi tầng HTTP để test được không cần dựng request. Mọi hàm ở đây nhận `AsyncSession`
và trả về object/None — **không** ném `HTTPException`; việc dịch sang mã lỗi HTTP là của
`app/api/v1/xac_thuc_routes.py`.

## Hai quy tắc chống rò rỉ thông tin

1. `dang_nhap` trả về `None` **giống hệt nhau** cho: email không tồn tại, sai mật khẩu, và tài
   khoản bị khoá. Nói ra sự khác biệt là xác nhận cho người dò biết email nào có thật.
2. Sai email vẫn **băm một mật khẩu giả**. Nếu không, "email không tồn tại" trả về sau 1ms còn
   "sai mật khẩu" sau 83ms — chênh lệch đó đủ để dò ra danh sách email có thật.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import mat_khau as mk
from app.core import phien as ph
from app.models import NguoiDung, Phien

#: Mật khẩu ngắn hơn ngưỡng này bị từ chối. 8 là mức tối thiểu NIST SP 800-63B.
DAI_MAT_KHAU_TOI_THIEU = 8
#: Chuỗi băm dùng để "đốt thời gian" khi email không tồn tại (xem quy tắc 2 ở docstring).
#: Băm sẵn một lần lúc nạp module, không phải mỗi request.
_BAM_GIA = mk.bam("khong-phai-mat-khau-cua-ai")


def chuan_hoa_email(email: str) -> str:
    """Hạ chữ thường + cắt khoảng trắng. Bắt buộc dùng ở CẢ đăng ký lẫn đăng nhập.

    Chuẩn hoá một bên mà quên bên kia là lỗi kinh điển: đăng ký `An@x.com` lưu thành
    `an@x.com`, đăng nhập gõ `An@x.com` tra không ra, người dùng tưởng sai mật khẩu.
    """
    return email.strip().lower()


def kiem_mat_khau_du_manh(mat_khau_tho: str) -> str | None:
    """Trả về lý do từ chối, hoặc None nếu đạt."""
    if len(mat_khau_tho) < DAI_MAT_KHAU_TOI_THIEU:
        return f"Mật khẩu phải dài ít nhất {DAI_MAT_KHAU_TOI_THIEU} ký tự."
    return None


async def dem_nguoi_dung(session: AsyncSession) -> int:
    return int((await session.execute(select(func.count()).select_from(NguoiDung))).scalar() or 0)


async def tim_theo_email(session: AsyncSession, email: str) -> NguoiDung | None:
    return (
        await session.execute(select(NguoiDung).where(NguoiDung.email == chuan_hoa_email(email)))
    ).scalars().first()


async def dang_ky(
    session: AsyncSession, *, email: str, ten_hien: str, mat_khau_tho: str
) -> NguoiDung:
    """Tạo tài khoản. Người **đầu tiên** đăng ký thành quản trị.

    Vì sao người đầu tiên: hệ thống phải có ít nhất một người nhận được các chapter cũ chưa có
    chủ, mà lúc migration chạy thì chưa có tài khoản nào để gán. Người dựng hệ thống là người
    đăng ký trước — đây là quy ước bootstrap chuẩn, và nó được nói thẳng ra trong tài liệu chứ
    không giấu.
    """
    email = chuan_hoa_email(email)
    if await tim_theo_email(session, email) is not None:
        raise ValueError("email_da_ton_tai")
    ly_do = kiem_mat_khau_du_manh(mat_khau_tho)
    if ly_do:
        raise ValueError(ly_do)

    nguoi = NguoiDung(
        email=email,
        ten_hien=ten_hien.strip() or email.split("@")[0],
        mat_khau_bam=mk.bam(mat_khau_tho),
        dang_hoat_dong=True,
        la_quan_tri=await dem_nguoi_dung(session) == 0,
    )
    session.add(nguoi)
    await session.commit()
    await session.refresh(nguoi)
    return nguoi


async def dang_nhap(session: AsyncSession, *, email: str, mat_khau_tho: str) -> tuple[NguoiDung, str] | None:
    """Trả `(người dùng, mã phiên thô)` hoặc None. Mã thô chỉ tồn tại ở đây và ở response."""
    nguoi = await tim_theo_email(session, email)
    if nguoi is None:
        # Đốt đúng lượng thời gian như một lần băm thật (xem quy tắc 2).
        mk.kiem(mat_khau_tho, _BAM_GIA)
        return None
    if not mk.kiem(mat_khau_tho, nguoi.mat_khau_bam):
        return None
    if not nguoi.dang_hoat_dong:
        # Kiểm SAU khi kiểm mật khẩu: kiểm trước sẽ trả lời nhanh hơn cho tài khoản bị khoá.
        return None

    ma_tho = ph.sinh_ma()
    session.add(Phien(nguoi_dung_id=nguoi.id, ma_bam=ph.bam_ma(ma_tho), het_han=ph.han_moi()))
    await session.commit()
    return nguoi, ma_tho


async def lay_theo_ma_phien(session: AsyncSession, ma_tho: str) -> NguoiDung | None:
    """Tra người dùng từ mã phiên. Hết hạn / bị thu hồi / tài khoản khoá ⇒ None."""
    if not ma_tho:
        return None
    ban_ghi = (
        await session.execute(select(Phien).where(Phien.ma_bam == ph.bam_ma(ma_tho)))
    ).scalars().first()
    if ban_ghi is None or not ph.con_han(ban_ghi.het_han):
        return None
    nguoi = await session.get(NguoiDung, ban_ghi.nguoi_dung_id)
    if nguoi is None or not nguoi.dang_hoat_dong:
        return None
    ban_ghi.dung_lan_cuoi = datetime.now(timezone.utc)
    await session.commit()
    return nguoi


async def dang_xuat(session: AsyncSession, ma_tho: str) -> bool:
    """Xoá phiên. Trả True nếu có phiên để xoá."""
    ban_ghi = (
        await session.execute(select(Phien).where(Phien.ma_bam == ph.bam_ma(ma_tho)))
    ).scalars().first()
    if ban_ghi is None:
        return False
    await session.delete(ban_ghi)
    await session.commit()
    return True


async def don_phien_het_han(session: AsyncSession) -> int:
    """Dọn phiên quá hạn. Không bắt buộc cho tính đúng (đã kiểm hạn lúc tra) — chỉ để bảng
    không phình vô hạn."""
    cu = (
        await session.execute(select(Phien).where(Phien.het_han <= datetime.now(timezone.utc)))
    ).scalars().all()
    for p in cu:
        await session.delete(p)
    if cu:
        await session.commit()
    return len(cu)
