"""Fail closed before destructive integration-test database setup."""
from urllib.parse import unquote, urlsplit


def validate_test_database_url(url: str) -> None:
    try:
        parsed = urlsplit(url)
        name = unquote(parsed.path.removeprefix('/'))
        safe = (parsed.scheme in {'postgresql+asyncpg', 'postgresql+psycopg'}
                and parsed.hostname in {'localhost', '127.0.0.1', '::1', 'db-test'}
                and name == 'translation_test' and not parsed.query and not parsed.fragment)
    except ValueError:
        safe = False
    if not safe:
        raise ValueError('Integration tests require local/db-test PostgreSQL database translation_test; refusing destructive migration.')
