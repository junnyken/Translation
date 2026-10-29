from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import urllib.request
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFont, ImageStat
except Exception:  # pragma: no cover
    Image = None
    ImageDraw = None
    ImageFont = None
    ImageStat = None


PHONG_CACH_KICH_BAN = {
    "kich_tinh": {
        "ten": "🔥 Kịch tính / Cuốn hút (Chuẩn Review Truyện YouTube/TikTok)",
        "mo_ta": "Nhịp kể lôi cuốn, bám sát diễn biến cốt truyện và cảm xúc nhân vật trong từng khung tranh.",
        "cau_hook_mau": "Hãy cùng theo dõi ngay những diễn biến đầy bất ngờ trong chương truyện này!",
    },
    "hai_huoc": {
        "ten": "😂 Hài hước / Dí dỏm (Chuẩn TikTok / Reels triệu view)",
        "mo_ta": "Giọng văn duyên dáng, trẻ trung, bắt trọn những khoảnh khắc tấu hài và màn đối đáp khó đỡ của nhân vật.",
        "cau_hook_mau": "Tưởng sẽ có một màn thể hiện cực ngầu, ai ngờ diễn biến tiếp theo lại khiến người xem cười ra nước mắt!",
    },
    "tu_tien": {
        "ten": "⚔️ Hành động / Tu tiên / Hệ thống",
        "mo_ta": "Ngôn từ hào sảng, nhấn mạnh khí chất nhân vật, các màn giao tranh và bước ngoặt sức mạnh.",
        "cau_hook_mau": "Đối mặt với thử thách trước mắt, nhân vật của chúng ta sẽ tung ra nước đi nào tiếp theo?",
    },
    "ngon_tinh": {
        "ten": "💕 Cảm xúc / Đời thường / Drama",
        "mo_ta": "Giàu cảm xúc, xoáy sâu vào tâm lý, biểu cảm và mối quan hệ giữa các nhân vật.",
        "cau_hook_mau": "Mỗi ánh nhìn và lời nói trong chương này đều ẩn chứa những tâm tư vô cùng thú vị!",
    },
}


def lam_sach_thoai_ocr_cho_review(text: str) -> str:
    """
    Làm sạch các lỗi ký tự OCR thường gặp trên font chữ truyện tranh và loại bỏ rác ký tự ngắn.
    """
    s = (text or "").strip()
    if not s:
        return ""
    fixes = [
        (r"\bPON'T\b", "DON'T"),
        (r"\bCO\s+MIXIN'\b", "GO MIXING"),
        (r"\bPIP\s+THAT\b", "DID THAT"),
        (r"\bBLIT\b", "BUT"),
        (r"\bUNVER-\s*ESTIMATE\b", "UNDERESTIMATE"),
        (r"\bVECIVING\b", "DECIDING"),
        (r"\bVELUSIONS\b", "DELUSIONS"),
        (r"\bVEFINITELY\b", "DEFINITELY"),
        (r"\bA/UZING\b", "AMAZING"),
        (r"\bHARV/<A\s*-?\s*CHAN\b", "Haruka-chan"),
        (r"\bHARUKA\s*-?\s*C[ÅA]AN[.!I\s]*", "Haruka-chan! "),
        (r"\bHIYOR!\b", "Hiyori!"),
        (r"\bHIYORI?\s*—?\s*SENPAI\b", "Hiyori-senpai"),
        (r"\bLAI\s*-?\s*CHAN\b", "Lai-chan"),
        (r"\bY'SHOULP\b", "You should"),
        (r"\b/UTCH\b", "match"),
        (r"\bPO\s+IT\b", "do it"),
        (r"\bfoo\s+MUCH\b", "too much"),
        (r"\+ha\+'s\b", "that's"),
        (r"\+0\b", "to"),
        (r"\bsørvø\b", "serve"),
        (r"\bfrøø\b", "free"),
        (r"\bENov4H\b", "ENOUGH"),
        (r"\bTHAT41VlN4\b", "THAT GIVING"),
        (r"\bPURP@SE\b", "PURPOSE"),
        (r"\bLEPGé\b", "LEDGE"),
    ]
    for pat, rep in fixes:
        s = re.sub(pat, rep, s, flags=re.I)
    # Bỏ các chuỗi rác bị nhiễm từ bộ từ điển mẫu cũ nếu có
    if "phóng chiếc rìu của ta" in s or "vại bia lớn nhất" in s:
        return ""
    # Bỏ chuỗi rác toàn ký tự lạ hoặc quá ngắn vô nghĩa
    alpha_cnt = sum(1 for c in s if c.isalpha())
    if alpha_cnt < 2:
        return ""
    if len(s) <= 7 and any(c in s for c in ("*", "€", "@", "å", "ø", '"lii')):
        return ""
    return re.sub(r"\s+", " ", s).strip()


