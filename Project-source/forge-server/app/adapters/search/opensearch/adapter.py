"""OpenSearch / ES-API-compatible adapter (opensearch-py AsyncOpenSearch).

Drives OpenSearch and every ES-API-compatible 信创 engine (Transwarp Scope, INFINI Easysearch,
Huawei CSS, Aliyun/Tencent ES). Exposes only the portable subset: ensure_index / index /
bulk_index / search / delete — so any ES-7.10-compatible backend is interchangeable.
"""

from __future__ import annotations

from typing import Any

from app.adapters.search.base import SearchAdapter


class OpenSearchAdapter(SearchAdapter):
    def __init__(self, settings) -> None:  # noqa: ANN001
        super().__init__(settings)
        self._client: Any = None

    def client(self) -> Any:
        if self._client is None:
            from opensearchpy import AsyncOpenSearch  # lazy import

            s = self.settings
            self._client = AsyncOpenSearch(
                hosts=[{"host": s.SEARCH_HOST, "port": s.SEARCH_PORT}],
                http_auth=(s.SEARCH_USERNAME, s.SEARCH_PASSWORD) if s.SEARCH_USERNAME else None,
                use_ssl=s.SEARCH_USE_SSL,
                verify_certs=s.SEARCH_VERIFY_CERTS,
                ssl_show_warn=False,
            )
        return self._client

    async def ensure_index(self, name, mappings=None):
        idx = self.index_name(name)
        c = self.client()
        if not await c.indices.exists(index=idx):
            body = {"mappings": mappings} if mappings else None
            await c.indices.create(index=idx, body=body)

    async def index(self, name, doc_id, body):
        await self.client().index(index=self.index_name(name), id=doc_id, body=body, refresh=True)

    async def bulk_index(self, name, docs):
        idx = self.index_name(name)
        actions: list[dict] = []
        for doc_id, body in docs:
            actions.append({"index": {"_index": idx, "_id": doc_id}})
            actions.append(body)
        if not actions:
            return 0
        await self.client().bulk(body=actions, refresh=True)
        return len(docs)

    async def search(self, name, query, size=20):
        r = await self.client().search(index=self.index_name(name), body={"query": query, "size": size})
        return [h["_source"] for h in r.get("hits", {}).get("hits", [])]

    async def delete(self, name, doc_id):
        await self.client().delete(index=self.index_name(name), id=doc_id, refresh=True, ignore=[404])

    async def health_check(self):
        try:
            return bool(await self.client().ping())
        except Exception:
            return False

    async def close(self):
        if self._client is not None:
            await self._client.close()
            self._client = None
