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
#: E14 thêm `services/safearea`: nó dùng cv2 cho HÌNH HỌC ảnh (ngưỡng sáng, đường viền, khoảng
#: cách tới biên) — không nạp model, không gọi mạng. Mọi `import cv2` ở đó đều nằm TRONG hàm,
#: và test đo `sys.modules` vẫn chứng minh tiến trình API không nạp cv2 thật.
#: E15 thêm `services/orientation` với cùng lý do như `safearea`: chỉ dùng cv2 để đo HÌNH HỌC
#: (góc của đường bao dòng chữ), không nạp model, không gọi mạng; mọi `import cv2` nằm trong hàm.
ALLOWED_MODEL_DIRS = (
    "services/detect", "services/ocr", "services/inpaint", "services/safearea",
    "services/orientation", "workers",
)


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
        "typeset.run_refit_job",
        "ocr.run_region_reocr_job",
        "translate.run_region_retranslate_job",
        "export.run_export_job",
        "consistency.run_consistency_scan_job",
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


# ---------------- M7: sửa tay từng vùng ----------------


def test_whitelist_font_doc_duoc_ma_khong_keo_pillow():
    """API cần danh sách font để validate PATCH — nhưng vẫn không được nạp engine render."""
    import subprocess
    import sys

    code = (
        "import sys; from app.services.typeset.registry import FONT_REGISTRY;"
        " assert 'PIL' not in sys.modules, 'import registry đã kéo theo Pillow';"
        " assert 'Bangers' in FONT_REGISTRY;"
        " print('ok')"
    )
    r = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=str(APP_DIR.parent)
    )
    assert r.returncode == 0, r.stderr


def test_sua_tay_khong_render_dong_bo_trong_request():
    """PATCH region chỉ được ghi DB + xếp việc; mọi thứ nặng phải qua Celery."""
    routes = (APP_DIR / "api" / "v1" / "routes.py").read_text()
    than = routes[routes.index("async def patch_region") :]
    than = than[: than.index("@router.post")]
    for cam in ("FitToBoxTypesetter", "PagePreviewRenderer", "render_page_preview", "ImageDraw"):
        assert cam not in than, f"PATCH region không được gọi {cam} đồng bộ"
    assert "dispatch_refit_job" in than


def test_preview_khong_duoc_cache():
    """Đường dẫn preview cố định theo page ⇒ phải có header chống cache, không thì sửa xong
    người dùng vẫn thấy ảnh cũ (M7 constraint 8)."""
    routes = (APP_DIR / "api" / "v1" / "routes.py").read_text()
    than = routes[routes.index("async def get_typeset_preview") :]
    than = than[: than.index("@router.post")]
    assert "no-cache" in than


def test_auto_fit_khong_bao_gio_danh_dau_sua_tay():
    """Chỉ đường sửa tay mới được set edited_by_user=true — auto luôn false."""
    tasks = (APP_DIR / "workers" / "tasks.py").read_text()
    tu_dong = tasks[tasks.index("def _run_typeset") : tasks.index("def _run_refit")]
    assert "edited_by_user=False" in tu_dong
    assert "edited_by_user=True" not in tu_dong, "đường tự động không được đánh dấu sửa tay"

    sua_tay = tasks[tasks.index("def _run_refit") : tasks.index("def _run_region_reocr")]
    assert "edited_by_user=True" in sua_tay


def test_sau_task_co_sau_timeout_rieng():
    from app.workers.tasks import run_refit_job, run_typeset_job

    assert run_refit_job.soft_time_limit is not None
    assert run_refit_job.soft_time_limit != run_typeset_job.soft_time_limit


# ---------------- M8: xuất chapter ----------------


def test_duong_dan_export_doc_duoc_ma_khong_keo_pillow():
    """API cần biết chỗ đặt file để phục vụ tải về — vẫn không được nạp engine render."""
    import subprocess
    import sys

    code = (
        "import sys; from app.services.export.paths import export_relative_dir;"
        " assert 'PIL' not in sys.modules, 'import export.paths đã kéo theo Pillow';"
        " print('ok')"
    )
    r = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=str(APP_DIR.parent)
    )
    assert r.returncode == 0, r.stderr


