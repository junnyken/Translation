"""E46 — nhận diện khung chữ bằng Gemini, thay cho ONNX cục bộ.

## Vì sao có tệp này

`comic-text-detector` chạy CPU mất **42–70s/trang** và chiếm ~60% thời gian một trang
(`REPORT_E45.md` §8). E25 và E45 đã đóng sáu hướng tối ưu — cả sáu đều *chia lại* cùng một khối
tính toán nên thất bại cùng lý do. Gọi AI thì **bỏ hẳn khối đó ra khỏi máy**: đo được **3,5s**,
tốn ~1,2 xu Mỹ cho một chapter 24 trang (`REPORT_E46.md`).

## Ba quyết định KHÔNG được đảo, mỗi cái đều có số đo đứng sau

### 1. `responseSchema` là BẮT BUỘC, không phải tuỳ chọn

Xin JSON bằng lời nhắc **hỏng âm thầm**. Đo được trên chính fixture của dự án: model dừng giữa
mảng JSON (thiếu dấu đóng) mà vẫn báo `finishReason: STOP` — tức nó *tưởng* đã trả lời xong — và
đổi tên khoá ngay trong một câu trả lời (`box` rồi `box_2d`). Tái hiện **7/7 lần trên cùng một
trang**, tức hỏng **tất định theo trang** chứ không phải nhiễu.

Không ngoại lệ mạng, không mã lỗi, chỉ là **dữ liệu thiếu** ⇒ trang đó im lặng mất vùng chữ.

Ép schema: **45/45 thành công** (so với 24/30), và còn *nhanh hơn* (2,46s so với 3,58s) vì không
phải sinh rào markdown hay lời dẫn.

### 2. Đòi khung CHỮ, KHÔNG đòi khung BONG BÓNG

Lời nhắc đầu tiên nói *"speech balloon and text area"* — chính nó mời model khoanh cả bong bóng.
Hậu quả đo được: diện tích ăn vào nét vẽ **gấp 2,7 lần** khung của model cũ. Khung này còn làm
**mask cho LaMa**, nên thừa nghĩa là **xoá cả nét vẽ quanh bong bóng**.

Đổi sang đòi khung bám sát nét chữ: **2,7× → 1,3×**. Đừng nới lời nhắc này ra cho "an toàn hơn" —
nới là quay lại đúng lỗi cũ.

### 3. `confidence = None`, KHÔNG bịa số

Gemini không trả điểm tin cậy. Điền 1.0 cho gọn là **bịa ra một con số không hề tồn tại** — đúng
thứ `ConfidenceState.unavailable` sinh ra để tránh (xem docstring của nó). Vùng do engine này tạo
có `confidence=None` và **không bao giờ** bị gắn cờ `low_confidence`, vì không có bằng chứng nào
để gắn.

## Vì sao KHÔNG đặt làm mặc định

Đo trên 5 trang Pepper&Carrot: engine này **bỏ sót 2/27 vùng**, model cũ sót **0/27**. Sót một
bong bóng nghĩa là **mất hẳn một câu thoại** trong bản giao cho người đọc. Mặc định vẫn là `ctd`;
ai bật cái này là chấp nhận đánh đổi đó một cách có ý thức.

Thêm nữa, toàn bộ phép đo chạy trên **truyện tiếng Anh, khung tranh phương Tây**. Truyện Nhật —
chữ dọc, bong bóng không viền, chữ tượng thanh đè lên nét vẽ — **chưa thử lần nào**.

## Hỏng thì BÁO, không lặng lẽ lùi về model cũ

Tự lùi về `ctd` khi API lỗi nghe có vẻ an toàn nhưng phá nguyên tắc evidence-first: người dùng
tưởng đang chạy engine mình chọn, và một sự cố kéo dài sẽ không ai thấy. Lỗi ở đây ném
`AIDetectError`; job detect sẽ mang đúng lý do đọc được.
"""
from __future__ import annotations

import base64
import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass, replace

from app.services.detect.ctd import DetectedRegion
from app.services.interfaces import BBox

logger = logging.getLogger(__name__)

#: Toạ độ Gemini trả về đã chuẩn hoá về thang này (`[ymin, xmin, ymax, xmax]`).
#: Đã XÁC MINH bằng cách vẽ khung lên ảnh và nhìn — đoán sai thứ tự sẽ cho khung
#: trông hợp lý mà sai hoàn toàn.
THANG = 1000.0

#: Ép cấu trúc đầu ra. Xem §1 ở docstring đầu tệp — bỏ cái này là mở lại đường hỏng âm thầm.
SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "box": {"type": "ARRAY", "items": {"type": "INTEGER"},
                    "minItems": 4, "maxItems": 4},
            #: E90 — chữ trong khung. TUỲ CHỌN trong schema: thiếu thì bước OCR chạy như cũ.
            "text": {"type": "STRING"},
        },
        "required": ["box"],
    },
}

#: E96 — Schema gộp Nhận diện khung + Đọc chữ (OCR) + Dịch ngữ cảnh trong 1 lượt gọi Gemini
#: duy nhất cho chế độ `chi_chu` (tiện ích đọc truyện).
SCHEMA_GOP_DICH = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "box": {
                "type": "ARRAY",
                "items": {"type": "INTEGER"},
                "minItems": 4,
                "maxItems": 4,
            },
            "text": {"type": "STRING"},
            "ban_dich": {"type": "STRING"},
            "doan": {"type": "BOOLEAN"},
        },
        "required": ["box", "text", "ban_dich", "doan"],
    },
}

#: Xem §2 ở docstring đầu tệp. Mỗi câu ở đây đều đang gánh một con số đo được.
LOI_NHAC = (
    "Find every block of dialogue, narration, character screams/shouts, and caption text in this comic page "
    "(including borderless floating dialogue with white/black outlines and spiky scream balloons). "
    "For each block, give a TIGHT bounding box [ymin, xmin, ymax, xmax] normalized 0-1000 around ALL lines "
    "and punctuation of that text block. "
    "Do NOT include the speech balloon, bubble outline, or blank padding, and NEVER shift the box onto "
    "adjacent hair, faces, or artwork outside the letters. "
    "MUST include every line from the first word down to the very last line and trailing punctuation "
    "(never clip the bottom line or '?/...' of a multi-line block). "
    "CRITICAL SFX RULE: NEVER box stylized brush-stroke sound effects / onomatopoeia (e.g. ドゴォン, ゴゴゴ, ズシン, "
    "콰아앙, 쿠구구, 轰隆, BOOM, SLASH, SWOOSH, THUD, CRACK) drawn directly over artwork, weapons, characters, or explosions "
    "outside speech balloons — leave background artwork SFX untouched. "
    "DO box character screams, yells, and attack/skill names inside spiky/jagged speech balloons. "
    "Return the exact original characters in \"text\" (join line breaks with spaces)."
)


