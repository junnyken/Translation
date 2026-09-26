"""E49e — quyết toán hạn mức: chốt lượt khi trang xong, hoàn lượt khi hệ thống hỏng.

## Vì sao phần này nguy hiểm hơn phần cổng chặn

Cổng chặn sai thì người dùng bị chặn oan và **kêu ngay**. Quyết toán sai thì lượt treo ở
`giu_cho` vĩnh viễn: hạn mức cứ hụt dần mỗi ngày mà không có triệu chứng nào ngoài con số sai,
và không ai biết để mà kêu.

## Ba bài canh nặng nhất

* `test_trang_le_KHONG_thuoc_me_van_duoc_chot` — quyết toán đặt trong `bao_ket_thuc_buoc`, ngay
  TRƯỚC cổng `batch_enabled`. Đẩy nhầm xuống sau cổng đó thì **mọi trang tải lẻ giữ chỗ mãi**,
  mà trang tải lẻ chính là đường khách lạ dùng.
* `test_worker_chet_thi_HOAN_luot` — worker của dự án đã bị hệ điều hành giết 3 lần. Không hoàn
  thì người dùng mất lượt vì lỗi của mình.
* `test_KHONG_hoan_trang_da_chay_xong` — hoàn ngược một trang đã tiêu là cho lượt từ hư không.
"""
from __future__ import annotations

import io

import pytest
import sqlalchemy as sa
from PIL import Image

from app.core.config import get_settings
from app.core.db_sync import sync_session
from app.models import Job, Page, SoCaiHanMuc
from app.models.enums import JobStatus, JobType, PageStatus
from app.services.quyet_toan_han_muc import (
    hoan_vi_he_thong_hong,
    quyet_toan_khi_ket_thuc_buoc,
)
from app.workers.hoi_phuc import don_job_mo_coi


def _anh() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), "white").save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def st():
    return get_settings()


async def _trang_da_giu_cho(client) -> str:
    """Tạo một trang qua ĐÚNG đường tải lên thật, nên nó có giữ chỗ hạn mức thật."""
    pid = (await client.post(
        "/api/v1/projects",
        json={"name": "Quyết toán", "source_lang": "ja", "intended_use": "personal"},
    )).json()["id"]
    r = await client.post(
        f"/api/v1/projects/{pid}/pages", files={"file": ("t.png", _anh(), "image/png")}
    )
    assert r.status_code == 202, r.text
    return r.json()["page_id"]


def _trang_thai_so_cai(page_id) -> list[str]:
    with sync_session() as s:
        return [
            r.trang_thai.value for r in s.execute(
                sa.select(SoCaiHanMuc).where(SoCaiHanMuc.trang_id == page_id)
            ).scalars().all()
        ]


def _dat_trang_thai(page_id, tt: PageStatus) -> None:
    with sync_session() as s:
        s.execute(sa.update(Page).where(Page.id == page_id).values(status=tt))
        s.commit()


class TestChotLuot:
    async def test_trang_chua_xong_thi_KHONG_chot(self, client):
        """Trang còn chạy dở thì lượt phải nằm nguyên ở `giu_cho` — chốt sớm là tiêu lượt cho
        một việc chưa chắc chạy xong."""
        trang = await _trang_da_giu_cho(client)
        assert quyet_toan_khi_ket_thuc_buoc(trang) == 0
        assert _trang_thai_so_cai(trang) == ["giu_cho"]

    async def test_trang_xong_thi_chot_luot(self, client):
        trang = await _trang_da_giu_cho(client)
        _dat_trang_thai(trang, PageStatus.typeset_done)

        assert quyet_toan_khi_ket_thuc_buoc(trang) == 1
        assert _trang_thai_so_cai(trang) == ["da_tieu"]

    async def test_ready_for_export_cung_la_DICH(self, client):
        """Hai trạng thái cùng nghĩa 'đã xong'. Sót một cái là trang đó giữ chỗ mãi."""
        trang = await _trang_da_giu_cho(client)
        _dat_trang_thai(trang, PageStatus.ready_for_export)
        assert quyet_toan_khi_ket_thuc_buoc(trang) == 1

    async def test_goi_HAI_LAN_khong_tieu_them(self, client):
        """Chạy lại bước cuối là chuyện thường; tiêu hai lần là lấy mất lượt của người dùng."""
        trang = await _trang_da_giu_cho(client)
        _dat_trang_thai(trang, PageStatus.typeset_done)

        assert quyet_toan_khi_ket_thuc_buoc(trang) == 1
        assert quyet_toan_khi_ket_thuc_buoc(trang) == 0, "lượt thứ hai tiêu thêm"
        assert _trang_thai_so_cai(trang) == ["da_tieu"]

    async def test_page_id_None_khong_no(self, client):
        assert quyet_toan_khi_ket_thuc_buoc(None) == 0

    async def test_trang_KHONG_co_giu_cho_thi_bao_0_chu_khong_loi(self, client, session):
        """Trang tạo trước khi có hạn mức. `0` là bình thường, KHÔNG phải lỗi."""
        trang = await _trang_da_giu_cho(client)
        with sync_session() as s:
            s.execute(sa.delete(SoCaiHanMuc).where(SoCaiHanMuc.trang_id == trang))
            s.commit()
        _dat_trang_thai(trang, PageStatus.typeset_done)
        assert quyet_toan_khi_ket_thuc_buoc(trang) == 0


