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
    from PIL import Image, ImageDraw, ImageFont
except Exception:  # pragma: no cover
    Image = None
    ImageDraw = None
    ImageFont = None


PHONG_CACH_KICH_BAN = {
    "kich_tinh": {
        "ten": "🔥 Kịch tính / Hành động (Chuẩn Review Manhwa/Manga)",
        "mo_ta": "Nhịp nhanh, dồn dập, nhấn mạnh các pha ra đòn, thức tỉnh sức mạnh và biểu cảm bá đạo.",
        "cau_hook_mau": "Tưởng chừng đã rơi vào tuyệt cảnh, nhưng không ai ngờ khoảnh khắc tiếp theo lại khiến tất cả phải chấn động!",
    },
    "hai_huoc": {
        "ten": "😂 Hài hước / Cà khịa (Chuẩn TikTok / Reels triệu view)",
        "mo_ta": "Dùng từ ngữ trẻ trung, dí dỏm, bắt trend, châm biếm đám phản diện gáy sớm.",
        "cau_hook_mau": "Đúng là quy luật muôn đời của đám phản diện: lúc gáy thì vang cả bầu trời, đến lúc gặp anh main thì chỉ biết khóc thét!",
    },
    "tu_tien": {
        "ten": "⚔️ Tu tiên / Hệ thống / Trọng sinh",
        "mo_ta": "Ngôn từ cổ trang, khí thế cường giả, đột phá cảnh giới, uy áp ngập trời.",
        "cau_hook_mau": "Trọng sinh trở về từ vạn năm trước, ánh mắt thiếu niên lạnh băng nhìn đám người từng phản bội mình!",
    },
    "ngon_tinh": {
        "ten": "💕 Ngôn tình / Tổng tài / Drama",
        "mo_ta": "Giàu cảm xúc, xoáy sâu vào ánh mắt, tâm lý nhân vật và những màn trả thù ngọt ngào.",
        "cau_hook_mau": "Ba năm hy sinh thầm lặng đổi lại chỉ là sự lạnh nhạt, ngày cô quyết định rời đi cũng là lúc anh ta hối hận muộn màng!",
    },
}


