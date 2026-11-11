"""Hệ thống Thanh toán Trực tuyến An toàn (Việt Nam VietQR/SePay + Quốc tế Stripe & PayPal Orders v2).

Tuân thủ 10 Nguyên tắc vàng (`payment-integration-vn-global`):
1. Chỉ tin máy chủ cổng thanh toán (chữ ký HMAC / xác minh API trực tiếp từ server).
2. Đủ 5 phép kiểm trước khi cấp quyền lợi: (a) chữ ký/nguồn hợp lệ, (b) paid_amount >= order.amount,
   (c) đúng loại tiền tệ, (d) đúng tài khoản/merchant nhận tiền, (e) khớp đúng đơn nội bộ & đúng user.
3. Idempotency fail-closed bằng `UNIQUE(provider, provider_event_id)` trên `payment_events` TRƯỚC khi đổi tier.
   Nhận diện trùng bằng SQLSTATE `23505`; lỗi CSDL khác trả HTTP 503 để cổng gửi lại.
4. Máy trạng thái đơn chuyển bằng Compare-And-Set (`UPDATE ... WHERE id=:id AND status='pending'`).
5. Mọi tình huống "đã nhận tiền nhưng chưa giao quyền lợi" -> ghi `payment_reviews` + bắn cảnh báo ngay.
6. Một nguồn giá duy nhất (`catalog`), không trùng giá VNĐ trên kênh chuyển khoản.
7. Tiền là số nguyên ở đơn vị nhỏ nhất (`VND` = đồng, `USD` = cent), parse bằng `Decimal`.
8. Không có secret mặc định trong code; thiếu secret -> tắt cổng (`404`/`503`); hỗ trợ xoay 2 secret (`*_PREVIOUS`).
9. Quy tắc gói rõ ràng: chặn hạ gói khi gói cao còn hạn (`409` lúc tạo đơn, `needs_manual_review` ở webhook);
   gia hạn cùng gói -> cộng dồn ngày; nâng gói -> bắt đầu kỳ mới và nâng hạng tức thì.
10. Cột quyền lợi (`cap_do_goi`, `ma_goi_hien_tai`, `het_han_goi`, `trang_thai_billing`, `gio_luot_json`)
    chỉ server ghi trong cùng transaction với `grant()`.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import re
import secrets
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import httpx
import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.danh_tinh_khach import TEN_CAP_DO, tinh_cap_do
from app.models import DonNapLuot, NguoiDung, PaymentEvent, PaymentOrder, PaymentReview

logger = logging.getLogger(__name__)

# Bảng chữ cái Crockford Base32 (32 ký tự, loại bỏ I, L, O, U để khách gõ nội dung CK không bao giờ nhầm)
CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
ORDER_CODE_PREFIX = "CIO"
ORDER_CODE_REGEX = re.compile(r"\b(CIO[0-9A-HJ-KM-NP-TV-Z]{8})\b", re.IGNORECASE)

# Thứ bậc gói cước chuẩn (dùng để kiểm nâng/hạ/gia hạn gói)
TIER_RANK: dict[str, int] = {
    "free": 0,
    "trial": 1,
    "starter": 2,
    "pro": 3,
    "studio": 4,
    "unlimited": 5,
}
RANK_TO_TIER_NAME: dict[int, str] = {v: k for k, v in TIER_RANK.items()}

# Lua script mở khoá nguyên tử cho job định kỳ 1 lần/ngày (§12.5)
RELEASE_LUA = (
    "if redis.call('get',KEYS[1])==ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end"
)

# Khoá cấu hình động lưu bởi Admin (KHÔNG BAO GIỜ có secret mặc định)
_TEP_CAU_HINH_THANH_TOAN = "quan_tri/cau_hinh_ngan_hang.json"
_CAU_HINH_MEM_CACHE: dict[str, Any] = {}
_DA_NAP_CAU_HINH_MEM = False

_SENSITIVE_KEY_MARKERS = (
    "secret",
    "token",
    "password",
    "authorization",
    "api_key",
    "apikey",
    "signature",
    "private_key",
    "card_number",
    "cvv",
    "cvc",
)

# Bản đồ mã ngân hàng phổ biến sang mã VietQR chuẩn
VIETQR_BANK_ALIASES: dict[str, str] = {
    "ACB": "ACB",
    "MB": "MB",
    "MBBANK": "MB",
    "VCB": "VCB",
    "VIETCOMBANK": "VCB",
    "TCB": "TCB",
    "TECHCOMBANK": "TCB",
    "BIDV": "BIDV",
    "CTG": "ICB",
    "VIETINBANK": "ICB",
    "ICB": "ICB",
    "VPB": "VPB",
    "VPBANK": "VPB",
    "TPB": "TPB",
    "TPBANK": "TPB",
    "STB": "STB",
    "SACOMBANK": "STB",
    "VIB": "VIB",
    "MSB": "MSB",
    "OCB": "OCB",
    "HDB": "HDB",
    "SHB": "SHB",
}


class NeedsManualReviewError(Exception):
    """Ngoại lệ báo hiệu giao dịch đã nhận tiền nhưng cần chuyển sang hàng chờ duyệt tay."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class PlanCatalogItem:
    code: str
    name: str
    tier_name: str
    tier_rank: int
    credits: int
    duration_days: int
    billing_cycle: str  # 'monthly' | 'yearly' | 'one_time'
    amount_vnd: int
    amount_usd_cents: int
    original_vnd: int
    original_usd_cents: int
    is_first_time_promo: bool
    is_subscription: bool
    note: str


# ---------------------------------------------------------------------------
# 1. Xử lý tiền tệ an toàn bằng Decimal (§1.7 & §12.1)
# ---------------------------------------------------------------------------


def parse_minor_units(raw: Any, exponent: int = 2) -> int | None:
    """'19.99' -> 1999 (USD, exponent=2); '99000' -> 99000 (VND, exponent=0).
    Trả None nếu thiếu, bool, không phải số, <= 0, vô hạn, hoặc lẻ hơn đơn vị nhỏ nhất.
    Tuyệt đối KHÔNG bao giờ dùng float() hay gán giá trị mặc định khi trả None.
    """
    if raw is None or isinstance(raw, bool):
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        d = Decimal(s)
    except (InvalidOperation, ValueError):
        return None
    if not d.is_finite() or d <= 0:
        return None
    m = d * (Decimal(10) ** exponent)
    return int(m) if m == m.to_integral_value() else None


def format_usd_from_cents(cents: int) -> str:
    """Đổi cent nguyên sang chuỗi USD 2 chữ số thập phân chính xác ('1999' -> '19.99')."""
    d = (Decimal(int(cents)) / Decimal(100)).quantize(Decimal("0.01"))
    return format(d, "f")


# ---------------------------------------------------------------------------
# 2. Sinh & Trích xuất Mã đơn Crockford Base32 (§3.1)
# ---------------------------------------------------------------------------


def generate_order_code(prefix: str = ORDER_CODE_PREFIX, length: int = 8) -> str:
    """Sinh mã đơn duy nhất gồm tiền tố + 8 ký tự Crockford Base32 (không có I, L, O, U)."""
    body = "".join(secrets.choice(CROCKFORD_ALPHABET) for _ in range(length))
    return f"{prefix.upper()}{body}"


def extract_order_code(text: str | None) -> str | None:
    """Trích mã đơn nội bộ từ nội dung chuyển khoản bằng regex chặt có ranh giới từ."""
    if not text:
        return None
    # Ngân hàng đôi khi chèn khoảng trắng hoặc gạch ngang giữa tiền tố CIO và 8 ký tự
    cleaned = str(text).strip().upper()
    m = ORDER_CODE_REGEX.search(cleaned)
    if m:
        return m.group(1).upper()
    m_dash = re.search(r"\bCIO[-_ ]([0-9A-HJ-KM-NP-TV-Z]{8})\b", cleaned)
    if m_dash:
        return f"CIO{m_dash.group(1).upper()}"
    return None


# ---------------------------------------------------------------------------
# 3. Lọc Secret / PII & Quản lý Cấu hình Động (§6, §13)
# ---------------------------------------------------------------------------


def mask_secret(val: str | None) -> str:
    s = (val or "").strip()
    if not s:
        return ""
    if len(s) <= 8:
        return "••••••••"
    return f"{s[:4]}••••••{s[-4:]}"


def sanitize_payload(obj: Any, depth: int = 0) -> Any:
    """Loại bỏ secret/token/chữ ký nhạy cảm trước khi lưu `raw_payload` hoặc gửi cảnh báo."""
    if depth > 6:
        return "[truncated]"
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            ks = str(k)
            kl = ks.lower()
            if any(marker in kl for marker in _SENSITIVE_KEY_MARKERS):
                out[ks] = "[REDACTED]"
            else:
                out[ks] = sanitize_payload(v, depth + 1)
        return out
    if isinstance(obj, (list, tuple)):
        return [sanitize_payload(x, depth + 1) for x in list(obj)[:40]]
    if isinstance(obj, (bytes, bytearray)):
        return f"[{len(obj)} bytes]"
    if isinstance(obj, str):
        if len(obj) > 500:
            return obj[:500] + "…"
        return obj
    if isinstance(obj, (int, float, bool)) or obj is None:
        return obj
    return str(obj)[:300]


_REVOKED_PUBLIC_SECRET_SHA256 = "3fc642add5c6f06da642660dabf8e15ec00aed15e3ed010b777b8f98fd512f00"


def _is_revoked_public_secret(val: str | None) -> bool:
    s = (val or "").strip()
    if not s:
        return False
    return hashlib.sha256(s.encode("utf-8")).hexdigest() == _REVOKED_PUBLIC_SECRET_SHA256


_DYNAMIC_PAYMENT_TMP_FILE = "/tmp/cau_hinh_ngan_hang.json"


def reset_payment_config_cache() -> None:
    global _DA_NAP_CAU_HINH_MEM
    _CAU_HINH_MEM_CACHE.clear()
    _DA_NAP_CAU_HINH_MEM = False