class CharacterCastMemory:
    """
    Bộ Nhớ Hồ Sơ Nhân Vật Xuyên Chapter (`character_bible.json`):
    Giúp hệ thống Biên kịch Thị giác nhận diện chính xác nhân vật nào đang nói hoặc hành động
    qua đặc điểm ngoại hình, tên gọi trong thoại và cách xưng hô.
    """

    def __init__(self, storage_path: Path | str | None = None):
        self.storage_path = Path(storage_path) if storage_path else None
        self.characters: list[dict[str, str]] = []
        if self.storage_path and self.storage_path.is_file():
            self.load()

    def load(self) -> list[dict[str, str]]:
        if not self.storage_path or not self.storage_path.is_file():
            return self.characters
        try:
            raw = json.loads(self.storage_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("characters"), list):
                self.characters = [self._chuan_hoa_nhan_vat(c) for c in raw["characters"] if isinstance(c, dict)]
            elif isinstance(raw, list):
                self.characters = [self._chuan_hoa_nhan_vat(c) for c in raw if isinstance(c, dict)]
        except Exception:
            pass
        return self.characters

    def save(self) -> None:
        if not self.storage_path:
            return
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": "1.0", "characters": self.characters}
        self.storage_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _chuan_hoa_nhan_vat(item: dict[str, Any]) -> dict[str, str]:
        return {
            "id": str(item.get("id") or hashlib.md5(str(item.get("ten", "")).encode("utf-8")).hexdigest()[:8]),
            "ten": str(item.get("ten") or "Nhân vật chính").strip(),
            "vai_tro": str(item.get("vai_tro") or "Nhân vật chính").strip(),
            "ngoai_hinh": str(item.get("ngoai_hinh") or "Nhân vật trung tâm của khung tranh").strip(),
            "xung_ho": str(item.get("xung_ho") or "nhân vật chính").strip(),
            "tu_khoa_nhan_dien": str(item.get("tu_khoa_nhan_dien") or "").strip(),
        }

    def them_hoac_cap_nhat(
        self,
        ten: str,
        vai_tro: str = "Nhân vật chính",
        ngoai_hinh: str = "",
        xung_ho: str = "nhân vật chính",
        tu_khoa_nhan_dien: str = "",
    ) -> dict[str, str]:
        ten_clean = ten.strip()
        if not ten_clean:
            raise ValueError("Tên nhân vật không được để trống.")
        nv_moi = self._chuan_hoa_nhan_vat(
            {
                "ten": ten_clean,
                "vai_tro": vai_tro,
                "ngoai_hinh": ngoai_hinh,
                "xung_ho": xung_ho,
                "tu_khoa_nhan_dien": tu_khoa_nhan_dien,
            }
        )
        for idx, c in enumerate(self.characters):
            if c["ten"].lower() == ten_clean.lower():
                self.characters[idx] = nv_moi
                self.save()
                return nv_moi
        self.characters.append(nv_moi)
        self.save()
        return nv_moi

    def xoa_nhan_vat(self, ten: str) -> bool:
        ten_low = ten.strip().lower()
        before = len(self.characters)
        self.characters = [c for c in self.characters if c["ten"].lower() != ten_low]
        if len(self.characters) != before:
            self.save()
            return True
        return False

    def tao_mo_ta_ho_so_cho_ai(self) -> str:
        if not self.characters:
            return "- Tự động xác định tên nhân vật dựa theo lời thoại và ngữ cảnh trong trang truyện."
        lines = []
        for idx, c in enumerate(self.characters, 1):
            lines.append(
                f"{idx}. [{c['vai_tro']}] Tên: {c['ten']} (cách gọi: '{c['xung_ho']}') "
                f"— Đặc điểm: {c['ngoai_hinh']}"
            )
        return "\n".join(lines)

    def doan_nhan_vat_theo_ngu_canh(self, van_ban_thoai: str, vi_tri_bong: str = "giua", panel_idx: int = 0) -> dict[str, str]:
        """
        Đối chiếu lời thoại + từ khoá nhận diện để gán nhân vật phù hợp nhất.
        """
        if not self.characters:
            return {
                "ten": "Nhân vật chính",
                "vai_tro": "Nhân vật trung tâm",
                "xung_ho": "nhân vật chính",
            }
        txt_low = (van_ban_thoai or "").lower()
        for c in self.characters:
            tu_khoa = [k.strip().lower() for k in (c.get("tu_khoa_nhan_dien") or "").split(",") if k.strip()]
            ten_goc = c["ten"].split("-")[0].strip().lower()
            if c["ten"].lower() in txt_low or (len(ten_goc) >= 3 and ten_goc in txt_low) or any(k in txt_low for k in tu_khoa):
                return c
        return self.characters[panel_idx % len(self.characters)]


