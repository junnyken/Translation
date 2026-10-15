"""E72 — giá trị mới `local_llm` cho enum Postgres `translation_engine`.

`ALTER TYPE … ADD VALUE` chạy trong `autocommit_block`: giá trị mới không dùng được trong CÙNG
transaction đã thêm nó.

Downgrade KHÔNG gỡ giá trị: Postgres không có `DROP VALUE`; dựng lại kiểu là phải viết lại mọi cột
đang dùng nó, và dòng đã lưu `local_llm` thì không có giá trị nào để quy về mà không nói dối về
engine đã chạy. Để lại một giá trị thừa là vô hại.

Revision ID: 0026_e72
Revises: 0025_e70
"""
from __future__ import annotations

from alembic import op

revision = "0026_e72"
down_revision = "0025_e70"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE translation_engine ADD VALUE IF NOT EXISTS 'local_llm'")


def downgrade() -> None:
    pass