def test_endpoint_tai_ve_chi_phuc_vu_file_khong_tu_render():
    routes = (APP_DIR / "api" / "v1" / "routes.py").read_text()
    than = routes[routes.index("async def download_export") :]
    than = than[: than.index("@router.get")]
    for cam in ("ChapterExporter", "PagePreviewRenderer", "zipfile", "ImageDraw", "run_export_job"):
        assert cam not in than, f"endpoint tải về không được đụng tới {cam}"


def test_khong_export_trang_chua_canh_chu():
    """Chỉ trang `typeset_done`/`ready_for_export` mới được xuất — xuất trang chưa canh chữ là
    giao cho người đọc ảnh trắng không có chữ."""
    from app.models.enums import PageStatus
    from app.workers.tasks import TRANG_XUAT_DUOC

    assert set(TRANG_XUAT_DUOC) == {PageStatus.typeset_done, PageStatus.ready_for_export}
    for xau in (PageStatus.queued, PageStatus.detected, PageStatus.ocr_done,
                PageStatus.inpainted, PageStatus.translated):
        assert xau not in TRANG_XUAT_DUOC


def test_export_dung_lai_renderer_cua_m6_khong_viet_lai():
    """Hai đường vẽ khác nhau ⇒ ảnh xuất ra lệch với ảnh xem thử. Phải dùng chung `draw()`."""
    chapter = (APP_DIR / "services" / "export" / "chapter.py").read_text()
    assert "self.renderer.draw(" in chapter
    for cam in ("ImageDraw", "multiline_text", "getlength", "FontResolver"):
        assert cam not in chapter, f"export tự vẽ lấy bằng {cam} thay vì dùng renderer của M6"


def test_bay_task_co_bay_timeout_rieng():
    from app.workers.tasks import run_export_job, run_refit_job, run_typeset_job

    assert run_export_job.soft_time_limit is not None
    assert run_export_job.soft_time_limit not in (
        run_typeset_job.soft_time_limit,
        run_refit_job.soft_time_limit,
    ), "export phải có timeout riêng, không copy của job khác"


def test_ten_file_export_khong_co_ky_tu_gay_loi_he_tep():
    from app.services.export.naming import ten_file_export

    ten = ten_file_export('Truyện /' + chr(92) + ':*?"<>| Hay', "cbz")
    for ky_tu in '/' + chr(92) + ':*?"<>|':
        assert ky_tu not in ten


# ---------------- M9: chạy cả mẻ ----------------


def test_khong_tao_apikeypool():
    """M5 đã ĐO và chứng minh: xoay key trong cùng project Gemini KHÔNG tăng quota.

    Thêm bảng xoay key chỉ tạo ảo giác là hệ thống đang xoay xở, trong khi hạn mức không đổi.
    Hết quota thì phải báo `blocked_quota` cho đúng sự thật.
    """
    for f in APP_DIR.rglob("*.py"):
        noi_dung = f.read_text()
        assert "APIKeyPool" not in noi_dung, f"{f.name} có APIKeyPool — xem REPORT_M5 §3"
        assert "round_robin_key" not in noi_dung


def test_dieu_phoi_me_khong_sao_chep_logic_pipeline():
    """Bộ điều phối chỉ xếp việc. Sao chép logic vào đây là hai đường xử lý sẽ lệch nhau."""
    orch = (APP_DIR / "services" / "batch" / "orchestrator.py").read_text()
    for cam in ("LamaInpainter", "FitToBoxTypesetter", "get_translator", "CTDDetector",
                "PagePreviewRenderer", "ImageDraw", "onnxruntime"):
        assert cam not in orch, f"orchestrator không được đụng tới {cam}"


def test_me_khong_tu_xuat_chapter():
    """Tự xuất sau khi dịch xong có thể phát hành bản còn tràn khung — mất quyền quyết định
    của người vận hành. Xuất là hành động có chủ ý ở M8."""
    for ten in ("orchestrator.py", "dispatch.py"):
        noi_dung = (APP_DIR / "services" / "batch" / ten).read_text()
        assert "run_export_job" not in noi_dung
        assert "ExportJob" not in noi_dung


