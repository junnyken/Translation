"""F1 — trạng thái căn chữ `font_missing_glyph` + đếm vùng bỏ trống lúc xuất

Revision ID: 0013_f1
Revises: 0012_b1
Create Date: 2026-09-04

## Vì sao cần giá trị enum mới thay vì dùng lại `pending`

`pending` nghĩa là "không có chữ để chèn". Vùng ở đây thì **có chữ**, dịch xong hẳn hoi, nhưng
font không vẽ được một ký tự trong đó nên bong bóng bị bỏ trống. Gộp hai thứ vào một trạng thái
là làm cho một vùng MẤT CHỮ trông y hệt một vùng vốn dĩ trống — người dùng xuất file mà không
biết mình mất gì.

## Bẫy `ALTER TYPE ... ADD VALUE`

Trước PostgreSQL 12 câu lệnh này KHÔNG chạy được trong transaction, mà Alembic mặc định bọc mỗi
migration trong một transaction. Ở đây tự mở kết nối AUTOCOMMIT để chạy, nên không phụ thuộc vào
phiên bản máy chủ.

Ràng buộc đi kèm: giá trị vừa thêm **không dùng được ngay trong cùng transaction đã thêm nó**.
Migration này chỉ thêm giá trị chứ không ghi dữ liệu dùng giá trị đó, nên không vướng.

## Không có `downgrade` cho phần enum

PostgreSQL không cho xoá một giá trị khỏi enum. Muốn lùi thật thì phải dựng lại kiểu và ép kiểu
toàn bộ cột — rủi ro hơn hẳn thứ nó lùi lại. `downgrade` chỉ gỡ cột đếm, và nói thẳng ra ở đây
thay vì im lặng giả vờ đã lùi sạch.
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_f1"
down_revision = "0012_b1"
branch_labels = None
depends_on = None

GIA_TRI_MOI = "font_missing_glyph"


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"ALTER TYPE fit_status ADD VALUE IF NOT EXISTS '{GIA_TRI_MOI}'")

    op.add_column(
        "export_compliance_log",
        sa.Column("font_missing_count", sa.Integer(), nullable=False, server_default="0"),
    )
    # Bỏ server_default sau khi lấp xong dòng cũ: mặc định thuộc về tầng ứng dụng, để trong DB
    # thì lần sau quên truyền giá trị sẽ không ai phát hiện ra.
    op.alter_column("export_compliance_log", "font_missing_count", server_default=None)


def downgrade() -> None:
    op.drop_column("export_compliance_log", "font_missing_count")
    # Giá trị enum `font_missing_glyph` CỐ Ý ở lại — xem ghi chú đầu tệp.
