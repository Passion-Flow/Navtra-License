"""Local object storage — dual mode (03-Services §2.3):
- filesystem: plain on-disk store under OBJECT_STORAGE_LOCAL_PATH/<bucket>/<key> (dev default);
- minio: delegate to the S3-compatible client against a local MinIO endpoint.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from app.adapters.object_storage.base import ObjectStat, ObjectStorageAdapter, S3CompatibleStorage
from app.settings import AppSettings


class LocalStorage(ObjectStorageAdapter):
    def __init__(self, settings: AppSettings) -> None:
        super().__init__(settings)
        self._minio: S3CompatibleStorage | None = None
        if settings.OBJECT_STORAGE_LOCAL_MODE == "minio":
            self._minio = S3CompatibleStorage(settings)  # endpoint = OBJECT_STORAGE_ENDPOINT

    def _root(self, bucket: str | None) -> Path:
        return Path(self.settings.OBJECT_STORAGE_LOCAL_PATH) / self._bucket(bucket)

    def _path(self, key: str, bucket: str | None) -> Path:
        return self._root(bucket) / key

    async def upload(self, key, data, *, bucket=None, content_type=None, public=False):
        if self._minio:
            return await self._minio.upload(key, data, bucket=bucket, content_type=content_type, public=public)

        def _do():
            p = self._path(key, bucket)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            return ObjectStat(key=key, size=len(data), content_type=content_type)
        return await asyncio.to_thread(_do)

    async def download(self, key, *, bucket=None):
        if self._minio:
            return await self._minio.download(key, bucket=bucket)
        return await asyncio.to_thread(lambda: self._path(key, bucket).read_bytes())

    async def delete(self, key, *, bucket=None):
        if self._minio:
            return await self._minio.delete(key, bucket=bucket)

        def _do():
            try:
                self._path(key, bucket).unlink()
            except FileNotFoundError:
                pass
        await asyncio.to_thread(_do)

    async def head(self, key, *, bucket=None):
        if self._minio:
            return await self._minio.head(key, bucket=bucket)

        def _do():
            p = self._path(key, bucket)
            if not p.exists():
                return None
            st = p.stat()
            return ObjectStat(key=key, size=st.st_size, last_modified=str(int(st.st_mtime)))
        return await asyncio.to_thread(_do)

    async def list(self, prefix="", *, bucket=None):
        if self._minio:
            return await self._minio.list(prefix, bucket=bucket)

        def _do():
            root = self._root(bucket)
            if not root.exists():
                return []
            out: list[ObjectStat] = []
            for dirpath, _dirs, files in os.walk(root):
                for f in files:
                    full = Path(dirpath) / f
                    rel = str(full.relative_to(root))
                    if rel.startswith(prefix):
                        out.append(ObjectStat(key=rel, size=full.stat().st_size))
            return out
        return await asyncio.to_thread(_do)

    async def presigned_upload_url(self, key, *, bucket=None, expires=None, content_type=None):
        if self._minio:
            return await self._minio.presigned_upload_url(key, bucket=bucket, expires=expires, content_type=content_type)
        # Filesystem has no presigning; the app serves these paths internally.
        return f"/internal/storage/{self._bucket(bucket)}/{key}"

    async def presigned_download_url(self, key, *, bucket=None, expires=None):
        if self._minio:
            return await self._minio.presigned_download_url(key, bucket=bucket, expires=expires)
        return f"/internal/storage/{self._bucket(bucket)}/{key}"
