"""SLA targets per queue: first response and resolution.

Requirement from the case study: replies after 7 days were associated with
+4.8 pp of unresolved complaints, so each target is tracked and flagged
*before* it is breached ("em risco"), not only after.

Each target is described by instants fixed when they are set: the deadline and
the *risk point* (start + fraction × window). Storing the risk point makes every
state a plain datetime comparison, so the same rule runs in Python (`state`) and
in SQL (services.tickets.sla_condition), and can use indexes.

The resolution clock pauses while the ticket waits for the customer: time the
team cannot act on should not count against it. On resume, the deadline moves
forward by the paused time (see `resume`). A pause never hides a breach: if the
deadline had already passed when the pause began, the ticket stays overdue.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum


class SlaState(StrEnum):
    NO_PRAZO = 'no_prazo'        # pending, before the risk point
    EM_RISCO = 'em_risco'        # pending, between the risk point and the deadline
    VENCIDO = 'vencido'          # pending, deadline passed
    CUMPRIDO = 'cumprido'        # met on time
    VIOLADO = 'violado'          # met, but late
    PAUSADO = 'pausado'          # pending, clock stopped while waiting for the customer


@dataclass(frozen=True)
class Deadlines:
    first_response: datetime
    first_response_risk: datetime
    resolution: datetime
    resolution_risk: datetime


def risk_point(start: datetime, due: datetime, fraction: float) -> datetime:
    if not 0 < fraction <= 1:
        raise ValueError('A fração de risco deve estar entre 0 e 1')
    return start + (due - start) * fraction


def deadlines(created_at: datetime, first_response_hours: int, resolution_hours: int, risk_fraction: float = .8) -> Deadlines:
    if first_response_hours <= 0 or resolution_hours < first_response_hours:
        raise ValueError('SLA inválido: 0 < primeira resposta ≤ resolução')
    first = created_at + timedelta(hours=first_response_hours)
    resolution = created_at + timedelta(hours=resolution_hours)
    return Deadlines(first, risk_point(created_at, first, risk_fraction),
                     resolution, risk_point(created_at, resolution, risk_fraction))


def state(due: datetime, risk_at: datetime, met_at: datetime | None, now: datetime,
          paused_at: datetime | None = None) -> SlaState:
    if met_at is not None:
        return SlaState.CUMPRIDO if met_at <= due else SlaState.VIOLADO
    if paused_at is not None and paused_at <= due:
        return SlaState.PAUSADO
    if now > due:
        return SlaState.VENCIDO
    return SlaState.EM_RISCO if now >= risk_at else SlaState.NO_PRAZO


def resume(due: datetime, paused_at: datetime, now: datetime) -> tuple[datetime, timedelta]:
    """New deadline after a pause, and how long the pause lasted."""
    if now < paused_at:
        raise ValueError('O fim da pausa não pode ser anterior ao início')
    pause = now - paused_at
    return (due + pause if paused_at <= due else due), pause
