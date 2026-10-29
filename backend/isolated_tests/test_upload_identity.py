"""Pure request identity tests: no PostgreSQL correctness claims."""
import importlib.util
import uuid
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("upload_identity", Path(__file__).parents[1] / "app/services/upload_identity.py")
identity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(identity)


def options():
    return dict(source_lang="en", target_lang="vi", engine="llm_context", che_do="chi_chu",
                font_style="comic", tu_dien_rieng="Pepper = Tiêu", tao_chapter_rieng=True)


def test_same_bytes_and_choices_have_stable_identity():
    assert identity.upload_fingerprint(b"image", **options()) == identity.upload_fingerprint(b"image", **dict(reversed(list(options().items()))))


@pytest.mark.parametrize("field,new", [("source_lang", "ja"), ("target_lang", "en"),
    ("engine", "google_fast"), ("che_do", "day_du"), ("font_style", "romance"),
    ("tu_dien_rieng", "Pepper = Pepper"), ("tao_chapter_rieng", False)])
def test_each_translation_choice_is_part_of_identity(field, new):
    changed = options()
    changed[field] = new
    assert identity.upload_fingerprint(b"image", **options()) != identity.upload_fingerprint(b"image", **changed)


def test_original_bytes_are_bound_even_if_image_would_look_the_same():
    assert identity.upload_fingerprint(b"image", **options()) != identity.upload_fingerprint(b"image+metadata", **options())


def test_empty_optional_fields_have_consistent_identity():
    one, two = options(), options()
    one.update(font_style=None, tu_dien_rieng=None)
    two.update(font_style="", tu_dien_rieng="")
    assert identity.upload_fingerprint(b"image", **one) == identity.upload_fingerprint(b"image", **two)


def test_lock_is_stable_and_scoped_to_owner_and_key():
    owner, key = uuid.uuid4(), uuid.uuid4()
    lock = identity.upload_lock_id(owner, key)
    assert lock == identity.upload_lock_id(str(owner), str(key))
    assert -(2**63) <= lock < 2**63
    assert lock != identity.upload_lock_id(uuid.uuid4(), key)
    assert lock != identity.upload_lock_id(owner, uuid.uuid4())