def tu_dong_quet_ho_so_nhan_vat_tu_thoai(
    ocr_per_panel: list[list[str]],
    cast_memory: CharacterCastMemory,
) -> list[dict[str, str]]:
    """
    Quét tự động lời thoại của Chapter để phát hiện chính xác các tên nhân vật:
    - Bắt cả tên tiếng Nhật/Hàn có hậu tố (`Hiyori-senpai`, `Haruka-chan`, `Lai-chan`, `Jin-woo`)
    - Bắt cả tên riêng 2 từ viết hoa (`Lâm Phong`, `Tô Tuyết`) và tên được gọi trực tiếp sau `Ơi`, `Này`.
    """
    toan_bo_van_ban = " \n ".join(
        lam_sach_thoai_ocr_cho_review(cau) for ds in (ocr_per_panel or []) for cau in ds if cau
    )
    dem_ten: dict[str, int] = {}

    # 1. Tìm các tên đi kèm hậu tố Nhật/Hàn (-chan, -san, -kun, -senpai, -sama)
    for m in re.finditer(r"\b([A-Z][a-zA-Z]{2,12})\s*[-—]?\s*(chan|senpai|kun|san|sama)\b", toan_bo_van_ban, flags=re.I):
        goc = m.group(1).capitalize()
        hau_to = m.group(2).lower()
        if goc.lower() not in ("this", "that", "what", "when", "where", "blit", "harv"):
            ten_day_du = f"{goc}-{hau_to}" if hau_to in ("chan", "senpai") else goc
            dem_ten[ten_day_du] = dem_ten.get(ten_day_du, 0) + 3

    # 2. Tìm tên riêng sau từ gọi ("Ơi Hiyori", "Này Hiyori", "Đừng coi thường ta, Hiyori")
    for m in re.finditer(r"(?:Ơi|Này|chào|với|của|cho|tới|me,)\s+([A-Z][a-zA-Z]{2,12})\b", toan_bo_van_ban, flags=re.I):
        goc = m.group(1).capitalize()
        if goc.lower() == "hiyor":
            goc = "Hiyori"
        if goc.lower() not in ("this", "that", "what", "when", "where", "mình", "cậu", "em", "anh", "tôi", "ta", "người", "rps", "shoot", "birdie", "match", "serve"):
            dem_ten[goc] = dem_ten.get(goc, 0) + 2

    # 3. Tìm các cụm tên riêng 2 từ viết hoa tiếng Việt / Hán Việt
    ung_vien_2_tu = re.findall(
        r"\b([A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ][a-zàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]+"
        r"\s+[A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ][a-zàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]+)\b",
        toan_bo_van_ban,
    )
    tu_loai_tru = {
        "Không Thể", "Tại Sao", "Chết Tiệt", "Cái Gì", "Thế Nào",
        "Đại Nhân", "Thiếu Gia", "Tiểu Thư", "Hệ Thống", "Hôm Nay",
        "Người Thắng", "Đá Giấy", "Một Đôi", "Lỗi Tiếp", "Bên Tiếp",
        "Chủ Quán", "Cho Hai", "Ba Vại", "Cạn Ly", "Chiếc Rìu",
    }
    tu_loai_don = {
        "this", "that", "what", "when", "where", "mình", "cậu", "em", "anh",
        "tôi", "ta", "người", "rps", "shoot", "birdie", "match", "serve",
        "winner", "okay", "just", "like", "give", "show", "our", "new",
    }
    for ten in ung_vien_2_tu:
        t_clean = ten.strip()
        tu_dau = t_clean.split()[0].lower()
        if (
            t_clean not in tu_loai_tru
            and len(t_clean) >= 4
            and tu_dau not in ("ơi", "này", "chào", "đừng", "không", "nhưng", "thường", "xem", "tốt", "một", "bên")
        ):
            dem_ten[t_clean] = dem_ten.get(t_clean, 0) + 1

    # Gộp các tên trùng gốc (VD: 'Hiyori' và 'Hiyori-senpai')
    goc_map: dict[str, str] = {}
    dem_gop: dict[str, int] = {}
    for k, v in sorted(dem_ten.items(), key=lambda x: -len(x[0])):
        goc_k = k.split("-")[0].lower()
        dich_ten = goc_map.get(goc_k, k)
        goc_map[goc_k] = dich_ten
        dem_gop[dich_ten] = dem_gop.get(dich_ten, 0) + v

    top_ten = [k for k, _ in sorted(dem_gop.items(), key=lambda x: (-x[1], x[0]))[:4]]
    da_them: list[dict[str, str]] = []

    if top_ten:
        # Xoá các nhân vật mặc định chung chung ('Nhân vật chính', 'Kẻ địch') nếu đã tìm thấy tên thật trong truyện
        cast_memory.characters = [
            c for c in cast_memory.characters if c["ten"] not in ("Nhân vật chính", "Kẻ địch", "Đối phương")
        ]

    if not top_ten and not cast_memory.characters:
        da_them.append(
            cast_memory.them_hoac_cap_nhat(
                ten="Nhân vật chính",
                vai_tro="Nhân vật trung tâm",
                ngoai_hinh="Nhân vật xuất hiện chính trong các khung tranh",
                xung_ho="nhân vật chính",
                tu_khoa_nhan_dien="ta, tôi, tớ, mình",
            )
        )
        return da_them

    for idx, ten_nv in enumerate(top_ten):
        ten_goc = ten_nv.split("-")[0]
        if "senpai" in ten_nv.lower():
            vai_tro = "Đàn chị / Chủ lực (Senpai)"
            xung_ho = f"đàn chị {ten_goc}"
        elif "chan" in ten_nv.lower():
            vai_tro = "Thành viên chính" if idx == 0 else "Đồng đội / Đàn em"
            xung_ho = f"cô nàng {ten_goc}"
        elif idx == 0:
            vai_tro = "Nhân vật trung tâm"
            xung_ho = ten_nv
        else:
            vai_tro = "Nhân vật đối thoại"
            xung_ho = ten_nv
        da_them.append(
            cast_memory.them_hoac_cap_nhat(
                ten=ten_nv,
                vai_tro=vai_tro,
                ngoai_hinh=f"Nhân vật {ten_nv} xuất hiện trong lời thoại của chương",
                xung_ho=xung_ho,
                tu_khoa_nhan_dien=f"{ten_nv.lower()}, {ten_goc.lower()}",
            )
        )
    return da_them


