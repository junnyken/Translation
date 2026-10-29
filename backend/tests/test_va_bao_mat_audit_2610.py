"""Vá bảo mật theo đợt kiểm tra 26/10/2026 — mỗi lớp test khoá một lỗ đã đo được.

1. PoW chống bot không có "work": mã có chữ ký là đủ qua, dùng lại vô hạn.
2. Email "chủ hệ thống" viết cứng tự lên quản trị khi đăng ký (repo công khai, không xác minh email).
3. Chapter vô chủ mở cho MỌI tài khoản (xoá một người là phát truyện của họ cho cả hệ thống).
4. Webhook nạp tiền cộng lượt lại khi cổng gửi lại cùng một giao dịch.
5. SSRF: kiểm IP host đầu rồi để urllib tự đi theo 302 vào mạng nội bộ.
6. Ảnh bom pixel: vài KB nhưng giải mã ra hàng trăm MB trong tiến trình API.
"""
from __future__ import annotations

import hashlib
import io
import uuid

import pytest
from PIL import Image
from sqlalchemy import select

from app.api.v1 import developer_routes as dev
from app.api.v1 import xac_thuc_routes as xt
from app.core.config import get_settings
from app.models import DonNapLuot, NguoiDung, NhatKyQuanTri, Project
from app.models.enums import IntendedUse, SourceLang, TargetLang
from app.services import tai_khoan
from app.services.storage import UnsupportedImage, sniff_image

pytestmark = pytest.mark.anyio


def _giai(ma: str, do_kho: int) -> str:
    i = 0
    while True:
        if xt._so_bit_0_dau(hashlib.sha256(f"{ma}:{i}".encode()).digest()) >= do_kho:
            return str(i)
        i += 1


class TestPowThat:
    def test_ma_tron_khong_kem_loi_giai_thi_bi_tu_choi(self):
        s = get_settings()
        ma = xt._tao_ma_thach_thuc_pow(s)
        assert xt._kiem_tra_ma_thach_thuc_pow(ma, None, s) is None
        assert xt._kiem_tra_ma_thach_thuc_pow(ma, "abc", s) is None

    def test_loi_giai_dung_thi_qua_va_tra_nonce(self):
        s = get_settings()
        ma = xt._tao_ma_thach_thuc_pow(s)
        nonce = xt._kiem_tra_ma_thach_thuc_pow(ma, _giai(ma, xt._DO_KHO_POW_BIT), s)
        assert nonce == ma.split(".")[1]

    def test_ma_gia_chu_ky_thi_loi_giai_cung_vo_dung(self):
        s = get_settings()
        iat, nonce, _ = xt._tao_ma_thach_thuc_pow(s).split(".")
        gia = f"{iat}.{nonce}.{'0' * 32}"
        assert xt._kiem_tra_ma_thach_thuc_pow(gia, _giai(gia, xt._DO_KHO_POW_BIT), s) is None


class TestKhongConEmailChuHeThong:
    async def test_dang_ky_bang_email_cu_khong_thanh_quan_tri(self, session, tai_khoan_test):
        # Đã có tài khoản (A, B) ⇒ người mới KHÔNG phải người đầu tiên.
        nguoi = await tai_khoan.dang_ky(
            session, email="thientrieu753@gmail.com", ten_hien="x", mat_khau_tho="mat-khau-du-dai"
        )
        try:
            assert nguoi.la_quan_tri is False
            assert await tai_khoan.dang_nhap(
                session, email="thientrieu753@gmail.com", mat_khau_tho="mat-khau-du-dai"
            ) is not None
            await session.refresh(nguoi)
            assert nguoi.la_quan_tri is False, "đăng nhập không được tự phong quyền"
        finally:
            await session.delete(nguoi)
            await session.commit()


async def _chapter_vo_chu(session) -> Project:
    p = Project(
        name="vo-chu", source_lang=SourceLang.ja, target_lang=TargetLang.vi,
        intended_use=IntendedUse.personal, chu_so_huu_id=None,
    )
    session.add(p)
    await session.commit()
    return p


async def _dat_quan_tri(session, nguoi_id: str, la: bool) -> None:
    n = await session.get(NguoiDung, uuid.UUID(nguoi_id))
    n.la_quan_tri = la
    await session.commit()


