"""Structured logging — structlog JSON to stdout (HARD RULE: observability.md).

Secrets/PII are masked before they ever reach a log record (security.md §10).
Private key material and verification internals NEVER enter logs (licensing.md).
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

_SENSITIVE_KEYS = {
    "password", "password_hash", "secret", "private_key", "private_key_ciphertext",
    "dek_wrapped", "token", "validation_token", "twofa_secret", "backup_codes",
    "authorization", "cookie", "set-cookie", "kek", "field_encryption_key",
}


def _mask(value: str) -> str:
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}****{value[-4:]}"


def _redact(_logger: Any, _name: str, event_dict: dict) -> dict:
    for key in list(event_dict.keys()):
        if key.lower() in _SENSITIVE_KEYS and isinstance(event_dict[key], str):
            event_dict[key] = _mask(event_dict[key])
    return event_dict


def configure_logging(debug: bool = False) -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.DEBUG if debug else logging.INFO)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG if debug else logging.INFO),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "forge") -> Any:
    return structlog.get_logger(name)
