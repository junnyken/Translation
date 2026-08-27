"""Unit — CTDDetector: đúng Protocol M1, tiền/hậu xử lý đúng, thiếu weight thì báo rõ."""
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.services.detect.ctd import CTDDetector, ModelWeightsMissing
from app.services.interfaces import BBox, IDetector


class _FakeSession:
    """Giả lập ONNX session: trả đúng shape output thật [1, N, 4+1+2]."""

    def __init__(self, rows: list[list[float]]):
        self._out = np.array([rows], dtype=np.float32)

    def get_inputs(self):
        class _I:
            name = "images"

        return [_I()]

    def run(self, _outputs, _feed):
        seg = np.zeros((1, 1, 1024, 1024), dtype=np.float32)
        det = np.zeros((1, 2, 1024, 1024), dtype=np.float32)
        return [self._out, seg, det]


@pytest.fixture
def image_file(tmp_path) -> Path:
    p = tmp_path / "page.png"
    Image.new("RGB", (2048, 1024), "white").save(p)
    return p


def _detector(**kw) -> CTDDetector:
    return CTDDetector(weights_path="/khong/co/that.onnx", **kw)


def test_ctd_detector_dung_protocol_idetector():
    assert isinstance(_detector(), IDetector)


def test_detect_tra_ve_list_bbox_dung_contract_m1(image_file, monkeypatch):
    d = _detector()
    # ảnh 2048x1024 -> letterbox scale 0.5, pad_y=256; box giữa ảnh
    monkeypatch.setattr(d, "_get_session", lambda: _FakeSession([[512, 512, 100, 50, 0.9, 0.8, 0.1]]))
    out = d.detect(str(image_file))
    assert isinstance(out, list)
    assert all(isinstance(b, BBox) for b in out)
    assert len(out) == 1


def test_toa_do_duoc_map_ve_he_anh_goc(image_file, monkeypatch):
    d = _detector()
    monkeypatch.setattr(d, "_get_session", lambda: _FakeSession([[512, 512, 100, 50, 0.9, 0.8, 0.1]]))
    r = d.detect_regions(str(image_file))[0]
    # scale=0.5, pad_x=0, pad_y=256 -> tâm (512,512) => ảnh gốc (1024, 512)
    assert r.bbox.x == pytest.approx((512 - 50) / 0.5, abs=1)
    assert r.bbox.y == pytest.approx((512 - 25 - 256) / 0.5, abs=1)
    assert r.bbox.w == pytest.approx(200, abs=1)
    assert r.bbox.h == pytest.approx(100, abs=1)


def test_confidence_la_tich_objectness_va_diem_lop(image_file, monkeypatch):
    d = _detector()
    monkeypatch.setattr(d, "_get_session", lambda: _FakeSession([[512, 512, 100, 50, 0.5, 0.6, 0.2]]))
    r = d.detect_regions(str(image_file))[0]
    assert r.confidence == pytest.approx(0.5 * 0.6, abs=1e-5)
    assert r.cls == 0


def test_box_duoi_san_nhieu_bi_bo(image_file, monkeypatch):
    d = _detector(raw_min_conf=0.25)
    monkeypatch.setattr(
        d, "_get_session", lambda: _FakeSession([[512, 512, 100, 50, 0.2, 0.5, 0.1]])
    )
    assert d.detect_regions(str(image_file)) == []


def test_khong_tu_loc_theo_conf_threshold(image_file, monkeypatch):
    """Detector chỉ trả kết quả thô — lọc/gắn cờ low_confidence là việc của Celery task."""
    d = _detector(conf_threshold=0.9, raw_min_conf=0.25)
    monkeypatch.setattr(
        d, "_get_session", lambda: _FakeSession([[512, 512, 100, 50, 0.6, 0.7, 0.1]])
    )
    regions = d.detect_regions(str(image_file))
    assert len(regions) == 1  # 0.42 < 0.9 nhưng KHÔNG bị loại ở tầng detector
    assert regions[0].confidence < d.conf_threshold


def test_box_vuot_bien_bi_clamp_khong_ghi_toa_do_am(image_file, monkeypatch):
    d = _detector()
    monkeypatch.setattr(
        d, "_get_session", lambda: _FakeSession([[0, 300, 400, 400, 0.9, 0.9, 0.1]])
    )
    r = d.detect_regions(str(image_file))[0]
    assert r.bbox.x >= 0 and r.bbox.y >= 0
    assert r.bbox.x + r.bbox.w <= 2048
    assert r.bbox.y + r.bbox.h <= 1024


def test_nms_duoc_ap_dung_cho_box_trung_nhau(image_file, monkeypatch):
    d = _detector(nms_iou=0.45)
    rows = [
        [512, 512, 100, 50, 0.9, 0.9, 0.1],
        [514, 513, 100, 50, 0.8, 0.9, 0.1],  # gần trùng
        [300, 400, 100, 50, 0.7, 0.9, 0.1],  # tách biệt, nằm trong vùng ảnh sau letterbox
    ]
    monkeypatch.setattr(d, "_get_session", lambda: _FakeSession(rows))
    assert len(d.detect_regions(str(image_file))) == 2


def test_thieu_file_weight_bao_loi_ro_khong_detect_bang_weight_gia(image_file):
    d = _detector()
    with pytest.raises(ModelWeightsMissing) as exc:
        d.detect_regions(str(image_file))
    assert "MODEL_WEIGHTS_PATH" in str(exc.value)


def test_thieu_file_anh_bao_loi_ro(tmp_path):
    with pytest.raises(FileNotFoundError):
        _detector().detect_regions(str(tmp_path / "khong-ton-tai.png"))


def test_letterbox_giu_ty_le_va_kich_thuoc_dau_vao(image_file):
    d = _detector(input_size=1024)
    with Image.open(image_file) as im:
        tensor, scale, pad_x, pad_y = d._letterbox(im.convert("RGB"))
    assert tensor.shape == (1, 3, 1024, 1024)
    assert scale == pytest.approx(0.5)
    assert (pad_x, pad_y) == (0, 256)
    assert 0.0 <= tensor.min() and tensor.max() <= 1.0
