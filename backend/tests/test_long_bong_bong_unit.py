"""A2 — tìm lòng bong bóng bằng tô loang.

Toàn bộ test dùng mặt nạ **dựng bằng số**, không đọc ảnh: đúng/sai không phụ thuộc một tệp ảnh
có thể bị đổi, và chạy được ở mọi máy.
"""
from __future__ import annotations

import numpy as np
import pytest

from app.services.safearea.decision import ReasonCode
from app.services.safearea.long_bong_bong import (
    du_tin_lam_bong_bong,
    long_bong_bong,
)


def mat_na(h=200, w=200, bong_bong=(40, 40, 120, 120), day=3):
    """True = không mực. Vẽ một khung mực rỗng ruột làm 'viền bong bóng'."""
    m = np.ones((h, w), dtype=bool)
    x, y, bw, bh = bong_bong
    m[y:y + bh, x:x + day] = False
    m[y:y + bh, x + bw - day:x + bw] = False
    m[y:y + day, x:x + bw] = False
    m[y + bh - day:y + bh, x:x + bw] = False
    return m


class TestToLoang:
    def test_tam_trong_bong_bong_thi_ra_dung_long_bong_bong(self):
        kq, ly_do = long_bong_bong(mat_na(), (100, 100))
        assert ly_do == []
        x, y, w, h = kq.rect
        # Lòng bong bóng: từ 43 tới 157 (viền dày 3 ở mỗi bên).
        assert (x, y) == (43, 43)
        assert (w, h) == (114, 114)

    def test_tam_NGOAI_bong_bong_thi_ro_ra_ca_anh(self):
        """Đây là ca 'chữ nằm trên nền vẽ' — phải rò, để trần diện tích loại nó."""
        kq, ly_do = long_bong_bong(mat_na(), (10, 10))
        assert ly_do == []
        assert kq.so_diem > 0.5 * 200 * 200, "không rò thì trần diện tích mất tác dụng"

    def test_tam_roi_TRUNG_MUC_thi_doi_tam_chu_khong_bo_cuoc(self):
        """Tâm bbox chữ rất hay rơi trúng nét chữ còn sót — đo 04/09: còn chữ ở 8/8 vùng."""
        m = mat_na()
        m[95:105, 95:105] = False           # một vệt mực ngay tại tâm
        kq, ly_do = long_bong_bong(m, (100, 100))
        assert ly_do == []
        assert kq.da_doi_tam is True
        assert kq.tam_da_dung != (100, 100)
        # Vẫn phải ra đúng lòng bong bóng, không phải ra vệt mực.
        assert kq.rect == (43, 43, 114, 114)

    def test_quanh_tam_toan_muc_thi_noi_KHONG_TIM_DUOC(self):
        m = np.zeros((200, 200), dtype=bool)   # mực đặc
        kq, ly_do = long_bong_bong(m, (100, 100))
        assert kq is None
        assert ReasonCode.SHAPE_EROSION_ELIMINATED_AREA in ly_do

    def test_tam_ngoai_anh_thi_bao_loi_chu_khong_no(self):
        kq, ly_do = long_bong_bong(mat_na(), (999, 999))
        assert kq is None and ly_do

    def test_ket_qua_TAT_DINH(self):
        """Cùng đầu vào phải cho cùng đầu ra ở mọi lần chạy — dò tâm đi theo thứ tự cố định."""
        m = mat_na()
        m[95:105, 95:105] = False
        ra = {long_bong_bong(m, (100, 100))[0].tam_da_dung for _ in range(5)}
        assert len(ra) == 1

    def test_net_chu_con_sot_KHONG_lam_vo_long_bong_bong(self):
        """Nét sót là đảo nhỏ giữa lòng bong bóng; tô loang đi vòng qua chúng."""
        m = mat_na()
        m[70:76, 70:110] = False
        m[85:91, 70:120] = False
        kq, _ = long_bong_bong(m, (100, 130))
        assert kq.rect == (43, 43, 114, 114), "lòng bong bóng bị nét sót chia nhỏ"


class TestTranDienTich:
    #: Lấy đúng dải đã đo trên `test_fixtures/`: trong bong bóng 4-6% trang, rò ra 75-82%.
    TRAN_ROI = 0.60
    TRAN_BBOX = 40.0

    def _kiem(self, kq, dt_roi, bbox):
        return du_tin_lam_bong_bong(kq, dien_tich_roi=dt_roi, bbox_wh=bbox,
                                    tran_ti_le_roi=self.TRAN_ROI, tran_boi_bbox=self.TRAN_BBOX)

    def test_bong_bong_that_thi_NHAN(self):
        kq, _ = long_bong_bong(mat_na(), (100, 100))
        assert self._kiem(kq, 200 * 200, (40.0, 40.0)) == []

    def test_ro_ra_ca_anh_thi_LOAI(self):
        kq, _ = long_bong_bong(mat_na(), (10, 10))
        assert ReasonCode.SHAPE_CANDIDATE_FILLS_ROI in self._kiem(kq, 200 * 200, (40.0, 40.0))

    def test_bong_bong_LON_BAT_THUONG_so_voi_khoi_chu_thi_LOAI(self):
        """Trần theo ROI chưa chạm nhưng vùng tô rộng gấp trăm lần khối chữ ⇒ nhiều khả năng đã
        rò sang panel bên cạnh."""
        kq, _ = long_bong_bong(mat_na(), (100, 100))
        assert ReasonCode.SHAPE_CANDIDATE_FILLS_ROI in self._kiem(kq, 200 * 200, (8.0, 8.0))
