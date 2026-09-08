"""E20a — chạy MỘT engine OCR trên tập mẫu benchmark, dùng ĐÚNG adapter M3 production.

Cố ý gọi `engine.recognize(image_path, bbox)` — chữ ký giống hệt lúc worker thật gọi (M3) —
thay vì tự viết lại lời gọi PaddleOCR/manga-ocr riêng cho benchmark. Bbox truyền vào là NGUYÊN
CẢ ẢNH CROP (0,0,w,h): mỗi file trong `crops/` đã LÀ một vùng, không phải cả trang, nên không
cần cắt gì thêm — nhưng vẫn đi qua đúng `crop_region`/`bbox_to_pixel_box` của production, không
bỏ qua bước đó.

Không đụng DB — không có tham chiếu `Page`/`Job`/`OCRResult` nào ở đây.
"""
from __future__ import annotations

import time

from PIL import Image

from app.services.interfaces import BBox
from app.services.ocr.engines import _BaseOCREngine

from .dataset import BenchmarkSample
from .metrics import KetQuaMotMau


class OCRBenchmarkRunner:
    def __init__(self, engine: _BaseOCREngine) -> None:
        self.engine = engine

    def chay_mot(self, mau: BenchmarkSample) -> KetQuaMotMau:
        with Image.open(mau.crop_path) as im:
            w, h = im.size
        bbox = BBox(x=0, y=0, w=w, h=h)

        bat_dau = time.perf_counter()
        text, conf = self.engine.recognize(str(mau.crop_path), bbox)
        het_gio = time.perf_counter() - bat_dau

        return KetQuaMotMau(
            sample_id=mau.sample_id,
            lettering_style=mau.lettering_style,
            text_kind=mau.text_kind,
            ground_truth=mau.ground_truth,
            predicted_text=text,
            confidence=conf,
            runtime_seconds=het_gio,
        )

    def chay_tat_ca(self, danh_sach: list[BenchmarkSample]) -> list[KetQuaMotMau]:
        return [self.chay_mot(m) for m in danh_sach]
