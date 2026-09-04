"""API contract M1 — prefix /api/v1.

Nguyên tắc bắt buộc:
- Không chạy logic AI đồng bộ trong request. Endpoint upload page trả 202 + job_id.
- Response luôn qua Pydantic schema, không trả SQLAlchemy object.
- Lỗi validate để FastAPI trả 422 mặc định, không tự chế error format.
"""
from __future__ import annotations

import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.quyen import (
    LOI_KHONG_THAY,
    bao_dam_quyen,
    duoc_dung_project,
    nguoi_dung_hien_tai,
)
from app.models import (
    BatchItem,
    NguoiDung,
    RegionSafeArea,
    RegionTextOrientation,
    CharacterVoiceProfile,
    ConsistencyReviewTask,
    GlossaryEntry,
    BatchRun,
    RegionQualityAssessment,
    ExportJob,
    Job,
    OCRResult,
    Page,
    Project,
    TermSuggestionRun,
    TextRegion,
    TranslationResult,
    TypesetResult,
)
from app.models.enums import (
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
    PageStatus,
    TranslationEngine,
)
from app.schemas.common import (
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
    PageAccepted,
    PageRead,
    ProjectCreate,
    ProjectDetail,
    ProjectRead,
    RegionRead,
)
from app.services.dispatch import (
    dispatch_rut_gon_job,
    dispatch_detect_job,
    dispatch_inpaint_job,
    dispatch_ocr_job,
    dispatch_translate_job,
    dispatch_typeset_job,
    dispatch_refit_job,
    dispatch_region_reocr_job,
    dispatch_region_retranslate_job,
    dispatch_export_job,
    dispatch_consistency_scan_job,
)
from app.services.storage import (
    IObjectStorage,
    ObjectStat,
    UnsupportedImage,
    get_storage,
    sniff_image,
)
# CHỈ import module quy ước đường dẫn — KHÔNG kéo theo Pillow vào tiến trình API.
from app.services.export.paths import export_relative_dir
from app.services.typeset.paths import preview_relative_path
# Whitelist font của M6 — UI chỉ được chọn trong danh sách này, không tự chế font mới.
from app.services.typeset.registry import FONT_REGISTRY

router = APIRouter(prefix="/api/v1")


async def _get_project_or_404(
    session: AsyncSession, project_id: uuid.UUID, nguoi: NguoiDung
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
    session: AsyncSession, page_id: uuid.UUID, nguoi: NguoiDung
) -> Page:
    """Lấy trang, ném 404 nếu không có hoặc chapter chứa nó không phải của `nguoi`."""
    page = await session.get(Page, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail=LOI_KHONG_THAY)
    await bao_dam_quyen(session, nguoi, page)
    await bao_dam_quyen(session, nguoi, page)
    return page


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
    return project


