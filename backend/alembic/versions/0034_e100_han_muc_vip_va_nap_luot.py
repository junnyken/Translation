"""E100 — cột hạn mức VIP theo ngày (`tran_hang_ngay_rieng`) và số lượt mua thêm (`so_luot_mua_them`) trên `nguoi_dung`.

Revision ID: 0034_e100_han_muc_vip
Revises: 0033_e94_tieng_han_ko
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0034_e100_han_muc_vip"
down_revision = "0033_e94_tieng_han_ko"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("nguoi_dung")}
    if "tran_hang_ngay_rieng" not in cols:
        op.add_column("nguoi_dung", sa.Column("tran_hang_ngay_rieng", sa.Integer(), nullable=True))
    if "so_luot_mua_them" not in cols:
        op.add_column(
            "nguoi_dung",
            sa.Column("so_luot_mua_them", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    op.drop_column("nguoi_dung", "so_luot_mua_them")
    op.drop_column("nguoi_dung", "tran_hang_ngay_rieng")
