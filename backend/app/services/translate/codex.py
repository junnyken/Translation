"""E73 — dịch bằng tài khoản ChatGPT của CHÍNH NGƯỜI CÀI, đăng nhập kiểu Codex (device code).

## Nguồn

Giao thức chuyển từ Koharu (`crates/koharu-agent/src/codex/{auth,mod,protocol,stream,catalog}.rs`,
MIT OR Apache-2.0, © Mayo Takanashi and Koharu contributors): đăng nhập device-code ở
`auth.openai.com` bằng client id của ứng dụng Codex, gọi `chatgpt.com/backend-api/codex/responses`
dạng luồng SSE, tự làm mới token.

## Ranh giới — đọc trước khi đổi bất cứ gì

Đây **không** phải API công khai của OpenAI. Chủ dự án quyết định thử nghiệm (15-10-2026) sau khi được
nói rủi ro: dùng client id của ứng dụng khác có thể trái điều khoản OpenAI và tài khoản có thể bị
khoá. Vì vậy:

1. **Chỉ chạy ở bản cài cục bộ** (`CHE_DO_CAI_CUC_BO=true`). Tắt cờ ⇒ engine từ chối trước khi gọi
   mạng, API đăng nhập trả 404. Một gói ChatGPT KHÔNG được dùng để phục vụ nhiều người qua một
   dịch vụ chung — đó là chia sẻ tài khoản, khác hẳn "người cài dùng tài khoản của mình".
2. Khách lạ (chưa đăng nhập) KHÔNG được chọn engine này — xem chốt ở cổng khách.
3. Token nằm trong tệp riêng (`CODEX_AUTH_PATH`, quyền 600, thư mục 700), trên volume RIÊNG — không
   nằm trong kho ảnh, không bao giờ vào log, không bao giờ trả qua API.
4. `originator` khai đúng tên ứng dụng này, không mạo nhận là Codex CLI hay Koharu.
"""
from __future__ import annotations

import base64
import contextlib
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.models.enums import TranslationEngine
from app.services.translate.engines import LLMContextTranslator, TranslationFailed
from app.services.translate.llm_cuc_bo import SCHEMA_DICH_JSON

logger = logging.getLogger(__name__)

AUTH_BASE = "https://auth.openai.com"
CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
DEVICE_REDIRECT_URI = "https://auth.openai.com/deviceauth/callback"
LINK_XAC_NHAN = f"{AUTH_BASE}/codex/device"
RESPONSES_URL = "https://chatgpt.com/backend-api/codex/responses"
MODELS_URL = "https://chatgpt.com/backend-api/codex/models?client_version=0.146.0"
HAN_DANG_NHAP_S = 15 * 60
TRAN_LUONG_BYTE = 16 * 1024 * 1024
AUTH_CLAIM = "https://api.openai.com/auth"
PROFILE_CLAIM = "https://api.openai.com/profile"


class CodexChuaDangNhap(TranslationFailed):
    pass


@dataclass(frozen=True)
class TaiKhoan:
    id: str
    email: str | None
    goi: str | None


# ---------------------------------------------------------------- tiện ích

def _bay_gio_ms() -> int:
    return int(time.time() * 1000)


def _jwt(gia_tri: str) -> dict | None:
    phan = (gia_tri or "").split(".")
    if len(phan) != 3:
        return None
    try:
        return json.loads(base64.urlsafe_b64decode(phan[1] + "=" * (-len(phan[1]) % 4)))
    except (ValueError, json.JSONDecodeError):
        return None


def _post(url: str, *, json_body: dict | None = None, form: dict | None = None,
          timeout: int = 30) -> tuple[int, dict | str]:
    """POST, trả (mã HTTP, thân đã giải JSON nếu được). KHÔNG ném với mã 4xx/5xx."""
    if json_body is not None:
        data, ct = json.dumps(json_body).encode(), "application/json"
    else:
        data, ct = urllib.parse.urlencode(form or {}).encode(), "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": ct})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ma, tho = r.status, r.read()
    except urllib.error.HTTPError as exc:
        ma, tho = exc.code, exc.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise TranslationFailed(f"codex_khong_ket_noi: {exc}") from exc
    van_ban = tho.decode("utf-8", "replace")
    try:
        return ma, json.loads(van_ban)
    except json.JSONDecodeError:
        return ma, van_ban[:500]


