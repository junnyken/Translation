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

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.bao_ve import TEN_HEADER as TEN_HEADER_KHOA
from app.core.bao_ve import cong_khoa
from app.core.config import Settings, get_settings
from app.core.danh_tinh_khach import bam, ip_cua
from app.services.han_muc import bay_gio, moc_reset_ke_tiep, ngay_han_muc
from app.services.han_muc_dang_ky import giu_suat_dang_ky
from app.core.db import get_session
from app.core.phien import han_moi
from app.core.quyen import TIEN_TO_BEARER, ma_phien_tu_header, nguoi_dung_hien_tai
import uuid

from sqlalchemy import delete, select

from app.models import NguoiDung, Phien
from app.schemas.common import (
    DangKyRequest,
    DoiTrangThaiRequest,
    DangNhapRequest,
    DangNhapResponse,
    NguoiDungRead,
    SuaTaiKhoanRequest,
    SuaTaiKhoanResponse,
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
)
async def dang_ky(
    payload: DangKyRequest,
    request: Request,
    x_api_key: str | None = Header(default=None, alias=TEN_HEADER_KHOA),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> NguoiDung:
    """Tạo tài khoản.

    ## E52 — cổng khoá chung nay CÓ ĐIỀU KIỆN, không còn chặn mọi người

    Trước E52, đường này gắn `Depends(cong_khoa)` nên **người lạ không tự đăng ký được**. Điều đó
    trái §4.1 đặc tả ("đăng ký là thứ người dùng chọn khi muốn nhiều hơn, không phải cổng chặn ở
    cửa"): khách dùng hết 6 trang không có đường nào lên 10.

    Nay:

    * **chưa có tài khoản nào** ⇒ vẫn ĐÒI khoá chung. Tài khoản đầu tiên thành quản trị và nhận
      các chapter cũ chưa có chủ, nên để người lạ chiếm chỗ đó là giao quyền quản trị cho người
      bấm nhanh nhất;
    * **đã có tài khoản** ⇒ mở, nhưng chặn theo địa chỉ mạng (xem dưới).

    ## Vì sao PHẢI có trần theo IP

    Không có nó thì hạn mức trang của E49 **vô nghĩa**: khách hết 6 trang chỉ cần tạo tài khoản
    mới để có 10, lặp vô hạn. Mở đăng ký mà quên con số này là tự vô hiệu hoá cả E49.

    Suất chỉ mất khi tài khoản **thật sự** được tạo: hàng giữ suất nằm cùng phiên với lượt tạo,
    nên email trùng hay mật khẩu yếu ⇒ giao dịch huỷ ⇒ không mất suất. Cùng luật với "tệp hỏng
    không mất lượt" của đường tải lên.
    """
    dau_tien = await tai_khoan.dem_nguoi_dung(session) == 0
    if dau_tien:
        await cong_khoa(x_api_key)
    else:
        ip = ip_cua(request, settings)
        if ip is None:
            # Không xác định được địa chỉ mạng ⇒ KHÔNG mở cửa tự do. Thà chặn còn hơn để đường
            # tạo tài khoản không có trần nào — đó là đường vô hiệu hoá hạn mức.
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Chưa xác định được địa chỉ mạng của bạn nên tạm thời không mở đăng ký "
                "tự do. Liên hệ người quản trị để được cấp tài khoản.",
            )
        tran = settings.so_tai_khoan_moi_moi_ip_mot_ngay
        kq = await giu_suat_dang_ky(
            session, ip_da_bam=bam(ip, settings), ngay=ngay_han_muc(), tran=tran
        )
        if not kq.thanh_cong:
            reset = moc_reset_ke_tiep()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(max(0, int((reset - bay_gio()).total_seconds())))},
                detail={
                    "loi": "vuot_tran_dang_ky",
                    "tran_moi_ngay": tran,
                    "reset_luc": reset.isoformat(),
                    # Nói rõ là trần theo ĐỊA CHỈ MẠNG: người ở văn phòng/quán cà phê có thể bị
                    # chặn dù chính họ chưa tạo tài khoản nào, và không có cách nào tự đoán ra.
                    "thong_diep": "Địa chỉ mạng này đã tạo đủ số tài khoản cho phép trong hôm "
                    "nay. Thử lại sau, hoặc liên hệ người quản trị.",
                },
            )

    try:
        return await tai_khoan.dang_ky(
            session,
            email=payload.email,
            ten_hien=payload.ten_hien,
            mat_khau_tho=payload.mat_khau,
        )
    except ValueError as exc:
        # Lùi TƯỜNG MINH để trả lại suất đã giữ ở trên.
        #
        # Về nguyên tắc `get_session` đóng phiên khi request nổ và `AsyncSession.close()` tự lùi
        # giao dịch — nên ở bản chạy thật suất vẫn được trả lại dù không có dòng này. Nhưng:
        #
        # 1. Bảo đảm "lượt bị từ chối không mất suất" khi đó nằm ở **vòng đời của dependency**,
        #    cách xa chỗ đọc mã. Ai sửa phần cấp phiên sau này sẽ phá nó mà không biết.
        # 2. Bộ test ghi đè `get_session` bằng một phiên sống lâu, nên nó **không bao giờ quan sát
        #    được** phép lùi kia. Đo được 27-09: hai bài canh đúng luật này ĐỎ, và đỏ vì bàn thử
        #    không thấy được, chứ không phải vì sản phẩm sai.
        #
        # Lùi ngay tại đây làm bảo đảm thành thứ đọc được và kiểm được. `upload_archive` đã làm
        # đúng như vậy ở các nhánh lỗi của nó.
        await session.rollback()
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


