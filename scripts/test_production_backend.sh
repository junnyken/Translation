#!/usr/bin/env bash
# Only a dedicated disposable local test database is accepted by conftest.
set -euo pipefail
translation_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$translation_root/backend"
export PYTHONPATH="$translation_root/backend${PYTHONPATH:+:$PYTHONPATH}"
python3 -c 'import asyncpg, psycopg, alembic, pytest_asyncio' || {
  echo 'Missing test dependencies. Use a dedicated venv and requirements-dev.txt.' >&2
  exit 1
}
python3 -m pytest tests/test_production_private_context.py tests/test_production_upload_requests.py "$@"
