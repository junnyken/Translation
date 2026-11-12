"""Endpoints Thanh toán Trực tuyến An toàn (VietQR/SePay, Stripe Checkout, PayPal Orders v2 & Admin Review Queue)."""
from __future__ import annotations

import json
import logging
import re
import urllib.parse
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.danh_tinh_khach import DanhTinhHanMuc, danh_tinh_han_muc, ten_cap_do, tinh_cap_do
from app.core.db import get_session
from app.core.quyen import nguoi_dung_hien_tai, nguoi_dung_phien_dang_nhap
from app.models import NguoiDung, PaymentOrder, PaymentReview
from app.schemas.common import (
    GoiNapLuotRead,
    PayPalCaptureOrderResponse,
    PayPalCreateOrderRequest,
    PayPalCreateOrderResponse,
    PaymentOrderRead,
    PaymentReviewRead,
    QuanTriCauHinhThanhToanRequest,
    QuanTriCauHinhThanhToanResponse,
    StripeCheckoutRequest,
    StripeCheckoutResponse,
    TaoDonThanhToanRequest,
    ThongTinNapLuotRead,
    XuLyPaymentReviewRequest,
)
from app.services import nhat_ky_quan_tri
from app.services import thanh_toan as tt

logger = logging.getLogger(__name__)

MAX_WEBHOOK_BODY_BYTES = 262_144  # 256 KB
VN_TZ = timezone(timedelta(hours=7))


def _customer_status_message(status: str) -> str:
    if status == "paid":
        return "Thanh toán đã hoàn tất! Quyền lợi gói cước và Credits đã được cộng vào tài khoản."
    if status in ("needs_manual_review", "underpaid", "expired_late_payment"):
        return "Thanh toán đang được kiểm tra, chúng tôi sẽ liên hệ trong 24h."
    if status == "expired":
        return "Đơn thanh toán đã hết hạn 24h. Vui lòng tạo đơn mới trước khi chuyển khoản."
    if status == "canceled":
        return "Đơn thanh toán đã được huỷ."
    if status == "refunded":
        return "Đơn thanh toán đã được hoàn tiền / xử lý đối soát."
    return "Đang chờ xác nhận thanh toán từ cổng ngân hàng / quốc tế."


def _order_to_read(
    order: PaymentOrder,
    *,
    cfg: dict[str, Any] | None = None,
    plan_name: str = "",
) -> PaymentOrderRead:
    eff_cfg = cfg or tt.resolve_payment_config()
    if order.currency.upper() == "VND":
        amt_disp = f"{int(order.amount):,}đ".replace(",", ".")
    else:
        amt_disp = f"${tt.format_usd_from_cents(int(order.amount))}"

    qr_url = ""
    if order.rail == "vietqr" and order.status == "pending":
        qr_url = tt.build_vietqr_url(
            eff_cfg.get("ngan_hang_ten", ""),
            eff_cfg.get("ngan_hang_so_tk", ""),
            eff_cfg.get("ngan_hang_chu_tk", ""),
            int(order.amount),
            order.code,
        )

    return PaymentOrderRead(
        id=order.id,
        code=order.code,
        plan=order.plan,
        plan_name=plan_name or order.plan,
        tier_rank=int(order.tier_rank),
        credits=int(order.credits),
        duration_days=int(order.duration_days),
        rail=order.rail,
        currency=order.currency,
        amount=int(order.amount),
        amount_display=amt_disp,
        status=order.status,
        customer_message=_customer_status_message(order.status),
        vietqr_url=qr_url,
        bank_name=eff_cfg.get("ngan_hang_ten", ""),
        bank_account=eff_cfg.get("ngan_hang_so_tk", ""),
        bank_holder=eff_cfg.get("ngan_hang_chu_tk", ""),
        provider_ref=order.provider_ref,
        paid_amount=int(order.paid_amount) if order.paid_amount is not None else None,
        expires_at=order.expires_at.isoformat() if order.expires_at else None,
        created_at=order.created_at.isoformat() if order.created_at else "",
    )


def _review_to_read(r: PaymentReview) -> PaymentReviewRead:
    return PaymentReviewRead(
        id=r.id,
        provider=r.provider,
        provider_event_id=r.provider_event_id,
        event_type=r.event_type,
        user_id=r.user_id,
        user_email=r.user_email,
        order_id=r.order_id,
        order_code=r.order_code,
        current_tier=r.current_tier,
        target_tier=r.target_tier,
        amount=int(r.amount) if r.amount is not None else None,
        currency=r.currency,
        status=r.status,
        reason=r.reason,
        raw_payload=r.raw_payload if isinstance(r.raw_payload, dict) else {},
        resolved_by=r.resolved_by,
        resolved_at=r.resolved_at.isoformat() if r.resolved_at else None,
        resolution_note=r.resolution_note,
        created_at=r.created_at.isoformat() if r.created_at else "",
    )


def _catalog_items_to_goi_read(items: list[tt.PlanCatalogItem]) -> list[GoiNapLuotRead]:
    return [
        GoiNapLuotRead(
            ma=it.code,
            ten=it.name,
            so_tien_vnd=int(it.amount_vnd),
            so_trang=int(it.credits),
            ghi_chu=it.note,
            so_tien_usd_cents=int(it.amount_usd_cents),
            gia_goc_vnd=int(it.original_vnd),
            gia_goc_usd_cents=int(it.original_usd_cents),
            cap_do=int(it.tier_rank),
            ten_cap_do=it.tier_name,
            so_ngay_han=int(it.duration_days),
            chu_ky=it.billing_cycle,
            uu_dai_lan_dau=bool(it.is_first_time_promo),
        )
        for it in items
    ]


def _normalize_bank_acc(acc: str | None) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", (acc or "").strip()).upper()


def _parse_sepay_tx_time(raw_dt: Any) -> str | None:
    """Giờ giao dịch của SePay là giờ Việt Nam (UTC+7) -> đổi chuẩn xác về UTC (§3.1 bước 3)."""
    if not raw_dt:
        return None
    s = str(raw_dt).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt_vn = datetime.strptime(s[:19], fmt).replace(tzinfo=VN_TZ)
            return dt_vn.astimezone(timezone.utc).isoformat()
        except ValueError:
            continue
    try:
        dt_any = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt_any.tzinfo is None:
            dt_any = dt_any.replace(tzinfo=VN_TZ)
        return dt_any.astimezone(timezone.utc).isoformat()
    except ValueError:
        return None


def _safe_frontend_return_url(candidate: str | None, default_base: str, fallback_path: str) -> str:
    base = (default_base or "https://comic.io.vn").rstrip("/")
    if not candidate or not candidate.strip():
        return f"{base}{fallback_path}"
    cand = candidate.strip()
    parsed_cand = urllib.parse.urlparse(cand)
    parsed_base = urllib.parse.urlparse(base)
    if parsed_cand.scheme in ("http", "https") and (
        parsed_cand.netloc == parsed_base.netloc
        or parsed_cand.hostname in ("localhost", "127.0.0.1", "comic.io.vn")
    ):
        return cand
    return f"{base}{fallback_path}"


async def _read_bounded_raw_body(request: Request) -> bytes:
    raw = await request.body()
    if len(raw) > MAX_WEBHOOK_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Webhook payload too large")
    return raw


