"""E20b — tiền xử lý ảnh trước OCR, mỗi phép biến đổi ĐẶT TÊN + CÓ PHIÊN BẢN, xác định.

Không chaining ngẫu nhiên nhiều filter (constraint E20b #đầu) — mỗi hàm trong `PIPELINE` là MỘT
biến đổi độc lập, không gọi lồng nhau. Không sửa `ground_truth` — chỉ trả về `Image.Image` mới,
không đụng gì tới manifest.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter


@dataclass(frozen=True)
class PhepTienXuLy:
    ten: str
    phien_ban: str
    ham: Callable[[Image.Image], Image.Image]
    mo_ta: str


def _khong_doi(img: Image.Image) -> Image.Image:
    return img.copy()


def _xam_hoa(img: Image.Image) -> Image.Image:
    return img.convert("L").convert("RGB")


def _phong_to_2x(img: Image.Image) -> Image.Image:
    return img.resize((img.width * 2, img.height * 2), Image.LANCZOS)


def _tang_tuong_phan(img: Image.Image) -> Image.Image:
    """Tăng tương phản cố định 1.8x — hệ số CHỐT sẵn (không tự dò per-ảnh), để pipeline xác định
    và tái lập được. Giả thuyết cần đo (REPORT_E20a §10.2): chữ mảnh lẫn vào nền phức tạp vì
    tương phản cục bộ thấp ngay tại nét chữ — tăng tương phản toàn ảnh là phép rẻ nhất kiểm trước."""
    return ImageEnhance.Contrast(img.convert("RGB")).enhance(1.8)


def _nguong_thich_nghi(img: Image.Image) -> Image.Image:
    """Nhị phân hoá kiểu ngưỡng cục bộ (so mỗi điểm ảnh với trung bình một vùng quanh nó, trừ đi
    hằng số) — khác hẳn ngưỡng toàn cục (Otsu) vì nền tranh không đều màu; dùng NumPy thuần, không
    thêm dependency OpenCV cho một phép biến đổi benchmark."""
    xam = np.asarray(img.convert("L"), dtype=np.float32)
    xam_mo = np.asarray(img.convert("L").filter(ImageFilter.GaussianBlur(15)), dtype=np.float32)
    nhi_phan = np.where(xam > (xam_mo - 8), 255, 0).astype(np.uint8)
    return Image.fromarray(nhi_phan, mode="L").convert("RGB")


PIPELINE: dict[str, PhepTienXuLy] = {
    p.ten: p for p in (
        PhepTienXuLy("khong_doi", "1.0.0", _khong_doi, "Đối chứng — không xử lý gì"),
        PhepTienXuLy("xam_hoa", "1.0.0", _xam_hoa, "Chuyển ảnh xám"),
        PhepTienXuLy("phong_to_2x", "1.0.0", _phong_to_2x, "Phóng to 2x (LANCZOS)"),
        PhepTienXuLy("tang_tuong_phan", "1.0.0", _tang_tuong_phan, "Tăng tương phản cố định 1.8x"),
        PhepTienXuLy("nguong_thich_nghi", "1.0.0", _nguong_thich_nghi,
                     "Nhị phân hoá ngưỡng cục bộ (Gaussian blur bán kính 15, trừ hằng số 8)"),
    )
}


def ap_dung(ten_phep: str, img: Image.Image) -> Image.Image:
    if ten_phep not in PIPELINE:
        raise KeyError(f"Không có phép tiền xử lý '{ten_phep}'. Có: {sorted(PIPELINE)}")
    return PIPELINE[ten_phep].ham(img)
