"""Bảng thanh toán trực tuyến chuẩn an toàn (`payment_orders`, `payment_events`, `payment_reviews`)
và cột quyền lợi gói trả phí bền vững trên `nguoi_dung`.

Revision ID: 0039_payment_online_safe
Revises: 0038_detect_outbox
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0039_payment_online_safe"
down_revision = "0038_detect_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "nguoi_dung",
        sa.Column("cap_do_goi", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "nguoi_dung",
        sa.Column("ma_goi_hien_tai", sa.String(64), nullable=True),
    )
    op.add_column(
        "nguoi_dung",
        sa.Column("het_han_goi", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "nguoi_dung",
        sa.Column("trang_thai_billing", sa.String(32), nullable=False, server_default="free"),
    )
    op.add_column(
        "nguoi_dung",
        sa.Column("gio_luot_json", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.create_index("ix_nguoi_dung_het_han_goi", "nguoi_dung", ["het_han_goi"])

    op.create_table(
        "payment_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("nguoi_dung.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("owner_ref", sa.String(64), nullable=False),
        sa.Column("email", sa.String(320), nullable=False, server_default=""),
        sa.Column("plan", sa.String(64), nullable=False),
        sa.Column("tier_rank", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("rail", sa.String(32), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("paid_amount", sa.BigInteger(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_ref", sa.Text(), nullable=True),
        sa.Column("evidence", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("code", name="uq_payment_orders_code"),
    )
    op.create_index("ix_payment_orders_status_expires", "payment_orders", ["status", "expires_at"])
    op.create_index("ix_payment_orders_user_created", "payment_orders", ["user_id", "created_at"])
    op.create_index("ix_payment_orders_owner_created", "payment_orders", ["owner_ref", "created_at"])

    op.create_table(
        "payment_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("provider_event_id", sa.String(160), nullable=False),
        sa.Column("event_type", sa.String(96), nullable=True),
        sa.Column("amount", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("match_type", sa.String(40), nullable=False, server_default="claiming"),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("provider", "provider_event_id", name="uq_payment_events_provider_event"),
    )
    op.create_index("ix_payment_events_order_id", "payment_events", ["order_id"])

    op.create_table(
        "payment_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("provider_event_id", sa.String(160), nullable=True),
        sa.Column("event_type", sa.String(96), nullable=True),
        sa.Column("user_id", sa.String(64), nullable=True),
        sa.Column("user_email", sa.String(320), nullable=True),
        sa.Column("order_id", sa.String(64), nullable=True),
        sa.Column("order_code", sa.String(32), nullable=True),
        sa.Column("current_tier", sa.String(32), nullable=True),
        sa.Column("target_tier", sa.String(32), nullable=True),
        sa.Column("amount", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="needs_manual_review"),
        sa.Column("reason", sa.String(120), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("resolved_by", sa.String(320), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_payment_reviews_status_created", "payment_reviews", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_payment_reviews_status_created", table_name="payment_reviews")
    op.drop_table("payment_reviews")
    op.drop_index("ix_payment_events_order_id", table_name="payment_events")
    op.drop_table("payment_events")
    op.drop_index("ix_payment_orders_owner_created", table_name="payment_orders")
    op.drop_index("ix_payment_orders_user_created", table_name="payment_orders")
    op.drop_index("ix_payment_orders_status_expires", table_name="payment_orders")
    op.drop_table("payment_orders")
    op.drop_index("ix_nguoi_dung_het_han_goi", table_name="nguoi_dung")
    op.drop_column("nguoi_dung", "gio_luot_json")
    op.drop_column("nguoi_dung", "trang_thai_billing")
    op.drop_column("nguoi_dung", "het_han_goi")
    op.drop_column("nguoi_dung", "ma_goi_hien_tai")
    op.drop_column("nguoi_dung", "cap_do_goi")
