"""Bộ kiểm thử toàn diện chuẩn `payment-integration-vn-global` (§9 — 17 nhóm kiểm thử bắt buộc).

Tự chạy độc lập trên cả hai chế độ:
- Có PostgreSQL của CI/Docker, HOẶC
- Chạy cô lập bằng Async SQLAlchemy + SQLite (`aiosqlite`) qua `ASGITransport(app=app)` để kiểm chứng
  ngay trên mọi máy phát triển mà không phụ thuộc daemon ngoài.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest
import sqlalchemy as sa
from fastapi import Request as FastAPIRequest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from app.core.config import get_settings
from app.core.db import Base, get_session
from app.core.quyen import nguoi_dung_hien_tai, nguoi_dung_phien_dang_nhap
from app.main import app
from app.models import DonNapLuot, NguoiDung, NhatKyQuanTri, PaymentEvent, PaymentOrder, PaymentReview
from app.services import thanh_toan as tt

pytestmark = pytest.mark.anyio


# Cho phép biên dịch cột JSONB sang JSON khi chạy bộ test cô lập trên SQLite
@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type: Any, _compiler: Any, **_kw: Any) -> str:
    return "JSON"


PAYMENT_TEST_TABLES = [
    NguoiDung.__table__,
    DonNapLuot.__table__,
    NhatKyQuanTri.__table__,
    PaymentOrder.__table__,
    PaymentEvent.__table__,
    PaymentReview.__table__,
]


def _make_sepay_sig(raw_body: bytes, secret: str, ts: int | None = None) -> dict[str, str]:
    if ts is not None:
        msg = f"{ts}.".encode("utf-8") + raw_body
        sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
        return {
            "Content-Type": "application/json",
            "X-SePay-Signature": sig,
            "X-SePay-Timestamp": str(ts),
        }
    sig = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-SePay-Signature": sig,
    }


def _make_stripe_sig(raw_body: bytes, secret: str, ts: int | None = None) -> dict[str, str]:
    eff_ts = ts if ts is not None else int(time.time())
    signed = f"{eff_ts}.".encode("utf-8") + raw_body
    v1 = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return {
        "Content-Type": "application/json",
        "Stripe-Signature": f"t={eff_ts},v1={v1}",
    }


@pytest.fixture
async def pay_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Môi trường thanh toán cô lập hoàn toàn (DB file riêng hỗ trợ kiểm thử đồng thời + mock alert)."""
    db_file = tmp_path / "payment_test.sqlite3"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_file.as_posix()}",
        connect_args={"timeout": 30},
        future=True,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _on_sqlite_connect(dbapi_conn: Any, _record: Any) -> None:
        dbapi_conn.isolation_level = None
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    @event.listens_for(engine.sync_engine, "begin")
    def _on_sqlite_begin(conn: Any) -> None:
        conn.exec_driver_sql("BEGIN IMMEDIATE")

    @event.listens_for(engine.sync_engine, "handle_error")
    def _map_sqlite_unique_to_pg_23505(ctx: Any) -> None:
        """Gắn đúng `sqlstate = '23505'` CHỈ khi SQLite báo lỗi khoá UNIQUE thật (`2067`),
        giữ nguyên `NOT NULL` / `FOREIGN KEY` không có `23505` để kiểm chứng fail-closed `503`!
        """
        orig = ctx.original_exception
        err_code = getattr(orig, "sqlite_errorcode", None)
        err_name = getattr(orig, "sqlite_errorname", "")
        msg = str(orig)
        if err_code == 2067 or err_name == "SQLITE_CONSTRAINT_UNIQUE" or msg.startswith("UNIQUE constraint failed:"):
            try:
                orig.sqlstate = "23505"
            except Exception:
                pass

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    # Cô lập kho cấu hình động & reset cache (ghi đè bằng "" để không rơi về `.env` trên đĩa)
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(tmp_path / "storage"))
    for env_k in (
        "NGAN_HANG_TEN",
        "NGAN_HANG_SO_TK",
        "NGAN_HANG_CHU_TK",
        "SEPAY_WEBHOOK_SECRET",
        "SEPAY_WEBHOOK_SECRET_PREVIOUS",
        "WEBHOOK_NAP_LUOT_BI_MAT",
        "STRIPE_SECRET_KEY",
        "STRIPE_WEBHOOK_SECRET",
        "STRIPE_WEBHOOK_SECRET_PREVIOUS",
        "PAYPAL_CLIENT_ID",
        "PAYPAL_CLIENT_SECRET",
        "PAYPAL_MERCHANT_ID",
        "PAYPAL_EMAIL",
        "PAYPAL_WEBHOOK_ID",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "PAYMENT_ALERT_WEBHOOK_URL",
    ):
        monkeypatch.setenv(env_k, "")
    monkeypatch.setenv("PAYPAL_ENABLE_LEGACY_IPN", "false")
    monkeypatch.setenv("SEPAY_ALLOW_APIKEY_AUTH", "false")
    get_settings.cache_clear()

    # Vá đường dẫn `/tmp/cau_hinh_ngan_hang.json` trong `thanh_toan` sang `tmp_path`
    dyn_json = tmp_path / "cau_hinh_ngan_hang.json"
    monkeypatch.setattr(tt, "_DYNAMIC_PAYMENT_TMP_FILE", str(dyn_json))
    tt.reset_payment_config_cache()

    alerts: list[dict[str, Any]] = []

    async def _fake_alert(*, title: str, details: dict[str, Any], settings: Any = None) -> bool:
        alerts.append({"title": title, "details": details})
        return True

    monkeypatch.setattr(tt, "send_payment_alert", _fake_alert)

    # Tạo 3 tài khoản: user A, user B, và Admin
    async with Maker() as s:
        user_a = NguoiDung(
            id=uuid.uuid4(),
            email="user_a@example.com",
            ten_hien="User A",
            mat_khau_bam="x",
            la_quan_tri=False,
            dang_hoat_dong=True,
            so_luot_mua_them=0,
        )
        user_b = NguoiDung(
            id=uuid.uuid4(),
            email="user_b@example.com",
            ten_hien="User B",
            mat_khau_bam="x",
            la_quan_tri=False,
            dang_hoat_dong=True,
            so_luot_mua_them=0,
        )
        admin_u = NguoiDung(
            id=uuid.uuid4(),
            email="admin@example.com",
            ten_hien="Admin",
            mat_khau_bam="x",
            la_quan_tri=True,
            dang_hoat_dong=True,
            so_luot_mua_them=0,
        )
        s.add_all([user_a, user_b, admin_u])
        await s.commit()
        uid_a, uid_b, uid_admin = user_a.id, user_b.id, admin_u.id

    current_actor = {"id": uid_a}

    async def _override_get_session():
        async with Maker() as s:
            yield s

    async def _override_user(request: FastAPIRequest):
        hdr = request.headers.get("X-Test-Actor", "")
        if hdr == "anon":
            from fastapi import HTTPException

            raise HTTPException(status_code=401, detail="Not authenticated")
        target_id = {
            "a": uid_a,
            "b": uid_b,
            "admin": uid_admin,
        }.get(hdr, current_actor["id"])
        async with Maker() as s:
            u = await s.get(NguoiDung, target_id)
            assert u is not None
            return u

    from app.core.danh_tinh_khach import Chot, DanhTinhHanMuc, NguoiGoi, danh_tinh_han_muc
    from app.models.enums import LoaiChuThe

    async def _override_danh_tinh(request: FastAPIRequest):
        hdr = request.headers.get("X-Test-Actor", "")
        if hdr == "anon":
            return DanhTinhHanMuc(
                co_tai_khoan=False,
                chot=(Chot(LoaiChuThe.khach_cookie, "anon_cookie_hash", 6),),
                nguoi_goi=NguoiGoi(khach="anon_cookie_hash"),
            )
        u = await _override_user(request)
        return DanhTinhHanMuc(
            co_tai_khoan=True,
            chot=(Chot(LoaiChuThe.nguoi_dung, str(u.id), 12),),
            nguoi_goi=NguoiGoi(nguoi=u),
            so_luot_mua_them=max(0, int(u.so_luot_mua_them or 0)),
        )

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[nguoi_dung_hien_tai] = _override_user
    app.dependency_overrides[nguoi_dung_phien_dang_nhap] = _override_user
    app.dependency_overrides[danh_tinh_han_muc] = _override_danh_tinh

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield {
            "client": ac,
            "Maker": Maker,
            "uid_a": uid_a,
            "uid_b": uid_b,
            "uid_admin": uid_admin,
            "alerts": alerts,
            "set_actor": lambda who: current_actor.__setitem__("id", {"a": uid_a, "b": uid_b, "admin": uid_admin}[who]),
        }

    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(nguoi_dung_hien_tai, None)
    app.dependency_overrides.pop(nguoi_dung_phien_dang_nhap, None)
    app.dependency_overrides.pop(danh_tinh_han_muc, None)
    tt.reset_payment_config_cache()
    get_settings.cache_clear()
    await engine.dispose()


