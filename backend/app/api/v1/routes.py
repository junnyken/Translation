"""API contract M1 — prefix /api/v1.

Nguyên tắc bắt buộc:
- Không chạy logic AI đồng bộ trong request. Endpoint upload page trả 202 + job_id.
- Response luôn qua Pydantic schema, không trả SQLAlchemy object.
- Lỗi validate để FastAPI trả 422 mặc định, không tự chế error format.
"""
from __future__ import annotations

import logging
import mimetypes
import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy import String, delete, func, select
from sqlalchemy import cast as sa_cast
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import (
    Settings,
    dich_danh_sach_thoai_ngu_canh_dong,
    dong_bo_khoa_ai_dong,
    get_settings,
    kiem_tra_ket_noi_khoa_ai,
    lay_thong_tin_khoa_ai_che,
    luu_cau_hinh_khoa_ai_dong,
    viet_kich_ban_review_chuong_dong,
)
from app.core.db import get_session
from app.core.cong_han_muc import con_du_khong, giu_cho_moi_chot, loi_vuot_han_muc
from app.core.danh_tinh_khach import DanhTinhHanMuc, danh_tinh_han_muc
from app.services.han_muc import bay_gio, moc_reset_ke_tiep, ngay_han_muc
from app.services import don_nap
from app.services.han_muc_nhan_dang import giu_mot_luot
from app.services.nhat_ky_quan_tri import ghi_nhat_ky
from app.services.so_cai_han_muc import da_dung_bat_dong_bo, giu_cho_bat_dong_bo
from app.core.quyen import (
    LOI_KHONG_THAY,
    NguoiGoi,
    bao_dam_quyen,
    duoc_dung_project,
    nguoi_dung_hien_tai,
    nguoi_dung_phien_dang_nhap,
)
from app.models import (
    BatchItem,
    BatchRun,
    CharacterVoiceProfile,
    ConsistencyReviewTask,
    DonNapLuot,
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
    SoCaiHanMuc,
    TermSuggestionRun,
    TextRegion,
    TranslationResult,
    TypesetResult,
    YeuCauNhanDangNgonNgu,
    UploadRequest,
    DetectOutbox,
)
from app.models.enums import (
    OCRStatus,
    ChePipeline,
    IntendedUse,
    RegionStatus,
    SourceLang,
    TargetLang,
    TrangThaiHanMuc,
    BatchItemStatus,
    OrientationStatus,
    SafeAreaStatus,
    TextOrientation,
    ConsistencyTaskStatus,
    ConsistencyTaskType,
    GlossaryStatus,
    TermType,
    VoiceProfileStatus,
    BatchPipeline,
    BatchStatus,
    OverallBand,
    ReviewStatus,
    ExportFormat,
    FitStatus,
    JobStatus,
    JobType,
    LoaiChuThe,
    PageStatus,
    TranslationEngine,
)
from app.schemas.common import (
    CapLuotRequest,
    CapLuotResponse,
    ChotHanMucRead,
    DonNapLuotRead,
    DuyetDonNapRequest,
    GoiNapLuotRead,
    HanMucRead,
    DichThoaiNguCanhRequest,
    DichThoaiNguCanhResponse,
    VietKichBanReviewRequest,
    VietKichBanReviewResponse,
    QuanTriCauHinhAiRequest,
    QuanTriCauHinhAiResponse,
    QuanTriKiemTraAiRequest,
    QuanTriKiemTraAiResponse,
    QuanTriNguoiDungChiTietRead,
    QuanTriThongKeRead,
    ThongTinNapLuotRead,
    XacNhanChuyenKhoanRequest,
    TienDoDocTruyen,
    NhanDangNgonNguRead,
    TrangDocTruyen,
    VungDocTruyen,
    TermCandidatesResponse,
    TermSuggestionCreate,
    TermSuggestionRunRead,
    VoiceSignalsResponse,
    OrientationRead,
    PageOrientationSummary,
    PageSafeAreaSummary,
    SafeAreaRead,
    DoiChieuTenRequest,
    DoiChieuTenResponse,
    JobRead,
    OCRResultRead,
    TranslationResultRead,
    TypesetResultRead,
    BBoxOut,
    PageDetail,
    RegionDetail,
    RegionPatch,
    RegionPatchAccepted,
    JobAccepted,
    ExportJobAccepted,
    ExportJobRead,
    ExportPreview,
    ExportRequest,
    ExportWarningsRead,
    BatchAccepted,
    BatchConfigRead,
    BatchCreate,
    BatchItemRead,
    BatchItemsPage,
    BatchResumeAccepted,
    AcknowledgeRead,
    AcknowledgeRequest,
    LyDoRead,
    PageQualityRead,
    QualityReviewRead,
    QualityReviewRequest,
    QualitySummary,
    RegionQualityRead,
    BatchResumeRequest,
    BatchRunList,
    BatchRunRead,
    ConsistencyScanRequest,
    ConsistencySummary,
    ConsistencyTaskRead,
    ConsistencyTasksPage,
    GlossaryEntryCreate,
    GlossaryEntryRead,
    GlossaryEntryUpdate,
    TaskAcceptAccepted,
    TaskAcceptRequest,
    TaskRejectRequest,
    VoiceProfileCreate,
    VoiceProfileRead,
    VoiceProfileUpdate,
    ArchiveAccepted,
    PageAccepted,
    PageRead,
    ProjectCreate,
    TrangTrongGoiAccepted,
    ProjectDetail,
    ProjectRead,
    RegionRead,
)
from app.services.dispatch import (
    dispatch_nhan_dang_ngon_ngu,
    dispatch_rut_gon_job,
    dispatch_detect_job,
    dispatch_inpaint_job,
    dispatch_xoa_vung_to_job,
    dispatch_ocr_job,
    dispatch_translate_job,
    dispatch_typeset_job,
    dispatch_refit_job,
    dispatch_region_reocr_job,
    dispatch_region_retranslate_job,
    dispatch_export_job,
    dispatch_consistency_scan_job,
)
from app.services.archive import (
    ArchiveEmpty,
    ArchiveError,
    ArchiveTooLarge,
    doc_goi_anh,
)
from app.services.pdf import doc_pdf_anh, la_pdf
from app.services.storage import (
    IObjectStorage,
    ObjectStat,
    UnsupportedImage,
    get_storage,
    sniff_image,
    thu_nho_anh_trang,
)
# CHỈ import module quy ước đường dẫn — KHÔNG kéo theo Pillow vào tiến trình API.
from app.services.export.paths import export_relative_dir
from app.services.typeset.paths import preview_relative_path
# Whitelist font của M6 — UI chỉ được chọn trong danh sách này, không tự chế font mới.
from app.services.typeset.registry import FONT_REGISTRY

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")

#: E49 — router CHO KHÁCH LẠ. Mọi đường trên đây **không** đòi đăng nhập.
#:
#: Vì sao tách router thay vì gỡ `Depends(nguoi_dung_hien_tai)` ở từng endpoint: cổng đăng nhập
#: gắn ở tầng router chính là thứ giữ cho 73 đường còn lại mặc định ĐÓNG. Gỡ nó ra rồi gắn lại
#: từng chỗ thì sớm muộn cũng quên một đường, và đường bị quên sẽ là đường không ai ngờ tới.
#:
#: Ở đây thì ngược lại: mặc định vẫn đóng, và mở là việc phải làm TƯỜNG MINH bằng cách chuyển
#: endpoint sang router này. `test_e49f` khoá chặt danh sách — thêm một đường vào đây mà không
#: sửa bài test thì bộ test ĐỎ.
router_khach = APIRouter(prefix="/api/v1")


async def _get_project_or_404(
    session: AsyncSession, project_id: uuid.UUID, nguoi: "NguoiDung | NguoiGoi"
) -> Project:
    """Lấy chapter, ném 404 nếu không có **hoặc không phải của `nguoi`**.

    `nguoi` là tham số BẮT BUỘC có chủ đích: đây là điểm nghẽn mà 18 endpoint đi qua, và nếu
    nó có giá trị mặc định thì một chỗ gọi quên truyền sẽ lặng lẽ bỏ qua kiểm quyền.
    """
    project = await session.get(Project, project_id)
    if project is None or not duoc_dung_project(nguoi, project):
        # Cùng một câu cho "không có" và "không phải của bạn" — xem app/core/quyen.py.
        raise HTTPException(status_code=404, detail=LOI_KHONG_THAY)
    return project


async def _bao_dam_quyen_theo_id(
    session: AsyncSession, nguoi: NguoiDung, loai: type, ban_ghi_id: uuid.UUID
) -> None:
    """Kiểm quyền cho các endpoint uỷ quyền việc SỬA cho dịch vụ đồng bộ rồi mới trả bản ghi.

    Ở những chỗ đó, kiểm quyền sau khi gọi dịch vụ là **đã muộn**: dữ liệu bị sửa xong rồi mới
    trả 404, tức là người lạ vẫn duyệt/lưu trữ/từ chối được mục của người khác — chỉ là không
    nhìn thấy kết quả.
    """
    ban_ghi = await session.get(loai, ban_ghi_id)
    if ban_ghi is None:
        raise HTTPException(status_code=404, detail=LOI_KHONG_THAY)
    await bao_dam_quyen(session, nguoi, ban_ghi)


async def _get_page_or_404(
    session: AsyncSession, page_id: uuid.UUID, nguoi: "NguoiDung | NguoiGoi"
) -> Page:
    """Lấy trang, ném 404 nếu không có hoặc chapter chứa nó không phải của `nguoi`."""
    page = await session.get(Page, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail=LOI_KHONG_THAY)
    await bao_dam_quyen(session, nguoi, page)
    return page


# ---------------- E19: tiện ích đọc truyện ----------------
#
# Hai endpoint này là toàn bộ những gì tiện ích cần. Chúng KHÔNG phải đường vòng né các cổng của
# bản web: vẫn qua cổng đăng nhập ở tầng router, vẫn dùng đúng pipeline, và chapter tạo ra vẫn
# mang `intended_use` do người dùng khai như mọi chapter khác.

#: Tên chapter dùng chung cho mọi trang tiện ích gửi lên. Một chapter cho mỗi (tài khoản, ngôn
#: ngữ nguồn) — KHÔNG phải mỗi lần bấm một chapter mới (bấm dịch 200 trang mà sinh 200 chapter thì
#: danh sách chapter của người dùng thành bãi rác), và KHÔNG dồn mọi ngôn ngữ vào một chapter
#: (source_lang chốt lúc tạo, đổi được lẫn lộn ja/en trong cùng chapter là dữ liệu sai).
TEN_CHAPTER_DOC_NHANH = "Đọc nhanh (tiện ích)"
#: E51 — chapter của luồng TRANG CHỦ (pipeline đầy đủ: xoá chữ + căn chữ ⇒ có ảnh tải về được).
#: Tên KHÁC hẳn tên của tiện ích: hai luồng sinh ra hai chapter riêng cho cùng một người, và để
#: chung tên thì danh sách chapter có hai dòng giống nhau mà nội dung khác nhau.
TEN_CHAPTER_DICH_NHANH = "Dịch nhanh"


def _kiem_engine(
    engine: TranslationEngine | None, settings: Settings, *, co_tai_khoan: bool = True
) -> None:
    """Chặn engine không dùng được NGAY lúc nhận yêu cầu, trước khi xếp việc.

    - `llm_context` thiếu khoá ⇒ 422 (như trước).
    - E73 `chatgpt_codex` ngoài bản cài cục bộ ⇒ 422: máy chủ dùng chung KHÔNG được chạy tài khoản
      ChatGPT của một người cho người khác. Khách lạ chưa đăng nhập ⇒ 403 kể cả ở bản cài cục bộ.
      Worker vẫn tự từ chối lần nữa (`cho_phep`) — đây chỉ là báo sớm.
    """
    if engine is TranslationEngine.llm_context and not settings.llm_configured:
        dong_bo_khoa_ai_dong(settings)
    if engine is TranslationEngine.llm_context and not settings.llm_configured:
        raise HTTPException(
            status_code=422,
            detail="llm_not_configured: chưa cấu hình khoá dịch, không dùng được llm_context",
        )
    if engine is TranslationEngine.chatgpt_codex:
        if not settings.che_do_cai_cuc_bo:
            raise HTTPException(
                status_code=422,
                detail="codex_chi_cai_cuc_bo: chatgpt_codex chỉ dùng ở bản cài cục bộ",
            )
        if not co_tai_khoan:
            raise HTTPException(
                status_code=403, detail="codex_can_dang_nhap: khách không dùng được chatgpt_codex",
            )


def _ten_chapter_nhanh(
    che_do: ChePipeline, source_lang: SourceLang, target_lang: TargetLang = TargetLang.vi
) -> str:
    goc = TEN_CHAPTER_DOC_NHANH if che_do is ChePipeline.chi_chu else TEN_CHAPTER_DICH_NHANH
    if target_lang is TargetLang.vi:
        return f"{goc} — {source_lang.value}"
    return f"{goc} — {source_lang.value}→{target_lang.value}"


async def _chapter_doc_nhanh(
    session: AsyncSession, goi: NguoiGoi, source_lang: SourceLang,
    che_do: ChePipeline = ChePipeline.chi_chu,
    target_lang: TargetLang = TargetLang.vi,
    *, rieng: bool = False, commit_project: bool = True,
) -> Project:
    """Lấy chapter `chi_chu` đúng ngôn ngữ nguồn/đích của người gọi, chưa có thì tạo.

    E49 — nhận cả khách lạ. Điều kiện tìm phải **đối xứng** với luật ở `duoc_dung_project`:
    người đăng nhập tìm kèm `chu_khach IS NULL`, nếu không một chapter của khách trùng tên sẽ
    bị nhận nhầm là của họ.
    """
    ten = _ten_chapter_nhanh(che_do, source_lang, target_lang)
    chu = (
        (Project.chu_khach == goi.khach,)
        if goi.la_khach
        else (Project.chu_so_huu_id == goi.nguoi.id, Project.chu_khach.is_(None))
    )
    co = (await session.execute(
        select(Project).where(
            *chu,
            Project.name == ten,
            Project.che_do_pipeline == che_do,
            Project.source_lang == source_lang,
            Project.target_lang == target_lang,
        ).limit(1)
    )).scalars().first()
    if co is not None and not rieng:
        return co

    project = Project(
        name=f"{ten} — riêng {uuid.uuid4().hex[:12]}" if rieng else ten,
        cau_hinh_rieng=rieng,
        source_lang=source_lang,
        target_lang=target_lang,
        # Khai `personal`: tiện ích dịch truyện người dùng đang tự đọc. Đây là mặc định trung
        # thực nhất, và người dùng đổi được ở bản web như mọi chapter khác.
        intended_use=IntendedUse.other if rieng else IntendedUse.personal,
        che_do_pipeline=che_do,
        chu_so_huu_id=None if goi.la_khach else goi.nguoi.id,
        chu_khach=goi.khach if goi.la_khach else None,
    )
    session.add(project)
    if commit_project:
        await session.commit()
        await session.refresh(project)
    else:
        await session.flush()
    return project


async def _tien_do_trang(session: AsyncSession, page_id: uuid.UUID) -> TienDoDocTruyen:
    """Việc của trang này đang chạy hay đang chờ, và chờ sau bao nhiêu việc khác.

    `started_at` (E19-3) là thứ phân biệt hai trạng thái đó. Không có nó thì chỉ nói được
    "chưa xong", và người dùng không biết mình chờ 5 giây hay 5 phút.
    """
    viec = (await session.execute(
        select(Job).where(Job.page_id == page_id, Job.status.in_((JobStatus.queued, JobStatus.running)))
        .order_by(Job.created_at)
        .limit(1)
    )).scalars().first()
    if viec is None:
        return TienDoDocTruyen()

    dang_chay = viec.started_at is not None
    truoc = None
    if not dang_chay:
        # Hàng đợi worker là hàng đợi CHUNG cho mọi chapter của mọi người, nên đếm trên toàn bộ
        # việc chưa chạy — đếm riêng chapter này sẽ ra một con số đẹp mà sai.
        truoc = int((await session.execute(
            select(func.count()).select_from(Job).where(
                Job.status == JobStatus.queued,
                Job.started_at.is_(None),
                Job.created_at < viec.created_at,
            )
        )).scalar() or 0)
    return TienDoDocTruyen(buoc=viec.type.value, dang_chay=dang_chay, so_viec_cho_truoc=truoc)


def _giu_ket_qua_phut_cho(co_tai_khoan: bool, settings: Settings) -> int | None:
    """Kết quả của NGƯỜI NÀY được giữ bao nhiêu phút. `None` = không tự xoá.

    Phải tính theo người gọi, không phải trả một hằng số: `tu_xoa_cho_tai_khoan` cho phép tắt
    luật xoá riêng cho tài khoản đã đăng ký, nên cùng một cấu hình có thể cho hai câu trả lời
    khác nhau ở hai người.

    Thứ tự kiểm quan trọng — `bat_lich_don_tep` tắt thì KHÔNG AI bị xoá, kể cả khách lạ. Đây là
    trạng thái thật của bản chạy ngày 27-09: E50 ship với lịch mặc định tắt, trong khi giao diện
    vẫn hứa "xoá sau 30 phút". Trường này sinh ra để câu trên màn không còn nói sai.
    """
    if not settings.bat_lich_don_tep:
        return None
    if co_tai_khoan and not settings.tu_xoa_cho_tai_khoan:
        return None
    return settings.giu_ket_qua_phut


@router_khach.get("/han-muc", response_model=HanMucRead, tags=["han-muc"])
async def xem_han_muc(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    danh_tinh: DanhTinhHanMuc = Depends(danh_tinh_han_muc),
) -> HanMucRead:
    """Hạn mức hôm nay của người đang gọi. **Khách lạ gọi được** — họ cần biết trước khi thả tệp.

    Đặc tả §1.3(c): thiếu endpoint này thì cách duy nhất để biết hạn mức là **bị từ chối**, và
    "hiện 0/6 mà không nói bao giờ có lại" chính là thứ làm người dùng tưởng hệ thống hỏng rồi
    bấm lại liên tục.

    `con_lai` là **nhỏ nhất** trong các chốt, không phải của chốt cookie: khách ở văn phòng đã
    chạm trần IP thì con số phải nói đúng `0`, dù chốt cookie của họ còn nguyên. Trả số lớn hơn
    thực tế là mời người ta thả 6 trang lên rồi nhận 429.

    Gọi endpoint này **không** tốn lượt và **không** giữ chỗ — chỉ đọc.
    """
    ngay = ngay_han_muc()
    chi_tiet: list[ChotHanMucRead] = []
    for chot in danh_tinh.chot:
        da = await da_dung_bat_dong_bo(session, chot.loai, chot.chu_the, ngay)
        chi_tiet.append(ChotHanMucRead(
            loai=chot.loai.value, da_dung=da, con_lai=max(0, chot.tran - da), tran=chot.tran
        ))

    reset = moc_reset_ke_tiep()
    chinh = chi_tiet[0] if chi_tiet else None
    luot_mua = danh_tinh.so_luot_mua_them if danh_tinh.co_tai_khoan else 0
    la_qt = bool(
        danh_tinh.co_tai_khoan
        and not danh_tinh.nguoi_goi.la_khach
        and getattr(danh_tinh.nguoi_goi.nguoi, "la_quan_tri", False)
    )
    return HanMucRead(
        giu_ket_qua_phut=_giu_ket_qua_phut_cho(danh_tinh.co_tai_khoan, settings),
        co_tai_khoan=danh_tinh.co_tai_khoan,
        tran=danh_tinh.tran_hien,
        # `da_dung` lấy của chốt CHÍNH: đó là con số "tôi đã dùng bao nhiêu", trong khi phần đã
        # dùng của chốt IP là của cả mạng dùng chung — trộn hai thứ đó vào một ô là nói sai.
        da_dung=chinh.da_dung if chinh else 0,
        con_lai=min((c.con_lai for c in chi_tiet), default=0) + luot_mua,
        reset_luc=reset,
        reset_sau_giay=max(0, int((reset - bay_gio()).total_seconds())),
        chot=chi_tiet,
        so_luot_mua_them=luot_mua,
        la_quan_tri=la_qt,
    )


def _doc_cau_hinh_ngan_hang_dong(settings: Settings) -> tuple[str, str, str]:
    """Đọc cấu hình VietQR động (hiện tạm ẩn thông tin tài khoản ngân hàng mặc định theo yêu cầu)."""
    return (
        (settings.ngan_hang_ten or "").strip(),
        (settings.ngan_hang_so_tk or "").strip(),
        (settings.ngan_hang_chu_tk or "").strip(),
    )


def _luu_cau_hinh_ngan_hang_dong(ten: str, stk: str, chu: str) -> None:
    import json

    storage = get_storage()
    rel = "quan_tri/cau_hinh_ngan_hang.json"
    payload = {
        "ngan_hang_ten": (ten or "").strip(),
        "ngan_hang_so_tk": (stk or "").strip(),
        "ngan_hang_chu_tk": (chu or "").strip(),
    }
    storage.save(rel, json.dumps(payload, ensure_ascii=False).encode("utf-8"))


def _danh_sach_goi_nap_chuan(don_gia: int) -> list[GoiNapLuotRead]:
    """Danh sách gói cước Phương án A (500đ/trang) kèm Gói Mồi 20.000đ (40 trang, mua nhiều lần cộng dồn thoải mái)."""
    return [
        GoiNapLuotRead(
            ma="goi_moi",
            ten="🎯 Gói Mồi Trải Nghiệm — Đọc Nhanh (40 trang)",
            so_tien_vnd=40 * don_gia,
            so_trang=40,
            ghi_chu="Gói nhỏ 20.000đ đọc trọn ~2 chapter. Mua nhiều lần tự động cộng dồn vĩnh viễn vào tài khoản.",
        ),
        GoiNapLuotRead(
            ma="co_ban",
            ten="🌱 Gói Khởi Đầu — Starter (105 trang)",
            so_tien_vnd=100 * don_gia,
            so_trang=105,
            ghi_chu="Tặng thêm +5% số trang (~5.5 chapter). Lượt mua cộng dồn vĩnh viễn không bao giờ hết hạn qua đêm.",
        ),
        GoiNapLuotRead(
            ma="tieu_chuan",
            ten="🔥 Gói Độc Giả VIP — Reader (550 trang)",
            so_tien_vnd=500 * don_gia,
            so_trang=550,
            ghi_chu="Tặng thêm 10% số trang (~28 chapter). Dùng chung Web, Extension & App Windows.",
        ),
        GoiNapLuotRead(
            ma="nhom_dich",
            ten="🎬 Gói Nhóm Dịch / Studio (1.200 trang)",
            so_tien_vnd=1000 * don_gia,
            so_trang=1200,
            ghi_chu="Tặng thêm 20% số trang (~60 chapter). Phù hợp nhóm scanlation, dịch trọn bộ / làm video.",
        ),
        GoiNapLuotRead(
            ma="doanh_nghiep_api",
            ten="🏢 Gói Doanh Nghiệp / Web Truyện API Pro (6.500 trang)",
            so_tien_vnd=5000 * don_gia,
            so_trang=6500,
            ghi_chu="Tặng thêm 30% số trang (~325 chapter). Mở toàn bộ Developer REST API (tr_live_...), đẩy cả chapter qua URL & đồng bộ đa máy.",
        ),
        GoiNapLuotRead(
            ma="enterprise_scale",
            ten="🏛️ Gói Doanh Nghiệp Lớn / Hệ Thống Cổng Truyện (28.000 trang)",
            so_tien_vnd=20000 * don_gia,
            so_trang=28000,
            ghi_chu="Tặng thêm 40% số trang (~1.400 chapter). Dành cho hệ thống web truyện lớn & tool tự động hoá 24/7 qua API.",
        ),
    ]


@router_khach.get("/nap-luot/thong-tin", response_model=ThongTinNapLuotRead, tags=["han-muc"])
async def xem_thong_tin_nap_luot(
    settings: Settings = Depends(get_settings),
    danh_tinh: DanhTinhHanMuc = Depends(danh_tinh_han_muc),
) -> ThongTinNapLuotRead:
    """E100 — Thông tin gói nạp lượt & mã chuyển khoản VietQR tự động."""
    nguoi = danh_tinh.nguoi_goi.nguoi if (danh_tinh.co_tai_khoan and not danh_tinh.nguoi_goi.la_khach) else None
    email = nguoi.email if nguoi is not None else None
    ma_noi_dung = f"NAP {str(nguoi.id).split('-')[0].upper()}" if nguoi is not None else "NAP <EMAIL_CUA_BAN>"
    don_gia = max(1, settings.ty_le_vnd_moi_trang)
    nh_ten, nh_stk, nh_chu = await run_in_threadpool(_doc_cau_hinh_ngan_hang_dong, settings)

    return ThongTinNapLuotRead(
        co_tai_khoan=danh_tinh.co_tai_khoan,
        email=email,
        la_quan_tri=bool(nguoi and nguoi.la_quan_tri),
        so_luot_mua_them=danh_tinh.so_luot_mua_them if danh_tinh.co_tai_khoan else 0,
        tran_hang_ngay=danh_tinh.tran_hien,
        ngan_hang_ten=nh_ten,
        ngan_hang_so_tk=nh_stk,
        ngan_hang_chu_tk=nh_chu,
        noi_dung_chuyen_khoan=ma_noi_dung,
        ty_le_vnd_moi_trang=don_gia,
        goi_goi_y=_danh_sach_goi_nap_chuan(don_gia),
    )


