"""E73 — dịch bằng tài khoản ChatGPT đăng nhập kiểu Codex (chỉ bản cài cục bộ).

Canh:
1. Đăng nhập device-code đủ hai bước với máy chủ HTTP THẬT dựng trong test (đóng vai
   auth.openai.com + chatgpt.com) — token lưu tệp quyền 600, KHÔNG bao giờ trả qua API.
2. Dịch qua luồng SSE, ép JSON theo `id` (E71); 401 ⇒ làm mới token một lần rồi gọi lại.
3. Luồng đứt trước `response.completed` là LỖI, không trả chữ nửa chừng.
4. Ranh giới: cờ `che_do_cai_cuc_bo` tắt ⇒ engine từ chối TRƯỚC khi gọi mạng, API trả 404/422;
   người không phải quản trị ⇒ 404; khách lạ ⇒ 403.
"""
from __future__ import annotations

import base64
import json
import os
import stat
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.models.enums import TranslationEngine
from app.services.translate import codex
from app.services.translate.engines import ENGINE_LLM, TranslationFailed, get_translator


def _jwt(claims: dict) -> str:
    def b64(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")

    return f"{b64({'alg': 'none'})}.{b64(claims)}.ky"


def _access(so: int) -> str:
    return _jwt({
        "exp": 9_999_999_999, "n": so,
        codex.AUTH_CLAIM: {"chatgpt_account_id": "acc-1", "chatgpt_plan_type": "plus"},
        codex.PROFILE_CLAIM: {"email": "nguoi.cai@example.com"},
    })


def _sse(*su_kien: dict) -> bytes:
    return b"".join(f"data: {json.dumps(e)}\n\n".encode() for e in su_kien)


@pytest.fixture
def openai_gia(monkeypatch):
    """Một máy chủ đóng vai cả auth.openai.com lẫn chatgpt.com/backend-api/codex."""
    tt = {"xac_nhan": False, "lan_lam_moi": 0, "responses": [], "401_mot_lan": False,
          "luong": None}

    class _H(BaseHTTPRequestHandler):
        def _tra(self, ma, body, ct="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(ma)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):  # noqa: N802
            if self.path.startswith("/codex/models"):
                return self._tra(200, {"models": [
                    {"slug": "an-di", "visibility": "hide"}, {"slug": "gpt-thu", "visibility": "list"},
                ]})
            self._tra(404, {})

        def do_POST(self):  # noqa: N802
            tho = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            if self.path == "/api/accounts/deviceauth/usercode":
                return self._tra(200, {"device_auth_id": "dev-1", "user_code": "ABCD-1234"})
            if self.path == "/api/accounts/deviceauth/token":
                if not tt["xac_nhan"]:
                    return self._tra(403, {"error": "pending"})
                return self._tra(200, {"authorization_code": "code-1", "code_verifier": "ver-1"})
            if self.path == "/oauth/token":
                form = dict(x.split("=", 1) for x in tho.decode().split("&"))
                if form["grant_type"] == "refresh_token":
                    tt["lan_lam_moi"] += 1
                    return self._tra(200, {"access_token": _access(2), "refresh_token": "r2",
                                           "expires_in": 3600})
                return self._tra(200, {"access_token": _access(1), "refresh_token": "r1",
                                       "id_token": _access(1), "expires_in": 3600})
            if self.path == "/codex/responses":
                than = json.loads(tho)
                tt["responses"].append({"than": than, "auth": self.headers["Authorization"],
                                        "acc": self.headers["chatgpt-account-id"],
                                        "originator": self.headers["originator"]})
                if tt["401_mot_lan"]:
                    tt["401_mot_lan"] = False
                    return self._tra(401, {"error": "expired"})
                luong = tt["luong"] or _sse(
                    {"type": "response.output_text.delta",
                     "delta": '{"translations":[{"id":1,"text":"Xin '},
                    {"type": "response.output_text.delta", "delta": 'chào.","doan":false}]}'},
                    {"type": "response.completed",
                     "response": {"usage": {"input_tokens": 9, "output_tokens": 4, "total_tokens": 13}}},
                )
                return self._tra(200, luong, "text/event-stream")
            self._tra(404, {})

        def log_message(self, *a):
            pass

    sv = HTTPServer(("127.0.0.1", 0), _H)
    threading.Thread(target=sv.serve_forever, daemon=True).start()
    goc = f"http://127.0.0.1:{sv.server_port}"
    monkeypatch.setattr(codex, "AUTH_BASE", goc)
    monkeypatch.setattr(codex, "RESPONSES_URL", f"{goc}/codex/responses")
    monkeypatch.setattr(codex, "MODELS_URL", f"{goc}/codex/models")
    yield tt
    sv.shutdown()


def _dang_nhap(tmp_path, tt) -> str:
    duong = str(tmp_path / "codex" / "auth.json")
    xt = codex.XacThucCodex(duong)
    bd = xt.bat_dau()
    assert bd["ma"] == "ABCD-1234"
    assert xt.hoi_lai() == "cho_xac_nhan"
    tt["xac_nhan"] = True
    assert xt.hoi_lai() == "da_dang_nhap"
    return duong


def test_dang_nhap_hai_buoc_luu_token_quyen_600(tmp_path, openai_gia):
    duong = _dang_nhap(tmp_path, openai_gia)
    assert stat.S_IMODE(os.stat(duong).st_mode) == 0o600
    tk = codex.XacThucCodex(duong).tai_khoan()
    assert (tk.id, tk.email, tk.goi) == ("acc-1", "nguoi.cai@example.com", "plus")
    assert not (tmp_path / "codex" / "auth.cho_xac_nhan.json").exists()


def test_dich_qua_sse_ep_schema_va_chon_model_hien(tmp_path, openai_gia):
    duong = _dang_nhap(tmp_path, openai_gia)
    may = get_translator("chatgpt_codex", auth_path=duong, cho_phep=True)
    assert may.translate(["Hello"], "en", "vi") == ["Xin chào."]
    r = openai_gia["responses"][0]
    assert r["than"]["model"] == "gpt-thu", "model ẩn khỏi bộ chọn không được dùng"
    assert r["than"]["text"]["format"]["type"] == "json_schema"
    assert r["acc"] == "acc-1" and r["originator"] == "matbao-translation"
    assert may.usage.prompt_tokens == 9 and may.usage.output_tokens == 4
    assert TranslationEngine.chatgpt_codex.value in ENGINE_LLM, "lỗi phải lùi về google_fast"


def test_401_thi_lam_moi_token_mot_lan_roi_goi_lai(tmp_path, openai_gia):
    duong = _dang_nhap(tmp_path, openai_gia)
    openai_gia["401_mot_lan"] = True
    may = get_translator("chatgpt_codex", auth_path=duong, cho_phep=True, model_name="gpt-thu")
    assert may.translate(["Hello"], "en", "vi") == ["Xin chào."]
    assert openai_gia["lan_lam_moi"] == 1
    auth = [r["auth"] for r in openai_gia["responses"]]
    assert auth[0] != auth[1], "lần gọi lại phải dùng token MỚI"


def test_luong_dut_truoc_completed_la_loi(tmp_path, openai_gia):
    duong = _dang_nhap(tmp_path, openai_gia)
    openai_gia["luong"] = _sse({"type": "response.output_text.delta", "delta": '{"transl'})
    may = get_translator("chatgpt_codex", auth_path=duong, cho_phep=True, model_name="gpt-thu")
    with pytest.raises(TranslationFailed, match="trước khi hoàn tất"):
        may.translate(["Hello"], "en", "vi")


def test_tat_co_thi_tu_choi_truoc_khi_goi_mang(tmp_path, openai_gia):
    duong = _dang_nhap(tmp_path, openai_gia)
    may = get_translator("chatgpt_codex", auth_path=duong, cho_phep=False)
    with pytest.raises(TranslationFailed, match="cài cục bộ"):
        may.translate(["Hello"], "en", "vi")
    assert openai_gia["responses"] == []


def test_chua_dang_nhap_bao_ro(tmp_path):
    may = get_translator("chatgpt_codex", auth_path=str(tmp_path / "khong.json"), cho_phep=True)
    with pytest.raises(codex.CodexChuaDangNhap):
        may.translate(["Hello"], "en", "vi")


def test_worker_dung_dung_cau_hinh(monkeypatch):
    from app.workers import tasks

    monkeypatch.setattr(tasks.settings, "che_do_cai_cuc_bo", False)
    monkeypatch.setattr(tasks.settings, "codex_model", "gpt-x")
    may = tasks.build_translator(TranslationEngine.chatgpt_codex.value)
    assert isinstance(may, codex.CodexTranslator)
    assert may.cho_phep is False and may.model_name == "gpt-x"


# ---------------------------------------------------------------- API


async def _dat_quan_tri(session, nguoi_id, la=True):
    from app.models import NguoiDung

    n = await session.get(NguoiDung, nguoi_id)
    n.la_quan_tri = la
    await session.commit()


@pytest.fixture
def cai_cuc_bo(monkeypatch, tmp_path):
    from app.core.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "che_do_cai_cuc_bo", True)
    monkeypatch.setattr(s, "codex_auth_path", str(tmp_path / "codex" / "auth.json"))
    return s


@pytest.mark.anyio
async def test_api_404_khi_khong_phai_ban_cai_cuc_bo(session, client, nguoi_a):
    await _dat_quan_tri(session, uuid.UUID(nguoi_a[0]))
    assert (await client.get("/api/v1/codex")).status_code == 404
    assert (await client.post("/api/v1/codex/dang-nhap")).status_code == 404


@pytest.mark.anyio
async def test_api_404_voi_nguoi_khong_phai_quan_tri(cai_cuc_bo, client_b):
    assert (await client_b.get("/api/v1/codex")).status_code == 404


@pytest.mark.anyio
async def test_api_dang_nhap_khong_bao_gio_tra_token(
    cai_cuc_bo, openai_gia, session, client, nguoi_a,
):
    await _dat_quan_tri(session, uuid.UUID(nguoi_a[0]))
    bd = await client.post("/api/v1/codex/dang-nhap")
    assert bd.status_code == 200 and bd.json()["ma"] == "ABCD-1234"
    assert (await client.post("/api/v1/codex/dang-nhap/hoi")).json() == {"trang_thai": "cho_xac_nhan"}
    openai_gia["xac_nhan"] = True
    assert (await client.post("/api/v1/codex/dang-nhap/hoi")).json() == {"trang_thai": "da_dang_nhap"}
    tt = await client.get("/api/v1/codex")
    assert tt.json() == {"da_dang_nhap": True, "email": "nguoi.cai@example.com", "goi": "plus",
                         "dang_cho_xac_nhan": False}
    for r in (bd, tt):
        assert "r1" not in r.text and _access(1) not in r.text

    hz = (await client.get("/healthz")).json()["codex"]
    assert hz == {"bat": True, "da_dang_nhap": True}

    assert (await client.delete("/api/v1/codex")).status_code == 204
    assert (await client.get("/api/v1/codex")).json()["da_dang_nhap"] is False


@pytest.mark.anyio
async def test_chon_codex_tren_may_chu_chung_bi_422(client, sample_page_image):
    pr = await client.post("/api/v1/projects", json={
        "name": "c", "source_lang": "ja", "target_lang": "vi", "intended_use": "personal",
    })
    r = await client.post(
        f"/api/v1/projects/{pr.json()['id']}/pages",
        files={"file": ("p.png", sample_page_image, "image/png")},
        data={"engine": "chatgpt_codex"},
    )
    assert r.status_code == 422 and "codex_chi_cai_cuc_bo" in r.text


def test_khach_la_bi_403_ke_ca_o_ban_cai_cuc_bo(cai_cuc_bo):
    from fastapi import HTTPException

    from app.api.v1.routes import _kiem_engine

    with pytest.raises(HTTPException) as e:
        _kiem_engine(TranslationEngine.chatgpt_codex, cai_cuc_bo, co_tai_khoan=False)
    assert e.value.status_code == 403
    _kiem_engine(TranslationEngine.chatgpt_codex, cai_cuc_bo, co_tai_khoan=True)
