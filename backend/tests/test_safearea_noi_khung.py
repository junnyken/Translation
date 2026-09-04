"""Unit — nới khung ra chỗ trống khi không dựng được hình bong bóng (E14 · A1).

## Vì sao có bộ này

Đo thật 04/09 trên một trang manga tiếng Nhật của người dùng: `shape_derived: 0/8` — E14 không
dựng được hình cho **bất kỳ** vùng nào, vì bong bóng trắng nằm trên trang cũng trắng, không có
ranh giới sáng/tối để tách. Khung dự phòng khi đó là **cột chữ dọc** cao-hẹp; chữ Việt viết
ngang nhét vào cột hẹp thì 3/8 vùng tràn khung kể cả ở cỡ chữ nhỏ nhất, và chữ bị cắt cụt.

Bộ test dựng lại đúng hình dạng đó: một cột chữ hẹp nằm giữa một bong bóng rộng có viền mực.
"""
from __future__ import annotations

import numpy as np
import pytest

from app.services.interfaces import BBox
from app.services.safearea.config import SafeAreaConfig
from app.services.safearea.decision import ReasonCode
from app.services.safearea.extractor import khung_du_phong, khung_du_phong_co_noi
from app.services.safearea.grow import gioi_han_no, no_khung_ra_cho_trong


def cfg(**kw) -> SafeAreaConfig:
    mac_dinh = dict(
        roi_expand_ratio=4.0, roi_expand_max_px=1400, brightness_threshold=200,
        saturation_threshold=60, morph_kernel_ratio=0.06, erosion_margin_ratio=0.06,
        erosion_margin_min_px=3, erosion_margin_max_px=40, min_bbox_coverage_ratio=0.8,
        max_roi_coverage_ratio=0.75, max_roi_touch_ratio=0.02, max_polygon_vertices=64,
        safe_area_min_pixels=400, safe_area_min_width_px=24, safe_area_min_height_px=16,
        fallback_padding_ratio=0.09,
    )
    mac_dinh.update(kw)
    return SafeAreaConfig(**mac_dinh)


def trang_manga(w=400, h=400, bong_bong=(60, 60, 280, 280)) -> np.ndarray:
    """Mặt nạ "chỗ trống": tất cả trắng, trừ VIỀN bong bóng — đúng cảnh manga đen trắng.

    Cả trong lẫn ngoài bong bóng đều trắng; chỉ có nét mực của viền ngăn hai bên. Đây chính là
    cảnh mà phép tách theo ngưỡng sáng của E14 bó tay.
    """
    m = np.ones((h, w), dtype=bool)
    bx, by, bw, bh = bong_bong
    m[by:by + bh, bx:bx + 3] = False          # viền trái
    m[by:by + bh, bx + bw - 3:bx + bw] = False  # viền phải
    m[by:by + 3, bx:bx + bw] = False          # viền trên
    m[by + bh - 3:by + bh, bx:bx + bw] = False  # viền dưới
    return m


