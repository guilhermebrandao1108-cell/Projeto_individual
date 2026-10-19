"""Programmatic Alembic helpers (used by app.seed and tests). CLI equivalent: `alembic upgrade head`."""
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection

INI = Path(__file__).resolve().parents[1] / 'alembic.ini'


def alembic_config(connection: Connection | None = None) -> Config:
    config = Config(str(INI))
    config.attributes['configure_logger'] = False
    if connection is not None:
        config.attributes['connection'] = connection
    return config


def upgrade(connection: Connection | None = None, revision: str = 'head') -> None:
    command.upgrade(alembic_config(connection), revision)


def downgrade(connection: Connection | None = None, revision: str = 'base') -> None:
    command.downgrade(alembic_config(connection), revision)
