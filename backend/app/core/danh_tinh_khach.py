"""Nhận diện CHỦ THỂ của hạn mức — người đăng nhập, hoặc khách lạ qua cookie + IP.

## Vì sao khách lạ cần HAI chốt chứ không một

Cookie nhận ra trình duyệt, nhưng xoá cookie là việc một cú bấm. Nếu cookie là chốt duy nhất thì
hạn mức chỉ còn là gợi ý. IP là chốt thứ hai: xoá cookie xong vẫn còn IP chặn.

Ngược lại, IP **một mình cũng không đủ**: văn phòng, trường học, quán cà phê dùng chung một IP.
Nên trần IP phải **cao hơn** trần cookie (`han_muc_ip_khach_la` > `han_muc_khach_la`), và request
phải lọt qua **cả hai** chốt mới được chạy.

## Vì sao băm, và vì sao muối rỗng là chuyện đáng ồn ào

Sổ cái chỉ cần biết "có phải cùng một người không", không cần biết người đó ở đâu. Lưu IP thô là
giữ dữ liệu cá nhân không dùng tới.

Nhưng **băm không muối thì gần như không băm**: cả không gian IPv4 chỉ có ~4,3 tỉ địa chỉ, dựng
bảng tra SHA-256 cho toàn bộ là chuyện vài phút. Vì vậy muối rỗng được ghi WARNING chứ không âm
thầm chạy tiếp — đây đúng là kiểu "lặng lẽ lùi về đường cũ" mà dự án cấm.

## Vì sao KHÔNG tin `X-Forwarded-For` theo mặc định

Header đó do client gửi. Tin nó khi chưa có proxy ghi đè nghĩa là ai cũng tự đặt "IP" của mình
thành giá trị ngẫu nhiên mỗi lần gọi ⇒ chốt IP biến mất mà không ai thấy. Phải bật tường minh
bằng `tin_header_proxy`, và chỉ khi proxy thật sự ghi đè header.

## Cookie chứa gì

Một mã ngẫu nhiên, **không** chứa số lượt. Số lượt nằm trong sổ cái phía máy chủ; để ở cookie thì
client sửa được. Cookie đặt `HttpOnly` (JavaScript không đọc được) · `SameSite=Lax` · `Secure`
(cấu hình được, xem `cookie_khach_secure`).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass, field

from fastapi import Depends, Header, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.quyen import NguoiGoi, ma_phien_tu_header
from app.models.enums import LoaiChuThe
from app.services import tai_khoan
from app.services.han_muc import han_muc_cho

log = logging.getLogger(__name__)

TEN_COOKIE = "ma_khach"

TEN_CAP_DO = {
    0: "Free",
    1: "Trial",
    2: "Starter",
    3: "Pro",
    4: "Studio",
    5: "Unlimited",
}

_CAP_DO_GOI_MEM_CACHE: dict[str, int] = {}
_DA_NAP_CAP_DO_GOI = False


def cap_do_tu_ma_goi(ma_goi: str, so_trang_don: int = 0) -> int:
    """Xác định cấp độ VIP (1..5) của ĐƠN GÓI CƯỚC mà khách vừa mua.

    Đảm bảo:
    - Khách mua gói nào thì hưởng đúng cấp độ của gói đó suốt thời gian còn lượt (không bị tụt hạng
      khi đang xài dở từ 5.000 trang xuống 3.000 trang, hay từ 600 trang xuống 200 trang).
    - Khách chỉ mua lặp lại gói thấp (Trial 19k / Starter 49k) thì chỉ ở Cấp 1 / Cấp 2, KHÔNG thể
      lách để mở khoá tính năng Pro (99k) hay Unlimited API (399k).
    """
    ma = (ma_goi or "").strip().lower()
    if ma in ("unlimited_plan", "doanh_nghiep_api", "enterprise_scale") or so_trang_don >= 5000:
        return 5
    if ma in ("studio_monthly", "pack_2000", "nhom_dich") or so_trang_don >= 1200:
        return 4
    if ma in ("pro_monthly", "tieu_chuan") or so_trang_don >= 500:
        return 3
    if ma in ("starter_monthly", "co_ban") or so_trang_don >= 100:
        return 2
    if ma in ("trial_pack_50", "goi_moi") or so_trang_don > 0:
        return 1
    return 0


def _nap_cache_cap_do_goi() -> dict[str, int]:
    global _DA_NAP_CAP_DO_GOI
    if _DA_NAP_CAP_DO_GOI:
        return _CAP_DO_GOI_MEM_CACHE
    import json
    from pathlib import Path

    data: dict[str, int] = {}
    try:
        p = Path("/tmp/cap_do_goi_khach.json")
        if p.is_file():
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data.update({str(k): int(v or 0) for k, v in raw.items()})
    except Exception:
        pass
    if not data:
        try:
            from app.services.storage import get_storage

            st = get_storage()
            raw_bytes = st.read("quan_tri/cap_do_goi_khach.json")
            if raw_bytes:
                raw = json.loads(raw_bytes.decode("utf-8"))
                if isinstance(raw, dict):
                    data.update({str(k): int(v or 0) for k, v in raw.items()})
        except Exception:
            pass
    _CAP_DO_GOI_MEM_CACHE.update(data)
    _DA_NAP_CAP_DO_GOI = True
    return _CAP_DO_GOI_MEM_CACHE


def ghi_nhan_cap_do_goi_mua(
    nguoi_id, ma_goi: str, so_trang_don: int = 0, so_luot_con_lai_truoc_do: int = 0
) -> int:
    """Lưu cấp độ gói khách vừa mua.

    - Nếu khách vẫn còn lượt của gói cao hơn trước đó (`so_luot_con_lai_truoc_do > 0`), giữ cấp cao nhất
      giữa gói cũ và gói mới.
    - Nếu khách đã dùng hết sạch lượt cũ (`so_luot_con_lai_truoc_do <= 0`), áp đúng cấp của gói mới mua.
    """
    import json
    from pathlib import Path

    uid_str = str(nguoi_id or "").strip()
    if not uid_str:
        return 0
    cache = _nap_cache_cap_do_goi()
    cap_moi = cap_do_tu_ma_goi(ma_goi, so_trang_don)
    cap_cu = int(cache.get(uid_str, 0) or 0) if so_luot_con_lai_truoc_do > 0 else 0
    cap_chot = max(cap_cu, cap_moi)
    cache[uid_str] = cap_chot

    raw_bytes = json.dumps(cache, ensure_ascii=False).encode("utf-8")
    try:
        Path("/tmp/cap_do_goi_khach.json").write_bytes(raw_bytes)
    except Exception:
        pass
    try:
        from app.services.storage import get_storage

        get_storage().save("quan_tri/cap_do_goi_khach.json", raw_bytes)
    except Exception:
        pass
    return cap_chot


def tinh_cap_do(nguoi) -> int:
    """Tính cấp độ VIP (0..5) dựa trên quyền quản trị, trần ngày riêng và GÓI CƯỚC ĐÃ MUA.

    1. KHÔNG BỊ HẠ HẠNG GIỮA CHỪNG:
       - Khách mua gói Unlimited (5.000 trang), dùng xuống còn 3.000 trang hay 10 trang vẫn giữ nguyên
         Cấp 5 (Unlimited) cho đến khi dùng hết sạch về 0 trang.
       - Khách mua gói Pro (600 trang), dùng xuống còn 200 trang hay 5 trang vẫn giữ nguyên
         Cấp 3 (Pro) cho đến khi dùng hết sạch về 0 trang.
    2. CHỐNG LÁCH BẰNG GÓI THẤP:
       - Khách chỉ mua gói Trial (19k) hoặc Starter (49k) nhiều lần thì `cap_goi_da_mua` chỉ là
         Cấp 1 (Trial) hoặc Cấp 2 (Starter) — muốn mở khoá tính năng Pro (99k) hoặc Unlimited API (399k)
         bắt buộc phải mua đúng gói Pro / Studio / Unlimited.
    """
    if nguoi is None:
        return 0
    if getattr(nguoi, "la_quan_tri", False):
        return 5  # Admin = Unlimited
    tran = int(getattr(nguoi, "tran_hang_ngay_rieng", 0) or 0)
    vi = int(getattr(nguoi, "so_luot_mua_them", 0) or 0)

    cap_tran = 0
    if tran >= 5000:
        cap_tran = 5
    elif tran >= 2000:
        cap_tran = 4
    elif tran >= 600:
        cap_tran = 3
    elif tran >= 200:
        cap_tran = 2
    elif tran > 10:
        cap_tran = 1

    if vi <= 0:
        return cap_tran

    uid_str = str(getattr(nguoi, "id", "") or "").strip()
    cache = _nap_cache_cap_do_goi()
    cap_goi_da_mua = int(cache.get(uid_str, 0) or 0) if uid_str else 0
    if cap_goi_da_mua > 0:
        return max(cap_tran, cap_goi_da_mua)

    # Dự phòng cho tài khoản được cộng lượt trước khi có sổ lưu gói:
    if vi >= 3500:
        return max(cap_tran, 5)
    if vi >= 1200:
        return max(cap_tran, 4)
    if vi >= 300:
        return max(cap_tran, 3)
    if vi >= 100:
        return max(cap_tran, 2)
    return max(cap_tran, 1)


def ten_cap_do(cap: int) -> str:
    return TEN_CAP_DO.get(int(cap), "Free")


def loi_can_nang_cap(
    *,
    cap_hien_tai: int,
    cap_yeu_cau: int,
    tinh_nang: str,
    thong_bao: str,
):
    from fastapi import HTTPException

    ten_yc = ten_cap_do(cap_yeu_cau)
    return HTTPException(
        status_code=402,
        detail={
            "loi": "can_nang_cap",
            "cap_hien_tai": cap_hien_tai,
            "ten_cap_hien_tai": ten_cap_do(cap_hien_tai),
            "cap_yeu_cau": cap_yeu_cau,
            "ten_cap_yeu_cau": ten_yc,
            "tinh_nang": tinh_nang,
            "thong_bao": thong_bao,
            "thong_diep": thong_bao,
            "url_nang_cap": "https://comic.io.vn/#bang-gia",
        },
    )


#: Ghi WARNING muối rỗng đúng MỘT lần mỗi tiến trình. Mỗi request một dòng sẽ thành lụt log và
#: bị người đọc bỏ qua — đúng thứ làm cảnh báo mất tác dụng.
_da_canh_bao_muoi = False


@dataclass(frozen=True)
class Chot:
    """Một cổng phải lọt qua. Khách lạ có hai cổng, người đăng nhập có một."""

    loai: LoaiChuThe
    chu_the: str
    tran: int


@dataclass(frozen=True)
class DanhTinhHanMuc:
    """Chủ thể của hạn mức cho một request.

    `cookie_moi` khác `None` nghĩa là request này chưa mang cookie và ta vừa cấp một mã mới —
    nơi gọi phải gửi nó về bằng `Set-Cookie`, nếu không thì lần sau lại là "khách mới".
    """

    co_tai_khoan: bool
    chot: tuple[Chot, ...]
    cookie_moi: str | None = None
    nguoi_goi: NguoiGoi = field(default_factory=NguoiGoi)
    #: E100 — Số lượt nạp thêm (không hết hạn qua đêm) của tài khoản đã đăng nhập.
    so_luot_mua_them: int = 0

    @property
    def tran_hien(self) -> int:
        """Trần ĐEM HIỆN cho người dùng.

        Là trần của chốt đầu (tài khoản, hoặc cookie) — không phải trần IP. Trần IP là hàng rào
        chống lạm dụng dùng chung, hiện nó lên chỉ làm người dùng bối rối vì con số không khớp
        với thứ họ thật sự được dùng.
        """
        return self.chot[0].tran if self.chot else 0

    @property
    def cap_do(self) -> int:
        """Cấp độ tài khoản (0=Free .. 5=Unlimited)."""
        if self.co_tai_khoan and not self.nguoi_goi.la_khach and self.nguoi_goi.nguoi is not None:
            return tinh_cap_do(self.nguoi_goi.nguoi)
        return 0

    @property
    def ten_cap_do(self) -> str:
        return ten_cap_do(self.cap_do)


def _muoi(settings: Settings) -> bytes:
    global _da_canh_bao_muoi
    muoi = settings.muoi_bam_khach
    if not muoi and not _da_canh_bao_muoi:
        _da_canh_bao_muoi = True
        log.warning(
            "MUOI_BAM_KHACH rỗng: định danh khách lạ đang băm KHÔNG muối. Toàn bộ không gian "
            "IPv4 băm hết chỉ mất vài phút, nên ai đọc được CSDL sẽ khôi phục lại được IP thô. "
            "Đặt biến môi trường MUOI_BAM_KHACH ở production."
        )
    return muoi.encode("utf-8")


def bam(gia_tri: str, settings: Settings) -> str:
    """Băm một định danh khách. HMAC-SHA256 rồi cắt còn 32 ký tự hex.

    Dùng HMAC chứ không phải `sha256(muoi + gia_tri)`: cách nối chuỗi thủ công dính lỗi kéo dài
    độ dài (length-extension), còn HMAC thì không — và nó không đắt hơn.

    Cắt 32 ký tự (128 bit) vẫn quá thừa để tránh đụng trùng, mà cột ngắn thì chỉ mục nhẹ hơn.
    """
    return hmac.new(_muoi(settings), gia_tri.encode("utf-8"), hashlib.sha256).hexdigest()[:32]


def ip_cua(request: Request, settings: Settings) -> str | None:
    """IP của người gọi. `None` khi không xác định được — nơi gọi phải xử lý, đừng đoán bừa.

    Lấy mục **trái nhất** của `X-Forwarded-For` (client gốc) và chỉ khi `tin_header_proxy` bật.
    """
    if settings.tin_header_proxy:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            dau = xff.split(",")[0].strip()
            if dau:
                return dau
    return request.client.host if request.client else None


def chot_cho_khach(request: Request, settings: Settings) -> tuple[tuple[Chot, ...], str | None]:
    """Dựng các chốt cho một khách lạ, kèm cookie mới nếu phải cấp.

    Không lấy được IP thì **chỉ còn chốt cookie** — và điều đó được ghi WARNING, vì lúc đó xoá
    cookie là vượt được hạn mức. Đây là hạ cấp có thật, không được im lặng.

    Ngoài cookie `ma_khach`, chấp nhận thêm header `X-Ma-Khach` (dài >= 16 ký tự) cho tiện ích mở
    rộng trình duyệt (`chrome-extension://`), nơi cookie `SameSite=Lax` không được trình duyệt đính
    kèm vào request `POST` chéo nguồn. Chốt IP vẫn luôn đi kèm nên không thể lách hạn mức.
    """
    ma_cookie = request.cookies.get(TEN_COOKIE)
    if not ma_cookie:
        ma_header = (
            request.headers.get("x-ma-khach")
            or request.query_params.get("ma_khach")
            or ""
        ).strip()
        if len(ma_header) >= 16:
            ma_cookie = ma_header
    cookie_moi = None
    if not ma_cookie:
        ma_cookie = secrets.token_urlsafe(24)
        cookie_moi = ma_cookie

    chot = [
        Chot(LoaiChuThe.khach_cookie, bam(ma_cookie, settings), settings.han_muc_khach_la)
    ]
    ip = ip_cua(request, settings)
    if ip:
        chot.append(
            Chot(LoaiChuThe.khach_ip, bam(ip, settings), settings.han_muc_ip_khach_la)
        )
    else:
        log.warning(
            "Không xác định được IP người gọi: hạn mức khách lạ chỉ còn chốt cookie, mà xoá "
            "cookie là vượt được. Kiểm lại cấu hình proxy."
        )
    return tuple(chot), cookie_moi


def dat_cookie_khach(response: Response, ma: str, settings: Settings) -> None:
    """Gửi cookie khách về. Tách hàm riêng để mọi nơi đặt cookie dùng chung một bộ cờ bảo mật."""
    response.set_cookie(
        TEN_COOKIE,
        ma,
        max_age=settings.cookie_khach_song_giay,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_khach_secure,
        path="/",
    )


async def danh_tinh_han_muc(
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_customer_api_key: str | None = Header(default=None, alias="X-Customer-Api-Key"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> DanhTinhHanMuc:
    """Dependency: ai đang gọi, và hạn mức của họ đo theo chốt nào.

    **Không ném 401.** Khác hẳn `nguoi_dung_hien_tai` — endpoint nào cho khách lạ vào thì dùng
    dependency này; endpoint nào bắt đăng nhập vẫn giữ `nguoi_dung_hien_tai` và dependency này
    chỉ nói thêm "hạn mức tính vào tài khoản nào".

    Cookie mới (nếu có) được gửi về **ngay tại đây**, kể cả khi request sau đó bị từ chối vì hết
    hạn mức: không cấp cookie cho request bị từ chối thì mỗi lần thử lại là một khách mới, và
    chốt cookie không bao giờ chạm trần.
    """
    ma = ma_phien_tu_header(authorization, x_customer_api_key, x_api_key)
    if not ma:
        q_key = (request.query_params.get("api_key") or "").strip()
        if q_key.startswith("tr_live_"):
            ma = q_key
    nguoi = await tai_khoan.lay_theo_ma_phien(session, ma) if ma else None
    if nguoi is None and (
        (ma and ma.startswith("tr_live_"))
        or bool(x_customer_api_key and x_customer_api_key.strip())
    ):
        # Chặn tuyệt đối việc giả mạo hoặc dùng Developer API Key (tr_live_...) đã bị thu hồi:
        # KHÔNG cho phép rớt âm thầm về chế độ khách vãng lai, đồng thời tính điểm chống dò khoá theo IP.
        from fastapi import HTTPException, status
        from app.services.han_muc import bay_gio, moc_reset_ke_tiep, ngay_han_muc
        from app.services.han_muc_dang_nhap import da_sai_bao_nhieu, ghi_nhan_dang_nhap_sai

        tran_sai = settings.so_lan_dang_nhap_sai_moi_ip_mot_ngay
        ip_k = ip_cua(request, settings) if tran_sai > 0 else None
        ip_bam_k = bam(ip_k, settings) if ip_k is not None else None
        ngay_k = ngay_han_muc() if ip_bam_k is not None else None
        if ip_bam_k is not None and ngay_k is not None:
            if await da_sai_bao_nhieu(session, ip_bam_k, ngay_k) >= tran_sai:
                reset_k = moc_reset_ke_tiep()
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    headers={"Retry-After": str(max(0, int((reset_k - bay_gio()).total_seconds())))},
                    detail="Quá nhiều lần gửi sai Developer API Key từ địa chỉ mạng này trong hôm nay.",
                )
            await ghi_nhan_dang_nhap_sai(session, ip_da_bam=ip_bam_k, ngay=ngay_k, tran=tran_sai)
            await session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Developer API Key (tr_live_...) không hợp lệ, bị giả mạo hoặc đã bị thu hồi.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if nguoi is not None:
        tran_ngay = (
            int(nguoi.tran_hang_ngay_rieng)
            if getattr(nguoi, "tran_hang_ngay_rieng", None) is not None
            else han_muc_cho(True)
        )
        luot_mua = max(0, int(getattr(nguoi, "so_luot_mua_them", 0) or 0))
        return DanhTinhHanMuc(
            co_tai_khoan=True,
            chot=(Chot(LoaiChuThe.nguoi_dung, str(nguoi.id), tran_ngay),),
            nguoi_goi=NguoiGoi(nguoi=nguoi),
            so_luot_mua_them=luot_mua,
        )

    chot, cookie_moi = chot_cho_khach(request, settings)
    if cookie_moi:
        dat_cookie_khach(response, cookie_moi, settings)
    return DanhTinhHanMuc(
        co_tai_khoan=False,
        chot=chot,
        cookie_moi=cookie_moi,
        # Mã khách = chốt cookie đã băm. Cố ý KHÔNG dùng chốt IP làm danh tính dữ liệu: cả văn
        # phòng dùng chung một IP, lấy nó làm chủ sở hữu là cho người này đọc truyện người kia.
        nguoi_goi=NguoiGoi(khach=chot[0].chu_the),
    )