# ---------------------------------------------------------------- lưu token

class KhoToken:
    """Một tệp JSON, ghi nguyên tử, quyền 600. Kèm tệp "đang chờ xác nhận" của lượt đăng nhập."""

    def __init__(self, duong_dan: str) -> None:
        self.tep = Path(duong_dan)
        self.tep_cho = self.tep.with_name(self.tep.stem + ".cho_xac_nhan.json")
        self.tep_khoa = self.tep.with_name(self.tep.stem + ".lock")

    def _ghi(self, tep: Path, du_lieu: dict) -> None:
        tep.parent.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(OSError):
            os.chmod(tep.parent, 0o700)
        tam = tep.with_name(f".{tep.name}.{uuid.uuid4().hex}")
        fd = os.open(tam, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(du_lieu, f)
        os.replace(tam, tep)

    @staticmethod
    def _doc(tep: Path) -> dict | None:
        try:
            return json.loads(tep.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError):
            logger.warning("Tệp %s hỏng — coi như chưa có", tep.name)
            return None

    def doc(self) -> dict | None:
        return self._doc(self.tep)

    def ghi(self, token: dict) -> None:
        self._ghi(self.tep, token)

    def xoa(self) -> None:
        for t in (self.tep, self.tep_cho):
            with contextlib.suppress(FileNotFoundError):
                t.unlink()

    def doc_cho(self) -> dict | None:
        return self._doc(self.tep_cho)

    def ghi_cho(self, d: dict) -> None:
        self._ghi(self.tep_cho, d)

    def xoa_cho(self) -> None:
        with contextlib.suppress(FileNotFoundError):
            self.tep_cho.unlink()

    @contextlib.contextmanager
    def khoa(self):
        """Khoá liên tiến trình (API và worker có thể cùng làm mới token một lúc).

        Windows không có `fcntl` (app desktop — `docs/desktop/DECISIONS.md` D10) ⇒ dùng `msvcrt`.
        """
        self.tep_khoa.parent.mkdir(parents=True, exist_ok=True)
        with open(self.tep_khoa, "a+") as f:
            if os.name == "nt":
                import msvcrt

                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)


# ---------------------------------------------------------------- xác thực

def _token_tu_phan_hoi(body: dict) -> dict:
    access, refresh = body.get("access_token"), body.get("refresh_token")
    if not access or not refresh:
        raise TranslationFailed("codex: phản hồi token thiếu access/refresh")
    if body.get("expires_in"):
        het = _bay_gio_ms() + int(body["expires_in"]) * 1000
    else:
        exp = (_jwt(access) or {}).get("exp")
        het = int(exp) * 1000 if exp else None
    if het is None:
        raise TranslationFailed("codex: phản hồi token không có hạn dùng")
    return {"access": access, "refresh": refresh, "id": body.get("id_token"), "expires_at_ms": het}


def tai_khoan_tu_token(token: dict) -> TaiKhoan:
    claims = _jwt(token["access"]) or (_jwt(token["id"]) if token.get("id") else None) or {}
    auth = claims.get(AUTH_CLAIM) or {}
    if not auth.get("chatgpt_account_id"):
        raise TranslationFailed("codex: token không chứa mã tài khoản ChatGPT")
    profile = claims.get(PROFILE_CLAIM) or {}
    return TaiKhoan(id=auth["chatgpt_account_id"], email=profile.get("email"),
                    goi=auth.get("chatgpt_plan_type"))


