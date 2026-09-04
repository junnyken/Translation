"""Auth slice A — cổng khoá truy cập.

Trước lớp này, đo trên bản chạy thật 2026-09-04: **65 thao tác API, 100% không cần xác thực,
31 trong đó ghi/xoá**. Ai có URL là tạo/sửa/xoá được mọi chapter của mọi người.
"""
from __future__ import annotations

import uuid

import pytest

from app.core.bao_ve import TEN_HEADER
from app.core.config import get_settings
from app.main import app

KHOA = "khoa-thu-nghiem-dai-va-kho-doan-0123456789"


@pytest.fixture
def bat_cong(monkeypatch):
    monkeypatch.setattr(get_settings(), "api_access_key", KHOA)


class TestCongTat:
    """Mặc định TẮT — máy phát triển và bộ test không phải mang khoá đi khắp nơi."""

    async def test_khong_dat_khoa_thi_goi_duoc_nhu_cu(self, client):
        assert (await client.get("/api/v1/projects/" + str(uuid.uuid4()))).status_code == 404


class TestCongBat:
    async def test_thieu_khoa_thi_401(self, client, bat_cong):
        r = await client.get(f"/api/v1/projects/{uuid.uuid4()}")
        assert r.status_code == 401
        assert TEN_HEADER in r.headers.get("www-authenticate", "")

    async def test_khoa_sai_thi_401(self, client, bat_cong):
        r = await client.get(f"/api/v1/projects/{uuid.uuid4()}", headers={TEN_HEADER: "sai"})
        assert r.status_code == 401

    async def test_thieu_khoa_va_khoa_sai_bao_Y_HET_nhau(self, client, bat_cong):
        """Nói ra sự khác biệt là xác nhận cho người dò biết họ đã đoán đúng định dạng."""
        a = await client.get(f"/api/v1/projects/{uuid.uuid4()}")
        b = await client.get(f"/api/v1/projects/{uuid.uuid4()}", headers={TEN_HEADER: "sai"})
        assert a.status_code == b.status_code
        assert a.json() == b.json()

    async def test_dung_khoa_thi_qua(self, client, bat_cong):
        r = await client.get(f"/api/v1/projects/{uuid.uuid4()}", headers={TEN_HEADER: KHOA})
        assert r.status_code == 404, "khoá đúng mà vẫn bị chặn"

    async def test_CHAN_CA_thao_tac_GHI(self, client, bat_cong):
        """Ghi/xoá mới là thứ nguy hiểm — chặn đọc mà quên chặn ghi là vô nghĩa."""
        r = await client.post("/api/v1/projects", json={
            "name": "lén", "source_lang": "en", "target_lang": "vi", "intended_use": "personal"})
        assert r.status_code == 401

    async def test_khoa_dung_thi_GHI_duoc(self, client, bat_cong):
        r = await client.post("/api/v1/projects", headers={TEN_HEADER: KHOA}, json={
            "name": "hợp lệ", "source_lang": "en", "target_lang": "vi",
            "intended_use": "personal"})
        assert r.status_code == 201


class TestKhongSotDuongNao:
    """Gắn cổng ở tầng router chính là để không sót. Test này chứng minh điều đó."""

    def _duong_v1(self):
        return [r for r in app.routes
                if getattr(r, "path", "").startswith("/api/v1")
                and getattr(r, "methods", None)]

    def test_moi_endpoint_v1_deu_co_cong(self):
        thieu = []
        for r in self._duong_v1():
            ten = [getattr(d.call, "__name__", "") for d in (r.dependant.dependencies or [])]
            if "cong_khoa" not in ten:
                thieu.append(f"{sorted(r.methods)} {r.path}")
        assert not thieu, f"{len(thieu)} endpoint KHÔNG có cổng khoá: {thieu[:5]}"

    def test_co_dang_kiem_that_chu_khong_phai_danh_sach_rong(self):
        """Một test 'không có gì thiếu' trên danh sách rỗng luôn xanh và chẳng chứng minh gì."""
        assert len(self._duong_v1()) >= 50


class TestDuongSONG_phai_mo:
    """Nền tảng hosting thăm dò `/` và `/healthz`. Khoá chúng lại là tự làm hỏng deploy."""

    async def test_healthz_van_mo_khi_cong_bat(self, client, bat_cong):
        assert (await client.get("/healthz")).status_code == 200

    async def test_root_van_mo_khi_cong_bat(self, client, bat_cong):
        assert (await client.get("/")).status_code == 200
