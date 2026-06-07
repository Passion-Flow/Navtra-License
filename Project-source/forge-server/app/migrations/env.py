"""Alembic async env — engine assembled from field-ized settings via the DB adapter."""

from __future__ import annotations

import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import AsyncEngine

from app.adapters.database.base import get_database_adapter
from app.db.base import Base
from app.settings import get_settings

# Import all models so autogenerate / metadata sees them.
from app.models import (  # noqa: F401
    audit, binding, customer, license, product, revocation, signing_key, user,
)

target_metadata = Base.metadata


def _run_sync(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def _run_async() -> None:
    # Official async-alembic pattern: alembic owns the transaction inside _run_sync and
    # commits it. The migration mutex (advisory lock) is held by the CLI on a separate
    # connection (see app/cli migrate up), so it must NOT be done here or it would break
    # alembic's commit semantics.
    engine: AsyncEngine = get_database_adapter(get_settings()).create_engine()
    async with engine.connect() as connection:
        await connection.run_sync(_run_sync)
    await engine.dispose()


def run_migrations_offline() -> None:
    settings = get_settings()
    url = get_database_adapter(settings).dsn().render_as_string(hide_password=False)
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(_run_async())
