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
#: Chỉ các thư mục này được phép chạm runtime model (M2: detect, M3: ocr, M4: inpaint).
ALLOWED_MODEL_DIRS = ("services/detect", "services/ocr", "services/inpaint", "workers")


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
    assert user_tasks == {
        "detect.run_detect_job",
        "ocr.run_ocr_job",
        "inpaint.run_inpaint_job",
        "translate.run_translate_job",
        "typeset.run_typeset_job",
    }, user_tasks


def test_task_detect_co_timeout_khong_de_worker_treo():
    from app.workers.tasks import run_detect_job

    assert run_detect_job.soft_time_limit is not None
    assert run_detect_job.time_limit > run_detect_job.soft_time_limit


# ---------------- M3: engine OCR cũng chỉ được sống trong worker ----------------

OCR_LIBS = ("manga_ocr", "paddleocr", "paddle", "torch", "transformers")
#: Thêm services/ocr vào danh sách thư mục được phép chạm runtime model.
ALLOWED_OCR_DIRS = ("services/ocr", "services/detect", "services/inpaint", "workers")


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


# ---------------- M4: model inpaint cũng chỉ sống trong worker ----------------


def test_api_handler_khong_goi_thang_inpainter():
    routes = (APP_DIR / "api" / "v1" / "routes.py").read_text()
    assert "LamaInpainter" not in routes
    assert "get_inpainter" not in routes
    assert "dispatch_inpaint_job" in routes


def test_import_app_khong_keo_theo_model_inpaint():
    import subprocess
    import sys

    code = (
        "import sys; import app.main;"
        " bad=[m for m in ('onnxruntime','torch','cv2') if m in sys.modules];"
        " assert not bad, f'API đã nạp {bad}';"
        " print('ok')"
    )
    r = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=str(APP_DIR.parent)
    )
    assert r.returncode == 0, r.stderr
    assert "ok" in r.stdout


def test_module_inpaint_import_tre_khong_nap_onnx():
    import subprocess
    import sys

    code = (
        "import sys; import app.services.inpaint.lama as l;"
        " assert 'onnxruntime' not in sys.modules, 'import lama đã kéo theo onnxruntime';"
        " print('ok')"
    )
    r = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=str(APP_DIR.parent)
    )
    assert r.returncode == 0, r.stderr
    assert "ok" in r.stdout


def test_ba_task_co_ba_timeout_rieng():
    from app.workers.tasks import run_detect_job, run_inpaint_job, run_ocr_job

    limits = {
        "detect": run_detect_job.soft_time_limit,
        "ocr": run_ocr_job.soft_time_limit,
        "inpaint": run_inpaint_job.soft_time_limit,
    }
    assert all(v is not None for v in limits.values()), limits
    assert run_inpaint_job.time_limit > run_inpaint_job.soft_time_limit
    # inpaint phải có biến timeout RIÊNG, không tái dùng của detect
    assert limits["inpaint"] != limits["detect"], limits


def test_khong_lang_le_fallback_opencv_khi_lama_loi():
    """Constraint 10 của M4: fallback phải bật tường minh, mặc định TẮT."""
    from app.core.config import Settings

    assert Settings().inpaint_allow_opencv_fallback is False
    lama = (APP_DIR / "services" / "inpaint" / "lama.py").read_text()
    # cấm DÙNG cv2, không cấm nhắc tới trong ghi chú
    assert "import cv2" not in lama, "LamaInpainter không được import cv2"
    assert "cv2.inpaint(" not in lama, "LamaInpainter không được tự lùi về cv2.inpaint"


# ---------------- M5: API key không được lọt vào git ----------------

REPO_ROOT = APP_DIR.parent.parent

#: Mẫu key hay gặp: Google/Gemini (AIza..., AQ....), OpenAI (sk-...), Anthropic (sk-ant-...).
KEY_PATTERNS = (
    r"AIza[0-9A-Za-z_\-]{30,}",
    r"AQ\.[0-9A-Za-z_\-]{30,}",
    r"sk-[A-Za-z0-9_\-]{20,}",
    r"sk-ant-[A-Za-z0-9_\-]{20,}",
)


def _tracked_files() -> list[str]:
    import subprocess

    out = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, cwd=str(REPO_ROOT)
    )
    return [f for f in out.stdout.splitlines() if f]


def test_khong_co_api_key_nao_bi_commit_vao_git():
    """GUARDRAIL M5: key chỉ được sống trong .env (đã gitignore), tuyệt đối không vào git."""
    import re

    hits = []
    for rel in _tracked_files():
        path = REPO_ROOT / rel
        if not path.is_file() or path.suffix in (".png", ".jpg", ".jpeg", ".onnx"):
            continue
        try:
            content = path.read_text(errors="ignore")
        except Exception:  # noqa: BLE001
            continue
        for pattern in KEY_PATTERNS:
            for match in re.finditer(pattern, content):
                hits.append(f"{rel}: {match.group(0)[:8]}…")
    assert hits == [], f"Có API key bị commit vào git: {hits}"