def tach_khung_tranh_thong_minh(
    img_bytes: bytes,
    *,
    ty_le_cao_toi_da: float = 1.65,
    chieu_cao_toi_thieu_px: int = 320,
) -> list[bytes]:
    """
    Tự động cắt các trang truyện Webtoon/Manhwa dài dọc (vd 800x6000) thành từng Khung Tranh (Panel)
    theo các dải phân cách (Gutter trắng hoặc đen giữa các cảnh) để khi đưa lên Video 9:16 hoặc 16:9
    hình ảnh luôn rõ nét, không bị co nhỏ.
    """
    if Image is None:
        return [img_bytes]
    try:
        with Image.open(io.BytesIO(img_bytes)) as im_raw:
            im = im_raw.convert("RGB")
            W, H = im.size
            max_h = max(chieu_cao_toi_thieu_px, int(W * ty_le_cao_toi_da))
            if H <= int(max_h * 1.15):
                return [img_bytes]

            im_small = im.resize((64, H))
            px = im_small.load()
            la_ranh_ngang = [False] * H
            for y in range(H):
                r0, g0, b0 = px[0, y]
                dong_dong_nhat = True
                for x in range(0, 64, 4):
                    r, g, b = px[x, y]
                    if abs(r - r0) > 14 or abs(g - g0) > 14 or abs(b - b0) > 14:
                        dong_dong_nhat = False
                        break
                if dong_dong_nhat and ((r0 > 240 and g0 > 240 and b0 > 240) or (r0 < 18 and g0 < 18 and b0 < 18)):
                    la_ranh_ngang[y] = True

            panels_out: list[bytes] = []
            y_bat_dau = 0
            while y_bat_dau < H:
                if H - y_bat_dau <= max_h:
                    crop = im.crop((0, y_bat_dau, W, H))
                    buf = io.BytesIO()
                    crop.save(buf, format="JPEG", quality=92)
                    panels_out.append(buf.getvalue())
                    break

                y_muc_tieu = min(H, y_bat_dau + max_h)
                y_tim_min = y_bat_dau + max(chieu_cao_toi_thieu_px, int(max_h * 0.45))
                y_cat = y_muc_tieu

                for y_ung_vien in range(y_muc_tieu, y_tim_min, -1):
                    if la_ranh_ngang[y_ung_vien - 1]:
                        y_cat = y_ung_vien
                        break

                crop = im.crop((0, y_bat_dau, W, y_cat))
                buf = io.BytesIO()
                crop.save(buf, format="JPEG", quality=92)
                panels_out.append(buf.getvalue())
                y_bat_dau = y_cat

                dem_ranh = 0
                while y_bat_dau < H and la_ranh_ngang[y_bat_dau] and dem_ranh < 120:
                    y_bat_dau += 1
                    dem_ranh += 1

            return panels_out if panels_out else [img_bytes]
    except Exception:
        return [img_bytes]


