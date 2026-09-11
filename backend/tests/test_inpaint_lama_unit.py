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


class TestTranOCat:
    """E23 — tự báo hỏng thay vì để hệ điều hành giết worker.

    Đo `VmHWM` (đỉnh thật) trên đường chạy theo cụm, container 4096MB (worker ~3850MB):

        0,80 Mpx -> 1697 MB (44%) · 1,40 -> 2076 (54%) · 2,00 -> 3367 (87%)
        2,57 Mpx -> 3368 MB (87%) · 2,60 -> 3710 (96%) · 3,20 -> BỊ GIẾT

    Đường cong **có bậc**: 2,00 và 2,57 gần như bằng nhau, rồi 2,60 nhảy +342 MB. Nên dùng TRẦN
    DIỆN TÍCH đo được, không dùng công thức GB/Mpx (tỉ lệ chạy từ 1,28 đến 2,07 tuỳ cỡ).
    """

    @staticmethod
    def _may(tmp_path, **kw):
        return LamaInpainter(weights_path=str(tmp_path / "w.onnx"), **kw)

    def test_o_qua_lon_thi_bao_hong_TRUOC_khi_chay(self, tmp_path, monkeypatch):
        """Phải hỏng TRƯỚC khi gọi model — gọi rồi mới hỏng là đã tốn bộ nhớ rồi."""
        p = _make_image(tmp_path, size=(2000, 2000))  # 4 Mpx
        d = self._may(tmp_path, whole_page_max_mpx=10.0, max_crop_mpx=2.6)
        goi = []
        monkeypatch.setattr(d, "_get_session", lambda: goi.append(1) or _FakeSession())

        with pytest.raises(InpaintFailed) as e:
            d.inpaint(str(p), [BBox(x=10, y=10, w=50, h=50)])
        assert "crop_too_large" in str(e.value)
        assert goi == [], "đã gọi tới model — nghĩa là kiểm SAU khi tốn bộ nhớ, vô nghĩa"

    def test_cau_loi_noi_du_de_nguoi_dung_xu_ly_duoc(self, tmp_path):
        p = _make_image(tmp_path, size=(2000, 2000))
        d = self._may(tmp_path, whole_page_max_mpx=10.0, max_crop_mpx=2.6)
        with pytest.raises(InpaintFailed) as e:
            d.inpaint(str(p), [BBox(x=10, y=10, w=50, h=50)])
        chu = str(e.value)
        assert "2000x2000" in chu, "phải nói cỡ trang"
        assert "2.60" in chu or "2.6" in chu, "phải nói trần là bao nhiêu"
        assert "hạ độ phân giải" in chu, "phải nói cách xử lý, không chỉ nói 'hỏng'"

    def test_TRANG_THAT_cua_E23_KHONG_bi_chan(self, tmp_path, monkeypatch):
        """Trang 1200x2144 = 2,57 Mpx: 1 cụm phủ cả trang, nhưng ĐO THẬT là 3368 MB — vừa.

        Test này tồn tại vì bản đầu của tôi dùng công thức 1,6 GB/Mpx và **đã** chặn đúng trang
        này (dự đoán 4,1 GB cho một trang thật sự cần 3,37 GB). Chặn oan là hỏng đúng thứ mình
        sinh ra để cứu.
        """
        p = _make_image(tmp_path, size=(1200, 2144))
        d = self._may(tmp_path, whole_page_max_mpx=2.5, max_crop_mpx=2.6)
        monkeypatch.setattr(d, "_get_session", lambda: _FakeSession())
        vung = [BBox(x=100, y=40 + i * 190, w=1000, h=180) for i in range(11)]
        assert Path(d.inpaint(str(p), vung)).is_file(), "chặn oan một trang đo được là vừa"

    def test_CUM_gop_thanh_ca_trang_O_CO_LON_thi_bi_chan(self, tmp_path, monkeypatch):
        """Cỡ đọc 1600x2259 (3,6 Mpx): gộp thành 1 cụm cả trang ⇒ vượt thật, phải chặn.

        Kiểm ô cắt LỚN NHẤT chứ không kiểm cỡ trang: nếu chỉ tin "đã chuyển sang cụm là an toàn"
        thì cảnh này lọt lưới — và 3,2 Mpx đã BỊ GIẾT trong phép đo.
        """
        p = _make_image(tmp_path, size=(1600, 2259))
        d = self._may(tmp_path, whole_page_max_mpx=2.5, max_crop_mpx=2.6)
        goi = []
        monkeypatch.setattr(d, "_get_session", lambda: goi.append(1) or _FakeSession())
        vung = [BBox(x=120, y=40 + i * 200, w=1360, h=180) for i in range(11)]

        with pytest.raises(InpaintFailed) as e:
            d.inpaint(str(p), vung)
        assert "crop_too_large" in str(e.value)
        assert "cụm lớn nhất" in str(e.value), "phải nói rõ chặn vì CỤM, không phải vì cỡ trang"
        assert goi == []

    def test_CUM_nho_thi_KHONG_bi_chan(self, tmp_path, monkeypatch):
        """Cảnh mà chiến lược cụm sinh ra để phục vụ: trang lớn nhưng chữ gom một góc."""
        p = _make_image(tmp_path, size=(1200, 2144))
        d = self._may(tmp_path, whole_page_max_mpx=2.5, max_crop_mpx=2.6)
        monkeypatch.setattr(d, "_get_session", lambda: _FakeSession())
        assert Path(d.inpaint(str(p), [BBox(x=50, y=50, w=200, h=150)])).is_file()

    def test_dat_tran_0_la_TAT_phep_kiem(self, tmp_path, monkeypatch):
        """Phải có đường tắt tường minh: bàn thử khác có thể có nhiều RAM hơn production."""
        p = _make_image(tmp_path, size=(2000, 2000))
        d = self._may(tmp_path, whole_page_max_mpx=10.0, max_crop_mpx=0)
        monkeypatch.setattr(d, "_get_session", lambda: _FakeSession())
        assert Path(d.inpaint(str(p), [BBox(x=10, y=10, w=50, h=50)])).is_file()
