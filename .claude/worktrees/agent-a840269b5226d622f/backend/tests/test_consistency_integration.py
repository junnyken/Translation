"""Integration — thuật ngữ, quét nhất quán, áp dụng (E13) trên DB thật."""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa

from app.core.db_sync import sync_session
from app.models import (
    ConsistencyReviewTask,
    GlossaryEntry,
    OCRResult,
    Page,
    RegionQualityAssessment,
    TextRegion,
    TranslationResult,
)
from app.models.enums import (
    ConsistencyTaskStatus,
    ConsistencyTaskType,
    GlossaryStatus,
    JobType,
    OCRStatus,
    OCREngine,
    ConfidenceState,
    RegionRelevance,
    TranslationState,
    PageStatus,
    ReviewStatus,
    VoiceProfileStatus,
)
from app.services.consistency.apply import (
    ConsistencyApplyService,
    TaskInvalid,
    TaskStale,
)
from app.services.consistency.glossary import GlossaryInvalid, GlossaryService, VoiceProfileService
from app.services.consistency.scanner import ConsistencyScanner, bam_ban_dich


def _md5(p) -> str:
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


@pytest.fixture
async def chapter(client, sample_page_image, no_broker_for_chained_ocr):
    """Chapter 2 trang, mỗi trang 2 vùng có chữ gốc + bản dịch — dựng thẳng vào DB cho nhanh."""
    async def _go(cap_van_ban=None, ten="Chapter E13"):
        proj = await client.post(
            "/api/v1/projects",
            json={"name": ten, "source_lang": "en", "intended_use": "study"},
        )
        pid = uuid.UUID(proj.json()["id"])
        cap = cap_van_ban or [
            ("I drink a magic potion", "Tôi uống lọ thuốc ma thuật"),
            ("Pepper is here", "Pepper đang ở đây"),
        ]
        vung_ids = []
        for i, (goc, dich) in enumerate(cap):
            up = await client.post(
                f"/api/v1/projects/{pid}/pages",
                files={"file": (f"{i + 1:03d}.png", sample_page_image, "image/png")},
            )
            page_id = uuid.UUID(up.json()["page_id"])
            with sync_session() as s:
                page = s.get(Page, page_id)
                page.status = PageStatus.typeset_done
                r = TextRegion(
                    page_id=page_id, bbox_x=10, bbox_y=10, bbox_w=200, bbox_h=80,
                    confidence=0.9, reading_order=1,
                )
                s.add(r)
                s.flush()
                s.add(OCRResult(region_id=r.id, raw_text=goc, ocr_engine=OCREngine.manga_ocr,
                                status=OCRStatus.ok))
                s.add(TranslationResult(region_id=r.id, translated_text=dich))
                s.commit()
                vung_ids.append(r.id)
        return pid, vung_ids
    return _go


def _them_thuat_ngu(pid, **kw) -> uuid.UUID:
    mac_dinh = dict(
        source_term="magic potion", target_term="bình thuốc phép",
        term_type="item", definition="Lọ thuốc do phù thuỷ pha chế",
    )
    mac_dinh.update(kw)
    with sync_session() as s:
        e = GlossaryService(s).create_entry(pid, mac_dinh)
        return e.id


def _duyet(entry_id):
    with sync_session() as s:
        GlossaryService(s).approve_entry(entry_id)


def _quet(pid):
    with sync_session() as s:
        return ConsistencyScanner(s).scan_project(pid)


def _viec(pid, **loc) -> list[ConsistencyReviewTask]:
    with sync_session() as s:
        q = sa.select(ConsistencyReviewTask).where(ConsistencyReviewTask.project_id == pid)
        for k, v in loc.items():
            q = q.where(getattr(ConsistencyReviewTask, k) == v)
        return list(s.execute(q.order_by(ConsistencyReviewTask.created_at)).scalars())


# ---------------- vòng đời thuật ngữ ----------------


