"""E89 — đổi thời gian giữ kết quả từ 30 phút sang 1 ngày: dời mốc hết hạn ĐÃ ĐÓNG của chapter cũ.

Mốc `project.het_han_luc` được đóng một lần khi chapter xong, bằng `xong + GIU_KET_QUA_PHUT` lúc
đó (mặc định 30). Lịch dọn production đang TẮT nên chưa chapter nào bị xoá, nhưng mọi chapter xong
từ 30 phút trước đều đã có mốc NẰM TRONG QUÁ KHỨ. Bật lịch với `GIU_KET_QUA_PHUT=1440` mà không
dời mốc ⇒ lượt dọn đầu tiên xoá ngay cả chapter mới xong sáng nay — trái ý chủ dự án ("không cần
lưu quá 1 ngày", không phải "xoá hết bây giờ").

Dời đúng phần chênh 1440 − 30 = 1410 phút ⇒ mốc mới = xong + 1 ngày. Chapter chưa có mốc
(đang chạy, hoặc chưa có trang) không đổi.

Revision ID: 0031_e89_giu_mot_ngay
Revises: 0030_e73_codex
"""
from __future__ import annotations

from alembic import op

revision = "0031_e89_giu_mot_ngay"
down_revision = "0030_e73_codex"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE project SET het_han_luc = het_han_luc + interval '1410 minutes' "
        "WHERE het_han_luc IS NOT NULL"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE project SET het_han_luc = het_han_luc - interval '1410 minutes' "
        "WHERE het_han_luc IS NOT NULL"
    )
