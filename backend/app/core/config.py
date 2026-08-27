"""Cấu hình ứng dụng — đọc toàn bộ từ biến môi trường (.env), không hard-code credential."""
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://translation:translation@db:5432/translation"
    alembic_database_url: str | None = None

    # Job queue (dùng thật từ M2)
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"

    # Storage
    storage_backend: Literal["local", "supabase"] = "local"
    storage_local_root: str = "/data/storage"
    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_bucket: str = "manga-pages"

    # Upload
    max_upload_mb: int = 25

    # ---- M2: comic-text-detector ----
    #: Đường dẫn file weight ONNX. Không có file -> job detect fail rõ ràng,
    #: tuyệt đối không detect bằng weight giả.
    model_weights_path: str = "/models/comic-text-detector.onnx"
    ctd_device: str = "cpu"
    #: Dưới ngưỡng này region vẫn được LƯU với status=low_confidence (không loại bỏ).
    ctd_conf_threshold: float = 0.5
    #: Sàn nhiễu trước NMS — phải nhỏ hơn ctd_conf_threshold để low_confidence còn được giữ.
    ctd_raw_min_conf: float = 0.25
    ctd_nms_iou: float = 0.45
    ctd_input_size: int = 1024
    ctd_intra_op_threads: int = 0
    #: 2 box chồng nhau quá tỷ lệ này (so với box nhỏ hơn) -> gắn cờ overlap_suspect.
    ctd_overlap_suspect_ratio: float = 0.8
    #: Timeout job detect. Mặc định 60s theo spec; trên máy chỉ có CPU nên đặt cao hơn
    #: trong .env (đo thật: ~39s/ảnh 1400x2000 trên workspace này).
    detect_timeout_seconds: int = 60

    app_env: str = "dev"
    log_level: str = "INFO"

    @property
    def sync_database_url(self) -> str:
        """URL driver đồng bộ cho Alembic (suy ra từ database_url nếu không khai báo riêng)."""
        if self.alembic_database_url:
            return self.alembic_database_url
        return self.database_url.replace("+asyncpg", "+psycopg")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
