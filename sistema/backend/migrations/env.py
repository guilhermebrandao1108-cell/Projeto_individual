"""Alembic environment: the database URL comes from app settings (DATABASE_URL)."""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool

from app import models  # noqa: F401  (registers every table on Base.metadata)
from app.config import settings
from app.database import Base, make_engine

config = context.config
if config.config_file_name is not None and config.attributes.get('configure_logger', True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _configure(**kwargs) -> None:
    # Batch mode lets ALTER-style migrations run on SQLite (it recreates the table under the hood).
    context.configure(target_metadata=target_metadata, render_as_batch=True, compare_type=True, **kwargs)


def run_migrations_offline() -> None:
    _configure(url=settings.database_url, literal_binds=True, dialect_opts={'paramstyle': 'named'})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Tests (and app.seed) may pass an open connection; otherwise connect with the app settings.
    connection = config.attributes.get('connection')
    if connection is not None:
        _configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = make_engine(settings.database_url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        _configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
