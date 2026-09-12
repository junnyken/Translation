"""Nối vùng an toàn vào bước canh chữ và bước vẽ (E14).

Một chỗ duy nhất trả ra "ô đặt chữ" cho một vùng. Bước canh chữ, ảnh xem thử và file xuất ra
đều gọi hàm này — nếu mỗi nơi tự tính một kiểu thì sớm muộn ảnh xem thử sẽ khác ảnh tải về.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RegionSafeArea, TextRegion
from app.services.safearea.khong_de_len_nhau import cat_o_dat_chu
from app.services.safearea.service import vung_an_toan_dung_duoc


def nap_o_dat_chu(
    session: Session,
    region_ids: list[uuid.UUID],
    van_tay_clean: str | None,
) -> dict[uuid.UUID, tuple[float, float, float, float]]:
    """Ô đặt chữ của từng vùng. Vùng không có hình dùng được thì KHÔNG xuất hiện trong dict —
    bên gọi sẽ tự lùi về hành vi M6, chứ không nhận một ô mặc định trông như thật.

    P3c: tham số thứ ba là **vân tay ảnh clean** (`van_tay_hien_vat()`), không còn là đường dẫn
    tuyệt đối — bên gọi tính một lần rồi truyền vào.
    """
    if not region_ids:
        return {}
    ket: dict[uuid.UUID, tuple[float, float, float, float]] = {}
    for ban in session.scalars(
        select(RegionSafeArea).where(RegionSafeArea.region_id.in_(region_ids))
    ):
        if not vung_an_toan_dung_duoc(ban, van_tay_clean):
            continue
        o = ban.place_rect_json
        if not o or o.get("w", 0) < 1 or o.get("h", 0) < 1:
            continue
        ket[ban.region_id] = (float(o["x"]), float(o["y"]), float(o["w"]), float(o["h"]))

    # E27 — cắt lại để ô đặt chữ của vùng này không trùm lên KHUNG CHỮ của vùng khác.
    #
    # A1 nới ô tới khi chạm nét vẽ, nhưng trên nền phẳng (trời, tường trắng) không có nét nào cản
    # nên nó nới tràn, và nó KHÔNG coi vùng chữ khác là vật cản. Đo thật trên `0d47b661`: hai ô
    # `497x156` và `636x130` chồng nhau, mỗi ô trùm cả khung chữ của vùng kia ⇒ chữ vẽ đè nhau.
    #
    # Vá ở ĐÂY vì docstring trên đã chốt: đây là **một chỗ duy nhất** trả ra ô đặt chữ, mọi đường
    # (canh chữ, ảnh xem thử, file xuất) đều đi qua. Vá chỗ khác là sớm muộn ba đường lệch nhau.
    #
    # Phải lấy khung chữ của **MỌI vùng cùng trang**, không chỉ `region_ids` được hỏi: bên gọi có
    # thể chỉ hỏi một vùng (M7 sửa tay), mà vật cản thì vẫn là toàn bộ vùng anh em trên trang đó.
    if not ket:
        return ket
    trang_ids = set(
        session.scalars(
            select(TextRegion.page_id).where(TextRegion.id.in_(list(ket.keys()))).distinct()
        )
    )
    khung = {
        r.id: (float(r.bbox_x), float(r.bbox_y), float(r.bbox_w), float(r.bbox_h))
        for r in session.scalars(select(TextRegion).where(TextRegion.page_id.in_(trang_ids)))
    }
    return cat_o_dat_chu(ket, khung)
