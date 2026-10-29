"""P3e — hiện vật nhị phân lưu trong CSDL (VibeHost không có volume bền)

Revision ID: 0010_p3e
Revises: 0009_e15b
Create Date: 2026-08-31
"""
from alembic import op
import sqlalchemy as sa

revision = '0010_p3e'
down_revision = '0009_e15b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'artifact_blob',
        sa.Column('path', sa.Text(), nullable=False),
        sa.Column('data', sa.LargeBinary(), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False),
        sa.PrimaryKeyConstraint('path'),
    )
    # PNG/ZIP ĐÃ nén sẵn. Để mặc định (EXTENDED) thì Postgres còn thử nén lại lần nữa: tốn CPU
    # mỗi lượt ghi mà gần như không giảm được byte nào. EXTERNAL = vẫn đẩy ra TOAST (bắt buộc,
    # vì hàng vượt ~2KB) nhưng bỏ bước nén vô ích.
    op.execute("ALTER TABLE artifact_blob ALTER COLUMN data SET STORAGE EXTERNAL")
    # Liệt kê/dọn theo tiền tố (`exports/<project_id>/…`) là truy vấn nóng nhất sau khoá chính.
    # `text_pattern_ops` để `LIKE 'tiền tố/%'` dùng được index — collation mặc định thì không.
    op.execute(
        "CREATE INDEX ix_artifact_blob_path_prefix "
        "ON artifact_blob (path text_pattern_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_artifact_blob_path_prefix")
    op.drop_table('artifact_blob')