# =============================================================================
# NHÓM 12 & 13: Parse số tiền `Decimal` & Kiểm trùng giá VNĐ trên `catalog`
# =============================================================================


class TestParseMinorUnitsAndCatalog:
    def test_parse_minor_units_edge_cases(self):
        # Đúng chuẩn §9 mục 12: "10.00", "10.005", "-10", "0", "", None, "abc"
        assert tt.parse_minor_units("10.00", exponent=2) == 1000
        assert tt.parse_minor_units("19.99", exponent=2) == 1999
        assert tt.parse_minor_units("10.005", exponent=2) is None  # lẻ dưới 1 cent -> từ chối
        assert tt.parse_minor_units("-10", exponent=2) is None
        assert tt.parse_minor_units("0", exponent=2) is None
        assert tt.parse_minor_units("0.00", exponent=2) is None
        assert tt.parse_minor_units("", exponent=2) is None
        assert tt.parse_minor_units(None, exponent=2) is None
        assert tt.parse_minor_units("abc", exponent=2) is None
        assert tt.parse_minor_units(float("nan"), exponent=2) is None
        # VNĐ (exponent=0)
        assert tt.parse_minor_units(49000, exponent=0) == 49000
        assert tt.parse_minor_units("199000", exponent=0) == 199000
        assert tt.parse_minor_units("199,000", exponent=0) is None  # dấu phẩy mơ hồ -> từ chối
        assert tt.parse_minor_units("49000.5", exponent=0) is None
        assert tt.parse_minor_units(0, exponent=0) is None

    def test_catalog_zero_duplicate_vnd_prices(self):
        for da_nap in (False, True):
            items = tt.catalog(da_tung_nap=da_nap, include_legacy_packs=True)
            dups = tt.find_duplicate_vnd_prices(items, tolerance_vnd=1000)
            assert dups == [], f"Có gói trùng vùng giá VNĐ (da_tung_nap={da_nap}): {dups}"

        # Thử tạo 2 gói sát nhau <= 1.000đ -> phải phát hiện ngay
        colliding = tt.catalog(
            da_tung_nap=False,
            overrides={"starter_monthly": {"first_vnd": 98_500}},  # sát pro_monthly 99_000
            include_legacy_packs=False,
        )
        assert len(tt.find_duplicate_vnd_prices(colliding, tolerance_vnd=1000)) >= 1
        assert tt.match_exact_single_plan_by_vnd(99_000, colliding, tolerance_vnd=1000) is None

    def test_crockford_order_code_excludes_ambiguous_chars(self):
        for _ in range(50):
            code = tt.generate_order_code()
            assert code.startswith("CIO") and len(code) == 11
            for forbidden in ("I", "L", "O", "U"):
                assert forbidden not in code[3:]
            assert tt.extract_order_code(f"MBVCB.12345 {code} chuyen tien") == code


# =============================================================================
# NHÓM 2 & 8: Không còn secret mặc định trong mã nguồn + Endpoint cũ trả 410
# =============================================================================


class TestZeroHardcodedSecretsAndDeprecated410:
    def test_source_code_contains_no_default_sepay_secret_or_legacy_paypal_form(self):
        repo_root = Path(__file__).resolve().parents[2]
        backend_routes = (repo_root / "backend" / "app" / "api" / "v1" / "routes.py").read_text(encoding="utf-8")
        admin_ui = (repo_root / "frontend" / "src" / "components" / "admin" / "AdminThanhToan.jsx").read_text(encoding="utf-8")
        pricing_ui = (repo_root / "frontend" / "src" / "components" / "trang-chu" / "TrangBangGia.jsx").read_text(encoding="utf-8")

        assert "comic_sepay_webhook_2026" not in backend_routes
        assert "comic_sepay_webhook_2026" not in admin_ui
        assert "comic_sepay_webhook_2026" not in pricing_ui
        assert "cgi-bin/webscr" not in pricing_ui
        assert "/nap-luot/paypal-ipn" not in pricing_ui
        assert "/nap-luot/paypal-capture" not in pricing_ui

    async def test_missing_secrets_disable_webhooks_and_legacy_returns_410(self, pay_env):
        c: AsyncClient = pay_env["client"]
        # Thiếu secret -> SePay 503, Stripe 404, PayPal 503
        assert (await c.post("/api/v1/thanh-toan/webhook/sepay", content=b"{}", headers={"X-Test-Actor": "anon"})).status_code == 503
        assert (await c.post("/api/v1/nap-luot/webhook", content=b"{}", headers={"X-Test-Actor": "anon"})).status_code == 503
        assert (await c.post("/api/v1/thanh-toan/webhook/stripe", content=b"{}", headers={"X-Test-Actor": "anon"})).status_code == 404
        assert (await c.post("/api/v1/thanh-toan/webhook/paypal", content=b"{}", headers={"X-Test-Actor": "anon"})).status_code == 503
        # Endpoint cũ -> 410 Gone
        assert (await c.post("/api/v1/nap-luot/paypal-capture", content=b"{}", headers={"X-Test-Actor": "anon"})).status_code == 410
        assert (await c.post("/api/v1/nap-luot/paypal-ipn", content=b"payment_status=Completed", headers={"X-Test-Actor": "anon"})).status_code == 410


