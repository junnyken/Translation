"""Entrypoint FastAPI của Translation (Phase MTE)."""
from fastapi import FastAPI

from app.api.v1.routes import router as v1_router

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
app.include_router(v1_router)
