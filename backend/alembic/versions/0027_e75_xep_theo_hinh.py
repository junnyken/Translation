"""E75 — vị trí từng dòng khi chữ được xếp theo hình bong bóng.

`typeset_result.dong_json`: `[[tâm_x, đỉnh_y], …]` theo toạ độ ẢNH GỐC. Bước căn chữ tính và lưu,
bộ vẽ chỉ đọc — giữ "một đường vẽ duy nhất" của E14. NULL ⇒ khối chữ nhật như trước.

Revision ID: 0027_e75
Revises: 0026_e72
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0027_e75"
down_revision = "0026_e72"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("typeset_result", sa.Column(
        "dong_json", postgresql.JSONB(), nullable=True,
        comment="E75: [[tâm_x, đỉnh_y], …] mỗi dòng, toạ độ ảnh gốc; NULL = khối chữ nhật",
    ))


def downgrade() -> None:
    op.drop_column("typeset_result", "dong_json")