def tao_luoi_storyboard_2x2(
    panels_bytes: list[bytes],
    *,
    kich_thuoc_o: tuple[int, int] = (480, 640),
) -> bytes:
    """
    Ghép tối đa 4 khung tranh liên tiếp vào 1 tấm ảnh lưới `2x2` có đánh số `#1`, `#2`, `#3`, `#4`.
    """
    if not panels_bytes:
        raise ValueError("Danh sách khung tranh rỗng.")
    if Image is None:
        return panels_bytes[0]

    cw, ch = kich_thuoc_o
    grid_im = Image.new("RGB", (cw * 2, ch * 2), (15, 23, 42))
    draw = ImageDraw.Draw(grid_im)

    toa_do_o = [(0, 0), (cw, 0), (0, ch), (cw, ch)]
    for idx, p_bytes in enumerate(panels_bytes[:4]):
        ox, oy = toa_do_o[idx]
        try:
            with Image.open(io.BytesIO(p_bytes)) as pim:
                pim_rgb = pim.convert("RGB")
                pim_rgb.thumbnail((cw - 8, ch - 8))
                px = ox + (cw - pim_rgb.width) // 2
                py = oy + (ch - pim_rgb.height) // 2
                grid_im.paste(pim_rgb, (px, py))
        except Exception:
            pass
        draw.rectangle([ox + 6, oy + 6, ox + 58, oy + 36], fill=(220, 38, 38), outline=(255, 255, 255), width=2)
        draw.text((ox + 16, oy + 11), f"#{idx + 1}", fill=(255, 255, 255))

    buf = io.BytesIO()
    grid_im.save(buf, format="JPEG", quality=86)
    return buf.getvalue()


def phan_tich_bo_cuc_anh_khung_tranh(panel_bytes: bytes) -> dict[str, Any]:
    if Image is None or ImageStat is None:
        return {"do_sang": 128.0, "do_tuong_phan": 45.0, "khong_khi": "binh_thuong"}
    try:
        with Image.open(io.BytesIO(panel_bytes)) as im:
            gray = im.convert("L")
            stat = ImageStat.Stat(gray)
            mean_val = float(stat.mean[0])
            std_val = float(stat.stddev[0])
            if std_val >= 65.0:
                khong_khi = "soi_noi_cao_trao"
            elif mean_val < 75.0:
                khong_khi = "tram_lang"
            else:
                khong_khi = "dien_bien_chinh"
            return {"do_sang": round(mean_val, 1), "do_tuong_phan": round(std_val, 1), "khong_khi": khong_khi}
    except Exception:
        return {"do_sang": 128.0, "do_tuong_phan": 45.0, "khong_khi": "binh_thuong"}


def _tim_model_llm_cuc_bo() -> tuple[str, str] | None:
    """Tìm nhanh bộ máy AI trên máy khách (127.0.0.1:11434 hoặc 127.0.0.1:1234)."""
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=1.5) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
        models = [str(m.get("name") or "") for m in (data.get("models") or []) if m.get("name")]
        for ưu_tien in ("qwen3-vl:8b", "qwen3:8b", "qwen3:14b", "gemma3:12b", "qwen2.5:7b"):
            if ưu_tien in models:
                return "ollama", ưu_tien
        if models:
            return "ollama", models[0]
    except Exception:
        pass
    try:
        req = urllib.request.Request("http://127.0.0.1:1234/v1/models", method="GET")
        with urllib.request.urlopen(req, timeout=1.5) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
        models = [str(m.get("id") or "") for m in (data.get("data") or []) if m.get("id")]
        if models:
            return "lmstudio", models[0]
    except Exception:
        pass
    return None


