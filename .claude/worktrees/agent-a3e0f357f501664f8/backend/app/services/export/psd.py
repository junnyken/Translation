"""E78 — bộ ghi PSD tối giản (Adobe Photoshop File Format, version 1) bằng `struct` + numpy.

Cảm hứng từ cách Koharu xuất PSD (lớp ảnh gốc ẩn, lớp đã xoá chữ, lớp chữ) — KHÔNG lấy code của
Koharu (GPL, nguyên tắc 1 của dự án). Viết thẳng theo đặc tả công khai của Adobe.

## Chỉ ghi đúng tập con cần dùng — cố ý

- 8 bit/kênh, chế độ màu RGB (mode 3), 3 kênh cho ảnh ghép.
- Mỗi lớp là RGBA: kênh `-1` (độ trong suốt) + 0/1/2 (R/G/B), **nén RAW** (compression 0).
  RAW to hơn RLE nhưng không có chỗ nào để sai thuật toán nén; tệp nằm trong ZIP deflate nên
  phần trong suốt (toàn số 0) nén lại gần hết.
- Lớp được cắt gọn về hộp bao các điểm ảnh có alpha > 0 (`rect` riêng của từng lớp), nên lớp chữ
  chỉ tốn đúng chỗ chữ chiếm chứ không tốn cả trang.
- Tên lớp: Pascal string ASCII (dự phòng cho bộ đọc cũ) + khối `luni` (UTF-16BE) cho tiếng Việt.
- Ảnh ghép (image data cuối tệp) = ảnh xem thử đã chèn chữ — bộ đọc không hiểu lớp (Xem ảnh
  Windows, ảnh thu nhỏ) vẫn thấy đúng trang hoàn thiện.

Không có: color mode data, image resources, layer mask, text layer (`TySh`). Lớp chữ là RASTER.

Ghi THẲNG ra tệp/luồng (`fp.write`), không dựng cả tệp trong RAM: ảnh đã phóng `he_so_ve` có thể
vài chục MB mỗi kênh.
"""
from __future__ import annotations

import struct
import unicodedata
from dataclasses import dataclass
from typing import BinaryIO, Iterable

import numpy as np
from PIL import Image

#: Cạnh tối đa của PSD version 1 (PSB mới vượt được). Vượt thì Photoshop từ chối mở.
CANH_TOI_DA = 30000

#: Cờ lớp: bit 1 = ẨN. Đặc tả gọi bit này là "visible" nhưng ý nghĩa thực tế (Photoshop, Photopea,
#: psd-tools) là: bật ⇒ lớp bị ẩn.
CO_AN = 0x02


class PsdQuaLon(ValueError):
    pass


@dataclass
class LopPsd:
    """Một lớp. `anh` là ảnh RGBA CỠ CANVAS (hoặc RGB ⇒ coi như đục hoàn toàn)."""

    ten: str
    anh: Image.Image
    an: bool = False


def _ten_ascii(ten: str) -> bytes:
    """Pascal name dự phòng: bỏ dấu tiếng Việt, ký tự ngoài ASCII thành `?`, tối đa 255 byte."""
    t = unicodedata.normalize("NFD", ten).replace("đ", "d").replace("Đ", "D")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return t.encode("ascii", "replace")[:255]


def _pascal_dem_4(ten: str) -> bytes:
    """Byte độ dài + tên, đệm 0 cho TỔNG (kể cả byte độ dài) chia hết cho 4 — đặc tả layer record."""
    b = _ten_ascii(ten)
    raw = bytes([len(b)]) + b
    return raw + b"\x00" * (-len(raw) % 4)


