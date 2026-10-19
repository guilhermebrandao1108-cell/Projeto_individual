"""Request/response models (Pydantic). Field names are the public API contract."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from .domain.sla import SlaState
from .domain.workflow import Action
from .models import EventType, Priority, Role, Status


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- users & auth -------------------------------------------------------------
class UserOut(ORM):
    id: int
    name: str
    email: str
    role: Role
    is_active: bool


class UserBrief(ORM):
    id: int
    name: str
    role: Role


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserCreate(RegisterIn):
    role: Role


class Token(BaseModel):
    access_token: str
    token_type: str = 'bearer'


# --- categories ---------------------------------------------------------------
class CategoryIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    first_response_hours: int = Field(gt=0, le=24 * 30)
    resolution_hours: int = Field(gt=0, le=24 * 90)

    @model_validator(mode='after')
    def resolution_after_first_response(self):
        if self.resolution_hours < self.first_response_hours:
            raise ValueError('resolution_hours deve ser ≥ first_response_hours')
        return self


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    first_response_hours: int | None = Field(default=None, gt=0, le=24 * 30)
    resolution_hours: int | None = Field(default=None, gt=0, le=24 * 90)
    is_active: bool | None = None


class CategoryOut(ORM):
    id: int
    name: str
    first_response_hours: int
    resolution_hours: int
    is_active: bool


# --- tickets ------------------------------------------------------------------
class TicketCreate(BaseModel):
    title: str = Field(min_length=5, max_length=200)
    description: str = Field(min_length=10, max_length=10_000)
    category_id: int
    priority: Priority = Priority.MEDIA


class SlaOut(BaseModel):
    first_response: SlaState
    first_response_due_at: datetime
    resolution: SlaState
    resolution_due_at: datetime


class TicketSummary(ORM):
    id: int
    title: str
    status: Status
    priority: Priority
    category: CategoryOut
    customer: UserBrief
    assignee: UserBrief | None
    created_at: datetime
    first_response_at: datetime | None
    resolved_at: datetime | None
    closed_at: datetime | None
    reopen_count: int
    transfer_count: int
    satisfaction: int | None
    sla_paused_seconds: int
    sla: SlaOut


class TicketPageOut(BaseModel):
    items: list[TicketSummary]
    total: int
    limit: int
    offset: int
    open_at_risk: int
    open_overdue: int


class MessageOut(ORM):
    id: int
    author: UserBrief
    body: str
    internal: bool
    created_at: datetime


class EventOut(ORM):
    id: int
    actor: UserBrief
    type: EventType
    from_value: str | None
    to_value: str | None
    created_at: datetime


class TicketDetail(TicketSummary):
    description: str
    satisfaction_comment: str | None
    messages: list[MessageOut]
    events: list[EventOut]
    allowed_actions: list[Action]


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=10_000)
    internal: bool = False


class ActionIn(BaseModel):
    """Staff status actions (iniciar, pedir_info). A message is required to ask the customer for info."""
    action: Action
    message: str | None = Field(default=None, max_length=10_000)


class ResolveIn(BaseModel):
    message: str = Field(min_length=5, max_length=10_000)


class ConfirmIn(BaseModel):
    satisfaction: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2_000)


class RejectIn(BaseModel):
    message: str = Field(min_length=5, max_length=10_000)


class AssignIn(BaseModel):
    assignee_id: int


# --- metrics ------------------------------------------------------------------
class MetricsOut(BaseModel):
    """Operational indicators chosen to validate the case study hypotheses in a pilot."""
    tickets: int
    open_tickets: int
    open_at_risk: int
    open_overdue: int
    first_response_within_sla: float | None
    first_response_p90_hours: float | None
    resolution_within_sla: float | None
    confirmed_resolution_rate: float | None
    reopen_rate: float | None
    satisfaction_coverage: float | None
    satisfaction_avg: float | None
    by_category: list[dict]
