"""Set-of-Mark (SoM) Hybrid Vision cho Model 3 (`llm_context`) — Kết hợp độ chính xác từng pixel của
`comic-text-detector` (CTD) với khả năng hiểu toàn cảnh tranh & biểu cảm nhân vật của Multimodal Vision LLM.

## Bài toán giải quyết
- Nếu chỉ dùng Vision LLM thuần (`detect_va_dich_regions` trên ảnh trần): AI hiểu biểu cảm và ngữ cảnh cực tốt,
  nhưng toạ độ `[ymin, xmin, ymax, xmax]` do LLM tự ước lượng thường bị trôi/lệch 15–40px trên trang nhiều chữ,
  và KHÔNG có mặt nạ nét chữ `mat_na_chu` (`seg` mask) cho bước xoá chữ `LaMa`.
- Nếu chỉ dùng OCR cục bộ thuần (Model 1 / Model 2): toạ độ và mặt nạ nét chữ chuẩn từng pixel, nhưng LLM dịch chỉ
  nhận được các dòng văn bản mù, không nhìn thấy ai đang khóc/cười/hét hay mối quan hệ nhân vật trong tranh.

## Kiến trúc Set-of-Mark (`[#1..#N]`) Hybrid Vision (Model 3)
1. Chạy `CTDDetector` cục bộ trước để khoá khung chữ chuẩn từng pixel + giữ lại `mat_na_chu` (`seg` mask) cho `LaMa`.
2. Sắp xếp các khung theo chiều đọc truyện tranh (`RTL` cho Manga Nhật / Phồn thể, `LTR` cho Manhwa / Manhua / Comic)
   và vẽ khung mảnh kèm thẻ đánh số tương phản cao `#1`, `#2`, ..., `#N` ở mép ngoài góc khung trên bản sao ảnh
   (tuyệt đối không đè lên nét chữ gốc bên trong khung).
3. Gửi bản sao Set-of-Mark lên Vision LLM (`Gemini` / `GPT-4o` / `Claude` / `OpenRouter Vision`):
   - Với các khung đã đánh dấu `#1..#N`: AI đọc chữ gốc, nhìn biểu cảm nhân vật trong khung tranh và trả về
     `{"id": i, "text": "...", "ban_dich": "...", "doan": false}` -> ghép thẳng vào toạ độ pixel của CTD (sai số 0px!).
   - Với lời thì thầm / chữ viết tay siêu nhỏ lọt lưới CTD (nếu có): AI tự bổ sung với `"id": 0` kèm `"box": [y0, x0, y1, x1]`.
"""
from __future__ import annotations

import io
import logging
import re
from typing import Sequence

from PIL import Image, ImageDraw, ImageFont

from app.services.detect.ctd import DetectedRegion
from app.services.interfaces import BBox

logger = logging.getLogger(__name__)

THANG_SOM = 1000
_CHI_LA_SO_SOM = re.compile(r"^\d{1,3}$")

#: Schema JSON ép đầu ra chuẩn cho lượt gọi Set-of-Mark Vision 1-Pass
SCHEMA_SOM_GOP_DICH: dict = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "id": {
                "type": "INTEGER",
                "description": "Tag number 1..N matching [#1]..[#N] on image, or 0 for newly discovered unmarked dialogue.",
            },
            "box": {
                "type": "ARRAY",
                "items": {"type": "INTEGER"},
                "description": "[ymin, xmin, ymax, xmax] scaled 0..1000 (required when id=0, optional when id>=1).",
            },
            "text": {"type": "STRING"},
            "ban_dich": {"type": "STRING"},
            "doan": {"type": "BOOLEAN"},
        },
        "required": ["id", "text", "ban_dich", "doan"],
    },
}


