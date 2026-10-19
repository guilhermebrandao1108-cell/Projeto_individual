from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .domain import DomainError, PermissionDenied
from .ratelimit import TooManyAttempts
from .routers import auth, categories, metrics, tickets, users
from .services import NotFound


# The schema is managed by Alembic migrations (`alembic upgrade head`), never created implicitly here.
app = FastAPI(title='Chamados API', version='0.2.0',
              description='Gestão de chamados com SLA por fila, confirmação de solução pelo cliente e métricas. '
                          'Requisitos derivados do estudo de caso em analise/.')
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=['*'], allow_headers=['*'])

for router in (auth.router, users.router, categories.router, tickets.router, metrics.router):
    app.include_router(router)


def _error(code: int):
    async def handler(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=code, content={'detail': str(exc)})
    return handler


app.add_exception_handler(DomainError, _error(status.HTTP_409_CONFLICT))
app.add_exception_handler(PermissionDenied, _error(status.HTTP_403_FORBIDDEN))
app.add_exception_handler(NotFound, _error(status.HTTP_404_NOT_FOUND))


@app.exception_handler(TooManyAttempts)
async def too_many_attempts(_: Request, exc: TooManyAttempts) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_429_TOO_MANY_REQUESTS, content={'detail': str(exc)},
                        headers={'Retry-After': str(exc.retry_after_seconds)})


@app.get('/health', tags=['health'])
def health():
    return {'status': 'ok'}
