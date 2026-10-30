"""Cổng Developer REST API (`/api/v1/developer/*`) dành cho Tool & Website của Khách Hàng đấu nối kéo dữ liệu về.

Hỗ trợ xác thực bằng:
- Header `X-Customer-Api-Key: tr_live_...`
- Header `Authorization: Bearer tr_live_...` (hoặc mã phiên đăng nhập)
- Header `X-API-Key: tr_live_...`
- Query param `?api_key=tr_live_...` (tiện cho tải ảnh trực tiếp qua URL)

Mọi lượt dịch qua Developer API đều trừ trực tiếp vào hạn mức miễn phí trong ngày + quỹ lượt mua tích luỹ (`so_luot_mua_them`) của tài khoản sở hữu API Key đó, đồng thời tận dụng Bảng Cache Cộng Đồng (`SHA-256` + `target_lang`).
"""
from __future__ import annotations

import asyncio
import base64
import urllib.request
import uuid
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.api.v1.routes import (
    _chapter_doc_nhanh,
    _get_page_or_404,
    _kiem_engine,
    doc_truyen_lay_trang,
)
from app.core.config import Settings, get_settings
from app.core.cong_han_muc import danh_tinh_han_muc, giu_cho_moi_chot
from app.core.danh_tinh_khach import Chot, DanhTinhHanMuc, bam, ip_cua
from app.core.db import get_session
from app.core.quyen import NguoiGoi, ma_phien_tu_header
from app.services.han_muc_dang_nhap import da_sai_bao_nhieu, ghi_nhan_dang_nhap_sai
from app.models import (
    Job,
    NguoiDung,
    OCRResult,
    Page,
    Project,
    TextRegion,
    TranslationResult,
    TypesetResult,
)
from app.models.enums import (
    ChePipeline,
    JobStatus,
    JobType,
    LoaiChuThe,
    PageStatus,
    SourceLang,
    TargetLang,
    TranslationEngine,
)
from app.services import tai_khoan
from app.services.bo_nho_anh_dich import (
    ghi_nhan_trang_anh,
    thu_sao_chep_tu_cache,
    tinh_bam_anh,
)
from app.services.dispatch import dispatch_detect_job
from app.services.han_muc import bay_gio, han_muc_cho, moc_reset_ke_tiep, ngay_han_muc
from app.services.so_cai_han_muc import da_dung_bat_dong_bo
from app.services.storage import (
    UnsupportedImage,
    get_storage,
    sniff_image,
    thu_nho_anh_trang,
)
from app.services.typeset.paths import preview_relative_path

router = APIRouter(prefix="/api/v1/developer", tags=["developer-api"])


def _khoa_bi_mat_chu_ky_anh(settings: Settings) -> bytes:
    """Khoá HMAC riêng để ký URL tải ảnh từng trang (`?sig=...&exp=...`), tránh lộ `tr_live_...`."""
    from app.core.config import lay_khoa_bi_mat_noi_bo

    return lay_khoa_bi_mat_noi_bo(settings, nhan="developer-image-url-v1")


def _ky_url_anh_developer(
    page_id: uuid.UUID, nguoi_id: uuid.UUID, exp: int, settings: Settings | None = None
) -> str:
    import hashlib
    import hmac

    st = settings or get_settings()
    msg = f"{page_id}:{nguoi_id}:{int(exp)}".encode("utf-8")
    return hmac.new(_khoa_bi_mat_chu_ky_anh(st), msg, hashlib.sha256).hexdigest()[:32]


async def _xac_minh_chu_ky_anh_developer(
    session: AsyncSession,
    page_id: uuid.UUID,
    sig: str | None,
    exp: int | None,
    settings: Settings,
) -> NguoiDung | None:
    """Kiểm tra chữ ký `?sig=...&exp=...` gắn riêng cho đúng `page_id` đó."""
    import hmac
    import time

    if not sig or exp is None:
        return None
    if int(exp) < int(time.time()):
        return None
    page = await session.get(Page, page_id)
    if page is None:
        return None
    project = await session.get(Project, page.project_id)
    if project is None or project.chu_so_huu_id is None:
        return None
    nguoi = await session.get(NguoiDung, project.chu_so_huu_id)
    if nguoi is None or not nguoi.dang_hoat_dong:
        return None
    ky_vong = _ky_url_anh_developer(page_id, nguoi.id, int(exp), settings)
    if not hmac.compare_digest(sig.strip(), ky_vong):
        return None
    return nguoi


async def _xac_thuc_developer(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_customer_api_key: str | None = Header(default=None, alias="X-Customer-Api-Key"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    api_key_query: str | None = Query(default=None, alias="api_key"),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> tuple[NguoiDung, str]:
    """Xác thực API Key của khách hàng từ Header hoặc Query param, kèm chống dò khoá theo IP."""
    tran = settings.so_lan_dang_nhap_sai_moi_ip_mot_ngay
    ip = ip_cua(request, settings) if tran > 0 else None
    ip_bam = bam(ip, settings) if ip is not None else None
    ngay = ngay_han_muc() if ip_bam is not None else None

    if ip_bam is not None and ngay is not None:
        if await da_sai_bao_nhieu(session, ip_bam, ngay) >= tran:
            reset = moc_reset_ke_tiep()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(max(0, int((reset - bay_gio()).total_seconds())))},
                detail={
                    "error": "too_many_invalid_api_key_attempts",
                    "message": "Quá nhiều lần gửi sai Developer API Key từ địa chỉ mạng này trong hôm nay. Vui lòng thử lại sau.",
                },
            )

    ma = ma_phien_tu_header(authorization, x_customer_api_key, x_api_key)
    if not ma and api_key_query and api_key_query.strip():
        ma = api_key_query.strip()
    nguoi = await tai_khoan.lay_theo_ma_phien(session, ma) if ma else None
    if nguoi is None:
        if ma and ip_bam is not None and ngay is not None:
            await ghi_nhan_dang_nhap_sai(session, ip_da_bam=ip_bam, ngay=ngay, tran=tran)
            await session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "invalid_or_missing_api_key",
                "message": "Thiếu hoặc sai Developer API Key. Hãy tạo key tại mục Tài khoản trên Website (tr_live_...) và gửi qua header 'X-Customer-Api-Key' hoặc 'Authorization: Bearer tr_live_...'.",
            },
        )
    return nguoi, ma or ""


