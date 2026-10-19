"""ORM → API models, adding the computed fields (SLA state, allowed actions, visibility)."""
from dataclasses import asdict
from datetime import datetime

from .domain.workflow import allowed_actions
from .models import EventType, Role, Ticket, User
from .schemas import TicketDetail, TicketSummary
from .services.tickets import sla_view


def _fields(t: Ticket, model) -> dict:
    return {name: getattr(t, name) for name in model.model_fields if hasattr(t, name)}


def ticket_summary(t: Ticket, now: datetime) -> TicketSummary:
    return TicketSummary.model_validate({**_fields(t, TicketSummary), 'sla': asdict(sla_view(t, now))}, from_attributes=True)


def ticket_detail(t: Ticket, user: User, now: datetime) -> TicketDetail:
    is_customer = user.role == Role.CLIENTE
    messages = [m for m in t.messages if not (is_customer and m.internal)]
    events = [e for e in t.events if not (is_customer and e.type == EventType.MENSAGEM and e.to_value == 'interna')]
    data = {**_fields(t, TicketDetail), 'sla': asdict(sla_view(t, now)), 'messages': messages, 'events': events,
            'allowed_actions': allowed_actions(t.status, user.role)}
    return TicketDetail.model_validate(data, from_attributes=True)
