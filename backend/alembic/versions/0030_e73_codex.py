"""E73 — giá trị mới `chatgpt_codex` cho enum Postgres `translation_engine`.

Cùng cách và cùng lý do với `0026_e72`: thêm trong `autocommit_block`; downgrade không gỡ giá trị
(Postgres không có `DROP VALUE`, và dòng đã lưu `chatgpt_codex` không có giá trị nào để quy về mà
không nói dối về engine đã chạy).

Revision ID: 0030_e73_codex
Revises: 0029_e78_psd
"""
from __future__ import annotations

from alembic import op

revision = "0030_e73_codex"
down_revision = "0029_e78_psd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE translation_engine ADD VALUE IF NOT EXISTS 'chatgpt_codex'")


def downgrade() -> None:
    pass