def _danh_tinh_tu_nguoi_dung(nguoi: NguoiDung) -> DanhTinhHanMuc:
    tran_ngay = (
        int(nguoi.tran_hang_ngay_rieng)
        if getattr(nguoi, "tran_hang_ngay_rieng", None) is not None
        else han_muc_cho(True)
    )
    luot_mua = max(0, int(getattr(nguoi, "so_luot_mua_them", 0) or 0))
    return DanhTinhHanMuc(
        co_tai_khoan=True,
        chot=(Chot(LoaiChuThe.nguoi_dung, str(nguoi.id), tran_ngay),),
        nguoi_goi=NguoiGoi(nguoi=nguoi),
        so_luot_mua_them=luot_mua,
    )


async def _thong_tin_quota(session: AsyncSession, nguoi: NguoiDung) -> dict[str, Any]:
    await session.refresh(nguoi)
    danh_tinh = _danh_tinh_tu_nguoi_dung(nguoi)
    chot = danh_tinh.chot[0]
    da_dung = await da_dung_bat_dong_bo(session, chot.loai, chot.chu_the, ngay_han_muc())
    con_ngay = max(0, chot.tran - da_dung)
    luot_mua = max(0, int(nguoi.so_luot_mua_them or 0))
    reset = moc_reset_ke_tiep()
    return {
        "daily_limit": chot.tran,
        "daily_used": da_dung,
        "daily_remaining": con_ngay,
        "purchased_remaining": luot_mua,
        "total_usable_pages": con_ngay + luot_mua,
        "reset_at": reset.isoformat(),
    }


class LoiTaiAnh(ValueError):
    """Lỗi tải ảnh có câu báo AN TOÀN để trả cho người gọi (không kèm chi tiết mạng nội bộ)."""


def _kiem_tra_url_an_toan_ssrf(url: str) -> str:
    """Chặn SSRF: chỉ cho tải ảnh từ địa chỉ IP công cộng (`is_global`) và trả về IP đã kiểm để ghim kết nối.

    `is_global` thay cho danh sách `is_private/is_loopback/...`: danh sách cũ để lọt dải CGNAT
    100.64.0.0/10 và NAT64 64:ff9b::/96 — cả hai đều có thể trỏ vào mạng nội bộ của nền tảng.
    """
    import ipaddress
    import socket
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise LoiTaiAnh("image_url phải bắt đầu bằng http:// hoặc https://")
    host = (parsed.hostname or "").strip().lower()
    if not host or host in ("localhost", "metadata.google.internal"):
        raise LoiTaiAnh("URL ảnh không hợp lệ hoặc trỏ tới địa chỉ nội bộ bị cấm.")
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as exc:
        raise LoiTaiAnh(f"Không phân giải được tên miền ảnh: {host}") from exc
    ip_hop_le: list[str] = []
    for info in infos:
        raw_ip = info[4][0].split("%")[0]
        ip_obj = ipaddress.ip_address(raw_ip)
        if getattr(ip_obj, "ipv4_mapped", None):
            ip_obj = ip_obj.ipv4_mapped
        if not ip_obj.is_global or ip_obj.is_multicast:
            raise LoiTaiAnh("Từ chối kết nối tới địa chỉ IP nội bộ / đặc quyền.")
        ip_hop_le.append(str(ip_obj))
    if not ip_hop_le:
        raise LoiTaiAnh(f"Không tìm thấy địa chỉ IP công cộng hợp lệ cho: {host}")
    return ip_hop_le[0]