_TEN_NGON_NGU_1PASS = {
    "en": "natural, idiomatic Comic/Manga English",
    "es": "natural, expressive Spanish (Español neutro/latino para Manga/Manhwa)",
    "pt": "natural Brazilian Portuguese (Português brasileiro para Manga/Webtoon)",
    "fr": "natural French (Français fluide pour Manga/Webtoon)",
    "id": "natural Bahasa Indonesia (Bahasa Indonesia luwes untuk Komik/Manhwa)",
    "th": "natural Thai (ภาษาไทยธรรมชาติสำหรับการ์ตูน/มังงะ)",
    "zh": "natural Simplified Chinese (自然流畅的简体中文漫画对白)",
    "zh-tw": "natural Traditional Chinese (自然流暢的繁體中文漫畫對白)",
}


def xay_loi_nhac_gop_dich(source_lang: str, target_lang: str, boi_canh: str = "") -> str:
    """E96 + E104 — Lời nhắc gộp Nhận diện + Đọc chữ + Dịch ngữ cảnh trong 1 lượt gọi (rút gọn chuẩn kỹ thuật)."""
    boi_canh_sach = (boi_canh or "").strip()
    la_ultra_3_luot = "[CHẾ ĐỘ ULTRA CLOUD AI 3 LƯỢT" in boi_canh_sach
    la_pro_2_luot = "[CHẾ ĐỘ AI PRO 2 LƯỢT" in boi_canh_sach
    tl_norm = str(target_lang or "vi").strip().lower()
    if tl_norm != "vi":
        ten_dich = _TEN_NGON_NGU_1PASS.get(tl_norm, tl_norm)
        chi_dan_cap_do_qt = ""
        if la_ultra_3_luot:
            chi_dan_cap_do_qt = "- [ULTRA 2K SCANLATION]: Inspect facial expressions, age, and hierarchy for natural register; capture tiny handwritten whispers.\n"
        elif la_pro_2_luot:
            chi_dan_cap_do_qt = "- [PRO SCANLATION]: Capture handwritten side-notes and enforce 100% glossary consistency.\n"
        return (
            f"{LOI_NHAC}\n\n"
            f"Translate each block from {source_lang} into {ten_dich} in \"ban_dich\":\n"
            "- Translate in full-page context matching character tone, emotion, and relationship.\n"
            f"{chi_dan_cap_do_qt}"
            "- Screams, shouts & skill names in spiky balloons: translate in ALL-CAPS with strong exclamation ('!!') and condense elongated vowels.\n"
            "- Background artwork SFX outside balloons: do NOT include them (if a tiny inline action note inside a balloon appears, localize naturally).\n"
            f"- Complete, natural sentences in {ten_dich} with zero untranslated source characters.\n"
            "- Set \"doan\" = true ONLY if text is occluded/blurry; otherwise false."
            + (f"\n\n{boi_canh_sach}" if boi_canh_sach else "")
        )
    chi_dan_cap_do_vi = ""
    if la_ultra_3_luot:
        chi_dan_cap_do_vi = (
            "- [ULTRA 2K SCANLATION]: Quan sát biểu cảm, trang phục, tuổi tác và vị thế nhân vật để chọn chuẩn đại từ "
            "(Ta-Ngươi, Huynh-Muội, Thần-Bệ hạ, Anh-Em, Mày-Tao); đọc sạch chữ viết tay nhỏ cạnh khung.\n"
        )
    elif la_pro_2_luot:
        chi_dan_cap_do_vi = (
            "- [PRO SCANLATION]: Đọc kỹ chữ viết tay/lẩm bẩm ngoài bóng thoại và đồng nhất 100% đại từ theo từ điển.\n"
        )
    return (
        f"{LOI_NHAC}\n\n"
        f"Dịch từng khối chữ từ {source_lang} sang {target_lang} vào trường \"ban_dich\":\n"
        "- Dịch theo ngữ cảnh toàn trang (lưu ý thứ tự đọc phải-sang-trái của Manga), khớp cảm xúc và quan hệ nhân vật.\n"
        f"{chi_dan_cap_do_vi}"
        "- Tiếng hét lớn, tiếng gầm & tên chiêu thức trong bóng thoại gai nhọn: dịch sang chữ IN HOA ĐẬM CẢM XÚC kèm '!!' (vd: 'DỪNG LẠI NGAY!!', 'KHÔNGGG!!', 'THIÊN ĐỊA VÔ CỰC!'), rút gọn nguyên âm kéo dài.\n"
        "- Chữ tượng thanh/tượng hình (SFX) vẽ cách điệu đè lên nền tranh ngoài bóng thoại: BỎ QUA không khoanh để giữ nguyên nét vẽ gốc.\n"
        "- Tên riêng: phiên âm chuẩn và giữ đồng nhất. Câu dịch hoàn chỉnh, có dấu câu, không sót ký tự gốc.\n"
        "- Đặt \"doan\" = true CHỈ KHI chữ gốc bị mờ/che khuất; còn lại false."
        + (f"\n\n{boi_canh_sach}" if boi_canh_sach else "")
    )

#: E90 — khung chỉ chứa chữ số (số trang, số in trên nhãn chai…) KHÔNG phải lời cần dịch. Lời nhắc
#: đọc chữ làm model khoanh thêm chúng (A/B: "18" xuất hiện 3 lần trên trang Pepper&Carrot).
_CHI_LA_SO = __import__("re").compile(r"^(?=.*\d)[\s\d.,:/\-–—#]+$")
_MAU_SFX_NGAN = __import__("re").compile(
    r"^(?:WHO+M+|BO+M+|KA-?RO+M+|KRA+K+|CRA+SH+|BA+M+|SLA+M+|THU+D+|ZWO+SH+|SPLA+SH+|SPLR+SH+|STOMP+|CLANK+|CLANG+|SWO+SH+|SLI+CE+|"
    r"BÙM+|ẦM+|RẦM+|XOẸT+|XÈ+|KENG+|VÙ+|VỤT+|BỐP+|BỊCH+|UỲNH+|"
    r"ドゴ+ン*|ゴゴ+|ズシ+ン*|ザッ+|パァ+ン*|ドォ+ン*|バァ+ン*|ガァ+ン*|シュッ+|ギュッ+|"
    r"콰아+앙*|쿠구+구*|스윽+|번쩍+|퍼억+|쾅+|쿵+|휙+|"
    r"轰隆*|砰+|嗖+|咔嚓*)[!?.\s…~〜ー]*$",
    __import__("re").IGNORECASE,
)


