"""E51b — `/healthz` phải nói đủ để đo RỦI RO SỐ MỘT của hạn mức bằng một lượt curl.

## Rủi ro đang nói tới, và vì sao bộ test không bắt được

Chốt hạn mức theo IP dùng `request.client.host`. Sau một reverse proxy, giá trị đó rất có thể là
IP của **proxy** ⇒ **mọi khách lạ chung một chốt IP** ⇒ khách thứ 26 trong ngày bị chặn oan.

Bàn thử **không có proxy**, nên không bài test nào tái hiện được. Cách duy nhất là làm cho bản
chạy thật **tự nói ra**, và đó là việc của khối chẩn đoán này.

## Bài canh nặng nhất

`test_KHONG_tra_IP_tho` — endpoint này công khai. Trả IP thô là rò rỉ dữ liệu cá nhân của chính
người đang gọi, mà câu hỏi thật chỉ cần một bit: IP máy chủ thấy có phải địa chỉ nội bộ không.
"""
from __future__ import annotations

import pytest

from app.core.config import get_settings

IP_TEST = "127.0.0.1"


@pytest.fixture
def st():
    return get_settings()


class TestKhoiChanDoan:
    async def test_healthz_co_khoi_nhan_dien_khach(self, client_chua_dang_nhap):
        """`/healthz` không đòi đăng nhập — đúng thứ người vận hành curl được ngay sau deploy."""
        r = await client_chua_dang_nhap.get("/healthz")
        assert r.status_code == 200, r.text
        assert "nhan_dien_khach" in r.json(), r.json()

    async def test_KHONG_tra_IP_tho(self, client_chua_dang_nhap):
        """**Bài canh.** Endpoint công khai không được in IP của người gọi ra."""
        khoi = (await client_chua_dang_nhap.get("/healthz")).json()["nhan_dien_khach"]

        nhu_chuoi = str(khoi)
        assert IP_TEST not in nhu_chuoi, f"IP thô lọt ra: {khoi}"
        assert not any(
            isinstance(v, str) and v.count(".") >= 3 for v in khoi.values()
        ), f"có giá trị trông như một địa chỉ IP: {khoi}"

    async def test_noi_duoc_IP_may_chu_thay_la_noi_bo_hay_khong(self, client_chua_dang_nhap):
        """Đây là bit quyết định: `true` ⇒ đó là proxy, không phải người dùng ⇒ chốt IP vô dụng."""
        khoi = (await client_chua_dang_nhap.get("/healthz")).json()["nhan_dien_khach"]

        assert khoi["co_ip"] is True
        # Bàn thử gọi qua ASGI nên IP là loopback ⇒ phải báo ĐÚNG là nội bộ. Bài này cũng chứng
        # minh phép phân loại chạy thật, chứ không phải luôn trả None.
        assert khoi["ip_la_noi_bo"] is True, khoi

    async def test_bao_dung_trang_thai_header_proxy(self, client_chua_dang_nhap):
        khoi = (await client_chua_dang_nhap.get("/healthz")).json()["nhan_dien_khach"]
        assert khoi["co_x_forwarded_for"] is False
        assert khoi["so_muc_x_forwarded_for"] == 0

    async def test_dem_dung_so_muc_x_forwarded_for(self, client_chua_dang_nhap):
        """Số mục cho biết có MẤY lớp proxy — cần biết trước khi quyết lấy mục trái nhất."""
        r = await client_chua_dang_nhap.get(
            "/healthz", headers={"x-forwarded-for": "203.0.113.9, 10.0.0.1, 10.0.0.2"}
        )
        khoi = r.json()["nhan_dien_khach"]
        assert khoi["co_x_forwarded_for"] is True
        assert khoi["so_muc_x_forwarded_for"] == 3

    async def test_bao_dung_4_co_cau_hinh(self, client_chua_dang_nhap, st, monkeypatch):
        """Bốn cờ này quyết định tính năng chạy đúng hay không, mà `list_env` của nền tảng chỉ trả
        TÊN biến chứ không trả giá trị — nên bản chạy thật phải tự nói ra."""
        monkeypatch.setattr(st, "muoi_bam_khach", "co-muoi-roi")
        monkeypatch.setattr(st, "tin_header_proxy", True)
        monkeypatch.setattr(st, "bat_lich_don_tep", True)
        monkeypatch.setattr(st, "tu_xoa_cho_tai_khoan", False)

        khoi = (await client_chua_dang_nhap.get("/healthz")).json()["nhan_dien_khach"]
        assert khoi["muoi_bam_khach_da_dat"] is True
        assert khoi["tin_header_proxy"] is True
        assert khoi["bat_lich_don_tep"] is True
        assert khoi["tu_xoa_cho_tai_khoan"] is False

    async def test_muoi_rong_bao_dung_la_CHUA_DAT(self, client_chua_dang_nhap, st, monkeypatch):
        """Muối rỗng ⇒ băm gần như vô nghĩa. Báo sai chỗ này là che mất một lỗ bảo mật thật."""
        monkeypatch.setattr(st, "muoi_bam_khach", "")
        khoi = (await client_chua_dang_nhap.get("/healthz")).json()["nhan_dien_khach"]
        assert khoi["muoi_bam_khach_da_dat"] is False
