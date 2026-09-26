"""E49f — khách lạ tải lên được, và KHÔNG ai đọc được truyện của ai.

## Bài canh nặng nhất nằm ở phân quyền, không ở hạn mức

Mở đường cho khách lạ nghĩa là sinh ra chapter **không có `chu_so_huu_id`**. Trước E49, dự án
định nghĩa `chu_so_huu_id IS NULL` là "chapter cũ chưa có chủ" và **mọi tài khoản đăng nhập đều
dùng được** — nên nếu không phân biệt, mọi người đăng nhập sẽ đọc được truyện của mọi khách lạ.

`test_NGUOI_DANG_NHAP_khong_doc_duoc_truyen_cua_khach` canh đúng chỗ đó. Gỡ nhánh giữa trong
`duoc_dung_project` ra thì nó phải đỏ.

## Vì sao các bài dưới tắt `cookie_khach_secure`

Bộ test chạy trên `http://test`. Trình duyệt và bộ nhớ cookie của httpx **không gửi lại** cookie
`Secure` qua `http://`, nên để bật thì mỗi request là một "khách mới" và không bài nào kiểm được
tính liên tục. Cờ `Secure` bản thân nó đã có bài riêng ở `test_e49d`.
"""
from __future__ import annotations

import io

import pytest
import sqlalchemy as sa
from PIL import Image

from app.core.config import get_settings
from app.core.danh_tinh_khach import TEN_COOKIE
from app.models import Project
from app.models.enums import SourceLang


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


async def _khach_gui(client, **data):
    return await client.post(
        "/api/v1/doc-truyen/trang",
        files={"file": ("t.png", _anh(), "image/png")},
        data={"source_lang": SourceLang.ja.value, **data},
    )


class TestDanhSachDuongMo:
    async def test_CHI_nhung_duong_nay_mo_cho_khach(self):
        """**Bài canh cấu trúc.** Khoá chặt danh sách đường không đòi đăng nhập.

        Cổng đăng nhập gắn ở tầng router chính là thứ giữ cho 73 đường còn lại mặc định ĐÓNG.
        Chuyển thêm một endpoint sang `router_khach` là mở nó ra cho cả internet — việc đó phải
        là một quyết định có người duyệt, không phải một dòng lọt qua trong lúc sửa việc khác.

        Bài này đỏ khi danh sách đổi. Sửa nó **cùng lúc** với việc mở đường, và chỉ khi thật sự
        muốn mở.
        """
        from app.api.v1.routes import router_khach

        thuc_te = sorted(
            (r.path, m)
            for r in router_khach.routes
            for m in sorted(r.methods)
            if m not in ("HEAD", "OPTIONS")
        )
        assert thuc_te == [
            # Luồng dịch: gửi trang → hỏi tiến độ → lấy ảnh đã dịch
            ("/api/v1/doc-truyen/trang", "POST"),
            ("/api/v1/doc-truyen/trang/{page_id}", "GET"),
            ("/api/v1/doc-truyen/trang/{page_id}/anh", "GET"),
            # Gói nhiều trang thành MỘT tệp (§3.3): 24 tệp rời là 24 lần bị trình duyệt hỏi
            ("/api/v1/export-jobs/{job_id}", "GET"),
            ("/api/v1/export-jobs/{job_id}/download", "GET"),
            ("/api/v1/han-muc", "GET"),
            ("/api/v1/projects/{project_id}/export", "POST"),
        ], f"danh sách đường mở cho khách đã đổi: {thuc_te}"

    async def test_duong_khac_VAN_doi_dang_nhap(self, client_chua_dang_nhap):
        """Đối chứng: mở đường cho khách KHÔNG được làm sổng các đường còn lại."""
        r = await client_chua_dang_nhap.get("/api/v1/projects")
        assert r.status_code == 401, f"đường /projects đã sổng: {r.status_code}"


class TestKhachTaiLenDuoc:
    async def test_khong_dang_nhap_van_gui_duoc_trang(
        self, client_chua_dang_nhap, cookie_chay_duoc_tren_http
    ):
        """Nguyên tắc §4.1 đặc tả: thả tệp là chạy, không bắt khai báo gì trước."""
        r = await _khach_gui(client_chua_dang_nhap)
        assert r.status_code == 202, r.text
        assert r.json()["page_id"]

    async def test_duoc_cap_cookie_ngay_lan_dau(
        self, client_chua_dang_nhap, cookie_chay_duoc_tren_http
    ):
        r = await _khach_gui(client_chua_dang_nhap)
        assert TEN_COOKIE in r.headers.get("set-cookie", ""), r.headers

    async def test_khach_doc_lai_duoc_trang_cua_chinh_minh(
        self, client_chua_dang_nhap, cookie_chay_duoc_tren_http
    ):
        trang = (await _khach_gui(client_chua_dang_nhap)).json()["page_id"]
        r = await client_chua_dang_nhap.get(f"/api/v1/doc-truyen/trang/{trang}")
        assert r.status_code == 200, r.text
        assert r.json()["page_id"] == trang

    async def test_hai_lan_gui_dung_CHUNG_mot_chapter(
        self, client_chua_dang_nhap, session, cookie_chay_duoc_tren_http
    ):
        """Mỗi lần bấm một chapter mới thì danh sách thành bãi rác — luật này đã có từ E19,
        phải giữ đúng cho cả khách lạ."""
        await _khach_gui(client_chua_dang_nhap)
        await _khach_gui(client_chua_dang_nhap)

        dem = (await session.execute(
            sa.select(sa.func.count()).select_from(Project)
            .where(Project.chu_khach.isnot(None))
        )).scalar_one()
        assert dem == 1, f"sinh {dem} chapter cho cùng một khách"


