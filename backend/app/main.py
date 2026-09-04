"""Entrypoint FastAPI của Translation (Phase MTE)."""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fastapi import Depends

from app.api.v1.routes import router as v1_router
from app.core.bao_ve import canh_bao_neu_khong_khoa
from app.core.quyen import nguoi_dung_hien_tai
from app.api.v1.xac_thuc_routes import router as xac_thuc_router
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
        # `X-API-Key` phải nằm trong danh sách này, nếu không trình duyệt sẽ chặn ngay ở
        # preflight và giao diện không bao giờ gửi được khoá đi.
        # `Authorization` cho mã phiên (slice B), `X-API-Key` cho khoá chung lúc đăng ký (slice A).
        allow_headers=["Content-Type", "X-API-Key", "Authorization"],
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
    # HAI con số của HAI tiến trình, dán nhãn tách bạch.
    #
    # `rss_api_mb` là bộ nhớ của tiến trình đang phục vụ HTTP này. `worker.rss_mb` là của tiến
    # trình worker — thứ thật sự bị OOM killer giết. Trước P3m chỉ có một trường `rss_mb` (của
    # API) và ai nhìn cũng tưởng đó là số của worker: đúng về kỹ thuật, sai về câu hỏi.
    #
    # Giữ luôn `rss_mb` cũ trỏ vào số của API để không phá thứ đang đọc nó (API.md §healthz).
    ket_qua["rss_api_mb"] = ket_qua["rss_mb"] = rss_mb()
    try:
        moc = json.loads(_Path(os.environ.get("WORKER_RSS_FILE", "/tmp/rss-worker.json")).read_text())
        # Kèm `luc` để bên đọc tự đánh giá số này CŨ tới đâu — worker chết thì tệp đứng lại,
        # và một con số đứng yên trông y hệt một con số bình thường nếu không có mốc thời gian.
        ket_qua["worker"] = {**ket_qua["worker"], "rss_mb": moc.get("rss_mb"),
                             "rss_moc": moc.get("moc"), "rss_luc": moc.get("luc")}
    except Exception:
        # Worker chưa chạy bước nặng nào thì chưa có tệp — không phải lỗi, và KHÔNG bịa số 0.
        ket_qua["worker"] = {**ket_qua["worker"], "rss_mb": None}
    return ket_qua


# Router tài khoản KHÔNG đòi đăng nhập (đăng nhập thì lấy đâu ra phiên mà gửi). Riêng
# `/auth/register` tự đòi khoá chung bên trong, để người lạ không tự tạo tài khoản.
app.include_router(xac_thuc_router, prefix="/api/v1")

# Gắn cổng ĐĂNG NHẬP ở tầng ROUTER, không gắn từng endpoint: 65 đường dẫn thì kiểu gì cũng
# quên một cái, và cái bị quên sẽ là cái không ai ngờ tới.
#
# Đây là chỗ slice B thay slice A: trước là một khoá chung (ai cầm khoá làm được mọi thứ với
# chapter của mọi người), giờ là tài khoản riêng + chapter có chủ. Khoá chung KHÔNG còn mở
# được dữ liệu nữa — nó chỉ còn gác cổng đăng ký.
app.include_router(v1_router, dependencies=[Depends(nguoi_dung_hien_tai)])

canh_bao_neu_khong_khoa()
