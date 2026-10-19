"""Team management rules."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain import DomainError
from ..models import EventType, Role, Ticket, TicketEvent, User
from . import NotFound
from .tickets import OPEN_STATUSES, STAFF_ROLES


def update_staff(db: Session, actor: User, user_id: int, *, is_active: bool | None, role: Role | None,
                 now: datetime) -> tuple[User, int]:
    """Change a team member's role or status. Returns the user and how many tickets went back to the queue."""
    user = db.get(User, user_id)
    if user is None or user.role not in STAFF_ROLES:
        raise NotFound('Membro da equipe não encontrado')
    if role is not None and role not in STAFF_ROLES:
        raise DomainError('A equipe só tem atendentes e gestores')
    if user.id == actor.id and (is_active is False or role == Role.ATENDENTE):
        raise DomainError('Você não pode desativar nem rebaixar a própria conta: peça a outro gestor')
    if role is not None:
        user.role = role
    released = 0
    if is_active is not None and is_active != user.is_active:
        user.is_active = is_active
        if not is_active:
            released = _release_tickets(db, actor, user, now)
    db.commit()
    return user, released


def _release_tickets(db: Session, actor: User, user: User, now: datetime) -> int:
    """Open tickets of a deactivated member return to the queue, so none are left without an owner."""
    tickets = db.scalars(select(Ticket).where(Ticket.assignee_id == user.id, Ticket.status.in_(OPEN_STATUSES))).unique().all()
    for t in tickets:
        db.add(TicketEvent(ticket=t, actor_id=actor.id, type=EventType.ATRIBUIDO, from_value=user.name, to_value=None, created_at=now))
        t.assignee_id = None
        t.assignee = None
    return len(tickets)
