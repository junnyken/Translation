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
from app.services.han_muc_dang_nhap import da_sai_bao_nhieu, ghi_nhan_dang_nhap_sai
from app.core.db import get_session
from app.core.phien import han_moi
from app.core.quyen import (
    LOI_CAM_API_KEY_NHAY_CAM,
    TIEN_TO_BEARER,
    la_khoa_api_developer,
    ma_phien_tu_header,
    nguoi_dung_hien_tai,
    nguoi_dung_phien_dang_nhap,
)
import hashlib
import hmac
import logging
import secrets
import time
import urllib.parse
import uuid

import httpx
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
from app.services.nhat_ky_quan_tri import ghi_nhat_ky

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

#: Cùng một câu cho "email không tồn tại", "sai mật khẩu" và "tài khoản bị khoá".
#: Phân biệt ra là xác nhận cho người dò biết email nào có thật.
LOI_SAI_THONG_TIN = "Email hoặc mật khẩu không đúng."

_THOI_HAN_THACH_THUC_GIAY = 600
#: Số bit 0 đầu của sha256 mà lời giải PoW phải đạt: ~65 nghìn lượt băm, 1-2 giây trên trình duyệt.
_DO_KHO_POW_BIT = 16
#: Khoá Cloudflare Turnstile chính thức của hệ thống comic.io.vn.
_CF_TURNSTILE_SITE_KEY_MAC_DINH = "0x4AAAAAAFjgaHej0056M8hW"


def _khoa_ky_thach_thuc(settings: Settings) -> bytes:
    from app.core.config import lay_khoa_bi_mat_noi_bo

    return lay_khoa_bi_mat_noi_bo(settings, nhan="anti-bot")


def _ky_thach_thuc(iat: int, nonce: str, dap_an: str, settings: Settings) -> str:
    thong_diep = f"{iat}:{nonce}:{dap_an}".encode("utf-8")
    return hmac.new(_khoa_ky_thach_thuc(settings), thong_diep, hashlib.sha256).hexdigest()[:32]


def _tao_ma_thach_thuc_pow(settings: Settings) -> str:
    """Sinh mã thách thức chống Bot có chữ ký HMAC-SHA256 (hiệu lực 10 phút) dùng cho Tiện ích Chrome, App Windows và tên miền dự phòng."""
    iat = int(time.time())
    nonce = secrets.token_hex(8)
    chu_ky = _ky_thach_thuc(iat, nonce, "pow-v1", settings)
    return f"{iat}.{nonce}.{chu_ky}"


def _so_bit_0_dau(du_lieu: bytes) -> int:
    dem = 0
    for b in du_lieu:
        if b == 0:
            dem += 8
            continue
        return dem + 8 - b.bit_length()
    return dem


def _kiem_tra_ma_thach_thuc_pow(
    ma_thach_thuc: str | None, dap_an: str | None, settings: Settings
) -> str | None:
    """Kiểm mã thách thức (chữ ký + hạn 10 phút) VÀ lời giải proof-of-work.

    Trả `nonce` của mã khi hợp lệ (để giữ suất đăng ký theo đúng mã này — mỗi mã một lần),
    hoặc None. Lời giải: chuỗi số `dap_an` sao cho `sha256("<mã>:<dap_an>")` có ít nhất
    `_DO_KHO_POW_BIT` bit 0 ở đầu. Trước đây mã có chữ ký là ĐỦ để qua — tức không có "work"
    nào cả, bot chỉ cần GET rồi POST.
    """
    ma = (ma_thach_thuc or "").strip()
    phan = ma.split(".")
    if len(phan) != 3:
        return None
    iat_str, nonce, chu_ky = phan
    if not iat_str.isdigit() or not nonce:
        return None
    iat = int(iat_str)
    hien_tai = int(time.time())
    if hien_tai - iat > _THOI_HAN_THACH_THUC_GIAY or iat > hien_tai + 60:
        return None
    ky_mong_doi = _ky_thach_thuc(iat, nonce, "pow-v1", settings)
    if not hmac.compare_digest(chu_ky, ky_mong_doi):
        return None
    dap = (dap_an or "").strip()
    if not dap.isdigit() or len(dap) > 20:
        return None
    bam_dap_an = hashlib.sha256(f"{ma}:{dap}".encode("ascii")).digest()
    if _so_bit_0_dau(bam_dap_an) < _DO_KHO_POW_BIT:
        return None
    return nonce


