"""Volcengine TOS via its S3-compatible endpoint (tos-s3-<region>.volces.com)."""

from __future__ import annotations

from app.adapters.object_storage.base import S3CompatibleStorage


class VolcengineTOSStorage(S3CompatibleStorage):
    addressing_style = "virtual"

    def endpoint_url(self) -> str | None:
        if self.settings.OBJECT_STORAGE_ENDPOINT:
            return self.settings.OBJECT_STORAGE_ENDPOINT
        region = self.settings.OBJECT_STORAGE_REGION or "cn-beijing"
        scheme = "https" if self.settings.OBJECT_STORAGE_SECURE else "http"
        return f"{scheme}://tos-s3-{region}.volces.com"
