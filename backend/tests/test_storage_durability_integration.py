"""P3e — hiện vật có sống sót qua một lần TRIỂN KHAI LẠI không?

Đây là test trả lời đúng câu hỏi khiến P3a/P3b bị chặn, và là lý do duy nhất P3e tồn tại.

Cách mô phỏng một lượt triển khai lại của VibeHost: **xoá sạch hệ tệp cục bộ**. Đó chính xác là
điều nền tảng làm với lớp ghi của container mỗi lần deploy (P3a đã đo trực tiếp trên host), trong
khi CSDL thì còn nguyên.

Hai test dưới đây là một CẶP có chủ đích: một cái chứng minh backend `postgres` sống sót, cái kia
chứng minh backend `local` KHÔNG — nếu chỉ có cái đầu thì không ai biết nó có đang kiểm gì thật
hay không.
"""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa

from app.core.config import get_settings
from app.core.db_sync import sync_session
from app.models import ArtifactBlob, Page
from app.services.storage import get_storage

@pytest.fixture(autouse=True)
def _dung_lai_thu_muc_kho(storage_root):
    """Hai test dưới đây XOÁ thư mục kho dùng chung cả phiên. Dựng lại sau mỗi test để thứ tự
    chạy ngẫu nhiên (pytest-randomly) không biến chúng thành quả mìn cho test khác."""
    yield
    Path(storage_root).mkdir(parents=True, exist_ok=True)


@pytest.fixture
def kho_postgres(monkeypatch):
    """Chuyển toàn hệ thống sang backend CSDL trong phạm vi một test.

    `get_settings()` có `lru_cache` nên mọi nơi (API, worker, service) dùng CHUNG một đối tượng
    settings — sửa thuộc tính trên nó là đổi backend ở mọi tầng cùng lúc, đúng như khi đặt biến
    môi trường `STORAGE_BACKEND=postgres` trên host.
    """
    st = get_settings()
    monkeypatch.setattr(st, "storage_backend", "postgres")
    with sync_session() as s:
        s.execute(sa.delete(ArtifactBlob))
        s.commit()
    return get_storage()


async def _upload(client, anh: bytes) -> tuple[str, str]:
    pr = await client.post(
        "/api/v1/projects",
        json={"name": "P3e", "source_lang": "en", "target_lang": "vi", "intended_use": "personal"},
    )
    project_id = pr.json()["id"]
    r = await client.post(
        f"/api/v1/projects/{project_id}/pages",
        files={"file": ("page_001.png", anh, "image/png")},
    )
    assert r.status_code == 202, r.text
    return project_id, r.json()["page_id"]


def _gan_anh_clean(page_id: str, du_lieu: bytes) -> str:
    """Đặt ảnh clean qua kho + ghi path vào DB — đúng cách bước xoá chữ (M4) vẫn làm."""
    storage = get_storage()
    rel = f"projects/p3e/pages/{page_id}_clean.png"
    storage.save(rel, du_lieu)
    with sync_session() as s:
        page = s.get(Page, uuid.UUID(page_id))
        page.clean_image_path = rel
        s.commit()
    return rel


def _anh_chup_thu_muc(goc: str) -> set[Path]:
    g = Path(goc)
    return {p for p in g.rglob("*") if p.is_file()} if g.exists() else set()


async def test_backend_postgres_song_sot_qua_mot_lan_trien_khai_lai(
    client, sample_page_image, storage_root, kho_postgres
):
    # Thư mục kho dùng chung cả phiên nên test khác có để lại tệp ở đó. Chỉ so tệp MỚI.
    truoc_khi_ghi = _anh_chup_thu_muc(storage_root)

    _project_id, page_id = await _upload(client, sample_page_image)
    _gan_anh_clean(page_id, sample_page_image)

    truoc = await client.get(f"/api/v1/pages/{page_id}/clean-image")
    assert truoc.status_code == 200
    assert truoc.content == sample_page_image

    # Không một byte MỚI nào ra hệ tệp: có, nghĩa là còn đường ghi lén chưa đi qua kho.
    moi = _anh_chup_thu_muc(storage_root) - truoc_khi_ghi
    assert moi == set(), f"backend postgres vẫn ghi ra đĩa: {sorted(map(str, moi))}"

    # Và hiện vật thật sự nằm trong CSDL, không phải "tình cờ chưa ai xoá".
    with sync_session() as s:
        assert s.scalar(sa.select(sa.func.count()).select_from(ArtifactBlob)) >= 2

    # ---- mô phỏng triển khai lại: hệ tệp container bị thay mới hoàn toàn ----
    shutil.rmtree(storage_root, ignore_errors=True)

    sau = await client.get(f"/api/v1/pages/{page_id}/clean-image")
    assert sau.status_code == 200, "hiện vật KHÔNG sống sót qua lần triển khai lại"
    assert sau.content == sample_page_image, "nội dung đổi sau khi triển khai lại"


async def test_backend_local_mat_hien_vat_qua_mot_lan_trien_khai_lai(
    client, sample_page_image, storage_root
):
    """Đối chứng — đây CHÍNH LÀ lỗi đang có trên host, và là lý do P3e tồn tại.

    Test này *khẳng định điều sai đang xảy ra*. Ngày nào nó bắt đầu đỏ, nghĩa là nền tảng đã cấp
    được volume bền và có thể xét quay về `local`.
    """
    assert get_settings().storage_backend == "local"
    _project_id, page_id = await _upload(client, sample_page_image)
    _gan_anh_clean(page_id, sample_page_image)

    assert (await client.get(f"/api/v1/pages/{page_id}/clean-image")).status_code == 200

    shutil.rmtree(storage_root, ignore_errors=True)

    sau = await client.get(f"/api/v1/pages/{page_id}/clean-image")
    assert sau.status_code == 404, "bất ngờ: backend local giữ được hiện vật qua redeploy?"
    # Và đây là lời nói dối mà người dùng gặp: DB vẫn khai có ảnh clean.
    with sync_session() as s:
        assert s.get(Page, uuid.UUID(page_id)).clean_image_path is not None


async def test_ETag_304_hoat_dong_tren_kho_CSDL(
    client, sample_page_image, storage_root, kho_postgres
):
    """304 phải chạy được cả khi kho là CSDL — vì `stat()` là thứ dựng ra ETag."""
    _project_id, page_id = await _upload(client, sample_page_image)
    _gan_anh_clean(page_id, sample_page_image)

    r1 = await client.get(f"/api/v1/pages/{page_id}/clean-image")
    assert r1.status_code == 200
    etag = r1.headers["etag"]
    assert r1.headers["content-length"] == str(len(sample_page_image))

    r2 = await client.get(
        f"/api/v1/pages/{page_id}/clean-image", headers={"If-None-Match": etag}
    )
    assert r2.status_code == 304
    assert r2.content == b"", "304 mà vẫn gửi thân"


async def test_doi_noi_dung_thi_ETag_doi_theo(
    client, sample_page_image, storage_root, kho_postgres
):
    _project_id, page_id = await _upload(client, sample_page_image)
    rel = _gan_anh_clean(page_id, sample_page_image)

    etag_cu = (await client.get(f"/api/v1/pages/{page_id}/clean-image")).headers["etag"]
    get_storage().save(rel, sample_page_image + b"\x00")
    etag_moi = (await client.get(f"/api/v1/pages/{page_id}/clean-image")).headers["etag"]
    assert etag_cu != etag_moi, "ảnh đã đổi mà ETag không đổi — trình duyệt sẽ giữ bản cũ mãi"
