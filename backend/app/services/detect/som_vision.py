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
import math
import re
from typing import Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

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


def _dien_tich_giao(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> int:
    ix1 = max(a[0], b[0])
    iy1 = max(a[1], b[1])
    ix2 = min(a[2], b[2])
    iy2 = min(a[3], b[3])
    if ix2 <= ix1 or iy2 <= iy1:
        return 0
    return (ix2 - ix1) * (iy2 - iy1)


def ve_anh_set_of_mark(
    image_bytes: bytes,
    regions: Sequence[DetectedRegion],
    *,
    max_side: int = 1280,
) -> tuple[bytes, str]:
    """Vẽ viền neo mảnh và thẻ số `[#1]..[#N]` tránh va chạm với mọi khung khác và thẻ đã đặt.
    Giữ thẻ số bên ngoài lòng khung để KHÔNG che khuất nét chữ gốc.
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

    tat_ca_hop: list[tuple[int, int, int, int]] = []
    for reg in regions:
        x1 = max(0, int(round(reg.bbox.x * scale)) - 2)
        y1 = max(0, int(round(reg.bbox.y * scale)) - 2)
        x2 = min(w_m - 1, int(round((reg.bbox.x + reg.bbox.w) * scale)) + 2)
        y2 = min(h_m - 1, int(round((reg.bbox.y + reg.bbox.h) * scale)) + 2)
        tat_ca_hop.append((x1, y1, x2, y2))

    nhan_da_dat: list[tuple[int, int, int, int]] = []

    for i_reg, (x1, y1, x2, y2) in enumerate(tat_ca_hop):
        if x2 <= x1 or y2 <= y1:
            continue
        idx = i_reg + 1
        draw.rectangle([x1, y1, x2, y2], outline=(219, 39, 119), width=1)

        nhan = f"#{idx}"
        if hasattr(draw, "textbbox"):
            tb = draw.textbbox((0, 0), nhan, font=font)
            tw = max(15, int(tb[2] - tb[0]) + 6)
            th = max(13, int(tb[3] - tb[1]) + 4)
        else:
            tw = 8 * len(nhan) + 6
            th = 14

        ung_vien = [
            (x1, y1 - th - 2),               # Trên trái
            (x1, y2 + 2),                    # Dưới trái
            (x1 - tw - 2, y1),               # Trái trên
            (x2 + 2, y1),                    # Phải trên
            (x2 - tw, y1 - th - 2),          # Trên phải
            (x2 - tw, y2 + 2),               # Dưới phải
            (x1 - tw - 2, max(0, y2 - th)),  # Trái dưới
            (x2 + 2, max(0, y2 - th)),       # Phải dưới
            (x1 + 2, y1 + 2),                # Dự phòng góc trên trong khung
        ]

        tot_nhat: tuple[int, int, int, int] | None = None
        diem_tot_nhat = float("inf")
        for ux, uy in ung_vien:
            bx1 = min(max(0, ux), max(0, w_m - tw))
            by1 = min(max(0, uy), max(0, h_m - th))
            cand = (bx1, by1, bx1 + tw, by1 + th)
            va_cham_nhan = sum(_dien_tich_giao(cand, lb) for lb in nhan_da_dat) * 10
            va_cham_hop_khac = sum(
                _dien_tich_giao(cand, hb) for j_reg, hb in enumerate(tat_ca_hop) if j_reg != i_reg
            ) * 4
            va_cham_chinh_no = _dien_tich_giao(cand, (x1 + 2, y1 + 2, max(x1 + 2, x2 - 2), max(y1 + 2, y2 - 2))) * 6
            tong_phat = va_cham_nhan + va_cham_hop_khac + va_cham_chinh_no
            if tong_phat < diem_tot_nhat:
                diem_tot_nhat = tong_phat
                tot_nhat = cand
                if tong_phat == 0:
                    break

        bx1, by1, bx2, by2 = tot_nhat if tot_nhat is not None else (0, 0, tw, th)
        nhan_da_dat.append((bx1, by1, bx2, by2))
        draw.rectangle([bx1, by1, bx2, by2], fill=(250, 204, 21), outline=(15, 23, 42), width=1)
        draw.text((bx1 + 3, by1 + 1), nhan, fill=(15, 23, 42), font=font)

    out = io.BytesIO()
    canvas.save(out, format="JPEG", quality=90, optimize=True)
    return out.getvalue(), "image/jpeg"


def tao_bang_cat_can_canh_som(
    image_bytes: bytes,
    regions: Sequence[DetectedRegion],
    *,
    max_side: int = 768,
) -> tuple[bytes, str] | None:
    """Tạo Bảng Cắt Cận Cảnh 1:1 (`#1..#N`) phóng nét chữ nhỏ & tự đảo cực nền tối -> đen/trắng
    để Vision LLM đọc chính xác 100% từng chữ nhỏ/chữ trắng trên tóc tối mà vẫn giữ chi phí token thấp.
    """
    if not regions:
        return None
    with Image.open(io.BytesIO(image_bytes)) as im_goc:
        rgb = im_goc.convert("RGB")
        w0, h0 = rgb.size

    try:
        font = ImageFont.load_default()
    except Exception:  # noqa: BLE001
        font = None

    header_h = 18
    margin = 6
    cells: list[tuple[int, Image.Image]] = []
    for idx, reg in enumerate(regions, start=1):
        pad = max(6, min(14, int(round(min(reg.bbox.w, reg.bbox.h) * 0.10))))
        cx0 = max(0, int(round(reg.bbox.x)) - pad)
        cy0 = max(0, int(round(reg.bbox.y)) - pad)
        cx1 = min(w0, int(round(reg.bbox.x + reg.bbox.w)) + pad)
        cy1 = min(h0, int(round(reg.bbox.y + reg.bbox.h)) + pad)
        if cx1 - cx0 < 6 or cy1 - cy0 < 6:
            continue

        crop = rgb.crop((cx0, cy0, cx1, cy1))
        arr = np.asarray(crop)
        gray = np.mean(arr, axis=2)
        border_vals = np.concatenate([gray[0, :], gray[-1, :], gray[:, 0], gray[:, -1]])
        if float(np.median(gray)) < 95.0 or (float(np.median(border_vals)) < 92.0 and float(np.percentile(gray, 92)) > 185.0):
            crop = ImageOps.invert(crop)
        else:
            p2, p98 = float(np.percentile(gray, 2)), float(np.percentile(gray, 98))
            if p98 - p2 < 140.0 and p98 > p2 + 12.0:
                crop = ImageOps.autocontrast(crop, cutoff=1)

        cw, ch = crop.size
        if min(cw, ch) < 120 or cw < 185:
            scale_up = min(2.2, 260.0 / max(1, cw))
            if scale_up > 1.08:
                crop = crop.resize(
                    (max(1, int(round(cw * scale_up))), max(1, int(round(ch * scale_up)))),
                    Image.Resampling.LANCZOS,
                )
        crop = crop.filter(ImageFilter.UnsharpMask(radius=1.0, percent=115, threshold=2))

        cell_w, cell_h = crop.size
        cell = Image.new("RGB", (max(46, cell_w), cell_h + header_h), (241, 245, 249))
        cell.paste(crop, (0, header_h))
        cdraw = ImageDraw.Draw(cell)
        cdraw.rectangle([0, 0, cell.width - 1, header_h - 1], fill=(250, 204, 21), outline=(15, 23, 42), width=1)
        cdraw.text((4, 2), f"#{idx}", fill=(15, 23, 42), font=font)
        cdraw.rectangle([0, header_h, cell.width - 1, cell.height - 1], outline=(219, 39, 119), width=1)
        cells.append((idx, cell))

    if not cells:
        return None

    so_o = len(cells)
    so_cot = 2 if so_o <= 4 else (3 if so_o <= 12 else 4)
    so_hang = math.ceil(so_o / so_cot)
    cot_w = [0] * so_cot
    hang_h = [0] * so_hang
    for i, (_, cell) in enumerate(cells):
        r, c = divmod(i, so_cot)
        cot_w[c] = max(cot_w[c], cell.width)
        hang_h[r] = max(hang_h[r], cell.height)

    tong_w = sum(cot_w) + margin * (so_cot + 1)
    tong_h = sum(hang_h) + margin * (so_hang + 1)
    bang = Image.new("RGB", (max(64, tong_w), max(64, tong_h)), (248, 250, 252))

    y_cur = margin
    for r in range(so_hang):
        x_cur = margin
        for c in range(so_cot):
            pos = r * so_cot + c
            if pos < so_o:
                bang.paste(cells[pos][1], (x_cur, y_cur))
            x_cur += cot_w[c] + margin
        y_cur += hang_h[r] + margin

    scale_out = min(1.0, float(max_side) / float(max(1, bang.width, bang.height)))
    if scale_out < 0.999:
        bang = bang.resize(
            (max(1, int(round(bang.width * scale_out))), max(1, int(round(bang.height * scale_out)))),
            Image.Resampling.LANCZOS,
        )

    out = io.BytesIO()
    bang.save(out, format="JPEG", quality=92, optimize=True)
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
    *,
    co_bang_cat_can_canh: bool = False,
) -> str:
    """Tạo prompt Set-of-Mark Dual-View yêu cầu Vision LLM nhìn toàn cảnh biểu cảm (Ảnh 1)
    kết hợp đọc chính xác nét chữ phóng đại 1:1 (Ảnh 2) và dịch chuẩn từng thẻ `#1..#N`.
    """
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

    huong_dan_hai_anh = (
        f"You are given TWO images:\n"
        f"- Image 1: Full comic page with yellow tags `#1`..`#{so_khung}` and thin magenta frames (use for panel flow, speaker identity, emotion, and reading order).\n"
        f"- Image 2: High-resolution zoomed crop sheet of those exact `#1`..`#{so_khung}` regions (dark-background/hair boxes were contrast-inverted to dark text on light paper so every tiny glyph, punctuation, and broken line is crystal clear).\n"
        if co_bang_cat_can_canh
        else f"This comic page has {so_khung} pre-detected text regions marked with yellow-black tags `#1` through `#{so_khung}` and thin magenta frames.\n"
    )

    return (
        f"You are an elite multimodal Manga/Manhwa/Comic scanlation director translating from {ten_nguon} into {ten_dich}.\n"
        f"{huong_dan_hai_anh}"
        "Tasks:\n"
        f"1. For EVERY marked region `#1` .. `#{so_khung}` that contains dialogue, narration, caption, note, sign, or meaningful text:\n"
        "   - Transcribe the exact source text (`text`) faithfully from the zoomed crop / page—check leading ellipses (`...`), hyphens, contractions, and small words carefully so NOTHING is dropped or misread.\n"
        "   - Translate (`ban_dich`) concisely, naturally, and accurately in scanlation style across all 6 text types:\n"
        "     * Speech & spiky shout bubbles: natural conversational flow matching speaker age/gender/status/emotion in Image 1. Never add fluff or invent words not in the source text.\n"
        "     * Internal monologue / floating haloed thoughts over background or hair: crisp, reflective inner voice.\n"
        "     * Rectangular narration / time-location captions: concise literary storytelling tone.\n"
        "     * Margin translator/editor notes (`*TN:`, `Note:`, `*`): compact explanatory note (`Chú thích: ...` for Vietnamese).\n"
        "     * In-world signs / labels / documents: authentic signage wording.\n"
        "     * Context-driven SFX judgment (preserve clean artwork): keep plot-essential signs or story-critical sound cues, "
        "but leave `ban_dich` strictly empty (`\"\"`) for ordinary decorative/ambient floating SFX strokes drawn over artwork "
        "(e.g. `GULP`, `주절`, `꼬르르`, `픽`, `ビュウ`, `ガタガタ`, `グキ`, `ピキ`, `ボワアア`, `ドゴォン`, `ゴゴゴ`, `轰隆`), "
        "garbled texture misreads, or watermark/credit boxes so the original artwork is left untouched.\n"
        "   - Output `id` equal to the tag number (`1` .. `N`). Do NOT drop valid dialogue/narration tags.\n"
        "2. Safety check for unmarked text: ONLY IF you clearly see an important dialogue/whisper/narration/note line on Image 1 "
        "that has NO `#id` tag at all, include an extra entry with `\"id\": 0` and its tight `[ymin, xmin, ymax, xmax]` (0..1000) in `box`.\n"
        "3. Set `doan: true` only when source characters are genuinely blurred/occluded; otherwise `doan: false`.\n"
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
        # Khi Vision LLM cố ý để trống `ban_dich` (vì là SFX trang trí / nhiễu nền / watermark),
        # tuyệt đối KHÔNG lấy lại `chu` để thay thế — tôn trọng quyết định bỏ qua để giữ nguyên nét tranh.
        if not ban_dich:
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
                    ban_dich=ban_dich or None,
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
                    ban_dich=ban_dich or None,
                    doan=co_doan,
                )
            )

    ra: list[DetectedRegion] = []
    for idx in range(1, n + 1):
        if idx in da_ghep_theo_id:
            ra.append(da_ghep_theo_id[idx])
    ra.extend(bo_sung_id0)
    return ra