class _KhongTuChuyenHuong(urllib.request.HTTPRedirectHandler):
    """Tắt tự đi theo 3xx: mỗi bước chuyển hướng phải qua lại `_kiem_tra_url_an_toan_ssrf`.
    Để urllib tự đi theo là kiểm host đầu rồi bị 302 dắt vào 169.254.169.254 hay `redis:6379`."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


def _tao_opener_ghim_ip_chong_dns_rebinding(ip_da_kiem: str) -> urllib.request.OpenerDirector:
    """Tạo OpenerDirector ghim chặt kết nối TCP vào `ip_da_kiem` đã qua kiểm tra SSRF,
    nhưng vẫn giữ nguyên `Host` header và TLS SNI `server_hostname` của tên miền gốc."""
    import http.client
    import socket
    import ssl

    class _PinnedHTTPConnection(http.client.HTTPConnection):
        def connect(self):
            self.sock = socket.create_connection((ip_da_kiem, self.port), self.timeout)

    class _PinnedHTTPSConnection(http.client.HTTPSConnection):
        def connect(self):
            raw_sock = socket.create_connection((ip_da_kiem, self.port), self.timeout)
            ctx = self._context if hasattr(self, "_context") and self._context else ssl.create_default_context()
            self.sock = ctx.wrap_socket(raw_sock, server_hostname=self.host)

    class _PinnedHTTPHandler(urllib.request.HTTPHandler):
        def http_open(self, req):
            return self.do_open(_PinnedHTTPConnection, req)

    class _PinnedHTTPSHandler(urllib.request.HTTPSHandler):
        def https_open(self, req):
            return self.do_open(_PinnedHTTPSConnection, req)

    return urllib.request.build_opener(_PinnedHTTPHandler, _PinnedHTTPSHandler, _KhongTuChuyenHuong)


_SO_LAN_CHUYEN_HUONG_TOI_DA = 5


def _tai_anh_url_chong_chan(url: str, referer: str | None = None, max_bytes: int = 20 * 1024 * 1024) -> bytes:
    """Tải ảnh từ URL bên ngoài kèm Referer tự động vượt chống hotlink cho tool khách hàng."""
    import urllib.error
    from urllib.parse import urljoin, urlparse

    u = (url or "").strip()
    if not (u.startswith("http://") or u.startswith("https://")):
        raise LoiTaiAnh("image_url phải bắt đầu bằng http:// hoặc https://")
    parsed = urlparse(u)
    origin_ref = referer or f"{parsed.scheme}://{parsed.netloc}/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Referer": origin_ref,
    }
    for _ in range(_SO_LAN_CHUYEN_HUONG_TOI_DA + 1):
        ip_da_kiem = _kiem_tra_url_an_toan_ssrf(u)
        opener = _tao_opener_ghim_ip_chong_dns_rebinding(ip_da_kiem)
        try:
            with opener.open(urllib.request.Request(u, headers=headers), timeout=25) as resp:
                data = resp.read(max_bytes + 1)
            break
        except urllib.error.HTTPError as exc:
            dich = exc.headers.get("Location") if exc.code in (301, 302, 303, 307, 308) else None
            if not dich:
                raise LoiTaiAnh(f"Máy chủ ảnh trả mã lỗi HTTP {exc.code}.") from exc
            u = urljoin(u, dich)
        except (urllib.error.URLError, OSError) as exc:
            # KHÔNG trả nguyên văn lỗi mạng: "connection refused" vs "timeout" là công cụ dò cổng.
            raise LoiTaiAnh("Không kết nối được tới máy chủ ảnh.") from exc
    else:
        raise LoiTaiAnh("Ảnh chuyển hướng quá nhiều lần.")
    if len(data) > max_bytes:
        raise LoiTaiAnh("Ảnh từ image_url vượt quá dung lượng tối đa cho phép.")
    return data


def _ly_do_an_toan(exc: Exception) -> str:
    return str(exc) if isinstance(exc, (LoiTaiAnh, ValueError)) else "Lỗi không xác định khi tải ảnh."


async def _dong_goi_ket_qua_trang_developer(
    request: Request,
    session: AsyncSession,
    page: Page,
    nguoi: NguoiDung,
    ma_api: str,
    *,
    cached: bool = False,
    include_base64: bool = False,
) -> dict[str, Any]:
    kq = await doc_truyen_lay_trang(
        page.id,
        session=session,
        danh_tinh=_danh_tinh_tu_nguoi_dung(nguoi),
    )
    project = await session.get(Project, page.project_id)

    # Lấy thêm thông tin TypesetResult (cỡ chữ, màu chữ) nếu có
    rows_ts = (
        await session.execute(
            select(TextRegion.id, TypesetResult)
            .outerjoin(TypesetResult, TypesetResult.region_id == TextRegion.id)
            .where(TextRegion.page_id == page.id)
        )
    ).all()
    map_ts = {rid: ts for rid, ts in rows_ts if ts is not None}

    base_url = str(request.base_url).rstrip("/")
    import time as _time

    exp_ts = int(_time.time()) + 86400
    sig_anh = _ky_url_anh_developer(page.id, nguoi.id, exp_ts)
    duoi_key = f"?sig={sig_anh}&exp={exp_ts}"

    storage = get_storage()
    rel_preview = preview_relative_path(page.id)
    co_anh_dich = await run_in_threadpool(storage.exists, rel_preview)
    co_anh_xoa = bool(
        page.clean_image_path and await run_in_threadpool(storage.exists, page.clean_image_path)
    )

    rendered_b64: str | None = None
    if include_base64 and co_anh_dich:
        raw_png = await run_in_threadpool(storage.read, rel_preview)
        rendered_b64 = "data:image/png;base64," + base64.b64encode(raw_png).decode("ascii")

    regions_out = []
    for idx, v in enumerate(kq.vung):
        ts = map_ts.get(v.region_id)
        regions_out.append(
            {
                "region_id": str(v.region_id),
                "order": v.thu_tu_doc or (idx + 1),
                "bbox": {
                    "x": round(float(v.x), 1),
                    "y": round(float(v.y), 1),
                    "w": round(float(v.w), 1),
                    "h": round(float(v.h), 1),
                },
                "source_text": v.chu_goc or "",
                "translated_text": v.ban_dich or "",
                "low_confidence": bool(v.kem_tin_cay),
                "font_size": ts.font_size if ts else None,
                "text_color": ts.text_color if ts else "#111827",
                "stroke_color": ts.stroke_color if ts else "#FFFFFF",
            }
        )

    trang_thai_en = (
        "completed"
        if kq.xong
        else ("failed" if kq.loi or page.status.value.endswith("failed") else "processing")
    )

    return {
        "status": trang_thai_en,
        "page_status": kq.trang_thai.value,
        "completed": kq.xong,
        "cached": cached,
        "page_id": str(page.id),
        "project_id": str(page.project_id),
        "source_lang": project.source_lang.value if project else "ja",
        "target_lang": project.target_lang.value if project else "vi",
        "mode": project.che_do_pipeline.value if project else "day_du",
        "engine": (page.translate_engine_override or TranslationEngine.google_fast).value,
        "rendered_image_url": (
            f"{base_url}/api/v1/developer/pages/{page.id}/rendered-image{duoi_key}"
            if co_anh_dich
            else None
        ),
        "inpainted_image_url": (
            f"{base_url}/api/v1/developer/pages/{page.id}/inpainted-image{duoi_key}"
            if co_anh_xoa
            else None
        ),
        "rendered_image_base64": rendered_b64,
        "regions_count": len(regions_out),
        "regions": regions_out,
        "error": kq.loi,
        "quota": await _thong_tin_quota(session, nguoi),
    }


@router.get("/me", response_model=dict)
@router.get("/quota", response_model=dict)
async def developer_kiem_tra_quota(
    xac_thuc: tuple[NguoiDung, str] = Depends(_xac_thuc_developer),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Kiểm tra thông tin tài khoản & số dư lượt dịch bằng Developer API Key."""
    nguoi, _ = xac_thuc
    return {
        "ok": True,
        "account": {
            "id": str(nguoi.id),
            "email": nguoi.email,
            "display_name": nguoi.ten_hien,
        },
        "quota": await _thong_tin_quota(session, nguoi),
    }