async def test_thieu_dinh_nghia_thi_bi_tu_choi(chapter):
    pid, _ = await chapter()
    with pytest.raises(GlossaryInvalid, match="definition_required"):
        _them_thuat_ngu(pid, definition="")


async def test_thuat_ngu_luon_bat_dau_o_nhap(chapter):
    pid, _ = await chapter()
    with sync_session() as s:
        assert s.get(GlossaryEntry, _them_thuat_ngu(pid)).status is GlossaryStatus.draft


async def test_trung_thuat_ngu_bi_chan_theo_khoa_chuan_hoa(chapter):
    pid, _ = await chapter()
    _them_thuat_ngu(pid, source_term="Magic Potion")
    with pytest.raises(GlossaryInvalid, match="duplicate_term"):
        _them_thuat_ngu(pid, source_term="  magic   potion  ")


async def test_sua_noi_dung_da_duyet_thi_ve_lai_nhap(chapter):
    """Không làm vậy thì một luật cả chapter đang dùng bị đổi nghĩa âm thầm."""
    pid, _ = await chapter()
    eid = _them_thuat_ngu(pid)
    _duyet(eid)
    with sync_session() as s:
        GlossaryService(s).update_entry(eid, {"target_term": "bình thuốc thần"})
        assert s.get(GlossaryEntry, eid).status is GlossaryStatus.draft


async def test_sua_ghi_chu_khong_lam_mat_trang_thai_da_duyet(chapter):
    """Ghi chú không đổi nghĩa của luật nên không cần duyệt lại."""
    pid, _ = await chapter()
    eid = _them_thuat_ngu(pid)
    _duyet(eid)
    with sync_session() as s:
        GlossaryService(s).update_entry(eid, {"usage_note": "chỉ dùng khi nói với phù thuỷ"})
        assert s.get(GlossaryEntry, eid).status is GlossaryStatus.approved


async def test_luu_tru_khong_xoa_viec_da_tao(chapter):
    pid, _ = await chapter()
    eid = _them_thuat_ngu(pid)
    _duyet(eid)
    _quet(pid)
    truoc = len(_viec(pid))
    with sync_session() as s:
        GlossaryService(s).archive_entry(eid)
    assert len(_viec(pid)) == truoc, "lưu trữ không được xoá bằng chứng đã có"


# ---------------- quét ----------------


async def test_chi_thuat_ngu_da_duyet_moi_duoc_quet(chapter):
    pid, _ = await chapter()
    _them_thuat_ngu(pid)          # để nháp
    assert _quet(pid).tao_moi == 0
    assert _viec(pid) == []


async def test_tim_ra_cho_chua_dung_thuat_ngu_da_chot(chapter):
    pid, vung = await chapter()
    eid = _them_thuat_ngu(pid)
    _duyet(eid)
    tom_tat = _quet(pid)

    assert tom_tat.tao_moi == 1
    v = _viec(pid)[0]
    assert v.task_type is ConsistencyTaskType.glossary_missing
    assert v.status is ConsistencyTaskStatus.open
    assert v.region_id == vung[0]
    assert v.evidence["thuat_ngu_da_duyet"] == "bình thuốc phép"
    assert "magic potion" in v.evidence["doan_khop_chu"]
    assert "bình thuốc phép" in v.evidence["ly_do"]


async def test_ban_dich_da_dung_thuat_ngu_thi_khong_tao_viec(chapter):
    pid, _ = await chapter(cap_van_ban=[("I drink a magic potion", "Tôi uống bình thuốc phép")])
    _duyet(_them_thuat_ngu(pid))
    assert _quet(pid).tao_moi == 0


async def test_bien_the_bi_cam_bi_gan_co(chapter):
    pid, _ = await chapter(cap_van_ban=[("magic potion", "Tôi uống thuốc ma thuật")])
    eid = _them_thuat_ngu(pid, prohibited_variants=["thuốc ma thuật"])
    _duyet(eid)
    _quet(pid)
    loai = {v.task_type for v in _viec(pid)}
    assert ConsistencyTaskType.prohibited_variant in loai


