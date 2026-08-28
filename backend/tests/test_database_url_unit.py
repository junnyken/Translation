"""Unit — ép URL database về đúng driver (chuẩn bị chạy thật).

Nền tảng hosting tiêm `DATABASE_URL` dạng `postgresql://…` không có driver. SQLAlchemy gặp dạng
đó mặc định dùng `psycopg2` — thứ repo này KHÔNG cài — nên container chết lặp lúc khởi động với
`ModuleNotFoundError: No module named 'psycopg2'`. Đây là lỗi thật đã gặp khi deploy lần đầu.
"""
from __future__ import annotations

import pytest

from app.core.config import Settings

VAO = "user:mat_khau@may-chu.noi-bo:5432/tendb"


@pytest.mark.parametrize(
    "url_vao",
    [
        f"postgresql://{VAO}",
        f"postgres://{VAO}",
        f"postgresql+asyncpg://{VAO}",
        f"postgresql+psycopg://{VAO}",
        f"postgresql+psycopg2://{VAO}",
    ],
)
def test_moi_dang_url_deu_ra_dung_driver(url_vao):
    s = Settings(database_url=url_vao)
    assert s.async_database_url == f"postgresql+asyncpg://{VAO}"
    assert s.sync_database_url == f"postgresql+psycopg://{VAO}"


def test_khong_bao_gio_ra_psycopg2():
    """psycopg2 không có trong requirements — ra URL đó là chết lúc chạy."""
    for url in (f"postgresql://{VAO}", f"postgres://{VAO}", f"postgresql+psycopg2://{VAO}"):
        s = Settings(database_url=url)
        assert "psycopg2" not in s.sync_database_url
        assert "psycopg2" not in s.async_database_url


def test_uu_tien_alembic_database_url_neu_khai_rieng():
    s = Settings(database_url=f"postgresql://{VAO}", alembic_database_url=f"postgresql://khac:x@h/d")
    assert s.sync_database_url == "postgresql+psycopg://khac:x@h/d"


def test_mat_khau_co_ky_tu_dac_biet_khong_bi_hong():
    url = "postgresql://u:p%40ss%2Fword@h:5432/d"
    s = Settings(database_url=url)
    assert s.async_database_url == "postgresql+asyncpg://u:p%40ss%2Fword@h:5432/d"


def test_url_khong_phai_postgres_thi_giu_nguyen():
    s = Settings(database_url="sqlite+aiosqlite:///./x.db")
    assert s.async_database_url == "sqlite+aiosqlite:///./x.db"
