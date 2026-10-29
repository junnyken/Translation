"""Unit — crop bbox float → pixel int (M3 §7.1). Crop sai thì OCR đúng cũng vô nghĩa."""
import pytest
from PIL import Image

from app.services.interfaces import BBox
from app.services.ocr.crop import InvalidCropBox, bbox_to_pixel_box, crop_region


def test_convert_co_ban():
    assert bbox_to_pixel_box(BBox(10, 20, 100, 50), 500, 500) == (10, 20, 110, 70)


def test_lam_tron_theo_toa_do_tuyet_doi_khong_lech_1px():
    """x=10.6, w=100.7 -> right = round(111.3) = 111, KHÔNG phải round(10.6)+round(100.7)=112."""
    left, top, right, bottom = bbox_to_pixel_box(BBox(10.6, 20.4, 100.7, 50.3), 500, 500)
    assert (left, right) == (11, 111)
    assert (top, bottom) == (20, 71)


def test_bbox_cham_bien_phai_duoi_khong_tran():
    left, top, right, bottom = bbox_to_pixel_box(BBox(400, 300, 100, 200), 500, 500)
    assert (right, bottom) == (500, 500)


def test_bbox_vuot_bien_bi_clamp():
    left, top, right, bottom = bbox_to_pixel_box(BBox(450, 450, 200, 200), 500, 500)
    assert (right, bottom) == (500, 500)
    assert (left, top) == (450, 450)


def test_bbox_toa_do_am_bi_clamp_ve_0():
    left, top, right, bottom = bbox_to_pixel_box(BBox(-20, -10, 100, 50), 500, 500)
    assert (left, top) == (0, 0)
    assert (right, bottom) == (80, 40)


def test_bbox_nam_ngoai_anh_bao_loi():
    with pytest.raises(InvalidCropBox):
        bbox_to_pixel_box(BBox(600, 600, 50, 50), 500, 500)


def test_bbox_dien_tich_0_bao_loi():
    with pytest.raises(InvalidCropBox):
        bbox_to_pixel_box(BBox(10, 10, 0.2, 50), 500, 500)


def test_anh_kich_thuoc_khong_hop_le_bao_loi():
    with pytest.raises(InvalidCropBox):
        bbox_to_pixel_box(BBox(0, 0, 10, 10), 0, 500)


def test_crop_region_tra_dung_kich_thuoc():
    img = Image.new("RGB", (400, 300), "white")
    crop = crop_region(img, BBox(10, 20, 100, 50))
    assert crop.size == (100, 50)


def test_crop_khong_noi_them_le():
    """Không tự nới lề — giữ đúng vùng detector chỉ ra."""
    img = Image.new("RGB", (400, 300), "white")
    assert crop_region(img, BBox(0, 0, 400, 300)).size == (400, 300)