@router.post("/nap-luot/xac-nhan-chuyen-khoan", response_model=DonNapLuotRead, tags=["han-muc"])
async def xac_nhan_chuyen_khoan_goi(
    body: XacNhanChuyenKhoanRequest,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> DonNapLuotRead:
    """Ghi nhận đơn khách đã chọn để chờ Webhook ngân hàng hoặc quản trị xác nhận đối soát.

    CHỐT BẢO MẬT CHỐNG HACK SỐ LẦN GÓI CƯỚC:
    - Tuyệt đối KHÔNG nhận `so_tien_vnd` hay `so_trang` do phía client gửi lên để tự tính lượt.
    - Chỉ chấp nhận `ma_goi` nằm trong 5 gói chính thức của hệ thống (`_danh_sach_goi_nap_chuan`);
      nếu gửi `ma_goi` lạ hoặc giả mạo ⇒ từ chối thẳng 422.
    - Mọi đơn tạo qua đường này đều ở trạng thái `cho_duyet` và chỉ được cộng lượt khi có chữ ký
      Webhook ngân hàng (`WEBHOOK_NAP_LUOT_BI_MAT`) hoặc quản trị viên duyệt đối soát.
    """
    don_gia = max(1, settings.ty_le_vnd_moi_trang)
    ds_goi = {g.ma: g for g in _danh_sach_goi_nap_chuan(don_gia)}
    ma_goi_gui = (body.ma_goi or "").strip()
    goi = ds_goi.get(ma_goi_gui)
    if goi is None:
        raise HTTPException(
            status_code=422,
            detail="Mã gói cước không hợp lệ. Chỉ chấp nhận các gói cước chính thức của hệ thống.",
        )

    ma_goi = goi.ma
    ten_goi = goi.ten
    so_tien = goi.so_tien_vnd
    so_trang = goi.so_trang

    # Khách đã có đơn chờ duyệt cùng gói ⇒ trả đơn đó, không tạo dòng trùng.
    cho = await don_nap.tim_don_cho_duyet(session, nguoi.email or "", ma_goi)
    if cho is not None:
        return don_nap.sang_read(cho)

    don = DonNapLuot(
        ma_don=don_nap.sinh_ma_don(),
        nguoi_dung_id=nguoi.id,
        email=nguoi.email,
        ten_hien=nguoi.ten_hien,
        ma_goi=ma_goi,
        ten_goi=ten_goi,
        so_tien_vnd=so_tien,
        so_trang_cong=so_trang,
        noi_dung_chuyen_khoan=body.noi_dung_chuyen_khoan.strip() or f"NAP {ma_goi.upper()} {nguoi.email}",
        trang_thai="cho_duyet",
    )
    session.add(don)
    await session.commit()
    await session.refresh(don)
    return don_nap.sang_read(don)


def _ma_giao_dich_ngan_hang(payload: dict) -> str | None:
    """Mã giao dịch duy nhất của ngân hàng/cổng (SePay `id`/`referenceCode`, Casso/PayOS `data`)."""
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    for nguon in (payload, data):
        for khoa in ("id", "referenceCode", "reference", "tid", "transactionId", "transaction_id"):
            gia_tri = nguon.get(khoa)
            if gia_tri not in (None, ""):
                return f"{khoa}:{gia_tri}"[:128]
    return None


@router_khach.post("/nap-luot/webhook", tags=["han-muc"])
async def webhook_nap_luot_ngan_hang(
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    """E100 — Webhook tự động cộng lượt khi khách chuyển khoản ngân hàng (tương thích SePay / Casso / PayOS).

    Cú pháp nội dung chuyển khoản: `NAP <8_KY_TU_DAU_UUID>` hoặc `NAP <EMAIL>`.
    Bảo vệ bằng khoá bí mật `WEBHOOK_NAP_LUOT_BI_MAT` trong header `Authorization`.

    Chống cộng trùng: mỗi mã giao dịch ngân hàng chỉ cộng MỘT lần (ràng buộc duy nhất trên
    `don_nap_luot.ma_giao_dich_ngan_hang`). Cổng gửi lại vì timeout ⇒ trả `trung_lap`, không cộng.
    Chỉ nhận tiền VÀO (`transferType == "in"` khi cổng có gửi trường này).
    """
    import hmac
    import re

    bi_mat = (settings.webhook_nap_luot_bi_mat or "").strip()
    if not bi_mat:
        raise HTTPException(
            status_code=503,
            detail="Chưa cấu hình WEBHOOK_NAP_LUOT_BI_MAT trên máy chủ.",
        )

    auth = (request.headers.get("authorization") or request.headers.get("x-webhook-secret") or "").strip()
    for tien_to in ("Apikey ", "Bearer ", "apikey ", "bearer "):
        if auth.startswith(tien_to):
            auth = auth[len(tien_to):].strip()
            break
    if not hmac.compare_digest(auth.encode("utf-8"), bi_mat.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Khoá xác thực webhook không hợp lệ.")

    payload = await request.json()
    if not isinstance(payload, dict):
        return {"ok": False, "ly_do": "payload_khong_hop_le"}
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    loai_ck = str(payload.get("transferType") or data.get("transferType") or "in").lower()
    if loai_ck != "in":
        return {"ok": False, "ly_do": "khong_phai_tien_vao"}
    ma_giao_dich = _ma_giao_dich_ngan_hang(payload)
    if ma_giao_dich is None:
        return {"ok": False, "ly_do": "thieu_ma_giao_dich"}
    noi_dung = str(
        payload.get("content")
        or payload.get("description")
        or data.get("description")
        or ""
    ).strip()
    so_tien = int(
        payload.get("transferAmount")
        or payload.get("amount")
        or data.get("amount")
        or 0
    )
    if so_tien <= 0 or not noi_dung:
        return {"ok": False, "ly_do": "khong_co_so_tien_hoac_noi_dung"}

    da_xu_ly = (
        await session.execute(
            select(DonNapLuot.ma_don).where(DonNapLuot.ma_giao_dich_ngan_hang == ma_giao_dich)
        )
    ).scalar_one_or_none()
    if da_xu_ly is not None:
        return {"ok": True, "trung_lap": True, "ma_don": da_xu_ly}

    don_gia = max(1, settings.ty_le_vnd_moi_trang)
    so_trang_goc = so_tien // don_gia
    if so_trang_goc <= 0:
        return {"ok": False, "ly_do": "so_tien_nho_hon_1_trang"}
    # Tặng thêm theo bậc (cộng dồn vĩnh viễn vào so_luot_mua_them):
    # >= 20.000 trang gốc (Enterprise): +40%
    # >= 5.000 trang gốc (Doanh nghiệp API Pro): +30%
    # >= 1.000 trang gốc (Studio): +20%
    # >= 500 trang gốc (VIP): +10%
    # >= 100 trang gốc (Starter): +5%
    # < 100 trang gốc (Gói Mồi 40 trang / 20.000đ): đúng tỷ lệ chuẩn, cộng dồn không giới hạn số lần mua
    if so_trang_goc >= 20000:
        so_trang_cong = int(so_trang_goc * 1.4)
        ma_goi_nhan = "enterprise_scale"
        ten_goi_nhan = "🏛️ Gói Doanh Nghiệp Lớn / Hệ Thống Cổng Truyện"
    elif so_trang_goc >= 5000:
        so_trang_cong = int(so_trang_goc * 1.3)
        ma_goi_nhan = "doanh_nghiep_api"
        ten_goi_nhan = "🏢 Gói Doanh Nghiệp / Web Truyện API Pro"
    elif so_trang_goc >= 1000:
        so_trang_cong = int(so_trang_goc * 1.2)
        ma_goi_nhan = "nhom_dich"
        ten_goi_nhan = "🎬 Gói Nhóm Dịch / Studio"
    elif so_trang_goc >= 500:
        so_trang_cong = int(so_trang_goc * 1.1)
        ma_goi_nhan = "tieu_chuan"
        ten_goi_nhan = "🔥 Gói Độc Giả VIP — Reader"
    elif so_trang_goc >= 100:
        so_trang_cong = int(so_trang_goc * 1.05)
        ma_goi_nhan = "co_ban"
        ten_goi_nhan = f"🌱 Gói Khởi Đầu ({so_trang_cong} trang)"
    else:
        so_trang_cong = so_trang_goc
        ma_goi_nhan = "goi_moi"
        ten_goi_nhan = f"🎯 Gói Mồi Trải Nghiệm ({so_trang_cong} trang)"

    nguoi: NguoiDung | None = None
    khop_email = re.search(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", noi_dung)
    if khop_email:
        email_tim = khop_email.group(1).lower()
        nguoi = (await session.execute(select(NguoiDung).where(NguoiDung.email == email_tim))).scalar_one_or_none()

    if nguoi is None:
        khop_ma = re.search(r"NAP\s+([0-9A-Fa-f]{8})\b", noi_dung, re.IGNORECASE)
        if khop_ma:
            ung_vien = (
                await session.execute(
                    select(NguoiDung).where(
                        sa_cast(NguoiDung.id, String).like(f"{khop_ma.group(1).lower()}%")
                    )
                )
            ).scalars().all()
            # Hai tài khoản trùng 8 ký tự đầu ⇒ không đoán, để quản trị đối soát tay.
            if len(ung_vien) == 1:
                nguoi = ung_vien[0]

    # App ngân hàng hay xoá '@' và '.' ("NAP user@gmail.com" → "NAP usergmailcom"): chỉ nhận khi
    # TOÀN BỘ email đã rút gọn nằm trong nội dung. Không còn khớp theo phần trước @ — "nguyen"
    # nằm trong nội dung của người khác là cộng nhầm tiền sang tài khoản khác.
    if nguoi is None:
        noi_dung_sach = re.sub(r"[^a-z0-9]", "", noi_dung.lower())
        khop: list[NguoiDung] = []
        for u in (await session.execute(select(NguoiDung))).scalars().all():
            email_rut_gon = re.sub(r"[^a-z0-9]", "", (u.email or "").lower())
            if len(email_rut_gon) >= 8 and email_rut_gon in noi_dung_sach:
                khop.append(u)
        if len(khop) == 1:
            nguoi = khop[0]

    if nguoi is None:
        return {"ok": False, "ly_do": "khong_tim_thay_tai_khoan_tu_noi_dung"}

    # Đơn khách đã bấm trên web ⇒ chốt đơn đó; không có ⇒ tạo đơn mới. Số lượt cộng LUÔN theo
    # số tiền thật về tài khoản, không theo con số khách tự khai trên đơn.
    don_cho = await don_nap.tim_don_cho_duyet(session, nguoi.email or "")
    try:
        if don_cho is not None and await don_nap.chuyen_trang_thai(
            session, don_cho.id, tu=("cho_duyet",), sang="da_xac_nhan", ma_giao_dich=ma_giao_dich,
            so_tien_vnd=so_tien, so_trang_cong=so_trang_cong,
        ):
            ma_don = don_cho.ma_don
        else:
            don_moi = DonNapLuot(
                ma_don=don_nap.sinh_ma_don(),
                nguoi_dung_id=nguoi.id,
                email=nguoi.email,
                ten_hien=nguoi.ten_hien,
                ma_goi=ma_goi_nhan,
                ten_goi=ten_goi_nhan,
                so_tien_vnd=so_tien,
                so_trang_cong=so_trang_cong,
                noi_dung_chuyen_khoan=noi_dung,
                trang_thai="da_xac_nhan",
                ma_giao_dich_ngan_hang=ma_giao_dich,
                duyet_luc=bay_gio(),
            )
            session.add(don_moi)
            await session.flush()
            ma_don = don_moi.ma_don
        await don_nap.cong_luot(session, nguoi.id, so_trang_cong)
        await session.commit()
    except IntegrityError:
        # Hai lượt gửi lại cùng lúc: lượt kia đã ghi mã giao dịch trước ⇒ không cộng lần hai.
        await session.rollback()
        return {"ok": True, "trung_lap": True}

    await session.refresh(nguoi)
    return {
        "ok": True,
        "email": nguoi.email,
        "ma_don": ma_don,
        "da_cong_them": so_trang_cong,
        "so_luot_mua_them_moi": nguoi.so_luot_mua_them,
    }


@router.post("/quan-tri/duyet-don-nap", response_model=DonNapLuotRead, tags=["han-muc"])
async def quan_tri_duyet_don_nap(
    body: DuyetDonNapRequest,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    nguoi: NguoiDung = Depends(nguoi_dung_phien_dang_nhap),
) -> DonNapLuotRead:
    """Quản trị xác nhận khớp sao kê hoặc thu hồi đơn.

    Chuyển trạng thái nguyên tử: bấm "Xác nhận" hai lần (hoặc trùng lúc webhook) thì chỉ một
    lượt cộng lượt, lượt kia thấy trạng thái đã đổi và không làm gì.
    """
    if not nguoi.la_quan_tri:
        raise HTTPException(status_code=403, detail="Chỉ quản trị viên mới được duyệt đơn nạp.")

    don = await don_nap.tim_don(session, body.ma_don)
    if don is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn nạp.")

    # Đối chiếu lại số trang của gói chuẩn nếu là đơn tạo tay (chưa có mã giao dịch ngân hàng)
    don_gia = max(1, settings.ty_le_vnd_moi_trang)
    ds_goi = {g.ma: g for g in _danh_sach_goi_nap_chuan(don_gia)}
    if don.ma_goi in ds_goi and not don.ma_giao_dich_ngan_hang:
        goi_chuan = ds_goi[don.ma_goi]
        don.so_tien_vnd = goi_chuan.so_tien_vnd
        don.so_trang_cong = goi_chuan.so_trang

    khach_id = don.nguoi_dung_id
    if khach_id is None:
        khach_id = (
            await session.execute(select(NguoiDung.id).where(NguoiDung.email == don.email.lower()))
        ).scalar_one_or_none()

    if body.hanh_dong == "xac_nhan":
        if await don_nap.chuyen_trang_thai(
            session, don.id, tu=("cho_duyet", "da_thu_hoi"), sang="da_xac_nhan"
        ):
            if khach_id is not None:
                await don_nap.cong_luot(session, khach_id, don.so_trang_cong)
            ghi_nhat_ky(session, nguoi, "duyet_don_nap", don.ma_don,
                        email=don.email, so_trang=don.so_trang_cong)
    elif body.hanh_dong == "thu_hoi":
        if await don_nap.chuyen_trang_thai(
            session, don.id, tu=("da_cong_tu_dong", "da_xac_nhan"), sang="da_thu_hoi"
        ):
            if khach_id is not None:
                await don_nap.cong_luot(session, khach_id, -don.so_trang_cong)
            ghi_nhat_ky(session, nguoi, "thu_hoi_don_nap", don.ma_don,
                        email=don.email, so_trang=don.so_trang_cong)
    else:
        raise HTTPException(status_code=422, detail="hanh_dong phải là 'xac_nhan' hoặc 'thu_hoi'.")

    await session.commit()
    await session.refresh(don)
    return don_nap.sang_read(don)


@router.post("/quan-tri/cap-luot", response_model=CapLuotResponse, tags=["han-muc"])
async def quan_tri_cap_luot(
    body: CapLuotRequest,
    session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_phien_dang_nhap),
) -> CapLuotResponse:
    """E100 — Quản trị viên cấp trực tiếp lượt mua thêm, đặt trần VIP hoặc lưu cấu hình VietQR."""
    if not nguoi.la_quan_tri:
        raise HTTPException(status_code=403, detail="Chỉ quản trị viên mới được cấp lượt.")

    if (
        body.ngan_hang_ten is not None
        or body.ngan_hang_so_tk is not None
        or body.ngan_hang_chu_tk is not None
    ) and not body.email.strip():
        await run_in_threadpool(
            _luu_cau_hinh_ngan_hang_dong,
            body.ngan_hang_ten or "",
            body.ngan_hang_so_tk or "",
            body.ngan_hang_chu_tk or "",
        )
        ghi_nhat_ky(session, nguoi, "doi_cau_hinh_ngan_hang", body.ngan_hang_ten or "",
                    so_tk=body.ngan_hang_so_tk, chu_tk=body.ngan_hang_chu_tk)
        await session.commit()
        return CapLuotResponse(
            email=nguoi.email,
            so_luot_mua_them=int(nguoi.so_luot_mua_them or 0),
            tran_hang_ngay_rieng=nguoi.tran_hang_ngay_rieng,
            # Thông tin ngân hàng đang TẠM ẨN theo yêu cầu (trang khách chỉ đọc từ biến môi trường),
            # nên báo đúng: đã lưu nhưng khách CHƯA thấy.
            thong_diep=f"Đã lưu cấu hình VietQR ({body.ngan_hang_ten} - {body.ngan_hang_so_tk}). "
            "Thông tin ngân hàng đang tạm ẩn trên trang khách — khách chưa thấy mã QR này.",
        )

    email_tim = body.email.strip().lower()
    dich = (
        await session.execute(select(NguoiDung).where(NguoiDung.email == email_tim))
    ).scalar_one_or_none()
    if dich is None:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy tài khoản '{email_tim}'.")

    truoc = (int(dich.so_luot_mua_them or 0), dich.tran_hang_ngay_rieng)
    if body.cong_them_luot != 0:
        await don_nap.cong_luot(session, dich.id, body.cong_them_luot)
    if body.tran_hang_ngay_rieng is not None:
        dich.tran_hang_ngay_rieng = body.tran_hang_ngay_rieng if body.tran_hang_ngay_rieng > 0 else None
    ghi_nhat_ky(session, nguoi, "cap_luot", dich.email, cong_them=body.cong_them_luot,
                luot_truoc=truoc[0], tran_truoc=truoc[1], tran_sau=dich.tran_hang_ngay_rieng)

    await session.commit()
    await session.refresh(dich)
    return CapLuotResponse(
        email=dich.email,
        so_luot_mua_them=dich.so_luot_mua_them,
        tran_hang_ngay_rieng=dich.tran_hang_ngay_rieng,
        thong_diep=f"Đã cập nhật hạn mức cho {dich.email}: {dich.so_luot_mua_them} lượt tích luỹ"
        + (f", trần VIP {dich.tran_hang_ngay_rieng} trang/ngày." if dich.tran_hang_ngay_rieng else "."),
    )


@router.post("/quan-tri/cau-hinh-ai", response_model=QuanTriCauHinhAiResponse, tags=["han-muc"])
async def quan_tri_luu_cau_hinh_ai(
    body: QuanTriCauHinhAiRequest,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    nguoi: NguoiDung = Depends(nguoi_dung_phien_dang_nhap),
) -> QuanTriCauHinhAiResponse:
    """Quản trị viên lưu & kích hoạt trực tiếp khoá DeepSeek (sk-...) và khoá AI dự phòng ngay từ trang Admin."""
    if not nguoi.la_quan_tri:
        raise HTTPException(status_code=403, detail="Chỉ quản trị viên mới được cấu hình khoá AI.")

    tt_che = await run_in_threadpool(
        luu_cau_hinh_khoa_ai_dong,
        settings,
        khoa_deepseek=body.khoa_deepseek,
        khoa_du_phong=body.khoa_du_phong,
        email_quan_tri=nguoi.email,
    )
    ghi_nhat_ky(
        session,
        nguoi,
        "cap_nhat_khoa_ai",
        tt_che.get("nha_cung_cap_uu_tien", ""),
        so_key_deepseek=tt_che.get("deepseek_so_key", 0),
        so_key_du_phong=tt_che.get("du_phong_so_key", 0),
    )
    await session.commit()

    so_ds = int(tt_che.get("deepseek_so_key", 0))
    so_dp = int(tt_che.get("du_phong_so_key", 0))
    if so_ds > 0:
        thong_diep = (
            f"Đã lưu & kích hoạt {so_ds} khoá DeepSeek (deepseek-chat) thành công"
            + (f" kèm {so_dp} khoá AI dự phòng." if so_dp > 0 else ".")
        )
    elif so_dp > 0:
        thong_diep = f"Đã lưu {so_dp} khoá AI dự phòng (hiện chưa có khoá DeepSeek)."
    else:
        thong_diep = "Đã xoá cấu hình khoá AI động (hệ thống quay về dịch nhanh miễn phí)."

    return QuanTriCauHinhAiResponse(
        thong_diep=thong_diep,
        **tt_che,
    )


@router.post("/quan-tri/kiem-tra-ai", response_model=QuanTriKiemTraAiResponse, tags=["han-muc"])
async def quan_tri_kiem_tra_ket_noi_ai(
    body: QuanTriKiemTraAiRequest,
    settings: Settings = Depends(get_settings),
    nguoi: NguoiDung = Depends(nguoi_dung_phien_dang_nhap),
) -> QuanTriKiemTraAiResponse:
    """Quản trị viên bấm nút kiểm tra kết nối trực tiếp tới DeepSeek / AI."""
    if not nguoi.la_quan_tri:
        raise HTTPException(status_code=403, detail="Chỉ quản trị viên mới được kiểm tra khoá AI.")
    kq = await run_in_threadpool(kiem_tra_ket_noi_khoa_ai, settings, body.khoa_thu)
    return QuanTriKiemTraAiResponse(**kq)


@router_khach.post("/doc-truyen/dich-thoai-ngu-canh", response_model=DichThoaiNguCanhResponse, tags=["doc-truyen"])
async def dich_thoai_ngu_canh_cho_app_va_tien_ich(
    body: DichThoaiNguCanhRequest,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    danh_tinh: DanhTinhHanMuc = Depends(danh_tinh_han_muc),
) -> DichThoaiNguCanhResponse:
    """Cầu nối dịch danh sách câu thoại đã OCR trên App Windows / Tiện ích bằng DeepSeek (deepseek-chat) trên máy chủ."""
    if not body.texts:
        return DichThoaiNguCanhResponse(translations=[], engine_used="empty")
    la_admin = (
        danh_tinh.co_tai_khoan
        and not danh_tinh.nguoi_goi.la_khach
        and getattr(danh_tinh.nguoi_goi.nguoi, "la_quan_tri", False)
    )
    if not la_admin:
        chu_the_chinh = danh_tinh.chot[0].chu_the if danh_tinh.chot else "guest"
        eng_name = (body.engine or "local_ocr_gpu").strip() or "local_ocr_gpu"
        pkey = (body.page_key or "").strip()
        trang_uid = (
            uuid.uuid5(uuid.NAMESPACE_URL, f"local-ocr-gpu:{eng_name}:{chu_the_chinh}:{pkey}:0")
            if pkey
            else uuid.uuid4()
        )
        await giu_cho_moi_chot(session, danh_tinh, settings, trang_id=trang_uid)
        await session.commit()
    ban_dich, eng_used = await run_in_threadpool(
        dich_danh_sach_thoai_ngu_canh_dong,
        settings,
        body.texts,
        source_lang=body.source_lang.value,
        target_lang=body.target_lang.value,
        boi_canh=body.boi_canh,
    )
    return DichThoaiNguCanhResponse(translations=ban_dich, engine_used=eng_used)


@router_khach.post("/doc-truyen/viet-kich-ban-review", response_model=VietKichBanReviewResponse, tags=["doc-truyen"])
async def viet_kich_ban_review_cho_video_studio(
    body: VietKichBanReviewRequest,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    danh_tinh: DanhTinhHanMuc = Depends(danh_tinh_han_muc),
) -> VietKichBanReviewResponse:
    """Biên kịch kịch bản Review Truyện toàn Chapter bằng DeepSeek (deepseek-chat) trên máy chủ."""
    if not body.pages:
        return VietKichBanReviewResponse(tom_tat_chuong="", scenes=[], engine_used="empty")
    la_admin = (
        danh_tinh.co_tai_khoan
        and not danh_tinh.nguoi_goi.la_khach
        and getattr(danh_tinh.nguoi_goi.nguoi, "la_quan_tri", False)
    )
    if not la_admin:
        chu_the_chinh = danh_tinh.chot[0].chu_the if danh_tinh.chot else "guest"
        ckey = (body.chapter_key or f"{body.ten_truyen}:{body.ten_chap}").strip()
        trang_uid = uuid.uuid5(uuid.NAMESPACE_URL, f"video-review-script:{chu_the_chinh}:{ckey}")
        await giu_cho_moi_chot(session, danh_tinh, settings, trang_id=trang_uid)
        await session.commit()

    pages_dict = [p.model_dump() for p in body.pages]
    scenes_raw, tom_tat, eng_used = await run_in_threadpool(
        viet_kich_ban_review_chuong_dong,
        settings,
        ten_truyen=body.ten_truyen,
        ten_chap=body.ten_chap,
        phong_cach=body.phong_cach,
        ho_so_nhan_vat=body.ho_so_nhan_vat,
        tom_tat_mach_chuong=body.tom_tat_mach_chuong,
        pages_input=pages_dict,
    )
    return VietKichBanReviewResponse(
        tom_tat_chuong=tom_tat,
        scenes=scenes_raw,
        engine_used=eng_used,
    )


@router.get("/quan-tri/thong-ke", response_model=QuanTriThongKeRead, tags=["han-muc"])
async def quan_tri_thong_ke(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    nguoi: NguoiDung = Depends(nguoi_dung_phien_dang_nhap),
) -> QuanTriThongKeRead:
    """E107 — Dashboard Quản trị tổng hợp: Thống kê hệ thống, số lượt tiêu thụ hôm nay/7 ngày/toàn thời gian và danh sách chi tiết từng khách hàng."""
    if not nguoi.la_quan_tri:
        raise HTTPException(status_code=404, detail="Không tìm thấy.")

    import json as _json
    import os as _os
    from datetime import timedelta
    from pathlib import Path

    hom_nay = ngay_han_muc()
    bay_ngay_truoc = hom_nay - timedelta(days=6)

    ds_nguoi = list(
        (await session.execute(select(NguoiDung).order_by(NguoiDung.created_at.desc()))).scalars()
    )

    # Thống kê số trang đã dịch từ sổ cái `SoCaiHanMuc` (không tính các khoản đã hoàn;
    # chỉ đếm `nguoi_dung` và `khach_cookie` để không cộng trùng `khach_ip` của cùng 1 khách lạ).
    trang_thai_hop_le = [TrangThaiHanMuc.giu_cho, TrangThaiHanMuc.da_tieu]
    loai_dem_trang = [LoaiChuThe.nguoi_dung, LoaiChuThe.khach_cookie]

    trang_tk_hom_nay = int(
        (
            await session.execute(
                select(func.coalesce(func.sum(SoCaiHanMuc.so_trang), 0)).where(
                    SoCaiHanMuc.ngay_han_muc == hom_nay,
                    SoCaiHanMuc.loai_chu_the == LoaiChuThe.nguoi_dung,
                    SoCaiHanMuc.trang_thai.in_(trang_thai_hop_le),
                )
            )
        ).scalar_one()
        or 0
    )
    trang_khach_hom_nay = int(
        (
            await session.execute(
                select(func.coalesce(func.sum(SoCaiHanMuc.so_trang), 0)).where(
                    SoCaiHanMuc.ngay_han_muc == hom_nay,
                    SoCaiHanMuc.loai_chu_the == LoaiChuThe.khach_cookie,
                    SoCaiHanMuc.trang_thai.in_(trang_thai_hop_le),
                )
            )
        ).scalar_one()
        or 0
    )
    trang_hom_nay = trang_tk_hom_nay + trang_khach_hom_nay

    trang_7_ngay = int(
        (
            await session.execute(
                select(func.coalesce(func.sum(SoCaiHanMuc.so_trang), 0)).where(
                    SoCaiHanMuc.ngay_han_muc >= bay_ngay_truoc,
                    SoCaiHanMuc.loai_chu_the.in_(loai_dem_trang),
                    SoCaiHanMuc.trang_thai.in_(trang_thai_hop_le),
                )
            )
        ).scalar_one()
        or 0
    )
    trang_toan_thoi_gian = int(
        (
            await session.execute(
                select(func.coalesce(func.sum(SoCaiHanMuc.so_trang), 0)).where(
                    SoCaiHanMuc.loai_chu_the.in_(loai_dem_trang),
                    SoCaiHanMuc.trang_thai.in_(trang_thai_hop_le),
                )
            )
        ).scalar_one()
        or 0
    )
    # Nếu có trang được dịch trước khi bật sổ cái hoặc qua luồng nội bộ, lấy max với tổng số Page thực tế
    tong_page_db = int(
        (await session.execute(select(func.count(Page.id)))).scalar_one() or 0
    )
    if tong_page_db > trang_toan_thoi_gian:
        trang_toan_thoi_gian = tong_page_db

    tong_chapter = int(
        (await session.execute(select(func.count(Project.id)))).scalar_one() or 0
    )

    # Biểu đồ sản lượng 7 ngày gần nhất
    rows_7_ngay = (
        await session.execute(
            select(
                SoCaiHanMuc.ngay_han_muc,
                SoCaiHanMuc.loai_chu_the,
                func.coalesce(func.sum(SoCaiHanMuc.so_trang), 0),
            )
            .where(
                SoCaiHanMuc.ngay_han_muc >= bay_ngay_truoc,
                SoCaiHanMuc.loai_chu_the.in_(loai_dem_trang),
                SoCaiHanMuc.trang_thai.in_(trang_thai_hop_le),
            )
            .group_by(SoCaiHanMuc.ngay_han_muc, SoCaiHanMuc.loai_chu_the)
        )
    ).all()
    map_7_ngay_tk: dict[str, int] = {}
    map_7_ngay_khach: dict[str, int] = {}
    for ngay_row, loai_row, so_tr in rows_7_ngay:
        k = ngay_row.isoformat() if hasattr(ngay_row, "isoformat") else str(ngay_row)
        if loai_row == LoaiChuThe.nguoi_dung:
            map_7_ngay_tk[k] = int(so_tr or 0)
        else:
            map_7_ngay_khach[k] = int(so_tr or 0)

    bieu_do_7_ngay: list[dict] = []
    for i in range(6, -1, -1):
        d = hom_nay - timedelta(days=i)
        k = d.isoformat()
        tk_d = map_7_ngay_tk.get(k, 0)
        kh_d = map_7_ngay_khach.get(k, 0)
        bieu_do_7_ngay.append(
            {
                "ngay": k,
                "nhan": d.strftime("%d/%m"),
                "trang_tai_khoan": tk_d,
                "trang_khach": kh_d,
                "tong": tk_d + kh_d,
            }
        )

    # Phân bổ theo ngôn ngữ nguồn
    rows_lang = (
        await session.execute(
            select(Project.source_lang, func.count(Project.id)).group_by(Project.source_lang)
        )
    ).all()
    phan_bo_ngon_ngu: dict[str, int] = {}
    for lang_val, cnt_lang in rows_lang:
        ma_lang = lang_val.value if hasattr(lang_val, "value") else str(lang_val)
        phan_bo_ngon_ngu[ma_lang] = int(cnt_lang or 0)

    # Gom số trang dùng hôm nay theo từng user
    rows_hom_nay = (
        await session.execute(
            select(SoCaiHanMuc.chu_the, func.coalesce(func.sum(SoCaiHanMuc.so_trang), 0))
            .where(
                SoCaiHanMuc.loai_chu_the == LoaiChuThe.nguoi_dung,
                SoCaiHanMuc.ngay_han_muc == hom_nay,
                SoCaiHanMuc.trang_thai.in_(trang_thai_hop_le),
            )
            .group_by(SoCaiHanMuc.chu_the)
        )
    ).all()
    map_hom_nay: dict[str, int] = {}
    for chu_the, tong in rows_hom_nay:
        k_uid = str(chu_the).removeprefix("mua_them:")
        map_hom_nay[k_uid] = map_hom_nay.get(k_uid, 0) + int(tong or 0)

    # Gom tổng trang toàn thời gian theo từng user
    rows_all = (
        await session.execute(
            select(SoCaiHanMuc.chu_the, func.coalesce(func.sum(SoCaiHanMuc.so_trang), 0))
            .where(
                SoCaiHanMuc.loai_chu_the == LoaiChuThe.nguoi_dung,
                SoCaiHanMuc.trang_thai.in_(trang_thai_hop_le),
            )
            .group_by(SoCaiHanMuc.chu_the)
        )
    ).all()
    map_all: dict[str, int] = {}
    for chu_the, tong in rows_all:
        k_uid = str(chu_the).removeprefix("mua_them:")
        map_all[k_uid] = map_all.get(k_uid, 0) + int(tong or 0)

    # Gom số chapter theo từng user
    rows_chap = (
        await session.execute(
            select(Project.chu_so_huu_id, func.count(Project.id))
            .where(Project.chu_so_huu_id.is_not(None))
            .group_by(Project.chu_so_huu_id)
        )
    ).all()
    map_chap = {str(uid): int(cnt) for uid, cnt in rows_chap}
    map_email_theo_uid = {str(u.id): u.email for u in ds_nguoi}

    tran_mac_dinh = settings.han_muc_co_tai_khoan
    chi_tiet: list[QuanTriNguoiDungChiTietRead] = []
    tong_tich_luy = 0
    so_vip = 0
    so_hoat_dong = 0
    nguoi_moi_hom_nay = 0
    nguoi_moi_7_ngay = 0

    for u in ds_nguoi:
        uid_str = str(u.id)
        if u.dang_hoat_dong:
            so_hoat_dong += 1
        try:
            ngay_tao = ngay_han_muc(u.created_at) if u.created_at else None
            if ngay_tao == hom_nay:
                nguoi_moi_hom_nay += 1
            if ngay_tao and ngay_tao >= bay_ngay_truoc:
                nguoi_moi_7_ngay += 1
        except Exception:
            pass
        mua_them = max(0, int(u.so_luot_mua_them or 0))
        tong_tich_luy += mua_them
        if mua_them > 0 or (u.tran_hang_ngay_rieng and u.tran_hang_ngay_rieng > tran_mac_dinh):
            so_vip += 1
        tran_u = u.tran_hang_ngay_rieng if (u.tran_hang_ngay_rieng and u.tran_hang_ngay_rieng > 0) else tran_mac_dinh
        da_dung_u = map_hom_nay.get(uid_str, 0)
        con_lai_ngay = max(0, tran_u - da_dung_u)
        chi_tiet.append(
            QuanTriNguoiDungChiTietRead(
                id=u.id,
                email=u.email,
                ten_hien=u.ten_hien or "",
                la_quan_tri=u.la_quan_tri,
                dang_hoat_dong=u.dang_hoat_dong,
                tran_hang_ngay=tran_u,
                tran_hang_ngay_rieng=u.tran_hang_ngay_rieng,
                da_dung_hom_nay=da_dung_u,
                con_lai_hom_nay=con_lai_ngay + mua_them,
                so_luot_mua_them=mua_them,
                tong_trang_da_dich=map_all.get(uid_str, 0),
                so_chapter=map_chap.get(uid_str, 0),
                created_at=u.created_at,
            )
        )

    # Danh sách 15 chapter hoạt động gần đây trên toàn hệ thống
    rows_recent_proj = (
        await session.execute(
            select(Project, func.count(Page.id))
            .outerjoin(Page, Page.project_id == Project.id)
            .group_by(Project.id)
            .order_by(Project.created_at.desc())
            .limit(15)
        )
    ).all()
    chapter_gan_day: list[dict] = []
    for prj, so_tr_prj in rows_recent_proj:
        uid_c = str(prj.chu_so_huu_id) if prj.chu_so_huu_id else ""
        email_chu = map_email_theo_uid.get(uid_c) or ("Khách vãng lai" if prj.chu_khach else "Chưa có chủ")
        chapter_gan_day.append(
            {
                "id": str(prj.id),
                "name": prj.name,
                "email_chu": email_chu,
                "source_lang": prj.source_lang.value if hasattr(prj.source_lang, "value") else str(prj.source_lang),
                "target_lang": prj.target_lang.value if hasattr(prj.target_lang, "value") else str(prj.target_lang),
                "che_do_pipeline": prj.che_do_pipeline.value if hasattr(prj.che_do_pipeline, "value") else str(prj.che_do_pipeline),
                "so_trang": int(so_tr_prj or 0),
                "created_at": prj.created_at.isoformat() if prj.created_at else "",
            }
        )

    # Đếm job đang chạy và job lỗi hôm nay
    viec_dang_chay = int(
        (
            await session.execute(
                select(func.count(Job.id)).where(Job.status.in_((JobStatus.queued, JobStatus.running)))
            )
        ).scalar_one()
        or 0
    )
    viec_loi_hom_nay = int(
        (
            await session.execute(
                select(func.count(Job.id)).where(Job.status == JobStatus.failed)
            )
        ).scalar_one()
        or 0
    )

    # Sức khoẻ máy chủ & Worker AI
    from app.workers.bo_nho import rss_mb

    rss_api = rss_mb()
    rss_worker = None
    worker_tt = "running"
    try:
        moc_w = _json.loads(Path(_os.environ.get("WORKER_RSS_FILE", "/tmp/rss-worker.json")).read_text())
        rss_worker = moc_w.get("rss_mb")
    except Exception:
        pass
    try:
        san_sang = _json.loads(Path(_os.environ.get("WORKER_READY_FILE", "/tmp/worker-ready.json")).read_text()).get("san_sang_luc")
        if san_sang:
            worker_tt = "running"
    except Exception:
        pass

    tt_khoa_ai = await run_in_threadpool(lay_thong_tin_khoa_ai_che, settings)
    he_thong_info = {
        "worker_trang_thai": worker_tt,
        "rss_api_mb": rss_api,
        "rss_worker_mb": rss_worker,
        "llm_configured": settings.llm_configured,
        "llm_model_name": "deepseek-chat" if tt_khoa_ai.get("deepseek_configured") else settings.llm_model_name,
        "detect_engine": settings.detect_engine,
        "translate_default_engine": settings.translate_default_engine,
        "han_muc_khach_la": settings.han_muc_khach_la,
        "han_muc_co_tai_khoan": settings.han_muc_co_tai_khoan,
        "han_muc_ip_khach_la": settings.han_muc_ip_khach_la,
        **tt_khoa_ai,
    }

    nh_ten, nh_stk, nh_chu = await run_in_threadpool(_doc_cau_hinh_ngan_hang_dong, settings)
    ds_don_out = [don_nap.sang_read(d) for d in await don_nap.ds_don_moi_nhat(session, 50)]

    return QuanTriThongKeRead(
        tong_nguoi_dung=len(ds_nguoi),
        nguoi_dung_hoat_dong=so_hoat_dong,
        nguoi_dung_moi_hom_nay=nguoi_moi_hom_nay,
        nguoi_dung_moi_7_ngay=nguoi_moi_7_ngay,
        so_khach_vip=so_vip,
        tong_luot_tich_luy_con_lai=tong_tich_luy,
        trang_dich_hom_nay=trang_hom_nay,
        trang_tai_khoan_hom_nay=trang_tk_hom_nay,
        trang_khach_hom_nay=trang_khach_hom_nay,
        trang_dich_7_ngay=trang_7_ngay,
        trang_dich_toan_thoi_gian=trang_toan_thoi_gian,
        tong_chapter=tong_chapter,
        viec_dang_chay=viec_dang_chay,
        viec_loi_hom_nay=viec_loi_hom_nay,
        han_muc_khach_la=settings.han_muc_khach_la,
        han_muc_co_tai_khoan=settings.han_muc_co_tai_khoan,
        han_muc_ip_khach_la=settings.han_muc_ip_khach_la,
        ty_le_vnd_moi_trang=max(1, settings.ty_le_vnd_moi_trang),
        ngan_hang_ten=nh_ten,
        ngan_hang_so_tk=nh_stk,
        ngan_hang_chu_tk=nh_chu,
        bieu_do_7_ngay=bieu_do_7_ngay,
        phan_bo_ngon_ngu=phan_bo_ngon_ngu,
        chapter_gan_day=chapter_gan_day,
        he_thong=he_thong_info,
        nguoi_dung_chi_tiet=chi_tiet,
        don_nap_gan_day=ds_don_out,
    )


@router_khach.get("/tai-ve/tien-ich-chrome", tags=["tai-ve"])
async def tai_ve_tien_ich_chrome() -> Response:
    """Tải trực tiếp gói cài đặt Tiện ích mở rộng Chrome (.zip) từ Trang chủ."""
    from pathlib import Path

    goc = Path(__file__).resolve().parents[4]
    ung_vien = [
        goc / "dist" / "extension-doc-truyen-v0.3.0.zip",
        goc / "dich-truyen-dang-doc.zip",
    ]
    for p in ung_vien:
        if p.is_file():
            return Response(
                content=p.read_bytes(),
                media_type="application/zip",
                headers={
                    "Content-Disposition": 'attachment; filename="dich-truyen-chrome-extension-v0.3.0.zip"'
                },
            )
    raise HTTPException(status_code=404, detail="Chưa tìm thấy gói cài đặt Tiện ích Chrome.")


@router_khach.get("/tai-ve/app-windows", tags=["tai-ve"])
async def tai_ve_app_windows() -> Response:
    """Tải trực tiếp bộ cài App Windows Dịch Truyện Tự Động Theo Link (.zip) từ Trang chủ."""
    from pathlib import Path

    goc = Path(__file__).resolve().parents[4]
    ung_vien = [
        goc / "dist" / "app-windows-dich-truyen.zip",
    ]
    for p in ung_vien:
        if p.is_file():
            return Response(
                content=p.read_bytes(),
                media_type="application/zip",
                headers={
                    "Content-Disposition": 'attachment; filename="App-Windows-Dich-Truyen-Tu-Dong-v1.0.zip"'
                },
            )
    raise HTTPException(status_code=404, detail="Chưa tìm thấy gói cài đặt App Windows.")



@router_khach.post(
    "/nhan-dang-ngon-ngu",
    response_model=NhanDangNgonNguRead,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["nhan-dang-ngon-ngu"],
)
async def nhan_dang_ngon_ngu_gui(
    file: UploadFile = File(..., description="Một ảnh trang truyện để ĐỌC THỬ"),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    danh_tinh: DanhTinhHanMuc = Depends(danh_tinh_han_muc),
) -> NhanDangNgonNguRead:
    """Đọc thử một ảnh để đoán ngôn ngữ gốc. Trả `202` + `id`, hỏi lại bằng `GET`.

    ## Vì sao đây là đường RIÊNG chứ không phải một `source_lang=auto`

    `Project.source_lang` chọn **engine OCR** (`ja` → manga-ocr, `zh`/`en` → PaddleOCR) và còn đi
    vào hướng đọc lẫn prompt dịch. Muốn "auto" ở đó thì phải cho cột đó nhận `NULL` và sửa ~10 chỗ
    trong pipeline — nhiều rủi ro cho một tính năng phụ trợ.

    Quan trọng hơn: phép đoán **có thể không kết luận được** (ảnh không chữ, quá ít chữ, hệ chữ
    không hỗ trợ). Lúc đó phải **hỏi lại người dùng**, mà một `source_lang=auto` chạy ngầm trong
    pipeline thì không có chỗ nào để hỏi — nó buộc phải chọn bừa một trong ba, hoặc để chapter kẹt.

    ## Trần riêng, KHÔNG trừ hạn mức trang

    Đường này trả về chữ đã đọc được nên nó **là** một dịch vụ OCR: không có trần thì thành OCR miễn
    phí không giới hạn. Nhưng trừ vào hạn mức **trang** cũng sai: khách có 6 lượt sẽ mất 1 lượt chỉ
    vì bấm "Tự nhận", tức tính năng càng dùng càng đắt và người ta sẽ tránh nó rồi quay lại chọn tay
    sai. ⇒ bộ đếm riêng (`services/han_muc_nhan_dang.py`).

    ## Ảnh bị xoá ngay sau khi đọc

    Nó là rác tạm, không ai tải về. Xem `run_nhan_dang_ngon_ngu_job`.
    """
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="File rỗng")
    if len(data) > settings.archive_max_total_bytes:
        raise HTTPException(status_code=413, detail=f"Tệp vượt quá {settings.archive_max_total_mb}MB")
    try:
        if len(data) > settings.max_upload_bytes:
            raise UnsupportedImage("kiem_tra_goi")
        _mime, ext = sniff_image(data)
    except UnsupportedImage as exc:
        # Nếu người dùng thả gói ZIP/CBZ/PDF ở trang chủ rồi bấm "Đọc thử trang đầu", trích đúng
        # trang đầu tiên ra để nhận dạng thay vì báo lỗi 422.
        def _trich_trang_dau():
            if la_pdf(data):
                it = doc_pdf_anh(
                    data, max_pages=settings.archive_max_pages,
                    max_page_bytes=settings.max_upload_bytes, max_px=settings.pdf_render_max_px,
                )
            else:
                it = doc_goi_anh(
                    data, max_pages=settings.archive_max_pages,
                    max_total_bytes=settings.archive_max_total_bytes,
                    max_page_bytes=settings.max_upload_bytes,
                )
            return next(it, None)

        try:
            muc_dau = await run_in_threadpool(_trich_trang_dau)
        except Exception:  # noqa: BLE001
            muc_dau = None
        if muc_dau is None:
            if len(data) > settings.max_upload_bytes:
                raise HTTPException(
                    status_code=413, detail=f"Ảnh vượt quá {settings.max_upload_mb}MB"
                ) from exc
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        data, ext = muc_dau.data, muc_dau.ext

    yc = YeuCauNhanDangNgonNgu(
        chu_so_huu_id=danh_tinh.nguoi_goi.nguoi.id if not danh_tinh.nguoi_goi.la_khach else None,
        chu_khach=danh_tinh.nguoi_goi.khach if danh_tinh.nguoi_goi.la_khach else None,
        trang_thai=JobStatus.queued,
    )
    session.add(yc)
    await session.flush()

    # Giữ lượt SAU khi tệp đã qua kiểm (tệp hỏng không được mất lượt) và TRƯỚC khi ghi xuống kho
    # (hết lượt thì không ghi tệp nào). Ném 429 ở đây ⇒ giao dịch huỷ ⇒ bản ghi vừa flush biến mất.
    tran = settings.so_lan_nhan_dang_ngon_ngu_mot_ngay
    kq, chot_chan = await giu_mot_luot(
        session, danh_tinh=danh_tinh, ngay=ngay_han_muc(), tran=tran
    )
    if not kq.thanh_cong:
        # `tran=` BẮT BUỘC ở đây: `chot.tran` là trần hạn mức TRANG, không phải trần bộ đếm này.
        raise loi_vuot_han_muc(
            danh_tinh=danh_tinh, settings=settings, can=1,
            con_lai=kq.con_lai, chot=chot_chan, tran=tran,
        )

    storage = get_storage()
    yc.duong_anh = await run_in_threadpool(storage.save, f"nhan-dang/{yc.id}{ext}", data)
    await session.commit()
    await session.refresh(yc)

    sent, ly_do = dispatch_nhan_dang_ngon_ngu(yc.id)
    if not sent:
        yc.trang_thai = JobStatus.failed
        yc.loi = ly_do
        await session.commit()
        await session.refresh(yc)

    return _doc_nhan_dang(yc, con_lai=kq.con_lai)


@router_khach.get(
    "/nhan-dang-ngon-ngu/{yeu_cau_id}",
    response_model=NhanDangNgonNguRead,
    tags=["nhan-dang-ngon-ngu"],
)
async def nhan_dang_ngon_ngu_tra(
    yeu_cau_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    danh_tinh: DanhTinhHanMuc = Depends(danh_tinh_han_muc),
) -> NhanDangNgonNguRead:
    """Tra kết quả. `404` nếu không có **hoặc không phải của người gọi**.

    Trả `404` chứ không `403` cho lượt của người khác: `403` là xác nhận "id này tồn tại", tức là
    một đường dò. Cùng luật với `_get_project_or_404`.
    """
    yc = await session.get(YeuCauNhanDangNgonNgu, yeu_cau_id)
    if yc is None or not _cua_nguoi_goi(yc, danh_tinh):
        raise HTTPException(status_code=404, detail="Không tìm thấy lượt nhận dạng này.")
    return _doc_nhan_dang(yc)


def _cua_nguoi_goi(yc: YeuCauNhanDangNgonNgu, danh_tinh: DanhTinhHanMuc) -> bool:
    """Ba nhánh, và nhánh GIỮA là thứ chặn rò rỉ hàng loạt.

    Cùng hình dạng với `quyen.duoc_dung_project`: một bản ghi có `chu_khach` thì **chỉ** khách đó
    xem được — người đã đăng nhập cũng không. Thiếu nhánh giữa thì mọi người đăng nhập đọc được
    lượt nhận dạng của mọi khách.
    """
    goi = danh_tinh.nguoi_goi
    if goi.la_khach:
        return goi.khach is not None and yc.chu_khach == goi.khach
    if yc.chu_khach is not None:
        return False
    return yc.chu_so_huu_id == goi.nguoi.id


def _doc_nhan_dang(
    yc: YeuCauNhanDangNgonNgu, *, con_lai: int | None = None
) -> NhanDangNgonNguRead:
    """`xong` tính ở MỘT chỗ, và giao diện đọc nó thay vì tự suy từ `trang_thai`.

    Tự suy ở phía giao diện là cách chắc chắn để hai bên lệch nhau khi thêm trạng thái mới.
    """
    return NhanDangNgonNguRead(
        id=yc.id,
        trang_thai=yc.trang_thai,
        xong=yc.trang_thai in (JobStatus.done, JobStatus.failed),
        ngon_ngu=yc.ngon_ngu,
        ly_do=yc.ly_do,
        bang_chung=yc.bang_chung,
        loi=yc.loi,
        con_lai_hom_nay=con_lai,
    )


@router_khach.post(
    "/doc-truyen/trang",
    response_model=TrangDocTruyen,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["doc-truyen"],
)
async def doc_truyen_gui_trang(
    file: UploadFile = File(..., description="Ảnh trang truyện lấy từ trang web"),
    source_lang: SourceLang = Form(
        SourceLang.ja, description="Ngôn ngữ chữ TRÊN ẢNH — quyết định chọn engine OCR nào"
    ),
    target_lang: TargetLang = Form(
        TargetLang.vi, description="Ngôn ngữ ĐÍCH muốn dịch sang (vi = Tiếng Việt, en = Tiếng Anh quốc tế)"
    ),
    engine: TranslationEngine = Form(
        TranslationEngine.google_fast,
        description="google_fast (miễn phí, dịch rời rạc) hoặc llm_context (Gemini, giữ mạch văn "
        "+ tự sửa lỗi OCR, tốn token)",
    ),
    che_do: ChePipeline = Form(
        ChePipeline.chi_chu,
        description="chi_chu = chỉ trả toạ độ + chữ dịch để tiện ích PHỦ lên ảnh gốc trên trang "
        "web (mặc định, giữ nguyên hành vi E19). day_du = chạy hết pipeline (xoá chữ gốc + căn "
        "chữ Việt vào bong bóng) ⇒ có ẢNH ĐÃ DỊCH tải về được — đây là chế độ của trang chủ.",
    ),
    font_style: str | None = Form(
        None,
        description="E108 — Font chữ theo thể loại truyện: bangers | romance | historical | comic",
    ),
    tu_dien_rieng: str | None = Form(
        None,
        description="E108 — Sổ tay nhân vật / xưng hô cố định do người dịch chỉ định",
    ),
    tao_chapter_rieng: bool = Form(
        False, description="P1 — tách cấu hình cho lượt dịch này, không dùng hoặc công bố cache cộng đồng",
    ),
    request_key: uuid.UUID | None = Form(None, description="Mã chống trùng bền cho tài khoản + cấu hình riêng"),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    danh_tinh: DanhTinhHanMuc = Depends(danh_tinh_han_muc),
) -> TrangDocTruyen:
    """Nhận một ảnh trang truyện, xếp việc, trả về `page_id` để tra sau.

    **Trả 202, không phải kết quả.** Một trang tốn khoảng 45 giây (đo 05/09, chủ yếu ở bước nhận
    diện) nên giữ kết nối chờ là sai — tiện ích lấy `page_id` rồi hỏi lại.

    Không có request_key: giữ hành vi cũ, mỗi lần gửi là một lượt mới.
    Có request_key: tài khoản đăng nhập + chapter riêng, cùng ảnh/cấu hình trả lại trang cũ;
    khác nội dung trả 409, trang đã xoá trả 410. Không enqueue hoặc trừ lượt lại khi replay.

    `source_lang` mặc định `ja` để không đổi hành vi cũ, nhưng **sai ngôn ngữ là ra chữ vô nghĩa**
    chứ không phải lỗi rõ ràng: chọn `ja` cho trang chữ Latin (vd bản tiếng Anh chính thức trên
    MangaPlus) khiến manga-ocr đọc bậy chữ Latin thành "chữ Nhật", rồi bước dịch dịch tiếp cái bậy
    đó — sai chồng sai mà không endpoint nào báo lỗi được, vì cả hai bước đều "chạy xong bình
    thường". Tiện ích phải để người dùng tự chọn đúng ngôn ngữ của trang đang đọc.

    `engine` mặc định `google_fast` để không tự tốn token khi chưa được phép (M5). Đo được 08/09
    trên MangaPlus: bản miễn phí dịch RỜI RẠC từng dòng, không tự sửa được lỗi OCR đọc dính chữ
    trên font chữ hoa/nghiêng cách điệu — vài dòng ra nguyên tiếng Anh, vài dòng dịch sai nghĩa.
    `llm_context` giữ mạch văn cả trang và được yêu cầu tự suy luận sửa lỗi OCR khi dịch, nhưng
    tốn token Gemini mỗi trang — tiện ích để người dùng tự bật, không âm thầm đổi mặc định toàn hệ
    thống (đổi mặc định sẽ ảnh hưởng mọi luồng khác, không chỉ E19).
    """
    data = await file.read(settings.max_upload_bytes + 1)
    if not data:
        raise HTTPException(status_code=422, detail="File rỗng")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail=f"Ảnh vượt quá {settings.max_upload_mb}MB")
    try:
        _mime, ext = sniff_image(data)
    except UnsupportedImage as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    request_hash = None
    owner_id = None
    if request_key is not None:
        if not danh_tinh.co_tai_khoan or danh_tinh.nguoi_goi.la_khach:
            raise HTTPException(401, "Cần đăng nhập để dùng mã phục hồi lượt dịch.")
        if tao_chapter_rieng is not True:
            raise HTTPException(422, "Mã phục hồi chỉ dùng với cấu hình chapter riêng.")
        from app.services.upload_identity import upload_fingerprint
        from app.services.upload_requests import lock_and_find
        owner_id = danh_tinh.nguoi_goi.nguoi.id
        request_hash = upload_fingerprint(
            data, source_lang=source_lang.value, target_lang=target_lang.value,
            engine=engine.value, che_do=che_do.value, font_style=font_style,
            tu_dien_rieng=tu_dien_rieng, tao_chapter_rieng=True,
        )
        previous = await lock_and_find(session, owner_id, request_key, request_hash)
        if previous is not None:
            result = await doc_truyen_lay_trang(previous.page_id, session=session, danh_tinh=danh_tinh)
            return result.model_copy(update={"request_key": request_key})

    from app.services.upload_artifacts import UploadArtifactGuard
    async with UploadArtifactGuard(session, owner_id, request_key) as artifacts:
        # Replays above remain readable even if engine or quota is now unavailable.
        _kiem_engine(engine, settings, co_tai_khoan=danh_tinh.co_tai_khoan)
        project = await _chapter_doc_nhanh(
            session, danh_tinh.nguoi_goi, source_lang, che_do, target_lang=target_lang,
            rieng=tao_chapter_rieng is True, commit_project=request_key is None,
        )
        artifacts.project_id = project.id
        next_order = (await session.scalar(
            select(func.coalesce(func.max(Page.order), 0) + 1).where(Page.project_id == project.id)
        )) or 1
        page = Page(
            project_id=project.id, image_path="", order=next_order, status=PageStatus.queued,
            # E58 — lưu THẲNG lựa chọn, kể cả `google_fast`. Trước đây `google_fast` bị mã hoá thành
            # `None` với lý do "cả hai đều đọc ra dùng mặc định hệ thống, không khác nhau".
            #
            # Câu đó ĐÚNG khi mặc định hệ thống là `google_fast`, và SAI ngay khi ai đó đổi nó. Đo được
            # trên production 28-09: `TRANSLATE_DEFAULT_ENGINE=llm_context`, nên mọi trang từ trang chủ
            # và từ tiện ích đọc truyện **đều chạy Gemini trả tiền** — dù tiện ích gửi đúng
            # `engine=google_fast` với chú thích của chính nó là "để không tự tốn token Gemini khi người
            # dùng chưa từng bật". Bằng chứng: hai trang dịch qua tiện ích có
            # `translate_engine_override = None` và `/pages/{id}/translation` trả `engine: llm_context`.
            #
            # Đúng cái bẫy mà docstring của `Page.translate_engine_override` đã cảnh báo bằng chữ, và
            # hai endpoint của đường đăng nhập đã sửa theo từ ĐX-3 — chỉ endpoint này còn sót.
            #
            # Tương thích ngược KHÔNG đổi: trang CŨ vẫn `NULL` ⇒ vẫn lùi về mặc định hệ thống y như
            # trước. Chỉ trang MỚI mang đúng lựa chọn của người gửi.
            translate_engine_override=engine,
        )
        session.add(page)
        await session.flush()

        artifacts.page_id = page.id
        # Giữ chỗ SAU khi tệp đã qua kiểm (tệp hỏng không được mất lượt) và TRƯỚC khi ghi xuống kho
        # (hết lượt thì không ghi tệp nào). Ném 429 ở đây ⇒ giao dịch huỷ ⇒ trang vừa flush biến mất.
        await giu_cho_moi_chot(session, danh_tinh, settings, trang_id=page.id)
        if request_key is not None:
            session.add(UploadRequest(owner_id=owner_id, request_key=request_key,
                                      request_hash=request_hash, page_id=page.id))

        storage = get_storage()
        artifacts.storage = storage
        if font_style or tu_dien_rieng:
            from app.services.typeset.chon_font import luu_tuy_chon_du_an
            await run_in_threadpool(
                luu_tuy_chon_du_an, project.id, font_style=font_style, tu_dien_rieng=tu_dien_rieng,
                **({"strict": True} if project.cau_hinh_rieng else {}),
            )

        data = await run_in_threadpool(thu_nho_anh_trang, data, ext, settings.anh_trang_canh_dai_toi_da)
        page.image_path = await run_in_threadpool(
            storage.save_page_image, project.id, page.id, data, ext
        )

        from app.services.bo_nho_anh_dich import (
            ghi_nhan_trang_anh,
            thu_sao_chep_tu_cache,
            tinh_bam_anh,
        )

        bam_anh = tinh_bam_anh(data)
        if settings.doc_truyen_dung_cache_anh:
            trung_cache = await thu_sao_chep_tu_cache(
                session,
                bam_anh=bam_anh,
                source_lang=source_lang,
                target_lang=target_lang,
                engine=engine,
                che_do=che_do,
                dich_page=page,
                storage=storage,
            )
            if trung_cache:
                ghi_nhan_trang_anh(
                    bam_anh, source_lang, engine, che_do, page.id, target_lang=target_lang
                )
                artifacts.commit_attempted = True
                await session.commit()
                artifacts.committed = True
                await session.refresh(page)
                result = await doc_truyen_lay_trang(page.id, session=session, danh_tinh=danh_tinh)
                return result.model_copy(update={"request_key": request_key})

        ghi_nhan_trang_anh(bam_anh, source_lang, engine, che_do, page.id, target_lang=target_lang)
        job = Job(type=JobType.detect, page_id=page.id, status=JobStatus.queued)
        session.add(job)
        if request_key is not None:
            await session.flush()  # Generate job ID before inserting its FK delivery intent.
            session.add(DetectOutbox(job_id=job.id))
        artifacts.commit_attempted = True
        await session.commit()
        artifacts.committed = True
        await session.refresh(page)

        if request_key is not None:
            from app.services.upload_outbox import try_publish_job
            try:
                await run_in_threadpool(try_publish_job, job.id,
                                        publish=lambda jid: dispatch_detect_job(jid, task_id=str(jid)))
            except Exception:
                # The committed intent remains for beat, even if this API process dies.
                logging.getLogger(__name__).exception("outbox publish deferred: job=%s", job.id)
        else:
            sent, ly_do = dispatch_detect_job(job.id)
            if not sent:
                job.error_log = ly_do
                await session.commit()

        return TrangDocTruyen(
            request_key=request_key, page_id=page.id, project_id=project.id, trang_thai=page.status, xong=False,
            cau_hinh_rieng=project.cau_hinh_rieng,
            che_do=project.che_do_pipeline,
            tien_do=await _tien_do_trang(session, page.id),
        )


@router_khach.get(
    "/doc-truyen/yeu-cau/{request_key}", response_model=TrangDocTruyen, tags=["doc-truyen"],
)
async def doc_truyen_tra_yeu_cau(
    request_key: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    danh_tinh: DanhTinhHanMuc = Depends(danh_tinh_han_muc),
) -> TrangDocTruyen:
    """Account-scoped lookup only; 404 absent/unowned, 410 retained deletion tombstone."""
    if not danh_tinh.co_tai_khoan or danh_tinh.nguoi_goi.la_khach:
        raise HTTPException(401, "Cần đăng nhập để tra lượt dịch.")
    from app.services.upload_requests import find_owned
    row = await find_owned(session, danh_tinh.nguoi_goi.nguoi.id, request_key)
    result = await doc_truyen_lay_trang(row.page_id, session=session, danh_tinh=danh_tinh)
    return result.model_copy(update={"request_key": request_key})


@router_khach.get(
    "/doc-truyen/trang/{page_id}", response_model=TrangDocTruyen, tags=["doc-truyen"]
)
async def doc_truyen_lay_trang(
    page_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    danh_tinh: DanhTinhHanMuc = Depends(danh_tinh_han_muc),
) -> TrangDocTruyen:
    """Kết quả của một trang: đang tới đâu, và các bong bóng đã dịch được.

    Trả về **vùng đã có** kể cả khi chưa xong hết — dịch xong bong bóng nào thì tiện ích phủ
    được bong bóng đó, không phải chờ cả trang.
    """
    page = await _get_page_or_404(session, page_id, danh_tinh.nguoi_goi)

    rows = (await session.execute(
        select(TextRegion, OCRResult, TranslationResult)
        .outerjoin(OCRResult, OCRResult.region_id == TextRegion.id)
        .outerjoin(TranslationResult, TranslationResult.region_id == TextRegion.id)
        .where(TextRegion.page_id == page_id)
        .order_by(TextRegion.reading_order.nulls_last(), TextRegion.created_at)
    )).all()

    vung = [
        VungDocTruyen(
            region_id=r.id, x=r.bbox_x, y=r.bbox_y, w=r.bbox_w, h=r.bbox_h,
            thu_tu_doc=r.reading_order,
            chu_goc=o.raw_text if o is not None else None,
            ban_dich=t.translated_text if t is not None else None,
            kem_tin_cay=(
                r.status is RegionStatus.low_confidence
                or (o is not None and o.status is OCRStatus.needs_manual)
            ),
        )
        for r, o, t in rows
    ]

    hong = (await session.execute(
        select(Job.error_log).where(Job.page_id == page_id, Job.status == JobStatus.failed)
        .order_by(Job.created_at.desc()).limit(1)
    )).scalars().first()

    project = await session.get(Project, page.project_id)
    chi_chu = project is not None and project.che_do_pipeline is ChePipeline.chi_chu

    # `xong` phải theo CHẾ ĐỘ của chapter, không phải một danh sách cứng.
    #
    # `translated` là ĐÍCH của chế độ chỉ-chữ — nó không bao giờ tới `typeset_done`, nên chờ
    # trạng thái đó là chờ mãi. Nhưng với chế độ ĐẦY ĐỦ thì `translated` mới là giữa đường: lúc
    # đó **chưa căn chữ**, chưa có ảnh nào để tải. Gộp cả ba trạng thái vào một danh sách cứng
    # (như bản trước E51) khiến chế độ đầy đủ báo "xong" sớm một bước, và client đi lấy một ảnh
    # chưa tồn tại.
    if chi_chu:
        xong = page.status in (PageStatus.translated, PageStatus.typeset_done,
                              PageStatus.ready_for_export)
    else:
        xong = page.status in (PageStatus.typeset_done, PageStatus.ready_for_export)

    if (xong and project is not None and not project.cau_hinh_rieng
            and page.image_path and any(v.ban_dich for v in vung)):
        try:
            from app.services.bo_nho_anh_dich import (
                ghi_nhan_trang_anh,
                luu_snapshot_cache_cong_dong,
                tinh_bam_anh,
            )

            st_cache = get_storage()
            if await run_in_threadpool(st_cache.exists, page.image_path):
                raw_img = await run_in_threadpool(st_cache.read, page.image_path)
                bam_anh = tinh_bam_anh(raw_img)
                eng_cache = page.translate_engine_override or TranslationEngine.llm_context
                ghi_nhan_trang_anh(
                    bam_anh,
                    project.source_lang,
                    eng_cache,
                    project.che_do_pipeline,
                    page.id,
                    target_lang=project.target_lang,
                )
                vung_snap = [
                    {
                        "x": v.x,
                        "y": v.y,
                        "w": v.w,
                        "h": v.h,
                        "reading_order": v.thu_tu_doc or (idx + 1),
                        "chu_goc": v.chu_goc or "",
                        "ban_dich": v.ban_dich or "",
                    }
                    for idx, v in enumerate(vung)
                    if v.ban_dich
                ]
                await luu_snapshot_cache_cong_dong(
                    storage=st_cache,
                    bam_anh=bam_anh,
                    source_lang=project.source_lang,
                    target_lang=project.target_lang,
                    engine=eng_cache,
                    che_do=project.che_do_pipeline,
                    page_id=page.id,
                    vung_snapshot=vung_snap,
                )
        except Exception:  # noqa: BLE001
            pass

    image_width = image_height = None
    if xong and project is not None and project.cau_hinh_rieng:
        # Desktop renders on the ORIGINAL upload; coordinates use the stored resized image.
        def _kich_thuoc_anh_da_luu():
            import io
            from PIL import Image

            with Image.open(io.BytesIO(get_storage().read(page.image_path))) as image:
                return image.size

        image_width, image_height = await run_in_threadpool(_kich_thuoc_anh_da_luu)

    return TrangDocTruyen(
        page_id=page.id,
        cau_hinh_rieng=bool(project is not None and project.cau_hinh_rieng),
        image_width=image_width, image_height=image_height,
        project_id=page.project_id,
        trang_thai=page.status,
        xong=xong,
        che_do=project.che_do_pipeline if project is not None else None,
        # Đường lấy ảnh đã dịch. `None` khi chưa có — CHƯA CHẠY thì để null, không đưa ra một
        # đường dẫn sẽ trả 404.
        anh_da_dich=(
            None if chi_chu or not xong
            else f"/api/v1/doc-truyen/trang/{page.id}/anh"
        ),
        tien_do=await _tien_do_trang(session, page.id),
        vung=vung,
        loi=hong,
    )


@router_khach.get(
    "/doc-truyen/trang/{page_id}/anh",
    tags=["doc-truyen"],
    responses={
        200: {"content": {"image/png": {}}},
        404: {"description": "Chưa có ảnh đã dịch, hoặc trang không thuộc về người gọi"},
    },
)
async def doc_truyen_lay_anh(
    page_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
    danh_tinh: DanhTinhHanMuc = Depends(danh_tinh_han_muc),
) -> Response:
    """Ảnh ĐÃ DỊCH của một trang: ảnh đã xoá chữ gốc + chữ Việt đã căn vào bong bóng.

    **Khách lạ lấy được** — đây là thứ luồng trang chủ trả về, và không có nó thì phần tự động
    tải về (§3 đặc tả) chẳng có gì để tải.

    CHỈ phục vụ tệp đã render sẵn, **không bao giờ tự render**: việc nặng thuộc worker. Ảnh gốc
    không hề bị đụng tới; đây là tệp thứ ba bên cạnh ảnh gốc và ảnh đã xoá chữ.

    Chỉ có ở chế độ `day_du`. Chapter chạy `chi_chu` không sinh ảnh nào — hỏi ở đây sẽ nhận 404
    kèm lý do đọc được, chứ không phải một tệp rỗng.
    """
    page = await _get_page_or_404(session, page_id, danh_tinh.nguoi_goi)
    project = await session.get(Project, page.project_id)
    if project is not None and project.che_do_pipeline is ChePipeline.chi_chu:
        raise HTTPException(
            status_code=404,
            detail="Chapter này chạy chế độ 'chi_chu' (chỉ trả chữ dịch để phủ lên ảnh gốc) nên "
            "KHÔNG sinh ảnh đã dịch. Gửi lại trang với che_do=day_du nếu cần ảnh tải về.",
        )

    storage = get_storage()
    rel = preview_relative_path(page_id)
    if not await run_in_threadpool(storage.exists, rel):
        raise HTTPException(
            status_code=404,
            detail="Chưa có ảnh đã dịch — bước căn chữ chưa chạy xong. Hỏi lại "
            "GET /doc-truyen/trang/{page_id} tới khi `xong` = true.",
        )
    # `no-cache`: đường dẫn cố định theo trang, nên thiếu header này thì sau khi sửa tay người
    # dùng vẫn thấy ảnh cũ.
    return await _phuc_vu_hien_vat(
        storage, rel, "image/png", request, cache_control="no-cache, must-revalidate"
    )


@router_khach.get(
    "/doc-truyen/trang/{page_id}/anh-goc",
    tags=["doc-truyen"],
    responses={
        200: {"content": {"image/*": {}}},
        404: {"description": "Không còn ảnh gốc hoặc trang không thuộc về người gọi"},
    },
)
async def doc_truyen_lay_anh_goc(
    page_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
    danh_tinh: DanhTinhHanMuc = Depends(danh_tinh_han_muc),
) -> Response:
    """Ảnh GỐC của trang dịch nhanh (dùng cho xem trước Trước/Sau khi người dùng tải lên gói
    ZIP/CBZ/PDF ở trang chủ, nơi trình duyệt không có tệp ảnh rời trong RAM)."""
    page = await _get_page_or_404(session, page_id, danh_tinh.nguoi_goi)
    storage = get_storage()
    if not await run_in_threadpool(storage.exists, page.image_path):
        raise HTTPException(
            status_code=404,
            detail="Không còn tệp ảnh gốc trên máy chủ lưu trữ.",
        )
    mime, _ = mimetypes.guess_type(page.image_path)
    return await _phuc_vu_hien_vat(
        storage, page.image_path, mime or "application/octet-stream", request
    )


@router_khach.post(
    "/doc-truyen/goi",
    response_model=ArchiveAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["doc-truyen"],
)
async def doc_truyen_gui_goi(
    file: UploadFile = File(..., description="Gói ZIP/CBZ/PDF chứa các trang truyện"),
    source_lang: SourceLang = Form(
        SourceLang.ja, description="Ngôn ngữ chữ TRÊN ẢNH — quyết định chọn engine OCR nào"
    ),
    target_lang: TargetLang = Form(
        TargetLang.vi, description="Ngôn ngữ ĐÍCH muốn dịch sang (vi = Tiếng Việt, en = Tiếng Anh quốc tế)"
    ),
    engine: TranslationEngine = Form(
        TranslationEngine.google_fast,
        description="google_fast (miễn phí) hoặc llm_context (Gemini, giữ mạch văn, tốn token)",
    ),
    che_do: ChePipeline = Form(
        ChePipeline.day_du,
        description="day_du = xoá chữ gốc + căn chữ Việt vào bong bóng (mặc định cho trang chủ); "
        "chi_chu = chỉ trả toạ độ + chữ dịch.",
    ),
    font_style: str | None = Form(
        None,
        description="E108 — Font chữ theo thể loại truyện: bangers | romance | historical | comic",
    ),
    tu_dien_rieng: str | None = Form(
        None,
        description="E108 — Sổ tay nhân vật / xưng hô cố định do người dịch chỉ định",
    ),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    danh_tinh: DanhTinhHanMuc = Depends(danh_tinh_han_muc),
) -> ArchiveAccepted:
    """E99 (Chuẩn Ichigo Reader) — Nhận trực tiếp gói `.zip`, `.cbz`, `.pdf` ngay trên màn hình
    trang chủ (`router_khach`, hỗ trợ cả khách chưa đăng nhập lẫn tài khoản đã đăng nhập).

    Áp dụng đầy đủ các chốt an toàn của `upload_archive`:
    - Chặn zip-bomb, path traversal, gói lồng gói (`doc_goi_anh` / `doc_pdf_anh`).
    - Kiểm tra tổng số lượt còn lại (`con_du_khong`) TRƯỚC khi giải nén từng trang để nếu thiếu
      lượt thì báo 429 ngay lập tức, không tiêu nửa chừng.
    - Tận dụng bộ nhớ đệm SHA-256 (`thu_sao_chep_tu_cache`) cho các trang trùng nội dung.
    """
    _kiem_engine(engine, settings, co_tai_khoan=danh_tinh.co_tai_khoan)

    project = await _chapter_doc_nhanh(
        session, danh_tinh.nguoi_goi, source_lang, che_do, target_lang=target_lang
    )
    if font_style or tu_dien_rieng:
        from app.services.typeset.chon_font import luu_tuy_chon_du_an

        await run_in_threadpool(
            luu_tuy_chon_du_an,
            project.id,
            font_style=font_style,
            tu_dien_rieng=tu_dien_rieng,
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="File rỗng")
    if len(data) > settings.archive_max_total_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Gói vượt quá {settings.archive_max_total_mb}MB",
        )

    def _mo_goi():
        if la_pdf(data):
            return doc_pdf_anh(
                data,
                max_pages=settings.archive_max_pages,
                max_page_bytes=settings.max_upload_bytes,
                max_px=settings.pdf_render_max_px,
            )
        return doc_goi_anh(
            data,
            max_pages=settings.archive_max_pages,
            max_total_bytes=settings.archive_max_total_bytes,
            max_page_bytes=settings.max_upload_bytes,
        )

    try:
        trang_iter = await run_in_threadpool(_mo_goi)
    except ArchiveTooLarge as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except ArchiveError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    await con_du_khong(session, danh_tinh, settings, so_trang=trang_iter.so_muc)

    next_order = (
        await session.scalar(
            select(func.coalesce(func.max(Page.order), 0) + 1).where(Page.project_id == project.id)
        )
    ) or 1

    from app.services.bo_nho_anh_dich import (
        ghi_nhan_trang_anh,
        thu_sao_chep_tu_cache,
        tinh_bam_anh,
    )

    storage = get_storage()
    da_nhan: list[TrangTrongGoiAccepted] = []
    jobs: list[uuid.UUID] = []
    da_luu: list[str] = []
    try:
        while True:
            muc = await run_in_threadpool(next, trang_iter, None)
            if muc is None:
                break

            page = Page(
                project_id=project.id,
                image_path="",
                order=next_order,
                status=PageStatus.queued,
                translate_engine_override=engine,
            )
            session.add(page)
            await session.flush()

            await giu_cho_moi_chot(session, danh_tinh, settings, trang_id=page.id)

            du_lieu = await run_in_threadpool(
                thu_nho_anh_trang, muc.data, muc.ext, settings.anh_trang_canh_dai_toi_da
            )
            page.image_path = await run_in_threadpool(
                storage.save_page_image, project.id, page.id, du_lieu, muc.ext
            )
            da_luu.append(page.image_path)

            bam_anh = tinh_bam_anh(du_lieu)
            trung_cache = False
            if settings.doc_truyen_dung_cache_anh:
                trung_cache = await thu_sao_chep_tu_cache(
                    session,
                    bam_anh=bam_anh,
                    source_lang=source_lang,
                    engine=engine,
                    che_do=che_do,
                    dich_page=page,
                    storage=storage,
                    target_lang=target_lang,
                )
            ghi_nhan_trang_anh(bam_anh, source_lang, engine, che_do, page.id, target_lang=target_lang)

            if trung_cache:
                job_id_tra = page.id
            else:
                job = Job(type=JobType.detect, page_id=page.id, status=JobStatus.queued)
                session.add(job)
                await session.flush()
                jobs.append(job.id)
                job_id_tra = job.id

            da_nhan.append(
                TrangTrongGoiAccepted(
                    page_id=page.id, job_id=job_id_tra, order=next_order, ten_trong_goi=muc.ten
                )
            )
            next_order += 1
    except ArchiveEmpty as exc:
        await _huy_me_goi(session, storage, da_luu)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ArchiveError as exc:
        await _huy_me_goi(session, storage, da_luu)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except HTTPException:
        await _huy_me_goi(session, storage, da_luu)
        raise

    await session.commit()

    for job_id in jobs:
        sent, reason = dispatch_detect_job(job_id)
        if not sent:
            job = await session.get(Job, job_id)
            if job is not None:
                job.error_log = reason
    await session.commit()

    return ArchiveAccepted(
        project_id=project.id,
        so_trang=len(da_nhan),
        bo_qua=max(0, trang_iter.so_muc - len(da_nhan)),
        trang=da_nhan,
    )


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED, tags=["projects"])
async def create_project(payload: ProjectCreate, session: AsyncSession = Depends(get_session), nguoi: NguoiDung = Depends(nguoi_dung_hien_tai)) -> Project:
    project = Project(
        name=payload.name,
        source_lang=payload.source_lang,
        target_lang=payload.target_lang,
        intended_use=payload.intended_use,
        # Chapter tạo từ slice B trở đi LUÔN có chủ ngay từ đầu — không có đường nào sinh
        # thêm chapter vô chủ nữa.
        chu_so_huu_id=nguoi.id,
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    if payload.font_style or payload.tu_dien_rieng:
        from app.services.typeset.chon_font import luu_tuy_chon_du_an

        await run_in_threadpool(
            luu_tuy_chon_du_an,
            project.id,
            font_style=payload.font_style,
            tu_dien_rieng=payload.tu_dien_rieng,
        )
    return project


@router.get("/projects", response_model=list[ProjectRead], tags=["projects"])
async def list_projects(
    session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> list[Project]:
    """Chapter của tôi + chapter chưa có chủ.

    Endpoint này **mới có ở slice B**. Trước đó giao diện tự nhớ id chapter trong máy, nên
    người dùng mới đăng nhập trên máy khác sẽ không thấy gì cả.

    Chapter chưa có chủ (`chu_so_huu_id IS NULL`) chỉ hiện cho **quản trị**, để họ nhận hoặc
    dọn. Giao diện phải gắn nhãn phân biệt.
    """
    dieu_kien = Project.chu_so_huu_id == nguoi.id
    if nguoi.la_quan_tri:
        # Vô chủ = không thuộc tài khoản nào VÀ không thuộc khách lạ nào (thiếu vế sau là lộ
        # tên/id chapter của mọi khách). Chỉ quản trị — cùng luật với `duoc_dung_project`.
        dieu_kien = dieu_kien | (
            Project.chu_so_huu_id.is_(None) & Project.chu_khach.is_(None)
        )
    return list(
        (await session.execute(
            select(Project).where(dieu_kien).order_by(Project.created_at.desc())
        )).scalars()
    )


@router.post(
    "/projects/{project_id}/claim", response_model=ProjectRead, tags=["projects"]
)
async def claim_project(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> Project:
    """Nhận một chapter chưa có chủ về mình.

    Chỉ nhận được chapter **đang không có chủ**. Chapter đã có chủ thì `_get_project_or_404`
    đã chặn từ trước — không có đường nào cướp chapter của người khác.
    """
    project = await _get_project_or_404(session, project_id, nguoi)
    if project.chu_so_huu_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Chapter này đã có chủ rồi.",
        )
    project.chu_so_huu_id = nguoi.id
    await session.commit()
    await session.refresh(project)
    return project


@router.post(
    "/projects/{project_id}/release", response_model=ProjectRead, tags=["projects"]
)
async def release_project(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> Project:
    """Nhả chapter về "chưa có chủ" — đường NGƯỢC của `claim`.

    Vì sao cần: có `claim` mà không có đường ngược lại là một cái bẫy một chiều. Nhận nhầm một
    chapter là nó khoá cứng vào tài khoản đó vĩnh viễn, và người khác **không có cách nào** lấy
    lại kể cả khi đó là việc của họ — vì `_get_project_or_404` đã chặn từ trước. Đo được ngay
    trong lượt kiểm chứng B1: một tài khoản thử nhận nhầm chapter thật, và không có đường nào
    trả lại ngoài sửa tay trong CSDL.

    Nhả xong thì chapter về trạng thái vô chủ: chỉ quản trị thấy và nhận lại được.
    Đây KHÔNG phải chuyển chủ cho một người cụ thể — chuyển chủ cần biết tên người nhận, tức là
    cần một danh bạ người dùng, và đó là chuyện khác.
    """
    project = await _get_project_or_404(session, project_id, nguoi)
    if project.chu_so_huu_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Chapter này vốn đã chưa có chủ.",
        )
    project.chu_so_huu_id = None
    await session.commit()
    await session.refresh(project)
    return project


@router.get("/projects/{project_id}", response_model=ProjectDetail, tags=["projects"])
async def get_project(project_id: uuid.UUID, session: AsyncSession = Depends(get_session), nguoi: NguoiDung = Depends(nguoi_dung_hien_tai)) -> Project:
    stmt = select(Project).where(Project.id == project_id).options(selectinload(Project.pages))
    project = (await session.execute(stmt)).scalar_one_or_none()
    if project is None or not duoc_dung_project(nguoi, project):
        raise HTTPException(status_code=404, detail=LOI_KHONG_THAY)
    ket = ProjectDetail.model_validate(project)
    ids = [pg.id for pg in ket.pages]
    if ids:
        tran, co_canh = await _dem_theo_trang(
            session, TypesetResult, TypesetResult.fit_status == FitStatus.overflow_warning, ids
        )
        can_xem, co_cham = await _dem_theo_trang(
            session, RegionQualityAssessment,
            RegionQualityAssessment.review_status == ReviewStatus.needs_review, ids,
        )
        for pg in ket.pages:
            pg.so_vung_tran_khung = tran.get(pg.id, 0) if pg.id in co_canh else None
            pg.so_vung_can_xem = can_xem.get(pg.id, 0) if pg.id in co_cham else None
    return ket


async def _dem_theo_trang(session: AsyncSession, bang, dieu_kien, page_ids: list) -> tuple[dict, set]:
    """Đếm theo trang các dòng của `bang` (nối qua `region_id`) thoả `dieu_kien`, kèm tập trang CÓ
    dòng nào của bảng đó — để phân biệt "0" (đã có dữ liệu, không vùng nào) với "chưa có dữ liệu".
    Hai câu GROUP BY cho cả chapter, không phải N lời gọi theo trang."""
    noi = select(TextRegion.page_id).join(bang, bang.region_id == TextRegion.id).where(
        TextRegion.page_id.in_(page_ids)
    )
    co = set((await session.execute(noi.distinct())).scalars())
    dem = dict((await session.execute(
        select(TextRegion.page_id, func.count()).join(bang, bang.region_id == TextRegion.id)
        .where(TextRegion.page_id.in_(page_ids), dieu_kien).group_by(TextRegion.page_id)
    )).all())
    return dem, co


@router.post(
    "/projects/{project_id}/pages",
    response_model=PageAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["pages"],
)
async def upload_page(
    project_id: uuid.UUID,
    file: UploadFile = File(..., description="Ảnh trang manga (JPEG/PNG/WEBP)"),
    engine: TranslationEngine | None = Form(
        None,
        description="ĐX-3 — engine dịch cho ĐÚNG trang này: google_fast (miễn phí) hoặc "
        "llm_context (Gemini, giữ mạch văn, TỐN token). Bỏ trống = mặc định hệ thống.",
    ),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
    danh_tinh: DanhTinhHanMuc = Depends(danh_tinh_han_muc),
) -> PageAccepted:
    """Nhận ảnh trang, lưu file, tạo Page(status=queued) + Job(type=detect, status=queued).

    M1 chỉ ghi record Job vào hàng đợi (chưa dispatch worker thật — bắt đầu ở M2).

    `engine` (ĐX-3) ghi vào `Page.translate_engine_override`, và
    `enqueue_translate_after_inpaint` đọc lại đúng cột đó khi tới lượt dịch. **Hai đầu phải đi
    cùng nhau** — trước ĐX-3 chỉ có đầu ghi, đầu đọc của pipeline đầy đủ cố ý bỏ qua cột này nên
    lựa chọn của người dùng rơi vào hư không mà không báo lỗi.

    Bỏ trống `engine` ⇒ cột để NULL ⇒ lùi về `settings.translate_default_engine` y như trước.
    Không bao giờ tự chọn `llm_context` hộ người dùng: engine đó tốn token thật (M5).
    """
    _kiem_engine(engine, settings)

    project = await _get_project_or_404(session, project_id, nguoi)

    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="File rỗng")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413, detail=f"Ảnh vượt quá {settings.max_upload_mb}MB"
        )
    try:
        _mime, ext = sniff_image(data)
    except UnsupportedImage as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    next_order = (
        await session.scalar(
            select(func.coalesce(func.max(Page.order), 0) + 1).where(Page.project_id == project.id)
        )
    ) or 1

    page = Page(
        project_id=project.id,
        image_path="",  # gán sau khi biết page.id để đặt tên file theo id
        order=next_order,
        status=PageStatus.queued,
        translate_engine_override=engine,
    )
    session.add(page)
    await session.flush()  # lấy page.id, chưa commit

    # Xem ghi chú ở `doc_truyen_gui_trang`: sau kiểm tệp, trước khi ghi kho.
    await giu_cho_moi_chot(session, danh_tinh, settings, trang_id=page.id)

    storage = get_storage()
    data = await run_in_threadpool(thu_nho_anh_trang, data, ext, settings.anh_trang_canh_dai_toi_da)
    page.image_path = await run_in_threadpool(
        storage.save_page_image, project.id, page.id, data, ext
    )

    job = Job(type=JobType.detect, page_id=page.id, status=JobStatus.queued)
    session.add(job)
    await session.commit()
    await session.refresh(page)
    await session.refresh(job)

    # M2: đẩy việc sang worker. Chỉ enqueue — KHÔNG chờ detect chạy xong trong request.
    sent, reason = dispatch_detect_job(job.id)
    if not sent:
        job.error_log = reason
        await session.commit()

    return PageAccepted(page_id=page.id, status=page.status, job_id=job.id)


