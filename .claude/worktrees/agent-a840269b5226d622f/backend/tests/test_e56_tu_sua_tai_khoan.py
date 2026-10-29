"""E56 — người dùng tự đổi tên hiển thị và mật khẩu.

## Lỗ đang vá

Màn tài khoản (§4.4, E54) **chỉ đọc**. Không có đường nào để người dùng tự đổi mật khẩu, nên một
mật khẩu bị lộ chỉ sửa được bằng cách nhờ quản trị — mà quản trị cũng **không có** đường đổi mật
khẩu người khác (cố ý: `DoiTrangThaiRequest` ghi rõ "không được phép hoá trang thành họ"). Tức là
trước E56 mật khẩu đã lộ là **không thể xoay**.

## Ba bài canh nặng nhất

`test_doi_mat_khau_THU_HOI_cac_phien_khac` — đổi mật khẩu mà để phiên cũ sống tiếp là *đổi trên
giấy*. Người ta đổi mật khẩu chính vì nghi có người khác đang vào được; giữ phiên của người đó
lại là phá đúng mục đích của thao tác.

`test_sai_mat_khau_cu_thi_KHONG_doi_duoc` — không đòi mật khẩu cũ thì một phiên bị mượn (máy công
cộng chưa đăng xuất) **chiếm hẳn** được tài khoản.

`test_bi_tu_choi_thi_ten_hien_cung_KHONG_bi_luu` — một lượt gọi gửi cả tên lẫn mật khẩu mà mật
khẩu sai thì **không được lưu nửa vời**. Lưu nửa vời là trả lỗi cho người dùng trong khi đã đổi
một phần dữ liệu của họ.
"""
from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from app.core import mat_khau as mk
from app.core import phien as ph
from app.core.db_sync import sync_session

DUONG = "/api/v1/auth/me"
MK_CU = "mat-khau-cu-12345"
MK_MOI = "mat-khau-moi-67890"


def _tao_nguoi(mat_khau: str = MK_CU, *, so_phien: int = 1) -> tuple[str, list[str]]:
    """Tạo tài khoản RIÊNG cho từng bài + `so_phien` phiên. Trả `(id, [mã phiên thô])`.

    Cố ý không dùng `nguoi_a` của conftest: bảng `nguoi_dung` KHÔNG bị TRUNCATE giữa các test, nên
    một bài đổi mật khẩu của tài khoản dùng chung sẽ rò trạng thái sang mọi bài xếp sau. Lỗi đó
    biểu hiện là "xanh khi chạy riêng, đỏ khi chạy chung" — thứ khó truy nhất trong một bộ test.
    """
    uid = uuid.uuid4()
    email = f"e56-{uid.hex[:10]}@test.local"
    ma_thos: list[str] = []
    with sync_session() as s:
        s.execute(
            sa.text(
                "INSERT INTO nguoi_dung (id, email, ten_hien, mat_khau_bam, dang_hoat_dong,"
                " la_quan_tri) VALUES (:id, :e, :t, :b, true, false)"
            ),
            {"id": uid, "e": email, "t": "Tên Cũ", "b": mk.bam(mat_khau)},
        )
        for _ in range(so_phien):
            ma_tho = ph.sinh_ma()
            ma_thos.append(ma_tho)
            s.execute(
                sa.text(
                    "INSERT INTO phien (id, nguoi_dung_id, ma_bam, het_han)"
                    " VALUES (:id, :u, :h, :x)"
                ),
                {"id": uuid.uuid4(), "u": uid, "h": ph.bam_ma(ma_tho), "x": ph.han_moi()},
            )
        s.commit()
    return str(uid), ma_thos


def _doc_nguoi(uid: str) -> tuple[str, str]:
    """Trả `(ten_hien, mat_khau_bam)` đọc TRỰC TIẾP từ CSDL, không qua API."""
    with sync_session() as s:
        hang = s.execute(
            sa.text("SELECT ten_hien, mat_khau_bam FROM nguoi_dung WHERE id = :id"), {"id": uid}
        ).one()
    return hang[0], hang[1]