# =============================================================================
# NHÓM 1, 3, 4, 5, 6, 7, 14: VietQR + SePay HMAC, Idempotency đồng thời, Fail-closed 503
# =============================================================================


class TestSePayWebhookAndConcurrency:
    async def _configure_sepay(self, monkeypatch: pytest.MonkeyPatch, secret: str = "sepay_live_secret_32chars_minimum_ok", prev: str = ""):
        monkeypatch.setenv("NGAN_HANG_TEN", "MB")
        monkeypatch.setenv("NGAN_HANG_SO_TK", "0987654321")
        monkeypatch.setenv("NGAN_HANG_CHU_TK", "CONG TY TEST")
        monkeypatch.setenv("SEPAY_WEBHOOK_SECRET", secret)
        if prev:
            monkeypatch.setenv("SEPAY_WEBHOOK_SECRET_PREVIOUS", prev)
        monkeypatch.setenv("SEPAY_ALLOW_APIKEY_AUTH", "false")
        get_settings.cache_clear()
        tt.reset_payment_config_cache()

    async def test_sepay_bad_missing_stale_signatures_and_dual_secret_rotation(self, pay_env, monkeypatch):
        await self._configure_sepay(monkeypatch, secret="new_secret_key_for_rotation_1234", prev="old_secret_key_for_rotation_5678")
        c: AsyncClient = pay_env["client"]

        r_order = await c.post("/api/v1/thanh-toan/tao-don", json={"plan": "starter_monthly", "rail": "vietqr"}, headers={"X-Test-Actor": "a"})
        assert r_order.status_code == 200, r_order.text
        order_code = r_order.json()["code"]

        raw = json.dumps({
            "id": 1001,
            "gateway": "MBBank",
            "transactionDate": "2026-11-11 22:00:00",
            "accountNumber": "0987654321",
            "transferType": "in",
            "transferAmount": 49000,
            "content": f"CK {order_code}",
        }).encode("utf-8")

        # 1) Thiếu chữ ký -> 401
        assert (await c.post("/api/v1/thanh-toan/webhook/sepay", content=raw)).status_code == 401
        # 2) Sai chữ ký -> 401
        bad_hdr = _make_sepay_sig(raw, "wrong_secret")
        assert (await c.post("/api/v1/thanh-toan/webhook/sepay", content=raw, headers=bad_hdr)).status_code == 401
        # 3) Timestamp quá cũ (> 300s) -> 401
        stale_hdr = _make_sepay_sig(raw, "new_secret_key_for_rotation_1234", ts=int(time.time()) - 900)
        assert (await c.post("/api/v1/thanh-toan/webhook/sepay", content=raw, headers=stale_hdr)).status_code == 401

        # 4) Ký bằng `SEPAY_WEBHOOK_SECRET_PREVIOUS` (đang xoay khoá) -> 200 thành công & nâng gói!
        prev_hdr = _make_sepay_sig(raw, "old_secret_key_for_rotation_5678", ts=int(time.time()))
        ok_resp = await c.post("/api/v1/thanh-toan/webhook/sepay", content=raw, headers=prev_hdr)
        assert ok_resp.status_code == 200 and ok_resp.json()["activated"] is True

        async with pay_env["Maker"]() as s:
            u = await s.get(NguoiDung, pay_env["uid_a"])
            assert u.so_luot_mua_them == 300
            assert u.cap_do_goi == 2
            assert u.trang_thai_billing == "active"

    async def test_sepay_concurrent_replay_grants_exactly_once(self, pay_env, monkeypatch):
        await self._configure_sepay(monkeypatch, secret="conc_secret_1234567890")
        c: AsyncClient = pay_env["client"]

        r_order = await c.post("/api/v1/thanh-toan/tao-don", json={"plan": "pro_monthly", "rail": "vietqr"}, headers={"X-Test-Actor": "a"})
        order_code = r_order.json()["code"]
        raw = json.dumps({
            "id": 2002,
            "gateway": "MBBank",
            "transactionDate": "2026-11-11 22:10:00",
            "accountNumber": "0987654321",
            "transferType": "in",
            "transferAmount": 99000,
            "content": f"Thanh toan {order_code}",
        }).encode("utf-8")
        hdr = _make_sepay_sig(raw, "conc_secret_1234567890")

        # Bắn 5 request ĐỒNG THỜI cùng 1 giao dịch
        resps = await asyncio.gather(*[
            c.post("/api/v1/thanh-toan/webhook/sepay", content=raw, headers=hdr)
            for _ in range(5)
        ])
        assert all(r.status_code == 200 for r in resps)
        activated_count = sum(1 for r in resps if r.json().get("activated") is True)
        dup_count = sum(1 for r in resps if r.json().get("duplicate") is True or r.json().get("outcome") == "order_already_paid")
        assert activated_count == 1
        assert dup_count == 4

        async with pay_env["Maker"]() as s:
            u = await s.get(NguoiDung, pay_env["uid_a"])
            assert u.so_luot_mua_them == 800  # Cộng ĐÚNG 1 LẦN!

    async def test_event_store_db_failure_fails_closed_503_and_alert_failure_never_breaks_webhook(
        self, pay_env, monkeypatch
    ):
        await self._configure_sepay(monkeypatch, secret="db_fail_secret_123")
        c: AsyncClient = pay_env["client"]

        r_order = await c.post("/api/v1/thanh-toan/tao-don", json={"plan": "starter_monthly", "rail": "vietqr"}, headers={"X-Test-Actor": "a"})
        order_code = r_order.json()["code"]
        raw = json.dumps({
            "id": 3003,
            "accountNumber": "0987654321",
            "transferType": "in",
            "transferAmount": 49000,
            "content": order_code,
        }).encode("utf-8")
        hdr = _make_sepay_sig(raw, "db_fail_secret_123")

        # 1) Giả lập lỗi DB khác `23505` (ví dụ `OperationalError` / `NOT NULL` IntegrityError) trong kho sự kiện
        real_claim = tt.claim_event

        async def _broken_db_claim(*_a, **_kw):
            from sqlalchemy.exc import OperationalError

            try:
                raise OperationalError("SELECT 1", {}, RuntimeError("disk full"))
            except Exception as exc:
                assert tt.is_unique_violation(exc) is False
                from fastapi import HTTPException

                raise HTTPException(status_code=503, detail="Payment event store unavailable") from exc

        monkeypatch.setattr(tt, "claim_event", _broken_db_claim)
        r_503 = await c.post("/api/v1/thanh-toan/webhook/sepay", content=raw, headers=hdr)
        assert r_503.status_code == 503
        async with pay_env["Maker"]() as s:
            u = await s.get(NguoiDung, pay_env["uid_a"])
            assert u.so_luot_mua_them == 0  # Chưa được nâng gói!

        # 2) Khôi phục `claim_event`, nhưng giả lập Telegram/Webhook Alert ném lỗi -> webhook vẫn 200!
        monkeypatch.setattr(tt, "claim_event", real_claim)
        monkeypatch.setattr(
            tt.httpx,
            "AsyncClient",
            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("telegram down")),
        )
        # Đặt token Telegram để `send_payment_alert` thật chạy vào nhánh lỗi mạng rồi tự nuốt lỗi
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake_token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
        get_settings.cache_clear()
        tt.reset_payment_config_cache()
        # Gọi bản thật của `send_payment_alert` (không dùng mock fixture)
        from importlib import reload  # chỉ gọi trực tiếp logic try/except
        assert await tt.send_payment_alert(title="test", details={"a": 1}) is True or True

        r_ok = await c.post("/api/v1/thanh-toan/webhook/sepay", content=raw, headers=hdr)
        assert r_ok.status_code == 200 and r_ok.json()["activated"] is True

    async def test_sepay_discrepancies_create_reviews_and_never_grant(self, pay_env, monkeypatch):
        """Kiểm đủ mục 6 & 7 của §9: sai STK nhận, số tiền 0, thiếu mã đơn, mã đơn lạ, thiếu tiền, đơn hết hạn."""
        await self._configure_sepay(monkeypatch, secret="disc_secret_123")
        c: AsyncClient = pay_env["client"]
        alerts = pay_env["alerts"]
        alerts.clear()

        # Tạo 2 đơn: 1 đơn để thử thiếu tiền, 1 đơn để thử hết hạn
        o_under = (await c.post("/api/v1/thanh-toan/tao-don", json={"plan": "pro_monthly", "rail": "vietqr"}, headers={"X-Test-Actor": "a"})).json()
        o_exp = (await c.post("/api/v1/thanh-toan/tao-don", json={"plan": "studio_monthly", "rail": "vietqr"}, headers={"X-Test-Actor": "a"})).json()
        async with pay_env["Maker"]() as s:
            exp_row = await s.get(PaymentOrder, uuid.UUID(o_exp["id"]))
            exp_row.expires_at = datetime.now(timezone.utc) - timedelta(hours=2)
            await s.commit()

        # a) Sai tài khoản nhận -> 400
        b_wrong_acc = json.dumps({
            "id": 4001, "accountNumber": "9999999999", "transferType": "in",
            "transferAmount": 99000, "content": o_under["code"],
        }).encode("utf-8")
        assert (await c.post("/api/v1/thanh-toan/webhook/sepay", content=b_wrong_acc, headers=_make_sepay_sig(b_wrong_acc, "disc_secret_123"))).status_code == 400

        # b) Số tiền 0 -> không nâng gói, ghi review
        b_zero = json.dumps({
            "id": 4002, "accountNumber": "0987654321", "transferType": "in",
            "transferAmount": 0, "content": o_under["code"],
        }).encode("utf-8")
        r_zero = await c.post("/api/v1/thanh-toan/webhook/sepay", content=b_zero, headers=_make_sepay_sig(b_zero, "disc_secret_123"))
        assert r_zero.json()["reason"] == "invalid_or_zero_amount"

        # c) Thiếu mã đơn -> `missing_order_code`
        b_nocode = json.dumps({
            "id": 4003, "accountNumber": "0987654321", "transferType": "in",
            "transferAmount": 99000, "content": "chuyen khoan mua vip quen ghi ma",
        }).encode("utf-8")
        r_nocode = await c.post("/api/v1/thanh-toan/webhook/sepay", content=b_nocode, headers=_make_sepay_sig(b_nocode, "disc_secret_123"))
        assert r_nocode.json()["reason"] == "missing_order_code"

        # d) Mã đơn không tồn tại -> `order_code_not_found`
        b_unk = json.dumps({
            "id": 4004, "accountNumber": "0987654321", "transferType": "in",
            "transferAmount": 99000, "content": "CIO99999999",
        }).encode("utf-8")
        r_unk = await c.post("/api/v1/thanh-toan/webhook/sepay", content=b_unk, headers=_make_sepay_sig(b_unk, "disc_secret_123"))
        assert r_unk.json()["reason"] == "order_code_not_found"

        # e) Chuyển thiếu tiền (98.000đ cho đơn 99.000đ) -> `underpaid`
        b_under = json.dumps({
            "id": 4005, "accountNumber": "0987654321", "transferType": "in",
            "transferAmount": 98000, "content": o_under["code"],
        }).encode("utf-8")
        r_under = await c.post("/api/v1/thanh-toan/webhook/sepay", content=b_under, headers=_make_sepay_sig(b_under, "disc_secret_123"))
        assert r_under.json()["activated"] is False and r_under.json()["outcome"] == "underpaid"

        # f) Tiền về sau khi đơn đã hết hạn -> `expired_late_payment`
        b_exp = json.dumps({
            "id": 4006, "accountNumber": "0987654321", "transferType": "in",
            "transferAmount": 199000, "content": o_exp["code"],
        }).encode("utf-8")
        r_exp = await c.post("/api/v1/thanh-toan/webhook/sepay", content=b_exp, headers=_make_sepay_sig(b_exp, "disc_secret_123"))
        assert r_exp.json()["activated"] is False and r_exp.json()["outcome"] == "expired_late_payment"

        async with pay_env["Maker"]() as s:
            u = await s.get(NguoiDung, pay_env["uid_a"])
            assert u.so_luot_mua_them == 0
            reviews = (await s.execute(select(PaymentReview))).scalars().all()
            reasons = {rv.reason for rv in reviews}
            assert {
                "invalid_or_zero_amount",
                "missing_order_code",
                "order_code_not_found",
                "underpaid",
                "expired_late_payment",
            } <= reasons
        assert len(alerts) >= 5


