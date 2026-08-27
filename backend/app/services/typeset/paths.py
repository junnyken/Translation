"""Quy ước đường dẫn của M6 — module này CỐ Ý không import Pillow.

API cần biết chỗ đặt file preview để phục vụ file, nhưng **không được nạp engine render**
(guardrail kế thừa từ M2–M5). Vì vậy quy ước đường dẫn tách khỏi `preview.py`.
"""
from __future__ import annotations

import uuid


def preview_relative_path(page_id: uuid.UUID) -> str:
    """Đường dẫn ỔN ĐỊNH theo page — chạy lại là ghi đè đúng file cũ, không đẻ file rác."""
    return f"previews/{page_id}/typeset.png"