@router.get("/projects", response_model=list[ProjectRead], tags=["projects"])
async def list_projects(
    session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> list[Project]:
    """Chapter của tôi + chapter chưa có chủ.

    Endpoint này **mới có ở slice B**. Trước đó giao diện tự nhớ id chapter trong máy, nên
    người dùng mới đăng nhập trên máy khác sẽ không thấy gì cả.

    Chapter chưa có chủ (`chu_so_huu_id IS NULL`, tạo trước slice B) cũng hiện ra, để chúng
    không biến mất khỏi tầm nhìn. Giao diện phải gắn nhãn phân biệt.
    """
    return list(
        (await session.execute(
            select(Project)
            .where(
                (Project.chu_so_huu_id == nguoi.id) | (Project.chu_so_huu_id.is_(None))
            )
            .order_by(Project.created_at.desc())
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

    Nhả xong thì chapter về đúng trạng thái của chapter cũ: ai đăng nhập cũng thấy và nhận được.
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
    return project


@router.post(
    "/projects/{project_id}/pages",
    response_model=PageAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["pages"],
)
async def upload_page(
    project_id: uuid.UUID,
    file: UploadFile = File(..., description="Ảnh trang manga (JPEG/PNG/WEBP)"),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> PageAccepted:
    """Nhận ảnh trang, lưu file, tạo Page(status=queued) + Job(type=detect, status=queued).

    M1 chỉ ghi record Job vào hàng đợi (chưa dispatch worker thật — bắt đầu ở M2).
    """
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
    )
    session.add(page)
    await session.flush()  # lấy page.id, chưa commit

    storage = get_storage()
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


@router.post(
    "/pages/{page_id}/retry-detect",
    response_model=PageAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["pages"],
)
async def retry_detect(
    page_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> PageAccepted:
    """Xếp lại việc detect cho 1 page (dùng sau khi detection_failed hoặc muốn chạy lại).

    Vẫn chỉ enqueue — không chạy detect trong request.
    """
    page = await _get_page_or_404(session, page_id, nguoi)
    if page.status is PageStatus.detecting:
        raise HTTPException(status_code=409, detail="Page đang detect, không xếp thêm việc trùng")

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
    page_id: uuid.UUID, session: AsyncSession = Depends(get_session),
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
    page_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> PageAccepted:
    """Xếp lại việc OCR cho 1 page. Chỉ enqueue — không chạy OCR trong request."""
    page = await _get_page_or_404(session, page_id, nguoi)
    region_count = await session.scalar(
        select(func.count(TextRegion.id)).where(TextRegion.page_id == page_id)
    )
    if not region_count:
        raise HTTPException(
            status_code=409,
            detail="Page chưa có vùng chữ nào — chạy detect trước (POST /pages/{id}/retry-detect)",
        )

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


@router.post(
    "/pages/{page_id}/retry-inpaint",
    response_model=PageAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["pages"],
)
async def retry_inpaint(
    page_id: uuid.UUID, session: AsyncSession = Depends(get_session),
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

    job = Job(type=JobType.inpaint, page_id=page.id, status=JobStatus.queued)
    session.add(job)
    await session.commit()
    await session.refresh(job)

    sent, reason = dispatch_inpaint_job(job.id)
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
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> PageAccepted:
    """Xếp lại việc dịch. `engine` (tuỳ chọn): `google_fast` (miễn phí) hoặc `llm_context` (tốn token).

    Không truyền `engine` thì dùng mặc định trong cấu hình. Chỉ enqueue, không dịch trong request.
    """
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
            translated_text=tr.translated_text if tr else None,
            translation_status=tr.status if tr else None,
            translation_edited_by_user=bool(tr.edited_by_user) if tr else False,
            font_family=ts.font_family if ts else None,
            font_size=ts.font_size if ts else None,
            wrapped_text=ts.wrapped_text if ts else None,
            fit_status=ts.fit_status if ts else None,
            typeset_edited_by_user=bool(ts.edited_by_user) if ts else False,
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
    """Sửa tay 1 vùng: bản dịch / khung chữ / font / cỡ chữ, rồi **canh lại đúng vùng đó**.

    Ghi thẳng phần sửa vào DB, đánh dấu `edited_by_user=true`, rồi xếp việc canh chữ chạy nền
    (không canh trong request). Vì bản canh cũ đã không còn đúng với nội dung mới, `fit_status`
    trả về là **`pending`** — không trả trạng thái cũ để khỏi báo nhầm là "vẫn vừa khung".

    `font_size` = **ghim cỡ chữ**: canh lại sẽ dùng đúng cỡ đó. Bỏ trống = tự dò cỡ như M6.
    Dữ liệu gốc (bbox của M2 thì có sửa, còn chữ OCR của M3) **không bị đụng tới**.
    """
    if not patch.co_thay_doi():
        raise HTTPException(status_code=422, detail="Không có trường nào để sửa")

    region = await _get_region_or_404(session, region_id, nguoi)
    da_sua: list[str] = []

    if patch.bbox is not None:
        region.bbox_x, region.bbox_y = patch.bbox.x, patch.bbox.y
        region.bbox_w, region.bbox_h = patch.bbox.w, patch.bbox.h
        da_sua.append("bbox")

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

    if typeset is not None:
        # Bản canh cũ không còn đúng với nội dung mới -> nói thật là "chưa canh", không giữ fit_ok.
        typeset.fit_status = FitStatus.pending
        typeset.edited_by_user = True

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
    region_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> JobAccepted:
    """Đọc lại chữ gốc của 1 vùng từ **ảnh gốc** (ảnh clean đã bị xoá chữ nên không dùng được).

    KHÔNG tự dịch lại và không tự canh lại — người dùng chủ động bấm tiếp, để không âm thầm
    ghi đè bản dịch mà họ có thể đã sửa tay.
    """
    region = await _get_region_or_404(session, region_id, nguoi)
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
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> JobAccepted:
    """Dịch lại 1 vùng từ chữ gốc hiện tại. **Ghi đè bản dịch**, kể cả bản đã sửa tay.

    Lưu ý: dịch lại một dòng lẻ thì `llm_context` mất lợi thế ngữ cảnh cả trang.
    KHÔNG tự canh chữ lại — bấm "canh lại" hoặc sửa tiếp thì mới canh.
    """
    region = await _get_region_or_404(session, region_id, nguoi)
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
    xuat_duoc = [p for p in pages if p.status in (PageStatus.typeset_done, PageStatus.ready_for_export)]

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


@router.post(
    "/projects/{project_id}/export",
    response_model=ExportJobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["export"],
)
async def create_export(
    project_id: uuid.UUID,
    body: ExportRequest,
    session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> ExportJobAccepted:
    """Xếp việc xuất chapter. Chỉ enqueue — render nhiều trang là việc của worker.

    Trang chưa canh chữ xong sẽ bị **bỏ qua** (không xuất ảnh chưa có chữ); số trang bỏ qua ghi
    vào `error_log` của job. Không trang nào xuất được ⇒ job `failed` với lý do rõ.
    """
    await _get_project_or_404(session, project_id, nguoi)

    job = ExportJob(project_id=project_id, format=body.format, status=JobStatus.queued)
    session.add(job)
    await session.commit()
    await session.refresh(job)

    sent, reason = dispatch_export_job(job.id)
    if not sent:
        job.error_log = reason
        await session.commit()

    return ExportJobAccepted(job_id=job.id, project_id=project_id, status=job.status)


@router.get("/export-jobs/{job_id}", response_model=ExportJobRead, tags=["export"])
async def get_export_job(
    job_id: uuid.UUID, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> ExportJob:
    """Theo dõi tiến trình xuất. `status` đi `queued → running → done | failed`.

    `status=done` mà `error_log` khác NULL nghĩa là **xuất được nhưng có cảnh báo** —
    đọc kỹ trước khi giao file cho người khác.
    """
    job = await session.get(ExportJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Export job không tồn tại")
    await bao_dam_quyen(session, nguoi, job)
    return job


@router.get(
    "/export-jobs/{job_id}/download",
    tags=["export"],
    responses={
        200: {"content": {"application/octet-stream": {}}},
        404: {"description": "Chưa xuất xong hoặc file không còn"},
    },
)
async def download_export(
    job_id: uuid.UUID, request: Request, session: AsyncSession = Depends(get_session),
    nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
) -> Response:
    """Tải file đã xuất. **Chỉ phục vụ file có sẵn** — không bao giờ tự render ở đây.

    Với `png_single`, kết quả là một THƯ MỤC nhiều file nên không tải một lần được:
    trả `409` kèm hướng dẫn, thay vì trả file sai hoặc dựng ZIP ngầm.
    """
    job = await session.get(ExportJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Export job không tồn tại")
    await bao_dam_quyen(session, nguoi, job)
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
    if engine is TranslationEngine.llm_context and not settings.llm_configured:
        # Báo NGAY chứ không xếp việc rồi mới hỏng ở trang thứ nhất.
        raise HTTPException(
            status_code=422,
            detail="llm_not_configured: chưa cấu hình khoá dịch, không dùng được llm_context",
        )

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

    return ExportWarningsRead(
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