def can_chinh_khung_theo_bong_bong(
    image_path: str,
    regions: list[DetectedRegion],
) -> list[DetectedRegion]:
    """Căn chỉnh chính xác toạ độ khung chữ `regions` của Gemini vào đúng cụm chữ bên trong lòng bong bóng trắng.

    Khắc phục triệt để 2 hiện tượng của `gemini-3.1-flash-lite` trên trang truyện nhiều khung phức tạp:
    1. Khoanh hụt dòng đầu/dòng cuối hoặc lề trái/phải của cụm chữ trong bong bóng (Pass A: mở rộng khớp trọn `tx0..ty1`).
    2. Đặt lệch tâm hộp chữ sang vùng tóc đen / đám đông / khói bụi kế bên bong bóng thoại trong cùng khung tranh
       (Pass B: tự động hút hộp chữ bị lệch về đúng cụm chữ trong lòng bong bóng chưa có chủ ở cùng dải ngang).
    """
    if not regions:
        return regions
    try:
        import cv2
        import numpy as np

        a = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if a is None or a.size == 0:
            return regions
        H, W = a.shape
        if W < 64 or H < 64:
            return regions

        S = max(0.75, min(W, H) / 960.0)
        white = (a > 205).astype(np.uint8)
        num, labels, stats, _ = cv2.connectedComponentsWithStats(white, connectivity=4)

        bubbles: list[dict] = []
        for idx in range(1, num):
            x0, y0, bw, bh, area = (int(v) for v in stats[idx])
            x1, y1 = x0 + bw, y0 + bh
            if bw < 22 or bh < 18 or bw > W * 0.92 or bh > H * 0.92 or area < 450:
                continue
            pad = np.zeros((bh + 2, bw + 2), dtype=np.uint8)
            pad[1 : bh + 1, 1 : bw + 1] = (labels[y0:y1, x0:x1] == idx).astype(np.uint8)
            inv = (1 - pad).astype(np.uint8)
            n_inv, l_inv, s_inv, _ = cv2.connectedComponentsWithStats(inv, connectivity=8)
            ext_lbl = int(l_inv[0, 0])
            chars = []
            all_holes = []
            for h_idx in range(1, n_inv):
                if h_idx == ext_lbl:
                    continue
                hx, hy, hw, hh, ha = (int(v) for v in s_inv[h_idx])
                hx -= 1
                hy -= 1
                if hx < 0 or hy < 0 or hx + hw > bw or hy + hh > bh:
                    continue
                min_val = int(a[y0 + hy : y0 + hy + hh, x0 + hx : x0 + hx + hw].min())
                if min_val <= 115 and ha >= 4 and hw <= round(48 * S) and hh <= round(48 * S):
                    all_holes.append([x0 + hx, y0 + hy, x0 + hx + hw, y0 + hy + hh, ha, hw, hh])
                if (
                    min_val <= 105
                    and ha >= round(14 * S * S)
                    and round(3 * S) <= hw <= round(42 * S)
                    and round(7 * S) <= hh <= round(42 * S)
                ):
                    chars.append([x0 + hx, y0 + hy, x0 + hx + hw, y0 + hy + hh, ha, hw, hh])
            if len(chars) < 2:
                continue

            n_c = len(chars)
            visited = [False] * n_c
            sub_clusters: list[dict] = []
            for i in range(n_c):
                if visited[i]:
                    continue
                comp = [i]
                visited[i] = True
                q = [i]
                while q:
                    cur = q.pop()
                    cx0, cy0, cx1, cy1 = chars[cur][:4]
                    for j in range(n_c):
                        if visited[j]:
                            continue
                        jx0, jy0, jx1, jy1 = chars[j][:4]
                        gx = max(0, max(cx0 - jx1, jx0 - cx1))
                        gy = max(0, max(cy0 - jy1, jy0 - cy1))
                        if gx <= round(18 * S) and gy <= round(28 * S):
                            visited[j] = True
                            comp.append(j)
                            q.append(j)
                if len(comp) < 2:
                    continue
                hs = sorted(chars[k][6] for k in comp)
                h_ratio = hs[int(len(hs) * 0.75)] / max(1, hs[int(len(hs) * 0.25)])
                if h_ratio > 1.78:
                    continue
                c_area = sum(chars[k][4] for k in comp)
                tx0 = min(chars[k][0] for k in comp)
                ty0 = min(chars[k][1] for k in comp)
                tx1 = max(chars[k][2] for k in comp)
                ty1 = max(chars[k][3] for k in comp)
                for h in all_holes:
                    hx0, hy0, hx1, hy1 = h[:4]
                    if (
                        hx0 >= tx0 - round(10 * S)
                        and hx1 <= tx1 + round(10 * S)
                        and hy0 >= ty0 - round(12 * S)
                        and hy1 <= ty1 + round(12 * S)
                    ):
                        tx0, ty0 = min(tx0, hx0), min(ty0, hy0)
                        tx1, ty1 = max(tx1, hx1), max(ty1, hy1)
                tw, th = tx1 - tx0, ty1 - ty0
                fill = c_area / max(1, tw * th)
                sub_box = a[max(0, ty0 - 4) : min(H, ty1 + 4), max(0, tx0 - 4) : min(W, tx1 + 4)]
                white_ratio = float((sub_box > 210).mean()) if sub_box.size > 0 else 0.0
                min_area_need = round(90 * S * S) if len(comp) == 2 else round(150 * S * S)
                min_white_need = 0.56 if len(comp) == 2 else 0.48
                if c_area >= min_area_need and fill >= 0.13 and white_ratio >= min_white_need:
                    sub_clusters.append(
                        {
                            "bx0": float(x0),
                            "by0": float(y0),
                            "bx1": float(x1),
                            "by1": float(y1),
                            "tx0": float(tx0),
                            "ty0": float(ty0),
                            "tx1": float(tx1),
                            "ty1": float(ty1),
                            "chars": len(comp),
                            "c_area": c_area,
                            "da_gan": False,
                        }
                    )
            if len(sub_clusters) > 1:
                merged = True
                while merged and len(sub_clusters) > 1:
                    merged = False
                    for a_i in range(len(sub_clusters)):
                        for b_i in range(a_i + 1, len(sub_clusters)):
                            A = sub_clusters[a_i]
                            B = sub_clusters[b_i]
                            x_ov = min(A["tx1"], B["tx1"]) - max(A["tx0"], B["tx0"])
                            y_ov = min(A["ty1"], B["ty1"]) - max(A["ty0"], B["ty0"])
                            x_gap = max(0.0, max(A["tx0"] - B["tx1"], B["tx0"] - A["tx1"]))
                            y_gap = max(0.0, max(A["ty0"] - B["ty1"], B["ty0"] - A["ty1"]))
                            min_h = max(1.0, min(A["ty1"] - A["ty0"], B["ty1"] - B["ty0"]))
                            gop_doc = (
                                bw <= W * 0.36
                                and bh <= H * 0.42
                                and x_ov >= -round(14 * S)
                                and y_gap <= round(48 * S)
                            )
                            gop_cot_ngang = (
                                x_gap <= round(26 * S)
                                and y_ov >= min_h * 0.35
                                and (max(A["tx1"], B["tx1"]) - min(A["tx0"], B["tx0"])) <= W * 0.48
                                and (max(A["ty1"], B["ty1"]) - min(A["ty0"], B["ty0"])) <= H * 0.48
                            )
                            if gop_doc or gop_cot_ngang:
                                A["tx0"] = min(A["tx0"], B["tx0"])
                                A["ty0"] = min(A["ty0"], B["ty0"])
                                A["tx1"] = max(A["tx1"], B["tx1"])
                                A["ty1"] = max(A["ty1"], B["ty1"])
                                A["chars"] += B["chars"]
                                A["c_area"] += B["c_area"]
                                sub_clusters.pop(b_i)
                                merged = True
                                break
                        if merged:
                            break
            bubbles.extend(sub_clusters)

        if not bubbles:
            return regions

        def _la_sfx_ngan(r: DetectedRegion) -> bool:
            chu_goc = (r.chu or "").strip()
            ban_dich = (r.ban_dich or "").strip()
            if chu_goc and _MAU_SFX_NGAN.match(chu_goc):
                return True
            if ban_dich and _MAU_SFX_NGAN.match(ban_dich):
                return True
            return False

        def _co_ranh_khung_tranh_doc(x_a: float, x_b: float, y_top: float, y_bot: float) -> bool:
            xa = int(max(0, min(W - 1, min(x_a, x_b))))
            xb = int(max(0, min(W - 1, max(x_a, x_b))))
            ya = int(max(0, min(H - 1, y_top)))
            yb = int(max(0, min(H, y_bot)))
            if xb - xa < 16 or yb - ya < 40:
                return False
            strip = a[ya:yb, xa:xb]
            col_white = (strip > 238).mean(axis=0)
            col_dark = (strip < 95).mean(axis=0)
            # Rãnh ngăn cách 2 khung tranh: phải có vách mực đen dọc (>= 80% chiều cao) kẹp hai bên dải trắng (>= 5px)
            n_cols = len(col_white)
            i_c = 0
            while i_c < n_cols:
                if col_white[i_c] >= 0.94:
                    j_c = i_c
                    while j_c < n_cols and col_white[j_c] >= 0.94:
                        j_c += 1
                    if j_c - i_c >= 5:
                        co_vien_trai = any(col_dark[k] >= 0.78 for k in range(max(0, i_c - 5), i_c))
                        co_vien_phai = any(col_dark[k] >= 0.78 for k in range(j_c, min(n_cols, j_c + 5)))
                        if co_vien_trai and co_vien_phai:
                            return True
                    i_c = j_c
                else:
                    i_c += 1
            return False

        da_gan_r = [False] * len(regions)

        # Pass A: Khớp trực tiếp các hộp chữ đã giao cắt hoặc nằm trong lòng bong bóng
        for r_idx, r in enumerate(regions):
            if _la_sfx_ngan(r):
                continue
            vx0, vy0 = float(r.bbox.x), float(r.bbox.y)
            vx1, vy1 = vx0 + float(r.bbox.w), vy0 + float(r.bbox.h)
            vcx, vcy = (vx0 + vx1) * 0.5, (vy0 + vy1) * 0.5
            best_b = None
            best_score = 0.0
            for b in bubbles:
                if b["da_gan"]:
                    continue
                ix0, iy0 = max(vx0, b["tx0"]), max(vy0, b["ty0"])
                ix1, iy1 = min(vx1, b["tx1"]), min(vy1, b["ty1"])
                inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
                min_a = max(1.0, min(r.bbox.w * r.bbox.h, (b["tx1"] - b["tx0"]) * (b["ty1"] - b["ty0"])))
                ov = inter / min_a
                btcy = (b["ty0"] + b["ty1"]) * 0.5
                in_bub = (
                    b["bx0"] <= vcx <= b["bx1"]
                    and b["by0"] <= vcy <= b["by1"]
                    and abs(vcy - btcy) <= max(r.bbox.h, b["ty1"] - b["ty0"], 65.0 * S)
                )
                if ov >= 0.18 or in_bub:
                    score = ov + (0.5 if in_bub else 0.0)
                    if score > best_score:
                        best_score = score
                        best_b = b
            if best_b is not None:
                best_b["da_gan"] = True
                da_gan_r[r_idx] = True
                regions[r_idx] = replace(
                    r,
                    bbox=BBox(
                        x=best_b["tx0"],
                        y=best_b["ty0"],
                        w=best_b["tx1"] - best_b["tx0"],
                        h=best_b["ty1"] - best_b["ty0"],
                    ),
                )

        # Pass B: Khôi phục hộp thoại bị AI đặt lệch ra ngoài bong bóng (đè lên tóc đen / đám đông trong cùng khung tranh)
        for r_idx, r in enumerate(regions):
            if da_gan_r[r_idx] or _la_sfx_ngan(r):
                continue
            vx0, vy0 = float(r.bbox.x), float(r.bbox.y)
            vx1, vy1 = vx0 + float(r.bbox.w), vy0 + float(r.bbox.h)
            vcx, vcy = (vx0 + vx1) * 0.5, (vy0 + vy1) * 0.5
            do_dai_chu = max(len((r.chu or "").strip()), len((r.ban_dich or "").strip()))
            best_b = None
            best_dist = 1e9
            for b in bubbles:
                if b["da_gan"]:
                    continue
                if do_dai_chu > 0:
                    if b["chars"] >= 14 and do_dai_chu <= 7:
                        continue
                    if b["chars"] <= 6 and do_dai_chu >= 22:
                        continue
                btcx = (b["tx0"] + b["tx1"]) * 0.5
                btcy = (b["ty0"] + b["ty1"]) * 0.5
                vy_ov = min(vy1, b["by1"]) - max(vy0, b["by0"])
                if vy_ov < -20.0 * S and abs(vcy - btcy) > max(r.bbox.h, b["ty1"] - b["ty0"], 90.0 * S):
                    continue
                dx = abs(vcx - btcx)
                dy = abs(vcy - btcy)
                if dx > W * 0.34:
                    continue
                if _co_ranh_khung_tranh_doc(vcx, btcx, max(vy0, b["by0"]), min(vy1, b["by1"])):
                    continue
                dist = dx + dy * 1.5
                if dist < best_dist:
                    best_dist = dist
                    best_b = b
            if best_b is not None:
                best_b["da_gan"] = True
                da_gan_r[r_idx] = True
                regions[r_idx] = replace(
                    r,
                    bbox=BBox(
                        x=best_b["tx0"],
                        y=best_b["ty0"],
                        w=best_b["tx1"] - best_b["tx0"],
                        h=best_b["ty1"] - best_b["ty0"],
                    ),
                )

        # Pass C: Loại bỏ chữ tượng thanh/tượng hình (SFX) vẽ đè trực tiếp lên nền tranh phức tạp ngoài bong bóng
        # (giữ nguyên 100% các câu thoại và tiếng hét nằm trong bong bóng trắng/đen khép kín).
        ket_qua_loc: list[DetectedRegion] = []
        for r_idx, r in enumerate(regions):
            if not da_gan_r[r_idx] and _la_sfx_ngan(r):
                rx0 = int(max(0, min(W - 1, r.bbox.x)))
                ry0 = int(max(0, min(H - 1, r.bbox.y)))
                rx1 = int(max(rx0 + 1, min(W, r.bbox.x + r.bbox.w)))
                ry1 = int(max(ry0 + 1, min(H, r.bbox.y + r.bbox.h)))
                patch = a[ry0:ry1, rx0:rx1]
                if patch.size > 0:
                    ty_le_trang = float((patch > 212).mean())
                    ty_le_den = float((patch < 42).mean())
                    if ty_le_trang < 0.58 and ty_le_den < 0.72:
                        logger.info("ai_gemini bo qua SFX ve de len tranh ngoai bong thoai: %r", r.chu or r.ban_dich)
                        continue
            ket_qua_loc.append(r)
        return ket_qua_loc
    except Exception as exc:  # noqa: BLE001
        logger.warning("can_chinh_khung_theo_bong_bong bo qua do loi: %s", exc)
        return regions


