"""E14 — vùng đặt chữ an toàn theo hình bong bóng

Revision ID: 0007_e14
Revises: 0006_e13
Create Date: 2026-08-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0007_e14'
down_revision = '0006_e13'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'region_safe_area',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('region_id', sa.UUID(), nullable=False),
        sa.Column('algorithm_version', sa.String(length=64), nullable=False),
        sa.Column('source', sa.Enum('shape_derived', 'fallback_rectangle', 'manual_override',
                                    name='safe_area_source'), nullable=False),
        sa.Column('status', sa.Enum('ready', 'fallback_rectangle', 'needs_review', 'failed',
                                    name='safe_area_status'), nullable=False),
        sa.Column('roi_x', sa.Integer(), nullable=False),
        sa.Column('roi_y', sa.Integer(), nullable=False),
        sa.Column('roi_w', sa.Integer(), nullable=False),
        sa.Column('roi_h', sa.Integer(), nullable=False),
        sa.Column('geometry_type', sa.Enum('rect', 'polygon', name='safe_area_geometry_type'),
                  nullable=False),
        sa.Column('geometry_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('safe_area_pixels', sa.Integer(), nullable=True),
        sa.Column('bbox_coverage_ratio', sa.Float(), nullable=True),
        sa.Column('reason_codes', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('config_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('place_rect_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('clean_image_fingerprint', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False),
        sa.ForeignKeyConstraint(['region_id'], ['text_region.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        # Đúng MỘT vùng an toàn hiện hành cho mỗi vùng chữ. Tính lại là ghi đè, không đẻ bản mới.
        sa.UniqueConstraint('region_id', name='uq_region_safe_area_region'),
    )


def downgrade() -> None:
    op.drop_table('region_safe_area')
    # Enum của Postgres KHÔNG tự mất khi drop table — không xoá tay thì lần nâng cấp sau
    # sẽ gãy vì "type already exists" (bài học từ 0001).
    op.execute('DROP TYPE IF EXISTS safe_area_geometry_type')
    op.execute('DROP TYPE IF EXISTS safe_area_status')
    op.execute('DROP TYPE IF EXISTS safe_area_source')
