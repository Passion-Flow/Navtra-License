"""Top-level exception handlers — render the unified error envelope (error-codes.md).

No stack traces in responses; 500 is always redacted to SYSTEM_INTERNAL_ERROR.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.errors import BizError
from app.core.logging import get_logger

log = get_logger("forge.error")


def _lang(request: Request) -> str:
    # URL path style /<lang>/...; default zh-CN.
    parts = request.url.path.strip("/").split("/")
    return parts[0] if parts and parts[0] in ("zh-CN", "zh", "en") else "zh-CN"


def _rid(request: Request) -> str:
    return getattr(request.state, "request_id", "req_unknown")


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(BizError)
    async def _biz(request: Request, exc: BizError):
        env = exc.envelope(_rid(request), _lang(request))
        getattr(log, exc.log_level, log.warning)("biz_error", code=exc.code, **exc.details)
        return JSONResponse(status_code=exc.http_status, content=env)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        err = BizError("VALIDATION_FAILED", {"fields": exc.errors()})
        return JSONResponse(status_code=400, content=err.envelope(_rid(request), _lang(request)))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.error("unhandled_exception", error=type(exc).__name__)
        err = BizError("SYSTEM_INTERNAL_ERROR")
        return JSONResponse(status_code=500, content=err.envelope(_rid(request), _lang(request)))
