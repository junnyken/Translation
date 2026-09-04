"""Fixture test: DB Postgres THẬT (không sqlite/mock), migration thật, storage tạm.

TEST_DATABASE_URL mặc định trỏ service `db` của docker-compose (cổng 5433 trên host).
"""
from __future__ import annotations

import os
import tempfile
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

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
# M9: tắt cổng nhịp trong test — test dùng translator giả, không gọi nhà cung cấp thật, nên
# cổng chỉ làm test phụ thuộc vào Redis. Cổng có bộ test riêng ở `test_batch_unit.py`.
os.environ.setdefault("LLM_PROJECT_RPM", "0")
# M6: font nằm trong `backend/fonts/` (phải nằm TRONG backend/ để nền tảng hosting
# build được — nó chỉ nhận thư mục con `backend` hoặc `frontend` làm gốc build).
os.environ.setdefault("FONT_DIR", str(Path(__file__).resolve().parents[1] / "fonts"))

import sqlalchemy as sa  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.db import get_session  # noqa: E402
from app.main import app  # noqa: E402

TABLES = (
    "consistency_review_task",
    "character_voice_profile",
    "glossary_entry",
    "region_quality_assessment",
    "export_compliance_log",
    "batch_item",
    "batch_run",
    "export_job",
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


# ── Tài khoản dùng cho test (Auth slice B) ────────────────────────────────────────────────
# Tạo MỘT LẦN cho cả lượt chạy, không phải mỗi test: mỗi lần băm scrypt tốn ~83ms, nhân với
# ~700 test là thêm cả phút vào mỗi lần chạy mà chẳng kiểm thêm được gì.
#
# `nguoi_dung` và `phien` KHÔNG nằm trong TABLES nên không bị TRUNCATE giữa các test. An toàn:
# TRUNCATE ... CASCADE chỉ lan sang bảng THAM CHIẾU tới bảng bị xoá, mà `nguoi_dung` không
# tham chiếu `project` (chiều ngược lại).
EMAIL_A = "a@test.local"
EMAIL_B = "b@test.local"
MAT_KHAU_TEST = "mat-khau-test-1234"


#: Băm scrypt MỘT lần cho cả lượt chạy (~83ms). Dùng chung cho cả hai tài khoản test —
#: test không kiểm sức mạnh mật khẩu ở đây, chỉ cần đăng nhập được.
_BAM_TEST: list[str] = []
_ENGINE_TEST: list = []


def _tao_tai_khoan_test() -> dict[str, tuple[str, str]]:
    """Trả `{email: (user_id, mã phiên thô)}`. Dùng driver đồng bộ cho đơn giản.

    **Idempotent và tự dựng lại**: `test_migration.py` chạy `downgrade base` trên chính CSDL
    test, tức là nó XOÁ bảng `nguoi_dung`. Nếu fixture này chỉ chạy một lần cho cả lượt thì mọi
    test xếp sau test đó sẽ mất tài khoản và nhận 401 — đúng triệu chứng đã đo được: cả
    `test_range_integration` lẫn `test_typeset_task_integration` xanh khi chạy riêng, đỏ khi
    chạy chung.
    """
    from app.core import phien as ph
    from app.core.mat_khau import bam

    # Dùng CHUNG một engine cho cả lượt chạy. Tạo engine mới mỗi test (~980 test) mở ra ngần
    # ấy pool kết nối, và Postgres có trần `max_connections` — hết trần thì các test khác đỏ ở
    # những chỗ chẳng liên quan gì tới tài khoản.
    if not _ENGINE_TEST:
        _ENGINE_TEST.append(sa.create_engine(_sync_url(TEST_DB_URL), pool_size=2, max_overflow=2))
    eng = _ENGINE_TEST[0]
    ket_qua: dict[str, tuple[str, str]] = {}
    if not _BAM_TEST:
        _BAM_TEST.append(bam(MAT_KHAU_TEST))
    bam_chung = _BAM_TEST[0]
    with eng.begin() as conn:
        for email in (EMAIL_A, EMAIL_B):
            uid = conn.execute(
                sa.text("SELECT id FROM nguoi_dung WHERE email = :e"), {"e": email}
            ).scalar()
            if uid is None:
                uid = uuid.uuid4()
                conn.execute(
                    sa.text(
                        "INSERT INTO nguoi_dung (id, email, ten_hien, mat_khau_bam,"
                        " dang_hoat_dong, la_quan_tri) VALUES"
                        " (:id, :e, :t, :b, true, false)"
                    ),
                    {"id": uid, "e": email, "t": email.split("@")[0], "b": bam_chung},
                )
            ma_tho = ph.sinh_ma()
            conn.execute(
                sa.text(
                    "INSERT INTO phien (id, nguoi_dung_id, ma_bam, het_han)"
                    " VALUES (:id, :u, :h, :x)"
                ),
                {"id": uuid.uuid4(), "u": uid, "h": ph.bam_ma(ma_tho), "x": ph.han_moi()},
            )
            ket_qua[email] = (str(uid), ma_tho)
    return ket_qua


@pytest.fixture
def tai_khoan_test(migrated_database) -> dict[str, tuple[str, str]]:
    """Cố ý KHÔNG dùng `scope="session"` — xem giải thích ở `_tao_tai_khoan_test`."""
    return _tao_tai_khoan_test()


@pytest.fixture
def nguoi_a(tai_khoan_test) -> tuple[str, str]:
    """`(user_id, mã phiên)` của tài khoản A — chủ mặc định của mọi thứ test tạo ra."""
    return tai_khoan_test[EMAIL_A]


@pytest.fixture
def nguoi_b(tai_khoan_test) -> tuple[str, str]:
    """Tài khoản thứ hai — dùng để chứng minh A không đụng được vào dữ liệu của B và ngược lại."""
    return tai_khoan_test[EMAIL_B]


def _client(session, headers: dict[str, str]) -> AsyncClient:
    async def _override() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _override
    return AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=headers
    )