class TestDiemNghen:
    async def test_trang_le_KHONG_thuoc_me_van_duoc_chot(self, client, st, monkeypatch):
        """**Bài canh nặng nhất.** `bao_ket_thuc_buoc` trả về sớm khi `batch_enabled` tắt.

        Quyết toán phải chạy TRƯỚC cái cổng đó. Đẩy nó xuống sau thì mọi trang tải lẻ — đúng
        đường khách lạ dùng — giữ chỗ vĩnh viễn.
        """
        from app.workers.tasks import bao_ket_thuc_buoc

        monkeypatch.setattr(st, "batch_enabled", False)
        trang = await _trang_da_giu_cho(client)
        _dat_trang_thai(trang, PageStatus.typeset_done)

        bao_ket_thuc_buoc(trang, None, "done")

        assert _trang_thai_so_cai(trang) == ["da_tieu"], (
            "trang lẻ không được chốt ⇒ quyết toán đang nằm sau cổng batch_enabled"
        )


class TestHoanLuot:
    async def test_worker_chet_thi_HOAN_luot(self, client):
        """**Bài canh.** Job `running` lúc worker khởi động = worker vừa chết giữa chừng."""
        trang = await _trang_da_giu_cho(client)
        with sync_session() as s:
            s.add(Job(type=JobType.detect, page_id=trang, status=JobStatus.running))
            s.commit()

        with sync_session() as s:
            kq = don_job_mo_coi(s, ap_dung=True)

        assert kq.luot_da_hoan == 1, f"dọn {kq.job_da_danh_dau} job mà hoàn {kq.luot_da_hoan} lượt"
        assert _trang_thai_so_cai(trang) == ["da_hoan"]

    async def test_hoan_roi_thi_giu_cho_duoc_TRANG_MOI(self, client, st, monkeypatch):
        """Hoàn mà không trả lại chỗ dùng được thì hoàn chỉ là ghi sổ cho đẹp."""
        monkeypatch.setattr(st, "han_muc_co_tai_khoan", 1)
        trang = await _trang_da_giu_cho(client)

        pid = (await client.post(
            "/api/v1/projects",
            json={"name": "X", "source_lang": "ja", "intended_use": "personal"},
        )).json()["id"]
        chan = await client.post(
            f"/api/v1/projects/{pid}/pages", files={"file": ("t.png", _anh(), "image/png")}
        )
        assert chan.status_code == 429, "chưa hết hạn mức thì bài này không chứng minh được gì"

        with sync_session() as s:
            hoan_vi_he_thong_hong(s, trang, "worker_chet")
            s.commit()

        lai = await client.post(
            f"/api/v1/projects/{pid}/pages", files={"file": ("t.png", _anh(), "image/png")}
        )
        assert lai.status_code == 202, f"hoàn rồi mà vẫn bị chặn: {lai.text}"

    async def test_KHONG_hoan_trang_da_chay_xong(self, client):
        """**Bài canh.** Trang đã xong thì lượt đã tiêu đúng — hoàn ngược là cho lượt từ hư không."""
        trang = await _trang_da_giu_cho(client)
        _dat_trang_thai(trang, PageStatus.typeset_done)
        quyet_toan_khi_ket_thuc_buoc(trang)

        with sync_session() as s:
            assert hoan_vi_he_thong_hong(s, trang, "worker_chet") == 0
            s.commit()
        assert _trang_thai_so_cai(trang) == ["da_tieu"]

    async def test_don_job_mo_coi_KHONG_hoan_trang_da_tieu(self, client):
        """Worker chết SAU khi trang đã xong: job mồ côi có thật, nhưng lượt thì không được trả."""
        trang = await _trang_da_giu_cho(client)
        _dat_trang_thai(trang, PageStatus.typeset_done)
        quyet_toan_khi_ket_thuc_buoc(trang)

        with sync_session() as s:
            s.add(Job(type=JobType.typeset, page_id=trang, status=JobStatus.running))
            s.commit()
        with sync_session() as s:
            kq = don_job_mo_coi(s, ap_dung=True)

        assert kq.job_da_danh_dau == 1, "phải có job mồ côi thật thì bài này mới có nghĩa"
        assert kq.luot_da_hoan == 0
        assert _trang_thai_so_cai(trang) == ["da_tieu"]

    async def test_che_chi_dem_KHONG_ghi_gi(self, client):
        """`ap_dung=False` là để soi trước khi động vào dữ liệu — soi mà ghi thì vô nghĩa."""
        trang = await _trang_da_giu_cho(client)
        with sync_session() as s:
            s.add(Job(type=JobType.detect, page_id=trang, status=JobStatus.running))
            s.commit()

        with sync_session() as s:
            don_job_mo_coi(s, ap_dung=False)

        assert _trang_thai_so_cai(trang) == ["giu_cho"]
