"""Unit — dựng mask từ bbox + dilate (M4 §7.1)."""
import numpy as np
import pytest

from app.services.inpaint.mask import (
    MAX_DILATE_RATIO,
    InvalidMask,
    build_mask,
    dilate_bbox,
    mask_coverage,
)
from app.services.interfaces import BBox


class TestDilate:
    def test_khong_noi_khi_ratio_0(self):
        b = dilate_bbox(BBox(10, 20, 100, 50), 500, 500, ratio=0.0)
        assert (b.x, b.y, b.w, b.h) == (10, 20, 100, 50)

    def test_noi_dung_ty_le_chia_deu_hai_ben(self):
        b = dilate_bbox(BBox(100, 100, 100, 40), 500, 500, ratio=0.10)
        # rộng thêm tổng cộng 10% (mỗi bên 5%) -> 100 -> 110, x lùi 5
        assert b.x == pytest.approx(95.0)
        assert b.w == pytest.approx(110.0)
        assert b.y == pytest.approx(98.0)
        assert b.h == pytest.approx(44.0)

    def test_ratio_vuot_tran_bi_kep_xuong_15_phan_tram(self):
        rong = dilate_bbox(BBox(100, 100, 100, 100), 500, 500, ratio=0.9)
        toi_da = dilate_bbox(BBox(100, 100, 100, 100), 500, 500, ratio=MAX_DILATE_RATIO)
        assert rong.w == pytest.approx(toi_da.w)
        assert rong.w == pytest.approx(115.0)  # không bao giờ nới quá 15%

    def test_ratio_am_bao_loi(self):
        with pytest.raises(InvalidMask):
            dilate_bbox(BBox(10, 10, 10, 10), 100, 100, ratio=-0.1)

    def test_cham_bien_anh_thi_clamp_khong_tran_ra_ngoai(self):
        b = dilate_bbox(BBox(0, 0, 100, 100), 120, 120, ratio=0.15)
        assert b.x == 0.0 and b.y == 0.0
        assert b.x + b.w <= 120
        assert b.y + b.h <= 120

    def test_bbox_sat_goc_phai_duoi(self):
        b = dilate_bbox(BBox(90, 90, 10, 10), 100, 100, ratio=0.15)
        assert b.x + b.w <= 100
        assert b.y + b.h <= 100


class TestBuildMask:
    def test_mask_cung_kich_thuoc_anh_va_nhi_phan(self):
        m = build_mask(200, 100, [BBox(10, 10, 50, 20)])
        assert m.shape == (100, 200)  # (H, W) — LaMa cần mask cùng kích thước ảnh
        assert set(np.unique(m)) <= {0.0, 1.0}

    def test_dung_vung_bbox_duoc_danh_dau(self):
        m = build_mask(200, 100, [BBox(10, 20, 50, 30)])
        assert m[20:50, 10:60].min() == 1.0
        assert m[0:19, :].max() == 0.0

    def test_nhieu_bbox_deu_vao_mask(self):
        m = build_mask(200, 100, [BBox(0, 0, 20, 20), BBox(150, 60, 40, 30)])
        assert m[0:20, 0:20].min() == 1.0
        assert m[60:90, 150:190].min() == 1.0

    def test_khong_bbox_thi_mask_toan_0(self):
        assert build_mask(50, 50, []).max() == 0.0

    def test_bbox_vuot_bien_khong_lam_vo_mask(self):
        m = build_mask(100, 100, [BBox(80, 80, 100, 100)])
        assert m.shape == (100, 100)
        assert m[80:100, 80:100].min() == 1.0

    def test_kich_thuoc_anh_khong_hop_le_bao_loi(self):
        with pytest.raises(InvalidMask):
            build_mask(0, 100, [BBox(0, 0, 10, 10)])

    def test_mask_coverage_tinh_dung_ty_le(self):
        m = build_mask(100, 100, [BBox(0, 0, 50, 100)])
        assert mask_coverage(m) == pytest.approx(0.5)


# ---------------- Gom cụm để xoá chữ theo ô (sinh ra từ Run C) ----------------


class TestGomCum:
    """Bộ nhớ LaMa tỉ lệ THUẬN với diện tích ảnh — đo thật ~1,6 GB / triệu điểm ảnh.

    Trang truyện thật ở cỡ đọc (1600x2259 ≈ 3,6 triệu điểm) chạy cả trang thì bị hệ điều hành
    giết bằng SIGKILL. Ảnh tổng hợp của M2–M8 chỉ 1200x1700 (2,0 triệu điểm) nên không bao giờ
    lộ ra. Cắt theo cụm làm bộ nhớ tỉ lệ với Ô CẮT chứ không với trang.
    """

    def test_moi_vung_ra_mot_o_da_noi_le(self):
        from app.services.inpaint.lama import gom_cum

        o = gom_cum([BBox(x=500, y=500, w=100, h=50)], 2000, 2000, le=96)
        assert o == [(404, 404, 696, 646)]

    def test_hai_vung_xa_nhau_thi_hai_o_rieng(self):
        from app.services.inpaint.lama import gom_cum

        o = gom_cum(
            [BBox(x=100, y=100, w=80, h=40), BBox(x=1500, y=1500, w=80, h=40)],
            2000, 2000, le=50,
        )
        assert len(o) == 2

    def test_hai_vung_sat_nhau_thi_gop_lam_mot(self):
        """Chạy model hai lần trên vùng giao nhau sẽ vẽ đè hai lượt, dễ lộ đường nối."""
        from app.services.inpaint.lama import gom_cum

        o = gom_cum(
            [BBox(x=500, y=500, w=100, h=50), BBox(x=560, y=520, w=100, h=50)],
            2000, 2000, le=96,
        )
        assert len(o) == 1
        assert o[0][0] <= 404 and o[0][2] >= 756

    def test_o_luon_nam_trong_anh(self):
        from app.services.inpaint.lama import gom_cum

        o = gom_cum([BBox(x=5, y=5, w=50, h=30)], 300, 200, le=200)
        assert o == [(0, 0, 255, 200)]

    def test_khong_co_vung_nao_thi_khong_co_o(self):
        from app.services.inpaint.lama import gom_cum

        assert gom_cum([], 100, 100, le=10) == []

    def test_dien_tich_o_nho_hon_han_ca_trang(self):
        """Đây chính là điều khiến việc cắt ô có ý nghĩa — phải đo, không nói suông."""
        from app.services.inpaint.lama import gom_cum

        rong, cao = 1600, 2259
        vung = [BBox(x=200 + i * 300, y=300 + i * 400, w=200, h=100) for i in range(4)]
        o = gom_cum(vung, rong, cao, le=96)
        dien_tich_o = sum((x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in o)
        assert dien_tich_o < rong * cao * 0.25, (
            f"ô chiếm {dien_tich_o / (rong * cao):.0%} trang — cắt ô không còn tiết kiệm được gì"
        )
