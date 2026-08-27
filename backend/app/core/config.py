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
