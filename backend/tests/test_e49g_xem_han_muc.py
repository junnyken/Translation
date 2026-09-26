"""E49g — `GET /han-muc`: nói rõ còn bao nhiêu và bao giờ có lại.

## Vì sao endpoint này KHÔNG phải tiện nghi

Đặc tả §1.3(c): thiếu nó thì cách duy nhất để biết hạn mức là **bị từ chối**. Và "hiện 0/6 mà
không nói bao giờ có lại" chính là thứ làm người dùng tưởng hệ thống hỏng rồi bấm lại liên tục —
vừa vô ích cho họ, vừa tốn tài nguyên của mình.

## Bài canh nặng nhất

`test_con_lai_lay_NHO_NHAT_giua_cac_chot` — khách ở văn phòng đã chạm trần IP thì `con_lai` phải
nói đúng `0`, dù chốt cookie của họ còn nguyên. Trả số lớn hơn thực tế là **mời người ta thả 6
trang lên rồi nhận 429** — tệ hơn hẳn việc nói thật ngay từ đầu.
"""
from __future__ import annotations

import io

import pytest
from PIL import Image

from app.core.config import get_settings
from app.models.enums import LoaiChuThe, SourceLang


def _anh() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), "white").save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def st():
    return get_settings()


@pytest.fixture
def cookie_chay_duoc_tren_http(st, monkeypatch):
    monkeypatch.setattr(st, "cookie_khach_secure", False)


async def _khach_gui(client):
    return await client.post(
        "/api/v1/doc-truyen/trang",
        files={"file": ("t.png", _anh(), "image/png")},
        data={"source_lang": SourceLang.ja.value},
    )


class TestNguoiDangNhap:
    async def test_chua_dung_gi_thi_con_nguyen_tran(self, client, st, monkeypatch):
        monkeypatch.setattr(st, "han_muc_co_tai_khoan", 10)
        than = (await client.get("/api/v1/han-muc")).json()

        assert than["co_tai_khoan"] is True
        assert (than["tran"], than["da_dung"], than["con_lai"]) == (10, 0, 10)

    async def test_tai_len_roi_thi_so_KHOP_voi_thuc_te(self, client, st, monkeypatch):
        monkeypatch.setattr(st, "han_muc_co_tai_khoan", 5)
        pid = (await client.post("/api/v1/projects", json={
            "name": "H", "source_lang": "ja", "intended_use": "personal"
        })).json()["id"]
        for _ in range(2):
            r = await client.post(
                f"/api/v1/projects/{pid}/pages", files={"file": ("t.png", _anh(), "image/png")}
            )
            assert r.status_code == 202, r.text

        than = (await client.get("/api/v1/han-muc")).json()
        assert (than["da_dung"], than["con_lai"]) == (2, 3)

    async def test_chi_MOT_chot_cho_nguoi_dang_nhap(self, client):
        than = (await client.get("/api/v1/han-muc")).json()
        assert [c["loai"] for c in than["chot"]] == [LoaiChuThe.nguoi_dung.value]

    async def test_xem_han_muc_KHONG_ton_luot(self, client, st, monkeypatch):
        """Chỉ đọc. Gọi mà cũng trừ lượt thì giao diện tự đốt hạn mức của người dùng mỗi lần
        làm mới trang."""
        monkeypatch.setattr(st, "han_muc_co_tai_khoan", 3)
        for _ in range(5):
            await client.get("/api/v1/han-muc")
        assert (await client.get("/api/v1/han-muc")).json()["da_dung"] == 0


class TestMocReset:
    async def test_co_moc_reset_va_dem_nguoc(self, client):
        than = (await client.get("/api/v1/han-muc")).json()
        assert than["reset_luc"].endswith("+07:00"), than["reset_luc"]
        assert 0 < than["reset_sau_giay"] <= 24 * 3600

    async def test_moc_reset_la_gio_VIET_NAM_ke_ca_khi_may_chay_UTC(
        self, client, monkeypatch
    ):
        """Container production chạy UTC. Mốc reset tính theo giờ máy sẽ lệch 7 tiếng — người
        dùng hết lượt lúc 23:00 đợi qua nửa đêm vẫn bị chặn thêm 7 tiếng nữa."""
        import os
        import time

        cu = os.environ.get("TZ")
        os.environ["TZ"] = "UTC"
        time.tzset()
        try:
            than = (await client.get("/api/v1/han-muc")).json()
            assert than["reset_luc"].endswith("+07:00"), than["reset_luc"]
            assert "T00:00:00" in than["reset_luc"], than["reset_luc"]
        finally:
            if cu is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = cu
            time.tzset()