class XacThucCodex:
    def __init__(self, duong_dan: str) -> None:
        self.kho = KhoToken(duong_dan)

    # --- đăng nhập 2 bước: lấy mã, rồi hỏi lại cho tới khi người dùng xác nhận trên trình duyệt ---
    def bat_dau(self) -> dict:
        ma, body = _post(f"{AUTH_BASE}/api/accounts/deviceauth/usercode",
                         json_body={"client_id": CLIENT_ID})
        if ma != 200 or not isinstance(body, dict):
            raise TranslationFailed(f"codex: không lấy được mã thiết bị (HTTP {ma}): {body}")
        ma_nguoi_dung = body.get("user_code") or body.get("usercode")
        if not body.get("device_auth_id") or not ma_nguoi_dung:
            raise TranslationFailed("codex: phản hồi mã thiết bị thiếu trường")
        self.kho.ghi_cho({
            "device_auth_id": body["device_auth_id"],
            "user_code": ma_nguoi_dung,
            "bat_dau_ms": _bay_gio_ms(),
        })
        return {"ma": ma_nguoi_dung, "link": LINK_XAC_NHAN, "het_han_giay": HAN_DANG_NHAP_S}

    def hoi_lai(self) -> str:
        """Hỏi OpenAI MỘT lần. Trả `cho_xac_nhan` | `da_dang_nhap` | `het_han` | `chua_bat_dau`."""
        cho = self.kho.doc_cho()
        if cho is None:
            return "da_dang_nhap" if self.kho.doc() else "chua_bat_dau"
        if _bay_gio_ms() - cho["bat_dau_ms"] > HAN_DANG_NHAP_S * 1000:
            self.kho.xoa_cho()
            return "het_han"
        ma, body = _post(f"{AUTH_BASE}/api/accounts/deviceauth/token", json_body={
            "device_auth_id": cho["device_auth_id"], "user_code": cho["user_code"],
        })
        if ma in (403, 404):
            return "cho_xac_nhan"
        if ma != 200 or not isinstance(body, dict):
            raise TranslationFailed(f"codex: hỏi trạng thái đăng nhập lỗi (HTTP {ma}): {body}")
        ma2, tok = _post(f"{AUTH_BASE}/oauth/token", form={
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "code": body["authorization_code"],
            "code_verifier": body["code_verifier"],
            "redirect_uri": DEVICE_REDIRECT_URI,
        })
        if ma2 != 200 or not isinstance(tok, dict):
            raise TranslationFailed(f"codex: đổi mã lấy token lỗi (HTTP {ma2})")
        token = _token_tu_phan_hoi(tok)
        tai_khoan_tu_token(token)  # token không có tài khoản ChatGPT thì không lưu
        self.kho.ghi(token)
        self.kho.xoa_cho()
        return "da_dang_nhap"

    def tai_khoan(self) -> TaiKhoan | None:
        token = self.kho.doc()
        return tai_khoan_tu_token(token) if token else None

    def dang_xuat(self) -> None:
        self.kho.xoa()

    # --- phiên dùng để gọi ---
    def phien(self, ep_lam_moi: bool = False) -> tuple[str, TaiKhoan]:
        token = self.kho.doc()
        if token is None:
            raise CodexChuaDangNhap("codex_chua_dang_nhap: chưa đăng nhập ChatGPT ở trang Cài đặt")
        if ep_lam_moi or token["expires_at_ms"] <= _bay_gio_ms() + 60_000:
            with self.kho.khoa():
                moi = self.kho.doc()  # tiến trình khác có thể vừa làm mới xong
                if moi is None:
                    raise CodexChuaDangNhap("codex_chua_dang_nhap: phiên đã bị đăng xuất")
                if (ep_lam_moi and moi["access"] == token["access"]) or (
                        moi["expires_at_ms"] <= _bay_gio_ms() + 60_000):
                    moi = self._lam_moi(moi)
                token = moi
        return token["access"], tai_khoan_tu_token(token)

    def _lam_moi(self, token: dict) -> dict:
        ma, body = _post(f"{AUTH_BASE}/oauth/token", form={
            "grant_type": "refresh_token", "refresh_token": token["refresh"], "client_id": CLIENT_ID,
        })
        if ma == 401:
            self.kho.xoa()
            raise CodexChuaDangNhap("codex_het_phien: phiên ChatGPT đã bị thu hồi — đăng nhập lại")
        if ma != 200 or not isinstance(body, dict):
            raise TranslationFailed(f"codex: làm mới token lỗi (HTTP {ma})")
        moi = _token_tu_phan_hoi(body)
        self.kho.ghi(moi)
        return moi


# ---------------------------------------------------------------- gọi model

