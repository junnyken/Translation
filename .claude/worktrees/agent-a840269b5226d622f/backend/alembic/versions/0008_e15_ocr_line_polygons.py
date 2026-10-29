"""E15 — lưu đường bao từng dòng chữ của OCR

Revision ID: 0008_e15a
Revises: 0007_e14
Create Date: 2026-08-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0008_e15a'
down_revision = '0007_e14'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'ocr_result',
        sa.Column('line_polygons', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('ocr_result', 'line_polygons')
