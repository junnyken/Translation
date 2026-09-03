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
