"""Integration E17 — ứng viên thuật ngữ, tín hiệu xưng hô, và tầng 3 trên DB thật."""
from __future__ import annotations

import uuid

import pytest
from app.core.db_sync import sync_session
from app.models import (
    CharacterVoiceProfile,
    GlossaryEntry,
    OCRResult,
    Page,
    TermSuggestionRun,
    TextRegion,
)
from app.models.enums import OCREngine, OCRStatus, PageStatus, TermSuggestionStatus
from app.services.consistency.glossary import GlossaryService


@pytest.fixture
def chapter_e17(client, sample_page_image, no_broker_for_chained_ocr):
    """Chapter có chữ THẬT trong `ocr_result` — đúng nguồn mà E17 đọc."""
    async def _go(cau: list[str], lang: str = "en", trang_thai=OCRStatus.ok, ten="Chapter E17"):
        proj = await client.post(
            "/api/v1/projects",
            json={"name": ten, "source_lang": lang, "intended_use": "study"},
        )
        pid = uuid.UUID(proj.json()["id"])
        for i, chu in enumerate(cau):
            up = await client.post(
                f"/api/v1/projects/{pid}/pages",
                files={"file": (f"{i + 1:03d}.png", sample_page_image, "image/png")},
            )
            page_id = uuid.UUID(up.json()["page_id"])
            with sync_session() as s:
                s.get(Page, page_id).status = PageStatus.ocr_done
                r = TextRegion(page_id=page_id, bbox_x=10, bbox_y=10, bbox_w=200, bbox_h=80,
                               confidence=0.9, reading_order=1)
                s.add(r)
                s.flush()
                s.add(OCRResult(region_id=r.id, raw_text=chu, ocr_engine=OCREngine.manga_ocr,
                                status=trang_thai))
                s.commit()
        return pid
    return _go


def _dem_ban_ghi(pid) -> tuple[int, int]:
    with sync_session() as s:
        return (
            s.query(GlossaryEntry).filter_by(project_id=pid).count(),
            s.query(CharacterVoiceProfile).filter_by(project_id=pid).count(),
        )


class TestUngVienQuaAPI:
    async def test_tra_ve_ung_vien_kem_bang_chung(self, client, chapter_e17):
        pid = await chapter_e17(["I met Pepper today", "Pepper drinks a Potion"])
        r = await client.get(f"/api/v1/projects/{pid}/term-candidates")
        assert r.status_code == 200
        body = r.json()
        assert body["trang_thai"] == "co_ung_vien"

        pepper = next(u for u in body["ung_vien"] if u["term_key"] == "pepper")
        assert pepper["count"] == 2
        assert pepper["pages"] == [1, 2]
        assert pepper["quotes"], "thiếu trích dẫn thì người dùng không có gì để đối chiếu"
        assert pepper["quotes"][0]["text"] in ("I met Pepper today", "Pepper drinks a Potion")
        assert pepper["reasons"], "phải nói ra vì sao mục này được nêu"

    async def test_KHONG_ghi_mot_dong_nao_vao_CSDL(self, client, chapter_e17):
        """Lời hứa gắt nhất của E17: máy tìm giúp, nhưng không tự tạo thuật ngữ nào."""
        pid = await chapter_e17(["I met Pepper today", "Pepper drinks a Potion"])
        truoc = _dem_ban_ghi(pid)
        await client.get(f"/api/v1/projects/{pid}/term-candidates")
        await client.get(f"/api/v1/projects/{pid}/voice-signals")
        assert _dem_ban_ghi(pid) == truoc == (0, 0)

    async def test_thuat_ngu_da_co_thi_khong_hien_lai(self, client, chapter_e17):
        pid = await chapter_e17(["I met Pepper today", "Pepper drinks a Potion"])
        with sync_session() as s:
            GlossaryService(s).create_entry(pid, {
                "source_term": "Pepper", "target_term": "Pepper",
                "term_type": "character_name", "definition": "cô phù thuỷ nhỏ",
            })
        body = (await client.get(f"/api/v1/projects/{pid}/term-candidates")).json()
        assert all(u["term_key"] != "pepper" for u in body["ung_vien"])
        assert body["so_bi_loc_vi_da_co"] >= 1

    async def test_ten_CHI_dung_dau_cau_thi_KHONG_tim_ra_duoc(self, client, chapter_e17):
        """Giới hạn thật, ghi lại để không ai tưởng là lỗi ngẫu nhiên.

        Tiếng Anh chữ thường: từ viết hoa ở đầu câu viết hoa vì ngữ pháp. Một cái tên mà TRONG
        CẢ CHAPTER chỉ từng đứng đầu câu thì không có bằng chứng nào phân biệt nó với một từ
        thường — và đoán bừa ở đây sẽ kéo theo mọi danh từ đầu câu.
        """
        pid = await chapter_e17(["Pepper is here", "Pepper is here again"])
        body = (await client.get(f"/api/v1/projects/{pid}/term-candidates")).json()
        assert all(u["term_key"] != "pepper" for u in body["ung_vien"])

    async def test_ghi_chu_noi_ro_luat_nao_dang_chay_voi_tieng_anh(self, client, chapter_e17):
        pid = await chapter_e17(["WHAT ARE YOU DOING HERE", "I KNOW WHAT YOU WANT"])
        body = (await client.get(f"/api/v1/projects/{pid}/term-candidates")).json()
        assert "chữ hoa" in (body["ghi_chu_ngon_ngu"] or "")
        assert "KHÔNG dùng được tín hiệu viết hoa" in body["ghi_chu_ngon_ngu"]