def sap_xep_khung_som(regions: Sequence[DetectedRegion], source_lang: str = "ja") -> list[DetectedRegion]:
    """Sắp xếp khung chữ theo dải ngang từ trên xuống dưới, trong cùng dải xếp RTL (Manga) hoặc LTR (Manhwa/Comic)."""
    if not regions:
        return []
    rtl = (source_lang or "ja").strip().lower() in ("ja", "zh-tw")
    ds = list(regions)
    # Sắp xếp sơ bộ theo tâm y
    ds.sort(key=lambda r: r.bbox.y + r.bbox.h * 0.5)

    dai_ngang: list[list[DetectedRegion]] = []
    for r in ds:
        cy = r.bbox.y + r.bbox.h * 0.5
        da_ghe = False
        for nhom in dai_ngang:
            y_tb = sum(x.bbox.y + x.bbox.h * 0.5 for x in nhom) / len(nhom)
            h_tb = sum(x.bbox.h for x in nhom) / len(nhom)
            if abs(cy - y_tb) <= max(28.0, h_tb * 0.55):
                nhom.append(r)
                da_ghe = True
                break
        if not da_ghe:
            dai_ngang.append([r])

    ket_qua: list[DetectedRegion] = []
    for nhom in dai_ngang:
        if rtl:
            nhom.sort(key=lambda r: -(r.bbox.x + r.bbox.w * 0.5))
        else:
            nhom.sort(key=lambda r: (r.bbox.x + r.bbox.w * 0.5))
        ket_qua.extend(nhom)
    return ket_qua


def ve_anh_set_of_mark(
    image_bytes: bytes,
    regions: Sequence[DetectedRegion],
    *,
    max_side: int = 1280,
) -> tuple[bytes, str]:
    """Vẽ viền neo mảnh và thẻ số `[#1]..[#N]` ở mép ngoài khung chữ trên BẢN SAO của trang truyện.
    Đặt thẻ số bên ngoài lòng khung để KHÔNG che khuất bất kỳ nét chữ gốc nào.
    """
    with Image.open(io.BytesIO(image_bytes)) as im_goc:
        rgb = im_goc.convert("RGB")
        w0, h0 = rgb.size
        scale = min(1.0, float(max_side) / float(max(1, w0, h0)))
        if scale < 0.999:
            w_m = max(1, int(round(w0 * scale)))
            h_m = max(1, int(round(h0 * scale)))
            canvas = rgb.resize((w_m, h_m), Image.Resampling.LANCZOS)
        else:
            w_m, h_m = w0, h0
            canvas = rgb.copy()

    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.load_default()
    except Exception:  # noqa: BLE001
        font = None

    for idx, reg in enumerate(regions, start=1):
        # Nới ra ngoài 2px để đường viền định vị không chạm vào nét mực chữ bên trong
        x1 = max(0, int(round(reg.bbox.x * scale)) - 2)
        y1 = max(0, int(round(reg.bbox.y * scale)) - 2)
        x2 = min(w_m - 1, int(round((reg.bbox.x + reg.bbox.w) * scale)) + 2)
        y2 = min(h_m - 1, int(round((reg.bbox.y + reg.bbox.h) * scale)) + 2)
        if x2 <= x1 or y2 <= y1:
            continue

        # Viền neo màu hồng tím đậm nổi bật trên cả truyện đen trắng lẫn truyện màu
        draw.rectangle([x1, y1, x2, y2], outline=(219, 39, 119), width=2)

        nhan = f"#{idx}"
        if hasattr(draw, "textbbox"):
            tb = draw.textbbox((0, 0), nhan, font=font)
            tw = max(14, int(tb[2] - tb[0]) + 6)
            th = max(13, int(tb[3] - tb[1]) + 4)
        else:
            tw = 8 * len(nhan) + 6
            th = 14

        # Ưu tiên đặt thẻ số ở ngay PHÍA TRÊN mép khung để không che chữ bên trong; nếu chạm mép đỉnh ảnh thì đặt xuống dưới hoặc sang trái
        bx1 = min(max(0, x1), max(0, w_m - tw))
        if y1 - th - 1 >= 0:
            by1 = y1 - th - 1
        elif y2 + th + 1 <= h_m:
            by1 = y2 + 1
        else:
            by1 = max(0, y1)
            bx1 = max(0, x1 - tw - 1) if x1 - tw - 1 >= 0 else min(max(0, w_m - tw), x2 + 1)

        draw.rectangle([bx1, by1, bx1 + tw, by1 + th], fill=(250, 204, 21), outline=(15, 23, 42), width=1)
        draw.text((bx1 + 3, by1 + 1), nhan, fill=(15, 23, 42), font=font)

    out = io.BytesIO()
    canvas.save(out, format="JPEG", quality=88, optimize=True)
    return out.getvalue(), "image/jpeg"


