"""Auth slice A — cổng khoá truy cập, và slice B đã thay nó ở đâu.

Trước slice A, đo trên bản chạy thật 2026-09-04: **65 thao tác API, 100% không cần xác thực,
31 trong đó ghi/xoá**. Ai có URL là tạo/sửa/xoá được mọi chapter của mọi người.

## Slice B đổi gì trong tệp này

Slice A đặt khoá chung ở tầng router. Slice B **thay nó bằng phiên đăng nhập** ở đúng chỗ đó,
và đẩy khoá chung về đúng một nhiệm vụ: gác cổng `/auth/register`.

Đây là bước MẠNH LÊN, không phải đổi ngang — và các test dưới đây phải chứng minh được điều
đó, chứ không chỉ đổi theo cho xanh:

- Chỉ cầm khoá chung, không có phiên ⇒ **không đọc/ghi được gì** (trước đây là làm được mọi thứ).
- Không có khoá chung ⇒ **không tạo được tài khoản**.
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
    """Mặc định TẮT — máy phát triển và bộ test không phải mang khoá đi khắp nơi.

    Lưu ý sau slice B: cổng khoá tắt KHÔNG có nghĩa là hệ thống mở toang. Cổng đăng nhập vẫn
    chặn mọi đường vào dữ liệu; tắt khoá chung chỉ khiến ai cũng **đăng ký** được.
    """

    async def test_khong_dat_khoa_thi_goi_duoc_nhu_cu(self, client):
        assert (await client.get("/api/v1/projects/" + str(uuid.uuid4()))).status_code == 404

    async def test_cong_khoa_tat_van_KHONG_mo_du_lieu_cho_nguoi_chua_dang_nhap(
        self, client_chua_dang_nhap
    ):
        r = await client_chua_dang_nhap.get(f"/api/v1/projects/{uuid.uuid4()}")
        assert r.status_code == 401


class TestCongBat:
    async def test_thieu_khoa_thi_khong_tao_duoc_tai_khoan(self, client_chua_dang_nhap, bat_cong):
        """Sau slice B, khoá chung gác **đăng ký** — chứ không còn gác dữ liệu."""
        r = await client_chua_dang_nhap.post("/api/v1/auth/register", json={
            "email": "len@x.test", "ten_hien": "len", "mat_khau": "mat-khau-du-dai"})
        assert r.status_code == 401
        assert TEN_HEADER in r.headers.get("www-authenticate", "")

    async def test_khoa_sai_thi_khong_tao_duoc_tai_khoan(self, client_chua_dang_nhap, bat_cong):
        r = await client_chua_dang_nhap.post(
            "/api/v1/auth/register", headers={TEN_HEADER: "sai"},
            json={"email": "len2@x.test", "ten_hien": "len", "mat_khau": "mat-khau-du-dai"})
        assert r.status_code == 401

    async def test_CHI_CO_KHOA_CHUNG_thi_KHONG_doc_duoc_du_lieu(
        self, client_chua_dang_nhap, bat_cong
    ):
        """Điểm mấu chốt chứng minh slice B mạnh hơn slice A.

        Ở slice A, cầm khoá chung là đọc/xoá được chapter của mọi người. Từ slice B, khoá chung
        **không mở được dữ liệu nữa** — phải có phiên đăng nhập.
        """
        r = await client_chua_dang_nhap.get(
            f"/api/v1/projects/{uuid.uuid4()}", headers={TEN_HEADER: KHOA}
        )
        assert r.status_code == 401

    async def test_CHI_CO_KHOA_CHUNG_thi_KHONG_ghi_duoc(self, client_chua_dang_nhap, bat_cong):
        r = await client_chua_dang_nhap.post(
            "/api/v1/projects", headers={TEN_HEADER: KHOA},
            json={"name": "lén", "source_lang": "en", "target_lang": "vi",
                  "intended_use": "personal"},
        )
        assert r.status_code == 401

    async def test_thieu_khoa_va_khoa_sai_bao_Y_HET_nhau(self, client_chua_dang_nhap, bat_cong):
        """Nói ra sự khác biệt là xác nhận cho người dò biết họ đã đoán đúng định dạng."""
        than = {"email": "x@x.test", "ten_hien": "x", "mat_khau": "mat-khau-du-dai"}
        a = await client_chua_dang_nhap.post("/api/v1/auth/register", json=than)
        b = await client_chua_dang_nhap.post(
            "/api/v1/auth/register", headers={TEN_HEADER: "sai"}, json=than
        )
        assert a.status_code == b.status_code
        assert a.json() == b.json()

    async def test_co_phien_thi_qua(self, client, bat_cong):
        """Đã đăng nhập thì KHÔNG cần khoá chung — nếu không, muốn cho ai dùng cũng phải phát
        cho họ khoá chung, mà cầm khoá chung là tạo được tài khoản cho người khác."""
        r = await client.get(f"/api/v1/projects/{uuid.uuid4()}")
        assert r.status_code == 404, "có phiên mà vẫn bị chặn"

    async def test_co_phien_thi_GHI_duoc(self, client, bat_cong):
        r = await client.post("/api/v1/projects", json={
            "name": "hợp lệ", "source_lang": "en", "target_lang": "vi",
            "intended_use": "personal"})
        assert r.status_code == 201

    async def test_dung_khoa_chung_thi_tao_duoc_tai_khoan(self, client_chua_dang_nhap, bat_cong):
        r = await client_chua_dang_nhap.post(
            "/api/v1/auth/register", headers={TEN_HEADER: KHOA},
            json={"email": f"moi-{uuid.uuid4().hex[:8]}@x.test", "ten_hien": "moi",
                  "mat_khau": "mat-khau-du-dai"},
        )
        assert r.status_code == 201, r.text


#: Đường KHÔNG đòi đăng nhập — vì lúc gọi chúng thì chưa có phiên mà gửi. Mỗi mục phải có lý
#: do đứng vững; danh sách này mà dài ra là dấu hiệu ai đó đang khoét lỗ.
MIEN_TRU_DANG_NHAP = {
    "/api/v1/auth/login",
    "/api/v1/auth/logout",           # thu hồi phiên; mã sai vẫn trả 204, không lộ gì
    "/api/v1/auth/register",         # tự gác bằng khoá chung
    "/api/v1/auth/co-tai-khoan-chua",  # chỉ trả true/false
}


class TestKhongSotDuongNao:
    """Gắn cổng ở tầng router chính là để không sót. Test này chứng minh điều đó."""

    def _duong_v1(self):
        return [r for r in app.routes
                if getattr(r, "path", "").startswith("/api/v1")
                and getattr(r, "methods", None)]

    @staticmethod
    def _ten_phu_thuoc(dep, sau=0):
        """Tên MỌI phụ thuộc, kể cả lồng nhau.

        Bản đầu chỉ nhìn phụ thuộc trực tiếp, và báo đỏ nhầm ba endpoint quản trị: chúng phụ
        thuộc `quan_tri_hien_tai`, mà `quan_tri_hien_tai` mới phụ thuộc `nguoi_dung_hien_tai`.
        Chúng được bảo vệ đúng (đo được: 401 khi chưa đăng nhập), chỉ là test soi nông quá.

        Đi đệ quy còn CHẶT HƠN bản cũ: một endpoint bọc cổng đăng nhập vào lớp giữa nào đó vẫn
        được tính là có cổng, thay vì phải viết ngoại lệ cho nó.
        """
        if sau > 8:
            return set()
        ten = set()
        for d in dep.dependencies or []:
            ten.add(getattr(d.call, "__name__", ""))
            ten |= TestKhongSotDuongNao._ten_phu_thuoc(d, sau + 1)
        return ten

    def test_moi_endpoint_v1_deu_doi_dang_nhap(self):
        """Slice B: cổng ở tầng router giờ là ĐĂNG NHẬP, không phải khoá chung."""
        thieu = []
        for r in self._duong_v1():
            if r.path in MIEN_TRU_DANG_NHAP:
                continue
            if "nguoi_dung_hien_tai" not in self._ten_phu_thuoc(r.dependant):
                thieu.append(f"{sorted(r.methods)} {r.path}")
        assert not thieu, f"{len(thieu)} endpoint KHÔNG đòi đăng nhập: {thieu[:5]}"

    async def test_endpoint_quan_tri_that_su_tra_401_khi_chua_dang_nhap(
        self, client_chua_dang_nhap
    ):
        """Kiểm bằng lời gọi THẬT, không chỉ soi cây phụ thuộc.

        Soi cấu trúc trả lời được "có gắn cổng không"; chỉ lời gọi thật mới trả lời được "cổng
        có chặn không". Test trên đã một lần báo sai vì soi nông — nên phải có cả hai.
        """
        gia = "00000000-0000-0000-0000-000000000001"
        for method, duong in (
            ("GET", "/api/v1/auth/users"),
            ("PATCH", f"/api/v1/auth/users/{gia}"),
            ("DELETE", f"/api/v1/auth/users/{gia}"),
        ):
            r = await client_chua_dang_nhap.request(
                method, duong, json={"dang_hoat_dong": False}
            )
            assert r.status_code == 401, f"{method} {duong} -> {r.status_code}"

    def test_dang_ky_van_duoc_khoa_chung_gac(self):
        """Nếu không, ai mở được địa chỉ cũng tự tạo tài khoản trên hạ tầng của mình."""
        dang_ky = [r for r in self._duong_v1() if r.path == "/api/v1/auth/register"]
        assert dang_ky, "không tìm thấy endpoint đăng ký"
        ten = [getattr(d.call, "__name__", "") for d in (dang_ky[0].dependant.dependencies or [])]
        assert "cong_khoa" in ten

    def test_co_dang_kiem_that_chu_khong_phai_danh_sach_rong(self):
        """Một test 'không có gì thiếu' trên danh sách rỗng luôn xanh và chẳng chứng minh gì."""
        assert len(self._duong_v1()) >= 50


class TestDuongSONG_phai_mo:
    """Nền tảng hosting thăm dò `/` và `/healthz`. Khoá chúng lại là tự làm hỏng deploy."""

    async def test_healthz_van_mo_khi_cong_bat(self, client, bat_cong):
        assert (await client.get("/healthz")).status_code == 200

    async def test_root_van_mo_khi_cong_bat(self, client, bat_cong):
        assert (await client.get("/")).status_code == 200