class TestChapterVoChuChiQuanTri:
    async def test_nguoi_thuong_khong_thay_khong_nhan_duoc(self, session, client_b):
        p = await _chapter_vo_chu(session)
        assert (await client_b.get(f"/api/v1/projects/{p.id}")).status_code == 404
        assert (await client_b.post(f"/api/v1/projects/{p.id}/claim")).status_code == 404
        ds = (await client_b.get("/api/v1/projects")).json()
        assert str(p.id) not in {x["id"] for x in ds}

    async def test_quan_tri_thay_va_nhan_duoc(self, session, client, nguoi_a):
        await _dat_quan_tri(session, nguoi_a[0], True)
        try:
            p = await _chapter_vo_chu(session)
            ds = (await client.get("/api/v1/projects")).json()
            assert str(p.id) in {x["id"] for x in ds}
            assert (await client.post(f"/api/v1/projects/{p.id}/claim")).status_code == 200
        finally:
            await _dat_quan_tri(session, nguoi_a[0], False)


@pytest.fixture
def bi_mat_webhook(monkeypatch):
    monkeypatch.setenv("WEBHOOK_NAP_LUOT_BI_MAT", "bi-mat-test")
    get_settings.cache_clear()
    yield "bi-mat-test"
    get_settings.cache_clear()


class TestWebhookKhongCongTrung:
    async def test_gui_lai_cung_giao_dich_chi_cong_mot_lan(
        self, session, client_chua_dang_nhap, nguoi_a, bi_mat_webhook
    ):
        nguoi = await session.get(NguoiDung, uuid.UUID(nguoi_a[0]))
        truoc = int(nguoi.so_luot_mua_them or 0)
        than = {
            "id": 987654, "transferType": "in", "transferAmount": 50_000,
            "content": f"NAP {nguoi.email}",
        }
        tieu_de = {"Authorization": f"Apikey {bi_mat_webhook}"}
        r1 = await client_chua_dang_nhap.post("/api/v1/nap-luot/webhook", json=than, headers=tieu_de)
        r2 = await client_chua_dang_nhap.post("/api/v1/nap-luot/webhook", json=than, headers=tieu_de)
        assert r1.json()["ok"] is True and r1.json()["da_cong_them"] == 100, r1.text
        assert r2.json().get("trung_lap") is True, r2.text
        await session.refresh(nguoi)
        try:
            assert nguoi.so_luot_mua_them == truoc + 100
        finally:
            nguoi.so_luot_mua_them = truoc
            await session.commit()

    async def test_tien_ra_va_thieu_ma_giao_dich_khong_cong(
        self, client_chua_dang_nhap, nguoi_a, bi_mat_webhook, session
    ):
        nguoi = await session.get(NguoiDung, uuid.UUID(nguoi_a[0]))
        tieu_de = {"Authorization": f"Apikey {bi_mat_webhook}"}
        ra = await client_chua_dang_nhap.post("/api/v1/nap-luot/webhook", headers=tieu_de, json={
            "id": 1, "transferType": "out", "transferAmount": 50_000, "content": f"NAP {nguoi.email}"})
        thieu = await client_chua_dang_nhap.post("/api/v1/nap-luot/webhook", headers=tieu_de, json={
            "transferAmount": 50_000, "content": f"NAP {nguoi.email}"})
        assert ra.json() == {"ok": False, "ly_do": "khong_phai_tien_vao"}
        assert thieu.json() == {"ok": False, "ly_do": "thieu_ma_giao_dich"}


