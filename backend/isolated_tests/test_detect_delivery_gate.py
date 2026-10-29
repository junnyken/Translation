"""Execute the real wrapper body with injected boundaries, without AI/SQL imports."""
import ast
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys
import uuid

import pytest


def wrapper(monkeypatch, claim):
    module = ModuleType('app.services.upload_outbox')
    module.claim_detect_job = claim
    monkeypatch.setitem(sys.modules, 'app.services.upload_outbox', module)
    tree = ast.parse((Path(__file__).parents[1] / 'app/workers/tasks.py').read_text())
    fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'run_detect_job')
    fn.decorator_list = []
    def forbidden(*args, **kwargs):
        pytest.fail('duplicate/claim failure must not execute AI, callbacks or failure mutation')
    env = dict(uuid=uuid, _run_detect=forbidden, _mark_failed=forbidden,
               bao_ket_thuc_buoc=forbidden, sync_session=forbidden)
    exec(compile(ast.Module(body=[fn], type_ignores=[]), '<real detect wrapper>', 'exec'), env)
    return env['run_detect_job']


def test_duplicate_returns_before_any_provider_or_callback(monkeypatch):
    run = wrapper(monkeypatch, lambda _: 'duplicate_or_stale')
    jid = str(uuid.uuid4())
    assert run(None, jid) == {'status': 'duplicate_ignored', 'job_id': jid}


def test_claim_failure_retries_without_failing_another_consumer(monkeypatch):
    class Retrying(Exception):
        pass
    def claim(_):
        raise ConnectionError('database unavailable')
    def retry(**kwargs):
        assert kwargs['max_retries'] is None
        assert kwargs['countdown'] == 300
        raise Retrying()
    run = wrapper(monkeypatch, claim)
    with pytest.raises(Retrying):
        run(SimpleNamespace(retry=retry, request=SimpleNamespace(retries=20)), str(uuid.uuid4()))
