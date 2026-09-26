"""Celery app — khung hàng đợi cho M2-M9.

M2 đăng ký task thật đầu tiên: `detect.run_detect_job` (app/workers/tasks.py),
tiêu thụ Job(type=detect) do endpoint upload page tạo ra.
"""
import logging

from celery import Celery
from celery.signals import worker_ready

from app.core.config import get_settings

settings = get_settings()

# --- Chặn tiếng ồn log của `httpx` -------------------------------------------------------------
#
# ## Hiện tượng
#
# Log worker bị lụt: một lượt chạy 76 dòng thì gần như toàn bộ là
# `HTTP Request: HEAD https://huggingface.co/... "HTTP/1.1 200 OK"`. Dòng ghi tên model AI và dòng
# của luật E47 bị đẩy ra khỏi bộ đệm — HAI LẦN liên tiếp không xác nhận được model đang chạy.
#
# ## Nguyên nhân THẬT — không phải cache của ta hỏng
#
# Chính log nói rõ `Model files already exist. Using cached files.` ⇒ **cache VẪN hit**. Tiếng ồn
# đến từ `huggingface_hub` đi hỏi máy chủ xem tệp đã tải còn mới không, mỗi lần khởi tạo
# PaddleOCR, cho TỪNG tệp. Nó gọi qua `httpx`, và `httpx` ghi mỗi request một dòng ở mức INFO.
#
# Đừng đi sửa khoá cache / TTL / logic cache trong mã ta — **không có gì sai ở đó**.
#
# ## Vì sao hạ `httpx` chứ không đặt `HF_HUB_OFFLINE=1`
#
# `HF_HUB_OFFLINE=1` sẽ chặn luôn lượt tải LẦN ĐẦU: container mới, cache rỗng ⇒ worker chết ngay
# thay vì tải model về. Hạ log level không đổi hành vi nào, chỉ bớt dòng.
#
# Không đụng logger khác: mã của ta gọi Gemini bằng `urllib`, nên hạ `httpx` không giấu mất lượt
# gọi AI nào. Giữ WARNING để lỗi mạng thật vẫn hiện.
logging.getLogger("httpx").setLevel(logging.WARNING)

celery_app = Celery(
    "translation",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)
celery_app.conf.update(
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    timezone="Asia/Ho_Chi_Minh",
    # Khi chạy thật, worker và Redis khởi động không cùng lúc. Không bật cái này thì Celery 6 sẽ
    # KHÔNG thử lại lúc mới bật và worker chết ngay nếu Redis chậm hơn vài giây.
    broker_connection_retry_on_startup=True,
    # P3k — ĐẶT TƯỜNG MINH, không sống nhờ mặc định của thư viện.
    #
    # `task_acks_late=True` ở trên nghĩa là task chỉ được ack KHI XONG, nên worker chết giữa chừng
    # thì broker GIAO LẠI. Với Redis, "giao lại" xảy ra sau `visibility_timeout`. Không đặt thì
    # Celery dùng mặc định 3600s — một con số không ai chọn, không ai ghi, và không ai kiểm.
    #
    # RÀNG BUỘC BẮT BUỘC: giá trị này phải LỚN HƠN trần cứng của task lâu nhất. Thấp hơn thì
    # Redis giao lại trong khi task VẪN ĐANG CHẠY ⇒ hai lượt cùng một việc trên cùng một trang.
    # Với `--pool=solo`, một task kẹt trong mã native (ONNX) thì `soft_time_limit` cũng không cắt
    # được, nên chạy trùng là rủi ro có thật — và hai lượt inpaint cùng lúc chính là thứ đã gây
    # OOM ở pilot. `test_visibility_timeout_phai_lon_hon_tran_task` khoá ràng buộc này lại.
    #
    # Vì sao 1800 chứ không thấp hơn: trần task lớn nhất hiện là 930s (translate/export). 1800 cho
    # gần gấp đôi biên an toàn, đồng thời rút thời gian giao lại từ 60 phút xuống 30.
    # Vì sao không cố hạ sâu hơn: việc làm thất bại HIỆN RA NGAY đã do P3j lo (quét lúc worker
    # khởi động). Đổi rủi ro chạy trùng để lấy thêm vài phút khôi phục là một món hời tồi.
    broker_transport_options={"visibility_timeout": 1800},
)

