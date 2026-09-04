"""Xác thực người dùng và kiểm quyền sở hữu chapter (Auth slice B).

## Quan hệ với slice A

Slice A (`app.core.bao_ve`) là **một khoá chung**: ai cầm khoá làm được mọi thứ. Slice B thay
thế nó ở đường vào dữ liệu — từ đây **phải đăng nhập bằng tài khoản riêng**, khoá chung không
còn mở được dữ liệu của ai nữa. Khoá chung chỉ còn đúng một việc: gác cổng **đăng ký**, để
người lạ trên internet không tự tạo tài khoản.

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


def _ma_tu_header(gia_tri: str | None) -> str | None:
    if not gia_tri or not gia_tri.startswith(TIEN_TO_BEARER):
        return None
    return gia_tri[len(TIEN_TO_BEARER):].strip() or None


async def nguoi_dung_hien_tai(
    authorization: str | None = Header(default=None, alias=TEN_HEADER),
    session: AsyncSession = Depends(get_session),
) -> NguoiDung:
    """Dependency bắt buộc đăng nhập. Thiếu/sai/hết hạn mã phiên ⇒ 401."""
    ma = _ma_tu_header(authorization)
    nguoi = await tai_khoan.lay_theo_ma_phien(session, ma) if ma else None
    if nguoi is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=LOI_CHUA_DANG_NHAP,
            headers={"WWW-Authenticate": "Bearer"},
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


def duoc_dung_project(nguoi: NguoiDung, project: Project) -> bool:
    """Chapter chưa có chủ thì ai đăng nhập cũng dùng được (xem docstring module)."""
    return project.chu_so_huu_id is None or project.chu_so_huu_id == nguoi.id


async def bao_dam_quyen(session: AsyncSession, nguoi: NguoiDung, ban_ghi: object) -> None:
    """Ném 404 nếu `nguoi` không được đụng vào `ban_ghi`. Không phải chủ ⇒ như không tồn tại."""
    pid = await project_id_cua(session, ban_ghi)
    project = await session.get(Project, pid) if pid is not None else None
    if project is None or not duoc_dung_project(nguoi, project):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=LOI_KHONG_THAY)