async def _xac_thuc_cloudflare_turnstile(
    token: str | None, ip: str | None, settings: Settings
) -> str | None:
    """Xác thực token Cloudflare Turnstile với máy chủ `challenges.cloudflare.com`."""
    if not token or not token.strip():
        return "Vui lòng hoàn thành bước xác thực Cloudflare (Verify you are human) trước khi tạo tài khoản."
    # KHÔNG có khoá mặc định trong mã (repo công khai). Thiếu biến môi trường ⇒ từ chối, không lặng lẽ chạy.
    secret = settings.cloudflare_turnstile_secret_key.strip()
    if not secret:
        logger.error("Chưa đặt CLOUDFLARE_TURNSTILE_SECRET_KEY — đăng ký qua Turnstile bị từ chối")
        return "Cổng xác thực chưa được cấu hình. Vui lòng liên hệ người quản trị."
    du_lieu = {"secret": secret, "response": token.strip()}
    if ip:
        du_lieu["remoteip"] = ip
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data=du_lieu,
            )
            kq = r.json()
            if not kq.get("success"):
                return "Xác thực Cloudflare chưa hợp lệ hoặc đã hết hạn. Vui lòng tích lại vào ô xác thực Cloudflare."
            return None
    except Exception as exc:
        logger.warning("Lỗi kết nối Cloudflare Turnstile siteverify: %s", exc)
        return "Không kết nối được cổng xác thực Cloudflare. Vui lòng thử lại sau giây lát."


@router.get("/thach-thuc-bot")
async def lay_thach_thuc_bot(
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    """Trả cấu hình xác thực Cloudflare Turnstile kèm mã chữ ký chống Bot dự phòng (`ma_thach_thuc`)."""
    site_key = settings.cloudflare_turnstile_site_key.strip() or _CF_TURNSTILE_SITE_KEY_MAC_DINH
    return {
        "turnstile_site_key": site_key,
        "yeu_cau_xac_nhan_email": False,
        "ma_thach_thuc": _tao_ma_thach_thuc_pow(settings),
        "do_kho_pow": _DO_KHO_POW_BIT,
    }


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
    ly_do_email = tai_khoan.kiem_email_hop_le_chong_spam(payload.email)
    if ly_do_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ly_do_email)

    dau_tien = await tai_khoan.dem_nguoi_dung(session) == 0
    bat_buoc_chong_bot = False
    nonce_pow: str | None = None
    if dau_tien:
        await cong_khoa(x_api_key)
    else:
        ua = request.headers.get("user-agent", "")
        co_origin = bool(request.headers.get("origin"))
        bat_buoc_chong_bot = (
            settings.app_env == "prod"
            or payload.cf_turnstile_token is not None
            or payload.ma_thach_thuc is not None
            or co_origin
            or ua.startswith("Mozilla/")
        )
        ip = ip_cua(request, settings)
        if bat_buoc_chong_bot:
            # Có token Turnstile ⇒ token đó PHẢI đúng; sai là từ chối, không có đường lùi sang PoW.
            # Không có token (tiện ích, Turnstile không tải được) ⇒ PoW thật, mỗi mã một lần.
            if payload.cf_turnstile_token:
                loi_cf = await _xac_thuc_cloudflare_turnstile(payload.cf_turnstile_token, ip, settings)
                if loi_cf:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=loi_cf)
            else:
                nonce_pow = _kiem_tra_ma_thach_thuc_pow(
                    payload.ma_thach_thuc, payload.dap_an_thach_thuc, settings
                )
                if nonce_pow is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Vui lòng hoàn thành bước xác thực Cloudflare (Verify you are human) "
                        "trước khi tạo tài khoản.",
                    )
        if ip is None and not bat_buoc_chong_bot:
            # Không xác định được địa chỉ mạng ⇒ KHÔNG mở cửa tự do. Thà chặn còn hơn để đường
            # tạo tài khoản không có trần nào — đó là đường vô hiệu hoá hạn mức.
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Chưa xác định được địa chỉ mạng của bạn nên tạm thời không mở đăng ký "
                "tự do. Liên hệ người quản trị để được cấp tài khoản.",
            )
        if ip is not None:
            tran = settings.so_tai_khoan_moi_moi_ip_mot_ngay
            kq = await giu_suat_dang_ky(
                session, ip_da_bam=bam(ip, settings), ngay=ngay_han_muc(), tran=tran,
                ma_mot_lan=f"pow:{nonce_pow}" if nonce_pow else None,
            )
            if kq.da_co_san:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Mã xác minh chống bot đã được dùng. Tải lại trang rồi thử lại.",
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
                        "thong_diep": "Địa chỉ mạng này đã tạo đủ số tài khoản cho phép trong hôm "
                        "nay. Thử lại sau, hoặc liên hệ người quản trị.",
                    },
                )

    try:
        nguoi = await tai_khoan.dang_ky(
            session,
            email=payload.email,
            ten_hien=payload.ten_hien,
            mat_khau_tho=payload.mat_khau,
            dang_hoat_dong=True,
        )
    except ValueError as exc:
        await session.rollback()
        thong_bao = (
            "Email này đã có tài khoản."
            if str(exc) == "email_da_ton_tai"
            else str(exc)
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=thong_bao) from exc

    return nguoi


