"""Celery app — khung hàng đợi cho M2-M9.

M1 CỐ Ý chưa đăng ký task thật nào: upload page chỉ ghi record Job(type=detect, status=queued).
Task Celery đầu tiên (detect) sẽ bind vào đây ở M2.
"""
from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "translation",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    timezone="Asia/Ho_Chi_Minh",
)