@router.post("/consume-local-page", response_model=dict)
async def developer_khau_tru_trang_cuc_bo(
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    danh_tinh: DanhTinhHanMuc = Depends(danh_tinh_han_muc),
) -> dict[str, Any]:
    """Khấu trừ 1 lượt/trang trên sổ cái Server khi khách hàng chạy Bộ máy AI Cục bộ (`local_ocr_gpu`) trên App Windows:
    - Máy khách tự gánh 100% tải OCR + Dịch bằng CPU/GPU của khách (chi phí vận hành Server = 0 VNĐ).
    - Sổ cái Server vẫn kiểm tra & trừ đúng 1 lượt/trang vào hạn mức ngày (10 trang/ngày) hoặc ví mua thêm (`so_luot_mua_them`).
    - Chống trừ trùng (Idempotent) theo `page_key` / `sha256` của bức ảnh.
    - Riêng tài khoản Quản trị viên (`la_quan_tri = True`) được miễn trừ không giới hạn.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    page_key = str(body.get("page_key") or body.get("request_key") or body.get("sha256") or uuid.uuid4().hex).strip()

    # Nếu gửi kèm X-Customer-Api-Key (tr_live_...) mà chưa qua danh_tinh_han_muc
    if not danh_tinh.co_tai_khoan:
        api_hdr = (request.headers.get("X-Customer-Api-Key") or request.headers.get("X-API-Key") or "").strip()
        if api_hdr:
            nguoi_k = await tai_khoan.lay_theo_ma_phien(session, api_hdr)
            if nguoi_k is not None:
                danh_tinh = _danh_tinh_tu_nguoi_dung(nguoi_k)

    # Quản trị viên (Chủ hệ thống) chạy tự động không bị giới hạn lượt
    if (
        danh_tinh.co_tai_khoan
        and not danh_tinh.nguoi_goi.la_khach
        and getattr(danh_tinh.nguoi_goi.nguoi, "la_quan_tri", False)
    ):
        return {
            "ok": True,
            "admin_bypass": True,
            "deducted": 0,
        }

    chu_the_chinh = danh_tinh.chot[0].chu_the if danh_tinh.chot else "guest"
    so_luot_can = max(1, min(3, int(body.get("credits") or 1)))
    engine_name = str(body.get("engine") or "local_ocr_gpu").strip()
    page_uuid = uuid.uuid5(uuid.NAMESPACE_URL, f"local-ocr-gpu:{engine_name}:{chu_the_chinh}:{page_key}:0")
    for idx_c in range(so_luot_can):
        uid_c = (
            page_uuid
            if idx_c == 0
            else uuid.uuid5(uuid.NAMESPACE_URL, f"local-ocr-gpu:{engine_name}:{chu_the_chinh}:{page_key}:{idx_c}")
        )
        await giu_cho_moi_chot(session, danh_tinh, settings, trang_id=uid_c)
    await session.commit()

    import hashlib
    import hmac
    import time as _time
    from app.core.config import lay_khoa_bi_mat_noi_bo

    ts_ticket = int(_time.time())
    khoa_ky = lay_khoa_bi_mat_noi_bo(settings, nhan="execution-ticket-v1")
    sig_ticket = hmac.new(
        khoa_ky,
        f"{page_uuid}:{engine_name}:{so_luot_can}:{ts_ticket}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:32]

    return {
        "ok": True,
        "page_id": str(page_uuid),
        "engine": engine_name,
        "deducted": so_luot_can,
        "execution_ticket": f"{ts_ticket}.{sig_ticket}",
    }


@router.post("/translate-image", response_model=dict)
async def developer_dich_anh(
    request: Request,
    file: UploadFile | None = File(default=None, description="File ảnh truyện (PNG/JPG/WEBP)"),
    image_url: str | None = Form(default=None, description="Hoặc truyền URL ảnh trực tiếp từ web nguồn"),
    image_base64: str | None = Form(default=None, description="Hoặc truyền chuỗi Base64 của ảnh"),
    referer: str | None = Form(default=None, description="Referer tuỳ chọn để vượt chống hotlink khi tải từ image_url"),
    source_lang: SourceLang = Form(SourceLang.ja, description="Ngôn ngữ gốc: ja | ko | zh | en"),
    target_lang: TargetLang = Form(TargetLang.vi, description="Ngôn ngữ đích: vi | en"),
    engine: TranslationEngine = Form(
        TranslationEngine.google_fast,
        description="google_fast (nhanh) hoặc llm_context (AI đọc ngữ cảnh cả trang)",
    ),
    mode: ChePipeline = Form(
        ChePipeline.day_du,
        description="day_du = xoá chữ + vẽ chữ dịch hoàn chỉnh lên ảnh; chi_chu = chỉ lấy toạ độ + chữ dịch",
    ),
    font_style: str | None = Form(default=None, description="Kiểu phông chữ: bangers | romance | historical | comic"),
    glossary: str | None = Form(default=None, description="Từ điển nhân vật / xưng hô riêng"),
    wait: bool = Form(True, description="True = chờ dịch xong trong 1 lệnh gọi rồi trả kết quả ngay; False = trả page_id để hỏi sau"),
    timeout_sec: int = Form(90, description="Thời gian chờ tối đa (giây) khi wait=True (10..120)"),
    include_base64: bool = Form(False, description="True = đính kèm luôn ảnh đã dịch dạng Base64 trong JSON"),
    xac_thuc: tuple[NguoiDung, str] = Depends(_xac_thuc_developer),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Endpoint All-in-One cho Tool/Website khách hàng gửi 1 trang ảnh lên dịch và kéo kết quả về.
    Hỗ trợ cả `multipart/form-data` (gửi `file` / `image_url` / `image_base64`) LẪN `application/json`.
    """
    nguoi, ma_api = xac_thuc
    danh_tinh = _danh_tinh_tu_nguoi_dung(nguoi)

    # Hỗ trợ cả khách hàng gọi bằng JSON body (`Content-Type: application/json`)
    ctype = (request.headers.get("content-type") or "").lower()
    if "application/json" in ctype:
        try:
            body_json = await request.json()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=422, detail=f"JSON không hợp lệ: {exc}") from exc
        if isinstance(body_json, dict):
            image_url = body_json.get("image_url") or image_url
            image_base64 = body_json.get("image_base64") or image_base64
            referer = body_json.get("referer") or referer
            if "source_lang" in body_json and body_json["source_lang"]:
                source_lang = SourceLang(str(body_json["source_lang"]))
            if "target_lang" in body_json and body_json["target_lang"]:
                target_lang = TargetLang(str(body_json["target_lang"]))
            if "engine" in body_json and body_json["engine"]:
                engine = TranslationEngine(str(body_json["engine"]))
            if "mode" in body_json and body_json["mode"]:
                mode = ChePipeline(str(body_json["mode"]))
            if "font_style" in body_json:
                font_style = body_json["font_style"]
            if "glossary" in body_json:
                glossary = body_json["glossary"]
            if "wait" in body_json:
                wait = bool(body_json["wait"])
            if "timeout_sec" in body_json and body_json["timeout_sec"] is not None:
                timeout_sec = int(body_json["timeout_sec"])
            if "include_base64" in body_json:
                include_base64 = bool(body_json["include_base64"])

    _kiem_engine(engine, settings, co_tai_khoan=True)

    if file is not None:
        data = await file.read()
    elif image_base64 and image_base64.strip():
        try:
            b64_clean = image_base64.strip()
            if "," in b64_clean and b64_clean.startswith("data:"):
                b64_clean = b64_clean.split(",", 1)[1]
            data = base64.b64decode(b64_clean)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=422, detail=f"image_base64 không hợp lệ: {exc}") from exc
    elif image_url and image_url.strip():
        try:
            data = await run_in_threadpool(
                _tai_anh_url_chong_chan,
                image_url.strip(),
                referer,
                settings.max_upload_bytes,
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=422,
                detail=f"Không tải được ảnh từ image_url: {_ly_do_an_toan(exc)}",
            ) from exc
    else:
        raise HTTPException(
            status_code=422,
            detail="Phải gửi kèm 'file' (multipart/form-data), 'image_url' hoặc 'image_base64'.",
        )

    if not data:
        raise HTTPException(status_code=422, detail="Dữ liệu ảnh rỗng.")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413, detail=f"Ảnh vượt quá {settings.max_upload_mb}MB."
        )
    try:
        _mime, ext = sniff_image(data)
    except UnsupportedImage as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    project = await _chapter_doc_nhanh(
        session, danh_tinh.nguoi_goi, source_lang, mode, target_lang=target_lang
    )
    if font_style or glossary:
        from app.services.typeset.chon_font import luu_tuy_chon_du_an

        await run_in_threadpool(
            luu_tuy_chon_du_an,
            project.id,
            font_style=font_style,
            tu_dien_rieng=glossary,
        )

    next_order = (
        await session.scalar(
            select(func.coalesce(func.max(Page.order), 0) + 1).where(Page.project_id == project.id)
        )
    ) or 1

    page = Page(
        project_id=project.id,
        image_path="",
        order=next_order,
        status=PageStatus.queued,
        translate_engine_override=engine,
    )
    session.add(page)
    await session.flush()

    await giu_cho_moi_chot(session, danh_tinh, settings, trang_id=page.id)

    storage = get_storage()
    data = await run_in_threadpool(thu_nho_anh_trang, data, ext, settings.anh_trang_canh_dai_toi_da)
    page.image_path = await run_in_threadpool(
        storage.save_page_image, project.id, page.id, data, ext
    )

    bam_anh = tinh_bam_anh(data)
    if settings.doc_truyen_dung_cache_anh:
        trung_cache = await thu_sao_chep_tu_cache(
            session,
            bam_anh=bam_anh,
            source_lang=source_lang,
            target_lang=target_lang,
            engine=engine,
            che_do=mode,
            dich_page=page,
            storage=storage,
        )
        if trung_cache:
            ghi_nhan_trang_anh(
                bam_anh, source_lang, engine, mode, page.id, target_lang=target_lang
            )
            await session.commit()
            await session.refresh(page)
            return await _dong_goi_ket_qua_trang_developer(
                request,
                session,
                page,
                nguoi,
                ma_api,
                cached=True,
                include_base64=include_base64,
            )

    ghi_nhan_trang_anh(bam_anh, source_lang, engine, mode, page.id, target_lang=target_lang)
    job = Job(type=JobType.detect, page_id=page.id, status=JobStatus.queued)
    session.add(job)
    await session.commit()
    await session.refresh(page)

    sent, ly_do = dispatch_detect_job(job.id)
    if not sent:
        job.error_log = ly_do
        await session.commit()

    if not wait:
        return await _dong_goi_ket_qua_trang_developer(
            request,
            session,
            page,
            nguoi,
            ma_api,
            cached=False,
            include_base64=False,
        )

    # Chờ worker xử lý xong ngay trong 1 request để tool của khách hàng lấy kết quả 1 bước
    gioi_han = max(10, min(120, int(timeout_sec or 90)))
    so_nhip = int(gioi_han / 0.8)
    for _ in range(so_nhip):
        await asyncio.sleep(0.8)
        session.expire_all()
        page_moi = await session.get(Page, page.id)
        if page_moi is None:
            break
        kq_tam = await _dong_goi_ket_qua_trang_developer(
            request,
            session,
            page_moi,
            nguoi,
            ma_api,
            cached=False,
            include_base64=include_base64,
        )
        if kq_tam["status"] in ("completed", "failed"):
            return kq_tam

    session.expire_all()
    page_cuoi = await session.get(Page, page.id) or page
    return await _dong_goi_ket_qua_trang_developer(
        request,
        session,
        page_cuoi,
        nguoi,
        ma_api,
        cached=False,
        include_base64=include_base64,
    )


