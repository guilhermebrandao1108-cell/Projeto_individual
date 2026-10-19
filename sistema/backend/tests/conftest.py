import os
import warnings
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

warnings.filterwarnings('ignore', message='SECRET_KEY not set')

from app.database import Base, get_db  # noqa: E402
from app.deps import get_now  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Category, Role, User  # noqa: E402
from app.ratelimit import login_throttle  # noqa: E402
from app.security import create_access_token, hash_password  # noqa: E402

T0 = datetime(2026, 3, 2, 9, 0, tzinfo=timezone.utc)
# Unset: fast in-memory SQLite. Set (e.g. postgresql+psycopg://...): every test runs on that server, from an empty schema.
TEST_DATABASE_URL = os.getenv('TEST_DATABASE_URL')


class Clock:
    """Controllable 'now' for SLA tests."""
    def __init__(self, start: datetime):
        self.now = start

    def advance(self, **delta) -> None:
        self.now += timedelta(**delta)


@pytest.fixture
def clock() -> Clock:
    return Clock(T0)


def reset_schema(engine) -> None:
    """Empty database (no tables, no alembic_version) on the external server."""
    with engine.begin() as conn:
        conn.execute(text('DROP SCHEMA public CASCADE'))
        conn.execute(text('CREATE SCHEMA public'))


@pytest.fixture
def empty_engine(tmp_path):
    """An empty database for migration tests: a SQLite file, or the external server reset."""
    if TEST_DATABASE_URL:
        engine = create_engine(TEST_DATABASE_URL)
        reset_schema(engine)
    else:
        engine = create_engine(f"sqlite:///{tmp_path / 'm.db'}")
    yield engine
    engine.dispose()


@pytest.fixture
def db():
    if TEST_DATABASE_URL:
        engine = create_engine(TEST_DATABASE_URL)
        reset_schema(engine)
    else:
        engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Session() as session:
        yield session
    engine.dispose()


@pytest.fixture
def client(db, clock):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_now] = lambda: clock.now
    login_throttle.reset()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def users(db) -> dict[str, User]:
    people = {
        'cliente': User(name='Ana Cliente', email='ana@ex.com', role=Role.CLIENTE),
        'outro_cliente': User(name='Bruno Cliente', email='bruno@ex.com', role=Role.CLIENTE),
        'atendente': User(name='Carla Atendente', email='carla@ex.com', role=Role.ATENDENTE),
        'atendente2': User(name='Davi Atendente', email='davi@ex.com', role=Role.ATENDENTE),
        'gestor': User(name='Eva Gestora', email='eva@ex.com', role=Role.GESTOR),
    }
    for user in people.values():
        user.password_hash = hash_password('senha-segura')
        db.add(user)
    db.commit()
    return people


@pytest.fixture
def auth(users):
    """auth['cliente'] -> Authorization header for that user."""
    return {key: {'Authorization': f'Bearer {create_access_token(u.id)}'} for key, u in users.items()}


@pytest.fixture
def category(db) -> Category:
    c = Category(name='Cobrança', first_response_hours=4, resolution_hours=48)
    db.add(c)
    db.commit()
    return c


@pytest.fixture
def open_ticket(client, auth, category):
    def make(headers=None, **overrides) -> dict:
        payload = {'title': 'Cobrança em duplicidade', 'description': 'Fui cobrado duas vezes no cartão em março.',
                   'category_id': category.id, **overrides}
        r = client.post('/tickets', json=payload, headers=headers or auth['cliente'])
        assert r.status_code == 201, r.text
        return r.json()
    return make
