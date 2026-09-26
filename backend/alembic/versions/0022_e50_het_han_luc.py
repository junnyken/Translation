"""E50 — mốc tự xoá của chapter (vòng đời tệp 30 phút).

Đếm từ lúc **cả chapter xong**, không phải lúc tải lên: một chapter 24 trang mất 30–40 phút để
chạy, đếm từ lúc tải lên thì tệp hết hạn TRƯỚC khi dịch xong.

Có chỉ mục vì phép dọn chạy định kỳ và luôn hỏi "chapter nào đã quá hạn" — quét toàn bảng mỗi
lượt là việc thừa trên một tiến trình worker đã bị hệ điều hành giết 3 lần.

Revision ID: 0022_e50
Revises: 0021_e49c
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0022_e50"
down_revision = "0021_e49c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "project", sa.Column("het_han_luc", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index("ix_project_het_han_luc", "project", ["het_han_luc"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_project_het_han_luc", table_name="project")
    op.drop_column("project", "het_han_luc")
