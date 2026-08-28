"""Unit — bộ chấm chất lượng vùng (E12). Thuần luật, không DB, không mạng."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.models.enums import (
    ConfidenceState,
    FitStatus,
    OCRStatus,
    OverallBand,
    RegionRelevance,
    RegionStatus,
    ReviewStatus,
    TranslationState,
    TranslationStatus,
)
from app.services.quality import MA_LY_DO, RegionQualityAssessor, do_dai_hien_thi

TRANG = (1600, 2259)


def vung(conf=0.9, status=RegionStatus.pending, overlap=False, w=200.0, h=90.0):
    return SimpleNamespace(bbox_x=100.0, bbox_y=100.0, bbox_w=w, bbox_h=h,
                           confidence=conf, overlap_suspect=overlap, status=status,
                           reading_order=1)


def doc_chu(text="Hello there", conf=0.95, status=OCRStatus.ok, engine=None):
    return SimpleNamespace(raw_text=text, confidence=conf, status=status, ocr_engine=engine)


def dich(text="Xin chào", status=TranslationStatus.ok, engine=None):
    return SimpleNamespace(translated_text=text, status=status, engine=engine)


def canh(fit=FitStatus.fit_ok, size=20.0):
    return SimpleNamespace(fit_status=fit, font_size=size)


def cham(**kw):
    mac_dinh = dict(region=vung(), ocr=doc_chu(), translation=dich(), typeset=canh(),
                    page_dimensions=TRANG)
    mac_dinh.update(kw)
    return RegionQualityAssessor().assess(**mac_dinh)


class TestVungSach:
    def test_khong_dau_hieu_gi_thi_khong_bat_ra_soat(self):
        kq = cham()
        assert kq.overall_band is OverallBand.clear
        assert kq.review_status is ReviewStatus.not_required
        assert kq.relevance is RegionRelevance.likely_translatable
        assert kq.reason_codes == []

    def test_chay_lai_cho_ra_y_HỆT(self):
        """Tất định: cùng đầu vào phải ra cùng kết quả, nếu không thì không kiểm được gì."""
        a, b = cham(), cham()
        assert (a.reason_codes, a.relevance, a.overall_band) == \
               (b.reason_codes, b.relevance, b.overall_band)
        assert a.evidence_snapshot == b.evidence_snapshot


class TestTungMaLyDo:
    """Mỗi mã trong bảng trắng phải có ít nhất một đường sinh ra nó."""

    @pytest.mark.parametrize("ma,dung_de_cham", [
        ("detector_low_confidence", dict(region=vung(conf=0.3, status=RegionStatus.low_confidence))),
        ("detector_overlap_suspect", dict(region=vung(overlap=True))),
        ("ocr_missing", dict(ocr=None)),
        ("ocr_empty", dict(ocr=doc_chu(text="   "))),
        ("ocr_needs_manual", dict(ocr=doc_chu(status=OCRStatus.needs_manual))),
        ("ocr_confidence_low", dict(ocr=doc_chu(conf=0.2))),
        ("ocr_confidence_unavailable", dict(ocr=doc_chu(conf=None))),
        ("translation_missing", dict(translation=None)),
        ("translation_empty", dict(translation=dich(text=""))),
        ("translation_fallback_used", dict(translation=dich(status=TranslationStatus.fallback_used))),
        ("translation_length_outlier", dict(ocr=doc_chu(text="Good morning everyone"),
                                            translation=dich(text="Chào"))),
        ("numeric_or_symbol_only", dict(ocr=doc_chu(text="18"))),
        ("short_stylized_text", dict(ocr=doc_chu(text="BAM!"))),
        ("hyphenated_fragment_suspect", dict(ocr=doc_chu(text="PARTICU-"))),
        ("small_region_suspect", dict(region=vung(w=8.0, h=8.0))),
        ("large_region_suspect", dict(region=vung(w=1500.0, h=1500.0))),
        ("layout_overflow_warning", dict(typeset=canh(fit=FitStatus.overflow_warning))),
        ("assessment_input_missing", dict(page_dimensions=None)),
    ])
    def test_sinh_dung_ma(self, ma, dung_de_cham):
        assert ma in cham(**dung_de_cham).reason_codes

    def test_moi_ma_trong_bang_trang_deu_co_cau_tieng_viet(self):
        for ma, cau in MA_LY_DO.items():
            assert cau and cau.endswith("."), f"{ma} chưa có câu mô tả tử tế"

    def test_khong_bao_gio_sinh_ma_ngoai_bang_trang(self):
        for kw in (dict(), dict(ocr=None), dict(translation=None), dict(page_dimensions=None),
                   dict(ocr=doc_chu(text="18", conf=None), region=vung(w=6, h=6, overlap=True))):
            for ma in cham(**kw).reason_codes:
                assert ma in MA_LY_DO


class TestKhongTuKetLuanThayNguoiDung:
    """Nhóm test quan trọng nhất của E12: máy KHÔNG được tự bỏ vùng nào."""

    @pytest.mark.parametrize("chu", ["18", "BAM!", "NO!", "PHEW!", "05/2014", "!!!"])
    def test_so_va_chu_ngan_duoc_day_cho_nguoi_xem_chu_khong_bi_bo(self, chu):
        kq = cham(ocr=doc_chu(text=chu))
        assert kq.review_status is not ReviewStatus.reviewed_skip
        assert kq.review_status is ReviewStatus.needs_review
        assert kq.relevance is not RegionRelevance.likely_translatable

    def test_tieng_dong_DAI_khong_bat_duoc_bang_luat_do_dai(self):
        """Sự thật đo được, không giấu: `SPLASH` dài 6 ký tự nên luật "chữ ngắn ≤5" KHÔNG bắt.

        Nới ngưỡng lên 6 chỉ để test xanh là sửa luật cho vừa test. Trong dữ liệu thật của
        Pepper&Carrot, vùng `SPLASH` VẪN được đẩy cho người xem — nhưng vì lý do khác:
        điểm nhận diện khung chỉ 0,384 (xem ca dưới). Giới hạn này ghi rõ ở REPORT_E12 §9.
        """
        kq = cham(ocr=doc_chu(text="SPLASH"))
        assert kq.reason_codes == []
        assert kq.review_status is ReviewStatus.not_required

    def test_ca_THAT_cua_SPLASH_van_duoc_day_cho_nguoi_xem(self):
        """Đúng dữ liệu đã đo trên trang thật: `SPLASH\n18`, tin cậy khung 0,384, khung 603x177."""
        kq = cham(
            region=vung(conf=0.384, status=RegionStatus.low_confidence, w=603.0, h=177.0),
            ocr=doc_chu(text="SPLASH\n18", conf=0.94),
            translation=dich(text="TUYỆT VỜI\n18"),
        )
        assert "detector_low_confidence" in kq.reason_codes
        assert kq.review_status is ReviewStatus.needs_review
        assert kq.relevance is not RegionRelevance.likely_translatable

    def test_tieng_dong_duoc_goi_la_CO_THE_la_tieng_dong(self):
        assert cham(ocr=doc_chu(text="BÕM!")).relevance is RegionRelevance.possible_sfx

    def test_so_duoc_goi_la_CO_THE_la_so_hoac_trang_tri(self):
        assert cham(ocr=doc_chu(text="18")).relevance \
            is RegionRelevance.possible_number_or_decoration

    def test_chu_hoa_dai_binh_thuong_KHONG_bi_gan_co_gi(self):
        """Không có luật 'viết hoa = bỏ'. Thoại viết hoa vẫn là thoại."""
        assert cham(ocr=doc_chu(text="I WILL NEVER FORGIVE YOU"),
                    translation=dich(text="TAO SẼ KHÔNG BAO GIỜ THA THỨ")).reason_codes == []


class TestDiemTinCayKhongCo:
    """manga-ocr không trả điểm tin cậy. 'Không có điểm' KHÁC 'điểm 0'."""

    def test_khong_co_diem_thi_bao_la_khong_co(self):
        kq = cham(ocr=doc_chu(conf=None))
        assert kq.ocr_confidence_state is ConfidenceState.unavailable
        assert "ocr_confidence_unavailable" in kq.reason_codes
        assert "ocr_confidence_low" not in kq.reason_codes

    def test_khong_co_diem_MA_moi_thu_khac_sach_thi_van_la_sach(self):
        """Nếu không có điểm mà bắt rà soát thì mọi trang tiếng Nhật đều phải rà soát."""
        kq = cham(ocr=doc_chu(conf=None))
        assert kq.overall_band is OverallBand.clear
        assert kq.review_status is ReviewStatus.not_required

    def test_diem_thap_thi_khac_han_khong_co_diem(self):
        kq = cham(ocr=doc_chu(conf=0.1))
        assert kq.ocr_confidence_state is ConfidenceState.low
        assert kq.review_status is ReviewStatus.needs_review


class TestDoDaiTinhTheoKyTu:
    def test_dem_ky_tu_hien_thi_chu_khong_dem_byte(self):
        assert do_dai_hien_thi("Đừng") == 4          # 4 ký tự, 7 byte UTF-8
        assert do_dai_hien_thi("こんにちは") == 5      # 5 ký tự, 15 byte
        assert do_dai_hien_thi(None) == 0

    def test_ban_dich_tieng_viet_binh_thuong_KHONG_bi_keu_dai_bat_thuong(self):
        kq = cham(ocr=doc_chu(text="Don't even think about it"),
                  translation=dich(text="Đừng hòng nghĩ đến chuyện đó"))
        assert "translation_length_outlier" not in kq.reason_codes

    def test_chu_goc_qua_ngan_thi_khong_xet_ty_le(self):
        """3 ký tự dịch thành 7 ký tự là chuyện thường, không phải bất thường."""
        assert "translation_length_outlier" not in \
            cham(ocr=doc_chu(text="Hi!"), translation=dich(text="Xin chào!")).reason_codes


class TestThieuDauVao:
    def test_thieu_kich_thuoc_trang_thi_bao_KHONG_danh_gia_duoc(self):
        kq = cham(page_dimensions=None)
        assert kq.overall_band is OverallBand.blocked
        assert kq.review_status is ReviewStatus.needs_review
        assert kq.reason_codes == ["assessment_input_missing"]

    def test_blocked_khong_co_nghia_la_dich_sai(self):
        kq = cham(region=None)
        assert kq.overall_band is OverallBand.blocked
        assert kq.translation_state is TranslationState.not_attempted
