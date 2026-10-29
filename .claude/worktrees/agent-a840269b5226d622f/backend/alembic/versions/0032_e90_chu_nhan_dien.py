"""E90 — chữ đọc được ngay lúc nhận diện (Gemini): cột `text_region.chu_nhan_dien` + giá trị
`ai_gemini` cho enum `ocr_engine`.

Revision ID: 0032_e90_chu_nhan_dien
Revises: 0031_e89_giu_mot_ngay
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0032_e90_chu_nhan_dien"
down_revision = "0031_e89_giu_mot_ngay"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("text_region", sa.Column("chu_nhan_dien", sa.Text(), nullable=True))
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE ocr_engine ADD VALUE IF NOT EXISTS 'ai_gemini'")


def downgrade() -> None:
    # Không gỡ giá trị enum (Postgres không có DROP VALUE) — như 0026/0030.
    op.drop_column("text_region", "chu_nhan_dien")
