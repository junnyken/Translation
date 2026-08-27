"""Package M6 — canh chữ dịch vào bubble.

CỐ Ý để trống phần re-export: `fonts`/`layout`/`fitter`/`preview` đều nạp Pillow ở đầu module,
mà tiến trình API **không được nạp engine render** (guardrail kế thừa M2–M5). Chỉ `paths`
là an toàn cho API. Worker import thẳng từng module con.
"""
from app.services.typeset.paths import preview_relative_path

__all__ = ["preview_relative_path"]