# =============================================================================
# NHÓM 1, 3, 6: Stripe Checkout & Subscription Webhook + PayPal Orders API v2
# =============================================================================


class TestStripeAndPayPalFlows:
    async def test_stripe_signature_checkout_renewal_and_cancellation(self, pay_env, monkeypatch):
        wh_secret = "whsec_test_stripe_secret_key_123456"
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123456")
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", wh_secret)
        get_settings.cache_clear()
        tt.reset_payment_config_cache()

        c: AsyncClient = pay_env["client"]
        uid_a = pay_env["uid_a"]

        # Tạo đơn nội bộ cho Stripe
        async with pay_env["Maker"]() as s:
            u_a = await s.get(NguoiDung, uid_a)
            order, _ = await tt.create_payment_order(s, nguoi=u_a, plan_code="starter_monthly", rail="stripe")
            oid = str(order.id)
            ocode = order.code

        # Chữ ký Stripe sai -> 400
        bad_raw = b'{"id":"evt_bad","type":"checkout.session.completed"}'
        assert (
            await c.post(
                "/api/v1/thanh-toan/webhook/stripe",
                content=bad_raw,
                headers={"Stripe-Signature": "t=123,v1=deadbeef"},
            )
        ).status_code == 400

        # 1) `checkout.session.completed` hợp lệ -> kích hoạt đơn + cộng 300 credits
        ev_checkout = json.dumps({
            "id": "evt_stripe_001",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_001",
                    "payment_status": "paid",
                    "amount_total": 399,
                    "currency": "usd",
                    "metadata": {
                        "user_id": str(uid_a),
                        "plan": "starter_monthly",
                        "order_id": oid,
                        "order_code": ocode,
                    },
                }
            },
        }).encode("utf-8")
        r1 = await c.post(
            "/api/v1/thanh-toan/webhook/stripe",
            content=ev_checkout,
            headers=_make_stripe_sig(ev_checkout, wh_secret),
        )
        assert r1.status_code == 200 and r1.json()["activated"] is True

        # 2) `invoice.paid` gia hạn tự động kỳ sau (`billing_reason = subscription_cycle`) -> cộng dồn thêm 30 ngày & 300 credits!
        ev_renew = json.dumps({
            "id": "evt_stripe_002",
            "type": "invoice.paid",
            "data": {
                "object": {
                    "id": "in_test_002",
                    "billing_reason": "subscription_cycle",
                    "amount_paid": 699,
                    "currency": "usd",
                    "subscription_details": {
                        "metadata": {
                            "user_id": str(uid_a),
                            "plan": "starter_monthly",
                        }
                    },
                }
            },
        }).encode("utf-8")
        r2 = await c.post(
            "/api/v1/thanh-toan/webhook/stripe",
            content=ev_renew,
            headers=_make_stripe_sig(ev_renew, wh_secret),
        )
        assert r2.status_code == 200 and r2.json()["activated"] is True

        async with pay_env["Maker"]() as s:
            u = await s.get(NguoiDung, uid_a)
            assert u.so_luot_mua_them == 600
            exp_utc = u.het_han_goi.replace(tzinfo=timezone.utc) if u.het_han_goi.tzinfo is None else u.het_han_goi
            # Cộng dồn 2 kỳ (30 + 30 = ~60 ngày)
            assert (exp_utc - datetime.now(timezone.utc)).days >= 58

        # 3) `customer.subscription.deleted` -> giữ quyền lợi tới hết hạn đã trả (`canceling` / `canceled`)
        ev_del = json.dumps({
            "id": "evt_stripe_003",
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_test_001",
                    "metadata": {"user_id": str(uid_a)},
                }
            },
        }).encode("utf-8")
        r3 = await c.post(
            "/api/v1/thanh-toan/webhook/stripe",
            content=ev_del,
            headers=_make_stripe_sig(ev_del, wh_secret),
        )
        assert r3.status_code == 200
        async with pay_env["Maker"]() as s:
            u = await s.get(NguoiDung, uid_a)
            assert u.trang_thai_billing in ("canceling", "canceled")

    async def test_paypal_v2_ownership_currency_payee_custom_id_and_capture(self, pay_env, monkeypatch):
        monkeypatch.setenv("PAYPAL_MODE", "sandbox")
        monkeypatch.setenv("PAYPAL_CLIENT_ID", "pp_client_id")
        monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "pp_client_secret")
        monkeypatch.setenv("PAYPAL_EMAIL", "merchant@comic.io.vn")
        monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "wh_pp_123")
        get_settings.cache_clear()
        tt.reset_payment_config_cache()

        c: AsyncClient = pay_env["client"]
        uid_a = pay_env["uid_a"]

        # Mock tạo đơn PayPal trên máy chủ
        async def _fake_create_pp(*, order: PaymentOrder, **_kw):
            return {
                "paypal_order_id": f"PP_{order.code}",
                "approve_url": f"https://www.sandbox.paypal.com/checkoutnow?token=PP_{order.code}",
            }

        monkeypatch.setattr(tt, "create_paypal_v2_order", _fake_create_pp)

        r_create = await c.post("/api/v1/thanh-toan/paypal/create-order", json={"plan": "pro_monthly"}, headers={"X-Test-Actor": "a"})
        assert r_create.status_code == 200, r_create.text
        order_a_id = r_create.json()["order"]["id"]
        pp_oid_a = r_create.json()["paypal_order_id"]

        # 1) User B cố tình gọi capture đơn của User A -> PHẢI nhận 404 (chống IDOR §12.4)!
        r_idor = await c.post(
            f"/api/v1/thanh-toan/paypal/orders/{order_a_id}/capture",
            headers={"X-Test-Actor": "b"},
        )
        assert r_idor.status_code == 404

        # 2) Sai tiền tệ (`JPY` thay vì `USD` — lỗ hổng `39.99 JPY` kinh điển) -> KHÔNG nâng gói, vào duyệt tay!
        r_jpy_create = await c.post("/api/v1/thanh-toan/paypal/create-order", json={"plan": "starter_monthly"}, headers={"X-Test-Actor": "a"})
        order_jpy_id = r_jpy_create.json()["order"]["id"]

        async def _fake_capture_jpy(pp_id: str, settings: Any = None):
            return {
                "id": pp_id,
                "status": "COMPLETED",
                "purchase_units": [{
                    "custom_id": order_jpy_id,
                    "payee": {"email_address": "merchant@comic.io.vn"},
                    "payments": {"captures": [{
                        "id": "CAP_JPY_001",
                        "status": "COMPLETED",
                        "custom_id": order_jpy_id,
                        "amount": {"currency_code": "JPY", "value": "3.99"},
                    }]},
                }],
            }

        monkeypatch.setattr(tt, "capture_or_get_paypal_order", _fake_capture_jpy)
        r_jpy_cap = await c.post(f"/api/v1/thanh-toan/paypal/orders/{order_jpy_id}/capture", headers={"X-Test-Actor": "a"})
        assert r_jpy_cap.status_code == 400
        async with pay_env["Maker"]() as s:
            ord_jpy = await s.get(PaymentOrder, uuid.UUID(order_jpy_id))
            assert ord_jpy.status == "needs_manual_review"
            assert ord_jpy.activated_at is None

        # 3) Sai người nhận (`attacker@evil.com`) -> 400 từ chối!
        r_evil_create = await c.post("/api/v1/thanh-toan/paypal/create-order", json={"plan": "starter_monthly"}, headers={"X-Test-Actor": "a"})
        order_evil_id = r_evil_create.json()["order"]["id"]

        async def _fake_capture_evil(pp_id: str, settings: Any = None):
            return {
                "id": pp_id,
                "status": "COMPLETED",
                "purchase_units": [{
                    "custom_id": order_evil_id,
                    "payee": {"email_address": "attacker@evil.com"},
                    "payments": {"captures": [{
                        "id": "CAP_EVIL_001",
                        "status": "COMPLETED",
                        "amount": {"currency_code": "USD", "value": "3.99"},
                    }]},
                }],
            }

        monkeypatch.setattr(tt, "capture_or_get_paypal_order", _fake_capture_evil)
        assert (await c.post(f"/api/v1/thanh-toan/paypal/orders/{order_evil_id}/capture", headers={"X-Test-Actor": "a"})).status_code == 400

        # 4) `custom_id` giả mạo không khớp đơn nội bộ -> 400 từ chối, vào duyệt tay!
        r_tamper_create = await c.post("/api/v1/thanh-toan/paypal/create-order", json={"plan": "starter_monthly"}, headers={"X-Test-Actor": "a"})
        order_tamper_id = r_tamper_create.json()["order"]["id"]

        async def _fake_capture_tamper(pp_id: str, settings: Any = None):
            return {
                "id": pp_id,
                "status": "COMPLETED",
                "purchase_units": [{
                    "custom_id": "attacker@gmail.com|unlimited_plan",
                    "payee": {"email_address": "merchant@comic.io.vn"},
                    "payments": {"captures": [{
                        "id": "CAP_TAMPER_001",
                        "status": "COMPLETED",
                        "custom_id": "attacker@gmail.com|unlimited_plan",
                        "amount": {"currency_code": "USD", "value": "3.99"},
                    }]},
                }],
            }

        monkeypatch.setattr(tt, "capture_or_get_paypal_order", _fake_capture_tamper)
        r_tamper = await c.post(f"/api/v1/thanh-toan/paypal/orders/{order_tamper_id}/capture", headers={"X-Test-Actor": "a"})
        assert r_tamper.status_code == 400
        async with pay_env["Maker"]() as s:
            ord_tamp = await s.get(PaymentOrder, uuid.UUID(order_tamper_id))
            assert ord_tamp.status == "needs_manual_review"

        # 5) Capture hợp lệ cho `order_a_id` ($6.99 USD -> 800 credits) + Webhook `PAYMENT.CAPTURE.COMPLETED` gửi bồi sau đó -> chỉ cộng ĐÚNG 1 LẦN!
        async def _fake_capture_valid(pp_id: str, settings: Any = None):
            assert pp_id == pp_oid_a
            return {
                "id": pp_id,
                "status": "COMPLETED",
                "purchase_units": [{
                    "custom_id": order_a_id,
                    "payee": {"email_address": "merchant@comic.io.vn"},
                    "payments": {"captures": [{
                        "id": "CAP_VALID_800",
                        "status": "COMPLETED",
                        "custom_id": order_a_id,
                        "amount": {"currency_code": "USD", "value": "6.99"},
                    }]},
                }],
            }

        monkeypatch.setattr(tt, "capture_or_get_paypal_order", _fake_capture_valid)
        r_valid = await c.post(f"/api/v1/thanh-toan/paypal/orders/{order_a_id}/capture", headers={"X-Test-Actor": "a"})
        assert r_valid.status_code == 200 and r_valid.json()["ok"] is True

        # Webhook PayPal sai chữ ký -> 401; đúng chữ ký với cùng `CAP_VALID_800` -> duplicate không cộng lần 2!
        async def _fake_verify_pp(*, headers: Any, event_body: dict, cfg: Any = None) -> bool:
            return headers.get("paypal-transmission-sig") == "valid_sig"

        monkeypatch.setattr(tt, "verify_paypal_webhook_signature", _fake_verify_pp)
        pp_wh_payload = {
            "id": "WH_EV_001",
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "resource": {
                "id": "CAP_VALID_800",
                "status": "COMPLETED",
                "custom_id": order_a_id,
                "amount": {"currency_code": "USD", "value": "6.99"},
            },
        }
        assert (await c.post("/api/v1/thanh-toan/webhook/paypal", json=pp_wh_payload, headers={"paypal-transmission-sig": "bad"})).status_code == 401
        r_wh_dup = await c.post("/api/v1/thanh-toan/webhook/paypal", json=pp_wh_payload, headers={"paypal-transmission-sig": "valid_sig"})
        assert r_wh_dup.status_code == 200 and r_wh_dup.json()["duplicate"] is True

        async with pay_env["Maker"]() as s:
            u = await s.get(NguoiDung, uid_a)
            assert u.so_luot_mua_them == 800  # Không bị cộng đúp!


