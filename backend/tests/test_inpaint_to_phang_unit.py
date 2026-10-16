"""E69 — tô phẳng vùng chữ trên nền một màu (ý tưởng từ Koharu), bỏ qua LaMa cho vùng đó.

Bất biến được canh:
- Nền phẳng (trắng, hoặc một màu nhạt) ⇒ khung được tô ĐÚNG màu nền, model không được gọi.
- Dải viền dính mực / hoạ tiết, hoặc trong khung chủ yếu là tranh ⇒ KHÔNG tô, giữ LaMa.
- Trang có cả hai loại ⇒ model chỉ nhận mặt nạ của khung chưa tô.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from app.services.inpaint.lama import LamaInpainter
from app.services.inpaint.to_phang import mau_nen_phang, to_phang
from app.services.interfaces import BBox


def _chu(anh: np.ndarray, x: int, y: int, w: int, h: int, mau=(0, 0, 0)) -> None:
    """Vẽ "chữ": các vạch ngang mảnh — ~25% diện tích khung, như nét chữ thật."""
    for yy in range(y + 2, y + h - 2, 8):
        anh[yy:yy + 2, x + 3:x + w - 3] = mau


def test_bong_bong_trang_thi_to_trang():
    anh = np.full((200, 300, 3), 255, np.uint8)
    _chu(anh, 100, 60, 80, 40)
    kq = to_phang(anh, [BBox(96, 56, 88, 48)])
    assert kq.da_to == (0,) and kq.con_lai == ()
    assert (anh[56:104, 96:184] == 255).all()


def test_nen_mau_nhat_thi_to_dung_mau_do():
    anh = np.empty((200, 300, 3), np.uint8)
    anh[:] = (250, 236, 200)
    _chu(anh, 100, 60, 80, 40, mau=(40, 20, 10))
    kq = to_phang(anh, [BBox(96, 56, 88, 48)])
    assert kq.da_to == (0,)
    assert (anh[56:104, 96:184] == (250, 236, 200)).all()


def test_nhieu_jpeg_nhe_van_coi_la_phang():
    rng = np.random.default_rng(0)
    anh = np.clip(255 - np.abs(rng.normal(0, 4, (200, 300, 3))), 0, 255).astype(np.uint8)
    _chu(anh, 100, 60, 80, 40)
    assert to_phang(anh, [BBox(96, 56, 88, 48)]).da_to == (0,)


def test_nen_hoa_tiet_thi_khong_to():
    rng = np.random.default_rng(1)
    anh = rng.integers(0, 256, (200, 300, 3), dtype=np.uint8)
    goc = anh.copy()
    kq = to_phang(anh, [BBox(96, 56, 88, 48)])
    assert kq.da_to == () and kq.con_lai == (0,)
    assert np.array_equal(anh, goc), "không tô thì không được đụng vào ảnh"


def test_khung_cham_vien_bong_bong_thi_khong_dung_vao_net_vien():
    """Trước E86: dải viền dính nét viền ⇒ KHÔNG tô, để LaMa. E86 (tô từng phần): nền đa số vẫn
    trắng ⇒ tô phần trong khung, nhưng nét viền nằm NGOÀI khung phải còn nguyên — đó mới là điều
    ca này canh (tô là xoá mất nét)."""
    anh = np.full((200, 300, 3), 255, np.uint8)
    anh[50:53, :] = 0  # nét viền bong bóng chạy ngay sát mép trên khung
    _chu(anh, 100, 60, 80, 40)
    to_phang(anh, [BBox(96, 56, 88, 48)])
    assert (anh[50:53, :] == 0).all(), "nét viền bị tô mất"
    assert (anh[56:104, 96:184] == 255).all(), "chữ trong khung chưa được xoá"


def test_net_vien_bong_bong_cham_dai_vien_nhung_khong_vao_khung_thi_van_to():
    """Ca đo được trên trang thật (E69): vài % dải viền là nét viền bong bóng, khung vẫn sạch."""
    anh = np.full((200, 300, 3), 255, np.uint8)
    anh[48:50, 150:170] = 0  # một mẩu nét viền chạm dải viền phía trên, NGOÀI khung
    _chu(anh, 100, 60, 80, 40)
    assert to_phang(anh, [BBox(96, 56, 88, 48)]).da_to == (0,)
    assert (anh[48:50, 150:170] == 0).all(), "nét ngoài khung không được đụng tới"


def test_net_cat_ngang_mep_khung_thi_khong_to():
    """Nét vẽ CẮT VÀO khung (ở mép) — tô là xoá mất nét, phải để LaMa."""
    anh = np.full((200, 300, 3), 255, np.uint8)
    anh[56:104, 97:99] = 0  # vạch dọc chạy suốt mép trái BÊN TRONG khung
    _chu(anh, 100, 60, 80, 40)
    assert to_phang(anh, [BBox(96, 56, 88, 48)]).da_to == ()


def test_trong_khung_chu_yeu_la_tranh_thi_khong_to():
    anh = np.full((200, 300, 3), 255, np.uint8)
    anh[60:100, 100:180] = 30  # khối tranh đặc chiếm gần trọn khung, viền ngoài vẫn trắng
    assert to_phang(anh, [BBox(96, 56, 88, 48)]).da_to == ()


def test_dai_vien_khong_lay_mau_tu_chu_cua_khung_ben_canh():
    anh = np.full((200, 300, 3), 255, np.uint8)
    _chu(anh, 40, 60, 60, 40)
    _chu(anh, 104, 60, 60, 40)  # sát khung trái: dải viền của khung này phủ lên chữ khung kia
    kq = to_phang(anh, [BBox(36, 56, 66, 48), BBox(103, 56, 66, 48)])
    assert kq.da_to == (0, 1)


def test_qua_it_mau_thi_khong_ket_luan():
    assert mau_nen_phang(np.full((15, 3), 255, np.uint8)) is None
    assert mau_nen_phang(np.full((16, 3), 255, np.uint8)) is not None


# ---------- nối vào LamaInpainter ----------

class _ModelGhi:
    """Thay `_chay_model`: ghi lại mặt nạ model nhận được, trả ảnh tô xám 128."""

    def __init__(self):
        self.mat_na = []

    def __call__(self, rgb, mask):
        self.mat_na.append(mask.copy())
        return np.full_like(rgb, 128 / 255.0)


def _luu(tmp_path: Path, anh: np.ndarray) -> Path:
    p = tmp_path / "trang.png"
    Image.fromarray(anh).save(p)
    return p


def test_moi_vung_deu_phang_thi_khong_nap_model(tmp_path):
    anh = np.full((200, 300, 3), 255, np.uint8)
    _chu(anh, 100, 60, 80, 40)
    # weight không tồn tại: nếu model bị nạp thì sẽ ném InpaintWeightsMissing
    may = LamaInpainter(weights_path=str(tmp_path / "khong_co.onnx"))
    sach = may.inpaint(str(_luu(tmp_path, anh)), [BBox(100, 60, 80, 40)])
    with Image.open(sach) as im:
        assert (np.asarray(im.convert("RGB")) == 255).all()


def test_trang_tron_thi_model_chi_nhan_khung_chua_to(tmp_path):
    rng = np.random.default_rng(2)
    anh = np.full((200, 400, 3), 255, np.uint8)
    anh[:, 250:] = rng.integers(0, 256, (200, 150, 3), dtype=np.uint8)  # nửa phải là tranh
    _chu(anh, 40, 60, 80, 40)
    _chu(anh, 290, 60, 80, 40)
    may = LamaInpainter(weights_path=str(tmp_path / "w.onnx"), dilate_ratio=0.0)
    ghi = _ModelGhi()
    may._chay_model = ghi
    sach = may.inpaint(str(_luu(tmp_path, anh)), [BBox(40, 60, 80, 40), BBox(290, 60, 80, 40)])

    assert len(ghi.mat_na) == 1
    m = ghi.mat_na[0]
    assert m[60:100, 290:370].all(), "khung trên nền tranh phải vào model"
    assert not m[60:100, 40:120].any(), "khung đã tô phẳng không được vào model"
    with Image.open(sach) as im:
        out = np.asarray(im.convert("RGB"))
    assert (out[60:100, 40:120] == 255).all()
    assert (out[60:100, 290:370] == 128).all()


def test_tat_flat_fill_thi_giu_hanh_vi_cu(tmp_path):
    anh = np.full((200, 300, 3), 255, np.uint8)
    _chu(anh, 100, 60, 80, 40)
    may = LamaInpainter(weights_path=str(tmp_path / "w.onnx"), flat_fill=False)
    ghi = _ModelGhi()
    may._chay_model = ghi
    may.inpaint(str(_luu(tmp_path, anh)), [BBox(100, 60, 80, 40)])
    assert len(ghi.mat_na) == 1
