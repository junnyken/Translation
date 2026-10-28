"""Offline regressions: no real Tk, model downloads, network, or production.py.

Run only this file: python -m pytest -q windows-app/tests/test_qwen3_offline.py
Batch-file checks below are static; executing it still needs a Windows smoke test.
"""
from __future__ import annotations

import ast
import base64
import importlib.util
import io
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import urllib.error
import urllib.request
from unittest.mock import Mock

import pytest


APP_PATH = Path(__file__).resolve().parents[1] / "app_dich_truyen_windows.py"
SETUP_PATH = APP_PATH.with_name("Cai-Dich-Offline.bat")
MODEL = "qwen3-vl:8b"
TAGS = "http://127.0.0.1:11434/api/tags"
CHAT = "http://127.0.0.1:11434/api/chat"
LM_MODELS = "http://127.0.0.1:1234/v1/models"
LM_CHAT = "http://127.0.0.1:1234/v1/chat/completions"
REGION = {"box_2d": [100, 200, 300, 600], "chu_goc": "原文", "ban_dich": "Xin chào"}


@pytest.fixture
def app(monkeypatch):
    """Import the real tracked app with GUI launch and real IO forbidden."""
    def forbidden(*args, **kwargs):
        raise AssertionError("A unit test must not launch a GUI or use real network")

    tkinter = ModuleType("tkinter")
    tkinter.Tk = type("ForbiddenTk", (), {"__init__": forbidden})
    for name in ("filedialog", "messagebox", "scrolledtext", "simpledialog", "ttk"):
        child = ModuleType(f"tkinter.{name}")
        setattr(tkinter, name, child)
        monkeypatch.setitem(sys.modules, child.__name__, child)
    monkeypatch.setitem(sys.modules, "tkinter", tkinter)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    # No image processing dependency is needed for request/box conversion tests.
    monkeypatch.setitem(sys.modules, "PIL", None)
    production = ModuleType("production")
    production.ChapterLedger = object
    production.NeedsAttention = RuntimeError
    production.RunStopped = RuntimeError
    production.natural_key = lambda value: str(value)
    production.process_chapter = forbidden
    production.require_production_backend = forbidden
    monkeypatch.setitem(sys.modules, "production", production)
    spec = importlib.util.spec_from_file_location("windows_app_qwen3_test", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.Image is None
    monkeypatch.setattr(module.os, "system", forbidden)
    monkeypatch.setattr(module.webbrowser, "open", forbidden)
    return module


def mock_http(monkeypatch, app, routes):
    """Fail on every unexpected request, including downloads/remote endpoints."""
    calls = []

    def urlopen(request, timeout):
        url = request.full_url
        calls.append((request, timeout))
        assert url in routes, f"Unexpected request: {url}"
        result = routes[url]
        if isinstance(result, Exception):
            raise result
        raw = result if isinstance(result, bytes) else json.dumps(result, ensure_ascii=False).encode("utf-8")
        return io.BytesIO(raw)

    monkeypatch.setattr(app.urllib.request, "urlopen", urlopen)
    return calls


def tags(*models):
    return {"models": [{"name": model} for model in models]}


def translated(content=None):
    return {"message": {"content": content if content is not None else json.dumps({"regions": [REGION]})}}


def test_import_does_not_launch_gui_or_network(app):
    assert app.QWEN3_VL_MODEL == MODEL
    assert callable(app.dich_anh_local_gguf_tren_may_khach)


@pytest.mark.parametrize("models", [
    ("llama3:8b", MODEL, "qwen2.5vl:7b"),
    ("qwen3-vl:235b", "qwen3-vl:4b", MODEL),
    (MODEL,),
])
def test_ollama_selects_exact_qwen3_8b_and_converts_boxes(app, monkeypatch, models):
    calls = mock_http(monkeypatch, app, {TAGS: tags(*models), CHAT: translated()})
    result = app.dich_anh_local_gguf_tren_may_khach(
        b"page-image", ngon_ngu_nguon="ja", ngon_ngu_dich="en", tu_dien_rieng="A = B"
    )
    assert result == [{"x": 200, "y": 140, "w": 400, "h": 280, "chu_goc": "原文", "ban_dich": "Xin chào"}]
    assert [req.full_url for req, _ in calls] == [TAGS, CHAT]
    request, timeout = calls[1]
    payload = json.loads(request.data)
    assert timeout == 180
    assert payload["model"] == MODEL
    assert payload["stream"] is False
    assert payload["format"] == "json"
    assert payload["messages"][0]["images"] == [base64.b64encode(b"page-image").decode("ascii")]
    assert "English" in payload["messages"][0]["content"]
    assert "A = B" in payload["messages"][0]["content"]
    assert calls[0][0].get_method() == "GET"
    assert request.get_method() == "POST"


@pytest.mark.parametrize("models", [(), ("llama3:8b",), ("qwen2.5vl:7b",), ("qwen3-vl:4b",), ("qwen3-vl:235b",)])
def test_missing_model_has_actionable_error_without_fallback(app, monkeypatch, models):
    calls = mock_http(monkeypatch, app, {TAGS: tags(*models)})
    with pytest.raises(app.LocalModelMissingError) as exc:
        app.dich_anh_local_gguf_tren_may_khach(b"page")
    text = str(exc.value)
    assert "Ollama đang chạy" in text
    assert "ollama pull qwen3-vl:8b" in text
    assert "Cai-Dich-Offline.bat" in text
    assert "6.2 GB" in text
    assert "local_gguf" in text
    assert "Chưa kết nối" not in text
    assert [req.full_url for req, _ in calls] == [TAGS]


def test_no_local_servers_has_distinct_error(app, monkeypatch):
    calls = mock_http(monkeypatch, app, {
        TAGS: urllib.error.URLError("connection refused"),
        LM_MODELS: urllib.error.URLError("connection refused"),
    })
    with pytest.raises(app.LocalServerUnavailableError, match="Hãy mở Ollama"):
        app.dich_anh_local_gguf_tren_may_khach(b"page")
    assert [req.full_url for req, _ in calls] == [TAGS, LM_MODELS]


@pytest.mark.parametrize("endpoint", [TAGS, CHAT])
def test_http_error_keeps_original_cause_and_never_falls_back(app, monkeypatch, endpoint):
    routes = {TAGS: tags(MODEL)}
    routes[endpoint] = urllib.error.HTTPError(
        endpoint, 400, "Bad Request", {}, io.BytesIO(b'{"error":"model not supported"}')
    )
    calls = mock_http(monkeypatch, app, routes)
    with pytest.raises(RuntimeError, match="model not supported") as exc:
        app.dich_anh_local_gguf_tren_may_khach(b"page")
    assert not isinstance(exc.value, app.LocalServerUnavailableError)
    assert "HTTP 400" in str(exc.value)
    assert "cập nhật Ollama" in str(exc.value)
    assert LM_MODELS not in [req.full_url for req, _ in calls]


CRASH_BODY = (
    b'{"error":"llama-server process has terminated: exit status 0xc0000409 '
    b'CUDA error: shared object initialization failed"}'
)


def test_runner_crash_gets_specific_error_not_generic_update_advice(app, monkeypatch):
    routes = {
        TAGS: tags(MODEL),
        CHAT: urllib.error.HTTPError(CHAT, 500, "Server Error", {}, io.BytesIO(CRASH_BODY)),
    }
    calls = mock_http(monkeypatch, app, routes)
    with pytest.raises(app.LocalRuntimeCrashError) as exc:
        app.dich_anh_local_gguf_tren_may_khach(b"page")
    text = str(exc.value)
    assert "0xc0000409" in text and "server.log" in text and "CPU" in text
    assert "cập nhật Ollama từ" not in text
    assert LM_MODELS not in [req.full_url for req, _ in calls]


def test_cpu_mode_is_opt_in_and_sets_num_gpu_zero(app, monkeypatch):
    calls = mock_http(monkeypatch, app, {TAGS: tags(MODEL), CHAT: translated()})
    app.dich_anh_local_gguf_tren_may_khach(b"page")
    assert "num_gpu" not in json.loads(calls[1][0].data)["options"]
    assert calls[1][1] == 180
    calls = mock_http(monkeypatch, app, {TAGS: tags(MODEL), CHAT: translated()})
    app.dich_anh_local_gguf_tren_may_khach(b"page", chay_cpu=True)
    assert json.loads(calls[1][0].data)["options"]["num_gpu"] == 0
    assert calls[1][1] == app.TIMEOUT_CPU > 180


def test_smoke_run_sends_text_only_and_reports_crash(app, monkeypatch):
    calls = mock_http(monkeypatch, app, {TAGS: tags(MODEL), CHAT: {"message": {"content": "hi"}}})
    assert app.chay_thu_model_cuc_bo() == ("ollama", MODEL)
    payload = json.loads(calls[1][0].data)
    assert "images" not in payload["messages"][0] and "num_gpu" not in payload["options"]
    mock_http(monkeypatch, app, {
        TAGS: tags(MODEL),
        CHAT: urllib.error.HTTPError(CHAT, 500, "x", {}, io.BytesIO(CRASH_BODY)),
    })
    with pytest.raises(app.LocalRuntimeCrashError):
        app.chay_thu_model_cuc_bo()


@pytest.mark.parametrize("response", [b"not-json", [], {"error": "model load failed"}])
def test_invalid_server_response_is_not_misreported_as_no_server(app, monkeypatch, response):
    calls = mock_http(monkeypatch, app, {TAGS: response})
    with pytest.raises(RuntimeError) as exc:
        app.dich_anh_local_gguf_tren_may_khach(b"page")
    assert not isinstance(exc.value, app.LocalServerUnavailableError)
    assert "Chưa kết nối" not in str(exc.value)
    assert len(calls) == 1


@pytest.mark.parametrize("response", [{}, {"message": {}}, {"message": {"content": ""}}])
def test_smoke_run_rejects_empty_http_200_response(app, monkeypatch, response):
    mock_http(monkeypatch, app, {TAGS: tags(MODEL), CHAT: response})
    with pytest.raises(app.LocalEmptyResponseError, match="HTTP 200"):
        app.chay_thu_model_cuc_bo()


def test_smoke_run_rejects_cpu_claim_for_lm_studio(app, monkeypatch):
    calls = mock_http(monkeypatch, app, {
        TAGS: urllib.error.URLError("refused"),
        LM_MODELS: {"data": [{"id": "Qwen/Qwen3-VL-8B-Instruct"}]},
    })
    with pytest.raises(app.LocalCpuUnsupportedError, match="LM Studio"):
        app.chay_thu_model_cuc_bo(chay_cpu=True)
    assert [req.full_url for req, _ in calls] == [TAGS, LM_MODELS]


def test_chat_timeout_does_not_retry_with_different_model_or_backend(app, monkeypatch):
    calls = mock_http(monkeypatch, app, {TAGS: tags(MODEL), CHAT: TimeoutError("generation timed out")})
    with pytest.raises(app.LocalServerUnavailableError, match="api/chat"):
        app.dich_anh_local_gguf_tren_may_khach(b"page")
    assert [req.full_url for req, _ in calls] == [TAGS, CHAT]


@pytest.mark.parametrize("model_id", ["qwen3-vl:8b", "Qwen/Qwen3-VL-8B-Instruct", "qwen3-vl-8b-instruct-q4_k_m.gguf"])
def test_lm_studio_fallback_selects_qwen3_not_first_model(app, monkeypatch, model_id):
    calls = mock_http(monkeypatch, app, {
        TAGS: urllib.error.URLError("refused"),
        LM_MODELS: {"data": [{"id": "text-only"}, {"id": model_id}]},
        LM_CHAT: {"choices": [{"message": {"content": json.dumps([REGION])}}]},
    })
    result = app.dich_anh_local_gguf_tren_may_khach(b"page")
    assert result[0]["ban_dich"] == "Xin chào"
    assert [req.full_url for req, _ in calls] == [TAGS, LM_MODELS, LM_CHAT]
    payload = json.loads(calls[-1][0].data)
    assert payload["model"] == model_id
    image = payload["messages"][0]["content"][1]["image_url"]["url"]
    assert image == "data:image/jpeg;base64," + base64.b64encode(b"page").decode("ascii")


@pytest.mark.parametrize("models", [[], ["text-only"], ["qwen2.5-vl-8b"], ["qwen3-vl-235b"], ["qwen3-vl-8bother"]])
def test_lm_studio_missing_qwen3_model_is_not_swallowed(app, monkeypatch, models):
    calls = mock_http(monkeypatch, app, {
        TAGS: urllib.error.URLError("refused"),
        LM_MODELS: {"data": [{"id": model} for model in models]},
    })
    with pytest.raises(app.LocalModelMissingError, match="LM Studio đang chạy"):
        app.dich_anh_local_gguf_tren_may_khach(b"page")
    assert len(calls) == 2


@pytest.mark.parametrize("content", ["", "I cannot translate", "{}", '{"regions": "not a list"}'])
def test_bad_translation_is_not_silently_saved_as_empty_success(app, monkeypatch, content):
    mock_http(monkeypatch, app, {TAGS: tags(MODEL), CHAT: translated(content)})
    with pytest.raises(RuntimeError, match="không đúng JSON regions"):
        app.dich_anh_local_gguf_tren_may_khach(b"page")


@pytest.mark.parametrize("content", ["[]", '{"regions": []}', '{"vung": []}', "```json\n[]\n```"])
def test_valid_empty_regions_remain_supported(app, monkeypatch, content):
    mock_http(monkeypatch, app, {TAGS: tags(MODEL), CHAT: translated(content)})
    assert app.dich_anh_local_gguf_tren_may_khach(b"page") == []


@pytest.mark.parametrize("models", [(), ("llama3:8b",), (MODEL,)])
def test_check_button_never_pulls_launches_gui_or_switches_engine(app, monkeypatch, models):
    calls = mock_http(monkeypatch, app, {TAGS: tags(*models), CHAT: {"message": {"content": "hi"}}})
    state = SimpleNamespace(
        ghi_log=Mock(), cmb_engine=SimpleNamespace(current=Mock()), after=Mock(),
        var_cpu_ollama=SimpleNamespace(get=lambda: False), cau_hinh={}, _luu_cau_hinh=Mock(),
    )

    class ImmediateThread:
        def __init__(self, *, target, daemon):
            assert daemon is True
            self.target = target

        def start(self):
            self.target()

    monkeypatch.setattr(app.threading, "Thread", ImmediateThread)
    app.AppDichTruyenWindows._kiem_tra_gguf_cuc_bo(state)
    state.cmb_engine.current.assert_not_called()
    state.after.assert_not_called()
    text = "\n".join(call.args[0] for call in state.ghi_log.call_args_list)
    assert "local_gguf (Qwen3-VL 8B Offline)" in text
    if not models or MODEL not in models:
        assert "ollama pull qwen3-vl:8b" in text
    else:
        assert "hãy tự chọn" in text
    assert [req.full_url for req, _ in calls] == ([TAGS, CHAT] if MODEL in models else [TAGS])


def test_default_stays_gemini_and_local_label_is_explicit():
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "AppDichTruyenWindows")
    ui = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "_dung_giao_dien")
    assignment = next(node for node in ast.walk(ui) if isinstance(node, ast.Assign)
                      and any(isinstance(t, ast.Attribute) and t.attr == "cmb_engine" for t in node.targets))
    values = next(kw.value for kw in assignment.value.keywords if kw.arg == "values")
    assert ast.literal_eval(values)[0].startswith("llm_context ")
    assert ast.literal_eval(values)[2] == "local_gguf (Qwen3-VL 8B Offline)"
    current_calls = [node for node in ast.walk(ui) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Attribute) and node.func.attr == "current"
                     and isinstance(node.func.value, ast.Attribute) and node.func.value.attr == "cmb_engine"]
    assert len(current_calls) == 1
    assert ast.literal_eval(current_calls[0].args[0]) == 0


