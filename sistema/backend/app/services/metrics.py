"""Operational indicators. They are the metrics the case study proposes to validate in a pilot:
deadlines met, confirmed resolution (not just a reply), reopenings and feedback coverage.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.sla import SlaState
from ..models import Status, Ticket
from .tickets import OPEN_STATUSES, sla_view

DECIDED = {SlaState.CUMPRIDO, SlaState.VIOLADO, SlaState.VENCIDO}


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _p90(values: list[float]) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=10, method='inclusive')[8]


def _summary(tickets: list[Ticket], now: datetime) -> dict:
    views = [sla_view(t, now) for t in tickets]
    first = [v.first_response for v in views if v.first_response in DECIDED]
    resolution = [v.resolution for v in views if v.resolution in DECIDED]
    proposed = [t for t in tickets if t.status in (Status.RESOLVIDO, Status.FECHADO) or t.reopen_count > 0]
    closed = [t for t in tickets if t.status == Status.FECHADO]
    rated = [t.satisfaction for t in closed if t.satisfaction is not None]
    open_views = [v for t, v in zip(tickets, views) if t.status in OPEN_STATUSES]
    return {
        'tickets': len(tickets),
        'open_tickets': len(open_views),
        'open_at_risk': sum(SlaState.EM_RISCO in (v.first_response, v.resolution) for v in open_views),
        'open_overdue': sum(SlaState.VENCIDO in (v.first_response, v.resolution) for v in open_views),
        # Overdue pending targets count as failures, otherwise ignoring late tickets would inflate the rate.
        'first_response_within_sla': _rate(first.count(SlaState.CUMPRIDO), len(first)),
        'first_response_p90_hours': _p90([(t.first_response_at - t.created_at).total_seconds() / 3600
                                          for t in tickets if t.first_response_at]),
        'resolution_within_sla': _rate(resolution.count(SlaState.CUMPRIDO), len(resolution)),
        'confirmed_resolution_rate': _rate(len(closed), len(proposed)),
        'reopen_rate': _rate(sum(t.reopen_count > 0 for t in proposed), len(proposed)),
        'satisfaction_coverage': _rate(len(rated), len(closed)),
        'satisfaction_avg': statistics.fmean(rated) if rated else None,
    }


def overview(db: Session, now: datetime, *, start: datetime | None = None, end: datetime | None = None,
             category_id: int | None = None) -> dict:
    stmt = select(Ticket)
    if start:
        stmt = stmt.where(Ticket.created_at >= start)
    if end:
        stmt = stmt.where(Ticket.created_at < end)
    if category_id:
        stmt = stmt.where(Ticket.category_id == category_id)
    tickets = list(db.scalars(stmt).unique())
    by_category: dict[str, list[Ticket]] = defaultdict(list)
    for t in tickets:
        by_category[t.category.name].append(t)
    return {**_summary(tickets, now),
            'by_category': [{'category': name, **_summary(group, now)} for name, group in sorted(by_category.items())]}
