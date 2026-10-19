"""Database tables. Business rules live in app/domain and app/services, not here."""
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .timeutils import UTCDateTime, utcnow


class Role(StrEnum):
    CLIENTE = 'cliente'
    ATENDENTE = 'atendente'
    GESTOR = 'gestor'


class Status(StrEnum):
    ABERTO = 'aberto'
    EM_ATENDIMENTO = 'em_atendimento'
    AGUARDANDO_CLIENTE = 'aguardando_cliente'
    RESOLVIDO = 'resolvido'      # solution proposed by staff, awaiting customer confirmation
    FECHADO = 'fechado'          # solution confirmed by the customer


class Priority(StrEnum):
    BAIXA = 'baixa'
    MEDIA = 'media'
    ALTA = 'alta'
    URGENTE = 'urgente'


class EventType(StrEnum):
    CRIADO = 'criado'
    STATUS = 'status'
    ATRIBUIDO = 'atribuido'
    MENSAGEM = 'mensagem'
    AVALIADO = 'avaliado'


def _enum(cls):
    return Enum(cls, native_enum=False, values_callable=lambda e: [x.value for x in e], length=32)


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(_enum(Role))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Category(Base):
    """A queue ("fila") with its own SLA targets."""
    __tablename__ = 'categories'
    __table_args__ = (CheckConstraint('first_response_hours > 0 AND resolution_hours >= first_response_hours', name='sla_valido'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    first_response_hours: Mapped[int] = mapped_column(Integer)
    resolution_hours: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Ticket(Base):
    __tablename__ = 'tickets'
    __table_args__ = (CheckConstraint('satisfaction IS NULL OR satisfaction BETWEEN 1 AND 5', name='satisfacao_1_a_5'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[Status] = mapped_column(_enum(Status), default=Status.ABERTO, index=True)
    priority: Mapped[Priority] = mapped_column(_enum(Priority), default=Priority.MEDIA)
    category_id: Mapped[int] = mapped_column(ForeignKey('categories.id'))
    customer_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), index=True)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    first_response_due_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    first_response_risk_at: Mapped[datetime] = mapped_column(UTCDateTime)  # risk point, see domain/sla.py
    resolution_due_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    resolution_risk_at: Mapped[datetime] = mapped_column(UTCDateTime)
    first_response_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime)   # last solution proposal
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)     # customer confirmation
    sla_paused_at: Mapped[datetime | None] = mapped_column(UTCDateTime)  # set while AGUARDANDO_CLIENTE
    sla_paused_seconds: Mapped[int] = mapped_column(Integer, default=0, server_default='0')

    reopen_count: Mapped[int] = mapped_column(Integer, default=0)
    transfer_count: Mapped[int] = mapped_column(Integer, default=0)
    satisfaction: Mapped[int | None] = mapped_column(Integer)
    satisfaction_comment: Mapped[str | None] = mapped_column(Text)

    category: Mapped[Category] = relationship(lazy='joined')
    customer: Mapped[User] = relationship(foreign_keys=[customer_id], lazy='joined')
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id], lazy='joined')
    messages: Mapped[list['Message']] = relationship(back_populates='ticket', order_by='Message.id', cascade='all, delete-orphan')
    events: Mapped[list['TicketEvent']] = relationship(back_populates='ticket', order_by='TicketEvent.id', cascade='all, delete-orphan')


class Message(Base):
    """Interaction history. Internal notes are visible only to staff."""
    __tablename__ = 'messages'
    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey('tickets.id'), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    body: Mapped[str] = mapped_column(Text)
    internal: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)

    ticket: Mapped[Ticket] = relationship(back_populates='messages')
    author: Mapped[User] = relationship(lazy='joined')


class TicketEvent(Base):
    """Append-only audit trail of everything that happened to a ticket."""
    __tablename__ = 'ticket_events'
    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey('tickets.id'), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    type: Mapped[EventType] = mapped_column(_enum(EventType))
    from_value: Mapped[str | None] = mapped_column(String(64))
    to_value: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)

    ticket: Mapped[Ticket] = relationship(back_populates='events')
    actor: Mapped[User] = relationship(lazy='joined')
