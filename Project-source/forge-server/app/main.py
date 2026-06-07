"""FastAPI application factory. APP_ROLE selects the surface:
  api  -> /admin-api/v1 (signing core + admin backend, internal-only, holds private key)
  edge -> /edge/v1      (public validation relay, NO private key)  [built in Phase 2]
"""

from __future__ import annotations

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app import models  # noqa: F401 - register all ORM tables (FK resolution) for every role
from app.core.handlers import install_handlers
from app.core.logging import configure_logging
from app.middleware.context import RequestContextMiddleware
from app.permissions.roles import assert_registry_consistent
from app.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.APP_DEBUG)
    assert_registry_consistent()  # fail fast if RBAC roles reference unknown permissions

    # KEK fail-closed: a signing role must NOT boot in production without a valid KEK, or it would
    # serve traffic and only fail at first sign/decrypt. api needs the master KEK; edge needs its own.
    if settings.APP_ROLE in ("api", "edge") and not settings.APP_DEBUG:
        from app.core import crypto
        crypto._load_kek(settings.FORGE_EDGE_KEK if settings.APP_ROLE == "edge"
                         and settings.FORGE_EDGE_KEK else settings.FORGE_FIELD_ENCRYPTION_KEY)

    app = FastAPI(
        title=f"Forge ({settings.APP_ROLE})",
        version="1.0.0",
        docs_url="/docs" if settings.APP_DEBUG else None,
        # don't expose the signing core's full route map in production (info disclosure)
        openapi_url="/openapi.json" if settings.APP_DEBUG else None,
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.APP_BASE_URL],   # explicit whitelist, never "*"
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        max_age=600,
    )
    install_handlers(app)

    from app.api import health
    app.include_router(health.router)

    if settings.APP_ROLE == "api":
        from app.api.admin.v1 import (audit, auth, crl, customers, licenses, me, products,
                                      settings, users)
        for r in (auth.router, me.router, products.router, customers.router, licenses.router,
                  crl.router, audit.router, settings.router, users.router):
            app.include_router(r, prefix="/admin-api/v1")
    elif settings.APP_ROLE == "edge":
        from app.api.edge.v1 import routes as edge_routes
        app.include_router(edge_routes.router)

    return app


app = create_app()