def doc_luong_sse(dong_byte) -> tuple[str, dict]:
    """Đọc luồng SSE của Responses API. Trả (chữ đầu ra, usage). Lỗi ⇒ `TranslationFailed`.

    Xử lý đúng các sự kiện Koharu xử lý (`stream.rs`). Luồng hết mà chưa có `completed` là LỖI —
    không trả chữ nửa chừng.
    """
    chu: list[str] = []
    dau_ra: list[dict] = []
    usage: dict = {}
    du_lieu: list[str] = []
    xong, tong = False, 0

    def _xu_ly(tho: str) -> bool:
        nonlocal usage
        if not tho or tho == "[DONE]":
            return False
        try:
            ev = json.loads(tho)
        except json.JSONDecodeError as exc:
            raise TranslationFailed(f"codex: JSON hỏng trong luồng: {tho[:120]}") from exc
        loai = ev.get("type", "")
        if loai == "response.output_text.delta":
            chu.append(ev.get("delta") or "")
        elif loai == "response.output_item.done" and ev.get("item"):
            dau_ra.append(ev["item"])
        elif loai in ("response.completed", "response.done"):
            resp = ev.get("response") or {}
            if not dau_ra:
                dau_ra.extend(resp.get("output") or [])
            usage = resp.get("usage") or {}
            return True
        elif loai in ("response.incomplete", "response.failed", "error"):
            loi = (ev.get("message") or (ev.get("error") or {}).get("message")
                   or ((ev.get("response") or {}).get("error") or {}).get("message")
                   or str(ev)[:200])
            raise TranslationFailed(f"codex {loai}: {loi}")
        return False

    for dong in dong_byte:
        tong += len(dong)
        if tong > TRAN_LUONG_BYTE:
            raise TranslationFailed("codex: luồng trả về vượt 16MB")
        s = dong.decode("utf-8", "replace").rstrip("\r\n")
        if s.startswith("data:"):
            du_lieu.append(s[5:].lstrip())
        elif s == "" and du_lieu:
            if _xu_ly("\n".join(du_lieu)):
                xong = True
                break
            du_lieu = []
    if not xong and du_lieu and _xu_ly("\n".join(du_lieu)):
        xong = True
    if not xong:
        raise TranslationFailed("codex: luồng kết thúc trước khi hoàn tất")
    van_ban = "".join(chu)
    if not van_ban:
        van_ban = "".join(
            c.get("text", "")
            for it in dau_ra if it.get("type") == "message"
            for c in it.get("content") or [] if c.get("type") == "output_text"
        )
    return van_ban, usage


