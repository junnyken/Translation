"""E26-C — giữ nguyên chữ cho vùng có thể là TIẾNG ĐỘNG (SFX), không dịch thành từ.

## Vì sao

Đo thật trên trang `en_E12P01` (2026-09-11), bộ dịch cho:

    Clang  -> 'Kêu vang'      Cling -> 'Bám vào'      Clong -> 'tiếng kêu'

`Cling` thành "Bám vào" là dịch **đúng từ điển nhưng sai thể loại**: đó là tiếng kim loại chạm
nhau, không phải động từ "bám". Tiếng động trong truyện tranh Việt thường giữ nguyên hoặc phiên âm,
không dịch nghĩa.

## Vì sao CHỈ dựa vào cờ `possible_sfx` của E12, không tự suy thêm

E12 đã có `RegionRelevance.possible_sfx`. Đo trên dữ liệu thật, nó bắt được **3/6**:

| Chữ | E12 gắn |
|---|---|
| `Clang` · `Cling` · `Clong` | `possible_sfx` ✓ |
| `Shhshh` · `Shklak!` · `CRACK!!\\nKLING!!` | `likely_translatable` ✗ |

Tức nó bỏ sót một nửa. **Nhưng tôi cố ý không thêm luật tự suy** (chữ ngắn / nghiêng / ngoài bong
bóng): một dương tính giả ở đây để **thoại thật không được dịch** — người đọc mất hẳn một câu. Đổi
lại, một SFX bị dịch sai chỉ là một từ lạ mà người đọc vẫn hiểu là tiếng động.

Sai một chiều mất cả câu, sai chiều kia chỉ lạ một từ ⇒ chọn chiều chỉ-lạ-một-từ.

Nên cơ chế này **cải thiện 3/6 ca và không phá ca nào** — không bao giờ tệ hơn hiện trạng. Muốn
bắt nốt 3 ca kia thì phải làm cho `possible_sfx` của E12 nhạy hơn, và đó là việc có bằng chứng
riêng của nó, không nhét vào đây.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RegionQualityAssessment
from app.models.enums import RegionRelevance

#: Từ điển Tiếng động / Chữ tượng thanh (SFX) đa ngôn ngữ chuẩn Manga / Manhwa / Manhua.
#: Ánh xạ trực tiếp các âm thanh phổ biến (Nhật / Hàn / Trung / Anh) sang từ tượng thanh
#: tự nhiên của từng ngôn ngữ đích mà không tốn token gọi LLM và không bị dịch nhầm thành tên người.
TU_DIEN_SFX_DA_NGON_NGU: dict[str, dict[str, str]] = {
    # Tiếng tim đập / hồi hộp
    "ドキドキ": {"vi": "Thình thịch", "en": "Ba-dump", "es": "Bum-bum", "pt": "Tum-tum", "fr": "Boum-boum", "id": "Deg-degan"},
    "ドキッ": {"vi": "Thịch!", "en": "Thump!", "es": "¡Pum!", "pt": "Tum!", "fr": "Boum !", "id": "Deg!"},
    "두근": {"vi": "Thình thịch", "en": "Thump", "es": "Bum-bum", "pt": "Tum-tum", "fr": "Boum", "id": "Deg"},
    "두근두근": {"vi": "Thình thịch", "en": "Ba-dump", "es": "Bum-bum", "pt": "Tum-tum", "fr": "Boum-boum", "id": "Deg-degan"},
    # Tiếng nổ / va chạm mạnh
    "ドーン": {"vi": "BÙM!", "en": "BOOM!", "es": "¡BUM!", "pt": "CABUM!", "fr": "BOUM !", "id": "DUAR!"},
    "ドゴォン": {"vi": "ẦM!!", "en": "KABOOM!!", "es": "¡¡BOOOOM!!", "pt": "CABUUM!!", "fr": "KABOUM !!", "id": "BLAAAR!!"},
    "ドカン": {"vi": "ĐÙNG!", "en": "BANG!", "es": "¡PUM!", "pt": "POW!", "fr": "PAN !", "id": "DOR!"},
    "バン": {"vi": "ĐOÀNG!", "en": "BANG!", "es": "¡PAM!", "pt": "BANG!", "fr": "PAN !", "id": "DOR!"},
    "쾅": {"vi": "RẦM!", "en": "SLAM!", "es": "¡PLAF!", "pt": "BLAM!", "fr": "VLAM !", "id": "BRAK!"},
    "콰앙": {"vi": "ẦM!!", "en": "BOOM!!", "es": "¡¡BUM!!", "pt": "CABUM!!", "fr": "BOUM !!", "id": "DUAR!!"},
    "쿠구구궁": {"vi": "Ầm ầm ầm...", "en": "Rumble...", "es": "Retumbar...", "pt": "Rumble...", "fr": "Gronde...", "id": "Gemuruh..."},
    "轰": {"vi": "ẦM!", "en": "BOOM!", "es": "¡BUM!", "pt": "CABUM!", "fr": "BOUM !", "id": "DUAR!"},
    "轰隆": {"vi": "ẦM ẦM!", "en": "RUMBLE!", "es": "¡RETUMBAR!", "pt": "ESTRondo!", "fr": "GRONDE !", "id": "GEMURUH!"},
    "砰": {"vi": "ĐOÀNG!", "en": "BANG!", "es": "¡PUM!", "pt": "POW!", "fr": "PAN !", "id": "DOR!"},
    # Tiếng kim loại / vật rơi / chuông
    "カラン": {"vi": "Keng", "en": "Clang", "es": "Clink", "pt": "Plim", "fr": "Dring", "id": "Kling"},
    "コロン": {"vi": "Lộc cộc", "en": "Clatter", "es": "Clac", "pt": "Clac", "fr": "Clac", "id": "Klotak"},
    "キーン": {"vi": "Keng!", "en": "Shing!", "es": "¡Cling!", "pt": "Plim!", "fr": "Dring !", "id": "Tring!"},
    "챙": {"vi": "Xoảng!", "en": "Clash!", "es": "¡Clang!", "pt": "Clang!", "fr": "Clang !", "id": "Tring!"},
    # Tiếng nuốt nước bọt / uống nước
    "ゴクッ": {"vi": "Ực!", "en": "Gulp!", "es": "¡Glup!", "pt": "Glup!", "fr": "Gloups !", "id": "Glek!"},
    "ごくごく": {"vi": "Ực ực", "en": "Gulp gulp", "es": "Glup glup", "pt": "Glup glup", "fr": "Glou glou", "id": "Glek glek"},
    "꿀꺽": {"vi": "Ực!", "en": "Gulp!", "es": "¡Glup!", "pt": "Glup!", "fr": "Gloups !", "id": "Glek!"},
    # Tiếng uy áp / im lặng / bàn tán
    "ゴゴゴ": {"vi": "Rầm rầm...", "en": "Menacing...", "es": "Amenazante...", "pt": "Ameaçador...", "fr": "Menaçant...", "id": "Mencekam..."},
    "ゴゴゴゴ": {"vi": "Rầm rầm...", "en": "Menacing...", "es": "Amenazante...", "pt": "Ameaçador...", "fr": "Menaçant...", "id": "Mencekam..."},
    "ザワザワ": {"vi": "Xì xào...", "en": "Murmur...", "es": "Murmullo...", "pt": "Murmúrio...", "fr": "Chuchote...", "id": "Bisik-bisik..."},
    "シーン": {"vi": "Im phắc...", "en": "Silence...", "es": "Silencio...", "pt": "Silêncio...", "fr": "Silence...", "id": "Hening..."},
    # Tiếng cười / cảm xúc / lấp lánh
    "キラキラ": {"vi": "Lấp lánh✨", "en": "Sparkle✨", "es": "Brillo✨", "pt": "Brilho✨", "fr": "Scintille✨", "id": "Berkilau✨"},
    "ニコッ": {"vi": "Tươi cười", "en": "Smile", "es": "Sonrisa", "pt": "Sorriso", "fr": "Sourire", "id": "Senyum"},
    "ハァハァ": {"vi": "Hộc... hộc...", "en": "Pant... pant...", "es": "Jadea...", "pt": "Arfa...", "fr": "Halète...", "id": "Hah... hah..."},
    "짝": {"vi": "Bốp!", "en": "Clap!", "es": "¡Plaf!", "pt": "Pá!", "fr": "Clac !", "id": "Plak!"},
    "啪": {"vi": "Bốp!", "en": "Slap!", "es": "¡Zas!", "pt": "Pá!", "fr": "Clac !", "id": "Plak!"},
}


def tra_cuu_sfx_nhanh(text: str, target_lang: str = "vi") -> str | None:
    """Tra cứu nhanh chữ tượng thanh (SFX) trong từ điển tĩnh đa ngôn ngữ.

    Trả về chuỗi SFX đã bản địa hoá nếu khớp chính xác (bỏ qua dấu chấm than/khoảng trắng),
    hoặc `None` nếu không phải SFX đã biết để nhường cho bộ dịch ngữ cảnh xử lý.
    """
    if not text:
        return None
    clean = text.strip().strip("!！?？.。…~～ ")
    if not clean:
        return None
    entry = TU_DIEN_SFX_DA_NGON_NGU.get(clean)
    if not entry:
        return None
    tl = (target_lang or "vi").strip().lower()
    return entry.get(tl) or entry.get("en") or entry.get("vi")


def nap_vung_giu_nguyen(session: Session, region_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    """Tập id vùng E12 đánh `possible_sfx` ⇒ giữ nguyên chữ gốc, không gửi đi dịch.

    Vùng chưa được E12 chấm thì **không** nằm trong tập này: thiếu bằng chứng nghĩa là dịch bình
    thường, chứ không phải đoán rồi giữ nguyên.
    """
    if not region_ids:
        return set()
    return set(
        session.scalars(
            select(RegionQualityAssessment.region_id).where(
                RegionQualityAssessment.region_id.in_(region_ids),
                RegionQualityAssessment.relevance == RegionRelevance.possible_sfx,
            )
        )
    )