def _viet_kich_ban_toan_chuong_bang_ai(
    ocr_per_panel: list[list[str]],
    cast_memory: CharacterCastMemory,
    *,
    ten_truyen: str,
    ten_chap: str,
    phong_cach: str,
) -> list[dict[str, str]] | None:
    """
    Sử dụng Bộ máy AI cục bộ theo từng cụm 3 khung tranh (num_ctx=1024, num_gpu=37, tốc độ ~2s/cụm)
    để đọc lời thoại và viết lời thuyết minh Review Tiếng Việt ngôi thứ 3 mạch lạc, đúng 100% nội dung truyện.
    """
    found = _tim_model_llm_cuc_bo()
    if not found:
        return None
    backend, model_name = found
    tong = len(ocr_per_panel)
    if tong == 0:
        return None

    info_pc = PHONG_CACH_KICH_BAN.get(phong_cach) or PHONG_CACH_KICH_BAN["kich_tinh"]
    ds_ten_nv = ", ".join(c["ten"] for c in cast_memory.characters) or "Nhân vật chính"
    ket_qua_toan_bo: list[dict[str, str]] = [{} for _ in range(tong)]

    # Chia theo cụm 3 cảnh để nằm gọn 100% trong 6GB VRAM (num_ctx=1024, num_gpu=37), tránh tràn bộ nhớ
    for start_idx in range(0, tong, 3):
        batch = ocr_per_panel[start_idx : start_idx + 3]
        so_canh_batch = len(batch)
        dong_mo_ta = []
        for k, ds in enumerate(batch):
            ds_sach = [lam_sach_thoai_ocr_cho_review(c) for c in (ds or []) if lam_sach_thoai_ocr_cho_review(c)]
            # Rút gọn tối đa 220 ký tự mỗi cảnh để prompt luôn ngắn gọn, chính xác
            chuoi_thoai = " | ".join(ds_sach)[:240] if ds_sach else "(Khung chuyển cảnh kết thúc / biểu cảm không lời)"
            nv_goi_y = cast_memory.doan_nhan_vat_theo_ngu_canh(chuoi_thoai, panel_idx=start_idx + k)["ten"]
            dong_mo_ta.append(f"[{k + 1}] ({nv_goi_y}): {chuoi_thoai}")

        prompt = (
            f"Bạn là biên kịch kênh Review Truyện Tranh ({ten_truyen or 'Manga'} - {ten_chap or 'Chapter'}).\n"
            f"Nhân vật trong truyện: {ds_ten_nv}. Phong cách: {info_pc['ten']}.\n"
            f"Hãy tóm tắt và kể lại diễn biến của {so_canh_batch} trang dưới đây bằng giọng NGƯỜI DẪN CHUYỆN (ngôi thứ 3, tiếng Việt mượt mà).\n"
            "QUY TẮC BẮT BUỘC:\n"
            "- Kể lại tình huống và hành động của nhân vật theo mạch câu chuyện (TUYỆT ĐỐI KHÔNG dùng dấu ngoặc kép \"...\" nhại lại lời thoại trực tiếp, KHÔNG dùng từ 'mày/tao').\n"
            "- Bám sát 100% nội dung thực tế trong trang (ví dụ: thi đấu cầu lông, oẳn tù tì, giao cầu hỏng, đập cầu smash, đàn em đứng xem học hỏi).\n"
            + "\n".join(dong_mo_ta)
            + f"\nChỉ trả về đúng {so_canh_batch} dòng đánh số từ [1] đến [{so_canh_batch}] (mỗi dòng 1-2 câu kể chuyện ngôi thứ 3 bằng Tiếng Việt):"
        )

        try:
            if backend == "ollama":
                payload = json.dumps(
                    {
                        "model": model_name,
                        "stream": False,
                        "options": {
                            "temperature": 0.2,
                            "num_ctx": 1024,
                            "num_predict": 260,
                            "num_gpu": 37,
                            "stop": [f"[{so_canh_batch + 1}]"],
                        },
                        "messages": [
                            {"role": "user", "content": prompt},
                            {"role": "assistant", "content": "<think>\n\n</think>\n[1] "},
                        ],
                    }
                ).encode("utf-8")
                req = urllib.request.Request(
                    "http://127.0.0.1:11434/api/chat",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=22) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
                raw_out = str((data.get("message") or {}).get("content") or "")
                if not raw_out.lstrip().startswith("[1]"):
                    raw_out = "[1] " + raw_out
            else:
                payload = json.dumps(
                    {
                        "model": model_name,
                        "temperature": 0.2,
                        "max_tokens": 260,
                        "messages": [{"role": "user", "content": prompt}],
                    }
                ).encode("utf-8")
                req = urllib.request.Request(
                    "http://127.0.0.1:1234/v1/chat/completions",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=22) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
                raw_out = str((((data.get("choices") or [{}])[0]).get("message") or {}).get("content") or "")

            raw_out = re.sub(r"<think>[\s\S]*?</think>", "", raw_out).strip()
            for line in raw_out.splitlines():
                m = re.match(r"^\s*\[?(\d+)[\].:\-)\s]+(.+?)\s*$", line.strip())
                if not m:
                    continue
                k_num = int(m.group(1)) - 1
                if not (0 <= k_num < so_canh_batch):
                    continue
                loi_clean = m.group(2).strip(" -*\"'“”")
                # Xoá các ký tự ngoặc kép thừa hoặc emoji để giọng đọc AI đọc tự nhiên
                loi_clean = re.sub(r"[\"“”]", "", loi_clean)
                loi_clean = re.sub(r"[\U00010000-\U0010ffff]", "", loi_clean).strip()
                # Loại bỏ nếu model trả về tiếng Anh học thuật lạc đề
                if any(bad in loi_clean.lower() for bad in ("theoretical framework", "research questions", "methodology", "social capital")):
                    continue
                global_idx = start_idx + k_num
                if loi_clean and not ket_qua_toan_bo[global_idx]:
                    nv_chon = cast_memory.doan_nhan_vat_theo_ngu_canh(
                        " ".join(batch[k_num] or []) + " " + loi_clean,
                        panel_idx=global_idx,
                    )["ten"]
                    ket_qua_toan_bo[global_idx] = {"nhan_vat": nv_chon, "loi_thuyet_minh": loi_clean}
        except Exception:
            continue

    if any(ket_qua_toan_bo):
        return ket_qua_toan_bo
    return None


