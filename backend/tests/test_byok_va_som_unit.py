from __future__ import annotations

import io
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from PIL import Image

from app.services.byok import (
    BYOKKeyError,
    CauHinhBYOK,
    doan_nha_cung_cap_tu_khoa,
    giai_ma_byok_tam_thoi,
    he_so_luot_theo_engine,
    ma_hoa_byok_tam_thoi,
    tao_uuid_trang_byok_m3,
    tinh_tong_luot_cho_me_trang,
    trich_xuat_byok_tho,
    xac_thuc_byok_cho_danh_tinh,
)
from app.services.detect.ctd import DetectedRegion
from app.services.detect.som_vision import (
    ghep_ket_qua_som_vao_khung_ctd,
    sap_xep_khung_som,
    ve_anh_set_of_mark,
    xay_loi_nhac_som_gop_dich,
)
from app.services.interfaces import BBox


def _tao_danh_tinh_gia(*, cap_do: int, la_quan_tri: bool = False):
    nguoi = SimpleNamespace(la_quan_tri=la_quan_tri)
    nguoi_goi = SimpleNamespace(la_khach=(cap_do <= 0 and not la_quan_tri), nguoi=nguoi)
    return SimpleNamespace(
        co_tai_khoan=(cap_do >= 1 or la_quan_tri),
        nguoi_goi=nguoi_goi,
        cap_do=cap_do,
        chot=[],
    )


def test_nhan_dien_6_nha_cung_cap_ai_byok():
    assert doan_nha_cung_cap_tu_khoa("AIzaSyTestKey1234567890") == "gemini"
    assert doan_nha_cung_cap_tu_khoa("sk-ant-api03-1234567890abcdef") == "claude"
    assert doan_nha_cung_cap_tu_khoa("sk-or-v1-1234567890abcdef") == "openrouter"
    assert doan_nha_cung_cap_tu_khoa("gsk_1234567890abcdefghij") == "groq"
    assert doan_nha_cung_cap_tu_khoa("sk-proj-1234567890abcdef") == "openai"

    ds_cfg = trich_xuat_byok_tho(byok_key="sk-1234567890abcdef1234", byok_provider="deepseek")
    assert ds_cfg is not None
    assert ds_cfg.provider == "deepseek"
    assert ds_cfg.khoa_dinh_tuyen(vision=False).startswith("ds|deepseek-chat|")
    assert ds_cfg.ho_tro_vision_truc_tiep is False

    cl_cfg = trich_xuat_byok_tho(byok_key="sk-ant-api03-1234567890abcdef")
    assert cl_cfg is not None
    assert cl_cfg.provider == "claude"
    assert cl_cfg.ho_tro_vision_truc_tiep is True
    assert cl_cfg.khoa_dinh_tuyen(vision=True).startswith("claude|claude-3-5-sonnet-latest|")


def test_cong_goi_1_mo_khoa_tu_goi_1_va_chan_khach_free():
    # Gói 1 (cap_do == 1) được mở khóa hoàn toàn (dùng được cho cả Model 2 = 1 lượt & Model 3 = 1,5 lượt)
    dt_goi_1 = _tao_danh_tinh_gia(cap_do=1)
    cfg = xac_thuc_byok_cho_danh_tinh(
        dt_goi_1,
        byok_key="AIzaSyDummyValidLengthKey123456",
        byok_provider="gemini",
    )
    assert cfg is not None
    assert cfg.provider == "gemini"

    # Khách Free (cap_do == 0) bị chặn không được dùng BYOK với mã 402 + tinh_nang = byok_api_key
    dt_free = _tao_danh_tinh_gia(cap_do=0)
    try:
        xac_thuc_byok_cho_danh_tinh(
            dt_free,
            byok_key="AIzaSyDummyValidLengthKey123456",
            byok_provider="gemini",
        )
        raise AssertionError("Phải chặn khách Free (cap_do == 0) khi gửi BYOK!")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 402
        detail = getattr(exc, "detail", {})
        assert detail.get("tinh_nang") == "byok_api_key"
        assert detail.get("cap_yeu_cau") == 1


def test_ke_toan_luot_byok_chinh_xac_1_va_1_5_luot_tren_so_cai_nguyen():
    assert he_so_luot_theo_engine("local_ocr_gpu", co_byok=False) == 1.0
    assert he_so_luot_theo_engine("local_hybrid_pro", co_byok=False) == 2.0
    assert he_so_luot_theo_engine("local_hybrid_pro", co_byok=True) == 1.0
    assert he_so_luot_theo_engine("llm_context", co_byok=False) == 3.0
    assert he_so_luot_theo_engine("llm_context", co_byok=True) == 1.5

    # Model 2 + BYOK: 10 trang = đúng 10 lượt (1 lượt/trang, giảm 50% từ 20 lượt)
    me_m2 = tinh_tong_luot_cho_me_trang(10, "local_hybrid_pro", co_byok=True)
    assert me_m2 == [1] * 10
    assert sum(me_m2) == 10

    # Model 3 + BYOK: chuỗi luân phiên [2, 1, 2, 1, ...] => 2 trang = 3 lượt (1,5 lượt/trang), 10 trang = 15 lượt!
    me_m3_2 = tinh_tong_luot_cho_me_trang(2, "llm_context", co_byok=True, da_chay_byok_m3_hom_nay=0)
    assert me_m3_2 == [2, 1]
    assert sum(me_m3_2) == 3

    me_m3_10 = tinh_tong_luot_cho_me_trang(10, "llm_context", co_byok=True, da_chay_byok_m3_hom_nay=0)
    assert sum(me_m3_10) == 15

    u = tao_uuid_trang_byok_m3("page-abc-1")
    assert str(u).startswith("00000150-")


