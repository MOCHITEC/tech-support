import pytest

from app.state_machine import TicketState, can_transition, validate_transition


def test_received_can_go_to_triaging():
    assert can_transition(TicketState.RECEIVED, TicketState.TRIAGING) is True


def test_received_cannot_jump_to_released():
    assert can_transition(TicketState.RECEIVED, TicketState.RELEASED) is False


def test_validate_transition_raises_on_illegal():
    with pytest.raises(ValueError):
        validate_transition(TicketState.RECEIVED, TicketState.RELEASED)


def test_terminal_state_has_no_outgoing():
    assert can_transition(TicketState.RELEASED, TicketState.FIXING) is False


def test_deploy_failed_can_retry_fixing():
    assert can_transition(TicketState.DEPLOY_FAILED, TicketState.FIXING) is True