_TEN_NGUON_SOM = {
    "ja": "Japanese (Manga)",
    "ko": "Korean (Manhwa/Webtoon)",
    "zh": "Chinese (Manhua)",
    "zh-tw": "Traditional Chinese (Manga/Manhua)",
    "en": "English (Comic)",
}

_TEN_DICH_SOM = {
    "vi": "natural idiomatic Vietnamese (chuẩn thoại truyện tranh tự nhiên, đúng xưng hô)",
    "en": "natural idiomatic Comic/Manga English",
    "es": "natural expressive Spanish (Español neutro/latino para Manga/Manhwa)",
    "pt": "natural Brazilian Portuguese (Português brasileiro para Manga/Webtoon)",
    "fr": "natural French (Français fluide pour Manga/Webtoon)",
    "id": "natural Bahasa Indonesia (Bahasa Indonesia luwes untuk Komik/Manhwa)",
    "th": "natural Thai (ภาษาไทยธรรมชาติสำหรับการ์ตูน/มังงะ)",
    "zh": "natural Simplified Chinese (自然流畅的简体中文漫画对白)",
    "zh-tw": "natural Traditional Chinese (自然流暢的繁體中文漫畫對白)",
}


def xay_loi_nhac_som_gop_dich(
    so_khung: int,
    source_lang: str,
    target_lang: str = "vi",
    boi_canh: str | None = None,
) -> str:
    """Tạo prompt Set-of-Mark yêu cầu Vision LLM nhìn toàn bộ biểu cảm tranh và dịch chuẩn từng thẻ `#1..#N`."""
    sl = (source_lang or "ja").strip().lower()
    tl = (target_lang or "vi").strip().lower()
    ten_nguon = _TEN_NGUON_SOM.get(sl, f"source ({source_lang})")
    ten_dich = _TEN_DICH_SOM.get(tl, "natural idiomatic Vietnamese")
    khung_boi_canh = ""
    if boi_canh and boi_canh.strip():
        khung_boi_canh = (
            "\nEstablished story glossary, character relationships & previous page context:\n"
            f"{boi_canh.strip()}\n"
        )

    return (
        f"You are an elite multimodal Manga/Manhwa/Comic scanlation director translating from {ten_nguon} into {ten_dich}.\n"
        f"This comic page has {so_khung} pre-detected text regions marked with yellow-black tags `#1` through `#{so_khung}` "
        "and thin magenta borders.\n"
        "Tasks:\n"
        f"1. For EVERY marked region `#1` .. `#{so_khung}` that contains dialogue, narration, caption, note, sign, or meaningful text:\n"
        "   - Read the exact original text inside that magenta box (`text`).\n"
        "   - Apply context-specific scanlation tone across all 6 comic text types:\n"
        "     * Speech & spiky shout bubbles: natural conversational flow, accurate pronouns matching age/gender/status/emotion in the art.\n"
        "     * Internal monologue / floating haloed thoughts over background or hair: reflective, concise inner-voice phrasing.\n"
        "     * Rectangular narration / time-location captions: literary, atmospheric storytelling tone.\n"
        "     * Margin translator/editor notes (`*TN:`, `Note:`, `*`): clear, compact explanatory note (`Chú thích: ...` for Vietnamese).\n"
        "     * In-world signs / screens / labels / documents: crisp, authentic signage/UI wording.\n"
        "     * Sound effects (SFX) & publisher/scanner credit blocks: omit decorative raw strokes AND omit publisher/creator credit boxes "
        "(e.g., `STORY ... PENCILS ... INKS ... LETTERS`) or scanlation watermarks by leaving `ban_dich` empty.\n"
        "   - Output `id` equal to the tag number (`1` .. `N`). Do NOT drop valid story text tags.\n"
        "2. Safety check for unmarked text: ONLY IF you clearly see an important dialogue/whisper/narration/note line on the page "
        "that has NO `#id` tag at all, include an extra entry with `\"id\": 0` and its tight `[ymin, xmin, ymax, xmax]` (0..1000) in `box`.\n"
        "3. Set `doan: true` only when source characters are partially illegible and inferred from context; otherwise `doan: false`.\n"
        f"{khung_boi_canh}"
    )


