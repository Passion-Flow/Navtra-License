"""Search adapter interface — optional category (enable only if a project indexes data).

One `opensearch-py` client drives the OpenSearch default AND every ES-API-compatible 信创 engine
(Transwarp Scope / INFINI Easysearch / Huawei CSS / Aliyun·Tencent ES) — only the endpoint/auth
differ, so they all map to OpenSearchAdapter. opensearch-py is chosen over elasticsearch-py because
the latter hard-fails its product/version check against non-Elastic servers. (xinchuang.md §4)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.settings import AppSettings


class SearchAdapter(ABC):
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def index_name(self, name: str) -> str:
        return f"{self.settings.SEARCH_INDEX_PREFIX}-{name}"

    @abstractmethod
    async def ensure_index(self, name: str, mappings: dict | None = None) -> None: ...

    @abstractmethod
    async def index(self, name: str, doc_id: str, body: dict) -> None: ...

    @abstractmethod
    async def bulk_index(self, name: str, docs: list[tuple[str, dict]]) -> int: ...

    @abstractmethod
    async def search(self, name: str, query: dict, size: int = 20) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def delete(self, name: str, doc_id: str) -> None: ...

    @abstractmethod
    async def health_check(self) -> bool: ...

    async def close(self) -> None:  # pragma: no cover - optional
        ...


def get_search_adapter(settings: AppSettings) -> SearchAdapter:
    # All supported engines are ES-API-compatible → one opensearch-py adapter.
    from app.adapters.search.opensearch.adapter import OpenSearchAdapter

    return OpenSearchAdapter(settings)