@router.post("/login", response_model=DangNhapResponse)
async def dang_nhap(
    payload: DangNhapRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> DangNhapResponse:
    tran = settings.so_lan_dang_nhap_sai_moi_ip_mot_ngay
    ip = ip_cua(request, settings) if tran > 0 else None
    ip_bam = bam(ip, settings) if ip is not None else None
    ngay = ngay_han_muc() if ip_bam is not None else None

    if ip_bam is not None and ngay is not None:
        if await da_sai_bao_nhieu(session, ip_bam, ngay) >= tran:
            reset = moc_reset_ke_tiep()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(max(0, int((reset - bay_gio()).total_seconds())))},
                detail={
                    "loi": "vuot_tran_dang_nhap_sai",
                    "tran_moi_ngay": tran,
                    "reset_luc": reset.isoformat(),
                    "thong_diep": "Quá nhiều lần đăng nhập sai từ địa chỉ mạng này trong hôm nay. "
                    "Vui lòng thử lại sau.",
                },
            )

    ket_qua = await tai_khoan.dang_nhap(
        session, email=payload.email, mat_khau_tho=payload.mat_khau
    )
    if ket_qua is None:
        if ip_bam is not None and ngay is not None:
            await ghi_nhan_dang_nhap_sai(
                session, ip_da_bam=ip_bam, ngay=ngay, tran=tran
            )
            await session.commit()
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
    x_customer_api_key: str | None = Header(default=None, alias="X-Customer-Api-Key"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
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
    ma_xac_thuc = ma_phien_tu_header(authorization, x_customer_api_key, x_api_key)

    if payload.mat_khau_moi:
        if la_khoa_api_developer(ma_xac_thuc):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=LOI_CAM_API_KEY_NHAY_CAM,
            )
        ly_do, so_thu_hoi = await tai_khoan.doi_mat_khau(
            session,
            nguoi=nguoi,
            mat_khau_cu=payload.mat_khau_cu or "",
            mat_khau_moi=payload.mat_khau_moi,
            giu_ma_phien_tho=ma_xac_thuc,
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


@router.get("/api-key", response_model=dict)
async def xem_trang_thai_api_key(
    session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> dict:
    """Kiểm tra trạng thái Developer API Key (`tr_live_...`) của tài khoản hiện tại."""
    ban_ghi = await tai_khoan.lay_thong_tin_api_key(session, nguoi.id)
    if ban_ghi is None:
        return {
            "co_api_key": False,
            "tao_luc": None,
            "dung_lan_cuoi": None,
            "het_han": None,
        }
    return {
        "co_api_key": True,
        "tao_luc": ban_ghi.created_at.isoformat() if ban_ghi.created_at else None,
        "dung_lan_cuoi": ban_ghi.dung_lan_cuoi.isoformat() if ban_ghi.dung_lan_cuoi else None,
        "het_han": ban_ghi.het_han.isoformat() if ban_ghi.het_han else None,
    }


@router.post("/api-key", response_model=dict, status_code=status.HTTP_201_CREATED)
async def tao_hoac_doi_api_key(
    session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_phien_dang_nhap),
) -> dict:
    """Tạo mới hoặc xoay (rotate) Developer API Key (`tr_live_...`) cho tài khoản hiện tại.
    Mã thô chỉ trả về ĐÚNG MỘT LẦN trong phản hồi này để khách hàng copy vào tool riêng.
    Bắt buộc dùng phiên đăng nhập tương tác (không cho phép dùng chính `tr_live_...` để tự xoay khoá).
    """
    ma_tho, ban_ghi = await tai_khoan.tao_moi_api_key(session, nguoi.id)
    return {
        "api_key": ma_tho,
        "co_api_key": True,
        "tao_luc": ban_ghi.created_at.isoformat() if ban_ghi.created_at else None,
        "dung_lan_cuoi": None,
        "thong_diep": "Đã tạo Developer API Key mới. Hãy sao chép và lưu lại ngay — mã đầy đủ chỉ hiển thị một lần này.",
    }


@router.delete("/api-key", response_model=dict)
async def xoa_api_key_cua_toi(
    session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_phien_dang_nhap),
) -> dict:
    """Thu hồi ngay lập tức Developer API Key của tài khoản."""
    so_xoa = await tai_khoan.thu_hoi_api_key(session, nguoi.id)
    return {
        "da_thu_hoi": so_xoa > 0,
        "co_api_key": False,
        "thong_diep": "Đã thu hồi Developer API Key. Mọi tool dùng key cũ sẽ bị từ chối ngay lập tức.",
    }


