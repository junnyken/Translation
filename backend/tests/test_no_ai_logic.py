"""Guardrail — giữ ranh giới kiến trúc khi M2 đưa model AI thật vào hệ thống.

M1: cấm mọi import model AI trong app/.
M2: model detect chỉ sống trong worker (app/services/detect + app/workers).
M3: engine OCR cũng vậy (app/services/ocr) — và phải import TRỄ, không nạp lúc import module.
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
#: Chỉ 3 thư mục này được phép chạm tới runtime model (M2: detect, M3: ocr).
ALLOWED_MODEL_DIRS = ("services/detect", "services/ocr", "workers")


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
    assert user_tasks == {"detect.run_detect_job", "ocr.run_ocr_job"}, user_tasks


def test_task_detect_co_timeout_khong_de_worker_treo():
    from app.workers.tasks import run_detect_job

    assert run_detect_job.soft_time_limit is not None
    assert run_detect_job.time_limit > run_detect_job.soft_time_limit


# ---------------- M3: engine OCR cũng chỉ được sống trong worker ----------------

OCR_LIBS = ("manga_ocr", "paddleocr", "paddle", "torch", "transformers")
#: Thêm services/ocr vào danh sách thư mục được phép chạm runtime model.
ALLOWED_OCR_DIRS = ("services/ocr", "services/detect", "workers")


def test_duong_di_http_khong_nap_thu_vien_ocr():
    hits = []
    for py in APP_DIR.rglob("*.py"):
        rel = py.relative_to(APP_DIR).as_posix()
        if any(rel.startswith(d) for d in ALLOWED_OCR_DIRS):
            continue
        for lineno, stmt in _imports(py):
            for mod in OCR_LIBS:
                if f"import {mod}" in stmt or stmt.startswith(f"from {mod}"):
                    hits.append(f"{rel}:{lineno}: {stmt}")
    assert hits == [], f"Thư viện OCR lọt vào đường đi HTTP: {hits}"


def test_import_app_khong_keo_theo_thu_vien_ocr():
    """Tiến trình API không được nạp manga_ocr/paddleocr/torch."""
    import subprocess
    import sys

    code = (
        "import sys; import app.main;"
        " bad=[m for m in ('manga_ocr','paddleocr','paddle','torch','transformers')"
        "      if m in sys.modules];"
        " assert not bad, f'API đã nạp {bad}';"
        " print('ok')"
    )
    r = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=str(APP_DIR.parent)
    )
    assert r.returncode == 0, r.stderr
    assert "ok" in r.stdout


def test_engine_ocr_import_tre_khong_nap_luc_import_module():
    """Import module engine KHÔNG được kéo theo torch/paddle (chỉ nạp khi thực sự OCR)."""
    import subprocess
    import sys

    code = (
        "import sys; import app.services.ocr.engines as e;"
        " bad=[m for m in ('manga_ocr','paddleocr','paddle','torch') if m in sys.modules];"
        " assert not bad, f'import engines đã kéo theo {bad}';"
        " print('ok')"
    )
    r = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=str(APP_DIR.parent)
    )
    assert r.returncode == 0, r.stderr
    assert "ok" in r.stdout


def test_api_handler_khong_goi_thang_engine_ocr():
    routes = (APP_DIR / "api" / "v1" / "routes.py").read_text()
    assert "get_ocr_engine" not in routes
    assert "recognize(" not in routes
    assert "dispatch_ocr_job" in routes


def test_task_ocr_co_timeout_rieng_khac_detect():
    from app.workers.tasks import run_detect_job, run_ocr_job

    assert run_ocr_job.soft_time_limit is not None
    assert run_ocr_job.time_limit > run_ocr_job.soft_time_limit
    assert run_ocr_job.soft_time_limit != run_detect_job.soft_time_limit, (
        "OCR phải có timeout riêng, không dùng chung biến với detect"
    )