class TestNoKhungThuanHinhHoc:
    def test_cot_hep_no_ra_gan_trong_bong_bong(self):
        m = trang_manga()
        # cột chữ dọc: hẹp (30px) và cao (200px), nằm giữa bong bóng 280×280
        kq = no_khung_ra_cho_trong(m, (185, 100, 30, 200), gioi_han=(0, 0, 400, 400))
        assert kq is not None
        assert kq.w > 200, f"chỉ nới được tới {kq.w}px — chưa lấy được bề rộng bong bóng"
        assert kq.he_so_dien_tich > 3
        # và KHÔNG được vượt qua viền mực
        assert kq.x >= 63 and kq.x + kq.w <= 337

    def test_dung_lai_o_net_muc_khong_tran_sang_ben_kia(self):
        m = trang_manga()
        kq = no_khung_ra_cho_trong(m, (185, 100, 30, 200), gioi_han=(0, 0, 400, 400))
        # toàn bộ ô kết quả phải nằm trong chỗ trống
        assert m[kq.y:kq.y + kq.h, kq.x:kq.x + kq.w].all()

    def test_MUC_CON_SOT_trong_o_ban_dau_KHONG_chan_phep_noi(self):
        """Luật cũ của chính bộ này SAI với thực tế — sửa sau khi đo trên trang thật.

        Bản đầu đòi ô ban đầu phải sạch tuyệt đối rồi mới nới. Nghe có lý, nhưng ô ban đầu chính
        là chỗ chữ gốc vừa bị xoá, mà bước xoá chữ hầu như luôn để sót nét: log trang manga thật
        04/09 ghi `còn chữ ở 8/8 vùng`. Kết quả là phép nới **từ chối chạy ở cả 8 vùng** và bản
        sửa thành vô dụng đúng trên trang cần nó nhất.
        """
        m = trang_manga()
        m[200:206, 190:196] = False      # nét chữ còn sót nằm giữa ô ban đầu
        kq = no_khung_ra_cho_trong(m, (185, 100, 30, 200), gioi_han=(0, 0, 400, 400))
        assert kq is not None, "mực còn sót trong ô ban đầu không được chặn phép nới"
        assert kq.w > 200

    def test_van_KHONG_lan_qua_muc_o_dai_noi_them(self):
        """Nới lỏng ở ô ban đầu KHÔNG được kéo theo nới lỏng ở dải nới thêm."""
        m = trang_manga()
        m[200:206, 190:196] = False
        kq = no_khung_ra_cho_trong(m, (185, 100, 30, 200), gioi_han=(0, 0, 400, 400))
        # ngoài đúng vết mực cố ý đặt trong ô ban đầu, mọi điểm khác phải là chỗ trống
        vung = m[kq.y:kq.y + kq.h, kq.x:kq.x + kq.w].copy()
        vung[200 - kq.y:206 - kq.y, 190 - kq.x:196 - kq.x] = True
        assert vung.all(), "đã nới lấn qua nét mực ở dải nới thêm"

    def test_o_ban_dau_rong_thi_tra_None(self):
        m = trang_manga()
        assert no_khung_ra_cho_trong(m, (55, 55, 0, 0), gioi_han=(0, 0, 400, 400)) is None

    def test_khong_no_qua_gioi_han(self):
        m = np.ones((400, 400), dtype=bool)   # trống hoàn toàn, không gì chặn
        kq = no_khung_ra_cho_trong(m, (190, 190, 20, 20), gioi_han=(150, 150, 100, 100))
        assert (kq.x, kq.y, kq.w, kq.h) == (150, 150, 100, 100)

    def test_vung_tren_nen_ve_thi_no_duoc_rat_it(self):
        """Chữ ngoài bong bóng (tiếng động) — nét vẽ chặn ngay, và đó là kết quả ĐÚNG."""
        m = np.ones((200, 200), dtype=bool)
        m[:, :90] = False
        m[:, 110:] = False
        kq = no_khung_ra_cho_trong(m, (92, 90, 16, 20), gioi_han=(0, 0, 200, 200))
        assert kq.w <= 20, "không được lấn sang chỗ có nét vẽ"

    def test_ket_qua_tat_dinh(self):
        m = trang_manga()
        a = no_khung_ra_cho_trong(m, (185, 100, 30, 200), gioi_han=(0, 0, 400, 400))
        b = no_khung_ra_cho_trong(m, (185, 100, 30, 200), gioi_han=(0, 0, 400, 400))
        assert (a.x, a.y, a.w, a.h) == (b.x, b.y, b.w, b.h)


class TestGioiHanNo:
    def test_chan_theo_CANH_DAI_cho_ca_hai_chieu(self):
        """Cột chữ dọc 40×200: chặn theo bề rộng thì khung không bao giờ vượt 160px, trong khi
        lòng bong bóng rộng hơn nhiều. Cạnh dài (200) mới là thước đo "bong bóng to cỡ nào"."""
        x, y, w, h = gioi_han_no(100, 100, 40, 200, (0, 0, 1000, 1000), 1.5, 400)
        # 200×1,5 = 300px mỗi bên; trái và trên chạm mép ảnh nên bị cắt về 0.
        assert (x, y) == (0, 0) and (w, h) == (440, 600)

    def test_chan_theo_canh_ngan_thi_khung_khong_bao_gio_du_rong(self):
        """Chốt lại chính cái bẫy đã sửa — nếu ai đó đổi về cạnh tương ứng, test này đỏ."""
        _x, _y, w, _h = gioi_han_no(100, 100, 40, 200, (0, 0, 1000, 1000), 1.5, 400)
        assert w > 40 * 4, "chiều ngang đang bị chặn theo bề rộng cột chữ"

    def test_cat_theo_roi(self):
        x, y, w, h = gioi_han_no(100, 100, 40, 200, (90, 90, 100, 100), 1.5, 400)
        assert (x, y, w, h) == (90, 90, 100, 100)

    def test_px_toi_da_chan_tren_trang_lon(self):
        x, _y, w, _h = gioi_han_no(1000, 100, 400, 100, (0, 0, 4000, 4000), 1.5, 50)
        assert x == 950 and w == 500


