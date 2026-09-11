"""E16 — nạp góc nghiêng của từng vùng để bước căn chữ dùng được.

Theo đúng khuôn `safearea/apply.py` của E14: vùng nào **không** có bằng chứng dùng được thì **không
xuất hiện** trong dict, để bên gọi tự lùi về hành vi cũ — chứ không nhận một góc mặc định trông
như thật.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RegionTextOrientation
from app.models.enums import TextOrientation


def nap_goc_nghieng(
    session: Session, region_ids: list[uuid.UUID],
) -> dict[uuid.UUID, float]:
    """Góc hướng-đường của các vùng ĐƯỢC PHÉP xoay chữ. Khoá thiếu = không xoay.

    ## Vì sao chỉ nhận `rotated_horizontal`

    `horizontal_ltr` thì không có gì để xoay. `vertical_ttb` thì E15 đánh `unavailable` —
    *"nhận ra hướng rồi nhưng KHÔNG dựng được chữ theo hướng đó"* — và dữ liệu thật của lượt 24
    trang cho thấy cả 3 mẫu `vertical_ttb` đều là **dương tính giả** (`?!`, `?!`, `SXXX` trong
    khung hẹp, gắn cờ vì tỉ lệ khung chứ không vì chữ dọc thật). Xoay 90° những vùng đó là làm ảnh
    xấu đi. `unknown` thì theo định nghĩa là chưa đủ bằng chứng.

    ## Vì sao KHÔNG đòi `status = ready`

    Mọi vùng `rotated_horizontal` đều mang `status = needs_review` kèm mã
    `rotated_text_manual_review_only` — E15 cố ý đặt vậy vì *"v1 không tự xoay chữ"*. E16 chính là
    lượt tháo ràng buộc đó, nên đòi `ready` thì sẽ không có vùng nào được phục vụ. Đổi lại, bước
    này KHÔNG xoá cờ rà soát: người dùng vẫn thấy vùng đó cần soi.
    """
    if not region_ids:
        return {}
    ket: dict[uuid.UUID, float] = {}
    for ban in session.scalars(
        select(RegionTextOrientation).where(RegionTextOrientation.region_id.in_(region_ids))
    ):
        if ban.orientation is not TextOrientation.rotated_horizontal:
            continue
        if ban.rotation_degrees is None:
            continue  # nhận ra nghiêng mà không đo được góc ⇒ không đoán
        ket[ban.region_id] = float(ban.rotation_degrees)
    return ket
