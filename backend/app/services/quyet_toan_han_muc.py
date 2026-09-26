"""Quyết toán hạn mức — chốt lượt khi trang xong, hoàn lượt khi hệ thống hỏng.

## Vì sao phần này tách riêng khỏi sổ cái

`so_cai_han_muc.py` biết *cách* ghi sổ. Tệp này biết *khi nào* thì ghi — tức là ánh xạ từ trạng
thái của pipeline sang thao tác sổ cái. Trộn hai thứ vào nhau thì mỗi lần pipeline thêm một
trạng thái là phải sửa vào trong lõi kế toán.

## Chốt ở ĐÂU: đúng một điểm nghẽn

`workers/tasks.bao_ket_thuc_buoc` được gọi ở **cuối mọi bước**, cả thành công lẫn hỏng (17 chỗ).
Gắn vào đó nghĩa là thêm một bước mới vào pipeline cũng không quên quyết toán.

Cách làm hỏng mà tôi cố ý tránh: gắn vào từng chỗ đặt `page.status = ...`. Có 12 chỗ như vậy,
và sót một chỗ là người dùng mất lượt vĩnh viễn mà **không có triệu chứng nào** ngoài con số
hạn mức sai.

## Hoàn khi nào

Theo §1.3(b) đặc tả, chỉ hoàn khi **hệ thống** hỏng:

* worker chết giữa chừng (lượt dọn job mồ côi);
* hết lượt thử lại của mẻ;
* bị chặn vì hết quota nhà cung cấp — lỗi của mình, không phải của người dùng.

**KHÔNG hoàn** khi trang chạy xong rồi người dùng không tải kịp (§2.8), và **không** hoàn khi
một bước hỏng còn thử lại được — trang chưa tới trạng thái cuối thì lượt vẫn đang giữ chỗ, đúng
như nó phải thế.

## Quyết toán hỏng thì KHÔNG được kéo theo việc của trang

Trang đã chạy xong mà ghi sổ hỏng thì trang vẫn phải xong. Nhưng lỗi ghi ở ERROR chứ không nuốt:
nuốt đi thì lượt treo ở `giu_cho` mãi và người dùng mất lượt mà không ai biết vì sao.
"""
from __future__ import annotations

import logging
import uuid

from app.core.db_sync import sync_session
from app.models import Page
from app.models.enums import PageStatus
from app.services.so_cai_han_muc import hoan_theo_trang, tieu_theo_trang

logger = logging.getLogger(__name__)

#: Trang đã đi hết pipeline. Giống `services/batch/rollup.TRANG_DA_XONG` — cố ý nhắc lại ở đây
#: thay vì import, vì ý nghĩa khác nhau: bên kia là "đừng chạy lại", bên này là "tiêu lượt".
#: Gộp lại thì một ngày nào đó đổi một ý sẽ âm thầm đổi luôn ý kia.
TRANG_DA_XONG = (PageStatus.typeset_done, PageStatus.ready_for_export)


def quyet_toan_khi_ket_thuc_buoc(page_id: uuid.UUID | None) -> int:
    """Gọi sau MỖI bước của pipeline. Chỉ làm gì khi trang đã tới đích.

    Trả về số dòng vừa chốt (`0` là bình thường: trang chưa xong, hoặc đã chốt ở lượt trước).
    Idempotent — bước cuối chạy lại không tiêu thêm lượt nào.
    """
    if page_id is None:
        return 0
    try:
        with sync_session() as session:
            page = session.get(Page, page_id)
            if page is None or page.status not in TRANG_DA_XONG:
                return 0
            dem = tieu_theo_trang(session, page_id)
            if dem:
                session.commit()
                logger.info("hạn mức: chốt %d lượt cho trang %s (%s)",
                            dem, page_id, page.status.value)
            return dem
    except Exception:  # noqa: BLE001 — xem docstring module
        logger.exception(
            "hạn mức: KHÔNG chốt được lượt cho trang %s. Lượt đang treo ở `giu_cho`; "
            "người dùng sẽ thấy hạn mức hụt cho tới khi có người xử lý.", page_id
        )
        return 0


def hoan_vi_he_thong_hong(session, page_id: uuid.UUID | None, ly_do: str) -> int:
    """Hoàn lượt của một trang vì lỗi HỆ THỐNG. Dùng phiên của nơi gọi, KHÔNG tự commit.

    Nơi gọi (lượt dọn job mồ côi, bộ điều phối mẻ) đã ở trong một giao dịch của riêng nó; tự mở
    phiên thứ hai ở đây sẽ tạo ra hai giao dịch cùng ghi lên một bảng và chờ khoá lẫn nhau.

    Dòng đã `da_tieu` không bị đụng tới — trang chạy xong rồi thì lượt đã tiêu đúng.
    """
    if page_id is None:
        return 0
    dem = hoan_theo_trang(session, page_id, ly_do)
    if dem:
        logger.warning("hạn mức: hoàn %d lượt cho trang %s — %s", dem, page_id, ly_do)
    return dem
