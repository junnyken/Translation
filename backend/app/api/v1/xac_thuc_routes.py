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
import uuid

from sqlalchemy import delete, select

from app.models import NguoiDung, Phien
from app.schemas.common import (
    DangKyRequest,
    DoiTrangThaiRequest,
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


# ---------------- quản trị người dùng ----------------
#
# Vì sao cần: không có phần này thì "cho người khác dùng" là con đường một chiều — phát tài
# khoản ra được nhưng **không thu lại được**. Muốn khoá một người phải sửa tay trong CSDL, mà
# CSDL trên bản chạy thật thì không phải lúc nào cũng với tới.


async def quan_tri_hien_tai(
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> NguoiDung:
    """Chỉ quản trị. Không phải quản trị ⇒ **404**, không phải 403.

    Cùng lý do như quyền sở hữu chapter: 403 xác nhận "có endpoint này và nó có thật", tức là
    nói cho người dò biết hệ thống có phần quản trị để mà nhắm vào.
    """
    if not nguoi.la_quan_tri:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy.")
    return nguoi


@router.get("/users", response_model=list[NguoiDungRead])
async def danh_sach_nguoi_dung(
    session: AsyncSession = Depends(get_session),
    _: NguoiDung = Depends(quan_tri_hien_tai),
) -> list[NguoiDung]:
    """Danh bạ tài khoản. **Chỉ quản trị** — với người thường, ai đang dùng hệ thống này không
    phải việc của họ."""
    return list(
        (await session.execute(select(NguoiDung).order_by(NguoiDung.created_at))).scalars()
    )


@router.patch("/users/{nguoi_id}", response_model=NguoiDungRead)
async def doi_trang_thai_nguoi_dung(
    nguoi_id: uuid.UUID,
    payload: DoiTrangThaiRequest,
    session: AsyncSession = Depends(get_session),
    quan_tri: NguoiDung = Depends(quan_tri_hien_tai),
) -> NguoiDung:
    """Khoá/mở khoá, và phong/thu quyền quản trị.

    Khoá là cách đúng để cho ai đó nghỉ — **không** phải xoá: xoá sẽ làm mọi chapter của họ
    thành vô chủ.

    Không đụng được vào chính mình (409): tự khoá hoặc tự thu quyền của mình là tự đẩy mình ra
    ngoài, và nếu đây là quản trị duy nhất thì không còn ai sửa lại được.
    """
    if nguoi_id == quan_tri.id:
        # Tự khoá hoặc tự thu quyền của mình là tự đẩy mình ra ngoài, và nếu đây là quản trị
        # duy nhất thì không còn ai sửa lại được.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Không tự khoá hay tự thu quyền của chính mình được.",
        )
    muc_tieu = await session.get(NguoiDung, nguoi_id)
    if muc_tieu is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy.")
    if payload.dang_hoat_dong is None and payload.la_quan_tri is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Không có gì để đổi.",
        )
    if payload.la_quan_tri is not None:
        muc_tieu.la_quan_tri = payload.la_quan_tri
    if payload.dang_hoat_dong is not None:
        muc_tieu.dang_hoat_dong = payload.dang_hoat_dong
    if payload.dang_hoat_dong is False:
        # Khoá tài khoản mà để phiên cũ sống tiếp là khoá trên giấy: người đó vẫn thao tác bình
        # thường cho tới khi phiên hết hạn (tối đa 14 ngày).
        await session.execute(delete(Phien).where(Phien.nguoi_dung_id == nguoi_id))
    await session.commit()
    await session.refresh(muc_tieu)
    return muc_tieu


@router.delete(
    "/users/{nguoi_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
async def xoa_nguoi_dung(
    nguoi_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    quan_tri: NguoiDung = Depends(quan_tri_hien_tai),
) -> None:
    """Xoá hẳn một tài khoản.

    **Chapter của họ KHÔNG bị xoá theo** — khoá ngoại là `ON DELETE SET NULL`, nên chapter trở
    về "chưa có chủ" và người khác nhận được. Xoá kèm chapter sẽ là xoá việc của người khác chỉ
    vì gỡ một tài khoản.

    Muốn giữ nguyên chủ sở hữu thì **khoá** (`PATCH`) chứ đừng xoá.
    """
    if nguoi_id == quan_tri.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Không tự xoá tài khoản của chính mình được.",
        )
    muc_tieu = await session.get(NguoiDung, nguoi_id)
    if muc_tieu is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy.")
    await session.delete(muc_tieu)
    await session.commit()
