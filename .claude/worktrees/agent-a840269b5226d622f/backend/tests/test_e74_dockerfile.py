"""E74 — canh thứ tự stage trong Dockerfile.

Production build KHÔNG có `--target` ⇒ Docker lấy stage CUỐI. Khi thêm `worker-gpu` (E74), đặt nó ở
cuối tệp là lượt deploy kế tiếp build nhầm image GPU (torch CUDA ~5GB) thay cho bản chạy thật — lỗi
này suýt xảy ra lúc viết E74.
"""
from __future__ import annotations

import re
from pathlib import Path

DOCKERFILE = Path(__file__).resolve().parents[1] / "Dockerfile"


def _stages() -> list[str]:
    return re.findall(r"^FROM\s+\S+\s+AS\s+(\S+)", DOCKERFILE.read_text(), flags=re.M | re.I)


def test_stage_cuoi_la_app_ban_chay_that():
    assert _stages()[-1] == "app"


def test_co_stage_worker_gpu_cho_ban_cai_cuc_bo():
    assert "worker-gpu" in _stages()


def test_app_khong_ke_thua_worker_gpu():
    m = re.search(r"^FROM\s+(\S+)\s+AS\s+app\b", DOCKERFILE.read_text(), flags=re.M | re.I)
    assert m and m.group(1) == "worker"
