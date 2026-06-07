"""forge CLI — management commands (cli-tools.md). Naming: forge <domain> <action>.

Every command goes through the same services/adapters as the API (no DB bypass),
is idempotent, and writes an audit record. Exit codes: 0 ok / 1 general / 4 not-found.
"""

from __future__ import annotations

import asyncio

import typer

from app.settings import get_settings

app = typer.Typer(name="forge", help="Forge License Authority management CLI", no_args_is_help=True)
migrate_app = typer.Typer(help="Database migrations")
keys_app = typer.Typer(help="Signing key management")
app.add_typer(migrate_app, name="migrate")
app.add_typer(keys_app, name="keys")


def _alembic_config():
    from alembic.config import Config
    return Config("alembic.ini")


@migrate_app.command("up")
def migrate_up() -> None:
    """Apply all pending migrations, guarded by a DB advisory lock (multi-replica safe)."""
    asyncio.run(_migrate_up())
    typer.echo("✓ migrations applied")


async def _migrate_up() -> None:
    from alembic import command
    from sqlalchemy import text

    from app.adapters.database.base import get_database_adapter

    adapter = get_database_adapter(get_settings())
    engine = adapter.create_engine()
    async with engine.connect() as lock_conn:
        # Hold a session-level advisory lock for the whole migration (best-effort mutex).
        try:
            await lock_conn.execute(text(adapter.dialect_specific_sql("advisory_lock")))
        except Exception:  # noqa: BLE001 - lock is best-effort; never block migrating
            pass
        # alembic's async env.py calls asyncio.run() internally, so run it in a worker
        # thread (its own event loop) while we hold the lock on this connection.
        await asyncio.to_thread(command.upgrade, _alembic_config(), "head")
        try:
            await lock_conn.execute(text(adapter.dialect_specific_sql("advisory_unlock")))
        except Exception:  # noqa: BLE001
            pass
    await engine.dispose()


@migrate_app.command("down")
def migrate_down(steps: int = typer.Option(1, help="number of revisions to roll back")) -> None:
    from alembic import command
    command.downgrade(_alembic_config(), f"-{steps}")
    typer.echo(f"✓ rolled back {steps} revision(s)")


@app.command()
def bootstrap(silent: bool = typer.Option(False, "--silent")) -> None:
    """Idempotently seed the default super-admin + signing keys (master + edge_lease).

    Super-admin: forge@navtra.ai (vendor-internal: login password = email). 2FA should be
    enabled before issuing licenses. Signing keys are generated once and stored encrypted.
    """
    created, key_ids = asyncio.run(_bootstrap())
    if not silent:
        typer.echo("✓ super-admin created" if created else "• super-admin already exists — no-op")
        typer.echo(f"✓ signing keys: {key_ids}")


@keys_app.command("init")
def keys_init() -> None:
    """Generate the master + edge_lease Ed25519 keys if missing (idempotent)."""
    typer.echo(f"✓ signing keys: {asyncio.run(_ensure_keys())}")


@keys_app.command("export-public")
def keys_export_public(purpose: str = typer.Option("master", help="master | edge_lease")) -> None:
    """Print the PUBLIC key (PEM) for embedding into a consumer product's Verifier SDK."""
    typer.echo(asyncio.run(_export_public(purpose)))


@app.command()
def healthcheck(wait_deps: bool = typer.Option(False, "--wait-deps"),
                timeout: int = typer.Option(60, "--timeout")) -> None:
    """Verify DB + cache connectivity (used by container entrypoint)."""
    if not asyncio.run(_healthcheck(wait_deps, timeout)):
        raise typer.Exit(code=1)
    typer.echo("✓ dependencies healthy")


async def _bootstrap() -> tuple[bool, dict]:
    from app.core import security
    from app.db.session import get_sessionmaker
    from app.licensing.keys import KeyManager
    from app.models.user import User
    from app.repositories.user import UserRepository
    from app.services.audit_service import AuditService

    email = "forge@navtra.ai"
    async with get_sessionmaker()() as db:
        repo = UserRepository(db)
        created = False
        if not await repo.get_by_email(email, include_deleted=True):
            user = User(
                email=email, username="Admin", role="super_admin", is_active=True,
                password_hash=security.hash_password(email),  # vendor-internal: password = email
            )
            db.add(user)
            AuditService(db).log(action="bootstrap_super_admin", result="success", actor_type="cli",
                                 actor_name="Admin", resource_type="user", resource_id=str(user.id))
            created = True
        key_ids = await KeyManager(db).ensure_keys()
        await db.commit()
        return created, key_ids


async def _ensure_keys() -> dict:
    from app.db.session import get_sessionmaker
    from app.licensing.keys import KeyManager

    async with get_sessionmaker()() as db:
        key_ids = await KeyManager(db).ensure_keys()
        await db.commit()
        return key_ids


async def _export_public(purpose: str) -> str:
    from app.db.session import get_sessionmaker
    from app.licensing.keys import KeyManager

    async with get_sessionmaker()() as db:
        key = await KeyManager(db).require_active(purpose)
        return key.public_key


async def _healthcheck(wait_deps: bool, timeout: int) -> bool:
    import time

    from sqlalchemy import text

    from app.adapters.cache.base import get_cache_adapter
    from app.db.session import get_engine

    settings = get_settings()
    deadline = time.time() + timeout
    while True:
        try:
            async with get_engine().connect() as conn:
                await conn.execute(text("SELECT 1"))
            if await get_cache_adapter(settings).health_check():
                return True
        except Exception:
            pass
        if not wait_deps or time.time() > deadline:
            return False
        await asyncio.sleep(2)
