"""E57 — hai đường `nhan-dang-ngon-ngu`: trần riêng, chủ sở hữu, và ảnh tạm bị xoá.

## Ba bài canh nặng nhất

`test_KHONG_tru_han_muc_TRANG` — cả thiết kế đứng trên chỗ này. Trừ hạn mức trang thì khách có 6
lượt mất 1 lượt chỉ vì bấm "Tự nhận", nên tính năng **càng dùng càng đắt** và người ta sẽ tránh nó
rồi quay lại chọn tay sai — tức tự vô hiệu hoá đúng lúc cần nhất.

`test_nguoi_dang_nhap_KHONG_doc_duoc_luot_cua_khach` — nhánh GIỮA của phép kiểm chủ sở hữu. Thiếu nó
thì mọi người đăng nhập đọc được lượt nhận dạng (kèm chữ đã đọc) của mọi khách.

`test_khong_ket_luan_ghi_DONE_khong_ghi_FAILED` — `done` + `ngon_ngu=NULL` là "đã đọc xong, không đủ
căn cứ"; `failed` là "không đọc được". Trộn hai cái là làm người dùng không phân biệt được "ảnh của
tôi không có chữ" với "hệ thống đang lỗi".
"""
from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from app.core.config import get_settings
from app.core.db_sync import sync_session
from app.models import JobStatus, SoCaiHanMuc, SourceLang, YeuCauNhanDangNgonNgu
from app.services import han_muc_nhan_dang as hmn
from app.services.nhan_dang_ngon_ngu import BangChung, KetQuaNhanDang

DUONG = "/api/v1/nhan-dang-ngon-ngu"


@pytest.fixture
def st():
    return get_settings()


def _gui(client, anh: bytes, ten: str = "p.png"):
    return client.post(DUONG, files={"file": (ten, anh, "image/png")})


def _doc_db(yc_id) -> YeuCauNhanDangNgonNgu | None:
    with sync_session() as s:
        return s.get(YeuCauNhanDangNgonNgu, uuid.UUID(str(yc_id)))


def _dem_so_cai(tien_to: str) -> int:
    """Tổng đơn vị đã tiêu trên các chủ thể có tiền tố này. `""` = chủ thể KHÔNG có tiền tố."""
    with sync_session() as s:
        if tien_to:
            dieu_kien = SoCaiHanMuc.chu_the.like(f"{tien_to}%")
        else:
            dieu_kien = ~SoCaiHanMuc.chu_the.like("%:%")
        return int(
            s.execute(
                sa.select(sa.func.coalesce(sa.func.sum(SoCaiHanMuc.so_trang), 0)).where(dieu_kien)
            ).scalar_one()
        )


# ── Đường gửi ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gui_duoc_va_tra_202_kem_id(client, sample_page_image):
    r = await _gui(client, sample_page_image)
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["trang_thai"] == "queued"
    assert body["xong"] is False
    assert body["ngon_ngu"] is None
    assert _doc_db(body["id"]) is not None


@pytest.mark.asyncio
async def test_tep_rong_bi_tu_choi_va_KHONG_mat_luot(client):
    truoc = _dem_so_cai(hmn.TIEN_TO)
    r = await _gui(client, b"")
    assert r.status_code == 422
    # Cùng luật với đường tải trang: tệp hỏng không được mất lượt.
    assert _dem_so_cai(hmn.TIEN_TO) == truoc


@pytest.mark.asyncio
async def test_khong_phai_anh_bi_tu_choi_va_KHONG_mat_luot(client):
    truoc = _dem_so_cai(hmn.TIEN_TO)
    r = await _gui(client, b"day-khong-phai-anh-png")
    assert r.status_code == 422
    assert _dem_so_cai(hmn.TIEN_TO) == truoc


@pytest.mark.asyncio
async def test_KHONG_tru_han_muc_TRANG(client, sample_page_image):
    """BÀI CANH NẶNG NHẤT — cả thiết kế đứng trên chỗ này."""
    trang_truoc = _dem_so_cai("")
    nhan_dang_truoc = _dem_so_cai(hmn.TIEN_TO)

    assert (await _gui(client, sample_page_image)).status_code == 202

    # Bộ đếm NHẬN DẠNG tăng…
    assert _dem_so_cai(hmn.TIEN_TO) == nhan_dang_truoc + 1
    # …và bộ đếm TRANG KHÔNG tăng.
    assert _dem_so_cai("") == trang_truoc