async def test_khong_tu_nghi_ra_tu_dong_nghia_de_cam(chapter):
    """Chỉ biến thể NGƯỜI DÙNG tự khai mới bị gắn cờ — máy không tự bịa từ cấm."""
    pid, _ = await chapter(cap_van_ban=[("magic potion", "Tôi uống thuốc ma thuật")])
    _duyet(_them_thuat_ngu(pid))   # không khai prohibited_variants
    loai = {v.task_type for v in _viec(pid)} if _quet(pid) else set()
    assert ConsistencyTaskType.prohibited_variant not in loai


async def test_khong_co_chu_goc_thi_khong_ket_luan_gi(chapter):
    """Đoán thuật ngữ từ bản dịch là bịa bằng chứng — chất lượng vùng là việc của E12."""
    pid, vung = await chapter()
    with sync_session() as s:
        ocr = s.execute(sa.select(OCRResult).where(OCRResult.region_id == vung[0])).scalars().one()
        ocr.raw_text = ""
        ocr.status = OCRStatus.needs_manual
        s.commit()
    _duyet(_them_thuat_ngu(pid))
    assert _quet(pid).tao_moi == 0


async def test_vung_da_bo_qua_o_e12_khong_bi_quet_lai(chapter):
    """Người dùng đã xem và quyết định rồi — dựng lại việc là phớt lờ quyết định của họ."""
    pid, vung = await chapter()
    with sync_session() as s:
        s.add(RegionQualityAssessment(
            region_id=vung[0], assessment_version="test",
            relevance=RegionRelevance.likely_translatable,
            review_status=ReviewStatus.reviewed_skip,
            detector_confidence_state=ConfidenceState.available,
            ocr_confidence_state=ConfidenceState.unavailable,
            translation_state=TranslationState.present,
        ))
        s.commit()
    _duyet(_them_thuat_ngu(pid))
    tom_tat = _quet(pid)
    assert tom_tat.tao_moi == 0
    assert tom_tat.so_vung_bo_qua >= 1


async def test_quet_khong_bao_gio_sua_ban_dich(chapter):
    pid, vung = await chapter()
    with sync_session() as s:
        truoc = [
            (t.translated_text, t.edited_by_user)
            for t in s.execute(sa.select(TranslationResult)).scalars()
        ]
    _duyet(_them_thuat_ngu(pid))
    _quet(pid)
    with sync_session() as s:
        sau = [
            (t.translated_text, t.edited_by_user)
            for t in s.execute(sa.select(TranslationResult)).scalars()
        ]
    assert sau == truoc, "quét chỉ được TẠO VIỆC, không được sửa gì"


async def test_quet_lai_khong_tao_viec_trung(chapter):
    """Ràng buộc UNIQUE NULLS NOT DISTINCT là thứ làm điều này chạy được."""
    pid, _ = await chapter()
    _duyet(_them_thuat_ngu(pid))
    _quet(pid)
    lan1 = len(_viec(pid))
    lan2 = _quet(pid)
    assert len(_viec(pid)) == lan1
    assert lan2.tao_moi == 0 and lan2.giu_nguyen >= 1


async def test_ban_dich_doi_thi_viec_cu_thanh_cu(chapter):
    pid, vung = await chapter()
    _duyet(_them_thuat_ngu(pid))
    _quet(pid)
    with sync_session() as s:
        t = s.execute(
            sa.select(TranslationResult).where(TranslationResult.region_id == vung[0])
        ).scalars().one()
        t.translated_text = "Một bản dịch hoàn toàn khác"
        s.commit()
    _quet(pid)
    tt = {v.status for v in _viec(pid)}
    assert ConsistencyTaskStatus.stale in tt