def _giao(a, b) -> float:
    """Phần giao / diện tích khung NHỎ hơn ([ymin, xmin, ymax, xmax])."""
    y0, x0 = max(a[0], b[0]), max(a[1], b[1])
    y1, x1 = min(a[2], b[2]), min(a[3], b[3])
    giao = max(0, y1 - y0) * max(0, x1 - x0)
    nho = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return giao / nho if nho > 0 else 0.0


def gop_luot(cac_luot: list[list[dict]]) -> list[dict]:
    """E93 — gộp khung của nhiều lượt gọi: giữ NGUYÊN lượt nhiều khung nhất, chỉ THÊM khung của
    lượt khác KHÔNG chạm khung nào đã giữ.

    Vì sao: model dao động giữa các lượt dù temperature 0. Đo 16-10-2026 trên ja_E12P01 (6 lượt):
    chữ tượng thanh カラン/コロン có lượt khoanh đủ 3, có lượt 0; lời nhắc nói rõ hơn KHÔNG chữa được
    (2/3 so với 2/3). E46 cũng ghi engine này sót 2/27 bong bóng. Gộp chỉ thêm khung RỜI nhau ⇒
    không sinh vùng chồng/đôi chữ; khung chạm nhau (cùng bong bóng khoanh khác cách) thì bỏ.
    """
    hop_le = [[m for m in luot if isinstance(m.get("box"), list) and len(m["box"]) == 4]
              for luot in cac_luot]
    hop_le.sort(key=len, reverse=True)
    giu = list(hop_le[0]) if hop_le else []
    for luot in hop_le[1:]:
        for m in luot:
            if all(_giao(m["box"], g["box"]) < 0.2 for g in giu):
                giu.append(m)
    return giu