def _dem_phien(uid: str) -> int:
    with sync_session() as s:
        return int(
            s.execute(
                sa.text("SELECT count(*) FROM phien WHERE nguoi_dung_id = :u"), {"u": uid}
            ).scalar_one()
        )


def _phien_con_song(ma_tho: str) -> bool:
    with sync_session() as s:
        return bool(
            s.execute(
                sa.text("SELECT count(*) FROM phien WHERE ma_bam = :h"),
                {"h": ph.bam_ma(ma_tho)},
            ).scalar_one()
        )


def _khach(session, ma_tho: str):
    from tests.conftest import _client

    return _client(session, {"Authorization": f"Bearer {ma_tho}"})


# ── Tên hiển thị ──────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_doi_duoc_ten_hien(session):
    uid, (ma,) = _tao_nguoi()
    async with _khach(session, ma) as c:
        r = await c.patch(DUONG, json={"ten_hien": "Tên Mới"})
    assert r.status_code == 200, r.text
    assert r.json()["nguoi_dung"]["ten_hien"] == "Tên Mới"
    assert _doc_nguoi(uid)[0] == "Tên Mới"


@pytest.mark.asyncio
async def test_ten_hien_rong_thi_lay_phan_truoc_a_moc(session):
    """Cùng luật với lúc đăng ký. Khác luật thì xoá trắng ô tên cho ra tài khoản KHÔNG có tên,
    trạng thái mà một tài khoản mới không bao giờ rơi vào."""
    uid, (ma,) = _tao_nguoi()
    async with _khach(session, ma) as c:
        r = await c.patch(DUONG, json={"ten_hien": "   "})
    assert r.status_code == 200, r.text
    ten = _doc_nguoi(uid)[0]
    assert ten.startswith("e56-") and "@" not in ten


@pytest.mark.asyncio
async def test_doi_ten_KHONG_thu_hoi_phien_nao(session):
    """Đổi tên là vô hại — đăng xuất các thiết bị khác vì một việc vô hại là hình phạt vô cớ."""
    uid, mas = _tao_nguoi(so_phien=3)
    async with _khach(session, mas[0]) as c:
        r = await c.patch(DUONG, json={"ten_hien": "Tên Mới"})
    assert r.status_code == 200
    assert r.json()["so_phien_khac_da_thu_hoi"] == 0
    assert _dem_phien(uid) == 3


# ── Mật khẩu ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_doi_duoc_mat_khau_va_mat_khau_moi_dung_la_moi(session):
    uid, (ma,) = _tao_nguoi()
    bam_cu = _doc_nguoi(uid)[1]
    async with _khach(session, ma) as c:
        r = await c.patch(DUONG, json={"mat_khau_cu": MK_CU, "mat_khau_moi": MK_MOI})
    assert r.status_code == 200, r.text
    assert r.json()["da_doi_mat_khau"] is True

    bam_moi = _doc_nguoi(uid)[1]
    assert bam_moi != bam_cu
    # Khẳng định vào HÀNH VI, không chỉ "chuỗi băm đã khác": băm khác có thể chỉ vì đổi muối.
    assert mk.kiem(MK_MOI, bam_moi) is True
    assert mk.kiem(MK_CU, bam_moi) is False


@pytest.mark.asyncio
async def test_sai_mat_khau_cu_thi_KHONG_doi_duoc(session):
    """BÀI CANH NẶNG: không đòi mật khẩu cũ thì một phiên bị mượn chiếm hẳn được tài khoản."""
    uid, (ma,) = _tao_nguoi()
    async with _khach(session, ma) as c:
        r = await c.patch(DUONG, json={"mat_khau_cu": "sai-bet-roi-123", "mat_khau_moi": MK_MOI})
    assert r.status_code == 400
    # Đối chứng âm: mật khẩu CŨ phải còn dùng được, mật khẩu mới phải KHÔNG.
    bam = _doc_nguoi(uid)[1]
    assert mk.kiem(MK_CU, bam) is True
    assert mk.kiem(MK_MOI, bam) is False


