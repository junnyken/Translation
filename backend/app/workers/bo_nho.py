"""Đo và ghìm bộ nhớ của tiến trình worker (P3h).

Vì sao tệp này tồn tại: pilot 6 trang trên host làm worker bị **OOM killer giết** (`exit 137`),
và không ai thấy nó tới lúc chết — hệ thống **không có một chỉ số bộ nhớ nào**. `/healthz` báo
`status: ok` trong khi tiến trình đang tiến thẳng tới vực.

Nguyên tắc rút ra: *thứ không đo được thì không quản được, và nó sẽ hỏng vào lúc bất tiện nhất.*
Nên tệp này làm hai việc, theo đúng thứ tự quan trọng:

1. **Nhìn thấy** — `rss_mb()` đọc RSS thật, rẻ, không cần thư viện ngoài.
2. **Ghìm lại** — `giai_phong_model()` nhả các model ONNX/OCR không cần cho bước đang chạy.

Vì sao đọc `/proc/self/statm` chứ không dùng `psutil`: nó không có trong requirements, và thêm
một phụ thuộc chỉ để đọc một con số là cái giá không đáng. Bản chạy thật là Linux.
"""
from __future__ import annotations

import gc
import logging

logger = logging.getLogger(__name__)

#: Kích thước một trang bộ nhớ. Linux luôn 4096; đọc động để không đoán.
try:  # pragma: no cover - phụ thuộc nền tảng
    import os as _os

    _KICH_THUOC_TRANG = _os.sysconf("SC_PAGE_SIZE")
except Exception:  # pragma: no cover
    _KICH_THUOC_TRANG = 4096


def rss_mb() -> float | None:
    """Bộ nhớ thường trú (RSS) của tiến trình, tính bằng MB. `None` nếu không đọc được.

    Trả `None` chứ không trả 0: 0 nghĩa là "đo được và bằng không", còn đây là "không đo được".
    Hai thứ đó khác nhau, và gộp lại là cách nhanh nhất để có một biểu đồ nói dối.
    """
    try:
        with open("/proc/self/statm", "rb") as fh:
            so_trang = int(fh.read().split()[1])
        return round(so_trang * _KICH_THUOC_TRANG / 1e6, 1)
    except Exception:  # noqa: BLE001 - không đo được thì thôi, không được làm hỏng job
        return None


def ghi_moc(nhan: str) -> float | None:
    """Ghi một mốc RSS vào log. Gọi ở ranh giới các bước nặng."""
    r = rss_mb()
    if r is not None:
        logger.info("bộ nhớ [%s]: RSS %.1f MB", nhan, r)
    return r


def giai_phong_model(giu: set[str]) -> list[str]:
    """Nhả các model nặng KHÔNG nằm trong `giu`. Trả danh sách đã nhả (để log, không đoán).

    Tên hợp lệ: `detector`, `inpainter`, `ocr`.

    Đây là van xả, không phải chế độ thường trực: nhả rồi thì lượt sau phải nạp lại (LaMa ~197MB,
    CTD ~91MB), tức đánh đổi tốc độ lấy việc còn sống. Chỉ nên gọi khi RSS đã vượt ngưỡng.
    """
    from app.workers import tasks  # noqa: PLC0415 - vòng lặp import nếu đưa lên đầu tệp

    da_nha: list[str] = []
    if "detector" not in giu and getattr(tasks, "_detector", None) is not None:
        tasks._detector = None
        da_nha.append("detector")
    if "inpainter" not in giu and getattr(tasks, "_inpainter", None) is not None:
        tasks._inpainter = None
        da_nha.append("inpainter")
    if "ocr" not in giu and getattr(tasks, "_ocr_engines", None):
        tasks._ocr_engines.clear()
        da_nha.append("ocr")
    if da_nha:
        gc.collect()
    return da_nha


def ep_giai_phong_neu_cang(giu: set[str], nguong_mb: float) -> list[str]:
    """Chỉ nhả model khi RSS đã vượt ngưỡng — giữ cache ở đường chạy bình thường.

    `nguong_mb <= 0` ⇒ tắt hẳn cơ chế này (dùng cho máy phát triển và cho test).
    """
    if nguong_mb <= 0:
        return []
    truoc = rss_mb()
    if truoc is None or truoc < nguong_mb:
        return []
    da_nha = giai_phong_model(giu)
    if da_nha:
        logger.warning(
            "RSS %.1f MB vượt ngưỡng %.0f MB — đã nhả model %s, còn %.1f MB",
            truoc, nguong_mb, ", ".join(da_nha), rss_mb() or -1,
        )
    return da_nha
