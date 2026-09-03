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

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Job, Page
from app.models.enums import JobStatus, PageStatus

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
    chi_tiet: list[str] = field(default_factory=list)

    @property
    def tong(self) -> int:
        return self.job_da_danh_dau + self.trang_da_lui


def don_job_mo_coi(session: Session, *, ap_dung: bool = True) -> KetQuaDon:
    """Đánh dấu mọi job đang `running` là hỏng, và lùi trạng thái trang bị kẹt.

    `ap_dung=False` chỉ đếm, không ghi — để soi trước khi động vào dữ liệu.
    Idempotent: chạy lần hai không còn gì để dọn.
    """
    kq = KetQuaDon()

    mo_coi = list(session.scalars(select(Job).where(Job.status == JobStatus.running)))
    for job in mo_coi:
        kq.job_da_danh_dau += 1
        kq.chi_tiet.append(f"job {job.id} ({job.type.value}) trang {job.page_id}: running -> failed")
        if ap_dung:
            job.status = JobStatus.failed
            job.error_log = LY_DO[:4000]

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
            "dọn job mồ côi (%s): %d job -> failed, %d trang lùi khỏi trạng thái tạm",
            "ĐÃ SỬA" if ap_dung else "chỉ đếm", kq.job_da_danh_dau, kq.trang_da_lui,
        )
        for d in kq.chi_tiet:
            logger.warning("  %s", d)
    else:
        logger.info("dọn job mồ côi: không có gì để dọn")
    return kq
