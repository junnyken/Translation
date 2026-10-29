"""E26-C — giữ nguyên chữ cho vùng có thể là TIẾNG ĐỘNG (SFX), không dịch thành từ.

## Vì sao

Đo thật trên trang `en_E12P01` (2026-09-11), bộ dịch cho:

    Clang  -> 'Kêu vang'      Cling -> 'Bám vào'      Clong -> 'tiếng kêu'

`Cling` thành "Bám vào" là dịch **đúng từ điển nhưng sai thể loại**: đó là tiếng kim loại chạm
nhau, không phải động từ "bám". Tiếng động trong truyện tranh Việt thường giữ nguyên hoặc phiên âm,
không dịch nghĩa.

## Vì sao CHỈ dựa vào cờ `possible_sfx` của E12, không tự suy thêm

E12 đã có `RegionRelevance.possible_sfx`. Đo trên dữ liệu thật, nó bắt được **3/6**:

| Chữ | E12 gắn |
|---|---|
| `Clang` · `Cling` · `Clong` | `possible_sfx` ✓ |
| `Shhshh` · `Shklak!` · `CRACK!!\\nKLING!!` | `likely_translatable` ✗ |

Tức nó bỏ sót một nửa. **Nhưng tôi cố ý không thêm luật tự suy** (chữ ngắn / nghiêng / ngoài bong
bóng): một dương tính giả ở đây để **thoại thật không được dịch** — người đọc mất hẳn một câu. Đổi
lại, một SFX bị dịch sai chỉ là một từ lạ mà người đọc vẫn hiểu là tiếng động.

Sai một chiều mất cả câu, sai chiều kia chỉ lạ một từ ⇒ chọn chiều chỉ-lạ-một-từ.

Nên cơ chế này **cải thiện 3/6 ca và không phá ca nào** — không bao giờ tệ hơn hiện trạng. Muốn
bắt nốt 3 ca kia thì phải làm cho `possible_sfx` của E12 nhạy hơn, và đó là việc có bằng chứng
riêng của nó, không nhét vào đây.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RegionQualityAssessment
from app.models.enums import RegionRelevance


def nap_vung_giu_nguyen(session: Session, region_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    """Tập id vùng E12 đánh `possible_sfx` ⇒ giữ nguyên chữ gốc, không gửi đi dịch.

    Vùng chưa được E12 chấm thì **không** nằm trong tập này: thiếu bằng chứng nghĩa là dịch bình
    thường, chứ không phải đoán rồi giữ nguyên.
    """
    if not region_ids:
        return set()
    return set(
        session.scalars(
            select(RegionQualityAssessment.region_id).where(
                RegionQualityAssessment.region_id.in_(region_ids),
                RegionQualityAssessment.relevance == RegionRelevance.possible_sfx,
            )
        )
    )
