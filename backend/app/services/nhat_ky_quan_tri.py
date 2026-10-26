"""Ghi dấu vết thao tác quản trị vào bảng `nhat_ky_quan_tri`.

Không tự commit: dòng nhật ký đi CÙNG giao dịch với thao tác nó ghi lại — thao tác huỷ thì
nhật ký cũng không còn, thao tác thành thì nhật ký chắc chắn có.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import NguoiDung, NhatKyQuanTri


def ghi_nhat_ky(
    session: AsyncSession,
    quan_tri: NguoiDung,
    hanh_dong: str,
    doi_tuong: str = "",
    **chi_tiet: Any,
) -> None:
    session.add(
        NhatKyQuanTri(
            quan_tri_id=quan_tri.id,
            quan_tri_email=quan_tri.email,
            hanh_dong=hanh_dong,
            doi_tuong=doi_tuong[:320],
            chi_tiet={k: v for k, v in chi_tiet.items() if v is not None},
        )
    )
