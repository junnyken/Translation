"""E78 — giá trị mới `psd` cho enum Postgres `export_format` (xuất PSD nhiều lớp).

`ALTER TYPE … ADD VALUE` chạy trong `autocommit_block`: giá trị mới không dùng được trong CÙNG
transaction đã thêm nó.

Số 0028 được để dành cho việc khác — revision này nối thẳng vào 0027_e75.

Downgrade KHÔNG gỡ giá trị: Postgres không có `DROP VALUE`; một giá trị thừa là vô hại (cùng lý do
với 0026_e72).

Revision ID: 0029_e78_psd
Revises: 0027_e75
"""
from __future__ import annotations

from alembic import op

revision = "0029_e78_psd"
down_revision = "0027_e75"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE export_format ADD VALUE IF NOT EXISTS 'psd'")


def downgrade() -> None:
    pass
