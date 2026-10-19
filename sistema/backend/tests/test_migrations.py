"""Migrations must build exactly the schema the models describe, in both directions."""
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from app import migrate
from app.database import Base


def _diff(conn):
    return compare_metadata(MigrationContext.configure(conn, opts={'compare_type': True}), Base.metadata)


def test_upgrade_matches_models_and_downgrade_is_clean(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'm.db'}")
    with engine.begin() as conn:
        migrate.upgrade(conn)
        assert _diff(conn) == []                      # no model change is missing a migration
        migrate.downgrade(conn, 'base')
        assert set(inspect(conn).get_table_names()) <= {'alembic_version'}
        migrate.upgrade(conn)                         # and it can be applied again
    engine.dispose()


def test_pause_migration_keeps_existing_tickets(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'm.db'}")
    with engine.begin() as conn:
        migrate.upgrade(conn, '0001')
        conn.execute(text("INSERT INTO users (id, name, email, password_hash, role, is_active, created_at) "
                          "VALUES (1, 'Ana', 'a@x.com', 'h', 'cliente', 1, '2026-01-01 00:00:00')"))
        conn.execute(text("INSERT INTO categories (id, name, first_response_hours, resolution_hours, is_active) VALUES (1, 'C', 1, 2, 1)"))
        conn.execute(text("INSERT INTO tickets (id, title, description, status, priority, category_id, customer_id, created_at, "
                          "first_response_due_at, resolution_due_at, reopen_count, transfer_count) VALUES (1, 'Título', 'Descrição', "
                          "'aberto', 'media', 1, 1, '2026-01-01 00:00:00', '2026-01-01 01:00:00', '2026-01-01 02:00:00', 0, 0)"))
        migrate.upgrade(conn, '0002')
        row = conn.execute(text('SELECT sla_paused_at, sla_paused_seconds FROM tickets WHERE id = 1')).one()
        assert tuple(row) == (None, 0)
    engine.dispose()
