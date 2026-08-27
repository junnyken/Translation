"""Guardrail — giữ ranh giới kiến trúc khi M2 đưa model AI thật vào hệ thống.

M1: cấm mọi import model AI trong app/.
M2: model chỉ được phép sống trong worker (app/services/detect + app/workers).
    Đường đi HTTP (api/schemas/models/core) tuyệt đối không nạp model.
"""
from pathlib import Path

FORBIDDEN = (
    "torch",
    "manga_ocr",
    "paddleocr",
    "paddle",
    "onnxruntime",
    "cv2",
    "transformers",
    "ultralytics",
    "google.generativeai",
    "openai",
)

APP_DIR = Path(__file__).resolve().parent.parent / "app"
#: Chỉ 2 thư mục này được phép chạm tới runtime model.
ALLOWED_MODEL_DIRS = ("services/detect", "workers")


def _imports(py: Path) -> list[tuple[int, str]]:
    out = []
    for lineno, line in enumerate(py.read_text().splitlines(), 1):
        s = line.strip()
        if s.startswith("import ") or s.startswith("from "):
            out.append((lineno, s))
    return out


def test_duong_di_http_khong_nap_model_ai():
    hits = []
    for py in APP_DIR.rglob("*.py"):
        rel = py.relative_to(APP_DIR).as_posix()
        if any(rel.startswith(d) for d in ALLOWED_MODEL_DIRS):
            continue
        for lineno, stmt in _imports(py):
            for mod in FORBIDDEN:
                if f"import {mod}" in stmt or stmt.startswith(f"from {mod}"):
                    hits.append(f"{rel}:{lineno}: {stmt}")
    assert hits == [], f"Model AI lọt vào đường đi HTTP: {hits}"


def test_api_handler_khong_import_detector():
    """API chỉ được ENQUEUE job, không được gọi thẳng detector."""
    routes = (APP_DIR / "api" / "v1" / "routes.py").read_text()
    assert "CTDDetector" not in routes
    assert "detect_regions" not in routes
    assert "dispatch_detect_job" in routes


def test_import_app_khong_keo_theo_onnxruntime():
    """Tiến trình API không được nạp onnxruntime (nặng + không cần)."""
    import subprocess
    import sys

    code = (
        "import sys; import app.main;"
        " assert 'onnxruntime' not in sys.modules, 'API đã nạp onnxruntime';"
        " print('ok')"
    )
    r = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(APP_DIR.parent),
    )
    assert r.returncode == 0, r.stderr
    assert "ok" in r.stdout


def test_celery_da_dang_ky_dung_task_detect_cua_m2():
    from app.workers.celery_app import celery_app
    import app.workers.tasks  # noqa: F401

    user_tasks = {t for t in celery_app.tasks if not t.startswith("celery.")}
    assert user_tasks == {"detect.run_detect_job"}, user_tasks


def test_task_detect_co_timeout_khong_de_worker_treo():
    from app.workers.tasks import run_detect_job

    assert run_detect_job.soft_time_limit is not None
    assert run_detect_job.time_limit > run_detect_job.soft_time_limit
