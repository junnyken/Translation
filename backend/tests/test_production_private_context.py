"""P1 integration contract. Requires migrated PostgreSQL, as do other API tests.

These tests do not call a real AI provider. They verify request isolation/cache
boundaries and backwards compatibility; Windows/provider UAT remains separate.
"""
import io
import pytest
from PIL import Image

from app.models import Project, Page
from app.models.enums import ChePipeline, IntendedUse, PageStatus, SourceLang, TranslationEngine
from app.services import bo_nho_anh_dich as cache
from app.services.typeset.chon_font import doc_tu_dien_du_an


def png():
    stream = io.BytesIO()
    Image.new("RGB", (32, 48), "white").save(stream, "PNG")
    return stream.getvalue()


async def upload(client, *, private=False, glossary=""):
    return await client.post("/api/v1/doc-truyen/trang", files={"file": ("page.png", png(), "image/png")},
                             data={"source_lang": "en", "tao_chapter_rieng": str(private).lower(),
                                   "tu_dien_rieng": glossary})


async def test_private_uploads_do_not_share_project_or_glossary(client, session):
    a = await upload(client, private=True, glossary="Pepper = Pepper")
    b = await upload(client, private=True, glossary="Pepper = Tiêu")
    assert a.status_code == b.status_code == 202
    one, two = a.json(), b.json()
    assert one["cau_hinh_rieng"] is two["cau_hinh_rieng"] is True
    assert one["project_id"] != two["project_id"]
    assert doc_tu_dien_du_an(one["project_id"]) == "Pepper = Pepper"
    assert doc_tu_dien_du_an(two["project_id"]) == "Pepper = Tiêu"
    result = await client.get(f"/api/v1/doc-truyen/trang/{one['page_id']}")
    assert result.status_code == 200
    assert result.json()["cau_hinh_rieng"] is True


async def test_old_clients_keep_shared_chapter_default(client):
    # Omit the new form field entirely, as released browser clients do.
    def files():
        return {"file": ("page.png", png(), "image/png")}
    a = await client.post("/api/v1/doc-truyen/trang", files=files(), data={"source_lang": "en"})
    b = await client.post("/api/v1/doc-truyen/trang", files=files(), data={"source_lang": "en"})
    assert a.status_code == b.status_code == 202
    assert a.json()["cau_hinh_rieng"] is False
    assert a.json()["project_id"] == b.json()["project_id"]


async def test_private_destination_never_reads_community_cache(client, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Private work reached the community-cache key lookup")
    monkeypatch.setattr(cache, "_khoa", forbidden)
    # Registration alone is not disclosure, but skip its key call to isolate the read test.
    monkeypatch.setattr(cache, "ghi_nhan_trang_anh", lambda *args, **kwargs: None)
    response = await upload(client, private=True)
    assert response.status_code == 202


async def test_private_source_is_not_copied_to_public_destination(session, tmp_path):
    from app.services.storage import LocalObjectStorage

    source_project = Project(name="Private", source_lang=SourceLang.en,
                             intended_use=IntendedUse.other, cau_hinh_rieng=True,
                             che_do_pipeline=ChePipeline.day_du)
    dest_project = Project(name="Public", source_lang=SourceLang.en,
                           intended_use=IntendedUse.personal, cau_hinh_rieng=False,
                           che_do_pipeline=ChePipeline.day_du)
    session.add_all([source_project, dest_project])
    await session.flush()
    source = Page(project_id=source_project.id, image_path="private.png", order=1, status=PageStatus.typeset_done)
    dest = Page(project_id=dest_project.id, image_path="public.png", order=1, status=PageStatus.queued)
    session.add_all([source, dest])
    await session.flush()
    digest = cache.tinh_bam_anh(png())
    cache.xoa_bo_nho_bam()
    try:
        cache.ghi_nhan_trang_anh(digest, SourceLang.en, TranslationEngine.google_fast, ChePipeline.day_du, source.id)
        found = await cache.thu_sao_chep_tu_cache(
            session, bam_anh=digest, source_lang=SourceLang.en,
            engine=TranslationEngine.google_fast, che_do=ChePipeline.day_du,
            dich_page=dest, storage=LocalObjectStorage(tmp_path),
        )
        assert found is False
        assert dest.status == PageStatus.queued
    finally:
        cache.xoa_bo_nho_bam()


async def test_health_advertises_private_context_before_upload(client_chua_dang_nhap):
    response = await client_chua_dang_nhap.get("/healthz")
    assert response.status_code == 200
    assert response.json()["translation_capabilities"]["private_context_v1"] is True
