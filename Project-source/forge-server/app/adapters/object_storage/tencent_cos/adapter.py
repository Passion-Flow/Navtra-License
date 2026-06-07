"""Tencent COS via its S3-compatible endpoint (cos.<region>.myqcloud.com).

Note: the COS bucket name is "<name>-<appid>" — set that full value as the bucket.
"""

from __future__ import annotations

from app.adapters.object_storage.base import S3CompatibleStorage


class TencentCOSStorage(S3CompatibleStorage):
    addressing_style = "virtual"

    def endpoint_url(self) -> str | None:
        if self.settings.OBJECT_STORAGE_ENDPOINT:
            return self.settings.OBJECT_STORAGE_ENDPOINT
        region = self.settings.OBJECT_STORAGE_REGION or "ap-guangzhou"
        scheme = "https" if self.settings.OBJECT_STORAGE_SECURE else "http"
        return f"{scheme}://cos.{region}.myqcloud.com"
