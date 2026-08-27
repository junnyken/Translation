"""Unit — 2 engine dịch: prompt, ghép dòng, xoay key, chốt tắt 'thinking' (M5 §7.1)."""
from __future__ import annotations

import json
import urllib.error

import pytest

from app.models.enums import TranslationEngine
from app.services.interfaces import ITranslator
from app.services.translate.engines import (
    GoogleTranslateEngine,
    LLMContextTranslator,
    QuotaExhausted,
    UnsupportedTranslationEngine,
    get_translator,
)


class TestFactory:
    def test_google_fast(self):
        engine = get_translator("google_fast")
        assert isinstance(engine, GoogleTranslateEngine)
        assert engine.engine_enum is TranslationEngine.google_fast

    def test_llm_context(self):
        engine = get_translator("llm_context", api_keys=["k1"])
        assert isinstance(engine, LLMContextTranslator)
        assert engine.engine_enum is TranslationEngine.llm_context

    @pytest.mark.parametrize("bad", ["gpt4", "deepl", "", "auto"])
    def test_engine_la_bao_loi_khong_fallback_am_tham(self, bad):
        with pytest.raises(UnsupportedTranslationEngine):
            get_translator(bad)

    def test_ca_hai_dung_protocol_itranslator(self):
        assert isinstance(get_translator("google_fast"), ITranslator)
        assert isinstance(get_translator("llm_context", api_keys=["k"]), ITranslator)


class TestPrompt:
    def test_giu_dung_khung_da_chot(self):
        prompt = LLMContextTranslator(["k"]).build_prompt(["A", "B"], "ja", "vi")
        assert "### page.jpg" in prompt
        assert "1. A" in prompt and "2. B" in prompt
        assert "ĐÚNG 2 dòng" in prompt

    def test_yeu_cau_dich_theo_mach_van_ca_trang(self):
        prompt = LLMContextTranslator(["k"]).build_prompt(["A"], "ja", "vi")
        assert "mạch văn" in prompt
        assert "không dịch rời rạc" in prompt.lower()

    def test_dan_llm_tu_sua_loi_ocr(self):
        """Không tự sửa raw_text (constraint 5) — nhờ LLM sửa theo ngữ cảnh."""
        assert "OCR" in LLMContextTranslator(["k"]).build_prompt(["A"], "ja", "vi")


class TestParseResponse:
    def test_tach_dung_so_dong(self):
        out = LLMContextTranslator.parse_response("1. Xin chào\n2. Cẩn thận!", 2)
        assert out == ["Xin chào", "Cẩn thận!"]

    def test_bo_qua_heading_va_dong_thua(self):
        raw = "### page.jpg\n1. Một\n2. Hai\nGhi chú linh tinh"
        assert LLMContextTranslator.parse_response(raw, 2) == ["Một", "Hai"]

    def test_thieu_dong_thi_de_rong_khong_bia(self):
        out = LLMContextTranslator.parse_response("1. Một", 3)
        assert out == ["Một", "", ""]

    def test_thua_dong_thi_cat_bot(self):
        out = LLMContextTranslator.parse_response("1. A\n2. B\n3. C", 2)
        assert out == ["A", "B"]

    @pytest.mark.parametrize("sep", [".", ")", "-", "]"])
    def test_chap_nhan_nhieu_kieu_danh_so(self, sep):
        assert LLMContextTranslator.parse_response(f"1{sep} Một", 1) == ["Một"]

    def test_response_rong(self):
        assert LLMContextTranslator.parse_response("", 2) == ["", ""]