class TestKhachLa:
    async def test_khach_chua_dang_nhap_van_xem_duoc(
        self, client_chua_dang_nhap, cookie_chay_duoc_tren_http, st, monkeypatch
    ):
        """Bắt đăng nhập để xem hạn mức của chính mình là đúng cái vòng luẩn quẩn §4.1 cấm."""
        monkeypatch.setattr(st, "han_muc_khach_la", 6)
        r = await client_chua_dang_nhap.get("/api/v1/han-muc")

        assert r.status_code == 200, r.text
        assert r.json()["co_tai_khoan"] is False
        assert r.json()["tran"] == 6

    async def test_khach_co_DU_HAI_chot(
        self, client_chua_dang_nhap, cookie_chay_duoc_tren_http
    ):
        than = (await client_chua_dang_nhap.get("/api/v1/han-muc")).json()
        assert [c["loai"] for c in than["chot"]] == [
            LoaiChuThe.khach_cookie.value, LoaiChuThe.khach_ip.value
        ]

    async def test_tran_DEM_HIEN_la_tran_cookie_khong_phai_tran_IP(
        self, client_chua_dang_nhap, cookie_chay_duoc_tren_http, st, monkeypatch
    ):
        """Trần IP là hàng rào chống lạm dụng dùng chung. Hiện nó lên làm người dùng bối rối vì
        con số không khớp thứ họ thật sự được dùng."""
        monkeypatch.setattr(st, "han_muc_khach_la", 6)
        monkeypatch.setattr(st, "han_muc_ip_khach_la", 25)
        assert (await client_chua_dang_nhap.get("/api/v1/han-muc")).json()["tran"] == 6

    async def test_con_lai_lay_NHO_NHAT_giua_cac_chot(
        self, client_chua_dang_nhap, cookie_chay_duoc_tren_http, st, monkeypatch
    ):
        """**Bài canh nặng nhất.** Chạm trần IP thì `con_lai` phải là 0, dù cookie còn nguyên.

        Trần cookie 99, trần IP 2, dùng hết 2 qua IP bằng cách xoá cookie mỗi lượt ⇒ chốt cookie
        hiện tại còn nguyên 99 nhưng thực tế không gửi thêm được trang nào.
        """
        monkeypatch.setattr(st, "han_muc_khach_la", 99)
        monkeypatch.setattr(st, "han_muc_ip_khach_la", 2)

        for _ in range(2):
            client_chua_dang_nhap.cookies.clear()
            assert (await _khach_gui(client_chua_dang_nhap)).status_code == 202

        client_chua_dang_nhap.cookies.clear()
        than = (await client_chua_dang_nhap.get("/api/v1/han-muc")).json()

        assert than["con_lai"] == 0, (
            f"báo còn {than['con_lai']} trong khi chốt IP đã hết — mời người ta thả tệp lên rồi "
            f"nhận 429. Chi tiết chốt: {than['chot']}"
        )
        assert (await _khach_gui(client_chua_dang_nhap)).status_code == 429, (
            "bài này chỉ có nghĩa nếu lượt gửi tiếp theo THẬT SỰ bị chặn"
        )

    async def test_so_cua_khach_NAY_khong_lan_sang_khach_KHAC(
        self, client_chua_dang_nhap, cookie_chay_duoc_tren_http, st, monkeypatch
    ):
        monkeypatch.setattr(st, "han_muc_khach_la", 9)
        monkeypatch.setattr(st, "han_muc_ip_khach_la", 99)
        await _khach_gui(client_chua_dang_nhap)
        assert (await client_chua_dang_nhap.get("/api/v1/han-muc")).json()["da_dung"] == 1

        client_chua_dang_nhap.cookies.clear()
        than = (await client_chua_dang_nhap.get("/api/v1/han-muc")).json()
        assert than["da_dung"] == 0, "cookie mới mà vẫn thấy lượt đã dùng của khách trước"
