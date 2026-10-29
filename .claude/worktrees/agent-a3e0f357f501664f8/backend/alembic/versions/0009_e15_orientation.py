"""E15 — hướng chữ của từng vùng

Revision ID: 0009_e15b
Revises: 0008_e15a
Create Date: 2026-08-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0009_e15b'
down_revision = '0008_e15a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'region_text_orientation',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('region_id', sa.UUID(), nullable=False),
        sa.Column('algorithm_version', sa.String(length=64), nullable=False),
        sa.Column('orientation', sa.Enum('horizontal_ltr', 'vertical_ttb',
                                         'rotated_horizontal', 'unknown',
                                         name='text_orientation'), nullable=False),
        sa.Column('source', sa.Enum('ctd_geometry', 'ocr_layout', 'image_heuristic',
                                    'manual_reserved', 'fallback_unknown',
                                    name='orientation_source'), nullable=False),
        sa.Column('status', sa.Enum('ready', 'needs_review', 'unavailable', 'failed',
                                    name='orientation_status'), nullable=False),
        sa.Column('rotation_degrees', sa.Float(), nullable=True),
        sa.Column('line_count_estimate', sa.Integer(), nullable=True),
        sa.Column('reason_codes', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('evidence_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False),
        sa.ForeignKeyConstraint(['region_id'], ['text_region.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('region_id', name='uq_region_text_orientation_region'),
    )


def downgrade() -> None:
    op.drop_table('region_text_orientation')
    # Enum Postgres không tự mất khi drop table (bài học từ 0001).
    op.execute('DROP TYPE IF EXISTS orientation_status')
    op.execute('DROP TYPE IF EXISTS orientation_source')
    op.execute('DROP TYPE IF EXISTS text_orientation')
