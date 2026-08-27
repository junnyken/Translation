"""Fixture test: DB Postgres THẬT (không sqlite/mock), migration thật, storage tạm.

TEST_DATABASE_URL mặc định trỏ service `db` của docker-compose (cổng 5433 trên host).
"""
from __future__ import annotations

import os
import tempfile
import uuid
from collections.abc import AsyncIterator

import pytest

TEST_DB_URL = os.environ.setdefault(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://translation:translation@localhost:5433/translation_test",
)
# Phải set TRƯỚC khi import app (Settings cache bằng lru_cache).
os.environ["DATABASE_URL"] = TEST_DB_URL
_STORAGE_ROOT = tempfile.mkdtemp(prefix="translation-test-storage-")
os.environ["STORAGE_LOCAL_ROOT"] = _STORAGE_ROOT
os.environ["STORAGE_BACKEND"] = "local"

import sqlalchemy as sa  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.db import get_session  # noqa: E402
from app.main import app  # noqa: E402

TABLES = (
    "job",
    "typeset_result",
    "translation_result",
    "ocr_result",
    "text_region",
    "page",
    "project",
)


def _sync_url(url: str) -> str:
    return url.replace("+asyncpg", "+psycopg")


def _ensure_test_database() -> None:
    """Tạo DB test nếu chưa có (kết nối vào db `postgres` để CREATE DATABASE)."""
    target = sa.engine.make_url(_sync_url(TEST_DB_URL))
    admin = target.set(database="postgres")
    engine = sa.create_engine(admin, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        exists = conn.execute(
            sa.text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": target.database}
        ).scalar()
        if not exists:
            conn.execute(sa.text(f'CREATE DATABASE "{target.database}"'))
    engine.dispose()


def _run_migrations(direction: str = "head") -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic"))
    if direction == "head":
        command.upgrade(cfg, "head")
    else:
        command.downgrade(cfg, direction)


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    get_settings.cache_clear()
    _ensure_test_database()
    _run_migrations("base")  # DB sạch tuyệt đối trước khi chạy
    _run_migrations("head")


@pytest.fixture
async def engine():
    eng = create_async_engine(TEST_DB_URL, poolclass=None)
    yield eng
    await eng.dispose()


@pytest.fixture
async def session(engine) -> AsyncIterator[AsyncSession]:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        yield s
    async with engine.begin() as conn:
        await conn.execute(sa.text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))


@pytest.fixture
async def client(session) -> AsyncIterator[AsyncClient]:
    async def _override() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def storage_root() -> str:
    return _STORAGE_ROOT


@pytest.fixture
def sample_page_image() -> bytes:
    """Ảnh PNG THẬT (Pillow render), không phải file rỗng/mock: 1 trang giả lập có bubble."""
    import io

    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1200, 1700), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([60, 60, 1140, 820], outline="black", width=6)
    d.rectangle([60, 880, 1140, 1640], outline="black", width=6)
    d.ellipse([150, 150, 620, 430], outline="black", width=5, fill="white")
    d.text((260, 270), "SAMPLE TEXT", fill="black")
    d.ellipse([620, 980, 1080, 1260], outline="black", width=5, fill="white")
    d.text((730, 1100), "TEST BUBBLE", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture(autouse=True)
def fake_dispatch(monkeypatch):
    """Chặn gọi broker thật trong test API — ghi lại job_id đã được đẩy đi.

    Có test riêng (test_detect_task_integration) kiểm hành vi khi broker chết.
    """
    sent: list = []

    def _fake(job_id):
        sent.append(job_id)
        return True, None

    monkeypatch.setattr("app.api.v1.routes.dispatch_detect_job", _fake)
    return sent


@pytest.fixture
def fixtures_dir():
    import os

    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_fixtures")


@pytest.fixture
def fake_detector(monkeypatch):
    """Cắm detector giả lập vào worker (không nạp ONNX 91MB trong test nhanh)."""
    from app.workers import tasks

    def _install(regions=None, raises=None):
        class _Fake:
            conf_threshold = 0.5

            def detect_regions(self, image_path):
                if raises is not None:
                    raise raises
                return list(regions or [])

            def detect(self, image_path):
                return [r.bbox for r in self.detect_regions(image_path)]

        tasks._detector = _Fake()
        return tasks._detector

    yield _install
    tasks.reset_detector()


@pytest.fixture(autouse=True)
def no_broker_for_chained_ocr(monkeypatch):
    """Chặn chuỗi detect->OCR->inpaint gọi broker thật; ghi lại job_id đã đẩy.

    Không có fixture này, `.delay()` sẽ ngồi retry kết nối Redis và treo cả test suite.
    """
    from app.workers import tasks

    sent: list = []
    monkeypatch.setattr(tasks.run_ocr_job, "delay", lambda job_id: sent.append(job_id))
    monkeypatch.setattr(tasks.run_inpaint_job, "delay", lambda job_id: sent.append(job_id))
    monkeypatch.setattr("app.api.v1.routes.dispatch_ocr_job", lambda job_id: (True, None))
    monkeypatch.setattr("app.api.v1.routes.dispatch_inpaint_job", lambda job_id: (True, None))
    return sent


@pytest.fixture
def fake_ocr_engine(monkeypatch):
    """Cắm engine OCR giả lập (không nạp torch/paddle trong test nhanh)."""
    from app.models.enums import OCREngine
    from app.workers import tasks

    def _install(results=None, raises=None, engine_enum=OCREngine.manga_ocr, per_call=None):
        class _Fake:
            def __init__(self):
                self.engine_enum = engine_enum
                self.calls = []

            def recognize(self, image_path, bbox):
                self.calls.append((image_path, bbox))
                if raises is not None:
                    raise raises
                if per_call is not None:
                    return per_call(len(self.calls) - 1, bbox)
                return results if results is not None else ("text mẫu", None)

        fake = _Fake()
        monkeypatch.setattr(tasks, "get_ocr_engine_cached", lambda source_lang: fake)
        return fake

    yield _install
    tasks.reset_ocr_engines()


@pytest.fixture
def fake_inpainter(monkeypatch):
    """Inpainter giả lập: ghi ra file ảnh clean THẬT (để test đường dẫn/xoá file/idempotent)."""
    from pathlib import Path

    from PIL import Image

    from app.workers import tasks

    def _install(raises=None, fill=(255, 255, 255)):
        class _Fake:
            def __init__(self):
                self.calls = []
                self.dilate_ratio = 0.08

            def dilated_masks(self, w, h, masks):
                return list(masks)

            def clean_path_for(self, image_path):
                src = Path(image_path)
                return src.with_name(f"{src.stem}_clean.png")

            def inpaint(self, image_path, masks):
                self.calls.append((image_path, list(masks)))
                if raises is not None:
                    raise raises
                target = self.clean_path_for(image_path)
                with Image.open(image_path) as im:
                    size = im.size
                Image.new("RGB", size, fill).save(target)
                return str(target)

        fake = _Fake()
        monkeypatch.setattr(tasks, "get_inpainter", lambda: fake)
        return fake

    yield _install
    tasks.reset_inpainter()
