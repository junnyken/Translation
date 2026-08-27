"""Chạy ONNX THẬT trên fixture — chậm (~40s/ảnh CPU) nên phải bật bằng env.

    MTE_RUN_MODEL_TESTS=1 pytest tests/test_detect_real_model.py -q

Đây KHÔNG phải benchmark độ chính xác trên manga thật: fixture là trang tổng hợp do repo
tự sinh. Số liệu thật ghi trong docs/TEST_LOG.md.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.services.detect.ctd import CTDDetector
from app.services.interfaces import IDetector

pytestmark = pytest.mark.skipif(
    os.environ.get("MTE_RUN_MODEL_TESTS") != "1",
    reason="Cần MTE_RUN_MODEL_TESTS=1 (test nạp model 91MB, ~40s/ảnh)",
)

#: Số vùng chữ đếm tay trên từng fixture (xem test_fixtures/make_fixtures.py).
EXPECTED = {"many_bubbles.png": 6, "few_bubbles.png": 2, "loose_sfx.png": 4}


def _weights() -> str:
    path = os.environ.get("MODEL_WEIGHTS_PATH") or get_settings().model_weights_path
    if not Path(path).is_file():
        pytest.skip(f"Chưa có weight tại {path}")
    return path


@pytest.mark.parametrize("name,expected", EXPECTED.items())
def test_detect_that_tren_fixture(name, expected, fixtures_dir):
    detector = CTDDetector(weights_path=_weights(), device="cpu")
    regions = detector.detect_regions(os.path.join(fixtures_dir, name))

    assert isinstance(detector, IDetector)
    assert abs(len(regions) - expected) <= 1, f"{name}: {len(regions)} vùng, đếm tay {expected}"

    from PIL import Image

    with Image.open(os.path.join(fixtures_dir, name)) as im:
        w, h = im.size
    for r in regions:
        assert r.bbox.x >= 0 and r.bbox.y >= 0, f"bbox âm: {r.bbox}"
        assert r.bbox.x + r.bbox.w <= w + 1, f"bbox vượt chiều rộng ảnh: {r.bbox}"
        assert r.bbox.y + r.bbox.h <= h + 1, f"bbox vượt chiều cao ảnh: {r.bbox}"
        assert 0.0 <= r.confidence <= 1.0
