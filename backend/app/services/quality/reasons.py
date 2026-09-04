"""Bảng trắng mã lý do của E12 và cách nói chúng ra bằng tiếng Việt.

Vì sao là bảng TRẮNG chứ không phải chữ tự do: mã lý do đi thẳng ra giao diện và vào bảng đếm.
Cho phép chữ tự do là sớm muộn có hai chỗ viết hai kiểu cho cùng một chuyện, rồi không đếm được
nữa. Thêm mã mới phải sửa đúng ở đây, và test sẽ bắt nếu quên dịch sang tiếng Việt.
"""
from __future__ import annotations

#: 18 mã chốt ở spec E12 v1 + 1 mã của F1 (bong bóng rỗng vì font thiếu glyph).
#: KHÔNG sinh mã ở nơi khác — thêm mã mới phải khai ở đúng bảng này.
MA_LY_DO: dict[str, str] = {
    # --- tín hiệu từ bước nhận diện khung (M2) ---
    "detector_low_confidence": "Khung chữ có điểm nhận diện thấp.",
    "detector_overlap_suspect": "Khung chữ chồng lên khung khác.",
    # --- tín hiệu từ bước đọc chữ (M3) ---
    "ocr_missing": "Chưa đọc chữ cho vùng này.",
    "ocr_empty": "OCR không đọc được nội dung nào.",
    "ocr_needs_manual": "Bước đọc chữ đã tự đánh dấu cần kiểm tra tay.",
    "ocr_confidence_low": "Điểm tin cậy khi đọc chữ thấp.",
    "ocr_confidence_unavailable": "Engine OCR không cung cấp điểm tin cậy.",
    # --- tín hiệu từ bước dịch (M5) ---
    "translation_missing": "Chưa có bản dịch cho vùng này.",
    "translation_empty": "Bản dịch rỗng trong khi chữ gốc có nội dung.",
    "translation_fallback_used": "Đã lùi về đường dịch nhanh vì dịch theo ngữ cảnh lỗi.",
    "translation_length_outlier": "Bản dịch dài bất thường so với chữ gốc.",
    # --- tín hiệu từ hình dạng nội dung ---
    "numeric_or_symbol_only": "Chỉ có số hoặc ký hiệu — có thể là số trang/trang trí.",
    "short_stylized_text": "Chữ rất ngắn — có thể là tiếng động hoặc chữ cách điệu.",
    "hyphenated_fragment_suspect": "Có thể là một từ bị ngắt dòng sang vùng kế bên.",
    # --- tín hiệu từ hình học khung ---
    "small_region_suspect": "Khung rất nhỏ so với trang.",
    "large_region_suspect": "Khung rất lớn so với trang.",
    # --- tín hiệu từ bước căn chữ (M6) ---
    "layout_overflow_warning": "Chữ dịch chưa vừa khung.",
    # F1 — nặng hơn tràn khung: bong bóng này đang RỖNG.
    "layout_font_missing_glyph": "Chưa chèn được chữ: font không có ký tự trong bản dịch.",
    # --- không đánh giá được ---
    "assessment_input_missing": "Thiếu dữ liệu để đánh giá vùng này.",
}

#: Mã CHỈ mang tính thông tin: có mặt cũng không đủ để bắt người dùng rà soát.
#: `ocr_confidence_unavailable` nằm đây vì manga-ocr **không bao giờ** trả điểm tin cậy — bắt
#: rà soát vì lý do đó là bắt rà soát toàn bộ trang tiếng Nhật.
MA_CHI_DE_BIET = frozenset({"ocr_confidence_unavailable"})


def nhan_ly_do(ma: str) -> str:
    """Câu tiếng Việt cho một mã. Mã lạ thì nói thẳng là lạ, không im lặng bỏ qua."""
    return MA_LY_DO.get(ma, f"Dấu hiệu chưa có mô tả: {ma}")
