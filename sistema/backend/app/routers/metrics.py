from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import Response

from ..deps import DB, Manager, Now
from ..schemas import MetricsOut
from ..services import export, metrics

router = APIRouter(prefix='/metrics', tags=['metrics'])


@router.get('/overview', response_model=MetricsOut)
def overview(db: DB, _: Manager, now: Now, start: datetime | None = None, end: datetime | None = None,
             category_id: int | None = None):
    """Indicators for the pilot: SLA compliance, confirmed resolution, reopenings and feedback coverage."""
    return metrics.overview(db, now, start=start, end=end, category_id=category_id)


@router.get('/export.csv', response_class=Response, responses={200: {'content': {'text/csv': {}}}})
def export_csv(db: DB, _: Manager, now: Now, start: datetime | None = None, end: datetime | None = None):
    """One row per ticket, without personal data, for `python -m atendimento piloto` (analise/)."""
    body = export.tickets_csv(db, now, start=start, end=end)
    return Response(body, media_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="chamados_{now:%Y%m%d}.csv"'})
