"""Celery app — khung hàng đợi cho M2-M9.

M2 đăng ký task thật đầu tiên: `detect.run_detect_job` (app/workers/tasks.py),
tiêu thụ Job(type=detect) do endpoint upload page tạo ra.
"""
from celery import Celery
from celery.signals import worker_ready

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "translation",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)
celery_app.conf.update(
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    timezone="Asia/Ho_Chi_Minh",
    # Khi chạy thật, worker và Redis khởi động không cùng lúc. Không bật cái này thì Celery 6 sẽ
    # KHÔNG thử lại lúc mới bật và worker chết ngay nếu Redis chậm hơn vài giây.
    broker_connection_retry_on_startup=True,
    # P3k — ĐẶT TƯỜNG MINH, không sống nhờ mặc định của thư viện.
    #
    # `task_acks_late=True` ở trên nghĩa là task chỉ được ack KHI XONG, nên worker chết giữa chừng
    # thì broker GIAO LẠI. Với Redis, "giao lại" xảy ra sau `visibility_timeout`. Không đặt thì
    # Celery dùng mặc định 3600s — một con số không ai chọn, không ai ghi, và không ai kiểm.
    #
    # RÀNG BUỘC BẮT BUỘC: giá trị này phải LỚN HƠN trần cứng của task lâu nhất. Thấp hơn thì
    # Redis giao lại trong khi task VẪN ĐANG CHẠY ⇒ hai lượt cùng một việc trên cùng một trang.
    # Với `--pool=solo`, một task kẹt trong mã native (ONNX) thì `soft_time_limit` cũng không cắt
    # được, nên chạy trùng là rủi ro có thật — và hai lượt inpaint cùng lúc chính là thứ đã gây
    # OOM ở pilot. `test_visibility_timeout_phai_lon_hon_tran_task` khoá ràng buộc này lại.
    #
    # Vì sao 1800 chứ không thấp hơn: trần task lớn nhất hiện là 930s (translate/export). 1800 cho
    # gần gấp đôi biên an toàn, đồng thời rút thời gian giao lại từ 60 phút xuống 30.
    # Vì sao không cố hạ sâu hơn: việc làm thất bại HIỆN RA NGAY đã do P3j lo (quét lúc worker
    # khởi động). Đổi rủi ro chạy trùng để lấy thêm vài phút khôi phục là một món hời tồi.
    broker_transport_options={"visibility_timeout": 1800},
)


@worker_ready.connect
def _don_job_mo_coi_luc_khoi_dong(**_):
    """P3j — worker vừa sống lại nghĩa là worker trước đã chết; job nào còn `running` là mồ côi.

    Bọc trong try/except có chủ đích: dọn dẹp hỏng thì **không được** ngăn worker nhận việc. Một
    worker chạy được mà chưa dọn còn hơn một worker không chạy.
    """
    if not settings.worker_sweep_orphan_jobs_on_start:
        return
    try:
        from app.core.db_sync import sync_session
        from app.workers.hoi_phuc import don_job_mo_coi

        with sync_session() as s:
            don_job_mo_coi(s, ap_dung=True)
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).exception("dọn job mồ côi lỗi — bỏ qua, worker vẫn nhận việc")
