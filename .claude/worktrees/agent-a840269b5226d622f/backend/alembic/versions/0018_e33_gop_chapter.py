"""E33 — gộp nhiều chapter vào một file xuất.

Thêm MỘT cột nullable vào `export_job`. Không đổi cột nào đang có, không tạo bảng mới.

`project_id` giữ nguyên nghĩa "chapter chính" — nó là chỗ nghẽn kiểm quyền và là khoá ngoại mà
mọi đường đọc hiện có đang dùng. `gop_project_ids` là danh sách id theo ĐÚNG thứ tự người dùng
chọn (kể cả chapter chính); `NULL` ⇒ xuất một chapter như trước E33.

Revision ID: 0018_e33
Revises: 0017_e22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0018_e33"
down_revision = "0017_e22"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("export_job", sa.Column("gop_project_ids", JSONB(), nullable=True))


def downgrade() -> None:
    # Cột JSONB không kéo theo enum type nào, nên không cần DROP TYPE ở đây (khác 0001_m1).
    op.drop_column("export_job", "gop_project_ids")
