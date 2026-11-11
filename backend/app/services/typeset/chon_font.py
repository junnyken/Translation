"""E108 — Lưu & đọc tuỳ chọn Font thể loại (`font_style`) và Từ điển xưng hô nhanh (`tu_dien_rieng`)
cho từng Project thông qua `get_storage()`.

Vì sao lưu qua `get_storage()` (`projects/{project_id}/tuy_chon_dich.json`):
- Chia sẻ xuyên suốt giữa API process và Celery Worker (hỗ trợ cả `local` lẫn `postgres` storage).
- Không đòi hỏi migration bảng `project` trên CSDL đang chạy, an toàn tuyệt đối khi nâng cấp nóng.
- Khi không truyền `font_style` hoặc truyền mặc định (`bangers`), trả về `None` để giữ nguyên
  `settings.default_font_family` (`"Bangers"`), bảo toàn 100% các bài unit test hiện có.
"""
from __future__ import annotations

import json
import logging
import uuid

from app.services.typeset.registry import FONT_REGISTRY

logger = logging.getLogger(__name__)

#: Ánh xạ mã font thể loại từ giao diện Web / Tiện ích / App Windows sang tên family trong FONT_REGISTRY.
MAP_FONT_THE_LOAI: dict[str, str] = {
    "bangers": "Bangers",          # ⚔️ Hành động (Đậm)
    "romance": "ShantellSans",     # 🌸 Ngôn tình (Mềm)
    "historical": "Mansalva",      # 🏮 Cổ trang (Bút)
    "comic": "SigmarOne",          # 💥 Hài hước (Tròn)
}


def chuan_hoa_font_family(font_style: str | None) -> str | None:
    """Chuyển `font_style` ('bangers'|'romance'|'historical'|'comic' hoặc tên trong FONT_REGISTRY)
    thành tên family hợp lệ trong `FONT_REGISTRY`. Trả `None` nếu rỗng hoặc không hợp lệ."""
    if not font_style:
        return None
    s = font_style.strip()
    if s in FONT_REGISTRY:
        return s
    mapped = MAP_FONT_THE_LOAI.get(s.lower())
    if mapped and mapped in FONT_REGISTRY:
        return mapped
    return None


def _duong_dan_tuy_chon(project_id: uuid.UUID | str) -> str:
    return f"projects/{project_id}/tuy_chon_dich.json"


def doc_tuy_chon_du_an(project_id: uuid.UUID | str) -> dict:
    """Đọc dict tuỳ chọn (`font_family`, `tu_dien_rieng`) của project từ kho."""
    try:
        from app.services.storage import get_storage

        storage = get_storage()
        rel = _duong_dan_tuy_chon(project_id)
        if not storage.exists(rel):
            return {}
        raw = storage.read(rel)
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def luu_tuy_chon_du_an(
    project_id: uuid.UUID | str,
    *,
    font_style: str | None = None,
    tu_dien_rieng: str | None = None,
    byok_cipher: str | None = None,
    xoa_tu_dien_neu_rong: bool = False,
    xoa_byok: bool = False,
    strict: bool = False,
) -> None:
    """Cập nhật `font_family`, `tu_dien_rieng` hoặc `byok_cipher` (đã mã hoá TTL) vào `projects/{project_id}/tuy_chon_dich.json`."""
    family = chuan_hoa_font_family(font_style)
    tu_dien = (tu_dien_rieng or "").strip()
    byok_tok = (byok_cipher or "").strip()
    if not family and not tu_dien and not byok_tok and not xoa_tu_dien_neu_rong and not xoa_byok:
        return
    try:
        from app.services.storage import get_storage

        storage = get_storage()
        rel = _duong_dan_tuy_chon(project_id)
        hien_tai = doc_tuy_chon_du_an(project_id)
        if family:
            hien_tai["font_family"] = family
        if tu_dien:
            hien_tai["tu_dien_rieng"] = tu_dien[:4000]
        elif xoa_tu_dien_neu_rong and "tu_dien_rieng" in hien_tai:
            hien_tai.pop("tu_dien_rieng", None)
        if byok_tok:
            hien_tai["byok_cipher"] = byok_tok[:2048]
        elif xoa_byok and "byok_cipher" in hien_tai:
            hien_tai.pop("byok_cipher", None)
        storage.save(rel, json.dumps(hien_tai, ensure_ascii=False).encode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Không lưu được tuỳ chọn dịch cho project %s: %s", project_id, exc)
        if strict:
            raise


def doc_font_du_an(project_id: uuid.UUID | str | None) -> str | None:
    """Trả `font_family` hợp lệ trong `FONT_REGISTRY` nếu project có đặt riêng, ngược lại `None`."""
    if not project_id:
        return None
    tc = doc_tuy_chon_du_an(project_id)
    fam = tc.get("font_family")
    if isinstance(fam, str) and fam in FONT_REGISTRY:
        return fam
    return None


def doc_tu_dien_du_an(project_id: uuid.UUID | str | None) -> str:
    """Trả chuỗi ghi chú từ điển / xưng hô nhân vật của project (rỗng nếu không có)."""
    if not project_id:
        return ""
    tc = doc_tuy_chon_du_an(project_id)
    td = tc.get("tu_dien_rieng")
    return td.strip() if isinstance(td, str) else ""


def doc_byok_cipher_du_an(project_id: uuid.UUID | str | None) -> str:
    """Trả chuỗi `byok_cipher` đã mã hoá tạm thời của project (rỗng nếu không dùng BYOK)."""
    if not project_id:
        return ""
    tc = doc_tuy_chon_du_an(project_id)
    bc = tc.get("byok_cipher")
    return bc.strip() if isinstance(bc, str) else ""