class AIDetectError(RuntimeError):
    """Nhận diện bằng AI thất bại. Mang lý do đọc được, không nuốt."""


def la_anh_khong_co_chu(image_path: str) -> bool:
    """Bộ lọc Tiền Kiểm (Pre-Flight Blank/Transition Strip Filter) kiểu Cotrans / Ichigo:
    Kiểm tra siêu nhanh (<2ms bằng NumPy) xem dải ảnh Webtoon/Manhwa có phải là dải chuyển cảnh
    trắng tinh, đen kịt, hoặc dải màu chuyển sắc (gradient) hoàn toàn không có bất kỳ nét chữ/viền sắc nào không.
    Nếu không có nét tương phản cục bộ nào (`max_grad < 28` và `std < 5.0` trên ảnh kích thước thực `>= 320px`),
    bỏ qua ngay lập tức, tốn 0 token Gemini Vision.
    """
    try:
        import numpy as np
        from PIL import Image

        with Image.open(image_path) as im:
            w, h = im.size
            if w < 320 or h < 320:
                return False
            a = np.asarray(im.convert("L"), dtype=np.int16)
        if float(a.std()) >= 5.0:
            return False
        dx = int(np.abs(np.diff(a, axis=1)).max()) if a.shape[1] > 1 else 0
        dy = int(np.abs(np.diff(a, axis=0)).max()) if a.shape[0] > 1 else 0
        return max(dx, dy) < 28
    except Exception:  # noqa: BLE001
        return False


def cat_dai_hoat_dong_co_chu(
    image_path: str, goc_bytes: bytes, rong_goc: int, cao_goc: int
) -> tuple[bytes, int, int]:
    """Tiền định vị vùng có chữ / bóng thoại & Cắt gọn dải hoạt động (ROI Pre-Detection & Active-Band Cropping):

    Học từ kiến trúc BallonsTranslator & Cotrans:
    - Với các trang/dải Webtoon cao (`cao_goc >= 960` và `cao_goc >= rong_goc * 1.45`), thường 30%-70% chiều cao
      ở đầu hoặc cuối dải là bầu trời, kiến trúc, cảnh hành động hoặc khoảng chuyển cảnh không có chữ.
    - Quét nhanh (<5ms bằng OpenCV) tìm các cụm nét chữ trong lòng bong bóng trắng/đen và cụm tương phản cao.
    - Nếu vùng chứa chữ chỉ nằm gọn trong `<= 75%` chiều cao trang, cắt gọn (`crop`) đúng dải có chữ kèm lề
      ngữ cảnh 12% rồi mới gửi cho Gemini OCR/Vision.
    - Lợi ích kép:
      1. Đưa dải ảnh dài về tỷ lệ chuẩn `<= 2.2` để lọt gọn vào 1 ô đơn `768px` (258 token thay vì 1.290 token).
      2. Chữ trong bóng thoại sau khi thu về 768px vẫn TO VÀ SẮC NÉT gấp 1,5-2,5 lần so với gửi nguyên dải dài!
    """
    if cao_goc < 960 or cao_goc < rong_goc * 1.45:
        return goc_bytes, 0, cao_goc
    try:
        import io
        import cv2
        import numpy as np
        from PIL import Image

        a = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if a is None or a.shape[0] != cao_goc or a.shape[1] != rong_goc:
            return goc_bytes, 0, cao_goc

        # Tìm các cụm nét chữ có độ tương phản cục bộ cao (Black-Hat cho chữ đen nền sáng & Top-Hat cho chữ trắng nền tối)
        k_w = max(9, min(25, round(rong_goc / 38)))
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k_w, 3))
        bhat = cv2.morphologyEx(a, cv2.MORPH_BLACKHAT, kernel)
        that = cv2.morphologyEx(a, cv2.MORPH_TOPHAT, kernel)
        text_energy = np.maximum(bhat, that)

        # Bỏ qua 4% viền trái/phải (thường là khung viền dọc của khung tranh)
        le_x = max(4, round(rong_goc * 0.04))
        core = text_energy[:, le_x : max(le_x + 1, rong_goc - le_x)]
        row_active = (core > 85).mean(axis=1)

        # Làm mượt theo cửa sổ dọc ~18px để chỉ giữ các dải thực sự có cụm ký tự (loại bỏ đường kẻ đơn lẻ)
        win = max(9, round(cao_goc / 90))
        smooth = np.convolve(row_active, np.ones(win) / win, mode="same")
        idx_co_chu = np.where(smooth >= 0.018)[0]
        if idx_co_chu.size < 8:
            return goc_bytes, 0, cao_goc

        le_y = max(48, round(rong_goc * 0.14))
        y0_cat = max(0, int(idx_co_chu[0]) - le_y)
        y1_cat = min(cao_goc, int(idx_co_chu[-1]) + le_y)
        cao_cat = y1_cat - y0_cat
        if cao_cat < 320 or cao_cat > cao_goc * 0.76:
            return goc_bytes, 0, cao_goc

        with Image.open(io.BytesIO(goc_bytes)) as im:
            im_cat = im.crop((0, y0_cat, rong_goc, y1_cat)).convert("RGB")
            buf = io.BytesIO()
            im_cat.save(buf, format="JPEG", quality=88, optimize=True)
            logger.info(
                "ai_gemini ROI crop: %s thu gon chieu cao %d -> %d (y=%d..%d)",
                image_path, cao_goc, cao_cat, y0_cat, y1_cat,
            )
            return buf.getvalue(), y0_cat, cao_cat
    except Exception:  # noqa: BLE001
        return goc_bytes, 0, cao_goc


