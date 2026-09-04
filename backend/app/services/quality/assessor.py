"""Chấm chất lượng một vùng chữ bằng LUẬT — thuần tuý, tất định (E12).

Nguyên tắc lớn nhất: **không kết luận thay người dùng**. Bộ này chỉ đọc bằng chứng đã có sẵn
trong DB rồi nói "vùng này có dấu hiệu X, nên nhìn lại". Nó KHÔNG xoá vùng, KHÔNG sửa chữ,
KHÔNG gọi mạng, và KHÔNG tự bỏ qua tiếng động hay con số.

Vì sao là luật chứ không phải hỏi thêm một con AI: nhờ LLM chấm chính bản dịch của LLM là để
nó tự khen mình, tốn token, và kết quả không lặp lại được. Bằng chứng có cấu trúc thì đã nằm
sẵn trong DB — việc cần làm là nói nó ra cho dễ hiểu.

Cũng **không có điểm số 0–100**: một con số gộp nhiều thứ khác bản chất lại nghe như đo được
chính xác, trong khi không giải thích được vì sao. Mức + lý do thì nói được thành câu.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from app.models.enums import (
    ConfidenceState,
    FitStatus,
    OCREngine,
    OCRStatus,
    OverallBand,
    RegionRelevance,
    RegionStatus,
    ReviewStatus,
    TranslationState,
    TranslationStatus,
)
from app.services.quality.reasons import MA_CHI_DE_BIET, MA_LY_DO


@dataclass(frozen=True)
class NguongLuat:
    """Các ngưỡng của bộ luật. Đưa ra ngoài để test đặt số cố định, và để đổi mà không sửa mã."""

    #: Dưới ngưỡng này coi là điểm tin cậy thấp (chỉ áp cho engine CÓ trả điểm).
    ocr_confidence_low: float = 0.60
    #: Chữ ngắn hơn/bằng ngần này coi là ngắn — có thể là tiếng động. KHÔNG phải lý do để bỏ.
    short_text_max_chars: int = 5
    #: Bản dịch dài gấp hơn ngần này lần chữ gốc thì đáng nhìn lại.
    length_ratio_max: float = 3.0
    #: …và ngắn hơn ngần này lần thì cũng vậy.
    length_ratio_min: float = 0.25
    #: Chỉ xét tỉ lệ độ dài khi chữ gốc đủ dài — vài ký tự thì tỉ lệ nào cũng vô nghĩa.
    length_ratio_min_chars: int = 8
    #: Khung nhỏ/lớn hơn ngần này phần diện tích trang thì đáng nhìn lại.
    small_area_ratio: float = 0.0004
    large_area_ratio: float = 0.25


@dataclass
class KetQuaCham:
    relevance: RegionRelevance
    review_status: ReviewStatus
    overall_band: OverallBand
    detector_confidence_state: ConfidenceState
    ocr_confidence_state: ConfidenceState
    translation_state: TranslationState
    reason_codes: list[str] = field(default_factory=list)
    evidence_snapshot: dict = field(default_factory=dict)


def do_dai_hien_thi(text: str | None) -> int:
    """Đếm ký tự người đọc THẤY, không đếm byte.

    "Đừng" tiếng Việt và "こんにちは" tiếng Nhật có số byte khác hẳn số ký tự; đếm byte là cách
    làm cho mọi bản dịch tiếng Việt trông như "dài bất thường".
    """
    if not text:
        return 0
    return len(unicodedata.normalize("NFC", text.strip()))


_CHI_SO_KY_HIEU = re.compile(r"^[\W\d_]+$", re.UNICODE)


class RegionQualityAssessor:
    """Chấm một vùng. Không chạm DB, không chạm mạng, không sửa dữ liệu đầu vào."""

    VERSION = "e12-rules-v1"

    def __init__(self, nguong: NguongLuat | None = None) -> None:
        self.nguong = nguong or NguongLuat()

    def assess(
        self,
        region,
        ocr=None,
        translation=None,
        typeset=None,
        page_dimensions: tuple[int, int] | None = None,
        vung_ke_ben_truoc=None,
    ) -> KetQuaCham:
        """`vung_ke_ben_truoc`: chữ gốc của vùng ngay TRƯỚC theo thứ tự đọc, để phát hiện từ bị
        ngắt dòng sang hai vùng. Không có thì bỏ qua luật đó, không đoán."""
        ly_do: list[str] = []
        bang_chung: dict = {}

        # ---- 1. Thiếu đầu vào: KHÔNG đánh giá được, và nói thẳng là không đánh giá được ----
        if region is None or not page_dimensions or page_dimensions[0] <= 0 or page_dimensions[1] <= 0:
            return KetQuaCham(
                relevance=RegionRelevance.uncertain,
                review_status=ReviewStatus.needs_review,
                overall_band=OverallBand.blocked,
                detector_confidence_state=ConfidenceState.unavailable,
                ocr_confidence_state=ConfidenceState.unavailable,
                translation_state=TranslationState.not_attempted,
                reason_codes=["assessment_input_missing"],
                evidence_snapshot={"thieu": "region" if region is None else "page_dimensions"},
            )

        rong, cao = page_dimensions

        # ---- 2. Tín hiệu từ bước nhận diện khung (M2) ----
        tt_khung = (
            ConfidenceState.unavailable if region.confidence is None
            else ConfidenceState.available
        )
        if region.status is RegionStatus.low_confidence:
            ly_do.append("detector_low_confidence")
            tt_khung = ConfidenceState.low
        if region.overlap_suspect:
            ly_do.append("detector_overlap_suspect")
        bang_chung["diem_tin_cay_khung"] = region.confidence

        # ---- 3. Tín hiệu từ bước đọc chữ (M3) ----
        chu_goc = (ocr.raw_text or "").strip() if ocr is not None else ""
        so_ky_tu_goc = do_dai_hien_thi(chu_goc)
        tt_ocr = ConfidenceState.unavailable
        if ocr is None:
            ly_do.append("ocr_missing")
        else:
            if ocr.confidence is None:
                # manga-ocr KHÔNG trả điểm. Đây là "không có điểm", không phải "điểm 0".
                ly_do.append("ocr_confidence_unavailable")
            elif ocr.confidence < self.nguong.ocr_confidence_low:
                ly_do.append("ocr_confidence_low")
                tt_ocr = ConfidenceState.low
            else:
                tt_ocr = ConfidenceState.available
            if not chu_goc:
                ly_do.append("ocr_empty")
            if ocr.status is OCRStatus.needs_manual:
                ly_do.append("ocr_needs_manual")
            bang_chung["engine_ocr"] = ocr.ocr_engine.value if ocr.ocr_engine else None
            bang_chung["diem_tin_cay_ocr"] = ocr.confidence
        bang_chung["so_ky_tu_goc"] = so_ky_tu_goc

        # ---- 4. Tín hiệu từ bước dịch (M5) ----
        ban_dich = (translation.translated_text or "").strip() if translation is not None else ""
        so_ky_tu_dich = do_dai_hien_thi(ban_dich)
        if translation is None:
            tt_dich = TranslationState.missing if chu_goc else TranslationState.not_attempted
            if chu_goc:
                ly_do.append("translation_missing")
        elif translation.status is TranslationStatus.fallback_used:
            tt_dich = TranslationState.fallback_used
            ly_do.append("translation_fallback_used")
        elif translation.status is TranslationStatus.pending and not ban_dich:
            # M5 để `pending` khi model không trả dòng nào — nghĩa là "chưa có bản dịch".
            tt_dich = TranslationState.missing if chu_goc else TranslationState.not_attempted
            if chu_goc:
                ly_do.append("translation_missing")
        else:
            tt_dich = TranslationState.present if ban_dich else TranslationState.missing
            if chu_goc and not ban_dich:
                ly_do.append("translation_empty")

        if chu_goc and ban_dich and so_ky_tu_goc >= self.nguong.length_ratio_min_chars:
            ty_le = so_ky_tu_dich / so_ky_tu_goc
            bang_chung["ty_le_do_dai"] = round(ty_le, 2)
            if ty_le > self.nguong.length_ratio_max or ty_le < self.nguong.length_ratio_min:
                ly_do.append("translation_length_outlier")
        bang_chung["so_ky_tu_dich"] = so_ky_tu_dich
        if translation is not None:
            bang_chung["engine_dich"] = translation.engine.value if translation.engine else None

        # ---- 5. Tín hiệu từ hình dạng nội dung ----
        # Đây là chỗ dễ sai nhất: "toàn số" hay "rất ngắn" KHÔNG có nghĩa là bỏ được.
        # `NO!` là thoại, `18` có thể là số trang mà cũng có thể là hình vẽ trong truyện.
        if chu_goc and _CHI_SO_KY_HIEU.match(chu_goc):
            ly_do.append("numeric_or_symbol_only")
        if chu_goc and so_ky_tu_goc <= self.nguong.short_text_max_chars:
            ly_do.append("short_stylized_text")
        if self._nghi_bi_ngat_dong(chu_goc, vung_ke_ben_truoc):
            ly_do.append("hyphenated_fragment_suspect")

        # ---- 6. Tín hiệu từ hình học khung ----
        dien_tich = (region.bbox_w * region.bbox_h) / float(rong * cao)
        bang_chung["ty_le_dien_tich"] = round(dien_tich, 5)
        if dien_tich < self.nguong.small_area_ratio:
            ly_do.append("small_region_suspect")
        elif dien_tich > self.nguong.large_area_ratio:
            ly_do.append("large_region_suspect")

        # ---- 7. Tín hiệu từ bước căn chữ (M6) ----
        if typeset is not None and typeset.fit_status is FitStatus.overflow_warning:
            ly_do.append("layout_overflow_warning")
            bang_chung["co_chu"] = typeset.font_size
        # F1 — vùng bị bỏ trống vì font thiếu glyph. Phải vào danh sách cần rà soát: nhìn trên
        # ảnh nó là một bong bóng trắng, không có dấu hiệu nào cho biết đã mất chữ.
        if typeset is not None and typeset.fit_status is FitStatus.font_missing_glyph:
            ly_do.append("layout_font_missing_glyph")
            bang_chung["co_chu"] = None

        return self._chot(ly_do, bang_chung, tt_khung, tt_ocr, tt_dich, chu_goc)

    # ------------------------------------------------------------------
    def _nghi_bi_ngat_dong(self, chu_goc: str, vung_truoc) -> bool:
        """Từ bị ngắt dòng qua hai vùng: vùng trước kết thúc bằng gạch nối, vùng này viết tiếp.

        Chỉ xét khi có vùng liền trước theo thứ tự đọc. Không có thì im lặng bỏ qua — đoán bừa
        ở đây sẽ gắn cờ cho mọi vùng có dấu gạch ngang trong câu.
        """
        if chu_goc.endswith("-"):
            return True
        truoc = (vung_truoc or "").strip()
        return bool(truoc.endswith("-") and chu_goc and chu_goc[:1].isalpha())

    def _chot(self, ly_do, bang_chung, tt_khung, tt_ocr, tt_dich, chu_goc) -> KetQuaCham:
        """Từ danh sách dấu hiệu suy ra phân loại + mức + ai phải xem.

        Luật vàng: **có dấu hiệu đáng kể thì đẩy cho người xem**, không tự quyết.
        """
        for ma in ly_do:
            assert ma in MA_LY_DO, f"mã lý do ngoài bảng trắng: {ma}"

        dang_ke = [m for m in ly_do if m not in MA_CHI_DE_BIET]

        # Phân loại: nói "có thể là", không nói "đây là".
        if "numeric_or_symbol_only" in ly_do:
            relevance = RegionRelevance.possible_number_or_decoration
        elif "short_stylized_text" in ly_do:
            relevance = RegionRelevance.possible_sfx
        elif not chu_goc or "ocr_empty" in ly_do or "ocr_missing" in ly_do:
            relevance = RegionRelevance.uncertain
        elif dang_ke:
            relevance = RegionRelevance.uncertain
        else:
            relevance = RegionRelevance.likely_translatable

        if not dang_ke:
            return KetQuaCham(
                relevance=RegionRelevance.likely_translatable,
                review_status=ReviewStatus.not_required,
                overall_band=OverallBand.clear,
                detector_confidence_state=tt_khung,
                ocr_confidence_state=tt_ocr,
                translation_state=tt_dich,
                reason_codes=ly_do,
                evidence_snapshot=bang_chung,
            )

        return KetQuaCham(
            relevance=relevance,
            review_status=ReviewStatus.needs_review,
            overall_band=OverallBand.attention,
            detector_confidence_state=tt_khung,
            ocr_confidence_state=tt_ocr,
            translation_state=tt_dich,
            reason_codes=ly_do,
            evidence_snapshot=bang_chung,
        )
