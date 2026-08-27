"""Chạy LaMa THẬT trên fixture — chậm (~54s/ảnh CPU), bật bằng env:

    MTE_RUN_MODEL_TESTS=1 pytest tests/test_inpaint_real_model.py -q
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.core.config import get_settings
from app.services.inpaint.lama import LamaInpainter
from app.services.interfaces import BBox, IInpainter

pytestmark = pytest.mark.skipif(
    os.environ.get("MTE_RUN_MODEL_TESTS") != "1",
    reason="Cần MTE_RUN_MODEL_TESTS=1 (nạp weight 197MB, ~54s/ảnh)",
)


def _weights() -> str:
    path = os.environ.get("INPAINT_WEIGHTS_PATH") or get_settings().inpaint_weights_path
    if not Path(path).is_file():
        pytest.skip(f"Chưa có weight LaMa tại {path}")
    return path


def test_inpaint_that_xoa_chu_va_giu_nguyen_anh_goc(fixtures_dir, tmp_path):
    src = Path(fixtures_dir) / "few_bubbles.png"
    work = tmp_path / "page.png"
    work.write_bytes(src.read_bytes())
    before = hashlib.md5(work.read_bytes()).hexdigest()

    inpainter = LamaInpainter(weights_path=_weights(), device="cpu")
    assert isinstance(inpainter, IInpainter)

    # bbox thật do M2 detect trên chính ảnh này
    boxes = [BBox(345, 244, 151, 89), BBox(690, 1271, 219, 43)]
    clean = inpainter.inpaint(str(work), boxes)

    assert Path(clean).is_file()
    assert hashlib.md5(work.read_bytes()).hexdigest() == before, "ảnh gốc bị ghi đè"

    with Image.open(work) as a, Image.open(clean) as b:
        assert a.size == b.size
        orig = np.asarray(a.convert("RGB"), dtype=np.int16)
        out = np.asarray(b.convert("RGB"), dtype=np.int16)

    # vùng mask phải đổi; vùng ngoài mask giữ nguyên từng pixel
    x, y, w, h = 345, 244, 151, 89
    assert np.abs(orig[y : y + h, x : x + w] - out[y : y + h, x : x + w]).mean() > 5
    assert np.array_equal(orig[0:100, 0:100], out[0:100, 0:100])