class TestBaTrangThaiRongKhongDuocGop:
    """"Chưa chạy" ≠ "đã chạy mà trống" ≠ "đều đã có" — bài học `worker: khong_ro` của E1a."""

    async def test_chua_doc_chu(self, client, sample_page_image, no_broker_for_chained_ocr):
        proj = await client.post("/api/v1/projects",
                                 json={"name": "trống", "source_lang": "en",
                                       "intended_use": "study"})
        pid = proj.json()["id"]
        await client.post(f"/api/v1/projects/{pid}/pages",
                          files={"file": ("1.png", sample_page_image, "image/png")})
        body = (await client.get(f"/api/v1/projects/{pid}/term-candidates")).json()
        assert body["trang_thai"] == "chua_doc_chu"
        assert body["so_vung_co_chu"] == 0

    async def test_da_doc_nhung_khong_thay_gi(self, client, chapter_e17):
        pid = await chapter_e17(["yes", "no"])
        body = (await client.get(f"/api/v1/projects/{pid}/term-candidates")).json()
        assert body["trang_thai"] == "khong_thay"
        assert body["so_vung_co_chu"] == 2, "có đọc được chữ, chỉ là không có danh xưng nào"

    async def test_deu_da_co_trong_glossary(self, client, chapter_e17):
        pid = await chapter_e17(["I met Pepper today", "We saw Pepper again"])
        with sync_session() as s:
            GlossaryService(s).create_entry(pid, {
                "source_term": "Pepper", "target_term": "Pepper",
                "term_type": "character_name", "definition": "nhân vật chính",
            })
        body = (await client.get(f"/api/v1/projects/{pid}/term-candidates")).json()
        assert body["trang_thai"] == "deu_da_co"

    async def test_chu_doc_chua_chac_thi_bi_bo_va_DEM_ra(self, client, chapter_e17):
        """Bỏ im lặng thì người dùng tưởng chapter không có gì. Phải nói ra con số."""
        pid = await chapter_e17(["Pepper is here", "Pepper is here"],
                                trang_thai=OCRStatus.needs_manual)
        body = (await client.get(f"/api/v1/projects/{pid}/term-candidates")).json()
        assert body["trang_thai"] == "chua_doc_chu"
        assert body["so_vung_khong_chac"] == 2


