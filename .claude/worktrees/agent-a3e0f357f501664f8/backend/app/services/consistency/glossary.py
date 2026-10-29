"""Vòng đời thuật ngữ và hồ sơ giọng nhân vật (E13)."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CharacterVoiceProfile, GlossaryEntry, Project
from app.models.enums import GlossaryStatus, VoiceProfileStatus
from app.services.consistency.matching import chuan_hoa, khoa_thuat_ngu


class GlossaryInvalid(ValueError):
    """Dữ liệu thuật ngữ không hợp lệ — báo ngay, không lưu rồi mới phát hiện."""


#: Các trường mà sửa vào là làm ĐỔI NGHĨA của luật đã duyệt.
TRUONG_LAM_DOI_NGHIA = ("source_term", "target_term", "definition", "term_type")


class GlossaryService:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ---------------- tạo / sửa ----------------
    def create_entry(self, project_id: uuid.UUID, payload: dict) -> GlossaryEntry:
        du_an = self.session.get(Project, project_id)
        if du_an is None:
            raise GlossaryInvalid(f"project_not_found: {project_id}")

        for truong in ("source_term", "target_term", "definition"):
            if not (payload.get(truong) or "").strip():
                raise GlossaryInvalid(
                    f"{truong}_required: thiếu {truong}. Một cặp chữ trần trụi không đủ để giữ "
                    "bản dịch nhất quán — người duyệt sau cần biết thuật ngữ này nghĩa là gì."
                )

        # Thuật ngữ phải cùng ngôn ngữ nguồn với project; khác đi thì không bao giờ khớp được.
        lang = du_an.source_lang
        khoa = khoa_thuat_ngu(payload["source_term"], lang.value)
        trung = self.session.execute(
            select(GlossaryEntry).where(
                GlossaryEntry.project_id == project_id,
                GlossaryEntry.source_lang == lang,
                GlossaryEntry.source_term_key == khoa,
            )
        ).scalars().first()
        if trung is not None:
            raise GlossaryInvalid(
                f"duplicate_term: '{payload['source_term']}' đã có trong chapter này "
                f"(đang dịch là '{trung.target_term}', trạng thái {trung.status.value})"
            )

        entry = GlossaryEntry(
            project_id=project_id,
            source_lang=lang,
            target_lang=du_an.target_lang,
            source_term=chuan_hoa(payload["source_term"]).strip(),
            source_term_key=khoa,
            target_term=chuan_hoa(payload["target_term"]).strip(),
            term_type=payload["term_type"],
            definition=chuan_hoa(payload["definition"]).strip(),
            usage_note=(chuan_hoa(payload.get("usage_note") or "").strip() or None),
            prohibited_variants=[
                chuan_hoa(v).strip() for v in (payload.get("prohibited_variants") or []) if str(v).strip()
            ],
            status=GlossaryStatus.draft,  # luôn bắt đầu ở nháp, không ai tự duyệt cho mình
        )
        self.session.add(entry)
        self.session.commit()
        self.session.refresh(entry)
        return entry

    def update_entry(self, entry_id: uuid.UUID, payload: dict) -> GlossaryEntry:
        """Sửa nội dung của một thuật ngữ ĐÃ DUYỆT sẽ đưa nó về `draft`.

        Không làm vậy thì một luật đang được cả chapter dùng có thể bị đổi nghĩa âm thầm, và
        mọi việc rà soát đã tạo từ luật cũ trở thành vô nghĩa mà không ai biết.
        """
        entry = self.session.get(GlossaryEntry, entry_id)
        if entry is None:
            raise GlossaryInvalid(f"entry_not_found: {entry_id}")
        if entry.status is GlossaryStatus.archived:
            raise GlossaryInvalid("entry_archived: thuật ngữ đã lưu trữ, mở lại trước khi sửa")

        doi_nghia = False
        for truong in TRUONG_LAM_DOI_NGHIA:
            if truong in payload and payload[truong] is not None:
                gia_tri = payload[truong]
                if truong != "term_type":
                    gia_tri = chuan_hoa(str(gia_tri)).strip()
                    if not gia_tri:
                        raise GlossaryInvalid(f"{truong}_required: không được để trống")
                if getattr(entry, truong) != gia_tri:
                    setattr(entry, truong, gia_tri)
                    doi_nghia = True
                if truong == "source_term":
                    entry.source_term_key = khoa_thuat_ngu(gia_tri, entry.source_lang.value)

        if "usage_note" in payload:
            entry.usage_note = (chuan_hoa(payload["usage_note"] or "").strip() or None)
        if "prohibited_variants" in payload and payload["prohibited_variants"] is not None:
            entry.prohibited_variants = [
                chuan_hoa(v).strip() for v in payload["prohibited_variants"] if str(v).strip()
            ]

        if doi_nghia and entry.status is GlossaryStatus.approved:
            entry.status = GlossaryStatus.draft
        self.session.commit()
        self.session.refresh(entry)
        return entry

    # ---------------- vòng đời ----------------
    def approve_entry(self, entry_id: uuid.UUID) -> GlossaryEntry:
        entry = self.session.get(GlossaryEntry, entry_id)
        if entry is None:
            raise GlossaryInvalid(f"entry_not_found: {entry_id}")
        for truong in ("source_term", "target_term", "definition"):
            if not (getattr(entry, truong) or "").strip():
                raise GlossaryInvalid(f"{truong}_required: chưa đủ thông tin để duyệt")
        entry.status = GlossaryStatus.approved
        self.session.commit()
        self.session.refresh(entry)
        return entry

    def archive_entry(self, entry_id: uuid.UUID) -> GlossaryEntry:
        """Lưu trữ **không xoá** — các việc rà soát đã tạo từ thuật ngữ này vẫn còn để đối chiếu."""
        entry = self.session.get(GlossaryEntry, entry_id)
        if entry is None:
            raise GlossaryInvalid(f"entry_not_found: {entry_id}")
        entry.status = GlossaryStatus.archived
        self.session.commit()
        self.session.refresh(entry)
        return entry

    def list_approved(self, project_id: uuid.UUID) -> list[GlossaryEntry]:
        """CHỈ thuật ngữ đã duyệt mới được đem đi quét — nháp/từ chối không được tính."""
        return list(
            self.session.execute(
                select(GlossaryEntry).where(
                    GlossaryEntry.project_id == project_id,
                    GlossaryEntry.status == GlossaryStatus.approved,
                ).order_by(GlossaryEntry.source_term)
            ).scalars()
        )


class VoiceProfileService:
    """Hồ sơ giọng nhân vật — do NGƯỜI đặt. Máy không suy ra tính cách nhân vật ở E13."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, project_id: uuid.UUID, payload: dict) -> CharacterVoiceProfile:
        if self.session.get(Project, project_id) is None:
            raise GlossaryInvalid(f"project_not_found: {project_id}")
        ten = chuan_hoa(payload.get("character_name") or "").strip()
        if not ten:
            raise GlossaryInvalid("character_name_required: thiếu tên nhân vật")
        khoa = khoa_thuat_ngu(ten, "en")
        if self.session.execute(
            select(CharacterVoiceProfile).where(
                CharacterVoiceProfile.project_id == project_id,
                CharacterVoiceProfile.character_name_key == khoa,
            )
        ).scalars().first() is not None:
            raise GlossaryInvalid(f"duplicate_character: '{ten}' đã có hồ sơ trong chapter này")

        hs = CharacterVoiceProfile(
            project_id=project_id,
            character_name=ten,
            character_name_key=khoa,
            aliases=[chuan_hoa(a).strip() for a in (payload.get("aliases") or []) if str(a).strip()],
            speech_register=payload.get("speech_register") or "neutral",
            vietnamese_pronoun_guidance=(
                chuan_hoa(payload.get("vietnamese_pronoun_guidance") or "").strip() or None
            ),
            tone_note=(chuan_hoa(payload.get("tone_note") or "").strip() or None),
            status=VoiceProfileStatus.draft,
        )
        self.session.add(hs)
        self.session.commit()
        self.session.refresh(hs)
        return hs

    def update(self, profile_id: uuid.UUID, payload: dict) -> CharacterVoiceProfile:
        hs = self.session.get(CharacterVoiceProfile, profile_id)
        if hs is None:
            raise GlossaryInvalid(f"profile_not_found: {profile_id}")
        if "character_name" in payload and payload["character_name"]:
            ten = chuan_hoa(payload["character_name"]).strip()
            hs.character_name = ten
            hs.character_name_key = khoa_thuat_ngu(ten, "en")
        for truong in ("speech_register", "vietnamese_pronoun_guidance", "tone_note"):
            if truong in payload and payload[truong] is not None:
                gia_tri = payload[truong]
                if truong != "speech_register":
                    gia_tri = chuan_hoa(str(gia_tri)).strip() or None
                setattr(hs, truong, gia_tri)
        if "aliases" in payload and payload["aliases"] is not None:
            hs.aliases = [chuan_hoa(a).strip() for a in payload["aliases"] if str(a).strip()]
        self.session.commit()
        self.session.refresh(hs)
        return hs

    def set_status(self, profile_id: uuid.UUID, status: VoiceProfileStatus) -> CharacterVoiceProfile:
        hs = self.session.get(CharacterVoiceProfile, profile_id)
        if hs is None:
            raise GlossaryInvalid(f"profile_not_found: {profile_id}")
        hs.status = status
        self.session.commit()
        self.session.refresh(hs)
        return hs

    def list_active(self, project_id: uuid.UUID) -> list[CharacterVoiceProfile]:
        return list(
            self.session.execute(
                select(CharacterVoiceProfile).where(
                    CharacterVoiceProfile.project_id == project_id,
                    CharacterVoiceProfile.status == VoiceProfileStatus.active,
                ).order_by(CharacterVoiceProfile.character_name)
            ).scalars()
        )
