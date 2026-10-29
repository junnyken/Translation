"""E19 — chế độ pipeline theo chapter + `job.started_at`

Revision ID: 0014_e19
Revises: 0013_f1
Create Date: 2026-09-05

## Hai chỗ sửa tay so với bản autogenerate

1. Alembic lại đòi `op.drop_index('ix_artifact_blob_path_prefix')`. **Đã bỏ** — index đó tạo ở
   0010_p3e với `text_pattern_ops`, alembic không biểu diễn được opclass nên tưởng thừa. Đây là
   lần thứ hai nó đòi (lần đầu ở 0012_b1); nghe theo là mất index quét tiền tố của kho hiện vật.
2. Enum Postgres **không** tự mất khi drop cột, nên downgrade phải `DROP TYPE` tường minh
   (quy ước chốt từ 0001).

## Vì sao `che_do_pipeline` có `server_default`

Bảng `project` đang có dữ liệu thật. Thêm cột NOT NULL mà không có mặc định ở tầng CSDL sẽ
hỏng ngay lúc migrate. `day_du` giữ nguyên hành vi cũ cho mọi chapter đã có.
"""
from alembic import op
import sqlalchemy as sa

revision = "0014_e19"
down_revision = "0013_f1"
branch_labels = None
depends_on = None

TEN_ENUM = "che_pipeline"
GIA_TRI = ("day_du", "chi_chu")


def upgrade() -> None:
    che = sa.Enum(*GIA_TRI, name=TEN_ENUM)
    che.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "project",
        sa.Column("che_do_pipeline", che, server_default="day_du", nullable=False),
    )
    op.add_column("job", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("job", "started_at")
    op.drop_column("project", "che_do_pipeline")
    sa.Enum(name=TEN_ENUM).drop(op.get_bind(), checkfirst=True)
