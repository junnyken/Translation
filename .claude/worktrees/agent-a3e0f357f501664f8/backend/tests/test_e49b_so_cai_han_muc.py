"""E49b — lõi sổ cái hạn mức: giữ chỗ, tiêu, hoàn.

Ba bài canh nặng nhất ở đây, mỗi bài ứng với một cách bộ đếm đơn sẽ sai:

* `test_hai_request_song_song_KHONG_tieu_qua_han_muc` — kiểm rồi ghi trong hai bước luôn có khe
  hở; bài này chạy **hai luồng thật**, không giả lập.
* `test_thu_lai_cung_khoa_KHONG_tru_hai_lan` — HTTP thử lại là chuyện thường, và trừ hai lần thì
  người dùng mất lượt mà không hiểu vì sao.
* `test_hoan_hai_lan_KHONG_cho_them_luot` — lượt dọn job mồ côi có thể gọi hoàn nhiều lần cho
  cùng một mẻ; hoàn hai lần là **cho lượt từ hư không**.
"""
from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
import sqlalchemy as sa

from app.core.db_sync import sync_session
from app.models import SoCaiHanMuc
from app.models.enums import LoaiChuThe, TrangThaiHanMuc
from app.services.so_cai_han_muc import (
    da_dung_dong_bo,
    giu_cho_dong_bo,
    hoan,
    tieu,
)

pytestmark = pytest.mark.anyio

NGAY = date(2026, 9, 25)


@pytest.fixture
def ai_do():
    """Một chủ thể mới mỗi bài — tránh bài này ăn hạn mức của bài kia."""
    return f"khach-{uuid.uuid4().hex[:12]}"


def _dem_dong(chu_the: str) -> list[tuple[str, int, str | None]]:
    with sync_session() as s:
        rows = s.execute(
            sa.select(SoCaiHanMuc).where(SoCaiHanMuc.chu_the == chu_the)
            .order_by(SoCaiHanMuc.created_at)
        ).scalars().all()
        return [(r.trang_thai.value, r.so_trang, r.ly_do_hoan) for r in rows]


def _khoa(chu_the: str, ten: str) -> str:
    """Gắn khoá theo chủ thể.

    `khoa_idempotency` là DUY NHẤT toàn bảng — đúng thiết kế. Dùng chung `"k1"` giữa các bài thì
    bài sau tìm thấy dòng của bài trước (thuộc chủ thể khác) và coi là "đã giữ chỗ rồi".
    """
    return f"{chu_the}:{ten}"


def _giu(chu_the: str, khoa: str, so_trang: int, tran: int = 6):
    with sync_session() as s:
        kq = giu_cho_dong_bo(
            s, khoa=_khoa(chu_the, khoa), loai=LoaiChuThe.khach_cookie, chu_the=chu_the,
            ngay=NGAY, so_trang=so_trang, tran=tran,
        )
        s.commit()
        return kq


def _da_dung(chu_the: str) -> int:
    with sync_session() as s:
        return da_dung_dong_bo(s, LoaiChuThe.khach_cookie, chu_the, NGAY)


