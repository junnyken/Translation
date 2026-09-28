"""E65 — hệ số phóng ảnh RA của mỗi trang.

## Vì sao phải LƯU, không tính lại ở chỗ vẽ

Hệ số này do bước **căn chữ** quyết định: nó fit chữ vào khung đã nhân lên `k`, nên `font_size`
ghi trong `typeset_result` là pixel **của ảnh đã phóng**. Bước **vẽ** phải phóng ảnh đúng `k` đó,
không thì cỡ chữ và khung lệch nhau.

Tính lại ở cả hai nơi bằng "cùng một công thức" là đúng cái bẫy `feedback_tinh_nang_chet_vi_hai_
dau_khong_gap`: một bên đổi, bên kia không, và chẳng gì đỏ cả. Một cột là một nguồn sự thật.

`server_default="1.0"` + NOT NULL: mọi trang CŨ nhận đúng 1.0 — nghĩa là "không phóng", hành vi y
hệt trước E65. Không có trang nào phải chạy lại.

Revision ID: 0024_e65
Revises: 0023_e57
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0024_e65"
down_revision = "0023_e57"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "page",
        sa.Column(
            "he_so_ve",
            sa.Float(),
            nullable=False,
            server_default="1.0",
            comment="E65: hệ số phóng ảnh RA (1.0 = không phóng). Cỡ chữ trong typeset_result "
                    "là pixel của ảnh ĐÃ phóng theo hệ số này.",
        ),
    )


def downgrade() -> None:
    op.drop_column("page", "he_so_ve")
