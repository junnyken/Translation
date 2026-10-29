"""E19 — cho phép người dùng tiện ích chọn engine dịch mỗi trang (miễn phí/Gemini)

Revision ID: 0015_e19b
Revises: 0014_e19
Create Date: 2026-09-08

`page.translate_engine_override` NULL = dùng mặc định hệ thống (`google_fast`, hành vi cũ,
mọi trang đã có). Chỉ chế độ `chi_chu` (E19) đọc cột này — pipeline đầy đủ bỏ qua, luôn `NULL`.

Dùng LẠI enum Postgres `translation_engine` đã tạo ở 0003_m9 (`create_type=False`) — tạo lại là
trùng tên, và downgrade ở đây KHÔNG được drop type đó vì `translation_result`/`batch_run` vẫn
đang dùng (đúng quy ước đã ghi ở 0003_m9/0014_e19).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0015_e19b"
down_revision = "0014_e19"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "page",
        sa.Column(
            "translate_engine_override",
            postgresql.ENUM("google_fast", "llm_context", name="translation_engine", create_type=False),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("page", "translate_engine_override")
    # `translation_engine` KHÔNG drop — translation_result (M5) và batch_run (M9) vẫn đang dùng.
