"""E54 — máy chủ nói CHÍNH SÁCH GIỮ TỆP, giao diện không gõ cứng.

## Lỗi đang vá — một câu SAI trên màn của bản đang chạy

E50 ship với `bat_lich_don_tep` mặc định **TẮT**, trong khi giao diện vẫn hứa "kết quả chỉ giữ 30
phút, sau đó bị xoá". Tệp không hề bị xoá ⇒ **giao diện nói sai với người dùng**.

Không gây mất dữ liệu, nhưng nó phá đúng thứ dự án coi là nguyên tắc: nói thật về trạng thái.

## Vì sao phải tính THEO NGƯỜI GỌI

`tu_xoa_cho_tai_khoan` cho phép tắt luật xoá riêng cho tài khoản đã đăng ký. Nên cùng một cấu hình
cho hai câu trả lời khác nhau ở khách lạ và người đăng nhập — giao diện không có cách nào tự biết.
"""
from __future__ import annotations

import pytest

from app.core.config import get_settings


@pytest.fixture
def st():
    return get_settings()


class TestGiuKetQuaPhut:
    async def test_lich_TAT_thi_tra_None_chu_khong_tra_30(
        self, client_chua_dang_nhap, st, monkeypatch
    ):
        """**Bài canh chính.** Đây đúng trạng thái bản chạy 27-09: lịch tắt, tệp KHÔNG bị xoá.

        Trả `30` ở đây là để giao diện tiếp tục nói sai.
        """
        monkeypatch.setattr(st, "bat_lich_don_tep", False)
        than = (await client_chua_dang_nhap.get("/api/v1/han-muc")).json()
        assert than["giu_ket_qua_phut"] is None, than

    async def test_lich_BAT_thi_tra_dung_so_phut(self, client_chua_dang_nhap, st, monkeypatch):
        monkeypatch.setattr(st, "bat_lich_don_tep", True)
        monkeypatch.setattr(st, "giu_ket_qua_phut", 30)
        than = (await client_chua_dang_nhap.get("/api/v1/han-muc")).json()
        assert than["giu_ket_qua_phut"] == 30

    async def test_KHACH_bi_xoa_nhung_TAI_KHOAN_thi_khong(self, client_chua_dang_nhap, client, st, monkeypatch):
        """Cùng một cấu hình, HAI câu trả lời khác nhau — đúng thứ giao diện không tự suy được."""
        monkeypatch.setattr(st, "bat_lich_don_tep", True)
        monkeypatch.setattr(st, "giu_ket_qua_phut", 30)
        monkeypatch.setattr(st, "tu_xoa_cho_tai_khoan", False)

        khach = (await client_chua_dang_nhap.get("/api/v1/han-muc")).json()
        co_tk = (await client.get("/api/v1/han-muc")).json()

        assert khach["giu_ket_qua_phut"] == 30, "khách lạ vẫn phải bị dọn"
        assert co_tk["giu_ket_qua_phut"] is None, "tài khoản đã tắt tự xoá mà vẫn báo bị xoá"

    async def test_bat_ca_hai_thi_ca_hai_deu_bi_xoa(self, client_chua_dang_nhap, client, st, monkeypatch):
        monkeypatch.setattr(st, "bat_lich_don_tep", True)
        monkeypatch.setattr(st, "giu_ket_qua_phut", 45)
        monkeypatch.setattr(st, "tu_xoa_cho_tai_khoan", True)
        assert (await client_chua_dang_nhap.get("/api/v1/han-muc")).json()["giu_ket_qua_phut"] == 45
        assert (await client.get("/api/v1/han-muc")).json()["giu_ket_qua_phut"] == 45

    async def test_lich_TAT_thi_KHONG_AI_bi_xoa_ke_ca_khach(
        self, client_chua_dang_nhap, client, st, monkeypatch
    ):
        """Thứ tự kiểm quan trọng: lịch tắt phải thắng `tu_xoa_cho_tai_khoan`."""
        monkeypatch.setattr(st, "bat_lich_don_tep", False)
        monkeypatch.setattr(st, "tu_xoa_cho_tai_khoan", True)
        assert (await client_chua_dang_nhap.get("/api/v1/han-muc")).json()["giu_ket_qua_phut"] is None
        assert (await client.get("/api/v1/han-muc")).json()["giu_ket_qua_phut"] is None
