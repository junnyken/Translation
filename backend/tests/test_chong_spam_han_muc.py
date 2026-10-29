"""Kiểm chứng cấu hình hạn mức mới (khách 2 trang, tài khoản 20 trang) và các chốt chống spam:
1. Chặn dò mật khẩu brute-force trên `POST /api/v1/auth/login` theo địa chỉ mạng.
2. Chặn spam `retry-*` / `re-translate` vô hạn trên cùng một trang để đốt token LLM / CPU.
"""
from __future__ import annotations

import io
import uuid

import pytest
from PIL import Image

from app.core.config import get_settings
from app.models import Page
from app.models.enums import PageStatus
from tests.conftest import EMAIL_A, MAT_KHAU_TEST


def _anh() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), "white").save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def st():
    return get_settings()


class TestCauHinhHanMucMoi:
    def test_mac_dinh_khach_2_trang_tai_khoan_10_trang(self, st):
        assert st.han_muc_khach_la == 2
        assert st.han_muc_co_tai_khoan == 10
        assert st.han_muc_ip_khach_la == 8
        assert st.han_muc_ip_khach_la > st.han_muc_khach_la
        assert st.so_tai_khoan_moi_moi_ip_mot_ngay == 2


class TestChanBruteForceDangNhap:
    async def test_dang_nhap_sai_qua_tran_thi_429(
        self, client_chua_dang_nhap, tai_khoan_test, st, monkeypatch
    ):
        monkeypatch.setattr(st, "so_lan_dang_nhap_sai_moi_ip_mot_ngay", 3)

        for lan in range(3):
            r = await client_chua_dang_nhap.post(
                "/api/v1/auth/login",
                json={"email": EMAIL_A, "mat_khau": "sai-mat-khau-1234"},
            )
            assert r.status_code == 401, f"lượt {lan + 1}: {r.text}"

        r4 = await client_chua_dang_nhap.post(
            "/api/v1/auth/login",
            json={"email": EMAIL_A, "mat_khau": "sai-mat-khau-1234"},
        )
        assert r4.status_code == 429, r4.text
        detail = r4.json()["detail"]
        assert detail["loi"] == "vuot_tran_dang_nhap_sai"
        assert detail["tran_moi_ngay"] == 3
        assert int(r4.headers["retry-after"]) > 0

    async def test_dang_nhap_DUNG_khong_tieu_suat_sai(
        self, client_chua_dang_nhap, tai_khoan_test, st, monkeypatch
    ):
        monkeypatch.setattr(st, "so_lan_dang_nhap_sai_moi_ip_mot_ngay", 2)

        for _ in range(3):
            r = await client_chua_dang_nhap.post(
                "/api/v1/auth/login",
                json={"email": EMAIL_A, "mat_khau": MAT_KHAU_TEST},
            )
            assert r.status_code == 200, r.text

    async def test_dang_nhap_sai_KHONG_an_vao_han_muc_trang(
        self, client_chua_dang_nhap, tai_khoan_test, st, monkeypatch
    ):
        monkeypatch.setattr(st, "cookie_khach_secure", False)
        truoc = (await client_chua_dang_nhap.get("/api/v1/han-muc")).json()

        await client_chua_dang_nhap.post(
            "/api/v1/auth/login",
            json={"email": EMAIL_A, "mat_khau": "sai-mat-khau-1234"},
        )

        sau = (await client_chua_dang_nhap.get("/api/v1/han-muc")).json()
        chot_ip_truoc = [c for c in truoc["chot"] if c["loai"] == "khach_ip"][0]
        chot_ip_sau = [c for c in sau["chot"] if c["loai"] == "khach_ip"][0]
        assert chot_ip_sau["da_dung"] == chot_ip_truoc["da_dung"]


class TestChanSpamChayLaiTrang:
    async def test_retry_translate_qua_tran_thi_429(
        self, client, session, st, monkeypatch
    ):
        monkeypatch.setattr(st, "so_lan_chay_lai_toi_da_moi_trang", 2)

        pid = (
            await client.post(
                "/api/v1/projects",
                json={"name": "Chống spam retry", "source_lang": "ja", "intended_use": "personal"},
            )
        ).json()["id"]
        page_id = (
            await client.post(
                f"/api/v1/projects/{pid}/pages",
                files={"file": ("p.png", _anh(), "image/png")},
            )
        ).json()["page_id"]

        page = await session.get(Page, uuid.UUID(page_id))
        page.status = PageStatus.typeset_done
        await session.commit()

        for lan in range(2):
            r = await client.post(f"/api/v1/pages/{page_id}/retry-translate")
            assert r.status_code == 202, f"lượt {lan + 1}: {r.text}"

        r3 = await client.post(f"/api/v1/pages/{page_id}/retry-translate")
        assert r3.status_code == 429, r3.text
        detail = r3.json()["detail"]
        assert detail["loi"] == "vuot_tran_chay_lai_trang"
        assert detail["buoc"] == "translate"
        assert detail["tran_moi_trang"] == 2