def _khoi_luni(ten: str) -> bytes:
    """Tagged block `luni`: `8BIM` `luni` <độ dài> <số ký tự UTF-16> <UTF-16BE>, đệm tới bội 4."""
    u16 = ten.encode("utf-16-be")
    data = struct.pack(">I", len(u16) // 2) + u16
    data += b"\x00" * (-len(data) % 4)
    return b"8BIM" + b"luni" + struct.pack(">I", len(data)) + data


@dataclass
class _LopDaChuan:
    ten: str
    an: bool
    top: int
    left: int
    bottom: int
    right: int
    kenh: list[tuple[int, np.ndarray]]  # (id kênh, mảng uint8 h×w), theo thứ tự ghi

    @property
    def dien_tich(self) -> int:
        return (self.bottom - self.top) * (self.right - self.left)


def _chuan_hoa(lop: LopPsd, kich_thuoc: tuple[int, int]) -> _LopDaChuan:
    anh = lop.anh
    if anh.size != kich_thuoc:
        raise ValueError(f"lớp '{lop.ten}' cỡ {anh.size} khác canvas {kich_thuoc}")
    rgba = anh.convert("RGBA")
    # Cắt về hộp bao phần có alpha > 0. Lớp trống hoàn toàn ⇒ rect rỗng (0×0) — vẫn là một lớp
    # hợp lệ, để số lớp luôn khớp số vùng có chữ (không lặng lẽ mất một lớp).
    hop = rgba.getchannel("A").getbbox()
    if hop is None:
        return _LopDaChuan(lop.ten, lop.an, 0, 0, 0, 0, [(0, _rong()), (1, _rong()),
                                                         (2, _rong()), (-1, _rong())])
    left, top, right, bottom = hop
    if (right - left) % 2 and (right - left) < kich_thuoc[0]:
        # Nới bề rộng thành số CHẴN (thêm một cột trong suốt). Vô hại với Photoshop, nhưng bộ đọc
        # PSD của Pillow tự nhảy 1 byte đệm sau mỗi kênh có độ dài lẻ (đặc tả KHÔNG có byte đệm
        # đó) — kênh lẻ làm nó đọc lệch mọi lớp phía sau. Giữ chẵn để kiểm được bằng Pillow.
        if right < kich_thuoc[0]:
            right += 1
        else:
            left -= 1
    mang = np.asarray(rgba.crop((left, top, right, bottom)), dtype=np.uint8)
    # Thứ tự R, G, B rồi alpha (-1). Đặc tả cho phép thứ tự bất kỳ (mỗi kênh mang id riêng);
    # chọn thứ tự này vì Pillow đọc kênh lớp theo đúng thứ tự R, G, B, A bất kể id.
    kenh = [(0, mang[:, :, 0]), (1, mang[:, :, 1]), (2, mang[:, :, 2]), (-1, mang[:, :, 3])]
    return _LopDaChuan(lop.ten, lop.an, top, left, bottom, right, kenh)


def _rong() -> np.ndarray:
    return np.zeros((0, 0), dtype=np.uint8)


def _ban_ghi_lop(lop: _LopDaChuan) -> bytes:
    """Layer record (đặc tả: "Layer records")."""
    out = struct.pack(">iiii", lop.top, lop.left, lop.bottom, lop.right)
    out += struct.pack(">H", len(lop.kenh))
    for id_kenh, _m in lop.kenh:
        # Độ dài dữ liệu kênh = 2 byte kiểu nén + dữ liệu RAW.
        out += struct.pack(">hI", id_kenh, 2 + lop.dien_tich)
    out += b"8BIM" + b"norm"
    out += struct.pack(">BBBB", 255, 0, CO_AN if lop.an else 0, 0)  # opacity, clipping, cờ, filler
    phu = (
        struct.pack(">I", 0)  # layer mask data: không có
        + struct.pack(">I", 0)  # blending ranges: không có
        + _pascal_dem_4(lop.ten)
        + _khoi_luni(lop.ten)
    )
    return out + struct.pack(">I", len(phu)) + phu


def ghi_psd(fp: BinaryIO, kich_thuoc: tuple[int, int], cac_lop: Iterable[LopPsd],
            anh_ghep: Image.Image) -> None:
    """Ghi một PSD vào `fp`. `cac_lop` xếp DƯỚI → TRÊN (lớp đầu là lớp dưới cùng, đúng đặc tả).

    `cac_lop` có thể là generator: mỗi lớp được cắt gọn ngay khi tới, nên ảnh RGBA cỡ canvas của
    từng vùng chữ không phải nằm trong RAM cùng lúc.

    `anh_ghep` là ảnh ghép hiển thị (cỡ canvas) — ghi vào phần image data cuối tệp.
    """
    rong, cao = kich_thuoc
    if rong > CANH_TOI_DA or cao > CANH_TOI_DA:
        raise PsdQuaLon(f"canvas {rong}×{cao} vượt {CANH_TOI_DA}px — PSD v1 không chứa được")
    if anh_ghep.size != kich_thuoc:
        raise ValueError(f"ảnh ghép cỡ {anh_ghep.size} khác canvas {kich_thuoc}")

    lop_chuan = [_chuan_hoa(lop, kich_thuoc) for lop in cac_lop]

    # ---- Header ----
    fp.write(b"8BPS" + struct.pack(">H", 1) + b"\x00" * 6)
    fp.write(struct.pack(">HIIHH", 3, cao, rong, 8, 3))  # 3 kênh, cao, rộng, 8 bit, RGB
    # ---- Color mode data + Image resources: rỗng ----
    fp.write(struct.pack(">I", 0))
    fp.write(struct.pack(">I", 0))

    # ---- Layer and mask information ----
    ban_ghi = b"".join(_ban_ghi_lop(lop) for lop in lop_chuan)
    do_dai_du_lieu = sum(len(lop.kenh) * (2 + lop.dien_tich) for lop in lop_chuan)
    noi_dung_layer_info = 2 + len(ban_ghi) + do_dai_du_lieu
    dem_layer_info = noi_dung_layer_info % 2  # đặc tả: làm tròn lên bội 2
    do_dai_layer_info = noi_dung_layer_info + dem_layer_info
    # Tổng phần: 4 (độ dài layer info) + layer info + 4 (global layer mask info, rỗng).
    fp.write(struct.pack(">I", 4 + do_dai_layer_info + 4))
    fp.write(struct.pack(">I", do_dai_layer_info))
    # Số lớp DƯƠNG: kênh alpha của ảnh ghép không mang độ trong suốt (ảnh ghép đục).
    fp.write(struct.pack(">h", len(lop_chuan)))
    fp.write(ban_ghi)
    for lop in lop_chuan:
        for _id, mang in lop.kenh:
            fp.write(struct.pack(">H", 0))  # RAW
            fp.write(np.ascontiguousarray(mang).tobytes())
    fp.write(b"\x00" * dem_layer_info)
    fp.write(struct.pack(">I", 0))  # global layer mask info: rỗng

    # ---- Image data (ảnh ghép), RAW, xếp theo mặt phẳng R rồi G rồi B ----
    fp.write(struct.pack(">H", 0))
    ghep = np.asarray(anh_ghep.convert("RGB"), dtype=np.uint8)
    for i in range(3):
        fp.write(np.ascontiguousarray(ghep[:, :, i]).tobytes())