class TestKhungDuPhongCoNoi:
    BBOX = BBox(x=185.0, y=100.0, w=30.0, h=200.0)

    def test_no_duoc_thi_khung_rong_hon_han_khung_cu(self):
        m = trang_manga()
        cu = khung_du_phong(self.BBOX, cfg(), [])
        moi = khung_du_phong_co_noi(self.BBOX, cfg(), [], m, (0, 0, 400, 400))
        r_cu, r_moi = cu.geometry["rect"], moi.geometry["rect"]
        assert r_moi["w"] > r_cu["w"] * 4
        assert ReasonCode.FALLBACK_GROWN_TO_FREE_SPACE in moi.reason_codes

    def test_VAN_la_khung_du_phong_khong_tu_phong_la_tim_duoc_bong_bong(self):
        """Nới được một khung rộng hơn KHÔNG có nghĩa là đã nhận ra hình bong bóng."""
        moi = khung_du_phong_co_noi(self.BBOX, cfg(), [], trang_manga(), (0, 0, 400, 400))
        assert moi.source.value == "fallback_rectangle"
        assert moi.status.value == "fallback_rectangle"
        assert ReasonCode.FALLBACK_NO_RELIABLE_SHAPE in moi.reason_codes
        assert ReasonCode.SHAPE_CANDIDATE_FOUND not in moi.reason_codes

    def test_chua_le_nen_khong_dinh_vien_bong_bong(self):
        moi = khung_du_phong_co_noi(self.BBOX, cfg(), [], trang_manga(), (0, 0, 400, 400))
        r = moi.geometry["rect"]
        assert r["x"] > 63, "mép trái đang dính viền mực"
        assert r["x"] + r["w"] < 337, "mép phải đang dính viền mực"

    def test_tat_cong_tac_thi_giu_nguyen_hanh_vi_cu(self):
        m = trang_manga()
        tat = khung_du_phong_co_noi(self.BBOX, cfg(grow_enabled=False), [], m, (0, 0, 400, 400))
        assert tat.geometry == khung_du_phong(self.BBOX, cfg(), []).geometry
        assert ReasonCode.FALLBACK_GROWN_TO_FREE_SPACE not in tat.reason_codes

    def test_no_duoc_it_qua_thi_khong_doi_gi(self):
        """Đổi hình học vì vài pixel chỉ làm bố cục nhảy giữa các lần chạy.

        Chỗ trống ở đây đúng bằng khung dự phòng — nét mực bao sát bốn phía, không nới được
        pixel nào, nên phải trả về y nguyên khung cũ.
        """
        m = np.zeros((200, 200), dtype=bool)
        m[59:141, 103:128] = True
        bbox = BBox(x=100.0, y=50.0, w=30.0, h=100.0)
        kq = khung_du_phong_co_noi(bbox, cfg(), [], m, (0, 0, 200, 200))
        assert ReasonCode.FALLBACK_GROWN_TO_FREE_SPACE not in kq.reason_codes
        assert kq.geometry == khung_du_phong(bbox, cfg(), []).geometry

    def test_khong_co_mat_na_thi_tra_khung_cu(self):
        kq = khung_du_phong_co_noi(self.BBOX, cfg(), [], None, (0, 0, 400, 400))
        assert kq.geometry == khung_du_phong(self.BBOX, cfg(), []).geometry

    @pytest.mark.parametrize("ma", [
        ReasonCode.SHAPE_CANDIDATE_NOT_CENTERED,
        ReasonCode.SHAPE_CANDIDATE_FILLS_ROI,
        ReasonCode.SHAPE_LOW_CONTRAST,
    ])
    def test_giu_nguyen_ly_do_vi_sao_khong_dung_duoc_hinh(self, ma):
        """Nới khung không được xoá mất bằng chứng vì sao E14 bó tay."""
        kq = khung_du_phong_co_noi(self.BBOX, cfg(), [ma], trang_manga(), (0, 0, 400, 400))
        assert ma in kq.reason_codes
