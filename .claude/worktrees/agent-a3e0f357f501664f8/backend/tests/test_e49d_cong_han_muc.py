"""E49d — cổng hạn mức ở tầng MÁY CHỦ, kiểm qua HTTP thật.

## Vì sao bộ test này gọi thẳng API

Dự án có tiền lệ đúng chỗ này: **bộ test đầy đủ vẫn xanh khi cổng chặn chỉ nằm ở giao diện.**
Ẩn nút mà API vẫn nhận thì ai mở công cụ nhà phát triển cũng vượt được, và không bài test nào
thấy — vì test gọi API chứ không bấm nút. Nên mọi bài ở đây gọi endpoint thật.

## Bốn bài canh nặng nhất

* `test_het_han_muc_thi_API_tu_choi_429` — cổng có thật hay không.
* `test_tep_hong_KHONG_mat_luot` — tệp bị từ chối vì định dạng/kích thước mà vẫn trừ lượt là
  lấy mất lượt của người dùng cho một việc chưa hề chạy.
* `test_goi_vuot_han_muc_KHONG_ghi_tep_nao_xuong_kho` — hết lượt mà vẫn ghi tệp là vừa phí
  băng thông vừa để lại rác không ai dọn.
* `test_xoa_cookie_van_bi_chot_IP_chan` — điều kiện nghiệm thu §5.2 của đặc tả. Cookie là chốt
  xoá được bằng một cú bấm; thiếu chốt IP thì hạn mức chỉ còn là gợi ý.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
import sqlalchemy as sa
from PIL import Image
from starlette.requests import Request

from app.core.config import get_settings
from app.core.cong_han_muc import giu_cho_moi_chot
from app.core.danh_tinh_khach import DanhTinhHanMuc, TEN_COOKIE, chot_cho_khach
from app.models import Page, SoCaiHanMuc
from app.models.enums import LoaiChuThe, TrangThaiHanMuc

IP_CHUNG = "198.51.100.44"


@pytest.fixture
def st():
    return get_settings()


@pytest.fixture
def tran_2(st, monkeypatch):
    """Hạ trần xuống 2 thay vì tải lên 10 lần — chính vì trần KHÔNG gõ cứng trong mã."""
    monkeypatch.setattr(st, "han_muc_co_tai_khoan", 2)
    return 2


def _anh(mau: str = "white") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), mau).save(buf, format="PNG")
    return buf.getvalue()


def _goi(so_trang: int) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i in range(so_trang):
            zf.writestr(f"p{i}.png", _anh())
    return buf.getvalue()


async def _du_an(client) -> str:
    r = await client.post(
        "/api/v1/projects",
        json={"name": "Hạn mức", "source_lang": "ja", "intended_use": "personal"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _gui_trang(client, pid: str, data: bytes | None = None):
    return await client.post(
        f"/api/v1/projects/{pid}/pages",
        files={"file": ("t.png", data if data is not None else _anh(), "image/png")},
    )


def _dem_tep(goc: str) -> int:
    return sum(1 for p in Path(goc).rglob("*") if p.is_file())


class TestCongChanThat:
    async def test_het_han_muc_thi_API_tu_choi_429(self, client, tran_2):
        """**Bài canh chính.** Gọi thẳng API, không qua giao diện."""
        pid = await _du_an(client)
        for lan in range(tran_2):
            assert (await _gui_trang(client, pid)).status_code == 202, f"lượt {lan + 1}"

        r = await _gui_trang(client, pid)
        assert r.status_code == 429, f"API vẫn nhận khi đã hết hạn mức: {r.status_code}"

    async def test_than_loi_429_noi_du_con_bao_nhieu_va_bao_gio_co_lai(self, client, tran_2):
        """Thông báo mơ hồ làm người dùng tưởng hệ thống hỏng rồi bấm lại liên tục."""
        pid = await _du_an(client)
        for _ in range(tran_2):
            await _gui_trang(client, pid)

        than = (await _gui_trang(client, pid)).json()["detail"]
        assert than["loi"] == "vuot_han_muc"
        assert than["can"] == 1
        assert than["con_lai"] == 0
        assert than["tran"] == tran_2
        assert than["chot"] == LoaiChuThe.nguoi_dung.value
        assert than["reset_sau_giay"] > 0
        assert than["reset_luc"].endswith("+07:00"), than["reset_luc"]

    async def test_429_co_header_Retry_After(self, client, tran_2):
        pid = await _du_an(client)
        for _ in range(tran_2):
            await _gui_trang(client, pid)
        r = await _gui_trang(client, pid)
        assert int(r.headers["retry-after"]) > 0

    async def test_con_han_muc_thi_van_chay_binh_thuong(self, client, tran_2):
        pid = await _du_an(client)
        assert (await _gui_trang(client, pid)).status_code == 202


class TestKhongMatLuotOan:
    async def test_tep_hong_KHONG_mat_luot(self, client, tran_2):
        """**Bài canh.** Tệp không phải ảnh ⇒ 422, và lượt phải còn NGUYÊN."""
        pid = await _du_an(client)
        assert (await _gui_trang(client, pid, b"day khong phai anh")).status_code == 422

        for lan in range(tran_2):
            assert (await _gui_trang(client, pid)).status_code == 202, (
                f"lượt {lan + 1} bị chặn ⇒ tệp hỏng đã ăn mất lượt"
            )

    async def test_tep_rong_KHONG_mat_luot(self, client, tran_2):
        pid = await _du_an(client)
        assert (await _gui_trang(client, pid, b"")).status_code == 422
        for _ in range(tran_2):
            assert (await _gui_trang(client, pid)).status_code == 202


class TestGhiSoCai:
    async def test_moi_trang_giu_cho_mot_dong_gan_dung_trang(self, client, session, tran_2):
        """`trang_id` là đường worker tra ngược để `tieu`/`hoan`. Sai cột này thì lượt không bao
        giờ được chốt, và người dùng mất lượt vĩnh viễn dù trang chạy xong."""
        pid = await _du_an(client)
        page_id = (await _gui_trang(client, pid)).json()["page_id"]

        dong = (await session.execute(
            sa.select(SoCaiHanMuc).where(SoCaiHanMuc.trang_id == page_id)
        )).scalars().all()

        assert len(dong) == 1, f"phải đúng 1 dòng cho 1 chốt, thực tế {len(dong)}"
        assert dong[0].trang_thai is TrangThaiHanMuc.giu_cho
        assert dong[0].so_trang == 1
        assert dong[0].loai_chu_the is LoaiChuThe.nguoi_dung


class TestGoiNen:
    async def test_goi_vuot_han_muc_KHONG_ghi_tep_nao_xuong_kho(
        self, client, session, storage_root, tran_2
    ):
        """**Bài canh.** Gói 5 trang trên trần 2 ⇒ từ chối NGUYÊN mẻ, và không để lại rác."""
        pid = await _du_an(client)
        truoc = _dem_tep(storage_root)

        r = await client.post(
            f"/api/v1/projects/{pid}/pages/archive",
            files={"file": ("c.cbz", _goi(5), "application/zip")},
        )

        assert r.status_code == 429, r.text
        assert _dem_tep(storage_root) == truoc, "đã ghi tệp xuống kho cho một mẻ bị từ chối"
        con = (await session.execute(
            sa.select(sa.func.count()).select_from(Page).where(Page.project_id == pid)
        )).scalar_one()
        assert con == 0, f"còn {con} trang trong CSDL cho mẻ bị từ chối"

    async def test_goi_vua_du_thi_giu_cho_du_moi_trang(self, client, session, tran_2):
        pid = await _du_an(client)
        r = await client.post(
            f"/api/v1/projects/{pid}/pages/archive",
            files={"file": ("c.cbz", _goi(2), "application/zip")},
        )
        assert r.status_code == 202, r.text

        dem = (await session.execute(
            sa.select(sa.func.count()).select_from(SoCaiHanMuc)
            .where(SoCaiHanMuc.trang_thai == TrangThaiHanMuc.giu_cho)
        )).scalar_one()
        assert dem == 2, f"giữ chỗ {dem} dòng cho 2 trang"


class TestKhachLaHaiChot:
    """Khách lạ chưa vào được đường tải lên (mọi endpoint còn bắt đăng nhập), nên phần này kiểm
    thẳng vào cổng — đúng chỗ luật hai chốt nằm."""

    @staticmethod
    def _danh_tinh(st, ma_cookie: str, ip: str = IP_CHUNG) -> DanhTinhHanMuc:
        r = Request({
            "type": "http", "http_version": "1.1", "method": "POST", "path": "/",
            "raw_path": b"/", "root_path": "", "scheme": "http", "query_string": b"",
            "headers": [(b"cookie", f"{TEN_COOKIE}={ma_cookie}".encode())],
            "client": (ip, 5000), "server": ("test", 80),
        })
        chot, moi = chot_cho_khach(r, st)
        return DanhTinhHanMuc(co_tai_khoan=False, chot=chot, cookie_moi=moi)

    async def test_khach_la_giu_cho_o_CA_HAI_chot(self, client, session, st):
        import uuid as _u

        trang = _u.uuid4()
        await giu_cho_moi_chot(session, self._danh_tinh(st, "ma-a"), st, trang_id=trang)

        loai = sorted(
            r.loai_chu_the.value for r in (await session.execute(
                sa.select(SoCaiHanMuc).where(SoCaiHanMuc.trang_id == trang)
            )).scalars().all()
        )
        assert loai == ["khach_cookie", "khach_ip"], loai

    async def test_xoa_cookie_van_bi_chot_IP_chan(self, client, session, st, monkeypatch):
        """**Bài canh — điều kiện nghiệm thu §5.2.** Cookie mới mỗi lượt, IP giữ nguyên.

        Trần IP hạ xuống 3 để bài chạy nhanh; trần cookie để cao hơn hẳn, nhờ vậy nếu chốt IP
        biến mất thì bài này ĐỎ chứ không phải chốt cookie vô tình cứu.
        """
        import uuid as _u
        from fastapi import HTTPException

        monkeypatch.setattr(st, "han_muc_ip_khach_la", 3)
        monkeypatch.setattr(st, "han_muc_khach_la", 99)

        for i in range(3):
            await giu_cho_moi_chot(
                session, self._danh_tinh(st, f"cookie-moi-{i}"), st, trang_id=_u.uuid4()
            )

        with pytest.raises(HTTPException) as loi:
            await giu_cho_moi_chot(
                session, self._danh_tinh(st, "cookie-moi-tinh"), st, trang_id=_u.uuid4()
            )

        assert loi.value.status_code == 429
        assert loi.value.detail["chot"] == LoaiChuThe.khach_ip.value, (
            "chặn bởi chốt khác ⇒ bài này không chứng minh được chốt IP"
        )

    async def test_cookie_moi_duoc_gui_kem_ngay_trong_phan_hoi_429(
        self, client, session, st, monkeypatch
    ):
        """Không cấp cookie trong chính phản hồi 429 thì mỗi lần thử lại là một khách mới, và
        chốt cookie không bao giờ chạm trần."""
        import uuid as _u
        from fastapi import HTTPException

        monkeypatch.setattr(st, "han_muc_ip_khach_la", 1)
        monkeypatch.setattr(st, "han_muc_khach_la", 99)
        monkeypatch.setattr(st, "cookie_khach_secure", True)

        await giu_cho_moi_chot(session, self._danh_tinh(st, "co-san"), st, trang_id=_u.uuid4())

        r = Request({
            "type": "http", "http_version": "1.1", "method": "POST", "path": "/",
            "raw_path": b"/", "root_path": "", "scheme": "http", "query_string": b"",
            "headers": [], "client": (IP_CHUNG, 5000), "server": ("test", 80),
        })
        chot, moi = chot_cho_khach(r, st)
        assert moi, "khách chưa có cookie mà không được cấp"

        with pytest.raises(HTTPException) as loi:
            await giu_cho_moi_chot(
                session, DanhTinhHanMuc(False, chot, moi), st, trang_id=_u.uuid4()
            )

        dat = loi.value.headers.get("set-cookie", "")
        assert TEN_COOKIE in dat, f"429 không mang cookie: {loi.value.headers}"
        thap = dat.lower()
        assert "httponly" in thap and "secure" in thap and "samesite=lax" in thap, dat
