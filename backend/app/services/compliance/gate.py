"""Cổng khai báo mục đích & cảnh báo trước khi mang file đi (M10).

Nguyên tắc: **cảnh báo, không chặn**. Đây là công cụ cá nhân, không phải hệ thống kiểm duyệt —
chặn cứng chỉ khiến người dùng đi đường vòng. Nhưng cũng **không im lặng bỏ qua**: người dùng
phải nhìn thấy đúng số vùng còn lỗi và tự tick xác nhận, và việc đó được ghi lại.

Cũng **không** watermark/DRM: nó không giúp gì cho việc tuân thủ bản quyền thật, chỉ làm hỏng ảnh
của chính người dùng.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ExportComplianceLog,
    GlossaryEntry,
    OCRResult,
    Page,
    TextRegion,
    TypesetResult,
)
from app.models.enums import (
    FitStatus,
    GlossaryStatus,
    IntendedUse,
    OCRStatus,
    PageStatus,
)


@dataclass(frozen=True)
class ExportWarnings:
    """Những gì người dùng PHẢI nhìn thấy trước khi mang file đi."""

    overflow_warning_count: int
    needs_manual_count: int
    #: Đã từng xác nhận cho chapter này chưa — để cảnh báo chỉ hiện **một lần**, không lải nhải.
    acknowledged: bool
    acknowledged_at: datetime | None
    #: E13 — số thuật ngữ ĐÃ DUYỆT. 0 là cảnh báo thật: chưa chốt thuật ngữ thì tên riêng bị
    #: dịch nghĩa đen ("Pepper" -> "Hạt tiêu", đo được ở pilot 03/09).
    glossary_approved_count: int = 0


#: Trang đã chèn chữ xong — chỉ những trang này mới được xuất, nên cũng chỉ đếm cảnh báo ở đây.
#: Vùng lỗi trên trang KHÔNG được xuất thì không nằm trong file giao đi, đếm vào chỉ gây hoang mang.
TRANG_SE_XUAT = (PageStatus.typeset_done, PageStatus.ready_for_export)


class ComplianceGate:
    @staticmethod
    def validate_intended_use(intended_use: str | None) -> IntendedUse:
        """Chỉ nhận đúng giá trị trong enum. Thiếu ⇒ lỗi, **không** tự điền `personal`.

        Tự điền hộ là suy đoán mục đích sử dụng thay người dùng — đúng thứ mà khai báo này sinh ra
        để tránh.
        """
        if intended_use is None or intended_use == "":
            raise ValueError("intended_use_required: phải tự khai mục đích sử dụng")
        try:
            return IntendedUse(intended_use)
        except ValueError as exc:
            hop_le = ", ".join(e.value for e in IntendedUse)
            raise ValueError(f"intended_use_invalid: chỉ nhận {hop_le}") from exc

    async def get_export_warnings(
        self, session: AsyncSession, project_id: uuid.UUID
    ) -> ExportWarnings:
        """Đếm vùng còn tràn khung và vùng chưa đọc được chữ, trên các trang **sẽ được xuất**."""
        trang = list(
            (await session.execute(
                select(Page.id).where(
                    Page.project_id == project_id, Page.status.in_(TRANG_SE_XUAT)
                )
            )).scalars()
        )

        so_tran = so_can_doc_lai = 0
        if trang:
            so_tran = (await session.execute(
                select(func.count()).select_from(TypesetResult)
                .join(TextRegion, TextRegion.id == TypesetResult.region_id)
                .where(TextRegion.page_id.in_(trang),
                       TypesetResult.fit_status == FitStatus.overflow_warning)
            )).scalar() or 0
            so_can_doc_lai = (await session.execute(
                select(func.count()).select_from(OCRResult)
                .join(TextRegion, TextRegion.id == OCRResult.region_id)
                .where(TextRegion.page_id.in_(trang),
                       OCRResult.status == OCRStatus.needs_manual)
            )).scalar() or 0

        # E13 — đếm thuật ngữ ĐÃ DUYỆT (chỉ mục đã duyệt mới được dùng khi rà soát).
        so_thuat_ngu = (await session.execute(
            select(func.count()).select_from(GlossaryEntry).where(
                GlossaryEntry.project_id == project_id,
                GlossaryEntry.status == GlossaryStatus.approved,
            )
        )).scalar() or 0

        gan_nhat = (await session.execute(
            select(ExportComplianceLog)
            .where(ExportComplianceLog.project_id == project_id,
                   ExportComplianceLog.user_acknowledged.is_(True))
            .order_by(ExportComplianceLog.acknowledged_at.desc())
            .limit(1)
        )).scalars().first()

        return ExportWarnings(
            overflow_warning_count=int(so_tran),
            needs_manual_count=int(so_can_doc_lai),
            acknowledged=gan_nhat is not None,
            acknowledged_at=gan_nhat.acknowledged_at if gan_nhat else None,
            glossary_approved_count=int(so_thuat_ngu),
        )

    async def log_export_acknowledgement(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        export_job_id: uuid.UUID | None,
        intended_use: IntendedUse,
        overflow_warning_count: int,
        needs_manual_count: int,
        user_acknowledged: bool,
    ) -> ExportComplianceLog:
        """Ghi lại **đúng những con số người dùng đã nhìn thấy** lúc bấm xác nhận.

        Không ghi tên file, không ghi nội dung, không ghi bản dịch — chỉ số liệu và thời điểm.
        """
        ban_ghi = ExportComplianceLog(
            project_id=project_id,
            export_job_id=export_job_id,
            intended_use=intended_use,
            overflow_warning_count=overflow_warning_count,
            needs_manual_count=needs_manual_count,
            user_acknowledged=user_acknowledged,
            # Chưa tick thì KHÔNG có mốc xác nhận — để trống chứ không điền giờ hiện tại cho đẹp.
            acknowledged_at=datetime.now(timezone.utc) if user_acknowledged else None,
        )
        session.add(ban_ghi)
        await session.commit()
        await session.refresh(ban_ghi)
        return ban_ghi
