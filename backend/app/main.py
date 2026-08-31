"""Entrypoint FastAPI của Translation (Phase MTE)."""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routes import router as v1_router
from app.core.config import get_settings

app = FastAPI(
    title="Translation — Manga Translation Extension (MTE)",
    version="0.1.0-M1",
    description=(
        "Pipeline dịch manga EN/JP/CN → VI. M1: data model + API contract + interface engine. "
        "Chưa có logic AI thật (detect/OCR/inpaint/translate/typeset thuộc M2–M6)."
    ),
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# Chạy thật thì giao diện (M7/M8) và API nằm ở HAI tên miền khác nhau, nên trình duyệt coi là
# gọi chéo nguồn và sẽ chặn nếu thiếu CORS. Mặc định để RỖNG = không cho phép nguồn nào —
# phải khai báo tường minh trong `.env`, không mở sẵn `*` cho cả internet.
_settings = get_settings()
if _settings.cors_allow_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_settings.cors_allow_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type"],
    )


@app.get("/", tags=["ops"])
async def root() -> dict:
    """Trang gốc. Nền tảng hosting thăm dò `/` để biết ứng dụng đã sẵn sàng chưa —
    thiếu route này thì nó nhận 404 và coi như deploy hỏng, dù ứng dụng chạy bình thường."""
    return {
        "service": "Translation — Manga Translation Extension (MTE)",
        "status": "ok",
        "docs": "/docs",
        "api": "/api/v1",
    }


@app.get("/healthz", tags=["ops"])
async def healthz() -> dict:
    """Kiểm tra sống — nền tảng hosting dùng để biết container đã sẵn sàng chưa.

    Khi API và worker chạy chung một container (`ROLE=all` lúc deploy), endpoint này còn báo
    **tình trạng worker**: worker chết mà API vẫn 200 là loại sự cố tệ nhất — pipeline đứng im
    mà nhìn từ ngoài vẫn thấy "bình thường". Ở đây nói thẳng ra.
    """
    import json
    from pathlib import Path as _Path

    from app.workers.bo_nho import rss_mb

    ket_qua: dict = {"status": "ok"}
    duong_dan = _Path(os.environ.get("WORKER_STATE_FILE", "/tmp/trang-thai-worker.json"))
    try:
        ket_qua["worker"] = json.loads(duong_dan.read_text())
    except Exception:
        # Chạy ở máy nhà thì worker là container riêng, không có file này — không phải lỗi.
        ket_qua["worker"] = {"trang_thai": "khong_ro"}
    # RSS của tiến trình API. Trước P3h endpoint này không có MỘT chỉ số bộ nhớ nào, nên lần
    # worker bị OOM killer giết (exit 137) không ai thấy gì tới lúc nó chết. `null` nghĩa là
    # không đo được — khác với 0, và không được gộp hai thứ đó làm một.
    ket_qua["rss_mb"] = rss_mb()
    return ket_qua


app.include_router(v1_router)