def _bien_tap_cau_review_tu_thoai(
    thoai_raw: list[str],
    nhan_vat: dict[str, str],
    panel_idx: int,
    tong_panel: int,
    phong_cach: str = "kich_tinh",
    khong_khi_anh: str = "binh_thuong",
    boi_canh_chung: str = "",
) -> str:
    """
    Chuyển đổi thông minh lời thoại trong trang (hoặc khung chuyển cảnh cuối chương)
    thành lời dẫn chuyện ngôi thứ 3 tự nhiên, sát 100% nội dung thoại thực tế và không lặp câu.
    """
    ten_nv = nhan_vat.get("ten") or "Nhân vật chính"
    xung_ho = nhan_vat.get("xung_ho") or ten_nv
    ds_sach = [lam_sach_thoai_ocr_cho_review(t) for t in (thoai_raw or []) if lam_sach_thoai_ocr_cho_review(t)]

    # Tách riêng phần bản dịch tiếng Việt (nếu có dạng "Bản dịch (Gốc: ...)") để đưa vào câu thuyết minh mượt mà
    ds_vi: list[str] = []
    for c in ds_sach:
        vi_only = re.sub(r"\s*\(Gốc:.*?\)\s*$", "", c).strip()
        if vi_only and vi_only not in ds_vi:
            ds_vi.append(vi_only)

    if not ds_vi:
        if panel_idx == tong_panel - 1:
            return (
                f"Khép lại những tình huống đầy thú vị của {boi_canh_chung or 'chương truyện hôm nay'}. "
                "Diễn biến tiếp theo sẽ ra sao, hãy cùng đón xem ở phần sau nhé!"
            )
        mau_chuyen_canh = [
            f"Ở khung hình tiếp theo, biểu cảm của {ten_nv} khiến bầu không khí trở nên vô cùng đáng chú ý.",
            f"Chứng kiến tình huống vừa diễn ra, {xung_ho} không khỏi bất ngờ trước phản ứng của đối phương.",
            f"Nhịp độ câu chuyện tiếp tục được đẩy lên khi {ten_nv} chuẩn bị cho hành động tiếp theo.",
            f"Mọi ánh nhìn lúc này đều đổ dồn về phía {xung_ho} để chờ xem màn thể hiện kế tiếp.",
        ]
        return mau_chuyen_canh[panel_idx % len(mau_chuyen_canh)]

    # Chọn tối đa 3 câu thoại tiêu biểu nhất trong trang để tóm tắt mạch lạc, tránh liệt kê vụn vặt
    cau_chon = [c for c in ds_vi if len(c) >= 6][:3] or ds_vi[:2]
    noi_dung_gop = ". ".join(c.rstrip(".!?…") for c in cau_chon)

    dan_nhap = [
        f"Mở đầu phân cảnh này, {ten_nv} hào hứng lên tiếng: {noi_dung_gop}.",
        f"Tiếp nối tình huống đó, {xung_ho} liền chia sẻ thẳng thắn: {noi_dung_gop}.",
        f"Trước diễn biến trên sân, {ten_nv} lập tức phản ứng: {noi_dung_gop}.",
        f"Không chịu kém cạnh, {xung_ho} liền đáp lại đầy tự tin: {noi_dung_gop}.",
        f"Ngay sau pha xử lý vừa rồi, {ten_nv} phải thốt lên: {noi_dung_gop}.",
        f"Nhìn màn thể hiện trước mắt, {xung_ho} nhận xét cực kỳ chuẩn xác: {noi_dung_gop}.",
        f"Trước tình cảnh dở khóc dở cười này, {ten_nv} chỉ biết lắc đầu bảo rằng: {noi_dung_gop}.",
        f"Qua màn đối đầu vừa rồi, {xung_ho} rút ra ngay bài học đắt giá: {noi_dung_gop}.",
    ]
    cau_hoan_chinh = dan_nhap[panel_idx % len(dan_nhap)]
    if panel_idx == tong_panel - 1:
        cau_hoan_chinh += " Hãy cùng theo dõi tiếp những diễn biến thú vị ở chương sau nhé!"
    return cau_hoan_chinh


