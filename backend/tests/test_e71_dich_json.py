"""E71 — `llm_context` gửi đoạn có `id`, ép schema JSON, ghép bản dịch theo `id` (giao thức Koharu).

Canh:
- Thân request có `responseSchema` (bằng chứng E46: ép schema 45/45, xin bằng lời 24/30).
- Ghép theo `id`, không theo vị trí; thiếu id ⇒ rỗng (không bịa); id lạ/lặp ⇒ bỏ.
- `doan` và `[?]` lọt vào chữ đều bật cờ "cần xem lại" (E66) — và `[?]` không lọt vào bong bóng.
- JSON hỏng ⇒ `TranslationFailed` để đường lùi `google_fast` bắt.
- Luật NỘI DUNG giống hệt chế độ cũ; chỉ giao thức đổi.
- `goi_prompt_tho` (E17) KHÔNG bị ép schema của bản dịch.
"""
from __future__ import annotations

import json

import pytest

from app.services.translate import engines as mod
from app.services.translate.engines import (
    DAU_KHONG_CHAC,
    SCHEMA_DICH,
    LLMContextTranslator,
    TranslationFailed,
)


def _may(**kw) -> LLMContextTranslator:
    return LLMContextTranslator(api_keys=["k"], json_mode=True, **kw)


def _tra(*muc) -> str:
    return json.dumps({"translations": [dict(zip(("id", "text", "doan"), m)) for m in muc]})


@pytest.fixture
def gemini_gia(monkeypatch):
    """Thay `_http_json`: ghi lại thân request, trả `van_ban` như một câu trả lời của Gemini."""
    ghi: list[dict] = []

    def _cai(van_ban: str):
        def _fake(request, timeout):
            ghi.append(json.loads(request.data.decode("utf-8")))
            return {"candidates": [{"content": {"parts": [{"text": van_ban}]}}],
                    "usageMetadata": {"promptTokenCount": 10}}
        monkeypatch.setattr(mod, "_http_json", _fake)
        return ghi
    return _cai


# ---------- prompt ----------

def test_prompt_gui_doan_co_id_dang_json():
    p = _may().build_prompt_json(["Hello\nthere", "Bye"], "en", "vi")
    khoi = json.loads(p.split("### page.jpg\n", 1)[1])
    assert khoi == [{"id": 1, "text": "Hello there"}, {"id": 2, "text": "Bye"}]


def test_prompt_json_khong_bao_go_dau_hoi_trong_chu():
    p = _may().build_prompt_json(["a"], "ja", "vi")
    assert DAU_KHONG_CHAC not in p and "`doan` = true" in p


def test_khong_anh_thi_prompt_json_KHONG_noi_ve_anh():
    assert "ẢNH" not in _may().build_prompt_json(["a"], "ja", "vi")
    assert "ẢNH" in _may(anh_trang=b"x").build_prompt_json(["a"], "ja", "vi")


def test_boi_canh_dat_truoc_danh_sach():
    p = _may(boi_canh="THUẬT NGỮ: X → Y").build_prompt_json(["a"], "ja", "vi")
    assert p.index("THUẬT NGỮ") < p.index("### page.jpg")


@pytest.mark.parametrize("luat", [
    "Dịch theo mạch văn của cả trang",
    "Bám sát nghĩa gốc: không bỏ sót ý",
    "Giữ giọng điệu nhân vật",
    "KHÔNG được đoán ra một TỪ KHÁC HẲN",
    "TÊN RIÊNG (người, địa danh): phiên âm theo cách đọc và GIỮ NGUYÊN LÀ TÊN",
    "Tuyệt đối không để lại ký tự Nhật/Trung/Hàn",
])
def test_luat_noi_dung_giong_che_do_cu(luat):
    cu = LLMContextTranslator(api_keys=["k"]).build_prompt(["a"], "ja", "vi")
    moi = _may().build_prompt_json(["a"], "ja", "vi")
    assert luat in cu and luat in moi


# ---------- đọc kết quả ----------

def test_ghep_theo_id_khong_theo_vi_tri():
    dong, doan = LLMContextTranslator.parse_response_json(_tra((2, "Hai", False), (1, "Một", False)), 2)
    assert dong == ["Một", "Hai"] and doan == set()


def test_thieu_id_thi_rong_khong_bia():
    dong, _ = LLMContextTranslator.parse_response_json(_tra((1, "Một", False)), 3)
    assert dong == ["Một", "", ""]


def test_id_la_va_id_lap_bi_bo():
    dong, _ = LLMContextTranslator.parse_response_json(
        _tra((1, "Một", False), (1, "Lặp", False), (9, "Lạ", False), (0, "Không", False)), 2,
    )
    assert dong == ["Một", ""]


def test_doan_va_dau_hoi_lot_vao_chu_deu_bat_co():
    dong, doan = LLMContextTranslator.parse_response_json(
        _tra((1, "Một", True), (2, f"{DAU_KHONG_CHAC} Hai", False), (3, "Ba", False)), 3,
    )
    assert doan == {0, 1}
    assert dong == ["Một", "Hai", "Ba"], "dấu [?] không được lọt vào bong bóng"


@pytest.mark.parametrize("hong", ["", "1. Một\n2. Hai", '{"translations": {"id": 1}}', "[]"])
def test_json_hong_thi_bao_loi_de_duong_lui_bat(hong):
    with pytest.raises(TranslationFailed, match="llm_json_invalid"):
        LLMContextTranslator.parse_response_json(hong, 2)


# ---------- gọi API ----------

def test_translate_ep_schema_va_tra_dung_thu_tu(gemini_gia):
    ghi = gemini_gia(_tra((2, "Tạm biệt", False), (1, "Xin chào", True)))
    may = _may()
    assert may.translate(["Hello", "Bye"], "en", "vi") == ["Xin chào", "Tạm biệt"]
    assert may.vung_khong_chac == {0}
    cfg = ghi[0]["generationConfig"]
    assert cfg["responseMimeType"] == "application/json" and cfg["responseSchema"] == SCHEMA_DICH


def test_che_do_cu_khong_gui_schema(gemini_gia):
    ghi = gemini_gia("1. Xin chào")
    LLMContextTranslator(api_keys=["k"]).translate(["Hello"], "en", "vi")
    assert "responseSchema" not in ghi[0]["generationConfig"]


def test_goi_prompt_tho_khong_bi_ep_schema_dich(gemini_gia):
    ghi = gemini_gia("tự do")
    _may().goi_prompt_tho("hỏi gì đó")
    assert "responseSchema" not in ghi[0]["generationConfig"]


def test_task_truyen_co_tu_cau_hinh(monkeypatch):
    from app.workers import tasks

    nhan: dict = {}
    monkeypatch.setattr(
        "app.services.translate.engines.get_translator",
        lambda engine, **kw: nhan.update(kw) or object(),
    )
    for gia_tri in (True, False):
        monkeypatch.setattr(tasks.settings, "llm_dich_json", gia_tri)
        tasks.build_translator("llm_context")
        assert nhan["json_mode"] is gia_tri
