from fastapi import APIRouter, status

from ..deps import DB, CurrentUser, Now, Staff
from ..domain.sla import SlaState
from ..models import Status
from ..schemas import (ActionIn, AssignIn, ConfirmIn, MessageIn, RejectIn, ResolveIn, TicketCreate, TicketDetail,
                       TicketSummary)
from ..serializers import ticket_detail, ticket_summary
from ..services import tickets as svc

router = APIRouter(prefix='/tickets', tags=['tickets'])


@router.get('', response_model=list[TicketSummary])
def list_tickets(db: DB, user: CurrentUser, now: Now, status: Status | None = None, category_id: int | None = None,
                 assignee_id: int | None = None, unassigned: bool = False, sla: SlaState | None = None, q: str | None = None):
    """Customers see their own tickets; staff see the whole queue, ordered by nearest deadline."""
    found = svc.list_tickets(db, user, now, status=status, category_id=category_id, assignee_id=assignee_id,
                             unassigned=unassigned, sla_state=sla, q=q)
    return [ticket_summary(t, now) for t in found]


@router.post('', response_model=TicketDetail, status_code=status.HTTP_201_CREATED)
def create_ticket(data: TicketCreate, db: DB, user: CurrentUser, now: Now):
    t = svc.create_ticket(db, user, **data.model_dump(), now=now)
    return ticket_detail(t, user, now)


@router.get('/{ticket_id}', response_model=TicketDetail)
def get_ticket(ticket_id: int, db: DB, user: CurrentUser, now: Now):
    return ticket_detail(svc.get_ticket(db, user, ticket_id), user, now)


@router.post('/{ticket_id}/messages', response_model=TicketDetail)
def add_message(ticket_id: int, data: MessageIn, db: DB, user: CurrentUser, now: Now):
    t = svc.add_message(db, user, svc.get_ticket(db, user, ticket_id), body=data.body, internal=data.internal, now=now)
    return ticket_detail(t, user, now)


@router.post('/{ticket_id}/actions', response_model=TicketDetail)
def apply_action(ticket_id: int, data: ActionIn, db: DB, user: Staff, now: Now):
    t = svc.apply_action(db, user, svc.get_ticket(db, user, ticket_id), action=data.action, message=data.message, now=now)
    return ticket_detail(t, user, now)


@router.post('/{ticket_id}/resolve', response_model=TicketDetail)
def propose_resolution(ticket_id: int, data: ResolveIn, db: DB, user: Staff, now: Now):
    t = svc.propose_resolution(db, user, svc.get_ticket(db, user, ticket_id), message=data.message, now=now)
    return ticket_detail(t, user, now)


@router.post('/{ticket_id}/confirm', response_model=TicketDetail)
def confirm_resolution(ticket_id: int, data: ConfirmIn, db: DB, user: CurrentUser, now: Now):
    t = svc.confirm_resolution(db, user, svc.get_ticket(db, user, ticket_id), satisfaction=data.satisfaction,
                               comment=data.comment, now=now)
    return ticket_detail(t, user, now)


@router.post('/{ticket_id}/reject', response_model=TicketDetail)
def reject_resolution(ticket_id: int, data: RejectIn, db: DB, user: CurrentUser, now: Now):
    t = svc.reject_resolution(db, user, svc.get_ticket(db, user, ticket_id), message=data.message, now=now)
    return ticket_detail(t, user, now)


@router.post('/{ticket_id}/assign', response_model=TicketDetail)
def assign(ticket_id: int, data: AssignIn, db: DB, user: Staff, now: Now):
    t = svc.assign(db, user, svc.get_ticket(db, user, ticket_id), assignee_id=data.assignee_id, now=now)
    return ticket_detail(t, user, now)
