"""Durable private-upload keys and deletion tombstones.

Revision ID: 0037_upload_request
Revises: 0036_cau_hinh_rieng
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "0037_upload_request"
down_revision = "0036_cau_hinh_rieng"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "upload_request",
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("nguoi_dung.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("page_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("page.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("owner_id", "request_key"),
    )
    op.create_index("ix_upload_request_page_id", "upload_request", ["page_id"])


def downgrade():
    op.drop_index("ix_upload_request_page_id", table_name="upload_request")
    op.drop_table("upload_request")
