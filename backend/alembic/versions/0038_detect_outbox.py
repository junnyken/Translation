"""Transactional delivery of the first detect job for keyed private uploads.

Revision ID: 0038_detect_outbox
Revises: 0037_upload_request
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "0038_detect_outbox"
down_revision = "0037_upload_request"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "detect_outbox",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("job.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("abandoned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_detect_outbox_next_attempt_at", "detect_outbox", ["next_attempt_at"])


def downgrade():
    op.drop_index("ix_detect_outbox_next_attempt_at", table_name="detect_outbox")
    op.drop_table("detect_outbox")