class TestKhongAiDocDuocCuaAi:
    async def test_NGUOI_DANG_NHAP_khong_doc_duoc_truyen_cua_khach(
        self, client_chua_dang_nhap, client, cookie_chay_duoc_tren_http
    ):
        """**Bài canh nặng nhất.** Chapter của khách có `chu_so_huu_id IS NULL`.

        Trước E49 đó là nhóm "chưa có chủ" mà mọi tài khoản đăng nhập đều dùng được. Thiếu nhánh
        phân biệt thì đây là rò rỉ dữ liệu hàng loạt, không phải chuyện tiện lợi.
        """
        trang = (await _khach_gui(client_chua_dang_nhap)).json()["page_id"]

        r = await client.get(f"/api/v1/doc-truyen/trang/{trang}")
        assert r.status_code == 404, (
            f"người đăng nhập đọc được truyện của khách lạ: {r.status_code}"
        )

    async def test_khach_KHAC_khong_doc_duoc(self, client_chua_dang_nhap, st, monkeypatch):
        monkeypatch.setattr(st, "cookie_khach_secure", False)
        trang = (await _khach_gui(client_chua_dang_nhap)).json()["page_id"]

        client_chua_dang_nhap.cookies.clear()
        client_chua_dang_nhap.cookies.set(TEN_COOKIE, "cookie-cua-khach-khac")
        r = await client_chua_dang_nhap.get(f"/api/v1/doc-truyen/trang/{trang}")
        assert r.status_code == 404, f"khách khác đọc được: {r.status_code}"

    async def test_khach_khong_doc_duoc_truyen_cua_NGUOI_DANG_NHAP(
        self, client, client_chua_dang_nhap, cookie_chay_duoc_tren_http
    ):
        trang = (await client.post(
            "/api/v1/doc-truyen/trang",
            files={"file": ("t.png", _anh(), "image/png")},
            data={"source_lang": SourceLang.ja.value},
        )).json()["page_id"]

        r = await client_chua_dang_nhap.get(f"/api/v1/doc-truyen/trang/{trang}")
        assert r.status_code == 404, r.status_code

    async def test_chapter_CU_chua_co_chu_van_dung_duoc_nhu_truoc(self, client, session):
        """Không được sửa lỗi này bằng cách làm hỏng hành vi cũ: chapter từ trước slice B
        (`chu_so_huu_id NULL` **và** `chu_khach NULL`) vẫn phải mở được cho tài khoản đăng nhập."""
        cu = Project(
            name="Chapter cũ vô chủ", source_lang=SourceLang.ja, target_lang="vi",
            intended_use="personal", chu_so_huu_id=None, chu_khach=None,
        )
        session.add(cu)
        await session.commit()

        r = await client.get(f"/api/v1/projects/{cu.id}")
        assert r.status_code == 200, r.text


class TestHanMucKhachLa:
    async def test_khach_het_han_muc_thi_429(
        self, client_chua_dang_nhap, st, monkeypatch, cookie_chay_duoc_tren_http
    ):
        monkeypatch.setattr(st, "han_muc_khach_la", 2)
        monkeypatch.setattr(st, "han_muc_ip_khach_la", 99)

        for lan in range(2):
            assert (await _khach_gui(client_chua_dang_nhap)).status_code == 202, f"lượt {lan+1}"

        r = await _khach_gui(client_chua_dang_nhap)
        assert r.status_code == 429, r.status_code
        assert r.json()["detail"]["chot"] == "khach_cookie"
        assert r.json()["detail"]["co_tai_khoan"] is False

    async def test_xoa_cookie_van_bi_chot_IP_chan_QUA_HTTP(
        self, client_chua_dang_nhap, st, monkeypatch, cookie_chay_duoc_tren_http
    ):
        """Điều kiện nghiệm thu §5.2, lần này đi HẲN qua HTTP chứ không gọi thẳng hàm.

        Trần cookie để cao hơn hẳn: nếu chốt IP biến mất thì bài này đỏ, chứ không phải chốt
        cookie vô tình cứu.
        """
        monkeypatch.setattr(st, "han_muc_khach_la", 99)
        monkeypatch.setattr(st, "han_muc_ip_khach_la", 2)

        for lan in range(2):
            client_chua_dang_nhap.cookies.clear()
            assert (await _khach_gui(client_chua_dang_nhap)).status_code == 202, f"lượt {lan+1}"

        client_chua_dang_nhap.cookies.clear()
        r = await _khach_gui(client_chua_dang_nhap)
        assert r.status_code == 429, f"xoá cookie là vượt được hạn mức: {r.status_code}"
        assert r.json()["detail"]["chot"] == "khach_ip"

    async def test_chot_IP_co_that_trong_moi_truong_test(
        self, client_chua_dang_nhap, cookie_chay_duoc_tren_http, st, monkeypatch
    ):
        """Canh chính bộ test: nếu `request.client` là None thì chốt IP biến mất và bài trên
        thành xanh giả. Bài này chặn đúng cái xanh giả đó."""
        monkeypatch.setattr(st, "han_muc_khach_la", 99)
        monkeypatch.setattr(st, "han_muc_ip_khach_la", 1)

        client_chua_dang_nhap.cookies.clear()
        assert (await _khach_gui(client_chua_dang_nhap)).status_code == 202
        client_chua_dang_nhap.cookies.clear()
        r = await _khach_gui(client_chua_dang_nhap)
        assert r.status_code == 429 and r.json()["detail"]["chot"] == "khach_ip", (
            "không có chốt IP ⇒ mọi bài 'xoá cookie vẫn bị chặn' đều là xanh giả"
        )
