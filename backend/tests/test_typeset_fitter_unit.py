"""Unit — chọn cỡ chữ vừa bubble (M6). Thuần tính toán, không DB, không render."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.services.interfaces import BBox
from app.services.typeset.fitter import FIT_OK, OVERFLOW_WARNING, PENDING, FitToBoxTypesetter
from app.services.typeset.fonts import FontResolver

FONT_DIR = os.environ.get("FONT_DIR") or str(Path(__file__).resolve().parents[1] / "fonts")
MIN, MAX = 10, 28


@pytest.fixture
def fitter() -> FitToBoxTypesetter:
    return FitToBoxTypesetter(FontResolver(FONT_DIR, "Bangers"), MIN, MAX, 0.09, 0.18)


def _bbox(w: float, h: float) -> BBox:
    return BBox(x=0.0, y=0.0, w=w, h=h)


class TestFitOk:
    def test_text_ngan_bbox_lon_chon_co_lon_nhat(self, fitter):
        r = fitter.fit("Ừ!", _bbox(600, 400), "Bangers")
        assert r["fit_status"] == FIT_OK
        assert r["font_size"] == float(MAX)
        assert "\n" not in r["wrapped_text"], "bbox thừa chỗ thì không được ngắt dòng vô cớ"

    def test_khong_bao_gio_vuot_qua_max(self, fitter):
        r = fitter.fit("A", _bbox(5000, 5000), "Bangers")
        assert r["font_size"] == float(MAX)

    def test_moi_dong_nam_gon_trong_vung_content(self, fitter):
        bbox = _bbox(200, 160)
        r = fitter.fit("Cậu ổn chứ? Tớ tưởng cậu đã biến mất rồi.", bbox, "Bangers")
        assert r["fit_status"] == FIT_OK
        rect = fitter.content_rect(bbox)
        _wrapped, w, h = fitter._do_thu(
            r["wrapped_text"], "Bangers", int(r["font_size"]), rect
        )
        assert w <= rect.width and h <= rect.height


class TestOverflow:
    def test_text_dai_bbox_nho_dung_o_co_min(self, fitter):
        r = fitter.fit(
            "Đây là một câu thoại cực kỳ dài dùng để ép hệ thống phải cảnh báo tràn khung "
            "chứ tuyệt đối không được co chữ bé lại cho vừa.",
            _bbox(60, 40), "Bangers",
        )
        assert r["fit_status"] == OVERFLOW_WARNING
        assert r["font_size"] == float(MIN), "KHÔNG được co nhỏ hơn min để giả vờ vừa khung"

    def test_khong_bao_gio_nho_hon_min(self, fitter):
        for w, h in ((30, 20), (20, 15), (12, 10)):
            r = fitter.fit("Một câu thoại dài dằng dặc không thể vừa nổi", _bbox(w, h), "Bangers")
            assert r["font_size"] >= float(MIN)

    def test_bbox_nho_hon_hai_lan_padding_khong_crash(self, fitter):
        r = fitter.fit("Ừ", _bbox(2, 2), "Bangers")
        assert r["fit_status"] == OVERFLOW_WARNING
        assert r["font_size"] == float(MIN)

    def test_bbox_khong_am_khong_crash(self, fitter):
        assert fitter.fit("Ừ", _bbox(0, 0), "Bangers")["fit_status"] == OVERFLOW_WARNING


class TestPending:
    def test_khong_co_chu_thi_pending_khong_phai_overflow(self, fitter):
        """Vùng chưa có bản dịch KHÔNG phải 'tràn khung' — gắn overflow là nói sai sự thật."""
        for text in ("", "   ", "\n"):
            r = fitter.fit(text, _bbox(200, 100), "Bangers")
            assert r["fit_status"] == PENDING
            assert r["font_size"] is None
            assert r["wrapped_text"] == ""


class TestDeterministic:
    def test_chay_nhieu_lan_ra_ket_qua_y_het(self, fitter):
        bbox = _bbox(191.92, 84.93)
        ket_qua = [fitter.fit("Chào buổi sáng.", bbox, "Bangers") for _ in range(5)]
        assert all(k == ket_qua[0] for k in ket_qua)

    def test_giam_1px_lay_duoc_co_lon_nhat_ke_ca_khi_khong_don_dieu(self, fitter):
        """Ca thật: "Cẩn thận!" trong bubble 108x83 vừa ở 25, HỎNG ở 26, lại vừa ở 27.

        Tìm kiếm nhị phân sẽ dừng ở 25 và bỏ sót 27 — đó là lý do M6 dùng giảm dần 1px.
        """
        bbox = _bbox(108.14, 83.50)
        rect = fitter.content_rect(bbox)
        vua = []
        for size in range(MIN, MAX + 1):
            _w0, w, h = fitter._do_thu("Cẩn thận!", "Bangers", size, rect)
            if w <= rect.width and h <= rect.height:
                vua.append(size)
        assert vua, "ca mẫu phải có ít nhất một cỡ vừa"
        # Chính là bằng chứng không đơn điệu (có khoảng đứt ở giữa).
        assert vua != list(range(min(vua), max(vua) + 1)), "ca mẫu này phải KHÔNG đơn điệu"
        assert fitter.fit("Cẩn thận!", bbox, "Bangers")["font_size"] == float(max(vua))


class TestCauHinh:
    def test_min_lon_hon_max_bao_loi_ngay_luc_dung(self):
        with pytest.raises(ValueError, match="TYPESET_MIN_FONT_SIZE"):
            FitToBoxTypesetter(FontResolver(FONT_DIR, "Bangers"), 30, 20, 0.09, 0.18)

    def test_padding_lon_hon_thi_vung_chu_nho_hon(self):
        r = FontResolver(FONT_DIR, "Bangers")
        it = FitToBoxTypesetter(r, MIN, MAX, 0.05, 0.18).content_rect(_bbox(200, 100))
        nhieu = FitToBoxTypesetter(r, MIN, MAX, 0.25, 0.18).content_rect(_bbox(200, 100))
        assert nhieu.width < it.width and nhieu.height < it.height

    def test_font_la_bao_loi_khong_am_tham_doi_font(self, fitter):
        from app.services.typeset.fonts import FontNotFound

        with pytest.raises(FontNotFound):
            fitter.fit("Xin chào", _bbox(200, 100), "FontKhongCo")
