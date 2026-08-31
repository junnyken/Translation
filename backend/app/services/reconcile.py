"""P3f — đối chiếu bản ghi với hiện vật thật, rồi nói thật.

Vì sao cần: P3c/P3d/P3e làm hiện vật **từ nay** bền. Chúng **không** hồi sinh được ảnh đã mất —
ảnh gốc mất rồi thì không dựng lại được. Nên sau khi bật kho CSDL, các trang cũ vẫn mang bản ghi
nói "đã canh chữ xong" trong khi bấm vào thì 404.

Đó đúng là thứ CLAUDE.md §3 cấm: *không tự nhận "done" khi thiếu bằng chứng*. Bản ghi là lời
khai; hiện vật là bằng chứng. Mất bằng chứng thì phải rút lời khai, không phải giữ nguyên.

**Không xoá bản dịch hay kết quả canh chữ.** Chúng vẫn đúng và vẫn quý — chỉ có ảnh là mất. Chạy
lại bước xoá chữ sẽ sinh ảnh clean mới rồi dùng lại đúng những bản dịch đó.

Hai chế độ, và mặc định là chế độ KHÔNG ghi gì:
  - `report` — chỉ đếm và ghi log. Dùng để nhìn thiệt hại trước khi động vào dữ liệu.
  - `apply`  — sửa thật.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ExportJob, OCRResult, Page, TextRegion
from app.models.enums import JobStatus, PageStatus
from app.services.storage import IObjectStorage
from app.services.typeset.paths import preview_relative_path

logger = logging.getLogger(__name__)

#: Trạng thái chỉ đạt được KHI ĐÃ có ảnh clean. Mất ảnh clean ⇒ lời khai này hết hiệu lực.
_DOI_HOI_ANH_CLEAN = {
    PageStatus.inpainted,
    PageStatus.inpaint_needs_review,
    PageStatus.translated,
    PageStatus.typeset_done,
    PageStatus.ready_for_export,
}

#: Trạng thái khẳng định "đã có ảnh xem thử".
_DOI_HOI_PREVIEW = {PageStatus.typeset_done, PageStatus.ready_for_export}


@dataclass
class KetQuaDoiChieu:
    trang_mat_anh_clean: int = 0
    trang_mat_preview: int = 0
    job_xuat_mat_file: int = 0
    da_ghi: bool = False
    chi_tiet: list[str] = field(default_factory=list)

    @property
    def tong(self) -> int:
        return self.trang_mat_anh_clean + self.trang_mat_preview + self.job_xuat_mat_file


def _co_hien_vat(storage: IObjectStorage, path: str | None) -> bool:
    """`png_single` lưu output_path là một THƯ MỤC, không phải một hiện vật đơn.

    Nên chỉ hỏi `exists()` là sai: nó luôn trả False cho thư mục ở cả hai backend, và mọi lần
    xuất png_single sẽ bị kết oan là đã mất file.
    """
    if not path:
        return False
    return storage.exists(path) or bool(storage.list_prefix(path))


def _muc_lui_khi_mat_anh_clean(session: Session, page: Page) -> PageStatus:
    """Lùi về mốc gần nhất mà bằng chứng vẫn còn nguyên — không lùi sạch về `queued`.

    Kết quả OCR và vùng chữ nằm trong CSDL nên chúng KHÔNG mất. Lùi quá tay là bắt người dùng
    chạy lại những bước vẫn còn nguyên bằng chứng.
    """
    co_ocr = session.scalar(
        select(OCRResult.id)
        .join(TextRegion, TextRegion.id == OCRResult.region_id)
        .where(TextRegion.page_id == page.id)
        .limit(1)
    )
    if co_ocr is not None:
        return PageStatus.ocr_done
    co_vung = session.scalar(
        select(TextRegion.id).where(TextRegion.page_id == page.id).limit(1)
    )
    return PageStatus.detected if co_vung is not None else PageStatus.queued


def doi_chieu_hien_vat(
    session: Session, storage: IObjectStorage, *, ap_dung: bool
) -> KetQuaDoiChieu:
    """Quét toàn bộ, so bản ghi với kho. `ap_dung=False` thì KHÔNG ghi một chữ nào.

    Idempotent: chạy lần hai trên dữ liệu đã dọn sẽ trả về toàn số 0.
    """
    kq = KetQuaDoiChieu(da_ghi=ap_dung)

    # ---- 1. trang khai có ảnh clean mà kho không có ----
    for page in session.scalars(select(Page).where(Page.clean_image_path.is_not(None))):
        if storage.exists(page.clean_image_path):
            continue
        kq.trang_mat_anh_clean += 1
        moi = _muc_lui_khi_mat_anh_clean(session, page)
        kq.chi_tiet.append(
            f"page {page.id}: mất ảnh clean ({page.clean_image_path}) · "
            f"{page.status.value} -> {moi.value}"
        )
        if ap_dung:
            page.clean_image_path = None
            # Cố ý KHÔNG đi qua `assert_transition`: đây là sửa chữa, không phải một bước của
            # pipeline. Máy trạng thái mô tả đường ĐI TỚI; nó không có đường lùi vì bình thường
            # không được lùi.
            page.status = moi

    # ---- 2. trang khai đã canh chữ mà không có ảnh xem thử (ảnh clean thì vẫn còn) ----
    for page in session.scalars(select(Page).where(Page.status.in_(_DOI_HOI_PREVIEW))):
        if page.clean_image_path is None:
            continue  # đã xử ở bước 1
        if storage.exists(preview_relative_path(page.id)):
            continue
        kq.trang_mat_preview += 1
        kq.chi_tiet.append(
            f"page {page.id}: mất ảnh xem thử · {page.status.value} -> translated"
        )
        if ap_dung:
            page.status = PageStatus.translated

    # ---- 3. lần xuất khai xong mà file không còn ----
    for job in session.scalars(
        select(ExportJob).where(ExportJob.status == JobStatus.done)
    ):
        if _co_hien_vat(storage, job.output_path):
            continue
        kq.job_xuat_mat_file += 1
        kq.chi_tiet.append(f"export_job {job.id}: mất file xuất ({job.output_path})")
        if ap_dung:
            job.status = JobStatus.failed
            job.error_log = (
                "artifact_lost: file xuất không còn trên kho lưu trữ (mất trước khi bật kho bền "
                "— xem docs/REPORT_P3e_POSTGRES_ARTIFACT_STORE.md). Xuất lại để có file mới."
            )[:4000]

    if ap_dung:
        session.commit()

    logger.info(
        "đối chiếu hiện vật (%s): %d trang mất ảnh clean, %d trang mất ảnh xem thử, "
        "%d lần xuất mất file",
        "ĐÃ SỬA" if ap_dung else "chỉ đếm",
        kq.trang_mat_anh_clean,
        kq.trang_mat_preview,
        kq.job_xuat_mat_file,
    )
    for dong in kq.chi_tiet:
        logger.info("  %s", dong)
    return kq
