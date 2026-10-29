"""Bảng `don_nap_luot` (thay tệp JSON, chống cộng lượt trùng) và `nhat_ky_quan_tri`.

Revision ID: 0035_don_nap_nhat_ky
Revises: 0034_e100_han_muc_vip
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0035_don_nap_nhat_ky"
down_revision = "0034_e100_han_muc_vip"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "don_nap_luot",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ma_don", sa.String(32), nullable=False),
        sa.Column(
            "nguoi_dung_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("nguoi_dung.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("ten_hien", sa.String(120), nullable=False, server_default=""),
        sa.Column("ma_goi", sa.String(60), nullable=False),
        sa.Column("ten_goi", sa.String(160), nullable=False, server_default=""),
        sa.Column("so_tien_vnd", sa.BigInteger(), nullable=False),
        sa.Column("so_trang_cong", sa.Integer(), nullable=False),
        sa.Column("noi_dung_chuyen_khoan", sa.Text(), nullable=False, server_default=""),
        sa.Column("trang_thai", sa.String(32), nullable=False),
        sa.Column("ma_giao_dich_ngan_hang", sa.String(128), nullable=True),
        sa.Column("duyet_luc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("ma_don", name="uq_don_nap_luot_ma_don"),
        sa.UniqueConstraint("ma_giao_dich_ngan_hang", name="uq_don_nap_luot_ma_giao_dich"),
    )
    op.create_index("ix_don_nap_luot_nguoi_dung_id", "don_nap_luot", ["nguoi_dung_id"])
    op.create_index("ix_don_nap_luot_email", "don_nap_luot", ["email"])
    op.create_index("ix_don_nap_luot_trang_thai", "don_nap_luot", ["trang_thai"])

    op.create_table(
        "nhat_ky_quan_tri",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "quan_tri_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("nguoi_dung.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("quan_tri_email", sa.String(320), nullable=False),
        sa.Column("hanh_dong", sa.String(64), nullable=False),
        sa.Column("doi_tuong", sa.String(320), nullable=False, server_default=""),
        sa.Column("chi_tiet", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_nhat_ky_quan_tri_hanh_dong", "nhat_ky_quan_tri", ["hanh_dong"])
    op.create_index("ix_nhat_ky_quan_tri_created_at", "nhat_ky_quan_tri", ["created_at"])


def downgrade() -> None:
    op.drop_table("nhat_ky_quan_tri")
    op.drop_table("don_nap_luot")
