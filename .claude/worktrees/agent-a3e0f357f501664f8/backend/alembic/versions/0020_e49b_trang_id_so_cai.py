"""E49b — gắn khoản hạn mức với TRANG nó giữ chỗ cho.

Worker cần tra "trang này đã giữ chỗ những dòng nào" để `tieu`/`hoan` khi trang tới trạng thái
cuối. Không có cột này thì chỉ còn cách dò tiền tố chuỗi trên `khoa_idempotency` — chậm và dễ
sai khi đổi cách đặt khoá.

**Cố ý KHÔNG có khoá ngoại tới `page`.** Trang bị xoá sau 30 phút, còn sổ cái là dấu vết hạn mức
và phải sống lâu hơn trang: `CASCADE` sẽ xoá luôn bằng chứng đã tiêu lượt (⇒ người dùng được lượt
từ hư không), `RESTRICT` thì chặn mất phép dọn.

Revision ID: 0020_e49b
Revises: 0019_e49
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision = "0020_e49b"
down_revision = "0019_e49"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "so_cai_han_muc",
        sa.Column("trang_id", PGUUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_so_cai_han_muc_trang_id", "so_cai_han_muc", ["trang_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_so_cai_han_muc_trang_id", table_name="so_cai_han_muc")
    op.drop_column("so_cai_han_muc", "trang_id")
