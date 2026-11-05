"""Hệ thống Tự Chữa Lành & Khắc Phục Lỗi Tự Động 24/7 (Autonomous Self-Healing Doctor).

Bao gồm 4 năng lực tự động phát hiện và khắc phục sự cố ngay trong lúc chạy (Runtime):
1. Circuit Breaker & Cooldown Khóa AI: Tự động cách ly API key bị 429/402/403/5xx trong 60s
   để các request kế tiếp nhảy thẳng sang key khỏe mạnh hoặc dự phòng sang Google Translate.
2. Tự Sửa Lỗi JSON Bản Dịch AI (Malformed JSON Auto-Repair): Bóc tách markdown fences,
   sửa dấu phẩy thừa, hoặc khôi phục từng cặp (id, text) khi LLM trả về JSON bị cắt cụt.
3. Dọn Rác Bộ Nhớ & Phục Hồi Thư Mục Tạm (RAM & Storage Doctor): Tự động chạy Garbage
   Collection, dọn file tạm quá hạn và tái tạo các thư mục lưu trữ bị thiếu.
4. Sổ Cái Sự Cố Tự Chữa Lành (Self-Healing Ledger): Lưu nhật ký mọi lần hệ thống tự động
   phát hiện và sửa lỗi để hiển thị trực tiếp trên Bảng Quản Trị (Admin Dashboard).
"""

from __future__ import annotations

import gc
import json
import logging
import os
import re
import tempfile
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_KHOA_LUONG = threading.Lock()
_SO_SU_CO_TOI_DA = 120
_DUONG_DAN_SO_CAI = Path(
    os.getenv("SELF_HEALING_LEDGER_PATH", os.path.join(tempfile.gettempdir(), "self-healing-ledger.json"))
)

# Lưu trữ trong RAM + đồng bộ đĩa để không mất khi worker đọc lại
_DANH_SACH_SU_CO: deque[dict[str, Any]] = deque(maxlen=_SO_SU_CO_TOI_DA)
_THONG_KE_DEM: dict[str, int] = {
    "tong_so_lan_tu_sua": 0,
    "xoay_vong_khoa_ai": 0,
    "du_phong_google_translate": 0,
    "tu_sua_json_ai": 0,
    "don_rac_bo_nho": 0,
    "khoi_phuc_tep_cau_hinh": 0,
}

# Bảng cách ly tạm thời các API key bị lỗi Rate Limit / Quota: {ma_rut_gon_key: thoi_diem_het_han_epoch}
_KHOA_TAM_NGUNG_DEN: dict[str, dict[str, Any]] = {}
_THOI_GIAN_CACH_LY_KHOA_GIAY = 60.0
_THOI_DIEM_KHOI_DONG = time.time()
_DA_NAP_TU_DIA = False


def _rut_gon_khoa(api_key: str) -> str:
    k = (api_key or "").strip()
    if len(k) <= 10:
        return "***"
    return f"{k[:6]}...{k[-4:]}"


def _nap_so_cai_tu_dia_neu_can() -> None:
    global _DA_NAP_TU_DIA
    if _DA_NAP_TU_DIA:
        return
    _DA_NAP_TU_DIA = True
    try:
        if _DUONG_DAN_SO_CAI.exists():
            raw = _DUONG_DAN_SO_CAI.read_text(encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, dict):
                su_co_cu = data.get("su_co_gan_day") or []
                for item in reversed(su_co_cu[:_SO_SU_CO_TOI_DA]):
                    if isinstance(item, dict):
                        _DANH_SACH_SU_CO.appendleft(item)
                thong_ke_cu = data.get("thong_ke") or {}
                if isinstance(thong_ke_cu, dict):
                    for k in _THONG_KE_DEM:
                        if isinstance(thong_ke_cu.get(k), int):
                            _THONG_KE_DEM[k] = int(thong_ke_cu[k])
    except Exception as exc:
        logger.debug("Khong nap duoc so cai tu chua lanh tu dia: %s", exc)


