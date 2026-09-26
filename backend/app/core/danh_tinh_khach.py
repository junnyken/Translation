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
    #: Ai đang gọi, dùng cho phân quyền dữ liệu.
    #:
    #: Gộp chung vào ĐÂY thay vì một dependency thứ hai là có chủ đích: hai dependency riêng có
    #: thể **bất đồng** — tính hạn mức cho khách trong khi đọc dữ liệu với tư cách người đăng
    #: nhập, hoặc ngược lại. Một nguồn thì không có cửa đó.
    #:
    #: Mặc định là `NguoiGoi()` rỗng — người gọi không có tài khoản và không có mã khách, tức
    #: **không thấy gì**. Hỏng kiểu fail-closed: chỗ nào quên gán thì mất quyền, không phải được
    #: quyền.
    nguoi_goi: NguoiGoi = field(default_factory=NguoiGoi)

    @property
    def tran_hien(self) -> int:
        """Trần ĐEM HIỆN cho người dùng.

        Là trần của chốt đầu (tài khoản, hoặc cookie) — không phải trần IP. Trần IP là hàng rào
        chống lạm dụng dùng chung, hiện nó lên chỉ làm người dùng bối rối vì con số không khớp
        với thứ họ thật sự được dùng.
        """
        return self.chot[0].tran if self.chot else 0


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
    """
    ma_cookie = request.cookies.get(TEN_COOKIE)
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
    ma = ma_phien_tu_header(authorization)
    nguoi = await tai_khoan.lay_theo_ma_phien(session, ma) if ma else None
    if nguoi is not None:
        return DanhTinhHanMuc(
            co_tai_khoan=True,
            chot=(Chot(LoaiChuThe.nguoi_dung, str(nguoi.id), han_muc_cho(True)),),
            nguoi_goi=NguoiGoi(nguoi=nguoi),
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
