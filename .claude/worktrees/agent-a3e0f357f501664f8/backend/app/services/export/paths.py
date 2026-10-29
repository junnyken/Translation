"""Quy ước đường dẫn xuất chapter — module này CỐ Ý không import Pillow.

API cần biết chỗ đặt file để phục vụ tải về, nhưng **không được nạp engine render**
(guardrail kế thừa M2–M7).
"""
from __future__ import annotations

import uuid


def export_relative_dir(project_id: uuid.UUID) -> str:
    """Thư mục chứa mọi file xuất của 1 project. Ổn định theo project để còn dọn file cũ."""
    return f"exports/{project_id}"