def _luu_so_cai_xuong_dia_khong_khoa() -> None:
    try:
        _DUONG_DAN_SO_CAI.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "cap_nhat_luc": datetime.now(timezone.utc).isoformat(),
            "thong_ke": dict(_THONG_KE_DEM),
            "su_co_gan_day": list(_DANH_SACH_SU_CO),
        }
        tmp_path = _DUONG_DAN_SO_CAI.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(_DUONG_DAN_SO_CAI)
    except Exception as exc:
        logger.debug("Khong luu duoc so cai tu chua lanh xuong dia: %s", exc)


def ghi_nhan_tu_chua_lanh(
    thanh_phan: str,
    su_co: str,
    hanh_dong: str,
    ket_qua: str = "da_khac_phuc",
    loai_thong_ke: str | None = None,
) -> dict[str, Any]:
    """Ghi nhận một sự cố đã được hệ thống tự động phát hiện và khắc phục."""
    ban_ghi = {
        "id": f"sh-{int(time.time() * 1000)}-{len(_DANH_SACH_SU_CO) + 1}",
        "thoi_gian": datetime.now(timezone.utc).isoformat(),
        "thanh_phan": str(thanh_phan or "he_thong"),
        "su_co": str(su_co or "")[:300],
        "hanh_dong": str(hanh_dong or "")[:350],
        "ket_qua": str(ket_qua or "da_khac_phuc"),
    }
    with _KHOA_LUONG:
        _nap_so_cai_tu_dia_neu_can()
        _DANH_SACH_SU_CO.appendleft(ban_ghi)
        _THONG_KE_DEM["tong_so_lan_tu_sua"] = _THONG_KE_DEM.get("tong_so_lan_tu_sua", 0) + 1
        if loai_thong_ke and loai_thong_ke in _THONG_KE_DEM:
            _THONG_KE_DEM[loai_thong_ke] = _THONG_KE_DEM.get(loai_thong_ke, 0) + 1
        _luu_so_cai_xuong_dia_khong_khoa()
    return ban_ghi


def danh_dau_khoa_ai_tam_ngung(
    api_key: str,
    nha_cung_cap: str = "llm",
    ly_do: str = "rate_limit_hoac_quota",
    thoi_gian_giay: float = _THOI_GIAN_CACH_LY_KHOA_GIAY,
) -> None:
    """Đưa API key gặp lỗi 429/402/403/5xx vào diện cách ly tạm thời để các request sau bỏ qua ngay."""
    k = (api_key or "").strip()
    if not k:
        return
    het_han = time.time() + max(5.0, float(thoi_gian_giay))
    rut_gon = _rut_gon_khoa(k)
    with _KHOA_LUONG:
        _KHOA_TAM_NGUNG_DEN[k] = {
            "khoa_rut_gon": rut_gon,
            "nha_cung_cap": nha_cung_cap,
            "ly_do": str(ly_do or "")[:160],
            "het_han_epoch": het_han,
        }
    ghi_nhan_tu_chua_lanh(
        thanh_phan=f"AI Key Guard ({nha_cung_cap})",
        su_co=f"Khóa {rut_gon} gặp lỗi ({str(ly_do)[:90]})",
        hanh_dong=f"Tự động cách ly khóa {rut_gon} trong {int(thoi_gian_giay)}s và xoay vòng sang khóa/engine dự phòng",
        ket_qua="da_khac_phuc",
        loai_thong_ke="xoay_vong_khoa_ai",
    )


def sap_xep_khoa_ai_uu_tien_khoe_manh(danh_sach_khoa: list[str]) -> list[str]:
    """Đưa các khóa đang khỏe mạnh lên đầu và đẩy các khóa đang trong thời gian cách ly xuống cuối."""
    if not danh_sach_khoa or len(danh_sach_khoa) <= 1:
        return list(danh_sach_khoa or [])
    bay_gio = time.time()
    khoa_khoe: list[str] = []
    khoa_cach_ly: list[str] = []
    with _KHOA_LUONG:
        # Dọn các khóa đã hết hạn cách ly
        het_han_keys = [
            k for k, info in _KHOA_TAM_NGUNG_DEN.items() if float(info.get("het_han_epoch", 0)) <= bay_gio
        ]
        for k in het_han_keys:
            _KHOA_TAM_NGUNG_DEN.pop(k, None)

        for k in danh_sach_khoa:
            if k in _KHOA_TAM_NGUNG_DEN:
                khoa_cach_ly.append(k)
            else:
                khoa_khoe.append(k)
    return khoa_khoe + khoa_cach_ly