def _iou_hop(a: BBox, b: BBox) -> float:
    ix1 = max(a.x, b.x)
    iy1 = max(a.y, b.y)
    ix2 = min(a.x + a.w, b.x + b.w)
    iy2 = min(a.y + a.h, b.y + b.h)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0.0:
        return 0.0
    union = a.w * a.h + b.w * b.h - inter
    return inter / union if union > 0.0 else 0.0


def ghep_ket_qua_som_vao_khung_ctd(
    ctd_regions_ordered: Sequence[DetectedRegion],
    som_items: Sequence[dict],
    img_w: int,
    img_h: int,
) -> list[DetectedRegion]:
    """Ánh xạ bản dịch của Vision LLM vào đúng khung pixel `CTDDetector` theo `id` (1..N) với độ lệch 0px,
    đồng thời bổ sung các vùng chữ sót (`id == 0`) không trùng lặp.
    """
    n = len(ctd_regions_ordered)
    da_ghep_theo_id: dict[int, DetectedRegion] = {}
    bo_sung_id0: list[DetectedRegion] = []

    for muc in som_items:
        if not isinstance(muc, dict):
            continue
        try:
            idx = int(muc.get("id") or 0)
        except (TypeError, ValueError):
            idx = 0
        chu = muc.get("text")
        chu = " ".join(chu.split()) if isinstance(chu, str) else ""
        if chu and _CHI_LA_SO_SOM.match(chu):
            continue
        ban_dich = muc.get("ban_dich")
        ban_dich = " ".join(ban_dich.split()) if isinstance(ban_dich, str) else ""
        if not chu and not ban_dich:
            continue
        co_doan = bool(muc.get("doan"))

        if 1 <= idx <= n:
            goc_reg = ctd_regions_ordered[idx - 1]
            # Nếu LLM vô tình trả 2 dòng cùng 1 id, gộp câu mượt mà không mất chữ
            if idx in da_ghep_theo_id:
                cu = da_ghep_theo_id[idx]
                chu_moi = " ".join(filter(None, [cu.chu, chu])).strip()
                dich_moi = " ".join(filter(None, [cu.ban_dich, ban_dich])).strip()
                da_ghep_theo_id[idx] = DetectedRegion(
                    bbox=goc_reg.bbox,
                    confidence=goc_reg.confidence,
                    cls=goc_reg.cls,
                    chu=chu_moi or None,
                    ban_dich=dich_moi or None,
                    doan=cu.doan or co_doan,
                )
            else:
                da_ghep_theo_id[idx] = DetectedRegion(
                    bbox=goc_reg.bbox,
                    confidence=goc_reg.confidence,
                    cls=goc_reg.cls,
                    chu=chu or ban_dich or None,
                    ban_dich=ban_dich or chu or None,
                    doan=co_doan,
                )
        elif idx == 0:
            hop = muc.get("box") or muc.get("box_2d")
            if not (isinstance(hop, list) and len(hop) == 4):
                continue
            try:
                y0, x0, y1, x1 = (float(v) for v in hop)
            except (TypeError, ValueError):
                continue
            px0 = max(0.0, min(float(img_w), x0 / THANG_SOM * img_w))
            px1 = max(0.0, min(float(img_w), x1 / THANG_SOM * img_w))
            py0 = max(0.0, min(float(img_h), y0 / THANG_SOM * img_h))
            py1 = max(0.0, min(float(img_h), y1 / THANG_SOM * img_h))
            if px1 - px0 < 10.0 or py1 - py0 < 10.0:
                continue
            bbox_moi = BBox(
                x=round(px0, 2),
                y=round(py0, 2),
                w=round(px1 - px0, 2),
                h=round(py1 - py0, 2),
            )
            # Chỉ nhận khung bổ sung nếu nó thực sự chưa được CTD khoanh (IoU < 0.22)
            if any(_iou_hop(bbox_moi, r.bbox) >= 0.22 for r in ctd_regions_ordered):
                continue
            bo_sung_id0.append(
                DetectedRegion(
                    bbox=bbox_moi,
                    confidence=None,
                    cls=0,
                    chu=chu or ban_dich or None,
                    ban_dich=ban_dich or chu or None,
                    doan=co_doan,
                )
            )

    ra: list[DetectedRegion] = []
    for idx in range(1, n + 1):
        if idx in da_ghep_theo_id:
            ra.append(da_ghep_theo_id[idx])
    ra.extend(bo_sung_id0)
    return ra
