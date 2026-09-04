"""Integration — rút gọn bản dịch cho vừa bong bóng, chạy trên DB thật (E18).

Tái hiện đúng cảnh đã đo trên trang manga thật: bản dịch tiếng Việt dài hơn hẳn chỗ chứa, khung
đã nới hết cỡ mà vẫn tràn.
"""
from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from app.core.db_sync import sync_session
from app.models import Job, TextRegion, TranslationResult, TypesetResult
from app.models.enums import FitStatus, JobStatus, JobType, OCREngine, PageStatus
from app.services.detect.ctd import DetectedRegion
from app.services.interfaces import BBox
from app.workers import tasks
from app.workers.tasks import (
    run_detect_job,
    run_inpaint_job,
    run_ocr_job,
    run_translate_job,
    run_typeset_job,
)

#: Dài gấp nhiều lần chỗ chứa — đúng tỉ lệ đã đo trên trang thật: bong bóng vẽ vừa ~30 ký tự
#: tiếng Nhật, bản dịch tiếng Việt về 105 ký tự. Ở đây phóng đại thêm để chắc chắn tràn kể cả
#: sau khi A1 đã nới khung ra hết lòng bong bóng.
DAI = (
    "Tôi nghe nói rằng cô gái tôi từng thích đã kể về những chuyến phiêu lưu thời thơ ấu "
    "của cô ấy, và thật lòng mà nói thì tôi không thể nào tin nổi chuyện đó lại xảy ra "
    "đúng vào lúc mọi người đang ngồi quanh bàn ăn tối hôm ấy"
)
NGAN = "Cô ấy kể chuyện hồi bé."


def _job_id(page_id: str, loai: JobType) -> str:
    with sync_session() as s:
        job = s.execute(
            sa.select(Job).where(Job.page_id == uuid.UUID(page_id), Job.type == loai)
            .order_by(Job.created_at.desc())
        ).scalars().first()
        return str(job.id)


def _trang_thai(page_id: str) -> list[FitStatus]:
    with sync_session() as s:
        return list(s.execute(
            sa.select(TypesetResult.fit_status)
            .join(TextRegion, TextRegion.id == TypesetResult.region_id)
            .where(TextRegion.page_id == uuid.UUID(page_id))
        ).scalars())


def _ban_dich(page_id: str) -> list[str]:
    with sync_session() as s:
        return list(s.execute(
            sa.select(TranslationResult.translated_text)
            .join(TextRegion, TextRegion.id == TranslationResult.region_id)
            .where(TextRegion.page_id == uuid.UUID(page_id))
            .order_by(TextRegion.reading_order)
        ).scalars())