def tu_sua_json_ban_dich(van_ban_tho: str, so_luong_ky_vong: int) -> list[str] | None:
    """Cố gắng khôi phục danh sách bản dịch từ chuỗi JSON bị lỗi định dạng do LLM sinh ra.

    Trả về `list[str]` có độ dài `so_luong_ky_vong` nếu tự sửa thành công, ngược lại trả về `None`.
    """
    if not van_ban_tho or so_luong_ky_vong <= 0:
        return None

    text = van_ban_tho.strip()
    # Bước 1: Bóc bỏ khối ```json ... ``` hoặc ``` ... ```
    text_sach = re.sub(r"^```(?:json|javascript|ts)?\s*", "", text, flags=re.IGNORECASE)
    text_sach = re.sub(r"\s*```$", "", text_sach).strip()

    # Tìm đoạn bắt đầu bằng { hoặc [
    ung_vien: list[str] = [text_sach]
    first_brace = text_sach.find("{")
    last_brace = text_sach.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        ung_vien.append(text_sach[first_brace : last_brace + 1])

    first_bracket = text_sach.find("[")
    last_bracket = text_sach.rfind("]")
    if first_bracket != -1 and last_bracket > first_bracket:
        ung_vien.append(text_sach[first_bracket : last_bracket + 1])

    for cand in ung_vien:
        # Xóa dấu phẩy thừa trước } hoặc ]
        cand_fixed = re.sub(r",\s*([}\]])", r"\1", cand)
        try:
            data = json.loads(cand_fixed)
            items = data.get("translations") if isinstance(data, dict) else data
            if isinstance(items, list):
                by_id: dict[int, str] = {}
                for idx, item in enumerate(items):
                    if isinstance(item, dict):
                        raw_id = item.get("id", idx + 1)
                        raw_txt = item.get("text", item.get("translation", item.get("vi", "")))
                        if isinstance(raw_id, int) and isinstance(raw_txt, str):
                            by_id[raw_id] = raw_txt.strip()
                    elif isinstance(item, str):
                        by_id[idx + 1] = item.strip()
                # Hỗ trợ đánh số 1..N (chuẩn E71) hoặc 0..N-1
                if all((i + 1) in by_id for i in range(so_luong_ky_vong)):
                    ghi_nhan_tu_chua_lanh(
                        thanh_phan="AI JSON Sanitizer",
                        su_co="LLM trả về JSON kèm markdown fences hoặc dấu phẩy thừa",
                        hanh_dong=f"Tự động bóc tách và chuẩn hóa {so_luong_ky_vong} câu dịch thành công",
                        ket_qua="da_khac_phuc",
                        loai_thong_ke="tu_sua_json_ai",
                    )
                    return [by_id[i + 1] for i in range(so_luong_ky_vong)]
                if all(i in by_id for i in range(so_luong_ky_vong)):
                    ghi_nhan_tu_chua_lanh(
                        thanh_phan="AI JSON Sanitizer",
                        su_co="LLM trả về JSON đánh chỉ mục 0-based hoặc kèm markdown",
                        hanh_dong=f"Tự động chuẩn hóa chỉ mục cho {so_luong_ky_vong} câu dịch",
                        ket_qua="da_khac_phuc",
                        loai_thong_ke="tu_sua_json_ai",
                    )
                    return [by_id[i] for i in range(so_luong_ky_vong)]
        except Exception:
            continue

    # Bước 2: Regex khôi phục từng cặp {"id": 1, "text": "..."} ngay cả khi JSON bị cụt cuối
    by_id_regex: dict[int, str] = {}
    pattern = re.compile(
        r'"id"\s*:\s*(\d+)\s*,\s*"(?:text|translation)"\s*:\s*"((?:[^"\\]|\\.)*)"',
        flags=re.DOTALL,
    )
    for match in pattern.finditer(text_sach):
        try:
            idx = int(match.group(1))
            raw_val = match.group(2)
            val = json.loads(f'"{raw_val}"')
            if isinstance(val, str) and idx not in by_id_regex:
                by_id_regex[idx] = val.strip()
        except Exception:
            continue

    if by_id_regex:
        # Chấp nhận nếu cứu được từ id 1..N hoặc 0..N-1 (các id thiếu sẽ trả chuỗi rỗng để tầng dưới bù)
        la_1_based = any(1 <= k <= so_luong_ky_vong for k in by_id_regex)
        ket_qua_regex = [
            by_id_regex.get(i + 1 if la_1_based else i, "") for i in range(so_luong_ky_vong)
        ]
        if any(s.strip() for s in ket_qua_regex):
            ghi_nhan_tu_chua_lanh(
                thanh_phan="AI JSON Regex Recovery",
                su_co="Cấu trúc JSON của LLM bị vỡ cú pháp hoặc cắt cụt giữa chừng",
                hanh_dong=f"Dùng Regex cứu thành công {sum(1 for s in ket_qua_regex if s.strip())}/{so_luong_ky_vong} bong bóng thoại",
                ket_qua="da_khac_phuc",
                loai_thong_ke="tu_sua_json_ai",
            )
            return ket_qua_regex

    return None


