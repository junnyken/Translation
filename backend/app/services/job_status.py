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
