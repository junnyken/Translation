"""E17 — lượt xin gợi ý cách dịch danh xưng theo tên bộ truyện (tầng 3)

Revision ID: 0011_e17
Revises: 0010_p3e
Create Date: 2026-09-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '0011_e17'
down_revision = '0010_p3e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'term_suggestion_run',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        # Nguyên văn người dùng gõ — không chuẩn hoá, để còn đối chất khi kết quả lạ.
        sa.Column('series_name', sa.Text(), nullable=False),
        sa.Column(
            'status',
            sa.Enum('queued', 'running', 'done', 'failed', name='term_suggestion_status'),
            nullable=False,
            server_default='queued',
        ),
        sa.Column('model_name', sa.String(length=200), nullable=True),
        # NULL = chưa chạy xong. [] = chạy xong, cổng đối chiếu loại sạch. KHÔNG gộp hai thứ này.
        sa.Column('suggestions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('dropped_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('asked_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_log', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_term_suggestion_project', 'term_suggestion_run',
                    ['project_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_term_suggestion_project', table_name='term_suggestion_run')
    op.drop_table('term_suggestion_run')
    # Enum type KHÔNG tự biến mất khi drop table (bài học từ M1) -> drop tường minh.
    op.execute(sa.text("DROP TYPE IF EXISTS term_suggestion_status"))
