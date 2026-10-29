"""Áp dụng một việc rà soát đã được NGƯỜI duyệt (E13).

Ba điều tuyệt đối:
- Chỉ đụng vào **một** `TranslationResult` của đúng vùng đó.
- Chữ gốc OCR (M3) và ảnh (M4/M6) không bao giờ bị sửa.
- Bản dịch đã đổi kể từ lúc tạo việc ⇒ **từ chối**, không áp đè.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ConsistencyReviewTask, Job, TextRegion, TranslationResult
from app.models.enums import ConsistencyTaskStatus, JobStatus, JobType
from app.services.consistency.matching import chuan_hoa
from app.services.consistency.scanner import bam_ban_dich

logger = logging.getLogger(__name__)


class TaskNotFound(LookupError):
    pass


class TaskStale(RuntimeError):
    """Bản dịch đã đổi kể từ lần quét — đề xuất cũ không còn dùng được."""


class TaskInvalid(ValueError):
    pass


@dataclass
class ApplyResult:
    task_id: uuid.UUID
    region_id: uuid.UUID
    page_id: uuid.UUID
    refit_job_id: uuid.UUID | None
    applied_text: str


class ConsistencyApplyService:
    def __init__(self, session: Session, dispatcher=None) -> None:
        self.session = session
        #: Tách ra để test không cần Celery/Redis.
        self._dispatcher = dispatcher

    def _lay_viec(self, task_id: uuid.UUID) -> ConsistencyReviewTask:
        viec = self.session.get(ConsistencyReviewTask, task_id)
        if viec is None:
            raise TaskNotFound(f"task_not_found: {task_id}")
        return viec

    def accept_task(self, task_id: uuid.UUID, edited_text: str | None = None) -> ApplyResult:
        """Áp bản đề xuất (hoặc bản người dùng tự sửa) vào đúng một vùng."""
        viec = self._lay_viec(task_id)
        if viec.status is not ConsistencyTaskStatus.open:
            raise TaskInvalid(
                f"task_not_open: việc đang ở '{viec.status.value}', chỉ áp được việc đang mở"
            )

        dich = self.session.execute(
            select(TranslationResult).where(TranslationResult.region_id == viec.region_id)
        ).scalars().first()
        if dich is None:
            raise TaskInvalid("missing_translation: vùng này không còn bản dịch")

        # Chốt chặn quan trọng nhất: bản dịch phải y hệt lúc tạo việc.
        if bam_ban_dich(dich.translated_text) != viec.snapshot_hash:
            viec.status = ConsistencyTaskStatus.stale
            self.session.commit()
            raise TaskStale(
                "task_stale: bản dịch đã thay đổi kể từ lần quét. Hãy quét lại rồi xem lại đề xuất "
                "— áp bản cũ sẽ ghi đè mất phần vừa sửa."
            )

        chu_moi = chuan_hoa(edited_text if edited_text is not None else (viec.proposed_text or ""))
        if not chu_moi.strip():
            raise TaskInvalid(
                "empty_text: việc này không có sẵn bản đề xuất, bạn phải tự nhập bản dịch mới"
            )

        region = self.session.get(TextRegion, viec.region_id)
        dich.translated_text = chu_moi
        # Đánh dấu người sửa — để về sau phân biệt được với bản máy dịch.
        dich.edited_by_user = True

        viec.status = ConsistencyTaskStatus.accepted
        viec.resolved_at = datetime.now(timezone.utc)

        # Mọi việc khác đang mở trên CÙNG vùng đều dựa trên bản dịch cũ ⇒ thành cũ.
        for khac in self.session.execute(
            select(ConsistencyReviewTask).where(
                ConsistencyReviewTask.region_id == viec.region_id,
                ConsistencyReviewTask.status == ConsistencyTaskStatus.open,
                ConsistencyReviewTask.id != viec.id,
            )
        ).scalars():
            khac.status = ConsistencyTaskStatus.stale

        job = Job(type=JobType.typeset, page_id=region.page_id, status=JobStatus.queued)
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)

        # Canh lại ĐÚNG vùng đó qua đường của M7 — không chạy lại cả trang, không dịch lại.
        # Cỡ chữ ghim của M7 giữ nguyên: không truyền font_size nghĩa là dùng lại thiết lập
        # đang có của vùng, chữ mới không vừa thì báo tràn chứ không tự bỏ ghim.
        if self._dispatcher is None:
            from app.services.dispatch import dispatch_refit_job

            self._dispatcher = dispatch_refit_job
        sent, ly_do = self._dispatcher(job.id, viec.region_id, None)
        if not sent:
            job.error_log = ly_do
            self.session.commit()

        logger.info("E13: áp việc %s cho vùng %s, canh lại job %s", task_id, viec.region_id, job.id)
        return ApplyResult(
            task_id=viec.id, region_id=viec.region_id, page_id=region.page_id,
            refit_job_id=job.id, applied_text=chu_moi,
        )

    def reject_task(self, task_id: uuid.UUID, resolution: str) -> ConsistencyReviewTask:
        """Từ chối — KHÔNG đụng vào bản dịch, ảnh hay bố cục."""
        viec = self._lay_viec(task_id)
        if viec.status is not ConsistencyTaskStatus.open:
            raise TaskInvalid(f"task_not_open: việc đang ở '{viec.status.value}'")
        if resolution not in ("keep_current", "not_applicable"):
            raise TaskInvalid(
                f"invalid_resolution: '{resolution}' (chỉ keep_current | not_applicable)"
            )
        viec.status = (
            ConsistencyTaskStatus.resolved_no_change
            if resolution == "keep_current"
            else ConsistencyTaskStatus.rejected
        )
        viec.resolved_at = datetime.now(timezone.utc)
        self.session.commit()
        self.session.refresh(viec)
        return viec