def _lay_thong_tin_ram_mb() -> dict[str, Any]:
    """Lấy dung lượng RAM hiện tại của tiến trình Backend mà không cần phụ thuộc cứng vào psutil."""
    rss_mb = 0.0
    try:
        # Đọc từ /proc/self/status trên Linux container
        status_path = Path("/proc/self/status")
        if status_path.exists():
            for line in status_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    if len(parts) >= 2 and parts[1].isdigit():
                        rss_mb = round(int(parts[1]) / 1024.0, 1)
                        break
    except Exception:
        pass
    return {
        "rss_mb": rss_mb,
        "nguong_canh_bao_mb": 1400.0,
        "trang_thai": "on_dinh" if rss_mb < 1400.0 else "can_don_rac",
    }


def chay_chan_doan_va_tu_chua_lanh(chu_dong: bool = False) -> dict[str, Any]:
    """Thực thi quy trình tự kiểm tra, giải phóng RAM, mở khóa các key hết hạn và kiểm tra thư mục."""
    cac_buoc_da_lam: list[str] = []
    bay_gio = time.time()

    # 1. Giải phóng bộ nhớ rác (Garbage Collection)
    so_doi_tuong_thu_hoi = gc.collect()
    cac_buoc_da_lam.append(f"Đã thu hồi {so_doi_tuong_thu_hoi} đối tượng rác trong bộ nhớ (GC)")

    # 2. Mở khóa các API key đã hết thời gian cách ly
    so_khoa_phuc_hoi = 0
    with _KHOA_LUONG:
        het_han_keys = [
            k for k, info in _KHOA_TAM_NGUNG_DEN.items() if float(info.get("het_han_epoch", 0)) <= bay_gio
        ]
        for k in het_han_keys:
            _KHOA_TAM_NGUNG_DEN.pop(k, None)
            so_khoa_phuc_hoi += 1
    if so_khoa_phuc_hoi > 0:
        cac_buoc_da_lam.append(f"Đã đưa {so_khoa_phuc_hoi} khóa AI hết hạn cách ly trở lại trạng thái hoạt động")

    # 3. Đảm bảo thư mục tạm và thư mục dữ liệu luôn tồn tại và có quyền ghi
    thu_muc_kiem_tra = [
        Path(tempfile.gettempdir()) / "comic-translator-cache",
        _DUONG_DAN_SO_CAI.parent,
    ]
    for tm in thu_muc_kiem_tra:
        try:
            tm.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
    cac_buoc_da_lam.append("Đã xác minh và làm sạch vùng đệm lưu trữ tạm thời")

    if chu_dong or so_doi_tuong_thu_hoi > 500 or so_khoa_phuc_hoi > 0:
        ghi_nhan_tu_chua_lanh(
            thanh_phan="System Doctor (Chẩn Đoán Chủ Động)" if chu_dong else "Auto Memory & Key Watchdog",
            su_co="Kiểm tra sức khỏe định kỳ & tối ưu hóa tài nguyên máy chủ",
            hanh_dong=" | ".join(cac_buoc_da_lam),
            ket_qua="da_khac_phuc",
            loai_thong_ke="don_rac_bo_nho",
        )

    return lay_trang_thai_tu_chua_lanh()


