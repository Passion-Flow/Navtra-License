"""Unified error model — BizError + {code, message, details, request_id} envelope.

HARD RULE (error-codes.md): business code raises ONLY BizError(code); a top-level
handler renders the envelope. No bare strings, no stack traces in responses.
"""

from __future__ import annotations

import functools
import os
import pathlib
from typing import Any

import yaml


def _resolve_dict_path() -> pathlib.Path:
    """Locate error-codes.yaml without hardcoding one repo/deploy layout.

    Order: explicit env override, then candidate locations covering the source tree
    (Project-source/forge-shared/), a container mount (/forge-shared/), and a copy
    packaged next to the app. The error dictionary is a required runtime asset.
    """
    if env := os.environ.get("FORGE_ERROR_CODES_PATH"):
        return pathlib.Path(env)
    here = pathlib.Path(__file__).resolve()
    candidates = [
        here.parents[3] / "forge-shared" / "error-codes.yaml",  # Project-source/forge-shared
        pathlib.Path("/forge-shared/error-codes.yaml"),          # container mount
        here.parents[2] / "forge-shared" / "error-codes.yaml",   # packaged alongside app/
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(
        "error-codes.yaml not found; set FORGE_ERROR_CODES_PATH or mount forge-shared"
    )


@functools.lru_cache
def _dictionary() -> dict[str, dict]:
    with _resolve_dict_path().open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not data:
        raise RuntimeError("error-codes.yaml is empty — dictionary is the single source of truth")
    return data


class BizError(Exception):
    """The only exception business code is allowed to raise for user-facing errors."""

    def __init__(self, code: str, details: dict[str, Any] | None = None) -> None:
        if code not in _dictionary():
            # Fail loud at dev/startup if a code is not registered in the dictionary.
            raise KeyError(f"error code '{code}' not in error-codes.yaml")
        self.code = code
        self.details = details or {}
        super().__init__(code)

    @property
    def http_status(self) -> int:
        return int(_dictionary()[self.code]["http"])

    @property
    def log_level(self) -> str:
        return str(_dictionary()[self.code].get("log_level", "warning"))

    def message(self, lang: str = "zh-CN") -> str:
        msgs = _dictionary()[self.code]["message"]
        return msgs.get(lang) or msgs.get("zh-CN") or self.code

    def envelope(self, request_id: str, lang: str = "zh-CN") -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message(lang),
            "details": self.details,
            "request_id": request_id,
        }


def all_codes() -> set[str]:
    return set(_dictionary().keys())
