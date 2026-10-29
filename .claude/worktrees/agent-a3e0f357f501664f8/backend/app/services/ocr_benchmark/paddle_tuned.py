"""E20b phụ lục — PaddleOCR với tham số DETECTION đổi được, chỉ dùng cho benchmark.

## Vì sao cần tệp này dù E20b đã chạy 9 path

9 path của E20b đều chỉ đổi **pixel đầu vào** (xám hoá, phóng to, tăng tương phản, ngưỡng thích
nghi) rồi đưa cho PaddleOCR mặc định. Không path nào đụng vào **cách bộ detect của chính
PaddleOCR diễn giải bản đồ xác suất** — trong khi `REPORT_E20a.md §10` chốt nguyên nhân gốc nằm
đúng ở bước detect nội bộ đó (chữ nét mảnh trên nền bận không được phát hiện). Đây là cần gạt
khác hẳn, chưa từng thử.

## Vì sao KHÔNG sửa `PaddleOCREngine` production

Constraint E20b #1: benchmark không được đổi hành vi OCR production. Kế thừa rồi ghi đè
`build_kwargs()` giữ tệp production nguyên vẹn tuyệt đối — không thêm cả tham số tuỳ chọn mặc
định `None` (thứ vẫn đọc như một cánh cửa để ai đó bật lên sau này mà không qua benchmark).

Tên tham số theo **PaddleOCR 3.7.0** (`text_det_*`), không phải tên `det_db_*` của bản 2.x —
đã kiểm bằng `inspect.signature(PaddleOCR.__init__)` trong chính container worker.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.ocr.engines import PaddleOCREngine


@dataclass(frozen=True)
class CauHinhDetect:
    """Một bộ tham số detection ĐẶT TÊN + CHỐT TRƯỚC khi chạy.

    `frozen=True` là cố ý: sau khi thấy kết quả xấu, không sửa được tại chỗ để "cứu" con số —
    muốn đổi phải sửa mã và chạy lại cả lượt, và lượt đó phải được ghi vào báo cáo như một
    lượt riêng. Đây là cùng kỷ luật chống p-hacking mà E20b gốc đã tự đặt (`REPORT_E20b.md §3`).
    """

    ten: str
    #: Mô tả cần gạt này nhắm vào giả thuyết nào — bắt buộc, để đọc bảng kết quả biết đang đo gì.
    gia_thuyet: str
    tham_so: dict[str, float] = field(default_factory=dict)

    def mo_ta_tham_so(self) -> str:
        if not self.tham_so:
            return "(mặc định thư viện — không truyền gì)"
        return ", ".join(f"{k}={v}" for k, v in sorted(self.tham_so.items()))


class PaddleOCRDetectTuned(PaddleOCREngine):
    """`PaddleOCREngine` + ghi đè tham số detection. CHỈ dùng trong benchmark."""

    def __init__(self, cau_hinh: CauHinhDetect, lang: str = "en", device: str = "cpu") -> None:
        super().__init__(lang=lang, device=device)
        self.cau_hinh = cau_hinh

    def build_kwargs(self) -> dict:
        kwargs = super().build_kwargs()
        kwargs.update(self.cau_hinh.tham_so)
        return kwargs


#: Các cấu hình CHỐT TRƯỚC khi chạy, lấy thẳng từ khoảng khuyến nghị trong mini-spec E20b
#: ("lower det_db_thresh/box_thresh to catch weak/faint detections", "increase unclip_ratio to
#: avoid cutting off first/last characters"). KHÔNG dò thêm giá trị sau khi thấy kết quả.
CAC_CAU_HINH: tuple[CauHinhDetect, ...] = (
    CauHinhDetect(
        ten="det_baseline",
        gia_thuyet="ĐỐI CHỨNG — không truyền gì, phải tái hiện đúng số của REPORT_E20b §7",
        tham_so={},
    ),
    CauHinhDetect(
        ten="det_nhay",
        gia_thuyet="Hạ cả hai ngưỡng + nới khung: bắt nét mảnh đang bị bỏ sót (khoảng giữa)",
        tham_so={"text_det_thresh": 0.2, "text_det_box_thresh": 0.4, "text_det_unclip_ratio": 2.0},
    ),
    CauHinhDetect(
        ten="det_rat_nhay",
        gia_thuyet="Như trên nhưng đẩy tới đầu mút khuyến nghị — nếu vẫn 0/10 thì cần gạt này hết đường",
        tham_so={"text_det_thresh": 0.15, "text_det_box_thresh": 0.3, "text_det_unclip_ratio": 2.5},
    ),
    CauHinhDetect(
        ten="det_no_khung",
        gia_thuyet="CÔ LẬP giả thuyết 'khung cắt mất chữ đầu/cuối' — chỉ nới unclip, giữ nguyên ngưỡng",
        tham_so={"text_det_unclip_ratio": 2.0},
    ),
)

#: `text_det_limit_side_len` CỐ Ý không có trong danh sách trên: mọi crop của bộ E20b có cạnh dài
#: ≤600px, nhỏ hơn hẳn mặc định (~960) nên KHÔNG có phép thu nhỏ nào xảy ra — nâng ngưỡng đó lên
#: là một phép đo rỗng. Đã đo kích thước thật trước khi loại, không loại theo cảm tính.
LY_DO_BO_LIMIT_SIDE_LEN = (
    "mọi crop ≤600px < mặc định ~960 ⇒ không có phép thu nhỏ để mà chặn"
)
