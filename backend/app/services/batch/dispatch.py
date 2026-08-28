"""Đẩy một BƯỚC của pipeline cho một trang (M9).

Chỉ tạo `Job` rồi gọi đúng task cũ của M2–M6. Không có logic xử lý nào ở đây — sao chép logic
pipeline vào bộ điều phối là cách chắc chắn để hai đường xử lý lệch nhau về sau.
"""
from __future__ import annotations

import logging
import uuid

from app.core.db_sync import sync_session
from app.models import BatchRun, Job, Page
from app.models.enums import JobStatus, JobType

logger = logging.getLogger(__name__)

#: bước -> (loại Job, tên task)
_BANG_BUOC = {
    "detect": (JobType.detect, "run_detect_job"),
    "ocr": (JobType.ocr, "run_ocr_job"),
    "inpaint": (JobType.inpaint, "run_inpaint_job"),
    "translate": (JobType.translate, "run_translate_job"),
    "typeset": (JobType.typeset, "run_typeset_job"),
}


def day_viec_buoc(
    page_id: uuid.UUID, buoc: str, batch_run_id: uuid.UUID | None = None, cho_giay: float = 0.0
) -> uuid.UUID:
    """Tạo Job cho `buoc` rồi đẩy vào hàng đợi. Trả job_id.

    `cho_giay` > 0 là lần THỬ LẠI: hẹn giờ chạy thay vì gọi ngay. Thử lại ngay lập tức sau khi
    nhà cung cấp vừa báo "quá nhịp" chính là cách chắc chắn nhất để bị chặn tiếp.
    """
    if buoc not in _BANG_BUOC:
        raise ValueError(f"bước không hợp lệ: {buoc}")
    loai_job, ten_task = _BANG_BUOC[buoc]

    engine = None
    with sync_session() as session:
        page = session.get(Page, page_id)
        if page is None:
            raise ValueError(f"page_not_found: {page_id}")
        if buoc == "translate" and batch_run_id is not None:
            me = session.get(BatchRun, batch_run_id)
            # Engine dịch được CHỐT lúc tạo mẻ, không đọc lại cấu hình lúc chạy — nếu không,
            # đổi cấu hình giữa chừng sẽ khiến các trang trong cùng một mẻ dịch bằng hai engine.
            engine = me.translation_engine.value if me and me.translation_engine else None
        job = Job(type=loai_job, page_id=page_id, status=JobStatus.queued)
        session.add(job)
        session.commit()
        job_id = job.id

    from app.workers import tasks

    task = getattr(tasks, ten_task)
    args = [str(job_id), engine] if buoc == "translate" else [str(job_id)]
    task.apply_async(args=args, countdown=max(cho_giay, 0.0))
    logger.info("mẻ %s: đẩy bước %s cho trang %s (job %s)%s", batch_run_id, buoc, page_id, job_id,
                f", chờ {cho_giay:.1f}s" if cho_giay else "")
    return job_id


def viec_dang_song() -> set[str] | None:
    """Hỏi BROKER xem những job nào đang thật sự chạy. `None` = không hỏi được.

    Vì sao cần: worker bị giết giữa chừng thì `Job` và `BatchItem` nằm lại ở `running` **vĩnh
    viễn** — không ai ghi lại trạng thái cuối cho chúng. Nếu chỉ dựa vào đồng hồ để đoán (mục
    `running` quá N phút thì coi là mồ côi) thì người vận hành bấm "chạy lại" ngay sau sự cố sẽ
    **không thấy gì xảy ra**, mẻ đứng im tới khi hết N phút. Đo thật ở Run E: `resumed_count=0`
    và mẻ treo ở 2/3. Hỏi thẳng broker cho câu trả lời đúng ngay lập tức.
    """
    try:
        from app.workers.celery_app import celery_app

        dang_chay = celery_app.control.inspect(timeout=2.0).active()
    except Exception as exc:  # noqa: BLE001
        logger.warning("không hỏi được broker về việc đang chạy: %s", exc)
        return None
    if dang_chay is None:
        # Không worker nào trả lời: hoặc không có worker nào, hoặc broker đang trục trặc.
        return None
    ket = set()
    for viec_cua_worker in dang_chay.values():
        for v in viec_cua_worker or []:
            tham_so = v.get("args") or []
            if tham_so:
                ket.add(str(tham_so[0]))
    return ket