class TestGiuCho:
    async def test_trong_han_muc_thi_giu_duoc(self, client, ai_do):
        kq = _giu(ai_do, "k1", 4)
        assert (kq.thanh_cong, kq.da_dung, kq.con_lai) == (True, 4, 2)

    async def test_vuot_han_muc_thi_tu_choi_NGUYEN_me(self, client, ai_do):
        """Xử lý một phần âm thầm sẽ khiến người dùng nhận nửa chapter mà không hiểu vì sao."""
        _giu(ai_do, "k1", 4)
        kq = _giu(ai_do, "k2", 3)

        assert kq.thanh_cong is False
        assert kq.ly_do == "vuot_han_muc"
        assert _da_dung(ai_do) == 4, "mẻ bị từ chối mà vẫn trừ lượt"

    async def test_giu_cho_van_CHIEM_han_muc(self, client, ai_do):
        """`giu_cho` phải được tính vào phần đã dùng — nếu không, hai mẻ đang chạy dở sẽ cùng
        thấy hạn mức còn nguyên."""
        _giu(ai_do, "k1", 5)
        assert _da_dung(ai_do) == 5
        assert _giu(ai_do, "k2", 2).thanh_cong is False

    async def test_hai_request_song_song_KHONG_tieu_qua_han_muc(self, client, ai_do):
        """**Bài canh nặng nhất.** Hai luồng THẬT, cùng chủ thể, mỗi luồng xin 4 trên trần 6.

        Chỉ một được. Không có khoá thì cả hai cùng đọc "đã dùng 0", cùng thấy đủ, cùng ghi ⇒
        tiêu 8 trên trần 6.

        ## Engine riêng: đủ kết nối cho hai luồng, không phụ thuộc bể dùng chung

        Bài này cần **hai kết nối thật cùng lúc**. Bể dùng chung của bộ test có
        `pool_size=2, max_overflow=2`, đủ — nhưng nó còn phải phục vụ các fixture khác trong cùng
        bài, nên engine riêng làm ý định rõ ràng và không phụ thuộc vào chỗ còn trống của bể.

        ⚠️ **ĐÍNH CHÍNH — docstring này từng ghi một nguyên nhân SAI.** Bản trước nói bài này treo
        vì phần cấp phiên dùng chung ràng hai luồng vào một kết nối. **Không phải.** Lần treo hôm
        25-09 có nguyên nhân hoàn toàn khác: lúc đó có **một lượt `pytest` khác đang chạy nền**
        trên cùng CSDL, và `test_migration.py` của lượt mới cố `downgrade base` trong khi lượt cũ
        còn giữ bảng `job`.

        Dấu hiệu đã chỉ đúng ngay từ đầu mà bị bỏ qua: truy vấn `pg_locks` cho **`advisory = 0`**
        — khoá tư vấn của chính hàm đang kiểm **không hề tham gia** vào vụ treo.

        **Bài học: chạy một lượt `pytest` một lúc.** Nhiều lượt chung một Postgres cho ra đỏ giả
        và treo ở những chỗ chẳng liên quan gì tới thay đổi đang làm.
        """
        from sqlalchemy.orm import sessionmaker

        from tests.conftest import TEST_DB_URL, _sync_url

        eng = sa.create_engine(_sync_url(TEST_DB_URL), pool_size=4, max_overflow=4)
        Phien = sessionmaker(bind=eng, expire_on_commit=False)

        def _giu_rieng(ten: str):
            with Phien() as s:
                kq = giu_cho_dong_bo(
                    s, khoa=_khoa(ai_do, ten), loai=LoaiChuThe.khach_cookie,
                    chu_the=ai_do, ngay=NGAY, so_trang=4, tran=6,
                )
                s.commit()
                return kq

        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                ra = [f.result(timeout=30) for f in [
                    pool.submit(_giu_rieng, "song-song-a"),
                    pool.submit(_giu_rieng, "song-song-b"),
                ]]
        finally:
            eng.dispose()

        assert sum(1 for k in ra if k.thanh_cong) == 1, (
            f"phải đúng 1 lượt thành công, thực tế {[k.thanh_cong for k in ra]}"
        )
        assert _da_dung(ai_do) == 4, f"tiêu quá hạn mức: {_da_dung(ai_do)}/6"

    async def test_thu_lai_cung_khoa_KHONG_tru_hai_lan(self, client, ai_do):
        a = _giu(ai_do, "cung-khoa", 3)
        b = _giu(ai_do, "cung-khoa", 3)

        assert a.thanh_cong and b.thanh_cong
        assert b.da_co_san is True, "lượt thử lại phải được nhận ra"
        assert _da_dung(ai_do) == 3, "thử lại bị trừ thêm lượt"
        assert len(_dem_dong(ai_do)) == 1, "thử lại tạo thêm dòng trong sổ cái"


