"""Dựng bộ điều phối mẻ từ cấu hình — **một chỗ duy nhất** (M9).

Lỗi thật do Run B tìm ra: tầng API dựng `BatchOrchestrator` kèm `RetryPolicy` đọc từ cấu hình,
còn tầng worker thì dựng bằng tay và **quên** truyền `retry_policy`. Mà mọi quyết định thử lại
đều xảy ra ở worker — nên `BATCH_MAX_RETRIES` và `BATCH_RETRY_BACKOFF_*` trong `.env` thực chất
**không có tác dụng gì**: hệ thống luôn chạy bằng số mặc định trong mã.

Đo được: đặt `BATCH_RETRY_BACKOFF_BASE_SECONDS=30` nhưng ba lần thử lại thật cách nhau
0,6s / 3,7s / 6,4s — đúng dãy của trần mặc định 2s, không phải của 30s.
"""
from __future__ import annotations

from app.core.config import Settings, get_settings
from app.services.batch.errors import RetryPolicy
from app.services.batch.orchestrator import BatchOrchestrator


def tao_dieu_phoi(settings: Settings | None = None) -> BatchOrchestrator:
    s = settings or get_settings()
    return BatchOrchestrator(
        max_concurrent_pages=s.batch_max_concurrent_pages,
        retry_policy=RetryPolicy(
            max_retries=s.batch_max_retries,
            backoff_base_seconds=s.batch_retry_backoff_base_seconds,
            backoff_max_seconds=s.batch_retry_backoff_max_seconds,
            jitter=s.batch_retry_jitter,
        ),
        stale_item_seconds=s.batch_stale_item_seconds,
    )
