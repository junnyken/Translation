"""API contract M1 — prefix /api/v1.

Nguyên tắc bắt buộc:
- Không chạy logic AI đồng bộ trong request. Endpoint upload page trả 202 + job_id.
- Response luôn qua Pydantic schema, không trả SQLAlchemy object.
- Lỗi validate để FastAPI trả 422 mặc định, không tự chế error format.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.models import (
    BatchItem,
    BatchRun,
    ExportJob,
    Job,
    OCRResult,
    Page,
    Project,
    TextRegion,
    TranslationResult,
    TypesetResult,
)
from app.models.enums import (
    BatchItemStatus,
    BatchPipeline,
    BatchStatus,
    ExportFormat,
    FitStatus,
    JobStatus,
    JobType,
    PageStatus,
    TranslationEngine,
)
from app.schemas.common import (
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
    BatchResumeRequest,
    BatchRunList,
    BatchRunRead,
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
    dispatch_typeset_job,
    dispatch_refit_job,
    dispatch_region_reocr_job,
    dispatch_region_retranslate_job,
    dispatch_export_job,
)
from app.services.storage import UnsupportedImage, get_storage, sniff_image
# CHỈ import module quy ước đường dẫn — KHÔNG kéo theo Pillow vào tiến trình API.
from app.services.export.paths import export_relative_dir
from app.services.typeset.paths import preview_relative_path
# Whitelist font của M6 — UI chỉ được chọn trong danh sách này, không tự chế font mới.
from app.services.typeset.registry import FONT_REGISTRY

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
    page_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> list[TypesetResult]:
    """Kết quả canh chữ theo từng vùng, sắp theo ĐÚNG thứ tự đọc (M6).

    Trả `[]` khi chưa canh. `fit_status`: `fit_ok` · `overflow_warning` (không vừa dù đã xuống
    cỡ nhỏ nhất — M7 sẽ sửa tay) · `pending` (vùng chưa có bản dịch nên chưa có gì để canh).
    Cảnh báo tràn khung PHẢI đọc được ở đây, không bị ảnh preview đẹp che mất.
    """
    await _get_page_or_404(session, page_id)
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
    response_class=FileResponse,
    responses={200: {"content": {"image/png": {}}}, 404: {"description": "Chưa render preview"}},
)
async def get_typeset_preview(
    page_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> FileResponse:
    """Ảnh xem thử: ảnh clean của M4 + chữ dịch đã canh (M6).

    CHỈ phục vụ file đã render sẵn — endpoint này không bao giờ tự render (việc nặng thuộc
    worker). Ảnh gốc và ảnh clean không hề bị đụng tới; đây là file thứ ba.
    """
    await _get_page_or_404(session, page_id)
    storage = get_storage()
    rel = preview_relative_path(page_id)
    if not storage.exists(rel):
        raise HTTPException(
            status_code=404,
            detail="Page chưa có ảnh preview — bước canh chữ (typeset) chưa chạy xong",
        )
    # `no-cache` = trình duyệt PHẢI hỏi lại server trước khi dùng bản đã lưu. Đường dẫn preview
    # cố định theo page nên thiếu header này thì sau khi sửa tay (M7) người dùng vẫn thấy ảnh cũ.
    return FileResponse(
        storage.abs_path(rel),
        media_type="image/png",
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


@router.post(
    "/pages/{page_id}/retry-typeset",
    response_model=PageAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["pages"],
)
async def retry_typeset(
    page_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> PageAccepted:
    """Xếp lại việc canh chữ. Chỉ enqueue, không render trong request."""
    page = await _get_page_or_404(session, page_id)
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


async def _get_region_or_404(session: AsyncSession, region_id: uuid.UUID) -> TextRegion:
    region = await session.get(TextRegion, region_id)
    if region is None:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy vùng chữ {region_id}")
    return region


@router.get("/pages/{page_id}/detail", response_model=PageDetail, tags=["pages"])
async def get_page_detail(
    page_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> PageDetail:
    """Gom TẤT CẢ dữ liệu của 1 trang cho màn sửa tay (M7) — 1 lần gọi thay vì 5 lần.

    Mọi cảnh báo đều lộ ra ở đây và **không bị ẩn**: `status` của vùng (`low_confidence`),
    `ocr_status` (`needs_manual`), `fit_status` (`overflow_warning`), cùng cờ `edited_by_user`
    của cả bản dịch lẫn kết quả canh chữ để biết chỗ nào người sửa, chỗ nào máy làm.
    """
    page = await _get_page_or_404(session, page_id)

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
            f"/api/v1/pages/{page_id}/typeset-preview" if storage.exists(preview_rel) else None
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

    region = await _get_region_or_404(session, region_id)
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
) -> JobAccepted:
    """Canh lại chữ cho 1 vùng mà KHÔNG sửa gì (dùng khi đổi cấu hình font/padding)."""
    region = await _get_region_or_404(session, region_id)
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
    region_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> JobAccepted:
    """Đọc lại chữ gốc của 1 vùng từ **ảnh gốc** (ảnh clean đã bị xoá chữ nên không dùng được).

    KHÔNG tự dịch lại và không tự canh lại — người dùng chủ động bấm tiếp, để không âm thầm
    ghi đè bản dịch mà họ có thể đã sửa tay.
    """
    region = await _get_region_or_404(session, region_id)
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
) -> JobAccepted:
    """Dịch lại 1 vùng từ chữ gốc hiện tại. **Ghi đè bản dịch**, kể cả bản đã sửa tay.

    Lưu ý: dịch lại một dòng lẻ thì `llm_context` mất lợi thế ngữ cảnh cả trang.
    KHÔNG tự canh chữ lại — bấm "canh lại" hoặc sửa tiếp thì mới canh.
    """
    region = await _get_region_or_404(session, region_id)
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


async def _get_project_or_404(session: AsyncSession, project_id: uuid.UUID) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project không tồn tại")
    return project


def _thong_ke_xuat_stmt(project_id: uuid.UUID):
    return select(Page).where(Page.project_id == project_id).order_by(Page.order)


@router.get(
    "/projects/{project_id}/export-preview", response_model=ExportPreview, tags=["export"]
)
async def export_preview(
    project_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> ExportPreview:
    """Xem trước TRƯỚC khi xuất: sẽ xuất mấy trang, bỏ qua mấy trang, còn mấy vùng tràn khung.

    Vùng tràn khung **không chặn** việc xuất — nhưng phải hiện rõ ở đây để người dùng chọn:
    xuất luôn, hay quay lại sửa tay (M7) trước.
    """
    await _get_project_or_404(session, project_id)
    pages = list((await session.execute(_thong_ke_xuat_stmt(project_id))).scalars())
    xuat_duoc = [p for p in pages if p.status in (PageStatus.typeset_done, PageStatus.ready_for_export)]

    so_tran = 0
    if xuat_duoc:
        so_tran = (
            await session.execute(
                select(func.count())
                .select_from(TypesetResult)
                .join(TextRegion, TextRegion.id == TypesetResult.region_id)
                .where(
                    TextRegion.page_id.in_([p.id for p in xuat_duoc]),
                    TypesetResult.fit_status == FitStatus.overflow_warning,
                )
            )
        ).scalar() or 0

    return ExportPreview(
        page_count=len(xuat_duoc),
        total_page_count=len(pages),
        skipped_page_count=len(pages) - len(xuat_duoc),
        overflow_warning_count=so_tran,
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
) -> ExportJobAccepted:
    """Xếp việc xuất chapter. Chỉ enqueue — render nhiều trang là việc của worker.

    Trang chưa canh chữ xong sẽ bị **bỏ qua** (không xuất ảnh chưa có chữ); số trang bỏ qua ghi
    vào `error_log` của job. Không trang nào xuất được ⇒ job `failed` với lý do rõ.
    """
    await _get_project_or_404(session, project_id)

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
    job_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> ExportJob:
    """Theo dõi tiến trình xuất. `status` đi `queued → running → done | failed`.

    `status=done` mà `error_log` khác NULL nghĩa là **xuất được nhưng có cảnh báo** —
    đọc kỹ trước khi giao file cho người khác.
    """
    job = await session.get(ExportJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Export job không tồn tại")
    return job


@router.get(
    "/export-jobs/{job_id}/download",
    tags=["export"],
    response_class=FileResponse,
    responses={
        200: {"content": {"application/octet-stream": {}}},
        404: {"description": "Chưa xuất xong hoặc file không còn"},
    },
)
async def download_export(
    job_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> FileResponse:
    """Tải file đã xuất. **Chỉ phục vụ file có sẵn** — không bao giờ tự render ở đây.

    Với `png_single`, kết quả là một THƯ MỤC nhiều file nên không tải một lần được:
    trả `409` kèm hướng dẫn, thay vì trả file sai hoặc dựng ZIP ngầm.
    """
    job = await session.get(ExportJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Export job không tồn tại")
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
    if not storage.exists(job.output_path):
        raise HTTPException(
            status_code=404,
            detail=f"Đường dẫn có trong DB nhưng file không còn: {job.output_path}",
        )
    return FileResponse(
        storage.abs_path(job.output_path),
        media_type="application/octet-stream",
        filename=job.output_path.rsplit("/", 1)[-1],
        headers={"Cache-Control": "no-cache, must-revalidate"},
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
) -> BatchAccepted:
    """Chạy cả project qua pipeline bằng MỘT mẻ theo dõi được.

    Danh sách trang được **chụp lại ngay lúc tạo** theo `Page.order` — trang tải lên sau đó
    không lẫn vào mẻ đang chạy, nên tổng số trang không nhảy lung tung giữa chừng.

    Mỗi trang tiếp tục **từ đúng bước nó đang đứng**, không chạy lại từ đầu: trang đã canh chữ
    xong được đánh `skipped` chứ không bị làm lại (làm lại là xoá mất kết quả đã có).
    """
    await _get_project_or_404(session, project_id)

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
    batch_run_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> BatchRun:
    """Tiến độ mẻ. `status` được **suy ra từ các mục con**, không bao giờ đặt tay.

    Còn một trang chưa xong thì `status` vẫn là `running` — không có chuyện báo `completed`
    trong khi vẫn còn việc.
    """
    me = await session.get(BatchRun, batch_run_id)
    if me is None:
        raise HTTPException(status_code=404, detail="Batch run không tồn tại")
    return me


@router.get("/batch-runs/{batch_run_id}/items", response_model=BatchItemsPage, tags=["batch"])
async def list_batch_items(
    batch_run_id: uuid.UUID,
    status_filter: BatchItemStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    cursor: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> BatchItemsPage:
    """Từng trang trong mẻ, sắp theo `page_order` đã chụp lúc tạo."""
    if await session.get(BatchRun, batch_run_id) is None:
        raise HTTPException(status_code=404, detail="Batch run không tồn tại")
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
) -> BatchResumeAccepted:
    """Chạy lại các trang `failed`/`blocked_quota`. **Không đụng** trang đã xong.

    Chọn nhầm một mục đã `completed` sẽ bị từ chối 422 chứ không âm thầm bỏ qua — im lặng bỏ
    qua khiến người dùng tưởng đã chạy lại.
    """
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
    batch_run_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> BatchRun:
    """Dừng đẩy việc mới. Việc **đang chạy vẫn chạy nốt** — cắt ngang dễ để lại dữ liệu dở dang."""
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
    project_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> ExportWarningsRead:
    """Những gì người dùng phải nhìn thấy TRƯỚC khi mang file đi.

    Chỉ đếm trên các trang **sẽ được xuất**: vùng lỗi ở trang chưa chèn chữ xong không nằm trong
    file giao đi, đếm vào chỉ làm người dùng hoang mang rồi bỏ qua cả cảnh báo thật.

    `acknowledged` để giao diện biết đã xác nhận cho chapter này chưa — cảnh báo hiện **một lần**.
    """
    await _get_project_or_404(session, project_id)
    from app.services.compliance import ComplianceGate

    cb = await ComplianceGate().get_export_warnings(session, project_id)
    return ExportWarningsRead(
        overflow_warning_count=cb.overflow_warning_count,
        needs_manual_count=cb.needs_manual_count,
        acknowledged=cb.acknowledged,
        acknowledged_at=cb.acknowledged_at,
    )


@router.post(
    "/export-jobs/{job_id}/acknowledge", response_model=AcknowledgeRead, tags=["compliance"]
)
async def acknowledge_export(
    job_id: uuid.UUID,
    body: AcknowledgeRequest,
    session: AsyncSession = Depends(get_session),
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
        user_acknowledged=body.user_acknowledged,
    )
    return AcknowledgeRead.model_validate(ban_ghi, from_attributes=True)


@router.get("/batch-config", response_model=BatchConfigRead, tags=["batch"])
async def get_batch_config(settings: Settings = Depends(get_settings)) -> BatchConfigRead:
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
) -> BatchRunList:
    """Các mẻ của project, mới nhất trước.

    Không có endpoint này thì giao diện phải tự nhớ mã mẻ trong trình duyệt — tải lại trang là
    mất dấu mẻ đang chạy, và người vận hành không còn cách nào nhìn thấy tiến độ.
    """
    await _get_project_or_404(session, project_id)
    rows = list(
        (await session.execute(
            select(BatchRun).where(BatchRun.project_id == project_id)
            .order_by(BatchRun.created_at.desc()).limit(limit)
        )).scalars()
    )
    return BatchRunList(runs=[BatchRunRead.model_validate(r) for r in rows])


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