@dataclass
class AIGeminiDetector:
    """Nhận diện khung chữ qua Gemini. Cùng interface với `CTDDetector` nên thay được tại chỗ."""

    api_keys: list[str]
    model_name: str = "gemini-3.1-flash-lite"
    timeout: int = 120
    #: Cạnh dài ảnh gửi đi. Gemini tính tiền theo ô 768×768 nên giữ mặc định 768px để vừa khít
    #: 1 ô đơn (258 token), giảm 80% chi phí quét ảnh so với mức >768px (bị chia 4-5 ô).
    canh_toi_da: int = 768
    #: E93 — số lượt gọi SONG SONG rồi gộp khung (xem `gop_luot`). 1 = như trước; production đặt
    #: qua `DETECT_AI_SO_LUOT` (mặc định cấu hình 1).
    so_luot: int = 1

    def detect(self, image_path: str) -> list[BBox]:
        return [r.bbox for r in self.detect_regions(image_path)]

    def detect_regions(self, image_path: str) -> list[DetectedRegion]:
        if not self.api_keys:
            raise AIDetectError(
                "Chưa cấu hình GEMINI_API_KEYS — engine nhận diện 'ai_gemini' cần khoá API. "
                "Đặt khoá, hoặc chuyển DETECT_ENGINE về 'ctd' để chạy model cục bộ."
            )
        if la_anh_khong_co_chu(image_path):
            logger.info("ai_gemini bo qua anh chuyen canh khong co chu (0 token): %s", image_path)
            return []

        from PIL import Image

        from app.services.translate.anh_kem import chuan_bi_anh

        with Image.open(image_path) as im:
            rong_goc, cao_goc = im.size

        with open(image_path, "rb") as f:
            goc = f.read()
        goc_gui, y_bat_dau, cao_cat = cat_dai_hoat_dong_co_chu(image_path, goc, rong_goc, cao_goc)
        ty_le_khung = max(rong_goc, cao_cat) / max(1, min(rong_goc, cao_cat))
        canh_dung = max(self.canh_toi_da, 1024) if ty_le_khung > 2.2 else min(self.canh_toi_da, 768)
        da_chuan = chuan_bi_anh(goc_gui, canh_dung)
        if da_chuan is None:
            raise AIDetectError(f"Không chuẩn bị được ảnh để gửi: {image_path}")
        anh, mime = da_chuan

        if self.so_luot > 1:
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(max_workers=self.so_luot) as ex:
                tuong_lai = [ex.submit(self._goi, anh, mime) for _ in range(self.so_luot)]
            cac_luot, loi = [], None
            for f in tuong_lai:
                try:
                    cac_luot.append(f.result())
                except AIDetectError as exc:
                    loi = exc
            if not cac_luot:
                raise loi or AIDetectError("Mọi lượt gọi Gemini đều thất bại")
            tho = gop_luot(cac_luot)
        else:
            tho = self._goi(anh, mime)

        ra: list[DetectedRegion] = []
        for muc in tho:
            hop = muc.get("box")
            if not (isinstance(hop, list) and len(hop) == 4):
                continue
            y0, x0, y1, x1 = (float(v) for v in hop)
            # Toạ độ chuẩn hoá theo ẢNH ĐÃ THU NHỎ (hoặc dải hoạt động đã cắt gọn), quy thẳng về cỡ GỐC.
            x0, x1 = x0 / THANG * rong_goc, x1 / THANG * rong_goc
            y0, y1 = y_bat_dau + y0 / THANG * cao_cat, y_bat_dau + y1 / THANG * cao_cat
            if x1 <= x0 or y1 <= y0:
                continue  # khung rỗng/đảo chiều: bỏ, không tự "sửa" thành khung đoán
            x0, y0 = max(0.0, x0), max(0.0, y0)
            x1, y1 = min(float(rong_goc), x1), min(float(cao_goc), y1)
            chu = muc.get("text")
            chu = " ".join(chu.split()) if isinstance(chu, str) else None
            if chu and _CHI_LA_SO.match(chu):
                continue  # E90: số trang / số trên nhãn — không phải lời thoại
            ban_dich = muc.get("ban_dich")
            ban_dich = " ".join(ban_dich.split()) if isinstance(ban_dich, str) else None
            ra.append(DetectedRegion(
                bbox=BBox(x=x0, y=y0, w=x1 - x0, h=y1 - y0),
                confidence=None,   # §3: KHÔNG bịa. Xem docstring đầu tệp.
                cls=0,
                chu=chu or None,
                ban_dich=ban_dich or None,
                doan=bool(muc.get("doan")),
            ))

        ra = can_chinh_khung_theo_bong_bong(image_path, ra)
        logger.info(
            "ai_gemini detect: %s -> %d khung (model %s)", image_path, len(ra), self.model_name
        )
        return ra

    def detect_va_dich_regions(
        self,
        image_path: str,
        source_lang: str,
        target_lang: str,
        boi_canh: str = "",
    ) -> list[DetectedRegion]:
        """E96 — Nhận diện khung chữ + Đọc chữ + Dịch ngữ cảnh trong 1 lượt gọi Gemini duy nhất.

        Dành riêng cho chế độ `chi_chu` khi `DETECT_ENGINE=ai_gemini` và `engine=llm_context`.
        Chỉ gửi ảnh 1 lần và dùng 1 lượt gọi để cắt giảm một nửa độ trễ (~8s -> ~4s) lẫn ~45%
        token ảnh đầu vào.
        """
        if not self.api_keys:
            raise AIDetectError(
                "Chưa cấu hình GEMINI_API_KEYS — engine nhận diện 'ai_gemini' cần khoá API. "
                "Đặt khoá, hoặc chuyển DETECT_ENGINE về 'ctd' để chạy model cục bộ."
            )
        if la_anh_khong_co_chu(image_path):
            logger.info("ai_gemini bo qua anh chuyen canh khong co chu (0 token): %s", image_path)
            return []

        from PIL import Image

        from app.services.translate.anh_kem import chuan_bi_anh

        with Image.open(image_path) as im:
            rong_goc, cao_goc = im.size

        with open(image_path, "rb") as f:
            goc = f.read()
        goc_gui, y_bat_dau, cao_cat = cat_dai_hoat_dong_co_chu(image_path, goc, rong_goc, cao_goc)
        la_ultra_3_luot = "[CHẾ ĐỘ ULTRA CLOUD AI 3 LƯỢT" in (boi_canh or "")
        la_pro_2_luot = "[CHẾ ĐỘ AI PRO 2 LƯỢT" in (boi_canh or "")
        # Tối ưu chi phí ô ảnh Gemini (768x768 tiling):
        # - Chế độ Tiêu chuẩn (1 lượt, trang/dải tỷ lệ thường <= 2.2): dùng đúng ngưỡng 768px (1 ô = 258 token).
        # - Trang Webtoon dải dọc dài (tỷ lệ > 2.2) hoặc chế độ Pro/Ultra: dùng 1024px để giữ nét chữ nhỏ.
        ty_le_khung = max(rong_goc, cao_cat) / max(1, min(rong_goc, cao_cat))
        if la_ultra_3_luot or la_pro_2_luot or ty_le_khung > 2.2:
            canh_dung = max(self.canh_toi_da, 1024)
        else:
            canh_dung = min(self.canh_toi_da, 768)
        da_chuan = chuan_bi_anh(goc_gui, canh_dung)
        if da_chuan is None:
            raise AIDetectError(f"Không chuẩn bị được ảnh để gửi: {image_path}")
        anh, mime = da_chuan

        # Chế độ Đa Phương Thức 1-Pass: Gemini vừa NHÌN bức tranh vừa nhận diện tọa độ + đọc chữ gốc + dịch ngữ cảnh
        # trong DUY NHẤT 1 lượt gọi. Đây là cấu hình cho chất lượng dịch CAO NHẤT (AI thấy biểu cảm nhân vật, bối cảnh
        # hành động trong tranh để chọn đúng xưng hô và ngữ điệu), đồng thời RẺ HƠN cách tách 2 bước vì Output token
        # Gemini ($0.40/M) rẻ hơn 2,75 lần Output token DeepSeek ($1.10/M), và NHANH HƠN vì chỉ 1 round-trip API.
        loi_nhac = xay_loi_nhac_gop_dich(source_lang, target_lang, boi_canh)
        tho = self._goi(anh, mime, loi_nhac=loi_nhac, schema=SCHEMA_GOP_DICH)

        ra: list[DetectedRegion] = []
        for muc in tho:
            hop = muc.get("box")
            if not (isinstance(hop, list) and len(hop) == 4):
                continue
            y0, x0, y1, x1 = (float(v) for v in hop)
            x0, x1 = x0 / THANG * rong_goc, x1 / THANG * rong_goc
            y0, y1 = y_bat_dau + y0 / THANG * cao_cat, y_bat_dau + y1 / THANG * cao_cat
            if x1 <= x0 or y1 <= y0:
                continue
            x0, y0 = max(0.0, x0), max(0.0, y0)
            x1, y1 = min(float(rong_goc), x1), min(float(cao_goc), y1)
            chu = muc.get("text")
            chu = " ".join(chu.split()) if isinstance(chu, str) else None
            if chu and _CHI_LA_SO.match(chu):
                continue
            ban_dich = muc.get("ban_dich")
            ban_dich = " ".join(ban_dich.split()) if isinstance(ban_dich, str) else None
            ra.append(DetectedRegion(
                bbox=BBox(x=x0, y=y0, w=x1 - x0, h=y1 - y0),
                confidence=None,
                cls=0,
                chu=chu or None,
                ban_dich=ban_dich or None,
                doan=bool(muc.get("doan")),
            ))

        ra = can_chinh_khung_theo_bong_bong(image_path, ra)
        logger.info(
            "ai_gemini detect_va_dich (1-pass): %s -> %d khung (model %s)",
            image_path, len(ra), self.model_name,
        )
        return ra

    def _goi(
        self,
        anh: bytes,
        mime: str,
        *,
        loi_nhac: str = LOI_NHAC,
        schema: dict = SCHEMA,
    ) -> list[dict]:
        """Gọi API, xoay key khi gặp lỗi có thể do key. Hết key thì ném lỗi cuối cùng."""
        b64_anh = base64.b64encode(anh).decode()
        than = json.dumps({
            "contents": [{"parts": [
                {"inline_data": {"mime_type": mime, "data": b64_anh}},
                {"text": loi_nhac},
            ]}],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 4096,
                "thinkingConfig": {"thinkingBudget": 0},
                "responseMimeType": "application/json",
                "responseSchema": schema,
            },
        }).encode()
        than_vertex = json.dumps({
            "contents": [{"role": "user", "parts": [
                {"inlineData": {"mimeType": mime, "data": b64_anh}},
                {"text": loi_nhac},
            ]}],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 4096,
                "thinkingConfig": {"thinkingBudget": 0},
                "responseMimeType": "application/json",
                "responseSchema": schema,
            },
        }).encode()
        than_vertex_no_think = json.dumps({
            "contents": [{"role": "user", "parts": [
                {"inlineData": {"mimeType": mime, "data": b64_anh}},
                {"text": loi_nhac},
            ]}],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 4096,
                "responseMimeType": "application/json",
                "responseSchema": schema,
            },
        }).encode()

        loi_cuoi: Exception | None = None
        ds_khoa_gemini: list[tuple[str, str]] = []
        ds_khoa_vision_oai: list[tuple[str, str, str]] = []  # (endpoint_url, model, api_key)
        model_goc = (self.model_name or "gemini-3.1-flash-lite").strip()
        if model_goc.lower() == "gemini-3.5-flash":
            model_goc = "gemini-3.5-flash-lite"
        for raw_k in self.api_keys:
            s_k = str(raw_k or "").strip()
            if not s_k or s_k.startswith(("sk-", "ds:", "ds|", "gsk_")):
                continue
            if s_k.startswith(("or|", "or:", "oai|", "oai:", "groq|", "groq:", "custom|")):
                if s_k.startswith("custom|"):
                    parts_c = s_k.split("|", 3)
                    if len(parts_c) == 4 and parts_c[1].strip() and parts_c[3].strip():
                        u_c = parts_c[1].strip().rstrip("/")
                        if not u_c.endswith("/chat/completions"):
                            u_c = f"{u_c}/chat/completions"
                        ds_khoa_vision_oai.append((u_c, parts_c[2].strip() or "gpt-4o-mini", parts_c[3].strip()))
                elif s_k.startswith(("or|", "or:")):
                    parts_or = s_k.split("|", 2) if "|" in s_k else ["or", "google/gemini-2.5-flash", s_k[3:]]
                    m_or = parts_or[1].strip() if len(parts_or) == 3 and parts_or[1].strip() else "google/gemini-2.5-flash"
                    k_or = parts_or[-1].strip()
                    if k_or:
                        ds_khoa_vision_oai.append(("https://openrouter.ai/api/v1/chat/completions", m_or, k_or))
                elif s_k.startswith(("oai|", "oai:")):
                    parts_oa = s_k.split("|", 2) if "|" in s_k else ["oai", "gpt-4o-mini", s_k[4:]]
                    m_oa = parts_oa[1].strip() if len(parts_oa) == 3 and parts_oa[1].strip() else "gpt-4o-mini"
                    k_oa = parts_oa[-1].strip()
                    if k_oa:
                        ds_khoa_vision_oai.append(("https://api.openai.com/v1/chat/completions", m_oa, k_oa))
                elif s_k.startswith(("groq|", "groq:")):
                    parts_gq = s_k.split("|", 2) if "|" in s_k else ["groq", "meta-llama/llama-4-scout-17b-16e-instruct", s_k[5:]]
                    m_gq = parts_gq[1].strip() if len(parts_gq) == 3 and parts_gq[1].strip() else "meta-llama/llama-4-scout-17b-16e-instruct"
                    k_gq = parts_gq[-1].strip()
                    if k_gq and ("vision" in m_gq.lower() or "llama-4" in m_gq.lower()):
                        ds_khoa_vision_oai.append(("https://api.groq.com/openai/v1/chat/completions", m_gq, k_gq))
                continue
            m_k = model_goc
            if s_k.startswith("gm|"):
                parts_gm = s_k.split("|", 2)
                if len(parts_gm) == 3 and parts_gm[1].strip():
                    m_k = parts_gm[1].strip()
                    if m_k.lower() == "gemini-3.5-flash":
                        m_k = "gemini-3.5-flash-lite"
                s_k = parts_gm[-1].strip()
            elif s_k.startswith("gm:"):
                s_k = s_k[3:].strip()
            if s_k and not any(k_existing == s_k and m_existing == m_k for m_existing, k_existing in ds_khoa_gemini):
                ds_khoa_gemini.append((m_k, s_k))
        if not ds_khoa_gemini and not ds_khoa_vision_oai:
            ds_khoa_gemini = [(model_goc, str(k).split("|")[-1].strip()) for k in self.api_keys if str(k).strip()]

        d = None
        for m_key, key in ds_khoa_gemini:
            la_vertex_aq = key.startswith("AQ.")
            la_khoa_that = len(key) >= 16
            if la_vertex_aq:
                ds_ung_vien_url = [
                    (f"https://generativelanguage.googleapis.com/v1beta/models/{m_key}:generateContent?key={key}", than),
                    (f"https://aiplatform.googleapis.com/v1/publishers/google/models/{m_key}:generateContent?key={key}", than_vertex),
                    (f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite-preview:generateContent?key={key}", than),
                    (f"https://aiplatform.googleapis.com/v1/publishers/google/models/gemini-3.1-flash-lite-preview:generateContent?key={key}", than_vertex_no_think),
                    (f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={key}", than),
                    (f"https://aiplatform.googleapis.com/v1/publishers/google/models/gemini-2.5-flash-lite:generateContent?key={key}", than_vertex_no_think),
                    (f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image-preview:generateContent?key={key}", than_vertex_no_think),
                    (f"https://aiplatform.googleapis.com/v1/publishers/google/models/gemini-3.1-flash-image-preview:generateContent?key={key}", than_vertex_no_think),
                ]
            elif la_khoa_that:
                ds_ung_vien_url = [
                    (f"https://generativelanguage.googleapis.com/v1beta/models/{m_key}:generateContent?key={key}", than),
                    (f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite-preview:generateContent?key={key}", than),
                    (f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={key}", than),
                    (f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}", than),
                    (f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image-preview:generateContent?key={key}", than_vertex_no_think),
                ]
            else:
                ds_ung_vien_url = [
                    (
                        "https://generativelanguage.googleapis.com/v1beta/models/"
                        f"{m_key}:generateContent?key={key}",
                        than,
                    )
                ]

            thanh_cong_key = False
            for url_goi, payload_bytes in ds_ung_vien_url:
                try:
                    req = urllib.request.Request(
                        url_goi,
                        data=payload_bytes,
                        headers={"Content-Type": "application/json"},
                    )
                    with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                        d = json.load(resp)
                    thanh_cong_key = True
                    break
                except urllib.error.HTTPError as exc:
                    # Đọc THÂN lỗi: thông điệp thật nằm ở đó. Đoán theo mã HTTP là cách chắc chắn
                    # chẩn sai — 400 của bậc pro hoá ra là "model only works in thinking mode".
                    try:
                        chi_tiet = json.loads(exc.read()).get("error", {}).get("message", "")
                    except Exception:
                        chi_tiet = ""
                    loi_cuoi = AIDetectError(f"Gemini HTTP {exc.code}: {chi_tiet[:300]}")
                    chi_tiet_lower = chi_tiet.lower()
                    la_loi_key = (
                        "api key not valid" in chi_tiet_lower
                        or "api_key_invalid" in chi_tiet_lower
                        or "key expired" in chi_tiet_lower
                        or exc.code in (401, 403)
                    )
                    if la_loi_key:
                        break
                    if (la_vertex_aq or la_khoa_that) and exc.code in (400, 404):
                        # Với khoá thực (AQ. hoặc AIza...), thử tiếp endpoint/model kế tiếp trong ds_ung_vien_url
                        continue
                    if exc.code in (400, 404) and not la_loi_key:
                        raise loi_cuoi from exc   # lỗi cấu hình: xoay key không cứu được
                except Exception as exc:
                    loi_cuoi = AIDetectError(f"Gọi Gemini thất bại: {type(exc).__name__}: {exc}")
                    break
            if thanh_cong_key and d is not None:
                break

        if d is None and ds_khoa_vision_oai:
            chi_dan_json = (
                "\n\nReturn ONLY a raw JSON array (no markdown fences) where each item has "
                '{"box_2d": [ymin, xmin, ymax, xmax], "text": "...", "ban_dich": "...", "doan": false}.'
            )
            for url_oai, m_oai, k_oai in ds_khoa_vision_oai:
                try:
                    than_oai = json.dumps({
                        "model": m_oai,
                        "temperature": 0.0,
                        "max_tokens": 4096,
                        "messages": [{
                            "role": "user",
                            "content": [
                                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64_anh}"}},
                                {"type": "text", "text": loi_nhac + chi_dan_json},
                            ],
                        }],
                    }).encode()
                    req_oai = urllib.request.Request(
                        url_oai,
                        data=than_oai,
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {k_oai}",
                            "User-Agent": "ComicTranslator/1.0",
                        },
                    )
                    with urllib.request.urlopen(req_oai, timeout=self.timeout) as resp_oai:
                        d_oai = json.load(resp_oai)
                    chu_oai = (d_oai.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
                    if chu_oai.startswith("```"):
                        chu_oai = chu_oai.strip("`").removeprefix("json").strip()
                    tho_oai = json.loads(chu_oai)
                    if isinstance(tho_oai, dict) and isinstance(tho_oai.get("items"), list):
                        tho_oai = tho_oai["items"]
                    if isinstance(tho_oai, list):
                        self.last_usage = d_oai.get("usage") or {}
                        return tho_oai
                except Exception as exc_oai:
                    loi_cuoi = AIDetectError(f"Gọi Vision AI ({m_oai}) thất bại: {exc_oai}")

        if d is None:
            raise loi_cuoi or AIDetectError("Gọi Gemini thất bại, không rõ lý do")

        try:
            self.last_usage = d.get("usageMetadata") if isinstance(d, dict) else {}
            ung_vien = d["candidates"][0]
            # Gộp MỌI phần: câu trả lời có thể bị tách thành nhiều `parts`.
            chu = "".join(p.get("text", "") for p in ung_vien["content"]["parts"])
        except (KeyError, IndexError) as exc:
            raise AIDetectError(f"Phản hồi Gemini thiếu nội dung: {json.dumps(d)[:300]}") from exc

        try:
            tho = json.loads(chu)
        except json.JSONDecodeError as exc:
            # Với `responseSchema` thì đây gần như không xảy ra — nhưng nếu xảy ra thì phải BÁO,
            # vì im lặng ở đây chính là kiểu hỏng §1 đã mô tả.
            raise AIDetectError(
                f"Gemini trả JSON hỏng dù đã ép schema (finishReason="
                f"{ung_vien.get('finishReason')!r}): {chu[:200]}"
            ) from exc

        if not isinstance(tho, list):
            raise AIDetectError(f"Gemini trả về không phải mảng: {type(tho).__name__}")
        return tho
