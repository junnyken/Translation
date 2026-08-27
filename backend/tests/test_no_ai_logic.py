"""Guardrail tự động — M1 không được import/chạy model AI thật (§8)."""
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


def test_khong_co_import_model_ai_trong_pham_vi_m1():
    hits = []
    for py in APP_DIR.rglob("*.py"):
        for lineno, line in enumerate(py.read_text().splitlines(), 1):
            stripped = line.strip()
            if not (stripped.startswith("import ") or stripped.startswith("from ")):
                continue
            for mod in FORBIDDEN:
                if f"import {mod}" in stripped or stripped.startswith(f"from {mod}"):
                    hits.append(f"{py}:{lineno}: {stripped}")
    assert hits == [], f"M1 không được import model AI: {hits}"


def test_celery_chua_dang_ky_task_that():
    from app.workers.celery_app import celery_app

    user_tasks = [t for t in celery_app.tasks if not t.startswith("celery.")]
    assert user_tasks == [], f"M1 chưa được có task Celery thật: {user_tasks}"