@pytest.mark.asyncio
async def test_het_luot_thi_429_kem_du_thong_tin(client, sample_page_image, monkeypatch, st):
    # KHÔNG gọi `get_settings.cache_clear()` ở đây. `get_settings` có `lru_cache`, nên `st` LÀ chính
    # đối tượng mà `Depends(get_settings)` trả về — sửa nó là xong. Gọi `cache_clear()` sau khi sửa
    # sẽ **ném bỏ bản đã sửa** và endpoint nhận một bản mặc định: bài test xanh/đỏ theo mặc định chứ
    # không theo thứ mình đặt. Đã trả giá cho chỗ này ở E49 (xem `test_e49_ngay_han_muc.py`).
    monkeypatch.setattr(st, "so_lan_nhan_dang_ngon_ngu_mot_ngay", 2)
    assert (await _gui(client, sample_page_image)).status_code == 202
    assert (await _gui(client, sample_page_image)).status_code == 202
    r = await _gui(client, sample_page_image)
    assert r.status_code == 429, r.text
    ct = r.json()["detail"]
    # Thông báo mơ hồ làm người dùng tưởng hệ thống hỏng rồi bấm lại liên tục.
    assert ct["tran"] == 2
    assert ct["con_lai"] == 0
    assert "reset_luc" in ct and "chot" in ct
    assert r.headers.get("Retry-After") is not None


@pytest.mark.asyncio
async def test_het_luot_thi_KHONG_de_lai_ban_ghi_hay_tep(client, sample_page_image, monkeypatch, st):
    """429 ném TRƯỚC khi ghi tệp ⇒ giao dịch huỷ ⇒ bản ghi vừa flush cũng biến mất."""
    monkeypatch.setattr(st, "so_lan_nhan_dang_ngon_ngu_mot_ngay", 1)
    assert (await _gui(client, sample_page_image)).status_code == 202
    assert (await _gui(client, sample_page_image)).status_code == 429
    with sync_session() as ss:
        assert int(
            ss.execute(sa.select(sa.func.count()).select_from(YeuCauNhanDangNgonNgu)).scalar_one()
        ) == 1


# ── Đường tra + chủ sở hữu ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tra_duoc_luot_cua_MINH(client, sample_page_image):
    yc_id = (await _gui(client, sample_page_image)).json()["id"]
    r = await client.get(f"{DUONG}/{yc_id}")
    assert r.status_code == 200, r.text
    assert r.json()["id"] == yc_id


@pytest.mark.asyncio
async def test_khong_co_thi_404(client):
    assert (await client.get(f"{DUONG}/{uuid.uuid4()}")).status_code == 404


@pytest.mark.asyncio
async def test_nguoi_khac_KHONG_tra_duoc_va_nhan_404_chu_khong_403(
    client, client_b, sample_page_image
):
    """`403` là xác nhận "id này tồn tại" — một đường dò. Cùng luật với `_get_project_or_404`."""
    yc_id = (await _gui(client, sample_page_image)).json()["id"]
    r = await client_b.get(f"{DUONG}/{yc_id}")
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_nguoi_dang_nhap_KHONG_doc_duoc_luot_cua_khach(client, sample_page_image):
    """BÀI CANH NẶNG: nhánh GIỮA của phép kiểm chủ sở hữu.

    Thiếu nó thì mọi người đăng nhập đọc được lượt nhận dạng — **kèm chữ đã đọc được** — của mọi
    khách lạ. Cùng hình dạng lỗi mà `quyen.duoc_dung_project` đã phải vá ở E49.
    """
    # Dựng trực tiếp một lượt CỦA KHÁCH (chu_khach có giá trị, chu_so_huu_id NULL).
    yc_id = uuid.uuid4()
    with sync_session() as s:
        s.execute(
            sa.text(
                "INSERT INTO yeu_cau_nhan_dang_ngon_ngu (id, chu_khach, duong_anh, trang_thai)"
                " VALUES (:id, :k, '', 'done')"
            ),
            {"id": yc_id, "k": "bam-cookie-cua-mot-khach-la"},
        )
        s.commit()

    # `client` là tài khoản ĐÃ đăng nhập — không được thấy.
    assert (await client.get(f"{DUONG}/{yc_id}")).status_code == 404


# ── Task ──────────────────────────────────────────────────────────────────────────────────


def _chay_task(yc_id, ket_qua: KetQuaNhanDang, monkeypatch):
    import app.services.nhan_dang_ngon_ngu as mod
    from app.workers.tasks import run_nhan_dang_ngon_ngu_job

    monkeypatch.setattr(mod, "nhan_dang_tu_anh", lambda *a, **k: ket_qua)
    return run_nhan_dang_ngon_ngu_job(str(yc_id))


@pytest.mark.asyncio
async def test_task_ghi_ket_qua_va_bang_chung(client, sample_page_image, monkeypatch):
    yc_id = (await _gui(client, sample_page_image)).json()["id"]
    bc = BangChung(kana=11, han=5, tong_co_nghia=16, so_vung_doc_duoc=3, so_vung_da_thu=3)
    _chay_task(yc_id, KetQuaNhanDang(SourceLang.ja, "co_11_kana", bc), monkeypatch)

    yc = _doc_db(yc_id)
    assert yc.trang_thai is JobStatus.done
    assert yc.ngon_ngu is SourceLang.ja
    assert yc.ly_do == "co_11_kana"
    # Giao diện HIỆN con số này ra — một kết luận không kèm số đo thì không ai biết nên tin bao nhiêu.
    assert yc.bang_chung["kana"] == 11
    assert yc.bang_chung["tong_co_nghia"] == 16


