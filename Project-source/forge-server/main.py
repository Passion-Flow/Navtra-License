"""Local dev entrypoint: `python main.py` (tech-stack.md). Prod uses uvicorn/gunicorn."""

from __future__ import annotations

import uvicorn

from app.settings import get_settings

if __name__ == "__main__":
    s = get_settings()
    uvicorn.run("app.main:app", host=s.APP_HOST, port=s.APP_PORT, reload=s.APP_DEBUG)
