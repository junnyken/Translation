"""E20b — `TesseractOCREngineBenchmarkAdapter`.

Gọi thẳng binary `tesseract` qua subprocess — KHÔNG thêm `pytesseract` vào requirements (đây là
harness benchmark, không phải dependency production; gọi CLI trực tiếp giữ dấu chân dependency
bằng 0 ở tầng Python). Tesseract **không cài trong image production** (`Dockerfile` không đổi —
constraint E20b) — cài tạm trong container benchmark một lần (`apt-get install`), không commit
vào image.

Tesseract có nhiều PSM (Page Segmentation Mode); ta chỉ benchmark 4 mode liên quan tới việc đọc
MỘT vùng chữ đã cắt sẵn (không phải cả trang): PSM 7 (một dòng), PSM 8 (một từ), PSM 11 (rải
rác, không theo khối), PSM 13 (dòng thô, bỏ qua bước phát hiện hướng/kịch bản của Tesseract) —
không giả định trước mode nào thắng.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

PSM_HO_TRO = (7, 8, 11, 13)


class TesseractKhongCoSan(RuntimeError):
    """Binary `tesseract` không có trong PATH — báo rõ, không âm thầm trả chuỗi rỗng."""


def co_san() -> bool:
    return shutil.which("tesseract") is not None


class TesseractOCREngineBenchmarkAdapter:
    def __init__(self, psm: int, lang: str = "eng") -> None:
        if psm not in PSM_HO_TRO:
            raise ValueError(f"PSM {psm} chưa được audit — chỉ hỗ trợ {PSM_HO_TRO}")
        if not co_san():
            raise TesseractKhongCoSan(
                "Không thấy binary `tesseract` trong PATH — cài tạm bằng "
                "`apt-get install tesseract-ocr tesseract-ocr-eng` trong container benchmark."
            )
        self.psm = psm
        self.lang = lang

    def ten_hien_thi(self) -> str:
        return f"tesseract_psm{self.psm}"

    def recognize(self, image: Image.Image) -> tuple[str, None]:
        """Cùng kiểu trả về `(text, confidence)` như `PaddleOCREngine.recognize` để dùng chung
        runner — Tesseract CLI (`stdout` output) không trả confidence trên mỗi lần gọi đơn giản
        này, nên `confidence` luôn `None` (KHÔNG bịa số — đúng nguyên tắc M3)."""
        with tempfile.TemporaryDirectory() as td:
            duong_dan = Path(td) / "anh.png"
            image.convert("RGB").save(duong_dan)
            ra = subprocess.run(
                ["tesseract", str(duong_dan), "stdout", "--psm", str(self.psm), "-l", self.lang],
                capture_output=True, text=True, timeout=30,
            )
        if ra.returncode != 0:
            raise RuntimeError(f"tesseract lỗi (mã {ra.returncode}): {ra.stderr[:300]}")
        return ra.stdout.strip(), None