@router.get("/pages/{page_id}", response_model=dict)
async def developer_lay_ket_qua_trang(
    page_id: uuid.UUID,
    request: Request,
    include_base64: bool = Query(default=False),
    xac_thuc: tuple[NguoiDung, str] = Depends(_xac_thuc_developer),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Lấy trạng thái & kết quả dịch của 1 trang theo `page_id`."""
    nguoi, ma_api = xac_thuc
    page = await _get_page_or_404(session, page_id, NguoiGoi(nguoi=nguoi))
    return await _dong_goi_ket_qua_trang_developer(
        request,
        session,
        page,
        nguoi,
        ma_api,
        cached=False,
        include_base64=include_base64,
    )


@router.get("/pages/{page_id}/rendered-image")
async def developer_tai_anh_da_dich(
    page_id: uuid.UUID,
    request: Request,
    sig: str | None = Query(default=None, description="Chữ ký HMAC gắn theo trang"),
    exp: int | None = Query(default=None, description="Thời điểm hết hạn chữ ký (Unix timestamp)"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_customer_api_key: str | None = Header(default=None, alias="X-Customer-Api-Key"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    api_key_query: str | None = Query(default=None, alias="api_key"),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Response:
    """Tải trực tiếp file ảnh PNG đã xoá chữ + ghép chữ dịch hoàn chỉnh của trang.
    Chấp nhận chữ ký ngắn hạn `?sig=...&exp=...` (không làm lộ `tr_live_...`) hoặc Header API Key.
    """
    nguoi = await _xac_minh_chu_ky_anh_developer(session, page_id, sig, exp, settings)
    if nguoi is None:
        nguoi, _ = await _xac_thuc_developer(
            request=request,
            authorization=authorization,
            x_customer_api_key=x_customer_api_key,
            x_api_key=x_api_key,
            api_key_query=api_key_query,
            session=session,
            settings=settings,
        )
    await _get_page_or_404(session, page_id, NguoiGoi(nguoi=nguoi))
    storage = get_storage()
    rel = preview_relative_path(page_id)
    if not await run_in_threadpool(storage.exists, rel):
        raise HTTPException(
            status_code=404,
            detail="Chưa có ảnh đã ghép chữ (hãy chắc chắn bạn gửi mode=day_du và trang đã dịch xong).",
        )
    data = await run_in_threadpool(storage.read, rel)
    return Response(
        content=data,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/pages/{page_id}/inpainted-image")
async def developer_tai_anh_da_xoa_chu(
    page_id: uuid.UUID,
    request: Request,
    sig: str | None = Query(default=None, description="Chữ ký HMAC gắn theo trang"),
    exp: int | None = Query(default=None, description="Thời điểm hết hạn chữ ký (Unix timestamp)"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_customer_api_key: str | None = Header(default=None, alias="X-Customer-Api-Key"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    api_key_query: str | None = Query(default=None, alias="api_key"),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Response:
    """Tải trực tiếp file ảnh đã xoá sạch chữ gốc trong bong bóng (chưa vẽ chữ mới).
    Chấp nhận chữ ký ngắn hạn `?sig=...&exp=...` (không làm lộ `tr_live_...`) hoặc Header API Key.
    """
    nguoi = await _xac_minh_chu_ky_anh_developer(session, page_id, sig, exp, settings)
    if nguoi is None:
        nguoi, _ = await _xac_thuc_developer(
            request=request,
            authorization=authorization,
            x_customer_api_key=x_customer_api_key,
            x_api_key=x_api_key,
            api_key_query=api_key_query,
            session=session,
            settings=settings,
        )
    page = await _get_page_or_404(session, page_id, NguoiGoi(nguoi=nguoi))
    storage = get_storage()
    if not page.clean_image_path or not await run_in_threadpool(storage.exists, page.clean_image_path):
        raise HTTPException(
            status_code=404,
            detail="Chưa có ảnh xoá chữ cho trang này.",
        )
    data = await run_in_threadpool(storage.read, page.clean_image_path)
    return Response(
        content=data,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


class DeveloperTranslateChapterRequest(BaseModel):
    chapter_name: str = Field("Chapter API", max_length=200, description="Tên chapter")
    image_urls: list[str] = Field(..., min_length=1, max_length=80, description="Danh sách URL ảnh của cả chapter theo thứ tự trang")
    referer: str | None = Field(default=None, description="Referer tuỳ chọn để vượt chống hotlink")
    source_lang: SourceLang = Field(SourceLang.ja, description="ja | ko | zh | en")
    target_lang: TargetLang = Field(TargetLang.vi, description="vi | en")
    engine: TranslationEngine = Field(TranslationEngine.google_fast, description="google_fast hoặc llm_context")
    mode: ChePipeline = Field(ChePipeline.day_du, description="day_du hoặc chi_chu")
    font_style: str | None = Field(default=None)
    glossary: str | None = Field(default=None)


@router.post("/translate-chapter", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
async def developer_dich_ca_chapter_urls(
    body: DeveloperTranslateChapterRequest,
    request: Request,
    xac_thuc: tuple[NguoiDung, str] = Depends(_xac_thuc_developer),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Nhận danh sách `image_urls` của nguyên 1 chapter từ tool khách hàng, tự động tải từng trang,
    kiểm tra Cache Cộng Đồng SHA-256 và xếp hàng dịch toàn bộ chapter.
    """
    from app.core.cong_han_muc import con_du_khong
    from app.models.enums import IntendedUse

    nguoi, ma_api = xac_thuc
    danh_tinh = _danh_tinh_tu_nguoi_dung(nguoi)
    _kiem_engine(body.engine, settings, co_tai_khoan=True)

    urls = [u.strip() for u in body.image_urls if u and u.strip()]
    if not urls:
        raise HTTPException(status_code=422, detail="Danh sách image_urls rỗng.")

    await con_du_khong(session, danh_tinh, settings, so_trang=len(urls))

    project = Project(
        name=body.chapter_name.strip() or "Chapter API",
        source_lang=body.source_lang,
        target_lang=body.target_lang,
        intended_use=IntendedUse.personal,
        che_do_pipeline=body.mode,
        chu_so_huu_id=nguoi.id,
    )
    session.add(project)
    await session.flush()

    if body.font_style or body.glossary:
        from app.services.typeset.chon_font import luu_tuy_chon_du_an

        await run_in_threadpool(
            luu_tuy_chon_du_an,
            project.id,
            font_style=body.font_style,
            tu_dien_rieng=body.glossary,
        )

    storage = get_storage()
    pages_out = []
    jobs_to_dispatch: list[uuid.UUID] = []

    for idx, url in enumerate(urls, start=1):
        try:
            raw_data = await run_in_threadpool(
                _tai_anh_url_chong_chan, url, body.referer, settings.max_upload_bytes
            )
            _mime, ext = sniff_image(raw_data)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=422,
                detail=f"Trang số {idx} ({url}) không tải được hoặc không phải ảnh hợp lệ: {_ly_do_an_toan(exc)}",
            ) from exc

        page = Page(
            project_id=project.id,
            image_path="",
            order=idx,
            status=PageStatus.queued,
            translate_engine_override=body.engine,
        )
        session.add(page)
        await session.flush()

        await giu_cho_moi_chot(session, danh_tinh, settings, trang_id=page.id)

        du_lieu = await run_in_threadpool(
            thu_nho_anh_trang, raw_data, ext, settings.anh_trang_canh_dai_toi_da
        )
        page.image_path = await run_in_threadpool(
            storage.save_page_image, project.id, page.id, du_lieu, ext
        )

        bam_anh = tinh_bam_anh(du_lieu)
        trung_cache = False
        if settings.doc_truyen_dung_cache_anh:
            trung_cache = await thu_sao_chep_tu_cache(
                session,
                bam_anh=bam_anh,
                source_lang=body.source_lang,
                target_lang=body.target_lang,
                engine=body.engine,
                che_do=body.mode,
                dich_page=page,
                storage=storage,
            )
        ghi_nhan_trang_anh(
            bam_anh, body.source_lang, body.engine, body.mode, page.id, target_lang=body.target_lang
        )

        if not trung_cache:
            job = Job(type=JobType.detect, page_id=page.id, status=JobStatus.queued)
            session.add(job)
            await session.flush()
            jobs_to_dispatch.append(job.id)

        pages_out.append(
            {
                "order": idx,
                "page_id": str(page.id),
                "source_url": url,
                "cached": trung_cache,
                "status": "completed" if trung_cache else "processing",
            }
        )

    await session.commit()

    for jid in jobs_to_dispatch:
        sent, reason = dispatch_detect_job(jid)
        if not sent:
            j = await session.get(Job, jid)
            if j is not None:
                j.error_log = reason
    await session.commit()

    base_url = str(request.base_url).rstrip("/")
    return {
        "status": "accepted",
        "project_id": str(project.id),
        "chapter_name": project.name,
        "total_pages": len(pages_out),
        "cached_pages": sum(1 for p in pages_out if p["cached"]),
        "poll_chapter_url": f"{base_url}/api/v1/developer/projects/{project.id}",
        "pages": pages_out,
        "quota": await _thong_tin_quota(session, nguoi),
    }