def test_cong_nhip_khong_bao_gio_luu_api_key():
    gate = (APP_DIR / "services" / "batch" / "gate.py").read_text()
    # Khoá đi vào Redis và có thể lộ ra log -> phải băm.
    assert "hashlib" in gate and "sha256" in gate
    assert "gemini_api_key" not in gate.lower()


def test_khong_dung_rate_limit_cua_celery_lam_cong_toan_cuc():
    """`rate_limit` của Celery giới hạn theo TỪNG worker instance, không toàn hệ thống.

    Hai worker cùng đặt 10 lượt/phút thành 20 lượt/phút đập vào nhà cung cấp.
    """
    from app.workers.celery_app import celery_app

    assert celery_app.conf.get("task_default_rate_limit") in (None, "")
    tasks_src = (APP_DIR / "workers" / "tasks.py").read_text()
    assert "rate_limit=" not in tasks_src


def test_thong_diep_loi_cua_me_duoc_loc_khoa_bi_mat():
    orch = (APP_DIR / "services" / "batch" / "orchestrator.py").read_text()
    assert "_lam_sach" in orch
    assert "AIza" in orch, "phải có luật lọc chuỗi giống API key"


def _than_ham(ten: str):
    """Lấy đúng thân một hàm bằng AST — cắt theo số ký tự sẽ lọt/thiếu nhánh."""
    import ast

    cay = ast.parse((APP_DIR / "workers" / "tasks.py").read_text())
    for nut in ast.walk(cay):
        if isinstance(nut, ast.FunctionDef) and nut.name == ten:
            return nut
    raise AssertionError(f"không thấy hàm {ten}")


def _dem_bao_ve_me(ten: str) -> int:
    import ast

    return sum(
        1
        for n in ast.walk(_than_ham(ten))
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "bao_ket_thuc_buoc"
    )


def test_moi_task_pipeline_deu_bao_ket_qua_ve_me():
    """Phải báo về ở CẢ BA nhánh: xong, hết giờ, và lỗi.

    Lỗi thật đã gặp: `run_detect_job` chỉ báo về ở nhánh thành công. Trang hỏng lúc dò khung
    (bước ĐẦU TIÊN của mẻ, cũng là bước hay hỏng nhất) để lại mục ở `running` cho tới khi
    bộ thu hồi mồ côi chạm mốc 2400s — nhìn vào giao diện thì mẻ như đang chạy, thật ra đứng im.
    """
    for ten in ("run_detect_job", "run_ocr_job", "run_inpaint_job",
                "run_translate_job", "run_typeset_job"):
        assert _dem_bao_ve_me(ten) >= 3, (
            f"{ten} chỉ báo về mẻ ở {_dem_bao_ve_me(ten)} nhánh — phải đủ xong/hết giờ/lỗi"
        )


def test_viec_thao_tac_tay_khong_bao_ve_me():
    """Mẻ chỉ đẩy 5 bước pipeline. Việc sửa tay (canh lại chữ, đọc lại vùng, dịch lại vùng)
    không bao giờ là bước của mẻ, nên báo về chỉ có thể đánh hỏng NHẦM một mục đang chạy."""
    for ten in ("run_refit_job", "run_region_reocr_job", "run_region_retranslate_job"):
        assert _dem_bao_ve_me(ten) == 0, f"{ten} không được báo về mẻ"


def test_chi_mot_cho_dung_bo_dieu_phoi_me():
    """Lỗi thật do Run B tìm ra: worker dựng `BatchOrchestrator` bằng tay và QUÊN `retry_policy`.

    Mọi quyết định thử lại đều xảy ra ở worker, nên `BATCH_MAX_RETRIES` và `BATCH_RETRY_BACKOFF_*`
    trong `.env` khi đó **không có tác dụng gì** — đặt lùi dần 30s mà đo được 0,6s.
    Dựng ở hai nơi là cách chắc chắn để hai nơi lệch nhau, nên chỉ được dựng ở đúng một chỗ.
    """
    noi_dung = [
        (f, f.read_text()) for f in APP_DIR.rglob("*.py")
        if "BatchOrchestrator(" in f.read_text()
    ]
    ten = sorted(f.name for f, _ in noi_dung)
    assert ten == ["factory.py"], f"chỉ `factory.py` được dựng bộ điều phối, đang thấy {ten}"


