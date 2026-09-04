"""Endpoint tài khoản (Auth slice B) — router duy nhất KHÔNG đòi đăng nhập.

Tách khỏi `routes.py` vì lý do an toàn chứ không phải gọn gàng: `routes.py` được gắn
`Depends(nguoi_dung_hien_tai)` ở **tầng router**, nên endpoint mới thêm vào đó tự động có
kiểm quyền, không ai quên được. Nếu để `/auth/login` chung file thì phải khoét một lỗ miễn
trừ — và lỗ miễn trừ là thứ về sau người ta vô tình mở rộng.

## Cổng đăng ký

`POST /auth/register` đòi **khoá chung** (`X-API-Key`, slice A). Nếu không, ai trên internet
cũng tự tạo tài khoản rồi dùng hạ tầng của mình. Khoá chung từ nay chỉ còn đúng nhiệm vụ này:
phát tài khoản. Nó không còn mở được dữ liệu.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.bao_ve import cong_khoa
from app.core.db import get_session
from app.core.phien import han_moi
from app.core.quyen import TIEN_TO_BEARER, nguoi_dung_hien_tai
from app.models import NguoiDung
from app.schemas.common import (
    DangKyRequest,
    DangNhapRequest,
    DangNhapResponse,
    NguoiDungRead,
)
from app.services import tai_khoan

router = APIRouter(prefix="/auth", tags=["auth"])

#: Cùng một câu cho "email không tồn tại", "sai mật khẩu" và "tài khoản bị khoá".
#: Phân biệt ra là xác nhận cho người dò biết email nào có thật.
LOI_SAI_THONG_TIN = "Email hoặc mật khẩu không đúng."


@router.post(
    "/register",
    response_model=NguoiDungRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(cong_khoa)],
)
async def dang_ky(
    payload: DangKyRequest, session: AsyncSession = Depends(get_session)
) -> NguoiDung:
    """Tạo tài khoản. Đòi khoá chung. Người đầu tiên đăng ký thành quản trị."""
    try:
        return await tai_khoan.dang_ky(
            session,
            email=payload.email,
            ten_hien=payload.ten_hien,
            mat_khau_tho=payload.mat_khau,
        )
    except ValueError as exc:
        thong_bao = (
            "Email này đã có tài khoản."
            if str(exc) == "email_da_ton_tai"
            else str(exc)
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=thong_bao) from exc


@router.post("/login", response_model=DangNhapResponse)
async def dang_nhap(
    payload: DangNhapRequest, session: AsyncSession = Depends(get_session)
) -> DangNhapResponse:
    ket_qua = await tai_khoan.dang_nhap(
        session, email=payload.email, mat_khau_tho=payload.mat_khau
    )
    if ket_qua is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=LOI_SAI_THONG_TIN
        )
    nguoi, ma_tho = ket_qua
    return DangNhapResponse(
        ma_phien=ma_tho, het_han=han_moi(), nguoi_dung=NguoiDungRead.model_validate(nguoi)
    )


# `response_class=Response`: 204 theo chuẩn HTTP là "không có thân", FastAPI mặc định
# gắn JSONResponse nên phải nói rõ.
@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    # `response_model=None` bắt buộc: FastAPI suy response model từ chú thích `-> None` thành
    # kiểu NoneType, rồi tự chặn vì 204 không được có thân.
    response_model=None,
)
async def dang_xuat(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Thu hồi phiên. **Luôn trả 204**, kể cả mã sai.

    Trả lỗi khi mã sai không giúp gì cho người dùng (họ muốn đăng xuất, và họ đã đăng xuất) mà
    lại cho người dò biết mã nào có thật.
    """
    if authorization and authorization.startswith(TIEN_TO_BEARER):
        await tai_khoan.dang_xuat(session, authorization[len(TIEN_TO_BEARER):].strip())


@router.get("/me", response_model=NguoiDungRead)
async def toi_la_ai(nguoi: NguoiDung = Depends(nguoi_dung_hien_tai)) -> NguoiDung:
    """Giao diện gọi lúc mở app để biết mã phiên lưu trong máy còn dùng được không."""
    return nguoi


@router.get("/co-tai-khoan-chua", response_model=dict)
async def co_tai_khoan_chua(session: AsyncSession = Depends(get_session)) -> dict:
    """Hệ thống đã có tài khoản nào chưa — để giao diện biết hiện màn "đăng nhập" hay
    "tạo tài khoản đầu tiên".

    Chỉ trả về true/false, **không** trả số lượng hay danh sách email: đó là thông tin về hệ
    thống mà người chưa đăng nhập không cần biết.
    """
    return {"da_co": await tai_khoan.dem_nguoi_dung(session) > 0}
