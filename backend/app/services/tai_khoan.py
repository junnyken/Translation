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

import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import mat_khau as mk
from app.core import phien as ph
from app.models import NguoiDung, Phien

#: Mật khẩu ngắn hơn ngưỡng này bị từ chối. 8 là mức tối thiểu NIST SP 800-63B.
DAI_MAT_KHAU_TOI_THIEU = 8
#: Chuỗi băm dùng để "đốt thời gian" khi email không tồn tại (xem quy tắc 2 ở docstring).
#: Băm sẵn một lần lúc nạp module, không phải mỗi request.
_BAM_GIA = mk.bam("khong-phai-mat-khau-cua-ai")

#: Mốc phân biệt phiên trình duyệt (14 ngày) với Developer API Key dài hạn (năm 2099).
MOC_NAM_API_KEY = datetime(2090, 1, 1, tzinfo=timezone.utc)
HAN_API_KEY = datetime(2099, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
TIEN_TO_API_KEY = "tr_live_"

#: Danh sách tên miền email 10 phút / email tạm thời / email rác bị chặn khi đăng ký tài khoản.
MIEN_EMAIL_RAC_10_PHUT: frozenset[str] = frozenset({
    "10minutemail.com", "10minutemail.net", "10minutemail.org", "10minutemail.co.uk",
    "10minutemail.de", "10minutemail.be", "10minutemail.cf", "10minutemail.ga",
    "10minutemail.gq", "10minutemail.ml", "10minutemail.tk", "10minutemail.us",
    "10mail.org", "10minmail.com", "10mail.tk", "20minutemail.com", "20minutemail.it",
    "temp-mail.org", "temp-mail.io", "temp-mail.ru", "temp-mail.de", "tempmail.com",
    "tempmail.net", "tempmail.org", "tempmail.plus", "tempmail.io", "tempmail.dev",
    "tempmailo.com", "tempail.com", "tmpmail.net", "tmpmail.org", "tmails.net",
    "tempmailaddress.com", "mytemp.email", "tempinbox.com", "tempmailer.com",
    "guerrillamail.com", "guerrillamail.net", "guerrillamail.org", "guerrillamail.biz",
    "guerrillamail.de", "guerrillamail.info", "guerrillamailblock.com", "sharklasers.com",
    "grr.la", "pokemail.net", "spam4.me",
    "yopmail.com", "yopmail.fr", "yopmail.net", "cool.fr.nf", "jetable.fr.nf",
    "courriel.fr.nf", "moncourrier.fr.nf", "monemail.fr.nf", "monmail.fr.nf",
    "mailinator.com", "mailinator.net", "mailinator.org", "mailinator2.com",
    "sogetthis.com", "mailin8r.com", "mailinator.gq", "binkmail.com", "bobmail.info",
    "chammy.info", "devnullmail.com", "letthemeatspam.com", "mailinater.com",
    "trashmail.com", "trashmail.net", "trashmail.org", "trashmail.me", "trashmail.io",
    "trashmail.at", "trashmail.es", "trash-mail.com", "trashemail.de",
    "getnada.com", "nada.email", "nada.ltd", "abyssmail.com", "boximail.com",
    "clrmail.com", "dropmail.me", "getairmail.com", "givmail.com", "inboxbear.com",
    "tafmail.com", "vomoto.com", "zetmail.com",
    "maildrop.cc", "throwawaymail.com", "throwaway.email", "dispostable.com",
    "mailnesia.com", "mohmal.com", "mohmal.in", "mohmal.tech", "mohmal.im",
    "emailondeck.com", "fakeinbox.com", "fakemail.net", "fakemailgenerator.com",
    "emailfake.com", "generator.email", "crazymailing.com", "smailpro.com",
    "burnermail.io", "inboxkitten.com", "mailsac.com", "harakirimail.com",
    "mintemail.com", "incognitomail.org", "anonbox.net", "mailcatch.com",
    "mailnull.com", "meltmail.com", "spamgourmet.com", "eyepaste.com",
    "armyspy.com", "cuvox.de", "dayrep.com", "einrot.com", "fleckens.hu",
    "gustr.com", "jourrapide.com", "rhyta.com", "superrito.com", "teleworm.us",
    "vn10p.com", "mail1s.com", "1secmail.com", "1secmail.org", "1secmail.net",
    "esiix.com", "wwjmp.com", "dcctb.com", "dpptd.com", "rteet.com",
    "linshiyouxiang.net", "luxusmail.org", "moakt.com", "moakt.cc", "moakt.ws",
    "tmail.ws", "disbox.net", "disbox.org", "mailpoof.com", "mailtemp.info",
    "spambox.us", "spamfree24.org", "tempomail.fr", "wegwerfmail.de", "wegwerfmail.net",
})

_TU_KHOA_MIEN_RAC = (
    "10min", "tempmail", "temp-mail", "trashmail", "throwaway", "guerrillamail",
    "mailinator", "yopmail", "fakeinbox", "fakemail", "burnermail", "1secmail",
    "maildrop", "dispostable", "harakirimail", "smailpro", "emailfake", "mohmal",
)

_TLD_RAC = (".tk", ".ml", ".ga", ".cf", ".gq")

_MAU_EMAIL_CO_BAN = re.compile(r"^[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def chuan_hoa_email(email: str) -> str:
    """Hạ chữ thường + cắt khoảng trắng. Bắt buộc dùng ở CẢ đăng ký lẫn đăng nhập.

    Chuẩn hoá một bên mà quên bên kia là lỗi kinh điển: đăng ký `An@x.com` lưu thành
    `an@x.com`, đăng nhập gõ `An@x.com` tra không ra, người dùng tưởng sai mật khẩu.
    """
    return email.strip().lower()


def email_goc_chong_clone(email: str) -> str:
    """Đưa địa chỉ email về dạng gốc để chống lách hạn mức bằng dấu chấm Gmail (`a.b.c@gmail.com`)
    hoặc đuôi `+alias` (`user+1@gmail.com`)."""
    chuan = chuan_hoa_email(email)
    if "@" not in chuan:
        return chuan
    local, domain = chuan.split("@", 1)
    local = local.split("+", 1)[0]
    if domain in ("gmail.com", "googlemail.com"):
        local = local.replace(".", "")
        domain = "gmail.com"
    return f"{local}@{domain}"


#: Danh sách CÁC NHÀ CUNG CẤP EMAIL CHÍNH THỐNG ĐƯỢC PHÉP ĐĂNG KÝ (Whitelist).
#: Chặn 100% mọi dịch vụ mail 10 phút xoay tên miền ngẫu nhiên (temp-mail, smailpro, emailondeck...)
#: và không chấp nhận các đuôi tên miền tổ chức/trường học (.edu.vn, .gov.vn...).
MIEN_EMAIL_CHINH_THONG_CHO_PHEP: frozenset[str] = frozenset({
    "gmail.com", "googlemail.com",
    "outlook.com", "hotmail.com", "live.com", "msn.com", "outlook.com.vn", "hotmail.com.vn",
    "icloud.com", "me.com", "mac.com",
    "yahoo.com", "yahoo.com.vn", "ymail.com", "rocketmail.com",
    "proton.me", "protonmail.com", "pm.me",
})


def kiem_email_hop_le_chong_spam(email: str) -> str | None:
    """Kiểm tra định dạng email và CHỈ chấp nhận các nhà cung cấp email chính thống (Gmail, Outlook,
    iCloud, Yahoo, ProtonMail) để chặn triệt để 100% mọi loại mail 10 phút.
    Trả về lý do từ chối (tiếng Việt), hoặc `None` nếu hợp lệ."""
    chuan = chuan_hoa_email(email)
    if "@" not in chuan:
        return "Địa chỉ email không hợp lệ."
    local, domain = chuan.split("@", 1)
    if not local or not domain or "." not in domain:
        return "Địa chỉ email không đúng định dạng (ví dụ: ten@gmail.com)."
    if "+" in local:
        return (
            "Không hỗ trợ tạo tài khoản bằng email phụ chứa dấu cộng (+). "
            "Vui lòng dùng địa chỉ email chính."
        )
    if not _MAU_EMAIL_CO_BAN.match(chuan):
        return "Địa chỉ email chứa ký tự không hợp lệ."
    if local.count(".") > 3:
        return "Địa chỉ email có quá nhiều dấu chấm bất thường."

    # Tên miền nội bộ cho bộ kiểm thử tự động (`@test.local`, `@vi-du.com`, ...) — KHÔNG mở ở
    # production: `x.com`, `*.local` là địa chỉ không nhận thư, mở ra là lỗ tạo tài khoản ảo.
    from app.core.config import get_settings

    if get_settings().app_env != "prod" and (
        domain.endswith(".local") or domain in ("vi-du.com", "example.com", "x.com", "b.com", "c.com")
    ):
        return None

    # Whitelist nhà cung cấp email thật chính thống — chặn 100% mail 10 phút và các tên miền khác
    if domain not in MIEN_EMAIL_CHINH_THONG_CHO_PHEP:
        return (
            f"Tên miền '@{domain}' không được hỗ trợ để chống tạo tài khoản ảo / mail 10 phút. "
            "Hệ thống chỉ chấp nhận Gmail (@gmail.com), Outlook/Hotmail, iCloud, Yahoo hoặc ProtonMail."
        )
    return None


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
    session: AsyncSession,
    *,
    email: str,
    ten_hien: str,
    mat_khau_tho: str,
    dang_hoat_dong: bool = True,
) -> NguoiDung:
    """Tạo tài khoản. Người **đầu tiên** đăng ký thành quản trị."""
    email = chuan_hoa_email(email)
    ly_do_email = kiem_email_hop_le_chong_spam(email)
    if ly_do_email:
        raise ValueError(ly_do_email)
    ly_do = kiem_mat_khau_du_manh(mat_khau_tho)
    if ly_do:
        raise ValueError(ly_do)

    hien_co = await tim_theo_email(session, email)
    if hien_co is not None:
        raise ValueError("email_da_ton_tai")
    # Chặn thủ thuật chèn dấu chấm Gmail (vd `a.b.c@gmail.com` trùng với `abc@gmail.com`)
    email_goc = email_goc_chong_clone(email)
    if email_goc != email and await tim_theo_email(session, email_goc) is not None:
        raise ValueError("email_da_ton_tai")

    # KHÔNG có email "chủ hệ thống" viết cứng: repo công khai + đăng ký không xác minh email ⇒ ai
    # đăng ký trước bằng email đó là thành quản trị. Phong quyền qua `PATCH /auth/users/{id}` hoặc
    # `python -m app.scripts.phong_quan_tri <email>`.
    nguoi = NguoiDung(
        email=email,
        ten_hien=ten_hien.strip() or email.split("@")[0],
        mat_khau_bam=mk.bam(mat_khau_tho),
        dang_hoat_dong=dang_hoat_dong,
        la_quan_tri=await dem_nguoi_dung(session) == 0,
    )
    session.add(nguoi)
    await session.commit()
    await session.refresh(nguoi)
    return nguoi


def _ten_hien_chuan(ten_tho: str, email: str) -> str:
    """Cùng một luật với lúc đăng ký: rỗng ⇒ lấy phần trước @.

    Nếu đường SỬA dùng luật khác đường TẠO thì xoá trắng ô tên sẽ cho ra tài khoản không có tên
    hiển thị, trong khi tài khoản mới không bao giờ rơi vào trạng thái đó. Một luật, hai đường.
    """
    return ten_tho.strip() or chuan_hoa_email(email).split("@")[0]


async def doi_ten_hien(session: AsyncSession, *, nguoi: NguoiDung, ten_hien: str) -> NguoiDung:
    """Đổi tên hiển thị. KHÔNG đòi mật khẩu — có chủ đích.

    Tên hiển thị là thứ đổi lại được trong một giây và không cho ai thêm quyền gì. Đòi mật khẩu
    cho một thao tác vô hại là dạy người dùng gõ mật khẩu vào bất cứ ô nào hỏng — đó là huấn
    luyện cho lừa đảo, không phải bảo mật.
    """
    nguoi.ten_hien = _ten_hien_chuan(ten_hien, nguoi.email)
    await session.commit()
    await session.refresh(nguoi)
    return nguoi


async def doi_mat_khau(
    session: AsyncSession,
    *,
    nguoi: NguoiDung,
    mat_khau_cu: str,
    mat_khau_moi: str,
    giu_ma_phien_tho: str | None = None,
) -> tuple[str | None, int]:
    """Đổi mật khẩu. Trả `(lý do từ chối | None, số phiên khác đã thu hồi)`.

    ## Ba luật, mỗi luật vá một lỗ thật

    **1. PHẢI đúng mật khẩu cũ.** Không đòi thì một phiên bị mượn (máy công cộng chưa đăng xuất,
    mã phiên bị lấy) **chiếm hẳn** được tài khoản: kẻ kia đặt mật khẩu mới và chính chủ mất
    đường vào. Đòi mật khẩu cũ biến "mượn được phiên" thành "vẫn không đổi được khoá".

    **2. Thu hồi mọi phiên KHÁC.** Đổi mật khẩu mà để phiên cũ sống tiếp là *đổi trên giấy* —
    đúng cùng lý do `PATCH /users/{id}` xoá phiên khi khoá tài khoản. Người ta đổi mật khẩu
    chính vì nghi có người khác đang vào được; giữ phiên của người đó lại là phá đúng mục đích.

    **3. Giữ LẠI phiên đang dùng.** Đăng xuất chính người vừa đổi là hình phạt cho hành vi đúng,
    và họ sẽ tưởng đổi thất bại. Nên thu hồi "mọi phiên trừ phiên này".

    Mật khẩu mới trùng mật khẩu cũ bị từ chối: nó làm người dùng tin mình đã xoay khoá trong khi
    khoá y nguyên, và thao tác thu hồi phiên ở luật 2 sẽ làm họ tin tưởng sai chỗ.
    """
    if not mk.kiem(mat_khau_cu, nguoi.mat_khau_bam):
        return "Mật khẩu hiện tại không đúng.", 0
    ly_do = kiem_mat_khau_du_manh(mat_khau_moi)
    if ly_do:
        return ly_do, 0
    if mat_khau_cu == mat_khau_moi:
        return "Mật khẩu mới phải khác mật khẩu hiện tại.", 0

    nguoi.mat_khau_bam = mk.bam(mat_khau_moi)

    dieu_kien = [Phien.nguoi_dung_id == nguoi.id]
    if giu_ma_phien_tho:
        dieu_kien.append(Phien.ma_bam != ph.bam_ma(giu_ma_phien_tho))
    kq = await session.execute(delete(Phien).where(*dieu_kien))
    await session.commit()
    return None, int(kq.rowcount or 0)


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


async def lay_thong_tin_api_key(session: AsyncSession, nguoi_id: uuid.UUID) -> Phien | None:
    """Kiểm tra xem tài khoản đang có Developer API Key (`tr_live_...`) nào còn hiệu lực không."""
    return (
        await session.execute(
            select(Phien)
            .where(Phien.nguoi_dung_id == nguoi_id, Phien.het_han >= MOC_NAM_API_KEY)
            .order_by(Phien.created_at.desc())
        )
    ).scalars().first()


async def tao_moi_api_key(session: AsyncSession, nguoi_id: uuid.UUID) -> tuple[str, Phien]:
    """Sinh mới (hoặc xoay) Developer API Key (`tr_live_...`) cho tài khoản.
    Xoá các API Key cũ của tài khoản đó trước khi cấp key mới, giữ nguyên phiên trình duyệt.
    """
    import secrets

    await session.execute(
        delete(Phien).where(Phien.nguoi_dung_id == nguoi_id, Phien.het_han >= MOC_NAM_API_KEY)
    )
    ma_tho = f"{TIEN_TO_API_KEY}{secrets.token_urlsafe(32)}"
    ban_ghi = Phien(
        nguoi_dung_id=nguoi_id,
        ma_bam=ph.bam_ma(ma_tho),
        het_han=HAN_API_KEY,
    )
    session.add(ban_ghi)
    await session.commit()
    await session.refresh(ban_ghi)
    return ma_tho, ban_ghi


async def thu_hoi_api_key(session: AsyncSession, nguoi_id: uuid.UUID) -> int:
    """Thu hồi ngay lập tức Developer API Key của tài khoản."""
    kq = await session.execute(
        delete(Phien).where(Phien.nguoi_dung_id == nguoi_id, Phien.het_han >= MOC_NAM_API_KEY)
    )
    await session.commit()
    return int(kq.rowcount or 0)