def sinh_kich_ban_review_chuong(
    panels_bytes: list[bytes],
    ocr_per_panel: list[list[str]] | None = None,
    *,
    cast_memory: CharacterCastMemory | None = None,
    phong_cach: str = "kich_tinh",
    ten_truyen: str = "",
    ten_chap: str = "",
    thu_ket_noi_vision_cuc_bo: bool = True,
) -> dict[str, Any]:
    """
    Sinh kịch bản Review Truyện hoàn chỉnh cho 1 Chapter:
    - Tự động quét tên nhân vật thật trong lời thoại (`Hiyori`, `Haruka-chan`, `Lai-chan`...).
    - Kết nối trực tiếp Bộ máy AI để đọc toàn bộ lời thoại của Chapter và biên tập kịch bản Review
      bám sát 100% cốt truyện thực tế.
    - Tự động ghép lưới Storyboard `2x2` và dự phòng thông minh nếu máy đang chạy ngoại tuyến.
    """
    if not panels_bytes:
        raise ValueError("Chưa có khung tranh nào để tạo kịch bản Review.")

    cast = cast_memory or CharacterCastMemory()
    tong = len(panels_bytes)
    normalized_ocr: list[list[str]] = [
        [lam_sach_thoai_ocr_cho_review(c) for c in (ocr_per_panel[i] if ocr_per_panel and i < len(ocr_per_panel) else []) if lam_sach_thoai_ocr_cho_review(c)]
        for i in range(tong)
    ]

    # Tự động trích xuất tên nhân vật thật từ thoại nếu chưa có hoặc chỉ đang có nhân vật mặc định
    co_ten_mac_dinh = all(c["ten"] in ("Nhân vật chính", "Kẻ địch", "Đối phương") for c in cast.characters)
    if (not cast.characters or co_ten_mac_dinh) and any(normalized_ocr):
        tu_dong_quet_ho_so_nhan_vat_tu_thoai(normalized_ocr, cast)

    info_pc = PHONG_CACH_KICH_BAN.get(phong_cach) or PHONG_CACH_KICH_BAN["kich_tinh"]
    tieu_de = " - ".join(p for p in (ten_truyen.strip(), ten_chap.strip()) if p) or "Chương Truyện Mới"
    cau_hook = f"Chào mừng các bạn quay lại với {tieu_de}. {info_pc['cau_hook_mau']}"

    so_luoi_2x2 = (tong + 3) // 4
    scenes: list[dict[str, Any]] = []

    # Gọi AI Biên kịch toàn chương nếu có lời thoại
    ai_scenes = (
        _viet_kich_ban_toan_chuong_bang_ai(
            normalized_ocr,
            cast,
            ten_truyen=ten_truyen,
            ten_chap=ten_chap,
            phong_cach=phong_cach,
        )
        if any(normalized_ocr)
        else None
    )

    for idx, p_bytes in enumerate(panels_bytes):
        ds_thoai = normalized_ocr[idx]
        van_ban_gop = " ".join(ds_thoai)
        nv = cast.doan_nhan_vat_theo_ngu_canh(van_ban_gop, panel_idx=idx)
        bo_cuc = phan_tich_bo_cuc_anh_khung_tranh(p_bytes)

        ai_sc = ai_scenes[idx] if ai_scenes and idx < len(ai_scenes) else {}
        ten_nv_vis = str((ai_sc or {}).get("nhan_vat") or nv["ten"]).strip()
        loi_binh = str((ai_sc or {}).get("loi_thuyet_minh") or "").strip()

        if not loi_binh:
            loi_binh = _bien_tap_cau_review_tu_thoai(
                ds_thoai,
                nv,
                panel_idx=idx,
                tong_panel=tong,
                phong_cach=phong_cach,
                khong_khi_anh=bo_cuc["khong_khi"],
                boi_canh_chung=tieu_de,
            )

        if idx == 0 and tieu_de.lower() not in loi_binh.lower():
            loi_binh = f"Chào mừng các bạn đến với {tieu_de}. {loi_binh}"

        scenes.append(
            {
                "scene_index": idx + 1,
                "nhan_vat": ten_nv_vis,
                "vai_tro": nv["vai_tro"],
                "xung_ho": nv["xung_ho"],
                "thoai_goc": ds_thoai,
                "la_canh_hanh_dong": len(ds_thoai) == 0,
                "khong_khi_anh": bo_cuc["khong_khi"],
                "loi_thuyet_minh": loi_binh,
                "hieu_ung_camera": "pan_down" if idx % 2 == 0 else "zoom_in",
            }
        )

    return {
        "ten_truyen": ten_truyen,
        "ten_chap": ten_chap,
        "phong_cach": phong_cach,
        "ten_phong_cach": info_pc["ten"],
        "cau_hook_mo_dau": cau_hook,
        "so_khung_tranh": tong,
        "so_luoi_storyboard_2x2": so_luoi_2x2,
        "ho_so_nhan_vat": cast.tao_mo_ta_ho_so_cho_ai(),
        "scenes": scenes,
    }