async def test_khong_ghi_de_quyet_dinh_cua_nguoi(chapter):
    """Người đã từ chối rồi thì quét lại KHÔNG được mở lại việc đó."""
    pid, _ = await chapter()
    _duyet(_them_thuat_ngu(pid))
    _quet(pid)
    v = _viec(pid)[0]
    with sync_session() as s:
        ConsistencyApplyService(s).reject_task(v.id, "keep_current")
    _quet(pid)
    with sync_session() as s:
        assert s.get(ConsistencyReviewTask, v.id).status is ConsistencyTaskStatus.resolved_no_change


async def test_thuat_ngu_cua_chapter_nay_khong_quet_chapter_khac(chapter):
    pid_a, _ = await chapter(ten="Chapter A")
    pid_b, _ = await chapter(ten="Chapter B")
    _duyet(_them_thuat_ngu(pid_a))
    _quet(pid_a)
    assert len(_viec(pid_a)) == 1
    assert _viec(pid_b) == [], "thuật ngữ của chapter A không được đụng vào chapter B"


async def test_so_ngan_sfx_khong_bi_tu_dong_bo_qua(chapter):
    """E13 không tự quyết định cái gì là 'nhiễu' — đó là việc của E12 và của người dùng."""
    pid, _ = await chapter(cap_van_ban=[("SPLASH 18", "BÕM! 18")])
    _duyet(_them_thuat_ngu(pid, source_term="SPLASH", target_term="TÕM",
                           term_type="general_term", definition="tiếng nước bắn"))
    tom_tat = _quet(pid)
    assert tom_tat.so_vung_xet == 1, "vùng chữ tượng thanh vẫn phải được xét"
    assert tom_tat.tao_moi == 1


# ---------------- áp dụng / từ chối ----------------


class _DayViecGia:
    def __init__(self):
        self.da_day = []

    def __call__(self, job_id, region_id, font_size=None):
        self.da_day.append((job_id, region_id, font_size))
        return True, None


def _ap(task_id, edited_text=None, day=None):
    day = day or _DayViecGia()
    with sync_session() as s:
        return ConsistencyApplyService(s, dispatcher=day).accept_task(task_id, edited_text), day


async def test_ap_dung_chi_doi_dung_mot_vung(chapter):
    pid, vung = await chapter()
    _duyet(_them_thuat_ngu(pid))
    _quet(pid)
    v = _viec(pid)[0]

    with sync_session() as s:
        truoc_khac = s.execute(
            sa.select(TranslationResult).where(TranslationResult.region_id == vung[1])
        ).scalars().one().translated_text

    _ap(v.id, "Tôi uống bình thuốc phép")

    with sync_session() as s:
        doi = s.execute(
            sa.select(TranslationResult).where(TranslationResult.region_id == vung[0])
        ).scalars().one()
        khac = s.execute(
            sa.select(TranslationResult).where(TranslationResult.region_id == vung[1])
        ).scalars().one()
    assert doi.translated_text == "Tôi uống bình thuốc phép"
    assert doi.edited_by_user is True
    assert khac.translated_text == truoc_khac, "vùng khác không được đụng tới"
    assert khac.edited_by_user is False


async def test_ap_dung_khong_dung_chu_goc_ocr(chapter):
    """Chữ gốc của M3 phải giữ nguyên để về sau còn đối chiếu."""
    pid, vung = await chapter()
    _duyet(_them_thuat_ngu(pid))
    _quet(pid)
    with sync_session() as s:
        truoc = s.execute(sa.select(OCRResult).where(OCRResult.region_id == vung[0])).scalars().one().raw_text
    _ap(_viec(pid)[0].id, "Tôi uống bình thuốc phép")
    with sync_session() as s:
        sau = s.execute(sa.select(OCRResult).where(OCRResult.region_id == vung[0])).scalars().one().raw_text
    assert sau == truoc == "I drink a magic potion"


