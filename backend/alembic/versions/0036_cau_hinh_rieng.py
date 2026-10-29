"""Private translation context for production desktop requests.

Revision ID: 0036_cau_hinh_rieng
Revises: 0035_don_nap_nhat_ky
"""
import sqlalchemy as sa
from alembic import op

revision = "0036_cau_hinh_rieng"
down_revision = "0035_don_nap_nhat_ky"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("project", sa.Column("cau_hinh_rieng", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column("project", "cau_hinh_rieng")