class TestTinHieuXungHo:
    async def test_bat_duoc_hau_to_kinh_ngu_va_gan_dung_ten(self, client, chapter_e17):
        pid = await chapter_e17(["ペッパー様、お待ちください", "俺が行く"], lang="ja")
        body = (await client.get(f"/api/v1/projects/{pid}/voice-signals")).json()
        assert body["trang_thai"] == "co_tin_hieu"
        ma = {t["ma"]: t for t in body["tin_hieu"]}
        assert "ja_sama" in ma and "ja_ore" in ma
        assert "ペッパー" in ma["ja_sama"]["ten_lien_quan"]
        assert ma["ja_sama"]["quotes"][0]["text"] == "ペッパー様、お待ちください"
        assert ma["ja_ore"]["ten_lien_quan"] == [], "đại từ không gắn được với tên nào — nói thật"

    async def test_khong_co_tin_hieu_thi_noi_thang(self, client, chapter_e17):
        pid = await chapter_e17(["hello", "goodbye"])
        body = (await client.get(f"/api/v1/projects/{pid}/voice-signals")).json()
        assert body["trang_thai"] == "khong_thay" and body["tin_hieu"] == []


class TestTang3:
    async def test_tao_luot_hoi_tra_202_va_dung_o_queued(self, client, chapter_e17):
        pid = await chapter_e17(["I met Pepper today", "We saw Pepper again"])
        r = await client.post(f"/api/v1/projects/{pid}/term-suggestions",
                              json={"series_name": "Pepper&Carrot"})
        assert r.status_code == 202
        body = r.json()
        assert body["status"] == "queued"
        assert body["suggestions"] is None, (
            "`null` = chưa chạy xong. `[]` = xong mà không mục nào qua cổng. Không được gộp."
        )
        assert body["series_name"] == "Pepper&Carrot"

    async def test_doc_lai_luot_hoi(self, client, chapter_e17):
        pid = await chapter_e17(["I met Pepper today", "We saw Pepper again"])
        rid = (await client.post(f"/api/v1/projects/{pid}/term-suggestions",
                                 json={"series_name": "X"})).json()["id"]
        r = await client.get(f"/api/v1/term-suggestion-runs/{rid}")
        assert r.status_code == 200 and r.json()["id"] == rid

    async def test_khong_co_ung_vien_thi_KHONG_goi_mo_hinh(self, client, chapter_e17, monkeypatch):
        """Hỏi suông vẫn tốn tiền, và câu trả lời cho một danh sách rỗng chắc chắn là bịa."""
        from app.workers import tasks

        def no(*a, **k):
            raise AssertionError("đã gọi mô hình dù không có ứng viên nào")
        monkeypatch.setattr(tasks, "build_translator", no)

        pid = await chapter_e17(["yes", "no"])
        rid = (await client.post(f"/api/v1/projects/{pid}/term-suggestions",
                                 json={"series_name": "X"})).json()["id"]
        ket = tasks._run_term_suggestion(uuid.UUID(rid))

        assert ket["status"] == "done" and ket["asked"] == 0
        with sync_session() as s:
            run = s.get(TermSuggestionRun, uuid.UUID(rid))
            assert run.status is TermSuggestionStatus.done
            assert run.suggestions == [], "xong-mà-rỗng phải là [] chứ không phải null"

    async def test_cong_doi_chieu_loai_muc_bia_va_khong_tao_thuat_ngu(
        self, client, chapter_e17, monkeypatch
    ):
        """Ca đắt giá nhất của tầng 3: model trả về một nhân vật KHÔNG có trong chapter."""
        from app.workers import tasks

        class ModelGia:
            def goi_prompt_tho(self, prompt):
                assert "Pepper" in prompt, "phải hỏi đúng danh xưng lấy từ chapter"
                return (
                    (
                        "1. Pepper => Pepper | character_name | cô phù thuỷ\n"
                        "2. Naruto Uzumaki => Naruto | character_name | nhân vật chính\n"
                    ),
                    {"totalTokenCount": 42},
                )

        monkeypatch.setattr(tasks, "build_translator", lambda engine: ModelGia())
        monkeypatch.setattr(tasks, "_cong_nhip", lambda engine: None)

        pid = await chapter_e17(["I met Pepper today", "We saw Pepper again"])
        rid = (await client.post(f"/api/v1/projects/{pid}/term-suggestions",
                                 json={"series_name": "Pepper&Carrot"})).json()["id"]
        ket = tasks._run_term_suggestion(uuid.UUID(rid))

        assert ket["kept"] == 1 and ket["dropped"] == 1
        with sync_session() as s:
            run = s.get(TermSuggestionRun, uuid.UUID(rid))
            assert [g["source_term"] for g in run.suggestions] == ["Pepper"]
            assert all(g["nguon"] == "goi_y_mo_hinh_chua_duyet" for g in run.suggestions)
            assert run.dropped_count == 1, "con số này là bằng chứng model có bịa — không được nuốt"
        assert _dem_ban_ghi(pid) == (0, 0), "tầng 3 KHÔNG được tự tạo thuật ngữ"

    async def test_mo_hinh_hong_thi_ghi_that_chu_khong_tra_goi_y_rong(
        self, client, chapter_e17, monkeypatch
    ):
        from app.services.translate.engines import TranslationFailed
        from app.workers import tasks

        class ModelHong:
            def goi_prompt_tho(self, prompt):
                raise TranslationFailed("HTTP 429: hết nhịp")

        monkeypatch.setattr(tasks, "build_translator", lambda engine: ModelHong())
        monkeypatch.setattr(tasks, "_cong_nhip", lambda engine: None)

        pid = await chapter_e17(["I met Pepper today", "We saw Pepper again"])
        rid = (await client.post(f"/api/v1/projects/{pid}/term-suggestions",
                                 json={"series_name": "X"})).json()["id"]
        tasks._run_term_suggestion(uuid.UUID(rid))

        with sync_session() as s:
            run = s.get(TermSuggestionRun, uuid.UUID(rid))
            assert run.status is TermSuggestionStatus.failed
            assert "429" in run.error_log
            assert run.suggestions is None, "hỏng thì để null, KHÔNG trả [] như thể đã hỏi xong"


