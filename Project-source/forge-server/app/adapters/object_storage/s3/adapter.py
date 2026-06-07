"""AWS S3 (also serves any generic S3-compatible endpoint set via OBJECT_STORAGE_ENDPOINT)."""

from __future__ import annotations

from app.adapters.object_storage.base import S3CompatibleStorage


class S3Storage(S3CompatibleStorage):
    addressing_style = "virtual"
