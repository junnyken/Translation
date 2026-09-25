"""Hạn mức sử dụng — phần tính NGÀY và MỐC RESET.

## Vì sao tách thành module riêng

Đây là chỗ dễ sai nhất của cả tính năng, và cái sai thì **không lộ ra ở máy làm việc**.

Container production chạy giờ **UTC**. Máy làm việc là **UTC+7**. Một phép tính "hôm nay" viết
bằng `date.today()` hay `datetime.now().date()` sẽ:

* ở máy làm việc: đúng, vì giờ máy đã là UTC+7;
* trên server: **lệch 7 tiếng** — từ 00:00 đến 07:00 giờ Việt Nam, server vẫn coi là "hôm qua".

Hệ quả thật: người dùng hết hạn mức lúc 23:00, đợi qua nửa đêm, và **vẫn bị chặn thêm 7 tiếng
nữa**. Hoặc ngược lại, hạn mức reset sớm 7 tiếng và ai biết mẹo thì dùng gấp đôi.

Dự án đã có tiền lệ đúng loại này: bài test gom theo "giờ trong ngày" **xanh ở máy mà đỏ trên
server**. Vì vậy ở đây **không hàm nào đọc giờ máy** — mọi thứ đi qua múi giờ tường minh, và
bài test bắt buộc phải ép `TZ` chứ không dựa vào máy chạy test.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.config import get_settings

settings = get_settings()


def _mui_gio() -> ZoneInfo:
    return ZoneInfo(settings.mui_gio_han_muc)


def bay_gio() -> datetime:
    """Thời điểm hiện tại, **có múi giờ**, theo múi giờ hạn mức.

    Cố ý KHÔNG trả `datetime.now()` trần: một `datetime` không mang múi giờ đi qua vài lớp hàm
    rồi bị đem so sánh với một `datetime` có múi giờ sẽ ném `TypeError` — hoặc tệ hơn, được so
    sánh với một giá trị khác múi giờ mà không ai biết.
    """
    return datetime.now(tz=_mui_gio())


def ngay_han_muc(luc: datetime | None = None) -> date:
    """Ngày lịch dùng để gom hạn mức, tính theo múi giờ hạn mức.

    `luc` để `None` nghĩa là "bây giờ". Truyền `luc` vào được là để **bài test ép giờ tường
    minh** — đó là cách duy nhất kiểm được mốc nửa đêm mà không phụ thuộc máy chạy test.

    Nhận `datetime` **có hoặc không có** múi giờ:

    * có múi giờ ⇒ quy đổi về múi giờ hạn mức rồi lấy ngày;
    * không có múi giờ ⇒ **coi là đã ở múi giờ hạn mức** (không phải UTC). Giả định này viết ra
      đây để ai gọi cũng thấy; truyền vào một mốc UTC trần là đang tự đặt bẫy cho chính mình.
    """
    moc = luc if luc is not None else bay_gio()
    if moc.tzinfo is None:
        moc = moc.replace(tzinfo=_mui_gio())
    return moc.astimezone(_mui_gio()).date()


def moc_reset_ke_tiep(luc: datetime | None = None) -> datetime:
    """Thời điểm hạn mức được làm mới lần kế tiếp — 00:00 của NGÀY HÔM SAU, theo múi giờ hạn mức.

    Trả về `datetime` **có múi giờ**, để nơi gọi đem ra API là có sẵn phần bù `+07:00` chứ không
    phải tự ghép chuỗi. Giao diện đếm ngược lấy thẳng giá trị này làm nguồn sự thật, không tự
    tính giờ ở phía trình duyệt.
    """
    hom_nay = ngay_han_muc(luc)
    return datetime.combine(hom_nay + timedelta(days=1), datetime.min.time(), tzinfo=_mui_gio())


def han_muc_cho(co_tai_khoan: bool) -> int:
    """Số trang mỗi ngày. Tách ra đây để **không nơi nào gõ số cứng**.

    Đổi chính sách thì đổi biến môi trường, không phải deploy lại mã.
    """
    return settings.han_muc_co_tai_khoan if co_tai_khoan else settings.han_muc_khach_la
