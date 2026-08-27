"""Celery app — khung hàng đợi cho M2-M9.

M2 đăng ký task thật đầu tiên: `detect.run_detect_job` (app/workers/tasks.py),
tiêu thụ Job(type=detect) do endpoint upload page tạo ra.
"""
from celery import Celery

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
)
