"""E49 — ngày hạn mức và mốc reset phải theo giờ Việt Nam, KHÔNG theo giờ máy.

## Bẫy đang canh

Container production chạy **UTC**, máy làm việc là **UTC+7**. Một phép tính "hôm nay" viết bằng
`date.today()` sẽ **xanh ở máy mà sai trên server**: từ 00:00 đến 07:00 giờ Việt Nam, server vẫn
coi là "hôm qua".

Hệ quả thật: người dùng hết hạn mức lúc 23:00, đợi qua nửa đêm, **vẫn bị chặn thêm 7 tiếng nữa**.

## Vì sao các bài dưới đây ÉP `TZ=UTC`

Chạy ở máy UTC+7 thì một bản cài sai **vẫn xanh** — đó đúng là cách lỗi này lọt lên server. Ép
`TZ=UTC` biến bộ test thành bản mô phỏng container, nên sai là ĐỎ ngay tại máy.

`test_may_UTC_van_tinh_dung_ngay_VN` là bài canh chính. Gỡ phần quy đổi múi giờ trong
`services/han_muc.py` ra thì nó phải đỏ.
"""
from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from app.services.han_muc import han_muc_cho, moc_reset_ke_tiep, ngay_han_muc

VN = ZoneInfo("Asia/Ho_Chi_Minh")


@pytest.fixture
def may_chay_utc():
    """Ép máy chạy test sang UTC — mô phỏng container production.

    Không dùng `monkeypatch.setenv` một mình: `time.tzset()` mới thực sự áp `TZ` cho tiến trình.
    """
    cu = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    time.tzset()
    try:
        yield
    finally:
        if cu is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = cu
        time.tzset()


class TestNgayHanMuc:
    def test_may_UTC_van_tinh_dung_ngay_VN(self, may_chay_utc):
        """**Bài canh chính.** 18:00 UTC ngày 25 = 01:00 giờ VN ngày 26.

        Máy đang ở UTC nên `date.today()` sẽ trả ngày **25** — sai. Phải ra **26**.
        """
        moc = datetime(2026, 9, 25, 18, 0, tzinfo=UTC)
        assert ngay_han_muc(moc).isoformat() == "2026-09-26", (
            "tính theo giờ máy (UTC) thay vì giờ Việt Nam"
        )

    def test_ngay_UTC_va_ngay_VN_lech_nhau_o_khung_17h_den_24h(self, may_chay_utc):
        """Khung 17:00–23:59 UTC là lúc hai lịch lệch nhau — đúng chỗ lỗi hay lọt."""
        assert ngay_han_muc(datetime(2026, 9, 25, 16, 59, tzinfo=UTC)).day == 25
        assert ngay_han_muc(datetime(2026, 9, 25, 17, 0, tzinfo=UTC)).day == 26

    def test_ngay_truoc_va_sau_nua_dem_GIO_VN(self, may_chay_utc):
        truoc = datetime(2026, 9, 25, 23, 59, tzinfo=VN)
        sau = datetime(2026, 9, 26, 0, 1, tzinfo=VN)
        assert ngay_han_muc(truoc).isoformat() == "2026-09-25"
        assert ngay_han_muc(sau).isoformat() == "2026-09-26"

    def test_datetime_khong_mui_gio_duoc_coi_la_gio_VN(self, may_chay_utc):
        """Giả định này viết rõ trong docstring của hàm — bài test khoá nó lại.

        Nếu ai đổi sang "coi là UTC" thì mọi mốc trần sẽ lệch 7 tiếng, im lặng.
        """
        assert ngay_han_muc(datetime(2026, 9, 25, 23, 59)).isoformat() == "2026-09-25"


class TestMocReset:
    def test_reset_la_nua_dem_HOM_SAU_gio_VN(self, may_chay_utc):
        moc = moc_reset_ke_tiep(datetime(2026, 9, 25, 10, 0, tzinfo=VN))
        assert (moc.year, moc.month, moc.day) == (2026, 9, 26)
        assert (moc.hour, moc.minute, moc.second) == (0, 0, 0)

    def test_co_phan_bu_07_00(self, may_chay_utc):
        """API trả thẳng giá trị này cho giao diện đếm ngược, nên phần bù phải có sẵn —
        không để nơi gọi tự ghép chuỗi."""
        moc = moc_reset_ke_tiep(datetime(2026, 9, 25, 10, 0, tzinfo=VN))
        assert moc.tzinfo is not None, "thiếu múi giờ — client sẽ đoán sai"
        assert moc.isoformat().endswith("+07:00"), moc.isoformat()

    def test_luc_23h_VN_thi_reset_chi_con_1_tieng(self, may_chay_utc):
        """Mốc reset phải tính từ NGÀY VIỆT NAM. Máy đang ở UTC (lúc đó mới 16:00) nên bản cài
        sai sẽ trả mốc lệch hẳn một ngày."""
        luc = datetime(2026, 9, 25, 23, 0, tzinfo=VN)
        con = moc_reset_ke_tiep(luc) - luc
        assert con.total_seconds() == 3600, f"còn {con} thay vì 1 tiếng"


class TestHanMuc:
    def test_lay_tu_cau_hinh_khong_go_so_cung(self):
        from app.core.config import get_settings

        s = get_settings()
        assert han_muc_cho(co_tai_khoan=False) == s.han_muc_khach_la
        assert han_muc_cho(co_tai_khoan=True) == s.han_muc_co_tai_khoan

    def test_doc_cau_hinh_LUC_GOI_chu_khong_phai_luc_import(self):
        """**Bài canh — bẫy đã cắn thật ngày 25-09.**

        `get_settings` có `lru_cache`, nhưng cache đó xoá được và `tests/conftest.py` xoá nó.
        Module nào chụp `settings = get_settings()` lúc import sẽ trỏ mãi vào đối tượng CŨ.

        Hậu quả đo được: `han_muc_cho(True)` trả **10** trong khi cấu hình app đang là **2** —
        cổng hạn mức vẫn chạy nhưng theo trần sai, và **không bài test nào đỏ**. Đó là kiểu hỏng
        tệ hơn lỗi thường: bộ test mất khả năng phát hiện lỗi thật.

        Gỡ `get_settings()` trong thân `han_muc_cho` ra, quay lại ảnh chụp mức module, thì bài
        này phải đỏ.
        """
        from app.core.config import get_settings

        cu = get_settings()
        get_settings.cache_clear()
        moi = get_settings()
        try:
            assert moi is not cu, "cache_clear không tạo đối tượng mới ⇒ bài test này vô nghĩa"
            moi.han_muc_co_tai_khoan = 4242
            assert han_muc_cho(co_tai_khoan=True) == 4242, (
                "đọc cấu hình từ ảnh chụp lúc import, không phải cấu hình đang dùng"
            )
        finally:
            get_settings.cache_clear()

    def test_tran_IP_phai_LON_HON_tran_cookie(self):
        """Bằng nhau là chặn oan văn phòng/trường học/quán cà phê dùng chung IP."""
        from app.core.config import get_settings

        s = get_settings()
        assert s.han_muc_ip_khach_la > s.han_muc_khach_la, (
            f"trần IP {s.han_muc_ip_khach_la} không lớn hơn trần cookie {s.han_muc_khach_la}"
        )
