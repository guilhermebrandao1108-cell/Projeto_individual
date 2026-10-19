"""pontos de risco do SLA

Stores, for each SLA target, the instant it becomes "em risco", so the queue can
filter and count SLA states in SQL. Existing tickets are backfilled with the same
rule the application uses (domain.sla.risk_point), in three steps: add the columns
as nullable, compute them, then make them NOT NULL.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-18 21:42:12.524708

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.timeutils
from app.config import settings
from app.domain.sla import risk_point


# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

tickets = sa.table(
    'tickets',
    sa.column('id', sa.Integer),
    sa.column('created_at', app.timeutils.UTCDateTime),
    sa.column('first_response_due_at', app.timeutils.UTCDateTime),
    sa.column('resolution_due_at', app.timeutils.UTCDateTime),
    sa.column('first_response_risk_at', app.timeutils.UTCDateTime),
    sa.column('resolution_risk_at', app.timeutils.UTCDateTime),
)


def upgrade() -> None:
    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('first_response_risk_at', app.timeutils.UTCDateTime(), nullable=True))
        batch_op.add_column(sa.Column('resolution_risk_at', app.timeutils.UTCDateTime(), nullable=True))

    conn = op.get_bind()
    fraction = settings.sla_risk_fraction
    rows = conn.execute(sa.select(tickets.c.id, tickets.c.created_at, tickets.c.first_response_due_at,
                                  tickets.c.resolution_due_at)).all()
    for id_, created, first_due, resolution_due in rows:
        conn.execute(tickets.update().where(tickets.c.id == id_).values(
            first_response_risk_at=risk_point(created, first_due, fraction),
            resolution_risk_at=risk_point(created, resolution_due, fraction)))

    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.alter_column('first_response_risk_at', existing_type=app.timeutils.UTCDateTime(), nullable=False)
        batch_op.alter_column('resolution_risk_at', existing_type=app.timeutils.UTCDateTime(), nullable=False)
        batch_op.create_index(batch_op.f('ix_tickets_first_response_due_at'), ['first_response_due_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_tickets_resolution_due_at'), ['resolution_due_at'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tickets_resolution_due_at'))
        batch_op.drop_index(batch_op.f('ix_tickets_first_response_due_at'))
        batch_op.drop_column('resolution_risk_at')
        batch_op.drop_column('first_response_risk_at')
