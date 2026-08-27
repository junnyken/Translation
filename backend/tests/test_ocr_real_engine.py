"""Chạy engine OCR THẬT — chỉ chạy trong container worker (có torch/paddle), bật bằng env:

    MTE_RUN_OCR_TESTS=1 pytest tests/test_ocr_real_engine.py -q

Không chạy trong test suite thường vì cần tải model (~440MB manga-ocr, ~20MB PaddleOCR).
Đây KHÔNG phải benchmark trên manga thật — fixture là ảnh tổng hợp; xem docs/TEST_LOG.md.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.services.interfaces import BBox
from app.services.ocr.engines import MangaOCREngine, PaddleOCREngine

pytestmark = pytest.mark.skipif(
    os.environ.get("MTE_RUN_OCR_TESTS") != "1",
    reason="Cần MTE_RUN_OCR_TESTS=1 và môi trường có manga-ocr/paddleocr",
)


def test_paddleocr_doc_duoc_chu_tren_fixture_tieng_anh(fixtures_dir):
    """few_bubbles.png có 2 bubble: 'HELLO THERE' và 'GOODBYE' (chữ Latin)."""
    engine = PaddleOCREngine(lang="en")
    # bbox lấy từ chính kết quả detect của M2 trên ảnh này
    text, confidence = engine.recognize(
        os.path.join(fixtures_dir, "few_bubbles.png"), BBox(x=345, y=244, w=151, h=89)
    )
    assert text, "PaddleOCR trả rỗng trên vùng chữ rõ"
    assert "HELLO" in text.upper() or "THERE" in text.upper(), text
    assert confidence is not None and 0.0 <= confidence <= 1.0


def test_mangaocr_doc_duoc_anh_mau_tieng_nhat_cua_chinh_thu_vien():
    """manga-ocr đóng gói sẵn 1 ảnh mẫu tiếng Nhật (assets/example.jpg) dùng để warmup.

    Dùng đúng ảnh đó làm phép thử thật cho nhánh `ja` — không cần ảnh manga có bản quyền.
    """
    manga_ocr = pytest.importorskip("manga_ocr")
    example = Path(manga_ocr.__file__).parent / "assets" / "example.jpg"
    if not example.is_file():
        pytest.skip("Bản manga-ocr này không kèm ảnh mẫu")

    from PIL import Image

    with Image.open(example) as im:
        w, h = im.size

    engine = MangaOCREngine(device="cpu")
    text, confidence = engine.recognize(str(example), BBox(x=0, y=0, w=w, h=h))

    assert text.strip(), "manga-ocr trả rỗng trên chính ảnh mẫu của nó"
    assert confidence is None, "manga-ocr không có confidence — không được bịa số"
    # chữ Nhật: phải có ít nhất 1 ký tự ngoài bảng ASCII
    assert any(ord(c) > 127 for c in text), text
