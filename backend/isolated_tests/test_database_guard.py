import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('test_database_guard', Path(__file__).parents[1] / 'app/services/test_database_guard.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


@pytest.mark.parametrize('host', ['localhost', '127.0.0.1', '[::1]', 'db-test'])
def test_accepts_only_dedicated_local_database(host):
    guard.validate_test_database_url(f'postgresql+asyncpg://tester:password@{host}:5433/translation_test')


@pytest.mark.parametrize('url', [
    'postgresql+asyncpg://tester@localhost/translation',
    'postgresql+asyncpg://tester@production/translation_test',
    'postgresql+asyncpg://tester@localhost/translation_test?host=production',
    'postgresql+asyncpg://tester@localhost/translation_test#anything',
    'postgresql+asyncpg://tester@localhost/translation_test/other',
    'sqlite:///translation_test', '',
])
def test_rejects_before_destructive_setup_without_echoing_credentials(url):
    with pytest.raises(ValueError, match='refusing destructive migration') as error:
        guard.validate_test_database_url(url)
    assert url not in str(error.value) if url else True
