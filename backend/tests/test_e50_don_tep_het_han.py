"""E50 — vòng đời tệp: chapter tự xoá sau khi xong.

## Bốn bài canh nặng nhất

* `test_KHONG_xoa_chapter_con_viec_dang_chay` — §2.4 đặc tả. Xoá tệp giữa lúc worker đang đọc là
  cách chắc chắn tạo ra lỗi **không tái hiện được**.
* `test_xoa_DU_CA_BA_tien_to` — hiện vật nằm ở ba chỗ, và `previews/` đánh theo **trang** chứ
  không theo chapter. Sót nó thì đĩa đầy dần trong im lặng.
* `test_het_han_KHONG_hoan_luot_han_muc` — §2.8. Hết hạn vì không tải kịp thì lượt vẫn đã dùng,
  khác hẳn §1.3(b) nơi hệ thống hỏng nên phải hoàn.
* `test_dong_ho_dem_tu_luc_XONG_khong_phai_luc_tai_len` — §2.3. Đếm từ lúc tải lên thì một
  chapter 24 trang hết hạn **trước khi dịch xong**.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa

from app.core.config import get_settings
from app.core.db_sync import sync_session
from app.models import Job, Page, Project, SoCaiHanMuc
from app.models.enums import (
    JobStatus,
    JobType,
    LoaiChuThe,
    PageStatus,
    SourceLang,
    TrangThaiHanMuc,
)
from app.services.don_tep_het_han import (
    danh_dau_het_han,
    don_chapter_het_han,
)
from app.services.storage import get_storage
from app.services.typeset.paths import preview_relative_path

GIO = timezone.utc


@pytest.fixture
def st():
    return get_settings()


def _tao_chapter(*, chu_khach: str | None = None, so_trang: int = 1) -> tuple[uuid.UUID, list]:
    """Chapter + trang, tạo thẳng bằng SQL đồng bộ — phần dọn cũng chạy ở phiên đồng bộ."""
    with sync_session() as s:
        p = Project(
            name="Chapter E50", source_lang=SourceLang.ja, target_lang="vi",
            intended_use="personal", chu_khach=chu_khach,
        )
        s.add(p)
        s.flush()
        trang = []
        for i in range(so_trang):
            pg = Page(
                project_id=p.id, image_path=f"projects/{p.id}/pages/x{i}.png",
                order=i + 1, status=PageStatus.typeset_done,
            )
            s.add(pg)
            s.flush()
            trang.append(pg.id)
        s.commit()
        return p.id, trang


def _them_job(page_id, trang_thai: JobStatus) -> None:
    with sync_session() as s:
        s.add(Job(type=JobType.detect, page_id=page_id, status=trang_thai))
        s.commit()


def _ghi_ba_tien_to(project_id, page_ids) -> list[str]:
    """Ghi hiện vật vào ĐỦ ba tiền tố thật, qua đúng kho lưu trữ sản phẩm dùng."""
    kho = get_storage()
    duong = [f"projects/{project_id}/pages/goc.png", f"exports/{project_id}/chapter.cbz"]
    duong += [preview_relative_path(pid) for pid in page_ids]
    for d in duong:
        kho.save(d, b"x" * 8)
    return duong


def _con_lai_trong_kho(duong: list[str]) -> list[str]:
    kho = get_storage()
    con = []
    for d in duong:
        try:
            kho.read(d)
            con.append(d)
        except Exception:  # noqa: BLE001 — đọc không được = đã xoá, đúng ý
            pass
    return con


def _moc(project_id) -> datetime | None:
    with sync_session() as s:
        return s.get(Project, project_id).het_han_luc


def _con_chapter(project_id) -> bool:
    with sync_session() as s:
        return s.get(Project, project_id) is not None


class TestDatMocHetHan:
    async def test_dong_ho_dem_tu_luc_XONG_khong_phai_luc_tai_len(self, client, st, monkeypatch):
        """**Bài canh.** Một chapter 24 trang mất 30–40 phút để chạy."""
        monkeypatch.setattr(st, "giu_ket_qua_phut", 30)
        pid, _ = _tao_chapter()
        luc = datetime(2026, 9, 26, 10, 0, tzinfo=GIO)

        with sync_session() as s:
            assert danh_dau_het_han(s, pid, bay_gio=luc) is True
            s.commit()

        assert _moc(pid) == luc + timedelta(minutes=30)

    async def test_con_viec_dang_chay_thi_KHONG_dat_moc(self, client):
        pid, trang = _tao_chapter()
        _them_job(trang[0], JobStatus.running)

        with sync_session() as s:
            assert danh_dau_het_han(s, pid) is False
            s.commit()
        assert _moc(pid) is None

    async def test_job_con_XEP_HANG_cung_tinh_la_dang_chay(self, client):
        """`queued` là việc CHƯA chạy, không phải việc đã xong. Tính nhầm nó là xong thì chapter
        hết hạn trong khi hàng đợi còn đầy."""
        pid, trang = _tao_chapter()
        _them_job(trang[0], JobStatus.queued)

        with sync_session() as s:
            assert danh_dau_het_han(s, pid) is False
            s.commit()

    async def test_goi_lai_KHONG_doi_moc(self, client):
        """Dời mốc mỗi lần chạy lại một bước thì chapter không bao giờ hết hạn."""
        pid, _ = _tao_chapter()
        mot = datetime(2026, 9, 26, 10, 0, tzinfo=GIO)
        with sync_session() as s:
            danh_dau_het_han(s, pid, bay_gio=mot)
            s.commit()
        dau = _moc(pid)

        with sync_session() as s:
            assert danh_dau_het_han(s, pid, bay_gio=mot + timedelta(hours=5)) is False
            s.commit()
        assert _moc(pid) == dau, "mốc bị dời"

    async def test_chay_lai_mot_trang_thi_XOA_moc(self, client):
        """Người dùng bấm 'chạy lại' sau khi chapter đã xong — chapter không được biến mất giữa
        chừng."""
        pid, trang = _tao_chapter()
        with sync_session() as s:
            danh_dau_het_han(s, pid)
            s.commit()
        assert _moc(pid) is not None

        _them_job(trang[0], JobStatus.running)
        with sync_session() as s:
            assert danh_dau_het_han(s, pid) is False
            s.commit()
        assert _moc(pid) is None, "chapter đang chạy lại mà vẫn giữ mốc tự xoá"

    async def test_chapter_RONG_khong_dat_moc(self, client):
        """Chapter vừa tạo, chưa trang nào — 'xong' ở đây là vô nghĩa."""
        with sync_session() as s:
            p = Project(name="Rỗng", source_lang=SourceLang.ja, target_lang="vi",
                        intended_use="personal")
            s.add(p)
            s.commit()
            pid = p.id
        with sync_session() as s:
            assert danh_dau_het_han(s, pid) is False
            s.commit()


class TestDonTep:
    async def test_chua_qua_han_thi_KHONG_xoa(self, client):
        pid, trang = _tao_chapter()
        duong = _ghi_ba_tien_to(pid, trang)
        with sync_session() as s:
            danh_dau_het_han(s, pid)
            s.commit()

        with sync_session() as s:
            kq = don_chapter_het_han(s)
        assert kq.chapter_da_xoa == 0
        assert _con_chapter(pid) is True
        assert len(_con_lai_trong_kho(duong)) == len(duong)

    async def test_qua_han_thi_xoa_ca_dong_CSDL(self, client):
        pid, trang = _tao_chapter(so_trang=2)
        with sync_session() as s:
            danh_dau_het_han(s, pid, bay_gio=datetime(2020, 1, 1, tzinfo=GIO))
            s.commit()

        with sync_session() as s:
            kq = don_chapter_het_han(s)

        assert kq.chapter_da_xoa == 1
        assert _con_chapter(pid) is False
        with sync_session() as s:
            con = s.execute(
                sa.select(sa.func.count()).select_from(Page).where(Page.project_id == pid)
            ).scalar_one()
        assert con == 0, f"còn {con} trang mồ côi — xoá dòng mà để lại trang là dữ liệu treo"

    async def test_xoa_DU_CA_BA_tien_to(self, client):
        """**Bài canh nặng nhất của phần dọn.**

        `previews/` đánh theo TRANG chứ không theo chapter, nên nó là cái dễ sót nhất. Sót thì
        đĩa đầy dần mà không ai thấy cho tới khi hỏng.
        """
        pid, trang = _tao_chapter(so_trang=2)
        duong = _ghi_ba_tien_to(pid, trang)
        assert len(_con_lai_trong_kho(duong)) == 4, "bài test chưa ghi đủ tệp thì không canh được gì"

        with sync_session() as s:
            danh_dau_het_han(s, pid, bay_gio=datetime(2020, 1, 1, tzinfo=GIO))
            s.commit()
        with sync_session() as s:
            don_chapter_het_han(s)

        con = _con_lai_trong_kho(duong)
        assert con == [], f"còn sót {len(con)} tệp: {con}"

    async def test_KHONG_xoa_chapter_con_viec_dang_chay(self, client):
        """**Bài canh.** §2.4 — xoá tệp giữa lúc worker đang đọc tạo ra lỗi không tái hiện được."""
        pid, trang = _tao_chapter()
        duong = _ghi_ba_tien_to(pid, trang)
        with sync_session() as s:
            danh_dau_het_han(s, pid, bay_gio=datetime(2020, 1, 1, tzinfo=GIO))
            s.commit()
        _them_job(trang[0], JobStatus.running)

        with sync_session() as s:
            kq = don_chapter_het_han(s)

        assert kq.chapter_da_xoa == 0
        assert kq.chapter_bo_qua_dang_chay == 1
        assert _con_chapter(pid) is True
        assert len(_con_lai_trong_kho(duong)) == len(duong), "đã xoá tệp của chapter đang chạy"

    async def test_che_chi_dem_KHONG_ghi_gi(self, client):
        pid, trang = _tao_chapter()
        duong = _ghi_ba_tien_to(pid, trang)
        with sync_session() as s:
            danh_dau_het_han(s, pid, bay_gio=datetime(2020, 1, 1, tzinfo=GIO))
            s.commit()

        with sync_session() as s:
            kq = don_chapter_het_han(s, ap_dung=False)

        assert kq.chapter_da_xoa == 1, "chế độ chỉ đếm phải nói đúng việc chế độ sửa sẽ làm"
        assert _con_chapter(pid) is True
        assert len(_con_lai_trong_kho(duong)) == len(duong)

    async def test_gioi_han_moi_luot(self, client):
        """Lượt dọn chạy chung tiến trình worker đã bị giết 3 lần — không được kéo dài vô hạn."""
        for _ in range(3):
            pid, _ = _tao_chapter()
            with sync_session() as s:
                danh_dau_het_han(s, pid, bay_gio=datetime(2020, 1, 1, tzinfo=GIO))
                s.commit()

        with sync_session() as s:
            kq = don_chapter_het_han(s, gioi_han=2)
        assert kq.chapter_da_xoa == 2


class TestKhongHoanLuot:
    async def test_het_han_KHONG_hoan_luot_han_muc(self, client):
        """**Bài canh.** §2.8 — hạn mức tiêu vào lúc XỬ LÝ, không phải lúc tải về.

        Chạy được là nhờ `so_cai_han_muc.trang_id` cố ý KHÔNG có khoá ngoại. Thêm
        `ForeignKey(..., ondelete='CASCADE')` vào cột đó thì bài này đỏ — và người dùng được
        lượt từ hư không.
        """
        pid, trang = _tao_chapter()
        with sync_session() as s:
            s.add(SoCaiHanMuc(
                khoa_idempotency=f"trang:{trang[0]}#nguoi_dung",
                loai_chu_the=LoaiChuThe.nguoi_dung, chu_the="ai-do",
                ngay_han_muc=datetime(2026, 9, 26, tzinfo=GIO).date(),
                so_trang=1, trang_thai=TrangThaiHanMuc.da_tieu, trang_id=trang[0],
            ))
            danh_dau_het_han(s, pid, bay_gio=datetime(2020, 1, 1, tzinfo=GIO))
            s.commit()

        with sync_session() as s:
            don_chapter_het_han(s)

        with sync_session() as s:
            dong = s.execute(
                sa.select(SoCaiHanMuc).where(SoCaiHanMuc.trang_id == trang[0])
            ).scalars().all()

        assert len(dong) == 1, "xoá chapter đã kéo theo sổ cái ⇒ cho lượt từ hư không"
        assert dong[0].trang_thai is TrangThaiHanMuc.da_tieu


class TestCongTacTaiKhoan:
    async def test_tat_cong_tac_thi_CHI_don_chapter_cua_khach(self, client, st, monkeypatch):
        """`tu_xoa_cho_tai_khoan=False` là công tắc để KHÔNG xoá dữ liệu của người đã đăng ký."""
        monkeypatch.setattr(st, "tu_xoa_cho_tai_khoan", False)
        cua_khach, _ = _tao_chapter(chu_khach="bam-cookie-abc")
        cua_tai_khoan, _ = _tao_chapter(chu_khach=None)
        for pid in (cua_khach, cua_tai_khoan):
            with sync_session() as s:
                danh_dau_het_han(s, pid, bay_gio=datetime(2020, 1, 1, tzinfo=GIO))
                s.commit()

        with sync_session() as s:
            kq = don_chapter_het_han(s)

        assert kq.chapter_da_xoa == 1
        assert _con_chapter(cua_khach) is False
        assert _con_chapter(cua_tai_khoan) is True, "đã xoá chapter của tài khoản dù công tắc tắt"

    async def test_bat_cong_tac_thi_don_CA_HAI(self, client, st, monkeypatch):
        monkeypatch.setattr(st, "tu_xoa_cho_tai_khoan", True)
        cua_khach, _ = _tao_chapter(chu_khach="bam-cookie-xyz")
        cua_tai_khoan, _ = _tao_chapter(chu_khach=None)
        for pid in (cua_khach, cua_tai_khoan):
            with sync_session() as s:
                danh_dau_het_han(s, pid, bay_gio=datetime(2020, 1, 1, tzinfo=GIO))
                s.commit()

        with sync_session() as s:
            kq = don_chapter_het_han(s)
        assert kq.chapter_da_xoa == 2


class TestLichChay:
    async def test_lich_MAC_DINH_TAT(self, st):
        """Đây là hành vi XOÁ DỮ LIỆU KHÔNG HOÀN TÁC ĐƯỢC. Mặc định phải là tắt."""
        assert st.bat_lich_don_tep is False

    async def test_task_khong_xoa_gi_khi_lich_TAT(self, client, st, monkeypatch):
        from app.workers.tasks import don_tep_het_han_task

        monkeypatch.setattr(st, "bat_lich_don_tep", False)
        pid, _ = _tao_chapter()
        with sync_session() as s:
            danh_dau_het_han(s, pid, bay_gio=datetime(2020, 1, 1, tzinfo=GIO))
            s.commit()

        ra = don_tep_het_han_task()
        assert ra["status"] == "tat"
        assert _con_chapter(pid) is True, "cờ tắt mà vẫn xoá dữ liệu"

    async def test_task_don_that_khi_lich_BAT(self, client, st, monkeypatch):
        from app.workers import tasks as m

        monkeypatch.setattr(m.settings, "bat_lich_don_tep", True)
        pid, _ = _tao_chapter()
        with sync_session() as s:
            danh_dau_het_han(s, pid, bay_gio=datetime(2020, 1, 1, tzinfo=GIO))
            s.commit()

        ra = m.don_tep_het_han_task()
        assert ra["status"] == "done", ra
        assert ra["chapter_da_xoa"] == 1
        assert _con_chapter(pid) is False

    async def test_lenh_worker_local_va_production_deu_co_beat(self):
        """Lệch ở đây nghĩa là bàn thử không tái hiện được lịch chạy định kỳ."""
        from pathlib import Path

        goc = Path(__file__).resolve().parents[2]
        prod = (goc / "backend" / "deploy-start.sh").read_text(encoding="utf-8")
        local = (goc / "deploy" / "docker-compose.yml").read_text(encoding="utf-8")
        for ten, noi_dung in (("deploy-start.sh", prod), ("docker-compose.yml", local)):
            assert " -B " in noi_dung, f"{ten} thiếu `-B` ⇒ lịch dọn không bao giờ chạy"
            assert "--schedule=/tmp/" in noi_dung, (
                f"{ten} để beat ghi tệp lịch vào thư mục làm việc — có thể chỉ-đọc trên hosting"
            )
