"""E52 — người lạ tự đăng ký được, nhưng có TRẦN theo địa chỉ mạng.

## Lỗ đang vá

Trước E52, `POST /auth/register` gắn `Depends(cong_khoa)` nên **người lạ không tự đăng ký được**.
Trái §4.1 đặc tả: "đăng ký là thứ người dùng chọn khi muốn nhiều hơn, không phải cổng chặn ở
cửa". Khách dùng hết 6 trang không có đường nào lên 10.

## Bài canh nặng nhất

`test_tran_theo_IP_lam_cho_han_muc_KHONG_bi_vo_hieu_hoa` — không có trần này thì hạn mức trang
của E49 vô nghĩa: khách hết 6 trang chỉ cần tạo tài khoản mới để có 10, lặp vô hạn. Mở đăng ký
mà quên con số này là tự tay vô hiệu hoá cả E49.

`test_tai_khoan_DAU_TIEN_van_doi_khoa_chung` — tài khoản đầu tiên thành **quản trị** và nhận các
chapter cũ chưa có chủ. Để người lạ chiếm chỗ đó là giao quyền quản trị cho người bấm nhanh nhất.
"""
from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from app.core.config import get_settings
from app.core.db_sync import sync_session
from app.models import NguoiDung, SoCaiHanMuc
from app.services.han_muc_dang_ky import TIEN_TO

MK = "mat-khau-du-manh-1234"


@pytest.fixture
def st():
    return get_settings()


def _email() -> str:
    return f"e52-{uuid.uuid4().hex[:10]}@test.local"


async def _dang_ky(client, email=None, khoa=None):
    headers = {"X-API-Key": khoa} if khoa is not None else {}
    return await client.post(
        "/api/v1/auth/register",
        json={"email": email or _email(), "ten_hien": "Thử", "mat_khau": MK},
        headers=headers,
    )


def _xoa_het_tai_khoan() -> None:
    """Đưa hệ thống về trạng thái "chưa có tài khoản nào" để kiểm nhánh bootstrap.

    `nguoi_dung` KHÔNG nằm trong danh sách TRUNCATE giữa các test (conftest ghi rõ lý do), nên
    phải tự dọn — và dọn xong thì fixture `tai_khoan_test` của bài SAU sẽ tự dựng lại.
    """
    with sync_session() as s:
        s.execute(sa.text("DELETE FROM phien"))
        s.execute(sa.text("DELETE FROM nguoi_dung"))
        s.commit()


def _dem_suat_dang_ky() -> int:
    with sync_session() as s:
        return int(s.execute(
            sa.select(sa.func.coalesce(sa.func.sum(SoCaiHanMuc.so_trang), 0))
            .where(SoCaiHanMuc.chu_the.like(f"{TIEN_TO}%"))
        ).scalar_one())


class TestNguoiLaTuDangKyDuoc:
    async def test_khong_kem_khoa_chung_van_tao_duoc(self, client_chua_dang_nhap, client):
        """`client` có mặt để CHẮC hệ thống đã có tài khoản — nếu không, bài này rơi vào nhánh
        bootstrap và chẳng chứng minh gì."""
        r = await _dang_ky(client_chua_dang_nhap)
        assert r.status_code == 201, r.text
        assert r.json()["la_quan_tri"] is False, "người tự đăng ký KHÔNG được thành quản trị"

    async def test_email_trung_thi_400(self, client_chua_dang_nhap, client):
        e = _email()
        assert (await _dang_ky(client_chua_dang_nhap, e)).status_code == 201
        r = await _dang_ky(client_chua_dang_nhap, e)
        assert r.status_code == 400
        assert "đã có tài khoản" in r.json()["detail"]

    async def test_mat_khau_yeu_thi_400(self, client_chua_dang_nhap, client):
        r = await client_chua_dang_nhap.post(
            "/api/v1/auth/register",
            json={"email": _email(), "ten_hien": "x", "mat_khau": "123"},
        )
        assert r.status_code == 400, r.text


class TestTranTheoIP:
    async def test_tran_theo_IP_lam_cho_han_muc_KHONG_bi_vo_hieu_hoa(
        self, client_chua_dang_nhap, client, st, monkeypatch
    ):
        """**Bài canh nặng nhất.** Không có trần này thì hạn mức trang thành vô nghĩa."""
        monkeypatch.setattr(st, "so_tai_khoan_moi_moi_ip_mot_ngay", 2)

        for lan in range(2):
            assert (await _dang_ky(client_chua_dang_nhap)).status_code == 201, f"lượt {lan + 1}"

        r = await _dang_ky(client_chua_dang_nhap)
        assert r.status_code == 429, f"tạo được tài khoản thứ 3 ⇒ hạn mức trang vô nghĩa: {r.text}"
        than = r.json()["detail"]
        assert than["loi"] == "vuot_tran_dang_ky"
        assert than["tran_moi_ngay"] == 2
        assert than["reset_luc"].endswith("+07:00"), than["reset_luc"]
        assert int(r.headers["retry-after"]) > 0

    async def test_thong_diep_noi_ro_la_tran_theo_DIA_CHI_MANG(
        self, client_chua_dang_nhap, client, st, monkeypatch
    ):
        """Người ở văn phòng có thể bị chặn dù chính họ chưa tạo tài khoản nào — không nói ra thì
        họ không có cách nào tự đoán."""
        monkeypatch.setattr(st, "so_tai_khoan_moi_moi_ip_mot_ngay", 1)
        await _dang_ky(client_chua_dang_nhap)
        than = (await _dang_ky(client_chua_dang_nhap)).json()["detail"]
        assert "địa chỉ mạng" in than["thong_diep"].lower(), than

    async def test_email_trung_KHONG_mat_suat(
        self, client_chua_dang_nhap, client, st, monkeypatch
    ):
        """Cùng luật với "tệp hỏng không mất lượt": lượt bị từ chối không được tiêu suất."""
        monkeypatch.setattr(st, "so_tai_khoan_moi_moi_ip_mot_ngay", 2)
        e = _email()
        assert (await _dang_ky(client_chua_dang_nhap, e)).status_code == 201

        for _ in range(3):
            assert (await _dang_ky(client_chua_dang_nhap, e)).status_code == 400

        assert (await _dang_ky(client_chua_dang_nhap)).status_code == 201, (
            "lượt email trùng đã ăn mất suất"
        )
        assert _dem_suat_dang_ky() == 2

    async def test_mat_khau_yeu_KHONG_mat_suat(
        self, client_chua_dang_nhap, client, st, monkeypatch
    ):
        monkeypatch.setattr(st, "so_tai_khoan_moi_moi_ip_mot_ngay", 1)
        for _ in range(3):
            await client_chua_dang_nhap.post(
                "/api/v1/auth/register",
                json={"email": _email(), "ten_hien": "x", "mat_khau": "1"},
            )
        assert (await _dang_ky(client_chua_dang_nhap)).status_code == 201