@pytest.mark.asyncio
async def test_doi_mat_khau_THU_HOI_cac_phien_khac(session):
    """BÀI CANH NẶNG NHẤT: đổi mật khẩu mà để phiên cũ sống là đổi TRÊN GIẤY."""
    uid, mas = _tao_nguoi(so_phien=3)
    dang_dung, khac_1, khac_2 = mas

    async with _khach(session, dang_dung) as c:
        r = await c.patch(DUONG, json={"mat_khau_cu": MK_CU, "mat_khau_moi": MK_MOI})
    assert r.status_code == 200, r.text
    assert r.json()["so_phien_khac_da_thu_hoi"] == 2

    assert _phien_con_song(khac_1) is False
    assert _phien_con_song(khac_2) is False
    assert _dem_phien(uid) == 1


@pytest.mark.asyncio
async def test_doi_mat_khau_GIU_LAI_phien_dang_dung(session):
    """Đăng xuất chính người vừa đổi mật khẩu là hình phạt cho hành vi đúng — và họ sẽ tưởng
    thao tác thất bại."""
    _, mas = _tao_nguoi(so_phien=2)
    dang_dung = mas[0]

    async with _khach(session, dang_dung) as c:
        r = await c.patch(DUONG, json={"mat_khau_cu": MK_CU, "mat_khau_moi": MK_MOI})
        assert r.status_code == 200
        # Vẫn gọi được bằng CHÍNH mã phiên đó ngay sau khi đổi.
        r2 = await c.get("/api/v1/auth/me")
    assert r2.status_code == 200, r2.text
    assert _phien_con_song(dang_dung) is True


@pytest.mark.asyncio
async def test_mat_khau_moi_ngan_bi_tu_choi(session):
    """Dùng lại đúng ngưỡng của đường đăng ký (`DAI_MAT_KHAU_TOI_THIEU`). Hai đường hai ngưỡng là
    một cửa sau: đặt mật khẩu 1 ký tự qua đường sửa."""
    uid, (ma,) = _tao_nguoi()
    async with _khach(session, ma) as c:
        r = await c.patch(DUONG, json={"mat_khau_cu": MK_CU, "mat_khau_moi": "abc"})
    assert r.status_code == 400
    assert "8" in r.json()["detail"]
    assert mk.kiem(MK_CU, _doc_nguoi(uid)[1]) is True


@pytest.mark.asyncio
async def test_mat_khau_moi_trung_mat_khau_cu_bi_tu_choi(session):
    """Cho qua thì người dùng tin mình đã xoay khoá trong khi khoá y nguyên — và lượt thu hồi
    phiên kèm theo làm họ tin tưởng sai chỗ."""
    uid, mas = _tao_nguoi(so_phien=2)
    async with _khach(session, mas[0]) as c:
        r = await c.patch(DUONG, json={"mat_khau_cu": MK_CU, "mat_khau_moi": MK_CU})
    assert r.status_code == 400
    # Và KHÔNG được thu hồi phiên nào cho một lượt đổi không xảy ra.
    assert _dem_phien(uid) == 2


# ── Hình dạng yêu cầu ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {"mat_khau_moi": MK_MOI},  # thiếu mật khẩu cũ
        {"mat_khau_cu": MK_CU},  # thiếu mật khẩu mới
    ],
)
async def test_gui_nua_cap_mat_khau_bi_tu_choi(session, body):
    """Bỏ qua im lặng sẽ trả 200 "đã lưu" cho một lượt đổi mật khẩu KHÔNG hề xảy ra."""
    uid, (ma,) = _tao_nguoi()
    async with _khach(session, ma) as c:
        r = await c.patch(DUONG, json=body)
    assert r.status_code == 422, r.text
    assert mk.kiem(MK_CU, _doc_nguoi(uid)[1]) is True


@pytest.mark.asyncio
async def test_body_rong_bi_tu_choi(session):
    _, (ma,) = _tao_nguoi()
    async with _khach(session, ma) as c:
        r = await c.patch(DUONG, json={})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_bi_tu_choi_thi_ten_hien_cung_KHONG_bi_luu(session):
    """BÀI CANH NẶNG: một lượt gọi gửi cả hai mà mật khẩu sai thì không được lưu nửa vời."""
    uid, (ma,) = _tao_nguoi()
    async with _khach(session, ma) as c:
        r = await c.patch(
            DUONG,
            json={"ten_hien": "Tên Mới", "mat_khau_cu": "sai-het-roi-9", "mat_khau_moi": MK_MOI},
        )
    assert r.status_code == 400
    assert _doc_nguoi(uid)[0] == "Tên Cũ"


