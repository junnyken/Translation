"""Unit — state machine của Page (M1 §7.1: nếu có validate transition thì phải test)."""
import pytest

from app.models.enums import InvalidPageTransition, PageStatus, assert_transition, can_transition


def test_queued_chi_di_toi_detecting():
    assert can_transition(PageStatus.queued, PageStatus.detecting)
    assert not can_transition(PageStatus.queued, PageStatus.detected)
    assert not can_transition(PageStatus.queued, PageStatus.ready_for_export)


def test_khong_nhay_coc_tu_detected_sang_translated():
    assert not can_transition(PageStatus.detected, PageStatus.translated)


def test_detecting_co_the_that_bai():
    assert can_transition(PageStatus.detecting, PageStatus.detection_failed)


def test_detection_failed_co_the_chay_lai():
    assert can_transition(PageStatus.detection_failed, PageStatus.detecting)


def test_assert_transition_nem_loi_khi_sai():
    with pytest.raises(InvalidPageTransition):
        assert_transition(PageStatus.queued, PageStatus.typeset_done)


def test_moi_status_deu_co_mat_trong_bang_transition():
    from app.models.enums import PAGE_STATUS_TRANSITIONS

    assert set(PAGE_STATUS_TRANSITIONS) == set(PageStatus)