# --- E50: lịch chạy định kỳ ---------------------------------------------------------------
#
# Dự án TRƯỚC ĐÂY KHÔNG có lịch chạy định kỳ nào — quét cả `celery_app.py`, `deploy-start.sh` và
# compose đều trống. Đây là cơ chế MỚI, không phải tái dùng cái sẵn có.
#
# ## Vì sao beat nhúng (`-B`) chứ không dựng tiến trình riêng
#
# Topology hiện tại là **đúng một** worker `--pool=solo` trên một máy chủ đã bó 4096 MB, mà
# worker đã bị hệ điều hành giết 3 lần. Dựng thêm một container beat là thêm một tiến trình Python
# nữa cùng toàn bộ thư viện — trả giá bộ nhớ thật để lấy một thứ chưa cần.
#
# Đánh đổi đã biết: tài liệu Celery khuyên không dùng beat nhúng ở production vì nó không chịu
# được nhiều worker. Với đúng một worker thì ràng buộc đó không áp. Ngày nào chạy nhiều worker,
# phải tách beat ra TRƯỚC — nếu không mỗi worker sẽ tự chạy lịch của riêng nó và lượt dọn chạy
# chồng lên nhau.
#
# ## Vì sao lịch đăng ký CÓ ĐIỀU KIỆN
#
# `bat_lich_don_tep` mặc định TẮT. Đây là hành vi **xoá dữ liệu không hoàn tác được**, nên nó
# phải bật tường minh sau khi đã quan sát mốc `het_han_luc` được ghi đúng trên bản chạy thật.
# Đăng ký lịch rồi để task tự kiểm cờ cũng được, nhưng như vậy beat vẫn đánh thức worker mỗi
# 5 phút để chạy một hàm trả về ngay — tiếng ồn vô ích trên tiến trình đang bó bộ nhớ.
if settings.bat_lich_don_tep:
    celery_app.conf.beat_schedule = {
        "don-tep-het-han": {
            "task": "vong_doi.don_tep_het_han",
            "schedule": float(settings.don_tep_moi_giay),
            # `expires` ngắn hơn chu kỳ: worker bận lâu thì bỏ hẳn lượt cũ thay vì dồn một hàng
            # dài lượt dọn rồi chạy liên tiếp đúng lúc worker đang yếu.
            "options": {"expires": float(settings.don_tep_moi_giay) - 10},
        }
    }


@worker_ready.connect
def _don_job_mo_coi_luc_khoi_dong(**_):
    """P3j — worker vừa sống lại nghĩa là worker trước đã chết; job nào còn `running` là mồ côi.

    Bọc trong try/except có chủ đích: dọn dẹp hỏng thì **không được** ngăn worker nhận việc. Một
    worker chạy được mà chưa dọn còn hơn một worker không chạy.
    """
    if not settings.worker_sweep_orphan_jobs_on_start:
        return
    try:
        from app.core.db_sync import sync_session
        from app.workers.hoi_phuc import don_job_mo_coi

        with sync_session() as s:
            don_job_mo_coi(s, ap_dung=True)
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).exception("dọn job mồ côi lỗi — bỏ qua, worker vẫn nhận việc")

    # E23 — dọn xong CHƯA đủ: mẻ vẫn đứng im. `dispatch_next` chỉ chạy khi một trang tới trạng
    # thái cuối, mà sau sự cố thì không còn trang nào đang chạy để mà kết thúc. Đo được hai lần:
    # mẻ nằm im với các mục `pending` cho tới khi người dùng tự bấm "Chạy lại".
    #
    # PHẢI chạy SAU lượt quét: quét mới là thứ đưa mục mẻ mồ côi từ `running` về `failed`, giải
    # phóng chỗ chạy. Gọi trước thì `dispatch_next` thấy chỗ vẫn bị chiếm và không đẩy được gì.
    #
    # Chỉ đẩy mục `pending` (trang CHƯA từng chạy) — job vừa giết worker đã nằm ở `failed` nên
    # KHÔNG bị xếp lại. Nguyên tắc "Không tự chạy lại" của `hoi_phuc.py` vẫn nguyên vẹn.
    if not settings.batch_enabled or not settings.batch_danh_thuc_khi_worker_khoi_dong:
        return
    try:
        from app.services.batch.factory import tao_dieu_phoi

        tao_dieu_phoi(settings).danh_thuc_me_dang_do()
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).exception("đánh thức mẻ lỗi — bỏ qua, worker vẫn nhận việc")
