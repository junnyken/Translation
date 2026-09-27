"""E57 — bảng cho một lượt "đọc thử ảnh để đoán ngôn ngữ".

Xảy ra **trước khi** có chapter nào (chính vì chưa biết `source_lang` để tạo chapter), nên không
dùng được `job`: `job.page_id` là NOT NULL có khoá ngoại tới `page`. Nới ràng buộc đó chỉ để tiết
kiệm một bảng là làm yếu thứ đang bảo vệ cả pipeline.

Dùng LẠI hai enum đã có (`job_status`, `source_lang`) ⇒ `create_type=False`. Tạo lại sẽ ném
"type already exists"; và thêm giá trị vào enum đang chạy là một lượt `ALTER TYPE` trên production
mà `CLAUDE.md` đã cảnh báo riêng.

`ngon_ngu` **cho phép NULL** có chủ đích: "chưa kết luận" là một kết quả hợp lệ (ảnh không chữ, quá
ít chữ, hệ chữ không hỗ trợ). Đặt NOT NULL ở đây sẽ buộc chọn bừa một trong ba giá trị.

Revision ID: 0023_e57
Revises: 0022_e50
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0023_e57"
down_revision = "0022_e50"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "yeu_cau_nhan_dang_ngon_ngu",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "chu_so_huu_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("nguoi_dung.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("chu_khach", sa.String(length=128), nullable=True),
        sa.Column("duong_anh", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "trang_thai",
            postgresql.ENUM(
                "queued", "running", "done", "failed", name="job_status", create_type=False
            ),
            nullable=False,
        ),
        sa.Column(
            "ngon_ngu",
            postgresql.ENUM("ja", "zh", "en", name="source_lang", create_type=False),
            nullable=True,
        ),
        sa.Column("ly_do", sa.String(length=120), nullable=True),
        sa.Column("bang_chung", postgresql.JSONB(), nullable=True),
        sa.Column("loi", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_yeu_cau_nhan_dang_chu_so_huu",
        "yeu_cau_nhan_dang_ngon_ngu",
        ["chu_so_huu_id"],
    )
    op.create_index(
        "ix_yeu_cau_nhan_dang_chu_khach", "yeu_cau_nhan_dang_ngon_ngu", ["chu_khach"]
    )
    # Phép dọn định kỳ luôn hỏi "lượt nào cũ rồi" — quét toàn bảng mỗi lượt là việc thừa.
    op.create_index(
        "ix_yeu_cau_nhan_dang_created_at", "yeu_cau_nhan_dang_ngon_ngu", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_yeu_cau_nhan_dang_created_at", table_name="yeu_cau_nhan_dang_ngon_ngu")
    op.drop_index("ix_yeu_cau_nhan_dang_chu_khach", table_name="yeu_cau_nhan_dang_ngon_ngu")
    op.drop_index("ix_yeu_cau_nhan_dang_chu_so_huu", table_name="yeu_cau_nhan_dang_ngon_ngu")
    op.drop_table("yeu_cau_nhan_dang_ngon_ngu")
    # KHÔNG `DROP TYPE job_status`/`source_lang`: hai enum này có TỪ TRƯỚC migration này và còn
    # nhiều bảng khác đang dùng. Xoá chúng ở đây là kéo sập `job`, `project`, `glossary_entry`.
    # (Luật "downgrade phải DROP TYPE tường minh" ở CLAUDE.md áp cho enum do CHÍNH migration tạo ra.)