async def _huy_me_goi(
    session: AsyncSession, storage: IObjectStorage, da_luu: list[str]
) -> None:
    """Huỷ một mẻ gói: lùi CSDL rồi dọn các tệp đã ghi.

    Thứ tự quan trọng — lùi CSDL TRƯỚC. Xoá tệp trước mà `rollback` hỏng thì còn lại dòng trỏ
    vào tệp không tồn tại, tức giao diện hiện trang có thật nhưng bấm vào thì vỡ.

    Xoá tệp hỏng thì **ghi lại**, không nuốt: §2.6 đặc tả nói rõ dọn thất bại mà không ai biết
    thì đĩa đầy dần. Nhưng cũng KHÔNG để lỗi dọn dẹp che mất lỗi thật đang trên đường ném ra —
    người dùng cần biết "hết hạn mức", không phải "xoá tệp tạm hỏng".
    """
    await session.rollback()
    for rel in da_luu:
        try:
            await run_in_threadpool(storage.delete, rel)
        except Exception:  # noqa: BLE001 — xem docstring: ghi lại, không che lỗi thật
            logger.exception("Dọn tệp sau khi huỷ mẻ gói thất bại: %s", rel)


@router.post(
    "/projects/{project_id}/pages/archive",
    response_model=ArchiveAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["pages"],
)
async def upload_archive(
    project_id: uuid.UUID,
    file: UploadFile = File(..., description="Gói ZIP/CBZ chứa các trang ảnh"),
    engine: TranslationEngine | None = Form(
        None,
        description="ĐX-3 — engine dịch áp cho MỌI trang trong gói. Bỏ trống = mặc định hệ thống.",
    ),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
    danh_tinh: DanhTinhHanMuc = Depends(danh_tinh_han_muc),
) -> ArchiveAccepted:
    """ĐX-2 — nhận **cả chapter trong một gói** ZIP/CBZ thay vì tải từng trang một.

    Vì sao đáng làm: một chapter 24 trang trước đây là 24 lượt thao tác. Đây là khoảng cách thao
    tác lớn nhất đo được khi so với công cụ cùng loại (xem `REPORT_ICHIGO_BLACKBOX_BENCHMARK.md`
    §7 G2), và nó không đụng gì tới chất lượng dịch — thuần tuý là lớp nhận việc.

    **Thứ tự trang sắp bằng khoá tự nhiên** (`p2` trước `p10`), không theo thứ tự lưu trong gói.
    Sắp sai là hỏng im lặng: file vẫn xuất ra bình thường, chỉ nội dung lộn trang. Phản hồi trả
    kèm `ten_trong_goi` của từng trang để đối chiếu được ngay.

    Mọi phép chặn gói độc (bom giải nén, đường dẫn thoát thư mục, quá nhiều mục, gói lồng gói)
    nằm ở `app/services/archive.py` và chạy **xong hết trước khi** chạm vào CSDL.

    **PDF cũng nhận** (ĐX-2b): mỗi trang được **dựng lại thành ảnh** ở cạnh dài
    `PDF_RENDER_MAX_PX` (mặc định 1600px), không phải trích ảnh nhúng. Lý do ở
    `app/services/pdf.py`: trang truyện trong PDF có thể là ảnh nền cộng chữ vector, và trích
    ảnh nhúng sẽ **mất chữ mà không báo lỗi**.

    Cả ba loại đầu vào (`.zip`, `.cbz`, `.pdf`) đi chung MỘT nhánh ghi CSDL — rẽ nhánh theo chữ
    ký đầu file, không theo đuôi tệp.
    """
    _kiem_engine(engine, settings)

    project = await _get_project_or_404(session, project_id, nguoi)

    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="File rỗng")
    if len(data) > settings.archive_max_total_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Gói vượt quá {settings.archive_max_total_mb}MB",
        )

    def _mo_goi():
        # Rẽ theo CHỮ KÝ ĐẦU FILE, không theo đuôi tệp — đuôi do người gửi đặt.
        # Cả hai đường trả về cùng hình dạng (`so_muc` + lặp ra `TrangTrongGoi`) nên phần bên
        # dưới chỉ có MỘT nhánh ghi CSDL, thay vì hai nhánh gần giống nhau rồi lệch dần.
        if la_pdf(data):
            return doc_pdf_anh(
                data,
                max_pages=settings.archive_max_pages,
                max_page_bytes=settings.max_upload_bytes,
                max_px=settings.pdf_render_max_px,
            )
        return doc_goi_anh(
            data,
            max_pages=settings.archive_max_pages,
            max_total_bytes=settings.archive_max_total_bytes,
            # Trần MỖI trang dùng chung với ảnh lẻ: một trang trong gói không có lý do gì được
            # phép to hơn chính trang đó tải lên riêng.
            max_page_bytes=settings.max_upload_bytes,
        )

    try:
        trang_iter = await run_in_threadpool(_mo_goi)
    except ArchiveTooLarge as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except ArchiveError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Chặn sớm: gói 24 trang mà còn 3 lượt thì từ chối NGAY, đừng dựng lại 24 ảnh PDF rồi mới
    # biết. Đây chỉ là phép ĐỌC, không giữ chỗ — cổng thật là `giu_cho_moi_chot` trong vòng lặp.
    await con_du_khong(session, danh_tinh, settings, so_trang=trang_iter.so_muc)

    next_order = (
        await session.scalar(
            select(func.coalesce(func.max(Page.order), 0) + 1).where(Page.project_id == project.id)
        )
    ) or 1

    storage = get_storage()
    da_nhan: list[TrangTrongGoiAccepted] = []
    jobs: list[uuid.UUID] = []
    #: Đường dẫn các tệp ĐÃ ghi xuống kho. Huỷ mẻ thì `rollback` gỡ được các dòng CSDL nhưng
    #: KHÔNG gỡ tệp — không dọn là đĩa đầy dần trong im lặng, đúng thứ §2.5 đặc tả cấm.
    da_luu: list[str] = []
    try:
        while True:
            # Lấy từng trang một: giữ đúng MỘT ảnh trong bộ nhớ thay vì cả gói đã bung.
            # `next(it, None)` chạy trong threadpool vì đọc zip là việc chặn.
            muc = await run_in_threadpool(next, trang_iter, None)
            if muc is None:
                break

            page = Page(
                project_id=project.id,
                image_path="",
                order=next_order,
                status=PageStatus.queued,
                translate_engine_override=engine,
            )
            session.add(page)
            await session.flush()

            await giu_cho_moi_chot(session, danh_tinh, settings, trang_id=page.id)

            du_lieu = await run_in_threadpool(
                thu_nho_anh_trang, muc.data, muc.ext, settings.anh_trang_canh_dai_toi_da
            )
            page.image_path = await run_in_threadpool(
                storage.save_page_image, project.id, page.id, du_lieu, muc.ext
            )
            da_luu.append(page.image_path)
            job = Job(type=JobType.detect, page_id=page.id, status=JobStatus.queued)
            session.add(job)
            await session.flush()

            da_nhan.append(
                TrangTrongGoiAccepted(
                    page_id=page.id, job_id=job.id, order=next_order, ten_trong_goi=muc.ten
                )
            )
            jobs.append(job.id)
            next_order += 1
    except ArchiveEmpty as exc:
        # Gói mở được nhưng không có ảnh nào. Lùi sạch — thà báo lỗi còn hơn để lại một chapter
        # rỗng trông như đã nhận việc.
        await _huy_me_goi(session, storage, da_luu)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ArchiveError as exc:
        await _huy_me_goi(session, storage, da_luu)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except HTTPException:
        # Hết hạn mức giữa chừng (429). Từ chối NGUYÊN mẻ — xử lý một phần âm thầm sẽ khiến
        # người dùng nhận nửa chapter mà không có cách nào biết thiếu trang nào.
        await _huy_me_goi(session, storage, da_luu)
        raise

    await session.commit()

    # Đẩy việc SAU khi commit: job trỏ tới trang chưa commit là job trỏ vào hư không.
    for job_id in jobs:
        sent, reason = dispatch_detect_job(job_id)
        if not sent:
            job = await session.get(Job, job_id)
            if job is not None:
                job.error_log = reason
    await session.commit()

    return ArchiveAccepted(
        project_id=project.id,
        so_trang=len(da_nhan),
        # Chênh lệch giữa số mục ứng viên (đếm thật lúc mở gói) và số trang nhận được = số mục
        # bị bỏ qua vì không phải ảnh. Hiện ra để "gói 20 file mà chỉ vào 18 trang" là chuyện
        # nhìn thấy được, không phải chuyện phải đi đoán.
        bo_qua=max(0, trang_iter.so_muc - len(da_nhan)),
        trang=da_nhan,
    )


