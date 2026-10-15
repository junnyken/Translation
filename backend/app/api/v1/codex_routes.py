"""E73 — đăng nhập ChatGPT kiểu Codex (device code) cho engine `chatgpt_codex`.

Ranh giới (đầy đủ ở docstring `app/services/translate/codex.py`):
- Chỉ tồn tại khi `CHE_DO_CAI_CUC_BO=true`. Tắt ⇒ mọi đường dẫn ở đây trả **404**, như chưa từng có.
- Chỉ QUẢN TRỊ (người cài) — người khác nhận 404 (`quan_tri_hien_tai`).
- KHÔNG bao giờ trả token. Chỉ trả mã thiết bị để người dùng gõ vào trang OpenAI, và email/gói của
  tài khoản đã đăng nhập.

Endpoint viết `def` (không `async`) có chủ đích: gọi `auth.openai.com` bằng `urllib` đồng bộ, FastAPI
chạy hàm `def` trong threadpool nên không chặn vòng sự kiện.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.v1.xac_thuc_routes import quan_tri_hien_tai
from app.core.config import Settings, get_settings
from app.models import NguoiDung

router = APIRouter(prefix="/codex", tags=["codex"])


def _xac_thuc(settings: Settings):
    if not settings.che_do_cai_cuc_bo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy.")
    from app.services.translate.codex import XacThucCodex

    return XacThucCodex(settings.codex_auth_path)


def _loi(exc: Exception) -> HTTPException:
    # Thông điệp của `TranslationFailed` ở codex.py không chứa token (chỉ mã HTTP + thân lỗi ngắn).
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)[:300])


@router.get("")
def trang_thai_codex(
    settings: Settings = Depends(get_settings),
    _: NguoiDung = Depends(quan_tri_hien_tai),
) -> dict:
    """Đã đăng nhập chưa, bằng tài khoản nào. Không gọi mạng."""
    from app.services.translate.engines import TranslationFailed

    xt = _xac_thuc(settings)
    try:
        tk = xt.tai_khoan()
    except TranslationFailed:
        tk = None  # tệp token hỏng/không có mã tài khoản ⇒ coi như chưa đăng nhập
    return {
        "da_dang_nhap": tk is not None,
        "email": tk.email if tk else None,
        "goi": tk.goi if tk else None,
        "dang_cho_xac_nhan": xt.kho.doc_cho() is not None,
    }


@router.post("/dang-nhap")
def bat_dau_dang_nhap(
    settings: Settings = Depends(get_settings),
    _: NguoiDung = Depends(quan_tri_hien_tai),
) -> dict:
    """Bước 1: lấy mã thiết bị. Người dùng mở `link`, gõ `ma`, rồi gọi `/codex/dang-nhap/hoi`."""
    from app.services.translate.engines import TranslationFailed

    xt = _xac_thuc(settings)
    try:
        return xt.bat_dau()
    except TranslationFailed as exc:
        raise _loi(exc) from exc


@router.post("/dang-nhap/hoi")
def hoi_trang_thai_dang_nhap(
    settings: Settings = Depends(get_settings),
    _: NguoiDung = Depends(quan_tri_hien_tai),
) -> dict:
    """Bước 2: hỏi OpenAI MỘT lần. `trang_thai`: cho_xac_nhan | da_dang_nhap | het_han | chua_bat_dau."""
    from app.services.translate.engines import TranslationFailed

    xt = _xac_thuc(settings)
    try:
        return {"trang_thai": xt.hoi_lai()}
    except TranslationFailed as exc:
        raise _loi(exc) from exc


@router.delete("", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def dang_xuat_codex(
    settings: Settings = Depends(get_settings),
    _: NguoiDung = Depends(quan_tri_hien_tai),
) -> Response:
    """Xoá token khỏi máy. Không gọi OpenAI thu hồi — tự thu hồi trong cài đặt tài khoản ChatGPT."""
    _xac_thuc(settings).dang_xuat()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