class TestDuyetDonNguyenTu:
    async def test_xac_nhan_hai_lan_chi_cong_mot_lan_va_co_nhat_ky(self, session, client, nguoi_a, nguoi_b):
        await _dat_quan_tri(session, nguoi_a[0], True)
        khach = await session.get(NguoiDung, uuid.UUID(nguoi_b[0]))
        truoc = int(khach.so_luot_mua_them or 0)
        don = DonNapLuot(
            ma_don="ACB-TEST0001", nguoi_dung_id=khach.id, email=khach.email, ma_goi="co_ban",
            so_tien_vnd=10_000, so_trang_cong=20, trang_thai="cho_duyet",
        )
        session.add(don)
        await session.commit()
        try:
            for _ in range(2):
                r = await client.post("/api/v1/quan-tri/duyet-don-nap",
                                      json={"ma_don": "ACB-TEST0001", "hanh_dong": "xac_nhan"})
                assert r.status_code == 200, r.text
            await session.refresh(khach)
            assert khach.so_luot_mua_them == truoc + 20
            nhat_ky = (await session.execute(
                select(NhatKyQuanTri).where(NhatKyQuanTri.doi_tuong == "ACB-TEST0001")
            )).scalars().all()
            assert [n.hanh_dong for n in nhat_ky] == ["duyet_don_nap"]
        finally:
            khach.so_luot_mua_them = truoc
            await session.commit()
            await _dat_quan_tri(session, nguoi_a[0], False)


class TestSsrfChuyenHuong:
    def test_dai_cgnat_va_noi_bo_bi_chan(self):
        for url in ("http://100.64.0.1/a.png", "http://127.0.0.1/a.png", "http://[::ffff:10.0.0.1]/a.png"):
            with pytest.raises(dev.LoiTaiAnh):
                dev._kiem_tra_url_an_toan_ssrf(url)

    def test_302_vao_dia_chi_noi_bo_bi_chan_o_buoc_chuyen_huong(self, monkeypatch):
        import urllib.error
        from email.message import Message

        da_mo: list[str] = []

        class _Opener:
            def open(self, req, timeout=None):
                da_mo.append(req.full_url)
                h = Message()
                h["Location"] = "http://169.254.169.254/latest/meta-data/"
                raise urllib.error.HTTPError(req.full_url, 302, "Found", h, None)

        # Host đầu "công cộng" để qua bước kiểm đầu tiên; bước chuyển hướng phải bị chặn.
        thuc = dev._kiem_tra_url_an_toan_ssrf
        monkeypatch.setattr(dev, "_kiem_tra_url_an_toan_ssrf",
                            lambda u: None if "anh.vi-du" in u else thuc(u))
        monkeypatch.setattr(dev.urllib.request, "build_opener", lambda *a: _Opener())
        with pytest.raises(dev.LoiTaiAnh, match="nội bộ"):
            dev._tai_anh_url_chong_chan("http://anh.vi-du/a.png")
        assert da_mo == ["http://anh.vi-du/a.png"], "không được mở địa chỉ nội bộ"


class TestAnhBom:
    def test_png_mot_mau_khong_lo_bi_tu_choi_truoc_khi_giai_ma(self):
        ra = io.BytesIO()
        Image.new("1", (9000, 9000)).save(ra, "PNG")  # 81 triệu điểm, chỉ vài chục KB
        assert len(ra.getvalue()) < 2_000_000
        with pytest.raises(UnsupportedImage, match="vượt quá kích thước"):
            sniff_image(ra.getvalue())

    def test_anh_trang_binh_thuong_van_qua(self, sample_page_image):
        assert sniff_image(sample_page_image)[1] in (".png", ".jpg", ".webp")