@router.get("/pages/{page_id}", response_model=PageRead, tags=["pages"])
async def get_page(page_id: uuid.UUID, session: AsyncSession = Depends(get_session), nguoi: NguoiDung = Depends(nguoi_dung_hien_tai)) -> Page:
    return await _get_page_or_404(session, page_id, nguoi)


@router.get("/pages/{page_id}/regions", response_model=list[RegionRead], tags=["pages"])
async def list_page_regions(
    page_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> list[RegionRead]:
    """Trả [] cho tới khi M2 (detect) chạy thật — không bịa region."""
    await _get_page_or_404(session, page_id, nguoi)
    stmt = (
        select(TextRegion)
        .where(TextRegion.page_id == page_id)
        .order_by(TextRegion.reading_order.nulls_last(), TextRegion.created_at)
    )
    regions = (await session.execute(stmt)).scalars().all()
    return [RegionRead.from_model(r) for r in regions]


async def _giu_suat_chay_lai_trang(
    session: AsyncSession,
    page_id: uuid.UUID,
    job_type: JobType,
    settings: Settings,
) -> None:
    """Chặn gọi `retry-*` / `re-translate` vô hạn trên cùng một trang để đốt token LLM / CPU.

    Dùng lại sổ cái `so_cai_han_muc` với tiền tố `chay-lai:<page_id>:<buoc>` (chứa dấu `:` nên
    không bao giờ lẫn vào bộ đếm hạn mức trang). Chỉ tính các lượt người dùng bấm chạy lại qua
    HTTP; chuỗi tự động `detect -> ocr -> inpaint -> translate` không đi qua đây.
    """
    tran = settings.so_lan_chay_lai_toi_da_moi_trang
    if tran <= 0:
        return
    kq = await giu_cho_bat_dong_bo(
        session,
        khoa=f"chay-lai:{uuid.uuid4()}",
        loai=LoaiChuThe.khach_ip,
        chu_the=f"chay-lai:{page_id}:{job_type.value}",
        ngay=ngay_han_muc(),
        so_trang=1,
        tran=tran,
    )
    if not kq.thanh_cong:
        reset = moc_reset_ke_tiep()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(max(0, int((reset - bay_gio()).total_seconds())))},
            detail={
                "loi": "vuot_tran_chay_lai_trang",
                "buoc": job_type.value,
                "tran_moi_trang": tran,
                "reset_luc": reset.isoformat(),
                "thong_diep": f"Trang này đã chạy lại bước '{job_type.value}' tối đa {tran} lần "
                "trong hôm nay.",
            },
        )