def test_bo_dieu_phoi_doc_du_cau_hinh_thu_lai():
    from app.core.config import get_settings
    from app.services.batch.factory import tao_dieu_phoi

    s = get_settings()
    dp = tao_dieu_phoi(s)
    assert dp.retry_policy.max_retries == s.batch_max_retries
    assert dp.retry_policy.backoff_base_seconds == s.batch_retry_backoff_base_seconds
    assert dp.retry_policy.backoff_max_seconds == s.batch_retry_backoff_max_seconds
    assert dp.retry_policy.jitter == s.batch_retry_jitter
    assert dp.max_concurrent_pages == s.batch_max_concurrent_pages
    assert dp.stale_item_seconds == s.batch_stale_item_seconds


# ---------------- M10: khai báo mục đích & cảnh báo bản quyền ----------------

FE_DIR = Path(__file__).resolve().parents[2] / "frontend" / "src"


def test_giao_dien_khong_chon_ho_muc_dich_su_dung():
    """Chọn sẵn một mục đích là suy đoán hộ người dùng — đúng thứ khai báo này sinh ra để tránh.

    Trước M10 ô này mặc định `personal`, nghĩa là ai bấm nhanh cũng thành "đọc cá nhân" mà
    không hề tự khai.
    """
    src = (FE_DIR / "components" / "chapter" / "ChapterCreateForm.jsx").read_text()
    assert "useState('personal')" not in src, "vẫn đang chọn sẵn mục đích hộ người dùng"
    assert "useState('')" in src
    assert "!mucDich" in src, "chưa chọn mục đích thì không được cho tạo chapter"
    assert "lyDoChuaTaoDuoc" in src, "nút bị khoá phải nói rõ vì sao"


def test_nut_xuat_trong_hop_thoai_chi_sang_khi_da_tick():
    """Bằng chứng "đã xem cảnh báo" phải là một hành động có chủ ý, không phải bấm cho qua."""
    src = (FE_DIR / "components" / "ExportWarningModal.jsx").read_text()
    assert "disabled={!daTick}" in src


def test_hop_thoai_hien_du_ca_hai_loai_canh_bao():
    """Ẩn bớt cảnh báo để đỡ làm người dùng lo là cách giao đi một bản lỗi mà họ không biết."""
    src = (FE_DIR / "components" / "ExportWarningModal.jsx").read_text()
    assert "overflow_warning_count" in src and "needs_manual_count" in src


def _ma_khong_ke_chu_thich(f: Path) -> str:
    """Bỏ chú thích và chuỗi tài liệu, chỉ giữ phần MÃ.

    Cần thiết vì chính đoạn văn giải thích "không làm watermark" cũng chứa từ đó — soi lời văn
    thì guardrail sẽ đỏ vì đúng lý do ngược hẳn với ý nghĩa của nó.
    """
    import re
    import tokenize

    if f.suffix == ".py":
        with tokenize.open(f) as fh:
            return " ".join(
                tok.string for tok in tokenize.generate_tokens(fh.readline)
                if tok.type not in (tokenize.COMMENT, tokenize.STRING)
            ).lower()
    ma = re.sub(r"/\*.*?\*/", " ", f.read_text(), flags=re.S)   # /* … */
    ma = re.sub(r"(?m)^\s*//.*$", " ", ma)                       # // …
    return ma.lower()


def test_khong_lam_watermark_hay_drm():
    """Mini-spec cấm: nó không giúp gì cho việc tuân thủ bản quyền thật, chỉ làm hỏng ảnh của
    chính người dùng. Soi phần MÃ, không soi lời văn."""
    for goc in (APP_DIR, FE_DIR):
        for f in list(goc.rglob("*.py")) + list(goc.rglob("*.jsx")) + list(goc.rglob("*.js")):
            ma = _ma_khong_ke_chu_thich(f)
            for cam in ("watermark", "drm", "encrypt_export"):
                assert cam not in ma, f"{f.name} có mã {cam}"


