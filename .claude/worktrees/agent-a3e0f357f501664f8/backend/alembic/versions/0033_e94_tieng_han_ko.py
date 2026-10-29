"""E94 — hỗ trợ tiếng Hàn (`ko` / Manhwa / Webtoon) trong enum Postgres `source_lang`.

Revision ID: 0033_e94_tieng_han_ko
Revises: 0032_e90_chu_nhan_dien
"""
from __future__ import annotations

from alembic import op

revision = "0033_e94_tieng_han_ko"
down_revision = "0032_e90_chu_nhan_dien"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE source_lang ADD VALUE IF NOT EXISTS 'ko'")


def downgrade() -> None:
    # Postgres không có DROP VALUE cho enum — giữ tương tự 0026/0030/0032.
    pass
