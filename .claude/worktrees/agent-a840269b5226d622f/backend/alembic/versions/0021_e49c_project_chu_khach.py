"""E49c — chapter của khách lạ (chưa đăng nhập).

Giá trị là mã cookie **đã băm**. Cột này đổi nghĩa của `chu_so_huu_id IS NULL`: trước đây
"không có chủ" nghĩa là chapter cũ từ trước slice B mà mọi tài khoản đăng nhập đều dùng được.
Không có cột này thì chapter của khách lạ sẽ rơi đúng vào nhóm đó và **mọi người đăng nhập đọc
được truyện của mọi khách lạ**.

Revision ID: 0021_e49c
Revises: 0020_e49b
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0021_e49c"
down_revision = "0020_e49b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("project", sa.Column("chu_khach", sa.String(length=128), nullable=True))
    op.create_index("ix_project_chu_khach", "project", ["chu_khach"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_project_chu_khach", table_name="project")
    op.drop_column("project", "chu_khach")