def test_khong_co_duong_nao_tu_dong_chia_se_ban_xuat():
    """File xuất ra chỉ nằm trên máy người dùng — không có đường nào tự đăng công khai."""
    routes = (APP_DIR / "api" / "v1" / "routes.py").read_text().lower()
    for cam in ("public_url", "share_link", "make_public", "upload_to_cloud", "publish"):
        assert cam not in routes, f"routes.py có {cam}"


def test_nhat_ky_tuan_thu_chi_luu_so_lieu():
    """Không lưu nội dung export vào máy chủ — chỉ metadata."""
    from app.models import ExportComplianceLog

    cot = {c.name for c in ExportComplianceLog.__table__.columns}
    for cam in ("output_path", "content", "text", "image", "file"):
        assert not any(cam in c for c in cot), f"cột {cam} — đang lưu nội dung export"


# ---------------- E13: thuật ngữ & rà soát nhất quán ----------------


def test_bo_quet_khong_goi_mang():
    """Quét theo luật phải chạy offline hoàn toàn — không token, không phụ thuộc nhà cung cấp."""
    for ten in ("scanner.py", "matching.py", "glossary.py", "apply.py"):
        noi_dung = (APP_DIR / "services" / "consistency" / ten).read_text()
        for cam in ("urllib", "requests", "httpx", "socket", "generativelanguage",
                    "get_translator", "gemini"):
            assert cam not in noi_dung.lower(), f"{ten} có dấu vết gọi mạng: {cam}"


def test_quet_khong_bao_gio_sua_ban_dich_hay_anh():
    """Bộ quét chỉ TẠO VIỆC. Sửa gì ở đây là phá nguyên tắc 'người quyết định' của E13."""
    scanner = (APP_DIR / "services" / "consistency" / "scanner.py").read_text()
    for cam in ("translated_text =", "raw_text =", "wrapped_text =", "clean_image_path =",
                "TypesetResult(", "edited_by_user"):
        assert cam not in scanner, f"scanner không được đụng tới {cam}"


def test_khong_co_diem_chat_luong_0_100():
    """Máy không đo được bản dịch hay dở — chấm điểm là tạo cảm giác chính xác giả.

    Kiểm TÊN TRƯỜNG thật chứ không quét văn xuôi: bản đầu của test này bắt nhầm chính dòng
    chú thích giải thích luật ("**không** có điểm chất lượng 0–100").
    """
    from app.models import ConsistencyReviewTask
    from app.schemas.common import ConsistencySummary, ConsistencyTaskRead

    ten_truong = (
        set(ConsistencySummary.model_fields)
        | set(ConsistencyTaskRead.model_fields)
        | {c.name for c in ConsistencyReviewTask.__table__.columns}
    )
    xau = [t for t in ten_truong if "score" in t or "rating" in t or "grade" in t]
    assert not xau, f"E13 không được có trường chấm điểm: {xau}"


def test_chi_thuat_ngu_da_duyet_tham_gia_quet():
    scanner = (APP_DIR / "services" / "consistency" / "scanner.py").read_text()
    assert "list_approved" in scanner
    glossary = (APP_DIR / "services" / "consistency" / "glossary.py").read_text()
    than = glossary[glossary.index("def list_approved") :]
    assert "GlossaryStatus.approved" in than[:600]


def test_khong_co_nut_ap_dung_toan_chapter():
    """E13 v1 cố ý KHÔNG có thao tác hàng loạt — mỗi chỗ cần người quyết riêng."""
    routes = (APP_DIR / "api" / "v1" / "routes.py").read_text()
    for cam in ("apply_all", "accept_all", "bulk_apply", "apply-all"):
        assert cam not in routes, f"có thao tác hàng loạt: {cam}"


def test_client_khong_dat_duoc_trang_thai_hay_bang_chung():
    """Người dùng chỉ được chọn accept/reject — không được tự ghi bằng chứng hay trạng thái."""
    from app.schemas.common import TaskAcceptRequest, TaskRejectRequest

    assert set(TaskAcceptRequest.model_fields) == {"edited_text"}
    assert set(TaskRejectRequest.model_fields) == {"resolution"}


