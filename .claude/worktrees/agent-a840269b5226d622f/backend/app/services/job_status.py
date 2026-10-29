"""E22 (thu hẹp theo audit) — suy ra trạng thái hiển thị TRUNG THỰC cho một `Job` đang `running`.

KHÔNG đổi `Job.status` trong DB — đó vẫn là việc riêng của `app/workers/hoi_phuc.py` lúc worker
khởi động lại. Đây chỉ là suy luận LÚC ĐỌC (API `GET /jobs/{id}`): nếu một job đứng `running`
lâu hơn hẳn trần thời gian thật của chính loại việc đó (`*_timeout_seconds` — cũng là
`soft_time_limit` Celery đang dùng), gần như chắc chắn worker đã chết nhưng CHƯA tới lượt quét mồ
côi (worker restart theo chu kỳ ~10s của `deploy-start.sh`, cộng thời gian Celery kết nối lại).
Không suy luận gì thêm cho các trạng thái khác — chúng chỉ được ghi KHI XONG nên đã trung thực sẵn
(nguyên tắc gốc của `hoi_phuc.py`).
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import get_settings
from app.models.enums import JobStatus, JobType

#: Cộng thêm ngoài soft_time_limit — không phải số đoán: bằng đúng 2 lần chu kỳ restart
#: (`sleep 10` trong `deploy-start.sh`) cộng thời gian Celery/Redis kết nối lại quan sát được
#: trong log thật (~13s, xem `docs/REPORT_E22.md` §Audit). Làm tròn lên 20s cho an toàn.
_BUFFER_SECONDS = 20

#: Tên field settings tương ứng từng loại job — dùng đúng số đã cấu hình, không bịa ngưỡng riêng.
_TIMEOUT_ATTR: dict[JobType, str] = {
    JobType.detect: "detect_timeout_seconds",
    JobType.ocr: "ocr_timeout_seconds",
    JobType.inpaint: "inpaint_timeout_seconds",
    JobType.translate: "translate_timeout_seconds",
    JobType.typeset: "typeset_timeout_seconds",
    JobType.export: "export_timeout_seconds",
}

#: Nếu loại job không có trong bảng trên (vd job phụ trợ khác) — dùng trần rộng nhất đã biết thay
#: vì đoán bừa; rộng hơn thì thà báo trễ còn hơn báo nhầm "gián đoạn" cho việc vẫn đang chạy tốt.
_TIMEOUT_MAC_DINH = 900


def nguong_qua_han_giay(loai: JobType) -> int:
    settings = get_settings()
    attr = _TIMEOUT_ATTR.get(loai)
    timeout = getattr(settings, attr, None) if attr else None
    return (timeout if timeout is not None else _TIMEOUT_MAC_DINH) + _BUFFER_SECONDS


#: `queued`/`done`/`failed` giữ nguyên nhãn cũ — chỉ `running` có thể suy ra thêm.
TRANG_THAI_WORKER_GIAN_DOAN = "worker_interrupted"


def suy_ra_trang_thai_hien_thi(
    *,
    status: JobStatus,
    loai: JobType,
    heartbeat_at: datetime | None,
    started_at: datetime | None,
    bay_gio: datetime | None = None,
) -> str:
    """Trả về 1 trong: `queued` | `running` | `worker_interrupted` | `done` | `failed`.

    Nhận giá trị thô (không phải đối tượng `Job`) CỐ Ý — hàm này được gọi lại từ
    `JobRead` (tầng schema, `app/schemas/common.py`) qua `model_validator`, và tầng schema không
    nên phụ thuộc ngược vào tầng ORM chỉ để đọc vài trường vô hướng.
    """
    if status != JobStatus.running:
        return status.value
    if heartbeat_at is None or started_at is None:
        # Job tạo trước E22 (chưa từng có heartbeat) — không đủ bằng chứng để nói khác đi.
        return JobStatus.running.value
    now = bay_gio or datetime.now(timezone.utc)
    if (now - heartbeat_at).total_seconds() > nguong_qua_han_giay(loai):
        return TRANG_THAI_WORKER_GIAN_DOAN
    return JobStatus.running.value


def job_chua_ket_thuc(session, page_id, loai: JobType, bay_gio: datetime | None = None):
    """E42 — job CÙNG LOẠI cho CÙNG TRANG còn đang sống. Trả `Job` hoặc `None`.

    ## Vì sao cần

    `PageStatus` chỉ có **một** trạng thái đang-chạy (`detecting`), nên `buoc_cho_trang` không
    phân biệt được "bước kế tiếp đã được đẩy rồi" với "chưa đẩy". Hậu quả đo được:

        OCR xong -> Page.status = ocr_done, commit
          auto-chain đẩy inpaint                       tasks.py
          mẻ tick, đọc thấy ocr_done -> đẩy inpaint    orchestrator.py
          status VẪN ocr_done tới khi inpaint XONG -> mọi tick đẩy thêm một cái

    Số đo trên 38 trang (DB dev) — và **xếp hạng chính là bằng chứng cho nguyên nhân**:

        typeset 2,92 · translate 1,68 · inpaint 1,42 · ocr 1,13 · detect 1,11 job/trang
                                                                  ^^^^^^^^^^
                                     detect là bước DUY NHẤT có trạng thái đang-chạy, và nó
                                     trùng ÍT NHẤT.

    Production (E35, trang `a744aede`): translate 2 job, token 935 + **959 lãng phí**; typeset
    4 job, mỗi lần "xoá 21 kết quả cũ" rồi ghi lại y hệt; inpaint 2 job.

    ## Ngưỡng mồ côi: KHÔNG bịa số mới

    Dùng đúng `nguong_qua_han_giay(loai)` mà E22 đã suy ra từ `*_timeout_seconds` đã cấu hình.
    Một job `running` quá ngưỡng đó thì gần như chắc chắn worker đã chết mà chưa tới lượt quét mồ
    côi — lúc đó **phải cho đẩy lại**, nếu không một lần worker chết sẽ chặn trang đó vĩnh viễn.

    Lưu ý về `heartbeat_at`: nó **không phải nhịp tim định kỳ**, chỉ được ghi MỘT LẦN lúc job bắt
    đầu (`danh_dau_dang_chay`). Nên nó tương đương `started_at`, và phép nhận mồ côi ở đây dựa
    vào NGƯỠNG THỜI GIAN theo loại job, không dựa vào "nhịp tim còn mới".

    ## Chỉ dùng ở các đường TỰ ĐỘNG

    KHÔNG phải luật toàn cục. Có 22 chỗ tạo `Job`, trong đó nhiều chỗ theo **vùng**
    (`page_id=region.page_id`) — `enqueue_refit_after_retranslate` tạo một job `typeset` cho MỖI
    vùng và đó là đúng thiết kế (dịch lại 16 vùng ⇒ 16 job). Chắn theo (trang, loại) ở những chỗ
    đó sẽ chặn oan. Và 15 đường trong `routes.py` là do người dùng bấm — bấm "chạy lại" mà không
    có gì xảy ra thì tệ hơn hẳn một job trùng.
    """
    from sqlalchemy import select

    from app.models import Job

    now = bay_gio or datetime.now(timezone.utc)
    hang = session.execute(
        select(Job)
        .where(Job.page_id == page_id, Job.type == loai,
               Job.status.in_((JobStatus.queued, JobStatus.running)))
        .order_by(Job.created_at.desc())
    ).scalars().all()

    for job in hang:
        if job.status is JobStatus.queued:
            # Chưa ai nhặt: chắc chắn còn sống. Đẩy thêm là trùng thật.
            return job
        moc = job.heartbeat_at or job.started_at
        if moc is None:
            # `running` mà không có mốc nào (job trước E22) — không đủ bằng chứng để gọi là mồ
            # côi, nên coi là còn sống. Thà bỏ một lượt đẩy còn hơn đẩy trùng.
            return job
        if (now - moc).total_seconds() <= nguong_qua_han_giay(loai):
            return job
    return None