async def test_ap_dung_xep_viec_canh_lai_dung_vung_do(chapter):
    pid, vung = await chapter()
    _duyet(_them_thuat_ngu(pid))
    _quet(pid)
    kq, day = _ap(_viec(pid)[0].id, "Tôi uống bình thuốc phép")

    assert kq.refit_job_id is not None
    assert len(day.da_day) == 1, "chỉ canh lại MỘT vùng, không chạy lại cả trang"
    assert day.da_day[0][1] == vung[0]
    assert day.da_day[0][2] is None, "không truyền cỡ chữ ⇒ giữ nguyên cỡ đã ghim ở M7"


async def test_ban_dich_doi_roi_thi_tu_choi_ap_de(chapter):
    """Chốt chặn quan trọng nhất: áp bản cũ sẽ xoá mất phần người khác vừa sửa."""
    pid, vung = await chapter()
    _duyet(_them_thuat_ngu(pid))
    _quet(pid)
    v = _viec(pid)[0]

    with sync_session() as s:   # ai đó sửa tay ở M7 trong lúc này
        t = s.execute(
            sa.select(TranslationResult).where(TranslationResult.region_id == vung[0])
        ).scalars().one()
        t.translated_text = "Bản người khác vừa sửa"
        s.commit()

    with pytest.raises(TaskStale, match="task_stale"):
        _ap(v.id, "Tôi uống bình thuốc phép")

    with sync_session() as s:
        assert s.execute(
            sa.select(TranslationResult).where(TranslationResult.region_id == vung[0])
        ).scalars().one().translated_text == "Bản người khác vừa sửa"
        assert s.get(ConsistencyReviewTask, v.id).status is ConsistencyTaskStatus.stale


async def test_khong_ap_duoc_viec_da_xu_ly(chapter):
    pid, _ = await chapter()
    _duyet(_them_thuat_ngu(pid))
    _quet(pid)
    v = _viec(pid)[0]
    _ap(v.id, "Tôi uống bình thuốc phép")
    with pytest.raises(TaskInvalid, match="task_not_open"):
        _ap(v.id, "lần nữa")


async def test_khong_co_de_xuat_va_khong_tu_nhap_thi_tu_choi(chapter):
    """Luật quét chỉ CHỈ RA vấn đề, không tự viết bản dịch thay người."""
    pid, _ = await chapter()
    _duyet(_them_thuat_ngu(pid))
    _quet(pid)
    with pytest.raises(TaskInvalid, match="empty_text"):
        _ap(_viec(pid)[0].id, None)


async def test_tu_choi_khong_doi_gi_ca(chapter):
    pid, vung = await chapter()
    _duyet(_them_thuat_ngu(pid))
    _quet(pid)
    v = _viec(pid)[0]
    with sync_session() as s:
        truoc = s.execute(
            sa.select(TranslationResult).where(TranslationResult.region_id == vung[0])
        ).scalars().one().translated_text
        ConsistencyApplyService(s).reject_task(v.id, "not_applicable")
    with sync_session() as s:
        assert s.execute(
            sa.select(TranslationResult).where(TranslationResult.region_id == vung[0])
        ).scalars().one().translated_text == truoc
        assert s.get(ConsistencyReviewTask, v.id).status is ConsistencyTaskStatus.rejected


async def test_ly_do_tu_choi_la_bi_chan(chapter):
    pid, _ = await chapter()
    _duyet(_them_thuat_ngu(pid))
    _quet(pid)
    with sync_session() as s:
        with pytest.raises(TaskInvalid, match="invalid_resolution"):
            ConsistencyApplyService(s).reject_task(_viec(pid)[0].id, "xoa_luon")


# ---------------- API ----------------


async def test_api_vong_doi_thuat_ngu(client, chapter):
    pid, _ = await chapter()
    r = await client.post(f"/api/v1/projects/{pid}/glossary", json={
        "source_term": "magic potion", "target_term": "bình thuốc phép",
        "term_type": "item", "definition": "Lọ thuốc phù thuỷ pha",
    })
    assert r.status_code == 201
    eid = r.json()["id"]
    assert r.json()["status"] == "draft"

    assert (await client.post(f"/api/v1/glossary/{eid}/approve")).json()["status"] == "approved"
    sua = await client.patch(f"/api/v1/glossary/{eid}", json={"target_term": "bình thuốc thần"})
    assert sua.json()["status"] == "draft", "sửa nội dung đã duyệt phải quay về nháp"
    assert (await client.post(f"/api/v1/glossary/{eid}/archive")).json()["status"] == "archived"