def test_goi_y_bang_llm_mac_dinh_tat():
    """Bật lên mới tốn token — không bao giờ tự tiêu tiền của người dùng."""
    from app.core.config import Settings

    assert Settings().e13_llm_suggestions_enabled is False


def test_muoi_task_co_muoi_timeout_rieng():
    from app.workers.tasks import run_consistency_scan_job, run_export_job

    assert run_consistency_scan_job.soft_time_limit is not None
    assert run_consistency_scan_job.soft_time_limit != run_export_job.soft_time_limit


# ---------- E14: vùng an toàn theo hình bong bóng ----------


def test_api_khong_import_bo_trich_hinh_e14():
    """Tầng HTTP chỉ được ĐỌC bản ghi vùng an toàn, không được tự chạy xử lý ảnh."""
    routes = (APP_DIR / "api" / "v1" / "routes.py").read_text()
    for cam in ("BubbleSafeAreaExtractor", "SafeAreaService", "o_dat_chu"):
        assert cam not in routes, f"routes.py gọi thẳng {cam} — xử lý ảnh phải ở worker"


def test_e14_khong_sua_bbox_cua_bo_nhan_dien():
    """Bbox của M2 là bằng chứng. E14 chỉ được THÊM vùng an toàn, không ghi đè lịch sử đó."""
    thu_muc = APP_DIR / "services" / "safearea"
    for py in thu_muc.rglob("*.py"):
        noi_dung = py.read_text()
        for cam in ("bbox_x =", "bbox_y =", "bbox_w =", "bbox_h ="):
            assert cam not in noi_dung, f"{py.name} đang gán vào bbox của TextRegion"


def test_e14_khong_goi_ctd_text_mask_la_bubble_mask():
    """Mask của CTD là mask CHỮ. Gọi nó là 'mask bong bóng' là nói sai về bằng chứng."""
    thu_muc = APP_DIR / "services" / "safearea"
    for py in thu_muc.rglob("*.py"):
        noi_dung = py.read_text().lower()
        assert "ctd" not in noi_dung, f"{py.name} nhắc tới CTD — E14 không dùng output detector"


def test_e14_ready_phai_co_hinh_that():
    """`ready` là lời khẳng định mạnh nhất về hình bong bóng — không được rỗng ruột."""
    import pytest

    from app.models.enums import SafeAreaGeometryType, SafeAreaSource, SafeAreaStatus
    from app.services.safearea.decision import ReasonCode, SafeAreaDecision

    with pytest.raises(ValueError):
        SafeAreaDecision(
            source=SafeAreaSource.shape_derived, status=SafeAreaStatus.ready,
            geometry_type=SafeAreaGeometryType.polygon, geometry={"polygon": []},
            roi=(0, 0, 10, 10), reason_codes=[ReasonCode.SHAPE_CANDIDATE_FOUND],
            safe_area_pixels=100,
        )
    with pytest.raises(ValueError):
        SafeAreaDecision(
            source=SafeAreaSource.fallback_rectangle, status=SafeAreaStatus.ready,
            geometry_type=SafeAreaGeometryType.polygon,
            geometry={"polygon": [[0, 0], [1, 0], [1, 1]]},
            roi=(0, 0, 10, 10), reason_codes=[ReasonCode.SHAPE_CANDIDATE_FOUND],
            safe_area_pixels=100,
        )


def test_e14_du_phong_luon_co_hinh_hoc():
    """Dự phòng phải LƯU hẳn khung chữ nhật — 'không có hình' đọc nhầm thành 'vừa khít'."""
    from app.core.config import get_settings
    from app.services.interfaces import BBox
    from app.services.safearea.config import SafeAreaConfig
    from app.services.safearea.extractor import khung_du_phong

    cfg = SafeAreaConfig.from_settings(get_settings())
    qd = khung_du_phong(BBox(x=10, y=10, w=200, h=100), cfg, [])
    assert qd.geometry["rect"]["w"] > 0 and qd.geometry["rect"]["h"] > 0
    assert "fallback_no_reliable_shape" in qd.reason_codes


