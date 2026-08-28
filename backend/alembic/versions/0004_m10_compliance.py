"""M10 compliance — bảng export_compliance_log

Revision ID: 0004_m10
Revises: 0003_m9
Create Date: 2026-08-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0004_m10'
down_revision = '0003_m9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'export_compliance_log',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('export_job_id', sa.UUID(), nullable=True),
        # Dùng LẠI enum `intended_use` đã có từ M1 -> create_type=False, không tạo type trùng nghĩa.
        sa.Column('intended_use',
                  postgresql.ENUM('personal', 'study', 'other', name='intended_use',
                                  create_type=False),
                  nullable=False),
        sa.Column('overflow_warning_count', sa.Integer(), nullable=False),
        sa.Column('needs_manual_count', sa.Integer(), nullable=False),
        sa.Column('user_acknowledged', sa.Boolean(), nullable=False),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='CASCADE'),
        # SET NULL: xoá bản ghi xuất KHÔNG được xoá mất bằng chứng đã xác nhận.
        sa.ForeignKeyConstraint(['export_job_id'], ['export_job.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_export_compliance_project', 'export_compliance_log',
                    ['project_id', 'acknowledged_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_export_compliance_project', table_name='export_compliance_log')
    op.drop_table('export_compliance_log')
    # KHÔNG drop type `intended_use`: bảng `project` của M1 vẫn đang dùng.