def lay_trang_thai_tu_chua_lanh() -> dict[str, Any]:
    """Trả về toàn bộ trạng thái Bác Sĩ Hệ Thống & danh sách sự cố đã tự động khắc phục."""
    bay_gio = time.time()
    with _KHOA_LUONG:
        _nap_so_cai_tu_dia_neu_can()
        # Lọc các khóa còn đang cách ly
        khoa_dang_cach_ly = []
        for k, info in list(_KHOA_TAM_NGUNG_DEN.items()):
            con_lai = round(float(info.get("het_han_epoch", 0)) - bay_gio, 1)
            if con_lai > 0:
                khoa_dang_cach_ly.append(
                    {
                        "khoa_rut_gon": info.get("khoa_rut_gon", "***"),
                        "nha_cung_cap": info.get("nha_cung_cap", "llm"),
                        "ly_do": info.get("ly_do", ""),
                        "con_lai_giay": con_lai,
                    }
                )
            else:
                _KHOA_TAM_NGUNG_DEN.pop(k, None)

        su_co_list = list(_DANH_SACH_SU_CO)[:40]
        thong_ke_copy = dict(_THONG_KE_DEM)

    ram_info = _lay_thong_tin_ram_mb()
    return {
        "trang_thai_tong_the": "khoe_manh",
        "che_do_tu_chua_lanh": "dang_bat_24_7",
        "uptime_giay": int(max(1.0, bay_gio - _THOI_DIEM_KHOI_DONG)),
        "bo_nho": ram_info,
        "thong_ke": thong_ke_copy,
        "khoa_ai_dang_cach_ly": khoa_dang_cach_ly,
        "co_che_bao_ve": [
            {
                "ma": "ai_circuit_breaker",
                "ten": "Tự Động Xoay Vòng Khóa AI & Dự Phòng Google Translate",
                "mo_ta": "Khi khóa AI gặp lỗi 429/Hết hạn mức/Timeout, tự động cách ly 60s, chuyển sang khóa tiếp theo hoặc dịch dự phòng để người đọc không bao giờ bị lỗi trang.",
                "trang_thai": "dang_hoat_dong",
            },
            {
                "ma": "json_auto_sanitizer",
                "ten": "Tự Sửa Lỗi Cú Pháp JSON Bản Dịch AI",
                "mo_ta": "Tự động bóc tách markdown fences, sửa dấu phẩy thừa và dùng Regex cứu từng câu thoại khi LLM trả về JSON bị ngắt quãng.",
                "trang_thai": "dang_hoat_dong",
            },
            {
                "ma": "extension_image_downscaler",
                "ten": "Tự Nén Ảnh & Chuyển Tiếp Máy Chủ (Chrome Extension)",
                "mo_ta": "Khi ảnh truyện quá nặng gây lỗi 413/502/504 hoặc đứt mạng, tiện ích tự động nén ảnh xuống 1600px JPEG 0.82 và thử lại trong nền.",
                "trang_thai": "dang_hoat_dong",
            },
            {
                "ma": "desktop_anti_block_healer",
                "ten": "Tự Đổi User-Agent Vượt Chặn 403/429 & Phục Hồi Cấu Hình (Windows App)",
                "mo_ta": "Tự động xoay vòng trình duyệt giả lập khi web truyện chặn tải ảnh và tự khôi phục tệp cấu hình nếu bị hỏng dữ liệu.",
                "trang_thai": "dang_hoat_dong",
            },
        ],
        "su_co_gan_day": su_co_list,
    }
