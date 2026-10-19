"""Ticket export for statistical analysis of the pilot (see analise/atendimento/piloto.py).

One row per ticket with timings, SLA states and outcomes. No names, e-mails or message
text: only the fields an analysis needs. The customer is kept as an opaque id because
repeated customers are a dependency the analysis must be able to account for.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Ticket
from .tickets import sla_view

COLUMNS = ['chamado', 'fila', 'prioridade', 'status', 'criado_em', 'cliente', 'responsavel',
           'horas_ate_primeira_resposta', 'horas_ate_solucao_proposta', 'horas_pausado',
           'sla_primeira_resposta', 'sla_resolucao', 'reaberturas', 'transferencias', 'confirmado', 'avaliacao']


def _hours(start: datetime, end: datetime | None) -> str:
    return '' if end is None else f'{(end - start).total_seconds() / 3600:.2f}'


def tickets_csv(db: Session, now: datetime, *, start: datetime | None = None, end: datetime | None = None) -> str:
    stmt = select(Ticket).order_by(Ticket.id)
    if start:
        stmt = stmt.where(Ticket.created_at >= start)
    if end:
        stmt = stmt.where(Ticket.created_at < end)
    out = io.StringIO()
    writer = csv.writer(out, lineterminator='\n')
    writer.writerow(COLUMNS)
    for t in db.scalars(stmt).unique():
        view = sla_view(t, now)
        writer.writerow([
            t.id, t.category.name, t.priority.value, t.status.value, t.created_at.isoformat(), t.customer_id,
            t.assignee_id or '', _hours(t.created_at, t.first_response_at), _hours(t.created_at, t.resolved_at),
            f'{t.sla_paused_seconds / 3600:.2f}', view.first_response.value, view.resolution.value,
            t.reopen_count, t.transfer_count, int(t.closed_at is not None), t.satisfaction or '',
        ])
    return out.getvalue()