async def test_api_thieu_dinh_nghia_tra_422(client, chapter):
    pid, _ = await chapter()
    r = await client.post(f"/api/v1/projects/{pid}/glossary", json={
        "source_term": "x", "target_term": "y", "term_type": "item",
    })
    assert r.status_code == 422


async def test_api_ho_so_giong_nhan_vat(client, chapter):
    pid, _ = await chapter()
    r = await client.post(f"/api/v1/projects/{pid}/voice-profiles", json={
        "character_name": "Pepper", "speech_register": "casual",
        "vietnamese_pronoun_guidance": "xưng tớ, gọi cậu",
    })
    assert r.status_code == 201 and r.json()["status"] == "draft"
    hid = r.json()["id"]
    assert (await client.post(f"/api/v1/voice-profiles/{hid}/activate")).json()["status"] == "active"
    ds = await client.get(f"/api/v1/projects/{pid}/voice-profiles")
    assert len(ds.json()) == 1


async def test_api_tom_tat_khong_co_diem_chat_luong(client, chapter):
    """Không bao giờ chấm điểm 0–100 — máy không đo được bản dịch hay dở."""
    pid, _ = await chapter()
    _duyet(_them_thuat_ngu(pid))
    _quet(pid)
    r = await client.get(f"/api/v1/projects/{pid}/consistency-summary")
    body = r.json()
    assert body["open_count"] == 1
    assert body["approved_glossary_count"] == 1
    assert not any("score" in k or "quality" in k for k in body), body.keys()


async def test_api_danh_sach_viec_co_bang_chung(client, chapter):
    pid, _ = await chapter()
    _duyet(_them_thuat_ngu(pid))
    _quet(pid)
    r = await client.get(f"/api/v1/projects/{pid}/consistency-tasks")
    v = r.json()["items"][0]
    assert v["task_type"] == "glossary_missing"
    assert "ly_do" in v["evidence"] and "bình thuốc phép" in v["evidence"]["ly_do"]
    assert v["current_text_snapshot"]


async def test_api_ap_ban_dich_da_doi_tra_409(client, chapter):
    pid, vung = await chapter()
    _duyet(_them_thuat_ngu(pid))
    _quet(pid)
    v = _viec(pid)[0]
    with sync_session() as s:
        t = s.execute(
            sa.select(TranslationResult).where(TranslationResult.region_id == vung[0])
        ).scalars().one()
        t.translated_text = "đã đổi"
        s.commit()
    r = await client.post(f"/api/v1/consistency-tasks/{v.id}/accept",
                          json={"edited_text": "bình thuốc phép"})
    assert r.status_code == 409 and "task_stale" in r.text


async def test_api_khong_truy_cap_cheo_chapter(client, chapter):
    pid_a, _ = await chapter(ten="A")
    pid_b, _ = await chapter(ten="B")
    eid = _them_thuat_ngu(pid_a)
    ds = await client.get(f"/api/v1/projects/{pid_b}/glossary")
    assert ds.json() == [], "thuật ngữ chapter A không được lộ sang chapter B"


@pytest.mark.parametrize("body", [
    {"resolution": "xoa"}, {}, {"resolution": "keep_current", "la": 1},
])
async def test_api_du_lieu_tu_choi_sai_bi_chan(client, chapter, body):
    pid, _ = await chapter()
    _duyet(_them_thuat_ngu(pid))
    _quet(pid)
    r = await client.post(f"/api/v1/consistency-tasks/{_viec(pid)[0].id}/reject", json=body)
    assert r.status_code == 422
