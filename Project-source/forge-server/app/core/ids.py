"""Identifier helpers — UUID v7 primary keys (HARD RULE: database.md §2)."""

from __future__ import annotations

import uuid

import uuid_utils


def uuid7() -> uuid.UUID:
    """Time-ordered UUID v7 for business primary keys."""
    return uuid.UUID(bytes=uuid_utils.uuid7().bytes)


def new_request_id() -> str:
    return f"req_{uuid_utils.uuid7().hex[:24]}"


def new_event_id() -> str:
    return f"evt_{uuid_utils.uuid7().hex}"
