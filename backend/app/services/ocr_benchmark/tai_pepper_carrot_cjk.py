"""Tải trang Pepper&Carrot bản **tiếng Nhật và tiếng Trung** để hiệu chỉnh E57.

Script nằm ở đây, KHÔNG nằm cạnh ảnh: `backend/test_fixtures/external/` bị `.gitignore` (đúng —
ảnh không lên repo), nên để script ở đó là để công thức tái lập cũng biến mất theo.

## Vì sao bộ này

`ocr_benchmark` + `ocr_benchmark_e20b` có 65 mẫu có nhãn nhưng **tất cả là `en`**. Không có mẫu
ja/zh nào thì không hiệu chỉnh được ngưỡng kana, cũng không đo được chiều ja↔zh — đúng hai chỗ mà
`source_lang` chọn sai gây hại nhất (manga-ocr vs PaddleOCR là hai model khác hẳn).

Pepper&Carrot có bản dịch tiếng Nhật và tiếng Trung của **cùng những trang** dự án đã dùng cho Run C.
Giấy phép **CC BY-SA 4.0** (David Revoy, peppercarrot.com) nên số đo công bố được — cùng lý do
`NGUON.md` đã chọn bộ này.

## Ba bẫy, cả ba đã trả giá một lần rồi

**1. Mã ngôn ngữ của tiếng Trung là `cn`, KHÔNG phải `zh`.** `https://…/zh/webcomic/ep01…` trả HTTP
**200** — nhưng ảnh trong đó mang tiền tố `en_`, tức trang **chưa dịch** và site lùi về bản tiếng
Anh. Tin "200 = có bản dịch" là tải ảnh tiếng Anh về rồi dán nhãn "tiếng Trung": một tập dữ liệu
BỊA, và mọi số đo sau đó vô nghĩa. ⇒ chỉ nhận ảnh mang **đúng tiền tố ngôn ngữ đang xin**.

**2. peppercarrot.com trả HTTP 200 kèm một trang HTML cho MỌI URL sai** (soft-404, ~12 KB). Mã 200
không phải bằng chứng có ảnh ⇒ phải kiểm **magic byte** + **mở được bằng PIL**.

**3. "Không kiểm được" phải là lỗi làm DỪNG, không được tính thành phán quyết "tệp xấu".**
Lượt tải của E23 kiểm bằng `file --mime-type`, mà `file` không có trong máy này ⇒ phép kiểm luôn
thất bại ⇒ script **xoá sạch 18 ảnh thật vừa tải**. Nên ở đây chỉ dùng thứ chắc chắn có (`PIL`), và
nếu `PIL` không import được thì dừng ngay chứ không xoá gì.

Chạy:

    ../.venv/bin/python -m app.services.ocr_benchmark.tai_pepper_carrot_cjk
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

GOC = "https://www.peppercarrot.com"
#: `cn` là tiếng Trung — xem bẫy 1 ở docstring. `zh` KHÔNG có bản dịch.
NGON_NGU = {"ja": "ja", "cn": "zh"}
TAP = [
    "ep01_Potion-of-Flight",
    "ep02_Rainbow-Potions",
    "ep03_The-Secret-Ingredients",
]
DICH = (
    Path(__file__).resolve().parents[3] / "test_fixtures" / "external" / "pepper_carrot_cjk"
)


def _tai(url: str, timeout: int = 30) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception as e:  # noqa: BLE001
        print(f"    loi mang: {type(e).__name__}: {e}", file=sys.stderr)
        return 0, b""


def _la_anh_that(raw: bytes) -> tuple[bool, str]:
    """Hai lớp: magic byte, rồi mở thật bằng PIL. Trả (đạt, lý do nếu không đạt)."""
    if len(raw) < 1024:
        return False, f"qua nho ({len(raw)} byte)"
    if not (raw.startswith(b"\xff\xd8\xff") or raw.startswith(b"\x89PNG\r\n\x1a\n")):
        # Soft-404 rơi vào đây: nó là HTML, không có magic byte ảnh.
        return False, f"khong phai JPEG/PNG (dau tep: {raw[:8]!r})"
    import io

    from PIL import Image  # import o day de bay 3 la loi DUNG, khong phai phan quyet "tep xau"

    try:
        with Image.open(io.BytesIO(raw)) as im:
            im.verify()
        with Image.open(io.BytesIO(raw)) as im:
            w, h = im.size
    except Exception as e:  # noqa: BLE001
        return False, f"PIL khong mo duoc: {type(e).__name__}: {e}"
    if w < 400 or h < 400:
        return False, f"kich thuoc bat thuong {w}x{h}"
    return True, f"{w}x{h}"


def main() -> int:
    try:
        import PIL  # noqa: F401
    except ImportError:
        # Bẫy 3: phép kiểm không chạy được ⇒ DỪNG, không tải và không xoá gì.
        print("DUNG: khong import duoc PIL nen khong kiem duoc anh. Khong tai gi.", file=sys.stderr)
        return 2

    DICH.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []
    for ma_site, nhan in NGON_NGU.items():
        for tap in TAP:
            st, html = _tai(f"{GOC}/{ma_site}/webcomic/{tap}.html")
            if st != 200:
                print(f"  {ma_site}/{tap}: trang tap HTTP {st} — bo qua")
                continue
            html_s = html.decode("utf-8", "replace")
            # CHỈ nhận ảnh mang đúng tiền tố ngôn ngữ đang xin (bẫy 1).
            duong = re.findall(
                rf'src="([^"]*low-res/{re.escape(ma_site)}_Pepper[^"]*\.jpg)"', html_s
            )
            if not duong:
                print(f"  {ma_site}/{tap}: KHONG co anh mang tien to '{ma_site}_' "
                      f"⇒ tap nay CHUA dich sang ngon ngu nay. Bo qua (khong lay anh en_).")
                continue
            for u in duong:
                ten = u.rsplit("/", 1)[-1]
                # P00 là ảnh BÌA (tiêu đề + logo), không phải trang thoại — bỏ.
                if "P00" in ten:
                    continue
                st2, raw = _tai(u)
                if st2 != 200:
                    print(f"    {ten}: HTTP {st2}")
                    continue
                dat, ly_do = _la_anh_that(raw)
                if not dat:
                    print(f"    {ten}: BO — {ly_do}")
                    continue
                p = DICH / f"{nhan}__{ten}"
                p.write_bytes(raw)
                manifest.append({
                    "tep": p.name,
                    "language": nhan,
                    "ma_site": ma_site,
                    "tap": tap,
                    "kich_thuoc": ly_do,
                    "nguon": u,
                    "license": "CC BY-SA 4.0 — David Revoy, peppercarrot.com",
                })
                print(f"    OK {p.name} ({ly_do})")

    (DICH / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    from collections import Counter
    print(f"\nTong {len(manifest)} trang: {dict(Counter(m['language'] for m in manifest))}")
    print(f"Luu o {DICH}")
    return 0 if manifest else 1


if __name__ == "__main__":
    raise SystemExit(main())