@pytest.mark.asyncio
async def test_khong_ket_luan_ghi_DONE_khong_ghi_FAILED(client, sample_page_image, monkeypatch):
    """BÀI CANH NẶNG: "đọc xong mà không đủ căn cứ" ≠ "không đọc được"."""
    yc_id = (await _gui(client, sample_page_image)).json()["id"]
    _chay_task(
        yc_id,
        KetQuaNhanDang(None, "khong_doc_duoc_chu_nao", BangChung(so_vung_da_thu=0)),
        monkeypatch,
    )
    yc = _doc_db(yc_id)
    assert yc.trang_thai is JobStatus.done
    assert yc.ngon_ngu is None
    assert yc.loi is None          # KHÔNG phải lỗi
    assert yc.ly_do == "khong_doc_duoc_chu_nao"


@pytest.mark.asyncio
async def test_task_XOA_anh_tam(client, sample_page_image, monkeypatch):
    """Ảnh này là rác tạm: không ai tải về. Giữ lại là giữ ảnh có bản quyền không vì mục đích gì."""
    from app.services.storage import get_storage

    yc_id = (await _gui(client, sample_page_image)).json()["id"]
    duong = _doc_db(yc_id).duong_anh
    assert duong and get_storage().exists(duong), "ảnh phải tồn tại TRƯỚC khi task chạy"

    _chay_task(
        yc_id, KetQuaNhanDang(SourceLang.en, "latin_100%", BangChung(latin=20, tong_co_nghia=20)),
        monkeypatch,
    )
    assert get_storage().exists(duong) is False
    assert _doc_db(yc_id).duong_anh == ""


@pytest.mark.asyncio
async def test_task_chay_LAI_thi_bo_qua_khong_ghi_de_ket_qua_dung(
    client, sample_page_image, monkeypatch
):
    """Celery có thể giao lại cùng một việc (worker chết giữa lượt). Lượt hai sẽ đọc một ảnh ĐÃ BỊ
    XOÁ và ghi `failed` lên một kết quả đúng — nên phải chốt lại."""
    yc_id = (await _gui(client, sample_page_image)).json()["id"]
    bc = BangChung(kana=9, tong_co_nghia=9)
    _chay_task(yc_id, KetQuaNhanDang(SourceLang.ja, "co_9_kana", bc), monkeypatch)
    assert _doc_db(yc_id).trang_thai is JobStatus.done

    kq2 = _chay_task(yc_id, KetQuaNhanDang(SourceLang.zh, "sai_be_het", bc), monkeypatch)
    assert kq2["status"] == "bo_qua"
    yc = _doc_db(yc_id)
    assert yc.trang_thai is JobStatus.done
    assert yc.ngon_ngu is SourceLang.ja          # kết quả CŨ còn nguyên
    assert yc.ly_do == "co_9_kana"


@pytest.mark.asyncio
async def test_engine_hong_thi_ghi_FAILED_va_van_xoa_anh(client, sample_page_image, monkeypatch):
    """Engine hỏng là lỗi THẬT và phải nổi lên — nuốt nó rồi trả "không kết luận" là biến một sự cố
    hạ tầng thành một câu trả lời bình thường, và người dùng sẽ tưởng ảnh của mình có vấn đề."""
    import app.services.nhan_dang_ngon_ngu as mod
    from app.services.storage import get_storage
    from app.workers.tasks import run_nhan_dang_ngon_ngu_job

    yc_id = (await _gui(client, sample_page_image)).json()["id"]
    duong = _doc_db(yc_id).duong_anh

    def no(*a, **k):
        raise RuntimeError("engine_chet_that")

    monkeypatch.setattr(mod, "nhan_dang_tu_anh", no)
    kq = run_nhan_dang_ngon_ngu_job(str(yc_id))

    assert kq["status"] == "failed"
    yc = _doc_db(yc_id)
    assert yc.trang_thai is JobStatus.failed
    assert "engine_chet_that" in (yc.loi or "")
    assert yc.ngon_ngu is None
    # Dọn trong `finally` ⇒ lượt hỏng cũng không để lại tệp.
    assert get_storage().exists(duong) is False


@pytest.mark.asyncio
async def test_tra_ket_qua_qua_API_sau_khi_task_xong(client, sample_page_image, monkeypatch):
    """Vòng tròn đầy đủ: ghi được vào CSDL ≠ đọc lại được qua API."""
    yc_id = (await _gui(client, sample_page_image)).json()["id"]
    _chay_task(
        yc_id,
        KetQuaNhanDang(SourceLang.zh, "han_100%_khong_kana", BangChung(han=15, tong_co_nghia=15)),
        monkeypatch,
    )
    r = await client.get(f"{DUONG}/{yc_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["xong"] is True
    assert body["ngon_ngu"] == "zh"
    assert body["bang_chung"]["han"] == 15
