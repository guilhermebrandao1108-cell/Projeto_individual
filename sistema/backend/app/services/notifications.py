"""Deadline alerts: e-mail the owner when a target enters "em risco" or is overdue.

Requirement from the case study: replies after 7 days were associated with more unresolved
complaints, so the team is warned *before* a deadline is missed, not only after.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..domain.sla import SlaState
from ..mailer import Mail, Mailer
from ..models import Notification, Role, Ticket, User
from .tickets import OPEN_STATUSES, target_condition

# (kind, label, due column, risk column, met column, paused column)
TARGETS = [
    ('primeira_resposta', 'primeira resposta', Ticket.first_response_due_at, Ticket.first_response_risk_at,
     Ticket.first_response_at, None),
    ('resolucao', 'resolução', Ticket.resolution_due_at, Ticket.resolution_risk_at, Ticket.resolved_at, Ticket.sla_paused_at),
]
STATES = {SlaState.EM_RISCO: 'em risco', SlaState.VENCIDO: 'vencido'}
PRIORITY_LABEL = {'baixa': 'Baixa', 'media': 'Média', 'alta': 'Alta', 'urgente': 'Urgente'}


@dataclass(frozen=True)
class Alert:
    ticket: Ticket
    kind: str
    due_at: datetime
    recipients: list[User]
    mail_subject: str
    mail_body: str


def _recipients(db: Session, t: Ticket) -> list[User]:
    """The owner; an unowned ticket goes to every active manager."""
    if t.assignee is not None and t.assignee.is_active:
        return [t.assignee]
    return list(db.scalars(select(User).where(User.role == Role.GESTOR, User.is_active).order_by(User.id)))


def pending_alerts(db: Session, now: datetime) -> list[Alert]:
    alerts = []
    for kind, label, due, risk, met, paused in TARGETS:
        for state, state_label in STATES.items():
            condition = target_condition(state, now, due, risk, met, paused)
            for t in db.scalars(select(Ticket).where(Ticket.status.in_(OPEN_STATUSES), condition).order_by(Ticket.id)).unique():
                due_at = getattr(t, due.key)
                full_kind = f'{kind}_{state.value}'
                already = set(db.scalars(select(Notification.recipient_id).where(
                    Notification.ticket_id == t.id, Notification.kind == full_kind, Notification.due_at == due_at)))
                recipients = [u for u in _recipients(db, t) if u.id not in already]
                if not recipients:
                    continue
                when = 'venceu' if state == SlaState.VENCIDO else 'vence'
                alerts.append(Alert(
                    ticket=t, kind=full_kind, due_at=due_at, recipients=recipients,
                    mail_subject=f'[Chamado #{t.id}] Prazo de {label} {state_label}',
                    mail_body=(f'O prazo de {label} do chamado #{t.id} ({t.title}) está {state_label}.\n'
                               f'Fila: {t.category.name} · Prioridade: {PRIORITY_LABEL[str(t.priority)]}\n'
                               f'O prazo {when} em {due_at:%d/%m/%Y %H:%M} (UTC).\n\n'
                               f'Abrir o chamado: {settings.app_url}/chamados/{t.id}\n'),
                ))
    return alerts


def send_alerts(db: Session, mailer: Mailer, now: datetime) -> int:
    """Send and record every pending alert. Safe to run repeatedly (e.g. every 5 minutes)."""
    sent = 0
    for alert in pending_alerts(db, now):
        for user in alert.recipients:
            mailer.send(Mail(to=user.email, subject=alert.mail_subject, body=alert.mail_body))
            # Recorded right after each send: a crash mid-run never repeats the e-mails already delivered.
            db.add(Notification(ticket_id=alert.ticket.id, recipient_id=user.id, kind=alert.kind,
                                due_at=alert.due_at, sent_at=now))
            db.commit()
            sent += 1
    return sent
