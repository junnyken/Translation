"""API contract M1 — prefix /api/v1.

Nguyên tắc bắt buộc:
- Không chạy logic AI đồng bộ trong request. Endpoint upload page trả 202 + job_id.
- Response luôn qua Pydantic schema, không trả SQLAlchemy object.
- Lỗi validate để FastAPI trả 422 mặc định, không tự chế error format.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.models import Job, OCRResult, Page, Project, TextRegion, TranslationResult
from app.models.enums import JobStatus, JobType, PageStatus, TranslationEngine
from app.schemas.common import (
    JobRead,
    OCRResultRead,
    TranslationResultRead,
    PageAccepted,
    PageRead,
    ProjectCreate,
    ProjectDetail,
    ProjectRead,
    RegionRead,
)
from app.services.dispatch import (
    dispatch_detect_job,
    dispatch_inpaint_job,
    dispatch_ocr_job,
    dispatch_translate_job,
)
from app.services.storage import UnsupportedImage, get_storage, sniff_image

router = APIRouter(prefix="/api/v1")


async def _get_project_or_404(session: AsyncSession, project_id: uuid.UUID) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project không tồn tại")
    return project


async def _get_page_or_404(session: AsyncSession, page_id: uuid.UUID) -> Page:
    page = await session.get(Page, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Page không tồn tại")
    return page


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED, tags=["projects"])
async def create_project(payload: ProjectCreate, session: AsyncSession = Depends(get_session)) -> Project:
    project = Project(
        name=payload.name,
        source_lang=payload.source_lang,
        target_lang=payload.target_lang,
        intended_use=payload.intended_use,
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


@router.get("/projects/{project_id}", response_model=ProjectDetail, tags=["projects"])
async def get_project(project_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> Project:
    stmt = select(Project).where(Project.id == project_id).options(selectinload(Project.pages))
    project = (await session.execute(stmt)).scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project không tồn tại")
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
) -> PageAccepted:
    """Nhận ảnh trang, lưu file, tạo Page(status=queued) + Job(type=detect, status=queued).

    M1 chỉ ghi record Job vào hàng đợi (chưa dispatch worker thật — bắt đầu ở M2).
    """
    project = await _get_project_or_404(session, project_id)

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
    page.image_path = storage.save_page_image(project.id, page.id, data, ext)

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
async def get_page(page_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> Page:
    return await _get_page_or_404(session, page_id)


@router.get("/pages/{page_id}/regions", response_model=list[RegionRead], tags=["pages"])
async def list_page_regions(
    page_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> list[RegionRead]:
    """Trả [] cho tới khi M2 (detect) chạy thật — không bịa region."""
    await _get_page_or_404(session, page_id)
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
    page_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> PageAccepted:
    """Xếp lại việc detect cho 1 page (dùng sau khi detection_failed hoặc muốn chạy lại).

    Vẫn chỉ enqueue — không chạy detect trong request.
    """
    page = await _get_page_or_404(session, page_id)
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


@router.get("/pages/{page_id}/ocr", response_model=list[OCRResultRead], tags=["pages"])
async def list_page_ocr(
    page_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> list[OCRResult]:
    """Kết quả OCR theo từng region của page (M3).

    Trả `[]` khi job OCR chưa chạy — không bịa text. `confidence = null` là BÌNH THƯỜNG
    với engine manga-ocr (thư viện không cung cấp điểm tin cậy), không phải lỗi.
    """
    await _get_page_or_404(session, page_id)
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
    page_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> PageAccepted:
    """Xếp lại việc OCR cho 1 page. Chỉ enqueue — không chạy OCR trong request."""
    page = await _get_page_or_404(session, page_id)
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


@router.get(
    "/pages/{page_id}/clean-image",
    tags=["pages"],
    response_class=FileResponse,
    responses={200: {"content": {"image/png": {}}}, 404: {"description": "Chưa có ảnh clean"}},
)
async def get_clean_image(
    page_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> FileResponse:
    """Ảnh đã xoá chữ gốc (M4). Ảnh GỐC không bao giờ bị thay — đây là file riêng."""
    page = await _get_page_or_404(session, page_id)
    if not page.clean_image_path:
        raise HTTPException(
            status_code=404,
            detail="Page chưa có ảnh clean — bước xoá chữ (inpaint) chưa chạy xong",
        )
    storage = get_storage()
    if not storage.exists(page.clean_image_path):
        raise HTTPException(
            status_code=404,
            detail=f"Đường dẫn ảnh clean có trong DB nhưng file không còn: {page.clean_image_path}",
        )
    return FileResponse(storage.abs_path(page.clean_image_path), media_type="image/png")


@router.post(
    "/pages/{page_id}/retry-inpaint",
    response_model=PageAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["pages"],
)
async def retry_inpaint(
    page_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> PageAccepted:
    """Xếp lại việc xoá chữ cho 1 page. Chỉ enqueue — không chạy inpaint trong request."""
    page = await _get_page_or_404(session, page_id)
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
    page_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> list[TranslationResult]:
    """Bản dịch theo từng vùng chữ, sắp theo ĐÚNG thứ tự đọc (M5).

    Trả `[]` khi chưa dịch — không bịa bản dịch. `status`: `ok` · `fallback_used`
    (LLM lỗi nên đã lùi về Google) · `pending` (model không trả dòng này, cần xem lại).
    """
    await _get_page_or_404(session, page_id)
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
) -> PageAccepted:
    """Xếp lại việc dịch. `engine` (tuỳ chọn): `google_fast` (miễn phí) hoặc `llm_context` (tốn token).

    Không truyền `engine` thì dùng mặc định trong cấu hình. Chỉ enqueue, không dịch trong request.
    """
    page = await _get_page_or_404(session, page_id)
    if page.status not in (
        PageStatus.inpainted,
        PageStatus.inpaint_needs_review,
        PageStatus.translated,
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


@router.get("/jobs/{job_id}", response_model=JobRead, tags=["jobs"])
async def get_job(job_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> Job:
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    return job


@router.get("/health", include_in_schema=False)
async def health(session: AsyncSession = Depends(get_session)) -> Response:
    await session.execute(select(1))
    return Response(status_code=200, content='{"status":"ok"}', media_type="application/json")
