"""P3j — dọn job MỒ CÔI khi worker khởi động lại.

Sinh ra từ một sự cố có thật trong pilot hosted 03/09: worker bị OOM killer giết giữa lúc chạy
`inpaint`, và trang đó **kẹt vĩnh viễn** — job biến mất không dấu vết, không tự chạy lại, và
người vận hành nhìn từ giao diện chỉ thấy "5/6 trang" mà không có cách nào biết vì sao.

## Vì sao dám kết luận "mọi job `running` lúc khởi động đều là mồ côi"

Vì topology hiện tại có **đúng một** worker: `deploy-start.sh` chạy celery với `--pool=solo`
(một tiến trình, không fork) trong **một** container. Nên tiến trình duy nhất có thể đang giữ một
job `running` chính là tiến trình vừa chết. Không có worker thứ hai nào để mà giết nhầm.

⚠️ **Ràng buộc này là điều kiện đúng đắn của cả tệp.** Ngày nào chạy nhiều worker, quét kiểu này
sẽ giết job đang chạy hợp lệ của worker khác. Khi đó phải đổi sang cơ chế "job có chủ" (ghi id
worker + nhịp tim) — và tắt `worker_sweep_orphan_jobs_on_start` trước đã.

## Không tự chạy lại

Chỉ **đánh dấu hỏng kèm lý do đọc được** rồi trả quyền quyết định cho người dùng. Tự chạy lại một
job vừa làm chết worker vì hết bộ nhớ là cách nhanh nhất để giết nó lần nữa — và lần này thành
vòng lặp.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BatchItem, Job, Page
from app.models.enums import BatchItemStatus, JobStatus, PageStatus
from app.workers.trang_thai_worker import doc_va_phan_loai

logger = logging.getLogger(__name__)

#: Lý do ghi vào `job.error_log`. Cố ý viết cho NGƯỜI đọc, không phải cho máy grep: đây là dòng
#: chữ người vận hành sẽ thấy khi hỏi "vì sao trang này đứng im".
LY_DO = (
    "worker_died: tiến trình xử lý bị dừng giữa chừng nên việc này không chạy xong "
    "(hay gặp nhất là container hết bộ nhớ). Dữ liệu của bạn KHÔNG mất — bấm chạy lại bước này "
    "hoặc 'Chạy cả chapter' là tiếp tục được."
)

#: Trạng thái page chỉ tồn tại TRONG LÚC một bước đang chạy. Job chết giữa chừng thì trang mắc
#: kẹt ở đây mãi, nên phải lùi về mốc trước đó. Các trạng thái khác đều chỉ được đặt KHI XONG,
#: nên chúng vẫn trung thực dù job chết — không được đụng vào.
LUI_VE = {
    PageStatus.detecting: PageStatus.queued,
}


@dataclass
class KetQuaDon:
    job_da_danh_dau: int = 0
    trang_da_lui: int = 0
    #: E23 — mục mẻ trỏ vào job mồ côi, phải đánh hỏng nếu không mẻ đứng im 40 phút.
    muc_me_da_danh_dau: int = 0
    chi_tiet: list[str] = field(default_factory=list)

    @property
    def tong(self) -> int:
        return self.job_da_danh_dau + self.trang_da_lui + self.muc_me_da_danh_dau


def don_job_mo_coi(session: Session, *, ap_dung: bool = True) -> KetQuaDon:
    """Đánh dấu mọi job đang `running` là hỏng, và lùi trạng thái trang bị kẹt.

    `ap_dung=False` chỉ đếm, không ghi — để soi trước khi động vào dữ liệu.
    Idempotent: chạy lần hai không còn gì để dọn.
    """
    kq = KetQuaDon()

    mo_coi = list(session.scalars(select(Job).where(Job.status == JobStatus.running)))
    # E22 (thu hẹp) — phân loại MỘT LẦN cho cả lượt quét: mọi job mồ côi tìm thấy trong CÙNG một
    # lần khởi động lại đều do CÙNG một lần worker chết gây ra (đúng 1 worker tại 1 thời điểm),
    # nên dùng chung 1 bằng chứng mã thoát là đủ — không cần đọc lại tệp cho từng job.
    loi_class, loi_tin_hieu = doc_va_phan_loai() if (ap_dung and mo_coi) else (None, None)
    for job in mo_coi:
        kq.job_da_danh_dau += 1
        kq.chi_tiet.append(f"job {job.id} ({job.type.value}) trang {job.page_id}: running -> failed")
        if ap_dung:
            job.status = JobStatus.failed
            job.error_log = LY_DO[:4000]
            job.error_class = loi_class
            job.exit_signal = loi_tin_hieu

    # E23 — mục MẺ trỏ tới job vừa bị đánh hỏng cũng phải nói thật, nếu không mẻ ĐỨNG IM.
    #
    # Đo thật (lượt 24 trang, 2026-09-10): sau khi worker bị giết và bật lại, job được đánh
    # `failed` đúng nhưng `BatchItem` vẫn `running` và trỏ vào đúng job đó. Mẻ chờ một job đã chết
    # ⇒ không job nào trong hàng đợi, 4 mục `pending` không bao giờ tới lượt vì chỗ chạy bị mục
    # `running` kia giữ. Mẻ chỉ tự lành sau `batch_stale_item_seconds` = 2400s (40 PHÚT).
    #
    # Đánh `failed` chứ KHÔNG đưa về `pending`: `pending` nghĩa là mẻ tự xếp lại ngay, mà đó đúng
    # là điều mục "Không tự chạy lại" ở đầu tệp này cấm — xếp lại một job vừa làm chết worker vì
    # hết bộ nhớ là cách nhanh nhất để giết nó lần nữa, thành vòng lặp. `failed` giải phóng chỗ
    # chạy cho các trang còn lại VÀ giữ quyền quyết định chạy lại cho người dùng.
    # Điều kiện là "mục `running` mà job của nó ĐÃ tới trạng thái cuối" — KHÔNG phải "job vừa bị
    # đánh mồ côi trong lượt này". Bản đầu của tôi lọc theo danh sách job vừa quét, và vì thế
    # KHÔNG sửa được mục đã kẹt từ một lượt quét TRƯỚC (job của nó lúc đó đã thành `failed`, nên
    # không còn nằm trong danh sách). Đúng cảnh đang có trên bàn thử E23.
    #
    # `job.status` tới trạng thái cuối mà mục vẫn `running` thì mục đó **định nghĩa là** cũ: quét
    # chỉ chạy lúc worker khởi động, khi không task nào đang chạy, nên không có cửa sổ "job vừa
    # xong mà `on_page_terminal` chưa kịp chạy" để giết oan.
    id_mo_coi = [j.id for j in mo_coi]
    dieu_kien_job = Job.status.in_((JobStatus.done, JobStatus.failed))
    if id_mo_coi:
        # Ở chế độ chỉ-đếm, job mồ côi chưa bị ghi `failed` nên phải kể tên chúng ra tường minh,
        # nếu không báo cáo chỉ-đếm sẽ nói ít hơn thực tế chế độ sửa sẽ làm.
        dieu_kien_job = dieu_kien_job | Job.id.in_(id_mo_coi)
    for muc in session.scalars(
        select(BatchItem)
        .join(Job, Job.id == BatchItem.current_job_id)
        .where(BatchItem.status == BatchItemStatus.running, dieu_kien_job)
    ):
        kq.muc_me_da_danh_dau += 1
        kq.chi_tiet.append(f"mục mẻ {muc.id} trang {muc.page_id}: running -> failed")
        if ap_dung:
            muc.status = BatchItemStatus.failed
            # Dùng ĐÚNG phân loại đã gắn cho job ở trên, để hai tầng nói cùng một thứ thay vì
            # mỗi tầng một chữ. Không có bằng chứng mã thoát thì là `worker_lost`.
            # Cố ý KHÔNG dùng mã trong `MA_TAM_THOI`: mã tạm thời sẽ bật đường tự thử lại.
            muc.error_code = loi_class or "worker_lost"
            muc.error_message = LY_DO[:1000]
            muc.finished_at = datetime.now(timezone.utc)

    # Lùi trang khỏi trạng thái tạm. Làm RIÊNG khỏi vòng trên: một trang có thể không có job
    # `running` nào mà vẫn kẹt (worker chết trước khi kịp ghi job), nên quét theo trang mới đủ.
    for page in session.scalars(select(Page).where(Page.status.in_(tuple(LUI_VE)))):
        moi = LUI_VE[page.status]
        kq.trang_da_lui += 1
        kq.chi_tiet.append(f"page {page.id}: {page.status.value} -> {moi.value}")
        if ap_dung:
            page.status = moi

    if ap_dung and kq.tong:
        session.commit()

    if kq.tong:
        logger.warning(
            "dọn job mồ côi (%s): %d job -> failed, %d trang lùi khỏi trạng thái tạm, "
            "%d mục mẻ -> failed",
            "ĐÃ SỬA" if ap_dung else "chỉ đếm", kq.job_da_danh_dau, kq.trang_da_lui,
            kq.muc_me_da_danh_dau,
        )
        for d in kq.chi_tiet:
            logger.warning("  %s", d)
    else:
        logger.info("dọn job mồ côi: không có gì để dọn")
    return kq
