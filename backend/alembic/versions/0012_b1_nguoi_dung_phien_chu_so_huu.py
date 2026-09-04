"""B1 — tài khoản thật, phiên đăng nhập, chapter có chủ

Revision ID: 0012_b1
Revises: 0011_e17
Create Date: 2026-09-04

## Hai chỗ đã sửa tay so với bản autogenerate

1. Alembic đòi `op.drop_index('ix_artifact_blob_path_prefix')`. **Đã bỏ.** Index đó tạo ở
   0010_p3e với `text_pattern_ops` — alembic không biểu diễn được opclass nên tưởng nó thừa.
   Nghe theo là mất index quét tiền tố của kho hiện vật, và `list_prefix` chuyển sang quét
   toàn bảng bytea.
2. `op.drop_constraint(None, ...)` ở downgrade — thiếu tên thì nổ lúc chạy. Đã đặt tên tường minh.

## Vì sao `chu_so_huu_id` cho phép NULL

Chapter tạo trước bản này không có chủ. Gán bừa cho một tài khoản là đoán mò, mà chưa có tài
khoản nào tồn tại lúc migration chạy nên cũng không gán được. NULL = "chưa có chủ", xử lý ở
tầng ứng dụng (quản trị nhận về).
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_b1"
down_revision = "0011_e17"
branch_labels = None
depends_on = None

FK_CHU_SO_HUU = "fk_project_chu_so_huu_id_nguoi_dung"


def upgrade() -> None:
    op.create_table(
        "nguoi_dung",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("ten_hien", sa.String(length=120), nullable=False),
        sa.Column("mat_khau_bam", sa.String(length=255), nullable=False),
        sa.Column("dang_hoat_dong", sa.Boolean(), nullable=False),
        sa.Column("la_quan_tri", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_nguoi_dung_email", "nguoi_dung", ["email"], unique=True)

    op.create_table(
        "phien",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("nguoi_dung_id", sa.UUID(), nullable=False),
        sa.Column("ma_bam", sa.String(length=64), nullable=False),
        sa.Column("het_han", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dung_lan_cuoi", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["nguoi_dung_id"], ["nguoi_dung.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_phien_ma_bam", "phien", ["ma_bam"], unique=True)
    op.create_index("ix_phien_nguoi_dung", "phien", ["nguoi_dung_id"], unique=False)

    op.add_column("project", sa.Column("chu_so_huu_id", sa.UUID(), nullable=True))
    op.create_index("ix_project_chu_so_huu_id", "project", ["chu_so_huu_id"], unique=False)
    op.create_foreign_key(
        FK_CHU_SO_HUU, "project", "nguoi_dung", ["chu_so_huu_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint(FK_CHU_SO_HUU, "project", type_="foreignkey")
    op.drop_index("ix_project_chu_so_huu_id", table_name="project")
    op.drop_column("project", "chu_so_huu_id")
    op.drop_index("ix_phien_nguoi_dung", table_name="phien")
    op.drop_index("ix_phien_ma_bam", table_name="phien")
    op.drop_table("phien")
    op.drop_index("ix_nguoi_dung_email", table_name="nguoi_dung")
    op.drop_table("nguoi_dung")