def _anh_bong_bong_be() -> bytes:
    """Trang có bong bóng NHỎ — như bong bóng manga thật.

    Không dùng `sample_page_image` của conftest: bong bóng ở đó rộng 470×280, mà từ A1 khung
    chữ được nới ra tới cả lòng bong bóng, nên bản dịch dài mấy cũng vừa. Muốn tái hiện cảnh
    tràn thật thì phải có một bong bóng nhỏ đúng nghĩa — và đó chính là cảnh của manga: bong
    bóng vẽ vừa đúng lượng chữ tiếng Nhật.
    """
    import io

    from PIL import Image, ImageDraw

    img = Image.new("RGB", (600, 800), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([20, 20, 580, 780], outline="black", width=5)
    d.ellipse([200, 200, 340, 300], outline="black", width=4, fill="white")  # 140×100
    d.text((235, 240), "テスト", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _ve_lai_anh_clean(storage_root: str, rel: str) -> None:
    """Vẽ NÉT MỰC vào ảnh clean.

    `fake_inpainter` của conftest ghi ra một ảnh **trắng tinh hoàn toàn**. Từ A1, không có nét
    mực nào nghĩa là không có gì chặn phép nới: khung phình tới kịch trần và bản dịch dài mấy
    cũng vừa. Trang thật thì luôn có viền bong bóng — thiếu nó thì bộ test đang đo một thế giới
    không tồn tại.
    """
    from pathlib import Path

    from PIL import Image, ImageDraw

    duong_dan = Path(storage_root) / rel
    with Image.open(duong_dan) as im:
        anh = im.convert("RGB").copy()
    d = ImageDraw.Draw(anh)
    d.rectangle([20, 20, 580, 780], outline="black", width=5)
    d.ellipse([200, 200, 340, 300], outline="black", width=4)
    anh.save(duong_dan)


@pytest.fixture
def trang_tran(client, storage_root, fake_detector, fake_ocr_engine,
               fake_inpainter, fake_translator, no_broker_for_chained_ocr):
    """Một trang có đúng 1 vùng trong bong bóng NHỎ, bản dịch DÀI ⇒ chắc chắn tràn khung."""
    async def _go():
        proj = await client.post("/api/v1/projects", json={
            "name": "E18", "source_lang": "ja", "intended_use": "study"})
        pid = proj.json()["id"]
        up = await client.post(f"/api/v1/projects/{pid}/pages",
                               files={"file": ("p.png", _anh_bong_bong_be(), "image/png")})
        page_id = up.json()["page_id"]

        fake_detector(regions=[DetectedRegion(bbox=BBox(x=235, y=238, w=70, h=26),
                                              confidence=0.9, cls=0)])
        run_detect_job(up.json()["job_id"])
        fake_ocr_engine(results=("そんなん人それぞれだろ", 0.9), engine_enum=OCREngine.manga_ocr)
        run_ocr_job(_job_id(page_id, JobType.ocr))
        fake_inpainter()
        fake_ocr_engine(results=("", None), engine_enum=OCREngine.manga_ocr)
        run_inpaint_job(_job_id(page_id, JobType.inpaint))
        from app.models import Page
        with sync_session() as s:
            _ve_lai_anh_clean(storage_root, s.get(Page, uuid.UUID(page_id)).clean_image_path)
        fake_translator(prefix="")
        run_translate_job(_job_id(page_id, JobType.translate))

        with sync_session() as s:
            row = s.execute(sa.select(TranslationResult)
                            .join(TextRegion, TextRegion.id == TranslationResult.region_id)
                            .where(TextRegion.page_id == uuid.UUID(page_id))).scalars().one()
            row.translated_text = DAI
            s.commit()
        run_typeset_job(_job_id(page_id, JobType.typeset))
        assert _trang_thai(page_id) == [FitStatus.overflow_warning], "tiền đề: phải đang tràn"
        return pid, page_id
    return _go


def _model_gia(monkeypatch, tra_ve, ghi_prompt=None):
    class Model:
        def goi_prompt_tho(self, prompt):
            if ghi_prompt is not None:
                ghi_prompt.append(prompt)
            return tra_ve, {"totalTokenCount": 30}
    monkeypatch.setattr(tasks, "build_translator", lambda engine: Model())
    monkeypatch.setattr(tasks, "_cong_nhip", lambda engine: None)


class TestRutGon:
    async def test_rut_gon_xong_thi_vua_khung(self, client, trang_tran, monkeypatch):
        _pid, page_id = await trang_tran()
        _model_gia(monkeypatch, f"1. {NGAN}")

        r = await client.post(f"/api/v1/pages/{page_id}/fit-translation")
        assert r.status_code == 202
        kq = tasks._run_rut_gon(uuid.UUID(r.json()["job_id"]))

        assert kq["status"] == "done"
        assert kq["so_vung_rut_gon"] == 1
        assert _ban_dich(page_id) == [NGAN]
        assert _trang_thai(page_id) == [FitStatus.fit_ok], "rút gọn xong phải căn lại luôn"
        assert kq["con_tran"] == 0

    async def test_prompt_mang_theo_SUC_CHUA_va_chu_goc(self, client, trang_tran, monkeypatch):
        _pid, page_id = await trang_tran()
        prompts: list[str] = []
        _model_gia(monkeypatch, f"1. {NGAN}", ghi_prompt=prompts)

        r = await client.post(f"/api/v1/pages/{page_id}/fit-translation")
        tasks._run_rut_gon(uuid.UUID(r.json()["job_id"]))

        assert "tối đa" in prompts[0] and "ký tự" in prompts[0]
        assert "そんなん人それぞれだろ" in prompts[0], "phải đưa chữ gốc vào, không chỉ cắt câu tiếng Việt"
        assert DAI in prompts[0]

    async def test_KHONG_dung_toi_vung_nguoi_dung_da_sua_tay(
        self, client, trang_tran, monkeypatch
    ):
        """Đè lên chữ người ta tự gõ là việc không ai xin — và bản gốc của họ không lưu ở đâu."""
        _pid, page_id = await trang_tran()
        with sync_session() as s:
            row = s.execute(sa.select(TranslationResult)
                            .join(TextRegion, TextRegion.id == TranslationResult.region_id)
                            .where(TextRegion.page_id == uuid.UUID(page_id))).scalars().one()
            row.edited_by_user = True
            s.commit()
        _model_gia(monkeypatch, f"1. {NGAN}")

        r = await client.post(f"/api/v1/pages/{page_id}/fit-translation")
        kq = tasks._run_rut_gon(uuid.UUID(r.json()["job_id"]))

        assert kq["so_vung_rut_gon"] == 0
        assert len(kq["bo_qua_sua_tay"]) == 1, "phải NÓI RA là đã bỏ qua, không im lặng"
        assert _ban_dich(page_id) == [DAI], "chữ người dùng sửa tay phải còn nguyên"

    async def test_model_tra_rac_thi_GIU_NGUYEN_ban_dich_cu(
        self, client, trang_tran, monkeypatch
    ):
        _pid, page_id = await trang_tran()
        _model_gia(monkeypatch, "xin lỗi, tôi không hiểu yêu cầu")

        r = await client.post(f"/api/v1/pages/{page_id}/fit-translation")
        kq = tasks._run_rut_gon(uuid.UUID(r.json()["job_id"]))

        assert kq["so_vung_rut_gon"] == 0
        assert _ban_dich(page_id) == [DAI]

    async def test_model_viet_DAI_HON_thi_khong_nhan(self, client, trang_tran, monkeypatch):
        _pid, page_id = await trang_tran()
        _model_gia(monkeypatch, f"1. {DAI} và còn nhiều chuyện khác nữa")

        r = await client.post(f"/api/v1/pages/{page_id}/fit-translation")
        kq = tasks._run_rut_gon(uuid.UUID(r.json()["job_id"]))

        assert kq["so_vung_rut_gon"] == 0
        assert _ban_dich(page_id) == [DAI]

    async def test_model_hong_thi_job_failed_va_ban_dich_KHONG_doi(
        self, client, trang_tran, monkeypatch
    ):
        """Rút gọn hỏng thì thà không đổi gì, còn hơn để lại trang nửa cũ nửa mới."""
        from app.services.translate.engines import TranslationFailed

        _pid, page_id = await trang_tran()

        class ModelHong:
            def goi_prompt_tho(self, prompt):
                raise TranslationFailed("hết quota giả lập")

        monkeypatch.setattr(tasks, "build_translator", lambda engine: ModelHong())
        monkeypatch.setattr(tasks, "_cong_nhip", lambda engine: None)

        r = await client.post(f"/api/v1/pages/{page_id}/fit-translation")
        jid = uuid.UUID(r.json()["job_id"])
        kq = tasks.run_rut_gon_job(jid)

        assert kq["status"] == "failed"
        assert _ban_dich(page_id) == [DAI]
        with sync_session() as s:
            assert s.get(Job, jid).status is JobStatus.failed


class TestCongVao:
    async def test_trang_khong_co_vung_tran_thi_TU_CHOI_chu_khong_goi_model(
        self, client, trang_tran, monkeypatch
    ):
        """Hỏi suông vẫn tốn token, mà bản dịch đang vừa khung thì rút gọn là mất chữ vô cớ."""
        _pid, page_id = await trang_tran()
        with sync_session() as s:
            row = s.execute(sa.select(TypesetResult)
                            .join(TextRegion, TextRegion.id == TypesetResult.region_id)
                            .where(TextRegion.page_id == uuid.UUID(page_id))).scalars().one()
            row.fit_status = FitStatus.fit_ok
            s.commit()

        r = await client.post(f"/api/v1/pages/{page_id}/fit-translation")
        assert r.status_code == 422
        assert "khong_co_vung_tran" in r.json()["detail"]

    async def test_trang_khong_ton_tai_tra_404(self, client):
        r = await client.post(f"/api/v1/pages/{uuid.uuid4()}/fit-translation")
        assert r.status_code == 404

    async def test_trang_cua_nguoi_khac_KHONG_dung_toi_duoc(self, client, trang_tran):
        """Cùng luật quyền như mọi đường khác — không có ngoại lệ cho endpoint mới."""
        _pid, page_id = await trang_tran()
        assert (await client.post(f"/api/v1/pages/{page_id}/fit-translation")).status_code == 202
        # (kiểm chéo tài khoản đã có bộ riêng quét toàn bộ route; ở đây chỉ chốt là có gác)
        with sync_session() as s:
            assert s.get(Job, uuid.UUID(_job_id(page_id, JobType.translate))) is not None


class TestTrangThaiTrang:
    async def test_trang_van_o_typeset_done_sau_khi_rut_gon(
        self, client, trang_tran, monkeypatch
    ):
        _pid, page_id = await trang_tran()
        _model_gia(monkeypatch, f"1. {NGAN}")
        r = await client.post(f"/api/v1/pages/{page_id}/fit-translation")
        tasks._run_rut_gon(uuid.UUID(r.json()["job_id"]))

        from app.models import Page
        with sync_session() as s:
            assert s.get(Page, uuid.UUID(page_id)).status is PageStatus.typeset_done


class TestDichLaiPhaiCanLai:
    """Dịch lại MỘT vùng mà không căn chữ lại thì trạng thái để lại là của bản dịch cũ.

    Đo được 05/09 trên trang thật của người dùng: dịch lại 2 vùng xong, trang báo **0/8 tràn**
    trong khi chạy lại bước căn chữ ra **2/8 tràn**. Con số đã hết hạn hiện ra y như con số
    thật, không dấu hiệu nào phân biệt.
    """

    async def test_dich_lai_vung_thi_tu_xep_viec_can_lai_chu(
        self, client, trang_tran, monkeypatch
    ):
        from app.models.enums import TranslationEngine

        _pid, page_id = await trang_tran()
        with sync_session() as s:
            rid = s.execute(sa.select(TextRegion.id).where(
                TextRegion.page_id == uuid.UUID(page_id))).scalars().one()

        da_xep: list[tuple] = []
        monkeypatch.setattr(tasks.run_refit_job, "delay",
                            lambda job_id, region_id: da_xep.append((job_id, region_id)))

        class Dich:
            engine_enum = TranslationEngine.google_fast
            model_name = "gia-lap"
            usage = None

            def translate(self, texts, source_lang, target_lang):
                return ["Ngắn thôi."]

        monkeypatch.setattr(tasks, "build_translator", lambda engine: Dich())

        with sync_session() as s:
            job = Job(type=JobType.translate, page_id=uuid.UUID(page_id), status=JobStatus.queued)
            s.add(job)
            s.commit()
            jid = job.id
        kq = tasks._run_region_retranslate(jid, rid, None)

        assert kq["refit_job_id"], "dịch lại xong phải xếp việc căn lại chữ"
        assert da_xep and da_xep[0][1] == str(rid)