def test_setup_batch_consent_and_error_guards_static():
    text = SETUP_PATH.read_text(encoding="utf-8")
    lowered = text.lower()
    assert "https://ollama.com/download/windows" in text
    assert 'set "OLLAMA_HOST=127.0.0.1:11434"' in text
    assert "6.2 GB" in text
    assert 'choice /C YN /N /M "Ban dong y tai model qwen3-vl:8b' in text
    assert text.index('choice /C YN /N /M "Ban dong y') < text.index('"%OLLAMA_EXE%" pull qwen3-vl:8b')
    assert 'if errorlevel 2 goto cancelled\nif not errorlevel 1 goto choice_failed\n"%OLLAMA_EXE%" pull' in text
    assert '"%OLLAMA_EXE%" pull qwen3-vl:8b\nif errorlevel 1 goto pull_failed' in text
    assert '"%OLLAMA_EXE%" list >nul\nif errorlevel 1 goto server_failed' in text
    assert '"%OLLAMA_EXE%" show qwen3-vl:8b >nul\nif errorlevel 1 goto verify_failed' in text
    for command in ("powershell", "curl ", "wget ", "invoke-webrequest", "iex", "pip install", "winget install"):
        assert command not in lowered
    assert "|" not in text
    assert "exit /b 1" in text
    assert "local_gguf (Qwen3-VL 8B Offline)" in text
