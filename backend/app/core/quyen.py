"""Xác thực người dùng và kiểm quyền sở hữu chapter (Auth slice B).

## Quan hệ với slice A

Slice A (`app.core.bao_ve`) là **một khoá chung**: ai cầm khoá làm được mọi thứ. Slice B thay
thế nó ở đường vào dữ liệu — từ đây **phải đăng nhập bằng tài khoản riêng**, khoá chung không
còn mở được dữ liệu của ai nữa. Khoá chung chỉ còn gác lượt tạo tài khoản **ĐẦU TIÊN**
(E52) — người lạ tự đăng ký được, và bị chặn bằng trần theo địa chỉ mạng thay vì bằng khoá.

Đây là bước mạnh lên, không phải đổi ngang: trước đây ai có khoá là đọc/xoá được chapter của
mọi người.

## Vì sao trả 404 chứ không 403 khi không phải chủ

403 nói "có tồn tại, nhưng bạn không được vào" — tức là xác nhận id đó có thật. Người dò sẽ
quét id để lập danh sách chapter tồn tại. 404 không phân biệt "không có" với "không phải của
bạn", nên không rò rỉ gì.

## Chapter chưa có chủ

Chapter tạo trước slice B có `chu_so_huu_id = NULL`. Chúng **không bị giấu đi** — mọi tài
khoản đăng nhập đều thấy, kèm nhãn "chưa có chủ", và quản trị nhận về được. Giấu đi hoặc gán
bừa cho một tài khoản đều là làm mất việc của người dùng.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models import (
    BatchItem,
    BatchRun,
    CharacterVoiceProfile,
    ConsistencyReviewTask,
    ExportComplianceLog,
    ExportJob,
    GlossaryEntry,
    Job,
    NguoiDung,
    OCRResult,
    Page,
    Project,
    RegionQualityAssessment,
    RegionSafeArea,
    RegionTextOrientation,
    TermSuggestionRun,
    TextRegion,
    TranslationResult,
    TypesetResult,
)
from app.services import tai_khoan

TEN_HEADER = "Authorization"
TIEN_TO_BEARER = "Bearer "

LOI_CHUA_DANG_NHAP = "Chưa đăng nhập. Gửi mã phiên ở header `Authorization: Bearer <mã>`."
LOI_KHONG_THAY = "Không tìm thấy, hoặc không thuộc về tài khoản của bạn."
LOI_CAM_API_KEY_NHAY_CAM = (
    "Khoá Developer API (tr_live_...) chỉ được cấp quyền dịch thuật tự động, không được phép "
    "đổi mật khẩu, xoay/thu hồi khoá API hay thực hiện thao tác quản trị hệ thống. "
    "Vui lòng đăng nhập trực tiếp bằng tài khoản trên Web."
)


def la_khoa_api_developer(ma_tho: str | None) -> bool:
    """Kiểm tra mã xác thực có phải là Developer API Key (`tr_live_...`) hay không."""
    return bool(ma_tho and ma_tho.strip().startswith("tr_live_"))


def ma_phien_tu_header(
    gia_tri: str | None,
    x_customer_api_key: str | None = None,
    x_api_key: str | None = None,
) -> str | None:
    if gia_tri and gia_tri.startswith(TIEN_TO_BEARER):
        ma = gia_tri[len(TIEN_TO_BEARER):].strip()
        if ma:
            return ma
    if x_customer_api_key and x_customer_api_key.strip():
        return x_customer_api_key.strip()
    if x_api_key and x_api_key.strip().startswith("tr_live_"):
        return x_api_key.strip()
    return None


async def nguoi_dung_hien_tai(
    authorization: str | None = Header(default=None, alias=TEN_HEADER),
    x_customer_api_key: str | None = Header(default=None, alias="X-Customer-Api-Key"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_session),
) -> NguoiDung:
    """Dependency bắt buộc đăng nhập (hoặc gửi Developer API Key `tr_live_...`). Thiếu/sai/hết hạn ⇒ 401."""
    ma = ma_phien_tu_header(authorization, x_customer_api_key, x_api_key)
    nguoi = await tai_khoan.lay_theo_ma_phien(session, ma) if ma else None
    if nguoi is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=LOI_CHUA_DANG_NHAP,
            headers={"WWW-Authenticate": "Bearer"},
        )
    return nguoi


async def nguoi_dung_phien_dang_nhap(
    authorization: str | None = Header(default=None, alias=TEN_HEADER),
    x_customer_api_key: str | None = Header(default=None, alias="X-Customer-Api-Key"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_session),
) -> NguoiDung:
    """Dependency bắt buộc phiên đăng nhập tương tác (14 ngày), TỪ CHỐI Developer API Key (`tr_live_...`).

    Dùng cho các thao tác nhạy cảm: xoay/thu hồi API Key, đổi mật khẩu, hoặc quản trị hệ thống.
    Nếu `tr_live_...` bị lộ từ máy khách/tool bên thứ ba, kẻ tấn công không thể dùng nó để chiếm
    tài khoản hoặc leo thang đặc quyền.
    """
    ma = ma_phien_tu_header(authorization, x_customer_api_key, x_api_key)
    nguoi = await tai_khoan.lay_theo_ma_phien(session, ma) if ma else None
    if nguoi is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=LOI_CHUA_DANG_NHAP,
            headers={"WWW-Authenticate": "Bearer"},
        )
    if la_khoa_api_developer(ma):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=LOI_CAM_API_KEY_NHAY_CAM,
        )
    return nguoi


#: Đi từ một bản ghi bất kỳ ngược về chapter. Thứ tự trong tuple là thứ tự thử.
#: Viết dạng bảng thay vì `if isinstance(...)` rải rác để **thêm bảng mới không quên kiểm quyền**:
#: bảng nào chưa có mặt ở đây sẽ bị `project_id_cua` từ chối thẳng, chứ không lọt qua im lặng.
_CHA: dict[type, tuple[str, type | None]] = {
    Project: ("id", None),
    Page: ("project_id", Project),
    ExportJob: ("project_id", Project),
    BatchRun: ("project_id", Project),
    GlossaryEntry: ("project_id", Project),
    CharacterVoiceProfile: ("project_id", Project),
    ConsistencyReviewTask: ("project_id", Project),
    ExportComplianceLog: ("project_id", Project),
    TermSuggestionRun: ("project_id", Project),
    TextRegion: ("page_id", Page),
    Job: ("page_id", Page),
    BatchItem: ("page_id", Page),
    OCRResult: ("region_id", TextRegion),
    TranslationResult: ("region_id", TextRegion),
    TypesetResult: ("region_id", TextRegion),
    RegionQualityAssessment: ("region_id", TextRegion),
    RegionSafeArea: ("region_id", TextRegion),
    RegionTextOrientation: ("region_id", TextRegion),
}


async def project_id_cua(session: AsyncSession, ban_ghi: object) -> uuid.UUID | None:
    """Lần ngược chuỗi cha tới chapter. Bản ghi mồ côi (cha đã bị xoá) ⇒ None."""
    loai = type(ban_ghi)
    if loai not in _CHA:
        raise TypeError(
            f"{loai.__name__} chưa khai trong bảng _CHA của app/core/quyen.py — "
            "thêm vào đó rồi mới dùng, đừng bỏ qua kiểm quyền."
        )
    hien_tai: object | None = ban_ghi
    while hien_tai is not None:
        ten_cot, loai_cha = _CHA[type(hien_tai)]
        gia_tri = getattr(hien_tai, ten_cot)
        if loai_cha is None:
            return gia_tri
        if gia_tri is None:
            return None
        hien_tai = await session.get(loai_cha, gia_tri)
    return None


@dataclass(frozen=True)
class NguoiGoi:
    """Ai đang gọi — **một** kiểu cho cả người đăng nhập lẫn khách lạ.

    Cố ý gộp thành một kiểu thay vì hai đường kiểm quyền song song: hai đường thì luật phân
    quyền có hai bản, và một ngày nào đó chỉ một bản được sửa.

    `khach` là mã cookie **đã băm**, không phải cookie thô.
    """

    nguoi: NguoiDung | None = None
    khach: str | None = None

    @property
    def la_khach(self) -> bool:
        return self.nguoi is None

    @staticmethod
    def cua(ai: "NguoiDung | NguoiGoi") -> "NguoiGoi":
        """Nhận cả `NguoiDung` lẫn `NguoiGoi` — để 18 chỗ gọi `bao_dam_quyen` không phải sửa."""
        return ai if isinstance(ai, NguoiGoi) else NguoiGoi(nguoi=ai)


def duoc_dung_project(ai: "NguoiDung | NguoiGoi", project: Project) -> bool:
    """Luật phân quyền chapter — viết MỘT lần, dùng cho cả hai loại người gọi.

    Ba nhánh, và nhánh giữa là nhánh dễ quên nhất:

    1. **Khách lạ** chỉ thấy chapter mang đúng mã khách của mình. Khách chưa có mã (`None`)
       không thấy gì — kể cả các chapter `chu_khach IS NULL`.
    2. **Người đăng nhập KHÔNG thấy chapter của khách.** Thiếu nhánh này thì chapter khách
       (`chu_so_huu_id IS NULL`) rơi vào nhóm "chưa có chủ" ở nhánh 3, và **mọi tài khoản đăng
       nhập đọc được truyện của mọi khách lạ**. Đây là rò rỉ dữ liệu, không phải chuyện tiện lợi.
    3. Người đăng nhập thấy chapter của mình; chapter **chưa có chủ** chỉ quản trị thấy.
    """
    goi = NguoiGoi.cua(ai)
    if goi.la_khach:
        return goi.khach is not None and project.chu_khach == goi.khach
    if project.chu_khach is not None:
        return False
    if project.chu_so_huu_id is None:
        # Chapter vô chủ (cũ trước slice B, của tài khoản đã bị xoá, hoặc vừa `release`) CHỈ quản
        # trị thấy/nhận. Mở cho mọi tài khoản thì xoá một người là phát truyện của họ cho cả hệ thống.
        return bool(goi.nguoi.la_quan_tri)
    return project.chu_so_huu_id == goi.nguoi.id


async def bao_dam_quyen(
    session: AsyncSession, nguoi: "NguoiDung | NguoiGoi", ban_ghi: object
) -> None:
    """Ném 404 nếu `nguoi` không được đụng vào `ban_ghi`. Không phải chủ ⇒ như không tồn tại.

    Nhận cả `NguoiDung` lẫn `NguoiGoi`, nên 18 chỗ gọi sẵn có không phải sửa gì.
    """
    pid = await project_id_cua(session, ban_ghi)
    project = await session.get(Project, pid) if pid is not None else None
    if project is None or not duoc_dung_project(nguoi, project):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=LOI_KHONG_THAY)
