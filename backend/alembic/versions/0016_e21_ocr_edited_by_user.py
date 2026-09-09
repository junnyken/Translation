"""E21 — cho phép người dùng tự gõ đè `raw_text` (chữ OCR đọc được) tại màn sửa tay (M7)

Revision ID: 0016_e21
Revises: 0015_e19b
Create Date: 2026-09-09

`REPORT_E20a.md`/`REPORT_E20b.md` đo được: chữ mảnh trên nền tranh phức tạp không path OCR nào
(PaddleOCR + 4 kiểu tiền xử lý, 4 chế độ Tesseract) tự sửa được. E21 thêm lối thoát tay: người
dùng tự gõ lại đúng chữ gốc khi OCR đọc sai — cần cột đánh dấu để phân biệt "máy đọc" và "người
gõ", đúng mẫu đã có sẵn với `TranslationResult.edited_by_user`/`TypesetResult.edited_by_user`.

`server_default='false'` vì `ocr_result` đã có dữ liệu thật — thêm cột NOT NULL không mặc định ở
tầng CSDL sẽ hỏng ngay lúc migrate (đúng bài học đã ghi ở 0014_e19).
"""
from alembic import op
import sqlalchemy as sa

revision = "0016_e21"
down_revision = "0015_e19b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ocr_result",
        sa.Column("edited_by_user", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("ocr_result", "edited_by_user")
