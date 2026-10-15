"""E72 — dịch bằng LLM chạy trên máy (Ollama / LM Studio / llama.cpp) qua API kiểu OpenAI.

Gọi một máy chủ HTTP THẬT dựng trong test (không vá `urlopen`), để kiểm đúng cửa mà engine đi qua:
thân request, ép `json_schema`, ghép theo `id`, lỗi kết nối ⇒ `TranslationFailed` (đường lùi bắt).
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.models.enums import TranslationEngine
from app.services.translate.engines import ENGINE_LLM, TranslationFailed, get_translator
from app.services.translate.llm_cuc_bo import SCHEMA_DICH_JSON, OpenAICompatTranslator


@pytest.fixture
def may_chu():
    """Máy chủ kiểu OpenAI: ghi lại thân request, trả `tra[0]` (mã, nội dung assistant)."""
    ghi: list[dict] = []
    tra: list = [(200, json.dumps({"translations": [{"id": 1, "text": "Xin chào.", "doan": False}]}))]

    class _H(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            than = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            ghi.append({"path": self.path, "auth": self.headers.get("Authorization"), **than})
            ma, noi_dung = tra[0]
            body = json.dumps({
                "choices": [{"message": {"role": "assistant", "content": noi_dung}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
            } if ma == 200 else {"error": noi_dung}).encode()
            self.send_response(ma)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    sv = HTTPServer(("127.0.0.1", 0), _H)
    threading.Thread(target=sv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{sv.server_port}/v1", ghi, tra
    sv.shutdown()


def _may(url, **kw):
    kw.setdefault("model_name", "qwen3:14b")
    return OpenAICompatTranslator(base_url=url, **kw)


def test_goi_dung_cua_va_ep_json_schema(may_chu):
    url, ghi, _ = may_chu
    may = _may(url)
    assert may.translate(["Hello"], "en", "vi") == ["Xin chào."]
    r = ghi[0]
    assert r["path"] == "/v1/chat/completions" and r["model"] == "qwen3:14b"
    assert r["response_format"]["type"] == "json_schema"
    assert r["response_format"]["json_schema"]["schema"] == SCHEMA_DICH_JSON
    assert r["auth"] is None, "không khai khoá thì không gửi Authorization"
    assert may.usage.prompt_tokens == 11 and may.usage.output_tokens == 7


def test_dung_chung_prompt_E71(may_chu):
    url, ghi, _ = may_chu
    _may(url, boi_canh="THUẬT NGỮ: X → Y").translate(["Hello"], "en", "vi")
    prompt = ghi[0]["messages"][0]["content"][-1]["text"]
    assert prompt == _may(url, boi_canh="THUẬT NGỮ: X → Y").build_prompt_json(["Hello"], "en", "vi")


def test_ghep_theo_id_va_co_doan(may_chu):
    url, _, tra = may_chu
    tra[0] = (200, json.dumps({"translations": [
        {"id": 2, "text": "Hai.", "doan": True}, {"id": 1, "text": "Một.", "doan": False},
    ]}))
    may = _may(url)
    assert may.translate(["one", "two"], "en", "vi") == ["Một.", "Hai."]
    assert may.vung_khong_chac == {1}


def test_khong_thi_giac_thi_khong_gui_anh(may_chu):
    url, ghi, _ = may_chu
    _may(url, anh_trang=b"\xff\xd8anh").translate(["a"], "ja", "vi")
    assert [c["type"] for c in ghi[0]["messages"][0]["content"]] == ["text"]
    _may(url, anh_trang=b"\xff\xd8anh", vision=True).translate(["a"], "ja", "vi")
    loai = [c["type"] for c in ghi[1]["messages"][0]["content"]]
    assert loai == ["image_url", "text"]
    assert ghi[1]["messages"][0]["content"][0]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_co_khoa_thi_gui_bearer(may_chu):
    url, ghi, _ = may_chu
    _may(url, api_key="lm-studio").translate(["a"], "en", "vi")
    assert ghi[0]["auth"] == "Bearer lm-studio"


def test_chua_dat_model_thi_bao_ro_khong_doan(may_chu):
    url, ghi, _ = may_chu
    with pytest.raises(TranslationFailed, match="LOCAL_LLM_MODEL"):
        _may(url, model_name="").translate(["a"], "en", "vi")
    assert ghi == [], "chưa cấu hình thì không được gọi máy chủ"


def test_may_chu_chua_bat_thi_loi_de_duong_lui_bat():
    with pytest.raises(TranslationFailed, match="local_llm_khong_ket_noi"):
        _may("http://127.0.0.1:9/v1", timeout=3).translate(["a"], "en", "vi")


def test_may_chu_loi_500_thi_bao(may_chu):
    url, _, tra = may_chu
    tra[0] = (500, "model not loaded")
    with pytest.raises(TranslationFailed, match="local_llm HTTP 500"):
        _may(url).translate(["a"], "en", "vi")


def test_tra_json_hong_thi_bao(may_chu):
    url, _, tra = may_chu
    tra[0] = (200, "1. Xin chào")
    with pytest.raises(TranslationFailed, match="llm_json_invalid"):
        _may(url).translate(["a"], "en", "vi")


def test_factory_va_nhom_engine_llm():
    assert isinstance(
        get_translator("local_llm", base_url="http://x/v1", model_name="m"), OpenAICompatTranslator,
    )
    assert TranslationEngine.local_llm.value in ENGINE_LLM


def test_task_dung_cau_hinh_local_llm(monkeypatch):
    from app.workers import tasks

    monkeypatch.setattr(tasks.settings, "local_llm_model", "gemma3:12b")
    monkeypatch.setattr(tasks.settings, "local_llm_base_url", "http://may:1234/v1")
    may = tasks.build_translator("local_llm", "THUẬT NGỮ", (b"anh", "image/png"))
    assert (may.model_name, may.base_url, may.boi_canh) == ("gemma3:12b", "http://may:1234/v1", "THUẬT NGỮ")
    assert may.anh_trang is None, "LOCAL_LLM_VISION mặc định tắt ⇒ không giữ ảnh"