class TestTieu:
    async def test_tieu_xong_van_chiem_dung_so_trang(self, client, ai_do):
        _giu(ai_do, "k1", 3)
        with sync_session() as s:
            assert tieu(s, khoa=_khoa(ai_do, "k1")) is True
            s.commit()
        assert _da_dung(ai_do) == 3
        assert _dem_dong(ai_do) == [("da_tieu", 3, None)]

    async def test_tieu_hai_lan_KHONG_tieu_them(self, client, ai_do):
        _giu(ai_do, "k1", 3)
        with sync_session() as s:
            tieu(s, khoa=_khoa(ai_do, "k1")); s.commit()
        with sync_session() as s:
            assert tieu(s, khoa=_khoa(ai_do, "k1")) is True, "chạy lại task không được coi là lỗi"
            s.commit()
        assert _da_dung(ai_do) == 3

    async def test_thanh_cong_MOT_PHAN_thi_chi_tieu_phan_thanh_cong(self, client, ai_do):
        """Giữ chỗ 5, xong 3, hỏng 2 ⇒ tiêu 3 và hoàn 2. Phần hỏng do hệ thống, không phải lỗi
        người dùng."""
        _giu(ai_do, "k1", 5)
        with sync_session() as s:
            tieu(s, khoa=_khoa(ai_do, "k1"), so_trang_thanh_cong=3)
            s.commit()

        assert _da_dung(ai_do) == 3, "hoàn thiếu hoặc tiêu thừa"
        dong = _dem_dong(ai_do)
        assert ("da_tieu", 3, None) in dong
        assert any(t == "da_hoan" and n == 2 for t, n, _ in dong), dong

    async def test_khong_trang_nao_thanh_cong_thi_hoan_HET(self, client, ai_do):
        _giu(ai_do, "k1", 4)
        with sync_session() as s:
            tieu(s, khoa=_khoa(ai_do, "k1"), so_trang_thanh_cong=0)
            s.commit()
        assert _da_dung(ai_do) == 0


class TestHoan:
    async def test_hoan_tra_lai_luot(self, client, ai_do):
        _giu(ai_do, "k1", 5)
        with sync_session() as s:
            assert hoan(s, khoa=_khoa(ai_do, "k1"), ly_do="worker_chet") is True
            s.commit()

        assert _da_dung(ai_do) == 0
        assert _dem_dong(ai_do) == [("da_hoan", 5, "worker_chet")]
        assert _giu(ai_do, "k2", 5).thanh_cong is True, "hoàn rồi mà vẫn bị chặn"

    async def test_hoan_hai_lan_KHONG_cho_them_luot(self, client, ai_do):
        """Lượt dọn job mồ côi có thể gọi hoàn nhiều lần cho cùng một mẻ."""
        _giu(ai_do, "k1", 4)
        for _ in range(3):
            with sync_session() as s:
                assert hoan(s, khoa=_khoa(ai_do, "k1"), ly_do="het_luot_thu_lai") is True
                s.commit()

        assert _da_dung(ai_do) == 0
        assert len(_dem_dong(ai_do)) == 1, "hoàn lặp tạo thêm dòng"

    async def test_KHONG_hoan_dong_da_tieu(self, client, ai_do):
        """Việc đã chạy xong thì lượt đã tiêu đúng — hoàn ngược là cho lượt từ hư không."""
        _giu(ai_do, "k1", 3)
        with sync_session() as s:
            tieu(s, khoa=_khoa(ai_do, "k1")); s.commit()
        with sync_session() as s:
            assert hoan(s, khoa=_khoa(ai_do, "k1"), ly_do="nham") is False
            s.commit()
        assert _da_dung(ai_do) == 3

    async def test_khoa_khong_ton_tai_thi_bao_KHONG_lam_gi(self, client, ai_do):
        with sync_session() as s:
            assert hoan(s, khoa="khoa-khong-co-that", ly_do="x") is False
            assert tieu(s, khoa="khoa-khong-co-that") is False
