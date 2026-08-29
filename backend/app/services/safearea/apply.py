"""Nối vùng an toàn vào bước canh chữ và bước vẽ (E14).

Một chỗ duy nhất trả ra "ô đặt chữ" cho một vùng. Bước canh chữ, ảnh xem thử và file xuất ra
đều gọi hàm này — nếu mỗi nơi tự tính một kiểu thì sớm muộn ảnh xem thử sẽ khác ảnh tải về.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RegionSafeArea
from app.services.safearea.service import vung_an_toan_dung_duoc


def nap_o_dat_chu(
    session: Session,
    region_ids: list[uuid.UUID],
    clean_image_abs: str | None,
) -> dict[uuid.UUID, tuple[float, float, float, float]]:
    """Ô đặt chữ của từng vùng. Vùng không có hình dùng được thì KHÔNG xuất hiện trong dict —
    bên gọi sẽ tự lùi về hành vi M6, chứ không nhận một ô mặc định trông như thật."""
    if not region_ids:
        return {}
    ket: dict[uuid.UUID, tuple[float, float, float, float]] = {}
    for ban in session.scalars(
        select(RegionSafeArea).where(RegionSafeArea.region_id.in_(region_ids))
    ):
        if not vung_an_toan_dung_duoc(ban, clean_image_abs):
            continue
        o = ban.place_rect_json
        if not o or o.get("w", 0) < 1 or o.get("h", 0) < 1:
            continue
        ket[ban.region_id] = (float(o["x"]), float(o["y"]), float(o["w"]), float(o["h"]))
    return ket
