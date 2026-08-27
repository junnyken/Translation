"""Unit — Pydantic schema validation (M1 §7.1)."""
import pytest
from pydantic import ValidationError

from app.models.enums import IntendedUse, SourceLang, TargetLang
from app.schemas.common import ProjectCreate


def test_project_create_reject_missing_source_lang():
    with pytest.raises(ValidationError) as exc:
        ProjectCreate(name="One Piece", intended_use="personal")
    assert "source_lang" in str(exc.value)


def test_project_create_reject_missing_intended_use():
    with pytest.raises(ValidationError) as exc:
        ProjectCreate(name="One Piece", source_lang="ja")
    assert "intended_use" in str(exc.value)


def test_project_create_reject_missing_name():
    with pytest.raises(ValidationError):
        ProjectCreate(source_lang="ja", intended_use="personal")


def test_project_create_reject_empty_name():
    with pytest.raises(ValidationError):
        ProjectCreate(name="", source_lang="ja", intended_use="personal")


@pytest.mark.parametrize("bad_lang", ["vi", "ko", "JA", "japanese", ""])
def test_project_create_reject_source_lang_ngoai_enum(bad_lang):
    with pytest.raises(ValidationError):
        ProjectCreate(name="X", source_lang=bad_lang, intended_use="personal")


@pytest.mark.parametrize("bad_use", ["commercial", "share", ""])
def test_project_create_reject_intended_use_ngoai_enum(bad_use):
    with pytest.raises(ValidationError):
        ProjectCreate(name="X", source_lang="ja", intended_use=bad_use)


def test_project_create_target_lang_mac_dinh_vi():
    p = ProjectCreate(name="X", source_lang=SourceLang.ja, intended_use=IntendedUse.study)
    assert p.target_lang is TargetLang.vi
