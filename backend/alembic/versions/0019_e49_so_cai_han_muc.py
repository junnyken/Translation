"""E49 — sổ cái hạn mức sử dụng.

## Ba chỗ đã sửa tay so với bản `--autogenerate` sinh ra

**1. Bỏ `op.drop_index('ix_artifact_blob_path_prefix')`.** Autogenerate tự ý xoá một chỉ mục của
bảng `artifact_blob` — bảng lưu trữ, **không liên quan gì** tới thay đổi này. Nó bị hiểu nhầm là
"thừa" vì không mô tả được trong model. Áp nguyên bản sinh ra là **mất chỉ mục của kho lưu trữ**.

**2. Thêm `DROP TYPE` tường minh ở `downgrade`.** Trên Postgres, kiểu enum **KHÔNG tự mất** khi
xoá bảng. Thiếu bước này thì lần `upgrade` sau đổ với lỗi "type already exists" — dự án đã ghi
đúng bẫy này trong `CLAUDE.md`.

**3. Đổi mã bản từ chuỗi băm sang `0019_e49`** cho khớp quy ước các bản trước.
"""
from alembic import op
import sqlalchemy as sa

revision = "0019_e49"
down_revision = "0018_e33"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "so_cai_han_muc",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("khoa_idempotency", sa.String(length=128), nullable=False),
        sa.Column(
            "loai_chu_the",
            sa.Enum("nguoi_dung", "khach_cookie", "khach_ip", name="loai_chu_the"),
            nullable=False,
        ),
        sa.Column("chu_the", sa.String(length=128), nullable=False),
        sa.Column("ngay_han_muc", sa.Date(), nullable=False),
        sa.Column("so_trang", sa.Integer(), nullable=False),
        sa.Column(
            "trang_thai",
            sa.Enum("giu_cho", "da_tieu", "da_hoan", name="trang_thai_han_muc"),
            nullable=False,
        ),
        sa.Column("ly_do_hoan", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("khoa_idempotency", name="uq_so_cai_han_muc_khoa"),
    )
    op.create_index(
        "ix_so_cai_han_muc_tra_cuu",
        "so_cai_han_muc",
        ["loai_chu_the", "chu_the", "ngay_han_muc", "trang_thai"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_so_cai_han_muc_tra_cuu", table_name="so_cai_han_muc")
    op.drop_table("so_cai_han_muc")
    # Enum KHÔNG tự mất khi drop table — xem docstring đầu tệp.
    op.execute("DROP TYPE IF EXISTS trang_thai_han_muc")
    op.execute("DROP TYPE IF EXISTS loai_chu_the")