def danh_sach_model(access: str, tk: TaiKhoan, originator: str, timeout: int = 30) -> list[str]:
    """Model tài khoản này được dùng, theo thứ tự máy chủ trả (Koharu `catalog.rs`)."""
    req = urllib.request.Request(MODELS_URL, headers={
        "Authorization": f"Bearer {access}", "chatgpt-account-id": tk.id,
        "originator": originator, "accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read(1024 * 1024))
    except urllib.error.HTTPError as exc:
        raise TranslationFailed(f"codex: lấy danh sách model lỗi HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise TranslationFailed(f"codex: lấy danh sách model lỗi: {exc}") from exc
    ra = []
    for m in data.get("models") or []:
        hien = str(m.get("visibility") or "list").lower() == "list"
        chon = m.get("show_in_picker", m.get("showInPicker", True))
        ten = (m.get("slug") or m.get("id") or "").strip()
        if hien and chon is not False and ten:
            ra.append(ten)
    return ra


class CodexTranslator(LLMContextTranslator):
    """Luôn ở chế độ JSON theo `id` (E71) — cùng prompt với Gemini và LLM cục bộ."""

    engine_enum = TranslationEngine.chatgpt_codex

    HUONG_DAN = (
        "Bạn là người dịch truyện tranh chuyên nghiệp. Làm đúng yêu cầu trong tin nhắn của người "
        "dùng và chỉ trả về JSON theo đúng định dạng được yêu cầu."
    )

    def __init__(
        self,
        auth_path: str,
        model_name: str = "",
        originator: str = "matbao-translation",
        timeout: int = 300,
        cho_phep: bool = False,
        reasoning: str = "low",
        boi_canh: str = "",
        anh_trang: bytes | None = None,
        anh_mime: str = "image/jpeg",
    ) -> None:
        super().__init__(api_keys=["codex"], model_name=model_name, timeout=timeout,
                         thinking_budget=None, boi_canh=boi_canh, anh_trang=anh_trang,
                         anh_mime=anh_mime, json_mode=True)
        self.xac_thuc = XacThucCodex(auth_path)
        self.originator = originator
        self.cho_phep = cho_phep
        self.reasoning = reasoning

    def _chon_model(self, access: str, tk: TaiKhoan) -> str:
        if self.model_name:
            return self.model_name
        ds = danh_sach_model(access, tk, self.originator, min(self.timeout, 30))
        if not ds:
            raise TranslationFailed("codex: tài khoản không có model nào dùng được")
        self.model_name = self.usage.model_name = ds[0]
        return ds[0]

    def _than(self, model: str, prompt: str, schema: dict | None) -> dict:
        noi_dung: list[dict] = []
        if self.anh_trang:
            noi_dung.append({"type": "input_image", "detail": "high", "image_url":
                             f"data:{self.anh_mime};base64,"
                             + base64.b64encode(self.anh_trang).decode("ascii")})
        noi_dung.append({"type": "input_text", "text": prompt})
        than = {
            "model": model,
            "instructions": self.HUONG_DAN,
            "input": [{"type": "message", "role": "user", "content": noi_dung}],
            "tools": [],
            "tool_choice": "auto",
            "parallel_tool_calls": False,
            "reasoning": {"effort": self.reasoning, "summary": "auto"},
            "text": {"verbosity": "low"},
            "include": ["reasoning.encrypted_content"],
            "stream": True,
            "store": False,
            "prompt_cache_key": uuid.uuid4().hex,
        }
        if schema is not None:
            than["text"]["format"] = {"type": "json_schema", "name": "ban_dich",
                                      "schema": SCHEMA_DICH_JSON, "strict": True}
        return than

    def _gui(self, access: str, tk: TaiKhoan, than: dict):
        req = urllib.request.Request(RESPONSES_URL, data=json.dumps(than).encode(), method="POST",
                                     headers={
                                         "Authorization": f"Bearer {access}",
                                         "chatgpt-account-id": tk.id,
                                         "originator": self.originator,
                                         "OpenAI-Beta": "responses=experimental",
                                         "accept": "text/event-stream",
                                         "Content-Type": "application/json",
                                         "session_id": than["prompt_cache_key"],
                                     })
        return urllib.request.urlopen(req, timeout=self.timeout)

    def _call_api(self, prompt: str, schema: dict | None = None) -> tuple[str, dict]:
        if not self.cho_phep:
            raise TranslationFailed(
                "chatgpt_codex chỉ dùng ở bản cài cục bộ (CHE_DO_CAI_CUC_BO=true) — không chạy trên "
                "máy chủ dùng chung"
            )
        access, tk = self.xac_thuc.phien()
        model = self._chon_model(access, tk)
        than = self._than(model, prompt, schema)
        da_lam_moi = da_bo_schema = False
        while True:
            try:
                with self._gui(access, tk, than) as r:
                    van_ban, usage = doc_luong_sse(r)
                break
            except urllib.error.HTTPError as exc:
                chi_tiet = exc.read().decode("utf-8", "replace")[:300]
                self.usage.errors.append(f"HTTP {exc.code}")
                if exc.code == 401 and not da_lam_moi:
                    access, tk = self.xac_thuc.phien(ep_lam_moi=True)
                    da_lam_moi = True
                    continue
                if (exc.code == 400 and "format" in chi_tiet and not da_bo_schema
                        and "format" in than["text"]):
                    # Máy chủ không nhận ép schema ⇒ thử lại không ép; prompt vẫn đòi JSON và
                    # `parse_response_json` vẫn chặn JSON hỏng.
                    logger.warning("codex không nhận text.format — thử lại không ép schema")
                    than["text"].pop("format")
                    da_bo_schema = True
                    continue
                raise TranslationFailed(f"codex HTTP {exc.code}: {chi_tiet}") from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                raise TranslationFailed(f"codex_khong_ket_noi: {exc}") from exc
        return van_ban, {
            "promptTokenCount": usage.get("input_tokens"),
            "candidatesTokenCount": usage.get("output_tokens"),
            "totalTokenCount": usage.get("total_tokens"),
        }
