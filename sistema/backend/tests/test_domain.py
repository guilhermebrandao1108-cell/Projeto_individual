"""Pure rules: state machine and SLA, without database or HTTP."""
from datetime import datetime, timedelta, timezone

import pytest

from app.domain import DomainError, PermissionDenied
from app.domain.sla import SlaState, deadlines, resume, risk_point, state
from app.domain.workflow import Action, allowed_actions, next_status
from app.models import Role, Status

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
H = timedelta(hours=1)


class TestWorkflow:
    def test_happy_path_requires_customer_confirmation(self):
        s = next_status(Status.ABERTO, Action.INICIAR, Role.ATENDENTE)
        s = next_status(s, Action.PROPOR_SOLUCAO, Role.ATENDENTE)
        assert s == Status.RESOLVIDO  # staff only proposes...
        assert next_status(s, Action.CONFIRMAR, Role.CLIENTE) == Status.FECHADO  # ...customer closes

    def test_staff_cannot_close_on_behalf_of_customer(self):
        with pytest.raises(PermissionDenied):
            next_status(Status.RESOLVIDO, Action.CONFIRMAR, Role.GESTOR)

    def test_rejecting_reopens(self):
        assert next_status(Status.RESOLVIDO, Action.REJEITAR, Role.CLIENTE) == Status.EM_ATENDIMENTO

    def test_customer_reply_resumes_work(self):
        s = next_status(Status.EM_ATENDIMENTO, Action.PEDIR_INFO, Role.ATENDENTE)
        assert next_status(s, Action.RESPOSTA_CLIENTE, Role.CLIENTE) == Status.EM_ATENDIMENTO

    @pytest.mark.parametrize('current,action', [
        (Status.FECHADO, Action.PROPOR_SOLUCAO),
        (Status.ABERTO, Action.CONFIRMAR),
        (Status.ABERTO, Action.PEDIR_INFO),
        (Status.EM_ATENDIMENTO, Action.INICIAR),
    ])
    def test_invalid_transitions(self, current, action):
        role = Role.CLIENTE if action == Action.CONFIRMAR else Role.ATENDENTE
        with pytest.raises(DomainError):
            next_status(current, action, role)

    def test_closed_ticket_is_terminal(self):
        for role in Role:
            assert allowed_actions(Status.FECHADO, role) == []

    def test_allowed_actions_depend_on_role(self):
        assert allowed_actions(Status.RESOLVIDO, Role.CLIENTE) == [Action.CONFIRMAR, Action.REJEITAR]
        assert allowed_actions(Status.RESOLVIDO, Role.ATENDENTE) == []
        assert Action.PROPOR_SOLUCAO in allowed_actions(Status.ABERTO, Role.ATENDENTE)


class TestSla:
    def test_deadlines_and_risk_points(self):
        d = deadlines(T0, 4, 48, risk_fraction=.75)
        assert (d.first_response, d.resolution) == (T0 + 4 * H, T0 + 48 * H)
        assert (d.first_response_risk, d.resolution_risk) == (T0 + 3 * H, T0 + 36 * H)

    @pytest.mark.parametrize('fraction', [0, -.1, 1.5])
    def test_invalid_risk_fraction(self, fraction):
        with pytest.raises(ValueError):
            risk_point(T0, T0 + H, fraction)

    @pytest.mark.parametrize('first,resolution', [(0, 10), (10, 5)])
    def test_invalid_policy(self, first, resolution):
        with pytest.raises(ValueError):
            deadlines(T0, first, resolution)

    @pytest.mark.parametrize('now_h,met_h,expected', [
        (1, None, SlaState.NO_PRAZO),
        (8, None, SlaState.EM_RISCO),     # at the risk point (80% of 10h)
        (11, None, SlaState.VENCIDO),
        (11, 9, SlaState.CUMPRIDO),
        (11, 10, SlaState.CUMPRIDO),      # exactly on the deadline counts as met
        (12, 10.5, SlaState.VIOLADO),
    ])
    def test_states(self, now_h, met_h, expected):
        met = None if met_h is None else T0 + met_h * H
        assert state(T0 + 10 * H, T0 + 8 * H, met, T0 + now_h * H) == expected

    def test_paused_clock_is_not_overdue(self):
        assert state(T0 + 10 * H, T0 + 8 * H, None, T0 + 30 * H, paused_at=T0 + 2 * H) == SlaState.PAUSADO

    def test_pause_never_hides_a_breach(self):
        assert state(T0 + 10 * H, T0 + 8 * H, None, T0 + 30 * H, paused_at=T0 + 12 * H) == SlaState.VENCIDO

    def test_resume_moves_deadline_by_the_pause(self):
        due, pause = resume(T0 + 10 * H, paused_at=T0 + 2 * H, now=T0 + 7 * H)
        assert (due, pause) == (T0 + 15 * H, 5 * H)

    def test_resume_after_breach_keeps_deadline(self):
        due, pause = resume(T0 + 10 * H, paused_at=T0 + 12 * H, now=T0 + 20 * H)
        assert (due, pause) == (T0 + 10 * H, 8 * H)