@router.patch("/me", response_model=SuaTaiKhoanResponse)
async def sua_tai_khoan_cua_toi(
    payload: SuaTaiKhoanRequest,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> SuaTaiKhoanResponse:
    """Tự sửa tài khoản của mình: tên hiển thị và/hoặc mật khẩu (E56).

    ## Vì sao KHÔNG dùng `PATCH /users/{id}` có sẵn

    Đường đó là của **quản trị** và cố ý không nhận `ten_hien`/`mat_khau` — docstring của
    `DoiTrangThaiRequest` nói thẳng lý do: *"quản trị được phép chặn người khác, nhưng không được
    phép hoá trang thành họ"*. Nhét tên/mật khẩu vào đó là phá đúng nguyên tắc ấy. Nên đây là
    đường riêng, và nó **chỉ sửa được chính mình** — không có tham số `{id}` để nhắm vào ai khác.

    ## Đổi mật khẩu thu hồi các phiên KHÁC

    Trả về `so_phien_khac_da_thu_hoi` để giao diện nói ra hệ quả. Phiên đang gọi được **giữ lại**:
    đăng xuất chính người vừa đổi mật khẩu là hình phạt cho hành vi đúng. Lý do đầy đủ ở
    `services/tai_khoan.doi_mat_khau`.
    """
    so_thu_hoi = 0
    da_doi_mk = False

    if payload.mat_khau_moi:
        ly_do, so_thu_hoi = await tai_khoan.doi_mat_khau(
            session,
            nguoi=nguoi,
            mat_khau_cu=payload.mat_khau_cu or "",
            mat_khau_moi=payload.mat_khau_moi,
            giu_ma_phien_tho=ma_phien_tu_header(authorization),
        )
        if ly_do:
            # Rollback tường minh: `doi_mat_khau` trả lý do TRƯỚC khi commit, nhưng tên hiển thị
            # có thể đã được gán ở dưới trong một lượt gọi gửi cả hai. Đổi thứ tự (mật khẩu
            # TRƯỚC tên) là để một lượt bị từ chối không lưu nửa vời.
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=ly_do
            )
        da_doi_mk = True

    if payload.ten_hien is not None:
        nguoi = await tai_khoan.doi_ten_hien(session, nguoi=nguoi, ten_hien=payload.ten_hien)

    return SuaTaiKhoanResponse(
        nguoi_dung=NguoiDungRead.model_validate(nguoi),
        da_doi_mat_khau=da_doi_mk,
        so_phien_khac_da_thu_hoi=so_thu_hoi,
    )


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
