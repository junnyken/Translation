"""Hạ tầng BYOK (Bring Your Own Key) — Cho phép người dùng từ Gói 1 trở lên tự cắm API Key cá nhân.

Chiến lược kinh doanh & bảo mật (Học hỏi và tối ưu từ Torii Translate + Cursor SaaS):
1. Khóa cổng BYOK từ Gói 1 trở lên (`cap_do >= 1`): Tài khoản Khách / Miễn phí (`cap_do == 0`) không được
   dùng BYOK để tránh tiêu tốn tài nguyên OCR + LaMa Inpaint + Băng thông máy chủ với doanh thu 0đ.
2. Khi bật BYOK hợp lệ (`cap_do >= 1`), giảm đúng 50% số lượt trừ ở các bộ máy AI nâng cao:
   - Model 1 (`local_ocr_gpu`)    : 1 lượt/trang -> giữ nguyên 1 lượt/trang (sàn hạ tầng).
   - Model 2 (`local_hybrid_pro`) : 2 lượt/trang -> giảm còn 1 lượt/trang (-50%).
   - Model 3 (`llm_context`)      : 3 lượt/trang -> giảm còn 1,5 lượt/trang (-50%, mở khóa luôn Model 3
     cho khách Gói 1 tự trả phí Vision Token trên Key của họ, máy chủ thu ròng 1,5 lượt phí CTD + LaMa).
3. Chốt chặn Strict Non-Fallback: Khi yêu cầu có gắn BYOK, chỉ gọi duy nhất Key của khách. Nếu Key khách
   hết hạn mức hoặc sai mã, báo lỗi rõ ràng để khách kiểm tra và KHÔNG BAO GIỜ âm thầm lấy Key của Server bù vào.
4. Không lưu trữ thô Key của khách trong CSDL hay nhật ký hệ thống; khi truyền qua tiến trình Worker bất đồng bộ,
   mã hóa đối xứng HMAC-SHA256 kèm thời hạn tự hủy ngắn (TTL 30 phút).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.core.config import Settings
    from app.core.danh_tinh_khach import DanhTinhHanMuc

#: Tiền tố UUID hợp lệ đánh dấu trang cơ sở của Model 3 BYOK (1,5 lượt/trang) trên sổ cái `SoCaiHanMuc`
#: giúp đối chiếu chẵn/lẻ nguyên tử (2 + 1 = 3 lượt / 2 trang = đúng 1,5 lượt/trang) mà không cần đổi cột Integer.
TIEN_TO_UUID_BYOK_M3 = "00000150-"

#: Cấu hình mặc định của các hãng AI hỗ trợ BYOK
NHA_CUNG_CAP_BYOK: dict[str, dict[str, str]] = {
    "gemini": {
        "ten": "Google Gemini",
        "prefix": "gm",
        "model_text": "gemini-2.5-flash",
        "model_vision": "gemini-2.5-flash",
    },
    "deepseek": {
        "ten": "DeepSeek API",
        "prefix": "ds",
        "model_text": "deepseek-chat",
        "model_vision": "deepseek-chat",
    },
    "openai": {
        "ten": "OpenAI (ChatGPT)",
        "prefix": "oai",
        "model_text": "gpt-4o-mini",
        "model_vision": "gpt-4o-mini",
    },
    "claude": {
        "ten": "Anthropic Claude",
        "prefix": "claude",
        "model_text": "claude-3-5-haiku-latest",
        "model_vision": "claude-3-5-sonnet-latest",
    },
    "openrouter": {
        "ten": "OpenRouter",
        "prefix": "or",
        "model_text": "google/gemini-2.5-flash",
        "model_vision": "google/gemini-2.5-flash",
    },
    "groq": {
        "ten": "Groq LPU",
        "prefix": "groq",
        "model_text": "llama-3.3-70b-versatile",
        "model_vision": "meta-llama/llama-4-scout-17b-16e-instruct",
    },
}


class BYOKKeyError(RuntimeError):
    """Lỗi xác thực hoặc hết hạn mức từ chính API Key cá nhân (BYOK) của khách hàng."""


@dataclass(frozen=True)
class CauHinhBYOK:
    provider: str
    api_key: str
    model: str = ""

    @property
    def ten_nha_cung_cap(self) -> str:
        return NHA_CUNG_CAP_BYOK.get(self.provider, {}).get("ten", self.provider)

    def khoa_dinh_tuyen(self, *, vision: bool = False) -> str:
        """Biên dịch thành chuỗi định tuyến nội bộ `<prefix>|<model>|<api_key>` cho Engine."""
        cfg = NHA_CUNG_CAP_BYOK.get(self.provider, NHA_CUNG_CAP_BYOK["gemini"])
        prefix = cfg["prefix"]
        m_default = cfg["model_vision"] if vision else cfg["model_text"]
        m_chon = (self.model or "").strip() or m_default
        # Nếu khách dùng khóa OpenAI/Claude/OpenRouter nhưng không chỉ định model Vision khi gọi Vision
        if vision and self.provider == "groq" and "llama-4" not in m_chon.lower() and "vision" not in m_chon.lower():
            m_chon = cfg["model_vision"]
        return f"{prefix}|{m_chon}|{self.api_key}"

    @property
    def ho_tro_vision_truc_tiep(self) -> bool:
        """Nhà cung cấp có hỗ trợ nhận ảnh trực tiếp (Set-of-Mark Multimodal Vision) hay chỉ nhận văn bản."""
        if self.provider == "deepseek":
            return False
        return True


def doan_nha_cung_cap_tu_khoa(raw_key: str, provider_goi_y: str | None = None) -> str:
    """Tự nhận diện nhà cung cấp từ định dạng khóa hoặc tên hãng do khách chọn."""
    p = (provider_goi_y or "").strip().lower()
    alias = {
        "google": "gemini",
        "gpt": "openai",
        "chatgpt": "openai",
        "anthropic": "claude",
    }
    p = alias.get(p, p)
    if p in NHA_CUNG_CAP_BYOK and p != "auto":
        return p

    k = (raw_key or "").strip()
    if k.startswith("AIza") or k.startswith("AQ."):
        return "gemini"
    if k.startswith("sk-ant-"):
        return "claude"
    if k.startswith("sk-or-"):
        return "openrouter"
    if k.startswith("gsk_"):
        return "groq"
    if k.startswith(("sk-proj-", "sk-svcacct-")):
        return "openai"
    if k.startswith("sk-"):
        return "deepseek"
    return "gemini"


def trich_xuat_byok_tho(
    request: "Request | None" = None,
    *,
    byok_key: str | None = None,
    byok_provider: str | None = None,
    byok_model: str | None = None,
) -> CauHinhBYOK | None:
    """Đọc thông tin BYOK từ Header (`X-BYOK-Key`, `X-BYOK-Provider`, `X-BYOK-Model`) hoặc tham số truyền vào."""
    h_key = ""
    h_prov = ""
    h_mod = ""
    if request is not None:
        h_key = (request.headers.get("X-BYOK-Key") or "").strip()
        h_prov = (request.headers.get("X-BYOK-Provider") or "").strip()
        h_mod = (request.headers.get("X-BYOK-Model") or "").strip()

    key_val = (byok_key or h_key or "").strip()
    if not key_val:
        return None
    # Chặn ký tự xuống dòng hoặc khoảng trắng lạ gây lỗi HTTP header
    key_val = "".join(ch for ch in key_val if 32 < ord(ch) < 127)
    if len(key_val) < 12 or len(key_val) > 512:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400,
            detail="API Key cá nhân (BYOK) không đúng định dạng (độ dài tối thiểu 12 ký tự ASCII).",
        )

    prov_val = doan_nha_cung_cap_tu_khoa(key_val, byok_provider or h_prov)
    mod_val = "".join(ch for ch in (byok_model or h_mod or "").strip() if 32 < ord(ch) < 127)[:120]
    return CauHinhBYOK(provider=prov_val, api_key=key_val, model=mod_val)


def xac_thuc_byok_cho_danh_tinh(
    danh_tinh: "DanhTinhHanMuc",
    request: "Request | None" = None,
    *,
    byok_key: str | None = None,
    byok_provider: str | None = None,
    byok_model: str | None = None,
) -> CauHinhBYOK | None:
    """Kiểm tra cổng quyền lợi Gói 1 (`cap_do >= 1`) khi người dùng gửi kèm khóa BYOK."""
    cfg = trich_xuat_byok_tho(
        request,
        byok_key=byok_key,
        byok_provider=byok_provider,
        byok_model=byok_model,
    )
    if cfg is None:
        return None

    la_admin = (
        danh_tinh.co_tai_khoan
        and not danh_tinh.nguoi_goi.la_khach
        and getattr(danh_tinh.nguoi_goi.nguoi, "la_quan_tri", False)
    )
    if not la_admin and int(danh_tinh.cap_do or 0) < 1:
        thong_bao = (
            "Tính năng tự cắm API Key cá nhân (BYOK — Giảm 50% lượt trừ: Model 2 còn 1 lượt/trang, "
            "Model 3 còn 1,5 lượt/trang) mở khóa từ Gói 1 trở lên. "
            "Vui lòng nâng cấp Gói 1 tại https://comic.io.vn/#bang-gia để kích hoạt!"
        )
        _nem_loi_can_nang_cap(
            cap_hien_tai=int(danh_tinh.cap_do or 0),
            cap_yeu_cau=1,
            tinh_nang="byok_api_key",
            thong_bao=thong_bao,
        )
    return cfg


def _nem_loi_can_nang_cap(*, cap_hien_tai: int, cap_yeu_cau: int, tinh_nang: str, thong_bao: str) -> None:
    try:
        from app.core.danh_tinh_khach import loi_can_nang_cap

        raise loi_can_nang_cap(
            cap_hien_tai=int(cap_hien_tai or 0),
            cap_yeu_cau=cap_yeu_cau,
            tinh_nang=tinh_nang,
            thong_bao=thong_bao,
        )
    except ImportError:
        err = PermissionError(thong_bao)
        err.status_code = 402  # type: ignore[attr-defined]
        err.detail = {  # type: ignore[attr-defined]
            "loi": "can_nang_cap",
            "cap_hien_tai": int(cap_hien_tai or 0),
            "cap_yeu_cau": cap_yeu_cau,
            "tinh_nang": tinh_nang,
            "thong_bao": thong_bao,
        }
        raise err


def kiem_tra_cong_goi_doc_truyen(
    danh_tinh: "DanhTinhHanMuc",
    *,
    engine_name: object,
    font_style: str | None = None,
    tu_dien_rieng: str | None = None,
    co_byok: bool = False,
) -> None:
    """Kiểm tra phân quyền gói cước cho `/doc-truyen/trang`:
    - Model 1 (`google_fast` / `local_ocr_gpu`): mở cho cả Free (`cap_do >= 0`).
    - Model 2 (`[CHẾ ĐỘ AI PRO 2 LƯỢT]`) hoặc bật BYOK hợp lệ: mở từ Gói 1 (`cap_do >= 1`).
    - Model 3 (`llm_context` không BYOK) hoặc Sổ tay nhân vật thủ công trên Web (không BYOK): yêu cầu Gói 2 / Pro (`cap_do >= 3`).
    """
    cap_ht = int(getattr(danh_tinh, "cap_do", 0) or 0)
    eng = str(getattr(engine_name, "value", engine_name) or "").strip().lower()
    td_sach = (tu_dien_rieng or "").strip()
    la_pro_2_luot = "[CHẾ ĐỘ AI PRO 2 LƯỢT" in td_sach
    co_nhan_ext = la_pro_2_luot or ("[CHẾ ĐỘ ULTRA CLOUD AI 3 LƯỢT" in td_sach)

    if eng == "llm_context":
        if la_pro_2_luot:
            if cap_ht < 1 and not co_byok:
                _nem_loi_can_nang_cap(
                    cap_hien_tai=cap_ht,
                    cap_yeu_cau=1,
                    tinh_nang="local_hybrid_pro",
                    thong_bao=(
                        "Bộ máy OCR + AI Hội Thoại Pro (2 lượt/trang) yêu cầu Gói 1 trở lên. "
                        "Xem chi tiết tại https://comic.io.vn/#bang-gia"
                    ),
                )
        elif cap_ht < 3 and not co_byok:
            _nem_loi_can_nang_cap(
                cap_hien_tai=cap_ht,
                cap_yeu_cau=3,
                tinh_nang="llm_context",
                thong_bao=(
                    "Bộ máy Set-of-Mark Vision + LaMa Đám Mây yêu cầu Gói 2 trở lên, "
                    "hoặc bạn có thể cắm API Key cá nhân (BYOK từ Gói 1) để mở khoá với giá chỉ 1,5 lượt/trang! "
                    "Xem chi tiết tại https://comic.io.vn/#bang-gia"
                ),
            )

    if font_style and font_style.strip().lower() not in ("", "bangers") and cap_ht < 1:
        _nem_loi_can_nang_cap(
            cap_hien_tai=cap_ht,
            cap_yeu_cau=1,
            tinh_nang="font_style",
            thong_bao=(
                "Tuỳ chọn Font chữ theo thể loại (Ngôn tình / Cổ trang / Hài hước) yêu cầu gói Starter trở lên. "
                "Nâng cấp chỉ từ $3.99 (49.000đ) ưu đãi tháng đầu tại https://comic.io.vn/#bang-gia"
            ),
        )

    if td_sach:
        if co_nhan_ext or co_byok:
            if cap_ht < 1:
                _nem_loi_can_nang_cap(
                    cap_hien_tai=cap_ht,
                    cap_yeu_cau=1,
                    tinh_nang="glossary",
                    thong_bao=(
                        "Tính năng Ngữ cảnh hội thoại Pro & BYOK yêu cầu Gói 1 trở lên. "
                        "Xem chi tiết tại https://comic.io.vn/#bang-gia"
                    ),
                )
        elif cap_ht < 3:
            _nem_loi_can_nang_cap(
                cap_hien_tai=cap_ht,
                cap_yeu_cau=3,
                tinh_nang="glossary",
                thong_bao=(
                    "Tính năng Sổ tay Nhân vật & Xưng hô cố định (Character Glossary) yêu cầu gói Standard trở lên. "
                    "Vui lòng nâng cấp tại https://comic.io.vn/#bang-gia"
                ),
            )


def he_so_luot_theo_engine(engine_name: str | None, *, co_byok: bool = False) -> float:
    """Trả hệ số lượt chuẩn cho mỗi trang theo bộ máy và trạng thái BYOK:
    - Model 1 (`local_ocr_gpu` / `google_fast`) : 1.0 lượt/trang
    - Model 2 (`local_hybrid_pro`)              : 2.0 lượt/trang -> BYOK còn 1.0 lượt/trang (-50%)
    - Model 3 (`llm_context`)                   : 3.0 lượt/trang -> BYOK còn 1.5 lượt/trang (-50%)
    """
    ma = (engine_name or "local_ocr_gpu").strip().lower()
    if ma == "llm_context":
        return 1.5 if co_byok else 3.0
    if ma == "local_hybrid_pro":
        return 1.0 if co_byok else 2.0
    return 1.0


def tao_uuid_trang_byok_m3(seed: str | None = None) -> uuid.UUID:
    """Sinh UUID hợp lệ mang tiền tố `00000150-` để sổ cái nhận diện trang cơ sở của Model 3 BYOK (1,5 lượt)."""
    if seed:
        goc = uuid.uuid5(uuid.NAMESPACE_URL, f"byok-m3-base:{seed}").hex
    else:
        goc = uuid.uuid4().hex
    hex_moi = "00000150" + goc[8:]
    return uuid.UUID(hex=hex_moi)


async def dem_so_trang_byok_m3_hom_nay(
    session: "AsyncSession",
    danh_tinh: "DanhTinhHanMuc",
) -> int:
    """Đếm số trang Model 3 BYOK đã giữ chỗ/tiêu trong ngày hiện tại của chủ thể chính để tính chẵn/lẻ 1,5 lượt."""
    if not danh_tinh.chot:
        return 0
    from sqlalchemy import func, select
    from app.models import SoCaiHanMuc
    from app.models.enums import TrangThaiHanMuc
    from app.services.han_muc import ngay_han_muc

    c0 = danh_tinh.chot[0]
    ngay = ngay_han_muc()
    mau_khoa = f"giu:{c0.loai.value}:{c0.chu_the}:{TIEN_TO_UUID_BYOK_M3}%"
    q = select(func.count()).select_from(SoCaiHanMuc).where(
        SoCaiHanMuc.loai_chu_the == c0.loai,
        SoCaiHanMuc.chu_the == c0.chu_the,
        SoCaiHanMuc.ngay_han_muc == ngay,
        SoCaiHanMuc.trang_thai.in_((TrangThaiHanMuc.giu_cho, TrangThaiHanMuc.da_tieu)),
        SoCaiHanMuc.khoa_idempotency.like(mau_khoa),
    )
    so_luong = await session.scalar(q)
    return int(so_luong or 0)


async def so_luot_nguyen_can_tru_cho_trang(
    session: "AsyncSession",
    danh_tinh: "DanhTinhHanMuc",
    engine_name: str | None,
    *,
    co_byok: bool = False,
) -> int:
    """Tính số lượt nguyên cần giữ chỗ trên `SoCaiHanMuc` cho 1 trang đơn lẻ:
    - Khi KHÔNG bật BYOK: Model 1 = 1, Model 2 = 2, Model 3 = 3.
    - Khi BẬT BYOK:
      + Model 1 = 1 lượt.
      + Model 2 = 1 lượt (giảm từ 2 xuống 1).
      + Model 3 = 1,5 lượt -> Lượt lẻ (#1, #3, #5...) trừ 2; Lượt chẵn (#2, #4, #6...) trừ 1
        => Trung bình 2 trang đúng bằng 3 lượt (1,5 lượt/trang), bảo toàn nguyên tử 100% trên cột Integer!
    """
    ma = (engine_name or "local_ocr_gpu").strip().lower()
    if not co_byok:
        if ma == "llm_context":
            return 3
        if ma == "local_hybrid_pro":
            return 2
        return 1

    if ma == "local_hybrid_pro":
        return 1
    if ma == "llm_context":
        da_chay = await dem_so_trang_byok_m3_hom_nay(session, danh_tinh)
        # Trang đầu tiên (da_chay chẵn: 0, 2, 4...) trừ 2; trang kế tiếp (da_chay lẻ: 1, 3, 5...) trừ 1 -> 2 + 1 = 3 / 2 = 1.5
        return 2 if (da_chay % 2 == 0) else 1
    return 1


def tinh_tong_luot_cho_me_trang(
    so_trang: int,
    engine_name: str | None,
    *,
    co_byok: bool = False,
    da_chay_byok_m3_hom_nay: int = 0,
) -> list[int]:
    """Trả danh sách số lượt trừ cho từng trang trong 1 mẻ nhiều trang (ZIP/CBZ/PDF/Chapter):
    Ví dụ 10 trang Model 3 + BYOK => [2, 1, 2, 1, 2, 1, 2, 1, 2, 1] => tổng đúng 15 lượt (thay vì 30 lượt)!
    """
    n = max(0, int(so_trang))
    ma = (engine_name or "local_ocr_gpu").strip().lower()
    if not co_byok:
        c = 3 if ma == "llm_context" else (2 if ma == "local_hybrid_pro" else 1)
        return [c] * n
    if ma == "local_hybrid_pro":
        return [1] * n
    if ma == "llm_context":
        return [2 if ((da_chay_byok_m3_hom_nay + i) % 2 == 0) else 1 for i in range(n)]
    return [1] * n


# ---------- Mã hóa đối xứng tạm thời (Ephemeral Cipher) cho Worker bất đồng bộ ----------

def _tao_keystream(secret: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        blk = hmac.new(secret, nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest()
        out.extend(blk)
        counter += 1
    return bytes(out[:length])


def _lay_secret_byok(settings: "Settings") -> bytes:
    try:
        from app.core.config import lay_khoa_bi_mat_noi_bo

        return lay_khoa_bi_mat_noi_bo(settings, nhan="byok-ephemeral-v1")
    except ImportError:
        raw = str(getattr(settings, "khoa_bi_mat_phien", None) or "byok-local-test-secret")
        return hashlib.sha256(f"byok-ephemeral-v1:{raw}".encode("utf-8")).digest()


def ma_hoa_byok_tam_thoi(cfg: CauHinhBYOK, settings: "Settings", ttl_giay: int = 1800) -> str:
    """Mã hóa cấu hình BYOK kèm thời hạn tự hủy (mặc định 30 phút) để Worker đọc mà không lưu khóa thô."""
    secret = _lay_secret_byok(settings)
    payload = json.dumps(
        {
            "p": cfg.provider,
            "k": cfg.api_key,
            "m": cfg.model,
            "exp": int(time.time()) + max(60, int(ttl_giay)),
        },
        separators=(",", ":"),
    ).encode("utf-8")
    nonce = os.urandom(16)
    ks = _tao_keystream(secret, nonce, len(payload))
    ct = bytes(a ^ b for a, b in zip(payload, ks))
    mac = hmac.new(secret, nonce + ct, hashlib.sha256).digest()[:16]
    return base64.urlsafe_b64encode(nonce + mac + ct).decode("ascii")


def giai_ma_byok_tam_thoi(token: str | None, settings: "Settings") -> CauHinhBYOK | None:
    """Giải mã cấu hình BYOK tạm thời trong Worker; trả `None` nếu sai chữ ký hoặc đã quá hạn TTL."""
    if not token or not isinstance(token, str):
        return None
    try:
        raw = base64.urlsafe_b64decode(token.strip().encode("ascii"))
        if len(raw) <= 32:
            return None
        nonce, mac_nhan, ct = raw[:16], raw[16:32], raw[32:]
        secret = _lay_secret_byok(settings)
        mac_dung = hmac.new(secret, nonce + ct, hashlib.sha256).digest()[:16]
        if not hmac.compare_digest(mac_nhan, mac_dung):
            return None
        ks = _tao_keystream(secret, nonce, len(ct))
        pt = bytes(a ^ b for a, b in zip(ct, ks))
        data = json.loads(pt.decode("utf-8"))
        if int(data.get("exp") or 0) < int(time.time()):
            return None
        prov = str(data.get("p") or "gemini").strip()
        key = str(data.get("k") or "").strip()
        mod = str(data.get("m") or "").strip()
        if not key:
            return None
        return CauHinhBYOK(provider=prov, api_key=key, model=mod)
    except Exception:  # noqa: BLE001
        return None


def kiem_tra_ket_noi_byok(cfg: CauHinhBYOK, timeout: float = 12.0) -> dict:
    """Kiểm tra trực tiếp API Key cá nhân của người dùng bằng 1 câu chào siêu nhẹ (~5 token).
    Không dùng bất kỳ khóa nào của máy chủ.
    """
    from app.services.translate.engines import LLMContextTranslator

    t0 = time.perf_counter()
    khoa_dt = cfg.khoa_dinh_tuyen(vision=False)
    try:
        tr = LLMContextTranslator(
            api_keys=[khoa_dt],
            model_name=cfg.model or NHA_CUNG_CAP_BYOK.get(cfg.provider, {}).get("model_text", "gemini-2.5-flash"),
            timeout=int(max(5, timeout)),
            max_output_tokens=64,
            json_mode=True,
        )
        kq = tr.translate(["こんにちは"], source_lang="ja", target_lang="vi")
        ms = int((time.perf_counter() - t0) * 1000)
        mau = (kq[0] if kq else "").strip()
        if not mau:
            return {
                "ok": False,
                "provider": cfg.provider,
                "ten_nha_cung_cap": cfg.ten_nha_cung_cap,
                "model": cfg.model or NHA_CUNG_CAP_BYOK.get(cfg.provider, {}).get("model_text", ""),
                "latency_ms": ms,
                "thong_diep": "API Key phản hồi rỗng. Vui lòng kiểm tra lại tên Model hoặc quyền truy cập Key.",
            }
        return {
            "ok": True,
            "provider": cfg.provider,
            "ten_nha_cung_cap": cfg.ten_nha_cung_cap,
            "model": cfg.model or NHA_CUNG_CAP_BYOK.get(cfg.provider, {}).get("model_text", ""),
            "latency_ms": ms,
            "mau_dich_thu": mau,
            "thong_diep": (
                f"✅ Kết nối {cfg.ten_nha_cung_cap} thành công ({ms}ms — thử nghiệm: 'こんにちは' → '{mau}')! "
                "Đã kích hoạt ưu đãi giảm 50% lượt: Model 2 còn 1 lượt/trang, Model 3 còn 1,5 lượt/trang."
            ),
        }
    except Exception as exc:  # noqa: BLE001
        ms = int((time.perf_counter() - t0) * 1000)
        chi_tiet = str(exc)
        # Che mọi mảnh khóa nếu vô tình xuất hiện trong chuỗi ngoại lệ
        if cfg.api_key and cfg.api_key in chi_tiet:
            chi_tiet = chi_tiet.replace(cfg.api_key, "***")
        return {
            "ok": False,
            "provider": cfg.provider,
            "ten_nha_cung_cap": cfg.ten_nha_cung_cap,
            "model": cfg.model or NHA_CUNG_CAP_BYOK.get(cfg.provider, {}).get("model_text", ""),
            "latency_ms": ms,
            "thong_diep": f"❌ Không kết nối được {cfg.ten_nha_cung_cap}: {chi_tiet[:220]}",
        }
