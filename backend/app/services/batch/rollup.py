"""Quy tắc gộp trạng thái mẻ và chọn bước kế tiếp cho từng trang (M9).

Tách khỏi bộ điều phối để **test được mà không cần DB** — đây là chỗ dễ sai nhất và cũng là chỗ
mà sai thì hậu quả nặng nhất: báo mẻ "xong" trong khi còn trang chưa chạy.
"""
from __future__ import annotations

from app.models.enums import BatchItemStatus, BatchStatus, PageStatus

#: Trang đã đi hết pipeline — mẻ KHÔNG được chạy lại, tránh xoá mất kết quả đã có.
TRANG_DA_XONG = (PageStatus.typeset_done, PageStatus.ready_for_export)

#: Trang đang ở trạng thái nào thì phải chạy bước nào tiếp theo.
#: Cố ý KHÔNG luôn chạy lại từ đầu: máy trạng thái của M1 không cho `translated -> detecting`,
#: và chạy lại từ đầu sẽ xoá mất công đã làm. Mỗi trang tiếp tục từ đúng chỗ nó đang đứng.
BUOC_TIEP_THEO: dict[PageStatus, str] = {
    PageStatus.queued: "detect",
    PageStatus.detection_failed: "detect",
    PageStatus.detected: "ocr",
    PageStatus.ocr_done: "inpaint",
    PageStatus.inpainted: "translate",
    PageStatus.inpaint_needs_review: "translate",
    PageStatus.translated: "typeset",
}


def buoc_cho_trang(trang_thai: PageStatus) -> str | None:
    """Trả tên bước cần chạy, hoặc None nếu không nên đụng vào trang này.

    `detecting` trả None có chủ đích: trang đang chạy dở, đẩy thêm một việc nữa vào là hai job
    cùng ghi lên một trang. Endpoint `retry-detect` của M2 cũng từ chối đúng như vậy (409).
    """
    if trang_thai in TRANG_DA_XONG:
        return None
    return BUOC_TIEP_THEO.get(trang_thai)


def gop_trang_thai_me(trang_thai_items: list[BatchItemStatus], da_huy: bool = False) -> BatchStatus:
    """Suy trạng thái mẻ TỪ các mục con. Không bao giờ đặt tay.

    Thứ tự xét quan trọng: còn mục nào chưa xong thì mẻ vẫn `running`, **kể cả khi đã có mục
    hỏng** — báo `partial_failed` sớm sẽ khiến người vận hành tưởng mẻ đã dừng.
    """
    if da_huy:
        return BatchStatus.cancelled
    if not trang_thai_items:
        return BatchStatus.completed

    dem = {tt: trang_thai_items.count(tt) for tt in set(trang_thai_items)}
    con_chay = dem.get(BatchItemStatus.pending, 0) + dem.get(BatchItemStatus.running, 0)
    xong = dem.get(BatchItemStatus.completed, 0) + dem.get(BatchItemStatus.skipped, 0)
    hong = dem.get(BatchItemStatus.failed, 0)
    chan = dem.get(BatchItemStatus.blocked_quota, 0)

    if con_chay:
        return BatchStatus.running
    if hong == 0 and chan == 0:
        return BatchStatus.completed
    # Không còn gì chạy nữa, và có mục chưa xong:
    if xong == 0 and chan == 0:
        return BatchStatus.failed          # hỏng sạch
    if chan and hong == 0 and xong == 0:
        return BatchStatus.blocked_quota   # chặn sạch vì quota
    if chan and not hong:
        return BatchStatus.blocked_quota   # có trang xong, phần còn lại kẹt quota
    return BatchStatus.partial_failed
