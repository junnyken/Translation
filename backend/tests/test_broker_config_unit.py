"""P3k — khoá ràng buộc giữa `visibility_timeout` và trần thời lượng task.

Hai tham số này nằm ở hai tệp khác nhau và **không ai nhắc ai**. Nâng một trần task lên quá
`visibility_timeout` là mở đường cho Redis giao lại task **trong khi nó vẫn đang chạy** ⇒ hai lượt
cùng một việc trên cùng một trang. Với `--pool=solo`, task kẹt trong mã native (ONNX) thì
`soft_time_limit` cũng không cắt được, nên đây là rủi ro có thật — và hai lượt inpaint cùng lúc
chính là thứ đã gây OOM ở pilot hosted 03/09.

Test này tồn tại để lần sau ai đó nâng một timeout sẽ bị chặn ngay, thay vì phát hiện qua một sự
cố chạy trùng trên bản chạy thật.
"""
from __future__ import annotations

from app.core.config import get_settings
from app.workers.celery_app import celery_app


def _tran_cung_lon_nhat(s) -> tuple[str, int]:
    """Trần CỨNG (`time_limit`) của từng task, đúng như khai trong `tasks.py`."""
    tran = {
        "detect": s.detect_timeout_seconds + 15,
        "ocr": s.ocr_timeout_seconds + 30,
        "inpaint": s.inpaint_timeout_seconds + 30,
        "translate": s.translate_timeout_seconds + 30,
        "typeset": s.typeset_timeout_seconds + 30,
        "refit": s.refit_timeout_seconds + 30,
        "export": s.export_timeout_seconds + 30,
    }
    ten = max(tran, key=tran.get)
    return ten, tran[ten]


def test_visibility_timeout_duoc_dat_TUONG_MINH():
    """Sống nhờ mặc định thư viện là một con số không ai chọn, không ai ghi, không ai kiểm."""
    opts = celery_app.conf.broker_transport_options or {}
    assert "visibility_timeout" in opts, (
        "chưa đặt visibility_timeout ⇒ đang dùng mặc định ngầm của Celery/Redis"
    )


def test_visibility_timeout_phai_lon_hon_tran_task():
    vt = celery_app.conf.broker_transport_options["visibility_timeout"]
    ten, tran = _tran_cung_lon_nhat(get_settings())
    assert vt > tran, (
        f"visibility_timeout={vt}s KHÔNG lớn hơn trần cứng của task '{ten}' ({tran}s) ⇒ Redis sẽ "
        "giao lại task trong khi nó vẫn đang chạy, gây chạy trùng trên cùng một trang"
    )


def test_con_bien_an_toan_it_nhat_50_phan_tram():
    """Lớn hơn thôi chưa đủ: hết trần mềm rồi còn phải dọn dẹp, ghi CSDL, nhả model."""
    vt = celery_app.conf.broker_transport_options["visibility_timeout"]
    ten, tran = _tran_cung_lon_nhat(get_settings())
    assert vt >= tran * 1.5, (
        f"visibility_timeout={vt}s chỉ hơn trần '{ten}' ({tran}s) {vt/tran:.2f} lần — quá sát, "
        "không còn chỗ cho phần dọn dẹp sau khi task hết giờ"
    )


def test_acks_late_van_bat():
    """Ràng buộc trên chỉ có nghĩa khi acks_late bật — tắt nó thì mất luôn việc giao lại."""
    assert celery_app.conf.task_acks_late is True
