"""SLA targets per queue: first response and resolution.

Requirement from the case study: replies after 7 days were associated with
+4.8 pp of unresolved complaints, so each target is tracked and flagged
*before* it is breached ("em risco"), not only after.

The resolution clock pauses while the ticket waits for the customer: time the
team cannot act on should not count against it. On resume, the deadline moves
forward by the paused time (see `resume`). A pause never hides a breach: if the
deadline had already passed when the pause began, the ticket stays overdue.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum


class SlaState(StrEnum):
    NO_PRAZO = 'no_prazo'        # pending, less than the risk fraction elapsed
    EM_RISCO = 'em_risco'        # pending, close to the deadline
    VENCIDO = 'vencido'          # pending, deadline passed
    CUMPRIDO = 'cumprido'        # met on time
    VIOLADO = 'violado'          # met, but late
    PAUSADO = 'pausado'          # pending, clock stopped while waiting for the customer


@dataclass(frozen=True)
class Deadlines:
    first_response: datetime
    resolution: datetime


def deadlines(created_at: datetime, first_response_hours: int, resolution_hours: int) -> Deadlines:
    if first_response_hours <= 0 or resolution_hours < first_response_hours:
        raise ValueError('SLA inválido: 0 < primeira resposta ≤ resolução')
    return Deadlines(created_at + timedelta(hours=first_response_hours),
                     created_at + timedelta(hours=resolution_hours))


def state(start: datetime, due: datetime, met_at: datetime | None, now: datetime, risk_fraction: float = .8,
          paused_at: datetime | None = None) -> SlaState:
    if met_at is not None:
        return SlaState.CUMPRIDO if met_at <= due else SlaState.VIOLADO
    if paused_at is not None and paused_at <= due:
        return SlaState.PAUSADO
    if now > due:
        return SlaState.VENCIDO
    elapsed = (now - start) / (due - start)
    return SlaState.EM_RISCO if elapsed >= risk_fraction else SlaState.NO_PRAZO


def resume(due: datetime, paused_at: datetime, now: datetime) -> tuple[datetime, timedelta]:
    """New deadline after a pause, and how long the pause lasted."""
    if now < paused_at:
        raise ValueError('O fim da pausa não pode ser anterior ao início')
    pause = now - paused_at
    return (due + pause if paused_at <= due else due), pause
