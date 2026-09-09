"""E22 (thu hẹp theo audit) — heartbeat + phân loại lỗi có bằng chứng cho `job`

Revision ID: 0017_e22
Revises: 0016_e21
Create Date: 2026-09-09

Audit trước khi build (xem `docs/REPORT_E22.md`) tìm ra `app/workers/hoi_phuc.py` đã xử lý đúng
trường hợp "worker chết giữa chừng" cho topology hiện tại (đúng một worker, `--pool=solo`) — nên
KHÔNG cần bảng `JobAttempt`/capacity-gate như bản nháp E22 gốc đề xuất. Chỉ còn hai khoảng trống
thật, có bằng chứng: (1) cửa sổ ngắn giữa lúc worker chết và lúc quét mồ côi chạy xong, DB vẫn ghi
`running` dù đã chết; (2) lý do job hỏng vì worker chết luôn là một câu cứng, không phân biệt
được "nghi ngờ hết bộ nhớ" khỏi các nguyên nhân khác. Ba cột dưới đây chỉ phục vụ đúng hai việc
đó — không thêm cột lease/worker_identity vì chưa ai đọc/ghi tới (audit: chỉ có 1 nơi ghi
`error_class`/`exit_signal`, chỉ có 1 nơi đọc `heartbeat_at`).

`server_default` không cần cho cả 3 cột vì đều `nullable=True` và không có ràng buộc NOT NULL —
khác bài học 0014_e19/0016_e21 (những cột đó là NOT NULL nên bắt buộc phải có default khi bảng đã
có dữ liệu).
"""
from alembic import op
import sqlalchemy as sa

revision = "0017_e22"
down_revision = "0016_e21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("job", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("job", sa.Column("error_class", sa.String(length=64), nullable=True))
    op.add_column("job", sa.Column("exit_signal", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("job", "exit_signal")
    op.drop_column("job", "error_class")
    op.drop_column("job", "heartbeat_at")
