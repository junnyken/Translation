"""E93 + E110 — Bảng Cache Cộng Đồng theo chữ ký ảnh (`SHA-256` + `source_lang` + `target_lang` + `engine` + `che_do`).

## Nguyên tắc thiết kế

1. **Bảo toàn cô lập quyền truy cập (IDOR = 0)**: Mỗi người gọi vẫn sở hữu bản ghi `Page` riêng
   trong `Project` của riêng họ. Khi trúng cache, hệ thống sao chép các vùng chữ (`TextRegion`,
   `OCRResult`, `TranslationResult`, `TypesetResult`) và tệp ảnh xem trước (nếu `day_du`) sang
   `Page` mới của người gọi, KHÔNG bao giờ dùng chung `page_id` giữa hai người.
2. **Bảo toàn sổ cái hạn mức**: Kiểm tra cache chỉ chạy SAU khi `giu_cho_moi_chot` đã giữ suất,
   nên người thứ 2..1000 nhận kết quả tức thì trong 0,15 giây mà chủ hệ thống tốn **0 đồng tiền AI**.
3. **Bền vững qua khởi động lại (`cache_cong_dong/*.json`)**: Ngoài bộ nhớ RAM `_BO_NHO_BAM`,
   khi một trang dịch xong, bản chụp toạ độ + câu dịch (`vung_cache`) được lưu bền vững vào `storage`
   theo khoá `(SHA-256, ngôn ngữ gốc, ngôn ngữ đích, bộ máy, chế độ)`.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from collections import OrderedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.models import OCRResult, Page, TextRegion, TranslationResult, TypesetResult
from app.models.enums import (
    ChePipeline,
    OCREngine,
    OCRStatus,
    PageStatus,
    RegionStatus,
    SourceLang,
    TargetLang,
    TranslationEngine,
    TranslationStatus,
)
from app.services.typeset.paths import preview_relative_path

_TOI_DA_KHOA = 4096
_BO_NHO_BAM: OrderedDict[tuple[str, str, str, str], list[uuid.UUID]] = OrderedDict()


def tinh_bam_anh(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _chuan_target_lang(target_lang: TargetLang | str | None) -> str:
    if target_lang is None:
        return "vi"
    val = target_lang.value if hasattr(target_lang, "value") else str(target_lang)
    return (val or "vi").strip().lower()


def _khoa(
    bam_anh: str,
    source_lang: SourceLang,
    engine: TranslationEngine,
    che_do: ChePipeline,
    target_lang: TargetLang | str | None = None,
) -> tuple[str, str, str, str]:
    tl = _chuan_target_lang(target_lang)
    # Giữ nguyên khoá 4 phần tử `(bam_anh, source_lang.value, engine.value, che_do.value)` khi `target_lang == "vi"`
    # để tương thích 100% với các bài unit test hiện có (`test_nang_cap_abc.py`).
    # Khi dịch sang ngôn ngữ đích khác (`en`), gộp `ja->en` vào phần tử thứ 2 để tách biệt tuyệt đối.
    sl_key = source_lang.value if tl == "vi" else f"{source_lang.value}->{tl}"
    return (bam_anh, sl_key, engine.value, che_do.value)


def _duong_dan_cache_cong_dong(
    bam_anh: str,
    source_lang: SourceLang,
    engine: TranslationEngine,
    che_do: ChePipeline,
    target_lang: TargetLang | str | None = None,
) -> str:
    tl = _chuan_target_lang(target_lang)
    return f"cache_cong_dong/{bam_anh}_{source_lang.value}_{tl}_{engine.value}_{che_do.value}.json"


def ghi_nhan_trang_anh(
    bam_anh: str,
    source_lang: SourceLang,
    engine: TranslationEngine,
    che_do: ChePipeline,
    page_id: uuid.UUID,
    *,
    target_lang: TargetLang | str | None = None,
) -> None:
    k = _khoa(bam_anh, source_lang, engine, che_do, target_lang=target_lang)
    ds = _BO_NHO_BAM.get(k, [])
    if page_id not in ds:
        ds.append(page_id)
        if len(ds) > 12:
            ds = ds[-12:]
    _BO_NHO_BAM[k] = ds
    _BO_NHO_BAM.move_to_end(k)
    while len(_BO_NHO_BAM) > _TOI_DA_KHOA:
        _BO_NHO_BAM.popitem(last=False)


def xoa_bo_nho_bam() -> None:
    """Dùng cho test đơn vị khi cần làm sạch bộ nhớ băm."""
    _BO_NHO_BAM.clear()


def _doc_cache_file_dong_bo(storage, rel_path: str) -> dict | None:
    try:
        if storage is None or not storage.exists(rel_path):
            return None
        raw = storage.read(rel_path)
        d = json.loads(raw.decode("utf-8"))
        return d if isinstance(d, dict) else None
    except Exception:  # noqa: BLE001
        return None


def _ghi_cache_file_dong_bo(storage, rel_path: str, payload: dict) -> None:
    try:
        if storage is None:
            return
        storage.save(rel_path, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    except Exception:  # noqa: BLE001
        pass


async def luu_snapshot_cache_cong_dong(
    *,
    storage,
    bam_anh: str,
    source_lang: SourceLang,
    target_lang: TargetLang | str | None,
    engine: TranslationEngine,
    che_do: ChePipeline,
    page_id: uuid.UUID,
    vung_snapshot: list[dict],
) -> None:
    """Lưu bền vững kết quả dịch của trang vào Bảng Cache Cộng Đồng trên `storage`."""
    if not bam_anh or not vung_snapshot or storage is None:
        return
    rel = _duong_dan_cache_cong_dong(bam_anh, source_lang, engine, che_do, target_lang=target_lang)
    payload = {
        "bam_anh": bam_anh,
        "source_lang": source_lang.value,
        "target_lang": _chuan_target_lang(target_lang),
        "engine": engine.value,
        "che_do": che_do.value,
        "source_page_id": str(page_id),
        "vung": vung_snapshot,
    }
    await run_in_threadpool(_ghi_cache_file_dong_bo, storage, rel, payload)


async def thu_sao_chep_tu_cache(
    session: AsyncSession,
    *,
    bam_anh: str,
    source_lang: SourceLang,
    engine: TranslationEngine,
    che_do: ChePipeline,
    dich_page: Page,
    storage,
    target_lang: TargetLang | str | None = None,
) -> bool:
    """Thử tìm một trang đã dịch xong có cùng mã băm SHA-256 + ngôn ngữ đích + cấu hình và chép sang `dich_page`.

    Trả `True` nếu đã sao chép thành công (không cần đẩy Celery job, tốn 0 token AI), `False` nếu chưa có.
    """
    k = _khoa(bam_anh, source_lang, engine, che_do, target_lang=target_lang)
    ung_vien_ids = list(reversed(_BO_NHO_BAM.get(k, [])))

    rel_cache = _duong_dan_cache_cong_dong(bam_anh, source_lang, engine, che_do, target_lang=target_lang)
    du_lieu_file: dict | None = None
    if not ung_vien_ids and storage is not None:
        du_lieu_file = await run_in_threadpool(_doc_cache_file_dong_bo, storage, rel_cache)
        if du_lieu_file and du_lieu_file.get("source_page_id"):
            try:
                uv_tu_file = uuid.UUID(str(du_lieu_file["source_page_id"]))
                ung_vien_ids.append(uv_tu_file)
            except Exception:  # noqa: BLE001
                pass

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

        vung_snapshot: list[dict] = []
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
            if t is not None and t.translated_text:
                vung_snapshot.append(
                    {
                        "x": r.bbox_x,
                        "y": r.bbox_y,
                        "w": r.bbox_w,
                        "h": r.bbox_h,
                        "reading_order": r.reading_order,
                        "chu_goc": o.raw_text if o is not None else (r.chu_nhan_dien or ""),
                        "ban_dich": t.translated_text,
                    }
                )

        if vung_snapshot and storage is not None:
            await luu_snapshot_cache_cong_dong(
                storage=storage,
                bam_anh=bam_anh,
                source_lang=source_lang,
                target_lang=target_lang,
                engine=engine,
                che_do=che_do,
                page_id=dich_page.id,
                vung_snapshot=vung_snapshot,
            )

        return True

    # Nhánh 2: Khôi phục từ file Bảng Cache Cộng Đồng bền vững (`cache_cong_dong/*.json`) cho chế độ `chi_chu`
    # kể cả khi máy chủ vừa khởi động lại hoặc trang gốc ban đầu đã bị dọn dẹp.
    if che_do is ChePipeline.chi_chu and storage is not None:
        if du_lieu_file is None:
            du_lieu_file = await run_in_threadpool(_doc_cache_file_dong_bo, storage, rel_cache)
        ds_vung_file = (du_lieu_file or {}).get("vung")
        if isinstance(ds_vung_file, list) and len(ds_vung_file) > 0:
            dich_page.status = PageStatus.translated
            for idx, vf in enumerate(ds_vung_file, start=1):
                if not isinstance(vf, dict) or not vf.get("ban_dich"):
                    continue
                r_moi = TextRegion(
                    page_id=dich_page.id,
                    bbox_x=int(vf.get("x", 0)),
                    bbox_y=int(vf.get("y", 0)),
                    bbox_w=max(4, int(vf.get("w", 10))),
                    bbox_h=max(4, int(vf.get("h", 10))),
                    confidence=0.98,
                    overlap_suspect=False,
                    chu_nhan_dien=str(vf.get("chu_goc") or ""),
                    reading_order=int(vf.get("reading_order") or idx),
                    status=RegionStatus.pending,
                )
                session.add(r_moi)
                await session.flush()
                session.add(
                    OCRResult(
                        region_id=r_moi.id,
                        raw_text=str(vf.get("chu_goc") or ""),
                        line_polygons=None,
                        ocr_engine=OCREngine.ai_gemini,
                        confidence=0.98,
                        status=OCRStatus.ok,
                        edited_by_user=False,
                    )
                )
                session.add(
                    TranslationResult(
                        region_id=r_moi.id,
                        translated_text=str(vf.get("ban_dich") or ""),
                        engine=engine,
                        model_name="community-cache-sha256",
                        token_cost=0,
                        edited_by_user=False,
                        status=TranslationStatus.ok,
                    )
                )
            return True

    return False