def test_file_env_that_khong_duoc_track():
    assert ".env" not in _tracked_files(), ".env chứa key — không được commit"


def test_key_khong_bi_ghi_vao_db_hay_tra_ra_api():
    """Key chỉ đọc từ settings; không có cột nào trong DB và không endpoint nào trả ra."""
    routes = (APP_DIR / "api" / "v1" / "routes.py").read_text()
    models = (APP_DIR / "models" / "__init__.py").read_text()
    assert "gemini_api_key" not in routes.lower()
    assert "api_key" not in models.lower(), "Không lưu API key trong bảng DB ở M5"


def test_nam_task_co_nam_timeout_rieng():
    from app.workers.tasks import (
        run_detect_job,
        run_inpaint_job,
        run_ocr_job,
        run_translate_job,
        run_typeset_job,
    )

    limits = {
        "detect": run_detect_job.soft_time_limit,
        "ocr": run_ocr_job.soft_time_limit,
        "inpaint": run_inpaint_job.soft_time_limit,
        "translate": run_translate_job.soft_time_limit,
        "typeset": run_typeset_job.soft_time_limit,
    }
    assert all(v is not None for v in limits.values()), limits
    assert limits["translate"] != limits["detect"], limits
    assert limits["typeset"] != limits["translate"], limits


def test_mac_dinh_khong_tu_tieu_token_cua_nguoi_dung():
    """Auto-chain sau inpaint phải dùng engine MIỄN PHÍ trừ khi người dùng chọn khác."""
    from app.core.config import Settings

    assert Settings().translate_default_engine == "google_fast"


def test_mac_dinh_tat_thinking_de_khong_dot_token():
    """Đo thật: không tắt thinking thì 938 token suy nghĩ cho 6 dòng (đắt gấp ~7,7 lần)."""
    from app.core.config import Settings

    assert Settings().llm_thinking_budget == 0
    assert "2.5" not in Settings().llm_model_name, "gemini-2.5-* đã bị chặn với key mới (404)"


# ---------------- M6: canh chữ vào bubble ----------------


def test_api_khong_nap_engine_render_cua_m6():
    """Tiến trình API phải KHÔNG nạp Pillow/engine render — việc nặng thuộc worker."""
    import subprocess
    import sys

    code = (
        "import sys; import app.main;"
        " bad=[m for m in ('PIL','onnxruntime','torch','cv2') if m in sys.modules];"
        " assert not bad, f'API đã nạp {bad}';"
        " print('ok')"
    )
    r = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=str(APP_DIR.parent)
    )
    assert r.returncode == 0, r.stderr


def test_package_typeset_khong_keo_theo_pillow():
    """`app.services.typeset` phải nạp được mà không kéo Pillow — API dùng nó để lấy đường dẫn."""
    import subprocess
    import sys

    code = (
        "import sys; import app.services.typeset.paths as p;"
        " assert 'PIL' not in sys.modules, 'import typeset.paths đã kéo theo Pillow';"
        " assert p.preview_relative_path;"
        " print('ok')"
    )
    r = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=str(APP_DIR.parent)
    )
    assert r.returncode == 0, r.stderr


def test_endpoint_preview_chi_phuc_vu_file_khong_tu_render():
    """Endpoint preview không được gọi renderer — nếu chưa có file thì trả 404."""
    routes = (APP_DIR / "api" / "v1" / "routes.py").read_text()
    than_ham = routes[routes.index("async def get_typeset_preview") :]
    than_ham = than_ham[: than_ham.index("@router.post")]
    for cam in ("PagePreviewRenderer", "FitToBoxTypesetter", "ImageDraw", "render("):
        assert cam not in than_ham, f"endpoint preview không được đụng tới {cam}"
    assert "404" in than_ham


def test_khong_co_hai_thuat_toan_fit_song_song():
    """Spec §6: chỉ giữ MỘT thuật toán trong production (đã chọn giảm 1px, có bằng chứng)."""
    fitter = (APP_DIR / "services" / "typeset" / "fitter.py").read_text()
    than = fitter[fitter.index("def fit(") :]
    assert "//" not in than.split('"""')[2], "còn dấu vết tìm kiếm nhị phân trong fit()"


def test_khong_co_font_path_hard_code():
    """Font phải qua FontResolver + FONT_DIR, không nhét thẳng đường dẫn vào code."""
    for name in ("fitter.py", "preview.py", "layout.py"):
        noi_dung = (APP_DIR / "services" / "typeset" / name).read_text()
        assert ".ttf" not in noi_dung, f"{name} hard-code đường dẫn font"


def test_khong_bao_gio_co_chu_nho_hon_min():
    from app.core.config import Settings

    s = Settings()
    assert s.typeset_min_font_size >= 1
    assert s.typeset_min_font_size <= s.typeset_max_font_size
    assert s.allow_font_fallback is False, "mặc định KHÔNG được âm thầm đổi font"
