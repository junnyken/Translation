"""E31 — CHỈ nạp thuật ngữ `approved` và giọng nhân vật `active` vào prompt.

Đây là tính chất an toàn cốt lõi của E31, và nó cần CSDL thật nên không thể canh bằng unit test.

Bản `draft` là **gợi ý của máy chưa ai duyệt** (E17 sinh ra). Đưa nó vào prompt là để mô hình tự
xác nhận phỏng đoán của chính nó, và biến một gợi ý sai thành cái sai **lặp trên cả chapter** —
đúng thứ nguyên tắc E13 cấm: *"máy chỉ ra chỗ kèm lý do, KHÔNG tự sửa"*.
"""
from __future__ import annotations

import uuid

import pytest

from app.core.db_sync import sync_session
from app.models import CharacterVoiceProfile, GlossaryEntry, Project
from app.models.enums import (
    GlossaryStatus, IntendedUse, SourceLang, TargetLang, TermType, VoiceProfileStatus,
)
from app.services.translate.boi_canh import nap_boi_canh_du_an


def _du_an(s) -> uuid.UUID:
    pr = Project(
        name=f"E31 {uuid.uuid4().hex[:8]}", source_lang=SourceLang.ja,
        target_lang=TargetLang.vi, intended_use=IntendedUse.study,
    )
    s.add(pr)
    s.flush()
    return pr.id


def _tn(pid, goc, dich, tt):
    return GlossaryEntry(
        project_id=pid, source_lang=SourceLang.ja, target_lang=TargetLang.vi,
        source_term=goc, source_term_key=goc, target_term=dich,
        term_type=TermType.item, definition="x", status=tt,
    )


@pytest.mark.parametrize("trang_thai,phai_co", [
    (GlossaryStatus.approved, True),
    (GlossaryStatus.draft, False),
    (GlossaryStatus.rejected, False),
    (GlossaryStatus.archived, False),
])
def test_chi_thuat_ngu_APPROVED_vao_prompt(trang_thai, phai_co):
    with sync_session() as s:
        pid = _du_an(s)
        s.add(_tn(pid, "風竜", "Rồng Gió", trang_thai))
        s.commit()
        ra = nap_boi_canh_du_an(s, pid)
    assert ("Rồng Gió" in ra) is phai_co, f"{trang_thai.value}: sai chiều"


@pytest.mark.parametrize("trang_thai,phai_co", [
    (VoiceProfileStatus.active, True),
    (VoiceProfileStatus.draft, False),
    (VoiceProfileStatus.archived, False),
])
def test_chi_giong_ACTIVE_vao_prompt(trang_thai, phai_co):
    with sync_session() as s:
        pid = _du_an(s)
        s.add(CharacterVoiceProfile(
            project_id=pid, character_name="Pepper", character_name_key="pepper",
            status=trang_thai,
        ))
        s.commit()
        ra = nap_boi_canh_du_an(s, pid)
    assert ("Pepper" in ra) is phai_co, f"{trang_thai.value}: sai chiều"


def test_chua_chot_gi_thi_tra_CHUOI_RONG():
    """Chuỗi rỗng ⇒ prompt không đổi một ký tự so với trước E31."""
    with sync_session() as s:
        pid = _du_an(s)
        s.commit()
        assert nap_boi_canh_du_an(s, pid) == ""


def test_KHONG_lay_thuat_ngu_cua_du_an_KHAC():
    """Rò thuật ngữ giữa hai bộ truyện là làm bản dịch sai theo cách rất khó lần ra."""
    with sync_session() as s:
        a, b = _du_an(s), _du_an(s)
        s.add(_tn(a, "風竜", "Rồng Gió", GlossaryStatus.approved))
        s.commit()
        assert "Rồng Gió" in nap_boi_canh_du_an(s, a)
        assert nap_boi_canh_du_an(s, b) == ""
