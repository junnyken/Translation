"""B1a — nhả chapter, và quản trị tài khoản.

Hai lỗ hổng vận hành lộ ra trong chính lượt kiểm chứng B1 trên bản chạy thật:

1. **`claim` là đường một chiều.** Một tài khoản thử nhận nhầm một chapter thật, và không có
   cách nào trả lại ngoài sửa tay trong CSDL — mà CSDL trên bản chạy thật thì không với tới được.
2. **Phát tài khoản ra được, không thu lại được.** "Cho người khác dùng" mà không gỡ được ai là
   một nửa tính năng.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models import NguoiDung, Phien, Project
from app.models.enums import IntendedUse, SourceLang, TargetLang

pytestmark = pytest.mark.anyio


async def _chapter_cua(session, chu_id):
    p = Project(
        name="c", source_lang=SourceLang.ja, target_lang=TargetLang.vi,
        intended_use=IntendedUse.personal, chu_so_huu_id=chu_id,
    )
    session.add(p)
    await session.commit()
    return p


async def _dat_quan_tri(session, nguoi_id, la=True):
    n = await session.get(NguoiDung, nguoi_id)
    n.la_quan_tri = la
    await session.commit()


class TestNhaChapter:
    async def test_nha_roi_thi_nguoi_khac_nhan_duoc(self, session, client, client_b, nguoi_a):
        """Đường ngược của `claim` — không có nó thì nhận nhầm là khoá cứng vĩnh viễn."""
        p = await _chapter_cua(session, uuid.UUID(nguoi_a[0]))
        assert (await client_b.get(f"/api/v1/projects/{p.id}")).status_code == 404

        nha = await client.post(f"/api/v1/projects/{p.id}/release")
        assert nha.status_code == 200, nha.text
        assert nha.json()["chu_so_huu_id"] is None

        assert (await client_b.get(f"/api/v1/projects/{p.id}")).status_code == 200
        assert (await client_b.post(f"/api/v1/projects/{p.id}/claim")).status_code == 200

    async def test_khong_nha_ho_chapter_cua_nguoi_khac(self, session, client_b, nguoi_a):
        """Nhả hộ = cướp gián tiếp: nhả xong rồi nhận lại là xong."""
        p = await _chapter_cua(session, uuid.UUID(nguoi_a[0]))
        assert (await client_b.post(f"/api/v1/projects/{p.id}/release")).status_code == 404
        await session.refresh(p)
        assert p.chu_so_huu_id is not None, "chapter đã bị người lạ nhả mất"

    async def test_nha_chapter_von_da_vo_chu_thi_409_chu_khong_gia_vo_thanh_cong(
        self, session, client
    ):
        p = await _chapter_cua(session, None)
        assert (await client.post(f"/api/v1/projects/{p.id}/release")).status_code == 409


class TestQuanTriNguoiDung:
    async def test_nguoi_thuong_KHONG_thay_danh_ba_tai_khoan(self, session, client, nguoi_a):
        """Và trả 404 chứ không 403 — 403 xác nhận hệ thống có phần quản trị để nhắm vào."""
        await _dat_quan_tri(session, uuid.UUID(nguoi_a[0]), False)
        r = await client.get("/api/v1/auth/users")
        assert r.status_code == 404

    async def test_quan_tri_thay_danh_ba(self, session, client, nguoi_a, nguoi_b):
        await _dat_quan_tri(session, uuid.UUID(nguoi_a[0]))
        r = await client.get("/api/v1/auth/users")
        assert r.status_code == 200
        assert {n["id"] for n in r.json()} >= {nguoi_a[0], nguoi_b[0]}
        # Không bao giờ lộ chuỗi băm mật khẩu ra API, kể cả cho quản trị.
        assert all("mat_khau_bam" not in n for n in r.json())

    async def test_khoa_tai_khoan_thi_PHIEN_DANG_MO_mat_hieu_luc_NGAY(
        self, session, client, client_b, nguoi_a, nguoi_b
    ):
        """Khoá mà để phiên cũ sống tiếp là khoá trên giấy: người đó vẫn thao tác bình thường
        tới khi phiên hết hạn — tối đa 14 ngày."""
        await _dat_quan_tri(session, uuid.UUID(nguoi_a[0]))
        assert (await client_b.get("/api/v1/projects")).status_code == 200

        r = await client.patch(f"/api/v1/auth/users/{nguoi_b[0]}", json={"dang_hoat_dong": False})
        assert r.status_code == 200

        assert (await client_b.get("/api/v1/projects")).status_code == 401
        con = (await session.execute(
            select(Phien).where(Phien.nguoi_dung_id == uuid.UUID(nguoi_b[0]))
        )).scalars().all()
        assert con == [], "còn sót phiên của tài khoản đã khoá"

    async def test_khong_tu_khoa_chinh_minh(self, session, client, nguoi_a):
        """Quản trị duy nhất tự khoá mình là không còn ai mở lại được nữa."""
        await _dat_quan_tri(session, uuid.UUID(nguoi_a[0]))
        r = await client.patch(f"/api/v1/auth/users/{nguoi_a[0]}", json={"dang_hoat_dong": False})
        assert r.status_code == 409

    async def test_khong_tu_xoa_chinh_minh(self, session, client, nguoi_a):
        await _dat_quan_tri(session, uuid.UUID(nguoi_a[0]))
        assert (await client.delete(f"/api/v1/auth/users/{nguoi_a[0]}")).status_code == 409

    async def test_xoa_tai_khoan_thi_chapter_cua_ho_VE_VO_CHU_chu_khong_bi_xoa(
        self, session, client, nguoi_a, nguoi_b
    ):
        """Điểm quan trọng nhất của khoá ngoại `ON DELETE SET NULL`.

        Xoá kèm chapter là xoá việc của người khác chỉ vì gỡ một tài khoản.
        """
        await _dat_quan_tri(session, uuid.UUID(nguoi_a[0]))
        p = await _chapter_cua(session, uuid.UUID(nguoi_b[0]))

        assert (await client.delete(f"/api/v1/auth/users/{nguoi_b[0]}")).status_code == 204

        await session.refresh(p)
        assert p.chu_so_huu_id is None, "chapter bị xoá theo tài khoản"
        assert (await client.get(f"/api/v1/projects/{p.id}")).status_code == 200

    async def test_nguoi_thuong_khong_khoa_duoc_ai(self, session, client, nguoi_a, nguoi_b):
        await _dat_quan_tri(session, uuid.UUID(nguoi_a[0]), False)
        r = await client.patch(f"/api/v1/auth/users/{nguoi_b[0]}", json={"dang_hoat_dong": False})
        assert r.status_code == 404
        assert (await session.get(NguoiDung, uuid.UUID(nguoi_b[0]))).dang_hoat_dong is True

    async def test_quan_tri_KHONG_doi_duoc_email_hay_mat_khau_nguoi_khac(
        self, session, client, nguoi_a, nguoi_b
    ):
        """Quản trị khoá được người khác, nhưng không hoá trang thành họ."""
        await _dat_quan_tri(session, uuid.UUID(nguoi_a[0]))
        r = await client.patch(
            f"/api/v1/auth/users/{nguoi_b[0]}",
            json={"dang_hoat_dong": True, "email": "cuop@x.test", "mat_khau": "abc"},
        )
        assert r.status_code == 422