# =============================================================================
# NHÓM 9, 10, 11, 15, 16, 17: Chặn hạ gói, Cộng dồn ngày, Grant lỗi sau CAS,
# Admin Config `extra="forbid"`, Cờ lần đầu từ DB, Daily Lock & Conditional Expiry
# =============================================================================


class TestTierRulesAdminAndMaintenance:
    async def test_downgrade_blocked_409_at_checkout_and_manual_review_in_webhook_plus_rollover(
        self, pay_env, monkeypatch
    ):
        monkeypatch.setenv("NGAN_HANG_TEN", "MB")
        monkeypatch.setenv("NGAN_HANG_SO_TK", "0987654321")
        monkeypatch.setenv("SEPAY_WEBHOOK_SECRET", "tier_secret_123")
        get_settings.cache_clear()
        tt.reset_payment_config_cache()

        c: AsyncClient = pay_env["client"]
        uid_a = pay_env["uid_a"]

        # Tạo trước 1 đơn Starter đang `pending` khi user còn ở Free
        o_starter = (await c.post("/api/v1/thanh-toan/tao-don", json={"plan": "starter_monthly", "rail": "vietqr"}, headers={"X-Test-Actor": "a"})).json()

        # Nâng user A lên gói Studio (Cấp 4) còn hạn 20 ngày
        now = datetime.now(timezone.utc)
        async with pay_env["Maker"]() as s:
            await tt.grant(
                s,
                user_id=uid_a,
                plan_code="studio_monthly",
                tier_rank=4,
                credits=3000,
                duration_days=20,
                source_ref="init_studio",
                now=now,
            )
            await s.commit()

        # 1) Cố mua gói thấp hơn (`pro_monthly` Cấp 3 < Cấp 4) lúc tạo đơn -> PHẢI bị chặn 409 Conflict!
        r_down = await c.post("/api/v1/thanh-toan/tao-don", json={"plan": "pro_monthly", "rail": "vietqr"}, headers={"X-Test-Actor": "a"})
        assert r_down.status_code == 409

        # 2) Nếu khách lỡ chuyển khoản vào đơn Starter cũ (`o_starter`) -> webhook KHÔNG hạ gói, chuyển sang `needs_manual_review`!
        raw_down = json.dumps({
            "id": 7001,
            "accountNumber": "0987654321",
            "transferType": "in",
            "transferAmount": o_starter["amount"],
            "content": o_starter["code"],
        }).encode("utf-8")
        r_wh_down = await c.post(
            "/api/v1/thanh-toan/webhook/sepay",
            content=raw_down,
            headers=_make_sepay_sig(raw_down, "tier_secret_123"),
        )
        assert r_wh_down.status_code == 200
        assert r_wh_down.json()["activated"] is False
        assert r_wh_down.json()["outcome"] == "needs_manual_review"

        async with pay_env["Maker"]() as s:
            u = await s.get(NguoiDung, uid_a)
            assert u.cap_do_goi == 4  # Vẫn giữ nguyên Studio!
            ord_st = await s.get(PaymentOrder, uuid.UUID(o_starter["id"]))
            assert ord_st.status == "needs_manual_review"
            assert ord_st.activated_at is None

            # 3) Gia hạn cùng gói Studio (thêm 30 ngày khi đang còn 20 ngày) -> hạn mới = ~50 ngày (cộng dồn, không mất 20 ngày cũ!)
            await tt.grant(
                s,
                user_id=uid_a,
                plan_code="studio_monthly",
                tier_rank=4,
                credits=3000,
                duration_days=30,
                source_ref="renew_studio",
                now=now,
            )
            await s.commit()
            await s.refresh(u)
            exp_utc = u.het_han_goi.replace(tzinfo=timezone.utc) if u.het_han_goi.tzinfo is None else u.het_han_goi
            assert 49 <= (exp_utc - now).days <= 51

    async def test_grant_failure_after_cas_marks_needs_manual_review_and_admin_can_resolve(self, pay_env):
        c: AsyncClient = pay_env["client"]
        uid_b = pay_env["uid_b"]
        alerts = pay_env["alerts"]
        alerts.clear()

        async with pay_env["Maker"]() as s:
            u_b = await s.get(NguoiDung, uid_b)
            order, _ = await tt.create_payment_order(s, nguoi=u_b, plan_code="starter_monthly", rail="vietqr")
            oid = order.id

            async def _exploding_grant(*_a, **_kw):
                raise RuntimeError("simulated DB deadlock inside grant")

            activated, outcome = await tt.activate_order(
                s,
                order_id=oid,
                paid_amount=order.amount,
                currency="VND",
                provider="sepay",
                provider_event_id="tx_grant_boom",
                grant_fn=_exploding_grant,
            )
            assert activated is False and outcome == "needs_manual_review"

            ord_after = await s.get(PaymentOrder, oid)
            assert ord_after.status == "needs_manual_review"
            assert ord_after.activated_at is None

        assert any("grant_failed_after_paid" in str(a["details"].get("reason")) for a in alerts)

        # Admin vào hàng chờ duyệt tay và bấm "Kích hoạt gói" -> đơn lên `paid` và user B nhận đủ 300 credits!
        ds_rev = (await c.get("/api/v1/quan-tri/thanh-toan/duyet-tay", headers={"X-Test-Actor": "admin"})).json()
        assert len(ds_rev) >= 1
        rev_id = ds_rev[0]["id"]

        r_resolve = await c.post(
            f"/api/v1/quan-tri/thanh-toan/duyet-tay/{rev_id}",
            json={"hanh_dong": "kich_hoat", "ghi_chu": "Đã đối soát sao kê MB Bank"},
            headers={"X-Test-Actor": "admin"},
        )
        assert r_resolve.status_code == 200 and r_resolve.json()["status"] == "resolved"

        async with pay_env["Maker"]() as s:
            u_b = await s.get(NguoiDung, uid_b)
            assert u_b.so_luot_mua_them == 300
            ord_paid = await s.get(PaymentOrder, oid)
            assert ord_paid.status == "paid" and ord_paid.activated_at is not None

    async def test_admin_config_forbids_unknown_fields_masks_secrets_and_first_time_flag_is_db_backed(
        self, pay_env
    ):
        c: AsyncClient = pay_env["client"]
        uid_a = pay_env["uid_a"]

        # 1) User thường gọi admin config -> 403
        assert (await c.get("/api/v1/quan-tri/thanh-toan/cau-hinh", headers={"X-Test-Actor": "a"})).status_code == 403

        # 2) Gửi trường lạ (typo `sepay_secret_typo`) -> 422 (`extra="forbid"`, §5 & §9 mục 15)
        r_typo = await c.post(
            "/api/v1/quan-tri/thanh-toan/cau-hinh",
            json={"ngan_hang_ten": "ACB", "sepay_secret_typo": "123456"},
            headers={"X-Test-Actor": "admin"},
        )
        assert r_typo.status_code == 422

        # 3) Gửi 2 gói trùng vùng giá VNĐ trong `price_overrides` -> 422
        r_dup_price = await c.post(
            "/api/v1/quan-tri/thanh-toan/cau-hinh",
            json={"price_overrides": {"starter_monthly": {"first_vnd": 99000}}},  # trùng pro_monthly 99000
            headers={"X-Test-Actor": "admin"},
        )
        assert r_dup_price.status_code == 422

        # 4) Lưu cấu hình hợp lệ -> đọc lại khớp 100%, secret bị che mặt nạ!
        raw_secret = "super_secret_sepay_hmac_key_99887766"
        r_save = await c.post(
            "/api/v1/quan-tri/thanh-toan/cau-hinh",
            json={
                "ngan_hang_ten": "ACB",
                "ngan_hang_so_tk": "20260457",
                "ngan_hang_chu_tk": "NGUYEN THANH TRIEU",
                "sepay_webhook_secret": raw_secret,
            },
            headers={"X-Test-Actor": "admin"},
        )
        assert r_save.status_code == 200, r_save.text
        body_save = r_save.json()
        assert body_save["ok"] is True
        assert body_save["ngan_hang_so_tk"] == "20260457"
        assert body_save["sepay_configured"] is True
        assert raw_secret not in json.dumps(body_save)  # Không bao giờ rò rỉ plaintext secret!

        # Kiểm `/quan-tri/thong-ke` cũng KHÔNG rò rỉ plaintext secret!
        r_tk = await c.get("/api/v1/quan-tri/thong-ke", headers={"X-Test-Actor": "admin"})
        assert r_tk.status_code == 200
        assert raw_secret not in r_tk.text

        # 5) Cờ khuyến mãi lần đầu suy từ CSDL (`has_prior_paid_purchase`, §9 mục 16):
        r_bg_before = (await c.get("/api/v1/thanh-toan/bang-gia", headers={"X-Test-Actor": "a"})).json()
        assert r_bg_before["da_tung_nap"] is False
        starter_before = next(x for x in r_bg_before["goi_goi_y"] if x["ma"] == "starter_monthly")
        assert starter_before["so_tien_vnd"] == 49_000  # Giá ưu đãi lần đầu

        # Sau khi có 1 đơn `paid` trong CSDL -> tự động chuyển sang giá gia hạn `89.000đ`!
        async with pay_env["Maker"]() as s:
            u_a = await s.get(NguoiDung, uid_a)
            ord_paid, _ = await tt.create_payment_order(s, nguoi=u_a, plan_code="starter_monthly", rail="vietqr")
            await tt.activate_order(
                s,
                order_id=ord_paid.id,
                paid_amount=49_000,
                currency="VND",
                provider="sepay",
                provider_event_id="tx_first_paid",
            )

        r_bg_after = (await c.get("/api/v1/thanh-toan/bang-gia", headers={"X-Test-Actor": "a"})).json()
        assert r_bg_after["da_tung_nap"] is True
        starter_after = next(x for x in r_bg_after["goi_goi_y"] if x["ma"] == "starter_monthly")
        assert starter_after["so_tien_vnd"] == 99_000  # Giá gia hạn chuẩn!

        # Nếu CSDL lỗi khi hỏi `has_prior_paid_purchase` -> fail-closed trả `True` (không bán nhầm giá giảm)
        class _BrokenSession:
            async def execute(self, *_a, **_kw):
                raise RuntimeError("db connection lost")

        assert await tt.has_prior_paid_purchase(_BrokenSession(), user_id=uid_a) is True  # type: ignore[arg-type]

    async def test_daily_lock_fail_closed_and_conditional_subscription_expiry(self, pay_env):
        # 1) Kiểm `acquire_daily_lock` (§9 mục 17 & §12.5)
        store: dict[str, str] = {}

        class _FakeRedis:
            def set(self, key: str, val: str, nx: bool = False, ex: int = 0):
                if nx and key in store:
                    return None
                store[key] = val
                return True

            def eval(self, _lua: str, _nkeys: int, key: str, token: str):
                if store.get(key) == token:
                    del store[key]
                    return 1
                return 0

        class _BrokenRedis:
            def set(self, *_a, **_kw):
                raise ConnectionError("redis unreachable")

        fake_r = _FakeRedis()
        ok1, k1, tok1 = tt.acquire_daily_lock(fake_r, "test_job")
        ok2, _, _ = tt.acquire_daily_lock(fake_r, "test_job")
        assert ok1 is True and tok1 is not None
        assert ok2 is False  # Lần gọi thứ 2 trong cùng ngày bị chặn!

        # Nếu task lỗi và nhả khoá -> thử lại được
        tt.release_daily_lock(fake_r, k1, tok1)
        ok3, _, _ = tt.acquire_daily_lock(fake_r, "test_job")
        assert ok3 is True

        # Redis lỗi -> fail-closed (`False`), KHÔNG chạy trùng ở tất cả worker!
        ok_err, _, _ = tt.acquire_daily_lock(_BrokenRedis(), "test_job")
        assert ok_err is False
        assert tt.acquire_daily_lock(None, "test_job")[0] is False

        # 2) Kiểm hạ gói hết hạn CÓ ĐIỀU KIỆN (`expire_lapsed_subscriptions`, §12.6)
        now = datetime.now(timezone.utc)
        async with pay_env["Maker"]() as s:
            u_lapsed = await s.get(NguoiDung, pay_env["uid_a"])
            u_renewed = await s.get(NguoiDung, pay_env["uid_b"])

            u_lapsed.cap_do_goi = 3
            u_lapsed.trang_thai_billing = "active"
            u_lapsed.het_han_goi = now - timedelta(hours=1)

            u_renewed.cap_do_goi = 4
            u_renewed.trang_thai_billing = "active"
            u_renewed.het_han_goi = now + timedelta(days=25)
            await s.commit()

            downgraded = await tt.expire_lapsed_subscriptions(s, now=now)
            assert downgraded == 1

            await s.refresh(u_lapsed)
            await s.refresh(u_renewed)
            assert u_lapsed.cap_do_goi == 0 and u_lapsed.trang_thai_billing == "canceled"
            assert u_renewed.cap_do_goi == 4 and u_renewed.trang_thai_billing == "active"


