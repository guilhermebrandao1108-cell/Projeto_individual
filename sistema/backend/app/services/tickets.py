"""Ticket use cases: apply domain rules, persist changes and record the audit trail.

Every function receives `now` explicitly so SLA behaviour is deterministic in tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, case, false, func, or_, select
from sqlalchemy.orm import Session

from ..config import settings
from ..domain import DomainError, PermissionDenied, sla
from ..domain.workflow import Action, next_status
from ..models import Category, EventType, Message, Priority, Role, Status, Ticket, TicketEvent, User
from . import NotFound

STAFF_ROLES = {Role.ATENDENTE, Role.GESTOR}
OPEN_STATUSES = {Status.ABERTO, Status.EM_ATENDIMENTO, Status.AGUARDANDO_CLIENTE}
PRIORITY_ORDER = {Priority.URGENTE: 0, Priority.ALTA: 1, Priority.MEDIA: 2, Priority.BAIXA: 3}


# --- SLA view -----------------------------------------------------------------
@dataclass(frozen=True)
class SlaView:
    first_response: sla.SlaState
    first_response_due_at: datetime
    resolution: sla.SlaState
    resolution_due_at: datetime


def sla_view(t: Ticket, now: datetime) -> SlaView:
    return SlaView(
        first_response=sla.state(t.first_response_due_at, t.first_response_risk_at, t.first_response_at, now),
        first_response_due_at=t.first_response_due_at,
        # Resolution counts when a solution is proposed; a rejection clears it and the clock keeps running.
        resolution=sla.state(t.resolution_due_at, t.resolution_risk_at, t.resolved_at, now, paused_at=t.sla_paused_at),
        resolution_due_at=t.resolution_due_at,
    )


# --- SLA in SQL: the same rule as domain.sla.state, as WHERE clauses ----------
def target_condition(state: sla.SlaState, now: datetime, due, risk_at, met_at, paused_at=None):
    met, pending = met_at.is_not(None), met_at.is_(None)
    paused = and_(paused_at.is_not(None), paused_at <= due) if paused_at is not None else false()
    running = and_(pending, ~paused) if paused_at is not None else pending
    return {
        sla.SlaState.CUMPRIDO: and_(met, met_at <= due),
        sla.SlaState.VIOLADO: and_(met, met_at > due),
        sla.SlaState.PAUSADO: and_(pending, paused),
        sla.SlaState.VENCIDO: and_(running, due < now),
        sla.SlaState.EM_RISCO: and_(running, due >= now, risk_at <= now),
        sla.SlaState.NO_PRAZO: and_(running, risk_at > now),
    }[state]


def sla_condition(state: sla.SlaState, now: datetime):
    """Tickets where either target (first response or resolution) is in `state`."""
    return or_(
        target_condition(state, now, Ticket.first_response_due_at, Ticket.first_response_risk_at, Ticket.first_response_at),
        target_condition(state, now, Ticket.resolution_due_at, Ticket.resolution_risk_at, Ticket.resolved_at, Ticket.sla_paused_at),
    )


# --- helpers ------------------------------------------------------------------
def _event(db: Session, t: Ticket, actor: User, type_: EventType, now: datetime, from_=None, to=None) -> None:
    db.add(TicketEvent(ticket=t, actor_id=actor.id, type=type_, from_value=from_, to_value=to, created_at=now))


def _set_status(db: Session, t: Ticket, actor: User, action: Action, now: datetime) -> None:
    new = next_status(t.status, action, actor.role)
    _event(db, t, actor, EventType.STATUS, now, t.status, new)
    if t.status == Status.AGUARDANDO_CLIENTE and t.sla_paused_at is not None:
        t.resolution_due_at, pause = sla.resume(t.resolution_due_at, t.sla_paused_at, now)
        t.resolution_risk_at = sla.risk_point(t.created_at, t.resolution_due_at, settings.sla_risk_fraction)
        t.sla_paused_seconds += int(pause.total_seconds())
        t.sla_paused_at = None
    if new == Status.AGUARDANDO_CLIENTE:
        t.sla_paused_at = now
    t.status = new


def _post(db: Session, t: Ticket, author: User, body: str, now: datetime, internal: bool = False) -> None:
    db.add(Message(ticket=t, author_id=author.id, body=body, internal=internal, created_at=now))
    _event(db, t, author, EventType.MENSAGEM, now, to='interna' if internal else 'publica')
    if author.role in STAFF_ROLES and not internal and t.first_response_at is None:
        t.first_response_at = now


def _require_open(t: Ticket) -> None:
    if t.status == Status.FECHADO:
        raise DomainError('Chamado fechado: abra um novo chamado')


# --- queries ------------------------------------------------------------------
def get_ticket(db: Session, user: User, ticket_id: int) -> Ticket:
    t = db.get(Ticket, ticket_id)
    # Customers get 404 (not 403) for other people's tickets, so ids are not revealed.
    if t is None or (user.role == Role.CLIENTE and t.customer_id != user.id):
        raise NotFound(f'Chamado {ticket_id} não encontrado')
    return t


@dataclass(frozen=True)
class TicketPage:
    items: list[Ticket]
    total: int
    open_at_risk: int     # open tickets matching the scope filters, for the queue shortcuts
    open_overdue: int


def list_tickets(db: Session, user: User, now: datetime, *, status: Status | None = None, open_only: bool = False,
                 category_id: int | None = None, assignee_id: int | None = None, unassigned: bool = False,
                 sla_state: sla.SlaState | None = None, q: str | None = None, limit: int = 50, offset: int = 0) -> TicketPage:
    """Filtering, ordering, counting and paging all happen in the database."""
    scope = []
    if user.role == Role.CLIENTE:
        scope.append(Ticket.customer_id == user.id)
    if category_id:
        scope.append(Ticket.category_id == category_id)
    if assignee_id:
        scope.append(Ticket.assignee_id == assignee_id)
    if unassigned:
        scope.append(Ticket.assignee_id.is_(None))
    if q:
        like = f'%{q.strip()}%'
        scope.append(or_(Ticket.title.ilike(like), Ticket.description.ilike(like)))

    filters = list(scope)
    if status:
        filters.append(Ticket.status == status)
    elif open_only:
        filters.append(Ticket.status.in_(OPEN_STATUSES))
    if sla_state:
        filters.append(sla_condition(sla_state, now))

    def count(*where) -> int:
        return db.scalar(select(func.count(Ticket.id)).where(*where)) or 0

    is_open = Ticket.status.in_(OPEN_STATUSES)
    # Work queue order: open first, then nearest deadline, then priority (id breaks ties so pages are stable).
    order = (case((is_open, 0), else_=1), Ticket.resolution_due_at,
             case(*((Ticket.priority == p, rank) for p, rank in PRIORITY_ORDER.items())), Ticket.id)
    items = list(db.scalars(select(Ticket).where(*filters).order_by(*order).limit(limit).offset(offset)).unique())
    return TicketPage(items=items, total=count(*filters),
                      open_at_risk=count(*scope, is_open, sla_condition(sla.SlaState.EM_RISCO, now)),
                      open_overdue=count(*scope, is_open, sla_condition(sla.SlaState.VENCIDO, now)))


# --- commands -----------------------------------------------------------------
def create_ticket(db: Session, customer: User, *, title: str, description: str, category_id: int,
                  priority: Priority, now: datetime) -> Ticket:
    if customer.role != Role.CLIENTE:
        raise PermissionDenied('Somente clientes abrem chamados')
    category = db.get(Category, category_id)
    if category is None or not category.is_active:
        raise NotFound(f'Categoria {category_id} não encontrada')
    due = sla.deadlines(now, category.first_response_hours, category.resolution_hours, settings.sla_risk_fraction)
    t = Ticket(title=title, description=description, category=category, priority=priority, customer_id=customer.id,
               status=Status.ABERTO, created_at=now,
               first_response_due_at=due.first_response, first_response_risk_at=due.first_response_risk,
               resolution_due_at=due.resolution, resolution_risk_at=due.resolution_risk)
    db.add(t)
    _event(db, t, customer, EventType.CRIADO, now, to=Status.ABERTO)
    db.commit()
    return t


def add_message(db: Session, user: User, t: Ticket, *, body: str, internal: bool, now: datetime) -> Ticket:
    _require_open(t)
    if internal and user.role not in STAFF_ROLES:
        raise PermissionDenied('Notas internas são exclusivas da equipe')
    _post(db, t, user, body, now, internal)
    if user.role == Role.CLIENTE and t.status == Status.AGUARDANDO_CLIENTE:
        _set_status(db, t, user, Action.RESPOSTA_CLIENTE, now)
    elif user.role in STAFF_ROLES and not internal and t.status == Status.ABERTO:
        _set_status(db, t, user, Action.INICIAR, now)
    db.commit()
    return t


def apply_action(db: Session, user: User, t: Ticket, *, action: Action, message: str | None, now: datetime) -> Ticket:
    """Staff status actions that are not covered by a dedicated endpoint."""
    if action not in (Action.INICIAR, Action.PEDIR_INFO):
        raise DomainError(f'Use o endpoint específico para "{action}"')
    if action == Action.PEDIR_INFO and not message:
        raise DomainError('Informe ao cliente o que é necessário')
    _set_status(db, t, user, action, now)
    if action == Action.INICIAR and t.assignee_id is None and user.role == Role.ATENDENTE:
        _assign(db, user, t, user, now)
    if message:
        _post(db, t, user, message, now)
    db.commit()
    return t


def propose_resolution(db: Session, user: User, t: Ticket, *, message: str, now: datetime) -> Ticket:
    _set_status(db, t, user, Action.PROPOR_SOLUCAO, now)
    _post(db, t, user, message, now)
    t.resolved_at = now
    db.commit()
    return t


def confirm_resolution(db: Session, user: User, t: Ticket, *, satisfaction: int | None, comment: str | None, now: datetime) -> Ticket:
    _set_status(db, t, user, Action.CONFIRMAR, now)
    t.closed_at = now
    if satisfaction is not None:
        t.satisfaction, t.satisfaction_comment = satisfaction, comment
        _event(db, t, user, EventType.AVALIADO, now, to=str(satisfaction))
    db.commit()
    return t


def reject_resolution(db: Session, user: User, t: Ticket, *, message: str, now: datetime) -> Ticket:
    _set_status(db, t, user, Action.REJEITAR, now)
    _post(db, t, user, message, now)
    t.reopen_count += 1
    t.resolved_at = None
    db.commit()
    return t


def _assign(db: Session, actor: User, t: Ticket, assignee: User, now: datetime) -> None:
    previous = t.assignee
    if previous is not None and previous.id != assignee.id:
        t.transfer_count += 1
    _event(db, t, actor, EventType.ATRIBUIDO, now, previous.name if previous else None, assignee.name)
    t.assignee_id = assignee.id
    t.assignee = assignee


def assign(db: Session, actor: User, t: Ticket, *, assignee_id: int, now: datetime) -> Ticket:
    _require_open(t)
    assignee = db.get(User, assignee_id)
    if assignee is None or not assignee.is_active or assignee.role not in STAFF_ROLES:
        raise NotFound('Responsável deve ser um atendente ou gestor ativo')
    if actor.role == Role.ATENDENTE and (assignee.id != actor.id or t.assignee_id not in (None, actor.id)):
        raise PermissionDenied('Atendentes só podem assumir chamados sem responsável; transferências são do gestor')
    if t.assignee_id == assignee.id:
        return t
    _assign(db, actor, t, assignee, now)
    db.commit()
    return t