@pytest.fixture
async def client(session, nguoi_a) -> AsyncIterator[AsyncClient]:
    """Máy khách ĐÃ đăng nhập bằng tài khoản A.

    Mặc định là "đã đăng nhập" để hàng trăm test có sẵn không phải sửa. Test nào cần chứng
    minh cổng đăng nhập hoạt động thì dùng `client_chua_dang_nhap`.
    """
    async with _client(session, {"Authorization": f"Bearer {nguoi_a[1]}"}) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def client_b(session, nguoi_b) -> AsyncIterator[AsyncClient]:
    """Máy khách đăng nhập bằng tài khoản B — người lạ với dữ liệu của A."""
    async with _client(session, {"Authorization": f"Bearer {nguoi_b[1]}"}) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def client_chua_dang_nhap(session) -> AsyncIterator[AsyncClient]:
    async with _client(session, {}) as c:
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
    monkeypatch.setattr(
        tasks.run_translate_job, "delay", lambda job_id, engine=None: sent.append(job_id)
    )
    monkeypatch.setattr("app.api.v1.routes.dispatch_ocr_job", lambda job_id: (True, None))
    monkeypatch.setattr("app.api.v1.routes.dispatch_inpaint_job", lambda job_id: (True, None))
    monkeypatch.setattr(
        "app.api.v1.routes.dispatch_translate_job", lambda job_id, engine=None: (True, None)
    )
    monkeypatch.setattr(tasks.run_typeset_job, "delay", lambda job_id: sent.append(job_id))
    monkeypatch.setattr("app.api.v1.routes.dispatch_typeset_job", lambda job_id: (True, None))
    # E18 — rút gọn bản dịch cho vừa bong bóng
    monkeypatch.setattr(tasks.run_rut_gon_job, "delay", lambda job_id: sent.append(job_id))
    monkeypatch.setattr("app.api.v1.routes.dispatch_rut_gon_job", lambda job_id: (True, None))
    # M7 — sửa tay từng vùng
    monkeypatch.setattr(
        tasks.run_refit_job, "delay", lambda job_id, region_id, font_size=None: sent.append(job_id)
    )
    monkeypatch.setattr(
        "app.api.v1.routes.dispatch_refit_job",
        lambda job_id, region_id, font_size=None: (True, None),
    )
    monkeypatch.setattr(
        "app.api.v1.routes.dispatch_region_reocr_job", lambda job_id, region_id: (True, None)
    )
    monkeypatch.setattr(
        "app.api.v1.routes.dispatch_region_retranslate_job",
        lambda job_id, region_id, engine=None: (True, None),
    )
    # M8 — xuất chapter
    monkeypatch.setattr(tasks.run_export_job, "delay", lambda job_id: sent.append(job_id))
    monkeypatch.setattr("app.api.v1.routes.dispatch_export_job", lambda job_id: (True, None))
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


@pytest.fixture
def fake_translator(monkeypatch):
    """Translator giả lập cho cả 2 path, có thể ép lỗi để thử nhánh fallback."""
    from app.services.translate.engines import UsageStats
    from app.workers import tasks

    made: list = []

    def _install(prefix="VI:", raises_for=None, total_tokens=123):
        class _Fake:
            def __init__(self, engine_name):
                self.engine_name = engine_name
                self.model_name = f"fake-{engine_name}"
                self.usage = UsageStats(model_name=self.model_name, total_tokens=total_tokens)
                self.calls = []

            def translate(self, texts, source_lang, target_lang):
                self.calls.append(list(texts))
                if raises_for and self.engine_name == raises_for:
                    from app.services.translate.engines import QuotaExhausted

                    raise QuotaExhausted("hết quota giả lập")
                return [f"{prefix}{t}" for t in texts]

        def _build(engine_name):
            fake = _Fake(engine_name)
            made.append(fake)
            return fake

        monkeypatch.setattr(tasks, "build_translator", _build)
        return made

    return _install