class TestKeyRotation:
    def _translator(self, keys, responses):
        """responses: list các phản hồi giả lập, mỗi lần _http_json trả/ném 1 phần tử."""
        t = LLMContextTranslator(keys)
        calls = []

        def fake_http(request, timeout):
            calls.append(request.headers.get("X-goog-api-key") or request.headers.get("x-goog-api-key"))
            item = responses[len(calls) - 1]
            if isinstance(item, Exception):
                raise item
            return item

        import app.services.translate.engines as mod

        mod._http_json = fake_http  # type: ignore[assignment]
        return t, calls

    @staticmethod
    def _ok(text="1. Xin chào"):
        return {
            "candidates": [{"content": {"parts": [{"text": text}]}}],
            "usageMetadata": {"totalTokenCount": 42, "thoughtsTokenCount": 0},
        }

    @staticmethod
    def _http_429():
        err = urllib.error.HTTPError("u", 429, "Too Many Requests", {}, None)
        err.read = lambda: b'{"error":{"message":"quota"}}'  # type: ignore[method-assign]
        return err

    def test_gap_429_thi_chuyen_sang_key_ke_tiep(self, monkeypatch):
        import app.services.translate.engines as mod

        original = mod._http_json
        try:
            t, calls = self._translator(["key-A", "key-B"], [self._http_429(), self._ok()])
            out = t.translate(["HELLO"], "en", "vi")
            assert out == ["Xin chào"]
            assert calls == ["key-A", "key-B"], "không xoay sang key thứ hai"
            assert t.usage.key_rotations == 1
        finally:
            mod._http_json = original

    def test_het_sach_key_thi_bao_ro_khong_tra_ban_rong(self, monkeypatch):
        import app.services.translate.engines as mod

        original = mod._http_json
        try:
            t, _ = self._translator(["k1", "k2"], [self._http_429(), self._http_429()])
            with pytest.raises(QuotaExhausted):
                t.translate(["HELLO"], "en", "vi")
        finally:
            mod._http_json = original

    def test_khong_co_key_nao_thi_bao_ro(self):
        with pytest.raises(QuotaExhausted):
            LLMContextTranslator([]).translate(["X"], "en", "vi")

    def test_ghi_lai_so_token_that(self, monkeypatch):
        import app.services.translate.engines as mod

        original = mod._http_json
        try:
            t, _ = self._translator(["k"], [self._ok()])
            t.translate(["HELLO"], "en", "vi")
            assert t.usage.total_tokens == 42
        finally:
            mod._http_json = original


class TestThinkingBudget:
    def test_mac_dinh_tat_thinking(self):
        cfg = LLMContextTranslator(["k"])._generation_config()
        assert cfg["thinkingConfig"] == {"thinkingBudget": 0}

    def test_co_the_bat_lai_neu_that_su_muon(self):
        cfg = LLMContextTranslator(["k"], thinking_budget=256)._generation_config()
        assert cfg["thinkingConfig"] == {"thinkingBudget": 256}

    def test_thinking_budget_none_thi_khong_gui_truong_do(self):
        cfg = LLMContextTranslator(["k"], thinking_budget=None)._generation_config()
        assert "thinkingConfig" not in cfg

    def test_mac_dinh_khong_dung_model_2_5(self):
        """gemini-2.5-flash trả 404 'no longer available to new users' với key mới."""
        assert "2.5" not in LLMContextTranslator(["k"]).model_name


class TestGoogleFast:
    def test_dich_tung_dong_giu_dung_so_luong_va_thu_tu(self, monkeypatch):
        import app.services.translate.engines as mod

        original = mod._http_json
        try:
            seen = []

            def fake(request, timeout):
                seen.append(request.full_url)
                return ["ĐÃ DỊCH %d" % len(seen)]

            mod._http_json = fake  # type: ignore[assignment]
            out = GoogleTranslateEngine().translate(["A", "B", "C"], "en", "vi")
            assert out == ["ĐÃ DỊCH 1", "ĐÃ DỊCH 2", "ĐÃ DỊCH 3"]
            assert len(seen) == 3
        finally:
            mod._http_json = original

    def test_dong_rong_khong_goi_api(self, monkeypatch):
        import app.services.translate.engines as mod

        original = mod._http_json
        try:
            calls = []
            mod._http_json = lambda r, t: calls.append(1) or ["x"]  # type: ignore[assignment]
            assert GoogleTranslateEngine().translate(["", "  "], "en", "vi") == ["", ""]
            assert calls == []
        finally:
            mod._http_json = original

    def test_endpoint_dau_loi_thi_thu_endpoint_du_phong(self, monkeypatch):
        import app.services.translate.engines as mod

        original = mod._http_json
        try:
            state = {"n": 0}

            def fake(request, timeout):
                state["n"] += 1
                if state["n"] == 1:
                    raise urllib.error.HTTPError("u", 429, "rate", {}, None)
                return [[["Xin chào", "HELLO", None, None]]]

            mod._http_json = fake  # type: ignore[assignment]
            assert GoogleTranslateEngine().translate(["HELLO"], "en", "vi") == ["Xin chào"]
            assert state["n"] == 2, "chưa thử endpoint dự phòng"
        finally:
            mod._http_json = original
