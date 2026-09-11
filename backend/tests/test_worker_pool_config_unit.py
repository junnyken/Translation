"""E23 — khoá pool Celery của bàn thử local vào ĐÚNG pool của production.

## Vì sao test này tồn tại

Đo thật ở E23 (lượt 24 trang, 2026-09-10): một cú SIGKILL trên bàn thử local để lại **một job
nằm `running` và một trang nằm `detecting` suốt 20+ phút**, cột `error_class`/`exit_signal` rỗng,
không có lượt quét job mồ côi nào chạy. Nhìn thì y như một lỗi hồi phục nghiêm trọng của E22.

Thực ra đó là **lỗi CHỈ CÓ ở local**, do bàn thử dùng pool khác production:

| | Pool | SIGKILL giết gì | `worker_ready` chạy lại? | Quét mồ côi |
|---|---|---|---|---|
| production (`deploy-start.sh`) | `--pool=solo` | cả worker ⇒ vòng bật lại khởi động lại | **CÓ** | **chạy** |
| local (trước bản sửa này) | `--concurrency=1` (prefork) | chỉ tiến trình CON | KHÔNG | **không chạy** |

Với prefork, Celery sinh tiến trình con thay thế và tiến trình chính sống tiếp, nên tín hiệu
`worker_ready` — thứ duy nhất kích hoạt `don_job_mo_coi` (`celery_app.py`) — không bao giờ phát
lại. Job mồ côi nằm lại vĩnh viễn.

Điều đó làm bàn thử **không tái hiện được chế độ hỏng quan trọng nhất của hệ thống**. Một bàn thử
lệch production ở đúng chỗ đó thì mọi kết luận độ tin cậy rút từ nó đều vô giá trị — theo cả hai
chiều: nó vừa báo động giả (job kẹt mà production không kẹt), vừa có thể **che** một lỗi thật.

Test này chặn việc lệch lại. Cùng họ với `test_broker_config_unit.py`: hai tệp cấu hình ở hai chỗ
khác nhau và **không ai nhắc ai**.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

GOC = Path(__file__).resolve().parents[2]
COMPOSE = GOC / "deploy" / "docker-compose.yml"
DEPLOY_SH = GOC / "backend" / "deploy-start.sh"

#: Chỉ những pool KHÔNG fork mới giữ được tính chất "SIGKILL giết cả worker".
POOL_KHONG_FORK = {"solo"}


def _doc(p: Path) -> str:
    if not p.exists():
        pytest.fail(f"không tìm thấy {p} — test này canh cấu hình thật, không canh giả định")
    return p.read_text(encoding="utf-8")


def _pool(noi_dung: str, nhan: str) -> str:
    """Rút `--pool=<x>` từ lệnh celery worker. Không có `--pool` thì là prefork (mặc định Celery).

    Phải NỐI dòng tiếp nối (`\\` cuối dòng) trước khi tìm. `deploy-start.sh` viết lệnh trên ba
    dòng và `--pool=solo` nằm ở dòng thứ hai — dòng đó có chữ "celery" (trong `-Q celery`) nhưng
    KHÔNG có chữ "worker". Bản đầu của hàm này lọc theo từng dòng nên bỏ sót `--pool` và báo
    production dùng prefork. Chính test này bắt được lỗi đó.
    """
    phang = re.sub(r"\\\s*\n\s*", " ", noi_dung)  # nối dòng tiếp nối của shell
    dong_celery = [d for d in phang.splitlines()
                   if "celery" in d and "worker" in d and not d.strip().startswith("#")]
    if not dong_celery:
        pytest.fail(f"{nhan}: không tìm thấy lệnh celery worker nào")
    gop = " ".join(dong_celery)
    khop = re.search(r"--pool[= ]([a-z]+)", gop)
    return khop.group(1) if khop else "prefork"


def test_production_dung_pool_khong_fork():
    """Nền móng của cả chuỗi hồi phục E22: SIGKILL phải giết CẢ worker để vòng bật lại chạy."""
    pool = _pool(_doc(DEPLOY_SH), "deploy-start.sh")
    assert pool in POOL_KHONG_FORK, (
        f"production đang dùng pool '{pool}' — pool có fork thì SIGKILL chỉ giết tiến trình con, "
        "`worker_ready` không phát lại, và `don_job_mo_coi` không bao giờ chạy ⇒ job mồ côi nằm "
        "`running` vĩnh viễn"
    )


def test_pool_celery_phai_khop_production():
    """Bàn thử local phải dùng ĐÚNG pool của production, nếu không nó đo một hệ thống khác."""
    pool_prod = _pool(_doc(DEPLOY_SH), "deploy-start.sh")
    pool_local = _pool(_doc(COMPOSE), "docker-compose.yml")
    assert pool_local == pool_prod, (
        f"local dùng pool '{pool_local}' còn production dùng '{pool_prod}'. Lệch ở đây nghĩa là "
        "bàn thử không tái hiện được chế độ hỏng khi worker bị giết — E23 đã mất 20 phút truy một "
        "'lỗi' chỉ tồn tại ở local vì đúng lý do này."
    )


def test_pool_solo_o_local_phai_kem_co_che_bat_lai():
    """`solo` mà không có cơ chế bật lại thì SIGKILL giết HẲN worker — tệ hơn prefork.

    Với prefork, Celery sinh tiến trình con thay thế nên worker vẫn phục vụ tiếp (chỉ mất job đang
    chạy). Với solo, SIGKILL giết cả tiến trình chính. Production chịu được vì `deploy-start.sh`
    có vòng `while true` bật lại; ở local thì phải là `restart` của Docker. Thiếu nó, "khớp
    production" chỉ đúng một nửa và nửa còn lại làm bàn thử tệ đi.
    """
    if _pool(_doc(COMPOSE), "docker-compose.yml") not in POOL_KHONG_FORK:
        pytest.skip("local không dùng pool solo nên ràng buộc này không áp")

    noi_dung = _doc(COMPOSE)
    khoi_worker = noi_dung.split("\n  worker:", 1)
    assert len(khoi_worker) == 2, "không tìm thấy service `worker` trong docker-compose.yml"
    # Cắt tới service kế tiếp (thụt 2 dấu cách) để chỉ xét đúng khối của worker.
    than = re.split(r"\n  [a-z_-]+:", khoi_worker[1])[0]
    assert re.search(r"^\s+restart:\s*\S+", than, re.MULTILINE), (
        "service `worker` dùng --pool=solo nhưng KHÔNG có `restart:` — SIGKILL sẽ giết hẳn "
        "container, `worker_ready` không bao giờ phát lại, và quét job mồ côi không chạy"
    )


def test_quet_mo_coi_van_gan_vao_worker_ready():
    """Nếu ai đó tháo `worker_ready` thì lý lẽ của hai test trên sụp — phải đỏ ngay.

    Test này KHÔNG nói `worker_ready` là cách đúng duy nhất; nó nói: ràng buộc pool ở trên chỉ
    có giá trị *vì* quét mồ côi phụ thuộc tín hiệu này. Đổi cách kích hoạt thì phải đọc lại cả ba.
    """
    noi_dung = (GOC / "backend" / "app" / "workers" / "celery_app.py").read_text(encoding="utf-8")
    assert "worker_ready" in noi_dung, "không còn thấy worker_ready trong celery_app.py"
    assert "don_job_mo_coi" in noi_dung, "không còn thấy don_job_mo_coi trong celery_app.py"