class TestBoDemTachRiengKhoiHanMucTrang:
    async def test_dang_ky_KHONG_an_vao_han_muc_TRANG(
        self, client_chua_dang_nhap, client, st, monkeypatch
    ):
        """Hai bộ đếm dùng chung `loai_chu_the = khach_ip`, phân biệt bằng TIỀN TỐ chủ thể.
        Lẫn vào nhau thì tạo tài khoản sẽ ăn mất lượt dịch trang."""
        monkeypatch.setattr(st, "so_tai_khoan_moi_moi_ip_mot_ngay", 3)
        monkeypatch.setattr(st, "cookie_khach_secure", False)

        truoc = (await client_chua_dang_nhap.get("/api/v1/han-muc")).json()
        await _dang_ky(client_chua_dang_nhap)
        sau = (await client_chua_dang_nhap.get("/api/v1/han-muc")).json()

        chot_ip_truoc = [c for c in truoc["chot"] if c["loai"] == "khach_ip"][0]
        chot_ip_sau = [c for c in sau["chot"] if c["loai"] == "khach_ip"][0]
        assert chot_ip_sau["da_dung"] == chot_ip_truoc["da_dung"], (
            f"tạo tài khoản đã ăn vào hạn mức TRANG: {chot_ip_truoc} → {chot_ip_sau}"
        )

    async def test_chu_the_dang_ky_co_TIEN_TO(self, client_chua_dang_nhap, client):
        await _dang_ky(client_chua_dang_nhap)
        with sync_session() as s:
            chu_the = s.execute(
                sa.select(SoCaiHanMuc.chu_the).where(SoCaiHanMuc.chu_the.like(f"{TIEN_TO}%"))
            ).scalars().all()
        assert chu_the, "không ghi hàng nào cho suất đăng ký"
        assert all(c.startswith(TIEN_TO) for c in chu_the)


class TestTaiKhoanDauTien:
    async def test_tai_khoan_DAU_TIEN_van_doi_khoa_chung(
        self, client_chua_dang_nhap, st, monkeypatch, migrated_database
    ):
        """**Bài canh.** Tài khoản đầu tiên thành QUẢN TRỊ và nhận chapter cũ chưa có chủ.

        Để người lạ chiếm chỗ đó là giao quyền quản trị cho người bấm nhanh nhất.
        """
        monkeypatch.setattr(st, "api_access_key", "khoa-chung-thu-nghiem")
        _xoa_het_tai_khoan()

        r = await _dang_ky(client_chua_dang_nhap)
        assert r.status_code == 401, f"tạo được tài khoản đầu tiên mà không cần khoá: {r.text}"

    async def test_dau_tien_KEM_khoa_dung_thi_thanh_quan_tri(
        self, client_chua_dang_nhap, st, monkeypatch, migrated_database
    ):
        monkeypatch.setattr(st, "api_access_key", "khoa-chung-thu-nghiem")
        _xoa_het_tai_khoan()

        r = await _dang_ky(client_chua_dang_nhap, khoa="khoa-chung-thu-nghiem")
        assert r.status_code == 201, r.text
        assert r.json()["la_quan_tri"] is True

    async def test_dau_tien_KHONG_tieu_suat_theo_IP(
        self, client_chua_dang_nhap, st, monkeypatch, migrated_database
    ):
        """Nhánh bootstrap đi qua khoá chung, không qua trần IP — trần đó dành cho người lạ."""
        monkeypatch.setattr(st, "api_access_key", "khoa-chung-thu-nghiem")
        _xoa_het_tai_khoan()
        await _dang_ky(client_chua_dang_nhap, khoa="khoa-chung-thu-nghiem")
        assert _dem_suat_dang_ky() == 0


class TestKhongMoCuaKhiThieuIP:
    async def test_khong_xac_dinh_duoc_IP_thi_503_chu_khong_mo_tu_do(
        self, client_chua_dang_nhap, client, st, monkeypatch
    ):
        """Thà chặn còn hơn để đường tạo tài khoản KHÔNG có trần nào — đó là đường vô hiệu hoá
        hạn mức. Không xác định được IP ⇒ nói thẳng là tạm không mở, kèm lối đi khác."""
        import app.api.v1.xac_thuc_routes as m

        monkeypatch.setattr(m, "ip_cua", lambda *a, **k: None)
        r = await _dang_ky(client_chua_dang_nhap)
        assert r.status_code == 503, r.text
        assert "quản trị" in r.json()["detail"]
