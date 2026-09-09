"""E22 (thu hẹp theo audit) — đọc lại bằng chứng thoát tiến trình mà `deploy-start.sh` ĐÃ ghi sẵn.

`deploy-start.sh` từ P3m đã ghi `ma_thoat_gan_nhat` vào `WORKER_STATE_FILE` (mặc định
`/tmp/trang-thai-worker.json`) mỗi lần vòng lặp restart bắt được worker thoát — `/healthz` đã đọc
tệp này. Module này KHÔNG ghi gì mới, chỉ đọc lại đúng tệp đó để `hoi_phuc.don_job_mo_coi()` có
bằng chứng phân loại job mồ côi, thay vì gán chung một lý do cho mọi trường hợp.

Cố tình KHÔNG có giá trị phân loại `resource_limit_confirmed`: hệ thống hiện không có nguồn nào
(VibeHost/OOM-killer log) xác nhận được nguyên nhân thật — nói "nghi ngờ" (`_suspected`) là câu
trả lời trung thực, nói "chắc chắn" là bịa (đúng nguyên tắc audit §5.6/#2 của E22).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

#: Trùng mặc định với `deploy-start.sh`/`app/main.py:healthz` — CỐ Ý lặp lại thay vì import chéo
#: sang shell script; đổi một bên thì `test_doc_trang_thai_worker_dung_duong_dan_mac_dinh` sẽ đỏ.
_DUONG_DAN_MAC_DINH = "/tmp/trang-thai-worker.json"

#: SIGKILL. Đây là con số duy nhất mà `deploy-start.sh` tự diễn giải ra "nghi ngờ hết bộ nhớ" —
#: giữ đúng một chỗ định nghĩa để không lệch giữa shell script và Python.
_MA_SIGKILL = 137


def doc_trang_thai_worker() -> dict:
    """Đọc lại y hệt cách `/healthz` đọc (`app/main.py`) — cùng đường dẫn, cùng kiểu lỗi nuốt êm.

    Trả `{"trang_thai": "khong_ro"}` nếu không đọc được — chạy ở máy nhà (worker là tiến trình
    riêng, không có tệp này) không phải lỗi, không phải chỗ để raise.
    """
    duong_dan = Path(os.environ.get("WORKER_STATE_FILE", _DUONG_DAN_MAC_DINH))
    try:
        return json.loads(duong_dan.read_text())
    except Exception:  # noqa: BLE001 - đọc bằng chứng phụ, không được chặn dọn job mồ côi
        return {"trang_thai": "khong_ro"}


def phan_loai_tu_ma_thoat(ma_thoat: int | None) -> tuple[str, str | None]:
    """(error_class, exit_signal) từ mã thoát tiến trình worker gần nhất.

    `ma_thoat=None` (chưa từng ghi nhận, hoặc tệp thiếu trường) vẫn xếp `worker_lost` — bản thân
    việc `don_job_mo_coi` chạy tới đây ĐÃ LÀ bằng chứng worker vừa chết (xem docstring
    `hoi_phuc.py`), chỉ là không biết thêm chi tiết mã thoát.
    """
    if ma_thoat == _MA_SIGKILL:
        return "resource_limit_suspected", f"SIGKILL({_MA_SIGKILL})"
    if ma_thoat is None:
        return "worker_lost", None
    return "worker_lost", f"exit({ma_thoat})"


def doc_va_phan_loai() -> tuple[str, str | None]:
    """Tiện ích gộp: đọc tệp trạng thái rồi phân loại luôn — cái `don_job_mo_coi()` thật sự gọi."""
    trang_thai = doc_trang_thai_worker()
    return phan_loai_tu_ma_thoat(trang_thai.get("ma_thoat_gan_nhat"))
