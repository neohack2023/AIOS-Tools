"""Read-only Notion source adapter for Cartography Slice 3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .fixtures import adapt_notion_page_tree


class NotionReadClient(Protocol):
    """Minimal read contract. No create, update, archive, or delete methods exist."""

    def fetch_page(self, page_id: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class NotionReadResult:
    records: tuple[dict[str, Any], ...]
    nodes: tuple[dict[str, Any], ...]
    edges: tuple[dict[str, Any], ...]
    unresolved_references: tuple[dict[str, Any], ...]
    source_trace: tuple[dict[str, str], ...]


class NotionPageChainAdapter:
    """Read a page and its explicit ancestor chain into Graph IR.

    The adapter follows only source-declared parent IDs. It never infers hierarchy,
    never mutates source data, and fails closed on cycles or malformed records.
    """

    adapter_id = "notion.page_chain.read_only"
    adapter_version = "0.1.0"

    def __init__(self, client: NotionReadClient, *, max_depth: int = 32) -> None:
        if max_depth < 1:
            raise ValueError("max_depth must be positive")
        self._client = client
        self._max_depth = max_depth

    def read(self, page_id: str, scope_key: str) -> NotionReadResult:
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        current: str | None = page_id

        while current:
            if current in seen:
                raise ValueError(f"Notion ancestor cycle detected at {current}")
            if len(records) >= self._max_depth:
                raise ValueError("Notion ancestor chain exceeded max_depth")
            seen.add(current)

            raw = self._client.fetch_page(current)
            record = self._normalize(raw)
            if record["id"] != current:
                raise ValueError(f"Client returned page {record['id']} for requested {current}")
            records.append(record)
            current = record.get("parent_id")

        nodes, edges, unresolved = adapt_notion_page_tree(records, scope_key)
        trace = tuple(
            {
                "source_object_id": record["id"],
                "source_pointer": record["url"],
                "adapter_id": self.adapter_id,
                "adapter_version": self.adapter_version,
            }
            for record in sorted(records, key=lambda item: item["id"])
        )
        return NotionReadResult(
            records=tuple(records),
            nodes=tuple(nodes),
            edges=tuple(edges),
            unresolved_references=tuple(unresolved),
            source_trace=trace,
        )

    @staticmethod
    def _normalize(raw: dict[str, Any]) -> dict[str, Any]:
        required = ("id", "title", "url")
        missing = [key for key in required if not isinstance(raw.get(key), str) or not raw[key]]
        if missing:
            raise ValueError(f"Malformed Notion page record; missing {', '.join(missing)}")
        normalized = {
            "id": raw["id"],
            "type": raw.get("type", "page"),
            "title": raw["title"],
            "url": raw["url"],
            "authority_role": raw.get("authority_role", "AUTHORITATIVE"),
            "partial": bool(raw.get("partial", False)),
        }
        parent_id = raw.get("parent_id")
        if parent_id is not None:
            if not isinstance(parent_id, str) or not parent_id:
                raise ValueError("parent_id must be a non-empty string or null")
            normalized["parent_id"] = parent_id
        return normalized
