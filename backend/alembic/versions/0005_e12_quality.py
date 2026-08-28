"""E12 quality gate — bảng region_quality_assessment

Revision ID: 0005_e12
Revises: 0004_m10
Create Date: 2026-08-29

CỘNG THÊM hoàn toàn: không sửa bảng nào của M1–M10, không đụng enum cũ.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0005_e12'
down_revision = '0004_m10'
branch_labels = None
depends_on = None

_ENUM = ("region_relevance", "review_status", "overall_band", "confidence_state",
         "translation_state")


def upgrade() -> None:
    op.create_table(
        'region_quality_assessment',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('region_id', sa.UUID(), nullable=False),
        sa.Column('assessment_version', sa.String(length=32), nullable=False),
        sa.Column('relevance',
                  sa.Enum('likely_translatable', 'possible_sfx',
                          'possible_number_or_decoration', 'uncertain',
                          name='region_relevance'), nullable=False),
        sa.Column('review_status',
                  sa.Enum('not_required', 'needs_review', 'reviewed_keep', 'reviewed_skip',
                          name='review_status'), nullable=False),
        sa.Column('overall_band',
                  sa.Enum('clear', 'attention', 'blocked', name='overall_band'), nullable=False),
        sa.Column('detector_confidence_state',
                  sa.Enum('available', 'low', 'unavailable', name='confidence_state'),
                  nullable=False),
        # Dùng LẠI type `confidence_state` đã tạo ở cột trên -> create_type=False, tránh lỗi
        # "type already exists" khi Alembic tự phát hành CREATE TYPE lần hai.
        sa.Column('ocr_confidence_state',
                  postgresql.ENUM('available', 'low', 'unavailable', name='confidence_state',
                                  create_type=False), nullable=False),
        sa.Column('translation_state',
                  sa.Enum('present', 'missing', 'fallback_used', 'not_attempted',
                          name='translation_state'), nullable=False),
        sa.Column('reason_codes', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('evidence_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('assessed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False),
        sa.ForeignKeyConstraint(['region_id'], ['text_region.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('region_id', name='uq_rqa_region'),
    )
    op.create_index('ix_rqa_review_band', 'region_quality_assessment',
                    ['review_status', 'overall_band'], unique=False)
    op.create_index('ix_rqa_relevance', 'region_quality_assessment', ['relevance'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_rqa_relevance', table_name='region_quality_assessment')
    op.drop_index('ix_rqa_review_band', table_name='region_quality_assessment')
    op.drop_table('region_quality_assessment')
    # Enum type KHÔNG tự mất khi drop table (bài học từ M1) -> drop tường minh.
    for ten in _ENUM:
        op.execute(sa.text(f"DROP TYPE IF EXISTS {ten}"))