@pytest.mark.asyncio
async def test_chua_dang_nhap_thi_401(client_chua_dang_nhap):
    r = await client_chua_dang_nhap.patch(DUONG, json={"ten_hien": "X"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_KHONG_tu_phong_quyen_quan_tri_duoc(session):
    """Đường này không nhận `la_quan_tri`. Nhận là lỗ leo thang quyền: ai cũng tự thành quản trị."""
    uid, (ma,) = _tao_nguoi()
    async with _khach(session, ma) as c:
        r = await c.patch(DUONG, json={"ten_hien": "X", "la_quan_tri": True})
    assert r.status_code == 200, r.text
    assert r.json()["nguoi_dung"]["la_quan_tri"] is False
    with sync_session() as s:
        assert (
            s.execute(
                sa.text("SELECT la_quan_tri FROM nguoi_dung WHERE id = :id"), {"id": uid}
            ).scalar_one()
            is False
        )


@pytest.mark.asyncio
async def test_KHONG_doi_duoc_email(session):
    """Email là danh tính đăng nhập và hệ thống chưa có hạ tầng gửi thư để xác minh địa chỉ mới.
    Cho đổi mà không xác minh là cho người ta tự gõ sai rồi mất hẳn đường vào."""
    uid, (ma,) = _tao_nguoi()
    email_cu = None
    with sync_session() as s:
        email_cu = s.execute(
            sa.text("SELECT email FROM nguoi_dung WHERE id = :id"), {"id": uid}
        ).scalar_one()
    async with _khach(session, ma) as c:
        r = await c.patch(DUONG, json={"ten_hien": "X", "email": "cuop@test.local"})
    assert r.status_code == 200
    with sync_session() as s:
        assert (
            s.execute(
                sa.text("SELECT email FROM nguoi_dung WHERE id = :id"), {"id": uid}
            ).scalar_one()
            == email_cu
        )


@pytest.mark.asyncio
async def test_chi_sua_duoc_CHINH_MINH(session):
    """Đường này không có tham số `{id}` nên về cấu trúc đã không nhắm được vào ai khác. Bài này
    canh điều đó bằng HÀNH VI: hai tài khoản, A đổi tên, B không đổi gì."""
    uid_a, (ma_a,) = _tao_nguoi()
    uid_b, _ = _tao_nguoi()
    ten_b_truoc = _doc_nguoi(uid_b)[0]

    async with _khach(session, ma_a) as c:
        r = await c.patch(DUONG, json={"ten_hien": "Chỉ A đổi"})
    assert r.status_code == 200
    assert _doc_nguoi(uid_a)[0] == "Chỉ A đổi"
    assert _doc_nguoi(uid_b)[0] == ten_b_truoc


@pytest.mark.asyncio
async def test_dang_nhap_lai_bang_mat_khau_MOI(session):
    """Vòng tròn đầy đủ: đổi xong phải đăng nhập được bằng mật khẩu mới qua đúng đường `/login`.
    Không có bài này thì "đã ghi vào CSDL" vẫn có thể không dùng được thật."""
    uid, (ma,) = _tao_nguoi()
    with sync_session() as s:
        email = s.execute(
            sa.text("SELECT email FROM nguoi_dung WHERE id = :id"), {"id": uid}
        ).scalar_one()

    async with _khach(session, ma) as c:
        assert (
            await c.patch(DUONG, json={"mat_khau_cu": MK_CU, "mat_khau_moi": MK_MOI})
        ).status_code == 200
        cu = await c.post("/api/v1/auth/login", json={"email": email, "mat_khau": MK_CU})
        moi = await c.post("/api/v1/auth/login", json={"email": email, "mat_khau": MK_MOI})
    assert cu.status_code == 401
    assert moi.status_code == 200, moi.text
