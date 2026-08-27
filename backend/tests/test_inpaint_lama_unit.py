"""Unit — LamaInpainter: đúng Protocol M1, pad bội số 8, KHÔNG ghi đè ảnh gốc (M4 §7.1)."""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.services.inpaint.lama import (
    InpaintFailed,
    InpaintWeightsMissing,
    LamaInpainter,
    _pad_to_multiple,
)
from app.services.inpaint.mask import InvalidMask
from app.services.interfaces import BBox, IInpainter


class _FakeSession:
    """Giả lập ONNX: trả ảnh toàn màu xám, ghi lại shape đầu vào để kiểm pad."""

    def __init__(self, fill: float = 0.5, out_shape=None):
        self.fill = fill
        self.seen_shapes: list[tuple] = []
        self.out_shape = out_shape

    def get_inputs(self):
        class _I:
            def __init__(self, name):
                self.name = name

        return [_I("image"), _I("mask")]

    def run(self, _outputs, feed):
        img = feed["image"]
        self.seen_shapes.append(img.shape)
        shape = self.out_shape or img.shape
        return [np.full(shape, self.fill, dtype=np.float32)]


def _make_image(tmp_path: Path, size=(120, 80), color=(200, 30, 30)) -> Path:
    p = tmp_path / "page.png"
    Image.new("RGB", size, color).save(p)
    return p


def _md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def _inpainter(**kw) -> LamaInpainter:
    return LamaInpainter(weights_path="/khong/co/that.onnx", **kw)


def test_dung_protocol_iinpainter():
    assert isinstance(_inpainter(), IInpainter)


def test_pad_ve_boi_so_8():
    arr = np.zeros((1, 3, 101, 99), dtype=np.float32)
    padded, pad_h, pad_w = _pad_to_multiple(arr)
    assert padded.shape[-2] % 8 == 0 and padded.shape[-1] % 8 == 0
    assert (pad_h, pad_w) == (3, 5)


def test_khong_pad_khi_da_chia_het_8():
    arr = np.zeros((1, 3, 64, 32), dtype=np.float32)
    padded, pad_h, pad_w = _pad_to_multiple(arr)
    assert padded.shape == arr.shape and (pad_h, pad_w) == (0, 0)


def test_anh_le_duoc_pad_truoc_khi_vao_model(tmp_path, monkeypatch):
    """LaMa vỡ nếu cạnh không chia hết 8 (đã đo thật) -> phải pad."""
    img = _make_image(tmp_path, size=(101, 99))
    d = _inpainter()
    fake = _FakeSession()
    monkeypatch.setattr(d, "_get_session", lambda: fake)

    out_path = d.inpaint(str(img), [BBox(10, 10, 30, 30)])

    assert fake.seen_shapes[0][-2] % 8 == 0
    assert fake.seen_shapes[0][-1] % 8 == 0
    with Image.open(out_path) as im:
        assert im.size == (101, 99)  # trả về đúng kích thước ảnh gốc, không phải kích thước pad


def test_khong_ghi_de_anh_goc(tmp_path, monkeypatch):
    """INVARIANT QUAN TRỌNG NHẤT của M4."""
    img = _make_image(tmp_path)
    before = _md5(img)
    d = _inpainter()
    monkeypatch.setattr(d, "_get_session", lambda: _FakeSession())

    out_path = d.inpaint(str(img), [BBox(10, 10, 40, 20)])

    assert Path(out_path) != img
    assert Path(out_path).is_file()
    assert _md5(img) == before, "ảnh gốc đã bị thay đổi"
    assert _md5(Path(out_path)) != before, "ảnh clean trùng hệt ảnh gốc"


def test_chi_thay_pixel_trong_mask(tmp_path, monkeypatch):
    img = _make_image(tmp_path, size=(100, 60), color=(200, 30, 30))
    d = _inpainter()
    monkeypatch.setattr(d, "_get_session", lambda: _FakeSession(fill=0.0))  # model trả màu đen

    out_path = d.inpaint(str(img), [BBox(10, 10, 20, 20)])

    arr = np.asarray(Image.open(out_path).convert("RGB"))
    assert tuple(arr[0, 0]) == (200, 30, 30), "pixel ngoài mask bị đổi"
    assert tuple(arr[15, 15]) == (0, 0, 0), "pixel trong mask chưa được thay"


def test_ten_file_clean_khac_ten_anh_goc(tmp_path):
    d = _inpainter()
    target = d.clean_path_for(str(tmp_path / "abc.jpg"))
    assert target.name == "abc_clean.png"


def test_masks_rong_bao_loi(tmp_path, monkeypatch):
    img = _make_image(tmp_path)
    d = _inpainter()
    monkeypatch.setattr(d, "_get_session", lambda: _FakeSession())
    with pytest.raises(InvalidMask):
        d.inpaint(str(img), [])


def test_thieu_weight_bao_loi_ro_khong_lang_le_fallback(tmp_path):
    img = _make_image(tmp_path)
    with pytest.raises(InpaintWeightsMissing) as exc:
        _inpainter().inpaint(str(img), [BBox(1, 1, 10, 10)])
    assert "INPAINT_WEIGHTS_PATH" in str(exc.value)


def test_thieu_anh_bao_loi(tmp_path):
    with pytest.raises(FileNotFoundError):
        _inpainter().inpaint(str(tmp_path / "khong-co.png"), [BBox(1, 1, 5, 5)])


def test_model_tra_kich_thuoc_la_thi_bao_loi(tmp_path, monkeypatch):
    img = _make_image(tmp_path, size=(64, 64))
    d = _inpainter()
    monkeypatch.setattr(d, "_get_session", lambda: _FakeSession(out_shape=(1, 3, 32, 32)))
    with pytest.raises(InpaintFailed):
        d.inpaint(str(img), [BBox(1, 1, 10, 10)])


def test_dilated_masks_khop_voi_mask_da_dung(tmp_path):
    d = _inpainter(dilate_ratio=0.10)
    boxes = d.dilated_masks(200, 200, [BBox(50, 50, 100, 40)])
    assert boxes[0].w == pytest.approx(110.0)
    assert boxes[0].h == pytest.approx(44.0)