@router.post(
    "/pages/{page_id}/retry-detect",
    response_model=PageAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["pages"],
)
async def retry_detect(
    page_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> PageAccepted:
    """Xếp lại việc detect cho 1 page (dùng sau khi detection_failed hoặc muốn chạy lại).

    Vẫn chỉ enqueue — không chạy detect trong request.
    """
    page = await _get_page_or_404(session, page_id, nguoi)
    if page.status is PageStatus.detecting:
        raise HTTPException(status_code=409, detail="Page đang detect, không xếp thêm việc trùng")

    await _giu_suat_chay_lai_trang(session, page.id, JobType.detect, settings)

    job = Job(type=JobType.detect, page_id=page.id, status=JobStatus.queued)
    session.add(job)
    await session.commit()
    await session.refresh(job)

    sent, reason = dispatch_detect_job(job.id)
    if not sent:
        job.error_log = reason
        await session.commit()

    return PageAccepted(page_id=page.id, status=page.status, job_id=job.id)


@router.get("/pages/{page_id}/jobs", response_model=list[JobRead], tags=["pages"])
async def list_page_jobs(
    page_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> list[Job]:
    """Lịch sử job của một trang, MỚI NHẤT trước (P3j).

    Vì sao cần: trước P3j chỉ tra được job theo id, mà id thì chỉ có ngay lúc bấm. Trang đứng im
    vì worker chết giữa chừng nhìn từ giao diện **y hệt** trang đang chạy chậm — người vận hành
    không có đường nào biết lý do. Đây là đường đó.

    `error_log` của job hỏng là chỗ chứa lý do đọc được (vd `worker_died: …`).
    """
    await _get_page_or_404(session, page_id, nguoi)
    return list(
        (await session.execute(
            select(Job).where(Job.page_id == page_id).order_by(Job.created_at.desc())
        )).scalars()
    )


@router.get(
    "/projects/{project_id}/failed-jobs", response_model=list[JobRead], tags=["projects"]
)
async def list_project_failed_jobs(
    project_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> list[Job]:
    """Việc HỎNG mới nhất của mỗi trang trong chapter — một lời gọi cho cả chapter (F1).

    Vì sao cần thêm, khi đã có `/pages/{id}/jobs`: đường cũ hỏi TỪNG trang, nên màn tiến độ chỉ
    dám hỏi khi người dùng bấm "Vì sao?". Hậu quả đo được 04/09: bước căn chữ chết sau 34 mili
    giây, màn hình vẫn quay "đang cập nhật…" và người dùng ngồi đợi 10 phút một việc đã chết,
    vì không ai nghĩ tới chuyện phải bấm mới biết.

    Chỉ trả **job hỏng mới nhất của mỗi trang**: một trang chạy lại 5 lần rồi hỏng 5 lần thì thứ
    người dùng cần là lý do lần cuối, không phải cả tập lịch sử.
    """
    await _get_project_or_404(session, project_id, nguoi)
    rows = list((await session.execute(
        select(Job)
        .join(Page, Page.id == Job.page_id)
        .where(Page.project_id == project_id, Job.status == JobStatus.failed)
        .order_by(Job.page_id, Job.created_at.desc())
    )).scalars())
    moi_nhat: dict[uuid.UUID, Job] = {}
    for job in rows:
        moi_nhat.setdefault(job.page_id, job)
    return list(moi_nhat.values())


@router.post("/pages/{page_id}/fit-translation", status_code=202, tags=["translate"])
async def rut_gon_cho_vua_khung(
    page_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> dict:
    """Dịch lại **ngắn hơn** những vùng đang tràn khung, rồi căn chữ lại (E18).

    Vì sao phải bấm tay chứ không tự chạy: rút gọn là **làm mất chữ** của bản dịch đầy đủ. Máy
    tự quyết định bỏ bớt lời thoại của người khác là việc không ai xin.

    Vùng người dùng **đã sửa tay** không bị đụng tới, và số vùng bị bỏ qua được trả về để nói rõ.
    """
    page = await session.get(Page, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="page_not_found")
    await bao_dam_quyen(session, nguoi, page)

    so_tran = int(await session.scalar(
        select(func.count()).select_from(TypesetResult)
        .join(TextRegion, TextRegion.id == TypesetResult.region_id)
        .where(TextRegion.page_id == page_id,
               TypesetResult.fit_status == FitStatus.overflow_warning)
    ) or 0)
    if so_tran == 0:
        # Không có gì tràn thì KHÔNG gọi mô hình: hỏi suông vẫn tốn token, và bản dịch đang
        # vừa khung mà đem rút gọn là làm mất chữ vô cớ.
        raise HTTPException(
            status_code=422,
            detail="khong_co_vung_tran: trang này không có vùng nào tràn khung để rút gọn",
        )

    await _giu_suat_chay_lai_trang(session, page_id, JobType.translate, settings)

    job = Job(type=JobType.translate, page_id=page_id, status=JobStatus.queued)
    session.add(job)
    await session.commit()
    await session.refresh(job)

    sent, reason = dispatch_rut_gon_job(job.id)
    if not sent:
        job.error_log = reason
        await session.commit()
    return {"job_id": str(job.id), "page_id": str(page_id), "so_vung_tran": so_tran,
            "status": job.status.value, "detail": reason}


@router.get("/pages/{page_id}/ocr", response_model=list[OCRResultRead], tags=["pages"])
async def list_page_ocr(
    page_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> list[OCRResult]:
    """Kết quả OCR theo từng region của page (M3).

    Trả `[]` khi job OCR chưa chạy — không bịa text. `confidence = null` là BÌNH THƯỜNG
    với engine manga-ocr (thư viện không cung cấp điểm tin cậy), không phải lỗi.
    """
    await _get_page_or_404(session, page_id, nguoi)
    stmt = (
        select(OCRResult)
        .join(TextRegion, TextRegion.id == OCRResult.region_id)
        .where(TextRegion.page_id == page_id)
        .order_by(TextRegion.reading_order.nulls_last(), TextRegion.created_at)
    )
    return list((await session.execute(stmt)).scalars())


@router.post(
    "/pages/{page_id}/retry-ocr",
    response_model=PageAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["pages"],
)
async def retry_ocr(
    page_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> PageAccepted:
    """Xếp lại việc OCR cho 1 page. Chỉ enqueue — không chạy OCR trong request."""
    page = await _get_page_or_404(session, page_id, nguoi)
    region_count = await session.scalar(
        select(func.count(TextRegion.id)).where(TextRegion.page_id == page_id)
    )
    # E43 — chốt chặn thứ NĂM, và là chốt duy nhất nằm ở tầng API.
    #
    # Trang TRANH THUẦN (`detected` + 0 vùng) phải chạy lại OCR được: từ E43, lượt OCR đó không
    # đọc gì cả mà chỉ đẩy trang đi tiếp cho tới `typeset_done`. Đây chính là đường CỨU những
    # trang đã kẹt từ trước bản vá — chặn nó là khoá luôn lối thoát.
    #
    # Đo thật trên production 24-09: 5 trang kẹt, cả 5 lượt `retry-ocr` trả 409 kèm thông điệp
    # "chạy detect trước" — trong khi detect ĐÃ chạy xong. Thông điệp sai sự thật đẩy người vận
    # hành đi chạy lại detect, việc vô ích vì detect sẽ lại cho ra đúng 0 vùng.
    #
    # Trang CHƯA detect xong thì vẫn phải chặn — đó mới đúng là "chạy detect trước".
    if not region_count and page.status is not PageStatus.detected:
        raise HTTPException(
            status_code=409,
            detail="Page chưa có vùng chữ nào — chạy detect trước (POST /pages/{id}/retry-detect)",
        )

    await _giu_suat_chay_lai_trang(session, page.id, JobType.ocr, settings)

    job = Job(type=JobType.ocr, page_id=page.id, status=JobStatus.queued)
    session.add(job)
    await session.commit()
    await session.refresh(job)

    sent, reason = dispatch_ocr_job(job.id)
    if not sent:
        job.error_log = reason
        await session.commit()

    return PageAccepted(page_id=page.id, status=page.status, job_id=job.id)



# ============================ phục vụ hiện vật (P3c) ============================
#
# Trước P3c, ba endpoint dưới đây trả thẳng một `FileResponse` dựng từ đường dẫn tuyệt đối của
# kho — tức là yêu cầu kho lưu trữ PHẢI là một hệ tệp cục bộ. Nay chúng đọc qua luồng
# `open_read()`, nên kho có thể là Postgres hay S3 mà route không đổi một dòng nào.
#
# Đổi sang `StreamingResponse` thì mất ETag/Content-Length/Range mà Starlette tự sinh, nên phải
# tự dựng lại cả ba:
#
#  - ETag/304 — ảnh xem thử đặt `no-cache, must-revalidate`, tức trình duyệt hỏi lại server MỖI
#    lượt xem. Không có ETag thì mỗi lượt hỏi lại là tải nguyên ~3MB thay vì một cái 304 rỗng.
#  - Range/206 — đứt mạng giữa chừng khi tải gói CBZ thì tải tiếp được, không phải tải lại từ
#    đầu. P3d đã nhận mất tính năng này; P3g trả lại.
#
# Cả hai đều chỉ cần `stat()` + `read_range()`, tức kho nào cũng cấp được — không lôi lại giả
# định "kho phải là hệ tệp".


def _the_phien_ban(st: ObjectStat) -> str:
    """ETag từ (kích thước, mtime) — đúng cặp số mà `stat()` của mọi backend đều cấp được."""
    return f'"{st.size:x}-{st.mtime:x}"'


def _doc_theo_khoi(fh, kich_thuoc: int = 64 * 1024):
    """Đọc luồng theo khối. Duyệt thẳng file object sẽ cắt theo dấu xuống dòng — sai với nhị phân.

    Đây là generator ĐỒNG BỘ. Starlette tự chạy generator đồng bộ trong threadpool, nên các lượt
    đi CSDL bên trong (kho `postgres` đọc lười) không chặn event loop.
    """
    try:
        while khoi := fh.read(kich_thuoc):
            yield khoi
    finally:
        fh.close()


#: Range hợp lệ về cú pháp nhưng không thoả mãn được ⇒ 416.
_RANGE_KHONG_THOA = object()


def _pha_range(header: str | None, tong: int):
    """Đọc header `Range`. Trả `None` = phục vụ nguyên tệp · `(dau, cuoi)` bao gồm cả hai đầu ·
    `_RANGE_KHONG_THOA` = 416.

    Cú pháp hỏng thì **bỏ qua header và trả nguyên tệp** — RFC 9110 cho phép, và đó là hành vi an
    toàn hơn so với ném lỗi vào mặt người dùng vì một header họ không tự gõ.
    """
    if not header:
        return None
    header = header.strip()
    if not header.startswith("bytes="):
        return None
    spec = header[len("bytes=") :].strip()
    if "," in spec:
        # Đa đoạn là hợp lệ nhưng cần multipart/byteranges. Chưa ai cần ⇒ trả nguyên tệp,
        # vẫn đúng chuẩn.
        return None
    dau_s, co_gach, cuoi_s = spec.partition("-")
    if not co_gach:
        return None
    try:
        if dau_s == "":
            if cuoi_s == "":
                return None
            n_cuoi = int(cuoi_s)
            if n_cuoi <= 0:
                return _RANGE_KHONG_THOA
            dau = max(0, tong - n_cuoi)
            cuoi = tong - 1
        else:
            dau = int(dau_s)
            cuoi = int(cuoi_s) if cuoi_s else tong - 1
    except ValueError:
        return None
    if tong == 0 or dau >= tong or dau > cuoi or dau < 0:
        return _RANGE_KHONG_THOA
    return dau, min(cuoi, tong - 1)


def _doc_mot_doan(storage: IObjectStorage, rel: str, dau: int, cuoi: int, kich_thuoc: int = 64 * 1024):
    """Phát một đoạn theo khối — đoạn dài cũng không nằm trọn trong RAM."""
    vi_tri = dau
    while vi_tri <= cuoi:
        khoi = storage.read_range(rel, vi_tri, min(kich_thuoc, cuoi - vi_tri + 1))
        if not khoi:
            break
        yield khoi
        vi_tri += len(khoi)


async def _phuc_vu_hien_vat(
    storage: IObjectStorage,
    rel: str,
    media_type: str,
    request: Request,
    *,
    filename: str | None = None,
    cache_control: str | None = None,
) -> Response:
    # P3e: kho có thể là CSDL, tức mỗi lời gọi dưới đây là một lượt đi CSDL đồng bộ. Gọi thẳng
    # trong hàm async sẽ CHẶN event loop — mọi request khác đứng chờ theo. `run_in_threadpool`
    # đẩy chúng sang luồng phụ. Với backend `local` thì đây chỉ là vài syscall, không đáng kể.
    st = await run_in_threadpool(storage.stat, rel)
    if st is None:
        # Chỉ xảy ra khi hiện vật biến mất giữa lúc kiểm và lúc phục vụ.
        raise HTTPException(status_code=404, detail="Hiện vật không còn trên kho lưu trữ")
    etag = _the_phien_ban(st)
    headers: dict[str, str] = {"ETag": etag, "Accept-Ranges": "bytes"}
    if cache_control:
        headers["Cache-Control"] = cache_control
    if filename:
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)

    # `If-Range` không khớp nghĩa là hiện vật đã đổi kể từ lúc client tải dở ⇒ phải trả NGUYÊN
    # tệp. Nối tiếp một đoạn của bản cũ vào phần đã tải sẽ tạo ra một tệp lai không của ai cả.
    if_range = request.headers.get("if-range")
    doan = None if (if_range is not None and if_range != etag) else _pha_range(
        request.headers.get("range"), st.size
    )

    if doan is _RANGE_KHONG_THOA:
        return Response(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            headers={**headers, "Content-Range": f"bytes */{st.size}"},
        )

    if doan is not None:
        dau, cuoi = doan
        headers["Content-Range"] = f"bytes {dau}-{cuoi}/{st.size}"
        headers["Content-Length"] = str(cuoi - dau + 1)
        return StreamingResponse(
            _doc_mot_doan(storage, rel, dau, cuoi),
            status_code=status.HTTP_206_PARTIAL_CONTENT,
            media_type=media_type,
            headers=headers,
        )

    headers["Content-Length"] = str(st.size)
    luong = await run_in_threadpool(storage.open_read, rel)
    return StreamingResponse(
        _doc_theo_khoi(luong), media_type=media_type, headers=headers
    )


@router.get(
    "/pages/{page_id}/clean-image",
    tags=["pages"],
    responses={200: {"content": {"image/png": {}}}, 404: {"description": "Chưa có ảnh clean"}},
)
async def get_clean_image(
    page_id: uuid.UUID, request: Request, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> Response:
    """Ảnh đã xoá chữ gốc (M4). Ảnh GỐC không bao giờ bị thay — đây là file riêng."""
    page = await _get_page_or_404(session, page_id, nguoi)
    if not page.clean_image_path:
        raise HTTPException(
            status_code=404,
            detail="Page chưa có ảnh clean — bước xoá chữ (inpaint) chưa chạy xong",
        )
    storage = get_storage()
    if not await run_in_threadpool(storage.exists, page.clean_image_path):
        raise HTTPException(
            status_code=404,
            detail=f"Đường dẫn ảnh clean có trong DB nhưng file không còn: {page.clean_image_path}",
        )
    return await _phuc_vu_hien_vat(storage, page.clean_image_path, "image/png", request)


@router.get(
    "/pages/{page_id}/original-image",
    tags=["pages"],
    responses={200: {"content": {"image/*": {}}}, 404: {"description": "Không còn file"}},
)
async def get_original_image(
    page_id: uuid.UUID, request: Request, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> Response:
    """Ảnh GỐC lúc upload — CHƯA xoá chữ, CHƯA chèn gì (E21).

    `typeset-preview`/`clean-image` đều đã xoá chữ gốc (M4) nên không dùng đối chiếu OCR được.
    Màn rà soát (M7) cần ảnh này để phóng to một vùng, so trực tiếp với `raw_text` khi người dùng
    quyết định có cần gõ đè hay không (xem `PATCH /regions/{id}` §`raw_text`, E21).
    """
    page = await _get_page_or_404(session, page_id, nguoi)
    storage = get_storage()
    if not await run_in_threadpool(storage.exists, page.image_path):
        raise HTTPException(
            status_code=404,
            detail="Không còn tệp ảnh gốc trên máy chủ lưu trữ.",
        )
    mime, _ = mimetypes.guess_type(page.image_path)
    return await _phuc_vu_hien_vat(storage, page.image_path, mime or "application/octet-stream", request)


@router.post(
    "/pages/{page_id}/retry-inpaint",
    response_model=PageAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["pages"],
)
async def retry_inpaint(
    page_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> PageAccepted:
    """Xếp lại việc xoá chữ cho 1 page. Chỉ enqueue — không chạy inpaint trong request."""
    page = await _get_page_or_404(session, page_id, nguoi)
    if page.status not in (
        PageStatus.ocr_done,
        PageStatus.inpainted,
        PageStatus.inpaint_needs_review,
    ):
        raise HTTPException(
            status_code=409,
            detail=f"Page đang ở '{page.status.value}' — cần OCR xong trước khi xoá chữ",
        )

    await _giu_suat_chay_lai_trang(session, page.id, JobType.inpaint, settings)

    job = Job(type=JobType.inpaint, page_id=page.id, status=JobStatus.queued)
    session.add(job)
    await session.commit()
    await session.refresh(job)

    sent, reason = dispatch_inpaint_job(job.id)
    if not sent:
        job.error_log = reason
        await session.commit()

    return PageAccepted(page_id=page.id, status=page.status, job_id=job.id)


def _doc_mat_na(im):
    """Điểm XOÁ = điểm SÁNG (trắng) và ĐỤC. Nhận được cả hai kiểu mặt nạ hay gặp:

    - trắng/đen đục toàn bộ (màn canvas xuất kiểu này),
    - trong suốt ở chỗ không tô.

    Bản đầu lấy "không trong suốt" làm điểm xoá khi ảnh có kênh alpha ⇒ mặt nạ trắng/đen đục của
    màn canvas thành "tô 100% trang" ⇒ 422. Test hai phía đều xanh vì mỗi phía tự kiểm theo cách hiểu
    của mình; chỉ lộ ra khi bấm thật trên hệ thống chạy thật (15-10-2026).
    """
    import numpy as np

    sang = np.asarray(im.convert("L")) > 127
    if im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info:
        sang &= np.asarray(im.convert("RGBA").getchannel("A")) > 127
    return sang


#: E76 — trần cỡ tệp mặt nạ. PNG một kênh của trang 4000×6000 nén còn vài trăm KB; 20MB là dư.
_TRAN_MAT_NA_BYTE = 20 * 1024 * 1024
#: Tô quá nửa trang thì đó không còn là "xoá vết chữ sót" — gần như chắc là bấm nhầm công cụ.
_TRAN_TI_LE_TO = 0.5


@router.post(
    "/pages/{page_id}/xoa-vung-to",
    response_model=PageAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["pages"],
)
async def xoa_vung_to(
    page_id: uuid.UUID,
    file: UploadFile = File(..., description="Mặt nạ PNG cùng cỡ ẢNH GỐC: điểm trắng/không trong suốt = xoá"),
    session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> PageAccepted:
    """E76 — cọ xoá chữ trên màn canvas: xoá chữ trong vùng người dùng tô, chạy nền.

    Làm trên ẢNH SẠCH hiện tại (chưa có thì trên ảnh gốc); ảnh gốc không bao giờ bị ghi đè. Kiểm
    mặt nạ NGAY tại đây (đúng cỡ, không rỗng, không trùm quá nửa trang) để lỗi hiện ra liền cho
    người tô, thay vì thành một việc nền hỏng mà họ phải đi tìm.
    """
    import io

    import numpy as np
    from PIL import Image as _Image

    page = await _get_page_or_404(session, page_id, nguoi)
    if page.status in (PageStatus.queued, PageStatus.detecting):
        raise HTTPException(status_code=409, detail="Trang còn đang xử lý — đợi xong rồi hãy tô")
    tho = await file.read(_TRAN_MAT_NA_BYTE + 1)
    if len(tho) > _TRAN_MAT_NA_BYTE:
        raise HTTPException(status_code=413, detail="Tệp mặt nạ quá lớn")
    storage = get_storage()
    try:
        with _Image.open(io.BytesIO(tho)) as im:
            co_mn = im.size
            mn = _doc_mat_na(im)
        with storage.open_read(page.image_path) as f, _Image.open(f) as goc:
            co_goc = goc.size
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Không đọc được mặt nạ: {exc}") from exc
    if co_mn != co_goc:
        raise HTTPException(
            status_code=422,
            detail=f"Mặt nạ {co_mn[0]}x{co_mn[1]} khác cỡ trang {co_goc[0]}x{co_goc[1]}",
        )
    ti_le = float(mn.mean())
    if ti_le == 0:
        raise HTTPException(status_code=422, detail="Chưa tô vùng nào")
    if ti_le > _TRAN_TI_LE_TO:
        raise HTTPException(
            status_code=422,
            detail=f"Vùng tô chiếm {ti_le:.0%} trang — quá rộng để là vết chữ sót",
        )

    from pathlib import PurePosixPath

    mat_na_rel = str(PurePosixPath(page.image_path).parent / f"{page.id}_mat_na_{uuid.uuid4().hex}.png")
    buf = io.BytesIO()
    _Image.fromarray(mn.astype(np.uint8) * 255).save(buf, format="PNG")
    await run_in_threadpool(storage.save, mat_na_rel, buf.getvalue())

    job = Job(type=JobType.inpaint, page_id=page.id, status=JobStatus.queued)
    session.add(job)
    await session.commit()
    await session.refresh(job)
    sent, reason = dispatch_xoa_vung_to_job(job.id, mat_na_rel)
    if not sent:
        job.error_log = reason
        await session.commit()
    return PageAccepted(page_id=page.id, status=page.status, job_id=job.id)


@router.get(
    "/pages/{page_id}/translation", response_model=list[TranslationResultRead], tags=["pages"]
)
async def list_page_translation(
    page_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> list[TranslationResult]:
    """Bản dịch theo từng vùng chữ, sắp theo ĐÚNG thứ tự đọc (M5).

    Trả `[]` khi chưa dịch — không bịa bản dịch. `status`: `ok` · `fallback_used`
    (LLM lỗi nên đã lùi về Google) · `pending` (model không trả dòng này, cần xem lại).
    """
    await _get_page_or_404(session, page_id, nguoi)
    stmt = (
        select(TranslationResult)
        .join(TextRegion, TextRegion.id == TranslationResult.region_id)
        .where(TextRegion.page_id == page_id)
        .order_by(TextRegion.reading_order.nulls_last(), TextRegion.created_at)
    )
    return list((await session.execute(stmt)).scalars())


@router.post(
    "/pages/{page_id}/retry-translate",
    response_model=PageAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["pages"],
)
async def retry_translate(
    page_id: uuid.UUID,
    engine: TranslationEngine | None = None,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> PageAccepted:
    """Xếp lại việc dịch. `engine` (tuỳ chọn): `google_fast` (miễn phí) hoặc `llm_context` (tốn token).

    Không truyền `engine` thì dùng mặc định trong cấu hình. Chỉ enqueue, không dịch trong request.
    """
    _kiem_engine(engine, settings)
    page = await _get_page_or_404(session, page_id, nguoi)
    # `typeset_done` PHẢI nằm trong danh sách: từ M6 pipeline tự nối chuỗi nên mọi trang đều kết
    # thúc ở trạng thái này — thiếu nó thì không trang nào dịch lại được nữa (lỗi thật, M8 phát hiện).
    if page.status not in (
        PageStatus.inpainted,
        PageStatus.inpaint_needs_review,
        PageStatus.translated,
        PageStatus.typeset_done,
    ):
        raise HTTPException(
            status_code=409,
            detail=f"Page đang ở '{page.status.value}' — cần xoá chữ xong trước khi dịch",
        )

    await _giu_suat_chay_lai_trang(session, page.id, JobType.translate, settings)

    job = Job(type=JobType.translate, page_id=page.id, status=JobStatus.queued)
    session.add(job)
    await session.commit()
    await session.refresh(job)

    sent, reason = dispatch_translate_job(job.id, engine.value if engine else None)
    if not sent:
        job.error_log = reason
        await session.commit()

    return PageAccepted(page_id=page.id, status=page.status, job_id=job.id)


@router.get("/pages/{page_id}/typeset", response_model=list[TypesetResultRead], tags=["pages"])
async def list_page_typeset(
    page_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> list[TypesetResult]:
    """Kết quả canh chữ theo từng vùng, sắp theo ĐÚNG thứ tự đọc (M6).

    Trả `[]` khi chưa canh. `fit_status`: `fit_ok` · `overflow_warning` (không vừa dù đã xuống
    cỡ nhỏ nhất — M7 sẽ sửa tay) · `pending` (vùng chưa có bản dịch nên chưa có gì để canh).
    Cảnh báo tràn khung PHẢI đọc được ở đây, không bị ảnh preview đẹp che mất.
    """
    await _get_page_or_404(session, page_id, nguoi)
    stmt = (
        select(TypesetResult)
        .join(TextRegion, TextRegion.id == TypesetResult.region_id)
        .where(TextRegion.page_id == page_id)
        .order_by(TextRegion.reading_order.nulls_last(), TextRegion.created_at)
    )
    return list((await session.execute(stmt)).scalars())


@router.get(
    "/pages/{page_id}/typeset-preview",
    tags=["pages"],
    responses={200: {"content": {"image/png": {}}}, 404: {"description": "Chưa render preview"}},
)
async def get_typeset_preview(
    page_id: uuid.UUID, request: Request, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> Response:
    """Ảnh xem thử: ảnh clean của M4 + chữ dịch đã canh (M6).

    CHỈ phục vụ file đã render sẵn — endpoint này không bao giờ tự render (việc nặng thuộc
    worker). Ảnh gốc và ảnh clean không hề bị đụng tới; đây là file thứ ba.
    """
    await _get_page_or_404(session, page_id, nguoi)
    storage = get_storage()
    rel = preview_relative_path(page_id)
    if not await run_in_threadpool(storage.exists, rel):
        raise HTTPException(
            status_code=404,
            detail="Page chưa có ảnh preview — bước canh chữ (typeset) chưa chạy xong",
        )
    # `no-cache` = trình duyệt PHẢI hỏi lại server trước khi dùng bản đã lưu. Đường dẫn preview
    # cố định theo page nên thiếu header này thì sau khi sửa tay (M7) người dùng vẫn thấy ảnh cũ.
    return await _phuc_vu_hien_vat(
        storage, rel, "image/png", request, cache_control="no-cache, must-revalidate"
    )


#: Cạnh dài tối đa của ảnh thu nhỏ (px). Thẻ chapter trên giao diện rộng ~220–300px CSS, nhân 2
#: cho màn hình mật độ cao vẫn dưới mức này.
CANH_ANH_THU_NHO = 480


def _tao_anh_thu_nho(storage: IObjectStorage, nguon: str, dich: str, thu_muc: str) -> None:
    """Đọc ảnh nguồn, thu nhỏ JPEG, ghi vào kho. Xoá bản thu nhỏ CŨ của cùng trang trước khi ghi —
    khoá theo phiên bản nguồn nên mỗi lần ảnh đổi là một tệp mới, không xoá thì kho phình mãi."""
    import io

    from PIL import Image

    with storage.open_read(nguon) as f, Image.open(f) as im:
        im.thumbnail((CANH_ANH_THU_NHO, CANH_ANH_THU_NHO))
        ra = io.BytesIO()
        im.convert("RGB").save(ra, "JPEG", quality=80, optimize=True)
    storage.delete_prefix(thu_muc)
    storage.save(dich, ra.getvalue())


@router.get(
    "/pages/{page_id}/thumbnail",
    tags=["pages"],
    responses={200: {"content": {"image/jpeg": {}}}, 404: {"description": "Không còn ảnh nào"}},
)
async def get_page_thumbnail(
    page_id: uuid.UUID, request: Request, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> Response:
    """Ảnh thu nhỏ của trang (JPEG, cạnh dài ≤ 480px) — làm ảnh bìa thẻ chapter và lưới trang.

    Nguồn: ảnh ĐÃ DỊCH nếu có, chưa có thì ảnh GỐC. Tạo một lần rồi giữ trong kho, khoá theo phiên
    bản ảnh nguồn (kích thước + mtime) ⇒ trang dịch lại thì tự có ảnh thu nhỏ mới. Tải cả ảnh gốc
    1–3MB chỉ để vẽ một thẻ 220px là lãng phí băng thông của chính người dùng.
    """
    page = await _get_page_or_404(session, page_id, nguoi)
    storage = get_storage()
    nguon = preview_relative_path(page_id)
    st = await run_in_threadpool(storage.stat, nguon)
    if st is None:
        nguon = page.image_path
        st = await run_in_threadpool(storage.stat, nguon)
    if st is None:
        raise HTTPException(status_code=404, detail="Trang không còn ảnh nào để thu nhỏ")
    thu_muc = f"projects/{page.project_id}/thumbs/{page_id}/"
    dich = f"{thu_muc}{st.size:x}-{st.mtime:x}.jpg"
    if not await run_in_threadpool(storage.exists, dich):
        try:
            await run_in_threadpool(_tao_anh_thu_nho, storage, nguon, dich, thu_muc)
        except Exception as exc:  # noqa: BLE001 — ảnh hỏng/không đọc được ⇒ 404 rõ, không 500
            logger.warning("Không tạo được ảnh thu nhỏ trang %s: %s", page_id, exc)
            raise HTTPException(status_code=404, detail="Không đọc được ảnh trang để thu nhỏ")
    return await _phuc_vu_hien_vat(
        storage, dich, "image/jpeg", request, cache_control="no-cache, must-revalidate"
    )


@router.post(
    "/pages/{page_id}/retry-typeset",
    response_model=PageAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["pages"],
)
async def retry_typeset(
    page_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> PageAccepted:
    """Xếp lại việc canh chữ. Chỉ enqueue, không render trong request."""
    page = await _get_page_or_404(session, page_id, nguoi)
    if page.status not in (PageStatus.translated, PageStatus.typeset_done):
        raise HTTPException(
            status_code=409,
            detail=f"Page đang ở '{page.status.value}' — cần dịch xong trước khi canh chữ",
        )

    job = Job(type=JobType.typeset, page_id=page.id, status=JobStatus.queued)
    session.add(job)
    await session.commit()
    await session.refresh(job)

    sent, reason = dispatch_typeset_job(job.id)
    if not sent:
        job.error_log = reason
        await session.commit()

    return PageAccepted(page_id=page.id, status=page.status, job_id=job.id)


# ============================ M7: sửa tay từng vùng ============================


async def _get_region_or_404(
    session: AsyncSession, region_id: uuid.UUID, nguoi: NguoiDung
) -> TextRegion:
    """Lấy vùng chữ, ném 404 nếu không có hoặc chapter chứa nó không phải của `nguoi`."""
    region = await session.get(TextRegion, region_id)
    if region is None:
        # Bỏ `{region_id}` khỏi thông báo: lặp lại id người ta gửi lên không thêm thông tin gì
        # cho chủ sở hữu, mà lại giúp người dò phân biệt các nhánh lỗi.
        raise HTTPException(status_code=404, detail=LOI_KHONG_THAY)
    await bao_dam_quyen(session, nguoi, region)
    return region


@router.get("/pages/{page_id}/detail", response_model=PageDetail, tags=["pages"])
async def get_page_detail(
    page_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> PageDetail:
    """Gom TẤT CẢ dữ liệu của 1 trang cho màn sửa tay (M7) — 1 lần gọi thay vì 5 lần.

    Mọi cảnh báo đều lộ ra ở đây và **không bị ẩn**: `status` của vùng (`low_confidence`),
    `ocr_status` (`needs_manual`), `fit_status` (`overflow_warning`), cùng cờ `edited_by_user`
    của cả bản dịch lẫn kết quả canh chữ để biết chỗ nào người sửa, chỗ nào máy làm.
    """
    page = await _get_page_or_404(session, page_id, nguoi)

    stmt = (
        select(TextRegion, OCRResult, TranslationResult, TypesetResult)
        .outerjoin(OCRResult, OCRResult.region_id == TextRegion.id)
        .outerjoin(TranslationResult, TranslationResult.region_id == TextRegion.id)
        .outerjoin(TypesetResult, TypesetResult.region_id == TextRegion.id)
        .where(TextRegion.page_id == page_id)
        .order_by(TextRegion.reading_order.nulls_last(), TextRegion.created_at)
    )
    rows = (await session.execute(stmt)).all()

    regions = [
        RegionDetail(
            id=region.id,
            bbox=BBoxOut(x=region.bbox_x, y=region.bbox_y, w=region.bbox_w, h=region.bbox_h),
            confidence=region.confidence,
            overlap_suspect=region.overlap_suspect,
            reading_order=region.reading_order,
            status=region.status,
            raw_text=ocr.raw_text if ocr else None,
            ocr_confidence=ocr.confidence if ocr else None,
            ocr_status=ocr.status if ocr else None,
            ocr_edited_by_user=bool(ocr.edited_by_user) if ocr else False,
            translated_text=tr.translated_text if tr else None,
            translation_status=tr.status if tr else None,
            translation_edited_by_user=bool(tr.edited_by_user) if tr else False,
            # P1 — `TranslationResult` đã nằm sẵn trong lượt join ở trên, nên thêm trường này
            # KHÔNG tốn thêm truy vấn nào. Đọc thẳng cột đã ghi, không tính lại.
            token_cost=tr.token_cost if tr else None,
            font_family=ts.font_family if ts else None,
            font_size=ts.font_size if ts else None,
            wrapped_text=ts.wrapped_text if ts else None,
            fit_status=ts.fit_status if ts else None,
            typeset_edited_by_user=bool(ts.edited_by_user) if ts else False,
            text_color=ts.text_color if ts else None,
            stroke_color=ts.stroke_color if ts else None,
            stroke_width=ts.stroke_width if ts else None,
            xep_theo_hinh=bool(ts and ts.dong_json),
        )
        for region, ocr, tr, ts in rows
    ]

    storage = get_storage()
    preview_rel = preview_relative_path(page_id)
    return PageDetail(
        page=page,
        # Chỉ trả URL khi file CÓ THẬT — không đưa link chết cho UI.
        preview_url=(
            f"/api/v1/pages/{page_id}/typeset-preview"
            if await run_in_threadpool(storage.exists, preview_rel)
            else None
        ),
        font_families=sorted(FONT_REGISTRY),
        min_font_size=settings.typeset_min_font_size,
        max_font_size=settings.typeset_max_font_size,
        regions=regions,
    )


@router.patch(
    "/regions/{region_id}",
    response_model=RegionPatchAccepted,
    status_code=status.HTTP_200_OK,
    tags=["regions"],
)
async def patch_region(
    region_id: uuid.UUID,
    patch: RegionPatch,
    session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> RegionPatchAccepted:
    """Sửa tay 1 vùng: chữ gốc / bản dịch / khung chữ / font / cỡ chữ, rồi **canh lại đúng vùng đó**.

    Ghi thẳng phần sửa vào DB, đánh dấu `edited_by_user=true` (riêng cho `OCRResult` và
    `TranslationResult` — hai cờ độc lập), rồi xếp việc canh chữ chạy nền (không canh trong
    request). Vì bản canh cũ đã không còn đúng với nội dung mới, `fit_status` trả về là
    **`pending`** — không trả trạng thái cũ để khỏi báo nhầm là "vẫn vừa khung".

    **E21b — chỉ canh lại khi cần:** lượt sửa chỉ đụng `raw_text` KHÔNG xếp việc canh chữ nào
    (`refit_job_id=null`) và giữ nguyên `fit_status` thật. Chữ được vẽ vào bong bóng là
    `translated_text`; sửa chữ gốc OCR không đổi bản vẽ, nên canh lại chỉ tổ chiếm suất của
    worker `--pool=solo` và hạ nhầm `fit_ok` xuống `pending`.

    `font_size` = **ghim cỡ chữ**: canh lại sẽ dùng đúng cỡ đó. Bỏ trống = tự dò cỡ như M6.

    `raw_text` (E21): gõ đè chữ OCR đọc SAI — đo được ở `REPORT_E20a`/`REPORT_E20b`, chữ mảnh
    trên nền tranh phức tạp không path OCR tự động nào (kể cả Tesseract, kể cả 4 kiểu tiền xử lý
    ảnh) tự sửa được. Sửa `raw_text` **KHÔNG tự dịch lại** — bản dịch cũ (dựa trên chữ gốc sai)
    vẫn còn nguyên tới khi bấm "Dịch lại" (`POST /regions/{id}/re-translate`), để không âm thầm
    tốn token dịch lại khi người dùng chỉ đang sửa từng chữ một.
    """
    if not patch.co_thay_doi():
        raise HTTPException(status_code=422, detail="Không có trường nào để sửa")

    region = await _get_region_or_404(session, region_id, nguoi)
    da_sua: list[str] = []

    if patch.bbox is not None:
        region.bbox_x, region.bbox_y = patch.bbox.x, patch.bbox.y
        region.bbox_w, region.bbox_h = patch.bbox.w, patch.bbox.h
        da_sua.append("bbox")
        # E76 — khung đổi ⇒ vùng an toàn E14 cũ (lòng bong bóng quanh khung CŨ) hết đúng. Không xoá
        # thì bộ vẽ vẫn đặt chữ vào bong bóng cũ: kéo khung trên màn canvas mà chữ đứng yên (thấy khi
        # bấm thật 15-10-2026). Bước căn lại sẽ tự tính vùng an toàn quanh khung MỚI.
        await session.execute(delete(RegionSafeArea).where(RegionSafeArea.region_id == region.id))

    if patch.translated_text is not None:
        row = (
            await session.execute(
                select(TranslationResult).where(TranslationResult.region_id == region_id)
            )
        ).scalars().first()
        if row is None:
            raise HTTPException(
                status_code=409,
                detail="Vùng này chưa có bản dịch để sửa — chạy bước dịch (M5) trước",
            )
        row.translated_text = patch.translated_text or None
        row.edited_by_user = True
        da_sua.append("translated_text")

    if patch.raw_text is not None:
        ocr_row = (
            await session.execute(select(OCRResult).where(OCRResult.region_id == region_id))
        ).scalars().first()
        if ocr_row is None:
            raise HTTPException(
                status_code=409,
                detail="Vùng này chưa đọc chữ (OCR) — chạy bước đọc chữ (M3) trước",
            )
        ocr_row.raw_text = patch.raw_text or None
        ocr_row.edited_by_user = True
        da_sua.append("raw_text")

    typeset = (
        await session.execute(select(TypesetResult).where(TypesetResult.region_id == region_id))
    ).scalars().first()

    if patch.font_family is not None:
        if patch.font_family not in FONT_REGISTRY:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"font_not_found: '{patch.font_family}' không nằm trong whitelist "
                    f"({', '.join(sorted(FONT_REGISTRY))})"
                ),
            )
        if typeset is None:
            raise HTTPException(
                status_code=409,
                detail="Vùng này chưa canh chữ lần nào — chạy bước canh chữ (M6) trước",
            )
        typeset.font_family = patch.font_family
        da_sua.append("font_family")

    if patch.font_size is not None:
        da_sua.append("font_size")

    # E21b — chỉ canh lại khi có thứ THẬT SỰ đổi bản vẽ.
    #
    # `raw_text` là chữ GỐC OCR đọc được; chữ được VẼ vào bong bóng là `translated_text`. Sửa chữ
    # gốc không làm bản vẽ khác đi một pixel nào, nên canh lại là việc thừa — và không hề rẻ:
    # worker chạy `--pool=solo`, mỗi lúc đúng một việc (`REPORT_E22`), nên mỗi lượt canh thừa
    # chiếm mất suất của việc thật đang xếp hàng. Nó còn hạ `fit_status` đang `fit_ok` xuống
    # `pending` và gắn `edited_by_user` lên tầng typeset dù người dùng không đụng tầng đó.
    #
    # E21 thêm `raw_text` vào endpoint này nhưng không sửa phần đuôi, nên tác dụng phụ đó lọt
    # qua: test E21 chỉ khoá "không tự DỊCH lại", chưa bao giờ soi job typeset.
    CAN_CANH_LAI = {"bbox", "translated_text", "font_family", "font_size"}
    can_canh_lai = bool(set(da_sua) & CAN_CANH_LAI)

    if typeset is not None and can_canh_lai:
        # Bản canh cũ không còn đúng với nội dung mới -> nói thật là "chưa canh", không giữ fit_ok.
        typeset.fit_status = FitStatus.pending
        typeset.edited_by_user = True

    if not can_canh_lai:
        # Vẫn phải commit: phần sửa (raw_text) nằm trong session này, trước đây được commit ké
        # theo job bên dưới.
        await session.commit()
        return RegionPatchAccepted(
            region_id=region_id,
            page_id=region.page_id,
            # Trả trạng thái canh chữ THẬT đang có, không hạ xuống `pending` — không có gì để canh
            # lại thì bản canh cũ vẫn còn đúng nguyên.
            fit_status=typeset.fit_status if typeset is not None else FitStatus.pending,
            refit_job_id=None,
            edited_fields=da_sua,
            edited_by_user=True,
        )

    job = Job(type=JobType.typeset, page_id=region.page_id, status=JobStatus.queued)
    session.add(job)
    await session.commit()
    await session.refresh(job)

    sent, reason = dispatch_refit_job(job.id, region_id, patch.font_size)
    if not sent:
        job.error_log = reason
        await session.commit()

    return RegionPatchAccepted(
        region_id=region_id,
        page_id=region.page_id,
        fit_status=FitStatus.pending,
        refit_job_id=job.id,
        edited_fields=da_sua,
        edited_by_user=True,
    )


@router.post(
    "/regions/{region_id}/re-fit",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["regions"],
)
async def refit_region(
    region_id: uuid.UUID,
    font_size: float | None = None,
    session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> JobAccepted:
    """Canh lại chữ cho 1 vùng mà KHÔNG sửa gì (dùng khi đổi cấu hình font/padding)."""
    region = await _get_region_or_404(session, region_id, nguoi)
    job = Job(type=JobType.typeset, page_id=region.page_id, status=JobStatus.queued)
    session.add(job)
    await session.commit()
    await session.refresh(job)

    sent, reason = dispatch_refit_job(job.id, region_id, font_size)
    if not sent:
        job.error_log = reason
        await session.commit()
    return JobAccepted(job_id=job.id, page_id=region.page_id, status=job.status)


@router.post(
    "/regions/{region_id}/re-ocr",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["regions"],
)
async def reocr_region(
    region_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> JobAccepted:
    """Đọc lại chữ gốc của 1 vùng từ **ảnh gốc** (ảnh clean đã bị xoá chữ nên không dùng được).

    KHÔNG tự dịch lại và không tự canh lại — người dùng chủ động bấm tiếp, để không âm thầm
    ghi đè bản dịch mà họ có thể đã sửa tay.
    """
    region = await _get_region_or_404(session, region_id, nguoi)
    await _giu_suat_chay_lai_trang(session, region.page_id, JobType.ocr, settings)
    job = Job(type=JobType.ocr, page_id=region.page_id, status=JobStatus.queued)
    session.add(job)
    await session.commit()
    await session.refresh(job)

    sent, reason = dispatch_region_reocr_job(job.id, region_id)
    if not sent:
        job.error_log = reason
        await session.commit()
    return JobAccepted(job_id=job.id, page_id=region.page_id, status=job.status)


@router.post(
    "/regions/{region_id}/re-translate",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["regions"],
)
async def retranslate_region(
    region_id: uuid.UUID,
    engine: TranslationEngine | None = None,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> JobAccepted:
    """Dịch lại 1 vùng từ chữ gốc hiện tại. **Ghi đè bản dịch**, kể cả bản đã sửa tay.

    Lưu ý: dịch lại một dòng lẻ thì `llm_context` mất lợi thế ngữ cảnh cả trang.
    KHÔNG tự canh chữ lại — bấm "canh lại" hoặc sửa tiếp thì mới canh.
    """
    _kiem_engine(engine, settings)
    region = await _get_region_or_404(session, region_id, nguoi)
    await _giu_suat_chay_lai_trang(session, region.page_id, JobType.translate, settings)
    job = Job(type=JobType.translate, page_id=region.page_id, status=JobStatus.queued)
    session.add(job)
    await session.commit()
    await session.refresh(job)

    sent, reason = dispatch_region_retranslate_job(
        job.id, region_id, engine.value if engine else None
    )
    if not sent:
        job.error_log = reason
        await session.commit()
    return JobAccepted(job_id=job.id, page_id=region.page_id, status=job.status)


# ============================ M8: xuất chapter ============================




def _thong_ke_xuat_stmt(project_id: uuid.UUID):
    return select(Page).where(Page.project_id == project_id).order_by(Page.order)


@router.get(
    "/projects/{project_id}/export-preview", response_model=ExportPreview, tags=["export"]
)
async def export_preview(
    project_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> ExportPreview:
    """Xem trước TRƯỚC khi xuất: sẽ xuất mấy trang, bỏ qua mấy trang, còn mấy vùng tràn khung.

    Vùng tràn khung **không chặn** việc xuất — nhưng phải hiện rõ ở đây để người dùng chọn:
    xuất luôn, hay quay lại sửa tay (M7) trước.
    """
    await _get_project_or_404(session, project_id, nguoi)
    pages = list((await session.execute(_thong_ke_xuat_stmt(project_id))).scalars())
    # E43 — xem-trước phải đếm GIỐNG file xuất thật.
    #
    # E38 dạy cổng xuất rằng trang `detected` + 0 vùng (tranh thuần) vẫn được xuất bằng ảnh gốc,
    # nhưng chỉ sửa trong `tasks.py` và **bỏ sót chỗ này**. Hậu quả đo được trên production
    # 24-09: xem-trước báo "19 trang, bỏ qua 5" trong khi file ZIP thật có ĐỦ 24 trang. Cảnh báo
    # sai làm người dùng mất tin vào mọi cảnh báo khác.
    #
    # Từ E43 trang tranh thuần đi hết chuỗi tới `typeset_done` nên phép so trạng thái tự đúng
    # với chapter MỚI. Dòng dưới lo nốt chapter CŨ đang kẹt ở `detected`.
    co_vung = set((await session.execute(
        select(TextRegion.page_id).where(TextRegion.page_id.in_([p.id for p in pages])).distinct()
    )).scalars()) if pages else set()
    xuat_duoc = [
        p for p in pages
        if p.status in (PageStatus.typeset_done, PageStatus.ready_for_export)
        or (p.status is PageStatus.detected and p.id not in co_vung)
    ]

    so_tran = so_thieu_glyph = 0
    if xuat_duoc:
        async def _dem(trang_thai: FitStatus) -> int:
            return (
                await session.execute(
                    select(func.count())
                    .select_from(TypesetResult)
                    .join(TextRegion, TextRegion.id == TypesetResult.region_id)
                    .where(
                        TextRegion.page_id.in_([p.id for p in xuat_duoc]),
                        TypesetResult.fit_status == trang_thai,
                    )
                )
            ).scalar() or 0

        so_tran = await _dem(FitStatus.overflow_warning)
        so_thieu_glyph = await _dem(FitStatus.font_missing_glyph)

    return ExportPreview(
        page_count=len(xuat_duoc),
        total_page_count=len(pages),
        skipped_page_count=len(pages) - len(xuat_duoc),
        overflow_warning_count=so_tran,
        font_missing_count=so_thieu_glyph,
    )


# E51 — MỞ CHO KHÁCH LẠ. Đây là đường duy nhất để lấy NHIỀU trang trong MỘT tệp, mà §3.3 đặc tả
# nói rõ: tải 24 tệp rời là 24 lần bị trình duyệt hỏi, gần như chắc chắn bị chặn.
#
# An toàn không dựa vào cổng đăng nhập mà dựa vào `bao_dam_quyen`, nay nhận cả `NguoiGoi`:
# `ExportJob` có mặt trong bảng `_CHA` của `core/quyen.py` nên nó lần được về chapter, và chapter
# của khách mang `chu_khach` riêng. Khách hỏi job của người khác ⇒ 404.
@router_khach.post(
    "/projects/{project_id}/export",
    response_model=ExportJobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["export"],
)
async def create_export(
    project_id: uuid.UUID,
    body: ExportRequest,
    session: AsyncSession = Depends(get_session),
    danh_tinh: DanhTinhHanMuc = Depends(danh_tinh_han_muc),
) -> ExportJobAccepted:
    """Xếp việc xuất chapter. Chỉ enqueue — render nhiều trang là việc của worker.

    Trang chưa canh chữ xong sẽ bị **bỏ qua** (không xuất ảnh chưa có chữ); số trang bỏ qua ghi
    vào `error_log` của job. Không trang nào xuất được ⇒ job `failed` với lý do rõ.
    """
    await _get_project_or_404(session, project_id, danh_tinh.nguoi_goi)

    # E33 — GỘP NHIỀU CHAPTER. Kiểm quyền TỪNG chapter, không có đường nào bỏ qua.
    #
    # Đây là chỗ dễ thành lỗ IDOR nhất của tính năng này: không kiểm thì ai cũng gộp được chapter
    # của người khác vào file của mình rồi tải về. `_get_project_or_404` trả 404 cho cả "không có"
    # lẫn "không phải của bạn" (xem `app/core/quyen.py`), nên vòng lặp này vừa kiểm quyền vừa kiểm
    # tồn tại — và một id lạ làm CẢ lượt xuất bị từ chối, chứ không lặng lẽ bỏ qua id đó.
    gop_ids = None
    if body.gop_project_ids:
        from app.services.export.gop_chapter import kiem_thu_tu

        gop_ids = kiem_thu_tu(body.gop_project_ids, project_id)
        for pid_khac in gop_ids:
            if pid_khac != project_id:
                await _get_project_or_404(session, pid_khac, danh_tinh.nguoi_goi)

    job = ExportJob(
        project_id=project_id, format=body.format, status=JobStatus.queued,
        gop_project_ids=[str(i) for i in gop_ids] if gop_ids else None,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    sent, reason = dispatch_export_job(job.id)
    if not sent:
        job.error_log = reason
        await session.commit()

    return ExportJobAccepted(job_id=job.id, project_id=project_id, status=job.status)


@router_khach.get("/export-jobs/{job_id}", response_model=ExportJobRead, tags=["export"])
async def get_export_job(
    job_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    danh_tinh: DanhTinhHanMuc = Depends(danh_tinh_han_muc),
) -> ExportJob:
    """Theo dõi tiến trình xuất. `status` đi `queued → running → done | failed`.

    `status=done` mà `error_log` khác NULL nghĩa là **xuất được nhưng có cảnh báo** —
    đọc kỹ trước khi giao file cho người khác.
    """
    job = await session.get(ExportJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Export job không tồn tại")
    await bao_dam_quyen(session, danh_tinh.nguoi_goi, job)
    return job


@router_khach.get(
    "/export-jobs/{job_id}/download",
    tags=["export"],
    responses={
        200: {"content": {"application/octet-stream": {}}},
        404: {"description": "Chưa xuất xong hoặc file không còn"},
    },
)
async def download_export(
    job_id: uuid.UUID, request: Request, session: AsyncSession = Depends(get_session),
    danh_tinh: DanhTinhHanMuc = Depends(danh_tinh_han_muc),
) -> Response:
    """Tải file đã xuất. **Chỉ phục vụ file có sẵn** — không bao giờ tự render ở đây.

    Với `png_single`, kết quả là một THƯ MỤC nhiều file nên không tải một lần được:
    trả `409` kèm hướng dẫn, thay vì trả file sai hoặc dựng ZIP ngầm.
    """
    job = await session.get(ExportJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Export job không tồn tại")
    await bao_dam_quyen(session, danh_tinh.nguoi_goi, job)
    if job.status is not JobStatus.done or not job.output_path:
        raise HTTPException(
            status_code=404,
            detail=f"Chưa có file để tải — job đang ở '{job.status.value}'",
        )
    if job.format is ExportFormat.png_single:
        raise HTTPException(
            status_code=409,
            detail=(
                "Định dạng png_single xuất ra nhiều file trong một thư mục nên không tải một lần "
                f"được. Thư mục: '{job.output_path}'. Muốn tải một file thì chọn format cbz hoặc zip."
            ),
        )

    storage = get_storage()
    if not await run_in_threadpool(storage.exists, job.output_path):
        raise HTTPException(
            status_code=404,
            detail=f"Đường dẫn có trong DB nhưng file không còn: {job.output_path}",
        )
    return await _phuc_vu_hien_vat(
        storage,
        job.output_path,
        "application/octet-stream",
        request,
        filename=job.output_path.rsplit("/", 1)[-1],
        cache_control="no-cache, must-revalidate",
    )


# ============================ M9: chạy cả mẻ ============================


def _dieu_phoi():
    """Dựng bộ điều phối theo cấu hình. Import trễ để API không kéo theo tầng worker.

    Dùng **chung một hàm dựng** với worker: dựng bằng tay ở hai nơi là cách mà cấu hình thử lại
    đã có lần chỉ có tác dụng ở một nửa hệ thống (xem `services/batch/factory.py`).
    """
    from app.services.batch.factory import tao_dieu_phoi

    return tao_dieu_phoi(get_settings())


@router.post(
    "/projects/{project_id}/batch-runs",
    response_model=BatchAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["batch"],
)
async def create_batch_run(
    project_id: uuid.UUID,
    body: BatchCreate,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> BatchAccepted:
    """Chạy cả project qua pipeline bằng MỘT mẻ theo dõi được.

    Danh sách trang được **chụp lại ngay lúc tạo** theo `Page.order` — trang tải lên sau đó
    không lẫn vào mẻ đang chạy, nên tổng số trang không nhảy lung tung giữa chừng.

    Mỗi trang tiếp tục **từ đúng bước nó đang đứng**, không chạy lại từ đầu: trang đã canh chữ
    xong được đánh `skipped` chứ không bị làm lại (làm lại là xoá mất kết quả đã có).
    """
    await _get_project_or_404(session, project_id, nguoi)

    engine = body.translation_engine
    # Báo NGAY chứ không xếp việc rồi mới hỏng ở trang thứ nhất.
    _kiem_engine(engine, settings)

    from app.services.batch.orchestrator import BatchInvalid

    try:
        me_id = _dieu_phoi().create_full_pipeline_run(
            project_id, engine.value if engine else None, body.requested_pipeline
        )
    except BatchInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    me = await session.get(BatchRun, me_id)
    await session.refresh(me)
    return BatchAccepted(batch_run_id=me.id, status=me.status, total_pages=me.total_pages)


@router.get("/batch-runs/{batch_run_id}", response_model=BatchRunRead, tags=["batch"])
async def get_batch_run(
    batch_run_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> BatchRun:
    """Tiến độ mẻ. `status` được **suy ra từ các mục con**, không bao giờ đặt tay.

    Còn một trang chưa xong thì `status` vẫn là `running` — không có chuyện báo `completed`
    trong khi vẫn còn việc.
    """
    me = await session.get(BatchRun, batch_run_id)
    if me is None:
        raise HTTPException(status_code=404, detail="Batch run không tồn tại")
    await bao_dam_quyen(session, nguoi, me)
    return me


@router.get("/batch-runs/{batch_run_id}/items", response_model=BatchItemsPage, tags=["batch"])
async def list_batch_items(
    batch_run_id: uuid.UUID,
    status_filter: BatchItemStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    cursor: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> BatchItemsPage:
    """Từng trang trong mẻ, sắp theo `page_order` đã chụp lúc tạo."""
    me = await session.get(BatchRun, batch_run_id)
    if me is None:
        raise HTTPException(status_code=404, detail=LOI_KHONG_THAY)
    await bao_dam_quyen(session, nguoi, me)
    stmt = select(BatchItem).where(BatchItem.batch_run_id == batch_run_id)
    if status_filter is not None:
        stmt = stmt.where(BatchItem.status == status_filter)
    rows = list(
        (await session.execute(
            stmt.order_by(BatchItem.page_order).offset(cursor).limit(limit + 1)
        )).scalars()
    )
    con_nua = len(rows) > limit
    return BatchItemsPage(
        items=[BatchItemRead.model_validate(r) for r in rows[:limit]],
        next_cursor=(cursor + limit) if con_nua else None,
    )


@router.post(
    "/batch-runs/{batch_run_id}/resume",
    response_model=BatchResumeAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["batch"],
)
async def resume_batch_run(
    batch_run_id: uuid.UUID,
    body: BatchResumeRequest,
    session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> BatchResumeAccepted:
    """Chạy lại các trang `failed`/`blocked_quota`. **Không đụng** trang đã xong.

    Chọn nhầm một mục đã `completed` sẽ bị từ chối 422 chứ không âm thầm bỏ qua — im lặng bỏ
    qua khiến người dùng tưởng đã chạy lại.
    """
    await _bao_dam_quyen_theo_id(session, nguoi, BatchRun, batch_run_id)
    from app.services.batch.orchestrator import BatchInvalid

    try:
        dem = _dieu_phoi().resume_failed(batch_run_id, body.item_ids)
    except BatchInvalid as exc:
        ma = 404 if "batch_not_found" in str(exc) else 422
        raise HTTPException(status_code=ma, detail=str(exc)) from exc

    me = await session.get(BatchRun, batch_run_id)
    await session.refresh(me)
    return BatchResumeAccepted(batch_run_id=batch_run_id, resumed_count=dem, status=me.status)


@router.post(
    "/batch-runs/{batch_run_id}/cancel",
    response_model=BatchRunRead,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["batch"],
)
async def cancel_batch_run(
    batch_run_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> BatchRun:
    """Dừng đẩy việc mới. Việc **đang chạy vẫn chạy nốt** — cắt ngang dễ để lại dữ liệu dở dang."""
    await _bao_dam_quyen_theo_id(session, nguoi, BatchRun, batch_run_id)
    from app.services.batch.orchestrator import BatchInvalid

    try:
        _dieu_phoi().cancel(batch_run_id)
    except BatchInvalid as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    me = await session.get(BatchRun, batch_run_id)
    await session.refresh(me)
    return me


# ============================ M10: khai báo mục đích & cảnh báo trước khi xuất ============================


@router.get(
    "/projects/{project_id}/export-warnings",
    response_model=ExportWarningsRead,
    tags=["compliance"],
)
async def get_export_warnings(
    project_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> ExportWarningsRead:
    """Những gì người dùng phải nhìn thấy TRƯỚC khi mang file đi.

    Chỉ đếm trên các trang **sẽ được xuất**: vùng lỗi ở trang chưa chèn chữ xong không nằm trong
    file giao đi, đếm vào chỉ làm người dùng hoang mang rồi bỏ qua cả cảnh báo thật.

    `acknowledged` để giao diện biết đã xác nhận cho chapter này chưa — cảnh báo hiện **một lần**.
    """
    await _get_project_or_404(session, project_id, nguoi)
    from app.services.compliance import ComplianceGate

    cb = await ComplianceGate().get_export_warnings(session, project_id)
    # Gọi THẲNG hàm của endpoint khác, không qua FastAPI — nên phải tự truyền `nguoi`.
    # Bỏ qua thì `nguoi` vào hàm dưới dạng object `Depends` chưa được giải, và kiểm quyền
    # bên trong nổ AttributeError thay vì trả 404.
    cl = await get_project_quality_summary(project_id, session, nguoi)
    # E14: đếm theo BỐ CỤC, tách hẳn khỏi tràn khung (chữ không vừa) và khỏi chất lượng E12.
    # Một vùng vẫn có thể vừa khít bên trong khung dự phòng mà vẫn nên xem lại bằng mắt.
    bo_cuc = dict((await session.execute(
        select(RegionSafeArea.status, func.count())
        .join(TextRegion, TextRegion.id == RegionSafeArea.region_id)
        .join(Page, Page.id == TextRegion.page_id)
        .where(Page.project_id == project_id)
        .group_by(RegionSafeArea.status)
    )).all())
    # E15: đếm theo HƯỚNG CHỮ, khối thứ năm và tách khỏi cả bốn khối trước.
    huong = dict((await session.execute(
        select(RegionTextOrientation.orientation, func.count())
        .join(TextRegion, TextRegion.id == RegionTextOrientation.region_id)
        .join(Page, Page.id == TextRegion.page_id)
        .where(Page.project_id == project_id)
        .group_by(RegionTextOrientation.orientation)
    )).all())
    doc_xong = int(await session.scalar(
        select(func.count()).select_from(RegionTextOrientation)
        .join(TextRegion, TextRegion.id == RegionTextOrientation.region_id)
        .join(Page, Page.id == TextRegion.page_id)
        .where(Page.project_id == project_id,
               RegionTextOrientation.orientation == TextOrientation.vertical_ttb,
               RegionTextOrientation.status == OrientationStatus.ready)
    ) or 0)
    doc_tong = int(huong.get(TextOrientation.vertical_ttb, 0))

    # P1 — TỔNG token đã tiêu. Cộng giá trị đã ghi, không tính lại token.
    #
    # Đếm trên CẢ chapter, khác với mọi số ở trên (chỉ đếm trang sẽ được xuất). Có chủ đích:
    # token đã tiêu là tiền đã mất, kể cả ở trang cuối cùng không lọt vào file xuất. Giấu phần
    # đó đi là báo thiếu chi phí cho người trả tiền.
    #
    # `SUM` của Postgres trả NULL khi không có dòng nào hợp lệ — giữ nguyên NULL đó thay vì ép
    # về 0, vì "chưa trang nào dùng engine tốn token" khác hẳn "đã dùng mà tốn 0 token".
    tong_token = await session.scalar(
        select(func.sum(TranslationResult.token_cost))
        .join(TextRegion, TextRegion.id == TranslationResult.region_id)
        .join(Page, Page.id == TextRegion.page_id)
        .where(Page.project_id == project_id)
    )

    return ExportWarningsRead(
        token_cost_total=int(tong_token) if tong_token is not None else None,
        overflow_warning_count=cb.overflow_warning_count,
        needs_manual_count=cb.needs_manual_count,
        font_missing_count=cb.font_missing_count,
        acknowledged=cb.acknowledged,
        acknowledged_at=cb.acknowledged_at,
        shape_fallback_count=int(bo_cuc.get(SafeAreaStatus.fallback_rectangle, 0)),
        shape_needs_review_count=int(bo_cuc.get(SafeAreaStatus.needs_review, 0))
        + int(bo_cuc.get(SafeAreaStatus.failed, 0)),
        orientation_vertical_rendered_count=doc_xong,
        orientation_review_count=(doc_tong - doc_xong)
        + int(huong.get(TextOrientation.rotated_horizontal, 0)),
        orientation_unknown_count=int(huong.get(TextOrientation.unknown, 0)),
        quality_needs_review_count=cl.can_ra_soat,
        quality_unassessed_count=cl.chua_danh_gia,
        quality_reviewed_skip_count=cl.da_bo_qua,
        glossary_approved_count=cb.glossary_approved_count,
    )


@router.post(
    "/export-jobs/{job_id}/acknowledge", response_model=AcknowledgeRead, tags=["compliance"]
)
async def acknowledge_export(
    job_id: uuid.UUID,
    body: AcknowledgeRequest,
    session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> AcknowledgeRead:
    """Ghi lại việc người dùng đã đọc cảnh báo bản quyền cho lần xuất này.

    **Không chặn xuất.** Đây là công cụ cá nhân; chặn cứng chỉ khiến người ta đi đường vòng, mà
    cũng chẳng bảo vệ được ai. Việc của endpoint này là để lại **bằng chứng đã xem cảnh báo**:
    lúc nào, khai báo dùng vào việc gì, và **đúng những con số cảnh báo hiện trên màn hình lúc đó**.

    Số cảnh báo được đếm lại tại đây chứ không nhận từ giao diện gửi lên — số do máy khách gửi thì
    không còn là bằng chứng nữa.
    """
    job = await session.get(ExportJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Việc xuất không tồn tại")
    await bao_dam_quyen(session, nguoi, job)
    project = await session.get(Project, job.project_id)

    from app.services.compliance import ComplianceGate

    cong = ComplianceGate()
    cb = await cong.get_export_warnings(session, job.project_id)
    ban_ghi = await cong.log_export_acknowledgement(
        session,
        project_id=job.project_id,
        export_job_id=job.id,
        intended_use=project.intended_use,
        overflow_warning_count=cb.overflow_warning_count,
        needs_manual_count=cb.needs_manual_count,
        font_missing_count=cb.font_missing_count,
        user_acknowledged=body.user_acknowledged,
    )
    return AcknowledgeRead.model_validate(ban_ghi, from_attributes=True)


# ============================ E12: cổng chất lượng từng vùng ============================


def _doc_danh_gia(dg, reading_order=None) -> RegionQualityRead:
    """Kèm CÂU tiếng Việt cho mỗi mã lý do — mã trần không nói được gì với người dùng."""
    from app.services.quality.reasons import nhan_ly_do

    return RegionQualityRead(
        region_id=dg.region_id,
        reading_order=reading_order,
        assessment_version=dg.assessment_version,
        relevance=dg.relevance,
        review_status=dg.review_status,
        overall_band=dg.overall_band,
        detector_confidence_state=dg.detector_confidence_state,
        ocr_confidence_state=dg.ocr_confidence_state,
        translation_state=dg.translation_state,
        ly_do=[LyDoRead(ma=m, nhan=nhan_ly_do(m)) for m in (dg.reason_codes or [])],
        evidence_snapshot=dg.evidence_snapshot or {},
        assessed_at=dg.assessed_at,
    )


def _gop_tom_tat(cap: list[tuple], so_tran: int) -> QualitySummary:
    """Đếm theo nhóm. Vùng CHƯA có đánh giá được đếm riêng, tuyệt đối không gộp vào 'rõ ràng'."""
    ro = ra_soat = chua = bo_qua = 0
    theo_loai: dict[str, int] = {}
    for _, dg in cap:
        if dg is None:
            chua += 1
            continue
        theo_loai[dg.relevance.value] = theo_loai.get(dg.relevance.value, 0) + 1
        if dg.review_status is ReviewStatus.reviewed_skip:
            bo_qua += 1
        elif dg.overall_band is OverallBand.blocked:
            chua += 1
        elif dg.review_status is ReviewStatus.needs_review:
            ra_soat += 1
        else:
            ro += 1
    return QualitySummary(
        tong_vung=len(cap), ro_rang=ro, can_ra_soat=ra_soat, chua_danh_gia=chua,
        da_bo_qua=bo_qua, vung_tran_khung=so_tran, theo_phan_loai=theo_loai,
    )


async def _cap_vung_danh_gia(session: AsyncSession, page_ids: list[uuid.UUID]) -> list[tuple]:
    if not page_ids:
        return []
    rows = (await session.execute(
        select(TextRegion, RegionQualityAssessment)
        .outerjoin(RegionQualityAssessment,
                   RegionQualityAssessment.region_id == TextRegion.id)
        .where(TextRegion.page_id.in_(page_ids))
        .order_by(TextRegion.reading_order.nulls_last(), TextRegion.bbox_y)
    )).all()
    return [(r[0], r[1]) for r in rows]


@router.get("/pages/{page_id}/quality", response_model=PageQualityRead, tags=["quality"])
async def get_page_quality(
    page_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> PageQualityRead:
    """Đánh giá chất lượng từng vùng của một trang, sắp theo thứ tự đọc.

    Vùng chưa được chấm **không** biến mất khỏi danh sách và **không** bị coi là sạch — nó nằm
    trong `chua_danh_gia`.
    """
    await _get_page_or_404(session, page_id, nguoi)
    cap = await _cap_vung_danh_gia(session, [page_id])
    so_tran = (await session.execute(
        select(func.count()).select_from(TypesetResult)
        .join(TextRegion, TextRegion.id == TypesetResult.region_id)
        .where(TextRegion.page_id == page_id,
               TypesetResult.fit_status == FitStatus.overflow_warning)
    )).scalar() or 0
    phien_ban = next((dg.assessment_version for _, dg in cap if dg is not None), None)
    return PageQualityRead(
        page_id=page_id,
        assessment_version=phien_ban,
        summary=_gop_tom_tat(cap, int(so_tran)),
        regions=[_doc_danh_gia(dg, v.reading_order) for v, dg in cap if dg is not None],
    )


@router.get(
    "/projects/{project_id}/quality-summary", response_model=QualitySummary, tags=["quality"]
)
async def get_project_quality_summary(
    project_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> QualitySummary:
    """Tổng hợp cho cả chapter — dùng ở màn chapter và ở hộp thoại xuất."""
    await _get_project_or_404(session, project_id, nguoi)
    page_ids = list((await session.execute(
        select(Page.id).where(Page.project_id == project_id))).scalars())
    cap = await _cap_vung_danh_gia(session, page_ids)
    so_tran = 0
    if page_ids:
        so_tran = (await session.execute(
            select(func.count()).select_from(TypesetResult)
            .join(TextRegion, TextRegion.id == TypesetResult.region_id)
            .where(TextRegion.page_id.in_(page_ids),
                   TypesetResult.fit_status == FitStatus.overflow_warning)
        )).scalar() or 0
    return _gop_tom_tat(cap, int(so_tran))


@router.post(
    "/regions/{region_id}/quality-review", response_model=QualityReviewRead, tags=["quality"]
)
async def set_quality_review(
    region_id: uuid.UUID,
    body: QualityReviewRequest,
    session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> QualityReviewRead:
    """Ghi quyết định của NGƯỜI: giữ vùng này để dịch, hay bỏ qua nó.

    "Bỏ qua" ở đây là quyết định có chủ ý của người dùng, **không** phải xoá: khung chữ, chữ gốc,
    bản dịch và kết quả căn chữ đều giữ nguyên trong cơ sở dữ liệu.

    Máy khách chỉ được gửi `keep`/`skip` — không được tự đặt mức, mã lý do hay bằng chứng.
    """
    vung = await session.get(TextRegion, region_id)
    if vung is None:
        raise HTTPException(status_code=404, detail="Vùng không tồn tại")
    await bao_dam_quyen(session, nguoi, vung)
    dg = (await session.execute(
        select(RegionQualityAssessment)
        .where(RegionQualityAssessment.region_id == region_id))).scalars().first()
    if dg is None:
        raise HTTPException(
            status_code=409,
            detail="Vùng này chưa được đánh giá chất lượng — chạy lại bước căn chữ trước.",
        )
    dg.review_status = (ReviewStatus.reviewed_keep if body.decision == "keep"
                        else ReviewStatus.reviewed_skip)
    await session.commit()
    await session.refresh(dg)
    return QualityReviewRead(
        region_id=region_id, review_status=dg.review_status,
        relevance=dg.relevance, overall_band=dg.overall_band,
    )


@router.get("/batch-config", response_model=BatchConfigRead, tags=["batch"])
async def get_batch_config(settings: Settings = Depends(get_settings), nguoi: NguoiDung = Depends(nguoi_dung_hien_tai)) -> BatchConfigRead:
    """Cho giao diện biết chạy mẻ được cấu hình thế nào — **không có khoá bí mật nào ở đây**.

    `llm_configured` chỉ là true/false: giao diện cần biết có bật được lựa chọn dịch bằng LLM
    hay không, và nếu không thì nói rõ lý do ngay lúc chọn, thay vì để người dùng bấm rồi nhận 422.
    """
    if not settings.llm_configured:
        await run_in_threadpool(dong_bo_khoa_ai_dong, settings)
    return BatchConfigRead(
        llm_configured=settings.llm_configured,
        llm_project_rpm=settings.llm_project_rpm,
        batch_max_concurrent_pages=settings.batch_max_concurrent_pages,
        batch_max_retries=settings.batch_max_retries,
        batch_retry_backoff_base_seconds=settings.batch_retry_backoff_base_seconds,
        batch_retry_backoff_max_seconds=settings.batch_retry_backoff_max_seconds,
    )


@router.get("/projects/{project_id}/batch-runs", response_model=BatchRunList, tags=["batch"])
async def list_batch_runs(
    project_id: uuid.UUID,
    limit: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> BatchRunList:
    """Các mẻ của project, mới nhất trước.

    Không có endpoint này thì giao diện phải tự nhớ mã mẻ trong trình duyệt — tải lại trang là
    mất dấu mẻ đang chạy, và người vận hành không còn cách nào nhìn thấy tiến độ.
    """
    await _get_project_or_404(session, project_id, nguoi)
    rows = list(
        (await session.execute(
            select(BatchRun).where(BatchRun.project_id == project_id)
            .order_by(BatchRun.created_at.desc()).limit(limit)
        )).scalars()
    )
    return BatchRunList(runs=[BatchRunRead.model_validate(r) for r in rows])


# ============================ E13: thuật ngữ & rà soát nhất quán ============================


def _dich_vu_glossary(session):
    from app.services.consistency.glossary import GlossaryService

    return GlossaryService(session)


async def _thuoc_project_hoac_404(session, doi_tuong, project_id: uuid.UUID, ten: str):
    """Chặn truy cập chéo chapter: id của chapter khác thì coi như không tồn tại."""
    if doi_tuong is None or doi_tuong.project_id != project_id:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy {ten} trong chapter này")
    return doi_tuong


@router.get(
    "/projects/{project_id}/glossary", response_model=list[GlossaryEntryRead], tags=["glossary"]
)
async def list_glossary(
    project_id: uuid.UUID,
    status_filter: GlossaryStatus | None = Query(default=None, alias="status"),
    term_type: TermType | None = None,
    session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> list[GlossaryEntry]:
    """Thuật ngữ đã chốt của **riêng chapter này**.

    Cố ý không dùng chung giữa các chapter: cách dịch hợp ở truyện này có thể sai hẳn ở truyện
    khác, mỗi bộ có thế giới riêng.
    """
    await _get_project_or_404(session, project_id, nguoi)
    stmt = select(GlossaryEntry).where(GlossaryEntry.project_id == project_id)
    if status_filter is not None:
        stmt = stmt.where(GlossaryEntry.status == status_filter)
    if term_type is not None:
        stmt = stmt.where(GlossaryEntry.term_type == term_type)
    return list((await session.execute(stmt.order_by(GlossaryEntry.source_term))).scalars())


@router.post(
    "/projects/{project_id}/glossary",
    response_model=GlossaryEntryRead,
    status_code=status.HTTP_201_CREATED,
    tags=["glossary"],
)
async def create_glossary_entry(
    project_id: uuid.UUID, body: GlossaryEntryCreate, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> GlossaryEntry:
    """Thêm một thuật ngữ. Luôn bắt đầu ở **nháp** — phải duyệt rồi mới được đem đi quét."""
    from app.core.db_sync import sync_session
    from app.services.consistency.glossary import GlossaryInvalid

    await _get_project_or_404(session, project_id, nguoi)
    try:
        with sync_session() as s:
            entry = _dich_vu_glossary(s).create_entry(project_id, body.model_dump())
            entry_id = entry.id
    except GlossaryInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return await session.get(GlossaryEntry, entry_id)


@router.patch("/glossary/{entry_id}", response_model=GlossaryEntryRead, tags=["glossary"])
async def update_glossary_entry(
    entry_id: uuid.UUID, body: GlossaryEntryUpdate, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> GlossaryEntry:
    """Sửa thuật ngữ. **Sửa nội dung của thuật ngữ đã duyệt sẽ đưa nó về nháp.**

    Không làm vậy thì một luật cả chapter đang dùng có thể bị đổi nghĩa âm thầm, và mọi việc rà
    soát tạo ra từ luật cũ thành vô nghĩa mà không ai biết.
    """
    await _bao_dam_quyen_theo_id(session, nguoi, GlossaryEntry, entry_id)
    from app.core.db_sync import sync_session
    from app.services.consistency.glossary import GlossaryInvalid

    try:
        with sync_session() as s:
            _dich_vu_glossary(s).update_entry(
                entry_id, body.model_dump(exclude_unset=True)
            )
    except GlossaryInvalid as exc:
        ma = 404 if "not_found" in str(exc) else 422
        raise HTTPException(status_code=ma, detail=str(exc)) from exc
    await session.commit()
    return await session.get(GlossaryEntry, entry_id)


@router.post("/glossary/{entry_id}/approve", response_model=GlossaryEntryRead, tags=["glossary"])
async def approve_glossary_entry(
    entry_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> GlossaryEntry:
    """Duyệt thuật ngữ — từ đây nó mới tham gia quét."""
    await _bao_dam_quyen_theo_id(session, nguoi, GlossaryEntry, entry_id)
    from app.core.db_sync import sync_session
    from app.services.consistency.glossary import GlossaryInvalid

    try:
        with sync_session() as s:
            _dich_vu_glossary(s).approve_entry(entry_id)
    except GlossaryInvalid as exc:
        ma = 404 if "not_found" in str(exc) else 422
        raise HTTPException(status_code=ma, detail=str(exc)) from exc
    await session.commit()
    return await session.get(GlossaryEntry, entry_id)


@router.post("/glossary/{entry_id}/archive", response_model=GlossaryEntryRead, tags=["glossary"])
async def archive_glossary_entry(
    entry_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> GlossaryEntry:
    """Cất thuật ngữ đi. **Không xoá** — các việc rà soát đã tạo từ nó vẫn còn để đối chiếu."""
    await _bao_dam_quyen_theo_id(session, nguoi, GlossaryEntry, entry_id)
    from app.core.db_sync import sync_session
    from app.services.consistency.glossary import GlossaryInvalid

    try:
        with sync_session() as s:
            _dich_vu_glossary(s).archive_entry(entry_id)
    except GlossaryInvalid as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return await session.get(GlossaryEntry, entry_id)


# ---------------- hồ sơ giọng nhân vật ----------------


@router.get(
    "/projects/{project_id}/voice-profiles", response_model=list[VoiceProfileRead], tags=["glossary"]
)
async def list_voice_profiles(
    project_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> list[CharacterVoiceProfile]:
    await _get_project_or_404(session, project_id, nguoi)
    return list(
        (await session.execute(
            select(CharacterVoiceProfile)
            .where(CharacterVoiceProfile.project_id == project_id)
            .order_by(CharacterVoiceProfile.character_name)
        )).scalars()
    )


@router.post(
    "/projects/{project_id}/voice-profiles",
    response_model=VoiceProfileRead,
    status_code=status.HTTP_201_CREATED,
    tags=["glossary"],
)
async def create_voice_profile(
    project_id: uuid.UUID, body: VoiceProfileCreate, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> CharacterVoiceProfile:
    """Hồ sơ giọng nhân vật — là **hướng dẫn biên tập của bạn**, không phải suy luận của máy.

    E13 không tự đoán tính cách nhân vật và không dùng hồ sơ này để tự sửa lời thoại.
    """
    from app.core.db_sync import sync_session
    from app.services.consistency.glossary import GlossaryInvalid, VoiceProfileService

    await _get_project_or_404(session, project_id, nguoi)
    try:
        with sync_session() as s:
            hs = VoiceProfileService(s).create(project_id, body.model_dump())
            hs_id = hs.id
    except GlossaryInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return await session.get(CharacterVoiceProfile, hs_id)


@router.patch("/voice-profiles/{profile_id}", response_model=VoiceProfileRead, tags=["glossary"])
async def update_voice_profile(
    profile_id: uuid.UUID, body: VoiceProfileUpdate, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> CharacterVoiceProfile:
    await _bao_dam_quyen_theo_id(session, nguoi, CharacterVoiceProfile, profile_id)
    from app.core.db_sync import sync_session
    from app.services.consistency.glossary import GlossaryInvalid, VoiceProfileService

    try:
        with sync_session() as s:
            VoiceProfileService(s).update(profile_id, body.model_dump(exclude_unset=True))
    except GlossaryInvalid as exc:
        ma = 404 if "not_found" in str(exc) else 422
        raise HTTPException(status_code=ma, detail=str(exc)) from exc
    await session.commit()
    return await session.get(CharacterVoiceProfile, profile_id)


@router.post(
    "/voice-profiles/{profile_id}/activate", response_model=VoiceProfileRead, tags=["glossary"]
)
async def activate_voice_profile(
    profile_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> CharacterVoiceProfile:
    await _bao_dam_quyen_theo_id(session, nguoi, CharacterVoiceProfile, profile_id)
    return await _doi_trang_thai_ho_so(profile_id, VoiceProfileStatus.active, session)


@router.post(
    "/voice-profiles/{profile_id}/archive", response_model=VoiceProfileRead, tags=["glossary"]
)
async def archive_voice_profile(
    profile_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> CharacterVoiceProfile:
    await _bao_dam_quyen_theo_id(session, nguoi, CharacterVoiceProfile, profile_id)
    return await _doi_trang_thai_ho_so(profile_id, VoiceProfileStatus.archived, session)


async def _doi_trang_thai_ho_so(profile_id, trang_thai, session):
    from app.core.db_sync import sync_session
    from app.services.consistency.glossary import GlossaryInvalid, VoiceProfileService

    try:
        with sync_session() as s:
            VoiceProfileService(s).set_status(profile_id, trang_thai)
    except GlossaryInvalid as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return await session.get(CharacterVoiceProfile, profile_id)


# ---------------- quét & rà soát ----------------


@router.post(
    "/projects/{project_id}/consistency-scans",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["consistency"],
)
async def create_consistency_scan(
    project_id: uuid.UUID,
    body: ConsistencyScanRequest,
    session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> JobAccepted:
    """Quét cả chapter tìm chỗ dùng thuật ngữ chưa nhất quán.

    Chỉ **tạo việc cần rà soát**, tuyệt đối không sửa bản dịch. Vùng bạn đã bấm "bỏ qua" ở bước
    rà soát chất lượng sẽ không bị quét lại.
    """
    await _get_project_or_404(session, project_id, nguoi)
    trang = (await session.execute(select(Page).where(Page.project_id == project_id).limit(1))).first()
    if trang is None:
        raise HTTPException(status_code=422, detail="no_page: chapter chưa có trang nào")

    job = Job(type=JobType.typeset, page_id=trang[0].id, status=JobStatus.queued)
    session.add(job)
    await session.commit()
    await session.refresh(job)

    sent, ly_do = dispatch_consistency_scan_job(job.id, project_id)
    if not sent:
        job.error_log = ly_do
        await session.commit()
    return JobAccepted(job_id=job.id, page_id=job.page_id, status=job.status)


@router.get(
    "/projects/{project_id}/consistency-summary",
    response_model=ConsistencySummary,
    tags=["consistency"],
)
async def consistency_summary(
    project_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> ConsistencySummary:
    """Đếm việc cần rà soát. **Không có điểm chất lượng** — máy không đo được bản dịch hay dở."""
    await _get_project_or_404(session, project_id, nguoi)
    rows = (await session.execute(
        select(ConsistencyReviewTask.status, ConsistencyReviewTask.task_type)
        .where(ConsistencyReviewTask.project_id == project_id)
    )).all()

    dem = {tt: 0 for tt in ConsistencyTaskStatus}
    theo_loai: dict[str, int] = {}
    for tt, loai in rows:
        dem[tt] += 1
        if tt is ConsistencyTaskStatus.open:
            theo_loai[loai.value] = theo_loai.get(loai.value, 0) + 1

    so_tn = (await session.execute(
        select(func.count()).select_from(GlossaryEntry).where(
            GlossaryEntry.project_id == project_id, GlossaryEntry.status == GlossaryStatus.approved
        )
    )).scalar() or 0
    so_hs = (await session.execute(
        select(func.count()).select_from(CharacterVoiceProfile).where(
            CharacterVoiceProfile.project_id == project_id,
            CharacterVoiceProfile.status == VoiceProfileStatus.active,
        )
    )).scalar() or 0

    return ConsistencySummary(
        open_count=dem[ConsistencyTaskStatus.open],
        accepted_count=dem[ConsistencyTaskStatus.accepted],
        rejected_count=dem[ConsistencyTaskStatus.rejected],
        stale_count=dem[ConsistencyTaskStatus.stale],
        resolved_no_change_count=dem[ConsistencyTaskStatus.resolved_no_change],
        by_type=theo_loai,
        approved_glossary_count=so_tn,
        active_voice_profile_count=so_hs,
    )


@router.get(
    "/projects/{project_id}/consistency-tasks",
    response_model=ConsistencyTasksPage,
    tags=["consistency"],
)
async def list_consistency_tasks(
    project_id: uuid.UUID,
    status_filter: ConsistencyTaskStatus | None = Query(default=None, alias="status"),
    task_type: ConsistencyTaskType | None = None,
    page_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> ConsistencyTasksPage:
    """Danh sách việc cần rà soát, kèm bằng chứng để hiểu vì sao nó được tạo."""
    await _get_project_or_404(session, project_id, nguoi)
    stmt = select(ConsistencyReviewTask).where(ConsistencyReviewTask.project_id == project_id)
    if status_filter is not None:
        stmt = stmt.where(ConsistencyReviewTask.status == status_filter)
    if task_type is not None:
        stmt = stmt.where(ConsistencyReviewTask.task_type == task_type)
    if page_id is not None:
        stmt = stmt.join(TextRegion, TextRegion.id == ConsistencyReviewTask.region_id).where(
            TextRegion.page_id == page_id
        )
    rows = list((await session.execute(
        stmt.order_by(ConsistencyReviewTask.created_at).offset(cursor).limit(limit + 1)
    )).scalars())
    con_nua = len(rows) > limit
    return ConsistencyTasksPage(
        items=[ConsistencyTaskRead.model_validate(r) for r in rows[:limit]],
        next_cursor=(cursor + limit) if con_nua else None,
    )


@router.post(
    "/consistency-tasks/{task_id}/accept",
    response_model=TaskAcceptAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["consistency"],
)
async def accept_consistency_task(
    task_id: uuid.UUID, body: TaskAcceptRequest, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> TaskAcceptAccepted:
    """Áp đề xuất (hoặc bản bạn tự sửa) vào **đúng một vùng**, rồi canh chữ lại vùng đó.

    Bản dịch đã đổi kể từ lần quét ⇒ trả **409**, không áp đè — áp bản cũ sẽ xoá mất phần vừa sửa.
    Cỡ chữ bạn đã ghim ở bước sửa tay được giữ nguyên; chữ mới không vừa thì báo tràn khung.
    """
    await _bao_dam_quyen_theo_id(session, nguoi, ConsistencyReviewTask, task_id)
    from app.core.db_sync import sync_session
    from app.services.consistency.apply import (
        ConsistencyApplyService,
        TaskInvalid,
        TaskNotFound,
        TaskStale,
    )

    try:
        with sync_session() as s:
            kq = ConsistencyApplyService(s).accept_task(task_id, body.edited_text)
    except TaskNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TaskStale as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TaskInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return TaskAcceptAccepted(
        task_id=kq.task_id, region_id=kq.region_id, page_id=kq.page_id,
        refit_job_id=kq.refit_job_id, applied_text=kq.applied_text,
    )


@router.post(
    "/consistency-tasks/{task_id}/reject",
    response_model=ConsistencyTaskRead,
    tags=["consistency"],
)
async def reject_consistency_task(
    task_id: uuid.UUID, body: TaskRejectRequest, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> ConsistencyReviewTask:
    """Giữ bản hiện tại. **Không** đụng vào bản dịch, ảnh hay bố cục."""
    await _bao_dam_quyen_theo_id(session, nguoi, ConsistencyReviewTask, task_id)
    from app.core.db_sync import sync_session
    from app.services.consistency.apply import ConsistencyApplyService, TaskInvalid, TaskNotFound

    try:
        with sync_session() as s:
            ConsistencyApplyService(s).reject_task(task_id, body.resolution)
    except TaskNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TaskInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await session.commit()
    return await session.get(ConsistencyReviewTask, task_id)


@router.get("/jobs/{job_id}", response_model=JobRead, tags=["jobs"])
async def get_job(job_id: uuid.UUID, session: AsyncSession = Depends(get_session), nguoi: NguoiDung = Depends(nguoi_dung_hien_tai)) -> Job:
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    await bao_dam_quyen(session, nguoi, job)
    return job


@router.get("/health", include_in_schema=False)
async def health(session: AsyncSession = Depends(get_session), nguoi: NguoiDung = Depends(nguoi_dung_hien_tai)) -> Response:
    await session.execute(select(1))
    return Response(status_code=200, content='{"status":"ok"}', media_type="application/json")


# ---------------------------------------------------------------------------
# E14 — vùng đặt chữ an toàn theo hình bong bóng
# ---------------------------------------------------------------------------


def _doc_vung_an_toan(ban: RegionSafeArea) -> SafeAreaRead:
    return SafeAreaRead(
        region_id=ban.region_id,
        algorithm_version=ban.algorithm_version,
        source=ban.source.value,
        status=ban.status.value,
        geometry_type=ban.geometry_type.value,
        geometry=ban.geometry_json or {},
        roi={"x": ban.roi_x, "y": ban.roi_y, "w": ban.roi_w, "h": ban.roi_h},
        safe_area_pixels=ban.safe_area_pixels,
        bbox_coverage_ratio=ban.bbox_coverage_ratio,
        reason_codes=list(ban.reason_codes or []),
        config_summary=dict(ban.config_snapshot or {}),
        place_rect=ban.place_rect_json,
    )


@router.get("/regions/{region_id}/safe-area", response_model=SafeAreaRead, tags=["safe-area"])
async def get_region_safe_area(
    region_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> SafeAreaRead:
    """Hình học vùng an toàn của một vùng chữ.

    Chưa tính bao giờ ⇒ **404**, không trả hình rỗng: `geometry=[]` mà đọc thành "vừa khít" là
    đúng kiểu lỗi im lặng E14 sinh ra để chặn.
    """
    # Lấy vùng TRƯỚC: câu truy vấn dưới đi thẳng vào bảng con theo `region_id`, không chạm
    # vào `text_region` nên tự nó không có gì để kiểm quyền.
    await _get_region_or_404(session, region_id, nguoi)
    ban = await session.scalar(
        select(RegionSafeArea).where(RegionSafeArea.region_id == region_id)
    )
    if ban is None:
        raise HTTPException(
            status_code=404,
            detail="safe_area_not_computed: vùng này chưa được tính vùng an toàn",
        )
    return _doc_vung_an_toan(ban)


@router.get(
    "/pages/{page_id}/safe-area-summary",
    response_model=PageSafeAreaSummary,
    tags=["safe-area"],
)
async def get_page_safe_area_summary(
    page_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> PageSafeAreaSummary:
    """Đếm theo trạng thái. `not_computed` để RIÊNG — chưa tính khác hẳn tính rồi không ra hình."""
    page = await session.get(Page, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="page_not_found")
    await bao_dam_quyen(session, nguoi, page)

    tong = await session.scalar(
        select(func.count()).select_from(TextRegion).where(TextRegion.page_id == page_id)
    ) or 0
    rows = (await session.execute(
        select(RegionSafeArea.status, func.count())
        .join(TextRegion, TextRegion.id == RegionSafeArea.region_id)
        .where(TextRegion.page_id == page_id)
        .group_by(RegionSafeArea.status)
    )).all()
    dem = {tt.value: 0 for tt in SafeAreaStatus}
    for tt, n in rows:
        dem[tt.value] = int(n)
    da_tinh = sum(dem.values())
    return PageSafeAreaSummary(
        page_id=page_id,
        total_regions=int(tong),
        shape_derived_count=dem[SafeAreaStatus.ready.value],
        fallback_rectangle_count=dem[SafeAreaStatus.fallback_rectangle.value],
        needs_review_count=dem[SafeAreaStatus.needs_review.value],
        failed_count=dem[SafeAreaStatus.failed.value],
        not_computed_count=max(int(tong) - da_tinh, 0),
    )


@router.post("/pages/{page_id}/retry-safe-area", status_code=202, tags=["safe-area"])
async def retry_page_safe_area(
    page_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> dict:
    """Tính lại vùng an toàn cho cả trang rồi căn chữ lại.

    Cố ý **không** thêm loại việc mới: bước căn chữ tự tính lại vùng nào chưa có hình dùng
    được, nên "tính lại" chính là chạy lại bước căn chữ. API chỉ xếp việc, mọi xử lý ảnh ở worker.
    """
    page = await session.get(Page, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="page_not_found")
    await bao_dam_quyen(session, nguoi, page)
    if not page.clean_image_path:
        raise HTTPException(
            status_code=422,
            detail="no_clean_image: chưa xoá chữ xong nên chưa có ảnh để tìm hình bong bóng",
        )

    await session.execute(
        delete(RegionSafeArea).where(
            RegionSafeArea.region_id.in_(
                select(TextRegion.id).where(TextRegion.page_id == page_id)
            )
        )
    )
    job = Job(type=JobType.typeset, page_id=page_id, status=JobStatus.queued)
    session.add(job)
    await session.commit()
    await session.refresh(job)

    sent, reason = dispatch_typeset_job(job.id)
    return {
        "job_id": str(job.id),
        "page_id": str(page_id),
        "status": "queued" if sent else "queue_unavailable",
        "detail": reason,
    }


# ---------------------------------------------------------------------------
# E15 — hướng chữ
# ---------------------------------------------------------------------------


@router.get("/regions/{region_id}/orientation", response_model=OrientationRead,
            tags=["orientation"])
async def get_region_orientation(
    region_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> OrientationRead:
    """Chưa phân tích ⇒ **404**. Không trả `unknown` giả để khỏi bị đọc thành 'đã kiểm rồi'."""
    await _get_region_or_404(session, region_id, nguoi)
    ban = await session.scalar(
        select(RegionTextOrientation).where(RegionTextOrientation.region_id == region_id)
    )
    if ban is None:
        raise HTTPException(
            status_code=404,
            detail="orientation_not_analyzed: vùng này chưa được nhận biết hướng chữ",
        )
    return OrientationRead(
        region_id=ban.region_id,
        algorithm_version=ban.algorithm_version,
        orientation=ban.orientation.value,
        source=ban.source.value,
        status=ban.status.value,
        rotation_degrees=ban.rotation_degrees,
        line_count_estimate=ban.line_count_estimate,
        reason_codes=list(ban.reason_codes or []),
        evidence_summary=dict(ban.evidence_snapshot or {}),
    )


@router.get("/pages/{page_id}/orientation-summary", response_model=PageOrientationSummary,
            tags=["orientation"])
async def get_page_orientation_summary(
    page_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> PageOrientationSummary:
    page = await session.get(Page, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="page_not_found")
    await bao_dam_quyen(session, nguoi, page)

    tong = await session.scalar(
        select(func.count()).select_from(TextRegion).where(TextRegion.page_id == page_id)
    ) or 0
    rows = (await session.execute(
        select(RegionTextOrientation.orientation, RegionTextOrientation.status, func.count())
        .join(TextRegion, TextRegion.id == RegionTextOrientation.region_id)
        .where(TextRegion.page_id == page_id)
        .group_by(RegionTextOrientation.orientation, RegionTextOrientation.status)
    )).all()

    d = {"ngang": 0, "doc_xong": 0, "doc_can_xem": 0, "nghieng": 0, "chua_biet": 0, "chua_dung": 0}
    da_pt = 0
    for huong, tt, n in rows:
        n = int(n)
        da_pt += n
        if huong is TextOrientation.horizontal_ltr:
            d["ngang"] += n
        elif huong is TextOrientation.vertical_ttb:
            if tt is OrientationStatus.ready:
                d["doc_xong"] += n
            else:
                d["doc_can_xem"] += n
                if tt is OrientationStatus.unavailable:
                    d["chua_dung"] += n
        elif huong is TextOrientation.rotated_horizontal:
            d["nghieng"] += n
        else:
            d["chua_biet"] += n

    return PageOrientationSummary(
        page_id=page_id,
        total_regions=int(tong),
        horizontal_count=d["ngang"],
        vertical_ready_count=d["doc_xong"],
        vertical_review_count=d["doc_can_xem"],
        rotated_review_count=d["nghieng"],
        unknown_count=d["chua_biet"],
        unavailable_count=d["chua_dung"],
        not_analyzed_count=max(int(tong) - da_pt, 0),
    )


@router.post("/pages/{page_id}/retry-orientation", status_code=202, tags=["orientation"])
async def retry_page_orientation(
    page_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> dict:
    """Xoá kết quả cũ rồi xếp lại việc căn chữ — bước đó tự nhận biết lại hướng còn thiếu."""
    page = await session.get(Page, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="page_not_found")
    await bao_dam_quyen(session, nguoi, page)
    await session.execute(
        delete(RegionTextOrientation).where(
            RegionTextOrientation.region_id.in_(
                select(TextRegion.id).where(TextRegion.page_id == page_id)
            )
        )
    )
    job = Job(type=JobType.typeset, page_id=page_id, status=JobStatus.queued)
    session.add(job)
    await session.commit()
    await session.refresh(job)
    sent, reason = dispatch_typeset_job(job.id)
    return {"job_id": str(job.id), "page_id": str(page_id),
            "status": "queued" if sent else "queue_unavailable", "detail": reason}


# ============================ E17: gợi ý thuật ngữ & xưng hô từ chính chapter ============================


@router.post(
    "/projects/{project_id}/term-official-names",
    response_model=DoiChieuTenResponse,
    tags=["glossary"],
)
async def term_official_names(
    project_id: uuid.UUID,
    payload: DoiChieuTenRequest,
    session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> DoiChieuTenResponse:
    """Đối chiếu danh xưng CỦA CHAPTER với CSDL nhân vật AniList (E17 tầng 3b).

    **Chapter quyết định cần gì, CSDL chỉ trả lời viết thế nào.** Danh sách đem đi hỏi là danh
    xưng rút từ chính chapter (tầng 1); mọi nhân vật CSDL trả về mà không khớp danh sách đó đều
    bị loại và đếm vào `bo_qua`.

    Vì sao không lấy thẳng danh sách từ CSDL: đo 2026-09-04 thấy One Piece có **500** nhân vật
    trong CSDL còn một chapter thật có **3** danh xưng. Đổ 500 mục vào glossary là làm mọi lượt
    rà soát nhất quán ngập cảnh báo vô nghĩa.

    `200` chứ không `202`: đây là một lượt tra CSDL, **không gọi AI** — khác tầng 3a.
    """
    from app.core.db_sync import sync_session
    from app.services.consistency.anilist import tra_ten_chinh_thuc
    from app.services.consistency.ungvien import rut_ung_vien

    await _get_project_or_404(session, project_id, nguoi)

    def _chay():
        with sync_session() as s:
            uv = rut_ung_vien(s, project_id)
        danh_xung = [c.term for c in uv.ung_vien]
        if not danh_xung:
            # Không có gì để đối chiếu thì đừng làm phiền nguồn ngoài — và đừng để người dùng
            # tưởng đã đối chiếu xong khi thật ra chưa hỏi ai.
            from app.services.consistency.anilist import KetQuaDoiChieu

            return KetQuaDoiChieu(
                khong_dung_duoc="Chapter chưa có danh xưng nào để đối chiếu — chạy 'Tìm trong "
                                "chapter' trước."
            )
        return tra_ten_chinh_thuc(danh_xung, payload.ten_bo_truyen)

    kq = await run_in_threadpool(_chay)
    return DoiChieuTenResponse(
        tim_thay_bo_truyen=kq.tim_thay_bo_truyen,
        khop=[
            {
                "danh_xung": k.danh_xung, "ten_day_du": k.ten_day_du,
                "ten_goc": k.ten_goc, "ten_khac": k.ten_khac, "ly_do": k.ly_do,
            }
            for k in kq.khop
        ],
        bo_qua=kq.bo_qua,
        khong_dung_duoc=kq.khong_dung_duoc,
    )


@router.get(
    "/projects/{project_id}/term-candidates",
    response_model=TermCandidatesResponse,
    tags=["glossary"],
)
async def term_candidates(
    project_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> TermCandidatesResponse:
    """Danh xưng lặp lại trong **chính chapter này**, kèm bằng chứng.

    Chỉ đọc — không tạo thuật ngữ nào. Máy tìm ra *có những gì*; bạn vẫn là người quyết *dịch
    thành gì*. Mỗi ứng viên kèm số lần xuất hiện, trang, và trích nguyên văn câu chứa nó.

    `200` chứ không `202` vì đây là xử lý chuỗi trên dữ liệu có sẵn, **không gọi AI**.
    """
    from app.core.db_sync import sync_session
    from app.services.consistency.ungvien import rut_ung_vien

    await _get_project_or_404(session, project_id, nguoi)

    def _chay():
        with sync_session() as s:
            return rut_ung_vien(s, project_id)

    # Bộ này quét toàn bộ chữ của chapter -> chạy trong threadpool để không chặn event loop.
    ket = await run_in_threadpool(_chay)
    return TermCandidatesResponse(
        ung_vien=[
            {
                "source_term": uv.term,
                "term_key": uv.term_key,
                "count": uv.count,
                "pages": sorted(uv.pages),
                "quotes": [
                    {"page_order": q.page_order, "region_id": q.region_id, "text": q.text}
                    for q in uv.quotes
                ],
                "type_guess": uv.type_guess,
                "reasons": sorted(uv.reasons),
            }
            for uv in ket.ung_vien
        ],
        so_vung_da_quet=ket.so_vung_da_quet,
        so_vung_co_chu=ket.so_vung_co_chu,
        trang_thai=ket.trang_thai,
        so_bi_loc_vi_da_co=ket.so_bi_loc_vi_da_co,
        ghi_chu_ngon_ngu=ket.ghi_chu_ngon_ngu,
        so_vung_khong_chac=ket.so_vung_khong_chac,
        so_vung_liet_ke=ket.so_vung_liet_ke,
    )


@router.get(
    "/projects/{project_id}/voice-signals",
    response_model=VoiceSignalsResponse,
    tags=["glossary"],
)
async def voice_signals(
    project_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> VoiceSignalsResponse:
    """Tín hiệu xưng hô **có thật trong bản gốc** (hậu tố kính ngữ, đại từ nhân xưng).

    Giới hạn phải nói trước: hệ thống chưa gán lời thoại cho nhân vật, nên đây là *"trong chapter
    có tín hiệu này"*, KHÔNG phải *"nhân vật X xưng thế này với Y"*. Máy không suy ra tính cách
    nhân vật và không sửa lời thoại theo bất cứ gợi ý nào ở đây.
    """
    from app.core.db_sync import sync_session
    from app.services.consistency.ungvien import rut_tin_hieu_xung_ho

    await _get_project_or_404(session, project_id, nguoi)

    def _chay():
        with sync_session() as s:
            return rut_tin_hieu_xung_ho(s, project_id)

    ket = await run_in_threadpool(_chay)
    return VoiceSignalsResponse(
        tin_hieu=[
            {
                "ma": t.ma,
                "nhan": t.nhan,
                "goi_y_xung_ho": t.goi_y_xung_ho,
                "speech_register_goi_y": t.speech_register_goi_y,
                "count": t.count,
                "ten_lien_quan": sorted(t.ten_lien_quan),
                "quotes": [
                    {"page_order": q.page_order, "region_id": q.region_id, "text": q.text}
                    for q in t.quotes
                ],
            }
            for t in ket.tin_hieu
        ],
        so_vung_da_quet=ket.so_vung_da_quet,
        so_vung_co_chu=ket.so_vung_co_chu,
        trang_thai=ket.trang_thai,
        so_vung_khong_chac=ket.so_vung_khong_chac,
        so_vung_liet_ke=ket.so_vung_liet_ke,
    )


@router.post(
    "/projects/{project_id}/term-suggestions",
    response_model=TermSuggestionRunRead,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["glossary"],
)
async def create_term_suggestion(
    project_id: uuid.UUID,
    body: TermSuggestionCreate,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> TermSuggestionRun:
    """E17 tầng 3 — hỏi mô hình cách dịch cho các danh xưng CÓ THẬT trong chapter.

    `202` vì có gọi AI (nguyên tắc số 4: không chạy AI đồng bộ trong HTTP request).

    Câu hỏi gửi đi **không phải** *"truyện này có nhân vật nào"* — model sẽ luôn trả lời kể cả
    khi không biết. Nó là *"đây là những danh xưng trích từ chính chapter này, người ta thường
    dịch chúng thế nào"*. Mọi dòng trả về đều bị đối chiếu ngược với danh sách đã hỏi; nhắc sai
    thì loại thẳng và đếm vào `dropped_count`.

    Kết quả **không tự thành thuật ngữ** — nó nằm dưới nhãn `goi_y_mo_hinh_chua_duyet` cho tới
    khi bạn tự tay nhận.
    """
    from app.services.dispatch import dispatch_term_suggestion_job

    await _get_project_or_404(session, project_id, nguoi)
    await _giu_suat_chay_lai_trang(session, project_id, JobType.translate, settings)
    run = TermSuggestionRun(project_id=project_id, series_name=body.series_name.strip())
    session.add(run)
    await session.commit()
    await session.refresh(run)

    sent, ly_do = dispatch_term_suggestion_job(run.id)
    if not sent:
        run.error_log = ly_do
        await session.commit()
        await session.refresh(run)
    return run


@router.get(
    "/term-suggestion-runs/{run_id}", response_model=TermSuggestionRunRead, tags=["glossary"]
)
async def get_term_suggestion(
    run_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> TermSuggestionRun:
    """Kết quả một lượt hỏi. `suggestions = null` là **chưa xong**, `[]` là **xong mà không còn
    mục nào qua được cổng đối chiếu** — hai chuyện khác nhau."""
    run = await session.get(TermSuggestionRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="term_suggestion_run_not_found")
    await bao_dam_quyen(session, nguoi, run)
    return run