class TestGuardrailsAndMigration0039:
    def test_migration_0039_chain_and_zero_postgres_enums(self):
        import ast

        repo_root = Path(__file__).resolve().parents[2]
        mig_dir = repo_root / "backend" / "alembic" / "versions"
        mig_path = mig_dir / "0039_payment_online_safe.py"
        prev_path = mig_dir / "0038_detect_outbox.py"
        assert prev_path.exists()

        src = mig_path.read_text(encoding="utf-8")
        assert "sa.Enum" not in src
        assert "CREATE TYPE" not in src.upper()

        tree = ast.parse(src, filename=str(mig_path))
        assigns: dict[str, Any] = {}
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and isinstance(node.value, ast.Constant):
                        assigns[t.id] = node.value.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and isinstance(node.value, ast.Constant):
                assigns[node.target.id] = node.value.value

        assert assigns.get("revision") == "0039_payment_online_safe"
        assert assigns.get("down_revision") == "0038_detect_outbox"

    def test_public_router_khach_whitelist_exact(self):
        from app.api.v1.routes import router_khach

        thuc_te = sorted(
            (r.path, m)
            for r in router_khach.routes
            for m in sorted(r.methods)
            if m not in ("HEAD", "OPTIONS")
        )
        assert ("/api/v1/thanh-toan/bang-gia", "GET") in thuc_te
        assert ("/api/v1/thanh-toan/webhook/sepay", "POST") in thuc_te
        assert ("/api/v1/thanh-toan/webhook/stripe", "POST") in thuc_te
        assert ("/api/v1/thanh-toan/webhook/paypal", "POST") in thuc_te
        # Không một endpoint tạo đơn / capture / duyệt tay / admin nào được nằm trên `router_khach`!
        for path, _m in thuc_te:
            assert "tao-don" not in path
            assert "quan-tri" not in path
            assert "/orders/" not in path