def read_dynamic_payment_store() -> dict[str, Any]:
    """Đọc tệp cấu hình động do Admin lưu (không pha trộn mặc định)."""
    global _DA_NAP_CAU_HINH_MEM
    if _DA_NAP_CAU_HINH_MEM and _CAU_HINH_MEM_CACHE:
        return dict(_CAU_HINH_MEM_CACHE)

    data: dict[str, Any] = {}
    tmp_p = Path(_DYNAMIC_PAYMENT_TMP_FILE)
    try:
        if tmp_p.is_file():
            parsed = json.loads(tmp_p.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                data.update(parsed)
    except Exception:
        pass

    if not data:
        try:
            from app.services.storage import get_storage

            storage = get_storage()
            raw = storage.read(_TEP_CAU_HINH_THANH_TOAN)
            if raw:
                parsed = json.loads(raw.decode("utf-8"))
                if isinstance(parsed, dict):
                    data.update(parsed)
        except Exception:
            pass

    # Chặn triệt để chuỗi secret mặc định cũ từng lộ trong code nếu từng bị ghi xuống đĩa!
    if _is_revoked_public_secret(str(data.get("webhook_bi_mat") or "")):
        data["webhook_bi_mat"] = ""
    if _is_revoked_public_secret(str(data.get("sepay_webhook_secret") or "")):
        data["sepay_webhook_secret"] = ""

    _CAU_HINH_MEM_CACHE.clear()
    _CAU_HINH_MEM_CACHE.update(data)
    _DA_NAP_CAU_HINH_MEM = True
    return dict(data)


def write_dynamic_payment_store(updates: dict[str, Any]) -> dict[str, Any]:
    """Ghi cấu hình động xuống kho bền và ĐỌC LẠI từ kho để xác minh (§5 & §11)."""
    current = read_dynamic_payment_store()
    merged = dict(current)
    for k, v in updates.items():
        if v is None:
            continue
        if isinstance(v, str):
            val_clean = v.strip()
            if _is_revoked_public_secret(val_clean):
                raise HTTPException(
                    status_code=422,
                    detail="Secret mẫu đã lộ trên git công khai, tuyệt đối không được sử dụng lại.",
                )
            merged[k] = val_clean
        else:
            merged[k] = v

    raw_bytes = json.dumps(merged, ensure_ascii=False, indent=2).encode("utf-8")
    tmp_p = Path(_DYNAMIC_PAYMENT_TMP_FILE)
    saved_any = False
    try:
        tmp_p.parent.mkdir(parents=True, exist_ok=True)
        tmp_p.write_bytes(raw_bytes)
        saved_any = True
    except Exception:
        pass
    try:
        from app.services.storage import get_storage

        storage = get_storage()
        storage.save(_TEP_CAU_HINH_THANH_TOAN, raw_bytes)
        saved_any = True
    except Exception:
        pass

    reset_payment_config_cache()
    read_back = read_dynamic_payment_store()
    if not saved_any:
        _CAU_HINH_MEM_CACHE.update(merged)
        read_back = dict(_CAU_HINH_MEM_CACHE)
    return read_back


def resolve_payment_config(settings: Settings | None = None) -> dict[str, Any]:
    """Hợp nhất cấu hình Thanh toán theo thứ tự ưu tiên chuẩn §13:
    Biến môi trường -> Cấu hình Admin -> Rỗng (tắt cổng, TUYỆT ĐỐI không có mặc định).
    """
    st = settings or get_settings()
    dyn = read_dynamic_payment_store()

    def _pick_secret(env_val: str, dyn_key: str) -> str:
        ev = (env_val or "").strip()
        if ev and not _is_revoked_public_secret(ev):
            return ev
        dv = str(dyn.get(dyn_key) or "").strip()
        if dv and not _is_revoked_public_secret(dv):
            return dv
        return ""

    def _pick_text(env_val: str, dyn_key: str) -> str:
        ev = (env_val or "").strip()
        if ev:
            return ev
        return str(dyn.get(dyn_key) or "").strip()

    sepay_primary = (
        _pick_secret(st.sepay_webhook_secret, "sepay_webhook_secret")
        or _pick_secret(st.webhook_nap_luot_bi_mat, "webhook_bi_mat")
    )
    sepay_prev = _pick_secret(st.sepay_webhook_secret_previous, "sepay_webhook_secret_previous")
    sepay_secrets = [s for s in (sepay_primary, sepay_prev) if s]

    stripe_secret_key = _pick_secret(st.stripe_secret_key, "stripe_secret_key")
    stripe_wh_primary = _pick_secret(st.stripe_webhook_secret, "stripe_webhook_secret")
    stripe_wh_prev = _pick_secret(st.stripe_webhook_secret_previous, "stripe_webhook_secret_previous")
    stripe_wh_secrets = [s for s in (stripe_wh_primary, stripe_wh_prev) if s]

    paypal_client_id = _pick_text(st.paypal_client_id, "paypal_client_id")
    paypal_client_secret = _pick_secret(st.paypal_client_secret, "paypal_client_secret")
    paypal_merchant_id = _pick_text(st.paypal_merchant_id, "paypal_merchant_id")
    paypal_email = _pick_text(st.paypal_email, "paypal_email").lower()
    paypal_webhook_id = _pick_text(st.paypal_webhook_id, "paypal_webhook_id")
    paypal_mode = str(dyn.get("paypal_mode") or st.paypal_mode or "live").strip().lower()
    if paypal_mode not in ("sandbox", "live"):
        paypal_mode = "live"

    ngan_hang_ten = _pick_text(st.ngan_hang_ten, "ngan_hang_ten")
    ngan_hang_so_tk = _pick_text(st.ngan_hang_so_tk, "ngan_hang_so_tk")
    ngan_hang_chu_tk = _pick_text(st.ngan_hang_chu_tk, "ngan_hang_chu_tk")

    telegram_bot_token = _pick_secret(st.telegram_bot_token, "telegram_bot_token")
    telegram_chat_id = _pick_text(st.telegram_chat_id, "telegram_chat_id")
    alert_webhook_url = _pick_secret(st.payment_alert_webhook_url, "payment_alert_webhook_url")

    raw_overrides = dyn.get("price_overrides")
    price_overrides = raw_overrides if isinstance(raw_overrides, dict) else {}

    stripe_price_map: dict[str, str] = {}
    for raw_map in (dyn.get("stripe_price_map"), st.stripe_price_map_json):
        if isinstance(raw_map, dict):
            stripe_price_map.update({str(k): str(v).strip() for k, v in raw_map.items() if str(v).strip()})
        elif isinstance(raw_map, str) and raw_map.strip():
            try:
                parsed_map = json.loads(raw_map)
                if isinstance(parsed_map, dict):
                    stripe_price_map.update(
                        {str(k): str(v).strip() for k, v in parsed_map.items() if str(v).strip()}
                    )
            except Exception:
                pass

    vietqr_enabled = bool(ngan_hang_ten and ngan_hang_so_tk and sepay_secrets)
    stripe_enabled = bool(stripe_secret_key and stripe_wh_secrets)
    paypal_enabled = bool(
        paypal_client_id and paypal_client_secret and (paypal_merchant_id or paypal_email)
    )

    return {
        "ngan_hang_ten": ngan_hang_ten,
        "ngan_hang_so_tk": ngan_hang_so_tk,
        "ngan_hang_chu_tk": ngan_hang_chu_tk,
        "sepay_secrets": sepay_secrets,
        "sepay_configured": bool(sepay_secrets),
        "sepay_masked": mask_secret(sepay_primary),
        "sepay_allow_apikey_auth": bool(st.sepay_allow_apikey_auth or dyn.get("sepay_allow_apikey_auth")),
        "stripe_secret_key": stripe_secret_key,
        "stripe_secret_configured": bool(stripe_secret_key),
        "stripe_secret_masked": mask_secret(stripe_secret_key),
        "stripe_webhook_secrets": stripe_wh_secrets,
        "stripe_webhook_configured": bool(stripe_wh_secrets),
        "stripe_webhook_masked": mask_secret(stripe_wh_primary),
        "stripe_price_map": stripe_price_map,
        "paypal_client_id": paypal_client_id,
        "paypal_client_secret": paypal_client_secret,
        "paypal_secret_configured": bool(paypal_client_secret),
        "paypal_secret_masked": mask_secret(paypal_client_secret),
        "paypal_merchant_id": paypal_merchant_id,
        "paypal_email": paypal_email,
        "paypal_webhook_id": paypal_webhook_id,
        "paypal_mode": paypal_mode,
        "paypal_enable_legacy_ipn": bool(st.paypal_enable_legacy_ipn),
        "rapidapi_url": str(dyn.get("rapidapi_url") or "").strip(),
        "rapidapi_proxy_secret": _pick_secret(st.rapidapi_proxy_secret, "rapidapi_proxy_secret"),
        "telegram_bot_token": telegram_bot_token,
        "telegram_chat_id": telegram_chat_id,
        "telegram_configured": bool(telegram_bot_token and telegram_chat_id),
        "alert_webhook_url": alert_webhook_url,
        "vietqr_enabled": vietqr_enabled,
        "stripe_enabled": stripe_enabled,
        "paypal_enabled": paypal_enabled,
        "price_overrides": price_overrides,
    }


def build_vietqr_url(bank_code: str, account_number: str, account_name: str, amount_vnd: int, order_code: str) -> str:
    """Sinh liên kết ảnh VietQR chuẩn với số tiền chốt và mã đơn Crockford Base32."""
    import urllib.parse

    clean_bank = VIETQR_BANK_ALIASES.get(bank_code.strip().upper(), bank_code.strip().upper())
    clean_acc = re.sub(r"\s+", "", account_number.strip())
    if not clean_bank or not clean_acc:
        return ""
    params = {
        "amount": str(int(amount_vnd)),
        "addInfo": order_code,
    }
    if account_name.strip():
        params["accountName"] = account_name.strip()
    return f"https://img.vietqr.io/image/{clean_bank}-{clean_acc}-compact2.png?{urllib.parse.urlencode(params)}"


# ---------------------------------------------------------------------------
# 4. Một Nguồn Giá Duy Nhất (`catalog`) & Cờ Lần Đầu từ CSDL (§4, §5)
# ---------------------------------------------------------------------------

_BASE_PLANS: tuple[dict[str, Any], ...] = (
    {
        "code": "trial_pack_50",
        "name_first": "🎁 Gói Trải Nghiệm Ưu Đãi Lần Đầu (150 Credits / tháng)",
        "name_renew": "🎁 Gói Trải Nghiệm Gia Hạn (150 Credits / tháng)",
        "tier_name": "trial",
        "tier_rank": 1,
        "credits": 150,
        "duration_days": 30,
        "billing_cycle": "monthly",
        "first_vnd": 25_000,
        "renew_vnd": 45_000,
        "first_usd_cents": 199,
        "renew_usd_cents": 349,
        "is_subscription": True,
        "note_first": "Ưu đãi lần đầu $1.99/tháng (25.000đ · gia hạn $3.49 / 45.000đ) · Mở khóa OCR tách chữ + AI Hội Thoại + Hồi 50 lượt/3 giờ.",
        "note_renew": "Giá gia hạn $3.49/tháng (45.000đ) · 150 Credits + Mở khóa OCR tách chữ + AI Hội Thoại + Hồi 50 lượt/3 giờ.",
    },
    {
        "code": "starter_monthly",
        "name_first": "⭐ Gói Starter Ưu Đãi Lần Đầu (300 Credits / tháng)",
        "name_renew": "⭐ Gói Starter Gia Hạn (300 Credits / tháng)",
        "tier_name": "starter",
        "tier_rank": 2,
        "credits": 300,
        "duration_days": 30,
        "billing_cycle": "monthly",
        "first_vnd": 49_000,
        "renew_vnd": 89_000,
        "first_usd_cents": 399,
        "renew_usd_cents": 649,
        "is_subscription": True,
        "note_first": "Ưu đãi lần đầu $3.99/tháng (49.000đ · gia hạn $6.49 / 89.000đ) · Mở khóa OCR tách chữ + AI Hội Thoại + Hồi 90 lượt/3 giờ.",
        "note_renew": "Giá gia hạn $6.49/tháng (89.000đ) · 300 Credits + Mở khóa OCR tách chữ + AI Hội Thoại + Hồi 90 lượt/3 giờ.",
    },
    {
        "code": "pro_monthly",
        "name_first": "🔥 Gói Lite / Reader Ưu Đãi Lần Đầu (800 Credits / tháng)",
        "name_renew": "🔥 Gói Lite / Reader Gia Hạn (800 Credits / tháng)",
        "tier_name": "pro",
        "tier_rank": 3,
        "credits": 800,
        "duration_days": 30,
        "billing_cycle": "monthly",
        "first_vnd": 99_000,
        "renew_vnd": 149_000,
        "first_usd_cents": 699,
        "renew_usd_cents": 999,
        "is_subscription": True,
        "note_first": "Ưu đãi lần đầu $6.99/tháng (99.000đ · gia hạn $9.99 / 149.000đ) · Mở khóa Scan Ảnh AI Ngữ Cảnh Đám Mây + Hồi 200 lượt/3 giờ.",
        "note_renew": "Giá gia hạn $9.99/tháng (149.000đ) · 800 Credits + Scan Ảnh AI Ngữ Cảnh Đám Mây + Hồi 200 lượt/3 giờ.",
    },
    {
        "code": "studio_monthly",
        "name_first": "💎 Gói Tiêu Chuẩn / Studio + API (3.000 Credits / tháng — Đề xuất)",
        "name_renew": "💎 Gói Tiêu Chuẩn / Studio + API Gia Hạn (3.000 Credits / tháng)",
        "tier_name": "studio",
        "tier_rank": 4,
        "credits": 3_000,
        "duration_days": 30,
        "billing_cycle": "monthly",
        "first_vnd": 199_000,
        "renew_vnd": 389_000,
        "first_usd_cents": 1_299,
        "renew_usd_cents": 1_999,
        "is_subscription": True,
        "note_first": "Ưu đãi lần đầu $12.99/tháng (199.000đ · gia hạn $19.99 / 389.000đ) · 3.000 Credits + Developer API Key (tr_live_...) + Hồi 450 lượt/3 giờ.",
        "note_renew": "Giá gia hạn $19.99/tháng (389.000đ) · 3.000 Credits + Developer API Key (tr_live_...) + Hồi 450 lượt/3 giờ.",
    },
    {
        "code": "unlimited_plan",
        "name_first": "🏢 Gói Pro Max / Unlimited API (10.000 Credits / tháng)",
        "name_renew": "🏢 Gói Pro Max / Unlimited API Gia Hạn (10.000 Credits / tháng)",
        "tier_name": "unlimited",
        "tier_rank": 5,
        "credits": 10_000,
        "duration_days": 30,
        "billing_cycle": "monthly",
        "first_vnd": 399_000,
        "renew_vnd": 799_000,
        "first_usd_cents": 2_499,
        "renew_usd_cents": 3_999,
        "is_subscription": True,
        "note_first": "Ưu đãi lần đầu $24.99/tháng (399.000đ · gia hạn $39.99 / 799.000đ) · 10.000 Credits + Full Developer API Key + Hồi 900 lượt/3 giờ.",
        "note_renew": "Giá gia hạn $39.99/tháng (799.000đ) · 10.000 Credits + Full Developer API Key + Hồi 900 lượt/3 giờ.",
    },
    {
        "code": "starter_yearly",
        "name_first": "🎁 Gói Starter Năm (3.600 Credits / năm)",
        "name_renew": "🎁 Gói Starter Năm Gia Hạn (3.600 Credits / năm)",
        "tier_name": "starter",
        "tier_rank": 2,
        "credits": 3_600,
        "duration_days": 365,
        "billing_cycle": "yearly",
        "first_vnd": 450_000,
        "renew_vnd": 708_000,
        "first_usd_cents": 2_999,
        "renew_usd_cents": 5_988,
        "is_subscription": True,
        "note_first": "Ưu đãi lần đầu $29.99/năm (450.000đ · gia hạn $59.88 / 708.000đ) · 3.600 Credits/năm.",
        "note_renew": "Giá gia hạn $59.88/năm (708.000đ) · 3.600 Credits/năm.",
    },
    {
        "code": "pro_yearly",
        "name_first": "⭐ Gói Lite / Reader Năm (9.600 Credits / năm)",
        "name_renew": "⭐ Gói Lite / Reader Năm Gia Hạn (9.600 Credits / năm)",
        "tier_name": "pro",
        "tier_rank": 3,
        "credits": 9_600,
        "duration_days": 365,
        "billing_cycle": "yearly",
        "first_vnd": 890_000,
        "renew_vnd": 1_428_000,
        "first_usd_cents": 5_399,
        "renew_usd_cents": 9_588,
        "is_subscription": True,
        "note_first": "Ưu đãi lần đầu $53.99/năm (890.000đ · gia hạn $95.88 / 1.428.000đ) · 9.600 Credits/năm.",
        "note_renew": "Giá gia hạn $95.88/năm (1.428.000đ) · 9.600 Credits/năm.",
    },
    {
        "code": "studio_yearly",
        "name_first": "💎 Gói Tiêu Chuẩn / Studio + API Năm (36.000 Credits / năm)",
        "name_renew": "💎 Gói Tiêu Chuẩn / Studio + API Năm Gia Hạn (36.000 Credits / năm)",
        "tier_name": "studio",
        "tier_rank": 4,
        "credits": 36_000,
        "duration_days": 365,
        "billing_cycle": "yearly",
        "first_vnd": 1_790_000,
        "renew_vnd": 2_988_000,
        "first_usd_cents": 8_999,
        "renew_usd_cents": 17_988,
        "is_subscription": True,
        "note_first": "Ưu đãi lần đầu $89.99/năm (1.790.000đ · gia hạn $179.88 / 2.988.000đ) · 36.000 Credits + API.",
        "note_renew": "Giá gia hạn $179.88/năm (2.988.000đ) · 36.000 Credits + API.",
    },
    {
        "code": "unlimited_yearly",
        "name_first": "🏢 Gói Pro Max API Năm (120.000 Credits / năm)",
        "name_renew": "🏢 Gói Pro Max API Năm Gia Hạn (120.000 Credits / năm)",
        "tier_name": "unlimited",
        "tier_rank": 5,
        "credits": 120_000,
        "duration_days": 365,
        "billing_cycle": "yearly",
        "first_vnd": 3_590_000,
        "renew_vnd": 5_988_000,
        "first_usd_cents": 17_999,
        "renew_usd_cents": 35_988,
        "is_subscription": True,
        "note_first": "Ưu đãi lần đầu $179.99/năm (3.590.000đ · gia hạn $359.88 / 5.988.000đ) · 120.000 Credits + Full API.",
        "note_renew": "Giá gia hạn $359.88/năm (5.988.000đ) · 120.000 Credits + Full API.",
    },
)


def catalog(
    *,
    da_tung_nap: bool = False,
    don_gia_vnd: int = 500,
    overrides: dict[str, dict[str, int]] | None = None,
    include_legacy_packs: bool = True,
) -> list[PlanCatalogItem]:
    """Một nguồn giá duy nhất cho Pricing UI, tạo đơn, Checkout, và đối soát chuyển khoản.
    Mọi số tiền trả về đều là số nguyên ở đơn vị nhỏ nhất (`VND` đồng, `USD` cent).
    """
    don_gia = max(1, int(don_gia_vnd or 500))
    ovr = overrides if isinstance(overrides, dict) else {}
    items: list[PlanCatalogItem] = []

    for p in _BASE_PLANS:
        code = p["code"]
        plan_ovr = ovr.get(code) if isinstance(ovr.get(code), dict) else {}
        first_vnd = int(plan_ovr.get("first_vnd") or p["first_vnd"])
        renew_vnd = int(plan_ovr.get("renew_vnd") or p["renew_vnd"])
        first_usd = int(plan_ovr.get("first_usd_cents") or p["first_usd_cents"])
        renew_usd = int(plan_ovr.get("renew_usd_cents") or p["renew_usd_cents"])

        use_vnd = renew_vnd if da_tung_nap else first_vnd
        use_usd = renew_usd if da_tung_nap else first_usd
        items.append(
            PlanCatalogItem(
                code=code,
                name=p["name_renew"] if da_tung_nap else p["name_first"],
                tier_name=p["tier_name"],
                tier_rank=int(p["tier_rank"]),
                credits=int(p["credits"]),
                duration_days=int(p["duration_days"]),
                billing_cycle=p["billing_cycle"],
                amount_vnd=use_vnd,
                amount_usd_cents=use_usd,
                original_vnd=renew_vnd,
                original_usd_cents=renew_usd,
                is_first_time_promo=(not da_tung_nap) and (first_vnd < renew_vnd or first_usd < renew_usd),
                is_subscription=bool(p["is_subscription"]),
                note=p["note_renew"] if da_tung_nap else p["note_first"],
            )
        )

    if include_legacy_packs:
        legacy_defs = (
            ("goi_moi", "🎯 Gói Mồi Trải Nghiệm — Đọc Nhanh (40 trang)", "trial", 1, 40, 30, 40 * don_gia, 99, "Gói nhỏ đọc trọn ~2 chapter. Mua nhiều lần tự động cộng dồn."),
            ("co_ban", "🌱 Gói Khởi Đầu — Starter (115 trang)", "starter", 2, 115, 30, 110 * don_gia, 249, "Tặng thêm +5% số trang (~6 chapter)."),
            ("tieu_chuan", "🔥 Gói Độc Giả VIP — Reader (550 trang)", "pro", 3, 550, 30, 500 * don_gia, 1_099, "Tặng thêm 10% số trang (~28 chapter)."),
            ("nhom_dich", "🎬 Gói Nhóm Dịch / Studio (1.200 trang)", "studio", 4, 1_200, 30, 1_000 * don_gia, 2_199, "Tặng thêm 20% số trang (~60 chapter)."),
            ("pack_2000", "🔥 Gói Tích Luỹ 2.000 Trang", "studio", 4, 2_000, 365, 600_000, 2_599, "Gói Credits 600.000đ nhận 2.000 trang tích luỹ."),
            ("doanh_nghiep_api", "🏢 Gói Doanh Nghiệp / Web Truyện API Pro (6.500 trang)", "unlimited", 5, 6_500, 365, 5_000 * don_gia, 10_999, "Mở toàn bộ Developer REST API (tr_live_...)."),
            ("enterprise_scale", "🏛️ Gói Doanh Nghiệp Lớn / Cổng Truyện (28.000 trang)", "unlimited", 5, 28_000, 365, 20_000 * don_gia, 42_999, "Dành cho hệ thống web truyện lớn & tool tự động hoá 24/7."),
        )
        for code, name, t_name, t_rank, creds, days, vnd, usd_c, note in legacy_defs:
            items.append(
                PlanCatalogItem(
                    code=code,
                    name=name,
                    tier_name=t_name,
                    tier_rank=t_rank,
                    credits=creds,
                    duration_days=days,
                    billing_cycle="one_time",
                    amount_vnd=int(vnd),
                    amount_usd_cents=int(usd_c),
                    original_vnd=int(vnd),
                    original_usd_cents=int(usd_c),
                    is_first_time_promo=False,
                    is_subscription=False,
                    note=note,
                )
            )
    return items


def find_duplicate_vnd_prices(items: list[PlanCatalogItem], tolerance_vnd: int = 1000) -> list[tuple[str, str, int, int]]:
    """Phát hiện hai gói có giá VNĐ trùng hoặc nằm trong sai số chuyển khoản (`<= tolerance_vnd`)."""
    dups: list[tuple[str, str, int, int]] = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            if abs(int(a.amount_vnd) - int(b.amount_vnd)) <= tolerance_vnd:
                dups.append((a.code, b.code, int(a.amount_vnd), int(b.amount_vnd)))
    return dups


def match_exact_single_plan_by_vnd(
    amount_vnd: int,
    items: list[PlanCatalogItem],
    *,
    tolerance_vnd: int = 1000,
) -> PlanCatalogItem | None:
    """Khớp chuyển khoản không qua đơn (§3.1):
    CHỈ trả về gói khi `amount_vnd` đúng bằng giá của ĐÚNG MỘT gói (`sai lệch <= 1.000đ`).
    Nếu không khớp hoặc có >= 2 gói trùng vùng giá -> trả `None` để chuyển sang duyệt tay.
    TUYỆT ĐỐI không bao giờ "chọn gói cao nhất mà số tiền đủ trả".
    """
    if amount_vnd <= 0:
        return None
    exact_matches = [it for it in items if int(it.amount_vnd) == int(amount_vnd)]
    near_matches = [it for it in items if abs(int(it.amount_vnd) - int(amount_vnd)) <= tolerance_vnd]
    if len(near_matches) == 1:
        return near_matches[0]
    if len(exact_matches) == 1 and len(near_matches) > 1:
        # Kể cả khớp tuyệt đối 1 gói nhưng có gói khác sát bên <= 1.000đ cũng coi là vùng giá mơ hồ
        return None
    return None


async def has_prior_paid_purchase(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
    email: str | None = None,
) -> bool:
    """Suy cờ 'đã mua lần đầu' trực tiếp từ CSDL (§4 & §9).
    Fail-closed: nếu CSDL lỗi -> trả `True` (coi như KHÔNG phải lần đầu, không bán nhầm giá khuyến mãi).
    """
    try:
        if user_id is not None:
            q_order = (
                select(PaymentOrder.id)
                .where(
                    PaymentOrder.user_id == user_id,
                    PaymentOrder.status == "paid",
                    PaymentOrder.plan != "goi_moi",
                )
                .limit(1)
            )
            if (await session.execute(q_order)).first() is not None:
                return True

            u = await session.get(NguoiDung, user_id)
            if u is not None and int(getattr(u, "cap_do_goi", 0) or 0) > 0:
                return True

        clean_email = (email or "").strip().lower()
        if clean_email:
            q_order_email = (
                select(PaymentOrder.id)
                .where(
                    func.lower(PaymentOrder.email) == clean_email,
                    PaymentOrder.status == "paid",
                    PaymentOrder.plan != "goi_moi",
                )
                .limit(1)
            )
            if (await session.execute(q_order_email)).first() is not None:
                return True

            q_legacy = (
                select(DonNapLuot.id)
                .where(
                    func.lower(DonNapLuot.email) == clean_email,
                    DonNapLuot.trang_thai.in_(("da_xac_nhan", "da_cong_tu_dong")),
                    DonNapLuot.ma_goi != "goi_moi",
                )
                .limit(1)
            )
            if (await session.execute(q_legacy)).first() is not None:
                return True
        return False
    except Exception as exc:
        logger.error("Không kiểm tra được lịch sử mua từ CSDL (fail-closed -> không cấp giá lần đầu): %s", exc)
        return True


# ---------------------------------------------------------------------------
# 5. Xác minh Chữ ký Cổng thanh toán (§3.1, §3.2, §3.3, §6)
# ---------------------------------------------------------------------------


def compute_sepay_hmac(raw_body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


def verify_sepay_signature(
    raw_body: bytes,
    headers: dict[str, str] | Any,
    secrets_list: list[str],
    *,
    allow_apikey: bool = False,
    max_skew_seconds: int = 300,
    now_ts: int | None = None,
) -> tuple[bool, str]:
    """Xác minh chữ ký webhook SePay trên `raw_body` bằng `hmac.compare_digest` hằng thời gian.
    Hỗ trợ xoay 2 secret (`*_SECRET` và `*_SECRET_PREVIOUS`).
    """
    valid_secrets = [s.strip() for s in secrets_list if s and s.strip()]
    if not valid_secrets:
        return False, "missing_secret_config"

    get_hdr = lambda k: (headers.get(k) or headers.get(k.lower()) or "").strip()
    ts_raw = get_hdr("x-sepay-timestamp") or get_hdr("x-timestamp") or get_hdr("x-webhook-timestamp")
    cur_now = int(now_ts if now_ts is not None else time.time())
    if ts_raw:
        try:
            ts_int = int(ts_raw)
        except ValueError:
            return False, "invalid_timestamp"
        if abs(cur_now - ts_int) > max_skew_seconds:
            return False, "timestamp_skew"

    sig_hdr = (
        get_hdr("x-sepay-signature")
        or get_hdr("x-webhook-signature")
        or get_hdr("x-signature")
    )
    if sig_hdr:
        # Hỗ trợ cả `t=...,v1=...`, `sha256=<hex>`, `<hex>` và `<base64>`
        candidates: list[str] = []
        if "v1=" in sig_hdr and "," in sig_hdr:
            parts = dict(
                p.split("=", 1) for p in sig_hdr.split(",") if "=" in p
            )
            if "t" in parts:
                try:
                    t_val = int(parts["t"].strip())
                except ValueError:
                    return False, "invalid_timestamp"
                if abs(cur_now - t_val) > max_skew_seconds:
                    return False, "timestamp_skew"
                signed_payload = f"{t_val}.".encode("utf-8") + raw_body
                for sec in valid_secrets:
                    expected_t = hmac.new(sec.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
                    if hmac.compare_digest(expected_t, parts["v1"].strip().lower()):
                        return True, "hmac_timestamped"
            candidates.append(parts.get("v1", "").strip())
        else:
            cleaned_sig = re.sub(r"^sha256=", "", sig_hdr, flags=re.IGNORECASE).strip()
            candidates.append(cleaned_sig)

        payload_variants = [raw_body]
        if ts_raw:
            payload_variants.append(f"{ts_raw}.".encode("utf-8") + raw_body)

        for cand in candidates:
            if not cand:
                continue
            for sec in valid_secrets:
                for p_bytes in payload_variants:
                    digest_bytes = hmac.new(sec.encode("utf-8"), p_bytes, hashlib.sha256).digest()
                    expected_hex = digest_bytes.hex()
                    expected_b64 = base64.b64encode(digest_bytes).decode("ascii")
                    if hmac.compare_digest(cand.lower(), expected_hex.lower()) or hmac.compare_digest(cand, expected_b64):
                        return True, "hmac_sha256"
        return False, "signature_mismatch"

    if allow_apikey:
        auth = get_hdr("authorization") or get_hdr("x-webhook-secret")
        auth_clean = re.sub(r"^(apikey|bearer|token)\s+", "", auth, flags=re.IGNORECASE).strip()
        if auth_clean:
            for sec in valid_secrets:
                if hmac.compare_digest(auth_clean.encode("utf-8"), sec.encode("utf-8")):
                    return True, "apikey"
            return False, "invalid_apikey"

    return False, "missing_signature"


def compute_stripe_signature(raw_body: bytes, secret: str, timestamp: int | None = None) -> str:
    ts = int(timestamp if timestamp is not None else time.time())
    signed_payload = f"{ts}.".encode("utf-8") + raw_body
    sig = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def verify_stripe_signature(
    raw_body: bytes,
    sig_header: str | None,
    secrets_list: list[str],
    *,
    max_skew_seconds: int = 300,
    now_ts: int | None = None,
) -> tuple[bool, str]:
    """Xác minh chữ ký `Stripe-Signature` chuẩn (`t=...,v1=...`) trên `raw_body`."""
    valid_secrets = [s.strip() for s in secrets_list if s and s.strip()]
    if not valid_secrets:
        return False, "missing_secret_config"
    if not sig_header or not sig_header.strip():
        return False, "missing_signature"

    timestamp_val: int | None = None
    v1_sigs: list[str] = []
    for item in sig_header.split(","):
        if "=" not in item:
            continue
        k, v = item.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k == "t":
            try:
                timestamp_val = int(v)
            except ValueError:
                return False, "invalid_timestamp"
        elif k == "v1" and v:
            v1_sigs.append(v)

    if timestamp_val is None or not v1_sigs:
        return False, "malformed_signature"

    cur_now = int(now_ts if now_ts is not None else time.time())
    if abs(cur_now - timestamp_val) > max_skew_seconds:
        return False, "timestamp_skew"

    signed_payload = f"{timestamp_val}.".encode("utf-8") + raw_body
    for sec in valid_secrets:
        expected = hmac.new(sec.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
        for cand in v1_sigs:
            if hmac.compare_digest(expected.lower(), cand.lower()):
                return True, "stripe_v1"
    return False, "signature_mismatch"


# ---------------------------------------------------------------------------
# 6. Idempotency Fail-Closed (`claim_event` & `finalize_event`) (§1.3, §12.2)
# ---------------------------------------------------------------------------


def is_unique_violation(exc: BaseException) -> bool:
    """Kiểm đúng mã lỗi SQLSTATE `23505` / `UniqueViolationError` của Postgres,
    TUYỆT ĐỐI không so chuỗi lỏng lẻo `'unique' in str(exc)` (§11).
    """
    orig = getattr(exc, "orig", None)
    for target in (exc, orig, getattr(orig, "__cause__", None)):
        if target is None:
            continue
        sqlstate = getattr(target, "sqlstate", None) or getattr(target, "pgcode", None)
        if sqlstate == "23505":
            return True
        cls_name = type(target).__name__
        if cls_name in ("UniqueViolationError", "UniqueViolation"):
            return True
    return False


async def claim_event(
    session: AsyncSession,
    provider: str,
    provider_event_id: str,
    *,
    event_type: str | None = None,
    amount: int | None = None,
    currency: str | None = None,
    raw_payload: dict[str, Any] | None = None,
    legacy_providers: tuple[str, ...] = (),
) -> tuple[str, uuid.UUID | None]:
    """Chiếm chỗ sự kiện trong `payment_events` TRƯỚC mọi thay đổi quyền lợi (§12.2).
    - Trả `("claimed", event_uuid)` nếu ghi thành công.
    - Trả `("duplicate", None)` nếu đụng `UNIQUE(provider, provider_event_id)` (`SQLSTATE 23505`).
    - Ném `HTTPException(503)` nếu kho sự kiện gặp bất kỳ lỗi CSDL nào khác (fail-closed).
    """
    ev_id_clean = (provider_event_id or "").strip()
    prov_clean = (provider or "").strip()
    if not ev_id_clean or not prov_clean:
        raise HTTPException(status_code=400, detail="Missing payment event id")

    try:
        if legacy_providers:
            existing_legacy = (
                await session.execute(
                    select(PaymentEvent.id).where(
                        PaymentEvent.provider.in_(legacy_providers),
                        PaymentEvent.provider_event_id == ev_id_clean,
                    )
                )
            ).scalar_one_or_none()
            if existing_legacy is not None:
                return "duplicate", None

        row_id = uuid.uuid4()
        sanitized = sanitize_payload(raw_payload or {})
        async with session.begin_nested():
            ev = PaymentEvent(
                id=row_id,
                provider=prov_clean[:40],
                provider_event_id=ev_id_clean[:160],
                event_type=(event_type or "")[:96] or None,
                amount=int(amount) if amount is not None else None,
                currency=(currency or "").upper()[:8] or None,
                match_type="claiming",
                processed=False,
                raw_payload=sanitized if isinstance(sanitized, dict) else {"data": sanitized},
            )
            session.add(ev)
            await session.flush()
        await session.commit()
        return "claimed", row_id
    except HTTPException:
        raise
    except Exception as exc:
        if is_unique_violation(exc):
            return "duplicate", None
        logger.error("Kho sự kiện payment_events lỗi (fail-closed 503): %s", exc, exc_info=True)
        await send_payment_alert(
            title="🚨 LỖI KHO SỰ KIỆN THANH TOÁN (503 FAIL-CLOSED)",
            details={
                "provider": prov_clean,
                "provider_event_id": ev_id_clean,
                "error_type": type(exc).__name__,
            },
        )
        raise HTTPException(status_code=503, detail="Payment event store unavailable") from exc


async def finalize_event(
    session: AsyncSession,
    event_row_id: uuid.UUID | None,
    *,
    match_type: str,
    processed: bool = True,
    order_id: uuid.UUID | None = None,
    amount: int | None = None,
    currency: str | None = None,
    error: str | None = None,
) -> None:
    if event_row_id is None:
        return
    values: dict[str, Any] = {
        "match_type": match_type[:40],
        "processed": processed,
        "processed_at": datetime.now(timezone.utc),
    }
    if order_id is not None:
        values["order_id"] = order_id
    if amount is not None:
        values["amount"] = int(amount)
    if currency is not None:
        values["currency"] = currency.upper()[:8]
    if error is not None:
        values["error"] = error[:500]
    await session.execute(update(PaymentEvent).where(PaymentEvent.id == event_row_id).values(**values))
    await session.commit()


# ---------------------------------------------------------------------------
# 7. Cảnh báo Tức thì & Hàng chờ Duyệt tay (§1.5, §7)
# ---------------------------------------------------------------------------


async def send_payment_alert(
    *,
    title: str,
    details: dict[str, Any],
    settings: Settings | None = None,
) -> bool:
    """Gửi cảnh báo thanh toán qua Telegram Bot hoặc Slack/Discord Webhook.
    TUYỆT ĐỐI không bao giờ làm hỏng luồng webhook nếu gửi cảnh báo lỗi (§7 & §9).
    """
    try:
        cfg = resolve_payment_config(settings)
        safe_details = sanitize_payload(details)
        lines = [title]
        if isinstance(safe_details, dict):
            for k, v in safe_details.items():
                if v not in (None, "", {}):
                    lines.append(f"• {k}: {v}")
        text = "\n".join(lines)[:3800]

        sent = False
        bot_token = cfg.get("telegram_bot_token") or ""
        chat_id = cfg.get("telegram_chat_id") or ""
        if bot_token and chat_id:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            async with httpx.AsyncClient(timeout=6.0) as client:
                resp = await client.post(
                    url,
                    json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
                )
                if resp.status_code == 200:
                    sent = True
                else:
                    logger.error(
                        "Cảnh báo Telegram thất bại HTTP %s — kiểm tra lại TELEGRAM_BOT_TOKEN/CHAT_ID!",
                        resp.status_code,
                    )

        wh_url = cfg.get("alert_webhook_url") or ""
        if wh_url:
            async with httpx.AsyncClient(timeout=6.0) as client:
                resp2 = await client.post(wh_url, json={"text": text, "content": text})
                if 200 <= resp2.status_code < 300:
                    sent = True
                else:
                    logger.error("Cảnh báo Webhook thất bại HTTP %s", resp2.status_code)
        return sent
    except Exception as exc:
        logger.error("Gửi cảnh báo thanh toán gặp lỗi (đã nuốt để không làm hỏng webhook): %s", exc)
        return False


async def check_telegram_bot_health(settings: Settings | None = None) -> dict[str, Any]:
    """Kiểm tra `getMe` của bot Telegram sau deploy để phát hiện token 401 hết hạn (§7 & §11)."""
    cfg = resolve_payment_config(settings)
    bot_token = cfg.get("telegram_bot_token") or ""
    chat_id = cfg.get("telegram_chat_id") or ""
    if not bot_token or not chat_id:
        return {"configured": False, "valid": False, "detail": "not_configured"}
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get(f"https://api.telegram.org/bot{bot_token}/getMe")
        if resp.status_code == 200:
            body = resp.json()
            bot_user = (body.get("result") or {}).get("username") or ""
            return {"configured": True, "valid": True, "bot_username": bot_user}
        return {"configured": True, "valid": False, "http_status": resp.status_code, "detail": "invalid_token"}
    except Exception as exc:
        return {"configured": True, "valid": False, "detail": f"network_error:{type(exc).__name__}"}


async def record_review_and_alert(
    session: AsyncSession,
    *,
    provider: str,
    reason: str,
    provider_event_id: str | None = None,
    event_type: str | None = None,
    order: PaymentOrder | None = None,
    user_id: str | None = None,
    user_email: str | None = None,
    order_id: str | None = None,
    order_code: str | None = None,
    current_tier: str | None = None,
    target_tier: str | None = None,
    amount: int | None = None,
    currency: str | None = None,
    raw_payload: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> PaymentReview:
    """Tạo bản ghi hàng chờ duyệt tay (`payment_reviews`) và gửi cảnh báo ngay lập tức."""
    eff_user_id = user_id or (str(order.user_id) if order and order.user_id else (order.owner_ref if order else None))
    eff_email = user_email or (order.email if order else None)
    eff_order_id = order_id or (str(order.id) if order else None)
    eff_order_code = order_code or (order.code if order else None)
    eff_target_tier = target_tier or (RANK_TO_TIER_NAME.get(order.tier_rank, order.plan) if order else None)
    eff_amount = amount if amount is not None else (int(order.amount) if order else None)
    eff_currency = (currency or (order.currency if order else "") or "").upper() or None
    sanitized = sanitize_payload(raw_payload or {})

    review = PaymentReview(
        id=uuid.uuid4(),
        provider=provider[:40],
        provider_event_id=(provider_event_id or "")[:160] or None,
        event_type=(event_type or "")[:96] or None,
        user_id=(eff_user_id or "")[:64] or None,
        user_email=(eff_email or "")[:320] or None,
        order_id=(eff_order_id or "")[:64] or None,
        order_code=(eff_order_code or "")[:32] or None,
        current_tier=(current_tier or "")[:32] or None,
        target_tier=(eff_target_tier or "")[:32] or None,
        amount=int(eff_amount) if eff_amount is not None else None,
        currency=eff_currency[:8] if eff_currency else None,
        status="needs_manual_review",
        reason=reason[:120],
        raw_payload=sanitized if isinstance(sanitized, dict) else {"data": sanitized},
    )
    session.add(review)
    await session.commit()

    await send_payment_alert(
        title=f"⚠️ CẦN DUYỆT TAY THANH TOÁN [{provider.upper()}] — {reason}",
        details={
            "review_id": str(review.id),
            "reason": reason,
            "order_code": eff_order_code,
            "order_id": eff_order_id,
            "user_email": eff_email,
            "amount": f"{eff_amount} {eff_currency or ''}".strip() if eff_amount is not None else "unknown",
            "current_tier": current_tier,
            "target_tier": eff_target_tier,
            "provider_event_id": provider_event_id,
        },
        settings=settings,
    )
    return review


# ---------------------------------------------------------------------------
# 8. Quy tắc Gói & Hàm Cấp Quyền Lợi Duy Nhất `grant()` + `activate_order()` (§4, §12.3)
# ---------------------------------------------------------------------------


def active_paid_profile(nguoi: NguoiDung | None, now: datetime | None = None) -> tuple[int, str, datetime | None]:
    """Trả `(tier_rank, tier_name, expiry)` đang thực sự còn hiệu lực của user."""
    if nguoi is None:
        return 0, "free", None
    cur_now = now or datetime.now(timezone.utc)
    het_han = getattr(nguoi, "het_han_goi", None)
    if het_han is not None and het_han.tzinfo is None:
        het_han = het_han.replace(tzinfo=timezone.utc)

    cap_db = int(getattr(nguoi, "cap_do_goi", 0) or 0)
    vi = int(getattr(nguoi, "so_luot_mua_them", 0) or 0)

    if cap_db > 0 and (het_han is None or het_han > cur_now) and (vi > 0 or getattr(nguoi, "trang_thai_billing", "") == "active"):
        return cap_db, RANK_TO_TIER_NAME.get(cap_db, "starter"), het_han

    # Kiểm thêm giỏ lượt còn hạn trên user cũ (không tính quyền admin vào kiểm chặn hạ gói mua hàng)
    if not getattr(nguoi, "la_quan_tri", False) and vi > 0:
        cap_eff = int(tinh_cap_do(nguoi) or 0)
        if cap_eff > 0 and (het_han is None or het_han > cur_now):
            return cap_eff, RANK_TO_TIER_NAME.get(cap_eff, "starter"), het_han

    return 0, "free", None


def assert_not_downgrade_on_checkout(nguoi: NguoiDung, target_tier_rank: int, now: datetime | None = None) -> None:
    """Chặn mua gói thấp hơn ngay từ lúc tạo đơn / checkout (HTTP 409) (§4 & §9)."""
    cur_rank, cur_name, cur_exp = active_paid_profile(nguoi, now)
    if cur_rank > 0 and int(target_tier_rank) < cur_rank:
        exp_str = cur_exp.strftime("%d/%m/%Y") if cur_exp else "hiện tại"
        raise HTTPException(
            status_code=409,
            detail=(
                f"Tài khoản đang sử dụng gói {TEN_CAP_DO.get(cur_rank, cur_name.upper())} còn hiệu lực "
                f"(đến {exp_str}). Không thể hạ xuống gói thấp hơn khi gói cao còn hạn."
            ),
        )


async def _grant_affiliate_bonus_idempotent(
    session: AsyncSession,
    *,
    buyer_id: uuid.UUID,
    credits: int,
    source_ref: str,
) -> None:
    """Cộng thưởng 15% Affiliate idempotent theo `source_ref` (§4)."""
    if credits <= 0 or not source_ref:
        return
    try:
        from starlette.concurrency import run_in_threadpool
        from app.api.v1.xac_thuc_routes import _doc_so_cai_affiliate, _luu_so_cai_affiliate

        aff_data = await run_in_threadpool(_doc_so_cai_affiliate)
        history = aff_data.setdefault("history", [])
        if any(isinstance(h, dict) and h.get("source_ref") == source_ref for h in history):
            return
        claim_info = (aff_data.get("claims") or {}).get(str(buyer_id))
        if isinstance(claim_info, dict) and claim_info.get("referrer_id"):
            ref_uid = uuid.UUID(str(claim_info["referrer_id"]))
            if ref_uid == buyer_id:
                return
            bonus = max(1, int(round(credits * 0.15)))
            await session.execute(
                update(NguoiDung)
                .where(NguoiDung.id == ref_uid)
                .values(so_luot_mua_them=func.greatest(0, NguoiDung.so_luot_mua_them + bonus))
            )
            history.append(
                {
                    "beneficiary_id": str(ref_uid),
                    "type": "vip_commission_15pct",
                    "bonus_pages": bonus,
                    "source_ref": source_ref,
                    "note": f"Hoa hồng 15% từ {source_ref} (+{credits} trang)",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            await run_in_threadpool(_luu_so_cai_affiliate, aff_data)
    except Exception as exc:
        logger.warning("Thưởng Affiliate không thành (không chặn cấp quyền lợi chính): %s", exc)


async def grant(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    plan_code: str,
    tier_rank: int,
    credits: int,
    duration_days: int,
    source_ref: str,
    allow_admin_override_downgrade: bool = False,
    now: datetime | None = None,
) -> NguoiDung:
    """HÀM CẤP QUYỀN LỢI DUY NHẤT (§4).
    - Kiểm quy tắc không hạ gói khi gói cao còn hạn (`NeedsManualReviewError`).
    - Gia hạn cùng gói -> cộng dồn ngày (`max(now, expiry) + duration_days`).
    - Nâng lên gói cao hơn -> bắt đầu kỳ mới (`now + duration_days`) và thăng hạng ngay.
    - Đồng bộ MỌI nơi lưu gói trong cùng transaction: `nguoi_dung` (`cap_do_goi`, `ma_goi_hien_tai`,
      `het_han_goi`, `trang_thai_billing`, `gio_luot_json`, `so_luot_mua_them`) + cache giỏ + API key.
    """
    cur_now = now or datetime.now(timezone.utc)
    stmt = select(NguoiDung).where(NguoiDung.id == user_id).with_for_update()
    nguoi = (await session.execute(stmt)).scalar_one_or_none()
    if nguoi is None:
        raise LookupError(f"User {user_id} not found")

    target_rank = max(1, min(5, int(tier_rank or 1)))
    cur_rank, _, cur_expiry = active_paid_profile(nguoi, cur_now)

    if not allow_admin_override_downgrade and cur_rank > 0 and target_rank < cur_rank:
        raise NeedsManualReviewError("downgrade_while_higher_tier_active")

    days = max(1, int(duration_days or 30))
    if target_rank == cur_rank and cur_expiry is not None and cur_expiry > cur_now:
        base_dt = max(cur_now, cur_expiry)
    else:
        base_dt = cur_now
    new_expiry = base_dt + timedelta(days=days)
    new_exp_ts = int(new_expiry.timestamp())

    vi_truoc = max(0, int(nguoi.so_luot_mua_them or 0))
    credits_add = max(0, int(credits or 0))
    vi_moi = vi_truoc + credits_add

    # Đồng bộ giỏ lượt theo bậc gói lưu trực tiếp trong `nguoi_dung.gio_luot_json`
    now_ts = int(cur_now.timestamp())
    gio_cu = list(nguoi.gio_luot_json) if isinstance(nguoi.gio_luot_json, list) else []
    gio_sach: list[dict[str, int]] = []
    for item in gio_cu:
        if not isinstance(item, dict):
            continue
        c = max(1, min(5, int(item.get("cap", 1) or 1)))
        tr = max(0, int(item.get("trang", 0) or 0))
        exp_i = int(item.get("het_han_ts", 0) or 0)
        if exp_i > 0 and now_ts > exp_i:
            continue
        if tr > 0:
            gio_sach.append({"cap": c, "trang": tr, "het_han_ts": exp_i} if exp_i > 0 else {"cap": c, "trang": tr})
    gio_sach.sort(key=lambda x: x["cap"], reverse=True)

    # Khấu trừ phần đã tiêu trước đó vào giỏ trước khi cộng giỏ mới
    tong_gio = sum(x["trang"] for x in gio_sach)
    if tong_gio > vi_truoc:
        can_tru = tong_gio - vi_truoc
        gio_da_tru: list[dict[str, int]] = []
        for item in gio_sach:
            if can_tru > 0:
                t_m = min(item["trang"], can_tru)
                con = item["trang"] - t_m
                can_tru -= t_m
                if con > 0:
                    rec = {"cap": item["cap"], "trang": con}
                    if item.get("het_han_ts"):
                        rec["het_han_ts"] = item["het_han_ts"]
                    gio_da_tru.append(rec)
            else:
                gio_da_tru.append(item)
        gio_sach = gio_da_tru
    elif vi_truoc > 0 and not gio_sach and cur_rank > 0:
        gio_sach = [{"cap": cur_rank, "trang": vi_truoc, "het_han_ts": int((cur_expiry or cur_now).timestamp())}]

    if credits_add > 0:
        merged = False
        for item in gio_sach:
            if item["cap"] == target_rank:
                item["trang"] += credits_add
                item["het_han_ts"] = max(int(item.get("het_han_ts", 0) or 0), new_exp_ts)
                merged = True
                break
        if not merged:
            gio_sach.append({"cap": target_rank, "trang": credits_add, "het_han_ts": new_exp_ts})
    gio_sach.sort(key=lambda x: x["cap"], reverse=True)
    effective_rank = max(target_rank, gio_sach[0]["cap"] if gio_sach else target_rank)

    nguoi.so_luot_mua_them = vi_moi
    nguoi.cap_do_goi = effective_rank
    nguoi.ma_goi_hien_tai = plan_code[:64]
    nguoi.het_han_goi = new_expiry
    nguoi.trang_thai_billing = "active"
    nguoi.gio_luot_json = gio_sach
    await session.flush()

    # Đồng bộ cả bộ nhớ đệm phụ `danh_tinh_khach` để không bao giờ lệch giữa 2 đường đọc
    try:
        from starlette.concurrency import run_in_threadpool
        from app.core.danh_tinh_khach import ghi_nhan_cap_do_goi_mua

        await run_in_threadpool(ghi_nhan_cap_do_goi_mua, nguoi.id, plan_code, credits_add, vi_truoc)
    except Exception:
        pass

    # Tự động khởi tạo Developer API Key (`tr_live_...`) cho gói Studio (Cấp 4) & Unlimited (Cấp 5)
    if effective_rank >= 4 or credits_add >= 3000:
        try:
            from app.services import tai_khoan as _tk_auto

            existing_key = await _tk_auto.lay_thong_tin_api_key(session, nguoi.id)
            if existing_key is None:
                await _tk_auto.tao_moi_api_key(session, nguoi.id)
        except Exception as exc:
            logger.warning("Không tự khởi tạo được API key cho %s: %s", nguoi.id, exc)

    # Thưởng giới thiệu 15% chạy sau khi cấp quyền lợi chính, idempotent theo `source_ref`
    await _grant_affiliate_bonus_idempotent(
        session,
        buyer_id=nguoi.id,
        credits=credits_add,
        source_ref=source_ref,
    )
    return nguoi


async def _set_order_status_and_review(
    session: AsyncSession,
    *,
    order: PaymentOrder,
    new_status: str,
    reason: str,
    provider: str,
    provider_event_id: str | None,
    paid_amount: int | None,
    currency: str | None,
    provider_ref: str | None,
    evidence: dict[str, Any] | None,
    current_tier: str | None = None,
    settings: Settings | None = None,
) -> tuple[bool, str]:
    now_dt = datetime.now(timezone.utc)
    sanitized_ev = sanitize_payload(evidence or {})
    cas = await session.execute(
        update(PaymentOrder)
        .where(PaymentOrder.id == order.id, PaymentOrder.status == "pending")
        .values(
            status=new_status,
            paid_amount=int(paid_amount) if paid_amount is not None else order.paid_amount,
            paid_at=now_dt if paid_amount else order.paid_at,
            provider_ref=provider_ref or order.provider_ref,
            evidence=sanitized_ev if isinstance(sanitized_ev, dict) else {},
            admin_note=reason[:500],
            updated_at=now_dt,
        )
        .returning(PaymentOrder.id)
    )
    if cas.first() is None:
        return False, "concurrent_status_change"
    await record_review_and_alert(
        session,
        provider=provider,
        reason=reason,
        provider_event_id=provider_event_id,
        order=order,
        current_tier=current_tier,
        amount=paid_amount,
        currency=currency,
        raw_payload=sanitized_ev if isinstance(sanitized_ev, dict) else {},
        settings=settings,
    )
    return False, new_status


async def activate_order(
    session: AsyncSession,
    *,
    order_id: uuid.UUID,
    paid_amount: int,
    currency: str,
    provider: str,
    provider_event_id: str | None = None,
    provider_ref: str | None = None,
    evidence: dict[str, Any] | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
    grant_fn: Any = None,
) -> tuple[bool, str]:
    """Kích hoạt đơn chuẩn §12.3:
    5 phép kiểm -> Compare-And-Set `pending -> paid` -> `grant()` -> nếu `grant()` lỗi thì
    chuyển đơn sang `needs_manual_review` (`activated_at=None`) + hàng chờ duyệt tay + cảnh báo!
    """
    cur_now = now or datetime.now(timezone.utc)
    order = await session.get(PaymentOrder, order_id)
    if order is None:
        await record_review_and_alert(
            session,
            provider=provider,
            reason="order_not_found",
            provider_event_id=provider_event_id,
            order_id=str(order_id),
            amount=paid_amount,
            currency=currency,
            raw_payload=evidence,
            settings=settings,
        )
        return False, "order_not_found"

    if order.status != "pending":
        # Nếu cùng một provider_ref (ví dụ capture thành công rồi webhook PAYMENT.CAPTURE.COMPLETED tới sau)
        # thì coi là đã kích hoạt hợp lệ, không bắn cảnh báo giả!
        if order.status == "paid" and provider_ref and order.provider_ref == provider_ref:
            return False, "order_already_paid"
        # Nếu khách chuyển khoản lần 2 vào đơn đã paid / canceled / expired -> phải đưa vào duyệt tay!
        await record_review_and_alert(
            session,
            provider=provider,
            reason=f"order_not_pending:{order.status}",
            provider_event_id=provider_event_id,
            order=order,
            amount=paid_amount,
            currency=currency,
            raw_payload=evidence,
            settings=settings,
        )
        return False, f"order_already_{order.status}"

    if (currency or "").strip().upper() != (order.currency or "").strip().upper():
        return await _set_order_status_and_review(
            session,
            order=order,
            new_status="needs_manual_review",
            reason="currency_mismatch",
            provider=provider,
            provider_event_id=provider_event_id,
            paid_amount=paid_amount,
            currency=currency,
            provider_ref=provider_ref,
            evidence=evidence,
            settings=settings,
        )

    exp_dt = order.expires_at
    if exp_dt is not None:
        if exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
        if cur_now > exp_dt:
            return await _set_order_status_and_review(
                session,
                order=order,
                new_status="expired_late_payment",
                reason="expired_late_payment",
                provider=provider,
                provider_event_id=provider_event_id,
                paid_amount=paid_amount,
                currency=currency,
                provider_ref=provider_ref,
                evidence=evidence,
                settings=settings,
            )

    if int(paid_amount) < int(order.amount):
        return await _set_order_status_and_review(
            session,
            order=order,
            new_status="underpaid",
            reason="underpaid",
            provider=provider,
            provider_event_id=provider_event_id,
            paid_amount=paid_amount,
            currency=currency,
            provider_ref=provider_ref,
            evidence=evidence,
            settings=settings,
        )

    if order.user_id is None:
        return await _set_order_status_and_review(
            session,
            order=order,
            new_status="needs_manual_review",
            reason="order_missing_user",
            provider=provider,
            provider_event_id=provider_event_id,
            paid_amount=paid_amount,
            currency=currency,
            provider_ref=provider_ref,
            evidence=evidence,
            settings=settings,
        )

    nguoi_check = await session.get(NguoiDung, order.user_id)
    cur_rank, cur_tier_name, _ = active_paid_profile(nguoi_check, cur_now)
    if cur_rank > 0 and int(order.tier_rank) < cur_rank:
        return await _set_order_status_and_review(
            session,
            order=order,
            new_status="needs_manual_review",
            reason="downgrade_while_higher_tier_active",
            provider=provider,
            provider_event_id=provider_event_id,
            paid_amount=paid_amount,
            currency=currency,
            provider_ref=provider_ref,
            evidence=evidence,
            current_tier=cur_tier_name,
            settings=settings,
        )

    overpaid_diff = int(paid_amount) - int(order.amount)
    sanitized_ev = sanitize_payload(evidence or {})
    if not isinstance(sanitized_ev, dict):
        sanitized_ev = {"data": sanitized_ev}
    if overpaid_diff > 0:
        sanitized_ev["overpaid_minor_units"] = overpaid_diff
    note_paid = f"overpaid:{overpaid_diff}" if overpaid_diff > 0 else None

    # Compare-And-Set nguyên tử: chỉ ĐÚNG MỘT tiến trình thắng `pending -> paid`!
    cas = await session.execute(
        update(PaymentOrder)
        .where(PaymentOrder.id == order.id, PaymentOrder.status == "pending")
        .values(
            status="paid",
            paid_amount=int(paid_amount),
            paid_at=cur_now,
            activated_at=cur_now,
            provider_ref=provider_ref or order.provider_ref,
            evidence=sanitized_ev,
            admin_note=note_paid,
            updated_at=cur_now,
        )
        .returning(PaymentOrder.id)
    )
    if cas.first() is None:
        return False, "concurrent_activation"
    await session.commit()

    # Bước cấp quyền lợi bọc trong SAVEPOINT riêng để nếu `grant()` lỗi sau CAS,
    # đơn lập tức lùi sang `needs_manual_review` (`activated_at=None`) + cảnh báo (§12.3)!
    actual_grant = grant_fn or grant
    try:
        async with session.begin_nested():
            nguoi_updated = await actual_grant(
                session,
                user_id=order.user_id,
                plan_code=order.plan,
                tier_rank=order.tier_rank,
                credits=order.credits,
                duration_days=order.duration_days,
                source_ref=f"order_{order.id}",
                now=cur_now,
            )
            # Ghi bản ghi đối chiếu sang sổ `don_nap_luot` để trang thống kê Admin thấy chung lịch sử
            vnd_equiv = (
                int(paid_amount)
                if order.currency.upper() == "VND"
                else int(Decimal(int(paid_amount)) * Decimal(250))  # ~25.000đ / 100 cent
            )
            tx_key = f"{provider}:{provider_ref or provider_event_id or order.code}"[:128]
            existing_don = (
                await session.execute(
                    select(DonNapLuot.id).where(
                        sa.or_(
                            DonNapLuot.ma_don == order.code,
                            DonNapLuot.ma_giao_dich_ngan_hang == tx_key,
                        )
                    )
                )
            ).first()
            if existing_don is None:
                session.add(
                    DonNapLuot(
                        ma_don=order.code[:32],
                        nguoi_dung_id=order.user_id,
                        email=nguoi_updated.email,
                        ten_hien=nguoi_updated.ten_hien,
                        ma_goi=order.plan[:60],
                        ten_goi=f"{order.plan} ({order.rail.upper()})"[:160],
                        so_tien_vnd=vnd_equiv,
                        so_trang_cong=order.credits,
                        noi_dung_chuyen_khoan=f"{order.code} [{order.rail.upper()}]",
                        trang_thai="da_cong_tu_dong",
                        ma_giao_dich_ngan_hang=tx_key,
                        duyet_luc=cur_now,
                    )
                )
            else:
                await session.execute(
                    update(DonNapLuot)
                    .where(DonNapLuot.ma_don == order.code)
                    .values(
                        trang_thai="da_cong_tu_dong",
                        ma_giao_dich_ngan_hang=tx_key,
                        duyet_luc=cur_now,
                    )
                )
            await session.flush()
        await session.commit()
        return True, "activated"
    except Exception as exc:
        logger.error("grant() thất bại sau CAS cho đơn %s: %s", order.code, exc, exc_info=True)
        reason_err = (
            exc.reason if isinstance(exc, NeedsManualReviewError) else f"grant_failed:{type(exc).__name__}"
        )
        await session.execute(
            update(PaymentOrder)
            .where(PaymentOrder.id == order.id)
            .values(
                status="needs_manual_review",
                activated_at=None,
                admin_note=reason_err[:500],
                updated_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()
        await record_review_and_alert(
            session,
            provider=provider,
            reason="grant_failed_after_paid" if not isinstance(exc, NeedsManualReviewError) else exc.reason,
            provider_event_id=provider_event_id,
            order=order,
            current_tier=cur_tier_name,
            amount=paid_amount,
            currency=currency,
            raw_payload={"error": type(exc).__name__, "evidence": sanitized_ev},
            settings=settings,
        )
        return False, "needs_manual_review"


# ---------------------------------------------------------------------------
# 9. Tạo đơn nội bộ có Rate-limit & Giới hạn Pending (§2, §3.1)
# ---------------------------------------------------------------------------


async def create_payment_order(
    session: AsyncSession,
    *,
    nguoi: NguoiDung,
    plan_code: str,
    rail: str,
    settings: Settings | None = None,
) -> tuple[PaymentOrder, PlanCatalogItem]:
    """Tạo đơn hàng nội bộ chốt giá nguyên ở đơn vị nhỏ nhất, kiểm chặn hạ gói (409)
    và giới hạn tối đa N đơn pending mỗi tài khoản.
    """
    st = settings or get_settings()
    rail_clean = (rail or "").strip().lower()
    if rail_clean not in ("vietqr", "stripe", "paypal"):
        raise HTTPException(status_code=422, detail="Kênh thanh toán phải là 'vietqr', 'stripe' hoặc 'paypal'.")

    cfg = resolve_payment_config(st)
    da_tung_nap = await has_prior_paid_purchase(session, user_id=nguoi.id, email=nguoi.email)
    items = catalog(
        da_tung_nap=da_tung_nap,
        don_gia_vnd=st.ty_le_vnd_moi_trang,
        overrides=cfg.get("price_overrides"),
    )
    plan_map = {it.code: it for it in items}
    item = plan_map.get((plan_code or "").strip())
    if item is None:
        raise HTTPException(
            status_code=422,
            detail="Mã gói cước không hợp lệ. Chỉ chấp nhận các gói chính thức trong catalog.",
        )

    now_dt = datetime.now(timezone.utc)
    # 1. Chặn hạ gói ngay lúc tạo đơn / checkout (HTTP 409)
    assert_not_downgrade_on_checkout(nguoi, item.tier_rank, now_dt)

    # 2. Tự động đánh dấu hết hạn các đơn pending cũ đã quá TTL của chính user này
    await session.execute(
        update(PaymentOrder)
        .where(
            PaymentOrder.user_id == nguoi.id,
            PaymentOrder.status == "pending",
            PaymentOrder.expires_at.is_not(None),
            PaymentOrder.expires_at <= now_dt,
        )
        .values(status="expired", updated_at=now_dt)
    )

    currency = "VND" if rail_clean == "vietqr" else "USD"
    locked_amount = int(item.amount_vnd if currency == "VND" else item.amount_usd_cents)

    # Nếu đã có đơn pending cùng gói + cùng kênh + cùng số tiền còn hạn dài (> 30 phút) và chưa gắn ref cổng ngoài -> tái sử dụng
    if rail_clean == "vietqr":
        existing_same = (
            await session.execute(
                select(PaymentOrder)
                .where(
                    PaymentOrder.user_id == nguoi.id,
                    PaymentOrder.status == "pending",
                    PaymentOrder.plan == item.code,
                    PaymentOrder.rail == rail_clean,
                    PaymentOrder.amount == locked_amount,
                    PaymentOrder.expires_at > now_dt + timedelta(minutes=30),
                )
                .order_by(PaymentOrder.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing_same is not None:
            return existing_same, item

    # 3. Rate-limit tạo đơn (tối đa 10 đơn mới trong 10 phút / user)
    recent_count = int(
        (
            await session.execute(
                select(func.count(PaymentOrder.id)).where(
                    PaymentOrder.user_id == nguoi.id,
                    PaymentOrder.created_at >= now_dt - timedelta(minutes=10),
                )
            )
        ).scalar()
        or 0
    )
    if recent_count >= 10:
        raise HTTPException(
            status_code=429,
            detail="Bạn vừa tạo quá nhiều đơn thanh toán liên tiếp. Vui lòng đợi ít phút hoặc huỷ đơn cũ.",
        )

    # 4. Giới hạn tối đa N đơn `pending` mỗi user (mặc định 3)
    max_pending = max(1, int(st.payment_max_pending_orders_per_user or 3))
    pending_count = int(
        (
            await session.execute(
                select(func.count(PaymentOrder.id)).where(
                    PaymentOrder.user_id == nguoi.id,
                    PaymentOrder.status == "pending",
                )
            )
        ).scalar()
        or 0
    )
    if pending_count >= max_pending:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Bạn đang có {pending_count} đơn chờ thanh toán (tối đa {max_pending} đơn cùng lúc). "
                "Vui lòng hoàn tất hoặc huỷ bớt đơn cũ trước khi tạo đơn mới."
            ),
        )

    ttl_hours = max(1, int(st.payment_order_ttl_hours or 24))
    expires_at = now_dt + timedelta(hours=ttl_hours)

    order: PaymentOrder | None = None
    for _ in range(5):
        code = generate_order_code()
        candidate = PaymentOrder(
            id=uuid.uuid4(),
            user_id=nguoi.id,
            owner_ref=str(nguoi.id),
            email=nguoi.email,
            plan=item.code,
            tier_rank=item.tier_rank,
            credits=item.credits,
            duration_days=item.duration_days,
            rail=rail_clean,
            currency=currency,
            amount=locked_amount,
            code=code,
            status="pending",
            expires_at=expires_at,
        )
        try:
            async with session.begin_nested():
                session.add(candidate)
                await session.flush()
            order = candidate
            break
        except Exception as exc:
            if is_unique_violation(exc):
                continue
            raise
    if order is None:
        raise HTTPException(status_code=503, detail="Không sinh được mã đơn duy nhất, vui lòng thử lại.")

    await session.commit()
    await session.refresh(order)
    return order, item


# ---------------------------------------------------------------------------
# 10. Adapter Cổng Quốc tế: Stripe Checkout & PayPal Orders v2 (§3.2, §3.3, §12.4)
# ---------------------------------------------------------------------------


async def create_stripe_checkout_session(
    *,
    order: PaymentOrder,
    item: PlanCatalogItem,
    success_url: str,
    cancel_url: str,
    settings: Settings | None = None,
) -> dict[str, str]:
    """Tạo Stripe Checkout Session trực tiếp từ server với `metadata={user_id, plan, order_id}`."""
    cfg = resolve_payment_config(settings)
    secret_key = cfg.get("stripe_secret_key") or ""
    wh_secrets = cfg.get("stripe_webhook_secrets") or []
    if not secret_key or not wh_secrets:
        raise HTTPException(status_code=503, detail="Cổng thanh toán thẻ quốc tế Stripe hiện đang tạm tắt.")

    price_map: dict[str, str] = cfg.get("stripe_price_map") or {}
    configured_price_id = price_map.get(item.code, "")

    form_data: dict[str, str] = {
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": str(order.id),
        "customer_email": order.email,
        "metadata[user_id]": str(order.user_id or order.owner_ref),
        "metadata[plan]": order.plan,
        "metadata[order_id]": str(order.id),
        "metadata[order_code]": order.code,
        "line_items[0][quantity]": "1",
    }

    if configured_price_id:
        mode = "subscription" if item.is_subscription else "payment"
        form_data["mode"] = mode
        form_data["line_items[0][price]"] = configured_price_id
        if mode == "subscription":
            form_data["subscription_data[metadata][user_id]"] = str(order.user_id or order.owner_ref)
            form_data["subscription_data[metadata][plan]"] = order.plan
            form_data["subscription_data[metadata][order_id]"] = str(order.id)
    else:
        form_data["mode"] = "payment"
        form_data["line_items[0][price_data][currency]"] = order.currency.lower()
        form_data["line_items[0][price_data][unit_amount]"] = str(int(order.amount))
        form_data["line_items[0][price_data][product_data][name]"] = item.name
        form_data["line_items[0][price_data][product_data][description]"] = (
            f"{item.credits} Credits · Mã đơn {order.code}"
        )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.stripe.com/v1/checkout/sessions",
                data=form_data,
                headers={
                    "Authorization": f"Bearer {secret_key}",
                    "Idempotency-Key": f"checkout_{order.id}",
                },
            )
    except Exception as exc:
        logger.error("Không kết nối được Stripe API: %s", exc)
        raise HTTPException(status_code=502, detail="Không kết nối được cổng Stripe, vui lòng thử lại.") from exc

    if resp.status_code >= 400:
        logger.error("Stripe tạo Checkout Session lỗi HTTP %s", resp.status_code)
        raise HTTPException(status_code=502, detail="Không khởi tạo được phiên thanh toán Stripe.")

    payload = resp.json()
    session_id = str(payload.get("id") or "").strip()
    checkout_url = str(payload.get("url") or "").strip()
    if not session_id or not checkout_url:
        raise HTTPException(status_code=502, detail="Phản hồi Stripe thiếu đường dẫn thanh toán.")
    return {"session_id": session_id, "checkout_url": checkout_url}


def _paypal_api_base(mode: str) -> str:
    return "https://api-m.sandbox.paypal.com" if mode == "sandbox" else "https://api-m.paypal.com"


async def get_paypal_access_token(cfg: dict[str, Any]) -> str:
    client_id = cfg.get("paypal_client_id") or ""
    client_secret = cfg.get("paypal_client_secret") or ""
    if not client_id or not client_secret:
        raise HTTPException(status_code=503, detail="Chưa cấu hình khóa xác thực PayPal Orders v2.")
    base_url = _paypal_api_base(cfg.get("paypal_mode", "live"))
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{base_url}/v1/oauth2/token",
                data={"grant_type": "client_credentials"},
                auth=(client_id, client_secret),
                headers={"Accept": "application/json"},
            )
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Không kết nối được máy chủ PayPal OAuth.") from exc
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Xác thực PayPal OAuth thất bại.")
    token = str(resp.json().get("access_token") or "").strip()
    if not token:
        raise HTTPException(status_code=502, detail="Thiếu access_token từ PayPal.")
    return token


async def create_paypal_v2_order(
    *,
    order: PaymentOrder,
    item: PlanCatalogItem,
    return_url: str,
    cancel_url: str,
    settings: Settings | None = None,
) -> dict[str, str]:
    """Tạo PayPal Order v2 phía server (§3.3):
    `custom_id = str(order.id)`, `invoice_id = order.code`, số tiền từ đơn nội bộ.
    """
    cfg = resolve_payment_config(settings)
    if not cfg.get("paypal_enabled"):
        raise HTTPException(status_code=503, detail="Cổng thanh toán PayPal hiện đang tạm tắt.")

    token = await get_paypal_access_token(cfg)
    base_url = _paypal_api_base(cfg.get("paypal_mode", "live"))
    usd_value = format_usd_from_cents(int(order.amount))

    body = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": order.code,
                "custom_id": str(order.id),
                "invoice_id": order.code,
                "description": f"{item.name[:90]} ({order.code})",
                "amount": {
                    "currency_code": order.currency.upper(),
                    "value": usd_value,
                },
            }
        ],
        "application_context": {
            "brand_name": "Comic.io.vn AI Translator",
            "user_action": "PAY_NOW",
            "return_url": return_url,
            "cancel_url": cancel_url,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{base_url}/v2/checkout/orders",
                json=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "PayPal-Request-Id": f"create_{order.id}",
                    "Content-Type": "application/json",
                },
            )
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Không kết nối được PayPal Orders API.") from exc

    if resp.status_code not in (200, 201):
        logger.error("PayPal tạo order lỗi HTTP %s", resp.status_code)
        raise HTTPException(status_code=502, detail="Không khởi tạo được đơn PayPal.")

    data = resp.json()
    paypal_order_id = str(data.get("id") or "").strip()
    approve_url = ""
    for link in data.get("links") or []:
        if isinstance(link, dict) and link.get("rel") in ("approve", "payer-action"):
            approve_url = str(link.get("href") or "").strip()
            break
    if not paypal_order_id:
        raise HTTPException(status_code=502, detail="PayPal không trả về mã đơn hợp lệ.")
    return {"paypal_order_id": paypal_order_id, "approve_url": approve_url}


def paypal_payee_matches(
    payee: dict[str, Any] | None,
    expected_email: str,
    expected_merchant_id: str,
) -> bool:
    """Kiểm tra người nhận PayPal khớp đúng email hoặc merchant_id của mình (§1.2d & §12.4)."""
    exp_email = (expected_email or "").strip().lower()
    exp_mid = (expected_merchant_id or "").strip()
    if not exp_email and not exp_mid:
        return False
    if not isinstance(payee, dict):
        return False
    got_email = str(payee.get("email_address") or "").strip().lower()
    got_mid = str(payee.get("merchant_id") or "").strip()
    if exp_mid and got_mid:
        if got_mid != exp_mid:
            return False
    if exp_email and got_email:
        if got_email != exp_email:
            return False
    return bool((exp_mid and got_mid == exp_mid) or (exp_email and got_email == exp_email))


async def capture_or_get_paypal_order(paypal_order_id: str, cfg: dict[str, Any]) -> dict[str, Any]:
    """Gọi capture PayPal Order v2; nếu đơn đã `COMPLETED` từ trước thì đọc chi tiết đơn."""
    token = await get_paypal_access_token(cfg)
    base_url = _paypal_api_base(cfg.get("paypal_mode", "live"))
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "PayPal-Request-Id": f"cap_{paypal_order_id}",
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(f"{base_url}/v2/checkout/orders/{paypal_order_id}/capture", headers=headers)
        if resp.status_code in (200, 201):
            return resp.json()
        # Nếu khách bấm F5 khi đơn đã được capture xong (UNPROCESSABLE_ENTITY / ORDER_ALREADY_CAPTURED) -> GET
        get_resp = await client.get(f"{base_url}/v2/checkout/orders/{paypal_order_id}", headers=headers)
        if get_resp.status_code == 200:
            return get_resp.json()
    raise HTTPException(status_code=502, detail="Không xác minh được trạng thái capture từ PayPal.")


async def verify_paypal_webhook_signature(
    *,
    headers: dict[str, str] | Any,
    event_body: dict[str, Any],
    cfg: dict[str, Any],
) -> bool:
    """Xác minh chữ ký Webhook PayPal qua API chính thức `/v1/notifications/verify-webhook-signature`."""
    webhook_id = (cfg.get("paypal_webhook_id") or "").strip()
    if not webhook_id:
        return False
    get_hdr = lambda k: (headers.get(k) or headers.get(k.lower()) or "").strip()
    transmission_id = get_hdr("paypal-transmission-id")
    transmission_time = get_hdr("paypal-transmission-time")
    cert_url = get_hdr("paypal-cert-url")
    auth_algo = get_hdr("paypal-auth-algo")
    transmission_sig = get_hdr("paypal-transmission-sig")
    if not all((transmission_id, transmission_time, cert_url, auth_algo, transmission_sig)):
        return False

    token = await get_paypal_access_token(cfg)
    base_url = _paypal_api_base(cfg.get("paypal_mode", "live"))
    verify_payload = {
        "auth_algo": auth_algo,
        "cert_url": cert_url,
        "transmission_id": transmission_id,
        "transmission_sig": transmission_sig,
        "transmission_time": transmission_time,
        "webhook_id": webhook_id,
        "webhook_event": event_body,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{base_url}/v1/notifications/verify-webhook-signature",
                json=verify_payload,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
        if resp.status_code != 200:
            return False
        return str(resp.json().get("verification_status") or "").upper() == "SUCCESS"
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 11. Job Định kỳ, Khoá Redis 1 lần/ngày & `ensure_payment_schema()` (§7, §8, §12.5, §12.6)
# ---------------------------------------------------------------------------


def acquire_daily_lock(redis_client: Any, task: str, now: datetime | None = None) -> tuple[bool, str, str | None]:
    """Khoá chạy ĐÚNG MỘT LẦN mỗi ngày cho job định kỳ chạm tiền/gói (§12.5).
    Redis lỗi -> trả `(False, key, None)` để BỎ QUA lượt này (fail-closed).
    """
    cur_now = now or datetime.now(timezone.utc)
    key = f"app:daily_lock:{task}:{cur_now:%Y-%m-%d}"
    token = uuid.uuid4().hex
    if redis_client is None:
        return False, key, None
    try:
        ok = bool(redis_client.set(key, token, nx=True, ex=90_000))  # 25h
        return ok, key, (token if ok else None)
    except Exception as exc:
        logger.warning("Redis lỗi khi lấy daily_lock '%s' -> fail-closed bỏ qua lượt: %s", task, exc)
        return False, key, None


def release_daily_lock(redis_client: Any, key: str, token: str | None) -> None:
    """Chỉ gọi khi task lỗi giữa chừng để cho phép lượt sau thử lại (§12.5)."""
    if redis_client is None or not token:
        return
    try:
        redis_client.eval(RELEASE_LUA, 1, key, token)
    except Exception:
        pass


async def expire_stale_pending_orders(session: AsyncSession, now: datetime | None = None) -> int:
    """Dọn các đơn `pending` đã quá hạn `expires_at` mà chưa có tiền."""
    cur_now = now or datetime.now(timezone.utc)
    res = await session.execute(
        update(PaymentOrder)
        .where(
            PaymentOrder.status == "pending",
            PaymentOrder.expires_at.is_not(None),
            PaymentOrder.expires_at < cur_now,
        )
        .values(status="expired", updated_at=cur_now)
    )
    await session.commit()
    return int(res.rowcount or 0)


async def expire_lapsed_subscriptions(session: AsyncSession, now: datetime | None = None) -> int:
    """Hạ gói hết hạn CÓ ĐIỀU KIỆN ngay trong chính câu `UPDATE` (§12.6):
    0 dòng bị đổi = user vừa gia hạn giữa lúc SELECT và UPDATE -> bỏ qua an toàn!
    """
    cur_now = now or datetime.now(timezone.utc)
    candidate_ids = list(
        (
            await session.execute(
                select(NguoiDung.id).where(
                    NguoiDung.trang_thai_billing.in_(("active", "canceling", "past_due", "manual")),
                    NguoiDung.het_han_goi.is_not(None),
                    NguoiDung.het_han_goi < cur_now,
                )
            )
        ).scalars()
    )
    downgraded = 0
    for uid in candidate_ids:
        upd = await session.execute(
            update(NguoiDung)
            .where(
                NguoiDung.id == uid,
                NguoiDung.trang_thai_billing.in_(("active", "canceling", "past_due", "manual")),
                NguoiDung.het_han_goi.is_not(None),
                NguoiDung.het_han_goi < cur_now,
            )
            .values(
                cap_do_goi=0,
                trang_thai_billing="canceled",
                updated_at=cur_now,
            )
            .returning(NguoiDung.id)
        )
        if upd.first() is not None:
            downgraded += 1
    if candidate_ids:
        await session.commit()
    return downgraded


async def check_payment_schema_status(session: AsyncSession) -> dict[str, Any]:
    """Endpoint admin chỉ đọc để kiểm tra các bảng thanh toán thật sự đã tồn tại trên DB production (§8)."""
    required_tables = ("payment_orders", "payment_events", "payment_reviews", "don_nap_luot", "nguoi_dung")
    present: dict[str, bool] = {}
    try:
        for t in required_tables:
            row = (await session.execute(sa.text("SELECT to_regclass(:tname)"), {"tname": f"public.{t}"})).scalar()
            present[t] = row is not None
        cols = (
            await session.execute(
                sa.text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'nguoi_dung'"
                )
            )
        ).scalars().all()
        col_set = set(cols)
        user_cols_ok = {"cap_do_goi", "ma_goi_hien_tai", "het_han_goi", "trang_thai_billing", "gio_luot_json"} <= col_set
        all_ok = all(present.values()) and user_cols_ok
        return {"ok": all_ok, "tables": present, "nguoi_dung_billing_columns": user_cols_ok}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__, "tables": present}


_ENSURE_SCHEMA_STATEMENTS: tuple[str, ...] = (
    "ALTER TABLE nguoi_dung ADD COLUMN IF NOT EXISTS cap_do_goi INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE nguoi_dung ADD COLUMN IF NOT EXISTS ma_goi_hien_tai VARCHAR(64)",
    "ALTER TABLE nguoi_dung ADD COLUMN IF NOT EXISTS het_han_goi TIMESTAMPTZ",
    "ALTER TABLE nguoi_dung ADD COLUMN IF NOT EXISTS trang_thai_billing VARCHAR(32) NOT NULL DEFAULT 'free'",
    "ALTER TABLE nguoi_dung ADD COLUMN IF NOT EXISTS gio_luot_json JSONB NOT NULL DEFAULT '[]'::jsonb",
    "CREATE INDEX IF NOT EXISTS ix_nguoi_dung_het_han_goi ON nguoi_dung (het_han_goi)",
    """CREATE TABLE IF NOT EXISTS payment_orders (
        id UUID PRIMARY KEY,
        user_id UUID REFERENCES nguoi_dung(id) ON DELETE SET NULL,
        owner_ref VARCHAR(64) NOT NULL,
        email VARCHAR(320) NOT NULL DEFAULT '',
        plan VARCHAR(64) NOT NULL,
        tier_rank INTEGER NOT NULL DEFAULT 1,
        credits INTEGER NOT NULL DEFAULT 0,
        duration_days INTEGER NOT NULL DEFAULT 30,
        rail VARCHAR(32) NOT NULL,
        currency VARCHAR(8) NOT NULL,
        amount BIGINT NOT NULL,
        code VARCHAR(32) NOT NULL CONSTRAINT uq_payment_orders_code UNIQUE,
        status VARCHAR(32) NOT NULL DEFAULT 'pending',
        paid_amount BIGINT,
        paid_at TIMESTAMPTZ,
        activated_at TIMESTAMPTZ,
        provider_ref TEXT,
        evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
        admin_note TEXT,
        expires_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )""",
    "CREATE INDEX IF NOT EXISTS ix_payment_orders_status_expires ON payment_orders (status, expires_at)",
    "CREATE INDEX IF NOT EXISTS ix_payment_orders_user_created ON payment_orders (user_id, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_payment_orders_owner_created ON payment_orders (owner_ref, created_at)",
    """CREATE TABLE IF NOT EXISTS payment_events (
        id UUID PRIMARY KEY,
        provider VARCHAR(40) NOT NULL,
        provider_event_id VARCHAR(160) NOT NULL,
        event_type VARCHAR(96),
        amount BIGINT,
        currency VARCHAR(8),
        order_id UUID,
        match_type VARCHAR(40) NOT NULL DEFAULT 'claiming',
        processed BOOLEAN NOT NULL DEFAULT false,
        error TEXT,
        raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        processed_at TIMESTAMPTZ,
        CONSTRAINT uq_payment_events_provider_event UNIQUE (provider, provider_event_id)
    )""",
    "CREATE INDEX IF NOT EXISTS ix_payment_events_order_id ON payment_events (order_id)",
    """CREATE TABLE IF NOT EXISTS payment_reviews (
        id UUID PRIMARY KEY,
        provider VARCHAR(40) NOT NULL,
        provider_event_id VARCHAR(160),
        event_type VARCHAR(96),
        user_id VARCHAR(64),
        user_email VARCHAR(320),
        order_id VARCHAR(64),
        order_code VARCHAR(32),
        current_tier VARCHAR(32),
        target_tier VARCHAR(32),
        amount BIGINT,
        currency VARCHAR(8),
        status VARCHAR(32) NOT NULL DEFAULT 'needs_manual_review',
        reason VARCHAR(120),
        raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
        resolved_by VARCHAR(320),
        resolved_at TIMESTAMPTZ,
        resolution_note TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )""",
    "CREATE INDEX IF NOT EXISTS ix_payment_reviews_status_created ON payment_reviews (status, created_at)",
)


async def ensure_payment_schema(session: AsyncSession) -> bool:
    """Đảm bảo schema thanh toán tồn tại idempotent lúc khởi động (có khoá tránh chạy chồng;
    lỗi chỉ ghi log + cảnh báo, tuyệt đối không làm sập ứng dụng — §8).
    """
    try:
        for ddl in _ENSURE_SCHEMA_STATEMENTS:
            await session.execute(sa.text(ddl))
        await session.commit()
        return True
    except Exception as exc:
        try:
            await session.rollback()
        except Exception:
            pass
        logger.error("ensure_payment_schema lỗi (không làm sập app): %s", exc)
        await send_payment_alert(
            title="🚨 ensure_payment_schema lỗi lúc khởi động",
            details={"error_type": type(exc).__name__},
        )
        return False