@router.get("/projects/{project_id}", response_model=dict)
async def developer_lay_ket_qua_chapter(
    project_id: uuid.UUID,
    request: Request,
    xac_thuc: tuple[NguoiDung, str] = Depends(_xac_thuc_developer),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Lấy tiến độ & danh sách toàn bộ các trang đã dịch của 1 chapter (`project_id`)."""
    from app.api.v1.routes import _get_project_or_404

    nguoi, ma_api = xac_thuc
    project = await _get_project_or_404(session, project_id, NguoiGoi(nguoi=nguoi))
    pages = (
        await session.execute(
            select(Page).where(Page.project_id == project.id).order_by(Page.order)
        )
    ).scalars().all()

    ds_trang = []
    so_xong = 0
    for p in pages:
        item = await _dong_goi_ket_qua_trang_developer(
            request, session, p, nguoi, ma_api, cached=False, include_base64=False
        )
        if item["completed"]:
            so_xong += 1
        ds_trang.append(item)

    return {
        "project_id": str(project.id),
        "chapter_name": project.name,
        "source_lang": project.source_lang.value,
        "target_lang": project.target_lang.value,
        "mode": project.che_do_pipeline.value,
        "total_pages": len(ds_trang),
        "completed_pages": so_xong,
        "all_completed": len(ds_trang) > 0 and so_xong == len(ds_trang),
        "pages": ds_trang,
        "quota": await _thong_tin_quota(session, nguoi),
    }


class DeveloperTranslateTextRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1, max_length=200, description="Mảng các đoạn văn bản cần dịch")
    source_lang: SourceLang = Field(SourceLang.ja, description="Ngôn ngữ gốc: ja | ko | zh | en")
    target_lang: TargetLang = Field(TargetLang.vi, description="Ngôn ngữ đích: vi | en")
    engine: TranslationEngine = Field(TranslationEngine.google_fast, description="google_fast hoặc llm_context")


@router.post("/translate-text", response_model=dict)
async def developer_dich_van_ban(
    body: DeveloperTranslateTextRequest,
    xac_thuc: tuple[NguoiDung, str] = Depends(_xac_thuc_developer),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Dịch hàng loạt đoạn văn bản / chương truyện chữ (Web Novel / Light Novel) cho tool khách hàng."""
    nguoi, _ = xac_thuc
    danh_tinh = _danh_tinh_tu_nguoi_dung(nguoi)
    _kiem_engine(body.engine, settings, co_tai_khoan=True)

    doan_sach = [str(t or "").strip() for t in body.texts[:200]]
    if not any(doan_sach):
        raise HTTPException(status_code=422, detail="Danh sách văn bản rỗng.")

    # Mỗi 30 đoạn văn bản tính 1 lượt trang
    so_luot_can = max(1, (len(doan_sach) + 29) // 30)
    for _ in range(so_luot_can):
        await giu_cho_moi_chot(session, danh_tinh, settings, trang_id=uuid.uuid4())
    await session.commit()

    from app.services.translate.engines import GoogleTranslateEngine, LLMContextTranslator

    def _dich_dong_bo() -> list[str]:
        from app.core.config import dong_bo_khoa_ai_dong
        dong_bo_khoa_ai_dong(settings)
        if body.engine is TranslationEngine.llm_context and settings.llm_configured:
            try:
                tr = LLMContextTranslator(
                    api_keys=settings.llm_api_keys_list,
                    model_name=settings.llm_model_name,
                )
                return tr.translate(
                    doan_sach,
                    source_lang=body.source_lang.value,
                    target_lang=body.target_lang.value,
                )
            except Exception:  # noqa: BLE001
                pass
        tr_free = GoogleTranslateEngine()
        return tr_free.translate(
            doan_sach,
            source_lang=body.source_lang.value,
            target_lang=body.target_lang.value,
        )

    ban_dich = await run_in_threadpool(_dich_dong_bo)
    return {
        "status": "completed",
        "source_lang": body.source_lang.value,
        "target_lang": body.target_lang.value,
        "engine": body.engine.value,
        "count": len(ban_dich),
        "translations": ban_dich,
        "quota": await _thong_tin_quota(session, nguoi),
    }
