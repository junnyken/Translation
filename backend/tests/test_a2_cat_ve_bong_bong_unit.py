"""A2 — cắt khung chữ về trong lòng bong bóng, nối vào sau A1.

Test ở đây đo **số điểm mực nằm trong khung** — thước đo trực tiếp của câu hỏi "khung có lọt
trong bong bóng không", và là tiêu chí nghiệm thu số 2 của A2.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from app.core.config import get_settings
from app.services.safearea.config import SafeAreaConfig
from app.services.safearea.extractor import _dem_muc, khung_du_phong_co_noi
from app.services.interfaces import BBox


def cfg(bat: bool) -> SafeAreaConfig:
    return replace(SafeAreaConfig.from_settings(get_settings()), cat_ve_bong_bong_enabled=bat)


def canh_bong_bong(h=400, w=400):
    """Bong bóng sát mép panel — đúng ca người dùng báo lỗi 05/09."""
    import cv2

    img = np.full((h, w), 255, np.uint8)
    cv2.rectangle(img, (20, 20), (380, 380), 0, 3)          # khung panel
    cv2.ellipse(img, (330, 150), (90, 70), 0, 0, 360, 0, 3)  # bong bóng bị mép panel cắt
    return img >= 128   # True = không mực


def chay(bat: bool, bbox: BBox):
    mat_na = canh_bong_bong()
    qd = khung_du_phong_co_noi(bbox, cfg(bat), [], mat_na, (0, 0, mat_na.shape[1], mat_na.shape[0]))
    r = qd.geometry["rect"]
    o = (r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"])
    return qd, o, _dem_muc(mat_na, o)


class TestCatVeBongBong:
    #: bbox chữ chồm qua viền phải bong bóng — khung A1 sẽ đè lên nét vẽ.
    BBOX = BBox(x=300, y=110, w=110, h=80)

    def test_TAT_thi_khung_van_de_len_net_ve(self):
        """Ghi lại hành vi CŨ bằng số, để bản sửa có mốc so sánh thật."""
        _, _, muc = chay(False, self.BBOX)
        assert muc > 0, "ca dựng không tái hiện được lỗi — test dưới sẽ rỗng nghĩa"

    def test_BAT_thi_khung_khong_con_de_len_net_ve(self):
        _, _, muc_bat = chay(True, self.BBOX)
        _, _, muc_tat = chay(False, self.BBOX)
        assert muc_bat < muc_tat, "bật A2 mà điểm mực trong khung không giảm"
        assert muc_bat == 0

    def test_CHI_THU_NHO_khong_bao_gio_no_them(self):
        """A2 là phép giao, nên nó không thể làm khung to ra. Nếu to ra là logic sai."""
        _, o_tat, _ = chay(False, self.BBOX)
        _, o_bat, _ = chay(True, self.BBOX)
        assert o_bat[0] >= o_tat[0] and o_bat[1] >= o_tat[1]
        assert o_bat[2] <= o_tat[2] and o_bat[3] <= o_tat[3]

    def test_khung_von_da_nam_gon_thi_KHONG_bi_dong_toi(self):
        """Vùng đang đúng không được đổi — bật A2 phải là sửa ca hỏng, không phải xáo trộn cả trang."""
        gon = BBox(x=300, y=130, w=50, h=40)
        _, o_tat, _ = chay(False, gon)
        _, o_bat, _ = chay(True, gon)
        assert o_bat == o_tat

    def test_chu_tren_NEN_VE_thi_A2_dung_ngoai_khong_can_thiep(self):
        """Không có bong bóng ⇒ tô loang rò ⇒ bị trần diện tích loại ⇒ giữ nguyên hành vi A1."""
        ngoai = BBox(x=60, y=250, w=80, h=40)
        _, o_tat, _ = chay(False, ngoai)
        _, o_bat, _ = chay(True, ngoai)
        assert o_bat == o_tat

    def test_mac_dinh_la_TAT(self):
        """Đổi hình học là đổi thứ người dùng nhìn thấy. Bật mặc định trước khi đo trên trang
        thật là đúng thứ kế hoạch A2 §7 cấm."""
        assert SafeAreaConfig.from_settings(get_settings()).cat_ve_bong_bong_enabled is False
