from datetime import datetime

from fastapi import APIRouter

from ..deps import DB, Manager, Now
from ..schemas import MetricsOut
from ..services import metrics

router = APIRouter(prefix='/metrics', tags=['metrics'])


@router.get('/overview', response_model=MetricsOut)
def overview(db: DB, _: Manager, now: Now, start: datetime | None = None, end: datetime | None = None,
             category_id: int | None = None):
    """Indicators for the pilot: SLA compliance, confirmed resolution, reopenings and feedback coverage."""
    return metrics.overview(db, now, start=start, end=end, category_id=category_id)