# ---------------- quản trị người dùng ----------------
#
# Vì sao cần: không có phần này thì "cho người khác dùng" là con đường một chiều — phát tài
# khoản ra được nhưng **không thu lại được**. Muốn khoá một người phải sửa tay trong CSDL, mà
# CSDL trên bản chạy thật thì không phải lúc nào cũng với tới.


async def quan_tri_hien_tai(
    authorization: str | None = Header(default=None),
    x_customer_api_key: str | None = Header(default=None, alias="X-Customer-Api-Key"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> NguoiDung:
    """Chỉ quản trị. Không phải quản trị ⇒ **404**, không phải 403.

    Cùng lý do như quyền sở hữu chapter: 403 xác nhận "có endpoint này và nó có thật", tức là
    nói cho người dò biết hệ thống có phần quản trị để mà nhắm vào.
    Đồng thời chặn việc dùng Developer API Key (`tr_live_...`) để thực thi thao tác quản trị.
    """
    if not nguoi.la_quan_tri:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy.")
    ma = ma_phien_tu_header(authorization, x_customer_api_key, x_api_key)
    if la_khoa_api_developer(ma):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=LOI_CAM_API_KEY_NHAY_CAM,
        )
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
    ghi_nhat_ky(session, quan_tri, "doi_trang_thai_nguoi_dung", muc_tieu.email,
                dang_hoat_dong=payload.dang_hoat_dong, la_quan_tri=payload.la_quan_tri)
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
    về "chưa có chủ" — chỉ quản trị thấy và nhận lại được. Xoá kèm chapter sẽ là xoá việc của người khác chỉ
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
    ghi_nhat_ky(session, quan_tri, "xoa_nguoi_dung", muc_tieu.email)
    await session.delete(muc_tieu)
    await session.commit()
