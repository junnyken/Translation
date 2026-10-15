"""E70 — màu chữ, màu viền và bề dày viền ĐO TỪ CHỮ GỐC cho từng vùng.

Đo trên ảnh gốc ở bước căn chữ (cách đo chuyển từ Koharu — xem `typeset/mau_chu.py`), lưu cạnh
kết quả căn chữ vì bề dày viền ảnh hưởng tới phép đo cỡ chữ: hai thứ phải sống chết cùng nhau.

Cả ba cột cho phép NULL và KHÔNG có giá trị mặc định: NULL nghĩa là **chưa đo** (dòng cũ, hoặc tắt
cờ `e70_mau_chu_theo_vung`), khi đó bộ vẽ dùng màu cấu hình chung như trước E70. Không điền giá trị
giả cho dòng cũ.

Revision ID: 0025_e70
Revises: 0024_e65
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0025_e70"
down_revision = "0024_e65"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("typeset_result", sa.Column(
        "text_color", sa.String(7), nullable=True,
        comment="E70: #rrggbb màu chữ đo từ chữ gốc; NULL = chưa đo, dùng màu cấu hình",
    ))
    op.add_column("typeset_result", sa.Column(
        "stroke_color", sa.String(7), nullable=True,
        comment="E70: #rrggbb màu viền chữ gốc; NULL = không có viền / chưa đo",
    ))
    op.add_column("typeset_result", sa.Column(
        "stroke_width", sa.Float(), nullable=True,
        comment="E70: bề dày viền theo px ẢNH GỐC (chưa nhân he_so_ve); NULL = không viền / chưa đo",
    ))


def downgrade() -> None:
    op.drop_column("typeset_result", "stroke_width")
    op.drop_column("typeset_result", "stroke_color")
    op.drop_column("typeset_result", "text_color")