def test_e14_ma_ly_do_nam_trong_danh_sach_dong():
    """Mã lý do được giao diện dịch ra tiếng Việt, nên không được đẻ mã tuỳ hứng."""
    import pytest

    from app.models.enums import SafeAreaGeometryType, SafeAreaSource, SafeAreaStatus
    from app.services.safearea.decision import SafeAreaDecision

    with pytest.raises(ValueError):
        SafeAreaDecision(
            source=SafeAreaSource.fallback_rectangle, status=SafeAreaStatus.fallback_rectangle,
            geometry_type=SafeAreaGeometryType.rect,
            geometry={"rect": {"x": 0, "y": 0, "w": 5, "h": 5}},
            roi=(0, 0, 10, 10), reason_codes=["ly_do_tu_bia"],
        )


# ---------- E15: hướng chữ ----------


def test_api_khong_import_bo_phan_tich_huong_chu():
    routes = (APP_DIR / "api" / "v1" / "routes.py").read_text()
    for cam in ("RegionOrientationAnalyzer", "OrientationService", "chuan_hoa_goc"):
        assert cam not in routes, f"routes.py gọi thẳng {cam} — xử lý ảnh phải ở worker"


def test_e15_khong_sua_chu_ocr_hay_ban_dich():
    """Hướng chữ chỉ để CĂN CHỮ. Đảo ký tự/đảo dòng theo hướng là phá bằng chứng của M3/M5."""
    thu_muc = APP_DIR / "services" / "orientation"
    for py in thu_muc.rglob("*.py"):
        noi_dung = py.read_text()
        for cam in ("raw_text =", "translated_text =", "[::-1]", "reversed("):
            assert cam not in noi_dung, f"{py.name} đang sửa/đảo chữ — E15 không được đụng vào"


def test_e15_khong_dung_goc_tho_cua_minAreaRect():
    """Góc thô không phân biệt được 0° với 90° (đo thật) — mọi chỗ đọc góc phải qua bộ chuẩn hoá."""
    thu_muc = APP_DIR / "services" / "orientation"
    for py in thu_muc.rglob("*.py"):
        if py.name == "angle.py":
            continue
        noi_dung = py.read_text()
        if "minAreaRect" in noi_dung:
            assert "chuan_hoa_goc" in noi_dung, (
                f"{py.name} đọc minAreaRect mà không chuẩn hoá góc"
            )


def test_e15_ti_le_khung_khong_bao_gio_tu_quyet_huong():
    """Chữ 'PHEW!' viết thưa theo chiều dọc vẫn là chữ ngang cách điệu."""
    from app.services.orientation.analyzer import OrientationConfig, RegionOrientationAnalyzer
    from app.models.enums import TextOrientation

    bd = RegionOrientationAnalyzer(OrientationConfig())
    for w, h in ((20, 400), (400, 20), (10, 10)):
        d = bd.analyze(bbox_w=w, bbox_h=h, line_polygons=None)
        assert d.orientation is TextOrientation.unknown


def test_e15_khong_tu_bo_qua_vung_nao():
    """SFX/chữ dọc/chữ nghiêng đều phải được GIỮ và đưa người xem, không bao giờ tự loại."""
    thu_muc = APP_DIR / "services" / "orientation"
    for py in thu_muc.rglob("*.py"):
        noi_dung = py.read_text()
        assert "reviewed_skip" not in noi_dung, f"{py.name} tự đánh dấu bỏ qua"


def test_e15_chua_dung_duoc_chu_doc_thi_khong_duoc_bao_ready():
    from app.services.orientation.analyzer import OrientationConfig, RegionOrientationAnalyzer
    from app.models.enums import OrientationStatus, TextOrientation
    import numpy as np
    import pytest as _pt

    cv2 = _pt.importorskip("cv2")
    doc = [cv2.boxPoints(((250.0, 250.0), (240.0, 40.0), 90.0)).tolist() for _ in range(3)]
    d = RegionOrientationAnalyzer(
        OrientationConfig(vertical_render_enabled=False)
    ).analyze(bbox_w=60, bbox_h=300, line_polygons=doc)
    assert d.orientation is TextOrientation.vertical_ttb
    assert d.status is not OrientationStatus.ready