class TestDoiChieuTenChinhThuc:
    """E17 tầng 3b — endpoint đối chiếu danh xưng chapter với CSDL AniList.

    Nguyên tắc: **chapter quyết định cần gì, CSDL chỉ trả lời viết thế nào.**
    """

    async def test_project_khong_ton_tai_tra_404(self, client):
        import uuid as _u
        r = await client.post(f"/api/v1/projects/{_u.uuid4()}/term-official-names",
                              json={"ten_bo_truyen": "Naruto"})
        assert r.status_code == 404

    async def test_thieu_ten_bo_truyen_thi_422_chu_khong_doan_ho(self, client):
        """Đoán hộ tên bộ truyện là đối chiếu chapter này với nhân vật của một bộ khác."""
        pr = await client.post("/api/v1/projects", json={
            "name": "t3b", "source_lang": "ja", "target_lang": "vi", "intended_use": "personal"})
        r = await client.post(f"/api/v1/projects/{pr.json()['id']}/term-official-names", json={})
        assert r.status_code == 422

    async def test_AniList_hong_thi_van_200_va_NOI_RA_ly_do(self, client, monkeypatch):
        """Nguồn ngoài sập không được kéo theo cả lượt rà soát — nhưng cũng không được im lặng."""
        import urllib.request

        def sap(*a, **k):
            raise OSError("mạng đứt")
        monkeypatch.setattr(urllib.request, "urlopen", sap)

        pr = await client.post("/api/v1/projects", json={
            "name": "t3b hỏng", "source_lang": "ja", "target_lang": "vi",
            "intended_use": "personal"})
        r = await client.post(f"/api/v1/projects/{pr.json()['id']}/term-official-names",
                              json={"ten_bo_truyen": "Naruto"})
        assert r.status_code == 200
        d = r.json()
        assert d["khong_dung_duoc"], "hỏng mà không nói lý do"
        assert d["khop"] == []

    async def test_chapter_KHONG_co_danh_xung_thi_khong_hoi_CSDL_lam_gi(self, client, monkeypatch):
        """Không có gì để đối chiếu thì đừng làm phiền nguồn ngoài."""
        import urllib.request
        goi = {"n": 0}

        def dem(*a, **k):
            goi["n"] += 1
            raise OSError("không nên tới đây")
        monkeypatch.setattr(urllib.request, "urlopen", dem)

        pr = await client.post("/api/v1/projects", json={
            "name": "t3b rỗng", "source_lang": "ja", "target_lang": "vi",
            "intended_use": "personal"})
        r = await client.post(f"/api/v1/projects/{pr.json()['id']}/term-official-names",
                              json={"ten_bo_truyen": "Naruto"})
        assert r.status_code == 200
        assert r.json()["khop"] == []
