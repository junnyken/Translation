"""Quét nhất quán theo LUẬT TẤT ĐỊNH (E13).

Bộ này **không gọi LLM** và **không sửa gì cả**. Nó chỉ tạo ra các việc cần người rà soát, mỗi
việc kèm bằng chứng cụ thể: thuật ngữ nào đã duyệt, khớp ở đoạn nào của chữ gốc, bản dịch hiện
tại đang dùng gì.

Vì sao tất định chứ không nhờ máy phán: luật kiểu này rẻ, chạy lại ra đúng kết quả cũ, giải
thích được cho người dùng, và **không giả vờ đo được đúng-sai về nghĩa**. Máy không biết câu nào
dịch hay hơn; nó chỉ biết "thuật ngữ đã chốt là X mà chỗ này không có X".
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ConsistencyReviewTask,
    GlossaryEntry,
    OCRResult,
    Page,
    RegionQualityAssessment,
    TextRegion,
    TranslationResult,
)
from app.models.enums import (
    ConsistencyTaskStatus,
    ConsistencyTaskType,
    OCRStatus,
    ReviewStatus,
)
from app.services.consistency.glossary import GlossaryService, VoiceProfileService
from app.services.consistency.matching import (
    chua_thuat_ngu_dich,
    chuan_hoa,
    khop_uu_tien_dai_truoc,
    tim_khop,
)

logger = logging.getLogger(__name__)


def bam_ban_dich(text: str | None) -> str:
    """Vân tay của bản dịch tại thời điểm tạo việc.

    Dùng bản đã chuẩn hoá NFC để cùng một nội dung không ra hai vân tay khác nhau chỉ vì cách
    mã hoá dấu.
    """
    return hashlib.sha256(chuan_hoa(text or "").encode()).hexdigest()


@dataclass
class ScanSummary:
    version: str
    so_vung_xet: int = 0
    so_vung_bo_qua: int = 0
    tao_moi: int = 0
    giu_nguyen: int = 0
    danh_dau_cu: int = 0
    theo_loai: dict = field(default_factory=dict)


class ConsistencyScanner:
    VERSION = "e13-rules-v1"

    def __init__(self, session: Session) -> None:
        self.session = session

    # ---------------- chọn vùng đủ điều kiện ----------------
    def _vung_du_dieu_kien(self, project_id: uuid.UUID):
        """Lấy vùng theo thứ tự đọc, KÈM chữ gốc và bản dịch.

        Loại bỏ vùng người dùng đã bấm "bỏ qua" ở E12: họ đã xem và quyết định rồi, dựng lại
        việc cho vùng đó là phớt lờ quyết định của người dùng.
        """
        return list(
            self.session.execute(
                select(TextRegion, OCRResult, TranslationResult, RegionQualityAssessment)
                .join(Page, Page.id == TextRegion.page_id)
                .outerjoin(OCRResult, OCRResult.region_id == TextRegion.id)
                .outerjoin(TranslationResult, TranslationResult.region_id == TextRegion.id)
                .outerjoin(
                    RegionQualityAssessment,
                    RegionQualityAssessment.region_id == TextRegion.id,
                )
                .where(Page.project_id == project_id)
                .order_by(Page.order, TextRegion.reading_order.nulls_last(), TextRegion.created_at)
            ).all()
        )

    # ---------------- quét ----------------
    def scan_project(self, project_id: uuid.UUID) -> ScanSummary:
        tom_tat = ScanSummary(version=self.VERSION)
        thuat_ngu = GlossaryService(self.session).list_approved(project_id)
        if not thuat_ngu:
            logger.info("project %s chưa có thuật ngữ nào đã duyệt — không quét", project_id)
            return tom_tat

        hang = self._vung_du_dieu_kien(project_id)
        can_giu: set[tuple] = set()

        for region, ocr, dich, danh_gia in hang:
            if danh_gia is not None and danh_gia.review_status is ReviewStatus.reviewed_skip:
                tom_tat.so_vung_bo_qua += 1
                continue

            chu_goc = (ocr.raw_text or "") if ocr else ""
            ocr_hong = ocr is None or ocr.status is OCRStatus.needs_manual or not chu_goc.strip()
            ban_dich = (dich.translated_text or "") if dich else ""

            # Không có chữ gốc thì KHÔNG được kết luận thuật ngữ có xuất hiện hay không.
            # Đoán từ bản dịch là bịa bằng chứng — chất lượng vùng đó là việc của E12.
            if ocr_hong or not ban_dich.strip():
                tom_tat.so_vung_bo_qua += 1
                continue

            tom_tat.so_vung_xet += 1
            vet = bam_ban_dich(ban_dich)

            khop = khop_uu_tien_dai_truoc(
                chu_goc,
                [(str(e.id), e.source_term) for e in thuat_ngu],
                region_lang := thuat_ngu[0].source_lang.value,
            )

            for entry in thuat_ngu:
                doan_khop = khop.get(str(entry.id))

                # Luật 1: chữ gốc có thuật ngữ, bản dịch KHÔNG có từ đã chốt.
                if doan_khop and not chua_thuat_ngu_dich(ban_dich, entry.target_term):
                    khoa = self._ghi_viec(
                        project_id, region, entry, None,
                        ConsistencyTaskType.glossary_missing, ban_dich, vet,
                        de_xuat=None,
                        bang_chung={
                            "thuat_ngu_nguon": entry.source_term,
                            "thuat_ngu_da_duyet": entry.target_term,
                            "loai": entry.term_type.value,
                            "dinh_nghia": entry.definition,
                            "doan_khop": [d.span for d in doan_khop],
                            "doan_khop_chu": [d.doan for d in doan_khop],
                            "ban_dich_hien_tai": ban_dich,
                            "ly_do": (
                                f"Chữ gốc có “{entry.source_term}” — thuật ngữ này đã được chốt "
                                f"là “{entry.target_term}”, nhưng bản dịch hiện tại chưa dùng."
                            ),
                        },
                        tom_tat=tom_tat,
                    )
                    can_giu.add(khoa)

                # Luật 2: bản dịch dùng đúng biến thể mà NGƯỜI DÙNG đã khai là cấm.
                # Chỉ xét biến thể do người dùng tự khai — máy không tự nghĩ ra từ đồng nghĩa.
                for cam in entry.prohibited_variants or []:
                    if not chua_thuat_ngu_dich(ban_dich, cam):
                        continue
                    khoa = self._ghi_viec(
                        project_id, region, entry, None,
                        ConsistencyTaskType.prohibited_variant, ban_dich, vet,
                        de_xuat=None,
                        bang_chung={
                            "thuat_ngu_da_duyet": entry.target_term,
                            "bien_the_bi_cam": cam,
                            "dinh_nghia": entry.definition,
                            "ban_dich_hien_tai": ban_dich,
                            "ly_do": (
                                f"Bản dịch đang dùng “{cam}” — bạn đã ghi đây là cách dịch không "
                                f"dùng cho thuật ngữ “{entry.target_term}”."
                            ),
                        },
                        tom_tat=tom_tat,
                    )
                    can_giu.add(khoa)

        tom_tat.danh_dau_cu = self._danh_dau_viec_cu(project_id, can_giu)
        self.session.commit()
        return tom_tat

    # ---------------- ghi việc (idempotent) ----------------
    def _ghi_viec(
        self, project_id, region, entry, voice, loai, ban_dich, vet, de_xuat, bang_chung, tom_tat
    ) -> tuple:
        khoa = (region.id, loai, entry.id if entry else None, voice.id if voice else None, vet)
        cu = self.session.execute(
            select(ConsistencyReviewTask).where(
                ConsistencyReviewTask.region_id == region.id,
                ConsistencyReviewTask.task_type == loai,
                ConsistencyReviewTask.glossary_entry_id == (entry.id if entry else None),
                ConsistencyReviewTask.voice_profile_id == (voice.id if voice else None),
                ConsistencyReviewTask.snapshot_hash == vet,
            )
        ).scalars().first()

        if cu is not None:
            # Quét lại với cùng dữ liệu ⇒ giữ nguyên việc cũ. Người dùng đã xử lý (chấp nhận/từ
            # chối) thì TUYỆT ĐỐI không mở lại — ghi đè quyết định của người là điều cấm.
            tom_tat.giu_nguyen += 1
            return khoa

        viec = ConsistencyReviewTask(
            project_id=project_id,
            region_id=region.id,
            glossary_entry_id=entry.id if entry else None,
            voice_profile_id=voice.id if voice else None,
            task_type=loai,
            status=ConsistencyTaskStatus.open,
            current_text_snapshot=ban_dich,
            snapshot_hash=vet,
            proposed_text=de_xuat,
            evidence=bang_chung,
        )
        self.session.add(viec)
        self.session.flush()
        tom_tat.tao_moi += 1
        tom_tat.theo_loai[loai.value] = tom_tat.theo_loai.get(loai.value, 0) + 1
        return khoa

    def _danh_dau_viec_cu(self, project_id: uuid.UUID, can_giu: set[tuple]) -> int:
        """Việc `open` dựa trên bản dịch đã thay đổi ⇒ chuyển `stale`.

        Không xoá và không tự cập nhật đề xuất: đề xuất cũ được tính trên một bản dịch không còn
        tồn tại, áp vào là ghi đè mất phần người khác vừa sửa.
        """
        dem = 0
        for viec in self.session.execute(
            select(ConsistencyReviewTask).where(
                ConsistencyReviewTask.project_id == project_id,
                ConsistencyReviewTask.status == ConsistencyTaskStatus.open,
            )
        ).scalars():
            khoa = (
                viec.region_id, viec.task_type, viec.glossary_entry_id,
                viec.voice_profile_id, viec.snapshot_hash,
            )
            if khoa in can_giu:
                continue
            viec.status = ConsistencyTaskStatus.stale
            dem += 1
        return dem
