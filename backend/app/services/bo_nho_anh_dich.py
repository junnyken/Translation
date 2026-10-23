"""E93 — bộ nhớ đệm kết quả dịch theo mã băm SHA-256 của ảnh chuẩn hoá cho `/doc-truyen/trang`.

## Nguyên tắc thiết kế

1. **Bảo toàn cô lập quyền truy cập (IDOR = 0)**: Mỗi người gọi vẫn sở hữu bản ghi `Page` riêng
   trong `Project` của riêng họ. Khi trúng cache, hệ thống sao chép các vùng chữ (`TextRegion`,
   `OCRResult`, `TranslationResult`, `TypesetResult`) và tệp ảnh xem trước (nếu `day_du`) sang
   `Page` mới của người gọi, KHÔNG bao giờ dùng chung `page_id` giữa hai người.
2. **Bảo toàn sổ cái hạn mức**: Kiểm tra cache chỉ chạy SAU khi `giu_cho_moi_chot` đã giữ suất,
   và khi trúng cache sẽ chốt ngay suất đó thành `da_tieu` (tương đương một trang hoàn tất).
3. **Chỉ sao chép trang đã hoàn tất thật sự**: Trang nguồn phải đạt trạng thái đích của chế độ
   tương ứng VÀ có ít nhất một `TextRegion` kèm bản dịch (tránh ăn nhầm ảnh trắng dùng trong test
   đơn vị chỉ gắn cờ trạng thái giả).
"""
from __future__ import annotations

import hashlib
import uuid
from collections import OrderedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.models import OCRResult, Page, TextRegion, TranslationResult, TypesetResult
from app.models.enums import ChePipeline, PageStatus, SourceLang, TranslationEngine
from app.services.typeset.paths import preview_relative_path

_TOI_DA_KHOA = 2048
_BO_NHO_BAM: OrderedDict[tuple[str, str, str, str], list[uuid.UUID]] = OrderedDict()


def tinh_bam_anh(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _khoa(
    bam_anh: str,
    source_lang: SourceLang,
    engine: TranslationEngine,
    che_do: ChePipeline,
) -> tuple[str, str, str, str]:
    return (bam_anh, source_lang.value, engine.value, che_do.value)


def ghi_nhan_trang_anh(
    bam_anh: str,
    source_lang: SourceLang,
    engine: TranslationEngine,
    che_do: ChePipeline,
    page_id: uuid.UUID,
) -> None:
    k = _khoa(bam_anh, source_lang, engine, che_do)
    ds = _BO_NHO_BAM.get(k, [])
    if page_id not in ds:
        ds.append(page_id)
        if len(ds) > 8:
            ds = ds[-8:]
    _BO_NHO_BAM[k] = ds
    _BO_NHO_BAM.move_to_end(k)
    while len(_BO_NHO_BAM) > _TOI_DA_KHOA:
        _BO_NHO_BAM.popitem(last=False)


def xoa_bo_nho_bam() -> None:
    """Dùng cho test đơn vị khi cần làm sạch bộ nhớ băm."""
    _BO_NHO_BAM.clear()


async def thu_sao_chep_tu_cache(
    session: AsyncSession,
    *,
    bam_anh: str,
    source_lang: SourceLang,
    engine: TranslationEngine,
    che_do: ChePipeline,
    dich_page: Page,
    storage,
) -> bool:
    """Thử tìm một trang đã dịch xong có cùng mã băm + cấu hình và chép sang `dich_page`.

    Trả `True` nếu đã sao chép thành công (không cần đẩy Celery job), `False` nếu chưa có.
    """
    k = _khoa(bam_anh, source_lang, engine, che_do)
    ung_vien_ids = list(reversed(_BO_NHO_BAM.get(k, [])))
    if not ung_vien_ids:
        return False

    trang_thai_xong = (
        (PageStatus.translated, PageStatus.typeset_done, PageStatus.ready_for_export)
        if che_do is ChePipeline.chi_chu
        else (PageStatus.typeset_done, PageStatus.ready_for_export)
    )

    for uv_id in ung_vien_ids:
        if uv_id == dich_page.id:
            continue
        nguon = await session.get(Page, uv_id)
        if nguon is None or nguon.status not in trang_thai_xong:
            continue

        rows = (
            await session.execute(
                select(TextRegion, OCRResult, TranslationResult, TypesetResult)
                .outerjoin(OCRResult, OCRResult.region_id == TextRegion.id)
                .outerjoin(TranslationResult, TranslationResult.region_id == TextRegion.id)
                .outerjoin(TypesetResult, TypesetResult.region_id == TextRegion.id)
                .where(TextRegion.page_id == nguon.id)
                .order_by(TextRegion.reading_order.nulls_last(), TextRegion.created_at)
            )
        ).all()
        if not rows or not any(t is not None and t.translated_text for _, _, t, _ in rows):
            continue

        if che_do is ChePipeline.day_du:
            rel_nguon = preview_relative_path(nguon.id)
            if not await run_in_threadpool(storage.exists, rel_nguon):
                continue
            anh_preview = await run_in_threadpool(storage.read, rel_nguon)
            await run_in_threadpool(storage.save, preview_relative_path(dich_page.id), anh_preview)

        dich_page.he_so_ve = nguon.he_so_ve
        dich_page.status = nguon.status

        for r, o, t, ts in rows:
            r_moi = TextRegion(
                page_id=dich_page.id,
                bbox_x=r.bbox_x,
                bbox_y=r.bbox_y,
                bbox_w=r.bbox_w,
                bbox_h=r.bbox_h,
                confidence=r.confidence,
                overlap_suspect=r.overlap_suspect,
                chu_nhan_dien=r.chu_nhan_dien,
                reading_order=r.reading_order,
                status=r.status,
            )
            session.add(r_moi)
            await session.flush()

            if o is not None:
                session.add(
                    OCRResult(
                        region_id=r_moi.id,
                        raw_text=o.raw_text,
                        line_polygons=o.line_polygons,
                        ocr_engine=o.ocr_engine,
                        confidence=o.confidence,
                        status=o.status,
                        edited_by_user=False,
                    )
                )
            if t is not None:
                session.add(
                    TranslationResult(
                        region_id=r_moi.id,
                        translated_text=t.translated_text,
                        engine=t.engine,
                        model_name=t.model_name,
                        token_cost=0,
                        edited_by_user=False,
                        status=t.status,
                    )
                )
            if ts is not None:
                session.add(
                    TypesetResult(
                        region_id=r_moi.id,
                        font_family=ts.font_family,
                        font_size=ts.font_size,
                        wrapped_text=ts.wrapped_text,
                        padding_ratio=ts.padding_ratio,
                        fit_status=ts.fit_status,
                        edited_by_user=False,
                        text_color=ts.text_color,
                        stroke_color=ts.stroke_color,
                        stroke_width=ts.stroke_width,
                        dong_json=ts.dong_json,
                    )
                )

        return True

    return False