class TestChongHackGoiVaBaoMatApiKey:
    async def test_chan_gia_mao_ma_goi_va_so_tien_khi_xac_nhan_chuyen_khoan(self, client):
        # 1. Gửi mã gói tự chế -> phải bị chặn 422
        r_fake = await client.post(
            "/api/v1/nap-luot/xac-nhan-chuyen-khoan",
            json={
                "ma_goi": "goi_tu_che_999999_trang",
                "ten_goi": "Hack 1 triệu trang",
                "so_tien_vnd": 500_000_000,
                "noi_dung_chuyen_khoan": "NAP HACK",
            },
        )
        assert r_fake.status_code == 422, r_fake.text

        # 2. Gửi mã gói hợp lệ ('co_ban' = 105 trang, 50.000đ theo Phương án A) nhưng cố tình sửa so_tien_vnd = 500 triệu
        # -> Hệ thống phải bỏ qua so_tien_vnd của client, giữ đúng 105 trang / 50.000đ và ở trạng thái 'cho_duyet'
        r_ok = await client.post(
            "/api/v1/nap-luot/xac-nhan-chuyen-khoan",
            json={
                "ma_goi": "co_ban",
                "ten_goi": "Hack tên gói",
                "so_tien_vnd": 500_000_000,
                "noi_dung_chuyen_khoan": "NAP STARTER",
            },
        )
        assert r_ok.status_code == 200, r_ok.text
        body = r_ok.json()
        assert body["so_trang_cong"] == 105
        assert body["so_tien_vnd"] == 50_000
        assert body["trang_thai"] == "cho_duyet"

        # 3. Gói Mồi ('goi_moi' = 40 trang, 20.000đ) cho phép mua nhiều lần và cộng dồn luỹ kế vào so_luot_mua_them
        for lan in (1, 2):
            r_moi = await client.post(
                "/api/v1/nap-luot/xac-nhan-chuyen-khoan",
                json={
                    "ma_goi": "goi_moi",
                    "ten_goi": f"Gói Mồi lần {lan}",
                    "so_tien_vnd": 20_000,
                    "noi_dung_chuyen_khoan": f"NAP MOI {lan}",
                },
            )
            assert r_moi.status_code == 200, r_moi.text
            don_moi = r_moi.json()
            assert don_moi["so_trang_cong"] == 40
            assert don_moi["so_tien_vnd"] == 20_000
            r_duyet = await client.post(
                "/api/v1/quan-tri/duyet-don-nap",
                json={"ma_don": don_moi["ma_don"], "hanh_dong": "xac_nhan"},
            )
            assert r_duyet.status_code == 200, r_duyet.text

        # Kiểm tra số dư mua thêm đã cộng dồn đủ 2 lần x 40 = 80 trang
        r_tt = await client.get("/api/v1/nap-luot/thong-tin")
        assert r_tt.status_code == 200
        assert r_tt.json()["so_luot_mua_them"] >= 80

    async def test_khoa_api_tr_live_khong_duoc_xoay_key_doi_mat_khau_hay_quan_tri(
        self, client, client_chua_dang_nhap
    ):
        # Tạo API Key bằng phiên đăng nhập tương tác hợp lệ
        r_key = await client.post("/api/v1/auth/api-key")
        assert r_key.status_code == 201, r_key.text
        api_key = r_key.json()["api_key"]
        assert api_key.startswith("tr_live_")
        assert len(api_key) >= 48  # 256-bit token_urlsafe(32) + prefix

        headers_api = {"Authorization": f"Bearer {api_key}"}

        # Dùng tr_live_ để xoay key mới hoặc xoá key -> phải bị chặn 403
        r_rotate = await client_chua_dang_nhap.post("/api/v1/auth/api-key", headers=headers_api)
        assert r_rotate.status_code == 403, r_rotate.text
        r_delete = await client_chua_dang_nhap.delete("/api/v1/auth/api-key", headers=headers_api)
        assert r_delete.status_code == 403, r_delete.text

        # Dùng tr_live_ để đổi mật khẩu -> phải bị chặn 403
        r_pw = await client_chua_dang_nhap.patch(
            "/api/v1/auth/me",
            headers=headers_api,
            json={"mat_khau_cu": "mat-khau-test-1234", "mat_khau_moi": "mat-khau-moi-56789"},
        )
        assert r_pw.status_code == 403, r_pw.text

        # Dùng tr_live_ (kể cả của tài khoản admin) gọi endpoint quản trị -> phải bị chặn 403
        r_admin_users = await client_chua_dang_nhap.get("/api/v1/auth/users", headers=headers_api)
        assert r_admin_users.status_code == 403, r_admin_users.text
        r_admin_cap = await client_chua_dang_nhap.post(
            "/api/v1/quan-tri/cap-luot",
            headers=headers_api,
            json={"email": "a@test.local", "cong_them_luot": 1000},
        )
        assert r_admin_cap.status_code == 403, r_admin_cap.text

    def test_chu_ky_url_anh_developer_khong_lo_api_key(self):
        import uuid

        pid = uuid.uuid4()
        uid = uuid.uuid4()
        sig = dev._ky_url_anh_developer(pid, uid, 1800000000)
        assert len(sig) == 32
        assert "tr_live_" not in sig
