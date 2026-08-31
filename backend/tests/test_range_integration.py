"""P3g — HTTP `Range` trên 3 endpoint trả tệp.

P3d đổi `FileResponse` sang luồng và **nhận mất** hỗ trợ `Range`; P3g trả lại. Ý nghĩa thật:
đứt mạng giữa chừng khi tải gói CBZ thì tải tiếp được, không phải tải lại từ đầu.

Test chạy trên backend CSDL — vì đó mới là chỗ khó: `Range` phải đi qua `substr()` phía máy chủ,
không được nạp cả hiện vật rồi mới cắt.
"""
from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from app.core.config import get_settings
from app.core.db_sync import sync_session
from app.models import ArtifactBlob, Page
from app.services.storage import get_storage


@pytest.fixture
def kho_postgres(monkeypatch):
    st = get_settings()
    monkeypatch.setattr(st, "storage_backend", "postgres")
    with sync_session() as s:
        s.execute(sa.delete(ArtifactBlob)); s.commit()
    return get_storage()


@pytest.fixture
async def trang_co_anh(client, sample_page_image, kho_postgres):
    pr = await client.post("/api/v1/projects", json={
        "name": "P3g", "source_lang": "en", "target_lang": "vi", "intended_use": "personal"})
    r = await client.post(f"/api/v1/projects/{pr.json()['id']}/pages",
                          files={"file": ("p.png", sample_page_image, "image/png")})
    page_id = r.json()["page_id"]
    rel = f"p3g/{page_id}_clean.png"
    kho_postgres.save(rel, sample_page_image)
    with sync_session() as s:
        page = s.get(Page, uuid.UUID(page_id))
        page.clean_image_path = rel
        s.commit()
    return page_id


def _url(page_id: str) -> str:
    return f"/api/v1/pages/{page_id}/clean-image"


async def test_bao_rang_minh_ho_tro_range(client, trang_co_anh):
    r = await client.get(_url(trang_co_anh))
    assert r.status_code == 200
    assert r.headers["accept-ranges"] == "bytes", "không quảng cáo thì client không bao giờ hỏi"


async def test_doan_giua_tra_206_dung_byte(client, trang_co_anh, sample_page_image):
    r = await client.get(_url(trang_co_anh), headers={"Range": "bytes=10-19"})
    assert r.status_code == 206
    assert r.content == sample_page_image[10:20]
    assert r.headers["content-range"] == f"bytes 10-19/{len(sample_page_image)}"
    assert r.headers["content-length"] == "10"


async def test_khong_ghi_cuoi_thi_lay_tiep_toi_het(client, trang_co_anh, sample_page_image):
    dau = len(sample_page_image) - 50
    r = await client.get(_url(trang_co_anh), headers={"Range": f"bytes={dau}-"})
    assert r.status_code == 206
    assert r.content == sample_page_image[dau:]


async def test_hau_to_lay_n_byte_cuoi(client, trang_co_anh, sample_page_image):
    r = await client.get(_url(trang_co_anh), headers={"Range": "bytes=-25"})
    assert r.status_code == 206
    assert r.content == sample_page_image[-25:]


async def test_noi_hai_doan_lai_ra_dung_tep_goc(client, trang_co_anh, sample_page_image):
    """Đây mới là điều người dùng thật sự cần: tải dở rồi tải tiếp, ghép lại phải khớp."""
    giua = len(sample_page_image) // 2
    p1 = await client.get(_url(trang_co_anh), headers={"Range": f"bytes=0-{giua - 1}"})
    p2 = await client.get(_url(trang_co_anh), headers={"Range": f"bytes={giua}-"})
    assert p1.status_code == p2.status_code == 206
    assert p1.content + p2.content == sample_page_image


async def test_xin_qua_cuoi_tra_416_kem_kich_thuoc_that(client, trang_co_anh, sample_page_image):
    r = await client.get(_url(trang_co_anh), headers={"Range": "bytes=999999999-"})
    assert r.status_code == 416
    assert r.headers["content-range"] == f"bytes */{len(sample_page_image)}"


async def test_cu_phap_hong_thi_tra_nguyen_tep_chu_khong_no(client, trang_co_anh, sample_page_image):
    """RFC 9110 cho bỏ qua header hỏng. Ném lỗi vào mặt người dùng vì một header họ không tự gõ
    là hành vi tệ hơn."""
    for xau in ("bytes=abc-def", "chuong=1-2", "bytes=", "bytes=1-2, 5-6"):
        r = await client.get(_url(trang_co_anh), headers={"Range": xau})
        assert r.status_code == 200, f"{xau!r} phải cho ra nguyên tệp"
        assert r.content == sample_page_image


async def test_if_range_khop_thi_cho_lay_doan(client, trang_co_anh):
    r0 = await client.get(_url(trang_co_anh))
    r = await client.get(_url(trang_co_anh),
                         headers={"Range": "bytes=0-9", "If-Range": r0.headers["etag"]})
    assert r.status_code == 206


async def test_if_range_lech_thi_tra_NGUYEN_tep(client, trang_co_anh, sample_page_image):
    """Hiện vật đã đổi kể từ lúc client tải dở ⇒ nối đoạn của bản cũ vào phần đã tải sẽ tạo ra
    một tệp lai không của ai cả. Phải trả nguyên tệp."""
    r = await client.get(_url(trang_co_anh),
                         headers={"Range": "bytes=0-9", "If-Range": '"cu-roi"'})
    assert r.status_code == 200
    assert r.content == sample_page_image


async def test_304_van_thang_range(client, trang_co_anh):
    """Client đã có bản mới nhất thì không cần đoạn nào cả."""
    etag = (await client.get(_url(trang_co_anh))).headers["etag"]
    r = await client.get(_url(trang_co_anh),
                         headers={"Range": "bytes=0-9", "If-None-Match": etag})
    assert r.status_code == 304
    assert r.content == b""