class CharacterCastMemory:
    """
    Bộ Nhớ Hồ Sơ Nhân Vật Xuyên Chapter (`character_bible.json`):
    Giúp hệ thống Biên kịch Thị giác nhận diện chính xác nhân vật nào đang nói hoặc hành động
    qua đặc điểm ngoại hình (màu tóc, trang phục, vũ khí) và cách xưng hô.
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
            "vai_tro": str(item.get("vai_tro") or "Nam chính (Main)").strip(),
            "ngoai_hinh": str(item.get("ngoai_hinh") or "Tóc đen, trang phục chiến đấu tối màu").strip(),
            "xung_ho": str(item.get("xung_ho") or "thanh niên").strip(),
            "tu_khoa_nhan_dien": str(item.get("tu_khoa_nhan_dien") or "").strip(),
        }

    def them_hoac_cap_nhat(
        self,
        ten: str,
        vai_tro: str = "Nam chính (Main)",
        ngoai_hinh: str = "",
        xung_ho: str = "thanh niên",
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
            return (
                "- Nhân vật chính (Main): gọi là 'thanh niên' hoặc 'nhân vật chính'.\n"
                "- Đối thủ / Phản diện: gọi là 'tên đối thủ' hoặc 'gã trước mặt'."
            )
        lines = []
        for idx, c in enumerate(self.characters, 1):
            lines.append(
                f"{idx}. [{c['vai_tro']}] Tên: {c['ten']} (cách gọi: '{c['xung_ho']}') "
                f"— Ngoại hình nhận diện: {c['ngoai_hinh']}"
            )
        return "\n".join(lines)

    def doan_nhan_vat_theo_ngu_canh(self, van_ban_thoai: str, vi_tri_bong: str = "giua", panel_idx: int = 0) -> dict[str, str]:
        """
        Đối chiếu lời thoại + từ khoá nhận diện + vị trí bóng thoại để gán nhân vật phù hợp nhất.
        """
        if not self.characters:
            return {
                "ten": "Nhân vật chính" if panel_idx % 2 == 0 else "Đối phương",
                "vai_tro": "Main" if panel_idx % 2 == 0 else "Nhân vật",
                "xung_ho": "thanh niên" if panel_idx % 2 == 0 else "đối phương",
            }
        txt_low = (van_ban_thoai or "").lower()
        # 1. Nếu trong câu thoại hoặc ghi chú có tên / từ khoá nhận diện trực tiếp
        for c in self.characters:
            tu_khoa = [k.strip().lower() for k in (c.get("tu_khoa_nhan_dien") or "").split(",") if k.strip()]
            if c["ten"].lower() in txt_low or any(k in txt_low for k in tu_khoa):
                return c
        # 2. Nếu câu thoại mang sắc thái gáy bẩn / đe dọa của phản diện
        if any(w in txt_low for w in ("chết đi", "phế vật", "ngươi dám", "quỳ xuống", "con kiến", "ha ha")):
            for c in self.characters:
                if "phản diện" in c["vai_tro"].lower() or "đối thủ" in c["vai_tro"].lower():
                    return c
        # 3. Mặc định ưu tiên nhân vật chính ở các khung chủ đạo hoặc luân phiên hợp lý
        if vi_tri_bong == "phai" and len(self.characters) > 1:
            return self.characters[min(1, len(self.characters) - 1)]
        return self.characters[0]


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

            # Thu nhỏ chiều ngang về 64px để quét nhanh phương sai màu theo từng dòng ngang (Gutter Detection)
            im_small = im.resize((64, H))
            px = im_small.load()
            la_ranh_ngang = [False] * H
            for y in range(H):
                r0, g0, b0 = px[0, y]
                # Kiểm tra dòng gần như đồng màu trắng (>=242) hoặc đen (<=16)
                dong_dong_nhat = True
                for x in range(0, 64, 4):
                    r, g, b = px[x, y]
                    if abs(r - r0) > 14 or abs(g - g0) > 14 or abs(b - b0) > 14:
                        dong_dong_nhat = False
                        break
                if dong_dong_nhat and ((r0 > 240 and g0 > 240 and b0 > 240) or (r0 < 18 and g0 < 18 and b0 < 18)):
                    la_ranh_ngang[y] = True

            # Cắt trang dài theo các điểm rãnh hợp lý
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

                # Tìm rãnh phân cách gần vị trí mục tiêu nhất
                for y_ung_vien in range(y_muc_tieu, y_tim_min, -1):
                    if la_ranh_ngang[y_ung_vien - 1]:
                        y_cat = y_ung_vien
                        break

                crop = im.crop((0, y_bat_dau, W, y_cat))
                buf = io.BytesIO()
                crop.save(buf, format="JPEG", quality=92)
                panels_out.append(buf.getvalue())
                y_bat_dau = y_cat

                # Bỏ qua vùng đệm rãnh quá dày giữa 2 khung tranh
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
    Ghép tối đa 4 khung tranh liên tiếp vào 1 tấm ảnh lưới `2x2` có đánh số `[1]`, `[2]`, `[3]`, `[4]`.
    Giúp Lõi Thị Giác AI nhìn xuyên suốt 4 cảnh liên tiếp cùng lúc và tiết kiệm 75%-80% chi phí xử lý!
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
        # Vẽ nhãn số thứ tự khung [1]..[4] ở góc trái trên mỗi ô
        draw.rectangle([ox + 6, oy + 6, ox + 58, oy + 36], fill=(220, 38, 38), outline=(255, 255, 255), width=2)
        draw.text((ox + 16, oy + 11), f"#{idx + 1}", fill=(255, 255, 255))

    buf = io.BytesIO()
    grid_im.save(buf, format="JPEG", quality=86)
    return buf.getvalue()


def _bien_tap_cau_review_tu_thoai(
    thoai_raw: list[str],
    nhan_vat: dict[str, str],
    panel_idx: int,
    tong_panel: int,
    phong_cach: str = "kich_tinh",
) -> str:
    """
    Chuyển đổi thông minh lời thoại rời rạc (hoặc khung tranh hành động không lời)
    thành câu thuyết minh ngôi thứ 3 mạch lạc chuẩn kênh Review Truyện.
    """
    ten_nv = nhan_vat.get("ten") or "Nhân vật chính"
    xung_ho = nhan_vat.get("xung_ho") or "thanh niên"
    ds_sach = [t.strip() for t in thoai_raw if t and len(t.strip()) >= 2]

    # Khung tranh hành động không lời (Silent Action Panel)
    if not ds_sach:
        mau_khong_loi = {
            "kich_tinh": [
                f"Không cần thêm bất kỳ lời nói thừa thãi nào, {ten_nv} lập tức lao lên tung ra đòn quyết định khiến không gian xung quanh chấn động.",
                f"Ánh mắt của {xung_ho} đột nhiên sắc lạnh, sát khí bùng nổ bao trùm toàn bộ chiến trường trong tích tắc.",
                f"Trước sức ép kinh hoàng đang ập tới, {ten_nv} vẫn đứng vững vàng, chuẩn bị tung raát chủ bài của mình.",
            ],
            "hai_huoc": [
                f"Nhìn cảnh này thì đúng là không còn gì để nói, {ten_nv} chỉ lặng lẽ ra tay cho đối phương biết thế nào là lễ độ.",
                f"Không nói nhiều, {xung_ho} vào việc luôn với tốc độ bàn thờ khiến đối thủ đứng hình mất năm giây.",
            ],
            "tu_tien": [
                f"Linh khí quanh người {ten_nv} cuồn cuộn dâng trào, uy áp khủng khiếp khiến vạn vật xung quanh đều phải run rẩy.",
                f"Chỉ bằng một ánh nhìn lạnh băng, {xung_ho} đã thi triển tuyệt kỹ trấn phái chấn động cả một vùng thiên địa.",
            ],
            "ngon_tinh": [
                f"Khoảnh khắc bốn mắt nhìn nhau, bầu không khí bỗng chốc lắng đọng với biết bao cảm xúc ngổn ngang chưa thể nói thành lời.",
                f"{ten_nv} lặng lẽ quay bước đi, để lại phía sau ánh nhìn đầy sững sờ và tiếc nuối.",
            ],
        }
        ds_mau = mau_khong_loi.get(phong_cach) or mau_khong_loi["kich_tinh"]
        return ds_mau[panel_idx % len(ds_mau)]

    gop_thoai = " ".join(ds_sach)
    # Loại bỏ các từ cảm thán đơn lẻ đầu câu để câu thuyết minh mượt mà
    gop_sach = re.sub(r"^(hả|cái gì|á|ớ|hự|ư|hừm|này)[!?.…\s]+", "", gop_thoai, flags=re.I).strip() or gop_thoai

    if phong_cach == "hai_huoc":
        dan_nhap = [
            f"Lúc này {ten_nv} liền buông một câu cực gắt rằng: {gop_sach}",
            f"Nghe vậy, {xung_ho} chẳng thèm nể nang mà tuyên bố thẳng thừng: {gop_sach}",
            f"Tưởng thế nào, {ten_nv} lập tức đáp trả cực kỳ tỉnh bơ: {gop_sach}",
        ]
    elif phong_cach == "tu_tien":
        dan_nhap = [
            f"Khí thế bất phàm, {ten_nv} lạnh lùng cất giọng vang vọng: {gop_sach}",
            f"Ánh mắt {xung_ho} loé lên tia hàn quang rồi trầm giọng tuyên bố: {gop_sach}",
        ]
    elif phong_cach == "ngon_tinh":
        dan_nhap = [
            f"Giữa bầu không khí căng thẳng, {ten_nv} nghẹn ngào lên tiếng: {gop_sach}",
            f"Nhìn thẳng vào đối phương, {xung_ho} dứt khoát nói rõ lòng mình: {gop_sach}",
        ]
    else:
        dan_nhap = [
            f"Ngay lúc đó, {ten_nv} đanh thép lên tiếng: {gop_sach}",
            f"Chứng kiến cảnh tượng trước mắt, {xung_ho} lập tức khẳng định: {gop_sach}",
            f"Không hề nao núng, {ten_nv} lạnh lùng đáp trả: {gop_sach}",
        ]

    cau_hoan_chinh = dan_nhap[panel_idx % len(dan_nhap)]
    if panel_idx == tong_panel - 1:
        cau_hoan_chinh += " Diễn biến tiếp theo sẽ ra sao, hãy cùng theo dõi ngay phần sau nhé!"
    return cau_hoan_chinh


def sinh_kich_ban_review_chuong(
    panels_bytes: list[bytes],
    ocr_per_panel: list[list[str]] | None = None,
    *,
    cast_memory: CharacterCastMemory | None = None,
    phong_cach: str = "kich_tinh",
    ten_truyen: str = "",
    ten_chap: str = "",
) -> dict[str, Any]:
    """
    Sinh kịch bản Review Truyện hoàn chỉnh cho 1 Chapter:
    - Tự động ghép lưới Storyboard `2x2` cho từng cụm 4 khung tranh.
    - Đối chiếu `CharacterCastMemory` để xác định đúng nhân vật nói / hành động ở từng phân cảnh.
    - Sinh Câu Mở Đầu (Hook 3s đầu) + Danh sách phân cảnh (`scenes`) gồm:
      `scene_index`, `nhan_vat`, `vai_tro`, `thoai_goc`, `loi_thuyet_minh`, `la_canh_hanh_dong`.
    """
    if not panels_bytes:
        raise ValueError("Chưa có khung tranh nào để tạo kịch bản Review.")

    cast = cast_memory or CharacterCastMemory()
    info_pc = PHONG_CACH_KICH_BAN.get(phong_cach) or PHONG_CACH_KICH_BAN["kich_tinh"]
    tieu_de = " - ".join(p for p in (ten_truyen.strip(), ten_chap.strip()) if p) or "Chương Truyện Mới"

    cau_hook = f"Chào mừng các bạn quay lại với {tieu_de}. {info_pc['cau_hook_mau']}"

    # Tạo lưới 2x2 cho từng cụm 4 khung tranh để lưu kèm metadata Storyboard
    so_luoi_2x2 = 0
    for i in range(0, len(panels_bytes), 4):
        _ = tao_luoi_storyboard_2x2(panels_bytes[i : i + 4])
        so_luoi_2x2 += 1

    scenes: list[dict[str, Any]] = []
    tong = len(panels_bytes)
    for idx in range(tong):
        ds_thoai = (ocr_per_panel[idx] if ocr_per_panel and idx < len(ocr_per_panel) else []) or []
        van_ban_gop = " ".join(ds_thoai)
        vi_tri_bong = "trai" if idx % 2 == 0 else "phai"
        nv = cast.doan_nhan_vat_theo_ngu_canh(van_ban_gop, vi_tri_bong=vi_tri_bong, panel_idx=idx)
        loi_binh = _bien_tap_cau_review_tu_thoai(
            ds_thoai,
            nv,
            panel_idx=idx,
            tong_panel=tong,
            phong_cach=phong_cach,
        )
        if idx == 0:
            loi_binh = f"{cau_hook} {loi_binh}"

        scenes.append(
            {
                "scene_index": idx + 1,
                "nhan_vat": nv["ten"],
                "vai_tro": nv["vai_tro"],
                "xung_ho": nv["xung_ho"],
                "thoai_goc": ds_thoai,
                "la_canh_hanh_dong": len(ds_thoai) == 0,
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
