"""Nhận diện CHỦ THỂ của hạn mức — người đăng nhập, hoặc khách lạ qua cookie + IP.

## Vì sao khách lạ cần HAI chốt chứ không một

Cookie nhận ra trình duyệt, nhưng xoá cookie là việc một cú bấm. Nếu cookie là chốt duy nhất thì
hạn mức chỉ còn là gợi ý. IP là chốt thứ hai: xoá cookie xong vẫn còn IP chặn.

Ngược lại, IP **một mình cũng không đủ**: văn phòng, trường học, quán cà phê dùng chung một IP.
Nên trần IP phải **cao hơn** trần cookie (`han_muc_ip_khach_la` > `han_muc_khach_la`), và request
phải lọt qua **cả hai** chốt mới được chạy.

## Vì sao băm, và vì sao muối rỗng là chuyện đáng ồn ào

Sổ cái chỉ cần biết "có phải cùng một người không", không cần biết người đó ở đâu. Lưu IP thô là
giữ dữ liệu cá nhân không dùng tới.

Nhưng **băm không muối thì gần như không băm**: cả không gian IPv4 chỉ có ~4,3 tỉ địa chỉ, dựng
bảng tra SHA-256 cho toàn bộ là chuyện vài phút. Vì vậy muối rỗng được ghi WARNING chứ không âm
thầm chạy tiếp — đây đúng là kiểu "lặng lẽ lùi về đường cũ" mà dự án cấm.

## Vì sao KHÔNG tin `X-Forwarded-For` theo mặc định

Header đó do client gửi. Tin nó khi chưa có proxy ghi đè nghĩa là ai cũng tự đặt "IP" của mình
thành giá trị ngẫu nhiên mỗi lần gọi ⇒ chốt IP biến mất mà không ai thấy. Phải bật tường minh
bằng `tin_header_proxy`, và chỉ khi proxy thật sự ghi đè header.

## Cookie chứa gì

Một mã ngẫu nhiên, **không** chứa số lượt. Số lượt nằm trong sổ cái phía máy chủ; để ở cookie thì
client sửa được. Cookie đặt `HttpOnly` (JavaScript không đọc được) · `SameSite=Lax` · `Secure`
(cấu hình được, xem `cookie_khach_secure`).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass, field

from fastapi import Depends, Header, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.quyen import NguoiGoi, ma_phien_tu_header
from app.models.enums import LoaiChuThe
from app.services import tai_khoan
from app.services.han_muc import han_muc_cho

log = logging.getLogger(__name__)

TEN_COOKIE = "ma_khach"

TEN_CAP_DO = {
    0: "Free",
    1: "Trial",
    2: "Starter",
    3: "Pro",
    4: "Studio",
    5: "Unlimited",
}

#: Danh mục 3 Chế độ Dịch Truyện thực tế của hệ thống (phân tầng thông minh theo Gói):
#: - Tầng 1 (`local_ocr_gpu` - 1 lượt): OCR tách chữ cục bộ + Dịch nhanh (chi phí máy chủ ~0đ).
#: - Tầng 2 (`local_hybrid_pro` - 2 lượt, Gói 1): OCR tách chữ trước + Chỉ gửi văn bản hội thoại lên AI Ngữ Cảnh (~2.5đ/trang).
#: - Tầng 3 (`llm_context` - 3 lượt, Gói 2): Quét hình ảnh (Scan hình ảnh Vision) + AI Ngữ Cảnh Đám Mây (~35đ-60đ/trang).
DANH_SACH_MODEL_DICH_TRUYEN: tuple[dict, ...] = (
    {
        "ma": "local_ocr_gpu",
        "ten": "OCR + GPU Nhanh (Tách chữ cục bộ)",
        "nhom_goi": "free",
        "nhan_goi": "Miễn phí",
        "cap_yeu_cau": 0,
        "he_so_luot": 1,
        "he_so_luot_byok": 1,
        "nha_cung_cap": "Local OCR + Fast NMT",
        "mo_ta": "OCR tách chữ trực tiếp trên máy + dịch siêu tốc (1 lượt/trang, chi phí hạ tầng ~0đ).",
    },
    {
        "ma": "local_hybrid_pro",
        "ten": "OCR + AI Hội Thoại Pro (Chỉ gửi văn bản thoại)",
        "nhom_goi": "goi_1",
        "nhan_goi": "Gói 1",
        "cap_yeu_cau": 1,
        "he_so_luot": 2,
        "he_so_luot_byok": 1,
        "nha_cung_cap": "Local OCR + DeepSeek/Gemini/GPT/Claude Text Context",
        "mo_ta": "OCR 2 tầng chữ viết tay + chỉ gửi văn bản hội thoại lên AI sửa lỗi & chuẩn xưng hô (2 lượt/trang · cắm BYOK còn 1 lượt/trang).",
    },
    {
        "ma": "llm_context",
        "ten": "Set-of-Mark Vision + LaMa Đám Mây",
        "nhom_goi": "goi_2",
        "nhan_goi": "Gói 2",
        "cap_yeu_cau": 3,
        "cap_yeu_cau_byok": 1,
        "he_so_luot": 3,
        "he_so_luot_byok": 1.5,
        "nha_cung_cap": "CTD Set-of-Mark [#1..#N] + Vision AI + LaMa Inpaint",
        "mo_ta": "Khóa khung chữ pixel bằng CTD đánh số [#1..#N] + Vision AI đọc toàn cảnh biểu cảm + LaMa vẽ lại nét tranh phức tạp (3 lượt/trang · cắm BYOK từ Gói 1 còn 1,5 lượt/trang).",
    },
)

_ANH_XA_MODEL_CU: dict[str, str] = {
    "google_fast": "local_ocr_gpu",
}


def thong_tin_model_dich(engine_id: str | None) -> dict:
    """Trả về cấu hình của model AI theo mã `engine_id` (hỗ trợ cả mã mới lẫn mã legacy)."""
    ma_goc = (engine_id or "").strip().lower()
    ma_chuan = _ANH_XA_MODEL_CU.get(ma_goc, ma_goc)
    for item in DANH_SACH_MODEL_DICH_TRUYEN:
        if item["ma"] == ma_chuan:
            return dict(item)
    return dict(DANH_SACH_MODEL_DICH_TRUYEN[0])


def danh_sach_model_cho_cap_do(cap_do: int) -> list[dict]:
    """Trả về danh sách 6 model kèm trạng thái khóa/mở khóa và nhãn hiển thị theo cấp độ hiện tại."""
    cap = max(0, int(cap_do or 0))
    ket_qua: list[dict] = []
    for item in DANH_SACH_MODEL_DICH_TRUYEN:
        bi_khoa = cap < int(item["cap_yeu_cau"])
        ten_hien_thi = (
            f"{item['ten']} (bị khóa: {item['nhan_goi'].lower()})"
            if bi_khoa
            else item["ten"]
        )
        ket_qua.append(
            {
                **item,
                "bi_khoa": bi_khoa,
                "ten_hien_thi": ten_hien_thi,
            }
        )
    return ket_qua


_CAP_DO_GOI_MEM_CACHE: dict[str, dict] = {}
_DA_NAP_CAP_DO_GOI = False


def cap_do_tu_ma_goi(ma_goi: str, so_trang_don: int = 0) -> int:
    """Xác định cấp độ VIP (1..5) của ĐƠN GÓI CƯỚC mà khách vừa mua (chu kỳ theo tháng 30 ngày / năm).

    Đảm bảo:
    - Khách mua gói nào thì đúng số trang/credits của gói đó mang cấp độ tương ứng.
    - Khách chỉ mua gói thấp (Trial / Lite) thì giỏ lượt đó chỉ ở Cấp 1 / Cấp 2,
      KHÔNG thể dùng gói rẻ để nuôi tài khoản Studio/Unlimited hay mở khoá tính năng API.
    """
    ma = (ma_goi or "").strip().lower()
    if ma in ("unlimited_plan", "unlimited_yearly", "doanh_nghiep_api", "enterprise_scale") or so_trang_don >= 5000:
        return 5
    if ma in ("studio_monthly", "studio_yearly", "pack_2000", "nhom_dich") or so_trang_don >= 2000:
        return 4
    if ma in ("pro_monthly", "pro_yearly", "tieu_chuan") or so_trang_don >= 600:
        return 3
    if ma in ("starter_monthly", "starter_yearly", "co_ban") or so_trang_don >= 200:
        return 2
    if ma in ("trial_pack_50", "goi_moi") or so_trang_don > 0:
        return 1
    return 0


def _chuan_hoa_ban_ghi_gio(val, vi_hien_tai: int = 0) -> dict:
    """Chuẩn hoá dữ liệu giỏ lượt theo cấp của 1 user (kèm hạn sử dụng theo tháng `het_han_ts`)."""
    import time

    now_ts = int(time.time())
    if isinstance(val, int):
        cap_cu = max(0, min(5, val))
        return {
            "tong": max(0, vi_hien_tai),
            "gio": [{"cap": cap_cu, "trang": max(0, vi_hien_tai)}] if (cap_cu > 0 and vi_hien_tai > 0) else [],
        }
    if isinstance(val, dict):
        tong = max(0, int(val.get("tong", 0) or 0))
        gio_raw = val.get("gio")
        gio_sach: list[dict[str, int]] = []
        if isinstance(gio_raw, list):
            for item in gio_raw:
                if isinstance(item, dict):
                    c = max(1, min(5, int(item.get("cap", 1) or 1)))
                    tr = max(0, int(item.get("trang", 0) or 0))
                    exp_ts = int(item.get("het_han_ts", 0) or 0)
                    # Nếu giỏ có hạn sử dụng theo tháng/năm và đã quá hạn -> tự động hết hiệu lực cấp độ đó
                    if exp_ts > 0 and now_ts > exp_ts:
                        continue
                    if tr > 0:
                        rec = {"cap": c, "trang": tr}
                        if exp_ts > 0:
                            rec["het_han_ts"] = exp_ts
                        gio_sach.append(rec)
        gio_sach.sort(key=lambda x: x["cap"], reverse=True)
        return {"tong": tong, "gio": gio_sach}
    return {"tong": 0, "gio": []}


def _luu_cache_cap_do_goi_xuong_dia(cache: dict[str, dict]) -> None:
    import json
    from pathlib import Path

    raw_bytes = json.dumps(cache, ensure_ascii=False).encode("utf-8")
    try:
        Path("/tmp/cap_do_goi_khach.json").write_bytes(raw_bytes)
    except Exception:
        pass
    try:
        from app.services.storage import get_storage

        get_storage().save("quan_tri/cap_do_goi_khach.json", raw_bytes)
    except Exception:
        pass


def _nap_cache_cap_do_goi() -> dict[str, dict]:
    global _DA_NAP_CAP_DO_GOI
    if _DA_NAP_CAP_DO_GOI:
        return _CAP_DO_GOI_MEM_CACHE
    import json
    from pathlib import Path

    data: dict[str, dict] = {}
    try:
        p = Path("/tmp/cap_do_goi_khach.json")
        if p.is_file():
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for k, v in raw.items():
                    data[str(k)] = _chuan_hoa_ban_ghi_gio(v)
    except Exception:
        pass
    if not data:
        try:
            from app.services.storage import get_storage

            st = get_storage()
            raw_bytes = st.read("quan_tri/cap_do_goi_khach.json")
            if raw_bytes:
                raw = json.loads(raw_bytes.decode("utf-8"))
                if isinstance(raw, dict):
                    for k, v in raw.items():
                        data[str(k)] = _chuan_hoa_ban_ghi_gio(v)
        except Exception:
            pass
    _CAP_DO_GOI_MEM_CACHE.update(data)
    _DA_NAP_CAP_DO_GOI = True
    return _CAP_DO_GOI_MEM_CACHE


def _dong_bo_gio_theo_so_du(uid_str: str, vi_hien_tai: int) -> list[dict[str, int]]:
    """Đồng bộ số trang đã tiêu vào giỏ lượt theo nguyên tắc:
    - Ưu tiên dùng lượt của gói cấp cao nhất trước (vì khách đang hưởng quyền lợi của cấp đó).
    - Khi dùng hết số trang của gói cấp cao (vd hết 300 trang Unlimited còn lại), giỏ đó tự xoá
      và tài khoản tự động chuyển về đúng cấp của gói thấp hơn còn lại (vd 50 trang Trial Cấp 1).
    """
    cache = _nap_cache_cap_do_goi()
    if vi_hien_tai <= 0:
        if uid_str in cache and cache[uid_str].get("gio"):
            cache[uid_str] = {"tong": 0, "gio": []}
            _luu_cache_cap_do_goi_xuong_dia(cache)
        return []

    ban_ghi = _chuan_hoa_ban_ghi_gio(cache.get(uid_str), vi_hien_tai)
    gio = ban_ghi["gio"]
    if not gio:
        return []

    tong_gio = sum(x["trang"] for x in gio)
    if tong_gio > vi_hien_tai:
        # Khách đã tiêu (tong_gio - vi_hien_tai) trang -> trừ từ giỏ cấp cao nhất trước
        can_tru = tong_gio - vi_hien_tai
        gio_moi: list[dict[str, int]] = []
        for item in gio:
            if can_tru > 0:
                tru_muc = min(item["trang"], can_tru)
                con_muc = item["trang"] - tru_muc
                can_tru -= tru_muc
                if con_muc > 0:
                    rec = {"cap": item["cap"], "trang": con_muc}
                    if item.get("het_han_ts"):
                        rec["het_han_ts"] = item["het_han_ts"]
                    gio_moi.append(rec)
            else:
                gio_moi.append(item)
        ban_ghi = {"tong": vi_hien_tai, "gio": gio_moi}
        cache[uid_str] = ban_ghi
        _luu_cache_cap_do_goi_xuong_dia(cache)
    elif tong_gio < vi_hien_tai:
        # Có lượt cộng thêm ngoài luồng (vd thưởng Affiliate) -> cộng vào giỏ hiện hành
        chenh = vi_hien_tai - tong_gio
        gio[-1]["trang"] += chenh
        ban_ghi = {"tong": vi_hien_tai, "gio": gio}
        cache[uid_str] = ban_ghi
    return ban_ghi["gio"]


def ghi_nhan_cap_do_goi_mua(
    nguoi_id, ma_goi: str, so_trang_don: int = 0, so_luot_con_lai_truoc_do: int = 0
) -> int:
    """Bỏ số trang của gói vừa mua vào đúng Giỏ Cấp Độ (Bucket) của gói đó.

    Ví dụ thực tế:
    1. Khách mua gói Unlimited (5.000 trang - Cấp 5), dùng còn 300 trang, rồi mua thêm gói Trial (50 trang - Cấp 1):
       - Giỏ của khách gồm: [300 trang Cấp 5 (Unlimited), 50 trang Cấp 1 (Trial)].
       - Trong 300 trang tiếp theo, khách vẫn là Unlimited (Cấp 5).
       - Ngay khi dùng hết 300 trang Unlimited đó (số dư còn 50 trang của gói Trial), giỏ Cấp 5 bằng 0
         và tài khoản lập tức hạ về đúng Cấp 1 (Trial)! Không thể mua gói 50 trang để nuôi Unlimited mãi.
    2. Khách đang còn 50 trang Trial (Cấp 1), mua thêm gói Pro (600 trang - Cấp 3):
       - Giỏ của khách gồm: [600 trang Cấp 3 (Pro), 50 trang Cấp 1 (Trial)].
       - Vì giỏ cấp cao đứng đầu, khách được THĂNG HẠNG NGAY LẬP TỨC lên Cấp 3 (Pro)!
    """
    uid_str = str(nguoi_id or "").strip()
    if not uid_str or so_trang_don <= 0:
        return 0
    cache = _nap_cache_cap_do_goi()
    vi_truoc = max(0, int(so_luot_con_lai_truoc_do or 0))
    gio_hien = _dong_bo_gio_theo_so_du(uid_str, vi_truoc)
    if vi_truoc > 0 and not gio_hien:
        # Tài khoản cũ đã có sẵn số dư trước khi bật giỏ -> quy đổi số dư cũ theo bậc tương ứng
        cap_cu_suy_luan = (
            5 if vi_truoc >= 3500 else (4 if vi_truoc >= 1200 else (3 if vi_truoc >= 300 else (2 if vi_truoc >= 100 else 1)))
        )
        gio_hien = [{"cap": cap_cu_suy_luan, "trang": vi_truoc}]

    import time

    now_ts = int(time.time())
    so_ngay_han = 365 if "yearly" in (ma_goi or "").lower() else 30
    het_han_moi = now_ts + so_ngay_han * 86400

    cap_moi = cap_do_tu_ma_goi(ma_goi, so_trang_don)
    da_gop = False
    for item in gio_hien:
        if item["cap"] == cap_moi:
            item["trang"] += so_trang_don
            item["het_han_ts"] = max(int(item.get("het_han_ts", 0) or 0), het_han_moi)
            da_gop = True
            break
    if not da_gop:
        gio_hien.append({"cap": cap_moi, "trang": so_trang_don, "het_han_ts": het_han_moi})

    gio_hien.sort(key=lambda x: x["cap"], reverse=True)
    tong_moi = sum(x["trang"] for x in gio_hien)
    cache[uid_str] = {"tong": tong_moi, "gio": gio_hien}
    _luu_cache_cap_do_goi_xuong_dia(cache)
    return gio_hien[0]["cap"] if gio_hien else 0


def tinh_cap_do(nguoi) -> int:
    """Tính cấp độ VIP (0..5) dựa trên quyền quản trị, trần ngày riêng và GIỎ LƯỢT THEO GÓI ĐÃ MUA.

    1. KHÔNG BỊ HẠ HẠNG GIỮA CHỪNG:
       - Mua gói 5.000 trang (Unlimited) hay 600 trang (Pro) thì hưởng trọn vẹn cấp đó cho hết sạch
         5.000 trang / 600 trang đã mua.
    2. CHỐNG LÁCH BẰNG CÁCH MUA GÓI 50 TRANG ĐỂ DUY TRÌ UNLIMITED:
       - Nếu còn 300 trang Unlimited mà mua thêm gói 50 trang (Trial 19k): chỉ 300 trang đầu là Unlimited,
         khi dùng hết 300 trang đó (còn lại 50 trang Trial) thì tự động hạ về đúng Cấp 1 (Trial).
    3. GIỮ NGUYÊN TÍNH NĂNG NÂNG CẤP HẠNG TỨC THÌ:
       - Đang ở gói thấp (Trial/Starter) mà mua thêm gói cao (Pro/Studio/Unlimited) thì lập tức thăng hạng
         lên gói cao ngay giây phút thanh toán!
    """
    if nguoi is None:
        return 0
    if getattr(nguoi, "la_quan_tri", False):
        return 5  # Admin = Unlimited
    tran = int(getattr(nguoi, "tran_hang_ngay_rieng", 0) or 0)
    vi = int(getattr(nguoi, "so_luot_mua_them", 0) or 0)

    cap_tran = 0
    if tran >= 5000:
        cap_tran = 5
    elif tran >= 2000:
        cap_tran = 4
    elif tran >= 600:
        cap_tran = 3
    elif tran >= 200:
        cap_tran = 2
    elif tran > 20:
        cap_tran = 1

    if vi <= 0:
        # Nếu có hạn gói thuê bao đang active trên CSDL mà chưa dùng hết kỳ hạn (ví dụ gói Stripe/PayPal có chu kỳ):
        cap_db = int(getattr(nguoi, "cap_do_goi", 0) or 0)
        het_han_db = getattr(nguoi, "het_han_goi", None)
        if cap_db > 0 and het_han_db is not None:
            from datetime import datetime, timezone

            now_dt = datetime.now(timezone.utc)
            exp_dt = het_han_db if het_han_db.tzinfo else het_han_db.replace(tzinfo=timezone.utc)
            if exp_dt <= now_dt:
                cap_db = 0
        uid_zero = str(getattr(nguoi, "id", "") or "").strip()
        if uid_zero:
            _dong_bo_gio_theo_so_du(uid_zero, 0)
        return cap_tran

    # Ưu tiên đọc sổ giỏ lượt & cấp độ lưu trực tiếp trong CSDL (`nguoi_dung.gio_luot_json`, `cap_do_goi`, `het_han_goi`)
    gio_db_raw = getattr(nguoi, "gio_luot_json", None)
    cap_db = int(getattr(nguoi, "cap_do_goi", 0) or 0)
    het_han_db = getattr(nguoi, "het_han_goi", None)
    if isinstance(gio_db_raw, list) and len(gio_db_raw) > 0:
        ban_ghi_db = _chuan_hoa_ban_ghi_gio({"tong": sum(int(x.get("trang", 0) or 0) for x in gio_db_raw if isinstance(x, dict)), "gio": gio_db_raw}, vi)
        gio_db = ban_ghi_db["gio"]
        if not gio_db:
            return cap_tran
        tong_db = sum(x["trang"] for x in gio_db)
        if tong_db > vi:
            can_tru_db = tong_db - vi
            gio_sau_tru: list[dict[str, int]] = []
            for item in gio_db:
                if can_tru_db > 0:
                    tru_m = min(item["trang"], can_tru_db)
                    con_m = item["trang"] - tru_m
                    can_tru_db -= tru_m
                    if con_m > 0:
                        gio_sau_tru.append({"cap": item["cap"], "trang": con_m})
                else:
                    gio_sau_tru.append(item)
            if gio_sau_tru:
                return max(cap_tran, int(gio_sau_tru[0]["cap"]))
            return cap_tran
        return max(cap_tran, int(gio_db[0]["cap"]))

    if cap_db > 0 and het_han_db is not None:
        from datetime import datetime, timezone

        now_dt = datetime.now(timezone.utc)
        exp_dt = het_han_db if het_han_db.tzinfo else het_han_db.replace(tzinfo=timezone.utc)
        if exp_dt > now_dt:
            return max(cap_tran, cap_db)
        return cap_tran

    uid_str = str(getattr(nguoi, "id", "") or "").strip()
    if uid_str:
        cache = _nap_cache_cap_do_goi()
        gio = _dong_bo_gio_theo_so_du(uid_str, vi)
        if gio:
            return max(cap_tran, int(gio[0]["cap"]))
        if uid_str in cache:
            # Đã có sổ giỏ lượt nhưng toàn bộ các giỏ theo tháng đều đã hết hạn 30 ngày -> hạ về cap_tran
            return cap_tran

    # Dự phòng cho tài khoản được cộng lượt trước khi có sổ lưu giỏ:
    if vi >= 3500:
        return max(cap_tran, 5)
    if vi >= 1200:
        return max(cap_tran, 4)
    if vi >= 300:
        return max(cap_tran, 3)
    if vi >= 100:
        return max(cap_tran, 2)
    return max(cap_tran, 1)


def ten_cap_do(cap: int) -> str:
    return TEN_CAP_DO.get(int(cap), "Free")


def loi_can_nang_cap(
    *,
    cap_hien_tai: int,
    cap_yeu_cau: int,
    tinh_nang: str,
    thong_bao: str,
):
    from fastapi import HTTPException

    ten_yc = ten_cap_do(cap_yeu_cau)
    return HTTPException(
        status_code=402,
        detail={
            "loi": "can_nang_cap",
            "cap_hien_tai": cap_hien_tai,
            "ten_cap_hien_tai": ten_cap_do(cap_hien_tai),
            "cap_yeu_cau": cap_yeu_cau,
            "ten_cap_yeu_cau": ten_yc,
            "tinh_nang": tinh_nang,
            "thong_bao": thong_bao,
            "thong_diep": thong_bao,
            "url_nang_cap": "https://comic.io.vn/#bang-gia",
        },
    )


#: Ghi WARNING muối rỗng đúng MỘT lần mỗi tiến trình. Mỗi request một dòng sẽ thành lụt log và
#: bị người đọc bỏ qua — đúng thứ làm cảnh báo mất tác dụng.
_da_canh_bao_muoi = False


@dataclass(frozen=True)
class Chot:
    """Một cổng phải lọt qua. Khách lạ có hai cổng, người đăng nhập có một."""

    loai: LoaiChuThe
    chu_the: str
    tran: int


@dataclass(frozen=True)
class DanhTinhHanMuc:
    """Chủ thể của hạn mức cho một request.

    `cookie_moi` khác `None` nghĩa là request này chưa mang cookie và ta vừa cấp một mã mới —
    nơi gọi phải gửi nó về bằng `Set-Cookie`, nếu không thì lần sau lại là "khách mới".
    """

    co_tai_khoan: bool
    chot: tuple[Chot, ...]
    cookie_moi: str | None = None
    nguoi_goi: NguoiGoi = field(default_factory=NguoiGoi)
    #: E100 — Số lượt nạp thêm (không hết hạn qua đêm) của tài khoản đã đăng nhập.
    so_luot_mua_them: int = 0

    @property
    def tran_hien(self) -> int:
        """Trần ĐEM HIỆN cho người dùng.

        Là trần của chốt đầu (tài khoản, hoặc cookie) — không phải trần IP. Trần IP là hàng rào
        chống lạm dụng dùng chung, hiện nó lên chỉ làm người dùng bối rối vì con số không khớp
        với thứ họ thật sự được dùng.
        """
        return self.chot[0].tran if self.chot else 0

    @property
    def cap_do(self) -> int:
        """Cấp độ tài khoản (0=Free .. 5=Unlimited)."""
        if self.co_tai_khoan and not self.nguoi_goi.la_khach and self.nguoi_goi.nguoi is not None:
            return tinh_cap_do(self.nguoi_goi.nguoi)
        return 0

    @property
    def ten_cap_do(self) -> str:
        return ten_cap_do(self.cap_do)


def _muoi(settings: Settings) -> bytes:
    global _da_canh_bao_muoi
    muoi = settings.muoi_bam_khach
    if not muoi and not _da_canh_bao_muoi:
        _da_canh_bao_muoi = True
        log.warning(
            "MUOI_BAM_KHACH rỗng: định danh khách lạ đang băm KHÔNG muối. Toàn bộ không gian "
            "IPv4 băm hết chỉ mất vài phút, nên ai đọc được CSDL sẽ khôi phục lại được IP thô. "
            "Đặt biến môi trường MUOI_BAM_KHACH ở production."
        )
    return muoi.encode("utf-8")


def bam(gia_tri: str, settings: Settings) -> str:
    """Băm một định danh khách. HMAC-SHA256 rồi cắt còn 32 ký tự hex.

    Dùng HMAC chứ không phải `sha256(muoi + gia_tri)`: cách nối chuỗi thủ công dính lỗi kéo dài
    độ dài (length-extension), còn HMAC thì không — và nó không đắt hơn.

    Cắt 32 ký tự (128 bit) vẫn quá thừa để tránh đụng trùng, mà cột ngắn thì chỉ mục nhẹ hơn.
    """
    return hmac.new(_muoi(settings), gia_tri.encode("utf-8"), hashlib.sha256).hexdigest()[:32]


def ip_cua(request: Request, settings: Settings) -> str | None:
    """IP của người gọi. `None` khi không xác định được — nơi gọi phải xử lý, đừng đoán bừa.

    Lấy mục **trái nhất** của `X-Forwarded-For` (client gốc) và chỉ khi `tin_header_proxy` bật.
    """
    if settings.tin_header_proxy:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            dau = xff.split(",")[0].strip()
            if dau:
                return dau
    return request.client.host if request.client else None


def chot_cho_khach(request: Request, settings: Settings) -> tuple[tuple[Chot, ...], str | None]:
    """Dựng các chốt cho một khách lạ, kèm cookie mới nếu phải cấp.

    Không lấy được IP thì **chỉ còn chốt cookie** — và điều đó được ghi WARNING, vì lúc đó xoá
    cookie là vượt được hạn mức. Đây là hạ cấp có thật, không được im lặng.

    Ngoài cookie `ma_khach`, chấp nhận thêm header `X-Ma-Khach` (dài >= 16 ký tự) cho tiện ích mở
    rộng trình duyệt (`chrome-extension://`), nơi cookie `SameSite=Lax` không được trình duyệt đính
    kèm vào request `POST` chéo nguồn. Chốt IP vẫn luôn đi kèm nên không thể lách hạn mức.
    """
    ma_cookie = request.cookies.get(TEN_COOKIE)
    if not ma_cookie:
        ma_header = (
            request.headers.get("x-ma-khach")
            or request.query_params.get("ma_khach")
            or ""
        ).strip()
        if len(ma_header) >= 16:
            ma_cookie = ma_header
    cookie_moi = None
    if not ma_cookie:
        ma_cookie = secrets.token_urlsafe(24)
        cookie_moi = ma_cookie

    chot = [
        Chot(LoaiChuThe.khach_cookie, bam(ma_cookie, settings), settings.han_muc_khach_la)
    ]
    ip = ip_cua(request, settings)
    if ip:
        chot.append(
            Chot(LoaiChuThe.khach_ip, bam(ip, settings), settings.han_muc_ip_khach_la)
        )
    else:
        log.warning(
            "Không xác định được IP người gọi: hạn mức khách lạ chỉ còn chốt cookie, mà xoá "
            "cookie là vượt được. Kiểm lại cấu hình proxy."
        )
    return tuple(chot), cookie_moi


def dat_cookie_khach(response: Response, ma: str, settings: Settings) -> None:
    """Gửi cookie khách về. Tách hàm riêng để mọi nơi đặt cookie dùng chung một bộ cờ bảo mật."""
    response.set_cookie(
        TEN_COOKIE,
        ma,
        max_age=settings.cookie_khach_song_giay,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_khach_secure,
        path="/",
    )


async def danh_tinh_han_muc(
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_customer_api_key: str | None = Header(default=None, alias="X-Customer-Api-Key"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> DanhTinhHanMuc:
    """Dependency: ai đang gọi, và hạn mức của họ đo theo chốt nào.

    **Không ném 401.** Khác hẳn `nguoi_dung_hien_tai` — endpoint nào cho khách lạ vào thì dùng
    dependency này; endpoint nào bắt đăng nhập vẫn giữ `nguoi_dung_hien_tai` và dependency này
    chỉ nói thêm "hạn mức tính vào tài khoản nào".

    Cookie mới (nếu có) được gửi về **ngay tại đây**, kể cả khi request sau đó bị từ chối vì hết
    hạn mức: không cấp cookie cho request bị từ chối thì mỗi lần thử lại là một khách mới, và
    chốt cookie không bao giờ chạm trần.
    """
    ma = ma_phien_tu_header(authorization, x_customer_api_key, x_api_key)
    if not ma:
        q_key = (request.query_params.get("api_key") or "").strip()
        if q_key.startswith("tr_live_"):
            ma = q_key
    nguoi = await tai_khoan.lay_theo_ma_phien(session, ma) if ma else None
    if nguoi is None and (
        (ma and ma.startswith("tr_live_"))
        or bool(x_customer_api_key and x_customer_api_key.strip())
    ):
        # Chặn tuyệt đối việc giả mạo hoặc dùng Developer API Key (tr_live_...) đã bị thu hồi:
        # KHÔNG cho phép rớt âm thầm về chế độ khách vãng lai, đồng thời tính điểm chống dò khoá theo IP.
        from fastapi import HTTPException, status
        from app.services.han_muc import bay_gio, moc_reset_ke_tiep, ngay_han_muc
        from app.services.han_muc_dang_nhap import da_sai_bao_nhieu, ghi_nhan_dang_nhap_sai

        tran_sai = settings.so_lan_dang_nhap_sai_moi_ip_mot_ngay
        ip_k = ip_cua(request, settings) if tran_sai > 0 else None
        ip_bam_k = bam(ip_k, settings) if ip_k is not None else None
        ngay_k = ngay_han_muc() if ip_bam_k is not None else None
        if ip_bam_k is not None and ngay_k is not None:
            if await da_sai_bao_nhieu(session, ip_bam_k, ngay_k) >= tran_sai:
                reset_k = moc_reset_ke_tiep()
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    headers={"Retry-After": str(max(0, int((reset_k - bay_gio()).total_seconds())))},
                    detail="Quá nhiều lần gửi sai Developer API Key từ địa chỉ mạng này trong hôm nay.",
                )
            await ghi_nhan_dang_nhap_sai(session, ip_da_bam=ip_bam_k, ngay=ngay_k, tran=tran_sai)
            await session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Developer API Key (tr_live_...) không hợp lệ, bị giả mạo hoặc đã bị thu hồi.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if nguoi is not None:
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

    chot, cookie_moi = chot_cho_khach(request, settings)
    if cookie_moi:
        dat_cookie_khach(response, cookie_moi, settings)
    return DanhTinhHanMuc(
        co_tai_khoan=False,
        chot=chot,
        cookie_moi=cookie_moi,
        # Mã khách = chốt cookie đã băm. Cố ý KHÔNG dùng chốt IP làm danh tính dữ liệu: cả văn
        # phòng dùng chung một IP, lấy nó làm chủ sở hữu là cho người này đọc truyện người kia.
        nguoi_goi=NguoiGoi(khach=chot[0].chu_the),
    )