def test_ma_hoa_byok_tam_thoi_roundtrip_va_het_han_ttl():
    cfg = CauHinhBYOK(provider="claude", api_key="sk-ant-api03-secret-user-key-9999", model="claude-3-5-sonnet-latest")
    fake_settings = SimpleNamespace(khoa_bi_mat_phien="test-secret-32-bytes-minimum-key!!")
    cipher = ma_hoa_byok_tam_thoi(cfg, fake_settings, ttl_giay=1800)
    assert "sk-ant-api03-secret-user-key-9999" not in cipher

    phuc_hoi = giai_ma_byok_tam_thoi(cipher, fake_settings)
    assert phuc_hoi is not None
    assert phuc_hoi.provider == "claude"
    assert phuc_hoi.api_key == "sk-ant-api03-secret-user-key-9999"
    assert phuc_hoi.model == "claude-3-5-sonnet-latest"

    # Giả lập thời gian trôi qua quá 30 phút (TTL hết hạn) -> tự hủy trả None!
    with patch("app.services.byok.time.time", return_value=9_999_999_999):
        assert giai_ma_byok_tam_thoi(cipher, fake_settings) is None


def test_set_of_mark_sap_xep_ve_nhan_ngoai_vien_va_giu_nguyen_0px_toa_do_ctd():
    anh_goc = Image.new("RGB", (600, 800), (245, 245, 245))
    buf = io.BytesIO()
    anh_goc.save(buf, format="PNG")
    raw_png = buf.getvalue()

    r_trai = DetectedRegion(bbox=BBox(x=60, y=120, w=90, h=90), confidence=0.92, cls=1)
    r_phai = DetectedRegion(bbox=BBox(x=420, y=100, w=70, h=80), confidence=0.95, cls=0)

    # Manga tiếng Nhật đọc Phải -> Trái: khung bên phải (x=420) mang nhãn #1!
    ds_ja = sap_xep_khung_som([r_trai, r_phai], source_lang="ja")
    assert (ds_ja[0].bbox.x, ds_ja[0].bbox.y) == (420, 100)
    assert (ds_ja[1].bbox.x, ds_ja[1].bbox.y) == (60, 120)

    # Manhwa tiếng Hàn đọc Trái -> Phải: khung bên trái (x=60) mang nhãn #1!
    ds_ko = sap_xep_khung_som([r_phai, r_trai], source_lang="ko")
    assert (ds_ko[0].bbox.x, ds_ko[0].bbox.y) == (60, 120)

    som_bytes, som_mime = ve_anh_set_of_mark(raw_png, ds_ja)
    assert som_mime == "image/jpeg"
    with Image.open(io.BytesIO(som_bytes)) as im_som:
        assert im_som.size == (600, 800)

    prompt = xay_loi_nhac_som_gop_dich(so_khung=2, source_lang="ja", target_lang="vi", boi_canh="Akagi: xưng tôi")
    assert "`#1` .. `#2`" in prompt
    assert "Akagi: xưng tôi" in prompt

    # Ghép kết quả Vision LLM về khung CTD: giữ nguyên 0px sai số tọa độ + giữ nguyên `mat_na_chu` cho LaMa!
    items_llm = [
        {"id": 1, "text": "何だと！？", "ban_dich": "Cái gì cơ!?", "doan": False},
        {"id": 2, "text": "", "ban_dich": "", "doan": False},
        {"id": 0, "text": "くそっ", "ban_dich": "Chết tiệt...", "doan": False, "box": [500, 500, 580, 620]},
    ]
    ket_qua = ghep_ket_qua_som_vao_khung_ctd(ds_ja, items_llm, img_w=600, img_h=800)
    assert len(ket_qua) == 2
    assert (ket_qua[0].bbox.x, ket_qua[0].bbox.y, ket_qua[0].bbox.w, ket_qua[0].bbox.h) == (420, 100, 70, 80)
    assert ket_qua[0].confidence == 0.95
    assert ket_qua[0].ban_dich == "Cái gì cơ!?"
    assert ket_qua[1].ban_dich == "Chết tiệt..."
    assert (ket_qua[1].bbox.x, ket_qua[1].bbox.y, ket_qua[1].bbox.w, ket_qua[1].bbox.h) == (300, 400, 72, 64)
