"""Entrypoint FastAPI của Translation (Phase MTE)."""
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
    """Kiểm tra sống — nền tảng hosting dùng để biết container đã sẵn sàng chưa."""
    return {"status": "ok"}


app.include_router(v1_router)
