"""Unit — hình học bbox của M2 (đổi format, clamp, chồng lấp, NMS)."""
import pytest

from app.services.detect.geometry import (
    Detection,
    InvalidBBox,
    build_bbox,
    iou,
    mark_overlap_suspects,
    nms,
    overlap_ratio,
)
from app.services.interfaces import BBox


class TestBuildBBox:
    def test_doi_xyxy_sang_xywh_dung_cong_thuc(self):
        b = build_bbox(10, 20, 110, 220, image_w=500, image_h=500)
        assert (b.x, b.y, b.w, b.h) == (10, 20, 100, 200)

    def test_toa_do_am_bi_clamp_ve_0(self):
        b = build_bbox(-50, -30, 100, 80, image_w=500, image_h=500)
        assert (b.x, b.y) == (0, 0)
        assert (b.w, b.h) == (100, 80)

    def test_vuot_bien_anh_bi_clamp_ve_kich_thuoc_anh(self):
        b = build_bbox(400, 400, 900, 700, image_w=500, image_h=500)
        assert b.x + b.w <= 500
        assert b.y + b.h <= 500
        assert (b.w, b.h) == (100, 100)

    def test_box_nam_hoan_toan_ngoai_anh_bao_loi_ro_rang(self):
        with pytest.raises(InvalidBBox):
            build_bbox(600, 600, 700, 700, image_w=500, image_h=500)

    def test_box_dien_tich_0_bao_loi(self):
        with pytest.raises(InvalidBBox):
            build_bbox(10, 10, 10, 50, image_w=500, image_h=500)

    def test_toa_do_dao_nguoc_van_ra_box_hop_le(self):
        b = build_bbox(110, 220, 10, 20, image_w=500, image_h=500)
        assert (b.x, b.y, b.w, b.h) == (10, 20, 100, 200)

    def test_anh_kich_thuoc_khong_hop_le_bao_loi(self):
        with pytest.raises(InvalidBBox):
            build_bbox(0, 0, 10, 10, image_w=0, image_h=100)


class TestOverlap:
    def test_khong_cham_nhau_thi_bang_0(self):
        assert overlap_ratio(BBox(0, 0, 10, 10), BBox(100, 100, 10, 10)) == 0.0

    def test_box_nho_nam_tron_trong_box_lon_thi_bang_1(self):
        assert overlap_ratio(BBox(0, 0, 100, 100), BBox(10, 10, 20, 20)) == 1.0

    def test_nguong_bien_79_phan_tram_khong_gan_co(self):
        # box nhỏ 100x100 (=10.000), phần chồng lấp 79x100 = 7.900 -> 79%
        a = BBox(0, 0, 200, 100)
        b = BBox(121, 0, 100, 100)  # chồng lấp từ x=121..200 = 79px
        ratio = overlap_ratio(a, b)
        assert ratio == pytest.approx(0.79, abs=1e-9)
        assert mark_overlap_suspects([a, b], threshold=0.8) == [False, False]

    def test_nguong_bien_81_phan_tram_co_gan_co(self):
        a = BBox(0, 0, 200, 100)
        b = BBox(119, 0, 100, 100)  # chồng lấp 81px
        assert overlap_ratio(a, b) == pytest.approx(0.81, abs=1e-9)
        assert mark_overlap_suspects([a, b], threshold=0.8) == [True, True]

    def test_dung_80_phan_tram_khong_gan_co_vi_dieu_kien_la_lon_hon(self):
        a = BBox(0, 0, 200, 100)
        b = BBox(120, 0, 100, 100)
        assert overlap_ratio(a, b) == pytest.approx(0.80, abs=1e-9)
        assert mark_overlap_suspects([a, b], threshold=0.8) == [False, False]

    def test_chi_gan_co_khong_xoa_box_nao(self):
        boxes = [BBox(0, 0, 100, 100), BBox(5, 5, 90, 90), BBox(500, 500, 50, 50)]
        flags = mark_overlap_suspects(boxes, threshold=0.8)
        assert len(flags) == len(boxes)  # không box nào biến mất
        assert flags == [True, True, False]

    def test_iou_hai_box_trung_khop_bang_1(self):
        assert iou(BBox(0, 0, 10, 10), BBox(0, 0, 10, 10)) == 1.0


class TestNMS:
    def test_giu_box_diem_cao_bo_box_trung(self):
        dets = [
            Detection(BBox(0, 0, 100, 100), 0.9),
            Detection(BBox(2, 2, 100, 100), 0.6),  # trùng gần hết với box trên
            Detection(BBox(500, 500, 80, 80), 0.7),
        ]
        kept = nms(dets, iou_threshold=0.45)
        assert len(kept) == 2
        assert kept[0].confidence == 0.9
        assert kept[1].confidence == 0.7

    def test_khong_bo_box_tach_biet(self):
        dets = [Detection(BBox(0, 0, 10, 10), 0.9), Detection(BBox(50, 50, 10, 10), 0.8)]
        assert len(nms(dets, 0.45)) == 2

    def test_danh_sach_rong(self):
        assert nms([], 0.45) == []