def attach_payment_routes(router: APIRouter, router_khach: APIRouter) -> None:
    """Gắn các route thanh toán an toàn vào `router` (yêu cầu đăng nhập) và `router_khach` (public/webhook)."""

    # =========================================================================
    # A. BẢNG GIÁ DUY NHẤT & TẠO / TRA CỨU / HUỶ ĐƠN HÀNG NỘI BỘ
    # =========================================================================

    @router_khach.get("/thanh-toan/bang-gia", response_model=ThongTinNapLuotRead, tags=["thanh-toan"])
    async def xem_bang_gia_chuan(
        session: AsyncSession = Depends(get_session),
        settings: Settings = Depends(get_settings),
        danh_tinh: DanhTinhHanMuc = Depends(danh_tinh_han_muc),
    ) -> ThongTinNapLuotRead:
        """API Bảng giá chuẩn duy nhất (dùng chung cho Pricing UI, Checkout và Tạo đơn)."""
        nguoi = (
            danh_tinh.nguoi_goi.nguoi
            if (danh_tinh.co_tai_khoan and not danh_tinh.nguoi_goi.la_khach)
            else None
        )
        email = nguoi.email if nguoi is not None else None
        da_tung_nap = (
            await tt.has_prior_paid_purchase(session, user_id=nguoi.id, email=email)
            if nguoi is not None
            else False
        )
        cfg = tt.resolve_payment_config(settings)
        don_gia = max(1, settings.ty_le_vnd_moi_trang)
        items = tt.catalog(
            da_tung_nap=da_tung_nap,
            don_gia_vnd=don_gia,
            overrides=cfg.get("price_overrides"),
        )
        cap_hien = tinh_cap_do(nguoi) if nguoi is not None else 0
        het_han_str = (
            nguoi.het_han_goi.isoformat()
            if (nguoi is not None and getattr(nguoi, "het_han_goi", None) is not None)
            else None
        )
        return ThongTinNapLuotRead(
            co_tai_khoan=danh_tinh.co_tai_khoan,
            email=email,
            la_quan_tri=bool(nguoi and nguoi.la_quan_tri),
            da_tung_nap=da_tung_nap,
            so_luot_mua_them=danh_tinh.so_luot_mua_them if danh_tinh.co_tai_khoan else 0,
            tran_hang_ngay=danh_tinh.tran_hien,
            cap_do_hien_tai=cap_hien,
            ten_cap_do_hien_tai=ten_cap_do(cap_hien),
            het_han_goi=het_han_str,
            ngan_hang_ten=cfg["ngan_hang_ten"],
            ngan_hang_so_tk=cfg["ngan_hang_so_tk"],
            ngan_hang_chu_tk=cfg["ngan_hang_chu_tk"],
            paypal_email=cfg["paypal_email"],
            paypal_client_id=cfg["paypal_client_id"],
            rapidapi_url=cfg["rapidapi_url"],
            vietqr_enabled=bool(cfg["vietqr_enabled"]),
            stripe_enabled=bool(cfg["stripe_enabled"]),
            paypal_enabled=bool(cfg["paypal_enabled"]),
            noi_dung_chuyen_khoan="Tạo đơn để nhận mã CIOXXXXXXXX duy nhất",
            ty_le_vnd_moi_trang=don_gia,
            goi_goi_y=_catalog_items_to_goi_read(items),
        )

    @router.post("/thanh-toan/tao-don", response_model=PaymentOrderRead, tags=["thanh-toan"])
    async def tao_don_thanh_toan(
        body: TaoDonThanhToanRequest,
        session: AsyncSession = Depends(get_session),
        settings: Settings = Depends(get_settings),
        nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
    ) -> PaymentOrderRead:
        """Tạo đơn hàng nội bộ chốt cứng giá nguyên từ server `catalog` và sinh mã `CIOXXXXXXXX`."""
        cfg = tt.resolve_payment_config(settings)
        order, item = await tt.create_payment_order(
            session,
            nguoi=nguoi,
            plan_code=body.plan,
            rail=body.rail,
            settings=settings,
        )
        return _order_to_read(order, cfg=cfg, plan_name=item.name)

    @router.get("/thanh-toan/don/{order_id}", response_model=PaymentOrderRead, tags=["thanh-toan"])
    async def xem_don_thanh_toan(
        order_id: uuid.UUID,
        session: AsyncSession = Depends(get_session),
        settings: Settings = Depends(get_settings),
        nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
    ) -> PaymentOrderRead:
        """Tra cứu trạng thái đơn hàng của CHÍNH người dùng đang đăng nhập (người khác -> 404)."""
        order = await session.get(PaymentOrder, order_id)
        if order is None or order.user_id != nguoi.id:
            raise HTTPException(status_code=404, detail="Không tìm thấy đơn thanh toán.")
        cfg = tt.resolve_payment_config(settings)
        return _order_to_read(order, cfg=cfg)

    @router.post("/thanh-toan/don/{order_id}/huy", response_model=PaymentOrderRead, tags=["thanh-toan"])
    async def huy_don_thanh_toan(
        order_id: uuid.UUID,
        session: AsyncSession = Depends(get_session),
        settings: Settings = Depends(get_settings),
        nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
    ) -> PaymentOrderRead:
        """Huỷ đơn `pending` của chính mình bằng Compare-And-Set."""
        order = await session.get(PaymentOrder, order_id)
        if order is None or order.user_id != nguoi.id:
            raise HTTPException(status_code=404, detail="Không tìm thấy đơn thanh toán.")
        cas = await session.execute(
            update(PaymentOrder)
            .where(PaymentOrder.id == order.id, PaymentOrder.status == "pending")
            .values(status="canceled", updated_at=datetime.now(timezone.utc))
            .returning(PaymentOrder.id)
        )
        if cas.first() is None:
            raise HTTPException(status_code=409, detail=f"Đơn đang ở trạng thái '{order.status}', không thể huỷ.")
        await session.commit()
        await session.refresh(order)
        cfg = tt.resolve_payment_config(settings)
        return _order_to_read(order, cfg=cfg)

    # =========================================================================
    # B. VIETQR + SEPAY WEBHOOK CHUẨN HMAC-SHA256 (§3.1)
    # =========================================================================

    @router_khach.post("/thanh-toan/webhook/sepay", tags=["thanh-toan"])
    async def webhook_sepay_chuan(
        request: Request,
        session: AsyncSession = Depends(get_session),
        settings: Settings = Depends(get_settings),
    ) -> dict[str, Any]:
        """Webhook SePay chuẩn an toàn 9 bước (§3.1):
        1. Đọc raw body + xác minh `X-SePay-Signature` HMAC-SHA256 hằng thời gian.
        2. Kiểm `transferType == 'in'` + `accountNumber` đúng tài khoản nhận của mình.
        3. Trích mã đơn `CIOXXXXXXXX` + parse tiền `Decimal` + đổi giờ VN (UTC+7) về UTC.
        4. Chiếm chỗ `payment_events(provider='sepay', provider_event_id=<id>)` (trùng -> duplicate, DB lỗi -> 503).
        5-8. Mọi lệch (thiếu mã, sai mã, đơn hết hạn, thiếu tiền, hạ gói) -> `payment_reviews` + cảnh báo;
             hợp lệ -> CAS `pending -> paid` -> `grant()` -> cập nhật `payment_events` thành `matched`.
        """
        cfg = tt.resolve_payment_config(settings)
        sepay_secrets = cfg.get("sepay_secrets") or []
        expected_acc = _normalize_bank_acc(cfg.get("ngan_hang_so_tk"))
        if not sepay_secrets or not expected_acc:
            raise HTTPException(
                status_code=503,
                detail="Cổng webhook SePay đang tắt (chưa cấu hình secret hoặc số tài khoản nhận).",
            )

        raw_body = await _read_bounded_raw_body(request)
        ok_sig, sig_reason = tt.verify_sepay_signature(
            raw_body,
            request.headers,
            sepay_secrets,
            allow_apikey=bool(cfg.get("sepay_allow_apikey_auth")),
        )
        if not ok_sig:
            raise HTTPException(status_code=401, detail=f"Signature verification failed: {sig_reason}")

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Invalid JSON object")

        transfer_type = str(payload.get("transferType") or "").strip().lower()
        if transfer_type != "in":
            return {"success": True, "ignored": "not_incoming_transfer"}

        sepay_id = str(payload.get("id") or payload.get("referenceCode") or "").strip()
        if not sepay_id:
            raise HTTPException(status_code=400, detail="Missing SePay transaction id")

        got_acc = _normalize_bank_acc(str(payload.get("accountNumber") or ""))
        if not got_acc or got_acc != expected_acc:
            raise HTTPException(status_code=400, detail="Receiver account mismatch")

        paid_vnd = tt.parse_minor_units(payload.get("transferAmount"), exponent=0)
        tx_utc = _parse_sepay_tx_time(payload.get("transactionDate"))

        # Bước 4: Chiếm chỗ sự kiện TRƯỚC mọi thay đổi quyền lợi!
        claim_state, event_row_id = await tt.claim_event(
            session,
            "sepay",
            sepay_id,
            event_type="bank_transfer_in",
            amount=paid_vnd,
            currency="VND",
            raw_payload={
                "id": sepay_id,
                "gateway": payload.get("gateway"),
                "transferAmount": payload.get("transferAmount"),
                "transactionDateUtc": tx_utc,
                "referenceCode": payload.get("referenceCode"),
            },
        )
        if claim_state == "duplicate":
            return {"success": True, "duplicate": True}

        if paid_vnd is None:
            await tt.record_review_and_alert(
                session,
                provider="sepay",
                reason="invalid_or_zero_amount",
                provider_event_id=sepay_id,
                event_type="bank_transfer_in",
                currency="VND",
                raw_payload={"id": sepay_id, "transferAmount": payload.get("transferAmount")},
                settings=settings,
            )
            await tt.finalize_event(
                session,
                event_row_id,
                match_type="failed",
                processed=True,
                error="invalid_or_zero_amount",
            )
            return {"success": True, "outcome": "needs_manual_review", "reason": "invalid_or_zero_amount"}

        order_code = tt.extract_order_code(str(payload.get("code") or "")) or tt.extract_order_code(
            f"{payload.get('content') or ''} {payload.get('description') or ''}"
        )
        if not order_code:
            await tt.record_review_and_alert(
                session,
                provider="sepay",
                reason="missing_order_code",
                provider_event_id=sepay_id,
                event_type="bank_transfer_in",
                amount=paid_vnd,
                currency="VND",
                raw_payload={"id": sepay_id, "referenceCode": payload.get("referenceCode"), "tx_utc": tx_utc},
                settings=settings,
            )
            await tt.finalize_event(
                session,
                event_row_id,
                match_type="unmatched",
                processed=True,
                amount=paid_vnd,
                currency="VND",
                error="missing_order_code",
            )
            return {"success": True, "outcome": "needs_manual_review", "reason": "missing_order_code"}

        order = (
            await session.execute(select(PaymentOrder).where(PaymentOrder.code == order_code))
        ).scalar_one_or_none()
        if order is None:
            await tt.record_review_and_alert(
                session,
                provider="sepay",
                reason="order_code_not_found",
                provider_event_id=sepay_id,
                event_type="bank_transfer_in",
                order_code=order_code,
                amount=paid_vnd,
                currency="VND",
                raw_payload={"id": sepay_id, "order_code": order_code, "tx_utc": tx_utc},
                settings=settings,
            )
            await tt.finalize_event(
                session,
                event_row_id,
                match_type="unmatched",
                processed=True,
                amount=paid_vnd,
                currency="VND",
                error="order_code_not_found",
            )
            return {"success": True, "outcome": "needs_manual_review", "reason": "order_code_not_found"}

        activated, outcome = await tt.activate_order(
            session,
            order_id=order.id,
            paid_amount=paid_vnd,
            currency="VND",
            provider="sepay",
            provider_event_id=sepay_id,
            provider_ref=sepay_id,
            evidence={
                "sepay_id": sepay_id,
                "gateway": payload.get("gateway"),
                "reference_code": payload.get("referenceCode"),
                "transaction_utc": tx_utc,
            },
            settings=settings,
        )
        await tt.finalize_event(
            session,
            event_row_id,
            match_type="matched" if activated else outcome,
            processed=True,
            order_id=order.id,
            amount=paid_vnd,
            currency="VND",
            error=None if activated else outcome,
        )
        return {"success": True, "activated": activated, "outcome": outcome, "order_code": order.code}

    # =========================================================================
    # C. STRIPE CHECKOUT & WEBHOOK (§3.2)
    # =========================================================================

    @router.post("/thanh-toan/stripe/checkout", response_model=StripeCheckoutResponse, tags=["thanh-toan"])
    async def tao_phien_stripe_checkout(
        body: StripeCheckoutRequest,
        session: AsyncSession = Depends(get_session),
        settings: Settings = Depends(get_settings),
        nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
    ) -> StripeCheckoutResponse:
        cfg = tt.resolve_payment_config(settings)
        if not cfg.get("stripe_enabled"):
            raise HTTPException(status_code=503, detail="Cổng thanh toán thẻ quốc tế Stripe hiện đang tạm tắt.")

        order, item = await tt.create_payment_order(
            session,
            nguoi=nguoi,
            plan_code=body.plan,
            rail="stripe",
            settings=settings,
        )
        success_url = _safe_frontend_return_url(
            body.success_url,
            settings.frontend_site_url,
            f"/?payment=stripe_success&order_id={order.id}",
        )
        cancel_url = _safe_frontend_return_url(
            body.cancel_url,
            settings.frontend_site_url,
            f"/?payment=stripe_cancel&order_id={order.id}",
        )
        stripe_res = await tt.create_stripe_checkout_session(
            order=order,
            item=item,
            success_url=success_url,
            cancel_url=cancel_url,
            settings=settings,
        )
        order.provider_ref = stripe_res["session_id"]
        await session.commit()
        await session.refresh(order)
        return StripeCheckoutResponse(
            order=_order_to_read(order, cfg=cfg, plan_name=item.name),
            session_id=stripe_res["session_id"],
            checkout_url=stripe_res["checkout_url"],
        )

    @router_khach.post("/thanh-toan/webhook/stripe", tags=["thanh-toan"])
    async def webhook_stripe_chuan(
        request: Request,
        session: AsyncSession = Depends(get_session),
        settings: Settings = Depends(get_settings),
    ) -> dict[str, Any]:
        """Webhook Stripe chuẩn (§3.2):
        - Thiếu `STRIPE_WEBHOOK_SECRET` -> HTTP 404 (tuyệt đối không nhận event chưa ký).
        - Xác minh `Stripe-Signature` (`t=...,v1=...`) trên `raw_body`.
        - Idempotency theo `event.id` trong `payment_events` trước mọi thay đổi.
        """
        cfg = tt.resolve_payment_config(settings)
        wh_secrets = cfg.get("stripe_webhook_secrets") or []
        if not wh_secrets:
            raise HTTPException(status_code=404, detail="Stripe webhook endpoint not configured")

        raw_body = await _read_bounded_raw_body(request)
        sig_header = request.headers.get("stripe-signature")
        ok_sig, sig_reason = tt.verify_stripe_signature(raw_body, sig_header, wh_secrets)
        if not ok_sig:
            raise HTTPException(status_code=400, detail=f"Invalid Stripe signature: {sig_reason}")

        try:
            event = json.loads(raw_body.decode("utf-8"))
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid Stripe JSON") from exc
        if not isinstance(event, dict):
            raise HTTPException(status_code=400, detail="Invalid Stripe event")

        event_id = str(event.get("id") or "").strip()
        event_type = str(event.get("type") or "").strip()
        obj = ((event.get("data") or {}).get("object")) if isinstance(event.get("data"), dict) else None
        if not event_id or not event_type or not isinstance(obj, dict):
            raise HTTPException(status_code=400, detail="Malformed Stripe event")

        claim_state, event_row_id = await tt.claim_event(
            session,
            "stripe",
            event_id,
            event_type=event_type,
            raw_payload={"id": event_id, "type": event_type, "object_id": obj.get("id")},
        )
        if claim_state == "duplicate":
            return {"received": True, "duplicate": True}

        if event_type == "checkout.session.completed":
            pay_status = str(obj.get("payment_status") or "").lower()
            if pay_status != "paid":
                await tt.finalize_event(session, event_row_id, match_type="ignored", processed=True, error=f"payment_status:{pay_status}")
                return {"received": True, "ignored": "not_paid_yet"}

            meta = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
            order_id_str = str(meta.get("order_id") or obj.get("client_reference_id") or "").strip()
            meta_user_id = str(meta.get("user_id") or "").strip()
            paid_cents = tt.parse_minor_units(obj.get("amount_total"), exponent=0)
            currency = str(obj.get("currency") or "").strip().upper()

            if paid_cents is None or not order_id_str:
                await tt.record_review_and_alert(
                    session,
                    provider="stripe",
                    reason="missing_order_or_invalid_amount",
                    provider_event_id=event_id,
                    event_type=event_type,
                    user_id=meta_user_id or None,
                    order_id=order_id_str or None,
                    amount=paid_cents,
                    currency=currency or None,
                    raw_payload={"session_id": obj.get("id"), "metadata": meta},
                    settings=settings,
                )
                await tt.finalize_event(session, event_row_id, match_type="needs_manual_review", processed=True, error="missing_order_or_invalid_amount")
                return {"received": True, "outcome": "needs_manual_review"}

            try:
                order_uuid = uuid.UUID(order_id_str)
            except ValueError:
                await tt.record_review_and_alert(
                    session,
                    provider="stripe",
                    reason="non_internal_order_id",
                    provider_event_id=event_id,
                    event_type=event_type,
                    user_id=meta_user_id or None,
                    order_id=order_id_str,
                    amount=paid_cents,
                    currency=currency,
                    raw_payload={"session_id": obj.get("id")},
                    settings=settings,
                )
                await tt.finalize_event(session, event_row_id, match_type="needs_manual_review", processed=True, error="non_internal_order_id")
                return {"received": True, "outcome": "needs_manual_review"}

            order = await session.get(PaymentOrder, order_uuid)
            if order is None or (meta_user_id and str(order.user_id) != meta_user_id):
                await tt.record_review_and_alert(
                    session,
                    provider="stripe",
                    reason="user_or_order_mismatch",
                    provider_event_id=event_id,
                    event_type=event_type,
                    order=order,
                    user_id=meta_user_id or None,
                    order_id=order_id_str,
                    amount=paid_cents,
                    currency=currency,
                    raw_payload={"session_id": obj.get("id"), "metadata": meta},
                    settings=settings,
                )
                await tt.finalize_event(session, event_row_id, match_type="needs_manual_review", processed=True, error="user_or_order_mismatch")
                return {"received": True, "outcome": "needs_manual_review"}

            activated, outcome = await tt.activate_order(
                session,
                order_id=order.id,
                paid_amount=paid_cents,
                currency=currency,
                provider="stripe",
                provider_event_id=event_id,
                provider_ref=str(obj.get("id") or event_id),
                evidence={"stripe_session_id": obj.get("id"), "payment_intent": obj.get("payment_intent")},
                settings=settings,
            )
            await tt.finalize_event(
                session,
                event_row_id,
                match_type="matched" if activated else outcome,
                processed=True,
                order_id=order.id,
                amount=paid_cents,
                currency=currency,
                error=None if activated else outcome,
            )
            return {"received": True, "activated": activated, "outcome": outcome}

        if event_type == "invoice.paid":
            billing_reason = str(obj.get("billing_reason") or "").lower()
            if billing_reason == "subscription_create":
                # Kỳ đầu đã do checkout.session.completed xử lý
                await tt.finalize_event(session, event_row_id, match_type="ignored", processed=True, error="initial_subscription_invoice")
                return {"received": True, "ignored": "subscription_create"}

            sub_details = obj.get("subscription_details") if isinstance(obj.get("subscription_details"), dict) else {}
            meta = sub_details.get("metadata") if isinstance(sub_details.get("metadata"), dict) else (obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {})
            user_id_str = str(meta.get("user_id") or "").strip()
            plan_code = str(meta.get("plan") or "").strip()
            paid_cents = tt.parse_minor_units(obj.get("amount_paid"), exponent=0)
            currency = str(obj.get("currency") or "").strip().upper()
            invoice_id = str(obj.get("id") or event_id)

            if not user_id_str or not plan_code or paid_cents is None:
                await tt.record_review_and_alert(
                    session,
                    provider="stripe",
                    reason="invoice_missing_metadata_or_amount",
                    provider_event_id=event_id,
                    event_type=event_type,
                    user_id=user_id_str or None,
                    target_tier=plan_code or None,
                    amount=paid_cents,
                    currency=currency or None,
                    raw_payload={"invoice_id": invoice_id},
                    settings=settings,
                )
                await tt.finalize_event(session, event_row_id, match_type="needs_manual_review", processed=True, error="invoice_missing_metadata")
                return {"received": True, "outcome": "needs_manual_review"}

            try:
                uid = uuid.UUID(user_id_str)
            except ValueError:
                uid = None
            nguoi_sub = await session.get(NguoiDung, uid) if uid else None
            items_renew = tt.catalog(da_tung_nap=True, don_gia_vnd=settings.ty_le_vnd_moi_trang, overrides=cfg.get("price_overrides"))
            plan_item = {it.code: it for it in items_renew}.get(plan_code)
            if nguoi_sub is None or plan_item is None:
                await tt.record_review_and_alert(
                    session,
                    provider="stripe",
                    reason="invoice_unknown_user_or_plan",
                    provider_event_id=event_id,
                    event_type=event_type,
                    user_id=user_id_str,
                    target_tier=plan_code,
                    amount=paid_cents,
                    currency=currency,
                    raw_payload={"invoice_id": invoice_id},
                    settings=settings,
                )
                await tt.finalize_event(session, event_row_id, match_type="needs_manual_review", processed=True, error="invoice_unknown_user_or_plan")
                return {"received": True, "outcome": "needs_manual_review"}

            renew_order = PaymentOrder(
                id=uuid.uuid4(),
                user_id=nguoi_sub.id,
                owner_ref=str(nguoi_sub.id),
                email=nguoi_sub.email,
                plan=plan_item.code,
                tier_rank=plan_item.tier_rank,
                credits=plan_item.credits,
                duration_days=plan_item.duration_days,
                rail="stripe",
                currency="USD",
                amount=int(plan_item.amount_usd_cents),
                code=tt.generate_order_code(),
                status="pending",
                provider_ref=invoice_id,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            )
            session.add(renew_order)
            await session.commit()
            activated, outcome = await tt.activate_order(
                session,
                order_id=renew_order.id,
                paid_amount=paid_cents,
                currency=currency,
                provider="stripe",
                provider_event_id=event_id,
                provider_ref=invoice_id,
                evidence={"invoice_id": invoice_id, "billing_reason": billing_reason},
                settings=settings,
            )
            await tt.finalize_event(session, event_row_id, match_type="matched" if activated else outcome, processed=True, order_id=renew_order.id, amount=paid_cents, currency=currency)
            return {"received": True, "activated": activated, "outcome": outcome}

        if event_type in ("customer.subscription.updated", "customer.subscription.deleted", "invoice.payment_failed"):
            meta = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
            uid_str = str(meta.get("user_id") or "").strip()
            try:
                uid = uuid.UUID(uid_str) if uid_str else None
            except ValueError:
                uid = None
            if uid is not None:
                nguoi_s = await session.get(NguoiDung, uid)
                if nguoi_s is not None:
                    if event_type == "invoice.payment_failed":
                        nguoi_s.trang_thai_billing = "past_due"
                        # Grace period 3 ngày trước khi job định kỳ hạ gói
                        now_utc = datetime.now(timezone.utc)
                        if nguoi_s.het_han_goi is None or nguoi_s.het_han_goi < now_utc:
                            nguoi_s.het_han_goi = now_utc + timedelta(days=3)
                    elif event_type == "customer.subscription.deleted":
                        nguoi_s.trang_thai_billing = "canceling"
                    elif event_type == "customer.subscription.updated":
                        if obj.get("cancel_at_period_end"):
                            nguoi_s.trang_thai_billing = "canceling"
                        elif str(obj.get("status") or "") == "active":
                            nguoi_s.trang_thai_billing = "active"
                    await session.commit()
            await tt.finalize_event(session, event_row_id, match_type="matched", processed=True)
            return {"received": True, "handled": event_type}

        await tt.finalize_event(session, event_row_id, match_type="ignored", processed=True)
        return {"received": True, "ignored": event_type}

    # =========================================================================
    # D. PAYPAL ORDERS API v2 & WEBHOOK (§3.3, §12.4)
    # =========================================================================

    @router.post("/thanh-toan/paypal/create-order", response_model=PayPalCreateOrderResponse, tags=["thanh-toan"])
    async def tao_don_paypal_v2(
        body: PayPalCreateOrderRequest,
        session: AsyncSession = Depends(get_session),
        settings: Settings = Depends(get_settings),
        nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
    ) -> PayPalCreateOrderResponse:
        cfg = tt.resolve_payment_config(settings)
        if not cfg.get("paypal_enabled"):
            raise HTTPException(status_code=503, detail="Cổng thanh toán PayPal Orders v2 hiện đang tạm tắt.")

        order, item = await tt.create_payment_order(
            session,
            nguoi=nguoi,
            plan_code=body.plan,
            rail="paypal",
            settings=settings,
        )
        return_url = _safe_frontend_return_url(
            body.return_url,
            settings.frontend_site_url,
            f"/?payment=paypal_return&order_id={order.id}",
        )
        cancel_url = _safe_frontend_return_url(
            body.cancel_url,
            settings.frontend_site_url,
            f"/?payment=paypal_cancel&order_id={order.id}",
        )
        pp_res = await tt.create_paypal_v2_order(
            order=order,
            item=item,
            return_url=return_url,
            cancel_url=cancel_url,
            settings=settings,
        )
        order.provider_ref = pp_res["paypal_order_id"]
        await session.commit()
        await session.refresh(order)
        return PayPalCreateOrderResponse(
            order=_order_to_read(order, cfg=cfg, plan_name=item.name),
            paypal_order_id=pp_res["paypal_order_id"],
            approve_url=pp_res["approve_url"],
        )

    @router.post(
        "/thanh-toan/paypal/orders/{order_id}/capture",
        response_model=PayPalCaptureOrderResponse,
        tags=["thanh-toan"],
    )
    async def capture_don_paypal_v2(
        order_id: uuid.UUID,
        session: AsyncSession = Depends(get_session),
        settings: Settings = Depends(get_settings),
        nguoi: NguoiDung = Depends(nguoi_dung_hien_tai),
    ) -> PayPalCaptureOrderResponse:
        """Capture PayPal Orders v2 chuẩn §12.4:
        - CHỈ nhận `order_id` NỘI BỘ của chính user đang đăng nhập (của người khác -> 404).
        - Đọc `paypal_order_id` từ `order.provider_ref` đã lưu trên server.
        - Đủ 5 phép kiểm + `claim_event('paypal_capture', capture.id)` + `activate_order()`.
        """
        order = await session.get(PaymentOrder, order_id)
        if order is None or order.user_id != nguoi.id:
            raise HTTPException(status_code=404, detail="Không tìm thấy đơn thanh toán.")

        cfg = tt.resolve_payment_config(settings)
        if not cfg.get("paypal_enabled"):
            raise HTTPException(
                status_code=503,
                detail="Thiếu cấu hình PayPal Orders v2 hoặc danh tính merchant.",
            )

        if order.rail != "paypal" or not order.provider_ref:
            raise HTTPException(status_code=400, detail="Đơn này không gắn với giao dịch PayPal hợp lệ.")

        if order.status == "paid":
            return PayPalCaptureOrderResponse(
                ok=True,
                status=order.status,
                detail="already_paid",
                order=_order_to_read(order, cfg=cfg),
            )

        odata = await tt.capture_or_get_paypal_order(order.provider_ref, cfg)
        pu_list = odata.get("purchase_units") if isinstance(odata.get("purchase_units"), list) else []
        pu = pu_list[0] if pu_list and isinstance(pu_list[0], dict) else {}
        captures = (((pu.get("payments") or {}).get("captures")) if isinstance(pu.get("payments"), dict) else None) or []
        cap = captures[0] if captures and isinstance(captures[0], dict) else {}

        async def _fail_capture(reason: str) -> None:
            if str(odata.get("status") or "").upper() == "COMPLETED":
                await session.execute(
                    update(PaymentOrder)
                    .where(PaymentOrder.id == order.id, PaymentOrder.status == "pending")
                    .values(
                        status="needs_manual_review",
                        admin_note=f"PayPal capture discrepancy: {reason}",
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                await session.commit()
                await session.refresh(order)
            await tt.record_review_and_alert(
                session,
                provider="paypal_capture",
                reason=reason,
                provider_event_id=str(cap.get("id") or order.provider_ref),
                order=order,
                raw_payload={"paypal_order_id": order.provider_ref, "status": odata.get("status")},
                settings=settings,
            )
            raise HTTPException(status_code=400, detail=f"PayPal capture verification failed: {reason}")

        if str(odata.get("status") or "").upper() != "COMPLETED":
            await _fail_capture("order_status_not_completed")
        if not cap or str(cap.get("status") or "").upper() != "COMPLETED" or not cap.get("id"):
            await _fail_capture("capture_missing_or_incomplete")

        cap_id = str(cap["id"]).strip()
        if str(pu.get("custom_id") or "").strip() != str(order.id):
            await _fail_capture("custom_id_mismatch")

        payee_obj = pu.get("payee") if isinstance(pu.get("payee"), dict) else (cap.get("payee") if isinstance(cap.get("payee"), dict) else None)
        if not tt.paypal_payee_matches(payee_obj, cfg.get("paypal_email", ""), cfg.get("paypal_merchant_id", "")):
            await _fail_capture("payee_mismatch")

        cap_amt = cap.get("amount") if isinstance(cap.get("amount"), dict) else {}
        cap_currency = str(cap_amt.get("currency_code") or "").strip().upper()
        if cap_currency != order.currency.upper():
            await _fail_capture("currency_mismatch")

        cents = tt.parse_minor_units(cap_amt.get("value"), exponent=2)
        if cents is None:
            await _fail_capture("unparseable_capture_amount")

        claim_state, event_row_id = await tt.claim_event(
            session,
            "paypal_capture",
            cap_id,
            event_type="PAYMENT.CAPTURE.COMPLETED",
            amount=cents,
            currency=cap_currency,
            raw_payload={"paypal_order_id": order.provider_ref, "capture_id": cap_id},
        )
        if claim_state == "duplicate":
            await session.refresh(order)
            return PayPalCaptureOrderResponse(
                ok=order.status == "paid",
                status=order.status,
                detail="duplicate_capture",
                order=_order_to_read(order, cfg=cfg),
            )

        activated, outcome = await tt.activate_order(
            session,
            order_id=order.id,
            paid_amount=cents,
            currency=cap_currency,
            provider="paypal_capture",
            provider_event_id=cap_id,
            provider_ref=cap_id,
            evidence={"paypal_order_id": order.provider_ref, "capture_id": cap_id},
            settings=settings,
        )
        await tt.finalize_event(
            session,
            event_row_id,
            match_type="matched" if activated else outcome,
            processed=True,
            order_id=order.id,
            amount=cents,
            currency=cap_currency,
            error=None if activated else outcome,
        )
        await session.refresh(order)
        return PayPalCaptureOrderResponse(
            ok=activated,
            status=order.status,
            detail=outcome,
            order=_order_to_read(order, cfg=cfg),
        )

    @router_khach.post("/thanh-toan/webhook/paypal", tags=["thanh-toan"])
    async def webhook_paypal_v2(
        request: Request,
        session: AsyncSession = Depends(get_session),
        settings: Settings = Depends(get_settings),
    ) -> dict[str, Any]:
        """Lưới an toàn PayPal Webhook (`PAYMENT.CAPTURE.COMPLETED`) xác minh qua `verify-webhook-signature`."""
        cfg = tt.resolve_payment_config(settings)
        if not cfg.get("paypal_enabled") or not cfg.get("paypal_webhook_id"):
            raise HTTPException(status_code=503, detail="PayPal webhook chưa được cấu hình đầy đủ.")

        raw_body = await _read_bounded_raw_body(request)
        try:
            event = json.loads(raw_body.decode("utf-8"))
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid PayPal JSON") from exc
        if not isinstance(event, dict):
            raise HTTPException(status_code=400, detail="Invalid PayPal event")

        if not await tt.verify_paypal_webhook_signature(headers=request.headers, event_body=event, cfg=cfg):
            raise HTTPException(status_code=401, detail="PayPal webhook signature verification failed")

        event_id = str(event.get("id") or "").strip()
        event_type = str(event.get("event_type") or "").strip()
        resource = event.get("resource") if isinstance(event.get("resource"), dict) else {}
        if not event_id or not event_type:
            raise HTTPException(status_code=400, detail="Missing PayPal event id/type")

        claim_state, event_row_id = await tt.claim_event(
            session,
            "paypal_webhook",
            event_id,
            event_type=event_type,
            raw_payload={"id": event_id, "event_type": event_type, "resource_id": resource.get("id")},
        )
        if claim_state == "duplicate":
            return {"received": True, "duplicate": True}

        if event_type == "PAYMENT.CAPTURE.COMPLETED":
            cap_id = str(resource.get("id") or "").strip()
            if cap_id:
                cap_state, _ = await tt.claim_event(
                    session,
                    "paypal_capture",
                    cap_id,
                    event_type=event_type,
                    raw_payload={"webhook_event_id": event_id, "capture_id": cap_id},
                )
                if cap_state == "duplicate":
                    await tt.finalize_event(session, event_row_id, match_type="duplicate_capture", processed=True)
                    return {"received": True, "duplicate": True}
            custom_id = str(resource.get("custom_id") or "").strip()
            amt_obj = resource.get("amount") if isinstance(resource.get("amount"), dict) else {}
            currency = str(amt_obj.get("currency_code") or "").strip().upper()
            cents = tt.parse_minor_units(amt_obj.get("value"), exponent=2)

            payee_obj = resource.get("payee") if isinstance(resource.get("payee"), dict) else None
            if payee_obj is not None and not tt.paypal_payee_matches(
                payee_obj, cfg.get("paypal_email", ""), cfg.get("paypal_merchant_id", "")
            ):
                await tt.record_review_and_alert(
                    session,
                    provider="paypal_webhook",
                    reason="payee_mismatch",
                    provider_event_id=event_id,
                    event_type=event_type,
                    order_id=custom_id or None,
                    amount=cents,
                    currency=currency or None,
                    raw_payload={"capture_id": cap_id},
                    settings=settings,
                )
                await tt.finalize_event(session, event_row_id, match_type="needs_manual_review", processed=True, error="payee_mismatch")
                return {"received": True, "outcome": "needs_manual_review"}

            try:
                order_uuid = uuid.UUID(custom_id) if custom_id else None
            except ValueError:
                order_uuid = None

            if order_uuid is None or cents is None:
                await tt.record_review_and_alert(
                    session,
                    provider="paypal_webhook",
                    reason="missing_or_invalid_custom_id_or_amount",
                    provider_event_id=event_id,
                    event_type=event_type,
                    order_id=custom_id or None,
                    amount=cents,
                    currency=currency or None,
                    raw_payload={"capture_id": cap_id, "custom_id": custom_id},
                    settings=settings,
                )
                await tt.finalize_event(session, event_row_id, match_type="needs_manual_review", processed=True, error="invalid_custom_id_or_amount")
                return {"received": True, "outcome": "needs_manual_review"}

            activated, outcome = await tt.activate_order(
                session,
                order_id=order_uuid,
                paid_amount=cents,
                currency=currency,
                provider="paypal_webhook",
                provider_event_id=event_id,
                provider_ref=cap_id or event_id,
                evidence={"paypal_event_id": event_id, "capture_id": cap_id},
                settings=settings,
            )
            await tt.finalize_event(
                session,
                event_row_id,
                match_type="matched" if activated else outcome,
                processed=True,
                order_id=order_uuid,
                amount=cents,
                currency=currency,
                error=None if activated else outcome,
            )
            return {"received": True, "activated": activated, "outcome": outcome}

        await tt.finalize_event(session, event_row_id, match_type="ignored", processed=True)
        return {"received": True, "ignored": event_type}

    # =========================================================================
    # E. QUẢN TRỊ CẤU HÌNH CỔNG & HÀNG CHỜ DUYỆT TAY (§5, §7, §8)
    # =========================================================================

    def _build_admin_cfg_response(
        cfg: dict[str, Any],
        *,
        thong_diep: str,
        schema_status: dict[str, Any],
        telegram_health: dict[str, Any],
        paypal_health: dict[str, Any] | None = None,
        don_gia: int,
    ) -> QuanTriCauHinhThanhToanResponse:
        warnings: list[str] = []
        for mode_label, flag in (("lần đầu", False), ("gia hạn", True)):
            items_check = tt.catalog(
                da_tung_nap=flag,
                don_gia_vnd=don_gia,
                overrides=cfg.get("price_overrides"),
                include_legacy_packs=False,
            )
            for c1, c2, v1, v2 in tt.find_duplicate_vnd_prices(items_check, tolerance_vnd=1000):
                warnings.append(f"Cảnh báo trùng vùng giá ({mode_label}): {c1} ({v1:,}đ) và {c2} ({v2:,}đ)")

        return QuanTriCauHinhThanhToanResponse(
            ok=True,
            thong_diep=thong_diep,
            ngan_hang_ten=cfg["ngan_hang_ten"],
            ngan_hang_so_tk=cfg["ngan_hang_so_tk"],
            ngan_hang_chu_tk=cfg["ngan_hang_chu_tk"],
            sepay_configured=bool(cfg["sepay_configured"]),
            sepay_masked=cfg["sepay_masked"],
            sepay_allow_apikey_auth=bool(cfg["sepay_allow_apikey_auth"]),
            stripe_enabled=bool(cfg["stripe_enabled"]),
            stripe_secret_configured=bool(cfg["stripe_secret_configured"]),
            stripe_secret_masked=cfg["stripe_secret_masked"],
            stripe_webhook_configured=bool(cfg["stripe_webhook_configured"]),
            stripe_webhook_masked=cfg["stripe_webhook_masked"],
            stripe_price_map=cfg.get("stripe_price_map") or {},
            paypal_enabled=bool(cfg["paypal_enabled"]),
            paypal_email=cfg["paypal_email"],
            paypal_merchant_id=cfg["paypal_merchant_id"],
            paypal_client_id=cfg["paypal_client_id"],
            paypal_secret_configured=bool(cfg["paypal_secret_configured"]),
            paypal_secret_masked=cfg["paypal_secret_masked"],
            paypal_webhook_id=cfg["paypal_webhook_id"],
            paypal_mode=cfg["paypal_mode"],
            rapidapi_url=cfg["rapidapi_url"],
            rapidapi_proxy_secret_configured=bool(cfg.get("rapidapi_proxy_secret")),
            telegram_configured=bool(cfg["telegram_configured"]),
            telegram_chat_id=cfg["telegram_chat_id"],
            vietqr_enabled=bool(cfg["vietqr_enabled"]),
            price_overrides=cfg.get("price_overrides") or {},
            canh_bao_trung_gia=warnings,
            schema_status=schema_status,
            telegram_health=telegram_health,
            paypal_health=paypal_health
            or {
                "configured": bool(cfg["paypal_client_id"] and cfg["paypal_secret_configured"]),
                "mode": cfg["paypal_mode"],
                "mode_source": cfg.get("paypal_mode_source", ""),
                "client_id_source": cfg.get("paypal_client_id_source", ""),
                "secret_source": cfg.get("paypal_secret_source", ""),
            },
        )

    @router.get(
        "/quan-tri/thanh-toan/cau-hinh",
        response_model=QuanTriCauHinhThanhToanResponse,
        tags=["thanh-toan"],
    )
    async def quan_tri_xem_cau_hinh_thanh_toan(
        check_bot: bool = Query(default=False),
        check_paypal: bool = Query(default=False),
        session: AsyncSession = Depends(get_session),
        settings: Settings = Depends(get_settings),
        nguoi: NguoiDung = Depends(nguoi_dung_phien_dang_nhap),
    ) -> QuanTriCauHinhThanhToanResponse:
        if not nguoi.la_quan_tri:
            raise HTTPException(status_code=403, detail="Chỉ quản trị viên mới được xem cấu hình thanh toán.")
        cfg = tt.resolve_payment_config(settings)
        schema_st = await tt.check_payment_schema_status(session)
        tg_health = await tt.check_telegram_bot_health(settings) if check_bot else {"configured": cfg["telegram_configured"]}
        pp_health = await tt.check_paypal_oauth_health(settings) if check_paypal else None
        return _build_admin_cfg_response(
            cfg,
            thong_diep="Đã tải cấu hình thanh toán hiện hành.",
            schema_status=schema_st,
            telegram_health=tg_health,
            paypal_health=pp_health,
            don_gia=max(1, settings.ty_le_vnd_moi_trang),
        )

    @router.post(
        "/quan-tri/thanh-toan/cau-hinh",
        response_model=QuanTriCauHinhThanhToanResponse,
        tags=["thanh-toan"],
    )
    async def quan_tri_luu_cau_hinh_thanh_toan(
        body: QuanTriCauHinhThanhToanRequest,
        session: AsyncSession = Depends(get_session),
        settings: Settings = Depends(get_settings),
        nguoi: NguoiDung = Depends(nguoi_dung_phien_dang_nhap),
    ) -> QuanTriCauHinhThanhToanResponse:
        """Lưu cấu hình cổng thanh toán & giá ghi đè (§5):
        - Schema `extra='forbid'` (trường lạ -> 422).
        - Chặn lưu hai gói trùng vùng giá VNĐ trên kênh chuyển khoản (422).
        - Ghi xong đọc lại từ kho để xác minh khớp thực tế rồi mới trả kết quả + ghi audit log.
        """
        if not nguoi.la_quan_tri:
            raise HTTPException(status_code=403, detail="Chỉ quản trị viên mới được lưu cấu hình thanh toán.")

        updates: dict[str, Any] = {}
        raw_dump = body.model_dump(exclude_unset=True)
        known_plan_codes = {it.code for it in tt.catalog(da_tung_nap=False, include_legacy_packs=False)}

        if "price_overrides" in raw_dump and body.price_overrides is not None:
            clean_ovr: dict[str, dict[str, int]] = {}
            for plan_code, ovr_model in body.price_overrides.items():
                if plan_code not in known_plan_codes:
                    raise HTTPException(status_code=422, detail=f"Mã gói ghi đè không hợp lệ: {plan_code}")
                d_ovr = {k: int(v) for k, v in ovr_model.model_dump(exclude_none=True).items()}
                if d_ovr:
                    clean_ovr[plan_code] = d_ovr
            # Kiểm trùng giá VNĐ trước khi cho lưu
            for flag in (False, True):
                test_items = tt.catalog(
                    da_tung_nap=flag,
                    don_gia_vnd=max(1, settings.ty_le_vnd_moi_trang),
                    overrides=clean_ovr,
                    include_legacy_packs=False,
                )
                dups = tt.find_duplicate_vnd_prices(test_items, tolerance_vnd=1000)
                if dups:
                    c1, c2, v1, v2 = dups[0]
                    raise HTTPException(
                        status_code=422,
                        detail=f"Hai gói '{c1}' ({v1:,}đ) và '{c2}' ({v2:,}đ) trùng vùng giá chuyển khoản (<= 1.000đ).",
                    )
            updates["price_overrides"] = clean_ovr

        for field_name, val in raw_dump.items():
            if field_name == "price_overrides":
                continue
            updates[field_name] = val

        read_back_store = tt.write_dynamic_payment_store(updates)
        # Xác minh giá trị đọc lại từ kho khớp với dữ liệu vừa ghi (với các trường không bị biến môi trường đè)
        for k_chk, v_chk in updates.items():
            if v_chk is not None and isinstance(v_chk, (str, dict, bool)):
                expected_v = v_chk.strip() if isinstance(v_chk, str) else v_chk
                if read_back_store.get(k_chk) != expected_v:
                    raise HTTPException(status_code=500, detail=f"Read-back verification failed for field '{k_chk}'")

        nhat_ky_quan_tri.ghi_nhat_ky(
            session,
            nguoi,
            "luu_cau_hinh_thanh_toan",
            updates.get("ngan_hang_ten") or updates.get("paypal_email") or "payment_gateways",
            fields_updated=sorted(list(updates.keys())),
        )
        await session.commit()

        cfg = tt.resolve_payment_config(settings)
        schema_st = await tt.check_payment_schema_status(session)
        tg_health = {"configured": cfg["telegram_configured"]}
        return _build_admin_cfg_response(
            cfg,
            thong_diep="Đã lưu và đối chiếu lại cấu hình thanh toán từ kho lưu trữ.",
            schema_status=schema_st,
            telegram_health=tg_health,
            don_gia=max(1, settings.ty_le_vnd_moi_trang),
        )

    @router.get(
        "/quan-tri/thanh-toan/duyet-tay",
        response_model=list[PaymentReviewRead],
        tags=["thanh-toan"],
    )
    async def quan_tri_danh_sach_duyet_tay(
        status: str = Query(default="needs_manual_review", max_length=32),
        limit: int = Query(default=100, ge=1, le=300),
        session: AsyncSession = Depends(get_session),
        nguoi: NguoiDung = Depends(nguoi_dung_phien_dang_nhap),
    ) -> list[PaymentReviewRead]:
        """Danh sách hàng chờ 'Giao dịch cần duyệt tay' cho trang Admin (§7)."""
        if not nguoi.la_quan_tri:
            raise HTTPException(status_code=403, detail="Chỉ quản trị viên mới được xem hàng chờ duyệt tay.")
        stmt = select(PaymentReview).order_by(PaymentReview.created_at.desc()).limit(limit)
        if status and status != "all":
            stmt = stmt.where(PaymentReview.status == status)
        rows = (await session.execute(stmt)).scalars().all()
        return [_review_to_read(r) for r in rows]

    @router.post(
        "/quan-tri/thanh-toan/duyet-tay/{review_id}",
        response_model=PaymentReviewRead,
        tags=["thanh-toan"],
    )
    async def quan_tri_xu_ly_duyet_tay(
        review_id: uuid.UUID,
        body: XuLyPaymentReviewRequest,
        session: AsyncSession = Depends(get_session),
        settings: Settings = Depends(get_settings),
        nguoi: NguoiDung = Depends(nguoi_dung_phien_dang_nhap),
    ) -> PaymentReviewRead:
        """Admin kích hoạt tay hoặc đánh dấu đã xử lý / hoàn tiền một bản ghi `payment_reviews` (§7)."""
        if not nguoi.la_quan_tri:
            raise HTTPException(status_code=403, detail="Chỉ quản trị viên mới được duyệt giao dịch.")

        review = await session.get(PaymentReview, review_id)
        if review is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi duyệt tay.")
        if review.status == "resolved":
            raise HTTPException(status_code=409, detail="Bản ghi này đã được xử lý trước đó.")

        now_dt = datetime.now(timezone.utc)
        note_clean = body.ghi_chu.strip() or f"Xử lý bởi {nguoi.email} ({body.hanh_dong})"

        order: PaymentOrder | None = None
        if review.order_id:
            try:
                order = await session.get(PaymentOrder, uuid.UUID(review.order_id))
            except ValueError:
                order = None
        if order is None and review.order_code:
            order = (
                await session.execute(select(PaymentOrder).where(PaymentOrder.code == review.order_code))
            ).scalar_one_or_none()

        if body.hanh_dong == "kich_hoat":
            target_user: NguoiDung | None = None
            if body.user_email_override:
                target_user = (
                    await session.execute(
                        select(NguoiDung).where(NguoiDung.email == body.user_email_override.strip().lower())
                    )
                ).scalar_one_or_none()
            elif order is not None and order.user_id is not None:
                target_user = await session.get(NguoiDung, order.user_id)
            elif review.user_id:
                try:
                    target_user = await session.get(NguoiDung, uuid.UUID(review.user_id))
                except ValueError:
                    target_user = None
            elif review.user_email:
                target_user = (
                    await session.execute(
                        select(NguoiDung).where(NguoiDung.email == review.user_email.strip().lower())
                    )
                ).scalar_one_or_none()

            if target_user is None:
                raise HTTPException(
                    status_code=422,
                    detail="Chưa xác định được tài khoản nhận gói. Vui lòng nhập email khách hàng ở ô ghi đè.",
                )

            cfg = tt.resolve_payment_config(settings)
            all_items = {
                it.code: it
                for it in tt.catalog(
                    da_tung_nap=False,
                    don_gia_vnd=max(1, settings.ty_le_vnd_moi_trang),
                    overrides=cfg.get("price_overrides"),
                )
            }
            plan_code = (body.plan_override or (order.plan if order else "") or (review.target_tier or "")).strip()
            plan_item = all_items.get(plan_code)
            if plan_item is None and order is not None:
                # Dùng thông số đã chốt sẵn trên đơn nội bộ
                tier_rank = order.tier_rank
                credits = order.credits
                duration_days = order.duration_days
                plan_code = order.plan
            elif plan_item is not None:
                tier_rank = plan_item.tier_rank
                credits = plan_item.credits
                duration_days = plan_item.duration_days
                plan_code = plan_item.code
            else:
                raise HTTPException(
                    status_code=422,
                    detail="Chưa xác định được mã gói để kích hoạt. Vui lòng chọn gói cước cần cấp.",
                )

            await tt.grant(
                session,
                user_id=target_user.id,
                plan_code=plan_code,
                tier_rank=tier_rank,
                credits=credits,
                duration_days=duration_days,
                source_ref=f"manual_review_{review.id}",
                allow_admin_override_downgrade=True,
                now=now_dt,
            )
            if order is not None:
                order.status = "paid"
                order.activated_at = now_dt
                order.paid_at = order.paid_at or now_dt
                if review.amount is not None and order.paid_amount is None:
                    order.paid_amount = review.amount
                order.admin_note = note_clean[:500]
                order.updated_at = now_dt

        elif body.hanh_dong == "hoan_tien":
            if order is not None and order.status in ("needs_manual_review", "underpaid", "expired_late_payment"):
                order.status = "refunded"
                order.admin_note = note_clean[:500]
                order.updated_at = now_dt

        review.status = "resolved"
        review.resolved_by = nguoi.email
        review.resolved_at = now_dt
        review.resolution_note = note_clean
        nhat_ky_quan_tri.ghi_nhat_ky(
            session,
            nguoi,
            f"duyet_tay_{body.hanh_dong}",
            review.order_code or str(review.id),
            review_id=str(review.id),
            reason=review.reason,
            note=note_clean,
        )
        await session.commit()
        await session.refresh(review)
        return _review_to_read(review)
